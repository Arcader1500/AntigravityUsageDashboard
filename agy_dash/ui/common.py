"""Theme, formatting, chart styling and the shared page context."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from ..config import Config
from .. import metrics
from ..pricing import Catalog, PriceEntry
from ..source import UsageData

# High-fidelity telemetry palette: vivid accents with deep contrast.
DARK = {
    "bg": "#080c14",
    "panel": "rgba(15, 23, 42, 0.75)",
    "panel_solid": "#0f172a",
    "panel_alt": "#141e33",
    "border": "rgba(255, 255, 255, 0.08)",
    "border_highlight": "rgba(56, 189, 248, 0.35)",
    "text": "#f1f5f9",
    "text_bright": "#ffffff",
    "muted": "#94a3b8",
    "dim": "#64748b",
    "accent": "#38bdf8",     # Electric Cyan
    "fresh": "#38bdf8",      # Fresh input tokens
    "cached": "#10b981",     # Cached tokens (Emerald)
    "output": "#f59e0b",     # Output & thinking tokens (Solar Amber)
    "cost": "#a78bfa",       # Equivalent API cost (Radiant Violet)
    "warn": "#fbbf24",       # Warning/notice (Golden Amber)
    "bad": "#f43f5e",        # Error/friction (Rose Coral)
    "grid": "rgba(255, 255, 255, 0.05)",
    "card_bg": "linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(11, 17, 30, 0.95) 100%)",
}

LIGHT = {
    "bg": "#f8fafc",
    "panel": "rgba(255, 255, 255, 0.85)",
    "panel_solid": "#ffffff",
    "panel_alt": "#f1f5f9",
    "border": "rgba(226, 232, 240, 0.9)",
    "border_highlight": "rgba(2, 132, 199, 0.35)",
    "text": "#0f172a",
    "text_bright": "#020617",
    "muted": "#64748b",
    "dim": "#94a3b8",
    "accent": "#0284c7",     # Deep Sky
    "fresh": "#0284c7",      # Fresh input tokens
    "cached": "#059669",     # Cached tokens (Forest Emerald)
    "output": "#d97706",     # Output tokens (Warm Ochre)
    "cost": "#7c3aed",       # Cost (Royal Violet)
    "warn": "#b45309",       # Warning
    "bad": "#e11d48",        # Error (Crimson)
    "grid": "rgba(0, 0, 0, 0.05)",
    "card_bg": "linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(248, 250, 252, 0.95) 100%)",
}


def colors(theme: str = "dark") -> dict:
    return LIGHT if theme == "light" else DARK


# --- formatting -----------------------------------------------------------
def fmt_tokens(n) -> str:
    n = float(n or 0)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(n) >= div:
            return f"{n / div:,.2f}{suf}".replace(".00", "")
    return f"{n:,.0f}"


def fmt_money(amount, currency: str = "USD", decimals: int = 2) -> str:
    sym = {"USD": "$", "INR": "₹", "EUR": "€", "GBP": "£"}.get(str(currency).upper(), "")
    return f"{sym}{float(amount or 0):,.{decimals}f}"


def fmt_pct(x, decimals: int = 1) -> str:
    return f"{float(x or 0) * 100:,.{decimals}f}%"


def fmt_rate(amount, currency: str = "USD") -> str:
    return f"{fmt_money(amount, currency, 2)}/1M"


# --- theme & css ----------------------------------------------------------
def inject_css(theme: str = "dark") -> None:
    c = colors(theme)
    is_dark = theme != "light"

    st.markdown(
        f"""
        <style>
          @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

          /* Global resets & typography */
          html, body, [class*="css"], .stApp {{
              font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
              color: {c['text']};
          }}

          .stApp {{
              background-color: {c['bg']};
              background-image: {
                  "radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0px, transparent 50%), "
                  "radial-gradient(at 100% 100%, rgba(167, 139, 250, 0.06) 0px, transparent 50%)"
                  if is_dark else
                  "radial-gradient(at 0% 0%, rgba(2, 132, 199, 0.04) 0px, transparent 50%), "
                  "radial-gradient(at 100% 100%, rgba(124, 58, 237, 0.03) 0px, transparent 50%)"
              };
              background-attachment: fixed;
          }}

          /* Sidebar Styling */
          section[data-testid="stSidebar"] {{
              background: {c['panel_solid']} !important;
              border-right: 1px solid {c['border']};
              box-shadow: { '4px 0 24px rgba(0, 0, 0, 0.35)' if is_dark else '4px 0 20px rgba(0, 0, 0, 0.03)' };
          }}
          section[data-testid="stSidebar"] h1 {{
              font-size: 1.25rem !important;
              font-weight: 800 !important;
              letter-spacing: -0.02em !important;
              background: { 'linear-gradient(135deg, #38bdf8 0%, #a78bfa 100%)' if is_dark else 'linear-gradient(135deg, #0284c7 0%, #7c3aed 100%)' };
              -webkit-background-clip: text;
              -webkit-text-fill-color: transparent;
              margin-bottom: 0.5rem !important;
          }}

          /* Headers & Hierarchy */
          h1, h2, h3, h4 {{
              font-family: 'Plus Jakarta Sans', sans-serif !important;
              font-weight: 700 !important;
              letter-spacing: -0.025em !important;
              color: {c['text_bright']} !important;
          }}
          h1 {{ font-size: 2.1rem !important; }}
          h2 {{ font-size: 1.45rem !important; margin-top: 1.2rem !important; }}
          h3 {{ font-size: 1.15rem !important; margin-top: 0.8rem !important; }}

          /* Monospace elements */
          code, pre, .font-mono, [data-testid="stMetricValue"] {{
              font-family: 'JetBrains Mono', monospace !important;
          }}

          /* Streamlit Default Metric Override */
          div[data-testid="stMetric"] {{
              background: {c['card_bg']};
              border: 1px solid {c['border']};
              border-radius: 12px;
              padding: 0.85rem 1rem;
              box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
              transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
          }}
          div[data-testid="stMetric"]:hover {{
              border-color: {c['border_highlight']};
              transform: translateY(-2px);
              box-shadow: 0 8px 24px rgba(56, 189, 248, 0.12);
          }}
          div[data-testid="stMetricLabel"] {{
              color: {c['muted']} !important;
              font-size: 0.78rem !important;
              font-weight: 600 !important;
              text-transform: uppercase !important;
              letter-spacing: 0.05em !important;
          }}
          div[data-testid="stMetricValue"] {{
              font-size: 1.55rem !important;
              font-weight: 700 !important;
              color: {c['text_bright']} !important;
              letter-spacing: -0.02em;
          }}

          /* Custom Telemetry Card (agy-kpi) */
          .agy-kpi {{
              background: {c['card_bg']};
              border: 1px solid {c['border']};
              border-radius: 14px;
              padding: 0.9rem 1.1rem;
              height: 100%;
              position: relative;
              overflow: hidden;
              box-shadow: { '0 4px 20px rgba(0, 0, 0, 0.25)' if is_dark else '0 2px 12px rgba(0, 0, 0, 0.04)' };
              transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.22s ease, box-shadow 0.22s ease;
          }}
          .agy-kpi::before {{
              content: '';
              position: absolute;
              top: 0; left: 0; right: 0;
              height: 2px;
              background: linear-gradient(90deg, {c['accent']}, transparent);
              opacity: 0.4;
              transition: opacity 0.2s ease;
          }}
          .agy-kpi:hover {{
              transform: translateY(-2px);
              border-color: {c['border_highlight']};
              box-shadow: 0 8px 30px rgba(56, 189, 248, 0.15);
          }}
          .agy-kpi:hover::before {{
              opacity: 1;
          }}
          .agy-kpi .lbl {{
              color: {c['muted']};
              font-size: 0.72rem;
              font-weight: 600;
              text-transform: uppercase;
              letter-spacing: 0.08em;
              margin-bottom: 0.35rem;
              display: flex;
              align-items: center;
              justify-content: space-between;
          }}
          .agy-kpi .val {{
              font-family: 'JetBrains Mono', monospace;
              font-size: 1.55rem;
              font-weight: 700;
              line-height: 1.15;
              color: {c['text_bright']};
              margin-bottom: 0.25rem;
              letter-spacing: -0.02em;
          }}
          .agy-kpi .sub {{
              color: {c['muted']};
              font-size: 0.76rem;
              font-weight: 500;
              display: flex;
              align-items: center;
              gap: 0.35rem;
          }}

          /* Telemetry HUD Top Header */
          .telemetry-hud {{
              background: {c['card_bg']};
              border: 1px solid {c['border']};
              border-radius: 14px;
              padding: 0.75rem 1.25rem;
              margin-bottom: 1.25rem;
              display: flex;
              flex-wrap: wrap;
              align-items: center;
              justify-content: space-between;
              gap: 0.75rem;
              box-shadow: { '0 4px 20px rgba(0, 0, 0, 0.3)' if is_dark else '0 2px 12px rgba(0, 0, 0, 0.04)' };
          }}
          .hud-badge {{
              display: inline-flex;
              align-items: center;
              gap: 0.45rem;
              background: rgba(56, 189, 248, 0.08);
              border: 1px solid rgba(56, 189, 248, 0.25);
              padding: 0.25rem 0.65rem;
              border-radius: 9999px;
              font-size: 0.74rem;
              font-weight: 600;
              color: {c['accent']};
          }}
          .hud-pulse {{
              width: 7px;
              height: 7px;
              border-radius: 50%;
              background: {c['cached']};
              box-shadow: 0 0 8px {c['cached']};
              animation: pulse-ring 2s infinite;
          }}
          @keyframes pulse-ring {{
              0% {{ transform: scale(0.95); opacity: 0.8; }}
              50% {{ transform: scale(1.3); opacity: 1; }}
              100% {{ transform: scale(0.95); opacity: 0.8; }}
          }}

          /* Callout Notes & Warnings */
          .agy-note {{
              border-left: 3px solid {c['accent']};
              background: { 'rgba(15, 23, 42, 0.65)' if is_dark else 'rgba(241, 245, 249, 0.8)' };
              border: 1px solid {c['border']};
              border-left: 3px solid {c['accent']};
              padding: 0.7rem 0.95rem;
              border-radius: 8px;
              color: {c['muted']};
              font-size: 0.84rem;
              line-height: 1.5;
              margin: 0.6rem 0;
              backdrop-filter: blur(8px);
          }}
          .agy-warn {{
              background: { 'rgba(30, 20, 10, 0.45)' if is_dark else 'rgba(254, 243, 199, 0.5)' };
              border: 1px solid rgba(245, 158, 11, 0.3);
              border-left: 3px solid {c['warn']};
              padding: 0.7rem 0.95rem;
              border-radius: 8px;
              color: { '#fcd34d' if is_dark else '#92400e' };
              font-size: 0.84rem;
              line-height: 1.5;
              margin: 0.6rem 0;
          }}

          /* Streamlit Tabs Customization */
          div[data-baseweb="tab-list"] {{
              gap: 0.5rem;
              background: { 'rgba(15, 23, 42, 0.45)' if is_dark else '#edf2f7' };
              padding: 0.3rem 0.4rem;
              border-radius: 10px;
              border: 1px solid {c['border']};
              margin-bottom: 1.1rem;
          }}
          button[data-baseweb="tab"] {{
              border-radius: 8px !important;
              padding: 0.45rem 1rem !important;
              font-size: 0.85rem !important;
              font-weight: 600 !important;
              color: {c['muted']} !important;
              border: none !important;
              background: transparent !important;
              transition: all 0.2s ease !important;
          }}
          button[data-baseweb="tab"]:hover {{
              color: {c['text_bright']} !important;
              background: { 'rgba(255, 255, 255, 0.05)' if is_dark else 'rgba(0, 0, 0, 0.04)' } !important;
          }}
          button[data-baseweb="tab"][aria-selected="true"] {{
              color: {c['text_bright']} !important;
              background: { 'rgba(56, 189, 248, 0.15)' if is_dark else '#ffffff' } !important;
              box-shadow: { '0 2px 10px rgba(0, 0, 0, 0.3)' if is_dark else '0 2px 8px rgba(0, 0, 0, 0.08)' } !important;
              border: 1px solid { 'rgba(56, 189, 248, 0.3)' if is_dark else 'rgba(2, 132, 199, 0.2)' } !important;
          }}

          /* Buttons styling */
          .stButton > button {{
              border-radius: 8px !important;
              font-weight: 600 !important;
              font-size: 0.85rem !important;
              padding: 0.45rem 1rem !important;
              border: 1px solid {c['border']} !important;
              transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
          }}
          .stButton > button:hover {{
              border-color: {c['accent']} !important;
              color: {c['accent']} !important;
              box-shadow: 0 4px 14px rgba(56, 189, 248, 0.18) !important;
              transform: translateY(-1px);
          }}
          .stDownloadButton > button {{
              border-radius: 8px !important;
              font-weight: 600 !important;
              border: 1px solid {c['border']} !important;
          }}

          /* Clean Dataframes */
          div[data-testid="stDataFrame"] {{
              border: 1px solid {c['border']};
              border-radius: 10px;
              overflow: hidden;
          }}

          /* Code & Badge chips */
          .agy-tag {{
              display: inline-block;
              border: 1px solid {c['border']};
              border-radius: 9999px;
              padding: 0.1rem 0.55rem;
              font-size: 0.72rem;
              font-weight: 600;
              color: {c['muted']};
              background: { 'rgba(255, 255, 255, 0.03)' if is_dark else 'rgba(0, 0, 0, 0.02)' };
              margin-right: 0.35rem;
          }}
          code {{
              color: {c['accent']} !important;
              background: { 'rgba(56, 189, 248, 0.08)' if is_dark else 'rgba(2, 132, 199, 0.08)' } !important;
              padding: 0.15rem 0.4rem !important;
              border-radius: 4px !important;
              font-size: 0.86em !important;
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _register_templates()


def _register_templates() -> None:
    for name, c, is_dark in (("agy_dark", DARK, True), ("agy_light", LIGHT, False)):
        if name in pio.templates:
            continue
        pio.templates[name] = go.layout.Template(layout=go.Layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans, sans-serif", color=c["text"], size=12),
            colorway=[c["fresh"], c["cached"], c["output"], c["cost"], c["warn"], c["bad"]],
            xaxis=dict(
                gridcolor=c["grid"],
                zeroline=False,
                linecolor=c["border"],
                tickfont=dict(family="JetBrains Mono, monospace", size=11),
            ),
            yaxis=dict(
                gridcolor=c["grid"],
                zeroline=False,
                linecolor=c["border"],
                tickfont=dict(family="JetBrains Mono, monospace", size=11),
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.03,
                x=0,
                font=dict(size=11),
            ),
            margin=dict(l=14, r=14, t=48, b=14),
            hoverlabel=dict(
                bgcolor=c["panel_solid"],
                bordercolor=c["border_highlight"] if is_dark else c["border"],
                font=dict(family="JetBrains Mono, monospace", color=c["text_bright"], size=12),
            ),
            hovermode="x unified",
        ))


def template_for(theme: str) -> str:
    return "agy_light" if theme == "light" else "agy_dark"


CHART_CONFIG = {
    "displaylogo": False,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {"format": "png", "scale": 2},
}


def show(fig: go.Figure, theme: str = "dark", height: int | None = None) -> None:
    """Render a figure with the bespoke app template and interactive chart config."""
    fig.update_layout(template=template_for(theme))
    if height:
        fig.update_layout(height=height)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)


