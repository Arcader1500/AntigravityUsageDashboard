"""Statistical analysis: baseline, bootstrap, Monte Carlo, trend, aggregation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from agy_dash import stats


def test_linear_forecast_on_flat_series_stays_flat():
    fc = stats.linear_forecast(np.full(10, 100.0), 5)
    assert fc.supported
    assert np.allclose(fc.per_day_median, 100.0, atol=1e-6)
    assert fc.cumulative_median == pytest.approx(500.0)


def test_linear_forecast_follows_an_established_slope():
    fc = stats.linear_forecast(np.arange(1, 11, dtype=float) * 10, 3)
    assert fc.per_day_median[0] == pytest.approx(110.0)  # next day after 10..100
    assert fc.per_day_median[-1] == pytest.approx(130.0)


def test_linear_growth_assumption_compounds_daily():
    flat = stats.linear_forecast(np.full(10, 100.0), 2, daily_growth=0.0)
    grown = stats.linear_forecast(np.full(10, 100.0), 2, daily_growth=0.10)
    assert grown.cumulative_median > flat.cumulative_median
    assert grown.per_day_median[1] == pytest.approx(100.0 * 1.1 ** 2, rel=1e-6)


def test_forecast_percentiles_are_ordered():
    for fc in (
        stats.bootstrap_forecast([1, 5, 50, 400, 900, 20_000, 3, 12], 10, seed=1),
        stats.monte_carlo_forecast([1, 5, 50, 400, 900, 20_000, 3, 12], 10, seed=1),
    ):
        assert np.all(fc.per_day_low <= fc.per_day_median + 1e-9)
        assert np.all(fc.per_day_median <= fc.per_day_high + 1e-9)
        assert fc.cumulative_low <= fc.cumulative_median <= fc.cumulative_high


def test_bootstrap_is_deterministic_for_a_seed():
    a = stats.bootstrap_forecast([10, 20, 30, 40], 5, seed=42)
    b = stats.bootstrap_forecast([10, 20, 30, 40], 5, seed=42)
    assert np.allclose(a.per_day_median, b.per_day_median)
    assert np.allclose(a.per_day_low, b.per_day_low)
    assert np.allclose(a.per_day_high, b.per_day_high)
    # any seed still yields a valid, ordered forecast
    c = stats.bootstrap_forecast([10, 20, 30, 40], 5, seed=7)
    assert np.all(c.per_day_low <= c.per_day_median) and np.all(c.per_day_median <= c.per_day_high)


def test_bootstrap_cannot_exceed_the_observed_maximum():
    values = [10, 20, 30, 40]
    fc = stats.bootstrap_forecast(values, 20, seed=3)
    assert fc.per_day_high.max() <= max(values) + 1e-9


def test_monte_carlo_drift_raises_the_forecast():
    values = np.array([100.0] * 10)
    flat = stats.monte_carlo_forecast(values, 10, growth_mean=0.0, seed=5)
    up = stats.monte_carlo_forecast(values, 10, growth_mean=0.05, seed=5)
    assert up.cumulative_median > flat.cumulative_median


def test_monte_carlo_output_is_never_negative():
    fc = stats.monte_carlo_forecast([5, 10, 3, 0, 40], 30, growth_sd=1.5, seed=2)
    assert float(np.min(fc.per_day_low)) >= 0.0


def test_holt_requires_enough_days():
    short = stats.holt_forecast(np.arange(5, dtype=float), 5)
    assert not short.supported and short.horizon_days == 0
    long = stats.holt_forecast(np.arange(1, 21, dtype=float), 3)
    assert long.supported and long.horizon_days == 3


def test_run_forecast_dispatches_by_name():
    fc = stats.run_forecast("Bootstrap resampling", [1, 2, 3, 4, 5], 4, seed=1)
    assert fc.method == "Bootstrap resampling"
    unknown = stats.run_forecast("nonsense", [1, 2, 3, 4, 5], 4)
    assert unknown.method.startswith("Linear")


def test_forecast_refuses_empty_input():
    for fn in (stats.linear_forecast, stats.bootstrap_forecast, stats.monte_carlo_forecast):
        fc = fn([], 10)
        assert not fc.supported and fc.horizon_days == 0


def test_future_dates_start_after_the_last_observed_day():
    fc = stats.linear_forecast(np.arange(5, dtype=float), 3, last_date=pd.Timestamp("2026-10-16"))
    assert fc.dates[0] == pd.Timestamp("2026-10-17")
    assert len(fc.dates) == 3


def test_observed_series_fills_missing_calendar_days(usage):
    s = stats.observed_series(usage.daily, "total")
    assert len(s) == 11  # 2026-10-05 .. 2026-10-15 inclusive
    assert s["total"].iloc[0] == usage.daily["total"].iloc[0]
    assert (s["total"] == 0).sum() > 0  # gap days are zero, not skipped


def test_uncertainty_note_warns_on_short_windows():
    assert "not a forecast" in stats.uncertainty_note(3)
    assert "short window" in stats.uncertainty_note(10)
    assert "trend model is enabled" in stats.uncertainty_note(20)


def test_aggregation_preserves_totals(usage):
    daily_total = int(usage.daily["total"].sum())
    for freq in ("weekly", "monthly"):
        agg = stats.aggregate(usage.daily, freq)
        assert int(agg["total"].sum()) == daily_total
    assert len(stats.aggregate(usage.daily, "daily")) == len(usage.daily)


def test_aggregation_handles_empty_frame():
    empty = pd.DataFrame(columns=["date", "calls", "sessions", "fresh_in", "cached", "output", "total"])
    assert stats.aggregate(empty, "weekly").empty
