# Milestone 06 — FastAPI + Jinja2/HTMX Web UI + Charts

## Goal

Provide a local browser UI for analyses, queue management, ticker summaries, trend metrics,
leaderboards, model performance, and charts. The web app should sit on top of the same DB-native
core modules used by the CLI.

This milestone combines the original web UI and charting work so the browser experience launches
with useful M03 alpha-aware metrics and M05 user-scoped history.

## Status

**Accepted.** T00-T06 are implemented, tested, documented, and ready for local user testing.

---

## Prerequisites

- Milestone 03 accepted so web metrics use alpha-aware accuracy.
- Milestone 04 accepted so the UI can enqueue and inspect background work.
- Milestone 05 accepted so the UI can show user-scoped history over shared canonical analyses.
- FastAPI, Uvicorn, Jinja2, and python-multipart are first-class project dependencies.

---

## Task List

### T00 · UX design and modular UI plan

- [x] Create a design spec for the non-technical user experience.
- [x] Define the primary navigation, page hierarchy, and plain-language labels.
- [x] Define reusable UI building blocks before template implementation.
- [x] Review and adjust the design before writing web UI code.

Design spec: [06-ui-design.md](06-ui-design.md)

### T01 · FastAPI app foundation

- [x] Add an app factory under `api/`.
- [x] Wire database sessions through FastAPI dependencies.
- [x] Add routes for: health, Research landing (`/`), Ticker Intelligence (`/ticker/{ticker}`),
  Analysis Report (`/analysis/{id}`), My Workspace (`/workspace`), New Analysis (POST),
  and Queue Status (`/queue`, admin-only, not in primary nav).
- [x] Keep route handlers thin; use `core/` modules for business logic.

T01 established the route map used by the server-rendered Jinja2 pages.

### T02 · Jinja2 layout and navigation

- [x] Create a base template with a top navigation bar: Research | My Workspace | [user ▾] | [+ Analyze].
  No persistent left sidebar.
- [x] Use server-rendered pages as the primary experience.
- [x] Use HTMX only for targeted partial updates: My Workspace status polling (while rows are
  queued/running), sort/filter changes on the Research table, and retry actions.
- [x] Keep the UI dense, clear, and operational rather than marketing-style.

T02 added the shared app shell, top navigation, initial page templates, static CSS, and HTML route
tests.

### T03 · Analysis and ticker pages

- [x] Research landing: sortable/filterable system-wide stock table (sort by alpha, hit rate,
  recency, ticker; filter by rating, min results, date range); inline sparkline per ticker.
- [x] My Workspace: user-scoped submission list with status badges; HTMX polling while active.
- [x] Ticker Intelligence page: metric tiles, alpha-over-time bar chart, rating calibration
  horizontal bar chart (hidden when fewer than 3 resolved outcomes), analysis history table.
- [x] Analysis Report page: outcome block (stock return, SPY, alpha, correct/missed call) shown only
  when outcome is resolved; summary, thesis, and tabbed evidence sections.
- [x] Include raw return and alpha return side by side in the outcome block.

T03 established the page hierarchy and data structures that T05 renders with Chart.js.

### T04 · Queue controls

- [x] Add New Analysis modal (single ticker + date; reuse detection note when report exists).
  Modal is triggered from the [+ Analyze] button; submits via POST and redirects to My Workspace.
- [x] Add retry action for failed submissions (in My Workspace and Queue Status pages).
- [x] Add Queue Status page (`/queue`): table of queued/running/failed items with HTMX auto-refresh.
  This page is not in primary navigation; link to it from the running-work indicator in My Workspace.
- [x] No batch enqueue form in this milestone.

T04 keeps queue management deliberately narrow: one-stock submission from the modal, shared-report
reuse detection before submit, queue-backed retry buttons, and polling only while work is active.

### T05 · Charts

- [x] System accuracy chart on Research landing: rolling 30-day hit rate line chart (Chart.js,
  CDN, no build pipeline).
- [x] Alpha-over-time bar chart on Ticker Intelligence: one bar per resolved analysis, green/rose
  coloring, 0-line prominent.
- [x] Rating calibration horizontal bar chart on Ticker Intelligence: avg alpha by rating label;
  hidden with a note when fewer than 3 resolved outcomes exist for that ticker.
- [x] Serialize chart data server-side into a `<script>` tag as JSON; no separate API endpoint
  for chart data.
- [x] No separate leaderboard page and no model-performance page; the Research landing is the
  leaderboard.

T05 uses Chart.js from CDN and a small static `charts.js` file. The backend serializes chart
payloads into page-local JSON script tags; there are no separate chart API routes and no JS build
pipeline.

### T06 · Local run docs and tests

- [x] Document `uv run uvicorn ...` or equivalent local startup command.
- [x] Add route tests for core pages and JSON/partial endpoints.
- [x] Add template rendering tests for empty DB and seeded DB states.
- [x] Keep tests network-free and LLM-free.

T06 documents the local web startup flow in `docs/getting-started.md`, updates development
workflow notes for the lightweight chart JavaScript, and adds empty/thin/seeded rendering coverage.

---

## Acceptance Criteria

- [x] UI design is reviewed and accepted before template implementation starts.
- [x] The Research landing shows all analyzed stocks sorted by best alpha, with working sort and
  filter controls and an accuracy-over-time chart.
- [x] Clicking a stock opens the Ticker Intelligence page with alpha bar chart and (when data
  allows) a rating calibration chart.
- [x] Clicking an analysis opens the Analysis Report with outcome block, summary, thesis, and
  tabbed evidence.
- [x] My Workspace shows the current user's submissions with live status and HTMX polling while
  work is active.
- [x] A user can submit a new analysis via the modal and retry a failed submission.
- [x] Empty DB states and thin-data states (e.g. fewer than 3 outcomes) render clearly without
  crashes or empty chart frames.
- [x] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- M06 remains accepted as the `0.0.1` release baseline. Known post-release hardening gaps are
  tracked in [07-milestone.md](07-milestone.md) rather than reopening this milestone.
- Do not introduce a JavaScript build pipeline unless server-rendered templates plus HTMX prove
  insufficient.
- Prefer Chart.js or a similarly small browser-side charting dependency only when charting starts.
- Keep web response structures stable enough that a future API milestone can formalize schemas
  without rewriting the page data model.
