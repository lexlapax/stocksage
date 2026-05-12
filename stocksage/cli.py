"""StockSage CLI entry point."""

import sys
from datetime import date

import click
from rich.console import Console
from tabulate import tabulate

from config import settings
from core.analysis_runs import (
    mark_analysis_failed,
    persist_analysis_result,
)
from core.analysis_runs import (
    prepare_analysis_row as _prepare_analysis_row,
)
from core.analyzer import AnalysisResult, Analyzer
from core.db import SessionLocal, init_db
from core.memory_sync import sync_resolved_outcomes_to_memory
from core.models import Analysis
from core.outcomes import resolve_pending_report
from core.queueing import (
    QUEUE_STATUSES,
    clear_completed_queue_items,
    enqueue_analysis,
    list_queue_items,
    retry_failed_queue_items,
    retry_queue_item,
)
from core.trends import (
    get_all_ticker_stats,
    get_model_stats,
    get_ticker_stats,
    is_correct_alpha_direction,
    is_correct_raw_direction,
)
from worker.runner import run_queued_jobs

console = Console()


@click.group()
def cli():
    """StockSage — LLM-powered stock analysis with persistent history."""
    pass


@cli.command()
@click.argument("ticker")
@click.option("--date", "trade_date", default=None, help="Trade date YYYY-MM-DD (default: today)")
@click.option("--debug", is_flag=True, default=False, help="Enable TradingAgents debug streaming")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-run even if analysis already exists for this ticker+date",
)
def analyze(ticker: str, trade_date: str, debug: bool, force: bool):
    """Run a full analysis for TICKER and persist to the database."""
    init_db()
    ticker = ticker.upper()
    parsed_date = date.fromisoformat(trade_date) if trade_date else date.today()

    with SessionLocal() as db:
        prep = _prepare_analysis_row(db, ticker, parsed_date, force, settings)
        if not prep.should_run:
            if prep.reason == "completed":
                detail = f"Already analyzed {ticker} on {parsed_date} (id={prep.analysis.id})."
            else:
                detail = (
                    f"Analysis for {ticker} on {parsed_date} already exists with "
                    f"status={prep.reason} (id={prep.analysis.id})."
                )
            console.print(f"[yellow]{detail} Use --force to re-run.[/yellow]")
            sys.exit(0)
        sync_resolved_outcomes_to_memory(db, settings)
        analysis_id = prep.analysis.id

    console.print(f"[cyan]Analyzing {ticker} for {parsed_date}...[/cyan]")

    try:
        analyzer = Analyzer(cfg=settings, debug=debug)
        result: AnalysisResult = analyzer.run(ticker, parsed_date)
    except Exception as exc:
        with SessionLocal() as db:
            mark_analysis_failed(db, analysis_id, str(exc))
        console.print(f"[red]Analysis failed: {exc}[/red]")
        raise SystemExit(1) from exc

    with SessionLocal() as db:
        persist_analysis_result(db, analysis_id, result)

    console.print("\n[bold green]=== DECISION ===[/bold green]")
    console.print(f"[bold]Ticker:[/bold]  {ticker}")
    console.print(f"[bold]Date:[/bold]    {parsed_date}")
    console.print(f"[bold]Rating:[/bold]  {result.rating}")
    if result.price_target:
        console.print(f"[bold]Target:[/bold]  ${result.price_target:.2f}")
    if result.time_horizon:
        console.print(f"[bold]Horizon:[/bold] {result.time_horizon}")
    console.print(f"\n[bold]Summary:[/bold]\n{result.executive_summary}")
    console.print(f"\n[bold]Thesis:[/bold]\n{result.investment_thesis[:600]}...")


@cli.command()
@click.option(
    "--holding-days",
    default=None,
    type=int,
    help="Override default holding days for outcome resolution",
)
@click.option(
    "--force", is_flag=True, default=False, help="Re-resolve analyses that already have outcomes"
)
def resolve(holding_days: int, force: bool):
    """Fetch actual returns for analyses that have no outcome yet."""
    init_db()
    with SessionLocal() as db:
        report = resolve_pending_report(db, settings, holding_days, force=force)
        memory_report = sync_resolved_outcomes_to_memory(db, settings)
    console.print(f"[green]Resolved {report.resolved} outcome(s).[/green]")
    console.print(
        f"Attempted: {report.attempted} | Too recent: {report.too_recent} | "
        f"Already resolved: {report.already_resolved} | "
        f"Insufficient price data: {report.insufficient_price_data}"
    )
    if memory_report.resolved_rows:
        console.print(
            f"Memory sync: {memory_report.resolved_rows} resolved outcome(s), "
            f"{memory_report.appended} appended, {memory_report.updated} updated."
        )


