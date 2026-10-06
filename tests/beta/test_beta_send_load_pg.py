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
        at = SLOT + timedelta(minutes=1)
        r = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(at), pacer=pacer)
        b = r["briefs"]
        # call 4 is the blocked participant (FAILED); call 7 hit flood control: only that chat waits,
        # the other 13 are sent in the same run (A5 review 7)
        assert (b["scheduled"], b["sent"], b["failed"], b["throttled"], b["unknown"]) == (20, 18, 1, 1, 0)
        assert (r["send_stop"], r["deferred"], r["retry_after_s"], r["throttled_chats"]) == (None, 0, 3.0, 1)
        assert waits == [0.05] * 19                                  # spaced: one wait before each later send
        assert await _states(pool) == {"SENT": 18, "FAILED": 1, "PENDING": 1}
        async with pool.acquire() as c:
            row = await c.fetchrow("SELECT error_summary, sending_at, finished_at, next_attempt_at "
                                   "FROM beta_notification_deliveries d JOIN beta_users u USING (user_pk) "
                                   "WHERE u.telegram_user_id = $1", UIDS[6])
        # A5 review 1 and 9: the wait is stored on the row, and a PENDING row carries no sending_at
        assert row["error_summary"] == "RetryAfter 3s" and row["next_attempt_at"] == at + timedelta(seconds=3)
        assert row["sending_at"] is None and row["finished_at"] is None

        # two seconds later the chat is still inside Telegram's wait: nothing is sent to it
        mid = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(at + timedelta(seconds=2)),
                                    pacer=_pacer()[0])
        assert mid["briefs"]["sent"] == 0 and s.calls == 20
        # the next run after the wait sends it; nobody gets a second copy
        r2 = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s,
                                   clock=Clock(SLOT + timedelta(minutes=2)), pacer=_pacer()[0])
        assert (r2["briefs"]["sent"], r2["briefs"]["scheduled"], r2["send_stop"]) == (1, 0, None)
        assert await _states(pool) == {"SENT": 19, "FAILED": 1}
        assert sorted(s.sent) == sorted(u for u in UIDS if u != BLOCKED) and len(set(s.sent)) == 19
        async with pool.acquire() as c:
            assert await c.fetchval("SELECT count(*) FROM beta_user_activity WHERE action = 'brief_delivered'") == 19
        await pool.close()
    run(body())


def test_a_stopped_notifier_leaves_pending_rows_that_the_next_run_sends(monkeypatch):
    from beta import delivery
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
        pinged = []

        async def ping():
            pinged.append(1)
            return "OK"
        monkeypatch.setattr(delivery, "deadman_ping", ping)
        # the committed pacing and the stop event the CLI sets on SIGTERM
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now), stop=stop, ping=True)
        assert r["market"]["sent"] == 4 and r["market"]["failed"] == 1      # UIDS[3] blocked among the first five
        assert (r["status"], r["send_stop"], r["deferred"]) == ("STOPPED", "STOPPING", 15)
        assert await _states(pool) == {"SENT": 4, "FAILED": 1, "PENDING": 15}   # no SENDING, no DELIVERY_UNKNOWN
        # A5 review 3: a stopped run ends at its next step: no success heartbeat, no dead-man ping
        assert "briefs" not in r and pinged == []
        assert await _rows(pool, "SELECT component FROM beta_runtime_health WHERE component = 'notifier'") == []
        r2 = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now + timedelta(minutes=1)),
                                   ping=True)
        assert r2["status"] == "OK" and r2["recovered_unknown"] == 0 and r2["market"]["sent"] == 15 and pinged == [1]
        assert await _states(pool) == {"SENT": 19, "FAILED": 1}
        assert len(set(s.sent)) == len(s.sent) == 19
        unknown = await _rows(pool, "SELECT count(*) AS n FROM beta_notification_deliveries "
                                    "WHERE state = 'DELIVERY_UNKNOWN'")
        assert unknown == [{"n": 0}]
        await pool.close()
    run(body())


