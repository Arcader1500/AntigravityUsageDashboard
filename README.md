# Antigravity Mission Telemetry Dashboard

A local, high-craft, read-only mission telemetry web dashboard over token usage recorded by the Antigravity CLI.
Built with **FastAPI**, **Jinja2**, **HTMX**, and **Apache ECharts** (replacing the legacy Streamlit + Plotly interface).
It reuses the existing extractor (`agy_usage.py`) instead of reimplementing it, and computes every cost itself from a **dated, versioned price catalog**.

Nothing is uploaded. The app binds to `127.0.0.1:8501` only, uses vendored offline-safe frontend assets (no CDNs or external requests), and transmits zero telemetry.

---

## 1. Quick start (Windows PowerShell)

```powershell
cd $env:USERPROFILE\PycharmProjects\AntigravityUsageDashboard

# One-time setup (using uv or py launcher)
uv venv
uv pip install -r requirements.txt
# Alternatively with python/pip:
# py -m venv .venv
# .venv\Scripts\python.exe -m pip install -r requirements.txt

# Run via production launcher script (starts uvicorn on http://127.0.0.1:8501)
.\run.ps1

# Or run directly with Uvicorn:
.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8501 --reload
```

Open your browser at `http://127.0.0.1:8501`.

Run tests:

```powershell
.venv\Scripts\python.exe -m pytest
```

---

## 2. What it reads

| | |
|---|---|
| Usage source | `~/.gemini/antigravity-cli/brain/<conversationId>/.system_generated/logs/transcript.jsonl` (read-only, never written) |
| Extractor | `agy_usage.py` — imported and called, never modified |
| Prices | `config/pricing.json` (falls back to the built-in catalog) |
| Config | `config/config.json` (falls back to `config/config.example.json` defaults) |
| Snapshots | `data/snapshots.db` (SQLite, optional) |
| Job logs | `data/logs/` (stdout/stderr per run, `last_run.json`, lock file) |
| Deep scan also reads | `transcript_full.jsonl` (richer than `transcript.jsonl`), `history.jsonl` (workspace), `settings.json` (current model), `messages/*.json` + `read.json`, `subagents/*.json`, `steps/*/output.txt` sizes, `*.md.metadata.json` artifacts — all read-only |

Token fields exist **only from 2026-10-05 onward**; older sessions are empty shells and
are skipped. A full scan takes ~1.5 s and is cached in-memory with a 30 s TTL.

---

## 3. Architecture & Data Flow

The dashboard is structured as a stateless FastAPI service paired with lightweight HTMX swaps and vanilla JS-managed Apache ECharts instances:

```
ACLI logs ──► agy_usage.scan(root) ──► sessions{} / daily{} dicts
                                          │
                     source.scan_usage()  │  normalize to pandas
                                          ▼
                     sessions_df / daily_df (tokens only, no cost)
                                          │
         pricing.Catalog.price_on(model, date) ──► PriceEntry (USD per 1M tokens)
                                          ▼
                     metrics.*  ──►  totals, costs, blended rate, tokens/₹, comparisons
                                          │
                   ┌───────────────────────┼──────────────────────────┐
                   ▼                       ▼                          ▼
          FastAPI + Jinja2 + HTMX   stats.py forecasts        snapshots.ingest()
          (3 Workspaces + 3 Drawers) (linear/bootstrap/MC)     (idempotent SQLite)
```

A second, heavier pass feeds the Deep Signals components. It is read-only and separate
from the token scan, because it answers different questions:

```
ACLI logs + history.jsonl + settings.json + messages/ + subagents/ + artifacts
                               │
                     deep.scan_deep(root)          ~7 s, cached 15 min
                               ▼
    tool_calls · turnarounds · gap time budget · failures · denials · commands
    model switches · session/workspace meta · artifacts · messages · counters
                               ▼
                     Sessions & Telemetry views
```

Cost is **never read from the logs** — it does not exist there. It is always
`tokens × price` for the model and period you select.

---

## 4. Workspaces & Slide-over Drawers

The web UI provides a dense, low-latency Mission Telemetry operations experience structured into **3 workspaces** and **3 slide-over drawers**, controlled by a sticky Command Bar:

