# StockSage — Project Plan

## Vision

StockSage is a standalone application that wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework. It persists every analysis, tracks prediction accuracy over time, and
surfaces historical trends in a browser-based UI. The system starts as a single-user CLI tool and
grows into a web application without architectural rewrites.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite (dev) → PostgreSQL (prod) | SQLAlchemy abstraction; `db.py` and Alembic migrations isolate the switch |
| TradingAgents dependency | Git dependency managed by `uv` | Keeps installs reproducible through `uv.lock` while tracking the upstream project |
| Web frontend | Jinja2 + HTMX | No build toolchain; server-rendered HTML with partial updates is sufficient for one-user scale |
| Async jobs | Thread/process pool (`concurrent.futures`) | Avoids Celery/Redis overhead; sufficient for personal use |
| Project root | `/Users/spuri/projects/lexlapax/stocksage` | Adjacent to other lexlapax projects |

---

## TradingAgents Library API (what we consume)

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph

ta = TradingAgentsGraph(debug=False, config=config)
final_state, decision = ta.propagate(ticker, trade_date)
```

### `config` keys used by StockSage

```python
{
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "checkpoint_enabled": True,
    "output_language": "English",
    "data_vendors": { "core_stock_apis": "yfinance", ... },
    "memory_log_path": "<stocksage data dir>/memory/trading_memory.md",
    "results_dir": "<stocksage data dir>/logs",
    "data_cache_dir": "<stocksage data dir>/cache",
}
```

### `final_state` keys we persist

```
market_report, sentiment_report, news_report, fundamentals_report
investment_debate_state.{bull_history, bear_history, judge_decision}
trader_investment_plan
risk_debate_state.{aggressive_history, conservative_history, neutral_history, judge_decision}
investment_plan
final_trade_decision   ← Portfolio Manager decision (rating + prose)
```

### Structured schemas (from `tradingagents.agents.schemas`)

- `PortfolioRating` — Buy / Overweight / Hold / Underweight / Sell
- `TraderAction` — Buy / Hold / Sell
- `PortfolioDecision` — rating, executive_summary, investment_thesis, price_target, time_horizon

The library's own `TradingMemoryLog` (markdown file) keeps running for prompt injection into the
Portfolio Manager. StockSage's DB is a parallel, richer store for the UI and analytics layer.

---

## Database Schema

### `analyses`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | autoincrement |
| ticker | VARCHAR(16) | e.g. "AAPL" |
| trade_date | DATE | analysis target date |
| run_at | DATETIME | wall-clock start of run |
| completed_at | DATETIME | nullable |
| status | VARCHAR(16) | queued / running / completed / failed |
| rating | VARCHAR(16) | Buy / Overweight / Hold / Underweight / Sell |
| executive_summary | TEXT | |
| investment_thesis | TEXT | |
| price_target | FLOAT | nullable |
| time_horizon | VARCHAR(64) | nullable |
| llm_provider | VARCHAR(32) | |
| deep_model | VARCHAR(64) | |
| quick_model | VARCHAR(64) | |
| error_message | TEXT | nullable; populated on failure |

### `analysis_details`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| analysis_id | INTEGER FK → analyses.id | CASCADE DELETE |
| market_report | TEXT | |
| sentiment_report | TEXT | |
| news_report | TEXT | |
| fundamentals_report | TEXT | |
| bull_history | TEXT | |
| bear_history | TEXT | |
| research_decision | TEXT | judge_decision from investment_debate_state |
| trader_plan | TEXT | trader_investment_plan |
| risk_aggressive | TEXT | |
| risk_conservative | TEXT | |
| risk_neutral | TEXT | |
| risk_decision | TEXT | judge_decision from risk_debate_state |
| full_state_json | TEXT | raw JSON dump of entire final_state |

### `outcomes`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| analysis_id | INTEGER FK → analyses.id | CASCADE DELETE |
| resolved_at | DATETIME | |
| raw_return | FLOAT | (price_end - price_start) / price_start |
| alpha_return | FLOAT | raw_return - SPY return over same period |
| holding_days | INTEGER | actual trading days held |
| reflection | TEXT | LLM-generated reflection |

### `analysis_queue`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| ticker | VARCHAR(16) | |
| trade_date | DATE | |
| priority | INTEGER | 0 = normal, 1 = high |
| queued_at | DATETIME | |
| status | VARCHAR(16) | queued / running / completed / failed |
| started_at | DATETIME | nullable |
| completed_at | DATETIME | nullable |
| attempts | INTEGER | retry/run count |
| last_error | TEXT | nullable; populated on failed jobs |
| analysis_id | INTEGER FK → analyses.id | nullable; set on start |

---

## Project Layout

```
stocksage/
├── docs/
│   ├── plan.md                ← this file
│   ├── getting-started.md     ← local setup and CLI usage
│   ├── development.md         ← development workflow and quality checks
│   ├── 01-milestone.md        ← Phase 1 detailed tasks
│   ├── 02-milestone.md        ← Phase 2 detailed tasks
│   ├── 03-milestone.md        ← Accuracy semantics + memory sync
│   ├── 04-milestone.md        ← Async queue + worker
│   └── 05-milestone.md        ← Web UI + charts
├── stocksage/
│   ├── __init__.py
│   └── cli.py                 ← Click commands and console script entry point
├── core/
│   ├── __init__.py
│   ├── analyzer.py            ← TradingAgentsGraph wrapper
│   ├── analysis_runs.py       ← shared analysis persistence helpers
│   ├── models.py              ← SQLAlchemy ORM models
│   ├── db.py                  ← engine / session factory / Alembic target
│   ├── outcomes.py            ← fetch returns, resolve pending analyses
│   ├── trends.py              ← alpha-aware accuracy metrics, trending
│   ├── memory_sync.py         ← resolved outcome sync to TradingAgents memory
│   └── queueing.py            ← queue operations and job claiming
├── cli/
│   ├── __init__.py
│   └── main.py                ← compatibility wrapper for python -m cli.main
├── worker/
│   ├── __init__.py
│   └── runner.py              ← thread pool queue poller (Milestone 04)
├── api/
│   ├── __init__.py
│   ├── app.py                 ← FastAPI app factory (Milestone 05)
│   ├── routes/
│   │   ├── analyses.py
│   │   ├── queue.py
│   │   └── outcomes.py
│   └── schemas/
│       └── analysis.py
├── web/
│   └── templates/             ← Jinja2 HTML (Milestone 05)
├── alembic/
│   ├── env.py
│   └── versions/
├── config.py                  ← Pydantic Settings; reads from .env
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Milestones

