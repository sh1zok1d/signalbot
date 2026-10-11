"""Unpenalized logistic regression and the frozen route.

This module does not load a market series. Market evaluation stays behind the owner go.
"""

from __future__ import annotations

import numpy as np

from . import constants as K


class ImplementationInvalid(RuntimeError):
    pass


def fit_scaler(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Training mean and population standard deviation. A zero scale is invalid."""
    x = np.asarray(x, dtype=np.float64)
    mu = x.mean(axis=0)
    sd = x.std(axis=0)
    if not np.all(np.isfinite(mu)) or not np.all(np.isfinite(sd)) or np.any(sd <= 0.0):
        raise ImplementationInvalid("SCALER_DEGENERATE")
    return mu, sd


def apply_scaler(x: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    return (np.asarray(x, dtype=np.float64) - mu) / sd


def sigmoid(z: np.ndarray) -> np.ndarray:
    clipped = np.clip(np.asarray(z, dtype=np.float64), -K.SIGMOID_CLIP, K.SIGMOID_CLIP)
    return 1.0 / (1.0 + np.exp(-clipped))


def fit_logistic(x_std: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Newton–Raphson on the binomial log-likelihood. No penalty term is added."""
    x_std = np.asarray(x_std, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    n = int(y.shape[0])
    design = np.column_stack([np.ones(n, dtype=np.float64), x_std])
    beta = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(K.MAX_ITERATIONS):
        prob = sigmoid(design @ beta)
        grad = design.T @ (prob - y)
        if float(np.max(np.abs(grad))) < K.GRADIENT_TOLERANCE:
            return beta
        weight = prob * (1.0 - prob)
        hess = design.T @ (design * weight[:, None])
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError as exc:
            raise ImplementationInvalid("SINGULAR_HESSIAN") from exc
        beta = beta - step
    prob = sigmoid(design @ beta)
    grad = design.T @ (prob - y)
    if float(np.max(np.abs(grad))) < K.GRADIENT_TOLERANCE:
        return beta
    raise ImplementationInvalid("LOGISTIC_DID_NOT_CONVERGE")


def predict(x_std: np.ndarray, beta: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(x_std.shape[0], dtype=np.float64), np.asarray(x_std, dtype=np.float64)])
    return sigmoid(design @ np.asarray(beta, dtype=np.float64))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    return float(np.mean((np.asarray(prob, dtype=np.float64) - np.asarray(y, dtype=np.float64)) ** 2))


def log_loss(y: np.ndarray, prob: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    p = np.clip(np.asarray(prob, dtype=np.float64), K.LOGLOSS_CLIP, 1.0 - K.LOGLOSS_CLIP)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def assign_route(delta_brier: float | None, delta_logloss: float | None, brier_hi: float | None,
                 slope: float | None, valid_draws: int, implementation_ok: bool) -> str:
    """Frozen route. AUROC is not an input."""
    missing = delta_brier is None or delta_logloss is None or brier_hi is None or slope is None
    if (not implementation_ok) or missing or int(valid_draws) < K.MIN_VALID_DRAWS:
        return K.ROUTE_INVALID
    improved = float(delta_brier) < 0.0 and float(delta_logloss) < 0.0
    interval_below = float(brier_hi) < 0.0
    slope_ok = float(slope) >= 0.0
    if improved and interval_below and slope_ok:
        return K.ROUTE_SUPPORTED
    if improved:
        return K.ROUTE_UNCERTAIN
    return K.ROUTE_NONE
