"""Tests for CLI persistence helpers."""

from datetime import date, datetime

from click.testing import CliRunner

import stocksage.cli as cli_main
from core.memory_sync import MemorySyncReport
from core.models import Analysis, AnalysisDetail, AnalysisQueue, Outcome
from core.outcomes import ResolutionReport
from stocksage.cli import _prepare_analysis_row
from worker.runner import WorkerReport


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
    assert "Alpha-direction accuracy" in result.output
    assert "Raw-direction accuracy" in result.output
    assert "Recent analyses" in result.output
    assert "Directionally useful" in result.output


def test_resolve_command_syncs_memory_after_resolution(db, monkeypatch):
    calls = []

    class SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, *_args):
            return False

    def fake_sync(sync_db, _settings):
        calls.append(sync_db)
        return MemorySyncReport(resolved_rows=1, appended=1, updated=0, unchanged=0)

    monkeypatch.setattr(cli_main, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(cli_main, "init_db", lambda: None)
    monkeypatch.setattr(
        cli_main,
        "resolve_pending_report",
        lambda *_args, **_kwargs: ResolutionReport(
            resolved=1,
            attempted=1,
            too_recent=0,
            already_resolved=0,
            insufficient_price_data=0,
        ),
    )
    monkeypatch.setattr(cli_main, "sync_resolved_outcomes_to_memory", fake_sync)

    result = CliRunner().invoke(cli_main.cli, ["resolve"])

    assert result.exit_code == 0
    assert calls == [db]
    assert "Memory sync: 1 resolved outcome(s), 1 appended, 0 updated." in result.output


def test_queue_commands_add_list_retry_and_clear(db, monkeypatch):
    class SessionContext:
        def __enter__(self):
            return db

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(cli_main, "SessionLocal", lambda: SessionContext())
    monkeypatch.setattr(cli_main, "init_db", lambda: None)

    runner = CliRunner()
    add = runner.invoke(cli_main.cli, ["queue", "add", "AAPL", "--date", "2026-01-02"])
    assert add.exit_code == 0
    assert "Queued AAPL" in add.output

    listed = runner.invoke(cli_main.cli, ["queue", "list"])
    assert listed.exit_code == 0
    assert "AAPL" in listed.output
    assert "queued" in listed.output

    row = db.query(AnalysisQueue).filter_by(ticker="AAPL").one()
    row.status = "failed"
    row.last_error = "provider failed"
    db.commit()

    retry = runner.invoke(cli_main.cli, ["queue", "retry", str(row.id)])
    assert retry.exit_code == 0
    assert "Re-queued job" in retry.output
    db.refresh(row)
    assert row.status == "queued"

    row.status = "completed"
    db.commit()
    clear = runner.invoke(cli_main.cli, ["queue", "clear-completed"])
    assert clear.exit_code == 0
    assert "Cleared 1 completed" in clear.output


def test_queue_run_command_invokes_worker(monkeypatch):
    calls = []

    monkeypatch.setattr(cli_main, "init_db", lambda: None)
    monkeypatch.setattr(
        cli_main,
        "run_queued_jobs",
        lambda **kwargs: (
            calls.append(kwargs)
            or WorkerReport(attempted=2, completed=1, failed=1, skipped=0, reset_stale=0)
        ),
    )

    result = CliRunner().invoke(
        cli_main.cli,
        ["queue", "run", "--limit", "2", "--max-workers", "1"],
    )

    assert result.exit_code == 0
    assert calls[0]["max_jobs"] == 2
    assert calls[0]["max_workers"] == 1
    assert "1 completed, 1 failed" in result.output


def test_analyze_command_marks_failed_on_analyzer_error(db, monkeypatch):
    calls = []

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
    monkeypatch.setattr(
        cli_main,
        "sync_resolved_outcomes_to_memory",
        lambda sync_db, _settings: (
            calls.append(sync_db)
            or MemorySyncReport(resolved_rows=0, appended=0, updated=0, unchanged=0)
        ),
    )

    result = CliRunner().invoke(
        cli_main.cli,
        ["analyze", "MSFT", "--date", "2026-01-08"],
    )

    assert result.exit_code == 1
    row = db.query(Analysis).filter_by(ticker="MSFT").one()
    assert row.status == "failed"
    assert row.error_message == "provider unavailable"
    assert calls == [db]
