"""Temporal context, STRICT_QUALIFICATION_V1 (pure, no DB, no forward data).

The projection's episodes must be the detector's episodes (A), anchors are factual
single buckets (F, G, H), unfrozen hysteresis cannot reach runtime (I), and the
projection is deterministic / replayable without lookahead (J)."""
import ast
import copy
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from beta import context as cx
from beta import context_calibration as cal
from beta.config import (EVENT_TYPES, BetaConfig, BetaConfigError, LIQUIDATION_STRESS_LONG,
                         POSITION_BUILDUP_COMPRESSION, PRICE_OI_CONTRACTION_DOWN, PRICE_OI_CONTRACTION_UP,
                         TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL)
from beta.detector import BucketContext, step_episode
from beta.rules import evaluate_bucket
from beta.state_tape import BUCKET, metric_key
from common.versioning import _to_plain

CFG = BetaConfig.load()
EXS = CFG.exchanges
T0 = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
REPO = Path(__file__).resolve().parents[2]
NEUTRAL = {"price": 0.5, "oi": 0.5, "range": 0.5, "volume": 0.5, "taker": 0.5}
CALC = "c" * 16


def snap(ranks=None, values=None, *, fresh=True, venue_signs=None, liq=None, contributing=EXS,
         materialized=True):
    """A LIVE-like tape snapshot with mature percentiles. `ranks` override NEUTRAL."""
    r = {**NEUTRAL, **(ranks or {})}
    v = {"price": (r["price"] - 0.5) * 2, "oi": (r["oi"] - 0.5) * 4, "range": r["range"],
         "volume": 1e6 * (1 + r["volume"]), "taker": (r["taker"] - 0.5) * 1e7, **(values or {})}
    keys = {"price": "c:price_move_pct_median", "oi": "c:oi_change_pct_median",
            "range": "c:range_width_pct_median", "volume": "c:volume_notional_usd_sum",
            "taker": "c:taker_delta_notional_usd_sum"}
    metrics = {keys[k]: v[k] for k in keys}
    pct = {keys[k]: {"value": v[k], "rank": r[k], "tier": "mature"} for k in keys}
    signs = venue_signs or {}
    raw = {ex: {"price_move_pct": signs.get("price_move_pct", {}).get(ex, v["price"]),
                "oi_change_pct": signs.get("oi_change_pct", {}).get(ex, v["oi"]),
                "taker_delta_notional_usd": signs.get("taker_delta_notional_usd", {}).get(ex, v["taker"]),
                "range_width_pct": v["range"], "volume_notional_usd": v["volume"] / 3} for ex in EXS}
    for ex in EXS:
        for side in ("long_liquidation_notional", "short_liquidation_notional"):
            val, rank = (liq or {}).get((ex, side), (None, None))
            metrics[metric_key(ex, side)] = val
            pct[metric_key(ex, side)] = {"value": val, "rank": rank, "tier": "mature" if rank is not None else None}
    fam = {"available": len(contributing), "expected": 3, "contributing": list(contributing),
           "usable": len(contributing) >= 2}
    return {"materialized": materialized, "evaluation_fresh": fresh, "stale_barrier": False,
            "identity": {"calculation_version": CALC}, "code_version": "beta-test",
            "state_schema_version": CFG.state_schema_version,
            "metrics": metrics, "percentiles": pct, "venue_raw": raw,
            "families": {f: dict(fam) for f in ("price_structure", "oi", "volume", "taker_flow")},
            "venues": {ex: {"declared_available": True, "heartbeat_healthy": True} for ex in EXS},
            "reference": {"status": "OK", "price": 83500.0, "exchanges": list(EXS), "dispersion_pct": 0.01}}


def tape(snaps, cfg=CFG, start=T0):
    """Attach REAL rule evaluations, chained exactly like the detector (a missing
    bucket = no LIVE row = the detector never decided it)."""
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


