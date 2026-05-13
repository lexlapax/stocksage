# Allbert — Elixir/OTP Workspace Rethink Plan

**Author:** Sandeep Puri  
**Date:** 2026-05-13  
**Status:** Draft — revised with user input, prior-art research, and architectural decisions  
**Scope:** Three-deliverable plan for rethinking StockSage inside the Allbert personal AI workspace built on Elixir/OTP, Jido, Phoenix LiveView, and Ash

---

## 1. What Changed From The First Draft

The original `aiworkspace-plan.md` treated this as a greenfield project. This revision incorporates five new inputs:

1. **Prior art**: `allbert-assist-exs` (Elixir, v0.10) and `allbert-assist-rs` (Rust, v0.15) are both real, substantially built codebases. We are not starting from scratch.
2. **Workspace name**: The workspace is called **Allbert**. `allbert-assist-exs` is the Elixir repo this plan extends.
3. **Deliverable ordering**: Chat agent first, native trading agents second, StockSage web UI third.
4. **New architectural concerns**: multi-user data model from the start, cross-app agent/action/signal registry, and a generative UI live canvas in LiveView.
5. **Existing roadmap check**: The allbert-assist-exs `docs/plans/v0.11` through `v0.17` plans were reviewed. **No conflicts found** — v0.11–v0.16 cover allbert core capabilities (intent, jobs, channels, memory, security) that are orthogonal to D1–D3. **v0.17 already plans the live canvas** ("Agentic Workspace Surface and Ephemeral UI Substrate") — the generative UI work is already on the allbert roadmap. We do not rebuild it; StockSage hooks into it when v0.17 ships.

---

## 2. What Allbert Already Has (allbert-assist-exs v0.10)

`https://github.com/lexlapax/allbert-assist-exs` is a Phoenix umbrella at v0.10 with:

| Concern | What exists |
|---------|-------------|
| Umbrella structure | `allbert_assist` (OTP core) + `allbert_assist_web` (Phoenix web) |
| Agent framework | Jido 2.2, jido_action 2.2, jido_signal 2.1, jido_ai 2.1 |
| Primary agent | `AllbertAssist.Agents.IntentAgent` — deterministic routing + Jido.AI.Agent tools |
| Action registry | `AllbertAssist.Actions.Registry` — module-keyed action lookup |
| Skills system | Full agentskills.io-compatible: parser, local registry, online import, SKILL.md shipped skills |
| Memory | Markdown-first: `AllbertAssist.Memory` writes per-category `.md` files under `ALLBERT_HOME/memory/` |
| Settings | `AllbertAssist.Settings` — YAML-backed settings engine with encrypted secrets |
| Security | `AllbertAssist.Security.PermissionGate`, `SecurityCentral`, resource grants, durable confirmations |
| Runtime | `AllbertAssist.Runtime.submit_user_input/1` — signal-first turn boundary with `operator_id` |
| CLI | Mix tasks: `allbert.ask`, `allbert.skills`, `allbert.settings`, `allbert.confirmations`, `allbert.resources` |
| Web UI | LiveView: `AgentLive` (chat), `SettingsLive`; DaisyUI + Tailwind |
| Database | SQLite via ecto_sqlite3 (local, no server needed) |
| Plans | `docs/plans/v0.01` through `v0.17` — 13 ADRs documented |

The Rust version (`allbert-assist-rs` v0.15) is more advanced but is a separate runtime. We extend the Elixir version.

**What is explicitly missing** from allbert-assist-exs v0.10 (and what this plan adds):

- Multi-user support: `operator_id` exists but all data is single-user / single-home
- Conversation history: no turn-by-turn DB persistence (memory is append-only markdown)
- ETS session scratchpad: no in-process session state per user
- Native trading agents (Jido AI): no domain-specific agent topology for financial analysis
- StockSage web surface: no analysis, queue, trends LiveViews
- Cross-app registry: only `allbert_assist` actions are registered; no contract for other apps to register

---

## 3. Vision

> **Allbert is a personal AI workspace. StockSage is the first domain app inside it.**

The workspace is the operating environment. Allbert handles memory, skills, security, settings, multi-user sessions, and the shared agent runtime. StockSage plugs in as a first-class workspace app — registering its own agents, actions, and skills with the Allbert core at startup.

The LiveView surface evolves from a static chat UI toward a **live canvas**: a server-authoritative, AI-drivable workspace where the agent's output can specify which UI components to render, not just what text to display.

---

## 4. Three Deliverables

### D1 — Multi-user Allbert Chat Agent with Memory

