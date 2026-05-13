"""Web route foundation for M06."""

import getpass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse

from api import services
from api.deps import DbSession
from api.templates import templates
from core.users import UserResolutionError

router = APIRouter()

SORT_OPTIONS = ("best_alpha", "hit_rate", "most_analyses", "recent", "ticker")
QUEUE_STATUS_OPTIONS = ("queued", "running", "completed", "failed")
DATE_RANGE_OPTIONS = ("30", "90", "180", "all")
REQUEST_STATUS_OPTIONS = ("queued", "running", "completed", "failed", "reused")


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": "stocksage"}


@router.get("/", response_class=HTMLResponse, tags=["research"])
def research_landing(
    request: Request,
    db: DbSession,
    sort: str = Query("best_alpha"),
    rating: str | None = Query(None),
    min_results: int = Query(1, ge=1),
    date_range: str = Query("all"),
):
    view = _research_view(db, sort, rating, min_results, date_range)
    return _template_response(request, "research.html", view, active_nav="research")


@router.get("/research/partials/tickers", response_class=HTMLResponse, tags=["research"])
def research_tickers_partial(
    request: Request,
    db: DbSession,
    sort: str = Query("best_alpha"),
    rating: str | None = Query(None),
    min_results: int = Query(1, ge=1),
    date_range: str = Query("all"),
):
    view = _research_view(db, sort, rating, min_results, date_range)
    return templates.TemplateResponse(
        request=request,
        name="partials/research_tickers.html",
        context={"view": view},
    )


@router.get("/ticker/{ticker}", response_class=HTMLResponse, tags=["research"])
def ticker_intelligence(request: Request, ticker: str, db: DbSession):
    view = services.ticker_intelligence(db, ticker)
    return _template_response(request, "ticker.html", view, active_nav="research")


@router.get("/analysis/reuse-note", response_class=HTMLResponse, tags=["workspace"])
def analysis_reuse_note(
    request: Request,
    db: DbSession,
    ticker: str | None = Query(None),
    trade_date: str | None = Query(None),
):
    try:
        parsed_date = date.fromisoformat(trade_date) if trade_date else date.today()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid analysis date.") from exc
    view = services.analysis_reuse_note(db, ticker=ticker, trade_date=parsed_date)
    return templates.TemplateResponse(
        request=request,
        name="partials/reuse_note.html",
        context={"view": view},
    )


