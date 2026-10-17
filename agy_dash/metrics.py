"""Core calculations. Pure functions, no UI, no I/O - the testable core.

Units and conventions:
  * token counts are raw integers.
  * money is USD unless a function name says otherwise; convert at the edge.
  * every division goes through safe_div, so a zero denominator yields a
    documented default instead of inf/nan.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TOKEN_CATEGORIES = ("fresh_in", "cached", "output")


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    try:
        if pd.isna(numerator) or pd.isna(denominator):
            return default
        if denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def total_tokens(fresh_in: float, cached: float, output: float) -> float:
    """Total = fresh input + cached input + output. The three are mutually
    exclusive in the source (fresh excludes cache reads) - see the handoff doc."""
    return float(fresh_in or 0) + float(cached or 0) + float(output or 0)


def api_cost_usd(fresh_in, cached, output, prices) -> float:
    """Consumption-equivalent API cost in USD for one token bundle."""
    return (
        float(fresh_in or 0) * prices.input_usd
        + float(cached or 0) * prices.cached_usd
        + float(output or 0) * prices.output_usd
    ) / 1e6


def cost_breakdown_usd(fresh_in, cached, output, prices) -> dict[str, float]:
    fresh = float(fresh_in or 0) * prices.input_usd / 1e6
    cache = float(cached or 0) * prices.cached_usd / 1e6
    out = float(output or 0) * prices.output_usd / 1e6
    return {"fresh_in": fresh, "cached": cache, "output": out, "total": fresh + cache + out}


def blended_rate_usd_per_mtok(total_cost_usd: float, tokens: float) -> float:
    """Effective blended API rate: cost / tokens * 1e6."""
    return safe_div(total_cost_usd, tokens) * 1e6


def tokens_per_currency(tokens: float, spend: float) -> float:
    """Tokens obtained per 1 unit of currency actually spent on the subscription.
    0 when no spend is configured (do not report a fake infinite value)."""
    return safe_div(tokens, spend, default=0.0)


def cache_hit_rate(fresh_in: float, cached: float) -> float:
    """Share of prompt tokens served from cache, 0..1."""
    return safe_div(cached, float(fresh_in or 0) + float(cached or 0))


def usd_to(amount_usd: float, rate: float) -> float:
    """Convert USD to the reporting currency at a dated rate. rate=0 leaves USD."""
    return float(amount_usd) * float(rate or 1.0)


def currency_from_usd(amount_usd: float, currency: str, usd_inr: float) -> float:
    if str(currency).upper() == "INR":
        return usd_to(amount_usd, usd_inr)
    return float(amount_usd)


@dataclass
class Totals:
    sessions: int
    calls: int
    active_days: int
    fresh_in: int
    cached: int
    output: int
    total: int

    @property
    def cache_hit_rate(self) -> float:
        return cache_hit_rate(self.fresh_in, self.cached)


def totals_from_daily(daily: pd.DataFrame) -> Totals:
    """Aggregate a daily frame. `sessions` in daily data is a per-day distinct
    count, so it is NOT summed - caller supplies the real session count."""
    if daily is None or daily.empty:
        return Totals(0, 0, 0, 0, 0, 0, 0)
    fresh = int(daily["fresh_in"].sum())
    cached = int(daily["cached"].sum())
    out = int(daily["output"].sum())
    return Totals(
        sessions=0,
        calls=int(daily["calls"].sum()),
        active_days=int((daily["calls"] > 0).sum()),
        fresh_in=fresh, cached=cached, output=out,
        total=total_tokens(fresh, cached, out),
    )


def stock_totals(sessions: pd.DataFrame, daily: pd.DataFrame) -> Totals:
    """Totals over the whole (already filtered) selection, using real distinct
    session counts rather than the daily overlap counts."""
    daily_rows = daily if daily is not None else pd.DataFrame()
    t = totals_from_daily(daily_rows)
    t.sessions = 0 if sessions is None or sessions.empty else int(len(sessions))
    return t


def attach_costs(daily: pd.DataFrame, prices) -> pd.DataFrame:
    """Add per-row and cumulative USD cost columns for a daily frame."""
    if daily is None or daily.empty:
        return daily
    out = daily.copy()
    out["cost_usd"] = [
        api_cost_usd(r.fresh_in, r.cached, r.output, prices) for r in out.itertuples()
    ]
    out["cost_fresh_usd"] = out["fresh_in"] * prices.input_usd / 1e6
    out["cost_cached_usd"] = out["cached"] * prices.cached_usd / 1e6
    out["cost_output_usd"] = out["output"] * prices.output_usd / 1e6
    out["cumulative_cost_usd"] = out["cost_usd"].cumsum()
    return out


def best_worst_days(daily: pd.DataFrame, prices, n: int = 3) -> dict[str, pd.DataFrame]:
    """Most and least expensive/voluminous days. Uses full days only (calls > 0)."""
    empty = daily.iloc[0:0] if daily is not None else pd.DataFrame()
    if daily is None or daily.empty:
        return {"best": empty, "worst": empty}
    d = attach_costs(daily, prices)
    d = d[d["calls"] > 0]
    if d.empty:
        return {"best": empty, "worst": empty}
    return {
        "best": d.nlargest(n, "total").reset_index(drop=True),
        "worst": d.nsmallest(n, "total").reset_index(drop=True),
    }


def verify_consistency(sessions: pd.DataFrame, daily: pd.DataFrame) -> list[str]:
    """Check reported totals against the source records before deriving metrics.
    Returns human-readable discrepancies; never silently corrects anything."""
    issues: list[str] = []
    if daily is None or daily.empty:
        return issues
    for r in daily.itertuples():
        expected = total_tokens(r.fresh_in, r.cached, r.output)
        if int(r.total) != int(expected):
            issues.append(
                f"{r.date:%Y-%m-%d}: total {int(r.total):,} != fresh+cached+output {int(expected):,}"
            )
        if int(r.calls) <= 0 and int(expected) > 0:
            issues.append(f"{r.date:%Y-%m-%d}: tokens with 0 calls")
    if sessions is not None and not sessions.empty:
        s_total = int(sessions["total"].sum())
        d_total = int(daily["total"].sum())
        if s_total != d_total:
            issues.append(
                f"session total {s_total:,} != daily total {d_total:,} "
                f"(Δ {abs(s_total - d_total):,}); sessions may span filter boundaries"
            )
        bad = sessions[sessions["total"] != (sessions["fresh_in"] + sessions["cached"] + sessions["output"])]
        if not bad.empty:
            issues.append(f"{len(bad)} session row(s) where total != fresh+cached+output")
    return issues


@dataclass
class Overview:
    totals: Totals
    api_cost_usd: float
    breakdown_usd: dict[str, float]
    blended_rate_usd_per_mtok: float
    subscription_spend: float          # in reporting currency
    subscription_spend_usd: float
    tokens_per_currency_spent: float
    cost_per_mtok_in_currency: float
    currency: str
    model_name: str
    price_note: str | None


def update_overview(
    sessions: pd.DataFrame,
    daily: pd.DataFrame,
    prices,
    *,
    currency: str = "INR",
    usd_inr: float = 88.0,
    subscription_amount: float = 0.0,
    model_name: str = "",
    price_note: str | None = None,
) -> Overview:
    """One call builds every headline KPI, so UI and tests share the same math."""
    t = stock_totals(sessions, daily)
    cost = api_cost_usd(t.fresh_in, t.cached, t.output, prices)
    breakdown = cost_breakdown_usd(t.fresh_in, t.cached, t.output, prices)
    inr = str(currency).upper() == "INR"
    sub_native = float(subscription_amount or 0.0)
    sub_usd = sub_native / usd_inr if inr and usd_inr else sub_native
    return Overview(
        totals=t,
        api_cost_usd=cost,
        breakdown_usd=breakdown,
        blended_rate_usd_per_mtok=blended_rate_usd_per_mtok(cost, t.total),
        subscription_spend=sub_native,
        subscription_spend_usd=sub_usd,
        tokens_per_currency_spent=tokens_per_currency(t.total, sub_native),
        cost_per_mtok_in_currency=blended_rate_usd_per_mtok(cost, t.total) * (usd_inr if inr else 1.0),
        currency="INR" if inr else "USD",
        model_name=model_name,
        price_note=price_note,
    )


def hypothetical_tokens(
    fresh_in: float, cached: float, output: float,
    *, cached_ratio: float | None = None, output_multiplier: float = 1.0,
) -> dict[str, float]:
    """Rescale a token bundle. `cached_ratio` moves prompt tokens between fresh
    and cached without changing the prompt total; `output_multiplier` scales output."""
    prompt = float(fresh_in or 0) + float(cached or 0)
    if cached_ratio is not None:
        ratio = min(max(float(cached_ratio), 0.0), 1.0)
        cached_new = prompt * ratio
        fresh_new = prompt - cached_new
    else:
        cached_new, fresh_new = float(cached or 0), float(fresh_in or 0)
    return {"fresh_in": fresh_new, "cached": cached_new, "output": float(output or 0) * float(output_multiplier)}


def compare_models(tokens: dict[str, float], catalog, model_ids: list[str], on=None) -> pd.DataFrame:
    """Cost the SAME observed token bundle at each model's dated prices.

    The comparison assumes every model would produce identical token counts,
    which is an assumption, not a measurement - callers must label it as one.
    """
    rows = []
    for mid in model_ids:
        entry, estimate = catalog.price_on(mid, on)
        if entry is None:
            continue
        cost = api_cost_usd(tokens["fresh_in"], tokens["cached"], tokens["output"], entry)
        total = total_tokens(tokens["fresh_in"], tokens["cached"], tokens["output"])
        rows.append({
            "model_id": mid,
            "model": entry.name,
            "vendor": entry.vendor,
            "cost_usd": cost,
            "cost_per_mtok_usd": blended_rate_usd_per_mtok(cost, total),
            "pricing_from": entry.effective_from,
            "estimate": estimate,
        })
    return pd.DataFrame(rows).sort_values("cost_usd").reset_index(drop=True) if rows else pd.DataFrame(
        columns=["model_id", "model", "vendor", "cost_usd", "cost_per_mtok_usd",
                 "pricing_from", "estimate"]
    )
