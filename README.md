# StockSage

LLM-powered stock analysis with persistent history, outcome tracking, and trend analytics.
Wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent framework.

## Setup

```bash
cd /Users/spuri/projects/lexlapax/stocksage

# Create virtual environment
uv venv && source .venv/bin/activate

# Install TradingAgents as a local editable dependency
pip install -e /Users/spuri/projects/TradingAgents

# Install StockSage
pip install -e .

# Configure
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY (or your chosen provider)
```

## Usage

```bash
# Analyze a stock (creates DB tables on first run)
python -m cli.main analyze AAPL

# Analyze with a specific date
python -m cli.main analyze AAPL --date 2026-05-01

# Re-run an existing analysis
python -m cli.main analyze AAPL --force

# List recent analyses
python -m cli.main list

# List by ticker or status
python -m cli.main list --ticker AAPL --status completed

# Resolve outcomes for analyses older than holding-days
python -m cli.main resolve

# View ticker history with outcomes
python -m cli.main summary AAPL
```

## Project structure

See `docs/plan.md` for full architecture.
See `docs/01-milestone.md` and `docs/02-milestone.md` for detailed task lists.

## Milestones

| # | Description | Status |
|---|-------------|--------|
| 01 | CLI + Persistent Storage | in progress |
| 02 | Memory & Trending Engine | planned |
| 03 | Async Job Queue | planned |
| 04 | FastAPI + Jinja2/HTMX Web UI | planned |
| 05 | Charts, Leaderboard, Hardening | planned |
