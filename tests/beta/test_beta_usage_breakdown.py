"""Owner breakdown (backlog H6), pure: organic versus post-push pulls in the measurement
contract's 10-minute window, repeat /check, noise by delivery type, known and unknown apart,
and by trader type once one is recorded. Synthetic rows only."""
from datetime import datetime, timedelta, timezone

from beta.usage import build_usage_report, format_usage_report, owner_breakdown

NOW = datetime(2026, 6, 29, 12, tzinfo=timezone.utc)
START = NOW - timedelta(days=7)


def _at(day, hour, minute=0):
    return datetime(2026, 6, day, hour, minute, tzinfo=timezone.utc)


U1, U2, U3 = 1, 2, 3
USERS = [{"user_pk": U1, "known_contact": False}, {"user_pk": U2, "known_contact": True},
         {"user_pk": U3, "known_contact": False}]
ACTIVITY = [
    # u1: the 08:00 Kyiv brief, a tab within 3 min, /btc within 10 min, then /check on two Kyiv days
    (U1, "brief_delivered", None, _at(23, 5)),
    (U1, "tab_1h", None, _at(23, 5, 3)),
    (U1, "cmd_btc", None, _at(23, 5, 5)),
    (U1, "cmd_check", None, _at(23, 5, 30)),
    (U1, "cmd_check", None, _at(24, 10)),
    (U1, "btn_check", None, _at(24, 10, 1)),
    (U1, "btn_watch", None, _at(24, 10, 2)),
    # u1: a level alert, then the levels type turned off (a settings change is not a reaction)
    (U1, "alert_delivered", "level", _at(25, 10)),
    (U1, "cmd_push", "levels:off", _at(25, 10, 2)),
    # u1: an unusual-hour push voted useful within a minute
    (U1, "push_delivered", None, _at(26, 10)),
    (U1, "btn_useful", None, _at(26, 10, 1)),
    # u3: a personal alert just before the window still prompts the /alert just inside it
    (U3, "alert_delivered", "price", START - timedelta(minutes=2)),
    (U3, "cmd_alert", None, START + timedelta(minutes=3)),
    # u3: an unusual-hour push; /btc 11 minutes later is organic; voted noise
    (U3, "push_delivered", None, _at(27, 10)),
    (U3, "cmd_btc", None, _at(27, 10, 11)),
    # u2 (known): one organic /btc, then every push off
    (U2, "cmd_btc", None, _at(28, 9)),
    (U2, "cmd_push", "off", _at(28, 9, 5)),
]
ROWS = [{"user_pk": u, "action": a, "detail": d, "at": at} for u, a, d, at in ACTIVITY]
VOTES = [{"user_pk": U1, "kind": "hour", "vote": "USEFUL", "at": _at(26, 10, 1)},
         {"user_pk": U3, "kind": "hour", "vote": "NOISE", "at": _at(27, 10, 20)}]


def test_organic_and_post_push_pulls_use_the_ten_minute_window():
    out = owner_breakdown(USERS, ROWS, VOTES, start=START, end=NOW)
    unknown = out["unknown"]
    assert unknown["users"] == 2
    # post-push: u1 /btc 5 min after the brief, u3 /alert 5 min after its price alert
    assert unknown["pulls"] == {"organic": 3, "post_push": 2}
    # organic Kyiv days: u1 06-23 and 06-24, u3 06-27; u3's 06-22 had a post-push pull only
    assert unknown["organic_days"] == 3 and unknown["post_push_only_days"] == 1
    assert unknown["returning_users"] == 1
    assert unknown["check"] == {"pulls": 2, "users": 1, "repeat_users": 1, "btn_check": 1, "btn_watch": 1}
    assert out["known"]["pulls"] == {"organic": 1, "post_push": 0} and out["known"]["users"] == 1
    assert out["known"]["push_off_now"] == 1 and unknown["push_off_now"] == 0
    assert out["trader_types"] is None


def test_noise_by_type_counts_reactions_votes_and_mutes():
    types = owner_breakdown(USERS, ROWS, VOTES, start=START, end=NOW)["unknown"]["types"]
    shown = ("delivered", "reacted", "useful", "noise", "mutes", "muted_now")
    pick = lambda d: {k: d[k] for k in shown if k in d}  # noqa: E731
    assert pick(types["brief"]) == {"delivered": 1, "reacted": 1, "useful": 0, "noise": 0, "mutes": 0, "muted_now": 0}
    assert pick(types["level"]) == {"delivered": 1, "reacted": 0, "useful": 0, "noise": 0, "mutes": 1, "muted_now": 1}
    assert pick(types["hour"]) == {"delivered": 2, "reacted": 1, "useful": 1, "noise": 1, "mutes": 0, "muted_now": 0}
    # the personal alert arrived before the window; it has no mute (the participant asked for it)
    assert pick(types["price"]) == {"delivered": 0, "reacted": 0, "useful": 0, "noise": 0}
    # F4 is computed once, over all participants; the subgroups carry none
    assert all("review" not in t for t in types.values())
    assert all(t["review"] == [] for t in owner_breakdown(USERS, ROWS, VOTES, start=START, end=NOW)["all"]["types"].values())
    # turning the type back on clears the current state but keeps the mute in the window
    back = ROWS + [{"user_pk": U1, "action": "cmd_push", "detail": "levels:on", "at": _at(28, 12)}]
    level = owner_breakdown(USERS, back, VOTES, start=START, end=NOW)["unknown"]["types"]["level"]
    assert level["mutes"] == 1 and level["muted_now"] == 0


