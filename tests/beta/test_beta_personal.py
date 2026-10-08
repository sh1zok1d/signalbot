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
        # a named zone is labelled by its city, right on every date (review of #373, 5)
        assert fmt_clock(T, "ru") == "02:00 (New York)" and zone_name("en", T) == "New York"
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
    row = {"user_pk": 1, "action": "set_mute", "detail": "levels", "at": T}
    # a setting, never a button tap: a mute is a negative signal, not engagement (review of #373, 4)
    assert as_setting(row) == {**row, "action": "cmd_push", "detail": "levels:off"}
    assert as_setting({**row, "action": "set_unmute"})["detail"] == "levels:on"
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
    assert text.startswith("<b>BTC подходит к вашему уровню 65 000</b>\n09:00 (Киев) · цена 64 700 (Binance, 09:01)"
                           " · до уровня 0,46% — меньше обычного хода за 1ч (±0,60%)")
    assert detect_price_approaches([{**a, "approached_at": T}], block=blk, now=T) == []        # once
    assert detect_price_approaches([{**a, "created_price": 64800.0}], block=blk, now=T) == []  # set close already
    assert detect_price_approaches([{**a, "price": 66000.0}], block=blk, now=T) == []           # still far
    assert detect_price_approaches([a], block={**blk, "price": 65100.0}, now=T) == []           # already through
    assert detect_price_approaches([a], block={**blk, "corridor": {"horizons": {}}}, now=T) == []   # no typical move


def _brief_rows(user, start, end, step=timedelta(minutes=1), max_delay=timedelta(minutes=30)):
    """Every briefing row a notifier running every `step` would create for one participant."""
    from beta.delivery import brief_due
    u, rows, now = dict(user), [], start
    while now < end:
        due = brief_due(now, u, "08:00", max_delay)
        if due is not None:
            rows.append(due)
            u["last_brief_date"] = due[0]
        now += step
    return rows


def _utc(*a):
    return datetime(*a, tzinfo=UTC)


def test_the_briefing_is_neither_doubled_nor_lost_when_kyiv_goes_to_winter_time():
    """Owner requirement for package 4: Kyiv leaves summer time on 2026-10-25 (04:00 EEST → 03:00 EET, at
    01:00 UTC). Every participant gets one briefing per local date at their own slot; a slot inside the
    repeated hour comes once, at its first occurrence."""
    start, end = _utc(2026, 10, 23, 21, 0), _utc(2026, 10, 27, 0, 0)
    days = ["2026-10-24", "2026-10-25", "2026-10-26"]
    cases = [
        ({"brief_time": None, "tz": None},                     # 08:00 Kyiv
         [_utc(2026, 10, 24, 5, 0), _utc(2026, 10, 25, 6, 0), _utc(2026, 10, 26, 6, 0)]),
        ({"brief_time": "03:30", "tz": None},                  # inside the repeated hour on the 25th
         [_utc(2026, 10, 24, 0, 30), _utc(2026, 10, 25, 0, 30), _utc(2026, 10, 26, 1, 30)]),
        ({"brief_time": "04:00", "tz": None},                  # the first minute after the switch
         [_utc(2026, 10, 24, 1, 0), _utc(2026, 10, 25, 2, 0), _utc(2026, 10, 26, 2, 0)]),
        ({"brief_time": "07:00", "tz": "UTC+05:30"},           # a fixed half-hour offset: never moves
         [_utc(2026, 10, 24, 1, 30), _utc(2026, 10, 25, 1, 30), _utc(2026, 10, 26, 1, 30)]),
        ({"brief_time": "08:00", "tz": "Europe/Warsaw"},       # switches the same night (03:00 CEST → 02:00 CET)
         [_utc(2026, 10, 24, 6, 0), _utc(2026, 10, 25, 7, 0), _utc(2026, 10, 26, 7, 0)]),
    ]
    for user, slots in cases:
        rows = _brief_rows(user, start, end)
        assert [d.isoformat() for d, _ in rows] == days, user
        assert [at for _, at in rows] == slots, user
    # a notifier every 5 minutes, or one down through the whole repeated hour, gives the same rows
    for user, slots in cases:
        assert [at for _, at in _brief_rows(user, start, end, step=timedelta(minutes=5))] == slots, user
    # a notifier down from 00:30 to 01:01 UTC: the 03:30 slot was 31 minutes ago, too late, and the second
    # 03:30 on the clock (01:30 UTC) is never a slot of its own
    late = _brief_rows({"brief_time": "03:30", "tz": None}, _utc(2026, 10, 25, 1, 1), _utc(2026, 10, 25, 3, 0))
    assert late == []


