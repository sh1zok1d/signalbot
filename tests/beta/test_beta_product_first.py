"""PRODUCT_FIRST_DECISION_V1 §3 rows 7-10 and BETA_COPY_CONTRACT_V1: the unusual-hour
gate, the push text, the /catchup and briefing text, the «Необычные часы» block, the
withheld-message notes and the never-show list. Pure; no DB."""
from datetime import datetime, timedelta, timezone

import pytest

from test_beta_context import CFG, T0
from test_beta_context_4h_interpretation import C

from beta import hour_gate as hg
from beta.config import LIQUIDATION_STRESS_LONG
from beta.detector import in_quiet_hours
from beta.formatter import format_catchup, format_push
from beta.i18n import assert_descriptive
from beta.market_view import UNUSUAL_HOURS_MAX, market_block, unusual_hours
from beta.models import Episode
from beta.state_tape import BUCKET, iso

UTC = timezone.utc
T = datetime(2026, 10, 20, 10, 5, tzinfo=UTC)          # 13:05 Kyiv (EEST)


def _ctx(price=0.5, oi=0.5, taker=0.5, rng=0.5, vol=0.5, *, venues=None, tier="mature", start=T,
         move=-1.9, oi_pct=2.4, delta=-84e6, open_=61950.0, close=60770.0):
    """A 1h reading with the given ranks; the shown values (move, OI, Delta) are set
    explicitly and the per-venue moves follow the aggregate sign unless given."""
    ctx = C(price, oi, taker, rng, tier=tier, venues=venues, start=start)
    ctx["percentiles"]["volume_notional_usd_sum"] = {"rank": vol, "tier": tier}
    ctx.update(open_median=open_, close_median=close, oi_venues=["binance", "bybit", "okx"],
               price_move_pct_median=move, oi_change_pct_median=oi_pct, taker_delta_notional_usd_sum=delta)
    if venues is None:
        ctx["price_move_pct_by_venue"] = {ex: move for ex in ("binance", "bybit", "okx")}
    return ctx


# ---- the gate -------------------------------------------------------------------------------------
def test_gate_needs_two_extreme_metrics_and_venue_agreement_only_on_mature_ranks():
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.9, taker=0.1, rng=0.97, vol=0.96))
    assert g["qualified"] and g["status"] == hg.QUALIFIED
    assert g["passed"] == {"range": True, "volume": True, "price": "down"}
    assert (g["venues_agree"], g["venues"]) == (3, 3) and g["window_start"] == iso(T)
    assert g["interpretation"]["key"] == "short_build"               # price down, OI up, taker negative
    assert hg.evaluate_hour(CFG, _ctx(price=0.96, rng=0.5, vol=0.5))["status"] == hg.NOT_UNUSUAL
    assert hg.evaluate_hour(CFG, _ctx(price=0.96, rng=0.96, vol=0.5))["qualified"]     # price up tail counts
    assert hg.evaluate_hour(CFG, _ctx(price=0.5, rng=0.96, vol=0.96))["qualified"]     # price not needed
    mixed = _ctx(price=0.02, rng=0.97, vol=0.96, venues={"binance": -2.0, "bybit": 0.3, "okx": 0.1})
    assert hg.evaluate_hour(CFG, mixed)["status"] == hg.VENUES_DISAGREE
    assert hg.evaluate_hour(CFG, _ctx(price=0.02, rng=0.97, vol=0.96, tier="building"))["status"] == hg.IMMATURE
    assert hg.evaluate_hour(CFG, None)["status"] == hg.CONTEXT_UNAVAILABLE
    assert hg.MIN_EXTREME_METRICS == 2


