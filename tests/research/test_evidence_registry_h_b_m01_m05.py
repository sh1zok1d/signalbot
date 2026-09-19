"""Program-level evidence-registry extension through MARKET-05.

Documentation / evidence-synthesis only. Does not rerun MARKET-05, inspect
protected OOS, create MARKET-06, or treat MARKET-04H as a 17th scientific unit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
OLD_MD = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.md"
OLD_JSON = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.json"
NEW_MD = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M05.md"
NEW_JSON = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M05.json"
INTERP_MD = REPO / "docs/research/MARKET_05_PROGRAM_INTERPRETATION.md"
INTERP_JSON = REPO / "docs/research/MARKET_05_PROGRAM_INTERPRETATION.json"
OBS_MD = REPO / "docs/research/FORWARD_MARKET_OBSERVABILITY_V1.md"
OBS_JSON = REPO / "docs/research/FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_CONTRACT.json"
RESULT_JSON = REPO / "docs/research/MARKET_05_RESULT.json"
RESULT_MD = REPO / "docs/research/MARKET_05_RESULT.md"

PRIOR_UNITS = [
    "H01",
    "H02",
    "H03",
    "H04",
    "H05",
    "B2-01",
    "B2-02",
    "B2-03",
    "B2-04",
    "B2-05",
    "B2-06",
    "MARKET-01",
    "MARKET-02",
    "MARKET-03",
]

EXPECTED_UNITS = PRIOR_UNITS + ["MARKET-04", "MARKET-05"]

FROZEN_REGISTRY_MD_SHA256 = "f30b44a2d333600e3e6417f517e65c5dc1bde81fb03a6d1870cfcf19576c83c2"
FROZEN_REGISTRY_JSON_SHA256 = "0892f66db94cc679cb938980127985ab9a81efece62b2adb755c1b7e8a048c72"

RESULT_HEAD = "828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b"
RESULT_TREE = "338e72d23ff7f5547191221527b762a47e4e48bc"
RUN_IDENTITY = "6957613de4b035d850fc97edb833565c5fd3d7b085aa158e0992b88142190635"
RESULT_JSON_SHA256 = "80a29335dc697e784c1bb6d47c81dd1760f2f19bc49d36573b59372255a47f14"
RESULT_MD_SHA256 = "f0849bdaf3cf1fb0e939696d2fdc230342045717f902fcb5ef12f28b889db6ed"

REQUIRED_UNIT_FIELDS = (
    "id",
    "lineage",
    "mechanism_family",
    "original_claim",
    "evidence_class",
    "canonical_status",
    "scientific_outcome",
    "positive_evidence",
    "negative_evidence",
    "posthoc_residuals",
    "allowed_future_use",
    "forbidden_reinterpretations",
    "independence_notes",
    "protected_oos_touched",
    "authoritative_source_paths",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_old() -> dict:
    return json.loads(OLD_JSON.read_text(encoding="utf-8"))


def _load_new() -> dict:
    return json.loads(NEW_JSON.read_text(encoding="utf-8"))


def _load_interp() -> dict:
    return json.loads(INTERP_JSON.read_text(encoding="utf-8"))


def _load_obs() -> dict:
    return json.loads(OBS_JSON.read_text(encoding="utf-8"))


def test_frozen_fourteen_unit_registry_bytes_unchanged():
    assert _sha256(OLD_MD) == FROZEN_REGISTRY_MD_SHA256
    assert _sha256(OLD_JSON) == FROZEN_REGISTRY_JSON_SHA256
    old = _load_old()
    assert old["scope"]["unit_count"] == 14
    assert old["scope"]["market_04_included"] is False
    assert "MARKET-04" not in old["units"]
    assert "MARKET-05" not in old["units"]


def test_prior_unit_identities_copied_verbatim():
    old = _load_old()
    new = _load_new()
    for uid in PRIOR_UNITS:
        assert new["units"][uid] == old["units"][uid], uid
        assert new["units"][uid]["id"] == uid
        assert new["units"][uid]["evidence_class"] == old["units"][uid]["evidence_class"]
        assert new["units"][uid]["canonical_status"] == old["units"][uid]["canonical_status"]
        assert new["units"][uid]["scientific_outcome"] == old["units"][uid]["scientific_outcome"]


def test_sixteen_scientific_units_and_no_market_06():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    assert new["scope"]["unit_ids"] == EXPECTED_UNITS
    assert list(new["units"].keys()) == EXPECTED_UNITS
    assert new["scope"]["unit_count"] == 16
    assert new["scope"]["h_unit_count"] == 5
    assert new["scope"]["b_unit_count"] == 6
    assert new["scope"]["market_unit_count"] == 5
    assert new["scope"]["market_04_included"] is True
    assert new["scope"]["market_05_included"] is True
    assert new["scope"]["market_04h_top_level_unit"] is False
    assert new["scope"]["market_06_included"] is False
    assert "MARKET-06" not in new["units"]
    assert "MARKET-04H" not in new["units"]
    assert new["market_06_created"] is False
    assert new["new_scientific_hypothesis_id_created"] is False
    assert "REGISTRY_UNIT_COUNT = 16" in md
    assert "market_06_included = false" in md
    assert "MARKET_06_CREATED = FALSE" in md or "MARKET_06_CREATED = NO" in md


def test_required_fields_and_no_market_06_artifact():
    new = _load_new()
    for uid, unit in new["units"].items():
        for field in REQUIRED_UNIT_FIELDS:
            assert field in unit, f"{uid} missing {field}"
        assert unit["protected_oos_touched"] is False
    for rel in (
        "docs/research/MARKET_06.md",
        "docs/research/MARKET_06.json",
        "docs/research/MARKET_06_PREREG.md",
        "docs/research/MARKET_06_PREREG.json",
        "docs/research/MARKET_06_CANDIDATE.md",
        "docs/research/MARKET_06_CANDIDATE.json",
        "docs/research/MARKET_06_RESULT.md",
        "docs/research/MARKET_06_RESULT.json",
    ):
        assert not (REPO / rel).exists()


def test_market_04_selected_not_tested_blocked_not_rejected():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    m04 = new["units"]["MARKET-04"]
    facts = new["program_facts"]
    assert m04["evidence_class"] == "BLOCKED_OBSERVABLE"
    assert m04["canonical_status"] == "SELECTED_NOT_TESTED_BLOCKED_HISTORICAL_OBSERVABLE"
    assert m04["scientific_outcome"] is None
    assert m04["tested"] is False
    assert m04["rejected"] is False
    assert m04["selected"] is True
    assert m04["not_tested"] is True
    assert m04["not_rejected"] is True
    assert m04["blocked_historical_observable"] is True
    assert m04["absence_of_execution_is_negative_evidence"] is False
    assert m04["scientific_failure"] is False
    assert facts["market_04_status"] == "BLOCKED_OBSERVABLE / NOT_TESTED"
    assert facts["market_04_rejected"] is False
    assert facts["market_04_tested"] is False
    assert "market_04_rejected = false" in md
    assert "Do not mark MARKET-04 rejected." in md
    m04h = m04["blocked_observable_history"]["m04h"]
    assert m04h["independent_scientific_evidence_unit"] is False
    assert m04h["top_level_registry_unit"] is False
    assert m04h["lineage_kind"] == (
        "OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE"
    )
    assert m04h["status"] == "BLOCKED_OBSERVABLE"
    assert m04h["scientific_negative_evidence"] is False
    assert "scientific_negative_evidence = false" in md


def test_market_03_remains_external_reproduction():
    new = _load_new()
    m03 = new["units"]["MARKET-03"]
    assert m03["evidence_class"] == "EXTERNAL_REPRODUCTION"
    assert m03["scientific_outcome"] == "REPRODUCED_DIRECTION"
    assert m03["validated_oos"] is False
    assert new["program_facts"]["market_03_status"] == (
        "EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION"
    )
    assert new["program_facts"]["m03_is_external_historical_reproduction"] is True


def test_market_05_binds_exact_result_identity_and_no_evidence():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    interp = _load_interp()
    m05 = new["units"]["MARKET-05"]
    ident = m05["result_identity"]
    assert m05["scientific_outcome"] == "NO_EVIDENCE"
    assert m05["classification"] == "MARKET_05_NO_EVIDENCE"
    assert m05["scientifically_spent"] is True
    assert m05["rerun_authorized"] is False
    assert ident["result_head"] == RESULT_HEAD
    assert ident["result_tree"] == RESULT_TREE
    assert ident["run_identity"] == RUN_IDENTITY
    assert ident["result_json_sha256"] == RESULT_JSON_SHA256
    assert ident["result_md_sha256"] == RESULT_MD_SHA256
    assert _sha256(RESULT_JSON) == RESULT_JSON_SHA256
    assert _sha256(RESULT_MD) == RESULT_MD_SHA256
    hq = m05["headline_quantities"]
    assert hq["eligible_rows"] == 1825
    assert hq["BETA_ETH_CONFIRMATION"] == pytest.approx(-0.0002567502511611957)
    assert hq["BETA_ETH_CONFIRMATION_CI"] == [
        -0.0023464584123732146,
        0.0015931596784811688,
    ]
    assert hq["POOLED_MAE_BASELINE"] == pytest.approx(0.01474832634118777)
    assert hq["POOLED_MAE_CANDIDATE"] == pytest.approx(0.014768642312125536)
    assert hq["RELATIVE_MAE_IMPROVEMENT"] == pytest.approx(-0.0013775102657600513)
    assert hq["RELATIVE_MAE_IMPROVEMENT_CI"] == [
        -0.00249762914797686,
        -0.000375839559399871,
    ]
    assert hq["YEAR_2022"] == pytest.approx(0.000026398780684000478)
    assert hq["YEAR_2023"] == pytest.approx(-0.004303506211586372)
    assert hq["YEAR_2024"] == pytest.approx(-0.00045725937785223714)
    assert hq["G1"] == "PASS"
    assert hq["G2"] == "FAIL"
    assert hq["G3"] == "FAIL"
    assert hq["G4"] == "FAIL"
    assert hq["G5"] == "FAIL"
    assert hq["G6"] == "FAIL"
    assert "RESULT_HEAD = 828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b" in md
    assert "classification = MARKET_05_NO_EVIDENCE" in md
    cr = interp["canonical_result"]
    assert cr["result_head"] == RESULT_HEAD
    assert cr["run_identity"] == RUN_IDENTITY
    assert cr["classification"] == "MARKET_05_NO_EVIDENCE"
    assert interp["interpretation"]["negative_relative_mae_authorizes_reverse_hypothesis"] is False
    forbidden = "\n".join(m05["forbidden_reinterpretations"])
    interp_md = INTERP_MD.read_text(encoding="utf-8")
    for phrase in (
        "cross-asset context is useless",
        "ETH contains no predictive information",
        "divergence is validated",
        "reverse sign is validated",
        "ETH worsens BTC forecasting generally",
    ):
        assert phrase in forbidden
        assert phrase in interp_md


def test_program_counts_and_oos_untouched():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    interp = _load_interp()
    facts = new["program_facts"]
    assert facts["internal_historical_candidates_promoted"] == 0
    assert facts["internal_validated_candidates"] == 0
    assert facts["validated_oos_candidates"] == 0
    assert facts["protected_oos_edge_confirmations"] == 0
    assert facts["signalbot_protected_oos_touched"] is False
    assert facts["new_outcome_accessed"] is False
    assert facts["scientific_outcomes_inspected_during_update"] is False
    assert new["protected_oos_touched"] is False
    assert new["oos_distinctions"]["signalbot_protected_oos_touched"] is False
    assert new["scientific_outcomes_inspected_during_update"] is False
    assert "internal_historical_candidates_promoted = 0" in md
    assert "validated_oos_candidates = 0" in md
    assert interp["program_state_after_m05"]["internal_historical_candidates_promoted"] == 0
    assert interp["program_state_after_m05"]["validated_oos_candidates"] == 0
    assert interp["scientific_outcomes_inspected_during_update"] is False
    for rel in (
        "docs/research_data/CORE_BTC_BINANCE_V0/data/2025-01.parquet",
        "docs/research_data/CORE_BTC_BINANCE_V0/data/2026-01.parquet",
    ):
        assert not (REPO / rel).is_file()


def test_same_information_set_paused_and_next_phase():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    interp = _load_interp()
    facts = new["program_facts"]
    assert facts["same_information_set_hypothesis_generation_paused"] is True
    assert facts["next_program_phase"] == "INFORMATION_SET_EXPANSION"
    assert facts["next_information_family"] == (
        "POINT_IN_TIME_FUNDING_PREMIUM_OBSERVABILITY"
    )
    assert new["next_unit"] == "FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION"
    assert new["families_ranked"] is False
    assert new["next_family_selected"] is False
    assert new["registry_authorizes_next_experiment"] is False
    assert "SAME_INFORMATION_SET_HYPOTHESIS_GENERATION_PAUSED = true" in md
    assert "NEXT_PROGRAM_PHASE = INFORMATION_SET_EXPANSION" in md
    assert interp["program_decision"]["do_not_create_market_06_from_same_information_set"] is True
    assert interp["is_new_scientific_experiment"] is False


def test_forward_observability_design_only():
    obs = _load_obs()
    md = OBS_MD.read_text(encoding="utf-8")
    assert OBS_MD.is_file()
    assert obs["status"] == "DESIGN_ONLY_NOT_IMPLEMENTED"
    assert obs["implementation_authorized"] is False
    assert obs["scientific_test_authorized"] is False
    assert obs["market_hypothesis_frozen"] is False
    assert obs["market_06_created"] is False
    assert obs["legal_available_at_rule"] == "local_received_at_utc"
    assert obs["legal_available_at_is_not"] == "exchange_event_time"
    assert obs["parsed_record_may_replace_raw_immutable_evidence"] is False
    assert obs["computes_scientific_outcomes"] is False
    for field in (
        "local_received_at_utc",
        "exchange_event_time_if_present",
        "instrument",
        "stream_or_source",
        "raw_exact_message_bytes",
        "sha256_raw_bytes",
        "collector_version_git_identity",
        "connection_session_identity",
        "sequence_or_order_information_where_available",
    ):
        assert field in obs["raw_record_required_fields"]
    assert "legal_available_at = local_received_at_utc" in md
    assert "IMPLEMENTATION_AUTHORIZED = false" in md
    assert "future MAE" in md
    collector_scripts = list((REPO / "scripts/research").glob("*forward_market_observability*"))
    assert collector_scripts == []


def test_markdown_json_semantic_consistency_for_new_units():
    new = _load_new()
    md = NEW_MD.read_text(encoding="utf-8")
    for uid in EXPECTED_UNITS:
        unit = new["units"][uid]
        assert f"id = {uid}" in md
        assert f"evidence_class = {unit['evidence_class']}" in md
        so = unit["scientific_outcome"]
        assert f"scientific_outcome = {so if so is not None else 'None'}" in md
        assert f"canonical_status = {unit['canonical_status']}" in md
        assert f"mechanism_family = {unit['mechanism_family']}" in md
        assert unit["original_claim"] in md
    assert str(new["units"]["MARKET-05"]["headline_quantities"]["BETA_ETH_CONFIRMATION"]) in md
    assert str(new["units"]["MARKET-01"]["headline_quantities"]["beta_candidate"]) in md
    assert str(new["units"]["MARKET-03"]["headline_quantities"]["mdd_baseline"]) in md
