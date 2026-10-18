import datetime as dt
from pathlib import Path
import pandas as pd
import pytest

from agy_dash import config as cfgmod
from agy_dash import deep, pricing, source
from agy_dash.ui import common, state


def test_ttl_cache_returns_cached_or_recomputes():
    c = state.TTLCache(ttl_seconds=60)
    cnt = 0

    def compute():
        nonlocal cnt
        cnt += 1
        return "val"

    assert c.get("k", compute) == "val"
    assert cnt == 1
    assert c.get("k", compute) == "val"
    assert cnt == 1
    c.clear()
    assert c.get("k", compute) == "val"
    assert cnt == 2


def test_ttl_cache_expires_after_ttl(monkeypatch):
    c = state.TTLCache(ttl_seconds=10)
    current_time = 1000.0

    def mock_monotonic():
        return current_time

    monkeypatch.setattr(state.time, "monotonic", mock_monotonic)
    cnt = 0

    def compute():
        nonlocal cnt
        cnt += 1
        return f"val_{cnt}"

    assert c.get("k", compute) == "val_1"
    assert cnt == 1

    current_time = 1005.0
    assert c.get("k", compute) == "val_1"
    assert cnt == 1

    current_time = 1011.0
    assert c.get("k", compute) == "val_2"
    assert cnt == 2


def test_parse_filters_handles_currency_and_clamps():
    cfg = cfgmod.get_config()
    dates = pd.date_range("2026-10-05", "2026-10-15")
    daily = pd.DataFrame({"date": dates})
    usage = source.UsageData(pd.DataFrame(), daily, dt.datetime.now(), "/root", [])

    # Check currency parsing and defaults
    f = state.parse_filters({"currency": "usd", "start": "2026-10-08", "end": "2026-10-12"}, cfg, usage, ["claude-sonnet"])
    assert f.currency == "USD"
    assert f.start == dt.date(2026, 10, 8)
    assert f.end == dt.date(2026, 10, 12)

    # Clamping test
    f_clamped = state.parse_filters({"start": "2026-10-20", "end": "2026-10-01"}, cfg, usage, ["claude-sonnet"])
    assert f_clamped.start == dt.date(2026, 10, 5)
    assert f_clamped.end == dt.date(2026, 10, 15)


def test_parse_filters_defaults_and_fallbacks():
    cfg = cfgmod.get_config()
    empty_usage = source.UsageData(pd.DataFrame(), pd.DataFrame(), dt.datetime.now(), "/root", [])

    # Empty usage dataframe, invalid/empty query
    f = state.parse_filters({}, cfg, empty_usage, ["claude-sonnet", "gemini-flash"])
    assert f.view == "command"
    assert f.start is None
    assert f.end is None
    assert f.model_id == "claude-sonnet"
    assert f.currency == cfg.reporting_currency
    assert f.fx == cfg.usd_to_inr
    assert f.sub == float(cfg.subscription.get("amount", 0.0))
    assert f.theme == "dark"

    # Fallback to first model if DEFAULT_MODEL is absent
    f_other = state.parse_filters({}, cfg, empty_usage, ["custom-model", "other-model"])
    assert f_other.model_id == "custom-model"

    # Fallback when model list is empty
    f_no_models = state.parse_filters({}, cfg, empty_usage, [])
    assert f_no_models.model_id == ""

    # Invalid query inputs fall back cleanly
    f_invalid = state.parse_filters(
        {"view": "nonexistent", "currency": "JPY", "theme": "neon", "fx": "invalid", "sub": "-10"},
        cfg, empty_usage, ["claude-sonnet"],
    )
    assert f_invalid.view == "command"
    assert f_invalid.currency == cfg.reporting_currency
    assert f_invalid.theme == "dark"
    assert f_invalid.fx == cfg.usd_to_inr
    assert f_invalid.sub == 0.0  # max(float("-10"), 0.0) -> 0.0


