"""Real-PostgreSQL proof of V2-H2c: as-of/historical instrument metadata
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a's clean-room finding
that "instrument metadata has no as-of/historical model today"), amended
per tech-lead review 4990482334's four correctness findings:

  1. `observed_at` (provenance: when a value was fetched) is NEVER
     conflated with `effective_from` (the explicit V2 decision-time
     activation boundary) -- a deliberately-accepted mismatch must not be
     auto-backdated to its own observation time.
  2. The corrected temporal invariants are enforced in BOTH Python and
     PostgreSQL (nullable `observed_at`, `observed_at <= effective_from`).
  3. `Database.seed_current_instrument_history` gives an already-accepted
     pre-H2c `exchange_instruments` LKG row a safe, explicit, idempotent
     history bootstrap -- never extrapolating backward.
  4. The delayed-mismatch-acceptance replay vector is a first-class real
     regression here, proving the exact backdating bug this review found.

And per tech-lead review 4991738511's single remaining blocker: the FIRST
attempt at calculation_version fork enforcement (`accepted_code_version`,
a stored label recorded alongside the acceptance) proved only that two
LABELS differed, never that the live Stage-2 feature-assembly path was
mechanically prevented from consuming NEW critical metadata under an OLD
`calculation_version`. That column/parameter is REMOVED here (not kept
alongside the fix). The REAL, end-to-end mechanism this file now proves at
the storage layer: `Database.upsert_exchange_instrument`'s
`accept_mismatch=True` critical-diff path requires an explicit
`target_metadata_revision`, strictly greater than the ONE global
`stage2_instrument_metadata_state.required_revision` row's current value,
and atomically bumps it (under `SELECT ... FOR UPDATE`, serializing against
ANY other identity's concurrent critical acceptance too -- this row is
shared across every exchange/symbol, never per-identity, because
`calculation_version` is itself a shared Stage-2 computation namespace).
The full connection all the way to feature persistence (a resolved
Stage2Config's `instrument_metadata_revision` vs this same global row,
enforced in `analytics/feature_engine/input_adapter.py::
assemble_exchange_feature_request`) is proven separately in
`tests/analytics/test_stage2_metadata_revision_fork.py`, using the REAL
Stage2Config + assembly path + raw-bundle dataclass -- this file proves
the storage-layer half: the atomic revision bump/lock/rollback/restart
behavior against a REAL PostgreSQL instance.

Also covers finding 9 (the OKX vector actually uses `exchange="okx"`).

Deliberately NOT a FakeConn/SQL-string-inspection test — the whole point of
this suite is real PostgreSQL interval resolution, the real transactional
close-then-open history append (`Database.upsert_exchange_instrument`), the
real `ux_eih_one_open_interval_per_identity` partial unique index, the real
`stage2_instrument_metadata_state` singleton lock, and real transaction
rollback behavior, none of which a mocked connection can exercise. Mirrors
`tests/storage/test_v2_version_switch_readers.py`'s established pattern
exactly: per-test uniquely-named schema (never the connection's shared
default), one `asyncio.run()` per test (asyncpg pools are bound to the loop
that created them), and a `V2_INSTRUMENT_HISTORY_TEST_DSN` env var with the
identical fail-vs-skip contract (unset -> best-effort SKIP on connection
failure; explicitly set, as CI does -- a connection/setup failure is a
genuine FAILURE, never a silent skip).

The table DDL below is a hand-copied, column-for-column mirror of
`storage/stage2_schema.sql`'s real `exchange_instruments`/
`exchange_instrument_history`/`stage2_instrument_metadata_state`
definitions -- deliberately NOT the real `Database.init_stage2_schema()`
(which would also attempt `CREATE EXTENSION IF NOT EXISTS timescaledb` and
several `create_hypertable()` calls for unrelated Stage 2 tables neither
this test nor a vanilla `postgres:16` CI image can satisfy), matching
exactly why `test_klines_no_downgrade.py` and
`test_v2_version_switch_readers.py` do the same."""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from storage.db import Database
from storage.v2_setup_readers import V2SetupReaderError

