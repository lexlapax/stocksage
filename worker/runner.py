"""Queue worker for StockSage analyses."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from config import Settings
from config import settings as _default_settings
from core.analysis_runs import mark_analysis_failed, persist_analysis_result, prepare_analysis_row
from core.analyzer import Analyzer
from core.db import SessionLocal
from core.memory_sync import sync_resolved_outcomes_to_memory
from core.queueing import claim_next_queue_item, complete_queue_item, fail_queue_item
from core.queueing import reset_stale_running_jobs as reset_stale_jobs


@dataclass(frozen=True)
class JobSpec:
    queue_id: int
    ticker: str
    trade_date: date


@dataclass(frozen=True)
class JobRunResult:
    status: str
    queue_id: int | None = None
    analysis_id: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class WorkerReport:
    attempted: int
    completed: int
    failed: int
    skipped: int
    reset_stale: int = 0


def run_queued_jobs(
    max_jobs: int | None = None,
    max_workers: int = 1,
    *,
    session_factory: Callable[[], Session] = SessionLocal,
    cfg: Settings = _default_settings,
    analyzer_factory: Callable[..., Analyzer] = Analyzer,
    debug: bool = False,
    reset_stale_minutes: int | None = 120,
) -> WorkerReport:
    reset_count = 0
    if reset_stale_minutes is not None:
        stale_before = datetime.now(UTC) - timedelta(minutes=reset_stale_minutes)
        with session_factory() as db:
            reset_count = reset_stale_jobs(db, stale_before)

    limit = max_jobs if max_jobs is not None else _queued_count(session_factory)
    if limit <= 0:
        return WorkerReport(attempted=0, completed=0, failed=0, skipped=0, reset_stale=reset_count)

    if max_workers <= 1:
        results = []
        for _ in range(limit):
            result = process_next_job(session_factory, cfg, analyzer_factory, debug)
            results.append(result)
            if result.status == "skipped":
                break
    else:
        specs = []
        for _ in range(limit):
            spec = _claim_next_job(session_factory)
            if spec is None:
                break
            specs.append(spec)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(
                    _process_claimed_job,
                    spec,
                    session_factory,
                    cfg,
                    analyzer_factory,
                    debug,
                )
                for spec in specs
            ]
            results = [future.result() for future in as_completed(futures)]
        if not specs:
            results.append(JobRunResult(status="skipped"))

    attempted = sum(1 for result in results if result.status in {"completed", "failed"})
    completed = sum(1 for result in results if result.status == "completed")
    failed = sum(1 for result in results if result.status == "failed")
    skipped = sum(1 for result in results if result.status == "skipped")
    return WorkerReport(
        attempted=attempted,
        completed=completed,
        failed=failed,
        skipped=skipped,
        reset_stale=reset_count,
    )


def process_next_job(
    session_factory: Callable[[], Session] = SessionLocal,
    cfg: Settings = _default_settings,
    analyzer_factory: Callable[..., Analyzer] = Analyzer,
    debug: bool = False,
) -> JobRunResult:
    spec = _claim_next_job(session_factory)
    if spec is None:
        return JobRunResult(status="skipped")
    return _process_claimed_job(spec, session_factory, cfg, analyzer_factory, debug)


def _claim_next_job(session_factory: Callable[[], Session]) -> JobSpec | None:
    with session_factory() as db:
        job = claim_next_queue_item(db)
        if job is None:
            return None
        return JobSpec(queue_id=job.id, ticker=job.ticker, trade_date=job.trade_date)


def _process_claimed_job(
    spec: JobSpec,
    session_factory: Callable[[], Session],
    cfg: Settings,
    analyzer_factory: Callable[..., Analyzer],
    debug: bool,
) -> JobRunResult:
    analysis_id = None
    try:
        with session_factory() as db:
            prep = prepare_analysis_row(db, spec.ticker, spec.trade_date, force=True, cfg=cfg)
            analysis_id = prep.analysis.id
            sync_resolved_outcomes_to_memory(db, cfg)

        analyzer = analyzer_factory(cfg=cfg, debug=debug)
        result = analyzer.run(spec.ticker, spec.trade_date)

        with session_factory() as db:
            persist_analysis_result(db, analysis_id, result)
            complete_queue_item(db, spec.queue_id, analysis_id)
        return JobRunResult(status="completed", queue_id=spec.queue_id, analysis_id=analysis_id)
    except Exception as exc:
        message = str(exc)
        with session_factory() as db:
            if analysis_id is not None:
                mark_analysis_failed(db, analysis_id, message)
            fail_queue_item(db, spec.queue_id, analysis_id, message)
        return JobRunResult(
            status="failed",
            queue_id=spec.queue_id,
            analysis_id=analysis_id,
            error=message,
        )


def _queued_count(session_factory: Callable[[], Session]) -> int:
    from core.models import AnalysisQueue

    with session_factory() as db:
        return db.query(AnalysisQueue).filter(AnalysisQueue.status == "queued").count()
