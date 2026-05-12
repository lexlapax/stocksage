from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "sqlite:///./stocksage.db"

    # LLM
    llm_provider: str = "openai"
    deep_think_llm: str = "gpt-5.4"
    quick_think_llm: str = "gpt-5.4-mini"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Analysis behaviour
    max_debate_rounds: int = 1
    max_risk_discuss_rounds: int = 1
    checkpoint_enabled: bool = True
    output_language: str = "English"

    # Outcome resolution
    outcome_holding_days: int = 5

    # Data directories
    stocksage_data_dir: Path = Path("~/.stocksage").expanduser()

    # Derived — set by validator; override via env if needed
    results_dir: Path = Path("")
    cache_dir: Path = Path("")
    memory_log_path: Path = Path("")

    @model_validator(mode="after")
    def _set_derived_paths(self) -> "Settings":
        base = self.stocksage_data_dir.expanduser()
        if not self.results_dir or str(self.results_dir) == ".":
            self.results_dir = base / "logs"
        if not self.cache_dir or str(self.cache_dir) == ".":
            self.cache_dir = base / "cache"
        if not self.memory_log_path or str(self.memory_log_path) == ".":
            self.memory_log_path = base / "memory" / "trading_memory.md"
        return self

    def as_tradingagents_config(self) -> dict:
        """Build a config dict suitable for TradingAgentsGraph(config=...)."""
        return {
            "llm_provider": self.llm_provider,
            "deep_think_llm": self.deep_think_llm,
            "quick_think_llm": self.quick_think_llm,
            "max_debate_rounds": self.max_debate_rounds,
            "max_risk_discuss_rounds": self.max_risk_discuss_rounds,
            "checkpoint_enabled": self.checkpoint_enabled,
            "output_language": self.output_language,
            "results_dir": str(self.results_dir),
            "data_cache_dir": str(self.cache_dir),
            "memory_log_path": str(self.memory_log_path),
            "data_vendors": {
                "core_stock_apis": "yfinance",
                "technical_indicators": "yfinance",
                "fundamental_data": "yfinance",
                "news_data": "yfinance",
            },
        }


settings = Settings()
