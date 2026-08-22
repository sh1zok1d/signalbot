"""Real-PostgreSQL proof of `Database.insert_v2_episode_events`'s V2-H3
atomicity/idempotency/concurrency semantics
(docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a).

Deliberately NOT a FakeConn/SQL-string-inspection test (that suite is
`tests/storage/test_v2_episode_event_writers.py`) — the whole point of this
suite is real PostgreSQL transaction/rollback/concurrency/`UNIQUE`-
constraint behavior, which a mocked connection cannot exercise. Mirrors
`tests/storage/test_v2_version_switch_readers.py`'s established pattern
exactly: per-test uniquely-named schema (never the connection's shared
default), one `asyncio.run()` per test (asyncpg pools are bound to the loop
that created them), and a `V2_EPISODE_EVENT_TEST_DSN` env var with the
identical fail-vs-skip contract (unset -> best-effort SKIP on connection
failure; explicitly set, as CI does -- a connection/setup failure is a
genuine FAILURE, never a silent skip).

The table DDL below is a hand-copied, column-for-column mirror of
`storage/stage2_schema.sql`'s real `v2_episode_events` definition --
deliberately NOT the real `Database.init_stage2_schema()` (which would also
attempt `CREATE EXTENSION IF NOT EXISTS timescaledb` and several
`create_hypertable()` calls for unrelated Stage 2 tables neither this test
nor a vanilla `postgres:16` CI image can satisfy), matching exactly why
`test_klines_no_downgrade.py`/`test_v2_version_switch_readers.py` do the
same.
"""
from __future__ import annotations

import asyncio
import os
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from analytics.forecasting_v2.episode_identity import compute_episode_id, compute_event_id
from analytics.forecasting_v2.events import (
    COMPRESSION_BREAKOUT, CONFIRMED, EARLY_SIGNAL, LIVE, LONG, REPLAY, SHORT,
    TREND_PULLBACK, V2EpisodeEvent,
)
from common.v2_config import MODEL_FAMILY
from storage.db import Database
from storage.v2_serialization import V2EventBatchScopeError, V2EventIdentityConflictError
from tests.storage.test_v2_episode_event_schema import (
    _V2EE_BODY as _REAL_V2EE_BODY,
    _V2EE_SECTION as _REAL_V2EE_SECTION,
    _columns as _real_schema_columns,
    _pk as _real_schema_pk,
)

