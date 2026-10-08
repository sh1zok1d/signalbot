"""Equal-width scale around today's P0.

One k multiplies both partner log offsets. Dollar width matches today's width.
Log asymmetry is unchanged. There is no price-distance scale in this module.
"""

from __future__ import annotations

import numpy as np

from . import constants as K


def _f(k: np.float64, u: np.float64, d: np.float64) -> np.float64:
    """exp(k u) - exp(-k d). IEEE-754 float64. Overflow becomes inf, not an exception."""
    return np.exp(k * u) - np.exp((-k) * d)


def solve_equal_width(p0: float, w_real: float, u: float, d: float) -> dict:
    """The seven-step solver in the design note. Does not read a path after the decision."""
    p0_f = np.float64(p0)
    w_f = np.float64(w_real)
    u_f = np.float64(u)
    d_f = np.float64(d)
    if not (
        np.isfinite(p0_f)
        and np.isfinite(w_f)
        and np.isfinite(u_f)
        and np.isfinite(d_f)
        and p0_f > 0.0
        and w_f > 0.0
        and u_f > 0.0
        and d_f > 0.0
    ):
        return {"status": "invalid_geometry"}

    target = w_f / p0_f
    k_lo = np.float64(0.0)
    k_hi = np.float64(1.0)
    doubles = 0
    while doubles <= K.MAX_DOUBLES and not (_f(k_hi, u_f, d_f) >= target):
        if doubles == K.MAX_DOUBLES:
            return {"status": "scale_unbounded"}
        k_hi = k_hi * np.float64(2.0)
        doubles += 1

    for _ in range(K.BISECTIONS):
        k_mid = (k_lo + k_hi) / np.float64(2.0)
        if _f(k_mid, u_f, d_f) >= target:
            k_hi = k_mid
        else:
            k_lo = k_mid
    k = (k_lo + k_hi) / np.float64(2.0)
    pseudo_high = p0_f * np.exp(k * u_f)
    pseudo_low = p0_f * np.exp((-k) * d_f)
    if not (np.isfinite(pseudo_high) and np.isfinite(pseudo_low) and w_f > 0.0):
        return {"status": "scale_tolerance_failed"}
    rel = abs(float(pseudo_high - pseudo_low - w_f)) / float(w_f)
    if float(pseudo_low) < float(p0_f) < float(pseudo_high) and rel <= K.WIDTH_REL_TOL:
        return {
            "status": "ok",
            "k": float(k),
            "pseudo_high": float(pseudo_high),
            "pseudo_low": float(pseudo_low),
            "rel_width_error": rel,
        }
    return {"status": "scale_tolerance_failed"}


def collides(real_high: float, real_low: float, pseudo_high: float, pseudo_low: float) -> bool:
    """Parent REL_COLLIDE predicate, applied to the scaled bounds."""
    if real_high <= 0 or real_low <= 0 or pseudo_high <= 0 or pseudo_low <= 0:
        return True
    return (
        abs(pseudo_high - real_high) / real_high < K.REL_COLLIDE
        and abs(pseudo_low - real_low) / real_low < K.REL_COLLIDE
    )
