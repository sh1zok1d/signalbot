"""Real-PostgreSQL proof of V2-H3's schema-hardening UPGRADE path
(`Database._harden_v2_episode_events_id_constraints()`, invoked from the
canonical `Database.init_stage2_schema()`), closing tech-lead review
Blocker 2: an ALREADY-EXISTING (pre-H3) `v2_episode_events` table must
converge onto the EXACT SAME `ck_v2ee_event_id_hash_format`/
`ck_v2ee_episode_id_hash_format` invariant a fresh database's `CREATE
TABLE` already bakes in inline.

Deliberately NOT a FakeConn/SQL-string-inspection test — the whole point
is real PostgreSQL `pg_constraint` introspection, real `ALTER TABLE ADD
CONSTRAINT` validation-against-existing-rows semantics, and real
transaction rollback on a legacy-data violation, none of which a mocked
connection can exercise. Mirrors `tests/storage/test_v2_episode_event_
transactions.py`'s established pattern exactly (per-test isolated schema,
one `asyncio.run()` per test, `V2_EPISODE_EVENT_TEST_DSN` env var with the
identical fail-vs-skip contract).

Two hand-copied DDL variants, both deliberately NOT the real
`storage/stage2_schema.sql` (which a vanilla `postgres:16` test server
cannot fully apply for unrelated TimescaleDB reasons -- see
`test_v2_episode_event_transactions.py`'s own module docstring):

  - `_PRE_H3_DDL`: the table exactly as it existed on `main` before ANY
    V2-H3 change -- no `decision_code_version` column, no hash-format
    CHECKs, no `ux_v2ee_episode_decision_boundary` index. Used to prove
    the full, realistic upgrade sequence (A-G below) end to end, starting
    from a table that has genuinely never seen any V2-H3 schema change.
  - `_FULLY_UPGRADED_EXCEPT_HASH_FORMAT_DDL`: every OTHER V2-H3 schema
    change already applied (so a legacy row can legitimately satisfy
    `decision_code_version NOT NULL` and every other already-existing
    constraint) EXCEPT the two hash-format CHECKs -- used to prove the
    fail-closed legacy-malformed-row vector (H) in isolation from the
    unrelated `decision_code_version` prerequisite, which a table that
    has NEVER been upgraded at all cannot satisfy for a pre-existing row
    without either a DEFAULT (never fabricated here) or an empty table.
"""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from storage.db import Database

