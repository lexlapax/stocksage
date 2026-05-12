"""Tests for trend and accuracy analytics."""

from datetime import date, datetime

import pytest

from core.models import Analysis, Outcome
from core.trends import (
    get_accuracy_trend,
    get_all_ticker_stats,
    get_cross_ticker_lessons,
    get_model_stats,
    get_ticker_stats,
    is_correct_direction,
)


def _add_analysis(
    db,
    ticker: str,
    trade_date: date,
    rating: str,
    raw_return: float | None,
    alpha_return: float | None,
    provider: str = "openai",
    model: str = "gpt-5.4",
):
    row = Analysis(
        ticker=ticker,
        trade_date=trade_date,
        run_at=datetime(2026, 1, 1, 9, 0),
        completed_at=datetime(2026, 1, 1, 9, 5),
        status="completed",
        rating=rating,
        llm_provider=provider,
        deep_model=model,
        quick_model="gpt-5.4-mini",
    )
    db.add(row)
    db.flush()
    if raw_return is not None and alpha_return is not None:
        db.add(
            Outcome(
                analysis_id=row.id,
                resolved_at=datetime(2026, 1, 10),
                raw_return=raw_return,
                alpha_return=alpha_return,
                holding_days=5,
                reflection=f"{ticker} reflection.",
            )
        )
    db.commit()
    return row


def test_is_correct_direction():
    assert is_correct_direction("Buy", 0.01) is True
    assert is_correct_direction("Overweight", 0.01) is True
    assert is_correct_direction("Sell", -0.01) is True
    assert is_correct_direction("Underweight", -0.01) is True
    assert is_correct_direction("Hold", 0.019) is True
    assert is_correct_direction("Hold", 0.021) is False


def test_get_ticker_stats(db):
    _seed_trend_rows(db)

    stats = get_ticker_stats(db, "aapl")

    assert stats is not None
    assert stats.ticker == "AAPL"
    assert stats.total_analyses == 4
    assert stats.resolved_count == 3
    assert stats.directional_accuracy == pytest.approx(2 / 3)
    assert stats.avg_raw_return == pytest.approx(0.03)
    assert stats.avg_alpha_return == pytest.approx(0.01)
    assert stats.avg_return_by_rating["Buy"] == pytest.approx(0.05)
    assert stats.rating_counts["Hold"] == 1
    assert stats.accuracy_by_rating["Sell"] == pytest.approx(0.0)


def test_get_accuracy_trend(db):
    _seed_trend_rows(db)

    trend = get_accuracy_trend(db, "AAPL", window=2)

    assert [value for _, value in trend] == pytest.approx([1.0, 1.0, 0.5])


def test_get_all_ticker_stats(db):
    _seed_trend_rows(db)

    stats = get_all_ticker_stats(db)

    assert [item.ticker for item in stats] == ["AAPL", "MSFT"]


def test_get_model_stats(db):
    _seed_trend_rows(db)

    stats = get_model_stats(db)
    by_model = {(item.llm_provider, item.deep_model): item for item in stats}

    openai = by_model[("openai", "gpt-5.4")]
    assert openai.total_analyses == 4
    assert openai.resolved_count == 3
    assert openai.directional_accuracy == pytest.approx(2 / 3)

    anthropic = by_model[("anthropic", "claude-opus")]
    assert anthropic.total_analyses == 1
    assert anthropic.avg_alpha_return == pytest.approx(0.04)


def test_get_cross_ticker_lessons(db):
    _seed_trend_rows(db)

    lessons = get_cross_ticker_lessons(db, n=1)

    assert "Recent StockSage outcome lessons:" in lessons
    assert "MSFT" in lessons
    assert "raw +4.0%" in lessons


def _seed_trend_rows(db):
    _add_analysis(db, "AAPL", date(2026, 1, 2), "Buy", 0.05, 0.02)
    _add_analysis(db, "AAPL", date(2026, 1, 3), "Hold", 0.01, 0.00)
    _add_analysis(db, "AAPL", date(2026, 1, 4), "Sell", 0.03, 0.01)
    _add_analysis(db, "AAPL", date(2026, 1, 5), "Buy", None, None)
    _add_analysis(
        db,
        "MSFT",
        date(2026, 1, 6),
        "Overweight",
        0.04,
        0.04,
        provider="anthropic",
        model="claude-opus",
    )
