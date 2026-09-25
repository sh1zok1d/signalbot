"""Temporal context V0: episodization (confirmation x phase), hysteresis, running peak,
rolling 1h, labels, determinism and replay — pure, no DB, no forward data."""
import copy
import math
from datetime import datetime, timedelta, timezone

import pytest

from beta import context as cx
from beta.config import (BetaConfig, LIQUIDATION_STRESS_LONG, POSITION_BUILDUP_COMPRESSION,
                         PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP, TAKER_FLOW_EXTREME_BUY,
                         TAKER_FLOW_EXTREME_SELL)
from beta.detector import BucketContext, step_episode
from beta.models import ARMED, EARLY, TRIGGERED
from beta.rules import evaluate_bucket
from beta.state_tape import BUCKET, metric_key

CFG = BetaConfig.load()
EXS = CFG.exchanges
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
NEUTRAL = {"price": 0.5, "oi": 0.5, "range": 0.5, "volume": 0.5, "taker": 0.5}


def snap(ranks=None, values=None, *, fresh=True, venue_signs=None, liq=None, contributing=EXS):
    """A materialized tape snapshot with mature percentiles. `ranks` override NEUTRAL."""
    r = {**NEUTRAL, **(ranks or {})}
    v = {"price": (r["price"] - 0.5) * 2, "oi": (r["oi"] - 0.5) * 4, "range": r["range"],
         "volume": 1e6 * (1 + r["volume"]), "taker": (r["taker"] - 0.5) * 1e7, **(values or {})}
    keys = {"price": "c:price_move_pct_median", "oi": "c:oi_change_pct_median",
            "range": "c:range_width_pct_median", "volume": "c:volume_notional_usd_sum",
            "taker": "c:taker_delta_notional_usd_sum"}
    metrics = {keys[k]: v[k] for k in keys}
    pct = {keys[k]: {"value": v[k], "rank": r[k], "tier": "mature"} for k in keys}
    signs = venue_signs or {}
    for ex in EXS:
        for f, base in (("price_move_pct", v["price"]), ("oi_change_pct", v["oi"]),
                        ("taker_delta_notional_usd", v["taker"])):
            metrics[metric_key(ex, f)] = signs.get(f, {}).get(ex, base)
        for side in ("long_liquidation_notional", "short_liquidation_notional"):
            val, rank = (liq or {}).get((ex, side), (None, None))
            metrics[metric_key(ex, side)] = val
            pct[metric_key(ex, side)] = {"value": val, "rank": rank, "tier": "mature" if rank is not None else None}
    fam = {"available": len(contributing), "expected": 3, "contributing": list(contributing),
           "usable": len(contributing) >= 2}
    return {"materialized": True, "evaluation_fresh": fresh, "stale_barrier": False,
            "metrics": metrics, "percentiles": pct,
            "families": {f: dict(fam) for f in ("price_structure", "oi", "volume", "taker_flow")},
            "venues": {ex: {"declared_available": True, "heartbeat_healthy": True} for ex in EXS},
            "reference": {"status": "OK", "price": 83500.0, "exchanges": list(EXS), "dispersion_pct": 0.01}}


def tape(snaps, cfg=CFG, start=T0):
    """Attach real rule evaluations (streaks chained exactly like the detector)."""
    rows, prev = {}, None
    for i, s in enumerate(snaps):
        b = start + i * BUCKET
        if s is None:
            rows[b], prev = None, None
            continue
        s = copy.deepcopy(s)
        s["rule_evaluations"] = evaluate_bucket(cfg, s, prev)
        prev = s["rule_evaluations"]
        rows[b] = {"tape_id": i + 1, "revision": 1, "snapshot_digest": f"{i:064x}", "snapshot": s}
    return rows


def run(snaps, cfg=CFG):
    rows = tape(snaps, cfg)
    return cx.replay(cfg, rows, start_bucket=T0, end_bucket=T0 + (len(snaps) - 1) * BUCKET), rows


DOWN = {"price": 0.02, "oi": 0.05}          # PRICE_OI_CONTRACTION_DOWN qualifies
UP = {"price": 0.98, "oi": 0.05}            # PRICE_OI_CONTRACTION_UP qualifies
DOWN_EXIT = {"price": 0.15}                 # below entry, beyond exit (0.20)
QUIET = {}


def ep(state, et):
    return state["episodes"].get(et)


