"""Beta V0.2 PostgreSQL integration (real local PostgreSQL named by $BETA_TEST_DSN;
skipped when unset). The Stage-2 feature/consensus/percentile math runs unchanged
through ScenarioReader fakes. No network, no exchange call, no Telegram."""
import asyncio
import random
import re
from datetime import datetime, timedelta

import pytest

from beta_fakes import (CFG as CFG_COMMITTED, EXS, FEATURE_CODE, ON, ON_PUSH, S2, T0, TEST_DSN, Clock,
                        ScenarioReader, deps, down_move, fresh_pool, history_buckets, history_metrics, quiet,
                        run, seed_history, seed_live_klines)
from beta import detector as det
from beta.detector import run_bootstrap_once, run_detector_once
from beta.state_tape import materialize_bucket
from storage.beta_v0_store import BetaStore, apply_beta_schema

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

# The detector / episode / outbox pipeline is exercised under the V0.2 delivery policy
# (3 a day, no global cooldown, no quiet hours) with the unusual-hour gate answered
# "qualified": these tests pin the pipeline BELOW the product gate. The gate itself,
# the committed policy and /push off are tested separately (test_gate_* below).
CFG = CFG_COMMITTED.with_overrides(max_new_pushes_per_utc_day=3,
                                   push_policy={"quiet_hours_kyiv": ["00:00", "00:00"], "global_cooldown_min": 1})
REAL_HOUR_GATE = det._hour_gate


async def _qualified_gate(conn, cfg, hour_ctx, snapshot):
    return {"version": "TEST_GATE", "qualified": True, "status": "QUALIFIED"}


@pytest.fixture(autouse=True)
def _answer_the_hour_gate(monkeypatch):
    monkeypatch.setattr(det, "_hour_gate", _qualified_gate)

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
                        " stopped_at, lang) VALUES (11, 11, 'ACTIVE', now(), now(), NULL, 'en'),"
                        " (12, 12, 'STOPPED', now(), now(), now(), 'en')")


def test_delivery_sent_once_ttl_and_user_inactive(monkeypatch):
    from beta import delivery
    lat, real = [], delivery.format_push

    def spy(*a, latency=None, **k):
        lat.append(latency)
        return real(*a, latency=latency, **k)
    monkeypatch.setattr(delivery, "format_push", spy)

    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        decision_ts = B0 + 2 * BUCKET
        s = FakeSender()
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(decision_ts + timedelta(seconds=40)))
        assert r["sent"] == 1 and r["materialized"] == 2 and len(s.sent) == 1
        # A4: the push is rendered with its measured delay from the 5m bucket close it was decided on
        assert lat == [{"class": "push", "source": "candle_close", "source_at": decision_ts.isoformat(), "lag_s": 40,
                        "p50_s": None, "p95_s": None, "n": 0, "window_days": 7}]
        assert s.sent[0][1].startswith("<b>BTC · unusual hour</b>")
        assert s.sent[0][2][0] == [("📊 BTC now", "b:now")]                 # push -> /btc in one tap
        assert [b[0] for b in s.sent[0][2][1]] == ["Useful", "Noise"]       # no Details: it exposed internals
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


