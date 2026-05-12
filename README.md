# StockSage

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework with persistent storage, outcome tracking, and trend analytics.
It is currently a local CLI and is structured to grow into a FastAPI + Jinja2/HTMX web UI.

## Where We Are

- **M01 accepted:** CLI analysis, SQLite persistence, Alembic migration, tests, Ruff checks,
  and a live `stocksage analyze AAPL` smoke run are complete.
- **M02 accepted:** trend analytics, leaderboard, and model performance commands are complete
  and validated against a 20-stock resolved batch.
- **M03 accepted:** accuracy is now alpha-aware by default, raw-direction correctness remains
  visible as a diagnostic, and resolved DB outcomes sync into TradingAgents memory.
- **M04 accepted:** queue commands and the worker make batch analysis resumable and retryable.
- **M05 next:** add the FastAPI + Jinja2/HTMX web UI and charts.

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

Implement Milestone 05:

1. Add a local FastAPI app and Jinja2 templates.
2. Show DB-backed analysis history, trends, leaderboard, and model performance.
3. Add queue controls for enqueueing, retrying, and inspecting background work.
4. Display M03 alpha-aware metrics in browser charts.
