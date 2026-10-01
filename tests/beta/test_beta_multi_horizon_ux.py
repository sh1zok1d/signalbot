"""PR 1 of the multi-horizon /btc pass: language, Kyiv time, Event tab, 1h tab.

Presentation only. These tests render both languages from persisted view payloads
and check the 1h time-of-day baseline. They do not open a detector rule.
"""
import re
from datetime import datetime, timedelta, timezone

import pytest

from test_beta_btc_view import ALL_LIQ, CFG, C1H, DOWN, QUIET, UP, _view, run, snap
from test_beta_context import BUILDUP, EXS, T0
from test_beta_readiness import ready_of, rsnap, view_for

from beta.formatter import (assert_descriptive, btc_buttons, format_1h_tab, format_btc,
                            format_event_tab, view_id8)
from beta.horizons import HORIZON_DIGEST, HORIZON_VERSION, build_horizons, empty_horizons, verify_horizon_digest
from beta.i18n import _CATALOG, fmt_clock, fmt_kyiv_hm, fmt_price, fmt_ratio, fmt_signed_pct, fmt_usd, kyiv
from beta.state_tape import BUCKET, metric_key

RU_DISCLAIMER = ("Экспериментальная закрытая бета. Только описание состояния рынка — "
                 "не инвестиционный совет и не указание к сделке.")
EN_FAIL = ("Current observability is insufficient; the absence of events cannot be claimed right now.")
RU_FAIL = "Текущих данных недостаточно: отсутствие событий сейчас подтвердить нельзя."


def _plain(html):
    return re.sub(r"<[^>]+>", "", html)


def _body_lines(html):
    plain = _plain(html)
    lines = [ln for ln in plain.split("\n") if ln.strip()]
    disc = [ln for ln in lines if ln.startswith("Experimental") or ln.startswith("Экспериментальная")]
    body = [ln for ln in lines if ln not in disc]
    return body, disc


def _budget(html):
    body, disc = _body_lines(html)
    assert disc and len(disc) == 1
    assert len(body) <= 8, body
    assert_descriptive(html, "ru" if disc[0].startswith("Экспериментальная") else "en")
    return body


def _with_horizons(view, block):
    out = dict(view)
    out["horizons"] = {"version": HORIZON_VERSION, "digest": HORIZON_DIGEST, "1h": block}
    return out


def _hour_block(**kw):
    base = {
        "complete": True,
        "window_start": "2026-03-02T11:10:00+00:00",
        "window_end": "2026-03-02T12:10:00+00:00",
        "price_move_pct": -0.84,
        "range_width_pct": 1.12,
        "volume_notional_usd": 1.9e9,
        "baseline_days": {"range_width_pct_median": 30, "volume_notional_usd_sum": 30,
                          "price_move_pct_median": 30},
        "baseline_median": {"range_width_pct_median": 0.487, "volume_notional_usd_sum": 9.05e8,
                            "price_move_pct_median": -0.2},
        "range_ratio": 2.3,
        "volume_ratio": 2.1,
        "taker_delta_notional_usd_sum": -84e6,
        "funding_rate": 0.00006,
        "liquidations": {"buckets_missing": False, "venues": {
            "binance": {"long": {"amount": 8e6, "missing": False, "lower_bound": True},
                        "short": {"amount": 1e6, "missing": False, "lower_bound": True}},
            "bybit": {"long": {"amount": 10e6, "missing": False, "lower_bound": False},
                      "short": {"amount": 2e6, "missing": False, "lower_bound": False}},
            "okx": {"long": {"amount": 3e6, "missing": False, "lower_bound": False},
                    "short": {"amount": 4e5, "missing": False, "lower_bound": False}},
        }},
    }
    base.update(kw)
    return base


