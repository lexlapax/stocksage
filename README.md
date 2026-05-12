# StockSage

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework with persistent storage, outcome tracking, and trend analytics.
It starts as a local CLI and is structured so the same core modules can later back a
FastAPI + Jinja2/HTMX web UI.

## What Works Now

- Run a TradingAgents analysis for a ticker/date and store the structured result in SQLite.
- Persist full analysis detail sections, including the raw final state JSON.
- Resolve older analyses with yfinance returns and alpha versus SPY.
- Re-run an existing ticker/date safely with `analyze --force`.
- Summarize ticker history with directional accuracy, per-rating returns, and trend markers.
- Rank tickers with `leaderboard`.
- Compare model/provider performance with `models`.

## Requirements

- Python 3.11+
- `uv`
- An LLM provider API key, such as `OPENAI_API_KEY`

TradingAgents is declared as a git dependency in [pyproject.toml](pyproject.toml) and pinned
through [uv.lock](uv.lock).

## Setup

```bash
cd /Users/spuri/projects/lexlapax/stocksage
uv venv
uv sync
cp .env.example .env
```

Edit `.env` and set at least:

```bash
OPENAI_API_KEY=...
```

Initialize or upgrade the database:

```bash
uv run alembic upgrade head
```

## CLI Usage

```bash
# Analyze a stock for today
uv run stocksage analyze AAPL

# Analyze a specific date
uv run stocksage analyze AAPL --date 2026-05-01

# Re-run an existing ticker/date in place
uv run stocksage analyze AAPL --date 2026-05-01 --force

# Resolve pending outcomes
uv run stocksage resolve

# Re-resolve existing outcomes
uv run stocksage resolve --force

# Show ticker history and trend stats
uv run stocksage summary AAPL

# List recent analyses
uv run stocksage list

# Rank tickers by accuracy, alpha, or resolved count
uv run stocksage leaderboard --by accuracy --min-resolved 3

# Compare model/provider performance
uv run stocksage models
```

The legacy module entry point remains available for compatibility:

```bash
uv run python -m cli.main --help
```

## Configuration

Configuration is centralized in [config.py](config.py).
The default development database is `sqlite:///./stocksage.db`.

Common `.env` values:

```bash
DATABASE_URL=sqlite:///./stocksage.db
LLM_PROVIDER=openai
DEEP_THINK_LLM=gpt-5.4
QUICK_THINK_LLM=gpt-5.4-mini
OPENAI_API_KEY=...
STOCKSAGE_DATA_DIR=~/.stocksage
OUTCOME_HOLDING_DAYS=5
```

## Quality Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ruff is configured in [pyproject.toml](pyproject.toml) and installed through the `dev`
dependency group. Tests use in-memory SQLite and mock all live network/LLM paths.

## Project Layout

```text
stocksage/  Import-safe package entry point for the CLI
core/       ORM models, DB sessions, analyzer wrapper, outcomes, trends
cli/        Compatibility wrapper for python -m cli.main
worker/     Async queue runner stub for Milestone 03
api/        FastAPI package placeholder for Milestone 04
web/        Template placeholder for Milestone 04
alembic/    Database migrations
docs/       Project plan and milestone checklists
tests/      Unit and CLI integration tests
```

## Milestones

| # | Description | Status |
|---|-------------|--------|
| 01 | CLI + Persistent Storage | code complete; live LLM smoke pending configured API key |
| 02 | Memory & Trending Engine | code/test complete; needs real resolved-analysis dataset for validation |
| 03 | Async Job Queue | planned |
| 04 | FastAPI + Jinja2/HTMX Web UI | planned |
| 05 | Charts, Leaderboard, Hardening | planned |
