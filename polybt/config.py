"""Config loading. config.yaml is merged over the defaults bundled in the repo root."""
from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config(dict):
    """A plain dict with a few derived values."""

    @property
    def cutoff_ts(self) -> int:
        split = self["split"]
        if split.get("cutoff_date"):
            d = dt.date.fromisoformat(str(split["cutoff_date"]))
        else:
            d = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=int(split["cutoff_days_ago"]))
        return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())

    @property
    def selection_start_ts(self) -> int:
        return self.cutoff_ts - int(self["split"]["selection_lookback_days"]) * 86400


def load(path: str | Path | None = None, overrides: dict[str, Any] | None = None) -> Config:
    with open(DEFAULT_PATH) as f:
        cfg = yaml.safe_load(f)
    if path and Path(path).resolve() != DEFAULT_PATH:
        with open(path) as f:
            cfg = _merge(cfg, yaml.safe_load(f) or {})
    if overrides:
        cfg = _merge(cfg, overrides)
    return Config(cfg)
