# Milestone 04 — Async Queue + Worker

## Goal

Make batch analysis reliable without manual shell loops. StockSage already has an
`AnalysisQueue` model; this milestone makes it operational through CLI queue commands and a worker
that runs analyses with controlled concurrency.

No web UI yet. The CLI remains the control surface.

## Status

**Planned.** Starts after Milestone 03 makes accuracy semantics and memory sync trustworthy.

---

## Prerequisites

- Milestone 03 accepted.
- Existing `AnalysisQueue` model remains available.
- `Analyzer.run()` and persistence paths remain callable from non-interactive worker code.

---

## Task List

### T01 · Queue commands

- [ ] Add `stocksage queue add TICKER [--date YYYY-MM-DD] [--priority N]`.
- [ ] Add `stocksage queue add-batch TICKER... [--date YYYY-MM-DD]`.
- [ ] Add `stocksage queue list [--status queued|running|completed|failed]`.
- [ ] Add `stocksage queue retry [QUEUE_ID|--failed]`.
- [ ] Add `stocksage queue clear-completed`.

### T02 · Queue state model

- [ ] Decide whether `AnalysisQueue` needs additional status/error fields.
- [ ] If schema changes are needed, create an Alembic revision.
- [ ] Preserve the `ticker`, `trade_date`, `priority`, `queued_at`, and `analysis_id` contract.
- [ ] Ensure duplicate ticker/date queue requests do not create duplicate completed analyses.

### T03 · Worker runner

- [ ] Implement `worker/runner.py`.
- [ ] Poll queued jobs by priority and age.
- [ ] Mark jobs running before invoking `Analyzer`.
- [ ] Reuse the same analysis persistence behavior as `stocksage analyze`.
- [ ] Mark failed jobs with enough error context to retry safely.
- [ ] Support graceful shutdown between jobs.

### T04 · Concurrency and rate safety

- [ ] Default to one concurrent analysis.
- [ ] Add a configurable max worker count, but keep the default conservative for LLM/API cost.
- [ ] Avoid running two jobs for the same ticker/date at the same time.
- [ ] Document token/API cost expectations for batch runs.

### T05 · Resumability and failed jobs

- [ ] Treat existing failed analysis rows as retryable with explicit user intent.
- [ ] Ensure queued jobs can recover after process interruption.
- [ ] Preserve TradingAgents checkpoint behavior when enabled.
- [ ] Make retries reset stale running state safely.

### T06 · Tests

- [ ] Add queue command tests with in-memory SQLite.
- [ ] Add worker tests using a fake analyzer.
- [ ] Cover success, failure, retry, duplicate ticker/date, and interruption recovery.
- [ ] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [ ] A user can enqueue 20 tickers for the same date with one command.
- [ ] The worker processes queued jobs into completed or failed analyses.
- [ ] Failed jobs can be retried without violating the `ticker + trade_date` unique constraint.
- [ ] `stocksage queue list` shows queued, running, completed, and failed work clearly.
- [ ] `AnalysisQueue` is no longer a stub-only table.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Prefer the standard library `concurrent.futures` before introducing Celery, Redis, or another
  service dependency.
- Keep all analysis persistence in one shared helper so CLI single-run and worker-run behavior do
  not drift.
