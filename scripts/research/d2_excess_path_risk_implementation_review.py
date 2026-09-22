"""Write the outcome-blind D2 excess path-risk implementation-review artifacts.

Does not execute the scientific decomposition. Does not create an execution
permit. Does not create a RESULT. Does not open protected 2025/2026. Does not
reuse BitMEX 2017-2019 for this target.
"""

from __future__ import annotations

import ast
import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    CLASSIFICATION_ORDER,
    CONTROL_STRATA,
    FROZEN_RULE1_N,
    FROZEN_RULE1_YEAR_N,
    JSON_REL as DESIGN_JSON_REL,
    N_RANDOM_CONTROLS,
    PATH_SCALE_PRACTICAL_RELATIVE_BAR,
    PRACTICAL_DELTA_SHARE,
    PRIMARY_COMPARATOR,
    PRIMARY_SELECTOR,
    PRIMARY_TARGET,
    RANDOM_SEED,
    TARGET_INELIGIBLE_REASON,
    TEMPORAL_YEARS_REQUIRED,
    TEMPORAL_YEARS_TOTAL,
    file_sha256,
    verify_design_authorities,
)
from scripts.research.d2_excess_path_risk_evaluator import (
    CANONICAL_SELECTOR_DIGEST_VERSION,
    CONTROL_P95_METHOD,
    EXECUTION_AUTHORIZED,
    EXECUTION_PERMIT_REL,
    FROZEN_EXPECTED_SELECTOR_DIGEST,
    IMPLEMENTATION_FILES,
    PERMIT_REQUIRED_FIELDS,
    REVIEW_JSON_REL,
    REVIEW_MD_REL,
    UNIT,
    compute_run_identity,
    current_artifact_sha256,
    current_implementation_file_sha256,
    frozen_contract_summary,
    frozen_selector_expectations,
)
from scripts.research.discovery_sprint_01 import common as C

TEST_FILES = (
    "tests/research/test_d2_excess_path_risk_evaluator.py",
    "tests/research/test_d2_excess_path_risk_implementation_review.py",
)