# ---- continuity / cooling / end ------------------------------------------------------
def test_one_quieter_bucket_does_not_erase_the_episode():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET)])
    e = ep(states[-1], PRICE_OI_CONTRACTION_DOWN)
    assert e is not None and e["phase"] == cx.PHASE_COOLING
    assert e["confirmation"] == TRIGGERED        # the detector triggered at streak 2


def test_beyond_exit_keeps_active_then_cooling_then_ended_after_n():
    states, _ = run([snap(DOWN), snap(DOWN_EXIT), snap(QUIET), snap(QUIET), snap(QUIET)])
    phases = [(ep(s, PRICE_OI_CONTRACTION_DOWN) or {}).get("phase") for s in states]
    assert phases == [cx.PHASE_ACTIVE, cx.PHASE_ACTIVE, cx.PHASE_COOLING, cx.PHASE_COOLING, None]
    ended = states[-1]["last_ended"][PRICE_OI_CONTRACTION_DOWN]
    assert ended["phase"] == cx.PHASE_ENDED and ended["end_reason"] == cx.END_COOLED_DOWN
    assert ended["confirmation"] == ARMED        # only one qualifying bucket: never triggered


def test_missing_bucket_counts_as_below_exit():
    states, _ = run([snap(DOWN), None, None, None])
    assert states[-1]["last_ended"][PRICE_OI_CONTRACTION_DOWN]["end_reason"] == cx.END_COOLED_DOWN
    assert states[1]["episodes"][PRICE_OI_CONTRACTION_DOWN]["phase"] == cx.PHASE_COOLING


def test_same_side_reactivation_during_cooling_keeps_the_episode():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET), snap(DOWN)])
    e = ep(states[-1], PRICE_OI_CONTRACTION_DOWN)
    assert e["phase"] == cx.PHASE_ACTIVE and e["reactivations"] == 1
    assert e["episode_id"] == ep(states[0], PRICE_OI_CONTRACTION_DOWN)["episode_id"]
    assert len(e["detector_episode_ids"]) == 2   # the detector opened a 2nd episode


def test_beyond_exit_during_cooling_does_not_reactivate_but_resets_the_countdown():
    states, _ = run([snap(DOWN), snap(QUIET), snap(QUIET), snap(DOWN_EXIT), snap(QUIET), snap(QUIET)])
    e = ep(states[-1], PRICE_OI_CONTRACTION_DOWN)
    assert e["phase"] == cx.PHASE_COOLING and e["reactivations"] == 0 and e["below_exit_run"] == 2


def test_opposite_side_entry_supersedes_a_cooling_episode_in_the_same_cluster():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET), snap(UP)])
    last = states[-1]
    old = last["last_ended"][PRICE_OI_CONTRACTION_DOWN]
    new = ep(last, PRICE_OI_CONTRACTION_UP)
    assert old["end_reason"] == cx.END_SUPERSEDED and old["superseded_by"] == new["episode_id"]
    assert new["cluster_id"] == old["cluster_id"] == old["episode_id"] and new["supersedes"] == old["episode_id"]
    assert ep(last, PRICE_OI_CONTRACTION_DOWN) is None


def test_opposite_entry_directly_after_active_bucket_supersedes_deterministically():
    # the UP bucket is itself below the DOWN exit, so DOWN turns COOLING first, then is superseded
    states, _ = run([snap(DOWN), snap(UP)])
    assert states[-1]["last_ended"][PRICE_OI_CONTRACTION_DOWN]["end_reason"] == cx.END_SUPERSEDED


def test_ttl_ends_an_episode_that_would_otherwise_persist():
    from common.versioning import _to_plain
    raw = _to_plain(CFG.raw)
    raw["episodization"]["max_episode_duration_min"] = 20
    cfg = BetaConfig.from_mapping(raw)
    rows = tape([snap(DOWN)] + [snap(DOWN_EXIT)] * 6, cfg)
    states = [None]
    b = T0
    for i in range(7):
        states.append(cx.step_context(cfg, states[-1], b, rows[b], pinned=False))
        b += BUCKET
    ended = states[-1]["last_ended"][PRICE_OI_CONTRACTION_DOWN]
    assert ended["end_reason"] == cx.END_MAX_DURATION
    assert cx._ts(ended["ended_bucket"]) - cx._ts(ended["start_bucket"]) == timedelta(minutes=20)


