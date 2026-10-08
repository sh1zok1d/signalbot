"""Event-zone safety fallback (BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1 §9).

For horizon H and a scheduled CPI / FOMC release r, no numerical corridor — and nothing derived
from it (touch chances, /risk figures, alert corridor lines, tracked forecasts) — is shown while
now ∈ [r − H, r + 60 min). Outside every zone the generic corridor is unchanged. Synthetic data
and calendar entries only; no protected or prospective outcome is read."""
import re
from datetime import datetime, timedelta, timezone

import pytest

from beta import decision_format as df
from beta.decision import event_zones
from beta.i18n import assert_descriptive
from test_beta_v2_format import block

UTC = timezone.utc
R = datetime(2026, 10, 14, 12, 30, tzinfo=UTC)          # a CPI release (12:30 UTC)
CAL = {"events": [{"kind": "CPI", "at": R},
                  {"kind": "EXPIRY_WEEKLY", "at": R + timedelta(days=2)}]}   # expiries never make a zone
H = {"1h": timedelta(hours=1), "4h": timedelta(hours=4), "24h": timedelta(hours=24)}
ZONE_RU = "числовую оценку не показываем"
ZONE_EN = "no numerical estimate"


def ms(dt):
    return int(dt.timestamp() * 1000)


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace("&lt;", "<").replace("&gt;", ">")


def html_ok(text):
    body = re.sub(r"</?(b|i)>", "", text)
    body = re.sub(r"&(lt|gt|amp|quot|#\d+);", "", body)
    return not any(ch in body for ch in "<>&")


# ---- the zone itself: [r − H, r + 60 min), per horizon ------------------------------------------
POINTS = [  # (label, offset from the zone start or from the release, inside?)
    ("1 min before the zone", lambda h: R - H[h] - timedelta(minutes=1), False),
    ("zone start", lambda h: R - H[h], True),
    ("just before the release", lambda h: R - timedelta(minutes=1), True),
    ("the release", lambda h: R, True),
    ("+5m", lambda h: R + timedelta(minutes=5), True),
    ("+55m", lambda h: R + timedelta(minutes=55), True),
    ("+60m exactly", lambda h: R + timedelta(minutes=60), False),
    ("after +60m", lambda h: R + timedelta(minutes=61), False),
]


@pytest.mark.parametrize("h", ["1h", "4h", "24h"])
@pytest.mark.parametrize("label,when,inside", POINTS, ids=[p[0] for p in POINTS])
def test_zone_boundaries(h, label, when, inside):
    zones = event_zones(ms(when(h)), CAL)
    assert (h in zones) is inside, label
    if inside:
        assert zones[h] == [{"kind": "CPI", "at": R.isoformat()}]


def test_zone_kinds_and_nesting():
    # 3h before the release: inside the 4h and 24h zones only
    assert set(event_zones(ms(R - timedelta(hours=3)), CAL)) == {"4h", "24h"}
    fomc = {"events": [{"kind": "FOMC", "at": R}]}
    assert set(event_zones(ms(R + timedelta(minutes=30)), fomc)) == {"1h", "4h", "24h"}
    assert event_zones(ms(R + timedelta(days=2)), CAL) == {}            # the expiry makes no zone


# ---- formatting: the block as decision._build leaves it ----------------------------------------
def zoned(hs, base=None):
    """block() with the horizons in `hs` removed at the source, as decision._build does."""
    b = base or block()
    zones = {h: [{"kind": "CPI", "at": R.isoformat()}] for h in hs}
    b["corridor"]["horizons"] = {h: x for h, x in b["corridor"]["horizons"].items() if h not in zones}
    for side in ("above", "below"):
        for z in b["levels"][side]:
            z["touch"] = {h: p for h, p in z["touch"].items() if h not in zones}
    b["event_zone"] = zones
    return b


MODEL = {"horizons": {h: {"q_one": [0.01 * k for k in range(1, 100)] + [1.2, 1.5]} for h in ("1h", "4h", "24h")},
         "calibration": {}}
NUM = r"(<|>)?\d"


