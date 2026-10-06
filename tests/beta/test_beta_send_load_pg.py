"""Send load test (backlog A5) on real PostgreSQL ($BETA_TEST_DSN): twenty participants, a fake sender.
Telegram's flood control puts the row back to PENDING and the next run sends the rest; one blocked
participant never blocks the others; sends are spaced; a stopped notifier leaves PENDING rows, never
SENDING or DELIVERY_UNKNOWN. Synthetic data only."""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, ScenarioReader, fresh_pool, quiet, run
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UIDS = [800000000100 + k for k in range(20)]
BLOCKED = UIDS[3]


@pytest.fixture(autouse=True)
def _calc():
    import test_beta_pg_integration as pgi
    pgi.CALC = pgi.calc_version()       # the shared _setup seeds history under this version


class LoadSender:
    """Answers like Telegram: flood control on the `throttle_at`-th call, Forbidden for BLOCKED, and a
    stop request (SIGTERM) after `stop_after` delivered messages."""

    def __init__(self, *, throttle_at=None, stop=None, stop_after=None):
        self.calls, self.sent = 0, []
        self.throttle_at, self.stop, self.stop_after = throttle_at, stop, stop_after

    async def send(self, *, chat_id, html, buttons=None):
        from beta.delivery import DeliveryRejected, DeliveryThrottled
        self.calls += 1
        if self.calls == self.throttle_at:
            raise DeliveryThrottled(3)
        if chat_id == BLOCKED:
            raise DeliveryRejected("Forbidden: bot was blocked by the user")
        self.sent.append(chat_id)
        if self.stop is not None and len(self.sent) == self.stop_after:
            self.stop.set()
        return 5000 + len(self.sent)


def _pacer():
    from beta.delivery import SendPacer
    waits = []

    async def sleep(s):
        waits.append(round(s, 3))
    return SendPacer(interval_s=0.05, budget_s=35, monotonic=lambda: 0.0, sleep=sleep), waits


async def _twenty(pool, *, brief=False):
    async with pool.acquire() as c:
        await c.executemany(
            "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, stopped_at, "
            "lang, brief_enabled) VALUES ($1, $1, 'ACTIVE', now(), now(), NULL, 'ru', $2)",
            [(u, brief) for u in UIDS])


async def _states(pool):
    async with pool.acquire() as c:
        rows = await c.fetch("SELECT state, count(*) AS n FROM beta_notification_deliveries GROUP BY state")
    return {r["state"]: r["n"] for r in rows}


def test_a_morning_brief_to_twenty_survives_flood_control_and_a_blocked_participant():
    from test_beta_catchup_brief_pg import BRIEF_ON, SLOT
    from test_beta_pg_integration import B0, _detect, _setup

    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _detect(pool, ScenarioReader(quiet), B0)
        await _twenty(pool, brief=True)
        s = LoadSender(throttle_at=7)
        pacer, waits = _pacer()
        r = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s,
                                  clock=Clock(SLOT + timedelta(minutes=1)), pacer=pacer)
        b = r["briefs"]
        # calls 1-6: five delivered and the blocked one FAILED; call 7 hit flood control
        assert (b["scheduled"], b["sent"], b["failed"], b["throttled"], b["unknown"]) == (20, 5, 1, 1, 0)
        assert (r["send_stop"], r["deferred"], r["retry_after_s"]) == ("THROTTLED", 13, 3.0)
        assert waits == [0.05] * 6                                   # spaced: one wait before each later send
        assert await _states(pool) == {"SENT": 5, "FAILED": 1, "PENDING": 14}
        async with pool.acquire() as c:
            row = await c.fetchrow("SELECT error_summary, sending_at, finished_at FROM beta_notification_deliveries "
                                   "d JOIN beta_users u USING (user_pk) WHERE u.telegram_user_id = $1", UIDS[6])
        assert row["error_summary"] == "RetryAfter 3s" and row["sending_at"] is not None and row["finished_at"] is None

        # the next run (one minute later) sends the rest; nobody gets a second copy
        r2 = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s,
                                   clock=Clock(SLOT + timedelta(minutes=2)), pacer=_pacer()[0])
        assert (r2["briefs"]["sent"], r2["briefs"]["scheduled"], r2["send_stop"]) == (14, 0, None)
        assert await _states(pool) == {"SENT": 19, "FAILED": 1}
        assert sorted(s.sent) == sorted(u for u in UIDS if u != BLOCKED) and len(set(s.sent)) == 19
        async with pool.acquire() as c:
            assert await c.fetchval("SELECT count(*) FROM beta_user_activity WHERE action = 'brief_delivered'") == 19
        await pool.close()
    run(body())


def test_a_stopped_notifier_leaves_pending_rows_that_the_next_run_sends():
    from test_beta_v2_pg import _rows

    now = datetime(2026, 10, 6, 12, 0, 40, tzinfo=timezone.utc)      # 15:00 Kyiv: no brief, no weekly due

    async def body():
        from beta.delivery import run_notify_once
        pool = await fresh_pool()
        await _twenty(pool)
        async with BetaStore(pool).connect() as conn:
            await conn.insert_market_alert(
                kind="event", alert_key="event:load", decision_ts=now, decision="PUSH", suppression_reason=None,
                payload={"at": now.isoformat(), "source_at": now.isoformat(), "event_kind": "CPI",
                         "event_at": (now + timedelta(minutes=30)).isoformat(), "minutes": 30, "price": 60000.0,
                         "stats": None, "corridor_1h": None})
        stop = asyncio.Event()
        s = LoadSender(stop=stop, stop_after=4)
        # the committed pacing (50 ms between sends, 35 s budget) and the stop event the CLI sets on SIGTERM
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now), stop=stop)
        assert r["market"]["sent"] == 4 and r["market"]["failed"] == 1      # UIDS[3] blocked among the first five
        assert (r["send_stop"], r["deferred"]) == ("STOPPING", 15)
        assert await _states(pool) == {"SENT": 4, "FAILED": 1, "PENDING": 15}   # no SENDING, no DELIVERY_UNKNOWN
        r2 = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now + timedelta(minutes=1)))
        assert r2["recovered_unknown"] == 0 and r2["market"]["sent"] == 15
        assert await _states(pool) == {"SENT": 19, "FAILED": 1}
        assert len(set(s.sent)) == len(s.sent) == 19
        unknown = await _rows(pool, "SELECT count(*) AS n FROM beta_notification_deliveries "
                                    "WHERE state = 'DELIVERY_UNKNOWN'")
        assert unknown == [{"n": 0}]
        await pool.close()
    run(body())
