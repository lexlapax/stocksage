"""Tests for persisted queue runner lifecycle state."""

from core.queue_runs import (
    create_queue_run,
    finish_queue_run,
    record_queue_run_result,
    request_queue_run_stop,
)
from core.users import resolve_request_user
from worker.runner import JobRunResult


def test_create_queue_run_prevents_duplicate_active_run(db):
    user = resolve_request_user(db, username="alice")

    created = create_queue_run(db, requested_limit=5, started_by_user_id=user.id)
    duplicate = create_queue_run(db, requested_limit=1, started_by_user_id=user.id)

    assert created.created is True
    assert created.queue_run.status == "queued"
    assert created.queue_run.requested_limit == 5
    assert duplicate.created is False
    assert duplicate.reason == "active"
    assert duplicate.queue_run.id == created.queue_run.id


def test_request_queue_run_stop_marks_active_run_stopping(db):
    run = create_queue_run(db, requested_limit=None).queue_run

    stopped = request_queue_run_stop(db, run.id)

    assert stopped.status == "stopping"
    assert stopped.stop_requested_at is not None


def test_record_queue_run_result_updates_counts(db):
    run = create_queue_run(db, requested_limit=2).queue_run

    record_queue_run_result(db, run.id, JobRunResult(status="completed", queue_id=1))
    updated = record_queue_run_result(
        db,
        run.id,
        JobRunResult(status="failed", queue_id=2, error="provider failed"),
    )

    assert updated.attempted == 2
    assert updated.completed == 1
    assert updated.failed == 1
    assert updated.last_error == "provider failed"


def test_finish_queue_run_closes_active_run(db):
    run = create_queue_run(db, requested_limit=1).queue_run

    finished = finish_queue_run(db, run.id)

    assert finished.status == "finished"
    assert finished.completed_at is not None
