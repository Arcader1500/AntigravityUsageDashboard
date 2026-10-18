# Antigravity Telemetry Control — Mission Telemetry Web UI Design Spec

**Date:** 2026-10-18  
**Status:** Approved for Implementation Planning  
**Replaces:** Streamlit + Plotly UI (`app.py`, `agy_dash/ui/*.py`, `.streamlit/config.toml`)

---

## 1. Problem & Purpose

The existing Antigravity Usage Dashboard has a well-factored, read-only analytical core (`agy_dash/config.py`, `agy_dash/source.py`, `agy_dash/pricing.py`, `agy_dash/metrics.py`, `agy_dash/deep.py`, `agy_dash/stats.py`, `agy_dash/jobs.py`, `agy_dash/snapshots.py`), but its Streamlit + Plotly frontend suffers from:
1. **Fragmented Information Architecture**: 6 top-level sidebar pages plus 13+ nested sub-tabs scatter related telemetry across disconnected surfaces (e.g., cost is split across `overview.py`, `deep_signals.py::_cost_tab`, `lab.py`, and `forecast.py`; session analysis is split across `explorer.py` and 3 tabs of `deep_signals.py`; operational extraction & SQLite snapshots occupy an entire standalone page `data_jobs.py`).
2. **Primitive Streamlit Constraints**: Full-script reruns on every interaction, rigid column/widget wrappers, generic tab strips, and slow `AppTest` execution.

### Target Outcome
Replace the Streamlit UI completely with a **bespoke, zero-Node-build Python Web Application** powered by **FastAPI + Uvicorn + Jinja2 + HTMX + Alpine.js + Apache ECharts** (with locally vendored JS assets under `agy_dash/ui/static/vendor/`). Consolidate all analytics into **3 cohesive Bento workspaces** plus a **persistent Top Command Bar** and **non-intrusive slide-over drawers** (Sync & Snapshots Drawer, Session Inspector Drawer, and Price Catalog Drawer).

---

## 2. Aesthetic Direction: High-Craft Mission Telemetry

Inspired by **Oxide Computer Console**, **Linear Insights**, and **Raycast**, the interface commits to a **Dark-first High-Craft Mission Telemetry** aesthetic with a curated **Daylight (Technical Paper)** toggle.

### 2.1 Typography
Loaded from Google Fonts with crisp local technical fallbacks:
- **Display / Section Headers (`--font-display`)**: `'Syne', 'Plus Jakarta Sans', -apple-system, sans-serif` — geometric, high-character editorial tracking (`letter-spacing: -0.025em`, weights `600..800`).
- **UI Body & Labels (`--font-sans`)**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif` — clean legibility at `12px–14px`.
- **Telemetry Numerals, Timestamps, UUIDs, & Code (`--font-mono`)**: `'JetBrains Mono', 'Cascadia Mono', Consolas, monospace` with `font-variant-numeric: tabular-nums` enforced on every KPI value, table cell, badge, and axis tick.

### 2.2 Color & Surface Hierarchy (CSS Custom Properties)

#### Dark Mode (`[data-theme="dark"]` — Default: Obsidian Carbon)
- `--bg-canvas`: `#090A0F` (deep obsidian void with subtle radial cyan/amber atmospheric glow and `0.025` SVG noise grain overlay)
- `--bg-panel`: `#10121A` (primary Bento surface)
- `--bg-panel-elevated`: `#161924` (hover state, drawers, popovers, table header)
- `--bg-glass`: `rgba(16, 18, 26, 0.82)` with `backdrop-filter: blur(12px)` (sticky command bar & slide-over drawers)
- `--border-hairline`: `rgba(255, 255, 255, 0.07)` (`1px solid` structural grid lines)
- `--border-luminance`: `rgba(255, 255, 255, 0.14)` (top-edge `1px` specular highlight on cards)
- `--border-focus`: `rgba(56, 189, 248, 0.45)`
- `--text-primary`: `#F3F5F8`
- `--text-secondary`: `#94A3B8`
- `--text-muted`: `#64748B`
- **Signal Accents**:
  - `--signal-cyan` (Fresh Input / Primary Accent): `#38BDF8`
  - `--signal-emerald` (Cached Input / Healthy / Hit Rate): `#10B981`
  - `--signal-amber` (Output & Thinking / Forecast P50): `#F59E0B`
  - `--signal-violet` (API-Equivalent Cost / Thinking Ratio): `#A78BFA`
  - `--signal-rose` (Failures / Cache Miss / Friction): `#F43F5E`