def _screens():
    """Named views covering the main states. Horizons are attached where the tape is usable."""
    states, _ = run([snap(QUIET, liq=ALL_LIQ)])
    calm = _with_horizons(_view(states, c1h=C1H), _hour_block())
    states, _ = run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ)])
    unusual = _with_horizons(_view(states), _hour_block())
    states, _ = run([snap(UP, {"price": 0.20, "oi": -0.10}, liq=ALL_LIQ),
                     snap(QUIET, {"price": -0.02, "oi": 0.0}, liq=ALL_LIQ)])
    calmed = _with_horizons(_view(states, minutes_after=21.5, c1h=C1H), _hour_block())
    states, _ = run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ), snap(QUIET, liq=ALL_LIQ)])
    s = __import__("copy").deepcopy(states[-1])
    s["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]["terminal_reason"] = "DETECTION_GAP"
    from beta.context import btc_view, state_digest
    from test_beta_btc_view import _product, _readiness_for
    from beta import context as cx
    ended = _with_horizons(btc_view(
        CFG, product=_product(states), state=s, state_digest_value=state_digest(s),
        now=cx._ts(s["as_of_bucket"]) + BUCKET, readiness=_readiness_for(states),
        detector_open_ids=[]),
        _hour_block())
    r, snap_s = ready_of(rsnap(tier="building", span=8.47))
    history = _with_horizons(view_for(r, snap_s, "NO ACTIVE EVENTS"), None)
    history["horizons"] = empty_horizons()
    stale_open = _view(run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ)])[0], status="DATA STALE")
    stale_open["horizons"] = empty_horizons()
    quiet_states, _ = run([snap(QUIET, liq=ALL_LIQ)])
    stale_none = _view(quiet_states, status="DATA STALE")
    stale_none["horizons"] = empty_horizons()
    degraded = _view(run([snap(DOWN, liq=ALL_LIQ), snap(DOWN, liq=ALL_LIQ)])[0], status="DATA DEGRADED")
    degraded["horizons"] = empty_horizons()
    return {
        "calm": calm, "unusual": unusual, "calmed": calmed, "ended": ended,
        "history": history, "stale_open": stale_open, "stale_none": stale_none,
        "degraded": degraded,
    }


SCREENS = None


def screens():
    global SCREENS
    if SCREENS is None:
        SCREENS = _screens()
    return SCREENS


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize("name", ["calm", "unusual", "calmed", "ended", "history",
                                  "stale_open", "stale_none", "degraded"])
def test_main_screen_full_body_both_languages(name, lang):
    view = screens()[name]
    text = format_btc(CFG, view, lang)
    body = _budget(text)
    plain = _plain(text)
    assert_descriptive(text, lang)
    if lang == "ru":
        assert RU_DISCLAIMER in plain
        assert "Киев" in plain or view.get("data_through") is None
    else:
        assert "not a trade instruction" in plain
    if name in ("stale_open", "stale_none", "degraded"):
        assert (RU_FAIL if lang == "ru" else EN_FAIL) in plain
        assert "1ч:" not in plain and "1h:" not in plain
        assert "↑" not in plain and "↓" not in plain
    else:
        assert "1ч:" in plain or "1h:" in plain
    if name == "calm":
        assert ("спокойно" if lang == "ru" else "calm") in body[0]
        assert "83 500" in body[0] if lang == "ru" else "83,500" in body[0]
        assert ("1ч: −0,8% · объём 2,1× · диапазон 2,3×" if lang == "ru"
                else "1h: −0.8% · vol 2.1× · range 2.3×") in plain
    if name == "unusual":
        assert ("необычно сейчас" if lang == "ru" else "unusual now") in body[0]
        assert ("ОИ снизился во время падения" if lang == "ru" else "Open interest fell during the drop") in plain
    if name == "calmed":
        assert ("затихло" if lang == "ru" else "calmed") in body[0]
    if name == "ended":
        assert ("событие завершено" if lang == "ru" else "event ended") in body[0]
        assert ("пропуске данных" if lang == "ru" else "data gap") in plain
    if name == "history":
        assert ("накопление истории" if lang == "ru" else "history building") in body[0]
        assert ("1ч: неполные данные" if lang == "ru" else "1h: incomplete") in plain
    if name == "stale_open":
        assert "83" not in body[0]
        assert ("Последнее известное" if lang == "ru" else "Last known") in plain
    if name == "stale_none":
        assert ("Последнее известное" if lang == "ru" else "Last known") not in plain
    if name == "degraded":
        assert "83 500" in body[0] if lang == "ru" else "83,500" in body[0]
        assert ("Последнее известное" if lang == "ru" else "Last known") in plain
    buttons = btc_buttons(view, lang, view_pk=11)
    labels = [b[0] for b in (buttons[0] if buttons else [])]
    if name in ("stale_none",):
        assert ( "Событие" if lang == "ru" else "Event") not in labels
        assert ("1ч" if lang == "ru" else "1h") not in labels
    if name in ("stale_open", "degraded"):
        assert ("Событие" if lang == "ru" else "Event") in labels
        assert ("1ч" if lang == "ru" else "1h") not in labels
    if name in ("calm", "history"):
        assert ("1ч" if lang == "ru" else "1h") in labels
        assert ("Событие" if lang == "ru" else "Event") not in labels
    if name in ("unusual", "calmed", "ended"):
        assert ("Событие" if lang == "ru" else "Event") in labels
        assert ("1ч" if lang == "ru" else "1h") in labels


