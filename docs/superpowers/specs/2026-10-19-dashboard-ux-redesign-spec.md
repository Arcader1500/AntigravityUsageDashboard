# Antigravity Telemetry Dashboard — UI/UX Redesign Specification

**Date:** 2026-10-19  
**Status:** Awaiting User Review (Checkpoint 1)  
**Standard:** UI/UX Pro Max Design Intelligence (`Data-Dense Dashboard` + `Developer Tools Dark / Clean Light`)  
**Target:** Clean Information Architecture, Progressive Disclosure, Reduced Visual Clutter, and Professional Polish for `http://127.0.0.1:8501`.

---

## 1. Problem Diagnosis & Inspection Findings

A thorough browser and architectural inspection of `http://127.0.0.1:8501` across `app.py`, `agy_dash/ui/views.py`, and the Jinja2 templates revealed several critical UX and visual flaws causing cognitive fatigue and clutter:

### 1.1 Dual-Header Stacking & Vertical Real-Estate Waste
* **Current Issue:** The top of the page stacks two heavy sticky bars:
  1. Primary Command Bar (`.command-bar-primary`): brand, radar pulse, 2 badge pills, segmented view nav (`01 // COMMAND`, `02 // SESSIONS`, `03 // ECONOMICS`), and 3 action buttons.
  2. Global Filter Strip (`.filter-strip`): 6 form groups (`RANGE`, `MODEL`, `CURRENCY`, `FX`, `SUB`) plus Filter and Reset buttons.
* **Impact:** Together, they consume over ~110px of sticky height. This compresses the visible analytical workspace on 1080p and laptop screens. Every change to model or currency fires an immediate form submit (`onchange="this.form.requestSubmit()"`), which can cause jarring layout shifts.

### 1.2 "Command" View: Metric Satiation & Scroll Sprawl
* **Current Issue:**
  * 8 KPI cards in two consecutive 4-column strips right at the top (`TOTAL INGESTION`, `FRESH INPUT`, `CACHED INPUT`, `OUTPUT & THINKING`, `EQUIVALENT API COST`, `SUBSCRIPTION SPEND`, `BLENDED EFFICIENCY`, `CACHE SAVINGS`).
  * 3 verbose callout boxes (`Pricing Notice`, `Equivalent API Cost Notice`, `Waste Proxy Notice`) push visual charts down by ~200px.
  * 5 charts and 2 data tables stacked in a vertical sequence requiring 3 full viewport scrolls.
  * Structural emojis (`⚡`, `📥`, `📤`, `💰`) used inside KPI cards and badges, violating professional UI standards.

### 1.3 "Sessions" View: Extreme Clutter (9 Charts + 3 Tables + 11 KPIs)
* **Current Issue:**
  * 11 KPI cards spread across 3 disjointed strips.
  * 9 ECharts instances rendered simultaneously on a single page (`top_sessions`, `session_kinds`, `calls_vs_sessions`, `time_budget`, `thinking_ratio`, `tool_mix`, `model_switches`, `mcp`, `failure_daily`).
  * 3 dense data tables (Leaderboard, Latencies, Artifacts).
  * Collapses three completely distinct user intents (Workload Analysis, Swarm Agent Coordination, Reliability Diagnostics) into an endless, overwhelming feed.

### 1.4 "Economics" View: Two Conflicting Tools on One Screen
* **Current Issue:**
  * Stacks "Stage 1: Forecasting Engine" (statistical predictive projection over 7–90 days) and "Stage 2: What-If Simulator" (counterfactual engine benchmarking catalog models and cache hit rates) into one endless scroll.
  * Each stage has independent parameters, baseline KPIs, and tables. The user's mental model is divided between "historical projection" and "counterfactual simulation".

### 1.5 Visual Styling & Component Polish (`telemetry.css`)
* **Current Issue:**
  * Raw emojis (`🌓`, `🔄`, `⚡`, `🤖`, `📐`) render inconsistently across Windows, macOS, and Linux.
  * Blinding neon borders and pulses create visual vibration against dark backgrounds.
  * High-density padding inside bento cards wastes container area without improving clarity.

---

## 2. Redesign Goals & Architectural Principles

Applying the **UI/UX Pro Max** framework (`Data-Dense Dashboard`, `ux-guidelines`, `color-accessible-pairs`, and `pro-rules`):

