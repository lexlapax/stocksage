"""Web route foundation for M06."""

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
):
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported sort option: {sort}")
    view = services.research_landing(db, sort=sort, rating=rating, min_results=min_results)
    return _template_response(request, "research.html", view, active_nav="research")


@router.get("/ticker/{ticker}", response_class=HTMLResponse, tags=["research"])
def ticker_intelligence(request: Request, ticker: str, db: DbSession):
    view = services.ticker_intelligence(db, ticker)
    return _template_response(request, "ticker.html", view, active_nav="research")


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
):
    try:
        view = services.workspace(db, username=user, user_id=userid)
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _template_response(
        request,
        "workspace.html",
        view,
        active_nav="workspace",
        current_user=view["user"],
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
        },
    )


def _current_user_from_request(request: Request) -> dict:
    username = request.query_params.get("user") or "Local user"
    return {"id": request.query_params.get("userid"), "username": username}
