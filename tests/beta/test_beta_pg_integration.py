"""Beta V0.2 PostgreSQL integration (real local PostgreSQL named by $BETA_TEST_DSN;
skipped when unset). The Stage-2 feature/consensus/percentile math runs unchanged
through ScenarioReader fakes. No network, no exchange call, no Telegram."""
import asyncio
import random
from datetime import timedelta

import pytest

from beta_fakes import (CFG, EXS, FEATURE_CODE, ON, ON_PUSH, S2, T0, TEST_DSN, Clock, ScenarioReader,
                        deps, down_move, fresh_pool, history_buckets, history_metrics, quiet, run,
                        seed_history, seed_live_klines)
from beta.detector import run_bootstrap_once, run_detector_once
from beta.state_tape import materialize_bucket
from storage.beta_v0_store import BetaStore, apply_beta_schema

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

B0 = T0 + timedelta(days=40)
BUCKET = timedelta(minutes=5)


_CALC = []


def calc_version() -> str:
    """The Stage-2 calculation_version the fake reader's materialization yields."""
    if not _CALC:
        r = run(materialize_bucket(ScenarioReader(quiet), S2, CFG, bucket_ts=B0, code_version=FEATURE_CODE,
                                   liquidation_feed_available_by_exchange={e: True for e in EXS}))
        _CALC.append(r.consensus_feature.calculation_version)
    return _CALC[0]


@pytest.fixture(autouse=True)
def _calc():
    global CALC
    CALC = calc_version()      # computed outside any running event loop


CALC = None


async def _setup(n_eval=8, live=True):
    pool = await fresh_pool()
    rng = random.Random(7)
    await seed_history(pool, calculation_version=CALC, buckets=history_buckets(B0, n_eval),
                       metrics_fn=lambda b: history_metrics(rng))
    if live:
        await seed_live_klines(pool, [B0 + i * BUCKET for i in range(n_eval + 300)])
    return pool


async def _detect(pool, reader, bucket, *, switches=ON, cfg=CFG, **kw):
    clock = Clock(bucket + BUCKET + timedelta(seconds=30))
    return await run_detector_once(deps(pool, reader, clock, **kw), cfg, switches)


async def _rows(pool, sql, *args):
    async with pool.acquire() as c:
        return [dict(r) for r in await c.fetch(sql, *args)]


# --------------------------------------------------------------------------- schema
def test_schema_is_idempotent_and_append_only():
    async def body():
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await apply_beta_schema(c)          # second apply is a no-op
        await seed_history(pool, calculation_version=CALC, buckets=[B0], metrics_fn=lambda b: {})
        import asyncpg
        for sql in ("UPDATE beta_state_tape SET origin='LIVE'", "DELETE FROM beta_state_tape"):
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                async with pool.acquire() as c:
                    await c.execute(sql)
        async with pool.acquire() as c:
            await c.execute("INSERT INTO beta_admin_audit (action, authorized, actor_fingerprint, result) "
                            "VALUES ('admin_status', true, 'x', 'OK')")
            with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
                await c.execute("DELETE FROM beta_admin_audit")
        await pool.close()
    run(body())