_EXPLICIT_DSN = os.environ.get("V2_EPISODE_EVENT_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

# Column-for-column mirror of storage/stage2_schema.sql's real
# v2_episode_events definition (including V2-H3's decision_code_version
# column, its two hash-format CHECKs, and the new UNIQUE index) -- see
# module docstring for why this is hand-copied rather than applied via
# init_stage2_schema().
_V2_EPISODE_EVENTS_DDL = """
CREATE TABLE v2_episode_events (
    run_kind               TEXT NOT NULL,
    run_id                 TEXT NOT NULL,
    event_id               TEXT NOT NULL,
    episode_id             TEXT NOT NULL,

    model_family           TEXT NOT NULL,
    rules_version          TEXT NOT NULL,

    symbol                 TEXT NOT NULL,
    market_type            TEXT NOT NULL,
    direction              TEXT NOT NULL,
    setup_family           TEXT NOT NULL,
    structural_anchor      JSONB NOT NULL,

    episode_state          TEXT NOT NULL,
    decision_boundary      TIMESTAMPTZ NOT NULL,

    feature_schema_version INTEGER NOT NULL,
    calculation_version    TEXT NOT NULL,
    config_hash            TEXT NOT NULL,
    config_version         TEXT NOT NULL,
    code_version           TEXT NOT NULL,
    decision_code_version  TEXT NOT NULL,

    decision_snapshot      JSONB NOT NULL,
    event_payload          JSONB NOT NULL,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (run_kind, run_id, event_id),

    CONSTRAINT ck_v2ee_run_kind
        CHECK (run_kind IN ('LIVE','REPLAY')),
    CONSTRAINT ck_v2ee_run_id       CHECK (length(btrim(run_id)) > 0),
    CONSTRAINT ck_v2ee_event_id     CHECK (length(btrim(event_id)) > 0),
    CONSTRAINT ck_v2ee_episode_id   CHECK (length(btrim(episode_id)) > 0),
    CONSTRAINT ck_v2ee_event_id_hash_format
        CHECK (event_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_v2ee_episode_id_hash_format
        CHECK (episode_id ~ '^[0-9a-f]{64}$'),

    CONSTRAINT ck_v2ee_model_family
        CHECK (model_family = 'v2'),
    CONSTRAINT ck_v2ee_rules_version
        CHECK (rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$'),

    CONSTRAINT ck_v2ee_symbol       CHECK (symbol = 'BTCUSDT'),
    CONSTRAINT ck_v2ee_market_type  CHECK (market_type = 'perp'),
    CONSTRAINT ck_v2ee_direction
        CHECK (direction IN ('LONG','SHORT')),
    CONSTRAINT ck_v2ee_setup_family
        CHECK (setup_family IN ('TREND_PULLBACK','COMPRESSION_BREAKOUT','CONFIRMED_BREAKOUT')),
    CONSTRAINT ck_v2ee_structural_anchor_json
        CHECK (jsonb_typeof(structural_anchor) = 'object'),

    CONSTRAINT ck_v2ee_episode_state
        CHECK (episode_state IN
            ('EARLY_SIGNAL','CONFIRMED','WEAKENING','INVALIDATED','EXPIRED','COMPLETED')),

    CONSTRAINT ck_v2ee_feature_schema_version
        CHECK (feature_schema_version > 0),
    CONSTRAINT ck_v2ee_calculation_version
        CHECK (calculation_version ~ '^[0-9a-f]{16}$'),
    CONSTRAINT ck_v2ee_config_hash
        CHECK (config_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_v2ee_config_version   CHECK (length(btrim(config_version)) > 0),
    CONSTRAINT ck_v2ee_code_version     CHECK (length(btrim(code_version)) > 0),
    CONSTRAINT ck_v2ee_decision_code_version
        CHECK (length(btrim(decision_code_version)) > 0),

    CONSTRAINT ck_v2ee_decision_snapshot_json
        CHECK (jsonb_typeof(decision_snapshot) = 'object'),
    CONSTRAINT ck_v2ee_event_payload_json
        CHECK (jsonb_typeof(event_payload) = 'object')
);

CREATE UNIQUE INDEX ux_v2ee_episode_decision_boundary
    ON v2_episode_events (run_kind, run_id, episode_id, decision_boundary);
"""

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)   # legal 5m boundary
H64 = "a" * 64
H16 = "b" * 16


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
    return "v2ee_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_events_table(body):
    """Create a fresh, uniquely-named schema, connect `Database` to it,
    create ONE `v2_episode_events` table inside that schema, run
    `body(db, scoped_dsn)`, then unconditionally drop that exact schema --
    all inside the SAME event loop."""
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
            await conn.execute(_V2_EPISODE_EVENTS_DDL)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body):
    asyncio.run(_with_isolated_events_table(body))


# ---- deterministic event construction helpers -------------------------------
def _episode_id(**over) -> str:
    base = dict(
        model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
        calculation_version=H16, symbol="BTCUSDT", market_type="perp",
        direction=LONG, setup_family=TREND_PULLBACK,
        structural_anchor={"bucket_ts": T0.isoformat()}, t_create=T0,
    )
    base.update(over)
    return compute_episode_id(**base)


def make_event(*, episode_id=None, decision_boundary=None, run_kind=LIVE,
               run_id="v2-shadow-live", **over) -> V2EpisodeEvent:
    decision_boundary = decision_boundary if decision_boundary is not None else T0
    episode_id = episode_id if episode_id is not None else _episode_id()
    event_id = over.pop("event_id", None) or compute_event_id(
        episode_id=episode_id, decision_boundary=decision_boundary)
    base = dict(
        run_kind=run_kind, run_id=run_id, event_id=event_id, episode_id=episode_id,
        model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK,
        structural_anchor={"bucket_ts": T0.isoformat()},
        episode_state=EARLY_SIGNAL, decision_boundary=decision_boundary,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-deadbeef",
        decision_snapshot={"consensus_confidence": 87.5},
        event_payload={"entry_zone": {"low": 64500.0, "high": 65000.0}},
    )
    base.update(over)
    return V2EpisodeEvent(**base)


