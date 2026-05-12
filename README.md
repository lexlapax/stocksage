# StockSage

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework with persistent storage, outcome tracking, and trend analytics.
It is currently a local CLI and is structured to grow into a FastAPI + Jinja2/HTMX web UI.

## Where We Are

- **M01 accepted:** CLI analysis, SQLite persistence, Alembic migration, tests, Ruff checks,
  and a live `stocksage analyze AAPL` smoke run are complete.
- **M02 accepted:** trend analytics, leaderboard, and model performance commands are complete
  and validated against a 20-stock resolved batch.
- **M03 next:** raw-direction accuracy is too blunt for Overweight/Underweight calls, so the
  next milestone makes metrics alpha-aware and syncs resolved DB lessons back into
  TradingAgents memory.

## Project Docs

| Need | Doc |
|------|-----|
| Architecture, schema, and roadmap | [docs/plan.md](docs/plan.md) |
| Local setup and CLI usage | [docs/getting-started.md](docs/getting-started.md) |
| Development workflow and quality checks | [docs/development.md](docs/development.md) |
| M01 details | [docs/01-milestone.md](docs/01-milestone.md) |
| M02 details | [docs/02-milestone.md](docs/02-milestone.md) |
| M03 details | [docs/03-milestone.md](docs/03-milestone.md) |
| M04 details | [docs/04-milestone.md](docs/04-milestone.md) |
| M05 details | [docs/05-milestone.md](docs/05-milestone.md) |

## Next Steps

Implement Milestone 03 before starting queue or web work:

1. Add alpha-direction accuracy alongside raw-direction accuracy.
2. Make leaderboard and model metrics default to alpha-aware scoring.
3. Sync resolved outcomes from StockSage's database into TradingAgents' markdown memory log.
4. Cover the new semantics with tests, including PLTR-style alpha-correct cases.
