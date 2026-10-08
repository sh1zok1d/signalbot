"""Delivery latency (backlog A4) on real PostgreSQL ($BETA_TEST_DSN): an alert is rendered with its own
lag and the class's measured percentiles, and the owner's /admin_latency reads every class from the stored
rows. Synthetic data only."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, NOW, Sender, _handler, _join, _rows, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

OWNER = 900000000999


def _event(at, source_at):
    return {"at": at.isoformat(), "source_at": source_at.isoformat(), "event_kind": "CPI",
            "event_at": (at + timedelta(minutes=30)).isoformat(), "minutes": 30, "price": 60000.0, "stats": None,
            "corridor_1h": None}


def _owner(text, k):
    return {"update_id": k, "message": {"from": {"id": OWNER}, "chat": {"id": OWNER, "type": "private"},
                                        "text": text}}


def test_alerts_carry_their_latency_and_the_owner_reads_it_by_class(monkeypatch):
    from beta import decision_format
    from beta.market_alerts import run_market_alerts

    seen = []
    real = decision_format.format_alert

    def spy(kind, payload, lang):
        seen.append(payload.get("latency"))
        return real(kind, payload, lang)
    monkeypatch.setattr(decision_format, "format_alert", spy)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, OWNER, Clock(NOW))
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        await _join(h, A, 10)
        s = Sender()
        # due 60 s before NOW, decided 20 s before NOW, sent at NOW + 5 s
        async with store.connect() as conn:
            await conn.insert_market_alert(kind="event", alert_key="event:a", decision_ts=NOW - timedelta(seconds=20),
                                           decision="PUSH", suppression_reason=None,
                                           payload=_event(NOW, NOW - timedelta(seconds=60)))
            await run_market_alerts(conn, CFG, sender=s, clock=Clock(NOW + timedelta(seconds=5)), push_on=True)
        assert len(s.sent) == 1
        assert seen[0] == {"class": "event", "source": "event_due", "source_at": (NOW - timedelta(seconds=60)).isoformat(),
                           "lag_s": 65, "p50_s": None, "p95_s": None, "n": 0, "messages": 0, "window_days": 7}
        # the next one is rendered beside the measured class value, with its N
        later = NOW + timedelta(minutes=10)
        async with store.connect() as conn:
            await conn.insert_market_alert(kind="event", alert_key="event:b", decision_ts=later,
                                           decision="PUSH", suppression_reason=None,
                                           payload=_event(later, later - timedelta(seconds=30)))
            await run_market_alerts(conn, CFG, sender=s, clock=Clock(later + timedelta(seconds=2)), push_on=True)
        assert seen[1]["lag_s"] == 32 and (seen[1]["p50_s"], seen[1]["n"]) == (65.0, 1)

        # an alert recorded before A4 (no source time) and an expired one
        async with store.connect() as conn:
            pk = await conn.insert_market_alert(kind="level", alert_key="level:old", decision_ts=later,
                                                decision="PUSH", suppression_reason=None, payload={"at": later.isoformat()})
            pk2 = await conn.insert_market_alert(kind="level", alert_key="level:exp", decision_ts=later,
                                                 decision="PUSH", suppression_reason=None,
                                                 payload={"at": later.isoformat(), "source_at": later.isoformat()})
        user_pk = (await _rows(pool, "SELECT user_pk FROM beta_users"))[0]["user_pk"]
        async with pool.acquire() as c:
            await c.execute("""INSERT INTO beta_notification_deliveries (kind, alert_pk, user_pk, state, decision_ts,
                                   sending_at, finished_at, telegram_message_id)
                               VALUES ('alert', $1, $2, 'SENT', $3::timestamptz, $3::timestamptz, $3::timestamptz + interval '3 seconds', 99)""",
                            pk, user_pk, later)
            await c.execute("""INSERT INTO beta_notification_deliveries (kind, alert_pk, user_pk, state, decision_ts,
                                   suppression_reason, finished_at)
                               VALUES ('alert', $1, $2, 'EXPIRED_UNDELIVERED', $3, 'DELIVERY_TOO_OLD', $3)""",
                            pk2, user_pk, later)

        h = _handler(pool, OWNER, Clock(later + timedelta(minutes=1)))
        text = plain((await h.handle(_owner("/admin_latency", 100)))[0].html)
        assert "event (event_due): N=2 P50 32s P95 65s" in text
        assert "detect P50 30s P95 40s" in text and "send P50 2s P95 25s" in text
        assert "level (candle_close): N=0" in text and "expired 1" in text and "no source 1" in text
        assert plain((await h.handle(_owner("/admin_latency 0", 101)))[0].html).startswith("usage: /admin_latency")
        audit = await _rows(pool, "SELECT result FROM beta_admin_audit WHERE action = 'admin_latency' ORDER BY audit_id")
        assert [a["result"] for a in audit] == ["OK", "INVALID_ARGUMENT"]
        await pool.close()
    run(body())
