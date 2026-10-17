"""Statistical analysis: baseline extrapolation, bootstrap, Monte Carlo, and an
optional trend model - all in numpy, no extra dependency.

Every method returns its own assumptions so the UI can print them. Nothing here
decides how to display results; it never labels a modelled value as measured.

Honest limitation, stated once: with ~10 observed days, any of these methods can
describe the *shape* of the last few days, but none of them establishes what
happened or will happen over months. `uncertainty_note()` says so in words.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MIN_DAYS_FOR_TREND = 14


@dataclass
class Forecast:
    method: str
    horizon_days: int
    dates: list[pd.Timestamp]
    per_day_low: np.ndarray
    per_day_median: np.ndarray
    per_day_high: np.ndarray
    observed_days: int
    observed_mean: float
    assumptions: str
    supported: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def cumulative_low(self) -> float:
        return float(np.sum(self.per_day_low))

    @property
    def cumulative_median(self) -> float:
        return float(np.sum(self.per_day_median))

    @property
    def cumulative_high(self) -> float:
        return float(np.sum(self.per_day_high))

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame({
            "date": self.dates,
            "low": self.per_day_low,
            "median": self.per_day_median,
            "high": self.per_day_high,
        })


def uncertainty_note(observed_days: int) -> str:
    if observed_days < 7:
        return (f"Only {observed_days} observed day(s). Treat every number below as an illustration, "
                "not a forecast.")
    if observed_days < MIN_DAYS_FOR_TREND:
        return (f"{observed_days} observed days is a short window: it is enough to describe the recent "
                f"routine, not to establish months of behaviour. Extrapolating more than ~2x the "
                f"observed window ({observed_days * 2} days) is unreliable.")
    return (f"{observed_days} observed days. The trend model is enabled, but usage is bursty "
            "(a few heavy agent days dominate), so intervals stay wide on purpose.")


def observed_series(daily: pd.DataFrame, column: str) -> pd.DataFrame:
    """Calendar-complete series (missing days filled with 0) for one column."""
    if daily is None or daily.empty:
        return pd.DataFrame(columns=["date", column])
    s = daily[["date", column]].copy()
    s["date"] = pd.to_datetime(s["date"])
    s = s.sort_values("date")
    full = pd.date_range(s["date"].min(), s["date"].max(), freq="D")
    s = s.set_index("date").reindex(full, fill_value=0).rename_axis("date").reset_index()
    return s


def percentiles(samples: np.ndarray, ps=(10, 50, 90)) -> tuple[float, float, float]:
    if samples is None or len(samples) == 0:
        return 0.0, 0.0, 0.0
    low, med, high = np.percentile(np.asarray(samples, dtype=float), ps)
    return float(low), float(med), float(high)


def linear_forecast(values, horizon_days: int, last_date: pd.Timestamp | None = None,
                    daily_growth: float = 0.0) -> Forecast:
    """Least-squares straight line through the observed days, plus an optional
    compounding daily growth assumption. Band = +/-1.96 residual std."""
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n == 0 or horizon_days <= 0:
        return Forecast("Linear", 0, [], np.array([]), np.array([]), np.array([]), n, 0.0,
                        "no observed data", supported=False)
    x = np.arange(n, dtype=float)
    slope, intercept = np.polyfit(x, y, 1) if n >= 2 else (0.0, float(y.mean()))
    resid = y - (slope * x + intercept) if n >= 2 else np.zeros(n)
    band = 1.96 * float(np.std(resid)) if n >= 2 else 0.0
    # residual band widens with the square root of the horizon: extrapolation error grows
    steps = np.arange(1, horizon_days + 1, dtype=float)
    growth = np.power(1.0 + float(daily_growth), steps)
    med = (intercept + slope * (n - 1 + steps)) * growth
    spread = band * np.sqrt(steps)
    dates = _future_dates(last_date, horizon_days, n)
    return Forecast(
        method="Linear extrapolation (baseline)", horizon_days=horizon_days, dates=dates,
        per_day_low=np.clip(med - spread, 0, None), per_day_median=np.clip(med, 0, None),
        per_day_high=np.clip(med + spread, 0, None),
        observed_days=n, observed_mean=float(y.mean()),
        assumptions=(f"daily usage follows one straight line fitted on {n} days; "
                     f"daily growth assumption {daily_growth:+.1%}; prediction band = residual std x 1.96"),
    )


def bootstrap_forecast(values, horizon_days: int, last_date: pd.Timestamp | None = None,
                       n_sims: int = 2000, seed: int = 7) -> Forecast:
    """Resample the OBSERVED days with replacement to build a distribution of
    future totals. Assumes each future day is an independent draw from the
    observed day distribution (no trend, no weekday effect)."""
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n == 0 or horizon_days <= 0:
        return Forecast("Bootstrap resampling", 0, [], np.array([]), np.array([]), np.array([]), n, 0.0,
                        "no observed data", supported=False)
    rng = np.random.default_rng(seed)
    draws = rng.choice(y, size=(n_sims, horizon_days), replace=True)
    low, med, high = (np.percentile(draws, p, axis=0) for p in (10, 50, 90))
    return Forecast(
        method="Bootstrap resampling", horizon_days=horizon_days,
        dates=_future_dates(last_date, horizon_days, n),
        per_day_low=low, per_day_median=med, per_day_high=high,
        observed_days=n, observed_mean=float(y.mean()),
        assumptions=(f"each future day is an independent draw from the {n} observed days "
                     f"({n_sims} resamples); no trend and no weekday rhythm are modelled"),
        notes=["Bootstrap can only produce values it has already seen, so it never forecasts a new high."],
    )


def monte_carlo_forecast(values, horizon_days: int, last_date: pd.Timestamp | None = None,
                         n_sims: int = 2000, seed: int = 11,
                         growth_mean: float = 0.0, growth_sd: float = 0.05,
                         recent_days: int = 5) -> Forecast:
    """Simulate future days from a lognormal distribution anchored on the recent
    mean, with a configurable drift (growth_mean) and volatility (growth_sd)."""
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n == 0 or horizon_days <= 0:
        return Forecast("Monte Carlo", 0, [], np.array([]), np.array([]), np.array([]), n, 0.0,
                        "no observed data", supported=False)
    rng = np.random.default_rng(seed)
    recent = y[-min(recent_days, n):]
    base = float(recent.mean())
    # spread of the observed day-to-day ratio drives the simulated noise
    nonzero = recent[recent > 0]
    obs_cv = float(np.std(nonzero) / np.mean(nonzero)) if len(nonzero) > 1 else 0.5
    sigma = max(growth_sd, min(obs_cv, 2.0))
    steps = np.arange(1, horizon_days + 1)
    drift = np.power(1.0 + float(growth_mean), steps)
    noise = rng.lognormal(mean=0.0, sigma=sigma, size=(n_sims, horizon_days))
    paths = base * drift * noise
    low, med, high = (np.percentile(paths, p, axis=0) for p in (10, 50, 90))
    return Forecast(
        method="Monte Carlo simulation", horizon_days=horizon_days,
        dates=_future_dates(last_date, horizon_days, n),
        per_day_low=low, per_day_median=med, per_day_high=high,
        observed_days=n, observed_mean=float(y.mean()),
        assumptions=(f"future days ~ lognormal around the mean of the last {len(recent)} day(s) "
                     f"(base {base:,.0f}); daily drift {growth_mean:+.1%}; volatility "
                     f"sigma={sigma:.2f} (from observed day-to-day spread)"),
        notes=["Not a reconstruction of the past - simulated days only ever describe the future."],
    )


def holt_forecast(values, horizon_days: int, last_date: pd.Timestamp | None = None,
                  alpha: float = 0.5, beta: float = 0.3) -> Forecast:
    """Holt's linear (level + trend) exponential smoothing. Refuses to run on
    short windows, where the trend estimate is pure noise."""
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n < MIN_DAYS_FOR_TREND:
        return Forecast(
            "Holt linear trend", 0, [], np.array([]), np.array([]), np.array([]), n,
            float(y.mean()) if n else 0.0,
            f"needs at least {MIN_DAYS_FOR_TREND} observed days to estimate a trend",
            supported=False,
            notes=[f"only {n} day(s) available"],
        )
    level = y[0]
    trend = y[1] - y[0]
    resid = []
    for v in y:
        last_level = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - last_level) + (1 - beta) * trend
        resid.append(v - level)
    steps = np.arange(1, horizon_days + 1)
    med = level + trend * steps
    band = 1.96 * float(np.std(resid)) * np.sqrt(steps)
    return Forecast(
        method="Holt linear trend", horizon_days=horizon_days,
        dates=_future_dates(last_date, horizon_days, n),
        per_day_low=np.clip(med - band, 0, None), per_day_median=np.clip(med, 0, None),
        per_day_high=np.clip(med + band, 0, None),
        observed_days=n, observed_mean=float(y.mean()),
        assumptions=(f"level+trend exponential smoothing (alpha={alpha}, beta={beta}) on {n} days; "
                     "bursty agent days are treated as signal, which widens the band"),
    )


def _future_dates(last_date: pd.Timestamp | None, horizon: int, n_obs: int) -> list[pd.Timestamp]:
    if last_date is None:
        return list(pd.date_range(pd.Timestamp.today().normalize(), periods=horizon, freq="D"))
    return list(pd.date_range(pd.Timestamp(last_date) + pd.Timedelta(days=1), periods=horizon, freq="D"))


METHODS = {
    "Linear extrapolation (baseline)": linear_forecast,
    "Bootstrap resampling": bootstrap_forecast,
    "Monte Carlo simulation": monte_carlo_forecast,
    "Holt linear trend": holt_forecast,
}


def run_forecast(method: str, values, horizon_days: int, last_date=None, **kwargs) -> Forecast:
    fn = METHODS.get(method, linear_forecast)
    return fn(values, horizon_days, last_date=last_date, **kwargs)


def aggregate(daily: pd.DataFrame, freq: str) -> pd.DataFrame:
    """Aggregate a daily frame to daily/weekly/monthly totals (W-MON week start)."""
    if daily is None or daily.empty:
        return daily
    rule = {"daily": None, "weekly": "W-MON", "monthly": "MS"}.get(freq, None)
    if rule is None:
        return daily.copy()
    d = daily.set_index(pd.to_datetime(daily["date"])).drop(columns=["date"])
    agg = d.resample(rule).sum(numeric_only=True).reset_index().rename(columns={"index": "date"})
    agg = agg[agg["calls"] > 0] if "calls" in agg else agg
    return agg.reset_index(drop=True)