def test_quiet_hours_follow_the_participants_wall_clock_across_the_switch():
    """23:00–07:00 on the wall clock: the night of 24→25.10 is nine UTC hours in Kyiv, the next one eight;
    a +05:30 participant's night never moves."""
    from beta.config import BetaConfig
    from beta.detector import in_quiet_hours, quiet_for_all
    cfg = BetaConfig.load()
    assert tuple(cfg.quiet_hours_kyiv) == ("23:00", "07:00")

    def quiet_minutes(tz, start, end):
        n, now = 0, start
        while now < end:
            n += in_quiet_hours(cfg, now, tz)
            now += timedelta(minutes=1)
        return n
    assert quiet_minutes(None, _utc(2026, 10, 24, 12, 0), _utc(2026, 10, 25, 12, 0)) == 9 * 60
    assert quiet_minutes(None, _utc(2026, 10, 25, 12, 0), _utc(2026, 10, 26, 12, 0)) == 8 * 60
    assert quiet_minutes("UTC+05:30", _utc(2026, 10, 24, 12, 0), _utc(2026, 10, 25, 12, 0)) == 8 * 60
    edges = [(_utc(2026, 10, 24, 19, 59), False), (_utc(2026, 10, 24, 20, 0), True),    # 23:00 EEST
             (_utc(2026, 10, 25, 0, 30), True), (_utc(2026, 10, 25, 1, 30), True),     # 03:30 twice
             (_utc(2026, 10, 25, 4, 59), True), (_utc(2026, 10, 25, 5, 0), False),     # 07:00 EET
             (_utc(2026, 10, 25, 20, 59), False), (_utc(2026, 10, 25, 21, 0), True)]   # 23:00 EET
    assert [in_quiet_hours(cfg, ts) for ts, _ in edges] == [q for _, q in edges]
    assert in_quiet_hours(cfg, _utc(2026, 10, 25, 17, 30), "UTC+05:30")                 # 23:00 there
    assert not in_quiet_hours(cfg, _utc(2026, 10, 25, 1, 30), "UTC+05:30")             # 07:00 there
    # a decision at 04:30 UTC on the 25th: night in Kyiv (06:30 EET), morning at +05:30 (10:00)
    ts = _utc(2026, 10, 25, 4, 30)
    assert quiet_for_all(cfg, ts, [None]) and not quiet_for_all(cfg, ts, [None, "UTC+05:30"])


def test_reasons_and_interview_slots():
    """Backlog H2 / H3 answers and the H4 slots on the participant's clock (two weekdays ahead)."""
    from runtime.beta_bot import _interview_slots, _parse_reason, _reason_buttons
    assert _parse_reason("q:n:level-12:late") == ("noise", "level-12", "late")
    assert _parse_reason("q:s:-:too_many") == ("stop", "-", "too_many")
    for bad in ("q:n:level-12:too_many", "q:s:-:late", "q:x:-:other", "q:n::late", "q:n:a:b:late"):
        assert _parse_reason(bad) is None, bad
    assert [d for row in _reason_buttons("s", "-", "ru") for _l, d in row][0] == "q:s:-:not_needed"
    fri = datetime(2026, 10, 9, 10, 0, tzinfo=UTC)                       # Friday 13:00 Kyiv
    with render_tz("UTC+00:00"):
        slots = _interview_slots(fri)
    assert [s.isoformat() for s in slots] == ["2026-10-12T12:00:00+00:00", "2026-10-12T18:00:00+00:00",
                                              "2026-10-13T12:00:00+00:00"]           # Monday, Monday, Tuesday
