"""Exact (full Newton-IRLS) fits for V2: weighted rows, per-slope ridge, optional offset and intercept, standardization
on training rows only (weighted mean and sd), clip +-5. With unit weights, one ridge value 1.0, an intercept and no
offset it is adaptive_b1_forecast_v1.model.fit (tested). Used to validate the vectorized surrogate on synthetic data."""
from __future__ import annotations

import numpy as np

from . import engine as EN

CLIP_Z = 5.0
MAX_ITER = 50
TOL = 1e-10


def fit(x: np.ndarray, y: np.ndarray, lam, w: np.ndarray | None = None, offset: np.ndarray | None = None,
        intercept: bool = True) -> dict:
    n, k = x.shape
    w = np.ones(n) if w is None else w
    off = np.zeros(n) if offset is None else offset
    sw = w.sum()
    mu = (w[:, None] * x).sum(0) / sw
    sd = np.sqrt((w[:, None] * (x - mu) ** 2).sum(0) / sw)
    sd = np.where(sd > 0, sd, 1.0)
    z = np.clip((x - mu) / sd, -CLIP_Z, CLIP_Z)
    d = np.column_stack([np.ones(n), z]) if intercept else z
    pen = np.diag(np.concatenate([[0.0], np.asarray(lam, float)]) if intercept else np.asarray(lam, float))
    beta = np.zeros(d.shape[1])
    if intercept:
        ybar = float(np.clip((w * y).sum() / sw, 1e-6, 1 - 1e-6))
        beta[0] = np.log(ybar / (1 - ybar))
    for _ in range(MAX_ITER):
        m = 1 / (1 + np.exp(-(off + d @ beta)))
        g = d.T @ (w * (y - m)) - pen @ beta
        h = d.T @ (d * (w * m * (1 - m))[:, None]) + pen
        step = np.linalg.solve(h, g)
        beta = beta + step
        if np.max(np.abs(step)) < TOL:
            break
    return {"mu": mu, "sd": sd, "beta": beta, "intercept": intercept}


def eta(m: dict, x: np.ndarray, offset: np.ndarray | None = None) -> np.ndarray:
    z = np.clip((x - m["mu"]) / m["sd"], -CLIP_Z, CLIP_Z)
    e = (m["beta"][0] + z @ m["beta"][1:]) if m["intercept"] else z @ m["beta"]
    return e if offset is None else offset + e


def predict_block(g: EN.Geometry, y: np.ndarray, v: int, s: int, spec: EN.Spec, ix: np.ndarray) -> np.ndarray:
    """Exact prediction of one system for the block rows ix (one replication y over all rows)."""
    b1 = EN.b1_spec()
    a, b = g.train_range(v, s, spec if spec.structure != "OFFSET" else spec)
    tr = np.arange(a, b)
    w = None
    if spec.memory == "EWMA":
        w = np.exp2((g.t[tr] - s) / (spec.weeks * EN.K1.WEEK_MS))
    if spec.structure == "STD":
        c = list(spec.cols)
        m = fit(g.X[np.ix_(tr, c)], y[tr], spec.lam, w)
        return 1 / (1 + np.exp(-eta(m, g.X[np.ix_(ix, c)])))
    ae, be = g.train_range(v, s, b1)
    tre = np.arange(ae, be)
    c1 = list(b1.cols)
    mb = fit(g.X[np.ix_(tre, c1)], y[tre], b1.lam)
    c = list(spec.cols)
    off_tr = eta(mb, g.X[np.ix_(tr, c1)])
    mo = fit(g.X[np.ix_(tr, c)], y[tr], spec.lam, w, offset=off_tr, intercept=False)
    return 1 / (1 + np.exp(-eta(mo, g.X[np.ix_(ix, c)], offset=eta(mb, g.X[np.ix_(ix, c1)]))))