@cli.command()
@click.argument("ticker")
@click.option("--n", default=10, help="Number of past analyses to show")
def summary(ticker: str, n: int):
    """Print analysis history and outcomes for TICKER."""
    init_db()
    ticker = ticker.upper()
    with SessionLocal() as db:
        rows = (
            db.query(Analysis)
            .filter(Analysis.ticker == ticker, Analysis.status == "completed")
            .order_by(Analysis.trade_date.desc())
            .limit(n)
            .all()
        )

        if not rows:
            console.print(f"[yellow]No completed analyses found for {ticker}.[/yellow]")
            return

        stats = get_ticker_stats(db, ticker)
        table_data = []
        for a in rows:
            outcome = a.outcome
            raw = f"{outcome.raw_return:+.1%}" if outcome else "pending"
            alpha = f"{outcome.alpha_return:+.1%}" if outcome else "pending"
            raw_correct = (
                "yes"
                if outcome and is_correct_raw_direction(a.rating or "", outcome.raw_return)
                else "no"
                if outcome
                else "pending"
            )
            alpha_correct = (
                "yes"
                if outcome and is_correct_alpha_direction(a.rating or "", outcome.alpha_return)
                else "no"
                if outcome
                else "pending"
            )
            snippet = (outcome.reflection or "")[:60] if outcome else ""
            table_data.append(
                [
                    str(a.trade_date),
                    a.rating or "-",
                    raw,
                    alpha,
                    raw_correct,
                    alpha_correct,
                    snippet,
                ]
            )

    if stats:
        console.print(f"\n[bold]StockSage Summary: {ticker}[/bold] ({len(rows)} recent analyses)\n")
        console.print(
            f"Resolved: {stats.resolved_count}/{stats.total_analyses}   "
            f"Alpha-direction accuracy: {stats.alpha_directional_accuracy:.0%}   "
            f"Raw-direction accuracy: {stats.raw_directional_accuracy:.0%}"
        )
        console.print(
            f"Avg raw return: {stats.avg_raw_return:+.1%}   "
            f"Avg alpha: {stats.avg_alpha_return:+.1%}"
        )
        if stats.rating_counts:
            console.print("\n[bold]By rating:[/bold]")
            rating_rows = []
            for rating in sorted(stats.rating_counts):
                rating_rows.append(
                    [
                        rating,
                        stats.rating_counts[rating],
                        f"{stats.avg_return_by_rating.get(rating, 0.0):+.1%}",
                        f"{stats.avg_alpha_by_rating.get(rating, 0.0):+.1%}",
                        f"{stats.accuracy_by_rating.get(rating, 0.0):.0%}",
                        f"{stats.raw_accuracy_by_rating.get(rating, 0.0):.0%}",
                    ]
                )
            print(
                tabulate(
                    rating_rows,
                    headers=["Rating", "Calls", "Avg Raw", "Avg Alpha", "Alpha Acc", "Raw Acc"],
                    tablefmt="rounded_outline",
                )
            )
        if stats.accuracy_trend:
            trend = " ".join("hit" if ok else "miss" for _, ok in stats.accuracy_trend[-n:])
            console.print(f"\n[bold]Alpha accuracy trend:[/bold] {trend}")

    console.print("\n[bold]Recent analyses:[/bold]")
    print(
        tabulate(
            table_data,
            headers=["Date", "Rating", "Raw Ret", "Alpha", "Raw OK", "Alpha OK", "Reflection"],
            tablefmt="rounded_outline",
        )
    )


