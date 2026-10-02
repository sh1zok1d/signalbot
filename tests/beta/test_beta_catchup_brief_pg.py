"""/catchup, /brief and the morning briefing on real PostgreSQL ($BETA_TEST_DSN).

The briefing goes through the existing notifier and outbox (kind 'brief'); push
rows, push decisions and the push loop are not touched."""
from datetime import timedelta

import pytest

from beta_fakes import CFG, ON, ON_PUSH, Clock, ScenarioReader, TEST_DSN, down_move, quiet, run
from test_beta_pg_integration import B0, BUCKET, OWNER, ALICE, FakeSender, _cb, _detect, _msg, _rows, _setup
from storage.beta_v0_store import BetaStore

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")


@pytest.fixture(autouse=True)
def _calc():
    import test_beta_pg_integration as pgi
    pgi.CALC = pgi.calc_version()       # the shared _setup seeds history under this version
BRIEF_ON = CFG.with_overrides(briefing={"enabled": True, "time_kyiv": "08:00", "max_delay_min": 120})
# B0 is 2026-04-10 00:00 UTC (EEST, UTC+3): the 08:00 Kyiv slot is 05:00 UTC.
SLOT = B0 + timedelta(hours=5)


async def _joined(pool, now, cfg=CFG):
    from runtime.beta_bot import BetaBotHandler
    h = BetaBotHandler(BetaStore(pool), cfg, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(now))
    await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 1))
    await h.handle(_msg(ALICE, "/start", 2))
    await h.handle(_cb(ALICE, "pick:en", 3))
    await h.handle(_cb(ALICE, "join:en", 4))
    return h


def test_catchup_renders_the_shared_view_and_records_it():
    async def body():
        pool = await _setup()
        for i, sc in enumerate([down_move, down_move, quiet]):
            await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        h = await _joined(pool, B0 + 3 * BUCKET + timedelta(seconds=30))
        out = await h.handle(_msg(ALICE, "/catchup", 5))
        text = out[0].html
        assert "BTC" in text and "last 8h" in text
        assert "Events: sharp drop" in text                           # the triggered episode in the window
        assert "1h: " in text and "4h: " in text                       # interpretation lines
        assert "data 03:15 Kyiv" in text
        assert "trade" not in text.lower() and "next" not in text.lower()
        views = await _rows(pool, "SELECT kind, lang, payload->>'kind' AS pk FROM beta_btc_views ORDER BY view_pk")
        assert views[-1] == {"kind": "catchup", "lang": "en", "pk": "catchup"}
        out = await h.handle(_msg(ALICE, "/catchup 3", 6))
        assert "last 3h" in out[0].html
        out = await h.handle(_msg(ALICE, "/catchup 25", 7))
        assert out[0].html.startswith("Usage: /catchup")
        await h.handle(_msg(ALICE, "/btc", 8))
        kinds = [r["kind"] for r in await _rows(pool, "SELECT kind FROM beta_btc_views ORDER BY view_pk")]
        assert kinds == ["catchup", "catchup", "btc"]                 # /btc keeps its own kind
        import json
        from test_beta_btc_view import VIEW_KEYS
        btc_payload = json.loads((await _rows(pool, "SELECT payload FROM beta_btc_views WHERE kind='btc'"))[0]["payload"])
        assert set(btc_payload) == VIEW_KEYS                           # /btc payload keys unchanged
        acts = [r["action"] for r in await _rows(pool, "SELECT action FROM beta_user_activity ORDER BY activity_pk")]
        assert acts.count("cmd_catchup") == 2                          # usage replies are not activity
        await pool.close()
    run(body())


def test_brief_command_turns_the_morning_summary_on_and_off():
    async def body():
        pool = await _setup()
        h = await _joined(pool, B0)
        out = await h.handle(_msg(ALICE, "/brief", 5))
        assert "Morning summary: on" in out[0].html
        out = await h.handle(_msg(ALICE, "/brief off", 6))
        assert "Morning summary off" in out[0].html and "Event pushes are not affected" in out[0].html
        assert (await _rows(pool, "SELECT brief_enabled FROM beta_users"))[0]["brief_enabled"] is False
        await h.handle(_msg(ALICE, "/brief on", 7))
        assert (await _rows(pool, "SELECT brief_enabled FROM beta_users"))[0]["brief_enabled"] is True
        acts = [r["action"] for r in await _rows(pool, "SELECT action FROM beta_user_activity")]
        assert acts.count("cmd_brief") == 3
        await pool.close()
    run(body())