**Goal:** Extend allbert-assist-exs so the chat agent is multi-user from the start — `user_id` in all data structures, APIs, and storage — with conversation history and an ETS session scratchpad. Mix tasks are the primary test surface; LiveView comes in D3.

**What this is NOT:** This is not semantic vector search or structured fact extraction. Those are later phases. D1 is the foundation: turn history + in-session scratchpad + user scoping.

**Key changes to allbert-assist-exs:**

```
AllbertAssist.Memory.Thread       ← Ecto schema: {id, user_id, title, inserted_at, updated_at}
AllbertAssist.Memory.Message      ← Ecto schema: {id, thread_id, user_id, role, content, inserted_at}
AllbertAssist.Session.Scratchpad  ← ETS-backed, per session_id, TTL-expired
AllbertAssist.Runtime             ← updated: accepts user_id + thread_id; stores Message rows
```

**Mix task API changes:**

```sh
mix allbert.ask "hello"                          # user_id defaults to "local"
mix allbert.ask --user alice "hello"             # explicit user_id
mix allbert.ask --user alice --thread abc "..."  # explicit thread
mix allbert.ask --user alice --new-thread "..."  # creates a new thread
mix allbert.threads --user alice                 # list threads
mix allbert.threads --user alice --thread abc    # show messages in thread
```

**Why SQLite for history (not markdown):** Conversation history needs ordering, pagination, and cross-thread queries. Markdown files are fine for long-term memory entries but not for structured conversation records. SQLite via ecto_sqlite3 is already in the project.

**Later phases (not D1):**
- Semantic/vector recall (pgvector or sqlite-vec RAG)
- Structured fact extraction and entity recognition
- Cross-session memory promotion (connect to existing markdown memory)

---

### D2 — Native Elixir Trading Agents (Jido AI, Mix Task)

**Goal:** Implement TradingAgents as native Jido AI agents in a new `stocksage` umbrella app. The full analysis pipeline runs via `mix stocksage.analyze AAPL 2026-05-01` before any web UI exists.

**Why native Jido before web UI:** The Python bridge (ErlPort) works but is a seam, not a foundation. Building the agent topology first in Elixir makes D3 (the web UI) a pure presentation concern — the agents are already tested.

**New umbrella apps:** `stocksage` (OTP core) + `stocksage_web` (Phoenix surface, D3).

**Agent topology:**

```
StockSage.Analysis.Pod  (one Pod per analysis run)
├── OrchestratorAgent    ← coordinates workflow; receives signals
├── MarketAnalystAgent   ← Jido.AI.Agent, fetches market data, writes market_report
├── SentimentAnalystAgent
├── NewsAnalystAgent
├── FundamentalsAnalystAgent
├── BullResearcherAgent  ← receives analyst reports; argues Bull thesis
├── BearResearcherAgent  ← argues Bear thesis
├── TraderAgent          ← resolves bull/bear debate into a trading plan
└── PortfolioManagerAgent ← final risk-adjusted decision (Buy/Hold/Sell + target)
```

Each agent uses `Jido.AI.Agent` with a ReAct strategy. Actions are Jido actions with AI tool schema generation:

```elixir
defmodule StockSage.Actions.FetchStockData do
  use Jido.Action,
    name: "fetch_stock_data",
    description: "Fetch OHLCV, fundamentals, and technical indicators for a ticker",
    schema: [
      ticker:     [type: :string, required: true],
      start_date: [type: :date, required: true],
      end_date:   [type: :date, required: true]
    ]
  # ...
end
```

**Mix task:**

```sh
mix stocksage.analyze AAPL 2026-05-01
mix stocksage.analyze --deep AAPL 2026-05-01   # full multi-agent graph
mix stocksage.analyze --quick AAPL 2026-05-01  # single-agent fast path
```

**Python bridge (transitional):** For the Python TradingAgents graph, keep an ErlPort bridge as a fallback selectable via config. The native Jido agents are the default; bridge is the escape hatch.

---

### D3 — Web-based StockSage UI

**Goal:** A LiveView workspace surface for StockSage within the Allbert shell. Analysis, queue management, trends, and live agent progress.

**LiveViews:**

```
/stocksage/                  → StockSageLive.WorkspaceLive  (dashboard + quick-enqueue)
/stocksage/analysis/:id      → StockSageLive.AnalysisLive   (tabbed: Overview, Market, Bull/Bear, Trader, Risk)
/stocksage/queue             → StockSageLive.QueueLive      (live queue with Oban + PubSub)
/stocksage/trends            → StockSageLive.TrendsLive     (accuracy charts, leaderboard)
```

Real-time agent progress via `Phoenix.PubSub` — Oban job events push through to the LiveView without polling.

