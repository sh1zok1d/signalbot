"""Paired first-touch contrast and week-block bootstrap. No market I/O.

The primary estimand is the mean of Y_real - Y_pseudo on matched episodes.
A resample draws product-weeks of the real touch. Both members of a pair live on one
row, and every pair in a drawn week is kept, so a pair is never split.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def tercile_edges(sigmas) -> tuple[float, float]:
    s = np.asarray(list(sigmas), dtype=float)
    s = s[np.isfinite(s)]
    if s.size < 3:
        return (math.nan, math.nan)
    lo, hi = np.quantile(s, [1.0 / 3.0, 2.0 / 3.0])
    return float(lo), float(hi)


def tercile(sigma: float, edges: tuple[float, float]) -> int:
    lo, hi = edges
    if not math.isfinite(sigma) or not math.isfinite(lo):
        return -1
    if sigma <= lo:
        return 0
    if sigma <= hi:
        return 1
    return 2


def covariate_row(family: str, side: int, sigma: float, epoch: str, edges: tuple[float, float]) -> dict:
    ter = tercile(sigma, edges)
    return {
        "family_week": 1.0 if family == "WEEK" else 0.0,
        "family_month": 1.0 if family == "MONTH" else 0.0,
        "support": 1.0 if int(side) < 0 else 0.0,
        "vol_mid": 1.0 if ter == 1 else 0.0,
        "vol_high": 1.0 if ter == 2 else 0.0,
        "epoch_2018": 1.0 if epoch == "2018" else 0.0,
        "epoch_2019": 1.0 if epoch == "2019" else 0.0,
    }


def stacked_covariate_frame(pairs: list[dict], edges: tuple[float, float]) -> dict:
    """Two rows per pair: real then pseudo. No outcome column."""
    rows = []
    is_real = []
    for pair in pairs:
        rows.append(covariate_row(pair["family"], pair["real_side"], pair["real_sigma"],
                                  pair["epoch"], edges))
        is_real.append(1.0)
        rows.append(covariate_row(pair["family"], pair["pseudo_side"], pair["pseudo_sigma"],
                                  pair["pseudo_epoch"], edges))
        is_real.append(0.0)
    return {"rows": rows, "is_real": np.asarray(is_real, dtype=float)}


def select_adjusted_columns(pairs: list[dict], edges: tuple[float, float]) -> dict:
    """Share screen, then a greedy rank screen. Both use covariates only."""
    frame = stacked_covariate_frame(pairs, edges)
    rows = frame["rows"]
    n = len(rows)
    d = frame["is_real"]
    kept: list[str] = []
    dropped_share: list[str] = []
    dropped_rank: list[str] = []
    if n < 4:
        return {"columns": [], "dropped_share": list(K.ADJUSTED_COLUMN_ORDER), "dropped_rank": []}
    for name in K.ADJUSTED_COLUMN_ORDER:
        col = np.asarray([r[name] for r in rows], dtype=float)
        share = float(col.mean()) if n else 0.0
        if share < K.MIN_DUMMY_SHARE or share > K.MAX_DUMMY_SHARE:
            dropped_share.append(name)
            continue
        trial = kept + [name]
        rank = _rank(d, rows, trial)
        if rank < 2 + len(trial):
            dropped_rank.append(name)
            continue
        kept.append(name)
    return {"columns": kept, "dropped_share": dropped_share, "dropped_rank": dropped_rank}


def _rank(d: np.ndarray, rows: list[dict], names: list[str]) -> int:
    n = d.shape[0]
    cols = [np.ones(n), d]
    for name in names:
        cols.append(np.asarray([r[name] for r in rows], dtype=float))
    return int(np.linalg.matrix_rank(np.column_stack(cols), tol=1e-10))


def pair_diff(y_real: int, y_pseudo: int) -> float:
    return float(y_real) - float(y_pseudo)


def mean_diff(y_real: np.ndarray, y_pseudo: np.ndarray) -> float:
    return float(np.mean(np.asarray(y_real, dtype=float) - np.asarray(y_pseudo, dtype=float)))


def _week_index(weeks: np.ndarray):
    uniq, inv = np.unique(weeks, return_inverse=True)
    return uniq, inv


def block_mean_draws(values: np.ndarray, weeks: np.ndarray, rng: np.random.Generator, draws: int) -> np.ndarray:
    """Week-block bootstrap of a pair-level mean. `values` is one number per pair."""
    values = np.asarray(values, dtype=float)
    weeks = np.asarray(weeks)
    if values.size == 0:
        return np.full(draws, np.nan)
    _uniq, inv = _week_index(weeks)
    sums = np.bincount(inv, weights=values).astype(float)
    counts = np.bincount(inv).astype(float)
    n_w = sums.shape[0]
    out = np.empty(draws, dtype=float)
    for i in range(draws):
        take = rng.integers(0, n_w, size=n_w)
        denom = counts[take].sum()
        out[i] = sums[take].sum() / denom if denom > 0 else np.nan
    return out


def percentile_ci(draws: np.ndarray, *, expected: int) -> Optional[tuple[float, float]]:
    ok = np.asarray(draws, dtype=float)
    ok = ok[np.isfinite(ok)]
    if expected <= 0 or ok.size < K.BOOT_MIN_VALID_FRAC * expected:
        return None
    lo, hi = np.quantile(ok, [0.025, 0.975])
    return float(lo), float(hi)


def slice_mask(epochs: np.ndarray, families: np.ndarray, sides: np.ndarray, *,
               epoch: Optional[str] = None, family: Optional[str] = None,
               side: Optional[int] = None, omit_epoch: Optional[str] = None) -> np.ndarray:
    mask = np.ones(epochs.shape[0], dtype=bool)
    if epoch is not None:
        mask &= epochs == epoch
    if family is not None:
        mask &= families == family
    if side is not None:
        mask &= sides == side
    if omit_epoch is not None:
        mask &= epochs != omit_epoch
    return mask


def contrast_block(y_real, y_pseudo, weeks, rng, draws: int) -> dict:
    y_real = np.asarray(y_real, dtype=float)
    y_pseudo = np.asarray(y_pseudo, dtype=float)
    if y_real.size == 0:
        return {"estimate": None, "ci_low": None, "ci_high": None, "p_real": None, "p_pseudo": None, "n": 0}
    diff = y_real - y_pseudo
    estimate = float(diff.mean())
    boot = block_mean_draws(diff, np.asarray(weeks), rng, draws)
    ci = percentile_ci(boot, expected=draws)
    return {
        "estimate": estimate,
        "ci_low": None if ci is None else ci[0],
        "ci_high": None if ci is None else ci[1],
        "p_real": float(np.mean(y_real)) if len(y_real) else None,
        "p_pseudo": float(np.mean(y_pseudo)) if len(y_pseudo) else None,
        "n": int(len(y_real)),
    }


def control_matrix(families, sides, sigmas, epochs, edges, columns: list[str]) -> np.ndarray:
    """One row per touch. Built once; bootstrap draws index these rows."""
    n = len(families)
    z = np.zeros((n, len(columns)), dtype=float)
    for i in range(n):
        row = covariate_row(families[i], int(sides[i]), float(sigmas[i]), epochs[i], edges)
        for j, name in enumerate(columns):
            z[i, j] = row[name]
    return z


def adjusted_from_z(y_real, y_pseudo, z_real: np.ndarray, z_pseudo: np.ndarray,
                    index: np.ndarray) -> Optional[float]:
    if index.size == 0:
        return None
    yr = np.asarray(y_real, dtype=float)[index]
    yp = np.asarray(y_pseudo, dtype=float)[index]
    n = int(index.size)
    y = np.concatenate([yr, yp])
    d = np.concatenate([np.ones(n), np.zeros(n)])
    if z_real.shape[1] == 0:
        x = np.column_stack([np.ones(2 * n), d])
    else:
        z = np.vstack([z_real[index], z_pseudo[index]])
        x = np.column_stack([np.ones(2 * n), d, z])
    return adjusted_coefficient(y, x)


def adjusted_coefficient(y: np.ndarray, x: np.ndarray) -> Optional[float]:
    """Coefficient on the real-touch indicator (column 1). None when the design is short rank."""
    if x.ndim != 2 or x.shape[0] < x.shape[1]:
        return None
    if int(np.linalg.matrix_rank(x, tol=1e-10)) < x.shape[1]:
        return None
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    value = float(beta[1])
    if not math.isfinite(value):
        return None
    return value


def block_indices(weeks: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Pair indices from one week-block draw. Pairs that share a week stay together."""
    weeks = np.asarray(weeks)
    uniq, inv = np.unique(weeks, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(uniq.size)]
    take = rng.integers(0, uniq.size, size=uniq.size)
    return np.concatenate([groups[i] for i in take])


def bootstrap_adjusted(y_real, y_pseudo, z_real, z_pseudo, weeks, rng, draws: int) -> np.ndarray:
    out = np.empty(draws, dtype=float)
    for i in range(draws):
        index = block_indices(np.asarray(weeks), rng)
        value = adjusted_from_z(y_real, y_pseudo, z_real, z_pseudo, index)
        out[i] = np.nan if value is None else value
    return out
