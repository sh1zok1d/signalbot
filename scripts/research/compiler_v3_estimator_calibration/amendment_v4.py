"""Amendment V4: strict candidate preference state machine, exact CLUSTERED truth,
TWO_SAMPLE Candidate-B df, per-check Stage A lock, slim checkpoint schema, and the
deterministic validator of the amendment artifact.

    python -m scripts.research.compiler_v3_estimator_calibration.amendment_v4
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.linalg import toeplitz

from scripts.research.compiler_v3_estimator_calibration import amendment_v2 as V2
from scripts.research.compiler_v3_estimator_calibration import amendment_v3 as V3

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
AMENDMENT_V4 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V4.json"
PROTOCOL_V4 = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_EFFECTIVE_PROTOCOL_V4.md"

CANDIDATES = ("A", "B", "C")
REQUIRED_CLASSES = V3.REQUIRED_CLASSES
SLIM_ROW_KEYS = {"CAL": ["P", "C", "S", "VA", "T", "E"], "EVAL": ["P", "C", "S", "VA", "VB", "T", "E"]}


# ----------------------------------------------------------------------------- D1 class preference machine

def candidate_state(coverage: str, utility: str, error: bool, unresolved: bool) -> str:
    if coverage == "FAIL" or utility == "FAIL":
        return "NOT_ELIGIBLE_DECISIVE"
    if error:
        return "ERROR_STATE"
    if coverage == "PASS" and utility == "PASS" and not unresolved:
        return "ELIGIBLE"
    return "UNRESOLVED_STATE"


def class_decision(states: dict[str, str]) -> tuple[str, str | None]:
    """Strict preference A -> B -> C. A lower candidate is considered only when every
    higher one is NOT_ELIGIBLE_DECISIVE. Returns (CLASS_STATUS, SELECTED_CANDIDATE)."""
    for x in CANDIDATES:
        st = states[x]
        if st == "ELIGIBLE":
            return "CALIBRATION_CLASS_PASS", x
        if st == "ERROR_STATE":
            return "CALIBRATION_CLASS_EXECUTION_ERROR", None
        if st == "UNRESOLVED_STATE":
            return "CALIBRATION_CLASS_INDETERMINATE", None
        assert st == "NOT_ELIGIBLE_DECISIVE", st
    return "CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT", None


def class_state(cov: dict[str, list[str]], util: dict[str, dict[int, list[str]]], err: dict[str, bool], realistic_max: int) -> dict:
    """Same inputs as amendment_v3.class_state; V4 preference semantics."""
    states, detail = {}, {}
    for x in CANDIDATES:
        outcomes = cov[x]
        coverage = "PASS" if all(o == "PASS" for o in outcomes) else "FAIL" if any(o == "FAIL" for o in outcomes) else "OPEN"
        u = V2.utility_state(util[x], realistic_max)
        unresolved = any(o in ("ESCALATE", "CALIBRATION_INDETERMINATE") for o in outcomes) or u["UTILITY"] == "INDETERMINATE"
        states[x] = candidate_state(coverage, u["UTILITY"], err.get(x, False), unresolved)
        detail[x] = {"STATE": states[x], "COVERAGE": coverage, "UTILITY": u["UTILITY"], "FRONTIER": u["FRONTIER"]}
    status, selected = class_decision(states)
    return {"CLASS_STATUS": status, "SELECTED_CANDIDATE": selected, "CANDIDATES": detail}


global_status = V3.global_status


# ----------------------------------------------------------------------------- D2 exact CLUSTERED truth

def clustered_truth(v: np.ndarray, phi: float) -> float:
    """VAR_TRUE = (1/G) sum_g sum_h sqrt(v_g v_h) phi^|g-h|  (exact conditional finite-G variance)."""
    v = np.asarray(v, dtype=float)
    G = v.size
    sv = np.sqrt(v)
    idx = np.arange(G)
    return float((sv[:, None] * sv[None, :] * phi ** np.abs(idx[:, None] - idx[None, :])).sum()) / G


def clustered_truth_by_covariance(v: np.ndarray, phi: float) -> float:
    """Reference: G * Var(mean of X), X = D Z, Cov(Z) = Toeplitz(phi^|g-h|), D = diag(sqrt v)."""
    v = np.asarray(v, dtype=float)
    G = v.size
    cov_z = toeplitz(phi ** np.arange(G))
    D = np.diag(np.sqrt(v))
    cov_x = D @ cov_z @ D
    return float(np.ones(G) @ cov_x @ np.ones(G)) / G


def ar_factor(n: int, phi: float) -> float:
    return 1.0 + 2.0 * sum((1.0 - h / n) * phi**h for h in range(1, n))


# ----------------------------------------------------------------------------- D5 RARE_EVENT truth derivation

def rare_event_truth_by_covariance(n: int, phi: float, venue_corr: float, hetero: bool) -> float:
    """Reference: the generated process is x_1 = m_1 e_1, x_t = phi x_{t-1} + sqrt(1-phi^2) m_t e_t with
    m_t e_t independent across t, Var(m_t e_t) = E[m^2]; s = sqrt(c) x. Build the linear map x = A w and
    compute n * Var(mean of s) = c * 1' A diag(E[m^2]) A' 1 / n exactly."""
    c = (1.0 + 2.0 * venue_corr) / 3.0
    em2 = math.exp(0.5) if hetero else 1.0
    A = np.zeros((n, n))
    A[0, 0] = 1.0
    k = math.sqrt(1.0 - phi * phi)
    for t in range(1, n):
        A[t, :] = phi * A[t - 1, :]
        A[t, t] = k
    cov = A @ (em2 * np.eye(n)) @ A.T
    return c * float(np.ones(n) @ cov @ np.ones(n)) / n


def rare_event_truth_formula(n: int, phi: float, venue_corr: float, hetero: bool) -> float:
    c = (1.0 + 2.0 * venue_corr) / 3.0
    return c * (math.exp(0.5) if hetero else 1.0) * ar_factor(n, phi)


# ----------------------------------------------------------------------------- D4 TWO_SAMPLE Candidate-B df

def nu_b_two_sample(n: int) -> int:
    L = int(math.ceil(n ** (1.0 / 3.0)))
    return 2 * (n // (L + 1) - 1)


def nu_b_single(n: int) -> int:
    L = int(math.ceil(n ** (1.0 / 3.0)))
    return n // (L + 1) - 1


# ----------------------------------------------------------------------------- validator

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify() -> dict:
    am = json.loads(AMENDMENT_V4.read_text())
    checks = {}
    for key, ref in am["BOUND_ARTIFACTS"].items():
        checks[f"DIGEST_{key}"] = sha(REPO / ref["PATH"]) == ref["SHA256"]
    checks["AMENDMENT_V3_VERIFIES"] = V3.verify()["OK"]
    # D1 scenarios (owner item 1).
    S = lambda a, b, c: class_decision({"A": a, "B": b, "C": c})
    E, U, N, P = "ELIGIBLE", "UNRESOLVED_STATE", "NOT_ELIGIBLE_DECISIVE", "ERROR_STATE"
    checks["PREFERENCE_MACHINE"] = (
        S(U, E, E) == ("CALIBRATION_CLASS_INDETERMINATE", None) and S(P, E, E) == ("CALIBRATION_CLASS_EXECUTION_ERROR", None)
        and S(N, U, E) == ("CALIBRATION_CLASS_INDETERMINATE", None) and S(N, P, E) == ("CALIBRATION_CLASS_EXECUTION_ERROR", None)
        and S(N, N, E) == ("CALIBRATION_CLASS_PASS", "C") and S(E, P, P) == ("CALIBRATION_CLASS_PASS", "A")
        and S(N, N, N) == ("CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT", None) and S(N, E, U) == ("CALIBRATION_CLASS_PASS", "B"))
    # D2 analytic properties.
    rng = np.random.default_rng(0)
    v = 0.1 + 0.9 / rng.integers(12, 37, size=25)
    checks["CLUSTERED_PHI0_MEAN_V"] = abs(clustered_truth(v, 0.0) - v.mean()) < 1e-12
    veq = np.full(25, 0.1 + 0.9 / 24)
    checks["CLUSTERED_EQUAL_AR"] = abs(clustered_truth(veq, 0.3) - veq[0] * ar_factor(25, 0.3)) < 1e-12
    checks["CLUSTERED_EQUAL_PHI0"] = abs(clustered_truth(veq, 0.0) - (0.1 + 0.9 / 24)) < 1e-12
    checks["CLUSTERED_COV_MATRIX"] = all(abs(clustered_truth(v, p) - clustered_truth_by_covariance(v, p)) < 1e-10 for p in (0.0, 0.3, 0.6))
    # D5 rare-event identity.
    checks["RARE_EVENT_IDENTITY"] = all(
        abs(rare_event_truth_by_covariance(n, p, vc, h) - rare_event_truth_formula(n, p, vc, h)) < 1e-9
        for n in (30, 61, 100) for p in (0.0, 0.3, 0.6) for vc in (0.5, 0.9) for h in (False, True))
    # D4 df rule.
    checks["NU_B_TWO_SAMPLE"] = nu_b_two_sample(30) == 2 * (30 // 5 - 1) == 10 and nu_b_two_sample(250) == 2 * (250 // 8 - 1) == 60
    checks["SLIM_SCHEMA_BOUND"] = am["SLIM_CHECKPOINT"]["ROW_KEYS"] == SLIM_ROW_KEYS
    checks["NO_NEW_CELLS"] = am["NEW_CELLS"] == 0
    checks = {k: bool(v) for k, v in checks.items()}
    return {"OK": all(checks.values()), "CHECKS": checks}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=1))