**Canvas integration (post-v0.17):** StockSage LiveViews start as standard LiveViews. After the allbert core v0.17 live canvas ships, `StockSageWeb.Canvas.StockChart` and `AnalysisCard` register with the v0.17 catalog. No canvas work happens in D3 itself.

---

## 5. Cross-App Agent/Action/Signal Registry

### 5.1 The Problem

In an umbrella where `allbert_assist` (core) and `stocksage` are separate OTP applications, the IntentAgent in `allbert_assist` should be able to route to StockSage actions. Currently `AllbertAssist.Actions.Registry` only knows about actions defined in `allbert_assist`. There is no contract for apps to register themselves.

### 5.2 The Solution: App Behaviour + Registry Extension

Each workspace app implements a behaviour:

```elixir
defmodule AllbertAssist.App do
  @callback app_id() :: atom()
  @callback display_name() :: String.t()
  @callback actions() :: [module()]           # Jido action modules to register
  @callback skills() :: [String.t()]          # priv/skills/ directories to add to skill registry
  @callback signal_subscriptions() :: [String.t()]  # signal topics this app listens to
  @callback supervision_children() :: [Supervisor.child_spec()]
end
```

Apps register at startup via the Allbert core:

```elixir
# In StockSage.Application.start/2
AllbertAssist.App.Registry.register(StockSage)

# Which triggers:
AllbertAssist.Actions.Registry.register_many(StockSage.app_actions())
AllbertAssist.Skills.Registry.add_path(StockSage.priv_skills_dir())
```

The `AllbertAssist.Actions.Registry` already exists — it just needs an `app_id` tag on each entry so the intent agent can scope routing (e.g., "this is a stocksage action, only route here if stocksage is the active context").

### 5.3 Cross-App Signal Routing

Signals cross app boundaries via the shared `Jido.Signal.Bus` (already in the core supervision tree). A StockSage agent emits:

```elixir
Jido.Signal.new!("stocksage.analysis.completed", %{analysis_id: id, user_id: user_id})
|> Jido.Signal.Bus.publish(AllbertAssist.SignalBus)
```

The Allbert shell `NotificationAgent` subscribes to `stocksage.*` and surfaces cross-app events in the workspace notification bar. LiveViews subscribe directly to PubSub topics:

```elixir
Phoenix.PubSub.subscribe(AllbertAssist.PubSub, "stocksage:analysis:#{analysis_id}")
```

### 5.4 Intent Routing to Cross-App Actions

The IntentAgent's deterministic router gets a new layer:

```elixir
defp route(text, context) do
  # 1. Check core allbert actions (existing)
  # 2. Check active app context from session (new)
  # 3. Route to registered app actions if in-scope
end
```

When a user is in the StockSage context (navigated to `/stocksage/...`), the session agent sets `active_app: :stocksage` and the intent agent prioritizes StockSage actions. A natural language prompt like "analyze AAPL for today" routes to `StockSage.Actions.RunAnalysis`.

### 5.5 Umbrella Structure

```
allbert/                          ← Umbrella root (allbert-assist-exs renamed/extended)
├── apps/
│   ├── allbert_assist/           ← Core OTP application (existing v0.10)
│   │   ├── lib/allbert_assist/
│   │   │   ├── app.ex            ← AllbertAssist.App behaviour (new)
│   │   │   ├── app/registry.ex   ← AllbertAssist.App.Registry (new)
│   │   │   ├── memory/
│   │   │   │   ├── memory.ex     ← existing markdown memory
│   │   │   │   ├── thread.ex     ← NEW: Ecto schema, user_id + thread_id
│   │   │   │   └── message.ex    ← NEW: Ecto schema, turn history
│   │   │   ├── session/
│   │   │   │   └── scratchpad.ex ← NEW: ETS-backed session state
│   │   │   ├── agents/           ← existing IntentAgent + future specialists
│   │   │   ├── actions/          ← existing action modules
│   │   │   ├── skills/           ← existing skill registry + parser
│   │   │   ├── security/         ← existing security + permission gate
│   │   │   └── settings/         ← existing settings engine
│   │   └── mix.exs
│   │
│   ├── allbert_assist_web/       ← Phoenix web (existing v0.10)
│   │   ├── lib/allbert_assist_web/
│   │   │   ├── live/
│   │   │   │   ├── agent_live.ex     ← existing chat UI (updated: multi-user threads)
│   │   │   │   └── settings_live.ex  ← existing
│   │   │   └── components/           ← existing + thread list component
│   │   └── mix.exs
│   │   (canvas_live.ex and canvas catalog added by allbert core v0.17, not this plan)
│   │
│   ├── stocksage/                ← StockSage OTP application (NEW)
│   │   ├── lib/stocksage/
│   │   │   ├── application.ex    ← registers with AllbertAssist.App.Registry
│   │   │   ├── agents/           ← Jido.AI.Agent modules
│   │   │   ├── actions/          ← Jido action modules
│   │   │   ├── domain/           ← Ash resources (Analysis, Outcome, Queue, etc.)
│   │   │   ├── trader_bridge/    ← ErlPort bridge (transitional)
│   │   │   ├── outcomes/
│   │   │   ├── trends/
│   │   │   └── memory/           ← StockSage memory entries → allbert memory
│   │   └── mix.exs
│   │
│   └── stocksage_web/            ← StockSage LiveView surface (NEW, D3)
│       ├── lib/stocksage_web/
│       │   ├── live/             ← WorkspaceLive, AnalysisLive, QueueLive, TrendsLive
│       │   └── components/       ← StockSage UI components (standard LiveView)
│       │   (StockChart + AnalysisCard register with v0.17 canvas catalog post-D3)
│       └── mix.exs
│
├── config/
├── mix.exs
└── .env.example
```

