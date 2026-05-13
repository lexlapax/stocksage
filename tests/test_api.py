"""Tests for the M06 FastAPI route foundation."""

from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from api import services
from api.app import create_app
from api.deps import get_db
from core.models import Analysis, AnalysisQueue, AnalysisRequest, Outcome, QueueRun
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


def test_openapi_reports_package_version(db):
    response = _client(db).get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["version"] == "0.0.2"


def test_static_chart_asset_is_served(db):
    response = _client(db).get("/static/charts.js")

    assert response.status_code == 200
    assert "renderSystemAccuracy" in response.text


def test_static_app_asset_is_served(db):
    response = _client(db).get("/static/app.js")

    assert response.status_code == 200
    assert "prefillAnalysisForm" in response.text


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
    assert 'id="research-tickers"' in response.text
    assert 'hx-get="/research/partials/tickers"' in response.text
    assert 'hx-target="#research-tickers"' in response.text
    assert "System accuracy over time" in response.text
    assert "system-accuracy-data" in response.text
    assert "https://cdn.jsdelivr.net/npm/chart.js" in response.text
    assert 'aria-label="Help: Rolling 30-day hit rate"' in response.text
    assert 'data-analysis-ticker="AAPL"' in response.text
    assert "Analyze again" in response.text


def test_research_tickers_partial_supports_filtered_updates(db, completed_analysis):
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
    msft = Analysis(
        ticker="MSFT",
        trade_date=date(2026, 1, 3),
        run_at=datetime(2026, 1, 3, 9, 0),
        completed_at=datetime(2026, 1, 3, 9, 5),
        status="completed",
        rating="Overweight",
    )
    db.add(msft)
    db.flush()
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

    response = _client(db).get("/research/partials/tickers?rating=Buy&date_range=all")

    assert response.status_code == 200
    assert 'id="research-tickers"' in response.text
    assert "Analyzed stocks" in response.text
    assert "AAPL" in response.text
    assert "MSFT" not in response.text
    assert "<!doctype html>" not in response.text


def test_research_landing_shows_completed_analysis_before_outcome(db, completed_analysis):
    response = _client(db).get("/")

    assert response.status_code == 200
    assert "AAPL" in response.text
    assert "Pending" in response.text
    assert "system-accuracy-chart" not in response.text


def test_research_most_analyses_sort_uses_total_completed_reports(db):
    today = date.today()
    rows = [
        Analysis(
            ticker="AAPL",
            trade_date=today - timedelta(days=idx),
            run_at=datetime.combine(today - timedelta(days=idx), datetime.min.time()),
            completed_at=datetime.combine(today - timedelta(days=idx), datetime.min.time()),
            status="completed",
            rating="Buy",
        )
        for idx in range(2)
    ]
    resolved = Analysis(
        ticker="MSFT",
        trade_date=today,
        run_at=datetime.combine(today, datetime.min.time()),
        completed_at=datetime.combine(today, datetime.min.time()),
        status="completed",
        rating="Buy",
    )
    db.add_all([*rows, resolved])
    db.flush()
    db.add(
        Outcome(
            analysis_id=resolved.id,
            resolved_at=datetime.combine(today, datetime.min.time()),
            raw_return=0.03,
            alpha_return=0.01,
            holding_days=5,
            reflection="Resolved.",
        )
    )
    db.commit()

    response = _client(db).get("/?sort=most_analyses")

    assert response.status_code == 200
    assert response.text.index("/ticker/AAPL") < response.text.index("/ticker/MSFT")


def test_ticker_summary_pending_when_no_outcomes(db, completed_analysis):
    response = _client(db).get("/ticker/AAPL")

    assert response.status_code == 200
    assert "Results checked" in response.text
    assert "Pending" in response.text
    assert "No resolved outcomes yet" in response.text


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