#### Daylight Mode (`[data-theme="light"]` — Technical Stone Paper)
- `--bg-canvas`: `#F4F2ED` (warm technical stone paper)
- `--bg-panel`: `#FFFFFF`
- `--bg-panel-elevated`: `#EAE6DF`
- `--bg-glass`: `rgba(244, 242, 237, 0.88)`
- `--border-hairline`: `rgba(15, 23, 42, 0.10)`
- `--border-luminance`: `rgba(15, 23, 42, 0.18)`
- `--border-focus`: `rgba(2, 132, 199, 0.45)`
- `--text-primary`: `#0F172A`
- `--text-secondary`: `#475569`
- `--text-muted`: `#64748B`
- **Signal Accents**:
  - `--signal-cyan`: `#0284C7`
  - `--signal-emerald`: `#059669`
  - `--signal-amber`: `#D97706`
  - `--signal-violet`: `#7C3AED`
  - `--signal-rose`: `#E11D48`

### 2.3 Spatial Composition & Motion
- **Exposed Hairline Bento Grid**: `12-column` CSS Grid (`gap: 12px`, `max-width: 1680px`, `margin: 0 auto`, `padding: 0 20px 32px`). Panels feature sharp `8px` radius, `1px solid var(--border-hairline)`, and a `1px` top-border specular gradient.
- **Orchestrated Staggered Reveal**: On view swap, Bento cells animate in with a crisp `180ms cubic-bezier(0.16, 1, 0.3, 1)` fade-up (`animation-delay: calc(var(--stagger, 0) * 35ms)`).
- **Zero Full-Page Reloads**: View switching, global filter changes, scenario sliders, forecast model changes, and job status polling swap targeted DOM containers via HTMX (`hx-get` / `hx-post` / `hx-target`) and re-hydrate ECharts instances from JSON `<script type="application/json" data-chart="...">` payloads.

---

## 3. Information Architecture & Consolidation

All existing functionality from the 6 Streamlit pages and 13+ sub-tabs is preserved and consolidated into:

### 3.1 Persistent Top Command Bar (`partials/command_bar.html`)
Always visible at the top of the viewport (`position: sticky; top: 0; z-index: 40`):
1. **Brand & Live Telemetry Pulse**: Pulsing emerald dot, `ANTIGRAVITY // TELEMETRY CONTROL`, active session count, active days, total tokens badge, and API-equivalent cost badge.
2. **Primary View Switcher (3 Tabs)**:
   - `01 // COMMAND CENTER` (`view=command`) — Telemetry & Cost
   - `02 // SESSIONS & SIGNALS` (`view=sessions`) — Execution, Autonomy & Friction
   - `03 // ECONOMICS & FORECAST` (`view=economics`) — Trajectory & Model Lab
3. **Global Filter Bar** (`<form id="global-filters">` triggering HTMX workspace update):
   - Date Range inputs (`start`, `end` — `source.clip_dates` & `source.sessions_touching`)
   - Pricing Model selector (`model_id` from `pricing.models()`, defaulting to `gemini-3.8-flash`)
   - Currency & FX (`currency`, `fx` USD→INR rate input, `sub` subscription spend input)
   - `Reset` button (restores config defaults)
4. **Action Controls**:
   - **Theme Toggle** (`dark` ↔ `light` persisted in query/cookie + `document.documentElement.dataset.theme` + live ECharts theme re-render)
   - **Refresh Scan** button (`POST /api/refresh` — clears cached usage & deep scans)
   - **Sync & Snapshots Drawer Toggle** (`⚡ Sync & DB` button showing live badge for `JobRunner` status and SQLite snapshot count)

### 3.2 Slide-Over Drawer: Sync, Source Health & Snapshots (`partials/sync_drawer.html`)
Replaces the standalone `data_jobs.py` page with an on-demand slide-over drawer accessible from any view:
- **Telemetry Source Health & Integrity**:
  - Status badges for `brain_root` directory (`ONLINE`/`OFFLINE`), `extractor_script`, and `python_executable`.
  - Last scan timestamp, scanned session count, and any `usage.warnings`.
  - **Source Consistency Check** (`metrics.verify_consistency(usage.sessions, usage.daily)`): green verification banner when `total == fresh_in + cached + output` and session/daily sums match, or explicit warning list if discrepancies exist.