def test_one_open_episode_per_event_type_under_concurrency():
    async def body():
        import asyncpg
        pool = await fresh_pool()
        sql = """INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket, opened_at,
                     armed_at, rules_version, rules_digest, code_version, calculation_version,
                     opening_tape_digest, last_bucket, last_streak)
                 VALUES ($1,'BTCUSDT',$2,'ARMED',$3,$3,$3,'BETA_EVENT_RULES_V1',repeat('a',64),'c',
                         repeat('0',16),repeat('b',64),$3,1)"""

        async def ins(pid, et):
            async with pool.acquire() as c:
                await c.execute(sql, pid, et, B0)
        res = await asyncio.gather(ins("EV-000000000A", "PRICE_OI_CONTRACTION_DOWN"),
                                   ins("EV-000000000B", "PRICE_OI_CONTRACTION_DOWN"),
                                   ins("EV-000000000C", "PRICE_OI_CONTRACTION_UP"), return_exceptions=True)
        errors = [r for r in res if isinstance(r, Exception)]
        assert len(errors) == 1 and isinstance(errors[0], asyncpg.exceptions.UniqueViolationError)
        rows = await _rows(pool, "SELECT event_type FROM beta_episodes ORDER BY 1")
        assert [r["event_type"] for r in rows] == ["PRICE_OI_CONTRACTION_DOWN", "PRICE_OI_CONTRACTION_UP"]
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- detector
def test_detector_end_to_end_tape_episode_push_decision():
    async def body():
        pool = await _setup()
        reader = ScenarioReader(down_move)
        r1 = await _detect(pool, reader, B0)
        assert r1["processed"][0]["evaluations"]["PRICE_OI_CONTRACTION_DOWN"] == "QUALIFIES"
        r2 = await _detect(pool, reader, B0 + BUCKET)
        tr = r2["processed"][0]["transitions"]
        assert [(t[1], t[2]) for t in tr] == [("ARMED", "TRIGGERED")]
        assert r2["processed"][0]["push_decisions"][0][1:] == ("SUPPRESSED", "PUSH_DISABLED")
        tape = await _rows(pool, "SELECT bucket_ts, origin, materialized, evaluation_fresh, snapshot "
                                 "FROM beta_state_tape WHERE origin='LIVE' ORDER BY bucket_ts")
        assert [t["bucket_ts"] for t in tape] == [B0, B0 + BUCKET]
        assert all(t["materialized"] and t["evaluation_fresh"] for t in tape)
        ep = (await _rows(pool, "SELECT * FROM beta_episodes"))[0]
        assert ep["state"] == "TRIGGERED" and ep["reference_price"] == pytest.approx(98.0)
        assert ep["trigger_tape_digest"] != ep["opening_tape_digest"]
        pd = await _rows(pool, "SELECT would_push, decision, suppression_reason FROM beta_push_decisions")
        assert pd == [{"would_push": True, "decision": "SUPPRESSED", "suppression_reason": "PUSH_DISABLED"}]
        # a quiet next bucket ends it
        r3 = await _detect(pool, ScenarioReader(quiet), B0 + 2 * BUCKET)
        assert [(t[1], t[2], t[3]) for t in r3["processed"][0]["transitions"]] == \
            [("TRIGGERED", "ENDED", "CONDITION_FAILED")]
        seqs = await _rows(pool, "SELECT seq, from_state, to_state FROM beta_episode_transitions ORDER BY seq")
        assert [(s["from_state"], s["to_state"]) for s in seqs] == [(None, "ARMED"), ("ARMED", "TRIGGERED"),
                                                                    ("TRIGGERED", "ENDED")]
        assert "telegram" not in str(tape).lower()
        await pool.close()
    run(body())


def test_restart_idempotency_and_crash_mid_bucket_leaves_nothing():
    async def body():
        pool = await _setup()
        reader = ScenarioReader(down_move)
        await _detect(pool, reader, B0)
        again = await _detect(pool, reader, B0)          # same clock: watermark says done
        assert again["processed"] == []
        # crash inside the bucket transaction (after tape + transition writes)
        from storage import beta_v0_store as st
        orig = st.BetaConn.insert_push_decision

        async def boom(self, **kw):
            raise RuntimeError("crash")
        st.BetaConn.insert_push_decision = boom
        try:
            with pytest.raises(RuntimeError):
                await _detect(pool, reader, B0 + BUCKET)
        finally:
            st.BetaConn.insert_push_decision = orig
        n = await _rows(pool, "SELECT count(*) AS n FROM beta_state_tape WHERE origin='LIVE'")
        assert n[0]["n"] == 1                               # rolled back entirely
        await _detect(pool, reader, B0 + BUCKET)            # rerun after "restart"
        eps = await _rows(pool, "SELECT state FROM beta_episodes")
        assert eps == [{"state": "TRIGGERED"}]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_push_decisions"))[0]["n"] == 1
        await pool.close()
    run(body())


def test_correction_appends_revision_and_never_rewrites_decision():
    async def body():
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET)
        before_ep = await _rows(pool, "SELECT state, armed_at, triggered_at, opening_tape_digest, "
                                      "trigger_tape_digest FROM beta_episodes")
        before_tr = await _rows(pool, "SELECT * FROM beta_episode_transitions ORDER BY seq")
        corrected = ScenarioReader(lambda b: {ex: {"price_move": -2.5, "oi_change": -3.0} for ex in EXS})
        clock = Clock(B0 + 3 * BUCKET)
        res = await run_detector_once(deps(pool, corrected, clock), CFG, ON, explicit_bucket=B0)
        assert res["status"] == "CORRECTION_APPENDED" and res["revision"] == 2 and res["episodes_flagged"] == 1
        after_ep = await _rows(pool, "SELECT state, armed_at, triggered_at, opening_tape_digest, "
                                     "trigger_tape_digest FROM beta_episodes")
        assert after_ep == before_ep
        assert await _rows(pool, "SELECT * FROM beta_episode_transitions ORDER BY seq") == before_tr
        flag = await _rows(pool, "SELECT correction_flag, correction_note FROM beta_episodes")
        assert flag[0]["correction_flag"] is True and "revision 2" in flag[0]["correction_note"]
        chain = await _rows(pool, "SELECT origin, revision, supersedes_tape_id FROM beta_state_tape "
                                  "WHERE bucket_ts=$1 AND origin <> 'BOOTSTRAP' ORDER BY tape_id", B0)
        assert [(c["origin"], c["revision"]) for c in chain] == [("LIVE", 1), ("CORRECTION_CHECK", 2)]
        same = await run_detector_once(deps(pool, corrected, clock), CFG, ON, explicit_bucket=B0)
        assert same["status"] == "UNCHANGED"
        await pool.close()
    run(body())


