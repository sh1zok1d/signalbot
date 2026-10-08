"""Delivery latency (backlog A4), pure: the source time of every class, nearest-rank P50/P95 with N,
detection and sending apart, expired and source-less rows counted, the push's latency field and
the owner text. Synthetic rows only."""
from datetime import datetime, timedelta, timezone

from beta import latency as lt
from beta import market_alerts as ma
from beta.hist_series import bars_from_rows

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)


def test_nearest_rank_percentiles_report_observed_values():
    assert lt.percentile([], 50) is None
    xs = [40, 41, 45, 50, 300]
    assert lt.percentile(xs, 50) == 45 and lt.percentile(xs, 95) == 300 and lt.percentile([7], 95) == 7
    assert lt.percentile(range(1, 101), 95) == 95


def _row(kind, *, src_s, decision_s, done_s, alert_kind=None, state="SENT"):
    decision = T + timedelta(seconds=decision_s)
    row = {"kind": kind, "alert_kind": alert_kind, "state": state, "decision_ts": decision,
           "finished_at": None if done_s is None else T + timedelta(seconds=done_s), "source_at": None}
    if kind == "alert" and src_s is not None:
        row["source_at"] = (T + timedelta(seconds=src_s)).isoformat()
    return row


def test_summary_by_class_with_detection_and_sending_apart():
    rows = [_row("alert", alert_kind="level", src_s=0, decision_s=40, done_s=42),
            _row("alert", alert_kind="level", src_s=0, decision_s=100, done_s=103),
            _row("alert", alert_kind="level", src_s=None, decision_s=40, done_s=41),        # recorded before A4
            _row("alert", alert_kind="level", src_s=0, decision_s=40, done_s=900, state="EXPIRED_UNDELIVERED"),
            _row("push", src_s=None, decision_s=0, done_s=45),                               # source = decision_ts
            _row("brief", src_s=None, decision_s=0, done_s=30)]
    s = lt.summarize(rows)
    lv = s["level"]
    assert (lv["n"], lv["p50_s"], lv["p95_s"], lv["max_s"]) == (2, 42.0, 103.0, 103.0)
    assert (lv["detect_p50_s"], lv["detect_p95_s"]) == (40.0, 100.0)
    assert (lv["send_p50_s"], lv["send_p95_s"]) == (2.0, 3.0)                      # the source-less row too
    assert lv["expired"] == 1 and lv["no_source"] == 1 and lv["source"] == "candle_close"
    assert s["push"]["p50_s"] == 45.0 and s["push"]["detect_p50_s"] == 0.0
    assert s["brief"]["source"] == "schedule" and s["brief"]["n"] == 1


def test_the_push_field_carries_its_own_lag_and_the_class_percentiles_with_n():
    s = lt.summarize([_row("alert", alert_kind="move", src_s=0, decision_s=40, done_s=41)])
    f = lt.latency_field("move", T, T + timedelta(seconds=52), s)
    assert f == {"class": "move", "source": "candle_close", "source_at": T.isoformat(), "lag_s": 52,
                 "p50_s": 41.0, "p95_s": 41.0, "n": 1, "messages": 1, "window_days": 7}
    assert lt.latency_field("event", T, T, {})["n"] == 0 and lt.latency_field("event", T, T, {})["p95_s"] is None
    assert lt.latency_field("level", None, T, s) is None                           # never guessed
    assert lt.alert_source_at({"source_at": T.isoformat()}) == T and lt.alert_source_at({}) is None


def test_the_owner_text_names_every_class_with_its_n():
    text = lt.format_report(lt.summarize([_row("alert", alert_kind="price", src_s=0, decision_s=40, done_s=41),
                                          _row("weekly", src_s=None, decision_s=0, done_s=5)]), days=7)
    assert text.splitlines()[0].startswith("Delivery latency, last 7 d")
    assert "price (candle_close): N=1 P50 41s P95 41s" in text and "weekly (schedule): N=1" in text
    assert "no delivered or expired messages" in lt.format_report({}, days=3)


def test_a_touch_on_a_whole_5m_bar_is_measured_from_that_bar_close():
    day0 = datetime(2026, 10, 14, tzinfo=UTC)                 # the day period opens on the grid
    rows = [{"open_time_ms": int((day0 + timedelta(minutes=5 * k)).timestamp() * 1000), "open": 100.0,
             "high": 100.0 if k < 2 else 101.5, "low": 99.5, "close": 100.0} for k in range(3)]
    b = bars_from_rows(rows)
    blk = {"price": 100.0, "levels": {"all": [{"kind": "PDH", "price": 101.0}], "above": [], "below": []},
           "corridor": {"horizons": {}}}
    out = ma.detect_level_touches(blk, b, [], now=day0 + timedelta(minutes=15, seconds=40),
                                  max_age=timedelta(minutes=10), stats=None)
    assert out[0]["payload"]["at"] == (day0 + timedelta(minutes=10)).isoformat()
    assert out[0]["payload"]["source_at"] == (day0 + timedelta(minutes=15)).isoformat()
