"""Real-PostgreSQL proofs for the V2-H2e correction-publication coherence
barrier (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.4):
`storage/stage2_publication_state.py`, `Database.publish_stage2_correction`,
`Database.open_v2_coherent_read_session`, and the DIRTY-marking wired into
`insert_klines`/`insert_open_interest`/`insert_funding`.

Mirrors the established real-Postgres pattern (per-test uniquely-named
schema, one `asyncio.run()` per test, `V2_INSTRUMENT_HISTORY_TEST_DSN`
fail-vs-skip contract, hand-copied DDL) from
`tests/storage/test_v2_instrument_history_readers.py` /
`tests/storage/test_stage2_raw_bundle_snapshot.py`; DDL for
`exchange_instruments`/`exchange_instrument_history`/
`stage2_instrument_metadata_state` and for `klines_1m`/`open_interest`/
`funding_rate` is reused directly from those two modules (never a third
independently-drifting copy). Stage 2 OUTPUT table DDL
(`exchange_feature_vectors`/`consensus_feature_vectors`/
`percentile_snapshots`/`data_health_snapshots`) is hand-copied here,
verbatim from `storage/stage2_schema.sql` minus the `create_hypertable()`
calls (same reason every other real-Postgres test file avoids
`init_stage2_schema()`: no TimescaleDB dependency needed for these tests).
Output-row dataclass factories (`make_efv`/`make_consensus`/
`make_percentile`/`make_health`) are reused from
`tests/storage/test_stage2_writers.py` -- one copy of "what a minimally
valid row looks like" across the suite.

Sections:
  1. `stage2_publication_state` basics (bootstrap/read/mark_dirty/mark_clean).
  2. Raw-writer DIRTY wiring (`insert_klines`/`insert_open_interest`/
     `insert_funding`) -- a correction marks DIRTY; a first-ever insert does
     not.
  3. `publish_stage2_correction` -- success, truthful-absence validation,
     and the atomic all-or-nothing rollback proof.
  4. `open_v2_coherent_read_session` -- fail-closed on DIRTY/unbootstrapped,
     structural Protocol satisfaction, and the SIX mandatory real-Postgres
     concurrency vectors.
"""
from __future__ import annotations

import asyncio
import os
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest

from analytics.forecasting_v2.ports import V2AlignedInputReader, V2SetupHistoryReader
from storage.db import Database
from storage.stage2_publication_state import V2PublicationDirtyError
from tests.storage.test_stage2_writers import B as _WRITERS_B
from tests.storage.test_stage2_writers import make_consensus, make_efv, make_health, make_percentile
from tests.storage.test_v2_instrument_history_readers import (
    _EXCHANGE_INSTRUMENT_HISTORY_DDL, _EXCHANGE_INSTRUMENTS_DDL,
    _STAGE2_INSTRUMENT_METADATA_STATE_DDL,
)

UTC = timezone.utc
EXCHANGE = "binance"
SYMBOL = "BTCUSDT"
MARKET_TYPE = "perp"
CALC_VERSION = "b" * 16
T0 = datetime(2026, 8, 15, 0, 0, tzinfo=UTC)


def _t(minutes: int) -> datetime:
    return T0 + timedelta(minutes=minutes)


_EXPLICIT_DSN = os.environ.get("V2_INSTRUMENT_HISTORY_TEST_DSN")
BASE_DSN = _EXPLICIT_DSN or "postgresql://postgres:postgres@127.0.0.1:5432/signalbot_test"