RED_TEAM: dict[str, dict[str, str]] = {
    "F1_LOOKAHEAD_FEATURE_OUTCOME_OVERLAP": {
        "status": "NOT_CONFIRMED",
        "note": (
            "Features (rv, ret, SIDE) come from frozen construct_discovery_row at "
            "cutoff E=T-5m. The target re-walk reads only bars opening at T..T+287*5m; "
            "a RecordingPerp test asserts min(read key) >= T."
        ),
    },
    "F2_WRONG_FUTURE_BAR_WINDOW": {
        "status": "NOT_CONFIRMED",
        "note": (
            "future_bars_for_row demands exactly 288 bars at T + k*BAR_MS for "
            "k=0..287, asserts each bar.open_time_ms equals the requested key, and "
            "fails closed on a missing or off-grid bar."
        ),
    },
    "F3_CLOSES_INSTEAD_OF_HIGH_LOW": {
        "status": "NOT_CONFIRMED",
        "note": (
            "MAE comes from frozen arithmetic_mae over PerpBar high/low. An AST test "
            "asserts the evaluator never reads DiscoveryRow.future_closes, and a "
            "high/low-collapsed perp map fails the severity cross-check."
        ),
    },
    "F4_DIFFERENT_PATHS_FOR_SIDE_AND_MIRROR": {
        "status": "NOT_CONFIRMED",
        "note": (
            "mae_pair calls arithmetic_mae twice on one bars sequence. AST tests "
            "assert exactly one future_bars_for_row call and one mae_pair call per "
            "row, and LONG+SHORT shares on one path sum to exactly 1.0."
        ),
    },
    "F5_MAE_SIDE_SUBSTITUTION": {
        "status": "NOT_CONFIRMED",
        "note": (
            "Recomputed MAE_SIDE is cross-checked bit-for-bit (tolerance 0.0) "
            "against the frozen DiscoveryRow.severity, so any substituted path "
            "fails closed."
        ),
    },
    "F6_SELECTOR_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": (
            "The selector is frozen C.rv_abstention_mask (identity-asserted), "
            "RV_TRAILING_WINDOW=250, RV_PCTL=90.0, strict >, t excluded, imported "
            "not redefined. verify_selector_identity fails closed unless the "
            "constructed population is exactly 1791 / 334-364-364-364-365 AND the "
            "abstention census matches the frozen 163 / 10-48-32-23-50 (see F24), "
            "with exact timestamp identity deferred to the canonical digest (F23)."
        ),
    },
    "F7_SIDE_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": (
            "SIDE is the frozen row.side = sign(BTC_RET_24H); encode_side accepts "
            "only +/-1 and rejects 0 and fractional sides."
        ),
    },
    "F8_TARGET_INELIGIBILITY_HANDLING": {
        "status": "NOT_CONFIRMED",
        "note": (
            "PATH_SCALE<=0 or nonfinite yields exactly "
            "TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE with no epsilon. The "
            "selector mask is never rebuilt: candidate = selector AND eligible, "
            "and SELECTOR_ROWS_TARGET_INELIGIBLE_N is reported per year."
        ),
    },
    "F9_POOLED_K_OR_YEAR_ONLY_FALLBACK": {
        "status": "NOT_CONFIRMED",
        "note": (
            "Draws are per (calendar_year, frozen SIDE) stratum. Tests assert every "
            "replicate reproduces K exactly in every stratum, and that an all-LONG "
            "candidate set never draws a SHORT control row while a pooled draw would."
        ),
    },
    "F10_LONG_SHORT_COMPOSITION_MISMATCH": {
        "status": "NOT_CONFIRMED",
        "note": (
            "Per-stratum K equality is asserted for both sides in every replicate; "
            "K=0 strata draw zero rows."
        ),
    },
    "F11_RNG_SEED_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": (
            "numpy.random.Generator(numpy.random.PCG64(20260922131)), "
            "N_RANDOM_CONTROLS=10000. Asserted distinct from the D2 discovery seed "
            "and the D2 BitMEX seed; same seed reproduces masks, different seed does not."
        ),
    },
    "F12_REPLACEMENT_SAMPLING": {
        "status": "NOT_CONFIRMED",
        "note": (
            "rng.choice(..., replace=False) per stratum; tests assert each replicate "
            "sets exactly K distinct bits, which a with-replacement draw could not."
        ),
    },
    "F13_DIFFERENT_MASKS_FOR_SHARE_AND_SCALE": {
        "status": "NOT_CONFIRMED",
        "note": (
            "AST tests assert exactly one year_side_matched_control_masks call and "
            "that both means_from_shared_masks calls consume the same masks object."
        ),
    },
    "F14_SEPARATE_YEARLY_CONTROL_GENERATION": {
        "status": "NOT_CONFIRMED",
        "note": (
            "Yearly DELTA_SHARE uses year_means_from_shared_masks on the same masks "
            "object, subset by year; AST asserts exactly one such call and no second "
            "mask system."
        ),
    },
    "F15_FUTURE_INFORMATION_MATCHING": {
        "status": "NOT_CONFIRMED",
        "note": (
            "The comparator receives only years, sides, target-eligibility and "
            "candidacy. No matching on PATH_SCALE, future volatility, future return, "
            "MAE, extrema or abs(BTC_RET_24H); an AST test asserts no share/scale "
            "array is passed."
        ),
    },
    "F16_GATE_OR_CLASSIFICATION_RESCUE": {
        "status": "NOT_CONFIRMED",
        "note": (
            "classify_decomposition is the frozen ordered rule. PROMISING requires "
            "all three primary gates; PATH_SCALE elevation can only reach "
            "VOLATILITY_SCALE_COMPATIBLE and never rescues a failed ADVERSE_SHARE "
            "gate; the classifier never reads yearly or subgroup values."
        ),
    },
    "F17_AUTHORITY_HASH_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": (
            "verify_design_authorities binds the D2 discovery RESULT, program "
            "decision, common.py, the D2 card and the arithmetic_mae module by "
            "SHA256 and currently returns no blockers; a mutated copy raises "
            "COMMON_SHA in test."
        ),
    },
    "F18_ACCIDENTAL_REAL_OUTCOME_EXECUTION": {
        "status": "NOT_CONFIRMED",
        "note": (
            "execute_decomposition and load_canonical_core_btc_bars require an "
            "execution permit that does not exist; EXECUTION_AUTHORIZED is False and "
            "a forged permit still raises RealDecompositionForbidden."
        ),
    },
    "F19_PROTECTED_2025_2026_ACCESS": {
        "status": "NOT_CONFIRMED",
        "note": (
            "construct_discovery_row refuses decisions from 2025 onward and the "
            "target re-walk refuses any bar at or after PROTECTED_START_MS. No "
            "protected partition is opened."
        ),
    },
    "F20_BITMEX_REUSE_FOR_NEW_TARGET": {
        "status": "NOT_CONFIRMED",
        "note": (
            "An AST test asserts the evaluator imports no BitMEX module. The surface "
            "is CORE_BTC_BINANCE_V0 2020-02-01 -> 2025-01-01 only."
        ),
    },
    "F21_EXECUTION_READY_OVERSTATED_STUB_ROUTE": {
        "status": "CONFIRMED_AND_REPAIRED",
        "note": (
            "The first review recorded EXECUTION_READY=true while "
            "execute_decomposition was a terminal stub that checked the permit and "
            "then unconditionally raised, so the canonical wiring would have been "
            "written AFTER the outcome-blind review. The complete dormant route is "
            "now implemented and reviewed: permit -> frozen snapshot identity -> "
            "frozen CORE BTC load -> C.build_rows(RULE1_INTERVAL_START, "
            "DISCOVERY_END) -> selector identity -> exact 288x5m re-walk -> frozen "
            "comparator at seed 20260922131 / 10000 replicates with identity "
            "enforcement and severity cross-check ON. An end-to-end test runs steps "
            "3-8 over the real frozen interval against a synthetic surface. Frozen "
            "parameters are not caller-tunable: seed/N drift raises."
        ),
    },
    "F22_PERMIT_AUTHORITY_UNDER_BOUND": {
        "status": "CONFIRMED_AND_REPAIRED",
        "note": (
            "The first gate let caller kwargs supply design/review/implementation/"
            "snapshot values and bound only run_identity to the permit file. The "
            "gate now takes only `repo`: every authority value is read from the "
            "tracked permit artifact and compared against tracked/current "
            "authorities (unit, design SHA, review SHA, evaluator SHA, CORE BTC "
            "snapshot, RUN_IDENTITY equal to the review's, seed, N, "
            "EXECUTION_AUTHORIZED, ONE_SHOT, RERUN_AUTHORIZED, plus the frozen "
            "selector digest and its version). A CONSUMED permit cannot authorize a "
            "rerun. Parameterized tests cover every wrong/missing field, tampered "
            "design or review bytes, unparseable permits, and forged caller kwargs."
        ),
    },
    "F23_SELECTOR_IDENTITY_PROVED_COUNTS_NOT_IDENTITY": {
        "status": "CONFIRMED_AND_REPAIRED",
        "note": (
            "Counts are not identity. A canonical digest over the ordered "
            "(t_ms, selector_flag) sequence of the COMPLETE constructed-row "
            "population is now implemented and tested (equal counts with different "
            "firing positions produce different digests). ROW_COUNT_IDENTITY_VERIFIED "
            "and EXACT_SELECTOR_IDENTITY_VERIFIED are reported separately. No "
            "expected digest is invented here; the permit must carry one and the "
            "one-shot refuses metrics without a match."
        ),
    },
    "F24_FROZEN_1791_MISREAD_AS_THE_ABSTAIN_COUNT": {
        "status": "CONFIRMED_AND_REPAIRED",
        "note": (
            "Found while repairing F23. The frozen RULE_1_ROW_COUNT=1791 with "
            "334/364/364/364/365 is the CONSTRUCTED decision-row population "
            "(RULE_ELIGIBLE_N), not the abstention count; the frozen RULE_1 "
            "abstention census in the same hash-bound discovery RESULT is 163 "
            "(10/48/32/23/50). The first implementation asserted mask.sum()==1791, "
            "which would have failed closed on correct canonical data and invited a "
            "post-hoc loosening. Both censuses are now checked against the frozen "
            "discovery result, which is outcome-blind for the new ADVERSE_SHARE "
            "target because it describes the selector only."
        ),
    },
    "F25_CONTROL_PERCENTILE_CONVENTION_IMPLICIT": {
        "status": "CONFIRMED_AND_REPAIRED",
        "note": (
            "P95 relied on NumPy's default interpolation. It is now explicit as "
            "np.percentile(values, 95.0, method='linear') behind control_percentile, "
            "recorded as CONTROL_P95_METHOD=NUMPY_LINEAR_INHERITED_FROM_D2, and "
            "tested to equal the historical np.percentile(x, 95) call form used by "
            "D2 discovery and D2 BitMEX. The threshold itself is unchanged."
        ),
    },
}