def test_event_and_1h_tabs_both_languages():
    view = screens()["unusual"]
    for lang in ("ru", "en"):
        event = format_event_tab(CFG, view, lang, "1a2b3c4d")
        hour = format_1h_tab(CFG, view, lang, "1a2b3c4d")
        assert_descriptive(event, lang)
        assert_descriptive(hour, lang)
        for banned in ("EARLY", "ARMED", "TRIGGERED", "pct of 30d", "STRICT_QUALIFICATION_V1", "Now"):
            assert banned not in event and banned not in hour
        assert "1a2b3c4d" in event and view["active_episode"]["episode_id"] in event
        if lang == "ru":
            assert "СОБЫТИЕ · необычное падение" in event
            assert "ОИ " in event and "binance" in event
            assert "ПОСЛЕДНИЙ ЧАС" in hour
            assert "2,3× от обычного для этого часа" in hour
            assert "Фандинг сейчас 0,006%" in hour
            assert "Тейкер-поток: продавцы, нетто $84 млн" in hour
            assert "≥ — нижняя граница: Binance передаёт не все ликвидации." in event
            assert "ОИ −0,6%" not in hour
        else:
            assert "EVENT · unusual drop" in event
            assert "LAST HOUR" in hour
            assert "2.3× usual for this hour" in hour
            assert "Funding now 0.006%" in hour
            assert "Taker flow: sellers, net $84M" in hour
            assert "≥ — lower bound: Binance does not report every liquidation." in hour
            assert "OI −0.60%" not in hour and "\nOI " not in hour


def test_number_formats():
    assert fmt_price(112450, "ru") == "112 450"
    assert fmt_price(112450, "en") == "112,450"
    assert fmt_signed_pct(-0.84, "ru") == "−0,84%"
    assert fmt_signed_pct(-0.84, "en") == "−0.84%"
    assert fmt_usd(84e6, "ru") == "$84 млн"
    assert fmt_usd(84e6, "en") == "$84M"
    assert fmt_usd(1.9e9, "ru") == "$1,9 млрд"
    assert fmt_usd(1.9e9, "en") == "$1.9B"
    assert fmt_ratio(2.1, "ru") == "2,1×"
    assert fmt_ratio(0.4, "en") == "0.4×"
    assert fmt_ratio(10, "en") == "10×+"
    assert fmt_ratio(12.2, "ru") == "10×+"


def test_kyiv_dst_boundaries_2026():
    spring_before = datetime(2026, 3, 29, 0, 30, tzinfo=timezone.utc)
    spring_after = datetime(2026, 3, 29, 1, 30, tzinfo=timezone.utc)
    assert fmt_kyiv_hm(spring_before) == "02:30"
    assert fmt_kyiv_hm(spring_after) == "04:30"
    assert kyiv(spring_before).utcoffset() == timedelta(hours=2)
    assert kyiv(spring_after).utcoffset() == timedelta(hours=3)
    assert "02:30 (Киев)" == fmt_clock(spring_before, "ru")
    assert "04:30 Kyiv" == fmt_clock(spring_after, "en")
    fall_before = datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    fall_after = datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc)
    assert fmt_kyiv_hm(fall_before) == "03:30" and kyiv(fall_before).utcoffset() == timedelta(hours=3)
    assert fmt_kyiv_hm(fall_after) == "03:30" and kyiv(fall_after).utcoffset() == timedelta(hours=2)
    assert kyiv(datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc)).isoformat().startswith("2026-10-25T03:00:00")


def test_russian_forbidden_list_and_disclaimer():
    from beta.i18n import ForbiddenWordingError
    for sample in ("купить", "купите", "покупайте", "продай", "точка входа", "стоп-лосс", "тейк-профит",
                   "цель", "плечо", "вероятность роста", "скорее всего", "прогноз",
                   "ожидается", "сигналы", "рекомендуем", "прибыль", "лонг сейчас",
                   "толкают", "киты", "разворот", "продолжение"):
        with pytest.raises(ForbiddenWordingError):
            assert_descriptive(sample, "ru")
    assert_descriptive(RU_DISCLAIMER, "ru")
    for pair in _CATALOG.values():
        for lang, text in pair.items():
            assert_descriptive(text, lang)


