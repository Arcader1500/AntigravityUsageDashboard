"""Antigravity usage analytics dashboard - Streamlit entry point.

Run:  streamlit run app.py     (or use run.ps1 / run.bat)

The sidebar owns navigation, global filters and pricing. Each page module
renders into a shared Ctx so every tab uses identical numbers.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from agy_dash import config as cfgmod
from agy_dash import metrics, pricing, source
from agy_dash.jobs import JobRunner
from agy_dash.ui import common
from agy_dash.ui import data_jobs, deep_signals, explorer, forecast, lab, overview

PAGES = {
    "Overview": overview.render,
    "Usage Explorer": explorer.render,
    "Model Cost Lab": lab.render,
    "Forecast": forecast.render,
    "Deep Signals": deep_signals.render,
    "Data & Jobs": data_jobs.render,
}

st.set_page_config(page_title="Antigravity Usage", page_icon="🛰️", layout="wide")
CONFIG = cfgmod.get_config()
LOG = cfgmod.setup_logging(CONFIG)


@st.cache_data(ttl=30, show_spinner=False)
def load_usage(brain_root: str, extractor: str) -> source.UsageData:
    """Scan is ~1.5 s; cache for 30 s so UI interactions stay instant."""
    return source.scan_usage(Path(brain_root), Path(extractor))


@st.cache_data(ttl=300, show_spinner=False)
def load_catalog() -> list:
    return pricing.load_catalog()


def get_runner() -> JobRunner:
    if "runner" not in st.session_state:
        st.session_state["runner"] = JobRunner(
            CONFIG.extractor_script, CONFIG.python_executable,
            table=dict(os.environ), log_dir=CONFIG.log_dir, timeout_seconds=CONFIG.extraction_timeout,
        )
    return st.session_state["runner"]


def sidebar(usage: source.UsageData):
    st.sidebar.title("🛰️ Antigravity Usage")
    page = st.sidebar.radio("Page", list(PAGES), key="nav")

    st.sidebar.divider()
    st.sidebar.caption("FILTERS")
    theme = st.sidebar.radio("Theme", ["dark", "light"], horizontal=True, key="theme")

    daily = usage.daily
    if not daily.empty:
        dmin, dmax = daily["date"].min().date(), daily["date"].max().date()
        picked = st.sidebar.date_input("Date range", value=(dmin, dmax),
                                       min_value=dmin, max_value=dmax, key="flt_dates")
        if isinstance(picked, (list, tuple)) and len(picked) == 2:
            start, end = picked
        else:
            start = end = picked
    else:
        start = end = None
    if st.sidebar.button("Reset filters", key="flt_reset"):
        for k in ("flt_dates", "flt_model", "flt_fx", "flt_sub"):
            st.session_state.pop(k, None)
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("PRICING")
    ids = pricing.models(load_catalog())
    default_id = "gemini-3.8-flash" if "gemini-3.8-flash" in ids else (ids[0] if ids else "")
    model_id = st.sidebar.selectbox("Pricing model", ids, index=ids.index(default_id) if ids else 0,
                                    key="flt_model")
    fx = st.sidebar.number_input("USD → INR rate (dated, edit me)", min_value=0.0,
                                 value=float(CONFIG.usd_to_inr), step=0.5, key="flt_fx")
    sub_cfg = CONFIG.subscription
    sub = st.sidebar.number_input(f"Subscription spend ({sub_cfg.get('currency', 'INR')}) per "
                                  f"{sub_cfg.get('period_days', 30)} days",
                                  min_value=0.0, value=float(sub_cfg.get("amount", 0.0)),
                                  step=100.0, key="flt_sub")
    st.sidebar.caption(sub_cfg.get("label", ""))

    st.sidebar.divider()
    if st.sidebar.button("🔄 Refresh data now", key="flt_refresh"):
        load_usage.clear()
        st.rerun()
    st.sidebar.caption(f"Scanned {usage.scanned_at:%Y-%m-%d %H:%M:%S}")
    runner = get_runner()
    rec = None
    if Path(runner.last_run_path).exists():
        from agy_dash.jobs import last_run
        rec = last_run(runner.last_run_path)
    if rec:
        st.sidebar.caption(f"Last extraction: {rec['status']} ({rec.get('ended_at', '?')[:19]})")
    else:
        st.sidebar.caption("Last extraction: not run from here yet")
    return page, theme, start, end, model_id, fx, sub, runner


def main() -> None:
    try:
        usage = load_usage(str(CONFIG.brain_root), str(CONFIG.extractor_script))
    except source.SourceError as exc:
        st.error(f"Cannot read usage data: {exc}")
        st.markdown(
            "Check `config/config.json`:\n"
            f"* `brain_root` → currently `{CONFIG.brain_root}`\n"
            f"* `extractor_script` → currently `{CONFIG.extractor_script}`"
        )
        st.stop()

    page, theme, start, end, model_id, fx, sub, runner = sidebar(usage)
    common.inject_css(theme)

    daily = source.clip_dates(usage.daily, start, end)
    sessions = source.sessions_touching(usage.sessions, start, end)

    catalog = pricing.Catalog(load_catalog())
    on_date = daily["date"].max().date() if not daily.empty else None
    prices, estimate = catalog.price_on(model_id, on_date)
    if prices is None:
        st.error(f"No pricing entry for model '{model_id}'.")
        st.stop()
    price_note = catalog.availability_warning(model_id, on_date) if estimate else None
    if estimate and on_date:
        price_note = (f"No price version covers {on_date} for {prices.name}; using the "
                      f"{prices.effective_from} version as an ESTIMATE. Prices are dated - "
                      "add a version in config/pricing.json to be exact.")

    ctx = common.build_ctx(
        config=CONFIG, usage=usage, sessions=sessions, daily=daily, catalog=catalog,
        prices=prices, model_id=model_id, price_note=price_note,
        currency=CONFIG.reporting_currency, usd_inr=float(fx),
        subscription_amount=float(sub), theme=theme, runner=runner,
    )

    PAGE_ICONS = {
        "Overview": "📊",
        "Usage Explorer": "🧭",
        "Model Cost Lab": "⚗️",
        "Forecast": "🔮",
        "Deep Signals": "⚡",
        "Data & Jobs": "⚙️",
    }

    t = ctx.overview.totals
    range_str = f"{pd.Timestamp(start):%d %b %Y} → {pd.Timestamp(end):%d %b %Y}" if start and end else "Full Log History"
    badges = [
        (f"MODEL: {prices.name}", "model"),
        (f"RANGE: {range_str}", "range"),
        (f"{common.fmt_tokens(t.total)} TOKENS", "tokens"),
        (f"{ctx.money(ctx.overview.api_cost_usd)} API-EQUIV", "cost"),
    ]
    common.hud_header("ANTIGRAVITY TELEMETRY CONTROL",
                      f"Live session analytics · {t.sessions:,} sessions · {t.active_days} active days",
                      badges)

    st.title(f"{PAGE_ICONS.get(page, '')} {page}")
    if start and end:
        st.caption(f"{range_str} · priced at **{prices.name}** · reporting currency **{ctx.currency}**")
    PAGES[page](ctx)

    st.divider()
    st.caption("🔒 Data is read-only from the Antigravity CLI's local logs; nothing is uploaded. "
               "Costs are computed from tokens with a dated price catalog - not read from the logs.")


if __name__ == "__main__":
    main()
