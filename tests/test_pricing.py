"""Pricing catalog: dated versioning, historical assumptions, currency."""

from __future__ import annotations

import json

import pytest

from agy_dash import pricing


def test_catalog_has_models_for_every_family_in_the_brief():
    ids = set(pricing.models())
    for expected in ("gemini-3.8-flash", "gemini-4-argon", "claude-haiku", "claude-sonnet",
                     "claude-opus", "gpt-mini", "gpt-flagship", "llama-70b-api",
                     "deepseek-v3-api"):
        assert expected in ids


def test_prices_are_keyed_by_token_category():
    entry = pricing.Catalog().latest("claude-sonnet")
    assert entry.input_usd > 0 and entry.cached_usd > 0 and entry.output_usd > 0
    # cached reads are cheaper than fresh input for cache-capable providers
    assert entry.cached_usd < entry.input_usd


def test_price_on_selects_the_version_covering_the_date():
    cat = pricing.Catalog()
    intro, est = cat.price_on("gemini-3.8-flash", "2026-10-16")
    assert (intro.input_usd, intro.cached_usd, intro.output_usd) == (0.75, 0.075, 3.75)
    assert est is False

    later, est2 = cat.price_on("gemini-3.8-flash", "2027-06-01")
    assert (later.input_usd, later.output_usd) == (1.50, 7.50)  # documented doubling
    assert est2 is False


def test_historical_period_is_never_silently_priced_with_todays_rate():
    cat = pricing.Catalog()
    entry, is_estimate = cat.price_on("gemini-3.1-pro", "2026-06-01")  # before its first version
    assert is_estimate is True
    assert entry.effective_from == "2026-09-01"
    assert cat.availability_warning("gemini-3.1-pro", "2026-06-01") is not None
    assert cat.availability_warning("gemini-3.1-pro", "2026-10-16") is None


def test_unknown_model_returns_no_price():
    entry, is_estimate = pricing.Catalog().price_on("does-not-exist", "2026-10-16")
    assert entry is None and is_estimate is True
    assert pricing.Catalog().availability_warning("does-not-exist") is not None


def test_explicit_date_range_is_respected():
    e = pricing.PriceEntry("m", "M", "V", "2026-10-01", "2026-12-31", 1, 0.1, 2)
    assert e.covers("2026-10-01") and e.covers("2026-12-31")
    assert not e.covers("2026-09-30") and not e.covers("2027-01-01")
    open_ended = pricing.PriceEntry("m", "M", "V", "2026-10-01", None, 1, 0.1, 2)
    assert open_ended.covers("2099-01-01")


def test_catalog_file_overrides_the_builtin(tmp_path):
    path = tmp_path / "pricing.json"
    path.write_text(json.dumps({"models": [{
        "model_id": "custom", "name": "Custom", "vendor": "V",
        "effective_from": "2026-01-01", "effective_until": None,
        "input_usd": 1.0, "cached_usd": 0.1, "output_usd": 2.0,
    }]}), encoding="utf-8")
    entries = pricing.load_catalog(path)
    assert [e.model_id for e in entries] == ["custom"]
    assert pricing.load_catalog(tmp_path / "missing.json")[0].model_id == "gemini-3.8-flash"


def test_broken_catalog_file_falls_back_instead_of_crashing(tmp_path):
    path = tmp_path / "pricing.json"
    path.write_text("{not json", encoding="utf-8")
    assert pricing.load_catalog(path)[0].model_id == "gemini-3.8-flash"


def test_versions_are_sorted_by_effective_date():
    cat = pricing.Catalog()
    vs = cat.versions("gemini-3.8-flash")
    assert [v.effective_from for v in vs] == sorted(v.effective_from for v in vs)