1. **Progressive Disclosure**: Break high-density views into focused, intuitive sub-tabs (segmented controls) so users inspect one operational dimension at a time without losing context.
2. **Compact Command Header**: Collapse the double-header into a single 54px streamlined command bar with a sleek, popover or inline filter deck, reclaiming ~55px of vertical workspace.
3. **Information Density with Breathing Room**: Adopt an 8px spacing rhythm with disciplined typography (`font-variant-numeric: tabular-nums`) and unified KPI matrices instead of repetitive card rows.
4. **Vector Iconography**: Replace all system and KPI emojis with clean, themed SVG icons (Lucide / Heroicons inline vector format).
5. **Contextual Feedback**: Smooth 150ms transitions for tab swaps and drawer interactions; subtle loading spinners on form actions; zero full-page reload jumps.

---

## 3. UI/UX Pro Max Design System Foundation

### 3.1 Color Tokens & Theming (Developer Tools Dark + Clean Technical Light)
All color pairs are verified for WCAG 2.2 AA contrast (minimum 4.5:1 for body text, 3:1 for graphical UI):

| Token | Dark Mode (`[data-theme="dark"]`) | Light Mode (`[data-theme="light"]`) | Usage |
|---|---|---|---|
| `--bg-core` | `#0B0F19` (Slate Dark) | `#F8FAFC` (Slate 50) | Main canvas background |
| `--panel-bg` | `#111827` (Gray 900) | `#FFFFFF` (Pure White) | Bento cards, panels |
| `--panel-alt` | `#1E293B` (Slate 800) | `#F1F5F9` (Slate 100) | Header pills, table alternating rows |
| `--border-subtle` | `#1F2937` (Gray 800) | `#E2E8F0` (Slate 200) | Card borders, dividers |
| `--border-focus` | `#38BDF8` (Sky 400) | `#0284C7` (Sky 600) | Interactive active/focus state |
| `--text-main` | `#F1F5F9` (Slate 100) | `#0F172A` (Slate 900) | Primary headers, data values |
| `--text-muted` | `#94A3B8` (Slate 400) | `#64748B` (Slate 500) | Labels, subtext, captions |
| `--signal-emerald` | `#10B981` (Emerald 500) | `#059669` (Emerald 600) | Cache hit, healthy, online |
| `--signal-sky` | `#38BDF8` (Sky 400) | `#0284C7` (Sky 600) | Primary ingestion, fresh input |
| `--signal-amber` | `#F59E0B` (Amber 500) | `#D97706` (Amber 600) | Output tokens, forecast median |
| `--signal-violet` | `#A78BFA` (Violet 400) | `#7C3AED` (Violet 600) | Metered API value, thinking ratio |
| `--signal-rose` | `#F43F5E` (Rose 500) | `#E11D48` (Rose 600) | Failures, eviction, latency alerts |

### 3.2 Typography & Tabular Numerals
* **Display / Brand**: `Syne`, sans-serif (weights 700–800) for high-craft technical branding.
* **Body / Interface**: `Plus Jakarta Sans`, sans-serif (weights 400, 500, 600) at 12px–13px with 1.5 line-height.
* **Telemetry Data & Numerals**: `JetBrains Mono`, monospace (weights 500, 600, 700) with `font-variant-numeric: tabular-nums` to guarantee aligned columns and prevent layout shifts.

### 3.3 SVG Vector Iconography
Replace emojis with SVG vector icons:
* Theme toggle: SVG Sun / Moon icon
* Refresh / Rescan: SVG Arrow-Path sync icon
* Drawer / Settings: SVG Sliders / Database icon
* KPI indicators: SVG Zap (Tokens), Currency Dollar / Rupee, Cloud / Arrow-Down, Terminal, Shield-Alert.

---

## 4. View-by-View Redesign Specifications

### 4.1 Global Command Header (`partials/command_bar.html`)
* **Unified Single-Row Bar (54px height)**:
  * Left: Brand identity `ANTIGRAVITY // TELEMETRY` with subtle emerald status pulse + Live Mini Badges (`Tokens`, `Metered API`).
  * Center: Primary Navigation Tabs (`01 // COMMAND`, `02 // SESSIONS`, `03 // ECONOMICS`) with pill-style active indicator.
  * Right: Compact Filter Trigger (`Filters (Active: Last 30d, gemini-3.8-flash, INR)`), Theme Toggle button, Rescan button, and Sync/DB drawer button.
