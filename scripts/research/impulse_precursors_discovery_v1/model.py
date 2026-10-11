"""Unpenalized logistic pieces. This module does not load a market series."""

from __future__ import annotations

import numpy as np

from . import constants as K


class ImplementationInvalid(RuntimeError):
    pass


def fit_scaler(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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
    """Newton–Raphson. No penalty and no fallback solver."""
    x_std = np.asarray(x_std, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x_std.ndim == 1:
        x_std = x_std.reshape(-1, 1)
    design = np.column_stack([np.ones(y.shape[0], dtype=np.float64), x_std])
    beta = np.zeros(design.shape[1], dtype=np.float64)
    for _ in range(K.MAX_ITERATIONS):
        prob = sigmoid(design @ beta)
        grad = design.T @ (prob - y)
        weight = prob * (1.0 - prob)
        step = _identified_step(design, weight, grad)
        if float(np.max(np.abs(grad))) < K.GRADIENT_TOLERANCE:
            return beta
        beta = beta - step
    prob = sigmoid(design @ beta)
    grad = design.T @ (prob - y)
    weight = prob * (1.0 - prob)
    _identified_step(design, weight, grad)
    if float(np.max(np.abs(grad))) < K.GRADIENT_TOLERANCE:
        return beta
    raise ImplementationInvalid("LOGISTIC_DID_NOT_CONVERGE")


def _identified_step(design: np.ndarray, weight: np.ndarray, grad: np.ndarray) -> np.ndarray:
    """Reject a singular Hessian. A zero gradient on a non-identified design is not a fit."""
    hess = design.T @ (design * weight[:, None])
    if not np.all(np.isfinite(hess)):
        raise ImplementationInvalid("SINGULAR_HESSIAN")
    sign, logdet = np.linalg.slogdet(hess)
    if sign == 0.0 or not np.isfinite(logdet):
        raise ImplementationInvalid("SINGULAR_HESSIAN")
    try:
        step = np.linalg.solve(hess, grad)
    except np.linalg.LinAlgError as exc:
        raise ImplementationInvalid("SINGULAR_HESSIAN") from exc
    if not np.all(np.isfinite(step)):
        raise ImplementationInvalid("SINGULAR_HESSIAN")
    return step


def predict(x_std: np.ndarray, beta: np.ndarray) -> np.ndarray:
    x_std = np.asarray(x_std, dtype=np.float64)
    if x_std.ndim == 1:
        x_std = x_std.reshape(-1, 1)
    design = np.column_stack([np.ones(x_std.shape[0], dtype=np.float64), x_std])
    return sigmoid(design @ np.asarray(beta, dtype=np.float64))


def brier(y: np.ndarray, prob: np.ndarray) -> float:
    return float(np.mean((np.asarray(prob, dtype=np.float64) - np.asarray(y, dtype=np.float64)) ** 2))


def log_loss(y: np.ndarray, prob: np.ndarray) -> float:
    y = np.asarray(y, dtype=np.float64)
    p = np.clip(np.asarray(prob, dtype=np.float64), K.LOGLOSS_CLIP, 1.0 - K.LOGLOSS_CLIP)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def calibration_coefficients(y: np.ndarray, prob: np.ndarray) -> tuple[float, float]:
    p = np.clip(np.asarray(prob, dtype=np.float64), K.CALIBRATION_LOGIT_CLIP, 1.0 - K.CALIBRATION_LOGIT_CLIP)
    logit = np.log(p / (1.0 - p)).reshape(-1, 1)
    if not np.all(np.isfinite(logit)):
        raise ImplementationInvalid("NON_FINITE_LOGIT")
    beta = fit_logistic(logit, np.asarray(y, dtype=np.float64))
    return float(beta[1]), float(beta[0])


def auroc(y: np.ndarray, prob: np.ndarray) -> float | None:
    y = np.asarray(y, dtype=np.float64)
    prob = np.asarray(prob, dtype=np.float64)
    n_pos = float(np.sum(y == 1.0))
    n_neg = float(y.size - n_pos)
    if n_pos == 0.0 or n_neg == 0.0:
        return None
    order = np.argsort(prob, kind="mergesort")
    sorted_p = prob[order]
    ranks = np.empty(y.size, dtype=np.float64)
    start = 0
    while start < y.size:
        stop = start + 1
        while stop < y.size and sorted_p[stop] == sorted_p[start]:
            stop += 1
        ranks[order[start:stop]] = 0.5 * ((start + 1) + stop)
        start = stop
    sum_pos = float(ranks[y == 1.0].sum())
    return (sum_pos - n_pos * (n_pos + 1.0) / 2.0) / (n_pos * n_neg)


def assign_verdict(
    delta_brier: float | None,
    delta_logloss: float | None,
    brier_hi: float | None,
    logloss_hi: float | None,
    slope: float | None,
    dev_delta_brier: float | None,
    diag_delta_brier: float | None,
    valid_draws: int,
    implementation_ok: bool,
) -> str:
    missing = any(value is None for value in (
        delta_brier, delta_logloss, brier_hi, logloss_hi, slope, dev_delta_brier, diag_delta_brier,
    ))
    if (not implementation_ok) or missing or int(valid_draws) < K.MIN_VALID_DRAWS:
        return K.ROUTE_INVALID
    if float(delta_brier) >= 0.0 or float(delta_logloss) >= 0.0:
        return K.ROUTE_NO
    if (
        float(brier_hi) < 0.0
        and float(logloss_hi) < 0.0
        and float(slope) >= 0.0
        and float(dev_delta_brier) < 0.0
        and float(diag_delta_brier) < 0.0
    ):
        return K.ROUTE_PROMISING
    return K.ROUTE_WEAK
