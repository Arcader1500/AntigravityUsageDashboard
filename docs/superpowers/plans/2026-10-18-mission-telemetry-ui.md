# Mission Telemetry Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit + Plotly dashboard with a FastAPI + Jinja2 + HTMX + Apache ECharts web app. It has 3 workspaces (`01 // COMMAND`, `02 // SESSIONS`, `03 // ECONOMICS`), a sticky command bar with live telemetry HUD, and 3 slide-over drawers (Operations/Sync, Session Inspector, Price Catalog). The analytics core stays completely unchanged.

**Architecture:** `app.py` is a FastAPI app bound to `127.0.0.1`. Each request is stateless: filters travel as query parameters, and `agy_dash/ui/state.py` parses and validates them, caches the scans (TTL), and builds the shared `Ctx`. `agy_dash/ui/views.py` turns `Ctx` and `DeepData` into plain dicts: KPI cards, formatted tables, honesty notes, and ECharts option dicts from `agy_dash/ui/charts.py`. Jinja templates render those dicts. HTMX swaps workspaces via `hx-target="#workspace-canvas"` and `hx-swap="outerHTML"`, while `static/js/app.js` manages chart hydration via Apache ECharts and handles drawer and theme toggling.

**Tech Stack:** Python 3.11, FastAPI, Uvicorn, Jinja2, python-multipart, HTMX 2.0.3 (vendored), Apache ECharts 5.5.1 (vendored), pandas, numpy, pytest + FastAPI `TestClient` (httpx).

**Spec:** `docs/superpowers/specs/2026-10-18-mission-telemetry-ui-design.md`

---

## Plan-time decisions & Critic Findings (Revised)

1. **Alpine.js is dropped** (YAGNI). Client behavior consists of drawer toggling, theme switching, and ECharts hydration, implemented in ~80 lines of pure vanilla JS in `agy_dash/ui/static/js/app.js`.
2. **Offline-safe 127.0.0.1**: HTMX 2.0.3 and ECharts 5.5.1 are locally vendored under `agy_dash/ui/static/vendor/` with license notices.
3. **No new analytics or schema modifications**: `agy_dash/{config,source,pricing,metrics,deep,stats,jobs,snapshots}.py` remain read-only dependencies.
4. **All 14 Plan-Critic findings resolved**:
   - **F-01**: Model benchmark lookup compares string `model_id` to catalog entries (`e.model_id` / `price_on`), preventing empty benchmark displays.
   - **F-02**: Workspace swapping uses `hx-swap="outerHTML"` and `hx-include="#global-filter-form"`, eliminating DOM nesting and preserving filter state across tabs. Nav tabs include active class synchronization.
   - **F-03**: Complete Stage 1 Forecast and Stage 2 What-If controls, cadence charts, daily schedule ledger, and `/partials/forecast-stage` & `/partials/lab-stage` endpoints implemented.
   - **F-04**: Complete 3-Zone Sessions workspace implemented with search, kind pills, Subagent Swarm KPIs, Context Pressure KPIs, and all 5 missing charts (`thinking_ratio`, `tool_mix`, `model_switches`, `mcp_invocations`, `failure_daily`).
   - **F-05**: Sync drawer includes `metrics.verify_consistency()`, source health indicators, collapsible stdout/stderr viewers, and SQLite run ledger history. Polling (`every 2s`) occurs only while jobs are running.
   - **F-06**: Dedicated `partials/session_detail.html` partial replaces raw inline string in `app.py`, rendering session tools, commands, failures, and metadata.
   - **F-07**: Command bar includes total tokens badge, API cost badge, currency selector (`INR`, `USD`, `EUR`, `GBP`), FX rate input, subscription spend input, `POST /api/refresh`, and live job indicator.
   - **F-08**: Workspace attribution chart (`workspace_chart`), `ctx.price_note` banner, and waste proxy engineering disclaimer banner rendered.
   - **F-09**: ECharts confidence band uses stacked series (P10 transparent baseline + P90-P10 delta area) for accurate uncertainty ribbons.
   - **F-10**: All Cartesian charts define fallback `xAxis` and `yAxis` on empty data frames to prevent JS crashes. `daily_burn` includes `dataZoom` slider.
   - **F-11**: Debounced global window resize listener and explicit chart instance disposal (`chart.dispose()`) on HTMX swap prevent memory leaks.
   - **F-12**: Explicit network prerequisites flagged for dependency installation and CDN asset vendoring.
   - **F-13**: Index cleaned with `git restore --staged .` before branch creation.
   - **F-14**: Dead code block removed from `state.py`.

---

## File Structure

```text
AntigravityUsageDashboard/
├── app.py                           # FastAPI application entry point
├── run.ps1                          # Launcher script: uvicorn app:app --port 8501
├── requirements.txt                 # Updated: FastAPI stack replacing Streamlit & Plotly
├── agy_dash/
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── common.py                # Formatting helpers, color palettes, Ctx dataclass
│   │   ├── state.py                 # TTLCache, filter parsing, context building
│   │   ├── charts.py                # Pure ECharts option dict builders
│   │   ├── views.py                 # Workspace view-model builders
│   │   ├── static/
│   │   │   ├── css/telemetry.css    # High-Craft Mission Telemetry stylesheet
│   │   │   ├── js/app.js            # ECharts hydration, resize listener, theme & drawers
│   │   │   └── vendor/
│   │   │       ├── htmx.min.js      # Vendored HTMX 2.0.3
│   │   │       ├── echarts.min.js   # Vendored Apache ECharts 5.5.1
│   │   │       └── README.md
│   │   └── templates/
│   │       ├── base.html            # Main HTML shell, command bar, canvas, drawers
│   │       ├── error.html           # Diagnostic view for errors
│   │       └── partials/
│   │           ├── command_bar.html     # Sticky command bar + HUD + filters
│   │           ├── view_command.html    # 01 // COMMAND workspace
│   │           ├── view_sessions.html   # 02 // SESSIONS workspace (3 zones)
│   │           ├── view_economics.html  # 03 // ECONOMICS workspace (Stages 1 & 2)
│   │           ├── forecast_stage.html  # Forecast stage partial
│   │           ├── lab_stage.html       # What-If simulator stage partial
│   │           ├── sync_drawer.html     # Operations, health, consistency & snapshots
│   │           ├── job_status.html      # Extractor job status widget (conditional poll)
│   │           ├── session_drawer.html  # Session inspector drawer container
│   │           ├── session_detail.html  # Deep session inspection partial
│   │           └── catalog_drawer.html  # Interactive price catalog table
└── tests/
    ├── test_ui_common.py            # Tests for common.py
    ├── test_ui_state.py             # Tests for state.py & filter validation
    ├── test_ui_charts.py            # Tests for charts.py option builders
    ├── test_ui_views.py             # Tests for views.py view models
    ├── test_web_app.py              # TestClient end-to-end tests for FastAPI app
    └── test_extractor_integration.py# Extractor integration tests (retained from smoke)
```

**Deleted legacy files:**
- `agy_dash/ui/overview.py`, `explorer.py`, `deep_signals.py`, `lab.py`, `forecast.py`, `data_jobs.py`
- `.streamlit/config.toml`
- `tests/test_app_smoke.py`

---

## Tasks

### Task 0: Feature Branch & Working Tree Cleanliness

- [ ] **Step 1: Clean the index and branch out**
```powershell
git restore --staged .
git switch -c feat/mission-telemetry-ui
```

- [ ] **Verify:**
```powershell
git branch --show-current
git status --short
```
Expected: `feat/mission-telemetry-ui` printed, index is clean.

---

### Task 1: Dependencies

**Files:** Modify `requirements.txt`

> [!NOTE]
> Network access to PyPI is required for package installation. If working in an air-gapped environment, point pip/uv to a local wheelhouse.

- [ ] **Step 1: Update `requirements.txt`:**
```text
# Antigravity Usage Dashboard - runtime + test dependencies
fastapi>=0.110,<1
uvicorn>=0.29
jinja2>=3.1
python-multipart>=0.0.9
pandas>=2.1
numpy>=1.26
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 2: Install dependencies:**
```powershell
uv pip install -r requirements.txt --python .venv\Scripts\python.exe
```

- [ ] **Verify:**
```powershell
.venv\Scripts\python.exe -c "import fastapi, uvicorn, jinja2, multipart, httpx; from fastapi.testclient import TestClient; print('FastAPI', fastapi.__version__)"
```
Expected: prints `FastAPI 0.110.x` (or newer) with exit code 0.

- [ ] **Step 3: Commit:**
```bash
git add requirements.txt
git commit -m "build: swap streamlit/plotly for fastapi stack" -- requirements.txt
```

---

### Task 2: Vendor Frontend Libraries (Offline-Safe)

**Files:** Create `agy_dash/ui/static/vendor/htmx.min.js`, `agy_dash/ui/static/vendor/echarts.min.js`, `agy_dash/ui/static/vendor/README.md`

> [!NOTE]
> Outbound HTTPS access to `cdn.jsdelivr.net` is required for downloading vendor files.

- [ ] **Step 1: Download pinned vendor assets:**
```powershell
New-Item -ItemType Directory -Force agy_dash\ui\static\vendor | Out-Null
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/htmx.org@2.0.3/dist/htmx.min.js" -OutFile "agy_dash\ui\static\vendor\htmx.min.js" -TimeoutSec 30
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js" -OutFile "agy_dash\ui\static\vendor\echarts.min.js" -TimeoutSec 60
```

- [ ] **Step 2: Create `agy_dash/ui/static/vendor/README.md`:**
```markdown
# Vendored frontend libraries

Served locally so the dashboard works offline on 127.0.0.1. Do not edit; replace whole files to upgrade.

| File | Version | Source | License |
|---|---|---|---|
| htmx.min.js | 2.0.3 | https://cdn.jsdelivr.net/npm/htmx.org@2.0.3/dist/htmx.min.js | 0BSD |
| echarts.min.js | 5.5.1 | https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js | Apache-2.0 |
```

- [ ] **Verify:**
```powershell
(Get-Item agy_dash\ui\static\vendor\htmx.min.js).Length -gt 40000
(Get-Item agy_dash\ui\static\vendor\echarts.min.js).Length -gt 900000
```
Expected: Both return `True`.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/static/vendor
git commit -m "build: vendor htmx 2.0.3 and echarts 5.5.1" -- agy_dash/ui/static/vendor
```

---

### Task 3: Delete Legacy Streamlit UI & Extract Extractor Tests

**Files:**
- Create `tests/test_extractor_integration.py`
- Delete `agy_dash/ui/overview.py`, `explorer.py`, `deep_signals.py`, `lab.py`, `forecast.py`, `data_jobs.py`, `.streamlit/config.toml`, `tests/test_app_smoke.py`, `app.py`

- [ ] **Step 1: Create `tests/test_extractor_integration.py`:**
```python
"""Integration with the real extractor script (outside this repo).

Skipped when the script is absent. Everything UI-related is covered
hermetically in tests/test_web_app.py.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from agy_dash.jobs import JobRunner
from tests.conftest import build_brain

REAL_EXTRACTOR = Path.home() / "docs" / "superpowers" / "scripts" / "agy_usage.py"


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    synthetic_brain = build_brain(tmp_path)
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "brain_root": str(synthetic_brain),
        "extractor_script": str(REAL_EXTRACTOR),
        "python_executable": os.sys.executable,
        "db_path": str(tmp_path / "snap.db"),
        "log_dir": str(tmp_path / "logs"),
        "reporting_currency": "INR",
        "usd_to_inr": 88.0,
        "default_model": "claude-sonnet",
        "subscription": {"amount": 2000.0, "currency": "INR"},
    }))
    monkeypatch.setenv("ANTIGRAVITY_DASH_CONFIG", str(cfg_path))
    return cfg_path


@pytest.mark.skipif(not REAL_EXTRACTOR.exists(), reason="real extractor script not found at ~/docs/superpowers/scripts/agy_usage.py")
def test_real_extractor_runs_cleanly(app_env, tmp_path):
    runner = JobRunner(
        python_executable=os.sys.executable,
        extractor_script=REAL_EXTRACTOR,
        log_dir=tmp_path / "logs",
        last_run_path=tmp_path / "logs" / "last_run.json",
        lock_path=tmp_path / "logs" / "extractor.lock",
    )
    runner.start("all")
    for _ in range(60):
        runner.poll()
        if not runner.state.running:
            break
        import time
        time.sleep(0.5)
    assert runner.state.status == "success", f"job failed: {runner.state.message} stderr={runner.state.read_stderr()}"
    assert runner.state.exit_code == 0
```

- [ ] **Step 2: Delete legacy Streamlit files:**
```bash
git rm agy_dash/ui/overview.py agy_dash/ui/explorer.py agy_dash/ui/deep_signals.py agy_dash/ui/lab.py agy_dash/ui/forecast.py agy_dash/ui/data_jobs.py tests/test_app_smoke.py app.py .streamlit/config.toml
```

- [ ] **Verify:**
```powershell
.venv\Scripts\python.exe -m pytest tests/test_extractor_integration.py
```
Expected: passes or skips with `reason="real extractor script not found..."`.

- [ ] **Step 3: Commit:**
```bash
git add tests/test_extractor_integration.py
git commit -m "refactor: delete streamlit views and smoke test, keep extractor integration" -- agy_dash/ui tests/test_extractor_integration.py app.py .streamlit/config.toml
```

---

### Task 4: Common Data Structures & Color Systems

**Files:** Rewrite `agy_dash/ui/common.py`. Test: `tests/test_ui_common.py`

- [ ] **Step 1: Write `tests/test_ui_common.py`:**
```python
import pytest
from agy_dash.ui import common


def test_fmt_tokens():
    assert common.fmt_tokens(0) == "0"
    assert common.fmt_tokens(999) == "999"
    assert common.fmt_tokens(1_500) == "1.5K"
    assert common.fmt_tokens(2_450_000) == "2.45M"
    assert common.fmt_tokens(3_100_000_000) == "3.10B"


def test_fmt_money():
    assert common.fmt_money(0, "INR") == "₹0.00"
    assert common.fmt_money(1250.5, "INR") == "₹1,250.50"
    assert common.fmt_money(12.34, "USD") == "$12.34"
    assert common.fmt_money(12.34, "EUR") == "€12.34"
    assert common.fmt_money(12.34, "GBP") == "£12.34"


def test_fmt_pct():
    assert common.fmt_pct(0.1234) == "12.3%"
    assert common.fmt_pct(0.1234, decimals=0) == "12%"
    assert common.fmt_pct(None) == "-"


def test_colors_palette():
    dark = common.colors("dark")
    light = common.colors("light")
    assert dark["bg"] == "#090A0F"
    assert light["bg"] == "#F6F7F9"
    assert "fresh" in dark and "cached" in dark and "cost" in dark
```