def test_research_landing_respects_date_range_filter(db):
    today = date.today()
    recent = Analysis(
        ticker="AAPL",
        trade_date=today - timedelta(days=10),
        run_at=datetime.combine(today - timedelta(days=10), datetime.min.time()),
        completed_at=datetime.combine(today - timedelta(days=10), datetime.min.time()),
        status="completed",
        rating="Buy",
    )
    old = Analysis(
        ticker="MSFT",
        trade_date=today - timedelta(days=120),
        run_at=datetime.combine(today - timedelta(days=120), datetime.min.time()),
        completed_at=datetime.combine(today - timedelta(days=120), datetime.min.time()),
        status="completed",
        rating="Buy",
    )
    db.add_all([recent, old])
    db.flush()
    db.add_all(
        [
            Outcome(
                analysis_id=recent.id,
                resolved_at=datetime.combine(today, datetime.min.time()),
                raw_return=0.05,
                alpha_return=0.02,
                holding_days=5,
                reflection="Recent.",
            ),
            Outcome(
                analysis_id=old.id,
                resolved_at=datetime.combine(today, datetime.min.time()),
                raw_return=0.03,
                alpha_return=0.01,
                holding_days=5,
                reflection="Old.",
            ),
        ]
    )
    db.commit()

    response = _client(db).get("/?date_range=30")

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
    assert 'aria-label="Help: Positive alpha"' in ticker.text
    assert 'data-analysis-ticker="AAPL"' in ticker.text
    assert "View report" in ticker.text
    assert report.status_code == 200
    assert "AAPL report" in report.text
    assert "Correct call" in report.text
    assert "Stock return" in report.text
    assert 'aria-label="Help: Raw return"' in report.text
    assert "Market report text." in report.text
    assert "Evidence" in report.text


def test_analysis_report_uses_accessible_evidence_tabs(db, completed_analysis):
    response = _client(db).get(f"/analysis/{completed_analysis.id}")

    market_start = response.text.index('id="evidence-market-panel"')
    news_start = response.text.index('id="evidence-news-panel"')
    market_opening_tag = response.text[market_start : response.text.index(">", market_start)]
    news_opening_tag = response.text[news_start : response.text.index(">", news_start)]

    assert response.status_code == 200
    assert 'role="tablist"' in response.text
    assert 'id="evidence-market-tab"' in response.text
    assert 'aria-selected="true"' in response.text
    assert 'aria-controls="evidence-market-panel"' in response.text
    assert 'role="tabpanel"' in response.text
    assert "hidden" not in market_opening_tag
    assert "hidden" in news_opening_tag


def test_analysis_report_without_detail_renders_placeholders(db):
    row = Analysis(
        ticker="PLTR",
        trade_date=date(2026, 4, 24),
        run_at=datetime(2026, 4, 24, 9, 0),
        completed_at=datetime(2026, 4, 24, 9, 5),
        status="completed",
        rating="Underweight",
        executive_summary="Thin report.",
        investment_thesis="Stored without evidence details.",
    )
    db.add(row)
    db.commit()

    response = _client(db).get(f"/analysis/{row.id}")

    assert response.status_code == 200
    assert "PLTR report" in response.text
    assert "Thin report." in response.text
    assert "No evidence stored." in response.text


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
    assert "Queue Status" in response.text
    assert "alice ▾" not in response.text
    assert '<span class="user-pill">alice</span>' in response.text
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
    assert "Run next 1" in response.text
    assert "Live LLM run" in response.text


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


def test_queue_runner_controls_create_and_stop_run(db, monkeypatch):
    monkeypatch.setattr(services.web_runner, "start_queue_run", lambda run_id: True)
    monkeypatch.setattr(services.web_runner, "is_queue_run_thread_active", lambda run_id: True)
    user = resolve_request_user(db, username="alice")
    db.add(
        AnalysisQueue(
            ticker="AAPL",
            trade_date=date(2026, 1, 2),
            priority=0,
            queued_at=datetime(2026, 1, 2, 9, 0),
            status="queued",
            requested_by_user_id=user.id,
        )
    )
    db.commit()
    client = _client(db)

    started = client.post(
        "/queue/run",
        data={"limit": "1", "user": "alice"},
        headers={"HX-Request": "true"},
    )
    duplicate = client.post(
        "/queue/run",
        data={"limit": "5", "user": "alice"},
        headers={"HX-Request": "true"},
    )
    stopped = client.post("/queue/run/stop", headers={"HX-Request": "true"})

    assert started.status_code == 200
    assert "Stop after current job" in started.text
    assert duplicate.status_code == 200
    assert db.query(QueueRun).count() == 1
    run = db.query(QueueRun).one()
    assert run.requested_limit == 1
    assert run.started_by.username == "alice"
    assert stopped.status_code == 200
    assert "Stopping" in stopped.text
    db.refresh(run)
    assert run.status == "stopping"


def test_queue_runner_marks_missing_running_thread_blocked(db):
    user = resolve_request_user(db, username="alice")
    db.add(
        QueueRun(
            status="running",
            requested_limit=1,
            max_workers=1,
            started_by_user_id=user.id,
            started_at=datetime(2026, 1, 2, 9, 0),
            heartbeat_at=datetime(2026, 1, 2, 9, 0),
            attempted=0,
            completed=0,
            failed=0,
            skipped=0,
        )
    )
    db.commit()

    response = _client(db).get("/queue")

    assert response.status_code == 200
    assert "Needs attention" in response.text
    assert "web queue runner is no longer active" in response.text
