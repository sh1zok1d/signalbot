"""/check — the full version (PRE_BETA_SCOPE_DECISION_V1 §5): parsing, wording «B» and its fallback,
two levels with «ни один», context lines, buttons (pure)."""
import re
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from beta import check as ck
from beta import rangecast as rc
from beta.i18n import assert_descriptive

UTC = timezone.utc
NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
PRICE = 62480.0
Q = [3.0 * p for p in rc.P_GRID]                        # z uniform on [0, 3]: chances spread over the bins


def _joint():
    lv = np.array(rc.JOINT_LEVELS)
    u = np.interp(lv, rc.P_GRID, Q)
    return {"u": list(u), "v": list(u), "F": [[float(a * b) for b in lv] for a in lv]}   # independent margins


MODEL = {"version": rc.RANGE_MODEL_VERSION, "coverage": 0.8,
         "horizons": {h: {"q_one": Q, "q_joint": _joint(), "n_days": 2100} for h in ("1h", "4h", "24h")}}


def _bins(passed=True):
    return {"bins": [{"bin": list(b), "n_eff": 400, "predicted": (b[0] + b[1]) / 2, "realized": (b[0] + b[1]) / 2 + 0.01,
                      "passed": passed} for b in zip(rc.TOUCH_CAL_BINS[:-1], [min(x, 1.0) for x in rc.TOUCH_CAL_BINS[1:]])]}


def _zone(kinds, edge, dist, hist=None):
    return {"low": edge, "high": edge, "edge": edge, "distance_pct": dist, "kinds": kinds,
            "members": [{"kind": k, "price": edge} for k in kinds], "touch": {"4h": 0.3, "24h": 0.6}, "history": hist}


HIST = {"verdicts": {"1h": "as_usual"}, "ci95": {"1h": [-0.012, 0.091]}, "real": {"n": 812, "1h": {"hold_rate": 0.47, "further_median": 0.5, "back_median": 0.4}},
        "control": {"n": 4000, "1h": {"hold_rate": 0.43, "further_median": 0.3, "back_median": 0.25}}}


def block(passed=True, **over):
    hz = {h: {"scale_pct": s, "half_width_pct": s * 1.2, "lower": 60000.0, "upper": 64000.0, "typical_move_pct": s / 2}
          for h, s in (("1h", 0.6), ("4h", 1.2), ("24h", 3.0))}
    b = {"available": True, "price": PRICE, "price_ts": NOW.isoformat(),
         "corridor": {"coverage": 0.8, "horizons": hz,
                      "holdout": {h: {"touch_bins": _bins(passed), "neither_bins": _bins(passed)} for h in hz}},
         "event_zone": {}, "events": [{"kind": "CPI", "at": "2026-10-14T12:30:00+00:00", "stats": None}],
         "levels": {"above": [_zone(["PDH"], 62950.0, 0.75, HIST), _zone(["ROUND"], 65000.0, 4.03)],
                    "below": [_zone(["ASIA_L"], 61900.0, -0.93)], "at": None, "all": []}}
    b.update(over)
    return b


STATS = {"range_model": MODEL, "distance_reactions": {
    "version": "BETA_DISTANCE_REACTIONS_V1",
    "cells": [{"distance_pct": d, "side": s, "n": 9000, "1h": {"hold_rate": 0.42, "further_median": 0.3, "back_median": 0.35}}
              for d in (0.25, 0.5, 1.0, 2.0, 3.0, 5.0) for s in (1, -1)]}}


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace("&lt;", "<").replace("&gt;", ">")


