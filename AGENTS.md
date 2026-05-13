# StockSage — Agent Instructions

## Project

StockSage wraps the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent
LLM framework (pulled as a git dependency from GitHub) to add persistent storage,
outcome tracking, and a web UI. The core loop is:

1. User requests an analysis for a ticker + date
2. `core/analyzer.py` calls `TradingAgentsGraph.propagate(ticker, date)` — runs market,
   sentiment, news, and fundamentals agents, a bull/bear research debate, a trader, and a
   portfolio manager; returns a structured decision (Buy/Overweight/Hold/Underweight/Sell)
3. The result is stored in SQLite (`core/models.py`: `Analysis` + `AnalysisDetail`)
4. After ~5 trading days, `core/outcomes.py` fetches actual returns from yfinance, generates
   an LLM reflection, and writes an `Outcome` row
5. `core/trends.py` computes alpha-aware accuracy metrics and surfaces patterns over time
6. `core/memory_sync.py` syncs resolved DB lessons into TradingAgents memory
7. `worker/runner.py` processes queued analyses with conservative concurrency and retry support
8. `core/users.py` and `core/request_history.py` track who asked for shared canonical analyses
9. Milestone 06 adds the FastAPI + Jinja2/HTMX web UI and charts

Human-facing orientation starts in `README.md`. Local setup and CLI usage live in
`docs/getting-started.md`; development workflow lives in `docs/development.md`. Full architecture
and DB schema: `docs/plan.md`

---

## Current Status

**Current status: `0.0.1` release baseline — Milestone 06 accepted**
Detailed task lists and acceptance criteria:
`docs/01-milestone.md`, `docs/02-milestone.md`, `docs/03-milestone.md`,
`docs/04-milestone.md`, `docs/05-milestone.md`, `docs/06-milestone.md`

**What exists:**
- `config.py` — pydantic-settings; reads `.env`; builds tradingagents config dict
- `core/models.py` — SQLAlchemy ORM: User, Analysis, AnalysisDetail, Outcome, AnalysisQueue, AnalysisRequest
- `core/db.py` — engine, SessionLocal, init_db()
- `core/analysis_runs.py` — shared analysis row preparation, success persistence, and failure marking
- `core/analyzer.py` — wraps TradingAgentsGraph; parses final_state into AnalysisResult
- `core/outcomes.py` — batch yfinance return resolver + LLM reflection via tradingagents Reflector
- `core/trends.py` — alpha-aware ticker/model accuracy stats, rating calibration, trend helpers
- `core/memory_sync.py` — DB-to-TradingAgents memory log sync for resolved outcomes
- `core/queueing.py` — enqueue/list/retry/clear/claim queue operations
- `core/users.py` — default OS user, `--user`, and `--userid` resolution
- `core/request_history.py` — per-user request rows over shared canonical analyses and queue jobs
- `core/submissions.py` — shared submission helper for web/CLI-style request attribution
- `worker/runner.py` — queue worker with stale-running recovery and configurable worker count
- `stocksage/cli.py` — Click commands: analyze, resolve, summary, list, leaderboard, models, queue
- `api/app.py` — FastAPI app factory for Milestone 06
- `api/deps.py` — DB session dependency wiring for routes and tests
- `api/services.py` — route view-data assembly over core modules, including web submission/retry helpers
- `api/routes/web.py` — route handlers for Research, Workspace, Analysis, Queue, submission, retry, and health
- `web/templates/` — Jinja2 shell, page templates, and HTMX partials for M06
- `web/static/styles.css` and `web/static/charts.js` — shared web UI styling and Chart.js rendering
- `cli/main.py` — compatibility wrapper for `python -m cli.main`
- `alembic/env.py` — migrations wired to Settings.database_url + core.models.Base
- `tests/` — unit and CLI integration coverage for Milestone 01/02/03/04 behavior
- `docs/getting-started.md` — local setup, configuration, and CLI usage
- `docs/development.md` — development workflow, checks, and docs maintenance
- `docs/03-milestone.md` — accepted alpha-aware accuracy and memory sync work
- `docs/04-milestone.md` — accepted async queue + worker work
- `docs/05-milestone.md` — accepted user identity + request history work
- `docs/06-milestone.md` — accepted web UI + charts work