def _cb(uid, data, update_id, message_id=None):
    message = {"chat": {"id": uid}}
    if message_id is not None:
        message["message_id"] = message_id
    return {"update_id": update_id, "callback_query": {"id": f"cb{update_id}", "from": {"id": uid},
                                                       "message": message, "data": data}}


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
        assert "закрытой бете" in out[0].html.lower()
        assert "closed beta" in out[0].html.lower()
        for t in ("beta_users", "beta_allowlist", "beta_feedback", "beta_admin_audit"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] == 0
        out = await h.handle(_msg(STRANGER, "/admin_add 902", 2))
        assert "Неизвестная команда" in out[0].html
        audit = await _rows(pool, "SELECT authorized, actor_fingerprint FROM beta_admin_audit")
        assert audit == [{"authorized": False, "actor_fingerprint": "unauthorized"}]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_allowlist"))[0]["n"] == 0
        await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 3))
        assert (await _rows(pool, "SELECT telegram_user_id FROM beta_allowlist")) == [{"telegram_user_id": ALICE}]
        audit = await _rows(pool, "SELECT target_fingerprint FROM beta_admin_audit WHERE authorized")
        assert audit[0]["target_fingerprint"].startswith("u_") and str(ALICE) not in audit[0]["target_fingerprint"]
        out = await h.handle(_msg(ALICE, "/start", 4))
        assert out[0].buttons == [[("Русский", "pick:ru"), ("English", "pick:en")]]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_users"))[0]["n"] == 0
        out = await h.handle(_cb(ALICE, "pick:en", 5))
        assert "privacy notice" in out[1].html.lower() and out[1].buttons == [[("Join", "join:en")]]
        await h.handle(_cb(ALICE, "join:en", 6))
        assert (await _rows(pool, "SELECT lang FROM beta_users")) == [{"lang": "en"}]
        out = await h.handle(_msg(ALICE, "/btc", 7))
        assert "· unusual now" in out[0].html
        out = await h.handle(_msg(ALICE, "/history", 8))
        # the episode is listed in words: no internal id, no delivery state or suppression code
        assert "price + OI contraction down" in out[0].html and "no message" in out[0].html
        assert pid not in out[0].html and "SUPPRESSED" not in out[0].html and "PUSH_DISABLED" not in out[0].html
        await h.handle(_cb(ALICE, f"u:{pid}", 9))
        await h.handle(_cb(ALICE, f"n:{pid}", 10))
        fb = await _rows(pool, "SELECT vote FROM beta_feedback")
        assert fb == [{"vote": "NOISE"}]
        assert await h.handle(_cb(ALICE, f"u:{pid}", 10)) == []          # replayed update id ignored
        out = await h.handle(_cb(ALICE, f"d:{pid}", 11))          # episode Details are retired
        assert all(pid not in (getattr(m, "html", "") or "") for m in out)
        await h.handle(_msg(OWNER, "/admin_pause_push", 12))
        out = await h.handle(_msg(OWNER, "/admin_resume_push", 13))
        assert "remains OFF" in out[0].html
        await h.handle(_msg(ALICE, "/stop", 14))
        assert (await _rows(pool, "SELECT status FROM beta_users")) == [{"status": "STOPPED"}]
        await h.handle(_msg(ALICE, "/delete_me", 15))
        for t in ("beta_users", "beta_allowlist", "beta_feedback"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_episodes"))[0]["n"] == 1   # market records stay
        assert (await _rows(pool, "SELECT last_update_id FROM beta_bot_update_state"))[0]["last_update_id"] == 15
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


def taker_buy(b):
    return {ex: {"taker_buy": 60.0, "taker_sell": 0.5} for ex in EXS}


GOLDEN_PLAN = [down_move, down_move, quiet, quiet, down_move, down_move, quiet, up_move, up_move, quiet,
               taker_buy, taker_buy, taker_buy, quiet, taker_buy, taker_buy, quiet]
# Recorded on the pre-amendment base commit 234d5ee (no temporal context at all) with
# the same inputs. Detector episodes, transitions and push decisions must match exactly.
GOLDEN_EPISODES = [
    ('EV-751B156B16', 'PRICE_OI_CONTRACTION_DOWN', 'ENDED', '2026-04-10 00:00:00+00:00', '2026-04-10 00:10:00+00:00', '2026-04-10 00:15:00+00:00', 'CONDITION_FAILED', '2026-04-10 00:05:00+00:00', 2),
    ('EV-FA7B8C61F8', 'PRICE_OI_CONTRACTION_DOWN', 'ENDED', '2026-04-10 00:20:00+00:00', '2026-04-10 00:30:00+00:00', '2026-04-10 00:35:00+00:00', 'CONDITION_FAILED', '2026-04-10 00:25:00+00:00', 2),
    ('EV-67593F4F3C', 'PRICE_OI_CONTRACTION_UP', 'ENDED', '2026-04-10 00:35:00+00:00', '2026-04-10 00:45:00+00:00', '2026-04-10 00:50:00+00:00', 'CONDITION_FAILED', '2026-04-10 00:40:00+00:00', 2),
    ('EV-45FCBF1474', 'TAKER_FLOW_EXTREME_BUY', 'ENDED', '2026-04-10 00:50:00+00:00', '2026-04-10 01:00:00+00:00', '2026-04-10 01:10:00+00:00', 'CONDITION_FAILED', '2026-04-10 01:00:00+00:00', 3),
    ('EV-62F6E7AA3B', 'TAKER_FLOW_EXTREME_BUY', 'ENDED', '2026-04-10 01:10:00+00:00', '2026-04-10 01:20:00+00:00', '2026-04-10 01:25:00+00:00', 'CONDITION_FAILED', '2026-04-10 01:15:00+00:00', 2),
]
GOLDEN_TRANSITIONS = [
    ('EV-751B156B16', 1, None, 'ARMED', '2026-04-10 00:00:00+00:00', 'CONDITION_MET'),
    ('EV-751B156B16', 2, 'ARMED', 'TRIGGERED', '2026-04-10 00:05:00+00:00', 'CONDITION_MET'),
    ('EV-751B156B16', 3, 'TRIGGERED', 'ENDED', '2026-04-10 00:10:00+00:00', 'CONDITION_FAILED'),
    ('EV-FA7B8C61F8', 1, None, 'ARMED', '2026-04-10 00:20:00+00:00', 'CONDITION_MET'),
    ('EV-FA7B8C61F8', 2, 'ARMED', 'TRIGGERED', '2026-04-10 00:25:00+00:00', 'CONDITION_MET'),
    ('EV-FA7B8C61F8', 3, 'TRIGGERED', 'ENDED', '2026-04-10 00:30:00+00:00', 'CONDITION_FAILED'),
    ('EV-67593F4F3C', 1, None, 'ARMED', '2026-04-10 00:35:00+00:00', 'CONDITION_MET'),
    ('EV-67593F4F3C', 2, 'ARMED', 'TRIGGERED', '2026-04-10 00:40:00+00:00', 'CONDITION_MET'),
    ('EV-67593F4F3C', 3, 'TRIGGERED', 'ENDED', '2026-04-10 00:45:00+00:00', 'CONDITION_FAILED'),
    ('EV-45FCBF1474', 1, None, 'ARMED', '2026-04-10 00:50:00+00:00', 'CONDITION_MET'),
    ('EV-45FCBF1474', 2, 'ARMED', 'TRIGGERED', '2026-04-10 00:55:00+00:00', 'CONDITION_MET'),
    ('EV-45FCBF1474', 3, 'TRIGGERED', 'ENDED', '2026-04-10 01:05:00+00:00', 'CONDITION_FAILED'),
    ('EV-62F6E7AA3B', 1, None, 'ARMED', '2026-04-10 01:10:00+00:00', 'CONDITION_MET'),
    ('EV-62F6E7AA3B', 2, 'ARMED', 'TRIGGERED', '2026-04-10 01:15:00+00:00', 'CONDITION_MET'),
    ('EV-62F6E7AA3B', 3, 'TRIGGERED', 'ENDED', '2026-04-10 01:20:00+00:00', 'CONDITION_FAILED'),
]
GOLDEN_PUSH = {
    False: [
        ('EV-751B156B16', 'PRICE_OI_CONTRACTION_DOWN', '2026-04-10 00:10:00+00:00', True, 'SUPPRESSED', 'PUSH_DISABLED'),
        ('EV-FA7B8C61F8', 'PRICE_OI_CONTRACTION_DOWN', '2026-04-10 00:30:00+00:00', False, 'SUPPRESSED', 'SAME_EVENT_COOLDOWN'),
        ('EV-67593F4F3C', 'PRICE_OI_CONTRACTION_UP', '2026-04-10 00:45:00+00:00', True, 'SUPPRESSED', 'PUSH_DISABLED'),
        ('EV-45FCBF1474', 'TAKER_FLOW_EXTREME_BUY', '2026-04-10 01:00:00+00:00', True, 'SUPPRESSED', 'PUSH_DISABLED'),
        ('EV-62F6E7AA3B', 'TAKER_FLOW_EXTREME_BUY', '2026-04-10 01:20:00+00:00', False, 'SUPPRESSED', 'SAME_EVENT_COOLDOWN'),
    ],
    True: [
        ('EV-751B156B16', 'PRICE_OI_CONTRACTION_DOWN', '2026-04-10 00:10:00+00:00', True, 'PUSH', None),
        ('EV-FA7B8C61F8', 'PRICE_OI_CONTRACTION_DOWN', '2026-04-10 00:30:00+00:00', False, 'SUPPRESSED', 'SAME_EVENT_COOLDOWN'),
        ('EV-67593F4F3C', 'PRICE_OI_CONTRACTION_UP', '2026-04-10 00:45:00+00:00', True, 'PUSH', None),
        ('EV-45FCBF1474', 'TAKER_FLOW_EXTREME_BUY', '2026-04-10 01:00:00+00:00', True, 'PUSH', None),
        ('EV-62F6E7AA3B', 'TAKER_FLOW_EXTREME_BUY', '2026-04-10 01:20:00+00:00', False, 'SUPPRESSED', 'SAME_EVENT_COOLDOWN'),
    ],
}


async def _detector_record(pool):
    eps = await _rows(pool, "SELECT public_id, event_type, state, opened_bucket, triggered_at, terminal_at, "
                            "terminal_reason, last_bucket, last_streak FROM beta_episodes ORDER BY episode_pk")
    tr = await _rows(pool, "SELECT e.public_id, t.seq, t.from_state, t.to_state, t.decision_bucket, t.reason "
                           "FROM beta_episode_transitions t JOIN beta_episodes e USING (episode_pk) "
                           "ORDER BY e.episode_pk, t.seq")
    pd = await _rows(pool, "SELECT e.public_id, p.event_type, p.decision_ts, p.would_push, p.decision, "
                           "p.suppression_reason FROM beta_push_decisions p JOIN beta_episodes e USING (episode_pk) "
                           "ORDER BY p.decision_ts, p.event_type")
    s = lambda v: None if v is None else str(v)  # noqa: E731
    return ([(e["public_id"], e["event_type"], e["state"], s(e["opened_bucket"]), s(e["triggered_at"]),
              s(e["terminal_at"]), e["terminal_reason"], s(e["last_bucket"]), e["last_streak"]) for e in eps],
            [(t["public_id"], t["seq"], t["from_state"], t["to_state"], s(t["decision_bucket"]), t["reason"])
             for t in tr],
            [(p["public_id"], p["event_type"], s(p["decision_ts"]), p["would_push"], p["decision"],
              p["suppression_reason"]) for p in pd])


CFG_V1 = CFG.with_overrides(state_schema_version=1)


async def _run_plan(pool, switches, cfg=CFG):
    for i, sc in enumerate(GOLDEN_PLAN):
        await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET, switches=switches, cfg=cfg)