def kpi(label: str, value: str, sub: str | None = None, icon: str | None = None,
        badge: str | None = None) -> str:
    icon_html = f'<span style="margin-right: 0.35rem;">{icon}</span>' if icon else ""
    badge_html = f'<span class="agy-tag" style="margin-left: auto;">{badge}</span>' if badge else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return (
        f'<div class="agy-kpi">'
        f'  <div class="lbl">{icon_html}{label}{badge_html}</div>'
        f'  <div class="val">{value}</div>'
        f'  {sub_html}'
        f'</div>'
    )


def kpi_row(items: list[tuple], per_row: int = 6) -> None:
    """items: (label, value, sub|None, icon|None, badge|None). Renders cards in clean grids."""
    for i in range(0, len(items), per_row):
        chunk = items[i:i + per_row]
        cols = st.columns(len(chunk))
        for col, item in zip(cols, chunk):
            label, value = item[0], item[1]
            sub = item[2] if len(item) > 2 else None
            icon = item[3] if len(item) > 3 else None
            badge = item[4] if len(item) > 4 else None
            col.markdown(kpi(label, value, sub, icon=icon, badge=badge), unsafe_allow_html=True)


def note(text: str, warn: bool = False) -> None:
    cls = "agy-warn" if warn else "agy-note"
    icon = "⚠️" if warn else "ℹ️"
    st.markdown(f'<div class="{cls}"><span style="margin-right: 0.4rem;">{icon}</span>{text}</div>',
                unsafe_allow_html=True)


