"""Compiler-V3 feasibility verdict for a manifest cell under a candidate floor (spec §3A, §5).

The compiler sees only planning information: the cell's sample size, delta_min,
multiplicity alpha, the design's planning formula and VAR_PLANNING. It has no
access to any simulated evaluation outcome. The planning formulas are the
spec §5 oracle formulas with VAR_PLANNING in place of VAR_TRUE; N_ORACLE_80
itself is never recomputed or used here.
"""

from __future__ import annotations

import math

from scipy.stats import norm, t as student_t

POWER = 0.80
FEASIBLE, NOT_FEASIBLE = "FEASIBLE", "NOT_FEASIBLE"


def var_planning(cell: dict, f: float) -> float:
    vr = cell["VARIANCE_RELATIONSHIPS"]
    exposed = vr["q"] * vr["VAR_TRUE"]                      # controlled planning input, spec §2
    return max(exposed, f * vr["VAR_FALLBACK"])


def required_n(cell: dict, variance: float) -> int:
    """Design-specific planning requirement at `variance` (spec §5 formulas)."""
    alpha = cell["MULTIPLICITY_ALPHA"]
    d = cell["GENERATOR_PARAMS"]["delta_min"]
    z_a, z_b = norm.ppf(1 - alpha / 2), norm.ppf(POWER)
    design = cell["DESIGN_ID"]
    if design in ("S1", "S2"):
        return 2 * math.ceil(2 * variance * (z_a + z_b) ** 2 / d ** 2)
    if design in ("S3", "S5"):
        return math.ceil(variance * (z_a + z_b) ** 2 / d ** 2)
    if design == "S4":
        m, icc = cell["GENERATOR_PARAMS"]["m"], cell["GENERATOR_PARAMS"]["icc"]
        deff = 1 + (m - 1) * icc
        g = 5
        while True:
            ta, tb = student_t.ppf(1 - alpha / 2, g - 1), student_t.ppf(POWER, g - 1)
            if g >= variance * deff * (ta + tb) ** 2 / (m * d ** 2):
                return g
            g += 1
    if design == "S6":
        return 3 * math.ceil(variance * (z_a + z_b) ** 2 / d ** 2 / 3)
    raise KeyError(design)


def feasibility(cell: dict, f: float) -> dict:
    vp = var_planning(cell, f)
    need = required_n(cell, vp)
    have = cell["SAMPLE_SIZE"]["COUNT"]
    return {"CANDIDATE_FLOOR": f, "VAR_PLANNING": vp, "REQUIRED_N": need, "SAMPLE_N": have,
            "VERDICT": FEASIBLE if have >= need else NOT_FEASIBLE}
