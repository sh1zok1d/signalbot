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
--
-- It ALSO carries the additive shadow-forecast tables (appended at the end):
--   * `forecast_predictions` — an insert-once EVENT (INSERT ... ON CONFLICT DO
--     NOTHING): historical truth, what the bot decided; late data must NOT rewrite it.
--   * `forecast_outcomes` — a correction-friendly DERIVED evaluation row (upsert):
--     a measurement of future raw bars for a horizon, which MAY legitimately be
--     recomputed/corrected when future raw bars are corrected or filled;
--     outcome_version separates changes in evaluator semantics.

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
    -- NOTE: named percentile_window (not `window`) — `window` is a reserved
    -- keyword in PostgreSQL (window functions) and cannot be a bare column.
    percentile_window TEXT NOT NULL,           -- '7d' | '30d'
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
    PRIMARY KEY (scope, exchange, symbol, market_type, metric, timeframe, percentile_window, bucket_ts, calculation_version),
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
-- calculation_version. metric/scope/percentile_window are NULLABLE, mean "all".
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
    -- percentile_window (not `window` — reserved keyword in PostgreSQL).
    percentile_window   TEXT,                 -- NULL = all windows ('7d','30d')
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
        range_start_ts, range_end_ts, metric, scope, percentile_window, reason)
    NULLS NOT DISTINCT
    WHERE processed_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_rq_pending
    ON stage2_recompute_queue (enqueued_at) WHERE processed_at IS NULL;

-- ============================================================
-- Shadow forecast predictions — ADDITIVE, INSERT-ONCE EVENTS. A prediction is
-- what the bot actually decided for one bucket under one calculation_version and
-- one rule_version. Unlike the derived feature/consensus/health tables above
-- (correction-friendly upserts), a stored prediction is historical truth: it is
-- written with INSERT ... ON CONFLICT DO NOTHING and NEVER updated. A late-data
-- recomputation under the same (calculation_version, rule_version) must not
-- rewrite the original; a deliberately new forecast uses a new rule_version
-- and/or calculation_version. created_at is metadata only (not in the model/key).
-- The consensus_snapshot column stores the complete ConsensusFeatureVector the
-- decision was computed from, so every prediction is reproducible.
-- ============================================================
CREATE TABLE IF NOT EXISTS forecast_predictions (
    symbol                    TEXT NOT NULL,
    market_type               TEXT NOT NULL,
    timeframe                 TEXT NOT NULL,
    bucket_ts                 TIMESTAMPTZ NOT NULL,

    feature_schema_version    INTEGER NOT NULL,
    calculation_version       TEXT NOT NULL,
    rule_version              TEXT NOT NULL,

    direction                 TEXT NOT NULL,
    confidence                DOUBLE PRECISION NOT NULL,
    horizon_set               JSONB NOT NULL,
    reasons                   JSONB NOT NULL,
    component_scores          JSONB NOT NULL,
    final_score               DOUBLE PRECISION NOT NULL,

    reference_price           DOUBLE PRECISION NOT NULL,
    reference_price_source    TEXT NOT NULL,

    exchanges_expected_max    INTEGER NOT NULL,
    min_coverage_ratio        DOUBLE PRECISION,
    data_confidence_overall   DOUBLE PRECISION,
    consensus_confidence      DOUBLE PRECISION,
    is_partial_consensus      BOOLEAN NOT NULL,

    consensus_snapshot        JSONB NOT NULL,

    config_hash               TEXT NOT NULL,
    config_version            TEXT NOT NULL,
    code_version              TEXT NOT NULL,

    created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only

    -- DB-owned V1/V2 history discriminator (ADDITIVE, Multi-model Framework
    -- foundation PR). Every row inserted by the current V1 writer
    -- (analytics/forecasting/persistence.py) omits this column, so Postgres
    -- supplies 'v1' via the DEFAULT below — existing and future V1 rows
    -- become physically identifiable without any INSERT-statement change.
    -- This table remains V1-shaped in this PR: model_family is PINNED to
    -- 'v1', not merely non-blank — it does not accept V2 episode rows
    -- (docs/FORECASTING_ROADMAP.md §A, §J). A future Multi-model Framework
    -- PR that actually stores V2 episode rows here (if that ever becomes the
    -- chosen design) must relax this CHECK explicitly, not silently.
    model_family              TEXT NOT NULL DEFAULT 'v1',

    PRIMARY KEY (
        symbol,
        market_type,
        timeframe,
        bucket_ts,
        calculation_version,
        rule_version
    ),

    CONSTRAINT ck_fp_model_family
        CHECK (model_family = 'v1'),

    CONSTRAINT ck_fp_direction
        CHECK (direction IN ('LONG','SHORT','NEUTRAL')),

    CONSTRAINT ck_fp_confidence
        CHECK (confidence >= 0.0 AND confidence <= 1.0),

    CONSTRAINT ck_fp_final_score
        CHECK (final_score >= -1.0 AND final_score <= 1.0),

    CONSTRAINT ck_fp_reference_price
        CHECK (reference_price > 0.0),

    CONSTRAINT ck_fp_reference_price_source
        CHECK (length(btrim(reference_price_source)) > 0),

    CONSTRAINT ck_fp_exchanges_expected
        CHECK (exchanges_expected_max >= 1),

    CONSTRAINT ck_fp_coverage
        CHECK (
            min_coverage_ratio IS NULL
            OR (min_coverage_ratio >= 0.0 AND min_coverage_ratio <= 1.0)
        ),

    CONSTRAINT ck_fp_data_confidence
        CHECK (
            data_confidence_overall IS NULL
            OR (
                data_confidence_overall >= 0.0
                AND data_confidence_overall <= 100.0
            )
        ),

    CONSTRAINT ck_fp_consensus_confidence
        CHECK (
            consensus_confidence IS NULL
            OR (
                consensus_confidence >= 0.0
                AND consensus_confidence <= 100.0
            )
        ),

    CONSTRAINT ck_fp_horizons_json
        CHECK (jsonb_typeof(horizon_set) = 'array'),

    CONSTRAINT ck_fp_reasons_json
        CHECK (jsonb_typeof(reasons) = 'array'),

    CONSTRAINT ck_fp_components_json
        CHECK (jsonb_typeof(component_scores) = 'object'),

    CONSTRAINT ck_fp_consensus_snapshot_json
        CHECK (jsonb_typeof(consensus_snapshot) = 'object')
);

-- Idempotent upgrade path for a database created before model_family
-- existed: a no-op here on a fresh DB (the CREATE TABLE above already
-- includes the column), and additive-only on an existing installation — no
-- data rewritten, no historical row's meaning changed, existing PK/rule_version
-- untouched. Ordinary ALTER TABLE ADD COLUMN on a TimescaleDB hypertable is
-- supported the same as on a plain table (this hypertable carries no
-- compression policy, so no additional caveats apply). Carries the SAME
-- DEFAULT + CHECK as the CREATE TABLE definition above (ck_fp_model_family,
-- model_family = 'v1') so a fresh DB and an upgraded DB end up with
-- IDENTICAL integrity constraints, not merely the same column.
ALTER TABLE forecast_predictions
    ADD COLUMN IF NOT EXISTS model_family TEXT NOT NULL DEFAULT 'v1'
        CONSTRAINT ck_fp_model_family CHECK (model_family = 'v1');