def no_numbers_for(text, h, lang):
    """No corridor or probability figure for horizon h on any surface."""
    hz = {"ru": {"1h": "1ч", "4h": "4ч", "24h": "24ч"}, "en": {"1h": "1h", "4h": "4h", "24h": "24h"}}[lang][h]
    pats = [rf"(^|\s){hz}: {NUM}",                                 # corridor part / table cell
            rf"Коридор {hz}( сейчас)?:" if lang == "ru" else rf"{hz} corridor( now)?:",
            rf"за {hz} {NUM}" if lang == "ru" else rf"within {hz} {NUM}",
            rf"за {hz} — в" if lang == "ru" else rf"within {hz} — {NUM}",
            rf"(^|·\s){hz} {NUM}"]                                  # /risk table cell
    return not any(re.search(p, text, flags=re.M) for p in pats)


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize("hs", [{"24h"}, {"4h", "24h"}, {"1h", "4h", "24h"}])
def test_every_surface_withholds_the_zoned_horizons(lang, hs):
    b = zoned(hs)
    note = ZONE_RU if lang == "ru" else ZONE_EN
    texts = {
        "brief": "\n".join(df.brief_lines({"decision": b}, lang)),
        "btc": "\n".join(df.btc_lines({"decision": b}, lang)),
        "levels": df.format_levels(b, lang, now=R),
        "risk_stop": df.format_risk(b, MODEL, lang, stop_pct=0.5),
        "risk_table": df.format_risk(b, MODEL, lang, stop_pct=None),
    }
    for name, html in texts.items():
        assert html_ok(html), name
        assert_descriptive(html, lang)
        text = plain(html)
        for h in hs:
            assert no_numbers_for(text, h, lang), (name, h, text)
        assert "4 из 5" not in text and "4 of 5" not in text, name
    # the note says why, names the release and its time, on every surface that would show a number
    assert note in plain(texts["brief"]) and "CPI" in plain(texts["brief"]) and "15:30" in plain(texts["brief"])
    assert note in plain(texts["levels"]) and note in plain(texts["risk_stop"]) and note in plain(texts["risk_table"])
    if "4h" in hs:
        assert note in plain(texts["btc"])
    # horizons outside the zone keep their generic numbers
    risk = plain(texts["risk_stop"])
    for h in {"1h", "4h", "24h"} - hs:
        hz = {"ru": {"1h": "1ч", "4h": "4ч", "24h": "24ч"}, "en": {"1h": "1h", "4h": "4h", "24h": "24h"}}[lang][h]
        assert re.search(rf"за {hz} — в {NUM}" if lang == "ru" else rf"within {hz} — {NUM}", risk), h


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_outside_every_zone_the_generic_corridor_is_unchanged(lang):
    b = block()
    b["event_zone"] = {}
    b["corridor"]["holdout"] = {"4h": {"coverage_realized": 0.81, "n_days": 365},
                                "24h": {"coverage_realized": 0.8, "n_days": 365}}
    brief = plain("\n".join(df.brief_lines({"decision": b}, lang)))
    assert ("(расчёт — 80%)" in brief) if lang == "ru" else ("(designed for 80%)" in brief)   # the coverage claim
    assert re.search(r"24(ч|h) 60[ ,]230–64[ ,]730", brief)
    assert ZONE_RU not in brief and ZONE_EN not in brief
    assert "Коридор: 1ч 62 043–62 917 · 4ч 61 605–63 355 · 24ч 60 230–64 730" in plain(
        "\n".join(df.btc_lines({"decision": b}, "ru")))


# ---- alerts: even a payload that still carries a corridor shows none inside its zone -----------
CORR = {"lower": 61000.0, "upper": 62000.0, "half_width_pct": 0.8}


