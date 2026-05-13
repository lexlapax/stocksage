# Getting Started

Use this guide to install StockSage locally, configure live LLM access, and run the CLI.

## Requirements

- Python 3.11+
- `uv`
- An LLM provider key, such as `OPENAI_API_KEY`

TradingAgents is declared as a git dependency in [pyproject.toml](../pyproject.toml) and pinned
through [uv.lock](../uv.lock).

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

# Process queued work; default is one worker to control LLM/API cost
uv run stocksage queue run --limit 5

# Retry one failed job or all failed jobs
uv run stocksage queue retry 12
uv run stocksage queue retry --failed
```

The compatibility module entry point remains available:

```bash
uv run python -m cli.main --help
```

## Live Run Notes

- `stocksage analyze` makes live LLM and market-data calls.
- `stocksage resolve` only resolves analyses old enough to have the configured holding period.
- Milestone 05 will add user attribution flags. The planned default user is the current OS
  username; `--user USERNAME` auto-creates/reuses a username, while `--userid ID` must reference an
  existing user.
- `stocksage queue run` defaults to one concurrent analysis because each job can make live LLM and
  market-data calls. Increase `--max-workers` only when the provider budget and rate limits are
  comfortable.
- Use `stocksage queue list --status failed` and `stocksage queue retry --failed` to resume failed
  batches without re-creating completed analyses.
