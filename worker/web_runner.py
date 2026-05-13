"""In-process web queue runner controls."""

from collections.abc import Callable
from threading import Lock, Thread

from sqlalchemy.orm import Session

from core.db import SessionLocal
from core.models import QueueRun
from core.queue_runs import (
    fail_queue_run,
    finish_queue_run,
    mark_queue_run_running,
    queue_run_stop_requested,
    record_queue_run_result,
)
from worker.runner import JobRunResult, process_next_job

ProcessFunc = Callable[..., JobRunResult]
SessionFactory = Callable[[], Session]

_LOCK = Lock()
_ACTIVE_THREADS: dict[int, Thread] = {}


def start_queue_run(
    run_id: int,
    *,
    session_factory: SessionFactory = SessionLocal,
    process_func: ProcessFunc = process_next_job,
) -> bool:
    with _LOCK:
        thread = _ACTIVE_THREADS.get(run_id)
        if thread is not None and thread.is_alive():
            return False

        thread = Thread(
            target=_run_queue_run,
            args=(run_id, session_factory, process_func),
            name=f"stocksage-queue-run-{run_id}",
            daemon=True,
        )
        _ACTIVE_THREADS[run_id] = thread
        thread.start()
        return True


def is_queue_run_thread_active(run_id: int) -> bool:
    with _LOCK:
        thread = _ACTIVE_THREADS.get(run_id)
        return bool(thread and thread.is_alive())


def _run_queue_run(
    run_id: int,
    session_factory: SessionFactory,
    process_func: ProcessFunc,
) -> None:
    try:
        with session_factory() as db:
            run = db.get(QueueRun, run_id)
            if run is None:
                return
            mark_queue_run_running(db, run_id)

        while True:
            with session_factory() as db:
                run = db.get(QueueRun, run_id)
                if run is None:
                    return
                if queue_run_stop_requested(db, run_id):
                    finish_queue_run(db, run_id, status="stopped")
                    return
                if run.requested_limit is not None and run.attempted >= run.requested_limit:
                    finish_queue_run(db, run_id, status="finished")
                    return

            result = process_func(session_factory=session_factory)

            with session_factory() as db:
                record_queue_run_result(db, run_id, result)
                if result.status == "skipped":
                    finish_queue_run(db, run_id, status="finished")
                    return
    except Exception as exc:
        with session_factory() as db:
            fail_queue_run(db, run_id, str(exc))
    finally:
        with _LOCK:
            _ACTIVE_THREADS.pop(run_id, None)
