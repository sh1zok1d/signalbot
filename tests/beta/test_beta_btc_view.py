"""/btc from factual detector state: ACTIVE EVENT / LAST EVENT memory (C, D, E),
factual anchors per family (F, G, H), fail-closed headline, provenance (pure)."""
import json
import re
from datetime import timedelta

from test_beta_context import (BUILDUP, CFG, DOWN, QUIET, T0, cx, run, snap)

from beta.context import btc_view
from beta.formatter import format_btc, format_context_details
from beta.state_tape import BUCKET


def _product(states, status=None, reasons=()):
    s = states[-1]
    if status is None:
        opn = [e["state"] for e in s["open"].values()]
        status = "EVENT ACTIVE" if "TRIGGERED" in opn else "WATCH" if opn else "NO ACTIVE EVENTS"
    return {"status": status, "reasons": list(reasons), "last_good_bucket": cx._ts(s["as_of_bucket"])}


def _view(states, *, minutes_after=0.5, status=None, reasons=(), open_ids=None):
    s = states[-1]
    now = cx._ts(s["as_of_bucket"]) + BUCKET + timedelta(minutes=minutes_after)
    return btc_view(CFG, product=_product(states, status, reasons), state=s,
                    state_digest_value=cx.state_digest(s), now=now,
                    detector_open_ids=[e["episode_id"] for e in s["open"].values()] if open_ids is None else open_ids)


def _lines(html):
    return [l for l in re.sub(r"<[^>]+>", "", html).split("\n") if l.strip()]


# ---- C / E: a terminated detector episode appears as LAST EVENT, distinct from NOW ----------
def test_terminated_episode_is_last_event_and_now_is_a_different_bucket():
    states, _ = run([snap(DOWN, {"price": -0.91, "oi": -2.1}), snap(DOWN, {"price": -0.5}),
                     snap(QUIET, {"price": 0.21, "oi": 0.3})])
    v = _view(states)
    assert v["headline"] == "NO ACTIVE EVENTS" and v["active_episode"] is None
    assert v["last_event"]["terminal_reason"] == "CONDITION_FAILED"
    lines = _lines(format_btc(CFG, v))
    assert lines[0] == "BTC perp · NO ACTIVE EVENTS"
    assert lines[1] == "Last event: price + OI contraction down · reached triggered"
    assert lines[2] == "12:00–12:10 UTC · ended 0m ago (condition no longer met)"
    assert lines[3].startswith("Trigger bucket 12:05–12:10: price −0.50%")
    assert lines[4].startswith("Now 12:10–12:15: price +0.21%")
    assert "data through 12:15 UTC" in lines[-2]
    assert not any("EVENT ACTIVE" in l or "WATCH" in l for l in lines)
    assert len(lines) <= 9


# ---- D: LAST EVENT stays for the retention window across quiet buckets, never as active -------
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
                    now=ended_at + timedelta(minutes=retention), detector_open_ids=[])
    assert edge["last_event"] is not None
    gone = btc_view(CFG, product=_product(states), state=s, state_digest_value="x" * 64,
                    now=ended_at + timedelta(minutes=retention, seconds=1), detector_open_ids=[])
    assert gone["last_event"] is None
    assert "Last event" not in format_btc(CFG, gone)


def test_active_episode_uses_detector_vocabulary_and_qualifying_window():
    states, _ = run([snap(DOWN), snap(DOWN)])
    v = _view(states)
    assert v["headline"] == "EVENT ACTIVE" and v["last_event"] is None
    lines = _lines(format_btc(CFG, v))
    assert lines[1] == "price + OI contraction down · triggered · qualifying 12:00–12:10 UTC (2 buckets)"
    assert lines[2].startswith("Trigger bucket 12:05–12:10:")
    states, _ = run([snap(DOWN)])
    assert _view(states)["headline"] == "WATCH"


