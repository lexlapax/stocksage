"""Outcome resolution: fetch actual returns and generate reflections for past analyses."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from config import Settings
from config import settings as _default_settings
from core.models import Analysis, Outcome

logger = logging.getLogger(__name__)


@dataclass
class ResolutionReport:
    resolved: int
    attempted: int
    too_recent: int
    already_resolved: int
    insufficient_price_data: int


def resolve_pending(
    db: Session,
    cfg: Settings = _default_settings,
    holding_days: int | None = None,
    force: bool = False,
) -> int:
    return resolve_pending_report(db, cfg, holding_days, force=force).resolved


def resolve_pending_report(
    db: Session,
    cfg: Settings = _default_settings,
    holding_days: int | None = None,
    force: bool = False,
) -> ResolutionReport:
    """Resolve all completed analyses that have no Outcome yet.

    Only processes analyses whose trade_date is old enough that `holding_days`
    of price data is available.
    """
    days = holding_days or cfg.outcome_holding_days
    cutoff = date.today() - timedelta(days=days + 3)  # buffer for weekends

    too_recent = (
        db.query(Analysis)
        .outerjoin(Outcome)
        .filter(
            Analysis.status == "completed",
            Analysis.trade_date > cutoff,
            Outcome.id.is_(None),
        )
        .count()
    )
    already_resolved = (
        0
        if force
        else (db.query(Analysis).join(Outcome).filter(Analysis.status == "completed").count())
    )

    query = (
        db.query(Analysis)
        .outerjoin(Outcome)
        .filter(
            Analysis.status == "completed",
            Analysis.trade_date <= cutoff,
        )
    )
    if not force:
        query = query.filter(Outcome.id.is_(None))

    pending: list[Analysis] = query.all()

    if not pending:
        return ResolutionReport(
            resolved=0,
            attempted=0,
            too_recent=too_recent,
            already_resolved=already_resolved,
            insufficient_price_data=0,
        )

    # Batch yfinance fetch: gather unique tickers + shared date window
    tickers = list({a.ticker for a in pending})
    min_date = min(a.trade_date for a in pending)
    end_date = date.today()

    logger.info("Fetching price data for %d tickers (%s → %s)", len(tickers), min_date, end_date)
    prices = _batch_fetch(tickers, str(min_date), str(end_date + timedelta(days=1)))
    spy_prices = _fetch_single("SPY", str(min_date), str(end_date + timedelta(days=1)))

    resolved = 0
    insufficient = 0
    for analysis in pending:
        result = _compute_returns(
            analysis.ticker, str(analysis.trade_date), days, prices, spy_prices
        )
        if result is None:
            logger.debug(
                "Returns not yet available for %s on %s", analysis.ticker, analysis.trade_date
            )
            insufficient += 1
            continue

        raw_ret, alpha_ret, actual_days = result
        reflection = _generate_reflection(
            decision_text=analysis.investment_thesis or "",
            raw_return=raw_ret,
            alpha_return=alpha_ret,
            cfg=cfg,
        )

        if analysis.outcome is None:
            db.add(
                Outcome(
                    analysis_id=analysis.id,
                    resolved_at=datetime.now(UTC),
                    raw_return=raw_ret,
                    alpha_return=alpha_ret,
                    holding_days=actual_days,
                    reflection=reflection,
                )
            )
        else:
            analysis.outcome.resolved_at = datetime.now(UTC)
            analysis.outcome.raw_return = raw_ret
            analysis.outcome.alpha_return = alpha_ret
            analysis.outcome.holding_days = actual_days
            analysis.outcome.reflection = reflection
        resolved += 1

    if resolved:
        db.commit()

    return ResolutionReport(
        resolved=resolved,
        attempted=len(pending),
        too_recent=too_recent,
        already_resolved=already_resolved,
        insufficient_price_data=insufficient,
    )


def _batch_fetch(tickers: list[str], start: str, end: str) -> dict:
    """Download OHLCV for multiple tickers at once. Returns {ticker: flat DataFrame}."""
    try:
        if len(tickers) == 1:
            # multi_level_index=False gives flat columns directly for a single ticker
            data = yf.download(
                tickers[0],
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                multi_level_index=False,
            )
            return {tickers[0]: data} if not data.empty else {}

        data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            return {
                t: data.xs(t, axis=1, level=1)
                for t in tickers
                if t in data.columns.get_level_values(1)
            }
        return {}
    except Exception as e:
        logger.warning("Batch price fetch failed: %s", e)
        return {}


def _fetch_single(ticker: str, start: str, end: str):
    try:
        df = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
        # history() returns a timezone-aware index; strip it so string comparisons work
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return None


def _compute_returns(
    ticker: str,
    trade_date: str,
    holding_days: int,
    prices: dict,
    spy_prices,
) -> tuple[float, float, int] | None:
    df = prices.get(ticker)
    if df is None or spy_prices is None:
        return None

    # Slice to trade_date onward
    try:
        stock = df[df.index >= trade_date]
        spy = spy_prices[spy_prices.index >= trade_date]
    except Exception:
        return None

    if len(stock) < 2 or len(spy) < 2:
        return None

    actual_days = min(holding_days, len(stock) - 1, len(spy) - 1)
    raw = float(
        (stock["Close"].iloc[actual_days] - stock["Close"].iloc[0]) / stock["Close"].iloc[0]
    )
    spy_ret = float((spy["Close"].iloc[actual_days] - spy["Close"].iloc[0]) / spy["Close"].iloc[0])
    return raw, raw - spy_ret, actual_days


def _generate_reflection(
    decision_text: str,
    raw_return: float,
    alpha_return: float,
    cfg: Settings,
) -> str:
    """Generate an LLM reflection on the analysis outcome.

    Delegates to TradingAgents' Reflector when available; falls back to a
    template string so outcome resolution never hard-fails due to LLM issues.
    """
    try:
        from tradingagents.graph.reflection import Reflector
        from tradingagents.llm_clients import create_llm_client

        client = create_llm_client(
            provider=cfg.llm_provider,
            model=cfg.quick_think_llm,
        )
        reflector = Reflector(client.get_llm())
        return reflector.reflect_on_final_decision(
            final_decision=decision_text,
            raw_return=raw_return,
            alpha_return=alpha_return,
        )
    except Exception as e:
        logger.warning("LLM reflection failed, using template: %s", e)
        direction = "up" if raw_return > 0 else "down"
        correct = (raw_return > 0 and "buy" in decision_text.lower()) or (
            raw_return < 0 and "sell" in decision_text.lower()
        )
        verdict = "correct" if correct else "incorrect"
        return (
            f"Stock moved {direction} {raw_return:+.1%} ({alpha_return:+.1%} vs SPY). "
            f"The {cfg.deep_think_llm} analysis was directionally {verdict}."
        )
