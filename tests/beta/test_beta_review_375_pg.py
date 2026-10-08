"""The external review of #375 (package 5) on real PostgreSQL ($BETA_TEST_DSN): a vote counts only on a
message its voter received, the votes leave with /delete_me and with the retention purge, the briefing
and the weekly report carry their vote row, and the weekly owner copy reads a one-tap mute as the setting
it is."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, ON_PUSH, TEST_DSN, Clock, fresh_pool, run
from storage.beta_v0_store import BetaStore
from test_beta_v2_pg import Sender, _handler, _join, _rows
from test_beta_weekly_pg import OWNER, SLOT, _forecasts

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

A, B, C = 900000000301, 900000000302, 900000000303
HEX64 = "ab" * 32


def _cb(uid, data, k):
    return {"update_id": k, "callback_query": {"id": f"c{k}", "from": {"id": uid},
                                                "message": {"chat": {"id": uid}, "message_id": 1}, "data": data}}


def _msg(uid, text, k):
    return {"update_id": k, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"}, "text": text}}


def test_votes_only_on_received_messages_and_they_leave_with_the_participant():
    from beta.delivery import run_notify_once
    now = SLOT - timedelta(days=2)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, OWNER, Clock(now - timedelta(hours=1)))
        async with store.connect() as conn:
            for uid in (A, B, C):
                await conn.allowlist_add(uid)
        for i, uid in enumerate((A, C)):
            await _join(h, uid, 10 + 10 * i)
            await h.handle(_msg(uid, "/brief on", 15 + 10 * i))
        async with store.connect() as conn:
            brief_pk = await conn.insert_btc_view(
                requested_at=now, as_of_bucket=now, context_state_digest=None, episodization_version=None,
                episodization_digest=None, payload={"product_status": "DATA STALE", "kind": "brief", "now": {},
                                                    "horizons": None, "market": {"complete": False}},
                payload_digest=HEX64, rendered_sha256=HEX64, rendered_html="brief", lang="ru", kind="brief")
            assert await conn.materialize_brief_deliveries(brief_date=now.date(), view_pk=brief_pk, decision_ts=now) == 2
        sender = Sender()
        brief_cfg = CFG.with_overrides(briefing={"enabled": True, "time_kyiv": "08:00", "max_delay_min": 120})
        assert (await run_notify_once(store, brief_cfg, ON_PUSH, sender=sender, clock=Clock(now)))["briefs"]["sent"] == 2
        # the briefing carries its vote row (review of #375: never tested)
        for chat, _html, buttons in sender.sent:
            assert (chat in (A, C)) and f"v:brief:{brief_pk}:u" in [d for row in buttons or () for _l, d in row]
        # B joined later and never received it: their vote is refused and stored nowhere
        await _join(h, B, 40)
        out = await h.handle(_cb(B, f"v:brief:{brief_pk}:n", 50))
        assert out and await _rows(pool, "SELECT count(*) AS n FROM beta_message_votes") == [{"n": 0}]
        await h.handle(_cb(A, f"v:brief:{brief_pk}:u", 51))
        await h.handle(_cb(C, f"v:brief:{brief_pk}:n", 52))
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_message_votes") == [{"n": 2}]
        # /delete_me takes C's vote with the rest of C's data
        await h.handle(_msg(C, "/delete_me", 53))
        assert await _rows(pool, "SELECT vote FROM beta_message_votes") == [{"vote": "USEFUL"}]
        # the retention purge of a long-stopped participant deletes the row itself, so the vote goes too
        async with pool.acquire() as c:
            await c.execute("UPDATE beta_users SET status='STOPPED', stopped_at=$2 WHERE telegram_user_id=$1",
                            A, now - timedelta(days=CFG["privacy"]["stopped_user_retention_days"] + 1))
        report = await run_notify_once(store, CFG, ON_PUSH, sender=Sender(), clock=Clock(now + timedelta(minutes=5)))
        assert report["purged_users"] == 1
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_users WHERE telegram_user_id=$1", A) == [{"n": 0}]
        assert await _rows(pool, "SELECT count(*) AS n FROM beta_message_votes") == [{"n": 0}]
        await pool.close()
    run(body())


def test_the_weekly_owner_copy_reads_a_one_tap_mute_as_the_setting_and_the_report_has_its_vote_row(monkeypatch):
    """#375 review, item 2: a one-tap mute was invisible to the weekly owner copy (raw activity)."""
    import beta.usage as usage
    from beta.delivery import run_notify_once
    seen = []
    real = usage.owner_breakdown

    def spy(users, activity, votes, **kw):
        seen.extend(activity)
        return real(users, activity, votes, **kw)
    monkeypatch.setattr(usage, "owner_breakdown", spy)

    async def body():
        pool = await fresh_pool()
        store = BetaStore(pool)
        h = _handler(pool, OWNER, Clock(SLOT - timedelta(days=3)))
        async with store.connect() as conn:
            await conn.allowlist_add(A)
        await _join(h, A, 10)
        await h.handle(_cb(A, "m:levels", 20))                    # «🔕 Не присылать такие» under a level alert
        await _forecasts(pool)
        sender = Sender()
        r = await run_notify_once(store, CFG, ON_PUSH, sender=sender, clock=Clock(SLOT + timedelta(minutes=5)),
                                  owner_user_id=OWNER)
        assert r["weekly"]["sent"] == 1 and r["weekly"]["owner"] == "sent"
        assert [(x["action"], x.get("detail")) for x in seen if x["action"] in ("cmd_push", "set_mute")] == [
            ("cmd_push", "levels:off")]
        weekly = [buttons for chat, html, buttons in sender.sent if chat == A]
        assert weekly and any(d.startswith("v:weekly:") for row in weekly[-1] for _l, d in row)
        await pool.close()
    run(body())
