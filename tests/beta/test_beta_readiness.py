"""Detector readiness read model (pure): READY only when the detector evaluated the
family; HISTORY_BUILDING / DATA_UNAVAILABLE / DEGRADED otherwise; /btc headline
precedence; factual history progress; no effect on events or LAST EVENT."""
import ast
import copy
import json
import random
from datetime import timedelta
from pathlib import Path

import pytest

from test_beta_context import CFG, DOWN, EXS, QUIET, T0, cx, snap, tape

from beta import readiness as rd
from beta.config import (EVENT_TYPES, LIQUIDATION_STRESS_LONG, TAKER_FLOW_EXTREME_BUY, canonical_json)
from beta.context import btc_view
from beta.formatter import btc_buttons, format_btc, format_readiness_details
from beta.models import NOT_EVALUABLE
from beta.rules import evaluate_bucket
from beta.state_tape import BUCKET, iso, metric_key

REPO = Path(__file__).resolve().parents[2]
MAT = 30.0
LIQ_OK = {(ex, side): (1e5, 0.5) for ex in EXS
          for side in ("long_liquidation_notional", "short_liquidation_notional")}


def rsnap(ranks=None, *, tier="mature", span=31.0, tiers=None, liq=LIQ_OK, heartbeat=True, fresh=True,
          values=None, value_none=()):
    """A tape snapshot with the percentile fields the core records (tier, samples, earliest sample)."""
    s = snap(ranks, values, fresh=fresh, liq=liq)
    for k, p in s["percentiles"].items():
        t = (tiers or {}).get(k, tier)
        # a non-mature tier always has a non-mature span (the core derives tier FROM span)
        sp = span if t == tier else (tiers or {}).get(k + "#span", 31.0 if t == "mature" else 10.0)
        if p.get("value") is None and p.get("rank") is None:
            continue
        p.update(tier=t, sample_size=500, window_start=iso(T0 - timedelta(days=sp)))
    for k in value_none:
        s["metrics"][k] = None
        s["percentiles"][k] = {"value": None, "rank": None, "tier": "none", "sample_size": 0, "window_start": None}
    for ex in EXS:
        s["venues"][ex]["heartbeat_healthy"] = heartbeat
    return s


def ready_of(s, prev=None):
    s = copy.deepcopy(s)
    s["rule_evaluations"] = evaluate_bucket(CFG, s, prev)
    return rd.readiness(CFG, {"bucket_ts": T0, "snapshot": s}, maturity_days=MAT), s


def groups(r):
    return {g["group"]: g for g in r["groups"]}


def view_for(r, s, status, states=None):
    state = states[-1] if states else cx.step_context(CFG, None, T0, {"tape_id": 1, "revision": 1,
                                                                       "snapshot_digest": "0" * 64, "snapshot": s})
    prod = {"status": status, "reasons": [], "last_good_bucket": cx._ts(state["as_of_bucket"])}
    return btc_view(CFG, product=prod, state=state, state_digest_value=cx.state_digest(state),
                    now=cx._ts(state["as_of_bucket"]) + BUCKET + timedelta(seconds=30), readiness=r,
                    detector_open_ids=[e["episode_id"] for e in state["open"].values()])


# ---- A: all immature -------------------------------------------------------------------------
def test_all_immature_is_history_building_not_no_active_events():
    r, s = ready_of(rsnap(tier="building", span=8.47))
    assert {g["status"] for g in r["groups"]} == {rd.BUILDING} and r["core_ready"] is False
    for g in r["groups"]:
        assert g["progress"]["span_days"] == 8.4                   # floored, never overstated
    assert rd.headline("NO ACTIVE EVENTS", r) == "HISTORY BUILDING"
    v = view_for(r, s, "NO ACTIVE EVENTS")
    assert v["headline"] == "HISTORY BUILDING"
    out = format_btc(CFG, v)
    assert "BTC · history building" in out and "NO ACTIVE EVENTS" not in out and "HISTORY BUILDING" not in out
    assert "Price/OI history 8.4d / 30d" in out and "Unusual states are not evaluated yet" in out
    assert "Taker flow:" not in out and "Liquidations:" not in out
    assert ("Readiness", "r:latest") in btc_buttons(v)[0]
    details = format_readiness_details(CFG, r)
    assert "history building · OI history 8.4d / 30d" in details
    assert "history building · taker-flow history 8.4d / 30d" in details
    assert "history building · long-side liquidation history 8.4d / 30d" in details


