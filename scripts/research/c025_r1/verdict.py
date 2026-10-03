"""Deterministic C025-R1 verdict. No threshold is relaxed here."""

from __future__ import annotations

from .constants import EXECUTION_NEFF_RETAINED, MIN_MEANINGFUL_EFFECT, PRIMARY_ALPHA


def classify(result: dict) -> str:
    if result.get("INVALID_EXECUTION_REASON"):
        return "INVALID_EXECUTION"
    preflight = result.get("PREFLIGHT_EFFECTIVE_N")
    realized = result.get("REALIZED_EFFECTIVE_N")
    weak = (
        result.get("ANALYSIS_ONE_SIDED_N", 0) < 30
        or result.get("ANALYSIS_TWO_SIDED_N", 0) < 30
        or preflight is None
        or realized is None
        or realized < EXECUTION_NEFF_RETAINED * preflight
    )
    if weak:
        return "INFORMATIONALLY_WEAK"
    raw = result.get("POOLED_DELTA_IMPACT_RAW")
    standardized = result.get("POOLED_DELTA_IMPACT_STANDARDIZED")
    p_value = result.get("PRIMARY_PERMUTATION_P")
    supported = (
        raw is not None and raw > 0.0
        and p_value is not None and p_value <= PRIMARY_ALPHA
        and standardized is not None and standardized >= MIN_MEANINGFUL_EFFECT
        and result.get("PLACEBO_PASS") is True
        and result.get("STABILITY_PASS") is True
    )
    if supported:
        return "SUPPORTED_DISCOVERY"
    return "NO_SUPPORT_FOR_PREREGISTERED_C025_R1"
