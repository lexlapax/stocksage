"""Tests for analysis queue operations."""

from datetime import UTC, date, datetime, timedelta

from core.models import AnalysisQueue
from core.queueing import (
    clear_completed_queue_items,
    enqueue_analysis,
    list_queue_items,
    reset_stale_running_jobs,
    retry_failed_queue_items,
    retry_queue_item,
)
from core.request_history import create_analysis_request
from core.users import resolve_request_user


def test_enqueue_analysis_creates_queue_item(db):
    user = resolve_request_user(db, username="alice")

    result = enqueue_analysis(
        db,
        "aapl",
        date(2026, 1, 2),
        priority=2,
        requested_by_user_id=user.id,
    )

    assert result.created is True
    assert result.queue_item.ticker == "AAPL"
    assert result.queue_item.status == "queued"
    assert result.queue_item.priority == 2
    assert result.queue_item.requested_by_user_id == user.id


def test_enqueue_analysis_reuses_active_job_and_boosts_priority(db):
    first = enqueue_analysis(db, "AAPL", date(2026, 1, 2), priority=1)
    second = enqueue_analysis(db, "aapl", date(2026, 1, 2), priority=5)

    assert second.created is False
    assert second.queue_item.id == first.queue_item.id
    assert second.queue_item.priority == 5
    assert db.query(AnalysisQueue).count() == 1


def test_enqueue_analysis_skips_completed_analysis(db, completed_analysis):
    result = enqueue_analysis(db, "AAPL", date(2026, 1, 2))

    assert result.created is False
    assert result.reason == "analysis_completed"
    assert result.analysis.id == completed_analysis.id
    assert db.query(AnalysisQueue).count() == 0


def test_retry_and_clear_queue_items(db):
    failed = enqueue_analysis(db, "PLTR", date(2026, 1, 2)).queue_item
    done = enqueue_analysis(db, "MSFT", date(2026, 1, 3)).queue_item
    failed.status = "failed"
    failed.last_error = "rate limited"
    done.status = "completed"
    db.commit()

    row = retry_queue_item(db, failed.id)
    failed_count = retry_failed_queue_items(db)
    cleared = clear_completed_queue_items(db)

    assert row.status == "queued"
    assert row.last_error is None
    assert failed_count == 0
    assert cleared == 1
    assert db.get(AnalysisQueue, done.id) is None


def test_reset_stale_running_jobs(db):
    row = enqueue_analysis(db, "NVDA", date(2026, 1, 2)).queue_item
    row.status = "running"
    row.started_at = datetime.now(UTC) - timedelta(hours=3)
    db.commit()

    reset = reset_stale_running_jobs(db, datetime.now(UTC) - timedelta(hours=2))

    db.refresh(row)
    assert reset == 1
    assert row.status == "queued"
    assert row.started_at is None
    assert "stale" in row.last_error


def test_list_queue_items_can_filter_by_requesting_user(db):
    alice = resolve_request_user(db, username="alice")
    bob = resolve_request_user(db, username="bob")
    shared = enqueue_analysis(db, "AAPL", date(2026, 1, 2), requested_by_user_id=alice.id)
    create_analysis_request(
        db,
        user_id=bob.id,
        ticker="AAPL",
        trade_date=date(2026, 1, 2),
        source="cli_queue",
        status="queued",
        queue_id=shared.queue_item.id,
    )
    enqueue_analysis(db, "MSFT", date(2026, 1, 2), requested_by_user_id=bob.id)

    rows = list_queue_items(db, requested_by_user_id=alice.id)
    bob_rows = list_queue_items(db, requested_by_user_id=bob.id)

    assert [row.ticker for row in rows] == ["AAPL"]
    assert {row.ticker for row in bob_rows} == {"AAPL", "MSFT"}


def test_retry_reopens_failed_request_history(db):
    user = resolve_request_user(db, username="alice")
    job = enqueue_analysis(db, "PLTR", date(2026, 1, 2), requested_by_user_id=user.id).queue_item
    request = create_analysis_request(
        db,
        user_id=user.id,
        ticker="PLTR",
        trade_date=date(2026, 1, 2),
        source="cli_queue",
        status="queued",
        queue_id=job.id,
    )
    job.status = "failed"
    request.status = "failed"
    request.error_message = "rate limited"
    db.commit()

    retry_queue_item(db, job.id)

    db.refresh(request)
    assert request.status == "queued"
    assert request.completed_at is None
    assert request.error_message is None
