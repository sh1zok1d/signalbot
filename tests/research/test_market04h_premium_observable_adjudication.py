"""MARKET-04H Premium Index observable adjudication checks.

Outcome-blind child-design freeze only. Does not open protected OOS,
inspect scientific outcomes, or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.md"
JSON_PATH = REPO / "docs/research/MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json"
PARENT_MD = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.md"
PARENT_JSON = REPO / "docs/research/MARKET_04_CANDIDATE_SELECTION.json"
AUDIT_MD = REPO / "docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.md"
AUDIT_JSON = REPO / "docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.json"

PARENT_ID = "MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK"
CHILD_ID = "MARKET-04H_PREMIUM_INDEX_ADVERSE_PATH_RISK"
PARENT_MD_SHA256 = "bab848737137e9a9eebd6ef6565c5b74134d94310ebe20496621aba92a20a936"
PARENT_JSON_SHA256 = "e1c4270d89d891846fefbe3d14a6389c9d6ed747cb00f8bfc9906300f18d30a6"
AUDIT_MD_SHA256 = "2a5a7c6e1e712d04b0ec7c78e33fce7b3f0eb3a0008b793fbbc974d18f67b021"
AUDIT_JSON_SHA256 = "b1f4e02c55c6a6b32edfc5efec278446b2ac04a375197523faee8629bd389c0d"

FORBIDDEN_ARTIFACT_GLOBS = (
    "docs/research/MARKET_04H_*RESULT*",
    "docs/research/MARKET_04H_*ARM*",
    "docs/research/MARKET_04H_*PREREG*",
    "scripts/research/market_04h*",
)

REQUIRED_SOURCE_FIELDS = (
    "publisher",
    "document_title",
    "url",
    "document_version_date",
    "accessed_at",
    "relevant_section",
    "what_it_proves",
    "what_it_does_not_prove",
    "evidence_strength",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_parent_market04_artifacts_were_not_rewritten():
    payload = _load()
    assert _sha256(PARENT_MD) == PARENT_MD_SHA256
    assert _sha256(PARENT_JSON) == PARENT_JSON_SHA256
    assert _sha256(AUDIT_MD) == AUDIT_MD_SHA256
    assert _sha256(AUDIT_JSON) == AUDIT_JSON_SHA256
    parent = json.loads(PARENT_JSON.read_text(encoding="utf-8"))
    assert parent["research_id"] == PARENT_ID
    assert parent["candidate"] == PARENT_ID
    assert payload["parent_not_rewritten"] is True
    bound = payload["bound_parent"]
    assert bound["parent_md_sha256"] == PARENT_MD_SHA256
    assert bound["audit_md_sha256"] == AUDIT_MD_SHA256


def test_child_identity_and_lineage():
    payload = _load()
    md = _md()
    assert payload["parent_research_id"] == PARENT_ID
    assert payload["research_id"] == CHILD_ID
    assert payload["lineage_kind"] == (
        "OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE"
    )
    assert payload["scientific_outcome_seen_before_substitution"] is False
    assert payload["independent_confirmation_of_parent"] is False
    assert payload["market_03_independent_replication"] is False
    assert "market_03_independent_replication = false" in md
    assert "independent_confirmation_of_parent = false" in md
    assert "not an independent replication" in md


def test_settled_funding_is_not_claimed():
    payload = _load()
    md = _md()
    assert payload["settled_funding_claimed"] is False
    assert payload["observable_semantic_role"] == "FUNDING_PRESSURE_PROXY"
    for label in payload["forbidden_semantic_labels"]:
        assert payload["observable_semantic_role"] != label
    assert "settled_funding_claimed = false" in md
    assert "observable_semantic_role = FUNDING_PRESSURE_PROXY" in md
    assert "FINAL_SETTLED_FUNDING" in md


def test_fundingtime_and_close_time_are_not_publication():
    payload = _load()
    md = _md()
    assert payload["funding_time_equals_publication_time"] is False
    assert payload["close_time_equals_publication_time"] is False
    assert payload["close_time_equals_legal_available_at"] is False
    assert "close_time_equals_publication_time = false" in md
    assert "do_not_treat_fundingTime_as_publication_time = true" in md
    assert "do_not_treat_close_time_as_publication_time = true" in md


def test_safe_usable_at_not_adopted_without_timezone_authority():
    payload = _load()
    md = _md()
    assert payload["archive_day_timezone"] == "UNRESOLVED"
    assert payload["safe_usable_at_rule"] is None
    assert payload["safe_usable_at_authority"] is None
    assert payload["safe_usable_at_proven"] is False
    assert payload["authority_checklist"]["timezone_of_archive_day_D_established"] is False
    assert payload["authority_checklist"]["d_plus_2_ordering_adopted"] is False
    assert "archive_day_timezone = UNRESOLVED" in md
    assert "safe_usable_at_rule = null" in md
    assert "safe_usable_at_proven = false" in md
    assert "SAFE_USABLE_AT(D) = start of calendar day D+2" in md
    assert "not adopted" in md.lower() or "not adopted" in md


def test_revision_status_is_not_ignored():
    payload = _load()
    md = _md()
    assert payload["revision_ledger_claimed_exhaustive"] is True
    assert payload["relevant_files_revision_status"] == "REVISION_STATUS_UNRESOLVED"
    assert payload["revision_audit"]["current_download_treated_as_original"] is False
    assert payload["revision_audit"]["historically_available_version_recovered"] is False
    assert payload["revision_audit"]["relevant_files_in_documented_replacement"] is False
    assert payload["revision_audit"]["s3_last_modified_after_ledger_observed"] is True
    assert "relevant_files_revision_status = REVISION_STATUS_UNRESOLVED" in md
    assert "current_download_treated_as_original = false" in md


def test_threshold_55_is_not_design_authority():
    payload = _load()
    md = _md()
    assert payload["state_construction_boundary"]["threshold_55_inherited"] is False
    assert "funding threshold 55" in payload["m03_not_inherited"]
    assert "threshold 55" in md
    assert "does not inherit" in md


def test_no_future_outcomes_or_predictive_metrics():
    payload = _load()
    md = _md()
    dumped = json.dumps(payload) + md
    for needle in (
        "MAE_mean",
        "market_04_beta",
        "market_04h_beta",
        "MDD_filtered",
        "beta_confirmation",
        "-0.337755",
        "-0.493553",
        "-0.000163",
        "correlation_premium",
        "regression_coef",
    ):
        assert needle not in dumped
    forbidden = payload["this_unit_does_not"]
    assert "inspect future MAE" in forbidden
    assert "calculate correlations" in forbidden
    assert "inspect future returns" in md
    assert "calculate correlations" in md


def test_protected_oos_untouched_and_no_result_or_arm():
    payload = _load()
    md = _md()
    assert payload["protected_oos_touched"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["execution_authorized"] is False
    assert payload["armed"] is False
    assert payload["implementation_frozen"] is False
    assert payload["data_manifest_created"] is False
    assert not (REPO / "docs/research/MARKET_04H_PREMIUM_DATA_MANIFEST.json").exists()
    matches = []
    for pattern in FORBIDDEN_ARTIFACT_GLOBS:
        matches.extend(REPO.glob(pattern))
    assert matches == []
    assert "protected_oos_touched = false" in md
    assert "execution_authorized = false" in md
    assert "SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES" in md


def test_m03_is_not_independent_confirmation():
    payload = _load()
    md = _md()
    assert payload["market_03_independent_replication"] is False
    assert "would not be an independent replication of MARKET-03" in md
    assert payload["m01_m02_are_positive_support"] is False


def test_outcome_blocked_and_sources_complete():
    payload = _load()
    md = _md()
    assert payload["adjudication_outcome"] == "MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED"
    assert payload["historical_coverage_usable"] is False
    assert payload["same_support_required"] is True
    assert payload["primary_outcome_family"] == "FUTURE_CROWDING_SIDE_ADVERSE_PATH_RISK"
    assert payload["pnl_is_primary_outcome"] is False
    assert payload["next_unit"] == "BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION"
    assert "adjudication_outcome = MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED" in md
    assert "historical_coverage_usable = false" in md
    sources = payload["primary_sources"]
    assert len(sources) >= 5
    for source in sources:
        for field in REQUIRED_SOURCE_FIELDS:
            assert source.get(field), field
        assert source["evidence_strength"] == "DIRECT_FIRST_PARTY_AUTHORITY"
    assert payload["scientific_question_family"] in md
    assert "CORE_PRICE_STATE" not in md or "Premium Index" in md
    assert "NEXT_UNIT = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION" in md
