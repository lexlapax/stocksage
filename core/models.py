"""SQLAlchemy ORM models. No business logic — pure schema."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("ticker", "trade_date", name="uq_ticker_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="queued")
    # Portfolio Manager structured fields
    rating: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    executive_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    investment_thesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price_target: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_horizon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # LLM provenance
    llm_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    deep_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    quick_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Error tracking
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    detail: Mapped[Optional["AnalysisDetail"]] = relationship(
        back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )
    outcome: Mapped[Optional["Outcome"]] = relationship(
        back_populates="analysis", uselist=False, cascade="all, delete-orphan"
    )


class AnalysisDetail(Base):
    __tablename__ = "analysis_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    market_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    news_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fundamentals_report: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bull_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bear_history: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    research_decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trader_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_aggressive: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_conservative: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_neutral: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_state_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="detail")


class Outcome(Base):
    __tablename__ = "outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_return: Mapped[float] = mapped_column(Float, nullable=False)
    alpha_return: Mapped[float] = mapped_column(Float, nullable=False)
    holding_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reflection: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    analysis: Mapped["Analysis"] = relationship(back_populates="outcome")


class AnalysisQueue(Base):
    __tablename__ = "analysis_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    analysis_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("analyses.id"), nullable=True
    )
