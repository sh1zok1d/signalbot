"""Contract tests for the post-Sprint04 maturity decision and Generator V0 design.

Reads JSON/Markdown only. No generator is built and no market data is opened.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DECISION = REPO / "docs/research/POST_SPRINT04_AUTOMATION_MATURITY_DECISION.json"
DESIGN = REPO / "docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json"
MEMORY = REPO / "docs/research/MECHANISM_MEMORY_V0.json"
AUTHORITY = REPO / "docs/research/GOVERNANCE_REGION_AUTHORITY_V0.json"
NEXT_UNIT = "HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS"
CURRENT_ROUTING_UNIT = "GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW"
FALSE_FLAGS = (
    "NEW_DATA_ACQUIRED",
    "SCIENTIFIC_OUTCOMES_COMPUTED",
    "SPRINT05_CREATED",
    "D14_CREATED",
    "PROTECTED_2025_OPENED",
    "PROTECTED_2026_OPENED",
    "MARKET_07_CREATED",
    "D7_RERUN_PERFORMED",
    "D8_EXECUTED",
    "D7_CONFIRMATION_EXECUTED",
    "D11_CONFIRMATION_EXECUTED",
    "D12_CONFIRMATION_EXECUTED",
    "GENERATOR_BUILT",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _blind_projection(memory: dict, blind: dict) -> dict:
    out = {}
    for key, entry in memory["ENTRIES"].items():
        row = {field: entry.get(field) for field in blind["WHITELISTED_FIELDS"]}
        for target, value in blind["SANITIZATION_OVERRIDES"].items():
            entry_id, field = target.split(".", 1)
            if entry_id == key:
                row[field] = value
        row.update(blind["PER_ENTRY_ADDED_FIELD"])
        out[key] = row
    return out


def test_artifacts_are_canonical_sorted_json():
    for path in (DECISION, DESIGN):
        raw = path.read_text(encoding="utf-8")
        assert raw == json.dumps(json.loads(raw), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def test_decision_is_a_with_boundary_flags():
    d = _load(DECISION)
    assert d["MATURITY_DECISION"] == "HYPOTHESIS_GENERATOR_V0_INFRA_READY"
    assert d["OPTION_B_EVALUATION"]["VERDICT"] == "REJECTED"
    assert d["INTERNAL_DISCOVERY_CARDS_EXECUTED"] == 10
    assert d["INTERNAL_PROMISING_PROTOTYPES"] == 4
    assert d["MECHANISM_DIVERSITY_ASSESSMENT"]["EFFECTIVE_DISTINCT_PROTOTYPE_CLASSES"] == 2
    assert d["AUTOMATIC_SPRINT05"] is False
    assert d["NEXT_UNIT"] == NEXT_UNIT
    for key in FALSE_FLAGS:
        assert d[key] is False, key
    assert set(d["MECHANISM_DIVERSITY_ASSESSMENT"]["EXECUTED_CARDS"]) == {
        "D2", "D3", "D4", "D5", "D7", "D9", "D10", "D11", "D12", "D13"
    }


def test_design_freezes_schema_roles_and_taxonomy():
    g = _load(DESIGN)
    for key in FALSE_FLAGS:
        assert g[key] is False, key
    assert g["BLIND_GENERATOR_CONTEXT_DEFINED"] is True
    assert g["FULL_GOVERNANCE_CONTEXT_DEFINED"] is True
    assert g["OUTCOME_LABELS_HIDDEN_FROM_GENERATOR"] is True
    assert g["MODE"] == "SHADOW_ONLY"
    required = g["CANDIDATE_SCHEMA"]["REQUIRED_FIELDS"]
    assert len(required) == len(set(required)) == 27
    assert "EXPECTED_PROBABILITY_OF_SUCCESS" not in required
    assert "EXPECTED_PROBABILITY_OF_SUCCESS" in g["CANDIDATE_SCHEMA"]["FORBIDDEN_FIELDS"]
    assert set(g["ROLES"]) == {
        "GENERATOR", "NOVELTY_CRITIC", "FEASIBILITY_CRITIC", "RED_TEAM", "SELECTOR", "HUMAN"
    }
    assert set(g["DATA_STATUS_TAXONOMY"]) == {
        "DATA_READY",
        "FEASIBILITY_REQUIRED",
        "DATA_BLOCKED_MISSING_OBSERVABLE",
        "DATA_BLOCKED_PROVENANCE",
        "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS",
        "DATA_BLOCKED_COST",
    }
    catalog = g["DATA_CATALOG_V0_SEED"]
    assert catalog["PROTECTED_2025_2026"]["STATUS"] == "FORBIDDEN_HARD_FAIL"
    for name, row in catalog.items():
        assert row["STATUS"] in set(g["DATA_STATUS_TAXONOMY"]) | {"FORBIDDEN_HARD_FAIL"}, name
    batch = g["SHADOW_BATCH"]
    assert batch["BOUNDS"][0] <= g["SHADOW_BATCH_SIZE"] <= batch["BOUNDS"][1]
    assert g["BUDGET"]["REAL_LLM_BUDGET_CAP_USD"] <= 30
    assert g["ZERO_COST_MOCK_MODE_REQUIRED"] is True
    assert g["LLM_PROVIDER_NEUTRAL"] is True
    assert g["NEXT_UNIT"] == NEXT_UNIT


def test_selector_and_evaluation_never_use_outcomes():
    g = _load(DESIGN)
    forbidden_inputs = " ".join(g["ROLES"]["SELECTOR"]["FORBIDDEN_INPUTS"]).lower()
    assert "outcome labels" in forbidden_inputs
    assert "probability-of-success" in forbidden_inputs
    ev = g["GENERATOR_EVALUATION_CRITERIA"]
    assert "EXPECTED_PROBABILITY_OF_SUCCESS" in ev["FORBIDDEN_SCORES"]
    assert "never a generator reward" in ev["ANTI_GOODHART"]
    assert "no single opaque total score" in ev["SCALE"]


def test_blind_map_whitelist_is_realizable_on_current_memory():
    memory = _load(MEMORY)
    blind = _load(DESIGN)["BLIND_GENERATOR_CONTEXT"]
    deny = re.compile(blind["CONTEXT_SCANNER"]["DENYLIST_REGEX"], re.IGNORECASE)
    fields = {f for entry in memory["ENTRIES"].values() for f in entry}
    assert set(blind["WHITELISTED_FIELDS"]) <= fields
    assert not set(blind["WHITELISTED_FIELDS"]) & set(blind["EXCLUDED_FIELDS"])
    assert set(blind["WHITELISTED_FIELDS"]) | set(blind["EXCLUDED_FIELDS"]) == fields
    projection = _blind_projection(memory, blind)
    hits = {
        key: text
        for key, row in projection.items()
        for text in [json.dumps(row)]
        if deny.search(text)
    }
    assert hits == {}
    assert {row["REGION_STATE"] for row in projection.values()} == {"PRIOR_WORK_SIGNATURE"}


def test_excluded_fields_would_leak_outcomes():
    memory = _load(MEMORY)
    blind = _load(DESIGN)["BLIND_GENERATOR_CONTEXT"]
    deny = re.compile(blind["CONTEXT_SCANNER"]["DENYLIST_REGEX"], re.IGNORECASE)
    for field in ("STATUS_EVIDENCE_CLASS", "NEIGHBOR_RESCUE_WARNING"):
        leaking = [k for k, e in memory["ENTRIES"].items() if e.get(field) and deny.search(str(e[field]))]
        assert leaking, field
    raw_d2 = memory["ENTRIES"]["D2"]["INFORMATION_SOURCE"]
    assert deny.search(raw_d2)


def test_routing_docs_point_at_next_unit():
    for rel in (
        "docs/CURRENT_RESEARCH_STATE.md",
        "docs/RESEARCH_ROADMAP.md",
        "docs/DOCUMENTATION_INDEX.md",
        "docs/RESEARCH_LEDGER.md",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert CURRENT_ROUTING_UNIT in text, rel
    design = (REPO / "docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json").read_text(encoding="utf-8")
    assert NEXT_UNIT in design
    index = (REPO / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    assert "POST_SPRINT04_AUTOMATION_MATURITY_DECISION.md" in index
    assert "HYPOTHESIS_GENERATOR_V0_DESIGN.md" in index


# --- Pre-outcome amendment 1: neutral blind map, governance authority, roles, provenance ---

SCIENTIFIC_STATE = re.compile(
    # Governance/outcome state words; "null" alone is method vocabulary (e.g. "surrogate null").
    r"\bCONSUMED\b|DEFERRED|BLOCKED|PARTIAL_OR_MIXED|\bEXECUTED\b|PROMISING|CONFIRMED",
    re.IGNORECASE,
)
FORBIDDEN_MEMORY_FIELDS = {
    "STATUS_EVIDENCE_CLASS",
    "WHAT_WAS_ACTUALLY_TESTED",
    "WHAT_THE_RESULT_DEPRIORITIZES_OR_CLOSES",
    "WHAT_REMAINS_OPEN",
    "NEIGHBOR_RESCUE_WARNING",
    "POSTHOC_RESIDUALS_IF_ANY",
}


def _authority() -> dict:
    # Rules come from the frozen design; ROWS are the published projection of the
    # append-only memory chain (docs/research/generator_v0_memory/), mirrored here.
    return _load(AUTHORITY)


def test_design_holds_governance_rules_but_no_dynamic_rows():
    design = _load(DESIGN)["GOVERNANCE_REGION_AUTHORITY_V0"]
    assert "ROWS" not in design and "generator_v0_memory" in design["ROWS_SOURCE"]
    assert {k: v for k, v in _authority().items() if k != "ROWS"} == {k: v for k, v in design.items() if k != "ROWS_SOURCE"}


def _rows_by_id(authority: dict) -> dict:
    out = {}
    for row in authority["ROWS"]:
        out[row["SIGNATURE_ID"]] = row
        for sub in row.get("SUB_SIGNATURES", []):
            out[sub["SIGNATURE_ID"]] = sub
    return out


def _novelty_verdict(authority: dict, signature_id: str, relation: str) -> str:
    row = _rows_by_id(authority)[signature_id]
    assert row["STATE"] != "PARTIAL_OR_MIXED", "mixed rows adjudicate at sub-signature level"
    return authority["NOVELTY_DECISION_TABLE"][row["STATE"]][relation]


def _stream(verdict: str, data_statuses: list[str], red_team_pass: bool = True) -> str:
    if not red_team_pass or verdict not in ("ALLOW", "ALLOW_TO_FEASIBILITY"):
        return "NOT_A_STREAM"
    if verdict == "ALLOW" and all(s == "DATA_READY" for s in data_statuses):
        return "EXECUTABLE_NOW"
    if any(s == "FEASIBILITY_REQUIRED" or s.startswith("DATA_BLOCKED_") for s in data_statuses):
        return "HIGH_VALUE_DATA_BLOCKED"
    return "NOT_A_STREAM"


def test_blind_map_state_is_neutral_prior_work_signature():
    g = _load(DESIGN)
    blind = g["BLIND_GENERATOR_CONTEXT"]
    assert blind["PER_ENTRY_ADDED_FIELD"] == {"REGION_STATE": "PRIOR_WORK_SIGNATURE"}
    assert blind["REGION_STATE_VALUE"] == "PRIOR_WORK_SIGNATURE"
    assert blind["GENERATOR_SEES_EXECUTION_STATUS"] is False
    assert blind["GENERATOR_SEES_OUTCOME_LABELS"] is False
    assert "cosmetic" in blind["GENERATOR_SIDE_RULE"]
    projection = _blind_projection(_load(MEMORY), blind)
    assert "CONSUMED" not in json.dumps(projection)
    assert {row["REGION_STATE"] for row in projection.values()} == {"PRIOR_WORK_SIGNATURE"}


def test_generator_context_carries_no_scientific_state():
    g = _load(DESIGN)
    blind = g["BLIND_GENERATOR_CONTEXT"]
    # Status-bearing wording inside whitelisted fields is removed by reviewed overrides.
    assert blind["SANITIZATION_OVERRIDES"]["D4.FUNCTION"] == "Rolling 90d correlation range; 1-day lead-lag"
    assert "reclassified" not in blind["SANITIZATION_OVERRIDES"]["D1.MECHANISM"]
    projection = _blind_projection(_load(MEMORY), blind)
    for key, row in projection.items():
        assert set(row) == set(blind["WHITELISTED_FIELDS"]) | {"REGION_STATE"}, key
        assert not SCIENTIFIC_STATE.search(json.dumps(row)), key
    assert "GOVERNANCE_REGION_AUTHORITY_V0" in g["ROLE_CONTEXT_MATRIX"]["GENERATOR"]["FORBIDDEN"]


def test_role_context_matrix_is_explicit_and_complete():
    g = _load(DESIGN)
    matrix = g["ROLE_CONTEXT_MATRIX"]
    vocab = set(g["ROLE_CONTEXT_ARTIFACTS"])
    assert set(matrix) == set(g["ROLES"]) == {
        "GENERATOR", "NOVELTY_CRITIC", "FEASIBILITY_CRITIC", "RED_TEAM", "SELECTOR", "HUMAN"
    }
    assert g["ROLE_CONTEXT_MATRIX_FROZEN"] is True
    for role, spec in matrix.items():
        allowed, forbidden = set(spec["ALLOWED"]), set(spec["FORBIDDEN"])
        conditional = set(spec["CONDITIONAL"])
        assert allowed | forbidden | conditional <= vocab, role
        assert not allowed & forbidden and not conditional & (allowed | forbidden), role
    assert matrix["GENERATOR"]["ALLOWED"] == [
        "BLIND_MECHANISM_MAP_V0", "DATA_CATALOG_V0", "CANDIDATE_SCHEMA",
        "DATA_STATUS_TAXONOMY", "GENERIC_METHODOLOGY",
    ]
    assert "GOVERNANCE_REGION_AUTHORITY_V0" in matrix["NOVELTY_CRITIC"]["ALLOWED"]
    assert set(matrix["RED_TEAM"]["CONDITIONAL"]) == {"GOVERNANCE_REGION_AUTHORITY_V0"}
    # FULL_RESEARCH_HISTORY is reachable only by the human.
    holders = [r for r, spec in matrix.items() if "FULL_RESEARCH_HISTORY" in spec["ALLOWED"]]
    assert holders == ["HUMAN"]
    full = g["FULL_GOVERNANCE_CONTEXT"]
    assert full["MODEL"] == "PER_ROLE_ONLY"
    assert full["NO_ROLE_AGNOSTIC_FULL_CONTEXT_BUNDLE"] is True


def test_selector_cannot_receive_memory_results_or_authority():
    g = _load(DESIGN)
    sel = g["ROLE_CONTEXT_MATRIX"]["SELECTOR"]
    assert set(sel["ALLOWED"]) == {"SANITIZED_CRITIC_OUTPUTS", "DATA_STATUS", "SELECTION_JUDGMENTS"}
    assert sel["CONDITIONAL"] == {}
    for artifact in (
        "MECHANISM_MEMORY_V0_RAW",
        "RESULT_ARTIFACTS",
        "GOVERNANCE_REGION_AUTHORITY_V0",
        "OUTCOME_LABELS",
        "FULL_RESEARCH_HISTORY",
        "PRIOR_PROTOTYPE_OR_NULL_IDENTITY",
    ):
        assert artifact in sel["FORBIDDEN"], artifact
    fields = set(g["SANITIZED_CRITIC_OUTPUT_FIELDS"])
    assert not fields & {"STATE", "REGION_STATE", "CITED_SIGNATURE_STATE", "STATUS_EVIDENCE_CLASS"}
    assert not any(SCIENTIFIC_STATE.search(f) for f in fields if f != "DATA_STATUS")


def test_governance_authority_rows_are_outcome_free_and_cover_memory():
    authority = _authority()
    memory = _load(MEMORY)
    assert _load(DESIGN)["GOVERNANCE_REGION_AUTHORITY_DESIGNED"] is True
    assert set(authority["STATES"]) == {"CONSUMED", "DEFERRED_OR_BLOCKED", "PARTIAL_OR_MIXED"}
    top_ids = [row["SIGNATURE_ID"] for row in authority["ROWS"]]
    assert len(top_ids) == len(set(top_ids))
    assert set(top_ids) == set(memory["ENTRIES"])
    allowed = set(authority["ROW_FIELDS"])
    outcome = re.compile(
        r"p[-_ ]?value|effect size|prototype|promising|profit|\bgate\b|\b20[12]\d\b|\d\.\d",
        re.IGNORECASE,
    )
    for sig, row in _rows_by_id(authority).items():
        assert set(row) - {"SUB_SIGNATURES"} == allowed, sig
        assert row["STATE"] in authority["STATES"], sig
        text = json.dumps({k: v for k, v in row.items() if k != "SUB_SIGNATURES"})
        assert not outcome.search(text), sig
        assert not re.search(r"\bPASS\b|\bFAIL\b", text), sig
        if row["STATE"] == "DEFERRED_OR_BLOCKED":
            assert row["BLOCKER_CLASS_IF_ANY"] and row["BLOCKER_RESOLUTION_REQUIREMENT_IF_ANY"], sig
        if row["STATE"] == "CONSUMED":
            assert row["BLOCKER_CLASS_IF_ANY"] is None, sig
    assert "NOVELTY_CRITIC" in authority["CONSUMERS"]
    assert not any(c.startswith(("GENERATOR", "SELECTOR")) for c in authority["CONSUMERS"])


def test_decision_table_semantics():
    table = _authority()["NOVELTY_DECISION_TABLE"]
    assert table["CONSUMED"] == {
        "EXACT_DUPLICATE": "REJECT",
        "PARAMETER_NEIGHBOR": "REJECT",
        "FUNCTIONAL_RELABEL": "REJECT",
        "RESOLVES_BLOCKER": "HUMAN_REVIEW",
        "ORTHOGONAL_MECHANISM": "ALLOW",
    }
    blocked = table["DEFERRED_OR_BLOCKED"]
    assert blocked["EXACT_DUPLICATE"] in ("REJECT", "DEFER_BLOCKER_UNRESOLVED")
    assert blocked["RESOLVES_BLOCKER"] == "ALLOW_TO_FEASIBILITY"
    assert blocked["ORTHOGONAL_MECHANISM"] == "ALLOW"
    assert table["PARTIAL_OR_MIXED"] == "APPLY_SUB_SIGNATURE_STATE"
    assert _load(DESIGN)["DEFERRED_REGIONS_NOT_GLOBALLY_CONSUMED"] is True


def test_blocked_and_deferred_signatures_do_not_close_their_region():
    """F5 contract: Stream B demand survives blocked/deferred signatures."""
    authority = _authority()
    rows = _rows_by_id(authority)
    assert _load(DESIGN)["STREAM_B_PRESERVED"] is True
    assert "closes a family" in authority["FAMILY_NOT_CLOSED_BY_ROW"]

    # B2-06: a distinct funding/OI candidate stays eligible as HIGH_VALUE_DATA_BLOCKED.
    assert rows["B2-06"]["STATE"] == "DEFERRED_OR_BLOCKED"
    for relation in ("ORTHOGONAL_MECHANISM", "RESOLVES_BLOCKER"):
        verdict = _novelty_verdict(authority, "B2-06", relation)
        assert _stream(verdict, ["DATA_READY", "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"]) == (
            "HIGH_VALUE_DATA_BLOCKED"
        ), relation
    assert _stream(
        _novelty_verdict(authority, "B2-06", "EXACT_DUPLICATE"),
        ["DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"],
    ) == "NOT_A_STREAM"

    # D8: a distinct event-response mechanism is allowed; the exact card is not.
    assert rows["D8"]["STATE"] == "DEFERRED_OR_BLOCKED"
    assert _novelty_verdict(authority, "D8", "ORTHOGONAL_MECHANISM") == "ALLOW"
    assert _stream("ALLOW", ["DATA_READY"]) == "EXECUTABLE_NOW"
    assert _novelty_verdict(authority, "D8", "PARAMETER_NEIGHBOR") == "REJECT"

    # D6: another pinned external mechanism is allowed; family I is not consumed.
    assert rows["D6"]["STATE"] == "DEFERRED_OR_BLOCKED"
    assert rows["D6"]["BLOCKER_CLASS_IF_ANY"] == "DATA_PROVENANCE_SOURCE_NOT_PINNED"
    assert _novelty_verdict(authority, "D6", "ORTHOGONAL_MECHANISM") == "ALLOW"
    assert _novelty_verdict(authority, "D6", "RESOLVES_BLOCKER") == "ALLOW_TO_FEASIBILITY"
    assert _stream("ALLOW_TO_FEASIBILITY", ["FEASIBILITY_REQUIRED"]) == "HIGH_VALUE_DATA_BLOCKED"


def test_d4_mixed_subregions_are_distinct():
    authority = _authority()
    rows = _rows_by_id(authority)
    assert _load(DESIGN)["D4_MIXED_STATE_REPRESENTED"] is True
    d4 = rows["D4"]
    assert d4["STATE"] == "PARTIAL_OR_MIXED"
    subs = {s["SIGNATURE_ID"]: s for s in d4["SUB_SIGNATURES"]}
    assert set(subs) == {"D4.ROLLING_CORRELATION_90D", "D4.LEAD_LAG_1DAY"}
    assert subs["D4.ROLLING_CORRELATION_90D"]["STATE"] == "CONSUMED"
    assert subs["D4.LEAD_LAG_1DAY"]["STATE"] == "DEFERRED_OR_BLOCKED"
    assert subs["D4.LEAD_LAG_1DAY"]["BLOCKER_CLASS_IF_ANY"]
    for relation in ("EXACT_DUPLICATE", "PARAMETER_NEIGHBOR", "FUNCTIONAL_RELABEL"):
        assert _novelty_verdict(authority, "D4.ROLLING_CORRELATION_90D", relation) == "REJECT"
    assert _novelty_verdict(authority, "D4.LEAD_LAG_1DAY", "RESOLVES_BLOCKER") == "ALLOW_TO_FEASIBILITY"
    try:
        _novelty_verdict(authority, "D4", "ORTHOGONAL_MECHANISM")
    except AssertionError:
        pass
    else:
        raise AssertionError("D4 must be adjudicated at sub-signature level")


def test_structural_provenance_guard_excludes_outcome_fields():
    g = _load(DESIGN)
    blind = g["BLIND_GENERATOR_CONTEXT"]
    guard = blind["STRUCTURAL_PROVENANCE_GUARD"]
    assert g["STRUCTURAL_CONTEXT_PROVENANCE_GUARD_FROZEN"] is True
    assert guard["PRIMARY_PROTECTION"] is True
    assert set(guard["FORBIDDEN_SOURCE_FIELDS"]) == FORBIDDEN_MEMORY_FIELDS
    assert "BLIND_MECHANISM_MAP_V0.json" in guard["MATERIALIZATION"]
    assert "SHA256" in guard["MATERIALIZATION"]
    assert "refuses" in guard["FAIL_CLOSED_ON_MEMORY_CHANGE"]
    required = {"SOURCE_ARTIFACT", "SOURCE_FIELD", "TRANSFORM", "OUTPUT_FIELD"}
    outputs = set()
    for entry in guard["FIELD_ALLOWLIST"]:
        assert set(entry) == required, entry
        outputs.add(entry["OUTPUT_FIELD"])
        assert not any(f in entry["SOURCE_FIELD"] for f in FORBIDDEN_MEMORY_FIELDS), entry
        assert "RESULT" not in entry["SOURCE_ARTIFACT"], entry
        assert "discovery_results" not in entry["SOURCE_ARTIFACT"], entry
        assert "GOVERNANCE_REGION_AUTHORITY" not in entry["SOURCE_FIELD"], entry
    # Every map field has a provenance entry; nothing else from memory is allowlisted.
    assert set(blind["WHITELISTED_FIELDS"]) | {"REGION_STATE"} <= outputs
    memory_sources = {
        e["SOURCE_FIELD"].split(".")[-1]
        for e in guard["FIELD_ALLOWLIST"]
        if e["SOURCE_ARTIFACT"].endswith("MECHANISM_MEMORY_V0.json")
    }
    assert memory_sources == set(blind["WHITELISTED_FIELDS"])
    assert FORBIDDEN_MEMORY_FIELDS <= set(blind["EXCLUDED_FIELDS"])
    # Overrides may only target allowlisted fields.
    for target in blind["SANITIZATION_OVERRIDES"]:
        assert target.split(".", 1)[1] in blind["WHITELISTED_FIELDS"], target
    assert any("allowlisted provenance" in h for h in g["HARD_FAIL_CRITERIA"])


def test_scanner_is_backstop_and_passes_assembled_blind_context():
    g = _load(DESIGN)
    blind = g["BLIND_GENERATOR_CONTEXT"]
    scanner = blind["CONTEXT_SCANNER"]
    assert scanner["ROLE"] == "BACKSTOP_ONLY"
    assert g["SCANNER_REMAINS_BACKSTOP"] is True
    deny = re.compile(scanner["DENYLIST_REGEX"], re.IGNORECASE)
    assembled = {
        "BLIND_MECHANISM_MAP_V0": _blind_projection(_load(MEMORY), blind),
        "DATA_CATALOG_V0": {
            k: {f: v.get(f) for f in ("CONTENT", "LEGAL_RANGE", "STATUS")}
            for k, v in g["DATA_CATALOG_V0_SEED"].items()
        },
        "CANDIDATE_SCHEMA": g["CANDIDATE_SCHEMA"]["REQUIRED_FIELDS"],
        "DATA_STATUS_TAXONOMY": g["DATA_STATUS_TAXONOMY"],
        "GENERIC_METHODOLOGY": g["GENERIC_METHODOLOGY_LESSONS"],
        "GENERATOR_SIDE_RULE": blind["GENERATOR_SIDE_RULE"],
    }
    text = json.dumps(assembled, ensure_ascii=False)
    assert not deny.search(text), deny.search(text)
    # The governance authority would be caught if it ever leaked in.
    assert deny.search(json.dumps(_authority()["ROWS"]))


def test_generator_side_rule_has_explicit_identity_provenance():
    g = _load(DESIGN)
    blind = g["BLIND_GENERATOR_CONTEXT"]
    assert blind["GENERATOR_SIDE_RULE"] == (
        "Avoid exact duplicates of prior-work signatures and cosmetic parameter, "
        "window, threshold or horizon relabels of them."
    )
    rows = blind["STRUCTURAL_PROVENANCE_GUARD"]["FIELD_ALLOWLIST"]
    matched = [r for r in rows if r["OUTPUT_FIELD"] == "GENERATOR_SIDE_RULE"]
    assert matched == [{
        "OUTPUT_FIELD": "GENERATOR_SIDE_RULE",
        "SOURCE_ARTIFACT": "docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.json",
        "SOURCE_FIELD": "BLIND_GENERATOR_CONTEXT.GENERATOR_SIDE_RULE",
        "TRANSFORM": "IDENTITY",
    }]
    assert len(rows) == 11  # The sole authorized expansion of the ten-row freeze.
    assert "MECHANISM_MEMORY" not in matched[0]["SOURCE_ARTIFACT"]
    assert "RESULT" not in matched[0]["SOURCE_ARTIFACT"]
    # This rule is mandatory, with exact bytes, in the allowed methodology bundle.
    assembled = {
        "BLIND_MECHANISM_MAP_V0": _blind_projection(_load(MEMORY), blind),
        "DATA_CATALOG_V0": {
            k: {f: v.get(f) for f in ("CONTENT", "LEGAL_RANGE", "STATUS")}
            for k, v in g["DATA_CATALOG_V0_SEED"].items()
        },
        "CANDIDATE_SCHEMA": g["CANDIDATE_SCHEMA"]["REQUIRED_FIELDS"],
        "DATA_STATUS_TAXONOMY": g["DATA_STATUS_TAXONOMY"],
        "GENERIC_METHODOLOGY": {
            "LESSONS": g["GENERIC_METHODOLOGY_LESSONS"],
            "GENERATOR_SIDE_RULE": blind["GENERATOR_SIDE_RULE"],
        },
    }
    assert assembled["GENERIC_METHODOLOGY"]["GENERATOR_SIDE_RULE"]
    assert not re.search(blind["CONTEXT_SCANNER"]["DENYLIST_REGEX"],
                         json.dumps(assembled), re.IGNORECASE)


# Historical state/blocker language that must never appear in a projected prior-work row.
# Applied to the blind-map projection only, not to DATA_CATALOG_V0 (current data status is
# intentionally visible). Mechanism vocabulary such as "failed breakout", "null model" or
# "confirmatory" is allowed.
BLIND_ROW_STATE_LANGUAGE = re.compile(
    r"unpinned|\bpinned\b|unauthori[sz]ed|deferred|blocked|consumed|not executed|not tested"
    r"|not run|insufficient (?:control|support)|insufficient|publication latency|unresolved"
    r"|replicat|promising|prototype|rejected|no useful structure|no evidence|reclassified",
    re.IGNORECASE,
)


def test_blind_map_rows_carry_no_historical_state_language():
    blind = _load(DESIGN)["BLIND_GENERATOR_CONTEXT"]
    projection = _blind_projection(_load(MEMORY), blind)
    hits = {
        key: match.group(0)
        for key, row in projection.items()
        for match in [BLIND_ROW_STATE_LANGUAGE.search(json.dumps(row))]
        if match
    }
    assert hits == {}
    d6 = projection["D6"]
    assert d6["INFORMATION_SOURCE"] == "External mechanism source + CORE_BTC"
    assert d6["FUNCTION"] == "Diagnostic reproduction of an external mechanism"
    # The raw memory fields did leak, so the overrides are load-bearing.
    raw = _load(MEMORY)["ENTRIES"]
    for key, field in (("D6", "INFORMATION_SOURCE"), ("D4", "FUNCTION"), ("D1", "MECHANISM"), ("D2", "INFORMATION_SOURCE")):
        assert BLIND_ROW_STATE_LANGUAGE.search(raw[key][field]), (key, field)
    # The governance row itself is unchanged and still records the blocker.
    gov = _rows_by_id(_authority())["D6"]
    assert gov["STATE"] == "DEFERRED_OR_BLOCKED"
    assert gov["BLOCKER_CLASS_IF_ANY"] == "DATA_PROVENANCE_SOURCE_NOT_PINNED"