def _golden_under(cfg):
    """The base golden with episode ids re-derived by the UNCHANGED id function for
    `cfg`'s rules digest (which covers state_schema_version); every other field is
    the base value verbatim."""
    from beta.detector import public_episode_id
    ids = {g[0]: public_episode_id("BTCUSDT", g[1], datetime.fromisoformat(g[3]), cfg.rules_digest)
           for g in GOLDEN_EPISODES}
    return ([(ids[g[0]],) + g[1:] for g in GOLDEN_EPISODES],
            [(ids[t[0]],) + t[1:] for t in GOLDEN_TRANSITIONS],
            {k: [(ids[p[0]],) + p[1:] for p in v] for k, v in GOLDEN_PUSH.items()})


@pytest.mark.parametrize("push_on", [False, True])
def test_schema_v1_reproduces_the_pre_amendment_base_exactly(push_on):
    async def body():
        pool = await _setup(n_eval=len(GOLDEN_PLAN) + 2)
        await _run_plan(pool, ON_PUSH if push_on else ON, cfg=CFG_V1)
        eps, tr, pd = await _detector_record(pool)
        assert eps == GOLDEN_EPISODES and tr == GOLDEN_TRANSITIONS and pd == GOLDEN_PUSH[push_on]
        await pool.close()
    run(body())


@pytest.mark.parametrize("push_on", [False, True])
def test_detector_boundaries_and_push_decisions_identical_to_pre_amendment_base(push_on):
    async def body():
        pool = await _setup(n_eval=len(GOLDEN_PLAN) + 2)
        await _run_plan(pool, ON_PUSH if push_on else ON)
        eps, tr, pd = await _detector_record(pool)
        g_eps, g_tr, g_pd = _golden_under(CFG)
        assert eps == g_eps and tr == g_tr and pd == g_pd[push_on]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_context_snapshots"))[0]["n"] == len(GOLDEN_PLAN)
        await pool.close()
    run(body())


def test_a_failing_context_projection_cannot_change_or_block_detection(monkeypatch):
    async def body():
        from beta import detector as det

        async def boom(*a, **k):
            raise RuntimeError("synthetic context failure")
        monkeypatch.setattr(det, "advance_context", boom)
        pool = await _setup(n_eval=len(GOLDEN_PLAN) + 2)
        r = await _detect(pool, ScenarioReader(down_move), B0)
        assert r["processed"][0]["context_error"] == "RuntimeError"
        for i, sc in enumerate(GOLDEN_PLAN[1:], start=1):
            await _detect(pool, ScenarioReader(sc), B0 + i * BUCKET)
        eps, tr, pd = await _detector_record(pool)
        g_eps, g_tr, g_pd = _golden_under(CFG)
        assert eps == g_eps and tr == g_tr and pd == g_pd[False]
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_context_snapshots"))[0]["n"] == 0
        await pool.close()
    run(body())


async def _context_rows(pool):
    return await _rows(pool, "SELECT bucket_ts, tape_id, prev_state_digest, state, state_digest "
                             "FROM beta_context_snapshots ORDER BY bucket_ts")


def _j(v):
    import json
    return json.loads(v) if isinstance(v, str) else v


