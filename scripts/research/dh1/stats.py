"""DH1 inference: linear probability model, cluster bootstrap, Holm, Brier skill, epoch
heterogeneity. Pure numpy; works on any (X, y) and never reads data itself.

The cluster unit is the ISO week cut at epoch boundaries, so every cluster sits in one epoch.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K

S_COL = 1  # the state column of the design matrix


def cluster_ids(rows: list) -> np.ndarray:
    keys = [(r["WEEK"], r["EPOCH"]) for r in rows]
    uniq = {k: n for n, k in enumerate(sorted(set(keys)))}
    return np.array([uniq[k] for k in keys], dtype=np.int64)


def cluster_epochs(rows: list, cid: np.ndarray) -> list:
    out = [None] * (int(cid.max()) + 1 if cid.size else 0)
    for r, c in zip(rows, cid):
        out[c] = r["EPOCH"]
    return out


def aggregates(X: np.ndarray, y: np.ndarray, cid: np.ndarray) -> tuple:
    """Per-cluster X'X (C x k x k), X'y (C x k) and arm counts (C x 2)."""
    C, k = int(cid.max()) + 1, X.shape[1]
    xtx = np.zeros((C, k, k))
    xty = np.zeros((C, k))
    arms = np.zeros((C, 2))
    np.add.at(xtx, cid, X[:, :, None] * X[:, None, :])
    np.add.at(xty, cid, X * y[:, None])
    np.add.at(arms, (cid, X[:, S_COL].astype(int)), 1.0)
    return xtx, xty, arms


def solve(xtx: np.ndarray, xty: np.ndarray) -> np.ndarray:
    return np.linalg.pinv(xtx) @ xty


def fit(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return solve(X.T @ X, X.T @ y)


def bootstrap_beta(xtx: np.ndarray, xty: np.ndarray, draws: int, rng) -> np.ndarray:
    """State coefficient under resampling of clusters with replacement."""
    C = xtx.shape[0]
    W = rng.multinomial(C, np.full(C, 1.0 / C), size=draws).astype(float)
    A = np.einsum("bc,cij->bij", W, xtx)
    v = np.einsum("bc,ci->bi", W, xty)
    beta = np.linalg.pinv(A) @ v[:, :, None]
    return beta[:, S_COL, 0]


def boot_p(draws: np.ndarray) -> float:
    d = draws[np.isfinite(draws)]
    p = 2.0 * min(float(np.mean(d <= 0)), float(np.mean(d >= 0)))
    return float(min(1.0, max(p, 1.0 / d.size)))


def holm(pvals: dict) -> dict:
    items = sorted(((p, k) for k, p in pvals.items() if p is not None), key=lambda x: x[0])
    m, running, out = len(items), 0.0, {}
    for r, (p, k) in enumerate(items):
        running = max(running, min(1.0, (m - r) * p))
        out[k] = running
    return out


def brier(pred: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(pred, *K.PRED_CLIP)
    return float(np.sum((p - y) ** 2))


def crossfit_bss(X: np.ndarray, y: np.ndarray, epochs: list) -> Optional[float]:
    """Leave-one-epoch-out Brier skill of the model with the state against the model without it."""
    epochs = np.asarray(epochs)
    keep = [c for c in range(X.shape[1]) if c != S_COL]
    bf = bn = 0.0
    for e in sorted(set(epochs.tolist())):
        tr, te = epochs != e, epochs == e
        if te.sum() == 0 or tr.sum() == 0:
            continue
        bf += brier(X[te] @ fit(X[tr], y[tr]), y[te])
        bn += brier(X[te][:, keep] @ fit(X[tr][:, keep], y[tr]), y[te])
    return None if bn <= 0 else 1.0 - bf / bn


def frozen_bss(X_fit: np.ndarray, y_fit: np.ndarray, X_new: np.ndarray, y_new: np.ndarray) -> Optional[float]:
    keep = [c for c in range(X_fit.shape[1]) if c != S_COL]
    bf = brier(X_new @ fit(X_fit, y_fit), y_new)
    bn = brier(X_new[:, keep] @ fit(X_fit[:, keep], y_fit), y_new)
    return None if bn <= 0 else 1.0 - bf / bn


# ---------------------------------------------------------------- epoch heterogeneity
def epoch_estimates(xtx, xty, arms, c_epoch: list, epoch_names: list, rng, draws: int) -> dict:
    out = {}
    c_epoch = np.asarray(c_epoch)
    for e in epoch_names:
        m = c_epoch == e
        if m.sum() == 0 or arms[m, 0].sum() < K.MIN_EPOCH_ARM or arms[m, 1].sum() < K.MIN_EPOCH_ARM:
            out[e] = None
            continue
        b = float(solve(xtx[m].sum(0), xty[m].sum(0))[S_COL])
        bd = bootstrap_beta(xtx[m], xty[m], draws, rng)
        se = float(np.std(bd[np.isfinite(bd)], ddof=1))
        out[e] = {"BETA": b, "SE": se, "N_STATE": int(arms[m, 1].sum()), "N_COMPARATOR": int(arms[m, 0].sum())}
    return out


def het_test(xtx, xty, arms, c_epoch: list, epoch_names: list, pooled: float, rng, *,
             se_draws: int = K.EPOCH_BOOT_DRAWS, perms: int = K.HET_PERM_DRAWS) -> dict:
    est = epoch_estimates(xtx, xty, arms, c_epoch, epoch_names, rng, se_draws)
    defined = [e for e in epoch_names if est[e] is not None and est[e]["SE"] > 0]
    if len(defined) < 3:
        return {"STATUS": "NOT_ASSESSABLE", "REASON": "fewer than 3 epochs with an estimate", "EPOCHS": est}
    w = np.array([1.0 / est[e]["SE"] ** 2 for e in defined])
    b = np.array([est[e]["BETA"] for e in defined])
    bbar = float(np.sum(w * b) / np.sum(w))
    q_obs = float(np.sum(w * (b - bbar) ** 2))
    c_epoch = np.asarray(c_epoch)
    pool_mask = np.isin(c_epoch, defined)
    idx = np.flatnonzero(pool_mask)
    labels = c_epoch[idx]
    q_null = np.empty(perms)
    for p in range(perms):
        perm = rng.permutation(labels)
        bp = np.empty(len(defined))
        for k, e in enumerate(defined):
            sel = idx[perm == e]
            bp[k] = solve(xtx[sel].sum(0), xty[sel].sum(0))[S_COL]
        bb = float(np.sum(w * bp) / np.sum(w))
        q_null[p] = float(np.sum(w * (bp - bb) ** 2))
    p_het = float((1 + np.sum(q_null >= q_obs)) / (1 + perms))
    opposite = []
    for e in defined:
        be, se = est[e]["BETA"], est[e]["SE"]
        if np.sign(be) != np.sign(pooled) and pooled != 0:
            p_one = 0.5 * math.erfc(abs(be) / se / math.sqrt(2))
            if p_one < K.OPPOSITE_ALPHA:
                opposite.append(e)
    if p_het >= K.HET_ALPHA:
        status = "PASS"
    elif not opposite:
        status = "PASS_MAGNITUDE_VARIES_BY_EPOCH"
    else:
        status = "FAIL_HETEROGENEOUS_UNEXPLAINED"
    return {"STATUS": status, "Q": q_obs, "P_HET": p_het, "OPPOSITE_EPOCHS": opposite, "EPOCHS": est}


# ---------------------------------------------------------------- planning (outcome-blind)
def z(p: float) -> float:
    from statistics import NormalDist
    return NormalDist().inv_cdf(p)


def planning_se(X: np.ndarray) -> float:
    inv = np.linalg.pinv(X.T @ X)
    return math.sqrt(0.25 * inv[S_COL, S_COL] * K.DEFF_PLANNING)


def mde(se: float, alpha: float, power: float = 0.8) -> float:
    return (z(1 - alpha / 2) + z(power)) * se


def power_at(effect: float, se: float, alpha: float) -> float:
    from statistics import NormalDist
    nd = NormalDist()
    zc = z(1 - alpha / 2)
    return float(nd.cdf(effect / se - zc) + nd.cdf(-effect / se - zc))


def het_power(X: np.ndarray, cid: np.ndarray, c_epoch: list, epoch_names: list, seed: int) -> float:
    """Share of simulated datasets (Bernoulli outcomes, half of the epochs at each of the two
    effects of HET_POWER_EFFECTS) in which the heterogeneity test rejects. Uses only the design."""
    rng = np.random.default_rng(seed)
    ev_epoch = np.asarray(c_epoch)[cid]
    eff = {e: K.HET_POWER_EFFECTS[k % 2] for k, e in enumerate(epoch_names)}
    p_true = 0.5 + np.array([eff.get(e, 0.0) for e in ev_epoch]) * (X[:, S_COL] - 0.5)
    rej = 0
    for _ in range(K.HET_POWER_SIMS):
        y = (rng.random(X.shape[0]) < p_true).astype(float)
        xtx, xty, arms = aggregates(X, y, cid)
        pooled = float(solve(xtx.sum(0), xty.sum(0))[S_COL])
        res = het_test(xtx, xty, arms, c_epoch, epoch_names, pooled, rng, se_draws=100, perms=K.HET_POWER_PERMS)
        rej += res.get("P_HET", 1.0) < K.HET_ALPHA
    return rej / K.HET_POWER_SIMS