- [ ] **Step 2: Write `agy_dash/ui/common.py`:**
```python
"""Theme, formatting, and the shared request context. Framework-free."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .. import metrics, pricing, source
from ..config import Config

DARK = {
    "bg": "#090A0F",
    "panel": "#10121A",
    "panel_solid": "#10121A",
    "panel_alt": "#161922",
    "border": "#1E2230",
    "border_highlight": "rgba(56, 189, 248, 0.4)",
    "text": "#F1F5F9",
    "text_bright": "#FFFFFF",
    "muted": "#94A3B8",
    "dim": "#64748B",
    "accent": "#38BDF8",     # Cyan
    "fresh": "#38BDF8",      # Fresh input tokens
    "cached": "#10B981",     # Cached tokens (Emerald)
    "output": "#F59E0B",     # Output & thinking tokens (Amber)
    "cost": "#A78BFA",       # Cost burn (Violet)
    "warn": "#FBBF24",       # Warning notice
    "bad": "#F43F5E",        # Error / friction (Rose)
    "grid": "rgba(255, 255, 255, 0.05)",
}

LIGHT = {
    "bg": "#F6F7F9",
    "panel": "#FFFFFF",
    "panel_solid": "#FFFFFF",
    "panel_alt": "#F1F4F8",
    "border": "#E2E8F0",
    "border_highlight": "rgba(2, 132, 199, 0.4)",
    "text": "#0F172A",
    "text_bright": "#020617",
    "muted": "#64748B",
    "dim": "#94A3B8",
    "accent": "#0284C7",
    "fresh": "#0284C7",
    "cached": "#059669",
    "output": "#D97706",
    "cost": "#7C3AED",
    "warn": "#B45309",
    "bad": "#E11D48",
    "grid": "rgba(0, 0, 0, 0.05)",
}

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def colors(theme: str) -> dict[str, str]:
    return LIGHT if str(theme).lower() == "light" else DARK


def currency_symbol(curr: str) -> str:
    return CURRENCY_SYMBOLS.get(curr.upper(), f"{curr} ")


def fmt_tokens(n: float | int | None) -> str:
    if n is None:
        return "-"
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K" if n < 1e5 else f"{n / 1e3:.0f}K"
    return f"{int(n):,}"


def fmt_money(val: float | None, curr: str = "INR") -> str:
    if val is None:
        return "-"
    sym = currency_symbol(curr)
    return f"{sym}{val:,.2f}"


def fmt_rate(val: float | None, curr: str = "INR") -> str:
    if val is None:
        return "-"
    sym = currency_symbol(curr)
    return f"{sym}{val:,.4f}/Mtok"


def fmt_pct(val: float | None, decimals: int = 1) -> str:
    if val is None:
        return "-"
    return f"{val * 100:.{decimals}f}%"


@dataclass
class Ctx:
    config: Config
    usage: source.UsageData
    sessions: pd.DataFrame
    daily: pd.DataFrame
    catalog: pricing.Catalog
    prices: pricing.PriceEntry
    model_id: str
    price_note: str | None
    currency: str
    usd_inr: float
    subscription_amount: float
    theme: str
    runner: Any
    overview: metrics.Overview

    def to_currency(self, usd: float) -> float:
        return metrics.currency_from_usd(usd, self.currency, self.usd_inr)

    def money(self, usd: float) -> str:
        return fmt_money(self.to_currency(usd), self.currency)


def build_ctx(
    config: Config,
    usage: source.UsageData,
    sessions: pd.DataFrame,
    daily: pd.DataFrame,
    catalog: pricing.Catalog,
    prices: pricing.PriceEntry,
    model_id: str,
    price_note: str | None,
    currency: str,
    usd_inr: float,
    subscription_amount: float,
    theme: str,
    runner: Any,
) -> Ctx:
    overview = metrics.update_overview(
        sessions, daily, prices,
        currency=currency, usd_inr=usd_inr,
        subscription_amount=subscription_amount,
        model_name=prices.name, price_note=price_note,
    )
    return Ctx(
        config=config, usage=usage, sessions=sessions, daily=daily,
        catalog=catalog, prices=prices, model_id=model_id, price_note=price_note,
        currency=currency, usd_inr=usd_inr, subscription_amount=subscription_amount,
        theme=theme, runner=runner, overview=overview,
    )
```

- [ ] **Verify:** `.venv\Scripts\python.exe -m pytest tests/test_ui_common.py`
Expected: 4 passed.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/common.py tests/test_ui_common.py
git commit -m "feat(ui): pure-python common module - formatting, palettes, Ctx dataclass" -- agy_dash/ui/common.py tests/test_ui_common.py
```

---

### Task 5: Request State, TTLCache, & Filter Parsing

**Files:** Create `agy_dash/ui/state.py`. Test: `tests/test_ui_state.py`

- [ ] **Step 1: Write `tests/test_ui_state.py`:**
```python
import datetime as dt
from agy_dash import config as cfgmod
from agy_dash import pricing, source
from agy_dash.ui import state


def test_ttl_cache_returns_cached_or_recomputes():
    c = state.TTLCache(ttl_seconds=60)
    cnt = 0
    def compute():
        nonlocal cnt
        cnt += 1
        return "val"
    assert c.get("k", compute) == "val"
    assert cnt == 1
    assert c.get("k", compute) == "val"
    assert cnt == 1
    c.clear()
    assert c.get("k", compute) == "val"
    assert cnt == 2


def test_parse_filters_handles_currency_and_clamps():
    import pandas as pd
    cfg = cfgmod.get_config()
    dates = pd.date_range("2026-10-05", "2026-10-15")
    daily = pd.DataFrame({"date": dates})
    usage = source.UsageData(pd.DataFrame(), daily, dt.datetime.now(), "/root", [])
    
    # Check currency parsing and defaults
    f = state.parse_filters({"currency": "usd", "start": "2026-10-08", "end": "2026-10-12"}, cfg, usage, ["claude-sonnet"])
    assert f.currency == "USD"
    assert f.start == dt.date(2026, 10, 8)
    assert f.end == dt.date(2026, 10, 12)

    # Clamping test
    f_clamped = state.parse_filters({"start": "2026-10-20", "end": "2026-10-01"}, cfg, usage, ["claude-sonnet"])
    assert f_clamped.start == dt.date(2026, 10, 5)
    assert f_clamped.end == dt.date(2026, 10, 15)
```

- [ ] **Step 2: Write `agy_dash/ui/state.py`:**
```python
"""Stateless request-level state parsing, TTLCache, and Ctx builder."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .. import config as cfgmod
from .. import deep, jobs, pricing, source
from . import common

VIEWS = ("command", "sessions", "economics")
THEMES = ("dark", "light")
CURRENCIES = ("INR", "USD", "EUR", "GBP")
DEFAULT_MODEL = "claude-sonnet"


class PricingError(Exception):
    """Raised when the selected model cannot be priced."""


class TTLCache:
    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, factory: Callable[[], Any]) -> Any:
        now = time.monotonic()
        if key in self._entries:
            ts, val = self._entries[key]
            if now - ts < self.ttl:
                return val
        val = factory()
        self._entries[key] = (now, val)
        return val

    def clear(self) -> None:
        self._entries.clear()


USAGE_CACHE = TTLCache(ttl_seconds=60.0)
DEEP_CACHE = TTLCache(ttl_seconds=300.0)
_RUNNERS: dict[str, jobs.JobRunner] = {}


def clear_all_caches() -> None:
    USAGE_CACHE.clear()
    DEEP_CACHE.clear()


def get_runner(cfg: cfgmod.Config) -> jobs.JobRunner:
    key = str(Path(cfg.log_dir).resolve())
    if key not in _RUNNERS:
        _RUNNERS[key] = jobs.JobRunner(
            python_executable=cfg.python_executable,
            extractor_script=cfg.extractor_script,
            log_dir=cfg.log_dir,
            last_run_path=Path(cfg.log_dir) / "last_run.json",
            lock_path=Path(cfg.log_dir) / "extractor.lock",
        )
    return _RUNNERS[key]


def load_usage(cfg: cfgmod.Config) -> source.UsageData:
    key = f"{cfg.brain_root}:{cfg.extractor_script}"
    return USAGE_CACHE.get(key, lambda: source.load_usage(cfg))


def load_deep(brain_root: str) -> deep.DeepData:
    return DEEP_CACHE.get(brain_root, lambda: deep.scan_deep(brain_root))


def load_catalog() -> list[pricing.PriceEntry]:
    return pricing.load_catalog(pricing.pricing_file())


@dataclass
class FilterParams:
    view: str
    start: dt.date | None
    end: dt.date | None
    model_id: str
    currency: str
    fx: float
    sub: float
    theme: str


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s.strip())
    except ValueError:
        return None


def parse_filters(query: dict[str, Any], cfg: cfgmod.Config, usage: source.UsageData, model_ids: list[str]) -> FilterParams:
    daily = usage.daily
    lo = daily["date"].min().date() if not daily.empty else None
    hi = daily["date"].max().date() if not daily.empty else None
    start = _parse_date(query.get("start")) or lo
    end = _parse_date(query.get("end")) or hi
    if lo is not None:
        start = min(max(start, lo), hi)
        end = min(max(end, lo), hi)
        if start > end:
            start, end = end, start

    default_model = DEFAULT_MODEL if DEFAULT_MODEL in model_ids else (model_ids[0] if model_ids else "")
    model = query.get("model")
    view = query.get("view")
    theme = query.get("theme")
    curr = str(query.get("currency", "")).upper()
    currency = curr if curr in CURRENCIES else cfg.reporting_currency

    def _f(v, d):
        try:
            return max(float(v), 0.0) if v is not None else d
        except (ValueError, TypeError):
            return d

    return FilterParams(
        view=view if view in VIEWS else "command",
        start=start,
        end=end,
        model_id=model if model in model_ids else default_model,
        currency=currency,
        fx=_f(query.get("fx"), cfg.usd_to_inr),
        sub=_f(query.get("sub"), float(cfg.subscription.get("amount", 0.0))),
        theme=theme if theme in THEMES else "dark",
    )


def build_context(cfg: cfgmod.Config, usage: source.UsageData, entries: list[pricing.PriceEntry],
                  filters: FilterParams, runner) -> common.Ctx:
    daily = source.clip_dates(usage.daily, filters.start, filters.end)
    sessions = source.sessions_touching(usage.sessions, filters.start, filters.end)
    catalog = pricing.Catalog(entries)
    on_date = daily["date"].max().date() if not daily.empty else None
    prices, estimate = catalog.price_on(filters.model_id, on_date)
    if prices is None:
        raise PricingError(f"No pricing entry for model '{filters.model_id}'.")
    price_note = None
    if estimate:
        price_note = (f"No price version covers {on_date} for {prices.name}; using the "
                      f"{prices.effective_from} version as an ESTIMATE. Prices are dated - add a "
                      "version in config/pricing.json to be exact." if on_date
                      else catalog.availability_warning(filters.model_id, on_date))
    return common.build_ctx(
        config=cfg, usage=usage, sessions=sessions, daily=daily, catalog=catalog, prices=prices,
        model_id=filters.model_id, price_note=price_note, currency=filters.currency,
        usd_inr=filters.fx, subscription_amount=filters.sub, theme=filters.theme, runner=runner,
    )
```

- [ ] **Verify:** `.venv\Scripts\python.exe -m pytest tests/test_ui_state.py`
Expected: passes.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/state.py tests/test_ui_state.py
git commit -m "feat(ui): request state - TTLCache, filter parsing, currency support" -- agy_dash/ui/state.py tests/test_ui_state.py
```

---

### Task 6: ECharts Option Builders (Pure Data & Robust Styling)

**Files:** Create `agy_dash/ui/charts.py`. Test: `tests/test_ui_charts.py`

- [ ] **Step 1: Write `tests/test_ui_charts.py`:**
```python
import pandas as pd
from agy_dash import pricing, source
from agy_dash.ui import charts, common


def test_empty_chart_returns_valid_axes():
    c = common.colors("dark")
    ctx = common.Ctx(None, None, pd.DataFrame(), pd.DataFrame(), None, None, "m", None, "INR", 88.0, 0.0, "dark", None, None)
    
    # Test that empty data returns xAxis/yAxis instead of empty dictionary to avoid JS crash
    res = charts.daily_burn(ctx)
    assert "xAxis" in res and "yAxis" in res
    assert res["series"] == []


def test_forecast_fan_stacked_ribbon():
    from agy_dash import stats
    dates = pd.date_range("2026-10-01", periods=5)
    obs = pd.DataFrame({"date": dates, "total": [100, 120, 110, 130, 140]})
    fc = stats.Forecast("test", 3, list(pd.date_range("2026-10-06", periods=3)),
                        [10, 10, 10], [20, 20, 20], [30, 30, 30], 5, 120.0, "notes")
    ctx = common.Ctx(None, None, pd.DataFrame(), pd.DataFrame(), None, None, "m", None, "INR", 88.0, 0.0, "dark", None, None)
    opt = charts.forecast_fan(obs, fc, "total", "tokens", ctx)
    assert len(opt["series"]) == 4  # Measured, P10 Floor, Delta Band, P50 Median
    # Check that P10 and Band share the stack key
    assert opt["series"][1]["stack"] == "confidence_band"
    assert opt["series"][2]["stack"] == "confidence_band"
```

- [ ] **Step 2: Write `agy_dash/ui/charts.py`:**
```python
"""Pure ECharts option dict builders. Framework-free."""

from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd

from .. import metrics, stats
from . import common


def _base_chart(c: dict[str, str], title: str | None = None) -> dict[str, Any]:
    opt: dict[str, Any] = {
        "backgroundColor": "transparent",
        "textStyle": {"fontFamily": "Plus Jakarta Sans, sans-serif", "color": c["text"]},
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": c["panel_solid"],
            "borderColor": c["border"],
            "textStyle": {"color": c["text"], "fontFamily": "JetBrains Mono, monospace", "fontSize": 12},
            "axisPointer": {"lineStyle": {"color": c["border"], "type": "dashed"}},
        },
        "grid": {"top": 45, "right": 20, "bottom": 35, "left": 55, "containLabel": True},
    }
    if title:
        opt["title"] = {
            "text": title,
            "textStyle": {"color": c["text"], "fontSize": 13, "fontWeight": 600, "fontFamily": "Syne, sans-serif"},
            "left": 0, "top": 5,
        }
    return opt


def _empty_cartesian(opt: dict[str, Any]) -> dict[str, Any]:
    opt["xAxis"] = {"type": "category", "data": []}
    opt["yAxis"] = [{"type": "value"}]
    opt["series"] = []
    return opt


def daily_burn(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Daily Ingestion & Cost Burn")
    daily = ctx.daily
    if daily.empty:
        return _empty_cartesian(opt)

    attached = metrics.attach_costs(daily, ctx.prices)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in daily["date"]]
    costs = [round(ctx.to_currency(v), 2) for v in attached["cost_usd"]]

    opt["legend"] = {
        "data": ["Fresh Input", "Cached Input", "Output & Reasoning", f"API Cost ({ctx.currency})"],
        "textStyle": {"color": c["muted"], "fontSize": 11},
        "top": 5, "right": 0,
    }
    opt["xAxis"] = {
        "type": "category", "data": dates,
        "axisLine": {"lineStyle": {"color": c["border"]}},
        "axisLabel": {"color": c["muted"], "fontFamily": "JetBrains Mono", "fontSize": 10},
    }
    opt["yAxis"] = [
        {
            "type": "value", "name": "Tokens",
            "splitLine": {"lineStyle": {"color": c["grid"]}},
            "axisLabel": {"color": c["muted"], "fontFamily": "JetBrains Mono", "formatter": "{value}"},
        },
        {
            "type": "value", "name": ctx.currency, "position": "right",
            "splitLine": {"show": False},
            "axisLabel": {"color": c["cost"], "fontFamily": "JetBrains Mono"},
        },
    ]
    opt["series"] = [
        {"name": "Fresh Input", "type": "bar", "stack": "tokens", "color": c["fresh"], "data": daily["fresh_in"].tolist()},
        {"name": "Cached Input", "type": "bar", "stack": "tokens", "color": c["cached"], "data": daily["cached"].tolist()},
        {"name": "Output & Reasoning", "type": "bar", "stack": "tokens", "color": c["output"], "data": daily["output"].tolist()},
        {"name": f"API Cost ({ctx.currency})", "type": "line", "yAxisIndex": 1, "color": c["cost"],
         "smooth": True, "showSymbol": True, "symbolSize": 6, "data": costs},
    ]
    opt["dataZoom"] = [{"type": "slider", "bottom": 0, "height": 18, "textStyle": {"color": c["muted"]}}]
    return opt


def token_mix(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    t = ctx.overview.totals
    opt = _base_chart(c, "Token Distribution")
    opt["tooltip"] = {
        "trigger": "item", "backgroundColor": c["panel_solid"], "borderColor": c["border"],
        "textStyle": {"fontFamily": "JetBrains Mono", "color": c["text"]},
        "formatter": "{b}: <b>{c}</b> ({d}%)",
    }
    opt["series"] = [{
        "type": "pie", "radius": ["55%", "78%"], "avoidLabelOverlap": True,
        "itemStyle": {"borderRadius": 4, "borderColor": c["bg"], "borderWidth": 2},
        "label": {"show": False},
        "data": [
            {"value": t.fresh_in, "name": "Fresh Input", "itemStyle": {"color": c["fresh"]}},
            {"value": t.cached, "name": "Cached Input", "itemStyle": {"color": c["cached"]}},
            {"value": t.output, "name": "Output & Reasoning", "itemStyle": {"color": c["output"]}},
        ],
    }]
    return opt


def cost_burden(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    b = ctx.overview.breakdown_usd
    opt = _base_chart(c, f"Cost Burden by Category ({ctx.currency})")
    opt["tooltip"] = {
        "trigger": "item", "backgroundColor": c["panel_solid"], "borderColor": c["border"],
        "textStyle": {"fontFamily": "JetBrains Mono", "color": c["text"]},
    }
    opt["series"] = [{
        "type": "pie", "radius": ["55%", "78%"], "avoidLabelOverlap": True,
        "itemStyle": {"borderRadius": 4, "borderColor": c["bg"], "borderWidth": 2},
        "label": {"show": False},
        "data": [
            {"value": round(ctx.to_currency(b.get("fresh_usd", 0.0)), 2), "name": "Fresh Input", "itemStyle": {"color": c["fresh"]}},
            {"value": round(ctx.to_currency(b.get("cached_usd", 0.0)), 2), "name": "Cached Input", "itemStyle": {"color": c["cached"]}},
            {"value": round(ctx.to_currency(b.get("output_usd", 0.0)), 2), "name": "Output", "itemStyle": {"color": c["output"]}},
        ],
    }]
    return opt


def workspace_attribution(ws_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Workspace Token Attribution")
    if ws_df.empty:
        return _empty_cartesian(opt)
    df = ws_df.nlargest(8, "total").iloc[::-1]
    opt["grid"] = {"top": 35, "right": 30, "bottom": 25, "left": 130}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": [p[:22] for p in df["project"]], "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"name": "Tokens", "type": "bar", "color": c["accent"], "data": df["total"].tolist()}]
    return opt


def cache_thrash(step_days_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Context Eviction (Zero-Cache Days)")
    if step_days_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in step_days_df["date"]]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = [
        {"type": "value", "name": "Misses", "splitLine": {"lineStyle": {"color": c["grid"]}}},
        {"type": "value", "name": "Calls", "position": "right", "splitLine": {"show": False}},
    ]
    opt["series"] = [
        {"name": "Zero-Cache Miss Calls", "type": "bar", "color": c["bad"], "data": step_days_df["cache_miss_calls"].tolist()},
        {"name": "Total Model Calls", "type": "line", "yAxisIndex": 1, "color": c["accent"], "data": step_days_df["model_calls"].tolist()},
    ]
    return opt


def top_sessions(sessions_df: pd.DataFrame, top_n: int, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Top {top_n} Heavyweight Sessions")
    if sessions_df.empty:
        return _empty_cartesian(opt)
    s = sessions_df.nlargest(top_n, "total").iloc[::-1]
    kind_color = {"main": c["accent"], "subagent": c["cached"], "other": c["muted"]}
    labels = [lbl[:26] for lbl in s["label"].fillna("(unlabeled)")]
    data = []
    for row in s.itertuples():
        data.append({
            "value": int(row.total),
            "itemStyle": {"color": kind_color.get(row.kind, c["muted"]), "borderRadius": [0, 4, 4, 0]},
            "sessionId": row.session_id,
            "kind": row.kind,
        })
    opt["grid"] = {"top": 35, "right": 40, "bottom": 25, "left": 160}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": labels, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": data}]
    return opt


def session_kinds(sessions_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Session Class Split")
    if sessions_df.empty:
        opt["series"] = [{"type": "pie", "data": []}]
        return opt
    grp = sessions_df.groupby("kind", as_index=False)["total"].sum()
    kind_color = {"main": c["accent"], "subagent": c["cached"], "other": c["muted"]}
    items = []
    for r in grp.itertuples():
        items.append({
            "name": str(r.kind).upper(),
            "value": int(r.total),
            "itemStyle": {"color": kind_color.get(r.kind, c["muted"])},
        })
    opt["series"] = [{
        "type": "pie", "radius": ["50%", "72%"], "avoidLabelOverlap": True,
        "label": {"show": False}, "data": items,
    }]
    return opt


def calls_vs_sessions(daily_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Invocations vs Distinct Sessions")
    if daily_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in daily_df["date"]]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = [
        {"type": "value", "name": "Calls", "splitLine": {"lineStyle": {"color": c["grid"]}}},
        {"type": "value", "name": "Sessions", "position": "right", "splitLine": {"show": False}},
    ]
    opt["series"] = [
        {"name": "Calls", "type": "bar", "color": c["accent"], "data": daily_df["calls"].tolist()},
        {"name": "Sessions", "type": "line", "yAxisIndex": 1, "color": c["cached"], "data": daily_df["sessions"].tolist()},
    ]
    return opt


def time_budget(gaps_daily_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Agent Active (Busy) vs Idle Waiting (Hours)")
    if gaps_daily_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in gaps_daily_df["date"]]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": "Hours", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["series"] = [
        {"name": "Agent Active (Busy)", "type": "bar", "stack": "hours", "color": c["accent"],
         "data": gaps_daily_df["busy_hours"].round(2).tolist()},
        {"name": "Waiting on User (Idle)", "type": "bar", "stack": "hours", "color": c["cached"],
         "data": gaps_daily_df["idle_hours"].round(2).tolist()},
    ]
    return opt


def thinking_ratio(step_days_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Reasoning Step Ratio (%)")
    if step_days_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in step_days_df["date"]]
    ratio = (step_days_df["thinking_steps"] / step_days_df["steps"].replace(0, pd.NA)).fillna(0) * 100
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": "%", "max": 100, "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["series"] = [{
        "name": "Thinking Ratio", "type": "line", "smooth": True, "color": c["cost"],
        "data": ratio.round(1).tolist(),
    }]
    return opt


def tool_mix(counters: dict, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Tool Invocation Mix")
    tools = {k[5:]: v for k, v in counters.items() if k.startswith("tool:")}
    if not tools:
        return _empty_cartesian(opt)
    s = pd.Series(tools).sort_values().tail(12)
    opt["grid"] = {"top": 35, "right": 30, "bottom": 25, "left": 130}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": s.index.tolist(), "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": s.values.tolist(), "itemStyle": {"color": c["accent"]}}]
    return opt


def failure_daily(failures_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Failure Steps per Day")
    if failures_df.empty or "date" not in failures_df.columns:
        return _empty_cartesian(opt)
    by_day = failures_df.groupby("date").size()
    opt["xAxis"] = {"type": "category", "data": by_day.index.tolist(), "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": "Errors", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["series"] = [{"name": "Failures", "type": "bar", "color": c["bad"], "data": by_day.values.tolist()}]
    return opt


def model_switches(switches_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Engine Switches by Target")
    if switches_df.empty:
        opt["series"] = [{"type": "pie", "data": []}]
        return opt
    top = switches_df["to_model"].value_counts().head(6)
    opt["series"] = [{
        "type": "pie", "radius": ["45%", "68%"],
        "data": [{"name": k, "value": int(v)} for k, v in top.items()],
        "label": {"show": False},
    }]
    return opt


def mcp_invocations(counters: dict, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "MCP Server Dispatches")
    servers = {k[4:]: v for k, v in counters.items() if k.startswith("mcp:")}
    if not servers:
        return _empty_cartesian(opt)
    s = pd.Series(servers).sort_values().tail(8)
    opt["grid"] = {"top": 35, "right": 30, "bottom": 25, "left": 110}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": s.index.tolist(), "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": s.values.tolist(), "itemStyle": {"color": c["cached"]}}]
    return opt


def forecast_fan(observed: pd.DataFrame, fc: stats.Forecast, column: str, unit: str | None, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Trajectory Projection (P10 - P50 - P90)")
    if observed.empty:
        return _empty_cartesian(opt)

    obs_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in observed["date"]]
    obs_vals = [round(float(v), 2) for v in observed[column]]
    all_dates = list(obs_dates)
    if fc.supported and fc.horizon_days:
        fc_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in fc.dates]
        all_dates.extend(fc_dates)

    opt["xAxis"] = {"type": "category", "data": all_dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": ctx.currency if unit is None else "Tokens",
                    "splitLine": {"lineStyle": {"color": c["grid"]}}}

    series = [
        {"name": "Measured", "type": "line", "color": c["accent"], "data": obs_vals + [None] * (len(all_dates) - len(obs_vals))},
    ]
    if fc.supported and fc.horizon_days:
        pad = [None] * (len(obs_dates) - 1)
        anchor = [obs_vals[-1]] if obs_vals else []
        p10 = pad + anchor + [round(float(v), 2) for v in fc.per_day_low]
        delta = [None] * len(pad) + ([0.0] if anchor else []) + [round(float(h - l), 2) for l, h in zip(fc.per_day_low, fc.per_day_high)]
        p50 = pad + anchor + [round(float(v), 2) for v in fc.per_day_median]

        series.extend([
            {"name": "P10 Floor", "type": "line", "stack": "confidence_band",
             "lineStyle": {"opacity": 0}, "showSymbol": False, "data": p10},
            {"name": "P10-P90 Uncertainty Band", "type": "line", "stack": "confidence_band",
             "lineStyle": {"opacity": 0}, "areaStyle": {"color": "rgba(56,189,248,0.18)"},
             "showSymbol": False, "data": delta},
            {"name": "P50 Median", "type": "line",
             "lineStyle": {"color": c["output"], "type": "dashed", "width": 2},
             "data": p50},
        ])
    opt["series"] = series
    return opt


def historical_cadence(agg_df: pd.DataFrame, column: str, freq: str, unit: str | None, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Measured Aggregation ({freq.capitalize()})")
    if agg_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in agg_df["date"]]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": ctx.currency if unit is None else "Tokens",
                    "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["series"] = [{"name": column, "type": "bar", "color": c["accent"], "data": agg_df[column].round(2).tolist()}]
    return opt


def model_benchmark(cmp_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Workload Cost Across Engines ({ctx.currency})")
    if cmp_df.empty:
        return _empty_cartesian(opt)
    data = []
    for r in cmp_df.itertuples():
        cost_curr = round(ctx.to_currency(r.cost_usd), 2)
        data.append({
            "value": cost_curr,
            "itemStyle": {"color": c["warn"] if r.estimate else c["accent"], "borderRadius": [0, 4, 4, 0]},
        })
    opt["grid"] = {"top": 35, "right": 50, "bottom": 25, "left": 140}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": cmp_df["model"].tolist(), "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": data, "label": {"show": True, "position": "right", "color": c["text"]}}]
    return opt


def subscription_comparison(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Actual Spend vs Metered Equivalent ({ctx.currency})")
    sub_spend = ctx.overview.subscription_spend
    api_val = ctx.to_currency(ctx.overview.api_cost_usd)
    opt["grid"] = {"top": 35, "right": 40, "bottom": 25, "left": 140}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {
        "type": "category",
        "data": ["Actual Subscription", f"API Equiv ({ctx.model_id})"],
        "axisLabel": {"color": c["muted"], "fontSize": 11},
    }
    opt["series"] = [{
        "type": "bar",
        "data": [
            {"value": round(sub_spend, 2), "itemStyle": {"color": c["cached"], "borderRadius": [0, 4, 4, 0]}},
            {"value": round(api_val, 2), "itemStyle": {"color": c["accent"], "borderRadius": [0, 4, 4, 0]}},
        ],
        "label": {"show": True, "position": "right", "color": c["text"], "fontFamily": "JetBrains Mono"},
    }]
    return opt
```

- [ ] **Verify:** `.venv\Scripts\python.exe -m pytest tests/test_ui_charts.py`
Expected: passes.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/charts.py tests/test_ui_charts.py
git commit -m "feat(ui): pure ECharts option builders with stacked ribbons and empty fallbacks" -- agy_dash/ui/charts.py tests/test_ui_charts.py
```

---

### Task 7: Workspace View-Model Builders

**Files:** Create `agy_dash/ui/views.py`. Test: `tests/test_ui_views.py`

- [ ] **Step 1: Write `tests/test_ui_views.py`:**
```python
import pandas as pd
from agy_dash import pricing, source
from agy_dash.ui import common, views


def test_build_economics_view_populates_models(usage):
    catalog = pricing.default_catalog()
    prices, _ = catalog.price_on("claude-sonnet")
    ctx = common.build_ctx(
        None, usage, usage.sessions, usage.daily, catalog, prices,
        "claude-sonnet", None, "INR", 88.0, 2000.0, "dark", None,
    )
    # Ensure chosen_models is not empty due to string vs PriceEntry bug (F-01)
    res = views.build_economics_view(ctx, {}, {})
    assert len(res["cmp_rows"]) > 0
    assert len(res["available_models"]) > 0
    assert "cadence_chart" in res["charts"]
    assert "schedule_rows" in res
```

- [ ] **Step 2: Write `agy_dash/ui/views.py`:**
```python
"""View-model builders: transform Ctx and DeepData into plain template dicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from .. import deep, metrics, pricing, snapshots, stats
from . import charts, common


