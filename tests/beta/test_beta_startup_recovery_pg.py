"""Startup-recovery race (2026-10-02 incident) against a real local PostgreSQL
($BETA_TEST_DSN; skipped when unset).

After a host power cycle the persistent detector timer fired before Stage-1's
startup gap-fill had restored the outage's raw 1m bars: the detector caught the
outage buckets up and recorded LIVE rows with NULL kline OHLC that nothing ever
re-read. Incident fixture (UTC, B0 = 22:30): downtime 22:35-22:55, four degraded
buckets 22:35/22:40/22:45/22:50, raw restored (source=backfill) after the
detector's catch-up, 22:55 healthy."""
import json
import re
from datetime import timedelta
from pathlib import Path

import pytest

from beta_fakes import EXS, SYM, TEST_DSN, Clock, ScenarioReader, deps, down_move, run, seed_live_klines
from beta import detector as det
from beta import recovery
from beta.detector import run_detector_once
from beta.health import health_alerts
from beta.market_view import _tape_and_oi
from beta.state_tape import PERCENTILE_HISTORY_SCHEMA_VERSIONS
from storage.beta_v0_store import BetaStore
from test_beta_pg_integration import (B0, BUCKET, CFG, ON, _answer_the_hour_gate, _calc,  # noqa: F401 (autouse)
                                      _rows, _setup)

pytestmark = pytest.mark.skipif(not TEST_DSN, reason="BETA_TEST_DSN not set (local PostgreSQL)")

REPO = Path(__file__).resolve().parents[2]
OUTAGE = [B0 + i * BUCKET for i in range(1, 5)]           # 22:35, 22:40, 22:45, 22:50
HEALTHY_AFTER = B0 + 5 * BUCKET                            # 22:55
BOOT = B0 + timedelta(minutes=26, seconds=49)              # host boot / Stage-1 process start (22:56:49)
FIRST_RUN = B0 + timedelta(minutes=27)                     # persistent timer fires (22:57:00)
STAGE1_ROW = B0 + timedelta(minutes=27, seconds=1)         # infra ready, Stage-1 writes its row (22:57:01)
GAP_FILL_DONE = B0 + timedelta(minutes=27, seconds=11)     # gap-fill finished (22:57:11)
NEXT_RUN = HEALTHY_AFTER + BUCKET + timedelta(seconds=25)  # next timer slot (23:00:25)
REPAIR_ONLY = GAP_FILL_DONE + timedelta(seconds=30)        # a run with no new bucket to decide
OHLC = ("open", "high", "low", "close")
DECISION_TABLES = ("beta_episodes", "beta_episode_transitions", "beta_push_decisions",
                   "beta_notification_deliveries")


class OutageReader(ScenarioReader):
    """Raw bundles carry no 1m bars for an outage bucket until it is restored."""

    def __init__(self, during=None):
        self.restored = False
        during = during or (lambda b: {ex: {"n_bars": 0} for ex in EXS})
        super().__init__(lambda b: during(b) if b in OUTAGE and not self.restored else {})


async def _stage1_recovery(pool, *, started_at, status="running", finished_at=None):
    async with pool.acquire() as c:
        return await c.fetchval(
            "INSERT INTO backfill_runs (exchange, symbol, source, window_start, window_end, status, "
            "started_at, finished_at) VALUES ('*', $1, 'startup_recovery', $2, $2, $3, $2, $4) RETURNING id",
            SYM, started_at, status, finished_at)


async def _finish_stage1_recovery(pool, run_id, *, status="complete", at=GAP_FILL_DONE):
    async with pool.acquire() as c:
        await c.execute("UPDATE backfill_runs SET status=$2, finished_at=$3 WHERE id=$1", run_id, status, at)


async def _restore_raw(pool, reader, buckets=OUTAGE):
    await seed_live_klines(pool, buckets, source="backfill")
    reader.restored = True


async def _run(pool, reader, now, **kw):
    return await run_detector_once(deps(pool, reader, Clock(now), **kw), CFG, ON)