def test_parameter_change_without_new_version_label_fails():
    from common.versioning import _to_plain
    raw = _to_plain(CFG.raw)
    raw["episodization"]["cooling_buckets_to_end"] = 4
    with pytest.raises(cx.ContextVersionError):
        cx.empty_state(BetaConfig.from_mapping(raw))
    raw = _to_plain(CFG.raw)
    raw["context"]["label_high"] = 0.96
    with pytest.raises(cx.ContextVersionError):
        cx.empty_state(BetaConfig.from_mapping(raw))


def test_exit_thresholds_must_be_laxer_than_entry():
    from common.versioning import _to_plain
    from beta.config import BetaConfigError
    raw = _to_plain(CFG.raw)
    raw["episodization"]["exit_percentile"][PRICE_OI_CONTRACTION_DOWN] = 0.01
    with pytest.raises(BetaConfigError):
        BetaConfig.from_mapping(raw)


# ---- confirmation axis = detector lifecycle -----------------------------------------------
def test_confirmation_matches_detector_episode_states_over_the_same_tape():
    """Replaying the detector's own state machine over the same tape gives the same
    highest level for every detector episode linked to a context episode."""
    buildup = {"range": 0.2, "oi": 0.9, "volume": 0.7}
    snaps = [snap(buildup)] * 10 + [snap(QUIET)] * 4 + [snap(DOWN)] * 3
    states, rows = run(snaps)
    det_best, open_ep = {}, {}
    for b in sorted(rows):
        s = rows[b]["snapshot"]
        ctx = BucketContext(bucket_ts=b, decision_ts=b + BUCKET, snapshot_digest=rows[b]["snapshot_digest"],
                            calculation_version="0" * 16, reference=s["reference"], code_version="t")
        for et in (POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN):
            st = step_episode(CFG, et, open_ep.get(et), s["rule_evaluations"][et], ctx)
            for e in (st.opened, st.updated):
                if e is not None:
                    open_ep[et] = e
                    prev = det_best.get(e.public_id)
                    det_best[e.public_id] = e.state if prev is None or \
                        cx.STATE_ORDER[e.state] > cx.STATE_ORDER[prev] else prev
            if st.terminated is not None:
                open_ep.pop(et, None)
    allc = {**states[-1]["episodes"], **states[-1]["last_ended"]}
    b_ep = allc[POSITION_BUILDUP_COMPRESSION]
    assert b_ep["confirmation"] == TRIGGERED == det_best[b_ep["detector_episode_ids"][0]]
    d_ep = allc[PRICE_OI_CONTRACTION_DOWN]
    assert d_ep["confirmation"] == max((det_best[i] for i in d_ep["detector_episode_ids"]),
                                       key=cx.STATE_ORDER.get)
    assert set(b_ep["detector_episode_ids"]) | set(d_ep["detector_episode_ids"]) == set(det_best)


def test_buildup_early_confirmation_uses_the_detector_early_level():
    states, _ = run([snap({"range": 0.2, "oi": 0.9, "volume": 0.7})] * 3)
    assert ep(states[-1], POSITION_BUILDUP_COMPRESSION)["confirmation"] == EARLY


# ---- running peak ---------------------------------------------------------------------
def test_running_peak_updates_only_on_strict_improvement_and_keeps_earliest_tie():
    s1 = snap(DOWN, {"price": -0.50})
    s2 = snap(DOWN, {"price": -0.90})
    s3 = snap(DOWN_EXIT, {"price": -0.90})      # tie -> keep earlier (s2)
    s4 = snap(DOWN_EXIT, {"price": -0.30})
    states, _ = run([s1, s2, s3, s4])
    peaks = [ep(s, PRICE_OI_CONTRACTION_DOWN)["peak"]["bucket_ts"] for s in states]
    assert peaks == [cx.iso(T0), cx.iso(T0 + BUCKET), cx.iso(T0 + BUCKET), cx.iso(T0 + BUCKET)]


def test_peak_metrics_all_come_from_the_peak_bucket():
    s1 = snap(DOWN, {"price": -0.9, "oi": -0.2, "volume": 5e6})
    s2 = snap(DOWN, {"price": -0.5, "oi": -3.0, "volume": 9e6})   # bigger OI/volume, smaller price
    states, rows = run([s1, s2])
    peak = ep(states[-1], PRICE_OI_CONTRACTION_DOWN)["peak"]
    assert peak["bucket_ts"] == cx.iso(T0)
    assert peak["view"] == cx.bucket_view(CFG, T0, rows[T0]["snapshot"])
    assert peak["view"]["oi_change_pct"]["value"] == -0.2 and peak["view"]["volume_notional_usd"]["value"] == 5e6