def test_gate_records_the_liquidation_confirmation_from_existing_episodes():
    ep = {"event_type": LIQUIDATION_STRESS_LONG, "triggered_at": iso(T + 3 * BUCKET), "opened_bucket": iso(T + 2 * BUCKET),
          "last_bucket": iso(T + 11 * BUCKET), "episode_id": "EV-1"}          # still qualifying at the decision bucket
    snap = {"rule_evaluations": {LIQUIDATION_STRESS_LONG: {"status": "QUALIFIES", "detail": {
        "voting": ["binance", "bybit", "okx"], "eligible": ["binance", "bybit", "okx"]}}}}
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.1, taker=0.1, rng=0.97, vol=0.96),
                         liquidation_episodes=[ep], snapshot=snap)
    assert g["interpretation"]["key"] == "long_flush"
    assert g["liquidation"] == {"side": "long", "episode_id": "EV-1", "voting": ["binance", "bybit", "okx"],
                                "eligible": ["binance", "bybit", "okx"]}


def test_quiet_hours_are_kyiv_wall_clock_and_wrap_midnight():
    assert in_quiet_hours(CFG, datetime(2026, 10, 20, 20, 0, tzinfo=UTC))          # 23:00 EEST
    assert in_quiet_hours(CFG, datetime(2026, 10, 20, 3, 59, tzinfo=UTC))          # 06:59
    assert not in_quiet_hours(CFG, datetime(2026, 10, 20, 4, 0, tzinfo=UTC))       # 07:00
    assert not in_quiet_hours(CFG, datetime(2026, 10, 20, 19, 59, tzinfo=UTC))     # 22:59
    assert in_quiet_hours(CFG, datetime(2026, 12, 20, 21, 30, tzinfo=UTC))         # 23:30 EET (winter)


# ---- the push (contract §1.2, §3.3-3.6, §3.13) --------------------------------------------------
def _episode():
    return Episode(episode_pk=1, public_id="EV-ABCDEF0123", symbol="BTCUSDT", event_type="TAKER_FLOW_EXTREME_SELL",
                   state="TRIGGERED", opened_bucket=T, opened_at=T, armed_at=T, triggered_at=T + BUCKET,
                   terminal_at=None, terminal_reason=None, rules_version="BETA_EVENT_RULES_V1",
                   rules_digest="a" * 64, code_version="c", calculation_version="0" * 16,
                   opening_tape_digest="b" * 64, trigger_tape_digest="b" * 64, last_bucket=T,
                   last_streak=2, reference_price=60770.0, reference_exchanges=("binance", "okx"))


def _lines(text):
    return [ln for ln in text.split("\n") if ln.strip()]


def test_push_unusual_hour_inferred_label_matches_the_reference_message():
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.9, taker=0.1, rng=0.97, vol=0.96))
    text = format_push(_episode(), lang="ru", gate=g)
    assert text == ("<b>BTC · необычный час</b>\n13:05–14:05 (Киев)\n\n"
                    "Похоже на снижение с новыми шортами\n"
                    "Цена −1,90% (61 950 → 60 770): падение глубже, чем в 95% часовых окон за 30 дней\n"
                    "OI +2,4% · Delta −$84 млн\n"
                    "Диапазон и объём — оба в топ-5% часовых окон за 30 дней\n"
                    "Биржи: 3 из 3 в одну сторону\n"
                    # the research registry's line for this 1h label (PRODUCT_DECISION_V2 §2.4)
                    "↳ Проверка показала: после импульса рост OI вместе с продолжением цены не давал более сильного "
                    "продолжения в следующий час, чем такой же импульс без роста OI (MARKET-02)")
    assert len(_lines(text)) <= 8
    assert_descriptive(text, "ru")
    assert_descriptive(format_push(_episode(), lang="en", gate=g), "en")


