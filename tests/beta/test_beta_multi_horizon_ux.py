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

from beta.formatter import (assert_descriptive, btc_buttons, format_1h_tab, format_24h_tab, format_btc,
                            format_event_tab, view_id8)
from beta.horizons import HORIZON_DIGEST, HORIZON_VERSION, build_horizons, empty_horizons, verify_horizon_digest
from beta.i18n import _CATALOG, fmt_clock, fmt_kyiv_hm, fmt_price, fmt_ratio, fmt_signed_pct, fmt_usd, kyiv
from beta.state_tape import BUCKET, metric_key

RU_DISCLAIMER = ("Экспериментальная закрытая бета. Статистика и описание рынка — "
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
    assert disc == []                      # /btc carries no disclaimer (only /start and /terms)
    assert len(body) <= 8, body
    assert_descriptive(html, "ru" if re.search("[а-яА-Я]", _plain(html)) else "en")
    return body


def _with_horizons(view, block, day="auto"):
    out = dict(view)
    if day == "auto":
        day = _day_block() if block else None
    out["horizons"] = {"version": HORIZON_VERSION, "digest": HORIZON_DIGEST, "1h": block, "24h": day}
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
        "oi_change_pct": -0.6,
        "oi_by_venue": {"binance": -0.9, "bybit": -0.4, "okx": 0.1},
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


def _day_block(**kw):
    base = {
        "price_complete": True,
        "volume_complete": True,
        "volume_partial": False,
        "buckets_present": 288,
        "buckets_expected": 288,
        "window_start": "2026-03-01T12:10:00+00:00",
        "window_end": "2026-03-02T12:10:00+00:00",
        "price_move_pct": -1.9,
        "range_width_pct": 2.8,
        "high": 113900.0,
        "low": 110800.0,
        "volume_notional_usd": 38e9,
        "baseline_days": {"range_width_pct": 30, "volume_notional_usd": 30},
        "baseline_median": {"range_width_pct": 2.0, "volume_notional_usd": 38e9 / 1.3},
        "range_ratio": 1.4,
        "volume_ratio": 1.3,
        "taker_delta_notional_usd_sum": 210e6,
        "funding_rate": 0.00006,
        "funding_rate_avg": 0.00009,
        "oi_change_pct": 2.1,
        "oi_by_venue": {"binance": 2.8, "bybit": 1.5, "okx": 0.9},
        "liquidations": {"buckets_missing": False, "venues": {
            "binance": {"long": {"amount": 42e6, "missing": False, "lower_bound": True},
                        "short": {"amount": 9e6, "missing": False, "lower_bound": True}},
            "bybit": {"long": {"amount": 61e6, "missing": False, "lower_bound": False},
                      "short": {"amount": 14e6, "missing": False, "lower_bound": False}},
            "okx": {"long": {"amount": 19e6, "missing": False, "lower_bound": False},
                    "short": {"amount": 6e6, "missing": False, "lower_bound": False}},
        }},
        "changes": [
            {"rule": "range", "direction": "wider", "w": 2.8, "p": 1.9},
            {"rule": "oi_price", "oi_up": True, "price_up": False},
        ],
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
    # the disclaimer lives in /start and /terms only (BETA_COPY_CONTRACT_V1 §5 rule 8; owner 2026-10-03)
    if lang == "ru":
        assert RU_DISCLAIMER not in plain
        assert "Киев" in plain or view.get("data_through") is None
    else:
        assert "not a trade instruction" not in plain
    if name in ("stale_open", "stale_none", "degraded"):
        assert (RU_FAIL if lang == "ru" else EN_FAIL) in plain
        assert "1ч:" not in plain and "1h:" not in plain
        assert "24ч:" not in plain and "24h:" not in plain
        assert "↑" not in plain and "↓" not in plain
    else:
        assert "1ч:" in plain or "1h:" in plain
    if name == "calm":
        assert ("спокойно" if lang == "ru" else "calm") in body[0]
        assert "83 500" in body[0] if lang == "ru" else "83,500" in body[0]
        assert ("1ч: −0,8% · объём 2,1× · диапазон 2,3× · OI −0,6%" if lang == "ru"
                else "1h: −0.8% · vol 2.1× · range 2.3× · OI −0.6%") in plain
        assert ("24ч: −1,9% · объём 1,3× · OI +2,1%" if lang == "ru"
                else "24h: −1.9% · vol 1.3× · OI +2.1%") in plain
    if name == "unusual":
        assert ("необычно сейчас" if lang == "ru" else "unusual now") in body[0]
        assert ("OI снизился во время падения" if lang == "ru" else "Open interest fell during the drop") in plain
    if name == "calmed":
        assert ("затихло" if lang == "ru" else "calmed") in body[0]
    if name == "ended":
        assert ("событие завершено" if lang == "ru" else "event ended") in body[0]
        assert ("пропуске данных" if lang == "ru" else "data gap") in plain
    if name == "history":
        assert ("бот собирает историю" if lang == "ru" else "history building") in body[0]
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
        assert ("Событие" if lang == "ru" else "Event") not in labels
        assert ("1ч" if lang == "ru" else "1h") not in labels
        assert ("24ч" if lang == "ru" else "24h") not in labels
    if name in ("stale_open", "degraded"):
        assert ("Событие" if lang == "ru" else "Event") in labels
        assert ("1ч" if lang == "ru" else "1h") not in labels
        assert ("24ч" if lang == "ru" else "24h") not in labels
    if name in ("calm", "history"):
        assert ("1ч" if lang == "ru" else "1h") in labels
        assert ("24ч" if lang == "ru" else "24h") in labels
        assert ("Событие" if lang == "ru" else "Event") not in labels
    if name in ("unusual", "calmed", "ended"):
        assert ("Событие" if lang == "ru" else "Event") in labels
        assert ("1ч" if lang == "ru" else "1h") in labels
        assert ("24ч" if lang == "ru" else "24h") in labels


def test_event_and_1h_tabs_both_languages():
    view = screens()["unusual"]
    for lang in ("ru", "en"):
        event = format_event_tab(CFG, view, lang, "1a2b3c4d")
        hour = format_1h_tab(CFG, view, lang, "1a2b3c4d")
        assert_descriptive(event, lang)
        assert_descriptive(hour, lang)
        for banned in ("EARLY", "ARMED", "TRIGGERED", "pct of 30d", "STRICT_QUALIFICATION_V1", "Now"):
            assert banned not in event and banned not in hour
        assert "1a2b3c4d" not in event and "ref " not in event
        assert view["active_episode"]["episode_id"] not in event
        assert ("Термины: /terms" if lang == "ru" else "Terms: /terms") in event
        assert ("Термины: /terms" if lang == "ru" else "Terms: /terms") in hour
        if lang == "ru":
            assert "СОБЫТИЕ · резкое падение" in event
            assert "OI " in event and "Binance" in event and "binance" not in event
            assert "ПОСЛЕДНИЙ ЧАС" in hour
            assert "2,3× от обычного для этого часа" in hour
            assert "Funding сейчас 0,006%" in hour
            assert "Delta: −$84 млн (продавцы)" in hour
            assert "OI −0,6%: Binance −0,9% · Bybit −0,4% · OKX +0,1%" in hour
            assert "≥ — нижняя граница: Binance передаёт не все ликвидации." in event
        else:
            assert "EVENT · sharp drop" in event
            assert "LAST HOUR" in hour
            assert "2.3× usual for this hour" in hour
            assert "Funding now 0.006%" in hour
            assert "Delta: −$84M (sellers)" in hour
            assert "OI −0.6%: Binance −0.9% · Bybit −0.4% · OKX +0.1%" in hour
            assert "≥ — lower bound: Binance does not report every liquidation." in hour


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
    # PRODUCT_DECISION_V2 §3: direct trade calls, targets, hype and unobservable attributions
    for sample in ("купить", "купите", "покупайте", "продай", "точка входа", "тейк-профит",
                   "цель", "таргет", "рекомендуем", "лонг сейчас", "шорт сейчас", "открывайте лонг",
                   "срочно", "памп", "обвал", "толкают", "киты", "закрытие шортов"):
        with pytest.raises(ForbiddenWordingError):
            assert_descriptive(sample, "ru")
    # forecasting vocabulary is allowed since PRODUCT_DECISION_V2
    for sample in ("вероятность роста", "прогноз", "ожидается", "разворот", "продолжение", "стоп 0,4%"):
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
    assert "Bybit n/a" in shown and "$0" not in shown.split("Bybit n/a")[0]
    assert "OKX $1.2M" in shown
    assert "Binance ≥" in shown
    ru = format_1h_tab(CFG, {"horizons": one_missing, "active_episode": None, "last_event": None}, "ru", "abcd1234")
    assert "Bybit н/д" in ru and "Bybit $0" not in ru
    gap = format_1h_tab(CFG, {"horizons": incomplete, "active_episode": None, "last_event": None}, "en", "abcd1234")
    assert "1h: incomplete" in gap
    assert "Bybit ≥" in gap and "OKX ≥" in gap and "Binance ≥" in gap
    immature_view = screens()["calm"]
    immature_view = _with_horizons(immature_view, immature["1h"])
    en_main = format_btc(CFG, immature_view, "en")
    ru_main = format_btc(CFG, immature_view, "ru")
    assert "vol n/a" not in en_main and "range n/a" not in en_main
    assert "объём н/д" not in ru_main and "диапазон н/д" not in ru_main
    assert "1h:" in en_main and "1ч:" in ru_main
    assert "1h: incomplete" in format_btc(CFG, _with_horizons(immature_view, incomplete["1h"]), "en")
    assert "1ч: неполные данные" in format_btc(CFG, _with_horizons(immature_view, incomplete["1h"]), "ru")


def test_event_tab_missing_venue_liquidation_is_not_zero():
    import copy
    view = copy.deepcopy(screens()["unusual"])
    anchor = view["active_episode"]["anchor"]["view"]
    anchor["liquidations"]["long"]["per_venue"]["okx"] = None
    text = format_event_tab(CFG, view, "en", "abcd1234")
    assert "OKX n/a" in text and "OKX $0" not in text
    assert "Binance ≥" in text
    ru = format_event_tab(CFG, view, "ru", "abcd1234")
    assert "OKX н/д" in ru
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

    async def record_activity(self, **_kw):
        return True

    async def record_rejected_start(self, *_a, **_k):
        return True

    async def redeem_invite(self, *_a, **_k):
        return "MISSING"

    async def waitlist_contains(self, _uid):
        return False

    async def waitlist_add(self, *_a, **_k):
        return True

    async def mark_privacy_notice_seen(self, *_a, **_k):
        return None

    async def get_admin_push_enabled(self):
        return False


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
    from beta_fakes import Clock, ON
    conn = _Conn()
    conn.allow.add(2)
    h = BetaBotHandler(_Store(conn), CFG, switches=lambda: ON, owner_user_id=1,
                       clock=Clock(datetime(2026, 6, 15, tzinfo=timezone.utc)))

    async def go():
        stranger = await h.handle(_msg(9, "/start", 1))
        assert "закрытой бете" in stranger[0].html and "closed beta" in stranger[0].html
        assert conn.users == {}
        owner = await h.handle(_msg(1, "/start", 2))
        assert owner[0].buttons == [[("Русский", "pick:ru"), ("English", "pick:en")]]
        priv = await h.handle(_cb(1, "pick:ru", 3))
        assert "конфиденциальность" in priv[1].html
        assert priv[1].buttons == [[("Вступить", "join:ru")]]
        joined = await h.handle(_cb(1, "join:ru", 4))
        assert conn.users[1]["lang"] == "ru" and "/lang" in joined[1].html
        again = await h.handle(_msg(1, "/start", 5))
        assert "/btc" in again[0].html and again[0].buttons == [[("Термины", "terms"), ("Другие монеты", "x:assets")]]
        picker = await h.handle(_msg(1, "/lang", 6))
        assert picker[0].buttons == [[("Русский", "set:ru"), ("English", "set:en")]]
        saved = await h.handle(_cb(1, "set:en", 7))
        assert conn.users[1]["lang"] == "en" and "Language: English." in saved[1].html
        help_en = await h.handle(_msg(1, "/help", 8))
        assert "message language" in help_en[0].html
        assert help_en[0].buttons == [[("Glossary", "terms"), ("Other coins", "x:assets")]]
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
        terms = await h.handle(_msg(1, "/terms", 13))
        assert terms[0].html.startswith("TERMS") and "History building" in terms[0].html
        gloss = await h.handle(_cb(1, "terms", 14))
        assert gloss[1].html.startswith("TERMS")

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
    assert _parse_tab("o:7:24h") == ("o", 7, "24h")
    assert _parse_tab("e:7:nope") is None
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
        day = await h.handle(_cb(1, "e:7:24h", 4, message_id=42))
        assert day[1].kind == "edit"
        assert day[1].html == format_24h_tab(CFG, view, "ru", view_id8(conn.views[7]["payload_digest"]))
        assert conn.opens[-1]["tab"] == "24h"

    import asyncio
    asyncio.run(go())


RU_TERMS = """ТЕРМИНЫ

Состояния
Спокойно — необычных состояний сейчас нет.
Необычно сейчас — открыто одно из событий ниже.
Затихло — событие было в последние 2 ч и закончилось.
Событие завершено — событие прервалось по технической причине (нет данных, лимит длительности, смена версии).
Бот собирает историю — меньше 30 дней данных, сравнивать пока не с чем.
Данные неполные — свежих данных не хватает, отсутствие событий подтвердить нельзя.

События
Резкий рост / падение — за 5 мин цена прошла больше, чем в 95% пятиминуток за 30 дней, и одновременно OI заметно снизился, минимум на 2 биржах.
Набор OI в узком диапазоне — 45 мин подряд OI растёт сильнее обычного, а цена стоит в узком диапазоне.
Агрессивные покупки / продажи — две пятиминутки подряд Delta в верхних / нижних 5% за 30 дней.
Ликвидации лонгов / шортов — ликвидации одной стороны в верхних 5% за 30 дней, минимум на 2 биржах одновременно.

Показатели
OI (open interest) — общее число открытых фьючерсных контрактов. Растёт, когда открывается больше, чем закрывается.
Funding — регулярный платёж между лонгами и шортами на бессрочных фьючерсах. Плюс — лонги платят шортам, минус — наоборот.
Delta — разница между рыночными покупками и продажами в $. Минус — нетто продавали.
Объём — сумма сделок в $ по Binance, Bybit и OKX.
Диапазон — от минимума до максимума цены за период, в % от цены.
Ликвидации — принудительное закрытие позиций биржей, по каждой бирже отдельно.
≥ — нижняя граница: Binance публикует не все ликвидации.
$0* — ноль по неполным данным: это не значит, что ликвидаций не было.
н/д — данных нет или они неполные. Это не ноль.
× от обычного — во сколько раз больше обычного: для 1ч — в это же время суток за 30 дней, для 24ч — медиана за 30 дней. Сравнение появляется, когда накоплено 20 дней истории.
↑ ↓ — только направление, не сила.
Время — киевское.
High impact — за прошлый календарный час цена прошла много относительно объёма торгов. Исторически следующий час был таким же примерно в 1 из 5 случаев (обычно 1 из 10). Направление цены это не показывает."""

EN_TERMS = """TERMS

States
Calm — no unusual state right now.
Unusual now — one of the events below is open.
Calmed — an event happened in the last 2h and has ended.
Event ended — the event stopped for a technical reason (no data, duration limit, version change).
History building — less than 30 days of data, nothing to compare with yet.
Data incomplete — fresh data is insufficient; the absence of events cannot be confirmed.

Events
Sharp rise / drop — over 5 min the price moved more than in 95% of 5-minute periods of the last 30 days, while OI fell noticeably, on at least 2 venues.
OI build-up in a narrow range — for 45 min in a row OI grows faster than usual while the price stays in a narrow range.
Aggressive buying / selling — Delta in the top / bottom 5% of the last 30 days for two 5-minute periods in a row.
Long / short liquidations — one side's liquidations in the top 5% of the last 30 days, on at least 2 venues at once.

Metrics
OI (open interest) — total number of open futures contracts. It rises when more contracts are opened than closed.
Funding — a periodic payment between longs and shorts on perpetual futures. Positive — longs pay shorts; negative — the reverse.
Delta — difference between market buys and market sells in $. Negative — net selling.
Volume — total traded value in $ on Binance, Bybit and OKX.
Range — from the lowest to the highest price in the period, in % of the price.
Liquidations — positions force-closed by the exchange, shown per venue.
≥ — lower bound: Binance does not publish every liquidation.
$0* — zero from incomplete data: it does not mean there were no liquidations.
n/a — no data or incomplete data. This is not zero.
× usual — how many times larger than usual: for 1h, the same time of day over 30 days; for 24h, the 30-day median. The comparison appears once 20 days of history are collected.
↑ ↓ — direction only, not strength.
Time — Kyiv time.
High impact — in the last clock hour the price moved a lot relative to traded volume. Historically the following hour was like this about 1 in 5 times (usually 1 in 10). It says nothing about price direction."""


def _baseline_view(days_1h, days_24h, *, range_ratio, volume_ratio):
    hour = _hour_block(
        price_move_pct=-0.2, oi_change_pct=0.4,
        range_ratio=range_ratio, volume_ratio=volume_ratio,
        baseline_days={"range_width_pct_median": days_1h, "volume_notional_usd_sum": days_1h,
                       "price_move_pct_median": days_1h})
    day = _day_block(
        price_move_pct=-0.2, oi_change_pct=0.4,
        range_ratio=range_ratio, volume_ratio=volume_ratio,
        baseline_days={"range_width_pct": days_24h, "volume_notional_usd": days_24h})
    return _with_horizons(screens()["calm"], hour, day)


def test_immature_baseline_omits_main_ratios_and_tabs_count_down():
    from beta.i18n import t
    for key in ("h1_ratio_wait", "h1_ratio_wait_one", "h24_ratio_wait", "h24_ratio_wait_one",
                "ratio_unavailable", "terms"):
        for lang in ("ru", "en"):
            text = t(lang, key, n=16) if "{n}" in t(lang, key) else t(lang, key)
            assert_descriptive(text, "ru")
            assert_descriptive(text, "en")

    immature = _baseline_view(4, 4, range_ratio=None, volume_ratio=None)
    ru, en = format_btc(CFG, immature, "ru"), format_btc(CFG, immature, "en")
    _budget(ru)
    _budget(en)
    assert "1ч: −0,2% · OI +0,4%" in ru
    assert "24ч: −0,2% · OI +0,4%" in ru
    assert "объём" not in ru.split("1ч:")[1].split("\n")[0]
    assert "диапазон" not in ru.split("1ч:")[1].split("\n")[0]
    assert "н/д" not in ru.split("1ч:")[1].split("\n")[0]
    assert "н/д" not in ru.split("24ч:")[1].split("\n")[0]
    assert "1h: −0.2% · OI +0.4%" in en
    assert "24h: −0.2% · OI +0.4%" in en
    assert "vol " not in en.split("1h:")[1].split("\n")[0]
    assert "range " not in en.split("1h:")[1].split("\n")[0]
    assert "n/a" not in en.split("1h:")[1].split("\n")[0]
    assert "n/a" not in en.split("24h:")[1].split("\n")[0]
    ru_1h, en_1h = format_1h_tab(CFG, immature, "ru"), format_1h_tab(CFG, immature, "en")
    ru_24, en_24 = format_24h_tab(CFG, immature, "ru"), format_24h_tab(CFG, immature, "en")
    assert ru_1h.count("(сравнение с обычным — через ~16 дн.)") == 2
    assert en_1h.count("(comparison with usual in ~16 days)") == 2
    assert ru_24.count("(сравнение с медианой 30 дн. — через ~16 дн.)") == 2
    assert en_24.count("(30d comparison in ~16 days)") == 2
    assert "н/д от обычного" not in ru_1h and "n/a usual" not in en_1h
    for text, lang in ((ru_1h, "ru"), (en_1h, "en"), (ru_24, "ru"), (en_24, "en")):
        assert_descriptive(text, "ru")
        assert_descriptive(text, "en")

    almost = _baseline_view(19, 19, range_ratio=None, volume_ratio=None)
    assert "(сравнение с обычным — через ~1 дн.)" in format_1h_tab(CFG, almost, "ru")
    assert "(comparison with usual in ~1 day)" in format_1h_tab(CFG, almost, "en")
    assert "~1 days" not in format_1h_tab(CFG, almost, "en")
    assert "(сравнение с медианой 30 дн. — через ~1 дн.)" in format_24h_tab(CFG, almost, "ru")
    assert "(30d comparison in ~1 day)" in format_24h_tab(CFG, almost, "en")
    assert "~1 days" not in format_24h_tab(CFG, almost, "en")
    almost_main = format_btc(CFG, almost, "ru")
    _budget(almost_main)
    assert "1ч: −0,2% · OI +0,4%" in almost_main
    split = _with_horizons(screens()["calm"], _hour_block(
        range_ratio=None, volume_ratio=None,
        baseline_days={"range_width_pct_median": 4, "volume_notional_usd_sum": 19,
                       "price_move_pct_median": 4}), _day_block())
    split_en = format_1h_tab(CFG, split, "en")
    assert "(comparison with usual in ~16 days)" in split_en
    assert "(comparison with usual in ~1 day)" in split_en

    mature = _baseline_view(20, 30, range_ratio=2.3, volume_ratio=2.1)
    assert "2,3× от обычного для этого часа" in format_1h_tab(CFG, mature, "ru")
    assert "2.1× usual for this hour" in format_1h_tab(CFG, mature, "en")
    assert "2,3× от медианы 30 дн." in format_24h_tab(CFG, mature, "ru")
    assert "2.1× 30d median" in format_24h_tab(CFG, mature, "en")
    assert "1ч: −0,2% · объём 2,1× · диапазон 2,3× · OI +0,4%" in format_btc(CFG, mature, "ru")
    assert "1h: −0.2% · vol 2.1× · range 2.3× · OI +0.4%" in format_btc(CFG, mature, "en")
    _budget(format_btc(CFG, mature, "en"))

    missing = _baseline_view(20, 20, range_ratio=None, volume_ratio=None)
    assert "объём н/д" in format_btc(CFG, missing, "ru")
    assert "vol n/a" in format_btc(CFG, missing, "en")
    assert format_1h_tab(CFG, missing, "ru").count("(сравнение недоступно)") == 2
    assert format_1h_tab(CFG, missing, "en").count("(comparison unavailable)") == 2
    assert format_24h_tab(CFG, missing, "ru").count("(сравнение недоступно)") == 2
    assert format_24h_tab(CFG, missing, "en").count("(comparison unavailable)") == 2
    assert "через ~" not in format_1h_tab(CFG, missing, "ru")
    _budget(format_btc(CFG, missing, "ru"))


def test_glossary_is_verbatim_and_passes_both_forbidden_lists():
    from beta.i18n import t
    from beta.i18n_decision import DECISION_TERMS
    assert t("ru", "terms") == RU_TERMS + DECISION_TERMS["ru"]
    assert t("en", "terms") == EN_TERMS + DECISION_TERMS["en"]
    assert_descriptive(RU_TERMS, "ru")
    assert_descriptive(EN_TERMS, "en")
    assert_descriptive(RU_TERMS, "en")


def test_24h_tab_renders_changes_and_terms_footer():
    view = screens()["unusual"]
    ru = format_24h_tab(CFG, view, "ru", "1a2b3c4d")
    en = format_24h_tab(CFG, view, "en", "1a2b3c4d")
    assert_descriptive(ru, "ru")
    assert_descriptive(en, "en")
    assert "1a2b3c4d" not in ru and "ref " not in ru
    assert "ПОСЛЕДНИЕ 24 Ч" in ru and "Термины: /terms" in ru.split("\n")[-1]
    assert "диапазон шире: 2,8% против 1,9%" in ru
    assert "OI вырос, пока цена падала" in ru
    assert "Крупных изменений к предыдущим 24 ч нет" not in ru
    assert "Delta: +$210 млн (покупатели)" in ru
    assert "Funding сейчас 0,006% · среднее за 24 ч 0,009%" in ru
    assert "Высокий импакт" not in ru and "High impact" not in en
    assert "LAST 24H" in en and "Terms: /terms" in en.split("\n")[-1]
    assert "range wider: 2.8% vs 1.9%" in en
    assert "OI rose while price fell" in en
    assert "Delta: +$210M (buyers)" in en
    none = format_24h_tab(CFG, _with_horizons(view, _hour_block(), _day_block(changes=[])), "en", "abcd")
    assert "No large change vs previous 24h" in none


def _h24_rows(as_of, *, drop=()):
    out = {}
    for i in range(288):
        b = as_of - i * BUCKET
        if b in drop:
            continue
        row = {"c:volume_notional_usd_sum": 1.0, "c:taker_delta_notional_usd_sum": 1.0,
               "c:funding_rate_median": 0.0001}
        for ex in EXS:
            row[metric_key(ex, "kline_open")] = 100.0
            row[metric_key(ex, "kline_high")] = 101.0
            row[metric_key(ex, "kline_low")] = 99.0
            row[metric_key(ex, "kline_close")] = 100.0
        out[b] = row
    return out


def test_24h_completeness_and_immature_baseline():
    from beta.horizons import rolling_24h_values
    as_of = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    full = rolling_24h_values(CFG, _h24_rows(as_of), as_of)
    assert full["price_complete"] and full["volume_complete"] and full["buckets_present"] == 288
    drop6 = {as_of - i * BUCKET for i in range(2, 8)}
    ok = rolling_24h_values(CFG, _h24_rows(as_of, drop=drop6), as_of)
    assert ok["buckets_present"] == 282 and ok["price_complete"] and not ok["volume_complete"]
    assert ok["volume_partial"]
    drop7 = {as_of - i * BUCKET for i in range(2, 9)}
    thin = rolling_24h_values(CFG, _h24_rows(as_of, drop=drop7), as_of)
    assert thin["buckets_present"] == 281 and not thin["price_complete"] and thin["volume_partial"]
    first = as_of - 287 * BUCKET
    no_first = rolling_24h_values(CFG, _h24_rows(as_of, drop={first}), as_of)
    assert no_first["buckets_present"] == 287 and not no_first["price_complete"]
    no_last = rolling_24h_values(CFG, _h24_rows(as_of, drop={as_of}), as_of)
    assert not no_last["price_complete"]
    partial = rolling_24h_values(CFG, _h24_rows(as_of, drop={as_of - 3 * BUCKET}), as_of)
    assert partial["buckets_present"] == 287 and partial["price_complete"] and partial["volume_partial"]
    shown = format_24h_tab(CFG, {"horizons": {"24h": {
        "price_complete": True, "volume_complete": False, "volume_partial": True,
        "window_end": as_of.isoformat(), "price_move_pct": -1.0, "range_width_pct": 1.0,
        "high": 101.0, "low": 99.0, "volume_notional_usd": 287.0, "range_ratio": None,
        "volume_ratio": None, "oi_change_pct": None, "oi_by_venue": {},
        "taker_delta_notional_usd_sum": None, "funding_rate": None, "funding_rate_avg": None,
        "liquidations": {"venues": {}}, "changes": [],
    }}}, "ru")
    assert "(неполные)" in shown and "от медианы 30 дн." not in shown.split("Объём")[1].split("\n")[0]
    immature = build_horizons(CFG, as_of_bucket=as_of, metrics_by_bucket=_series(as_of, days=10, vol=1e6))
    assert immature["24h"]["baseline_days"]["volume_notional_usd"] < 20
    assert immature["24h"]["volume_ratio"] is None


def test_oi_asof_tolerance_unit_and_median():
    from beta.horizons import _oi_for
    from beta.oi_asof import pick_oi_asof, venue_oi_change_pct
    t = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
    tol = timedelta(minutes=2)
    assert pick_oi_asof([{"ts": t, "oi_raw": 110.0, "oi_unit": "base", "contract_value": None}], t)["oi_raw"] == 110
    assert pick_oi_asof([{"ts": t - tol, "oi_raw": 100.0, "oi_unit": "base", "contract_value": 1.0}], t)["oi_raw"] == 100
    assert pick_oi_asof([{"ts": t - tol - timedelta(microseconds=1), "oi_raw": 1, "oi_unit": "base",
                          "contract_value": None}], t) is None
    assert pick_oi_asof([{"ts": t + timedelta(seconds=1), "oi_raw": 1, "oi_unit": "base",
                          "contract_value": None}], t) is None
    clash = [{"ts": t, "oi_raw": 1.0, "oi_unit": "base", "contract_value": None},
             {"ts": t, "oi_raw": 2.0, "oi_unit": "base", "contract_value": None}]
    assert pick_oi_asof(clash, t) is None
    same = {"oi_raw": 100.0, "oi_unit": "base", "contract_value": None}
    assert venue_oi_change_pct(same, {"oi_raw": 90.0, "oi_unit": "base", "contract_value": None}) == pytest.approx(-10)
    assert venue_oi_change_pct(same, {"oi_raw": 110.0, "oi_unit": "contracts", "contract_value": None}) is None
    assert venue_oi_change_pct(
        {"oi_raw": 100.0, "oi_unit": "contracts", "contract_value": 0.01},
        {"oi_raw": 110.0, "oi_unit": "contracts", "contract_value": 0.02}) is None
    start, end = t - timedelta(hours=1), t
    got = _oi_for(CFG, start, end, {
        start: {"binance": {"oi_raw": 100, "oi_unit": "base", "contract_value": None},
                "bybit": {"oi_raw": 200, "oi_unit": "base", "contract_value": None},
                "okx": None},
        end: {"binance": {"oi_raw": 110, "oi_unit": "base", "contract_value": None},
              "bybit": {"oi_raw": 180, "oi_unit": "base", "contract_value": None},
              "okx": None},
    })
    assert got["oi_by_venue"]["okx"] is None
    assert got["oi_by_venue"]["binance"] == pytest.approx(10)
    assert got["oi_by_venue"]["bybit"] == pytest.approx(-10)
    assert got["oi_change_pct"] == pytest.approx(0)


def test_changes_vs_previous_24h_each_rule_cap_and_none():
    from beta.horizons import select_changes
    fired = select_changes(
        CFG, range_w=3, range_p=1, volume_w=3, volume_p=1, volume_w_complete=True, volume_p_complete=True,
        price_w=-2, oi_w=2, funding_now=0.01, funding_p=-0.01)
    assert [row["rule"] for row in fired] == ["range", "volume", "oi_price"]
    assert fired[0]["direction"] == "wider" and fired[2]["oi_up"] and not fired[2]["price_up"]
    narrower = select_changes(
        CFG, range_w=1, range_p=2, volume_w=1, volume_p=2, volume_w_complete=True, volume_p_complete=True,
        price_w=None, oi_w=None, funding_now=None, funding_p=None)
    assert [row["direction"] for row in narrower] == ["narrower", "lower"]
    funding = select_changes(
        CFG, range_w=1, range_p=1, volume_w=1, volume_p=1, volume_w_complete=True, volume_p_complete=True,
        price_w=0.2, oi_w=0.2, funding_now=-0.01, funding_p=0.01)
    assert funding == [{"rule": "funding", "positive": False}]
    positive = select_changes(
        CFG, range_w=None, range_p=None, volume_w=None, volume_p=None, volume_w_complete=False,
        volume_p_complete=False, price_w=None, oi_w=None, funding_now=0.01, funding_p=-0.02)
    assert positive == [{"rule": "funding", "positive": True}]
    quiet = select_changes(
        CFG, range_w=1.1, range_p=1, volume_w=1.1, volume_p=1, volume_w_complete=True, volume_p_complete=True,
        price_w=0.2, oi_w=0.2, funding_now=0.01, funding_p=0.02)
    assert quiet == []
