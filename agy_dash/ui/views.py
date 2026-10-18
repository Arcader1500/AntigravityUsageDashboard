"""View-model builders: transform Ctx and DeepData into plain template dicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

from .. import deep, jobs, metrics, pricing, snapshots, stats
from . import charts, common


def _cache_savings_usd(fresh_in: float, cached: float, prices: Any) -> float:
    return float(cached or 0) * max(getattr(prices, "input_usd", 0.0) - getattr(prices, "cached_usd", 0.0), 0.0) / 1e6


if not hasattr(metrics, "cache_savings_usd"):
    metrics.cache_savings_usd = _cache_savings_usd


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
        {"lbl": "EQUIVALENT API COST", "val": common.fmt_money(ctx.to_currency(o.api_cost_usd), curr), "sub": f"{o.model_name} catalog", "icon": "💵", "badge": "METERED"},
        {"lbl": "SUBSCRIPTION SPEND", "val": common.fmt_money(sub_spend, curr), "sub": "fixed periodic spend", "icon": "💳", "badge": "FIXED"},
        {"lbl": "BLENDED EFFICIENCY", "val": common.fmt_rate(ctx.to_currency(o.blended_rate_usd_per_mtok), curr), "sub": f"{common.fmt_tokens(o.tokens_per_currency_spent)} tok/{curr}", "icon": "📊", "badge": "RATE"},
        {"lbl": "CACHE SAVINGS", "val": common.fmt_money(ctx.to_currency(metrics.cache_savings_usd(t.fresh_in, t.cached, ctx.prices)), curr), "sub": "saved via reuse", "icon": "🛡️", "badge": "SAVED"},
    ]

    sessions = ctx.usage.sessions if ctx.usage else ctx.sessions
    ws_df = deep.workspace_totals(sessions, deep_data.session_meta if deep_data else pd.DataFrame(), ctx.prices)
    if not ws_df.empty and "total" not in ws_df.columns and "tokens" in ws_df.columns:
        ws_df = ws_df.assign(total=ws_df["tokens"])
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
    sub_share = metrics.safe_div(
        sessions.loc[sessions["kind"] == "subagent", "total"].sum() if not sessions.empty else 0,
        total_tok,
    )

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
            label = str(r.label) if pd.notna(r.label) and r.label else "(unlabeled)"
            session_rows.append({
                "session_id": r.session_id,
                "label": label[:42],
                "kind": r.kind,
                "calls": r.calls,
                "fresh_in": common.fmt_tokens(r.fresh_in),
                "cached": common.fmt_tokens(r.cached),
                "output": common.fmt_tokens(r.output),
                "total": common.fmt_tokens(r.total),
                "cost": ctx.money(r.cost),
                "last_date": r.last_date if pd.notna(r.last_date) and r.last_date else "-",
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
                    "date": r.date, "command": str(r.command)[:65] if r.command else "-",
                    "duration": f"{r.duration_seconds:.1f}s",
                    "exit_code": r.exit_code if pd.notna(r.exit_code) and r.exit_code is not None else "-",
                })

        fail_summary = deep.failure_summary(deep_data.failures, top=8)
        for r in fail_summary.itertuples():
            fail_rows.append({
                "text": str(r.text)[:80] if r.text else "-", "count": r.count, "last_seen": r.last_seen,
            })

        if not deep_data.denials.empty:
            for r in deep_data.denials.head(8).itertuples():
                denial_rows.append({
                    "date": r.date, "command": str(r.command)[:45] if r.command else "-",
                    "wait": f"{r.wait_seconds:.1f}s" if pd.notna(r.wait_seconds) and r.wait_seconds else "-",
                    "text": str(r.text)[:60] if r.text else "-",
                })

        if not deep_data.artifacts.empty:
            for r in deep_data.artifacts.head(8).itertuples():
                artifact_rows.append({
                    "name": r.name, "updated": str(r.updated_at)[:19] if r.updated_at else "-",
                    "gate": "Feedback Req" if r.request_feedback else "Direct",
                    "summary": str(r.summary)[:60] if r.summary else "-",
                })

        if not deep_data.messages.empty:
            for r in deep_data.messages.head(6).itertuples():
                message_rows.append({
                    "sender": r.sender, "title": str(r.title)[:45] if r.title else "-",
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
    sessions = ctx.usage.sessions if ctx.usage else ctx.sessions
    match = sessions[sessions["session_id"] == session_id]
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
            dur_col = "duration_seconds" if "duration_seconds" in st.columns else ("seconds" if "seconds" in st.columns else None)
            if dur_col and not st.empty:
                st_grp = st.groupby("tool").agg(calls=(dur_col, "count"), avg_sec=(dur_col, "mean"))
                for t_name, t_row in st_grp.iterrows():
                    tools.append({"tool": t_name, "calls": int(t_row["calls"]), "avg_sec": f"{t_row['avg_sec']:.2f}s"})
        if not deep_data.artifacts.empty and "session_id" in deep_data.artifacts.columns:
            sa = deep_data.artifacts[deep_data.artifacts["session_id"] == session_id]
            for a in sa.head(10).itertuples():
                artifacts.append({"name": a.name, "summary": a.summary, "gate": "Feedback Req" if a.request_feedback else "Direct"})

    return {
        "session_id": session_id,
        "label": r.get("label", "(unlabeled)") or "(unlabeled)",
        "kind": r.get("kind", "other") or "other",
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
    raw_ratio = lab_params.get("ratio")
    if raw_ratio is not None:
        ratio = float(raw_ratio)
        if ratio > 1.0:
            ratio = ratio / 100.0
    else:
        ratio = metrics.cache_hit_rate(base["fresh_in"], base["cached"])

    output_mult = float(lab_params.get("output_mult", 1.0))
    prompt_mult = float(lab_params.get("prompt_mult", 1.0))

    cat = ctx.catalog if hasattr(ctx.catalog, "entries") else pricing.Catalog(ctx.catalog)
    catalog_model_ids = {e.model_id for e in cat.entries}
    chosen_models = lab_params.get("chosen_models") or [
        m for m in ("gemini-3.8-flash", "gemini-4-argon", "claude-sonnet", "claude-opus", "gpt-flagship", "deepseek-v3-api")
        if m in catalog_model_ids or (hasattr(cat, "price_on") and cat.price_on(m)[0] is not None)
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
    cmp = metrics.compare_models(tokens, cat, chosen_models, on=on_date)

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
    db_path = ctx.config.db_path if ctx.config else None
    if db_path:
        conn = snapshots.connect(db_path)
        counts = snapshots.counts(conn)
        try:
            runs_raw = snapshots.runs(conn, limit=10)
        except TypeError:
            runs_raw = snapshots.runs(conn)
        conn.close()
    else:
        counts = {"session_facts": 0, "daily_facts": 0, "runs": 0}
        runs_raw = []

    runs = []
    if isinstance(runs_raw, pd.DataFrame):
        for r in runs_raw.head(10).itertuples():
            runs.append({
                "run_id": getattr(r, "run_id", 0),
                "started_at": str(getattr(r, "taken_at", getattr(r, "started_at", "-")))[:19],
                "duration_seconds": getattr(r, "duration_seconds", "-"),
                "report": getattr(r, "report", "all"),
                "status": getattr(r, "status", "success"),
            })
    elif isinstance(runs_raw, list):
        runs = runs_raw

    sessions = ctx.usage.sessions if ctx.usage else ctx.sessions
    daily = ctx.usage.daily if ctx.usage else ctx.daily
    consistency_issues = metrics.verify_consistency(sessions, daily)
    runner = ctx.runner
    state = runner.state if runner else None
    persisted = jobs.last_run(runner.last_run_path) if runner and hasattr(runner, "last_run_path") else None

    brain_root = ctx.usage.root if ctx.usage else (ctx.config.brain_root if ctx.config else "")
    extractor_script = ctx.config.extractor_script if ctx.config else ""
    python_executable = ctx.config.python_executable if ctx.config else ""
    warnings = ctx.usage.warnings if ctx.usage else []

    return {
        "source_online": Path(brain_root).exists() if brain_root else False,
        "brain_root": brain_root,
        "extractor_script": extractor_script,
        "python_executable": python_executable,
        "sessions_scanned": len(sessions) if sessions is not None else 0,
        "warnings": warnings,
        "consistency_issues": consistency_issues,
        "db_counts": counts,
        "runs": runs,
        "runner_state": state,
        "persisted_run": persisted,
        "stdout": state.read_stdout(limit=20000) if state else "",
        "stderr": state.read_stderr(limit=10000) if state else "",
    }