def test_push_factual_fallback_and_missing_delta_and_flush_lines():
    against = hg.evaluate_hour(CFG, _ctx(price=0.96, oi=0.1, taker=0.1, rng=0.97, vol=0.5, move=1.7,
                                         oi_pct=-1.8, delta=-22e6, open_=60300.0, close=61330.0))
    text = format_push(_episode(), lang="ru", gate=against)
    assert "Рост при снижении OI\n" in text
    assert "Цена +1,70% (60 300 → 61 330): рост сильнее, чем в 95% часовых окон за 30 дней" in text
    assert "OI −1,8% · Delta −$22 млн — против направления цены, без интерпретации" in text
    assert "Диапазон — в топ-5% часовых окон за 30 дней" in text and "оба" not in text
    nodelta = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.1, taker=0.5, rng=0.97, vol=0.96, delta=None))
    nodelta["interpretation"]["inputs"]["taker"] = "MISSING"
    text = format_push(_episode(), lang="ru", gate=nodelta)
    assert "Снижение при снижении OI\n" in text and "\nOI +2,4%\nDelta н/д — без неё не интерпретируем\n" in text
    ep = {"event_type": "LIQUIDATION_STRESS_SHORT", "triggered_at": iso(T + BUCKET), "opened_bucket": iso(T),
          "last_bucket": iso(T + 11 * BUCKET), "episode_id": "EV-2"}         # covers the decision bucket
    snap = {"rule_evaluations": {"LIQUIDATION_STRESS_SHORT": {"detail": {"voting": ["binance", "okx"],
                                                                         "eligible": ["binance", "bybit", "okx"]}}}}
    flush = hg.evaluate_hour(CFG, _ctx(price=0.96, oi=0.1, taker=0.9, rng=0.5, vol=0.96, move=2.6, oi_pct=-2.9,
                                       delta=95e6, open_=60900.0, close=62480.0),
                             liquidation_episodes=[ep], snapshot=snap)
    text = format_push(_episode(), lang="ru", gate=flush)
    assert "Похоже на вынос шортов\n" in text and "Ликвидации шортов — топ-5% на 2 из 3 бирж" in text
    assert "Объём — в топ-5% часовых окон за 30 дней" in text
    assert len(_lines(text)) <= 8 and "EV-" not in text


# ---- /catchup and the briefing (contract §1.1, §3.1, §3.2, §3.7-3.10) -----------------------------
def _view(market, *, kind="catchup", status="NO ACTIVE EVENTS", price=61880.0, h24=None):
    horizons = {"24h": h24 if h24 is not None else {
        "price_complete": True, "low": 60950.0, "high": 62300.0, "oi_change_pct": 1.2, "funding_rate_avg": 0.00008}}
    return {"product_status": status, "kind": kind, "now": {"reference_price": price},
            "data_through": iso(datetime(2026, 10, 20, 4, 55, tzinfo=UTC)), "horizons": horizons, "market": market}


def _market(h1, h4, *, hours=8, unusual=(), values=None, complete=True, history_days=None, immature=False):
    start = datetime(2026, 10, 19, 21, 0, tzinfo=UTC)
    v = values or {}
    return {"version": "BETA_MARKET_VIEW_V1", "window_hours": hours, "complete": complete,
            "window": {"window_start": iso(start), "window_end": iso(start + timedelta(hours=hours)),
                       "price_complete": True, "price_move_pct": 0.75, "range_width_pct": 1.3,
                       "open": 61420.0, "close": 61880.0, "low": 61210.0, "high": 61990.0,
                       "volume_notional_usd": 1.4e10, "oi_change_pct": -0.4},
            "unusual_hours": list(unusual), "interpretation": {"1h": h1, "4h": h4}, "levels": {},
            "values": {"1h": v.get("1h", {}), "4h": v.get("4h", {})},
            "history_days": history_days, "ranks_immature": immature}


def _interp(h, **kw):
    from beta import interpretation as it
    return it.interpret(CFG, C(**kw) if kw else None, horizon=h)


def test_brief_calm_night_matches_the_reference_message():
    m = _market(_interp("1h", price=0.5), _interp("4h", price=0.5))
    text = format_catchup(CFG, _view(m, kind="brief"), "ru", first_brief=True)
    assert text == ("<b>BTC за ночь · 00:00–08:00 (Киев)</b>\n"
                    "Цена 61 420 → 61 880 (+0,75%), мин 61 210, макс 61 990\n"
                    "Необычных часов не было.\n\n"
                    "<b>Сейчас</b>\n1ч: обычное состояние\n4ч: обычное состояние\n"
                    "24ч: 60 950–62 300, цена ближе к верхней границе · OI +1,2% за 24ч · средний Funding 0,008% (платят лонги)\n\n"
                    "Данные на 07:55 (Киев)\nОтключить утреннюю сводку: /brief off")
    assert_descriptive(text, "ru")
    assert "/brief off" not in format_catchup(CFG, _view(m, kind="brief"), "ru")          # only the first brief
    assert format_catchup(CFG, _view(m), "ru").startswith("<b>BTC за 8 ч · 00:00–08:00 (Киев)</b>")


