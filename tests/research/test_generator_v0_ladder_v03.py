"""GENERATOR_CONTRACT_V03 complexity-ladder amendment. Mock provider only: no LLM calls, no market data."""
import copy
import json

import pytest

from scripts.research.generator_v0 import contract, contract_v03 as v3
from scripts.research.generator_v0.__main__ import main
from scripts.research.generator_v0.complexity import COMPLEXITY_CLASSES
from scripts.research.generator_v0.context import Contexts, ContractError, canonical
from scripts.research.generator_v0.derive import derive_complete_rounds, fresh_campaign_budget_preflight
from scripts.research.generator_v0.ledger import Ledger
from scripts.research.generator_v0.mock import MockResponder, fixture, slot_plan
from scripts.research.generator_v0.output_schemas import anthropic_generator_compact_schema, role_schema
from scripts.research.generator_v0.provider import Caller, MockProvider
from scripts.research.generator_v0.roles import (NOVELTY_PROMPT, NOVELTY_PROMPT_V03, RED_PROMPT, RED_PROMPT_V03,
                                                 RoleContractError, Roles, red_checks)
from scripts.research.generator_v0.runner import (GENERATOR_PROMPT, GENERATOR_PROMPT_V03, card_violations_for,
                                                  contract_of_request, generator_identity, ladder_config, run_campaign,
                                                  slot_violations_v02)
from scripts.research.generator_v0.schema import encode_provider_card, output_schema, validate_card, validate_instance

V03 = v3.CONTRACT_ID


@pytest.fixture(scope="module")
def c():
    return Contexts()


def ladder_card(c, i=0):
    return fixture(v3.slot_plan()[i], c)


def rules(violations):
    return {v["RULE"] for v in violations}


# --------------------------------------------------------------------------- slot plan
def test_slot_mix_is_frozen_16_14_7_3_and_assigned_before_any_call():
    plan = v3.slot_plan(40)
    assert plan == v3.slot_plan(40)                                   # deterministic
    counts = {k: sum(s["COMPLEXITY_CLASS"] == k for s in plan) for k in COMPLEXITY_CLASSES}
    assert counts == {"ATOMIC": 16, "CONDITIONAL": 14, "INTERACTION": 7, "COMPOSITE": 3}
    rounds = [[s["COMPLEXITY_CLASS"] for s in plan[i:i + 10]] for i in range(0, 40, 10)]
    assert [r.count("ATOMIC") for r in rounds] == [4, 4, 4, 4]
    assert all(len(r) == 10 for r in rounds)
    v02 = slot_plan(40)
    assert [{k: v for k, v in s.items() if k != "COMPLEXITY_CLASS"} for s in plan] == v02
    assert all("COMPLEXITY_CLASS" not in s for s in v02)
    v3.ladder_diversity(plan)
    with pytest.raises(ContractError):
        v3.slot_plan(30)
    bad = copy.deepcopy(plan)
    bad[0]["COMPLEXITY_CLASS"] = "INTERACTION"
    with pytest.raises(ContractError):
        v3.ladder_diversity(bad)


def test_each_family_position_meets_several_rungs():
    plan = v3.slot_plan(40)
    for pos in range(10):
        assert len({plan[r * 10 + pos]["COMPLEXITY_CLASS"] for r in range(3)}) >= 2


# --------------------------------------------------------------------------- the model never chooses its rung
def test_provider_schema_pins_the_slot_rung(c):
    slot = v3.slot_plan()[2]                                          # INTERACTION
    schema = output_schema(c, provider=True, slot=slot)
    assert schema["properties"]["COMPLEXITY_CLASS"]["enum"] == ["INTERACTION"]
    card = encode_provider_card(fixture(slot, c))
    validate_instance(card, schema)
    card["COMPLEXITY_CLASS"] = "ATOMIC"
    violations, _ = slot_violations_v02(card, c, slot)
    assert rules(violations) == {"PROVIDER_SCHEMA"}
    app = fixture(slot, c)
    app["COMPLEXITY_CLASS"] = "ATOMIC"
    assert "SLOT_IDENTITY" in rules(card_violations_for(app, c, slot))


