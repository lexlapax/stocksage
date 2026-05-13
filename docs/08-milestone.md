# Milestone 08 — UI Clarity, Guided Help, and Web Queue Operation

## Goal

Make StockSage understandable and operable for non-technical users without requiring a terminal.
M08 turns the post-`0.0.1` manual-testing findings into an implementation-ready scope:

- Explain technical chart and finance terms in the UI.
- Let users run queued LLM analyses from the browser.
- Let users quickly queue a fresh analysis for an already analyzed ticker.

## Status

**Ready for implementation.** Scope is intentionally limited to explanatory and operational UI; no
analytics semantics, authentication, deployment, or multi-user permission model changes.

---

## Product Decisions

- Use the existing FastAPI + Jinja2 + HTMX stack. Do not add a frontend framework.
- Prefer server-rendered controls and partials. Use small vanilla JavaScript only where the current
  modal needs local form prefill behavior.
- Keep queue execution conservative: default to one worker and make paid/live LLM calls explicit.
- Do not promise instant cancellation of live provider calls. The web control is `Stop after current
  job` unless true safe cancellation is explicitly implemented later.
- Reuse canonical queue, submission, worker, and request-history paths. Do not create a second web
  analysis execution model.
- Keep the user model local: no auth, passwords, sessions, or permissions in M08.

## Non-Goals

- No hosted deployment or process supervisor.
- No full user switcher.
- No batch-analysis builder beyond running queued jobs that already exist.
- No changes to alpha/hit-rate/rating semantics.
- No separate API client or SPA.

---

## UX Contract

### Help affordances

Use a compact `?` or info control beside technical terms. Help should be available by mouse,
keyboard, and touch. Preferred first implementation is a reusable `details/summary` pattern styled
as a small popover because it works without JavaScript and is naturally dismissible.

Initial help terms:

| Term | Plain-language explanation |
|------|----------------------------|
| Resolved analysis | An analysis whose outcome has been checked after the holding period. |
| Alpha | The stock return minus the market return over the same period. |
| Positive alpha | The stock beat the market for that period. |
| Negative alpha | The stock underperformed the market for that period. |
| Hit rate | The share of resolved calls StockSage scored correctly by alpha-aware rules. |
| Rolling 30-day hit rate | For each chart date, the percentage of resolved calls from the previous 30 calendar days that were correct. |
| 50% reference line | A baseline showing right about as often as wrong. Above it is better than below it. |
| Average alpha | The average market-relative return across resolved analyses. |
| Raw return | The stock's own return before comparing it with the market. |
| SPY / market return | The market benchmark return used to calculate alpha. |
| Holding period | The number of trading days StockSage waits before checking the outcome. |
| Rating calibration | A view of how each rating label has performed historically. |
| Buy / Overweight / Hold / Underweight / Sell | StockSage's conviction labels, scored against future alpha after resolution. |

Placement:

- Research metric cards: Stocks analyzed, Avg hit rate, Avg alpha, Running.
- Research chart: System accuracy over time, Rolling 30-day hit rate, 50% reference line.
- Research table: Reports, Checked, Hit rate, Avg alpha, Trend.
- Ticker Intelligence: Results checked, Hit rate, Avg alpha, Alpha vs market, rating calibration.
- Analysis Report: Stock return, SPY, Alpha, Correct/Missed call, rating labels.

### Web queue operation

Queue Status becomes the operational place to run LLM work from the browser. It should include:

- Runner state banner: `Idle`, `Running`, `Stopping after current job`, `Paused`, `Blocked`, or
  `Finished`.
- Run controls: `Run next 1`, `Run next 5`, `Run all queued`.
- Optional advanced control: max workers, default `1`, hidden behind an advanced disclosure.
- Stop control: `Stop after current job`.
- Retry controls for failed jobs and failed-only batch retry.
- Clear copy that running analyses makes live LLM and market-data calls and may cost money.
- HTMX polling for runner state and job rows while active.

Honest stop behavior:

- A stop request prevents the runner from claiming another queued job.
- An already-running LLM call is allowed to finish and then records completed/failed state normally.
- If the server process dies, stale running jobs continue to use the existing stale reset behavior.

### Quick re-analysis

