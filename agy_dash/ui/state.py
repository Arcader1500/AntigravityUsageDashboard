"""Stateless request-level state parsing, TTLCache, and Ctx builder."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from .. import config as cfgmod
from .. import deep, jobs, pricing, source
from . import common

VIEWS = ("command", "sessions", "economics")
THEMES = ("dark", "light")
CURRENCIES = ("INR", "USD", "EUR", "GBP")
DEFAULT_MODEL = "claude-sonnet"


class PricingError(Exception):
    """Raised when the selected model cannot be priced."""


class TTLCache:
    def __init__(self, ttl_seconds: float = 60.0):
        self.ttl = ttl_seconds
        self._entries: dict[str, tuple[float, Any]] = {}

    def get(self, key: str, factory: Callable[[], Any]) -> Any:
        now = time.monotonic()
        if key in self._entries:
            ts, val = self._entries[key]
            if now - ts < self.ttl:
                return val
        val = factory()
        self._entries[key] = (now, val)
        return val

    def clear(self) -> None:
        self._entries.clear()


USAGE_CACHE = TTLCache(ttl_seconds=60.0)
DEEP_CACHE = TTLCache(ttl_seconds=300.0)
_RUNNERS: dict[str, jobs.JobRunner] = {}


def clear_all_caches() -> None:
    USAGE_CACHE.clear()
    DEEP_CACHE.clear()


def get_runner(cfg: cfgmod.Config) -> jobs.JobRunner:
    key = str(Path(cfg.log_dir).resolve())
    if key not in _RUNNERS:
        _RUNNERS[key] = jobs.JobRunner(
            script_path=cfg.extractor_script,
            python_executable=cfg.python_executable,
            log_dir=cfg.log_dir,
            last_run_path=Path(cfg.log_dir) / "last_run.json",
            lock_path=Path(cfg.log_dir) / "extractor.lock",
        )
    return _RUNNERS[key]


def load_usage(cfg: cfgmod.Config) -> source.UsageData:
    key = f"{cfg.brain_root}:{cfg.extractor_script}"
    loader = getattr(source, "load_usage", None)
    if not callable(loader):
        loader = lambda c: source.scan_usage(c.brain_root, c.extractor_script)
    return USAGE_CACHE.get(key, lambda: loader(cfg))


def load_deep(brain_root: str | Path) -> deep.DeepData:
    root_str = str(brain_root)
    return DEEP_CACHE.get(root_str, lambda: deep.scan_deep(Path(brain_root)))


def load_catalog() -> list[pricing.PriceEntry]:
    pricing_file = getattr(pricing, "pricing_file", None)
    if callable(pricing_file):
        return pricing.load_catalog(pricing_file())
    return pricing.load_catalog()


@dataclass
class FilterParams:
    view: str
    start: dt.date | None
    end: dt.date | None
    model_id: str
    currency: str
    fx: float
    sub: float
    theme: str


def _parse_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s).strip())
    except (ValueError, TypeError):
        return None


def parse_filters(query: dict[str, Any], cfg: cfgmod.Config, usage: source.UsageData, model_ids: list[str]) -> FilterParams:
    daily = usage.daily
    lo = daily["date"].min().date() if not daily.empty else None
    hi = daily["date"].max().date() if not daily.empty else None
    start = _parse_date(query.get("start")) or lo
    end = _parse_date(query.get("end")) or hi
    if lo is not None and start is not None and end is not None:
        start = min(max(start, lo), hi)
        end = min(max(end, lo), hi)
        if start > end:
            start, end = end, start

    default_model = DEFAULT_MODEL if DEFAULT_MODEL in model_ids else (model_ids[0] if model_ids else "")
    model = query.get("model")
    view = query.get("view")
    theme = query.get("theme")
    curr = str(query.get("currency", "")).upper()
    currency = curr if curr in CURRENCIES else cfg.reporting_currency

    def _f(v, d):
        try:
            return max(float(v), 0.0) if v is not None else d
        except (ValueError, TypeError):
            return d

    return FilterParams(
        view=view if view in VIEWS else "command",
        start=start,
        end=end,
        model_id=model if model in model_ids else default_model,
        currency=currency,
        fx=_f(query.get("fx"), cfg.usd_to_inr),
        sub=_f(query.get("sub"), float(cfg.subscription.get("amount", 0.0))),
        theme=theme if theme in THEMES else "dark",
    )


def build_context(cfg: cfgmod.Config, usage: source.UsageData, entries: list[pricing.PriceEntry],
                  filters: FilterParams, runner: Any) -> common.Ctx:
    daily = source.clip_dates(usage.daily, filters.start, filters.end)
    sessions = source.sessions_touching(usage.sessions, filters.start, filters.end)
    catalog = pricing.Catalog(entries)
    on_date = daily["date"].max().date() if not daily.empty else None
    prices, estimate = catalog.price_on(filters.model_id, on_date)
    if prices is None:
        raise PricingError(f"No pricing entry for model '{filters.model_id}'.")
    price_note = None
    if estimate:
        price_note = (f"No price version covers {on_date} for {prices.name}; using the "
                      f"{prices.effective_from} version as an ESTIMATE. Prices are dated - add a "
                      "version in config/pricing.json to be exact." if on_date
                      else catalog.availability_warning(filters.model_id, on_date))
    return common.build_ctx(
        config=cfg, usage=usage, sessions=sessions, daily=daily, catalog=catalog, prices=prices,
        model_id=filters.model_id, price_note=price_note, currency=filters.currency,
        usd_inr=filters.fx, subscription_amount=filters.sub, theme=filters.theme, runner=runner,
    )