---

## 6. Generative UI: Live Canvas — Alignment with allbert v0.17

### 6.1 What the Existing Roadmap Already Plans

The allbert-assist-exs `docs/plans/v0.17-plan.md` ("Agentic Workspace Surface and Ephemeral UI Substrate") already specifies exactly this concept. Key excerpts from that plan:

- Define an **Allbert surface envelope** for declarative UI data: surface id, purpose, lifecycle, component catalog, data bindings, provenance, fallback text, allowed events, registered action bindings
- Design the **LiveView workspace shell** around runtime state: conversation and signal timeline, canvas, task surfaces, approval inspector, trace inspector
- Use **Phoenix LiveView and OTP primitives**: PubSub topics for runtime events, LiveView streams for timelines, `start_async/3` for long-running requests
- Treat A2UI, AG-UI, MCP Apps, Claude Artifacts, Gemini generative UI as **research references** — Allbert-native contracts first

This is the right decomposition. **We do not build the canvas in D1–D3.** v0.17 owns it.

### 6.2 What D1–D3 Contribute Toward v0.17

D1 and D2 lay the groundwork that v0.17 needs:

| D1/D2/D3 contribution | Why v0.17 needs it |
|----------------------|---------------------|
| `user_id` + `thread_id` in runtime (D1a) | Canvas tiles are user-scoped and thread-scoped |
| ETS session scratchpad with `active_app` (D1b) | Canvas shell needs to know the active app context |
| `AllbertAssist.App` behaviour + registry (D2a) | v0.17 enumerates registered apps to populate the workspace shell nav |
| Jido Signal bus publishing from StockSage (D2b/D2c) | Canvas timeline streams from the signal bus |
| StockSage LiveViews as plain LiveViews (D3) | v0.17 canvas wraps existing LiveView surfaces; no rewrite needed |

### 6.3 StockSage Canvas Integration (Post-v0.17)

Once allbert core v0.17 ships its canvas substrate, StockSage adds:

```elixir
# In StockSage.App callbacks (extends the existing behaviour)
def canvas_components(), do: [
  {"stock_chart",    StockSageWeb.Canvas.StockChart},
  {"analysis_card",  StockSageWeb.Canvas.AnalysisCard}
]
```

The agent response format gains `canvas_ops` after v0.17 defines the contract:

```elixir
%{
  message: "Here is AAPL's 30-day trend.",
  canvas_ops: [
    %{op: :upsert, id: "chart-aapl", component: "stock_chart",
      attrs: %{ticker: "AAPL", range: "30d"}}
  ]
}
```

**This is a post-D3 milestone** (§11, M-Canvas) and has no dependency on D1–D3 being complete first — it just needs v0.17 to ship.

### 6.4 Technology Posture

Research found `ex_a2ui` (Google A2UI protocol, implemented in Elixir) and `vercel-labs/json-render` as alternatives. v0.17 already positions native LiveView as the substrate (server-authoritative diff-patch = built-in streaming protocol, no extra JS bundle). A2UI remains an option if Allbert later needs mobile/desktop clients. That decision belongs in the v0.17 plan, not here.

---

## 7. Multi-User Data Model

### 7.1 `user_id` Everywhere

Every resource, memory entry, action context, signal, and mix task parameter carries `user_id`. The default for local single-user operation is `"local"`. The existing `operator_id` in the runtime becomes `user_id` (or is aliased).