async def _product_rows(pool, buckets):
    """What product history / /catchup read: the newest materialized revision per bucket."""
    rows = await _rows(pool, "SELECT DISTINCT ON (bucket_ts) bucket_ts, origin, revision, metrics "
                             "FROM beta_state_tape WHERE symbol=$1 AND materialized AND bucket_ts = ANY($2) "
                             "ORDER BY bucket_ts, tape_id DESC", SYM, list(buckets))
    return {r["bucket_ts"]: {**r, "metrics": json.loads(r["metrics"])} for r in rows}


def _ohlc_complete(metrics):
    return all(metrics.get(f"x:{ex}:kline_{f}") is not None for ex in EXS for f in OHLC)


async def _chain(pool, buckets):
    return await _rows(pool, "SELECT tape_id, bucket_ts, origin, revision, supersedes_tape_id, feature_digest, "
                             "snapshot_digest, snapshot, metrics FROM beta_state_tape WHERE symbol=$1 "
                             "AND origin <> 'BOOTSTRAP' AND bucket_ts = ANY($2) ORDER BY tape_id",
                       SYM, list(buckets))


async def _counts(pool):
    out = {}
    for t in DECISION_TABLES:
        out[t] = (await _rows(pool, f"SELECT count(*) AS n FROM {t}"))[0]["n"]
    return out


async def _health(pool):
    async with BetaStore(pool).connect() as c:
        return await c.fetch_health()


async def _start(pool):
    await seed_live_klines(pool, [B0])
    await _run(pool, reader=ScenarioReader(), now=B0 + BUCKET + timedelta(seconds=30))


async def _incident_until_gap_fill(pool, reader):
    """Healthy 22:30, power cycle, Stage-1 starts its gap-fill, timer fires, raw restored."""
    await _start(pool)
    run_id = await _stage1_recovery(pool, started_at=BOOT)
    first = await _run(pool, reader, FIRST_RUN)
    await _restore_raw(pool, reader)
    await _finish_stage1_recovery(pool, run_id)
    await seed_live_klines(pool, [HEALTHY_AFTER])
    return run_id, first


async def _degraded_by_race(pool, reader):
    """The residual race the barrier cannot see (and production's 2026-10-02 state):
    the timer fires before Stage-1 has written ANY readiness row for this boot and
    the boot time is unknown, so the detector decides the outage buckets without
    their raw bars; Stage-1 then records its recovery and restores the raw."""
    await _start(pool)
    first = await _run(pool, reader, FIRST_RUN)
    assert first["startup_recovery"]["state"] == recovery.NO_SIGNAL
    assert [r["bucket_ts"] for r in first["processed"]] == OUTAGE
    run_id = await _stage1_recovery(pool, started_at=STAGE1_ROW)
    await _restore_raw(pool, reader)
    await _finish_stage1_recovery(pool, run_id)
    return run_id


# --------------------------------------------------------------------------- 1. reproduction
def test_startup_race_outage_buckets_end_with_raw_ohlc_once_raw_is_restored():
    """The incident end to end: after the next detector run every outage bucket's
    product row carries the restored kline OHLC (on unfixed main they stay NULL)."""
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _incident_until_gap_fill(pool, reader)
        await _run(pool, reader, NEXT_RUN)
        rows = await _product_rows(pool, OUTAGE + [HEALTHY_AFTER])
        assert sorted(rows) == OUTAGE + [HEALTHY_AFTER]
        stale = [b for b in OUTAGE if not _ohlc_complete(rows[b]["metrics"])]
        assert stale == [], f"outage buckets still without raw OHLC: {stale}"
        assert _ohlc_complete(rows[HEALTHY_AFTER]["metrics"])
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 2. barrier
def test_barrier_blocks_catch_up_while_stage1_recovery_is_running():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _start(pool)
        run_id = await _stage1_recovery(pool, started_at=BOOT)
        res = await _run(pool, reader, FIRST_RUN)
        assert res["status"] == "WAITING_FOR_STAGE1_RECOVERY"
        assert res["startup_recovery"]["state"] == recovery.RECOVERING
        assert res["startup_recovery"]["recovery_run_id"] == run_id
        assert reader.calls == []                                  # nothing materialized
        assert await _chain(pool, OUTAGE) == []                    # nothing decided
        wm = await _rows(pool, "SELECT bucket_ts FROM beta_detector_watermark WHERE runner_name='detector'")
        assert wm[0]["bucket_ts"] == B0                            # catch-up deferred, not skipped
        detail = (await _health(pool))["detector"]["detail"]
        assert detail["startup_recovery"]["state"] == recovery.RECOVERING and detail["buckets"] == 0
        # an explicit operator run waits too: it would read the same missing raw
        res = await run_detector_once(deps(pool, reader, Clock(FIRST_RUN)), CFG, ON, explicit_bucket=OUTAGE[0])
        assert res["status"] == "WAITING_FOR_STAGE1_RECOVERY"
        await pool.close()
    run(body())


