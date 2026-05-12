"""Tests for TradingAgents memory-log sync."""

import json
from datetime import date, datetime
from types import SimpleNamespace

from core.memory_sync import MEMORY_ENTRY_SEPARATOR, sync_resolved_outcomes_to_memory
from core.models import Analysis, AnalysisDetail, Outcome


def _cfg(path):
    return SimpleNamespace(memory_log_path=path)


def _add_resolved_analysis(
    db,
    ticker: str = "AAPL",
    trade_date: date = date(2026, 1, 2),
    rating: str = "Overweight",
    raw_return: float = 0.02,
    alpha_return: float = 0.01,
    full_state_decision: str | None = "**Rating**: Overweight\n\nState decision.",
):
    row = Analysis(
        ticker=ticker,
        trade_date=trade_date,
        run_at=datetime(2026, 1, 2, 9, 0),
        completed_at=datetime(2026, 1, 2, 9, 5),
        status="completed",
        rating=rating,
        executive_summary="Stored summary.",
        investment_thesis="Stored thesis.",
        llm_provider="openai",
        deep_model="gpt-5.4",
        quick_model="gpt-5.4-mini",
    )
    db.add(row)
    db.flush()
    full_state_json = None
    if full_state_decision is not None:
        full_state_json = json.dumps({"final_trade_decision": full_state_decision})
    db.add(
        AnalysisDetail(
            analysis_id=row.id,
            full_state_json=full_state_json,
        )
    )
    db.add(
        Outcome(
            analysis_id=row.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=raw_return,
            alpha_return=alpha_return,
            holding_days=5,
            reflection=f"{ticker} resolved reflection.",
        )
    )
    db.commit()
    return row


def test_sync_updates_pending_memory_entry_idempotently(db, tmp_path):
    _add_resolved_analysis(db)
    log_path = tmp_path / "memory" / "trading_memory.md"
    log_path.parent.mkdir()
    log_path.write_text(
        "[2026-01-02 | AAPL | Overweight | pending]\n\n"
        "DECISION:\nOld pending decision."
        f"{MEMORY_ENTRY_SEPARATOR}",
        encoding="utf-8",
    )

    report = sync_resolved_outcomes_to_memory(db, _cfg(log_path))

    text = log_path.read_text(encoding="utf-8")
    assert report.resolved_rows == 1
    assert report.updated == 1
    assert report.appended == 0
    assert "[2026-01-02 | AAPL | Overweight | +2.0% | +1.0% | 5d]" in text
    assert "| pending]" not in text
    assert "State decision." in text
    assert "AAPL resolved reflection." in text

    second = sync_resolved_outcomes_to_memory(db, _cfg(log_path))

    assert second.changed == 0
    assert log_path.read_text(encoding="utf-8").count("2026-01-02 | AAPL") == 1


def test_sync_appends_missing_resolved_entry_with_fallback_decision(db, tmp_path):
    _add_resolved_analysis(
        db,
        ticker="PLTR",
        trade_date=date(2026, 1, 3),
        rating="Underweight",
        raw_return=0.0068,
        alpha_return=-0.0025,
        full_state_decision=None,
    )
    log_path = tmp_path / "trading_memory.md"

    report = sync_resolved_outcomes_to_memory(db, _cfg(log_path))

    text = log_path.read_text(encoding="utf-8")
    assert report.appended == 1
    assert "[2026-01-03 | PLTR | Underweight | +0.7% | -0.2% | 5d]" in text
    assert "**Rating**: Underweight" in text
    assert "**Executive Summary**: Stored summary." in text
    assert "PLTR resolved reflection." in text
