"""The external review of #373 (package 4): each participant's own push budget, /tz offsets, the weekly
report in the recipient's night, a mute is not a reaction, the zone label of a shown moment."""
from datetime import datetime, timedelta, timezone

import pytest

from beta.config import BetaConfig

UTC = timezone.utc
CFG = BetaConfig.load()


def _snapshot():
    from beta.models import CORE_FAMILIES
    return {"evaluation_fresh": True, "families": {f: {"usable": True} for f in CORE_FAMILIES}}


def _decide(ts, recipients, would_today, last_any=None):
    from beta.detector import push_policy
    return push_policy(CFG, decision_ts=ts, evaluated_at=ts, snapshot=_snapshot(), last_same_type_terminal=None,
                       last_same_type_would_push=None, would_push_today=would_today, push_enabled=True,
                       hour={"qualified": True}, last_any_would_push=last_any, recipients=recipients)


def test_1_one_participant_elsewhere_never_spends_the_kyiv_participants_day(monkeypatch):
    """The reviewer's case: unusual hours at 01:00, 02:30 and 09:00 UTC. Kyiv alone: QUIET, QUIET, PUSH.
    Kyiv + Los Angeles: the night hours go to LA, and the 12:00 Kyiv hour still goes to Kyiv (it was
    DAILY_CAP: LA's two pushes had spent the one shared day)."""
    from beta import hour_gate
    monkeypatch.setattr(hour_gate, "is_qualified", lambda hour: True)
    day = datetime(2026, 10, 14, tzinfo=UTC)
    hours = [day + timedelta(hours=1), day + timedelta(hours=2, minutes=30), day + timedelta(hours=9)]
    kyiv = {"tz": None, "times": []}
    assert [_decide(ts, [kyiv], n)[1:] for n, ts in enumerate(hours[:2])] == [("SUPPRESSED", "QUIET_HOURS")] * 2
    assert _decide(hours[2], [kyiv], 0)[1:] == ("PUSH", None)
    k, la = {"tz": None, "times": []}, {"tz": "America/Los_Angeles", "times": []}
    out, would = [], 0
    for ts in hours:
        got = _decide(ts, [k, la], would)
        out.append(got[1:])
        if got[0]:
            would += 1
            for r in (k, la):                                   # a delivery that is sent or still on the way
                from beta.detector import in_quiet_hours
                if not in_quiet_hours(CFG, ts, r["tz"]):
                    r["times"].append(ts)
    assert out == [("PUSH", None), ("PUSH", None), ("PUSH", None)]
    # LA's own day (the 13th there) is now spent: another hour while only LA is awake is LA's DAILY_CAP
    late = day + timedelta(hours=3, minutes=30)                    # 20:30 on the 13th in LA, 06:30 Kyiv
    assert _decide(late, [k, la], would)[1:] == ("SUPPRESSED", "DAILY_CAP")
    # the count of all decisions of the UTC day is only a higher fuse
    assert _decide(hours[2], [k, la], CFG["push_decisions_fuse_per_utc_day"])[1:] == ("SUPPRESSED", "DAILY_CAP")
    assert _decide(hours[2], [k, la], CFG["max_new_pushes_per_utc_day"])[1:] == ("PUSH", None)


def test_1_own_day_is_the_participants_own_calendar_date():
    from beta.detector import own_day_count
    ts = datetime(2026, 10, 14, 23, 30, tzinfo=UTC)                 # 15th in Kyiv and Tokyo, 14th in LA
    times = [datetime(2026, 10, 14, 18, 0, tzinfo=UTC), datetime(2026, 10, 14, 22, 0, tzinfo=UTC)]   # LA 14th ×2
    assert own_day_count(times, ts, None) == 1 and own_day_count(times, ts, "America/Los_Angeles") == 2


@pytest.mark.parametrize("raw, stored", [("10", None), ("12", None), ("x5", None), ("UTC10", None), ("3", None),
                                         ("+10", "UTC+10:00"), ("UTC+12", "UTC+12:00"), ("−3:30", "UTC-03:30"),
                                         ("gmt-5", "UTC-05:00"), ("Europe/Warsaw", "Europe/Warsaw")])
def test_2_an_offset_needs_its_sign_and_a_bare_number_is_refused(raw, stored):
    from beta.i18n import parse_tz
    assert parse_tz(raw) == stored


def test_2_and_5_kyiv_in_any_spelling_is_kyiv_and_a_city_is_labelled_by_its_name():
    from beta.i18n import fmt_clock, render_tz, tz_of, zone_name, KYIV
    assert tz_of("Europe/Kiev") is KYIV and tz_of("KYIV") is KYIV
    with render_tz("Europe/Kiev"):
        assert zone_name("ru") == "Киев"
    # an event on 28.10 shown on 08.10 to Warsaw: never «UTC+2» beside a moment that is UTC+1
    ev = datetime(2026, 10, 28, 18, 0, tzinfo=UTC)
    with render_tz("Europe/Warsaw"):
        assert fmt_clock(ev, "ru") == "19:00 (Warsaw)" and zone_name("en") == "Warsaw"
    with render_tz("UTC+05:30"):
        assert zone_name("en", ev) == "UTC+5:30"                     # a fixed offset never changes


def test_3_the_weekly_report_waits_for_the_end_of_the_recipients_night():
    from beta.detector import quiet_end
    slot = datetime(2026, 5, 17, 16, 0, tzinfo=UTC)                 # Sunday 19:00 Kyiv = 01:00 Monday Tokyo
    assert quiet_end(CFG, slot, None) is None
    assert quiet_end(CFG, slot, "Asia/Tokyo") == datetime(2026, 5, 17, 22, 0, tzinfo=UTC)   # 07:00 Tokyo
    assert quiet_end(CFG, datetime(2026, 5, 17, 21, 0, tzinfo=UTC), None) == datetime(2026, 5, 18, 4, 0, tzinfo=UTC)


