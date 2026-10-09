"""Frozen preprocessing and the ridge logistic model (Newton-IRLS). Scaling is fitted on training rows only."""
from __future__ import annotations

import hashlib

import numpy as np

from . import constants as K


def design(rows: dict, ix: np.ndarray) -> np.ndarray:
    """x = [RP4H - 0.5, RET_4H/RV_4H, RET_1H/RV_4H, RET_15M/RV_4H, log RV_4H] (all five B1 quantities)."""
    rv = rows["rv4"][ix]
    return np.column_stack([rows["rp"][ix] - 0.5, rows["ret4"][ix] / rv, rows["ret1h"][ix] / rv,
                            rows["ret15"][ix] / rv, np.log(rv)])


def fit(x: np.ndarray, y: np.ndarray) -> dict:
    mu, sd = x.mean(axis=0), x.std(axis=0)
    sd = np.where(sd > 0, sd, 1.0)
    z = np.clip((x - mu) / sd, -K.CLIP_Z, K.CLIP_Z)
    n, p = z.shape
    d = np.column_stack([np.ones(n), z])
    pen = K.RIDGE * np.eye(p + 1)
    pen[0, 0] = 0.0
    ybar = float(np.clip(y.mean(), 1e-6, 1 - 1e-6))
    beta = np.zeros(p + 1)
    beta[0] = np.log(ybar / (1 - ybar))
    for _ in range(K.IRLS_MAX_ITER):
        eta = d @ beta
        m = 1.0 / (1.0 + np.exp(-eta))
        w = m * (1 - m)
        g = d.T @ (y - m) - pen @ beta
        h = d.T @ (d * w[:, None]) + pen
        step = np.linalg.solve(h, g)
        beta = beta + step
        if np.max(np.abs(step)) < K.IRLS_TOL:
            break
    return {"mu": mu, "sd": sd, "beta": beta}


def predict(m: dict, x: np.ndarray) -> np.ndarray:
    z = np.clip((x - m["mu"]) / m["sd"], -K.CLIP_Z, K.CLIP_Z)
    eta = m["beta"][0] + z @ m["beta"][1:]
    return 1.0 / (1.0 + np.exp(-eta))


def coef_hash(m: dict) -> str:
    return hashlib.sha256(np.concatenate([m["mu"], m["sd"], m["beta"]]).astype("<f8").tobytes()).hexdigest()[:16]