# ---- hand-copied Stage-1 raw DDL (plain, no hypertable) --------------------
_KLINES_1M_DDL = """
CREATE TABLE klines_1m (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    open DOUBLE PRECISION NOT NULL, high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL, close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    taker_buy_volume DOUBLE PRECISION, taker_sell_volume DOUBLE PRECISION,
    trades_count INTEGER, source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

_OPEN_INTEREST_DDL = """
CREATE TABLE open_interest (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    oi_raw DOUBLE PRECISION, oi_unit TEXT, contract_value DOUBLE PRECISION,
    oi_base_asset TEXT, oi_notional_usd DOUBLE PRECISION,
    oi_contracts DOUBLE PRECISION, oi_notional DOUBLE PRECISION,
    source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

_FUNDING_RATE_DDL = """
CREATE TABLE funding_rate (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL,
    funding_rate DOUBLE PRECISION NOT NULL, next_funding_time TIMESTAMPTZ,
    source TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);
"""

# ---- hand-copied Stage-2 OUTPUT DDL (verbatim from storage/stage2_schema.sql,
# minus create_hypertable()) -------------------------------------------------
_EXCHANGE_FEATURE_VECTORS_DDL = """
CREATE TABLE exchange_feature_vectors (
    exchange TEXT NOT NULL, symbol TEXT NOT NULL, market_type TEXT NOT NULL DEFAULT 'perp',
    timeframe TEXT NOT NULL, bucket_ts TIMESTAMPTZ NOT NULL,
    feature_schema_version INTEGER NOT NULL, calculation_version TEXT NOT NULL,
    price_move_pct DOUBLE PRECISION, range_width_pct DOUBLE PRECISION, close_price DOUBLE PRECISION,
    volume_raw DOUBLE PRECISION, volume_raw_unit TEXT, volume_notional_usd DOUBLE PRECISION,
    taker_buy_notional_usd DOUBLE PRECISION, taker_sell_notional_usd DOUBLE PRECISION,
    taker_delta_notional_usd DOUBLE PRECISION, cvd_delta_notional_usd DOUBLE PRECISION,
    oi_change_pct DOUBLE PRECISION, oi_unit TEXT, funding_rate DOUBLE PRECISION,
    long_liquidation_notional DOUBLE PRECISION, short_liquidation_notional DOUBLE PRECISION,
    liquidation_event_count INTEGER, liquidation_feed_quality TEXT, is_snapshot_feed BOOLEAN,
    bars_expected INTEGER, bars_present INTEGER,
    has_gap BOOLEAN NOT NULL DEFAULT FALSE, is_usable BOOLEAN NOT NULL DEFAULT TRUE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash TEXT NOT NULL, config_version TEXT NOT NULL, code_version TEXT NOT NULL,
    PRIMARY KEY (exchange, symbol, market_type, timeframe, bucket_ts, calculation_version)
);
"""

_CONSENSUS_FEATURE_VECTORS_DDL = """
CREATE TABLE consensus_feature_vectors (
    symbol TEXT NOT NULL, market_type TEXT NOT NULL DEFAULT 'perp', timeframe TEXT NOT NULL,
    bucket_ts TIMESTAMPTZ NOT NULL, feature_schema_version INTEGER NOT NULL,
    calculation_version TEXT NOT NULL,
    coverage_by_metric JSONB NOT NULL, provenance_by_metric JSONB NOT NULL,
    data_confidence_by_metric JSONB NOT NULL,
    exchanges_expected_max INTEGER NOT NULL, min_coverage_ratio DOUBLE PRECISION,
    data_confidence_overall DOUBLE PRECISION,
    price_direction_agreement DOUBLE PRECISION, flow_direction_agreement DOUBLE PRECISION,
    oi_direction_agreement DOUBLE PRECISION,
    price_move_pct_median DOUBLE PRECISION, range_width_pct_median DOUBLE PRECISION,
    oi_change_pct_median DOUBLE PRECISION,
    funding_rate_median DOUBLE PRECISION, funding_rate_mad DOUBLE PRECISION,
    volume_notional_usd_sum DOUBLE PRECISION, taker_buy_notional_usd_sum DOUBLE PRECISION,
    taker_sell_notional_usd_sum DOUBLE PRECISION, taker_delta_notional_usd_sum DOUBLE PRECISION,
    cvd_delta_notional_usd_sum DOUBLE PRECISION,
    observed_long_liquidation_notional_sum DOUBLE PRECISION,
    observed_short_liquidation_notional_sum DOUBLE PRECISION,
    observed_liquidation_event_count_sum INTEGER,
    liquidation_feed_quality_by_exchange JSONB,
    price_move_pct_mad DOUBLE PRECISION, oi_change_pct_mad DOUBLE PRECISION,
    outlier_exchanges JSONB,
    consensus_confidence DOUBLE PRECISION, is_partial_consensus BOOLEAN NOT NULL DEFAULT FALSE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash TEXT NOT NULL, config_version TEXT NOT NULL, code_version TEXT NOT NULL,
    PRIMARY KEY (symbol, market_type, timeframe, bucket_ts, calculation_version)
);
"""

_PERCENTILE_SNAPSHOTS_DDL = """
CREATE TABLE percentile_snapshots (
    scope TEXT NOT NULL, exchange TEXT NOT NULL DEFAULT '', symbol TEXT NOT NULL,
    market_type TEXT NOT NULL DEFAULT 'perp', metric TEXT NOT NULL, timeframe TEXT NOT NULL,
    percentile_window TEXT NOT NULL, bucket_ts TIMESTAMPTZ NOT NULL,
    value DOUBLE PRECISION, percentile_rank DOUBLE PRECISION, sample_size INTEGER NOT NULL,
    sample_window_start TIMESTAMPTZ, sample_window_end TIMESTAMPTZ,
    confidence_tier TEXT NOT NULL, computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash TEXT NOT NULL, config_version TEXT NOT NULL, code_version TEXT NOT NULL,
    feature_schema_version INTEGER NOT NULL, calculation_version TEXT NOT NULL,
    PRIMARY KEY (scope, exchange, symbol, market_type, metric, timeframe, percentile_window,
                 bucket_ts, calculation_version),
    CONSTRAINT ck_ps_scope CHECK (scope IN ('exchange','consensus')),
    CONSTRAINT ck_ps_scope_exchange CHECK (
        (scope = 'consensus' AND exchange = '') OR (scope = 'exchange' AND exchange <> '')),
    CONSTRAINT ck_ps_no_lookahead CHECK (sample_window_end IS NULL OR sample_window_end < bucket_ts)
);
"""

_DATA_HEALTH_SNAPSHOTS_DDL = """
CREATE TABLE data_health_snapshots (
    symbol TEXT NOT NULL, exchange TEXT NOT NULL, market_type TEXT NOT NULL DEFAULT 'perp',
    metric TEXT NOT NULL, snapshot_ts TIMESTAMPTZ NOT NULL, last_event_at TIMESTAMPTZ,
    expected_interval_s INTEGER, lateness_ms BIGINT, gap_count INTEGER NOT NULL DEFAULT 0,
    largest_gap_s INTEGER, backfill_status TEXT,
    coverage_window_start TIMESTAMPTZ, coverage_window_end TIMESTAMPTZ,
    is_stale BOOLEAN NOT NULL DEFAULT FALSE, is_usable BOOLEAN NOT NULL DEFAULT TRUE,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash TEXT NOT NULL, config_version TEXT NOT NULL, code_version TEXT NOT NULL,
    feature_schema_version INTEGER NOT NULL, calculation_version TEXT NOT NULL,
    PRIMARY KEY (symbol, exchange, market_type, metric, snapshot_ts, calculation_version)
);
"""

_STAGE2_PUBLICATION_STATE_DDL = """
CREATE TABLE stage2_publication_state (
    symbol TEXT NOT NULL, market_type TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'CLEAN',
    publication_generation BIGINT NOT NULL DEFAULT 0,
    dirty_reason TEXT, dirty_since TIMESTAMPTZ, clean_since TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, market_type),
    CONSTRAINT ck_sps_status CHECK (status IN ('CLEAN', 'DIRTY')),
    CONSTRAINT ck_sps_generation_nonneg CHECK (publication_generation >= 0)
);
"""

_ALL_DDL = (
    _KLINES_1M_DDL, _OPEN_INTEREST_DDL, _FUNDING_RATE_DDL,
    _EXCHANGE_INSTRUMENTS_DDL, _EXCHANGE_INSTRUMENT_HISTORY_DDL,
    _STAGE2_INSTRUMENT_METADATA_STATE_DDL, _STAGE2_PUBLICATION_STATE_DDL,
    _EXCHANGE_FEATURE_VECTORS_DDL, _CONSENSUS_FEATURE_VECTORS_DDL,
    _PERCENTILE_SNAPSHOTS_DDL, _DATA_HEALTH_SNAPSHOTS_DDL,
)


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
    return "v2cp_test_" + uuid.uuid4().hex[:16]


async def _with_isolated_schema(body):
    """Fresh, uniquely-named schema with every table this module's tests
    touch; seeds ONE instrument (bootstrap revision 1, tick=0.10) +
    bootstraps `stage2_publication_state` CLEAN for (SYMBOL, MARKET_TYPE);
    runs `body(db, scoped_dsn)`; unconditionally drops the schema after."""
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
            for ddl in _ALL_DDL:
                await conn.execute(ddl)
        await db.bootstrap_instrument_metadata_revision(initial_revision=1)
        await db.upsert_exchange_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_instrument_id=SYMBOL, quantity_unit="base",
            contract_multiplier=None, tick_size=0.10, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api",
            fetched_at=_t(0), is_stale=False)
        await db.bootstrap_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body):
    asyncio.run(_with_isolated_schema(body))


