"""/btc from factual detector state: open-episode and last-event memory, factual
anchors, fail-closed headline, and the compact main screen. Ranks, anchor kind,
lifecycle words, end-reason prose and per-venue detail stay in Details."""
import copy
import json
import re
from datetime import timedelta

import pytest

from test_beta_context import (BUILDUP, CFG, DOWN, EXS, QUIET, T0, UP, cx, snap)
from test_beta_context import run as _run

from beta.readiness import readiness

_LAST = {}
ALL_LIQ = {(ex, side): (2e5, 0.5) for ex in EXS
           for side in ("long_liquidation_notional", "short_liquidation_notional")}


def run(snaps):
    states, rows = _run(snaps)
    _LAST["rows"] = rows
    return states, rows


def _readiness_for(states):
    b = cx._ts(states[-1]["as_of_bucket"])
    row = _LAST["rows"].get(b)
    return readiness(CFG, None if row is None else {"bucket_ts": b, "snapshot": row["snapshot"]},
                     maturity_days=30.0)

from beta.context import btc_view
from beta.formatter import ForbiddenWordingError, btc_buttons, format_btc, format_context_details
from beta.state_tape import BUCKET

C1H = {"price_move_pct_median": -0.031, "range_width_pct_median": 0.41, "volume_notional_usd_sum": 2.4e9,
       "venues": list(EXS),
       "percentiles": {"price_move_pct_median": {"rank": None, "tier": "building"},
                       "range_width_pct_median": {"rank": None, "tier": "building"},
                       "volume_notional_usd_sum": {"rank": None, "tier": "building"}}}
# the exact key set of the persisted beta_btc_views payload (view model unchanged by layout work)
VIEW_KEYS = {"headline", "product_status", "readiness", "status_reasons", "requested_at", "as_of_bucket",
             "data_through", "projection_available", "active_episode", "other_active", "last_event", "now",
             "context_1h", "episodization_version", "episodization_digest", "live_hysteresis_enabled",
             "context_version", "context_state_digest"}
# wording that lives in Details / Readiness only, never in the compact main /btc
MOVED_TO_DETAILS = ("Trigger bucket", "Opening bucket", "Strongest observed bucket", "top ", "bottom ",
                    "pct of 30d", "condition no longer met", "at the ", "per-venue", "binance", "bybit",
                    "okx", "Detector readiness", "all families ready", "reached ", "qualifying 1")


def _product(states, status=None, reasons=()):
    s = states[-1]
    if status is None:
        opn = [e["state"] for e in s["open"].values()]
        status = "EVENT ACTIVE" if "TRIGGERED" in opn else "WATCH" if opn else "NO ACTIVE EVENTS"
    return {"status": status, "reasons": list(reasons), "last_good_bucket": cx._ts(s["as_of_bucket"])}


def _view(states, *, minutes_after=0.5, status=None, reasons=(), open_ids=None, c1h=None):
    s = states[-1]
    if c1h is not None:
        s = {**copy.deepcopy(s), "context_1h": c1h}
    now = cx._ts(s["as_of_bucket"]) + BUCKET + timedelta(minutes=minutes_after)
    return btc_view(CFG, product=_product(states, status, reasons), state=s,
                    state_digest_value=cx.state_digest(s), now=now, readiness=_readiness_for(states),
                    detector_open_ids=[e["episode_id"] for e in s["open"].values()] if open_ids is None else open_ids)


def _lines(html):
    return [l for l in re.sub(r"<[^>]+>", "", html).split("\n") if l.strip()]


def _event_block(html):
    """Plain lines of the ACTIVE/LAST EVENT section (header excluded)."""
    blocks = [b.split("\n") for b in re.sub(r"<[^>]+>", "", html).split("\n\n")]
    block = next((b for b in blocks if b[0] in ("ACTIVE EVENT", "LAST EVENT")), None)
    return block[1:] if block else []


