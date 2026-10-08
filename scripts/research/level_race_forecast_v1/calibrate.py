"""Batched Bayesian logistic recalibration per head with class intercepts and a shared slope
(design §7, §8a). MAP with a Gaussian prior; Laplace covariance. Prior numbers are [F3].

Per head:  logit p' = a_class + b * logit p,  classes GENERIC, LEVEL_T0, LEVEL_T15.
Prior:     a_GENERIC ~ N(m_a, s_a^2), b ~ N(m_b, s_b^2), a_LEVEL_x ~ N(a_GENERIC, s_level^2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .model import logit, sigmoid

CLASSES = ("GENERIC", "LEVEL_T0", "LEVEL_T15")


@dataclass
class Prior:
    m_a: float = 0.0
    s_a: float = 0.5
    m_b: float = 1.0
    s_b: float = 0.25
    s_level: float = 0.5          # [F3]; R2 diagnostic informs it


@dataclass
class HeadCalibrator:
    prior: Prior = field(default_factory=Prior)
    theta: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 0.0, 1.0]))  # aG, aT0, aT15, b
    cov: np.ndarray | None = None
    version: int = 0

    def _design(self, cls: Sequence[str], p: np.ndarray) -> np.ndarray:
        x = logit(p)
        X = np.zeros((len(p), 4))
        for i, c in enumerate(cls):
            X[i, CLASSES.index(c)] = 1.0
        X[:, 3] = x
        return X

    def _prior_terms(self, th):
        pr = self.prior
        aG, a0, a15, b = th
        f = ((aG - pr.m_a) / pr.s_a) ** 2 + ((b - pr.m_b) / pr.s_b) ** 2 \
            + ((a0 - aG) / pr.s_level) ** 2 + ((a15 - aG) / pr.s_level) ** 2
        Q = np.zeros((4, 4))
        Q[0, 0] = 1 / pr.s_a ** 2 + 2 / pr.s_level ** 2
        Q[3, 3] = 1 / pr.s_b ** 2
        for k in (1, 2):
            Q[k, k] = 1 / pr.s_level ** 2
            Q[0, k] = Q[k, 0] = -1 / pr.s_level ** 2
        mu_shift = np.array([pr.m_a / pr.s_a ** 2, 0.0, 0.0, pr.m_b / pr.s_b ** 2])
        return 0.5 * f, Q, mu_shift

    def fit(self, cls: Sequence[str], p: np.ndarray, y: np.ndarray) -> "HeadCalibrator":
        """MAP on all resolved records given (prequential use: pass only records resolved before t)."""
        X = self._design(cls, np.asarray(p, float))
        y = np.asarray(y, float)
        th = self.theta.copy()
        for _ in range(100):
            mu = sigmoid(X @ th)
            _, Q, ms = self._prior_terms(th)
            g = -X.T @ (y - mu) + Q @ th - ms
            H = (X.T * (mu * (1 - mu))) @ X + Q
            step = np.linalg.solve(H, g)
            th = th - step
            if np.max(np.abs(step)) < 1e-10:
                break
        mu = sigmoid(X @ th)
        _, Q, _ = self._prior_terms(th)
        H = (X.T * (mu * (1 - mu))) @ X + Q
        self.theta, self.cov, self.version = th, np.linalg.inv(H), self.version + 1
        return self

    def apply(self, cls: Sequence[str], p: np.ndarray) -> np.ndarray:
        return sigmoid(self._design(cls, np.asarray(p, float)) @ self.theta)


def published_from_heads(P: np.ndarray, cls: Sequence[str], cal_r: HeadCalibrator, cal_b: HeadCalibrator,
                         *, use_level_intercepts: bool) -> np.ndarray:
    """Three outcomes rebuilt from the calibrated heads. Case B / fallback: GENERIC intercept only."""
    cls_used = list(cls) if use_level_intercepts else ["GENERIC"] * len(cls)
    pR = cal_r.apply(cls_used, 1 - P[:, 2])
    pB = cal_b.apply(cls_used, P[:, 0] / (P[:, 0] + P[:, 1]))
    out = np.column_stack([pR * pB, pR * (1 - pB), 1 - pR])
    out = np.maximum(out, 0.001)
    return out / out.sum(axis=1, keepdims=True)


def prequential(week_of_issue: np.ndarray, week_resolved: np.ndarray, cls: Sequence[str], P: np.ndarray,
                y: np.ndarray, prior: Prior, *, use_level_intercepts: bool) -> np.ndarray:
    """Published probabilities: each week's calibrator uses only records resolved in earlier weeks."""
    out = np.zeros_like(P)
    cls = np.asarray(cls)
    yR = (y != 2).astype(float)
    res = y != 2
    pB_raw = P[:, 0] / (P[:, 0] + P[:, 1])
    for wk in np.unique(week_of_issue):
        known = week_resolved < wk
        cr, cb = HeadCalibrator(prior=prior), HeadCalibrator(prior=prior)
        if known.any():
            cr.fit(cls[known], 1 - P[known, 2], yR[known])
            kb = known & res
            if kb.any():
                cb.fit(cls[kb], pB_raw[kb], (y[kb] == 0).astype(float))
        m = week_of_issue == wk
        out[m] = published_from_heads(P[m], cls[m], cr, cb, use_level_intercepts=use_level_intercepts)
    return out
