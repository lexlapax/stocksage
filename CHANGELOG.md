# Changelog

All notable changes to StockSage are tracked here.

## [0.1.0] - 2026-05-12

### Added

- Initial SQLite persistence model for analyses, analysis details, outcomes, and queued work.
- Alembic initial schema migration.
- Click CLI commands: `analyze`, `resolve`, `summary`, `list`, `leaderboard`, and `models`.
- Import-safe `stocksage` package entry point plus a compatibility wrapper for `python -m cli.main`.
- TradingAgents wrapper that isolates third-party imports in `core/analyzer.py`.
- Outcome resolver with batched yfinance price fetching and optional `resolve --force`.
- Trend analytics for ticker accuracy, rating calibration, model performance, rolling accuracy, and cross-ticker lessons.
- Alpha-aware accuracy semantics for five-tier ratings, with raw-direction accuracy kept as a diagnostic.
- DB-to-TradingAgents memory sync for resolved outcomes, including pending-entry updates and idempotent appends.
- Shared analysis-run persistence helpers used by both single CLI runs and queued worker runs.
- Operational queue commands: `queue add`, `queue add-batch`, `queue list`, `queue retry`, `queue clear-completed`, and `queue run`.
- Queue worker with retry support, stale running-job reset, conservative default concurrency, and configurable `--max-workers`.
- Alembic queue-state migration adding status, timestamps, attempts, and last-error tracking to `analysis_queue`.
- User identity model with default local OS user resolution, `--user` auto-create/reuse, and strict existing-id `--userid` lookup.
- Per-user `analysis_requests` history over shared canonical analyses, including queued work, reused analyses, failures, and migration backfill.
- CLI attribution for `analyze`, `queue add`, and `queue add-batch`, plus user-scoped `list` and `queue list` filters.
- FastAPI app factory, DB session dependency, T01 route map, and route tests for Research, Workspace, Analysis Report, Queue Status, New Analysis POST, and health.
- Jinja2 app shell, top navigation, initial Research/Workspace/Ticker/Report/Queue templates, shared CSS, and HTML route tests.
- Research filters/sorting, Workspace status polling partial, Ticker Intelligence chart sections, and Analysis Report outcome/evidence layout.
- New Analysis modal reuse detection, queue-backed retry actions in My Workspace and Queue Status, and HTMX queue polling partials.
- Shared `core/submissions.py` helper for web submissions over the same canonical analysis and request-history model.
- Unit and CLI integration tests covering analyzer parsing, ORM relationships, outcome resolution, trend analytics, and forced reruns.
- Memory sync tests covering pending-entry resolution, fallback decision rendering, and idempotency.
- Queue and worker tests covering enqueueing, duplicate protection, retry, failure, stale recovery, and worker persistence.
- User/request tests covering default user creation, username reuse, `--userid`, shared analysis reuse, queue attribution, and migration backfill.
- Ruff linting and formatting checks configured in `pyproject.toml`.
- Detailed milestone docs for M03 accuracy semantics/memory sync, M04 async queue/worker, M05 user identity/request history, and M06 web UI/charts.
- M06 UI wireframe and reusable building-block design spec for review before implementation.
- Focused docs for local setup/CLI usage and development workflow.

### Changed

- `analyze --force` now reuses and resets the existing `ticker + trade_date` row instead of violating the unique constraint.
- `summary` now shows resolved counts, alpha-direction accuracy, raw-direction accuracy, average returns, rating breakdowns, trend markers, and recent outcome correctness.
- `leaderboard --by accuracy` and `models` now report alpha-direction accuracy by default.
- `resolve` now syncs resolved outcomes into TradingAgents memory, and `analyze` syncs before live runs so prior lessons can feed `past_context`.
- `analyze` now uses the shared persistence path also used by the queue worker.
- Project setup documentation now uses `uv` consistently.
- The `stocksage` console script now points at `stocksage.cli:cli` to avoid collisions with third-party `cli` packages.
- Milestone docs now mark M01 and M02 accepted after live validation and move raw-vs-alpha accuracy plus memory sync into M03.
- `README.md` is now a concise project front door, with operational details moved to `docs/getting-started.md` and `docs/development.md`.
- Roadmap now inserts M05 user identity and shared-analysis request history before moving web UI/charts to M06.
- Active roadmap now marks M05 accepted and moves M06 web UI/charts into the next implementation slot.
- FastAPI, Uvicorn, Jinja2, and form parsing dependencies are now first-class project dependencies for the web UI milestone.

### Known Gaps

- M06 Chart.js visualizations, final local-run docs, and empty/thin-state template coverage remain in progress.