def test_clear_all_caches():
    state.USAGE_CACHE.get("test_u", lambda: "val_u")
    state.DEEP_CACHE.get("test_d", lambda: "val_d")
    assert "test_u" in state.USAGE_CACHE._entries
    assert "test_d" in state.DEEP_CACHE._entries

    state.clear_all_caches()
    assert len(state.USAGE_CACHE._entries) == 0
    assert len(state.DEEP_CACHE._entries) == 0


def test_get_runner_caches_by_log_dir(tmp_path):
    cfg = cfgmod.Config(data={
        "python_executable": "py",
        "extractor_script": str(tmp_path / "script.py"),
        "log_dir": str(tmp_path / "logs"),
        "brain_root": str(tmp_path / "brain"),
    })
    r1 = state.get_runner(cfg)
    r2 = state.get_runner(cfg)
    assert r1 is r2


def test_load_usage_and_deep_caches(monkeypatch, tmp_path):
    state.clear_all_caches()
    cfg = cfgmod.Config(data={
        "brain_root": str(tmp_path / "brain"),
        "extractor_script": str(tmp_path / "script.py"),
        "log_dir": str(tmp_path / "logs"),
    })

    scan_called = 0
    def fake_scan(root, extractor):
        nonlocal scan_called
        scan_called += 1
        return source.UsageData(pd.DataFrame(), pd.DataFrame(), dt.datetime.now(), str(root), [])

    monkeypatch.setattr(source, "scan_usage", fake_scan)
    u1 = state.load_usage(cfg)
    u2 = state.load_usage(cfg)
    assert u1 is u2
    assert scan_called == 1

    deep_called = 0
    sentinel_deep = object()
    def fake_deep(root):
        nonlocal deep_called
        deep_called += 1
        return sentinel_deep

    monkeypatch.setattr(deep, "scan_deep", fake_deep)
    d1 = state.load_deep(str(tmp_path / "brain"))
    d2 = state.load_deep(str(tmp_path / "brain"))
    assert d1 is sentinel_deep
    assert d2 is sentinel_deep
    assert deep_called == 1


def test_load_catalog():
    entries = state.load_catalog()
    assert isinstance(entries, list)
    assert len(entries) > 0
    assert any(e.model_id == "claude-sonnet" for e in entries)


def test_build_context_success_and_pricing_error():
    cfg = cfgmod.get_config()
    dates = pd.date_range("2026-10-05", "2026-10-15")
    daily = pd.DataFrame({
        "date": dates,
        "calls": [1] * len(dates),
        "sessions": [1] * len(dates),
        "fresh_in": [100] * len(dates),
        "cached": [50] * len(dates),
        "output": [25] * len(dates),
        "total": [175] * len(dates),
    })
    sessions = pd.DataFrame({
        "session_id": ["s1"],
        "label": ["s1"],
        "kind": ["main"],
        "calls": [11],
        "fresh_in": [1100],
        "cached": [550],
        "output": [275],
        "total": [1925],
        "first_utc": [None],
        "last_utc": [None],
        "first_date": ["2026-10-05"],
        "last_date": ["2026-10-15"],
    })
    usage = source.UsageData(sessions, daily, dt.datetime.now(), "/root", [])
    entries = pricing.default_catalog()

    f = state.parse_filters({"model": "claude-sonnet"}, cfg, usage, ["claude-sonnet"])
    ctx = state.build_context(cfg, usage, entries, f, runner=None)
    assert isinstance(ctx, common.Ctx)
    assert ctx.model_id == "claude-sonnet"
    assert len(ctx.daily) == 11
    assert len(ctx.sessions) == 1

    # PricingError on unknown model
    f_bad = state.FilterParams(
        view="command", start=None, end=None, model_id="unknown-super-ai",
        currency="USD", fx=88.0, sub=0.0, theme="dark",
    )
    with pytest.raises(state.PricingError, match="No pricing entry for model 'unknown-super-ai'"):
        state.build_context(cfg, usage, entries, f_bad, runner=None)
