"""Paired ISO-week bootstrap of the mean transition difference."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def wald_p(point: Optional[float], se: Optional[float]) -> Optional[float]:
    if point is None or se is None or not math.isfinite(point) or not math.isfinite(se):
        return None
    if se <= 0.0:
        return 1.0 if point == 0.0 else 0.0
    return float(math.erfc(abs(point / se) / math.sqrt(2.0)))


def _ci(series: np.ndarray, draws: int):
    ok = np.isfinite(series)
    valid = int(ok.sum())
    if valid < K.BOOT_MIN_VALID_FRAC * draws or valid < 2:
        return None, None, valid
    clean = series[ok]
    lo, hi = np.quantile(clean, [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
    se = float(np.std(clean, ddof=1))
    return (float(lo), float(hi)), se, valid


def bootstrap_mean(weeks: np.ndarray, deltas: np.ndarray, *,
                   draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    """Resample real-touch weeks. Each pair delta moves as one atomic unit."""
    point = float(np.mean(deltas)) if deltas.size else None
    empty = {
        "delta": point, "ci95": None, "se": None, "p": None,
        "bootstrap_valid": 0, "n": int(deltas.size), "weeks": 0, "ci_withheld": True,
    }
    if deltas.size == 0:
        return empty
    uniq = np.unique(weeks)
    groups = [np.flatnonzero(weeks == week) for week in uniq]
    rng = np.random.default_rng(seed)
    choice = rng.integers(0, len(groups), size=(draws, len(groups)))
    series = np.full(draws, np.nan)
    for draw in range(draws):
        counts = np.bincount(choice[draw], minlength=len(groups))
        parts = [np.repeat(groups[i], int(counts[i])) for i in range(len(groups)) if counts[i]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        series[draw] = float(np.mean(deltas[idx]))
    ci, se, valid = _ci(series, draws)
    return {
        "delta": point,
        "ci95": ci,
        "se": se,
        "p": wald_p(point, se),
        "bootstrap_valid": valid,
        "n": int(deltas.size),
        "weeks": int(len(uniq)),
        "ci_withheld": ci is None,
    }