async def _seed_kline(db, *, ts, close=100.0, source="live"):
    await db.insert_klines(
        [(EXCHANGE, SYMBOL, ts, close, close, close, close, 1.0, None, None, None)],
        source=source)


# ============================================================================
# 1. stage2_publication_state basics
# ============================================================================
def test_bootstrap_is_idempotent_and_starts_clean_generation_zero():
    async def body(db, _dsn):
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"
        assert state.publication_generation == 0
        # a second bootstrap call must NOT reset anything
        result = await db.bootstrap_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert result == "ALREADY_INITIALIZED"

    _run(body)


def test_unbootstrapped_scope_reads_as_none():
    async def body(db, _dsn):
        state = await db.fetch_stage2_publication_state(symbol="ETHUSDT", market_type=MARKET_TYPE)
        assert state is None

    _run(body)


def test_mark_dirty_then_mark_clean_bumps_generation():
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_clean, mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(
                conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="TEST")
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "DIRTY"
        assert state.dirty_reason == "TEST"
        assert state.dirty_since is not None

        async with db.pool.acquire() as conn:
            new_gen = await mark_publication_clean(conn, symbol=SYMBOL, market_type=MARKET_TYPE)
        assert new_gen == 1
        state2 = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state2.status == "CLEAN"
        assert state2.publication_generation == 1
        assert state2.dirty_reason is None

    _run(body)