async def _row_count(db) -> int:
    async with db.pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM v2_episode_events")


async def _fetch_one(db, *, run_kind, run_id, event_id):
    async with db.pool.acquire() as conn:
        return await conn.fetchrow(
            "SELECT * FROM v2_episode_events WHERE run_kind=$1 AND run_id=$2 AND event_id=$3",
            run_kind, run_id, event_id)


# ============================================================================
# 1. deterministic event persists once
# ============================================================================
def test_deterministic_event_persists_once():
    async def body(db, _dsn):
        ev = make_event()
        result = await db.insert_v2_episode_events([ev])
        assert result == 1
        assert await _row_count(db) == 1
        row = await _fetch_one(db, run_kind=ev.run_kind, run_id=ev.run_id, event_id=ev.event_id)
        assert row is not None
        assert row["episode_id"] == ev.episode_id
        assert row["decision_code_version"] == "decision-deadbeef"

    _run(body)


# ============================================================================
# 2. exact retry = idempotent success
# ============================================================================
def test_exact_identical_retry_is_idempotent_success():
    async def body(db, _dsn):
        ev = make_event()
        first = await db.insert_v2_episode_events([ev])
        assert first == 1
        second = await db.insert_v2_episode_events([ev])
        assert second == 0   # no NEW row -- but no error either
        assert await _row_count(db) == 1

    _run(body)


# ============================================================================
# 3. commit-success / ack-loss simulation retry = success
# ============================================================================
def test_commit_succeeded_ack_lost_retry_is_idempotent():
    async def body(db, scoped_dsn):
        ev = make_event()
        result = await db.insert_v2_episode_events([ev])
        assert result == 1
        # Simulate "the caller lost the ack" -- a genuinely FRESH
        # Database/connection pool retries the IDENTICAL, deterministically-
        # derived request.
        retry_db = Database(scoped_dsn)
        await retry_db.connect()
        try:
            retried = await retry_db.insert_v2_episode_events([ev])
            assert retried == 0
        finally:
            await retry_db.close()
        assert await _row_count(db) == 1

    _run(body)


# ============================================================================
# 4. conflicting retry fails closed (no silent overwrite)
# ============================================================================
def test_conflicting_retry_raises_and_does_not_overwrite():
    async def body(db, _dsn):
        ev = make_event()
        await db.insert_v2_episode_events([ev])
        # Same deterministic identity (episode_id/event_id unchanged), but
        # a DIFFERENT non-identity field (episode_state) -- a genuine
        # conflicting-content retry (direction/setup_family/etc. DO
        # participate in episode_id, so varying THOSE would just produce
        # an independent identity, not a conflict; episode_state does not
        # participate at all, per §2.1a's frozen field list).
        conflicting = make_event(
            episode_id=ev.episode_id, event_id=ev.event_id,
            decision_boundary=ev.decision_boundary, episode_state=CONFIRMED)
        with pytest.raises(V2EventIdentityConflictError):
            await db.insert_v2_episode_events([conflicting])
        # Original row is untouched.
        row = await _fetch_one(db, run_kind=ev.run_kind, run_id=ev.run_id, event_id=ev.event_id)
        assert row["episode_state"] == EARLY_SIGNAL
        assert await _row_count(db) == 1

    _run(body)


# ============================================================================
# 5. concurrent identical writers = one logical row
# ============================================================================
def test_concurrent_identical_writers_produce_exactly_one_row():
    async def body(db, _dsn):
        ev = make_event()

        async def _attempt():
            return await db.insert_v2_episode_events([ev])

        results = await asyncio.gather(_attempt(), _attempt())
        assert sorted(results) == [0, 1]   # exactly one real insert, one no-op
        assert await _row_count(db) == 1

    _run(body)