_EXPLICIT_DSN = os.environ.get("V2_EPISODE_EVENT_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

UTC = timezone.utc
T0 = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
H64 = "a" * 64
H16 = "b" * 16

# Exact pre-V2-H3 (main) v2_episode_events definition -- no
# decision_code_version, no hash-format CHECKs, no unique index.
_PRE_H3_DDL = """
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

    decision_snapshot      JSONB NOT NULL,
    event_payload          JSONB NOT NULL,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (run_kind, run_id, event_id),

    CONSTRAINT ck_v2ee_run_kind
        CHECK (run_kind IN ('LIVE','REPLAY')),
    CONSTRAINT ck_v2ee_run_id       CHECK (length(btrim(run_id)) > 0),
    CONSTRAINT ck_v2ee_event_id     CHECK (length(btrim(event_id)) > 0),
    CONSTRAINT ck_v2ee_episode_id   CHECK (length(btrim(episode_id)) > 0),

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

    CONSTRAINT ck_v2ee_decision_snapshot_json
        CHECK (jsonb_typeof(decision_snapshot) = 'object'),
    CONSTRAINT ck_v2ee_event_payload_json
        CHECK (jsonb_typeof(event_payload) = 'object')
);
"""

# Every OTHER V2-H3 schema change already applied (decision_code_version,
# the unique index) -- ONLY the two hash-format CHECKs are deliberately
# absent. Isolates the fail-closed legacy-row vector from the unrelated
# decision_code_version NOT NULL prerequisite.
_FULLY_UPGRADED_EXCEPT_HASH_FORMAT_DDL = """
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
    -- deliberately NO ck_v2ee_event_id_hash_format / ck_v2ee_episode_id_hash_format --
    -- this is the EXACT "everything upgraded except this one hardening step" state.

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

_HASH_FORMAT_CONSTRAINT_NAMES = (
    "ck_v2ee_event_id_hash_format", "ck_v2ee_episode_id_hash_format")


async def _connect_admin() -> asyncpg.Connection:
    try:
        return await asyncpg.connect(BASE_DSN, timeout=3)
    except Exception as exc:  # noqa: BLE001
        if _EXPLICIT_DSN:
            raise
        pytest.skip(f"no reachable PostgreSQL test server at {BASE_DSN!r}: {exc}")
        raise AssertionError("unreachable")  # pragma: no cover


def _unique_schema_name() -> str:
    return "v2ee_upgrade_test_" + uuid.uuid4().hex[:16]


def _scoped_dsn(base_dsn: str, schema: str) -> str:
    parts = urllib.parse.urlsplit(base_dsn)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
    query.append(("options", f"-csearch_path={schema}"))
    new_query = urllib.parse.urlencode(query)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))


async def _with_isolated_schema(ddl: str, body):
    """Create a fresh, uniquely-named schema, connect `Database` to it,
    apply `ddl` (the STARTING state -- either genuinely pre-H3 or
    fully-upgraded-except-hash-format), run `body(db, scoped_dsn)`, then
    unconditionally drop the schema."""
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
            await conn.execute(ddl)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run_pre_h3(body):
    asyncio.run(_with_isolated_schema(_PRE_H3_DDL, body))


def _run_fully_upgraded_except_hash_format(body):
    asyncio.run(_with_isolated_schema(_FULLY_UPGRADED_EXCEPT_HASH_FORMAT_DDL, body))


async def _hash_format_constraint_names(conn) -> set:
    rows = await conn.fetch(
        "SELECT conname FROM pg_constraint "
        "WHERE conrelid = 'v2_episode_events'::regclass AND conname = ANY($1)",
        list(_HASH_FORMAT_CONSTRAINT_NAMES),
    )
    return {r["conname"] for r in rows}


_INSERT_SQL = """
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


async def _raw_insert(conn, *, event_id: str, episode_id: str, run_id: str = "legacy-run") -> None:
    """Direct SQL insert bypassing V2EpisodeEvent/Database entirely --
    proves the DB's own state, never the Python layer's."""
    await conn.execute(
        _INSERT_SQL,
        "LIVE", run_id, event_id, episode_id,
        "v2", "v2-rules-v0.1.0", "BTCUSDT", "perp", "LONG",
        "TREND_PULLBACK", "{}", "EARLY_SIGNAL", T0,
        1, H16, H64, "1.0", "legacy-code", "legacy-decision-code",
        "{}", "{}")


# ============================================================================
# A-C: fresh vs. pre-H3-upgraded schema converge on the SAME invariant
# ============================================================================
def test_pre_h3_table_starts_without_hash_format_constraints():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
        assert names == set()

    _run_pre_h3(body)


def test_canonical_init_stage2_schema_adds_both_constraints_to_pre_h3_table():
    async def body(db, _dsn):
        # B: run the SAME canonical schema/bootstrap path normal
        # runtime/deployment uses -- never a lower-level private method
        # called directly.
        await db.init_stage2_schema()
        # C: prove physically through pg_constraint that BOTH now exist.
        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
        assert names == set(_HASH_FORMAT_CONSTRAINT_NAMES)

    _run_pre_h3(body)


def test_fresh_and_upgraded_expose_the_same_invariant_shape():
    # "fresh == upgraded": both must show EXACTLY the same two constraint
    # names, with the SAME CHECK expression, after their respective
    # canonical init path runs.
    async def body(db, _dsn):
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT conname, pg_get_constraintdef(oid) AS def FROM pg_constraint "
                "WHERE conrelid = 'v2_episode_events'::regclass AND conname = ANY($1) "
                "ORDER BY conname",
                list(_HASH_FORMAT_CONSTRAINT_NAMES),
            )
        defs = {r["conname"]: r["def"] for r in rows}
        assert set(defs) == set(_HASH_FORMAT_CONSTRAINT_NAMES)
        assert "event_id" in defs["ck_v2ee_event_id_hash_format"]
        assert "~" in defs["ck_v2ee_event_id_hash_format"]
        assert "[0-9a-f]{64}" in defs["ck_v2ee_event_id_hash_format"]
        assert "episode_id" in defs["ck_v2ee_episode_id_hash_format"]
        assert "[0-9a-f]{64}" in defs["ck_v2ee_episode_id_hash_format"]

    _run_pre_h3(body)


# ============================================================================
# D-F: direct SQL insert against the UPGRADED (formerly pre-H3) table
# ============================================================================
def test_upgraded_table_rejects_malformed_event_id_via_direct_sql():
    async def body(db, _dsn):
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, event_id="not-a-hash", episode_id=H64)

    _run_pre_h3(body)


def test_upgraded_table_rejects_malformed_episode_id_via_direct_sql():
    async def body(db, _dsn):
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, event_id=H64, episode_id="not-a-hash")

    _run_pre_h3(body)


