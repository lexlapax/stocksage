"""Trend and accuracy analytics."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean

from sqlalchemy.orm import Session

from core.models import Analysis, Outcome


@dataclass
class TickerStats:
    ticker: str
    total_analyses: int
    resolved_count: int
    directional_accuracy: float
    avg_raw_return: float
    avg_alpha_return: float
    avg_return_by_rating: dict[str, float]
    accuracy_trend: list[tuple[date, bool]]
    rating_counts: dict[str, int] = field(default_factory=dict)
    accuracy_by_rating: dict[str, float] = field(default_factory=dict)


@dataclass
class ModelStats:
    llm_provider: str
    deep_model: str
    total_analyses: int
    resolved_count: int
    avg_alpha_return: float
    directional_accuracy: float


def is_correct_direction(rating: str, raw_return: float) -> bool:
    rating = (rating or "").strip().lower()
    if rating in {"buy", "overweight"}:
        return raw_return > 0
    if rating in {"sell", "underweight"}:
        return raw_return < 0
    if rating == "hold":
        return abs(raw_return) < 0.02
    return False


def get_ticker_stats(db: Session, ticker: str) -> TickerStats | None:
    ticker = ticker.upper()
    total = (
        db.query(Analysis).filter(Analysis.ticker == ticker, Analysis.status == "completed").count()
    )
    if total == 0:
        return None

    rows = _resolved_analyses(db, ticker=ticker)
    flags = _correct_flags(rows)
    by_rating: dict[str, list[float]] = defaultdict(list)
    flags_by_rating: dict[str, list[bool]] = defaultdict(list)

    for row in rows:
        rating = row.rating or "Unknown"
        by_rating[rating].append(row.outcome.raw_return)
        flags_by_rating[rating].append(is_correct_direction(rating, row.outcome.raw_return))

    return TickerStats(
        ticker=ticker,
        total_analyses=total,
        resolved_count=len(rows),
        directional_accuracy=_average_bools(flags),
        avg_raw_return=_average([row.outcome.raw_return for row in rows]),
        avg_alpha_return=_average([row.outcome.alpha_return for row in rows]),
        avg_return_by_rating={rating: mean(values) for rating, values in by_rating.items()},
        accuracy_trend=[(row.trade_date, flag) for row, flag in zip(rows, flags, strict=False)],
        rating_counts={rating: len(values) for rating, values in by_rating.items()},
        accuracy_by_rating={
            rating: _average_bools(values) for rating, values in flags_by_rating.items()
        },
    )


def get_all_ticker_stats(db: Session) -> list[TickerStats]:
    tickers = (
        db.query(Analysis.ticker)
        .join(Outcome)
        .filter(Analysis.status == "completed")
        .distinct()
        .order_by(Analysis.ticker.asc())
        .all()
    )
    stats = [get_ticker_stats(db, ticker) for (ticker,) in tickers]
    return [item for item in stats if item is not None]


def get_model_stats(db: Session) -> list[ModelStats]:
    total_counts: dict[tuple[str, str], int] = defaultdict(int)
    resolved_rows: dict[tuple[str, str], list[Analysis]] = defaultdict(list)

    completed = db.query(Analysis).filter(Analysis.status == "completed").all()
    for row in completed:
        total_counts[_model_key(row)] += 1

    for row in _resolved_analyses(db):
        resolved_rows[_model_key(row)].append(row)

    stats = []
    for key in sorted(total_counts):
        provider, model = key
        rows = resolved_rows.get(key, [])
        stats.append(
            ModelStats(
                llm_provider=provider,
                deep_model=model,
                total_analyses=total_counts[key],
                resolved_count=len(rows),
                avg_alpha_return=_average([row.outcome.alpha_return for row in rows]),
                directional_accuracy=_average_bools(_correct_flags(rows)),
            )
        )
    return stats


def get_accuracy_trend(
    db: Session,
    ticker: str,
    window: int = 10,
) -> list[tuple[date, float]]:
    rows = _resolved_analyses(db, ticker=ticker.upper())
    flags = _correct_flags(rows)
    if not rows:
        return []

    size = max(1, window)
    trend = []
    for idx, row in enumerate(rows):
        start = max(0, idx - size + 1)
        trend.append((row.trade_date, _average_bools(flags[start : idx + 1])))
    return trend


def get_cross_ticker_lessons(db: Session, n: int = 5) -> str:
    rows = (
        db.query(Analysis)
        .join(Outcome)
        .filter(Analysis.status == "completed")
        .order_by(Analysis.trade_date.desc(), Analysis.id.desc())
        .limit(n)
        .all()
    )
    if not rows:
        return "No resolved StockSage outcomes yet."

    lines = ["Recent StockSage outcome lessons:"]
    for row in rows:
        outcome = row.outcome
        correct = (
            "correct" if is_correct_direction(row.rating or "", outcome.raw_return) else "missed"
        )
        reflection = _one_line(outcome.reflection or "")
        lines.append(
            f"- {row.trade_date} {row.ticker} {row.rating or 'Unknown'}: "
            f"raw {outcome.raw_return:+.1%}, alpha {outcome.alpha_return:+.1%}, "
            f"{correct}. {reflection}"
        )
    return "\n".join(lines)


def _resolved_analyses(db: Session, ticker: str | None = None) -> list[Analysis]:
    query = (
        db.query(Analysis)
        .join(Outcome)
        .filter(Analysis.status == "completed")
        .order_by(Analysis.trade_date.asc(), Analysis.id.asc())
    )
    if ticker:
        query = query.filter(Analysis.ticker == ticker.upper())
    return query.all()


def _correct_flags(rows: list[Analysis]) -> list[bool]:
    return [
        is_correct_direction(row.rating or "", row.outcome.raw_return)
        for row in rows
        if row.outcome is not None
    ]


def _model_key(row: Analysis) -> tuple[str, str]:
    return row.llm_provider or "unknown", row.deep_model or "unknown"


def _average(values) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def _average_bools(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def _one_line(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."
