"""Real-PostgreSQL proofs for the V2-H2e correction-publication coherence
barrier (`docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` §3.4):
`storage/stage2_publication_state.py` (revision-comparison model, tech-lead
review round 2), `Database.publish_stage2_correction`,
`Database.open_v2_coherent_read_session`, and the raw-revision bumping
wired into `insert_klines`/`insert_open_interest`/`insert_funding`.

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
calls. Output-row dataclass factories (`make_efv`/`make_consensus`/
`make_percentile`/`make_health`) are reused from
`tests/storage/test_stage2_writers.py`.

Sections:
  1. `stage2_raw_revision`/`stage2_publication_state` basics (bootstrap/
     read/bump/CAS).
  2. Raw-writer revision-bumping (`insert_klines`/`insert_open_interest`/
     `insert_funding`) -- a correction bumps; a first-ever insert into an
     UNPUBLISHED range does not; a first-ever insert into an ALREADY-
     PUBLISHED bucket DOES (finding 2); arity/duplicate-key hardening
     (finding 7).
  3. `publish_stage2_correction` -- mandatory-family, scope/version-
     binding, and truthful-absence validation (finding 5), the CAS
     (finding 1), and the atomic all-or-nothing rollback proof.
  4. `open_v2_coherent_read_session` -- fail-closed on STALE/
     NEVER_PUBLISHED/unbootstrapped, structural Protocol satisfaction,
     session identity binding (finding 4), and the full set of mandatory
     real-Postgres concurrency vectors (six original + finding-specific
     additions: overlapping-correction CAS rejection, late-first-insert
     invalidation, active-vs-superseded calc_version, legacy/deploy-order
     bootstrap fail-closed).
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
from storage.stage2_publication_state import V2PublicationDirtyError, V2StalePublicationError
from storage.v2_coherent_read_session import V2CoherentReadSession, V2SessionIdentityError
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
CALC_VERSION_OLD = "c" * 16
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

_STAGE2_RAW_REVISION_DDL = """
CREATE TABLE stage2_raw_revision (
    symbol TEXT NOT NULL, market_type TEXT NOT NULL, raw_revision BIGINT NOT NULL DEFAULT 0,
    last_bump_reason TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, market_type),
    CONSTRAINT ck_srr_revision_nonneg CHECK (raw_revision >= 0)
);
"""

_STAGE2_PUBLICATION_STATE_DDL = """
CREATE TABLE stage2_publication_state (
    symbol TEXT NOT NULL, market_type TEXT NOT NULL, calculation_version TEXT NOT NULL,
    published_raw_revision BIGINT NOT NULL, publication_generation BIGINT NOT NULL DEFAULT 1,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, market_type, calculation_version),
    CONSTRAINT ck_sps_revision_nonneg CHECK (published_raw_revision >= 0),
    CONSTRAINT ck_sps_generation_positive CHECK (publication_generation > 0)
);
"""

_ALL_DDL = (
    _KLINES_1M_DDL, _OPEN_INTEREST_DDL, _FUNDING_RATE_DDL,
    _EXCHANGE_INSTRUMENTS_DDL, _EXCHANGE_INSTRUMENT_HISTORY_DDL,
    _STAGE2_INSTRUMENT_METADATA_STATE_DDL, _STAGE2_RAW_REVISION_DDL, _STAGE2_PUBLICATION_STATE_DDL,
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


async def _with_isolated_schema(body, *, ddl=_ALL_DDL):
    """Fresh, uniquely-named schema with every table this module's tests
    touch (or a caller-supplied subset via `ddl`); seeds ONE instrument
    (bootstrap revision 1, tick=0.10) + bootstraps `stage2_raw_revision` at
    0 for `(SYMBOL, MARKET_TYPE)` -- deliberately NEVER bootstraps
    `stage2_publication_state` (see that module's docstring: no automatic
    CLEAN path exists at all). Runs `body(db, scoped_dsn)`; unconditionally
    drops the schema after."""
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
            for stmt in ddl:
                await conn.execute(stmt)
        if _EXCHANGE_INSTRUMENTS_DDL in ddl:
            await db.bootstrap_instrument_metadata_revision(initial_revision=1)
            await db.upsert_exchange_instrument(
                exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
                exchange_instrument_id=SYMBOL, quantity_unit="base",
                contract_multiplier=None, tick_size=0.10, price_precision=1,
                quantity_precision=3, metadata_source="exchange_api",
                fetched_at=_t(0), is_stale=False)
        if _STAGE2_RAW_REVISION_DDL in ddl:
            await db.bootstrap_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        await body(db, scoped_dsn)
    finally:
        await db.close()
        cleanup = await _connect_admin()
        try:
            await cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        finally:
            await cleanup.close()


def _run(body, **kw):
    asyncio.run(_with_isolated_schema(body, **kw))


async def _seed_kline(db, *, ts, close=100.0, source="live"):
    await db.insert_klines(
        [(EXCHANGE, SYMBOL, ts, close, close, close, close, 1.0, None, None, None)],
        source=source)


async def _seed_published_efv_bucket(conn, *, timeframe="1m", bucket_ts):
    """Directly insert ONE minimal `exchange_feature_vectors` row -- the
    fact `_fresh_rows_affect_published_bucket` checks for -- WITHOUT going
    through `publish_stage2_correction` (this helper is for setting up the
    "already published" precondition finding-2 tests need, not for
    exercising the publish API itself)."""
    await conn.execute(
        """
        INSERT INTO exchange_feature_vectors
            (exchange, symbol, market_type, timeframe, bucket_ts,
             feature_schema_version, calculation_version, config_hash, config_version, code_version)
        VALUES ($1,$2,$3,$4,$5,1,$6,$7,$8,$9)
        """,
        EXCHANGE, SYMBOL, MARKET_TYPE, timeframe, bucket_ts, CALC_VERSION,
        "a" * 64, "2.1.0", "code-v1",
    )


# ============================================================================
# 1. stage2_raw_revision / stage2_publication_state basics
# ============================================================================
def test_bootstrap_raw_revision_idempotent_starts_zero():
    async def body(db, _dsn):
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 0
        result = await db.bootstrap_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert result == "ALREADY_INITIALIZED"

    _run(body)


def test_unbootstrapped_scope_raw_revision_is_none():
    async def body(db, _dsn):
        rev = await db.fetch_stage2_raw_revision(symbol="ETHUSDT", market_type=MARKET_TYPE)
        assert rev is None
        state = await db.fetch_stage2_publication_state(
            symbol="ETHUSDT", market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state is None   # stage2_raw_revision itself absent -> fully uninitialized

    _run(body)


def test_never_published_state_when_raw_revision_exists_but_no_publication_row():
    async def body(db, _dsn):
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state is not None
        assert state.raw_revision == 0
        assert state.published_raw_revision is None
        assert state.status == "NEVER_PUBLISHED"
        assert state.is_clean is False

    _run(body)


def test_bump_raw_revision_creates_row_at_one_if_unbootstrapped():
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            new_rev = await bump_raw_revision(
                conn, symbol="ETHUSDT", market_type=MARKET_TYPE, reason="TEST")
        assert new_rev == 1

    _run(body)


def test_bump_raw_revision_increments_by_exactly_one():
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            r1 = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="A")
            r2 = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="B")
        assert (r1, r2) == (1, 2)

    _run(body)


def test_mark_publication_clean_cas_success_bumps_generation():
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision, mark_publication_clean_cas
        async with db.pool.acquire() as conn:
            rev = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")
            gen = await mark_publication_clean_cas(
                conn, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=rev)
        assert gen == 1
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state.is_clean
        assert state.published_raw_revision == rev

    _run(body)


def test_mark_publication_clean_cas_rejects_stale_expected_revision():
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision, mark_publication_clean_cas
        async with db.pool.acquire() as conn:
            await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="A")
            await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="B")
            with pytest.raises(V2StalePublicationError) as excinfo:
                await mark_publication_clean_cas(
                    conn, symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                    expected_raw_revision=1)   # current is 2
        assert excinfo.value.expected_raw_revision == 1
        assert excinfo.value.actual_raw_revision == 2

    _run(body)


# ============================================================================
# 2. Raw-writer revision-bumping
# ============================================================================
def test_first_ever_kline_insert_does_not_bump_revision():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1))
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 0

    _run(body)


def test_kline_correction_bumps_revision_same_commit():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        rev1 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev1 == 0

        # A correction: same (exchange, symbol, ts), different close.
        await _seed_kline(db, ts=_t(1), close=101.0, source="backfill")
        rev2 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev2 == 1

    _run(body)


def test_open_interest_correction_bumps_revision():
    async def body(db, _dsn):
        row = (EXCHANGE, SYMBOL, _t(1), 1000.0, "base", None, None, None)
        await db.insert_open_interest([row], source="live")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 0

        corrected = (EXCHANGE, SYMBOL, _t(1), 1200.0, "base", None, None, None)
        await db.insert_open_interest([corrected], source="live")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 1

    _run(body)


def test_funding_correction_bumps_revision():
    async def body(db, _dsn):
        row = (EXCHANGE, SYMBOL, _t(1), 0.0001, None)
        await db.insert_funding([row], source="live")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 0

        corrected = (EXCHANGE, SYMBOL, _t(1), 0.0002, None)
        await db.insert_funding([corrected], source="live")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 1

    _run(body)


def test_correction_for_unmapped_instrument_does_not_raise_or_bump():
    async def body(db, _dsn):
        # "ETHUSDT" has no exchange_instruments row in this schema.
        row = (EXCHANGE, "ETHUSDT", _t(1), 100.0, 100.0, 100.0, 100.0, 1.0, None, None, None)
        await db.insert_klines([row], source="backfill")
        corrected = (EXCHANGE, "ETHUSDT", _t(1), 101.0, 101.0, 101.0, 101.0, 1.0, None, None, None)
        await db.insert_klines([corrected], source="backfill")   # must not raise
        rev = await db.fetch_stage2_raw_revision(symbol="ETHUSDT", market_type=MARKET_TYPE)
        assert rev is None   # never bootstrapped, never fabricated

    _run(body)


def test_first_insert_into_already_published_bucket_bumps_revision():
    """Finding 2: a late gap-fill that is a genuine FIRST-ever insert
    (`xmax = 0`) but lands inside a bucket `exchange_feature_vectors`
    ALREADY has a published row for must invalidate it -- "row already
    existed" is not the only correction signal."""
    async def body(db, _dsn):
        # Pretend Stage 2 already published the 1m bucket at _t(0) (i.e.
        # a bucket covering [_t(0), _t(1))) BEFORE the late bar arrives.
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="1m", bucket_ts=_t(0))

        # A genuinely first-ever kline insert at _t(0) -- exactly the
        # published bucket's own start.
        await _seed_kline(db, ts=_t(0), close=100.0, source="backfill")
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 1, "a first-ever insert into an ALREADY-PUBLISHED bucket must bump"

    _run(body)


