"""Role B auditor, frozen baseline, blind A/B judge with identical-pair controls (§13–§15, §20.7)."""
import json
from datetime import datetime, timedelta

import pytest

from beta.i18n import assert_descriptive
from beta.outcomes import LAST_BAR_GRACE
from sim_helpers import CFG, bundle, models, run
from tools.beta_user_sim.baseline import BASELINE_VERSION, baseline_text
from tools.beta_user_sim.llm import ROLE_AUDITOR, ROLE_JUDGE, FakeAuditorModel, FakeJudgeModel
from tools.beta_user_sim.prompts import JUDGE_SYSTEM, ROLE_B_SYSTEM
from tools.beta_user_sim.replay import ReplayConfig, ReplayEngine
from tools.beta_user_sim.role_b import (BASELINE, INVALID, PAIR_BASELINE_VS_BASELINE, PAIR_SIGNALBOT_VS_BASELINE,
                                        PAIR_SIGNALBOT_VS_SIGNALBOT, SIGNALBOT, BlindJudge, LeakToJudge,
                                        RoleBAuditor, assert_blind, summarize_judgements)
from tools.beta_user_sim.timeline import build_timeline


class Recorder:
    def __init__(self, inner):
        self.inner, self.model_id, self.calls = inner, inner.model_id, []

    def settings(self):
        return self.inner.settings()

    def complete(self, messages, *, role):
        self.calls.append(json.loads(json.dumps(messages)))
        return self.inner.complete(messages, role=role)


def _run_recorded():
    m = models()
    m[ROLE_AUDITOR], m[ROLE_JUDGE] = Recorder(FakeAuditorModel()), Recorder(FakeJudgeModel())
    e = ReplayEngine(bundle(), CFG, m, ReplayConfig())
    return e, e.run(), m


def test_role_b_gets_a_fresh_narrow_context_per_item():
    e, r, m = _run_recorded()
    calls = m[ROLE_AUDITOR].calls
    assert calls and len(calls) == len(r["role_b"]["audits"])
    for msgs in calls:
        assert [x["role"] for x in msgs] == ["system", "user"] and msgs[0]["content"] == ROLE_B_SYSTEM
        req = json.loads(msgs[1]["content"])
        assert set(req) == {"time_T", "kind", "original_message", "claims", "what_followed", "baseline_message"}
        blob = msgs[1]["content"]
        for hidden in ("percentile", "rank", "rules_digest", "payload", "journal", "RESEARCH", "docs/",
                       "Экспериментальная закрытая бета"):
            assert hidden not in blob, hidden
    journals = [v for d in r["role_a_decisions"] for v in d["journal"].values()]
    assert journals and not any(j in json.dumps(calls, ensure_ascii=False) for j in journals)


def test_role_b_runs_only_after_every_horizon_of_the_item_matured():
    e, r, m = _run_recorded()
    items = {i.item_id: i for i in [*e.timeline.views, *e.timeline.pushes]}
    for entry in r["phase_b_log"]:
        if entry["event"] in ("ROLE_B_AUDIT", "OUTCOME_UNLOCK", "AB_JUDGE"):
            item = items[entry["item_id"]]
            assert datetime.fromisoformat(entry["t"]) >= item.at + timedelta(hours=24) + LAST_BAR_GRACE
    last_a = max(datetime.fromisoformat(t["t"]) for t in r["transcript"])
    first_b = min(datetime.fromisoformat(t["t"]) for t in r["phase_b_log"])
    assert first_b > last_a


def test_a_later_move_never_counts_against_a_message_without_a_forward_claim():
    class Hostile:
        model_id = "hostile"

        def settings(self):
            return {}

        def complete(self, messages, *, role):
            return json.dumps({"wording_stronger_than_evidence": "YES", "forward_outcome_verdict": "MISSED_MOVE",
                               "retrospective_usefulness": "NOT_USEFUL", "prediction": "wrong"})
    m = models()
    m[ROLE_AUDITOR] = Hostile()
    r = ReplayEngine(bundle(), CFG, m, ReplayConfig()).run()
    for a in r["role_b"]["audits"]:
        assert a["forward_outcome_verdict"] == "NO_DIRECTIONAL_CLAIM"
        assert a["answers"]["adds_explanatory_value_over_baseline"] == INVALID
        assert a["answers"]["retrospective_usefulness"] == "NOT_USEFUL"