def build_command_view(ctx: common.Ctx, deep_data: deep.DeepData | None) -> dict[str, Any]:
    t = ctx.overview.totals
    o = ctx.overview
    curr = ctx.currency

    token_kpis = [
        {"lbl": "TOTAL INGESTION", "val": common.fmt_tokens(t.total), "sub": f"{t.active_days} active days", "icon": "⚡", "badge": "ALL"},
        {"lbl": "FRESH INPUT", "val": common.fmt_tokens(t.fresh_in), "sub": f"{common.fmt_pct(metrics.safe_div(t.fresh_in, t.total))} fresh", "icon": "📥", "badge": "UNCACHED"},
        {"lbl": "CACHED INPUT", "val": common.fmt_tokens(t.cached), "sub": f"{common.fmt_pct(t.cache_hit_rate)} efficiency", "icon": "⚡", "badge": "REUSED"},
        {"lbl": "OUTPUT & THINKING", "val": common.fmt_tokens(t.output), "sub": "reasoning tokens included", "icon": "📤", "badge": "GENERATED"},
    ]

    sub_spend = o.subscription_spend
    econ_kpis = [
        {"lbl": f"EQUIVALENT API COST", "val": common.fmt_money(ctx.to_currency(o.api_cost_usd), curr), "sub": f"{o.model_name} catalog", "icon": "💵", "badge": "METERED"},
        {"lbl": f"SUBSCRIPTION SPEND", "val": common.fmt_money(sub_spend, curr), "sub": "fixed periodic spend", "icon": "💳", "badge": "FIXED"},
        {"lbl": "BLENDED EFFICIENCY", "val": common.fmt_rate(ctx.to_currency(o.blended_rate_usd_per_mtok), curr), "sub": f"{common.fmt_tokens(o.tokens_per_currency_spent)} tok/{curr}", "icon": "📊", "badge": "RATE"},
        {"lbl": "CACHE SAVINGS", "val": common.fmt_money(ctx.to_currency(metrics.cache_savings_usd(t.fresh_in, t.cached, ctx.prices)), curr), "sub": "saved via reuse", "icon": "🛡️", "badge": "SAVED"},
    ]

    ws_df = deep.workspace_totals(ctx.usage.sessions, deep_data.session_meta if deep_data else pd.DataFrame(), ctx.prices)
    ws_rows = []
    if not ws_df.empty:
        ws_df = ws_df.sort_values("total", ascending=False).head(8)
        for r in ws_df.itertuples():
            ws_rows.append({
                "project": r.project,
                "sessions": r.sessions,
                "tokens": common.fmt_tokens(r.total),
                "cost": common.fmt_money(ctx.to_currency(r.cost_usd), curr),
            })

    days = metrics.best_worst_days(ctx.daily, ctx.prices, n=5)
    best_days = []
    if not days["best"].empty:
        for r in days["best"].itertuples():
            best_days.append({
                "date": pd.Timestamp(r.date).strftime("%Y-%m-%d"),
                "tokens": common.fmt_tokens(r.total),
                "calls": r.calls,
                "cost": common.fmt_money(ctx.to_currency(r.cost_usd), curr),
            })

    waste = None
    if deep_data:
        waste_info = deep.waste_estimate(ctx.overview, len(deep_data.failures))
        waste = {
            "cost": common.fmt_money(ctx.to_currency(waste_info["cost_usd"]), curr),
            "tokens_at_risk": common.fmt_tokens(waste_info["tokens_at_risk"]),
            "share_of_calls": common.fmt_pct(waste_info["share_of_calls"]),
            "failure_count": waste_info["failure_count"],
        }

    chart_payloads = {
        "daily_burn_chart": charts.daily_burn(ctx),
        "token_mix_chart": charts.token_mix(ctx),
        "cost_burden_chart": charts.cost_burden(ctx),
        "workspace_chart": charts.workspace_attribution(ws_df, ctx),
        "cache_thrash_chart": charts.cache_thrash(deep_data.step_days if deep_data else pd.DataFrame(), ctx),
    }

    return {
        "token_kpis": token_kpis,
        "econ_kpis": econ_kpis,
        "ws_rows": ws_rows,
        "best_days": best_days,
        "charts": chart_payloads,
        "waste": waste,
    }