def test_first_insert_outside_any_published_bucket_does_not_bump():
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="1m", bucket_ts=_t(0))

        # First-ever insert far outside the published bucket's range.
        await _seed_kline(db, ts=_t(500), close=100.0, source="backfill")
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 0

    _run(body)


def test_first_insert_into_published_5m_bucket_bumps_revision():
    """The containment check spans every timeframe exchange_feature_vectors
    tracks, not just 1m -- a bar landing inside an already-published 5m
    bucket must ALSO invalidate it."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="5m", bucket_ts=_t(0))

        # _t(3) is inside [_t(0), _t(5)) -- the published 5m bucket.
        await _seed_kline(db, ts=_t(3), close=100.0, source="backfill")
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 1

    _run(body)


# -- CodeRabbit review (tech-lead review round 3): exact per-timeframe
# containment boundaries, and the fail-closed unknown-timeframe fix --------
@pytest.mark.parametrize("timeframe,minutes", [
    ("1m", 1), ("5m", 5), ("15m", 15), ("1h", 60), ("4h", 240),
])
def test_every_known_timeframe_maps_to_its_correct_containing_interval(timeframe, minutes):
    """Every one of the five Stage-2-supported timeframes
    (`analytics/feature_engine/models.py::TIMEFRAME_MINUTES`) must map to
    its OWN exact half-open `[bucket_ts, bucket_ts + timeframe)` window --
    the bucket's own start bumps, one minute before it does not, the last
    minute inside the window bumps, and the bucket's own end (exclusive)
    does not."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe=timeframe, bucket_ts=_t(100))

        # One minute BEFORE the bucket start -- outside, must not bump.
        await _seed_kline(db, ts=_t(99), close=1.0, source="backfill")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 0

        # The bucket's own start -- inside (inclusive), must bump.
        await _seed_kline(db, ts=_t(100), close=1.0, source="backfill")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 1

        # The last minute still inside the window -- must bump (new pair,
        # fresh scope, so re-use a NEW symbol to isolate from the bump above).
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe=timeframe, bucket_ts=_t(300))
        last_minute_inside = _t(300 + minutes - 1)
        await _seed_kline(db, ts=last_minute_inside, close=1.0, source="backfill")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 2

        # The bucket's own end -- exclusive, outside, must NOT bump.
        bucket_end = _t(300 + minutes)
        await _seed_kline(db, ts=bucket_end, close=1.0, source="backfill")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 2

    _run(body)