def test_compact_wire_offers_only_the_round_rungs_and_intake_rebinds_exactly(c):
    slots = v3.slot_plan()[:10]
    compact = anthropic_generator_compact_schema(c, {"parameters": {"slots": slots}})
    assert compact["properties"]["CANDIDATES"]["items"]["properties"]["COMPLEXITY_CLASS"]["enum"] == ["ATOMIC", "CONDITIONAL", "INTERACTION"]
    v02_compact = anthropic_generator_compact_schema(c, {"parameters": {"slots": slot_plan()[:10]}})
    assert "COMPLEXITY_CLASS" not in v02_compact["properties"]["CANDIDATES"]["items"]["properties"]


def test_mixed_rounds_are_refused(c):
    with pytest.raises(ContractError):
        generator_identity(c, v3.slot_plan()[:5] + slot_plan()[5:10])


# --------------------------------------------------------------------------- V03 rule table
def test_rule_table_prompt_and_checks_agree(c):
    assert v3.RULE_IDS[:len(contract.RULE_IDS)] == contract.RULE_IDS
    assert set(v3.RULE_IDS) - set(contract.RULE_IDS) == {"COMPONENTS", "MAIN_EFFECT_BASELINE", "COMPLEXITY_RUNG", "SIMPLE_IS_NOT_BANAL"}
    for rule in v3.RULES:
        assert ("[" + rule["ID"] + "] " + rule["TEXT"]) in GENERATOR_PROMPT_V03
        assert (rule["ID"] in v3.CHECKS) != (rule["ID"] in v3.CRITIC_ENFORCEMENT)
    assert set(v3.CRITIC_ENFORCEMENT) == {r["ID"] for r in v3.RULES if r["ENFORCEMENT"] == "CRITIC"}
    assert GENERATOR_PROMPT == contract.generator_prompt() and GENERATOR_PROMPT != GENERATOR_PROMPT_V03
    c.validate("GENERATOR", c.generator(), GENERATOR_PROMPT_V03)    # passes the outcome-leak scanner


def test_fixture_cards_are_valid_v03_cards(c):
    for slot in v3.slot_plan():
        card = fixture(slot, c)
        assert card_violations_for(card, c, slot) == [], slot
        validate_card(card, c)


@pytest.mark.parametrize("cls,n_ok,n_bad", [("ATOMIC", 0, 1), ("CONDITIONAL", 0, 2), ("INTERACTION", 2, 3), ("COMPOSITE", 3, 2)])
def test_component_counts_by_rung(c, cls, n_ok, n_bad):
    slot = next(s for s in v3.slot_plan() if s["COMPLEXITY_CLASS"] == cls)
    card = fixture(slot, c)
    assert len(card["COMPONENTS"]) == n_ok
    card["COMPONENTS"] = ["Component " + str(k) for k in range(n_bad)]
    card["BASELINE_OR_NULL"] += " " + " ".join(card["COMPONENTS"])
    assert "COMPONENTS" in rules(card_violations_for(card, c, slot))


def test_components_are_distinct_short_strings(c):
    slot = next(s for s in v3.slot_plan() if s["COMPLEXITY_CLASS"] == "INTERACTION")
    card = fixture(slot, c)
    card["COMPONENTS"] = [card["COMPONENTS"][0], card["COMPONENTS"][0].upper()]
    assert "COMPONENTS" in rules(card_violations_for(card, c, slot))
    card = fixture(slot, c)
    card["COMPONENTS"][1] = "x" * 201
    assert "COMPONENTS" in rules(card_violations_for(card, c, slot))


def test_interaction_baseline_must_name_each_component_main_effect(c):
    slot = next(s for s in v3.slot_plan() if s["COMPLEXITY_CLASS"] == "INTERACTION")
    card = fixture(slot, c)
    card["BASELINE_OR_NULL"] = "Stratum-preserving permutation null with " + card["COMPONENTS"][0] + " only"
    assert "MAIN_EFFECT_BASELINE" in rules(card_violations_for(card, c, slot))
    # Control is required, prior support is not: no rule reads a component's own result.
    assert "need not have an effect of its own" in GENERATOR_PROMPT_V03