@pytest.mark.parametrize("arg,expected", [
    ("64000", [64000.0]), ("64k", [64000.0]), ("64к", [64000.0]), ("64 000", [64000.0]), ("64,5k", [64500.0]),
    ("65,000", [65000.0]), ("$63500", [63500.0]), ("-3%", [round(PRICE * 0.97, 2)]), ("- 3 %", [round(PRICE * 0.97, 2)]),
    ("+1.5%", [round(PRICE * 1.015, 2)]), ("2,5%", [round(PRICE * 1.025, 2)]),
    ("64000 61000", [64000.0, 61000.0]), ("64 000 61 000", [64000.0, 61000.0]), ("64к -2%", [64000.0, round(PRICE * 0.98, 2)]),
    # a comma or a semicolon between two levels (review of PR #334)
    ("64000, 61000", [64000.0, 61000.0]), ("64 000, 61 000", [64000.0, 61000.0]), ("64000,61000", [64000.0, 61000.0]),
    ("64000; 61000", [64000.0, 61000.0]), ("64000,", [64000.0]), ("63 000,5", [63000.5]),
])
def test_any_input_format(arg, expected):
    assert ck.parse_check_args(arg, PRICE) == (expected, None)


@pytest.mark.parametrize("arg,err", [
    ("", "ck_usage"), ("abc", "ck_usage"), ("64000 61000 60000", "ck_usage"), ("64000 64000", "ck_usage"),
    ("100000", "al_too_far"), ("62480", "al_too_close"), ("nan", "ck_usage"), ("-40%", "al_too_far"),
    # digit groups join only after a 1-3 digit head: «64000 100» is two numbers, never 64000100
    ("64000 100", "al_too_far"), ("64 0000", "al_too_far"),
])
def test_bad_input_is_named(arg, err):
    assert ck.parse_check_args(arg, PRICE) == ([], err)
    assert "64000100" not in ck._tokens(arg)
    assert ck.parse_check_args("64000", None) == ([], "al_no_price")


def test_one_level_wording_b_with_its_held_out_line_and_context():
    text = plain(ck.format_check(block(), STATS, [64000.0], "ru", now=NOW))
    lines = text.splitlines()
    assert lines[0].startswith("BTC → 64 000 (+2,43%) · сейчас 62 480 · ")
    p4 = rc.touch_probability(MODEL, "4h", 1.2, (64000 / PRICE - 1) * 100)
    assert f"4ч: шанс дойти ≈ {round(p4 * 100)}% · на истории: говорили " in text and "(N=400)" in text
    assert "Обычный ход: 1ч ±0,30%, 4ч ±0,60%, 24ч ±1,50%" in text
    assert "События в ближайшие 24ч: 15:30 CPI США (инфляция)" in text
    assert "64 000: после касания цены на таком расстоянии (≈2%, 9000 случаев) через 1ч цена была за ней в 42%" in text
    assert "За 64 000 дальше: 65 000 — круглый уровень (+4,03%)" in text
    assert text.endswith("Binance.") and "лонг" not in text
    for lang in ("ru", "en"):
        assert_descriptive(ck.format_check(block(), STATS, [64000.0], lang, now=NOW), lang)


def test_a_bin_outside_the_rule_falls_back_to_the_historical_wording():
    text = plain(ck.format_check(block(passed=False), STATS, [64000.0], "ru", now=NOW))
    assert "шанс" not in text.split("\n", 1)[1].split("Обычный")[0]
    assert "4ч: исторически цена доходила в " in text and "случаев" in text
    # the honesty rule: the historical number carries its N and a comparable «обычно»
    assert "(история 2100 дн.; обычно ход за 4ч ±0,60%)" in text
    two = plain(ck.format_check(block(passed=False), STATS, [61000.0, 64000.0], "ru", now=NOW))
    assert "* исторически в стольких случаях (история 2100 дн.)" in two


def test_live_line_replaces_the_held_out_one_once_mature():
    p4 = rc.touch_probability(MODEL, "4h", 1.2, (64000 / PRICE - 1) * 100)
    b = rc.touch_bin(p4)
    live = {"horizons": {"4h": {"bins": [{"bin": b, "n_eff": 31, "predicted": 0.2, "realized": 0.25}]}}, "diverged": {}}
    text = plain(ck.format_check(block(touch_live=live), STATS, [64000.0], "ru", now=NOW))
    assert "4ч: шанс дойти ≈ " in text and "вживую: говорили 20% → было 25% (N=31)" in text
    live["diverged"] = {"4h": [b]}
    assert "4ч: исторически цена доходила" in plain(ck.format_check(block(touch_live=live), STATS, [64000.0], "ru", now=NOW))


