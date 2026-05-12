"""Outcome resolution: fetch actual returns and generate reflections for past analyses."""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session

from config import Settings, settings as _default_settings
from core.models import Analysis, Outcome

logger = logging.getLogger(__name__)


def resolve_pending(
    db: Session,
    cfg: Settings = _default_settings,
    holding_days: Optional[int] = None,
) -> int:
    """Resolve all completed analyses that have no Outcome yet.

    Only processes analyses whose trade_date is old enough that `holding_days`
    of price data is available. Returns the count of newly resolved analyses.
    """
    days = holding_days or cfg.outcome_holding_days
    cutoff = date.today() - timedelta(days=days + 3)  # buffer for weekends

    pending: list[Analysis] = (
        db.query(Analysis)
        .outerjoin(Outcome)
        .filter(
            Analysis.status == "completed",
            Analysis.trade_date <= cutoff,
            Outcome.id.is_(None),
        )
        .all()
    )

    if not pending:
        return 0

    # Batch yfinance fetch: gather unique tickers + shared date window
    tickers = list({a.ticker for a in pending})
    min_date = min(a.trade_date for a in pending)
    end_date = date.today()

    logger.info("Fetching price data for %d tickers (%s → %s)", len(tickers), min_date, end_date)
    prices = _batch_fetch(tickers, str(min_date), str(end_date + timedelta(days=1)))
    spy_prices = _fetch_single("SPY", str(min_date), str(end_date + timedelta(days=1)))

    resolved = 0
    for analysis in pending:
        result = _compute_returns(analysis.ticker, str(analysis.trade_date), days, prices, spy_prices)
        if result is None:
            logger.debug("Returns not yet available for %s on %s", analysis.ticker, analysis.trade_date)
            continue

        raw_ret, alpha_ret, actual_days = result
        reflection = _generate_reflection(
            decision_text=analysis.investment_thesis or "",
            raw_return=raw_ret,
            alpha_return=alpha_ret,
            cfg=cfg,
        )

        db.add(Outcome(
            analysis_id=analysis.id,
            resolved_at=datetime.utcnow(),
            raw_return=raw_ret,
            alpha_return=alpha_ret,
            holding_days=actual_days,
            reflection=reflection,
        ))
        resolved += 1

    if resolved:
        db.commit()

    return resolved


def _batch_fetch(tickers: list[str], start: str, end: str) -> dict:
    """Download OHLCV for multiple tickers at once. Returns {ticker: DataFrame}."""
    try:
        data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
        if len(tickers) == 1:
            return {tickers[0]: data}
        # multi-ticker download returns MultiIndex columns
        return {t: data.xs(t, axis=1, level=1) for t in tickers if t in data.columns.get_level_values(1)}
    except Exception as e:
        logger.warning("Batch price fetch failed: %s", e)
        return {}


def _fetch_single(ticker: str, start: str, end: str):
    try:
        return yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    except Exception:
        return None


def _compute_returns(
    ticker: str,
    trade_date: str,
    holding_days: int,
    prices: dict,
    spy_prices,
) -> Optional[tuple[float, float, int]]:
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
    spy_ret = float(
        (spy["Close"].iloc[actual_days] - spy["Close"].iloc[0]) / spy["Close"].iloc[0]
    )
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
        correct = (raw_return > 0 and "buy" in decision_text.lower()) or \
                  (raw_return < 0 and "sell" in decision_text.lower())
        verdict = "correct" if correct else "incorrect"
        return (
            f"Stock moved {direction} {raw_return:+.1%} ({alpha_return:+.1%} vs SPY). "
            f"The {cfg.deep_think_llm} analysis was directionally {verdict}."
        )
