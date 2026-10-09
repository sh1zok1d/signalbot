"""The owner's UX preview (2026-10-09): with `access.preview_owner_only` every automated message reaches only the
owner. A participant's row is SUPPRESSED / SUPPRESSED_PREVIEW, terminal, and is never sent after the flag goes off.
`/admin_preview <type>` renders one type for the owner, from the latest stored decision or the current state,
and writes nothing but its own audit row."""
from datetime import timedelta

import pytest

from beta_fakes import ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import A, CFG, DAY, NOW, Sender, _handler, _join, _rows, _seed, plain

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
OWNER = 900000000001


def _cfg(on: bool):
    return CFG.with_overrides(briefing={**dict(CFG["briefing"]), "enabled": True, "time_kyiv": "08:00",
                                        "max_delay_min": 120},
                              access={**dict(CFG["access"]), "preview_owner_only": on})


def test_preview_flag_validates_and_ships_on():
    from beta.config import BetaConfig
    assert BetaConfig.load()["access"]["preview_owner_only"] is True
    with pytest.raises(Exception, match="preview_owner_only"):
        CFG.with_overrides(access={**dict(CFG["access"]), "preview_owner_only": "yes"})


def test_only_the_owner_receives_automated_messages_and_nothing_leaks_later():
    async def body():
        from beta.delivery import run_notify_once
        from beta.decision import reset_cache
        from beta.history_stats import run_history_build
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        h = _handler(pool, OWNER, Clock(NOW))
        for k, uid in enumerate((A, OWNER)):
            async with store.connect() as conn:
                await conn.allowlist_add(uid)
            await _join(h, uid, 10 + 10 * k)
        s = Sender()
        r = await run_notify_once(store, _cfg(True), ON_PUSH, sender=s, clock=Clock(NOW), owner_user_id=OWNER)
        assert s.sent and {c for c, _h, _b in s.sent} == {OWNER}             # the level alert and the briefing
        assert any("первое касание" in plain(x[1]) for x in s.sent)
        assert any(plain(x[1]).startswith("Сводка BTC") for x in s.sent)
        assert r["market"]["suppressed_preview"] == 1 and r["briefs"]["suppressed_preview"] == 1
        rows = await _rows(pool, """SELECT d.kind, d.state, d.suppression_reason FROM beta_notification_deliveries d
                                    JOIN beta_users u USING (user_pk) WHERE u.telegram_user_id = $1 ORDER BY d.kind""", A)
        assert rows == [{"kind": "alert", "state": "SUPPRESSED", "suppression_reason": "SUPPRESSED_PREVIEW"},
                        {"kind": "brief", "state": "SUPPRESSED", "suppression_reason": "SUPPRESSED_PREVIEW"}]
        decisions = await _rows(pool, "SELECT kind, decision FROM beta_market_alerts")
        assert decisions == [{"kind": "level", "decision": "PUSH"}]          # the decision itself is unchanged
        s2 = Sender()                                                        # the flag goes off: nothing late
        await run_notify_once(store, _cfg(False), ON_PUSH, sender=s2, clock=Clock(NOW + timedelta(minutes=1)),
                              owner_user_id=OWNER)
        assert [c for c, _h, _b in s2.sent if c == A] == []
        from beta.delivery import SendPacer                                  # no owner id: fail closed
        p = SendPacer().set_preview(_cfg(True), None)
        assert p.preview_blocks(OWNER) and p.preview_blocks(A)
        await pool.close()
    run(body())


def test_admin_preview_sends_one_type_to_the_owner_and_writes_nothing_else():
    async def body():
        from beta.delivery import run_notify_once
        from beta.decision import reset_cache
        from beta.history_stats import run_history_build
        reset_cache()
        pool = await fresh_pool()
        store = BetaStore(pool)
        await _seed(pool)
        assert (await run_history_build(store, CFG, now=DAY + timedelta(hours=2)))["status"] == "OK"
        h = _handler(pool, OWNER, Clock(NOW))
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        msg = await _join(h, A, 10)
        owner_msg = lambda text, k: {"update_id": k, "message": {"from": {"id": OWNER},  # noqa: E731
                                                                  "chat": {"id": OWNER, "type": "private"}, "text": text}}
        out = await h.handle(owner_msg("/admin_preview", 50))
        assert "brief, weekly" in plain(out[0].html)
        out = await h.handle(owner_msg("/admin_preview level", 51))
        assert "level: ещё не было" in plain(out[0].html) and len(out) == 1
        out = await h.handle(owner_msg("/admin_preview hour", 52))
        assert "hour: ещё не было" in plain(out[0].html) and len(out) == 1
        await run_notify_once(store, _cfg(True), ON_PUSH, sender=Sender(), clock=Clock(NOW), owner_user_id=OWNER)
        tables = [r["t"] for r in await _rows(pool, """SELECT tablename AS t FROM pg_tables WHERE schemaname = 'public'
                                                        AND tablename LIKE 'beta%' AND tablename <> 'beta_admin_audit'""")]
        assert {"beta_claims", "beta_claim_displays", "beta_user_activity", "beta_btc_views"} <= set(tables)

        async def counts():                                                 # every beta table but the audit
            return {t: (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] for t in tables}
        before = await counts()
        for k, kind in enumerate(("level", "brief", "weekly")):
            out = await h.handle(owner_msg(f"/admin_preview {kind}", 60 + k))
            to_owner = [o for o in out if o.chat_id == OWNER and plain(o.html).startswith("🔍 ПРЕВЬЮ")]
            assert len(to_owner) == 1 and all(o.chat_id == OWNER for o in out), kind
        assert await counts() == before                     # no claim, display, telemetry, outbox, view, report
        audit = await _rows(pool, "SELECT action, result, detail->>'type' AS t FROM beta_admin_audit "
                                  "WHERE action = 'admin_preview' ORDER BY audit_id")
        assert [a["t"] for a in audit] == [None, "level", "hour", "level", "brief", "weekly"]
        assert [a["result"] for a in audit][:3] == ["OK", "NONE", "NONE"]
        out = await h.handle(msg("/admin_preview level", 70))                # anyone else: unknown command
        assert all("ПРЕВЬЮ" not in plain(o.html) for o in out)
        await pool.close()
    run(body())