def test_version_change_mid_episode_terminalizes_and_suppresses_push():
    async def body():
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0)
        cfg2 = CFG.with_overrides(max_state_age_s=421)       # new rules digest
        r = await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, cfg=cfg2)
        t = r["processed"][0]["transitions"]
        assert t[0][1:] == ("ARMED", "EXPIRED", "DETECTOR_VERSION_CHANGED")
        # the new rules chain re-arms in the same bucket (fresh episode, new public id) ...
        assert t[1][1:] == (None, "ARMED", "CONDITION_MET") and t[1][0] != t[0][0]
        # ... and triggers next bucket — push suppressed by the same-event cooldown
        r = await _detect(pool, ScenarioReader(down_move), B0 + 2 * BUCKET, cfg=cfg2)
        pd = r["processed"][0]["push_decisions"]
        assert pd and pd[0][2] == "SAME_EVENT_COOLDOWN"
        await pool.close()
    run(body())


def test_liquidation_not_evaluable_without_live_heartbeat_and_triggers_with_it():
    async def body():
        pool = await _setup(live=False)
        liq = ScenarioReader(lambda b: {ex: {"liq_long": 5000.0} for ex in EXS})
        r = await _detect(pool, liq, B0)
        assert r["processed"][0]["evaluations"]["LIQUIDATION_STRESS_LONG"] == "NOT_EVALUABLE"
        snap = (await _rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE'"))[0]["snapshot"]
        assert '"x:binance:long_liquidation_notional": null' in snap
        await seed_live_klines(pool, [B0 + BUCKET])
        r = await _detect(pool, liq, B0 + BUCKET)
        assert r["processed"][0]["evaluations"]["LIQUIDATION_STRESS_LONG"] == "QUALIFIES"
        assert r["processed"][0]["transitions"][0][1:] == (None, "TRIGGERED", "CONDITION_MET")
        await pool.close()
    run(body())


def test_one_venue_bad_print_cannot_trigger_cross_venue_event():
    async def body():
        pool = await _setup()
        bad = ScenarioReader(lambda b: {"binance": {"price_move": -9.0, "oi_change": -9.0,
                                                    "liq_long": 99999.0}})
        r = await _detect(pool, bad, B0)
        ev = r["processed"][0]["evaluations"]
        assert ev["PRICE_OI_CONTRACTION_DOWN"] != "QUALIFIES" and ev["LIQUIDATION_STRESS_LONG"] != "QUALIFIES"
        await pool.close()
    run(body())


def test_daily_cap_suppression_is_logged():
    async def body():
        pool = await _setup()
        store = BetaStore(pool)
        day = (B0 + BUCKET + BUCKET).date()
        async with store.connect() as c:
            for i, et in enumerate(("LIQUIDATION_STRESS_LONG", "LIQUIDATION_STRESS_SHORT", "TAKER_FLOW_EXTREME_BUY")):
                pk = await c.conn.fetchval(
                    """INSERT INTO beta_episodes (public_id, symbol, event_type, state, opened_bucket, opened_at,
                           triggered_at, terminal_at, terminal_reason, rules_version, rules_digest, code_version,
                           calculation_version, opening_tape_digest, trigger_tape_digest, last_bucket, last_streak)
                       VALUES ($1,'BTCUSDT',$2,'ENDED',$3,$3,$3,$3,'CONDITION_FAILED','BETA_EVENT_RULES_V1',
                               repeat('a',64),'c',repeat('0',16),repeat('b',64),repeat('b',64),$3,1)
                       RETURNING episode_pk""", f"EV-00000000{i}F", et, B0 - timedelta(hours=1))
                await c.insert_push_decision(episode_pk=pk, event_type=et, decision_ts=B0 + timedelta(minutes=1 + i),
                                             would_push=True, decision="PUSH", suppression_reason=None,
                                             push_enabled_effective=True)
        assert B0.date() == day
        await _detect(pool, ScenarioReader(down_move), B0)
        r = await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, switches=ON_PUSH)
        assert r["processed"][0]["push_decisions"][0][1:] == ("SUPPRESSED", "DAILY_CAP")
        rows = await _rows(pool, "SELECT suppression_reason FROM beta_push_decisions WHERE decision='SUPPRESSED'")
        assert rows == [{"suppression_reason": "DAILY_CAP"}]
        await pool.close()
    run(body())