_EXPLICIT_DSN = os.environ.get("V2_INSTRUMENT_HISTORY_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

_EXCHANGE_INSTRUMENTS_DDL = """
CREATE TABLE exchange_instruments (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    exchange_instrument_id TEXT NOT NULL,
    quantity_unit         TEXT,
    contract_multiplier   DOUBLE PRECISION,
    tick_size             DOUBLE PRECISION,
    price_precision       INTEGER,
    quantity_precision    INTEGER,
    metadata_source       TEXT NOT NULL,
    fetched_at            TIMESTAMPTZ,
    is_stale              BOOLEAN NOT NULL DEFAULT FALSE,
    note                  TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type),
    CONSTRAINT ck_ei_quantity_unit CHECK (
        quantity_unit IS NULL OR quantity_unit IN ('base','contracts')),
    CONSTRAINT ck_ei_metadata_source CHECK (
        metadata_source IN ('exchange_api','declared_fallback','manual'))
);
"""

# Column-for-column mirror of storage/stage2_schema.sql's real
# exchange_instrument_history definition -- see module docstring for why
# this is hand-copied rather than applied via init_stage2_schema().
_EXCHANGE_INSTRUMENT_HISTORY_DDL = """
CREATE TABLE exchange_instrument_history (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    exchange_instrument_id TEXT NOT NULL,
    quantity_unit         TEXT,
    contract_multiplier   DOUBLE PRECISION,
    tick_size             DOUBLE PRECISION,
    price_precision       INTEGER,
    quantity_precision    INTEGER,
    metadata_source       TEXT NOT NULL,
    observed_at           TIMESTAMPTZ,
    effective_from        TIMESTAMPTZ NOT NULL,
    effective_until       TIMESTAMPTZ,
    note                  TEXT,
    accepted_metadata_revision INTEGER,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type, effective_from),
    CONSTRAINT ck_eih_quantity_unit CHECK (
        quantity_unit IS NULL OR quantity_unit IN ('base','contracts')),
    CONSTRAINT ck_eih_metadata_source CHECK (
        metadata_source IN ('exchange_api','declared_fallback','manual')),
    CONSTRAINT ck_eih_tick_size_positive CHECK (tick_size IS NULL OR tick_size > 0),
    CONSTRAINT ck_eih_contract_multiplier_positive CHECK (
        contract_multiplier IS NULL OR contract_multiplier > 0),
    CONSTRAINT ck_eih_price_precision_nonneg CHECK (
        price_precision IS NULL OR price_precision >= 0),
    CONSTRAINT ck_eih_quantity_precision_nonneg CHECK (
        quantity_precision IS NULL OR quantity_precision >= 0),
    CONSTRAINT ck_eih_interval_well_formed CHECK (
        effective_until IS NULL OR effective_until > effective_from),
    CONSTRAINT ck_eih_observed_at_not_after_effective_from CHECK (
        observed_at IS NULL OR observed_at <= effective_from),
    CONSTRAINT ck_eih_accepted_metadata_revision_positive CHECK (
        accepted_metadata_revision IS NULL OR accepted_metadata_revision > 0)
);
CREATE UNIQUE INDEX ux_eih_one_open_interval_per_identity
    ON exchange_instrument_history (exchange, symbol, market_type)
    WHERE effective_until IS NULL;
"""

# (Tech-lead review 4991738511) Column-for-column mirror of
# storage/stage2_schema.sql's real stage2_instrument_metadata_state
# definition -- the ONE global row every feature computation (any
# exchange, any symbol) must agree with.
_STAGE2_INSTRUMENT_METADATA_STATE_DDL = """
CREATE TABLE stage2_instrument_metadata_state (
    singleton         BOOLEAN NOT NULL DEFAULT TRUE,
    required_revision INTEGER NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (singleton),
    CONSTRAINT ck_s2ims_singleton_true CHECK (singleton),
    CONSTRAINT ck_s2ims_revision_positive CHECK (required_revision > 0)
);
"""

UTC = timezone.utc
EXCHANGE = "binance"
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
T0 = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)


def _t(hours: int) -> datetime:
    return T0 + timedelta(hours=hours)


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
    return "v2ih_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_instrument_tables(body, *, bootstrap_revision=1):
    """Create a fresh, uniquely-named schema, connect `Database` to it,
    create `exchange_instruments`/`exchange_instrument_history`/
    `stage2_instrument_metadata_state` inside that schema
    (`upsert_exchange_instrument` touches all three), run `body(db,
    scoped_dsn)`, then unconditionally drop that exact schema -- all inside
    the SAME event loop.

    `bootstrap_revision`: if not None, `Database.
    bootstrap_instrument_metadata_revision` is called with this value
    BEFORE `body` runs, matching `config/stage2.yaml`'s own initial
    `defaults.instrument_metadata_revision: 1` default -- most tests don't
    care about this mechanism directly and just need the singleton row to
    already exist. Pass `bootstrap_revision=None` to leave the table
    freshly created but unseeded, for tests that exercise the bootstrap
    method's own raw SEEDED/ALREADY_INITIALIZED behavior."""
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
            await conn.execute(_EXCHANGE_INSTRUMENTS_DDL)
            await conn.execute(_EXCHANGE_INSTRUMENT_HISTORY_DDL)
            await conn.execute(_STAGE2_INSTRUMENT_METADATA_STATE_DDL)
        if bootstrap_revision is not None:
            result = await db.bootstrap_instrument_metadata_revision(
                initial_revision=bootstrap_revision)
            assert result == "SEEDED"
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body, **kw):
    asyncio.run(_with_isolated_instrument_tables(body, **kw))


async def _accept(db, *, tick_size, fetched_at, contract_multiplier=None,
                   exchange_instrument_id=SYMBOL, quantity_unit="base",
                   price_precision=1, quantity_precision=3,
                   metadata_source="exchange_api", accept_mismatch=False,
                   effective_from=None, target_metadata_revision=None) -> None:
    await db.upsert_exchange_instrument(
        exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
        exchange_instrument_id=exchange_instrument_id, quantity_unit=quantity_unit,
        contract_multiplier=contract_multiplier, tick_size=tick_size,
        price_precision=price_precision, quantity_precision=quantity_precision,
        metadata_source=metadata_source, fetched_at=fetched_at, is_stale=False,
        accept_mismatch=accept_mismatch, effective_from=effective_from,
        target_metadata_revision=target_metadata_revision)