def test_v03_card_keeps_every_v02_safety_rule(c):
    slot = v3.slot_plan()[0]
    card = fixture(slot, c)
    card["MECHANISM"] = "holds into 2025"
    assert "NO_PROTECTED_YEARS" in rules(card_violations_for(card, c, slot))
    card = fixture(slot, c)
    card["COMPONENTS"] = []
    card.pop("COMPONENTS")
    assert "SCHEMA_FIELDS" in rules(card_violations_for(card, c, slot))
    with pytest.raises(ContractError):
        validate_card(card, c)


# --------------------------------------------------------------------------- critics
class Recorder:
    def __init__(self, contexts, answer):
        self.contexts, self.answer, self.requests = contexts, answer, []

    def call(self, role, context, prompt, parameters, slot, content_attempt=0, identity=None):
        self.requests.append((role, prompt))
        return canonical(self.answer(role, context))


def test_critics_use_ladder_prompts_and_red_team_checks_rung_consistency(c):
    mock = MockResponder(c)
    card = ladder_card(c)
    rec = Recorder(c, lambda role, ctx: json.loads(mock({"role": role, "context": ctx})))
    roles = Roles(c, rec)
    batch = [fixture(s, c) for s in v3.slot_plan()[:3]]
    roles.novelty(card, batch)
    red = roles.red_team(card)
    assert rec.requests[0] == ("NOVELTY_CRITIC", NOVELTY_PROMPT_V03)
    assert rec.requests[1] == ("RED_TEAM", RED_PROMPT_V03)
    assert red["VERDICT"] == "PASS" and "RUNG_CONSISTENT" in red["CHECKS"]
    assert "RUNG_CONSISTENT" in red_checks(card) and "RUNG_CONSISTENT" not in red_checks(fixture(slot_plan()[0], c))
    schema = role_schema("RED_TEAM", c, provider=True, request={"context": {"CANDIDATE": card}})
    assert "RUNG_CONSISTENT" in schema["properties"]["CHECKS"]["properties"]
    v02 = role_schema("RED_TEAM", c, provider=True, request={"context": {"CANDIDATE": fixture(slot_plan()[0], c)}})
    assert "RUNG_CONSISTENT" not in v02["properties"]["CHECKS"]["properties"]
    assert "Simplicity is not banality" in NOVELTY_PROMPT_V03 and "Simplicity" not in NOVELTY_PROMPT
    assert "RUNG_CONSISTENT" in RED_PROMPT_V03 and "RUNG_CONSISTENT" not in RED_PROMPT


def test_rung_mismatch_rejects_and_a_missing_rung_check_is_a_contract_error(c):
    card = ladder_card(c)
    roles = Roles(c, None)
    raw = {"CHECKS": {k: True for k in red_checks(card)}, "JUDGMENTS": {k: 2 for k in
           ("FALSIFIABILITY", "NO_LOOKAHEAD_QUALITY", "CONFOUNDING_AWARENESS", "SEARCH_SURFACE_DISCIPLINE", "NULL_INFORMATION_GAIN")}}
    raw["CHECKS"]["RUNG_CONSISTENT"] = False
    assert roles._red_team(raw, card)["VERDICT"] == "REJECT"
    del raw["CHECKS"]["RUNG_CONSISTENT"]
    with pytest.raises(ContractError):
        roles._red_team(raw, card)


# --------------------------------------------------------------------------- campaign
def ladder_campaign(path, responder=None):
    c = Contexts()
    ledger = Ledger(path, ladder_config(RUN_ID=path.name, SIZE=40))
    provider = MockProvider(responder or MockResponder(c))
    return run_campaign(c, Caller(c, ledger, provider)), ledger, provider