def _assert_compact(html):
    main = re.sub(r"<[^>]+>", "", html)
    for w in MOVED_TO_DETAILS:
        if w in ("top ", "bottom "):            # NOW keeps its own tail label; the event block never does
            assert not any(w in l for l in _event_block(html)), (w, html)
        else:
            assert w not in main, (w, main)


# ---- 1 / C / E: NO ACTIVE EVENTS + LAST EVENT + READY, in the target shape ---------------------
def test_last_event_ready_renders_the_compact_target_shape():
    states, _ = run([snap(UP, {"price": 0.20, "oi": -0.10}, liq=ALL_LIQ),
                     snap(QUIET, {"price": -0.02, "oi": 0.0}, liq=ALL_LIQ)])
    v = _view(states, minutes_after=21.5, c1h=C1H)
    assert v["headline"] == "NO ACTIVE EVENTS" and v["last_event"]["terminal_reason"] == "CONDITION_FAILED"
    out = format_btc(CFG, v)
    assert out.split("\n\n<i>")[0].split("\n") == [
        "<b>BTC · calmed</b>",
        "22m ago: unusual rise",
        "Price ↑↑ · OI ↓↓",
        "Positions shrank during the rise",
        "1h activity: history building",
        "Event has ended",
        "Data through 12:10 UTC"]
    _assert_compact(out)
    assert btc_buttons(v)[0][0] == ("Details", "c:" + v["last_event"]["episode_id"])


def test_terminated_episode_is_last_event_and_now_is_a_different_bucket():
    states, _ = run([snap(DOWN, {"price": -0.91, "oi": -2.1}), snap(DOWN, {"price": -0.5}),
                     snap(QUIET, {"price": 0.21, "oi": 0.3})])
    v = _view(states)
    assert v["headline"] == "NO ACTIVE EVENTS" and v["active_episode"] is None
    out = format_btc(CFG, v)
    assert "BTC · calmed" in out and "just ended: unusual drop" in out
    assert "Price ↓↓ · OI ↓↓" in out and "Positions shrank during the drop" in out
    assert "Event has ended" in out and "Data through 12:15 UTC" in out
    assert "TRIGGERED" not in out and "ARMED" not in out
    assert "Price +0.21%" not in out
    d = format_context_details(CFG, v["last_event"], states[-1])
    assert "price move: −0.50%" in d and "0.21" in d
    assert "Price +0.21%" not in out
    _assert_compact(out)