OBSERVATIONS: list[dict[str, str]] = [
    {
        "id": "O1_STATISTICAL_GATE_STRICT_INEQUALITY_AT_AN_EXACT_TIE",
        "class": "HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE",
        "note": (
            "The frozen STATISTICAL_GATE is MU_SHARE_RULE > CONTROL_SHARE_P95. When "
            "the rule and control means are exactly tied, floating-point noise can "
            "decide the strict comparison. The frozen design is authoritative and is "
            "NOT changed here. Defense in depth is already frozen: PROMISING requires "
            "the practical (>= 0.05) and temporal (>= 3 of 5 years) gates too, so a "
            "lone float-noise statistical pass cannot change the classification. "
            "Covered by test_statistical_gate_alone_cannot_produce_promising."
        ),
    },
    {
        "id": "O2_CONTROL_POOL_INCLUDES_THE_ABSTAINED_ROWS",
        "class": "FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE",
        "note": (
            "year_side_matched_control_masks draws from every target-eligible row in "
            "the stratum, including the D2-abstained rows themselves. This is the "
            "frozen design function's own behaviour and matches the original D2 "
            "discovery comparator rate_matched_random_abstention. No new researcher "
            "convention was introduced."
        ),
    },
    {
        "id": "O3_YEARLY_NAN_IS_STRUCTURALLY_IMPOSSIBLE_UNLESS_K_YEAR_IS_ZERO",
        "class": "FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE",
        "note": (
            "Each replicate draws exactly K per stratum, so a year's replicate subset "
            "is empty only when that year has no candidate rows at all. Partial NaN "
            "across replicates is therefore impossible and is rejected explicitly "
            "rather than silently averaged."
        ),
    },
]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _evaluator_ast(repo: Path) -> ast.Module:
    path = repo / "scripts/research/d2_excess_path_risk_evaluator.py"
    return ast.parse(path.read_text(encoding="utf-8"))