### Sticky Command Bar & Live HUD
- **Global Filters**: Date range presets (`All`, `Today`, `7d`, `14d`, `30d`), custom date inputs, baseline model selector.
- **Financial Controls**: Currency selector (`INR`, `USD`, `EUR`, `GBP`), configurable FX rate, and actual subscription spend input.
- **Live Telemetry HUD**: Real-time badges for total tokens, API-equivalent cost, background extractor job status dot, and manual cache refresh trigger (`POST /api/refresh`).
- **Workspace Navigation**: Instant HTMX tab switching (`hx-swap="outerHTML"` on `#workspace-canvas`) preserving filter parameters.

### `01 // COMMAND` Workspace
- **Telemetry Grid**: High-craft KPI cards displaying Total Tokens, Fresh vs Cached Token distribution, Thinking/Output volume, Blended API Rate, Cost per Call, and Autonomy Ratio.
- **Dual-Axis Daily Burn**: Daily token usage and equivalent API cost time series with interactive Apache ECharts `dataZoom` slider.
- **Fresh vs Cached Ratio**: Donut visualization showing prompt caching efficiency.
- **Workspace Attribution**: Spending and token volume breakdown categorized by workspace project directory.
- **Cost Drivers & Waste Proxy**: Top cost-contributing operations with an order-of-magnitude engineering waste proxy disclaimer.

### `02 // SESSIONS` Workspace (3 Zones)
- **Zone 1 (Header & Swarm Intelligence)**: Session search filter, kind pills (`All`, `Interactive`, `Subagent`), Subagent Swarm KPIs (total subagents, swarm share, inter-agent messages), and Context Pressure metrics.
- **Zone 2 (Deep Telemetry Visualizations)**:
  - *Thinking Ratio Trend*: Daily proportion of reasoning/thinking tokens.
  - *Tool Mix Leaderboard*: Frequency and turnaround time by tool.
  - *Model Switches*: Timeline of model transitions across sessions.
  - *MCP Server Invocations*: Distribution of Model Context Protocol server calls.
  - *Failure Feed & Daily Failures*: Failure frequency and error string analysis.
- **Zone 3 (Session Directory)**: Searchable session table with conversation ID, date, token breakdown, and direct click-to-open integration with the Session Inspector drawer.

### `03 // ECONOMICS` Workspace (Stages 1 & 2)
- **Stage 1: Forecasting Engine**:
  - Four projection models: Linear Baseline, Bootstrap Resampling, Monte Carlo Simulation, and Holt's Trend Model (gated to ≥14 days of data).
  - Configurable forecast horizon, growth drift, and volatility parameters.
  - Uncertainty confidence ribbons (P10–P90 percentile area bands) and cumulative low/median/high projections.
  - Historical cadence chart and daily projected schedule ledger.
- **Stage 2: What-If Simulator & Model Cost Lab**:
  - Cross-model pricing comparison against Gemini Flash/Argon/Pro, Claude Haiku/Sonnet/Opus, OpenAI tiers, and hosted open-weight models.
  - Interactive sliders adjusting Cached Token Ratio, Prompt Volume, and Output Volume.
  - Cost per 1M tokens, tokens per currency unit, and multiple-of-cheapest benchmarks.

### Slide-over Drawers
- **Operations & Sync Drawer (`#drawer-sync`)**: Subprocess job runner to trigger `agy_usage.py` extractions with live polling during execution, stdout/stderr logs, data consistency checks via `metrics.verify_consistency()`, and SQLite snapshot run history.
- **Session Inspector Drawer (`#drawer-session`)**: Deep-dive transcript inspector showing detailed tool invocations, slowest commands with exit codes, error diagnostics, and generated markdown artifacts.
- **Price Catalog Drawer (`#drawer-catalog`)**: Interactive table of dated and versioned model pricing entries with effective date ranges and input/cached/output token rates.

---

## 5. Configuration

`config/config.json` (copy of `config.example.json`):

```json
{
  "brain_root": "~/.gemini/antigravity-cli/brain",
  "extractor_script": "agy_usage.py",
  "python_executable": "py",
  "db_path": "data/snapshots.db",
  "log_dir": "data/logs",
  "extraction_timeout_seconds": 180,
  "subscription": { "amount": 0.0, "currency": "INR", "period_days": 30, "label": "Antigravity plan" },
  "fx": { "USD_INR": 88.0 },
  "reporting_currency": "INR"
}
```

