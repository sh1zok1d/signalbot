"""The external review of #375 (package 5): the owner review flag over all participants, a mute is
never a reaction, an honest corridor word, the delay median over distinct messages, the event delay on a
line of its own, the level the price stands at, the flag's denominator, the vote button parser."""
from datetime import datetime, timedelta, timezone

from beta import decision_format as df

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 41, tzinfo=UTC)


def _votes(n_users, per_user, vote="NOISE", kind="level"):
    return [{"user_pk": u, "kind": kind, "vote": vote, "at": T - timedelta(hours=1)}
            for u in range(1, n_users + 1) for _ in range(per_user)]


def test_1_the_review_flag_is_raised_over_everyone_and_printed_once():
    """The reviewer's script: 9 participants (5 unknown, 4 known), 36 «Шум» on level alerts. The owner's
    rule holds over everyone (36 votes from 9 people, all noise); neither subgroup alone reaches 8 people."""
    from beta.usage import _breakdown, owner_breakdown
    users = [{"user_pk": u, "known_contact": u > 5} for u in range(1, 10)]
    out = owner_breakdown(users, [], _votes(9, 4), start=T - timedelta(days=7), end=T)
    assert out["all"]["types"]["level"]["review"] == ["noise 36/36 from 9 people"]
    text = _breakdown("last 7 days", out)
    assert sum("⚑ review level" in line for line in text) == 1


def test_1_mass_disables_are_flagged_over_everyone_with_global_off_and_only_among_recipients():
    from beta.usage import owner_breakdown
    users = [{"user_pk": u, "known_contact": u > 2} for u in range(1, 9)]
    sent = [{"user_pk": u, "action": "alert_delivered", "detail": "level", "at": T - timedelta(hours=2)}
            for u in range(1, 9)]
    offs = [{"user_pk": 1, "action": "cmd_push", "detail": "levels:off", "at": T - timedelta(hours=1)},
            {"user_pk": 3, "action": "cmd_push", "detail": "off", "at": T - timedelta(hours=1)},   # all pushes off
            {"user_pk": 5, "action": "cmd_push", "detail": "levels:off", "at": T - timedelta(hours=1)}]
    out = owner_breakdown(users, sent + offs, [], start=T - timedelta(days=7), end=T)
    assert out["all"]["types"]["level"]["review"] == ["disabled by 3 of 8 who received it"]
    # someone who never received the type is not one of «those who received it»
    stranger = [{"user_pk": 9, "action": "cmd_push", "detail": "levels:off", "at": T - timedelta(hours=1)}]
    out = owner_breakdown(users + [{"user_pk": 9}], sent + offs[:2] + stranger, [], start=T - timedelta(days=7), end=T)
    assert out["all"]["types"]["level"]["review"] == []


def test_4_the_move_alerts_corridor_is_a_model_never_usually():
    move = {"at": T.isoformat(), "start": (T - timedelta(minutes=15)).isoformat(), "open": 63000.0, "close": 62000.0,
            "move_pct": -1.59, "ratio": 3.1, "every_days": 3.0,
            "corridor_1h": {"lower": 61700.0, "upper": 62300.0, "half_width_pct": 0.5}, "near": [], "event_zone": {}}
    for lang, word in (("ru", "обычно"), ("en", "usually")):
        line = [x for x in df.format_alert("move", move, lang).splitlines() if "61" in x and "62 300" in x
                or "61,700" in x]
        assert line and word not in line[0].lower()


def _lat(lag, p50=None, n=0, messages=0):
    return {"class": "level", "source": "candle_close", "source_at": (T - timedelta(seconds=lag)).isoformat(),
            "lag_s": lag, "p50_s": p50, "p95_s": None, "n": n, "messages": messages, "window_days": 7}


def test_5_the_usual_delay_needs_twenty_messages_not_twenty_deliveries_and_prints_its_n():
    from beta.latency import summarize
    sent = T + timedelta(seconds=40)
    rows = [{"kind": "alert", "alert_kind": "level", "state": "SENT", "decision_ts": T, "finished_at": sent,
             "source_at": (T - timedelta(seconds=5)).isoformat(), "alert_pk": 7, "decision_id": None,
             "view_pk": None, "weekly_pk": None} for _ in range(20)]          # one alert to 20 participants
    s = summarize(rows)["level"]
    assert s["n"] == 20 and s["messages"] == 1
    assert df.delay_text(_lat(40, p50=45, n=20, messages=1), "ru") == " · задержка 40 с"
    assert df.delay_text(_lat(40, p50=45, n=60, messages=20), "ru") == " · задержка 40 с (обычно 45 с, N=20)"


def test_the_event_warning_names_its_own_delay_apart_from_the_release_time():
    payload = {"at": T.isoformat(), "event_kind": "CPI", "event_at": (T + timedelta(minutes=30)).isoformat(),
               "minutes": 30, "price": 61000.0, "stats": None, "corridor_1h": None,
               "latency": _lat(40)}
    lines = [x for x in df.format_alert("event", payload, "ru").splitlines() if x.strip()]
    assert "задержка" not in lines[1]
    assert "Задержка этого сообщения: 40 с" in lines


def test_the_push_names_the_level_the_price_stands_at():
    z = lambda p, k, d: {"low": p, "high": p, "edge": p, "distance_pct": d, "kinds": [k],  # noqa: E731
                         "members": [{"kind": k, "price": p}]}
    levels = {"above": [z(62950.0, "PDH", 0.75)], "below": [z(61900.0, "ASIA_L", -0.93)], "at": z(62400.0, "PWL", 0.0)}
    line = df.near_levels_line(levels, "ru")
    assert line.index("↑") < line.index("цена у 62 400") < line.index("↓")


def test_the_vote_parser_takes_ascii_digits_only():
    from beta.formatter import parse_vote
    assert parse_vote("v:level:12:u") == ("level", 12, "USEFUL")
    for bad in ("v:level:²:u", "v:level:１２:u", "v:level:٣:n"):
        assert parse_vote(bad) is None


def test_the_simulator_records_votes_like_the_store():
    import asyncio
    from tools.beta_user_sim.sandbox import SandboxConn
    store = SandboxConn.__new__(SandboxConn)
    store._s = type("S", (), {"votes": {}})()

    async def body():
        assert await store.upsert_feedback(user_pk=1, episode_pk=2, vote="USEFUL") is True
        assert await store.upsert_feedback(user_pk=1, episode_pk=2, vote="USEFUL") is False
        assert await store.upsert_message_vote(user_pk=1, kind="brief", ref=3, vote="NOISE") is True
        assert await store.upsert_message_vote(user_pk=1, kind="brief", ref=3, vote="NOISE") is False
    asyncio.run(body())