def test_state_at_t_contains_no_later_peak():
    snaps = [snap(DOWN, {"price": -0.3}), snap(DOWN, {"price": -0.4}), snap(DOWN, {"price": -1.2})]
    states, _ = run(snaps)
    for i, s in enumerate(states):
        e = ep(s, PRICE_OI_CONTRACTION_DOWN)
        assert cx._ts(e["peak"]["bucket_ts"]) <= T0 + i * BUCKET
        assert cx._ts(e["peak"]["view"]["bucket_ts"]) <= T0 + i * BUCKET
    assert ep(states[1], PRICE_OI_CONTRACTION_DOWN)["peak"]["primary_value"] == -0.4


def test_replay_prefix_equals_live_state_at_t():
    snaps = [snap(DOWN), snap(DOWN), snap(QUIET), snap(DOWN, {"price": -2.0}), snap(QUIET)]
    full, rows = run(snaps)
    for k in range(1, len(snaps) + 1):
        prefix = cx.replay(CFG, {b: r for b, r in rows.items() if b < T0 + k * BUCKET},
                           start_bucket=T0, end_bucket=T0 + (k - 1) * BUCKET)
        assert cx.state_digest(prefix[-1]) == cx.state_digest(full[k - 1])


# ---- determinism / serialization -------------------------------------------------------------
def test_same_tape_same_version_is_byte_identical():
    snaps = [snap(DOWN), snap(QUIET), snap(UP), snap(QUIET), snap(QUIET), snap(QUIET)]
    a, _ = run(snaps)
    b, _ = run(snaps)
    assert [cx.state_digest(s) for s in a] == [cx.state_digest(s) for s in b]
    from beta.config import canonical_json
    assert canonical_json(a[-1]) == canonical_json(b[-1])


def test_version_is_carried_in_state_and_every_episode():
    states, _ = run([snap(DOWN)])
    s = states[-1]
    assert s["episodization_version"] == "BETA_EPISODES_V0" and s["episodization_frozen"] is False
    e = ep(s, PRICE_OI_CONTRACTION_DOWN)
    assert e["episodization_version"] == "BETA_EPISODES_V0"
    assert e["episodization_digest"] == cx.KNOWN_EPISODIZATION_DIGESTS["BETA_EPISODES_V0"]
    import json
    assert json.loads(json.dumps(s))["episodes"][PRICE_OI_CONTRACTION_DOWN]["episodization_version"] \
        == "BETA_EPISODES_V0"


def test_step_must_advance_exactly_one_bucket_and_same_version():
    states, rows = run([snap(DOWN)])
    with pytest.raises(ValueError):
        cx.step_context(CFG, states[-1], T0 + 2 * BUCKET, None)
    bad = dict(states[-1], episodization_digest="0" * 64)
    with pytest.raises(cx.ContextVersionError):
        cx.step_context(CFG, bad, T0 + BUCKET, None)


# ---- venue agreement ---------------------------------------------------------------------------
def test_single_venue_extreme_is_not_shown_as_cross_venue():
    signs = {"taker_delta_notional_usd": {"binance": 9e7, "bybit": -1e5, "okx": -2e5}}
    s = snap({"taker": 0.99}, venue_signs=signs)
    v = cx.bucket_view(CFG, T0, s)["venue_direction"]["taker"]
    assert v["up"] == ["binance"] and v["down"] == ["bybit", "okx"] and v["contributing"] == 3


def test_venue_direction_unavailable_without_per_venue_values():
    s = snap(DOWN)
    for ex in EXS:
        s["metrics"][metric_key(ex, "price_move_pct")] = None
    assert cx.bucket_view(CFG, T0, s)["venue_direction"]["price"] is None


# ---- taker / liquidation primaries -------------------------------------------------------------
def test_taker_and_liquidation_episodes_use_their_primary_observable():
    states, _ = run([snap({"taker": 0.99}), snap({"taker": 0.99}), snap({"taker": 0.85}),
                     snap({"taker": 0.01})])
    last = states[-1]
    assert last["last_ended"][TAKER_FLOW_EXTREME_BUY]["end_reason"] == cx.END_SUPERSEDED
    assert ep(last, TAKER_FLOW_EXTREME_SELL)["phase"] == cx.PHASE_ACTIVE
    liq = {(ex, "long_liquidation_notional"): (1e6 * (i + 1), 0.99) for i, ex in enumerate(EXS)}
    states, _ = run([snap(liq=liq)])
    e = ep(states[-1], LIQUIDATION_STRESS_LONG)
    assert e["peak"]["primary_value"] == 6e6