def test_a_stale_tape_shows_no_corridor_or_levels_in_the_catchup_even_with_a_decision_block():
    """A2: «нет данных», never a number, whatever the decision block holds."""
    from test_beta_v2_format import block as decision_block
    m = _market(_interp("1h", price=0.5), _interp("4h", price=0.5), complete=False)
    view = {**_view(m, status="DATA STALE"), "decision": decision_block()}
    text = format_catchup(CFG, view, "ru")
    assert "Коридор и уровни сейчас не показываем: данные отстают." in text
    assert "Коридор 4ч" not in text and "Уровни" not in text and "62 950" not in text
    assert "Сегодня" in text and "CPI" in text                    # the calendar carries no market number
    fresh = format_catchup(CFG, {**_view(_market(_interp("1h", price=0.5), _interp("4h", price=0.5))),
                                 "decision": decision_block()}, "ru")
    assert "Уровни" in fresh and "4ч: 61 605–63 355" in fresh and "данные отстают" not in fresh


def test_brief_with_a_night_hour_withheld_by_quiet_hours_and_push_off_sees_no_note():
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.1, taker=0.1, rng=0.97, vol=0.96, move=-2.1, oi_pct=-3.4,
                                   delta=-120e6, start=datetime(2026, 10, 20, 0, 10, tzinfo=UTC)))
    hour = {"decision_ts": iso(datetime(2026, 10, 20, 1, 10, tzinfo=UTC)), "decision": "SUPPRESSED",
            "suppression_reason": "QUIET_HOURS", "gate": g}
    v1 = {"price_move_pct": -0.3, "oi_change_pct": -0.2, "taker_delta_notional_usd": -5e6}
    m = _market(_interp("1h", price=0.5), _interp("4h", price=0.1, oi=0.1, taker=0.1), unusual=[hour],
                values={"4h": {"price_move_pct": -2.4, "oi_change_pct": -4.0, "taker_delta_notional_usd": -300e6}})
    text = format_catchup(CFG, _view(m, kind="brief"), "ru")
    assert ("Необычный час: 03:10–04:10 (Киев) — похоже на выход лонгов\n"
            "Цена −2,1%, OI −3,4%, Delta −$120 млн\n"
            "Диапазон и объём — оба в топ-5% часовых окон за 30 дней\n"
            "Ночью с 23:00 до 07:00 бот не пишет, поэтому это только в сводке.") in text
    assert "4ч: похоже на выход лонгов — цена −2,4%, OI −4,0%, Delta −$300 млн" in text
    assert len(_lines(text)) <= 15
    assert_descriptive(text, "ru")
    off = format_catchup(CFG, _view(m, kind="brief"), "ru", push_enabled=False)
    assert "Необычный час: 03:10–04:10" in off and "бот не пишет" not in off
    cap = dict(hour, suppression_reason="DAILY_CAP")
    assert "Сообщения об этом часе не было: за сутки уже было 2." in format_catchup(
        CFG, _view(_market(_interp("1h", price=0.5), _interp("4h", price=0.5), unusual=[cap])), "ru")
    cool = dict(hour, suppression_reason="GLOBAL_COOLDOWN")
    assert "Отдельного сообщения не было: незадолго до этого бот уже писал." in format_catchup(
        CFG, _view(_market(_interp("1h", price=0.5), _interp("4h", price=0.5), unusual=[cool])), "ru")


