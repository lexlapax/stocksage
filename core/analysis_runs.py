"""Shared analysis persistence helpers."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from config import Settings
from config import settings as _default_settings
from core.analyzer import AnalysisResult
from core.models import Analysis, AnalysisDetail


@dataclass(frozen=True)
class AnalysisRunPrep:
    analysis: Analysis
    should_run: bool
    reason: str


def prepare_analysis_row(
    db: Session,
    ticker: str,
    trade_date: date,
    force: bool,
    cfg: Settings = _default_settings,
    requested_by_user_id: int | None = None,
) -> AnalysisRunPrep:
    ticker = ticker.upper()
    existing = (
        db.query(Analysis)
        .filter(Analysis.ticker == ticker, Analysis.trade_date == trade_date)
        .first()
    )

    if existing and not force:
        return AnalysisRunPrep(existing, False, existing.status)

    now = datetime.now(UTC)
    if existing:
        if existing.detail is not None:
            db.delete(existing.detail)
        if existing.outcome is not None:
            db.delete(existing.outcome)
        db.flush()

        existing.run_at = now
        existing.completed_at = None
        existing.status = "running"
        existing.rating = None
        existing.executive_summary = None
        existing.investment_thesis = None
        existing.price_target = None
        existing.time_horizon = None
        existing.llm_provider = cfg.llm_provider
        existing.deep_model = cfg.deep_think_llm
        existing.quick_model = cfg.quick_think_llm
        existing.error_message = None
        if existing.created_by_user_id is None:
            existing.created_by_user_id = requested_by_user_id
        db.commit()
        db.refresh(existing)
        return AnalysisRunPrep(existing, True, "forced")

    row = Analysis(
        ticker=ticker,
        trade_date=trade_date,
        run_at=now,
        status="running",
        llm_provider=cfg.llm_provider,
        deep_model=cfg.deep_think_llm,
        quick_model=cfg.quick_think_llm,
        created_by_user_id=requested_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AnalysisRunPrep(row, True, "created")


def persist_analysis_result(db: Session, analysis_id: int, result: AnalysisResult) -> Analysis:
    row = db.get(Analysis, analysis_id)
    row.status = "completed"
    row.completed_at = datetime.now(UTC)
    row.rating = result.rating
    row.executive_summary = result.executive_summary
    row.investment_thesis = result.investment_thesis
    row.price_target = result.price_target
    row.time_horizon = result.time_horizon

    detail = AnalysisDetail(
        analysis_id=analysis_id,
        market_report=result.market_report,
        sentiment_report=result.sentiment_report,
        news_report=result.news_report,
        fundamentals_report=result.fundamentals_report,
        bull_history=result.bull_history,
        bear_history=result.bear_history,
        research_decision=result.research_decision,
        trader_plan=result.trader_plan,
        risk_aggressive=result.risk_aggressive,
        risk_conservative=result.risk_conservative,
        risk_neutral=result.risk_neutral,
        risk_decision=result.risk_decision,
        full_state_json=json.dumps(result.full_state, default=str),
    )
    db.add(detail)
    db.commit()
    db.refresh(row)
    return row


def mark_analysis_failed(db: Session, analysis_id: int, error: str) -> Analysis:
    row = db.get(Analysis, analysis_id)
    row.status = "failed"
    row.error_message = error
    db.commit()
    db.refresh(row)
    return row
