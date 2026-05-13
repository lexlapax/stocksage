"""Tests for the browser-triggered queue runner loop."""

from core.queue_runs import create_queue_run, request_queue_run_stop
from tests.test_worker import SessionContext
from worker.runner import JobRunResult
from worker.web_runner import _run_queue_run


def _session_factory(db):
    return lambda: SessionContext(db)


def test_web_runner_finishes_after_requested_limit(db):
    run = create_queue_run(db, requested_limit=1).queue_run

    _run_queue_run(
        run.id,
        _session_factory(db),
        lambda **_kwargs: JobRunResult(status="completed", queue_id=1),
    )

    db.refresh(run)
    assert run.status == "finished"
    assert run.attempted == 1
    assert run.completed == 1


def test_web_runner_honors_stop_before_next_job(db):
    run = create_queue_run(db, requested_limit=None).queue_run
    request_queue_run_stop(db, run.id)

    _run_queue_run(
        run.id,
        _session_factory(db),
        lambda **_kwargs: JobRunResult(status="failed", error="should not run"),
    )

    db.refresh(run)
    assert run.status == "stopped"
    assert run.attempted == 0
