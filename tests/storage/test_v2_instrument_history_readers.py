"""Real-PostgreSQL proof of V2-H2c: as-of/historical instrument metadata
(`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §12.5a's clean-room finding
that "instrument metadata has no as-of/historical model today").

Deliberately NOT a FakeConn/SQL-string-inspection test — the whole point of
this suite is real PostgreSQL interval resolution, the real transactional
close-then-open history append (`Database.upsert_exchange_instrument`), the
real `ux_eih_one_open_interval_per_identity` partial unique index, and real
transaction rollback behavior, none of which a mocked connection can
exercise. Mirrors `tests/storage/test_v2_version_switch_readers.py`'s
established pattern exactly: per-test uniquely-named schema (never the
connection's shared default), one `asyncio.run()` per test (asyncpg pools
are bound to the loop that created them), and a
`V2_INSTRUMENT_HISTORY_TEST_DSN` env var with the identical fail-vs-skip
contract (unset -> best-effort SKIP on connection failure; explicitly set,
as CI does -- a connection/setup failure is a genuine FAILURE, never a
silent skip).

The table DDL below is a hand-copied, column-for-column mirror of
`storage/stage2_schema.sql`'s real `exchange_instruments`/
`exchange_instrument_history` definitions -- deliberately NOT the real
`Database.init_stage2_schema()` (which would also attempt `CREATE EXTENSION
IF NOT EXISTS timescaledb` and several `create_hypertable()` calls for
unrelated Stage 2 tables neither this test nor a vanilla `postgres:16` CI
image can satisfy), matching exactly why `test_klines_no_downgrade.py` and
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
    observed_at           TIMESTAMPTZ NOT NULL,
    effective_from        TIMESTAMPTZ NOT NULL,
    effective_until       TIMESTAMPTZ,
    note                  TEXT,
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
        effective_until IS NULL OR effective_until > effective_from)
);
CREATE UNIQUE INDEX ux_eih_one_open_interval_per_identity
    ON exchange_instrument_history (exchange, symbol, market_type)
    WHERE effective_until IS NULL;
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


async def _with_isolated_instrument_tables(body):
    """Create a fresh, uniquely-named schema, connect `Database` to it,
    create BOTH `exchange_instruments` and `exchange_instrument_history`
    inside that schema (`upsert_exchange_instrument` touches both), run
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
            await conn.execute(_EXCHANGE_INSTRUMENTS_DDL)
            await conn.execute(_EXCHANGE_INSTRUMENT_HISTORY_DDL)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body):
    asyncio.run(_with_isolated_instrument_tables(body))


async def _accept(db, *, tick_size, fetched_at, contract_multiplier=None,
                   exchange_instrument_id=SYMBOL, quantity_unit="base",
                   price_precision=1, quantity_precision=3,
                   metadata_source="exchange_api", accept_mismatch=False) -> None:
    await db.upsert_exchange_instrument(
        exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
        exchange_instrument_id=exchange_instrument_id, quantity_unit=quantity_unit,
        contract_multiplier=contract_multiplier, tick_size=tick_size,
        price_precision=price_precision, quantity_precision=quantity_precision,
        metadata_source=metadata_source, fetched_at=fetched_at, is_stale=False,
        accept_mismatch=accept_mismatch)


async def _raw_insert(conn, **over) -> None:
    row = dict(
        exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
        exchange_instrument_id=SYMBOL, quantity_unit="base", contract_multiplier=None,
        tick_size=0.1, price_precision=1, quantity_precision=3,
        metadata_source="exchange_api", observed_at=T0, effective_from=T0,
        effective_until=None, note=None,
    )
    row.update(over)
    await conn.execute(
        """
        INSERT INTO exchange_instrument_history
            (exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
             contract_multiplier, tick_size, price_precision, quantity_precision,
             metadata_source, observed_at, effective_from, effective_until, note)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        """,
        row["exchange"], row["symbol"], row["market_type"], row["exchange_instrument_id"],
        row["quantity_unit"], row["contract_multiplier"], row["tick_size"],
        row["price_precision"], row["quantity_precision"], row["metadata_source"],
        row["observed_at"], row["effective_from"], row["effective_until"], row["note"])


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
                      accept_mismatch=True)

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
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True)

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
        from storage.v2_setup_readers import V2SetupReaderError
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
        from storage.v2_setup_readers import V2SetupReaderError
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
# a PRESENT-but-invalid one is corruption)
# ============================================================================
def test_okx_missing_contract_multiplier_is_legitimate_absence():
    async def body(db, _dsn):
        await _accept(
            db, tick_size=0.1, fetched_at=_t(0), contract_multiplier=None,
            quantity_unit="contracts", exchange_instrument_id="BTC-USDT-SWAP")
        result = await db.fetch_v2_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))
        assert result["contract_multiplier"] is None
        assert result["quantity_unit"] == "contracts"

    _run(body)


def test_okx_present_invalid_contract_multiplier_fails_closed():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _raw_insert(conn, contract_multiplier=float("nan"),
                               quantity_unit="contracts", effective_from=_t(0),
                               effective_until=None)
        from storage.v2_setup_readers import V2SetupReaderError
        with pytest.raises(V2SetupReaderError, match="contract_multiplier"):
            await db.fetch_v2_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE, as_of=_t(5))

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


# ============================================================================
# concurrency: two racing accepted upserts for the SAME identity serialize
# via the transaction-scoped advisory lock -- never two open intervals
# ============================================================================
def test_concurrent_accepted_upserts_serialize_never_two_open_intervals():
    async def body(db, _dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))

        async def _attempt(tick, fetched_at):
            await _accept(db, tick_size=tick, fetched_at=fetched_at, accept_mismatch=True)

        await asyncio.gather(_attempt(0.20, _t(12)), _attempt(0.30, _t(13)))

        async with db.pool.acquire() as conn:
            open_rows = await conn.fetch(
                "SELECT tick_size FROM exchange_instrument_history "
                "WHERE exchange=$1 AND symbol=$2 AND market_type=$3 "
                "AND effective_until IS NULL",
                EXCHANGE, SYMBOL, MARKET_TYPE)
        assert len(open_rows) == 1   # never two -- the partial unique index
                                     # plus the advisory lock make this so

    _run(body)


# ============================================================================
# restart gives the same as-of answer
# ============================================================================
def test_restart_gives_identical_as_of_answer():
    async def body(db, scoped_dsn):
        await _accept(db, tick_size=0.10, fetched_at=_t(0))
        await _accept(db, tick_size=0.50, fetched_at=_t(12), accept_mismatch=True)

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