def test_mock_ladder_campaign_end_to_end_with_quota_shortlist(tmp_path):
    result, ledger, provider = ladder_campaign(tmp_path / "v03.sqlite")
    assert result["CONTRACT"] == V03 and result["STATUS"] == "PENDING_HUMAN_REVIEW"
    assert result["METRICS"]["VALID"] == 40 and result["METRICS"]["HARD_FAIL"] == 0
    seats = result["SHORTLIST_RULE"]["SEATS"]
    assert [s["SEAT"] for s in seats] == ["ATOMIC", "ATOMIC", "CONDITIONAL", "CONDITIONAL", "COMPLEX"]
    assert result["SHORTLIST"] == [s["CANDIDATE_ID"] for s in seats]
    by_id = {x["CANDIDATE_ID"]: x for x in result["CANDIDATES"]}
    assert all(by_id[s["CANDIDATE_ID"]]["COMPLEXITY_CLASS"] == s["COMPLEXITY_CLASS"] for s in seats)
    gen = [x for x in ledger.export_calls() if x["ROLE"] == "GENERATOR"]
    assert len(gen) == 4 and {x["PROMPT_VERSION"] for x in gen} == {v3.PROMPT_VERSION}
    assert provider.calls == 125                                     # 4 generator + 3 x 40 critics + 1 advisory selector
    assert contract_of_request({"prompt_version": v3.PROMPT_VERSION}) == V03
    again, _, _ = ladder_campaign(tmp_path / "v03b.sqlite")
    assert again["SEMANTIC_RESULT_DIGEST"] == result["SEMANTIC_RESULT_DIGEST"]


class RejectComplex(MockResponder):
    """Red team finds every INTERACTION/COMPOSITE card off its rung."""
    def __call__(self, request):
        out = super().__call__(request)
        if request["role"] == "RED_TEAM" and request["context"]["CANDIDATE"]["COMPLEXITY_CLASS"] in ("INTERACTION", "COMPOSITE"):
            payload = json.loads(out)
            payload["CHECKS"]["RUNG_CONSISTENT"] = False
            return canonical(payload)
        return out


def test_complex_seat_passes_down_the_ladder_when_no_complex_card_survives(tmp_path):
    result, _, _ = ladder_campaign(tmp_path / "down.sqlite", RejectComplex(Contexts()))
    seats = result["SHORTLIST_RULE"]["SEATS"]
    assert seats[-1]["SEAT"] == "COMPLEX" and seats[-1]["COMPLEXITY_CLASS"] == "CONDITIONAL"
    assert all(s["COMPLEXITY_CLASS"] in ("ATOMIC", "CONDITIONAL") for s in seats)


def test_v02_campaigns_are_unchanged(tmp_path):
    c = Contexts()
    ledger = Ledger(tmp_path / "v02.sqlite", {"RUN_ID": "v02"})
    result = run_campaign(c, Caller(c, ledger, MockProvider(MockResponder(c))))
    assert result["CONTRACT"] == contract.CONTRACT_ID and "SHORTLIST_RULE" not in result
    assert all("COMPLEXITY_CLASS" not in x for x in result["CANDIDATES"])
    assert "prompt_version" not in generator_identity(c, slot_plan()[:10])


# --------------------------------------------------------------------------- budget, derive, CLI
def test_offline_budget_bound_for_the_ladder_campaign(c):
    from scripts.research.generator_v0.routed_provider import offline_routed_provider
    v03 = fresh_campaign_budget_preflight(40, 17_100_000, c, bound_provider=offline_routed_provider(c), contract_id=V03)
    v02 = fresh_campaign_budget_preflight(40, 17_100_000, c, bound_provider=offline_routed_provider(c))
    assert v03["GENERATOR_CONTRACT"] == V03 and "GENERATOR_CONTRACT" not in v02
    assert v03["WORST_CASE_REMAINING_MICRO_USD"] >= v02["WORST_CASE_REMAINING_MICRO_USD"] > 0
    assert v03["REAL_LLM_CALLS_MADE"] is False


def test_derive_refuses_a_ladder_source(tmp_path):
    (tmp_path / "src").mkdir()
    _, ledger, _ = ladder_campaign(tmp_path / "src" / "run.sqlite")
    ledger.close()
    with pytest.raises(ContractError, match="V02"):
        derive_complete_rounds(tmp_path / "src", tmp_path / "dst")


def test_cli_ladder_command_needs_explicit_live_authorization_and_v03_needs_40(tmp_path, capsys):
    with pytest.raises(ContractError, match="allow-real-llm"):
        main(["ladder-40-card", "--run-dir", str(tmp_path / "x")])
    with pytest.raises(ContractError, match="40"):
        main(["preflight", "--contract", "V03", "--size", "30", "--run-dir", str(tmp_path / "y")])
    main(["preflight", "--provider", "routed", "--contract", "V03", "--run-dir", str(tmp_path / "z")])
    info = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert info["GENERATOR_CONTRACT"] == V03 and info["REAL_LLM_CALLS_MADE"] is False