def test_abnormal_termination_keeps_its_reason_on_the_main_view():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET)])
    s = copy.deepcopy(states[-1])
    s["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]["terminal_reason"] = "DETECTION_GAP"
    v = btc_view(CFG, product=_product(states), state=s, state_digest_value=cx.state_digest(s),
                 now=cx._ts(s["as_of_bucket"]) + BUCKET, readiness=_readiness_for(states), detector_open_ids=[])
    out = format_btc(CFG, v)
    assert "BTC · event ended" in out and "A recent event ended on a data gap" in out
    assert "BTC · calmed" not in out
    assert "detection gap" in format_context_details(CFG, v["last_event"], s)


# ---- 8 / D: LAST EVENT stays for the retention window, then no event section at all -----------
def test_last_event_retained_across_quiet_buckets_then_dropped():
    retention = CFG.section("context")["last_event_retention_min"]
    states, _ = run([snap(DOWN), snap(DOWN)] + [snap(QUIET)] * 5)
    ended_at = cx._ts(states[-1]["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]["terminal_at"])
    for s_idx in range(2, 7):
        v = _view(states[:s_idx + 1])
        assert v["last_event"] is not None and v["active_episode"] is None
        assert v["headline"] == "NO ACTIVE EVENTS"
    s = states[-1]
    edge = btc_view(CFG, product=_product(states), state=s, state_digest_value="x" * 64,
                    now=ended_at + timedelta(minutes=retention), detector_open_ids=[],
                    readiness=_readiness_for(states))
    assert edge["last_event"] is not None and "BTC · calmed" in format_btc(CFG, edge)
    gone = btc_view(CFG, product=_product(states), state=s, state_digest_value="x" * 64,
                    now=ended_at + timedelta(minutes=retention, seconds=1), detector_open_ids=[],
                    readiness=_readiness_for(states))
    assert gone["last_event"] is None
    out = format_btc(CFG, gone)
    assert "BTC · calm" in out and "unusual drop" not in out and "No notable event in the last 2h" in out


# ---- 2 / 3: ACTIVE EVENT keeps the detector level, qualifying window and bucket count ----------
def test_active_episode_uses_detector_vocabulary_and_qualifying_window():
    states, _ = run([snap(DOWN), snap(DOWN)])
    v = _view(states)
    assert v["headline"] == "EVENT ACTIVE" and v["last_event"] is None
    out = format_btc(CFG, v)
    assert "BTC · unusual now" in out and "Still active" in out and "LAST EVENT" not in out
    assert "Price ↓↓ · OI ↓↓" in out and "TRIGGERED" not in out and "ARMED" not in out
    d = format_context_details(CFG, v["active_episode"], states[-1])
    assert "reached triggered" in d and "qualifying 12:00–12:10 UTC" in d
    _assert_compact(out)
    states, _ = run([snap(DOWN)])
    v = _view(states)
    assert v["headline"] == "WATCH"
    out = format_btc(CFG, v)
    assert "BTC · unusual now" in out and "Still active" in out and "ARMED" not in out
    assert "reached armed" in format_context_details(CFG, v["active_episode"], states[-1])


def test_multiple_active_events_list_the_others():
    states, _ = run([snap({**DOWN, "taker": 0.01}), snap({**DOWN, "taker": 0.01})])
    v = _view(states)
    assert len(v["other_active"]) == 1
    out = format_btc(CFG, v)
    assert "BTC · unusual now" in out and "TRIGGERED" not in out
    assert "Also open: seller-initiated flow" in out


# ---- 6 / 7: fail-closed headline precedence is unchanged --------------------------------------
def test_headline_is_always_the_existing_product_status():
    states, _ = run([snap(DOWN), snap(DOWN)])
    for status in ("DATA DEGRADED", "DATA STALE"):
        v = _view(states, status=status)
        assert v["headline"] == status
        out = format_btc(CFG, v)
        assert _lines(out)[:2] == ["BTC · data incomplete", "Current observability is insufficient; "
                                   "the absence of events cannot be claimed right now."]
        _assert_compact(out)
    stale = _view(states, status="DATA STALE")
    assert stale["now"] is None and stale["context_1h"] is None and stale["readiness"] is None
    out = format_btc(CFG, stale)
    assert "NOW · 5m" not in out and "1H CONTEXT" not in out and "Venues" not in out
    assert "Detector ready" not in out and "Ready:" not in out
    assert "1h activity" not in format_btc(CFG, _view(states, status="DATA DEGRADED"))


def test_projection_disagreeing_with_detector_shows_no_episode_details():
    states, _ = run([snap(DOWN), snap(DOWN)])
    v = _view(states, open_ids=["EV-0000000000"])
    assert v["active_episode"] is None and v["projection_available"] is False
    out = format_btc(CFG, v)
    assert "Episode details are not available" in out and "<b>ACTIVE EVENT</b>" not in out
    assert "No evaluation yet" in out


# ---- 9: incomplete vs complete rolling 1h ----------------------------------------------------
def test_incomplete_1h_is_stated_and_complete_1h_uses_level_labels():
    states, _ = run([snap(QUIET)])
    out = format_btc(CFG, _view(states))
    assert "BTC · calm" in out and "1h activity: incomplete" in out
    mature = copy.deepcopy(C1H)
    mature["percentiles"]["range_width_pct_median"] = {"rank": 0.96, "tier": "mature"}
    mature["percentiles"]["volume_notional_usd_sum"] = {"rank": 0.50, "tier": "mature"}
    lines = _lines(format_btc(CFG, _view(states, c1h=mature)))
    assert "1h volume: normal · range: high" in lines
    assert "0.96" not in "\n".join(lines) and "pct" not in "\n".join(lines)


# ---- F / G / H: factual anchors per family (raw values on main, ranks in Details) -------------
def test_taker_shows_strongest_observed_bucket_values_and_details_keep_the_rank():
    states, _ = run([snap({"taker": 0.99}, {"taker": 2e6}), snap({"taker": 0.99}, {"taker": 9e6})])
    out = format_btc(CFG, _view(states))
    assert "Taker flow ↑↑↑" in out and "TRIGGERED" not in out
    _assert_compact(out)
    d = format_context_details(CFG, states[-1]["open"]["TAKER_FLOW_EXTREME_BUY"], states[-1])
    assert "<b>Strongest observed bucket</b> 12:05–12:10 UTC" in d and "taker delta: +$9.0M · 99.0 pct of 30d" in d


def test_buildup_anchor_is_opening_then_trigger_bucket_never_strongest():
    states, _ = run([snap(BUILDUP)] * 4)
    out = format_btc(CFG, _view(states))
    assert "OI ↑" in out and "Open interest elevated" in out and "ARMED" not in out and "EARLY" not in out
    assert "<b>Opening bucket</b> 12:10–12:15" in format_context_details(
        CFG, states[-1]["open"]["POSITION_BUILDUP_COMPRESSION"], states[-1])
    states, _ = run([snap(BUILDUP)] * 10)
    assert "<b>Trigger bucket</b> 12:40–12:45" in format_context_details(
        CFG, states[-1]["open"]["POSITION_BUILDUP_COMPRESSION"], states[-1])
    out = format_btc(CFG, _view(states))
    assert "OI ↑" in out and "TRIGGERED" not in out
    assert "range width: 0.20%" in format_context_details(
        CFG, states[-1]["open"]["POSITION_BUILDUP_COMPRESSION"], states[-1])


def test_liquidation_renders_vote_count_not_a_sum_and_details_keep_the_venues():
    liq = {("binance", "long_liquidation_notional"): (5e6, 0.99),
           ("bybit", "long_liquidation_notional"): (1e6, 0.97),
           ("okx", "long_liquidation_notional"): (1e5, 0.40)}
    states, _ = run([snap(liq=liq)])
    out = format_btc(CFG, _view(states))
    assert "Long-side liquidations 2/3 venues" in out and "TRIGGERED" not in out
    assert "$6.1M" not in out
    _assert_compact(out)
    d = format_context_details(CFG, states[-1]["open"]["LIQUIDATION_STRESS_LONG"], states[-1])
    assert "binance $5.0M, bybit $1.0M, okx $100K" in d and "top-5% votes binance,bybit" in d


def test_single_venue_taker_extreme_shows_partial_agreement_but_not_unanimous():
    signs = {"taker_delta_notional_usd": {"binance": 9e7, "bybit": -1e5, "okx": -2e5}}
    states, _ = run([snap({"taker": 0.99}, venue_signs=signs)])
    out = format_btc(CFG, _view(states))
    assert "binance" not in out and "pushing" not in out
    d = format_context_details(CFG, states[-1]["open"]["TAKER_FLOW_EXTREME_BUY"], states[-1])
    assert "taker delta by venue: up binance · down bybit,okx" in d
    states, _ = run([snap({"taker": 0.99})])
    out = format_btc(CFG, _view(states))
    assert "binance" not in out


def test_facts_moved_off_the_main_view_are_all_in_details():
    states, _ = run([snap(DOWN, {"price": -0.91, "oi": -2.1}), snap(DOWN, {"price": -0.5}),
                     snap(QUIET, {"price": 0.21, "oi": 0.3})])
    s = states[-1]
    d = format_context_details(CFG, s["last_ended"]["PRICE_OI_CONTRACTION_DOWN"], s)
    assert "<b>Trigger bucket</b> 12:05–12:10 UTC" in d                        # anchor kind
    assert "price move: −0.50% · 2.0 pct of 30d (mature)" in d                  # anchor rank
    assert "condition no longer met" in d                                       # end reason
    assert "price by venue: up — · down binance,bybit,okx" in d                 # venue agreement
    assert "reached triggered" in d


def test_details_expose_version_and_detector_state():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET)])
    s = states[-1]
    d = format_context_details(CFG, s["last_ended"]["PRICE_OI_CONTRACTION_DOWN"], s)
    assert "Detector state ended · reached triggered" in d and "condition no longer met" in d
    assert "STRICT_QUALIFICATION_V1" in d and "detector episode boundaries" in d
    assert "COOLING" not in d and "cooling" not in d