def test_marking_dirty_twice_preserves_earliest_dirty_since():
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="FIRST")
        first = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)

        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="SECOND")
        second = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)

        assert second.dirty_since == first.dirty_since   # earliest preserved
        assert second.dirty_reason == "SECOND"           # latest trigger recorded

    _run(body)


# ============================================================================
# 2. Raw-writer DIRTY wiring
# ============================================================================
def test_first_ever_kline_insert_does_not_mark_dirty():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1))
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"

    _run(body)


def test_kline_correction_marks_dirty_same_commit():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"

        # A correction: same (exchange, symbol, ts), different close.
        await _seed_kline(db, ts=_t(1), close=101.0, source="backfill")
        state2 = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state2.status == "DIRTY"
        assert state2.dirty_reason == "RAW_KLINE_CORRECTION"

    _run(body)


def test_open_interest_correction_marks_dirty():
    async def body(db, _dsn):
        row = (EXCHANGE, SYMBOL, _t(1), 1000.0, "base", None, None, None)
        await db.insert_open_interest([row], source="live")
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"

        corrected = (EXCHANGE, SYMBOL, _t(1), 1200.0, "base", None, None, None)
        await db.insert_open_interest([corrected], source="live")
        state2 = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state2.status == "DIRTY"
        assert state2.dirty_reason == "RAW_OPEN_INTEREST_CORRECTION"

    _run(body)


def test_funding_correction_marks_dirty():
    async def body(db, _dsn):
        row = (EXCHANGE, SYMBOL, _t(1), 0.0001, None)
        await db.insert_funding([row], source="live")
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"

        corrected = (EXCHANGE, SYMBOL, _t(1), 0.0002, None)
        await db.insert_funding([corrected], source="live")
        state2 = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state2.status == "DIRTY"
        assert state2.dirty_reason == "RAW_FUNDING_CORRECTION"

    _run(body)


