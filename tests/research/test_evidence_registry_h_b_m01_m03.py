"""Evidence-registry freeze checks for H + B + MARKET-01..03.

Documentation / evidence-synthesis only. Does not open protected OOS data,
rerun experiments, or select MARKET-04.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.md"
JSON_PATH = REPO / "docs/research/EVIDENCE_REGISTRY_H_B_M01_M03.json"

EXPECTED_UNITS = [
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

LINEAGE_EDGES = [
    ("H01", "B2-01"),
    ("H02", "B2-02"),
    ("H03", "B2-03"),
    ("H04", "B2-04"),
    ("H05", "B2-05"),
    ("MARKET-01", "MARKET-02"),
]

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

REGISTRY_CLASSES = {
    "DISCOVERY",
    "CONTROLLED_DEVELOPMENT",
    "CANONICAL_HISTORICAL_TEST",
    "EXTERNAL_REPRODUCTION",
    "VALIDATED_OOS",
    "NO_EVIDENCE_UNIT",
    "INTEGRITY_LIMITED",
}


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_show(commit: str, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "cat-file", "blob", f"{commit}:{path}"],
        cwd=REPO,
    )


def test_exact_fourteen_unit_scope_and_no_market_04():
    payload = _load()
    md = _md()
    assert payload["scope"]["unit_ids"] == EXPECTED_UNITS
    assert list(payload["units"].keys()) == EXPECTED_UNITS
    assert payload["scope"]["unit_count"] == 14
    assert payload["scope"]["h_unit_count"] == 5
    assert payload["scope"]["b_unit_count"] == 6
    assert payload["scope"]["market_unit_count"] == 3
    assert payload["scope"]["market_04_included"] is False
    assert "MARKET-04" not in payload["units"]
    assert "MARKET-04" not in payload["scope"]["unit_ids"]
    assert payload["market_04_selected"] is False
    assert payload["new_hypothesis_created"] is False
    assert "MARKET_04_SELECTED = NO" in md
    assert "MARKET_04_SELECTED = YES" not in md
    assert payload["new_hypothesis_created"] is False
    assert "recommend MARKET-04" not in md
    assert "selected MARKET-04" not in md.lower()
    assert "next family is selected" in md.lower() or "next_family_selected = false" in md


def test_required_fields_and_registry_classes_are_metadata_only():
    payload = _load()
    assert payload["evidence_classes_are_registry_metadata_only"] is True
    assert payload["evidence_classes_do_not_replace_canonical_project_verdicts"] is True
    for uid, unit in payload["units"].items():
        for field in REQUIRED_UNIT_FIELDS:
            assert field in unit, f"{uid} missing {field}"
        assert unit["id"] == uid
        assert unit["evidence_class"] in REGISTRY_CLASSES
        assert unit["evidence_class"] != unit["canonical_status"] or uid in {
            "MARKET-01",
            "MARKET-02",
            "MARKET-03",
        }


def test_all_lineage_edges_encoded():
    payload = _load()
    md = _md()
    edges = {(e["parent"], e["child"]) for e in payload["lineage_edges"]}
    for parent, child in LINEAGE_EDGES:
        assert (parent, child) in edges
        assert f"{parent} -> {child}" in md
        child_unit = payload["units"][child]
        assert parent in child_unit["lineage"]["parents"] or child == "MARKET-03"
        if child != "MARKET-03":
            assert child_unit["lineage"]["parent_child_independence"] is False
        parent_unit = payload["units"][parent] if parent in payload["units"] else None
        if parent_unit is not None:
            assert child in parent_unit["lineage"]["children"]
    m03_edges = [e for e in payload["lineage_edges"] if e["child"] == "MARKET-03"]
    assert m03_edges
    assert m03_edges[0]["kind"] == "EXTERNAL_SOURCE_LINEAGE"


def test_h_promoted_count_is_zero_and_residuals_not_confirmatory():
    payload = _load()
    md = _md()
    assert payload["program_facts"]["h_generation_promoted"] == 0
    assert payload["program_facts"]["h_generation_total"] == 5
    assert "h_generation_promoted = 0" in md
    for uid in ("H01", "H02", "H03", "H04", "H05"):
        unit = payload["units"][uid]
        assert unit["scientific_outcome"] == "REJECTED"
        assert unit["positive_evidence"] == []
        for residual in unit["posthoc_residuals"]:
            assert residual["confirmatory"] is False
            assert residual["status"] == "POSTHOC_UNTESTED"
            assert residual["may_not_rescue_parent"] is True
    assert "posthoc_residuals_are_confirmatory = false" in md
    assert "Reverse volatility persistence" in md
    assert "hypothesis-generation material, not positive H01 confirmation" in json.dumps(
        payload["units"]["H01"]
    )


def test_b2_05_not_silently_promoted_or_closed_without_authority():
    payload = _load()
    md = _md()
    unit = payload["units"]["B2-05"]
    assert unit["evidence_class"] == "INTEGRITY_LIMITED"
    assert unit["canonical_status"] == "DEVELOPMENT_CONSUMED"
    assert unit["scientific_outcome"] == "ORDINARY_RESULT_UNAVAILABLE"
    assert unit["inferred_closed_no_promotion"] is False
    assert unit["inferred_promoted_candidate"] is False
    assert unit["ordinary_result_md_present"] is False
    assert unit["recovery_status"] == "B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED"
    dumped = json.dumps(unit)
    assert "B2_05_CLOSED_NO_PROMOTION" not in dumped
    assert "B2_05_PROMOTED_CANDIDATE" not in dumped
    assert "B2_05_CLOSED_NO_PROMOTION" not in md
    assert "B2_05_PROMOTED_CANDIDATE" not in md
    assert not (REPO / "docs/research/B2_05_FLOW_ABSORPTION_RESULT.md").exists()


def test_b2_06_has_no_scientific_outcome():
    payload = _load()
    md = _md()
    unit = payload["units"]["B2-06"]
    assert unit["evidence_class"] == "NO_EVIDENCE_UNIT"
    assert unit["scientific_outcome"] is None
    assert unit["scientific_outcome_opened"] is False
    assert unit["absence_of_execution_is_negative_evidence"] is False
    assert unit["canonical_status"] == "BLOCKED_MISSING_OBSERVABLE"
    assert "scientific_outcome = None" in md
    assert "absence_of_execution_is_negative_evidence = false" in md


def test_b2_01_through_04_closed_no_promotion_and_b2_01_not_near_pass():
    payload = _load()
    for uid, verdict in (
        ("B2-01", "B2_01_CLOSED_NO_PROMOTION"),
        ("B2-02", "B2_02_CLOSED_NO_PROMOTION"),
        ("B2-03", "B2_03_CLOSED_NO_PROMOTION"),
        ("B2-04", "B2_04_CLOSED_NO_PROMOTION"),
    ):
        unit = payload["units"][uid]
        assert unit["canonical_status"] == "CLOSED_NO_PROMOTION"
        assert unit["scientific_outcome"] == verdict
        assert unit["evidence_class"] == "CONTROLLED_DEVELOPMENT"
    assert payload["units"]["B2-01"]["near_pass_candidate"] is False
    assert payload["units"]["B2-04"]["h04_child_path"] == "CLOSED"
    assert payload["program_facts"]["b2_clean_promoted"] == 0
    assert payload["program_facts"]["b2_misleading_denominator_avoided"] is True


def test_market_01_and_02_no_evidence_and_adaptive_dependence():
    payload = _load()
    md = _md()
    m01 = payload["units"]["MARKET-01"]
    m02 = payload["units"]["MARKET-02"]
    assert m01["evidence_class"] == "CANONICAL_HISTORICAL_TEST"
    assert m02["evidence_class"] == "CANONICAL_HISTORICAL_TEST"
    assert m01["scientific_outcome"] == "NO_EVIDENCE"
    assert m02["scientific_outcome"] == "NO_EVIDENCE"
    assert payload["program_facts"]["market_01_classification"] == "NO_EVIDENCE"
    assert payload["program_facts"]["market_02_classification"] == "NO_EVIDENCE"
    assert abs(m01["headline_quantities"]["beta_candidate"] + 0.000163244) < 1e-12
    assert m01["headline_quantities"]["p_one_sided"] == 0.757
    assert m01["headline_quantities"]["market_01_test_calibrated"] is False
    assert abs(m02["headline_quantities"]["beta_confirmation"] + 0.000183788) < 1e-9
    assert abs(m02["headline_quantities"]["bootstrap_se"] - 0.000400695) < 1e-9
    assert m02["headline_quantities"]["p_one_sided"] == 0.647
    assert m02["lineage"]["dependence_type"] == "ADAPTIVE_RESEARCH_LINEAGE"
    assert m02["lineage"]["designed_after_parent_outcome_known"] is True
    assert m02["lineage"]["parent_child_independence"] is False
    assert payload["m01_m02_independent_replications"] is False
    assert "M01_M02_INDEPENDENT_REPLICATIONS = NO" in md
    assert m02["merge_status"]["on_origin_main"] is False
    assert m02["merge_status"]["on_this_tree"] is False
    assert m02["merge_status"]["open_research_pr"] == 157
    assert m01["merge_status"]["on_origin_main"] is True


def test_market_03_external_reproduction_not_validated_oos():
    payload = _load()
    md = _md()
    m03 = payload["units"]["MARKET-03"]
    assert m03["evidence_class"] == "EXTERNAL_REPRODUCTION"
    assert m03["scientific_outcome"] == "REPRODUCED_DIRECTION"
    assert m03["validated_oos"] is False
    assert m03["validated_candidate"] is False
    assert m03["proof_of_current_alpha"] is False
    assert m03["proof_of_causal_funding_effect"] is False
    assert m03["protected_oos_confirmation"] is False
    assert m03["replication_level"] == "LEVEL_2_FAITHFUL_REIMPLEMENTATION"
    assert m03["exact_differential_tests"] == "PARTIAL"
    assert m03["strict_funding_publication_latency"] == "UNPROVEN"
    assert m03["lineage"]["dependence_type"] == "EXTERNAL_SOURCE_LINEAGE"
    assert payload["program_facts"]["market_03_classification"] == "REPRODUCED_DIRECTION"
    assert m03["evidence_class"] != "VALIDATED_OOS"
    assert "validated_oos = false" in md
    assert "strict_funding_publication_latency = UNPROVEN" in md
    assert m03["merge_status"]["on_origin_main"] is False
    assert m03["merge_status"]["open_research_pr"] == 162
    assert m03["headline_quantities"]["mdd_filtered"] > m03["headline_quantities"]["mdd_baseline"]


def test_protected_oos_untouched_and_external_author_oos_distinction():
    payload = _load()
    md = _md()
    oos = payload["oos_distinctions"]
    assert oos["SIGNALBOT_PROTECTED_OOS_UNTOUCHED"] is True
    assert oos["signalbot_protected_oos_touched"] is False
    assert oos["EXTERNAL_HYPOTHESIS_SELECTION_OOS_STATUS"] == "NOT_GUARANTEED_UNTOUCHED"
    assert oos["EXTERNAL_M03_SELECTION_OOS_UNTOUCHED_GUARANTEED"] is False
    assert payload["program_facts"]["signalbot_protected_oos_touched"] is False
    assert payload["program_facts"]["protected_oos_edge_confirmations"] == 0
    assert payload["program_facts"]["internal_validated_candidates"] == 0
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md
    assert "EXTERNAL_HYPOTHESIS_SELECTION_OOS_STATUS = NOT_GUARANTEED_UNTOUCHED" in md
    assert "EXTERNAL_M03_SELECTION_OOS_UNTOUCHED_GUARANTEED = NO" in md
    for unit in payload["units"].values():
        assert unit["protected_oos_touched"] is False


def test_experiment_count_is_not_independent_replication_count():
    payload = _load()
    md = _md()
    assert payload["independent_replication_count_is_not_equal_to_experiment_count"] is True
    assert payload["experiment_count_equals_independent_evidence_count"] is False
    assert "EXPERIMENT_COUNT_EQUALS_INDEPENDENT_EVIDENCE_COUNT = NO" in md
    assert "prevent naive iid counting" in payload["independence_program_note"]
    assert "sequential idea generation" in md
    assert "post-result child design" in md


def test_no_next_hypothesis_or_family_ranking():
    payload = _load()
    md = _md()
    assert payload["families_ranked"] is False
    assert payload["next_family_selected"] is False
    assert payload["registry_authorizes_next_experiment"] is False
    assert payload["anti_rescue_contract"]["registry_authorizes_that_experiment"] is False
    assert payload["anti_rescue_contract"]["posthoc_residuals_are_confirmatory"] is False
    assert "families_ranked = false" in md
    assert "next_family_selected = false" in md
    assert "MARKET-04" not in "".join(payload["mechanism_families"].keys())
    for fam in payload["mechanism_families"].values():
        assert fam["clean_positive_units"] == []


def test_source_hashes_and_identities_match():
    payload = _load()
    assert payload["pre_registry_head"] == "9c360a19a8e35ba0e7638fd125a0e6ae32f15846"
    assert payload["pre_registry_tree"] == "16e8d125fc453202a4b5ce9c5c11f2cb5ff7b966"
    for binding in payload["source_bindings"]:
        path = binding["path"]
        sha = binding["sha256"]
        blob = binding["git_blob_sha"]
        location = binding["location"]
        commit = binding["bound_commit"]
        if location == "unmerged_pr_157":
            data = _git_show(commit, path)
            assert _sha256_bytes(data) == sha
            actual_blob = subprocess.check_output(
                ["git", "rev-parse", f"{commit}:{path}"],
                cwd=REPO,
                text=True,
            ).strip()
            assert actual_blob == blob
            assert not (REPO / path).exists()
            continue
        if location == "pre_registry_head_governance":
            data = _git_show(payload["pre_registry_head"], path)
            assert _sha256_bytes(data) == sha
            continue
        local = REPO / path
        assert local.is_file(), path
        assert _sha256_bytes(local.read_bytes()) == sha
        actual_blob = subprocess.check_output(
            ["git", "hash-object", str(local)],
            cwd=REPO,
            text=True,
        ).strip()
        assert actual_blob == blob


def test_markdown_json_semantic_consistency():
    payload = _load()
    md = _md()
    for uid in EXPECTED_UNITS:
        unit = payload["units"][uid]
        assert f"id = {uid}" in md
        assert f"evidence_class = {unit['evidence_class']}" in md
        so = unit["scientific_outcome"]
        assert f"scientific_outcome = {so if so is not None else 'None'}" in md
        assert f"canonical_status = {unit['canonical_status']}" in md
        assert f"mechanism_family = {unit['mechanism_family']}" in md
        assert unit["original_claim"] in md
    assert "internal_validated_candidates = 0" in md
    assert "protected_oos_edge_confirmations = 0" in md
    assert payload["units"]["MARKET-03"]["headline_quantities"]["mdd_baseline"] == pytest.approx(
        -0.4935539254862912
    )
    assert str(payload["units"]["MARKET-03"]["headline_quantities"]["mdd_baseline"]) in md
    assert str(payload["units"]["MARKET-01"]["headline_quantities"]["beta_candidate"]) in md
    assert str(payload["units"]["MARKET-02"]["headline_quantities"]["beta_confirmation"]) in md


def test_does_not_open_protected_oos_data():
    """Registry tests must not open protected 2025/2026 CORE partitions."""
    payload = _load()
    assert payload["new_outcome_accessed"] is False
    assert payload["oos_distinctions"]["signalbot_protected_oos_touched"] is False
    assert "NEW_OUTCOME_ACCESSED = NO" in _md()
    # Existence check only. Do not read parquet bytes.
    for rel in (
        "docs/research_data/CORE_BTC_BINANCE_V0/data/2025-01.parquet",
        "docs/research_data/CORE_BTC_BINANCE_V0/data/2026-01.parquet",
    ):
        assert not (REPO / rel).is_file()
