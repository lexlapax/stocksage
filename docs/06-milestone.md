# Milestone 06 — FastAPI + Jinja2/HTMX Web UI + Charts

## Goal

Provide a local browser UI for analyses, queue management, ticker summaries, trend metrics,
leaderboards, model performance, and charts. The web app should sit on top of the same DB-native
core modules used by the CLI.

This milestone combines the original web UI and charting work so the browser experience launches
with useful M03 alpha-aware metrics and M05 user-scoped history.

## Status

**Planned / next.** Milestone 05 has established user identity and request attribution; this is the
next implementation milestone.

---

## Prerequisites

- Milestone 03 accepted so web metrics use alpha-aware accuracy.
- Milestone 04 accepted so the UI can enqueue and inspect background work.
- Milestone 05 accepted so the UI can show user-scoped history over shared canonical analyses.
- FastAPI optional dependencies installed through the project `api` extra or equivalent `uv`
  dependency group.

---

## Task List

### T00 · UX design and modular UI plan

- [x] Create a design spec for the non-technical user experience.
- [x] Define the primary navigation, page hierarchy, and plain-language labels.
- [x] Define reusable UI building blocks before template implementation.
- [x] Review and adjust the design before writing web UI code.

Design spec: [06-ui-design.md](06-ui-design.md)

### T01 · FastAPI app foundation

- [ ] Add an app factory under `api/`.
- [ ] Wire database sessions through FastAPI dependencies.
- [ ] Add routes for: health, Research landing (`/`), Ticker Intelligence (`/ticker/{ticker}`),
  Analysis Report (`/analysis/{id}`), My Workspace (`/workspace`), New Analysis (POST),
  and Queue Status (`/queue`, admin-only, not in primary nav).
- [ ] Keep route handlers thin; use `core/` modules for business logic.

### T02 · Jinja2 layout and navigation

- [ ] Create a base template with a top navigation bar: Research | My Workspace | [user ▾] | [+ Analyze].
  No persistent left sidebar.
- [ ] Use server-rendered pages as the primary experience.
- [ ] Use HTMX only for targeted partial updates: My Workspace status polling (while rows are
  queued/running), sort/filter changes on the Research table, and retry actions.
- [ ] Keep the UI dense, clear, and operational rather than marketing-style.

### T03 · Analysis and ticker pages

- [ ] Research landing: sortable/filterable system-wide stock table (sort by alpha, hit rate,
  recency, ticker; filter by rating, min results, date range); inline sparkline per ticker.
- [ ] My Workspace: user-scoped submission list with status badges; HTMX polling while active.
- [ ] Ticker Intelligence page: metric tiles, alpha-over-time bar chart, rating calibration
  horizontal bar chart (hidden when fewer than 3 resolved outcomes), analysis history table.
- [ ] Analysis Report page: outcome block (stock return, SPY, alpha, beat/missed) shown only
  when outcome is resolved; summary, thesis, and tabbed evidence sections.
- [ ] Include raw return and alpha return side by side in the outcome block.

### T04 · Queue controls

- [ ] Add New Analysis modal (single ticker + date; reuse detection note when report exists).
  Modal is triggered from the [+ Analyze] button; submits via POST and redirects to My Workspace.
- [ ] Add retry action for failed submissions (in My Workspace and Queue Status pages).
- [ ] Add Queue Status page (`/queue`): table of queued/running/failed items with HTMX auto-refresh.
  This page is not in primary navigation; link to it from the running-work indicator in My Workspace.
- [ ] No batch enqueue form in this milestone.

### T05 · Charts

- [ ] System accuracy chart on Research landing: rolling 30-day hit rate line chart (Chart.js,
  CDN, no build pipeline).
- [ ] Alpha-over-time bar chart on Ticker Intelligence: one bar per resolved analysis, green/rose
  coloring, 0-line prominent.
- [ ] Rating calibration horizontal bar chart on Ticker Intelligence: avg alpha by rating label;
  hidden with a note when fewer than 3 resolved outcomes exist for that ticker.
- [ ] Serialize chart data server-side into a `<script>` tag as JSON; no separate API endpoint
  for chart data.
- [ ] No separate leaderboard page and no model-performance page; the Research landing is the
  leaderboard.

### T06 · Local run docs and tests

- [ ] Document `uv run uvicorn ...` or equivalent local startup command.
- [ ] Add route tests for core pages and JSON/partial endpoints.
- [ ] Add template rendering tests for empty DB and seeded DB states.
- [ ] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [x] UI design is reviewed and accepted before template implementation starts.
- [ ] The Research landing shows all analyzed stocks sorted by best alpha, with working sort and
  filter controls and an accuracy-over-time chart.
- [ ] Clicking a stock opens the Ticker Intelligence page with alpha bar chart and (when data
  allows) a rating calibration chart.
- [ ] Clicking an analysis opens the Analysis Report with outcome block, summary, thesis, and
  tabbed evidence.
- [ ] My Workspace shows the current user's submissions with live status and HTMX polling while
  work is active.
- [ ] A user can submit a new analysis via the modal and retry a failed submission.
- [ ] Empty DB states and thin-data states (e.g. fewer than 3 outcomes) render clearly without
  crashes or empty chart frames.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Do not introduce a JavaScript build pipeline unless server-rendered templates plus HTMX prove
  insufficient.
- Prefer Chart.js or a similarly small browser-side charting dependency only when charting starts.
- Keep API schemas stable enough that a future richer frontend could reuse them.
