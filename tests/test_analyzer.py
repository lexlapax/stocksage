"""Tests for the analyzer wrapper (no live LLM calls)."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from core.analyzer import Analyzer, AnalysisResult, _parse_decision


SAMPLE_DECISION = """
**Rating**: Buy

**Executive Summary**: The company shows strong momentum driven by AI tailwinds.

**Investment Thesis**: Revenue growth is accelerating and margins are expanding. The stock
remains undervalued relative to peers. Long-term holders will benefit from multiple expansion.

**Price Target**: 245.00
**Time Horizon**: 12 months
"""


def test_parse_decision_extracts_rating():
    result = _parse_decision(SAMPLE_DECISION)
    assert result["rating"] == "Buy"


def test_parse_decision_extracts_summary():
    result = _parse_decision(SAMPLE_DECISION)
    assert "strong momentum" in result["executive_summary"]


def test_parse_decision_extracts_price_target():
    result = _parse_decision(SAMPLE_DECISION)
    assert result["price_target"] == pytest.approx(245.0)


def test_parse_decision_extracts_horizon():
    result = _parse_decision(SAMPLE_DECISION)
    assert result["time_horizon"] == "12 months"


def test_parse_decision_fallback_on_missing_rating():
    result = _parse_decision("No structured content here.")
    assert result["rating"] == "Hold"


def test_analyzer_run_returns_analysis_result():
    mock_ta = MagicMock()
    mock_ta.propagate.return_value = (
        {
            "final_trade_decision": SAMPLE_DECISION,
            "market_report": "market",
            "sentiment_report": "sentiment",
            "news_report": "news",
            "fundamentals_report": "fundamentals",
            "trader_investment_plan": "buy 100 shares",
            "investment_debate_state": {
                "bull_history": "bull",
                "bear_history": "bear",
                "judge_decision": "bull wins",
            },
            "risk_debate_state": {
                "aggressive_history": "agg",
                "conservative_history": "con",
                "neutral_history": "neu",
                "judge_decision": "moderate",
            },
        },
        "BUY",
    )

    analyzer = Analyzer.__new__(Analyzer)
    analyzer._settings = MagicMock()
    analyzer._ta = mock_ta

    result = analyzer.run("aapl", date(2026, 1, 2))

    assert isinstance(result, AnalysisResult)
    assert result.ticker == "AAPL"
    assert result.rating == "Buy"
    assert result.price_target == pytest.approx(245.0)
    assert result.market_report == "market"