def test_correction_for_unmapped_instrument_does_not_raise_or_mark_dirty():
    async def body(db, _dsn):
        # "ETHUSDT" has no exchange_instruments row in this schema.
        row = (EXCHANGE, "ETHUSDT", _t(1), 100.0, 100.0, 100.0, 100.0, 1.0, None, None, None)
        await db.insert_klines([row], source="backfill")
        corrected = (EXCHANGE, "ETHUSDT", _t(1), 101.0, 101.0, 101.0, 101.0, 1.0, None, None, None)
        await db.insert_klines([corrected], source="backfill")   # must not raise
        state = await db.fetch_stage2_publication_state(symbol="ETHUSDT", market_type=MARKET_TYPE)
        assert state is None   # never bootstrapped, never fabricated

    _run(body)


# ============================================================================
# 3. publish_stage2_correction
# ============================================================================
def test_publish_stage2_correction_success_writes_all_and_flips_clean():
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        result = await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )
        assert result.exchange_feature_vectors_written == 1
        assert result.consensus_feature_vectors_written == 1
        assert result.percentile_snapshots_written == 1
        assert result.data_health_snapshots_written == 1
        assert result.publication_generation == 1

        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"
        assert state.publication_generation == 1

        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 1

    _run(body)


def test_publish_stage2_correction_requires_absent_reason_for_empty_percentiles():
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="percentile_snapshots"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=(),
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        # nothing was written -- the raise happens before any connection is acquired
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 0
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"   # unchanged -- was already CLEAN from bootstrap

    _run(body)


def test_publish_stage2_correction_accepts_explicit_absent_reason():
    async def body(db, _dsn):
        result = await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=(),
            percentile_snapshots_absent_reason="no percentile orchestrator implemented (D-008)",
            data_health_snapshots=(),
            data_health_snapshots_absent_reason="no health recompute for this correction",
        )
        assert result.percentile_snapshots_written == 0
        assert result.percentile_snapshots_absent_reason == "no percentile orchestrator implemented (D-008)"
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "CLEAN"
        assert state.publication_generation == 1

    _run(body)


def test_publish_stage2_correction_rolls_back_atomically_on_mid_batch_failure():
    """A percentile row violating `ck_ps_no_lookahead` fails the THIRD
    family write -- the whole transaction (including the exchange/consensus
    families already written earlier in the SAME transaction, and the
    trailing CLEAN transition that never even runs) must roll back. Proves
    §3.4's "never faked via sequential separately-committed calls"."""
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        bad_percentile = make_percentile(
            calculation_version=CALC_VERSION,
            bucket_ts=_t(0), sample_window_end=_t(0))   # violates "< bucket_ts"

        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[bad_percentile],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

        # nothing from ANY family persisted
        async with db.pool.acquire() as conn:
            efv_n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
            cfv_n = await conn.fetchval("SELECT count(*) FROM consensus_feature_vectors")
            dhs_n = await conn.fetchval("SELECT count(*) FROM data_health_snapshots")
        assert (efv_n, cfv_n, dhs_n) == (0, 0, 0)

        # still DIRTY -- the CLEAN transition never committed
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "DIRTY"
        assert state.publication_generation == 0

    _run(body)


# ============================================================================
# 4. open_v2_coherent_read_session
# ============================================================================
def test_coherent_session_fails_closed_on_dirty_scope():
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE):
                raise AssertionError("must never yield a session for a DIRTY scope")
        assert excinfo.value.status == "DIRTY"

    _run(body)


def test_coherent_session_fails_closed_on_unbootstrapped_scope():
    async def body(db, _dsn):
        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(symbol="ETHUSDT", market_type=MARKET_TYPE):
                raise AssertionError("must never yield a session for an unbootstrapped scope")
        assert excinfo.value.status == "UNINITIALIZED"

    _run(body)


def test_coherent_session_structurally_satisfies_both_ports():
    async def body(db, _dsn):
        async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
            assert isinstance(session, V2AlignedInputReader)
            assert isinstance(session, V2SetupHistoryReader)

    _run(body)


def test_coherent_session_reads_real_data_on_pinned_connection():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=42.0)
        async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
            rows = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
        assert len(rows) == 1
        assert rows[0]["close"] == 42.0

    _run(body)


