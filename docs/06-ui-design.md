# Milestone 06 UI Design

## Design Philosophy

StockSage is a research platform with two distinct views that serve different user needs:

**System view ("Research")** — what has StockSage analyzed across all users, and how has it
performed? This is the primary landing experience. It should feel like walking into a research
firm's knowledge base: sortable, chart-rich, and centered on investment insight. A visitor who
has never submitted anything can still learn from it.

**User view ("My Workspace")** — what did *I* submit and what is the status? This is a personal
inbox, not a dashboard. It should be minimal, status-focused, and require no performance
interpretation. Users come here to check "is it done?" and click through to read the result.

These are separate screens with separate navigation entries. The design never conflates them.

---

## Plain-Language Product Terms

| Internal concept | UI label | Notes |
|------------------|----------|-------|
| Analysis (canonical) | Research report | One per ticker/date, shared |
| AnalysisRequest row | My submission | User's personal record |
| Rating | Rating | Buy / Overweight / Hold / Underweight / Sell |
| alpha_return | Alpha vs market | Return minus SPY over same period |
| raw_return | Stock return | Actual price change |
| Outcome resolved | Result checked | Outcome row exists |
| Hit | Beat market | Alpha > 0 |
| AnalysisQueue status | Work status | Queued → Running → Done / Failed |
| Model/provider | Research quality | Advanced detail, not first-screen |

---

## Navigation

Top bar, always visible. No persistent left sidebar — this is a research tool, not an OS.

```text
┌──────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze] │
└──────────────────────────────────────────────────────────────────────┘
```

- **Research** — system view, the landing screen
- **My Workspace** — user-scoped submissions and status
- **[Alice ▾]** — user switcher (no auth yet; simple dropdown)
- **[+ Analyze]** — always-visible primary action; opens the New Analysis form

Queue status is not a primary nav item. Running work is surfaced as a live indicator inside
My Workspace, not its own top-level screen.

---

## Screen 1: Research (System View) — Primary Landing

Purpose: Show everything StockSage has analyzed, with the best-performing stocks on top by
default. A non-technical investor should immediately understand which stocks StockSage has
been right about and which it has not.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Research                                                                     │
│ StockSage's full analysis history — sorted by best alpha vs market           │
│                                                                              │
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────┐ │
│ │ Stocks analyzed  │ │  Avg hit rate    │ │ Avg alpha        │ │ Running  │ │
│ │ 47               │ │  68%             │ │ +1.4% vs market  │ │ 2        │ │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────┘ │
│                                                                              │
│ Accuracy over time (last 90 days)                                            │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │  line chart: rolling 30-day hit rate (% of resolved calls that beat      │ │
│ │  market). X axis = analysis date. Y axis = 0–100%. Zero line at 50%.     │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Analyzed stocks                    Sort: [Best alpha ▾]                      │
│ Filter: [Rating ▾]  [Min results ▾]  [Date range ▾]                         │
│                                                                              │
│ ┌──────┬──────────────┬────────────┬───────┬──────────┬───────────┬───────┐ │
│ │Ticker│ Last rating  │ Analyzed   │ Calls │ Hit rate │ Avg alpha │ Trend │ │
│ ├──────┼──────────────┼────────────┼───────┼──────────┼───────────┼───────┤ │
│ │GOOGL │ Overweight   │ May 8      │ 8     │ 75%      │ +3.2%     │ ▁▃▅▇▆ │ │
│ │AAPL  │ Overweight   │ May 1      │ 12    │ 70%      │ +1.8%     │ ▃▄▅▄▆ │ │
│ │MSFT  │ Hold         │ Apr 30     │ 6     │ 50%      │ +0.3%     │ ▄▃▃▄▃ │ │
│ │NVDA  │ Underweight  │ Apr 24     │ 5     │ 40%      │ -1.2%     │ ▅▄▃▂▁ │ │
│ └──────┴──────────────┴────────────┴───────┴──────────┴───────────┴───────┘ │
│   (click any row → Ticker Intelligence page)                                 │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Sort options** (dropdown, single-select):
- Best alpha vs market (default)
- Highest hit rate
- Most analyses
- Most recently analyzed
- Ticker A–Z

**Filter options:**
- Rating: Buy / Overweight / Hold / Underweight / Sell / Any
- Minimum results: 1 / 3 / 5 / 10 (exclude tickers with too little data)
- Date range: last 30 / 90 / 180 days / all time

**Trend column:** inline sparkline (small bar chart) showing the last 6 alpha values for that
ticker, oldest → newest. Gives a sense of direction without requiring a click.

**Empty state:** when the DB has no resolved outcomes yet, show a calm message:
"No resolved analyses yet. Results appear after StockSage checks outcomes ~5 trading days after
each analysis." Do not show an empty table.

---

## Screen 2: Ticker Intelligence (from Research click)

