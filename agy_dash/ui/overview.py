"""A. Overview - headline KPI cards, interactive tabs, and daily trends."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from .. import metrics
from ..jobs import last_run
from .common import Ctx, colors, fmt_pct, fmt_tokens, kpi_row, note, show


def render(ctx: Ctx) -> None:
    o = ctx.overview
    t = o.totals
    c = colors(ctx.theme)

    if t.total == 0:
        note("No token-bearing records in the selected range. Token fields only exist from "
             "2026-10-05 onward - widen the date range.", warn=True)
        return

    rec = last_run(ctx.runner.last_run_path)
    last_ok = (f"{rec['ended_at'][:19]} ({rec['status']})" if rec else "never run from this dashboard")
    st.caption(f"🔄 Last data refresh: `{ctx.usage.scanned_at:%Y-%m-%d %H:%M:%S}` · "
               f"Last extraction: `{last_ok}` · Root: `{ctx.usage.root}`")

    # Headline KPI Cards
    st.subheader("⚡ Token Telemetry")
    kpi_row([
        ("Total tokens", fmt_tokens(t.total), f"{t.active_days} active days", "⚡", "ALL TOKENS"),
        ("Fresh input", fmt_tokens(t.fresh_in), f"{fmt_pct(metrics.safe_div(t.fresh_in, t.total))} of volume", "📥", "UNCACHED"),
        ("Cached input", fmt_tokens(t.cached), f"{fmt_pct(t.cache_hit_rate)} hit efficiency", "⚡", "REUSED"),
        ("Output tokens", fmt_tokens(t.output), "includes reasoning", "📤", "GENERATED"),
        ("Model calls", f"{t.calls:,}", f"{(t.calls / max(1, t.active_days)):.1f} calls/day", "📞", "CALLS"),
        ("Sessions", f"{t.sessions:,}", f"{(t.total / max(1, t.sessions)):,.0f} tok/session", "🧭", "SESSIONS"),
    ])

    st.subheader("💰 Economics & Value Assessment")
    curr_label = "Rupee" if o.currency == "INR" else o.currency
    kpi_row([
        ("Equivalent API cost", ctx.money(o.api_cost_usd), f"at {ctx.prices.name}", "💰", "EQUIV"),
        ("Actual subscription", ctx.money(o.subscription_spend), ctx.config.subscription.get("label", ""), "💳", "FIXED"),
        (f"Tokens per {curr_label}", fmt_tokens(o.tokens_per_currency_spent), "observed tokens / actual spend", "🪙", "LEVERAGE"),
        ("Blended API rate", f"{ctx.money(o.blended_rate_usd_per_mtok)}/1M", "cost / token x 1M", "🏷️", "RATE"),
        ("Cache hit rate", fmt_pct(t.cache_hit_rate), "cached / prompt tokens", "🎯", "HIT RATE"),
        ("Cost split", f"{ctx.money(o.breakdown_usd['fresh_in'])} fresh",
         f"{ctx.money(o.breakdown_usd['cached'])} cached · {ctx.money(o.breakdown_usd['output'])} out", "⚖️", "BREAKDOWN"),
    ])

    note("<b>Equivalent API cost</b> is consumption-equivalent, not cash. Inside a subscription quota the real "
         "marginal spend is zero; it is what the same usage would bill on a metered API. Subscription "
         "spend is reported separately and is never subtracted from it.")
    if ctx.price_note:
        note(ctx.price_note, warn=True)

    # Interactive Sub-Tabs for deeper telemetry
    tab_trend, tab_composition, tab_extremes = st.tabs([
        "📈 Daily Trends & Cost Burn",
        "🍩 Token Composition & Economics",
        "⚡ Extremes & Activity Cadence"
    ])

    with tab_trend:
        _daily_trend(ctx)
    with tab_composition:
        _distribution(ctx)
    with tab_extremes:
        _best_worst(ctx)


def _daily_trend(ctx: Ctx) -> None:
    daily = ctx.daily
    c = colors(ctx.theme)
    cost = [metrics.currency_from_usd(x, ctx.currency, ctx.usd_inr)
            for x in metrics.attach_costs(daily, ctx.prices)["cost_usd"]]

    fig = go.Figure()
    fig.add_bar(x=daily["date"], y=daily["fresh_in"], name="Fresh input (uncached)", marker_color=c["fresh"])
    fig.add_bar(x=daily["date"], y=daily["cached"], name="Cached input (reused)", marker_color=c["cached"])
    fig.add_bar(x=daily["date"], y=daily["output"], name="Output & Thinking", marker_color=c["output"])
    fig.update_layout(
        barmode="stack",
        hovermode="x unified",
        title="Daily Token Ingestion & API-Equivalent Cost Burn",
        yaxis_title="Token Volume",
        legend=dict(orientation="h", y=1.12),
    )
    fig.add_trace(go.Scatter(
        x=daily["date"], y=cost, name=f"API-equivalent cost ({ctx.currency})",
        mode="lines+markers", yaxis="y2", line=dict(color=c["cost"], width=2.5),
        marker=dict(size=6, color=c["cost"]),
        hovertemplate=f"API cost: {ctx.currency} %{{y:,.2f}}<extra></extra>",
    ))
    fig.update_layout(
        yaxis2=dict(
            title=f"Cost ({ctx.currency})",
            overlaying="y",
            side="right",
            showgrid=False,
            tickfont=dict(color=c["cost"]),
        ),
    )
    show(fig, ctx.theme, height=450)
    st.caption("💡 Hover to inspect exact daily token layers; drag to zoom into time windows; click any legend item to toggle series.")


def _distribution(ctx: Ctx) -> None:
    o = ctx.overview
    left, right = st.columns(2)
    c = colors(ctx.theme)

    with left:
        fig = go.Figure(go.Pie(
            labels=["Fresh input", "Cached input", "Output"],
            values=[o.totals.fresh_in, o.totals.cached, o.totals.output],
            hole=0.6,
            marker=dict(colors=[c["fresh"], c["cached"], c["output"]]),
            hovertemplate="<b>%{label}</b><br>%{value:,.0f} tokens<br>%{percent} of volume<extra></extra>",
            textinfo="percent",
            textfont=dict(size=13, family="JetBrains Mono"),
        ))
        fig.update_layout(
            title="Token Mix (Prompt Fresh vs Cached vs Output)",
            showlegend=True,
            annotations=[dict(text=f"<b>{fmt_tokens(o.totals.total)}</b><br><span style='font-size:10px; color:{c['muted']}'>TOTAL</span>",
                              x=0.5, y=0.5, font_size=16, showarrow=False)],
        )
        show(fig, ctx.theme, height=360)

    with right:
        b = o.breakdown_usd
        cost_values = [metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr) for v in (b["fresh_in"], b["cached"], b["output"])]
        fig = go.Figure(go.Bar(
            x=cost_values,
            y=["Fresh input", "Cached input", "Output"],
            orientation="h",
            marker_color=[c["fresh"], c["cached"], c["output"]],
            text=[ctx.money(v) for v in (b["fresh_in"], b["cached"], b["output"])],
            textposition="auto",
            textfont=dict(family="JetBrains Mono"),
            hovertemplate="<b>%{y}</b><br>API Equiv: %{x:,.2f} " + ctx.currency + "<extra></extra>",
        ))
        fig.update_layout(
            title=f"Cost Burden by Token Class ({ctx.currency})",
            xaxis_title=f"Equivalent Cost ({ctx.currency})",
            showlegend=False,
        )
        show(fig, ctx.theme, height=360)


def _best_worst(ctx: Ctx) -> None:
    bw = metrics.best_worst_days(ctx.daily, ctx.prices, n=3)
    st.subheader("⚡ High & Low Consumption Peaks")
    col1, col2 = st.columns(2)
    for col, key, title, badge in ((col1, "best", "Top 3 Heaviest Usage Days", "🔥 PEAK"),
                                   (col2, "worst", "Top 3 Lightest Active Days", "🌱 LOW")):
        df = bw[key]
        with col:
            st.markdown(f"**{title}** <span class='agy-tag'>{badge}</span>", unsafe_allow_html=True)
            if df.empty:
                st.write("not enough data")
                continue
            view = df.assign(
                date=df["date"].dt.strftime("%a, %d %b %Y"),
                tokens=df["total"].map(fmt_tokens),
                cost=df["cost_usd"].map(ctx.money),
            )[["date", "tokens", "cost", "calls"]]
            st.dataframe(view, hide_index=True, use_container_width=True)

