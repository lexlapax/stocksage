"""View data assembly for the web routes."""

from datetime import date
from statistics import mean

from sqlalchemy.orm import Session

from core.models import Analysis, AnalysisQueue, Outcome
from core.queueing import list_queue_items
from core.request_history import list_user_requests
from core.submissions import SubmissionResult, submit_analysis_request
from core.trends import (
    TickerStats,
    get_all_ticker_stats,
    get_ticker_stats,
    is_correct_alpha_direction,
)
from core.users import resolve_request_user


def research_landing(
    db: Session,
    *,
    sort: str = "best_alpha",
    rating: str | None = None,
    min_results: int = 1,
) -> dict:
    stats = get_all_ticker_stats(db)
    if rating:
        stats = [item for item in stats if rating in item.rating_counts]
    stats = [item for item in stats if item.resolved_count >= min_results]
    stats = _sort_ticker_stats(stats, sort)
    running = (
        db.query(AnalysisQueue).filter(AnalysisQueue.status.in_(("queued", "running"))).count()
    )
    return {
        "page": "Research",
        "summary": {
            "stocks_analyzed": len(stats),
            "avg_hit_rate": _average([item.alpha_directional_accuracy for item in stats]),
            "avg_alpha_return": _average([item.avg_alpha_return for item in stats]),
            "running": running,
        },
        "sort": sort,
        "filters": {"rating": rating, "min_results": min_results},
        "tickers": [_ticker_row(item) for item in stats],
    }


def ticker_intelligence(db: Session, ticker: str) -> dict:
    ticker = ticker.upper()
    stats = get_ticker_stats(db, ticker)
    rows = (
        db.query(Analysis)
        .filter(Analysis.ticker == ticker)
        .order_by(Analysis.trade_date.desc(), Analysis.id.desc())
        .all()
    )
    return {
        "page": "Ticker Intelligence",
        "ticker": ticker,
        "summary": _ticker_row(stats) if stats else None,
        "history": [_analysis_row(row) for row in rows],
    }


def analysis_report(db: Session, analysis_id: int) -> dict | None:
    row = db.get(Analysis, analysis_id)
    if row is None:
        return None

    detail = row.detail
    return {
        "page": "Analysis Report",
        "analysis": _analysis_row(row),
        "summary": row.executive_summary,
        "investment_thesis": row.investment_thesis,
        "outcome": _outcome_row(row.outcome, row.rating),
        "evidence": {
            "market": detail.market_report if detail else None,
            "news": detail.news_report if detail else None,
            "sentiment": detail.sentiment_report if detail else None,
            "fundamentals": detail.fundamentals_report if detail else None,
            "debate": detail.research_decision if detail else None,
            "risk": detail.risk_decision if detail else None,
        },
    }


def workspace(
    db: Session,
    *,
    username: str | None = None,
    user_id: int | None = None,
) -> dict:
    user = resolve_request_user(db, username=username, user_id=user_id)
    requests = list_user_requests(db, user_id=user.id, limit=100)
    has_active_work = any(row.status in {"queued", "running"} for row in requests)
    return {
        "page": "My Workspace",
        "user": {"id": user.id, "username": user.username},
        "has_active_work": has_active_work,
        "submissions": [_request_row(row) for row in requests],
    }


def submit_new_analysis(
    db: Session,
    *,
    ticker: str,
    trade_date: date,
    username: str | None = None,
    user_id: int | None = None,
) -> SubmissionResult:
    user = resolve_request_user(db, username=username, user_id=user_id)
    return submit_analysis_request(
        db,
        user_id=user.id,
        ticker=ticker,
        trade_date=trade_date,
        source="web",
    )


def queue_status(db: Session, *, status: str | None = None, limit: int = 100) -> dict:
    rows = list_queue_items(db, status=status, limit=limit)
    return {
        "page": "Queue Status",
        "admin_only": True,
        "status": status,
        "jobs": [_queue_row(row) for row in rows],
    }


def _sort_ticker_stats(stats: list[TickerStats], sort: str) -> list[TickerStats]:
    sorters = {
        "best_alpha": lambda item: (item.avg_alpha_return, item.alpha_directional_accuracy),
        "hit_rate": lambda item: (item.alpha_directional_accuracy, item.resolved_count),
        "most_analyses": lambda item: (item.resolved_count, item.total_analyses),
        "recent": lambda item: (_latest_analysis_date(item), item.ticker),
        "ticker": lambda item: item.ticker,
    }
    key = sorters.get(sort, sorters["best_alpha"])
    reverse = sort != "ticker"
    return sorted(stats, key=key, reverse=reverse)


def _ticker_row(item: TickerStats) -> dict:
    return {
        "ticker": item.ticker,
        "total_analyses": item.total_analyses,
        "resolved_count": item.resolved_count,
        "hit_rate": item.alpha_directional_accuracy,
        "avg_alpha_return": item.avg_alpha_return,
        "last_rating": _best_rating(item),
        "trend": [
            {"date": trend_date.isoformat(), "beat_market": beat_market}
            for trend_date, beat_market in item.accuracy_trend[-6:]
        ],
    }


def _analysis_row(row: Analysis) -> dict:
    outcome = row.outcome
    return {
        "id": row.id,
        "ticker": row.ticker,
        "trade_date": row.trade_date.isoformat(),
        "status": row.status,
        "rating": row.rating,
        "price_target": row.price_target,
        "time_horizon": row.time_horizon,
        "outcome": _outcome_row(outcome, row.rating),
    }


def _outcome_row(outcome: Outcome | None, rating: str | None) -> dict | None:
    if outcome is None:
        return None
    spy_return = outcome.raw_return - outcome.alpha_return
    return {
        "raw_return": outcome.raw_return,
        "spy_return": spy_return,
        "alpha_return": outcome.alpha_return,
        "beat_market": is_correct_alpha_direction(rating or "", outcome.alpha_return),
        "holding_days": outcome.holding_days,
        "resolved_at": outcome.resolved_at.isoformat(),
    }


def _request_row(row) -> dict:
    return {
        "id": row.id,
        "ticker": row.ticker,
        "trade_date": row.trade_date.isoformat(),
        "status": row.status,
        "analysis_id": row.analysis_id,
        "queue_id": row.queue_id,
        "source": row.source,
        "requested_at": row.requested_at.isoformat(),
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "error_message": row.error_message,
    }


def _queue_row(row: AnalysisQueue) -> dict:
    return {
        "id": row.id,
        "ticker": row.ticker,
        "trade_date": row.trade_date.isoformat(),
        "status": row.status,
        "requested_by_user_id": row.requested_by_user_id,
        "attempts": row.attempts,
        "analysis_id": row.analysis_id,
        "queued_at": row.queued_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "last_error": row.last_error,
    }


def _latest_analysis_date(item: TickerStats) -> date:
    if item.accuracy_trend:
        return item.accuracy_trend[-1][0]
    return date.min


def _best_rating(item: TickerStats) -> str | None:
    if not item.rating_counts:
        return None
    return max(item.rating_counts, key=item.rating_counts.get)


def _average(values) -> float:
    values = list(values)
    return mean(values) if values else 0.0