def test_context_mirrors_db_episodes_and_replay_is_byte_identical():
    async def body():
        from beta import context as cx
        from beta.detector import replay_context
        pool = await _setup(n_eval=len(GOLDEN_PLAN) + 2)
        await _run_plan(pool, ON)
        rows = await _context_rows(pool)
        assert [r["bucket_ts"] for r in rows] == [B0 + i * BUCKET for i in range(len(GOLDEN_PLAN))]
        assert rows[0]["prev_state_digest"] is None
        for a, b in zip(rows, rows[1:]):
            assert b["prev_state_digest"] == a["state_digest"]
        states = [_j(r["state"]) for r in rows]
        assert [cx.state_digest(s) for s in states] == [r["state_digest"] for r in rows]
        # every DB detector episode appears in the projection with the same boundaries
        seen = {}
        for s in states:
            for e in list(s["open"].values()) + list(s["last_ended"].values()):
                seen[e["episode_id"]] = e
        db = {e[0]: e for e in (await _detector_record(pool))[0]}
        assert set(seen) == set(db)
        for pid, e in seen.items():
            d = db[pid]
            assert (e["state"], e["terminal_reason"], e["opened_bucket"], e["last_bucket"]) == \
                (d[2], d[6], cx.iso(datetime.fromisoformat(d[3])), cx.iso(datetime.fromisoformat(d[7])))
        assert states[-1]["open"] == {} and states[2]["open"] == {}          # no invented persistence
        async with BetaStore(pool).connect() as conn:
            replayed = await replay_context(CFG, S2, conn, start_bucket=B0,
                                            end_bucket=B0 + (len(GOLDEN_PLAN) - 1) * BUCKET)
        assert [cx.state_digest(s) for s in replayed] == [r["state_digest"] for r in rows]
        # per-venue raw evidence is on the tape by value (snapshot) + kline OHLC (metrics)
        tape = (await _rows(pool, "SELECT metrics, snapshot FROM beta_state_tape WHERE origin='LIVE' "
                                  "AND bucket_ts=$1", B0))[0]
        m, snapshot = _j(tape["metrics"]), _j(tape["snapshot"])
        for ex in EXS:
            assert snapshot["venue_raw"][ex]["price_move_pct"] == pytest.approx(-2.0)
            assert f"x:{ex}:price_move_pct" not in m
            assert [m[f"x:{ex}:kline_{k}"] for k in ("open", "high", "low", "close")] == [100.0, 100.1, 99.9, 100.0]
        await pool.close()
    run(body())


def test_context_steps_through_buckets_the_detector_skipped():
    async def body():
        pool = await _setup(n_eval=8)
        await _detect(pool, ScenarioReader(down_move), B0)
        clock = Clock(B0 + 5 * BUCKET + timedelta(seconds=30))
        await run_detector_once(deps(pool, ScenarioReader(down_move), clock), CFG, ON,
                                explicit_bucket=B0 + 4 * BUCKET)
        rows = await _context_rows(pool)
        assert [r["bucket_ts"] for r in rows] == [B0 + i * BUCKET for i in range(5)]
        assert [r["tape_id"] is None for r in rows] == [False, True, True, True, False]
        last = _j(rows[-1]["state"])
        db = await _rows(pool, "SELECT terminal_reason FROM beta_episodes ORDER BY episode_pk")
        assert db[0]["terminal_reason"] == "DETECTION_GAP"
        assert last["last_ended"]["PRICE_OI_CONTRACTION_DOWN"]["terminal_reason"] == "DETECTION_GAP"
        await pool.close()
    run(body())


def test_bot_btc_shows_last_event_after_detector_termination_and_records_view():
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
        await h.handle(_msg(ALICE, "/start", 2))
        await h.handle(_cb(ALICE, "pick:en", 3))
        await h.handle(_cb(ALICE, "join:en", 4))
        out = await h.handle(_msg(ALICE, "/btc", 5))
        text = out[0].html
        assert "· calmed" in text and "03:00–03:10: sharp drop · ended 03:15, just now" in text
        assert "data 03:15 Kyiv" in text and "Event has ended" not in text
        assert "NO ACTIVE EVENTS" not in text and "TRIGGERED" not in text and "ARMED" not in text
        assert "Trigger bucket" not in text and "condition no longer met" not in text
        pid = (await _rows(pool, "SELECT public_id FROM beta_episodes"))[0]["public_id"]
        buttons = out[0].buttons[0]
        assert buttons[0][0] == "Event" and buttons[0][1].endswith(":event")
        v = (await _rows(pool, "SELECT * FROM beta_btc_views"))[0]
        payload = _j(v["payload"])
        all_ready = payload.get("readiness") and all(
            g["status"] == "READY" for g in payload["readiness"]["groups"])
        assert all_ready is not None and ("Readiness", "r:latest") not in buttons
        assert v["rendered_html"] == text and v["lang"] == "en"
        assert v["rendered_sha256"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
        assert v["payload_digest"] == sha256_json(payload)
        from beta.formatter import format_1h_tab, format_btc, format_event_tab, view_id8
        assert format_btc(CFG, payload, "en") == v["rendered_html"]          # the stored payload re-renders exactly
        assert v["episodization_version"] == "STRICT_QUALIFICATION_V1"
        assert payload.get("horizons", {}).get("version") == "BETA_HORIZON_TOD_V3"
        latest = (await _rows(pool, "SELECT state_digest FROM beta_context_snapshots ORDER BY bucket_ts DESC"))[0]
        assert v["context_state_digest"] == latest["state_digest"]
        # the id as a value, not three digits inside a hex digest («…7f901e0…») or a price
        assert not re.search(rf"(?<![0-9a-fA-F.]){ALICE}(?![0-9a-fA-F.])", json.dumps(payload))
        view_pk = v["view_pk"]
        out = await h.handle(_cb(ALICE, f"o:{view_pk}:event", 6))
        vid = view_id8(v["payload_digest"])
        assert out[1].html == format_event_tab(CFG, payload, "en", vid)
        assert "STRICT_QUALIFICATION_V1" not in out[1].html and "Detector state" not in out[1].html
        edited = await h.handle(_cb(ALICE, f"e:{view_pk}:1h", 7, message_id=55))
        assert edited[1].kind == "edit" and edited[1].message_id == 55
        assert edited[1].html == format_1h_tab(CFG, payload, "en", vid)
        opens = await _rows(pool, "SELECT view_pk, tab, lang FROM beta_details_opens ORDER BY open_pk")
        assert opens == [{"view_pk": view_pk, "tab": "event", "lang": "en"},
                         {"view_pk": view_pk, "tab": "1h", "lang": "en"}]
        cols = await _rows(pool, "SELECT column_name FROM information_schema.columns "
                                 "WHERE table_name='beta_details_opens'")
        assert "user_pk" not in {c["column_name"] for c in cols}
        assert "telegram_user_id" not in {c["column_name"] for c in cols}
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- state-tape schema V1 -> V2
async def _explicit(pool, reader, bucket, cfg):
    clock = Clock(bucket + 2 * BUCKET + timedelta(seconds=30))
    return await run_detector_once(deps(pool, reader, clock), cfg, ON, explicit_bucket=bucket)


def test_v1_row_rechecked_by_v2_is_a_schema_boundary_not_a_market_correction():
    async def body():
        from beta.detector import build_live_record
        pool = await _setup(n_eval=8)
        await _detect(pool, ScenarioReader(down_move), B0, cfg=CFG_V1)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, cfg=CFG_V1)
        v1 = (await _rows(pool, "SELECT tape_id, feature_digest, metrics, snapshot FROM beta_state_tape "
                                "WHERE origin='LIVE' AND bucket_ts=$1", B0))[0]
        m, snapshot = _j(v1["metrics"]), _j(v1["snapshot"])
        assert snapshot["state_schema_version"] == 1 and "venue_raw" not in snapshot
        assert not any(k.startswith("x:") and "kline" in k for k in m)
        assert all("ohlc" not in v for v in snapshot["venues"].values())
        # the SAME market inputs in the V2 shape have a different feature_digest ...
        async with BetaStore(pool).connect() as conn:
            rec_v2 = await build_live_record(deps(pool, ScenarioReader(down_move), Clock(B0)), CFG, conn, B0)
        assert rec_v2.feature_digest != v1["feature_digest"]
        # ... yet a V2 correction check treats it as a schema boundary, never a correction
        r = await _explicit(pool, ScenarioReader(down_move), B0, CFG)
        assert r["status"] == "SCHEMA_VERSION_BOUNDARY"
        assert r["stored_state_schema_versions"] == [1] and r["current_state_schema_version"] == 2
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_state_tape WHERE origin='CORRECTION_CHECK'"))[0]["n"] == 0
        assert (await _rows(pool, "SELECT count(*) AS n FROM beta_episodes WHERE correction_flag"))[0]["n"] == 0
        # same-schema control: V1 re-checked by V1 with the same inputs is unchanged
        assert (await _explicit(pool, ScenarioReader(down_move), B0, CFG_V1))["status"] == "UNCHANGED"
        await pool.close()
    run(body())


