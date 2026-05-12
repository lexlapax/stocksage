# Milestone 03 — Accuracy Semantics + TradingAgents Memory Sync

## Goal

Make StockSage's accuracy metrics portfolio-correct and ensure resolved DB outcomes become usable
learning context for future TradingAgents runs.

Milestone 02 proved the mechanics work, but the 20-stock validation showed that raw-direction
accuracy is not enough for a five-tier rating system. Overweight and Underweight are relative
allocation calls, so alpha versus benchmark must become the default correctness signal.

No async worker yet. No web UI yet.

## Status

**Planned.** This is the next active milestone after the M01/M02 validation pass.

---

## Prerequisites

- Milestone 01 accepted.
- Milestone 02 accepted with at least 20 resolved analyses.
- Existing TradingAgents memory log path remains configured through `Settings.memory_log_path`.

---

## Task List

### T01 · Alpha-aware correctness semantics

- [ ] Rename the current raw-return helper to `is_correct_raw_direction()`.
- [ ] Add `is_correct_alpha_direction(rating, alpha_return)`.
- [ ] Treat Buy/Overweight as alpha-correct when `alpha_return > 0`.
- [ ] Treat Sell/Underweight as alpha-correct when `alpha_return < 0`.
- [ ] Treat Hold as alpha-correct when `abs(alpha_return) < 0.02`.
- [ ] Keep raw-direction correctness available as a secondary diagnostic.

### T02 · Trend dataclass updates

- [ ] Add alpha-direction accuracy fields to ticker and model stats.
- [ ] Keep raw-direction accuracy fields for comparison.
- [ ] Make alpha-direction accuracy the default `directional_accuracy` used by CLI tables.
- [ ] Preserve average raw return, average alpha return, and per-rating return breakdowns.

### T03 · CLI metric display

- [ ] Update `summary` to label alpha-based accuracy clearly.
- [ ] Show raw correctness and alpha correctness for recent analyses where useful.
- [ ] Update `leaderboard` to sort by alpha-direction accuracy for `--by accuracy`.
- [ ] Keep `--by alpha` as average alpha return.
- [ ] Update `models` to report alpha-direction accuracy.

### T04 · TradingAgents memory sync

- [ ] Add a DB-to-memory sync helper that writes resolved StockSage outcomes into the configured
  TradingAgents markdown memory log.
- [ ] Reconstruct the original final decision from `AnalysisDetail.full_state_json` when possible.
- [ ] Fall back to stored `rating`, `executive_summary`, and `investment_thesis` if raw final state
  is unavailable.
- [ ] Make sync idempotent: running it twice must not duplicate entries.
- [ ] Run sync after `stocksage resolve`.
- [ ] Run sync before `stocksage analyze` so future analyses receive resolved lessons via
  TradingAgents' existing `past_context`.

### T05 · Tests

- [ ] Add tests for raw versus alpha correctness, including PLTR-style cases.
- [ ] Add tests proving CLI stats default to alpha-direction accuracy.
- [ ] Add tests for memory sync creation, pending-entry resolution, and idempotency.
- [ ] Keep tests network-free and LLM-free.

---

## Acceptance Criteria

- [ ] PLTR-style Underweight with positive raw return but negative alpha is alpha-correct.
- [ ] Overweight with positive raw return but negative alpha is alpha-wrong.
- [ ] `stocksage leaderboard --by accuracy` ranks by alpha-direction accuracy.
- [ ] `stocksage models` reports alpha-direction accuracy.
- [ ] Resolved DB outcomes appear as resolved entries in the TradingAgents memory log.
- [ ] A future `stocksage analyze TICKER` can consume prior resolved lessons through existing
  TradingAgents memory context.
- [ ] `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest` pass.

---

## Notes

- Do not tune model/provider/debate-depth in this milestone. First make the metric and memory loop
  trustworthy.
- Do not change the database schema unless implementation proves the memory sync needs durable
  bookkeeping. Prefer idempotency from existing analysis IDs, tickers, dates, and memory-log tags.
