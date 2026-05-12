# Milestone 01 — CLI + Persistent Storage

## Goal

A working command-line tool that:
1. Runs a full TradingAgents analysis for a ticker
2. Persists every analysis and its full report sections to SQLite
3. Resolves prediction outcomes (actual returns) for past analyses
4. Prints a historical summary per ticker

No web server yet. No async queue yet. One analysis at a time, synchronous.

---

## Prerequisites

- Python 3.11+
- `uv` (or `pip`)
- TradingAgents (installed via `uv sync` — git dependency in `pyproject.toml`)
- OpenAI (or other LLM provider) API key in `.env`

---

## Task List

### T01 · Project scaffold

- [ ] `pyproject.toml` — project metadata, dependencies, scripts entry point
- [ ] `.env.example` — document every env var
- [ ] `config.py` — `pydantic-settings` `Settings` class; reads from `.env` + env vars
- [ ] `README.md` — setup steps, usage examples
- [ ] `.gitignore` — exclude `.env`, `*.db`, `__pycache__`, `.venv`
- [ ] `alembic.ini` + `alembic/env.py` — point at `core.db.Base.metadata` and `DATABASE_URL`

**Key `config.py` fields:**
```python
class Settings(BaseSettings):
    database_url: str = "sqlite:///./stocksage.db"
    llm_provider: str = "openai"
    deep_think_llm: str = "gpt-5.4"
    quick_think_llm: str = "gpt-5.4-mini"
    openai_api_key: str = ""
    stocksage_data_dir: Path = Path("~/.stocksage").expanduser()
    # derived paths (validators)
    results_dir: Path       # stocksage_data_dir / "logs"
    cache_dir: Path         # stocksage_data_dir / "cache"
    memory_log_path: Path   # stocksage_data_dir / "memory" / "trading_memory.md"
```

---

### T02 · SQLAlchemy models (`core/models.py`)

Define all ORM models using `DeclarativeBase`. No business logic here.

```python
class Analysis(Base):
    __tablename__ = "analyses"
    id, ticker, trade_date, run_at, completed_at
    status            # "queued" | "running" | "completed" | "failed"
    rating            # Buy | Overweight | Hold | Underweight | Sell
    executive_summary, investment_thesis
    price_target (Float, nullable)
    time_horizon (String, nullable)
    llm_provider, deep_model, quick_model
    error_message (Text, nullable)
    # relationships
    detail: AnalysisDetail (one-to-one, cascade delete)
    outcome: Outcome (one-to-one, cascade delete)

class AnalysisDetail(Base):
    __tablename__ = "analysis_details"
    id, analysis_id (FK)
    market_report, sentiment_report, news_report, fundamentals_report
    bull_history, bear_history, research_decision
    trader_plan
    risk_aggressive, risk_conservative, risk_neutral, risk_decision
    full_state_json   # TEXT — JSON dump of entire final_state dict

class Outcome(Base):
    __tablename__ = "outcomes"
    id, analysis_id (FK)
    resolved_at, raw_return, alpha_return, holding_days, reflection

class AnalysisQueue(Base):
    __tablename__ = "analysis_queue"
    id, ticker, trade_date, priority, queued_at
    analysis_id (FK, nullable)
```

**Important:** Use `UniqueConstraint("ticker", "trade_date")` on `analyses` so the same
ticker+date cannot be analyzed twice accidentally.

---

### T03 · Database session factory (`core/db.py`)

```python
# engine creation — SQLite uses check_same_thread=False connect_args
# PostgreSQL is a different URL scheme; SQLAlchemy handles it transparently
engine = create_engine(settings.database_url, ...)
SessionLocal = sessionmaker(bind=engine)

def get_db() -> Generator[Session, None, None]: ...
def init_db() -> None:
    Base.metadata.create_all(bind=engine)
```

Alembic `env.py` must import `Base` from `core.models` so auto-generated migrations see all tables.

---

### T04 · Alembic initial migration

After models are written:
```bash
alembic init alembic          # already done by scaffold
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

The revision file goes in `alembic/versions/`. Commit it. Every future schema change gets its own
revision — this is how we migrate to PostgreSQL later without pain.

---

### T05 · Analyzer wrapper (`core/analyzer.py`)

Wraps `TradingAgentsGraph` so the CLI and worker never import from `tradingagents` directly.

```python
class Analyzer:
    def __init__(self, settings: Settings):
        # build config dict from settings
        # instantiate TradingAgentsGraph(debug=..., config=config)

    def run(self, ticker: str, trade_date: date) -> AnalysisResult:
        # calls ta.propagate(ticker, str(trade_date))
        # returns AnalysisResult dataclass (not ORM model)

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
    full_state: dict          # raw final_state
    decision_text: str        # raw final_trade_decision string