def test_no_history_sample_yet_is_building_with_zero_span():
    s = rsnap()
    k = "c:oi_change_pct_median"
    s["percentiles"][k].update(rank=None, tier="none", sample_size=0, window_start=None)
    r, _ = ready_of(s)
    assert groups(r)["PRICE_OI"]["status"] == rd.BUILDING
    assert groups(r)["PRICE_OI"]["progress"] == {"metric": k, "span_days": 0.0}


# ---- B: all ready, no event -----------------------------------------------------------------
def test_all_ready_no_event_keeps_no_active_events():
    r, s = ready_of(rsnap())
    assert {g["status"] for g in r["groups"]} == {rd.READY} and r["core_ready"]
    assert all(e["rule_status"] != NOT_EVALUABLE for e in r["events"].values())
    v = view_for(r, s, "NO ACTIVE EVENTS")
    assert v["headline"] == "NO ACTIVE EVENTS"
    out = format_btc(CFG, v)
    assert "BTC · calm" in out and "No unusual state now" in out and "NO ACTIVE EVENTS" not in out
    assert "Detector ready" not in out and "Venues" not in out
    assert "Ready:" not in out and "history building ·" not in out
    assert btc_buttons(v) == [[("Details", "n:latest")]]


# ---- C: mixed ---------------------------------------------------------------------------------
def test_mixed_readiness_is_shown_per_group():
    s = rsnap(tiers={"c:taker_delta_notional_usd_sum": "building", "c:taker_delta_notional_usd_sum#span": 3.2},
              heartbeat=False)
    r, _ = ready_of(s)
    g = groups(r)
    assert (g["PRICE_OI"]["status"], g["TAKER_FLOW"]["status"], g["LIQUIDATIONS"]["status"]) == \
        (rd.READY, rd.BUILDING, rd.UNAVAILABLE)
    assert r["events"][LIQUIDATION_STRESS_LONG]["venues"]["binance"]["reason"] == "HEARTBEAT_UNHEALTHY"
    v = view_for(r, s, "NO ACTIVE EVENTS")
    assert v["headline"] == "NO ACTIVE EVENTS"
    out = format_btc(CFG, v)
    assert "BTC · calm" in out
    assert "Ready:" not in out and "Detector ready" not in out
    assert "history building" not in out and "data unavailable" not in out
    details = format_readiness_details(CFG, r)
    assert "<b>Price/OI</b>: ready" in details
    assert "Taker flow</b>: history building · taker-flow history 3.2d / 30d" in details
    assert "Liquidations</b>: data unavailable · fewer than the required eligible live feeds" in details


def test_partly_ready_group_is_not_collapsed():
    s = rsnap(tiers={"c:range_width_pct_median": "building", "c:range_width_pct_median#span": 12.0})
    r, _ = ready_of(s)
    g = groups(r)["PRICE_OI"]
    assert g["status"] == rd.BUILDING and g["partly_ready"] and (g["ready_members"], g["enabled_members"]) == (2, 3)
    assert rd.headline("NO ACTIVE EVENTS", r) == "HISTORY BUILDING"      # production scope not fully evaluable
    out = format_btc(CFG, view_for(r, s, "NO ACTIVE EVENTS"))
    assert "BTC · history building" in out and "Price/OI history 12.0d / 30d" in out
    assert "partly ready" not in out
    assert "partly ready (2/3 rules) · history building · range history 12.0d / 30d" in \
        format_readiness_details(CFG, r)