Purpose: deep view of how StockSage has performed on one ticker over time. The user clicked
because they want to understand the track record and read the research.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ← Research                                          [+ Analyze AAPL]         │
│                                                                              │
│ AAPL — Apple Inc.                                                            │
│                                                                              │
│ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────┐ │
│ │ Total analyses   │ │ Results checked  │ │ Hit rate         │ │ Avg alpha│ │
│ │ 12               │ │ 10               │ │ 70%              │ │ +1.8%    │ │
│ └──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────┘ │
│                                                                              │
│ Alpha vs market over time                                                    │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ bar chart: one bar per resolved analysis, colored green (beat) or        │ │
│ │ rose (missed). X = analysis date. Y = alpha return. 0-line prominent.    │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ How each rating has performed for AAPL                                       │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ horizontal bar chart: avg alpha by rating label.                         │ │
│ │ Shows whether StockSage's conviction ratings correlate with outcomes.    │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Research history                                          Sort: [Newest ▾]   │
│ ┌────────────┬──────────────┬─────────────┬────────────┬────────────────┐  │
│ │ Date       │ Rating       │ Alpha       │ Outcome    │                │  │
│ ├────────────┼──────────────┼─────────────┼────────────┼────────────────┤  │
│ │ May 1      │ Overweight   │ +2.4%       │ Beat mkt ✓ │ View report →  │  │
│ │ Apr 10     │ Overweight   │ -1.1%       │ Missed ✗   │ View report →  │  │
│ │ Mar 20     │ Hold         │ +0.3%       │ Beat mkt ✓ │ View report →  │  │
│ │ Mar 1      │ -            │ Pending     │ -          │ View report →  │  │
│ └────────────┴──────────────┴─────────────┴────────────┴────────────────┘  │
│                                                                              │
│ StockSage is a research aid, not financial advice.                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Outcome column:** "Beat mkt ✓" in green, "Missed ✗" in rose, "Pending" in amber (no outcome
yet), "Running" in blue (analysis in progress).

**Rating calibration chart:** only shown when there are ≥3 resolved outcomes for AAPL. Hidden
with a quiet note when data is too thin.

---

## Screen 3: Analysis Report (from Ticker Intelligence or My Workspace)

Purpose: one analyst report, in plain language. Make the decision understandable without
exposing agent internals.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ ← AAPL                                                                       │
│                                                                              │
│ AAPL  ·  May 1, 2026                                                         │
│                                                                              │
│ Rating: Overweight       Price target: $215      Horizon: 5 days             │
│                                                                              │
│ Outcome (resolved after 5 trading days)                                      │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Stock return: +4.1%     SPY over same period: +1.7%     Alpha: +2.4%    │ │
│ │ Beat market ✓                                                            │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Summary                                                                      │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Plain-language executive summary from the stored report.                 │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Investment thesis                                                            │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ The investment thesis, unedited except for layout.                       │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ Evidence    [Market] [News] [Sentiment] [Fundamentals] [Debate] [Risk]       │
│ ┌──────────────────────────────────────────────────────────────────────────┐ │
│ │ Active section content. Collapsed by default for long text.              │ │
│ └──────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│ StockSage is a research aid, not financial advice.                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

Outcome box is hidden (not shown as empty) if the analysis has not yet been resolved.

---

## Screen 4: My Workspace (User View)

Purpose: personal inbox. Answer "what did I submit and is it done?" Nothing more. Performance
data is not shown here — users click through to the report or the Research view for that.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ My Workspace                                                                 │
│ Showing submissions for Alice                                                │
│                                                                              │
│ ● 2 analyses running  (auto-refreshes)                                       │
│                                                                              │
│ Filter: [Ticker ▾]  [Status ▾]  [Date range ▾]                              │
│                                                                              │
│ ┌──────┬────────────┬────────────────────────┬────────────────────────────┐  │
│ │Ticker│ Submitted  │ Status                 │ Action                     │  │
│ ├──────┼────────────┼────────────────────────┼────────────────────────────┤  │
│ │AMZN  │ May 12     │ ◌ Running              │ —                          │  │
│ │AAPL  │ May 1      │ ● Ready                │ View report →              │  │
│ │MSFT  │ May 1      │ ● Ready                │ View report →              │  │
│ │GOOGL │ Apr 30     │ ● Ready (shared)       │ View report →              │  │
│ │PLTR  │ Apr 24     │ ✗ Failed               │ Retry                      │  │
│ └──────┴────────────┴────────────────────────┴────────────────────────────┘  │
│                                                                              │
│   "Ready (shared)" means another user already ran this analysis — your       │
│   request was linked to the same result.                                     │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Status labels and icons:**
| Status | Icon | Color | Meaning |
|--------|------|-------|---------|
| Queued | ○ | Amber | Waiting to start |
| Running | ◌ animated | Blue | LLM agents working |
| Ready | ● | Ink | Report available |
| Ready (shared) | ● | Ink | Reused existing report |
| Failed | ✗ | Rose | Error; retry available |

**Auto-refresh:** the status column uses HTMX polling only while any row is Queued or Running.
No full-page refresh. Stops polling when all rows are terminal.

**Empty state:** "No submissions yet. Hit + Analyze to request your first analysis."

