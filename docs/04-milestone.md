# Milestone 04 — Async Queue + Worker

## Goal

Make batch analysis reliable without manual shell loops. StockSage already has an
`AnalysisQueue` model; this milestone makes it operational through CLI queue commands and a worker
that runs analyses with controlled concurrency.

No user identity foundation or web UI yet. The CLI remains the control surface.

## Status

**Accepted.** Queue commands, durable queue state, worker processing, retries, stale-run recovery,
and tests are complete.

Validation completed on 2026-05-12 with `uv run alembic upgrade head`,
`uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.

---

## Prerequisites

- Milestone 03 accepted.
- Existing `AnalysisQueue` model remains available.
- `Analyzer.run()` and persistence paths remain callable from non-interactive worker code.

---

## Task List

### T01 · Queue commands

- [x] Add `stocksage queue add TICKER [--date YYYY-MM-DD] [--priority N]`.
- [x] Add `stocksage queue add-batch TICKER... [--date YYYY-MM-DD]`.
- [x] Add `stocksage queue list [--status queued|running|completed|failed]`.
- [x] Add `stocksage queue retry [QUEUE_ID|--failed]`.
- [x] Add `stocksage queue clear-completed`.

### T02 · Queue state model

- [x] Decide whether `AnalysisQueue` needs additional status/error fields.
- [x] If schema changes are needed, create an Alembic revision.
- [x] Preserve the `ticker`, `trade_date`, `priority`, `queued_at`, and `analysis_id` contract.
- [x] Ensure duplicate ticker/date queue requests do not create duplicate completed analyses.

### T03 · Worker runner

- [x] Implement `worker/runner.py`.
- [x] Poll queued jobs by priority and age.
- [x] Mark jobs running before invoking `Analyzer`.
- [x] Reuse the same analysis persistence behavior as `stocksage analyze`.
- [x] Mark failed jobs with enough error context to retry safely.
- [x] Support graceful shutdown between jobs.

### T04 · Concurrency and rate safety

- [x] Default to one concurrent analysis.
- [x] Add a configurable max worker count, but keep the default conservative for LLM/API cost.
- [x] Avoid running two jobs for the same ticker/date at the same time.
- [x] Document token/API cost expectations for batch runs.

### T05 · Resumability and failed jobs

- [x] Treat existing failed analysis rows as retryable with explicit user intent.
- [x] Ensure queued jobs can recover after process interruption.
- [x] Preserve TradingAgents checkpoint behavior when enabled.
- [x] Make retries reset stale running state safely.

### T06 · Tests

- [x] Add queue command tests with in-memory SQLite.
- [x] Add worker tests using a fake analyzer.
- [x] Cover success, failure, retry, duplicate ticker/date, and interruption recovery.
- [x] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [x] A user can enqueue 20 tickers for the same date with one command.
- [x] The worker processes queued jobs into completed or failed analyses.
- [x] Failed jobs can be retried without violating the `ticker + trade_date` unique constraint.
- [x] `stocksage queue list` shows queued, running, completed, and failed work clearly.
- [x] `AnalysisQueue` is no longer a stub-only table.
- [x] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Prefer the standard library `concurrent.futures` before introducing Celery, Redis, or another
  service dependency.
- Keep all analysis persistence in one shared helper so CLI single-run and worker-run behavior do
  not drift.