def detector_reference(rows, cfg=CFG):
    """The detector's own state machine over the same tape (what the DB would hold)."""
    open_, done = {}, []
    for b in sorted(rows):
        row = rows[b]
        if row is None:
            continue
        s = row["snapshot"]
        ctx = BucketContext(bucket_ts=b, decision_ts=b + BUCKET, snapshot_digest=row["snapshot_digest"],
                            calculation_version=CALC, reference=s["reference"], code_version="beta-test")
        for et in EVENT_TYPES:
            st = step_episode(cfg, et, open_.get(et), s["rule_evaluations"][et], ctx)
            if st.terminated is not None:
                done.append(st.terminated)
                open_.pop(et, None)
            for e in (st.updated, st.opened):
                if e is not None:
                    open_[et] = e
    return open_, done


DOWN = {"price": 0.02, "oi": 0.05}          # PRICE_OI_CONTRACTION_DOWN qualifies
UP = {"price": 0.98, "oi": 0.05}
BUILDUP = {"range": 0.2, "oi": 0.9, "volume": 0.7}
QUIET = {}


def _key(e):
    return (e.public_id, e.event_type, e.state, cx.iso(e.opened_bucket), cx.iso(e.last_bucket),
            e.terminal_reason, cx.iso(e.terminal_at), cx.iso(e.triggered_at))


def _pkey(p):
    return (p["episode_id"], p["event_type"], p["state"], p["opened_bucket"], p["last_bucket"],
            p["terminal_reason"], p["terminal_at"], p["triggered_at"])


# ---- A: detector episode boundaries are identical ------------------------------------------
MIXED = ([snap(DOWN), snap(DOWN), snap(QUIET), snap(DOWN), None, snap(DOWN), snap(UP), snap(UP),
          snap({"taker": 0.99}), snap({"taker": 0.99}), snap({"taker": 0.5}),
          snap(DOWN), snap(DOWN, fresh=False), snap(QUIET)] + [snap(BUILDUP)] * 40 + [snap(QUIET)])


def test_projection_episodes_equal_detector_episodes_on_a_mixed_tape():
    states, rows = run(MIXED)
    det_open, det_done = detector_reference(rows)
    seen_ended = {}
    for s in states:                                  # every ended episode appears in last_ended
        for e in s["last_ended"].values():
            seen_ended[e["episode_id"]] = e
    assert sorted(_pkey(e) for e in seen_ended.values()) == sorted(_key(e) for e in det_done)
    assert sorted(_pkey(e) for e in states[-1]["open"].values()) == sorted(_key(e) for e in det_open.values())
    reasons = {e.terminal_reason for e in det_done}
    assert {"CONDITION_FAILED", "DETECTION_GAP", "NOT_EVALUABLE", "MAX_DURATION"} <= reasons


def test_first_non_qualifying_bucket_ends_the_episode_no_cooling():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET)])
    assert states[-1]["open"] == {}
    last = states[-1]["last_ended"][PRICE_OI_CONTRACTION_DOWN]
    assert last["state"] == "ENDED" and last["terminal_reason"] == "CONDITION_FAILED"
    assert last["qualifying_buckets"] == 2
    blob = json.dumps(states)
    assert "COOLING" not in blob and "reactivation" not in blob.lower()


def test_buildup_keeps_its_existing_max_duration_cap():
    states, rows = run([snap(BUILDUP)] * 40)
    _, det_done = detector_reference(rows)
    capped = [e for e in det_done if e.terminal_reason == "MAX_DURATION"]
    assert capped                      # the detector caps it ...
    ended = states[-1]["last_ended"][POSITION_BUILDUP_COMPRESSION]
    assert ended["terminal_reason"] == "MAX_DURATION"   # ... and so does the projection


def test_missing_bucket_is_not_stepped_and_the_next_decided_bucket_sees_the_gap():
    states, _ = run([snap(DOWN), None, snap(DOWN)])
    assert states[1]["open"][PRICE_OI_CONTRACTION_DOWN]["state"] == "ARMED"     # untouched
    ended = states[2]["last_ended"][PRICE_OI_CONTRACTION_DOWN]
    assert ended["terminal_reason"] == "DETECTION_GAP"


