# Milestone 02 — Memory & Trending Engine

## Goal

Make StockSage learn from its own prediction history. After Milestone 1 we have a pile of analyses
in SQLite; Milestone 2 turns that pile into signal:

1. **Per-ticker accuracy** — how often are BUY/SELL/HOLD calls directionally correct?
2. **Rating calibration** — does "Buy" actually outperform "Overweight" in realised returns?
3. **Model performance** — which LLM provider/model produces better predictions?
4. **Trending** — is accuracy improving or degrading over time?
5. **Cross-ticker lessons** — surface patterns across sectors or market regimes

No web server yet. Everything is exposed through new CLI commands and a structured report.

## Status

**Code complete.** The trend dataclasses/functions, enhanced `summary`, `leaderboard`, `models`,
cross-ticker lessons, resolve status reporting, and automated tests are implemented.

**Remaining before declaring the milestone fully accepted:** validate the output against a real
dataset with at least 10-20 resolved analyses.

---

## Prerequisites

- Milestone 01 complete and `stocksage.db` has at least 10–20 resolved analyses
  (analyses where `outcomes` rows exist with `raw_return`, `alpha_return`)

---

## Task List

### T01 · Trends module (`core/trends.py`)

This module queries the DB and returns Python dataclasses — no printing, no side effects.

#### `TickerStats`
```python
@dataclass
class TickerStats:
    ticker: str
    total_analyses: int
    resolved_count: int          # has Outcome
    directional_accuracy: float  # % of buy/sell calls where direction was correct
    avg_raw_return: float
    avg_alpha_return: float
    avg_return_by_rating: dict[str, float]   # e.g. {"Buy": 0.032, "Hold": 0.005}
    accuracy_trend: list[tuple[date, bool]]  # (trade_date, was_correct) time-ordered
```

#### `ModelStats`
```python
@dataclass
class ModelStats:
    llm_provider: str
    deep_model: str
    total_analyses: int
    resolved_count: int
    avg_alpha_return: float
    directional_accuracy: float
```

#### Functions

```python
def get_ticker_stats(db: Session, ticker: str) -> TickerStats | None:
    """Query all resolved analyses for ticker and compute stats."""

def get_all_ticker_stats(db: Session) -> list[TickerStats]:
    """Stats for every ticker that has at least one resolved analysis."""

def get_model_stats(db: Session) -> list[ModelStats]:
    """Group by (llm_provider, deep_model) and compute accuracy."""

def get_accuracy_trend(
    db: Session, ticker: str, window: int = 10
) -> list[tuple[date, float]]:
    """Rolling accuracy over last `window` analyses, time-ordered."""

def is_correct_direction(rating: str, raw_return: float) -> bool:
    """
    Buy/Overweight → correct if raw_return > 0
    Sell/Underweight → correct if raw_return < 0
    Hold → correct if abs(raw_return) < 0.02 (within 2%)
    """
```

**Status:** Done in `core/trends.py`, with tests in `tests/test_trends.py`.

---

### T02 · Enhanced `summary` CLI command

Extend the existing `summary TICKER` command with trend data.

**New output format:**
```
══════════════════════════════════════════
 StockSage Summary: AAPL  (12 analyses)
══════════════════════════════════════════

Resolved: 9/12   Directional accuracy: 67%
Avg raw return:   +2.1%   Avg alpha: +0.8%

By rating:
  Buy         5 calls   avg +3.4%  ✓ 80%
  Hold        3 calls   avg +0.6%  ✓ 67%
  Sell        1 call    avg -1.2%  ✓ 100%

Accuracy trend (last 9):  ✓ ✗ ✓ ✓ ✗ ✓ ✓ ✓ ✓

Recent analyses:
Date        Rating     Raw     Alpha  Correct  Reflection snippet
2026-05-01  Buy       +3.2%   +1.1%  ✓        "Momentum call was right..."
2026-04-15  Hold      -0.8%   -0.2%  ✓        "Cautious stance appropriate..."
2026-03-30  Buy       -2.1%   -1.5%  ✗        "Overweighted near-term catalyst..."
```

**Status:** Done in `stocksage/cli.py`. The CLI now prints resolved counts, directional accuracy,
average returns, rating breakdowns, trend markers, and recent-analysis correctness.

---

### T03 · New CLI command: `leaderboard`

```
stocksage leaderboard [--by accuracy|alpha|count] [--min-resolved N]
```

Prints a ranked table of all tickers by chosen metric. Filters out tickers with fewer than
`--min-resolved` (default 3) resolved outcomes to avoid noise from single-analysis tickers.

```
Rank  Ticker  Resolved  Accuracy  Avg Alpha  Best Rating
 1    NVDA      8        87%       +2.3%      Buy
 2    AAPL      9        67%       +0.8%      Buy
 3    MSFT      5        60%       +0.4%      Overweight
```

**Status:** Done in `stocksage/cli.py`.

---

### T04 · New CLI command: `models`

```
stocksage models
```