def test_v2_real_input_change_is_still_a_correction():
    async def body():
        pool = await _setup(n_eval=8)
        await _detect(pool, ScenarioReader(down_move), B0)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET)
        assert (await _explicit(pool, ScenarioReader(down_move), B0, CFG))["status"] == "UNCHANGED"
        async with pool.acquire() as c:                 # a genuine Stage-1 revision of one V2 input (OHLC)
            await c.execute("UPDATE klines_1m SET high = high * 1.01 WHERE exchange='okx' AND ts=$1", B0)
        before = (await _rows(pool, "SELECT feature_digest FROM beta_state_tape WHERE bucket_ts=$1", B0))[0]
        r = await _explicit(pool, ScenarioReader(down_move), B0, CFG)
        assert r["status"] == "CORRECTION_APPENDED" and r["revision"] == 2 and r["episodes_flagged"] >= 1
        rows = await _rows(pool, "SELECT origin, revision, feature_digest, state_schema_version FROM beta_state_tape "
                                 "WHERE bucket_ts=$1 ORDER BY tape_id", B0)
        assert [(x["origin"], x["revision"], x["state_schema_version"]) for x in rows] == [
            ("LIVE", 1, 2), ("CORRECTION_CHECK", 2, 2)]
        assert rows[1]["feature_digest"] != before["feature_digest"]
        await pool.close()
    run(body())


def test_schema_boundary_ends_open_episodes_as_a_version_change_and_restarts_context():
    async def body():
        pool = await _setup(n_eval=8)
        await _detect(pool, ScenarioReader(down_move), B0, cfg=CFG_V1)
        await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, cfg=CFG_V1)
        await _detect(pool, ScenarioReader(down_move), B0 + 2 * BUCKET)            # first V2 bucket
        eps = await _rows(pool, "SELECT rules_digest, state, terminal_reason FROM beta_episodes ORDER BY episode_pk")
        assert (eps[0]["rules_digest"], eps[0]["state"], eps[0]["terminal_reason"]) == \
            (CFG_V1.rules_digest, "ENDED", "DETECTOR_VERSION_CHANGED")
        assert (eps[1]["rules_digest"], eps[1]["state"]) == (CFG.rules_digest, "ARMED")   # streak restarted
        ctx = await _rows(pool, "SELECT rules_digest, state FROM beta_context_snapshots ORDER BY context_pk")
        assert [c["rules_digest"] for c in ctx] == [CFG_V1.rules_digest] * 2 + [CFG.rules_digest]
        v2_state = _j(ctx[-1]["state"])
        assert v2_state["state_schema_version"] == 2 and v2_state["input"] is not None
        assert list(v2_state["open"]) == ["PRICE_OI_CONTRACTION_DOWN"]   # fresh V2 projection, no V1 carry-over
        await pool.close()
    run(body())


def test_1h_context_warms_up_on_12_v2_buckets_and_never_mixes_v1_rows():
    async def body():
        pool = await _setup(n_eval=24)
        for i in range(6):                                                         # V1 rows (no OHLC)
            await _detect(pool, ScenarioReader(quiet), B0 + i * BUCKET, cfg=CFG_V1)
        for k in range(1, 13):                                                     # V2 buckets 1..12
            await _detect(pool, ScenarioReader(quiet), B0 + (5 + k) * BUCKET)
        ctx = await _rows(pool, "SELECT bucket_ts, state FROM beta_context_snapshots WHERE rules_digest=$1 "
                                "ORDER BY bucket_ts", CFG.rules_digest)
        c1h = [_j(c["state"])["context_1h"] for c in ctx]
        assert len(c1h) == 12 and all(v is None for v in c1h[:11])                 # 11 V2 buckets: unavailable
        assert c1h[11] is not None                                                 # 12th: available
        assert c1h[11]["window_start"] == (B0 + 6 * BUCKET).isoformat().replace("+00:00", "Z")
        assert c1h[11]["range_width_pct_median"] == pytest.approx(0.2)            # seeded klines: (100.1-99.9)/100
        v1ctx = await _rows(pool, "SELECT state FROM beta_context_snapshots WHERE rules_digest=$1", CFG_V1.rules_digest)
        assert all(_j(c["state"])["context_1h"] is None for c in v1ctx)            # V1 never has 1h context
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- detector readiness
async def _setup_oi_maturity_boundary():
    """Real history whose earliest valid OI sample is B0-30d+5m: the OI percentile is
    'building' at B0 (span 30d-5m) and first 'mature' at B0+5m (span exactly 30d)."""
    pool = await fresh_pool()
    rng = random.Random(7)
    first_oi = B0 - timedelta(days=30) + BUCKET

    def metrics(b):
        m = history_metrics(rng)
        if b < first_oi:
            m["c:oi_change_pct_median"] = None
        return m
    await seed_history(pool, calculation_version=CALC, buckets=history_buckets(B0, 4), metrics_fn=metrics)
    await seed_live_klines(pool, [B0 + i * BUCKET for i in range(300)])
    return pool