The Research `Analyzed stocks` table and Ticker Intelligence page should let users queue a fresh
analysis without retyping the ticker.

- Research row action: `Analyze again` or `Queue today`.
- Ticker page action: `Analyze today`.
- Reuse the existing `Analyze a stock` modal.
- Pre-fill ticker and default date to today.
- Keep reuse detection so the user sees whether today's analysis already exists, is queued/running,
  or will create new LLM work.
- Preserve existing ticker links to Ticker Intelligence.

---

## Technical Design

### Help component

Preferred implementation:

- Add a reusable Jinja macro, for example `web/templates/macros/help.html`.
- Store help copy in one place. Acceptable first pass: macro arguments in templates. Better pass:
  `api/help_text.py` with a dictionary keyed by stable term ids.
- Style `.help-term`, `.help-trigger`, and `.help-popover` in `web/static/styles.css`.
- Keep content short. Link to docs only if a term truly needs more room.
- Add route/template tests that representative help controls render with accessible labels.

### Queue runner control

The current CLI uses `worker.runner.run_queued_jobs()`. For web controls, use the same worker
building blocks but add a controller that can report state and stop between jobs.

Recommended implementation shape:

- Add a persisted run record via Alembic, likely `queue_runs`.
- Add `core/queue_runs.py` for run creation, state transitions, duplicate-run protection, and stop
  requests.
- Add `worker/controller.py` or `worker/web_runner.py` that:
  - starts one background thread per accepted run;
  - repeatedly calls `worker.runner.process_next_job()`;
  - checks `queue_runs.stop_requested_at` between jobs;
  - updates attempted/completed/failed/skipped counts;
  - marks the run `finished`, `stopped`, `failed`, or `blocked`.
- Keep CLI `queue run` behavior unchanged unless sharing helpers is low-risk.

Suggested `queue_runs` fields:

| Column | Notes |
|--------|-------|
| id | integer primary key |
| status | queued / running / stopping / stopped / finished / failed / blocked |
| requested_limit | nullable integer; null means all currently queued |
| max_workers | integer, default 1 |
| started_by_user_id | nullable FK to users |
| started_at | datetime |
| heartbeat_at | datetime; updated between jobs |
| stop_requested_at | nullable datetime |
| completed_at | nullable datetime |
| attempted | integer |
| completed | integer |
| failed | integer |
| skipped | integer |
| last_error | nullable text |

Duplicate-run rule:

- Only one `running` or `stopping` queue run may exist for the local app.
- If a user clicks Run while a run is active, show the active run instead of starting another one.
- On app startup/status read, if a persisted run says `running` but no local runner thread exists,
  mark it `blocked` or `failed` with a clear "server restarted" message and rely on stale queue
  reset for jobs.

Routes and partials:

- `POST /queue/run` starts a run.
- `POST /queue/run/stop` requests stop after current job.
- `GET /queue/partials/runner` returns the runner state/control panel.
- Existing `GET /queue/partials/jobs` continues to return job rows.
- Existing retry routes remain, plus optional `POST /queue/retry-failed`.

### Quick re-analysis implementation

Preferred implementation:

- Add row-level action buttons with `data-analysis-ticker` and optional `data-analysis-date`.
- Add a small vanilla JS helper in the base template or a new static file to prefill:
  - `#analysis-ticker`
  - `#analysis-date`
  - `Run as` remains current user
- Trigger the existing reuse-note HTMX check after prefill.
- No new POST path should be needed; submit continues to use `POST /analysis`.
- If JavaScript is unavailable, the action may still open the modal without prefill as an acceptable
  fallback.

---

## Task List

### T00 · Finalize M08 UI primitives

- [ ] Add reusable help macro/component.
- [ ] Add shared CSS for inline help and queue runner controls.
- [ ] Decide whether help copy lives in template macro arguments or a Python dictionary.
- [ ] Add test helpers for asserting accessible help controls.

### T01 · Add popup help for technical chart and finance terms

- [ ] Add help affordances for the initial term inventory above.
- [ ] Explain each term in plain language for a non-technical user.
- [ ] Cover Research, Ticker Intelligence, Analysis Report, and Queue Status where relevant.
- [ ] Make help accessible by mouse, keyboard, and touch.
- [ ] Keep default UI quiet and avoid crowding charts/tables.
- [ ] Add route/template tests for representative help controls.