---

## Screen 5: New Analysis (Modal)

Purpose: one path to submit work. Appears as a modal over whatever screen the user is on.

```text
┌────────────────────────────────────────────────┐
│  Analyze a stock                           ✕   │
├────────────────────────────────────────────────┤
│                                                │
│  Ticker                                        │
│  ┌──────────────────────────────────────────┐  │
│  │ AAPL                                     │  │
│  └──────────────────────────────────────────┘  │
│                                                │
│  Analysis date                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ Today — May 12, 2026                     │  │
│  └──────────────────────────────────────────┘  │
│                                                │
│  ┌─ Note ─────────────────────────────────────┐ │
│  │ StockSage already has an AAPL report for  │ │
│  │ May 12. Your submission will link to it.  │ │
│  └────────────────────────────────────────────┘ │
│                                                │
│  ┌──────────────────────┐  ┌─────────────────┐ │
│  │  Submit              │  │ Cancel          │ │
│  └──────────────────────┘  └─────────────────┘ │
└────────────────────────────────────────────────┘
```

- Submitting always runs in the background and returns immediately.
- If a report for this ticker/date already exists (or is in progress), show the "Note" box
  explaining it will be reused — no duplicate LLM work.
- After submit, the user is sent to My Workspace.

---

## Screen 6: Queue Status (Admin / Power User)

Not in primary navigation. Accessible via a "View queue →" link from the running indicator in
My Workspace, or from a Settings page.

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ StockSage        Research   My Workspace           [Alice ▾]  [+ Analyze]    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│ Queue status                             Auto-refreshing · Last: 12:04:32    │
│                                                                              │
│ ┌──────┬────────────┬──────────┬──────────┬──────────┬──────────┬─────────┐  │
│ │Ticker│ Date       │ Status   │ Asked by │ Attempts │ Queued   │ Action  │  │
│ ├──────┼────────────┼──────────┼──────────┼──────────┼──────────┼─────────┤  │
│ │AMZN  │ May 12     │ Running  │ Alice    │ 1        │ 12:03    │ —       │  │
│ │TSLA  │ May 12     │ Queued   │ Bob      │ 0        │ 12:01    │ —       │  │
│ │PLTR  │ Apr 24     │ Failed   │ Alice    │ 3        │ Apr 24   │ Retry   │  │
│ └──────┴────────────┴──────────┴──────────┴──────────┴──────────┴─────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

Worker concurrency and advanced settings are behind a Settings page, not this view.

---

## Visual Direction

**Typography and color:**
- Ink text on white surfaces. No dark mode in scope for this milestone.
- Positive alpha / beat market: green (`#16a34a`)
- Negative alpha / missed: rose (`#e11d48`)
- Running / in progress: blue (`#2563eb`)
- Queued / pending: amber (`#d97706`)
- Neutral / pending outcome: slate gray

**Layout:**
- No hero sections or landing-page chrome. First screen is research content.
- Metric tiles: small, borderless, number large, label small and muted.
- Tables: compact, readable. Row actions right-aligned. No hover-reveal menus.
- Cards / chart panels: subtle border, small radius, no nested card stacks.
- Charts always include: a clear title, axis labels, an empty-state message, and a data-source note.

**Charts:**
| Chart | Location | Type |
|-------|----------|------|
| System accuracy over time | Research | Line, rolling 30-day hit rate |
| Alpha vs market over time | Ticker Intelligence | Bar, one bar per resolved analysis |
| Rating calibration | Ticker Intelligence | Horizontal bar, avg alpha by rating |

Use Chart.js loaded from CDN. No build pipeline. Chart data serialized server-side as JSON into
a `<script>` tag.

---

## Reusable Building Blocks

| Block | Used on | Purpose |
|-------|---------|---------|
| App shell | all | Top nav, user switcher, + Analyze button |
| Metric tile | Research, Ticker | Stat number + label |
| Research table | Research | Sortable, filterable system-view table with sparklines |
| Ticker header | Ticker Intelligence | Ticker symbol, name, quick stats |
| Alpha bar chart | Ticker Intelligence | Resolved outcomes over time |
| Rating calibration chart | Ticker Intelligence | Avg alpha by rating |
| System accuracy chart | Research | Rolling hit rate line chart |
| Workspace table | My Workspace | User-scoped status table, HTMX-refreshed |
| Status badge | Workspace table, Queue | Queued / Running / Ready / Failed / Shared |
| Rating badge | Research table, Report | Buy / Overweight / Hold / Underweight / Sell |
| Outcome block | Analysis Report | Stock return, SPY, alpha, beat/missed |
| Evidence tabs | Analysis Report | Sectioned deep-dive content |
| New Analysis modal | all | Submit form, reuse detection |
| Empty state | all list pages | Calm message + primary action |
| Chart panel | Research, Ticker | Consistent title, empty state, source note |

---

## Implementation Status

This design was reviewed and accepted before T01 began. Keep adjusting this document when UX
decisions change, and keep route/template implementation aligned with it.