```

**Parsing `final_trade_decision`:** The Portfolio Manager returns prose with embedded `**Rating**:`,
`**Executive Summary**:`, `**Investment Thesis**:` markers. Use regex or a small parser to extract
structured fields. Fall back to storing the full text in `investment_thesis` if parsing fails.

---

### T06 · Outcome resolver (`core/outcomes.py`)

Mirrors the logic already in `TradingAgentsGraph._fetch_returns` and `_resolve_pending_entries`,
but operates on the DB rather than the markdown memory log.

```python
def resolve_pending(db: Session, settings: Settings) -> int:
    """
    Find all completed analyses with no Outcome and trade_date older than
    HOLDING_DAYS (default 7) calendar days.
    For each, fetch yfinance returns (raw + alpha vs SPY).
    Generate LLM reflection via tradingagents Reflector.
    Write Outcome row.
    Returns count of newly resolved analyses.
    """

def _fetch_returns(ticker: str, trade_date: date, holding_days: int = 5
    ) -> tuple[float, float, int] | None:
    # same yfinance logic as trading_graph._fetch_returns
    # returns (raw_return, alpha_return, actual_days) or None

def _generate_reflection(decision_text: str, raw: float, alpha: float,
                          settings: Settings) -> str:
    # instantiate a one-shot LLM call using tradingagents Reflector
    # or a direct LLM client call
```

---

### T07 · CLI (`cli/main.py`)

Use `click`. Four commands:

#### `analyze`
```
python -m cli.main analyze TICKER [--date YYYY-MM-DD] [--debug]
```
1. `init_db()` (idempotent)
2. Check for existing completed analysis for this ticker+date; skip if found (print message)
3. Create `Analysis` row with `status="running"`
4. Call `Analyzer.run(ticker, date)`
5. Update `Analysis` + create `AnalysisDetail` with all fields; set `status="completed"`
6. On exception: set `status="failed"`, `error_message=str(e)`; re-raise
7. Print formatted decision to stdout

#### `resolve`
```
python -m cli.main resolve [--holding-days N]
```
Calls `resolve_pending(db, settings)`. Prints count resolved.

#### `summary TICKER`
```
python -m cli.main summary TICKER [--n 10]
```
Queries last N completed analyses for ticker. Prints table:
```
Date        Rating       Raw Ret   Alpha   Reflection
2026-05-01  Buy          +3.2%    +1.1%   "Model overestimated..."
2026-04-15  Hold         -0.8%    -0.2%   "Correct caution given..."
```

#### `list`
```
python -m cli.main list [--status completed|failed|queued] [--ticker AAPL]
```
Tabular output of recent analyses.

---

### T08 · Wire everything together

- `cli/main.py` imports from `core.db`, `core.analyzer`, `core.outcomes`
- `config.py` is the single source of truth for all paths and credentials
- `init_db()` is called at the top of every CLI command (idempotent via `create_all`)
- `.env` is loaded via `pydantic-settings` automatically on `Settings()` instantiation

---

### T09 · Smoke test

Not a full test suite — just verify the wiring:
```bash
python -m cli.main analyze AAPL
python -m cli.main list
python -m cli.main resolve
python -m cli.main summary AAPL
```
Check that `stocksage.db` has rows in `analyses` and `analysis_details`.
After waiting 7 trading days, run `resolve` again and verify an `outcomes` row appears.

---

## Dependencies (`pyproject.toml`)

```toml
[project]
name = "stocksage"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "tradingagents",            # local editable: pip install -e /path/to/TradingAgents
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "pydantic-settings>=2.0",
    "click>=8.1",
    "python-dotenv>=1.0",
    "yfinance>=0.2",            # for outcome resolver (returns fetching)
    "tabulate>=0.9",            # CLI table output
    "rich>=13.0",               # pretty CLI output
]

[project.scripts]
stocksage = "cli.main:cli"

[tool.setuptools.packages.find]
where = ["."]
```

---

## Acceptance Criteria

- [ ] `python -m cli.main analyze AAPL` completes without error
- [ ] `stocksage.db` contains rows in `analyses` and `analysis_details`
- [ ] Re-running the same ticker+date prints "already analyzed" and skips
- [ ] `python -m cli.main list` prints the completed analysis
- [ ] `python -m cli.main resolve` runs without error (may resolve 0 if analysis is too recent)
- [ ] `python -m cli.main summary AAPL` prints the rating and any resolved outcome
- [ ] A failed analysis (bad ticker, API error) sets `status="failed"` with `error_message`

---

## Files to Create

```
stocksage/
├── pyproject.toml
├── config.py
├── .env.example
├── .gitignore
├── README.md
├── alembic.ini
├── alembic/
│   ├── env.py
│   └── versions/
│       └── <hash>_initial_schema.py   (generated)
├── core/
│   ├── __init__.py
│   ├── models.py
│   ├── db.py
│   ├── analyzer.py
│   └── outcomes.py
└── cli/
    ├── __init__.py
    └── main.py
```