# ---- 10 / 13: deterministic rendering of an unchanged, persistable view payload ---------------
def test_view_payload_is_json_and_carries_versions():
    states, _ = run([snap(DOWN)])
    v = _view(states)
    rt = json.loads(json.dumps(v))
    assert set(rt) == VIEW_KEYS
    assert rt["episodization_version"] == "STRICT_QUALIFICATION_V1" and rt["live_hysteresis_enabled"] is False
    assert rt["context_state_digest"] == cx.state_digest(states[-1])


def test_render_is_deterministic_and_identical_from_the_stored_payload():
    states, _ = run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ), snap(QUIET, liq=ALL_LIQ)])
    again, _ = run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ), snap(QUIET, liq=ALL_LIQ)])
    for st in (states, states[:2], states[:1]):
        v = _view(st, c1h=C1H)
        out = format_btc(CFG, v)
        assert format_btc(CFG, v) == out
        assert format_btc(CFG, json.loads(json.dumps(v))) == out     # what beta_btc_views stores re-renders the same
    assert format_btc(CFG, _view(again, c1h=C1H)) == format_btc(CFG, _view(states, c1h=C1H))


# ---- 11: descriptive wording only ------------------------------------------------------------
def test_rendering_has_no_certainty_or_trade_wording():
    for snaps in ([snap({"price": 1.0, "oi": 0.0}), snap(DOWN)], [snap({"taker": 0.99})] * 2,
                  [snap({"taker": 0.01})] * 2, [snap(BUILDUP)] * 4):
        states, _ = run(snaps)
        out = re.sub(r"<[^>]+>", " ", format_btc(CFG, _view(states, c1h=C1H)))
        assert "100th" not in out and "0th pct" not in out
        for w in ("long now", "short now", "buy", "sell", "target", "signal", "forecast", "cooling",
                  "bullish", "bearish", "confidence", "score", "confirmation"):
            assert not re.search(rf"\b{w}\b", out, flags=re.I), (w, out)