def test_readiness_follows_the_real_percentile_maturity_boundary_without_pushes():
    async def body():
        import json
        from runtime.beta_bot import BetaBotHandler
        from beta.readiness import readiness
        from beta.config import canonical_json
        pool = await _setup_oi_maturity_boundary()
        h = BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON, owner_user_id=OWNER,
                           clock=Clock(B0 + BUCKET + timedelta(seconds=40)))
        await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 1))
        await h.handle(_msg(ALICE, "/start", 2))
        await h.handle(_cb(ALICE, "pick:en", 3))
        await h.handle(_cb(ALICE, "join:en", 4))

        await _detect(pool, ScenarioReader(quiet), B0)
        tape0 = (await _rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE' AND bucket_ts=$1", B0))[0]
        snap0 = _j(tape0["snapshot"])
        assert snap0["percentiles"]["c:oi_change_pct_median"]["tier"] == "building"
        assert snap0["rule_evaluations"]["PRICE_OI_CONTRACTION_DOWN"]["reason"].startswith(
            "PERCENTILE_NOT_MATURE:c:oi_change_pct_median")
        out = await h.handle(_msg(ALICE, "/btc", 5))
        text = out[0].html
        assert "· history building" in text and "NO ACTIVE EVENTS" not in text
        assert "Price/OI history 29.9d / 30d" in text
        assert ("Readiness", "r:latest") not in out[0].buttons[0]      # owner diagnostics only

        h.clock = Clock(B0 + 2 * BUCKET + timedelta(seconds=40))
        await _detect(pool, ScenarioReader(quiet), B0 + BUCKET)                     # first mature bucket
        snap1 = _j((await _rows(pool, "SELECT snapshot FROM beta_state_tape WHERE origin='LIVE' "
                                      "AND bucket_ts=$1", B0 + BUCKET))[0]["snapshot"])
        assert snap1["percentiles"]["c:oi_change_pct_median"]["tier"] == "mature"
        out = await h.handle(_msg(ALICE, "/btc", 6))
        text = out[0].html
        mature_buttons = out[0].buttons
        assert "· calm</b>" in text and "NO ACTIVE EVENTS" not in text
        assert "Detector ready" not in text and "Ready:" not in text
        details = await h.handle(_cb(ALICE, "r:latest", 7))           # an older message's button
        assert len(details) == 1 and details[0].kind == "answer" and "Detector readiness" not in details[0].html

        # the readiness transition produced no push decision and no delivery
        for t in ("beta_push_decisions", "beta_notification_deliveries"):
            assert (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"] == 0
        # what the user saw is persisted, and the same V2 row reproduces the same readiness
        views = await _rows(pool, "SELECT payload, rendered_html FROM beta_btc_views ORDER BY view_pk")
        assert [_j(v["payload"])["headline"] for v in views] == ["HISTORY BUILDING", "NO ACTIVE EVENTS"]
        ready = _j(views[1]["payload"])["readiness"]
        all_ready = all(g["status"] == "READY" for g in ready["groups"])
        row = mature_buttons[0] if mature_buttons else []
        assert all_ready is not None and ("Readiness", "r:latest") not in row
        again = readiness(CFG, {"bucket_ts": B0 + BUCKET, "snapshot": snap1}, maturity_days=30.0)
        assert canonical_json(_j(views[1]["payload"])["readiness"]) == canonical_json(json.loads(json.dumps(again)))
        await pool.close()
    run(body())


def test_open_interest_asof_query_keeps_the_two_minute_window():
    async def body():
        from datetime import timezone
        from beta.oi_asof import venue_oi_change_pct
        pool = await fresh_pool()
        t = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
        t0 = t - timedelta(hours=1)
        rows = [
            ("binance", "BTCUSDT", t, 110.0, "base", None),
            ("binance", "BTCUSDT", t - timedelta(minutes=1), 999.0, "base", None),
            ("bybit", "BTCUSDT", t - timedelta(minutes=2), 50.0, "base", None),
            ("bybit", "BTCUSDT", t + timedelta(seconds=30), 1.0, "base", None),
            ("okx", "BTCUSDT", t - timedelta(minutes=2, seconds=1), 9.0, "base", None),
            ("binance", "BTCUSDT", t0, 100.0, "contracts", 0.01),
        ]
        async with pool.acquire() as c:
            await c.executemany(
                """INSERT INTO open_interest (exchange, symbol, ts, oi_raw, oi_unit, contract_value)
                   VALUES ($1,$2,$3,$4,$5,$6)""", rows)
        async with BetaStore(pool).connect() as conn:
            got = await conn.fetch_open_interest_asof(
                symbol="BTCUSDT", exchanges=EXS, boundaries=(t0, t))
        assert got[t]["binance"]["oi_raw"] == 110.0
        assert got[t]["bybit"]["oi_raw"] == 50.0
        assert got[t]["okx"] is None
        assert venue_oi_change_pct(got[t0]["binance"], got[t]["binance"]) is None
        await pool.close()
    run(body())


def test_details_tab_check_widens_a_pr1_database_and_stays_idempotent():
    async def body():
        import asyncpg
        pool = await fresh_pool()
        async with pool.acquire() as c:
            await c.execute("ALTER TABLE beta_details_opens DROP CONSTRAINT ck_beta_details_opens_tab")
            await c.execute(
                "ALTER TABLE beta_details_opens ADD CONSTRAINT beta_details_opens_tab_check "
                "CHECK (tab IN ('event', '1h'))")
            await apply_beta_schema(c)
            await apply_beta_schema(c)
        async with BetaStore(pool).connect() as conn:
            pk = await conn.insert_btc_view(
                requested_at=T0, as_of_bucket=None, context_state_digest=None,
                episodization_version=None, episodization_digest=None, payload={"ok": True},
                payload_digest="a" * 64, rendered_sha256="b" * 64, rendered_html="x", lang="ru")
            await conn.insert_details_open(view_pk=pk, tab="24h", lang="ru", opened_at=T0)
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.insert_details_open(view_pk=pk, tab="nope", lang="ru", opened_at=T0)
        async with pool.acquire() as c:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await c.execute("UPDATE beta_details_opens SET lang='en'")
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await c.execute("DELETE FROM beta_details_opens")
        await pool.close()
    run(body())


# --------------------------------------------------------------- product gate and push policy
def test_gate_blocks_pushes_until_the_hour_is_readable_and_records_what_it_saw(monkeypatch):
    """Under the committed config, a TRIGGERED episode on a tape without mature 1h
    ranks is HOUR_NOT_UNUSUAL: nothing is materialized for delivery, and the gate
    record says why (decision §3 row 7)."""
    async def body():
        monkeypatch.setattr(det, "_hour_gate", REAL_HOUR_GATE)
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0, switches=ON_PUSH, cfg=CFG_COMMITTED)
        r = await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, switches=ON_PUSH, cfg=CFG_COMMITTED)
        assert r["processed"][0]["push_decisions"][0][1:] == ("SUPPRESSED", "HOUR_NOT_UNUSUAL")
        pd = await _rows(pool, "SELECT would_push, decision, suppression_reason, gate->>'status' AS st, "
                               "(gate->>'qualified')::boolean AS q FROM beta_push_decisions")
        assert pd == [{"would_push": False, "decision": "SUPPRESSED", "suppression_reason": "HOUR_NOT_UNUSUAL",
                       "st": "CONTEXT_UNAVAILABLE", "q": False}]        # V1 history rows: no 1h window yet
        store = BetaStore(pool)
        async with store.connect() as c:
            assert await c.fetch_undispatched_push_decisions(10) == []
            assert await c.fetch_qualified_hours(symbol="BTCUSDT", start=B0 - timedelta(days=1), end=B0 + timedelta(days=1)) == []
        await pool.close()
    run(body())