def test_upgraded_table_accepts_valid_hex64_event():
    async def body(db, _dsn):
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, event_id=H64, episode_id="c" * 64)
            count = await conn.fetchval("SELECT count(*) FROM v2_episode_events")
        assert count == 1

    _run_pre_h3(body)


# ============================================================================
# G: idempotent re-initialization
# ============================================================================
def test_reinitializing_stage2_schema_is_idempotent_exactly_one_copy_each():
    async def body(db, _dsn):
        await db.init_stage2_schema()
        await db.init_stage2_schema()
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT conname, count(*) AS n FROM pg_constraint "
                "WHERE conrelid = 'v2_episode_events'::regclass AND conname = ANY($1) "
                "GROUP BY conname",
                list(_HASH_FORMAT_CONSTRAINT_NAMES),
            )
        counts = {r["conname"]: r["n"] for r in rows}
        assert counts == {name: 1 for name in _HASH_FORMAT_CONSTRAINT_NAMES}

    _run_pre_h3(body)


def test_reinitializing_after_upgrade_still_succeeds_with_valid_data_present():
    async def body(db, _dsn):
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, event_id=H64, episode_id="c" * 64)
        # A valid, hex64-conforming row already present must never block a
        # later, idempotent re-init.
        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
            count = await conn.fetchval("SELECT count(*) FROM v2_episode_events")
        assert names == set(_HASH_FORMAT_CONSTRAINT_NAMES)
        assert count == 1

    _run_pre_h3(body)


# ============================================================================
# H: legacy malformed row -> fail closed, atomically, no rewrite, no fake ID
# ============================================================================
def test_legacy_malformed_event_id_row_makes_upgrade_fail_closed():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, event_id="legacy-opaque-event-id", episode_id=H64)

        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.init_stage2_schema()

        # Neither constraint was left behind (atomic transaction rolled
        # both checks back together), and the legacy row is untouched --
        # never rewritten, never given a fabricated hex64 ID.
        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
            row = await conn.fetchrow(
                "SELECT event_id, episode_id FROM v2_episode_events WHERE run_id = 'legacy-run'")
        assert names == set()
        assert row["event_id"] == "legacy-opaque-event-id"
        assert row["episode_id"] == H64

    _run_fully_upgraded_except_hash_format(body)


def test_legacy_malformed_episode_id_row_makes_upgrade_fail_closed_atomically():
    # The MORE REVEALING atomicity vector: event_id is ALREADY valid (its
    # own constraint would succeed in isolation), episode_id is malformed
    # (the SECOND constraint attempted, per Database._V2EE_ID_HASH_FORMAT_
    # CONSTRAINTS' fixed order) -- proves the FIRST constraint is not left
    # behind as an orphaned, half-converged state when the SECOND fails.
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, event_id=H64, episode_id="legacy-opaque-episode-id")

        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.init_stage2_schema()

        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
            row = await conn.fetchrow(
                "SELECT event_id, episode_id FROM v2_episode_events WHERE run_id = 'legacy-run'")
        # Neither constraint -- NOT even ck_v2ee_event_id_hash_format,
        # which would have succeeded on its own -- is present.
        assert names == set()
        assert row["event_id"] == H64
        assert row["episode_id"] == "legacy-opaque-episode-id"

    _run_fully_upgraded_except_hash_format(body)


def test_legacy_malformed_row_upgrade_retry_succeeds_once_data_is_fixed():
    # Proves the fail-closed state is recoverable: once the offending
    # legacy row is corrected (by an operator, out of this method's
    # scope -- this method itself never rewrites it), a retried init
    # succeeds and converges normally.
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, event_id="legacy-opaque-event-id", episode_id=H64)

        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.init_stage2_schema()

        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE v2_episode_events SET event_id = $1 WHERE run_id = 'legacy-run'",
                "d" * 64)

        await db.init_stage2_schema()
        async with db.pool.acquire() as conn:
            names = await _hash_format_constraint_names(conn)
        assert names == set(_HASH_FORMAT_CONSTRAINT_NAMES)

    _run_fully_upgraded_except_hash_format(body)


def test_harden_method_never_uses_not_valid_or_update_or_delete():
    # A structural guard against silently weakening the fail-closed
    # posture in the future -- NOT VALID would defer validation instead
    # of failing closed immediately; UPDATE/DELETE would imply rewriting
    # existing rows, which this method must never do.
    import inspect
    src = inspect.getsource(Database._harden_v2_episode_events_id_constraints)
    assert "NOT VALID" not in src.upper()
    assert " UPDATE " not in f" {src.upper()} "
    assert "DELETE" not in src.upper()
