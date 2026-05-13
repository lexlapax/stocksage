# Development

This guide covers the local development workflow. See [getting-started.md](getting-started.md)
for setup and CLI usage.

## Package Management

Use `uv` exclusively.

```bash
uv sync
uv add <package>
uv add --dev <package>
uv run <command>
```

Do not use raw `pip install` to add dependencies to this project.

## Quality Checks

Run these before every commit:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ruff is configured in [pyproject.toml](../pyproject.toml) and installed through the `dev`
dependency group. Tests use in-memory SQLite and mock live network and LLM paths.
FastAPI, Uvicorn, Jinja2, and form parsing dependencies are first-class project dependencies for
the web UI.

When editing browser JavaScript, also run:

```bash
node --check web/static/app.js
node --check web/static/charts.js
```

## Database Changes

All schema changes go through Alembic:

```bash
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
```

Keep the database layer PostgreSQL-compatible even though local development uses SQLite.

## Project Layout

```text
stocksage/  Import-safe package entry point for the CLI
core/       ORM models, DB sessions, analyzer wrapper, outcomes, trends, users, requests
cli/        Compatibility wrapper for python -m cli.main
worker/     Async queue worker
api/        FastAPI app factory, route dependencies, routes, and view-data assembly
web/        Jinja2 templates, HTMX partials, CSS, and lightweight chart JavaScript
alembic/    Database migrations
docs/       Project plan, usage docs, development guide, and milestone checklists
tests/      Unit and CLI integration tests
```

## Docs Maintenance

When milestone status changes, update the matching milestone doc, [plan.md](plan.md),
[../README.md](../README.md), [../AGENTS.md](../AGENTS.md), and
[../CHANGELOG.md](../CHANGELOG.md).

When milestone numbers shift, run a stale-reference scan for old doc paths and milestone names
before committing.

For docs-only changes, run `git diff --check` and a stale-wording scan tailored to the change:

```bash
rg "old status phrase|retired milestone name" README.md AGENTS.md CHANGELOG.md docs
git diff --check
```
