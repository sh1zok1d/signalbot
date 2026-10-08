"""The level alert's «Следующий уровень … за 24ч» chance follows the /btc touch-chance rule (track A).

The model's 24h chance to reach the next level is printed only in mode B, beside its own check
(«говорили → было: P → R (на истории | вживую, N=…)»), decided at detect time and carried in the payload.
In the «исторически» fallback, with no check, inside the 24h event zone or from a payload stored before
this change, the level is named without a number. Never the past-tense «доходили» for a model chance.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from beta import decision_format as df
from beta import market_alerts as ma
from beta.hist_series import bars_from_rows
from beta.i18n import assert_descriptive
from beta.rangecast import touch_bin

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
P24 = 0.42
BIN = touch_bin(P24)
HOLD_BINS = {"24h": {"touch_bins": {"bins": [{"bin": BIN, "passed": True, "predicted": 0.41, "realized": 0.39,
                                              "n_eff": 120}]}}}


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace(" ", " ").replace("\xa0", " ")


def _block(holdout=HOLD_BINS, touch_live=None):
    blk = {"price": 100.1, "levels": {"all": [{"kind": "PDH", "price": 101.0}], "below": [],
                                      "above": [{"low": 102.0, "high": 102.0, "edge": 102.0, "distance_pct": 1.9,
                                                 "kinds": ["ROUND"], "members": [{"kind": "ROUND", "price": 102.0}],
                                                 "touch": {"24h": P24, "4h": 0.2}}]},
           "corridor": {"coverage": 0.8, "horizons": {}, "holdout": holdout}}
    if touch_live is not None:
        blk["touch_live"] = touch_live
    return blk


def _detect(blk):
    day0 = datetime(2026, 10, 14, tzinfo=UTC)
    b = bars_from_rows([{"open_time_ms": int((day0 + timedelta(minutes=5 * k)).timestamp() * 1000), "open": 100.0,
                         "high": 100.5, "low": 100.0, "close": 100.0} for k in range(72)])
    closed = [{"ts": day0 + timedelta(hours=6, minutes=m), "open": 100.0, "high": 100.2 + (0.9 if m == 3 else 0),
               "low": 99.9, "close": 100.1} for m in range(5)]
    out = ma.detect_level_touches(blk, b, closed, now=day0 + timedelta(hours=6, minutes=5),
                                  max_age=timedelta(minutes=10), stats=None)
    assert len(out) == 1
    return out[0]["payload"]


def _text(payload, lang):
    return plain(df.format_alert("level", payload, lang))


def test_mode_b_prints_the_chance_with_its_held_out_check_ru_en():
    p = _detect(_block())
    assert p["next"]["touch_24h_wording"] == {"mode": "B", "source": "holdout", "bin": BIN, "predicted": 0.41,
                                              "realized": 0.39, "n_eff": 120}
    ru, en = _text(p, "ru"), _text(p, "en")
    assert "· за 24ч ≈ 42%; говорили → было: 41% → 39% (на истории, N=120)" in ru
    assert "· within 24h ≈ 42%; said → happened: 41% → 39% (on history, N=120)" in en
    assert "доходили" not in ru and "reached within" not in en
    assert len(ru.splitlines()) == len(en.splitlines())
    assert_descriptive(ru, "ru")
    assert_descriptive(en, "en")


def test_the_live_check_replaces_the_held_out_one_once_it_reaches_its_n():
    live = {"horizons": {"24h": {"bins": [{"bin": BIN, "predicted": 0.43, "realized": 0.45, "n_eff": 30}]}},
            "diverged": {}}
    ru = _text(_detect(_block(touch_live=live)), "ru")
    assert "говорили → было: 43% → 45% (вживую, N=30)" in ru


@pytest.mark.parametrize("holdout,live", [
    ({"24h": {"touch_bins": {"bins": [{"bin": BIN, "passed": False, "predicted": 0.41, "realized": 0.2,
                                       "n_eff": 120}]}}}, None),            # held-out bin did not pass
    ({}, None),                                                             # no check at all
    (HOLD_BINS, {"horizons": {}, "diverged": {"24h": [BIN]}}),              # the live bin diverged
])
def test_without_a_passing_check_the_next_level_has_no_number(holdout, live):
    p = _detect(_block(holdout=holdout, touch_live=live))
    for lang, gone in (("ru", "за 24ч"), ("en", "within 24h")):
        text = _text(p, lang)
        assert gone not in text and "42%" not in text, text
        assert ("Следующий уровень:" if lang == "ru" else "Next level:") in text


def test_a_payload_stored_before_the_check_prints_no_number():
    p = _detect(_block())
    del p["next"]["touch_24h_wording"]
    assert "42%" not in _text(p, "ru") and "42%" not in _text(p, "en")


def test_inside_the_24h_event_zone_no_number_even_in_mode_b():
    p = _detect(_block())
    p["event_zone"] = {"24h": [{"kind": "CPI", "at": T.isoformat()}]}
    assert "42%" not in _text(p, "ru")