- **Background Extractor Pipeline (`agy_dash.jobs.JobRunner`)**:
  - Report profile selector (`all`, `daily`, `sessions`, `tips`) and optional log directory override.
  - `Run Extraction` button (`POST /api/jobs/start`).
  - Live status fragment (`GET /api/jobs/status`, polled every `2s` via `hx-trigger="every 2s"` while `state.running` is true): displays status badge (`IDLE`, `RUNNING`, `SUCCESS`, `FAILED`, `TIMED OUT`, `ERROR`), started/ended timestamps, duration, exit code, command line, and collapsible `<pre>` viewers for `stdout` (last 20k chars) and `stderr` (last 10k chars) plus `last_run` summary.
- **SQLite Snapshot Ledger (`agy_dash.snapshots`)**:
  - `Save Snapshot Now` button (`POST /api/snapshots/ingest`) performing idempotent upsert (`snapshots.ingest`) and returning updated `session_facts`, `daily_facts`, and `runs` counts plus the historical ingestion run ledger table (`snapshots.runs`).

### 3.3 View 1: Command Center — Telemetry & Cost (`partials/view_command.html`)
Consolidates `overview.py`, `deep_signals.py::_cost_tab`, and `explorer.py::_timeseries` into a unified Bento grid:
- **Row 1 — Dual Telemetry & Economics KPI Strip (12 Cards in 2 Bento Ribbons)**:
  - *Token Ribbon (6 cards)*: Total Tokens (`t.total`), Fresh Input (`t.fresh_in` + share %), Cached Input (`t.cached` + hit rate %), Output Tokens (`t.output`), Model Calls (`t.calls` + calls/day), Active Sessions (`t.sessions` + avg tokens/session).
  - *Economics & Unit Ribbon (6 cards)*: Equivalent API Cost (`o.api_cost_usd` at `prices.name`), Actual Subscription (`o.subscription_spend`), Tokens per Currency (`o.tokens_per_currency_spent`), Blended API Rate (`o.blended_rate_usd_per_mtok`/1M), Cost per Call / Busy-Hr (`deep.unit_economics`: `cost_per_call_usd`, `cost_per_busy_hour_usd`, `autonomy_ratio`), Waste Proxy (`deep.waste_estimate`: `failure_count`, `cost_usd`, `tokens_at_risk`).
  - Honesty callout banner explaining consumption-equivalent API cost vs fixed subscription fee, plus `ctx.price_note` warning when using an estimated price version, and the waste-proxy order-of-magnitude disclaimer.
- **Row 2 — Main Telemetry Charts (8-col + 4-col Bento)**:
  - **Left (8 cols)**: *Daily Token Ingestion & API Cost Burn* (ECharts stacked bar for `fresh_in`, `cached`, `output` + dual-axis spline for daily `cost` in reporting currency + interactive metric series toggles + dataZoom slider).
  - **Right (4 cols)**: *Token Mix Donut & Cost Burden by Class* (ECharts ring chart with centered total token readout + horizontal bar breakdown of cost by `fresh_in`, `cached`, `output`).
- **Row 3 — Workspace Attribution & Cache Thrash (7-col + 5-col Bento)**:
  - **Left (7 cols)**: *Workspace Allocation & Attribution* (`deep.workspace_totals`): horizontal ECharts bar chart of top 12 projects by tokens + scrollable tabular-mono ledger (`Project / Workspace`, `Sessions`, `Calls`, `Tokens`, `Cost`, `Per 1M`). Includes `history.jsonl` attribution note.
  - **Right (5 cols)**: *Zero-Cache Read Calls & Context Thrashing* (`deep.step_days`): ECharts bar chart of `cache_miss_calls` vs line of `model_calls` per day + cache efficiency summary caption.
- **Row 4 — Consumption Extremes & Daily CSV Ledger (6-col + 6-col Bento)**:
  - **Left (6 cols)**: *Top 3 Heaviest Usage Days* (`metrics.best_worst_days["best"]`).
  - **Right (6 cols)**: *Top 3 Lightest Active Days* (`metrics.best_worst_days["worst"]`) + `Download Daily CSV` button (`GET /api/export/daily.csv`).