def test_unknown_timeframe_fails_closed_and_always_bumps():
    """CodeRabbit finding (tech-lead review round 3): `exchange_feature_vectors
    .timeframe` is not structurally constrained anywhere (no DB CHECK, no
    dataclass validation) -- an unrecognized value must NEVER silently
    behave as an always-false containment window (the old `ELSE interval
    '0'` bug). A first-ever insert at a timestamp far outside any
    "reasonable" window must still bump when an existing row carries an
    unrecognized timeframe."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="3m", bucket_ts=_t(0))

        # Far outside any plausible bucket width -- would NOT have bumped
        # under the old `ELSE interval '0'` behavior (which always
        # evaluates the containment predicate to false), but MUST bump now.
        await _seed_kline(db, ts=_t(99_999), close=1.0, source="backfill")
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 1, "an unrecognized timeframe must fail closed, never silently exclude"

    _run(body)


def test_known_timeframe_unaffected_rows_still_do_not_bump():
    """Sanity companion to the fail-closed fix: an existing row with a
    RECOGNIZED timeframe whose window genuinely does not contain the fresh
    ts must still correctly NOT bump (the fix only changes behavior for
    unrecognized timeframes, never adds false positives for known ones)."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="1h", bucket_ts=_t(0))

        await _seed_kline(db, ts=_t(9999), close=1.0, source="backfill")
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev == 0

    _run(body)


# -- finding 7: raw-writer regression hardening ------------------------------
def test_insert_klines_rejects_ragged_batch_before_any_db_call():
    async def body(db, _dsn):
        good = (EXCHANGE, SYMBOL, _t(1), 1.0, 1.0, 1.0, 1.0, 1.0, None, None, None)
        ragged = (EXCHANGE, SYMBOL, _t(2), 1.0, 1.0, 1.0, 1.0, 1.0, None, None)   # one short
        with pytest.raises(ValueError, match="insert_klines"):
            await db.insert_klines([good, ragged], source="backfill")
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM klines_1m")
        assert n == 0   # nothing committed -- rejected before any DB call

    _run(body)


def test_insert_open_interest_rejects_ragged_batch():
    async def body(db, _dsn):
        ragged = (EXCHANGE, SYMBOL, _t(1), 1.0, "base", None, None)   # one short
        with pytest.raises(ValueError, match="insert_open_interest"):
            await db.insert_open_interest([ragged], source="live")

    _run(body)


