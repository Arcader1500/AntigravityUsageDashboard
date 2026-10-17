"""B. Usage Explorer - time series, breakdowns, searchable records, CSV export."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from .. import metrics
from .common import Ctx, colors, fmt_pct, fmt_tokens, kpi_row, note, show

METRICS = {
    "Fresh input": "fresh_in",
    "Cached input": "cached",
    "Output": "output",
    "Total tokens": "total",
    "Calls": "calls",
    "Sessions": "sessions",
}


def render(ctx: Ctx) -> None:
    st.subheader("🔍 Filter & Query Console")
    f1, f2, f3, f4 = st.columns([1.2, 1.8, 1, 1.6])
    kinds = sorted(ctx.sessions["kind"].unique()) if not ctx.sessions.empty else []
    default_kinds = kinds or []
    with f1:
        kind_sel = st.multiselect("Session type", kinds, default=default_kinds, key="ex_kind")
    with f2:
        metric_sel = st.multiselect("Series to plot", list(METRICS), default=list(METRICS)[:4], key="ex_metric")
    with f3:
        top_n = st.number_input("Top sessions", min_value=5, max_value=200, value=25, step=5, key="ex_top")
    with f4:
        search = st.text_input("Search records (label or ID)", key="ex_search")

    sessions = ctx.sessions
    if kind_sel:
        sessions = sessions[sessions["kind"].isin(kind_sel)]
    if search:
        s = search.lower()
        sessions = sessions[
            sessions["label"].str.lower().str.contains(s, na=False)
            | sessions["session_id"].str.lower().str.contains(s, na=False)
        ]
    daily = ctx.daily

    if daily.empty:
        note("No records in the selected range.", warn=True)
        return

    daily_costs = metrics.attach_costs(daily, ctx.prices)

    # Tabs for Explorer
    tab_time, tab_sessions, tab_records = st.tabs([
        "📈 Time Series & Burn Trajectory",
        "🏆 Session Leaderboard & Architecture",
        "🗂️ Data Records & CSV Export"
    ])

    with tab_time:
        _timeseries(ctx, daily_costs, metric_sel)
        _calls_sessions(ctx, daily)

    with tab_sessions:
        # Quick summary stats
        sub_count = int((sessions["kind"] == "subagent").sum()) if not sessions.empty else 0
        main_count = int((sessions["kind"] == "main").sum()) if not sessions.empty else 0
        total_tok = int(sessions["total"].sum()) if not sessions.empty else 0
        kpi_row([
            ("Filtered Sessions", f"{len(sessions):,}", f"{main_count} main · {sub_count} subagents", "🧭", "COUNT"),
            ("Filtered Volume", fmt_tokens(total_tok), "tokens in view", "⚡", "VOLUME"),
            ("Avg Tokens / Session", fmt_tokens(total_tok / max(1, len(sessions))), "mean workload", "📊", "AVERAGE"),
        ], per_row=3)

        left, right = st.columns([1.5, 1])
        with left:
            _top_sessions(ctx, sessions, int(top_n))
        with right:
            _kind_split(ctx, sessions)

    with tab_records:
        _records(ctx, daily_costs, sessions)


def _timeseries(ctx: Ctx, daily_costs, metric_sel: list[str]) -> None:
    c = colors(ctx.theme)
    fig = go.Figure()
    color_map = {
        "fresh_in": c["fresh"], "cached": c["cached"], "output": c["output"],
        "total": c["accent"], "calls": c["warn"], "sessions": c["cost"]
    }
    for label in metric_sel:
        col = METRICS[label]
        fig.add_trace(go.Scatter(
            x=daily_costs["date"], y=daily_costs[col], name=label, mode="lines+markers",
            line=dict(color=color_map[col], width=2),
            marker=dict(size=5),
            hovertemplate=f"<b>{label}</b>: %{{y:,.0f}}<extra></extra>",
        ))
    if metric_sel and set(metric_sel) != {"Calls", "Sessions"}:
        fig.add_trace(go.Scatter(
            x=daily_costs["date"],
            y=[metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr) for v in daily_costs["cost_usd"]],
            name=f"API-equivalent cost ({ctx.currency})", mode="lines", yaxis="y2",
            line=dict(color=c["cost"], width=2.5, dash="dot"),
            hovertemplate=f"<b>API Cost</b>: {ctx.currency} %{{y:,.2f}}<extra></extra>",
        ))
    fig.update_layout(
        title="Token Metrics Over Time",
        yaxis_title="Count",
        hovermode="x unified",
        yaxis2=dict(
            title=f"Cost ({ctx.currency})",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color=c["cost"]),
        ),
        legend=dict(orientation="h", y=1.12),
    )
    show(fig, ctx.theme, height=430)


def _calls_sessions(ctx: Ctx, daily) -> None:
    c = colors(ctx.theme)
    fig = go.Figure()
    fig.add_bar(x=daily["date"], y=daily["calls"], name="Model Calls", marker_color=c["accent"])
    fig.add_trace(go.Scatter(
        x=daily["date"], y=daily["sessions"], name="Distinct Sessions",
        mode="lines+markers", yaxis="y2",
        line=dict(color=c["cached"], width=2.5),
        marker=dict(size=6, color=c["cached"]),
        hovertemplate="<b>Sessions</b>: %{y}<extra></extra>",
    ))
    fig.update_layout(
        title="Model Invocations vs Distinct Sessions per Day",
        hovermode="x unified",
        yaxis_title="Model Calls",
        yaxis2=dict(title="Sessions", overlaying="y", side="right", showgrid=False,
                    tickfont=dict(color=c["cached"])),
        legend=dict(orientation="h", y=1.12),
    )
    show(fig, ctx.theme, height=350)


def _top_sessions(ctx: Ctx, sessions, top_n: int) -> None:
    if sessions.empty:
        st.info("No sessions match the filters.")
        return
    s = sessions.nlargest(top_n, "total").copy()
    s["cost"] = [metrics.api_cost_usd(r.fresh_in, r.cached, r.output, ctx.prices) for r in s.itertuples()]
    s = s.sort_values("total")
    c = colors(ctx.theme)
    kind_color = {"main": c["accent"], "subagent": c["cached"], "other": c["muted"]}
    fig = go.Figure(go.Bar(
        x=s["total"], y=s["label"].str.slice(0, 42), orientation="h",
        marker_color=[kind_color.get(k, c["muted"]) for k in s["kind"]],
        customdata=[[r.session_id, ctx.money(r.cost), fmt_tokens(r.fresh_in),
                     fmt_tokens(r.cached), fmt_tokens(r.output), int(r.calls), r.kind] for r in s.itertuples()],
        hovertemplate=("<b>%{y}</b> [%{customdata[6]}]<br>Session: <code>%{customdata[0]}</code><br>"
                       "Total Tokens: <b>%{x:,.0f}</b><br>API Equiv: %{customdata[1]}<br>"
                       "Fresh: %{customdata[2]} | Cached: %{customdata[3]} | Output: %{customdata[4]}<br>"
                       "Model Invocations: %{customdata[5]} calls<extra></extra>"),
    ))
    fig.update_layout(
        title=f"Top {len(s)} Heavyweight Sessions (by Total Tokens)",
        xaxis_title="Total Tokens",
        yaxis_title="",
        height=max(380, 24 * len(s)),
    )
    show(fig, ctx.theme)
    note("Model attribution is not recorded per call in the source logs; every session above is priced "
         "at the model selected in the sidebar.")


def _kind_split(ctx: Ctx, sessions) -> None:
    if sessions.empty:
        return
    c = colors(ctx.theme)
    grp = sessions.groupby("kind", as_index=False).agg(tokens=("total", "sum"), calls=("calls", "sum"))
    kind_color = {"main": c["accent"], "subagent": c["cached"], "other": c["muted"]}
    fig = go.Figure(go.Pie(
        labels=grp["kind"].str.upper(),
        values=grp["tokens"],
        hole=0.55,
        marker=dict(colors=[kind_color.get(k, c["muted"]) for k in grp["kind"]]),
        textinfo="label+percent",
        textfont=dict(family="JetBrains Mono"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} tokens (%{percent})<extra></extra>",
    ))
    fig.update_layout(title="Token Share by Session Class", showlegend=False)
    show(fig, ctx.theme, height=360)
    sub_share = metrics.safe_div(int(grp.loc[grp['kind'].eq('subagent'), 'tokens'].sum()), int(grp['tokens'].sum()))
    st.caption(f"🤖 **{fmt_pct(sub_share)}** of filtered tokens ran in autonomous subagent sessions.")


def _records(ctx: Ctx, daily_costs, sessions) -> None:
    st.subheader("🗄️ Raw Data Ledger")
    tab_daily, tab_sessions = st.tabs(["Daily Records", "Session Records"])
    with tab_daily:
        df = daily_costs.assign(
            date=daily_costs["date"].dt.strftime("%Y-%m-%d"),
            cost=[ctx.money(v) for v in daily_costs["cost_usd"]],
        )[["date", "sessions", "calls", "fresh_in", "cached", "output", "total", "cost"]]
        st.caption(f"{len(df)} daily snapshots · tokens are raw recorded counts, cost computed at {ctx.prices.name}")
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button("📥 Download Daily CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="antigravity_daily.csv", mime="text/csv", key="dl_daily")
    with tab_sessions:
        if sessions.empty:
            st.info("No sessions match the filters.")
            return
        cost = [metrics.api_cost_usd(r.fresh_in, r.cached, r.output, ctx.prices) for r in sessions.itertuples()]
        df = sessions.assign(
            cost=[ctx.money(v) for v in cost],
        )[["session_id", "label", "kind", "calls", "fresh_in", "cached", "output", "total",
           "cost", "first_date", "last_date"]].sort_values("total", ascending=False)
        st.caption(f"{len(df)} sessions matched")
        st.dataframe(df, hide_index=True, use_container_width=True)
        st.download_button("📥 Download Session CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="antigravity_sessions.csv", mime="text/csv", key="dl_sessions")

