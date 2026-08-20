"""Real-PostgreSQL proof of `storage/v2_version_switch_readers.py` +
`Database.evaluate_v2_version_switch`'s atomicity/concurrency semantics
(V2-H2b, `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.1).

Deliberately NOT a FakeConn/SQL-string-inspection test — the whole point of
this suite is real PostgreSQL `SELECT ... FOR UPDATE` row-locking and real
transaction rollback behavior, which a mocked connection cannot exercise.
Mirrors `tests/storage/test_klines_no_downgrade.py`'s established pattern
exactly: per-test uniquely-named schema (never the connection's shared
default), one `asyncio.run()` per test (asyncpg pools are bound to the loop
that created them), and a `V2_VERSION_SWITCH_TEST_DSN` env var with the
identical fail-vs-skip contract (unset -> best-effort SKIP on connection
failure; explicitly set, as CI does -- a connection/setup failure is a
genuine FAILURE, never a silent skip).

The table DDL below is a hand-copied, column-for-column mirror of
`storage/stage2_schema.sql`'s real `v2_version_switch_state` definition --
deliberately NOT the real `Database.init_stage2_schema()` (which would also
attempt `CREATE EXTENSION IF NOT EXISTS timescaledb` and several
`create_hypertable()` calls for unrelated Stage 2 tables neither this test
nor a vanilla `postgres:16` CI image can satisfy), matching exactly why
`test_klines_no_downgrade.py` does the same for `klines_1m`."""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from analytics.forecasting_v2.alignment import selected_bucket
from analytics.forecasting_v2.version_switch import (
    ACTION_ACTIVATED, ACTION_DRAIN_COMPLETE, ACTION_DRAIN_CONTINUES,
    ACTION_NO_OP, PHASE_AWAITING_ACTIVATION_READINESS, PHASE_DRAINING,
    PHASE_NO_PENDING_SWITCH, V2DrainFact, V2SemanticTuple,
)
from storage.db import Database

