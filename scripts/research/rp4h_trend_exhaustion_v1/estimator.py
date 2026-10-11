"""The exact Unit-1 interaction estimator (imported) and its vectorized twin for synthetic replications.

PRIMARY (Unit 1 interaction_b0, unchanged): partial Spearman(R_1H, (rank RP4H - mean)(rank TS - mean) | RP4H, TS,
RET_4H, RV_4H): midranks, OLS residualization with an intercept on the control ranks, Pearson of the residuals.
Main effects (diagnostics): RP4H | RET_4H, RV_4H (the canonical RP4H partial) and TS | RP4H, RET_4H, RV_4H."""
from __future__ import annotations

import numpy as np

from scripts.research.rp4h_bitmex_temporal_v1.parent import average_ranks_fast, partial_rank
from scripts.research.rp4h_trend_regime_v1.evaluate import interaction as unit1_interaction  # noqa: F401 (parity)

from . import constants as K


def product_term(rp: np.ndarray, ts: np.ndarray) -> np.ndarray:
    rr, rt = average_ranks_fast(rp), average_ranks_fast(ts)
    return (rr - rr.mean()) * (rt - rt.mean())


def x_residual(x: np.ndarray, controls: list) -> np.ndarray:
    """Rank residual of x on the control ranks (with intercept): the estimator's fixed left factor."""
    rz = np.column_stack([np.ones(x.size)] + [average_ranks_fast(c) for c in controls])
    rx = average_ranks_fast(x)
    beta, *_ = np.linalg.lstsq(rz, rx, rcond=None)
    return rx - rz @ beta, rz


class Partial:
    """Vectorized partial Spearman for many synthetic outcome columns with a fixed x and fixed controls."""

    def __init__(self, x: np.ndarray, controls: list, weeks: np.ndarray):
        self.ex, rz = x_residual(x, controls)
        self.proj = np.linalg.pinv(rz)
        self.rz = rz
        self.wk_u, self.wk = np.unique(weeks, return_inverse=True)
        self.W = self.wk_u.size

    def residual_y(self, Y: np.ndarray) -> np.ndarray:
        n, R = Y.shape
        ry = np.empty((n, R))
        order = np.argsort(Y, axis=0, kind="stable")
        ar = np.arange(1, n + 1, dtype=np.float64)
        for j in range(R):                                    # continuous synthetic outcomes: no ties
            ry[order[:, j], j] = ar
        return ry - self.rz @ (self.proj @ ry)

    def rho(self, ey: np.ndarray) -> np.ndarray:
        ex = self.ex - self.ex.mean()
        eyc = ey - ey.mean(axis=0)
        return (ex @ eyc) / np.sqrt((ex @ ex) * (eyc * eyc).sum(axis=0))

    def week_sums(self, ey: np.ndarray) -> dict:
        W, R = self.W, ey.shape[1]
        add = lambda v: np.add.reduceat(v[self._order], self._starts, axis=0)
        if not hasattr(self, "_order"):
            self._order = np.argsort(self.wk, kind="stable")
            self._starts = np.flatnonzero(np.r_[True, np.diff(self.wk[self._order]) != 0])
        ex = self.ex
        return {"n": np.bincount(self.wk, minlength=W).astype(float), "x": add(ex), "xx": add(ex * ex),
                "y": add(ey), "yy": add(ey * ey), "xy": add(ex[:, None] * ey)}


def boot_counts(W: int, draws: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = rng.integers(0, W, size=(draws, W))
    C = np.zeros((draws, W))
    for b in range(draws):
        C[b] = np.bincount(d[b], minlength=W)
    return C


def fast_ci(C: np.ndarray, s: dict) -> dict:
    """Fixed-residual ISO-week block bootstrap of the Pearson of rank residuals (re-centred per draw)."""
    n = C @ s["n"]
    sx, sxx = C @ s["x"], C @ s["xx"]
    sy, syy, sxy = C @ s["y"], C @ s["yy"], C @ s["xy"]
    cov = sxy - sx[:, None] * sy / n[:, None]
    vx = sxx - sx * sx / n
    vy = syy - sy * sy / n[:, None]
    r = cov / np.sqrt(vx[:, None] * vy)
    return {"lo": np.quantile(r, K.BOOT_LO, axis=0), "hi": np.quantile(r, K.BOOT_HI, axis=0),
            "se": r.std(axis=0, ddof=1), "valid": np.isfinite(r).sum(axis=0)}


def route(point: float, lo: float, hi: float, valid: int) -> str:
    if valid < K.MIN_VALID_DRAWS or not np.isfinite(point):
        return K.ROUTE_INVALID
    if lo > 0:
        return K.ROUTE_OPPOSES
    if point < 0 and hi < 0:
        return K.ROUTE_SUPPORTED
    if point < 0:
        return K.ROUTE_UNCERTAIN
    return K.ROUTE_NOT


def canonical_ci(rows: dict, y: np.ndarray, seed: int = K.BOOT_SEED, draws: int = K.BOOT_DRAWS) -> dict:
    """The real run's bootstrap (Unit 1 machinery): whole ISO weeks resampled, every rank recomputed per draw."""
    rng = np.random.default_rng(seed)
    _u, inv = np.unique(rows["week"], return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(inv.max() + 1)]
    w = len(groups)
    out = np.full(draws, np.nan)
    for d in range(draws):
        ix = np.concatenate([groups[i] for i in rng.integers(0, w, size=w)])
        prod = product_term(rows["rp"][ix], rows["ts"][ix])
        r = partial_rank(y[ix], prod, [rows[c][ix] for c in K.PRIMARY_CONTROLS])["rho"]
        out[d] = np.nan if r is None else r
    f = out[np.isfinite(out)]
    return {"lo": float(np.quantile(f, K.BOOT_LO)), "hi": float(np.quantile(f, K.BOOT_HI)),
            "se": float(np.std(f, ddof=1)), "valid": int(f.size)}


def interaction_point(rows: dict, y: np.ndarray) -> float:
    """Unit 1 interaction_b0 on the full sample, through the imported Unit-1 function."""
    s = {"r1": y, "rp": rows["rp"], "ts": rows["ts"], "ret4": rows["ret4"], "rv4": rows["rv4"]}
    return unit1_interaction(s, np.arange(y.size))
