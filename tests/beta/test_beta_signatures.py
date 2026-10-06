"""Owner-only signature index (PRE_BETA_SCOPE_DECISION_V1 §7; backlog K), pure: the tuple of existing
states, «?» for what could not be read, tail states, the NEW rule, the blind owner text and the export.
Synthetic inputs only."""
from datetime import datetime, timedelta, timezone

import pytest

from beta import signatures as sg
from beta.config import BetaConfig

CFG = BetaConfig.load()
UTC = timezone.utc


@pytest.fixture
def fixed(monkeypatch):
    """Pin the three readers the signature reuses, so the mapping is what is under test."""
    from beta import context, hour_gate, interpretation
    vals = {"i1h": "long_build", "i4h": "normal", "level": "high", "gate": "QUALIFIED"}
    monkeypatch.setattr(interpretation, "interpret",
                        lambda cfg, ctx, horizon, liquidation_episodes=(): {"key": vals["i" + horizon]})
    monkeypatch.setattr(context, "level_label", lambda cfg, rank, tier: vals["level"])
    monkeypatch.setattr(hour_gate, "evaluate_hour",
                        lambda cfg, ctx, liquidation_episodes=(), snapshot=None: {"status": vals["gate"],
                                                                                  "snapshot": snapshot})
    return vals


STATE = {"context_1h": {"day_type": "WEEKDAY", "percentiles": {}}, "context_4h": {"percentiles": {}}}
RULES = {"LIQUIDATION_STRESS_LONG": {"status": "QUALIFIES"}, "LIQUIDATION_STRESS_SHORT": {"status": "NOT_QUALIFIES"}}


def test_components_are_existing_states_and_unknown_is_never_a_guess(fixed):
    c = sg.components(CFG, state=STATE, rules=RULES, d7=True, evidence=["D2", "D2", "DH3-P1"])
    assert c == {"i1h": "long_build", "i4h": "normal", "r1h": "high", "v1h": "high", "r4h": "high", "v4h": "high",
                 "gate": "Q", "d7": "on", "liq": "long", "ev": "D2+DH3-P1", "day": "WD"}
    assert sg.tail_states(c) == ["i1h", "r1h", "v1h", "r4h", "v4h", "gate", "d7", "liq", "ev"]
    blank = sg.components(CFG, state={}, rules=None, d7=None, evidence=None)
    assert blank == {k: sg.UNKNOWN for k in sg.COMPONENTS}
    assert sg.tail_states(blank) == []
    fixed.update(i1h="venues_diverge", level=None, gate="IMMATURE")
    c = sg.components(CFG, state=STATE, rules={**RULES, "LIQUIDATION_STRESS_SHORT": {"status": "NOT_EVALUABLE"}},
                      d7=False, evidence=[])
    assert (c["i1h"], c["r1h"], c["gate"], c["liq"], c["d7"], c["ev"]) == ("?", "?", "?", "?", "off", "")
    assert sg.tail_states(c) == []


def test_liquidation_votes_and_signature_identity():
    both = {"LIQUIDATION_STRESS_LONG": {"status": "QUALIFIES"}, "LIQUIDATION_STRESS_SHORT": {"status": "QUALIFIES"}}
    assert sg._liq(both) == "both" and sg._liq({}) == "?" and sg._liq(None) == "?"
    assert sg._liq({"LIQUIDATION_STRESS_LONG": {"status": "NOT_QUALIFIES"},
                    "LIQUIDATION_STRESS_SHORT": {"status": "NOT_QUALIFIES"}}) == "none"
    comp = {k: "x" for k in sg.COMPONENTS}
    key = sg.signature_key(comp)
    assert key.startswith("i1h=x|i4h=x|") and key.endswith("|day=x")
    assert sg.signature_id(key) == sg.signature_id(key) and len(sg.signature_id(key)) == 8
    assert sg.signature_id(key) != sg.signature_id(sg.signature_key({**comp, "d7": "on"}))


def test_evidence_counts_only_for_the_bucket_it_describes():
    close = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
    ev = {"as_of": "2026-10-06T09:01:00Z", "matches": [{"finding_id": "D2"}, {"finding_id": "H01"}]}
    assert sg._evidence_ids(ev, close) == ["D2", "H01"]
    assert sg._evidence_ids(ev, close + timedelta(minutes=5)) is None          # another bucket
    assert sg._evidence_ids({**ev, "as_of": "2026-10-06T09:20:00Z"}, close) is None    # too old for it
    assert sg._evidence_ids({**ev, "error_type": "Timeout"}, close) is None
    assert sg._evidence_ids({"as_of": "2026-10-06T09:01:00Z", "matches": []}, close) == []


def _stat(key, tail, eps, days, n=10):
    return {"key": key, "sig_id": key[:8].ljust(8, "0"), "components": {k: "x" for k in sg.COMPONENTS},
            "tail_count": tail, "n_episodes": eps, "n_days": days, "n_buckets": n}


def test_the_new_rule_is_the_decision_s_and_reviewed_signatures_leave_it():
    stats = [_stat("aaaaaaaa", 2, 3, 2), _stat("bbbbbbbb", 1, 9, 9), _stat("cccccccc", 3, 2, 5),
             _stat("dddddddd", 4, 5, 1), _stat("eeeeeeee", 5, 4, 3)]
    idx = sg.index_rows(stats, reviewed=["eeeeeeee"], total=1000)
    assert [r["key"] for r in idx["new"]] == ["aaaaaaaa"]
    assert [r["key"] for r in idx["reviewed"]] == ["eeeeeeee"]
    assert idx["new"][0]["frequency"] == 0.01


def test_the_owner_text_is_blind_and_names_the_review_commands():
    stats = [_stat("aaaaaaaa", 2, 3, 2, n=37)]
    summary = {"total": 8800, "signatures": 41, "first_bucket": datetime(2026, 10, 1, tzinfo=UTC)}
    text = sg.format_index(summary, sg.index_rows(stats, [], total=8800), pins=[], reviews=[])
    assert "[aaaaaaaa] 0.42% of buckets (N 37 of 8800) · 3 episodes · 2 days · tail 2" in text
    assert "/hypotheses research <id> <hypothesis text>" in text and "what followed is not shown" in text
    for word in ("after", "then", "returned", "outcome", "hit"):
        assert word not in text.lower().replace("what followed is not shown", "")


def test_export_is_shaped_for_the_atlas_exposure_ledger():
    at = datetime(2026, 10, 6, 7, 0, tzinfo=UTC)
    review = {"sig_id": "aaaaaaaa", "version": sg.SIGNATURE_VERSION, "decision": "RESEARCH",
              "hypothesis": "OI build-up with quiet range precedes wider 4h ranges", "components": {"d7": "on"},
              "decided_at": at, "window_from": at - timedelta(days=3), "window_to": at, "seen": {"n_buckets": 37}}
    out = sg.export_reviews([review])[0]
    assert out["exposure_entry"]["status"] == "EXPOSED" and out["exposure_entry"]["period"] == "2026-10-03..2026-10-06"
    assert out["window"] == [(at - timedelta(days=3)).isoformat(), at.isoformat()]
    assert out["seen_at_review"] == {"n_buckets": 37}
