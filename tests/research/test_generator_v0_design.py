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
NEXT_UNIT = "HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS"
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
        row["REGION_STATE"] = "CONSUMED"
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
    assert {row["REGION_STATE"] for row in projection.values()} == {"CONSUMED"}


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
        assert NEXT_UNIT in (REPO / rel).read_text(encoding="utf-8"), rel
    index = (REPO / "docs/DOCUMENTATION_INDEX.md").read_text(encoding="utf-8")
    assert "POST_SPRINT04_AUTOMATION_MATURITY_DECISION.md" in index
    assert "HYPOTHESIS_GENERATOR_V0_DESIGN.md" in index
