"""Aggregation of EVAL cell results into the Protocol V3 C6 state machine and the C7 per-class output.

Inputs are cell result records (engine.run_eval output). Required cells of a class are
given explicitly (so DEV fixtures can be aggregated); for the frozen run they are
cells.required_for_class(klass). Coverage is separate from utility: a coverage FAIL on
any required cell makes the candidate decisively not eligible (no count may be dropped
from the support set to rescue it); a utility frontier above n_min leaves the candidate
eligible, with operational support starting at the frontier.
"""

from __future__ import annotations

from scripts.research.compiler_v3_estimator_calibration import amendment_v3 as A3
from scripts.research.compiler_v3_estimator_calibration import amendment_v4 as A4

CANDIDATES = ("A", "B", "C")
ESTIMATOR_TEXT = {
    "TWO_SAMPLE": {"A": "pooled within-arm sample variance, df n_a+n_b-2 (EQUAL_ARMS_ONLY)",
                   "B": "pooled Bartlett long-run variance ((n_a-1)Omega_a+(n_b-1)Omega_b)/(n_a+n_b-2), L_h=ceil(n_h^(1/3)), divisor n_h",
                   "C": "pooled within-arm sample variance times sealed c_env(TWO_SAMPLE, n_i)"},
    "PAIRED_UNITS": {"A": "sample variance of unit paired differences, df N-1",
                     "B": "Bartlett long-run variance of the ordered unit differences, L=ceil(N^(1/3)), divisor N",
                     "C": "sample variance of unit differences times sealed c_env(PAIRED_UNITS, n_i)"},
    "CLUSTERED": {"A": "sample variance of cluster-level means, df G-1 (cluster-level object; not per-hour, not Run 1 S4 DEFF)",
                  "B": "Bartlett long-run variance of the ordered cluster means, L=ceil(G^(1/3)), divisor G",
                  "C": "sample variance of cluster means times sealed c_env(CLUSTERED, n_i)"},
    "RARE_EVENT": {"A": "sample variance of venue-averaged event statistics, df n_e-1",
                   "B": "Bartlett long-run variance of the ordered event statistics, L=ceil(n_e^(1/3)), divisor n_e",
                   "C": "sample variance of event statistics times sealed c_env(RARE_EVENT, n_i)"},
}
BOUND_TEXT = {"A": "U = V_A * nu_A / chi2_{0.01, nu_A}", "B": "U = V_LR * nu_B / chi2_{0.01, nu_B}", "C": "U = V_A * c_env(class, n_i), n_i = largest calibrated size <= n"}
BOUND_KIND = {"A": "APPROXIMATE_EVAL_VALIDATED (ANALYTIC_EXACT only in independent Gaussian equal-variance cells)",
              "B": "APPROXIMATE_EVAL_VALIDATED", "C": "CAL_FITTED_EVAL_VALIDATED"}


def count_support_map(results: list[dict], x: str) -> dict[int, str]:
    by_n: dict[int, list[tuple[str, str]]] = {}
    for r in results:
        d = r["DECISIONS"][x]
        by_n.setdefault(r["N"], []).append((d["COVERAGE"], d["UTILITY"]))
    return {n: A3.count_support(cells) for n, cells in sorted(by_n.items())}


def aggregate_class(klass: str, results: list[dict], realistic_max: int, supported_range: tuple[int, int]) -> dict:
    req = [r for r in results if r["CLASS"] == klass and r["DECISIVE"] and supported_range[0] <= r["N"] <= supported_range[1]]
    cov = {x: [r["DECISIONS"][x]["COVERAGE"] for r in req] for x in CANDIDATES}
    util = {x: {} for x in CANDIDATES}
    err = {}
    for x in CANDIDATES:
        for r in req:
            util[x].setdefault(r["N"], []).append(r["DECISIONS"][x]["UTILITY"])
        err[x] = any(r["DECISIONS"][x]["COVERAGE"] == "CALIBRATION_EXECUTION_ERROR" for r in req)
        cov[x] = ["CALIBRATION_INDETERMINATE" if c == "CALIBRATION_EXECUTION_ERROR" else c for c in cov[x]]
        util[x] = {n: ["CALIBRATION_INDETERMINATE" if u == "CALIBRATION_EXECUTION_ERROR" else u for u in us] for n, us in util[x].items()}
    state = A4.class_state(cov, util, err, realistic_max)       # V4 D1 strict preference A -> B -> C
    sel = state["SELECTED_CANDIDATE"]
    out = {"CLASS": klass, "REQUIRED_CELLS": len(req), "CLASS_STATUS": state["CLASS_STATUS"], "SELECTED_CANDIDATE": sel,
           "CANDIDATES": state["CANDIDATES"], "COUNT_SUPPORT": {x: count_support_map(req, x) for x in CANDIDATES},
           "REFERENCE_D": {"COVERAGE_FAILS": sum(r["DECISIONS"]["D"]["COVERAGE"] == "FAIL" for r in req),
                           "UTILITY_FAILS": sum(r["DECISIONS"]["D"]["UTILITY"] == "FAIL" for r in req)}}
    if sel is not None:
        supported = sorted(n for n, s in out["COUNT_SUPPORT"][sel].items() if s == "SUPPORTED")
        out["PASS_OUTPUT"] = {
            "SELECTED_CANDIDATE": sel, "ESTIMATOR": ESTIMATOR_TEXT[klass][sel], "UPPER_BOUND_FORMULA": BOUND_TEXT[sel],
            "CONFIDENCE_SEMANTICS": "P(VAR_TRUE <= U) >= 0.99 decided at CONF_CLASS_CANDIDATE = 1199/1200 (0.01 / (4 classes x 3 candidates)); MISS_UNACCEPTABLE = 0.02",
            "SUPPORTED_COUNT_SET": supported, "DECLARED_RANGE": list(supported_range),
            "ALLOCATION_DOMAIN": "EQUAL_ARMS_ONLY" if klass == "TWO_SAMPLE" else "SINGLE_ORDERED_SEQUENCE",
            "DEPENDENCE_DOMAIN": "MUST structural levels of the frozen grid; STRUCTURAL_UNDERSTATEMENT_NOT_COVERABLE_AT_COMPILE_TIME for between-window variance change",
            "BOUND_KIND": BOUND_KIND[sel], "UTILITY_FRONTIER": state["CANDIDATES"][sel]["FRONTIER"],
            "OPERATIONAL_SUPPORT_STARTS_AT": state["CANDIDATES"][sel]["FRONTIER"],
            "DOWNSTREAM_REVALIDATION": ("variance-model validation must be redone on the cluster-level planning object; Run 1 S4 does not transfer"
                                        if klass == "CLUSTERED" else "as identified by the result"),
        }
    return out


def aggregate(results: list[dict], realistic_max: dict, supported_range: dict, required_classes=A3.REQUIRED_CLASSES) -> dict:
    classes = {k: aggregate_class(k, results, realistic_max[k], tuple(supported_range[k])) for k in required_classes}
    status = A4.global_status({k: classes[k]["CLASS_STATUS"] for k in required_classes})
    return {"GLOBAL_STATUS": status, "CLASSES": classes}
