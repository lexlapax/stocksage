"""Queue operations for background analysis jobs."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from core.models import Analysis, AnalysisQueue

QUEUE_STATUSES = ("queued", "running", "completed", "failed")
ACTIVE_QUEUE_STATUSES = ("queued", "running")


@dataclass(frozen=True)
class EnqueueResult:
    queue_item: AnalysisQueue | None
    created: bool
    reason: str
    analysis: Analysis | None = None


def enqueue_analysis(
    db: Session,
    ticker: str,
    trade_date: date,
    priority: int = 0,
) -> EnqueueResult:
    ticker = ticker.upper()
    existing_analysis = _analysis_for(db, ticker, trade_date)
    if existing_analysis and existing_analysis.status == "completed":
        return EnqueueResult(None, False, "analysis_completed", analysis=existing_analysis)
    if existing_analysis and existing_analysis.status == "running":
        return EnqueueResult(None, False, "analysis_running", analysis=existing_analysis)

    active = (
        db.query(AnalysisQueue)
        .filter(
            AnalysisQueue.ticker == ticker,
            AnalysisQueue.trade_date == trade_date,
            AnalysisQueue.status.in_(ACTIVE_QUEUE_STATUSES),
        )
        .order_by(AnalysisQueue.id.desc())
        .first()
    )
    if active:
        if priority > active.priority:
            active.priority = priority
            db.commit()
            db.refresh(active)
        return EnqueueResult(active, False, active.status)

    row = AnalysisQueue(
        ticker=ticker,
        trade_date=trade_date,
        priority=priority,
        queued_at=datetime.now(UTC),
        status="queued",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return EnqueueResult(row, True, "queued")


def list_queue_items(
    db: Session,
    status: str | None = None,
    limit: int = 50,
) -> list[AnalysisQueue]:
    query = db.query(AnalysisQueue).order_by(
        AnalysisQueue.status.asc(),
        AnalysisQueue.priority.desc(),
        AnalysisQueue.queued_at.asc(),
        AnalysisQueue.id.asc(),
    )
    if status:
        query = query.filter(AnalysisQueue.status == status)
    return query.limit(limit).all()


def retry_queue_item(db: Session, queue_id: int) -> AnalysisQueue | None:
    row = db.get(AnalysisQueue, queue_id)
    if row is None:
        return None
    _requeue(row)
    db.commit()
    db.refresh(row)
    return row


def retry_failed_queue_items(db: Session) -> int:
    rows = db.query(AnalysisQueue).filter(AnalysisQueue.status == "failed").all()
    for row in rows:
        _requeue(row)
    db.commit()
    return len(rows)


def clear_completed_queue_items(db: Session) -> int:
    rows = db.query(AnalysisQueue).filter(AnalysisQueue.status == "completed").all()
    count = len(rows)
    for row in rows:
        db.delete(row)
    db.commit()
    return count


def reset_stale_running_jobs(db: Session, stale_before: datetime) -> int:
    rows = (
        db.query(AnalysisQueue)
        .filter(
            AnalysisQueue.status == "running",
            AnalysisQueue.started_at.is_not(None),
            AnalysisQueue.started_at < stale_before,
        )
        .all()
    )
    for row in rows:
        row.status = "queued"
        row.started_at = None
        row.last_error = "Reset stale running job after worker interruption."
    db.commit()
    return len(rows)


def claim_next_queue_item(db: Session) -> AnalysisQueue | None:
    rows = (
        db.query(AnalysisQueue)
        .filter(AnalysisQueue.status == "queued")
        .order_by(
            AnalysisQueue.priority.desc(), AnalysisQueue.queued_at.asc(), AnalysisQueue.id.asc()
        )
        .all()
    )
    now = datetime.now(UTC)
    for row in rows:
        existing = _analysis_for(db, row.ticker, row.trade_date)
        if existing and existing.status == "completed":
            row.status = "completed"
            row.analysis_id = existing.id
            row.completed_at = now
            db.commit()
            continue
        row.status = "running"
        row.started_at = now
        row.completed_at = None
        row.attempts += 1
        row.last_error = None
        db.commit()
        db.refresh(row)
        return row
    return None


def complete_queue_item(db: Session, queue_id: int, analysis_id: int) -> AnalysisQueue:
    row = db.get(AnalysisQueue, queue_id)
    row.status = "completed"
    row.analysis_id = analysis_id
    row.completed_at = datetime.now(UTC)
    row.last_error = None
    db.commit()
    db.refresh(row)
    return row


def fail_queue_item(
    db: Session, queue_id: int, analysis_id: int | None, error: str
) -> AnalysisQueue:
    row = db.get(AnalysisQueue, queue_id)
    row.status = "failed"
    row.analysis_id = analysis_id
    row.completed_at = datetime.now(UTC)
    row.last_error = error
    db.commit()
    db.refresh(row)
    return row


def _analysis_for(db: Session, ticker: str, trade_date: date) -> Analysis | None:
    return (
        db.query(Analysis)
        .filter(Analysis.ticker == ticker.upper(), Analysis.trade_date == trade_date)
        .first()
    )


def _requeue(row: AnalysisQueue) -> None:
    row.status = "queued"
    row.queued_at = datetime.now(UTC)
    row.started_at = None
    row.completed_at = None
    row.last_error = None