def _series(as_of, *, days, vol, liq=1e5, drop_bucket=None, missing=None):
    """5m metrics from as_of-days through as_of. `missing` is (exchange, side) set to None in the last bucket."""
    start = as_of - timedelta(days=days)
    out = {}
    b = start
    while b <= as_of:
        if b != drop_bucket:
            row = {"c:volume_notional_usd_sum": vol, "c:taker_delta_notional_usd_sum": -1e6,
                   "c:funding_rate_median": 0.00006}
            for ex in EXS:
                row[metric_key(ex, "kline_open")] = 100.0
                row[metric_key(ex, "kline_high")] = 100.5
                row[metric_key(ex, "kline_low")] = 99.5
                row[metric_key(ex, "kline_close")] = 99.16
                for side in ("long_liquidation_notional", "short_liquidation_notional"):
                    row[metric_key(ex, side)] = liq
            if b == as_of and missing:
                ex, side = missing
                row[metric_key(ex, side)] = None
            out[b] = row
        b += BUCKET
    # current window stands out so the ratio is not 1
    if drop_bucket is None:
        for i in range(12):
            bucket = as_of - i * BUCKET
            if bucket in out:
                out[bucket]["c:volume_notional_usd_sum"] = vol * 2.1
    return out


def test_horizon_digest_is_pinned_and_separate_from_context():
    from beta.context import KNOWN_CONTEXT_DIGESTS
    assert verify_horizon_digest() == HORIZON_DIGEST
    assert "BETA_CONTEXT_1H_V0" in KNOWN_CONTEXT_DIGESTS
    assert HORIZON_DIGEST not in KNOWN_CONTEXT_DIGESTS.values()


def test_incomplete_window_immature_baseline_and_liquidation_gaps():
    as_of = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    mature = build_horizons(CFG, as_of_bucket=as_of, metrics_by_bucket=_series(as_of, days=31, vol=1e6))
    block = mature["1h"]
    assert block["complete"] is True and block["volume_ratio"] == pytest.approx(2.1, rel=1e-6)
    assert block["price_move_pct"] == pytest.approx(-0.84, abs=1e-6)
    venues = block["liquidations"]["venues"]
    assert venues["binance"]["long"]["lower_bound"] is True
    assert venues["bybit"]["long"]["lower_bound"] is False
    assert venues["bybit"]["long"]["amount"] == pytest.approx(1e5 * 12)

    immature = build_horizons(CFG, as_of_bucket=as_of, metrics_by_bucket=_series(as_of, days=10, vol=1e6))
    assert immature["1h"]["complete"] is True
    assert immature["1h"]["volume_ratio"] is None and immature["1h"]["range_ratio"] is None
    assert immature["1h"]["baseline_days"]["volume_notional_usd_sum"] < 20

    missing_bucket = as_of - 2 * BUCKET
    incomplete = build_horizons(CFG, as_of_bucket=as_of,
                                metrics_by_bucket=_series(as_of, days=31, vol=1e6, drop_bucket=missing_bucket))
    assert incomplete["1h"]["complete"] is False
    assert incomplete["1h"]["liquidations"]["buckets_missing"] is True
    for ex in EXS:
        cell = incomplete["1h"]["liquidations"]["venues"][ex]["long"]
        assert cell["missing"] is False and cell["lower_bound"] is True and cell["amount"] > 0

    one_missing = build_horizons(
        CFG, as_of_bucket=as_of,
        metrics_by_bucket=_series(as_of, days=31, vol=1e6, missing=("bybit", "long_liquidation_notional")))
    bybit_long = one_missing["1h"]["liquidations"]["venues"]["bybit"]["long"]
    okx_long = one_missing["1h"]["liquidations"]["venues"]["okx"]["long"]
    assert bybit_long["missing"] is True and bybit_long["amount"] is None
    assert okx_long["missing"] is False and okx_long["amount"] == pytest.approx(1e5 * 12)
    assert okx_long["lower_bound"] is False

    view = {"product_status": "NO ACTIVE EVENTS", "active_episode": None, "last_event": None,
            "horizons": one_missing, "headline": "NO ACTIVE EVENTS", "readiness": None,
            "requested_at": as_of.isoformat(), "data_through": (as_of + BUCKET).isoformat(),
            "now": {"reference_price": 112450.0}, "projection_available": True, "other_active": []}
    # format_btc needs the headline path; build a calm-shaped view via the keys format_btc reads
    shown = format_1h_tab(CFG, {"horizons": one_missing, "active_episode": None, "last_event": None}, "en", "abcd1234")
    assert "bybit n/a" in shown and "$0" not in shown.split("bybit n/a")[0]
    assert "okx $1.2M" in shown
    assert "binance ≥" in shown
    ru = format_1h_tab(CFG, {"horizons": one_missing, "active_episode": None, "last_event": None}, "ru", "abcd1234")
    assert "bybit н/д" in ru and "bybit $0" not in ru
    gap = format_1h_tab(CFG, {"horizons": incomplete, "active_episode": None, "last_event": None}, "en", "abcd1234")
    assert "1h: incomplete" in gap
    assert "bybit ≥" in gap and "okx ≥" in gap and "binance ≥" in gap
    immature_view = screens()["calm"]
    immature_view = _with_horizons(immature_view, immature["1h"])
    assert "vol n/a" in format_btc(CFG, immature_view, "en")
    assert "объём н/д" in format_btc(CFG, immature_view, "ru")
    assert "1h: incomplete" in format_btc(CFG, _with_horizons(immature_view, incomplete["1h"]), "en")
    assert "1ч: неполные данные" in format_btc(CFG, _with_horizons(immature_view, incomplete["1h"]), "ru")