def test_bootstrap_bounded_resumable_oldest_first_and_detector_disabled_switch():
    async def body():
        pool = await fresh_pool()
        cfg = CFG.with_overrides(bootstrap={"lookback_days": 1, "max_buckets_per_run": 100})
        now = B0 + timedelta(seconds=30)
        d = deps(pool, ScenarioReader(quiet), Clock(now))
        r1 = await run_bootstrap_once(d, cfg, ON)
        assert r1["written"] == 100 and r1["complete"] is False
        r2 = await run_bootstrap_once(d, cfg, ON)
        r3 = await run_bootstrap_once(d, cfg, ON)
        assert r3["complete"] is True and r1["written"] + r2["written"] + r3["written"] == 24 * 12 + 1
        rows = await _rows(pool, "SELECT count(*) AS n, count(DISTINCT bucket_ts) AS d FROM beta_state_tape")
        assert rows[0]["n"] == rows[0]["d"] == 289
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_episodes"))[0]["n"] == 0
        r4 = await run_bootstrap_once(d, cfg, ON)
        assert r4["written"] == 0
        off = await run_detector_once(d, cfg, ON.__class__(True, False, False, True))
        assert off["status"] == "DISABLED"
        await pool.close()
    run(body())


def test_status_stale_never_no_active_events():
    async def body():
        from beta.admin import collect_status
        pool = await _setup()
        await _detect(pool, ScenarioReader(quiet), B0)
        async with BetaStore(pool).connect() as c:
            fresh = await collect_status(c, CFG, B0 + BUCKET + timedelta(seconds=40))
            stale = await collect_status(c, CFG, B0 + timedelta(hours=1))
        assert fresh["status"]["status"] == "NO ACTIVE EVENTS"
        assert stale["status"]["status"] == "DATA STALE"
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- outcomes
def test_outcomes_never_early_complete_then_superseded():
    async def body():
        from beta.outcomes import run_outcomes_once
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET)
        trig = B0 + 2 * BUCKET
        store = BetaStore(pool)

        async def rev():
            return 0
        cfg = CFG.with_overrides(forward_horizons=["15m"])
        early = await run_outcomes_once(store, cfg, ON, clock=Clock(trig + timedelta(minutes=16)), raw_revision=rev)
        assert early["written"] == [] and early["not_due"] == 1
        done = await run_outcomes_once(store, cfg, ON, clock=Clock(trig + timedelta(minutes=18)), raw_revision=rev)
        assert done["written"][0][2] == "COMPLETE"
        async with pool.acquire() as c:
            await c.execute("UPDATE klines_1m SET high = high * 1.05 WHERE ts=$1", trig + timedelta(minutes=3))
        again = await run_outcomes_once(store, cfg, ON, clock=Clock(trig + timedelta(minutes=30)), raw_revision=rev)
        assert again["superseded"] and again["superseded"][0][2] == 2
        rows = await _rows(pool, "SELECT revision, supersedes_outcome_id, max_up_pct FROM beta_episode_outcomes "
                                 "ORDER BY revision")
        assert [r["revision"] for r in rows] == [1, 2] and rows[1]["supersedes_outcome_id"] is not None
        assert rows[1]["max_up_pct"] > rows[0]["max_up_pct"]
        await pool.close()
    run(body())


