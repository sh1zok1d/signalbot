"""Implicit push metrics (backlog F5) on real PostgreSQL ($BETA_TEST_DSN): a market alert goes through the
real outbox to two participants; what each did in the next 10 minutes reaches the owner's /admin_stats per
message, with the alert kind from the outbox (not guessed from the activity row). Synthetic data only."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, B, NOW, Sender, _handler, _join, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

OWNER = 900000000999


def _say(uid, text, k):
    return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}


def test_a_delivered_alert_and_what_followed_reach_the_owner_report():
    from beta.market_alerts import run_market_alerts

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            for uid in (A, B):
                await conn.allowlist_add(uid)
        h = _handler(pool, OWNER, Clock(NOW - timedelta(hours=1)))
        await _join(h, A, 10)
        await _join(h, B, 20)
        async with store.connect() as conn:
            await conn.insert_market_alert(
                kind="event", alert_key="event:f5", decision_ts=NOW, decision="PUSH", suppression_reason=None,
                payload={"at": NOW.isoformat(), "source_at": NOW.isoformat(), "event_kind": "CPI",
                         "event_at": (NOW + timedelta(minutes=30)).isoformat(), "minutes": 30, "price": 60000.0,
                         "stats": None, "corridor_1h": None})
            rep = await run_market_alerts(conn, CFG, sender=Sender(), clock=Clock(NOW), push_on=True)
        assert rep["sent"] == 2
        # A looks at the levels 4 minutes later; B switches event alerts off 6 minutes later
        await _handler(pool, OWNER, Clock(NOW + timedelta(minutes=4))).handle(_say(A, "/levels", 30))
        await _handler(pool, OWNER, Clock(NOW + timedelta(minutes=6))).handle(_say(B, "/push events off", 31))

        out = await _handler(pool, OWNER, Clock(NOW + timedelta(hours=1))).handle(_say(OWNER, "/admin_stats", 40))
        text = "\n".join(plain(o.html) for o in out)
        assert "pushes, last 7 days (10-min window: button / any action / muted that type)" in text
        assert "event: 1 messages, sent 2 · button 0 · action 2 · muted 1" in text
        stamp = NOW.strftime("%m-%d %H:%M")
        assert f"event {stamp} UTC: sent 2 · button 0 · action 2 · muted 1" in text
        assert "time to disable event: N=1 median 0.1 h after the first (median 1 received)" in text
        for raw in (A, B):
            assert str(raw) not in text
        await pool.close()
    run(body())