def test_insert_funding_rejects_ragged_batch():
    async def body(db, _dsn):
        ragged = (EXCHANGE, SYMBOL, _t(1), 0.0001)   # one short (missing next_funding_time)
        with pytest.raises(ValueError, match="insert_funding"):
            await db.insert_funding([ragged], source="live")

    _run(body)


def test_insert_klines_duplicate_key_in_batch_last_write_wins():
    """A batch containing the SAME (exchange, symbol, ts) key twice must
    not raise a Postgres CardinalityViolation -- the LAST occurrence's
    values win, deterministically, matching the old per-row `executemany`
    behavior."""
    async def body(db, _dsn):
        first = (EXCHANGE, SYMBOL, _t(1), 1.0, 1.0, 1.0, 1.0, 1.0, None, None, None)
        second = (EXCHANGE, SYMBOL, _t(1), 2.0, 2.0, 2.0, 2.0, 2.0, None, None, None)
        written = await db.insert_klines([first, second], source="backfill")
        assert written == 1   # deduped count, not raw input length
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT close FROM klines_1m WHERE exchange=$1 AND symbol=$2 AND ts=$3",
                EXCHANGE, SYMBOL, _t(1))
        assert row["close"] == 2.0   # the LAST occurrence's value won

    _run(body)


# ============================================================================
# 3. publish_stage2_correction
# ============================================================================
def test_publish_stage2_correction_success_writes_all_and_bumps_generation():
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            rev = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        result = await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev,
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
        assert result.published_raw_revision == rev

        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state.is_clean
        assert state.publication_generation == 1

        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 1

    _run(body)


def test_publish_stage2_correction_rejects_empty_mandatory_efv():
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="exchange_feature_vectors"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=(),
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

    _run(body)


def test_publish_stage2_correction_rejects_empty_mandatory_cfv():
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="consensus_feature_vectors"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=(),
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

    _run(body)


def test_publish_stage2_correction_rejects_wrong_scope_row_before_connection():
    async def body(db, _dsn):
        wrong_symbol_row = make_efv(symbol="ETHUSDT", calculation_version=CALC_VERSION)
        with pytest.raises(ValueError, match="does not match declared symbol"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=[wrong_symbol_row],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 0

    _run(body)


def test_publish_stage2_correction_rejects_wrong_market_type_row():
    async def body(db, _dsn):
        wrong_mt_row = make_consensus(market_type="spot", calculation_version=CALC_VERSION)
        with pytest.raises(ValueError, match="does not match declared market_type"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[wrong_mt_row],
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

    _run(body)


def test_publish_stage2_correction_rejects_mixed_calculation_version():
    async def body(db, _dsn):
        other_version_row = make_efv(calculation_version=CALC_VERSION_OLD)
        with pytest.raises(ValueError, match="does not match declared calculation_version"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION), other_version_row],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

    _run(body)


def test_publish_stage2_correction_requires_absent_reason_for_empty_percentiles():
    async def body(db, _dsn):
        with pytest.raises(ValueError, match="percentile_snapshots"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=0,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=(),
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 0

    _run(body)


def test_publish_stage2_correction_accepts_absent_reason_when_family_truly_na():
    async def body(db, _dsn):
        result = await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=0,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=(),
            percentile_snapshots_absent_reason="no percentile orchestrator implemented (D-008)",
            data_health_snapshots=(),
            data_health_snapshots_absent_reason="no health recompute for this correction",
        )
        assert result.percentile_snapshots_written == 0
        assert result.percentile_snapshots_absent_reason == "no percentile orchestrator implemented (D-008)"
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state.is_clean

    _run(body)


def test_publish_stage2_correction_rejects_absent_reason_when_rows_already_exist():
    """Finding 5D: an absent_reason string is NOT sufficient proof once
    percentile_snapshots ALREADY has rows for this exact scope+version --
    "no orchestrator implemented" cannot substitute for a real recompute."""
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision

        async with db.pool.acquire() as conn:
            rev1 = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev1,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )

        async with db.pool.acquire() as conn:
            rev2 = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="Y")
        with pytest.raises(ValueError, match="NOT provably N/A"):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=rev2,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=(),
                percentile_snapshots_absent_reason="skipping percentile repair to save time",
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        # still stale at rev1 -- the second publish attempt never committed
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state.published_raw_revision == rev1

    _run(body)


def test_publish_stage2_correction_rolls_back_atomically_on_check_violation():
    """A percentile row violating `ck_ps_no_lookahead` fails the family
    write -- the whole transaction (including the exchange/consensus
    families already written earlier in the SAME transaction, and the
    trailing CAS'd CLEAN transition that never even runs) must roll back."""
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            rev = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        bad_percentile = make_percentile(
            calculation_version=CALC_VERSION,
            bucket_ts=_t(0), sample_window_end=_t(0))   # violates "< bucket_ts"

        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=rev,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[bad_percentile],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )

        async with db.pool.acquire() as conn:
            efv_n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
            cfv_n = await conn.fetchval("SELECT count(*) FROM consensus_feature_vectors")
            dhs_n = await conn.fetchval("SELECT count(*) FROM data_health_snapshots")
        assert (efv_n, cfv_n, dhs_n) == (0, 0, 0)

        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert not state.is_clean
        assert state.published_raw_revision is None   # never reached CAS

    _run(body)