def test_outcomes_incomplete_bars_wait_then_explicit_incomplete():
    async def body():
        from beta.outcomes import run_outcomes_once
        pool = await _setup(n_eval=2, live=False)
        await seed_live_klines(pool, [B0, B0 + BUCKET])          # no bars after trigger
        await _detect(pool, ScenarioReader(down_move), B0)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET)
        trig = B0 + 2 * BUCKET
        cfg = CFG.with_overrides(forward_horizons=["15m"])

        async def rev():
            return 0
        store = BetaStore(pool)
        r = await run_outcomes_once(store, cfg, ON, clock=Clock(trig + timedelta(hours=1)), raw_revision=rev)
        assert r["written"] == [] and r["pending_incomplete"] == 1
        r = await run_outcomes_once(store, cfg, ON, clock=Clock(trig + timedelta(hours=49)), raw_revision=rev)
        assert r["written"][0][2] == "INCOMPLETE_DATA"
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- delivery
class FakeSender:
    def __init__(self, mode="ok"):
        self.mode, self.sent = mode, []

    async def send(self, *, chat_id, html, buttons=None):
        from beta.delivery import DeliveryAmbiguous, DeliveryRejected
        self.sent.append((chat_id, html, buttons))
        if self.mode == "reject":
            raise DeliveryRejected("Forbidden: bot was blocked")
        if self.mode == "ambiguous":
            raise DeliveryAmbiguous("TimedOut")
        return 1000 + len(self.sent)


async def _triggered_push(pool):
    await _detect(pool, ScenarioReader(down_move), B0, switches=ON_PUSH)
    await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, switches=ON_PUSH)
    async with pool.acquire() as c:
        await c.execute("INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
                        " stopped_at) VALUES (11, 11, 'ACTIVE', now(), now(), NULL), (12, 12, 'STOPPED', now(), now(), now())")


def test_delivery_sent_once_ttl_and_user_inactive():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        decision_ts = B0 + 2 * BUCKET
        s = FakeSender()
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(decision_ts + timedelta(seconds=40)))
        assert r["sent"] == 1 and r["materialized"] == 2 and len(s.sent) == 1
        assert "Decision time" in s.sent[0][1] and s.sent[0][2][0][0][0] == "Details"
        again = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(decision_ts + timedelta(seconds=100)))
        assert again["sent"] == 0 and len(s.sent) == 1              # never re-sent
        states = await _rows(pool, "SELECT state, suppression_reason FROM beta_notification_deliveries ORDER BY delivery_id")
        assert {(x["state"], x["suppression_reason"]) for x in states} == {("SENT", None), ("SUPPRESSED", "USER_INACTIVE")}
        await pool.close()
    run(body())


def test_delivery_ttl_expired_is_never_pushed_late():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        s = FakeSender()
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s,
                                  clock=Clock(B0 + 2 * BUCKET + timedelta(seconds=601)))
        assert s.sent == [] and r["sent"] == 0
        states = await _rows(pool, "SELECT state, suppression_reason FROM beta_notification_deliveries")
        assert ("EXPIRED_UNDELIVERED", "DELIVERY_TOO_OLD") in {(x["state"], x["suppression_reason"]) for x in states}
        await pool.close()
    run(body())


def test_sending_recovery_is_delivery_unknown_without_resend_and_rejection_is_failed():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        now = B0 + 2 * BUCKET + timedelta(seconds=40)
        store = BetaStore(pool)
        async with store.connect() as c:
            for d in await c.fetch_undispatched_push_decisions(10):
                await c.materialize_deliveries(decision_id=d["decision_id"], episode_pk=d["episode_pk"],
                                               decision_ts=d["decision_ts"], expired=False)
            pend = await c.fetch_pending_deliveries(10)
            assert await c.transition_delivery(pend[0]["delivery_id"], from_state="PENDING", to_state="SENDING", now=now)
        s = FakeSender()                               # "process crashed" while SENDING
        r = await run_notify_once(store, CFG, ON_PUSH, sender=s, clock=Clock(now + timedelta(seconds=30)))
        assert r["recovered_unknown"] == 1 and s.sent == []
        st = await _rows(pool, "SELECT state FROM beta_notification_deliveries WHERE user_pk IS NOT NULL "
                               "AND suppression_reason IS NULL")
        assert st == [{"state": "DELIVERY_UNKNOWN"}]
        await pool.close()

        pool = await _setup()
        await _triggered_push(pool)
        s = FakeSender("reject")
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now))
        assert r["failed"] == 1 and len(s.sent) == 1
        await pool.close()

        pool = await _setup()
        await _triggered_push(pool)
        s = FakeSender("ambiguous")
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now))
        assert r["unknown"] == 1
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(now + timedelta(seconds=30)))
        assert len(s.sent) == 1                        # ambiguous is never retried
        await pool.close()
    run(body())


