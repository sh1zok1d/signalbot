-- BTC Signal Bot — TimescaleDB schema
-- Run once at startup (db.py:init_schema executes this file, all statements
-- are idempotent via IF NOT EXISTS).

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1m bars per exchange (raw ingestion granularity; 5m/15m/1h are
-- continuous aggregates derived from this table per spec section 3
-- metrics_engine: "Ресемплинг 5m/15m/1h/4h").
-- ============================================================
CREATE TABLE IF NOT EXISTS klines_1m (
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    open                DOUBLE PRECISION NOT NULL,
    high                DOUBLE PRECISION NOT NULL,
    low                 DOUBLE PRECISION NOT NULL,
    close               DOUBLE PRECISION NOT NULL,
    volume              DOUBLE PRECISION NOT NULL,
    taker_buy_volume    DOUBLE PRECISION,
    taker_sell_volume   DOUBLE PRECISION,
    trades_count        INTEGER,
    source               TEXT NOT NULL DEFAULT 'backfill', -- backfill | live
    PRIMARY KEY (exchange, symbol, ts)
);

SELECT create_hypertable('klines_1m', 'ts', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS ix_klines_1m_symbol_ts ON klines_1m (symbol, ts DESC);

-- ============================================================
-- Open interest. Backfilled at whatever granularity the exchange exposes
-- (see config.yaml backfill.oi_history_interval_fallback); live values are
-- 1m from WS/REST polling.
-- ============================================================
CREATE TABLE IF NOT EXISTS open_interest (
    exchange    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    oi_contracts DOUBLE PRECISION,
    oi_notional  DOUBLE PRECISION,
    source       TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);

SELECT create_hypertable('open_interest', 'ts', if_not_exists => TRUE);

-- OI units differ across exchanges (Binance/Bybit/Bitget report base BTC,
-- OKX reports contracts), so raw values are NOT comparable and must NEVER be
-- summed across exchanges. V0 signal logic works per-exchange (% change,
-- per-exchange percentile, then multi-exchange voting). These columns keep the
-- data honest: store the raw number + what it means; leave any normalized
-- value NULL unless it is directly provided or verified — no assumed
-- coefficients. (ADD COLUMN IF NOT EXISTS is a safe, data-preserving migration.)
--   oi_unit:        'base' | 'contracts' | 'usd'  (what oi_raw is denominated in)
--   contract_value: base-asset amount per contract, set ONLY when verified
--   oi_notional_usd:USD notional, set ONLY when the exchange returns it directly
ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS oi_raw         DOUBLE PRECISION;
ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS oi_unit        TEXT;
ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS contract_value DOUBLE PRECISION;
ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS oi_base_asset  TEXT;
ALTER TABLE open_interest ADD COLUMN IF NOT EXISTS oi_notional_usd DOUBLE PRECISION;

-- ============================================================
-- Funding rate history
-- ============================================================
CREATE TABLE IF NOT EXISTS funding_rate (
    exchange            TEXT NOT NULL,
    symbol              TEXT NOT NULL,
    ts                  TIMESTAMPTZ NOT NULL,
    funding_rate        DOUBLE PRECISION NOT NULL,
    next_funding_time   TIMESTAMPTZ,
    source               TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);

SELECT create_hypertable('funding_rate', 'ts', if_not_exists => TRUE);

-- ============================================================
-- Mark price
-- ============================================================
CREATE TABLE IF NOT EXISTS mark_price (
    exchange    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    mark_price  DOUBLE PRECISION NOT NULL,
    source       TEXT NOT NULL DEFAULT 'backfill',
    PRIMARY KEY (exchange, symbol, ts)
);

SELECT create_hypertable('mark_price', 'ts', if_not_exists => TRUE);

-- ============================================================
-- Liquidations — LIVE ONLY, never backfilled (spec section 2:
-- "liquidations_and_orderflow: NOT_BACKFILLED"). No zero-filling: absence
-- of rows for a period means absence of data, not zero liquidations.
-- ============================================================
CREATE TABLE IF NOT EXISTS liquidations (
    id           BIGSERIAL,
    exchange     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    ts           TIMESTAMPTZ NOT NULL,
    side         TEXT NOT NULL,  -- 'long' | 'short' (side that got liquidated)
    price        DOUBLE PRECISION NOT NULL,
    qty          DOUBLE PRECISION NOT NULL,
    notional     DOUBLE PRECISION,
    -- Binance forceOrder stream is a snapshot feed (1 evt/symbol/1000ms),
    -- so it under-counts during liquidation cascades. Flag it explicitly
    -- per spec 1.6 so consensus counting can exclude/weight it correctly.
    is_snapshot_feed BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (id, ts)
);

SELECT create_hypertable('liquidations', 'ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_liquidations_symbol_ts ON liquidations (symbol, ts DESC);

-- ============================================================
-- Exchange connectivity / coverage log — disconnects, restores, coverage
-- transitions. Used for /status, SYSTEM ALERT, restored-alert messages.
-- ============================================================
CREATE TABLE IF NOT EXISTS connectivity_events (
    id          BIGSERIAL PRIMARY KEY,
    exchange    TEXT NOT NULL,
    event_type  TEXT NOT NULL, -- disconnect | restore | coverage_change
    ts          TIMESTAMPTZ NOT NULL DEFAULT now(),
    detail      JSONB
);

-- ============================================================
-- Backfill run bookkeeping — lets us resume/skip completed backfills and
-- mark partial runs (missing liquidations/order flow) per spec section 8.
-- ============================================================
CREATE TABLE IF NOT EXISTS backfill_runs (
    id              BIGSERIAL PRIMARY KEY,
    exchange        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    source          TEXT NOT NULL, -- klines | open_interest | funding | mark_price
    window_start    TIMESTAMPTZ NOT NULL,
    window_end      TIMESTAMPTZ NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running', -- running | complete | partial | failed
    rows_written    INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    note            TEXT
);

-- ============================================================
-- Exchange x metric capability registry (structural, queryable).
-- Seeded at startup from common/capabilities.py (declarative data, NOT the
-- WS client classes). Lets validate + the future signal_engine answer
-- "is this source structurally available / snapshot / aggregated / never?"
-- via SQL, instead of inspecting Python client code. This is what makes the
-- spec's "count_only_valid_sources" / coverage rules enforceable from data.
--   coverage_type: full | snapshot | aggregated | unavailable
--   expected_freshness_s: NULL for event-driven sources (liquidations)
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_capabilities (
    exchange              TEXT NOT NULL,
    metric                TEXT NOT NULL,
    live_supported        BOOLEAN NOT NULL,
    historical_supported  BOOLEAN NOT NULL,
    coverage_type         TEXT NOT NULL,
    expected_freshness_s  INTEGER,
    note                  TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, metric),
    CONSTRAINT ck_coverage_type CHECK (
        coverage_type IN ('full', 'snapshot', 'aggregated', 'unavailable'))
);

-- `enabled` reflects config.enabled_exchanges: a structurally-capable exchange
-- can still be turned OFF for the active MVP (e.g. Bitget). Disabled exchanges
-- do not ingest, do not count toward coverage, and must be excluded from
-- percentile voting — so the signal_engine reads this flag, not the config.
ALTER TABLE exchange_capabilities ADD COLUMN IF NOT EXISTS enabled BOOLEAN NOT NULL DEFAULT TRUE;

-- ============================================================
-- Continuous aggregates: 5m / 15m / 1h / 4h derived from klines_1m
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS klines_5m
WITH (timescaledb.continuous) AS
SELECT
    exchange, symbol,
    time_bucket('5 minutes', ts) AS bucket,
    first(open, ts)  AS open,
    max(high)        AS high,
    min(low)         AS low,
    last(close, ts)  AS close,
    sum(volume)      AS volume,
    sum(taker_buy_volume)  AS taker_buy_volume,
    sum(taker_sell_volume) AS taker_sell_volume
FROM klines_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS klines_15m
WITH (timescaledb.continuous) AS
SELECT
    exchange, symbol,
    time_bucket('15 minutes', ts) AS bucket,
    first(open, ts)  AS open,
    max(high)        AS high,
    min(low)         AS low,
    last(close, ts)  AS close,
    sum(volume)      AS volume,
    sum(taker_buy_volume)  AS taker_buy_volume,
    sum(taker_sell_volume) AS taker_sell_volume
FROM klines_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS klines_1h
WITH (timescaledb.continuous) AS
SELECT
    exchange, symbol,
    time_bucket('1 hour', ts) AS bucket,
    first(open, ts)  AS open,
    max(high)        AS high,
    min(low)         AS low,
    last(close, ts)  AS close,
    sum(volume)      AS volume,
    sum(taker_buy_volume)  AS taker_buy_volume,
    sum(taker_sell_volume) AS taker_sell_volume
FROM klines_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

-- 4h context timeframe (product spec: "контекст 15m, 1h, 4h"). Added later
-- than 5m/15m/1h; CREATE ... IF NOT EXISTS + WITH NO DATA is idempotent and
-- never drops or rewrites existing rows in klines_1m or the other aggregates.
CREATE MATERIALIZED VIEW IF NOT EXISTS klines_4h
WITH (timescaledb.continuous) AS
SELECT
    exchange, symbol,
    time_bucket('4 hours', ts) AS bucket,
    first(open, ts)  AS open,
    max(high)        AS high,
    min(low)         AS low,
    last(close, ts)  AS close,
    sum(volume)      AS volume,
    sum(taker_buy_volume)  AS taker_buy_volume,
    sum(taker_sell_volume) AS taker_sell_volume
FROM klines_1m
GROUP BY exchange, symbol, bucket
WITH NO DATA;

-- Refresh policies keep the aggregates near-real-time.
SELECT add_continuous_aggregate_policy('klines_5m',
    start_offset => INTERVAL '1 day',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('klines_15m',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('klines_1h',
    start_offset => INTERVAL '10 days',
    end_offset   => INTERVAL '15 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE);

SELECT add_continuous_aggregate_policy('klines_4h',
    start_offset => INTERVAL '30 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE);
