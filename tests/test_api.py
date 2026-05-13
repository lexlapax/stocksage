"""Tests for the M06 FastAPI route foundation."""

from datetime import date, datetime

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_db
from core.models import AnalysisQueue, AnalysisRequest, Outcome
from core.users import resolve_request_user


def _client(db) -> TestClient:
    app = create_app()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_health_route(db):
    response = _client(db).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "stocksage"}


def test_research_landing_returns_system_summary(db, completed_analysis):
    db.add(
        Outcome(
            analysis_id=completed_analysis.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=0.05,
            alpha_return=0.02,
            holding_days=5,
            reflection="Useful call.",
        )
    )
    db.commit()

    response = _client(db).get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "StockSage" in response.text
    assert "Research" in response.text
    assert "AAPL" in response.text
    assert "+2.0%" in response.text


def test_ticker_and_analysis_routes(db, completed_analysis):
    db.add(
        Outcome(
            analysis_id=completed_analysis.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=0.05,
            alpha_return=0.02,
            holding_days=5,
            reflection="Useful call.",
        )
    )
    db.commit()

    client = _client(db)
    ticker = client.get("/ticker/AAPL")
    report = client.get(f"/analysis/{completed_analysis.id}")

    assert ticker.status_code == 200
    assert "AAPL intelligence" in ticker.text
    assert "View report" in ticker.text
    assert report.status_code == 200
    assert "AAPL report" in report.text
    assert "Beat market" in report.text
    assert "Market report text." in report.text


def test_workspace_route_is_user_scoped(db, completed_analysis):
    alice = resolve_request_user(db, username="alice")
    bob = resolve_request_user(db, username="bob")
    db.add_all(
        [
            AnalysisRequest(
                user_id=alice.id,
                ticker="AAPL",
                trade_date=completed_analysis.trade_date,
                source="web",
                status="reused",
                requested_at=datetime(2026, 1, 2, 10, 0),
                completed_at=datetime(2026, 1, 2, 10, 0),
                analysis_id=completed_analysis.id,
            ),
            AnalysisRequest(
                user_id=bob.id,
                ticker="MSFT",
                trade_date=date(2026, 1, 3),
                source="web",
                status="queued",
                requested_at=datetime(2026, 1, 3, 10, 0),
            ),
        ]
    )
    db.commit()

    response = _client(db).get("/workspace?user=alice")

    assert response.status_code == 200
    assert "Showing submissions for alice" in response.text
    assert "AAPL" in response.text
    assert "MSFT" not in response.text


def test_submit_analysis_creates_queue_and_request_then_redirects(db):
    response = _client(db).post(
        "/analysis",
        data={"ticker": "msft", "trade_date": "2026-01-03", "user": "alice"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/workspace?user=alice"
    queue_item = db.query(AnalysisQueue).filter_by(ticker="MSFT").one()
    request = db.query(AnalysisRequest).filter_by(ticker="MSFT").one()
    assert queue_item.requested_by_user_id == request.user_id
    assert request.status == "queued"
    assert request.queue_id == queue_item.id


def test_queue_status_route_lists_jobs(db):
    user = resolve_request_user(db, username="alice")
    job = AnalysisQueue(
        ticker="AAPL",
        trade_date=date(2026, 1, 2),
        priority=0,
        queued_at=datetime(2026, 1, 2, 9, 0),
        status="queued",
        requested_by_user_id=user.id,
    )
    db.add(job)
    db.commit()

    response = _client(db).get("/queue")

    assert response.status_code == 200
    assert "Queue status" in response.text
    assert "AAPL" in response.text
    assert "Queued" in response.text
