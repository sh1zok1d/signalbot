"""Week-block bootstrap of a conditional rate difference.

A resampled source episode always moves its real row and its pseudo row together.
The P1 denominator is rebuilt from whichever resampled rows are FIRST_BREAK.
Real and pseudo first-event types inside one pair do not have to match.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _rate(flags: np.ndarray) -> Optional[float]:
    if flags.size == 0:
        return None
    return float(np.mean(flags))


def contrast(real_flags: np.ndarray, pseudo_flags: np.ndarray) -> Optional[dict]:
    """flags are 0/1 on the conditional denominator. Empty arm returns None."""
    p_real = _rate(real_flags)
    p_pseudo = _rate(pseudo_flags)
    if p_real is None or p_pseudo is None:
        return None
    return {
        "p_real": p_real,
        "p_pseudo": p_pseudo,
        "delta": p_real - p_pseudo,
        "n_real": int(real_flags.size),
        "n_pseudo": int(pseudo_flags.size),
    }


def _ci(series: np.ndarray, draws: int):
    ok = np.isfinite(series)
    valid = int(ok.sum())
    if valid < K.BOOT_MIN_VALID_FRAC * draws or valid < 2:
        return None, valid
    lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
    return (float(lo), float(hi)), valid


def wald_p(delta: Optional[float], se: Optional[float]) -> Optional[float]:
    if delta is None or se is None or not math.isfinite(delta) or not math.isfinite(se):
        return None
    if se <= 0.0:
        return 1.0 if delta == 0.0 else 0.0
    return float(math.erfc(abs(delta / se) / math.sqrt(2.0)))


def bh_adjust(pvalues: list[Optional[float]]) -> list[Optional[float]]:
    m = len(pvalues)
    usable = [1.0 if p is None or not math.isfinite(p) else float(p) for p in pvalues]
    order = sorted(range(m), key=lambda i: (usable[i], i))
    adj = [None] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, usable[i] * m / rank)
        adj[i] = running
    return adj


def bootstrap_contrast(weeks: np.ndarray, real_flags: np.ndarray, pseudo_flags: np.ndarray,
                       *, draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    """real_flags is nan when the real row is outside the conditional denominator."""
    point = contrast(real_flags[np.isfinite(real_flags)], pseudo_flags[np.isfinite(pseudo_flags)])
    empty = {
        "p_real": None, "p_pseudo": None, "delta": None, "delta_ci95": None,
        "p": None, "n_real": 0, "n_pseudo": 0, "bootstrap_valid": 0, "weeks": 0,
    }
    if point is None:
        return empty
    uniq = np.unique(weeks)
    groups = [np.flatnonzero(weeks == week) for week in uniq]
    rng = np.random.default_rng(seed)
    choice = rng.integers(0, len(groups), size=(draws, len(groups)))
    deltas = np.full(draws, np.nan)
    for draw in range(draws):
        counts = np.bincount(choice[draw], minlength=len(groups))
        parts = [np.repeat(groups[i], int(counts[i])) for i in range(len(groups)) if counts[i]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got = contrast(real_flags[idx][np.isfinite(real_flags[idx])],
                       pseudo_flags[idx][np.isfinite(pseudo_flags[idx])])
        if got is None:
            continue
        deltas[draw] = got["delta"]
    ci, valid = _ci(deltas, draws)
    se = float(np.nanstd(deltas, ddof=1)) if valid >= 2 else None
    return {
        **point,
        "delta_ci95": ci,
        "p": wald_p(point["delta"], se),
        "se": se,
        "bootstrap_valid": valid,
        "weeks": int(len(uniq)),
    }
