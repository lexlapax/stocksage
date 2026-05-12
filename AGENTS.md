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
5. `core/trends.py` (Milestone 02) computes accuracy metrics and surfaces patterns over time
6. A FastAPI + Jinja2/HTMX web UI (Milestone 04) presents history, trends, and new query forms

Full architecture and DB schema: `docs/plan.md`

---

## Current Status

**Active milestone: 01 — CLI + Persistent Storage**  
Detailed task list and acceptance criteria: `docs/01-milestone.md`

**What exists (scaffold only — not yet installed or smoke-tested):**
- `config.py` — pydantic-settings; reads `.env`; builds tradingagents config dict
- `core/models.py` — SQLAlchemy ORM: Analysis, AnalysisDetail, Outcome, AnalysisQueue
- `core/db.py` — engine, SessionLocal, init_db()
- `core/analyzer.py` — wraps TradingAgentsGraph; parses final_state into AnalysisResult
- `core/outcomes.py` — batch yfinance return resolver + LLM reflection via tradingagents Reflector
- `cli/main.py` — Click commands: analyze, resolve, summary, list
- `alembic/env.py` — migrations wired to Settings.database_url + core.models.Base
- `core/trends.py` — stub (Milestone 02)
- `worker/runner.py` — stub (Milestone 03)

**Next action:** Install dependencies and smoke-test end-to-end:
```bash
uv venv && source .venv/bin/activate
uv sync
cp .env.example .env   # set OPENAI_API_KEY (or preferred provider)
uv run python -m cli.main analyze AAPL
```

**Update this section** whenever a milestone task is completed or the active milestone changes.

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

1. Run the test suite: `uv run pytest`
2. Fix any failures before committing — do not skip with `--no-verify`.
3. If no tests exist yet for the code being changed, write at least one before committing.

## Project Layout

```
core/       ORM models, DB session, analyzer wrapper, outcome resolver, trends
cli/        Click CLI commands (analyze, resolve, summary, list, leaderboard, models)
worker/     Async queue runner (Milestone 03+)
api/        FastAPI app + routes + Pydantic schemas (Milestone 04+)
web/        Jinja2 templates (Milestone 04+)
alembic/    DB migrations — every schema change gets its own revision
docs/       plan.md, 01-milestone.md, 02-milestone.md
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
- FastAPI routing, dependency injection, and Pydantic schemas (Milestones 04+)

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

Current work is tracked in `docs/01-milestone.md`. Check off tasks as they are completed.
Do not start Milestone 02 work until the Milestone 01 acceptance criteria are met.
