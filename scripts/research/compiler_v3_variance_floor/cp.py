"""Exact one-sided 99% Clopper-Pearson bounds and the frozen Stage A/B rule (spec §6).

Pure functions of success counts; no randomness.
"""

from __future__ import annotations

from scipy.stats import beta

CONFIDENCE = 0.99
PASS, FAIL, ESCALATE, INDETERMINATE = "PASS", "FAIL", "ESCALATE", "VALIDATION_INDETERMINATE"


def cp_lower(successes: int, n: int, confidence: float = CONFIDENCE) -> float:
    """One-sided lower bound: P(p >= bound) = confidence. Exact Clopper-Pearson."""
    if successes <= 0:
        return 0.0
    return float(beta.ppf(1.0 - confidence, successes, n - successes + 1))


def cp_upper(successes: int, n: int, confidence: float = CONFIDENCE) -> float:
    """One-sided upper bound: P(p <= bound) = confidence. Exact Clopper-Pearson."""
    if successes >= n:
        return 1.0
    return float(beta.ppf(confidence, successes + 1, n - successes))


def decide_at_least(successes: int, n: int, threshold: float) -> str:
    """Requirement 'proportion >= threshold' (power). PASS if the lower bound clears it,
    FAIL if the upper bound is below it, else ESCALATE."""
    if cp_lower(successes, n) >= threshold:
        return PASS
    if cp_upper(successes, n) < threshold:
        return FAIL
    return ESCALATE


def decide_at_most(successes: int, n: int, threshold: float) -> str:
    """Requirement 'proportion <= threshold' (size). PASS if the upper bound is within it,
    FAIL if the lower bound exceeds it, else ESCALATE."""
    if cp_upper(successes, n) <= threshold:
        return PASS
    if cp_lower(successes, n) > threshold:
        return FAIL
    return ESCALATE


def stage_decision(kind: str, successes: int, n: int, threshold: float) -> str:
    return decide_at_least(successes, n, threshold) if kind == "AT_LEAST" else decide_at_most(successes, n, threshold)


def final_decision(stage_a: str, stage_b: str | None) -> str:
    """Stage A decisive -> final. Else Stage B decisive -> final. Else VALIDATION_INDETERMINATE."""
    if stage_a in (PASS, FAIL):
        return stage_a
    if stage_b in (PASS, FAIL):
        return stage_b
    return INDETERMINATE