# ============================================================================
# 4. open_v2_coherent_read_session
# ============================================================================
def test_coherent_session_fails_closed_on_never_published_scope():
    async def body(db, _dsn):
        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must never yield a session for a NEVER_PUBLISHED scope")
        assert excinfo.value.status == "NEVER_PUBLISHED"

    _run(body)


def test_coherent_session_fails_closed_on_unbootstrapped_scope():
    async def body(db, _dsn):
        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(
                symbol="ETHUSDT", market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must never yield a session for an unbootstrapped scope")
        assert excinfo.value.status == "UNINITIALIZED"

    _run(body)


async def _publish_clean(db, *, calculation_version=CALC_VERSION):
    """Test-only convenience: read the current revision and publish a
    minimal valid correction, returning the revision it published at."""
    rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
    await db.publish_stage2_correction(
        symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=calculation_version,
        expected_raw_revision=rev,
        exchange_feature_vectors=[make_efv(calculation_version=calculation_version)],
        consensus_feature_vectors=[make_consensus(calculation_version=calculation_version)],
        percentile_snapshots=[make_percentile(calculation_version=calculation_version)],
        data_health_snapshots=[make_health(calculation_version=calculation_version)],
    )
    return rev


def test_coherent_session_fails_closed_on_stale_scope():
    async def body(db, _dsn):
        await _publish_clean(db)
        # A correction after the publish -> stale again.
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")

        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must never yield a session for a STALE scope")
        assert excinfo.value.status == "STALE"

    _run(body)


def test_coherent_session_structurally_satisfies_both_ports():
    async def body(db, _dsn):
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            assert isinstance(session, V2AlignedInputReader)
            assert isinstance(session, V2SetupHistoryReader)

    _run(body)


def test_coherent_session_reads_real_data_on_pinned_connection():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=42.0)
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            rows = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
        assert len(rows) == 1
        assert rows[0]["close"] == 42.0

    _run(body)


# -- finding 4: session identity binding -------------------------------------
def test_session_identity_binding_rejects_wrong_calculation_version_before_sql():
    async def body(db, _dsn):
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            with pytest.raises(V2SessionIdentityError):
                await session.fetch_v2_consensus_feature(
                    symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
                    bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION_OLD)

    _run(body)


def test_session_identity_binding_rejects_wrong_symbol_before_sql():
    async def body(db, _dsn):
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            with pytest.raises(V2SessionIdentityError):
                await session.fetch_v2_reference_klines(
                    exchange=EXCHANGE, symbol="ETHUSDT", bucket_start=_t(0), bucket_end=_t(2))

    _run(body)


def test_session_identity_binding_rejects_wrong_market_type_before_sql():
    async def body(db, _dsn):
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            with pytest.raises(V2SessionIdentityError):
                await session.fetch_v2_instrument(
                    exchange=EXCHANGE, symbol=SYMBOL, market_type="spot", as_of=_t(1))

    _run(body)


def test_session_after_calc_a_read_rejects_calc_b_read_on_same_session():
    async def body(db, _dsn):
        await _publish_clean(db)
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            ok = await session.fetch_v2_consensus_feature(
                symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
                bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION)
            assert ok is not None
            with pytest.raises(V2SessionIdentityError):
                await session.fetch_v2_consensus_feature(
                    symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
                    bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION_OLD)

    _run(body)


def test_session_identity_mismatch_never_touches_the_connection():
    """No DB read for the mismatched call: constructs a `V2CoherentReadSession`
    directly over a "poison" connection stub that raises if ANY attribute is
    ever accessed -- a structural (not merely behavioral) proof that the
    identity check runs, and raises, entirely in Python before any
    delegation to `self._conn`. No real Postgres needed for this proof."""
    class _PoisonConn:
        def __getattr__(self, name):
            raise AssertionError(f"session must not touch the connection ({name!r} accessed)")

    session = V2CoherentReadSession(
        _PoisonConn(), symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)

    async def call_mismatched():
        await session.fetch_v2_consensus_feature(
            symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
            bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION_OLD)

    with pytest.raises(V2SessionIdentityError):
        asyncio.run(call_mismatched())