def _function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls(node: ast.AST) -> set[str]:
    out: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = getattr(child.func, "attr", None) or getattr(child.func, "id", None)
            if name:
                out.add(name)
    return out


def probe_capabilities(repo: Path) -> dict[str, Any]:
    """Derive lifecycle status from the CODE, not from the findings table.

    Each flag below is a mechanical check of the reviewed implementation, so
    the review cannot claim a capability the code does not have.
    """
    tree = _evaluator_ast(repo)
    execute = _function(tree, "execute_decomposition")
    orchestration = _function(tree, "canonical_orchestration")
    gate = _function(tree, "_verify_execution_permit")

    execute_calls = _calls(execute) if execute else set()
    orchestration_calls = _calls(orchestration) if orchestration else set()

    canonical_route_steps = {
        "PERMIT_GATE": "_verify_execution_permit" in execute_calls,
        "SNAPSHOT_IDENTITY": "verify_core_btc_snapshot_identity" in execute_calls,
        "FROZEN_CORE_LOAD": "load_canonical_core_btc_bars" in execute_calls,
        "ROW_RECONSTRUCTION": "SCIENTIFIC_BUILD_ROWS" in orchestration_calls,
        "EVALUATION": "evaluate_decomposition" in orchestration_calls,
    }
    execute_is_terminal_stub = bool(
        execute is not None and isinstance(execute.body[-1], ast.Raise)
    )
    gate_args = (
        {a.arg for a in gate.args.args} | {a.arg for a in gate.args.kwonlyargs}
        if gate
        else set()
    )
    return {
        "CANONICAL_ROUTE_STEPS": canonical_route_steps,
        "CANONICAL_ORCHESTRATION_IMPLEMENTED": bool(
            all(canonical_route_steps.values()) and not execute_is_terminal_stub
        ),
        "EXECUTE_IS_TERMINAL_STUB": execute_is_terminal_stub,
        "PERMIT_GATE_TAKES_ONLY_REPO": gate_args == {"repo"},
        "PERMIT_GATE_DERIVES_AUTHORITY_FROM_REPO": (
            "expected_permit_authority" in _calls(gate) if gate else False
        ),
        "CANONICAL_SELECTOR_DIGEST_IMPLEMENTED": (
            _function(tree, "canonical_selector_digest") is not None
        ),
        "EXPECTED_CANONICAL_DIGEST_FROZEN": FROZEN_EXPECTED_SELECTOR_DIGEST is not None,
        "CONTROL_P95_METHOD_EXPLICIT": CONTROL_P95_METHOD
        == "NUMPY_LINEAR_INHERITED_FROM_D2",
    }


