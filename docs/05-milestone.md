# Milestone 05 — User Identity + Shared Analysis Ownership Foundation

## Goal

Make StockSage multi-user ready before adding the browser application. Analyses remain canonical and shared by
`ticker + trade_date`, while user-level request history records who asked for each analysis,
whether it reused an existing canonical result, and how queued work maps back to the requester.

TradingAgents memory remains global so the system can learn from all resolved outcomes. User
history, tracing, and future permissions live in StockSage request records.

No browser authentication yet. No passwords, sessions, teams, or roles yet.

## Status

**Accepted.** Implemented on 2026-05-13 with migration, CLI integration, queue/worker
attribution, tests, Ruff checks, and local Alembic upgrade verification.

---

## Prerequisites

- Milestone 04 accepted.
- Existing global `analyses(ticker, trade_date)` uniqueness remains in force.
- Existing queue commands and worker paths remain the write surface for batch analysis.

---

## Task List

### T01 · User model

- [x] Add a `users` table with stable integer primary key.
- [x] Add unique `username` for human CLI/web selection.
- [x] Store `created_at` and `last_seen_at` timestamps.
- [x] Backfill a default local user from `getpass.getuser()`.

### T02 · User resolution helper

- [x] Add a core helper that resolves the current request user.
- [x] Default to `getpass.getuser()` when no user flag is provided.
- [x] Support `--user USERNAME` and auto-create/reuse by username.
- [x] Support `--userid ID` and require the id to already exist.
- [x] Reject simultaneous `--user` and `--userid`.

### T03 · Request history model

- [x] Add `analysis_requests` table linking `user_id`, `ticker`, `trade_date`, and request source.
- [x] Include nullable `analysis_id` and `queue_id` so requests can point to canonical analysis rows
  and queued jobs.
- [x] Track request status, timestamps, and error message.
- [x] Preserve global canonical `analyses`, `analysis_details`, `outcomes`, and TradingAgents
  memory semantics.
- [x] Add non-owning attribution columns where useful, such as `created_by_user_id` on canonical
  analyses and `requested_by_user_id` on queue jobs.

### T04 · Migration and backfill

- [x] Create an Alembic migration for `users`, `analysis_requests`, and attribution columns.
- [x] Backfill existing analyses and queue rows to the default local user.
- [x] Create request rows for existing analyses so history pages have a complete starting point.
- [x] Keep the migration SQLite-compatible and PostgreSQL-ready.

### T05 · CLI integration

- [x] Add common `--user` and `--userid` options to write commands.
- [x] Record request user for `stocksage analyze`.
- [x] Record request user for `stocksage queue add` and `stocksage queue add-batch`.
- [x] Add user-aware filters for `stocksage list` and queue/history views where useful.
- [x] Keep leaderboard, model stats, trend analytics, outcomes, and memory sync global by default.

### T06 · Tests

- [x] Test default local user creation.
- [x] Test `--user` auto-create/reuse behavior.
- [x] Test `--userid` lookup and unknown-id failure.
- [x] Test shared canonical analysis reuse across different users.
- [x] Test request history for direct analyze and queued batch flows.
- [x] Test migration/backfill expectations with seeded rows.
- [x] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [x] CLI writes can be attributed to the current OS username by default.
- [x] `--user alice` creates or reuses `alice` and records request history.
- [x] `--userid ID` records against an existing user and fails clearly for unknown IDs.
- [x] Two users can request the same ticker/date without duplicating the canonical analysis row.
- [x] User-scoped history can answer “who asked for this?” without weakening global analytics.
- [x] Existing analyses and queue jobs are backfilled to the default local user.
- [x] `uv run alembic upgrade head`, `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run pytest` pass.

## Verification

- `uv run alembic upgrade head`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run pytest` (`56 passed`)

---

## Notes

- Do not add authentication, passwords, browser sessions, teams, or permissions in this milestone.
- Do not make `analyses`, `analysis_details`, or `outcomes` user-owned. They are canonical system
  records.
- Prefer request history over duplicated analyses so LLM cost, TradingAgents memory, and global
  model-performance analytics remain coherent.