def test_barrier_previous_boot_row_and_unfinished_recovery_block_until_overdue():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _start(pool)
        old = await _stage1_recovery(pool, started_at=B0 - timedelta(days=1), status="complete",
                                     finished_at=B0 - timedelta(days=1))
        # Stage-1 of THIS boot has not written its row yet: the newest row is a previous boot's.
        res = await _run(pool, reader, FIRST_RUN, host_boot_time=BOOT)
        assert res["startup_recovery"]["state"] == recovery.WAITING_FOR_STAGE1_START
        assert res["startup_recovery"]["recovery_run_id"] == old
        # A recovery that was cancelled (stop during gap-fill) is not ready either.
        cancelled = await _stage1_recovery(pool, started_at=STAGE1_ROW, status="cancelled",
                                           finished_at=GAP_FILL_DONE)
        res = await _run(pool, reader, FIRST_RUN + timedelta(minutes=1), host_boot_time=BOOT)
        assert res["startup_recovery"]["state"] == recovery.NOT_READY
        assert res["startup_recovery"]["recovery_run_id"] == cancelled
        assert await _chain(pool, OUTAGE) == []
        # Bounded: after max_catchup x 5m of waiting the detector proceeds (OVERDUE, alerted).
        late = GAP_FILL_DONE + recovery.max_wait(CFG)
        res = await _run(pool, reader, late, host_boot_time=BOOT)
        assert res["status"] == "OK" and res["startup_recovery"]["state"] == recovery.OVERDUE
        assert res["recovery_repair"] is None                      # no repair without readiness
        assert res["processed"] and res["skipped_buckets"] >= 0
        runtime = await _health(pool)
        keys = {a["key"] for a in health_alerts(CFG, now=late, heartbeat={"healthy": True},
                                                detector_watermark=None, latest_live=None, runtime=runtime,
                                                delivery_problems=None, switches=ON)}
        assert "STAGE1_RECOVERY_NOT_READY" in keys
        await pool.close()
    run(body())


