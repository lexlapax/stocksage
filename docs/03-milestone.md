# Milestone 03 — Accuracy Semantics + TradingAgents Memory Sync

## Goal

Make StockSage's accuracy metrics portfolio-correct and ensure resolved DB outcomes become usable
learning context for future TradingAgents runs.

Milestone 02 proved the mechanics work, but the 20-stock validation showed that raw-direction
accuracy is not enough for a five-tier rating system. Overweight and Underweight are relative
allocation calls, so alpha versus benchmark must become the default correctness signal.

Async worker and web UI work were intentionally out of scope for this milestone.

## Status

**Accepted.** Alpha-aware accuracy, raw-vs-alpha CLI display, TradingAgents memory sync, and
network-free tests are complete.

Validation completed on 2026-05-12 with `uv run ruff check .` and `uv run pytest`.

---

## Prerequisites

- Milestone 01 accepted.
- Milestone 02 accepted with at least 20 resolved analyses.
- Existing TradingAgents memory log path remains configured through `Settings.memory_log_path`.

---

## Task List

### T01 · Alpha-aware correctness semantics

- [x] Rename the current raw-return helper to `is_correct_raw_direction()`.
- [x] Add `is_correct_alpha_direction(rating, alpha_return)`.
- [x] Treat Buy/Overweight as alpha-correct when `alpha_return > 0`.
- [x] Treat Sell/Underweight as alpha-correct when `alpha_return < 0`.
- [x] Treat Hold as alpha-correct when `abs(alpha_return) < 0.02`.
- [x] Keep raw-direction correctness available as a secondary diagnostic.

### T02 · Trend dataclass updates

- [x] Add alpha-direction accuracy fields to ticker and model stats.
- [x] Keep raw-direction accuracy fields for comparison.
- [x] Make alpha-direction accuracy the default `directional_accuracy` used by CLI tables.
- [x] Preserve average raw return, average alpha return, and per-rating return breakdowns.

### T03 · CLI metric display

- [x] Update `summary` to label alpha-based accuracy clearly.
- [x] Show raw correctness and alpha correctness for recent analyses where useful.
- [x] Update `leaderboard` to sort by alpha-direction accuracy for `--by accuracy`.
- [x] Keep `--by alpha` as average alpha return.
- [x] Update `models` to report alpha-direction accuracy.

### T04 · TradingAgents memory sync

- [x] Add a DB-to-memory sync helper that writes resolved StockSage outcomes into the configured
  TradingAgents markdown memory log.
- [x] Reconstruct the original final decision from `AnalysisDetail.full_state_json` when possible.
- [x] Fall back to stored `rating`, `executive_summary`, and `investment_thesis` if raw final state
  is unavailable.
- [x] Make sync idempotent: running it twice must not duplicate entries.
- [x] Run sync after `stocksage resolve`.
- [x] Run sync before `stocksage analyze` so future analyses receive resolved lessons via
  TradingAgents' existing `past_context`.

### T05 · Tests

- [x] Add tests for raw versus alpha correctness, including PLTR-style cases.
- [x] Add tests proving CLI stats default to alpha-direction accuracy.
- [x] Add tests for memory sync creation, pending-entry resolution, and idempotency.
- [x] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [x] PLTR-style Underweight with positive raw return but negative alpha is alpha-correct.
- [x] Overweight with positive raw return but negative alpha is alpha-wrong.
- [x] `stocksage leaderboard --by accuracy` ranks by alpha-direction accuracy.
- [x] `stocksage models` reports alpha-direction accuracy.
- [x] Resolved DB outcomes appear as resolved entries in the TradingAgents memory log.
- [x] A future `stocksage analyze TICKER` can consume prior resolved lessons through existing
  TradingAgents memory context.
- [x] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Do not tune model/provider/debate-depth in this milestone. First make the metric and memory loop
  trustworthy.
- Do not change the database schema unless implementation proves the memory sync needs durable
  bookkeeping. Prefer idempotency from existing analysis IDs, tickers, dates, and memory-log tags.