@cli.command("list")
@click.option("--ticker", default=None, help="Filter by ticker")
@click.option(
    "--status",
    default=None,
    type=click.Choice(["queued", "running", "completed", "failed"]),
    help="Filter by status",
)
@click.option("--n", default=20, help="Max rows to show")
def list_analyses(ticker: str, status: str, n: int):
    """List recent analyses."""
    init_db()
    with SessionLocal() as db:
        q = db.query(Analysis).order_by(Analysis.run_at.desc())
        if ticker:
            q = q.filter(Analysis.ticker == ticker.upper())
        if status:
            q = q.filter(Analysis.status == status)
        rows = q.limit(n).all()

    table_data = [
        [a.id, a.ticker, str(a.trade_date), a.status, a.rating or "-", str(a.run_at)[:16]]
        for a in rows
    ]
    print(
        tabulate(
            table_data,
            headers=["ID", "Ticker", "Date", "Status", "Rating", "Run At"],
            tablefmt="rounded_outline",
        )
    )


@cli.group()
def queue():
    """Manage queued analysis jobs."""
    pass


@queue.command("add")
@click.argument("ticker")
@click.option("--date", "trade_date", default=None, help="Trade date YYYY-MM-DD (default: today)")
@click.option("--priority", default=0, type=int, help="Higher priority runs first")
def queue_add(ticker: str, trade_date: str | None, priority: int):
    """Queue one ticker for analysis."""
    init_db()
    parsed_date = _parse_trade_date(trade_date)
    with SessionLocal() as db:
        result = enqueue_analysis(db, ticker, parsed_date, priority)
    if result.created:
        console.print(
            f"[green]Queued {ticker.upper()} on {parsed_date} "
            f"(id={result.queue_item.id}, priority={priority}).[/green]"
        )
    elif result.queue_item is not None:
        console.print(
            f"[yellow]{ticker.upper()} on {parsed_date} already has queue job "
            f"id={result.queue_item.id} status={result.reason}.[/yellow]"
        )
    else:
        console.print(
            f"[yellow]{ticker.upper()} on {parsed_date} skipped: {result.reason} "
            f"(analysis id={result.analysis.id}).[/yellow]"
        )


@queue.command("add-batch")
@click.argument("tickers", nargs=-1, required=True)
@click.option("--date", "trade_date", default=None, help="Trade date YYYY-MM-DD (default: today)")
@click.option("--priority", default=0, type=int, help="Higher priority runs first")
def queue_add_batch(tickers: tuple[str, ...], trade_date: str | None, priority: int):
    """Queue multiple tickers for analysis."""
    init_db()
    parsed_date = _parse_trade_date(trade_date)
    created = 0
    skipped = 0
    rows = []
    with SessionLocal() as db:
        for ticker in tickers:
            result = enqueue_analysis(db, ticker, parsed_date, priority)
            if result.created:
                created += 1
                rows.append([result.queue_item.id, ticker.upper(), parsed_date, "queued"])
            else:
                skipped += 1
                queue_id = result.queue_item.id if result.queue_item is not None else "-"
                rows.append([queue_id, ticker.upper(), parsed_date, result.reason])
    console.print(f"[green]Queued {created} ticker(s); skipped {skipped}.[/green]")
    print(
        tabulate(rows, headers=["Queue ID", "Ticker", "Date", "Result"], tablefmt="rounded_outline")
    )


@queue.command("list")
@click.option("--status", default=None, type=click.Choice(QUEUE_STATUSES), help="Filter by status")
@click.option("--n", default=50, type=int, help="Max rows to show")
def queue_list(status: str | None, n: int):
    """List queued analysis jobs."""
    init_db()
    with SessionLocal() as db:
        rows = list_queue_items(db, status=status, limit=n)
    table_data = [
        [
            item.id,
            item.ticker,
            str(item.trade_date),
            item.status,
            item.priority,
            item.attempts,
            item.analysis_id or "-",
            _short_time(item.queued_at),
            _short_time(item.started_at),
            _short_time(item.completed_at),
            _short_error(item.last_error),
        ]
        for item in rows
    ]
    print(
        tabulate(
            table_data,
            headers=[
                "ID",
                "Ticker",
                "Date",
                "Status",
                "Priority",
                "Attempts",
                "Analysis",
                "Queued",
                "Started",
                "Done",
                "Error",
            ],
            tablefmt="rounded_outline",
        )
    )


