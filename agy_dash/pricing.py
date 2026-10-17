"""Dated, versioned model-pricing catalog, kept separate from usage data.

Prices are USD per 1M tokens. Every entry carries the date range it applies to,
so a historical period is never silently priced with today's rates. When no
version covers a date, the caller is told the number is an estimate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import CONFIG_DIR, PROJECT_DIR

CATALOG_PATH = CONFIG_DIR / "pricing.json"


@dataclass(frozen=True)
class PriceEntry:
    model_id: str
    name: str
    vendor: str
    effective_from: str  # ISO date, inclusive
    effective_until: str | None  # ISO date, inclusive; None = open ended
    input_usd: float  # per 1M fresh input tokens
    cached_usd: float  # per 1M cached-read tokens
    output_usd: float  # per 1M output tokens
    source: str = ""
    verified: bool = False  # manual confirmation, not a vendor-page scrape

    def covers(self, when: str) -> bool:
        if when < self.effective_from:
            return False
        return self.effective_until is None or when <= self.effective_until

    def as_dict(self) -> dict:
        return {
            "model_id": self.model_id, "name": self.name, "vendor": self.vendor,
            "effective_from": self.effective_from, "effective_until": self.effective_until,
            "input_usd": self.input_usd, "cached_usd": self.cached_usd,
            "output_usd": self.output_usd, "source": self.source, "verified": self.verified,
        }


def _e(d: dict) -> PriceEntry:
    return PriceEntry(
        model_id=d["model_id"], name=d["name"], vendor=d.get("vendor", ""),
        effective_from=d["effective_from"], effective_until=d.get("effective_until"),
        input_usd=float(d["input_usd"]), cached_usd=float(d["cached_usd"]),
        output_usd=float(d["output_usd"]), source=d.get("source", ""),
        verified=bool(d.get("verified", False)),
    )


def default_catalog() -> list[PriceEntry]:
    """Seed catalog. `verified=False` means: plausible published list price, not
    re-checked against the vendor page on this machine - shown as an estimate."""
    base = 0.75  # Gemini 3.8 Flash input price, USD per 1M (intro through 2026-12-31)
    return [
        # --- the model the logs were actually priced with ---
        _e({"model_id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash", "vendor": "Google",
            "effective_from": "2026-10-01", "effective_until": "2026-12-31",
            "input_usd": base, "cached_usd": base / 10, "output_usd": base * 5,
            "source": "Antigravity launch blog + Gemini API pricing page", "verified": True}),
        # the documented 2027 price doubling for the same model
        _e({"model_id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (post-intro)", "vendor": "Google",
            "effective_from": "2027-01-01", "effective_until": None,
            "input_usd": base * 2, "cached_usd": base / 5, "output_usd": base * 10,
            "source": "documented 2027-01-01 price change", "verified": True}),
        _e({"model_id": "gemini-4-argon", "name": "Gemini 4 Argon", "vendor": "Google",
            "effective_from": "2026-10-01", "effective_until": None,
            "input_usd": 2.00, "cached_usd": 0.10, "output_usd": 10.00,
            "source": "Antigravity docs (--*-price example)", "verified": True}),
        _e({"model_id": "gemini-3.1-pro", "name": "Gemini 3.1 Pro", "vendor": "Google",
            "effective_from": "2026-09-01", "effective_until": None,
            "input_usd": 1.25, "cached_usd": 0.31, "output_usd": 10.00,
            "source": "Gemini API list price (approximate)"}),
        # --- Anthropic ---
        _e({"model_id": "claude-haiku", "name": "Claude Haiku", "vendor": "Anthropic",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 1.00, "cached_usd": 0.10, "output_usd": 5.00,
            "source": "Anthropic list price (approximate)"}),
        _e({"model_id": "claude-sonnet", "name": "Claude Sonnet", "vendor": "Anthropic",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 3.00, "cached_usd": 0.30, "output_usd": 15.00,
            "source": "Anthropic list price (approximate)"}),
        _e({"model_id": "claude-opus", "name": "Claude Opus", "vendor": "Anthropic",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 15.00, "cached_usd": 1.50, "output_usd": 75.00,
            "source": "Anthropic list price (approximate)"}),
        # --- OpenAI ---
        _e({"model_id": "gpt-mini", "name": "OpenAI mini tier", "vendor": "OpenAI",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 0.15, "cached_usd": 0.075, "output_usd": 0.60,
            "source": "OpenAI list price (approximate)"}),
        _e({"model_id": "gpt-flagship", "name": "OpenAI flagship", "vendor": "OpenAI",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 2.50, "cached_usd": 1.25, "output_usd": 10.00,
            "source": "OpenAI list price (approximate)"}),
        # --- open-weight served by external APIs ---
        _e({"model_id": "llama-70b-api", "name": "Llama 3.3 70B (hosted)", "vendor": "Open-weight API",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 0.60, "cached_usd": 0.60, "output_usd": 0.70,
            "source": "typical hosted-serverless price; no prompt cache"}),
        _e({"model_id": "deepseek-v3-api", "name": "DeepSeek V3 (hosted)", "vendor": "Open-weight API",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 0.27, "cached_usd": 0.07, "output_usd": 1.10,
            "source": "typical hosted-serverless price"}),
        _e({"model_id": "qwen-32b-api", "name": "Qwen 2.5 32B (hosted)", "vendor": "Open-weight API",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 0.20, "cached_usd": 0.20, "output_usd": 0.60,
            "source": "typical hosted-serverless price; no prompt cache"}),
        _e({"model_id": "mistral-large-api", "name": "Mistral Large (hosted)", "vendor": "Open-weight API",
            "effective_from": "2026-01-01", "effective_until": None,
            "input_usd": 2.00, "cached_usd": 0.50, "output_usd": 6.00,
            "source": "typical hosted-serverless price"}),
    ]


def load_catalog(path: str | Path | None = None) -> list[PriceEntry]:
    """Load the catalog file if present, else the seeded default."""
    p = Path(path) if path else CATALOG_PATH
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            return [_e(d) for d in raw["models"]]
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            pass  # fall through to the built-in catalog
    return default_catalog()


def models(entries: list[PriceEntry] | None = None) -> list[str]:
    """Distinct model ids, sorted."""
    return sorted({e.model_id for e in (entries if entries is not None else load_catalog())})


class Catalog:
    """Versioned price lookup."""

    def __init__(self, entries: list[PriceEntry] | None = None):
        self.entries = entries if entries is not None else load_catalog()

    def versions(self, model_id: str) -> list[PriceEntry]:
        return sorted(
            (e for e in self.entries if e.model_id == model_id),
            key=lambda e: e.effective_from,
        )

    def price_on(self, model_id: str, on: str | date | None = None) -> tuple[PriceEntry | None, bool]:
        """Return (entry, is_estimate) for `on` (ISO date/date, default today).

        is_estimate is True when no version covers that date: the closest older
        version is used and the caller must label it an estimate.
        """
        when = (on.isoformat() if isinstance(on, date) else on) or date.today().isoformat()
        vs = self.versions(model_id)
        if not vs:
            return None, True
        for e in vs:
            if e.covers(when):
                return e, False
        older = [e for e in vs if e.effective_from <= when]
        if older:
            return older[-1], True  # newest version that predates the date
        return vs[0], True  # date predates all versions

    def latest(self, model_id: str) -> PriceEntry | None:
        vs = self.versions(model_id)
        return vs[-1] if vs else None

    def availability_warning(self, model_id: str, on: str | date | None = None) -> str | None:
        entry, estimate = self.price_on(model_id, on)
        if entry is None:
            return f"no pricing known for {model_id}"
        if estimate:
            return (f"{entry.name}: no price version for this period; using {entry.effective_from} "
                    f"prices - treat as an estimate")
        return None


def write_example_catalog(path: str | Path | None = None) -> Path:
    p = Path(path) if path else PROJECT_DIR / "config" / "pricing.example.json"
    p.write_text(
        json.dumps({"models": [e.as_dict() for e in default_catalog()]}, indent=2) + "\n",
        encoding="utf-8",
    )
    return p