def test_catchup_state_lines_for_divergence_missing_oi_immature_and_compression():
    div = _interp("1h", price=0.95, venues={"binance": 0.3, "bybit": -0.2, "okx": 0.0})
    m = _market(div, _interp("4h", price=0.5), hours=4,
                values={"1h": {"price_move_pct_by_venue": {"binance": 0.3, "bybit": -0.2, "okx": 0.0}}})
    text = format_catchup(CFG, _view(m), "ru")
    assert "<b>BTC за 4 ч · 00:00–04:00 (Киев)</b>" in text
    assert "1ч: биржи расходятся — Binance +0,30%, Bybit −0,20%, OKX 0,00%" in text
    oi_na = _interp("4h", price=0.95, missing=("oi_change_pct_median",))
    m = _market(_interp("1h", price=0.5), oi_na,
                values={"4h": {"price_move_pct": 1.74, "taker_delta_notional_usd": 60e6, "oi_venues": ["binance"]}})
    assert "4ч: рост, Delta +$60 млн · OI н/д: сейчас есть с 1 из 3 бирж" in format_catchup(CFG, _view(m), "ru")
    imm = _market(_interp("1h", price=0.9, tier="building"), _interp("4h", price=0.9, tier="building"),
                  values={"1h": {"price_move_pct": 0.4, "oi_change_pct": 0.6},
                          "4h": {"price_move_pct": 1.1, "oi_change_pct": 1.9}}, history_days=12, immature=True)
    text = format_catchup(CFG, _view(imm), "ru")
    assert "Необычные часы пока не отмечаем: мало истории (12 дн. из 30)." in text
    assert "1ч: мало истории — цена +0,4%, OI +0,6%" in text and "4ч: мало истории — цена +1,1%, OI +1,9%" in text
    comp = _market(_interp("1h", price=0.5), _interp("4h", price=0.5, rng=0.1, oi=0.6),
                   values={"4h": {"range_width_pct": 0.42, "oi_change_pct": 0.8}})
    assert "4ч: сжатие — диапазон 0,42%, в нижних 20% 4-часовых окон за 30 дней · OI +0,8%" in format_catchup(
        CFG, _view(comp), "ru")
    delta_na = _interp("4h", price=0.95, oi=0.9, missing=("taker_delta_notional_usd_sum",))
    text = format_catchup(CFG, _view(_market(_interp("1h", price=0.5), delta_na)), "ru")
    assert "4ч: рост с ростом OI — Delta н/д — без неё не интерпретируем" in text
    for lang in ("ru", "en"):
        assert_descriptive(format_catchup(CFG, _view(m), lang), lang)


def test_catchup_fails_closed_and_never_shows_internals():
    m = _market(_interp("1h"), _interp("4h"), complete=False)
    text = format_catchup(CFG, _view(m, status="DATA STALE"), "ru")
    assert "недостаточно" in text.lower() or "нельзя" in text.lower()
    assert "1ч: данные неполные" in text and "4ч: данные неполные" in text and "похоже" not in text
    assert "24ч: данные неполные" in text and "OI" not in text and "Funding" not in text
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.9, taker=0.1, rng=0.97, vol=0.96))
    hour = {"decision_ts": iso(T + BUCKET), "decision": "PUSH", "suppression_reason": None, "gate": g}
    text = format_catchup(CFG, _view(_market(_interp("1h", price=0.5), _interp("4h", price=0.5), unusual=[hour])), "ru")
    for banned in ("EV-", "TAKER_FLOW", "BETA_", "QUIET_HOURS", "kind", "площадк", "перцентиль", "ранг"):
        assert banned not in text


