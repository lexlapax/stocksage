# StockSage

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework with persistent storage, outcome tracking, and trend analytics.
It has a local CLI and FastAPI + Jinja2/HTMX browser UI over the same shared analysis database.

**Current release:** `0.0.1`

## Where We Are

- **M01 accepted:** CLI analysis, SQLite persistence, Alembic migration, tests, Ruff checks,
  and a live `stocksage analyze AAPL` smoke run are complete.
- **M02 accepted:** trend analytics, leaderboard, and model performance commands are complete
  and validated against a 20-stock resolved batch.
- **M03 accepted:** accuracy is now alpha-aware by default, raw-direction correctness remains
  visible as a diagnostic, and resolved DB outcomes sync into TradingAgents memory.
- **M04 accepted:** queue commands and the worker make batch analysis resumable and retryable.
- **M05 accepted:** user identity and request history now track who asked for shared analyses.
- **M06 accepted:** local FastAPI + Jinja2/HTMX web UI, user workspace, queue controls,
  Chart.js visualizations, local run docs, and route/template tests are complete.

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
| M06 details | [docs/06-milestone.md](docs/06-milestone.md) |
| M06 UI wireframe | [docs/06-ui-design.md](docs/06-ui-design.md) |

## Next Steps

1. Run the web UI locally against your real database and do a human smoke test.
2. Decide the next milestone scope after M06 based on that walkthrough.
