"""HISTORICAL_FOLLOW_UP_V0 + EVENT_COMPARABILITY_V0 (pure, deterministic, offline)."""
import copy
import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from beta import comparability as comp
from beta.comparability import (ComparabilityError, EVENT_RULE_KEYS, comparability_payload,
                                episode_comparability, event_comparability)
from beta.config import (BetaConfig, EVENT_TYPES, LIQUIDATION_STRESS_LONG, POSITION_BUILDUP_COMPRESSION,
                         PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY,
                         TAKER_FLOW_EXTREME_SELL)
from beta.formatter import assert_descriptive
from beta.followup import (DISPLAY_SUFFICIENCY, FOLLOW_UP_HORIZONS, LIVE_OBSERVED,
                           RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA, ControlCandidate, EpisodeWindow,
                           EventObservation, FollowUpError, Outcome, assert_follow_up_wording,
                           format_historical_follow_up, prior_1h_realized_range_pct,
                           select_ordinary_controls, summarize, summary_json, volatility_tercile)
from beta.state_tape import PERCENTILE_HISTORY_SCHEMA_VERSIONS

UTC = timezone.utc
CFG = BetaConfig.load()
CALC = "0123456789abcdef"
ID = event_comparability(CFG, event_type=PRICE_OI_CONTRACTION_DOWN, calculation_version=CALC)
PINNED_DOWN_DIGEST = "e0a3a5a1494c8eb9e0ac753103faa71a79f6ef3155b342b6fe4b5a3ac06c4a7b"
D0 = datetime(2026, 8, 1, tzinfo=UTC)
AS_OF = datetime(2026, 10, 1, tzinfo=UTC)
OV = "BETA_OUTCOME_V1"


def cfg_with(**rule_changes):
    """rule_changes: family -> {key: value}."""
    from common.versioning import _to_plain
    raw = _to_plain(CFG.raw)
    for fam, kv in rule_changes.items():
        raw["rules"][fam].update(kv)
    return BetaConfig.from_mapping(raw)


def digest(cfg=CFG, et=PRICE_OI_CONTRACTION_DOWN, calc=CALC, schema=None):
    return event_comparability(cfg, event_type=et, calculation_version=calc, state_schema_version=schema).digest


def outc(r1, r4, status="COMPLETE", ov=OV, extra=None):
    o = {"1h": Outcome(status, r1, ov), "4h": Outcome(status, r4, ov)}
    o.update(extra or {})
    return o


def ev(i, anchor, r1=1.0, r4=2.0, prov=LIVE_OBSERVED, tercile=1, dg=None, outcomes=None):
    return EventObservation(event_id=f"EV-{i:010d}", comparability_digest=dg or ID.digest, anchor=anchor,
                            provenance=prov, outcomes=outcomes or outc(r1, r4), prior_1h_tercile=tercile)


def window(e):
    return EpisodeWindow(start=e.anchor - timedelta(minutes=10), end=e.anchor)


def cand(anchor, r1=0.5, r4=1.0, prov=LIVE_OBSERVED, evaluable=True, tercile=1, status="COMPLETE"):
    return ControlCandidate(anchor=anchor, provenance=prov, evaluable=evaluable,
                            outcomes=outc(r1, r4, status=status), prior_1h_tercile=tercile)


def at(day, hour, minute=0):
    return D0 + timedelta(days=day, hours=hour, minutes=minute)