def test_invalid_auditor_output_is_recorded_as_invalid():
    class Junk:
        model_id = "junk"

        def settings(self):
            return {}

        def complete(self, messages, *, role):
            return "no json here"
    b = bundle()
    item = build_timeline(b, CFG, lang="ru").pushes[0]
    from tools.beta_user_sim.claims import build_manifest
    res = RoleBAuditor(Junk()).audit(item=item, text_html=item.html,
                                     manifest=build_manifest(CFG, item, episode=b.episode(item.source["episode_pk"])),
                                     observations=[], baseline=None)
    assert set(res.answers.values()) == {INVALID}


# ---- baseline -------------------------------------------------------------------------------------
def test_baseline_is_deterministic_descriptive_and_excludes_flow_data():
    b = bundle()
    for v in b.btc_views:
        text = baseline_text(v["payload"], v["lang"])
        assert text == baseline_text(v["payload"], v["lang"]) and text.startswith("BTC")
        assert_descriptive(text, v["lang"])
        for word in ("OI", "Delta", "taker", "ликвид", "liquidat", "Binance", "Bybit", "OKX", "funding"):
            assert word.lower() not in text.lower(), word
    assert BASELINE_VERSION == "BASELINE_SIMPLE_V0"
    assert baseline_text({"now": None, "data_through": None}, "ru") is None


# ---- blind judge ---------------------------------------------------------------------------------
def test_side_assignment_is_seeded_and_covers_both_sides():
    j1, j2, j3 = BlindJudge(FakeJudgeModel(), seed=11), BlindJudge(FakeJudgeModel(), seed=11), \
        BlindJudge(FakeJudgeModel(), seed=12)
    ids = [f"view:{i}" for i in range(60)]
    a = [j1.assign(i, PAIR_SIGNALBOT_VS_BASELINE) for i in ids]
    assert a == [j2.assign(i, PAIR_SIGNALBOT_VS_BASELINE) for i in ids]
    assert a != [j3.assign(i, PAIR_SIGNALBOT_VS_BASELINE) for i in ids]
    assert 15 < sum(a) < 45


def test_judge_never_sees_identities_and_controls_are_identical_pairs():
    e, r, m = _run_recorded()
    calls = m[ROLE_JUDGE].calls
    assert calls
    kinds = {j["pair_kind"] for j in r["role_b"]["judgements"]}
    assert kinds == {PAIR_SIGNALBOT_VS_BASELINE, PAIR_BASELINE_VS_BASELINE, PAIR_SIGNALBOT_VS_SIGNALBOT}
    for msgs, j in zip(calls, r["role_b"]["judgements"]):
        assert msgs[0]["content"] == JUDGE_SYSTEM
        payload = json.loads(msgs[1]["content"])
        assert set(payload) == {"option_a", "option_b", "what_followed"}
        for side in ("option_a", "option_b"):
            for word in ("Signalbot", "baseline", "бета", "beta", "SIGNALBOT", "BASELINE"):
                assert word not in payload[side]
        if j["pair_kind"] != PAIR_SIGNALBOT_VS_BASELINE:
            assert payload["option_a"] == payload["option_b"]
        else:
            assert payload["option_a"] != payload["option_b"]
    for word in ("length", "formatting", "confidence", "number of metrics"):
        assert word in JUDGE_SYSTEM


def test_identity_leak_guard_and_identity_mapping():
    with pytest.raises(LeakToJudge):
        assert_blind({"option_a": "Signalbot says", "option_b": "x", "what_followed": []})
    with pytest.raises(LeakToJudge):
        assert_blind({"option_a": "a", "option_b": "b", "what_followed": [], "source": "baseline"})

    class AlwaysA:
        model_id = "a"

        def settings(self):
            return {}

        def complete(self, messages, *, role):
            return '{"preferred": "A"}'
    j = BlindJudge(AlwaysA(), seed=11)
    res = [j.judge(item_id=f"v{i}", pair_kind=PAIR_SIGNALBOT_VS_BASELINE, signalbot="S text", baseline="B text",
                   observations=[]) for i in range(40)]
    for x in res:
        assert x.preferred_identity == x.a_identity and {x.a_identity, x.b_identity} == {SIGNALBOT, BASELINE}
    s = summarize_judgements(res)
    assert s["side_bias_all_pairs"]["side_a_share"] == 1.0
    assert 0 < s[PAIR_SIGNALBOT_VS_BASELINE]["identity_counts"][SIGNALBOT] < 40
    assert not any("score" in k for k in s)