# -- the six original mandatory real-Postgres concurrency vectors -----------
def test_vector_1_old_snapshot_survives_later_correction():
    """Session opens while CLEAN and reads a raw kline; a fully separate
    connection then corrects that SAME kline (bumping the raw revision --
    STALE), and COMMITS. The already-open session's reads must still
    observe the OLD value -- the correction happened AFTER this session's
    REPEATABLE READ snapshot was taken."""
    async def body(db, scoped_dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _publish_clean(db)

        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            before = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            assert before[0]["close"] == 100.0

            # A fully independent connection performs + commits a correction.
            await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")
            outside_state = await db.fetch_stage2_publication_state(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
            assert not outside_state.is_clean   # the correction really did commit

            # Same session, same pinned snapshot -- still OLD.
            after = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            assert after[0]["close"] == 100.0

    _run(body)


def test_vector_2_raw_new_derived_old_gap_fails_closed():
    """THE regression H2e closes: after a raw correction commits (bumping
    the revision -> STALE), a NEW session opened afterward must refuse
    immediately -- it must never reach a Stage 3/5 read with a stale
    derived view."""
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _publish_clean(db)
        await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")   # correction -> STALE

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must never reach a Stage 3/5 read")

    _run(body)


def test_vector_3_partial_final_publication_rolls_back():
    """Same proof as `test_publish_stage2_correction_rolls_back_atomically_on_check_violation`,
    named to map 1:1 onto the task's mandatory vectors."""
    async def body(db, _dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            rev = await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        bad_percentile = make_percentile(
            calculation_version=CALC_VERSION, bucket_ts=_t(0), sample_window_end=_t(0))
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=rev,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[bad_percentile],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert not state.is_clean

    _run(body)


def test_vector_4_successful_final_publication_becomes_visible():
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=999.0, source="backfill")   # -> revision 1

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("still never-published")

        rev = await _publish_clean(db)
        assert rev == 1

        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            rows = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(2))
            cfv = await session.fetch_v2_consensus_feature(
                symbol=SYMBOL, market_type=MARKET_TYPE, timeframe="5m",
                bucket_ts=_WRITERS_B, calculation_version=CALC_VERSION)
        assert rows[0]["close"] == 999.0
        assert cfv is not None

    _run(body)


def test_vector_5_dirty_survives_restart_reconnect():
    """No process-local boolean authority -- staleness is a durable
    revision-comparison fact. Bumping via one `Database`/pool instance and
    then reading it back via a COMPLETELY FRESH `Database`/pool instance
    (simulating a process restart) must still see the same, still-stale
    revision fact."""
    async def body(db, scoped_dsn):
        from storage.stage2_publication_state import bump_raw_revision
        async with db.pool.acquire() as conn:
            await bump_raw_revision(conn, symbol=SYMBOL, market_type=MARKET_TYPE, reason="X")

        fresh_db = Database(scoped_dsn)
        await fresh_db.connect()
        try:
            state = await fresh_db.fetch_stage2_publication_state(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
            assert state.raw_revision == 1
            assert not state.is_clean
        finally:
            await fresh_db.close()

    _run(body)


def test_vector_6_same_snapshot_no_reconnect_toctou():
    """Structurally proves there is no connection-A-then-connection-B TOCTOU:
    the publication-state check and every subsequent read inside one session
    are issued on the exact same asyncpg connection object, so a concurrent
    commit between two reads of the SAME session is provably invisible to
    the second read."""
    async def body(db, _dsn):
        await _seed_kline(db, ts=_t(1), close=1.0, source="backfill")
        await _seed_kline(db, ts=_t(2), close=2.0, source="backfill")
        await _publish_clean(db)

        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ) as session:
            conn_identity = session._conn   # noqa: SLF001 -- structural proof, this test's whole point
            r1 = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(3))
            assert session._conn is conn_identity   # noqa: SLF001

            # Concurrent correction on a fully separate connection.
            await _seed_kline(db, ts=_t(1), close=1000.0, source="backfill")

            r2 = await session.fetch_v2_reference_klines(
                exchange=EXCHANGE, symbol=SYMBOL, bucket_start=_t(0), bucket_end=_t(3))
            assert session._conn is conn_identity   # noqa: SLF001
            assert r1 == r2   # identical -- same pinned snapshot both times

    _run(body)


# -- finding-specific additional mandatory vectors ---------------------------
def test_vector_7_overlapping_corrections_stale_publisher_cas_rejected():
    """Finding 1's exact trace: correction #1 bumps to revision 1; a
    publisher reads that revision and starts "computing"; correction #2
    bumps to revision 2 WHILE the publisher is still working; the
    publisher's final publish (still targeting revision 1) MUST be
    rejected atomically, leaving the scope exactly as stale as before (no
    partial revision-1 publication survives); a publisher for the CURRENT
    revision (2) then succeeds."""
    async def body(db, _dsn):
        # A. correction #1 -> revision 1
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=101.0, source="backfill")
        rev_at_publisher_start = await db.fetch_stage2_raw_revision(
            symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev_at_publisher_start == 1

        # B. publisher A "begins" (just remembers the revision it read)

        # C. correction #2 -> revision 2, committed BEFORE the publish attempt
        await _seed_kline(db, ts=_t(2), close=200.0, source="backfill")
        await _seed_kline(db, ts=_t(2), close=201.0, source="backfill")
        assert await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE) == 2

        # D/E. publisher A attempts final publication at the STALE revision.
        with pytest.raises(V2StalePublicationError) as excinfo:
            await db.publish_stage2_correction(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
                expected_raw_revision=rev_at_publisher_start,
                exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
                consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
                percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
                data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
            )
        assert excinfo.value.expected_raw_revision == 1
        assert excinfo.value.actual_raw_revision == 2

        # F/G. state remains exactly as stale as before; no partial publish.
        state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert not state.is_clean
        assert state.published_raw_revision is None
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM exchange_feature_vectors")
        assert n == 0

        # Then: a publisher for the CURRENT revision succeeds.
        rev_now = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        result = await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev_now,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )
        assert result.published_raw_revision == 2
        state2 = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state2.is_clean

    _run(body)


