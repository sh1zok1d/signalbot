"""Exact estimators and bounds of the calibration executor (spec 1.2, Protocol V2 B2, V3 C4).

Candidate A: naive design-specific independent-unit variance (sample variance, ddof 1).
Candidate B: Bartlett long-run variance, L = ceil(n^(1/3)), divisor n, pooled by (n_h - 1)
             for TWO_SAMPLE; no clipping, no floor, no alternate kernel or bandwidth.
Candidate C: V_A times the sealed c_env(class, n_i), n_i = largest calibrated size <= n.
Candidate D: VAR_FALLBACK = 4 (reference only).
Bound A/B: V * nu / chi2_{0.01, nu}. Non-finite or non-positive -> CalibrationExecutionError.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import chi2

GAMMA = 0.01
VAR_FALLBACK = 4.0


class CalibrationExecutionError(ValueError):
    """Protocol B2 numerical-error rule: recorded, never repaired."""


def _check(x: float, what: str) -> float:
    if not math.isfinite(x) or x <= 0.0:
        raise CalibrationExecutionError(f"{what} not finite/positive: {x}")
    return float(x)


def bandwidth(n: int) -> int:
    return int(math.ceil(n ** (1.0 / 3.0)))


def bartlett_omega(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    n = x.size
    L = bandwidth(n)
    d = x - x.mean()
    gamma = [float(np.dot(d[l:], d[: n - l]) / n) for l in range(L + 1)]
    omega = gamma[0] + 2.0 * sum((1.0 - l / (L + 1)) * gamma[l] for l in range(1, L + 1))
    return _check(omega, "Omega")


def naive_variance(sample: dict) -> tuple[float, int]:
    """Candidate A estimator and its df nu_A for the sample's class."""
    if sample["CLASS"] == "TWO_SAMPLE":
        xa, xb = sample["ARMS"]
        na, nb = len(xa), len(xb)
        v = ((na - 1) * np.var(xa, ddof=1) + (nb - 1) * np.var(xb, ddof=1)) / (na + nb - 2)
        return _check(v, "V_A"), na + nb - 2
    s = sample["SEQUENCE"]
    return _check(np.var(s, ddof=1), "V_A"), len(s) - 1


def long_run_variance(sample: dict) -> tuple[float, int]:
    """Candidate B estimator and nu_B."""
    if sample["CLASS"] == "TWO_SAMPLE":
        xa, xb = sample["ARMS"]
        na, nb = len(xa), len(xb)
        v = ((na - 1) * bartlett_omega(xa) + (nb - 1) * bartlett_omega(xb)) / (na + nb - 2)
        n_pool = na + nb
        return _check(v, "V_LR"), n_pool // (bandwidth(n_pool) + 1) - 1
    s = sample["SEQUENCE"]
    n = len(s)
    return _check(bartlett_omega(s), "V_LR"), n // (bandwidth(n) + 1) - 1


def chi2_bound(v: float, nu: int) -> float:
    if nu < 1:
        raise CalibrationExecutionError(f"nu < 1: {nu}")
    return _check(v * nu / float(chi2.ppf(GAMMA, nu)), "U")


def bounds(sample: dict, c_env_factor: float | None) -> dict:
    """All candidate bounds from ONE sample. c_env_factor None -> C not applicable at this count."""
    va, nua = naive_variance(sample)
    vb, nub = long_run_variance(sample)
    out = {"V_A": va, "NU_A": nua, "V_B": vb, "NU_B": nub,
           "U_A": chi2_bound(va, nua), "U_B": chi2_bound(vb, nub),
           "U_C": _check(va * c_env_factor, "U_C") if c_env_factor is not None else None,
           "U_D": VAR_FALLBACK}
    return out