async def _raw_insert(conn, **over) -> None:
    row = dict(
        exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
        exchange_instrument_id=SYMBOL, quantity_unit="base", contract_multiplier=None,
        tick_size=0.1, price_precision=1, quantity_precision=3,
        metadata_source="exchange_api", observed_at=T0, effective_from=T0,
        effective_until=None, note=None, accepted_metadata_revision=None,
    )
    row.update(over)
    await conn.execute(
        """
        INSERT INTO exchange_instrument_history
            (exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
             contract_multiplier, tick_size, price_precision, quantity_precision,
             metadata_source, observed_at, effective_from, effective_until, note,
             accepted_metadata_revision)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        """,
        row["exchange"], row["symbol"], row["market_type"], row["exchange_instrument_id"],
        row["quantity_unit"], row["contract_multiplier"], row["tick_size"],
        row["price_precision"], row["quantity_precision"], row["metadata_source"],
        row["observed_at"], row["effective_from"], row["effective_until"], row["note"],
        row["accepted_metadata_revision"])


# ============================================================================
# 1. version A inserted -> pre-change as-of resolves A
# ============================================================================
def test_single_version_as_of_inside_interval_resolves_it():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert result["tick_size"] == 0.10

    _run(body)


# ============================================================================
# 2. before-first-known-history returns no row (never current LKG fallback)
# ============================================================================
def test_as_of_before_first_known_history_returns_none():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(12))
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(0))
        assert result is None

    _run(body)


def test_never_evaluated_identity_returns_none():
    async def body(db, _dsn):
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(0))
        assert result is None

    _run(body)


# ============================================================================
# 3/4/5. two versions A/B: before transition -> A; exact boundary -> B
# (frozen [effective_from, effective_until) convention); after -> B
# ============================================================================
def test_version_a_then_b_boundary_semantics_frozen_half_open_interval():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))              # version A
        await _accept(db, tick_size=0.50, fetched_at=_t(12),             # version B
                      accept_mismatch=True, effective_from=_t(12),
                      target_metadata_revision=2)

        before = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(11))
        at_boundary = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(12))
        after = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(13))

        assert before["tick_size"] == 0.10     # replay before 12:00 -> A
        assert at_boundary["tick_size"] == 0.50   # AT the transition -> B (NEW applies)
        assert after["tick_size"] == 0.50      # replay after 12:00 -> B

    _run(body)


# ============================================================================
# 6. insert/change current LKG (and history) AFTER a replay dataset exists
#    -> old replay result unchanged (adding B later must not retroactively
#    change a pre-transition detector result)
# ============================================================================
def test_adding_later_version_does_not_retroactively_change_earlier_as_of_result():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        pre_change_result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(6))
        assert pre_change_result["tick_size"] == 0.10

        # Now accept a NEW version much later.
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(12), target_metadata_revision=2)

        # Re-querying the SAME historical as_of=_t(6) must resolve to the
        # exact same DECISION-RELEVANT values -- protection_buffer() would
        # compute an identical result either way. (The row's own
        # effective_until bookkeeping field legitimately changes from NULL
        # to _t(12) once version B closes it -- that is NOT a lookahead
        # regression, it is this table correctly recording that A's
        # interval is now known to have ended; what must never change is
        # the VALUE a historical decision at as_of=_t(6) actually reads.)
        post_change_result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(6))
        decision_fields = (
            "tick_size", "contract_multiplier", "quantity_unit",
            "exchange_instrument_id", "price_precision", "quantity_precision")
        for field in decision_fields:
            assert post_change_result[field] == pre_change_result[field], field
        assert post_change_result["tick_size"] == 0.10
        assert post_change_result["effective_until"] == _t(12)   # correctly closed now

    _run(body)


# ============================================================================
# 7. future-only metadata exists -> historical T does not see it
# ============================================================================
def test_future_only_metadata_not_visible_to_earlier_as_of():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.50, fetched_at=_t(100))   # far future only
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(0))
        assert result is None   # NOT the future row, NOT an error either

    _run(body)


# ============================================================================
# 8. ambiguous overlapping (closed) versions -> reader fails closed
# (the ux_eih_one_open_interval_per_identity index only prevents two OPEN
# rows -- two CLOSED, overlapping rows are still directly insertable, which
# is exactly the corruption case the reader itself must catch.)
# ============================================================================
def test_overlapping_closed_history_rows_fail_closed_on_read():
    async def body(db, scoped_dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, tick_size=0.10,
                               effective_from=_t(0), effective_until=_t(12))
            await _raw_insert(conn, tick_size=0.20,
                               effective_from=_t(6), effective_until=_t(18))
        with pytest.raises(V2SetupReaderError, match="overlapping|ambiguous"):
            await db.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(8))

    _run(body)