def test_cas_row_lock_serializes_concurrent_publisher_and_corrector():
    """CodeRabbit finding (tech-lead review round 3): `test_vector_7` above
    proves the CAS *outcome* (a stale `expected_raw_revision` is rejected),
    but correction #2 there already committed before the publisher even
    attempted its CAS -- it does not prove `SELECT ... FOR UPDATE` itself
    actually SERIALIZES a genuinely concurrent publisher and corrector on
    the SAME `stage2_raw_revision` row. This test proves the row lock
    itself, via a real held-open transaction plus a bounded-timeout,
    task-based non-completion assertion (never sleep alone as the proof):

      1. Publisher A starts a transaction and runs `mark_publication_clean_cas`
         (which internally locks the row `FOR UPDATE`) -- the transaction
         is deliberately left OPEN (not yet committed), so the row lock is
         still held.
      2. Corrector B, on a FULLY SEPARATE connection, concurrently attempts
         `bump_raw_revision` for the SAME `(symbol, market_type)`. Its
         `INSERT ... ON CONFLICT DO UPDATE` must acquire the same row's
         lock, so it cannot complete while A's transaction is open --
         proven by `asyncio.wait_for(..., timeout=...)` raising
         `TimeoutError` (a bounded wait to keep the test fast, not the
         proof mechanism itself) and `bump_task.done()` being False.
      3. Publisher A commits -- releases the lock.
      4. Corrector B's bump NOW completes.
      5. Final state: publication remains at the OLD (pre-correction)
         revision; the current raw_revision has advanced -- the scope is
         STALE, exactly as §3.4 requires."""
    async def body(db, scoped_dsn):
        from storage.stage2_publication_state import bump_raw_revision, mark_publication_clean_cas

        conn_a = await asyncpg.connect(scoped_dsn)
        conn_b = await asyncpg.connect(scoped_dsn)
        try:
            tx_a = conn_a.transaction()
            await tx_a.start()
            # Publisher A: CAS at the never-published baseline (revision 0)
            # -- holds stage2_raw_revision's row lock for as long as tx_a
            # stays open (SELECT ... FOR UPDATE inside mark_publication_clean_cas).
            gen = await mark_publication_clean_cas(
                conn_a, symbol=SYMBOL, market_type=MARKET_TYPE,
                calculation_version=CALC_VERSION, expected_raw_revision=0)
            assert gen == 1

            # Corrector B: a fully independent connection concurrently
            # attempts to bump the SAME scope's revision.
            bump_task = asyncio.create_task(
                bump_raw_revision(conn_b, symbol=SYMBOL, market_type=MARKET_TYPE,
                                   reason="CONCURRENT_WHILE_LOCKED"))

            # Bounded wait proving B does NOT complete while A's
            # transaction (and lock) is still open. `asyncio.shield` keeps
            # bump_task itself alive/uncancelled across this timeout so it
            # can be awaited for real once A releases the lock.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(bump_task), timeout=0.5)
            assert not bump_task.done(), "the row lock must genuinely block the concurrent bump"

            # Publisher A commits -- releases the lock.
            await tx_a.commit()

            # NOW corrector B's bump completes (bounded only to keep the
            # test from hanging forever on a genuine regression).
            new_rev = await asyncio.wait_for(bump_task, timeout=5)
            assert new_rev == 1

            # Final state: publication is stuck at the OLD revision (0);
            # the authoritative revision has moved on to 1 -- STALE.
            state = await db.fetch_stage2_publication_state(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
            assert state.published_raw_revision == 0
            assert state.raw_revision == 1
            assert not state.is_clean
        finally:
            await conn_a.close()
            await conn_b.close()

    _run(body)


def test_vector_8_late_first_insert_invalidates_published_history():
    """Finding 2's real-Postgres vector, via the actual raw writer (not a
    unit-level check): a bucket is already published; a late gap-fill
    INSERT (never seen before, `xmax = 0`) lands inside it; the scope must
    become stale and a coherent session must refuse."""
    async def body(db, _dsn):
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="1m", bucket_ts=_t(3))
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=0,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )
        state_before = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert state_before.is_clean

        # The late gap-fill: a bar at _t(3) never seen before.
        await _seed_kline(db, ts=_t(3), close=55.0, source="backfill")

        state_after = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert not state_after.is_clean

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must fail closed after the late first-insert")

    _run(body)


def test_vector_9_active_calc_repaired_while_superseded_calc_remains_stale():
    """Finding 3: repairing the ACTIVE calculation_version must NEVER
    silently authorize a SUPERSEDED calculation_version as CLEAN too."""
    async def body(db, _dsn):
        # Publish CALC_VERSION_OLD at revision 1.
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=101.0, source="backfill")   # -> revision 1
        rev1 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION_OLD,
            expected_raw_revision=rev1,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION_OLD)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION_OLD)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION_OLD)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION_OLD)],
        )

        # A further correction bumps the raw revision again (rev1 -> rev2) --
        # simulating deployment moving on to a NEW active calculation_version
        # that gets republished, while CALC_VERSION_OLD is never touched again.
        await _seed_kline(db, ts=_t(1), close=102.0, source="backfill")
        rev2 = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert rev2 == rev1 + 1
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev2,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )

        # ACTIVE version is CLEAN at rev2.
        active_state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION)
        assert active_state.is_clean and active_state.published_raw_revision == rev2

        # SUPERSEDED version is STILL stale -- it was published at rev1, but
        # the current revision is rev2, and nobody republished it.
        old_state = await db.fetch_stage2_publication_state(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION_OLD)
        assert not old_state.is_clean
        assert old_state.published_raw_revision == rev1

        with pytest.raises(V2PublicationDirtyError):
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION_OLD,
            ):
                raise AssertionError("a superseded calculation_version must remain fail-closed")

        # And the active version's session still works fine.
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ):
            pass

    _run(body)