def test_event_tab_missing_venue_liquidation_is_not_zero():
    import copy
    view = copy.deepcopy(screens()["unusual"])
    anchor = view["active_episode"]["anchor"]["view"]
    anchor["liquidations"]["long"]["per_venue"]["okx"] = None
    text = format_event_tab(CFG, view, "en", "abcd1234")
    assert "okx n/a" in text and "okx $0" not in text
    assert "binance ≥" in text
    ru = format_event_tab(CFG, view, "ru", "abcd1234")
    assert "okx н/д" in ru
    assert "oi_change_pct_by_venue" in anchor


class _CM:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Conn(_CM):
    def __init__(self):
        self.users = {}
        self.allow = set()
        self.last_id = None
        self.views = {}
        self.opens = []
        self._pk = 1

    def transaction(self):
        return _CM()

    async def get_last_update_id(self, _name):
        return self.last_id

    async def set_last_update_id(self, _name, update_id):
        self.last_id = update_id

    async def allowlist_contains(self, uid):
        return uid in self.allow

    async def get_user(self, uid):
        return self.users.get(uid)

    async def join_user(self, *, telegram_user_id, chat_id, now, lang="ru"):
        self.users[telegram_user_id] = {
            "user_pk": self._pk, "telegram_user_id": telegram_user_id, "chat_id": chat_id,
            "status": "ACTIVE", "lang": lang, "joined_at": now, "stopped_at": None}
        self._pk += 1
        return self.users[telegram_user_id]["user_pk"]

    async def set_user_lang(self, uid, lang):
        if uid not in self.users or self.users[uid]["status"] != "ACTIVE":
            return False
        self.users[uid]["lang"] = lang
        return True

    async def fetch_btc_view(self, view_pk):
        return self.views.get(view_pk)

    async def insert_details_open(self, *, view_pk, tab, lang, opened_at):
        self.opens.append({"view_pk": view_pk, "tab": tab, "lang": lang, "opened_at": opened_at})


class _Store:
    def __init__(self, conn):
        self.conn = conn

    def connect(self):
        return self.conn


def _msg(uid, text, update_id):
    return {"update_id": update_id, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"},
                                                "text": text}}


def _cb(uid, data, update_id, message_id=None):
    message = {"chat": {"id": uid}}
    if message_id is not None:
        message["message_id"] = message_id
    return {"update_id": update_id, "callback_query": {"id": f"c{update_id}", "from": {"id": uid},
                                                       "message": message, "data": data}}