def test_one_open_interval_per_identity_index_rejects_two_open_rows():
    """The cheap partial-unique-index defense, proven for real: a SECOND
    row for the SAME identity with effective_until=NULL is rejected by
    PostgreSQL itself, never merely by application code."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, effective_from=_t(0), effective_until=None)
            with pytest.raises(asyncpg.exceptions.UniqueViolationError):
                await _raw_insert(conn, effective_from=_t(6), effective_until=None)

    _run(body)


# ============================================================================
# 9. wrong exchange/symbol/market_type -> no cross-identity fallback
# ============================================================================
def test_wrong_identity_never_falls_back():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        wrong_exchange = await db.fetch_v2_instrument(
            exchange="okx", symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        wrong_symbol = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol="ETHUSDT", market_type=MARKET_TYPE, as_of=_t(5))
        assert wrong_exchange is None
        assert wrong_symbol is None

    _run(body)


# ============================================================================
# 10/11. malformed tick_size (NaN/inf) -- PASSES the DB's own CHECK (Postgres
# float8 ordering treats NaN/Infinity as > 0) but the READER must still fail
# closed -- proving the Python-level check is the true authority, for real.
# ============================================================================
@pytest.mark.parametrize("bad_tick", [float("nan"), float("inf")])
def test_nan_and_infinite_tick_size_pass_db_check_but_reader_fails_closed(bad_tick):
    # NOTE: -inf is deliberately NOT included here -- Postgres's float8
    # ordering correctly treats -Infinity as less than 0, so `-inf` IS
    # caught by the schema's own `CHECK (tick_size > 0)` at INSERT time
    # (see test_zero_and_negative_tick_size_rejected_by_db_check_itself
    # below, which covers it alongside plain 0/negative). Only NaN and
    # +Infinity slip past that CHECK (Postgres treats both as "greater
    # than any value" for ordering purposes) and therefore need the
    # reader's own Python-level check to catch them.
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, tick_size=bad_tick, effective_from=_t(0),
                               effective_until=None)
        with pytest.raises(V2SetupReaderError, match="tick_size"):
            await db.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))

    _run(body)


def test_zero_and_negative_tick_size_rejected_by_db_check_itself():
    """Defense in depth: unlike NaN/Infinity, a plain 0/negative value IS
    caught by the schema's own `CHECK (tick_size > 0)` at INSERT time --
    never even reaches the reader."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, tick_size=0.0, effective_from=_t(0))
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, tick_size=-0.1, effective_from=_t(1))
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, tick_size=float("-inf"), effective_from=_t(2))

    _run(body)


# ============================================================================
# 12. OKX contracts metadata with missing/invalid multiplier -- preserves
# existing fail-closed semantics (contract_multiplier absence is legitimate;
# a PRESENT-but-invalid one is corruption). Tech-lead review 4990482334,
# finding 9: this vector must actually use exchange="okx", not the module's
# generic EXCHANGE="binance" constant.
# ============================================================================
def test_okx_missing_contract_multiplier_is_legitimate_absence():
    async def body(db, _dsn):
        await db.upsert_exchange_instrument(
            exchange="okx", symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_instrument_id="BTC-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=None, tick_size=0.1, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api", fetched_at=_t(0),
            is_stale=False)
        result = await db.fetch_v2_instrument(
            exchange="okx", symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert result["contract_multiplier"] is None
        assert result["quantity_unit"] == "contracts"
        # A missing ctVal must never be silently treated as base/1.0.
        assert result["exchange_instrument_id"] == "BTC-USDT-SWAP"

    _run(body)


def test_okx_present_invalid_contract_multiplier_fails_closed():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, exchange="okx", exchange_instrument_id="BTC-USDT-SWAP",
                               contract_multiplier=float("nan"),
                               quantity_unit="contracts", effective_from=_t(0),
                               effective_until=None)
        with pytest.raises(V2SetupReaderError, match="contract_multiplier"):
            await db.fetch_v2_instrument(
                exchange="okx", symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))

    _run(body)


# ============================================================================
# transaction failure cannot expose half-updated validity intervals
# ============================================================================
def test_transaction_failure_leaves_old_interval_untouched():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        before = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert before["tick_size"] == 0.10
        assert before["effective_until"] is None

        class _Boom(RuntimeError):
            pass

        with pytest.raises(_Boom):
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE exchange_instrument_history SET effective_until = $1 "
                        "WHERE exchange=$2 AND symbol=$3 AND market_type=$4 "
                        "AND effective_until IS NULL",
                        _t(12), EXCHANGE, SYMBOL, MARKET_TYPE)
                    raise _Boom("simulated failure after close, before the new INSERT commits")

        # Re-read: the interval must still be open with the ORIGINAL value --
        # the attempted close must be entirely invisible.
        reread = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(20))
        assert reread["tick_size"] == 0.10
        assert reread["effective_until"] is None

    _run(body)


