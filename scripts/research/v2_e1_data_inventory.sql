\set ON_ERROR_STOP on
\pset pager off
\timing on

-- V2 E1 Detector Separation — DATA INVENTORY ONLY
--
-- IMPORTANT: this script intentionally does NOT calculate any future returns,
-- MFE/MAE, detector performance, or baseline performance. It is safe to run
-- before the E1 development/holdout split is frozen.
--
-- Expected use:
--   psql "$DATABASE_URL" -v symbol=BTCUSDT -f scripts/research/v2_e1_data_inventory.sql
--
-- Read-only by design.
BEGIN TRANSACTION READ ONLY;

\echo '=== E1 inventory: database identity ==='
SELECT current_database() AS database_name,
       current_user AS database_user,
       now() AT TIME ZONE 'UTC' AS inspected_at_utc,
       version() AS postgres_version;

\echo '=== Relevant relation inventory ==='
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND (
    table_name IN (
      'klines_1m', 'open_interest', 'funding_rate', 'liquidations',
      'exchange_feature_vectors', 'consensus_feature_vectors',
      'percentile_snapshots', 'data_health_snapshots',
      'exchange_instruments', 'exchange_instrument_history',
      'symbol_exchange_capabilities', 'stage2_watermarks'
    )
    OR table_name LIKE '%kline%'
    OR table_name LIKE '%interest%'
    OR table_name LIKE '%funding%'
    OR table_name LIKE '%liquid%'
    OR table_name LIKE '%instrument%'
  )
ORDER BY table_schema, table_name;

\echo '=== Raw Binance/reference 1m OHLCV coverage by exchange/source ==='
SELECT exchange,
       source,
       min(ts) AS first_ts,
       max(ts) AS last_ts,
       count(*) AS rows,
       count(*) FILTER (WHERE taker_buy_volume IS NOT NULL) AS taker_buy_rows,
       count(*) FILTER (WHERE taker_sell_volume IS NOT NULL) AS taker_sell_rows
FROM klines_1m
WHERE symbol = :'symbol'
GROUP BY exchange, source
ORDER BY exchange, source;

\echo '=== Raw 1m cadence / gap diagnostics ==='
WITH ordered AS (
  SELECT exchange, source, ts,
         lag(ts) OVER (PARTITION BY exchange, source ORDER BY ts) AS prev_ts
  FROM klines_1m
  WHERE symbol = :'symbol'
), gaps AS (
  SELECT exchange, source,
         extract(epoch FROM (ts - prev_ts))::bigint AS gap_s
  FROM ordered
  WHERE prev_ts IS NOT NULL
)
SELECT exchange,
       source,
       count(*) AS observed_intervals,
       count(*) FILTER (WHERE gap_s > 60) AS gaps_gt_60s,
       max(gap_s) AS max_gap_s,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY gap_s) AS median_gap_s,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY gap_s) AS p95_gap_s
FROM gaps
GROUP BY exchange, source
ORDER BY exchange, source;

\echo '=== Open-interest historical coverage and provider cadence ==='
SELECT exchange,
       source,
       min(ts) AS first_ts,
       max(ts) AS last_ts,
       count(*) AS rows,
       count(*) FILTER (WHERE oi_raw IS NOT NULL OR oi_contracts IS NOT NULL OR oi_notional IS NOT NULL) AS rows_with_oi,
       count(*) FILTER (WHERE oi_unit IS NOT NULL) AS rows_with_explicit_unit
FROM open_interest
WHERE symbol = :'symbol'
GROUP BY exchange, source
ORDER BY exchange, source;

WITH ordered AS (
  SELECT exchange, source, ts,
         lag(ts) OVER (PARTITION BY exchange, source ORDER BY ts) AS prev_ts
  FROM open_interest
  WHERE symbol = :'symbol'
), cadence AS (
  SELECT exchange, source,
         extract(epoch FROM (ts - prev_ts))::double precision AS delta_s
  FROM ordered
  WHERE prev_ts IS NOT NULL
)
SELECT exchange,
       source,
       count(*) AS observed_intervals,
       percentile_cont(0.10) WITHIN GROUP (ORDER BY delta_s) AS p10_interval_s,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY delta_s) AS median_interval_s,
       percentile_cont(0.90) WITHIN GROUP (ORDER BY delta_s) AS p90_interval_s,
       max(delta_s) AS max_interval_s
FROM cadence
GROUP BY exchange, source
ORDER BY exchange, source;

\echo '=== Funding coverage ==='
SELECT exchange,
       source,
       min(ts) AS first_ts,
       max(ts) AS last_ts,
       count(*) AS rows
FROM funding_rate
WHERE symbol = :'symbol'
GROUP BY exchange, source
ORDER BY exchange, source;

\echo '=== Liquidation coverage (live-only semantics; absence is NOT zero) ==='
SELECT exchange,
       min(ts) AS first_ts,
       max(ts) AS last_ts,
       count(*) AS events,
       count(*) FILTER (WHERE is_snapshot_feed) AS snapshot_feed_events,
       count(*) FILTER (WHERE NOT is_snapshot_feed) AS non_snapshot_events
FROM liquidations
WHERE symbol = :'symbol'
GROUP BY exchange
ORDER BY exchange;

