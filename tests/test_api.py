"""Tests for the M06 FastAPI route foundation."""

from datetime import date, datetime

from fastapi.testclient import TestClient

from api.app import create_app
from api.deps import get_db
from core.models import Analysis, AnalysisQueue, AnalysisRequest, Outcome
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


def test_static_chart_asset_is_served(db):
    response = _client(db).get("/static/charts.js")

    assert response.status_code == 200
    assert "renderSystemAccuracy" in response.text


def test_empty_db_pages_render_clear_states(db):
    client = _client(db)

    research = client.get("/")
    workspace = client.get("/workspace?user=alice")
    queue = client.get("/queue")
    ticker = client.get("/ticker/ZZZZ")

    assert research.status_code == 200
    assert "No resolved analyses yet" in research.text
    assert "system-accuracy-chart" not in research.text
    assert workspace.status_code == 200
    assert "No submissions yet" in workspace.text
    assert queue.status_code == 200
    assert "No queue jobs" in queue.text
    assert ticker.status_code == 200
    assert "No reports for ZZZZ" in ticker.text


def test_missing_analysis_returns_404(db):
    response = _client(db).get("/analysis/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis report not found."


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
    assert "System accuracy over time" in response.text
    assert "system-accuracy-data" in response.text
    assert "https://cdn.jsdelivr.net/npm/chart.js" in response.text


def test_research_landing_supports_rating_filter(db, completed_analysis):
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
    db.add(
        Analysis(
            ticker="MSFT",
            trade_date=date(2026, 1, 3),
            run_at=datetime(2026, 1, 3, 9, 0),
            completed_at=datetime(2026, 1, 3, 9, 5),
            status="completed",
            rating="Overweight",
        )
    )
    db.flush()
    msft = db.query(Analysis).filter_by(ticker="MSFT").one()
    db.add(
        Outcome(
            analysis_id=msft.id,
            resolved_at=datetime(2026, 1, 10),
            raw_return=0.02,
            alpha_return=-0.01,
            holding_days=5,
            reflection="Missed call.",
        )
    )
    db.commit()

    response = _client(db).get("/?rating=Buy&date_range=all")

    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "MSFT" not in response.text


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
    assert "Alpha vs market over time" in ticker.text
    assert "ticker-alpha-chart" in ticker.text
    assert "ticker-alpha-data" in ticker.text
    assert "View report" in ticker.text
    assert report.status_code == 200
    assert "AAPL report" in report.text
    assert "Correct call" in report.text
    assert "Stock return" in report.text
    assert "Market report text." in report.text
    assert "Evidence" in report.text


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
    assert 'hx-trigger="every 5s"' not in response.text
    assert "AAPL" in response.text
    assert "MSFT" not in response.text


def test_workspace_partial_polls_when_user_has_active_work(db, completed_analysis):
    alice = resolve_request_user(db, username="alice")
    db.add(
        AnalysisRequest(
            user_id=alice.id,
            ticker="AAPL",
            trade_date=completed_analysis.trade_date,
            source="web",
            status="queued",
            requested_at=datetime(2026, 1, 2, 10, 0),
            analysis_id=completed_analysis.id,
        )
    )
    db.commit()

    response = _client(db).get("/workspace/partials/submissions?user=alice")

    assert response.status_code == 200
    assert 'hx-trigger="every 5s"' in response.text
    assert "AAPL" in response.text


def test_ticker_page_hides_calibration_until_enough_outcomes(db, completed_analysis):
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

    response = _client(db).get("/ticker/AAPL")

    assert response.status_code == 200
    assert "Not enough data yet" in response.text
    assert "rating-calibration-chart" not in response.text


def test_ticker_page_shows_calibration_chart_with_enough_outcomes(db, completed_analysis):
    for offset, alpha_return, rating in [
        (1, -0.01, "Overweight"),
        (2, 0.04, "Buy"),
    ]:
        row = Analysis(
            ticker="AAPL",
            trade_date=date(2026, 1, 2 + offset),
            run_at=datetime(2026, 1, 2 + offset, 9, 0),
            completed_at=datetime(2026, 1, 2 + offset, 9, 5),
            status="completed",
            rating=rating,
        )
        db.add(row)
        db.flush()
        db.add(
            Outcome(
                analysis_id=row.id,
                resolved_at=datetime(2026, 1, 10 + offset),
                raw_return=alpha_return + 0.01,
                alpha_return=alpha_return,
                holding_days=5,
                reflection="Resolved.",
            )
        )

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

    response = _client(db).get("/ticker/AAPL")

    assert response.status_code == 200
    assert "rating-calibration-chart" in response.text
    assert "rating-calibration-data" in response.text
    assert "Average alpha by rating label" in response.text


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


def test_submit_analysis_reuses_completed_report(db, completed_analysis):
    response = _client(db).post(
        "/analysis",
        data={
            "ticker": "aapl",
            "trade_date": completed_analysis.trade_date.isoformat(),
            "user": "alice",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert db.query(AnalysisQueue).count() == 0
    request = db.query(AnalysisRequest).filter_by(ticker="AAPL").one()
    assert request.status == "reused"
    assert request.analysis_id == completed_analysis.id


def test_reuse_note_reports_existing_analysis(db, completed_analysis):
    response = _client(db).get(
        f"/analysis/reuse-note?ticker=aapl&trade_date={completed_analysis.trade_date.isoformat()}"
    )

    assert response.status_code == 200
    assert "already has an existing AAPL report" in response.text
    assert "note-ready" in response.text


def test_retry_failed_submission_requeues_job(db):
    user = resolve_request_user(db, username="alice")
    job = AnalysisQueue(
        ticker="PLTR",
        trade_date=date(2026, 4, 24),
        priority=0,
        queued_at=datetime(2026, 4, 24, 9, 0),
        status="failed",
        attempts=1,
        completed_at=datetime(2026, 4, 24, 9, 10),
        last_error="Provider quota exceeded.",
        requested_by_user_id=user.id,
    )
    db.add(job)
    db.flush()
    request = AnalysisRequest(
        user_id=user.id,
        ticker="PLTR",
        trade_date=job.trade_date,
        queue_id=job.id,
        source="web",
        status="failed",
        requested_at=datetime(2026, 4, 24, 9, 0),
        completed_at=datetime(2026, 4, 24, 9, 10),
        error_message="Provider quota exceeded.",
    )
    db.add(request)
    db.commit()

    response = _client(db).post(
        f"/workspace/submissions/{request.id}/retry",
        data={"user": "alice"},
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert 'hx-trigger="every 5s"' in response.text
    db.refresh(job)
    db.refresh(request)
    assert job.status == "queued"
    assert job.last_error is None
    assert request.status == "queued"
    assert request.error_message is None


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


def test_queue_partial_polls_and_retry_action_for_active_and_failed_jobs(db):
    user = resolve_request_user(db, username="alice")
    db.add_all(
        [
            AnalysisQueue(
                ticker="AMZN",
                trade_date=date(2026, 5, 1),
                priority=0,
                queued_at=datetime(2026, 5, 1, 9, 0),
                status="queued",
                requested_by_user_id=user.id,
            ),
            AnalysisQueue(
                ticker="PLTR",
                trade_date=date(2026, 4, 24),
                priority=0,
                queued_at=datetime(2026, 4, 24, 9, 0),
                status="failed",
                attempts=1,
                last_error="Provider quota exceeded.",
                requested_by_user_id=user.id,
            ),
        ]
    )
    db.commit()

    response = _client(db).get("/queue/partials/jobs")

    assert response.status_code == 200
    assert 'hx-trigger="every 5s"' in response.text
    assert "AMZN" in response.text
    assert "PLTR" in response.text
    assert 'hx-post="/queue/' in response.text
