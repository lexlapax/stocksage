"""StockSage CLI entry point."""

import json
import sys
from datetime import UTC, date, datetime
from typing import NamedTuple

import click
from rich.console import Console
from tabulate import tabulate

from config import settings
from core.analyzer import AnalysisResult, Analyzer
from core.db import SessionLocal, init_db
from core.memory_sync import sync_resolved_outcomes_to_memory
from core.models import Analysis, AnalysisDetail
from core.outcomes import resolve_pending_report
from core.trends import (
    get_all_ticker_stats,
    get_model_stats,
    get_ticker_stats,
    is_correct_alpha_direction,
    is_correct_raw_direction,
)

console = Console()


class AnalysisRunPrep(NamedTuple):
    analysis: Analysis
    should_run: bool
    reason: str


def _prepare_analysis_row(db, ticker: str, trade_date: date, force: bool) -> AnalysisRunPrep:
    existing = (
        db.query(Analysis)
        .filter(Analysis.ticker == ticker, Analysis.trade_date == trade_date)
        .first()
    )

    if existing and not force:
        return AnalysisRunPrep(existing, False, existing.status)

    now = datetime.now(UTC)
    if existing:
        if existing.detail is not None:
            db.delete(existing.detail)
        if existing.outcome is not None:
            db.delete(existing.outcome)
        db.flush()

        existing.run_at = now
        existing.completed_at = None
        existing.status = "running"
        existing.rating = None
        existing.executive_summary = None
        existing.investment_thesis = None
        existing.price_target = None
        existing.time_horizon = None
        existing.llm_provider = settings.llm_provider
        existing.deep_model = settings.deep_think_llm
        existing.quick_model = settings.quick_think_llm
        existing.error_message = None
        db.commit()
        db.refresh(existing)
        return AnalysisRunPrep(existing, True, "forced")

    row = Analysis(
        ticker=ticker,
        trade_date=trade_date,
        run_at=now,
        status="running",
        llm_provider=settings.llm_provider,
        deep_model=settings.deep_think_llm,
        quick_model=settings.quick_think_llm,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AnalysisRunPrep(row, True, "created")


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
        prep = _prepare_analysis_row(db, ticker, parsed_date, force)
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
            row = db.get(Analysis, analysis_id)
            row.status = "failed"
            row.error_message = str(exc)
            db.commit()
        console.print(f"[red]Analysis failed: {exc}[/red]")
        raise SystemExit(1) from exc

    with SessionLocal() as db:
        row = db.get(Analysis, analysis_id)
        row.status = "completed"
        row.completed_at = datetime.now(UTC)
        row.rating = result.rating
        row.executive_summary = result.executive_summary
        row.investment_thesis = result.investment_thesis
        row.price_target = result.price_target
        row.time_horizon = result.time_horizon

        detail = AnalysisDetail(
            analysis_id=analysis_id,
            market_report=result.market_report,
            sentiment_report=result.sentiment_report,
            news_report=result.news_report,
            fundamentals_report=result.fundamentals_report,
            bull_history=result.bull_history,
            bear_history=result.bear_history,
            research_decision=result.research_decision,
            trader_plan=result.trader_plan,
            risk_aggressive=result.risk_aggressive,
            risk_conservative=result.risk_conservative,
            risk_neutral=result.risk_neutral,
            risk_decision=result.risk_decision,
            full_state_json=json.dumps(result.full_state, default=str),
        )
        db.add(detail)
        db.commit()

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


if __name__ == "__main__":
    cli()
