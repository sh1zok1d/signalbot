"""GV0R03 generator feasibility contract.

Future candidates must carry this outcome-blind planning object. The transform
copies declared fields into a GV0R02 compiler proposal. It does not score
feasibility, choose an inference class, or read market outcomes.

GENERATOR_CONTRACT_V02 cards stay the full-card object. This contract does not
change that rule table or any acceptance threshold.
"""
from __future__ import annotations

from .context import ContractError

CONTRACT_VERSION = "GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V0"
COMPILER_SCHEMA_VERSION = "GV0R02_SCHEMA_V0"
COMPILER_POLICY_VERSION = "GV0R02_POLICY_V0"
POWER_ASSUMPTION_PROFILE_VERSION = "GV0R02_POWER_PROFILE_V0"
FEATURE_REGISTRY_VERSION = "GV0R02_FEATURE_REGISTRY_V0"

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
# Screens the compiler already applies. A proposal may not drop one.
FROZEN_STRESS_SCREENS = ("STRESS_SD_MULTIPLIER", "HOMOGENEOUS_EFFECT", "ZERO_EFFECT_IN_ONE_ERA")
DIRECTIONS = {"POSITIVE", "NEGATIVE", "TWO_SIDED", "AS_RECORDED"}

REQUIRED_FIELDS = (
    "PROPOSAL_ID",
    "MECHANISM",
    "FALSIFIABLE_CLAIM",
    "EVENT_OR_STATE_DEFINITION",
    "PRIMARY_OBSERVABLE",
    "ENDPOINT_MOMENT",
    "COUNTERFACTUAL_CLASS",
    "NAMED_INFERENCE_CLASS",
    "HISTORICAL_WINDOW",
    "POINT_IN_TIME_REQUIREMENTS",
    "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION",
    "DEPENDENCE_CLUSTERING_UNIT",
    "ERA_ROLES",
    "EXPECTED_EFFECT",
    "REQUIRED_STRESS_SCREENS",
    "FEATURE_REQUIREMENTS",
    "DATA_SOURCE_REFS",
    "BLOCKING_ASSUMPTIONS",
    "ERA_INVARIANCE_PRIOR",
    "ERA_INVARIANCE_RATIONALE",
    "QUALITATIVE_DEPENDENCE_SOURCES",
)

# Downstream code may not rewrite these. The compiler adjudicates; it does not repair them.
SEALED_FIELDS = (
    "NAMED_INFERENCE_CLASS",
    "HISTORICAL_WINDOW",
    "FEATURE_REQUIREMENTS",
    "DATA_SOURCE_REFS",
    "ENDPOINT_MOMENT",
    "COUNTERFACTUAL_CLASS",
    "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION",
)

OUTCOME_KEYS = {
    "PRICE", "VOLUME", "RETURN", "PNL", "CLOSE", "OPEN", "HIGH", "LOW",
    "QUOTE_VOLUME", "OUTCOME", "TARGET_VALUE",
}


def _nonempty_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reject(field: str, reason: str) -> None:
    raise ContractError(f"{field}: {reason}")