# ============================================================================
# 6. concurrent conflicting writers = at most one commits, no corruption
# ============================================================================
def test_concurrent_conflicting_writers_at_most_one_commits():
    async def body(db, _dsn):
        ev_a = make_event(episode_state=EARLY_SIGNAL)
        ev_b = make_event(
            episode_id=ev_a.episode_id, event_id=ev_a.event_id, episode_state=CONFIRMED)

        async def _attempt(ev):
            try:
                return ("ok", await db.insert_v2_episode_events([ev]))
            except V2EventIdentityConflictError as exc:
                return ("conflict", exc)

        outcomes = await asyncio.gather(_attempt(ev_a), _attempt(ev_b))
        kinds = sorted(k for k, _ in outcomes)
        # Exactly one of the two either won outright (both raced before
        # either committed, so BOTH could legitimately see "ok" only if
        # they are semantically identical -- they are NOT here, so at most
        # one "ok" is possible) or the second observed a genuine conflict.
        ok_count = sum(1 for k, _ in outcomes if k == "ok")
        conflict_count = sum(1 for k, _ in outcomes if k == "conflict")
        assert ok_count == 1
        assert conflict_count == 1
        assert await _row_count(db) == 1
        # DB ends with exactly ONE internally-valid immutable truth -- either
        # ev_a's or ev_b's content, never a mix.
        row = await _fetch_one(db, run_kind=ev_a.run_kind, run_id=ev_a.run_id, event_id=ev_a.event_id)
        assert row["episode_state"] in (EARLY_SIGNAL, CONFIRMED)

    _run(body)


def _distinct_pair():
    """Two events, same (run_kind, run_id, decision_boundary) scope (a
    legal §13.4-step-8 batch), each with its own genuinely independent
    deterministic identity."""
    good_a = make_event(
        episode_id=compute_episode_id(
            model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
            calculation_version=H16, symbol="BTCUSDT", market_type="perp",
            direction=LONG, setup_family=TREND_PULLBACK,
            structural_anchor={"bucket_ts": T0.isoformat()}, t_create=T0))
    good_b = make_event(
        episode_id=compute_episode_id(
            model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
            calculation_version=H16, symbol="BTCUSDT", market_type="perp",
            direction=SHORT, setup_family=COMPRESSION_BREAKOUT,
            structural_anchor={"bucket_ts": T0.isoformat()}, t_create=T0),
        direction=SHORT, setup_family=COMPRESSION_BREAKOUT)
    return good_a, good_b


# ============================================================================
# 7. multi-event batch failure mid-transaction = zero partial batch
# ============================================================================
def test_batch_failure_mid_transaction_leaves_zero_partial_rows():
    # The most direct, honest real-Postgres proof available without
    # bypassing V2EpisodeEvent's own validation (which would no longer be
    # testing this writer's real code path): a batch whose SECOND row is a
    # genuine CONFLICTING identity against an ALREADY-PERSISTED row from a
    # PRIOR, separate call. If the transaction is genuinely atomic, this
    # must roll back the FIRST (otherwise entirely valid) row of THIS
    # batch too -- proving the atomic unit is "the whole batch", not
    # "each row independently".
    async def body(db, _dsn):
        good_a, good_b = _distinct_pair()
        pre_existing = make_event(
            episode_id=good_b.episode_id, event_id=good_b.event_id, episode_state=CONFIRMED)
        assert await db.insert_v2_episode_events([pre_existing]) == 1

        with pytest.raises(V2EventIdentityConflictError):
            await db.insert_v2_episode_events([good_a, good_b])

        # good_a (valid, would-be-first-inserted row of THIS batch) must
        # NOT be visible -- the whole batch rolled back, not just good_b.
        assert await _row_count(db) == 1   # only pre_existing survives
        row_a = await _fetch_one(
            db, run_kind=good_a.run_kind, run_id=good_a.run_id, event_id=good_a.event_id)
        assert row_a is None

    _run(body)


