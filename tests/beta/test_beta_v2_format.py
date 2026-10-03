"""Decision support V2: texts and market-alert detection (pure; PRODUCT_DECISION_V2 §2, §3)."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from beta import decision_format as df
from beta import market_alerts as ma
from beta.config import BetaConfig
from beta.hist_series import bars_from_rows
from beta.i18n import ForbiddenWordingError, assert_descriptive, t

UTC = timezone.utc
CFG = BetaConfig.load()
NOW = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)          # 09:00 Kyiv (summer time)


def _zone(kinds, low, high, dist, p4=0.3, p24=0.6, hist=None, **extra):
    return {"low": low, "high": high, "edge": low if dist > 0 else high, "distance_pct": dist,
            "kinds": kinds, "members": [{"kind": k, "price": low, **extra} for k in kinds],
            "touch": {"4h": p4, "24h": p24}, "history": hist}


HIST = {"type": "PDH", "kind": "PDH", "verdicts": {"1h": "as_usual", "4h": "as_usual", "touch": "as_usual"},
        "real": {"n": 812, "1h": {"hold_rate": 0.47, "further_median": 0.5, "back_median": 0.4}},
        "control": {"n": 4000, "1h": {"hold_rate": 0.43, "further_median": 0.5, "back_median": 0.4}}}


def block(**over):
    b = {"available": True, "price": 62480.0, "stats": {"data_from_ms": int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)},
         "corridor": {"coverage": 0.8, "horizons": {
             "1h": {"scale_pct": 0.6, "half_width_pct": 0.7, "lower": 62043.0, "upper": 62917.0,
                    "typical_move_pct": 0.25, "event_in_window": {"CPI": False, "FOMC": False}},
             "4h": {"scale_pct": 1.2, "half_width_pct": 1.4, "lower": 61605.0, "upper": 63355.0,
                    "typical_move_pct": 0.5, "event_in_window": {"CPI": True, "FOMC": False}},
             "24h": {"scale_pct": 3.0, "half_width_pct": 3.6, "lower": 60230.0, "upper": 64730.0,
                     "typical_move_pct": 1.4, "event_in_window": {"CPI": True, "FOMC": False}}}},
         "levels": {"above": [_zone(["PDH"], 62950.0, 62950.0, 0.75, hist=HIST),
                              _zone(["WO", "ROUND"], 64000.0, 64000.0, 2.43, 0.05, 0.21),
                              _zone(["ROUND"], 65000.0, 65000.0, 4.0, 0.01, 0.1)],
                    "below": [_zone(["ASIA_L"], 61900.0, 61900.0, -0.93, 0.4, 0.55),
                              _zone(["LIQ_LONG"], 61200.0, 61200.0, -2.05, 0.1, 0.26, notional_usd=3.8e7)],
                    "at": None, "all": []},
         "events": [{"kind": "CPI", "at": "2026-10-14T12:30:00+00:00",
                     "stats": {"hour": {"n": 61, "median_ratio": 3.2}, "day": {"n": 61, "median_ratio": 1.5}}}],
         "analogues": {}}
    b.update(over)
    return b


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace("&lt;", "<").replace("&gt;", ">")


def test_brief_block_ladder_corridor_and_today():
    lines = df.brief_lines({"decision": block()}, "ru")
    text = plain("\n".join(lines))
    assert "Коридор" in text and "4ч: 61 605–63 355 (±1,4%) · 24ч: 60 230–64 730 (±3,6%) · в окне — CPI США (инфляция)" in text
    ladder = text[text.index("Уровни"):text.index("Сегодня")].strip().splitlines()
    assert ladder[1].startswith("↑ 64 000 — открытие недели, круглый уровень · +2,43% · 21%")
    assert ladder[2].startswith("↑ 62 950 — максимум вчера · +0,75% · 60%")
    assert ladder[3] == "— сейчас 62 480 —"
    assert ladder[4].startswith("↓ 61 900 — минимум Азии") and "ликвидации лонгов $38 млн" in ladder[5]
    assert "15:30 — CPI США (инфляция): час выхода обычно ×3,2, день ×1,5 (61 случай)" in text
    for lang in ("ru", "en"):
        assert_descriptive("\n".join(df.brief_lines({"decision": block()}, lang)), lang)


def test_unavailable_block_says_why_and_never_shows_numbers():
    for reason, word in (("DATA_STALE", "отстают"), ("NO_STATS", "не загружена"), ("ERROR", "ошибка")):
        lines = df.brief_lines({"decision": {"available": False, "reason": reason}}, "ru")
        assert lines[-1].startswith("Коридор и уровни сейчас не показываем") and word in lines[-1]
    assert df.btc_lines({"decision": {"available": False}}, "ru") == []


def test_btc_lines():
    lines = df.btc_lines({"decision": block()}, "ru")
    assert lines == ["Коридор 4ч: 61 605–63 355 (±1,4%)",
                     "Уровни: ↑ 62 950 максимум вчера (+0,75%) · ↓ 61 900 минимум Азии (−0,93%)"]


def test_levels_card_has_history_beside_a_random_level():
    text = plain(df.format_levels(block(), "ru", now=NOW))
    assert "после первого касания (812 случаев): через 1ч цена выше уровня в 47% — у случайного уровня 43%, как обычно" in text
    assert "дойти: за 4ч 30%, за 24ч 60%" in text and "День, неделя и месяц — по UTC" in text
    en = plain(df.format_levels(block(), "en", now=NOW))
    assert "after the first touch (812 cases): 1h later the price was above the level in 47%" in en


def test_risk_card_and_argument_parsing():
    from beta import rangecast as rc
    model = {"horizons": {h: {"q_one": [0.01 * k for k in range(1, 100)] + [1.2, 1.5]} for h in ("1h", "4h", "24h")}}
    assert rc.P_GRID[-1] == 0.999
    text = plain(df.format_risk(block(), model, "ru", stop_pct=0.4))
    assert "Стоп 0,40% (≈ $250) против позиции" in text and "за 1ч — в " in text
    assert "Одинаково для лонга и шорта" in text
    table = plain(df.format_risk(block(), model, "en", stop_pct=None))
    assert "0.25%: 1h" in table and "/risk 0.5 or /risk 61500" in table
    assert df.parse_risk_arg("0,5%", 60000) == ("pct", 0.5)
    assert df.parse_risk_arg("59400", 60000) == ("pct", pytest.approx(1.0))
    assert df.parse_risk_arg("", 60000) == ("table", None)
    assert df.parse_risk_arg("abc", 60000) == ("bad", None)
    assert df.parse_risk_arg("40", 60000) == ("bad", None)
    assert df.parse_risk_arg("59400", None) == ("bad", None)


def test_analog_line_wording_follows_the_verdict():
    base = {"p_up": 0.51}
    cell = {"n": 412, "days": 300, "p_up": 0.53, "baseline": base, "range_ratio": 1.3,
            "verdicts": {"direction": "as_usual", "range": "differs"}}
    card = {"window": "4h", "outcomes": {"4h": cell}}
    ru = df.analog_line(card, "ru", since_year=2020)
    assert ru == ("↳ после похожих (412 случаев с 2020): через 4ч выше в 53% (обычно 51%) — как обычно; "
                  "ход ×1,3 — больше обычного")
    cell2 = {**cell, "p_up": 0.44, "range_ratio": 0.8, "verdicts": {"direction": "differs", "range": "differs"}}
    assert "чаще ниже обычного" in df.analog_line({"window": "1h", "outcomes": {"1h": cell2}}, "ru")
    assert "меньше обычного" in df.analog_line({"window": "1h", "outcomes": {"1h": cell2}}, "ru")
    small = {"window": "1h", "outcomes": {"1h": {**cell, "n": 12}}}
    assert df.analog_line(small, "ru") == "↳ после похожих: мало данных (12 случаев)"
    assert df.analog_line(None, "ru") is None


def test_events_and_accuracy_cards():
    evs = [{"kind": "CPI", "at": "2026-10-14T12:30:00+00:00", "stats": {"hour": {"n": 61, "median_ratio": 3.2},
                                                                         "day": {"n": 61, "median_ratio": 1.5}}},
           {"kind": "EXPIRY_MONTHLY", "at": "2026-10-30T08:00:00+00:00",
            "stats": {"hour": {"n": 70, "median_ratio": 1.1}, "day": {"n": 70, "median_ratio": 0.97}}}]
    text = plain(df.format_events(evs, "ru", funding_utc=["00:00", "08:00", "16:00"]))
    assert "Ср 14.10 15:30 — CPI США (инфляция): час выхода обычно ×3,2, день ×1,5 (61 случай)" in text
    assert "Пт 30.10 10:00 — месячная экспирация опционов Deribit: час ×1,1, день ×1,0 (70 случаев) — почти как обычно" in text
    model = {"calibration": {"1h": {"coverage_realized": 0.793, "holdout_from_ms": 1727740800000,
                                    "holdout_to_ms": 1759276800000}}}
    acc = plain(df.format_accuracy(model, {"4h": {"INSIDE": 82, "OUTSIDE": 18}}, "ru"))
    assert "Проверка на отложенном годе (2024-10 – 2025-10): 1ч 79%" in acc
    assert "Живые прогнозы за 30 дней: 4ч — 82% (из 100)" in acc
    assert "ещё не созрели" in plain(df.format_accuracy(None, {}, "ru"))


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_alert_texts(lang):
    payloads = {
        "level": {"at": NOW.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1, "period": "day",
                  "price": 62970.0, "history": HIST, "next": _zone(["WO"], 64000.0, 64000.0, 1.6),
                  "corridor_4h": block()["corridor"]["horizons"]["4h"]},
        "event": {"at": NOW.isoformat(), "event_kind": "FOMC", "event_at": (NOW + timedelta(minutes=30)).isoformat(),
                  "minutes": 30, "price": 62480.0,
                  "stats": {"hour": {"n": 39, "median_ratio": 3.3}, "day": {"n": 39, "median_ratio": 1.6}},
                  "corridor_1h": block()["corridor"]["horizons"]["1h"]},
        "move": {"at": NOW.isoformat(), "start": (NOW - timedelta(minutes=15)).isoformat(), "open": 63100.0,
                 "close": 62250.0, "move_pct": -1.35, "every_days": 3.0,
                 "corridor_1h": block()["corridor"]["horizons"]["1h"],
                 "near": [_zone(["PDL"], 61900.0, 61900.0, -0.56)]},
        "price": {"at": NOW.isoformat(), "level": 65000.0, "price": 65030.0,
                  "corridor_4h": block()["corridor"]["horizons"]["4h"]},
    }
    for kind, p in payloads.items():
        text = df.format_alert(kind, p, lang)
        assert_descriptive(text, lang)
        assert _telegram_html_ok(text), text
        assert len([x for x in plain(text).splitlines() if x.strip()]) <= 8
    ru = plain(df.format_alert("level", payloads["level"], "ru"))
    if lang == "ru":
        assert ru.startswith("BTC · максимум вчера 62 950\n09:00 (Киев) · цена 62 970 (Binance) — первое касание за день")
        assert "у случайного уровня 43%" in ru and "Следующий уровень: 64 000" in ru
        move = plain(df.format_alert("move", payloads["move"], "ru"))
        assert move.startswith("BTC · резкое движение −1,35% за 15 минут\n08:45–09:00 (Киев)")


def test_guard_rejects_direct_calls_in_any_rendered_text():
    with pytest.raises(ForbiddenWordingError):
        assert_descriptive("BTC у уровня — покупайте", "ru")
    with pytest.raises(ForbiddenWordingError):
        assert_descriptive("цель 70 000", "ru")
    assert t("ru", "rk_note") == "Одинаково для лонга и шорта: направление модель не предсказывает."


# ---- market alert detection (pure) ------------------------------------------------------------
def _grid(start, closes, highs=None, lows=None):
    rows = []
    for k, c in enumerate(closes):
        rows.append({"open_time_ms": int((start + timedelta(minutes=5 * k)).timestamp() * 1000), "open": c,
                     "high": (highs or closes)[k], "low": (lows or closes)[k], "close": c})
    return bars_from_rows(rows)


def test_level_touch_alerts_once_on_the_first_touch_of_the_period():
    day0 = datetime(2026, 10, 14, tzinfo=UTC)
    closes = [100.0] * 72                                     # today 00:00–06:00, below the level
    highs = [100.5] * 72
    b = _grid(day0, closes, highs)
    closed = [{"ts": day0 + timedelta(hours=6, minutes=m), "open": 100.0, "high": 100.2 + (0.9 if m == 3 else 0),
               "low": 99.9, "close": 100.1} for m in range(5)]
    blk = {"price": 100.1, "levels": {"all": [{"kind": "PDH", "price": 101.0}], "above": [], "below": []},
           "corridor": {"horizons": {}}}
    now = day0 + timedelta(hours=6, minutes=5)
    out = ma.detect_level_touches(blk, b, closed, now=now, max_age=timedelta(minutes=10), stats=None)
    assert [c["key"] for c in out] == ["level:PDH:2026-10-14"]
    assert out[0]["payload"]["at"] == (day0 + timedelta(hours=6, minutes=3)).isoformat()
    # an older first touch (the bot was down) is not pushed
    late = now + timedelta(minutes=30)
    assert ma.detect_level_touches(blk, b, closed, now=late, max_age=timedelta(minutes=10), stats=None) == []
    # a period that opened beyond the level has no approach
    b2 = _grid(day0, [102.0] * 72, [102.5] * 72, [101.5] * 72)
    assert ma.detect_level_touches(blk, b2, closed, now=now, max_age=timedelta(minutes=10), stats=None) == []


def test_event_reminder_window():
    cal = {"events": [{"kind": "CPI", "at": NOW + timedelta(minutes=20)},
                      {"kind": "FOMC", "at": NOW + timedelta(hours=2)},
                      {"kind": "NFP", "at": NOW + timedelta(minutes=10)}]}
    out = ma.detect_events({"price": 1.0, "corridor": {}}, cal, now=NOW, lead=timedelta(minutes=30), stats=None)
    assert [(c["payload"]["event_kind"], c["payload"]["minutes"]) for c in out] == [("CPI", 20)]


def test_sharp_move_uses_the_scale_known_before_the_move():
    day0 = datetime(2026, 10, 7, tzinfo=UTC)
    import numpy as np
    rng = np.random.default_rng(1)
    closes = list(100 * np.exp(np.cumsum(rng.normal(0, 0.001, 2100))))
    b = _grid(day0, closes, [c * 1.001 for c in closes], [c * 0.999 for c in closes])
    end = day0 + timedelta(minutes=5 * 2100)
    last = closes[-1]
    closed = [{"ts": end + timedelta(minutes=m), "open": last, "high": last, "low": last,
               "close": last * (1 - 0.02 * (m == 14))} for m in range(15)]
    model = {"move": {"threshold": 2.0, "episodes_per_day": 0.33},
             "horizons": {"1h": {"beta": [0.0] * 9, "season": [0.0] * 24}}}     # S = 1% for any input
    out = ma.detect_move({"price": last, "levels": {}, "corridor": {}}, b, closed, now=end + timedelta(minutes=15),
                         model=model, events={})
    assert len(out) == 1 and out[0]["payload"]["move_pct"] == pytest.approx(-2.0)
    assert out[0]["payload"]["every_days"] == pytest.approx(1 / 0.33)
    model["move"]["threshold"] = 2.5
    assert ma.detect_move({"price": last, "levels": {}, "corridor": {}}, b, closed, now=end + timedelta(minutes=15),
                          model=model, events={}) == []


def test_price_alert_triggers_only_after_creation():
    day0 = datetime(2026, 10, 14, tzinfo=UTC)
    b = _grid(day0, [100.0, 103.0, 100.0, 100.0], [100.0, 103.0, 100.0, 100.0])
    alert = {"price_alert_pk": 7, "user_pk": 3, "price": 102.0, "direction": "above",
             "created_at": day0 + timedelta(minutes=10)}
    assert ma.detect_price_alerts([alert], b, [], block={"price": 100.0}) == []
    closed = [{"ts": day0 + timedelta(minutes=20), "open": 100.0, "high": 102.5, "low": 100.0, "close": 102.2}]
    out = ma.detect_price_alerts([alert], b, closed, block={"price": 102.2})
    assert out[0]["key"] == "price:7" and out[0]["target_user_pk"] == 3


def _telegram_html_ok(html: str) -> bool:
    """Telegram HTML: only <b>/<i> tags; every other <, > and & must be an entity."""
    body = re.sub(r"</?(b|i)>", "", html)
    body = re.sub(r"&(lt|gt|amp|quot|#\d+);", "", body)
    return not any(ch in body for ch in "<>&")


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_every_decision_text_is_valid_telegram_html(lang):
    from beta import rangecast as rc
    model = {"horizons": {h: {"q_one": [0.01 * k for k in range(1, 100)] + [1.2, 1.5]} for h in ("1h", "4h", "24h")},
             "calibration": {}}
    blk = block()
    blk["levels"]["above"][0]["touch"] = {"4h": 0.001, "24h": 0.999}
    texts = ["\n".join(df.brief_lines({"decision": blk}, lang)), "\n".join(df.btc_lines({"decision": blk}, lang)),
             df.format_levels(blk, lang, now=NOW), df.format_risk(blk, model, lang, stop_pct=0.4),
             df.format_risk(blk, model, lang, stop_pct=None), df.format_accuracy(model, {}, lang),
             df.format_events(blk["events"], lang, funding_utc=["00:00"])]
    assert "&lt;1%" in texts[2] and "&gt;99%" in texts[2]
    for text in texts:
        assert _telegram_html_ok(text), text
