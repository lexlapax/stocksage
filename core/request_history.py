"""Request history over shared canonical analyses."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from core.models import AnalysisRequest

TERMINAL_REQUEST_STATUSES = {"completed", "failed", "reused"}
OPEN_REQUEST_STATUSES = {"queued", "running"}


def create_analysis_request(
    db: Session,
    *,
    user_id: int,
    ticker: str,
    trade_date: date,
    source: str,
    status: str,
    analysis_id: int | None = None,
    queue_id: int | None = None,
    error_message: str | None = None,
) -> AnalysisRequest:
    now = datetime.now(UTC)
    row = AnalysisRequest(
        user_id=user_id,
        ticker=ticker.upper(),
        trade_date=trade_date,
        analysis_id=analysis_id,
        queue_id=queue_id,
        source=source,
        status=status,
        requested_at=now,
        completed_at=now if status in TERMINAL_REQUEST_STATUSES else None,
        error_message=error_message,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_analysis_request(
    db: Session,
    request_id: int,
    *,
    status: str,
    analysis_id: int | None = None,
    queue_id: int | None = None,
    error_message: str | None = None,
) -> AnalysisRequest:
    row = db.get(AnalysisRequest, request_id)
    row.status = status
    if analysis_id is not None:
        row.analysis_id = analysis_id
    if queue_id is not None:
        row.queue_id = queue_id
    row.error_message = error_message
    row.completed_at = datetime.now(UTC) if status in TERMINAL_REQUEST_STATUSES else None
    db.commit()
    db.refresh(row)
    return row


def mark_queue_requests_running(db: Session, queue_id: int) -> int:
    rows = _open_queue_requests(db, queue_id)
    for row in rows:
        row.status = "running"
    db.commit()
    return len(rows)


def requeue_requests(db: Session, queue_id: int) -> int:
    rows = (
        db.query(AnalysisRequest)
        .filter(AnalysisRequest.queue_id == queue_id, AnalysisRequest.status == "failed")
        .all()
    )
    for row in rows:
        row.status = "queued"
        row.completed_at = None
        row.error_message = None
    db.commit()
    return len(rows)


def complete_queue_requests(db: Session, queue_id: int, analysis_id: int) -> int:
    rows = _open_queue_requests(db, queue_id)
    now = datetime.now(UTC)
    for row in rows:
        row.status = "completed"
        row.analysis_id = analysis_id
        row.completed_at = now
        row.error_message = None
    db.commit()
    return len(rows)


def fail_queue_requests(
    db: Session,
    queue_id: int,
    analysis_id: int | None,
    error_message: str,
) -> int:
    rows = _open_queue_requests(db, queue_id)
    now = datetime.now(UTC)
    for row in rows:
        row.status = "failed"
        row.analysis_id = analysis_id
        row.completed_at = now
        row.error_message = error_message
    db.commit()
    return len(rows)


def list_user_requests(
    db: Session,
    *,
    user_id: int,
    ticker: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[AnalysisRequest]:
    query = db.query(AnalysisRequest).filter(AnalysisRequest.user_id == user_id)
    if ticker:
        query = query.filter(AnalysisRequest.ticker == ticker.upper())
    if status:
        query = query.filter(AnalysisRequest.status == status)
    return (
        query.order_by(AnalysisRequest.requested_at.desc(), AnalysisRequest.id.desc())
        .limit(limit)
        .all()
    )


def _open_queue_requests(db: Session, queue_id: int) -> list[AnalysisRequest]:
    return (
        db.query(AnalysisRequest)
        .filter(
            AnalysisRequest.queue_id == queue_id,
            AnalysisRequest.status.in_(OPEN_REQUEST_STATUSES),
        )
        .all()
    )