\echo '=== Stage-2 exchange feature coverage ==='
SELECT exchange,
       market_type,
       timeframe,
       feature_schema_version,
       calculation_version,
       min(bucket_ts) AS first_bucket,
       max(bucket_ts) AS last_bucket,
       count(*) AS rows,
       count(*) FILTER (WHERE is_usable) AS usable_rows,
       count(*) FILTER (WHERE NOT is_usable OR has_gap) AS degraded_rows,
       count(*) FILTER (WHERE close_price IS NOT NULL) AS close_rows,
       count(*) FILTER (WHERE taker_delta_notional_usd IS NOT NULL) AS taker_rows,
       count(*) FILTER (WHERE oi_change_pct IS NOT NULL) AS oi_rows,
       count(*) FILTER (WHERE funding_rate IS NOT NULL) AS funding_rows,
       count(*) FILTER (
         WHERE long_liquidation_notional IS NOT NULL
            OR short_liquidation_notional IS NOT NULL
            OR liquidation_event_count IS NOT NULL
       ) AS liquidation_rows
FROM exchange_feature_vectors
WHERE symbol = :'symbol'
GROUP BY exchange, market_type, timeframe, feature_schema_version, calculation_version
ORDER BY calculation_version, timeframe, exchange;

\echo '=== Stage-2 consensus feature coverage ==='
SELECT market_type,
       timeframe,
       feature_schema_version,
       calculation_version,
       min(bucket_ts) AS first_bucket,
       max(bucket_ts) AS last_bucket,
       count(*) AS rows,
       count(*) FILTER (WHERE price_move_pct_median IS NOT NULL) AS price_rows,
       count(*) FILTER (WHERE taker_delta_notional_usd_sum IS NOT NULL) AS taker_rows,
       count(*) FILTER (WHERE oi_change_pct_median IS NOT NULL) AS oi_rows,
       count(*) FILTER (WHERE funding_rate_median IS NOT NULL) AS funding_rows,
       count(*) FILTER (
         WHERE observed_long_liquidation_notional_sum IS NOT NULL
            OR observed_short_liquidation_notional_sum IS NOT NULL
            OR observed_liquidation_event_count_sum IS NOT NULL
       ) AS liquidation_rows,
       count(*) FILTER (WHERE is_partial_consensus) AS partial_consensus_rows
FROM consensus_feature_vectors
WHERE symbol = :'symbol'
GROUP BY market_type, timeframe, feature_schema_version, calculation_version
ORDER BY calculation_version, timeframe;

\echo '=== Percentile snapshot coverage ==='
SELECT scope,
       exchange,
       market_type,
       metric,
       timeframe,
       percentile_window,
       feature_schema_version,
       calculation_version,
       min(bucket_ts) AS first_bucket,
       max(bucket_ts) AS last_bucket,
       count(*) AS rows,
       count(*) FILTER (WHERE percentile_rank IS NOT NULL) AS ranked_rows,
       min(sample_size) AS min_sample_size,
       max(sample_size) AS max_sample_size
FROM percentile_snapshots
WHERE symbol = :'symbol'
GROUP BY scope, exchange, market_type, metric, timeframe, percentile_window,
         feature_schema_version, calculation_version
ORDER BY calculation_version, timeframe, scope, exchange, metric, percentile_window;

\echo '=== Stage-2 watermarks ==='
SELECT stream,
       market_type,
       timeframe,
       calculation_version,
       last_computed_bucket_ts,
       last_run_at
FROM stage2_watermarks
WHERE symbol = :'symbol'
ORDER BY calculation_version, stream, timeframe;

\echo '=== Symbol/exchange capability declarations (historical vs live) ==='
SELECT exchange,
       market_type,
       metric,
       live_supported,
       historical_supported,
       coverage_type,
       expected_freshness_s,
       enabled,
       note
FROM symbol_exchange_capabilities
WHERE symbol = :'symbol'
ORDER BY metric, exchange;

\echo '=== Instrument metadata history/current coverage ==='
SELECT exchange,
       market_type,
       quantity_unit,
       contract_multiplier,
       tick_size,
       metadata_source,
       fetched_at,
       is_stale
FROM exchange_instruments
WHERE symbol = :'symbol'
ORDER BY exchange, market_type;

\echo '=== Candidate-safe coverage overlap by Stage-2 identity (NO outcomes) ==='
WITH c AS (
  SELECT market_type, timeframe, feature_schema_version, calculation_version,
         min(bucket_ts) AS first_bucket, max(bucket_ts) AS last_bucket, count(*) AS n
  FROM consensus_feature_vectors
  WHERE symbol = :'symbol'
  GROUP BY market_type, timeframe, feature_schema_version, calculation_version
), e AS (
  SELECT market_type, timeframe, feature_schema_version, calculation_version,
         min(bucket_ts) FILTER (WHERE exchange = 'binance') AS binance_first,
         max(bucket_ts) FILTER (WHERE exchange = 'binance') AS binance_last,
         count(*) FILTER (WHERE exchange = 'binance') AS binance_n
  FROM exchange_feature_vectors
  WHERE symbol = :'symbol'
  GROUP BY market_type, timeframe, feature_schema_version, calculation_version
)
SELECT c.market_type,
       c.timeframe,
       c.feature_schema_version,
       c.calculation_version,
       greatest(c.first_bucket, e.binance_first) AS overlap_start,
       least(c.last_bucket, e.binance_last) AS overlap_end,
       c.n AS consensus_rows,
       e.binance_n AS binance_rows
FROM c
JOIN e USING (market_type, timeframe, feature_schema_version, calculation_version)
ORDER BY c.calculation_version, c.timeframe;

ROLLBACK;
