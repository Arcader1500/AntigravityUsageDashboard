import pandas as pd
import pytest

from agy_dash import metrics, pricing, source, stats
from agy_dash.ui import charts, common


def _sample_ctx():
    prices = pricing.PriceEntry("m", "Test Model", "Google", "2026-01-01", None, 1.0, 0.2, 3.0)
    catalog = pricing.Catalog([prices])
    dates = pd.date_range("2026-10-01", periods=3)
    daily = pd.DataFrame({
        "date": dates,
        "calls": [10, 15, 20],
        "fresh_in": [1000, 2000, 3000],
        "cached": [5000, 8000, 10000],
        "output": [500, 700, 900],
        "total": [6500, 10700, 13900],
    })
    sessions = pd.DataFrame({
        "session_id": ["s1", "s2"],
        "label": ["Session 1", "Session 2"],
        "kind": ["main", "subagent"],
        "total": [10000, 21100],
        "fresh_in": [2000, 4000],
        "cached": [7000, 16000],
        "output": [1000, 1100],
    })
    overview = metrics.update_overview(
        sessions, daily, prices,
        currency="INR", usd_inr=88.0, subscription_amount=1000.0,
        model_name="Test Model", price_note="Test note",
    )
    return common.Ctx(
        config=None,
        usage=None,
        sessions=sessions,
        daily=daily,
        catalog=catalog,
        prices=prices,
        model_id="m",
        price_note="Test note",
        currency="INR",
        usd_inr=88.0,
        subscription_amount=1000.0,
        theme="dark",
        runner=None,
        overview=overview,
    )


def test_empty_chart_returns_valid_axes():
    c = common.colors("dark")
    ctx = common.Ctx(None, None, pd.DataFrame(), pd.DataFrame(), None, None, "m", None, "INR", 88.0, 0.0, "dark", None, None)

    # Test that empty data returns xAxis/yAxis instead of empty dictionary to avoid JS crash
    res = charts.daily_burn(ctx)
    assert "xAxis" in res and "yAxis" in res
    assert res["series"] == []


def test_forecast_fan_stacked_ribbon():
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


def test_daily_burn_populated():
    ctx = _sample_ctx()
    res = charts.daily_burn(ctx)
    assert "xAxis" in res
    assert len(res["xAxis"]["data"]) == 3
    assert len(res["series"]) == 4
    assert res["series"][0]["name"] == "Fresh Input"
    assert res["series"][1]["name"] == "Cached Input"
    assert res["series"][2]["name"] == "Output & Reasoning"
    assert res["series"][3]["name"] == "API Cost (INR)"


def test_token_mix_and_cost_burden():
    ctx = _sample_ctx()
    tm = charts.token_mix(ctx)
    assert len(tm["series"]) == 1
    assert tm["series"][0]["type"] == "pie"
    assert len(tm["series"][0]["data"]) == 3

    cb = charts.cost_burden(ctx)
    assert len(cb["series"]) == 1
    assert cb["series"][0]["type"] == "pie"
    assert len(cb["series"][0]["data"]) == 3
    # Check values are converted to INR (> 0)
    assert any(d["value"] > 0 for d in cb["series"][0]["data"])


def test_workspace_attribution():
    ctx = _sample_ctx()
    empty = charts.workspace_attribution(pd.DataFrame(), ctx)
    assert empty["series"] == []

    df = pd.DataFrame({"project": ["proj1", "proj2"], "total": [1000, 2000]})
    res = charts.workspace_attribution(df, ctx)
    assert len(res["series"]) == 1
    assert res["yAxis"]["data"] == ["proj1", "proj2"]  # iloc[::-1] from nlargest


def test_cache_thrash():
    ctx = _sample_ctx()
    empty = charts.cache_thrash(pd.DataFrame(), ctx)
    assert empty["series"] == []

    step_df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"],
        "cache_miss_calls": [5, 12],
        "model_calls": [10, 20],
    })
    res = charts.cache_thrash(step_df, ctx)
    assert len(res["series"]) == 2
    assert res["series"][0]["data"] == [5, 12]
    assert res["series"][1]["data"] == [10, 20]


def test_top_sessions_and_session_kinds():
    ctx = _sample_ctx()
    empty_top = charts.top_sessions(pd.DataFrame(), 5, ctx)
    assert empty_top["series"] == []

    top = charts.top_sessions(ctx.sessions, 5, ctx)
    assert len(top["series"]) == 1
    assert len(top["series"][0]["data"]) == 2

    empty_kinds = charts.session_kinds(pd.DataFrame(), ctx)
    assert empty_kinds["series"][0]["data"] == []

    kinds = charts.session_kinds(ctx.sessions, ctx)
    assert len(kinds["series"][0]["data"]) == 2


def test_calls_vs_sessions_and_time_budget():
    ctx = _sample_ctx()
    daily_df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"],
        "calls": [10, 20],
        "sessions": [2, 4],
    })
    cvs = charts.calls_vs_sessions(daily_df, ctx)
    assert len(cvs["series"]) == 2

    gaps_df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"],
        "busy_hours": [1.5, 3.2],
        "idle_hours": [0.5, 1.1],
    })
    tb = charts.time_budget(gaps_df, ctx)
    assert len(tb["series"]) == 2


def test_thinking_ratio_and_tool_mix():
    ctx = _sample_ctx()
    step_df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"],
        "thinking_steps": [5, 10],
        "steps": [10, 20],
    })
    tr = charts.thinking_ratio(step_df, ctx)
    assert len(tr["series"]) == 1
    assert tr["series"][0]["data"] == [50.0, 50.0]

    empty_tools = charts.tool_mix({}, ctx)
    assert empty_tools["series"] == []

    counters = {"tool:bash": 20, "tool:edit_file": 35, "other": 99}
    tm = charts.tool_mix(counters, ctx)
    assert len(tm["series"]) == 1
    assert tm["yAxis"]["data"] == ["bash", "edit_file"]


def test_failure_daily_and_model_switches_and_mcp():
    ctx = _sample_ctx()
    fail_df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-01", "2026-10-02"],
        "text": ["err1", "err2", "err3"],
    })
    fd = charts.failure_daily(fail_df, ctx)
    assert len(fd["series"]) == 1
    assert fd["series"][0]["data"] == [2, 1]

    sw_df = pd.DataFrame({"to_model": ["claude-3-5", "claude-3-5", "gpt-4o"]})
    ms = charts.model_switches(sw_df, ctx)
    assert len(ms["series"][0]["data"]) == 2

    counters = {"mcp:github": 10, "mcp:slack": 5}
    mcp = charts.mcp_invocations(counters, ctx)
    assert len(mcp["series"]) == 1


def test_historical_cadence_benchmark_subscription():
    ctx = _sample_ctx()
    agg_df = pd.DataFrame({"date": ["2026-10-01"], "cost": [12.5]})
    hc = charts.historical_cadence(agg_df, "cost", "daily", None, ctx)
    assert len(hc["series"]) == 1
    assert hc["series"][0]["data"] == [12.5]

    cmp_df = pd.DataFrame({
        "model": ["Model A", "Model B"],
        "cost_usd": [1.0, 2.0],
        "estimate": [False, True],
    })
    mb = charts.model_benchmark(cmp_df, ctx)
    assert len(mb["series"]) == 1
    assert len(mb["series"][0]["data"]) == 2

    sc = charts.subscription_comparison(ctx)
    assert len(sc["series"]) == 1
    assert len(sc["series"][0]["data"]) == 2