def build_review(*, repo: Path, implementation_commit: str | None = None) -> dict[str, Any]:
    blockers = verify_design_authorities(repo)
    contract = frozen_contract_summary(repo)
    impl = current_implementation_file_sha256(repo)
    artifacts = current_artifact_sha256(repo)
    tests = {rel: file_sha256(repo / rel) for rel in TEST_FILES}

    commit = implementation_commit or _git(repo, "rev-parse", "HEAD")
    # Resolve the tree OF THE IMPLEMENTATION COMMIT, never of whatever HEAD
    # happens to be, so RUN_IDENTITY and the artifact bytes stay stable once
    # the implementation is committed.
    tree = _git(repo, "rev-parse", f"{commit}^{{tree}}")

    identity_inputs = {
        "DESIGN_JSON_SHA256": artifacts["DESIGN_JSON_SHA256"],
        "DESIGN_MD_SHA256": artifacts["DESIGN_MD_SHA256"],
        "IMPLEMENTATION_FILE_SHA256": impl,
        "TEST_FILE_SHA256": tests,
        "RANDOM_SEED": int(RANDOM_SEED),
        "N_RANDOM_CONTROLS": int(N_RANDOM_CONTROLS),
        "PRIMARY_SELECTOR": PRIMARY_SELECTOR,
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "PRIMARY_COMPARATOR": PRIMARY_COMPARATOR,
        "FROZEN_RULE1_N": int(FROZEN_RULE1_N),
        "FROZEN_RULE1_YEAR_N": dict(FROZEN_RULE1_YEAR_N),
        "CORE_BTC_SNAPSHOT": C.CORE_BTC_SNAPSHOT,
        "FINAL_IMPLEMENTATION_COMMIT": commit,
        "FINAL_IMPLEMENTATION_TREE": tree,
    }
    run_identity = compute_run_identity(identity_inputs)

    caps = probe_capabilities(repo)
    selector = frozen_selector_expectations(repo)

    blocking = [name for name, body in RED_TEAM.items() if body["status"] == "BLOCKING"]

    # Status is derived from what the code actually does, not from the findings
    # table. A capability that is not mechanically present cannot be claimed.
    scientific_kernel_ready = bool(
        caps["CONTROL_P95_METHOD_EXPLICIT"]
        and caps["CANONICAL_SELECTOR_DIGEST_IMPLEMENTED"]
    )
    canonical_orchestration_ready = bool(caps["CANONICAL_ORCHESTRATION_IMPLEMENTED"])
    authority_verification_ready = bool(
        caps["PERMIT_GATE_TAKES_ONLY_REPO"]
        and caps["PERMIT_GATE_DERIVES_AUTHORITY_FROM_REPO"]
    )
    exact_selector_identity_verified = bool(caps["EXPECTED_CANONICAL_DIGEST_FROZEN"])

    review_pass = bool(
        not blocking
        and not blockers
        and scientific_kernel_ready
        and canonical_orchestration_ready
        and authority_verification_ready
    )

    # EXECUTION_READY is NOT "the review passed". The canonical one-shot still
    # lacks a frozen expected selector digest, which cannot legitimately be
    # produced in an outcome-blind unit, so execution is not yet possible.
    execution_blocked_by: list[str] = []
    if not exact_selector_identity_verified:
        execution_blocked_by.append("EXPECTED_CANONICAL_SELECTOR_DIGEST_NOT_FROZEN")
    if not (repo / EXECUTION_PERMIT_REL).is_file():
        execution_blocked_by.append("NO_EXECUTION_PERMIT")
    if EXECUTION_AUTHORIZED is not True:
        execution_blocked_by.append("EXECUTION_AUTHORIZED_FALSE")
    execution_ready = bool(review_pass and not execution_blocked_by)

    next_unit = (
        "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_IDENTITY_COMMIT"
        if review_pass
        else "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REPAIR"
    )

    return {
        "unit": UNIT,
        "kind": "OUTCOME_BLIND_IMPLEMENTATION_REVIEW",
        "EVIDENCE_CLASS": "POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY",
        "DESIGN_SCIENTIFIC_CONTRACT": DESIGN_JSON_REL,
        "DESIGN_STATUS": "FROZEN",
        "DESIGN_NOT_REDESIGNED": True,
        "CANDIDATE": "D2 / RULE_1 / RV_ABSTENTION",
        "IMPLEMENTATION_REVIEW": "PASS" if review_pass else "BLOCKED",
        "SCIENTIFIC_KERNEL_READY": scientific_kernel_ready,
        "CANONICAL_ORCHESTRATION_READY": canonical_orchestration_ready,
        "AUTHORITY_VERIFICATION_READY": authority_verification_ready,
        "ROW_COUNT_IDENTITY_IMPLEMENTED": True,
        "EXACT_SELECTOR_IDENTITY_VERIFIED": exact_selector_identity_verified,
        "EXACT_SELECTOR_IDENTITY_STATUS": (
            "CANONICAL_DIGEST_FROZEN"
            if exact_selector_identity_verified
            else "DIGEST_FUNCTION_IMPLEMENTED_EXPECTED_VALUE_NOT_YET_FROZEN"
        ),
        "CANONICAL_SELECTOR_DIGEST_VERSION": CANONICAL_SELECTOR_DIGEST_VERSION,
        "FROZEN_EXPECTED_SELECTOR_DIGEST": FROZEN_EXPECTED_SELECTOR_DIGEST,
        "CAPABILITY_PROBES": caps,
        "EXECUTION_READY": execution_ready,
        "EXECUTION_BLOCKED_BY": execution_blocked_by,
        "EXECUTION_AUTHORIZED": False,
        "EXECUTION_AUTHORIZED_FLAG": EXECUTION_AUTHORIZED,
        "EXECUTION_PERMIT_PRESENT": (repo / EXECUTION_PERMIT_REL).is_file(),
        "EXECUTION_PERMIT_CREATED": False,
        "PERMIT_REQUIRED_FIELDS": list(PERMIT_REQUIRED_FIELDS),
        "CONTROL_P95_METHOD": CONTROL_P95_METHOD,
        "FROZEN_SELECTOR_CENSUS": selector,
        "PRIMARY_SELECTOR": PRIMARY_SELECTOR,
        "PRIMARY_TARGET": PRIMARY_TARGET,
        "PRIMARY_COMPARATOR": PRIMARY_COMPARATOR,
        "CONTROL_STRATA": CONTROL_STRATA,
        "ADVERSE_SHARE_FORMULA": "MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)",
        "PATH_SCALE_FORMULA": "MAE_SIDE + MAE_OPPOSITE",
        "SAME_FUTURE_PATH_REQUIRED": True,
        "TARGET_SPECIFIC_INELIGIBILITY": TARGET_INELIGIBLE_REASON,
        "TARGET_INELIGIBILITY_DOES_NOT_CHANGE_D2_SELECTOR": True,
        "TARGET_INELIGIBILITY_MUST_BE_REPORTED": True,
        "STATISTICAL_GATE": "MU_SHARE_RULE > CONTROL_SHARE_P95",
        "PRACTICAL_GATE": f"DELTA_SHARE >= {PRACTICAL_DELTA_SHARE}",
        "TEMPORAL_GATE": (
            f"DELTA_SHARE > 0 in at least {TEMPORAL_YEARS_REQUIRED} of "
            f"{TEMPORAL_YEARS_TOTAL} years"
        ),
        "PATH_SCALE_RELATIVE_BAR": float(PATH_SCALE_PRACTICAL_RELATIVE_BAR),
        "PATH_SCALE_CANNOT_RESCUE_PRIMARY": True,
        "NO_SUBGROUP_RESCUE": True,
        "RANDOM_SEED": int(RANDOM_SEED),
        "N_RANDOM_CONTROLS": int(N_RANDOM_CONTROLS),
        "FROZEN_RULE1_N": int(FROZEN_RULE1_N),
        "FROZEN_RULE1_YEAR_N": dict(FROZEN_RULE1_YEAR_N),
        "SURFACE": {
            "DATASET": "CORE_BTC_BINANCE_V0",
            "SNAPSHOT": C.CORE_BTC_SNAPSHOT,
            "INTERVAL": "2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive",
            "LABEL": "ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA",
        },
        "DESIGN_AUTHORITY_BLOCKERS": blockers,
        "FROZEN_AUTHORITY_STATUS": "BOUND_NO_DRIFT" if not blockers else "DRIFT",
        "IMPLEMENTATION_FILES": list(IMPLEMENTATION_FILES),
        "IMPLEMENTATION_FILE_SHA256": impl,
        "TEST_FILES": list(TEST_FILES),
        "TEST_FILE_SHA256": tests,
        "DESIGN_JSON_SHA256": artifacts["DESIGN_JSON_SHA256"],
        "DESIGN_MD_SHA256": artifacts["DESIGN_MD_SHA256"],
        "FINAL_IMPLEMENTATION_COMMIT": commit,
        "FINAL_IMPLEMENTATION_TREE": tree,
        "RUN_IDENTITY": run_identity,
        "RUN_IDENTITY_INPUTS": identity_inputs,
        "RED_TEAM_FINDINGS": RED_TEAM,
        "BLOCKING_FINDINGS": blocking,
        "OBSERVATIONS": OBSERVATIONS,
        "SCIENTIFIC_AMBIGUITY_FOUND": False,
        "NEW_RESEARCHER_CONVENTION_INTRODUCED": False,
        "CLASSIFICATIONS_UNASSIGNED": list(CLASSIFICATION_ORDER),
        "CLASSIFICATION_ASSIGNED": None,
        "CLASSIFICATION_ORDER": list(CLASSIFICATION_ORDER),
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED": False,
        "MU_SHARE_RULE": None,
        "DELTA_SHARE": None,
        "MU_PATH_SCALE_RULE": None,
        "DELTA_PATH_SCALE": None,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "BITMEX_2017_2019_REUSED_FOR_NEW_TARGET": False,
        "MARKET_07_CREATED": False,
        "RESULT_CREATED": False,
        "ARM_CREATED": False,
        "SYNTHETIC_TESTS_ONLY": True,
        "CONTRACT_ECHO": contract,
        "NEXT_UNIT": next_unit,
        "UNIT_AFTER_NEXT": "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION",
        "NEXT_UNIT_REQUIREMENT": (
            "Reconstruct the frozen RULE_1 rows from CORE_BTC_BINANCE_V0 and freeze "
            "the canonical selector digest BEFORE any ADVERSE_SHARE or PATH_SCALE "
            "metric is computed. That step is outcome-blind for this target: it "
            "touches the selector only. The one-shot permit must then carry the "
            "frozen digest, and the one-shot must block if the reconstructed digest "
            "differs."
        ),
        "NOT_CREATED": ["RESULT", "execution permit", "MARKET-07", "ARM"],
    }


