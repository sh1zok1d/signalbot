"""Decision support V2 on real PostgreSQL ($BETA_TEST_DSN): history sync, nightly build,
decision block in every view, commands, market alerts through the outbox, forecast tracking,
privacy (PRODUCT_DECISION_V2). Synthetic data only; no network, no Telegram."""
import asyncio
import re
from datetime import date, datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from beta import history_data as hd
from storage.beta_v0_store import BetaStore
from v2_fakes import checksum_text, kline_zip, metrics_zip, one_minute_rows, synthetic_rows

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
T0 = datetime(2026, 1, 1, tzinfo=UTC)
HIST_DAYS = 131
DAY = T0 + timedelta(days=HIST_DAYS)                     # 2026-05-12, Kyiv is UTC+3
NOW = DAY + timedelta(hours=6, seconds=40)               # 09:00 Kyiv
A, B, C = 900000000111, 900000000222, 900000000333


def plain(html):
    return re.sub(r"<[^>]+>", "", html).replace("&lt;", "<").replace("&gt;", ">")


class Sender:
    def __init__(self):
        self.sent = []

    async def send(self, *, chat_id, html, buttons=None):
        self.sent.append((chat_id, html, buttons))
        return len(self.sent)


async def _rows(pool, sql, *args):
    async with pool.acquire() as c:
        return [dict(r) for r in await c.fetch(sql, *args)]


async def _seed(pool, *, touch_at_minute=357, minutes=6 * 60):
    """History for 131 days, then today's Binance 1m tail: flat below yesterday's high, one touch."""
    from beta.hist_series import bars_from_rows
    rows, ois = synthetic_rows(T0, HIST_DAYS, seed=11)
    store = BetaStore(pool)
    async with store.connect() as conn:
        for k in range(0, len(rows), 20000):
            await conn.upsert_hist_bars(rows[k:k + 20000], fetched_at=T0)
        await conn.upsert_hist_oi(ois, fetched_at=T0)
    b = bars_from_rows(rows)
    pdh = float(max(r["high"] for r in rows[-288:]))
    base = min(rows[-1]["close"], pdh * 0.995)
    recs = []
    for m in range(minutes):
        ts = DAY + timedelta(minutes=m)
        hi = pdh + 5.0 if m == touch_at_minute else base * 1.0005
        recs.append(("binance", "BTCUSDT", ts, base, hi, base * 0.9995, base, 10.0, 5.0, "live"))
    async with pool.acquire() as c:
        await c.executemany("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                   taker_buy_volume, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""", recs)
    return {"pdh": pdh, "base": base, "bars": b}


async def _join(h, uid, n, lang="ru"):
    def msg(text, k):
        return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}

    def cb(data, k):
        return {"update_id": k, "callback_query": {"id": f"c{k}", "from": {"id": uid},
                                                    "message": {"chat": {"id": uid}, "message_id": 1}, "data": data}}
    await h.handle(msg("/start", n))
    await h.handle(cb(f"pick:{lang}", n + 1))
    await h.handle(cb(f"join:{lang}", n + 2))
    return msg


def _handler(pool, owner, clock):
    from runtime.beta_bot import BetaBotHandler
    return BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON_PUSH, owner_user_id=owner, clock=clock)