def test_transaction_failure_leaves_required_revision_untouched():
    """The SAME atomicity guarantee, for the NEW global revision row: a
    failure after a critical acceptance's UPDATE but before commit must
    leave `stage2_instrument_metadata_state.required_revision` completely
    unaffected -- never a half-applied bump."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))

        class _Boom(RuntimeError):
            pass

        with pytest.raises(_Boom):
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE stage2_instrument_metadata_state SET required_revision = 99")
                    raise _Boom("simulated failure before commit")

        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert row["required_revision"] == 1   # untouched -- the bump never committed

    _run(body)


# ============================================================================
# concurrency: two racing IDENTICAL accepted upserts for the SAME identity
# serialize via the transaction-scoped advisory lock -- never two open
# intervals, and the second is a harmless no-op (deterministic regardless of
# which one wins the lock race -- avoids a flaky test that would depend on
# asyncio/Postgres scheduling order if the two attempts declared DIFFERENT
# new values with an explicit effective_from each).
# ============================================================================
def test_concurrent_identical_accepted_upserts_serialize_never_two_open_intervals():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))

        async def _attempt():
            await _accept(db, tick_size=0.20, fetched_at=_t(12), accept_mismatch=True,
                          effective_from=_t(12), target_metadata_revision=2)

        await asyncio.gather(_attempt(), _attempt())

        async with db.pool.acquire() as conn:
            open_rows = await conn.fetch(
                "SELECT tick_size FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                "AND effective_until IS NULL",
                EXCHANGE, SYMBOL, MARKET_TYPE)
            all_rows = await conn.fetch(
                "SELECT tick_size FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                EXCHANGE, SYMBOL, MARKET_TYPE)
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert len(open_rows) == 1   # never two -- the partial unique index
                                     # plus the advisory lock make this so
        assert open_rows[0]["tick_size"] == 0.20
        # Exactly 2 rows total (original A closed + one B) -- the second,
        # identical concurrent acceptance attempt was a true no-op, not a
        # duplicate interval.
        assert len(all_rows) == 2
        # The global revision was bumped exactly once too -- not twice, and
        # the second (no-op) attempt's own target_metadata_revision=2 must
        # not have been rejected as "not strictly greater" against itself
        # (it is IDENTICAL to the first attempt's already-committed value,
        # so the second attempt's critical_diff is empty by the time it
        # runs -- a true no-op, never reaching the revision-bump gate).
        assert revision_row["required_revision"] == 2

    _run(body)


# ============================================================================
# Tech-lead review 4991738511: the GLOBAL revision row is shared across
# DIFFERENT identities, never a per-identity counter -- a critical
# acceptance on ANY venue/symbol must fork the SAME namespace for all.
# ============================================================================
def test_global_required_revision_is_shared_across_different_identities():
    async def body(db, _dsn):
        # Identity 1: binance/BTCUSDT (the module's default EXCHANGE/SYMBOL).
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        await _accept(db, tick_size=0.20, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(12), target_metadata_revision=2)

        # Identity 2: an ENTIRELY DIFFERENT exchange/symbol -- its own
        # first-ever value (no critical_diff possible; existing is None).
        await db.upsert_exchange_instrument(
            exchange="okx", symbol="ETHUSDT", market_type=MARKET_TYPE,
            exchange_instrument_id="ETH-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=1.0, tick_size=0.05, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api", fetched_at=_t(1),
            is_stale=False)
        # Its own SECOND, deliberately-accepted critical change must respect
        # the SAME global counter identity 1 already advanced to 2 -- reusing
        # revision 2 (as if it were its own private counter starting at 1)
        # must be rejected exactly like identity 1's own reuse would be.
        with pytest.raises(ValueError, match="not strictly greater"):
            await db.upsert_exchange_instrument(
                exchange="okx", symbol="ETHUSDT", market_type=MARKET_TYPE,
                exchange_instrument_id="ETH-USDT-SWAP", quantity_unit="contracts",
                contract_multiplier=1.0, tick_size=0.09, price_precision=1,
                quantity_precision=3, metadata_source="exchange_api", fetched_at=_t(2),
                is_stale=False, accept_mismatch=True, effective_from=_t(2),
                target_metadata_revision=2)   # reuses identity 1's own revision

        # A genuinely higher revision (3) succeeds, and the SAME global row
        # both identities observe now reads 3 -- proving one shared namespace.
        await db.upsert_exchange_instrument(
            exchange="okx", symbol="ETHUSDT", market_type=MARKET_TYPE,
            exchange_instrument_id="ETH-USDT-SWAP", quantity_unit="contracts",
            contract_multiplier=1.0, tick_size=0.09, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api", fetched_at=_t(2),
            is_stale=False, accept_mismatch=True, effective_from=_t(2),
            target_metadata_revision=3)

        async with db.pool.acquire() as conn:
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert revision_row["required_revision"] == 3

    _run(body)


# ============================================================================
# restart gives the same as-of answer
# ============================================================================
def test_restart_gives_identical_as_of_answer():
    async def body(db, scoped_dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(12), target_metadata_revision=2)

        restarted = Database(scoped_dsn)
        await restarted.connect()
        try:
            r1 = await restarted.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(6))
            r2 = await restarted.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(20))
            assert r1["tick_size"] == 0.10
            assert r2["tick_size"] == 0.50
        finally:
            await restarted.close()

    _run(body)


# ============================================================================
# current LKG (exchange_instruments) is never read by the as-of path
# ============================================================================
def test_current_lkg_row_never_leaks_into_as_of_read():
    """A stale/never-updated LKG row must never satisfy a historical read
    -- only exchange_instrument_history does. Simulates a corrupted
    deployment where exchange_instruments has a row but
    exchange_instrument_history legitimately does not (e.g. seeded by an
    older, pre-H2c code path that never wrote history)."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO exchange_instruments
                    (exchange, symbol, market_type, exchange_instrument_id,
                     quantity_unit, contract_multiplier, tick_size,
                     price_precision, quantity_precision, metadata_source,
                     fetched_at, is_stale, note)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                """,
                EXCHANGE, SYMBOL, MARKET_TYPE, SYMBOL, "base", None, 0.99,
                1, 3, "exchange_api", _t(0), False, None)
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert result is None   # NOT 0.99 -- the LKG row must never leak in

    _run(body)


# ============================================================================
# Tech-lead review 4990482334, finding 1 (BLOCKER): observed_at is NOT
# effective_from -- a deliberately-accepted mismatch must not be
# auto-backdated to its own (possibly much earlier) fetch timestamp.
# ============================================================================
def test_accepting_a_value_change_without_explicit_effective_from_raises():
    """The exact backdating bug this review found: accepting a genuine
    value change (an interval is already open) with NO explicit
    effective_from must raise, not silently default to fetched_at."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        with pytest.raises(ValueError, match="effective_from"):
            await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                          target_metadata_revision=2)   # effective_from NOT supplied

        # The refused call must not have mutated anything.
        current = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(20))
        assert current["tick_size"] == 0.10

    _run(body)


