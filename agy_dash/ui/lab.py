"""C. Model Cost Laboratory - dated price catalog, what-if workload, model comparison."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .. import metrics
from .common import Ctx, colors, fmt_pct, fmt_tokens, kpi_row, note, show


def render(ctx: Ctx) -> None:
    base = {
        "fresh_in": int(ctx.overview.totals.fresh_in),
        "cached": int(ctx.overview.totals.cached),
        "output": int(ctx.overview.totals.output),
    }
    if base["fresh_in"] + base["cached"] + base["output"] == 0:
        note("No observed tokens in the selected range - widen the date range first.", warn=True)
        return

    # Baseline Workload HUD
    st.subheader("🧪 Workload Baseline & Simulator")
    cache_share = metrics.cache_hit_rate(base['fresh_in'], base['cached'])
    kpi_row([
        ("Prompt Tokens", fmt_tokens(base["fresh_in"] + base["cached"]),
         f"{fmt_pct(cache_share)} cached", "📥", "INPUT"),
        ("Output Tokens", fmt_tokens(base["output"]), "generation + reasoning", "📤", "OUTPUT"),
        ("Total Workload", fmt_tokens(sum(base.values())), "observed in window", "⚡", "VOLUME"),
    ], per_row=3)

    tab_sim, tab_sub = st.tabs([
        "⚗️ What-If Simulator & Model Benchmark",
        "💳 Subscription vs Metered Economics & Catalog"
    ])

    with tab_sim:
        st.markdown("**Interactive Scenario Controls**")
        a1, a2, a3 = st.columns([1.2, 1, 1])
        with a1:
            use_ratio = st.checkbox("Simulate custom cache ratio", value=False, key="lab_use_ratio")
            observed_ratio = metrics.cache_hit_rate(base["fresh_in"], base["cached"])
            ratio = st.slider("Cached share of prompt", 0.0, 1.0,
                              float(round(observed_ratio, 2)), 0.01,
                              disabled=not use_ratio, key="lab_ratio")
        with a2:
            output_mult = st.slider("Output volume multiplier", 0.0, 3.0, 1.0, 0.05, key="lab_out")
        with a3:
            prompt_mult = st.slider("Prompt volume multiplier", 0.0, 3.0, 1.0, 0.05, key="lab_prompt")

        tokens = metrics.hypothetical_tokens(
            base["fresh_in"] * prompt_mult, base["cached"] * prompt_mult, base["output"],
            cached_ratio=ratio if use_ratio else None, output_multiplier=output_mult,
        )
        changed = (abs(prompt_mult - 1) > 1e-9 or abs(output_mult - 1) > 1e-9 or use_ratio)
        if changed:
            note(f"🧪 <b>Simulated scenario active:</b> {fmt_tokens(tokens['fresh_in'])} fresh + "
                 f"{fmt_tokens(tokens['cached'])} cached + {fmt_tokens(tokens['output'])} output. "
                 "These are hypothetical modeling assumptions, not actual measurements.")
        else:
            note("Showing the observed workload as-is. Adjust the sliders above to model higher prompt sizes, "
                 "longer generation reasoning, or varying cache hit rates.")

        st.subheader("⚖️ Multi-Model Cost Matrix")
        all_models = ctx.catalog.entries
        labels = {e.model_id: e.name for e in all_models}
        ids = sorted(labels)
        defaults = [m for m in ("gemini-3.8-flash", "gemini-4-argon", "claude-sonnet",
                                "claude-opus", "gpt-flagship", "deepseek-v3-api") if m in ids]
        chosen = st.multiselect("Select models to benchmark", ids, default=defaults or ids[:5],
                                format_func=lambda m: labels.get(m, m), key="lab_models")

        on_date = ctx.daily["date"].max().date() if not ctx.daily.empty else None
        cmp = metrics.compare_models(tokens, ctx.catalog, chosen, on=on_date)
        if cmp.empty:
            st.info("Pick at least one model to benchmark.")
            return

        cmp["cost"] = [metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr) for v in cmp["cost_usd"]]
        cmp["cost_per_mtok"] = [metrics.currency_from_usd(v, ctx.currency, ctx.usd_inr)
                                for v in cmp["cost_per_mtok_usd"]]
        total_tokens = sum(tokens.values())
        cmp["tokens_per_currency"] = [metrics.tokens_per_currency(total_tokens, c) for c in cmp["cost"]]
        cmp["vs_cheapest"] = cmp["cost"] / cmp["cost"].min() if cmp["cost"].min() else 1.0
        cmp["price_note"] = ["estimate - no price version covers this date" if e else "" for e in cmp["estimate"]]

        view = cmp[["model", "vendor", "cost", "cost_per_mtok", "tokens_per_currency",
                    "vs_cheapest", "pricing_from", "price_note"]].rename(columns={
            "cost": f"Workload Cost ({ctx.currency})",
            "cost_per_mtok": f"Per 1M Tokens ({ctx.currency})",
            "tokens_per_currency": f"Tokens per {ctx.currency}",
            "vs_cheapest": "vs Cheapest", "pricing_from": "Price Version From",
            "price_note": "Note",
        })
        st.dataframe(view, hide_index=True, use_container_width=True)
        note("Estimates assume every model produces <b>identical token counts</b>. That is an assumption to "
             "make models comparable, not a measurement - real token counts differ per model and per task. "
             "Prices are the catalog's dated list prices (USD per 1M tokens); rows flagged 'estimate' have no "
             "price version covering the observed period and fall back to the nearest earlier version.")

        c = colors(ctx.theme)
        fig = go.Figure(go.Bar(
            x=cmp["cost"], y=cmp["model"], orientation="h",
            marker_color=[c["warn"] if e else c["accent"] for e in cmp["estimate"]],
            text=[f"{ctx.currency} {v:,.2f}" for v in cmp["cost"]],
            textposition="auto",
            textfont=dict(family="JetBrains Mono"),
            customdata=cmp[["cost_per_mtok"]],
            hovertemplate="<b>%{y}</b><br>Workload Cost: %{x:,.2f} " + ctx.currency +
                          "<br>Per 1M: %{customdata[0]:,.2f} " + ctx.currency + "<extra></extra>",
        ))
        fig.update_layout(title=f"Same Workload Run Across Different Engines ({ctx.currency})",
                          xaxis_title=ctx.currency, showlegend=False,
                          height=max(340, 36 * len(cmp)))
        show(fig, ctx.theme)

    with tab_sub:
        _subscription_panel(ctx, cmp)


def _subscription_panel(ctx: Ctx, cmp: pd.DataFrame) -> None:
    st.subheader("💳 Fixed Subscription vs Equivalent Metered API Value")
    o = ctx.overview
    diff = o.api_cost_usd - o.subscription_spend_usd
    diff_curr = metrics.currency_from_usd(diff, ctx.currency, ctx.usd_inr)

    kpi_row([
        ("Fixed Subscription Fee", ctx.money(o.subscription_spend), ctx.config.subscription.get("label", ""), "💳", "ACTUAL"),
        (f"API Value at {ctx.model_id}", ctx.money(o.api_cost_usd), f"metered consumption", "⚡", "EQUIV"),
        ("Theoretical Delta", ctx.money(diff_curr), "API value vs subscription", "⚖️", "MARGIN"),
    ], per_row=3)

    c = colors(ctx.theme)
    fig = go.Figure(go.Bar(
        x=[o.subscription_spend, metrics.currency_from_usd(o.api_cost_usd, ctx.currency, ctx.usd_inr)],
        y=["Actual Subscription Spend", f"API-Equivalent ({ctx.model_id})"],
        orientation="h",
        marker_color=[c["cached"], c["accent"]],
        text=[ctx.money(o.subscription_spend), ctx.money(o.api_cost_usd)],
        textposition="auto",
        textfont=dict(family="JetBrains Mono"),
        hovertemplate="<b>%{y}</b>: %{x:,.2f} " + ctx.currency + "<extra></extra>",
    ))
    fig.update_layout(title=f"Actual Spend vs Equivalent Metered Billing ({ctx.currency})",
                      xaxis_title=ctx.currency, showlegend=False, height=280)
    show(fig, ctx.theme)
    note("The difference is <b>not cash saved and not cash owed</b>: the subscription is a flat recurring fee and "
         "the API figure is what these tokens would cost per-token on a public API. Under a quota plan the "
         "marginal cost of this usage is zero; over quota, only the overage is actually billed.")

    with st.expander("📖 Versioned Price Catalog Reference (Dated USD / 1M Tokens)"):
        rows = [{
            "Model": e.name, "Vendor": e.vendor, "Effective From": e.effective_from,
            "Effective Until": e.effective_until or "open",
            "Input ($/1M)": f"${e.input_usd:.3f}",
            "Cached ($/1M)": f"${e.cached_usd:.3f}",
            "Output ($/1M)": f"${e.output_usd:.3f}",
            "Verified": "✅" if e.verified else "⚠️", "Source": e.source,
        } for e in ctx.catalog.entries]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Pricing catalog source: `config/pricing.json`. 'Verified' indicates manual date-stamped confirmation.")