SELECT create_hypertable(
    'forecast_predictions',
    'bucket_ts',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS ix_fp_symbol_tf_ts
    ON forecast_predictions (symbol, timeframe, bucket_ts DESC);

CREATE INDEX IF NOT EXISTS ix_fp_direction_ts
    ON forecast_predictions (direction, bucket_ts DESC);

-- Actionable (LONG/SHORT) predictions ordered by insertion time — supports the
-- Telegram notifier's created_at-based discovery scan (late inserts for older
-- bucket_ts make bucket_ts alone unsuitable as the discovery cursor).
CREATE INDEX IF NOT EXISTS ix_fp_actionable_created_at
    ON forecast_predictions (created_at ASC)
    WHERE direction IN ('LONG','SHORT');

-- ============================================================
-- Shadow forecast OUTCOMES — ADDITIVE, correction-friendly DERIVED rows. One row
-- per (prediction identity, horizon, evaluation_exchange, evaluation source,
-- outcome_version): a deterministic measurement of the future 1m price window
-- (target close at end-1m; window high/low; raw + direction-aware return/MFE/MAE).
-- Unlike forecast_predictions (immutable insert-once), an outcome is a derived
-- measurement of future raw bars, so it is a CORRECTION-FRIENDLY upsert
-- (ON CONFLICT DO UPDATE, computed_at=now()) — a corrected/filled future bar may
-- legitimately correct the outcome; a new outcome_version is a distinct result.
-- computed_at is metadata only. Only COMPLETE evaluations are persisted.
-- ============================================================
CREATE TABLE IF NOT EXISTS forecast_outcomes (
    symbol                    TEXT NOT NULL,
    market_type               TEXT NOT NULL,
    timeframe                 TEXT NOT NULL,
    bucket_ts                 TIMESTAMPTZ NOT NULL,

    feature_schema_version    INTEGER NOT NULL,
    calculation_version       TEXT NOT NULL,
    rule_version              TEXT NOT NULL,

    horizon                   TEXT NOT NULL,
    outcome_version           TEXT NOT NULL,

    direction                 TEXT NOT NULL,
    prediction_confidence     DOUBLE PRECISION NOT NULL,
    prediction_final_score    DOUBLE PRECISION NOT NULL,

    reference_price           DOUBLE PRECISION NOT NULL,
    reference_price_source    TEXT NOT NULL,

    evaluation_exchange       TEXT NOT NULL,
    evaluation_price_source   TEXT NOT NULL,

    evaluation_start_ts       TIMESTAMPTZ NOT NULL,
    evaluation_end_ts         TIMESTAMPTZ NOT NULL,
    target_bar_ts             TIMESTAMPTZ NOT NULL,

    bars_expected             INTEGER NOT NULL,
    bars_present              INTEGER NOT NULL,

    target_close_price        DOUBLE PRECISION NOT NULL,
    window_high_price         DOUBLE PRECISION NOT NULL,
    window_low_price          DOUBLE PRECISION NOT NULL,

    market_return_pct         DOUBLE PRECISION NOT NULL,
    peak_return_pct           DOUBLE PRECISION NOT NULL,
    trough_return_pct         DOUBLE PRECISION NOT NULL,

    directional_return_pct    DOUBLE PRECISION,
    mfe_pct                   DOUBLE PRECISION,
    mae_pct                   DOUBLE PRECISION,

    config_hash               TEXT NOT NULL,
    config_version            TEXT NOT NULL,
    code_version              TEXT NOT NULL,

    computed_at               TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only

    -- DB-owned V1/V2 history discriminator (ADDITIVE, Multi-model Framework
    -- foundation PR) — same pattern/rationale as the shadow forecast events
    -- table above: every row from the current V1 outcome writer omits this
    -- column, so Postgres supplies 'v1' via the DEFAULT below. This table
    -- remains V1-shaped in this PR: model_family is PINNED to 'v1', not
    -- merely non-blank — it does not accept V2 episode-outcome rows.
    model_family              TEXT NOT NULL DEFAULT 'v1',

    PRIMARY KEY (
        symbol,
        market_type,
        timeframe,
        bucket_ts,
        calculation_version,
        rule_version,
        horizon,
        evaluation_exchange,
        evaluation_price_source,
        outcome_version
    ),

    CONSTRAINT ck_fo_model_family
        CHECK (model_family = 'v1'),

    CONSTRAINT ck_fo_horizon
        CHECK (horizon IN ('15m','1h','4h')),

    CONSTRAINT ck_fo_direction
        CHECK (direction IN ('LONG','SHORT','NEUTRAL')),

    CONSTRAINT ck_fo_prediction_confidence
        CHECK (
            prediction_confidence >= 0.0
            AND prediction_confidence <= 1.0
        ),

    CONSTRAINT ck_fo_prediction_final_score
        CHECK (
            prediction_final_score >= -1.0
            AND prediction_final_score <= 1.0
        ),

    CONSTRAINT ck_fo_reference_price
        CHECK (reference_price > 0.0),

    CONSTRAINT ck_fo_reference_source
        CHECK (length(btrim(reference_price_source)) > 0),

    -- V0 same-exchange source rule (also enforced in the pure evaluator): the
    -- prediction's reference price must be the evaluation exchange's 5m close.
    CONSTRAINT ck_fo_reference_alignment
        CHECK (
            reference_price_source =
                evaluation_exchange || '_close_5m'
        ),

    CONSTRAINT ck_fo_evaluation_exchange
        CHECK (length(btrim(evaluation_exchange)) > 0),

    CONSTRAINT ck_fo_evaluation_source
        CHECK (evaluation_price_source = 'klines_1m'),

    -- bind the evaluation window to the prediction bucket: start is bucket + 5m
    -- (the closed 5m bucket OPEN that produced the prediction).
    CONSTRAINT ck_fo_evaluation_start
        CHECK (
            evaluation_start_ts =
                bucket_ts + INTERVAL '5 minutes'
        ),

    CONSTRAINT ck_fo_window_order
        CHECK (evaluation_end_ts > evaluation_start_ts),

    CONSTRAINT ck_fo_target_bar
        CHECK (
            target_bar_ts = evaluation_end_ts - INTERVAL '1 minute'
        ),

    CONSTRAINT ck_fo_bars
        CHECK (
            bars_expected > 0
            AND bars_present = bars_expected
        ),

    CONSTRAINT ck_fo_horizon_window
        CHECK (
            (
                horizon = '15m'
                AND bars_expected = 15
                AND evaluation_end_ts =
                    evaluation_start_ts + INTERVAL '15 minutes'
            )
            OR
            (
                horizon = '1h'
                AND bars_expected = 60
                AND evaluation_end_ts =
                    evaluation_start_ts + INTERVAL '1 hour'
            )
            OR
            (
                horizon = '4h'
                AND bars_expected = 240
                AND evaluation_end_ts =
                    evaluation_start_ts + INTERVAL '4 hours'
            )
        ),

    CONSTRAINT ck_fo_prices
        CHECK (
            target_close_price > 0.0
            AND window_high_price > 0.0
            AND window_low_price > 0.0
            AND window_low_price <= target_close_price
            AND target_close_price <= window_high_price
        ),

    CONSTRAINT ck_fo_return_order
        CHECK (peak_return_pct >= trough_return_pct),

    CONSTRAINT ck_fo_directional_metrics
        CHECK (
            (
                direction = 'NEUTRAL'
                AND directional_return_pct IS NULL
                AND mfe_pct IS NULL
                AND mae_pct IS NULL
            )
            OR
            (
                direction IN ('LONG','SHORT')
                AND directional_return_pct IS NOT NULL
                AND mfe_pct IS NOT NULL
                AND mae_pct IS NOT NULL
                AND mfe_pct >= 0.0
                AND mae_pct <= 0.0
            )
        )
);