# ---- D: active event during partial readiness -------------------------------------------------
def test_active_event_keeps_headline_while_other_families_build():
    immature_core = {k: "building" for k in ("c:price_move_pct_median", "c:oi_change_pct_median",
                                            "c:range_width_pct_median", "c:volume_notional_usd_sum")}
    snaps = [rsnap({"taker": 0.99}, tiers=immature_core), rsnap({"taker": 0.99}, tiers=immature_core)]
    rows = tape(snaps)
    states = cx.replay(CFG, rows, start_bucket=T0, end_bucket=T0 + BUCKET)
    assert states[-1]["open"][TAKER_FLOW_EXTREME_BUY]["state"] == "TRIGGERED"   # event not suppressed
    r = rd.readiness(CFG, {"bucket_ts": T0 + BUCKET, "snapshot": rows[T0 + BUCKET]["snapshot"]}, maturity_days=MAT)
    assert groups(r)["TAKER_FLOW"]["status"] == rd.READY and groups(r)["PRICE_OI"]["status"] == rd.BUILDING
    v = view_for(r, None, "EVENT ACTIVE", states)
    assert v["headline"] == "EVENT ACTIVE"
    out = format_btc(CFG, v)
    assert "BTC · unusual now" in out and "Still active" in out and "Taker flow ↑↑↑" in out
    assert "TRIGGERED" not in out and "ARMED" not in out and "Ready:" not in out
    assert "Price/OI history 10.0d / 30d" in out
    details = format_readiness_details(CFG, r)
    assert "<b>Taker flow</b>: ready" in details and "history building" in details


# ---- E / F: stale and degraded keep precedence ------------------------------------------------
def test_data_stale_wins_and_hides_readiness():
    r, s = ready_of(rsnap(tier="building", span=2.0))
    v = view_for(r, s, "DATA STALE")
    assert v["headline"] == "DATA STALE" and v["readiness"] is None
    out = format_btc(CFG, v)
    assert "BTC · data incomplete" in out
    assert "Detector ready" not in out and "Ready:" not in out and "Price/OI:" not in out


def test_data_degraded_wins_and_readiness_says_degraded():
    r, s = ready_of(rsnap(fresh=False))
    assert {g["status"] for g in r["groups"]} == {rd.DEGRADED}
    v = view_for(r, s, "DATA DEGRADED")
    assert v["headline"] == "DATA DEGRADED"
    out = format_btc(CFG, v)
    assert "BTC · data incomplete" in out and "degraded" not in out and "evaluation late" not in out
    details = format_readiness_details(CFG, r)
    assert details.count("degraded · evaluation late") == 3


def test_core_family_unavailable_is_detector_not_ready_not_no_active_events():
    s = rsnap()
    s["families"]["oi"]["usable"] = False
    r, s = ready_of(s)
    assert groups(r)["PRICE_OI"]["status"] == rd.UNAVAILABLE and not r["core_ready"]
    v = view_for(r, s, "NO ACTIVE EVENTS")
    assert v["headline"] == "DETECTOR NOT READY"
    out = format_btc(CFG, v)
    assert "BTC · data incomplete" in out and "NO ACTIVE EVENTS" not in out
    assert "Price/OI cannot be evaluated right now" in out
    assert "Detector ready" not in out
    assert "data unavailable · fewer than 2 usable venues for OI" in format_readiness_details(CFG, r)


def test_unavailable_input_is_never_called_history_building():
    r, _ = ready_of(rsnap(value_none=("c:taker_delta_notional_usd_sum",)))
    assert groups(r)["TAKER_FLOW"]["status"] == rd.UNAVAILABLE
    s = rsnap()
    s["families"]["taker_flow"]["usable"] = False
    r, _ = ready_of(s)
    t = groups(r)["TAKER_FLOW"]
    assert t["status"] == rd.UNAVAILABLE and t["reason"] == "FAMILY_UNUSABLE:taker_flow"


def test_disabled_rule_family_is_disabled():
    from common.versioning import _to_plain
    from beta.config import BetaConfig
    raw = _to_plain(CFG.raw)
    raw["rules"]["TAKER_FLOW_EXTREME"]["enabled"] = False
    cfg = BetaConfig.from_mapping(raw)
    s = rsnap()
    s["rule_evaluations"] = evaluate_bucket(cfg, s, None)
    r = rd.readiness(cfg, {"bucket_ts": T0, "snapshot": s}, maturity_days=MAT)
    assert groups(r)["TAKER_FLOW"]["status"] == rd.DISABLED


# ---- G: maturity boundary follows the detector exactly ----------------------------------------
@pytest.mark.parametrize("tier,expected", [("building", rd.BUILDING), ("mature", rd.READY)])
def test_ready_iff_the_rule_accepted_the_percentile(tier, expected):
    r, s = ready_of(rsnap(tiers={"c:oi_change_pct_median": tier, "c:oi_change_pct_median#span": 29.99}))
    assert groups(r)["PRICE_OI"]["status"] == expected
    assert (s["rule_evaluations"]["PRICE_OI_CONTRACTION_DOWN"]["status"] != NOT_EVALUABLE) == (expected == rd.READY)
    if expected == rd.BUILDING:
        assert groups(r)["PRICE_OI"]["progress"]["span_days"] == 29.9   # 29.99 floored, never "30.0"


