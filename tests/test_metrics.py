"""Core calculation tests: totals, costs, conversion, subscription metrics, bad data."""

from __future__ import annotations

import pandas as pd
import pytest

from agy_dash import metrics, pricing
from tests.conftest import DOC_SNAPSHOT

FLASH = pricing.PriceEntry(
    model_id="gemini-3.8-flash", name="Gemini 3.8 Flash", vendor="Google",
    effective_from="2026-10-01", effective_until="2026-12-31",
    input_usd=0.75, cached_usd=0.075, output_usd=3.75, verified=True,
)


# --- token totals ---------------------------------------------------------
def test_total_tokens_is_sum_of_categories():
    assert metrics.total_tokens(1000, 2000, 500) == 3500


def test_total_tokens_treats_none_as_zero():
    assert metrics.total_tokens(None, 2000, None) == 2000


def test_totals_from_daily_sums_categories_and_does_not_sum_sessions(usage):
    t = metrics.totals_from_daily(usage.daily)
    assert t.fresh_in == 396_400 + 10_400_000 + 9_900_000
    assert t.cached == 889_400 + 120_200_000 + 105_600_000
    assert t.output == 17_700 + 580_600 + 964_800
    assert t.total == t.fresh_in + t.cached + t.output
    assert t.calls == 41 + 1174 + 1430
    assert t.active_days == 3
    assert t.sessions == 0  # per-day distinct counts must not be summed


def test_stock_totals_uses_real_session_count(usage):
    t = metrics.stock_totals(usage.sessions, usage.daily)
    assert t.sessions == 4


# --- cost -----------------------------------------------------------------
def test_api_cost_matches_hand_verified_october_5_row():
    # doc section 3: Oct 5 -> 396.4K x 0.75 + 889.4K x 0.075 + 17.7K x 3.75 ~= $0.43
    cost = metrics.api_cost_usd(396_400, 889_400, 17_700, FLASH)
    assert cost == pytest.approx(0.43, abs=0.01)


def test_cost_breakdown_categories_sum_to_total():
    b = metrics.cost_breakdown_usd(1_000_000, 10_000_000, 100_000, FLASH)
    assert b["total"] == pytest.approx(b["fresh_in"] + b["cached"] + b["output"])
    assert b["fresh_in"] == pytest.approx(0.75)
    assert b["cached"] == pytest.approx(0.75)
    assert b["output"] == pytest.approx(0.375)


def test_doc_snapshot_cost_is_reproduced_within_rounding():
    """The doc's 55.0M/631.6M/3.9M figures were humanized, so allow rounding slack."""
    cost = metrics.api_cost_usd(DOC_SNAPSHOT["fresh_in"], DOC_SNAPSHOT["cached"],
                                DOC_SNAPSHOT["output"], FLASH)
    assert cost == pytest.approx(DOC_SNAPSHOT["cost_usd"], abs=0.6)
    total = metrics.total_tokens(DOC_SNAPSHOT["fresh_in"], DOC_SNAPSHOT["cached"],
                                 DOC_SNAPSHOT["output"])
    assert total == pytest.approx(DOC_SNAPSHOT["total"], rel=0.01)


def test_blended_rate_is_cost_per_million_tokens():
    # 1M fresh + 1M cached + 1M output at 0.75/0.075/3.75 = $4.575 over 3M tokens
    cost = metrics.api_cost_usd(1_000_000, 1_000_000, 1_000_000, FLASH)
    assert metrics.blended_rate_usd_per_mtok(cost, 3_000_000) == pytest.approx(1.525)


def test_blended_rate_safe_on_zero_tokens():
    assert metrics.blended_rate_usd_per_mtok(10.0, 0) == 0.0


# --- subscription metrics -------------------------------------------------
def test_tokens_per_currency_uses_actual_spend_only():
    assert metrics.tokens_per_currency(1_000_000, 2000) == pytest.approx(500.0)


def test_tokens_per_currency_is_zero_when_no_spend_configured():
    assert metrics.tokens_per_currency(1_000_000, 0) == 0.0


def test_currency_conversion_direction():
    assert metrics.usd_to(10.0, 88.0) == pytest.approx(880.0)
    assert metrics.currency_from_usd(10.0, "INR", 88.0) == pytest.approx(880.0)
    assert metrics.currency_from_usd(10.0, "USD", 88.0) == pytest.approx(10.0)


def test_update_overview_separates_subscription_from_api_cost(usage):
    o = metrics.update_overview(usage.sessions, usage.daily, FLASH, currency="INR",
                                usd_inr=88.0, subscription_amount=8800.0)
    assert o.subscription_spend == 8800.0
    assert o.subscription_spend_usd == pytest.approx(100.0)
    assert o.api_cost_usd > 0
    # the two are reported independently; neither is derived from the other
    assert o.tokens_per_currency_spent == pytest.approx(o.totals.total / 8800.0)
    assert o.cost_per_mtok_in_currency == pytest.approx(o.blended_rate_usd_per_mtok * 88.0)