def test_main_screen_is_short_and_makes_no_forecast():
    states, _ = run([snap(QUIET, liq=ALL_LIQ)])
    calm = _view(states)
    states, _ = run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ)])
    active = _view(states)
    states, _ = run([snap(UP, liq=ALL_LIQ), snap(QUIET, liq=ALL_LIQ)])
    ended = _view(states, minutes_after=21.5, c1h=C1H)
    for v in (calm, active, ended):
        plain = re.sub(r"<[^>]+>", "", format_btc(CFG, v))
        body = [l for l in plain.split("\n") if l.strip() and not l.startswith("Experimental")]
        assert 4 <= len(body) <= 8, body
        for line in body:
            assert len(line) <= 72, line
        for w in ("ARMED", "TRIGGERED", "EARLY", "pct", "NO ACTIVE EVENTS", "percentile"):
            assert w not in plain, (w, plain)
        for w in ("probably", "likely", "continuation", "reversal", "forecast", "predict",
                  "buy", "sell", "edge"):
            assert not re.search(rf"\b{w}\b", plain, flags=re.I), (w, plain)
    assert btc_buttons(calm) == [[("Details", "n:latest")]]
    assert btc_buttons(active) == [[("Details", "c:" + active["active_episode"]["episode_id"])]]
    assert btc_buttons(ended) == [[("Details", "c:" + ended["last_event"]["episode_id"])]]


def test_format_btc_still_enforces_assert_descriptive():
    states, _ = run([snap(DOWN)])
    v = _view(states)
    with pytest.raises(ForbiddenWordingError):
        format_btc(CFG, {**v, "headline": "BUY NOW"})
