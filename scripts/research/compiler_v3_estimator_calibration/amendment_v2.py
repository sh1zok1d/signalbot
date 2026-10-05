"""Deterministic validation of the calibration freeze amendment V2 (option B) and
reference definitions it freezes: the TWO_SAMPLE Bartlett long-run estimator (B2),
the supported-application-domain rule (B1) and the utility state machine (B4).

No simulation, no outcome. The reference functions exist so that a future executor
can be tested against them; they are not an executor.

    python -m scripts.research.compiler_v3_estimator_calibration.amendment_v2
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from scripts.research.compiler_v3_estimator_calibration import amendment as A1

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
AMENDMENT_V2 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V2.json"
PROTOCOL_V2 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_EFFECTIVE_PROTOCOL_V2.md"
PROBES = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_PROBES_V1.json"


class CalibrationExecutionError(ValueError):
    """B2 numerical-error rule: non-finite or non-positive long-run variance is an error, never repaired."""


def bartlett_omega(x: np.ndarray) -> float:
    """B2: Omega_h for one ordered arm/sequence. Divisor n, Bartlett weights, L = ceil(n^(1/3))."""
    x = np.asarray(x, dtype=float)
    n = x.size
    L = int(math.ceil(n ** (1.0 / 3.0)))
    d = x - x.mean()
    gamma = [float(np.dot(d[l:], d[: n - l]) / n) for l in range(L + 1)]
    omega = gamma[0] + 2.0 * sum((1.0 - l / (L + 1)) * gamma[l] for l in range(1, L + 1))
    if not math.isfinite(omega) or omega <= 0.0:
        raise CalibrationExecutionError(f"Omega not finite/positive: {omega}")
    return omega


def two_sample_long_run_variance(xa: np.ndarray, xb: np.ndarray) -> float:
    """B2: V_LR = ((n_a-1) Omega_a + (n_b-1) Omega_b) / (n_a + n_b - 2)."""
    na, nb = len(xa), len(xb)
    v = ((na - 1) * bartlett_omega(xa) + (nb - 1) * bartlett_omega(xb)) / (na + nb - 2)
    if not math.isfinite(v) or v <= 0.0:
        raise CalibrationExecutionError(f"V_LR not finite/positive: {v}")
    return v


def supported(n: int, sizes: list[int], passed_sizes: set[int], passed_probes: dict[int, bool]) -> bool:
    """B1 application rule. passed_probes maps the lower calibrated size n_i of an interval to the probe verdict."""
    if n < sizes[0] or n > sizes[-1]:
        return False
    if n in sizes:
        return n in passed_sizes
    lo = max(s for s in sizes if s < n)
    return lo in passed_sizes and passed_probes.get(lo, False)


def utility_state(size_cells: dict[int, list[str]], realistic_max: int) -> dict:
    """B4 utility state machine for one candidate and class.
    size_cells: size -> list of per-cell utility outcomes in {PASS, FAIL, ESCALATE, CALIBRATION_INDETERMINATE}."""
    states = {}
    for s, cells in size_cells.items():
        if s > realistic_max:
            continue
        if all(c == "PASS" for c in cells):
            states[s] = "PASS"
        elif any(c == "FAIL" for c in cells):
            states[s] = "FAIL"
        else:
            states[s] = "OPEN"
    passes = [s for s, st in states.items() if st == "PASS"]
    if passes:
        return {"UTILITY": "PASS", "FRONTIER": min(passes), "SIZE_STATES": states}
    if states and all(st == "FAIL" for st in states.values()):
        return {"UTILITY": "FAIL", "FRONTIER": None, "SIZE_STATES": states}
    return {"UTILITY": "INDETERMINATE", "FRONTIER": None, "SIZE_STATES": states}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify() -> dict:
    am = json.loads(AMENDMENT_V2.read_text())
    checks = {}
    for key, ref in am["BOUND_ARTIFACTS"].items():
        checks[f"DIGEST_{key}"] = sha(REPO / ref["PATH"]) == ref["SHA256"]
    checks["AMENDMENT_V1_VERIFIES"] = A1.verify()["OK"]
    probes = json.loads(PROBES.read_text())
    checks["PROBES_198"] = len(probes["CELLS"]) == 198 == am["OPTION_B"]["PROBE_CELLS"]
    checks["PROBES_GRID_OK"] = probes["GRID_VALIDATION"]["GRID_OK"] is True
    checks["PROBES_EVAL_ONLY"] = all(c["SPLIT"] == "EVAL_ONLY" and "CAL" not in c["SEED_RANGE"] for c in probes["CELLS"])
    checks["PROBES_IN_DOMAIN"] = all(c["K_IN_DOMAIN"] is not False for c in probes["CELLS"])
    checks["PROBE_SIZES_MATCH"] = probes["PROBE_SIZES"] == am["OPTION_B"]["PROBE_SIZES"]
    # B2 reference: iid Gaussian long-run variance is close to the sample variance scale; AR(0.6) is larger.
    rng = np.random.default_rng(0)  # test-only RNG, not a calibration seed
    x = rng.standard_normal(100000)
    checks["BARTLETT_IID_SANITY"] = abs(two_sample_long_run_variance(x[:50000], x[50000:]) - 1.0) < 0.05
    bad = np.zeros(40)
    try:
        bartlett_omega(bad)
        checks["BARTLETT_ERROR_RULE"] = False
    except CalibrationExecutionError:
        checks["BARTLETT_ERROR_RULE"] = True
    # B1 reference.
    sizes = [30, 60, 120, 250, 500]
    checks["APPLY_RULE_V2"] = (not supported(29, sizes, set(sizes), {}) and not supported(501, sizes, set(sizes), {})
                               and supported(60, sizes, {60}, {}) and not supported(70, sizes, {60}, {})
                               and supported(70, sizes, {60}, {60: True}) and not supported(70, sizes, set(), {60: True}))
    # B4 reference.
    checks["UTILITY_MACHINE"] = (
        utility_state({40: ["PASS", "ESCALATE"], 60: ["PASS", "PASS"]}, 260)["FRONTIER"] == 60
        and utility_state({40: ["FAIL", "PASS"], 60: ["FAIL"]}, 260)["UTILITY"] == "FAIL"
        and utility_state({40: ["FAIL"], 60: ["PASS", "CALIBRATION_INDETERMINATE"]}, 260)["UTILITY"] == "INDETERMINATE"
        and utility_state({40: ["FAIL"], 400: ["PASS"]}, 260)["UTILITY"] == "FAIL")
    checks["EQUAL_ALLOCATION_FROZEN"] = am["TWO_SAMPLE_BARTLETT"]["ALLOCATION_DOMAIN"] == "EQUAL_ARMS_ONLY"
    checks["EXTRAPOLATION_WITHDRAWN"] = am["OPTION_B"]["ABOVE_N_MAX"] == "NOT_FEASIBLE_INFORMATION_INSUFFICIENT"
    return {"OK": all(checks.values()), "CHECKS": checks}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=1))
