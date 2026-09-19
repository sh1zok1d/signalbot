"""MARKET-04 outcome-blind funding-availability audit checks.

Data-semantics / temporal-authority unit only. Does not open protected
OOS, inspect MARKET-04 outcomes, or authorize execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MD = REPO / "docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.md"
JSON_PATH = REPO / "docs/research/MARKET_04_FUNDING_AVAILABILITY_AUDIT.json"
VISION_README = (
    REPO
    / "docs/research_data/MARKET_04_FUNDING_AVAILABILITY_AUDIT/BINANCE_PUBLIC_DATA_README.md"
)
EXCERPT = (
    REPO
    / "docs/research_data/MARKET_04_FUNDING_AVAILABILITY_AUDIT/WAYBACK_20220315_UM_FUTURES_FUNDING_EXCERPT.md"
)
CANDIDATE = "MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK"
PREVIOUS_HEAD = "33ef39988f03bf634ff61c014671b35ba9b0f6ee"
PREVIOUS_TREE = "04ae63d2d3412a3988dea20cc17d3e177fe31205"
VISION_README_SHA256 = (
    "085ab91377aa9325d44f4c7ad27cce4ab381e158403e1d7df2bad39d1a66f7c6"
)
EXCERPT_SHA256 = "af99eec4795efdefe814b9882ae046a158f51bedd0b8984ebd62a135490fc349"

FORBIDDEN_ARTIFACT_GLOBS = (
    "docs/research/MARKET_04_*RESULT*",
    "docs/research/MARKET_04_*ARM*",
    "docs/research/MARKET_04_*RESERVATION*",
    "docs/research/MARKET_04_*PREREG*",
    "docs/research/MARKET_04_*IMPLEMENTATION*",
    "scripts/research/market_04*",
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

STRENGTHS = {
    "DIRECT_FIRST_PARTY_AUTHORITY",
    "FIRST_PARTY_INFERENCE",
    "SECONDARY_ONLY",
    "UNPROVEN",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> dict:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def _md() -> str:
    return MD.read_text(encoding="utf-8")


def test_audit_outcome_unresolved_and_identity():
    payload = _load()
    md = _md()
    assert payload["audit_id"] == "MARKET_04_FUNDING_AVAILABILITY_AUDIT"
    assert payload["market_04_id"] == CANDIDATE
    assert payload["audit_outcome"] == "FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED"
    assert payload["candidate_role"] == "RISK_STATE_FILTER"
    assert payload["primary_outcome_family"] == "FUTURE_ADVERSE_PATH_RISK"
    assert payload["bound_candidate"]["previous_head"] == PREVIOUS_HEAD
    assert payload["bound_candidate"]["previous_tree"] == PREVIOUS_TREE
    assert "audit_outcome = FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED" in md
    assert "MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK" in md


def test_no_protected_oos_or_scientific_outcomes():
    payload = _load()
    md = _md()
    assert payload["protected_oos_touched"] is False
    assert payload["scientific_outcomes_inspected"] is False
    assert payload["outcome_blind"] is True
    assert "protected_oos_touched = false" in md
    assert "scientific_outcomes_inspected = false" in md
    dumped = json.dumps(payload) + md
    for needle in (
        "MAE_mean",
        "market_04_beta",
        "MDD_filtered",
        "beta_confirmation",
        "-0.337755",
        "-0.493553",
        "-0.000163",
        "-0.000183",
    ):
        assert needle not in dumped
    assert "inspect future returns" in md
    assert "No funding/return correlation" in md or "no funding/return correlation" in md.lower()


def test_no_mae_threshold_or_horizon_search():
    payload = _load()
    md = _md()
    forbidden = payload["this_unit_does_not"]
    assert "inspect future MAE" in forbidden
    assert "search funding thresholds" in forbidden
    assert "search horizons" in forbidden
    assert "calculate correlations between funding and price outcomes" in forbidden
    assert "inspect future MAE" in md
    assert "search funding thresholds" in md
    assert "search horizons" in md


def test_no_result_arm_evaluator_or_prereg():
    payload = _load()
    assert payload["full_preregistration_frozen"] is False
    assert payload["implementation_frozen"] is False
    assert payload["armed"] is False
    assert payload["execution_authorized"] is False
    matches = []
    for pattern in FORBIDDEN_ARTIFACT_GLOBS:
        matches.extend(REPO.glob(pattern))
    assert matches == []
    assert "ARM MARKET-04" in payload["this_unit_does_not"]
    assert "implement the MARKET-04 scientific evaluator" in payload["this_unit_does_not"]
    assert "create MARKET-04 RESULT" in payload["this_unit_does_not"]


def test_market_03_assumption_is_not_authority():
    payload = _load()
    md = _md()
    assert payload["market_03_fundingtime_assumption_is_authority"] is False
    assert payload["market_03_assumption_kind"] == "LEVEL_2_FAITHFUL_REIMPLEMENTATION_ONLY"
    claim = next(
        item
        for item in payload["temporal_claims"]
        if item["claim_id"] == "MARKET_03_FUNDINGTIME_ASSUMPTION"
    )
    assert claim["evidence_strength"] == "UNPROVEN"
    assert claim["proves_legal_available_at"] is False
    assert "MARKET-03 LEVEL_2 fundingTime assumption" in payload["rejected_non_authority"]
    assert "market_03_fundingtime_assumption_is_authority = false" in md
    assert "not scientific authority" in md.lower() or "is **not**" in md


def test_event_time_is_not_publication_time_unless_proven():
    payload = _load()
    md = _md()
    assert payload["event_time_equals_publication_time"] is False
    assert payload["calc_time_equals_publication_time"] is False
    assert payload["funding_time_equals_publication_time"] is False
    assert payload["publication_time_semantics"] == "UNSPECIFIED"
    assert payload["clock_distinction"]["PUBLICATION_TIME"] == "UNSPECIFIED"
    assert payload["clock_distinction"]["LEGAL_AVAILABLE_AT"] is None
    assert "event_time_equals_publication_time = false" in md
    assert "publication_time_semantics = UNSPECIFIED" in md
    pub_claim = next(
        item
        for item in payload["temporal_claims"]
        if item["claim_id"] == "FUNDINGTIME_IS_PUBLICATION_TIME"
    )
    assert pub_claim["evidence_strength"] == "UNPROVEN"


def test_every_temporal_claim_has_evidence_strength():
    payload = _load()
    claims = payload["temporal_claims"]
    assert len(claims) >= 8
    seen = set()
    for claim in claims:
        assert claim["claim_id"]
        assert claim["claim"]
        assert claim["evidence_strength"] in STRENGTHS
        assert claim["proves_legal_available_at"] is False
        seen.add(claim["claim_id"])
    assert "FUNDINGTIME_IS_PUBLICATION_TIME" in seen
    assert "CALC_TIME_IS_PUBLICATION_TIME" in seen
    assert "SETTLED_RATE_KNOWN_AT_FUNDINGTIME" in seen
    assert "PUBLICATION_LATENCY_DOCUMENTED" in seen
    inference = next(
        item
        for item in claims
        if item["claim_id"] == "FUNDINGTIME_IS_EVENT_OR_SETTLEMENT_TIME"
    )
    assert inference["evidence_strength"] == "FIRST_PARTY_INFERENCE"


def test_legal_available_at_unset_and_execution_unauthorized():
    payload = _load()
    md = _md()
    assert payload["legal_available_at_rule"] is None
    assert payload["legal_available_at_authority"] is None
    assert payload["historical_availability_proven"] is False
    assert payload["market_04_funding_observable_usable"] is False
    assert payload["execution_authorized"] is False
    assert payload["invented_publication_latency"] is False
    assert payload["prior_settlement_later_boundary_proven"] is False
    assert "legal_available_at_rule = null" in md
    assert "legal_available_at_authority = null" in md
    assert "historical_availability_proven = false" in md
    assert "execution_authorized = false" in md
    assert "market_04_funding_observable_usable = false" in md


def test_outcome_matches_machine_readable_evidence():
    payload = _load()
    md = _md()
    assert payload["answers"]["C_known_at_fundingTime"] is False
    assert payload["answers"]["D_publication_documented_as"] == "UNSPECIFIED"
    assert payload["answers"]["F_reconstruct_without_post_T_final_value"] is False
    assert payload["answers"]["G_official_field_supports_legal_available_at"] is False
    assert payload["answers"]["H_other_first_party_funding_state_with_explicit_historical_availability"] is False
    assert payload["b2_06_implication"] == "UNCHANGED"
    assert payload["B2_06_FUNDING_BLOCKER_IMPLICATION"] == "UNCHANGED"
    assert payload["MARKET_04_NEXT_STEP"] == (
        "BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION"
    )
    assert payload["if_availability_cannot_be_established"] == "BLOCKED_OBSERVABLE"
    assert "B2_06_FUNDING_BLOCKER_IMPLICATION = UNCHANGED" in md
    assert (
        "MARKET_04_NEXT_STEP = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION"
        in md
    )
    for item in payload["alternative_observable_candidates"]:
        assert item["usable_for_market_04_legal_available_at"] is False


def test_primary_source_records_are_complete():
    payload = _load()
    sources = payload["primary_sources"]
    assert len(sources) >= 4
    for source in sources:
        for field in REQUIRED_SOURCE_FIELDS:
            assert source.get(field), field
        assert source["evidence_strength"] in STRENGTHS
        assert source["accessed_at"] == "2026-09-19"
    urls = {source["url"] for source in sources}
    assert any("binance-docs.github.io/apidocs/futures/en" in url for url in urls)
    assert any("binance-public-data" in url for url in urls)
    assert _sha256(VISION_README) == VISION_README_SHA256
    assert _sha256(EXCERPT) == EXCERPT_SHA256
    assert payload["bound_evidence"]["vision_readme_sha256"] == VISION_README_SHA256
    assert payload["bound_evidence"]["wayback_excerpt_sha256"] == EXCERPT_SHA256


def test_markdown_json_semantic_consistency():
    payload = _load()
    md = _md()
    assert payload["audit_outcome"] in md
    assert payload["settled_funding_source"] in md
    assert payload["settled_funding_field"] in md
    assert payload["event_time_semantics"] in md
    assert payload["publication_time_semantics"] in md
    assert "Get Funding Rate History" in md
    assert "This is the lasted funding rate" in md
    assert "FIRST_PARTY_INFERENCE" in md
    assert "DIRECT_FIRST_PARTY_AUTHORITY" in md
    assert "UNPROVEN" in md
    assert "ALTERNATIVE_OBSERVABLE_CANDIDATE" in md or "Alternative observable" in md
    for flag in (
        "current_api_semantics_known = true",
        "full_preregistration_frozen = false",
        "implementation_frozen = false",
        "armed = false",
    ):
        assert flag in md
    assert "B2-06 and MARKET-03 artifacts are not rewritten" in md
