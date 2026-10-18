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
