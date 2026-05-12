"""Tests for CLI persistence helpers."""

from datetime import date, datetime

from click.testing import CliRunner

import stocksage.cli as cli_main
from core.models import Analysis, AnalysisDetail, Outcome
from stocksage.cli import _prepare_analysis_row


def test_prepare_analysis_row_skips_existing_without_force(db, completed_analysis):
    prep = _prepare_analysis_row(db, "AAPL", date(2026, 1, 2), force=False)

    assert prep.should_run is False
    assert prep.reason == "completed"
    assert prep.analysis.id == completed_analysis.id
    assert db.query(Analysis).count() == 1


def test_prepare_analysis_row_force_reuses_and_resets_existing(db, completed_analysis):
    db.add(
        Outcome(
            analysis_id=completed_analysis.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=0.03,
            alpha_return=0.01,
            holding_days=5,
            reflection="Useful reflection.",
        )
    )
    db.commit()

    prep = _prepare_analysis_row(db, "AAPL", date(2026, 1, 2), force=True)

    assert prep.should_run is True
    assert prep.reason == "forced"
    assert prep.analysis.id == completed_analysis.id
    assert prep.analysis.status == "running"
    assert prep.analysis.rating is None
    assert prep.analysis.error_message is None
    assert db.query(Analysis).count() == 1
    assert db.query(AnalysisDetail).filter_by(analysis_id=completed_analysis.id).first() is None
    assert db.query(Outcome).filter_by(analysis_id=completed_analysis.id).first() is None


def test_summary_command_prints_trend_data(db, completed_analysis, monkeypatch):
    db.add(
        Outcome(
            analysis_id=completed_analysis.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=0.03,
            alpha_return=0.01,
            holding_days=5,
            reflection="Directionally useful.",
        )
    )
    db.commit()

    class SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(cli_main, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(cli_main, "init_db", lambda: None)

    result = CliRunner().invoke(cli_main.cli, ["summary", "AAPL"])

    assert result.exit_code == 0
    assert "Directional accuracy" in result.output
    assert "Recent analyses" in result.output
    assert "Directionally useful" in result.output


def test_analyze_command_marks_failed_on_analyzer_error(db, monkeypatch):
    class SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, *_args):
            return False

    class FailingAnalyzer:
        def __init__(self, **_kwargs):
            pass

        def run(self, *_args):
            raise RuntimeError("provider unavailable")

    monkeypatch.setattr(cli_main, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(cli_main, "init_db", lambda: None)
    monkeypatch.setattr(cli_main, "Analyzer", FailingAnalyzer)

    result = CliRunner().invoke(
        cli_main.cli,
        ["analyze", "MSFT", "--date", "2026-01-08"],
    )

    assert result.exit_code == 1
    row = db.query(Analysis).filter_by(ticker="MSFT").one()
    assert row.status == "failed"
    assert row.error_message == "provider unavailable"
