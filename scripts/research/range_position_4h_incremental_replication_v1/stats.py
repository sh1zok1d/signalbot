"""Ranks, partial Spearman, and the frozen route. No market data."""

from __future__ import annotations

import math

import numpy as np

from scripts.research.formation_width_regime_v1.amendment_a1 import average_ranks, partial_spearman

from . import constants as K


def average_ranks_fast(values: np.ndarray) -> np.ndarray:
    """Same midranks as average_ranks. Mergesort keeps the tie order stable."""
    x = np.asarray(values, dtype=np.float64)
    n = int(x.shape[0])
    order = np.argsort(x, kind="mergesort")
    sorted_x = x[order]
    change = np.empty(n, dtype=bool)
    change[0] = True
    if n > 1:
        change[1:] = sorted_x[1:] != sorted_x[:-1]
    starts = np.flatnonzero(change)
    ends = np.empty(starts.shape[0], dtype=np.int64)
    ends[:-1] = starts[1:]
    ends[-1] = n
    avg = 0.5 * ((starts.astype(np.float64) + 1.0) + ends.astype(np.float64))
    ranks = np.empty(n, dtype=np.float64)
    ranks[order] = np.repeat(avg, ends - starts)
    return ranks


def ranks_match_reference(values: np.ndarray) -> bool:
    a = average_ranks(np.asarray(values, dtype=np.float64))
    b = average_ranks_fast(values)
    return bool(np.allclose(a, b))


def _pearson(a: np.ndarray, b: np.ndarray) -> float | None:
    left = a - a.mean()
    right = b - b.mean()
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0:
        return None
    return float(np.dot(left, right) / denom)


def _ols_residual(y: np.ndarray, covariates: np.ndarray) -> np.ndarray | None:
    design = np.column_stack([np.ones(len(y)), covariates])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    centered = y - y.mean()
    ss_tot = float(np.dot(centered, centered))
    ss_res = float(np.dot(resid, resid))
    if ss_tot == 0.0 or ss_res <= 1e-12 * ss_tot:
        return None
    return resid


def spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.shape[0] < 3 or np.unique(x).size < 2 or np.unique(y).size < 2:
        return None
    return _pearson(average_ranks_fast(x), average_ranks_fast(y))


def partial_rank(y: np.ndarray, x: np.ndarray, covariates: list[np.ndarray]) -> dict:
    """Pearson of rank residuals. covariates are columns, intercept included."""
    y = np.asarray(y, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    cols = [np.asarray(c, dtype=np.float64) for c in covariates]
    n = int(y.shape[0])
    if n < 3 or any(c.shape[0] != n for c in cols) or x.shape[0] != n or not cols:
        return {"rho": None, "degenerate": True, "n": n}
    ry = average_ranks_fast(y)
    rx = average_ranks_fast(x)
    rz = np.column_stack([average_ranks_fast(c) for c in cols])
    left = _ols_residual(rx, rz)
    right = _ols_residual(ry, rz)
    if left is None or right is None:
        return {"rho": None, "degenerate": True, "n": n}
    rho = _pearson(left, right)
    if rho is None:
        return {"rho": None, "degenerate": True, "n": n}
    return {"rho": rho, "degenerate": False, "n": n}


def matches_canonical_one_covariate(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> bool:
    ours = partial_rank(y, x, [z])
    ref = partial_spearman(x, y, z)
    if ours["degenerate"] or ref["degenerate"]:
        return bool(ours["degenerate"] and ref["degenerate"])
    return abs(float(ours["rho"]) - float(ref["rho"])) <= 1e-9


def quintile_table(x: np.ndarray, y: np.ndarray) -> dict:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.size < 5:
        return {"degenerate": True, "bins": None}
    edges = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
    if not (edges[0] < edges[1] < edges[2] < edges[3]):
        return {"degenerate": True, "bins": None, "edges": [float(v) for v in edges]}
    bins = np.digitize(x, edges, right=False)
    rows = []
    for k in range(5):
        m = bins == k
        yy = y[m]
        rows.append({
            "bin": k + 1,
            "n": int(m.sum()),
            "p_up": float(np.mean(yy > 0.0)) if yy.size else None,
            "mean_return": float(yy.mean()) if yy.size else None,
            "median_return": float(np.median(yy)) if yy.size else None,
        })
    return {"degenerate": False, "edges": [float(v) for v in edges], "bins": rows}


def _interval(samples: np.ndarray) -> dict:
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        return {"lo": None, "hi": None, "valid": 0, "draws": K.BOOT_DRAWS}
    return {
        "lo": float(np.quantile(finite, K.BOOT_LO)),
        "hi": float(np.quantile(finite, K.BOOT_HI)),
        "valid": int(finite.size),
        "draws": K.BOOT_DRAWS,
    }


def _includes_zero(interval: dict) -> bool:
    return interval["lo"] is not None and interval["lo"] <= 0.0 <= interval["hi"]


def _below_zero(interval: dict) -> bool:
    return interval["hi"] is not None and interval["hi"] < 0.0


def _above_zero(interval: dict) -> bool:
    return interval["lo"] is not None and interval["lo"] > 0.0


def assign_route(raw: float | None, raw_ci: dict, primary: float | None, primary_ci: dict) -> str:
    """The design order. Diagnostics do not enter."""
    if (
        raw is None
        or primary is None
        or raw_ci["valid"] < K.MIN_VALID_DRAWS
        or primary_ci["valid"] < K.MIN_VALID_DRAWS
    ):
        return K.ROUTE_UNAVAILABLE
    if raw < 0.0 and primary < 0.0 and _below_zero(primary_ci):
        return K.ROUTE_SUPPORTED
    if raw < 0.0 and _below_zero(raw_ci) and _includes_zero(primary_ci):
        return K.ROUTE_RAW_ONLY
    if raw < 0.0 and _includes_zero(raw_ci):
        return K.ROUTE_COMPATIBLE
    if raw >= 0.0:
        return K.ROUTE_NOT
    if raw < 0.0 and _below_zero(raw_ci) and _above_zero(primary_ci):
        return K.ROUTE_OPPOSES
    return K.ROUTE_UNAVAILABLE
