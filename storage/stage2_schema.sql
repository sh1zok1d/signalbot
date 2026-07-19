-- BTC Signal Bot — Stage 2.1 schema (ADDITIVE, separate file).
--
-- Applied ONLY by db.init_stage2_schema() (never by Stage 1's init_schema()),
-- gated behind config/stage2.yaml stage2.enabled. Nothing here modifies, drops,
-- or points at any Stage 1 table (klines_1m, open_interest, exchange_capabilities,
-- …). Re-applying is safe: every object is IF NOT EXISTS / if_not_exists.
--
-- Source of truth: docs/STAGE2_SPEC.md §2 (Revision 0.2.2). This file is a
-- faithful transcription of that final normative DDL plus the three percentile
-- CHECK constraints required for Stage 2.1 (ck_ps_scope, ck_ps_scope_exchange,
-- ck_ps_no_lookahead). No FK constraints declared in Stage 2.1 (spec §4).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- Symbol registry (structural + lifecycle). Mirrors the existing
-- exchange_capabilities pattern: declarative Python data, upserted
-- idempotently at startup, queried via SQL by everything downstream.
-- ============================================================
CREATE TABLE IF NOT EXISTS symbols (
    symbol          TEXT PRIMARY KEY,
    base_asset      TEXT NOT NULL,
    quote_asset     TEXT NOT NULL,
    asset_tier      TEXT NOT NULL,             -- 'major' | 'major_alt' | ...
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    -- ACTIVE | DRAINING | DISABLED | DELISTED | DATA_UNAVAILABLE
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    disable_policy  TEXT NOT NULL DEFAULT 'drain',  -- drain | force_expire
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_symbol_status CHECK (
        status IN ('ACTIVE','DRAINING','DISABLED','DELISTED','DATA_UNAVAILABLE'))
);

-- Audit log per clarifications §18.
CREATE TABLE IF NOT EXISTS symbol_status_history (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    previous_status TEXT,
    new_status      TEXT NOT NULL,
    reason          TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    changed_by      TEXT,
    config_version  TEXT
);

-- ============================================================
-- exchange_instruments: ONE row per (exchange, symbol, market_type).
-- The authority for unit normalization. A NULL contract_multiplier where
-- quantity_unit='contracts' makes the instrument ineligible for notional
-- consensus (fail-closed). NULL means "unknown", never "1.0".
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_instruments (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,          -- canonical, e.g. BTCUSDT
    market_type           TEXT NOT NULL DEFAULT 'perp',
    exchange_instrument_id TEXT NOT NULL,         -- venue-native id, e.g. BTC-USDT-SWAP
    quantity_unit         TEXT,                   -- 'base' | 'contracts'
    contract_multiplier   DOUBLE PRECISION,       -- base asset per contract (OKX ctVal)
    tick_size             DOUBLE PRECISION,
    price_precision       INTEGER,
    quantity_precision    INTEGER,
    metadata_source       TEXT NOT NULL,          -- 'exchange_api' | 'declared_fallback' | 'manual'
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

-- ============================================================
-- symbol_exchange_capabilities: METRIC-LEVEL capability only. No unit/contract
-- columns — those live in exchange_instruments. Stage 1's exchange_capabilities
-- is NOT altered; this additive table adds the symbol/market_type dimension.
-- ============================================================
CREATE TABLE IF NOT EXISTS symbol_exchange_capabilities (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    metric                TEXT NOT NULL,
    live_supported        BOOLEAN NOT NULL,
    historical_supported  BOOLEAN NOT NULL,
    coverage_type         TEXT NOT NULL,      -- full|snapshot|aggregated|unavailable
    expected_freshness_s  INTEGER,
    enabled               BOOLEAN NOT NULL DEFAULT TRUE,
    note                  TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type, metric),
    CONSTRAINT ck_sec_coverage_type CHECK (
        coverage_type IN ('full','snapshot','aggregated','unavailable'))
);

-- ============================================================
-- LEVEL A — exchange-level features. One row per exchange per bucket. These are
-- INDEPENDENT observations; nothing here is cross-exchange. Every quantity
-- column carries an explicit unit in its name so a base-denominated and a
-- contract-denominated value can never be silently added together.
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_feature_vectors (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    timeframe             TEXT NOT NULL,       -- 1m|5m|15m|1h|4h
    bucket_ts             TIMESTAMPTZ NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version   TEXT NOT NULL,       -- see spec §10; part of logical identity

    -- price / structure (unit-safe: percentages)
    price_move_pct        DOUBLE PRECISION,
    range_width_pct       DOUBLE PRECISION,
    close_price           DOUBLE PRECISION,    -- for notional conversion + audit

    -- volume / flow. volume_raw is exchange-denominated (base for binance/bybit,
    -- CONTRACTS for OKX) and is NEVER comparable across exchanges — the unit is
    -- stored alongside it. *_notional_usd is the normalized, comparable form.
    volume_raw            DOUBLE PRECISION,
    volume_raw_unit       TEXT,                -- 'base' | 'contracts'
    volume_notional_usd   DOUBLE PRECISION,
    taker_buy_notional_usd  DOUBLE PRECISION,
    taker_sell_notional_usd DOUBLE PRECISION,
    taker_delta_notional_usd DOUBLE PRECISION,
    -- windowed CVD delta (NOT an open-ended accumulator — spec §7)
    cvd_delta_notional_usd  DOUBLE PRECISION,

    -- derivatives
    oi_change_pct         DOUBLE PRECISION,    -- % change within bucket, per exchange only
    oi_unit               TEXT,                -- carried through from open_interest
    funding_rate          DOUBLE PRECISION,

    -- liquidations, split by direction, with provenance
    long_liquidation_notional  DOUBLE PRECISION,
    short_liquidation_notional DOUBLE PRECISION,
    liquidation_event_count    INTEGER,
    liquidation_feed_quality   TEXT,           -- full|snapshot|aggregated|unavailable
    is_snapshot_feed           BOOLEAN,

    -- per-exchange data quality for this bucket
    bars_expected         INTEGER,
    bars_present          INTEGER,
    has_gap               BOOLEAN NOT NULL DEFAULT FALSE,
    is_usable             BOOLEAN NOT NULL DEFAULT TRUE,

    -- provenance / reproducibility
    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash           TEXT NOT NULL,
    config_version        TEXT NOT NULL,
    code_version          TEXT NOT NULL,

    PRIMARY KEY (exchange, symbol, market_type, timeframe, bucket_ts, calculation_version)
);
SELECT create_hypertable('exchange_feature_vectors', 'bucket_ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_efv_symbol_tf_ts
    ON exchange_feature_vectors (symbol, timeframe, bucket_ts DESC);

-- ============================================================
-- LEVEL B — consensus features. One row per bucket, NO exchange column.
-- Contains ONLY cross-exchange aggregation results. Aggregation inputs are
-- normalized quantities (notional USD), percentage changes and per-exchange
-- percentile ranks — never raw base/contract values, and never a blind sum of
-- raw OI. Coverage/provenance/confidence are PER metric family (six families).
-- ============================================================
CREATE TABLE IF NOT EXISTS consensus_feature_vectors (
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    timeframe             TEXT NOT NULL,
    bucket_ts             TIMESTAMPTZ NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version   TEXT NOT NULL,       -- see spec §10; part of logical identity

    -- coverage: PER METRIC FAMILY. The six families (revision 0.2.2):
    --   price_structure, volume, taker_flow, oi, funding, liquidations.
    -- BUCKET-LEVEL, not capability-level: "how many venues supplied usable data
    -- FOR THIS BUCKET". A historical bucket has liquidations available=0 even
    -- though all venues have a live feed (liquidations are never backfilled) —
    -- absence is NOT a measured zero.
    coverage_by_metric    JSONB NOT NULL,
    provenance_by_metric  JSONB NOT NULL,
    data_confidence_by_metric JSONB NOT NULL,

    -- Rolled-up convenience values (reporting only — never a per-metric gate).
    exchanges_expected_max INTEGER NOT NULL,
    min_coverage_ratio     DOUBLE PRECISION,   -- worst family, for quick triage
    data_confidence_overall DOUBLE PRECISION,  -- reporting only

    -- direction agreement (sign-based, unit-free — safe across exchanges)
    price_direction_agreement  DOUBLE PRECISION,  -- share agreeing on sign, 0..1
    flow_direction_agreement   DOUBLE PRECISION,
    oi_direction_agreement     DOUBLE PRECISION,

    -- robust aggregates of NORMALIZED values only
    price_move_pct_median      DOUBLE PRECISION,
    range_width_pct_median     DOUBLE PRECISION,
    oi_change_pct_median       DOUBLE PRECISION,
    -- funding consensus (revision 0.2.2): funding_rate is dimensionless and
    -- directly comparable; the consensus percentile is over the median.
    funding_rate_median        DOUBLE PRECISION,
    funding_rate_mad           DOUBLE PRECISION,

    -- additive notional sums (notional USD IS additive across venues; raw
    -- quantities are not — so no raw OI sum lives here).
    volume_notional_usd_sum       DOUBLE PRECISION,
    taker_buy_notional_usd_sum    DOUBLE PRECISION,
    taker_sell_notional_usd_sum   DOUBLE PRECISION,
    taker_delta_notional_usd_sum  DOUBLE PRECISION,
    cvd_delta_notional_usd_sum    DOUBLE PRECISION,
    -- observed_* : a provenance-aware LOWER BOUND on liquidations, not a market
    -- total (feeds under-count). NULLABLE — a historical bucket has no
    -- liquidation data at all, which is unavailable, not a measured zero.
    observed_long_liquidation_notional_sum  DOUBLE PRECISION,
    observed_short_liquidation_notional_sum DOUBLE PRECISION,
    observed_liquidation_event_count_sum    INTEGER,
    liquidation_feed_quality_by_exchange    JSONB,  -- {"binance":"snapshot",...}

    -- dispersion / outliers
    price_move_pct_mad         DOUBLE PRECISION,  -- median absolute deviation
    oi_change_pct_mad          DOUBLE PRECISION,
    outlier_exchanges          JSONB,             -- {"bybit": {"metric":"oi_change_pct","z":4.1}}

    -- confidence
    consensus_confidence       DOUBLE PRECISION,  -- 0..100
    is_partial_consensus       BOOLEAN NOT NULL DEFAULT FALSE,

    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash           TEXT NOT NULL,
    config_version        TEXT NOT NULL,
    code_version          TEXT NOT NULL,

    PRIMARY KEY (symbol, market_type, timeframe, bucket_ts, calculation_version)
);
SELECT create_hypertable('consensus_feature_vectors', 'bucket_ts', if_not_exists => TRUE);

-- ============================================================
-- Percentile snapshots — two-scoped. `scope` says whether the distribution is
-- one exchange's own history or the consensus series' history. Per-exchange
-- distributions are NEVER pooled. Look-ahead is DB-enforced.
-- ============================================================
CREATE TABLE IF NOT EXISTS percentile_snapshots (
    scope           TEXT NOT NULL,             -- 'exchange' | 'consensus'
    exchange        TEXT NOT NULL DEFAULT '',  -- '' when scope='consensus' (keeps PK non-null)
    symbol          TEXT NOT NULL,
    market_type     TEXT NOT NULL DEFAULT 'perp',
    metric          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    window          TEXT NOT NULL,             -- '7d' | '30d'
    bucket_ts       TIMESTAMPTZ NOT NULL,
    value           DOUBLE PRECISION,
    percentile_rank DOUBLE PRECISION,
    sample_size     INTEGER NOT NULL,
    sample_window_start TIMESTAMPTZ,
    sample_window_end   TIMESTAMPTZ,           -- MUST be < bucket_ts
    confidence_tier TEXT NOT NULL,             -- none|low|building|mature
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash     TEXT NOT NULL,
    config_version  TEXT NOT NULL,
    code_version    TEXT NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version TEXT NOT NULL,          -- see spec §10; part of logical identity
    PRIMARY KEY (scope, exchange, symbol, market_type, metric, timeframe, window, bucket_ts, calculation_version),
    CONSTRAINT ck_ps_scope CHECK (scope IN ('exchange','consensus')),
    -- consensus rows carry exchange='' ; exchange rows carry a real exchange.
    CONSTRAINT ck_ps_scope_exchange CHECK (
        (scope = 'consensus' AND exchange = '')
        OR
        (scope = 'exchange' AND exchange <> '')),
    -- Look-ahead guard enforced by the DB, not just by code review.
    CONSTRAINT ck_ps_no_lookahead CHECK (
        sample_window_end IS NULL OR sample_window_end < bucket_ts)
);
SELECT create_hypertable('percentile_snapshots', 'bucket_ts', if_not_exists => TRUE);

-- ============================================================
-- Data health / gap detection. Identity is DETERMINISTIC: snapshot_ts is
-- aligned to the health-check cadence, so a replay produces the same logical
-- rows. computed_at is wall-clock metadata and NOT part of the key. Health
-- classification is config-dependent, so calculation_version is in the PK.
-- ============================================================
CREATE TABLE IF NOT EXISTS data_health_snapshots (
    symbol             TEXT NOT NULL,
    exchange           TEXT NOT NULL,
    market_type        TEXT NOT NULL DEFAULT 'perp',
    metric             TEXT NOT NULL,
    snapshot_ts        TIMESTAMPTZ NOT NULL,   -- bucket-aligned, deterministic
    last_event_at      TIMESTAMPTZ,
    expected_interval_s INTEGER,
    lateness_ms         BIGINT,
    gap_count            INTEGER NOT NULL DEFAULT 0,
    largest_gap_s         INTEGER,
    backfill_status       TEXT,
    coverage_window_start  TIMESTAMPTZ,
    coverage_window_end     TIMESTAMPTZ,
    is_stale                 BOOLEAN NOT NULL DEFAULT FALSE,
    is_usable                 BOOLEAN NOT NULL DEFAULT TRUE,
    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash              TEXT NOT NULL,
    config_version           TEXT NOT NULL,
    code_version             TEXT NOT NULL,
    feature_schema_version   INTEGER NOT NULL,
    calculation_version      TEXT NOT NULL,
    PRIMARY KEY (symbol, exchange, market_type, metric, snapshot_ts, calculation_version)
);
SELECT create_hypertable('data_health_snapshots', 'snapshot_ts', if_not_exists => TRUE);

-- ============================================================
-- Computation watermark — drives restart catch-up and late-data correction
-- (spec §8). One row per computation stream, per calculation_version.
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_watermarks (
    stream            TEXT NOT NULL,      -- 'exchange_features'|'consensus_features'|'percentiles'|'health'
    symbol            TEXT NOT NULL,
    market_type       TEXT NOT NULL DEFAULT 'perp',
    timeframe         TEXT NOT NULL,
    calculation_version TEXT NOT NULL,    -- a new config starts its own progress line
    last_computed_bucket_ts TIMESTAMPTZ,
    last_run_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (stream, symbol, market_type, timeframe, calculation_version)
);

-- ============================================================
-- Recompute queue — populated when a late/corrected raw bar invalidates
-- already-computed results. RANGED jobs (revision 0.2.1), one row per
-- calculation_version. metric/scope/window are NULLABLE and mean "all".
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_recompute_queue (
    id                  BIGSERIAL PRIMARY KEY,
    job_type            TEXT NOT NULL,        -- BUCKET_RECOMPUTE | PERCENTILE_INVALIDATION
    symbol              TEXT NOT NULL,
    market_type         TEXT NOT NULL DEFAULT 'perp',
    timeframe           TEXT NOT NULL,
    calculation_version TEXT NOT NULL,        -- a job targets exactly ONE calculation_version
    range_start_ts      TIMESTAMPTZ NOT NULL,
    range_end_ts        TIMESTAMPTZ NOT NULL,
    metric              TEXT,                 -- NULL = all metrics
    scope               TEXT,                 -- NULL = both ('exchange','consensus')
    window              TEXT,                 -- NULL = all windows ('7d','30d')
    reason              TEXT NOT NULL,        -- LATE_BAR | BACKFILL_CORRECTION | QUEUE_OVERFLOW | MANUAL
    enqueued_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at        TIMESTAMPTZ,
    CONSTRAINT ck_rq_job_type CHECK (
        job_type IN ('BUCKET_RECOMPUTE','PERCENTILE_INVALIDATION')),
    CONSTRAINT ck_rq_range CHECK (range_end_ts >= range_start_ts),
    CONSTRAINT ck_rq_scope CHECK (scope IS NULL OR scope IN ('exchange','consensus'))
);

-- Dedup: PARTIAL unique index over PENDING rows only, NULLs treated as equal.
-- A plain table-level UNIQUE is wrong — it makes NULL "all" dimensions distinct
-- (broad jobs would not dedup) and would permanently block re-enqueue after a
-- job is processed. pg15+ (this deployment runs pg16).
CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job
    ON stage2_recompute_queue (
        job_type, symbol, market_type, timeframe, calculation_version,
        range_start_ts, range_end_ts, metric, scope, window, reason)
    NULLS NOT DISTINCT
    WHERE processed_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_rq_pending
    ON stage2_recompute_queue (enqueued_at) WHERE processed_at IS NULL;