# -- the SIX mandatory real-Postgres concurrency vectors ---------------------
def test_vector_1_old_snapshot_survives_later_correction():
    """Session opens while CLEAN and reads a raw kline; a fully separate
    connection then corrects that SAME kline and marks DIRTY, and COMMITS.
    The already-open session's reads must still observe the OLD value --
    the correction happened AFTER this session's REPEATABLE READ snapshot
    was taken."""
    async def body(db, scoped_dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")

        async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
            before = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            assert before[0]["close"] == 100.0

            # A fully independent connection performs + commits a correction.
            await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")
            outside_state = await db.fetch_stage2_publication_state(
                symbol=SYMBOL, market_type=MARKET_TYPE)
            assert outside_state.status == "DIRTY"   # the correction really did commit

            # Same session, same pinned snapshot -- still OLD.
            after = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            assert after[0]["close"] == 100.0

    _run(body)


def test_vector_2_raw_new_derived_old_gap_fails_closed():
    """THE regression H2e closes: after a raw correction commits (marking
    DIRTY), a NEW session opened afterward must refuse immediately -- it
    must never reach a Stage 3/5 read with a stale derived view. This is
    exactly the gap a bare REPEATABLE READ transaction (H2c's raw-bundle
    reader) does NOT close, since that only wraps ONE feature request's own
    reads, not this broader decision-view boundary."""
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")   # correction -> DIRTY

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE):
                raise AssertionError("must never reach a Stage 3/5 read")

    _run(body)


def test_vector_3_partial_final_publication_rolls_back():
    """Same proof as `test_publish_stage2_correction_rolls_back_atomically_on_mid_batch_failure`,
    named to map 1:1 onto the task's six mandatory vectors."""
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        bad_percentile = make_percentile(
            calculation_version=CALC_VERSION, bucket_ts=_t(0), sample_window_end=_t(0))
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[bad_percentile],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        state = await db.fetch_stage2_publication_state(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert state.status == "DIRTY"

    _run(body)


def test_vector_4_successful_final_publication_becomes_visible():
    async def body(db, _dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")   # -> DIRTY

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE):
                raise AssertionError("still dirty")

        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )

        async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
            rows = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            cfv = await session.fetch_v2_consensus_feature(
                symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
                bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION)
        assert rows[0]["close"] == 999.0
        assert cfv is not None

    _run(body)


def test_vector_5_dirty_survives_restart_reconnect():
    """No process-local boolean authority -- DIRTY is a durable row. Marking
    it via one `Database`/pool instance and then reading it back via a
    COMPLETELY FRESH `Database`/pool instance (simulating a process restart)
    must still see DIRTY."""
    async def body(db, scoped_dsn):
        from storage.stage2_publication_state import mark_publication_dirty
        async with db.pool.acquire() as conn:
            await mark_publication_dirty(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        fresh_db = Database(scoped_dsn)
        await fresh_db.connect()
        try:
            state = await fresh_db.fetch_stage2_publication_state(
                symbol=SYMBOL, market_type=MARKET_TYPE)
            assert state.status == "DIRTY"
            assert state.dirty_reason == "X"
        finally:
            await fresh_db.close()

    _run(body)


def test_vector_6_same_snapshot_no_reconnect_toctou():
    """Structurally proves there is no connection-A-then-connection-B TOCTOU:
    the publication-state check and every subsequent read inside one session
    are issued on the exact same asyncpg connection object, so a concurrent
    commit between two reads of the SAME session is provably invisible to
    the second read (not merely by convention -- by the connection identity
    itself never changing)."""
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=1.0, source="backfill")
        await _seed_kline(db, ts=_t(2), close=2.0, source="backfill")

        async with db.open_v2_coherent_read_session(symbol=SYMBOL, market_type=MARKET_TYPE) as session:
            conn_identity = session._conn   # noqa: SLF001 -- structural proof, this test's whole point
            r1 = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(3))
            assert session._conn is conn_identity   # noqa: SLF001

            # Concurrent correction + DIRTY mark on a fully separate connection.
            await _seed_kline(db, ts=_t(1), close=1000.0, source="backfill")

            r2 = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(3))
            assert session._conn is conn_identity   # noqa: SLF001
            assert r1 == r2   # identical -- same pinned snapshot both times

    _run(body)
