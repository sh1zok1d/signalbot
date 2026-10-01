"""Fail-closed product status, venue heartbeat, and forward outcome computation (pure)."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig, BetaSwitches
from beta.health import (health_alerts, ingestion_heartbeat, outage_intervals, outage_overlaps,
                         product_status, venue_states)
from beta.models import Episode
from beta.outcomes import compute_outcome

CFG = BetaConfig.load().with_overrides(enabled=True)
T = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
FAMS = {f: {"usable": True} for f in ("price_structure", "oi", "volume")}
GOOD = {"materialized": True, "stale_barrier": False, "evaluation_fresh": True, "families": FAMS}
HB_OK = {"healthy": True}


class _E:
    def __init__(self, state):
        self.state = state


def _st(now, snap=GOOD, eps=(), hb=HB_OK, bucket=T):
    return product_status(CFG, now=now, latest_live={"bucket_ts": bucket, "snapshot": snap},
                          open_episodes=eps, heartbeat=hb)["status"]


def test_no_active_events_only_when_everything_fresh():
    now = T + timedelta(minutes=5, seconds=40)
    assert _st(now) == "NO ACTIVE EVENTS"
    assert _st(now, eps=[_E("ARMED")]) == "WATCH"
    assert _st(now, eps=[_E("EARLY"), _E("TRIGGERED")]) == "EVENT ACTIVE"


def test_stale_state_is_data_stale_never_no_active():
    assert _st(T + timedelta(minutes=5, seconds=421)) == "DATA STALE"
    assert product_status(CFG, now=T, latest_live=None, open_episodes=[], heartbeat=HB_OK)["status"] == "DATA STALE"


@pytest.mark.parametrize("snap,hb", [
    ({**GOOD, "materialized": False}, HB_OK),
    ({**GOOD, "stale_barrier": True}, HB_OK),
    ({**GOOD, "evaluation_fresh": False}, HB_OK),
    ({**GOOD, "families": {**FAMS, "oi": {"usable": False}}}, HB_OK),
    (GOOD, {"healthy": False}),
])
def test_degraded_paths(snap, hb):
    assert _st(T + timedelta(minutes=6), snap=snap, hb=hb) == "DATA DEGRADED"


def test_outage_intervals_and_overlap():
    ev = [{"event_type": "disconnect", "ts": T + timedelta(minutes=4), "detail": {"idle_seconds": 180}},
          {"event_type": "restore", "ts": T + timedelta(minutes=10), "detail": {}}]
    assert outage_intervals(ev) == [(T + timedelta(minutes=1), T + timedelta(minutes=10))]
    assert outage_overlaps(ev, T, T + timedelta(minutes=5))
    assert not outage_overlaps(ev, T + timedelta(minutes=10), T + timedelta(minutes=15))
    open_ev = [{"event_type": "disconnect", "ts": T - timedelta(hours=1), "detail": {"idle_seconds": 200}}]
    assert outage_overlaps(open_ev, T, T + timedelta(minutes=5))


def test_venue_heartbeat_needs_five_live_bars_and_no_outage():
    rows = {"binance": {"live_bars": 5, "bars": 5, "events": []},
            "bybit": {"live_bars": 4, "bars": 5, "events": []},
            "okx": {"live_bars": 5, "bars": 5, "events": [{"event_type": "disconnect", "ts": T + timedelta(minutes=3),
                                                             "detail": {"idle_seconds": 120}}]}}
    v = venue_states(CFG, rows, {"binance": True, "bybit": True, "okx": True}, T)
    assert v["binance"]["heartbeat_healthy"] and not v["bybit"]["heartbeat_healthy"]
    assert not v["okx"]["heartbeat_healthy"]


def test_ingestion_heartbeat_min_two_venues():
    now = T + timedelta(minutes=2)
    assert ingestion_heartbeat(CFG, now, {"binance": T, "okx": T})["healthy"]
    assert not ingestion_heartbeat(CFG, now, {"binance": T})["healthy"]
    assert not ingestion_heartbeat(CFG, now + timedelta(hours=1), {"binance": T, "okx": T})["healthy"]


def test_health_alerts_cover_components():
    sw = BetaSwitches(True, True, False, True)
    a = health_alerts(CFG, now=T, heartbeat={"healthy": False}, detector_watermark=None,
                      latest_live={"snapshot": {"materialized": False}}, runtime={}, delivery_problems=5,
                      switches=sw, d7_newest_available_at=T)
    keys = {x["key"] for x in a}
    assert keys == {"INGESTION_STALE", "DETECTOR_NOT_ADVANCING", "MATERIALIZATION_FAILURE",
                    "OUTCOME_TRACKER_NOT_ADVANCING", "BOT_RECEIVER_DOWN", "NOTIFIER_NOT_RUNNING",
                    "DELIVERY_FAILURE_SPIKE"}


def test_no_telegram_mode_skips_only_telegram_liveness_alerts():
    kw = dict(now=T, heartbeat={"healthy": False}, detector_watermark=None,
              latest_live={"snapshot": {"materialized": False}}, runtime={}, delivery_problems=5,
              d7_newest_available_at=T)
    shadow = {x["key"] for x in health_alerts(CFG, switches=BetaSwitches(True, True, False, True, False), **kw)}
    assert shadow == {"INGESTION_STALE", "DETECTOR_NOT_ADVANCING", "MATERIALIZATION_FAILURE",
                      "OUTCOME_TRACKER_NOT_ADVANCING", "DELIVERY_FAILURE_SPIKE"}
    # healthy components: shadow mode reports nothing, Telegram mode still flags a stalled bot
    fresh = {"outcomes": {"last_success_at": T}, "notifier": {"last_success_at": T}}
    ok = dict(now=T, heartbeat={"healthy": True}, detector_watermark=T - timedelta(minutes=5),
              latest_live={"snapshot": {"materialized": True}}, runtime=fresh, delivery_problems=0,
              d7_newest_available_at=T)
    assert health_alerts(CFG, switches=BetaSwitches(True, True, False, True, False), **ok) == []
    assert [x["key"] for x in health_alerts(CFG, switches=BetaSwitches(True, True, False, True), **ok)] \
        == ["BOT_RECEIVER_DOWN"]


def _kl(ex, start, n, f):
    return [{"exchange": ex, "ts": start + timedelta(minutes=i), **f(i)} for i in range(n)]


def test_outcome_symmetric_factual_values():
    f = lambda i: {"high": 100 + i, "low": 100 - 2 * i, "close": 100 + 0.5 * i}   # noqa: E731
    kl = _kl("binance", T, 15, f) + _kl("okx", T, 15, f)
    o = compute_outcome(anchor=T, horizon="15m", reference_price=100.0, exchanges=["binance", "okx"], klines=kl)
    assert o["status"] == "COMPLETE" and o["bars_complete"] == 15
    assert o["max_up_pct"] == pytest.approx(14.0) and o["max_down_pct"] == pytest.approx(28.0)
    assert o["realized_range_pct"] == pytest.approx(42.0) and o["close_return_pct"] == pytest.approx(7.0)
    assert o["time_to_max_up_s"] == 15 * 60 and o["time_to_max_down_s"] == 15 * 60
    assert not {"mfe", "mae", "win", "loss", "direction"} & {k.lower() for k in o}


def test_outcome_incomplete_and_reference_unavailable():
    f = lambda i: {"high": 101, "low": 99, "close": 100}   # noqa: E731
    kl = _kl("binance", T, 15, f) + _kl("okx", T, 14, f)
    assert compute_outcome(anchor=T, horizon="15m", reference_price=100.0, exchanges=["binance", "okx"],
                           klines=kl)["status"] == "INCOMPLETE_DATA"
    assert compute_outcome(anchor=T, horizon="15m", reference_price=None, exchanges=[],
                           klines=kl)["status"] == "REFERENCE_UNAVAILABLE"
    # bars after the window never count
    late = _kl("okx", T + timedelta(minutes=15), 1, f)
    assert compute_outcome(anchor=T, horizon="15m", reference_price=100.0, exchanges=["binance", "okx"],
                           klines=kl + late)["status"] == "INCOMPLETE_DATA"