`subscription.amount` is **what you actually pay**. It is used only for
"tokens per rupee actually spent"; leave it at 0 and that metric reads 0 instead of infinity.
The command bar lets you adjust subscription amount, FX rate, currency, and pricing model for
the session without modifying the config file.

### Prices

`config/pricing.json` has one entry per model per date range (`effective_from` /
`effective_until`, USD per 1M tokens for input / cached input / output). To be exact for a
new period, add a version; the dashboard picks the version covering the observed date and
flags anything else as an **estimate** rather than silently using today's rate.
`config/pricing.example.json` is the generated copy of the built-in catalog.

---

## 6. Calculations (all in `agy_dash/metrics.py`, all tested)

* `total = fresh input + cached input + output` — the three categories are mutually
  exclusive in the source (fresh excludes cache reads).
* Equivalent API cost `= Σ (tokens × price) / 1e6`, per model and period.
* Blended API rate `= total modeled cost / total tokens × 1e6`.
* Tokens per ₹ spent `= observed tokens / actual subscription spend`.
* Cache-hit rate `= cached / (fresh + cached)`.
* Every division goes through `safe_div`: zero denominators return a documented default,
  and NaN never propagates.
* `verify_consistency()` re-checks reported totals against the source rows and surfaces
  mismatches in the Sync drawer instead of correcting them.

---

## 7. Limitations you should know

1. **Model attribution is not in the logs.** Transcripts record no per-call model, so all
   usage is priced with the single model you select. Re-pricing could shift totals.
2. **Equivalent cost is not cash.** Inside a subscription quota the marginal spend is zero;
   the API figure is what this usage *would* bill at list prices. The gap between subscription
   and API-equivalent cost is neither money saved nor money paid.
3. **Ten observed days is not six months.** Forecast methods describe the recent routine;
   they cannot establish long-run behaviour. Extrapolating past ~2× the observed window is
   unreliable, and the pages say so.
4. **Bootstrap can only replay what it has seen** — it can never forecast a new record day.
5. **Historical prices.** Where no price version covers a period, the nearest earlier version
   is used and labelled an estimate.
6. **Open-weight/other-vendor prices in the built-in catalog are approximate list prices**
   (`verified: false`), meant for comparison, not invoicing.
7. **Live drift.** Logs keep growing while agent sessions run; the command bar displays scan timestamp.
8. Not included: context-cache storage fees, image generation, print-mode differences.
9. **The time budget is an approximation.** Busy and idle hours come from gaps between
   consecutive step timestamps, capped at 4 h, so an overnight pause counts as 4 h rather than
   9. Granted approvals leave no trace, so their waiting time hides inside the planner→result gap.
10. **Command durations are windows, not stopwatches.** They are the CLI's own
    `Created At`→`Completed At` stamps, which for async commands include waiting. A result block
    is only accepted when it proves it is a command result (exit code or cancellation note),
    otherwise the pairing would invent hours-long "commands".
11. **Tool turnaround includes generation and dispatch**, not just tool execution, and parallel
    tool calls in one step share one gap. The tool list comes from `tool_calls[].name`.
12. **Workspace attribution comes from `history.jsonl`.** Subagent sessions inherit their
    parent's workspace; sessions with no history entry are reported as unattributed rather than
    guessed. The logs contain no per-call model, so the model-switch panel is a timeline, not
    per-call attribution.
13. **Waste estimate is an order of magnitude**, not accounting: failures × average observed
    cost per call. It is capped at 100 % of observed spend and labelled as a proxy in the UI.

---

## 8. Tests

Test suite covers both core analytics and the FastAPI + HTMX interface:

