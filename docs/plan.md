# StockSage — Project Plan

## Vision

StockSage is a standalone application that wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework. It persists every analysis, tracks prediction accuracy over time, and
surfaces historical trends in a browser-based UI. The system starts as a local CLI tool, adds
multi-user request attribution before the web layer, and grows into a web application without
architectural rewrites.

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite (dev) → PostgreSQL (prod) | SQLAlchemy abstraction; `db.py` and Alembic migrations isolate the switch |
| TradingAgents dependency | Git dependency managed by `uv` | Keeps installs reproducible through `uv.lock` while tracking the upstream project |
| Web frontend | Jinja2 + HTMX | No build toolchain; server-rendered HTML with partial updates is sufficient for one-user scale |
| Async jobs | Thread/process pool (`concurrent.futures`) | Avoids Celery/Redis overhead; sufficient for personal use |
| Multi-user data | Shared canonical analyses + per-user request history | Keeps global learning/analytics coherent while preserving user history and future permissions |
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

The library's own `TradingMemoryLog` (markdown file) keeps running globally for prompt injection
into the Portfolio Manager. StockSage's DB is a parallel, richer store for the UI and analytics
layer. User-specific history is tracked in StockSage request records, not by splitting
TradingAgents memory per user.

---

## Database Schema

### Multi-user ownership model

StockSage uses shared canonical analysis records plus per-user request history:

- `analyses`, `analysis_details`, `outcomes`, and TradingAgents memory are global system records.
- `users` identifies who asked for work.
- `analysis_requests` records user history and links requests to canonical analyses and queue jobs.
- Attribution columns such as `created_by_user_id` and `requested_by_user_id` are non-owning trace
  fields; ownership/history lives in `analysis_requests`.

### `users`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | stable user id |
| username | VARCHAR(128) | unique human identifier; `--user` auto-creates/reuses |
| created_at | DATETIME | |
| last_seen_at | DATETIME | updated when resolved by CLI/web |

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
| created_by_user_id | INTEGER FK → users.id | nullable, non-owning attribution |

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
| requested_by_user_id | INTEGER FK → users.id | nullable, non-owning attribution |

### `analysis_requests`
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER PK | |
| user_id | INTEGER FK → users.id | requester |
| ticker | VARCHAR(16) | denormalized for filtering and history |
| trade_date | DATE | denormalized for filtering and history |
| analysis_id | INTEGER FK → analyses.id | nullable until canonical analysis exists |
| queue_id | INTEGER FK → analysis_queue.id | nullable for direct runs or reused analyses |
| source | VARCHAR(32) | cli / cli_queue / web / backfill_analysis / backfill_queue |
| status | VARCHAR(16) | queued / running / completed / failed / reused |
| requested_at | DATETIME | |
| completed_at | DATETIME | nullable |
| error_message | TEXT | nullable |

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
│   ├── 05-milestone.md        ← User identity + request history
│   ├── 06-milestone.md        ← Web UI + charts
│   └── 06-ui-design.md        ← M06 wireframe and UI building blocks
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
│   ├── queueing.py            ← queue operations and job claiming
│   ├── users.py               ← default OS user, --user, and --userid resolution
│   └── request_history.py     ← per-user request rows over shared analyses
├── cli/
│   ├── __init__.py
│   └── main.py                ← compatibility wrapper for python -m cli.main
├── worker/
│   ├── __init__.py
│   └── runner.py              ← thread pool queue poller (Milestone 04)
├── api/
│   ├── __init__.py
│   ├── app.py                 ← FastAPI app factory
│   ├── deps.py                ← DB session dependency wiring
│   ├── services.py            ← route view-data assembly over core modules
│   ├── routes/
│   │   └── web.py             ← Research, Workspace, Analysis, Queue routes
├── web/
│   ├── templates/             ← Jinja2 app shell and page templates
│   └── static/                ← CSS and future lightweight browser assets
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
| **05** | User Identity + Shared Analysis Ownership Foundation | accepted | `docs/05-milestone.md` |
| **06** | FastAPI + Jinja2/HTMX Web UI + Charts | active next | `docs/06-milestone.md` |

Milestone 06 started with the accepted review gate in `docs/06-ui-design.md`. Keep route and
template work aligned with that wireframe as implementation continues.

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
