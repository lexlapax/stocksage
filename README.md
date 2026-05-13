# StockSage

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents)
multi-agent LLM framework with persistent storage, outcome tracking, and trend analytics.
It has a local CLI and an in-progress FastAPI + Jinja2/HTMX browser UI over the same shared
analysis database.

## Where We Are

- **M01 accepted:** CLI analysis, SQLite persistence, Alembic migration, tests, Ruff checks,
  and a live `stocksage analyze AAPL` smoke run are complete.
- **M02 accepted:** trend analytics, leaderboard, and model performance commands are complete
  and validated against a 20-stock resolved batch.
- **M03 accepted:** accuracy is now alpha-aware by default, raw-direction correctness remains
  visible as a diagnostic, and resolved DB outcomes sync into TradingAgents memory.
- **M04 accepted:** queue commands and the worker make batch analysis resumable and retryable.
- **M05 accepted:** user identity and request history now track who asked for shared analyses.
- **M06 in progress:** route foundation, app shell, research pages, user workspace, modal
  submission, and queue retry controls are complete; charts and final docs/tests remain.

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

Finish Milestone 06:

1. Add Chart.js visualizations for alpha-aware trends and ticker performance.
2. Finish local run docs and template coverage.
3. Keep route tests, template tests, Ruff, and pytest green as the UI fills in.
