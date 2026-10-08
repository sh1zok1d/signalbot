"""The one exception to the append-only audit (owner, 2026-10-08, #420): deleting a participant de-identifies the
audit rows about them in the same transaction. No audit row is deleted, no action changes, no other person's row
is edited, and an actor fingerprint that identifies them becomes the role; every row about or by them keeps
only the Kyiv date and detail {} (owner, 2026-10-09). Anything else stays rejected."""
import json
from datetime import timedelta

import asyncpg
import pytest

from beta.admin import fingerprint
from beta.pseudonym import legacy_pseudonym
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
        a, b = after[by_them], before[by_them]                                   # owner, 2026-10-09: same shape,
        assert (a["actor_fingerprint"], a["target_fingerprint"], json.loads(a["detail"]), a["recorded_at"]) == (
            "participant", live, {}, day)                                         # the live target stays
        assert (a["action"], a["authorized"], a["result"]) == (b["action"], b["authorized"], b["result"])
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
        day = T.astimezone(KYIV).replace(hour=0, minute=0, second=0, microsecond=0)
        assert (row["actor_fingerprint"], json.loads(row["detail"]), row["recorded_at"]) == ("owner", {}, day)
        await pool.close()
    run(body())


def test_everything_else_stays_append_only():
    async def body():
        pool = await fresh_pool()
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", LIVE)
        gone, live = fingerprint(GONE), fingerprint(LIVE)
        i = await _audit(pool, "admin_known", "u_owner", gone, {"known_contact": True})
        j = await _audit(pool, "admin_known", "u_owner", live, {"known_contact": True})
        await _audit(pool, "admin_known", "u_owner", legacy_pseudonym(LIVE), {"known_contact": True})  # pre-#423 row
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
            # someone still present: SQL can check only the legacy form (no key in SQL); the keyed form is refused
            # in Python by the store before the call (test_a_live_keyed_fingerprint_is_refused_before_the_update)
            f"SELECT beta_audit_deidentify(ARRAY['{legacy_pseudonym(LIVE)}'], 'participant')",
        ]
        for sql in refused:
            async with pool.acquire() as c:
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with c.transaction():
                        await c.execute(sql)
        assert await pool.fetchval("SELECT count(*) FROM beta_admin_audit WHERE target_fingerprint IS NOT NULL") == 3
        await pool.close()
    run(body())


def test_a_live_keyed_fingerprint_is_refused_before_the_update():
    """#423: the store checks, with the key, that no fingerprint passed belongs to anyone still present (keyed or
    legacy) and raises before beta_audit_deidentify runs; nothing changes."""
    from storage.beta_v0_store import AuditDeidentifyRefused

    async def body():
        pool = await fresh_pool()
        await pool.execute("INSERT INTO beta_allowlist VALUES ($1, now())", LIVE)
        j = await _audit(pool, "admin_known", "u_owner", fingerprint(LIVE), {"known_contact": True})
        k = await _audit(pool, "admin_known", "u_owner", legacy_pseudonym(LIVE), {"known_contact": True})
        for fps in ([fingerprint(LIVE)], [legacy_pseudonym(LIVE)], [fingerprint(GONE), fingerprint(LIVE)]):
            async with BetaStore(pool).connect() as conn:
                with pytest.raises(AuditDeidentifyRefused):
                    async with conn.transaction():
                        await conn.deidentify_audit(fps, "participant")
        rows = await pool.fetch("SELECT audit_id, target_fingerprint, detail FROM beta_admin_audit ORDER BY audit_id")
        assert [(r["audit_id"], r["target_fingerprint"]) for r in rows] == [(j, fingerprint(LIVE)),
                                                                            (k, legacy_pseudonym(LIVE))]
        await pool.close()
    run(body())


def test_deletion_de_identifies_both_the_keyed_and_the_legacy_rows():
    """Rows written before the keyed switch hold the legacy fingerprint, rows after it the keyed one: deleting the
    participant de-identifies both; a live person's rows in either form stay."""
    async def body():
        from runtime.beta_bot import BetaBotHandler
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, GONE, 10)
        await _join(h, store, LIVE, 20)
        keyed, legacy = fingerprint(GONE), legacy_pseudonym(GONE)
        assert keyed != legacy
        mine = [await _audit(pool, "admin_known", "u_owner", keyed, {"known_contact": True}),
                await _audit(pool, "admin_known", "u_owner", legacy, {"known_contact": True})]
        theirs = [await _audit(pool, "admin_known", "u_owner", fingerprint(LIVE), {"known_contact": True}),
                  await _audit(pool, "admin_known", "u_owner", legacy_pseudonym(LIVE), {"known_contact": True})]
        async with store.connect() as conn:
            out = await conn.delete_participant(GONE, owner_user_id=OWNER)
        assert out["audit"] == 2
        rows = {r["audit_id"]: r for r in await pool.fetch("SELECT * FROM beta_admin_audit")}
        assert all(rows[i]["target_fingerprint"] is None and json.loads(rows[i]["detail"]) == {} for i in mine)
        assert [rows[i]["target_fingerprint"] for i in theirs] == [fingerprint(LIVE), legacy_pseudonym(LIVE)]
        await pool.close()
    run(body())