# ---- rolling 1h -----------------------------------------------------------------------------
def _hist(n, start, *, hi=101.0, lo=99.0, vol=1e6):
    out = []
    for i in range(n):
        m = {"c:volume_notional_usd_sum": vol}
        for ex in EXS:
            m.update({metric_key(ex, "kline_open"): 100.0, metric_key(ex, "kline_high"): hi,
                      metric_key(ex, "kline_low"): lo, metric_key(ex, "kline_close"): 100.0})
        out.append((start + i * BUCKET, m))
    return out


def test_rolling_1h_uses_raw_last_12_buckets_not_5m_percentiles():
    rows = dict(_hist(12, T0))
    rows[T0 + 3 * BUCKET] = dict(rows[T0 + 3 * BUCKET])
    for ex in EXS:
        rows[T0 + 3 * BUCKET][metric_key(ex, "kline_high")] = 104.0
    rows[T0 + 11 * BUCKET] = dict(rows[T0 + 11 * BUCKET], **{metric_key(ex, "kline_close"): 102.0 for ex in EXS})
    v = cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET)
    assert math.isclose(v["range_width_pct_median"], 5.0)          # (104 - 99) / 100
    assert math.isclose(v["price_move_pct_median"], 2.0)
    assert math.isclose(v["volume_notional_usd_sum"], 12e6)
    assert v["window_start"] == cx.iso(T0) and v["window_end"] == cx.iso(T0 + 12 * BUCKET)
    del rows[T0 + 5 * BUCKET]
    assert cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET) is None


def test_rolling_1h_percentile_compares_against_rolling_1h_history():
    ident = {"feature_schema_version": 1, "calculation_version": "a" * 16,
             "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
    tiers = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}
    t = T0 + timedelta(days=31)
    n = int((timedelta(days=30, minutes=55)) / BUCKET)
    hist = _hist(n, t - n * BUCKET)                                  # flat 2% ranges, 1e6 volume
    cur = dict(hist[-1][1], **{metric_key(ex, "kline_high"): 110.0 for ex in EXS})
    out = cx.context_1h(CFG, bucket_ts=t, current_metrics=cur, history=hist,
                        identity=ident, code_version="t", tiers=tiers)
    assert out["percentiles"]["range_width_pct_median"]["tier"] == "mature"
    assert out["percentiles"]["range_width_pct_median"]["rank"] == 1.0
    assert cx.level_label(CFG, out["percentiles"]["range_width_pct_median"]["rank"], "mature") == "extreme"
    assert out["percentiles"]["volume_notional_usd_sum"]["rank"] == 0.5          # all ties
    assert out["percentiles"]["range_width_pct_median"]["sample_size"] == 8640


# ---- labels -------------------------------------------------------------------------------
@pytest.mark.parametrize("rank,label", [(0.5, "normal"), (0.80, "elevated"), (0.95, "high"),
                                        (0.99, "extreme"), (1.0, "extreme")])
def test_level_labels_are_predefined_thresholds(rank, label):
    assert cx.level_label(CFG, rank, "mature") == label
    assert cx.level_label(CFG, rank, "building") is None


@pytest.mark.parametrize("rank,text", [(1.0, "top <1%"), (0.995, "top <1%"), (0.97, "top 3%"),
                                       (0.02, "bottom 2%"), (0.0, "bottom <1%"), (0.5, None), (0.75, None)])
def test_signed_tail_labels_never_claim_certainty(rank, text):
    assert cx.tail_label(CFG, rank, "mature") == text


# ---- N selection helper uses structure only ------------------------------------------------
def test_structure_stats_for_candidate_n_use_no_prices_after_the_window():
    snaps = [snap(DOWN), snap(QUIET), snap(QUIET), snap(DOWN), snap(QUIET), snap(QUIET), snap(QUIET),
             snap(QUIET)]
    rows = tape(snaps)
    stats = cx.episode_structure_stats(CFG, rows, start_bucket=T0, end_bucket=T0 + 7 * BUCKET,
                                       candidates=[1, 3])
    assert stats[1]["episodes_ended"] == 2 and stats[1]["reactivations"] == 0
    assert stats[3]["episodes_ended"] == 1 and stats[3]["reactivations"] == 1
