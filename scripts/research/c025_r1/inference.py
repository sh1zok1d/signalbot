"""Primary permutation test, standardization, year stability, and placebo.

Seeds and draw counts are the module constants. Callers cannot replace them
on the confirmatory path.
"""

from __future__ import annotations

import numpy as np

from .constants import (
    PERMUTATION_DRAWS,
    PERMUTATION_SEED,
    PLACEBO_DRAWS,
    PLACEBO_SEED,
    PRIMARY_ALPHA,
    assert_locked_primary,
)


def delta_impact(y: np.ndarray, arm: np.ndarray) -> float | None:
    """Unweighted mean(one-sided) - mean(two-sided). None if either arm is empty."""
    y = np.asarray(y, dtype=np.float64)
    arm = np.asarray(arm)
    one = y[arm == 1]
    two = y[arm == 0]
    if one.size == 0 or two.size == 0:
        return None
    if not np.all(np.isfinite(one)) or not np.all(np.isfinite(two)):
        return None
    return float(np.mean(one) - np.mean(two))


def pooled_sd(y: np.ndarray, arm: np.ndarray) -> float | None:
    y = np.asarray(y, dtype=np.float64)
    arm = np.asarray(arm)
    one = y[arm == 1]
    two = y[arm == 0]
    if one.size < 2 or two.size < 2:
        return None
    num = (one.size - 1) * float(np.var(one, ddof=1)) + (two.size - 1) * float(np.var(two, ddof=1))
    den = one.size + two.size - 2
    if den <= 0:
        return None
    var = num / den
    if var <= 0.0:
        return None
    return float(np.sqrt(var))


def standardized_delta(y: np.ndarray, arm: np.ndarray) -> tuple[float | None, float | None]:
    raw = delta_impact(y, arm)
    scale = pooled_sd(y, arm)
    if raw is None or scale is None:
        return raw, None
    return raw, float(raw / scale)


def _groups(keys: np.ndarray) -> list[np.ndarray]:
    keys = np.asarray(keys)
    order = np.argsort(keys, kind="mergesort")
    sorted_keys = keys[order]
    if order.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(sorted_keys)) + 1
    starts = np.concatenate(([0], cuts))
    ends = np.concatenate((cuts, [order.size]))
    return [order[s:e] for s, e in zip(starts, ends)]


def permutation_pvalue(y: np.ndarray, arm: np.ndarray, keys: np.ndarray, observed: float,
                       draws: int = PERMUTATION_DRAWS, seed: int = PERMUTATION_SEED) -> dict:
    """Permute arm labels inside frozen strata. One-sided p with the +1 correction."""
    assert_locked_primary()
    if draws != PERMUTATION_DRAWS or seed != PERMUTATION_SEED:
        raise RuntimeError("permutation draws and seed are frozen")
    y = np.asarray(y, dtype=np.float64)
    arm = np.asarray(arm).astype(np.int64).copy()
    groups = _groups(keys)
    rng = np.random.Generator(np.random.PCG64(seed))
    ge = 0
    for _ in range(draws):
        perm = arm.copy()
        for idx in groups:
            perm[idx] = rng.permutation(arm[idx])
        stat = delta_impact(y, perm)
        if stat is None:
            raise RuntimeError("permutation destroyed an arm; stratum counts were not preserved")
        if stat >= observed:
            ge += 1
    p = (1.0 + ge) / (1.0 + draws)
    return {
        "PRIMARY_PERMUTATION_P": p,
        "PERMUTATION_GE": ge,
        "PERMUTATION_DRAWS": draws,
        "PERMUTATION_SEED": seed,
        "P_FORMULA": "(1 + count(T_perm >= T_obs)) / (1 + permutations)",
    }


def year_deltas(y: np.ndarray, arm: np.ndarray, year: np.ndarray) -> dict:
    out = {}
    positive = 0
    for value in (2020, 2021, 2022, 2023, 2024):
        member = year == value
        stat = delta_impact(y[member], arm[member]) if np.any(member) else None
        out[str(value)] = stat
        if stat is not None and stat > 0.0:
            positive += 1
    return {"YEAR_EFFECTS": out, "POSITIVE_YEARS": positive}


def stability_pass(pooled: float | None, year_effects: dict) -> bool:
    if pooled is None or not (pooled > 0.0):
        return False
    positive = sum(1 for value in year_effects.values() if value is not None and value > 0.0)
    return positive >= 3


def placebo_pvalue(y: np.ndarray, keys: np.ndarray, observed: float,
                   draws: int = PLACEBO_DRAWS, seed: int = PLACEBO_SEED) -> dict:
    """Random within-stratum splits of non-burst pseudo-events. Supporting gate."""
    assert_locked_primary()
    if draws != PLACEBO_DRAWS or seed != PLACEBO_SEED:
        raise RuntimeError("placebo draws and seed are frozen")
    y = np.asarray(y, dtype=np.float64)
    groups = [idx for idx in _groups(keys) if idx.size >= 2]
    if not groups:
        return {
            "PLACEBO_P": None,
            "PLACEBO_GE": None,
            "PLACEBO_DRAWS": draws,
            "PLACEBO_SEED": seed,
            "PLACEBO_PASS": False,
            "PLACEBO_STATUS": "NO_PLACEBO_STRATA",
        }
    rng = np.random.Generator(np.random.PCG64(seed))
    ge = 0
    last = None
    for _ in range(draws):
        arm = np.zeros(y.shape[0], dtype=np.int64)
        for idx in groups:
            choice = rng.permutation(idx)
            half = int(idx.size // 2)
            arm[choice[:half]] = 1
        stat = delta_impact(y, arm)
        last = stat
        if stat is not None and stat >= observed:
            ge += 1
    p = (1.0 + ge) / (1.0 + draws)
    return {
        "PLACEBO_STATISTIC_LAST_DRAW": last,
        "PLACEBO_P": p,
        "PLACEBO_GE": ge,
        "PLACEBO_DRAWS": draws,
        "PLACEBO_SEED": seed,
        "PLACEBO_PASS": bool(p <= PRIMARY_ALPHA),
        "PLACEBO_STATUS": "COMPUTED",
        "P_FORMULA": "(1 + count(PLACEBO_DELTA >= POOLED_DELTA_RAW)) / (1 + draws)",
    }