def test_vector_11_legacy_pre_h2e_database_bootstrap_remains_fail_closed():
    """Finding 6: a "legacy" database that already has raw+derived Stage 2
    history but has NEVER had `stage2_raw_revision`/`stage2_publication_state`
    bootstrapped must NOT silently become CLEAN once those tables are
    introduced and bootstrapped -- a coherent session must remain
    fail-closed until an explicit, real publish happens."""
    async def body(db, _dsn):
        # Simulate pre-existing legacy history: raw klines + an already-
        # published-looking exchange_feature_vectors row, all written
        # BEFORE stage2_raw_revision/stage2_publication_state existed
        # (this schema already has those tables per the harness, but we
        # deliberately do NOT call bootstrap_stage2_raw_revision ourselves
        # here beyond what _with_isolated_schema already did at revision 0
        # -- the point is that NO publish ever ran for this scope).
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        async with db.pool.acquire() as conn:
            await _seed_published_efv_bucket(conn, timeframe="1m", bucket_ts=_t(1))

        # A fresh "deploy" re-runs the idempotent bootstrap (as
        # runtime/shadow_cli.py does on every startup) -- must NOT create a
        # CLEAN publication_state row.
        result = await db.bootstrap_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert result == "ALREADY_INITIALIZED"

        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("legacy history must never silently read as CLEAN")
        assert excinfo.value.status == "NEVER_PUBLISHED"

        # Only an explicit, real publish establishes CLEAN going forward.
        rev = await db.fetch_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        await db.publish_stage2_correction(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            expected_raw_revision=rev,
            exchange_feature_vectors=[make_efv(calculation_version=CALC_VERSION)],
            consensus_feature_vectors=[make_consensus(calculation_version=CALC_VERSION)],
            percentile_snapshots=[make_percentile(calculation_version=CALC_VERSION)],
            data_health_snapshots=[make_health(calculation_version=CALC_VERSION)],
        )
        async with db.open_v2_coherent_read_session(
            symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
        ):
            pass   # now succeeds

    _run(body)


def test_vector_12_correction_before_schema_init_remains_fail_closed():
    """Finding 6's deploy-order vector: raw writes commit through the
    tolerant Stage-1-only path (H2e schema entirely absent -- not even
    `exchange_instruments`/`stage2_raw_revision` exist yet), and ONLY
    afterward is Stage 2 schema initialized + bootstrapped. The bootstrap
    MUST NOT erase the resulting uncertainty by advertising CLEAN -- a
    coherent session must remain fail-closed until an explicit publish."""
    async def raw_only_body(db, scoped_dsn):
        # Only klines_1m exists -- no exchange_instruments, no
        # stage2_raw_revision, no Stage 2 output tables at all.
        await _seed_kline(db, ts=_t(1), close=100.0, source="backfill")
        await _seed_kline(db, ts=_t(1), close=101.0, source="backfill")   # a "correction", tolerated
        async with db.pool.acquire() as conn:
            n = await conn.fetchval("SELECT count(*) FROM klines_1m")
        assert n == 1   # the raw write itself always committed

        # NOW Stage 2 schema is introduced (simulating a later deploy).
        async with db.pool.acquire() as conn:
            for stmt in (
                _EXCHANGE_INSTRUMENTS_DDL, _EXCHANGE_INSTRUMENT_HISTORY_DDL,
                _STAGE2_INSTRUMENT_METADATA_STATE_DDL, _STAGE2_RAW_REVISION_DDL,
                _STAGE2_PUBLICATION_STATE_DDL, _EXCHANGE_FEATURE_VECTORS_DDL,
                _CONSENSUS_FEATURE_VECTORS_DDL, _PERCENTILE_SNAPSHOTS_DDL,
                _DATA_HEALTH_SNAPSHOTS_DDL,
            ):
                await conn.execute(stmt)
        await db.bootstrap_instrument_metadata_revision(initial_revision=1)
        await db.upsert_exchange_instrument(
            exchange=EXCHANGE, symbol=SYMBOL, market_type=MARKET_TYPE,
            exchange_instrument_id=SYMBOL, quantity_unit="base",
            contract_multiplier=None, tick_size=0.10, price_precision=1,
            quantity_precision=3, metadata_source="exchange_api",
            fetched_at=_t(0), is_stale=False)
        result = await db.bootstrap_stage2_raw_revision(symbol=SYMBOL, market_type=MARKET_TYPE)
        assert result == "SEEDED"

        # The bootstrap must NOT advertise CLEAN -- the earlier correction's
        # signal was necessarily lost (no table existed to record it in),
        # but that lost signal must never be resolved as an implicit CLEAN.
        with pytest.raises(V2PublicationDirtyError) as excinfo:
            async with db.open_v2_coherent_read_session(
                symbol=SYMBOL, market_type=MARKET_TYPE, calculation_version=CALC_VERSION,
            ):
                raise AssertionError("must remain fail-closed after a deploy-order race")
        assert excinfo.value.status == "NEVER_PUBLISHED"

    _run(raw_only_body, ddl=(_KLINES_1M_DDL,))
