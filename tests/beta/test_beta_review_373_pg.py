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
            # an ambiguous send counts: it may have reached them (review of #379)
            await conn.conn.execute(
                "UPDATE beta_notification_deliveries SET state='DELIVERY_UNKNOWN', telegram_message_id=NULL"
                " WHERE delivery_id = (SELECT min(delivery_id) FROM beta_notification_deliveries WHERE user_pk=$1)",
                pks[51])
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


def test_3_the_weekly_report_comes_on_each_recipients_own_sunday_evening():
    """Review of #379: Sunday 19:00 on each recipient's clock (Auckland, Tokyo, Kyiv, Los Angeles), built
    once at the first of them, so never on a Monday-Friday U1a withdrawal day on anyone's clock."""
    from beta.i18n import tz_of
    from beta.weekly import run_due_weekly
    from test_beta_weekly_pg import SLOT, _forecasts
    zones = {61: None, 62: "Asia/Tokyo", 63: "Pacific/Auckland", 64: "America/Los_Angeles"}

    async def body():
        pool = await fresh_pool()
        async with pool.acquire() as c:
            for uid, tz in zones.items():
                await c.execute(
                    "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
                    " stopped_at, lang, tz) VALUES ($1, $1, 'ACTIVE', now(), now(), NULL, 'en', $2)", uid, tz)
        await _forecasts(pool)
        sent, clock = [], {}

        class Sender:
            async def send(self, *, chat_id, html, buttons=None):
                sent.append((chat_id, clock["now"]))
                return len(sent)
        built = []
        async with BetaStore(pool).connect() as conn:
            at = SLOT - timedelta(hours=10)                       # Sunday 06:00 UTC = 18:00 Auckland
            while at <= SLOT + timedelta(hours=13):              # Monday 05:00 UTC = 22:00 Sunday in LA
                clock["now"] = at
                r = await run_due_weekly(conn, CFG, sender=Sender(), clock=Clock(at), push_on=True)
                if r["built"]:
                    built.append(at)
                at += timedelta(minutes=5)
        assert built == [SLOT - timedelta(hours=9)]               # 19:00 Auckland, the first slot
        assert sorted(c for c, _ in sent) == sorted(zones)        # each once
        for chat, when in sent:
            local = when.astimezone(tz_of(zones[chat]))
            assert local.weekday() == 6 and local.hour == 19, (chat, local)
        await pool.close()
    run(body())


def test_3_379_a_move_east_before_ones_slot_or_a_slot_in_the_night_never_sends_on_a_monday():
    """Review of #379: an LA participant who moves to Auckland on Sunday evening (Kyiv), after Auckland's
    slot, gets nothing that week rather than a Monday report; a slot configured inside the night
    (23:30) is never held into Monday."""
    from beta.weekly import run_due_weekly
    from test_beta_weekly_pg import SLOT, _forecasts

    async def scenario(cfg, moves):
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.execute(
                "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, stopped_at,"
                " lang, tz) VALUES (61, 61, 'ACTIVE', now(), now(), NULL, 'en', NULL),"
                " (64, 64, 'ACTIVE', now(), now(), NULL, 'en', 'America/Los_Angeles')")
        await _forecasts(pool)
        sent = []
        clock = {}

        class Sender:
            async def send(self, *, chat_id, html, buttons=None):
                sent.append((chat_id, clock["now"]))
                return len(sent)
        async with BetaStore(pool).connect() as conn:
            at = SLOT - timedelta(hours=1)
            while at <= SLOT + timedelta(hours=16):
                clock["now"] = at
                if at in moves:
                    await conn.conn.execute("UPDATE beta_users SET tz=$2 WHERE telegram_user_id=$1", *moves[at])
                await run_due_weekly(conn, cfg, sender=Sender(), clock=Clock(at), push_on=True)
                at += timedelta(minutes=5)
        await pool.close()
        return sent

    async def body():
        move = {SLOT + timedelta(hours=4): (64, "Pacific/Auckland")}      # Sunday 23:00 Kyiv, Monday 08:00 Auckland
        sent = await scenario(CFG, move)
        assert [c for c, _ in sent] == [61]
        night = CFG.with_overrides(decision={**CFG.raw["decision"],
                                             "weekly_report": {**CFG.raw["decision"]["weekly_report"], "time_kyiv": "23:30"}})
        sent = await scenario(night, {})
        assert sent == []                         # both slots fall in their night: held, then expired on Monday
    run(body())
