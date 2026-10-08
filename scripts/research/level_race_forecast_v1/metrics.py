"""Evaluation metrics of design §6. Week-cluster bootstrap; numpy only."""

from __future__ import annotations

import numpy as np

from . import constants as K
from .model import fit_logit, logit


def ll_rows(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    return -np.log(P[np.arange(len(y)), y])


def brier_rows(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    Y = np.eye(P.shape[1])[y]
    return ((P - Y) ** 2).sum(axis=1)


class WeekBoot:
    """Week-cluster bootstrap weights shared by every statistic of one evaluation set."""

    def __init__(self, weeks: np.ndarray, *, draws: int = K.BOOT_DRAWS, seed: int = K.BOOT_SEED):
        self.uw, self.inv = np.unique(np.asarray(weeks), return_inverse=True)
        m = self.uw.size
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, m, size=(draws, m))
        self.W = np.zeros((draws, m))
        for d in range(draws):
            self.W[d] = np.bincount(idx[d], minlength=m)
        self.cnt = np.bincount(self.inv, minlength=m).astype(float)

    def mean_ci(self, v: np.ndarray) -> list:
        s = np.bincount(self.inv, weights=v, minlength=self.uw.size)
        b = (self.W @ s) / (self.W @ self.cnt)
        return [float(np.quantile(b, K.CI_ALPHA / 2)), float(np.quantile(b, 1 - K.CI_ALPHA / 2))]

    def row_weights(self, d: int) -> np.ndarray:
        return self.W[d][self.inv]


def recal(p: np.ndarray, y: np.ndarray, w: np.ndarray | None = None) -> tuple[float, float]:
    """logit P(y) = a + b logit p (weighted ML). Weights = bootstrap multiplicities."""
    x = logit(p)
    X = np.column_stack([np.ones_like(x), x])
    beta = fit_logit(X, np.zeros_like(x), y.astype(float), 0.0, np.array([False, False]), w=w)
    return float(beta[0]), float(beta[1])


def auc(score: np.ndarray, y: np.ndarray) -> float | None:
    pos, neg = score[y == 1], score[y == 0]
    if pos.size == 0 or neg.size == 0:
        return None
    allv = np.concatenate([pos, neg])
    ranks = np.argsort(np.argsort(allv, kind="mergesort"), kind="mergesort").astype(float) + 1
    # average ties
    order = np.argsort(allv, kind="mergesort")
    sv = allv[order]
    r = np.empty_like(ranks)
    i = 0
    while i < sv.size:
        j = i
        while j + 1 < sv.size and sv[j + 1] == sv[i]:
            j += 1
        r[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    rp = r[:pos.size].sum()
    return float((rp - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


def reliability(p: np.ndarray, y: np.ndarray) -> list:
    edges = K.RELIABILITY_EDGES
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi)
        out.append({"bin": [lo, min(hi, 1.0)], "n": int(m.sum()),
                    "mean_p": float(p[m].mean()) if m.any() else None,
                    "obs": float(y[m].mean()) if m.any() else None})
    return out


def murphy(P: np.ndarray, y: np.ndarray) -> dict:
    """Stacked one-vs-rest Murphy decomposition on the 5 reliability bins, summed over outcomes."""
    Y = np.eye(P.shape[1])[y]
    rel = res = unc = 0.0
    n = len(y)
    for k in range(P.shape[1]):
        p, o = P[:, k], Y[:, k]
        ob = o.mean()
        unc += ob * (1 - ob)
        for b in reliability(p, o):
            if b["n"]:
                rel += b["n"] * (b["mean_p"] - b["obs"]) ** 2 / n
                res += b["n"] * (b["obs"] - ob) ** 2 / n
    return {"brier": float(brier_rows(P, y).mean()), "reliability": rel, "resolution": res, "uncertainty": unc}


def ece_stacked(P: np.ndarray, y: np.ndarray) -> float:
    Y = np.eye(P.shape[1])[y]
    p, o = P.ravel(), Y.ravel()
    e = 0.0
    for b in reliability(p, o):
        if b["n"]:
            e += b["n"] * abs(b["mean_p"] - b["obs"])
    return float(e / p.size)


def evaluate(P: np.ndarray, y: np.ndarray, weeks: np.ndarray, refs: dict, boot: WeekBoot | None = None,
             slope_ci: bool = True) -> dict:
    """All §6 metrics of one model on one evaluation set. `refs` = {name: P_ref} for skill."""
    boot = boot or WeekBoot(weeks)
    ll = ll_rows(P, y)
    out: dict = {"n": int(len(y)), "weeks": int(np.unique(weeks).size), "logloss": float(ll.mean()),
                 "logloss_ci95": boot.mean_ci(ll)}
    for name, R in refs.items():
        lr = ll_rows(R, y)
        d = lr - ll
        out[f"skill_vs_{name}"] = float(1 - ll.mean() / lr.mean())
        out[f"ll_gain_vs_{name}"] = float(d.mean())
        out[f"ll_gain_vs_{name}_ci95"] = boot.mean_ci(d)
    Y = np.eye(3)[y]
    out["citl_pp"] = {}
    for k, name in enumerate(("BEYOND", "BACK", "NEITHER")):
        dv = Y[:, k] - P[:, k]
        lo, hi = boot.mean_ci(dv)
        out["citl_pp"][name] = [float(100 * dv.mean()), 100 * lo, 100 * hi]
    pR = 1 - P[:, 2]
    yR = (y != 2).astype(int)
    res = y != 2
    pB = P[res, 0] / (P[res, 0] + P[res, 1])
    yB = (y[res] == 0).astype(int)
    heads = {"R": (pR, yR, np.ones(len(y), bool)), "B": (pB, yB, res)}
    out["heads"] = {}
    for h, (p, yy, mask) in heads.items():
        a, b = recal(p, yy)
        hd = {"n": int(len(yy)), "citl_pp": float(100 * (yy - p).mean()), "recal_a": a, "recal_b": b,
              "auc": auc(p, yy), "reliability": reliability(p, yy)}
        if slope_ci:
            A, Bs = [], []
            for d in range(boot.W.shape[0]):
                w = boot.row_weights(d)[mask]
                aa, bb = recal(p, yy, w)
                A.append(aa)
                Bs.append(bb)
            hd["recal_a_ci95"] = [float(np.quantile(A, .025)), float(np.quantile(A, .975))]
            hd["recal_b_ci95"] = [float(np.quantile(Bs, .025)), float(np.quantile(Bs, .975))]
            hd["recal_ci_draws"] = len(A)
        out["heads"][h] = hd
    out["reliability_stacked"] = reliability(P.ravel(), Y.ravel())
    out["brier"] = murphy(P, y)
    lo, hi = K.SHARP_BAND
    out["sharpness"] = {"pB_outside_40_60": float(np.mean((pB < lo) | (pB > hi))) if pB.size else None,
                        "sd": {n: float(P[:, k].std()) for k, n in enumerate(("BEYOND", "BACK", "NEITHER"))}}
    out["ece_stacked_descriptive"] = ece_stacked(P, y)
    return out
