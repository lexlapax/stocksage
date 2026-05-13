"""Submit analysis requests over shared canonical work."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from core.models import Analysis, AnalysisQueue, AnalysisRequest
from core.queueing import enqueue_analysis
from core.request_history import create_analysis_request


@dataclass(frozen=True)
class SubmissionResult:
    request: AnalysisRequest
    queue_item: AnalysisQueue | None
    analysis: Analysis | None
    created_queue_item: bool
    reason: str


def submit_analysis_request(
    db: Session,
    *,
    user_id: int,
    ticker: str,
    trade_date: date,
    source: str,
    priority: int = 0,
) -> SubmissionResult:
    result = enqueue_analysis(
        db,
        ticker,
        trade_date,
        priority=priority,
        requested_by_user_id=user_id,
    )

    if result.queue_item is not None:
        request = create_analysis_request(
            db,
            user_id=user_id,
            ticker=ticker,
            trade_date=trade_date,
            source=source,
            status=result.queue_item.status,
            analysis_id=result.queue_item.analysis_id,
            queue_id=result.queue_item.id,
        )
        return SubmissionResult(
            request=request,
            queue_item=result.queue_item,
            analysis=result.analysis,
            created_queue_item=result.created,
            reason=result.reason,
        )

    request = create_analysis_request(
        db,
        user_id=user_id,
        ticker=ticker,
        trade_date=trade_date,
        source=source,
        status=_request_status_for_analysis(result.analysis.status),
        analysis_id=result.analysis.id,
        error_message=result.analysis.error_message,
    )
    return SubmissionResult(
        request=request,
        queue_item=None,
        analysis=result.analysis,
        created_queue_item=False,
        reason=result.reason,
    )


def _request_status_for_analysis(status: str) -> str:
    return "reused" if status == "completed" else status