# ============================================================================
# 8. batch retry after rollback succeeds
# ============================================================================
def test_batch_retry_after_rollback_succeeds_once_conflict_resolved():
    async def body(db, _dsn):
        good_a, good_b = _distinct_pair()

        # First attempt: entirely fresh batch, both rows genuinely new ->
        # succeeds outright (nothing to roll back here; this establishes
        # the baseline "retry of a fully-successful batch is idempotent").
        first = await db.insert_v2_episode_events([good_a, good_b])
        assert first == 2
        assert await _row_count(db) == 2

        # Retry the IDENTICAL batch again -- idempotent no-op, not a
        # partial success/failure mix.
        second = await db.insert_v2_episode_events([good_a, good_b])
        assert second == 0
        assert await _row_count(db) == 2

    _run(body)


# ============================================================================
# 9. LIVE vs REPLAY rows coexist without collision
# ============================================================================
def test_live_and_replay_rows_coexist_without_collision():
    async def body(db, _dsn):
        eid = _episode_id()
        live = make_event(run_kind=LIVE, run_id="v2-shadow-live", episode_id=eid)
        replay = make_event(run_kind=REPLAY, run_id="replay-2026-08-20", episode_id=eid)
        # Identical semantic identity (same episode_id/event_id -- proven
        # deterministic and reproducible across "runs" by construction),
        # yet both physically coexist because run_kind/run_id namespace
        # the physical rows apart.
        assert live.event_id == replay.event_id
        assert live.episode_id == replay.episode_id
        assert await db.insert_v2_episode_events([live]) == 1
        assert await db.insert_v2_episode_events([replay]) == 1
        assert await _row_count(db) == 2

    _run(body)


# ============================================================================
# 10. REPLAY A vs REPLAY B coexist without collision
# ============================================================================
def test_two_replay_runs_coexist_without_collision():
    async def body(db, _dsn):
        eid = _episode_id()
        replay_a = make_event(run_kind=REPLAY, run_id="replay-A", episode_id=eid)
        replay_b = make_event(run_kind=REPLAY, run_id="replay-B", episode_id=eid)
        assert replay_a.event_id == replay_b.event_id
        assert await db.insert_v2_episode_events([replay_a]) == 1
        assert await db.insert_v2_episode_events([replay_b]) == 1
        assert await _row_count(db) == 2

    _run(body)


# ============================================================================
# 11. one semantic-version field difference produces independent identity
# ============================================================================
def test_rules_version_difference_produces_independent_identity_no_collision():
    async def body(db, _dsn):
        eid_v1 = _episode_id(rules_version="v2-rules-v0.1.0")
        eid_v2 = _episode_id(rules_version="v2-rules-v0.2.0")
        assert eid_v1 != eid_v2
        ev1 = make_event(episode_id=eid_v1, rules_version="v2-rules-v0.1.0")
        ev2 = make_event(episode_id=eid_v2, rules_version="v2-rules-v0.2.0")
        assert await db.insert_v2_episode_events([ev1]) == 1
        assert await db.insert_v2_episode_events([ev2]) == 1
        assert await _row_count(db) == 2


    _run(body)


def test_calculation_version_difference_produces_independent_identity():
    async def body(db, _dsn):
        eid_a = _episode_id(calculation_version="a" * 16)
        eid_b = _episode_id(calculation_version="c" * 16)
        assert eid_a != eid_b
        ev_a = make_event(episode_id=eid_a, calculation_version="a" * 16)
        ev_b = make_event(episode_id=eid_b, calculation_version="c" * 16)
        assert await db.insert_v2_episode_events([ev_a]) == 1
        assert await db.insert_v2_episode_events([ev_b]) == 1
        assert await _row_count(db) == 2

    _run(body)


def test_decision_code_version_difference_does_not_fork_identity_but_persists_by_value():
    # decision_code_version deliberately does NOT participate in episode_id/
    # event_id (§2.1a) -- two events differing ONLY in decision_code_version
    # collide on the deterministic identity (by design), so the second
    # attempt is a genuine conflicting-content retry, not an independent row.
    async def body(db, _dsn):
        ev1 = make_event(decision_code_version="decision-code-A")
        ev2 = make_event(decision_code_version="decision-code-B")
        assert ev1.episode_id == ev2.episode_id
        assert ev1.event_id == ev2.event_id
        assert await db.insert_v2_episode_events([ev1]) == 1
        with pytest.raises(V2EventIdentityConflictError):
            await db.insert_v2_episode_events([ev2])
        row = await _fetch_one(db, run_kind=ev1.run_kind, run_id=ev1.run_id, event_id=ev1.event_id)
        assert row["decision_code_version"] == "decision-code-A"

    _run(body)


