"""Outcome-blind feasibility compiler, GV0R02_SCHEMA_V0.

Screens a pre-candidate proposal. It does not decide that a hypothesis is true,
does not open market outcomes, and does not replace preregistration.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO / "docs/research/GV0R02_FEASIBILITY_COMPILER_SCHEMA.json"
GOLDEN_PATH = REPO / "docs/research/GV0R02_FEASIBILITY_COMPILER_GOLDEN_CASES.json"
DATA_ROOT = REPO / "docs/research_data"
LEDGER_PATH = REPO / "docs/research/GV0R02_FEASIBILITY_BLOCKER_LEDGER.jsonl"

COMPILER_SCHEMA_VERSION = "GV0R02_SCHEMA_V0"
COMPILER_POLICY_VERSION = "GV0R02_POLICY_V0"
POWER_ASSUMPTION_PROFILE_VERSION = "GV0R02_POWER_PROFILE_V0"
FEATURE_REGISTRY_VERSION = "GV0R02_FEATURE_REGISTRY_V0"

# Frozen before any proposal is scored. Not adjusted from results.
POWER_PROFILE = {
    "POWER_ASSUMPTION_PROFILE_VERSION": POWER_ASSUMPTION_PROFILE_VERSION,
    "ALPHA": 0.05,
    "TARGET_POWER": 0.80,
    "SIDEDNESS": "TWO_SIDED",
    "Z_ALPHA": 1.959963984540054,
    "Z_TARGET": 0.8416212335729143,
    "BASE_SD": 1.0,
    "STRESS_SD_MULTIPLIER": 2.0,
    "SIMULATION_CAP": 50,
    "SIMULATION_SEED": 20020,
}

STATUS_PRIORITY = [
    "DEFINITION_INCOMPLETE",
    "DATA_BLOCKED",
    "PIT_BLOCKED",
    "INFERENCE_SUPPORT_INSUFFICIENT",
    "STRUCTURAL_INFERENCE_RISK",
    "INFORMATIONALLY_WEAK",
    "FEASIBLE_FOR_PREREGISTRATION",
]
REQUIRED_FIELDS = [
    "PROPOSAL_ID",
    "MECHANISM",
    "FALSIFIABLE_CLAIM",
    "EXPECTED_DIRECTION",
    "EVENT_OR_STATE_DEFINITION",
    "PRIMARY_OBSERVABLE",
    "ENDPOINT_MOMENT",
    "COUNTERFACTUAL_CLASS",
    "MIN_MEANINGFUL_EFFECT",
    "MIN_MEANINGFUL_EFFECT_UNITS",
    "MIN_MEANINGFUL_EFFECT_RATIONALE",
    "ERA_INVARIANCE_PRIOR",
    "ERA_INVARIANCE_RATIONALE",
    "QUALITATIVE_DEPENDENCE_SOURCES",
    "FEATURE_REQUIREMENTS",
    "POINT_IN_TIME_REQUIREMENTS",
    "NAMED_INFERENCE_CLASS",
]
ENDPOINT_MOMENTS = {"FIRST_MOMENT", "SECOND_MOMENT", "PARTICIPATION", "RELATIVE_VALUE", "OTHER"}
ERA_PRIORS = {"EXPECTED", "NOT_EXPECTED", "UNKNOWN"}
INFERENCE_CLASSES = {
    "EXACT_RANDOMIZATION",
    "PERMUTATION_GROUP_INVARIANCE",
    "PLACEBO_REFERENCE_DISTRIBUTION",
    "UNSPECIFIED_REQUIRES_FULL_DESIGN",
}
ERA_ROLES = {
    "BINANCE_2020_2024": "DISCOVERY",
    "BITMEX_2016_2019": "HISTORICAL_REPLICATION_CANDIDATE",
    "Y2025_2026": "PROTECTED_HOLDOUT",
}
FORBIDDEN_REVISION_FIELDS = {
    "MIN_MEANINGFUL_EFFECT",
    "MIN_MEANINGFUL_EFFECT_UNITS",
    "ERA_INVARIANCE_PRIOR",
    "NAMED_INFERENCE_CLASS",
}


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def assert_design_identity() -> None:
    schema = _load(SCHEMA_PATH)
    if schema["COMPILER_SCHEMA_VERSION"] != COMPILER_SCHEMA_VERSION:
        raise SystemExit("COMPILER_DESIGN_CONFLICT schema version")
    if schema["COMPILER_POLICY_VERSION"] != COMPILER_POLICY_VERSION:
        raise SystemExit("COMPILER_DESIGN_CONFLICT policy version")
    if schema["POWER_ASSUMPTION_PROFILE_VERSION"] != POWER_ASSUMPTION_PROFILE_VERSION:
        raise SystemExit("COMPILER_DESIGN_CONFLICT power profile")
    if schema["STATUS_PRIORITY"] != STATUS_PRIORITY:
        raise SystemExit("COMPILER_DESIGN_CONFLICT status priority")
    golden = _load(GOLDEN_PATH)
    if golden["COMPILER_SCHEMA_VERSION"] != COMPILER_SCHEMA_VERSION:
        raise SystemExit("COMPILER_DESIGN_CONFLICT golden schema")


def derive_feature_registry() -> dict:
    """Registry rows come from pinned dataset manifests. Values are not opened."""
    features = []
    for manifest_path in sorted(DATA_ROOT.glob("*/MANIFEST.json")):
        manifest = _load(manifest_path)
        dataset_id = manifest.get("DATASET_ID")
        if not dataset_id:
            continue
        digest = manifest.get("CANONICAL_DATASET_DIGEST") or manifest.get("CANONICAL_MANIFEST_DIGEST")
        years = manifest.get("CANONICAL_YEARS")
        if years is None and manifest.get("END_MONTH"):
            years = [int(manifest["END_MONTH"][:4])]
        venue = {}
        if manifest.get("MARKET"):
            venue[manifest["MARKET"]] = {"START": manifest.get("END_MONTH"), "VALUES_OPENED": False}
        features.append({
            "feature_id": dataset_id,
            "definition_ref": str(manifest_path.relative_to(REPO)),
            "definition_digest": digest,
            "input_dataset_ids": [dataset_id],
            "unit": "dataset",
            "normalization_rule": "identity of the pinned manifest",
            "lookback_requirement": None,
            "available_at_rule": "as-of the pinned publication or bar open time; values are not read here",
            "coverage_by_venue": venue,
            "coverage_by_instrument": {manifest.get("INSTRUMENT", "UNSPECIFIED"): years},
            "completeness": "MANIFEST_ONLY",
            "known_breaks": [],
            "cross_venue_notes": "No cross-venue portability grade is assigned.",
            "quality_status": "PINNED_MANIFEST",
        })
    features.sort(key=lambda row: row["feature_id"])
    body = {"FEATURE_REGISTRY_VERSION": FEATURE_REGISTRY_VERSION, "FEATURES": features}
    return {**body, "FEATURE_REGISTRY_DIGEST": sha256_hex(canonical_json(body))}


def _blank_numbers():
    return {
        "PRIMARY_SUPPORT_SIZE": None,
        "MIN_ATTAINABLE_P": None,
        "REFERENCE_SUPPORT_SIZE": None,
        "REFERENCE_SUPPORT_RESOLUTION": None,
        "MONTE_CARLO_P_FLOOR": None,
        "ALPHA_ATTAINABLE": None,
        "MDE_BASE": None,
        "MDE_STRESS": None,
        "POWER_AT_MIN_MEANINGFUL_EFFECT_BASE": None,
        "POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS": None,
    }


def _analytic_mde(sd: float, n_eff: float) -> float | None:
    if n_eff is None or n_eff <= 0:
        return None
    return (POWER_PROFILE["Z_ALPHA"] + POWER_PROFILE["Z_TARGET"]) * sd / (n_eff ** 0.5)


def _normal_power(effect: float | None, sd: float, n_eff: float | None) -> float | None:
    """Two-sided normal power at the frozen alpha. Profile constants are not changed."""
    if effect is None or n_eff is None or n_eff <= 0 or sd <= 0:
        return None
    se = sd / (n_eff ** 0.5)
    z = abs(effect) / se - POWER_PROFILE["Z_ALPHA"]
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def compile_proposal(proposal: dict, *, registry: dict | None = None) -> dict:
    assert_design_identity()
    registry = registry or derive_feature_registry()
    reasons = []
    blockers = []
    numbers = _blank_numbers()
    flags = {status: False for status in STATUS_PRIORITY}

    missing = [field for field in REQUIRED_FIELDS if field not in proposal or proposal[field] in (None, "", [])]
    if proposal.get("ENDPOINT_MOMENT") not in ENDPOINT_MOMENTS:
        missing.append("ENDPOINT_MOMENT")
    if proposal.get("ERA_INVARIANCE_PRIOR") not in ERA_PRIORS:
        missing.append("ERA_INVARIANCE_PRIOR")
    if proposal.get("NAMED_INFERENCE_CLASS") not in INFERENCE_CLASSES:
        missing.append("NAMED_INFERENCE_CLASS")
    if proposal.get("COMPILER_SCHEMA_VERSION") not in (None, COMPILER_SCHEMA_VERSION):
        missing.append("COMPILER_SCHEMA_VERSION")
    if missing:
        flags["DEFINITION_INCOMPLETE"] = True
        reasons.append("required semantic fields are absent or not in the frozen enums")
        blockers.append({
            "BLOCKER_CODE": "DEFINITION_INCOMPLETE",
            "BLOCKER_OBJECT": {"FIELDS": sorted(set(missing))},
        })

    by_id = {row["feature_id"]: row for row in registry["FEATURES"]}
    data_status = "DATA_READY"
    pit_status = "PIT_READY"
    if not flags["DEFINITION_INCOMPLETE"]:
        for feature_id in proposal["FEATURE_REQUIREMENTS"]:
            row = by_id.get(feature_id)
            if row is None:
                data_status = "DATA_BLOCKED"
                flags["DATA_BLOCKED"] = True
                reasons.append(f"feature {feature_id} is not in the derived registry")
                blockers.append({
                    "BLOCKER_CODE": "MISSING_FEATURE",
                    "BLOCKER_OBJECT": {"feature_id": feature_id},
                })
            elif row["known_breaks"]:
                data_status = "DATA_BLOCKED"
                flags["DATA_BLOCKED"] = True
                reasons.append(f"known breaks invalidate {feature_id}")
                blockers.append({
                    "BLOCKER_CODE": "INSUFFICIENT_HISTORY",
                    "BLOCKER_OBJECT": {"feature_id": feature_id, "known_breaks": row["known_breaks"]},
                })
        for requirement in proposal["POINT_IN_TIME_REQUIREMENTS"]:
            dataset_id = requirement.get("DATASET_ID")
            if dataset_id not in by_id or requirement.get("PIT_STATUS") == "UNESTABLISHED":
                pit_status = "PIT_BLOCKED"
                flags["PIT_BLOCKED"] = True
                reasons.append(f"point-in-time provenance is not established for {dataset_id}")
                blockers.append({
                    "BLOCKER_CODE": "PIT_NOT_ESTABLISHED",
                    "BLOCKER_OBJECT": {"DATASET_ID": dataset_id},
                })

    sample = proposal.get("OUTCOME_BLIND_SAMPLE")
    if sample is None:
        nominal_n = None
        n_by_era = {}
        sample_note = "SAMPLE_NOT_INSTANTIABLE_WITHOUT_OUTCOMES"
    else:
        nominal_n = sample.get("NOMINAL_OBSERVATION_COUNT")
        n_by_era = {
            "COUNT_BY_YEAR": sample.get("COUNT_BY_YEAR", {}),
            "COUNT_BY_ERA": sample.get("COUNT_BY_ERA", {}),
            "COUNT_BY_VENUE": sample.get("COUNT_BY_VENUE", {}),
            "COUNT_BY_EVENT_FAMILY": sample.get("COUNT_BY_EVENT_FAMILY", {}),
        }
        sample_note = "COUNTED_FROM_OUTCOME_BLIND_METADATA"

    dependence = proposal.get("STRUCTURAL_DEPENDENCE") or {
        "OVERLAPPING_OUTCOME_WINDOWS": None,
        "OVERLAPPING_ESTIMATION_WINDOWS": None,
        "REUSED_CONTROLS": None,
        "SHARED_BASELINES": None,
        "ROLLING_WINDOW_OVERLAP": None,
        "NESTED_OBSERVATIONS": None,
        "EVENT_CLUSTERING": None,
        "NO_TIMESTAMP_OVERLAP_IS_INDEPENDENCE": False,
    }
    dependence = {**dependence, "NO_TIMESTAMP_OVERLAP_IS_INDEPENDENCE": False}

    inference = proposal.get("NAMED_INFERENCE_CLASS")
    planning = proposal.get("FROZEN_OUTCOME_BLIND_SCREEN") or {}
    if inference == "UNSPECIFIED_REQUIRES_FULL_DESIGN":
        flags["STRUCTURAL_INFERENCE_RISK"] = True
        reasons.append("the named class defers the procedure to a full design unit")
        blockers.append({
            "BLOCKER_CODE": "COUNTERFACTUAL_UNRESOLVED",
            "BLOCKER_OBJECT": {"NAMED_INFERENCE_CLASS": inference},
        })
    elif inference == "EXACT_RANDOMIZATION" and planning.get("OBSERVED_ASSIGNMENT_IN_REFERENCE_SUPPORT") is False:
        flags["STRUCTURAL_INFERENCE_RISK"] = True
        reasons.append("the observed assignment is outside the claimed exact support and was not repaired")
        numbers["REFERENCE_SUPPORT_RESOLUTION"] = planning.get("REFERENCE_SUPPORT_RESOLUTION")
        numbers["REFERENCE_SUPPORT_SIZE"] = planning.get("REFERENCE_SUPPORT_SIZE")
        numbers["MIN_ATTAINABLE_P"] = None
        blockers.append({
            "BLOCKER_CODE": "DEPENDENCE_TOO_STRONG",
            "BLOCKER_OBJECT": {"REASON": "OBSERVED_ASSIGNMENT_NOT_IN_EXACT_SUPPORT"},
        })
    elif inference in {"EXACT_RANDOMIZATION", "PERMUTATION_GROUP_INVARIANCE"}:
        orbit = planning.get("PRIMARY_LABEL_ORBIT_SIZE")
        min_p = planning.get("MIN_ATTAINABLE_P")
        if min_p is None and orbit is not None:
            min_p = 1.0 / int(orbit)
        numbers["PRIMARY_SUPPORT_SIZE"] = orbit
        numbers["MIN_ATTAINABLE_P"] = min_p
        alpha = POWER_PROFILE["ALPHA"]
        attainable = None if min_p is None else min_p <= alpha
        numbers["ALPHA_ATTAINABLE"] = attainable
        if attainable is False:
            flags["INFERENCE_SUPPORT_INSUFFICIENT"] = True
            reasons.append(f"minimum attainable p {min_p} is above alpha {alpha}")
            blockers.append({
                "BLOCKER_CODE": "ALPHA_UNATTAINABLE",
                "BLOCKER_OBJECT": {"MIN_ATTAINABLE_P": min_p, "ALPHA": alpha, "PRIMARY_LABEL_ORBIT_SIZE": orbit},
            })
    elif inference == "PLACEBO_REFERENCE_DISTRIBUTION":
        numbers["REFERENCE_SUPPORT_SIZE"] = planning.get("REFERENCE_SUPPORT_SIZE")
        numbers["REFERENCE_SUPPORT_RESOLUTION"] = planning.get("REFERENCE_SUPPORT_RESOLUTION")
        numbers["MONTE_CARLO_P_FLOOR"] = planning.get("MONTE_CARLO_P_FLOOR", 1.0 / 1001.0)
        numbers["MIN_ATTAINABLE_P"] = None
        numbers["ALPHA_ATTAINABLE"] = numbers["MONTE_CARLO_P_FLOOR"] <= POWER_PROFILE["ALPHA"]
        reasons.append("placebo reference resolution is not an exact attainable p")

    screen = planning.get("POWER")
    if screen:
        numbers["MDE_BASE"] = screen.get("MDE_BASE")
        numbers["MDE_STRESS"] = screen.get("MDE_STRESS")
        numbers["POWER_AT_MIN_MEANINGFUL_EFFECT_BASE"] = screen.get("POWER_BASE")
        numbers["POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS"] = screen.get("POWER_STRESS")
    else:
        n_eff = None if nominal_n is None else float(nominal_n)
        numbers["MDE_BASE"] = _analytic_mde(POWER_PROFILE["BASE_SD"], n_eff)
        numbers["MDE_STRESS"] = _analytic_mde(
            POWER_PROFILE["BASE_SD"] * POWER_PROFILE["STRESS_SD_MULTIPLIER"], n_eff
        )
        numbers["POWER_AT_MIN_MEANINGFUL_EFFECT_BASE"] = _normal_power(
            proposal.get("MIN_MEANINGFUL_EFFECT"), POWER_PROFILE["BASE_SD"], n_eff
        )
        numbers["POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS"] = _normal_power(
            proposal.get("MIN_MEANINGFUL_EFFECT"),
            POWER_PROFILE["BASE_SD"] * POWER_PROFILE["STRESS_SD_MULTIPLIER"],
            n_eff,
        )

    effect = proposal.get("MIN_MEANINGFUL_EFFECT")
    stress_power = numbers["POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS"]
    stress_mde = numbers["MDE_STRESS"]
    weak = False
    if stress_power is not None and stress_power < POWER_PROFILE["TARGET_POWER"]:
        weak = True
    if stress_mde is not None and effect is not None and abs(stress_mde) > abs(effect) and inference != "PLACEBO_REFERENCE_DISTRIBUTION":
        weak = True
    if weak and not flags["INFERENCE_SUPPORT_INSUFFICIENT"]:
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("the stress screen does not reach the frozen target at the predeclared effect")
        blockers.append({
            "BLOCKER_CODE": "MDE_TOO_LARGE",
            "BLOCKER_OBJECT": {
                "MIN_MEANINGFUL_EFFECT": effect,
                "MDE_STRESS": stress_mde,
                "POWER_STRESS": stress_power,
                "TARGET_POWER": POWER_PROFILE["TARGET_POWER"],
            },
        })

    prior = proposal.get("ERA_INVARIANCE_PRIOR")
    pooled = prior == "EXPECTED"
    era = {
        "ROLES": ERA_ROLES,
        "POOLED_INTO_DISCOVERY": False,
        "BITMEX_ADDED_TO_DISCOVERY_N": False,
        "HOMOGENEOUS_EFFECT_SCREEN": "REPORTED" if pooled else "NOT_APPLICABLE",
        "ZERO_EFFECT_IN_ONE_ERA_STRESS": "REPORTED" if pooled else "NOT_APPLICABLE",
    }
    holdout = {
        "PROTECTED_VALUES_OPENED": False,
        "COVERAGE_RECORDED": "LIMITED_SURFACE_NOT_A_REJECTION",
        "AUTOMATIC_REJECTION": False,
    }
    warning = None
    if nominal_n is not None and nominal_n < 300 and proposal.get("ENDPOINT_MOMENT") == "FIRST_MOMENT":
        warning = "GENERATOR_WARNING_FIRST_MOMENT_BELOW_300_NOT_A_REJECTION"

    harder = [name for name in STATUS_PRIORITY if name != "FEASIBLE_FOR_PREREGISTRATION" and flags[name]]
    if not harder:
        flags["FEASIBLE_FOR_PREREGISTRATION"] = True
        reasons.append("no harder status matched")
    status = next(name for name in STATUS_PRIORITY if flags[name])
    otherwise_strong = status in {"INFERENCE_SUPPORT_INSUFFICIENT", "INFORMATIONALLY_WEAK", "STRUCTURAL_INFERENCE_RISK"}
    proposal_digest = sha256_hex(canonical_json({k: proposal[k] for k in REQUIRED_FIELDS if k in proposal}))
    identity_body = {
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "POWER_ASSUMPTION_PROFILE_VERSION": POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_VERSION": registry["FEATURE_REGISTRY_VERSION"],
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
    }
    result_id = sha256_hex(canonical_json(identity_body))
    result = {
        "RESULT_ID": result_id,
        "PROPOSAL_ID": proposal.get("PROPOSAL_ID"),
        "PROPOSAL_DIGEST": proposal_digest,
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "FEATURE_REGISTRY_VERSION": registry["FEATURE_REGISTRY_VERSION"],
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
        "POWER_ASSUMPTION_PROFILE_VERSION": POWER_ASSUMPTION_PROFILE_VERSION,
        "DATA_STATUS": data_status,
        "PIT_STATUS": pit_status,
        "NOMINAL_N": nominal_n,
        "N_BY_ERA": n_by_era,
        "SAMPLE_NOTE": sample_note,
        "STRUCTURAL_DEPENDENCE_SUMMARY": dependence,
        "INFERENCE_FEASIBILITY": inference,
        "NAMED_INFERENCE_CLASS": inference,
        **numbers,
        "MIN_MEANINGFUL_EFFECT": effect,
        "TARGET_POWER": POWER_PROFILE["TARGET_POWER"],
        "PLAUSIBLE_EFFECT_ASSESSMENT": None,
        "DISCOVERY_COMPATIBILITY": ERA_ROLES["BINANCE_2020_2024"],
        "HISTORICAL_REPLICATION_COMPATIBILITY": ERA_ROLES["BITMEX_2016_2019"],
        "PROTECTED_HOLDOUT_COMPATIBILITY": holdout,
        "ERA_POLICY": era,
        "RARE_EVENT_HEURISTIC": warning,
        "BLOCKERS": blockers,
        "OTHERWISE_STRONG": otherwise_strong,
        "FEASIBILITY_STATUS": status,
        "STATUS_REASONS": reasons,
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_VALUES_OPENED": False,
        "PROTECTED_2026_VALUES_OPENED": False,
    }
    return result


def append_blocker_ledger(result: dict, path: Path = LEDGER_PATH) -> None:
    row = {
        "PROPOSAL_ID": result["PROPOSAL_ID"],
        "RESULT_ID": result["RESULT_ID"],
        "COMPILER_SCHEMA_VERSION": result["COMPILER_SCHEMA_VERSION"],
        "COMPILER_POLICY_VERSION": result["COMPILER_POLICY_VERSION"],
        "POWER_PROFILE_VERSION": result["POWER_ASSUMPTION_PROFILE_VERSION"],
        "BLOCKER_CODE": None if not result["BLOCKERS"] else result["BLOCKERS"][0]["BLOCKER_CODE"],
        "BLOCKER_OBJECT": None if not result["BLOCKERS"] else result["BLOCKERS"][0]["BLOCKER_OBJECT"],
        "FEASIBILITY_STATUS": result["FEASIBILITY_STATUS"],
        "OTHERWISE_STRONG": result["OTHERWISE_STRONG"],
        "RECORDED_AT": "2026-09-25T12:00:00Z",
    }
    with path.open("a") as handle:
        handle.write(canonical_json(row).decode() + "\n")


def check_revision(parent: dict, revised: dict, *, revision_number: int, reason: str, parent_result_id: str) -> dict:
    if revision_number != 1:
        raise ValueError("only one revision is permitted")
    if not reason:
        raise ValueError("revision reason is required")
    changed = [field for field in FORBIDDEN_REVISION_FIELDS if parent.get(field) != revised.get(field)]
    if changed:
        raise ValueError("forbidden field changed after the first compile: " + ",".join(changed))
    return {
        "ORIGINAL_PROPOSAL_ID": parent["PROPOSAL_ID"],
        "PARENT_PROPOSAL_ID": parent["PROPOSAL_ID"],
        "ORIGINAL_RESULT_ID": parent_result_id,
        "REVISION_NUMBER": 1,
        "REVISION_REASON": reason,
    }


def _base_proposal(**overrides) -> dict:
    proposal = {
        "PROPOSAL_ID": "UNSET",
        "MECHANISM": "frozen planning record",
        "FALSIFIABLE_CLAIM": "the predeclared effect is detectable under the frozen screen",
        "EXPECTED_DIRECTION": "AS_RECORDED",
        "EVENT_OR_STATE_DEFINITION": "outcome-blind structural fixture",
        "PRIMARY_OBSERVABLE": "planning statistic",
        "ENDPOINT_MOMENT": "FIRST_MOMENT",
        "COUNTERFACTUAL_CLASS": "matched control",
        "MIN_MEANINGFUL_EFFECT": 0.5,
        "MIN_MEANINGFUL_EFFECT_UNITS": "AS_RECORDED",
        "MIN_MEANINGFUL_EFFECT_RATIONALE": "taken from the closed outcome-blind record",
        "ERA_INVARIANCE_PRIOR": "NOT_EXPECTED",
        "ERA_INVARIANCE_RATIONALE": "discovery and replication stay separate",
        "QUALITATIVE_DEPENDENCE_SOURCES": ["frozen design dependence summary"],
        "FEATURE_REQUIREMENTS": ["BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"],
        "POINT_IN_TIME_REQUIREMENTS": [{"DATASET_ID": "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0", "PIT_STATUS": "VERIFIED"}],
        "NAMED_INFERENCE_CLASS": "PERMUTATION_GROUP_INVARIANCE",
        "OUTCOME_BLIND_SAMPLE": {
            "NOMINAL_OBSERVATION_COUNT": 400,
            "COUNT_BY_YEAR": {},
            "COUNT_BY_ERA": {"BINANCE_2020_2024": 400},
            "COUNT_BY_VENUE": {"BINANCE": 400},
            "COUNT_BY_EVENT_FAMILY": {},
        },
    }
    proposal.update(overrides)
    return proposal


def golden_proposals() -> dict[str, dict]:
    c020_close = _load(REPO / "docs/research/GV0R01_C020_CLOSE.json")
    return {
        "GOLDEN_C012": _base_proposal(
            PROPOSAL_ID="GOLDEN_C012",
            FEATURE_REQUIREMENTS=["BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"],
            MIN_MEANINGFUL_EFFECT=0.5,
            MIN_MEANINGFUL_EFFECT_UNITS="SINGLE_WINDOW_SD",
            NAMED_INFERENCE_CLASS="PERMUTATION_GROUP_INVARIANCE",
            FROZEN_OUTCOME_BLIND_SCREEN={
                "PRIMARY_LABEL_ORBIT_SIZE": "3204454418600404451328000000000",
                "POWER": {"MDE_BASE": 0.5, "MDE_STRESS": 0.6093023255813953, "POWER_BASE": None, "POWER_STRESS": None},
            },
        ),
        "GOLDEN_C004": _base_proposal(
            PROPOSAL_ID="GOLDEN_C004",
            NAMED_INFERENCE_CLASS="PERMUTATION_GROUP_INVARIANCE",
            FROZEN_OUTCOME_BLIND_SCREEN={
                "PRIMARY_LABEL_ORBIT_SIZE": 16,
                "MIN_ATTAINABLE_P": 0.0625,
            },
        ),
        "GOLDEN_C020": _base_proposal(
            PROPOSAL_ID="GOLDEN_C020",
            FEATURE_REQUIREMENTS=["NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0"],
            POINT_IN_TIME_REQUIREMENTS=[{"DATASET_ID": "NYSE_HOLIDAY_CALENDAR_ARCHIVE_V0", "PIT_STATUS": "VERIFIED"}],
            MIN_MEANINGFUL_EFFECT=-0.10536051565782628,
            MIN_MEANINGFUL_EFFECT_UNITS="LOG_US_SESSION_SHARE_DISPLACEMENT",
            NAMED_INFERENCE_CLASS="PLACEBO_REFERENCE_DISTRIBUTION",
            OUTCOME_BLIND_SAMPLE={"NOMINAL_OBSERVATION_COUNT": 47, "COUNT_BY_ERA": {"BINANCE_2020_2024": 47}, "COUNT_BY_YEAR": {}, "COUNT_BY_VENUE": {"BINANCE": 47}, "COUNT_BY_EVENT_FAMILY": {"NYSE_FULL_WEEKDAY_CLOSURE": 47}},
            FROZEN_OUTCOME_BLIND_SCREEN={
                "REFERENCE_SUPPORT_SIZE": c020_close["REFERENCE_SUPPORT_SIZE"],
                "REFERENCE_SUPPORT_RESOLUTION": c020_close["REFERENCE_SUPPORT_RESOLUTION"],
                "MONTE_CARLO_P_FLOOR": c020_close["MONTE_CARLO_P_FLOOR"],
                "OBSERVED_ASSIGNMENT_IN_REFERENCE_SUPPORT": False,
                "POWER": {"MDE_BASE": None, "MDE_STRESS": None, "POWER_BASE": 0.79, "POWER_STRESS": 0.4},
            },
        ),
    }


def compile_golden() -> dict:
    started = dt.datetime.now(dt.timezone.utc)
    registry = derive_feature_registry()
    structural_started = dt.datetime.now(dt.timezone.utc)
    results = {name: compile_proposal(proposal, registry=registry) for name, proposal in golden_proposals().items()}
    structural_done = dt.datetime.now(dt.timezone.utc)
    # Pass E for these fixtures reads the frozen screen; the analytic profile is not refit.
    power_done = dt.datetime.now(dt.timezone.utc)
    return {
        "FEATURE_REGISTRY_VERSION": registry["FEATURE_REGISTRY_VERSION"],
        "FEATURE_REGISTRY_DIGEST": registry["FEATURE_REGISTRY_DIGEST"],
        "RESULTS": results,
        "FAST_PASS_RUNTIME_SECONDS": (structural_done - structural_started).total_seconds(),
        "POWER_PASS_RUNTIME_SECONDS": (power_done - structural_done).total_seconds(),
        "TOTAL_RUNTIME_SECONDS": (power_done - started).total_seconds(),
        "MARKET_OUTCOMES_OPENED": False,
    }