def build_sessions_view(
    ctx: common.Ctx,
    deep_data: deep.DeepData | None,
    kind_sel: list[str] | None = None,
    top_n: int = 25,
    search: str | None = None,
) -> dict[str, Any]:
    sessions = ctx.sessions
    if kind_sel:
        sessions = sessions[sessions["kind"].isin(kind_sel)]
    if search:
        s = search.lower()
        sessions = sessions[
            sessions["label"].str.lower().str.contains(s, na=False, regex=False)
            | sessions["session_id"].str.lower().str.contains(s, na=False, regex=False)
        ]

    sub_count = int((sessions["kind"] == "subagent").sum()) if not sessions.empty else 0
    main_count = int((sessions["kind"] == "main").sum()) if not sessions.empty else 0
    total_tok = int(sessions["total"].sum()) if not sessions.empty else 0
    all_tok = int(ctx.overview.totals.total)
    sub_share = metrics.safe_div(sessions.loc[sessions["kind"] == "subagent", "total"].sum(), total_tok)

    session_kpis = [
        {"lbl": "FILTERED SESSIONS", "val": f"{len(sessions):,}", "sub": f"{main_count} main · {sub_count} subagents", "icon": "🧭", "badge": "COUNT"},
        {"lbl": "FILTERED VOLUME", "val": common.fmt_tokens(total_tok), "sub": f"{common.fmt_pct(metrics.safe_div(total_tok, all_tok))} of window", "icon": "⚡", "badge": "VOLUME"},
        {"lbl": "AVG WORKLOAD / SESSION", "val": common.fmt_tokens(total_tok / max(1, len(sessions))), "sub": "mean tokens", "icon": "📊", "badge": "AVERAGE"},
        {"lbl": "SUBAGENT TOKEN SHARE", "val": common.fmt_pct(sub_share), "sub": "autonomous execution share", "icon": "🤖", "badge": "SHARE"},
    ]

    session_rows = []
    if not sessions.empty:
        costs = [metrics.api_cost_usd(r.fresh_in, r.cached, r.output, ctx.prices) for r in sessions.itertuples()]
        df = sessions.assign(cost=costs).sort_values("total", ascending=False).head(top_n)
        for r in df.itertuples():
            session_rows.append({
                "session_id": r.session_id,
                "label": r.label[:42],
                "kind": r.kind,
                "calls": r.calls,
                "fresh_in": common.fmt_tokens(r.fresh_in),
                "cached": common.fmt_tokens(r.cached),
                "output": common.fmt_tokens(r.output),
                "total": common.fmt_tokens(r.total),
                "cost": ctx.money(r.cost),
                "last_date": r.last_date or "-",
            })

    turn_rows = []
    cmd_rows = []
    fail_rows = []
    denial_rows = []
    artifact_rows = []
    message_rows = []
    counters = deep_data.counters if deep_data else {}

    if deep_data:
        turn_stats = deep.turnaround_stats(deep_data.turnarounds)
        for r in turn_stats.head(8).itertuples():
            turn_rows.append({
                "tool": r.tool, "calls": r.calls,
                "p50": f"{r.p50_seconds:.1f}s", "p90": f"{r.p90_seconds:.1f}s",
                "total_min": f"{r.total_minutes:.1f}m",
            })

        if not deep_data.commands.empty:
            cmds = deep_data.commands.dropna(subset=["duration_seconds"]).nlargest(10, "duration_seconds")
            for r in cmds.itertuples():
                cmd_rows.append({
                    "date": r.date, "command": r.command[:65],
                    "duration": f"{r.duration_seconds:.1f}s",
                    "exit_code": r.exit_code if r.exit_code is not None else "-",
                })

        fail_summary = deep.failure_summary(deep_data.failures, top=8)
        for r in fail_summary.itertuples():
            fail_rows.append({
                "text": r.text[:80], "count": r.count, "last_seen": r.last_seen,
            })

        if not deep_data.denials.empty:
            for r in deep_data.denials.head(8).itertuples():
                denial_rows.append({
                    "date": r.date, "command": r.command[:45] if r.command else "-",
                    "wait": f"{r.wait_seconds:.1f}s" if r.wait_seconds else "-",
                    "text": r.text[:60],
                })

        if not deep_data.artifacts.empty:
            for r in deep_data.artifacts.head(8).itertuples():
                artifact_rows.append({
                    "name": r.name, "updated": str(r.updated_at)[:19] if r.updated_at else "-",
                    "gate": "Feedback Req" if r.request_feedback else "Direct",
                    "summary": r.summary[:60],
                })

        if not deep_data.messages.empty:
            for r in deep_data.messages.head(6).itertuples():
                message_rows.append({
                    "sender": r.sender, "title": r.title[:45],
                    "priority": r.priority, "read": "Read" if r.read else "Unread",
                })

    gaps_df = deep.gaps_daily(deep_data.gaps) if deep_data else pd.DataFrame()
    swarm_kpis = [
        {"lbl": "BACKGROUND LOGS", "val": f"{counters.get('task_logs', 0):,}", "icon": "📋"},
        {"lbl": "SCHEDULE CALLS", "val": f"{counters.get('schedule_calls', 0):,}", "icon": "⏰"},
        {"lbl": "MANAGE_TASK", "val": f"{counters.get('tool:manage_task', 0):,}", "icon": "🛠️"},
        {"lbl": "MANAGE_SUBAGENTS", "val": f"{counters.get('tool:manage_subagents', 0):,}", "icon": "👥"},
    ]

    high_ctx = int((sessions["total"] > 100_000).sum()) if not sessions.empty else 0
    max_ctx = int(sessions["total"].max()) if not sessions.empty else 0
    avg_ctx = int(sessions["total"].mean()) if not sessions.empty else 0
    context_kpis = [
        {"lbl": "HIGH CONTEXT SESSIONS (>100K)", "val": f"{high_ctx:,}", "icon": "⚠️"},
        {"lbl": "PEAK CONTEXT RECORD", "val": common.fmt_tokens(max_ctx), "icon": "🏔️"},
        {"lbl": "AVG CONTEXT WORKLOAD", "val": common.fmt_tokens(avg_ctx), "icon": "📐"},
    ]

    chart_payloads = {
        "top_sessions_chart": charts.top_sessions(sessions, top_n, ctx),
        "session_kinds_chart": charts.session_kinds(sessions, ctx),
        "calls_vs_sessions_chart": charts.calls_vs_sessions(ctx.daily, ctx),
        "time_budget_chart": charts.time_budget(gaps_df, ctx),
        "thinking_ratio_chart": charts.thinking_ratio(deep_data.step_days if deep_data else pd.DataFrame(), ctx),
        "tool_mix_chart": charts.tool_mix(counters, ctx),
        "failure_daily_chart": charts.failure_daily(deep_data.failures if deep_data else pd.DataFrame(), ctx),
        "model_switches_chart": charts.model_switches(deep_data.model_switches if deep_data else pd.DataFrame(), ctx),
        "mcp_invocations_chart": charts.mcp_invocations(counters, ctx),
    }

    return {
        "session_kpis": session_kpis,
        "swarm_kpis": swarm_kpis,
        "context_kpis": context_kpis,
        "sessions_count": len(sessions),
        "session_rows": session_rows,
        "turn_rows": turn_rows,
        "cmd_rows": cmd_rows,
        "fail_rows": fail_rows,
        "denial_rows": denial_rows,
        "artifact_rows": artifact_rows,
        "message_rows": message_rows,
        "charts": chart_payloads,
    }


def build_session_detail(ctx: common.Ctx, deep_data: deep.DeepData | None, session_id: str) -> dict[str, Any] | None:
    match = ctx.usage.sessions[ctx.usage.sessions["session_id"] == session_id]
    if match.empty:
        return None
    r = match.iloc[0]
    cost_usd = metrics.api_cost_usd(r["fresh_in"], r["cached"], r["output"], ctx.prices)

    meta = {}
    commands = []
    failures = []
    tools = []
    artifacts = []
    if deep_data:
        if not deep_data.session_meta.empty:
            m = deep_data.session_meta[deep_data.session_meta["session_id"] == session_id]
            if not m.empty:
                meta = m.iloc[0].to_dict()
        if not deep_data.commands.empty and "session_id" in deep_data.commands.columns:
            sc = deep_data.commands[deep_data.commands["session_id"] == session_id]
            for cmd in sc.head(20).itertuples():
                commands.append({
                    "date": cmd.date, "command": cmd.command,
                    "duration": f"{cmd.duration_seconds:.1f}s" if pd.notna(cmd.duration_seconds) else "-",
                    "exit_code": cmd.exit_code if pd.notna(cmd.exit_code) else "-",
                })
        if not deep_data.failures.empty and "session_id" in deep_data.failures.columns:
            sf = deep_data.failures[deep_data.failures["session_id"] == session_id]
            for f in sf.head(10).itertuples():
                failures.append({"date": f.date, "text": f.text})
        if not deep_data.turnarounds.empty and "session_id" in deep_data.turnarounds.columns:
            st = deep_data.turnarounds[deep_data.turnarounds["session_id"] == session_id]
            st_grp = st.groupby("tool").agg(calls=("duration_seconds", "count"), avg_sec=("duration_seconds", "mean"))
            for t_name, t_row in st_grp.iterrows():
                tools.append({"tool": t_name, "calls": int(t_row["calls"]), "avg_sec": f"{t_row['avg_sec']:.2f}s"})
        if not deep_data.artifacts.empty and "session_id" in deep_data.artifacts.columns:
            sa = deep_data.artifacts[deep_data.artifacts["session_id"] == session_id]
            for a in sa.head(10).itertuples():
                artifacts.append({"name": a.name, "summary": a.summary, "gate": "Feedback Req" if a.request_feedback else "Direct"})

    return {
        "session_id": session_id,
        "label": r.get("label", "(unlabeled)"),
        "kind": r.get("kind", "other"),
        "calls": int(r.get("calls", 0)),
        "first_utc": str(r.get("first_utc", ""))[:19],
        "last_utc": str(r.get("last_utc", ""))[:19],
        "tokens": {
            "fresh_in": common.fmt_tokens(r["fresh_in"]),
            "cached": common.fmt_tokens(r["cached"]),
            "output": common.fmt_tokens(r["output"]),
            "total": common.fmt_tokens(r["total"]),
        },
        "cost": ctx.money(cost_usd),
        "meta": meta,
        "commands": commands,
        "failures": failures,
        "tools": tools,
        "artifacts": artifacts,
    }


def build_economics_view(
    ctx: common.Ctx,
    fc_params: dict[str, Any],
    lab_params: dict[str, Any],
) -> dict[str, Any]:
    TARGETS = {
        "Total tokens": ("total", "tokens"),
        "Fresh input tokens": ("fresh_in", "tokens"),
        "Cached input tokens": ("cached", "tokens"),
        "Output tokens": ("output", "tokens"),
        "Model calls": ("calls", "calls"),
        "API-equivalent cost": ("cost", None),
    }
    target = fc_params.get("target", "Total tokens")
    method = fc_params.get("method", "Bootstrap resampling")
    horizon = int(fc_params.get("horizon", 30))
    daily_growth = float(fc_params.get("daily_growth", 0.0))
    mc_growth = float(fc_params.get("mc_growth", 0.0))
    mc_sd = float(fc_params.get("mc_sd", 0.5))
    freq = fc_params.get("freq", "daily")

    column, unit = TARGETS.get(target, ("total", "tokens"))
    if column == "cost":
        d = metrics.attach_costs(ctx.daily, ctx.prices).copy()
        d["cost"] = [ctx.to_currency(v) for v in d["cost_usd"]]
        observed = stats.observed_series(d, "cost")
    else:
        observed = stats.observed_series(ctx.daily, column)

    values = observed[column].to_numpy(dtype=float) if not observed.empty else np.array([])
    last_date = observed["date"].max() if not observed.empty else None

    kwargs = {}
    if method == "Linear extrapolation (baseline)":
        kwargs = {"daily_growth": daily_growth}
    elif method == "Monte Carlo simulation":
        kwargs = {"growth_mean": mc_growth, "growth_sd": max(mc_sd, 0.01)}
    fc = stats.run_forecast(method, values, horizon, last_date=last_date, **kwargs)

    unit_fmt = (lambda v: common.fmt_money(v, ctx.currency)) if unit is None else common.fmt_tokens
    fc_kpis = [
        {"lbl": "OBSERVED DAILY MEAN", "val": unit_fmt(float(np.mean(values))) if len(values) else "0", "sub": f"{len(values)} active days measured", "icon": "📊", "badge": "MEASURED"},
        {"lbl": "FORECAST LOW (P10)", "val": unit_fmt(fc.cumulative_low), "sub": "conservative floor", "icon": "📉", "badge": "P10"},
        {"lbl": "FORECAST MEDIAN (P50)", "val": unit_fmt(fc.cumulative_median), "sub": "central projection", "icon": "🎯", "badge": "P50"},
        {"lbl": "FORECAST HIGH (P90)", "val": unit_fmt(fc.cumulative_high), "sub": "tail surge scenario", "icon": "📈", "badge": "P90"},
    ]

    schedule_rows = []
    if fc.supported and fc.horizon_days:
        fc_df = fc.to_frame()
        for r in fc_df.itertuples():
            schedule_rows.append({
                "date": pd.Timestamp(r.date).strftime("%Y-%m-%d"),
                "low": unit_fmt(r.low),
                "median": unit_fmt(r.median),
                "high": unit_fmt(r.high),
            })

    agg_df = stats.aggregate(ctx.daily, freq)
    if column == "cost":
        d_agg = metrics.attach_costs(agg_df, ctx.prices)
        d_agg["cost"] = [ctx.to_currency(v) for v in d_agg["cost_usd"]]
        agg_chart_df = d_agg
    else:
        agg_chart_df = agg_df

    # 2. Simulator & Model Benchmark Section (F-01 Fix)
    base = {
        "fresh_in": int(ctx.overview.totals.fresh_in),
        "cached": int(ctx.overview.totals.cached),
        "output": int(ctx.overview.totals.output),
    }
    use_ratio = bool(lab_params.get("use_ratio", False))
    ratio = float(lab_params.get("ratio", metrics.cache_hit_rate(base["fresh_in"], base["cached"])))
    output_mult = float(lab_params.get("output_mult", 1.0))
    prompt_mult = float(lab_params.get("prompt_mult", 1.0))

    catalog_model_ids = {e.model_id for e in ctx.catalog.entries}
    chosen_models = lab_params.get("chosen_models") or [
        m for m in ("gemini-3.8-flash", "gemini-4-argon", "claude-sonnet", "claude-opus", "gpt-flagship", "deepseek-v3-api")
        if m in catalog_model_ids or ctx.catalog.price_on(m)[0] is not None
    ]

    available_models = [
        {"id": m, "checked": m in chosen_models}
        for m in sorted(catalog_model_ids)
    ]

    tokens = metrics.hypothetical_tokens(
        base["fresh_in"] * prompt_mult, base["cached"] * prompt_mult, base["output"],
        cached_ratio=ratio if use_ratio else None, output_multiplier=output_mult,
    )
    on_date = ctx.daily["date"].max().date() if not ctx.daily.empty else None
    cmp = metrics.compare_models(tokens, ctx.catalog, chosen_models, on=on_date)

    cmp_rows = []
    if not cmp.empty:
        cmp["cost"] = [ctx.to_currency(v) for v in cmp["cost_usd"]]
        cmp["cost_per_mtok"] = [ctx.to_currency(v) for v in cmp["cost_per_mtok_usd"]]
        total_tok = sum(tokens.values())
        cmp["tokens_per_curr"] = [metrics.tokens_per_currency(total_tok, c) for c in cmp["cost"]]
        cmp["vs_cheapest"] = cmp["cost"] / cmp["cost"].min() if cmp["cost"].min() else 1.0
        for r in cmp.itertuples():
            cmp_rows.append({
                "model": r.model, "vendor": r.vendor,
                "cost": common.fmt_money(r.cost, ctx.currency),
                "cost_per_mtok": common.fmt_rate(r.cost_per_mtok, ctx.currency),
                "tokens_per_curr": common.fmt_tokens(r.tokens_per_curr),
                "vs_cheapest": f"{r.vs_cheapest:.2f}x",
                "version_date": r.pricing_from,
                "estimate": r.estimate,
            })

    sub_spend = ctx.overview.subscription_spend
    api_val = ctx.to_currency(ctx.overview.api_cost_usd)
    delta_usd = ctx.overview.api_cost_usd - ctx.overview.subscription_spend_usd
    delta_curr = ctx.to_currency(delta_usd)

    sub_card = {
        "actual_spend": common.fmt_money(sub_spend, ctx.currency),
        "api_val": common.fmt_money(api_val, ctx.currency),
        "delta": common.fmt_money(delta_curr, ctx.currency),
    }

    sub_spend_overview = ctx.overview.subscription_spend
    payback_pct = common.fmt_pct(metrics.safe_div(fc.cumulative_median, sub_spend_overview), decimals=0) if sub_spend_overview > 0 else "-"

    chart_payloads = {
        "forecast_chart": charts.forecast_fan(observed, fc, column, unit, ctx),
        "cadence_chart": charts.historical_cadence(agg_chart_df, column, freq, unit, ctx),
        "benchmark_chart": charts.model_benchmark(cmp, ctx),
        "sub_chart": charts.subscription_comparison(ctx),
    }

    return {
        "fc_kpis": fc_kpis,
        "fc_assumptions": fc.assumptions,
        "uncertainty_note": stats.uncertainty_note(len(values)),
        "fc_summary": [
            {"tier": "Conservative Floor (P10)", "val": unit_fmt(fc.cumulative_low)},
            {"tier": "Expected Median (P50)", "val": unit_fmt(fc.cumulative_median)},
            {"tier": "Upper Surge (P90)", "val": unit_fmt(fc.cumulative_high)},
        ],
        "payback_pct": payback_pct,
        "schedule_rows": schedule_rows,
        "fc_params": {"target": target, "method": method, "horizon": horizon, "daily_growth": daily_growth, "mc_growth": mc_growth, "mc_sd": mc_sd, "freq": freq},
        "workload_baseline": {
            "fresh_in": common.fmt_tokens(base["fresh_in"]),
            "cached": common.fmt_tokens(base["cached"]),
            "output": common.fmt_tokens(base["output"]),
            "cache_hit_rate": common.fmt_pct(metrics.cache_hit_rate(base["fresh_in"], base["cached"])),
        },
        "lab_params": {"prompt_mult": prompt_mult, "output_mult": output_mult, "use_ratio": use_ratio, "ratio": round(ratio * 100, 1), "chosen_models": chosen_models},
        "available_models": available_models,
        "cmp_rows": cmp_rows,
        "sub_card": sub_card,
        "charts": chart_payloads,
    }


