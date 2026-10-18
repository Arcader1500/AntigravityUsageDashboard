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
    if daily is None or daily.empty:
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
    t = ctx.overview.totals if ctx.overview else None
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
            {"value": t.fresh_in if t else 0, "name": "Fresh Input", "itemStyle": {"color": c["fresh"]}},
            {"value": t.cached if t else 0, "name": "Cached Input", "itemStyle": {"color": c["cached"]}},
            {"value": t.output if t else 0, "name": "Output & Reasoning", "itemStyle": {"color": c["output"]}},
        ],
    }]
    return opt


def cost_burden(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    b = ctx.overview.breakdown_usd if ctx.overview else {}
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
            {"value": round(ctx.to_currency(b.get("fresh_usd", b.get("fresh_in", 0.0))), 2), "name": "Fresh Input", "itemStyle": {"color": c["fresh"]}},
            {"value": round(ctx.to_currency(b.get("cached_usd", b.get("cached", 0.0))), 2), "name": "Cached Input", "itemStyle": {"color": c["cached"]}},
            {"value": round(ctx.to_currency(b.get("output_usd", b.get("output", 0.0))), 2), "name": "Output", "itemStyle": {"color": c["output"]}},
        ],
    }]
    return opt


def workspace_attribution(ws_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Workspace Token Attribution")
    if ws_df is None or ws_df.empty:
        return _empty_cartesian(opt)
    col = "total" if "total" in ws_df.columns else ("tokens" if "tokens" in ws_df.columns else None)
    if not col:
        return _empty_cartesian(opt)
    df = ws_df.nlargest(8, col).iloc[::-1]
    opt["grid"] = {"top": 35, "right": 30, "bottom": 25, "left": 130}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": [str(p)[:22] for p in df["project"].fillna("(unknown)")], "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"name": "Tokens", "type": "bar", "color": c["accent"], "data": df[col].tolist()}]
    return opt


def cache_thrash(step_days_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Context Eviction (Zero-Cache Days)")
    if step_days_df is None or step_days_df.empty:
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
    if sessions_df is None or sessions_df.empty:
        return _empty_cartesian(opt)
    s = sessions_df.nlargest(top_n, "total").iloc[::-1]
    kind_color = {"main": c["accent"], "subagent": c["cached"], "other": c["muted"]}
    labels = [str(lbl)[:26] for lbl in s["label"].fillna("(unlabeled)")]
    data = []
    for row in s.itertuples():
        kind = getattr(row, "kind", "other")
        data.append({
            "value": int(row.total),
            "itemStyle": {"color": kind_color.get(kind, c["muted"]), "borderRadius": [0, 4, 4, 0]},
            "sessionId": getattr(row, "session_id", ""),
            "kind": kind,
        })
    opt["grid"] = {"top": 35, "right": 40, "bottom": 25, "left": 160}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": labels, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": data}]
    return opt


def session_kinds(sessions_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Session Class Split")
    if sessions_df is None or sessions_df.empty:
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
    if daily_df is None or daily_df.empty:
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
    if gaps_daily_df is None or gaps_daily_df.empty:
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
    if step_days_df is None or step_days_df.empty:
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
    if failures_df is None or failures_df.empty or "date" not in failures_df.columns:
        return _empty_cartesian(opt)
    by_day = failures_df.groupby("date").size()
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in by_day.index]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = {"type": "value", "name": "Errors", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["series"] = [{"name": "Failures", "type": "bar", "color": c["bad"], "data": by_day.values.tolist()}]
    return opt


def model_switches(switches_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, "Engine Switches by Target")
    if switches_df is None or switches_df.empty or "to_model" not in switches_df.columns:
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
    if observed is None or observed.empty:
        return _empty_cartesian(opt)

    obs_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in observed["date"]]
    obs_vals = [round(float(v), 2) for v in observed[column]]
    all_dates = list(obs_dates)
    if fc.supported and fc.horizon_days:
        fc_dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in fc.dates]
        all_dates.extend(fc_dates)

    opt["xAxis"] = {"type": "category", "data": all_dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = [{"type": "value", "name": ctx.currency if unit is None else "Tokens",
                     "splitLine": {"lineStyle": {"color": c["grid"]}}}]

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
    if agg_df is None or agg_df.empty:
        return _empty_cartesian(opt)
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in agg_df["date"]]
    opt["xAxis"] = {"type": "category", "data": dates, "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["yAxis"] = [{"type": "value", "name": ctx.currency if unit is None else "Tokens",
                     "splitLine": {"lineStyle": {"color": c["grid"]}}}]
    opt["series"] = [{"name": column, "type": "bar", "color": c["accent"], "data": agg_df[column].round(2).tolist()}]
    return opt


def model_benchmark(cmp_df: pd.DataFrame, ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Workload Cost Across Engines ({ctx.currency})")
    if cmp_df is None or cmp_df.empty:
        return _empty_cartesian(opt)
    data = []
    for r in cmp_df.itertuples():
        cost_curr = round(ctx.to_currency(r.cost_usd), 2)
        estimate = getattr(r, "estimate", False)
        data.append({
            "value": cost_curr,
            "itemStyle": {"color": c["warn"] if estimate else c["accent"], "borderRadius": [0, 4, 4, 0]},
        })
    opt["grid"] = {"top": 35, "right": 50, "bottom": 25, "left": 140}
    opt["xAxis"] = {"type": "value", "splitLine": {"lineStyle": {"color": c["grid"]}}}
    opt["yAxis"] = {"type": "category", "data": cmp_df["model"].tolist(), "axisLabel": {"color": c["muted"], "fontSize": 10}}
    opt["series"] = [{"type": "bar", "data": data, "label": {"show": True, "position": "right", "color": c["text"]}}]
    return opt


def subscription_comparison(ctx: common.Ctx) -> dict[str, Any]:
    c = common.colors(ctx.theme)
    opt = _base_chart(c, f"Actual Spend vs Metered Equivalent ({ctx.currency})")
    sub_spend = ctx.overview.subscription_spend if ctx.overview else 0.0
    api_val = ctx.to_currency(ctx.overview.api_cost_usd) if ctx.overview else 0.0
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