def test_first_ever_value_safely_defaults_effective_from_to_fetched_at():
    """No OLD value's already-made LIVE decisions exist to protect
    against for a stream's first-ever accepted value -- effective_from
    may safely default to fetched_at here (the ONLY case where that
    default is safe)."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(5))   # no effective_from given
        exactly_at = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        before = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(4))
        assert exactly_at["tick_size"] == 0.10
        assert before is None

    _run(body)


def test_observed_at_after_effective_from_raises():
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="observed"):
            await _accept(db, tick_size=0.10, fetched_at=_t(5), effective_from=_t(0))

    _run(body)


def test_manual_metadata_with_no_fetched_at_but_explicit_effective_from_is_legal():
    """observed_at (fetched_at) MAY be NULL for a manual/declared value --
    but effective_from is still required and honored exactly."""
    async def body(db, _dsn):
        await db.upsert_exchange_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_instrument_id=SYMBOL, quantity_unit="base",
            contract_multiplier=None, tick_size=0.1, price_precision=None,
            quantity_precision=None, metadata_source="manual", fetched_at=None,
            is_stale=False, effective_from=_t(5))
        after = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        before = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(4))
        assert after["tick_size"] == 0.1
        assert after["observed_at"] is None
        assert before is None

    _run(body)


# ============================================================================
# Tech-lead review 4990482334, finding 1 (BLOCKER, continued): raw-INSERT
# real-Postgres regressions for invalid temporal shapes -- proving the DB's
# own CHECK constraint independently catches what the Python guard also
# catches, never relying on the Python layer alone.
# ============================================================================
def test_raw_insert_observed_at_after_effective_from_rejected_by_db_check():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await _raw_insert(conn, observed_at=_t(5), effective_from=_t(0))

    _run(body)


def test_raw_insert_non_strictly_increasing_effective_from_against_open_interval_raises():
    """The Python-level guard (not a DB CHECK -- ordering across ROWS isn't
    expressible as a single-row CHECK) still fails closed for real against
    PostgreSQL when a caller tries to reorder history."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(12))
        with pytest.raises(ValueError, match="strictly after"):
            await _accept(db, tick_size=0.50, fetched_at=_t(6), accept_mismatch=True,
                          effective_from=_t(6), target_metadata_revision=2)   # EARLIER, not later

    _run(body)


# ============================================================================
# Tech-lead review 4990482334, finding 4 (BLOCKER): delayed mismatch
# acceptance replay vector -- the exact scenario the review froze.
#
#   OLD: effective before 12:00, tick_size = 0.10
#   NEW: observed_at = 12:00, tick_size = 0.50, NOT yet accepted
#   acceptance/effective boundary: 13:00
#
#   as_of 12:30 -> OLD 0.10
#   as_of 12:59 -> OLD 0.10
#   as_of 13:00 -> NEW 0.50
#   as_of 13:05 -> NEW 0.50
#
# Also proves merely OBSERVING the mismatch (the refused, not-yet-accepted
# call) mutates NEITHER the exchange_instruments LKG NOR the historical
# decision-effective intervals.
# ============================================================================
def test_delayed_mismatch_acceptance_replay_vector():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))   # OLD, effective before 12:00

        # 12:00 -- the exchange fetch OBSERVES a NEW tick_size, but it is
        # NOT deliberately accepted yet (no accept_mismatch=True).
        with pytest.raises(ValueError, match="mismatch"):
            await _accept(db, tick_size=0.50, fetched_at=_t(12))

        # Merely observing the mismatch must mutate NOTHING.
        async with db.pool.acquire() as conn:
            lkg = await conn.fetchrow(
                "SELECT tick_size FROM exchange_instruments "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                EXCHANGE, SYMBOL, MARKET_TYPE)
            open_interval = await conn.fetchrow(
                "SELECT tick_size, effective_until FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                "AND effective_until IS NULL",
                EXCHANGE, SYMBOL, MARKET_TYPE)
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert lkg["tick_size"] == 0.10          # LKG untouched
        assert open_interval["tick_size"] == 0.10   # history untouched
        assert open_interval["effective_until"] is None
        assert revision_row["required_revision"] == 1   # global revision untouched too

        # LIVE decisions from 12:00 through 12:55 still correctly see OLD.
        live_1230 = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(12) + timedelta(minutes=30))
        assert live_1230["tick_size"] == 0.10

        # 13:00 -- an operator DELIBERATELY accepts NEW, declaring 13:00 as
        # the real V2 decision-time activation boundary (NOT 12:00).
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(13), target_metadata_revision=2)

        as_of_1230 = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            as_of=_t(12) + timedelta(minutes=30))
        as_of_1259 = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            as_of=_t(12) + timedelta(minutes=59))
        as_of_1300 = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(13))
        as_of_1305 = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            as_of=_t(13) + timedelta(minutes=5))

        assert as_of_1230["tick_size"] == 0.10   # still OLD -- the actual LIVE decision
        assert as_of_1259["tick_size"] == 0.10   # still OLD
        assert as_of_1300["tick_size"] == 0.50   # NEW takes effect exactly at acceptance
        assert as_of_1305["tick_size"] == 0.50   # still NEW

    _run(body)


