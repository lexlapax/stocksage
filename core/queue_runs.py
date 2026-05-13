"""Persisted queue runner lifecycle helpers."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.orm import Session

from core.models import QueueRun

QUEUE_RUN_STATUSES = ("queued", "running", "stopping", "stopped", "finished", "failed", "blocked")
ACTIVE_QUEUE_RUN_STATUSES = ("queued", "running", "stopping")


class JobResultLike(Protocol):
    status: str
    error: str | None


@dataclass(frozen=True)
class QueueRunStartResult:
    queue_run: QueueRun
    created: bool
    reason: str


def create_queue_run(
    db: Session,
    *,
    requested_limit: int | None,
    max_workers: int = 1,
    started_by_user_id: int | None = None,
) -> QueueRunStartResult:
    if requested_limit is not None and requested_limit < 1:
        raise ValueError("Queue run limit must be at least 1.")
    if max_workers < 1:
        raise ValueError("Queue run workers must be at least 1.")

    active = get_active_queue_run(db)
    if active is not None:
        return QueueRunStartResult(active, created=False, reason="active")

    now = datetime.now(UTC)
    row = QueueRun(
        status="queued",
        requested_limit=requested_limit,
        max_workers=max_workers,
        started_by_user_id=started_by_user_id,
        started_at=now,
        heartbeat_at=now,
        attempted=0,
        completed=0,
        failed=0,
        skipped=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return QueueRunStartResult(row, created=True, reason="created")


def get_active_queue_run(db: Session) -> QueueRun | None:
    return (
        db.query(QueueRun)
        .filter(QueueRun.status.in_(ACTIVE_QUEUE_RUN_STATUSES))
        .order_by(QueueRun.started_at.desc(), QueueRun.id.desc())
        .first()
    )


def get_latest_queue_run(db: Session) -> QueueRun | None:
    return db.query(QueueRun).order_by(QueueRun.started_at.desc(), QueueRun.id.desc()).first()


def mark_queue_run_running(db: Session, run_id: int) -> QueueRun:
    row = _get_queue_run(db, run_id)
    if row.status == "queued":
        row.status = "running"
    row.heartbeat_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


def request_queue_run_stop(db: Session, run_id: int | None = None) -> QueueRun | None:
    row = _get_queue_run(db, run_id) if run_id is not None else get_active_queue_run(db)
    if row is None:
        return None
    if row.status in ACTIVE_QUEUE_RUN_STATUSES:
        row.status = "stopping"
        row.stop_requested_at = datetime.now(UTC)
        row.heartbeat_at = row.stop_requested_at
        db.commit()
        db.refresh(row)
    return row


def queue_run_stop_requested(db: Session, run_id: int) -> bool:
    row = _get_queue_run(db, run_id)
    return row.status == "stopping" or row.stop_requested_at is not None


def record_queue_run_result(db: Session, run_id: int, result: JobResultLike) -> QueueRun:
    row = _get_queue_run(db, run_id)
    row.heartbeat_at = datetime.now(UTC)
    if result.status == "completed":
        row.attempted += 1
        row.completed += 1
    elif result.status == "failed":
        row.attempted += 1
        row.failed += 1
        row.last_error = result.error
    elif result.status == "skipped":
        row.skipped += 1
    db.commit()
    db.refresh(row)
    return row


def finish_queue_run(db: Session, run_id: int, *, status: str = "finished") -> QueueRun:
    if status not in {"finished", "stopped", "blocked"}:
        raise ValueError(f"Unsupported queue run finish status: {status}")
    row = _get_queue_run(db, run_id)
    row.status = status
    row.completed_at = datetime.now(UTC)
    row.heartbeat_at = row.completed_at
    db.commit()
    db.refresh(row)
    return row


def fail_queue_run(db: Session, run_id: int, error: str) -> QueueRun:
    row = _get_queue_run(db, run_id)
    now = datetime.now(UTC)
    row.status = "failed"
    row.completed_at = now
    row.heartbeat_at = now
    row.last_error = error
    db.commit()
    db.refresh(row)
    return row


def block_queue_run(db: Session, run_id: int, error: str) -> QueueRun:
    row = _get_queue_run(db, run_id)
    now = datetime.now(UTC)
    row.status = "blocked"
    row.completed_at = now
    row.heartbeat_at = now
    row.last_error = error
    db.commit()
    db.refresh(row)
    return row


def _get_queue_run(db: Session, run_id: int) -> QueueRun:
    row = db.get(QueueRun, run_id)
    if row is None:
        raise ValueError(f"Queue run {run_id} was not found.")
    return row