def build_sync_drawer(ctx: common.Ctx) -> dict[str, Any]:
    conn = snapshots.connect(ctx.config.db_path)
    counts = snapshots.counts(conn)
    runs = snapshots.runs(conn, limit=10)
    conn.close()

    consistency_issues = metrics.verify_consistency(ctx.usage.sessions, ctx.usage.daily)
    runner = ctx.runner
    state = runner.state if runner else None
    persisted = jobs.last_run(runner.last_run_path) if runner else None

    return {
        "source_online": Path(ctx.usage.root).exists(),
        "brain_root": ctx.usage.root,
        "extractor_script": ctx.config.extractor_script,
        "python_executable": ctx.config.python_executable,
        "sessions_scanned": len(ctx.usage.sessions),
        "warnings": ctx.usage.warnings,
        "consistency_issues": consistency_issues,
        "db_counts": counts,
        "runs": runs,
        "runner_state": state,
        "persisted_run": persisted,
        "stdout": state.read_stdout(limit=20000) if state else "",
        "stderr": state.read_stderr(limit=10000) if state else "",
    }
```

- [ ] **Verify:** `.venv\Scripts\python.exe -m pytest tests/test_ui_views.py`
Expected: passes.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/views.py tests/test_ui_views.py
git commit -m "feat(ui): view models with F-01 fix, sync drawer data, and complete session detail" -- agy_dash/ui/views.py tests/test_ui_views.py
```

---

### Task 8: CSS Design System & Client JS

**Files:** Create `agy_dash/ui/static/css/telemetry.css` and `agy_dash/ui/static/js/app.js`

- [ ] **Step 1: Write `agy_dash/ui/static/css/telemetry.css`:**
```css
/* High-Craft Mission Telemetry Design System */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap');

:root {
  --bg-core: #090A0F;
  --panel-bg: rgba(16, 18, 26, 0.85);
  --panel-solid: #10121A;
  --panel-alt: #161922;
  --border-subtle: #1E2230;
  --border-specular: rgba(255, 255, 255, 0.08);
  --text-main: #F1F5F9;
  --text-bright: #FFFFFF;
  --text-muted: #94A3B8;
  --brand-cyan: #38BDF8;
  --brand-accent: #38BDF8;
  --signal-emerald: #10B981;
  --signal-amber: #F59E0B;
  --signal-rose: #F43F5E;
  --signal-violet: #A78BFA;
  --font-display: 'Syne', sans-serif;
  --font-body: 'Plus Jakarta Sans', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}

[data-theme="light"] {
  --bg-core: #F6F7F9;
  --panel-bg: rgba(255, 255, 255, 0.9);
  --panel-solid: #FFFFFF;
  --panel-alt: #F1F4F8;
  --border-subtle: #E2E8F0;
  --border-specular: rgba(0, 0, 0, 0.06);
  --text-main: #0F172A;
  --text-bright: #020617;
  --text-muted: #64748B;
  --brand-cyan: #0284C7;
  --brand-accent: #0284C7;
  --signal-emerald: #059669;
  --signal-amber: #D97706;
  --signal-rose: #E11D48;
  --signal-violet: #7C3AED;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background-color: var(--bg-core);
  color: var(--text-main);
  font-family: var(--font-body);
  font-size: 13px;
  line-height: 1.5;
  min-height: 100vh;
}

.mono { font-family: var(--font-mono); }

/* Command Bar */
.command-bar {
  position: sticky; top: 0; z-index: 100;
  background: var(--panel-bg);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.5rem 1.25rem;
  gap: 1rem;
}

.brand { display: flex; align-items: center; gap: 0.75rem; }
.badge-pill {
  background: var(--panel-alt);
  border: 1px solid var(--border-subtle);
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
}

.view-nav { display: flex; gap: 0.25rem; }
.nav-tab {
  padding: 0.4rem 0.8rem;
  border-radius: 4px;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 0.78rem;
  color: var(--text-muted);
  text-decoration: none;
  border: 1px solid transparent;
  cursor: pointer;
}
.nav-tab:hover { color: var(--text-main); background: var(--panel-alt); }
.nav-tab.active {
  color: var(--brand-accent);
  border-color: var(--border-subtle);
  background: var(--panel-solid);
}

.filter-strip { display: flex; align-items: center; gap: 0.5rem; }
.filter-input {
  background: var(--panel-solid);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
}

.btn {
  background: var(--panel-alt);
  border: 1px solid var(--border-subtle);
  color: var(--text-main);
  padding: 0.35rem 0.65rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  text-decoration: none;
  display: inline-flex; align-items: center; gap: 0.3rem;
}
.btn:hover { border-color: var(--brand-accent); }
.btn-primary { background: var(--brand-accent); color: #000; font-weight: 600; }

/* Status dot */
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.status-dot.idle { background: var(--signal-emerald); }
.status-dot.running { background: var(--signal-amber); }
.pulse { animation: pulseAnim 1.5s infinite; }
@keyframes pulseAnim { 0% { opacity: 1; } 50% { opacity: 0.3; } 100% { opacity: 1; } }

/* Workspace Container */
.workspace { max-width: 1540px; margin: 1.5rem auto; padding: 0 1.25rem; }

/* KPI Strip */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.25rem;
}
.kpi-card {
  background: var(--panel-bg);
  border: 1px solid var(--border-specular);
  border-radius: 6px;
  padding: 0.85rem 1rem;
}
.kpi-card .lbl { font-size: 0.72rem; color: var(--text-muted); display: flex; justify-content: space-between; }
.kpi-card .val { font-family: var(--font-mono); font-size: 1.45rem; font-weight: 700; margin: 0.2rem 0; }
.kpi-card .sub { font-size: 0.72rem; color: var(--text-muted); }

/* Callout / Disclaimer */
.callout {
  background: var(--panel-alt);
  border-left: 3px solid var(--brand-accent);
  padding: 0.6rem 0.9rem;
  border-radius: 4px;
  font-size: 0.76rem;
  margin-bottom: 1.25rem;
  color: var(--text-muted);
}
.callout.warning { border-left-color: var(--signal-amber); color: var(--signal-amber); }

/* Bento Grid */
.bento-grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 1rem;
}
.bento-panel {
  background: var(--panel-bg);
  border: 1px solid var(--border-specular);
  border-radius: 8px;
  padding: 1rem;
}
.col-3 { grid-column: span 3; }
.col-4 { grid-column: span 4; }
.col-5 { grid-column: span 5; }
.col-6 { grid-column: span 6; }
.col-7 { grid-column: span 7; }
.col-8 { grid-column: span 8; }
.col-12 { grid-column: span 12; }

.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 0.75rem;
}
.panel-title { font-family: var(--font-display); font-weight: 700; font-size: 0.85rem; }

/* Chart boxes */
.chart-box { width: 100%; height: 260px; }
.chart-box-tall { width: 100%; height: 350px; }

/* Tables */
.data-table {
  width: 100%; border-collapse: collapse; font-size: 0.76rem;
}
.data-table th {
  text-align: left; padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--border-subtle);
  color: var(--text-muted); font-size: 0.7rem;
}
.data-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}
.data-table.clickable tbody tr { cursor: pointer; }
.data-table.clickable tbody tr:hover { background: var(--panel-alt); }

/* Slide-Over Drawers */
.drawer-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px); z-index: 200;
  display: none; opacity: 0; transition: opacity 0.2s ease;
}
.drawer-backdrop.open { display: block; opacity: 1; }

.drawer {
  position: fixed; top: 0; right: 0; bottom: 0; width: 480px; max-width: 90vw;
  background: var(--panel-solid); border-left: 1px solid var(--border-subtle);
  box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5); z-index: 210;
  transform: translateX(100%); transition: transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex; flex-direction: column;
}
.drawer.open { transform: translateX(0); }
.drawer-header {
  padding: 1rem 1.25rem; border-bottom: 1px solid var(--border-subtle);
  display: flex; justify-content: space-between; align-items: center;
}
.drawer-body { padding: 1.25rem; overflow-y: auto; flex: 1; }
```

- [ ] **Step 2: Write `agy_dash/ui/static/js/app.js`:**
```javascript
// High-Craft Mission Telemetry Client Runtime
(function() {
  'use strict';

  // 1. Chart hydration & memory management
  window.initCharts = function(root = document) {
    if (typeof echarts === 'undefined') return;
    const containers = root.querySelectorAll('[data-chart]');
    containers.forEach(el => {
      const scriptId = el.getAttribute('data-chart');
      const script = document.getElementById(scriptId);
      if (!script) return;
      try {
        const option = JSON.parse(script.textContent);
        let chart = echarts.getInstanceByDom(el);
        if (chart) {
          chart.dispose();
        }
        chart = echarts.init(el, null, { renderer: 'canvas' });
        chart.setOption(option, true);
      } catch (err) {
        console.error('Failed to parse or render chart option for', scriptId, err);
      }
    });
  };

  // Single debounced global window resize listener (F-11 fix)
  let resizeTimeout;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      document.querySelectorAll('[data-chart]').forEach(el => {
        const chart = echarts.getInstanceByDom(el);
        if (chart) chart.resize();
      });
    }, 100);
  });

  // 2. Drawer management
  window.openDrawer = function(id) {
    const d = document.getElementById(id);
    const b = document.getElementById('drawer-backdrop');
    if (d && b) {
      d.classList.add('open');
      b.classList.add('open');
    }
  };

  window.closeDrawers = function() {
    document.querySelectorAll('.drawer').forEach(d => d.classList.remove('open'));
    const b = document.getElementById('drawer-backdrop');
    if (b) b.classList.remove('open');
  };

  // 3. Theme toggling with cookie persistence
  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('agy_theme', next);
    document.cookie = `agy_theme=${next}; path=/; max-age=31536000`;
    const themeInput = document.getElementById('global-theme-input');
    if (themeInput) themeInput.value = next;
    // Resubmit form to redraw charts in new theme colors
    const form = document.getElementById('global-filter-form');
    if (form) form.requestSubmit();
  };

  // 4. HTMX lifecycle hooks (F-02 fix)
  document.addEventListener('DOMContentLoaded', () => {
    window.initCharts(document);
  });

  document.addEventListener('htmx:afterSwap', (evt) => {
    const target = evt.detail.target;
    if (target) {
      window.initCharts(target);
      // Synchronize active nav tab
      const urlParams = new URLSearchParams(window.location.search);
      const activeView = urlParams.get('view') || 'command';
      document.querySelectorAll('.nav-tab').forEach(tab => {
        if (tab.getAttribute('data-view') === activeView) {
          tab.classList.add('active');
        } else {
          tab.classList.remove('active');
        }
      });
    }
  });
})();
```

- [ ] **Verify:**
```powershell
Test-Path agy_dash\ui\static\css\telemetry.css
Test-Path agy_dash\ui\static\js\app.js
```
Expected: Both return `True`.

- [ ] **Step 3: Commit:**
```bash
git add agy_dash/ui/static/css/telemetry.css agy_dash/ui/static/js/app.js
git commit -m "feat(ui): design system css and client runtime with debounced resize and tab sync" -- agy_dash/ui/static/css/telemetry.css agy_dash/ui/static/js/app.js
```

---

### Task 9: Jinja2 Templates & Partials

**Files:**
- Create `agy_dash/ui/templates/base.html`
- Create `agy_dash/ui/templates/error.html`
- Create `agy_dash/ui/templates/partials/command_bar.html`
- Create `agy_dash/ui/templates/partials/view_command.html`
- Create `agy_dash/ui/templates/partials/view_sessions.html`
- Create `agy_dash/ui/templates/partials/view_economics.html`
- Create `agy_dash/ui/templates/partials/forecast_stage.html`
- Create `agy_dash/ui/templates/partials/lab_stage.html`
- Create `agy_dash/ui/templates/partials/sync_drawer.html`
- Create `agy_dash/ui/templates/partials/job_status.html`
- Create `agy_dash/ui/templates/partials/session_drawer.html`
- Create `agy_dash/ui/templates/partials/session_detail.html`
- Create `agy_dash/ui/templates/partials/catalog_drawer.html`

- [ ] **Step 1: Write `agy_dash/ui/templates/base.html` and `error.html`:**

`agy_dash/ui/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="en" data-theme="{{ filters.theme }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Antigravity // Mission Telemetry</title>
  <link rel="stylesheet" href="/static/css/telemetry.css">
  <script src="/static/vendor/htmx.min.js"></script>
  <script src="/static/vendor/echarts.min.js"></script>
  <script src="/static/js/app.js" defer></script>
</head>
<body>
  {% include "partials/command_bar.html" %}

  <main id="workspace-canvas" class="workspace">
    {% if filters.view == 'command' %}
      {% include "partials/view_command.html" %}
    {% elif filters.view == 'sessions' %}
      {% include "partials/view_sessions.html" %}
    {% elif filters.view == 'economics' %}
      {% include "partials/view_economics.html" %}
    {% endif %}
  </main>

  <div id="drawer-backdrop" class="drawer-backdrop" onclick="closeDrawers()"></div>
  {% include "partials/sync_drawer.html" %}
  {% include "partials/session_drawer.html" %}
  {% include "partials/catalog_drawer.html" %}
</body>
</html>
```

`agy_dash/ui/templates/error.html`:
```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
  <meta charset="utf-8">
  <title>Telemetry Error</title>
  <link rel="stylesheet" href="/static/css/telemetry.css">
</head>
<body style="display:flex; align-items:center; justify-content:center; height:100vh;">
  <div class="bento-panel col-6" style="max-width:600px; border-color:var(--signal-rose);">
    <h3 style="color:var(--signal-rose); margin-bottom:0.5rem;">Telemetry Fault Encountered</h3>
    <p style="margin-bottom:1rem;">{{ message }}</p>
    {% if hint %}
      <div class="callout">{{ hint }}</div>
    {% endif %}
    <a href="/" class="btn btn-primary" style="margin-top:1rem;">Return to Command Center</a>
  </div>
</body>
</html>
```

- [ ] **Step 2: Write `agy_dash/ui/templates/partials/command_bar.html` (F-02, F-07 Fixes):**
```html
<header class="command-bar">
  <div class="brand">
    <div style="font-family:var(--font-display); font-weight:800; font-size:0.95rem; letter-spacing:0.04em;">
      ANTIGRAVITY <span style="color:var(--brand-accent);">//</span> TELEMETRY
    </div>
    <div class="badge-pill mono" title="Total Tokens Scanned">⚡ {{ ctx.overview.totals.total | fmt_tokens if ctx else '0' }}</div>
    <div class="badge-pill mono" title="Modeled API Cost">💵 {{ ctx.money(ctx.overview.api_cost_usd) if ctx else '₹0' }}</div>
  </div>

  <nav class="view-nav">
    <a href="?view=command" class="nav-tab {% if filters.view == 'command' %}active{% endif %}" data-view="command"
       hx-get="/?view=command" hx-select="#workspace-canvas" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-include="#global-filter-form" hx-push-url="true">
       01 // COMMAND
    </a>
    <a href="?view=sessions" class="nav-tab {% if filters.view == 'sessions' %}active{% endif %}" data-view="sessions"
       hx-get="/?view=sessions" hx-select="#workspace-canvas" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-include="#global-filter-form" hx-push-url="true">
       02 // SESSIONS
    </a>
    <a href="?view=economics" class="nav-tab {% if filters.view == 'economics' %}active{% endif %}" data-view="economics"
       hx-get="/?view=economics" hx-select="#workspace-canvas" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-include="#global-filter-form" hx-push-url="true">
       03 // ECONOMICS
    </a>
  </nav>

  <form id="global-filter-form" class="filter-strip" method="get" action="/"
        hx-get="/" hx-select="#workspace-canvas" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-push-url="true">
    <input type="hidden" name="view" value="{{ filters.view }}">
    <input type="hidden" id="global-theme-input" name="theme" value="{{ filters.theme }}">

    <input type="date" name="start" value="{{ filters.start }}" class="filter-input" title="Start Date">
    <span style="color:var(--text-muted); font-size:0.75rem;">→</span>
    <input type="date" name="end" value="{{ filters.end }}" class="filter-input" title="End Date">

    <select name="model" class="filter-input" onchange="this.form.requestSubmit()">
      {% for m in model_ids %}
        <option value="{{ m }}" {% if m == filters.model_id %}selected{% endif %}>{{ m }}</option>
      {% endfor %}
    </select>

    <select name="currency" class="filter-input" onchange="this.form.requestSubmit()">
      <option value="INR" {% if ctx.currency == 'INR' %}selected{% endif %}>INR (₹)</option>
      <option value="USD" {% if ctx.currency == 'USD' %}selected{% endif %}>USD ($)</option>
      <option value="EUR" {% if ctx.currency == 'EUR' %}selected{% endif %}>EUR (€)</option>
      <option value="GBP" {% if ctx.currency == 'GBP' %}selected{% endif %}>GBP (£)</option>
    </select>

    <input type="number" step="0.1" name="fx" value="{{ filters.fx }}" placeholder="FX" title="USD/INR rate" style="width:4.5rem;" class="filter-input">
    <input type="number" step="100" name="sub" value="{{ filters.sub }}" placeholder="Sub" title="Subscription Spend" style="width:5.5rem;" class="filter-input">

    <button type="submit" class="btn">Filter</button>
    <a href="/?view={{ filters.view }}" class="btn">Reset</a>
    <button type="button" class="btn" title="Refresh local scans"
            hx-post="/api/refresh" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-headers='{"HX-Request":"true"}'>
      🔄
    </button>
    <button type="button" class="btn" onclick="toggleTheme()" title="Toggle Theme">🌓</button>
    <button type="button" class="btn" onclick="openDrawer('sync-drawer')" title="Operations & Snapshots">
      <span class="status-dot {% if runner_state and runner_state.running %}running pulse{% else %}idle{% endif %}"></span>
      ⚡ Sync & DB
    </button>
  </form>
</header>
```