def test_the_window_edge_is_inclusive_like_the_contract_query():
    edge = [{"user_pk": U1, "action": "push_delivered", "detail": None, "at": _at(26, 10)},
            {"user_pk": U1, "action": "cmd_risk", "detail": None, "at": _at(26, 10, 10)},
            {"user_pk": U1, "action": "cmd_levels", "detail": None, "at": _at(26, 10, 10) + timedelta(seconds=1)}]
    out = owner_breakdown(USERS, edge, [], start=START, end=NOW)["unknown"]
    assert out["pulls"] == {"organic": 1, "post_push": 1}


def test_split_by_trader_type_once_onboarding_records_it():
    typed = [dict(USERS[0], trader_type="swing"), dict(USERS[1], trader_type="scalp"), dict(USERS[2])]
    out = owner_breakdown(typed, ROWS, VOTES, start=START, end=NOW)["trader_types"]
    assert sorted(out) == ["none", "scalp", "swing"]
    assert out["swing"]["check"]["repeat_users"] == 1 and out["none"]["pulls"]["post_push"] == 1


def test_the_report_text_shows_the_breakdown_without_ids():
    owner = 900000000001
    users = [{"user_pk": 9, "telegram_user_id": owner, "status": "ACTIVE", "lang": "ru",
              "joined_at": _at(1, 0), "invite_code": None, "known_contact": False}]
    users += [{"user_pk": u["user_pk"], "telegram_user_id": 900000000100 + u["user_pk"], "status": "ACTIVE",
               "lang": "ru", "joined_at": _at(20, 0), "invite_code": None, "known_contact": u["known_contact"]}
              for u in USERS]
    owner_rows = [{"user_pk": 9, "action": "cmd_check", "detail": None, "at": _at(28, 10)}]
    facts = {"users": users, "activity": ROWS + owner_rows, "votes": VOTES, "invites": [], "deletions": [],
             "rejected_hashes": [], "rejected_counts": [], "waitlist_size": 0}
    report = build_usage_report(facts, now=NOW, owner_user_id=owner)
    last = report["last_7_days"]["owner_breakdown"]
    assert last["unknown"]["check"]["pulls"] == 2                       # the owner's /check is not counted
    text = format_usage_report(report)
    assert "owner breakdown (10-min window, all pulls; operational, not U1-U5)" in text
    assert ("  unknown (2 users): pulls organic 3, post-push 2 · organic days 3, post-push-only days 1"
            " · returning 1") in text
    assert "    /check 2 by 1, repeat 1 · check button 1 · watch button 1 · push off now 0" in text
    assert "    level: sent 1, reacted 0, useful 0, noise 0, muted 1 (now 1)" in text
    assert "    hour: sent 2, reacted 1, useful 1, noise 1, muted 0 (now 0)" in text
    assert "  trader type: not recorded" in text
    for raw in (owner, 900000000101, 900000000102, 900000000103):
        assert str(raw) not in text


def test_the_bisect_breakdown_equals_a_plain_scan():
    """Review #334 item 13: sorted lists and bisect instead of a scan per row; the counts are unchanged."""
    import random

    from beta.usage import DELIVERIES, PULL_ACTIONS, REACTION_WINDOW, _aware, _group_block, _type_of
    rnd = random.Random(7)
    actions = list(PULL_ACTIONS) + ["tab_1h", "btn_levels", "btn_useful", "cmd_push", "push_delivered",
                                    "brief_delivered", "weekly_delivered", "alert_delivered"]
    rows = []
    for _ in range(600):
        a = rnd.choice(actions)
        rows.append({"user_pk": rnd.choice((U1, U2, U3)), "action": a,
                     "detail": rnd.choice(("level", "event", "move", "price")) if a == "alert_delivered" else None,
                     "at": START + timedelta(minutes=rnd.randrange(7 * 24 * 60))})
    got = _group_block({U1, U2, U3}, rows, [], start=START, end=NOW)

    def scan_follows(at, starts):
        return any(timedelta(0) <= at - s <= REACTION_WINDOW for s in starts)
    organic = post = 0
    for r in rows:
        if r["action"] in PULL_ACTIONS:
            sent = [_aware(x["at"]) for x in rows if x["user_pk"] == r["user_pk"] and x["action"] in DELIVERIES]
            post += scan_follows(_aware(r["at"]), sent)
            organic += not scan_follows(_aware(r["at"]), sent)
    assert got["pulls"] == {"organic": organic, "post_push": post}
    for name, block in got["types"].items():
        sent = [r for r in rows if _type_of(r) == name]
        reacted = sum(any(x["user_pk"] == r["user_pk"] and x["action"].startswith(("tab_", "btn_"))
                          and timedelta(0) <= x["at"] - r["at"] <= REACTION_WINDOW for x in rows) for r in sent)
        assert (block["delivered"], block["reacted"]) == (len(sent), reacted), name