### 3.4 View 2: Sessions & Execution Signals (`partials/view_sessions.html`)
Consolidates `explorer.py` (`_top_sessions`, `_kind_split`, `_records`) and `deep_signals.py` (`_time_tab`, `_friction_tab`, `_collab_tab`) into a **3-Zone Bento Canvas + Session Inspector Slide-Over Drawer**:
- **Zone 1 — Session Filter Console, Leaderboard & Records**:
  - Inline filter bar (`hx-get="/partials/sessions-zone"`): Session kind pills (`main`, `subagent`, `other`), Top-N limit (`5..200`, default `25`), search input (matches `label` or `session_id`), and `Download Session CSV` (`GET /api/export/sessions.csv`) + `Rescan Deep Signals` button (`POST /api/refresh?scope=deep`).
  - Summary KPI strip: Filtered Sessions (`main` / `subagent` counts), Filtered Token Volume, Avg Tokens / Session, Subagent Token Share %.
  - **8-col + 4-col Bento**:
    - *Left (8 cols)*: Top Heavyweight Sessions ECharts horizontal bar chart (colored by `kind`) + interactive **Session Ledger Table** where clicking any row opens the **Session Inspector Drawer** (`GET /partials/session-detail/{session_id}`).
    - *Right (4 cols)*: Session Class Share Donut (`main` vs `subagent` vs `other`) + Model Calls vs Distinct Sessions per Day dual-axis ECharts chart.
- **Zone 2 — Autonomy, Time Budget & Tool Telemetry**:
  - **6-col + 6-col Bento**:
    - *Left (6 cols)*: *Agent Active Busy Hours vs User Idle Waiting Hours* (`deep.gaps_daily` stacked bar with 4h cap honesty note) + *Thinking Step Ratio* line chart (`thinking_steps / steps`).
    - *Right (6 cols)*: *Tool Invocations Mix* horizontal bar chart (`tool:*` counters) + *Tool Turnaround Latencies* table (`deep.turnaround_stats`: `Tool`, `Calls`, `P50 (s)`, `P90 (s)`, `Total (min)` with turnaround definition note).
  - **Multi-Agent, MCP & Async Operations Strip**:
    - Subagent Swarm & Async KPIs (`Subagent Sessions`, `invoke_subagent Calls`, `Background Task Logs`, `Schedule Calls`, `manage_task Calls`, `Inter-Agent Messages` + read receipts).
    - **4-col + 4-col + 4-col Bento**:
      - *Col 1*: *Model Engine Switching* (`deep.model_switches` donut + recent switch events table with `USER_SETTINGS_CHANGE` honesty note).
      - *Col 2*: *MCP Server Invocations* (`mcp:*` horizontal bar chart).
      - *Col 3*: *Artifact Ledger & Latest Inter-Agent Messages* (`deep.artifacts` & `deep.messages` tables + Interaction Matrix counters for `search_web`, `read_url_content`, `ask_question`, `generate_image`, `checkpoints`, `steps`).
- **Zone 3 — Friction, Command Diagnostics & Context Pressure**:
  - Context Pressure KPI strip: `Checkpoints` (truncations), `Tool Output Files` + total MB injected, `Peak Single Output (KB)`, `Max Session Checkpoints`.
  - **6-col + 6-col Bento**:
    - *Left (6 cols)*: *Failure Steps per Day* ECharts bar chart + *Top 10 Repeated Failure Signatures* table (`deep.failure_summary`: `Error Signature`, `Count`, `Last Seen`, `Impacted Sessions`).
    - *Right (6 cols)*: *Slowest Shell Commands* table (`deep.commands`: top 15 by `duration_seconds` with exit code badges and CLI stamp window note) + *User Approval Denials* table (`deep.denials`: date, blocked command, prompt window, reason).
- **Session Inspector Slide-Over Drawer (`partials/session_drawer.html`)**:
  - Triggered by clicking any session row in Zone 1 (`GET /partials/session-detail/{session_id}`).
  - Displays session metadata (`session_id`, `label`, `kind`, `workspace`, `project`, `parent`, `first_utc` → `last_utc`, `wall_seconds`), token & cost breakdown (`fresh_in`, `cached`, `output`, `total`, `api_cost`), session-specific tool call breakdown, command executions, failures, denials, and artifacts from `DeepData`.

