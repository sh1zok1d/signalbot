"""Two-head ridge logit offset by B0 (design §2.3), B1 climatology (§2.2). numpy only."""

from __future__ import annotations

import math
from typing import Optional, Sequence

import numpy as np

from . import constants as K

OUT3 = ("BEYOND", "BACK", "NEITHER")


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), K.OFFSET_CLIP, 1 - K.OFFSET_CLIP)
    return np.log(p / (1 - p))


def sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def floor3(p: np.ndarray, eps: float = K.PROB_FLOOR) -> np.ndarray:
    q = np.maximum(np.asarray(p, dtype=float), eps)
    return q / q.sum(axis=1, keepdims=True)


def fit_logit(X: np.ndarray, off: np.ndarray, y: np.ndarray, lam: float, pen: np.ndarray,
              iters: int = 100, tol: float = 1e-10, w: np.ndarray | None = None) -> np.ndarray:
    """argmin -sum(w*loglik)/sum(w) + lam/2 * ||beta[pen]||^2, Newton steps with step halving."""
    n0, p = X.shape
    w = np.ones(n0) if w is None else np.asarray(w, dtype=float)
    n = float(w.sum())
    beta = np.zeros(p)
    P = np.diag(pen.astype(float)) * lam

    def obj(b):
        z = off + X @ b
        ll = np.sum(w * (y * z - np.logaddexp(0.0, z)))
        return -ll / n + 0.5 * b @ P @ b

    f = obj(beta)
    for _ in range(iters):
        mu = sigmoid(off + X @ beta)
        g = -X.T @ (w * (y - mu)) / n + P @ beta
        H = (X.T * (w * mu * (1 - mu))) @ X / n + P + 1e-12 * np.eye(p)
        step = np.linalg.solve(H, g)
        t = 1.0
        while True:
            nb = beta - t * step
            nf = obj(nb)
            if nf <= f + 1e-15 or t < 1e-6:
                break
            t /= 2
        if abs(f - nf) < tol:
            beta, f = nb, nf
            break
        beta, f = nb, nf
    return beta


def tercile_edges(sigma: np.ndarray) -> tuple[float, float]:
    s = np.asarray(sigma, dtype=float)
    return float(np.quantile(s, 1 / 3)), float(np.quantile(s, 2 / 3))


def sigma_t(sigma: np.ndarray, edges: tuple[float, float]) -> np.ndarray:
    s = np.asarray(sigma, dtype=float)
    return np.where(s < edges[0], -1.0, np.where(s < edges[1], 0.0, 1.0))


def design(rows: Sequence[dict], spec: Sequence[str], edges: Optional[tuple[float, float]],
           extra: Optional[dict] = None) -> np.ndarray:
    cols = []
    for term in spec:
        if term == "1":
            cols.append(np.ones(len(rows)))
        elif term == "T15":
            cols.append(np.array([r["landmark"] == "T15" for r in rows], dtype=float))
        elif term == "FAM_WM":
            cols.append(np.array([r["family"] != "DAY" for r in rows], dtype=float))
        elif term == "WEEK":
            cols.append(np.array([r["family"] == "WEEK" for r in rows], dtype=float))
        elif term == "MONTH":
            cols.append(np.array([r["family"] == "MONTH" for r in rows], dtype=float))
        elif term == "SIDE":
            cols.append(np.array([r["struct_side"] for r in rows], dtype=float))
        elif term == "SIGMA_T":
            cols.append(sigma_t(np.array([r["sigma"] for r in rows]), edges))
        elif term == K.C1_TERM:
            cols.append(np.asarray(extra[K.C1_TERM], dtype=float))
        else:
            raise KeyError(term)
    return np.column_stack(cols)


def b0_matrix(rows: Sequence[dict]) -> np.ndarray:
    return np.array([[r["b0_beyond"], r["b0_back"], r["b0_neither"]] for r in rows], dtype=float)


def y_index(rows: Sequence[dict]) -> np.ndarray:
    return np.array([OUT3.index(r["outcome"]) for r in rows])


def head_offsets(b0: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    res = b0[:, 0] + b0[:, 1]
    return logit(res), logit(b0[:, 0] / res)


class TwoHead:
    """Fitted M1-family model. `beta_r`/`beta_b` follow `spec_r`/`spec_b`."""

    def __init__(self, spec_r, spec_b, beta_r, beta_b, edges, lam, c1_moments=None):
        self.spec_r, self.spec_b = tuple(spec_r), tuple(spec_b)
        self.beta_r, self.beta_b = np.asarray(beta_r), np.asarray(beta_b)
        self.edges, self.lam, self.c1_moments = edges, lam, c1_moments

    def predict(self, rows, extra=None) -> np.ndarray:
        b0 = b0_matrix(rows)
        o_r, o_b = head_offsets(b0)
        pr = sigmoid(o_r + design(rows, self.spec_r, self.edges, extra) @ self.beta_r)
        pb = sigmoid(o_b + design(rows, self.spec_b, self.edges, extra) @ self.beta_b)
        return floor3(np.column_stack([pr * pb, pr * (1 - pb), 1 - pr]))

    def to_json(self) -> dict:
        return {"spec_r": list(self.spec_r), "spec_b": list(self.spec_b),
                "beta_r": [float(v) for v in self.beta_r], "beta_b": [float(v) for v in self.beta_b],
                "sigma_tercile_edges": None if self.edges is None else list(self.edges),
                "lambda_per_event": self.lam, "c1_moments": self.c1_moments}


def fit_two_head(rows, spec_r, spec_b, lam, *, edges, extra=None, rows_b_mask=None) -> TwoHead:
    b0 = b0_matrix(rows)
    y = y_index(rows)
    o_r, o_b = head_offsets(b0)
    Xr = design(rows, spec_r, edges, extra)
    pen_r = np.array([t != "1" for t in spec_r])
    beta_r = fit_logit(Xr, o_r, (y != 2).astype(float), lam, pen_r)
    res = y != 2
    if rows_b_mask is not None:
        res = res & rows_b_mask
    Xb = design(rows, spec_b, edges, extra)[res]
    pen_b = np.array([t != "1" for t in spec_b])
    beta_b = fit_logit(Xb, o_b[res], (y[res] == 0).astype(float), lam, pen_b)
    return TwoHead(spec_r, spec_b, beta_r, beta_b, edges, lam)


def fit_b1(rows) -> dict:
    """Per landmark, family x structural side: Dirichlet(1,1,1)-smoothed outcome shares."""
    tab: dict = {}
    for r in rows:
        k = (r["landmark"], r["family"], int(r["struct_side"]))
        c = tab.setdefault(k, np.ones(3))
        c[OUT3.index(r["outcome"])] += 1
    return {k: (v / v.sum()).tolist() for k, v in tab.items()}


def predict_b1(b1: dict, rows) -> np.ndarray:
    out = []
    for r in rows:
        k = (r["landmark"], r["family"], int(r["struct_side"]))
        out.append(b1.get(k, [1 / 3, 1 / 3, 1 / 3]))
    return floor3(np.array(out))
