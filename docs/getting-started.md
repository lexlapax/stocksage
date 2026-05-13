# Getting Started

Use this guide to install StockSage locally, configure live LLM access, run the CLI, and start
the browser UI.

## Requirements

- Python 3.11+
- `uv`
- An LLM provider key, such as `OPENAI_API_KEY`

TradingAgents is declared as a git dependency in [pyproject.toml](../pyproject.toml) and pinned
through [uv.lock](../uv.lock).

## Setup

```bash
cd <path-to-stocksage>
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

## Configuration

Configuration is centralized in [config.py](../config.py). The default development database is
`sqlite:///./stocksage.db`.

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

## CLI Usage

```bash
# Analyze a stock for today
uv run stocksage analyze AAPL

# Attribute a direct analysis request to a specific user
uv run stocksage analyze AAPL --user alice

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

# Show request history for one user
uv run stocksage list --user alice

# Rank tickers by alpha-direction accuracy, average alpha, or resolved count
uv run stocksage leaderboard --by accuracy --min-resolved 3

# Compare model/provider performance
uv run stocksage models

# Queue one stock for background analysis
uv run stocksage queue add AAPL --date 2026-05-01

# Attribute queued work to an existing numeric user id
uv run stocksage queue add AAPL --date 2026-05-01 --userid 3

# Queue a batch for the same date
uv run stocksage queue add-batch AAPL MSFT NVDA GOOGL AMZN --date 2026-05-01

# Inspect queued/running/completed/failed jobs
uv run stocksage queue list

# Inspect queued work requested by one user
uv run stocksage queue list --user alice

# Process queued work; default is one worker to control LLM/API cost
uv run stocksage queue run --limit 5

# Retry one failed job or all failed jobs
uv run stocksage queue retry 12
uv run stocksage queue retry --failed
```

## Web App

The local browser UI is served through FastAPI with server-rendered Jinja2 templates, targeted
HTMX updates, and Chart.js charts loaded from CDN.

```bash
uv run alembic upgrade head
uv run uvicorn api.app:app --reload
```

Open:

- `http://127.0.0.1:8000/` — Research landing
- `http://127.0.0.1:8000/workspace` — My Workspace for the current OS user
- `http://127.0.0.1:8000/queue` — Queue Status
- `http://127.0.0.1:8000/health` — health check

Use the `+ Analyze` button to submit one ticker/date at a time. The UI reuses existing shared
reports when the same ticker/date has already completed or is already queued/running.

Web requests default to the current OS username. Use the modal's `Run as` field to submit as a
different local user, or open `/workspace?user=alice` to view another user's request history.

The compatibility module entry point remains available:

```bash
uv run python -m cli.main --help
```

## Live Run Notes

- `stocksage analyze` makes live LLM and market-data calls.
- `stocksage resolve` only resolves analyses old enough to have the configured holding period.
- CLI write commands default to the current OS username. Use `--user USERNAME` to auto-create/reuse
  a named user, or `--userid ID` to use an existing numeric user id.
- `stocksage queue run` defaults to one concurrent analysis because each job can make live LLM and
  market-data calls. Increase `--max-workers` only when the provider budget and rate limits are
  comfortable.
- Use `stocksage queue list --status failed` and `stocksage queue retry --failed` to resume failed
  batches without re-creating completed analyses.