# ============================================================================
# Tech-lead review 4990482334, finding 3 (BLOCKER): explicit, conservative,
# idempotent bootstrap of an already-accepted pre-H2c LKG row that has no
# history yet -- Database.seed_current_instrument_history.
# ============================================================================
def test_seed_current_instrument_history_full_vector():
    async def body(db, scoped_dsn):
        # 1. pre-H2c LKG exists, history empty.
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO exchange_instruments
                    (exchange, symbol, market_type, exchange_instrument_id,
                     quantity_unit, contract_multiplier, tick_size,
                     price_precision, quantity_precision, metadata_source,
                     fetched_at, is_stale, note)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                """,
                EXCHANGE, SYMBOL, MARKET_TYPE, SYMBOL, "base", None, 0.25,
                1, 3, "exchange_api", _t(0), False, None)

        # 2. as-of read initially returns None (no history at all).
        pre_seed = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(50))
        assert pre_seed is None

        # 3. explicit seed at T_seed.
        t_seed = _t(20)
        result = await db.seed_current_instrument_history(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, effective_from=t_seed)
        assert result == "SEEDED"

        # 4. T < T_seed still returns None -- never extrapolated backward.
        before_seed = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(19))
        assert before_seed is None

        # 5. T == T_seed resolves the accepted current row.
        at_seed = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=t_seed)
        assert at_seed["tick_size"] == 0.25

        # 6. T > T_seed resolves it.
        after_seed = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(50))
        assert after_seed["tick_size"] == 0.25

        # The LKG row itself must be preserved exactly, untouched.
        async with db.pool.acquire() as conn:
            lkg = await conn.fetchrow(
                "SELECT tick_size, fetched_at FROM exchange_instruments "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert lkg["tick_size"] == 0.25
        assert lkg["fetched_at"] == _t(0)

        # 7. repeated seed is idempotent -- never overwrites/duplicates.
        result2 = await db.seed_current_instrument_history(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            effective_from=_t(999))   # even with a DIFFERENT effective_from
        assert result2 == "ALREADY_HAS_HISTORY"
        still_before = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(19))
        assert still_before is None   # unchanged -- the re-seed attempt was a no-op

        # 8. restart preserves the same result.
        restarted = Database(scoped_dsn)
        await restarted.connect()
        try:
            restarted_result = await restarted.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(50))
            assert restarted_result["tick_size"] == 0.25
        finally:
            await restarted.close()

    _run(body)


def test_seed_current_instrument_history_no_lkg_is_noop():
    async def body(db, _dsn):
        result = await db.seed_current_instrument_history(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, effective_from=_t(0))
        assert result == "NO_LKG"
        still_none = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(0))
        assert still_none is None

    _run(body)


def test_seed_current_instrument_history_never_overwrites_real_history():
    """If real (non-seeded) history already exists, seeding must be a
    pure no-op -- never colliding with or masking real history."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.77, fetched_at=_t(0))
        result = await db.seed_current_instrument_history(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, effective_from=_t(999))
        assert result == "ALREADY_HAS_HISTORY"
        unaffected = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert unaffected["tick_size"] == 0.77

    _run(body)


def test_seed_current_instrument_history_stamps_current_global_revision():
    """(Finding 10, applied to bootstrapping too) The seeded row's own
    `accepted_metadata_revision` records whatever the global revision
    already IS at seed time -- never NULL, never invented."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO exchange_instruments
                    (exchange, symbol, market_type, exchange_instrument_id,
                     quantity_unit, contract_multiplier, tick_size,
                     price_precision, quantity_precision, metadata_source,
                     fetched_at, is_stale, note)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
                """,
                EXCHANGE, SYMBOL, MARKET_TYPE, SYMBOL, "base", None, 0.25,
                1, 3, "exchange_api", _t(0), False, None)
            # Bump the global revision to 2 BEFORE seeding, to prove the
            # seed stamps the CURRENT value, not a hardcoded 1.
            await conn.execute(
                "UPDATE stage2_instrument_metadata_state SET required_revision = 2")
        await db.seed_current_instrument_history(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, effective_from=_t(20))
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT accepted_metadata_revision FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert row["accepted_metadata_revision"] == 2

    _run(body)


# ============================================================================
# Tech-lead review 4991738511, finding 11: explicit, conservative, idempotent
# bootstrap of the GLOBAL stage2_instrument_metadata_state singleton itself.
# ============================================================================
def test_bootstrap_instrument_metadata_revision_seeds_once_idempotent():
    async def body(db, _dsn):
        result1 = await db.bootstrap_instrument_metadata_revision(initial_revision=1)
        assert result1 == "SEEDED"
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert row["required_revision"] == 1

        # A second bootstrap call, even with a DIFFERENT initial_revision,
        # must NEVER overwrite an already-live required revision.
        result2 = await db.bootstrap_instrument_metadata_revision(initial_revision=5)
        assert result2 == "ALREADY_INITIALIZED"
        async with db.pool.acquire() as conn:
            row_after = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert row_after["required_revision"] == 1   # unchanged

    _run(body, bootstrap_revision=None)   # start unseeded -- this IS the test


def test_upsert_before_bootstrap_fails_closed():
    """ANY history-touching upsert (even a first-ever, non-critical value)
    attempted before the global singleton has ever been bootstrapped must
    fail closed -- every history row's `accepted_metadata_revision`
    provenance stamp depends on that row existing, so there is no safe
    partial mode where only critical acceptances need it."""
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="not bootstrapped"):
            await _accept(db, tick_size=0.10, fetched_at=_t(0))
        # Nothing was committed by the refused attempt.
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert result is None

    _run(body, bootstrap_revision=None)


