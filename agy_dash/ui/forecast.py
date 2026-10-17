"""D. Historical usage and forecasting - extrapolation, bootstrap, Monte Carlo."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import metrics, stats
from .common import Ctx, colors, fmt_pct, fmt_tokens, kpi_row, note, show

TARGETS = {
    "Total tokens": ("total", "tokens"),
    "Fresh input tokens": ("fresh_in", "tokens"),
    "Cached input tokens": ("cached", "tokens"),
    "Output tokens": ("output", "tokens"),
    "Model calls": ("calls", "calls"),
    "API-equivalent cost": ("cost", None),  # currency
}


def render(ctx: Ctx) -> None:
    daily = ctx.daily
    if daily.empty or len(daily) < 2:
        note("Not enough observed days to model anything. At least 2 active days are needed; "
             "the token fields start 2026-10-05.", warn=True)
        return

    st.subheader("🔮 Predictive Modeling Engine")
    c1, c2, c3 = st.columns([1.3, 1.2, 1])
    with c1:
        target = st.selectbox("What to model", list(TARGETS), key="fc_target")
    with c2:
        method = st.selectbox("Method", list(stats.METHODS), index=1, key="fc_method")
    with c3:
        horizon = st.slider("Horizon (calendar days)", 1, 180, 30, key="fc_horizon")

    g1, g2, g3 = st.columns(3)
    with g1:
        daily_growth = st.slider("Assumed daily growth (linear model)", -0.05, 0.10, 0.0, 0.005,
                                 format="%.3f", key="fc_growth")
    with g2:
        mc_growth = st.slider("Monte Carlo drift (mean daily growth)", -0.05, 0.10, 0.0, 0.005,
                              format="%.3f", key="fc_mcgrowth")
    with g3:
        mc_sd = st.slider("Monte Carlo volatility (sigma)", 0.0, 1.5, 0.5, 0.05, key="fc_mcsd")

    column, unit = TARGETS[target]
    observed = _observed(ctx, daily, column)
    if observed.empty or observed[column].sum() == 0:
        note("The selected target has no data in this range.", warn=True)
        return

    values = observed[column].to_numpy(dtype=float)
    last_date = observed["date"].max()

    kwargs = {}
    if method == "Linear extrapolation (baseline)":
        kwargs = {"daily_growth": daily_growth}
    elif method == "Monte Carlo simulation":
        kwargs = {"growth_mean": mc_growth, "growth_sd": max(mc_sd, 0.01)}
    fc = stats.run_forecast(method, values, horizon, last_date=last_date, **kwargs)

    unit_fmt = (lambda v: ctx.money(v)) if unit is None else fmt_tokens
    if not fc.supported:
        note(f"{method} cannot run on this window: {fc.assumptions}", warn=True)

    kpi_row([
        ("Observed Daily Mean", unit_fmt(float(np.mean(values))), f"{len(values)} active days measured", "📊", "MEASURED"),
        ("Forecast Low (P10)", unit_fmt(fc.cumulative_low), "conservative floor", "📉", "P10"),
        ("Forecast Median (P50)", unit_fmt(fc.cumulative_median), "central projection", "🎯", "P50"),
        ("Forecast High (P90)", unit_fmt(fc.cumulative_high), "tail workload surge", "📈", "P90"),
    ], per_row=4)

    note(f"<b>Algorithm:</b> {method} · <i>Assumptions:</i> {fc.assumptions}.<br>{stats.uncertainty_note(len(values))}")
    for extra in fc.notes:
        note(extra, warn=True)
    if fc.supported:
        note("The dashed line and shaded band are <b>statistically modeled</b>, not logged. They describe a possible "
             "future trajectory under the mathematical assumptions above; nothing here reconstructs past behaviour.")

    # Sub-tabs for projection details
    tab_chart, tab_ledger, tab_historical = st.tabs([
        "🔮 Trajectory Projection (History vs Future)",
        "📋 Forecast Quantiles & Daily Ledger",
        "📅 Measured Historical Cadence"
    ])

    with tab_chart:
        _chart(ctx, observed, fc, column, unit, unit_fmt)
    with tab_ledger:
        _tables(ctx, fc, unit, unit_fmt)
    with tab_historical:
        _aggregates(ctx, daily, column, unit, unit_fmt)


def _observed(ctx: Ctx, daily: pd.DataFrame, column: str) -> pd.DataFrame:
    if column == "cost":
        d = metrics.attach_costs(daily, ctx.prices).copy()
        d["cost"] = [metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr) for v in d["cost_usd"]]
        return stats.observed_series(d, "cost")
    return stats.observed_series(daily, column)


def _chart(ctx: Ctx, observed, fc, column: str, unit, unit_fmt) -> None:
    c = colors(ctx.theme)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=observed["date"], y=observed[column], name="Measured (logged telemetry)", mode="lines+markers",
        line=dict(color=c["accent"], width=2.5),
        marker=dict(size=6, color=c["accent"]),
        hovertemplate=f"<b>Measured</b>: %{{y:,.2f}}<extra></extra>",
    ))
    if fc.supported and fc.horizon_days:
        fig.add_trace(go.Scatter(x=fc.dates, y=fc.per_day_high, name="High Confidence (P90)", mode="lines",
                                 line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=fc.dates, y=fc.per_day_low, name="P10..P90 Confidence Band", mode="lines",
                                 line=dict(width=0), fill="tonexty",
                                 fillcolor="rgba(56, 189, 248, 0.16)",
                                 hovertemplate="<b>P10 Floor</b>: %{y:,.2f}<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=fc.dates, y=fc.per_day_median, name="Modelled Median (Future P50)",
            mode="lines", line=dict(color=c["output"], width=2.5, dash="dash"),
            hovertemplate="<b>P50 Projection</b>: %{y:,.2f}<extra></extra>",
        ))
        fig.add_vline(x=fc.dates[0], line=dict(color=c["muted"], width=1, dash="dot"),
                      annotation_text="PROJECTION HORIZON →", annotation_position="top right",
                      annotation_font=dict(color=c["muted"], size=10, family="JetBrains Mono"))
    fig.update_layout(
        title="Measured History vs Modelled Future Horizon",
        hovermode="x unified",
        yaxis_title=(ctx.currency if unit is None else "Token Volume"),
        legend=dict(orientation="h", y=1.12),
    )
    show(fig, ctx.theme, height=450)
    st.caption("💡 Zoom or pan to examine specific intervals; the shaded band is the 10th-90th percentile of simulated paths.")


def _tables(ctx: Ctx, fc, unit, unit_fmt) -> None:
    left, right = st.columns([1, 1.4])
    with left:
        st.markdown("**Cumulative Horizon Summary**")
        if fc.supported and fc.horizon_days:
            st.dataframe(pd.DataFrame([
                {"Percentile": "Conservative Low (P10)", "Cumulative Total": unit_fmt(fc.cumulative_low)},
                {"Percentile": "Expected Median (P50)", "Cumulative Total": unit_fmt(fc.cumulative_median)},
                {"Percentile": "Upper Surge (P90)", "Cumulative Total": unit_fmt(fc.cumulative_high)},
            ]), hide_index=True, use_container_width=True)
            if unit is None and ctx.overview.subscription_spend:
                payback = metrics.safe_div(fc.cumulative_median, ctx.subscription_spend)
                st.caption(f"Median forecast is **{fmt_pct(payback, 0)}** of the configured subscription spend.")
        else:
            st.write("Method unavailable for this window.")
    with right:
        st.markdown("**Daily Projected Schedule**")
        if fc.supported and fc.horizon_days:
            df = fc.to_frame()
            df["date"] = df["date"].dt.strftime("%Y-%m-%d")
            st.dataframe(df, hide_index=True, use_container_width=True, height=250)
            st.download_button("📥 Download Forecast CSV", fc.to_frame().to_csv(index=False).encode("utf-8"),
                               file_name="antigravity_forecast.csv", mime="text/csv", key="dl_fc")
        else:
            st.write("-")


def _aggregates(ctx: Ctx, daily, column: str, unit, unit_fmt) -> None:
    st.subheader("📅 Measured Historical Aggregates")
    freq = st.radio("Cadence Period", ["daily", "weekly", "monthly"], index=0, horizontal=True, key="fc_agg")
    agg = stats.aggregate(daily, freq)
    if column == "cost":
        d = metrics.attach_costs(agg, ctx.prices)
        d["cost"] = [metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr) for v in d["cost_usd"]]
        y, name = d["cost"], f"Cost ({ctx.currency})"
    else:
        y, name = agg[column], column
    fig = go.Figure(go.Bar(
        x=agg["date"], y=y, name=name, marker_color=colors(ctx.theme)["accent"],
        hovertemplate="%{x|%Y-%m-%d}: %{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=f"Measured {target_label(column).title()} ({freq.capitalize()} Ingestion)",
        showlegend=False,
        yaxis_title=(ctx.currency if unit is None else "Token Volume"),
    )
    show(fig, ctx.theme, height=340)
    st.caption("🔒 Aggregated measured telemetry only - no statistical projections mixed in.")


def target_label(column: str) -> str:
    for label, (col, _) in TARGETS.items():
        if col == column:
            return label.lower()
    return column

