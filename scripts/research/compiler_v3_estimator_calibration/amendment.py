"""Deterministic validation of the calibration freeze amendment V1.

Checks, without any simulation or outcome read:
- the original frozen artifacts (spec, grid, builder, freeze record) match the digests
  bound in the amendment, i.e. they were not edited;
- the grid still has the 621 original cells with unchanged CELL_IDs and seed ranges;
- the amended coverage rule has disjoint PASS/FAIL regions at both stage sizes;
- the candidate confidence level is exactly 1 - 0.01/3;
- the Candidate C envelope rule is non-increasing and the application rule is total
  on the declared domain.

    python -m scripts.research.compiler_v3_estimator_calibration.amendment
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

from scipy.stats import beta

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs/research"
AMENDMENT = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V1.json"
PROTOCOL = DOCS / "COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_EFFECTIVE_PROTOCOL_V1.md"

ALPHA_FAMILY, N_SELECTABLE = Fraction(1, 100), 3
CONF_CANDIDATE = 1 - ALPHA_FAMILY / N_SELECTABLE          # 299/300
MISS_TARGET, MISS_UNACCEPTABLE = 0.01, 0.02
UTIL_MIN = 0.80
STAGE_SIZES = (4000, 20000)
CAL_SIZES = {"TWO_SAMPLE": [30, 60, 120, 250, 500], "PAIRED_UNITS": [40, 60, 100, 160, 260, 400],
             "CLUSTERED": [8, 15, 25, 40], "RARE_EVENT": [30, 50, 75, 100]}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def cp_lower(s: int, n: int, conf: float = float(CONF_CANDIDATE)) -> float:
    return 0.0 if s <= 0 else float(beta.ppf(1 - conf, s, n - s + 1))


def cp_upper(s: int, n: int, conf: float = float(CONF_CANDIDATE)) -> float:
    return 1.0 if s >= n else float(beta.ppf(conf, s + 1, n - s))


def coverage_decision(misses: int, n: int) -> str:
    """Amended rule A1. Regions are disjoint because cp_lower <= misses/n <= cp_upper."""
    if cp_upper(misses, n) <= MISS_TARGET:
        return "PASS"
    if cp_lower(misses, n) > MISS_UNACCEPTABLE:
        return "FAIL"
    return "ESCALATE"


def utility_decision(successes: int, n: int) -> str:
    """Amended rule A3."""
    if cp_lower(successes, n) >= UTIL_MIN:
        return "PASS"
    if cp_upper(successes, n) < UTIL_MIN:
        return "FAIL"
    return "ESCALATE"


def envelope(raw: dict[int, float]) -> dict[int, float]:
    """A6: suffix maximum over ordered sizes -> non-increasing in n."""
    sizes = sorted(raw)
    out, running = {}, float("-inf")
    for n in reversed(sizes):
        running = max(running, raw[n])
        out[n] = running
    return out


def apply_factor(env: dict[int, float], n: int) -> float | None:
    """A6 application rule: None below n_min; nearest lower calibrated size; constant above n_max."""
    sizes = sorted(env)
    if n < sizes[0]:
        return None
    lower = max(s for s in sizes if s <= n)
    return env[min(lower, sizes[-1])]


def rule_thresholds() -> dict:
    out = {}
    for n in STAGE_SIZES:
        pas = [s for s in range(n + 1) if coverage_decision(s, n) == "PASS"]
        fail = [s for s in range(n + 1) if coverage_decision(s, n) == "FAIL"]
        overlap = [s for s in range(n + 1) if cp_upper(s, n) <= MISS_TARGET and cp_lower(s, n) > MISS_UNACCEPTABLE]
        out[str(n)] = {"PASS_IF_MISSES_LE": max(pas), "FAIL_IF_MISSES_GE": min(fail), "OVERLAP": overlap}
    return out


def verify() -> dict:
    am = json.loads(AMENDMENT.read_text())
    checks = {}
    for key, ref in am["ORIGINAL_ARTIFACTS"].items():
        checks[f"DIGEST_{key}"] = sha(REPO / ref["PATH"]) == ref["SHA256"]
    grid = json.loads((REPO / am["ORIGINAL_ARTIFACTS"]["GRID"]["PATH"]).read_text())
    cells = grid["CELLS"]
    checks["GRID_621_CELLS"] = len(cells) == 621 == am["GRID_DELTA"]["ORIGINAL_CELLS"]
    checks["GRID_CELL_IDS_UNIQUE"] = len({c["CELL_ID"] for c in cells}) == 621
    checks["GRID_SEED_DIGEST"] = hashlib.sha256(json.dumps(
        [(c["CELL_ID"], c["SEED_RANGE"]) for c in cells], sort_keys=True).encode()).hexdigest() == am["GRID_DELTA"]["CELL_SEED_DIGEST"]
    thr = rule_thresholds()
    checks["COVERAGE_REGIONS_DISJOINT"] = all(not v["OVERLAP"] for v in thr.values())
    checks["THRESHOLDS_MATCH_AMENDMENT"] = all(
        thr[k]["PASS_IF_MISSES_LE"] == v["PASS_IF_MISSES_LE"] and thr[k]["FAIL_IF_MISSES_GE"] == v["FAIL_IF_MISSES_GE"]
        for k, v in am["COVERAGE_RULE"]["STAGE_THRESHOLDS"].items())
    checks["CONF_CANDIDATE_EXACT"] = am["CANDIDATE_SELECTION"]["CONF_CANDIDATE_RATIONAL"] == "299/300" and \
        abs(am["CANDIDATE_SELECTION"]["CONF_CANDIDATE"] - float(CONF_CANDIDATE)) < 1e-15
    demo = {30: 2.1, 60: 1.7, 120: 1.75, 250: 1.3, 500: 1.2}
    env = envelope(demo)
    checks["ENVELOPE_NON_INCREASING"] = all(env[a] >= env[b] for a, b in zip(sorted(env), sorted(env)[1:]))
    checks["ENVELOPE_SUFFIX_MAX"] = env == {30: 2.1, 60: 1.75, 120: 1.75, 250: 1.3, 500: 1.2}
    checks["APPLY_RULE"] = apply_factor(env, 29) is None and apply_factor(env, 100) == 1.75 and \
        apply_factor(env, 250) == 1.3 and apply_factor(env, 10_000) == 1.2
    checks["CAL_SIZES_MATCH_GRID"] = all(
        sorted({c["N"] for c in cells if c["CLASS"] == k and c["LABEL"] == "MUST"}) == v for k, v in CAL_SIZES.items())
    checks["TARGET_OBJECTS_PRESENT"] = set(am["TARGET_VARIANCE_OBJECT"]) == set(CAL_SIZES) | {"ERA_STRATIFIED"}
    checks["PROTOCOL_DIGEST"] = sha(PROTOCOL) == am["EFFECTIVE_PROTOCOL"]["SHA256"]
    return {"OK": all(checks.values()), "CHECKS": checks, "THRESHOLDS": thr, "CONF_CANDIDATE": float(CONF_CANDIDATE)}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=1))