# ============================================================================
# 12. direct DB duplicate logical episode/T invariant enforced
# ============================================================================
_RAW_INSERT_SQL = """
    INSERT INTO v2_episode_events (
        run_kind, run_id, event_id, episode_id,
        model_family, rules_version, symbol, market_type, direction,
        setup_family, structural_anchor, episode_state, decision_boundary,
        feature_schema_version, calculation_version, config_hash,
        config_version, code_version, decision_code_version,
        decision_snapshot, event_payload
    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13,$14,$15,$16,$17,$18,$19,
              $20::jsonb,$21::jsonb)
"""


async def _raw_insert_fields(db, **fields) -> None:
    """Bypasses `Database.insert_v2_episode_events()`/`serialize_batch()`
    AND `V2EpisodeEvent`'s own Python-level validation entirely -- a raw
    INSERT built directly from explicit field values, so a rejection here
    proves PostgreSQL's OWN constraints reject the row, not merely that
    `V2EpisodeEvent.__post_init__` refuses to construct it (which, for
    several of these fields, would make the row impossible to even
    attempt inserting via the normal `V2EpisodeEvent` path in the first
    place -- exactly the scenario this helper exists to bypass)."""
    from storage.stage2_serialization import dumps_canonical_jsonb
    base = dict(
        run_kind=LIVE, run_id="v2-shadow-live",
        event_id=compute_event_id(episode_id=_episode_id(), decision_boundary=T0),
        episode_id=_episode_id(),
        model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
        symbol="BTCUSDT", market_type="perp", direction=LONG,
        setup_family=TREND_PULLBACK,
        structural_anchor={"bucket_ts": T0.isoformat()},
        episode_state=EARLY_SIGNAL, decision_boundary=T0,
        feature_schema_version=1, calculation_version=H16, config_hash=H64,
        config_version="2.1.0", code_version="deadbeef",
        decision_code_version="decision-deadbeef",
        decision_snapshot={"consensus_confidence": 87.5},
        event_payload={"entry_zone": {"low": 64500.0, "high": 65000.0}},
    )
    base.update(fields)
    async with db.pool.acquire() as conn:
        await conn.execute(
            _RAW_INSERT_SQL,
            base["run_kind"], base["run_id"], base["event_id"], base["episode_id"],
            base["model_family"], base["rules_version"], base["symbol"], base["market_type"],
            base["direction"], base["setup_family"],
            dumps_canonical_jsonb(base["structural_anchor"]), base["episode_state"],
            base["decision_boundary"], base["feature_schema_version"],
            base["calculation_version"], base["config_hash"], base["config_version"],
            base["code_version"], base["decision_code_version"],
            dumps_canonical_jsonb(base["decision_snapshot"]),
            dumps_canonical_jsonb(base["event_payload"]))


async def _raw_insert(db, ev: V2EpisodeEvent) -> None:
    """Same raw-SQL bypass as `_raw_insert_fields()`, but sourced from an
    already-constructed, already-VALID `V2EpisodeEvent` -- used by tests
    that need a real, valid row inserted via a path independent of
    `Database.insert_v2_episode_events()` itself (e.g. to prove a DB-level
    constraint catches something the writer's OWN Python code never even
    attempts to construct in the first place, without that fact being
    confused with "the writer's Python validation already caught it")."""
    from storage.stage2_serialization import dumps_canonical_jsonb
    async with db.pool.acquire() as conn:
        await conn.execute(
            _RAW_INSERT_SQL,
            ev.run_kind, ev.run_id, ev.event_id, ev.episode_id,
            ev.model_family, ev.rules_version, ev.symbol, ev.market_type, ev.direction,
            ev.setup_family, dumps_canonical_jsonb(ev.structural_anchor), ev.episode_state,
            ev.decision_boundary, ev.feature_schema_version, ev.calculation_version,
            ev.config_hash, ev.config_version, ev.code_version, ev.decision_code_version,
            dumps_canonical_jsonb(ev.decision_snapshot), dumps_canonical_jsonb(ev.event_payload))