### 3.5 View 3: Economics Lab & Forecast (`partials/view_economics.html`)
Consolidates `forecast.py` and `lab.py` into a **Two-Stage Vertical Bento Workspace**:
- **Stage 1 — Predictive Trajectory & Historical Cadence Engine (`forecast.py` + `agy_dash.stats`)**:
  - Inline Forecast Controls (`hx-get="/partials/forecast-stage"`):
    - `target` selector (`Total tokens`, `Fresh input tokens`, `Cached input tokens`, `Output tokens`, `Model calls`, `API-equivalent cost`)
    - `method` selector (`Linear extrapolation (baseline)`, `Bootstrap resampling`, `Monte Carlo simulation`, `Holt linear trend`)
    - `horizon` slider (`1..180` days, default `30`)
    - Method parameter sliders: `daily_growth` (`-0.05..0.10`), `mc_growth` (`-0.05..0.10`), `mc_sd` (`0.0..1.5`)
    - Historical cadence selector (`daily`, `weekly`, `monthly` via `stats.aggregate`)
  - Forecast KPI row: `Observed Daily Mean`, `Forecast Low (P10)`, `Forecast Median (P50)`, `Forecast High (P90)`.
  - Algorithm assumptions callout (`fc.assumptions`, `stats.uncertainty_note`, `fc.notes`, and statistical modeling disclaimer).
  - **8-col + 4-col Bento**:
    - *Left (8 cols)*: *Trajectory Projection Fan Chart* (ECharts line of measured history + vertical horizon marker + dashed P50 median line + shaded P10–P90 confidence band) and *Measured Historical Cadence Bar Chart* (`daily`/`weekly`/`monthly`).
    - *Right (4 cols)*: *Cumulative Horizon Summary* (P10/P50/P90 + subscription payback ratio) + *Daily Projected Schedule* scrollable table + `Download Forecast CSV` button (`GET /api/export/forecast.csv`).
- **Stage 2 — Model Cost Laboratory & What-If Simulator (`lab.py` + `agy_dash.metrics`)**:
  - Baseline Workload KPIs (`Prompt Tokens` + cache share %, `Output Tokens`, `Total Workload`).
  - Interactive Scenario Controls (`hx-get="/partials/lab-stage"`):
    - `use_ratio` toggle + `cached_ratio` slider (`0.0..1.0`)
    - `output_mult` slider (`0.0..3.0`, default `1.0`)
    - `prompt_mult` slider (`0.0..3.0`, default `1.0`)
    - Multi-model benchmark checkboxes (`chosen` models from `ctx.catalog.entries`)
  - **7-col + 5-col Bento**:
    - *Left (7 cols)*: *Multi-Model Cost Matrix* horizontal ECharts bar chart (colored amber when `estimate=True`, cyan when verified for period) + comparison table (`Model`, `Vendor`, `Workload Cost`, `Per 1M Tokens`, `Tokens per Currency`, `vs Cheapest`, `Price Version From`, `Note`) + identical-token-count assumption note.
    - *Right (5 cols)*: *Fixed Subscription vs Equivalent Metered API Value* card (`Fixed Subscription Fee`, `API Value at Selected Model`, `Theoretical Delta`, horizontal comparison bar chart, quota/overage honesty note) + `Open Price Catalog Reference` button opening the **Price Catalog Slide-Over Drawer** (`partials/catalog_drawer.html`) displaying all `ctx.catalog.entries` with verified badges and sources.

---

## 4. Technical Architecture & File Layout

### 4.1 Dependencies (`requirements.txt` & `pyproject.toml`)
- Remove: `streamlit`, `plotly`, `.streamlit/config.toml`
- Keep: `pandas>=2.1`, `numpy>=1.26`, `pytest>=8.0`
- Add: `fastapi>=0.110`, `uvicorn>=0.29`, `jinja2>=3.1`, `python-multipart>=0.0.9`, `httpx>=0.27` (for FastAPI `TestClient`)