```elixir
# Runtime boundary (updated signature)
AllbertAssist.Runtime.submit_user_input(%{
  text: "analyze AAPL",
  user_id: "alice",           # was operator_id
  thread_id: "thread-123",    # new
  session_id: "sess-abc",     # new (ETS scratchpad key)
  channel: :cli
})
```

### 7.2 Conversation History Schema (SQLite)

```elixir
defmodule AllbertAssist.Memory.Thread do
  use Ecto.Schema

  schema "threads" do
    field :user_id,    :string
    field :title,      :string
    field :app_id,     :string  # nil = general; "stocksage" = stocksage context
    timestamps()
  end
end

defmodule AllbertAssist.Memory.Message do
  use Ecto.Schema

  schema "messages" do
    field :thread_id,  :string
    field :user_id,    :string
    field :role,       :string   # "user" | "assistant" | "tool"
    field :content,    :string
    field :action_log, :map      # rendered action results, serialized
    field :trace_id,   :string
    timestamps(updated_at: false)
  end
end
```

`app_id` on `Thread` is the cross-app signal: a thread started from the StockSage LiveView is tagged `app_id: "stocksage"` and the intent agent uses it for context.

### 7.3 ETS Session Scratchpad

```elixir
defmodule AllbertAssist.Session.Scratchpad do
  # ETS table :allbert_session_scratchpad, type: :set
  # Key: {user_id, session_id}
  # Value: %{active_app: :stocksage, context: %{}, working_memory: %{}, expires_at: ...}
  # (canvas_tiles added by allbert core v0.17 — not in scope here)

  def get(user_id, session_id) :: map()
  def put(user_id, session_id, key, value) :: :ok
  def delete(user_id, session_id) :: :ok
end
```

### 7.4 Multi-user Mix Task API

```sh
# Single-user (default, backwards-compatible)
mix allbert.ask "hello"

# Multi-user
mix allbert.ask --user alice "hello"
mix allbert.ask --user alice --thread abc123 "continue this thread"
mix allbert.threads list --user alice
mix allbert.threads show --user alice --thread abc123
```

No authentication in D1 — just `user_id` as a string. Authentication (AshAuthentication, JWT) is a later milestone.

---

## 8. Data Layer: Ash + SQLite (Allbert Core) and PostgreSQL (StockSage)

### 8.1 Two Storage Tiers

| App | Layer | Reason |
|-----|-------|--------|
| `allbert_assist` (core) | Ecto + SQLite (ecto_sqlite3) | Personal assistant; local-first; no server needed; existing choice |
| `stocksage` | Ash + PostgreSQL (AshPostgres) | Financial data; Oban requires Postgres; complex queries benefit from Postgres |

The two apps each have their own `Repo`. The umbrella root `mix.exs` lists both repos in `:repos`. Tests use in-memory SQLite for allbert_assist and a test PostgreSQL DB for stocksage.

### 8.2 Why keep SQLite for allbert core

- `allbert_assist` is already on SQLite and it works for settings, confirmations, resource grants, and conversation history
- Adding PostgreSQL just for the core would require users to run a Postgres server for a personal assistant
- SQLite is a correct fit for single-node, local-first, personal data

### 8.3 StockSage data uses Ash

StockSage Ash resources (unchanged from first plan draft):

```elixir
StockSage.Domain.Analysis
StockSage.Domain.AnalysisDetail
StockSage.Domain.Outcome
StockSage.Domain.AnalysisQueue
StockSage.Domain.QueueRun
StockSage.Domain.MemoryEntry
```

Each resource has `belongs_to :user, AllbertAssist.Accounts.User` — the `user_id` in StockSage resources is a foreign key to the Allbert user record.

---

## 9. agentskills.io — Already Implemented, What to Add

**allbert-assist-exs v0.10 already implements the full agentskills.io client spec:**

- `AllbertAssist.Skills.Parser` — parses SKILL.md frontmatter + body
- `AllbertAssist.Skills.Registry` — discovers skills from `~/.allbert/skills/` and `priv/skills/`
- `AllbertAssist.Skills.ActionPlan` — three-tier progressive disclosure (catalog → activation → resources)
- Mix tasks: `allbert.skills validate`, `allbert.skills import-local`, `allbert.skills import-url`
- Built-in skills: `append-memory`, `direct-answer`, `read-recent-memory`, `list-skills`, etc.

**What to add for StockSage:**