- [ ] **Step 3: Write `agy_dash/ui/templates/partials/view_command.html` (F-08 Fix):**
```html
<div class="kpi-strip">
  {% for kpi in vm.token_kpis %}
    <div class="kpi-card">
      <div class="lbl"><span>{{ kpi.icon }} {{ kpi.lbl }}</span></div>
      <div class="val">{{ kpi.val }}</div>
      <div class="sub">{{ kpi.sub }}</div>
    </div>
  {% endfor %}
</div>

<div class="kpi-strip">
  {% for kpi in vm.econ_kpis %}
    <div class="kpi-card">
      <div class="lbl"><span>{{ kpi.icon }} {{ kpi.lbl }}</span></div>
      <div class="val">{{ kpi.val }}</div>
      <div class="sub">{{ kpi.sub }}</div>
    </div>
  {% endfor %}
</div>

{% if ctx.price_note %}
  <div class="callout warning">
    <b>Pricing Notice:</b> {{ ctx.price_note }}
  </div>
{% endif %}

<div class="callout">
  <b>Equivalent API Cost:</b> Modeled consumption bill on a metered public API; real marginal spend inside subscription quota is zero. Subscription spend is reported independently.
</div>

{% if vm.waste %}
  <div class="callout">
    <b>Waste Proxy:</b> <code>{{ vm.waste.cost }}</code> ({{ vm.waste.tokens_at_risk }} tokens at risk) — {{ vm.waste.share_of_calls }} of calls failed across {{ vm.waste.failure_count }} errors. Order-of-magnitude engineering proxy, not an actual invoice.
  </div>
{% endif %}

<div class="bento-grid">
  <div class="bento-panel col-8">
    <div class="panel-header"><div class="panel-title">Telemetry Burn Trajectory</div></div>
    <div class="chart-box-tall" data-chart="chart-daily-burn"></div>
    <script type="application/json" id="chart-daily-burn">{{ vm.charts.daily_burn_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-4">
    <div class="panel-header"><div class="panel-title">Token Distribution</div></div>
    <div class="chart-box" data-chart="chart-token-mix"></div>
    <script type="application/json" id="chart-token-mix">{{ vm.charts.token_mix_chart | tojson }}</script>

    <div style="margin-top:12px;"></div>
    <div class="chart-box" data-chart="chart-cost-burden"></div>
    <script type="application/json" id="chart-cost-burden">{{ vm.charts.cost_burden_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-7">
    <div class="panel-header">
      <div class="panel-title">Workspace & Project Attribution</div>
      <span style="font-size:0.7rem; color:var(--text-muted);">From history.jsonl</span>
    </div>
    <div class="chart-box" data-chart="chart-workspace"></div>
    <script type="application/json" id="chart-workspace">{{ vm.charts.workspace_chart | tojson }}</script>
    <div style="margin-top:12px;"></div>
    <table class="data-table">
      <thead>
        <tr><th>Project</th><th>Sessions</th><th>Tokens</th><th>Equivalent Cost</th></tr>
      </thead>
      <tbody>
        {% for r in vm.ws_rows %}
          <tr>
            <td class="mono">{{ r.project }}</td>
            <td class="mono">{{ r.sessions }}</td>
            <td class="mono">{{ r.tokens }}</td>
            <td class="mono">{{ r.cost }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="bento-panel col-5">
    <div class="panel-header"><div class="panel-title">Context Eviction Signals</div></div>
    <div class="chart-box" data-chart="chart-cache-thrash"></div>
    <script type="application/json" id="chart-cache-thrash">{{ vm.charts.cache_thrash_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-12">
    <div class="panel-header"><div class="panel-title">Top Heaviest Active Days</div></div>
    <table class="data-table">
      <thead>
        <tr><th>Date</th><th>Tokens</th><th>Calls</th><th>Cost</th></tr>
      </thead>
      <tbody>
        {% for d in vm.best_days %}
          <tr>
            <td class="mono">{{ d.date }}</td>
            <td class="mono">{{ d.tokens }}</td>
            <td class="mono">{{ d.calls }}</td>
            <td class="mono">{{ d.cost }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
```

- [ ] **Step 4: Write `agy_dash/ui/templates/partials/view_sessions.html` (F-04 Fix):**
```html
<!-- ZONE 1: FILTER BAR & KPI STRIP -->
<div class="bento-panel col-12" style="margin-bottom:1rem; padding:0.6rem 0.85rem; display:flex; justify-content:space-between; align-items:center;">
  <div style="display:flex; gap:0.4rem; align-items:center;">
    <span style="font-size:0.72rem; color:var(--text-muted); margin-right:0.3rem;">KIND:</span>
    <button type="button" class="btn" hx-get="/?view=sessions" hx-target="#workspace-canvas" hx-swap="outerHTML">All</button>
    <button type="button" class="btn" hx-get="/?view=sessions&kind=main" hx-target="#workspace-canvas" hx-swap="outerHTML">Main</button>
    <button type="button" class="btn" hx-get="/?view=sessions&kind=subagent" hx-target="#workspace-canvas" hx-swap="outerHTML">Subagent</button>
    <button type="button" class="btn" hx-get="/?view=sessions&kind=other" hx-target="#workspace-canvas" hx-swap="outerHTML">Other</button>
  </div>
  <div style="display:flex; gap:0.5rem; align-items:center;">
    <input type="search" name="search" placeholder="Search sessions..." class="filter-input" style="width:14rem;"
           hx-get="/?view=sessions" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-trigger="keyup changed delay:300ms">
    <button type="button" class="btn" hx-post="/api/refresh?scope=deep" hx-target="#workspace-canvas" hx-swap="outerHTML" hx-headers='{"HX-Request":"true"}'>🔄 Rescan Deep</button>
  </div>
</div>

<div class="kpi-strip">
  {% for kpi in vm.session_kpis %}
    <div class="kpi-card">
      <div class="lbl"><span>{{ kpi.icon }} {{ kpi.lbl }}</span></div>
      <div class="val">{{ kpi.val }}</div>
      <div class="sub">{{ kpi.sub }}</div>
    </div>
  {% endfor %}
</div>

<!-- ZONE 2: PERFORMANCE & SUBAGENT SWARM -->
<div class="bento-grid">
  <div class="bento-panel col-8">
    <div class="panel-header">
      <div class="panel-title">Session Workload Leaderboard</div>
      <a href="/api/export/sessions.csv" class="btn" style="font-size:0.7rem;">Download CSV</a>
    </div>
    <div class="chart-box" data-chart="chart-top-sessions"></div>
    <script type="application/json" id="chart-top-sessions">{{ vm.charts.top_sessions_chart | tojson }}</script>

    <div style="margin-top:1rem;"></div>
    <table class="data-table clickable">
      <thead>
        <tr><th>Session ID</th><th>Label</th><th>Kind</th><th>Tokens</th><th>Cost</th><th>Active</th></tr>
      </thead>
      <tbody>
        {% for s in vm.session_rows %}
          <tr hx-get="/partials/session-detail/{{ s.session_id }}" hx-target="#session-drawer-content"
              onclick="openDrawer('session-drawer')">
            <td class="mono">{{ s.session_id[:8] }}</td>
            <td>{{ s.label }}</td>
            <td><span class="btn" style="padding:0.1rem 0.4rem; font-size:0.65rem;">{{ s.kind }}</span></td>
            <td class="mono">{{ s.total }}</td>
            <td class="mono">{{ s.cost }}</td>
            <td class="mono">{{ s.last_date }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="bento-panel col-4">
    <div class="panel-header"><div class="panel-title">Session Class Split</div></div>
    <div class="chart-box" data-chart="chart-session-kinds"></div>
    <script type="application/json" id="chart-session-kinds">{{ vm.charts.session_kinds_chart | tojson }}</script>

    <div style="margin-top:12px;"></div>
    <div class="chart-box" data-chart="chart-calls-sessions"></div>
    <script type="application/json" id="chart-calls-sessions">{{ vm.charts.calls_vs_sessions_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Active (Busy) vs Idle (Waiting) Hours</div></div>
    <div class="chart-box" data-chart="chart-time-budget"></div>
    <script type="application/json" id="chart-time-budget">{{ vm.charts.time_budget_chart | tojson }}</script>
    <div class="callout" style="font-size:0.7rem;">Gaps capped at 4h: an overnight pause counts as 4h, not 12h.</div>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Reasoning Step Ratio (%)</div></div>
    <div class="chart-box" data-chart="chart-thinking-ratio"></div>
    <script type="application/json" id="chart-thinking-ratio">{{ vm.charts.thinking_ratio_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Tool Invocation Mix</div></div>
    <div class="chart-box" data-chart="chart-tool-mix"></div>
    <script type="application/json" id="chart-tool-mix">{{ vm.charts.tool_mix_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Tool Execution Latencies</div></div>
    <table class="data-table">
      <thead><tr><th>Tool</th><th>Calls</th><th>P50 Latency</th><th>P90 Latency</th><th>Total Time</th></tr></thead>
      <tbody>
        {% for r in vm.turn_rows %}
          <tr><td class="mono">{{ r.tool }}</td><td class="mono">{{ r.calls }}</td><td class="mono">{{ r.p50 }}</td><td class="mono">{{ r.p90 }}</td><td class="mono">{{ r.total_min }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<div class="kpi-strip" style="margin-top:1rem;">
  {% for kpi in vm.swarm_kpis %}
    <div class="kpi-card">
      <div class="lbl">{{ kpi.icon }} {{ kpi.lbl }}</div>
      <div class="val">{{ kpi.val }}</div>
    </div>
  {% endfor %}
</div>

<div class="bento-grid" style="margin-top:1rem;">
  <div class="bento-panel col-4">
    <div class="panel-header"><div class="panel-title">Engine Switches</div></div>
    <div class="chart-box" data-chart="chart-model-switches"></div>
    <script type="application/json" id="chart-model-switches">{{ vm.charts.model_switches_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-4">
    <div class="panel-header"><div class="panel-title">MCP Server Dispatches</div></div>
    <div class="chart-box" data-chart="chart-mcp"></div>
    <script type="application/json" id="chart-mcp">{{ vm.charts.mcp_invocations_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-4">
    <div class="panel-header"><div class="panel-title">Artifacts & Messages</div></div>
    <table class="data-table">
      <thead><tr><th>Artifact</th><th>Gate</th></tr></thead>
      <tbody>
        {% for a in vm.artifact_rows %}
          <tr><td class="mono">{{ a.name }}</td><td>{{ a.gate }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>

<!-- ZONE 3: FRICTION & RELIABILITY -->
<div class="kpi-strip" style="margin-top:1rem;">
  {% for kpi in vm.context_kpis %}
    <div class="kpi-card">
      <div class="lbl">{{ kpi.icon }} {{ kpi.lbl }}</div>
      <div class="val">{{ kpi.val }}</div>
    </div>
  {% endfor %}
</div>

<div class="bento-grid">
  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Failure Steps per Day</div></div>
    <div class="chart-box" data-chart="chart-failure-daily"></div>
    <script type="application/json" id="chart-failure-daily">{{ vm.charts.failure_daily_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Top Repeated Failure Signatures</div></div>
    <table class="data-table">
      <thead><tr><th>Error Signature</th><th>Count</th></tr></thead>
      <tbody>
        {% for f in vm.fail_rows %}
          <tr><td class="mono" style="color:var(--signal-rose);">{{ f.text }}</td><td class="mono">{{ f.count }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">User Approval Denials</div></div>
    <table class="data-table">
      <thead><tr><th>Date</th><th>Command</th><th>Wait</th></tr></thead>
      <tbody>
        {% for d in vm.denial_rows %}
          <tr><td class="mono">{{ d.date }}</td><td class="mono">{{ d.command }}</td><td class="mono">{{ d.wait }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Slowest Shell Commands</div></div>
    <table class="data-table">
      <thead><tr><th>Command</th><th>Window</th><th>Exit</th></tr></thead>
      <tbody>
        {% for c in vm.cmd_rows %}
          <tr><td class="mono">{{ c.command }}</td><td class="mono">{{ c.duration }}</td><td class="mono">{{ c.exit_code }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
<div class="callout" style="margin-top:1rem;">
  <b>Execution Window Disclaimer:</b> CLI duration stamps reflect the full execution window including process queueing and waiting, not pure CPU stopwatch time.
</div>
```

- [ ] **Step 5: Write `agy_dash/ui/templates/partials/view_economics.html`, `forecast_stage.html`, and `lab_stage.html` (F-03 Fix):**

`agy_dash/ui/templates/partials/view_economics.html`:
```html
<div id="forecast-stage-container">
  {% include "partials/forecast_stage.html" %}
</div>

<div id="lab-stage-container" style="margin-top:1.5rem;">
  {% include "partials/lab_stage.html" %}
</div>
```

