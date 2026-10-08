"""Endpoint overlap between the two arms of one contrast. Outcome-blind."""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from . import constants as K


def _finite(values: np.ndarray) -> np.ndarray:
    series = np.asarray(values, dtype=float)
    return series[np.isfinite(series)]


def arm_summary(values: np.ndarray) -> dict:
    finite = _finite(values)
    if finite.size == 0:
        return {"n": 0, "mean": None, "sd": None, "min": None, "max": None,
                "p05": None, "p10": None, "p25": None, "p50": None, "p75": None, "p90": None, "p95": None}
    qs = np.quantile(finite, [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95])
    return {
        "n": int(finite.size),
        "mean": float(finite.mean()),
        "sd": float(finite.std(ddof=0)),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "p05": float(qs[0]),
        "p10": float(qs[1]),
        "p25": float(qs[2]),
        "p50": float(qs[3]),
        "p75": float(qs[4]),
        "p90": float(qs[5]),
        "p95": float(qs[6]),
    }


def standardized_difference(treated: dict, reference: dict) -> Optional[float]:
    needed = (treated.get("mean"), treated.get("sd"), reference.get("mean"), reference.get("sd"))
    if any(value is None or not math.isfinite(float(value)) for value in needed):
        return None
    mean_t, sd_t, mean_r, sd_r = (float(v) for v in needed)
    pooled = math.sqrt((sd_t * sd_t + sd_r * sd_r) / 2.0)
    if pooled <= 0.0:
        return 0.0 if mean_t == mean_r else None
    return (mean_t - mean_r) / pooled


def _share_inside(values: np.ndarray, lo: Optional[float], hi: Optional[float]) -> Optional[float]:
    finite = _finite(values)
    if finite.size == 0 or lo is None or hi is None:
        return None
    if not (math.isfinite(lo) and math.isfinite(hi)) or hi < lo:
        return None
    return float(np.mean((finite >= float(lo)) & (finite <= float(hi))))


def overlap_audit(treated_values: np.ndarray, reference_values: np.ndarray, *, contrast: str) -> dict:
    treated = arm_summary(treated_values)
    reference = arm_summary(reference_values)
    lo = hi = width = None
    if treated["p10"] is not None and reference["p10"] is not None:
        lo = max(float(treated["p10"]), float(reference["p10"]))
        hi = min(float(treated["p90"]), float(reference["p90"]))
        width = float(hi - lo)
    share_t = _share_inside(treated_values, reference.get("p05"), reference.get("p95"))
    share_r = _share_inside(reference_values, treated.get("p05"), treated.get("p95"))
    arm_pass = int(treated["n"]) >= K.ARM_MIN_N and int(reference["n"]) >= K.ARM_MIN_N
    overlap_pass = (
        width is not None
        and width > 0.0
        and share_t is not None
        and share_r is not None
        and share_t >= K.OVERLAP_SHARE_MIN
        and share_r >= K.OVERLAP_SHARE_MIN
    )
    reasons = []
    if not arm_pass:
        reasons.append("ARM_N_BELOW_MINIMUM")
    if not overlap_pass:
        reasons.append("COMPARISON_INFORMATION_LIMITED_NO_OVERLAP")
    return {
        "contrast": contrast,
        "treated_state": K.TREATED_STATE[contrast],
        "reference_state": K.REFERENCE_STATE[contrast],
        "treated": treated,
        "reference": reference,
        "standardized_difference": standardized_difference(treated, reference),
        "overlap_lo": lo,
        "overlap_hi": hi,
        "overlap_width": width,
        "share_treated_in_reference_central": share_t,
        "share_reference_in_treated_central": share_r,
        "arm_n_pass": arm_pass,
        "overlap_pass": overlap_pass,
        "block_reasons": reasons,
    }


def rough_mde(n_treated: int, n_reference: int) -> Optional[float]:
    """80 percent MDE for an unadjusted difference of proportions. Context only."""
    if n_treated < 2 or n_reference < 2:
        return None
    se = 0.5 * math.sqrt(K.INFO_DEFF * (1.0 / n_treated + 1.0 / n_reference))
    return float(K.PLANNING_Z * se)