_EXPLICIT_DSN = os.environ.get("V2_VERSION_SWITCH_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

# Column-for-column mirror of storage/stage2_schema.sql's real
# v2_version_switch_state definition -- see module docstring for why this
# is hand-copied rather than applied via init_stage2_schema().
_V2_VERSION_SWITCH_STATE_DDL = """
CREATE TABLE v2_version_switch_state (
    run_kind                       TEXT NOT NULL,
    run_id                         TEXT NOT NULL,

    active_rules_version           TEXT,
    active_calculation_version     TEXT,
    active_decision_code_version   TEXT,

    pending_rules_version          TEXT,
    pending_calculation_version    TEXT,
    pending_decision_code_version  TEXT,

    phase                          TEXT NOT NULL,
    drain_complete_at              TIMESTAMPTZ,
    requested_at                   TIMESTAMPTZ,

    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (run_kind, run_id),

    CONSTRAINT ck_v2vss_run_kind CHECK (run_kind IN ('LIVE','REPLAY')),
    CONSTRAINT ck_v2vss_run_id   CHECK (length(btrim(run_id)) > 0),

    CONSTRAINT ck_v2vss_phase
        CHECK (phase IN ('NO_PENDING_SWITCH','DRAINING','AWAITING_ACTIVATION_READINESS')),

    CONSTRAINT ck_v2vss_active_all_or_none CHECK (
        (active_rules_version IS NULL AND active_calculation_version IS NULL
             AND active_decision_code_version IS NULL)
        OR
        (active_rules_version IS NOT NULL AND active_calculation_version IS NOT NULL
             AND active_decision_code_version IS NOT NULL)
    ),
    CONSTRAINT ck_v2vss_pending_all_or_none CHECK (
        (pending_rules_version IS NULL AND pending_calculation_version IS NULL
             AND pending_decision_code_version IS NULL)
        OR
        (pending_rules_version IS NOT NULL AND pending_calculation_version IS NOT NULL
             AND pending_decision_code_version IS NOT NULL)
    ),

    CONSTRAINT ck_v2vss_active_rules_version_format CHECK (
        active_rules_version IS NULL OR
        active_rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$'),
    CONSTRAINT ck_v2vss_pending_rules_version_format CHECK (
        pending_rules_version IS NULL OR
        pending_rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$'),

    CONSTRAINT ck_v2vss_active_calc_version_format
        CHECK (active_calculation_version IS NULL OR active_calculation_version ~ '^[0-9a-f]{16}$'),
    CONSTRAINT ck_v2vss_pending_calc_version_format
        CHECK (pending_calculation_version IS NULL OR pending_calculation_version ~ '^[0-9a-f]{16}$'),

    CONSTRAINT ck_v2vss_active_decision_code_version_nonblank CHECK (
        active_decision_code_version IS NULL OR length(btrim(active_decision_code_version)) > 0),
    CONSTRAINT ck_v2vss_pending_decision_code_version_nonblank CHECK (
        pending_decision_code_version IS NULL OR length(btrim(pending_decision_code_version)) > 0),

    CONSTRAINT ck_v2vss_no_pending_switch_shape CHECK (
        phase <> 'NO_PENDING_SWITCH' OR
        (pending_rules_version IS NULL AND drain_complete_at IS NULL AND requested_at IS NULL)
    ),
    CONSTRAINT ck_v2vss_pending_requires_requested_at CHECK (
        phase = 'NO_PENDING_SWITCH' OR
        (pending_rules_version IS NOT NULL AND requested_at IS NOT NULL)
    ),
    CONSTRAINT ck_v2vss_draining_no_drain_complete_at
        CHECK (phase <> 'DRAINING' OR drain_complete_at IS NULL),
    CONSTRAINT ck_v2vss_awaiting_requires_drain_complete_at
        CHECK (phase <> 'AWAITING_ACTIVATION_READINESS' OR drain_complete_at IS NOT NULL),
    CONSTRAINT ck_v2vss_drain_complete_at_not_before_requested_at
        CHECK (drain_complete_at IS NULL OR requested_at IS NULL OR drain_complete_at >= requested_at),

    CONSTRAINT ck_v2vss_pending_distinct_from_active CHECK (
        pending_rules_version IS NULL OR active_rules_version IS NULL OR
        (pending_rules_version, pending_calculation_version, pending_decision_code_version)
            IS DISTINCT FROM
        (active_rules_version, active_calculation_version, active_decision_code_version)
    )
);
"""

UTC = timezone.utc
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
T0 = datetime(2026, 8, 20, 0, 0, tzinfo=UTC)
RUN_KIND = "LIVE"
RUN_ID = "v2-shadow-live"

OLD = V2SemanticTuple(
    rules_version="v2-rules-v0.1.0", calculation_version="a" * 16,
    decision_code_version="decision-code-1")
NEW = V2SemanticTuple(
    rules_version="v2-rules-v0.2.0", calculation_version="b" * 16,
    decision_code_version="decision-code-2")


def _t(n: int) -> datetime:
    return T0 + timedelta(minutes=5 * n)


def _scoped_dsn(base_dsn: str, schema: str) -> str:
    parts = urllib.parse.urlsplit(base_dsn)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-csearch_path={schema}"))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def _connect_admin() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(BASE_DSN, timeout=3)
    except Exception as exc:  # noqa: BLE001
        if _EXPLICIT_DSN:
            raise
        pytest.skip(f"no reachable PostgreSQL test server at {BASE_DSN!r}: {exc}")
        raise AssertionError("unreachable")  # pragma: no cover


def _unique_schema_name() -> str:
    return "v2vss_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_switch_table(body):
    """Create a fresh, uniquely-named schema, connect `Database` to it,
    create ONE `v2_version_switch_state` table inside that schema, run
    `body(db, scoped_dsn)`, then unconditionally drop that exact schema --
    all inside the SAME event loop (mirrors
    `test_klines_no_downgrade.py::_with_isolated_klines_table` exactly)."""
    schema = _unique_schema_name()
    admin = await _connect_admin()
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
    finally:
        await admin.close()

    scoped_dsn = _scoped_dsn(BASE_DSN, schema)
    db = Database(scoped_dsn)
    await db.connect()
    try:
        async with db.pool.acquire() as conn:
            await conn.execute(_V2_VERSION_SWITCH_STATE_DDL)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body):
    asyncio.run(_with_isolated_switch_table(body))


class _NeverCalledReadinessReader:
    async def fetch_v2_consensus_percentile_window(self, **kw):
        raise AssertionError("readiness must not be queried in this scenario")


class _ReadyReadinessReader:
    """Ready for whatever requirement/decision_boundary/calculation_version
    it is asked about -- this suite proves DB atomicity/concurrency, not
    H2a's own readiness logic (already covered elsewhere)."""
    async def fetch_v2_consensus_percentile_window(self, **kw):
        bucket = selected_bucket(kw["timeframe"], kw["bucket_start"])
        return ({"bucket_ts": bucket, "value": 1.0, "percentile_rank": 0.5,
                 "confidence_tier": "mature"},)


class _FixedDrainReader:
    def __init__(self, fact: V2DrainFact):
        self._fact = fact

    async def fetch_v2_version_drain_status(self, **kw):
        return self._fact


# ============================================================================
# 1. bootstrap creates the NO_PENDING_SWITCH row
# ============================================================================
def test_bootstrap_creates_no_pending_switch_row():
    async def body(db, _dsn):
        result = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(0),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=None,
            readiness_reader=_NeverCalledReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert result.action == ACTION_NO_OP
        assert result.state.phase == PHASE_NO_PENDING_SWITCH
        assert result.state.active is None

    _run(body)