# --- cache / ratios -------------------------------------------------------
def test_cache_hit_rate():
    assert metrics.cache_hit_rate(1_000, 9_000) == pytest.approx(0.9)
    assert metrics.cache_hit_rate(0, 0) == 0.0
    assert metrics.cache_hit_rate(5_000, 5_000) == pytest.approx(0.5)


def test_safe_div_never_raises_or_returns_nan():
    assert metrics.safe_div(5, 0) == 0.0
    assert metrics.safe_div(5, 0, default=-1) == -1
    assert metrics.safe_div(float("nan"), 5) == 0.0


# --- hypothetical workload ------------------------------------------------
def test_hypothetical_cached_ratio_preserves_prompt_total():
    t = metrics.hypothetical_tokens(4_000_000, 6_000_000, 1_000_000, cached_ratio=0.5)
    assert t["cached"] == pytest.approx(5_000_000)
    assert t["fresh_in"] == pytest.approx(5_000_000)
    assert t["output"] == pytest.approx(1_000_000)


def test_hypothetical_output_multiplier():
    t = metrics.hypothetical_tokens(1_000, 2_000, 1_000, output_multiplier=2.5)
    assert t["output"] == pytest.approx(2500)
    assert t["fresh_in"] == 1000 and t["cached"] == 2000


def test_hypothetical_ratio_is_clamped():
    assert metrics.hypothetical_tokens(1_000, 0, 0, cached_ratio=5.0)["cached"] == pytest.approx(1000)
    assert metrics.hypothetical_tokens(1_000, 0, 0, cached_ratio=-2.0)["cached"] == pytest.approx(0)


# --- model comparison / consistency --------------------------------------
def test_compare_models_prices_identical_token_bundle():
    token = {"fresh_in": 1_000_000, "cached": 0, "output": 0}
    cat = pricing.Catalog([
        FLASH,
        pricing.PriceEntry("claude-opus", "Claude Opus", "Anthropic", "2026-01-01", None,
                           15.0, 1.5, 75.0),
    ])
    df = metrics.compare_models(token, cat, ["gemini-3.8-flash", "claude-opus"], on="2026-10-16")
    assert list(df["model_id"]) == ["gemini-3.8-flash", "claude-opus"]  # cheapest first
    assert df["cost_usd"].iloc[0] == pytest.approx(0.75)
    assert df["cost_usd"].iloc[1] == pytest.approx(15.0)
    assert df["estimate"].sum() == 0


def test_compare_models_flags_estimate_only_when_no_version_covers_the_date():
    token = {"fresh_in": 1000, "cached": 0, "output": 0}
    cat = pricing.Catalog([FLASH])
    # date before every known version -> closest (earliest) version, flagged as an estimate
    df = metrics.compare_models(token, cat, ["gemini-3.8-flash"], on="2026-09-01")
    assert bool(df["estimate"].iloc[0]) is True
    # date after the only version -> newest older version, also an estimate, never a silent guess
    df2 = metrics.compare_models(token, cat, ["gemini-3.8-flash"], on="2027-05-05")
    assert bool(df2["estimate"].iloc[0]) is True
    # covered date -> exact
    df3 = metrics.compare_models(token, cat, ["gemini-3.8-flash"], on="2026-10-16")
    assert bool(df3["estimate"].iloc[0]) is False


def test_verify_consistency_passes_on_balanced_fixture(usage):
    assert metrics.verify_consistency(usage.sessions, usage.daily) == []


def test_verify_consistency_reports_broken_totals_instead_of_correcting(usage):
    daily = usage.daily.copy()
    daily.loc[0, "total"] = daily.loc[0, "total"] + 12345
    issues = metrics.verify_consistency(usage.sessions, daily)
    assert any("!=" in i for i in issues)


def test_verify_consistency_reports_session_daily_mismatch(usage):
    sessions = usage.sessions.iloc[:-1]
    issues = metrics.verify_consistency(sessions, usage.daily)
    assert any("session total" in i for i in issues)


def test_attach_costs_adds_expected_columns(usage):
    d = metrics.attach_costs(usage.daily, FLASH)
    for col in ("cost_usd", "cost_fresh_usd", "cost_cached_usd", "cost_output_usd",
                "cumulative_cost_usd"):
        assert col in d.columns
    assert d["cumulative_cost_usd"].iloc[-1] == pytest.approx(d["cost_usd"].sum())


def test_best_worst_days_use_full_days_only(usage):
    bw = metrics.best_worst_days(usage.daily, FLASH, n=1)
    assert bw["best"]["date"].iloc[0] == pd.Timestamp("2026-10-08")
    assert bw["worst"]["date"].iloc[0] == pd.Timestamp("2026-10-05")


def test_empty_frames_are_handled():
    empty = pd.DataFrame(columns=["date", "calls", "sessions", "fresh_in", "cached", "output", "total"])
    assert metrics.totals_from_daily(empty).total == 0
    assert metrics.stock_totals(empty, empty).sessions == 0
    assert metrics.best_worst_days(empty, FLASH)["best"].empty