def validate_planning(proposal: dict) -> None:
    if not isinstance(proposal, dict):
        _reject("PROPOSAL", "planning object must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in proposal or proposal[field] in (None, "", [])]
    if missing:
        _reject(missing[0], "required field omitted")
    if proposal.get("CONTRACT_VERSION") not in (None, CONTRACT_VERSION):
        _reject("CONTRACT_VERSION", "must be " + CONTRACT_VERSION)
    if proposal["ENDPOINT_MOMENT"] not in ENDPOINT_MOMENTS:
        _reject("ENDPOINT_MOMENT", "not in the GV0R02 endpoint set")
    if proposal["NAMED_INFERENCE_CLASS"] not in INFERENCE_CLASSES:
        _reject("NAMED_INFERENCE_CLASS", "not in the GV0R02 inference set")
    if proposal["ERA_INVARIANCE_PRIOR"] not in ERA_PRIORS:
        _reject("ERA_INVARIANCE_PRIOR", "not in the GV0R02 prior set")
    if proposal["ERA_ROLES"] != ERA_ROLES:
        _reject("ERA_ROLES", "discovery, replication, and holdout roles are frozen")
    if not _nonempty_text(proposal["HISTORICAL_WINDOW"]):
        _reject("HISTORICAL_WINDOW", "required historical window is empty")
    if "2025" in proposal["HISTORICAL_WINDOW"] or "2026" in proposal["HISTORICAL_WINDOW"]:
        _reject("HISTORICAL_WINDOW", "protected years are not a generator window")
    effect = proposal["EXPECTED_EFFECT"]
    if not isinstance(effect, dict):
        _reject("EXPECTED_EFFECT", "effect representation must be an object")
    for key in ("DIRECTION", "MIN_MEANINGFUL_EFFECT", "UNITS", "RATIONALE"):
        if key not in effect or effect[key] in (None, ""):
            _reject("EXPECTED_EFFECT", "missing " + key)
    if effect["DIRECTION"] not in DIRECTIONS:
        _reject("EXPECTED_EFFECT", "direction is not a planning label")
    if isinstance(effect["MIN_MEANINGFUL_EFFECT"], bool) or not isinstance(effect["MIN_MEANINGFUL_EFFECT"], (int, float)):
        _reject("EXPECTED_EFFECT", "minimum meaningful effect must be numeric")
    screens = proposal["REQUIRED_STRESS_SCREENS"]
    if list(screens) != list(FROZEN_STRESS_SCREENS):
        _reject("REQUIRED_STRESS_SCREENS", "frozen stress screens may not be dropped or reordered")
    if not isinstance(proposal["FEATURE_REQUIREMENTS"], list) or not all(_nonempty_text(x) for x in proposal["FEATURE_REQUIREMENTS"]):
        _reject("FEATURE_REQUIREMENTS", "feature registry ids are required")
    refs = proposal["DATA_SOURCE_REFS"]
    if not isinstance(refs, dict) or refs.get("FEATURE_REGISTRY_VERSION") != FEATURE_REGISTRY_VERSION:
        _reject("DATA_SOURCE_REFS", "feature registry version must be GV0R02_FEATURE_REGISTRY_V0")
    if list(refs.get("FEATURE_IDS") or []) != list(proposal["FEATURE_REQUIREMENTS"]):
        _reject("DATA_SOURCE_REFS", "feature ids must match FEATURE_REQUIREMENTS")
    pit = proposal["POINT_IN_TIME_REQUIREMENTS"]
    if not isinstance(pit, list) or not pit:
        _reject("POINT_IN_TIME_REQUIREMENTS", "at least one point-in-time requirement is required")
    for row in pit:
        if not isinstance(row, dict) or not _nonempty_text(row.get("DATASET_ID")) or not _nonempty_text(row.get("PIT_STATUS")):
            _reject("POINT_IN_TIME_REQUIREMENTS", "each row needs DATASET_ID and PIT_STATUS")
    construction = proposal["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]
    if not isinstance(construction, dict):
        _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "counting rule must be an object")
    for key in ("COUNTING_UNIT", "WINDOW", "INCLUSION_RULE", "EXCLUSION_RULE", "OUTCOME_FILTER"):
        if not _nonempty_text(construction.get(key)):
            _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "missing " + key)
    if construction["OUTCOME_FILTER"] != "NONE":
        _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "counting rule must not filter on outcomes")
    if construction["WINDOW"] != proposal["HISTORICAL_WINDOW"]:
        _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "counting window must match the historical window")
    if not _nonempty_text(proposal["DEPENDENCE_CLUSTERING_UNIT"]):
        _reject("DEPENDENCE_CLUSTERING_UNIT", "clustering unit is empty")
    if not isinstance(proposal["BLOCKING_ASSUMPTIONS"], list) or not all(_nonempty_text(x) for x in proposal["BLOCKING_ASSUMPTIONS"]):
        _reject("BLOCKING_ASSUMPTIONS", "at least one blocking assumption is required")
    if not isinstance(proposal["QUALITATIVE_DEPENDENCE_SOURCES"], list) or not proposal["QUALITATIVE_DEPENDENCE_SOURCES"]:
        _reject("QUALITATIVE_DEPENDENCE_SOURCES", "dependence sources are required")
    _reject_outcome_keys(proposal)


def _reject_outcome_keys(value, path="PROPOSAL") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).upper() in OUTCOME_KEYS:
                _reject(path + "." + str(key), "outcome values are not part of the planning contract")
            _reject_outcome_keys(item, path + "." + str(key))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _reject_outcome_keys(item, path + "[" + str(i) + "]")