-- Idempotent upgrade path for a database created before model_family
-- existed — same rationale as the shadow forecast events table's identical
-- statement above: a no-op on a fresh DB, additive-only on an existing
-- installation. Carries the SAME DEFAULT + CHECK as the CREATE TABLE
-- definition above (ck_fo_model_family, model_family = 'v1') so a fresh DB
-- and an upgraded DB end up with IDENTICAL integrity constraints.
ALTER TABLE forecast_outcomes
    ADD COLUMN IF NOT EXISTS model_family TEXT NOT NULL DEFAULT 'v1'
        CONSTRAINT ck_fo_model_family CHECK (model_family = 'v1');

SELECT create_hypertable(
    'forecast_outcomes',
    'bucket_ts',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS ix_fo_symbol_horizon_ts
    ON forecast_outcomes (
        symbol,
        horizon,
        bucket_ts DESC
    );

CREATE INDEX IF NOT EXISTS ix_fo_direction_horizon_ts
    ON forecast_outcomes (
        direction,
        horizon,
        bucket_ts DESC
    );

-- ============================================================
-- Shadow recovery watermark — ADDITIVE. A tiny durable key/value marking the
-- newest closed 5m bucket the AUTOMATIC shadow runner has fully attempted, per
-- (runner_name, symbol, market_type, timeframe). It is advanced only after a
-- bucket's process_shadow_cycle returns successfully, and only ever moves
-- forward (monotonic). Not a hypertable (one row per runner/scope). It is NOT
-- consulted for explicit manual --shadow-bucket-ts execution.
-- ============================================================
CREATE TABLE IF NOT EXISTS shadow_recovery_watermarks (
    runner_name               TEXT NOT NULL,
    symbol                    TEXT NOT NULL,
    market_type               TEXT NOT NULL DEFAULT 'perp',
    timeframe                 TEXT NOT NULL,
    last_completed_bucket_ts  TIMESTAMPTZ NOT NULL,
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (runner_name, symbol, market_type, timeframe),
    CONSTRAINT ck_srw_runner       CHECK (length(btrim(runner_name)) > 0),
    CONSTRAINT ck_srw_bucket_5m
        CHECK (date_part('epoch', last_completed_bucket_ts)::bigint % 300 = 0)
);

-- ============================================================
-- Telegram forecast notifier — ADDITIVE. Isolated durable outbox for the
-- separate Telegram notification worker (runtime/telegram_cli.py). NEVER
-- referenced by process_shadow_cycle or runtime/shadow_recovery.py — the
-- shadow prediction/outcome timer is fully independent of Telegram delivery.
--
-- telegram_notifier_state: ONE row per (runner_name, channel,
-- recipient_fingerprint), recording when this notifier scope first started
-- watching for actionable predictions (started_at). This prevents
-- historical-message spam on first deployment: only a prediction with
-- created_at >= started_at is ever enqueued. recipient_fingerprint is a
-- deterministic sha256 hex digest of the chat id — the raw chat id is NEVER
-- stored.
--
-- telegram_notification_deliveries: ONE row per (channel,
-- recipient_fingerprint, prediction identity) — a durable delivery outbox.
-- Rows are updated in place for attempt bookkeeping (correction-friendly),
-- but the underlying forecast_predictions / forecast_outcomes rows are NEVER
-- written here, and no raw bot token or chat id is ever stored. Delivery rows
-- remain after success as audit history.
-- ============================================================
CREATE TABLE IF NOT EXISTS telegram_notifier_state (
    runner_name             TEXT NOT NULL,
    channel                 TEXT NOT NULL,
    recipient_fingerprint   TEXT NOT NULL,
    started_at              TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (runner_name, channel, recipient_fingerprint),
    CONSTRAINT ck_tns_runner      CHECK (length(btrim(runner_name)) > 0),
    CONSTRAINT ck_tns_channel     CHECK (length(btrim(channel)) > 0),
    CONSTRAINT ck_tns_fingerprint CHECK (recipient_fingerprint ~ '^[0-9a-f]{64}$')
);

CREATE TABLE IF NOT EXISTS telegram_notification_deliveries (
    channel                 TEXT NOT NULL,
    recipient_fingerprint   TEXT NOT NULL,

    symbol                  TEXT NOT NULL,
    market_type             TEXT NOT NULL,
    timeframe               TEXT NOT NULL,
    bucket_ts               TIMESTAMPTZ NOT NULL,
    calculation_version     TEXT NOT NULL,
    rule_version             TEXT NOT NULL,

    attempt_count           INTEGER NOT NULL DEFAULT 0,
    next_attempt_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_attempt_at         TIMESTAMPTZ,
    sent_at                 TIMESTAMPTZ,
    telegram_message_id     BIGINT,
    last_error_class        TEXT,
    last_error_summary      TEXT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (
        channel,
        recipient_fingerprint,
        symbol,
        market_type,
        timeframe,
        bucket_ts,
        calculation_version,
        rule_version
    ),

    CONSTRAINT ck_tnd_channel     CHECK (length(btrim(channel)) > 0),
    CONSTRAINT ck_tnd_fingerprint CHECK (recipient_fingerprint ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_tnd_attempt_count CHECK (attempt_count >= 0),
    CONSTRAINT ck_tnd_sent_pair CHECK (
        (sent_at IS NULL AND telegram_message_id IS NULL)
        OR (sent_at IS NOT NULL AND telegram_message_id IS NOT NULL)
    )
);

-- Supports the pending-delivery scan: unsent rows ordered by next_attempt_at.
CREATE INDEX IF NOT EXISTS ix_tnd_pending_next_attempt
    ON telegram_notification_deliveries (next_attempt_at ASC)
    WHERE sent_at IS NULL;

-- ============================================================
-- V2 episode events — ADDITIVE (Multi-model Framework PR 2,
-- docs/FORECASTING_ROADMAP.md §I stage 2). Immutable, INSERT-ONCE historical
-- truth for one already-decided V2 episode event. This table is the
-- PERSISTENCE BOUNDARY docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1
-- requires: `decision_snapshot` (what the event decided FROM) and
-- `event_payload` (what the event decided/emitted) are stored BY VALUE
-- (JSONB), never by a row reference alone, so a later correction to
-- exchange_feature_vectors / consensus_feature_vectors / percentile_snapshots
-- can never rewrite what a past event already recorded.
--
-- This table does NOT implement the Episode State Machine — a future PR
-- constructs V2EpisodeEvent rows (analytics/forecasting_v2/events.py) and
-- calls Database.insert_v2_episode_events(); nothing in this schema or its
-- writer decides when an event should exist, what state it transitions to,
-- or how structural_anchor is computed. No FK to feature tables — by-value
-- historical truth is the authority, never a reference that could later
-- change meaning underneath an already-published event.
--
-- run_kind/run_id/event_id namespace LIVE vs. REPLAY execution (§2.1: "a
-- separate, explicitly provenanced recomputation... MUST carry its own
-- distinct provenance... from the live decision it is re-evaluating") — a
-- REPLAY run can legitimately reproduce an event_id a LIVE run already used
-- without colliding, because the primary key includes run_kind/run_id.
--
-- episode_state holds the six ACTUAL lifecycle states (§13.2).
-- REVERSAL_CANDIDATE is deliberately NOT a legal value here — per §13.3 it
-- is a cross-cutting event attached to an existing episode's history while
-- that episode's own state is unchanged, not a state itself
-- (V2_PRODUCT_CONTRACT.md §5.1).
--
-- Plain PostgreSQL table, NOT a TimescaleDB hypertable: this is low-volume
-- immutable episode-event history relative to raw per-bucket features (one
-- row per persisted lifecycle event, not one per closed 5m/15m/1h/4h
-- bucket) — the same reasoning shadow_recovery_watermarks /
-- telegram_notification_deliveries above already use for their own
-- low-volume additive tables. This deliberately does NOT claim every row
-- is notification-worthy: a historical episode update may be persisted
-- here without producing a material Telegram notification (notification
-- materiality is Stage 9 / state-machine semantics, out of scope here).
-- ============================================================
-- V2-H3 (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a): event_id/
-- episode_id are now ALWAYS the deterministic 64-char lowercase hex
-- SHA-256 digest analytics/forecasting_v2/episode_identity.py's
-- compute_episode_id()/compute_event_id() produce for every real write
-- path -- ck_v2ee_event_id_hash_format/ck_v2ee_episode_id_hash_format
-- below enforce that SHAPE at the DB layer too (defense-in-depth; this
-- cannot itself prove an ID was computed correctly from the right inputs,
-- only that its shape is not a random UUID/caller-invented opaque string/
-- truncated hash). The original ck_v2ee_event_id/ck_v2ee_episode_id
-- nonblank checks (below) are kept UNCHANGED, never removed -- this is a
-- strictly ADDITIONAL, stricter constraint, not a replacement.
CREATE TABLE IF NOT EXISTS v2_episode_events (
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
    -- V2-H3 (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.2): the Stage
    -- 4/5/6 DECISION-code identity, captured BY VALUE alongside code_version
    -- (Stage 2's FEATURE-computation-code identity) -- the two are
    -- deliberately separate columns, never conflated.
    decision_code_version  TEXT NOT NULL,

    decision_snapshot      JSONB NOT NULL,
    event_payload          JSONB NOT NULL,

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only

    PRIMARY KEY (run_kind, run_id, event_id),

    CONSTRAINT ck_v2ee_run_kind
        CHECK (run_kind IN ('LIVE','REPLAY')),
    CONSTRAINT ck_v2ee_run_id       CHECK (length(btrim(run_id)) > 0),
    CONSTRAINT ck_v2ee_event_id     CHECK (length(btrim(event_id)) > 0),
    CONSTRAINT ck_v2ee_episode_id   CHECK (length(btrim(episode_id)) > 0),
    -- V2-H3: deterministic-identity shape, additional to the plain
    -- nonblank checks immediately above (never a replacement for them).
    CONSTRAINT ck_v2ee_event_id_hash_format
        CHECK (event_id ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_v2ee_episode_id_hash_format
        CHECK (episode_id ~ '^[0-9a-f]{64}$'),

    CONSTRAINT ck_v2ee_model_family
        CHECK (model_family = 'v2'),
    -- Mirrors common/v2_config.py's RULES_VERSION_RE exactly (no leading
    -- zeros in any component except a lone '0') so the DB-side and
    -- Python-side rules never silently diverge.
    CONSTRAINT ck_v2ee_rules_version
        CHECK (rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'),

    CONSTRAINT ck_v2ee_symbol       CHECK (symbol = 'BTCUSDT'),
    CONSTRAINT ck_v2ee_market_type  CHECK (market_type = 'perp'),
    CONSTRAINT ck_v2ee_direction
        CHECK (direction IN ('LONG','SHORT')),
    CONSTRAINT ck_v2ee_setup_family
        CHECK (setup_family IN ('TREND_PULLBACK','COMPRESSION_BREAKOUT','CONFIRMED_BREAKOUT')),
    CONSTRAINT ck_v2ee_structural_anchor_json
        CHECK (jsonb_typeof(structural_anchor) = 'object'),

    -- REVERSAL_CANDIDATE intentionally excluded — see banner comment above.
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

-- Reconstruct one episode's full event history in order (one run's view).
CREATE INDEX IF NOT EXISTS ix_v2ee_episode_history
    ON v2_episode_events (run_kind, run_id, episode_id, decision_boundary ASC);

-- Recent V2 event inspection across episodes, for one symbol.
CREATE INDEX IF NOT EXISTS ix_v2ee_symbol_recent
    ON v2_episode_events (symbol, decision_boundary DESC);

-- V2-H3 (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §2.1a): the frozen
-- physical uniqueness invariant for one logical decision boundary's event
-- publication -- "at most one persisted V2EpisodeEvent per (execution_
-- stream, episode_id, decision_boundary)". ADDITIONAL to (and, once every
-- caller constructs event_id via analytics/forecasting_v2/
-- episode_identity.py::compute_event_id() -- itself a deterministic
-- function of exactly (episode_id, decision_boundary) -- implied by) the
-- existing PRIMARY KEY (run_kind, run_id, event_id) above: kept as its own
-- explicit unique index rather than replacing the PK, since event_id
-- remains this table's own physical row-lookup identity and dropping it
-- would be an unrelated, unnecessary destructive change. A UNIQUE INDEX
-- (rather than a table-level UNIQUE constraint) is used specifically so
-- this same statement is idempotent (`IF NOT EXISTS`) for BOTH a fresh
-- database and an upgrade of an already-deployed one -- PostgreSQL has no
-- `ADD CONSTRAINT IF NOT EXISTS` form for a table-level UNIQUE constraint.
CREATE UNIQUE INDEX IF NOT EXISTS ux_v2ee_episode_decision_boundary
    ON v2_episode_events (run_kind, run_id, episode_id, decision_boundary);

-- Idempotent upgrade path for a database created before decision_code_version
-- existed: a no-op on a fresh DB (the CREATE TABLE above already includes
-- the column/constraint), additive-only on an existing installation. The
-- CHECK is bundled into the SAME `ADD COLUMN IF NOT EXISTS` statement (the
-- `model_family` upgrade path elsewhere in this file uses the identical
-- pattern) rather than a separate `ADD CONSTRAINT`, specifically because
-- `storage/db.py::_split_sql_statements` splits this file on a plain `;`
-- with no dollar-quoted/PL-pgSQL awareness ("this schema is plain DDL...
-- switch to a real parser" if that ever changes) -- a guarded
-- `DO $$ ... $$` block guarding a separate idempotent `ADD CONSTRAINT`
-- would be silently mis-split into multiple invalid fragments by that
-- splitter, which is exactly why one is deliberately NOT used here (or for
-- the two new event_id/episode_id hash-format CHECKs below). No DEFAULT is
-- supplied -- this table has never had a real writer wired into any
-- runtime path (v2.enabled has always been false;
-- Database.insert_v2_episode_events is not called from connect()/
-- init_schema()/init_stage2_schema() and is exercised only by this
-- repository's own tests), so it has zero rows in every real deployment
-- today; fabricating a placeholder historical value for a column that in
-- practice has no existing rows to backfill would be worse than the
-- straightforward, honest failure mode below. If this assumption is ever
-- wrong for some deployment, PostgreSQL itself will refuse the ALTER
-- (`column "decision_code_version" contains null values`) rather than
-- silently inventing history -- exactly the fail-closed behavior wanted.
ALTER TABLE v2_episode_events
    ADD COLUMN IF NOT EXISTS decision_code_version TEXT NOT NULL
        CONSTRAINT ck_v2ee_decision_code_version
            CHECK (length(btrim(decision_code_version)) > 0);

-- KNOWN, ACCEPTED, NARROW LIMITATION (documented rather than silently
-- gapped): unlike decision_code_version above, event_id/episode_id are
-- NOT new columns -- there is no idempotent `ADD COLUMN IF NOT EXISTS`
-- trick available to retrofit ck_v2ee_event_id_hash_format/
-- ck_v2ee_episode_id_hash_format (declared inline in the CREATE TABLE
-- above) onto an ALREADY-existing v2_episode_events table from a
-- database that ran schema init before this PR, and PostgreSQL has no
-- `ADD CONSTRAINT IF NOT EXISTS` form for that case (the same
-- dollar-quoted-body limitation noted above rules out a guarded `DO $$`
-- workaround). This is safe in practice today: v2.enabled has always been
-- false and this table has zero rows in every real deployment, so no
-- write today can actually violate the missing constraint on an
-- unupgraded table. A future PR that needs this retrofitted for real
-- (e.g. once `_split_sql_statements` gains PL/pgSQL-aware parsing, or a
-- proper migration-numbering mechanism is adopted) can add it then.

-- ============================================================
-- V2-H2b: DRAIN-BEFORE-ACTIVATE version-switch durable state
-- (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.1). Column-for-column
-- mirror of analytics/forecasting_v2/version_switch.py's
-- V2VersionSwitchState -- every CHECK constraint below re-states, at the
-- DB layer, an invariant that dataclass's own __post_init__ already
-- enforces in Python (belt-and-suspenders: never relying on Python
-- validation alone for an invariant the DB can cheaply own).
--
-- Scope is exactly ONE execution_stream = (run_kind, run_id) -- §12.10,
-- NOT symbol/market_type (see version_switch.py's module docstring for
-- why). PRIMARY KEY (run_kind, run_id) means there is at most one row per
-- scope -- "at most one active identity and at most one pending target
-- per scope" (§9) is enforced BY CONSTRUCTION, not by a second uniqueness
-- constraint across multiple rows.
--
-- active_*/pending_* are grouped triples (rules_version,
-- calculation_version, decision_code_version) -- one V2SemanticTuple
-- each. active_* is NULL only before this execution_stream's first-ever
-- activation (a fresh LIVE/REPLAY stream); pending_* is NULL unless a
-- switch is currently in progress.
--
-- No FK to v2_episode_events -- this table's non_terminal_episode_count/
-- active_cooldown_count "drain fact" is NOT derived by a query against
-- that table here (Stage 6, which would own that real query, does not
-- exist yet -- see ports.py's V2VersionDrainStatusReader docstring); this
-- table only durably persists the SWITCH's own state, resolved by
-- analytics/forecasting_v2/version_switch.py's pure transition function
-- from facts supplied by whatever future Stage-6-backed reader satisfies
-- that Protocol.
-- ============================================================
CREATE TABLE IF NOT EXISTS v2_version_switch_state (
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

    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only

    PRIMARY KEY (run_kind, run_id),

    CONSTRAINT ck_v2vss_run_kind CHECK (run_kind IN ('LIVE','REPLAY')),
    CONSTRAINT ck_v2vss_run_id   CHECK (length(btrim(run_id)) > 0),

    CONSTRAINT ck_v2vss_phase
        CHECK (phase IN ('NO_PENDING_SWITCH','DRAINING','AWAITING_ACTIVATION_READINESS')),

    -- active_* triple: all NULL (never-activated bootstrap) or all NOT NULL.
    CONSTRAINT ck_v2vss_active_all_or_none CHECK (
        (active_rules_version IS NULL AND active_calculation_version IS NULL
             AND active_decision_code_version IS NULL)
        OR
        (active_rules_version IS NOT NULL AND active_calculation_version IS NOT NULL
             AND active_decision_code_version IS NOT NULL)
    ),
    -- pending_* triple: all NULL (no switch in progress) or all NOT NULL.
    CONSTRAINT ck_v2vss_pending_all_or_none CHECK (
        (pending_rules_version IS NULL AND pending_calculation_version IS NULL
             AND pending_decision_code_version IS NULL)
        OR
        (pending_rules_version IS NOT NULL AND pending_calculation_version IS NOT NULL
             AND pending_decision_code_version IS NOT NULL)
    ),

    -- rules_version format mirrors v2_episode_events.ck_v2ee_rules_version
    -- exactly -- the same common/v2_config.py RULES_VERSION_RE pattern.
    CONSTRAINT ck_v2vss_active_rules_version_format CHECK (
        active_rules_version IS NULL OR
        active_rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'),
    CONSTRAINT ck_v2vss_pending_rules_version_format CHECK (
        pending_rules_version IS NULL OR
        pending_rules_version ~ '^v2-rules-v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'),

    -- calculation_version format mirrors v2_episode_events.ck_v2ee_calculation_version.
    CONSTRAINT ck_v2vss_active_calc_version_format
        CHECK (active_calculation_version IS NULL OR active_calculation_version ~ '^[0-9a-f]{16}$'),
    CONSTRAINT ck_v2vss_pending_calc_version_format
        CHECK (pending_calculation_version IS NULL OR pending_calculation_version ~ '^[0-9a-f]{16}$'),

    CONSTRAINT ck_v2vss_active_decision_code_version_nonblank CHECK (
        active_decision_code_version IS NULL OR length(btrim(active_decision_code_version)) > 0),
    CONSTRAINT ck_v2vss_pending_decision_code_version_nonblank CHECK (
        pending_decision_code_version IS NULL OR length(btrim(pending_decision_code_version)) > 0),

    -- Phase <-> pending/drain_complete_at/requested_at shape -- mirrors
    -- V2VersionSwitchState.__post_init__ exactly.
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

    -- pending must never equal active -- that would not be a switch at all.
    CONSTRAINT ck_v2vss_pending_distinct_from_active CHECK (
        pending_rules_version IS NULL OR active_rules_version IS NULL OR
        (pending_rules_version, pending_calculation_version, pending_decision_code_version)
            IS DISTINCT FROM
        (active_rules_version, active_calculation_version, active_decision_code_version)
    ),

    -- Amendment round 2, finding 1a: REPLAY may never be mid-switch --
    -- mirrors version_switch.py's _SWITCH_ELIGIBLE_RUN_KINDS = (LIVE,) check
    -- in V2VersionSwitchState.__post_init__. A steady REPLAY row (its one
    -- pinned active tuple, or none yet before initial provisioning) is
    -- still fully permitted -- this does NOT make the whole table LIVE-only.
    CONSTRAINT ck_v2vss_replay_no_pending_switch CHECK (
        run_kind = 'LIVE' OR phase = 'NO_PENDING_SWITCH'
    ),

    -- Amendment round 2, finding 1b: any pending-switch phase requires an
    -- OLD active tuple -- mirrors V2VersionSwitchState.__post_init__'s
    -- `phase != PHASE_NO_PENDING_SWITCH => active is not None` check. A
    -- pending switch always means OLD exists (active_*) and NEW is
    -- pending_*; initial provisioning (active_* all NULL) can never itself
    -- be mid-switch. Reuses ck_v2vss_active_all_or_none's own triple
    -- structurally (checking one column of the all-or-none triple is
    -- sufficient -- no duplicated format/shape logic).
    CONSTRAINT ck_v2vss_pending_switch_requires_active CHECK (
        phase = 'NO_PENDING_SWITCH' OR active_rules_version IS NOT NULL
    )
);

-- ============================================================
-- V2-H2c: as-of/historical instrument metadata
-- (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §12.5a's "Clean-room audit
-- finding: instrument metadata has no as-of/historical model today").
--
-- `exchange_instruments` (above) remains the CURRENT/last-known-good
-- snapshot -- the operational row LIVE ingestion/`runtime/shadow_cli.py`
-- bootstrap reads and writes, UNCHANGED by this table. A historical V2
-- Stage 5 decision at boundary T must instead resolve the metadata
-- VERSION that was actually in effect at T -- never the current row,
-- never the newest fetch, never a future version.
--
-- Effective-dated history of immutable value versions, with interval
-- closure: ONE row per accepted metadata VERSION for one (exchange,
-- symbol, market_type) identity. A row's own value columns never change
-- once written -- only `effective_until` is later updated, exactly once,
-- to close that version's interval when the NEXT version is accepted (see
-- `storage/db.py::Database.upsert_exchange_instrument`). This is
-- deliberately NOT called "append-only": an UPDATE does happen, but it
-- only ever closes an interval, never rewrites a value.
--
-- Interval convention is frozen as HALF-OPEN [effective_from,
-- effective_until):
--   effective_from <= T  AND  (effective_until IS NULL OR T < effective_until)
-- means "this version applies at T". At a boundary exactly equal to the
-- NEXT version's effective_from, the NEW version applies -- the previous
-- row no longer does (same convention Python encodes,
-- storage/db.py/storage/v2_setup_readers.py, and the same convention
-- every test in tests/storage/test_v2_instrument_history*.py exercises).
--
-- TWO DISTINCT TIMESTAMPS, deliberately never conflated (tech-lead review
-- 4990482334, finding 1) -- `observed_at` is PROVENANCE ONLY: when the
-- external value was fetched/observed. It NEVER by itself determines
-- `effective_from`. `effective_from` is the EXPLICIT V2 decision-time
-- activation boundary the caller supplies -- when this version actually
-- became eligible for V2 decision boundaries to use. For an ordinary
-- fetch with no pre-existing conflicting value, the caller MAY choose
-- `effective_from == observed_at` (there is no earlier LIVE decision to
-- protect). For a DELIBERATELY-ACCEPTED metadata mismatch (the existing
-- `common/instrument_metadata.py`/`Database.upsert_exchange_instrument`
-- `accept_mismatch=True` flow), the two are generally DIFFERENT: the
-- mismatch may be *observed* well before an operator *accepts* it, and
-- every LIVE decision in between correctly used the OLD value --
-- `effective_from` MUST be the later acceptance boundary, never
-- auto-backdated to `observed_at`. `Database.upsert_exchange_instrument`
-- enforces this: it refuses (raises) to guess `effective_from` for a
-- genuine value change against an already-open interval -- the caller
-- must supply it explicitly. `observed_at` MAY be NULL (a `manual`/
-- `declared_fallback` value with no honest fetch timestamp) -- but
-- `effective_from` is still always required before that value can affect
-- any historical/replay V2 decision. Consequently there is NO migration
-- that assigns `effective_from = -infinity` or any arbitrary
-- project-start date for pre-existing `exchange_instruments` rows;
-- history begins only at each version's own explicit, truthful
-- `effective_from`. A historical T earlier than the oldest known
-- `effective_from` for an identity has NO row here -- legitimately
-- NOT_EVALUABLE, never silently satisfied by extrapolating today's value
-- backward. `Database.seed_current_instrument_history` provides the
-- explicit, conservative, idempotent bootstrap path for an
-- already-accepted pre-H2c `exchange_instruments` row that has no history
-- yet -- see that method's own docstring; it NEVER extrapolates
-- backward either, only from its own caller-supplied `effective_from`
-- forward.
--
-- Non-overlap is enforced by TWO cheap mechanisms rather than a
-- btree_gist exclusion constraint (disproportionate complexity for this
-- narrow need): (1) `ux_eih_one_open_interval_per_identity` below
-- guarantees AT MOST ONE currently-open (`effective_until IS NULL`) row
-- per identity at the DB level; (2) the writer
-- (`storage/db.py::Database.upsert_exchange_instrument`) always locks the
-- identity (a transaction-scoped Postgres advisory lock) and closes that
-- one open row in the SAME transaction as opening the next one, so no two
-- accepted writes for the same identity can ever race into overlapping
-- closed intervals either. The as-of reader independently re-checks:
-- more than one row matching a requested `as_of` is corruption/overlap
-- and FAILS CLOSED (`V2SetupReaderError`,
-- `storage/v2_setup_readers.py::read_v2_instrument`), never silently
-- picks one.
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_instrument_history (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    exchange_instrument_id TEXT NOT NULL,
    quantity_unit         TEXT,
    contract_multiplier   DOUBLE PRECISION,
    tick_size             DOUBLE PRECISION,
    price_precision       INTEGER,
    quantity_precision    INTEGER,
    metadata_source       TEXT NOT NULL,          -- 'exchange_api' | 'declared_fallback' | 'manual'
    observed_at           TIMESTAMPTZ,            -- PROVENANCE ONLY: when fetched/observed; NULL for a manual/declared value with no honest fetch timestamp; NEVER itself the activation boundary
    effective_from        TIMESTAMPTZ NOT NULL,   -- the EXPLICIT V2 decision-time activation boundary -- when this version actually became eligible for decisions to use; caller-supplied, never auto-derived from observed_at for a genuine value change
    effective_until       TIMESTAMPTZ,            -- NULL = still the currently-open version
    note                  TEXT,
    -- (tech-lead review 4991738511) PROVENANCE ONLY: the shared, GLOBAL
    -- `stage2_instrument_metadata_state.required_revision` that was
    -- current at the moment this row was written -- inherited unchanged
    -- for a non-critical value change (e.g. price_precision-only), and
    -- set to the NEW, just-bumped revision for a deliberately-accepted
    -- CRITICAL-field change. This column NEVER itself enforces anything
    -- (a decorative label was exactly what tech-lead review 4990482334's
    -- `accepted_code_version` predecessor turned out to be, per review
    -- 4991738511's finding 2 -- see that review for the full audit); the
    -- REAL, executable enforcement is `stage2_instrument_metadata_state`
    -- (below) compared against the resolved Stage2Config's OWN
    -- `defaults.instrument_metadata_revision` in
    -- `analytics/feature_engine/input_adapter.py::
    -- assemble_exchange_feature_request` -- see that function and table
    -- for the mechanism. Never reset to NULL merely because a given row
    -- was not itself a critical acceptance (finding 10).
    accepted_metadata_revision INTEGER,
    recorded_at           TIMESTAMPTZ NOT NULL DEFAULT now(),  -- DB-owned insert bookkeeping only
    PRIMARY KEY (exchange, symbol, market_type, effective_from),
    CONSTRAINT ck_eih_quantity_unit CHECK (
        quantity_unit IS NULL OR quantity_unit IN ('base','contracts')),
    CONSTRAINT ck_eih_metadata_source CHECK (
        metadata_source IN ('exchange_api','declared_fallback','manual')),
    -- (CodeRabbit finding, defense-in-depth) A plain `> 0` CHECK on a
    -- float8 column does NOT reject NaN/+Infinity: PostgreSQL's float8
    -- ordering treats both as "greater than any value", so `'NaN'::float8
    -- > 0` and `'Infinity'::float8 > 0` both evaluate true. `v = v` does
    -- NOT reject NaN either (PostgreSQL defines NaN equal to itself for
    -- ordering consistency, unlike IEEE754). The correct, PostgreSQL-
    -- specific finiteness test is `v > 0 AND v < 'Infinity'::float8`:
    -- NaN and +Infinity both fail `< 'Infinity'::float8` (neither is
    -- strictly less than it), while -Infinity/0/negative already fail
    -- `> 0`. This is still defense-in-depth only -- the Python reader
    -- (`storage/v2_setup_readers.py::read_v2_instrument`) keeps its own
    -- `math.isfinite()` check as the primary authority and is NOT removed.
    CONSTRAINT ck_eih_tick_size_positive CHECK (
        tick_size IS NULL OR (tick_size > 0 AND tick_size < 'Infinity'::float8)),
    CONSTRAINT ck_eih_contract_multiplier_positive CHECK (
        contract_multiplier IS NULL OR
        (contract_multiplier > 0 AND contract_multiplier < 'Infinity'::float8)),
    CONSTRAINT ck_eih_price_precision_nonneg CHECK (
        price_precision IS NULL OR price_precision >= 0),
    CONSTRAINT ck_eih_quantity_precision_nonneg CHECK (
        quantity_precision IS NULL OR quantity_precision >= 0),
    CONSTRAINT ck_eih_interval_well_formed CHECK (
        effective_until IS NULL OR effective_until > effective_from),
    -- (finding 2) A value cannot become accepted/effective before it was
    -- even observed -- the DB-level mirror of the same Python check in
    -- Database.upsert_exchange_instrument/seed_current_instrument_history.
    CONSTRAINT ck_eih_observed_at_not_after_effective_from CHECK (
        observed_at IS NULL OR observed_at <= effective_from),
    CONSTRAINT ck_eih_accepted_metadata_revision_positive CHECK (
        accepted_metadata_revision IS NULL OR accepted_metadata_revision > 0)
);

-- At most one currently-open (still-valid) history row per identity --
-- see the table-level comment above for why this, plus transactional
-- close-then-open, is chosen over a btree_gist exclusion constraint.
CREATE UNIQUE INDEX IF NOT EXISTS ux_eih_one_open_interval_per_identity
    ON exchange_instrument_history (exchange, symbol, market_type)
    WHERE effective_until IS NULL;

-- ============================================================
-- Tech-lead review 4991738511: calculation_version fork enforcement,
-- connected end-to-end to the REAL Stage-2 feature-computation path.
--
-- The previous round's `accepted_code_version` column (removed above,
-- replaced by `accepted_metadata_revision`) was correctly rejected: it
-- proved only that two stored LABELS differed, never that the live
-- Stage-2 assembly path (`analytics/feature_engine/input_adapter.py::
-- build_assembly_context`/`assemble_exchange_feature_request`) was
-- mechanically prevented from consuming NEW critical metadata under an
-- OLD `calculation_version`. `calculation_version` is computed BEFORE
-- any instrument metadata is even read (see `build_assembly_context`),
-- from `compute_calculation_version(feature_schema_version, config_hash,
-- code_version)` -- a formula/format this PR still does NOT change.
--
-- This table is the SINGLE GLOBAL source of truth for "what instrument-
-- metadata revision does Stage 2 feature computation currently require,
-- across ALL exchanges and symbols" -- deliberately ONE shared row, not
-- one per (exchange, symbol, market_type): `calculation_version` is a
-- SHARED Stage-2 computation namespace (`common/stage2_config.py`'s
-- `defaults.instrument_metadata_revision` applies identically to every
-- resolved per-symbol config, and `Stage2Config._validate()` refuses any
-- asset_tier/symbol override of that key) -- a critical metadata change
-- accepted for even ONE venue must fork the coherent namespace for ALL
-- venues together, never fragment it into per-venue sub-namespaces the
-- existing consensus contract does not support.
--
-- Mechanism, closing the loop all the way to feature persistence:
--   1. `defaults.instrument_metadata_revision` (config/stage2.yaml) is
--      part of the RESOLVED per-symbol config, hence part of
--      `config_hash`, hence part of `calculation_version` -- changing it
--      genuinely forks `calculation_version`, with ZERO changes to
--      `compute_calculation_version`'s formula/format.
--   2. `Database.upsert_exchange_instrument`'s `accept_mismatch=True`
--      path, on a genuine CRITICAL-field diff, REQUIRES an explicit
--      `target_metadata_revision` strictly greater than this table's
--      current `required_revision` -- and atomically bumps it, in the
--      SAME transaction as the LKG upsert and the history interval
--      close/open (serialized additionally by `SELECT ... FOR UPDATE`
--      on this table's one row, so two concurrent critical acceptances
--      for DIFFERENT identities cannot race past each other).
--   3. `storage/stage2_readers.py::read_exchange_feature_raw_bundle`
--      reads this table's CURRENT `required_revision` as part of the
--      SAME fixed raw-bundle read every live feature computation already
--      performs (`ExchangeFeatureRawBundle.required_metadata_revision`).
--   4. `analytics/feature_engine/input_adapter.py::
--      assemble_exchange_feature_request` compares the resolved config's
--      OWN `instrument_metadata_revision` (already baked into this
--      request's `calculation_version`) against that live value and
--      FAILS CLOSED (`FeatureInputError`, before any `ExchangeFeatureRequest`
--      is constructed) on a mismatch.
-- Until an operator explicitly updates `config/stage2.yaml` to adopt the
-- new revision (which forks `calculation_version` per step 1), ANY
-- Stage 2 computation for ANY venue/symbol refuses to persist a feature
-- vector at all -- it can never silently continue computing under the
-- OLD `calculation_version` against the NEW metadata. A non-critical
-- value change (e.g. price_precision-only) never bumps this table --
-- only a deliberately-accepted CRITICAL change does (finding 10).
--
-- Bootstrapped explicitly (never a hardcoded DDL literal) via
-- `Database.bootstrap_instrument_metadata_revision`, established from
-- the resolved Stage 2 configuration's OWN initial
-- `instrument_metadata_revision` -- idempotent, never overwrites an
-- already-initialized row.
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_instrument_metadata_state (
    singleton         BOOLEAN NOT NULL DEFAULT TRUE,
    required_revision INTEGER NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (singleton),
    CONSTRAINT ck_s2ims_singleton_true CHECK (singleton),
    CONSTRAINT ck_s2ims_revision_positive CHECK (required_revision > 0)
);

-- ============================================================
-- V2-H2e: Stage-2 correction-publication coherence barrier
-- (docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3.4, §2.1).
-- Amended per tech-lead review (round 2, finding 3 / finding 1): replaces
-- a single (symbol, market_type)-only CLEAN/DIRTY status with a
-- revision-comparison model across TWO tables -- see
-- `storage/stage2_publication_state.py`'s module docstring for the full
-- rationale (the single-status design silently authorized a SUPERSEDED
-- calculation_version as CLEAN merely because the ACTIVE version was
-- repaired; it also had no compare-and-swap, so an overlapping later
-- correction could be silently clobbered by a stale in-flight publisher).
--
-- Clean-room audit finding these tables close: a raw-data correction
-- (`Database.insert_klines`/`insert_open_interest`/`insert_funding`
-- upserting an ALREADY-EXISTING row, or a first-ever insert landing inside
-- an already-published derived bucket) and the Stage 2 derived recompute
-- it implies (`STAGE2_SPEC.md` §8.3) are NOT atomic with each other today
-- -- there is no code anywhere in this repository that enqueues, drains,
-- or otherwise executes `stage2_recompute_queue`/`stage2_watermarks`
-- (schema-only scaffolding; confirmed by exhaustive grep across
-- runtime/analytics/storage). A REPEATABLE READ V2 read transaction
-- starting in the window between the raw correction's commit and the
-- (currently nonexistent) derived republish would silently combine
-- POST-correction raw facts with PRE-correction derived facts under the
-- same `calculation_version` -- exactly the semantic hole §3.4 freezes as
-- a correctness requirement, which H2c's own per-request raw-bundle
-- REPEATABLE READ transaction (`fetch_exchange_feature_raw_bundle`) does
-- NOT close (it only protects ONE Stage 2 feature request's OWN seven
-- reads, never the broader Stage 3+5 V2 decision view).
--
-- `stage2_raw_revision`, scope (symbol, market_type) -- NOT
-- `calculation_version`: ONE monotonic BIGINT counter, bumped by EVERY
-- raw write a raw writer determines can invalidate already-published
-- derived history (a genuine correction to an existing row, OR a
-- first-ever insert landing inside an already-published bucket -- see
-- `storage/db.py`). Raw market data has no `calculation_version` of its
-- own (confirmed: neither `data_ingestion/manager.py` nor
-- `backfill/backfill.py` mentions it), so this counter deliberately
-- cannot be, and is not, scoped by it.
--
-- `stage2_publication_state`, scope (symbol, market_type,
-- calculation_version): `published_raw_revision` records the
-- `stage2_raw_revision` value THIS calculation_version's derived output
-- was last completely, atomically published against. A scope+version is
-- CLEAN iff `published_raw_revision` equals the CURRENT
-- `stage2_raw_revision.raw_revision` for that `(symbol, market_type)` --
-- computed by comparison at read time
-- (`storage/stage2_publication_state.py::read_publication_state`), never
-- stored as a separate boolean that could drift from the two facts it
-- summarizes. A superseded calculation_version's `published_raw_revision`
-- simply stays behind forever (nobody republishes it), so it correctly,
-- structurally reads STALE regardless of what happens to the active
-- version -- this is what fixes finding 3, not a documentation caveat.
--
-- Row lifecycle:
--   - `stage2_raw_revision` is bumped via `bump_raw_revision`, ALWAYS
--     inside the SAME transaction/COMMIT as the raw write that triggered
--     it.
--   - `stage2_publication_state` is written ONLY by
--     `mark_publication_clean_cas` (via `Database.publish_stage2_correction`'s
--     single atomic transaction, which writes every derived publication-
--     member family AND this CAS'd row in the SAME COMMIT). The CAS locks
--     `stage2_raw_revision`'s row (`SELECT ... FOR UPDATE`) and compares
--     the caller-supplied `expected_raw_revision` against the
--     authoritative current value; a mismatch (a LATER correction
--     committed while this publisher was computing) raises and rolls back
--     the WHOLE transaction -- no family write from a stale publish
--     attempt ever survives. `publication_generation` is bumped (never
--     reset) on every successful CAS'd publish -- a DB-owned, monotonic,
--     non-wall-clock, non-UUID counter distinct from
--     `stage2_instrument_metadata_state.required_revision` (that table
--     tracks instrument-METADATA generation; this tracks CORRECTION-
--     PUBLICATION generation -- different facts, deliberately not
--     conflated).
--   - `stage2_raw_revision` is bootstrapped (never a hardcoded DDL
--     literal) via `Database.bootstrap_stage2_raw_revision`, idempotent,
--     seeding revision 0 -- mirroring `bootstrap_instrument_metadata_revision`'s
--     SEEDED/ALREADY_INITIALIZED shape. `stage2_publication_state` is
--     NEVER auto-bootstrapped for any scope+version -- absence of a row is
--     ALWAYS treated identically to STALE by `open_v2_coherent_read_session`,
--     for a brand-new namespace exactly as much as for a legacy pre-H2e
--     database with pre-existing raw+derived history nobody has ever
--     explicitly published/reconciled through this barrier. This is a
--     deliberate simplification over "detect fresh vs. legacy and
--     auto-CLEAN only the genuinely fresh case": there is no classification
--     to get wrong, because there is no automatic CLEAN path at all.
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_raw_revision (
    symbol            TEXT NOT NULL,
    market_type       TEXT NOT NULL,
    raw_revision      BIGINT NOT NULL DEFAULT 0,
    last_bump_reason  TEXT,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, market_type),
    CONSTRAINT ck_srr_revision_nonneg CHECK (raw_revision >= 0)
);

CREATE TABLE IF NOT EXISTS stage2_publication_state (
    symbol                  TEXT NOT NULL,
    market_type             TEXT NOT NULL,
    calculation_version     TEXT NOT NULL,
    published_raw_revision  BIGINT NOT NULL,
    publication_generation  BIGINT NOT NULL DEFAULT 1,
    published_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (symbol, market_type, calculation_version),
    CONSTRAINT ck_sps_revision_nonneg CHECK (published_raw_revision >= 0),
    CONSTRAINT ck_sps_generation_positive CHECK (publication_generation > 0)
);
