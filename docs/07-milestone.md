# Milestone 07 — Hardening & Polish

## Goal

Close the implementation gaps, UX polish issues, and documentation inconsistencies left from the
`0.0.1` baseline. No new product scope. The milestone is complete when every item from the gap
analysis below is resolved and the full quality gate still passes.

## Status

**Accepted.** All tasks are implemented, tested, documented, and ready for the retagged `0.0.1`
release commit.

---

## Gap Analysis

These gaps were found by comparing the accepted M01-M06 milestone specs against the current
implementation, docs, and tests.

### Critical — user-facing behavior or accepted scope mismatch

**G3 · Research landing hides completed-but-unresolved analyses**
`api/services.py` builds the Research page from `_filtered_resolved_rows`, which inner-joins
`Outcome`. A user who has just completed analyses sees no Research rows until outcomes are
resolved about five trading days later. Research must show completed analyses immediately, while
pending outcome/alpha values render as pending and are excluded from hit-rate/alpha calculations.

**G1 · Evidence tabs are not interactive**
`web/templates/analysis.html` renders all evidence sections simultaneously in a two-column grid.
The tab links are in-page anchors rather than real tab controls, so long reports force users to
scroll through every section. M06 accepted “tabbed evidence sections”; M07 must make that true.

**G2 · Research filters reload the whole page instead of updating a partial**
M06 T02 specified targeted HTMX updates for Research sort/filter changes. The implementation uses
a full-page GET form. The controls work, but the accepted implementation contract is missing the
Research table partial.

### Significant — usability blockers or confusing UI

**G4 · No UI path to `/queue` when work is not active**
My Workspace links to Queue Status only when `has_active_work` is true. If the queue is idle,
completed, or failed-only, `/queue` is reachable only by manually editing the URL.

**G5 · `user ▾` pill implies an unavailable dropdown**
The top-bar user label includes a caret, but there is no dropdown or user switcher. Until a real
switcher exists, the label should be static and the docs should explain the current local-user
behavior.

### Code quality and consistency

**G6 · Dead `_sort_ticker_stats` helper**
`api/services.py` still defines `_sort_ticker_stats`, but Research uses `_sort_research_rows`.
Remove the unused helper.

**G7 · FastAPI metadata reports the wrong version**
`api/app.py` hardcodes an old pre-release version while the release and package version are
`0.0.1`. The OpenAPI metadata should come from installed package metadata so it stays in sync.

**G8 · Changelog release date does not match the tag date**
The `0.0.1` tag was created on May 12, 2026, while `CHANGELOG.md` records May 13, 2026.

### Documentation

**G9 · Getting Started contains a machine-specific project path**
`docs/getting-started.md` uses a developer-local absolute path; public setup docs should use
`cd <path-to-stocksage>`.

**G10 · Plan includes private local-path metadata**
The `docs/plan.md` design-decision table includes a “Project root” row with private machine
metadata. That is not an architecture decision and should be removed.

**G11 · API schema docs are premature/inconsistent**
There is no tracked API schema module, and M06 currently serves HTML plus minimal JSON health
metadata rather than a typed API surface. Do not add placeholder schemas in M07. Instead, remove or
soften “Pydantic schemas” promises from `AGENTS.md` and keep future API-schema work for a later API
milestone.

**G14 · Web user attribution is under-documented**
The app defaults to the current OS username, the modal has a `Run as` field, and `/workspace` can
be scoped with `?user=alice`, but `docs/getting-started.md` does not explain that local user model.

**G15 · M06 docs need a post-release hardening note**
M06 remains accepted as the `0.0.1` release baseline. Add a short note pointing to M07 for known
post-release hardening gaps rather than reopening or unaccepting M06.

### Test coverage

**G12 · No test for `date_range` filtering on Research**
`tests/test_api.py` exercises rating filtering but not `?date_range=30` or `?date_range=90`.

**G13 · No test for Analysis Report without `AnalysisDetail`**
The template falls back to “No evidence stored.” when detail text is missing, but no test confirms
an analysis without an `AnalysisDetail` row renders cleanly.

---

## Task List

### T01 · Show completed-but-unresolved analyses on Research (G3)

- [x] Query all completed analyses for the Research table, not only rows with outcomes.
- [x] Exclude unresolved rows from hit-rate, average-alpha, trend, and chart calculations.
- [x] Render unresolved table metrics as `Pending` or `-`, and keep those tickers clickable.
- [x] Add a test proving a completed analysis without an outcome appears on Research.

### T02 · Make evidence tabs real tabs (G1)

- [x] Replace the always-visible evidence grid with one visible panel at a time.
- [x] Use accessible tab semantics (`role="tablist"`, `role="tab"`, `role="tabpanel"`) and no JS
  framework.
- [x] Default the Market tab/panel open on page load.
- [x] Add/adjust a route test that verifies the tab structure and hidden/deferred panels render.

### T03 · Add HTMX Research table partial (G2)

- [x] Extract the ticker table into `web/templates/partials/research_tickers.html`.
- [x] Add a partial route for Research table updates.
- [x] Wire sort/filter controls with HTMX targeting the table partial while preserving full-page
  GET fallback.
- [x] Add a test for the partial endpoint and at least one filtered response.

### T04 · Fix queue navigation and user-label affordance (G4, G5)

- [x] Add a low-profile Queue Status link from My Workspace that is always visible and stays out
  of the primary nav.
- [x] Remove the caret from the static user pill until a real switcher exists.
- [x] Update tests/docs affected by the label and queue-link behavior.

### T05 · Clean code and version metadata (G6, G7)

- [x] Remove dead `_sort_ticker_stats` code.
- [x] Read FastAPI `version` from `importlib.metadata.version("stocksage")`.
- [x] Add a test asserting `/openapi.json` reports `"version": "0.0.1"`.

### T06 · Docs cleanup (G8-G11, G14, G15)

- [x] Fix the `CHANGELOG.md` `0.0.1` date to `2026-05-12`.
- [x] Replace machine-specific setup paths with placeholders.
- [x] Remove the private project-root row from `docs/plan.md`.
- [x] Remove/soften “Pydantic schemas” wording where it implies implemented schemas.
- [x] Document web user attribution: OS default, modal `Run as`, and `/workspace?user=alice`.
- [x] Add an M06 note that M07 tracks known post-release hardening gaps while M06 stays accepted.

### T07 · Fill test coverage gaps (G12, G13)

- [x] Add `test_research_landing_respects_date_range_filter`.
- [x] Add `test_analysis_report_without_detail_renders_placeholders`.

---

## Acceptance Criteria

- [x] Research shows completed analyses before outcomes are resolved.
- [x] Evidence sections behave as real one-panel-at-a-time tabs.
- [x] Research sort/filter changes can update the table through HTMX without replacing the whole
  page, with full-page fallback still working.
- [x] Queue Status is reachable from the UI even when no work is active.
- [x] The static user label no longer implies a dropdown.
- [x] `/openapi.json` reports `"version": "0.0.1"`.
- [x] Setup and plan docs have no private machine path.
- [x] Docs no longer imply implemented Pydantic API schemas.
- [x] Web user attribution is documented for local use.
- [x] `node --check web/static/charts.js`, `uv run ruff check .`,
  `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- M07 corrects accepted-scope gaps and polish issues from `0.0.1`; it should not add new product
  areas like authentication, deployment, or a full user switcher.
- M06 remains accepted as the first release baseline. M07 is the hardening milestone that makes the
  accepted web experience match its intent more closely.
- Likely M08 candidates are a real user switcher, authentication groundwork, or server deployment
  docs.
