"""Implicit push metrics (backlog F5), pure: per delivered message the recipients who pressed a button, did
anything, or muted that type within the contract's 10 minutes; time to disable per type; every delivery
prompts an open within 10 minutes. Synthetic rows only."""
from datetime import datetime, timedelta, timezone

from beta.usage import PROMPT_WINDOW, REACTION_WINDOW, build_usage_report, format_usage_report, push_metrics

UTC = timezone.utc
T = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
A, B, C, D = 1, 2, 3, 4


def _act(pk, action, at, detail=None):
    return {"user_pk": pk, "action": action, "detail": detail, "at": at}


def _sent(pk, kind, at, *, alert_kind=None, ref=1):
    return {"kind": kind, "alert_kind": alert_kind, "decision_id": ref if kind == "push" else None,
            "alert_pk": ref if kind == "alert" else None, "brief_date": at.date() if kind == "brief" else None,
            "weekly_pk": ref if kind == "weekly" else None, "user_pk": pk, "at": at}


def _fixture():
    deliveries = [_sent(pk, "alert", T + timedelta(seconds=pk), alert_kind="level", ref=10) for pk in (A, B, C, D)]
    deliveries += [_sent(C, "alert", T - timedelta(days=2), alert_kind="level", ref=9),     # C's first level
                   _sent(A, "alert", T + timedelta(hours=1), alert_kind="event", ref=11),
                   _sent(B, "push", T + timedelta(hours=2), ref=5),
                   _sent(A, "alert", T + timedelta(hours=3), alert_kind="price", ref=12)]
    activity = [_act(A, "btn_levels", T + timedelta(minutes=3)),                  # button and action
                _act(B, "cmd_btc", T + timedelta(minutes=9)),                     # action only
                _act(C, "cmd_push", T + timedelta(minutes=5), "levels:off"),     # muted that type
                _act(A, "tab_1h", T + timedelta(hours=1, minutes=11)),            # outside the window
                _act(B, "cmd_push", T + timedelta(hours=2, minutes=1), "off")]    # /push off mutes the hour push
    return activity, deliveries


def test_each_message_counts_buttons_actions_and_mutes_within_ten_minutes():
    assert REACTION_WINDOW == PROMPT_WINDOW == timedelta(minutes=10)
    activity, deliveries = _fixture()
    m = push_metrics(activity, deliveries, start=T - timedelta(hours=1), end=T + timedelta(days=1))
    level = next(p for p in m["pushes"] if p["type"] == "level")
    assert {k: level[k] for k in ("delivered", "button", "action", "muted")} == \
        {"delivered": 4, "button": 1, "action": 3, "muted": 1}
    assert level["at"] == T + timedelta(seconds=A)                           # the first recipient's delivery
    event = next(p for p in m["pushes"] if p["type"] == "event")
    assert (event["button"], event["action"]) == (0, 0)                    # 11 minutes later is not a reaction
    hour = next(p for p in m["pushes"] if p["type"] == "hour")
    assert hour["muted"] == 1 and hour["action"] == 1
    assert next(p for p in m["pushes"] if p["type"] == "price")["muted"] == 0   # a personal alert has no mute
    assert [p["type"] for p in m["pushes"]] == ["price", "hour", "event", "level"]    # newest first
    assert m["types"]["level"] == {"messages": 1, "delivered": 4, "button": 1, "action": 3, "muted": 1}
    # C switched levels off 48 h 05 min after their first level message (2 received); B's `/push off`
    # 2 h 01 min after their only level message switched levels off too (1 received)
    lv = m["disable"]["level"]
    c_h, b_h = (48 * 3600 + 5 * 60) / 3600, (2 * 3600 + 60 - 2) / 3600
    assert lv["n"] == 2 and abs(lv["median_h"] - (c_h + b_h) / 2) < 1e-9 and lv["received_median"] == 1.5
    assert m["disable"]["hour"] == {"n": 1, "median_h": 1 / 60, "received_median": 1}


def test_every_delivery_prompts_an_open_within_ten_minutes():
    users = [{"user_pk": A, "telegram_user_id": 11, "status": "ACTIVE", "lang": "ru", "joined_at": T - timedelta(days=1),
              "invite_code": None, "known_contact": False}]
    activity = [_act(A, "brief_delivered", T),
                _act(A, "cmd_btc", T + timedelta(minutes=5)),                    # after the brief: prompted
                _act(A, "cmd_btc", T + timedelta(minutes=15))]                   # unprompted (30 min used to say no)
    facts = {"users": users, "activity": activity, "votes": [], "invites": [], "deletions": [], "rejected_hashes": [],
             "rejected_counts": [], "waitlist_size": 0, "deliveries": [_sent(A, "brief", T)]}
    rep = build_usage_report(facts, now=T + timedelta(hours=1), owner_user_id=None)
    assert (rep["last_7_days"]["unprompted_btc"], rep["last_7_days"]["post_push_btc"]) == (1, 1)
    text = format_usage_report(rep)
    assert "pushes, last 7 days (10-min window: button / any action / muted that type)" in text
    assert "brief: 1 messages, sent 1 · button 0 · action 1 · muted 0" in text


def test_the_owner_text_lists_messages_and_time_to_disable():
    activity, deliveries = _fixture()
    users = [{"user_pk": pk, "telegram_user_id": 100 + pk, "status": "ACTIVE", "lang": "ru",
              "joined_at": T - timedelta(days=3), "invite_code": None, "known_contact": False} for pk in (A, B, C, D)]
    facts = {"users": users, "activity": activity, "votes": [], "invites": [], "deletions": [], "rejected_hashes": [],
             "rejected_counts": [], "waitlist_size": 0, "deliveries": deliveries}
    text = format_usage_report(build_usage_report(facts, now=T + timedelta(hours=4), owner_user_id=None))
    assert "level 10-06 09:00 UTC: sent 4 · button 1 · action 3 · muted 1" in text
    assert "time to disable level: N=2 median 25 h after the first (median 1.5 received)" in text
    assert "time to disable hour: N=1 median 0 h after the first (median 1 received)" in text