def events_over(n_events, n_days, first_day=40):
    out = []
    for i in range(n_events):
        out.append(ev(i, at(first_day + i % n_days, 10, 5 * (i // n_days)), r1=1.0 + i / 10, r4=2.0 + i / 10))
    return out


def daily_candidates(days=range(0, 60), hours=(9, 10, 11), minutes=(0, 5, 10, 15, 20, 25), r1=0.5, r4=1.0,
                     tercile=1):
    return [cand(at(d, h, m), r1=r1, r4=r4, tercile=tercile) for d in days for h in hours for m in minutes]


def run(events, candidates=(), windows=None, **kw):
    windows = [window(e) for e in events] if windows is None else windows
    return summarize(ID, events, list(candidates), windows, as_of=kw.pop("as_of", AS_OF), **kw)


def walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from walk(v)
    else:
        yield obj


# 1-7: comparability identity ------------------------------------------------------------
def test_comparability_digest_is_stable_and_order_independent():
    assert ID.digest == PINNED_DOWN_DIGEST == digest()
    raw = json.loads(json.dumps({k: (dict(v) if hasattr(v, "items") else v) for k, v in CFG.raw.items()},
                                default=lambda o: dict(o) if hasattr(o, "items") else list(o)))
    reordered = dict(reversed(list(raw.items())))
    reordered["rules"] = {k: dict(reversed(list(v.items()))) for k, v in reversed(list(raw["rules"].items()))}
    reordered["active_exchanges"] = list(reversed(raw["active_exchanges"]))
    assert digest(BetaConfig.from_mapping(reordered)) == PINNED_DOWN_DIGEST
    assert ID.payload["comparability_version"] == "EVENT_COMPARABILITY_V0"


def test_integer_and_float_percentile_thresholds_are_the_same_semantics():
    a = cfg_with(TAKER_FLOW_EXTREME={"buy_percentile_min": 1})
    b = cfg_with(TAKER_FLOW_EXTREME={"buy_percentile_min": 1.0})
    assert digest(a, TAKER_FLOW_EXTREME_BUY) == digest(b, TAKER_FLOW_EXTREME_BUY)


def test_state_schema_and_presentation_only_changes_keep_comparability():
    v1 = CFG.with_overrides(state_schema_version=1)
    assert v1.rules_digest != CFG.rules_digest                      # rules_digest DID change (V1 -> V2)
    for et in EVENT_TYPES:
        assert digest(v1, et) == digest(CFG, et)                    # comparability did not
        assert episode_comparability(v1, event_type=et, rules_digest=v1.rules_digest,
                                     calculation_version=CALC).digest == digest(CFG, et)
    ctx = dict(CFG["context"]); ctx["last_event_retention_min"] = 240
    for changed in (CFG.with_overrides(context=ctx), CFG.with_overrides(same_event_cooldown_min=90),
                    CFG.with_overrides(delivery_ttl_s=900), CFG.with_overrides(max_new_pushes_per_utc_day=9),
                    CFG.with_overrides(forward_horizons=["1h", "4h"]), CFG.with_overrides(enabled=True),
                    CFG.with_overrides(bucket_close_grace_s=30)):
        assert changed.config_digest != CFG.config_digest
        assert all(digest(changed, et) == digest(CFG, et) for et in EVENT_TYPES)


def test_the_repo_tape_equivalence_supports_the_feature_semantics_map():
    for version, history in PERCENTILE_HISTORY_SCHEMA_VERSIONS.items():
        assert {comp.DETECTOR_FEATURE_SEMANTICS[v] for v in history} == {comp.DETECTOR_FEATURE_SEMANTICS[version]}


def test_threshold_change_resets_comparability_but_only_for_the_event_that_reads_it():
    assert digest(cfg_with(PRICE_OI_CONTRACTION_DOWN={"price_move_pct_median_max": 0.04})) != ID.digest
    assert digest(cfg_with(PRICE_OI_CONTRACTION_DOWN={"oi_change_pct_median_max": 0.2})) != ID.digest
    sell = cfg_with(TAKER_FLOW_EXTREME={"sell_percentile_max": 0.01})
    assert digest(sell, TAKER_FLOW_EXTREME_SELL) != digest(CFG, TAKER_FLOW_EXTREME_SELL)
    assert digest(sell, TAKER_FLOW_EXTREME_BUY) == digest(CFG, TAKER_FLOW_EXTREME_BUY)
    assert digest(cfg_with(PRICE_OI_CONTRACTION_UP={"price_move_pct_median_min": 0.9})) == ID.digest


@pytest.mark.parametrize("family,key,et", [
    ("PRICE_OI_CONTRACTION_DOWN", "triggered_at_streak", PRICE_OI_CONTRACTION_DOWN),
    ("POSITION_BUILDUP_COMPRESSION", "max_duration_min", POSITION_BUILDUP_COMPRESSION),
    ("POSITION_BUILDUP_COMPRESSION", "early_at_streak", POSITION_BUILDUP_COMPRESSION),
    ("LIQUIDATION_STRESS", "triggered_at_streak", LIQUIDATION_STRESS_LONG)])
def test_streak_or_duration_change_resets_comparability(family, key, et):
    r = CFG.rule(family)
    changed = {key: r[key] + 1}
    if key == "triggered_at_streak" and family == "LIQUIDATION_STRESS":
        changed = {key: r[key] + 1}
    if key == "early_at_streak":
        changed = {key: r[key] - 1} if r[key] > 1 else {"armed_at_streak": r["armed_at_streak"] + 1,
                                                        "triggered_at_streak": r["triggered_at_streak"] + 1}
    if key == "max_duration_min":
        changed = {key: r[key] + 30}
    assert digest(cfg_with(**{family: changed}), et) != digest(CFG, et)


def test_stage2_feature_semantic_change_resets_comparability(monkeypatch):
    assert digest(calc="fedcba9876543210") != ID.digest
    with pytest.raises(ComparabilityError):
        digest(calc="UNMATERIALIZED")
    with pytest.raises(ComparabilityError):
        digest(schema=3)                                        # unknown semantics: fail closed
    monkeypatch.setattr(comp, "DETECTOR_FEATURE_SEMANTICS",
                        {1: "BETA_TAPE_DETECTOR_FEATURES_V1", 2: "BETA_TAPE_DETECTOR_FEATURES_V1",
                         3: "BETA_TAPE_DETECTOR_FEATURES_V2"})
    assert digest(schema=3) != digest(schema=2) == digest(schema=1)
    for gate in (dict(min_venue_coverage=3), dict(active_exchanges=["binance", "okx"]), dict(max_state_age_s=600)):
        assert digest(CFG.with_overrides(**gate)) != ID.digest


def test_outcome_version_change_resets_comparability():
    assert digest(CFG.with_overrides(outcome_version="BETA_OUTCOME_V2")) != ID.digest


def test_different_event_types_never_compare():
    ds = {et: digest(CFG, et) for et in EVENT_TYPES}
    assert len(set(ds.values())) == len(EVENT_TYPES) and set(EVENT_RULE_KEYS) == set(EVENT_TYPES)
    events = events_over(12, 6)
    up = [ev(100 + i, e.anchor, dg=ds[PRICE_OI_CONTRACTION_UP]) for i, e in enumerate(events)]
    s = run(up)
    assert s["user_facing"]["events"]["count"] == 0 and s["details"]["excluded_events"] == {"NOT_COMPARABLE": 12}


def test_episode_identity_requires_the_producing_configuration():
    with pytest.raises(ComparabilityError):
        episode_comparability(CFG, event_type=PRICE_OI_CONTRACTION_DOWN, rules_digest="0" * 64,
                              calculation_version=CALC)
    with pytest.raises(ComparabilityError):
        comparability_payload(CFG, event_type="LEVEL_SWEEP", calculation_version=CALC, state_schema_version=2)


# 8-11: sufficiency and the event statistic -----------------------------------------------
def _no_statistics(s):
    u = s["user_facing"]
    assert u["event_range_median_pct"] is None and u["ordinary_same_time_baseline"] is None \
        and u["volatility_matched"] is None
    floats = [x for x in walk(u) if isinstance(x, float)]
    assert floats == []
    text = format_historical_follow_up(s)
    assert "%" not in text and "median" not in text and "baseline" not in text
    return text


def test_fewer_than_ten_events_hides_every_number():
    s = run(events_over(9, 9), daily_candidates())
    assert s["user_facing"]["events"] == {"count": 9, "distinct_utc_dates": 9, "display_eligible": False,
                                          "not_eligible_reason": "INSUFFICIENT_EVENTS"}
    text = _no_statistics(s)
    assert text == ("<b>HISTORICAL FOLLOW-UP</b>\nLimited comparable history\n9 events across 9 days\n"
                    "More history is being collected")


def test_ten_events_on_fewer_than_five_dates_hides_every_number():
    s = run(events_over(10, 4), daily_candidates())
    assert s["user_facing"]["events"]["not_eligible_reason"] == "INSUFFICIENT_UTC_DATES"
    assert s["user_facing"]["events"]["distinct_utc_dates"] == 4
    _no_statistics(s)
    assert (DISPLAY_SUFFICIENCY.min_events, DISPLAY_SUFFICIENCY.min_utc_dates) == (10, 5)


def test_eligible_sample_exposes_the_event_median_and_the_median_is_exact_for_odd_and_even_n():
    even = run(events_over(12, 6))
    assert even["user_facing"]["events"]["display_eligible"] is True
    r1 = sorted(1.0 + i / 10 for i in range(12))
    assert even["user_facing"]["event_range_median_pct"]["1h"] == pytest.approx((r1[5] + r1[6]) / 2)
    odd = run(events_over(11, 6))
    assert odd["user_facing"]["event_range_median_pct"]["4h"] == pytest.approx(sorted(2.0 + i / 10 for i in range(11))[5])


# 12-14: ordinary baseline -------------------------------------------------------------------
def test_ordinary_baseline_excludes_plus_minus_four_hours_of_any_episode():
    e = ev(1, at(40, 10))
    cands = {c.anchor: c for c in daily_candidates(days=range(5, 40), hours=(10,), minutes=(0,))}
    other = EpisodeWindow(start=at(35, 13, 55), end=at(35, 14, 30))      # 10:00 on day 35 is 3h55m before it
    later = EpisodeWindow(start=at(34, 3), end=at(34, 6))                # 10:00 on day 34 is exactly 4h after it
    fine = EpisodeWindow(start=at(33, 3), end=at(33, 5, 55))             # 4h05m after -> not excluded
    chosen = select_ordinary_controls(e, cands, [window(e), other, later, fine], outcome_version=OV,
                                      provenances=(LIVE_OBSERVED,))
    days = {(c.anchor - D0).days for c in chosen}
    assert 35 not in days and 34 not in days and 33 in days


def test_ordinary_baseline_uses_one_same_slot_control_per_previous_date():
    e = ev(1, at(40, 10, 5))
    every5 = {c.anchor: c for c in daily_candidates(days=range(0, 41), hours=tuple(range(24)),
                                                     minutes=tuple(range(0, 60, 5)))}
    chosen = select_ordinary_controls(e, every5, [window(e)], outcome_version=OV, provenances=(LIVE_OBSERVED,))
    assert len(chosen) == 30
    assert len({c.anchor.date() for c in chosen}) == 30
    assert all((c.anchor.hour, c.anchor.minute) == (10, 5) for c in chosen)


def test_ordinary_baseline_never_uses_future_or_same_day_data():
    events = events_over(12, 6)
    base = daily_candidates(days=range(0, 40), hours=(10,), minutes=(0, 5, 10))
    s1 = run(events, base)
    future = daily_candidates(days=range(40, 60), hours=(10,), minutes=(0, 5, 10), r1=99.0, r4=99.0)
    s2 = run(events, base + future)
    assert s1["user_facing"]["ordinary_same_time_baseline"] == s2["user_facing"]["ordinary_same_time_baseline"]
    e = events[-1]
    cands = {c.anchor: c for c in base + future}
    chosen = select_ordinary_controls(e, cands, [window(x) for x in events], outcome_version=OV,
                                      provenances=(LIVE_OBSERVED,))
    assert chosen and all(c.anchor.date() < e.anchor.date() and c.anchor + timedelta(hours=4) <= e.anchor
                          for c in chosen)


# 15-17: volatility-matched baseline ---------------------------------------------------------
def _bars(start, minutes, ex=("binance", "bybit"), hi=101.0, lo=99.0):
    return [{"exchange": x, "ts": start + timedelta(minutes=i), "open": 100.0, "high": hi, "low": lo, "close": 100.0}
            for i in range(minutes) for x in ex]


def test_prior_volatility_uses_only_information_before_the_anchor():
    anchor = at(40, 10)
    before = _bars(anchor - timedelta(hours=1), 60)
    after = _bars(anchor, 240, hi=150.0, lo=50.0)
    v = prior_1h_realized_range_pct(anchor=anchor, reference_price=100.0, exchanges=("binance", "bybit"),
                                    klines=before)
    assert v == pytest.approx(2.0)
    assert prior_1h_realized_range_pct(anchor=anchor, reference_price=100.0, exchanges=("binance", "bybit"),
                                       klines=before + after) == v
    assert prior_1h_realized_range_pct(anchor=anchor, reference_price=100.0, exchanges=("binance", "bybit"),
                                       klines=before[:-2]) is None             # incomplete -> no tercile
    ref = [(anchor - timedelta(minutes=5 * (i + 1)), float(i % 30)) for i in range(3000)]
    t = volatility_tercile(anchor=anchor, value=5.0, reference=ref)
    poisoned = ref + [(anchor + timedelta(minutes=5 * i), 1000.0) for i in range(5000)] + [(anchor, 1000.0)]
    assert t == volatility_tercile(anchor=anchor, value=5.0, reference=poisoned) == 0
    assert volatility_tercile(anchor=anchor, value=5.0, reference=ref[:100]) is None


def test_volatility_matching_never_relaxes_hour_or_tercile():
    events = [ev(i, e.anchor, tercile=2) for i, e in enumerate(events_over(12, 6))]
    wrong_tercile = daily_candidates(tercile=1)
    wrong_hour = daily_candidates(hours=(7, 13, 14), tercile=2)
    s = run(events, wrong_tercile + wrong_hour)
    m = s["user_facing"]["volatility_matched"]
    assert m["count"] == 0 and m["display_eligible"] is False and "by_horizon" not in m
    assert all(v == [] for v in s["details"]["matched"]["controls"].values())
    s_ok = run(events, wrong_tercile + wrong_hour + daily_candidates(hours=(11,), minutes=(30, 35, 40), tercile=2))
    assert all(len(v) == 5 for v in s_ok["details"]["matched"]["controls"].values())
    for e_id, anchors in s_ok["details"]["matched"]["controls"].items():
        assert all(a[11:13] == "11" for a in anchors)


def test_matched_controls_are_without_replacement_and_the_sign_count_is_exact():
    events = events_over(12, 6)
    # Controls: range 1.5 at 1h / 2.5 at 4h. Events: 1h 1.0..2.1 and 4h 2.0..3.1 -> 6 of 12 above at each.
    cands = daily_candidates(r1=1.5, r4=2.5)
    s = run(events, cands)
    m = s["user_facing"]["volatility_matched"]
    assert m["display_eligible"] is True
    ranges1 = [1.0 + i / 10 for i in range(12)]
    ranges4 = [2.0 + i / 10 for i in range(12)]
    assert m["by_horizon"]["1h"]["event_above_baseline_count"] == sum(r > 1.5 for r in ranges1) == 6
    assert m["by_horizon"]["4h"]["event_above_baseline_count"] == sum(r > 2.5 for r in ranges4) == 6
    assert m["by_horizon"]["1h"]["comparisons"] == 12
    diffs = sorted(r - 1.5 for r in ranges1)
    assert m["by_horizon"]["1h"]["median_difference_pct_points"] == pytest.approx((diffs[5] + diffs[6]) / 2)
    used = [a for v in s["details"]["matched"]["controls"].values() for a in v]
    assert len(used) == len(set(used))


# 18-21: completeness, horizons, fields, provenance ------------------------------------------
def test_incomplete_or_foreign_outcomes_are_excluded():
    events = events_over(12, 6)
    bad = [ev(200, at(46, 10), outcomes=outc(1.0, None, status="INCOMPLETE_DATA")),
           ev(201, at(46, 11), outcomes={"1h": Outcome("COMPLETE", 1.0, OV),
                                        "4h": Outcome("REFERENCE_UNAVAILABLE", None, OV)}),
           ev(202, at(46, 12), outcomes=outc(1.0, 2.0, ov="BETA_OUTCOME_V2")),
           ev(203, AS_OF - timedelta(hours=3))]
    s = run(events + bad)
    assert s["user_facing"]["events"]["count"] == 12
    assert s["details"]["excluded_events"] == {"NOT_MATURED": 1, "OUTCOME_NOT_COMPLETE": 3}


def test_only_the_1h_and_4h_horizons_reach_the_summary():
    extra = {"15m": Outcome("COMPLETE", 9.0, OV), "24h": Outcome("COMPLETE", 9.0, OV)}
    events = [ev(i, e.anchor, outcomes=outc(1.0, 2.0, extra=extra)) for i, e in enumerate(events_over(12, 6))]
    s = run(events, daily_candidates())
    u = s["user_facing"]
    assert u["horizons"] == ["1h", "4h"] == list(FOLLOW_UP_HORIZONS)
    assert set(u["event_range_median_pct"]) == {"1h", "4h"}
    assert set(u["volatility_matched"]["by_horizon"]) == {"1h", "4h"}
    assert not {"15m", "30m", "24h"} & set(x for x in walk(u) if isinstance(x, str))


def test_no_directional_field_appears_in_the_user_facing_structure_or_text():
    s = run(events_over(12, 6), daily_candidates())
    forbidden = ("close_return", "max_up", "max_down", "time_to_max", "return", "direction")
    for x in walk(s["user_facing"]):
        if isinstance(x, str):
            assert not any(f in x for f in forbidden)
    text = format_historical_follow_up(s)
    assert not any(f.replace("_", " ") in text.lower() or f in text.lower() for f in forbidden)


def test_provenance_classes_stay_distinguishable():
    events = events_over(12, 6)
    mixed = [ev(i, e.anchor, prov=RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA if i % 3 == 0 else LIVE_OBSERVED)
             for i, e in enumerate(events)]
    s = run(mixed, daily_candidates())
    assert s["details"]["event_provenance"] == {LIVE_OBSERVED: 8, RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA: 4}
    live_only = run(mixed, daily_candidates(), provenances=(LIVE_OBSERVED,))
    assert live_only["details"]["excluded_events"] == {"PROVENANCE_NOT_INCLUDED": 4}
    assert live_only["details"]["event_provenance"][RECONSTRUCTED_FROM_LIVE_COLLECTED_RAW_DATA] == 0
    with pytest.raises(FollowUpError):
        run([ev(1, at(40, 10), prov="OBSERVED")])


# 22-24: formatter, wording, determinism ------------------------------------------------------
def test_formatter_is_descriptive_for_every_branch():
    eligible = run(events_over(14, 8), daily_candidates(r1=0.55, r4=1.31))
    text = format_historical_follow_up(eligible)
    assert assert_descriptive(text) == text
    assert text.startswith("<b>HISTORICAL FOLLOW-UP</b>\n14 comparable events · 8 days\n\nAfter previous events:\n1h range · median ")
    assert "Ordinary same-time baseline:\n1h · 0.55%\n4h · 1.31%" in text
    assert "Matched for prior volatility:\n1h range exceeded matched baseline in " in text
    limited = run(events_over(6, 3))
    assert format_historical_follow_up(limited) == ("<b>HISTORICAL FOLLOW-UP</b>\nLimited comparable history\n"
                                                    "6 events across 3 days\nMore history is being collected")
    no_controls = run(events_over(12, 6))
    t = format_historical_follow_up(no_controls)
    assert t.count("limited comparable history") == 2 and assert_descriptive(t)


@pytest.mark.parametrize("phrase", ["Next 1h range", "expected range", "forecast", "predicted", "likely",
                                    "probability", "edge", "signal", "LONG", "short squeeze", "price will rise",
                                    "moved up", "p-value 0.03", "statistically significant"])
def test_forbidden_directional_or_predictive_wording_is_rejected(phrase):
    with pytest.raises(ValueError):
        assert_follow_up_wording(f"<b>HISTORICAL FOLLOW-UP</b>\n{phrase}")


def test_formatter_refuses_a_foreign_or_tampered_summary():
    s = copy.deepcopy(run(events_over(12, 6)))
    s["user_facing"]["horizons"] = ["1h", "4h", "24h"]
    with pytest.raises(FollowUpError):
        format_historical_follow_up(s)


def test_the_same_inputs_give_a_byte_identical_summary():
    events, cands = events_over(12, 6), daily_candidates(r1=1.5, r4=2.5)
    a = summary_json(run(events, cands))
    shuffled_e, shuffled_c = events[:], cands[:]
    random.Random(7).shuffle(shuffled_e)
    random.Random(8).shuffle(shuffled_c)
    b = summary_json(run(shuffled_e, shuffled_c))
    assert a == b and a.encode() == summary_json(run(events, cands)).encode()
    assert json.loads(a)["summary_digest"] == run(events, cands)["summary_digest"]