def payload(kind, hs):
    zones = {h: [{"kind": "CPI", "at": R.isoformat()}] for h in hs}
    base = {"at": (R + timedelta(minutes=5)).isoformat(), "price": 61500.0, "event_zone": zones}
    if kind == "level":
        return {**base, "level_kind": "PDH", "level": 61500.0, "side": 1, "period": "day", "history": None,
                "corridor_4h": CORR, "next": {"low": 62500.0, "high": 62500.0, "edge": 62500.0, "distance_pct": 1.6,
                                              "kinds": ["ROUND"], "members": [{"kind": "ROUND", "price": 62500.0}],
                                              "touch": {"24h": 0.42}}}
    if kind == "event":     # a legacy payload with a corridor and event-size statistics
        return {**base, "at": (R - timedelta(minutes=30)).isoformat(), "event_kind": "CPI", "event_at": R.isoformat(),
                "minutes": 30, "corridor_1h": CORR,
                "stats": {"hour": {"n": 61, "median_ratio": 3.2}, "day": {"n": 61, "median_ratio": 1.5}}}
    if kind == "move":
        return {**base, "start": (R - timedelta(minutes=10)).isoformat(), "open": 62000.0, "close": 61500.0,
                "move_pct": -0.8, "ratio": 3.0, "every_days": 3.0, "corridor_1h": CORR, "near": []}
    return {**base, "level": 61500.0, "late": False, "corridor_4h": CORR}


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize("kind,hs,gone", [
    ("level", {"4h", "24h"}, ["61 000–62 000", "61,000–62,000", "42%"]),
    ("event", {"1h", "4h", "24h"}, ["61 000–62 000", "61,000–62,000", "×", "3,2", "3.2"]),
    ("move", {"1h", "4h", "24h"}, ["61 000–62 000", "61,000–62,000"]),
    ("price", {"4h", "24h"}, ["61 000–62 000", "61,000–62,000"]),
])
def test_alerts_withhold_corridor_lines_inside_the_zone(lang, kind, hs, gone):
    html = df.format_alert(kind, payload(kind, hs), lang)
    assert html_ok(html)
    text = plain(html)
    for g in gone:
        assert g not in text, (kind, g, text)
    assert "с учётом события" not in text and "with the event" not in text
    assert "4 из 5" not in text and "4 of 5" not in text
    if kind == "event":
        assert ("Числовой коридор на это время не показываем" in text) if lang == "ru" \
            else ("No numerical corridor for this time" in text)
        assert "CPI" in text and "15:30" in text                       # the release and its exact time
    else:
        assert (ZONE_RU if lang == "ru" else ZONE_EN) in text
    assert len([x for x in text.splitlines() if x.strip()]) <= df.ALERT_MAX_LINES


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_alerts_outside_the_zone_keep_their_corridor(lang):
    for kind in ("level", "move", "price"):
        text = plain(df.format_alert(kind, payload(kind, set()), lang))
        assert ("61 000–62 000" in text) or ("61,000–62,000" in text), kind
        assert ZONE_RU not in text and ZONE_EN not in text


# ---- event-facing surfaces: name, exact time and the neutral warning — nothing else -----------
# No size multiplier, no "4 of 5", no 80%, no probability, no direction: none of them is
# supported for the release window (design record §9). Unrelated generic percentages elsewhere stay.
WARN = {"ru": "вокруг публикации обычная калибровка коридора не применяется.",
        "en": "around the release, the usual corridor calibration does not apply."}
EVENT_FORBIDDEN = re.compile(r"×|\d\s*раз|\btimes\b|4 из 5|4 of 5|4 out of 5|\d\s*%|вероятн|probab|шанс|chance|"
                             r"выше|ниже|higher|lower|рост|паден|\bup\b|\bdown\b|Проверено|Tested|Checked|случа|cases",
                             re.I)
STATS = {"hour": {"n": 61, "median_ratio": 3.2}, "day": {"n": 61, "median_ratio": 1.5}}
EVENTS = [{"kind": "CPI", "at": "2026-10-14T12:30:00+00:00", "stats": STATS},
          {"kind": "FOMC", "at": "2026-10-28T18:00:00+00:00", "stats": STATS},
          {"kind": "EXPIRY_MONTHLY", "at": "2026-10-30T08:00:00+00:00", "stats": STATS}]
LINE = {"ru": r"^(Пн|Вт|Ср|Чт|Пт|Сб|Вс) \d\d\.\d\d \d\d:\d\d — [^:]+$",
        "en": r"^(Mon|Tue|Wed|Thu|Fri|Sat|Sun) \d\d\.\d\d \d\d:\d\d — [^:]+$"}


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_events_card_is_a_plain_calendar(lang):
    text = plain(df.format_events(EVENTS, lang))
    lines = text.splitlines()
    assert all(re.match(LINE[lang], x) for x in lines[1:4]), lines
    cpi, fomc = (("CPI США (инфляция)", "решение ФРС (FOMC)") if lang == "ru"
                 else ("US CPI (inflation)", "Fed decision (FOMC)"))
    assert lines[4:] == [f"{cpi}, {fomc}: {WARN[lang]}"]
    body = "\n".join(re.sub(r"\d\d\.\d\d \d\d:\d\d", "", x) for x in lines)
    assert not EVENT_FORBIDDEN.search(body), body
    # expiries alone make no event zone: no warning
    only_expiry = plain(df.format_events(EVENTS[2:], lang))
    assert WARN[lang] not in only_expiry and "×" not in only_expiry


