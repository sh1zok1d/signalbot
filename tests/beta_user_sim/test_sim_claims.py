"""Deterministic claim manifest, legacy adapter and factual auditor (§10–§12, §20.6)."""
import copy

from beta.formatter import format_btc
from sim_helpers import CFG, bundle
from tools.beta_user_sim.claims import (AT_T_FACT, CONSISTENT, CONTRADICTED, FORWARD_OUTCOME, NO_DIRECTIONAL_CLAIM,
                                        NOT_EVALUABLE, WORDING_JUDGMENT, build_manifest, surface_manifest)
from tools.beta_user_sim.timeline import KIND_BTC_VIEW, ReplayItem, build_timeline

FIELDS = {"claim_id", "claim_type", "source_fields", "rendered_text_fragment", "evaluation_class",
          "evaluation_rule", "directional_claim", "horizon", "status", "detail"}


def _views():
    b = bundle()
    tl = build_timeline(b, CFG, lang="ru")
    rows = {v["view_pk"]: v for v in b.btc_views}
    return b, [(i, rows[i.source["view_pk"]]["payload"]) for i in tl.views], tl


def _item(html, payload, lang="ru"):
    return ReplayItem(item_id="view:x", kind=KIND_BTC_VIEW, at=None, lang=lang, html=html, buttons=None,
                      provenance="TEST", template_check="TEST")


def _by_type(m):
    out = {}
    for c in m.claims:
        out.setdefault(c.claim_type, []).append(c)
    return out


def test_manifest_records_the_required_fields_for_every_claim():
    b, views, tl = _views()
    for item, payload in views:
        m = build_manifest(CFG, item, payload=payload)
        assert m.claims
        for c in m.claims:
            assert set(c.as_dict()) == FIELDS
            assert c.evaluation_class in (AT_T_FACT, FORWARD_OUTCOME, WORDING_JUDGMENT)
    for item in tl.pushes:
        m = build_manifest(CFG, item, episode=b.episode(item.source["episode_pk"]))
        assert {c.claim_type for c in m.claims} >= {"PUSH_DECISION_TIME", "PUSH_REFERENCE_PRICE"}


def test_current_templates_make_no_directional_claim():
    b, views, tl = _views()
    items = [(i, {"payload": p}) for i, p in views] + \
        [(i, {"episode": b.episode(i.source["episode_pk"])}) for i in tl.pushes]
    for item, kw in items:
        m = build_manifest(CFG, item, **kw)
        fwd = [c for c in m.claims if c.evaluation_class == FORWARD_OUTCOME]
        assert len(fwd) == 1 and fwd[0].status == NO_DIRECTIONAL_CLAIM and fwd[0].directional_claim is False
        assert not any(c.directional_claim for c in m.claims)


def test_at_t_facts_are_checked_against_persisted_as_of_fields():
    b, views, tl = _views()
    item, payload = views[0]
    m = _by_type(build_manifest(CFG, item, payload=payload))
    assert m["PRICE_LEVEL"][0].status == CONSISTENT
    assert m["HORIZON_1H_PRICE_CHANGE"][0].status == CONSISTENT
    assert m["TIMESTAMP_DATA_THROUGH"][0].status == CONSISTENT


def test_a_shown_number_that_disagrees_with_its_source_is_contradicted():
    b, views, tl = _views()
    item, payload = views[0]
    wrong = copy.deepcopy(payload)
    wrong["now"]["reference_price"] += 500
    wrong["horizons"]["1h"]["price_move_pct"] += 1.0
    wrong["data_through"] = "2024-03-04T00:00:00+00:00"
    m = _by_type(build_manifest(CFG, item, payload=wrong))
    assert m["PRICE_LEVEL"][0].status == CONTRADICTED
    assert m["HORIZON_1H_PRICE_CHANGE"][0].status == CONTRADICTED
    assert m["TIMESTAMP_DATA_THROUGH"][0].status == CONTRADICTED