@queue.command("retry")
@click.argument("queue_id", required=False, type=int)
@click.option("--failed", "retry_failed", is_flag=True, help="Retry all failed queue jobs")
def queue_retry(queue_id: int | None, retry_failed: bool):
    """Retry one failed queue job or all failed jobs."""
    if queue_id is None and not retry_failed:
        raise click.UsageError("Pass QUEUE_ID or --failed.")
    init_db()
    with SessionLocal() as db:
        if retry_failed:
            count = retry_failed_queue_items(db)
            console.print(f"[green]Re-queued {count} failed job(s).[/green]")
            return
        row = retry_queue_item(db, queue_id)
    if row is None:
        console.print(f"[red]Queue job {queue_id} not found.[/red]")
        raise SystemExit(1)
    console.print(f"[green]Re-queued job {row.id} for {row.ticker} on {row.trade_date}.[/green]")


@queue.command("clear-completed")
def queue_clear_completed():
    """Delete completed queue records."""
    init_db()
    with SessionLocal() as db:
        count = clear_completed_queue_items(db)
    console.print(f"[green]Cleared {count} completed queue job(s).[/green]")


@queue.command("run")
@click.option("--limit", default=None, type=int, help="Maximum queued jobs to process")
@click.option("--max-workers", default=1, type=int, help="Maximum concurrent analyses")
@click.option("--debug", is_flag=True, default=False, help="Enable TradingAgents debug streaming")
@click.option(
    "--reset-stale-minutes",
    default=120,
    type=int,
    help="Re-queue running jobs older than this many minutes",
)
def queue_run(limit: int | None, max_workers: int, debug: bool, reset_stale_minutes: int):
    """Run queued analysis jobs."""
    init_db()
    report = run_queued_jobs(
        max_jobs=limit,
        max_workers=max_workers,
        debug=debug,
        reset_stale_minutes=reset_stale_minutes,
    )
    console.print(
        f"[green]Worker attempted {report.attempted} job(s): "
        f"{report.completed} completed, {report.failed} failed, "
        f"{report.skipped} skipped, {report.reset_stale} reset stale.[/green]"
    )


@cli.command()
@click.option(
    "--by",
    "sort_by",
    default="accuracy",
    type=click.Choice(["accuracy", "alpha", "count"]),
    help="Metric to rank by",
)
@click.option("--min-resolved", default=3, type=int, help="Minimum resolved outcomes required")
def leaderboard(sort_by: str, min_resolved: int):
    """Rank tickers by resolved outcome performance."""
    init_db()
    with SessionLocal() as db:
        stats = [s for s in get_all_ticker_stats(db) if s.resolved_count >= min_resolved]

    key_funcs = {
        "accuracy": lambda s: s.directional_accuracy,
        "alpha": lambda s: s.avg_alpha_return,
        "count": lambda s: s.resolved_count,
    }
    stats.sort(key=key_funcs[sort_by], reverse=True)

    table_data = []
    for idx, item in enumerate(stats, start=1):
        best_rating = "-"
        if item.avg_alpha_by_rating:
            best_rating = max(item.avg_alpha_by_rating, key=item.avg_alpha_by_rating.get)
        table_data.append(
            [
                idx,
                item.ticker,
                item.resolved_count,
                f"{item.alpha_directional_accuracy:.0%}",
                f"{item.avg_alpha_return:+.1%}",
                best_rating,
            ]
        )

    print(
        tabulate(
            table_data,
            headers=["Rank", "Ticker", "Resolved", "Alpha Acc", "Avg Alpha", "Best Rating"],
            tablefmt="rounded_outline",
        )
    )


@cli.command("models")
def models_command():
    """Show resolved outcome performance by model."""
    init_db()
    with SessionLocal() as db:
        stats = get_model_stats(db)

    table_data = [
        [
            item.llm_provider,
            item.deep_model,
            item.total_analyses,
            item.resolved_count,
            f"{item.alpha_directional_accuracy:.0%}",
            f"{item.avg_alpha_return:+.1%}",
        ]
        for item in stats
    ]
    print(
        tabulate(
            table_data,
            headers=["Provider", "Model", "Analyses", "Resolved", "Alpha Acc", "Avg Alpha"],
            tablefmt="rounded_outline",
        )
    )


def _parse_trade_date(value: str | None) -> date:
    return date.fromisoformat(value) if value else date.today()


def _short_time(value) -> str:
    return str(value)[:16] if value else "-"


def _short_error(value: str | None) -> str:
    if not value:
        return ""
    return value if len(value) <= 50 else f"{value[:47]}..."


if __name__ == "__main__":
    cli()
