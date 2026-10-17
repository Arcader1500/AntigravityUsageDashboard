"""Application configuration: paths, defaults, logging.

Defaults live here; anything user-specific can be overridden by a JSON file
(config/config.json, or the path in AGY_DASH_CONFIG). Missing keys fall back to
the defaults below, so the app runs with no config file at all.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_DIR / "config"
DATA_DIR = PROJECT_DIR / "data"

# The extraction script owned by the earlier tooling work. Reused, never modified.
DEFAULT_EXTRACTOR = Path.home() / "docs" / "superpowers" / "scripts" / "agy_usage.py"
DEFAULT_BRAIN_ROOT = Path.home() / ".gemini" / "antigravity-cli" / "brain"

DEFAULTS: dict = {
    "brain_root": str(DEFAULT_BRAIN_ROOT),
    "extractor_script": str(DEFAULT_EXTRACTOR),
    # `python` is broken on this machine's PATH; the `py` launcher is not.
    "python_executable": "py",
    "db_path": str(DATA_DIR / "snapshots.db"),
    "log_dir": str(DATA_DIR / "logs"),
    "extraction_timeout_seconds": 180,
    # What I actually pay for the subscription. Used only for the
    # "tokens per rupee actually spent" metric; never assumed to equal API cost.
    "subscription": {
        "amount": 0.0,
        "currency": "INR",
        "period_days": 30,
        "label": "Antigravity plan (set me)",
    },
    # Rates are dated config, not scraped live.
    "fx": {"USD_INR": 88.0},
    "reporting_currency": "INR",
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@dataclass
class Config:
    data: dict = field(default_factory=lambda: dict(DEFAULTS))

    @property
    def brain_root(self) -> Path:
        return Path(os.path.expanduser(str(self.data["brain_root"])))

    @property
    def extractor_script(self) -> Path:
        return Path(os.path.expanduser(str(self.data["extractor_script"])))

    @property
    def python_executable(self) -> str:
        return str(self.data["python_executable"])

    @property
    def db_path(self) -> Path:
        return Path(os.path.expanduser(str(self.data["db_path"])))

    @property
    def log_dir(self) -> Path:
        return Path(os.path.expanduser(str(self.data["log_dir"])))

    @property
    def extraction_timeout(self) -> int:
        return int(self.data["extraction_timeout_seconds"])

    @property
    def subscription(self) -> dict:
        return dict(self.data["subscription"])

    @property
    def fx(self) -> dict:
        return dict(self.data["fx"])

    @property
    def reporting_currency(self) -> str:
        return str(self.data["reporting_currency"])

    @property
    def usd_to_inr(self) -> float:
        try:
            return float(self.fx.get("USD_INR") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def config_path(self) -> Path:
        return Path(os.environ.get("AGY_DASH_CONFIG", CONFIG_DIR / "config.json"))


def load_config(path: str | Path | None = None) -> Config:
    """Load config, merging over DEFAULTS. A bad/missing file never crashes the app."""
    cfg_file = Path(path) if path else Config().config_path()
    data = dict(DEFAULTS)
    if cfg_file.exists():
        try:
            data = _deep_merge(DEFAULTS, json.loads(cfg_file.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as exc:  # keep running on a broken config
            logging.getLogger(__name__).warning("ignoring unreadable config %s: %s", cfg_file, exc)
    return Config(data=data)


def setup_logging(cfg: Config | None = None) -> logging.Logger:
    cfg = cfg or get_config()
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    logfile = cfg.log_dir / "dashboard.log"
    logger = logging.getLogger("agy_dash")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(logfile, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(fh)
    return logger


_CONFIG: Config | None = None


def get_config(reload: bool = False) -> Config:
    global _CONFIG
    if _CONFIG is None or reload:
        _CONFIG = load_config()
    return _CONFIG