def test_barrier_bound_survives_a_stage1_crash_loop():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _start(pool)
        states, now = [], FIRST_RUN
        while now <= BOOT + recovery.max_wait(CFG) + 2 * BUCKET:
            await _stage1_recovery(pool, started_at=now - timedelta(seconds=5))    # a fresh restart each time
            res = await _run(pool, reader, now, host_boot_time=BOOT)
            states.append(res["startup_recovery"]["state"])
            if res["status"] == "OK":
                break
            now += BUCKET
        assert states[0] == recovery.RECOVERING and states[-1] == recovery.OVERDUE
        assert set(states[:-1]) == {recovery.RECOVERING}
        assert now - BOOT <= recovery.max_wait(CFG) + BUCKET
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 3. after READY
def test_after_ready_catch_up_proceeds_normally_with_the_restored_raw():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        run_id, first = await _incident_until_gap_fill(pool, reader)
        assert first["status"] == "WAITING_FOR_STAGE1_RECOVERY"
        res = await _run(pool, reader, NEXT_RUN, host_boot_time=BOOT)
        assert res["status"] == "OK" and res["startup_recovery"]["state"] == recovery.READY
        assert [r["bucket_ts"] for r in res["processed"]] == OUTAGE + [HEALTHY_AFTER]
        assert res["skipped_buckets"] == 0
        chain = await _chain(pool, OUTAGE + [HEALTHY_AFTER])
        assert [(c["origin"], c["revision"]) for c in chain] == [("LIVE", 1)] * 5   # no correction needed
        assert all(_ohlc_complete(json.loads(c["metrics"])) for c in chain)
        assert res["recovery_repair"]["status"] == "DONE" and res["recovery_repair"]["degraded"] == 0
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 4-8. repair
def test_late_raw_is_repaired_by_an_appended_correction_and_the_live_row_is_untouched():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        run_id = await _degraded_by_race(pool, reader)
        live_before = await _chain(pool, OUTAGE)
        assert [c["origin"] for c in live_before] == ["LIVE"] * 4
        assert not any(_ohlc_complete(json.loads(c["metrics"])) for c in live_before)
        await seed_live_klines(pool, [HEALTHY_AFTER])
        res = await _run(pool, reader, NEXT_RUN)
        rep = res["recovery_repair"]
        assert (rep["status"], rep["recovery_run_id"], rep["degraded"], rep["appended"], rep["unchanged"],
                rep["failed"]) == ("DONE", run_id, 4, 4, 0, 0)
        chain = await _chain(pool, OUTAGE)
        live_after = [c for c in chain if c["origin"] == "LIVE"]
        assert live_after == live_before                                    # 5. byte-identical LIVE rows
        corr = {c["bucket_ts"]: c for c in chain if c["origin"] == "CORRECTION_CHECK"}
        assert sorted(corr) == OUTAGE
        by_bucket = {c["bucket_ts"]: c for c in live_before}
        for b, c in corr.items():                                           # 4. appended revision with OHLC
            assert c["revision"] == 2 and c["supersedes_tape_id"] == by_bucket[b]["tape_id"]
            assert _ohlc_complete(json.loads(c["metrics"]))
            snap = json.loads(c["snapshot"])
            assert snap["origin"] == "CORRECTION_CHECK"
            for ex in EXS:                                                  # 8. backfill stays backfill
                v = snap["venues"][ex]
                assert (v["bars"], v["live_bars"], v["heartbeat_healthy"]) == (5, 0, False)
                assert snap["metrics"][f"x:{ex}:long_liquidation_notional"] is None
        sources = await _rows(pool, "SELECT DISTINCT source FROM klines_1m WHERE ts >= $1 AND ts < $2",
                              OUTAGE[0], OUTAGE[-1] + BUCKET)
        assert [s["source"] for s in sources] == ["backfill"]
        marker = (await _health(pool))[recovery.REPAIR_COMPONENT]
        assert marker["detail"]["recovery_run_id"] == run_id and marker["detail"]["complete"] is True
        await pool.close()
    run(body())


def test_product_history_and_catchup_read_the_repaired_revision():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _degraded_by_race(pool, reader)
        await seed_live_klines(pool, [HEALTHY_AFTER])
        await _run(pool, reader, NEXT_RUN)
        corr = {c["bucket_ts"]: json.loads(c["metrics"]) for c in await _chain(pool, OUTAGE)
                if c["origin"] == "CORRECTION_CHECK"}
        # /btc and /catchup: the one tape-history read of the shared view builder
        tape = None
        async with BetaStore(pool).connect() as conn:
            tape = await _tape_and_oi(conn, CFG, {"product_status": "NO ACTIVE EVENTS",
                                                  "as_of_bucket": HEALTHY_AFTER.isoformat()}, window_hours=1)
            calc = (await _rows(pool, "SELECT calculation_version FROM beta_state_tape "
                                      "WHERE origin='LIVE' LIMIT 1"))[0]["calculation_version"]
            hist = dict(await conn.fetch_tape_history(
                symbol=SYM, market_type=CFG.market_type, timeframe=CFG.timeframe, calculation_version=calc,
                state_schema_versions=PERCENTILE_HISTORY_SCHEMA_VERSIONS[CFG.state_schema_version],
                start=OUTAGE[0], end=HEALTHY_AFTER))
        for b in OUTAGE:
            assert tape["metrics"][b] == corr[b] and _ohlc_complete(tape["metrics"][b])
            assert hist[b] == corr[b]
        await pool.close()
    run(body())