### 4.2 File Structure
- `app.py` — FastAPI application entry point (`app = FastAPI(...)`), CLI runner (`python app.py` or `uvicorn app:app`), route handlers for HTML views, HTMX partials, JSON/action endpoints, and CSV exports.
- `agy_dash/ui/__init__.py` — Exports `Ctx`, `build_ctx`, `fmt_tokens`, `fmt_money`, `fmt_pct`, `fmt_rate`, `colors`.
- `agy_dash/ui/common.py` — Pure Python formatting (`fmt_tokens`, `fmt_money`, `fmt_pct`, `fmt_rate`), theme token palettes (`DARK`, `LIGHT`, `colors()`), and `Ctx` / `build_ctx()` (zero Streamlit/Plotly imports).
- `agy_dash/ui/state.py` — Thread-safe in-memory TTL cache for `scan_usage` (30s TTL) and `scan_deep` (900s TTL) keyed by `(brain_root, extractor_script)`, plus singleton `JobRunner` management and query-parameter filter parsing (`FilterParams`).
- `agy_dash/ui/charts.py` — Pure functions returning serializable Apache ECharts option dicts (`dict[str, Any]`) for all dashboard charts:
  - `daily_burn_chart(ctx)`
  - `token_mix_chart(ctx)`
  - `cost_burden_chart(ctx)`
  - `workspace_attribution_chart(ws_df, ctx)`
  - `cache_thrash_chart(step_days_df, ctx)`
  - `top_sessions_chart(sessions_df, top_n, ctx)`
  - `session_kind_chart(sessions_df, ctx)`
  - `calls_vs_sessions_chart(daily_df, ctx)`
  - `time_budget_chart(gaps_daily_df, ctx)`
  - `thinking_ratio_chart(step_days_df, ctx)`
  - `tool_mix_chart(counters, ctx)`
  - `failure_daily_chart(failures_df, ctx)`
  - `model_switches_chart(switches_df, ctx)`
  - `mcp_invocations_chart(counters, ctx)`
  - `forecast_fan_chart(observed_df, fc, column, unit, ctx)`
  - `historical_cadence_chart(agg_df, column, freq, unit, ctx)`
  - `model_benchmark_chart(cmp_df, ctx)`
  - `subscription_comparison_chart(ctx)`
- `agy_dash/ui/views.py` — View-model builders assembling template context dictionaries for:
  - `build_shell_context(ctx, view, filters)`
  - `build_command_view(ctx, deep_data)`
  - `build_sessions_view(ctx, deep_data, kind_sel, top_n, search)`
  - `build_session_detail(ctx, deep_data, session_id)`
  - `build_economics_view(ctx, fc_params, lab_params)`
  - `build_sync_drawer(ctx)`
- `agy_dash/ui/templates/`
  - `base.html` — HTML5 shell, Google Fonts (`Syne`, `Plus Jakarta Sans`, `JetBrains Mono`), CSS link, vendored JS scripts (`htmx.min.js`, `alpine.min.js`, `echarts.min.js`, `app.js`), top command bar, main `#workspace-canvas`, and drawer containers.
  - `error.html` — Styled diagnostic view when `SourceError` or missing `PriceEntry` occurs (showing `config/config.json` path hints).
  - `partials/command_bar.html`
  - `partials/view_command.html`
  - `partials/view_sessions.html`
  - `partials/view_economics.html`
  - `partials/sync_drawer.html`
  - `partials/job_status.html`
  - `partials/session_drawer.html`
  - `partials/catalog_drawer.html`
- `agy_dash/ui/static/`
  - `css/telemetry.css` — Complete design system, dark/light CSS variables, Bento grid layouts, hairline specular cards, tabular-mono tables, slide-over drawers, and staggered entrance animations.
  - `js/app.js` — ECharts auto-initializer and resize observer (`renderAllCharts()`), HTMX `afterSwap` chart hydration hook, and live Dark/Light theme switcher.
  - `vendor/htmx.min.js`, `vendor/alpine.min.js`, `vendor/echarts.min.js` — Locally vendored production builds so `127.0.0.1` works offline.
- Delete legacy Streamlit modules:
  - `agy_dash/ui/overview.py`
  - `agy_dash/ui/explorer.py`
  - `agy_dash/ui/deep_signals.py`
  - `agy_dash/ui/lab.py`
  - `agy_dash/ui/forecast.py`
  - `agy_dash/ui/data_jobs.py`
  - `.streamlit/config.toml`

---

## 5. Out of Scope
- Modifying the external token extraction script (`~/docs/superpowers/scripts/agy_usage.py`).
- Modifying the core analytical calculations or schemas in `agy_dash/metrics.py`, `agy_dash/deep.py`, `agy_dash/stats.py`, `agy_dash/pricing.py`, `agy_dash/source.py`, `agy_dash/jobs.py`, or `agy_dash/snapshots.py`.
- Adding external database servers, authentication, cloud telemetry uploads, or Node.js/npm build toolchains.
