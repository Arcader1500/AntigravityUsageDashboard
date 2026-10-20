import datetime as dt
from pathlib import Path
import pandas as pd
import pytest

from agy_dash import config as cfgmod, deep, jobs, pricing, snapshots, source
from agy_dash.ui import charts, common, views
from tests.conftest import MAIN_ID, SUB_ID, WORKSPACE


@pytest.fixture
def data(rich_brain) -> deep.DeepData:
    return deep.scan_deep(rich_brain)


def _make_ctx(usage, model_id="claude-sonnet", currency="INR", fx=88.0, sub=2000.0, theme="dark", config=None, runner=None):
    try:
        catalog = pricing.default_catalog()
        prices, _ = catalog.price_on(model_id)
    except AttributeError:
        catalog = pricing.Catalog()
        prices, _ = catalog.price_on(model_id)
    return common.build_ctx(
        config, usage, usage.sessions, usage.daily, catalog, prices,
        model_id, None, currency, fx, sub, theme, runner,
    )


def test_build_economics_view_populates_models(usage):
    try:
        catalog = pricing.default_catalog()
        prices, _ = catalog.price_on("claude-sonnet")
    except AttributeError:
        catalog = pricing.Catalog()
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


def test_build_command_view_with_none_and_deep_data(usage, data):
    ctx = _make_ctx(usage)

    # Without deep_data
    res_none = views.build_command_view(ctx, None)
    assert len(res_none["token_kpis"]) == 4
    assert len(res_none["econ_kpis"]) == 4
    assert res_none["waste"] is None
    assert "daily_burn_chart" in res_none["charts"]
    assert "token_mix_chart" in res_none["charts"]
    assert "cost_burden_chart" in res_none["charts"]
    assert "workspace_chart" in res_none["charts"]
    assert "cache_thrash_chart" in res_none["charts"]
    assert len(res_none["best_days"]) > 0

    # With deep_data
    # Map a session to DemoProject so workspace totals populates
    usage_with_meta = source.UsageData(
        usage.sessions.assign(session_id=[MAIN_ID, "26082efd", "sub00001", "aaaabbbb"]),
        usage.daily, usage.scanned_at, usage.root, [],
    )
    ctx_meta = _make_ctx(usage_with_meta)
    res_deep = views.build_command_view(ctx_meta, data)
    assert res_deep["waste"] is not None
    assert "cost" in res_deep["waste"]
    assert len(res_deep["ws_rows"]) > 0
    assert any(r["project"] == "DemoProject" for r in res_deep["ws_rows"])


def test_build_sessions_view_and_filtering(usage, data):
    ctx = _make_ctx(usage)

    # Unfiltered
    res = views.build_sessions_view(ctx, data)
    assert res["sessions_count"] == len(usage.sessions)
    assert len(res["session_rows"]) == len(usage.sessions)
    assert len(res["session_kpis"]) == 4
    assert len(res["swarm_kpis"]) == 4
    assert len(res["context_kpis"]) == 3
    assert len(res["turn_rows"]) > 0
    assert len(res["cmd_rows"]) > 0
    assert len(res["fail_rows"]) > 0
    assert len(res["denial_rows"]) > 0
    assert len(res["artifact_rows"]) > 0
    assert len(res["message_rows"]) > 0

    # Kind filter
    res_sub = views.build_sessions_view(ctx, data, kind_sel=["subagent"])
    assert res_sub["sessions_count"] == 1
    assert res_sub["session_rows"][0]["kind"] == "subagent"

    # Search filter
    res_search = views.build_sessions_view(ctx, data, search="verify")
    assert res_search["sessions_count"] == 1
    assert "verify" in res_search["session_rows"][0]["label"]

    # Empty sessions
    empty_ctx = common.build_ctx(
        None, usage, pd.DataFrame(columns=usage.sessions.columns), usage.daily,
        ctx.catalog, ctx.prices, "claude-sonnet", None, "INR", 88.0, 2000.0, "dark", None,
    )
    res_empty = views.build_sessions_view(empty_ctx, None)
    assert res_empty["sessions_count"] == 0
    assert res_empty["session_rows"] == []


