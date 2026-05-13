"""View data assembly for the web routes."""

from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import mean

from sqlalchemy.orm import Session

from core.models import Analysis, AnalysisQueue, AnalysisRequest, Outcome
from core.queueing import list_queue_items, retry_queue_item
from core.request_history import list_user_requests
from core.submissions import SubmissionResult, submit_analysis_request
from core.trends import (
    TickerStats,
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
    date_range: str = "all",
) -> dict:
    summary_rows = _filtered_completed_rows(db, rating=None, date_range="all")
    summary_ticker_rows = _research_ticker_rows(summary_rows)
    resolved_summary_ticker_rows = [
        item for item in summary_ticker_rows if item["resolved_count"] > 0
    ]
    resolved_summary_rows = [row for row in summary_rows if row.outcome is not None]

    table_rows = _filtered_completed_rows(db, rating=rating, date_range=date_range)
    ticker_rows = _research_ticker_rows(table_rows)
    ticker_rows = [item for item in ticker_rows if item["total_analyses"] >= min_results]
    ticker_rows = _sort_research_rows(ticker_rows, sort)
    running = (
        db.query(AnalysisQueue).filter(AnalysisQueue.status.in_(("queued", "running"))).count()
    )
    return {
        "page": "Research",
        "summary": {
            "stocks_analyzed": len(summary_ticker_rows),
            "resolved_stocks": len(resolved_summary_ticker_rows),
            "avg_hit_rate": _average([item["hit_rate"] for item in resolved_summary_ticker_rows]),
            "avg_alpha_return": _average(
                [item["avg_alpha_return"] for item in resolved_summary_ticker_rows]
            ),
            "running": running,
        },
        "sort": sort,
        "filters": {"rating": rating, "min_results": min_results, "date_range": date_range},
        "accuracy_chart": _rolling_accuracy_chart(resolved_summary_rows),
        "tickers": ticker_rows,
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
        "alpha_bars": _alpha_bars(rows),
        "alpha_chart": _alpha_chart(rows),
        "rating_calibration": _rating_calibration(rows),
        "rating_chart": _rating_chart(rows),
        "show_rating_calibration": len([row for row in rows if row.outcome is not None]) >= 3,
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


def analysis_reuse_note(db: Session, *, ticker: str | None, trade_date: date) -> dict:
    if not ticker or not ticker.strip():
        return {
            "kind": "idle",
            "message": "Enter a ticker and date to check for existing reports.",
        }

    normalized_ticker = ticker.upper().strip()
    analysis = _analysis_for(db, normalized_ticker, trade_date)
    if analysis and analysis.status == "completed":
        return {
            "kind": "ready",
            "message": (
                f"StockSage already has an existing {normalized_ticker} report for "
                f"{trade_date.isoformat()}. Your submission will link to it."
            ),
        }
    if analysis and analysis.status == "running":
        return {
            "kind": "running",
            "message": (
                f"{normalized_ticker} is already being analyzed for {trade_date.isoformat()}. "
                "Your submission will follow the same work."
            ),
        }

    active = _active_queue_for(db, normalized_ticker, trade_date)
    if active:
        return {
            "kind": active.status,
            "message": (
                f"{normalized_ticker} is already {active.status} for {trade_date.isoformat()}. "
                "Your submission will follow the same work."
            ),
        }

    return {
        "kind": "new",
        "message": f"StockSage will queue a new {normalized_ticker} analysis.",
    }


def workspace(
    db: Session,
    *,
    username: str | None = None,
    user_id: int | None = None,
    ticker: str | None = None,
    status: str | None = None,
) -> dict:
    user = resolve_request_user(db, username=username, user_id=user_id)
    requests = list_user_requests(db, user_id=user.id, ticker=ticker, status=status, limit=100)
    has_active_work = any(row.status in {"queued", "running"} for row in requests)
    return {
        "page": "My Workspace",
        "user": {"id": user.id, "username": user.username},
        "has_active_work": has_active_work,
        "filters": {"ticker": ticker, "status": status},
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


def retry_submission(
    db: Session,
    *,
    request_id: int,
    username: str | None = None,
    user_id: int | None = None,
) -> AnalysisQueue | None:
    user = resolve_request_user(db, username=username, user_id=user_id)
    request = db.get(AnalysisRequest, request_id)
    if request is None or request.user_id != user.id:
        return None
    if request.status != "failed":
        raise ValueError("Only failed submissions can be retried.")
    if request.queue_id is None:
        raise ValueError("Only queued submissions can be retried from the web UI.")
    queue_item = db.get(AnalysisQueue, request.queue_id)
    if queue_item is None:
        return None
    if queue_item.status != "failed":
        raise ValueError("Only failed queue jobs can be retried.")
    return retry_queue_item(db, queue_item.id)


def retry_queue_job(db: Session, *, queue_id: int) -> AnalysisQueue | None:
    queue_item = db.get(AnalysisQueue, queue_id)
    if queue_item is None:
        return None
    if queue_item.status != "failed":
        raise ValueError("Only failed queue jobs can be retried.")
    return retry_queue_item(db, queue_item.id)


def queue_status(db: Session, *, status: str | None = None, limit: int = 100) -> dict:
    rows = list_queue_items(db, status=status, limit=limit)
    return {
        "page": "Queue Status",
        "admin_only": True,
        "status": status,
        "has_active_work": any(row.status in {"queued", "running"} for row in rows),
        "last_refreshed": datetime.now(UTC).strftime("%H:%M:%S"),
        "jobs": [_queue_row(row) for row in rows],
    }


def _filtered_completed_rows(
    db: Session,
    *,
    rating: str | None,
    date_range: str,
) -> list[Analysis]:
    query = db.query(Analysis).filter(Analysis.status == "completed")
    if rating:
        query = query.filter(Analysis.rating == rating)
    start = _date_range_start(date_range)
    if start is not None:
        query = query.filter(Analysis.trade_date >= start)
    return query.order_by(Analysis.trade_date.asc(), Analysis.id.asc()).all()


def _research_ticker_rows(rows: list[Analysis]) -> list[dict]:
    by_ticker: dict[str, list[Analysis]] = defaultdict(list)
    for row in rows:
        by_ticker[row.ticker].append(row)

    ticker_rows = []
    for ticker, ticker_analyses in by_ticker.items():
        latest = max(ticker_analyses, key=lambda item: (item.trade_date, item.id))
        resolved = [row for row in ticker_analyses if row.outcome is not None]
        flags = [
            is_correct_alpha_direction(row.rating or "", row.outcome.alpha_return)
            for row in resolved
        ]
        ticker_rows.append(
            {
                "ticker": ticker,
                "total_analyses": len(ticker_analyses),
                "resolved_count": len(resolved),
                "hit_rate": _average_bools(flags) if resolved else None,
                "avg_alpha_return": (
                    _average([row.outcome.alpha_return for row in resolved]) if resolved else None
                ),
                "last_rating": latest.rating,
                "last_analyzed": latest.trade_date.isoformat(),
                "trend": [
                    {
                        "date": row.trade_date.isoformat(),
                        "alpha_return": row.outcome.alpha_return,
                        "correct_call": is_correct_alpha_direction(
                            row.rating or "", row.outcome.alpha_return
                        ),
                    }
                    for row in resolved[-6:]
                ],
            }
        )
    return ticker_rows


def _sort_research_rows(rows: list[dict], sort: str) -> list[dict]:
    sorters = {
        "best_alpha": lambda item: (
            _sortable_metric(item["avg_alpha_return"]),
            _sortable_metric(item["hit_rate"]),
        ),
        "hit_rate": lambda item: (_sortable_metric(item["hit_rate"]), item["resolved_count"]),
        "most_analyses": lambda item: (item["total_analyses"], item["resolved_count"]),
        "recent": lambda item: (item["last_analyzed"], item["ticker"]),
        "ticker": lambda item: item["ticker"],
    }
    key = sorters.get(sort, sorters["best_alpha"])
    return sorted(rows, key=key, reverse=sort != "ticker")


def _rolling_accuracy_chart(rows: list[Analysis]) -> list[dict]:
    sorted_rows = sorted(rows, key=lambda row: (row.trade_date, row.id))
    dates = sorted({row.trade_date for row in sorted_rows})
    points = []
    for point_date in dates:
        start = point_date - timedelta(days=30)
        window = [row for row in sorted_rows if start <= row.trade_date <= point_date]
        flags = [
            is_correct_alpha_direction(row.rating or "", row.outcome.alpha_return) for row in window
        ]
        points.append(
            {
                "date": point_date.isoformat(),
                "hit_rate": round(_average_bools(flags) * 100, 1),
                "resolved": len(window),
            }
        )
    return points


def _ticker_row(item: TickerStats) -> dict:
    return {
        "ticker": item.ticker,
        "total_analyses": item.total_analyses,
        "resolved_count": item.resolved_count,
        "hit_rate": item.alpha_directional_accuracy,
        "avg_alpha_return": item.avg_alpha_return,
        "last_rating": _best_rating(item),
        "trend": [
            {"date": trend_date.isoformat(), "correct_call": correct_call}
            for trend_date, correct_call in item.accuracy_trend[-6:]
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
        "outcome_label": _outcome_label(row),
    }


def _outcome_row(outcome: Outcome | None, rating: str | None) -> dict | None:
    if outcome is None:
        return None
    correct_call = is_correct_alpha_direction(rating or "", outcome.alpha_return)
    spy_return = outcome.raw_return - outcome.alpha_return
    return {
        "raw_return": outcome.raw_return,
        "spy_return": spy_return,
        "alpha_return": outcome.alpha_return,
        "beat_market": correct_call,
        "correct_call": correct_call,
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
        "requested_by": row.requested_by.username if row.requested_by else None,
        "attempts": row.attempts,
        "analysis_id": row.analysis_id,
        "queued_at": row.queued_at.isoformat(),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "last_error": row.last_error,
    }


def _alpha_bars(rows: list[Analysis]) -> list[dict]:
    resolved = [row for row in rows if row.outcome is not None]
    max_abs = max([abs(row.outcome.alpha_return) for row in resolved], default=0.0)
    scale = max(max_abs, 0.01)
    return [
        {
            "date": row.trade_date.isoformat(),
            "alpha_return": row.outcome.alpha_return,
            "height_pct": max(8, round(abs(row.outcome.alpha_return) / scale * 100)),
            "direction": "positive" if row.outcome.alpha_return >= 0 else "negative",
        }
        for row in resolved
    ]


def _alpha_chart(rows: list[Analysis]) -> list[dict]:
    resolved = sorted(
        [row for row in rows if row.outcome is not None],
        key=lambda row: (row.trade_date, row.id),
    )
    return [
        {
            "date": row.trade_date.isoformat(),
            "alpha_return": round(row.outcome.alpha_return * 100, 2),
        }
        for row in resolved
    ]


def _rating_calibration(rows: list[Analysis]) -> list[dict]:
    by_rating: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.outcome is not None and row.rating:
            by_rating[row.rating].append(row.outcome.alpha_return)
    averages = {rating: _average(values) for rating, values in by_rating.items() if values}
    max_abs = max([abs(value) for value in averages.values()], default=0.0)
    scale = max(max_abs, 0.01)
    return [
        {
            "rating": rating,
            "avg_alpha_return": averages[rating],
            "width_pct": max(8, round(abs(averages[rating]) / scale * 100)),
            "direction": "positive" if averages[rating] >= 0 else "negative",
        }
        for rating in sorted(averages)
    ]


def _rating_chart(rows: list[Analysis]) -> list[dict]:
    return [
        {
            "rating": row["rating"],
            "avg_alpha_return": round(row["avg_alpha_return"] * 100, 2),
        }
        for row in _rating_calibration(rows)
    ]


def _outcome_label(row: Analysis) -> str:
    if row.status in {"queued", "running", "failed"}:
        return row.status.title()
    if row.outcome is None:
        return "Pending"
    if is_correct_alpha_direction(row.rating or "", row.outcome.alpha_return):
        return "Correct call"
    return "Missed call"


def _best_rating(item: TickerStats) -> str | None:
    if not item.rating_counts:
        return None
    return max(item.rating_counts, key=item.rating_counts.get)


def _average(values) -> float:
    values = [value for value in values if value is not None]
    return mean(values) if values else 0.0


def _average_bools(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _date_range_start(value: str) -> date | None:
    days = {"30": 30, "90": 90, "180": 180}.get(value)
    if days is None:
        return None
    return date.today() - timedelta(days=days)


def _sortable_metric(value: float | None) -> float:
    return value if value is not None else float("-inf")


def _analysis_for(db: Session, ticker: str, trade_date: date) -> Analysis | None:
    return db.query(Analysis).filter_by(ticker=ticker.upper(), trade_date=trade_date).first()


def _active_queue_for(db: Session, ticker: str, trade_date: date) -> AnalysisQueue | None:
    return (
        db.query(AnalysisQueue)
        .filter(
            AnalysisQueue.ticker == ticker.upper(),
            AnalysisQueue.trade_date == trade_date,
            AnalysisQueue.status.in_(("queued", "running")),
        )
        .order_by(AnalysisQueue.id.desc())
        .first()
    )