# ---- the «Необычные часы» block from the gate (decision §3.1b.3) ----------------------------------
def test_unusual_hours_come_from_qualified_decisions_one_per_hour_at_most_three():
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.9, taker=0.1, rng=0.97, vol=0.96))
    rows = []
    for i, (minutes, reason) in enumerate([(0, None), (20, "SAME_EVENT_COOLDOWN"), (70, "DAILY_CAP"),
                                           (200, "QUIET_HOURS"), (300, None), (420, None)]):
        rows.append({"decision_ts": T + timedelta(minutes=minutes), "decision": "PUSH" if reason is None else "SUPPRESSED",
                     "suppression_reason": reason, "gate": dict(g, window_start=iso(T + timedelta(minutes=minutes) - timedelta(hours=1)))})
    out = unusual_hours(rows, start=T - timedelta(hours=1), end=T + timedelta(hours=8))
    assert [h["decision_ts"] for h in out] == [iso(T), iso(T + timedelta(minutes=70)), iso(T + timedelta(minutes=200))]
    assert len(out) == UNUSUAL_HOURS_MAX == 3
    assert out[1]["suppression_reason"] == "DAILY_CAP"                     # withheld hours stay eligible
    assert unusual_hours(rows, start=T + timedelta(hours=9), end=T + timedelta(hours=10)) == []


def test_market_block_carries_values_beside_the_labels_and_the_history_days():
    from test_beta_context_4h_interpretation import _taker_hist
    n = int(timedelta(days=31, hours=24) / BUCKET)
    hist = dict(_taker_hist(n, T0))
    as_of = T0 + (n - 1) * BUCKET
    tape = {"as_of": as_of, "metrics": hist, "oi": {}}
    ctx = dict(C(0.92, 0.08, 0.90), window_end=iso(as_of + BUCKET))
    ctx["percentiles"]["price_move_pct_median"]["sample_size"] = 288 * 12
    state = {"context_1h": ctx, "context_4h": None, "open": {}, "last_ended": {}}
    block = market_block(CFG, {}, state, tape, window_hours=8, qualified=[])
    assert block["unusual_hours"] == [] and block["history_days"] == 12 and block["ranks_immature"] is False
    assert block["values"]["1h"]["price_move_pct"] == ctx["price_move_pct_median"]
    assert block["window"]["open"] == pytest.approx(100.0) and block["window"]["close"] == pytest.approx(100.0)
    assert block["interpretation"]["1h"]["key"] == "short_exit"


# ---- B2: "против направления цены" only when taker flow opposes the price move ----------------------
_AGAINST_RU = "против направления цены"


@pytest.mark.parametrize("price,oi,taker,oi_missing,against", [
    (0.96, 0.5, 0.95, False, False),       # rise, OI stable, taker aligned (up)
    (0.96, 0.5, 0.5, False, False),        # rise, OI stable, taker flat
    (0.96, 0.5, 0.05, False, True),        # rise, OI stable, taker down: against
    (0.04, 0.5, 0.05, False, False),       # decline, OI stable, taker aligned (down)
    (0.04, 0.5, 0.95, False, True),        # decline, OI stable, taker up: against
    (0.96, 0.1, 0.5, False, False),        # rise, OI down, taker flat (factual fallback)
    (0.96, 0.1, 0.05, False, True),        # rise, OI down, taker down: against (fallback)
    (0.04, 0.9, 0.95, False, True),        # decline, OI up, taker up: against (fallback)
    (0.96, 0.5, 0.95, True, False),        # rise, OI n/a, taker aligned
    (0.04, 0.5, 0.05, True, False),        # decline, OI n/a, taker aligned
    (0.04, 0.5, 0.95, True, True),         # decline, OI n/a, taker up: against
])
def test_against_wording_only_when_taker_opposes_price_in_push_and_catchup(price, oi, taker, oi_missing, against):
    move = 1.7 if price > 0.5 else -1.7
    delta = 50e6 if taker > 0.5 else (-50e6 if taker < 0.5 else 1e6)
    ctx = _ctx(price=price, oi=oi, taker=taker, rng=0.97, vol=0.96, move=move, delta=delta, oi_pct=0.1)
    if oi_missing:
        ctx["oi_change_pct_median"] = None
        ctx["percentiles"]["oi_change_pct_median"] = {"rank": None, "tier": None}
    g = hg.evaluate_hour(CFG, ctx)
    assert g["qualified"] and g["interpretation"]["kind"] == "FACTUAL", g["interpretation"]
    push = format_push(_episode(), lang="ru", gate=g)
    assert (_AGAINST_RU in push) is against, push
    assert ("against the price direction" in format_push(_episode(), lang="en", gate=g)) is against
    from beta import interpretation as it
    res = it.interpret(CFG, ctx, horizon="1h")
    values = {"1h": {"price_move_pct": move, "oi_change_pct": ctx["oi_change_pct_median"],
                     "taker_delta_notional_usd": delta, "oi_venues": [] if oi_missing else ["binance", "bybit", "okx"]}}
    text = format_catchup(CFG, _view(_market(res, _interp("4h", price=0.5), values=values)), "ru")
    line = next(ln for ln in text.split("\n") if ln.startswith("1ч: "))
    if oi_missing:
        assert _AGAINST_RU not in line and "OI н/д" in line                    # the OI-n/a line makes no taker claim
    else:
        assert (_AGAINST_RU in line) is against, line
        if not against:
            assert "Delta +$50 млн" in line or "Delta −$50 млн" in line or "Delta +$1 млн" in line
    assert_descriptive(push, "ru")
    assert_descriptive(text, "ru")