# ---- F: taker strongest observed bucket, no lookahead ---------------------------------------
def test_taker_anchor_is_strongest_observed_with_strict_improvement_and_earliest_tie():
    s1 = snap({"taker": 0.99}, {"taker": 4e6})
    s2 = snap({"taker": 0.99}, {"taker": 9e6})
    s3 = snap({"taker": 0.99}, {"taker": 9e6})          # tie -> keep earlier
    s4 = snap({"taker": 0.99}, {"taker": 5e6})
    states, rows = run([s1, s2, s3, s4])
    anchors = [s["open"][TAKER_FLOW_EXTREME_BUY]["anchor"] for s in states]
    assert [a["bucket_ts"] for a in anchors] == [cx.iso(T0), cx.iso(T0 + BUCKET), cx.iso(T0 + BUCKET),
                                                 cx.iso(T0 + BUCKET)]
    assert all(a["kind"] == cx.ANCHOR_STRONGEST for a in anchors)
    assert anchors[-1]["view"] == cx.bucket_view(CFG, T0 + BUCKET, rows[T0 + BUCKET]["snapshot"])


def test_taker_sell_anchor_uses_the_signed_direction():
    states, _ = run([snap({"taker": 0.01}, {"taker": -3e6}), snap({"taker": 0.01}, {"taker": -8e6})])
    a = states[-1]["open"][TAKER_FLOW_EXTREME_SELL]["anchor"]
    assert a["bucket_ts"] == cx.iso(T0 + BUCKET) and a["value"] == -8e6


def test_no_state_contains_a_bucket_after_its_own_time():
    snaps = [snap({"taker": 0.99}, {"taker": x}) for x in (2e6, 3e6, 9e6, 1e6)] + [snap(QUIET)]
    states, _ = run(snaps)
    for i, s in enumerate(states):
        t = T0 + i * BUCKET
        for e in list(s["open"].values()) + list(s["last_ended"].values()):
            assert cx._ts(e["anchor"]["bucket_ts"]) <= t and cx._ts(e["last_bucket"]) <= t
    assert states[1]["open"][TAKER_FLOW_EXTREME_BUY]["anchor"]["value"] == 3e6


# ---- G: conjunction families acquire no new scientific semantics ------------------------------
def test_conjunction_anchor_is_the_detector_trigger_bucket_not_a_strongest_ranking():
    s1 = snap(DOWN, {"price": -0.4})
    s2 = snap(DOWN, {"price": -0.6})             # detector TRIGGERS here (streak 2)
    s3 = snap(DOWN, {"price": -3.0, "oi": -9.0}) # more extreme later bucket: anchor must NOT move
    states, _ = run([s1, s2, s3])
    a0 = states[0]["open"][PRICE_OI_CONTRACTION_DOWN]["anchor"]
    a2 = states[2]["open"][PRICE_OI_CONTRACTION_DOWN]["anchor"]
    assert a0["kind"] == cx.ANCHOR_OPENING and a0["bucket_ts"] == cx.iso(T0)
    assert a2["kind"] == cx.ANCHOR_TRIGGER and a2["bucket_ts"] == cx.iso(T0 + BUCKET)
    assert a2["evidence"]["ranks"] == {"price_move_pct_median": 0.02, "oi_change_pct_median": 0.05}


def test_projection_never_changes_rule_qualification():
    rows = tape(MIXED)
    for b, row in rows.items():
        if row is None:
            continue
        before = copy.deepcopy(row["snapshot"]["rule_evaluations"])
        cx.step_context(CFG, None, b, row)
        assert row["snapshot"]["rule_evaluations"] == before


def test_active_config_has_no_hysteresis_parameters():
    ep = dict(CFG.section("episodization"))
    assert ep == {"version": "STRICT_QUALIFICATION_V1", "live_hysteresis_enabled": False}
    payload = json.dumps(cx.episodization_payload(CFG))
    for k in ("cooling", "exit", "max_episode_duration", "0.65", "0.8"):
        assert k not in payload


