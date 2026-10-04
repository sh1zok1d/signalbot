"""Invite codes, waitlist, per-user activity, and the owner usage report."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest

from beta.access import ACTIVITY_ACTIONS, rejected_hmac
from beta.admin import fingerprint
from beta.usage import format_usage_report
from beta_fakes import CFG, ON, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaConn, BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

NOW = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
OWNER = 900000000001
HEX64 = "ab" * 32


def _msg(uid, text, update_id):
    return {"update_id": update_id, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"},
                                                "text": text}}


def _cb(uid, data, update_id):
    return {"update_id": update_id, "callback_query": {
        "id": f"cb{update_id}", "from": {"id": uid},
        "message": {"chat": {"id": uid}, "message_id": 1}, "data": data}}


def _handler(pool, *, owner=OWNER, cap=None, username="BetaBot", salt="test-salt", when=NOW):
    from runtime.beta_bot import BetaBotHandler
    cfg = CFG if cap is None else CFG.with_overrides(access={"max_active_users": cap})
    return BetaBotHandler(BetaStore(pool), cfg, switches=lambda: ON, owner_user_id=owner,
                          clock=Clock(when), bot_username=username, telemetry_salt=salt)


async def _rows(pool, sql, *args):
    async with pool.acquire() as c:
        return [dict(r) for r in await c.fetch(sql, *args)]


def test_join_by_code_and_rejected_codes_offer_the_waitlist():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool)
        async with store.connect() as conn:
            good = await conn.create_invite(label="friends", max_uses=2, now=NOW)
            expired = await conn.create_invite(label="old", max_uses=2, now=NOW,
                                               expires_at=NOW - timedelta(days=1))
            revoked = await conn.create_invite(label="pulled", max_uses=2, now=NOW)
            assert await conn.revoke_invite(revoked, NOW) == "OK"
            exhausted = await conn.create_invite(label="full", max_uses=1, now=NOW)
            assert await conn.redeem_invite(exhausted, 900000000777, NOW, 20, OWNER) == "OK"
        alice = 900000000101
        out = await h.handle(_msg(alice, f"/start {good}", 1))
        assert out[0].buttons == [[("Русский", "pick:ru"), ("English", "pick:en")]]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_users"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT invite_code FROM beta_allowlist WHERE telegram_user_id=$1",
                            alice))[0]["invite_code"] == good
        await h.handle(_cb(alice, "pick:ru", 2))
        await h.handle(_cb(alice, "join:ru", 3))
        joined = await _rows(pool, "SELECT invite_code, privacy_notice_version, lang FROM beta_users")
        assert joined == [{"invite_code": good, "privacy_notice_version": 4, "lang": "ru"}]
        assert (await _rows(pool, "SELECT used_count FROM beta_invites WHERE code=$1", good))[0]["used_count"] == 1

        async def rejected(uid, code, update_id):
            before = (await _rows(pool, "SELECT count(*) AS n FROM beta_waitlist"))[0]["n"]
            out = await h.handle(_msg(uid, f"/start {code}", update_id))
            assert "закрытой бете" in out[0].html and "closed beta" in out[0].html
            assert out[0].buttons == [[("Хочу доступ / Request access", "wl:ask")]]
            assert (await _rows(pool, "SELECT count(*) AS n FROM beta_waitlist"))[0]["n"] == before
            assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist WHERE telegram_user_id=$1",
                                uid))[0]["n"] == 0

        await rejected(900000000102, expired, 4)
        await rejected(900000000103, revoked, 5)
        await rejected(900000000104, exhausted, 6)
        assert (await _rows(pool, "SELECT used_count FROM beta_invites WHERE code=$1", exhausted))[0]["used_count"] == 1
        hashes = await _rows(pool, "SELECT user_hmac FROM beta_rejected_start_hashes ORDER BY user_hmac")
        expected = sorted(rejected_hmac("test-salt", uid) for uid in (900000000102, 900000000103, 900000000104))
        assert [r["user_hmac"] for r in hashes] == expected
        cols = await _rows(pool, """SELECT column_name FROM information_schema.columns
                                    WHERE table_name='beta_rejected_start_hashes'""")
        assert {r["column_name"] for r in cols} == {"utc_day", "user_hmac"}
        await pool.close()
    run(body())


def test_owner_invite_commands_are_audited():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool, username="BetaBot")
        created = await h.handle(_msg(OWNER, "/admin_invite_new 3 7 friends", 1))
        assert "t.me/BetaBot?start=" in created[0].html
        code = created[0].html.split("start=", 1)[1].split("<", 1)[0]
        assert len(code) == 12
        listed = await h.handle(_msg(OWNER, "/admin_invites", 2))
        assert "friends" in listed[0].html and "0/3" in listed[0].html and "expires none" not in listed[0].html
        revoked = await h.handle(_msg(OWNER, f"/admin_invite_revoke {code}", 3))
        assert ">revoked<" in revoked[0].html or revoked[0].html.endswith("revoked</pre>")
        listed = await h.handle(_msg(OWNER, "/admin_invites", 4))
        assert "revoked" in listed[0].html
        nameless = _handler(pool, username=None)
        created2 = await nameless.handle(_msg(OWNER, "/admin_invite_new 1 desk", 5))
        assert "bot username unavailable" in created2[0].html
        actions = [r["action"] for r in await _rows(
            pool, "SELECT action FROM beta_admin_audit ORDER BY audit_id")]
        assert actions == ["admin_invite_new", "admin_invites", "admin_invite_revoke",
                           "admin_invites", "admin_invite_new"]
        await pool.close()
    run(body())


def test_owner_invalid_code_is_not_a_rejected_start():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool)
        out = await h.handle(_msg(OWNER, "/start missing-code", 1))
        assert out[0].buttons[0][0][1] == "pick:ru"
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_rejected_start_hashes"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_rejected_start_counts"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_cap_blocks_joins_and_admin_add_but_not_the_owner():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, cap=1)
        async with store.connect() as conn:
            code = await conn.create_invite(label="one", max_uses=5, now=NOW)
            owner_code = await conn.create_invite(label="owner", max_uses=1, now=NOW)
        first = await h.handle(_msg(900000000301, f"/start {code}", 1))
        assert first[0].buttons[0][0][1] == "pick:ru"
        blocked = await h.handle(_msg(900000000302, f"/start {code}", 2))
        assert "wl:ask" in blocked[0].buttons[0][0][1]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 1
        owner = await h.handle(_msg(OWNER, f"/start {owner_code}", 3))
        assert owner[0].buttons[0][0][1] == "pick:ru"
        assert (await _rows(pool, "SELECT used_count FROM beta_invites WHERE code=$1", owner_code))[0]["used_count"] == 1
        bare = await h.handle(_msg(OWNER, "/start", 4))
        assert bare[0].buttons[0][0][1] == "pick:ru"
        added = await h.handle(_msg(OWNER, "/admin_add 900000000303", 5))
        assert "cap reached" in added[0].html
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist WHERE telegram_user_id=900000000303"))[0]["n"] == 0
        admit = await h.handle(_msg(OWNER, "/admin_waitlist_admit 900000000399", 6))
        assert "cap reached" in admit[0].html
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist WHERE telegram_user_id=900000000399"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_concurrent_last_slot_never_exceeds_uses_or_cap():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        async with store.connect() as conn:
            code = await conn.create_invite(label="last", max_uses=1, now=NOW)
            left = await conn.create_invite(label="left", max_uses=2, now=NOW)
            right = await conn.create_invite(label="right", max_uses=2, now=NOW)

        async def redeem(code, uid, cap):
            async with store.connect() as conn:
                async with conn.transaction():
                    outcome = await conn.redeem_invite(code, uid, NOW, cap, None)
                    await asyncio.sleep(0.05)
                    return outcome

        uses = await asyncio.gather(redeem(code, 900000000401, 20), redeem(code, 900000000402, 20))
        assert sorted(uses) == ["EXHAUSTED", "OK"]
        assert (await _rows(pool, "SELECT used_count FROM beta_invites WHERE code=$1", code))[0]["used_count"] == 1
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 1
        async with pool.acquire() as c:
            await c.execute("DELETE FROM beta_allowlist")

        cap = await asyncio.gather(redeem(left, 900000000403, 1), redeem(right, 900000000404, 1))
        assert sorted(cap) == ["CAP", "OK"]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 1
        await pool.close()
    run(body())


def test_waitlist_stores_nothing_until_the_button_and_delete_me_removes_it():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool, salt=None)
        uid = 900000000501
        out = await h.handle(_msg(uid, "/start", 1))
        assert "Хочу доступ / Request access" in out[0].buttons[0][0][0]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_waitlist"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_rejected_start_hashes"))[0]["n"] == 0
        counts = await _rows(pool, "SELECT attempt_count FROM beta_rejected_start_counts")
        assert counts == [{"attempt_count": 1}]
        pressed = await h.handle(_cb(uid, "wl:ask", 2))
        assert "Telegram ID" in pressed[1].html and "/delete_me" in pressed[1].html
        row = await _rows(pool, "SELECT telegram_user_id, requested_at FROM beta_waitlist")
        assert row[0]["telegram_user_id"] == uid
        again = await h.handle(_cb(uid, "wl:ask", 3))
        assert "Telegram ID" in again[1].html
        assert (await _rows(pool, "SELECT requested_at FROM beta_waitlist"))[0]["requested_at"] == row[0]["requested_at"]
        listed = await h.handle(_msg(OWNER, "/admin_waitlist", 4))
        assert str(uid) in listed[0].html
        audit = await _rows(pool, """SELECT detail::text AS detail FROM beta_admin_audit
                                     WHERE action='admin_waitlist'""")
        assert str(uid) not in audit[0]["detail"]
        admitted = await h.handle(_msg(OWNER, f"/admin_waitlist_admit {uid}", 5))
        assert "admitted" in admitted[0].html
        assert any("Access granted" in o.html and "/start" in o.html for o in admitted)
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_waitlist"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist WHERE telegram_user_id=$1",
                            uid))[0]["n"] == 1
        start = await h.handle(_msg(uid, "/start", 6))
        assert start[0].buttons[0][0][1] == "pick:ru"
        await pool.close()
    run(body())


def test_delete_me_removes_waitlist_and_activity():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool)
        uid = 900000000601
        await h.handle(_msg(uid, "/start", 1))
        await h.handle(_cb(uid, "wl:ask", 2))
        async with store.connect() as conn:
            code = await conn.create_invite(label="later", max_uses=1, now=NOW)
        await h.handle(_msg(OWNER, f"/admin_waitlist_admit {uid}", 3))
        await h.handle(_msg(uid, "/start", 4))
        await h.handle(_cb(uid, "pick:ru", 5))
        await h.handle(_cb(uid, "join:ru", 6))
        await h.handle(_msg(uid, "/help", 7))
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_user_activity"))[0]["n"] >= 1
        deleted = await h.handle(_msg(uid, "/delete_me", 8))
        assert "удал" in deleted[0].html.lower() or "delete" in deleted[0].html.lower()
        for table in ("beta_users", "beta_allowlist", "beta_waitlist", "beta_user_activity"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {table}"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_each_action_is_recorded_and_telemetry_failure_does_not_break_the_reply(caplog):
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool)
        uid = 8675309
        async with store.connect() as conn:
            code = await conn.create_invite(label="actions", max_uses=1, now=NOW)
        await h.handle(_msg(uid, f"/start {code}", 1))
        await h.handle(_cb(uid, "pick:en", 2))
        await h.handle(_cb(uid, "join:en", 3))
        await h.handle(_msg(uid, "/btc", 4))
        await h.handle(_msg(uid, "/history", 5))
        await h.handle(_msg(uid, "/help", 6))
        await h.handle(_msg(uid, "/terms", 7))
        await h.handle(_msg(uid, "/lang", 8))
        await h.handle(_cb(uid, "set:en", 9))
        await h.handle(_msg(uid, "/catchup", 20))
        await h.handle(_msg(uid, "/brief on", 21))
        await h.handle(_msg(uid, "/push off", 22))
        await h.handle(_msg(uid, "/push on", 23))         # back on: the push below must still reach this user
        # decision support (PRODUCT_DECISION_V2): every command records its action, also without data
        await h.handle(_msg(uid, "/levels", 24))
        await h.handle(_msg(uid, "/risk 0.5", 25))
        await h.handle(_msg(uid, "/alert 65000", 26))
        await h.handle(_msg(uid, "/events", 27))
        await h.handle(_msg(uid, "/accuracy", 28))
        await h.handle(_cb(uid, "L:levels", 29))
        async with store.connect() as conn:
            view_pk = await conn.insert_btc_view(
                requested_at=NOW, as_of_bucket=NOW, context_state_digest=None,
                episodization_version=None, episodization_digest=None,
                payload={"product_status": "NO ACTIVE EVENTS",
                         "active_episode": {"episode_id": "EV-AABBCCDDEE",
                                            "event_type": "PRICE_OI_CONTRACTION_DOWN",
                                            "opened_at": NOW.isoformat()},
                         "horizons": {"1h": {}, "24h": {}}},
                payload_digest=HEX64, rendered_sha256=HEX64, rendered_html="view", lang="en")
            await conn.conn.execute(
                """INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket, opened_at,
                       triggered_at, rules_version, rules_digest, code_version, calculation_version,
                       opening_tape_digest, trigger_tape_digest, last_bucket, last_streak)
                   VALUES ('EV-AABBCCDDEE','BTCUSDT','PRICE_OI_CONTRACTION_DOWN','TRIGGERED',$1,$1,$1,
                           'BETA_EVENT_RULES_V1',$2,'code','calc',$2,$2,$1,1)""", NOW, HEX64)
        for tab, n in (("event", 30), ("1h", 31), ("24h", 32)):
            await h.handle(_cb(uid, f"o:{view_pk}:{tab}", n))
        await h.handle(_cb(uid, "d:EV-AABBCCDDEE", 33))
        await h.handle(_cb(uid, "u:EV-AABBCCDDEE", 34))
        await h.handle(_cb(uid, "n:EV-AABBCCDDEE", 35))
        async with store.connect() as conn:
            await conn.conn.execute(
                """INSERT INTO beta_push_decisions (episode_pk, event_type, decision_ts, utc_day, would_push,
                       decision, push_enabled_effective)
                   SELECT episode_pk, event_type, $1, $2, true, 'PUSH', true FROM beta_episodes""",
                NOW, NOW.date())
            await conn.materialize_deliveries(
                decision_id=(await conn.conn.fetchval("SELECT decision_id FROM beta_push_decisions")),
                episode_pk=(await conn.conn.fetchval("SELECT episode_pk FROM beta_episodes")),
                decision_ts=NOW, expired=False)

        class Sender:
            async def send(self, *, chat_id, html, buttons=None):
                return 42

        async with store.connect() as conn:
            await conn.insert_market_alert(
                kind="event", alert_key="event:CPI:test", decision_ts=NOW, decision="PUSH",
                suppression_reason=None,
                payload={"at": NOW.isoformat(), "event_kind": "CPI", "event_at": (NOW + timedelta(minutes=30)).isoformat(),
                         "minutes": 30, "price": 61000.0, "stats": None, "corridor_1h": None})
        from beta.delivery import run_notify_once
        report = await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(NOW))
        assert report["sent"] == 1
        assert report["market"]["sent"] == 1
        # the morning briefing through the same outbox (kind 'brief') records brief_delivered
        async with store.connect() as conn:
            brief_pk = await conn.insert_btc_view(
                requested_at=NOW, as_of_bucket=NOW, context_state_digest=None, episodization_version=None,
                episodization_digest=None, payload={"product_status": "DATA STALE", "kind": "brief", "now": {},
                                                    "horizons": None, "market": {"complete": False}},
                payload_digest=HEX64, rendered_sha256=HEX64, rendered_html="brief", lang="en", kind="brief")
            assert await conn.materialize_brief_deliveries(brief_date=NOW.date(), view_pk=brief_pk, decision_ts=NOW) == 1
        brief_cfg = CFG.with_overrides(briefing={"enabled": True, "time_kyiv": "08:00", "max_delay_min": 120})
        report = await run_notify_once(store, brief_cfg, ON_PUSH, sender=Sender(), clock=Clock(NOW))
        assert report["briefs"]["sent"] == 1

        async def boom(self, **_kw):
            raise RuntimeError("boom")

        original = BetaConn.record_activity
        BetaConn.record_activity = boom
        try:
            with caplog.at_level(logging.WARNING):
                replied = await h.handle(_msg(uid, "/help", 36))
        finally:
            BetaConn.record_activity = original
        assert replied and "/btc" in replied[-1].html
        assert str(uid) not in caplog.text
        await h.handle(_msg(uid, "/feedback noted", 37))
        await h.handle(_cb(uid, "L:risk", 38))
        await h.handle(_cb(uid, "b:now", 39))                 # «📊 BTC сейчас» under a push
        await h.handle(_cb(uid, "x:assets", 40))              # U5 fake door
        await h.handle(_msg(uid, "/research", 41))
        await h.handle(_msg(uid, "/stop", 42))
        actions = [r["action"] for r in await _rows(pool, "SELECT action FROM beta_user_activity ORDER BY activity_pk")]
        # btn_details stays a valid historical action, but the episode Details are retired
        # (they exposed internals) and record nothing new.
        # brief_withheld (U1a) needs a withdrawal day: test_beta_invite_journey_pg covers it.
        # tab_research needs a view with research evidence: test_research_evidence.py covers it.
        assert set(actions) == set(ACTIVITY_ACTIONS) - {"btn_details", "brief_withheld", "tab_research"}
        cols = await _rows(pool, """SELECT column_name FROM information_schema.columns
                                    WHERE table_name='beta_user_activity'""")
        assert "telegram" not in " ".join(r["column_name"] for r in cols)
        stored = " ".join(str(v) for r in await _rows(pool, "SELECT * FROM beta_user_activity") for v in r.values())
        assert str(uid) not in stored

        async with store.connect() as conn:
            async with conn.transaction():
                ok = await conn.record_activity(user_pk=1, action="not-an-action", lang="en", at=NOW)
                assert await conn.conn.fetchval("SELECT 1") == 1
            assert ok is False
        health = await _rows(pool, "SELECT detail FROM beta_runtime_health WHERE component='telemetry'")
        detail = health[0]["detail"]
        if isinstance(detail, str):
            import json
            detail = json.loads(detail)
        assert detail["activity_write_failures"] == 1
        await pool.close()
    run(body())


def test_retention_purges_old_activity_and_rejected_starts():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        old = NOW - timedelta(days=121)
        recent = NOW - timedelta(days=1)
        async with store.connect() as conn:
            await conn.conn.execute(
                """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at)
                   VALUES (77, 77, 'ACTIVE', $1, $1)""", NOW)
            pk = await conn.conn.fetchval("SELECT user_pk FROM beta_users")
            await conn.conn.execute(
                "INSERT INTO beta_user_activity (user_pk, action, lang, at) VALUES ($1,'cmd_help','ru',$2),"
                "($1,'cmd_btc','ru',$3)", pk, old, recent)
            await conn.conn.execute(
                "INSERT INTO beta_rejected_start_counts (utc_day, attempt_count) VALUES ($1, 3), ($2, 1)",
                (NOW - timedelta(days=31)).date(), NOW.date())
        from beta.delivery import run_notify_once
        report = await run_notify_once(store, CFG, ON, sender=None, clock=Clock(NOW))
        assert report["purged_activity"] == 1
        assert report["purged_rejected_starts"] == 1
        left = await _rows(pool, "SELECT action FROM beta_user_activity")
        assert left == [{"action": "cmd_btc"}]
        days = await _rows(pool, "SELECT utc_day FROM beta_rejected_start_counts")
        assert days == [{"utc_day": NOW.date()}]
        await pool.close()
    run(body())


def test_existing_user_sees_the_updated_privacy_notice_once():
    async def body():
        pool = await fresh_pool()
        h = _handler(pool)
        async with pool.acquire() as c:
            await c.execute(
                """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at, lang)
                   VALUES (8675309, 8675309, 'ACTIVE', $1, $1, 'ru')""", NOW)
        first = await h.handle(_msg(8675309, "/help", 1))
        assert "конфиденциальность" in first[0].html and "120" in first[0].html
        assert "/btc" in first[1].html
        second = await h.handle(_msg(8675309, "/help", 2))
        assert len(second) == 1 and "конфиденциальность" not in second[0].html
        version = await _rows(pool, "SELECT privacy_notice_version FROM beta_users")
        assert version == [{"privacy_notice_version": 4}]
        await pool.close()
    run(body())


def test_usage_report_fixture_weeks_and_unprompted_opens():
    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        origin = datetime(2026, 5, 18, tzinfo=timezone.utc)
        now = datetime(2026, 6, 29, 12, tzinfo=timezone.utc)
        owner, a, b, c, g = 900000000001, 900000000101, 900000000102, 900000000103, 900000000105
        async with store.connect() as conn:
            await conn.conn.execute(
                """INSERT INTO beta_invites (code, label, max_uses, used_count, created_at) VALUES
                   ('alpha-code01','alpha',5,2,$1), ('beta-code001','beta',5,1,$1),
                   ('gamma-code01','gamma',5,1,$1)""", origin)
            await conn.conn.executemany(
                """INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,
                       stopped_at, lang, invite_code) VALUES ($1,$1,$2,$3,$3,$4,$5,$6)""",
                [(owner, "ACTIVE", datetime(2026, 5, 1, tzinfo=timezone.utc), None, "en", None),
                 (a, "ACTIVE", origin, None, "ru", "alpha-code01"),
                 (b, "ACTIVE", origin + timedelta(days=1), None, "en", "alpha-code01"),
                 (c, "STOPPED", origin + timedelta(days=3), datetime(2026, 5, 26, 12, tzinfo=timezone.utc),
                  "ru", "beta-code001"),
                 (g, "ACTIVE", datetime(2026, 6, 28, 18, tzinfo=timezone.utc), None, "ru", "gamma-code01")])
            ids = {r["telegram_user_id"]: r["user_pk"] for r in await conn.conn.fetch(
                "SELECT user_pk, telegram_user_id FROM beta_users")}
            rows = []

            def add(uid, action, at):
                rows.append((ids[uid], action, at))

            add(owner, "cmd_btc", datetime(2026, 6, 2, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 5, 18, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 5, 24, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 5, 31, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 2, 12, tzinfo=timezone.utc))
            add(a, "tab_event", datetime(2026, 6, 2, 13, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 3, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 4, 12, tzinfo=timezone.utc))
            add(a, "cmd_terms", datetime(2026, 6, 5, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 9, 12, tzinfo=timezone.utc))
            add(a, "push_delivered", datetime(2026, 6, 10, 10, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 10, 10, 10, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 10, 11, tzinfo=timezone.utc))
            add(a, "tab_1h", datetime(2026, 6, 14, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 23, 12, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 24, 12, tzinfo=timezone.utc))
            add(a, "tab_24h", datetime(2026, 6, 24, 13, tzinfo=timezone.utc))
            add(a, "cmd_btc", datetime(2026, 6, 25, 12, tzinfo=timezone.utc))
            add(b, "cmd_btc", datetime(2026, 5, 19, 12, tzinfo=timezone.utc))
            add(b, "cmd_btc", datetime(2026, 6, 3, 15, tzinfo=timezone.utc))
            add(b, "cmd_btc", datetime(2026, 6, 9, 15, tzinfo=timezone.utc))
            add(b, "cmd_terms", datetime(2026, 6, 26, 12, tzinfo=timezone.utc))
            add(b, "push_delivered", datetime(2026, 6, 28, 9, tzinfo=timezone.utc))
            add(b, "cmd_btc", datetime(2026, 6, 28, 9, 10, tzinfo=timezone.utc))
            add(b, "cmd_btc", datetime(2026, 6, 28, 12, tzinfo=timezone.utc))
            add(c, "cmd_stop", datetime(2026, 5, 26, 12, tzinfo=timezone.utc))
            await conn.conn.executemany(
                "INSERT INTO beta_user_activity (user_pk, action, lang, at) VALUES ($1,$2,'ru',$3)", rows)
            await conn.conn.execute(
                """INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, result, recorded_at)
                   VALUES ('user_delete_me', true, 'participant', 'OK', $1)""",
                origin + timedelta(days=10))
            await conn.conn.execute(
                """INSERT INTO beta_waitlist (telegram_user_id, requested_at) VALUES
                   (900000000201, $1), (900000000202, $1)""", origin)
            await conn.conn.execute(
                """INSERT INTO beta_rejected_start_hashes (utc_day, user_hmac) VALUES
                   ('2026-06-28', $1), ('2026-06-28', $2)""", "ab" * 32, "cd" * 32)
            await conn.conn.execute(
                "INSERT INTO beta_rejected_start_counts (utc_day, attempt_count) VALUES ('2026-06-27', 4)")
        h = _handler(pool, when=now)
        out = await h.handle(_msg(owner, "/admin_stats", 1))
        text = out[0].html.replace("<pre>", "").replace("</pre>", "")
        assert "week 3 active: 2" in text
        assert "week 4 active: 2" in text
        assert "weeks 3-4 both active: 2" in text
        both = {fingerprint(a), fingerprint(b)}
        assert both <= set(text.split())
        assert "unprompted /btc: 4" in text and "post-push /btc: 1" in text
        assert "median 2.5 max 3" in text
        assert "retention: d1 2/3 · d7 1/3 · d14 1/3 · d28 1/3" in text
        assert "language: ru 3, en 1" in text
        assert "waitlist: 2" in text
        assert "rejected 2026-06-28 distinct 2" in text
        assert "rejected 2026-06-27 unsalted 4" in text
        assert "alpha: joins 2, active 2" in text
        assert "gamma: joins 1, active 0" in text
        for raw in (owner, a, b, c, g, 900000000201):
            assert str(raw) not in text
        audit = await _rows(pool, "SELECT detail::text AS detail FROM beta_admin_audit WHERE action='admin_stats'")
        for raw in (owner, a, b, c, g):
            assert str(raw) not in audit[0]["detail"]

        from storage.db import Database
        import main
        from runtime.beta_cli import run_beta_cli_command
        db = Database(TEST_DSN)
        await db.connect()
        try:
            rep = await run_beta_cli_command(
                main.parse_args(["--beta-usage-report", "--beta-json"]), db=db,
                env={"BETA_OWNER_TELEGRAM_USER_ID": str(owner)}, clock=Clock(now))
        finally:
            await db.close()
        usage = rep["usage"]
        assert usage["since_first_external"]["weeks_3_and_4_active"] == 2
        assert usage["last_7_days"]["unprompted_btc"] == 4
        assert usage["last_7_days"]["post_push_btc"] == 1
        assert usage["since_first_external"]["unprompted_btc"] == 15
        assert usage["since_first_external"]["post_push_btc"] == 2
        assert format_usage_report(usage) == text
        import os
        os.makedirs("/opt/cursor/artifacts", exist_ok=True)
        with open("/opt/cursor/artifacts/admin_stats.txt", "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        await pool.close()
    run(body())