Prints a table grouped by (provider, deep_model):
```
Provider   Model         Analyses  Resolved  Accuracy  Avg Alpha
openai     gpt-5.4           18       14        71%      +1.2%
anthropic  claude-opus-4-7    4        2        50%      +0.1%
```

**Status:** Done in `stocksage/cli.py`.

---

### T05 · Cross-ticker insights

Add a `get_cross_ticker_lessons(db, n=5)` function in `core/trends.py` that returns a
formatted string of the most recent resolved analyses across all tickers, similar to what
`TradingMemoryLog.get_past_context` does for the library's own prompt injection.

This is the building block for feeding StockSage's own historical performance back into
the Portfolio Manager prompt — a "meta-memory" layer that goes beyond the single-ticker
reflections the library already provides.

**How to inject:** Pass the output as part of the `past_context` that gets added to the
Portfolio Manager's system prompt. The library already has a hook for this via
`TradingMemoryLog.get_past_context()` — but StockSage can supplement it by pre-populating
the markdown memory log from DB records (a one-way sync at analysis start).

**Status:** `get_cross_ticker_lessons()` is done. Prompt injection/backfill into TradingAgents
memory is still future work.

---

### T06 · `resolve` command improvements

The existing `resolve` command (Milestone 01) resolves outcomes one at a time. Upgrade it:

- **Batch resolve:** Fetch returns for all pending tickers in one yfinance batch call
  (use `yf.download(tickers=[...])` with a shared date range) to reduce API calls
- **Status report:** After resolving, print a summary of what was resolved and what is
  still pending (with reason: "too recent", "insufficient price data", etc.)
- **Force flag:** `--force` re-resolves already-resolved analyses (useful for correcting errors)

**Status:** Done. `resolve` now reports attempted, too recent, already resolved, and insufficient
price-data counts, and `--force` updates existing outcomes in place.

---

### T07 · Persistence of trends (optional, implement if needed)

If the DB grows large (thousands of analyses), computing stats on every `summary` call becomes
slow. Add a `trend_cache` table:

```python
class TrendCache(Base):
    __tablename__ = "trend_cache"
    id, ticker, computed_at
    directional_accuracy: Float
    avg_raw_return: Float
    avg_alpha_return: Float
    resolved_count: Integer
```

Invalidate and recompute when a new `Outcome` is written for a ticker. Keep this optional —
only add it if query latency becomes noticeable (>1 second for `leaderboard`).

**Status:** Not implemented by design. Current analytics are computed on demand; add this only
after query latency is measurable on a larger dataset.

---

### T08 · Tests

Write at least one test per public function in `core/trends.py`:

```
tests/
├── conftest.py          # in-memory SQLite session + test fixtures
├── test_trends.py       # TickerStats, ModelStats, accuracy calcs
└── test_outcomes.py     # is_correct_direction edge cases
```

Use `pytest` + an in-memory SQLite DB (`sqlite:///:memory:`). Seed with a handful of
`Analysis` + `Outcome` rows. No live network calls, no LLM calls.

**Status:** Done. Added `tests/test_trends.py` plus CLI/outcome tests for Milestone 02 behavior.

---

## Dependencies added in Milestone 02

No new runtime dependencies beyond Milestone 01. Tests require:
```toml
[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-cov>=5.0"]
```

---

## Acceptance Criteria

- [x] `stocksage summary AAPL` shows accuracy stats, trend line, per-rating breakdown
- [x] `stocksage leaderboard` ranks all tickers with resolved outcomes
- [x] `stocksage models` shows per-model accuracy
- [x] `stocksage resolve` resolves in a single yfinance batch call
- [x] `pytest tests/` passes with >90% coverage on `core/trends.py`
- [x] `get_cross_ticker_lessons()` returns formatted string usable as LLM prompt context
- [x] Ruff lint and format checks pass before release prep

**Remaining validation:** run these commands against a real DB with multiple resolved outcomes
once Milestone 01 has produced enough live analyses.

---

## Files Modified / Created

```
core/
└── trends.py               ← new

stocksage/
└── cli.py                  ← add leaderboard, models commands; enhance summary

cli/
└── main.py                 ← compatibility wrapper

tests/
├── conftest.py             ← new
├── test_cli.py             ← CLI helper and seeded-output coverage
├── test_trends.py          ← new
└── test_outcomes.py        ← new
```

---

## Notes for Future Milestones

- Milestone 03 (Async Queue): The worker polls `analysis_queue`, runs `Analyzer.run()` in a
  `ThreadPoolExecutor`, and writes results via the same `core/db.py` session. The trends module
  is already DB-native so nothing changes there.

- Milestone 04 (Web UI): FastAPI routes will call `get_ticker_stats()`, `get_all_ticker_stats()`,
  and `get_model_stats()` directly. The Jinja2 templates receive these dataclasses as template
  context. No additional data layer needed.

- Milestone 05 (Charts): `accuracy_trend` already returns `list[tuple[date, float]]` — the web
  layer just needs to serialize it to JSON for the chart library (Chart.js or similar).