# ---- H: liquidation keeps per-venue voting ----------------------------------------------------
def test_liquidation_view_keeps_per_venue_votes_and_never_sums():
    liq = {("binance", "long_liquidation_notional"): (5e6, 0.99),
           ("bybit", "long_liquidation_notional"): (1e6, 0.97),
           ("okx", "long_liquidation_notional"): (1e5, 0.40)}
    states, rows = run([snap(liq=liq)])
    e = states[-1]["open"][LIQUIDATION_STRESS_LONG]
    view = e["anchor"]["view"]["liquidations"]["long"]
    assert view["voting"] == ["binance", "bybit"] and view["eligible"] == ["binance", "bybit", "okx"]
    assert view["per_venue"] == {"binance": 5e6, "bybit": 1e6, "okx": 1e5}
    assert "sum" not in view and e["anchor"]["kind"] == cx.ANCHOR_TRIGGER


def test_one_huge_venue_does_not_create_a_liquidation_episode():
    liq = {("binance", "long_liquidation_notional"): (9e9, 1.0),
           ("bybit", "long_liquidation_notional"): (1e3, 0.30),
           ("okx", "long_liquidation_notional"): (1e3, 0.30)}
    states, rows = run([snap(liq=liq)])
    assert LIQUIDATION_STRESS_LONG not in states[-1]["open"]
    assert rows[T0]["snapshot"]["rule_evaluations"][LIQUIDATION_STRESS_LONG]["status"] == "NOT_QUALIFIES"


# ---- I: unfrozen hysteresis cannot reach runtime ---------------------------------------------
RUNTIME_FILES = [p for p in sorted((REPO / "beta").glob("*.py")) if p.name != "context_calibration.py"] + \
    sorted((REPO / "runtime").glob("beta_*.py")) + [REPO / "storage/beta_v0_store.py", REPO / "main.py"]


def test_no_runtime_module_imports_the_calibration_tooling():
    for f in RUNTIME_FILES:
        for n in ast.walk(ast.parse(f.read_text())):
            names = [a.name for a in n.names] if isinstance(n, (ast.Import, ast.ImportFrom)) else []
            mod = n.module if isinstance(n, ast.ImportFrom) else ""
            assert "context_calibration" not in (mod or "") and not any("context_calibration" in x for x in names), f


def test_live_hysteresis_cannot_be_enabled():
    raw = _to_plain(CFG.raw)
    raw["episodization"]["live_hysteresis_enabled"] = True
    with pytest.raises(BetaConfigError):
        BetaConfig.from_mapping(raw)
    raw = _to_plain(CFG.raw)
    raw["episodization"]["cooling_buckets_to_end"] = 3
    with pytest.raises(BetaConfigError):
        BetaConfig.from_mapping(raw)


def test_calibration_is_taker_only_structure_statistics():
    snaps = [snap({"taker": 0.99}), snap({"taker": 0.5}), snap({"taker": 0.99}), snap(QUIET),
             snap(QUIET), snap(QUIET), snap(DOWN), snap(DOWN)]
    rows = tape(snaps)
    loose = cal.HysteresisParams(3, 240, 0.80, 0.20)
    strict = cal.HysteresisParams(1, 240, 0.95, 0.05)
    a, b = cal.structure_stats(CFG, rows, start_bucket=T0, end_bucket=T0 + 7 * BUCKET, candidates=[loose, strict])
    assert a["identity"] == b["identity"] == "EXPERIMENTAL_TAKER_HYSTERESIS_UNFROZEN"
    assert (a["episodes_ended"], a["reactivations"]) == (1, 1)
    assert (b["episodes_ended"], b["reactivations"]) == (2, 0)
    assert set(cal.SUPPORTED) == {TAKER_FLOW_EXTREME_BUY, TAKER_FLOW_EXTREME_SELL}
    before = [cx.state_digest(s) for s in run(snaps)[0]]
    cal.structure_stats(CFG, rows, start_bucket=T0, end_bucket=T0 + 7 * BUCKET, candidates=[loose])
    assert [cx.state_digest(s) for s in run(snaps)[0]] == before


