"""Tests for outcome resolution logic (no live network calls)."""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from core.models import Analysis, Outcome
from core.outcomes import _compute_returns, resolve_pending


def _make_price_df(base_price: float, days: int = 10, start: str = "2026-01-02") -> pd.DataFrame:
    dates = pd.date_range(start, periods=days, freq="B")
    prices = [base_price * (1 + i * 0.005) for i in range(days)]
    return pd.DataFrame({"Close": prices}, index=dates)


def test_compute_returns_basic():
    stock_df = _make_price_df(100.0)
    spy_df = _make_price_df(400.0)
    prices = {"AAPL": stock_df}

    result = _compute_returns("AAPL", "2026-01-02", 5, prices, spy_df)
    assert result is not None
    raw, alpha, days = result
    assert days == 5
    assert raw == pytest.approx(0.025, abs=1e-3)
    assert alpha == pytest.approx(0.0, abs=1e-3)  # same % move → zero alpha


def test_compute_returns_missing_ticker():
    result = _compute_returns("MISSING", "2026-01-02", 5, {}, _make_price_df(400.0))
    assert result is None


def test_compute_returns_insufficient_data():
    tiny_df = _make_price_df(100.0, days=1)
    result = _compute_returns("AAPL", "2026-01-02", 5, {"AAPL": tiny_df}, tiny_df)
    assert result is None


def test_resolve_pending_skips_recent_analyses(db):
    # An analysis from yesterday is within the holding window — must not be resolved
    recent_analysis = Analysis(
        ticker="AAPL",
        trade_date=date.today() - timedelta(days=1),
        run_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        status="completed",
        rating="Buy",
    )
    db.add(recent_analysis)
    db.commit()
    count = resolve_pending(db)
    assert count == 0


def test_resolve_pending_resolves_old_analysis(db):
    old_date = date.today() - timedelta(days=20)
    row = Analysis(
        ticker="TSLA",
        trade_date=old_date,
        run_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        status="completed",
        rating="Hold",
        investment_thesis="Some thesis.",
    )
    db.add(row)
    db.commit()

    stock_df = _make_price_df(200.0, start=str(old_date))
    spy_df = _make_price_df(400.0, start=str(old_date))

    with (
        patch("core.outcomes._batch_fetch", return_value={"TSLA": stock_df}),
        patch("core.outcomes._fetch_single", return_value=spy_df),
        patch("core.outcomes._generate_reflection", return_value="reflection text"),
    ):
        count = resolve_pending(db)

    assert count == 1
    outcome = db.query(Outcome).filter_by(analysis_id=row.id).first()
    assert outcome is not None
    assert outcome.reflection == "reflection text"