@router.get("/analysis/{analysis_id}", response_class=HTMLResponse, tags=["research"])
def analysis_report(request: Request, analysis_id: int, db: DbSession):
    report = services.analysis_report(db, analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    return _template_response(request, "analysis.html", report, active_nav="research")


@router.get("/workspace", response_class=HTMLResponse, tags=["workspace"])
def workspace(
    request: Request,
    db: DbSession,
    user: str | None = Query(None),
    userid: int | None = Query(None),
    ticker: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    if status_filter is not None and status_filter not in REQUEST_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported request status: {status_filter}")
    try:
        view = services.workspace(
            db,
            username=user,
            user_id=userid,
            ticker=ticker,
            status=status_filter,
        )
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _template_response(
        request,
        "workspace.html",
        view,
        active_nav="workspace",
        current_user=view["user"],
    )


@router.get("/workspace/partials/submissions", response_class=HTMLResponse, tags=["workspace"])
def workspace_submissions_partial(
    request: Request,
    db: DbSession,
    user: str | None = Query(None),
    userid: int | None = Query(None),
    ticker: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
):
    if status_filter is not None and status_filter not in REQUEST_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported request status: {status_filter}")
    try:
        view = services.workspace(
            db,
            username=user,
            user_id=userid,
            ticker=ticker,
            status=status_filter,
        )
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="partials/workspace_submissions.html",
        context={"view": view},
    )


@router.post("/workspace/submissions/{request_id}/retry", tags=["workspace"])
def retry_workspace_submission(
    request: Request,
    db: DbSession,
    request_id: int,
    user: Annotated[str | None, Form()] = None,
    userid: Annotated[int | None, Form()] = None,
    ticker: Annotated[str | None, Form()] = None,
    status_filter: Annotated[str | None, Form(alias="status")] = None,
):
    if status_filter is not None and status_filter not in REQUEST_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported request status: {status_filter}")
    try:
        queue_item = services.retry_submission(
            db,
            request_id=request_id,
            username=user,
            user_id=userid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if queue_item is None:
        raise HTTPException(status_code=404, detail="Submission not found.")

    if _is_htmx(request):
        view = services.workspace(
            db, username=user, user_id=userid, ticker=ticker, status=status_filter
        )
        return templates.TemplateResponse(
            request=request,
            name="partials/workspace_submissions.html",
            context={"view": view},
        )

    workspace_user = user or _current_user_from_request(request)["username"]
    return RedirectResponse(
        url=f"/workspace?user={workspace_user}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/analysis", tags=["workspace"])
def submit_analysis(
    db: DbSession,
    ticker: Annotated[str, Form(min_length=1, max_length=16)],
    trade_date: Annotated[str | None, Form()] = None,
    user: Annotated[str | None, Form()] = None,
    userid: Annotated[int | None, Form()] = None,
) -> RedirectResponse:
    try:
        parsed_date = date.fromisoformat(trade_date) if trade_date else date.today()
        submission = services.submit_new_analysis(
            db,
            ticker=ticker,
            trade_date=parsed_date,
            username=user,
            user_id=userid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    workspace_user = submission.request.user.username
    return RedirectResponse(
        url=f"/workspace?user={workspace_user}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/queue", response_class=HTMLResponse, tags=["admin"])
def queue_status(
    request: Request,
    db: DbSession,
    queue_status: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
):
    if queue_status is not None and queue_status not in QUEUE_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported queue status: {queue_status}")
    view = services.queue_status(db, status=queue_status, limit=limit)
    return _template_response(request, "queue.html", view, active_nav="workspace")


@router.get("/queue/partials/jobs", response_class=HTMLResponse, tags=["admin"])
def queue_jobs_partial(
    request: Request,
    db: DbSession,
    queue_status: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
):
    if queue_status is not None and queue_status not in QUEUE_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported queue status: {queue_status}")
    view = services.queue_status(db, status=queue_status, limit=limit)
    return templates.TemplateResponse(
        request=request,
        name="partials/queue_jobs.html",
        context={"view": view},
    )


@router.post("/queue/{queue_id}/retry", tags=["admin"])
def retry_queue_job(
    request: Request,
    db: DbSession,
    queue_id: int,
):
    try:
        queue_item = services.retry_queue_job(db, queue_id=queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if queue_item is None:
        raise HTTPException(status_code=404, detail="Queue job not found.")

    if _is_htmx(request):
        view = services.queue_status(db)
        return templates.TemplateResponse(
            request=request,
            name="partials/queue_jobs.html",
            context={"view": view},
        )

    return RedirectResponse(url="/queue", status_code=status.HTTP_303_SEE_OTHER)


def _template_response(
    request: Request,
    template_name: str,
    view: dict,
    *,
    active_nav: str,
    current_user: dict | None = None,
):
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "view": view,
            "active_nav": active_nav,
            "current_user": current_user or _current_user_from_request(request),
            "today": date.today().isoformat(),
        },
    )


def _current_user_from_request(request: Request) -> dict:
    username = request.query_params.get("user") or getpass.getuser()
    return {"id": request.query_params.get("userid"), "username": username}


def _is_htmx(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


def _research_view(
    db: DbSession,
    sort: str,
    rating: str | None,
    min_results: int,
    date_range: str,
) -> dict:
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported sort option: {sort}")
    if date_range not in DATE_RANGE_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported date range: {date_range}")
    return services.research_landing(
        db,
        sort=sort,
        rating=rating,
        min_results=min_results,
        date_range=date_range,
    )