def test_two_levels_show_each_chance_and_neither_never_who_first():
    text = plain(ck.format_check(block(), STATS, [61000.0, 64000.0], "ru", now=NOW))
    assert text.splitlines()[0].startswith("BTC: 64 000 (+2,43%) и 61 000 (−2,37%) · сейчас 62 480")
    line4 = next(x for x in text.splitlines() if x.startswith("4ч: ↑"))
    up, dn = (rc.touch_probability(MODEL, "4h", 1.2, abs(d)) for d in ((64000 / PRICE - 1) * 100, (61000 / PRICE - 1) * 100))
    nei = rc.neither_probability(MODEL, "4h", 1.2, (64000 / PRICE - 1) * 100, abs(61000 / PRICE - 1) * 100,
                                 p_up=up, p_down=dn)
    assert f"↑ ≈ {round(up * 100)}%" in line4 and f"↓ ≈ {round(dn * 100)}%" in line4
    assert f"ни один ≈ {round(nei * 100)}%" in line4
    assert 1 - up - dn - 1e-9 <= nei <= 1 - max(up, dn) + 1e-9            # coherent with the two chances
    cal4 = text.splitlines()[text.splitlines().index(line4) + 1]
    assert cal4.startswith("   говорили → было: ↑ ") and cal4.count("(на истории, N=400)") == 3
    assert text.endswith("Какой из двух уровней будет первым — не показываем.")
    assert "64 000: после касания" in text and "61 000: после касания" in text
    same = plain(ck.format_check(block(), STATS, [63000.0, 64000.0], "ru", now=NOW))
    p_near = rc.touch_probability(MODEL, "4h", 1.2, (63000 / PRICE - 1) * 100)
    assert f"ни один ≈ {round((1 - p_near) * 100)}%" in same                 # the same side: not the nearer one


def test_each_part_of_a_pair_names_its_own_check_and_n():
    """One part checked live, the others on history: each says which, with its own N."""
    up = rc.touch_probability(MODEL, "4h", 1.2, (64000 / PRICE - 1) * 100)
    live = {"horizons": {"4h": {"bins": [{"bin": rc.touch_bin(up), "n_eff": 31, "predicted": 0.2, "realized": 0.25}]}},
            "diverged": {}, "neither": {}, "diverged_neither": {}}
    text = plain(ck.format_check(block(touch_live=live), STATS, [60500.0, 64000.0], "ru", now=NOW))  # three bins
    lines = text.splitlines()
    cal4 = lines[lines.index(next(x for x in lines if x.startswith("4ч: ↑"))) + 1]
    parts = cal4.split(": ", 1)[1].split(" · ")
    assert parts[0] == "↑ 20% → 25% (вживую, N=31)"
    assert parts[1].startswith("↓ ") and parts[1].endswith("(на истории, N=400)")
    assert parts[2].startswith("ни один ") and parts[2].endswith("(на истории, N=400)")


def test_an_objective_level_shows_its_own_history_beside_a_random_level():
    text = plain(ck.format_check(block(), STATS, [62950.0], "ru", now=NOW))
    assert "62 950 — это максимум вчера:" in text
    assert ("после первого касания (812 случаев): через 1ч цена выше уровня в 47% — у случайного уровня 43% "
            "(+4,0 п.п.; 95% интервал −1,2…+9,1)") in text
    assert "таком расстоянии" not in text
    # without the difference's interval: «мало данных», never a bare difference (review of #343, finding 2)
    b = block()
    b["levels"]["above"][0]["history"] = {k: v for k, v in HIST.items() if k != "ci95"}
    bare = plain(ck.format_check(b, STATS, [62950.0], "ru", now=NOW))
    assert "↳ после первого касания: интервал ещё не посчитан (812 случаев)" in bare and "п.п." not in bare


