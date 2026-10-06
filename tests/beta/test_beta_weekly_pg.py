"""Weekly report (backlog B4) on real PostgreSQL ($BETA_TEST_DSN): built once at the Sunday slot,
stored append-only before any send, delivered through the outbox to participants with the type on,
`/push weekly off` honoured and recorded, the owner copy with the operational breakdown, and the
delivery counted in the owner breakdown. Synthetic data only; no network, no Telegram."""
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, B, C, Sender, _handler, _join, _rows, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
SLOT = datetime(2026, 5, 17, 16, 0, tzinfo=UTC)               # Sunday 19:00 Kyiv
OWNER = 900000000999


async def _forecasts(pool):
    start = SLOT - timedelta(days=7) + timedelta(hours=1)        # inside the week that ends at 19:05 Kyiv
    rows = []
    for i in range(40):
        at = start + timedelta(hours=i)
        outside = i >= 36
        rows.append(("1h", at, at + timedelta(hours=1), 100.0, 98.0, 102.0, 0.8, "T",
                     "OUTSIDE" if outside else "INSIDE", 103.02 if outside else 101.0, 99.0, at + timedelta(hours=1)))
    async with pool.acquire() as c:
        await c.executemany(
            """INSERT INTO beta_forecasts (horizon, issued_at, horizon_end, anchor_price, lower, upper, coverage,
                   model_version, outcome, realized_high, realized_low, evaluated_at)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""", rows)
        alerts = [("level", "level:PDH:a", "PUSH", None), ("level", "level:PWH:b", "PUSH", None),
                  ("move", "move:c", "PUSH", None), ("level", "level:PDL:d", "SUPPRESSED", "DAILY_CAP"),
                  ("price", "price:e", "PUSH", None)]
        await c.executemany(
            """INSERT INTO beta_market_alerts (kind, alert_key, decision_ts, utc_day, decision, suppression_reason,
                   payload) VALUES ($1,$2,$3,($3 AT TIME ZONE 'UTC')::date,$4,$5,'{}'::jsonb)""",
            [(k, key, SLOT - timedelta(days=2), d, r) for k, key, d, r in alerts])


def test_the_weekly_report_is_built_once_and_delivered_to_those_who_want_it():
    from beta.delivery import run_notify_once

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        clock = Clock(SLOT - timedelta(days=3))
        h = _handler(pool, OWNER, clock)
        async with store.connect() as conn:
            for uid in (A, B, C):
                await conn.allowlist_add(uid)
        await _join(h, A, 10, "ru")
        await _join(h, B, 20, "en")
        msg = await _join(h, C, 30, "ru")
        out = await h.handle(msg("/push weekly off", 40))
        assert "итоги недели (воскресенье вечером): выкл" in plain(out[0].html)
        out = await h.handle(msg("/push", 41))
        assert "/push weekly off" in plain(out[0].html)
        await _forecasts(pool)

        # Sunday 18:59 Kyiv: nothing yet
        sender = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=sender, clock=Clock(SLOT - timedelta(minutes=1)),
                                  owner_user_id=OWNER)
        assert r["weekly"]["built"] is False and not await _rows(pool, "SELECT * FROM beta_weekly_reports")

        # 19:05 Kyiv: one report, two deliveries (C turned the type off), the owner copy
        sender = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=sender, clock=Clock(SLOT + timedelta(minutes=5)),
                                  owner_user_id=OWNER)
        wk = r["weekly"]
        assert wk["built"] is True and wk["scheduled"] == 2 and wk["sent"] == 2 and wk["owner"] == "sent", r
        texts = {chat: plain(html) for chat, html, _ in sender.sent if chat in (A, B)}
        assert "Неделя бота: 10.05–17.05" in texts[A] and "• 1ч: 90% (N=40" in texts[A]
        assert "уровни 2, события 0, резкие движения 1" in texts[A]
        assert "The bot's week: 10.05–17.05" in texts[B]
        assert C not in {chat for chat, _, _ in sender.sent}
        owner = [plain(html) for chat, html, _ in sender.sent if chat == OWNER]
        assert any("Неделя бота" in x for x in owner)
        assert any("weekly report 2026-05-10 .. 2026-05-17 (owner part)" in x for x in owner)
        assert any("    weekly: sent 0" in x for x in owner)       # the breakdown is read before the sends
        stored = await _rows(pool, "SELECT week_end, payload->>'version' AS v FROM beta_weekly_reports")
        assert stored == [{"week_end": SLOT.date(), "v": "BETA_WEEKLY_V1"}]
        acts = await _rows(pool, "SELECT count(*) AS n FROM beta_user_activity WHERE action='weekly_delivered'")
        assert acts[0]["n"] == 2

        # one minute later: nothing new is built or sent; the stored payload is append-only
        sender = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=sender, clock=Clock(SLOT + timedelta(minutes=6)),
                                  owner_user_id=OWNER)
        assert r["weekly"]["built"] is False and r["weekly"]["sent"] == 0
        async with pool.acquire() as c:
            with pytest.raises(asyncpg.PostgresError):
                await c.execute("UPDATE beta_weekly_reports SET built_at = now()")

        # the owner breakdown counts the deliveries and C's mute
        async with store.connect() as conn:
            from beta.usage import build_usage_report
            rep = build_usage_report(await conn.usage_facts(), now=SLOT + timedelta(minutes=7),
                                     owner_user_id=OWNER)
        weekly = rep["last_7_days"]["owner_breakdown"]["unknown"]["types"]["weekly"]
        assert weekly["delivered"] == 2 and weekly["mutes"] == 1 and weekly["muted_now"] == 1
        await pool.close()
    run(body())


def test_paused_messages_build_nothing_and_late_rows_expire():
    from beta.weekly import run_due_weekly

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, OWNER, Clock(SLOT - timedelta(days=1)))
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        await _join(h, A, 10, "ru")
        async with store.connect() as conn:
            r = await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(minutes=1)),
                                     push_on=False)
            assert r["built"] is False
            # past max_delay_min the week is skipped, never sent late
            r = await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(minutes=121)),
                                     push_on=True)
            assert r["built"] is False
            r = await run_due_weekly(conn, CFG, sender=None, clock=Clock(SLOT + timedelta(minutes=2)), push_on=True)
            assert r["built"] is True and r["failed"] == 1                 # no bot token: FAILED, never resent
            r = await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(minutes=3)),
                                     push_on=True)
            assert r["sent"] == 0
        await pool.close()
    run(body())