def test_push_off_is_a_recipient_preference_with_no_delivery_row():
    async def body():
        from beta.delivery import run_notify_once
        pool = await _setup()
        await _triggered_push(pool)
        async with pool.acquire() as c:
            await c.execute("INSERT INTO beta_users (telegram_user_id, chat_id, status, privacy_accepted_at, joined_at,"
                            " stopped_at, lang, push_enabled) VALUES (13, 13, 'ACTIVE', now(), now(), NULL, 'ru', FALSE)")
        s = FakeSender()
        r = await run_notify_once(BetaStore(pool), CFG, ON_PUSH, sender=s, clock=Clock(B0 + 2 * BUCKET + timedelta(seconds=40)))
        assert r["sent"] == 1 and [x[0] for x in s.sent] == [11]
        rows = await _rows(pool, "SELECT u.telegram_user_id AS uid, x.state FROM beta_notification_deliveries x "
                                 "JOIN beta_users u USING (user_pk) ORDER BY uid")
        assert rows == [{"uid": 11, "state": "SENT"}, {"uid": 12, "state": "SUPPRESSED"}]   # no row for 13
        text = s.sent[0][1]
        assert text.startswith("<b>BTC · unusual hour</b>") and "EV-" not in text and "EVENT" not in text
        await pool.close()
    run(body())


def test_push_command_and_admin_known_flag():
    async def body():
        from runtime.beta_bot import BetaBotHandler
        pool = await _setup()
        h = BetaBotHandler(BetaStore(pool), CFG, switches=lambda: ON, owner_user_id=OWNER, clock=Clock(B0))
        await h.handle(_msg(OWNER, f"/admin_add {ALICE}", 1))
        await h.handle(_msg(ALICE, "/start", 2))
        await h.handle(_cb(ALICE, "pick:en", 3))
        await h.handle(_cb(ALICE, "join:en", 4))
        out = await h.handle(_msg(ALICE, "/push", 5))
        assert out[0].html.startswith("Messages: on") and "• unusual hour: on" in out[0].html
        out = await h.handle(_msg(ALICE, "/push off", 6))
        assert "Messages: off" in out[0].html and "morning briefing is separate" in out[0].html.lower()
        assert (await _rows(pool, "SELECT push_enabled, known_contact FROM beta_users")) == \
            [{"push_enabled": False, "known_contact": False}]
        out = await h.handle(_msg(OWNER, f"/admin_known {ALICE} on", 7))
        assert "known_contact=true" in out[0].html
        assert (await _rows(pool, "SELECT known_contact FROM beta_users")) == [{"known_contact": True}]
        out = await h.handle(_msg(OWNER, "/admin_users", 8))
        assert "known" in out[0].html
        audit = await _rows(pool, "SELECT action, result FROM beta_admin_audit WHERE action='admin_known'")
        assert audit == [{"action": "admin_known", "result": "OK"}]
        acts = [r["action"] for r in await _rows(pool, "SELECT action FROM beta_user_activity ORDER BY activity_pk")]
        assert acts.count("cmd_push") == 2
        # the on/off history is reconstructable from the activity log, not only the current value
        await h.handle(_msg(ALICE, "/push on", 9))
        await h.handle(_msg(ALICE, "/brief off", 10))
        await h.handle(_msg(ALICE, "/brief", 11))
        await h.handle(_msg(ALICE, "/brief on", 12))
        hist = await _rows(pool, "SELECT action, detail FROM beta_user_activity "
                                 "WHERE action IN ('cmd_push', 'cmd_brief') ORDER BY activity_pk")
        assert [(r["action"], r["detail"]) for r in hist] == [
            ("cmd_push", "status"), ("cmd_push", "off"), ("cmd_push", "on"),
            ("cmd_brief", "off"), ("cmd_brief", "status"), ("cmd_brief", "on")]
        assert (await _rows(pool, "SELECT push_enabled, brief_enabled FROM beta_users")) == \
            [{"push_enabled": True, "brief_enabled": True}]
        # per-kind preferences (PRODUCT_DECISION_V2): each switch is its own column and activity detail
        out = await h.handle(_msg(ALICE, "/push levels off", 13))
        assert "• levels (first touch" in out[0].html and "highs and lows): off" in out[0].html
        await h.handle(_msg(ALICE, "/push hour off", 14))
        await h.handle(_msg(ALICE, "/push moves off", 15))
        await h.handle(_msg(ALICE, "/push events off", 16))
        await h.handle(_msg(ALICE, "/push events on", 17))
        assert (await _rows(pool, "SELECT push_enabled, push_levels, push_events, push_moves, push_hours "
                                  "FROM beta_users")) == [{"push_enabled": True, "push_levels": False,
                                                           "push_events": True, "push_moves": False,
                                                           "push_hours": False}]
        details = [r["detail"] for r in await _rows(pool, "SELECT detail FROM beta_user_activity "
                                                          "WHERE action='cmd_push' ORDER BY activity_pk")][3:]
        assert details == ["levels:off", "hours:off", "moves:off", "events:off", "events:on"]
        await pool.close()
    run(body())