| File | Covers |
|---|---|
| `tests/test_metrics.py` | token totals, cost per category, hand-verified Oct 5 row, blended rate, currency, subscription metrics, safe division, what-if scaling, model comparison, consistency checks |
| `tests/test_pricing.py` | dated versioning, 2027 price change, historical-estimate flagging, catalog file override, broken-file fallback |
| `tests/test_stats.py` | linear slope/flat/growth, bootstrap determinism and bounds, Monte Carlo drift/non-negativity, Holt gating, aggregation totals |
| `tests/test_jobs.py` | success, failure, timeout kill, concurrent-run refusal, lock release and stale locks, missing script, argv-not-shell, last-run record |
| `tests/test_snapshots.py` | idempotent ingestion, upsert on change, run log, last-success |
| `tests/test_source.py` | extractor reuse, normalization, missing paths, date filters, empty results |
| `tests/test_deep.py` | tool-name truth + corrupted-name filtering, MCP server parsing, gap capping, busy/idle split, command duration/exit-code guards, failure text, denials, model-switch cleaning, workspace inheritance, per-day counters, unit economics, waste bounds |
| `tests/test_ui_common.py` | context objects, formatting helpers, CSS helpers, currency conversion |
| `tests/test_ui_state.py` | query parameter parsing, filter validation, context builder caching |
| `tests/test_ui_charts.py` | Apache ECharts option generation, confidence bands, empty fallbacks, styling |
| `tests/test_ui_views.py` | Command, Sessions, and Economics view-model generation and benchmark resolution |
| `tests/test_web_app.py` | FastAPI endpoint tests via `TestClient`: index, workspaces, partials, drawers, refresh |
| `tests/test_extractor_integration.py` | real extractor against a synthetic brain dir and CLI run through the job runner |

Run full suite:
```powershell
.venv\Scripts\python.exe -m pytest
```

---

## 9. File map

```text
agy_usage.py                  the extractor script: scans Antigravity logs into daily/session aggregates
app.py                        FastAPI application: routing, workspace rendering, partial endpoints
agy_dash/
  config.py                   defaults, config.json merge, logging
  source.py                   import the existing extractor, normalize to DataFrames
  metrics.py                  all core calculations (pure)
  pricing.py                  dated/versioned price catalog + lookups
  stats.py                    linear / bootstrap / Monte Carlo / Holt + aggregation
  jobs.py                     subprocess job runner, timeout, lock, last-run record
  snapshots.py                SQLite schema + idempotent ingestion
  deep.py                     second read-only pass: tools, time, failures, workspaces
  ui/
    common.py                 formatting helpers, color palettes, shared Ctx dataclass
    state.py                  TTLCache, filter parameter parsing, context assembly
    charts.py                 pure Apache ECharts option dictionary builders
    views.py                  workspace view-model builders (Command, Sessions, Economics, Drawers)
    static/
      css/telemetry.css       Mission Telemetry design stylesheet (dark / light mode)
      js/app.js               vanilla JS: ECharts lifecycle, drawer triggers, theme toggling
      vendor/
        htmx.min.js           vendored HTMX 2.0.3 (offline-safe)
        echarts.min.js        vendored Apache ECharts 5.5.1 (offline-safe)
        README.md             vendor license and attribution notices
    templates/
      base.html               base layout shell, sticky command bar, workspace canvas, drawers
      error.html              diagnostic error view
      partials/
        command_bar.html      sticky command bar, HUD badges, global filter form
        view_command.html     01 // COMMAND workspace view
        view_sessions.html    02 // SESSIONS workspace view (3 zones)
        view_economics.html   03 // ECONOMICS workspace view (Stages 1 & 2)
        forecast_stage.html   Stage 1: Forecasting engine partial
        lab_stage.html        Stage 2: What-If simulator partial
        sync_drawer.html      Operations & Sync drawer (jobs, consistency, snapshots)
        job_status.html       live extractor job status widget
        session_drawer.html   Session Inspector container drawer
        session_detail.html   deep session transcript inspector partial
        catalog_drawer.html   versioned price catalog table drawer
config/
  config.example.json         configuration example (copied to config.json)
  pricing.example.json        generated copy of the built-in price catalog
tests/                        13 test modules + fixtures
run.ps1                       Windows PowerShell launcher (& uvicorn app:app)
requirements.txt              fastapi, uvicorn, jinja2, python-multipart, pandas, numpy, pytest, httpx
```

**Created:** everything under `AntigravityUsageDashboard/`.
**Modified: nothing external.** `agy_usage.py`, the Antigravity brain directory and the existing
`.gemini` state are only read.