# ---- B3: liquidation evidence belongs to the confirming episode ------------------------------------
def test_liquidation_episode_earlier_in_the_hour_with_a_quiet_decision_bucket_prints_no_votes():
    """The LIQUIDATION_STRESS_LONG episode qualified 12:10-12:30 of the 12:05-13:05 hour and
    ended; the decision bucket (13:00) is quiet. The label may still read «похоже на вынос
    лонгов» (an existing episode overlaps the window), but the quiet bucket's votes are not
    that episode's evidence: no «0 из 3 бирж» line."""
    ep = {"event_type": LIQUIDATION_STRESS_LONG, "triggered_at": iso(T + 3 * BUCKET), "opened_bucket": iso(T + BUCKET),
          "last_bucket": iso(T + 5 * BUCKET), "episode_id": "EV-LIQ"}
    quiet = {"rule_evaluations": {LIQUIDATION_STRESS_LONG: {"status": "NOT_QUALIFIES", "detail": {
        "voting": [], "eligible": ["binance", "bybit", "okx"]}}}}
    g = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.1, taker=0.1, rng=0.97, vol=0.96, move=-2.4, oi_pct=-2.6,
                                   delta=-110e6, open_=62300.0, close=60805.0),
                         liquidation_episodes=[ep], snapshot=quiet)
    assert g["interpretation"]["key"] == "long_flush"
    assert g["liquidation"] == {"side": "long", "episode_id": "EV-LIQ"}           # no votes attached
    text = format_push(_episode(), lang="ru", gate=g)
    assert "Похоже на вынос лонгов\n" in text
    assert "Ликвидации" not in text and "0 из 3" not in text
    assert len(_lines(text)) <= 8
    # ... and the same stored gate in the /catchup «Необычные часы» block
    hour = {"decision_ts": iso(T + timedelta(hours=1)), "decision": "SUPPRESSED", "suppression_reason": "DAILY_CAP",
            "gate": g}
    cu = format_catchup(CFG, _view(_market(_interp("1h", price=0.5), _interp("4h", price=0.5), unusual=[hour])), "ru")
    assert "похоже на вынос лонгов" in cu and "0 из 3" not in cu and "Ликвидации" not in cu
    # a covering episode whose votes are present still prints them
    covering = dict(ep, last_bucket=iso(T + 11 * BUCKET))
    loud = {"rule_evaluations": {LIQUIDATION_STRESS_LONG: {"status": "QUALIFIES", "detail": {
        "voting": ["binance", "okx"], "eligible": ["binance", "bybit", "okx"]}}}}
    g2 = hg.evaluate_hour(CFG, _ctx(price=0.02, oi=0.1, taker=0.1, rng=0.97, vol=0.96),
                          liquidation_episodes=[covering], snapshot=loud)
    assert "Ликвидации лонгов — топ-5% на 2 из 3 бирж" in format_push(_episode(), lang="ru", gate=g2)
