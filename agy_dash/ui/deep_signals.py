"""Deep Signals - the second-order analytics layer.

One expensive read-only scan (`agy_dash.deep`) feeds all of it; the result is
cached, and the page shows how long the scan took so the cost is visible.

Honesty rules enforced here:
  * busy/idle come from gap-capped timestamps: labelled an approximation.
  * command durations are the CLI's own Created->Completed stamps, which for
    async commands include waiting: labelled a window, not a stopwatch.
  * the waste estimate is an order of magnitude, never an accounting figure.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import deep, metrics
from .common import Ctx, colors, fmt_pct, fmt_tokens, kpi_row, note, show


def render(ctx: Ctx) -> None:
    data = _get_deep(ctx)
    if data is None:
        return
    if data.empty:
        note("The deep scan found no session transcripts to analyse.", warn=True)
        return

    h1, h2 = st.columns([3, 1])
    with h1:
        st.caption(f"⚡ Deep scan of **{data.counters.get('sessions_scanned', 0)}** sessions completed in "
                   f"**{data.duration_seconds:.1f}s** at `{data.scanned_at:%H:%M:%S}` · Cached execution.")
    with h2:
        if st.button("🔄 Rescan Deep Signals", key="deep_rescan"):
            _cached_scan.clear()   # only this scan: the token scan cache stays warm
            st.rerun()

    for w in data.warnings:
        note(w, warn=True)

    tabs = st.tabs([
        "💰 Cost & Workspaces",
        "⏱️ Behaviour & Time",
        "🛡️ Friction & Reliability",
        "🤖 Multi-Agent & Collab"
    ])
    with tabs[0]:
        _cost_tab(ctx, data)
    with tabs[1]:
        _time_tab(ctx, data)
    with tabs[2]:
        _friction_tab(ctx, data)
    with tabs[3]:
        _collab_tab(ctx, data)


def _get_deep(ctx: Ctx):
    """Deep scans take seconds, so they are cached and never re-run per widget."""
    try:
        with st.spinner("Running deep scan (tool calls, time budget, failures)..."):
            return _cached_scan(str(ctx.usage.root), ctx.config.extraction_timeout)
    except (FileNotFoundError, OSError, ValueError) as exc:
        note(f"Deep scan unavailable: {exc}", warn=True)
        return None


@st.cache_data(ttl=900, show_spinner=False)
def _cached_scan(root: str, _timeout: int = 0) -> deep.DeepData:
    return deep.scan_deep(root)


# --------------------------------------------------------------------------- A
def _cost_tab(ctx: Ctx, data: deep.DeepData) -> None:
    st.subheader("💵 Granular Unit Economics")
    busy_hours = float(deep.gaps_daily(data.gaps)["busy_hours"].sum()) if not data.gaps.empty else 0.0
    eco = deep.unit_economics(ctx.overview, {"busy_hours": busy_hours})
    waste = deep.waste_estimate(ctx.overview, len(data.failures))

    kpi_row([
        ("Cost per Call", ctx.money(eco["cost_per_call_usd"]),
         f"{fmt_tokens(eco['tokens_per_call'])} tokens/call", "📞", "CALL"),
        ("Cost per Session", ctx.money(eco["cost_per_session_usd"]),
         f"{ctx.overview.totals.sessions:,} sessions", "🧭", "SESSION"),
        ("Cost / Agent Busy-Hr", ctx.money(eco["cost_per_busy_hour_usd"]),
         f"{eco['busy_hours']:,.1f} active hours", "⏱️", "ACTIVE HR"),
        ("Autonomy Ratio", fmt_pct(_autonomy(data), 0),
         "agent-busy vs wall-clock", "🤖", "AUTONOMY"),
        ("Failed Steps", f"{waste['failure_count']:,}",
         f"{fmt_pct(waste['share_of_calls'])} of calls", "⚠️", "RETRIES"),
    ], per_row=5)

    note(f"<b>Waste Proxy:</b> <code>{ctx.money(waste['cost_usd'])}</code> ({fmt_tokens(waste['tokens_at_risk'])} "
         f"tokens at risk) - {waste['method']}. Order-of-magnitude engineering proxy, not an actual invoice.")

    st.subheader("🏢 Workspace Allocation & Attribution")
    ws = deep.workspace_totals(ctx.usage.sessions, data.session_meta, ctx.prices)
    if ws.empty:
        st.info("No workspace attribution available for the selected range.")
    else:
        ws = ws.copy()
        ws["cost"] = [ctx.money(v) for v in ws["cost_usd"]]
        ws["tokens_"] = ws["tokens"].map(fmt_tokens)
        view = ws[["project", "sessions", "calls", "tokens_", "cost", "cost_per_mtok_usd"]].rename(
            columns={"tokens_": "Tokens", "cost_per_mtok_usd": f"Per 1M ({ctx.currency})",
                     "project": "Project / Workspace", "sessions": "Sessions", "calls": "Calls", "cost": f"Cost ({ctx.currency})"})
        st.dataframe(view, hide_index=True, use_container_width=True)

        top = ws.nlargest(12, "tokens").iloc[::-1]
        fig = go.Figure(go.Bar(
            x=top["tokens"], y=top["project"], orientation="h",
            marker_color=colors(ctx.theme)["accent"],
            customdata=top[["cost", "sessions", "calls"]],
            hovertemplate=("<b>%{y}</b><br>Tokens: %{x:,.0f}<br>Cost: %{customdata[0]}<br>"
                           "%{customdata[1]} sessions · %{customdata[2]} calls<extra></extra>"),
        ))
        fig.update_layout(title="Tokens Attributed by Project Workspace",
                          xaxis_title="Tokens", height=max(320, 26 * len(top)))
        show(fig, ctx.theme)
        note("Workspace origin comes from <code>history.jsonl</code>. Subagent sessions inherit their parent's "
             "workspace; sessions without history entries show as unattributed.")

    st.subheader("🎯 Cache Economics & Thrash Warning")
    if data.step_days.empty:
        st.info("No per-day step telemetry.")
        return
    d = data.step_days.copy()
    d["miss_rate"] = d["cache_miss_calls"] / d["model_calls"].replace(0, pd.NA)
    fig = go.Figure()
    fig.add_bar(x=d["date"], y=d["cache_miss_calls"], name="Calls with Empty Cache (Miss)",
                marker_color=colors(ctx.theme)["bad"])
    fig.add_trace(go.Scatter(
        x=d["date"], y=d["model_calls"], name="Total Model Calls", yaxis="y2",
        mode="lines+markers", line=dict(color=colors(ctx.theme)["accent"], width=2.5),
        marker=dict(size=5),
    ))
    fig.update_layout(title="Zero-Cache Read Calls per Day (Context Thrashing & Cache Eviction Warning)",
                      hovermode="x unified", yaxis_title="Zero-Cache Calls",
                      yaxis2=dict(title="Total Calls", overlaying="y", side="right", showgrid=False,
                                  tickfont=dict(color=colors(ctx.theme)["accent"])),
                      legend=dict(orientation="h", y=1.12))
    show(fig, ctx.theme, height=360)

    hit = metrics.cache_hit_rate(ctx.overview.totals.fresh_in, ctx.overview.totals.cached)
    stale = data.counters.get("cache_miss_calls", 0)
    st.caption(f"🎯 Overall cache hit efficiency: **{fmt_pct(hit)}** · Fresh prompt volume is "
               f"**{fmt_pct(metrics.safe_div(ctx.overview.totals.fresh_in, ctx.overview.totals.total))}** "
               f"of all tokens · `{stale:,}` invocations across all history ran with zero cache hit.")


def _autonomy(data: deep.DeepData) -> float:
    wall = float(data.session_meta["wall_seconds"].sum()) if not data.session_meta.empty else 0.0
    busy = float(deep.gaps_daily(data.gaps)["busy_hours"].sum() * 3600) if not data.gaps.empty else 0.0
    return metrics.safe_div(busy, wall)


# --------------------------------------------------------------------------- B
def _time_tab(ctx: Ctx, data: deep.DeepData) -> None:
    st.subheader("⏱️ Time Budget Allocation")
    g = deep.gaps_daily(data.gaps)
    if g.empty:
        st.info("No timing telemetry available.")
    else:
        fig = go.Figure()
        fig.add_bar(x=g["date"], y=g["busy_hours"], name="Agent Working (MODEL to MODEL)",
                    marker_color=colors(ctx.theme)["accent"])
        fig.add_bar(x=g["date"], y=g["idle_hours"], name="Idle / Waiting on User (to USER_INPUT)",
                    marker_color=colors(ctx.theme)["cached"])
        fig.update_layout(barmode="stack", title="Agent Active Busy Hours vs User Idle Waiting Hours",
                          yaxis_title="Hours", hovermode="x unified",
                          legend=dict(orientation="h", y=1.12))
        show(fig, ctx.theme, height=380)
        b, i = g["busy_hours"].sum(), g["idle_hours"].sum()
        st.caption(f"Totals in observation window: **{b:,.1f}h busy** · **{i:,.1f}h idle**. Gaps between steps are "
                   "capped at 4 h, so overnight pauses count as 4 h, not 9 - an engineering approximation, not a hardware clock.")

        if not data.step_days.empty:
            d = data.step_days.copy()
            d["thinking_share"] = d["thinking_steps"] / d["steps"].replace(0, pd.NA)
            fig2 = go.Figure(go.Scatter(
                x=d["date"], y=d["thinking_share"], mode="lines+markers", name="Thinking Step Ratio",
                line=dict(color=colors(ctx.theme)["cost"], width=2.5),
                marker=dict(size=6, color=colors(ctx.theme)["cost"]),
                hovertemplate="<b>%{x|%Y-%m-%d}</b>: %{y:.1%} of steps carried reasoning<extra></extra>"))
            fig2.update_layout(title="Ratio of Model Steps Containing Deep Thinking / Reasoning Text",
                              yaxis=dict(tickformat=".0%"), yaxis_title="Thinking Steps / Total Steps")
            show(fig2, ctx.theme, height=300)

    st.subheader("⚡ Tool Turnaround Latencies")
    turn_stats = deep.turnaround_stats(data.turnarounds)
    if turn_stats.empty:
        st.info("No turnaround telemetry available.")
    else:
        view = turn_stats.copy()
        view["total_minutes"] = view["total_minutes"].round(1)
        st.dataframe(view.rename(columns={"tool": "Tool Name", "count": "Executions", "p50_seconds": "P50 Latency (s)",
                                          "p90_seconds": "P90 Latency (s)", "total_minutes": "Total Duration (min)"}),
                     hide_index=True, use_container_width=True)
        note("<b>Turnaround Definition:</b> The timestamp delta from tool dispatch to the subsequent recorded step. "
             "Includes generation, queueing, and dispatch, not solely tool CPU execution.")

    st.subheader("🛠️ Tool Invocations Mix")
    tool_counts = {k[5:]: v for k, v in data.counters.items() if k.startswith("tool:")}
    if tool_counts:
        s = pd.Series(tool_counts).sort_values(ascending=False)
        fig = go.Figure(go.Bar(
            x=s.values, y=s.index, orientation="h",
            marker_color=colors(ctx.theme)["accent"],
            text=[f"{v:,}" for v in s.values],
            textposition="auto",
            textfont=dict(family="JetBrains Mono"),
            hovertemplate="<b>%{y}</b>: %{x:,} calls<extra></extra>"
        ))
        fig.update_layout(title=f"Tool Execution Volume (n={int(s.sum()):,} Total Dispatches)", xaxis_title="Calls",
                          height=max(320, 24 * len(s)))
        fig.update_yaxes(autorange="reversed")
        show(fig, ctx.theme)

    st.subheader("🐢 Slowest Shell Commands")
    if data.commands.empty:
        st.info("No command result blocks found.")
    else:
        c = data.commands.dropna(subset=["duration_seconds"]).nlargest(15, "duration_seconds")
        if c.empty:
            st.info("No command durations parsed.")
        else:
            view = c[["date", "command", "duration_seconds", "exit_code", "note"]].copy()
            view["duration_seconds"] = view["duration_seconds"].round(1)
            view["command"] = view["command"].str.slice(0, 90)
            st.dataframe(view.rename(columns={"duration_seconds": "Window (s)", "command": "Command Line",
                                              "exit_code": "Exit Code", "date": "Date", "note": "Status"}),
                         hide_index=True, use_container_width=True)
            non_zero = int((data.commands["exit_code"].fillna(0) != 0).sum())
            st.caption(f"Parsed `{len(data.commands):,}` shell command results · `{non_zero:,}` exited with non-zero status.")

    st.subheader("🔄 Async Tasks & Scheduled Work")
    c = data.counters
    kpi_row([
        ("Background Logs", f"{c.get('task_logs', 0):,}", "daemon processes", "📋", "LOGS"),
        ("Schedule Calls", f"{c.get('schedule_calls', 0):,}", "timers & cron triggers", "⏰", "CRON"),
        ("manage_task Calls", f"{c.get('tool:manage_task', 0):,}", "process supervision", "🛠️", "TASK"),
        ("manage_subagents Calls", f"{c.get('tool:manage_subagents', 0):,}", "agent swarm control", "👥", "SWARM"),
    ], per_row=4)


# --------------------------------------------------------------------------- C
def _friction_tab(ctx: Ctx, data: deep.DeepData) -> None:
    st.subheader("🚨 Failure Feed & Friction Events")
    if data.failures.empty:
        st.info("No failure steps recorded.")
    else:
        by_day = data.failures.groupby("date").size()
        fig = go.Figure(go.Bar(
            x=pd.to_datetime(by_day.index), y=by_day.values,
            marker_color=colors(ctx.theme)["bad"], name="Errors",
            hovertemplate="<b>%{x|%Y-%m-%d}</b>: %{y} failure steps<extra></extra>"
        ))
        fig.update_layout(title=f"Failure Steps Recorded per Day (n={len(data.failures):,} Total Errors)", yaxis_title="Steps")
        show(fig, ctx.theme, height=300)

        top = deep.failure_summary(data.failures, top=10)
        if not top.empty:
            st.caption("Top 10 Most Frequent Failure Strings - High Priority Remediation Targets")
            st.dataframe(top.rename(columns={"text": "Error Signature", "count": "Count",
                                             "last_seen": "Last Seen", "sessions": "Impacted Sessions"}),
                         hide_index=True, use_container_width=True)
        note("Includes status ERROR/INVALID and ERROR_MESSAGE steps. Repeated <code>target content not found</code> "
             "entries represent edit retries where the agent attempted to patch file chunks that shifted.")

    st.subheader("🛑 User Approval Denials")
    if data.denials.empty:
        st.info("No approval denials recorded.")
    else:
        d = data.denials.copy()
        d["wait_seconds"] = d["wait_seconds"].round(1)
        st.dataframe(d[["date", "command", "wait_seconds", "text"]].rename(
            columns={"wait_seconds": "Prompt Window (s)", "text": "Denial Reason", "command": "Blocked Command"}),
            hide_index=True, use_container_width=True)
        note("Only denied commands are logged. Granted approvals do not leave a distinct denial event.")

    st.subheader("📦 Context Pressure & Eviction Signals")
    c = data.counters
    biggest = int(data.session_meta["biggest_tool_output_bytes"].max()) if not data.session_meta.empty else 0
    worst_str = "-"
    if not data.session_meta.empty:
        worst = data.session_meta.nlargest(1, "checkpoints").iloc[0]
        worst_str = f"{int(worst['checkpoints'])} (session {worst['session_id'][:8]})"

    kpi_row([
        ("Checkpoints", f"{c.get('checkpoints', 0):,}", "context window truncations", "✂️", "TRUNCATE"),
        ("Tool Output Files", f"{c.get('tool_outputs', 0):,}", f"{c.get('tool_output_bytes', 0) / 1e6:,.1f} MB injected", "📁", "INJECT"),
        ("Peak Single Output", f"{biggest / 1024:,.0f} KB", "max tool response size", "💾", "PEAK"),
        ("Max Session Checkpoints", worst_str, "heaviest context pressure", "🗜️", "MAX"),
    ], per_row=4)
    note("<b>Context Injection:</b> Every byte returned by a tool is appended into the prompt history. "
         "High tool output triggers prompt truncation and context checkpoints.")


# --------------------------------------------------------------------------- D
def _collab_tab(ctx: Ctx, data: deep.DeepData) -> None:
    st.subheader("🧠 Model Engine Switching")
    col1, col2 = st.columns([1, 1.2])
    with col1:
        if data.model_switches.empty:
            st.info("No model switches recorded.")
        else:
            s = data.model_switches["to_model"].value_counts().head(10)
            fig = go.Figure(go.Pie(
                labels=s.index, values=s.values, hole=0.55,
                textinfo="label+percent", textfont=dict(family="JetBrains Mono"),
                hovertemplate="<b>%{label}</b>: %{value} switches<extra></extra>",
            ))
            fig.update_layout(title="Switches by Target Model", showlegend=False)
            show(fig, ctx.theme, height=340)
    with col2:
        st.markdown("**Recent Model Switch Events**")
        recent = data.model_switches.tail(12)[["date", "from_model", "to_model"]].rename(
            columns={"date": "Date", "from_model": "Prior Model", "to_model": "New Model"})
        st.dataframe(recent.iloc[::-1], hide_index=True, use_container_width=True)
    note("Extracted from <code>USER_SETTINGS_CHANGE</code> records. Logs do not attribute model tags to each call, "
         "so telemetry is evaluated against the user's actively configured engine.")

    st.subheader("🔌 MCP Tool Server Invocations")
    mcp = {k[4:]: v for k, v in data.counters.items() if k.startswith("mcp:")}
    if mcp:
        s = pd.Series(mcp).sort_values(ascending=False)
        fig = go.Figure(go.Bar(
            x=s.values, y=s.index, orientation="h",
            marker_color=colors(ctx.theme)["cached"],
            text=[f"{v:,}" for v in s.values],
            textposition="auto",
            textfont=dict(family="JetBrains Mono"),
            hovertemplate="<b>%{y}</b>: %{x:,} MCP calls<extra></extra>",
        ))
        fig.update_layout(title="Invocations by MCP Server", xaxis_title="Calls",
                          height=max(280, 30 * len(s)))
        show(fig, ctx.theme)
    else:
        st.info("No MCP calls detected.")

    st.subheader("🤖 Subagent Swarm Telemetry")
    sub = data.session_meta[data.session_meta["kind"] == "subagent"] if not data.session_meta.empty else pd.DataFrame()
    main = data.session_meta[data.session_meta["kind"] != "subagent"] if not data.session_meta.empty else pd.DataFrame()
    tokens_by_session = ctx.usage.sessions.set_index("session_id")["total"]
    sub_tokens = int(tokens_by_session.reindex(sub["session_id"]).fillna(0).sum()) if not sub.empty else 0
    main_tokens = int(tokens_by_session.reindex(main["session_id"]).fillna(0).sum()) if not main.empty else 0

    kpi_row([
        ("Subagent Sessions", f"{len(sub):,}", "spawned worker agents", "👥", "COUNT"),
        ("invoke_subagent Calls", f"{data.counters.get('subagent_dispatches', 0):,}", "delegation dispatches", "⚡", "DISPATCH"),
        ("Subagent Token Share", fmt_pct(metrics.safe_div(sub_tokens, sub_tokens + main_tokens)),
         "share of all tokens", "📊", "SHARE"),
        ("Subagent Tokens", fmt_tokens(sub_tokens), "consumed by subagents", "🪙", "TOKENS"),
    ], per_row=4)

    st.subheader("📜 Artifact Ledger & Inter-Agent Messages")
    a1, a2 = st.columns([1.3, 1])
    with a1:
        if data.artifacts.empty:
            st.info("No artifact metadata found.")
        else:
            art = data.artifacts.copy()
            art["request_feedback"] = art["request_feedback"].map({True: "Feedback Req", False: "-"})
            art["updated_at"] = art["updated_at"].astype(str).str.slice(0, 19)
            st.dataframe(art[["name", "updated_at", "request_feedback", "summary"]].rename(
                columns={"name": "Artifact Name", "updated_at": "Updated", "request_feedback": "User Gate", "summary": "Summary"}),
                hide_index=True, use_container_width=True, height=260)
            st.caption(f"Artifacts registered: `{len(data.artifacts)}` · `{int(data.artifacts['request_feedback'].sum())}` requested explicit user approval.")
    with a2:
        c = data.counters
        st.metric("Inter-Agent Messages", f"{c.get('messages_total', 0):,}",
                  f"{c.get('messages_read', 0):,} receipts confirmed")
        st.metric("send_message Tool Calls", f"{c.get('tool:send_message', 0):,}")
        if not data.messages.empty:
            st.caption("Latest Messages")
            st.dataframe(data.messages[["sender", "title", "priority", "read"]].head(8),
                         hide_index=True, use_container_width=True)

    st.subheader("📈 Interaction Matrix Counters")
    c = data.counters
    kpi_row([
        ("Web Searches", f"{c.get('tool:search_web', 0):,}", "web search", "🔍", "SEARCH"),
        ("URL Content Reads", f"{c.get('tool:read_url_content', 0):,}", "scraped URLs", "🌐", "READ"),
        ("Interactive Questions", f"{c.get('tool:ask_question', 0):,}", "user interviews", "❓", "ASK"),
        ("Images Generated", f"{c.get('tool:generate_image', 0):,}", "visual assets", "🎨", "IMAGE"),
        ("Checkpoint Truncations", f"{c.get('checkpoints', 0):,}", "context resets", "✂️", "CHECK"),
        ("Total Steps Scanned", f"{c.get('steps', 0):,}", "transcript steps", "🪜", "STEPS"),
    ], per_row=6)

