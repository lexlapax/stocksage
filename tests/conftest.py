"""Shared fixtures for all tests."""

from datetime import date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import Analysis, AnalysisDetail, Base


@pytest.fixture(scope="function")
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def completed_analysis(db):
    row = Analysis(
        ticker="AAPL",
        trade_date=date(2026, 1, 2),
        run_at=datetime(2026, 1, 2, 9, 0, 0),
        completed_at=datetime(2026, 1, 2, 9, 5, 0),
        status="completed",
        rating="Buy",
        executive_summary="Strong fundamentals.",
        investment_thesis="Long-term growth story.",
        llm_provider="openai",
        deep_model="gpt-4o",
        quick_model="gpt-4o-mini",
    )
    db.add(row)
    db.flush()
    detail = AnalysisDetail(
        analysis_id=row.id,
        market_report="Market report text.",
        sentiment_report="Sentiment report text.",
        news_report="News report text.",
        fundamentals_report="Fundamentals report text.",
    )
    db.add(detail)
    db.commit()
    return row