* **Collapsible / Popover Filter Strip**:
  * Instead of permanently occupying 50px of vertical height across all views, filters expand smoothly on click or stay as an elegant inline toolbar that can be collapsed.
  * Debounced inputs with clear "Apply" button so changes don't fire unnecessary queries mid-typing.

### 4.2 View 01 // COMMAND (`partials/view_command.html`)
* **Consolidated KPI Matrix**:
  * Replace 8 cards with a balanced 4-metric Hero Grid:
    1. **Total Ingestion**: Big metric (`42.5M`), subtitle (`Fresh vs Cached ratio pill`), icon.
    2. **Equivalent API Cost**: Modeled consumption (`₹3,420`), rate per Mtok badge.
    3. **Cache Efficiency**: Hit rate (`64.2%`), savings estimated badge.
    4. **Active Footprint**: Days measured, total sessions, waste proxy warning if failures exist.
* **Streamlined Notices**:
  * Combine verbose text callouts into a single expandable info banner or subtle inline tooltips next to the metric labels, saving 150px of vertical space.
* **Tiered Bento Workspace**:
  * **Top Section (Trajectory & Breakdown)**:
    * Left (col-8): `Telemetry Burn Trajectory` (Daily token burn over time).
    * Right (col-4): `Token Mix & Cost Burden` (Combined clean donut/stacked bar visualization).
  * **Bottom Section (Attribution & Hotspots)**:
    * Left (col-7): `Workspace & Project Attribution` chart with clean paginated table.
    * Right (col-5): `Context Eviction Signals` & `Top Heaviest Active Days` consolidated in a structured panel with quick toggles.

### 4.3 View 02 // SESSIONS (`partials/view_sessions.html`)
De-clutter the 9 charts and 11 KPIs by introducing **3 Sub-Navigation Tabs**:

```
[ All Sessions (Leaderboard) ]  [ Swarm & Agent Coordination ]  [ Reliability & Latencies ]
```

1. **Sub-Tab 1: All Sessions (Leaderboard & Directory)**
   * Filter row: Quick Kind pills (`All`, `Main`, `Subagent`, `Other`) + Search input.
   * 4 Workload KPIs (`Filtered Sessions`, `Total Tokens`, `Avg Workload`, `Subagent Token Share`).
   * Charts: `Top Sessions Leaderboard` (Horizontal Bar) + `Session Class Split` (Donut).
   * Interactive Data Table: Clean rows with ID, Label, Kind badge, Tokens, Cost, Date. Clicking a row opens `#session-drawer`.
2. **Sub-Tab 2: Swarm & Agent Coordination**
   * 4 Swarm KPIs (`Background Logs`, `Schedule Calls`, `Task Invocations`, `Subagents Managed`).
   * Charts: `MCP Server Dispatches`, `Tool Invocation Mix`, `Engine Switches`, and `Active vs Waiting Time Budget`.
   * Artifacts & Messages reference table.
3. **Sub-Tab 3: Reliability & Latencies**
   * 3 Context & Friction KPIs (`High Context Sessions >100K`, `Failure Steps`, `Avg Latency`).
   * Charts: `Failure Steps per Day` + `Thinking Step Ratio`.
   * Tables: `Top Repeated Failure Signatures` (with syntax highlight and copyable error text) + `Slowest Shell Commands` + `User Approval Denials`.

*Result:* Instant reduction in cognitive load. Users focus on sessions, swarm tools, or debugging independently.

### 4.4 View 03 // ECONOMICS (`partials/view_economics.html`)
Split into **2 Distinct Segmented Modes**:

```
[ 01 // Forecasting Engine ]   [ 02 // What-If Simulator & Model Lab ]
```

1. **Mode 1: Forecasting Engine (`forecast_stage.html`)**
   * Clean control bar: Target metric, statistical method (Bootstrap, Monte Carlo, Linear, Holt), Horizon slider, Cadence selector.
   * 4 Projections KPIs (`Observed Daily Mean`, `P10 Floor`, `P50 Median`, `P90 Surge`).
   * Bento Grid: Trajectory Fan Chart (col-8) + Cumulative Horizon Summary & CSV download (col-4), followed by Schedule Table and Cadence Chart.