def test_repair_creates_no_episode_transition_push_decision_or_notification():
    async def body():
        pool = await _setup(live=False)
        # The outage buckets qualify (features from the raw bundle) so the degraded
        # LIVE rows DID open/advance an episode; the repair must not add to that.
        reader = OutageReader(during=down_move)
        run_id = await _degraded_by_race(pool, reader)
        before = await _counts(pool)
        assert before["beta_episodes"] >= 1 and before["beta_episode_transitions"] >= 1
        eps_before = await _rows(pool, "SELECT episode_pk, public_id, state, last_bucket, opening_tape_digest, "
                                       "trigger_tape_digest FROM beta_episodes ORDER BY episode_pk")
        res = await _run(pool, reader, REPAIR_ONLY)                 # no new bucket to decide
        assert res["processed"] == [] and res["recovery_repair"]["appended"] == 4
        assert await _counts(pool) == before
        assert await _rows(pool, "SELECT episode_pk, public_id, state, last_bucket, opening_tape_digest, "
                                 "trigger_tape_digest FROM beta_episodes ORDER BY episode_pk") == eps_before
        flags = await _rows(pool, "SELECT correction_flag, correction_note FROM beta_episodes")
        assert all(f["correction_flag"] for f in flags)             # annotated, never rewritten
        assert res["recovery_repair"]["recovery_run_id"] == run_id
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 9. normal path
def test_normal_path_is_unchanged_by_a_ready_stage1_signal():
    async def detect(with_signal):
        pool = await _setup()
        if with_signal:
            await _stage1_recovery(pool, started_at=B0 - timedelta(days=2), status="complete",
                                   finished_at=B0 - timedelta(days=2))
        reports = [await _run(pool, ScenarioReader(down_move), b + BUCKET + timedelta(seconds=30))
                   for b in (B0, B0 + BUCKET, B0 + 2 * BUCKET)]
        tape = await _rows(pool, "SELECT bucket_ts, origin, revision, feature_digest, snapshot_digest "
                                 "FROM beta_state_tape WHERE origin <> 'BOOTSTRAP' ORDER BY tape_id")
        tr = await _rows(pool, "SELECT from_state, to_state, reason, snapshot_digest FROM beta_episode_transitions "
                               "ORDER BY seq")
        pd = await _rows(pool, "SELECT decision, suppression_reason FROM beta_push_decisions ORDER BY 1, 2")
        await pool.close()
        return reports, tape, tr, pd

    async def body():
        r0, tape0, tr0, pd0 = await detect(False)
        r1, tape1, tr1, pd1 = await detect(True)
        assert [r["startup_recovery"]["state"] for r in r0] == [recovery.NO_SIGNAL] * 3
        assert [r["startup_recovery"]["state"] for r in r1] == [recovery.READY] * 3
        assert [r["processed"] for r in r0] == [r["processed"] for r in r1]
        assert (tape0, tr0, pd0) == (tape1, tr1, pd1)
        assert {t["origin"] for t in tape1} == {"LIVE"} and tr1
        assert r1[0]["recovery_repair"]["degraded"] == 0
        assert r1[1]["recovery_repair"]["status"] == "ALREADY_DONE"
    run(body())