```
apps/stocksage/priv/skills/
├── run-analysis/
│   └── SKILL.md    ← "Analyze a stock ticker for a given date using TradingAgents"
├── get-trends/
│   └── SKILL.md    ← "Get accuracy trends and leaderboard for a user's analyses"
├── resolve-outcome/
│   └── SKILL.md    ← "Resolve outcome for a completed analysis after holding period"
└── queue-analysis/
    └── SKILL.md    ← "Queue a batch of tickers for overnight analysis"
```

These skills register with the global skill registry via the `AllbertAssist.App` contract. The intent agent can activate them via natural language: "analyze AAPL" → activates `run-analysis` skill → routes to `StockSage.Actions.RunAnalysis`.

**What NOT to change:** The agentskills.io client implementation in allbert_assist is complete. StockSage just needs to publish skills.

---

## 10. Technology Stack (Updated)

### 10.1 Core Runtime (unchanged + confirmed against allbert-assist-exs)

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Elixir / OTP 27 | 1.18+ |
| Web framework | Phoenix | 1.8 |
| UI | Phoenix LiveView | 1.1 |
| Agent framework | Jido | 2.2 |
| AI integration | Jido AI | 2.1 |
| Actions library | Jido Action | 2.2 |
| Signal bus | Jido Signal / Phoenix.PubSub | 2.1 |

### 10.2 Data Layer

| Layer | App | Technology |
|-------|-----|-----------|
| Conversation history, settings, confirmations, resource grants | allbert_assist | Ecto + SQLite (ecto_sqlite3) |
| Analysis, outcomes, queue, trends | stocksage | Ash Framework 3.x + AshPostgres |
| In-memory session state | allbert_assist | ETS (session scratchpad) |
| Background jobs | stocksage | Oban (PostgreSQL) |

### 10.3 Python Bridge (transitional, StockSage only)

ErlPort pool for TradingAgents — unchanged from first draft. Long-term: native Jido agents (D2) replace it.

---

## 11. Milestones

### Two Parallel Tracks

The existing allbert-assist-exs roadmap already occupies v0.11–v0.17 for allbert core work (intent, jobs, channels, memory, security, canvas). This plan's milestones run as a **parallel track** using D-labels to avoid collision. The tracks share the same repo and can be developed concurrently — there are no blocking dependencies between them until D3 + v0.17 converge on the canvas.

```
allbert core (existing plans):   v0.11 → v0.12 → v0.13 → v0.14 → v0.15 → v0.16 → v0.17(canvas)
                                                                                        ↑
stocksage track (this plan):     D1a → D1b → D2a → D2b → D2c → D3a → D3b ──────→ M-Canvas
```

D1a/D1b touch allbert core files (add multi-user to `allbert_assist`). D2a–D3b add new umbrella apps. None of them alter files owned by v0.11–v0.17.

---

### M-D1a — Multi-User Conversation Layer  
**Allbert track: parallel to v0.11** (no dependency; additive changes to `allbert_assist` only)

**Goal:** Add `user_id`, `thread_id`, and conversation history to the existing allbert-assist-exs runtime. All existing behavior is preserved; new behavior is additive.

**Scope:**
- `Thread` and `Message` Ecto schemas + SQLite migrations
- `AllbertAssist.Session.Scratchpad` ETS table started in supervision tree
- `Runtime.submit_user_input/1` accepts and propagates `user_id`, `thread_id`, `session_id`
- `IntentAgent.respond/1` reads last N messages from thread as context prefix
- Mix tasks: `allbert.ask --user`, `--thread`, `--new-thread`; `allbert.threads list|show`
- `AgentLive` updated to support multiple threads per user (basic thread list sidebar)
- All existing single-user behavior preserved when `user_id` is omitted (defaults to `"local"`)

**Acceptance:** `mix allbert.ask --user alice "hello"` creates a thread; `mix allbert.ask --user alice "what did I just say?"` reads context from that thread and responds correctly.

---

### M-D1b — ETS Session Scratchpad  
**Allbert track: parallel to v0.11–v0.12** (additive; no canvas yet)

**Goal:** Wire up the session scratchpad so agents and LiveViews can read/write volatile per-session state keyed by `{user_id, session_id}`.

**Scope:**
- `AllbertAssist.Session.Scratchpad` — ETS table, full CRUD, TTL expiry via `:timer`
- Started in `AllbertAssist.Application` supervision tree
- Runtime populates `active_app` and `working_memory` on each turn
- `AgentLive` stores its `session_id` and reads scratchpad for `active_app` context
- (No canvas — `canvas_tiles` key is reserved for allbert core v0.17)

**Acceptance:** Two concurrent `mix allbert.ask --user alice` calls get isolated scratchpad entries; stale entries expire after TTL.

---