def to_compiler_proposal(proposal: dict) -> dict:
    """Copy a planning object into a GV0R02 proposal. No feasibility judgment."""
    validate_planning(proposal)
    effect = proposal["EXPECTED_EFFECT"]
    construction = proposal["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]
    sample = {
        "COUNTING_UNIT": construction["COUNTING_UNIT"],
        "WINDOW": construction["WINDOW"],
        "INCLUSION_RULE": construction["INCLUSION_RULE"],
        "EXCLUSION_RULE": construction["EXCLUSION_RULE"],
        "OUTCOME_FILTER": "NONE",
        "COUNT_BY_YEAR": {},
        "COUNT_BY_ERA": {"BINANCE_2020_2024": None},
        "COUNT_BY_VENUE": {},
        "COUNT_BY_EVENT_FAMILY": {},
    }
    if "DECLARED_NOMINAL_COUNT" in construction:
        count = construction["DECLARED_NOMINAL_COUNT"]
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            _reject("NOMINAL_OBSERVATION_COUNT_CONSTRUCTION", "declared count must be a positive integer")
        sample["NOMINAL_OBSERVATION_COUNT"] = count
        sample["COUNT_BY_ERA"] = {"BINANCE_2020_2024": count}
    return {
        "PROPOSAL_ID": proposal["PROPOSAL_ID"],
        "COMPILER_SCHEMA_VERSION": COMPILER_SCHEMA_VERSION,
        "COMPILER_POLICY_VERSION": COMPILER_POLICY_VERSION,
        "POWER_ASSUMPTION_PROFILE_VERSION": POWER_ASSUMPTION_PROFILE_VERSION,
        "FEATURE_REGISTRY_VERSION": FEATURE_REGISTRY_VERSION,
        "MECHANISM": proposal["MECHANISM"],
        "FALSIFIABLE_CLAIM": proposal["FALSIFIABLE_CLAIM"],
        "EXPECTED_DIRECTION": effect["DIRECTION"],
        "EVENT_OR_STATE_DEFINITION": proposal["EVENT_OR_STATE_DEFINITION"],
        "PRIMARY_OBSERVABLE": proposal["PRIMARY_OBSERVABLE"],
        "ENDPOINT_MOMENT": proposal["ENDPOINT_MOMENT"],
        "COUNTERFACTUAL_CLASS": proposal["COUNTERFACTUAL_CLASS"],
        "MIN_MEANINGFUL_EFFECT": effect["MIN_MEANINGFUL_EFFECT"],
        "MIN_MEANINGFUL_EFFECT_UNITS": effect["UNITS"],
        "MIN_MEANINGFUL_EFFECT_RATIONALE": effect["RATIONALE"],
        "ERA_INVARIANCE_PRIOR": proposal["ERA_INVARIANCE_PRIOR"],
        "ERA_INVARIANCE_RATIONALE": proposal["ERA_INVARIANCE_RATIONALE"],
        "QUALITATIVE_DEPENDENCE_SOURCES": list(proposal["QUALITATIVE_DEPENDENCE_SOURCES"]),
        "FEATURE_REQUIREMENTS": list(proposal["FEATURE_REQUIREMENTS"]),
        "POINT_IN_TIME_REQUIREMENTS": [dict(row) for row in proposal["POINT_IN_TIME_REQUIREMENTS"]],
        "NAMED_INFERENCE_CLASS": proposal["NAMED_INFERENCE_CLASS"],
        "HISTORICAL_WINDOW": proposal["HISTORICAL_WINDOW"],
        "ERA_ROLES": dict(ERA_ROLES),
        "STRUCTURAL_DEPENDENCE": {
            "CLUSTERING_UNIT": proposal["DEPENDENCE_CLUSTERING_UNIT"],
            "NO_TIMESTAMP_OVERLAP_IS_INDEPENDENCE": False,
        },
        "OUTCOME_BLIND_SAMPLE": sample,
        "REQUIRED_STRESS_SCREENS": list(FROZEN_STRESS_SCREENS),
        "BLOCKING_ASSUMPTIONS": list(proposal["BLOCKING_ASSUMPTIONS"]),
        "DATA_SOURCE_REFS": {
            "FEATURE_REGISTRY_VERSION": FEATURE_REGISTRY_VERSION,
            "FEATURE_IDS": list(proposal["FEATURE_REQUIREMENTS"]),
        },
    }


def seal(proposal: dict) -> dict:
    validate_planning(proposal)
    return {field: proposal[field] for field in SEALED_FIELDS}


def reject_downstream_edit(proposal: dict, edited: dict) -> None:
    """Refuse a silent rewrite of inference, universe, endpoint, counterfactual, or counting rule."""
    original = seal(proposal)
    if not isinstance(edited, dict):
        _reject("DOWNSTREAM", "edited proposal must be an object")
    for field, value in original.items():
        if edited.get(field) != value:
            _reject(field, "downstream change is forbidden")