| Milestone | Description | Status | Doc |
|-----------|-------------|--------|-----|
| **01** | CLI + Persistent Storage | accepted | `docs/01-milestone.md` |
| **02** | Memory & Trending Engine | accepted | `docs/02-milestone.md` |
| **03** | Accuracy Semantics + TradingAgents Memory Sync | accepted | `docs/03-milestone.md` |
| **04** | Async Job Queue + Worker | accepted | `docs/04-milestone.md` |
| **05** | FastAPI + Jinja2/HTMX Web UI + Charts | active next | `docs/05-milestone.md` |

---

## Environment Variables (`.env`)

```
# Database
DATABASE_URL=sqlite:///./stocksage.db

# LLM
LLM_PROVIDER=openai
DEEP_THINK_LLM=gpt-5.4
QUICK_THINK_LLM=gpt-5.4-mini
OPENAI_API_KEY=...

# Optional overrides
STOCKSAGE_DATA_DIR=~/.stocksage
TRADINGAGENTS_RESULTS_DIR=~/.stocksage/logs
TRADINGAGENTS_CACHE_DIR=~/.stocksage/cache
TRADINGAGENTS_MEMORY_LOG_PATH=~/.stocksage/memory/trading_memory.md
```

---

## Operating and Development Docs

- Local setup, configuration, and CLI usage: `docs/getting-started.md`
- Development workflow, checks, and project layout: `docs/development.md`