### M-D2a — StockSage Umbrella App + Domain  
**StockSage track: v0.1.0** (can start immediately; no allbert core version dependency)

**Goal:** `stocksage` umbrella app with all Ash resources, migrations, and the `AllbertAssist.App` registration.

**Scope:**
- `stocksage` and `stocksage_web` umbrella apps scaffolded
- `AllbertAssist.App` behaviour implemented for StockSage
- `AllbertAssist.App.Registry` in allbert_assist — `register/1` + `registered_apps/0`
- All Ash resources: `Analysis`, `AnalysisDetail`, `Outcome`, `AnalysisQueue`, `QueueRun`, `MemoryEntry`
- `user_id` FK on all resources → `allbert_assist.users` table
- Ash migrations + `mix ash.codegen` workflow
- StockSage skill pack: `run-analysis`, `get-trends`, `queue-analysis` SKILL.md files registered
- SQLite import task: `mix stocksage.import_sqlite /path/to/stocksage.db`

**Acceptance:** All Ash resources round-trip; existing Python stocksage.db data imports cleanly; StockSage skills appear in `mix allbert.skills list`.

---

### M-D2b — Python Bridge (Transitional)  
**StockSage track: v0.2.0** (depends on M-D2a)

**Goal:** TradingAgents callable via ErlPort. Mix task produces a real analysis.

**Scope:**
- `StockSage.TraderBridge` — NimblePool + ErlPort worker GenServer
- `priv/python/bridge.py` — Python entry point wrapping TradingAgents
- `StockSage.Actions.RunAnalysis` Jido action calling bridge
- Mix task: `mix stocksage.analyze AAPL 2026-05-01`
- Persists `Analysis` + `AnalysisDetail` Ash records
- IntentAgent routes "analyze AAPL" → `run-analysis` skill → `StockSage.Actions.RunAnalysis`

**Acceptance:** `mix stocksage.analyze AAPL 2026-05-01` returns a decision, persists to DB, and is reachable via `mix allbert.ask --user local "analyze AAPL for last week"`.

---

### M-D2c — Native Jido Trading Agents  
**StockSage track: v0.3.0** (depends on M-D2b; can develop in parallel with allbert core v0.12–v0.15)

**Goal:** Replace Python bridge with native Jido AI agents for the full analysis pipeline.

**Scope:**
- All 8 analyst/researcher/trader agents as `Jido.AI.Agent` modules
- Jido Pod topology for the analysis workflow
- `StockSage.Actions.*` — FetchStockData, FetchNews, FetchSentiment, FetchFundamentals
- Bridge remains available for `--bridge` flag on `mix stocksage.analyze`
- Oban `analysis` queue with `StockSage.Workers.AnalysisWorker`
- Outcome + memory workers (Oban cron)

**Acceptance:** Default analysis uses native agents; bridge flag still works; 20-stock smoke batch produces decisions matching Python baseline within acceptable variance.

---

### M-D3a — StockSage LiveView Shell  
**StockSage track: v0.4.0** (depends on M-D2c; plain LiveViews — no canvas yet)

**Goal:** StockSage web surface inside the Allbert shell. Standard LiveViews with real-time PubSub; canvas integration is post-v0.17.

**Scope:**
- `StockSageLive.WorkspaceLive`, `AnalysisLive`, `QueueLive`, `TrendsLive`
- Router: Allbert shell mounts `/stocksage/...` via `App.Registry` (config-driven, not fully dynamic)
- Real-time analysis progress via PubSub + LiveView `stream/3`
- `active_app: :stocksage` set in session scratchpad when user navigates to `/stocksage/...`
- No canvas catalog registration yet — StockSage renders its own LiveView surfaces independently

**Acceptance:** Full analysis cycle from browser; live progress updates without page refresh; trends charts load.

---

### M-D3b — Polish, Outcome Tracking, Trends  
**StockSage track: v0.5.0** (depends on M-D3a)

**Goal:** Full parity with Python StockSage 0.0.2 feature set.

**Scope:**
- Outcome resolver (Oban cron): fetches returns, generates LLM reflection
- Memory sync: resolved outcomes → allbert memory entries
- Trends dashboard: alpha-aware accuracy, rating calibration, leaderboard
- Analysis re-run from LiveView
- Mobile-responsive layout
- Error state handling, empty states

**Acceptance:** All Python 0.0.2 features replicated in Elixir; no Python runtime needed for analysis (bridge only for yfinance data if needed).

---

### M-Canvas — StockSage Canvas Integration  
**After: allbert core v0.17 ships**

**Goal:** Register StockSage components with the v0.17 canvas substrate. No new agent or data work — purely wiring existing StockSage LiveView components into the allbert canvas catalog.