def test_4_a_mute_is_a_setting_never_a_button_reaction():
    from beta.access import ACTIVITY_ACTIONS
    from beta.usage import as_setting
    assert "set_mute" in ACTIVITY_ACTIONS and "btn_mute" not in ACTIVITY_ACTIONS
    row = {"user_pk": 1, "action": "set_mute", "detail": "levels", "at": datetime(2026, 10, 14, tzinfo=UTC)}
    assert "button" not in as_setting(row)
    assert not as_setting(row)["action"].startswith(("btn_", "tab_"))   # the U2 reaction query reads btn_% and tab_%


def test_1_the_catchup_note_is_the_readers_own_outcome():
    """An hour pushed to Los Angeles at Kyiv's night: the Kyiv reader's /catchup says it waited for their
    night, never that it was sent; the LA reader's says nothing."""
    from beta.formatter import _hour_block
    from beta.i18n import t
    hour = {"decision_id": 7, "suppression_reason": None, "gate": {"values": {}}}
    s, e = CFG.quiet_hours_kyiv
    quiet = t("ru", "note_quiet", s=s, e=e)
    assert quiet not in _hour_block(CFG, hour, "ru", push_enabled=True)
    assert quiet in _hour_block(CFG, hour, "ru", push_enabled=True, own_reasons={7: "QUIET_HOURS"})
    assert quiet not in _hour_block(CFG, hour, "ru", push_enabled=True, own_reasons={7: None})


def _walk(hours, people, would=0):
    """Decide each hour and deliver it to each participant awake and under their own budget."""
    from beta.detector import in_quiet_hours, own_day_count
    cap, out = CFG["max_new_pushes_per_utc_day"], []
    for ts in hours:
        got = _decide(ts, list(people.values()), would)
        out.append(got[1:])
        if got[0]:
            would += 1
            for r in people.values():
                if not in_quiet_hours(CFG, ts, r["tz"]) and own_day_count(r["times"], ts, r["tz"]) < cap:
                    r["times"].append(ts)
    return out, would


def test_1_two_zones_in_one_utc_day_each_get_their_own_two_and_the_fuse_stays_silent(monkeypatch):
    """Kyiv and Los Angeles over 14.10 UTC: each gets up to their own 2 on their own date; the 4
    decisions never reach the fuse of 4."""
    from beta import hour_gate
    monkeypatch.setattr(hour_gate, "is_qualified", lambda hour: True)
    assert CFG["max_new_pushes_per_utc_day"] == 2 and CFG["push_decisions_fuse_per_utc_day"] == 4
    day = datetime(2026, 10, 14, tzinfo=UTC)
    people = {"kyiv": {"tz": None, "times": []}, "la": {"tz": "America/Los_Angeles", "times": []}}
    # 11:00, 13:00 Kyiv (LA asleep); 08:00, 10:00 LA (Kyiv spent); 14:00 LA (both spent)
    hours = [day + timedelta(hours=h) for h in (8, 10, 15, 17, 21)]
    out, would = _walk(hours, people)
    assert out == [("PUSH", None)] * 4 + [("SUPPRESSED", "DAILY_CAP")]
    assert would == 4 and [len(r["times"]) for r in people.values()] == [2, 2]


def test_1_the_fuse_stops_a_fifth_decision_of_the_utc_day_even_for_a_fresh_recipient(monkeypatch):
    from beta import hour_gate
    monkeypatch.setattr(hour_gate, "is_qualified", lambda hour: True)
    day = datetime(2026, 10, 14, tzinfo=UTC)
    people = {"kyiv": {"tz": None, "times": []}, "la": {"tz": "America/Los_Angeles", "times": []},
              "tokyo": {"tz": "Asia/Tokyo", "times": []}}
    # Tokyo gets 17:00 and 19:00 on its 14th; 23:00 UTC is 08:00 on its 15th, a fresh day with nothing yet,
    # while Kyiv sleeps and LA's 14th is spent
    _, would = _walk([day + timedelta(hours=h) for h in (8, 10, 15, 16)], people)
    assert would == 4 and len(people["tokyo"]["times"]) == 2
    from beta.detector import own_day_count
    assert own_day_count(people["tokyo"]["times"], day + timedelta(hours=23), "Asia/Tokyo") == 0
    late = day + timedelta(hours=23)
    assert _decide(late, list(people.values()), would)[1:] == ("SUPPRESSED", "DAILY_CAP")      # the fuse
    assert _decide(late, list(people.values()), would - 1)[1:] == ("PUSH", None)               # not the budget


def test_4_and_375_a_mute_right_after_an_alert_is_not_a_reaction_in_the_owner_breakdown():
    """#375 review, item 3: an alert at 06:00 and its one-tap mute at 06:02 — reacted 0, one mute."""
    from beta.access import MUTE_ACTIONS
    from beta.usage import as_setting, owner_breakdown
    at = datetime(2026, 10, 14, 6, 0, tzinfo=UTC)
    activity = [as_setting(r) for r in (
        {"user_pk": 1, "action": "alert_delivered", "detail": "level", "at": at},
        {"user_pk": 1, "action": MUTE_ACTIONS[0], "detail": "levels", "at": at + timedelta(minutes=2)})]
    out = owner_breakdown([{"user_pk": 1, "known_contact": False}], activity, [],
                          start=at - timedelta(hours=1), end=at + timedelta(hours=1))
    level = out["unknown"]["types"]["level"]
    assert level["delivered"] == 1 and level["reacted"] == 0 and level["mutes"] == 1