def render_markdown(review: dict[str, Any]) -> str:
    findings = "\n".join(
        f"- `{name}`: **{body['status']}** — {body['note']}"
        for name, body in review["RED_TEAM_FINDINGS"].items()
    )
    observations = "\n".join(
        f"- `{item['id']}` ({item['class']}) — {item['note']}"
        for item in review["OBSERVATIONS"]
    )
    year_n = ", ".join(
        f"{year}={count}" for year, count in sorted(review["FROZEN_RULE1_YEAR_N"].items())
    )
    return f"""# D2 excess direction-aligned path-risk — implementation review

**Unit:** `{review["unit"]}`
**Kind:** outcome-blind implementation review. **The decomposition was NOT executed.**

## Lineage

The frozen decomposition design
`{review["DESIGN_SCIENTIFIC_CONTRACT"]}` is authoritative and was not
redesigned. This unit adds an execution implementation plus an adversarial
synthetic test suite, without computing any real ADVERSE_SHARE, PATH_SCALE,
DELTA_SHARE, or classification.

The selector is unchanged: `{review["PRIMARY_SELECTOR"]}` — P90 of the previous
250 valid constructed-row RV observations, `t` excluded, strict `>`.

## Scientific contract

```
PRIMARY_SELECTOR   = {review["PRIMARY_SELECTOR"]}
PRIMARY_TARGET     = {review["PRIMARY_TARGET"]}
ADVERSE_SHARE      = {review["ADVERSE_SHARE_FORMULA"]}
PATH_SCALE         = {review["PATH_SCALE_FORMULA"]}
PRIMARY_COMPARATOR = {review["PRIMARY_COMPARATOR"]}
CONTROL_STRATA     = {review["CONTROL_STRATA"]}
STATISTICAL_GATE   = {review["STATISTICAL_GATE"]}
PRACTICAL_GATE     = {review["PRACTICAL_GATE"]}
TEMPORAL_GATE      = {review["TEMPORAL_GATE"]}
RANDOM_SEED        = {review["RANDOM_SEED"]}
N_RANDOM_CONTROLS  = {review["N_RANDOM_CONTROLS"]}
FROZEN_RULE1_N     = {review["FROZEN_RULE1_N"]} ({year_n})
```

Classification order is unchanged and exhaustive:

1. `{review["CLASSIFICATION_ORDER"][0]}`
2. `{review["CLASSIFICATION_ORDER"][1]}`
3. `{review["CLASSIFICATION_ORDER"][2]}`
4. `{review["CLASSIFICATION_ORDER"][3]}`

## Future-path reconstruction

`DiscoveryRow` stores `future_closes` only, so `MAE_OPPOSITE` cannot be read
off a stored row. The implementation re-walks the exact 288 5m `PerpBar`
sequence opening at `T … T+287*5m` and calls frozen `arithmetic_mae` twice on
that one shared sequence. Recomputed `MAE_SIDE` is cross-checked bit-for-bit
against the frozen `DiscoveryRow.severity`, so a wrong window, a close-path
substitution, or a split path fails closed rather than producing a number.

Rows whose envelope is nonpositive or nonfinite are target-ineligible with
reason `{review["TARGET_SPECIFIC_INELIGIBILITY"]}` and no epsilon. This never
rebuilds the D2 selector; the count of selector rows dropped by target
ineligibility is reported per year.

## Lifecycle status

These are distinct claims. Each is derived from a mechanical probe of the
reviewed code, not from the findings table.

```
IMPLEMENTATION_REVIEW          = {review["IMPLEMENTATION_REVIEW"]}
SCIENTIFIC_KERNEL_READY        = {review["SCIENTIFIC_KERNEL_READY"]}
CANONICAL_ORCHESTRATION_READY  = {review["CANONICAL_ORCHESTRATION_READY"]}
AUTHORITY_VERIFICATION_READY   = {review["AUTHORITY_VERIFICATION_READY"]}
ROW_COUNT_IDENTITY_IMPLEMENTED = {review["ROW_COUNT_IDENTITY_IMPLEMENTED"]}
EXACT_SELECTOR_IDENTITY_VERIFIED = {review["EXACT_SELECTOR_IDENTITY_VERIFIED"]}
EXACT_SELECTOR_IDENTITY_STATUS = {review["EXACT_SELECTOR_IDENTITY_STATUS"]}
EXECUTION_READY                = {review["EXECUTION_READY"]}
EXECUTION_BLOCKED_BY           = {review["EXECUTION_BLOCKED_BY"]}
EXECUTION_AUTHORIZED           = {review["EXECUTION_AUTHORIZED"]}
```

`EXECUTION_READY` is deliberately **not** a synonym for a passing review. The
canonical route is implemented and reviewed, but the expected canonical
selector digest has not been frozen, and that value cannot legitimately be
produced by an outcome-blind unit. Until it exists, the one-shot must not run.

## Canonical route (dormant, not a stub)

```
1. permit gate            : {review["CAPABILITY_PROBES"]["CANONICAL_ROUTE_STEPS"]["PERMIT_GATE"]}
2. frozen snapshot identity: {review["CAPABILITY_PROBES"]["CANONICAL_ROUTE_STEPS"]["SNAPSHOT_IDENTITY"]}
3. frozen CORE BTC load    : {review["CAPABILITY_PROBES"]["CANONICAL_ROUTE_STEPS"]["FROZEN_CORE_LOAD"]}
4. frozen row reconstruction: {review["CAPABILITY_PROBES"]["CANONICAL_ROUTE_STEPS"]["ROW_RECONSTRUCTION"]}
5. frozen evaluation       : {review["CAPABILITY_PROBES"]["CANONICAL_ROUTE_STEPS"]["EVALUATION"]}
execute_is_terminal_stub   : {review["CAPABILITY_PROBES"]["EXECUTE_IS_TERMINAL_STUB"]}
```

## Frozen selector census

`RULE_1_ROW_COUNT = 1791` is the **constructed decision-row population**
(`RULE_ELIGIBLE_N`), not the abstention count. The frozen RULE_1 abstention
census is separate and smaller.

```
CONSTRUCTED_N   = {review["FROZEN_SELECTOR_CENSUS"]["CONSTRUCTED_N"]}
CONSTRUCTED_YEAR_N = {review["FROZEN_SELECTOR_CENSUS"]["CONSTRUCTED_YEAR_N"]}
ABSTAIN_N       = {review["FROZEN_SELECTOR_CENSUS"]["ABSTAIN_N"]}
ABSTAIN_YEAR_N  = {review["FROZEN_SELECTOR_CENSUS"]["ABSTAIN_YEAR_N"]}
CONTROL_P95_METHOD = {review["CONTROL_P95_METHOD"]}
```

## Identity

```
FROZEN_AUTHORITY_STATUS    = {review["FROZEN_AUTHORITY_STATUS"]}
DESIGN_AUTHORITY_BLOCKERS  = {review["DESIGN_AUTHORITY_BLOCKERS"]}
DESIGN_JSON_SHA256         = {review["DESIGN_JSON_SHA256"]}
RUN_IDENTITY               = {review["RUN_IDENTITY"]}
FINAL_IMPLEMENTATION_COMMIT = {review["FINAL_IMPLEMENTATION_COMMIT"]}
EXECUTION_PERMIT_PRESENT   = {review["EXECUTION_PERMIT_PRESENT"]}
```

No execution permit exists. `execute_decomposition` and
`load_canonical_core_btc_bars` fail closed before any CORE BTC byte is read.
A future permit must itself carry every field in `PERMIT_REQUIRED_FIELDS`;
caller arguments cannot supply scientific authority.

## Red-team (F1–F25)

{findings}

## Observations (non-blocking)

{observations}

No scientific ambiguity required a new researcher convention:
`SCIENTIFIC_AMBIGUITY_FOUND = {review["SCIENTIFIC_AMBIGUITY_FOUND"]}`.

## Firewall

```
REAL_DECOMPOSITION_OUTCOME_COMPUTED = {review["REAL_DECOMPOSITION_OUTCOME_COMPUTED"]}
CLASSIFICATION_ASSIGNED             = {review["CLASSIFICATION_ASSIGNED"]}
PROTECTED_2025_OPENED               = {review["PROTECTED_2025_OPENED"]}
PROTECTED_2026_OPENED               = {review["PROTECTED_2026_OPENED"]}
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = {review["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"]}
MARKET_07_CREATED                   = {review["MARKET_07_CREATED"]}
RESULT_CREATED                      = {review["RESULT_CREATED"]}
EXECUTION_PERMIT_CREATED            = {review["EXECUTION_PERMIT_CREATED"]}
```

## Next

`NEXT_UNIT = {review["NEXT_UNIT"]}`

{review["NEXT_UNIT_REQUIREMENT"]}

Only after that does the explicit one-shot execution unit
`{review["UNIT_AFTER_NEXT"]}` become possible. Neither is executed here, and
this review does not authorize either: a future permit must bind the design
hash, this review's hash, the evaluator hash, the CORE BTC snapshot, the run
identity above, the frozen selector digest, the seed and the control count.
"""


def write_artifacts(
    *, repo: Path | None = None, implementation_commit: str | None = None
) -> dict[str, Any]:
    base = repo or C.repo_root()
    review = build_review(repo=base, implementation_commit=implementation_commit)
    (base / REVIEW_JSON_REL).write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (base / REVIEW_MD_REL).write_text(render_markdown(review), encoding="utf-8")
    return review


if __name__ == "__main__":
    written = write_artifacts()
    keys = (
        "IMPLEMENTATION_REVIEW",
        "EXECUTION_READY",
        "EXECUTION_AUTHORIZED",
        "FROZEN_AUTHORITY_STATUS",
        "DESIGN_AUTHORITY_BLOCKERS",
        "RUN_IDENTITY",
        "REAL_DECOMPOSITION_OUTCOME_COMPUTED",
        "PROTECTED_2025_OPENED",
        "PROTECTED_2026_OPENED",
        "BITMEX_2017_2019_REUSED_FOR_NEW_TARGET",
        "RESULT_CREATED",
        "EXECUTION_PERMIT_CREATED",
        "NEXT_UNIT",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