### T02 · Add persisted queue run state

- [ ] Add Alembic migration for `queue_runs`.
- [ ] Add ORM model and core helper module for queue run lifecycle.
- [ ] Enforce one active run at a time.
- [ ] Add stop-request state transitions.
- [ ] Add tests for run creation, duplicate protection, state updates, and stop request persistence.

### T03 · Add browser queue runner controls

- [ ] Add Queue Status runner panel with `Run next 1`, `Run next 5`, `Run all queued`, and
  `Stop after current job`.
- [ ] Add FastAPI routes/partials for starting, stopping, and polling runner state.
- [ ] Run jobs in a background thread using existing worker job processing.
- [ ] Update job and runner partial polling while a run is active.
- [ ] Add failed-job retry and optional retry-all-failed controls.
- [ ] Add route/service tests using stubbed analyzer/worker behavior; no live LLM/network calls.

### T04 · Add quick re-analysis actions

- [ ] Add `Analyze again` or `Queue today` action to Research table rows.
- [ ] Add `Analyze today` action to Ticker Intelligence.
- [ ] Reuse and pre-fill the existing `Analyze a stock` modal.
- [ ] Trigger reuse detection after prefill.
- [ ] Preserve ticker navigation and existing submission behavior.
- [ ] Add tests for action presence, prefill hooks, and reuse-note compatibility.

### T05 · Documentation and verification

- [ ] Update `README.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/plan.md`, and
  `docs/getting-started.md` for M08 behavior.
- [ ] Document the difference between queueing work and running queued LLM work.
- [ ] Document stop semantics as "after current job."
- [ ] Run stale-reference scans for old M08 collecting/planning wording.
- [ ] Run full quality gate.

---

## Acceptance Criteria

- [ ] A non-technical user can discover what each chart/metric means in the UI.
- [ ] Help content appears near the term being explained and can be dismissed.
- [ ] Help controls work with keyboard focus and screen-reader labels.
- [ ] Mobile layouts do not overlap or hide help content.
- [ ] A non-technical user can queue an analysis and run it with LLMs from the web UI.
- [ ] Queue Status clearly shows runner state and job progress.
- [ ] Pause/stop controls have honest semantics and do not corrupt in-flight analyses.
- [ ] The web UI prevents duplicate queue runners from starting accidentally.
- [ ] A user can start another analysis for an already analyzed ticker without retyping the ticker.
- [ ] Quick re-analysis defaults to today's date and still warns when work would be reused.
- [ ] No tests make live LLM or network calls.
- [ ] `node --check web/static/charts.js`, `uv run ruff check .`,
  `uv run ruff format --check .`, and `uv run pytest` pass.

## Manual Test Plan

1. Start the web app and open Research.
2. Confirm help controls explain System accuracy, rolling 30-day hit rate, 50% line, alpha, hit
   rate, and resolved analysis.
3. Use a Research row action to open the Analyze modal prefilled for that ticker and today's date.
4. Submit the modal and confirm My Workspace/Queue Status show the queued request.
5. Open Queue Status and run `Run next 1`.
6. Confirm runner state changes to running and job rows auto-refresh.
7. Request `Stop after current job` and confirm no additional jobs are claimed after the current one.
8. Retry a failed job from Queue Status.
9. Confirm all pages still render on mobile-sized viewport.

## Verification Plan

```bash
node --check web/static/charts.js
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Docs/stale scans:

```bash
rg "collecting findings|M08 collecting|No unreleased changes" README.md AGENTS.md CHANGELOG.md docs/plan.md
rg "Run next 1|Stop after current job|Analyze again|rolling 30-day" docs/08-milestone.md
git diff --check
```

## Notes

- Queue running from the browser should reuse the existing worker path rather than creating a
  second execution model.
- Quick re-analysis should reuse the existing modal/submission path so queue attribution and reuse
  detection stay consistent.
- If more manual-testing findings arrive before implementation starts, add them as new M08 tasks
  only if they fit UI clarity or browser operation. Otherwise, create an M09 candidate section.