# ============================================================================
# 2. full flow persists across a real "process restart" (a fresh Database
#    instance against the SAME schema)
# ============================================================================
def test_full_flow_persists_across_restart_drain_then_activate():
    async def body(db, scoped_dsn):
        r1 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(0),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=OLD,
            readiness_reader=_NeverCalledReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert r1.action == ACTION_DRAIN_COMPLETE  # bootstrap: vacuous OLD, already drained.

        r2 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(1),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=None,
            readiness_reader=_ReadyReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert r2.action == ACTION_ACTIVATED
        assert r2.state.active == OLD

        # Request a switch to NEW while OLD still has one lingering episode.
        r3 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(2),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=NEW,
            readiness_reader=_NeverCalledReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(1, 0)))
        assert r3.action == ACTION_DRAIN_CONTINUES
        assert r3.state.phase == PHASE_DRAINING

        # "Restart": a genuinely FRESH Database instance/connection pool
        # against the SAME underlying schema.
        restarted = Database(scoped_dsn)
        await restarted.connect()
        try:
            r4 = await restarted.evaluate_v2_version_switch(
                run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(3),
                symbol=SYMBOL, market_type=MARKET_TYPE, requested=None,
                readiness_reader=_NeverCalledReadinessReader(),
                drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
            assert r4.action == ACTION_DRAIN_COMPLETE
            assert r4.state.phase == PHASE_AWAITING_ACTIVATION_READINESS
            assert r4.state.pending == NEW  # never cancelled/reset by "restart".

            r5 = await restarted.evaluate_v2_version_switch(
                run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(4),
                symbol=SYMBOL, market_type=MARKET_TYPE, requested=None,
                readiness_reader=_ReadyReadinessReader(),
                drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
            assert r5.action == ACTION_ACTIVATED
            assert r5.state.active == NEW
        finally:
            await restarted.close()

    _run(body)


# ============================================================================
# 3. concurrency: two racing evaluations of the SAME execution_stream
#    serialize via real row locking (vectors 9/13)
# ============================================================================
def test_concurrent_evaluations_serialize_never_duplicate_transition():
    async def body(db, _dsn):
        r1 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(0),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=OLD,
            readiness_reader=_NeverCalledReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert r1.action == ACTION_DRAIN_COMPLETE
        r2 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(1),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=None,
            readiness_reader=_ReadyReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert r2.action == ACTION_ACTIVATED

        async def _attempt():
            return await db.evaluate_v2_version_switch(
                run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(2),
                symbol=SYMBOL, market_type=MARKET_TYPE, requested=NEW,
                readiness_reader=_NeverCalledReadinessReader(),
                drain_reader=_FixedDrainReader(V2DrainFact(1, 0)))

        results = await asyncio.gather(_attempt(), _attempt())
        accepted_flags = sorted(r.request_accepted for r in results)
        assert accepted_flags == [False, True], (
            "exactly one concurrent call must accept the request; the other must "
            "observe the already-pending identical target as idempotent")
        assert results[0].state.pending == NEW
        assert results[1].state.pending == NEW
        assert results[0].state.phase == results[1].state.phase == PHASE_DRAINING

    _run(body)


# ============================================================================
# 4. atomicity: a failure mid-transaction leaves no partial state (vector 14)
# ============================================================================
def test_transaction_failure_leaves_no_partial_activation_state():
    async def body(db, _dsn):
        r1 = await db.evaluate_v2_version_switch(
            run_kind=RUN_KIND, run_id=RUN_ID, decision_boundary=_t(0),
            symbol=SYMBOL, market_type=MARKET_TYPE, requested=OLD,
            readiness_reader=_NeverCalledReadinessReader(),
            drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
        assert r1.action == ACTION_DRAIN_COMPLETE
        before = r1.state

        from analytics.forecasting_v2.version_switch import ACTION_ACTIVATED as _ACTIVATED
        from analytics.forecasting_v2.version_switch_orchestrator import (
            resolve_version_switch_transition)
        from storage.v2_version_switch_readers import (
            bootstrap_and_lock_v2_version_switch_state, persist_v2_version_switch_state)

        class _Boom(RuntimeError):
            pass

        with pytest.raises(_Boom):
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    state = await bootstrap_and_lock_v2_version_switch_state(
                        conn, run_kind=RUN_KIND, run_id=RUN_ID)
                    result = await resolve_version_switch_transition(
                        state=state, decision_boundary=_t(1), symbol=SYMBOL,
                        market_type=MARKET_TYPE, requested=None,
                        readiness_reader=_ReadyReadinessReader(),
                        drain_reader=_FixedDrainReader(V2DrainFact(0, 0)))
                    assert result.action == _ACTIVATED  # would-be activation.
                    await persist_v2_version_switch_state(conn, result.state)
                    raise _Boom("simulated failure after write, before commit")

        # Re-read: must still show the PRE-failure state -- the attempted
        # activation must be entirely invisible.
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                reread = await bootstrap_and_lock_v2_version_switch_state(
                    conn, run_kind=RUN_KIND, run_id=RUN_ID)
        assert reread == before
        assert reread.phase == PHASE_AWAITING_ACTIVATION_READINESS
        assert reread.active is None

    _run(body)
