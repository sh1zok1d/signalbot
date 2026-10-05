"""Deterministic validation of the calibration freeze amendment V3 and reference
definitions it freezes: per-class candidate selection (C1, C6), the 1199/1200
confidence with its Stage A/B thresholds (C2), the exact-count support rule (C3/C4).

No simulation, no outcome. Reference functions are for testing a future executor;
they are not an executor.

    python -m scripts.research.compiler_v3_estimator_calibration.amendment_v3
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from scipy.stats import beta

from scripts.research.compiler_v3_estimator_calibration import amendment_v2 as V2

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
AMENDMENT_V3 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V3.json"
PROTOCOL_V3 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_EFFECTIVE_PROTOCOL_V3.md"
DENSE = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_GRID_DENSE_SUPPORT_V1.json"

REQUIRED_CLASSES = ["TWO_SAMPLE", "PAIRED_UNITS", "CLUSTERED", "RARE_EVENT"]
CANDIDATES = ["A", "B", "C"]
ALPHA_FAMILY = Fraction(1, 100)
ALPHA_CLASS_CANDIDATE = ALPHA_FAMILY / (len(REQUIRED_CLASSES) * len(CANDIDATES))   # 1/1200
CONF = 1 - ALPHA_CLASS_CANDIDATE                                                    # 1199/1200
MISS_TARGET, MISS_UNACCEPTABLE, UTIL_MIN = 0.01, 0.02, 0.80
STAGE_SIZES = (4000, 20000)


def cp_lower(s: int, n: int, conf: float = float(CONF)) -> float:
    return 0.0 if s <= 0 else float(beta.ppf(1 - conf, s, n - s + 1))


def cp_upper(s: int, n: int, conf: float = float(CONF)) -> float:
    return 1.0 if s >= n else float(beta.ppf(conf, s + 1, n - s))


def coverage_decision(misses: int, n: int) -> str:
    if cp_upper(misses, n) <= MISS_TARGET:
        return "PASS"
    if cp_lower(misses, n) > MISS_UNACCEPTABLE:
        return "FAIL"
    return "ESCALATE"


def utility_decision(successes: int, n: int) -> str:
    if cp_lower(successes, n) >= UTIL_MIN:
        return "PASS"
    if cp_upper(successes, n) < UTIL_MIN:
        return "FAIL"
    return "ESCALATE"


def thresholds() -> dict:
    out = {}
    for n in STAGE_SIZES:
        cp = [s for s in range(n + 1) if coverage_decision(s, n) == "PASS"]
        cf = [s for s in range(n + 1) if coverage_decision(s, n) == "FAIL"]
        up_ = [u for u in range(n + 1) if utility_decision(u, n) == "PASS"]
        uf = [u for u in range(n + 1) if utility_decision(u, n) == "FAIL"]
        overlap = [s for s in range(n + 1) if cp_upper(s, n) <= MISS_TARGET and cp_lower(s, n) > MISS_UNACCEPTABLE]
        out[str(n)] = {"COVERAGE_PASS_IF_MISSES_LE": max(cp), "COVERAGE_FAIL_IF_MISSES_GE": min(cf),
                       "UTILITY_PASS_IF_SUCCESSES_GE": min(up_), "UTILITY_FAIL_IF_SUCCESSES_LE": max(uf), "OVERLAP": overlap}
    return out


def count_support(cells: list[tuple[str, str]]) -> str:
    """C3: cells = list of (coverage_outcome, utility_outcome) for one (class, n, candidate)."""
    if any(c == "FAIL" or u == "FAIL" for c, u in cells):
        return "UNSUPPORTED_DECISIVE"
    if all(c == "PASS" and u == "PASS" for c, u in cells):
        return "SUPPORTED"
    return "UNSUPPORTED_UNRESOLVED"


def class_state(cov: dict[str, list[str]], util: dict[str, dict[int, list[str]]], err: dict[str, bool], realistic_max: int) -> dict:
    """C6 for one class. cov[X] = coverage outcomes of required cells; util[X] = size -> utility outcomes; err[X] = any execution error."""
    states, selected = {}, None
    for x in CANDIDATES:
        outcomes = cov[x]
        coverage = "PASS" if all(o == "PASS" for o in outcomes) else "FAIL" if any(o == "FAIL" for o in outcomes) else "OPEN"
        u = V2.utility_state(util[x], realistic_max)
        unresolved = any(o in ("ESCALATE", "CALIBRATION_INDETERMINATE") for o in outcomes) or u["UTILITY"] == "INDETERMINATE"
        if coverage == "FAIL" or u["UTILITY"] == "FAIL":
            st = "NOT_ELIGIBLE_DECISIVE"
        elif err.get(x, False):
            st = "ERROR_STATE"
        elif coverage == "PASS" and u["UTILITY"] == "PASS" and not unresolved:
            st = "ELIGIBLE"
        else:
            st = "UNRESOLVED_STATE"
        states[x] = {"STATE": st, "COVERAGE": coverage, "UTILITY": u["UTILITY"], "FRONTIER": u["FRONTIER"]}
        if st == "ELIGIBLE" and selected is None:
            selected = x
    if selected is not None:
        status = "CALIBRATION_CLASS_PASS"
    elif any(states[x]["STATE"] == "ERROR_STATE" for x in CANDIDATES):
        status = "CALIBRATION_CLASS_EXECUTION_ERROR"
    elif all(states[x]["STATE"] == "NOT_ELIGIBLE_DECISIVE" for x in CANDIDATES):
        status = "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT"
    else:
        status = "CALIBRATION_CLASS_INDETERMINATE"
    return {"CLASS_STATUS": status, "SELECTED_CANDIDATE": selected, "CANDIDATES": states}


def global_status(class_status: dict[str, str]) -> str:
    req = [class_status[c] for c in REQUIRED_CLASSES]
    if any(s == "CALIBRATION_CLASS_EXECUTION_ERROR" for s in req):
        return "ESTIMATOR_CALIBRATION_EXECUTION_ERROR"
    if any(s == "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT" for s in req):
        return "ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT"
    if any(s == "CALIBRATION_CLASS_INDETERMINATE" for s in req):
        return "CALIBRATION_INDETERMINATE"
    return "ESTIMATOR_CALIBRATION_PASS"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify() -> dict:
    am = json.loads(AMENDMENT_V3.read_text())
    checks = {}
    for key, ref in am["BOUND_ARTIFACTS"].items():
        checks[f"DIGEST_{key}"] = sha(REPO / ref["PATH"]) == ref["SHA256"]
    checks["AMENDMENT_V2_VERIFIES"] = V2.verify()["OK"]
    thr = thresholds()
    checks["THRESHOLDS_MATCH"] = all(
        {k: v for k, v in thr[s].items() if k != "OVERLAP"} == am["ERROR_BUDGET"]["STAGE_THRESHOLDS"][s] for s in thr)
    checks["REGIONS_DISJOINT"] = all(not thr[s]["OVERLAP"] for s in thr)
    checks["CONF_EXACT"] = am["ERROR_BUDGET"]["CONF_CLASS_CANDIDATE_RATIONAL"] == "1199/1200" and \
        abs(am["ERROR_BUDGET"]["CONF_CLASS_CANDIDATE"] - float(CONF)) < 1e-15
    dense = json.loads(DENSE.read_text())
    checks["DENSE_4716"] = len(dense["CELLS"]) == 4716 == am["DENSE_SUPPORT"]["DENSE_CELLS"]
    checks["DENSE_GRID_OK"] = dense["GRID_VALIDATION"]["GRID_OK"] is True
    checks["DENSE_EVAL_ONLY_IN_DOMAIN"] = all(c["SPLIT"] == "EVAL_ONLY" and c["K_IN_DOMAIN"] is not False for c in dense["CELLS"])
    checks["SUPPORT_SET_DIGEST"] = dense["SUPPORT_SET"]["SHA256"] == am["DENSE_SUPPORT"]["SUPPORT_SET_SHA256"] and dense["SUPPORT_SET"]["SIZE"] == 5148
    checks["SUPPORTED_RANGES"] = dense["SUPPORTED_RANGE"] == am["DENSE_SUPPORT"]["SUPPORTED_RANGE"]
    checks["COUNT_SUPPORT_RULE"] = (count_support([("PASS", "PASS")] * 3) == "SUPPORTED"
                                    and count_support([("PASS", "PASS"), ("FAIL", "PASS")]) == "UNSUPPORTED_DECISIVE"
                                    and count_support([("PASS", "PASS"), ("PASS", "ESCALATE")]) == "UNSUPPORTED_UNRESOLVED")
    # C6 reference scenarios.
    ok_cov = {x: ["PASS"] * 4 for x in CANDIDATES}
    ok_util = {x: {40: ["PASS"], 60: ["PASS"]} for x in CANDIDATES}
    s1 = class_state(ok_cov, ok_util, {}, 260)
    s2 = class_state({"A": ["PASS", "FAIL"], "B": ["PASS"] * 2, "C": ["PASS"] * 2}, ok_util, {}, 260)
    s3 = class_state({"A": ["PASS", "ESCALATE"], "B": ["PASS"] * 2, "C": ["PASS"] * 2}, ok_util, {}, 260)
    s4 = class_state({x: ["FAIL"] for x in CANDIDATES}, ok_util, {}, 260)
    s5 = class_state({"A": ["PASS", "ESCALATE"], "B": ["FAIL"], "C": ["FAIL"]}, ok_util, {}, 260)
    s6 = class_state({"A": ["PASS"], "B": ["PASS"], "C": ["PASS"]}, ok_util, {"A": True}, 260)
    checks["CLASS_MACHINE"] = (s1["SELECTED_CANDIDATE"] == "A" and s2["SELECTED_CANDIDATE"] == "B"
                               and s3["SELECTED_CANDIDATE"] == "B" and s3["CANDIDATES"]["A"]["STATE"] == "UNRESOLVED_STATE"
                               and s4["CLASS_STATUS"] == "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT"
                               and s5["CLASS_STATUS"] == "CALIBRATION_CLASS_INDETERMINATE"
                               and s6["SELECTED_CANDIDATE"] == "B" and s6["CLASS_STATUS"] == "CALIBRATION_CLASS_PASS")
    checks["GLOBAL_MACHINE"] = (
        global_status({c: "CALIBRATION_CLASS_PASS" for c in REQUIRED_CLASSES}) == "ESTIMATOR_CALIBRATION_PASS"
        and global_status({**{c: "CALIBRATION_CLASS_PASS" for c in REQUIRED_CLASSES}, "CLUSTERED": "CALIBRATION_CLASS_INDETERMINATE"}) == "CALIBRATION_INDETERMINATE"
        and global_status({**{c: "CALIBRATION_CLASS_PASS" for c in REQUIRED_CLASSES}, "CLUSTERED": "CALIBRATION_CLASS_INDETERMINATE",
                           "RARE_EVENT": "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT"}) == "ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT"
        and global_status({**{c: "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT" for c in REQUIRED_CLASSES},
                           "TWO_SAMPLE": "CALIBRATION_CLASS_EXECUTION_ERROR"}) == "ESTIMATOR_CALIBRATION_EXECUTION_ERROR")
    checks["EQUAL_ARMS_ONLY"] = am["TWO_SAMPLE_ALLOCATION_DOMAIN"] == "EQUAL_ARMS_ONLY"
    return {"OK": all(checks.values()), "CHECKS": checks, "THRESHOLDS": thr, "CONF": float(CONF)}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=1))
