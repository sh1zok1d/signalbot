"""The level-touch push as the #352 event (architect's P2 = A, behind `level_race.push_trigger`): one switch,
the structural candidate at the touch bar's 5m close, its T0 race line in place of the hold history, the
wording and the display link. Synthetic bars only."""
import re
from datetime import timedelta

import pytest

from beta import claims as cj
from beta import level_race_live as LR
from beta import market_alerts as MA
from beta.config import BetaConfig
from beta.decision_format import format_alert
from beta.hist_series import BAR_MS
from beta.i18n import assert_descriptive
from test_level_race_live import B, EVS, FORBIDDEN, TABLE, _cfg, _cut, _ts

MAX_AGE = timedelta(minutes=10)


def _block(b, now):
    return {"available": True, "price": float(b.close[-1]), "price_ts": (now - timedelta(minutes=1)).isoformat(),
            "levels": {"above": [], "below": [], "at": None, "all": []}, "event_zone": {}}


def _event_with_line():
    for e in EVS:
        if LR.push_view(_cut(B, e["t0_ms"]), e, TABLE) is not None:
            return e
    raise AssertionError("no event with a T0 line")


def test_one_switch_legacy_by_default():
    assert LR.push_trigger(BetaConfig.load()) == "legacy"
    assert LR.push_trigger(_cfg(push_trigger="structural")) == "structural"
    with pytest.raises(Exception):
        _cfg(push_trigger="zone")
    e = EVS[0]
    b, now = _cut(B, e["t0_ms"]), _ts(e["t0_ms"] + 60_000)
    legacy = MA.level_touch_candidates(BetaConfig.load(), _block(b, now), b, [], now=now, max_age=MAX_AGE, stats=None)
    assert legacy == MA.detect_level_touches(_block(b, now), b, [], now=now, max_age=MAX_AGE, stats=None)
    assert all("trigger" not in c["payload"] for c in legacy)


def test_structural_candidate_at_the_5m_close_within_max_age():
    e = _event_with_line()
    cfg = _cfg(push_trigger="structural", display_enabled=True)

    def cands(cut_ms, now_ms):
        b = _cut(B, cut_ms)
        return [c for c in MA.level_touch_candidates(cfg, _block(b, _ts(now_ms)), b, [], now=_ts(now_ms),
                                                     max_age=MAX_AGE, stats=None)
                if c["key"] == f"level:{e['event_id']}"]
    assert cands(e["t0_ms"] - BAR_MS, e["t0_ms"] - 1) == []                   # the touch bar is not closed yet
    got = cands(e["t0_ms"], e["t0_ms"] + 30_000)
    assert len(got) == 1
    p = got[0]["payload"]
    assert p["trigger"] == "structural" and p["source_at"] == _ts(e["t0_ms"]).isoformat()
    assert p["zone_low"] == e["zone_low"] and p["zone_high"] == e["zone_high"] and p["history"] is None
    assert p["race"]["class"] == "L2_LEVEL_RACE_HIST_T0_4H" and p["race"]["landmark"] == "T0"
    assert cands(e["t0_ms"] + 15 * 60_000, e["t0_ms"] + 11 * 60_000) == []   # older than max age: not pushed


def test_t0_has_no_line_when_the_touch_close_is_outside_the_barrier_pair():
    from test_level_race_live import _bars
    e = _event_with_line()
    b = _bars()
    v = LR.landmark_view(_cut(B, e["t0_ms"]), e, "T0", TABLE)
    j = e["j"]
    b.close[j] = v["p_up"] * 1.001
    b.high[j] = max(b.high[j], b.close[j])
    assert LR.push_view(_cut(b, e["t0_ms"]), e, TABLE) is None
    rows = cj.level_race_claims([LR.landmark_view(_cut(b, e["t0_ms"]), e, "T0", TABLE)], now=_ts(e["t0_ms"]))
    assert rows[0]["eligible_reason"] == "LANDMARK_T0_OUT_OF_CORRIDOR"           # still journaled, flagged


def test_push_text_says_zone_entry_with_the_race_line_and_no_hold_history():
    e = _event_with_line()
    cfg = _cfg(push_trigger="structural", display_enabled=True)
    b, now = _cut(B, e["t0_ms"]), _ts(e["t0_ms"] + 30_000)
    c = next(x for x in MA.level_touch_candidates(cfg, _block(b, now), b, [], now=now, max_age=MAX_AGE, stats=None)
             if x["key"] == f"level:{e['event_id']}")
    for lang in ("ru", "en"):
        text = format_alert("level", c["payload"], lang)
        assert_descriptive(text, lang)
        assert not FORBIDDEN.search(re.sub(r"<[^>]+>", " ", text))
        assert ("вошла в зону" if lang == "ru" else "entered the") in text
        assert f"{e['kind']} (" in text                                   # the level named by type and name
        assert ("После первого касания" if lang == "ru" else "After the first touch") not in text
        if c["payload"]["race"]["template"] == "LR_HIST_V1":
            assert "2020–2024" in text and ("ни одна —" if lang == "ru" else "neither —") in text
            assert ("первой была —" if lang == "ru" else "reached first —") in text
        # the full line with the interval is one tap away: /levels
        rows = MA.alert_buttons("level", c["payload"], lang)
        assert any(d == "L:levels" for row in rows for _l, d in row)
    keys = cj.shown_keys("alert", None, alert={"kind": "level", "key": c["key"], "payload": c["payload"]})
    assert ("L2_LEVEL_RACE_HIST_T0_4H", f"{e['event_id']}:T0", _ts(e["t0_ms"])) in keys
    assert not [k for k in keys if k[0].startswith("L2_LEVEL_FIRST_TOUCH")]


def test_levels_show_the_t0_line_until_t15_then_the_t15_line():
    e = _event_with_line()
    blk_t0 = LR.display_block(_cut(B, e["t0_ms"]), _ts(e["t0_ms"] + 60_000), TABLE, price=float(B.close[e["j"]]))
    mine = [r for r in blk_t0["races"] if r["event_id"] == e["event_id"]]
    assert [r["landmark"] for r in mine] == ["T0"] and mine[0]["class"] == "L2_LEVEL_RACE_HIST_T0_4H"


def test_without_the_display_flag_the_structural_push_has_no_race_and_no_hold_line():
    e = _event_with_line()
    cfg = _cfg(push_trigger="structural")                                  # display_enabled stays false
    b, now = _cut(B, e["t0_ms"]), _ts(e["t0_ms"] + 30_000)
    c = next(x for x in MA.level_touch_candidates(cfg, _block(b, now), b, [], now=now, max_age=MAX_AGE, stats=None)
             if x["key"] == f"level:{e['event_id']}")
    assert c["payload"]["race"] is None and c["payload"]["history"] is None
    text = format_alert("level", c["payload"], "ru")
    assert "2020–2024" not in text and "После первого касания" not in text and "вошла в зону" in text