def test_push_disabled_hard_switch_never_sends():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        s = FakeSender()
        r = await run_notify_once(BetaStore(pool), CFG, ON, sender=s, clock=Clock(B0 + 2 * BUCKET + timedelta(seconds=40)))
        assert s.sent == [] and r["sent"] == 0
        st = await _rows(pool, "SELECT DISTINCT state, suppression_reason FROM beta_notification_deliveries")
        assert ("SUPPRESSED", "PUSH_DISABLED") in {(x["state"], x["suppression_reason"]) for x in st}
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- bot / admin / privacy
OWNER, ALICE, STRANGER = 900, 901, 902


def _msg(uid, text, update_id):
    return {"update_id": update_id, "message": {"from": {"id": uid}, "chat": {"id": uid, "type": "private"},
                                                "text": text}}


def _cb(uid, data, update_id):
    return {"update_id": update_id, "callback_query": {"id": f"cb{update_id}", "from": {"id": uid},
                                                       "message": {"chat": {"id": uid}}, "data": data}}


def test_bot_unauthorized_admin_join_feedback_delete_me():
    async def body():
        from runtime.beta_bot import BetaBotHandler
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET)
        pid = (await _rows(pool, "SELECT public_id FROM beta_episodes"))[0]["public_id"]
        h = BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON, owner_user_id=OWNER,
                           clock=Clock(B0 + 2 * BUCKET + timedelta(seconds=30)))
        out = await h.handle(_msg(STRANGER, "/start", 1))
        assert "closed private beta" in out[0].html.lower()
        for t in ("beta_users", "beta_allowlist", "beta_feedback", "beta_admin_audit"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] == 0
        out = await h.handle(_msg(STRANGER, "/admin_add 902", 2))
        assert "Unknown command" in out[0].html
        audit = await _rows(pool, "SELECT authorized, actor_fingerprint FROM beta_admin_audit")
        assert audit == [{"authorized": False, "actor_fingerprint": "unauthorized"}]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 0
        await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 3))
        assert (await _rows(pool, "SELECT telegram_user_id FROM beta_allowlist")) == [{"telegram_user_id": ALICE}]
        audit = await _rows(pool, "SELECT target_fingerprint FROM beta_admin_audit WHERE authorized")
        assert audit[0]["target_fingerprint"].startswith("u_") and str(ALICE) not in audit[0]["target_fingerprint"]
        out = await h.handle(_msg(ALICE, "/start", 4))
        assert "privacy notice" in out[0].html.lower() and out[0].buttons == [[("Join", "join")]]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_users"))[0]["n"] == 0
        await h.handle(_cb(ALICE, "join", 5))
        out = await h.handle(_msg(ALICE, "/btc", 6))
        assert "EVENT ACTIVE" in out[0].html
        out = await h.handle(_msg(ALICE, "/history", 7))
        assert pid in out[0].html and "SUPPRESSED (PUSH_DISABLED)" in out[0].html
        await h.handle(_cb(ALICE, f"u:{pid}", 8))
        await h.handle(_cb(ALICE, f"n:{pid}", 9))
        fb = await _rows(pool, "SELECT vote FROM beta_feedback")
        assert fb == [{"vote": "NOISE"}]
        assert await h.handle(_cb(ALICE, f"u:{pid}", 9)) == []          # replayed update id ignored
        out = await h.handle(_cb(ALICE, f"d:{pid}", 10))
        assert pid in out[1].html
        await h.handle(_msg(OWNER, "/admin_pause_push", 11))
        out = await h.handle(_msg(OWNER, "/admin_resume_push", 12))
        assert "remains OFF" in out[0].html
        await h.handle(_msg(ALICE, "/stop", 13))
        assert (await _rows(pool, "SELECT status FROM beta_users")) == [{"status": "STOPPED"}]
        await h.handle(_msg(ALICE, "/delete_me", 14))
        for t in ("beta_users", "beta_allowlist", "beta_feedback"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_episodes"))[0]["n"] == 1   # market records stay
        assert (await _rows(pool, "SELECT last_update_id FROM beta_bot_update_state"))[0]["last_update_id"] == 14
        await pool.close()
    run(body())


def test_broadcast_wording_guard_and_retention_purge():
    async def body():
        from beta.delivery import run_notify_once
        from runtime.beta_bot import BetaBotHandler
        pool = await fresh_pool()
        h = BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(B0))
        out = await h.handle(_msg(OWNER, "/admin_broadcast BUY now", 1))
        assert "refused" in out[0].html and len(out) == 1
        async with pool.acquire() as c:
            await c.execute("INSERT INTO beta_allowlist VALUES (77, now())")
            await c.execute("INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
                            " stopped_at) VALUES (77, 77, 'STOPPED', $1, $1, $1)", B0 - timedelta(days=31))
        r = await run_notify_once(BetaStore(pool), CFG, ON, sender=None, clock=Clock(B0))
        assert r["purged_users"] == 1
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_users"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 0
        await pool.close()
    run(body())