def test_history_sync_verifies_resumes_and_falls_back_to_daily_objects():
    from beta.history_data import sync_history
    rows, ois = synthetic_rows(datetime(2026, 8, 1, tzinfo=UTC), 63, seed=3)

    def month(y, m):
        return [r for r in rows if datetime.fromtimestamp(r["open_time_ms"] / 1000, tz=UTC).strftime("%Y-%m") == f"{y}-{m:02d}"]

    def on(d):
        return [r for r in rows if datetime.fromtimestamp(r["open_time_ms"] / 1000, tz=UTC).date() == d]

    # August 2026 holds the E1-RUN-001 final holdout: the archive below has no object that
    # overlaps it (the fake could not serve one); only the allowed August days exist.
    allowed_aug = [date(2026, 8, d) for d in list(range(1, 16)) + list(range(26, 32))]
    objects = {
        **{f"daily/klines/BTCUSDT/5m/BTCUSDT-5m-{d.isoformat()}.zip": kline_zip(on(d), f"a{d.day}.zip")
           for d in allowed_aug},
        "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09-01.zip": kline_zip(on(date(2026, 9, 1)), "b.zip", header=False),
        "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-01.zip": kline_zip(on(date(2026, 10, 1)), "c.zip"),
        "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-02.zip": kline_zip(on(date(2026, 10, 2)), "d.zip"),
        # verifies against its CHECKSUM but holds a row with high < low: BAD, and the sync goes on
        "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09-03.zip": kline_zip(
            [{**r, "high": r["low"] - 1.0} if k == 5 else r for k, r in enumerate(on(date(2026, 9, 3)))], "e.zip"),
        "daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-10-01.zip": metrics_zip(
            [o for o in ois if datetime.fromtimestamp(o["ts_ms"] / 1000, tz=UTC).date() == date(2026, 10, 1)], "m.zip"),
    }
    calls = []

    async def fetch(url):
        key = url.split("/data/futures/um/", 1)[1]
        calls.append(key)
        assert hd.url_refusal(url) is None, f"a protected object reached the network: {key}"
        if key.endswith(".CHECKSUM"):
            body = objects.get(key[: -len(".CHECKSUM")])
            if key.startswith("daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-02"):
                return b"0" * 64 + b"  wrong\n"                      # a corrupt checksum object
            return None if body is None else checksum_text(body, "x.zip")
        return objects.get(key)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        now = datetime(2026, 10, 3, 3, tzinfo=UTC)
        rep = await sync_history(store, now=now, fetch=fetch, klines_start=date(2026, 8, 1),
                                 metrics_start=date(2026, 8, 10))
        assert rep["status"] == "PARTIAL" and any("checksum mismatch" in e for e in rep["errors"])
        assert rep["fallback_daily"] == 30                     # September's monthly object is not published
        # E1: rejected in the plan, never requested — neither an archive nor its CHECKSUM
        e1 = (["monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip"]
              + [f"daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-{d:02d}.zip" for d in range(16, 26)]
              + [f"daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-08-{d:02d}.zip" for d in range(16, 26)])
        assert rep["protected_rejected"] == 21 and rep["protected_rejected_keys"] == e1
        assert not {c.removesuffix(".CHECKSUM") for c in calls} & set(e1)
        assert all(hd.url_refusal(c) is None for c in calls)
        assert not any("ProtectedObjectRefused" in e for e in rep["errors"])   # the plan never tried
        assert "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-15.zip" in calls
        assert "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-26.zip" in calls
        ledger = {r["object_key"]: r["status"] for r in await _rows(pool, "SELECT object_key, status FROM beta_hist_objects")}
        assert not set(ledger) & set(e1)
        assert ledger["daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-15.zip"] == "OK"
        assert ledger["monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09.zip"] == "MISSING"
        assert ledger["daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09-01.zip"] == "OK"
        assert ledger["daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09-02.zip"] == "MISSING"
        assert ledger["daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-09-03.zip"] == "BAD" and rep["bad"] == 1
        assert any("BTCUSDT-5m-2026-09-03" in e and "HistoryDataError" in e for e in rep["errors"])
        assert "daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-10-02.zip" not in ledger      # never recorded as OK
        assert ledger["daily/metrics/BTCUSDT/BTCUSDT-metrics-2026-10-02.zip"] == "MISSING"
        n = (await _rows(pool, "SELECT count(*) AS n FROM beta_hist_bars_5m"))[0]["n"]
        assert n == 21 * 288 + 288 + 288          # Aug 1-15 and 26-31, Sep 1, Oct 1; nothing of Aug 16-25
        inside = await _rows(pool, "SELECT count(*) AS n FROM beta_hist_bars_5m WHERE open_time >= $1 AND open_time < $2",
                             datetime(2026, 8, 16, tzinfo=UTC), datetime(2026, 8, 26, tzinfo=UTC))
        assert inside == [{"n": 0}]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_hist_oi_5m"))[0]["n"] == 288
        calls.clear()
        again = await sync_history(store, now=now, fetch=fetch, klines_start=date(2026, 8, 1),
                                   metrics_start=date(2026, 10, 1))
        assert "monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip" not in calls       # OK objects are not refetched
        assert again["bars_written"] == 0 or again["status"] == "PARTIAL"
        health = await _rows(pool, "SELECT component FROM beta_runtime_health")
        assert {"component": "history_sync"} in health
        await pool.close()
    run(body())


