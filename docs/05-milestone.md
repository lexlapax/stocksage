# Milestone 05 — FastAPI + Jinja2/HTMX Web UI + Charts

## Goal

Provide a local browser UI for analyses, queue management, ticker summaries, trend metrics,
leaderboards, model performance, and charts. The web app should sit on top of the same DB-native
core modules used by the CLI.

This milestone combines the original web UI and charting work so the browser experience launches
with useful M03 alpha-aware metrics.

## Status

**Planned.** Starts after Milestone 04 makes batch analysis manageable.

---

## Prerequisites

- Milestone 03 accepted so web metrics use alpha-aware accuracy.
- Milestone 04 accepted so the UI can enqueue and inspect background work.
- FastAPI optional dependencies installed through the project `api` extra or equivalent `uv`
  dependency group.

---

## Task List

### T01 · FastAPI app foundation

- [ ] Add an app factory under `api/`.
- [ ] Wire database sessions through FastAPI dependencies.
- [ ] Add routes for health, analyses, tickers, outcomes, queue, leaderboard, and models.
- [ ] Keep route handlers thin; use `core/` modules for business logic.

### T02 · Jinja2 layout and navigation

- [ ] Create a base template with navigation for dashboard, analyses, queue, leaderboard, and models.
- [ ] Use server-rendered pages as the primary experience.
- [ ] Use HTMX only for targeted partial updates such as queue refresh and filter changes.
- [ ] Keep the UI dense, clear, and operational rather than marketing-style.

### T03 · Analysis and ticker pages

- [ ] Add analysis history with filters for ticker, status, rating, date range, and model.
- [ ] Add analysis detail pages showing the persisted reports and final decision.
- [ ] Add ticker summary pages using M03 alpha-aware trend stats.
- [ ] Include raw return and alpha return side by side.

### T04 · Queue controls

- [ ] Add queue list page.
- [ ] Add forms to enqueue a single ticker or batch tickers.
- [ ] Add retry controls for failed jobs.
- [ ] Add lightweight auto-refresh for queue status.

### T05 · Charts and leaderboard

- [ ] Add trend charts for ticker accuracy and alpha over time.
- [ ] Add rating calibration charts.
- [ ] Add leaderboard and model-performance pages.
- [ ] Serialize chart data from existing dataclasses without duplicating analytics logic.

### T06 · Local run docs and tests

- [ ] Document `uv run uvicorn ...` or equivalent local startup command.
- [ ] Add route tests for core pages and JSON/partial endpoints.
- [ ] Add template rendering tests for empty DB and seeded DB states.
- [ ] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [ ] A user can run the local web app and view DB-backed analysis history.
- [ ] A user can inspect a ticker summary with alpha-aware metrics and charts.
- [ ] A user can view leaderboard and model-performance pages.
- [ ] A user can enqueue analyses and retry failed jobs from the browser.
- [ ] Empty DB states render clearly without crashes.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Do not introduce a JavaScript build pipeline unless server-rendered templates plus HTMX prove
  insufficient.
- Prefer Chart.js or a similarly small browser-side charting dependency only when charting starts.
- Keep API schemas stable enough that a future richer frontend could reuse them.