# ------------------------------------------------- context/gate SQL errors never abort detection
async def _fail_sql(conn):
    """A real PostgreSQL error on this connection (division by zero)."""
    await conn.conn.execute("SELECT 1/0")


async def _detection_state(pool):
    tape = await _rows(pool, "SELECT bucket_ts, origin FROM beta_state_tape WHERE origin='LIVE' ORDER BY bucket_ts")
    wm = await _rows(pool, "SELECT bucket_ts FROM beta_detector_watermark WHERE runner_name=$1", det.DETECTOR)
    pd = await _rows(pool, "SELECT decision, suppression_reason, gate->>'status' AS st FROM beta_push_decisions")
    eps = await _rows(pool, "SELECT event_type, state FROM beta_episodes ORDER BY episode_pk")
    return tape, wm, pd, eps


def test_sql_error_in_the_context_read_rolls_back_only_its_savepoint(monkeypatch):
    """B1: a real PostgreSQL error inside the bucket's context read (aborted SQL state)
    must not roll back the tape row, the episodes, the push decision or the watermark;
    the gate degrades to CONTEXT_UNAVAILABLE."""
    async def body():
        monkeypatch.setattr(det, "_hour_gate", REAL_HOUR_GATE)
        real = det.context_asof

        async def broken_context_asof(cfg, stage2_config, conn, *a, **kw):
            await _fail_sql(conn)                      # raises; the transaction is now aborted
            return await real(cfg, stage2_config, conn, *a, **kw)
        monkeypatch.setattr(det, "context_asof", broken_context_asof)
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0, switches=ON_PUSH, cfg=CFG_COMMITTED)
        r = await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, switches=ON_PUSH, cfg=CFG_COMMITTED)
        assert r["processed"][-1]["context_error"] == "DivisionByZeroError"
        assert r["processed"][-1]["push_decisions"][0][1:] == ("SUPPRESSED", "HOUR_NOT_UNUSUAL")
        tape, wm, pd, eps = await _detection_state(pool)
        assert [t["bucket_ts"] for t in tape] == [B0, B0 + BUCKET]          # both LIVE rows committed
        assert wm == [{"bucket_ts": B0 + BUCKET}]                           # watermark advanced
        assert pd == [{"decision": "SUPPRESSED", "suppression_reason": "HOUR_NOT_UNUSUAL",
                       "st": "CONTEXT_UNAVAILABLE"}]
        assert eps and all(e["state"] for e in eps)
        await pool.close()
    run(body())


def test_sql_error_in_the_oi_read_leaves_detection_and_the_rest_of_the_context(monkeypatch):
    """B1: the Stage-1 OI range read fails with a real PostgreSQL error; detection still
    commits and the context is computed without OI."""
    async def body():
        from storage.beta_v0_store import BetaConn
        monkeypatch.setattr(det, "_hour_gate", REAL_HOUR_GATE)

        async def broken_oi(self, **_kw):
            await _fail_sql(self)
        monkeypatch.setattr(BetaConn, "fetch_open_interest_range", broken_oi)
        pool = await _setup()
        await _detect(pool, ScenarioReader(down_move), B0, switches=ON_PUSH, cfg=CFG_COMMITTED)
        r = await _detect(pool, ScenarioReader(down_move), B0 + BUCKET, switches=ON_PUSH, cfg=CFG_COMMITTED)
        assert r["processed"][-1]["push_decisions"][0][1:] == ("SUPPRESSED", "HOUR_NOT_UNUSUAL")
        tape, wm, pd, _eps = await _detection_state(pool)
        assert [t["bucket_ts"] for t in tape] == [B0, B0 + BUCKET]
        assert wm == [{"bucket_ts": B0 + BUCKET}]
        assert len(pd) == 1
        await pool.close()
    run(body())


def test_sql_error_in_the_gate_liquidation_read_does_not_abort_the_transaction(monkeypatch):
    """B1: the gate's liquidation-episode read fails with a real PostgreSQL error inside an
    open transaction; the transaction stays usable and later writes commit."""
    async def body():
        from storage.beta_v0_store import BetaConn
        from beta.hour_gate import NOT_UNUSUAL

        async def broken_liq(self, **_kw):
            await _fail_sql(self)
        monkeypatch.setattr(BetaConn, "fetch_liquidation_episodes", broken_liq)
        pool = await _setup(live=False)
        hour = {"window_start": (B0 - timedelta(hours=1)).isoformat(), "window_end": B0.isoformat(),
                "percentiles": {}}
        store = BetaStore(pool)
        async with store.connect() as c:
            async with c.transaction():
                gate = await REAL_HOUR_GATE(c, CFG_COMMITTED, hour, {})
                await c.conn.execute("CREATE TABLE b1_probe (x int)")    # must still run
        assert gate["status"] in ("IMMATURE", NOT_UNUSUAL)
        assert await _rows(pool, "SELECT count(*) AS n FROM b1_probe") == [{"n": 0}]
        await pool.close()
    run(body())