# ---- J: determinism, versions, replay -----------------------------------------------------------
def test_same_tape_same_version_is_byte_identical_and_replay_prefix_equals_state():
    a, rows = run(MIXED)
    b, _ = run(MIXED)
    assert [cx.state_digest(s) for s in a] == [cx.state_digest(s) for s in b]
    for k in (1, 7, 20, len(MIXED)):
        prefix = cx.replay(CFG, {x: r for x, r in rows.items() if x < T0 + k * BUCKET},
                           start_bucket=T0, end_bucket=T0 + (k - 1) * BUCKET)
        assert cx.state_digest(prefix[-1]) == cx.state_digest(a[k - 1])


def test_state_survives_json_round_trip_and_carries_versions():
    states, _ = run([snap(DOWN), snap(DOWN)])
    s = json.loads(json.dumps(states[-1]))
    assert cx.state_digest(s) == cx.state_digest(states[-1])
    assert s["episodization_version"] == "STRICT_QUALIFICATION_V1" and s["live_hysteresis_enabled"] is False
    e = s["open"][PRICE_OI_CONTRACTION_DOWN]
    assert e["episodization_version"] == "STRICT_QUALIFICATION_V1"
    assert e["episodization_digest"] == cx.KNOWN_EPISODIZATION_DIGESTS["STRICT_QUALIFICATION_V1"]
    nxt = cx.step_context(CFG, s, T0 + 2 * BUCKET, tape([snap(DOWN)] * 3)[T0 + 2 * BUCKET])
    assert nxt["open"][PRICE_OI_CONTRACTION_DOWN]["qualifying_buckets"] == 3


def test_version_pins_reject_silent_parameter_changes():
    raw = _to_plain(CFG.raw)
    raw["context"]["last_event_retention_min"] = 60
    with pytest.raises(cx.ContextVersionError):
        cx.empty_state(BetaConfig.from_mapping(raw))


def test_step_must_advance_exactly_one_bucket_and_same_version():
    states, _ = run([snap(DOWN)])
    with pytest.raises(ValueError):
        cx.step_context(CFG, states[-1], T0 + 2 * BUCKET, None)
    with pytest.raises(cx.ContextVersionError):
        cx.step_context(CFG, dict(states[-1], episodization_digest="0" * 64), T0 + BUCKET, None)


# ---- venue agreement ---------------------------------------------------------------------------
def test_single_venue_extreme_is_not_shown_as_cross_venue():
    signs = {"taker_delta_notional_usd": {"binance": 9e7, "bybit": -1e5, "okx": -2e5}}
    v = cx.bucket_view(CFG, T0, snap({"taker": 0.99}, venue_signs=signs))["venue_direction"]["taker"]
    assert v["up"] == ["binance"] and v["down"] == ["bybit", "okx"] and v["contributing"] == 3


def test_venue_direction_unavailable_without_per_venue_values():
    s = snap(DOWN)
    s["venue_raw"]["okx"]["price_move_pct"] = None
    assert cx.bucket_view(CFG, T0, s)["venue_direction"]["price"] is None


# ---- rolling 1h -------------------------------------------------------------------------------
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
    rows[T0 + 3 * BUCKET] = dict(rows[T0 + 3 * BUCKET], **{metric_key(ex, "kline_high"): 104.0 for ex in EXS})
    rows[T0 + 11 * BUCKET] = dict(rows[T0 + 11 * BUCKET], **{metric_key(ex, "kline_close"): 102.0 for ex in EXS})
    v = cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET)
    assert math.isclose(v["range_width_pct_median"], 5.0) and math.isclose(v["price_move_pct_median"], 2.0)
    assert math.isclose(v["volume_notional_usd_sum"], 12e6)
    assert v["window_start"] == cx.iso(T0) and v["window_end"] == cx.iso(T0 + 12 * BUCKET)
    del rows[T0 + 5 * BUCKET]
    assert cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET) is None