@pytest.mark.parametrize("lang", ["ru", "en"])
def test_brief_today_shows_name_time_and_the_warning_only(lang):
    b = block()
    b["events"] = [{**EVENTS[0], "at": "2026-10-14T12:30:00+00:00"}, {**EVENTS[1], "at": "2026-10-14T18:00:00+00:00"}]
    b["as_of"] = "2026-10-14T06:00:00+00:00"
    b["event_zone"] = {"24h": b["events"]}                    # a release in the next 24h is in the 24h zone
    text = plain("\n".join(df.brief_lines({"decision": b}, lang)))
    events = next(x for x in text.splitlines() if x.startswith(("События", "Events")))
    assert re.findall(r"\d\d:\d\d", events) == ["15:30", "21:00"]          # name and time only (C2)
    assert not EVENT_FORBIDDEN.search(re.sub(r"\d\d:\d\d", "", events)), events   # no D11 «1,76 раза», no size
    assert text.count("калибровка коридора" if lang == "ru" else "corridor calibration") == 1   # the warning once


@pytest.mark.parametrize("lang", ["ru", "en"])
@pytest.mark.parametrize("kind", ["CPI", "FOMC"])
def test_event_reminder_shows_name_time_and_the_warning_only(lang, kind):
    p = {**payload("event", {"1h", "4h", "24h"}), "event_kind": kind}
    text = plain(df.format_alert("event", p, lang))
    assert "15:30" in text and "×" not in text and "1,76" not in text and "1.76" not in text
    assert not re.search(r"4 из 5|4 of 5|4 out of 5|80\s*%|вероятн|probab|Проверено|Tested|Checked", text, re.I), text


def test_event_facing_catalog_entries_carry_no_size_share_or_probability():
    from beta import i18n
    from beta.i18n_decision import EVENT_NAMES
    keys = [k for k in i18n._CATALOG if k.startswith(("ev_", "ez_", "pa_event", "dc_event", "dc_btc_events",
                                                       "dc_no_events"))]
    assert {"ev_title", "ev_release_note", "ez_note", "ez_event_note", "dc_event_line", "pa_event_title"} <= set(keys)
    for k in keys:
        for lang in ("ru", "en"):
            assert not re.search(r"×|4 из 5|4 of 5|4 out of 5|80\s*%|\{p\b|\{size|\{n\}|вероятн|probab|шанс|chance",
                                 i18n._CATALOG[k][lang], re.I), (k, lang)
    for ru, en in EVENT_NAMES.values():
        assert "×" not in ru + en
    for gone in ("dc_event_size", "dc_event_size_plain", "ev_footer", "pa_event_size", "dc_corridor_event"):
        assert gone not in i18n._CATALOG, gone


# ---- end to end on PostgreSQL: the real decision block, commands and the event reminder -------
from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, run          # noqa: E402

PG_R = datetime(2026, 5, 12, 12, 30, tzinfo=UTC)                   # CPI in config/beta_calendar.yaml
PG_POINTS = [                                                       # (now, horizons inside their zone)
    (PG_R - timedelta(hours=4, minutes=1), {"24h"}),                # 1 min before the 4h zone
    (PG_R - timedelta(hours=4), {"4h", "24h"}),                     # 4h zone start
    (PG_R - timedelta(minutes=61), {"4h", "24h"}),                  # 1 min before the 1h zone
    (PG_R - timedelta(minutes=60), {"1h", "4h", "24h"}),            # 1h zone start
    (PG_R - timedelta(minutes=1), {"1h", "4h", "24h"}),
    (PG_R, {"1h", "4h", "24h"}),
    (PG_R + timedelta(minutes=5), {"1h", "4h", "24h"}),
    (PG_R + timedelta(minutes=55), {"1h", "4h", "24h"}),
    (PG_R + timedelta(minutes=60), set()),                          # every zone ends at +60 min
    (PG_R + timedelta(minutes=61), set()),
]


@pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
def test_end_to_end_suppression_around_a_cpi_release():
    from beta.decision import build_decision, reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build
    from beta_fakes import fresh_pool
    from storage.beta_v0_store import BetaStore
    from test_beta_v2_pg import DAY, _handler, _join, _rows, _seed

    assert DAY.date() == PG_R.date()

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool, touch_at_minute=-1, minutes=14 * 60)                      # 1m tail to 14:00 UTC
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        owner, ru, en = 900000000001, 900000000111, 900000000222
        h0 = _handler(pool, owner, Clock(PG_POINTS[0][0]))
        async with store.connect() as conn:
            for uid in (ru, en):
                await conn.allowlist_add(uid)
        msgs = {ru: await _join(h0, ru, 10, "ru"), en: await _join(h0, en, 20, "en")}
        async with store.connect() as conn:
            for uid in (ru, en):
                await conn.mark_privacy_notice_seen(uid, 4)
        k = 100
        for now, hs in PG_POINTS:
            async with store.connect() as conn:
                blk = await build_decision(conn, CFG, now=now)
            assert blk["available"], now
            assert set(blk["event_zone"]) == hs, now
            assert set(blk["corridor"]["horizons"]) == {"1h", "4h", "24h"} - hs, now
            for side in ("above", "below"):
                for z in blk["levels"][side]:
                    assert not set(z["touch"]) & hs, now
            for x in blk["corridor"]["horizons"].values():           # outside a zone the event flag is never on
                assert not any(x["event_in_window"].values()), now
            h = _handler(pool, owner, Clock(now))
            for uid, lang in ((ru, "ru"), (en, "en")):
                note = ZONE_RU if lang == "ru" else ZONE_EN
                for cmd in ("/btc", "/catchup", "/levels", "/events", "/risk", "/risk 0.5",
                            "/alert %d" % (blk["price"] * 1.01 + 7 * k)):
                    k += 1
                    out = await h.handle(msgs[uid](cmd, k))
                    text = plain(out[-1].html)
                    for hz in hs:
                        assert no_numbers_for(text, hz, lang), (now, cmd, hz, text)
                    if hs:
                        assert "4 из 5" not in text and "4 of 5" not in text, (now, cmd)
                    if cmd in ("/events", "/catchup"):                 # no size multiplier, anywhere around it
                        assert "×" not in text and "1,76" not in text and "1.76" not in text, (now, cmd)
                    if cmd == "/events":                               # the warning goes with a listed release
                        assert text.rstrip().endswith(WARN[lang]) is ("CPI" in text), (now, text)
                        assert ("CPI" in text) is (now <= PG_R), (now, text)          # listed up to the release minute
                    if cmd.startswith("/alert"):
                        k += 1
                        await h.handle(msgs[uid]("/alert del all", k))         # stay under the cap of 5
                        if "24h" in hs:
                            assert "За 24ч до такого" not in text and "Within 24h the price" not in text
                            assert note in text
                        else:
                            assert "За 24ч до такого" in text or "Within 24h the price" in text
                    if cmd.startswith("/risk"):
                        assert (note in text) is bool(hs), (now, cmd)
                        for hz in {"1h", "4h", "24h"} - hs:              # the generic figures come back
                            lab = {"1h": "1ч", "4h": "4ч", "24h": "24ч"}[hz] if lang == "ru" else hz
                            if cmd == "/risk 0.5":
                                assert re.search(rf"за {lab} — в {NUM}" if lang == "ru" else rf"within {lab} — {NUM}",
                                                 text), (now, hz)
                    if cmd == "/levels" and hs & {"4h", "24h"}:
                        assert note in text
                    if cmd == "/catchup" and hs & {"4h", "24h"}:
                        assert note in text and "CPI" in text
        # the event reminder 30 minutes ahead: inside every zone, no corridor, no multiplier
        s = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=s, clock=Clock(PG_R - timedelta(minutes=30)))
        assert r["market"]["forecasts_recorded"] == 0                       # nothing tracked inside a zone
        events = [plain(x[1]) for x in s.sent if "CPI" in plain(x[1])]
        assert len(events) == 2
        for text in events:
            assert "Коридор" not in text and "corridor with" not in text.lower() and "±" not in text
            assert "×" not in text and "4 из 5" not in text and "4 of 5" not in text
            assert "15:30" in text
            assert "Числовой коридор на это время не показываем" in text or "No numerical corridor for this time" in text
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_forecasts") == [{"n": 0}]
        await pool.close()
    run(body())


class Sender:
    def __init__(self):
        self.sent = []

    async def send(self, *, chat_id, html, buttons=None):
        self.sent.append((chat_id, html, buttons))
        return len(self.sent)