**Scope:**
- `StockSageWeb.Canvas.StockChart` — Phoenix.Component wrapping the chart LiveView
- `StockSageWeb.Canvas.AnalysisCard` — summary tile for a completed analysis
- `StockSage.App` canvas_components callback implemented
- Agent response format extended with `canvas_ops` for analysis results (where useful)
- `WorkspaceLive` dashboard leverages canvas tiles for recent analysis summaries

**Acceptance:** `mix allbert.ask --user alice "analyze AAPL"` triggers an analysis and pushes a `stock_chart` tile to the canvas; tile survives page reload when `persist: true`.

---

### M-Production — Release Hardening  
**After: M-D3b + allbert core v0.16**

- `mix release` + Docker + Fly.io deployment
- AshAuthentication (login, sessions, API keys) replacing string `user_id`
- libcluster + Horde for distributed agent supervision (if multi-node needed)
- Telemetry → OpenTelemetry export
- `StockSage.TraderBridge` pool adapted for cluster: analysis workers routed to analysis-tier nodes

---

## 12. Open Questions

| # | Question | Current position |
|---|----------|-----------------|
| 1 | Rename the repo `allbert-assist-exs` → `allbert`? | Yes — extend in place; GitHub repo rename preserves history and adds redirect |
| 2 | Should `Thread`/`Message` use Ash or raw Ecto? | Raw Ecto for now (consistent with existing allbert_assist style); migrate to Ash later if needed |
| 3 | `user_id` — simple string or UUID? | Simple string for now (`"local"`, `"alice"`) — UUID when AshAuthentication lands (M-Production) |
| 4 | How does `allbert-assist-rs` (Rust v0.15) relate going forward? | Keep it running separately; Elixir is the primary path for workspace + StockSage |
| 5 | Should `allbert_assist_web` router mount StockSage routes dynamically or statically? | Static mounts with conditional inclusion via config — simpler than runtime dynamic routing |
| 6 | D1a (multi-user) vs allbert core v0.11 (intent/resource): which goes first? | They are orthogonal — can be developed in parallel by the same developer; D1a changes are confined to `memory/` and `runtime.ex` |
| 7 | Should M-D2a (stocksage scaffolding) wait for D1a to land? | No hard dependency — `user_id` on Ash resources can be a simple string FK that gets wired up once D1a is merged |
| 8 | agentskills.io: publish StockSage skills to public registry? | Not yet; local priv/skills first; publishing is a post-M-D3b task |

---

## 13. Migration Path from Python StockSage

The Python `0.0.2` codebase is frozen at `stocksage.db`. Migration:

1. **M-D2a includes** `mix stocksage.import_sqlite /path/to/stocksage.db` — imports all analysis history
2. **TradingAgents memory log** (markdown file) is copied to `ALLBERT_HOME/memory/notes/` as a seed entry
3. **API keys** move from Python `.env` to `mix allbert.settings set provider.openai.api_key <key>` (Settings Central)
4. **Python app stays frozen** — it can run in parallel for reference; no new features

---

## 14. References

- allbert-assist-exs: [github.com/lexlapax/allbert-assist-exs](https://github.com/lexlapax/allbert-assist-exs) — Elixir umbrella at v0.10
- allbert-assist-rs: [github.com/lexlapax/allbert-assist-rs](https://github.com/lexlapax/allbert-assist-rs) — Rust version at v0.15
- Jido 2.2: [github.com/agentjido/jido](https://github.com/agentjido/jido)
- Jido AI 2.1: [github.com/agentjido/jido_ai](https://github.com/agentjido/jido_ai)
- agentskills.io standard: [agentskills.io/specification](https://agentskills.io/specification)
- A2UI Protocol: [a2ui.org](https://a2ui.org/) / ex_a2ui: [github.com/23min/ex_a2ui](https://github.com/23min/ex_a2ui)
- Phoenix LiveView 1.1: [hexdocs.pm/phoenix_live_view](https://hexdocs.pm/phoenix_live_view)
- Ash Framework 3.x: [ash-hq.org](https://ash-hq.org)
- Oban: [hexdocs.pm/oban](https://hexdocs.pm/oban)
- Sagents (reference agent+LiveView pattern): [github.com/sagents-ai/sagents](https://github.com/sagents-ai/sagents)
- phoenix_streamdown (streaming markdown): [github.com/dannote/phoenix_streamdown](https://github.com/dannote/phoenix_streamdown)
- Loomkin (reference Jido+LiveView app): [github.com/bleuropa/loomkin](https://github.com/bleuropa/loomkin)