`agy_dash/ui/templates/partials/forecast_stage.html`:
```html
<div class="bento-panel col-12" style="margin-bottom:1rem; padding:0.75rem 1rem;">
  <form hx-get="/partials/forecast-stage" hx-target="#forecast-stage-container" hx-swap="outerHTML" style="display:flex; gap:0.6rem; align-items:center; flex-wrap:wrap;">
    <span style="font-family:var(--font-display); font-weight:700; font-size:0.8rem;">STAGE 1 // FORECAST CONTROLS:</span>
    <select name="target" class="filter-input">
      <option value="Total tokens" {% if vm.fc_params.target == 'Total tokens' %}selected{% endif %}>Target: Total Tokens</option>
      <option value="Fresh input tokens" {% if vm.fc_params.target == 'Fresh input tokens' %}selected{% endif %}>Target: Fresh Input</option>
      <option value="Cached input tokens" {% if vm.fc_params.target == 'Cached input tokens' %}selected{% endif %}>Target: Cached Input</option>
      <option value="Output tokens" {% if vm.fc_params.target == 'Output tokens' %}selected{% endif %}>Target: Output</option>
      <option value="Model calls" {% if vm.fc_params.target == 'Model calls' %}selected{% endif %}>Target: Model Calls</option>
      <option value="API-equivalent cost" {% if vm.fc_params.target == 'API-equivalent cost' %}selected{% endif %}>Target: API Cost</option>
    </select>

    <select name="method" class="filter-input">
      <option value="Bootstrap resampling" {% if vm.fc_params.method == 'Bootstrap resampling' %}selected{% endif %}>Bootstrap Resampling</option>
      <option value="Linear extrapolation (baseline)" {% if vm.fc_params.method == 'Linear extrapolation (baseline)' %}selected{% endif %}>Linear Baseline</option>
      <option value="Monte Carlo simulation" {% if vm.fc_params.method == 'Monte Carlo simulation' %}selected{% endif %}>Monte Carlo</option>
      <option value="Holt linear trend" {% if vm.fc_params.method == 'Holt linear trend' %}selected{% endif %}>Holt Linear Trend</option>
    </select>

    <label style="font-size:0.75rem; color:var(--text-muted);">Horizon:
      <input type="number" name="horizon" value="{{ vm.fc_params.horizon }}" min="7" max="90" style="width:4rem;" class="filter-input"> days
    </label>

    <select name="freq" class="filter-input">
      <option value="daily" {% if vm.fc_params.freq == 'daily' %}selected{% endif %}>Daily Cadence</option>
      <option value="weekly" {% if vm.fc_params.freq == 'weekly' %}selected{% endif %}>Weekly Cadence</option>
      <option value="monthly" {% if vm.fc_params.freq == 'monthly' %}selected{% endif %}>Monthly Cadence</option>
    </select>

    <button type="submit" class="btn btn-primary">Project</button>
  </form>
</div>

<div class="kpi-strip">
  {% for kpi in vm.fc_kpis %}
    <div class="kpi-card">
      <div class="lbl"><span>{{ kpi.icon }} {{ kpi.lbl }}</span></div>
      <div class="val">{{ kpi.val }}</div>
      <div class="sub">{{ kpi.sub }}</div>
    </div>
  {% endfor %}
</div>

<div class="callout">
  <b>Predictive Engine:</b> {{ vm.fc_assumptions }}. {{ vm.uncertainty_note }}
</div>

<div class="bento-grid">
  <div class="bento-panel col-8">
    <div class="panel-header"><div class="panel-title">Future Trajectory Projection (P10 - P50 - P90)</div></div>
    <div class="chart-box-tall" data-chart="chart-forecast"></div>
    <script type="application/json" id="chart-forecast">{{ vm.charts.forecast_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-4">
    <div class="panel-header">
      <div class="panel-title">Cumulative Horizon Summary</div>
      <a href="/api/export/forecast.csv" class="btn" style="font-size:0.7rem;">Download CSV</a>
    </div>
    <table class="data-table" style="margin-bottom:1rem;">
      <thead><tr><th>Percentile</th><th>Volume</th></tr></thead>
      <tbody>
        {% for s in vm.fc_summary %}
          <tr><td>{{ s.tier }}</td><td class="mono">{{ s.val }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
    <div class="callout" style="font-size:0.72rem;">Median forecast is <b>{{ vm.payback_pct }}</b> of subscription spend.</div>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Historical Aggregation Cadence</div></div>
    <div class="chart-box" data-chart="chart-cadence"></div>
    <script type="application/json" id="chart-cadence">{{ vm.charts.cadence_chart | tojson }}</script>
  </div>

  <div class="bento-panel col-6">
    <div class="panel-header"><div class="panel-title">Daily Projected Schedule</div></div>
    <div style="max-height:260px; overflow-y:auto;">
      <table class="data-table">
        <thead><tr><th>Date</th><th>P10 Floor</th><th>P50 Median</th><th>P90 Surge</th></tr></thead>
        <tbody>
          {% for r in vm.schedule_rows %}
            <tr><td class="mono">{{ r.date }}</td><td class="mono">{{ r.low }}</td><td class="mono">{{ r.median }}</td><td class="mono">{{ r.high }}</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
```

`agy_dash/ui/templates/partials/lab_stage.html`:
```html
<div class="bento-panel col-12" style="margin-bottom:1rem; padding:0.75rem 1rem;">
  <form hx-get="/partials/lab-stage" hx-target="#lab-stage-container" hx-swap="outerHTML">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
      <span style="font-family:var(--font-display); font-weight:700; font-size:0.8rem;">STAGE 2 // WHAT-IF SIMULATOR CONTROLS:</span>
      <button type="submit" class="btn btn-primary">Simulate Scenario</button>
    </div>
    <div style="display:flex; gap:1.25rem; flex-wrap:wrap; align-items:center;">
      <label style="font-size:0.75rem;">Prompt Multiplier:
        <input type="number" step="0.1" min="0.1" max="5.0" name="prompt_mult" value="{{ vm.lab_params.prompt_mult }}" class="filter-input" style="width:4.5rem;">
      </label>
      <label style="font-size:0.75rem;">Output Multiplier:
        <input type="number" step="0.1" min="0.1" max="5.0" name="output_mult" value="{{ vm.lab_params.output_mult }}" class="filter-input" style="width:4.5rem;">
      </label>
      <label style="font-size:0.75rem;">
        <input type="checkbox" name="use_ratio" value="true" {% if vm.lab_params.use_ratio %}checked{% endif %}> Override Cache Hit Rate:
        <input type="number" step="1" min="0" max="100" name="ratio" value="{{ vm.lab_params.ratio }}" class="filter-input" style="width:4rem;">%
      </label>
    </div>
    <div style="display:flex; gap:0.75rem; margin-top:0.75rem; flex-wrap:wrap; font-size:0.72rem;">
      <span style="color:var(--text-muted);">Compare Models:</span>
      {% for m in vm.available_models %}
        <label><input type="checkbox" name="chosen_models" value="{{ m.id }}" {% if m.checked %}checked{% endif %}> {{ m.id }}</label>
      {% endfor %}
    </div>
  </form>
</div>

<div class="kpi-strip" style="grid-template-columns: repeat(4, 1fr);">
  <div class="kpi-card"><div class="lbl">BASELINE FRESH</div><div class="val">{{ vm.workload_baseline.fresh_in }}</div></div>
  <div class="kpi-card"><div class="lbl">BASELINE CACHED</div><div class="val">{{ vm.workload_baseline.cached }}</div></div>
  <div class="kpi-card"><div class="lbl">BASELINE OUTPUT</div><div class="val">{{ vm.workload_baseline.output }}</div></div>
  <div class="kpi-card"><div class="lbl">BASELINE HIT RATE</div><div class="val">{{ vm.workload_baseline.cache_hit_rate }}</div></div>
</div>

<div class="bento-grid">
  <div class="bento-panel col-7">
    <div class="panel-header">
      <div class="panel-title">What-If Multi-Model Benchmark</div>
      <button type="button" class="btn" onclick="openDrawer('catalog-drawer')">Price Catalog</button>
    </div>
    <div class="chart-box" data-chart="chart-benchmark"></div>
    <script type="application/json" id="chart-benchmark">{{ vm.charts.benchmark_chart | tojson }}</script>

    <table class="data-table" style="margin-top:1rem;">
      <thead>
        <tr><th>Model</th><th>Vendor</th><th>Workload Cost</th><th>Rate/MTok</th><th>Tokens/Spend</th><th>vs Cheapest</th><th>Pricing As Of</th></tr>
      </thead>
      <tbody>
        {% for r in vm.cmp_rows %}
          <tr>
            <td class="mono">{{ r.model }}</td>
            <td>{{ r.vendor }}</td>
            <td class="mono">{{ r.cost }}</td>
            <td class="mono">{{ r.cost_per_mtok }}</td>
            <td class="mono">{{ r.tokens_per_curr }}</td>
            <td class="mono">{{ r.vs_cheapest }}</td>
            <td class="mono" style="font-size:0.7rem;">{{ r.version_date }} {% if r.estimate %}<span style="color:var(--signal-amber);">[Est]</span>{% endif %}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
    <div class="callout" style="font-size:0.72rem; margin-top:0.75rem;">
      <b>Honesty Guarantee:</b> Simulations assume identical token volumes across engines; reasoning token expansion and prompt-caching behaviors differ significantly in real execution.
    </div>
  </div>

  <div class="bento-panel col-5">
    <div class="panel-header"><div class="panel-title">Fixed Subscription vs Metered Value</div></div>
    <div class="kpi-strip" style="grid-template-columns:1fr 1fr; margin-bottom:1rem;">
      <div class="kpi-card">
        <div class="lbl">Actual Subscription</div>
        <div class="val">{{ vm.sub_card.actual_spend }}</div>
      </div>
      <div class="kpi-card">
        <div class="lbl">API Value (Selected)</div>
        <div class="val">{{ vm.sub_card.api_val }}</div>
      </div>
    </div>
    <div class="chart-box" data-chart="chart-sub"></div>
    <script type="application/json" id="chart-sub">{{ vm.charts.sub_chart | tojson }}</script>
    <div class="callout" style="font-size:0.72rem; margin-top:0.75rem;">
      Inside a subscription quota, real marginal spend is zero. The API value displays the equivalent market price if billed on metered consumption.
    </div>
  </div>
</div>
```

- [ ] **Step 6: Write Drawer Partials (`sync_drawer.html`, `job_status.html`, `session_drawer.html`, `session_detail.html`, `catalog_drawer.html`) (F-05, F-06 Fixes):**

`agy_dash/ui/templates/partials/sync_drawer.html`:
```html
<div id="sync-drawer" class="drawer">
  <div class="drawer-header">
    <div style="font-family:var(--font-display); font-weight:700;">OPERATIONS & SNAPSHOTS</div>
    <button type="button" class="btn" onclick="closeDrawers()">✕</button>
  </div>
  <div class="drawer-body">
    <h4 style="margin-bottom:0.5rem; font-size:0.8rem;">Telemetry Source Integrity</h4>
    <div class="callout">
      Status: <span class="mono" style="color:{% if sync_data.source_online %}var(--signal-emerald){% else %}var(--signal-rose){% endif %};">
        {% if sync_data.source_online %}ONLINE{% else %}OFFLINE{% endif %}
      </span><br>
      Directory: <code>{{ sync_data.brain_root }}</code><br>
      Sessions Scanned: <span class="mono">{{ sync_data.sessions_scanned }}</span>
    </div>

    {% if sync_data.consistency_issues %}
      <div class="callout warning">
        <b>Consistency Discrepancies:</b>
        <ul style="margin:0.25rem 0 0 1rem;">
          {% for issue in sync_data.consistency_issues %}<li>{{ issue }}</li>{% endfor %}
        </ul>
        <span style="font-size:0.68rem; color:var(--text-muted);">Discrepancies may occur when sessions span filter boundaries.</span>
      </div>
    {% else %}
      <div class="callout" style="color:var(--signal-emerald);">
        ✓ Source records and daily totals are mathematically consistent.
      </div>
    {% endif %}

    <h4 style="margin:1.5rem 0 0.5rem 0; font-size:0.8rem;">Background Extractor Process</h4>
    <form hx-post="/api/jobs/start" hx-target="#job-status-panel" hx-headers='{"HX-Request":"true"}'>
      <div style="display:flex; gap:0.5rem; margin-bottom:1rem;">
        <select name="report" class="filter-input" style="flex:1;">
          <option value="all">Report: All</option>
          <option value="daily">Report: Daily</option>
          <option value="sessions">Report: Sessions</option>
          <option value="tips">Report: Tips</option>
        </select>
        <button type="submit" class="btn btn-primary">Run Extractor</button>
      </div>
    </form>

    <div id="job-status-panel">
      {% include "partials/job_status.html" %}
    </div>

    <h4 style="margin:1.5rem 0 0.5rem 0; font-size:0.8rem;">SQLite Snapshot Ledger</h4>
    <form hx-post="/api/snapshots/ingest" hx-target="#snapshot-counts" hx-headers='{"HX-Request":"true"}'>
      <button type="submit" class="btn">Save Snapshot Now</button>
    </form>
    <div id="snapshot-counts" style="margin-top:0.5rem; font-size:0.75rem;" class="mono">
      Database: {{ sync_data.db_counts.session_facts }} sessions · {{ sync_data.db_counts.daily_facts }} daily · {{ sync_data.db_counts.runs }} runs.
    </div>

    <h4 style="margin:1.5rem 0 0.5rem 0; font-size:0.8rem;">Historical Ingestion Runs</h4>
    <table class="data-table" style="font-size:0.72rem;">
      <thead><tr><th>Run</th><th>Started</th><th>Duration</th><th>Report</th><th>Status</th></tr></thead>
      <tbody>
        {% for r in sync_data.runs %}
          <tr>
            <td class="mono">#{{ r.run_id }}</td>
            <td class="mono">{{ r.started_at[:19] }}</td>
            <td class="mono">{{ r.duration_seconds }}s</td>
            <td class="mono">{{ r.report }}</td>
            <td class="mono">{{ r.status }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    <details style="margin-top:1rem;">
      <summary style="font-size:0.75rem; cursor:pointer; color:var(--text-muted);">Standard Output (stdout)</summary>
      <pre class="mono" style="font-size:0.68rem; background:rgba(0,0,0,0.4); padding:0.5rem; max-height:200px; overflow:auto;">{{ sync_data.stdout or "(empty)" }}</pre>
    </details>
    <details style="margin-top:0.5rem;">
      <summary style="font-size:0.75rem; cursor:pointer; color:var(--text-muted);">Standard Error (stderr)</summary>
      <pre class="mono" style="font-size:0.68rem; background:rgba(0,0,0,0.4); padding:0.5rem; max-height:200px; overflow:auto;">{{ sync_data.stderr or "(empty)" }}</pre>
    </details>
  </div>
</div>
```

`agy_dash/ui/templates/partials/job_status.html` (F-05 Fix: Polling occurs only when running):
```html
<div class="bento-panel" style="padding:0.75rem;"
     {% if runner_state and runner_state.running %}hx-get="/api/jobs/status" hx-trigger="every 2s" hx-swap="outerHTML"{% endif %}>
  <div style="display:flex; justify-content:space-between; margin-bottom:0.5rem;">
    <span class="mono" style="font-size:0.75rem;">Status: <b>{{ runner_state.status | upper if runner_state else 'IDLE' }}</b></span>
    <span class="mono" style="font-size:0.75rem;">Exit: {{ runner_state.exit_code if runner_state and runner_state.exit_code is not none else '-' }}</span>
  </div>
  {% if runner_state and runner_state.command %}
    <pre class="mono" style="font-size:0.68rem; background:rgba(0,0,0,0.3); padding:0.4rem; border-radius:4px; overflow-x:auto;">{{ " ".join(runner_state.command) }}</pre>
  {% endif %}
</div>
```

`agy_dash/ui/templates/partials/session_drawer.html`:
```html
<div id="session-drawer" class="drawer">
  <div class="drawer-header">
    <div style="font-family:var(--font-display); font-weight:700;">SESSION INSPECTOR</div>
    <button type="button" class="btn" onclick="closeDrawers()">✕</button>
  </div>
  <div id="session-drawer-content" class="drawer-body">
    <div style="color:var(--text-muted); font-size:0.8rem;">Select a session from the table to inspect details.</div>
  </div>
</div>
```

`agy_dash/ui/templates/partials/session_detail.html` (F-06 Fix: Full detail partial):
```html
<div style="margin-bottom:1rem;">
  <div style="display:flex; justify-content:space-between; align-items:baseline;">
    <span class="mono" style="font-size:1.1rem; font-weight:700; color:var(--brand-accent);">{{ detail.session_id[:8] }}</span>
    <span class="btn" style="padding:0.1rem 0.5rem; font-size:0.7rem;">{{ detail.kind | upper }}</span>
  </div>
  <div style="font-size:0.85rem; margin-top:0.25rem;">{{ detail.label }}</div>
  {% if detail.meta and detail.meta.workspace %}
    <div style="font-size:0.7rem; color:var(--text-muted); margin-top:0.2rem;" class="mono">Workspace: {{ detail.meta.workspace }}</div>
  {% endif %}
</div>

<div class="kpi-strip" style="grid-template-columns: repeat(2, 1fr); margin-bottom:1rem;">
  <div class="kpi-card">
    <div class="lbl">TOTAL TOKENS</div>
    <div class="val">{{ detail.tokens.total }}</div>
    <div class="sub">{{ detail.tokens.fresh_in }} fresh · {{ detail.tokens.cached }} cached</div>
  </div>
  <div class="kpi-card">
    <div class="lbl">API COST</div>
    <div class="val">{{ detail.cost }}</div>
    <div class="sub">{{ detail.calls }} model calls</div>
  </div>
</div>

{% if detail.meta and detail.meta.parent_id %}
  <div class="callout" style="font-size:0.75rem; margin-bottom:1rem;">
    <b>Subagent Lineage:</b> Parent Session <code class="mono">{{ detail.meta.parent_id[:8] }}</code> · Role: {{ detail.meta.get('subagent_type', 'subagent') }}
  </div>
{% endif %}

{% if detail.tools %}
  <h4 style="margin:1rem 0 0.5rem 0; font-size:0.8rem;">Tool Invocations</h4>
  <table class="data-table" style="font-size:0.75rem;">
    <thead><tr><th>Tool</th><th>Calls</th><th>Avg Time</th></tr></thead>
    <tbody>
      {% for t in detail.tools %}
        <tr><td class="mono">{{ t.tool }}</td><td class="mono">{{ t.calls }}</td><td class="mono">{{ t.avg_sec }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endif %}

{% if detail.commands %}
  <h4 style="margin:1rem 0 0.5rem 0; font-size:0.8rem;">Shell Command Executions</h4>
  <table class="data-table" style="font-size:0.72rem;">
    <thead><tr><th>Command</th><th>Window</th><th>Exit</th></tr></thead>
    <tbody>
      {% for c in detail.commands %}
        <tr>
          <td class="mono" title="{{ c.command }}">{{ c.command[:45] }}</td>
          <td class="mono">{{ c.duration }}</td>
          <td class="mono">{{ c.exit_code }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% endif %}

{% if detail.failures %}
  <h4 style="margin:1rem 0 0.5rem 0; font-size:0.8rem; color:var(--signal-rose);">Session Failures</h4>
  <table class="data-table" style="font-size:0.72rem;">
    <thead><tr><th>Date</th><th>Error Text</th></tr></thead>
    <tbody>
      {% for f in detail.failures %}
        <tr><td class="mono">{{ f.date }}</td><td class="mono" style="color:var(--signal-rose);">{{ f.text[:70] }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endif %}

{% if detail.artifacts %}
  <h4 style="margin:1rem 0 0.5rem 0; font-size:0.8rem;">Generated Artifacts</h4>
  <table class="data-table" style="font-size:0.72rem;">
    <thead><tr><th>Artifact</th><th>Gate</th><th>Summary</th></tr></thead>
    <tbody>
      {% for a in detail.artifacts %}
        <tr><td class="mono">{{ a.name }}</td><td class="mono">{{ a.gate }}</td><td>{{ a.summary }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
{% endif %}
```

