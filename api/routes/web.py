"""Web route foundation for M06."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from api import services
from api.deps import DbSession
from core.users import UserResolutionError

router = APIRouter()

SORT_OPTIONS = ("best_alpha", "hit_rate", "most_analyses", "recent", "ticker")
QUEUE_STATUS_OPTIONS = ("queued", "running", "completed", "failed")


@router.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": "stocksage"}


@router.get("/", tags=["research"])
def research_landing(
    db: DbSession,
    sort: str = Query("best_alpha"),
    rating: str | None = Query(None),
    min_results: int = Query(1, ge=1),
) -> dict:
    if sort not in SORT_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported sort option: {sort}")
    return services.research_landing(db, sort=sort, rating=rating, min_results=min_results)


@router.get("/ticker/{ticker}", tags=["research"])
def ticker_intelligence(ticker: str, db: DbSession) -> dict:
    return services.ticker_intelligence(db, ticker)


@router.get("/analysis/{analysis_id}", tags=["research"])
def analysis_report(analysis_id: int, db: DbSession) -> dict:
    report = services.analysis_report(db, analysis_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Analysis report not found.")
    return report


@router.get("/workspace", tags=["workspace"])
def workspace(
    db: DbSession,
    user: str | None = Query(None),
    userid: int | None = Query(None),
) -> dict:
    try:
        return services.workspace(db, username=user, user_id=userid)
    except UserResolutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


@router.get("/queue", tags=["admin"])
def queue_status(
    db: DbSession,
    queue_status: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    if queue_status is not None and queue_status not in QUEUE_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported queue status: {queue_status}")
    return services.queue_status(db, status=queue_status, limit=limit)
