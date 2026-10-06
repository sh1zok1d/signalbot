"""A3 monitoring on real PostgreSQL ($BETA_TEST_DSN): the failure spike counts every outbox kind, and the
owner's ready outage notice reaches each active participant in their language. Synthetic data only."""
from datetime import datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, B, C, _handler, _join, _rows, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

UTC = timezone.utc
NOW = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
OWNER = 900000000999


def _owner(text, k, uid=OWNER):
    return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}


def test_failures_of_every_kind_and_the_outage_notice():
    from beta.admin import collect_health

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            for uid in (A, B, C):
                await conn.allowlist_add(uid)
        h = _handler(pool, OWNER, Clock(NOW))
        await _join(h, A, 10, "ru")
        await _join(h, B, 20, "en")
        msg_c = await _join(h, C, 30, "ru")
        await h.handle(msg_c("/stop", 40))                           # STOPPED: no notice

        # three failed briefs: before A3 the spike counted pushes only and stayed silent
        async with store.connect() as conn:
            view_pk = await conn.insert_btc_view(requested_at=NOW, as_of_bucket=None, context_state_digest=None,
                                                 episodization_version=None, episodization_digest=None,
                                                 payload={}, payload_digest="a" * 64, rendered_sha256="b" * 64,
                                                 rendered_html="x", kind="brief")
            users = await _rows(pool, "SELECT user_pk FROM beta_users ORDER BY user_pk")
            for u in users:
                await conn.conn.execute(
                    """INSERT INTO beta_notification_deliveries (kind, brief_date, view_pk, user_pk, state, decision_ts,
                           error_summary, created_at)
                       VALUES ('brief', $1, $2, $3, 'FAILED', $4, 'Forbidden: blocked', $4)""",
                    NOW.date(), view_pk, u["user_pk"], NOW - timedelta(minutes=5))
            health = await collect_health(conn, CFG, ON, NOW)
        spike = next(a for a in health["alerts"] if a["key"] == "DELIVERY_FAILURE_SPIKE")
        assert spike["detail"] == {"count": 3, "by_kind": {"brief": 3}}

        # the ready outage notice: each ACTIVE participant in their language, the owner gets the count
        out = await h.handle(_owner("/admin_outage start", 50))
        by_chat = {o.chat_id: plain(o.html) for o in out}
        assert "outage start notice sent to 2 active participants" in by_chat[OWNER]
        assert by_chat[A].startswith("⚠️ У нас сбой") and by_chat[B].startswith("⚠️ We have an outage")
        assert C not in by_chat
        end = {o.chat_id: plain(o.html) for o in await h.handle(_owner("/admin_outage end", 51))}
        assert end[A].startswith("✅ Сбой устранён") and end[B].startswith("✅ The outage is over")
        usage = plain((await h.handle(_owner("/admin_outage", 52)))[0].html)
        assert usage.startswith("usage: /admin_outage start|end")
        assert len(await h.handle(_owner("/admin_outage start", 53, uid=A))) == 1          # refused for others
        audit = await _rows(pool, """SELECT authorized, result, detail::text AS d FROM beta_admin_audit
                                     WHERE action = 'admin_outage' ORDER BY audit_id""")
        assert [x["result"] for x in audit if x["authorized"]] == ["OK", "OK", "INVALID_ARGUMENT"]
        assert [x["authorized"] for x in audit] == [True, True, True, False]
        await pool.close()
    run(body())
