"""Tests for ORM models and DB session factory."""

from datetime import date, datetime

import pytest
from sqlalchemy.exc import IntegrityError

from core.models import Analysis, AnalysisDetail, AnalysisQueue, AnalysisRequest, Outcome, User


def test_analysis_persists(db):
    row = Analysis(
        ticker="TSLA",
        trade_date=date(2026, 3, 1),
        run_at=datetime(2026, 3, 1, 10, 0),
        status="completed",
        rating="Hold",
    )
    db.add(row)
    db.commit()
    fetched = db.query(Analysis).filter_by(ticker="TSLA").first()
    assert fetched is not None
    assert fetched.rating == "Hold"


def test_unique_ticker_date_constraint(db, completed_analysis):
    duplicate = Analysis(
        ticker="AAPL",
        trade_date=date(2026, 1, 2),
        run_at=datetime(2026, 1, 2, 10, 0),
        status="running",
    )
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.commit()


def test_cascade_delete_detail(db, completed_analysis):
    analysis_id = completed_analysis.id
    db.delete(completed_analysis)
    db.commit()
    assert db.query(AnalysisDetail).filter_by(analysis_id=analysis_id).first() is None


def test_outcome_relationship(db, completed_analysis):
    outcome = Outcome(
        analysis_id=completed_analysis.id,
        resolved_at=datetime(2026, 1, 10),
        raw_return=0.032,
        alpha_return=0.011,
        holding_days=5,
        reflection="Directionally correct.",
    )
    db.add(outcome)
    db.commit()
    db.refresh(completed_analysis)
    assert completed_analysis.outcome is not None
    assert completed_analysis.outcome.raw_return == pytest.approx(0.032)


def test_analysis_detail_relationship(db, completed_analysis):
    db.refresh(completed_analysis)
    assert completed_analysis.detail is not None
    assert completed_analysis.detail.market_report == "Market report text."


def test_analysis_queue(db):
    entry = AnalysisQueue(
        ticker="MSFT",
        trade_date=date(2026, 4, 1),
        priority=1,
        queued_at=datetime(2026, 4, 1, 8, 0),
    )
    db.add(entry)
    db.commit()
    fetched = db.query(AnalysisQueue).filter_by(ticker="MSFT").first()
    assert fetched.priority == 1
    assert fetched.status == "queued"
    assert fetched.attempts == 0
    assert fetched.last_error is None


def test_user_request_relationships(db, completed_analysis):
    user = User(
        username="alice",
        created_at=datetime(2026, 4, 1, 8, 0),
        last_seen_at=datetime(2026, 4, 1, 8, 0),
    )
    queue_item = AnalysisQueue(
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        priority=1,
        queued_at=datetime(2026, 4, 1, 8, 0),
        requested_by=user,
    )
    request = AnalysisRequest(
        user=user,
        ticker="AAPL",
        trade_date=completed_analysis.trade_date,
        analysis=completed_analysis,
        queue_item=queue_item,
        source="test",
        status="queued",
        requested_at=datetime(2026, 4, 1, 8, 1),
    )
    db.add(request)
    db.commit()

    fetched = db.query(AnalysisRequest).filter_by(ticker="AAPL").one()
    assert fetched.user.username == "alice"
    assert fetched.analysis.id == completed_analysis.id
    assert fetched.queue_item.requested_by.username == "alice"