`agy_dash/ui/templates/partials/catalog_drawer.html`:
```html
<div id="catalog-drawer" class="drawer" style="width:640px;">
  <div class="drawer-header">
    <div style="font-family:var(--font-display); font-weight:700;">PRICE CATALOG REFERENCE</div>
    <button type="button" class="btn" onclick="closeDrawers()">✕</button>
  </div>
  <div class="drawer-body">
    <table class="data-table">
      <thead><tr><th>Model ID</th><th>Vendor</th><th>Input / Mtok</th><th>Cached / Mtok</th><th>Output / Mtok</th><th>Effective</th></tr></thead>
      <tbody>
        {% for e in ctx.catalog.entries %}
          <tr>
            <td class="mono"><b>{{ e.model_id }}</b></td>
            <td>{{ e.vendor }}</td>
            <td class="mono">${{ "%.4f"|format(e.input_usd) }}</td>
            <td class="mono">${{ "%.4f"|format(e.cached_usd) }}</td>
            <td class="mono">${{ "%.4f"|format(e.output_usd) }}</td>
            <td class="mono">{{ e.effective_from }}</td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
```

- [ ] **Verify:**
```powershell
Get-ChildItem agy_dash\ui\templates\partials\*.html | Select-Object Name
```
Expected: All 11 partial templates exist.

- [ ] **Step 7: Commit:**
```bash
git add agy_dash/ui/templates
git commit -m "feat(ui): complete jinja2 templates and partials resolving F-02 to F-08" -- agy_dash/ui/templates
```

---

### Task 10: FastAPI Application, Routes, & Security Guards

**Files:** Create `app.py`. Test: `tests/test_web_app.py`

- [ ] **Step 1: Write `tests/test_web_app.py`:**
```python
import io
import pytest
from fastapi.testclient import TestClient
import app as app_module
from agy_dash import config as cfgmod
from agy_dash import pricing
from agy_dash.ui import state


@pytest.fixture
def client(usage, rich_brain, monkeypatch, tmp_path):
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


def test_index_renders_html_shell(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "ANTIGRAVITY" in res.text
    assert "01 // COMMAND" in res.text


def test_switch_workspace_views(client):
    for view in ("command", "sessions", "economics"):
        res = client.get(f"/?view={view}")
        assert res.status_code == 200


def test_session_detail_endpoint(client, usage):
    sid = usage.sessions["session_id"].iloc[0]
    res = client.get(f"/partials/session-detail/{sid}")
    assert res.status_code == 200
    assert sid[:8] in res.text


def test_forecast_and_lab_partials(client):
    res_fc = client.get("/partials/forecast-stage?target=Total+tokens&method=Bootstrap+resampling")
    assert res_fc.status_code == 200
    assert "STAGE 1 // FORECAST CONTROLS" in res_fc.text

    res_lab = client.get("/partials/lab-stage?prompt_mult=1.5")
    assert res_lab.status_code == 200
    assert "STAGE 2 // WHAT-IF SIMULATOR CONTROLS" in res_lab.text


def test_refresh_endpoint_clears_cache(client):
    res = client.post("/api/refresh", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert "workspace-canvas" in res.text


def test_csv_exports(client):
    for path in ("/api/export/daily.csv", "/api/export/sessions.csv", "/api/export/forecast.csv"):
        res = client.get(path)
        assert res.status_code == 200
        assert "text/csv" in res.headers["content-type"]


def test_csrf_protection_on_post_endpoints(client):
    res = client.post("/api/snapshots/ingest")
    assert res.status_code == 400
    res_valid = client.post("/api/snapshots/ingest", headers={"HX-Request": "true"})
    assert res_valid.status_code == 200
```

- [ ] **Step 2: Write `app.py`:**
```python
"""Antigravity Telemetry Control — FastAPI Entry Point.

Run: python app.py (or run.ps1 / uvicorn app:app --port 8501)
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Annotated

import pandas as pd
import uvicorn
from fastapi import FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agy_dash import config as cfgmod
from agy_dash import snapshots
from agy_dash.source import SourceError
from agy_dash.ui import common, state, views

APP_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "agy_dash" / "ui" / "templates"
STATIC_DIR = APP_DIR / "agy_dash" / "ui" / "static"

app = FastAPI(title="Antigravity Telemetry Control", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Register template filters
templates.env.filters["fmt_tokens"] = common.fmt_tokens
templates.env.filters["fmt_money"] = common.fmt_money
templates.env.filters["fmt_pct"] = common.fmt_pct


def _check_csrf(hx_request: str | None) -> None:
    if not hx_request:
        raise HTTPException(status_code=400, detail="Missing required HX-Request header")


def _get_context_and_filters(request: Request):
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    entries = state.load_catalog()
    model_ids = [e.model_id for e in entries]
    query_params = dict(request.query_params)
    filters = state.parse_filters(query_params, cfg, usage, model_ids)
    ctx = state.build_context(cfg, usage, entries, filters, runner=state.get_runner(cfg))
    return cfg, usage, entries, model_ids, query_params, filters, ctx


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = cfgmod.get_config()
    try:
        usage = state.load_usage(cfg)
    except SourceError as exc:
        return templates.TemplateResponse("error.html", {
            "request": request, "message": str(exc),
            "hint": f"Verify brain_root ({cfg.brain_root}) and extractor_script ({cfg.extractor_script}) in config/config.json.",
        }, status_code=500)

    entries = state.load_catalog()
    model_ids = [e.model_id for e in entries]
    query_params = dict(request.query_params)
    filters = state.parse_filters(query_params, cfg, usage, model_ids)

    try:
        ctx = state.build_context(cfg, usage, entries, filters, runner=state.get_runner(cfg))
    except state.PricingError as exc:
        return templates.TemplateResponse("error.html", {"request": request, "message": str(exc)}, status_code=400)

    deep_data = state.load_deep(str(cfg.brain_root))

    if filters.view == "command":
        vm = views.build_command_view(ctx, deep_data)
    elif filters.view == "sessions":
        kind_param = query_params.get("kind")
        kind_list = [kind_param] if kind_param else None
        vm = views.build_sessions_view(
            ctx, deep_data, kind_sel=kind_list,
            top_n=int(query_params.get("top", 25)),
            search=query_params.get("search"),
        )
    else:
        vm = views.build_economics_view(ctx, query_params, query_params)

    runner_state = ctx.runner.state if ctx.runner else None
    sync_data = views.build_sync_drawer(ctx)

    return templates.TemplateResponse("base.html", {
        "request": request, "ctx": ctx, "filters": filters,
        "model_ids": model_ids, "vm": vm, "runner_state": runner_state,
        "sync_data": sync_data,
    })


@app.get("/partials/forecast-stage", response_class=HTMLResponse)
def forecast_stage(request: Request):
    cfg, usage, entries, model_ids, query_params, filters, ctx = _get_context_and_filters(request)
    vm = views.build_economics_view(ctx, query_params, query_params)
    return templates.TemplateResponse("partials/forecast_stage.html", {"request": request, "ctx": ctx, "vm": vm})


@app.get("/partials/lab-stage", response_class=HTMLResponse)
def lab_stage(request: Request):
    cfg, usage, entries, model_ids, query_params, filters, ctx = _get_context_and_filters(request)
    lab_params = dict(query_params)
    if "chosen_models" in request.query_params:
        lab_params["chosen_models"] = request.query_params.getlist("chosen_models")
    vm = views.build_economics_view(ctx, query_params, lab_params)
    return templates.TemplateResponse("partials/lab_stage.html", {"request": request, "ctx": ctx, "vm": vm})


@app.get("/partials/session-detail/{session_id}", response_class=HTMLResponse)
def session_detail(request: Request, session_id: str):
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    entries = state.load_catalog()
    filters = state.parse_filters({}, cfg, usage, [e.model_id for e in entries])
    ctx = state.build_context(cfg, usage, entries, filters, runner=None)
    deep_data = state.load_deep(str(cfg.brain_root))
    detail = views.build_session_detail(ctx, deep_data, session_id)
    if not detail:
        return HTMLResponse("<p style='color:var(--signal-rose); padding:1rem;'>Session not found.</p>", status_code=404)
    return templates.TemplateResponse("partials/session_detail.html", {"request": request, "detail": detail})


@app.post("/api/refresh", response_class=HTMLResponse)
def refresh_scan(request: Request, scope: str | None = None, hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    if scope == "deep":
        state.DEEP_CACHE.clear()
    else:
        state.clear_all_caches()
    return index(request)


@app.post("/api/snapshots/ingest", response_class=HTMLResponse)
def save_snapshot(request: Request, hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    try:
        conn = snapshots.connect(cfg.db_path)
        info = snapshots.ingest(conn, usage)
        cnt = snapshots.counts(conn)
        conn.close()
        return HTMLResponse(f"<span style='color:var(--signal-emerald);'>Snapshot recorded: {info['sessions']} sessions ({cnt['runs']} total runs).</span>")
    except Exception as exc:
        return HTMLResponse(f"<span style='color:var(--signal-rose);'>Snapshot failed: {exc}</span>", status_code=500)


@app.post("/api/jobs/start", response_class=HTMLResponse)
def start_job(request: Request, report: Annotated[str, Form()] = "all", hx_request: Annotated[str | None, Header()] = None):
    _check_csrf(hx_request)
    cfg = cfgmod.get_config()
    runner = state.get_runner(cfg)
    runner.start(report)
    return templates.TemplateResponse("partials/job_status.html", {"request": request, "runner_state": runner.state})


@app.get("/api/jobs/status", response_class=HTMLResponse)
def job_status(request: Request):
    cfg = cfgmod.get_config()
    runner = state.get_runner(cfg)
    runner.poll()
    return templates.TemplateResponse("partials/job_status.html", {"request": request, "runner_state": runner.state})


@app.get("/api/export/daily.csv")
def export_daily():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    buf = io.StringIO()
    usage.daily.to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_daily.csv"})


@app.get("/api/export/sessions.csv")
def export_sessions():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    buf = io.StringIO()
    usage.sessions.to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_sessions.csv"})


@app.get("/api/export/forecast.csv")
def export_forecast():
    cfg = cfgmod.get_config()
    usage = state.load_usage(cfg)
    values = usage.daily["total"].to_numpy(dtype=float) if not usage.daily.empty else []
    fc = views.stats.run_forecast("Bootstrap resampling", values, 30, last_date=usage.daily["date"].max() if not usage.daily.empty else None)
    buf = io.StringIO()
    fc.to_frame().to_csv(buf, index=False)
    return Response(content=buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=antigravity_forecast.csv"})


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8501, reload=True)
```

- [ ] **Verify:** `.venv\Scripts\python.exe -m pytest tests/test_web_app.py`
Expected: all tests pass.

- [ ] **Step 3: Commit:**
```bash
git add app.py tests/test_web_app.py
git commit -m "feat(ui): fastapi application entry point, route handlers, and csrf protection" -- app.py tests/test_web_app.py
```

---

### Task 11: Production Launcher Script & Documentation

**Files:** Modify `run.ps1`, `README.md`

- [ ] **Step 1: Update `run.ps1`:**
```powershell
# Antigravity Telemetry Control Launcher
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment not found at .venv. Run 'uv venv' and install dependencies."
    exit 1
}

Write-Host "Launching Antigravity Mission Telemetry at http://127.0.0.1:8501 ..." -ForegroundColor Cyan
& $venvPython -m uvicorn app:app --host 127.0.0.1 --port 8501 --reload
```

- [ ] **Step 2: Update `README.md` to document the FastAPI + Mission Telemetry architecture.**

- [ ] **Verify:**
```powershell
Get-Content run.ps1 | Select-String "uvicorn"
```
Expected: match found.

- [ ] **Step 3: Commit:**
```bash
git add run.ps1 README.md
git commit -m "docs: update launcher script and documentation for FastAPI mission telemetry" -- run.ps1 README.md
```

---

### Task 12: End-to-End Verification & Self-Review

- [ ] **Step 1: Run full test suite:**
```powershell
.venv\Scripts\python.exe -m pytest
```
Expected: 100% tests pass (with skips for external extractor).

- [ ] **Step 2: Check git status for uncommitted files:**
```powershell
git status --short
```
Ensure no stray or untracked temporary files exist.

---

## Plan Self-Review & Critic Findings Verification Table

| Critic ID | Finding Summary | Addressed In Plan | Verification Detail |
|---|---|---|---|
| **F-01** | String vs `PriceEntry` bug in benchmark lookup | Task 7 (`views.py`) | Set `catalog_model_ids = {e.model_id for e in ctx.catalog.entries}`, check `m in catalog_model_ids or ctx.catalog.price_on(m)[0] is not None`. Tested in `test_ui_views.py`. |
| **F-02** | HTMX DOM nesting & filter loss | Task 8, 9 (`command_bar.html`, `app.js`) | Replaced `innerHTML` with `hx-swap="outerHTML"` on `#workspace-canvas`, added `hx-include="#global-filter-form"`, and hooked tab active styling in `app.js`. |
| **F-03** | Missing Economics forecast & lab controls | Task 7, 9, 10 (`view_economics.html`, `forecast_stage.html`, `lab_stage.html`, `app.py`) | Created complete forms for Stage 1 & Stage 2, added historical cadence chart, daily projected schedule table, and partial routes `/partials/forecast-stage` & `/partials/lab-stage`. |
| **F-04** | Missing Sessions 3-zone controls & charts | Task 7, 9, 10 (`view_sessions.html`, `app.py`) | Added Zone 1 kind pills & search box, Subagent Swarm KPIs, Context Pressure KPIs, and all 5 charts (`thinking_ratio`, `tool_mix`, `model_switches`, `mcp_invocations`, `failure_daily`). |
| **F-05** | Sync drawer missing health, consistency & run ledger | Task 7, 9 (`sync_drawer.html`, `job_status.html`, `views.py`) | Added `metrics.verify_consistency()`, online badges, SQLite run table, collapsible stdout/stderr, and restricted polling to active job state. |
| **F-06** | Session Inspector placeholder | Task 7, 9, 10 (`session_detail.html`, `app.py`) | Added `build_session_detail` with tool breakdown, commands, failures, and artifacts; rendered via dedicated `session_detail.html` template. |
| **F-07** | Command bar missing tokens, cost & refresh | Task 5, 9, 10 (`command_bar.html`, `app.py`) | Added token & cost badges, currency selector dropdown, FX & sub inputs, `POST /api/refresh`, and live job status dot. |
| **F-08** | Omitted workspace chart & honesty warnings | Task 7, 9 (`view_command.html`) | Embedded `chart-workspace` in attribution panel, added `ctx.price_note` warning banner and waste proxy order-of-magnitude engineering disclaimer. |
| **F-09** | ECharts confidence band area fill issue | Task 6 (`charts.py`) | Replaced unstacked fill with stacked confidence band (P10 transparent baseline + P90-P10 delta area ribbon). Tested in `test_ui_charts.py`. |
| **F-10** | ECharts crash on empty frames & missing dataZoom | Task 6 (`charts.py`) | Added `_empty_cartesian()` returning valid empty `xAxis`/`yAxis` structures for all Cartesian charts. Added `dataZoom` slider to `daily_burn`. |
| **F-11** | Memory leak from resize listener | Task 8 (`app.js`) | Replaced per-chart resize listeners with single debounced global window resize listener and explicit `chart.dispose()` on swap. |
| **F-12** | Network assumptions in Tasks 1 & 2 | Task 1, 2 | Flagged network prerequisites with timeout limits and air-gapped notes. |
| **F-13** | Unstaged files in working tree | Task 0 | Added `git restore --staged .` before branch creation. |
| **F-14** | Dead code block in Task 5 | Task 5 (`state.py`) | Completely removed dead code snippet and associated review note. |