def test_rolling_1h_percentile_compares_against_rolling_1h_history():
    ident = {"feature_schema_version": 1, "calculation_version": "a" * 16,
             "stage2_config_hash": "b" * 64, "stage2_config_version": "v"}
    tiers = {"none_below_days": 3, "low_below_days": 7, "building_below_days": 30}
    t = T0 + timedelta(days=31)
    n = int(timedelta(days=30, minutes=55) / BUCKET)
    hist = _hist(n, t - n * BUCKET)
    cur = dict(hist[-1][1], **{metric_key(ex, "kline_high"): 110.0 for ex in EXS})
    # V2 (pooled C0): every 5m step of the previous 30 days
    v2 = CFG.with_overrides(context={**CFG.section("context"), "version": "BETA_CONTEXT_1H_V2"})
    out = cx.context_1h(v2, bucket_ts=t, current_metrics=cur, history=hist, identity=ident,
                        code_version="t", tiers=tiers)
    p = out["percentiles"]["range_width_pct_median"]
    assert (p["tier"], p["rank"], p["sample_size"]) == ("mature", 1.0, 8640)
    assert cx.level_label(CFG, p["rank"], "mature") == "extreme"
    assert out["percentiles"]["volume_notional_usd_sum"]["rank"] == 0.5
    # V3 (C1): only the same UTC day type (t is a weekday: 22 weekday dates of samples)
    out = cx.context_1h(CFG, bucket_ts=t, current_metrics=cur, history=hist, identity=ident,
                        code_version="t", tiers=tiers)
    p = out["percentiles"]["range_width_pct_median"]
    assert (p["tier"], p["rank"], p["sample_size"], p["day_type"]) == ("mature", 1.0, 22 * 288, "WEEKDAY")
    assert out["percentiles"]["volume_notional_usd_sum"]["rank"] == 0.5


@pytest.mark.parametrize("rank,label", [(0.5, "normal"), (0.80, "elevated"), (0.95, "high"),
                                        (0.99, "extreme"), (1.0, "extreme")])
def test_level_labels_are_predefined_thresholds(rank, label):
    assert cx.level_label(CFG, rank, "mature") == label
    assert cx.level_label(CFG, rank, "building") is None


@pytest.mark.parametrize("rank,text", [(1.0, "top <1%"), (0.995, "top <1%"), (0.97, "top 3%"),
                                       (0.02, "bottom 2%"), (0.0, "bottom <1%"), (0.5, None), (0.75, None)])
def test_signed_tail_labels_never_claim_certainty(rank, text):
    assert cx.tail_label(CFG, rank, "mature") == text


# ---- state-tape schema awareness -----------------------------------------------------------
def test_projection_refuses_a_row_of_another_tape_schema():
    rows = tape([snap(DOWN)])
    bad = copy.deepcopy(rows[T0])
    bad["snapshot"]["state_schema_version"] = 1
    with pytest.raises(cx.ContextVersionError):
        cx.step_context(CFG, None, T0, bad)
    v1 = CFG.with_overrides(state_schema_version=1)
    states = cx.replay(v1, {T0: bad}, start_bucket=T0, end_bucket=T0)            # a V1 replay of V1 rows is fine
    assert states[0]["state_schema_version"] == 1
    with pytest.raises(cx.ContextVersionError):                                   # ... but never reinterpreted as V2
        cx.step_context(CFG, states[0], T0 + BUCKET, rows[T0] | {"snapshot": dict(rows[T0]["snapshot"])})


def test_1h_window_is_unavailable_at_11_and_available_at_12_compatible_buckets():
    rows = dict(_hist(11, T0))
    assert cx.rolling_1h_values(CFG, rows, T0 + 10 * BUCKET) is None
    rows.update(_hist(1, T0 + 11 * BUCKET))
    assert cx.rolling_1h_values(CFG, rows, T0 + 11 * BUCKET) is not None
    assert cx.context_payload(CFG)["requires_state_schema_version"] == 2