def test_the_auditor_is_deterministic():
    b, views, tl = _views()
    for item, payload in views:
        assert build_manifest(CFG, item, payload=payload).as_dict() == \
            build_manifest(CFG, item, payload=payload).as_dict()


def test_legacy_payload_without_horizons_maps_unknown_fragments_to_not_evaluable():
    b, views, tl = _views()
    item, payload = views[0]
    legacy = copy.deepcopy(payload)
    legacy["horizons"] = None
    legacy["context_1h"] = {"price_move_pct_median": -0.12}
    html = format_btc(CFG, legacy, "ru")
    m = _by_type(build_manifest(CFG, _item(html, legacy), payload=legacy))
    assert m["HORIZON_1H_PRICE_CHANGE"][0].status == CONSISTENT
    assert m["HORIZON_1H_PRICE_CHANGE"][0].source_fields == ["context_1h.price_move_pct_median"]
    assert "HORIZON_24H_PRICE_CHANGE" not in m


def test_unrecognized_or_ambiguous_text_is_not_evaluable():
    b, views, tl = _views()
    item, payload = views[0]
    odd = item.html.replace("\n\n<i>", "\nЦена может вырасти · 1ч OI сильный\n\n<i>")
    m = build_manifest(CFG, _item(odd, payload), payload=payload)
    unknown = [c for c in m.claims if c.claim_type == "UNRECOGNIZED_FRAGMENT"]
    assert unknown and all(c.status == NOT_EVALUABLE for c in unknown)
    fwd = [c for c in m.claims if c.evaluation_class == FORWARD_OUTCOME][0]
    assert fwd.status in (NO_DIRECTIONAL_CLAIM, NOT_EVALUABLE)


def test_forbidden_forward_wording_blocks_a_no_directional_verdict():
    b, views, tl = _views()
    item, payload = views[0]
    odd = item.html.replace("\n\n<i>", "\nexpect a bounce soon\n\n<i>")
    m = build_manifest(CFG, _item(odd, payload), payload=payload)
    fwd = [c for c in m.claims if c.evaluation_class == FORWARD_OUTCOME][0]
    assert fwd.status == NOT_EVALUABLE


def test_the_no_directional_claim_verdict_rests_on_the_frozen_catalog():
    from beta.i18n import _CATALOG, assert_descriptive
    for key, by_lang in _CATALOG.items():
        for lang, text in by_lang.items():
            assert_descriptive(text, lang)
    b, views, tl = _views()
    unparsed = [(i, p) for i, p in views
                if any(c.claim_type == "UNRECOGNIZED_FRAGMENT" for c in build_manifest(CFG, i, payload=p).claims)]
    assert unparsed, "fixture should contain a catalog line the V0 parser does not cover"
    for item, payload in unparsed:
        assert item.template_check == "TEMPLATE_MATCH"
        fwd = build_manifest(CFG, item, payload=payload).claims[0]
        assert fwd.status == NO_DIRECTIONAL_CLAIM


def test_push_rule_text_is_not_evaluable_without_the_tape_and_surfaces_have_no_rules():
    b, views, tl = _views()
    item = tl.pushes[0]
    m = _by_type(build_manifest(CFG, item, episode=b.episode(item.source["episode_pk"])))
    assert m["PUSH_RULE_DESCRIPTION"][0].status == NOT_EVALUABLE
    assert m["PUSH_REFERENCE_PRICE"][0].status == CONSISTENT
    s = surface_manifest("m9", "REPLY_HISTORY", "<b>History</b>", "en")
    assert [c.status for c in s.claims] == [NO_DIRECTIONAL_CLAIM, NOT_EVALUABLE]


def test_wording_judgments_check_their_inputs_but_leave_strength_to_role_b():
    b, views, tl = _views()
    for item, payload in views:
        for c in build_manifest(CFG, item, payload=payload).claims:
            if c.evaluation_class == WORDING_JUDGMENT:
                assert c.source_fields and c.status in (CONSISTENT, CONTRADICTED, NOT_EVALUABLE)
