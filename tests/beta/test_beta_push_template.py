"""Push template, votes on every type and the owner review flag (backlog F1, F4, F6): pure parts."""
import re
from datetime import datetime, timedelta, timezone

from beta import decision_format as df
from beta.formatter import parse_vote, vote_row
from beta.usage import review_flag

UTC = timezone.utc
T = datetime(2026, 10, 14, 6, 41, tzinfo=UTC)               # 09:41 Kyiv


def plain(html):
    return re.sub(r"<[^>]+>", "", html)


def _lat(lag, p50=None, n=0, cls="level"):
    return {"class": cls, "source": "candle_close", "source_at": (T - timedelta(seconds=lag)).isoformat(),
            "lag_s": lag, "p50_s": p50, "p95_s": None, "n": n, "window_days": 7}


def test_the_delay_is_the_messages_own_with_the_class_median_once_measured():
    assert df.delay_text(None, "ru") == ""
    assert df.delay_text(_lat(40), "ru") == " · задержка 40 с"
    assert df.delay_text(_lat(40, p50=35, n=19), "ru") == " · задержка 40 с"            # N below 20: no median
    assert df.delay_text(_lat(125, p50=35, n=20), "en") == " · delay 2 min 5 s (usually 35 s)"
    assert df.delay_text(_lat(3720, p50=60, n=50), "ru") == " · задержка 1 ч 2 мин (обычно 1 мин)"


def test_every_alert_carries_its_delay_on_the_time_line_never_a_line_of_its_own():
    payload = {"at": T.isoformat(), "level_kind": "PDH", "level": 62950.0, "side": 1, "period": "day",
               "price": 62960.0, "price_ts": (T + timedelta(minutes=1)).isoformat(), "history": None, "next": None,
               "corridor_4h": None, "event_zone": {}}
    before = df.format_alert("level", payload, "ru").splitlines()
    after = df.format_alert("level", {**payload, "latency": _lat(40, p50=35, n=30)}, "ru").splitlines()
    assert len(after) == len(before) and after[1] == before[1] + " · задержка 40 с (обычно 35 с)"
    move = {"at": T.isoformat(), "start": (T - timedelta(minutes=15)).isoformat(), "open": 63000.0, "close": 62000.0,
            "move_pct": -1.59, "ratio": 3.1, "every_days": 3.0,
            "corridor_1h": {"lower": 61700.0, "upper": 62300.0, "half_width_pct": 0.5}, "near": [], "event_zone": {}}
    text = plain(df.format_alert("move", {**move, "latency": _lat(70, cls="move")}, "ru"))
    assert "09:26–09:41 (Киев) · 63 000 → 62 000 (Binance) · задержка 1 мин 10 с" in text
    assert "Дальше обычно в коридоре 1ч: 61 700–62 300 (±0,5%)" in text                 # «что обычно дальше» (F1)


def test_the_unusual_hour_push_has_its_delay_and_the_nearest_levels():
    from types import SimpleNamespace
    from beta.formatter import format_push
    ep = SimpleNamespace(triggered_at=T, public_id="EV-1", event_type="X")
    levels = {"above": [{"low": 62950.0, "high": 62950.0, "edge": 62950.0, "distance_pct": 0.75, "kinds": ["PDH"],
                         "members": [{"kind": "PDH", "price": 62950.0}]}],
              "below": [{"low": 61900.0, "high": 61900.0, "edge": 61900.0, "distance_pct": -0.93, "kinds": ["ASIA_L"],
                         "members": [{"kind": "ASIA_L", "price": 61900.0}]}]}
    text = plain(format_push(ep, lang="ru", latency=_lat(45, cls="push"), levels=levels))
    lines = [x for x in text.splitlines() if x.strip()]
    assert lines[1] == "08:41–09:41 (Киев) · задержка 45 с"
    assert "Рядом: ↑ 62 950 максимум вчера (+0,75%) · ↓ 61 900 минимум Азии (−0,93%)" in lines
    assert len(lines) <= 8


def test_useful_and_noise_on_every_message_type():
    assert vote_row("level", 12, "ru") == [("Полезно", "v:level:12:u"), ("Шум", "v:level:12:n")]
    assert parse_vote("v:brief:7:n") == ("brief", 7, "NOISE") and parse_vote("v:weekly:3:u") == ("weekly", 3, "USEFUL")
    for bad in ("v:hour:1:u", "v:level:0:u", "v:level:x:u", "v:level:1:y", "v:level:1", "u:EV-1"):
        assert parse_vote(bad) is None, bad
    from beta.market_alerts import alert_buttons
    for kind in ("level", "event", "move", "price", "approach"):
        rows = alert_buttons(kind, {}, "en", alert_pk=99)
        assert ("Useful", f"v:{kind}:99:u") in [b for row in rows for b in row]


def test_the_owner_review_flag_is_raised_by_noise_or_mass_disables_only():
    base = {"useful": 10, "noise": 21, "voters": 8}
    assert review_flag(base, recipients=20) == ["noise 21/31 from 8 people"]
    assert review_flag({**base, "voters": 7}, recipients=20) == []                       # too few people
    assert review_flag({"useful": 14, "noise": 15, "voters": 9}, recipients=20) == []    # 29 votes
    assert review_flag({"useful": 16, "noise": 15, "voters": 9}, recipients=20) == []    # noise not above half
    assert review_flag({"useful": 0, "noise": 0, "voters": 0, "muters": 3}, recipients=12) == [
        "disabled by 3 of 12 who received it"]
    assert review_flag({"useful": 0, "noise": 0, "voters": 0, "muters": 3}, recipients=13) == []   # under 25 %
    assert review_flag({"useful": 0, "noise": 0, "voters": 0, "muters": 2}, recipients=4) == []    # under 3 people