def test_direct_db_write_cannot_bypass_episode_decision_boundary_uniqueness():
    # A hand-crafted row that shares (run_kind, run_id, episode_id,
    # decision_boundary) with an existing row, but uses a DIFFERENT
    # event_id (simulating exactly the "current PK is weaker than the
    # frozen invariant" gap this PR closes) -- PostgreSQL's OWN
    # ux_v2ee_episode_decision_boundary UNIQUE index must reject it, never
    # only the Python layer.
    async def body(db, _dsn):
        eid = _episode_id()
        ev1 = make_event(episode_id=eid, decision_boundary=T0, event_id="a" * 64)
        await _raw_insert(db, ev1)
        ev2 = make_event(episode_id=eid, decision_boundary=T0, event_id="b" * 64)
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await _raw_insert(db, ev2)
        assert await _row_count(db) == 1

    _run(body)


def test_direct_db_write_rejects_non_hash_shaped_event_id():
    # V2EpisodeEvent.__post_init__ itself only requires event_id to be
    # nonblank (deliberately, per events.py's own "only validates and
    # freezes what it is given" design -- see episode_identity.py module
    # docstring/PR body for why the hash-SHAPE enforcement is a DB-layer
    # concern here, not a V2EpisodeEvent-construction-time one) -- so a
    # non-hash-shaped event_id must be rejected by PostgreSQL itself, via
    # a raw write that bypasses V2EpisodeEvent construction entirely.
    async def body(db, _dsn):
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _raw_insert_fields(db, event_id="not-a-real-hash")

    _run(body)


def test_direct_db_write_rejects_non_hash_shaped_episode_id():
    async def body(db, _dsn):
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _raw_insert_fields(db, episode_id="not-a-real-hash-" + "a" * 48)

    _run(body)


def test_direct_db_write_rejects_blank_decision_code_version():
    # V2EpisodeEvent itself already rejects a blank decision_code_version
    # at construction (nonblank, mirrored from the DB CHECK) -- this test
    # specifically bypasses that Python-level guard to prove the DB's OWN
    # ck_v2ee_decision_code_version CHECK is real, independent enforcement,
    # not merely a duplicate of a check nothing could ever get past anyway.
    async def body(db, _dsn):
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await _raw_insert_fields(db, decision_code_version="   ")

    _run(body)


def test_direct_db_write_accepts_two_different_episodes_same_decision_boundary():
    # §13.4 step 8: legitimate -- multiple DIFFERENT episode_ids at the
    # SAME (run_kind, run_id, decision_boundary) must NOT be blocked by
    # ux_v2ee_episode_decision_boundary (it is scoped to include
    # episode_id, not merely decision_boundary alone).
    async def body(db, _dsn):
        ev_a, ev_b = _distinct_pair()
        assert await db.insert_v2_episode_events([ev_a, ev_b]) == 2
        assert await _row_count(db) == 2

    _run(body)


# ============================================================================
# 13. restart / fresh Database instance exact retry remains idempotent
# ============================================================================
def test_restart_fresh_database_instance_exact_retry_remains_idempotent():
    async def body(db, scoped_dsn):
        ev = make_event()
        first = await db.insert_v2_episode_events([ev])
        assert first == 1

        # "Restart": a genuinely fresh Database instance/connection pool
        # against the SAME underlying schema, reconstructing the IDENTICAL
        # deterministic event from the same semantic inputs.
        restarted = Database(scoped_dsn)
        await restarted.connect()
        try:
            same_episode_id = _episode_id()
            same_event_id = compute_event_id(episode_id=same_episode_id, decision_boundary=T0)
            assert same_episode_id == ev.episode_id
            assert same_event_id == ev.event_id
            retried_ev = make_event(episode_id=same_episode_id)
            retried = await restarted.insert_v2_episode_events([retried_ev])
            assert retried == 0   # idempotent -- no duplicate row
            assert await _row_count(restarted) == 1
        finally:
            await restarted.close()

    _run(body)