def test_an_overlapping_object_in_the_plan_is_refused_without_a_request(monkeypatch):
    from beta.history_data import sync_history
    calls = []

    async def fetch(url):
        calls.append(url)
        return None

    bad = [hd.klines_monthly(2026, 8), hd.metrics_daily(date(2026, 8, 25)), hd.klines_daily(date(2026, 8, 15))]
    monkeypatch.setattr(hd, "plan_objects", lambda today, **kw: (bad, []))

    async def body():
        pool = await fresh_pool()
        rep = await sync_history(BetaStore(pool), now=datetime(2026, 10, 3, 3, tzinfo=UTC), fetch=fetch)
        refused = [e for e in rep["errors"] if "ProtectedObjectRefused" in e]
        assert len(refused) == 2 and rep["fetched"] == 1
        assert [c.rsplit("/", 1)[-1] for c in calls] == ["BTCUSDT-5m-2026-08-15.zip"]   # only the allowed day
        await pool.close()
    run(body())


def test_build_view_commands_alerts_forecasts_and_privacy():
    from beta.decision import reset_cache
    from beta.delivery import run_notify_once
    from beta.history_stats import run_history_build
    from beta.market_alerts import _decide_and_record

    async def body():
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        seed = await _seed(pool)
        rep = await run_history_build(store, CFG, now=DAY + timedelta(hours=2))
        assert rep["status"] == "OK" and rep["bars"] == HIST_DAYS * 288 and rep["missing_bars"] == 0
        stats = (await _rows(pool, "SELECT version, payload->'range_model'->>'version' AS rm FROM beta_hist_stats"))[0]
        assert stats == {"version": "BETA_HIST_STATS_V1", "rm": "BETA_RANGE_MODEL_V1"}

        owner = 900000000001
        h = _handler(pool, owner, Clock(NOW))
        msgs = {}
        for k, uid in enumerate((A, B, C)):
            async with store.connect() as conn:
                await conn.allowlist_add(uid)
            msgs[uid] = await _join(h, uid, 10 + 10 * k)
        async with store.connect() as conn:
            for uid in (A, B, C):
                await conn.mark_privacy_notice_seen(uid, 4)
            await conn.set_push_pref(B, "push_levels", False)
            await conn.set_push_pref(C, "push_enabled", False)
            await conn.conn.execute("DELETE FROM beta_bot_update_state")

        # ---- commands --------------------------------------------------------------------
        out = await h.handle(msgs[A]("/levels", 100))
        text = plain(out[-1].html)
        assert text.startswith("Уровни BTC · Binance · цена ") and "\n↑ " in text and ("\n— сейчас " in text or "\nЦена у уровня " in text)  # one ladder (C3)
        assert re.search(r"\n↓ .* · за 4ч (≈|исторически в) ", text) and "↳ после первого касания" in text
        # NOW is 06:00 UTC on a CPI day (12:30 UTC): inside the 24h event zone, outside the 1h/4h ones
        assert "за 24ч" not in text and "Коридор 24ч" not in text
        assert "24ч: числовую оценку не показываем — CPI США (инфляция), Вт 12.05 15:30 (Киев)" in text
        out = await h.handle(msgs[A]("/risk 0.5", 101))
        risk = plain(out[-1].html)
        assert "Стоп 0,50%" in risk and "за 1ч — в " in risk and "за 4ч — в " in risk
        assert "за 24ч — без оценки" in risk and "24ч: числовую оценку не показываем" in risk
        out = await h.handle(msgs[A]("/events", 102))
        ev = plain(out[-1].html)
        assert ev.startswith("События (время — Киев)") and "\nВт 12.05 15:30 — CPI США (инфляция)\n" in ev
        assert ev.endswith("\nCPI США (инфляция): вокруг публикации обычная калибровка коридора не применяется.")
        assert "×" not in ev and "случа" not in ev                 # a plain calendar: no size, no N
        out = await h.handle(msgs[A]("/accuracy", 103))
        assert "Живые прогнозы ещё не созрели" in plain(out[-1].html)
        target = round(seed["base"] * 1.02)
        out = await h.handle(msgs[B]("/alert %d" % target, 104))
        assert plain(out[-1].html).startswith("Сообщу, когда BTC дойдёт до ")
        out = await h.handle(msgs[B]("/alert", 105))
        assert "1. " in plain(out[-1].html)
        for k in range(4):
            await h.handle(msgs[B]("/alert %d" % (target + 100 * (k + 1)), 106 + k))
        out = await h.handle(msgs[B]("/alert %d" % (target + 1000), 111))
        assert "максимум" in plain(out[-1].html)                   # 5 is the cap
        out = await h.handle(msgs[B]("/alert del 5", 112))
        assert plain(out[-1].html) == "Удалено: 1."
        out = await h.handle(msgs[A]("/btc", 113))
        assert out[-1].buttons[-1] == [("Уровни", "L:levels"), ("Риск", "L:risk")]
        out = await h.handle(msgs[A]("/catchup", 114))
        catchup = plain(out[-1].html)
        # no live tape is seeded here, so the window is DATA STALE: no corridor and no levels (A2);
        # the calendar and the event warning carry no market number and stay
        assert "Коридор и уровни сейчас не показываем: данные отстают." in catchup
        assert "Уровни\n" not in catchup and "— сейчас " not in catchup and "Коридор (Binance" not in catchup
        assert "в 4 из 5" not in catchup and "24ч: числовую оценку не показываем" in catchup
        assert "События в ближайшие сутки: 15:30 CPI США (инфляция)" in catchup   # 2026-05-12 is a CPI day
        views = await _rows(pool, "SELECT kind, payload->'decision'->>'available' AS ok FROM beta_btc_views ORDER BY view_pk")
        assert views[-2:] == [{"kind": "btc", "ok": "true"}, {"kind": "catchup", "ok": "true"}]

        # ---- market alerts: the first touch of yesterday's high, through the outbox ----------
        s = Sender()
        brief_cfg = CFG.with_overrides(briefing={"enabled": True, "time_kyiv": "08:00", "max_delay_min": 120})
        r = await run_notify_once(store, brief_cfg, ON_PUSH, sender=s, clock=Clock(NOW))
        m = r["market"]
        assert m["pushed"] == 1 and m["sent"] == 1 and m["forecasts_recorded"] == 2      # 24h is in its zone
        tracked = await _rows(pool, "SELECT horizon FROM beta_forecasts ORDER BY horizon")
        assert tracked == [{"horizon": "1h"}, {"horizon": "4h"}]
        alerts = await _rows(pool, "SELECT kind, alert_key, decision FROM beta_market_alerts")
        assert alerts == [{"kind": "level", "alert_key": f"level:PDH:{DAY.date().isoformat()}", "decision": "PUSH"}]
        level_msgs = [x for x in s.sent if "максимум вчера" in plain(x[1]) and "первое касание" in plain(x[1])]
        assert [x[0] for x in level_msgs] == [A]                  # B: levels off; C: push off
        assert level_msgs[0][2][:2] == [[("📊 BTC сейчас", "b:now")], [("Уровни", "L:levels"), ("Риск", "L:risk")]]
        assert all(d.startswith("k:") for row in level_msgs[0][2][2:] for _l, d in row)   # «🎯 Проверить» the next level
        # the morning briefing renders the decision block in the same cycle (under the unseeded,
        # stale tape: the A2 line instead of corridor and levels, the calendar from the block)
        briefs = [x for x in s.sent if plain(x[1]).startswith("BTC за ночь")]
        assert len(briefs) == 3 and "Коридор и уровни сейчас не показываем: данные отстают." in plain(briefs[0][1])
        assert "Коридор (Binance" not in plain(briefs[0][1])
        assert "\nСобытия в ближайшие сутки: 15:30 CPI США (инфляция)\n" in plain(briefs[0][1])
        assert "24ч: числовую оценку не показываем" in plain(briefs[0][1]) and "×" not in plain(briefs[0][1])
        r2 = await run_notify_once(store, brief_cfg, ON_PUSH, sender=s, clock=Clock(NOW + timedelta(minutes=1)))
        assert r2["market"]["pushed"] == 0 and r2["market"]["forecasts_recorded"] == 0

        # ---- a personal alert reaches its owner even with level pushes off ----------------
        async with pool.acquire() as c:
            await c.execute("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                   taker_buy_volume, source) VALUES ('binance','BTCUSDT',$1,$2,$3,$2,$2,1,1,'live')""",
                            DAY + timedelta(hours=6, minutes=1), seed["base"], target + 1.0)
        s2 = Sender()
        r3 = await run_notify_once(store, CFG, ON_PUSH, sender=s2, clock=Clock(NOW + timedelta(minutes=2)))
        assert r3["market"]["sent"] == 1 and s2.sent[0][0] == B and "дошёл до вашего уровня" in plain(s2.sent[0][1])
        left = await _rows(pool, "SELECT count(*) AS n FROM beta_price_alerts WHERE triggered_at IS NULL "
                                 "AND cancelled_at IS NULL")
        assert left == [{"n": 3}]

        # ---- quiet hours suppress market alerts, never personal ones ------------------------
        night = datetime(2026, 5, 12, 22, 30, tzinfo=UTC)          # 01:30 Kyiv
        async with store.connect() as conn:
            res = await _decide_and_record(conn, CFG, {"kind": "move", "key": "move:test", "payload": {"x": 1}},
                                           now=night, push_on=True)
            assert res == "QUIET_HOURS"
            assert await _decide_and_record(conn, CFG, {"kind": "move", "key": "move:test", "payload": {}},
                                            now=night, push_on=True) == "DUPLICATE"

        # ---- forecasts are scored once their horizon passed ----------------------------------
        async with pool.acquire() as c:
            later = [("binance", "BTCUSDT", DAY + timedelta(hours=6, minutes=m), seed["base"], seed["base"] * 1.0003,
                      seed["base"] * 0.9997, seed["base"], 1.0, 0.5, "live") for m in range(2, 70)]
            await c.executemany("""INSERT INTO klines_1m (exchange, symbol, ts, open, high, low, close, volume,
                                       taker_buy_volume, source) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                                   ON CONFLICT DO NOTHING""", later)
        await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(DAY + timedelta(hours=7, minutes=5, seconds=40)))
        scored = await _rows(pool, "SELECT horizon, outcome, realized_high AS high FROM beta_forecasts WHERE outcome IS NOT NULL")
        # the 06:01 minute (the personal alert's +2% spike) is inside the window issued at 06:00:40
        assert scored == [{"horizon": "1h", "outcome": "OUTSIDE", "high": target + 1.0}]
        from storage.beta_v0_store import BetaConn
        read = BetaConn.forecast_accuracy

        async def unused(self, *, since):                     # review #334 item 15: no dead 30-day read
            raise AssertionError("/accuracy shows the windowed detail; the 30-day summary is not read")
        BetaConn.forecast_accuracy = unused
        try:
            out = await h.handle(msgs[A]("/accuracy", 200))
        finally:
            BetaConn.forecast_accuracy = read
        assert "1ч: 7 дн. мало данных (N=1)" in plain(out[-1].html)   # one window: no share yet
        async with store.connect() as conn:
            acc = await conn.forecast_accuracy(since=DAY)
        assert acc == {"1h": {"OUTSIDE": 1, "N_EFF": 1}}

        # ---- /check with the real block; «Следить» makes a personal alert in one tap ----------
        out = await h.handle(msgs[A]("/check +1%", 201))
        check = plain(out[-1].html)
        assert check.startswith("BTC → ") and "1ч: " in check and "4ч: " in check
        assert "24ч: числовую оценку не показываем" in check                  # NOW is inside the CPI 24h zone
        assert out[-1].buttons[0][0][1].startswith("w:")
        before = (await _rows(pool, "SELECT count(*) AS n FROM beta_price_alerts WHERE cancelled_at IS NULL"))[0]["n"]
        cb = {"update_id": 202, "callback_query": {"id": "c202", "from": {"id": A},
                                                    "message": {"chat": {"id": A}, "message_id": 1},
                                                    "data": out[-1].buttons[0][0][1]}}
        watched = await h.handle(cb)
        assert plain(watched[-1].html).startswith("Сообщу, когда BTC дойдёт до ")
        after = (await _rows(pool, "SELECT count(*) AS n FROM beta_price_alerts WHERE cancelled_at IS NULL"))[0]["n"]
        assert after == before + 1

        # ---- /delete_me removes the participant's alerts ------------------------------------
        await h.handle(msgs[B]("/delete_me", 203))
        # B's alerts are gone; A's alert from «Следить» stays
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_price_alerts"))[0]["n"] == 1
        targeted = await _rows(pool, "SELECT target_user_pk FROM beta_market_alerts WHERE kind='price'")
        assert targeted == [{"target_user_pk": None}]
        await pool.close()
    run(body())


