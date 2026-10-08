"""The one exception to the append-only audit (owner, 2026-10-08, #420): deleting a participant de-identifies the
audit rows about them in the same transaction. No audit row is deleted, no action changes, no other person's row
is edited, and an actor fingerprint that identifies them becomes the role. Anything else stays rejected."""
import json
from datetime import timedelta

import asyncpg
import pytest

from beta.admin import fingerprint
from beta.i18n import KYIV
from beta_fakes import CFG, ON, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_feedback import NOW, _msg
from test_beta_test_open_pg import OWNER, _join

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
GONE, LIVE = 900000000511, 900000000512
T = NOW - timedelta(hours=5, minutes=7)


async def _audit(pool, action, actor, target, detail):
    return await pool.fetchval("""INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, target_fingerprint,
                                      result, detail, recorded_at) VALUES ($1, true, $2, $3, 'OK', $4::jsonb, $5)
                                  RETURNING audit_id""", action, actor, target, json.dumps(detail), T)


def test_deleting_a_participant_de_identifies_only_their_audit_rows():
    async def body():
        from runtime.beta_bot import BetaBotHandler
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, GONE, 10)
        await _join(h, store, LIVE, 20)
        gone, live, owner = fingerprint(GONE), fingerprint(LIVE), fingerprint(OWNER)
        about = [await _audit(pool, "admin_known", owner, gone, {"known_contact": True}),
                 await _audit(pool, "admin_reply", owner, gone, {})]
        by_them = await _audit(pool, "admin_reply", gone, live, {"len": 3})       # they acted, about someone else
        others = [await _audit(pool, "admin_known", owner, live, {"known_contact": False}),
                  await _audit(pool, "admin_stats", owner, None, {"waitlist": 2})]
        before = {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}

        await h.handle(_msg(GONE, "/delete_me", 40))

        after = {r["audit_id"]: dict(r) for r in await pool.fetch("SELECT * FROM beta_admin_audit")}
        assert set(before) <= set(after)                                          # nothing deleted
        day = T.astimezone(KYIV).replace(hour=0, minute=0, second=0, microsecond=0)
        for i in about:
            b, a = before[i], after[i]
            assert (a["action"], a["authorized"], a["result"], a["actor_fingerprint"]) == (
                b["action"], b["authorized"], b["result"], owner)
            assert (a["target_fingerprint"], json.loads(a["detail"]), a["recorded_at"]) == (None, {}, day)
        a = after[by_them]
        assert a["actor_fingerprint"] == "participant"
        assert {k: v for k, v in a.items() if k != "actor_fingerprint"} == {
            k: v for k, v in before[by_them].items() if k != "actor_fingerprint"}
        for i in others:
            assert after[i] == before[i]
        assert not [r for r in after.values() if gone in (r["actor_fingerprint"], r["target_fingerprint"])]
        await pool.close()
    run(body())


def test_the_owner_deleting_themself_becomes_the_owner_role():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", OWNER)
        i = await _audit(pool, "admin_stats", fingerprint(OWNER), None, {"waitlist": 2})
        async with store.connect() as conn:
            r = await conn.delete_participant(OWNER, OWNER)
        assert r["audit"] == 1
        row = await pool.fetchrow("SELECT * FROM beta_admin_audit WHERE audit_id=$1", i)
        assert (row["actor_fingerprint"], json.loads(row["detail"]), row["recorded_at"]) == ("owner", {"waitlist": 2}, T)
        await pool.close()
    run(body())


def test_everything_else_stays_append_only():
    async def body():
        pool = await fresh_pool()
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", LIVE)
        gone, live = fingerprint(GONE), fingerprint(LIVE)
        i = await _audit(pool, "admin_known", "u_owner", gone, {"known_contact": True})
        j = await _audit(pool, "admin_known", "u_owner", live, {"known_contact": True})
        day = "date_trunc('day', recorded_at AT TIME ZONE 'Europe/Kyiv') AT TIME ZONE 'Europe/Kyiv'"
        ok = f"target_fingerprint=NULL, detail='{{}}', recorded_at={day}"
        refused = [
            f"UPDATE beta_admin_audit SET {ok} WHERE audit_id={i}",                          # no deletion running
            f"DELETE FROM beta_admin_audit WHERE audit_id={i}",
            f"SELECT set_config('signalbot.audit_deidentify_fps', '{gone}', true), "
            f"set_config('signalbot.audit_deidentify_role', 'participant', true); "
            f"DELETE FROM beta_admin_audit WHERE audit_id={i}",                               # never a delete
            f"SELECT set_config('signalbot.audit_deidentify_fps', '{gone}', true), "
            f"set_config('signalbot.audit_deidentify_role', 'participant', true); "
            f"UPDATE beta_admin_audit SET {ok}, action='admin_reply' WHERE audit_id={i}",     # meaning changes
            f"SELECT set_config('signalbot.audit_deidentify_fps', '{gone}', true), "
            f"set_config('signalbot.audit_deidentify_role', 'participant', true); "
            f"UPDATE beta_admin_audit SET {ok}, result='FAIL' WHERE audit_id={i}",
            f"SELECT set_config('signalbot.audit_deidentify_fps', '{gone}', true), "
            f"set_config('signalbot.audit_deidentify_role', 'participant', true); "
            f"UPDATE beta_admin_audit SET {ok} WHERE audit_id={j}",                           # someone else's row
            f"SELECT beta_audit_deidentify(ARRAY['{live}'], 'participant')",                  # someone still present
        ]
        for sql in refused:
            async with pool.acquire() as c:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with c.transaction():
                        await c.execute(sql)
        assert await pool.fetchval("SELECT count(*) FROM beta_admin_audit WHERE target_fingerprint IS NOT NULL") == 2
        await pool.close()
    run(body())
