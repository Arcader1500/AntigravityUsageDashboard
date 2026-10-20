import io
import pytest
from agy_dash.source import SourceError
from agy_dash.ui import state


def test_index_renders_html_shell(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "ANTIGRAVITY" in res.text
    assert "01 // COMMAND" in res.text


def test_command_bar_unified_structure(client):
    res = client.get("/")
    assert res.status_code == 200
    assert 'class="command-bar-unified"' in res.text
    assert 'id="filter-deck-toggle"' in res.text
    assert '<svg class="icon"><use href="#icon-filter"' in res.text
    assert 'onchange="this.form.requestSubmit()"' not in res.text


def test_switch_workspace_views(client):
    for view in ("command", "sessions", "economics"):
        res = client.get(f"/?view={view}")
        assert res.status_code == 200

    # Ensure duplicate view query parameter from hx-include honors the explicit tab target
    res_sessions = client.get("/?view=sessions&view=command")
    assert res_sessions.status_code == 200
    assert "Session Workload Leaderboard" in res_sessions.text

    res_econ = client.get("/?view=economics&view=command")
    assert res_econ.status_code == 200
    assert "STAGE 1 // FORECAST CONTROLS" in res_econ.text


def test_session_detail_endpoint(client, usage):
    sid = usage.sessions["session_id"].iloc[0]
    res = client.get(f"/partials/session-detail/{sid}")
    assert res.status_code == 200
    assert sid[:8] in res.text


def test_session_detail_currency_usd(client, usage):
    sid = usage.sessions["session_id"].iloc[0]
    res = client.get(f"/partials/session-detail/{sid}?currency=USD")
    assert res.status_code == 200
    assert "$" in res.text


def test_theme_cookie_sets_data_theme(client):
    res_light = client.get("/", headers={"cookie": "agy_theme=light"})
    assert res_light.status_code == 200
    assert 'data-theme="light"' in res_light.text

    res_dark = client.get("/", headers={"cookie": "agy_theme=dark"})
    assert res_dark.status_code == 200
    assert 'data-theme="dark"' in res_dark.text


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


def test_economics_view_segmented_switcher(client):
    res = client.get("/?view=economics")
    assert res.status_code == 200
    assert 'class="economics-switcher subtab-bar"' in res.text
    assert 'data-econ-stage="forecast"' in res.text
    assert 'data-econ-stage="simulator"' in res.text


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