def test_bootstrap_rewind_only_moves_the_watermark_back():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            await conn.advance_watermark("bootstrap", symbol="BTCUSDT", market_type="perp", timeframe="5m",
                                         bucket_ts=NOW.replace(second=0))
            prev = await conn.rewind_bootstrap_watermark(symbol="BTCUSDT", market_type="perp", timeframe="5m",
                                                         bucket_ts=NOW.replace(second=0) - timedelta(days=30))
            assert prev == NOW.replace(second=0)
            await conn.rewind_bootstrap_watermark(symbol="BTCUSDT", market_type="perp", timeframe="5m",
                                                  bucket_ts=NOW.replace(second=0))       # never forward
            wm = await conn.get_watermark("bootstrap", symbol="BTCUSDT", market_type="perp", timeframe="5m")
            assert wm == NOW.replace(second=0) - timedelta(days=30)
        await pool.close()
    run(body())


def test_a_failing_update_never_replays_and_undeliverable_alerts_never_block():
    from beta.market_alerts import run_market_alerts
    from runtime.beta_bot import BOT_NAME

    def event(at):
        return {"at": at.isoformat(), "event_kind": "CPI", "event_at": (at + timedelta(minutes=30)).isoformat(),
                "minutes": 30, "price": 60000.0, "stats": None, "corridor_1h": None}

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, 900000000001, Clock(NOW))
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        msg = await _join(h, A, 10)
        out = await h.handle(msg("/alert nan", 20))                 # parses as a float; never reaches the DB
        assert "/alert" in plain(out[-1].html)

        async def boom(conn, update):
            raise RuntimeError("bad update")
        real, h._dispatch = h._dispatch, boom
        stop = asyncio.Event()

        class Poller:
            def __init__(self):
                self.offsets, self.sent = [], []

            async def get_me(self):
                return None

            async def get_updates(self, *, offset, timeout):
                self.offsets.append(offset)
                if len(self.offsets) > 1:
                    stop.set()
                    return []
                return [msg("/btc", 21)]

            async def send(self, *, chat_id, html, buttons=None):
                self.sent.append(chat_id)
                return 1
        from runtime import beta_bot
        poller = Poller()
        orig_cls = beta_bot.BetaBotHandler
        beta_bot.BetaBotHandler = lambda *a, **k: h                  # the service polls with this handler
        try:
            await asyncio.wait_for(beta_bot.run_bot_service(store=store, cfg=CFG, switches=lambda: ON_PUSH,
                                                            sender=poller, owner_user_id=None, stop=stop,
                                                            poll_timeout_s=0), 30)
        finally:
            beta_bot.BetaBotHandler = orig_cls
            h._dispatch = real
        assert poller.offsets == [21, 22] and poller.sent == []     # logged, rolled back, skipped, not replayed
        async with store.connect() as conn:
            assert await conn.get_last_update_id(BOT_NAME) == 21

        # moves nobody receives (A switched them off) are marked dispatched, so they never crowd
        # out the alerts behind them
        cfg = CFG.with_overrides(notifications={**dict(CFG["notifications"]), "max_deliveries_per_run": 2})
        async with store.connect() as conn:
            await conn.set_push_pref(A, "push_moves", False)
            for k in range(3):
                await conn.insert_market_alert(kind="move", alert_key=f"move:t{k}", decision_ts=NOW - timedelta(minutes=3 - k),
                                               decision="PUSH", suppression_reason=None, payload={"x": k})
            await conn.insert_market_alert(kind="event", alert_key="event:t", decision_ts=NOW, decision="PUSH",
                                           suppression_reason=None, payload=event(NOW))
        s = Sender()
        reps = []
        for _ in range(2):
            async with store.connect() as conn:
                reps.append(await run_market_alerts(conn, cfg, sender=s, clock=Clock(NOW), push_on=True))
        assert [r["materialized"] for r in reps] == [0, 1] and [r["sent"] for r in reps] == [0, 1]
        assert [x[0] for x in s.sent] == [A] and "CPI" in plain(s.sent[0][1])
        left = await _rows(pool, "SELECT count(*) AS n FROM beta_market_alerts WHERE dispatched_at IS NULL")
        assert left == [{"n": 0}]

        # a pause after the row was made: the pending row is suppressed, never sent late
        async with store.connect() as conn:
            await conn.insert_market_alert(kind="event", alert_key="event:t2", decision_ts=NOW, decision="PUSH",
                                           suppression_reason=None, payload=event(NOW))
            r = await run_market_alerts(conn, cfg, sender=s, clock=Clock(NOW), push_on=False)
        assert r["materialized"] == 1 and r["sent"] == 0 and r["suppressed"] == 1 and len(s.sent) == 1
        rows = await _rows(pool, "SELECT x.state, x.suppression_reason FROM beta_notification_deliveries x "
                                 "JOIN beta_market_alerts a USING (alert_pk) WHERE a.alert_key='event:t2'")
        assert rows == [{"state": "SUPPRESSED", "suppression_reason": "PUSH_DISABLED"}]
        await pool.close()
    run(body())