# ============================================================================
# Tech-lead review 4991738511, finding 9 (blocker): the storage-layer half
# of calculation_version fork enforcement -- REMOVED accepted_code_version,
# REPLACED by an explicit target_metadata_revision that must be strictly
# greater than the current GLOBAL stage2_instrument_metadata_state row, and
# is bumped ATOMICALLY with the LKG/history writes. The full connection to
# the live Stage-2 feature-assembly path (the part that actually makes this
# a REAL fork, not just a storage-layer label) is proven separately in
# tests/analytics/test_stage2_metadata_revision_fork.py.
# ============================================================================
def test_critical_mismatch_acceptance_without_target_revision_fails_closed():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        with pytest.raises(ValueError, match="target_metadata_revision"):
            await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                          effective_from=_t(12))   # no target_metadata_revision
        unaffected = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(20))
        assert unaffected["tick_size"] == 0.10
        async with db.pool.acquire() as conn:
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert revision_row["required_revision"] == 1   # untouched

    _run(body)


def test_critical_mismatch_acceptance_same_or_lower_revision_fails_closed():
    """The core executable proof: accepted critical metadata cannot be
    consumed under the OLD calculation_version -- a critical acceptance
    MUST supply a target_metadata_revision strictly greater than the
    GLOBAL row's current value, or it is refused outright."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(12), target_metadata_revision=2)

        # Reusing 2 (the SAME value the first acceptance just set) is refused.
        with pytest.raises(ValueError, match="not strictly greater"):
            await _accept(db, tick_size=0.90, fetched_at=_t(24), accept_mismatch=True,
                          effective_from=_t(24), target_metadata_revision=2)
        # A LOWER value is refused too.
        with pytest.raises(ValueError, match="not strictly greater"):
            await _accept(db, tick_size=0.90, fetched_at=_t(24), accept_mismatch=True,
                          effective_from=_t(24), target_metadata_revision=1)

        # Neither refused acceptance mutated anything further.
        unaffected = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(30))
        assert unaffected["tick_size"] == 0.50

        # A genuinely HIGHER revision succeeds.
        await _accept(db, tick_size=0.90, fetched_at=_t(24), accept_mismatch=True,
                      effective_from=_t(24), target_metadata_revision=3)
        now_current = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(30))
        assert now_current["tick_size"] == 0.90

        # The GLOBAL row itself now reads 3 -- the real, atomically-bumped
        # fork identity, not merely a per-row label.
        async with db.pool.acquire() as conn:
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
        assert revision_row["required_revision"] == 3

        # The recorded history proves each accepted critical fork by value.
        async with db.pool.acquire() as conn:
            forks = await conn.fetch(
                "SELECT tick_size, accepted_metadata_revision FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                "ORDER BY effective_from ASC",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert [(r["tick_size"], r["accepted_metadata_revision"]) for r in forks] == [
            (0.10, 1), (0.50, 2), (0.90, 3)]

    _run(body)


def test_first_ever_history_row_inherits_current_global_revision_not_null():
    """A first-ever accepted value (no prior LKG/history at all) is not a
    "critical mismatch acceptance" -- but its history row's
    accepted_metadata_revision is still stamped with the CURRENT global
    revision (1, from bootstrap), never NULL/None (finding 10: never
    silently reset provenance just because this particular row wasn't
    itself a critical acceptance)."""
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT accepted_metadata_revision FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert row["accepted_metadata_revision"] == 1

    _run(body)


# ============================================================================
# Tech-lead review 4991738511, finding 10: a NON-critical value change
# (price_precision-only) must NEVER require or bump the global revision --
# it simply inherits whatever the CURRENT global revision already is.
# ============================================================================
def test_noncritical_field_only_change_does_not_bump_required_revision():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        # Critical change -> bumps the global revision to 2.
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True,
                      effective_from=_t(12), target_metadata_revision=2)

        # Now a NON-critical-only change: same tick_size/quantity_unit/
        # contract_multiplier/exchange_instrument_id, only price_precision
        # differs. No accept_mismatch, no target_metadata_revision needed
        # at all -- critical_diff is empty, so the mismatch-refusal gate
        # doesn't even apply. effective_from is still required (a genuine
        # value change against an already-open interval), just not a
        # revision bump.
        await _accept(db, tick_size=0.50, fetched_at=_t(24), price_precision=9,
                      effective_from=_t(24))

        async with db.pool.acquire() as conn:
            revision_row = await conn.fetchrow(
                "SELECT required_revision FROM stage2_instrument_metadata_state")
            rows = await conn.fetch(
                "SELECT tick_size, price_precision, accepted_metadata_revision "
                "FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                "ORDER BY effective_from ASC",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert revision_row["required_revision"] == 2   # unchanged by the non-critical write
        # Three intervals now: original (rev 1), critical accept (rev 2),
        # non-critical precision-only change -- which INHERITS rev 2, never
        # resets to NULL/1.
        assert [(r["tick_size"], r["price_precision"], r["accepted_metadata_revision"])
                for r in rows] == [(0.10, 1, 1), (0.50, 1, 2), (0.50, 9, 2)]

    _run(body)