def test_owner_health_alerts_are_rate_limited_and_owner_only():
    async def body():
        from beta.delivery import run_notify_once
        pool = await fresh_pool()
        s = FakeSender()
        now = B0 + timedelta(hours=2)
        r1 = await run_notify_once(BetaStore(pool), CFG, ON, sender=s, clock=Clock(now), owner_user_id=OWNER)
        assert "INGESTION_STALE" in r1["owner_alerts"] and s.sent[0][0] == OWNER
        r2 = await run_notify_once(BetaStore(pool), CFG, ON, sender=s, clock=Clock(now + timedelta(minutes=5)),
                                   owner_user_id=OWNER)
        assert r2["owner_alerts"] == [] and len(s.sent) == 1
        r3 = await run_notify_once(BetaStore(pool), CFG, ON, sender=s, clock=Clock(now + timedelta(minutes=31)),
                                   owner_user_id=OWNER)
        assert r3["owner_alerts"] and all(chat == OWNER for chat, _h, _b in s.sent)
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- temporal context
def up_move(b):
    return {ex: {"price_move": 2.0, "oi_change": -3.0} for ex in EXS}


async def _context_rows(pool):
    return await _rows(pool, "SELECT bucket_ts, tape_id, prev_state_digest, state, state_digest "
                             "FROM beta_context_snapshots ORDER BY bucket_ts")


def test_context_episode_survives_quiet_bucket_one_push_and_replay_is_identical():
    async def body():
        import json
        from beta import context as cx
        from beta.detector import replay_context
        from storage.beta_v0_store import BetaStore
        pool = await _setup(n_eval=8)
        plan = [down_move, down_move, quiet, quiet, down_move, down_move]
        reports = []
        for i, sc in enumerate(plan):
            reports.append(await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET))
        # detector semantics unchanged: the quiet bucket ends the detector episode ...
        assert ("TRIGGERED", "ENDED", "CONDITION_FAILED") in [
            t[1:] for t in reports[2]["processed"][0]["transitions"]]
        # ... while the context episode is only COOLING, then reactivates
        assert reports[2]["processed"][0]["context"]["PRICE_OI_CONTRACTION_DOWN"] == ["COOLING", "TRIGGERED"]
        assert reports[4]["processed"][0]["context"]["PRICE_OI_CONTRACTION_DOWN"] == ["ACTIVE", "TRIGGERED"]
        # one loud push per context episode: the 2nd detector trigger is silent
        pd = await _rows(pool, "SELECT decision_ts, would_push, suppression_reason FROM beta_push_decisions "
                               "ORDER BY decision_ts")
        assert [(r["would_push"], r["suppression_reason"]) for r in pd] == [
            (True, "PUSH_DISABLED"), (False, "CONTEXT_EPISODE_NOTIFIED")]
        rows = await _context_rows(pool)
        assert [r["bucket_ts"] for r in rows] == [B0 + i * BUCKET for i in range(6)]
        assert rows[0]["prev_state_digest"] is None
        for a, b in zip(rows, rows[1:]):
            assert b["prev_state_digest"] == a["state_digest"]
        states = [json.loads(r["state"]) if isinstance(r["state"], str) else r["state"] for r in rows]
        assert [cx.state_digest(s) for s in states] == [r["state_digest"] for r in rows]
        e = states[-1]["episodes"]["PRICE_OI_CONTRACTION_DOWN"]
        assert e["reactivations"] == 1 and len(e["detector_episode_ids"]) == 2
        det_ids = {r["public_id"] for r in await _rows(pool, "SELECT public_id FROM beta_episodes")}
        assert set(e["detector_episode_ids"]) == det_ids
        assert e["episodization_version"] == "BETA_EPISODES_V0"
        # replay (LIVE decision rows + as-of 1h history) == what was persisted
        store = BetaStore(pool)
        async with store.connect() as conn:
            replayed = await replay_context(CFG, S2, conn, start_bucket=B0, end_bucket=B0 + 5 * BUCKET)
        assert [cx.state_digest(s) for s in replayed] == [r["state_digest"] for r in rows]
        # the tape now carries per-venue raw values + kline OHLC by value
        tape = await _rows(pool, "SELECT metrics FROM beta_state_tape WHERE origin='LIVE' AND bucket_ts=$1", B0)
        m = json.loads(tape[0]["metrics"]) if isinstance(tape[0]["metrics"], str) else tape[0]["metrics"]
        for ex in EXS:
            assert m[f"x:{ex}:price_move_pct"] == pytest.approx(-2.0)
            # OHLC comes from Stage-1 klines_1m (seeded flat at 100 here), not the Stage-2 fake reader
            assert [m[f"x:{ex}:kline_{k}"] for k in ("open", "high", "low", "close")] == [100.0, 100.1, 99.9, 100.0]
        await pool.close()
    run(body())