def test_start_and_lang_choice():
    from runtime.beta_bot import BetaBotHandler
    from beta_fakes import Clock
    conn = _Conn()
    conn.allow.add(2)
    h = BetaBotHandler(_Store(conn), CFG, switches=lambda: None, owner_user_id=1,
                       clock=Clock(datetime(2026, 6, 15, tzinfo=timezone.utc)))

    async def go():
        stranger = await h.handle(_msg(9, "/start", 1))
        assert "закрытая частная бета" in stranger[0].html
        assert conn.users == {}
        owner = await h.handle(_msg(1, "/start", 2))
        assert owner[0].buttons == [[("Русский", "pick:ru"), ("English", "pick:en")]]
        priv = await h.handle(_cb(1, "pick:ru", 3))
        assert "конфиденциальность" in priv[1].html
        assert priv[1].buttons == [[("Вступить", "join:ru")]]
        joined = await h.handle(_cb(1, "join:ru", 4))
        assert conn.users[1]["lang"] == "ru" and "/lang" in joined[1].html
        again = await h.handle(_msg(1, "/start", 5))
        assert "/btc" in again[0].html and again[0].buttons is None
        picker = await h.handle(_msg(1, "/lang", 6))
        assert picker[0].buttons == [[("Русский", "set:ru"), ("English", "set:en")]]
        saved = await h.handle(_cb(1, "set:en", 7))
        assert conn.users[1]["lang"] == "en" and "Language: English." in saved[1].html
        help_en = await h.handle(_msg(1, "/help", 8))
        assert "message language" in help_en[0].html
        alice = await h.handle(_msg(2, "/start", 9))
        assert alice[0].buttons == [[("Русский", "pick:ru"), ("English", "pick:en")]]
        en = await h.handle(_cb(2, "pick:en", 10))
        assert "privacy notice" in en[1].html.lower() and en[1].buttons == [[("Join", "join:en")]]
        await h.handle(_cb(2, "join:en", 11))
        assert conn.users[2]["lang"] == "en"
        conn.users[2]["status"] = "STOPPED"
        resume = await h.handle(_msg(2, "/start", 12))
        assert resume[0].buttons == [[("Join", "join:en")]]
        assert "Choose language" not in resume[0].html

    import asyncio
    asyncio.run(go())


def test_tab_edit_renders_persisted_view_not_live_state():
    from runtime.beta_bot import BetaBotHandler, _parse_tab
    from beta_fakes import Clock
    view = screens()["unusual"]
    live = dict(view)
    live["now"] = {"reference_price": 1.0}
    conn = _Conn()
    conn.users[1] = {"user_pk": 1, "telegram_user_id": 1, "chat_id": 1, "status": "ACTIVE",
                     "lang": "en", "joined_at": T0, "stopped_at": None}
    conn.views[7] = {"view_pk": 7, "payload": view, "payload_digest": "1a2b3c4d" + "ab" * 28,
                     "lang": "ru", "rendered_html": "stored"}
    h = BetaBotHandler(_Store(conn), CFG, switches=lambda: None, owner_user_id=1,
                       clock=Clock(datetime(2026, 6, 15, tzinfo=timezone.utc)))
    assert _parse_tab("o:7:event") == ("o", 7, "event")
    assert _parse_tab("e:7:1h") == ("e", 7, "1h")
    assert _parse_tab("o:" + "9" * 60 + ":1h") is None
    assert len("o:7:event") <= 64 and len("e:7:1h") <= 64

    async def go():
        opened = await h.handle(_cb(1, "o:7:event", 1))
        assert opened[1].kind == "message"
        edited = await h.handle(_cb(1, "e:7:1h", 2, message_id=42))
        assert edited[1].kind == "edit" and edited[1].message_id == 42
        expect = format_1h_tab(CFG, view, "ru", view_id8(conn.views[7]["payload_digest"]))
        assert edited[1].html == expect
        assert "1.0" not in edited[1].html or "BTC 1" not in edited[1].html
        assert format_1h_tab(CFG, live, "en", "zzzzzzzz") not in (edited[1].html,)
        assert conn.opens == [
            {"view_pk": 7, "tab": "event", "lang": "ru", "opened_at": h.clock()},
            {"view_pk": 7, "tab": "1h", "lang": "ru", "opened_at": h.clock()},
        ]
        assert "user" not in conn.opens[0]
        # a later user language does not restyle the stored view
        conn.users[1]["lang"] = "en"
        again = await h.handle(_cb(1, "e:7:event", 3, message_id=42))
        assert "СОБЫТИЕ" in again[1].html and "EVENT ·" not in again[1].html

    import asyncio
    asyncio.run(go())
