"""Tests for user resolution and request history."""

from datetime import date

import pytest

import core.users as users_module
from core.analysis_runs import prepare_analysis_row
from core.models import Analysis, AnalysisRequest, User
from core.request_history import (
    create_analysis_request,
    list_user_requests,
    update_analysis_request,
)
from core.users import UserResolutionError, resolve_request_user


def test_resolve_request_user_defaults_to_os_username(db, monkeypatch):
    monkeypatch.setattr(users_module.getpass, "getuser", lambda: "localdev")

    user = resolve_request_user(db)

    assert user.username == "localdev"
    assert user.id is not None
    assert user.created_at is not None
    assert user.last_seen_at is not None


def test_resolve_request_user_auto_creates_and_reuses_username(db):
    first = resolve_request_user(db, username="alice")
    second = resolve_request_user(db, username="alice")

    assert first.id == second.id
    assert db.query(User).filter_by(username="alice").count() == 1


def test_resolve_request_user_by_existing_id(db):
    alice = resolve_request_user(db, username="alice")

    found = resolve_request_user(db, user_id=alice.id)

    assert found.username == "alice"


def test_resolve_request_user_rejects_invalid_selection(db):
    with pytest.raises(UserResolutionError, match="either --user or --userid"):
        resolve_request_user(db, username="alice", user_id=1)

    with pytest.raises(UserResolutionError, match="Unknown user id"):
        resolve_request_user(db, user_id=999)

    with pytest.raises(UserResolutionError, match="blank"):
        resolve_request_user(db, username=" ")


def test_shared_analysis_can_have_multiple_user_requests(db, completed_analysis):
    alice = resolve_request_user(db, username="alice")
    bob = resolve_request_user(db, username="bob")

    create_analysis_request(
        db,
        user_id=alice.id,
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        source="cli",
        status="reused",
        analysis_id=completed_analysis.id,
    )
    create_analysis_request(
        db,
        user_id=bob.id,
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        source="cli",
        status="reused",
        analysis_id=completed_analysis.id,
    )

    assert db.query(Analysis).filter_by(ticker="AAPL").count() == 1
    assert db.query(AnalysisRequest).count() == 2
    assert {row.user.username for row in completed_analysis.requests} == {"alice", "bob"}


def test_prepare_analysis_row_records_creator_attribution(db):
    user = resolve_request_user(db, username="alice")

    prep = prepare_analysis_row(
        db,
        "MSFT",
        date(2026, 1, 3),
        force=False,
        requested_by_user_id=user.id,
    )

    assert prep.analysis.created_by_user_id == user.id


def test_update_and_list_user_requests(db, completed_analysis):
    user = resolve_request_user(db, username="alice")
    request = create_analysis_request(
        db,
        user_id=user.id,
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        source="cli",
        status="running",
        analysis_id=completed_analysis.id,
    )

    update_analysis_request(db, request.id, status="completed", analysis_id=completed_analysis.id)
    rows = list_user_requests(db, user_id=user.id, ticker="AAPL", status="completed")

    assert len(rows) == 1
    assert rows[0].completed_at is not None