2. **Mode 2: What-If Simulator & Model Lab (`lab_stage.html`)**
   * Simulator controls: Prompt multiplier, Output multiplier, Cache hit rate override slider, and Model selection checkboxes.
   * Workload baseline strip (Fresh, Cached, Output, Baseline Hit Rate).
   * Multi-Model Benchmark Chart & Comparison Table (`Model`, `Vendor`, `Workload Cost`, `Rate/MTok`, `Tokens/Spend`, `vs Cheapest`).
   * Subscription vs Metered Value comparison card and chart.

### 4.5 Flyout Drawers & Modals Polish
* **`#sync-drawer`**: Organized into 3 visual sections: "Source Health", "Snapshot Runs", and "Job Runner Logs" with scrollable output containers and syntax-styled status dots.
* **`#session-drawer`**: Add segmented tabs inside the drawer (`Overview`, `Tool Calls`, `Shell Commands`, `Failures`) to eliminate endless vertical scrolling in the drawer.
* Accessible escape hatch: Pressing `ESC` or clicking the backdrop smoothly closes any open drawer.

---

## 5. Implementation Scope & Grounded Files

| Component / File | Specific Scope of Changes |
|---|---|
| [`agy_dash/ui/templates/base.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/base.html) | Modernize font imports, add vector SVG icon symbols sprite, structure drawer container with accessibility attributes. |
| [`agy_dash/ui/templates/partials/command_bar.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/command_bar.html) | Unify command bar and filter strip into a single 54px header with collapsible filter deck; replace emojis with SVG icons. |
| [`agy_dash/ui/templates/partials/view_command.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_command.html) | Consolidate 8 KPIs into a 4-quadrant Hero Grid; streamline callouts into interactive badges; clean bento grid composition. |
| [`agy_dash/ui/templates/partials/view_sessions.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_sessions.html) | Implement 3 sub-navigation tabs (`Leaderboard`, `Swarm Coordination`, `Reliability`); distribute 9 charts and 3 tables cleanly. |
| [`agy_dash/ui/templates/partials/view_economics.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_economics.html) | Provide segmented switcher between `Forecasting Engine` and `What-If Simulator` with clean container swaps. |
| [`agy_dash/ui/templates/partials/session_drawer.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/session_drawer.html) | Add tabs inside session detail drawer to separate Metadata, Tool Latencies, Shell Commands, and Errors. |
| [`agy_dash/ui/templates/partials/sync_drawer.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/sync_drawer.html) | Refactor into structured status cards and clean run history table. |
| [`agy_dash/ui/static/css/telemetry.css`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/static/css/telemetry.css) | Implement UI/UX Pro Max design tokens, 8px spacing rhythm, card elevation, micro-interactions, responsive breakpoints (375px, 768px, 1200px, 1600px). |
| [`agy_dash/ui/static/js/app.js`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/static/js/app.js) | Enhance chart re-hydration, handle sub-tab transitions, keyboard `ESC` drawer closing, and filter strip toggle. |

---

## 6. Verification & Quality Gates

1. **Unit & View Tests**: Execute `pytest tests/test_ui_views.py tests/test_ui_common.py tests/test_web_app.py` to ensure all view models and FastAPI endpoints pass with zero errors.
2. **Visual Hierarchy & Contrast**: Verify all foreground/background pairs meet WCAG 2.2 AA contrast >= 4.5:1 in both Dark and Light themes.
3. **No Emoji as Structural Icons**: Confirm all UI controls, tabs, and badges use SVG icons rather than raw emoji characters.
4. **Responsive Testing**: Test across desktop (1440px+), tablet (1024px), and mobile breakpoints (375px) without horizontal scrolling.
5. **Chart Re-hydration**: Ensure switching sub-tabs properly resizes and re-renders ECharts without memory leaks or blank charts.

---

## 7. Checkpoint 1 Approval Request

This specification is submitted for user review before writing execution tasks or touching code.  
**Decision needed:** Approve the specification as written, or specify adjustments to the information architecture, color palette, or sub-tab breakdown.
