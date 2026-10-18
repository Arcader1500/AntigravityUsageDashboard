"""Theme, formatting, and the shared request context. Framework-free."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .. import metrics, pricing, source
from ..config import Config

DARK = {
    "bg": "#090A0F",
    "panel": "#10121A",
    "panel_solid": "#10121A",
    "panel_alt": "#161922",
    "border": "#1E2230",
    "border_highlight": "rgba(56, 189, 248, 0.4)",
    "text": "#F1F5F9",
    "text_bright": "#FFFFFF",
    "muted": "#94A3B8",
    "dim": "#64748B",
    "accent": "#38BDF8",     # Cyan
    "fresh": "#38BDF8",      # Fresh input tokens
    "cached": "#10B981",     # Cached tokens (Emerald)
    "output": "#F59E0B",     # Output & thinking tokens (Amber)
    "cost": "#A78BFA",       # Cost burn (Violet)
    "warn": "#FBBF24",       # Warning notice
    "bad": "#F43F5E",        # Error / friction (Rose)
    "grid": "rgba(255, 255, 255, 0.05)",
}

LIGHT = {
    "bg": "#F6F7F9",
    "panel": "#FFFFFF",
    "panel_solid": "#FFFFFF",
    "panel_alt": "#F1F4F8",
    "border": "#E2E8F0",
    "border_highlight": "rgba(2, 132, 199, 0.4)",
    "text": "#0F172A",
    "text_bright": "#020617",
    "muted": "#64748B",
    "dim": "#94A3B8",
    "accent": "#0284C7",
    "fresh": "#0284C7",
    "cached": "#059669",
    "output": "#D97706",
    "cost": "#7C3AED",
    "warn": "#B45309",
    "bad": "#E11D48",
    "grid": "rgba(0, 0, 0, 0.05)",
}

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}


def colors(theme: str) -> dict[str, str]:
    return LIGHT if str(theme).lower() == "light" else DARK


def currency_symbol(curr: str) -> str:
    return CURRENCY_SYMBOLS.get(curr.upper(), f"{curr} ")


def fmt_tokens(n: float | int | None) -> str:
    if n is None:
        return "-"
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.2f}B"
    if n >= 1e6:
        return f"{n / 1e6:.2f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K" if n < 1e5 else f"{n / 1e3:.0f}K"
    return f"{int(n):,}"


def fmt_money(val: float | None, curr: str = "INR") -> str:
    if val is None:
        return "-"
    sym = currency_symbol(curr)
    return f"{sym}{val:,.2f}"


def fmt_rate(val: float | None, curr: str = "INR") -> str:
    if val is None:
        return "-"
    sym = currency_symbol(curr)
    return f"{sym}{val:,.4f}/Mtok"


def fmt_pct(val: float | None, decimals: int = 1) -> str:
    if val is None:
        return "-"
    return f"{val * 100:.{decimals}f}%"


@dataclass
class Ctx:
    config: Config
    usage: source.UsageData
    sessions: pd.DataFrame
    daily: pd.DataFrame
    catalog: pricing.Catalog
    prices: pricing.PriceEntry
    model_id: str
    price_note: str | None
    currency: str
    usd_inr: float
    subscription_amount: float
    theme: str
    runner: Any
    overview: metrics.Overview

    def to_currency(self, usd: float) -> float:
        return metrics.currency_from_usd(usd, self.currency, self.usd_inr)

    def money(self, usd: float) -> str:
        return fmt_money(self.to_currency(usd), self.currency)


def build_ctx(
    config: Config,
    usage: source.UsageData,
    sessions: pd.DataFrame,
    daily: pd.DataFrame,
    catalog: pricing.Catalog,
    prices: pricing.PriceEntry,
    model_id: str,
    price_note: str | None,
    currency: str,
    usd_inr: float,
    subscription_amount: float,
    theme: str,
    runner: Any,
) -> Ctx:
    overview = metrics.update_overview(
        sessions, daily, prices,
        currency=currency, usd_inr=usd_inr,
        subscription_amount=subscription_amount,
        model_name=prices.name, price_note=price_note,
    )
    return Ctx(
        config=config, usage=usage, sessions=sessions, daily=daily,
        catalog=catalog, prices=prices, model_id=model_id, price_note=price_note,
        currency=currency, usd_inr=usd_inr, subscription_amount=subscription_amount,
        theme=theme, runner=runner, overview=overview,
    )
