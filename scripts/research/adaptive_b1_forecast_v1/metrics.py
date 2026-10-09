"""Loss metrics, the ISO-week block bootstrap of loss differences, and secondary calibration diagnostics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import constants as K


def brier(p, y):
    return (p - y) ** 2


def logloss(p, y):
    p = np.clip(p, K.P_CLIP, 1 - K.P_CLIP)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def weeks_of(close_ms):
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    return iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)


def boot_diffs(loss: dict, pairs: list, weeks: np.ndarray, seed: int = K.BOOT_SEED) -> dict:
    """Mean-loss differences (a - b) with an ISO-week block bootstrap (whole weeks resampled; ratio of week sums)."""
    _u, inv = np.unique(weeks, return_inverse=True)
    w = int(inv.max()) + 1
    cnt = np.bincount(inv, minlength=w).astype(float)
    sums = {k: np.bincount(inv, weights=v, minlength=w) for k, v in loss.items()}
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, w, size=(K.BOOT_DRAWS, w))
    n = cnt[draws].sum(axis=1)
    out = {}
    for a, b in pairs:
        d = (sums[a][draws].sum(axis=1) - sums[b][draws].sum(axis=1)) / n
        point = float((sums[a].sum() - sums[b].sum()) / cnt.sum())
        f = d[np.isfinite(d)]
        out[f"{a}-{b}"] = {"point": point, "lo": float(np.quantile(f, K.BOOT_LO)), "hi": float(np.quantile(f, K.BOOT_HI)),
                           "se": float(np.std(f, ddof=1)), "valid": int(f.size), "draws": K.BOOT_DRAWS}
    return out


def auroc(p, y):
    from scripts.research.rp4h_bitmex_temporal_v1.parent import average_ranks_fast
    r = average_ranks_fast(p)
    n1 = y.sum()
    n0 = y.size - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else None


def calibration(p, y):
    """Intercept and slope of y ~ a + b * logit(p) (plain IRLS)."""
    lp = np.log(np.clip(p, K.P_CLIP, 1 - K.P_CLIP) / (1 - np.clip(p, K.P_CLIP, 1 - K.P_CLIP)))
    d = np.column_stack([np.ones(p.size), lp])
    beta = np.zeros(2)
    for _ in range(50):
        m = 1 / (1 + np.exp(-(d @ beta)))
        w = m * (1 - m)
        step = np.linalg.solve(d.T @ (d * w[:, None]) + 1e-12 * np.eye(2), d.T @ (y - m))
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return {"intercept": float(beta[0]), "slope": float(beta[1])}


def reliability(p, y, bins: int = K.RELIABILITY_BINS):
    edges = np.quantile(p, np.linspace(0, 1, bins + 1)[1:-1])
    b = np.digitize(p, edges)
    rows, ece = [], 0.0
    for k in range(bins):
        m = b == k
        if not m.any():
            continue
        mp, my = float(p[m].mean()), float(y[m].mean())
        rows.append({"bin": k + 1, "n": int(m.sum()), "mean_p": mp, "observed_up": my})
        ece += m.mean() * abs(mp - my)
    return {"bins": rows, "ece": float(ece)}
