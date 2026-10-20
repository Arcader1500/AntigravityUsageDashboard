# Dashboard UX & UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the Antigravity Telemetry Dashboard into a clean, modern, data-dense technical interface by eliminating visual clutter, collapsing the dual-header, implementing progressive disclosure across Sessions and Economics views, and standardizing on vector SVG icons and WCAG-compliant design tokens.

**Architecture:** Refactor Jinja2 templates and CSS/JS client assets into a cohesive UI/UX Pro Max dashboard system. Maintain the read-only FastAPI analytical backend, updating view model icon identifiers to SVG symbol IDs, adding client-side and router-supported sub-tab progressive disclosure, a 54px unified command bar with an expandable filter deck, and segmented analytical workflows without full-page reloads.

**Tech Stack:** FastAPI, Jinja2, HTMX, Apache ECharts, CSS Custom Properties (Theme Tokens), Vanilla JS (Client Runtime), Pytest (`pytest`).

---

## Execution Waves

| Wave | Tasks | Description | Files Touched (100% Disjoint) |
|---|---|---|---|
| Wave 1 | Task 1, Task 2 | Design tokens, CSS system, fonts, SVG icon sprite, and global client fixture | `agy_dash/ui/static/css/telemetry.css`, `agy_dash/ui/templates/base.html`, `tests/conftest.py` |
| Wave 2 | Task 3 | View-model SVG icon symbols (eliminating hardcoded emojis) | `agy_dash/ui/views.py`, `tests/test_ui_views.py` |
| Wave 3 | Task 4 | Unified 54px command bar with collapsible filter deck (removing auto-submits) | `agy_dash/ui/templates/partials/command_bar.html`, `tests/test_web_app.py` |
| Wave 4 | Task 5 | Command View Hero KPI matrix & 2-tier Bento grid | `agy_dash/ui/templates/partials/view_command.html`, `tests/test_ui_views.py` |
| Wave 5 | Task 6 | Sessions View progressive disclosure (3 sub-tabs) & JS interactions | `agy_dash/ui/templates/partials/view_sessions.html`, `agy_dash/ui/static/js/app.js` |
| Wave 6 | Task 7 | Economics View segmented switcher (Forecast vs What-If Simulator) | `agy_dash/ui/templates/partials/view_economics.html`, `tests/test_web_app.py` |
| Wave 7 | Task 8 | Slide-Over Drawers polish (tabbed session inspector & clean status cards) | `agy_dash/ui/templates/partials/sync_drawer.html`, `agy_dash/ui/templates/partials/session_detail.html` |
| Wave 8 | Task 9 | Router deep-linking & template context for active sub-tabs and stages | `app.py`, `tests/test_web_app.py` |
| Wave 9 | Task 10 | Full end-to-end regression & live HTTP visual verification suite | `tests/test_web_app.py` |

---

## Tasks

### Task 1: UI/UX Pro Max CSS Design Tokens & Density Foundations

**Wave:** 1  
**Depends on:** None  
**Files Touched:**
- Modify: `agy_dash/ui/static/css/telemetry.css`

- [ ] **Step 1: Write Verification Test**

Verify CSS token existence and contrast variables using Python check:

```python
# Verification script snippet
from pathlib import Path
css = Path("agy_dash/ui/static/css/telemetry.css").read_text(encoding="utf-8")
assert "--bg-core" in css
assert "--signal-sky" in css
assert "--signal-emerald" in css
assert "font-variant-numeric: tabular-nums" in css
```

- [ ] **Step 2: Run verification to check current CSS state (Red)**

Run:
```bash
.\.venv\Scripts\python.exe -c "from pathlib import Path; css = Path('agy_dash/ui/static/css/telemetry.css').read_text(encoding='utf-8'); assert '--signal-sky' in css and 'tabular-nums' in css and '.subtab-btn' in css"
```
Expected: AssertionError (new semantic tokens and tabular-nums not yet present in `telemetry.css`).

- [ ] **Step 3: Implement Design Tokens & Spacing System in telemetry.css**

