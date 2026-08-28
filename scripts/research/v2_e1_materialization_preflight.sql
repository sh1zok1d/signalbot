\set ON_ERROR_STOP on
\pset pager off
\timing on

BEGIN;
SET TRANSACTION READ ONLY;

\echo '=== E1 materialization preflight: dominant Stage-2 provenance ==='
SELECT
    calculation_version,
    feature_schema_version,
    config_hash,
    config_version,
    code_version,
    min(bucket_ts) AS first_bucket,
    max(bucket_ts) AS last_bucket,
    count(*) AS rows
FROM consensus_feature_vectors
WHERE symbol = :'symbol'
  AND market_type = 'perp'
  AND calculation_version = :'calculation_version'
GROUP BY calculation_version, feature_schema_version, config_hash, config_version, code_version
ORDER BY first_bucket;

\echo '=== Exchange-level provenance must agree with consensus namespace ==='
SELECT
    exchange,
    calculation_version,
    feature_schema_version,
    config_hash,
    config_version,
    code_version,
    min(bucket_ts) AS first_bucket,
    max(bucket_ts) AS last_bucket,
    count(*) AS rows
FROM exchange_feature_vectors
WHERE symbol = :'symbol'
  AND market_type = 'perp'
  AND calculation_version = :'calculation_version'
GROUP BY exchange, calculation_version, feature_schema_version, config_hash, config_version, code_version
ORDER BY exchange, first_bucket;

\echo '=== Instrument-history relation/columns ==='
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name ILIKE '%instrument%history%'
ORDER BY table_name;

SELECT
    table_name,
    ordinal_position,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name ILIKE '%instrument%history%'
ORDER BY table_name, ordinal_position;

SELECT to_regclass('public.exchange_instrument_history') IS NOT NULL AS has_exchange_instrument_history \gset
\if :has_exchange_instrument_history
\echo '=== exchange_instrument_history rows (read-only, full row shape) ==='
SELECT *
FROM exchange_instrument_history
WHERE symbol = :'symbol'
ORDER BY exchange
LIMIT 100;
\else
\echo 'NO public.exchange_instrument_history relation'
\endif

\echo '=== Stage-2 publication/coherence relations ==='
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND (
      table_name ILIKE '%publication%'
      OR table_name ILIKE '%raw_revision%'
      OR table_name ILIKE '%correction%'
  )
ORDER BY table_name;

\echo '=== Stage-2 health coverage for dominant namespace ==='
SELECT
    exchange,
    metric,
    min(snapshot_ts) AS first_snapshot,
    max(snapshot_ts) AS last_snapshot,
    count(*) AS rows,
    count(*) FILTER (WHERE is_usable) AS usable_rows,
    count(*) FILTER (WHERE is_stale) AS stale_rows
FROM data_health_snapshots
WHERE symbol = :'symbol'
  AND market_type = 'perp'
  AND calculation_version = :'calculation_version'
GROUP BY exchange, metric
ORDER BY exchange, metric;

\echo '=== Raw live-equivalent lower-bound checks ==='
SELECT
    exchange,
    min(ts) FILTER (WHERE source = 'live') AS first_live_1m,
    max(ts) FILTER (WHERE source = 'live') AS last_live_1m,
    count(*) FILTER (WHERE source = 'live' AND taker_buy_volume IS NOT NULL AND taker_sell_volume IS NOT NULL) AS live_taker_rows
FROM klines_1m
WHERE symbol = :'symbol'
GROUP BY exchange
ORDER BY exchange;

SELECT
    exchange,
    min(ts) FILTER (WHERE source = 'live') AS first_live_oi,
    max(ts) FILTER (WHERE source = 'live') AS last_live_oi
FROM open_interest
WHERE symbol = :'symbol'
GROUP BY exchange
ORDER BY exchange;

\echo '=== Existing rows outside 5m for dominant namespace (expected empty before materialization) ==='
SELECT
    'exchange' AS layer,
    timeframe,
    count(*) AS rows,
    min(bucket_ts) AS first_bucket,
    max(bucket_ts) AS last_bucket
FROM exchange_feature_vectors
WHERE symbol = :'symbol'
  AND market_type = 'perp'
  AND calculation_version = :'calculation_version'
  AND timeframe <> '5m'
GROUP BY timeframe
UNION ALL
SELECT
    'consensus' AS layer,
    timeframe,
    count(*) AS rows,
    min(bucket_ts) AS first_bucket,
    max(bucket_ts) AS last_bucket
FROM consensus_feature_vectors
WHERE symbol = :'symbol'
  AND market_type = 'perp'
  AND calculation_version = :'calculation_version'
  AND timeframe <> '5m'
GROUP BY timeframe
ORDER BY layer, timeframe;

ROLLBACK;
