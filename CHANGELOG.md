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
- Unit and CLI integration tests covering analyzer parsing, ORM relationships, outcome resolution, trend analytics, and forced reruns.
- Ruff linting and formatting checks configured in `pyproject.toml`.

### Changed

- `analyze --force` now reuses and resets the existing `ticker + trade_date` row instead of violating the unique constraint.
- `summary` now shows resolved counts, directional accuracy, average returns, rating breakdowns, trend markers, and recent outcome correctness.
- Project setup documentation now uses `uv` consistently.
- The `stocksage` console script now points at `stocksage.cli:cli` to avoid collisions with third-party `cli` packages.

### Known Gaps

- Live TradingAgents analysis smoke testing still requires a configured `.env` with a valid provider API key.
- Milestone 02 analytics need a real resolved-analysis dataset before their output can be empirically validated.
- Async worker and web UI remain planned for later milestones.
