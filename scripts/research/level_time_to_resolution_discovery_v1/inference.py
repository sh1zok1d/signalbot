"""Paired week bootstrap of the restricted-mean unresolved-time difference."""

from __future__ import annotations

from typing import Optional

import numpy as np

from . import constants as K
from .survival import km_jumps, rmut


def paired_rmut(times_real, events_real, times_pseudo, events_pseudo) -> Optional[dict]:
    if len(times_real) == 0 or len(times_real) != len(times_pseudo):
        return None
    real = rmut(km_jumps(times_real, events_real))
    pseudo = rmut(km_jumps(times_pseudo, events_pseudo))
    return {"real": real, "pseudo": pseudo, "delta": real - pseudo, "n": int(len(times_real))}


def _ci(series: np.ndarray, draws: int):
    ok = np.isfinite(series)
    valid = int(ok.sum())
    if valid < K.BOOT_MIN_VALID_FRAC * draws or valid < 2:
        return None, valid
    lo, hi = np.quantile(series[ok], [K.CI_ALPHA / 2.0, 1.0 - K.CI_ALPHA / 2.0])
    return (float(lo), float(hi)), valid


def bootstrap_delta(weeks: np.ndarray, times_real, events_real, times_pseudo, events_pseudo,
                    *, draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED) -> dict:
    """Resample real-touch weeks. The real row and its pseudo row move together."""
    point = paired_rmut(times_real, events_real, times_pseudo, events_pseudo)
    empty = {
        "delta": None, "real": None, "pseudo": None, "delta_ci95": None,
        "real_ci95": None, "pseudo_ci95": None, "bootstrap_valid": 0, "n": 0, "weeks": 0,
    }
    if point is None:
        return empty
    uniq = np.unique(weeks)
    groups = [np.flatnonzero(weeks == week) for week in uniq]
    rng = np.random.default_rng(seed)
    choice = rng.integers(0, len(groups), size=(draws, len(groups)))
    deltas = np.full(draws, np.nan)
    reals = np.full(draws, np.nan)
    pseudos = np.full(draws, np.nan)
    for draw in range(draws):
        counts = np.bincount(choice[draw], minlength=len(groups))
        parts = [np.repeat(groups[i], int(counts[i])) for i in range(len(groups)) if counts[i]]
        if not parts:
            continue
        idx = np.concatenate(parts)
        got = paired_rmut(times_real[idx], events_real[idx], times_pseudo[idx], events_pseudo[idx])
        if got is None:
            continue
        deltas[draw] = got["delta"]
        reals[draw] = got["real"]
        pseudos[draw] = got["pseudo"]
    delta_ci, valid = _ci(deltas, draws)
    real_ci, _ = _ci(reals, draws)
    pseudo_ci, _ = _ci(pseudos, draws)
    return {
        "delta": point["delta"],
        "real": point["real"],
        "pseudo": point["pseudo"],
        "delta_ci95": delta_ci,
        "real_ci95": real_ci,
        "pseudo_ci95": pseudo_ci,
        "bootstrap_valid": valid,
        "n": point["n"],
        "weeks": int(len(uniq)),
    }