# --------------------------------------------------------------------------- 10. bounded
def test_repair_is_bounded_to_the_recovery_window_and_per_run_cap(monkeypatch):
    async def body():
        pool = await _setup(live=False)
        reader = ScenarioReader()
        await _run(pool, reader, B0 + BUCKET + timedelta(seconds=30))           # B0 decided with no raw
        for i in range(1, 15):
            b = B0 + i * BUCKET
            await seed_live_klines(pool, [b], exchanges=EXS[:2] if i >= 11 else EXS)
            await _run(pool, reader, b + BUCKET + timedelta(seconds=30))
        await seed_live_klines(pool, [B0], source="backfill")                  # late raw, far outside
        await seed_live_klines(pool, [B0 + i * BUCKET for i in range(11, 15)], exchanges=EXS[2:],
                               source="backfill")                              # late raw, inside
        started = B0 + timedelta(minutes=76)
        run_id = await _stage1_recovery(pool, started_at=started, status="complete",
                                        finished_at=started + timedelta(seconds=20))
        start, end = recovery.repair_window({"started_at": started, "finished_at": started}, max_catchup=12)
        assert (start, end) == (B0 + 3 * BUCKET, B0 + 15 * BUCKET)
        monkeypatch.setattr(det, "REPAIR_MAX_BUCKETS_PER_RUN", 3)
        now = started + timedelta(seconds=50)
        res = await _run(pool, reader, now)
        assert res["processed"] == []
        rep = res["recovery_repair"]
        assert (rep["status"], rep["degraded"], rep["appended"], rep["deferred"]) == ("INCOMPLETE", 4, 3, 1)
        res = await _run(pool, reader, now + timedelta(seconds=5))
        rep = res["recovery_repair"]
        assert (rep["status"], rep["degraded"], rep["appended"], rep["deferred"]) == ("DONE", 1, 1, 0)
        corr = await _rows(pool, "SELECT bucket_ts FROM beta_state_tape WHERE origin='CORRECTION_CHECK' "
                                 "ORDER BY bucket_ts")
        assert [c["bucket_ts"] for c in corr] == [B0 + i * BUCKET for i in range(11, 15)]   # never B0
        assert rep["recovery_run_id"] == run_id
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 11. idempotent
def test_repeated_runs_are_idempotent():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _degraded_by_race(pool, reader)
        first = await _run(pool, reader, REPAIR_ONLY)
        assert first["recovery_repair"]["appended"] == 4
        tape = await _rows(pool, "SELECT tape_id FROM beta_state_tape ORDER BY tape_id")
        again = await _run(pool, reader, REPAIR_ONLY + timedelta(seconds=5))
        assert again["recovery_repair"]["status"] == "ALREADY_DONE"
        # even with the done marker gone, the re-check finds nothing left to repair
        async with BetaStore(pool).connect() as c:
            await c.record_health(recovery.REPAIR_COMPONENT, now=REPAIR_ONLY, success=True, detail={})
        third = await _run(pool, reader, REPAIR_ONLY + timedelta(seconds=10))
        rep = third["recovery_repair"]
        assert (rep["status"], rep["degraded"], rep["appended"]) == ("DONE", 0, 0)
        async with BetaStore(pool).connect() as c:
            for b in OUTAGE:                    # and an explicit re-check of a repaired bucket is UNCHANGED
                assert (await det._correction_check(deps(pool, reader, Clock(REPAIR_ONLY)), CFG, b)
                        )["status"] == "UNCHANGED"
        assert await _rows(pool, "SELECT tape_id FROM beta_state_tape ORDER BY tape_id") == tape
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- 12. crash-safe
class _Crash(BaseException):
    """A process death mid-repair (not an Exception: nothing may catch it)."""


