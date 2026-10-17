"""Data loading: reuse the existing extractor, normalize to DataFrames.

The extractor (`agy_usage.py`) is imported and its `scan()` called directly -
it is the source of truth for token extraction and is never modified or
reimplemented here. Only token volumes come from it; cost is always computed by
this app from a dated price catalog.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SESSION_COLUMNS = [
    "session_id", "label", "kind", "calls", "fresh_in", "cached", "output", "total",
    "first_utc", "last_utc", "first_date", "last_date",
]
DAILY_COLUMNS = ["date", "calls", "sessions", "fresh_in", "cached", "output", "total"]


class SourceError(RuntimeError):
    """Raised when the extractor or the log directory cannot be used."""


@dataclass
class UsageData:
    sessions: pd.DataFrame
    daily: pd.DataFrame
    scanned_at: datetime
    root: str
    warnings: list[str]

    @property
    def empty(self) -> bool:
        return self.daily.empty and self.sessions.empty


_LOADED: dict[str, object] = {}


def load_extractor(path: Path):
    """Import the existing extractor module from its file path (read-only).

    Cached per resolved path: changing `extractor_script` in the config must
    actually load the new file, so the cache key is the path, not the name.
    """
    path = Path(path)
    if not path.exists():
        raise SourceError(f"extractor script not found: {path}")
    key = str(path.resolve())
    if key in _LOADED:
        return _LOADED[key]
    name = f"agy_usage_source_{abs(hash(key))}"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SourceError(f"cannot import extractor: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _LOADED[key] = mod
    return mod


def _empty_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    s = pd.DataFrame({c: pd.Series(dtype="object") for c in SESSION_COLUMNS})
    d = pd.DataFrame({c: pd.Series(dtype="object") for c in DAILY_COLUMNS})
    return s, d


def scan_usage(brain_root: Path, extractor_path: Path) -> UsageData:
    """Run the extractor's scan() and normalize the result. Pure read, no writes."""
    root = Path(brain_root)
    warnings: list[str] = []
    if not root.is_dir():
        raise SourceError(f"brain directory not found: {root}")

    mod = load_extractor(extractor_path)
    sessions_raw, daily_raw = mod.scan(root)
    scanned_at = datetime.now(timezone.utc).astimezone()

    srows = []
    for cid, s in sessions_raw.items():
        first = s.get("first")
        last = s.get("last")
        srows.append({
            "session_id": cid,
            "label": s.get("label") or "(unlabeled)",
            "kind": s.get("kind", "other"),
            "calls": int(s.get("steps", 0)),
            "fresh_in": int(s.get("in", 0)),
            "cached": int(s.get("cache", 0)),
            "output": int(s.get("out", 0)),
            "total": int(s.get("total", 0)),
            "first_utc": first,
            "last_utc": last,
            "first_date": first.astimezone().date().isoformat() if first else None,
            "last_date": last.astimezone().date().isoformat() if last else None,
        })
    sessions = pd.DataFrame(srows, columns=SESSION_COLUMNS)

    drows = []
    for day, v in daily_raw.items():
        fresh, cached, out = int(v.get("in", 0)), int(v.get("cache", 0)), int(v.get("out", 0))
        drows.append({
            "date": day,
            "calls": int(v.get("steps", 0)),
            "sessions": len(v.get("sessions", ()) or ()),
            "fresh_in": fresh, "cached": cached, "output": out,
            "total": fresh + cached + out,
        })
    daily = pd.DataFrame(drows, columns=DAILY_COLUMNS)

    if daily.empty and sessions.empty:
        warnings.append("The extractor returned no token-bearing sessions.")
    else:
        daily["date"] = pd.to_datetime(daily["date"])
        daily = daily.sort_values("date").reset_index(drop=True)
        for c in ("calls", "sessions", "fresh_in", "cached", "output", "total"):
            daily[c] = pd.to_numeric(daily[c], errors="coerce").fillna(0).astype("int64")
        if not sessions.empty:
            for c in ("calls", "fresh_in", "cached", "output", "total"):
                sessions[c] = pd.to_numeric(sessions[c], errors="coerce").fillna(0).astype("int64")

    if not daily.empty:
        oldest = daily["date"].min()
        if oldest > pd.Timestamp("2026-10-05"):
            warnings.append("Token fields only exist from 2026-10-05 onward; earlier sessions are token-less.")
    return UsageData(sessions, daily, scanned_at, str(root), warnings)


def clip_dates(df: pd.DataFrame, start, end, column: str = "date") -> pd.DataFrame:
    """Inclusive date-range filter used by every page's global filter."""
    if df.empty:
        return df
    out = df
    if start is not None:
        out = out[out[column] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out[column] <= pd.Timestamp(end)]
    return out


def sessions_touching(sessions: pd.DataFrame, start, end) -> pd.DataFrame:
    """Sessions whose active window overlaps [start, end]. Used with daily filters."""
    if sessions.empty:
        return sessions
    lo = pd.Timestamp(start).date().isoformat() if start is not None else None
    hi = pd.Timestamp(end).date().isoformat() if end is not None else None
    first = sessions["first_date"].fillna("9999-12-31")
    last = sessions["last_date"].fillna("0001-01-01")
    mask = pd.Series(True, index=sessions.index)
    if lo:
        mask &= last >= lo
    if hi:
        mask &= first <= hi
    return sessions[mask]
