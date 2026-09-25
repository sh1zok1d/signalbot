"""/btc compact summary + details: NOW vs running PEAK vs 1h, headline precedence,
explicit signed values, venue agreement and version provenance (pure)."""
import json
import re
from datetime import timedelta

from test_beta_context import (CFG, DOWN, QUIET, T0, UP, cx, run, snap)

from beta.context import btc_view
from beta.formatter import format_btc, format_context_details
from beta.state_tape import BUCKET


def _view(states, status="NO ACTIVE EVENTS", now_offset=40, reasons=()):
    s = states[-1]
    last = cx._ts(s["as_of_bucket"])
    prod = {"status": status, "reasons": list(reasons), "last_good_bucket": last}
    return btc_view(CFG, product=prod, state=s, state_digest_value=cx.state_digest(s),
                    now=last + BUCKET + timedelta(seconds=now_offset))


def _lines(html):
    return [l for l in re.sub(r"<[^>]+>", "", html).split("\n") if l.strip()]


def test_cooling_summary_keeps_the_event_visible_with_peak_now_and_freshness():
    states, _ = run([snap(DOWN, {"price": -0.91, "oi": -2.1}), snap(DOWN, {"price": -0.5}),
                     snap(QUIET, {"price": 0.21, "oi": 0.3})])
    v = _view(states)
    out = format_btc(CFG, v)
    lines = _lines(out)
    assert lines[0] == "BTC perp · COOLING"
    assert lines[1].startswith("price + OI contraction down episode · triggered · since 12:05 (10m)")
    assert lines[2].startswith("Peak 12:05: price −0.91% (bottom 2%) · OI −2.10% (bottom 5%)")
    assert lines[3].startswith("Now 12:15: price +0.21%")
    assert "data through 12:15 UTC" in lines[5] and "Venues 3/3 · peak direction on 3/3" in lines[5]
    assert len(lines) <= 8                       # compact: 6 content lines + disclaimer
    assert "NORMAL" not in out and "score" not in out.lower()


def test_headline_uses_detector_vocabulary_while_active():
    states, _ = run([snap(DOWN)])
    assert _view(states)["headline"] == "WATCH"              # armed, not yet triggered
    states, _ = run([snap(DOWN), snap(DOWN)])
    assert _view(states)["headline"] == "EVENT ACTIVE"


def test_data_problems_win_the_headline_and_stale_hides_now_and_1h():
    states, _ = run([snap(DOWN), snap(DOWN)])
    v = _view(states, status="DATA DEGRADED", reasons=["FAMILY_UNUSABLE:oi"])
    assert v["headline"] == "DATA DEGRADED" and v["episode"] is not None
    assert "absence of events cannot be claimed" in format_btc(CFG, v)
    v = _view(states, status="DATA STALE")
    assert v["headline"] == "DATA STALE" and v["now"] is None and v["context_1h"] is None
    assert "Now " not in format_btc(CFG, v)


def test_no_active_event_shows_last_event_and_now():
    states, _ = run([snap(DOWN), snap(QUIET), snap(QUIET), snap(QUIET)])
    v = _view(states, now_offset=40)
    out = _lines(format_btc(CFG, v))
    assert out[0] == "BTC perp · NO ACTIVE EVENTS"
    assert any(l.startswith("Now 12:20:") for l in out)
    assert any(l.startswith("Last event: price + OI contraction down · ended") for l in out)


def test_running_peak_and_now_are_distinct_single_buckets():
    states, rows = run([snap(DOWN, {"price": -1.5, "oi": -0.4}), snap(DOWN, {"price": -0.6, "oi": -3.0})])
    v = _view(states)
    pk = v["episode"]["peak"]["view"]
    assert pk["bucket_ts"] == cx.iso(T0) and v["now"]["bucket_ts"] == cx.iso(T0 + BUCKET)
    assert pk["price_move_pct"]["value"] == -1.5 and pk["oi_change_pct"]["value"] == -0.4
    out = format_btc(CFG, v)
    assert "Peak 12:05: price −1.50%" in out and "OI −0.40%" in out
    assert "Now 12:10: price −0.60%" in out and "OI −3.00%" in out


def test_single_venue_taker_extreme_shows_partial_agreement():
    signs = {"taker_delta_notional_usd": {"binance": 9e7, "bybit": -1e5, "okx": -2e5}}
    states, _ = run([snap({"taker": 0.99}, venue_signs=signs), snap({"taker": 0.99}, venue_signs=signs)])
    out = format_btc(CFG, _view(states))
    assert "taker flow extreme (buyer-initiated) episode" in out
    assert "peak direction on 1/3" in out and "3/3" not in out.split("peak direction")[1].split("\n")[0]


def test_opposite_succession_is_described_factually():
    states, _ = run([snap(DOWN), snap(QUIET), snap(UP)])
    v = _view(states)
    assert v["episode"]["event_type"] == "PRICE_OI_CONTRACTION_UP"
    detail = format_context_details(CFG, v["episode"], states[-1])
    assert "Follows CX-" in detail and "reversal" not in detail.lower()


def test_details_expose_versions_phase_and_full_percentiles():
    states, _ = run([snap(DOWN), snap(DOWN), snap(QUIET), snap(DOWN)])
    s = states[-1]
    d = format_context_details(CFG, s["episodes"]["PRICE_OI_CONTRACTION_DOWN"], s)
    assert "Phase active · confirmation triggered" in d and "Reactivations 1" in d
    assert "BETA_EPISODES_V0" in d and "parameters unfrozen" in d
    assert "pct of 30d (mature)" in d and "Detector episodes: EV-" in d


def test_view_payload_carries_versions_and_is_json_serializable():
    states, _ = run([snap(DOWN)])
    v = _view(states)
    rt = json.loads(json.dumps(v))
    assert rt["episodization_version"] == "BETA_EPISODES_V0"
    assert rt["episode"]["episodization_digest"] == cx.KNOWN_EPISODIZATION_DIGESTS["BETA_EPISODES_V0"]
    assert rt["context_state_digest"] == cx.state_digest(states[-1])


def test_rendering_never_uses_percentile_as_certainty_or_trade_words():
    states, _ = run([snap({"price": 1.0, "oi": 0.0}), snap(DOWN)])
    out = format_btc(CFG, _view(states))
    assert "100th" not in out and "0th pct" not in out
    for w in ("long now", "short now", "buy", "sell", "target", "signal", "forecast"):
        assert not re.search(rf"\b{w}\b", re.sub(r"<[^>]+>", " ", out), flags=re.I)