def test_event_zone_horizons_have_no_number():
    b = block(event_zone={"24h": [{"kind": "CPI", "at": "2026-10-14T12:30:00+00:00"}]})
    del b["corridor"]["horizons"]["24h"]
    text = plain(ck.format_check(b, STATS, [64000.0], "ru", now=NOW))
    assert "24ч: шанс" not in text and "24ч: числовую оценку не показываем" in text


def test_buttons_carry_the_level():
    assert ck.check_buttons([64000.0, 61000.0], "ru") == [[("🔔 Следить: 64 000", "w:64000.00"), ("🔔 Следить: 61 000", "w:61000.00")]]
    assert ck.check_button(62950.0, "ru") == ("🎯 Проверить 62 950", "k:62950.00")
    assert ck.parse_level_callback("w:64000.00") == 64000.0 and ck.parse_level_callback("k:x") is None
    assert ck.parse_level_callback("k:" + "9" * 70) is None and ck.parse_level_callback("u:1") is None
    from beta.market_alerts import alert_buttons
    rows = alert_buttons("level", {"next": {"edge": 64000.0}}, "ru")
    assert rows[-1] == [("🎯 Проверить 64 000", "k:64000.00")]
    assert len(alert_buttons("event", {}, "ru")) == 2
    # a sharp move offers the nearest level in its own direction, never the upper one by default
    near = [{"edge": 63100.0}, {"edge": 61900.0}]
    down = alert_buttons("move", {"near": near, "close": 62400.0, "move_pct": -1.4}, "ru")
    assert down[-1] == [("🎯 Проверить 61 900", "k:61900.00")]
    up = alert_buttons("move", {"near": near, "close": 62400.0, "move_pct": 1.4}, "ru")
    assert up[-1] == [("🎯 Проверить 63 100", "k:63100.00")]
    nothing_below = alert_buttons("move", {"near": [{"edge": 63100.0}], "close": 62400.0, "move_pct": -1.4}, "ru")
    assert len(nothing_below) == 2
    from beta.formatter import btc_buttons
    brief = btc_buttons({"kind": "brief", "decision": block()}, "ru", 5)
    assert brief[-1] == [("🎯 Проверить 62 950", "k:62950.00"), ("🎯 Проверить 61 900", "k:61900.00")]
    assert all("k:" not in d for row in btc_buttons({"kind": "btc", "decision": block()}, "ru", 5) for _l, d in row)


def test_unavailable_block_says_why():
    text = ck.format_check({"available": False, "reason": "DATA_STALE"}, STATS, [64000.0], "ru", now=NOW)
    assert "не показываем" in plain(text)


def test_distance_reactions_measure_a_level_with_no_meaning():
    from beta import levels
    from beta.hist_series import bars_from_rows
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rng = np.random.default_rng(3)
    closes = 60000 * np.exp(np.cumsum(rng.normal(0, 0.002, 30 * 288)))
    rows = [{"open_time_ms": int((start + timedelta(minutes=5 * k)).timestamp() * 1000), "open": float(c),
             "high": float(c) * 1.001, "low": float(c) * 0.999, "close": float(c)} for k, c in enumerate(closes)]
    st = levels.distance_reaction_stats(bars_from_rows(rows))
    assert st["version"] == levels.DISTANCE_REACTIONS_VERSION and len(st["cells"]) == 12
    near = next(c for c in st["cells"] if c["distance_pct"] == 0.25 and c["side"] == 1)
    far = next(c for c in st["cells"] if c["distance_pct"] == 5.0 and c["side"] == 1)
    assert near["touch_rate"] > far["touch_rate"] and near["n"] > 0 and 0 <= near["1h"]["hold_rate"] <= 1
    assert levels.distance_reaction(st, 2.43)["distance_pct"] == 2.0
    assert levels.distance_reaction(st, -0.6)["distance_pct"] == 0.5 and levels.distance_reaction(st, -0.6)["side"] == -1
    assert levels.distance_reaction({"version": "OLD"}, 1.0) is None