def test_opposite_side_entry_supersedes_cooling_episode_and_gets_its_own_push():
    async def body():
        pool = await _setup(n_eval=8)
        for i, sc in enumerate([down_move, down_move, quiet, up_move, up_move]):
            r = await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        ctx = (await _context_rows(pool))[-1]["state"]
        import json
        ctx = json.loads(ctx) if isinstance(ctx, str) else ctx
        old = ctx["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]
        new = ctx["episodes"]["PRICE_OI_CONTRACTION_UP"]
        assert old["end_reason"] == "SUPERSEDED_BY_OPPOSITE" and new["cluster_id"] == old["cluster_id"]
        pd = await _rows(pool, "SELECT event_type, would_push, suppression_reason FROM beta_push_decisions "
                               "ORDER BY decision_ts")
        assert [(r["event_type"], r["suppression_reason"]) for r in pd] == [
            ("PRICE_OI_CONTRACTION_DOWN", "PUSH_DISABLED"), ("PRICE_OI_CONTRACTION_UP", "PUSH_DISABLED")]
        assert r["status"] == "OK"
        await pool.close()
    run(body())


def test_context_steps_through_buckets_the_detector_skipped():
    async def body():
        pool = await _setup(n_eval=8)
        await _detect(pool, ScenarioReader(down_move), B0)
        clock = Clock(B0 + 5 * BUCKET + timedelta(seconds=30))
        await run_detector_once(deps(pool, ScenarioReader(quiet), clock), CFG, ON,
                                explicit_bucket=B0 + 4 * BUCKET)
        rows = await _context_rows(pool)
        assert [r["bucket_ts"] for r in rows] == [B0 + i * BUCKET for i in range(5)]
        assert [r["tape_id"] is None for r in rows] == [False, True, True, True, False]
        import json
        last = json.loads(rows[-1]["state"]) if isinstance(rows[-1]["state"], str) else rows[-1]["state"]
        assert last["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]["end_reason"] == "COOLED_DOWN"
        await pool.close()
    run(body())


def test_bot_btc_shows_cooling_episode_and_records_what_was_shown():
    async def body():
        import hashlib
        import json
        from runtime.beta_bot import BetaBotHandler
        from beta.state_tape import sha256_json
        pool = await _setup()
        for i, sc in enumerate([down_move, down_move, quiet]):
            await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        h = BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON, owner_user_id=OWNER,
                           clock=Clock(B0 + 3 * BUCKET + timedelta(seconds=30)))
        await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 1))
        await h.handle(_cb(ALICE, "join", 2))
        out = await h.handle(_msg(ALICE, "/btc", 3))
        html_text = out[0].html
        assert "BTC perp · COOLING" in html_text and "episode · triggered" in html_text
        assert "Peak 00:05" in html_text and "Now 00:15" in html_text
        (label, data), = out[0].buttons[0]
        assert label == "Details" and data.startswith("c:CX-")
        views = await _rows(pool, "SELECT * FROM beta_btc_views")
        assert len(views) == 1
        v = views[0]
        payload = json.loads(v["payload"]) if isinstance(v["payload"], str) else v["payload"]
        assert v["rendered_html"] == html_text
        assert v["rendered_sha256"] == hashlib.sha256(html_text.encode("utf-8")).hexdigest()
        assert v["payload_digest"] == sha256_json(payload)
        assert v["episodization_version"] == payload["episodization_version"] == "BETA_EPISODES_V0"
        latest = (await _rows(pool, "SELECT state_digest FROM beta_context_snapshots ORDER BY bucket_ts DESC"))[0]
        assert v["context_state_digest"] == latest["state_digest"]
        assert "telegram_user_id" not in json.dumps(payload) and str(ALICE) not in json.dumps(payload)
        out = await h.handle(_cb(ALICE, data, 4))
        assert "Phase cooling" in out[1].html and "BETA_EPISODES_V0" in out[1].html
        await pool.close()
    run(body())
