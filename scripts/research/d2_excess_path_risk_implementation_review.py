"""Write the outcome-blind D2 excess path-risk implementation-review artifacts.

Does not execute the scientific decomposition. Does not create an execution
permit. Does not create a RESULT. Does not open protected 2025/2026. Does not
reuse BitMEX 2017-2019 for this target.
"""

from __future__ import annotations

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
    CANONICAL_ORCHESTRATION_READY,
    CANONICAL_SELECTOR_DIGEST_FROZEN,
    CONTROL_P95_METHOD,
    EXACT_SELECTOR_IDENTITY_IMPLEMENTED,
    EXECUTION_AUTHORIZED,
    EXECUTION_PERMIT_REL,
    EXECUTION_READY,
    IMPLEMENTATION_FILES,
    PERMIT_VERIFIER_READY,
    REVIEW_JSON_REL,
    REVIEW_MD_REL,
    SCIENTIFIC_KERNEL_READY,
    SELECTOR_IDENTITY_AUTHORITY_REL,
    UNIT,
    canonical_orchestration,
    compute_run_identity,
    control_p95,
    current_artifact_sha256,
    current_implementation_file_sha256,
    frozen_contract_summary,
    selector_digest,
    selector_identity_authority_payload,
    verify_selector_identity_authority,
    verify_tracked_permit,
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
            "not redefined. The 1791 / year-count census is a secondary integrity "
            "check only. Exact identity is SHA256 of the ordered constructed-row "
            "t_ms plus selector flags; that machinery is implemented and tested. "
            "canonical_orchestration compares the reconstructed digest to a tracked "
            "selector-identity authority BEFORE evaluate_decomposition. The authority "
            "artifact is NOT created in this unit "
            "(CANONICAL_SELECTOR_DIGEST_FROZEN = false) because obtaining the true "
            "canonical digest would require opening real CORE BTC. Count-only identity "
            "is not called exact identity."
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
            "execute_decomposition is the full dormant canonical orchestration "
            "route, not a terminal firewall stub. Scientific authority is read "
            "only from a tracked permit artifact (UNIT, design/review/evaluator "
            "SHA256, CORE snapshot, RUN_IDENTITY, seed 20260922131, N=10000, "
            "EXECUTION_AUTHORIZED=true, ONE_SHOT=true, RERUN_AUTHORIZED=false). "
            "Caller kwargs cannot replace those fields. No permit exists in this "
            "unit, so the route fails closed before CORE BTC OHLC is opened. "
            "Adversarial tests cover forged caller authority, mutated permit "
            "bytes, and each bound-field mismatch."
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
    {
        "id": "O4_CONTROL_P95_METHOD_INHERITED_FROM_D2",
        "class": "FROZEN_SEMANTICS_CONFIRMED_NOT_A_NEW_CHOICE",
        "note": (
            "CONTROL_P95_METHOD = NUMPY_LINEAR_INHERITED_FROM_D2. "
            "np.percentile(values, 95.0, method='linear') is the historical D2 "
            "convention made explicit. This is not a newly selected scientific "
            "threshold. CONTROL_SHARE_P95 and CONTROL_PATH_SCALE_P95 both use it."
        ),
    },
    {
        "id": "O5_CANONICAL_SELECTOR_DIGEST_NOT_FROZEN_OUTCOME_BLIND",
        "class": "HONEST_IDENTITY_GAP_NOT_A_RESCUE",
        "note": (
            "Exact selector-identity machinery is implemented (ordered t_ms + "
            "selector-flag SHA256) and the canonical route requires a tracked "
            "selector-identity authority whose SHA256 is bound by the future "
            "execution permit. The true canonical digest cannot be obtained "
            "in this unit without opening prohibited real CORE BTC, so the "
            "authority artifact is not created or guessed. "
            "CANONICAL_SELECTOR_DIGEST_FROZEN = false. The next unit only "
            "reconstructs and freezes that authority; it must not alter the "
            "reviewed scientific execution implementation."
        ),
    },
]


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


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
        "CONTROL_P95_METHOD": CONTROL_P95_METHOD,
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

    blocking = [name for name, body in RED_TEAM.items() if body["status"] == "BLOCKING"]
    machinery_ready = (
        callable(canonical_orchestration)
        and callable(verify_tracked_permit)
        and callable(selector_digest)
        and callable(control_p95)
        and CONTROL_P95_METHOD == "NUMPY_LINEAR_INHERITED_FROM_D2"
        and SCIENTIFIC_KERNEL_READY is True
        and CANONICAL_ORCHESTRATION_READY is True
        and PERMIT_VERIFIER_READY is True
        and EXACT_SELECTOR_IDENTITY_IMPLEMENTED is True
        and EXECUTION_AUTHORIZED is False
        and not (repo / EXECUTION_PERMIT_REL).is_file()
        and not (repo / SELECTOR_IDENTITY_AUTHORITY_REL).is_file()
        and callable(selector_identity_authority_payload)
        and callable(verify_selector_identity_authority)
    )
    pass_blockers: list[str] = []
    if blocking:
        pass_blockers.append("RED_TEAM_BLOCKING")
    if blockers:
        pass_blockers.append("DESIGN_AUTHORITY")
    if not machinery_ready:
        pass_blockers.append("MACHINERY_NOT_READY")
    review_pass = not pass_blockers
    if not review_pass:
        next_unit = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REPAIR"
    elif CANONICAL_SELECTOR_DIGEST_FROZEN:
        next_unit = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION"
    else:
        next_unit = (
            "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE"
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
        "IMPLEMENTATION_REVIEW_PASS_JUSTIFICATION": (
            "Scientific kernel, dormant canonical orchestration, tracked-permit "
            "verifier, exact selector-identity machinery, and inherited D2 P95 "
            "method are implemented and covered by adversarial synthetic tests. "
            "PASS is not granted merely because the red-team table is hardcoded "
            "NOT_CONFIRMED. EXECUTION_READY remains false because the canonical "
            "selector digest is not frozen."
            if review_pass
            else ",".join(pass_blockers)
        ),
        "SCIENTIFIC_KERNEL_READY": SCIENTIFIC_KERNEL_READY,
        "CANONICAL_ORCHESTRATION_READY": CANONICAL_ORCHESTRATION_READY,
        "PERMIT_VERIFIER_READY": PERMIT_VERIFIER_READY,
        "EXACT_SELECTOR_IDENTITY_IMPLEMENTED": EXACT_SELECTOR_IDENTITY_IMPLEMENTED,
        "CANONICAL_SELECTOR_DIGEST_FROZEN": CANONICAL_SELECTOR_DIGEST_FROZEN,
        "CONTROL_P95_METHOD": CONTROL_P95_METHOD,
        "EXECUTION_READY": EXECUTION_READY,
        "EXECUTION_AUTHORIZED": False,
        "EXECUTION_AUTHORIZED_FLAG": EXECUTION_AUTHORIZED,
        "EXECUTION_PERMIT_PRESENT": (repo / EXECUTION_PERMIT_REL).is_file(),
        "EXECUTION_PERMIT_CREATED": False,
        "SELECTOR_IDENTITY_AUTHORITY_REL": SELECTOR_IDENTITY_AUTHORITY_REL,
        "SELECTOR_IDENTITY_AUTHORITY_PRESENT": (
            repo / SELECTOR_IDENTITY_AUTHORITY_REL
        ).is_file(),
        "SELECTOR_IDENTITY_AUTHORITY_CREATED": False,
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
        "LIFECYCLE_REPAIR": {
            "F1_CANONICAL_ORCHESTRATION": "CLOSED_DORMANT_ROUTE_WITH_HARD_FIREWALL",
            "F2_TRACKED_PERMIT_AUTHORITY": "CLOSED_NO_PERMIT_CREATED",
            "F3_EXACT_SELECTOR_IDENTITY": "IMPLEMENTED_AUTHORITY_CONTRACT_DIGEST_NOT_FROZEN",
            "F4_EXPLICIT_P95_METHOD": "CLOSED_NUMPY_LINEAR_INHERITED_FROM_D2",
        },
        "NEXT_UNIT": next_unit,
        "NOT_CREATED": [
            "RESULT",
            "execution permit",
            "selector identity authority",
            "MARKET-07",
            "ARM",
        ],
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
CONTROL_P95_METHOD = {review["CONTROL_P95_METHOD"]}
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

## Identity

```
IMPLEMENTATION_REVIEW                 = {review["IMPLEMENTATION_REVIEW"]}
SCIENTIFIC_KERNEL_READY               = {review["SCIENTIFIC_KERNEL_READY"]}
CANONICAL_ORCHESTRATION_READY         = {review["CANONICAL_ORCHESTRATION_READY"]}
PERMIT_VERIFIER_READY                 = {review["PERMIT_VERIFIER_READY"]}
EXACT_SELECTOR_IDENTITY_IMPLEMENTED   = {review["EXACT_SELECTOR_IDENTITY_IMPLEMENTED"]}
CANONICAL_SELECTOR_DIGEST_FROZEN      = {review["CANONICAL_SELECTOR_DIGEST_FROZEN"]}
SELECTOR_IDENTITY_AUTHORITY_CREATED   = {review["SELECTOR_IDENTITY_AUTHORITY_CREATED"]}
EXECUTION_READY                       = {review["EXECUTION_READY"]}
EXECUTION_AUTHORIZED                  = {review["EXECUTION_AUTHORIZED"]}
EXECUTION_PERMIT_PRESENT              = {review["EXECUTION_PERMIT_PRESENT"]}
FROZEN_AUTHORITY_STATUS               = {review["FROZEN_AUTHORITY_STATUS"]}
DESIGN_AUTHORITY_BLOCKERS             = {review["DESIGN_AUTHORITY_BLOCKERS"]}
DESIGN_JSON_SHA256                    = {review["DESIGN_JSON_SHA256"]}
RUN_IDENTITY                          = {review["RUN_IDENTITY"]}
FINAL_IMPLEMENTATION_COMMIT           = {review["FINAL_IMPLEMENTATION_COMMIT"]}
```

PASS is justified by implemented and tested machinery, not by a hardcoded
red-team table: {review["IMPLEMENTATION_REVIEW_PASS_JUSTIFICATION"]}

No execution permit exists and no selector-identity authority artifact
exists. `execute_decomposition` is the full dormant canonical route and
still fails closed before any CORE BTC OHLC is read. The route requires
the future tracked selector-identity authority (bound by permit SHA256)
and compares the reconstructed ordered digest to that frozen digest
before `evaluate_decomposition`. Count-only 1791/year census is secondary.

## Red-team (F1–F20)

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
SELECTOR_IDENTITY_AUTHORITY_CREATED = {review["SELECTOR_IDENTITY_AUTHORITY_CREATED"]}
```

## Next

`NEXT_UNIT = {review["NEXT_UNIT"]}`

The canonical selector digest is not frozen in this outcome-blind unit
and the selector-identity authority artifact was not created. The next
unit only reconstructs and freezes that tracked authority; it must not
alter the reviewed scientific execution implementation. This review does
not authorize execution: no permit exists, `EXECUTION_READY = false`,
and `EXECUTION_AUTHORIZED = false`.
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
        "SCIENTIFIC_KERNEL_READY",
        "CANONICAL_ORCHESTRATION_READY",
        "PERMIT_VERIFIER_READY",
        "EXACT_SELECTOR_IDENTITY_IMPLEMENTED",
        "CANONICAL_SELECTOR_DIGEST_FROZEN",
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
        "SELECTOR_IDENTITY_AUTHORITY_CREATED",
        "NEXT_UNIT",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
