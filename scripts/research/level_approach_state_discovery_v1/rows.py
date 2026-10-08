"""Turn parent touches into approach rows. Does not read or write an outcome."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K
from .approach import compute_features, price_features_ok, volume_ok


def vol_tercile(sigma: float) -> Optional[int]:
    if not math.isfinite(sigma):
        return None
    if sigma <= K.PARENT_SIGMA_LO:
        return 0
    if sigma <= K.PARENT_SIGMA_HI:
        return 1
    return 2


def approach_row(touch: dict, close, high, low, quote, *, band_mult: float) -> Optional[dict]:
    """Feature row for one parent touch. Returns None when the approach is not eligible.

    Parent `feature_eligible` is a data-availability flag (known side, usable X, complete
    4h window). It is not an outcome. The feature values themselves stop at bar j-1.
    """
    if not touch.get("feature_eligible"):
        return None
    sigma = touch.get("sigma")
    x = touch.get("x_primary")
    if sigma is None or x is None:
        return None
    feat = compute_features(
        close, high, low, quote,
        j=int(touch["j"]), i0=int(touch["i0"]), side=int(touch["side"]),
        zlo=float(touch["zone_low"]), zhi=float(touch["zone_high"]),
        x=float(x), sigma=float(sigma), band_mult=band_mult,
    )
    if feat is None or not price_features_ok(feat):
        return None
    tercile = vol_tercile(float(sigma))
    if tercile is None:
        return None
    side = int(touch["side"])
    bucket = touch["bucket"]
    return {
        "episode_id": touch["episode_id"],
        "population": touch.get("population", "real"),
        "family": touch["family"],
        "kind": touch["kind"],
        "bucket": bucket,
        "touch_number": int(touch["touch_number"]),
        "touch2": 1.0 if bucket == "2" else 0.0,
        "touch3": 1.0 if bucket == "3+" else 0.0,
        "side": side,
        "support": 1.0 if side < 0 else 0.0,
        "year": int(touch["year"]),
        "week": int(touch["week"]),
        "vol_tercile": int(tercile),
        "sigma": float(sigma),
        "j": int(touch["j"]),
        "cluster": touch["episode_id"],
        **feat,
        "volume_ok": volume_ok(feat),
    }


def collect(touches: list[dict], close, high, low, quote, *, band_mult: float) -> list[dict]:
    rows = []
    for touch in touches:
        row = approach_row(touch, close, high, low, quote, band_mult=band_mult)
        if row is not None:
            rows.append(row)
    return rows


def require_volume(rows: list[dict], retained: list[str]) -> list[dict]:
    if "rel_volume" not in retained:
        return rows
    return [row for row in rows if row.get("volume_ok")]


def volume_missing_rate(rows: list[dict]) -> float:
    """Share of price-eligible approach rows whose quote ratio is unusable."""
    if not rows:
        return math.nan
    missing = sum(1 for row in rows if not row.get("volume_ok"))
    return missing / len(rows)
