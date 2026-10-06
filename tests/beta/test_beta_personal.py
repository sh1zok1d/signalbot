"""The personal layer (PRE_BETA_SCOPE_DECISION_V1 §9 E; backlog C5, E1–E5): pure parts."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.i18n import fmt_clock, parse_tz, render_tz, t, tz_of, zone_name, KYIV

UTC = timezone.utc
T = datetime(2026, 10, 6, 6, 0, tzinfo=UTC)          # 09:00 Kyiv (summer time)


@pytest.mark.parametrize("raw, stored", [
    ("+3", "UTC+03:00"), ("UTC-5", "UTC-05:00"), ("+05:30", "UTC+05:30"), ("−4", "UTC-04:00"), ("gmt+0", "UTC+00:00"),
    ("Europe/Warsaw", "Europe/Warsaw"), ("america/new_york", "America/New_York"),
    ("+15", None), ("+3:75", None), ("Mars/Base", None), ("Warsaw", None), ("", None), (None, None)])
def test_a_time_zone_is_an_iana_name_or_a_fixed_offset(raw, stored):
    assert parse_tz(raw) == stored


def test_kyiv_is_the_default_and_an_unreadable_value_never_breaks_a_message():
    assert tz_of(None) is KYIV and tz_of("Nowhere/Land") is KYIV and tz_of("Europe/Kyiv") is KYIV
    assert fmt_clock(T, "ru") == "09:00 (Киев)" and fmt_clock(T, "en") == "09:00 Kyiv"


def test_every_clock_follows_the_participant_zone_inside_a_rendering():
    with render_tz("UTC+05:30"):
        assert fmt_clock(T, "ru") == "11:30 (UTC+5:30)" and fmt_clock(T, "en") == "11:30 UTC+5:30"
        # a template that names the zone gets the participant's (the catalog's «Киев» is gone, C5)
        assert t("ru", "dc_stats_built", when="Вт 06.10 11:30") == "Статистика по истории собрана Вт 06.10 11:30 (UTC+5:30)."
        assert t("en", "ev_title") == "<b>Events</b> (UTC+5:30 time)"
    with render_tz("America/New_York"):
        assert fmt_clock(T, "ru") == "02:00 (UTC−4)" and zone_name("en", T) == "UTC−4"
    assert fmt_clock(T, "ru") == "09:00 (Киев)"                    # the scope ends with the rendering
    assert t("ru", "ev_title") == "<b>События</b> (время — Киев)"


def test_the_briefing_slot_is_on_the_participants_clock():
    from beta.delivery import brief_slot
    assert brief_slot(T, "10:00") is None                                    # 09:00 Kyiv: before the slot
    d, at = brief_slot(T + timedelta(minutes=1), "09:00")
    assert (d.isoformat(), at) == ("2026-10-06", datetime(2026, 10, 6, 6, 0, tzinfo=UTC))
    assert brief_slot(T, "07:00", "UTC-05:00") is None                       # 01:00 there
    d, at = brief_slot(T, "07:00", "Asia/Tokyo")                              # 15:00 there
    assert (d.isoformat(), at) == ("2026-10-06", datetime(2026, 10, 5, 22, 0, tzinfo=UTC))


@pytest.mark.parametrize("raw, hhmm", [("7:30", "07:30"), ("07:30", "07:30"), ("0730", "07:30"), ("23.59", "23:59"),
                                       ("24:00", None), ("7:60", None), ("on", None), ("", None)])
def test_a_briefing_time_is_read_as_hh_mm(raw, hhmm):
    from runtime.beta_bot import _parse_hhmm
    assert _parse_hhmm(raw) == hhmm


def test_every_push_type_carries_its_one_tap_mute():
    """Backlog E2: under the unusual-hour push, the level / event / move alerts and the weekly report;
    never under a personal /alert (the participant's own)."""
    from beta.formatter import feedback_buttons, mute_row, parse_mute
    from beta.market_alerts import alert_buttons
    assert feedback_buttons("EV-1", "ru")[-1] == [("🔕 Не присылать такие", "m:hours")]
    for kind, mute in (("level", "m:levels"), ("event", "m:events"), ("move", "m:moves")):
        assert alert_buttons(kind, {}, "en")[-1] == [("🔕 Stop these", mute)]
    assert all(d[:2] != "m:" for row in alert_buttons("price", {}, "ru") for _l, d in row)
    assert mute_row("weekly", "ru") == [("🔕 Не присылать такие", "m:weekly")]
    assert parse_mute("m:levels") == (True, "levels") and parse_mute("a:weekly") == (False, "weekly")
    assert parse_mute("m:price") is None and parse_mute("u:levels") is None and parse_mute("a:" + "x" * 30) is None


def test_a_mute_button_counts_as_the_setting_it_makes_in_the_owner_report():
    from beta.usage import as_setting
    row = {"user_pk": 1, "action": "btn_mute", "detail": "levels", "at": T}
    assert as_setting(row) == {**row, "action": "cmd_push", "detail": "levels:off", "button": True}
    assert as_setting({**row, "action": "btn_unmute"})["detail"] == "levels:on"
    assert as_setting({**row, "action": "btn_check"}) == {**row, "action": "btn_check"}


def test_the_approach_of_a_personal_level_fires_once_within_the_hours_typical_move():
    """Backlog E1: set farther than the typical 1h move, now within it, not yet through, not yet told."""
    from beta.market_alerts import detect_price_approaches
    from beta.decision_format import format_alert
    blk = {"available": True, "price": 64700.0, "price_ts": T.isoformat(),
           "corridor": {"horizons": {"1h": {"typical_move_pct": 0.6}}}}
    a = {"price_alert_pk": 7, "user_pk": 3, "price": 65000.0, "direction": "above", "created_price": 63000.0,
         "approached_at": None}
    out = detect_price_approaches([a], block=blk, now=T)
    assert [c["key"] for c in out] == ["approach:7"] and out[0]["target_user_pk"] == 3
    assert round(out[0]["payload"]["distance_pct"], 3) == 0.464
    text = format_alert("approach", out[0]["payload"], "ru")
    assert text.startswith("<b>BTC подходит к вашему уровню 65 000</b>\n09:00 (Киев) · цена 64 700 (Binance, 09:00)"
                           " · до уровня 0,46% — меньше обычного хода за 1ч (±0,60%)")
    assert detect_price_approaches([{**a, "approached_at": T}], block=blk, now=T) == []        # once
    assert detect_price_approaches([{**a, "created_price": 64800.0}], block=blk, now=T) == []  # set close already
    assert detect_price_approaches([{**a, "price": 66000.0}], block=blk, now=T) == []           # still far
    assert detect_price_approaches([a], block={**blk, "price": 65100.0}, now=T) == []           # already through
    assert detect_price_approaches([a], block={**blk, "corridor": {"horizons": {}}}, now=T) == []   # no typical move
