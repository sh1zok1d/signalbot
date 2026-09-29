"""GV0R03 generator feasibility contract. No LLM calls and no market outcomes."""
import copy
import json

import pytest

from scripts.research.generator_v0.context import ContractError
from scripts.research.generator_v0.feasibility_contract import (
    CONTRACT_VERSION,
    REQUIRED_FIELDS,
    SEALED_FIELDS,
    reject_downstream_edit,
    to_compiler_proposal,
    validate_planning,
)
from scripts.research.gv0r02_feasibility_compiler import REQUIRED_FIELDS as COMPILER_FIELDS
from scripts.research.gv0r02_feasibility_compiler import compile_proposal

OUTCOME_KEYS = {"PRICE", "VOLUME", "RETURN", "PNL", "CLOSE", "QUOTE_VOLUME", "OUTCOME"}


def planning():
    return {
        "CONTRACT_VERSION": CONTRACT_VERSION,
        "PROPOSAL_ID": "GV0R03_SYNTHETIC_PLANNING",
        "MECHANISM": "synthetic frequent second-moment shift",
        "FALSIFIABLE_CLAIM": "the predeclared shift is detectable under the frozen stress screen",
        "EVENT_OR_STATE_DEFINITION": "one synthetic state on every closed decision bar",
        "PRIMARY_OBSERVABLE": "synthetic standardized second moment",
        "ENDPOINT_MOMENT": "SECOND_MOMENT",
        "COUNTERFACTUAL_CLASS": "within-sample sign symmetry",
        "NAMED_INFERENCE_CLASS": "PERMUTATION_GROUP_INVARIANCE",
        "HISTORICAL_WINDOW": "2020-01..2024-12",
        "POINT_IN_TIME_REQUIREMENTS": [
            {"DATASET_ID": "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0", "PIT_STATUS": "VERIFIED"}
        ],
        "NOMINAL_OBSERVATION_COUNT_CONSTRUCTION": {
            "COUNTING_UNIT": "DECISION_BAR",
            "WINDOW": "2020-01..2024-12",
            "INCLUSION_RULE": "one row per closed decision bar in the window",
            "EXCLUSION_RULE": "none",
            "OUTCOME_FILTER": "NONE",
            "DECLARED_NOMINAL_COUNT": 10000,
        },
        "DEPENDENCE_CLUSTERING_UNIT": "DECISION_BAR",
        "ERA_ROLES": {
            "BINANCE_2020_2024": "DISCOVERY",
            "BITMEX_2016_2019": "HISTORICAL_REPLICATION_CANDIDATE",
            "Y2025_2026": "PROTECTED_HOLDOUT",
        },
        "EXPECTED_EFFECT": {
            "DIRECTION": "POSITIVE",
            "MIN_MEANINGFUL_EFFECT": 0.20,
            "UNITS": "STANDARDIZED_SECOND_MOMENT",
            "RATIONALE": "planning magnitude only",
        },
        "REQUIRED_STRESS_SCREENS": ["STRESS_SD_MULTIPLIER", "HOMOGENEOUS_EFFECT", "ZERO_EFFECT_IN_ONE_ERA"],
        "FEATURE_REQUIREMENTS": ["BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"],
        "DATA_SOURCE_REFS": {
            "FEATURE_REGISTRY_VERSION": "GV0R02_FEATURE_REGISTRY_V0",
            "FEATURE_IDS": ["BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0"],
        },
        "BLOCKING_ASSUMPTIONS": ["the counting rule does not condition on the endpoint"],
        "ERA_INVARIANCE_PRIOR": "NOT_EXPECTED",
        "ERA_INVARIANCE_RATIONALE": "discovery and replication stay separate",
        "QUALITATIVE_DEPENDENCE_SOURCES": ["adjacent decision bars share a clock"],
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def test_complete_proposal_maps_without_interpretation():
    source = planning()
    mapped = to_compiler_proposal(source)
    assert set(COMPILER_FIELDS) <= set(mapped)
    assert mapped["COMPILER_SCHEMA_VERSION"] == "GV0R02_SCHEMA_V0"
    assert mapped["COMPILER_POLICY_VERSION"] == "GV0R02_POLICY_V0"
    assert mapped["POWER_ASSUMPTION_PROFILE_VERSION"] == "GV0R02_POWER_PROFILE_V0"
    assert mapped["FEATURE_REGISTRY_VERSION"] == "GV0R02_FEATURE_REGISTRY_V0"
    assert mapped["NAMED_INFERENCE_CLASS"] == source["NAMED_INFERENCE_CLASS"]
    assert mapped["ENDPOINT_MOMENT"] == source["ENDPOINT_MOMENT"]
    assert mapped["COUNTERFACTUAL_CLASS"] == source["COUNTERFACTUAL_CLASS"]
    assert mapped["FEATURE_REQUIREMENTS"] == source["FEATURE_REQUIREMENTS"]
    assert mapped["OUTCOME_BLIND_SAMPLE"]["INCLUSION_RULE"] == source["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["INCLUSION_RULE"]
    assert "FEASIBILITY_STATUS" not in mapped
    assert "MDE_STRESS" not in mapped
    result = compile_proposal(mapped)
    assert result["FEASIBILITY_STATUS"] != "DEFINITION_INCOMPLETE"
    assert result["MARKET_OUTCOMES_OPENED"] is False


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_each_omitted_field_is_rejected(field):
    broken = planning()
    broken.pop(field)
    with pytest.raises(ContractError, match=field):
        validate_planning(broken)


def test_downstream_cannot_rewrite_sealed_fields():
    source = planning()
    mapped = to_compiler_proposal(source)
    for field in ("NAMED_INFERENCE_CLASS", "HISTORICAL_WINDOW", "ENDPOINT_MOMENT", "COUNTERFACTUAL_CLASS", "FEATURE_REQUIREMENTS"):
        assert mapped[field] == source[field]
    assert mapped["OUTCOME_BLIND_SAMPLE"]["INCLUSION_RULE"] == source["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["INCLUSION_RULE"]
    assert mapped["DATA_SOURCE_REFS"]["FEATURE_IDS"] == source["DATA_SOURCE_REFS"]["FEATURE_IDS"]
    for field in ("NAMED_INFERENCE_CLASS", "HISTORICAL_WINDOW", "ENDPOINT_MOMENT", "COUNTERFACTUAL_CLASS"):
        edited = copy.deepcopy(source)
        edited[field] = "CHANGED"
        with pytest.raises(ContractError, match=field):
            reject_downstream_edit(source, edited)
    edited = copy.deepcopy(source)
    edited["FEATURE_REQUIREMENTS"] = ["OTHER_FEATURE"]
    with pytest.raises(ContractError, match="FEATURE_REQUIREMENTS"):
        reject_downstream_edit(source, edited)
    edited = copy.deepcopy(source)
    edited["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["INCLUSION_RULE"] = "keep only large moves"
    with pytest.raises(ContractError, match="NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"):
        reject_downstream_edit(source, edited)
    edited = copy.deepcopy(source)
    edited["DATA_SOURCE_REFS"]["FEATURE_IDS"] = ["OTHER_FEATURE"]
    with pytest.raises(ContractError, match="DATA_SOURCE_REFS"):
        reject_downstream_edit(source, edited)


def test_compiler_input_needs_no_outcome_values():
    mapped = to_compiler_proposal(planning())
    assert OUTCOME_KEYS.isdisjoint(_walk_keys(mapped))
    assert mapped["OUTCOME_BLIND_SAMPLE"]["OUTCOME_FILTER"] == "NONE"
    assert mapped["HISTORICAL_WINDOW"] == "2020-01..2024-12"
    assert mapped["ERA_ROLES"]["Y2025_2026"] == "PROTECTED_HOLDOUT"
    assert mapped["OUTCOME_BLIND_SAMPLE"]["WINDOW"] == "2020-01..2024-12"