def test_deterministic_ids_survive_a_no_op_reconnect_with_no_python_state():
    # Proves NO process-local registry/cache is the identity authority --
    # recomputing from scratch, in a brand-new interpreter-level import
    # scope simulated by simply calling the pure functions again with
    # nothing carried over, reproduces the identical ids used to persist.
    async def body(db, _dsn):
        ev = make_event()
        await db.insert_v2_episode_events([ev])
        recomputed_episode_id = compute_episode_id(
            model_family=MODEL_FAMILY, rules_version="v2-rules-v0.1.0",
            calculation_version=H16, symbol="BTCUSDT", market_type="perp",
            direction=LONG, setup_family=TREND_PULLBACK,
            structural_anchor={"bucket_ts": T0.isoformat()}, t_create=T0)
        recomputed_event_id = compute_event_id(
            episode_id=recomputed_episode_id, decision_boundary=T0)
        assert recomputed_episode_id == ev.episode_id
        assert recomputed_event_id == ev.event_id
        row = await _fetch_one(
            db, run_kind=ev.run_kind, run_id=ev.run_id, event_id=recomputed_event_id)
        assert row is not None

    _run(body)


# ============================================================================
# 14. DDL drift guard (CodeRabbit finding): the hand-copied
# _V2_EPISODE_EVENTS_DDL above (used because a vanilla postgres:16 test
# server cannot run the real init_stage2_schema(), which also touches
# unrelated TimescaleDB-only tables) must never silently diverge from
# storage/stage2_schema.sql's real production definition. Deliberately a
# NARROW, table-scoped parser reusing tests/storage/test_v2_episode_event_
# schema.py's own already-tested column/PK extraction helpers -- never a
# general SQL-schema-comparison framework.
# ============================================================================
def _hand_copied_table_body() -> str:
    m = re.search(r"CREATE TABLE v2_episode_events \((.*?)\n\);", _V2_EPISODE_EVENTS_DDL, re.S)
    assert m, "v2_episode_events not found in this file's own hand-copied DDL"
    return m.group(1)


def _named_check_constraints(body: str) -> "set[str]":
    """Every constraint in v2_episode_events takes the exact shape
    `CONSTRAINT <name> CHECK (...)` -- the only other constraint on this
    table is the PRIMARY KEY, compared separately via `_real_schema_pk()`.
    Scoped to this ONE table's own already-extracted body only -- not a
    general SQL parser."""
    return set(re.findall(r"CONSTRAINT\s+(\w+)\s+CHECK", body))


def _unique_index_columns(text: str, index_name: str) -> "tuple[str, ...]":
    m = re.search(
        r"CREATE UNIQUE INDEX(?: IF NOT EXISTS)? " + re.escape(index_name) + r"\s*\n"
        r"\s*ON v2_episode_events \(([^)]*)\)", text)
    assert m, f"{index_name} not found"
    return tuple(c.strip() for c in m.group(1).split(","))


def test_hand_copied_ddl_columns_match_production_schema_exactly_in_order():
    assert (_real_schema_columns(_hand_copied_table_body())
            == _real_schema_columns(_REAL_V2EE_BODY))


def test_hand_copied_ddl_primary_key_matches_production_schema():
    assert _real_schema_pk(_hand_copied_table_body()) == _real_schema_pk(_REAL_V2EE_BODY)


def test_hand_copied_ddl_named_check_constraints_match_production_schema():
    hand_copied = _named_check_constraints(_hand_copied_table_body())
    production = _named_check_constraints(_REAL_V2EE_BODY)
    assert hand_copied == production
    # Sanity: prove this drift guard is not vacuously trivial (e.g. both
    # sides accidentally empty from a regex typo).
    assert len(hand_copied) >= 20


def test_hand_copied_ddl_unique_index_matches_production_schema():
    assert (
        _unique_index_columns(_V2_EPISODE_EVENTS_DDL, "ux_v2ee_episode_decision_boundary")
        == _unique_index_columns(_REAL_V2EE_SECTION, "ux_v2ee_episode_decision_boundary"))