def test_build_session_detail(usage, data):
    usage_with_meta = source.UsageData(
        usage.sessions.assign(session_id=[MAIN_ID, "26082efd", "sub00001", "aaaabbbb"]),
        usage.daily, usage.scanned_at, usage.root, [],
    )
    ctx = _make_ctx(usage_with_meta)

    # Match found
    detail = views.build_session_detail(ctx, data, MAIN_ID)
    assert detail is not None
    assert detail["session_id"] == MAIN_ID
    assert detail["meta"]["project"] == "DemoProject"
    assert len(detail["commands"]) > 0
    assert len(detail["failures"]) > 0
    assert len(detail["artifacts"]) > 0

    # Without deep_data
    detail_simple = views.build_session_detail(ctx, None, MAIN_ID)
    assert detail_simple is not None
    assert detail_simple["commands"] == []
    assert detail_simple["failures"] == []

    # Non-existent session
    assert views.build_session_detail(ctx, data, "non-existent-id") is None


def test_build_economics_view_targets_and_methods(usage):
    ctx = _make_ctx(usage)

    # Target: API-equivalent cost (payback_pct computed)
    fc_params_cost = {"target": "API-equivalent cost", "method": "Linear extrapolation (baseline)", "horizon": 14, "daily_growth": 0.05}
    res_cost = views.build_economics_view(ctx, fc_params_cost, {})
    assert len(res_cost["schedule_rows"]) == 14
    assert res_cost["fc_params"]["target"] == "API-equivalent cost"
    assert res_cost["payback_pct"] is not None
    assert res_cost["payback_pct"].endswith("%")

    # Method: Monte Carlo simulation with What-If lab params (target: Total tokens, payback_pct is None)
    fc_params_mc = {"target": "Total tokens", "method": "Monte Carlo simulation", "horizon": 7, "mc_growth": 0.02, "mc_sd": 0.2}
    lab_params = {"use_ratio": True, "ratio": 80, "output_mult": 1.2, "prompt_mult": 1.5, "chosen_models": ["claude-sonnet", "gemini-3.8-flash"]}
    res_mc = views.build_economics_view(ctx, fc_params_mc, lab_params)
    assert len(res_mc["schedule_rows"]) == 7
    assert len(res_mc["cmp_rows"]) == 2
    assert res_mc["lab_params"]["ratio"] == 80.0
    assert res_mc["payback_pct"] is None


def test_workspace_attribution_chart(usage):
    ctx = _make_ctx(usage)
    df_tokens = pd.DataFrame([{"project": "ProjA", "tokens": 1000}, {"project": "ProjB", "tokens": 2000}])
    chart = charts.workspace_attribution(df_tokens, ctx)
    assert "series" in chart
    assert chart["series"][0]["data"] == [1000, 2000]


def test_build_sync_drawer(usage, tmp_path):
    db_path = tmp_path / "test_snapshots.db"
    conn = snapshots.connect(db_path)
    snapshots.ingest(conn, usage)
    conn.close()

    cfg = cfgmod.Config(data={
        "db_path": str(db_path),
        "brain_root": str(tmp_path / "brain"),
        "extractor_script": str(tmp_path / "extractor.py"),
        "python_executable": "python",
    })
    runner = jobs.JobRunner(
        script_path=tmp_path / "extractor.py",
        python_executable="python",
        log_dir=tmp_path / "logs",
        last_run_path=tmp_path / "logs" / "last_run.json",
    )
    ctx = _make_ctx(usage, config=cfg, runner=runner)

    sync_res = views.build_sync_drawer(ctx)
    assert sync_res["sessions_scanned"] == len(usage.sessions)
    assert sync_res["db_counts"]["session_facts"] == len(usage.sessions)
    assert sync_res["db_counts"]["daily_facts"] == len(usage.daily)
    assert len(sync_res["runs"]) >= 1
    assert sync_res["consistency_issues"] == []
    assert sync_res["runner_state"] is not None

    # Test with None config and None runner
    ctx_bare = _make_ctx(usage)
    sync_bare = views.build_sync_drawer(ctx_bare)
    assert sync_bare["db_counts"]["session_facts"] == 0
    assert sync_bare["runner_state"] is None


def test_view_models_use_svg_icon_identifiers(usage, data):
    ctx = _make_ctx(usage)
    cmd_vm = views.build_command_view(ctx, data)
    for kpi in cmd_vm["token_kpis"] + cmd_vm["econ_kpis"]:
        assert kpi["icon"].startswith("icon-"), f"KPI icon is not an SVG symbol ID: {kpi['icon']}"

    sess_vm = views.build_sessions_view(ctx, data)
    for kpi in sess_vm["session_kpis"] + sess_vm["swarm_kpis"] + sess_vm["context_kpis"]:
        assert kpi["icon"].startswith("icon-"), f"Session KPI icon is not an SVG symbol ID: {kpi['icon']}"
