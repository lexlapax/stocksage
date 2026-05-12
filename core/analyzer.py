"""Thin wrapper around TradingAgentsGraph.

All imports of tradingagents are isolated here so the rest of the codebase
never depends on the library directly.
"""

import re
from dataclasses import dataclass, field
from datetime import date

from config import Settings
from config import settings as _default_settings


@dataclass
class AnalysisResult:
    ticker: str
    trade_date: date
    rating: str
    executive_summary: str
    investment_thesis: str
    price_target: float | None
    time_horizon: str | None
    market_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str
    bull_history: str
    bear_history: str
    research_decision: str
    trader_plan: str
    risk_aggressive: str
    risk_conservative: str
    risk_neutral: str
    risk_decision: str
    decision_text: str
    full_state: dict = field(default_factory=dict, repr=False)


_RATING_PATTERN = re.compile(
    r"\*\*Rating\*\*:\s*(Buy|Overweight|Hold|Underweight|Sell)", re.IGNORECASE
)
_SUMMARY_PATTERN = re.compile(r"\*\*Executive Summary\*\*:\s*(.+?)(?=\n\n|\*\*|$)", re.DOTALL)
_THESIS_PATTERN = re.compile(r"\*\*Investment Thesis\*\*:\s*(.+?)(?=\n\n\*\*|$)", re.DOTALL)
_PRICE_PATTERN = re.compile(r"\*\*Price Target\*\*:\s*([\d.]+)")
_HORIZON_PATTERN = re.compile(r"\*\*Time Horizon\*\*:\s*(.+?)(?:\n|$)")


def _parse_decision(text: str) -> dict:
    """Extract structured fields from Portfolio Manager prose output."""
    rating_m = _RATING_PATTERN.search(text)
    summary_m = _SUMMARY_PATTERN.search(text)
    thesis_m = _THESIS_PATTERN.search(text)
    price_m = _PRICE_PATTERN.search(text)
    horizon_m = _HORIZON_PATTERN.search(text)

    rating = rating_m.group(1).capitalize() if rating_m else "Hold"
    # Normalise to the 5-tier vocabulary
    _normalise = {
        "buy": "Buy",
        "overweight": "Overweight",
        "hold": "Hold",
        "underweight": "Underweight",
        "sell": "Sell",
    }
    rating = _normalise.get(rating.lower(), rating)

    return {
        "rating": rating,
        "executive_summary": summary_m.group(1).strip() if summary_m else text[:500],
        "investment_thesis": thesis_m.group(1).strip() if thesis_m else text,
        "price_target": float(price_m.group(1)) if price_m else None,
        "time_horizon": horizon_m.group(1).strip() if horizon_m else None,
    }


class Analyzer:
    def __init__(self, cfg: Settings = _default_settings, debug: bool = False):
        from tradingagents.graph.trading_graph import TradingAgentsGraph  # lazy import

        self._settings = cfg
        self._ta = TradingAgentsGraph(debug=debug, config=cfg.as_tradingagents_config())

    def run(self, ticker: str, trade_date: date) -> AnalysisResult:
        ticker = ticker.upper()
        date_str = trade_date.strftime("%Y-%m-%d")

        final_state, _signal = self._ta.propagate(ticker, date_str)

        decision_text: str = final_state.get("final_trade_decision", "")
        parsed = _parse_decision(decision_text)

        inv = final_state.get("investment_debate_state", {})
        risk = final_state.get("risk_debate_state", {})

        return AnalysisResult(
            ticker=ticker,
            trade_date=trade_date,
            rating=parsed["rating"],
            executive_summary=parsed["executive_summary"],
            investment_thesis=parsed["investment_thesis"],
            price_target=parsed["price_target"],
            time_horizon=parsed["time_horizon"],
            market_report=final_state.get("market_report", ""),
            sentiment_report=final_state.get("sentiment_report", ""),
            news_report=final_state.get("news_report", ""),
            fundamentals_report=final_state.get("fundamentals_report", ""),
            bull_history=inv.get("bull_history", ""),
            bear_history=inv.get("bear_history", ""),
            research_decision=inv.get("judge_decision", ""),
            trader_plan=final_state.get("trader_investment_plan", ""),
            risk_aggressive=risk.get("aggressive_history", ""),
            risk_conservative=risk.get("conservative_history", ""),
            risk_neutral=risk.get("neutral_history", ""),
            risk_decision=risk.get("judge_decision", ""),
            decision_text=decision_text,
            full_state={
                k: v
                for k, v in final_state.items()
                if not hasattr(v, "__class__")
                or isinstance(v, (str, dict, list, float, int, bool, type(None)))
            },
        )
