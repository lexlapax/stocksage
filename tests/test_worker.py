"""Tests for queue worker behavior."""

from datetime import date
from types import SimpleNamespace

from core.analyzer import AnalysisResult
from core.models import Analysis, AnalysisQueue
from core.queueing import enqueue_analysis, retry_queue_item
from worker.runner import run_queued_jobs


class SessionContext:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self.db

    def __exit__(self, *_args):
        return False


def _session_factory(db):
    return lambda: SessionContext(db)


def _cfg(tmp_path):
    return SimpleNamespace(
        llm_provider="test",
        deep_think_llm="deep-test",
        quick_think_llm="quick-test",
        memory_log_path=tmp_path / "memory.md",
    )


class SuccessfulAnalyzer:
    def __init__(self, **_kwargs):
        pass

    def run(self, ticker, trade_date):
        return AnalysisResult(
            ticker=ticker,
            trade_date=trade_date,
            rating="Overweight",
            executive_summary=f"{ticker} summary",
            investment_thesis=f"{ticker} thesis",
            price_target=None,
            time_horizon="5 days",
            market_report="market",
            sentiment_report="sentiment",
            news_report="news",
            fundamentals_report="fundamentals",
            bull_history="bull",
            bear_history="bear",
            research_decision="research",
            trader_plan="trader",
            risk_aggressive="aggressive",
            risk_conservative="conservative",
            risk_neutral="neutral",
            risk_decision="risk",
            decision_text="decision",
            full_state={"final_trade_decision": "decision"},
        )


class FailingAnalyzer:
    def __init__(self, **_kwargs):
        pass

    def run(self, *_args):
        raise RuntimeError("provider failed")


def test_worker_processes_queued_job(db, tmp_path):
    job = enqueue_analysis(db, "AAPL", date(2026, 1, 2)).queue_item

    report = run_queued_jobs(
        max_jobs=1,
        session_factory=_session_factory(db),
        cfg=_cfg(tmp_path),
        analyzer_factory=SuccessfulAnalyzer,
    )

    db.refresh(job)
    analysis = db.query(Analysis).filter_by(ticker="AAPL").one()
    assert report.completed == 1
    assert job.status == "completed"
    assert job.analysis_id == analysis.id
    assert analysis.status == "completed"
    assert analysis.detail is not None


def test_worker_marks_failed_job_and_retry_reuses_analysis(db, tmp_path):
    job = enqueue_analysis(db, "PLTR", date(2026, 1, 2)).queue_item

    failed = run_queued_jobs(
        max_jobs=1,
        session_factory=_session_factory(db),
        cfg=_cfg(tmp_path),
        analyzer_factory=FailingAnalyzer,
    )

    db.refresh(job)
    failed_analysis = db.query(Analysis).filter_by(ticker="PLTR").one()
    assert failed.failed == 1
    assert job.status == "failed"
    assert job.analysis_id == failed_analysis.id
    assert failed_analysis.status == "failed"
    assert "provider failed" in job.last_error

    retry_queue_item(db, job.id)
    retried = run_queued_jobs(
        max_jobs=1,
        session_factory=_session_factory(db),
        cfg=_cfg(tmp_path),
        analyzer_factory=SuccessfulAnalyzer,
    )

    db.refresh(job)
    assert retried.completed == 1
    assert job.status == "completed"
    assert db.query(Analysis).filter_by(ticker="PLTR").count() == 1
    assert db.get(Analysis, failed_analysis.id).status == "completed"


def test_worker_marks_queue_completed_when_analysis_already_exists(
    db, completed_analysis, tmp_path
):
    job = AnalysisQueue(
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        priority=0,
        queued_at=completed_analysis.run_at,
        status="queued",
    )
    db.add(job)
    db.commit()

    report = run_queued_jobs(
        max_jobs=1,
        session_factory=_session_factory(db),
        cfg=_cfg(tmp_path),
        analyzer_factory=FailingAnalyzer,
    )

    db.refresh(job)
    assert report.attempted == 0
    assert report.skipped == 1
    assert job.status == "completed"
    assert job.analysis_id == completed_analysis.id
