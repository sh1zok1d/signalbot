"""Parent code vendored unchanged from origin/cursor/range-position-4h-incremental-replication-v1-08d8.

grid.py blob 18112255083d4c04f2f316156782d0993266758f: _nan, features.
stats.py blob a7aa21f4af5fa7f1f2c8655fb5dff84e633cffb2: average_ranks_fast, _pearson, _ols_residual, spearman,
    partial_rank, quintile_table, _interval, _includes_zero, _below_zero, _above_zero.
formation_width_regime_v1/amendment_a1.py blob 2ef15dbcec1cba268ef87616c05d89b36e75e18f: average_ranks, _ols_residual,
    _pearson, partial_spearman (reference for the one-covariate parity gate; prefixed ref_).
Only module references were adapted (K = this unit's constants). Function bodies are byte-identical otherwise.
"""
from __future__ import annotations

import math

import numpy as np

from . import constants as K


def _nan(n: int) -> np.ndarray:
    return np.full(n, np.nan, dtype=np.float64)

def features(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> dict[str, np.ndarray]:
    """RP4H, RET_4H, RV_4H, RANGE_WIDTH_4H, R_1H on one dense grid. Past only for the states."""
    n = int(close.shape[0])
    ret = _nan(n)
    with np.errstate(divide="ignore", invalid="ignore"):
        ret[1:] = np.log(close[1:] / close[:-1])
    rp = _nan(n)
    width = _nan(n)
    signed = _nan(n)
    rv = _nan(n)
    future = _nan(n)
    w = K.LOOKBACK
    h = K.HORIZON
    if n > w:
        hv = np.lib.stride_tricks.sliding_window_view(high, w)
        lv = np.lib.stride_tricks.sliding_window_view(low, w)
        cv = np.lib.stride_tricks.sliding_window_view(close, w)
        rvw = np.lib.stride_tricks.sliding_window_view(ret, w)
        finite = np.isfinite(hv).all(axis=1) & np.isfinite(lv).all(axis=1) & np.isfinite(cv).all(axis=1)
        hi = np.max(hv, axis=1)
        lo = np.min(lv, axis=1)
        span = hi - lo
        last = cv[:, -1]
        ok_rp = finite & np.isfinite(span) & (span > 0.0) & np.isfinite(last)
        with np.errstate(divide="ignore", invalid="ignore"):
            pos = (last - lo) / span
        sl = slice(w - 1, None)
        rp[sl] = np.where(ok_rp, pos, np.nan)
        ok_w = ok_rp & (lo > 0.0) & (hi > 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            log_width = np.log(hi) - np.log(lo)
        width[sl] = np.where(ok_w, log_width, np.nan)
        ret_ok = np.isfinite(rvw).all(axis=1)
        with np.errstate(divide="ignore", invalid="ignore"):
            scale = np.sqrt(np.sum(rvw * rvw, axis=1))
        rv[sl] = np.where(ret_ok, scale, np.nan)
    if n > w:
        earlier = close[:-w]
        later = close[w:]
        with np.errstate(divide="ignore", invalid="ignore"):
            step = np.log(later / earlier)
        ok_s = np.isfinite(earlier) & np.isfinite(later) & (earlier > 0.0) & (later > 0.0)
        signed[w:] = np.where(ok_s, step, np.nan)
    if n > h:
        base = close[:-h]
        dest = close[h:]
        with np.errstate(divide="ignore", invalid="ignore"):
            fwd = np.log(dest / base)
        ok_f = np.isfinite(base) & np.isfinite(dest) & (base > 0.0) & (dest > 0.0)
        future[:-h] = np.where(ok_f, fwd, np.nan)
    return {"rp": rp, "ret4": signed, "rv4": rv, "width": width, "r1": future}

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


# ---- reference (amendment_a1), used only for the one-covariate parity gate
def ref_average_ranks(values: np.ndarray) -> np.ndarray:
    x = np.asarray(values, dtype=np.float64)
    n = int(x.shape[0])
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(n, dtype=np.float64)
    sorted_x = x[order]
    i = 0
    while i < n:
        j = i + 1
        while j < n and sorted_x[j] == sorted_x[i]:
            j += 1
        ranks[order[i:j]] = 0.5 * ((i + 1) + j)
        i = j
    return ranks

def ref_ols_residual(y: np.ndarray, x: np.ndarray) -> np.ndarray | None:
    design = np.column_stack([np.ones(len(y)), x])
    beta, _, _, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    ss_tot = float(np.dot(y - y.mean(), y - y.mean()))
    ss_res = float(np.dot(resid, resid))
    if ss_tot == 0.0 or ss_res <= 1e-12 * ss_tot:
        return None
    return resid

def ref_pearson(a: np.ndarray, b: np.ndarray) -> float:
    left = a - a.mean()
    right = b - b.mean()
    denom = math.sqrt(float(np.dot(left, left) * np.dot(right, right)))
    if denom == 0.0:
        raise RuntimeError("partial correlation is degenerate")
    return float(np.dot(left, right) / denom)

def ref_partial_spearman(v: np.ndarray, y: np.ndarray, z: np.ndarray) -> dict:
    """Pearson correlation of average-rank residuals. One covariate, OLS with intercept."""
    v = np.asarray(v, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    if not (len(v) == len(y) == len(z)) or len(v) < 3:
        raise RuntimeError("partial Spearman needs three aligned series of length at least 3")
    rv = ref_average_ranks(v)
    ry = ref_average_ranks(y)
    rz = ref_average_ranks(z)
    left = ref_ols_residual(rv, rz)
    right = ref_ols_residual(ry, rz)
    if left is None or right is None:
        return {"rho": None, "degenerate": True, "covariate": "ONE_COVARIATE"}
    return {"rho": ref_pearson(left, right), "degenerate": False, "covariate": "ONE_COVARIATE"}