async def _users(pool):
    async with pool.acquire() as c:
        await c.execute(
            "INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
            " stopped_at, lang, brief_enabled) VALUES"
            " (21, 21, 'ACTIVE', now(), now(), NULL, 'en', TRUE),"
            " (22, 22, 'ACTIVE', now(), now(), NULL, 'ru', FALSE),"
            " (23, 23, 'STOPPED', now(), now(), now(), 'en', TRUE)")


def test_brief_is_sent_once_per_day_through_the_outbox_and_never_touches_pushes():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _detect(pool, ScenarioReader(quiet), B0)
        await _users(pool)
        s = FakeSender()
        before = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(SLOT - timedelta(minutes=1)))
        assert before["briefs"]["scheduled"] == 0 and s.sent == []
        r = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(SLOT + timedelta(minutes=1)))
        assert r["briefs"] == {"scheduled": 1, "sent": 1, "failed": 0, "unknown": 0, "expired": 0, "suppressed": 0}
        assert len(s.sent) == 1 and s.sent[0][0] == 21 and "Morning · BTC" in s.sent[0][1]
        again = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(SLOT + timedelta(minutes=30)))
        assert again["briefs"]["scheduled"] == 0 and len(s.sent) == 1        # once per day, never re-sent
        rows = await _rows(pool, "SELECT kind, state, decision_id, episode_pk, brief_date::text AS d "
                                 "FROM beta_notification_deliveries")
        assert rows == [{"kind": "brief", "state": "SENT", "decision_id": None, "episode_pk": None,
                         "d": "2026-04-10"}]
        assert r["sent"] == 0 and r["materialized"] == 0                    # the push loop saw nothing
        async with BetaStore(pool).connect() as conn:
            assert await conn.delivery_state_counts() == {}                 # push metrics exclude briefs
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_push_decisions WHERE decision='PUSH'"))[0]["n"] == 0
        views = await _rows(pool, "SELECT kind FROM beta_btc_views")
        assert views == [{"kind": "brief"}]
        acts = await _rows(pool, "SELECT action FROM beta_user_activity")
        assert acts == [{"action": "brief_delivered"}]
        await pool.close()
    run(body())


def test_brief_off_by_config_or_push_switch_and_never_late():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _detect(pool, ScenarioReader(quiet), B0)
        await _users(pool)
        s = FakeSender()
        assert (await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s,
                                      clock=Clock(SLOT + timedelta(minutes=1))))["briefs"]["scheduled"] == 0
        assert (await run_notify_once(BetaStore(pool), BRIEF_ON, ON, sender=s,
                                      clock=Clock(SLOT + timedelta(minutes=1))))["briefs"]["scheduled"] == 0
        late = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s,
                                     clock=Clock(SLOT + timedelta(minutes=121)))
        assert late["briefs"]["scheduled"] == 0 and s.sent == []
        # a row that missed its slot (e.g. a notifier outage) expires instead of arriving late
        async with BetaStore(pool).connect() as conn:
            vpk = await conn.insert_btc_view(requested_at=SLOT, as_of_bucket=None, context_state_digest=None,
                                             episodization_version=None, episodization_digest=None,
                                             payload={"kind": "brief"}, payload_digest="a" * 64,
                                             rendered_sha256="b" * 64, rendered_html="x", lang="ru", kind="brief")
            assert await conn.materialize_brief_deliveries(brief_date=SLOT.date(), view_pk=vpk, decision_ts=SLOT) == 1
        r = await run_notify_once(BetaStore(pool), BRIEF_ON, ON_PUSH, sender=s, clock=Clock(SLOT + timedelta(hours=3)))
        assert r["briefs"]["expired"] == 1 and s.sent == []
        await pool.close()
    run(body())


def test_context_dry_run_reads_the_recorded_tape_read_only():
    async def body():
        from beta.dry_run import run_dry_run_from_db
        from common.stage2_config import Stage2Config
        pool = await _setup()
        for i, sc in enumerate([down_move, down_move, quiet]):
            await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        before = await _rows(pool, "SELECT (SELECT count(*) FROM beta_state_tape) AS t,"
                                   " (SELECT count(*) FROM beta_context_snapshots) AS c")
        async with BetaStore(pool).connect() as conn:
            rep = await run_dry_run_from_db(conn, CFG, Stage2Config.load(), end=B0 + 3 * BUCKET, days=1,
                                            stride_buckets=1, ignore_maturity=True)
        assert rep["status"] == "PROVISIONAL_RANKS_IGNORE_MATURITY" and rep["samples"] >= 1
        assert rep["tape_rows"] > 0 and rep["liquidation_episodes"] == 0
        after = await _rows(pool, "SELECT (SELECT count(*) FROM beta_state_tape) AS t,"
                                  " (SELECT count(*) FROM beta_context_snapshots) AS c")
        assert before == after                                       # nothing written
        await pool.close()
    run(body())
