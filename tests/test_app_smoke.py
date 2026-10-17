"""End-to-end smoke tests.

These do not touch the real ~/.gemini logs. They build a tiny synthetic brain
directory in the correct on-disk format, point the config at it, run the REAL
extractor through it, and then render every dashboard page with Streamlit's
AppTest. If the page tree or the extractor integration breaks, these fail.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1", reason="streamlit testing framework required")

from streamlit.testing.v1 import AppTest  # noqa: E402

from agy_dash.jobs import JobRunner  # noqa: E402
from tests.conftest import build_brain  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
REAL_EXTRACTOR = Path.home() / "docs" / "superpowers" / "scripts" / "agy_usage.py"


@pytest.fixture
def synthetic_brain(tmp_path) -> Path:
    """A brain dir with the real on-disk layout: main session, subagent, history labels."""
    return build_brain(tmp_path)


@pytest.fixture
def app_env(tmp_path, synthetic_brain, monkeypatch):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({
        "brain_root": str(synthetic_brain),
        "extractor_script": str(REAL_EXTRACTOR),
        "python_executable": os.sys.executable,
        "db_path": str(tmp_path / "snap.db"),
        "log_dir": str(tmp_path / "logs"),
        "subscription": {"amount": 1999.0, "currency": "INR", "period_days": 30,
                         "label": "test plan"},
        "fx": {"USD_INR": 88.0},
        "reporting_currency": "INR",
    }), encoding="utf-8")
    monkeypatch.setenv("AGY_DASH_CONFIG", str(cfg_path))
    import agy_dash.config as cfgmod
    cfgmod.get_config(reload=True)
    yield cfg_path
    cfgmod.get_config(reload=True)


pytestmark = pytest.mark.skipif(
    not REAL_EXTRACTOR.exists(),
    reason=f"real extractor not present at {REAL_EXTRACTOR}",
)


def test_real_extractor_reads_the_synthetic_brain(synthetic_brain):
    """The extraction script itself still works against a correctly-shaped brain dir."""
    from agy_dash import source

    data = source.scan_usage(synthetic_brain, REAL_EXTRACTOR)
    assert len(data.sessions) == 3
    assert sorted(data.sessions["kind"]) == ["main", "other", "subagent"]
    assert int(data.sessions["total"].sum()) == int(data.daily["total"].sum())
    assert data.daily["total"].sum() > 0


def test_extractor_cli_still_runs_end_to_end(tmp_path, synthetic_brain):
    """The dashboard's job runner executes the real CLI and captures its report."""
    runner = JobRunner(REAL_EXTRACTOR, os.sys.executable, table=dict(os.environ),
                       log_dir=tmp_path / "joblogs", timeout_seconds=120)
    runner.start("all", extra_args=["--root", str(synthetic_brain), "--top", "5"])
    import time
    deadline = time.time() + 60
    while runner.state.running and time.time() < deadline:
        time.sleep(0.1)
        runner.poll()
    assert runner.state.status == "success", runner.state.read_stderr()
    out = runner.state.read_stdout()
    assert "tokens per day" in out and "tokens per session" in out


def test_dashboard_renders_every_page(app_env):
    from agy_dash.ui.data_jobs import STATUS_BADGE  # noqa: F401  (import ordering sanity)

    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    assert not at.exception, at.exception

    for page in ("Overview", "Usage Explorer", "Model Cost Lab", "Forecast", "Deep Signals",
                 "Data & Jobs"):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, f"{page}: {at.exception}"


def test_light_theme_renders(app_env):
    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    at.sidebar.radio[1].set_value("light").run()
    assert not at.exception, at.exception


def test_sidebar_model_choice_changes_the_numbers(app_env):
    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    at.sidebar.selectbox[0].set_value("claude-opus").run()
    assert not at.exception, at.exception
    at.sidebar.selectbox[0].set_value("gemini-3.8-flash").run()
    assert not at.exception, at.exception


def test_forecast_page_with_every_method(app_env):
    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    at.sidebar.radio[0].set_value("Forecast").run()
    for method in ("Linear extrapolation (baseline)", "Bootstrap resampling",
                   "Monte Carlo simulation", "Holt linear trend"):
        at.selectbox[1].set_value(method).run()  # 0 = target, 1 = method
        assert not at.exception, f"{method}: {at.exception}"


def test_snapshot_button_ingests_real_extracted_data(app_env, tmp_path):
    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    at.sidebar.radio[0].set_value("Data & Jobs").run()

    save = [b for b in at.button if "Save snapshot" in b.label][0]
    save.click().run()
    assert not at.exception, at.exception

    from agy_dash import snapshots
    conn = snapshots.connect(tmp_path / "snap.db")
    counts = snapshots.counts(conn)
    conn.close()
    assert counts["session_facts"] == 3  # one row per scanned session
    assert counts["daily_facts"] == 3
    assert counts["runs"] == 1


def test_snapshot_ingestion_is_idempotent_from_the_ui(app_env, tmp_path):
    from agy_dash import snapshots

    at = AppTest.from_file(str(PROJECT_DIR / "app.py"), default_timeout=90)
    at.run()
    at.sidebar.radio[0].set_value("Data & Jobs").run()
    for _ in range(2):
        [b for b in at.button if "Save snapshot" in b.label][0].click().run()
        assert not at.exception, at.exception

    conn = snapshots.connect(tmp_path / "snap.db")
    counts = snapshots.counts(conn)
    conn.close()
    assert counts["session_facts"] == 3 and counts["daily_facts"] == 3  # no duplicates
    assert counts["runs"] == 2  # the run log records both scans
