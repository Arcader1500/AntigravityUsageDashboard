import io
import pytest
from fastapi.testclient import TestClient
import app as app_module
from agy_dash import config as cfgmod
from agy_dash import pricing
from agy_dash.source import SourceError
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


def test_session_detail_not_found(client):
    res = client.get("/partials/session-detail/nonexistent-id-12345")
    assert res.status_code == 404
    assert "Session not found" in res.text


def test_jobs_endpoints(client):
    res_blocked = client.post("/api/jobs/start")
    assert res_blocked.status_code == 400

    res_start = client.post("/api/jobs/start", data={"report": "all"}, headers={"HX-Request": "true"})
    assert res_start.status_code == 200

    res_status = client.get("/api/jobs/status")
    assert res_status.status_code == 200
    assert "Status:" in res_status.text


def test_refresh_deep_scope(client):
    res = client.post("/api/refresh?scope=deep", headers={"HX-Request": "true"})
    assert res.status_code == 200
    assert "workspace-canvas" in res.text


def test_source_error_handling(client, monkeypatch):
    def _raise(_):
        raise SourceError("Brain root does not exist")

    monkeypatch.setattr(state, "load_usage", _raise)
    res = client.get("/")
    assert res.status_code == 500
    assert "Brain root does not exist" in res.text
    assert "Telemetry Fault Encountered" in res.text


def test_pricing_error_handling(client, monkeypatch):
    monkeypatch.setattr(state, "load_catalog", lambda: [])
    res = client.get("/")
    assert res.status_code == 400
    assert "Telemetry Fault Encountered" in res.text
