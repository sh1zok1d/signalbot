"""The 4h corridor in level and price alerts is a forecast: it carries its record (track A, item 1).

Same rule as /btc (`decision_format.corridor_record`): the live 30-day share inside once its independent
windows reach MIN_N_SHOWN, else the held-out share with its days. A payload without a record — stored
before this change, or none computable — shows the corridor only as «сейчас», never as a forecast.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from beta import decision_format as df
from beta import market_alerts as ma
from beta.hist_series import bars_from_rows
from beta.i18n import assert_descriptive

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
CORR = {"lower": 61000.0, "upper": 62000.0, "half_width_pct": 0.8}
HOLD = {"coverage": 0.8, "live": {"4h": None}, "holdout": {"4h": {"coverage_realized": 0.81, "n_days": 365}}}
LIVE = {"coverage": 0.8, "live": {"4h": {"INSIDE": 120, "OUTSIDE": 40, "N_EFF": 40}},
        "holdout": {"4h": {"coverage_realized": 0.81, "n_days": 365}}}


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace(" ", " ").replace("\xa0", " ")


def _payload(kind, track):
    base = {"at": T.isoformat(), "price": 61500.0, "price_ts": T.isoformat(), "event_zone": {},
            "corridor_4h": CORR, "corridor_4h_track": track}
    if kind == "level":
        return {**base, "level_kind": "PDH", "level": 61500.0, "side": 1, "period": "day", "history": None,
                "next": None}
    return {**base, "level": 61500.0, "late": False}


@pytest.mark.parametrize("kind", ["level", "price"])
def test_the_4h_corridor_carries_its_held_out_record(kind):
    ru = plain(df.format_alert(kind, _payload(kind, HOLD), "ru"))
    en = plain(df.format_alert(kind, _payload(kind, HOLD), "en"))
    assert "Коридор 4ч: 61 000–62 000 (±0,8%) · внутри бывало 81% на истории (365 дн.) (расчёт — 80%)" in ru
    assert "4h corridor: 61,000–62,000 (±0.8%) · inside 81% on history (365 days) (designed for 80%)" in en
    assert len(ru.splitlines()) == len(en.splitlines())                 # RU/EN equal, the record on the same line
    assert_descriptive(ru, "ru")
    assert_descriptive(en, "en")


@pytest.mark.parametrize("kind", ["level", "price"])
def test_the_live_record_replaces_the_held_out_one_once_it_reaches_min_n(kind):
    ru = plain(df.format_alert(kind, _payload(kind, LIVE), "ru"))
    en = plain(df.format_alert(kind, _payload(kind, LIVE), "en"))
    assert "· внутри бывало 75% вживую за 30 дн. (N=40) (расчёт — 80%)" in ru
    assert "· inside 75% live over 30 days (N=40) (designed for 80%)" in en
    below = {**LIVE, "live": {"4h": {"INSIDE": 20, "OUTSIDE": 5, "N_EFF": df.MIN_N_SHOWN - 1}}}
    assert "81% на истории (365 дн.)" in plain(df.format_alert(kind, _payload(kind, below), "ru"))


@pytest.mark.parametrize("kind", ["level", "price"])
@pytest.mark.parametrize("track", [None, {"coverage": None}, {**HOLD, "holdout": {"4h": {}}}])
def test_without_a_record_the_corridor_is_only_now_never_a_bare_forecast(kind, track):
    ru = plain(df.format_alert(kind, _payload(kind, track), "ru"))
    en = plain(df.format_alert(kind, _payload(kind, track), "en"))
    assert "Коридор 4ч сейчас: 61 000–62 000 (±0,8%)" in ru and "Коридор 4ч:" not in ru
    assert "4h corridor now: 61,000–62,000 (±0.8%)" in en and "4h corridor:" not in en


def test_a_bare_4h_corridor_line_is_never_printed():
    """Every alert line naming the 4h corridor either carries a record or says «сейчас»."""
    for kind in ("level", "price"):
        for track in (None, HOLD, LIVE):
            for lang, bare, ok in (("ru", "Коридор 4ч:", ("внутри бывало",)), ("en", "4h corridor:", ("inside",))):
                for line in plain(df.format_alert(kind, _payload(kind, track), lang)).splitlines():
                    if bare in line:
                        assert any(w in line for w in ok), line


def test_corridor_record_is_the_btc_rule():
    assert df.corridor_record(LIVE, "4h") == ("live", 0.75, 40)
    assert df.corridor_record(HOLD, "4h") == ("hold", 0.81, 365)
    assert df.corridor_record({"live": {}, "holdout": {}}, "4h") is None


# ---- the detectors carry the record into the payload (rendered later, at send time) ----------
def _grid(start, closes, highs):
    return bars_from_rows([{"open_time_ms": int((start + timedelta(minutes=5 * k)).timestamp() * 1000), "open": c,
                            "high": highs[k], "low": c, "close": c} for k, c in enumerate(closes)])


BLOCK_CORRIDOR = {"coverage": 0.8, "horizons": {"4h": CORR},
                  "live": {"4h": {"INSIDE": 120, "OUTSIDE": 40, "N_EFF": 40}, "1h": {"INSIDE": 1}},
                  "holdout": {"4h": {"coverage_realized": 0.81, "n_days": 365, "touch_bins": [1, 2]},
                              "24h": {"coverage_realized": 0.7}}}


def test_level_and_price_detectors_put_the_4h_record_in_the_payload():
    day0 = datetime(2026, 10, 14, tzinfo=UTC)
    b = _grid(day0, [100.0] * 72, [100.5] * 72)
    closed = [{"ts": day0 + timedelta(hours=6, minutes=m), "open": 100.0, "high": 100.2 + (0.9 if m == 3 else 0),
               "low": 99.9, "close": 100.1} for m in range(5)]
    blk = {"price": 100.1, "levels": {"all": [{"kind": "PDH", "price": 101.0}], "above": [], "below": []},
           "corridor": BLOCK_CORRIDOR}
    out = ma.detect_level_touches(blk, b, closed, now=day0 + timedelta(hours=6, minutes=5),
                                  max_age=timedelta(minutes=10), stats=None)
    want = {"coverage": 0.8, "live": {"4h": {"INSIDE": 120, "OUTSIDE": 40, "N_EFF": 40}},
            "holdout": {"4h": {"coverage_realized": 0.81, "n_days": 365}}}
    assert out[0]["payload"]["corridor_4h_track"] == want                # the 4h horizon only, nothing else
    alert = {"price_alert_pk": 7, "user_pk": 3, "price": 100.9, "direction": "above",
             "created_at": day0 + timedelta(hours=5)}
    pout = ma.detect_price_alerts([alert], b, closed, block=blk)
    assert pout[0]["payload"]["corridor_4h_track"] == want
    # no 4h corridor (inside its event zone, or no model): no record either
    blk2 = {**blk, "corridor": {**BLOCK_CORRIDOR, "horizons": {}}}
    assert ma.detect_price_alerts([alert], b, closed, block=blk2)[0]["payload"]["corridor_4h_track"] is None


def test_a_held_out_record_without_its_days_is_no_record():
    """Never «(0 дн.)»: a held-out share without a positive n_days is not printed (ОПГ-1 review of #402)."""
    for nd in (None, 0):
        tr = {"coverage": 0.8, "live": {}, "holdout": {"4h": {"coverage_realized": 0.81, "n_days": nd}}}
        assert df.corridor_record(tr, "4h") is None
        assert "Коридор 4ч сейчас:" in plain(df.format_alert("price", _payload("price", tr), "ru"))