def test_readiness_mirror_matches_the_rules_on_generated_snapshots():
    rng = random.Random(11)
    keys = ["c:price_move_pct_median", "c:oi_change_pct_median", "c:range_width_pct_median",
            "c:volume_notional_usd_sum", "c:taker_delta_notional_usd_sum"]
    for _ in range(400):
        tiers = {k: rng.choice(["mature", "mature", "building", "low", "none"]) for k in keys}
        s = rsnap({"price": rng.random(), "oi": rng.random(), "range": rng.random(), "volume": rng.random(),
                   "taker": rng.random()}, tiers=tiers, fresh=rng.random() > 0.1,
                  value_none=tuple(k for k in keys if rng.random() < 0.08), heartbeat=rng.random() > 0.3)
        for f in ("price_structure", "oi", "volume", "taker_flow"):
            s["families"][f]["usable"] = rng.random() > 0.08
        r, s2 = ready_of(s)
        for et in EVENT_TYPES:
            evaluable = s2["rule_evaluations"][et]["status"] != NOT_EVALUABLE
            assert (r["events"][et]["status"] == rd.READY) == evaluable, (et, r["events"][et])
            if et in rd.REQUIRED:
                own = rd._threshold_family(CFG, et, s2, T0)["status"]
                assert (own == rd.READY) == evaluable, (et, own, s2["rule_evaluations"][et])


# ---- H: readiness can never produce a push -------------------------------------------------
def test_readiness_is_imported_by_no_detection_or_delivery_module():
    for name in ("detector.py", "delivery.py", "rules.py", "outcomes.py", "state_tape.py", "health.py",
                 "models.py"):
        tree = ast.parse((REPO / "beta" / name).read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                assert "readiness" not in (n.module or ""), name
                assert all(a.name != "readiness" for a in n.names), name


# ---- I: replay determinism ----------------------------------------------------------------------
def test_same_v2_state_gives_the_same_readiness_bytes():
    s = rsnap(tiers={"c:oi_change_pct_median": "building"}, heartbeat=False)
    a, _ = ready_of(s)
    b, _ = ready_of(copy.deepcopy(s))
    assert canonical_json(a) == canonical_json(b)
    assert json.loads(json.dumps(a)) == a
    assert a["readiness_version"] == "BETA_READINESS_V0"


# ---- J: LAST EVENT is independent of readiness ------------------------------------------------
def test_last_event_is_unchanged_by_readiness():
    snaps = [rsnap(DOWN), rsnap(DOWN), rsnap(QUIET, tiers={"c:taker_delta_notional_usd_sum": "building"})]
    rows = tape(snaps)
    states = cx.replay(CFG, rows, start_bucket=T0, end_bucket=T0 + 2 * BUCKET)
    last_row = {"bucket_ts": T0 + 2 * BUCKET, "snapshot": rows[T0 + 2 * BUCKET]["snapshot"]}
    building = rd.readiness(CFG, last_row, maturity_days=MAT)
    assert groups(building)["TAKER_FLOW"]["status"] == rd.BUILDING
    v1 = view_for(building, None, "NO ACTIVE EVENTS", states)
    v2 = view_for(None, None, "NO ACTIVE EVENTS", states)
    assert v1["last_event"] == v2["last_event"] and v1["last_event"]["terminal_reason"] == "CONDITION_FAILED"
    out = format_btc(CFG, v1)
    assert "BTC · calmed" in out and "unusual drop" in out and "Positions shrank during the drop" in out
    assert "Taker flow:" not in out and "history building" not in out
    assert "history building · taker-flow history" in format_readiness_details(CFG, building)


def test_details_view_shows_tier_samples_span_and_venues():
    r, _ = ready_of(rsnap(tiers={"c:oi_change_pct_median": "building", "c:oi_change_pct_median#span": 8.0},
                          heartbeat=False))
    d = format_readiness_details(CFG, r)
    assert "OI history: building · 500 samples · 8.0d span" in d
    assert "binance: data unavailable (HEARTBEAT_UNHEALTHY)" in d
    assert "never send notifications" in d
