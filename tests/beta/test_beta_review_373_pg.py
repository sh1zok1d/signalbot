"""The external review of #373 on real PostgreSQL ($BETA_TEST_DSN): each participant's own daily budget in
the store and at delivery, and the weekly report held through a
recipient's night."""
from datetime import datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
T = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)                     # 12:00 Kyiv, 02:00 Los Angeles


async def _users(pool):
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, stopped_at,"
            " lang, tz) VALUES (51, 51, 'ACTIVE', now(), now(), NULL, 'ru', NULL),"
            " (52, 52, 'ACTIVE', now(), now(), NULL, 'en', 'America/Los_Angeles')")
        return {r["telegram_user_id"]: r["user_pk"] for r in await c.fetch("SELECT telegram_user_id, user_pk FROM beta_users")}


async def _sent_alert(conn, key, ts, kind="level"):
    pk = await conn.insert_market_alert(kind=kind, alert_key=key, decision_ts=ts, decision="PUSH",
                                        suppression_reason=None, payload={})
    await conn.materialize_alert_deliveries(alert_pk=pk, kind=kind, decision_ts=ts, target_user_pk=None, expired=False)
    return pk


def test_1_each_participant_counts_their_own_day_and_is_capped_alone():
    async def body():
        pool = await fresh_pool()
        pks = await _users(pool)
        async with BetaStore(pool).connect() as conn:
            # four level alerts sent to both on the 13th in LA (Kyiv's 14th morning)
            for i in range(4):
                await _sent_alert(conn, f"level:x:{i}", datetime(2026, 10, 14, 2 + i, 0, tzinfo=UTC))
            await conn.conn.execute("UPDATE beta_notification_deliveries SET state='SENT', sending_at=decision_ts, finished_at=decision_ts,"
                                    " telegram_message_id=delivery_id")
            loads = {r["user_pk"]: r for r in await conn.recipient_loads(
                "push_levels", since=T - timedelta(hours=48), outbox_kind="alert", alert_kinds=["level", "move"])}
            assert len(loads[pks[51]]["times"]) == 4 and loads[pks[52]]["tz"] == "America/Los_Angeles"
            # 18:00 UTC: Kyiv's 14th (4 sent: spent), LA's 14th (none of them: free)
            at = datetime(2026, 10, 14, 18, 0, tzinfo=UTC)
            assert await conn.count_sent_on_own_day(user_pk=pks[51], ts=at, tz=None, outbox_kind="alert",
                                                    alert_kinds=["level", "move"]) == 4
            assert await conn.count_sent_on_own_day(user_pk=pks[52], ts=at, tz="America/Los_Angeles",
                                                    outbox_kind="alert", alert_kinds=["level", "move"]) == 0
            # the next level alert: one delivery DAILY_CAP (Kyiv, their day spent), one sent (LA)
            from beta.market_alerts import run_market_alerts
            pk = await _sent_alert(conn, "level:x:next", at)
            await conn.conn.execute("UPDATE beta_market_alerts SET payload = $2::jsonb WHERE alert_pk=$1", pk,
                                    '{"at": "2026-10-14T18:00:00+00:00", "level_kind": "PDH", "level": 62950.0, '
                                    '"side": 1, "period": "day", "price": 62960.0, "history": null, "next": null, '
                                    '"corridor_4h": null, "event_zone": {}}')

            class Sender:
                async def send(self, *, chat_id, html, buttons=None):
                    return 1
            await run_market_alerts(conn, CFG, sender=Sender(), clock=Clock(at + timedelta(seconds=30)), push_on=True)
            rows = {r["user_pk"]: (r["state"], r["suppression_reason"]) for r in await conn.conn.fetch(
                "SELECT user_pk, state, suppression_reason FROM beta_notification_deliveries WHERE alert_pk=$1", pk)}
            assert rows[pks[51]] == ("SUPPRESSED", "DAILY_CAP") and rows[pks[52]][0] == "SENT"
        await pool.close()
    run(body())


def test_3_the_weekly_report_waits_for_the_end_of_a_recipients_night():
    from beta.weekly import run_due_weekly
    from test_beta_weekly_pg import SLOT, _forecasts

    async def body():
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.execute(
                "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, stopped_at,"
                " lang, tz) VALUES (61, 61, 'ACTIVE', now(), now(), NULL, 'ru', NULL),"
                " (62, 62, 'ACTIVE', now(), now(), NULL, 'en', 'Asia/Tokyo')")
        await _forecasts(pool)
        sent = []

        class Sender:
            async def send(self, *, chat_id, html, buttons=None):
                sent.append(chat_id)
                return len(sent)
        async with BetaStore(pool).connect() as conn:
            # Sunday 19:05 Kyiv = 01:05 Monday in Tokyo: Kyiv now, Tokyo held (still PENDING)
            r = await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(minutes=5)), push_on=True)
            assert sent == [61] and r["expired"] == 0
            # 06:59 Tokyo: still night
            await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(hours=5, minutes=59)), push_on=True)
            assert sent == [61]
            # 07:05 Tokyo: sent, its delay counted from the end of the night, not from the Kyiv slot
            await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(SLOT + timedelta(hours=6, minutes=5)), push_on=True)
            assert sent == [61, 62]
        await pool.close()
    run(body())