def test_rows_that_must_wait_are_not_rendered(monkeypatch):
    """A5 review 8: with the pacer closed, no message is rendered; the rows stay PENDING untouched."""
    from beta import decision_format
    from beta.delivery import SendPacer
    from beta.market_alerts import run_market_alerts

    now = datetime(2026, 10, 6, 12, 0, 40, tzinfo=timezone.utc)
    rendered = []
    real = decision_format.format_alert

    def spy(kind, payload, lang):
        rendered.append(kind)
        return real(kind, payload, lang)
    monkeypatch.setattr(decision_format, "format_alert", spy)

    async def body():
        pool = await fresh_pool()
        await _twenty(pool)
        async with BetaStore(pool).connect() as conn:
            await conn.insert_market_alert(
                kind="event", alert_key="event:closed", decision_ts=now, decision="PUSH", suppression_reason=None,
                payload={"at": now.isoformat(), "source_at": now.isoformat(), "event_kind": "CPI",
                         "event_at": (now + timedelta(minutes=30)).isoformat(), "minutes": 30, "price": 60000.0,
                         "stats": None, "corridor_1h": None})
            closed = SendPacer()
            closed.closed = "BUDGET"
            rep = await run_market_alerts(conn, CFG, sender=LoadSender(), clock=Clock(now), push_on=True,
                                          pacer=closed)
        assert rep["sent"] == 0 and rendered == [] and closed.deferred == 20
        assert await _states(pool) == {"PENDING": 20}
        await pool.close()
    run(body())


def test_flood_control_holds_back_every_row_of_that_chat_until_its_wait_ends():
    """Review of #345: Telegram's wait is the chat's, not one message's. While one row of a participant
    waits after flood control, the next run sends none of that participant's rows; the others go."""
    from beta.market_alerts import run_market_alerts

    now = datetime(2026, 10, 6, 12, 0, 40, tzinfo=timezone.utc)

    async def body():
        pool = await fresh_pool()
        await _twenty(pool)
        async with BetaStore(pool).connect() as conn:
            for key in ("event:first", "event:second"):
                await conn.insert_market_alert(
                    kind="event", alert_key=key, decision_ts=now, decision="PUSH", suppression_reason=None,
                    payload={"at": now.isoformat(), "source_at": now.isoformat(), "event_kind": "CPI",
                             "event_at": (now + timedelta(minutes=30)).isoformat(), "minutes": 30,
                             "price": 60000.0, "stats": None, "corridor_1h": None})
        s = LoadSender(throttle_at=1)                  # the first send (UIDS[0], first alert) hits flood control
        async with BetaStore(pool).connect() as conn:
            rep = await run_market_alerts(conn, CFG, sender=s, clock=Clock(now), push_on=True, pacer=_pacer()[0])
        # UIDS[0]: first alert waits 3 s, the second is held back in the same run; UIDS[3] blocked twice
        assert (rep["sent"], rep["failed"], rep["throttled"]) == (36, 2, 1)
        assert UIDS[0] not in s.sent
        async with pool.acquire() as c:
            rows = await c.fetch("SELECT state, next_attempt_at FROM beta_notification_deliveries d "
                                 "JOIN beta_users u USING (user_pk) WHERE u.telegram_user_id = $1 "
                                 "ORDER BY delivery_id", UIDS[0])
        assert [(r["state"], r["next_attempt_at"]) for r in rows] == [("PENDING", now + timedelta(seconds=3)),
                                                                       ("PENDING", None)]
        # two seconds later, with a fresh pacer (a new notifier run): neither row of that chat is sent
        calls = s.calls
        async with BetaStore(pool).connect() as conn:
            rep = await run_market_alerts(conn, CFG, sender=s, clock=Clock(now + timedelta(seconds=2)), push_on=True,
                                          pacer=_pacer()[0])
        assert rep["sent"] == 0 and s.calls == calls and UIDS[0] not in s.sent
        # after the wait both go, once each
        async with BetaStore(pool).connect() as conn:
            rep = await run_market_alerts(conn, CFG, sender=s, clock=Clock(now + timedelta(minutes=1)), push_on=True,
                                          pacer=_pacer()[0])
        assert rep["sent"] == 2 and s.sent.count(UIDS[0]) == 2
        assert await _states(pool) == {"SENT": 38, "FAILED": 2}
        await pool.close()
    run(body())
