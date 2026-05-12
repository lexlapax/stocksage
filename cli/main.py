"""StockSage CLI — entry point for all commands."""

import json
import sys
from datetime import UTC, date, datetime

import click
from rich.console import Console
from rich.table import Table
from tabulate import tabulate

from config import settings
from core.analyzer import Analyzer, AnalysisResult
from core.db import SessionLocal, init_db
from core.models import Analysis, AnalysisDetail, Outcome
from core.outcomes import resolve_pending

console = Console()


@click.group()
def cli():
    """StockSage — LLM-powered stock analysis with persistent history."""
    pass


@cli.command()
@click.argument("ticker")
@click.option("--date", "trade_date", default=None,
              help="Trade date YYYY-MM-DD (default: today)")
@click.option("--debug", is_flag=True, default=False,
              help="Enable TradingAgents debug streaming")
@click.option("--force", is_flag=True, default=False,
              help="Re-run even if analysis already exists for this ticker+date")
def analyze(ticker: str, trade_date: str, debug: bool, force: bool):
    """Run a full analysis for TICKER and persist to the database."""
    init_db()
    ticker = ticker.upper()
    parsed_date = date.fromisoformat(trade_date) if trade_date else date.today()

    with SessionLocal() as db:
        existing = (
            db.query(Analysis)
            .filter(Analysis.ticker == ticker, Analysis.trade_date == parsed_date,
                    Analysis.status == "completed")
            .first()
        )
        if existing and not force:
            console.print(
                f"[yellow]Already analyzed {ticker} on {parsed_date} "
                f"(id={existing.id}). Use --force to re-run.[/yellow]"
            )
            sys.exit(0)

        now = datetime.now(UTC)
        row = Analysis(
            ticker=ticker,
            trade_date=parsed_date,
            run_at=now,
            status="running",
            llm_provider=settings.llm_provider,
            deep_model=settings.deep_think_llm,
            quick_model=settings.quick_think_llm,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        analysis_id = row.id

    console.print(f"[cyan]Analyzing {ticker} for {parsed_date}…[/cyan]")

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
        raise SystemExit(1)

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

    console.print("\n[bold green]═══ DECISION ═══[/bold green]")
    console.print(f"[bold]Ticker:[/bold]  {ticker}")
    console.print(f"[bold]Date:[/bold]    {parsed_date}")
    console.print(f"[bold]Rating:[/bold]  {result.rating}")
    if result.price_target:
        console.print(f"[bold]Target:[/bold]  ${result.price_target:.2f}")
    if result.time_horizon:
        console.print(f"[bold]Horizon:[/bold] {result.time_horizon}")
    console.print(f"\n[bold]Summary:[/bold]\n{result.executive_summary}")
    console.print(f"\n[bold]Thesis:[/bold]\n{result.investment_thesis[:600]}…")


@cli.command()
@click.option("--holding-days", default=None, type=int,
              help="Override default holding days for outcome resolution")
def resolve(holding_days: int):
    """Fetch actual returns for analyses that have no outcome yet."""
    init_db()
    with SessionLocal() as db:
        count = resolve_pending(db, settings, holding_days)
    console.print(f"[green]Resolved {count} outcome(s).[/green]")


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

    table_data = []
    for a in rows:
        outcome = a.outcome
        raw = f"{outcome.raw_return:+.1%}" if outcome else "pending"
        alpha = f"{outcome.alpha_return:+.1%}" if outcome else "pending"
        snippet = (outcome.reflection or "")[:60] if outcome else ""
        table_data.append([
            str(a.trade_date), a.rating or "—", raw, alpha, snippet
        ])

    console.print(f"\n[bold]StockSage Summary: {ticker}[/bold] ({len(rows)} analyses)\n")
    print(tabulate(
        table_data,
        headers=["Date", "Rating", "Raw Ret", "Alpha", "Reflection"],
        tablefmt="rounded_outline",
    ))


@cli.command("list")
@click.option("--ticker", default=None, help="Filter by ticker")
@click.option("--status", default=None,
              type=click.Choice(["queued", "running", "completed", "failed"]),
              help="Filter by status")
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
        [a.id, a.ticker, str(a.trade_date), a.status, a.rating or "—",
         str(a.run_at)[:16]]
        for a in rows
    ]
    print(tabulate(
        table_data,
        headers=["ID", "Ticker", "Date", "Status", "Rating", "Run At"],
        tablefmt="rounded_outline",
    ))


if __name__ == "__main__":
    cli()