**Next action:** Run a local human smoke test and plan the next milestone:
```bash
uv run alembic upgrade head
uv run uvicorn api.app:app --reload
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Milestone 01 is accepted after a live AAPL TradingAgents smoke run. Milestone 02 is accepted after
a 20-stock resolved validation batch. Milestone 03 is accepted after alpha-aware accuracy and
TradingAgents memory sync landed with tests. Milestone 04 is accepted after queue commands, worker
processing, retries, stale-run recovery, and the queue migration landed with tests.
Milestone 05 is accepted after adding `users`, `analysis_requests`, CLI user flags, queue
attribution, migration backfill, and tests. Milestone 06 is accepted after adding the local web UI,
HTMX partials, queue controls, Chart.js charts, run docs, and route/template tests.

---

## Environment

- **Python**: 3.11+
- **Package manager**: `uv` exclusively. Never use raw `pip install` to add dependencies.
  - Add a dependency: `uv add <package>`
  - Add a dev/test dependency: `uv add --dev <package>`
  - Install from lockfile: `uv sync`
  - Run a command in the venv: `uv run <command>`
- **Virtual environment**: `.venv/` at project root (created by `uv venv`).
- **TradingAgents** is a git dependency declared in `pyproject.toml` and pinned in `uv.lock`.
  Never modify it to serve StockSage needs — treat it as a third-party library.

## Before Every Commit

1. Run lint: `uv run ruff check .`
2. Run format check: `uv run ruff format --check .`
3. Run the test suite: `uv run pytest`
4. Fix any failures before committing — do not skip with `--no-verify`.
5. If no tests exist yet for the code being changed, write at least one before committing.

## Project Layout

```
stocksage/  Import-safe package entry point for the CLI
core/       ORM models, DB session, analyzer wrapper, outcome resolver, trends
cli/        Compatibility wrapper for python -m cli.main
worker/     Async queue runner
api/        FastAPI app + routes + Pydantic schemas (Milestone 06)
web/        Jinja2 templates (Milestone 06)
alembic/    DB migrations — every schema change gets its own revision
docs/       plan.md, getting-started.md, development.md, and milestone docs 01-06
```

## Database Rules

- All schema changes go through Alembic: `uv run alembic revision --autogenerate -m "description"`
- Run `uv run alembic upgrade head` after generating a revision.
- Never call `Base.metadata.create_all()` in production paths — only in `init_db()` for dev convenience.
- SQLite for development; the abstraction layer (`core/db.py`) must stay PostgreSQL-compatible.
  - No SQLite-specific SQL or pragma calls outside `core/db.py`.
  - Use SQLAlchemy ORM or Core; no raw `sqlite3` calls.

## Library & API References

Before writing code that uses any library, framework, or external API, always consult
the **Context7 MCP plugin** (`mcp__context7__resolve-library-id` + `mcp__context7__query-docs`)
to fetch current documentation. Do not rely on training-data knowledge for:

- SQLAlchemy ORM patterns (mapped columns, relationships, session API)
- Alembic migration commands and `env.py` patterns
- Pydantic / pydantic-settings field declarations and validators
- Click command/option signatures
- yfinance download API (column structure changes between releases)
- LangGraph / LangChain APIs used inside TradingAgents
- FastAPI routing, dependency injection, and Pydantic schemas (Milestone 06+)

Steps: call `resolve-library-id` with the library name, then `query-docs` with the
specific question. Use `researchMode: true` on a second call if the first answer is stale
or incomplete.

## Code Style

- No comments explaining what the code does — only why, when non-obvious.
- No docstrings beyond a single short line when truly needed.
- Keep `core/` modules free of CLI/web concerns — they are pure business logic.
- `config.py` is the single source of truth for all settings; never hardcode paths or keys elsewhere.
- All TradingAgents imports are isolated in `core/analyzer.py` and `core/outcomes.py`.

## Testing

- Test files live in `tests/`.
- Use an in-memory SQLite DB for all tests: `sqlite:///:memory:`.
- No live network calls or LLM calls in tests — mock or stub them.
- Fixture pattern: `conftest.py` provides a `db` session and pre-seeded `Analysis`/`Outcome` rows.

## Milestones

Milestones 01-06 are accepted. Before starting the next implementation milestone, update
`docs/plan.md` and add a milestone doc that names the new scope and acceptance criteria.