In [`agy_dash/ui/static/css/telemetry.css`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/static/css/telemetry.css#L1-L60):
1. Update `:root` and `[data-theme="light"]` color tokens to adhere to UI/UX Pro Max Developer Tools Dark & Clean Light palette:
   - Primary dark surface: `--bg-core: #0B0F19`, `--panel-bg: #111827`, `--panel-alt: #1E293B`, `--border-subtle: #1F2937`.
   - Signals: `--signal-sky: #38BDF8`, `--signal-emerald: #10B981`, `--signal-amber: #F59E0B`, `--signal-violet: #A78BFA`, `--signal-rose: #F43F5E`.
   - Light mode overrides with >= 4.5:1 text contrast (`--bg-core: #F8FAFC`, `--panel-bg: #FFFFFF`, `--border-subtle: #E2E8F0`, `--text-main: #0F172A`).
2. Add global typography rules:
   ```css
   .mono, .data-table td.mono, .kpi-card .val, .pill-val {
     font-family: var(--font-mono);
     font-variant-numeric: tabular-nums;
   }
   ```
3. Add utility classes for sub-tab navigation (`.subtab-bar`, `.subtab-btn`, `.subtab-btn.active`, `.subtab-pane`) and compact filter deck (`.filter-collapsible`, `.filter-collapsible.open`).
4. Re-tune `.kpi-card` padding to `0.75rem 1rem` and add subtle 1px border hover transitions (`transition: border-color 150ms ease, box-shadow 150ms ease`).

- [ ] **Step 4: Verify CSS tokens are applied (Green)**

Run:
```bash
.\.venv\Scripts\python.exe -c "from pathlib import Path; css = Path('agy_dash/ui/static/css/telemetry.css').read_text(encoding='utf-8'); assert '--signal-sky' in css and 'tabular-nums' in css and '.subtab-btn' in css; print('CSS tokens verified successfully')"
```
Expected: `CSS tokens verified successfully`

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/static/css/telemetry.css
git commit -m "style: implement UI/UX Pro Max design tokens, tabular numerals, and subtab classes"
```

---

### Task 2: Vector SVG Icon Sprite, Fonts & Global Test Fixture

**Wave:** 1  
**Depends on:** None  
**Files Touched:**
- Modify: `agy_dash/ui/templates/base.html`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write Failing Test in conftest.py check**

Verify that moving the `client` fixture to `tests/conftest.py` allows any test file to import it:

```python
# Test in python check
def test_client_fixture_in_conftest():
    import tests.conftest as c
    assert hasattr(c, "client")
```

- [ ] **Step 2: Run verification to check conftest state (Red)**

Run:
```bash
.\.venv\Scripts\python.exe -c "import tests.conftest as c; assert hasattr(c, 'client')"
```
Expected: AssertionError (`client` fixture not yet in `conftest.py`).

- [ ] **Step 3: Move client fixture to conftest.py & Add SVG Sprite to base.html**

1. In [`tests/conftest.py`](file:///D:/Code/AntigravityUsageDashboard/tests/conftest.py#L205-L208):
   - Move the `client` fixture from `tests/test_web_app.py` to `tests/conftest.py`:
     ```python
     @pytest.fixture
     def client(usage, rich_brain, monkeypatch, tmp_path):
         from fastapi.testclient import TestClient
         import app as app_module
         from agy_dash import config as cfgmod, pricing
         from agy_dash.ui import state
         cfg = cfgmod.Config(data={
             **cfgmod.DEFAULTS,
             "brain_root": str(rich_brain),
             "db_path": str(tmp_path / "snap.db"),
             "log_dir": str(tmp_path / "logs"),
             "reporting_currency": "INR",
             "usd_to_inr": 88.0,
             "default_model": "claude-sonnet",
             "subscription": {"amount": 2000.0, "currency": "INR"},
         })
         monkeypatch.setattr(cfgmod, "get_config", lambda reload=False: cfg)
         monkeypatch.setattr(state, "load_usage", lambda _: usage)
         monkeypatch.setattr(state, "load_catalog", lambda: pricing.default_catalog())
         state.clear_all_caches()
         return TestClient(app_module.app)
     ```
2. In [`agy_dash/ui/templates/base.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/base.html#L1-L30):
   - Add Google Fonts `<link rel="preconnect" href="https://fonts.googleapis.com">` and `<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Syne:wght@700;800&display=swap" rel="stylesheet">`.
   - Insert an inline SVG sprite `<svg style="display:none;" xmlns="http://www.w3.org/2000/svg">` with symbols for all system and KPI icons:
     `icon-refresh`, `icon-theme`, `icon-filter`, `icon-database`, `icon-chevron-down`, `icon-close`, `icon-zap`, `icon-inbox`, `icon-cpu`, `icon-coins`, `icon-credit-card`, `icon-chart-bar`, `icon-shield-check`, `icon-compass`, `icon-bot`, `icon-clipboard`, `icon-clock`, `icon-wrench`, `icon-users`, `icon-alert-triangle`, `icon-mountain`, `icon-ruler`, `icon-trending-down`, `icon-target`, `icon-trending-up`.
   - Add `aria-modal="true" role="dialog"` to all drawer containers for accessibility.

- [ ] **Step 4: Verify conftest fixture is available (Green)**

Run:
```bash
.\.venv\Scripts\python.exe -c "import tests.conftest as c; assert hasattr(c, 'client'); print('conftest client fixture ready')"
```
Expected: `conftest client fixture ready`

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/base.html tests/conftest.py
git commit -m "feat: embed SVG icon sprite, Google fonts in base.html, and expose client fixture in conftest"
```

---

### Task 3: View-Model SVG Icon Symbols (Eliminating Hardcoded Emojis)

**Wave:** 2  
**Depends on:** Task 2  
**Files Touched:**
- Modify: `agy_dash/ui/views.py`
- Modify: `tests/test_ui_views.py`

- [ ] **Step 1: Write Failing Test in test_ui_views.py**

In [`tests/test_ui_views.py`](file:///D:/Code/AntigravityUsageDashboard/tests/test_ui_views.py#L50-L65), assert that KPI dictionaries in view models use SVG icon IDs (`icon-*`) instead of raw emojis:

```python
def test_view_models_use_svg_icon_identifiers(usage, data):
    ctx = _make_ctx(usage)
    cmd_vm = views.build_command_view(ctx, data)
    for kpi in cmd_vm["token_kpis"] + cmd_vm["econ_kpis"]:
        assert kpi["icon"].startswith("icon-"), f"KPI icon is not an SVG symbol ID: {kpi['icon']}"
    
    sess_vm = views.build_sessions_view(ctx, data)
    for kpi in sess_vm["session_kpis"] + sess_vm["swarm_kpis"] + sess_vm["context_kpis"]:
        assert kpi["icon"].startswith("icon-"), f"Session KPI icon is not an SVG symbol ID: {kpi['icon']}"
```

- [ ] **Step 2: Run test to verify it fails (Red)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_ui_views.py::test_view_models_use_svg_icon_identifiers -v
```
Expected: FAIL with `AssertionError: KPI icon is not an SVG symbol ID: ⚡`.

- [ ] **Step 3: Update Icon Identifiers in views.py**

In [`agy_dash/ui/views.py`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/views.py):
1. In `build_command_view` (lines 24–35):
   - Replace `"⚡"` with `"icon-zap"`, `"📥"` with `"icon-inbox"`, `"📤"` with `"icon-cpu"`.
   - Replace `"💵"` with `"icon-coins"`, `"💳"` with `"icon-credit-card"`, `"📊"` with `"icon-chart-bar"`, `"🛡️"` with `"icon-shield-check"`.
2. In `build_sessions_view` (lines 119–123, 201–213):
   - Replace `"🧭"` with `"icon-compass"`, `"⚡"` with `"icon-zap"`, `"📊"` with `"icon-chart-bar"`, `"🤖"` with `"icon-bot"`.
   - Replace `"📋"` with `"icon-clipboard"`, `"⏰"` with `"icon-clock"`, `"🛠️"` with `"icon-wrench"`, `"👥"` with `"icon-users"`.
   - Replace `"⚠️"` with `"icon-alert-triangle"`, `"🏔️"` with `"icon-mountain"`, `"📐"` with `"icon-ruler"`.
3. In `build_economics_view` (lines 349–353):
   - Replace `"📊"` with `"icon-chart-bar"`, `"📉"` with `"icon-trending-down"`, `"🎯"` with `"icon-target"`, `"📈"` with `"icon-trending-up"`.

- [ ] **Step 4: Run test to verify it passes (Green)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_ui_views.py::test_view_models_use_svg_icon_identifiers -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/views.py tests/test_ui_views.py
git commit -m "feat: replace hardcoded emojis with SVG icon identifiers across all view models"
```

---

### Task 4: Unified 54px Command Bar & Collapsible Filter Deck

**Wave:** 3  
**Depends on:** Task 1, Task 2  
**Files Touched:**
- Modify: `agy_dash/ui/templates/partials/command_bar.html`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write Failing Test in test_web_app.py**

In [`tests/test_web_app.py`](file:///D:/Code/AntigravityUsageDashboard/tests/test_web_app.py#L30-L50), add tests verifying the unified 54px header structure, SVG icon references, and removal of inline `onchange="this.form.requestSubmit()"`:

```python
def test_command_bar_unified_structure(client):
    res = client.get("/")
    assert res.status_code == 200
    assert 'class="command-bar-unified"' in res.text
    assert 'id="filter-deck-toggle"' in res.text
    assert '<svg class="icon"><use href="#icon-filter"' in res.text
    assert 'onchange="this.form.requestSubmit()"' not in res.text
```

- [ ] **Step 2: Run test to verify it fails (Red)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_command_bar_unified_structure -v
```
Expected: FAIL (`class="command-bar-unified"` not found).

- [ ] **Step 3: Refactor command_bar.html**

In [`agy_dash/ui/templates/partials/command_bar.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/command_bar.html#L1-L103):
1. Consolidate into `.command-bar-unified` (54px height):
   - Brand title `ANTIGRAVITY // TELEMETRY` with emerald pulse and live mini-badges (`Tokens`, `Metered API`).
   - Center segmented navigation tabs (`01 // COMMAND`, `02 // SESSIONS`, `03 // ECONOMICS`).
   - Right action deck:
     - Filter Deck Toggle button: `<button type="button" id="filter-deck-toggle" class="btn btn-filter-toggle" onclick="toggleFilterDeck()"><svg class="icon"><use href="#icon-filter"/></svg><span>Filters</span><span class="filter-pill-summary">{{ filters.model_id }} · {{ ctx.currency }}</span></button>`.
     - Theme Toggle with `<use href="#icon-theme"/>`.
     - Rescan button with `<use href="#icon-refresh"/>`.
     - Sync & DB button with `<use href="#icon-database"/>`.
2. Wrap the filter controls (`RANGE`, `MODEL`, `CURRENCY`, `FX`, `SUB`) inside a collapsible container `<div id="global-filter-deck" class="filter-deck-panel">` that toggles open/closed without permanently taking up vertical page space.
3. Remove inline `onchange="this.form.requestSubmit()"` from `<select name="model">` and `<select name="currency">`, adding an explicit "Apply" submit button to prevent jarring full-page re-submits.

- [ ] **Step 4: Run test to verify it passes (Green)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_command_bar_unified_structure -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/partials/command_bar.html tests/test_web_app.py
git commit -m "feat: unify command bar into single 54px header with collapsible filter deck and SVG icons"
```

---

### Task 5: Command View Metric Hierarchy & 2-Tier Bento Grid

**Wave:** 4  
**Depends on:** Task 1, Task 3  
**Files Touched:**
- Modify: `agy_dash/ui/templates/partials/view_command.html`
- Modify: `tests/test_ui_views.py`

- [ ] **Step 1: Write Failing Test in test_ui_views.py**

In [`tests/test_ui_views.py`](file:///D:/Code/AntigravityUsageDashboard/tests/test_ui_views.py#L49-L77), add a test using the globally available `client` fixture verifying that `/?view=command` renders the new `.hero-kpi-matrix` and SVG icons in KPI cards:

```python
def test_command_view_hero_matrix_structure(client):
    res = client.get("/?view=command")
    assert res.status_code == 200
    assert 'class="hero-kpi-matrix"' in res.text
    assert '<svg class="icon"><use href="#icon-zap"' in res.text
    assert 'chart-daily-burn' in res.text
    assert 'chart-token-mix' in res.text
```

- [ ] **Step 2: Run test to verify it fails (Red)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_ui_views.py::test_command_view_hero_matrix_structure -v
```
Expected: FAIL (`class="hero-kpi-matrix"` not found).

- [ ] **Step 3: Redesign view_command.html Layout**

In [`agy_dash/ui/templates/partials/view_command.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_command.html#L1-L108):
1. Replace two 4-column `.kpi-strip` rows with a unified 4-quadrant `.hero-kpi-matrix`:
   - Quadrant 1: **Total Ingestion** (`<use href="#icon-zap"/>`, Tokens value, active days, fresh/cached ratio pill).
   - Quadrant 2: **Equivalent API Cost** (`<use href="#icon-coins"/>`, Modeled value, currency badge, pricing note tooltip).
   - Quadrant 3: **Cache Efficiency** (`<use href="#icon-shield-check"/>`, Hit rate percentage, cache savings estimate).
   - Quadrant 4: **System Activity** (`<use href="#icon-cpu"/>`, Active days, sessions footprint, waste proxy indicator).
2. Render KPI icons using vector SVG tags: `<svg class="icon"><use href="#{{ kpi.icon }}"/></svg> {{ kpi.lbl }}`.
3. Consolidate verbose standalone `.callout` boxes into subtle info dismissible chips or tooltip triggers beside the card headers.
4. Organize the Bento Grid into two balanced visual tiers:
   - Tier 1: `col-8` Daily Burn Chart + `col-4` Token Distribution & Cost Burden Donut.
   - Tier 2: `col-7` Workspace Attribution with paginated table + `col-5` Context Eviction signals and Heaviest Days list.

- [ ] **Step 4: Run test to verify it passes (Green)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_ui_views.py::test_command_view_hero_matrix_structure -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/partials/view_command.html tests/test_ui_views.py
git commit -m "feat: consolidate Command view into Hero KPI matrix and tiered Bento grid with SVG icons"
```

---

### Task 6: Sessions View Progressive Disclosure (3 Sub-Tabs) & JS Runtime

**Wave:** 5  
**Depends on:** Task 1, Task 2, Task 3  
**Files Touched:**
- Modify: `agy_dash/ui/templates/partials/view_sessions.html`
- Modify: `agy_dash/ui/static/js/app.js`

- [ ] **Step 1: Write Verification Test for Sub-Tabs**

Verify through `client` that `view=sessions` renders the 3 sub-navigation tabs and their respective pane containers:

```python
# Verification snippet
def test_sessions_view_subtab_structure(client):
    res = client.get("/?view=sessions")
    assert res.status_code == 200
    assert 'data-subtab-target="tab-workload"' in res.text
    assert 'data-subtab-target="tab-swarm"' in res.text
    assert 'data-subtab-target="tab-reliability"' in res.text
    assert 'id="tab-workload"' in res.text
    assert 'id="tab-swarm"' in res.text
    assert 'id="tab-reliability"' in res.text
```

- [ ] **Step 2: Run test to verify current state (Red)**

Run:
```bash
.\.venv\Scripts\python.exe -c "
import tests.conftest as c; from fastapi.testclient import TestClient; import app as app_module
client = TestClient(app_module.app)
res = client.get('/?view=sessions')
assert 'data-subtab-target=\"tab-workload\"' in res.text
"
```
Expected: AssertionError (sub-tab targets not yet present).

- [ ] **Step 3: Implement Sub-Tabs in view_sessions.html & Client Runtime in app.js**

1. In [`agy_dash/ui/templates/partials/view_sessions.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_sessions.html#L1-L203):
   - Add a sticky sub-navigation bar:
     ```html
     <div class="subtab-bar" role="tablist">
       <button type="button" class="subtab-btn active" data-subtab-target="tab-workload" role="tab">01 // Leaderboard & Directory</button>
       <button type="button" class="subtab-btn" data-subtab-target="tab-swarm" role="tab">02 // Swarm & Agent Coordination</button>
       <button type="button" class="subtab-btn" data-subtab-target="tab-reliability" role="tab">03 // Reliability & Diagnostics</button>
     </div>
     ```
   - Partition into 3 panes:
     - `tab-workload`: Filter bar (Kind pills + Search), Session Workload KPIs, Top Sessions chart, Session Class Split chart, Session Leaderboard table.
     - `tab-swarm`: Swarm KPIs, Time Budget chart, Thinking Ratio chart, Tool Mix chart, MCP Server chart, Model Switches chart, Artifacts table.
     - `tab-reliability`: Context & Failure KPIs, Failure Steps Daily chart, Failure Signatures table, Slowest Shell Commands, User Approval Denials.
   - Update KPI card templates to render `<svg class="icon"><use href="#{{ kpi.icon }}"/></svg>`.
2. In [`agy_dash/ui/static/js/app.js`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/static/js/app.js#L50-L115):
   - Implement `window.toggleFilterDeck()` to toggle `.open` on `#global-filter-deck`.
   - Implement subtab switching: clicking `.subtab-btn` toggles `.active` on buttons and `.subtab-pane`, and triggers `chart.resize()` on newly revealed ECharts instances.
   - Implement drawer tab switching: clicking `.drawer-tab-btn` toggles `.active` on drawer panels.
   - Implement global `keydown` listener for `Escape`: closes any open `.drawer` and closes `#global-filter-deck`.

- [ ] **Step 4: Verify Sub-Tabs rendered (Green)**

Run:
```bash
.\.venv\Scripts\python.exe -c "
from fastapi.testclient import TestClient; import app as app_module
client = TestClient(app_module.app)
res = client.get('/?view=sessions')
assert 'data-subtab-target=\"tab-workload\"' in res.text
assert 'id=\"tab-workload\"' in res.text
assert 'id=\"tab-swarm\"' in res.text
assert 'id=\"tab-reliability\"' in res.text
print('Sessions sub-tabs verified successfully')
"
```
Expected: `Sessions sub-tabs verified successfully`

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/partials/view_sessions.html agy_dash/ui/static/js/app.js
git commit -m "feat: implement 3 progressive disclosure sub-tabs and interactive JS runtime in Sessions view"
```

---

### Task 7: Economics View Segmented Switcher (Forecast vs What-If Simulator)

**Wave:** 6  
**Depends on:** Task 1, Task 3  
**Files Touched:**
- Modify: `agy_dash/ui/templates/partials/view_economics.html`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write Verification Test in test_web_app.py**

In [`tests/test_web_app.py`](file:///D:/Code/AntigravityUsageDashboard/tests/test_web_app.py#L47-L51), add a test asserting that `view=economics` contains the segmented stage switcher:

```python
def test_economics_view_segmented_switcher(client):
    res = client.get("/?view=economics")
    assert res.status_code == 200
    assert 'class="economics-switcher subtab-bar"' in res.text
    assert 'data-econ-stage="forecast"' in res.text
    assert 'data-econ-stage="simulator"' in res.text
```

- [ ] **Step 2: Run test to verify it fails (Red)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_economics_view_segmented_switcher -v
```
Expected: FAIL (`class="economics-switcher subtab-bar"` not found).

- [ ] **Step 3: Implement Segmented Switcher in view_economics.html**

In [`agy_dash/ui/templates/partials/view_economics.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/view_economics.html#L1-L8):
1. Replace the plain vertical stacking of `#forecast-stage-container` and `#lab-stage-container` with an interactive segmented stage switcher:
   ```html
   <div class="economics-switcher subtab-bar" role="tablist">
     <button type="button" class="subtab-btn active" data-econ-stage="forecast" onclick="switchEconStage('forecast')">
       01 // Forecasting Engine
     </button>
     <button type="button" class="subtab-btn" data-econ-stage="simulator" onclick="switchEconStage('simulator')">
       02 // What-If Simulator & Model Lab
     </button>
   </div>
   <div id="forecast-stage-pane" class="econ-stage-pane active">
     <div id="forecast-stage-container">{% include "partials/forecast_stage.html" %}</div>
   </div>
   <div id="lab-stage-pane" class="econ-stage-pane" style="display:none;">
     <div id="lab-stage-container">{% include "partials/lab_stage.html" %}</div>
   </div>
   ```
2. In `app.js`, add `window.switchEconStage(stage)` to toggle display between `forecast-stage-pane` and `lab-stage-pane` and call `resize()` on any newly shown charts.

- [ ] **Step 4: Run test to verify it passes (Green)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_economics_view_segmented_switcher -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/partials/view_economics.html tests/test_web_app.py
git commit -m "feat: add segmented switcher separating Forecast and What-If Simulator in Economics view"
```

---

### Task 8: Slide-Over Drawers Refactoring (Tabbed Session Inspector & Status Cards)

**Wave:** 7  
**Depends on:** Task 2, Task 6  
**Files Touched:**
- Modify: `agy_dash/ui/templates/partials/sync_drawer.html`
- Modify: `agy_dash/ui/templates/partials/session_detail.html`

- [ ] **Step 1: Write Verification Test**

Verify that rendering session detail contains the new `.drawer-tab-bar` tabs:

```python
# Verification snippet
def test_session_detail_tabbed_structure(client, usage):
    sid = usage.sessions["session_id"].iloc[0]
    res = client.get(f"/partials/session-detail/{sid}")
    assert res.status_code == 200
    assert 'class="drawer-tab-bar subtab-bar"' in res.text
```

- [ ] **Step 2: Run verification to check current state (Red)**

Run:
```bash
.\.venv\Scripts\python.exe -c "
from fastapi.testclient import TestClient; import app as app_module
client = TestClient(app_module.app)
res = client.get('/partials/session-detail/26082efd')
assert 'class=\"drawer-tab-bar subtab-bar\"' in res.text
"
```
Expected: AssertionError (drawer tabs not yet present).

- [ ] **Step 3: Refactor sync_drawer.html and session_detail.html**

1. In [`agy_dash/ui/templates/partials/session_detail.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/session_detail.html#L1-L90):
   - Replace the stacked sequence of 4 long tables with clean tabs:
     ```html
     <div class="drawer-tab-bar subtab-bar">
       <button type="button" class="subtab-btn active" onclick="switchDrawerTab(this, 'dtab-overview')">Overview</button>
       <button type="button" class="subtab-btn" onclick="switchDrawerTab(this, 'dtab-tools')">Tools</button>
       <button type="button" class="subtab-btn" onclick="switchDrawerTab(this, 'dtab-commands')">Commands</button>
       <button type="button" class="subtab-btn" onclick="switchDrawerTab(this, 'dtab-failures')">Failures</button>
     </div>
     ```
   - Place `Tool Invocations`, `Shell Command Executions`, and `Session Failures` inside their respective tab panes.
2. In [`agy_dash/ui/templates/partials/sync_drawer.html`](file:///D:/Code/AntigravityUsageDashboard/agy_dash/ui/templates/partials/sync_drawer.html#L1-L83):
   - Organize into 3 distinct visual cards: "Telemetry Source Health", "Snapshot Ledger Counts", and "Live Extractor & Logs".
   - Replace emoji buttons with clean vector SVG buttons (`<svg class="icon"><use href="#icon-refresh"/></svg>`).

- [ ] **Step 4: Verify drawer tabs rendered (Green)**

Run:
```bash
.\.venv\Scripts\python.exe -c "
from fastapi.testclient import TestClient; import app as app_module
client = TestClient(app_module.app)
res = client.get('/partials/session-detail/26082efd')
assert 'class=\"drawer-tab-bar subtab-bar\"' in res.text; print('Drawer tabs verified successfully')
"
```
Expected: `Drawer tabs verified successfully`

- [ ] **Step 5: Commit**

```bash
git add agy_dash/ui/templates/partials/session_detail.html agy_dash/ui/templates/partials/sync_drawer.html
git commit -m "feat: polish slide-over drawers with tabbed session inspector and clean status cards"
```

---

### Task 9: Router Deep-Linking & Template Context for Sub-Tabs and Stages

**Wave:** 8  
**Depends on:** Task 6, Task 7  
**Files Touched:**
- Modify: `app.py`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Write Strict Failing Test in test_web_app.py (No Fallback Clauses)**

In [`tests/test_web_app.py`](file:///D:/Code/AntigravityUsageDashboard/tests/test_web_app.py#L37-L51), add a test asserting that query parameters for `subtab` or `stage` in `app.py` set the `.active` class on the requested pane:

```python
def test_subtab_query_parameters(client):
    res_swarm = client.get("/?view=sessions&subtab=swarm")
    assert res_swarm.status_code == 200
    assert 'class="subtab-pane active" id="tab-swarm"' in res_swarm.text

    res_rel = client.get("/?view=sessions&subtab=reliability")
    assert res_rel.status_code == 200
    assert 'class="subtab-pane active" id="tab-reliability"' in res_rel.text

    res_econ = client.get("/?view=economics&stage=simulator")
    assert res_econ.status_code == 200
    assert 'id="lab-stage-pane" class="econ-stage-pane active"' in res_econ.text
```

- [ ] **Step 2: Run test to verify it fails (Red)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_subtab_query_parameters -v
```
Expected: FAIL (`class="subtab-pane active" id="tab-swarm"` not found).

- [ ] **Step 3: Update app.py context handling**

In [`app.py`](file:///D:/Code/AntigravityUsageDashboard/app.py#L48-L86):
1. In `index()`, extract `subtab = query_params.get("subtab", "workload")` and `stage = query_params.get("stage", "forecast")`.
2. Pass `subtab` and `stage` into `TemplateResponse` context dict so server-side rendered initial states match deep-linked query URLs:
   ```python
   return templates.TemplateResponse(request, "base.html", {
       "request": request, "ctx": ctx, "filters": filters,
       "model_ids": model_ids, "vm": vm, "runner_state": runner_state,
       "sync_data": sync_data, "subtab": subtab, "stage": stage,
   })
   ```
3. Update `view_sessions.html` and `view_economics.html` conditional classes to check `subtab` and `stage` from context (e.g., `{% if subtab == 'swarm' %}active{% endif %}`).

- [ ] **Step 4: Run test to verify it passes (Green)**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/test_web_app.py::test_subtab_query_parameters -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_web_app.py
git commit -m "feat: pass active subtab and stage query parameters through app router"
```

---

### Task 10: Full Regression & Visual Validation Suite

**Wave:** 9  
**Depends on:** Task 1, Task 2, Task 3, Task 4, Task 5, Task 6, Task 7, Task 8, Task 9  
**Files Touched:**
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Run Full Pytest Suite**

Run:
```bash
.\.venv\Scripts\pytest.exe tests/ -v
```
Expected: All tests pass with zero failures.

- [ ] **Step 2: Check for Emoji Cleanliness Across View Models & Templates**

Ensure no raw structural emojis remain:
```bash
.\.venv\Scripts\python.exe -c "
from pathlib import Path
for p in Path('agy_dash/ui/templates').rglob('*.html'):
    text = p.read_text(encoding='utf-8')
    for emo in ['⚡', '📥', '📤', '💰', '🤖', '📐', '🌓', '🔄']:
        if emo in text:
            print(f'Warning: emoji {emo} found in {p.name}')
"
```
Expected: Clean output (no structural emojis).

- [ ] **Step 3: Validate Live HTTP Endpoints on Local Server**

Run requests against `http://127.0.0.1:8501` to verify all views and partials return HTTP 200:
```bash
.\.venv\Scripts\python.exe -c "
import urllib.request
for url in ['http://127.0.0.1:8501/?view=command', 'http://127.0.0.1:8501/?view=sessions', 'http://127.0.0.1:8501/?view=economics']:
    req = urllib.request.urlopen(url)
    assert req.status == 200, f'Failed on {url}'
    print(f'Checked {url} -> 200 OK')
"
```
Expected: All 3 view routes return HTTP 200 OK.

- [ ] **Step 4: Commit**

```bash
git add tests/test_web_app.py
git commit -m "test: complete visual regression and end-to-end verification"
```
