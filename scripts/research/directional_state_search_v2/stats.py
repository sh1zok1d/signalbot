"""Estimands for DIRECTIONAL_STATE_SEARCH_V2 (method fixed by design before any outcome).

- raw: Spearman(STATE, R_1H) = Pearson of midranks;
- incremental: partial Spearman = Pearson of the OLS residuals (intercept) of rank(STATE) and rank(R_1H) on the ranks of
  the frozen control set; the rank machinery is the RANGE_POSITION_4H parent code (imported, not copied);
- uncertainty: ISO-week block bootstrap of the residual cross-products. Ranks and residuals are fixed on the full
  sample; each draw resamples whole ISO weeks with replacement and recomputes
  rho* = sum S_xy / sqrt(sum S_xx * sum S_yy). B and the seed are frozen; percentile 2.5/97.5.
"""
from __future__ import annotations

import math

import numpy as np

from scripts.research.rp4h_bitmex_temporal_v1.parent import _ols_residual, _pearson, average_ranks_fast, partial_rank, spearman

from . import constants as K


def _centered(v: np.ndarray) -> np.ndarray:
    return v - v.mean()


def rank_residuals(y: np.ndarray, x: np.ndarray, controls: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray] | None:
    ry = average_ranks_fast(y)
    rx = average_ranks_fast(x)
    if not controls:
        return _centered(rx), _centered(ry)
    rz = np.column_stack([average_ranks_fast(c) for c in controls])
    ex = _ols_residual(rx, rz)
    ey = _ols_residual(ry, rz)
    if ex is None or ey is None:
        return None
    return ex, ey


def week_index(blocks: np.ndarray) -> tuple[np.ndarray, int]:
    _, inv = np.unique(blocks, return_inverse=True)
    return inv, int(inv.max()) + 1


def boot_matrix(n_weeks: int) -> np.ndarray:
    rng = np.random.default_rng(K.BOOT_SEED)
    return rng.integers(0, n_weeks, size=(K.BOOT_DRAWS, n_weeks))


def block_draws(ex: np.ndarray, ey: np.ndarray, inv: np.ndarray, n_weeks: int, draws: np.ndarray) -> tuple[float, np.ndarray]:
    sxy = np.bincount(inv, weights=ex * ey, minlength=n_weeks)
    sxx = np.bincount(inv, weights=ex * ex, minlength=n_weeks)
    syy = np.bincount(inv, weights=ey * ey, minlength=n_weeks)
    num = sxy[draws].sum(axis=1)
    den = np.sqrt(sxx[draws].sum(axis=1) * syy[draws].sum(axis=1))
    with np.errstate(invalid="ignore", divide="ignore"):
        rho = np.where(den > 0, num / den, np.nan)
    return float(sxy.sum() / math.sqrt(sxx.sum() * syy.sum())), rho


def summarize_draws(point: float, rho: np.ndarray) -> dict:
    finite = rho[np.isfinite(rho)]
    se = float(np.std(finite, ddof=1)) if finite.size > 1 else None
    return {"point": point, "lo": float(np.quantile(finite, K.BOOT_LO)), "hi": float(np.quantile(finite, K.BOOT_HI)),
            "se": se, "z": (point / se) if se else None, "valid": int(finite.size), "draws": int(rho.size)}


def block_bootstrap(ex: np.ndarray, ey: np.ndarray, inv: np.ndarray, n_weeks: int, draws: np.ndarray) -> dict:
    point, rho = block_draws(ex, ey, inv, n_weeks, draws)
    out = summarize_draws(point, rho)
    out["_draws"] = rho
    return out


def estimate(y: np.ndarray, x: np.ndarray, controls: list[np.ndarray], inv: np.ndarray, n_weeks: int,
             draws: np.ndarray) -> dict | None:
    res = rank_residuals(y, x, controls)
    if res is None:
        return None
    out = block_bootstrap(res[0], res[1], inv, n_weeks, draws)
    out["residual_state"] = res[0]
    return out


def two_sided_p(z: float | None) -> float | None:
    if z is None:
        return None
    return float(math.erfc(abs(z) / math.sqrt(2.0)))


def quintiles(x: np.ndarray, y: np.ndarray) -> dict:
    x = np.asarray(x, dtype=np.float64)
    edges = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
    if not (edges[0] < edges[1] < edges[2] < edges[3]):
        return {"degenerate": True, "edges": [float(v) for v in edges], "bins": None}
    b = np.digitize(x, edges, right=False)
    rows = []
    for k in range(5):
        yy = y[b == k]
        rows.append({"bin": k + 1, "n": int(yy.size), "p_up": float(np.mean(yy > 0.0)),
                     "mean_bp": float(yy.mean() * 1e4), "median_bp": float(np.median(yy) * 1e4)})
    return {"degenerate": False, "edges": [float(v) for v in edges], "bins": rows}


__all__ = ["average_ranks_fast", "rank_residuals", "week_index", "boot_matrix", "block_bootstrap", "estimate", "two_sided_p", "quintiles",
           "partial_rank", "spearman", "_pearson"]
