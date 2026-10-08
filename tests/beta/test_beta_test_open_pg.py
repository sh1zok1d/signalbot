"""The test opening and Day 0 (owner, 2026-10-08; measurement contract §1.4), and the de-identified deletion
audit (§1.5): /admin_test_open is written once, Day 0 is the Kyiv date of the first unknown join at or after it,
an earlier join never starts the test, and a deletion keeps only the cohort fields."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from beta_fakes import CFG, ON, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_feedback import NOW, _cb, _msg

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")
OWNER = 900000000900
UTC = timezone.utc


async def _join(h, store, uid, k):
    async with store.connect() as conn:
        code = await conn.create_invite(label="t", max_uses=9, now=NOW)
    await h.handle(_msg(uid, f"/start {code}", k))
    await h.handle(_cb(uid, "pick:ru", k + 1))
    await h.handle(_cb(uid, "join:ru", k + 2))


def test_day0_consistency_states():
    from beta.admin import day0_consistency
    cfg_on = CFG.with_overrides(briefing={**CFG["briefing"],
                                          "withdrawal": {**CFG["briefing"]["withdrawal"], "day0_kyiv": "2026-11-02"}})
    opened = datetime(2026, 11, 1, 9, tzinfo=UTC)
    assert day0_consistency(CFG, None, None)["state"] == "NOT_OPEN"
    assert day0_consistency(cfg_on, None, None)["state"] == "MISMATCH_NOT_OPEN"
    assert day0_consistency(CFG, opened, None)["state"] == "WAITING_FIRST_UNKNOWN"
    assert day0_consistency(cfg_on, opened, None)["state"] == "MISMATCH_NO_DAY0"
    assert day0_consistency(CFG, opened, date(2026, 11, 2))["state"] == "SET_DAY0_KYIV"
    assert day0_consistency(cfg_on, opened, date(2026, 11, 2))["state"] == "OK"
    assert day0_consistency(cfg_on, opened, date(2026, 11, 3))["state"] == "MISMATCH"


def test_the_test_opens_once_and_day0_follows_the_first_unknown_join_after_it():
    async def body():
        from runtime.beta_bot import BetaBotHandler
        pool = await fresh_pool()
        store = BetaStore(pool)
        early, known, gone, later = 900000000401, 900000000402, 900000000403, 900000000404
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, early, 1)                                   # an accidental join before the opening
        h.clock = Clock(NOW + timedelta(days=2))
        first = await h.handle(_msg(OWNER, "/admin_test_open", 10))
        assert "test opened at" in first[0].html
        again = await h.handle(_msg(OWNER, "/admin_test_open", 11))       # once
        assert "refused" in again[0].html
        async with store.connect() as conn:
            opened = await conn.test_open_at()
            assert opened == NOW + timedelta(days=2)
            assert await conn.derived_day0_kyiv(OWNER) is None            # the early join never starts the test
        h.clock = Clock(NOW + timedelta(days=3))
        await _join(h, store, known, 20)
        async with store.connect() as conn:
            await conn.set_known_contact(known, True)
        h.clock = Clock(NOW + timedelta(days=4))
        await _join(h, store, gone, 30)
        h.clock = Clock(NOW + timedelta(days=5))
        await _join(h, store, later, 40)
        await h.handle(_msg(gone, "/delete_me", 50))                      # Day 0 survives the deletion
        async with store.connect() as conn:
            from beta.i18n import KYIV
            assert await conn.derived_day0_kyiv(OWNER) == (NOW + timedelta(days=4)).astimezone(KYIV).date()
        health = await h.handle(_msg(OWNER, "/admin_health", 51))
        assert "test SET_DAY0_KYIV" in health[0].html
        forced = await h.handle(_msg(OWNER, "/admin_test_open force", 52))  # the owner may move it on purpose
        assert "test opened at" in forced[0].html
        async with store.connect() as conn:
            assert await conn.test_open_at() == NOW + timedelta(days=5)
        await pool.close()
    run(body())


def test_deletions_keep_only_the_cohort_fields():
    """/delete_me, /admin_remove and the retention purge: no fingerprint, no per-person counts (§1.5)."""
    async def body():
        from beta.delivery import run_notify_once
        from runtime.beta_bot import BetaBotHandler
        pool = await fresh_pool()
        store = BetaStore(pool)
        a, b = 900000000411, 900000000412
        h = BetaBotHandler(store, CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(NOW))
        await _join(h, store, a, 1)
        await _join(h, store, b, 10)
        await h.handle(_msg(a, "/delete_me", 20))
        await h.handle(_msg(OWNER, f"/admin_remove {b}", 21))
        async with pool.acquire() as c:
            await c.execute("INSERT INTO beta_allowlist VALUES (77, now())")
            await c.execute("INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
                            " stopped_at) VALUES (77, 77, 'STOPPED', $1, $1, $1)", NOW - timedelta(days=31))
        r = await run_notify_once(store, CFG, ON, sender=None, clock=Clock(NOW))
        assert r["purged_users"] == 1
        rows = await pool.fetch("""SELECT action, target_fingerprint, detail FROM beta_admin_audit
                                   WHERE action IN ('user_delete_me', 'admin_remove', 'retention_purge')
                                   ORDER BY audit_id""")
        assert [r["action"] for r in rows] == ["user_delete_me", "admin_remove", "retention_purge"]
        for r in rows:
            detail = json.loads(r["detail"])
            assert r["target_fingerprint"] is None and set(detail) == {"cohort"}, r["action"]
            assert set(detail["cohort"]) == {"joined_kyiv_date", "known_contact", "joined_after_test_open"}
            assert str(a) not in r["detail"] and str(b) not in r["detail"] and "77" not in r["detail"]
        await pool.close()
    run(body())