def test_headline_is_always_the_existing_product_status():
    states, _ = run([snap(DOWN), snap(DOWN)])
    for status in ("DATA DEGRADED", "DATA STALE"):
        v = _view(states, status=status)
        assert v["headline"] == status
    assert _view(states, status="DATA STALE")["now"] is None
    assert "absence of events cannot be claimed" in format_btc(CFG, _view(states, status="DATA DEGRADED"))


def test_projection_disagreeing_with_detector_shows_no_episode_details():
    states, _ = run([snap(DOWN), snap(DOWN)])
    v = _view(states, open_ids=["EV-0000000000"])
    assert v["active_episode"] is None and v["projection_available"] is False
    out = format_btc(CFG, v)
    assert "Episode details are not available" in out and "Trigger bucket" not in out


# ---- F / G / H: factual anchors per family ---------------------------------------------------
def test_taker_shows_strongest_observed_bucket():
    states, _ = run([snap({"taker": 0.99}, {"taker": 2e6}), snap({"taker": 0.99}, {"taker": 9e6})])
    out = format_btc(CFG, _view(states))
    assert "Strongest observed bucket 12:05–12:10: taker delta +$9.0M (top 1%)" in out


def test_buildup_anchor_is_opening_then_trigger_bucket_never_strongest():
    states, _ = run([snap(BUILDUP)] * 4)
    out = format_btc(CFG, _view(states))
    assert "Opening bucket 12:10–12:15:" in out and "Strongest" not in out   # detector opens at streak 3
    states, _ = run([snap(BUILDUP)] * 10)
    assert "Trigger bucket 12:40–12:45:" in format_btc(CFG, _view(states))


def test_liquidation_renders_per_venue_votes_not_a_sum():
    liq = {("binance", "long_liquidation_notional"): (5e6, 0.99),
           ("bybit", "long_liquidation_notional"): (1e6, 0.97),
           ("okx", "long_liquidation_notional"): (1e5, 0.40)}
    states, _ = run([snap(liq=liq)])
    out = format_btc(CFG, _view(states))
    assert "long-side liquidations in their top 5% on binance, bybit (2 of 3 eligible venues)" in out
    assert "$6.1M" not in out
    d = format_context_details(CFG, states[-1]["open"]["LIQUIDATION_STRESS_LONG"], states[-1])
    assert "binance $5.0M, bybit $1.0M, okx $100K" in d and "top-5% votes binance,bybit" in d


def test_single_venue_taker_extreme_shows_partial_agreement():
    signs = {"taker_delta_notional_usd": {"binance": 9e7, "bybit": -1e5, "okx": -2e5}}
    states, _ = run([snap({"taker": 0.99}, venue_signs=signs)])
    out = format_btc(CFG, _view(states))
    assert "same direction on 1/3 at the strongest observed bucket" in out


def test_details_expose_version_and_detector_state():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET)])
    s = states[-1]
    d = format_context_details(CFG, s["last_ended"]["PRICE_OI_CONTRACTION_DOWN"], s)
    assert "Detector state ended · reached triggered" in d and "condition no longer met" in d
    assert "STRICT_QUALIFICATION_V1" in d and "detector episode boundaries" in d
    assert "COOLING" not in d and "cooling" not in d


def test_view_payload_is_json_and_carries_versions():
    states, _ = run([snap(DOWN)])
    rt = json.loads(json.dumps(_view(states)))
    assert rt["episodization_version"] == "STRICT_QUALIFICATION_V1" and rt["live_hysteresis_enabled"] is False
    assert rt["context_state_digest"] == cx.state_digest(states[-1])


def test_rendering_has_no_certainty_or_trade_wording():
    states, _ = run([snap({"price": 1.0, "oi": 0.0}), snap(DOWN)])
    out = re.sub(r"<[^>]+>", " ", format_btc(CFG, _view(states)))
    assert "100th" not in out and "0th pct" not in out
    for w in ("long now", "short now", "buy", "sell", "target", "signal", "forecast", "cooling"):
        assert not re.search(rf"\b{w}\b", out, flags=re.I)