def hud_header(title: str, subtitle: str, badges: list[tuple[str, str]] | None = None) -> None:
    """Render an aerospace-grade telemetry header."""
    badges_html = ""
    if badges:
        for text, color_style in badges:
            badges_html += f'<span class="hud-badge">{text}</span>'
    st.markdown(
        f"""
        <div class="telemetry-hud">
          <div style="display: flex; align-items: center; gap: 0.75rem;">
            <div class="hud-pulse"></div>
            <div>
              <div style="font-weight: 700; font-size: 1.05rem; letter-spacing: -0.01em;">{title}</div>
              <div style="font-size: 0.78rem; opacity: 0.75;">{subtitle}</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
            {badges_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# --- shared page context --------------------------------------------------
@dataclass
class Ctx:
    config: Config
    usage: UsageData            # full scan
    sessions: pd.DataFrame      # filtered
    daily: pd.DataFrame         # filtered
    catalog: Catalog
    prices: PriceEntry
    model_id: str
    price_note: str | None
    currency: str
    usd_inr: float
    subscription_amount: float
    theme: str
    overview: metrics.Overview
    runner: object              # jobs.JobRunner
    sqlite_path: str


def money(self: Ctx, amount_usd: float) -> str:
    return fmt_money(metrics.currency_from_usd(amount_usd, self.currency, self.usd_inr), self.currency)


Ctx.money = money  # type: ignore[attr-defined]


def build_ctx(*, config, usage, sessions, daily, catalog, prices, model_id, price_note,
              currency, usd_inr, subscription_amount, theme, runner) -> Ctx:
    overview = metrics.update_overview(
        sessions, daily, prices, currency=currency, usd_inr=usd_inr,
        subscription_amount=subscription_amount, model_name=prices.name, price_note=price_note,
    )
    return Ctx(config=config, usage=usage, sessions=sessions, daily=daily, catalog=catalog,
               prices=prices, model_id=model_id, price_note=price_note, currency=currency,
               usd_inr=usd_inr, subscription_amount=subscription_amount, theme=theme,
               overview=overview, runner=runner, sqlite_path=str(config.db_path))