def test_crash_or_failure_mid_repair_is_safe_and_resumes(monkeypatch):
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        run_id = await _degraded_by_race(pool, reader)
        real, calls = det._correction_check, []

        async def crashing(deps_, cfg, b):
            calls.append(b)
            if len(calls) == 3:
                raise _Crash()
            return await real(deps_, cfg, b)

        monkeypatch.setattr(det, "_correction_check", crashing)
        with pytest.raises(_Crash):
            await _run(pool, reader, REPAIR_ONLY)
        corr = await _rows(pool, "SELECT bucket_ts FROM beta_state_tape WHERE origin='CORRECTION_CHECK'")
        assert sorted(c["bucket_ts"] for c in corr) == OUTAGE[:2]      # committed per bucket
        assert recovery.REPAIR_COMPONENT not in await _health(pool)    # no done marker

        async def failing(deps_, cfg, b):                              # an ordinary failure is counted
            if b == OUTAGE[2]:
                raise RuntimeError("synthetic")
            return await real(deps_, cfg, b)

        monkeypatch.setattr(det, "_correction_check", failing)
        res = await _run(pool, reader, REPAIR_ONLY + timedelta(seconds=5))
        rep = res["recovery_repair"]
        assert (rep["status"], rep["degraded"], rep["appended"], rep["failed"]) == ("INCOMPLETE", 2, 1, 1)
        runtime = await _health(pool)
        assert runtime[recovery.REPAIR_COMPONENT]["last_error_type"] == "REPAIR_FAILED"
        keys = {a["key"] for a in health_alerts(CFG, now=REPAIR_ONLY, heartbeat={"healthy": True},
                                                detector_watermark=None, latest_live=None, runtime=runtime,
                                                delivery_problems=None, switches=ON)}
        assert "STARTUP_RECOVERY_REPAIR_INCOMPLETE" in keys

        monkeypatch.setattr(det, "_correction_check", real)
        res = await _run(pool, reader, REPAIR_ONLY + timedelta(seconds=10))
        rep = res["recovery_repair"]
        assert (rep["status"], rep["degraded"], rep["appended"], rep["failed"]) == ("DONE", 1, 1, 0)
        corr = await _rows(pool, "SELECT bucket_ts, count(*) AS n FROM beta_state_tape "
                                 "WHERE origin='CORRECTION_CHECK' GROUP BY 1 ORDER BY 1")
        assert [(c["bucket_ts"], c["n"]) for c in corr] == [(b, 1) for b in OUTAGE]
        assert rep["recovery_run_id"] == run_id
        await pool.close()
    run(body())


# --------------------------------------------------------------------------- smoke
async def _smoke(pool, deploy_ts):
    sql = (REPO / "deploy" / "signalbot-beta-smoke.sql").read_text(encoding="utf-8")
    body = sql.split("BEGIN TRANSACTION READ ONLY;", 1)[1].rsplit("COMMIT;", 1)[0].strip().rstrip(";")
    body = (body.replace(":'deploy_ts'", f"'{deploy_ts.isoformat()}'")
                .replace(":'d7_enabled'", "'false'").replace(":'d7_deploy_ts'", "''"))
    assert not re.search(r":'\w+'", body)
    async with pool.acquire() as c:
        # the smoke reads Stage-1 columns the minimal test schema does not carry
        await c.execute("ALTER TABLE klines_1m ADD COLUMN IF NOT EXISTS taker_buy_volume DOUBLE PRECISION, "
                        "ADD COLUMN IF NOT EXISTS taker_sell_volume DOUBLE PRECISION; "
                        "ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS source TEXT; "
                        "CREATE TABLE IF NOT EXISTS liquidations (id BIGSERIAL, exchange TEXT NOT NULL, "
                        "symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL, side TEXT NOT NULL, "
                        "price DOUBLE PRECISION NOT NULL, qty DOUBLE PRECISION NOT NULL, notional DOUBLE PRECISION, "
                        "is_snapshot_feed BOOLEAN NOT NULL DEFAULT FALSE, PRIMARY KEY (id, ts))")
        rows = await c.fetch(body)
    return [(r["status"], r["detail"]) for r in rows if r["section"] == "I. Startup recovery"]


def test_smoke_detects_raw_recovered_but_tape_still_stale_and_clears_after_repair():
    async def body():
        pool = await _setup(live=False)
        reader = OutageReader()
        await _degraded_by_race(pool, reader)
        before = await _smoke(pool, B0)
        stale = [s for s in before if "raw recovered, tape stale" in s[1]]
        assert stale[0][0] == "FAIL" and "buckets=4" in stale[0][1]
        assert any(s[0] == "PASS" and "status=complete" in s[1] for s in before)
        await _run(pool, reader, REPAIR_ONLY)
        after = await _smoke(pool, B0)
        assert [s[0] for s in after if "raw recovered, tape stale" in s[1]] == ["PASS"]
        await pool.close()
    run(body())
