-- Read-only coverage aggregates for the live-archive replay preflight.
-- Server-side counts, timestamps, unit labels, and boolean flags only.
-- No price, OHLC, volume, taker, open-interest magnitude, or liquidation notional
-- is selected as a result column. Session timezone must be UTC.

-- statement: archive_klines
SELECT
    'klines_1m' AS table_name,
    exchange,
    source,
    count(*) AS row_count,
    min(ts) AS min_ts,
    max(ts) AS max_ts,
    NULL::text AS note
FROM klines_1m
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
GROUP BY exchange, source
ORDER BY exchange, source

-- statement: archive_open_interest
SELECT
    'open_interest' AS table_name,
    exchange,
    source,
    count(*) AS row_count,
    min(ts) AS min_ts,
    max(ts) AS max_ts,
    NULL::text AS note
FROM open_interest
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
GROUP BY exchange, source
ORDER BY exchange, source

-- statement: archive_liquidations
SELECT
    'liquidations' AS table_name,
    exchange,
    NULL::text AS source,
    count(*) AS row_count,
    min(ts) AS min_ts,
    max(ts) AS max_ts,
    'no_source_column' AS note
FROM liquidations
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
GROUP BY exchange
ORDER BY exchange

-- statement: archive_connectivity
SELECT
    'connectivity_events' AS table_name,
    exchange,
    event_type AS source,
    count(*) AS row_count,
    min(ts) AS min_ts,
    max(ts) AS max_ts,
    'event_type_in_source_column' AS note
FROM connectivity_events
WHERE exchange IN ('binance', 'bybit', 'okx')
  AND event_type IN ('disconnect', 'restore')
GROUP BY exchange, event_type
ORDER BY exchange, event_type

-- statement: archive_instrument_history
SELECT
    'exchange_instrument_history' AS table_name,
    exchange,
    NULL::text AS source,
    count(*) AS row_count,
    min(effective_from) AS min_ts,
    max(effective_from) AS max_ts,
    'effective_from_bounds_not_market_ts' AS note
FROM exchange_instrument_history
WHERE symbol = 'BTCUSDT'
  AND market_type = 'perp'
  AND exchange IN ('binance', 'bybit', 'okx')
GROUP BY exchange
ORDER BY exchange

-- statement: oi_unit_changes
SELECT
    exchange,
    source,
    oi_unit,
    count(*) AS row_count,
    min(ts) AS min_ts,
    max(ts) AS max_ts
FROM open_interest
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
GROUP BY exchange, source, oi_unit
ORDER BY exchange, source, oi_unit

-- statement: instrument_history_intervals
SELECT
    exchange,
    symbol,
    market_type,
    quantity_unit,
    (
        contract_multiplier IS NOT NULL
        AND contract_multiplier > 0
        AND contract_multiplier < 'Infinity'::float8
    ) AS multiplier_present,
    metadata_source,
    effective_from,
    effective_until,
    (effective_until IS NULL) AS open_ended
FROM exchange_instrument_history
WHERE symbol = 'BTCUSDT'
  AND market_type = 'perp'
  AND exchange IN ('binance', 'bybit', 'okx')
ORDER BY exchange, effective_from

-- statement: connectivity_events
SELECT
    id,
    exchange,
    event_type,
    ts,
    detail->>'idle_seconds' AS idle_seconds_text
FROM connectivity_events
WHERE exchange IN ('binance', 'bybit', 'okx')
  AND event_type IN ('disconnect', 'restore')
  AND ts < __INTERVAL_END__ + interval '6 hours'
ORDER BY exchange, ts, id

-- statement: liquidation_capability
SELECT
    exchange,
    symbol,
    market_type,
    metric,
    live_supported,
    enabled,
    coverage_type
FROM symbol_exchange_capabilities
WHERE symbol = 'BTCUSDT'
  AND market_type = 'perp'
  AND metric = 'liquidations'
  AND exchange IN ('binance', 'bybit', 'okx')
ORDER BY exchange, symbol, market_type, metric

-- statement: coverage_grid
WITH grid AS (
    SELECT gs AS bucket_start, v.exchange
    FROM generate_series(
        __LOOKBACK_START__,
        __INTERVAL_END__ - interval '5 minutes',
        interval '5 minutes'
    ) AS gs
    CROSS JOIN (VALUES ('binance'), ('bybit'), ('okx')) AS v(exchange)
),
bar_agg AS (
    SELECT
        exchange,
        bucket_start,
        count(*) FILTER (WHERE source = 'live') AS live_bar_row_count,
        count(*) FILTER (
            WHERE source = 'live' AND ts IN (
                bucket_start,
                bucket_start + interval '1 minute',
                bucket_start + interval '2 minutes',
                bucket_start + interval '3 minutes',
                bucket_start + interval '4 minutes'
            )
        ) AS distinct_expected_live_minutes,
        count(*) FILTER (
            WHERE source = 'live' AND ts NOT IN (
                bucket_start,
                bucket_start + interval '1 minute',
                bucket_start + interval '2 minutes',
                bucket_start + interval '3 minutes',
                bucket_start + interval '4 minutes'
            )
        ) AS offslot_live_bar_count,
        min(ts) FILTER (WHERE source = 'live') AS first_live_minute_ts,
        max(ts) FILTER (WHERE source = 'live') AS last_live_minute_ts,
        bool_or(source = 'live' AND ts = bucket_start) AS first_expected_bar_present,
        bool_or(source = 'live' AND ts = bucket_start AND open = 0)
            AS first_expected_open_is_zero,
        count(*) FILTER (
            WHERE source = 'live'
              AND ts IN (
                  bucket_start,
                  bucket_start + interval '1 minute',
                  bucket_start + interval '2 minutes',
                  bucket_start + interval '3 minutes',
                  bucket_start + interval '4 minutes'
              )
              AND taker_buy_volume IS NOT NULL
              AND taker_sell_volume IS NOT NULL
        ) AS taker_split_complete_expected_minutes
    FROM (
        SELECT
            exchange,
            source,
            ts,
            open,
            taker_buy_volume,
            taker_sell_volume,
            date_bin('5 minutes', ts, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS bucket_start
        FROM klines_1m
        WHERE symbol = 'BTCUSDT'
          AND exchange IN ('binance', 'bybit', 'okx')
          AND ts >= __LOOKBACK_START__
          AND ts < __INTERVAL_END__
    ) AS bars
    GROUP BY exchange, bucket_start
),
oi_agg AS (
    SELECT
        exchange,
        bucket_start,
        count(*) FILTER (WHERE source = 'live') AS live_oi_row_count,
        count(DISTINCT ts) FILTER (WHERE source = 'live' AND usable)
            AS usable_oi_distinct_timestamps,
        (
            count(*) FILTER (WHERE source = 'live')
            - count(DISTINCT ts) FILTER (WHERE source = 'live')
        ) AS oi_duplicate_timestamp_count,
        count(DISTINCT oi_unit) FILTER (WHERE source = 'live' AND usable)
            AS oi_distinct_unit_count,
        string_agg(DISTINCT oi_unit, ',' ORDER BY oi_unit)
            FILTER (WHERE source = 'live' AND usable) AS oi_units,
        COALESCE(
            (array_agg(oi_raw ORDER BY ts) FILTER (WHERE source = 'live' AND usable))[1] = 0,
            TRUE
        ) AS first_usable_oi_is_zero_or_null,
        min(ts) FILTER (WHERE source = 'live' AND usable) AS first_usable_oi_ts,
        max(ts) FILTER (WHERE source = 'live' AND usable) AS last_usable_oi_ts
    FROM (
        SELECT
            exchange,
            source,
            ts,
            oi_raw,
            oi_unit,
            date_bin('5 minutes', ts, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS bucket_start,
            (
                oi_raw IS NOT NULL
                AND oi_unit IS NOT NULL
                AND btrim(oi_unit) <> ''
                AND oi_raw = oi_raw
                AND oi_raw > '-Infinity'::float8
                AND oi_raw < 'Infinity'::float8
            ) AS usable
        FROM open_interest
        WHERE symbol = 'BTCUSDT'
          AND exchange IN ('binance', 'bybit', 'okx')
          AND ts >= __LOOKBACK_START__
          AND ts < __INTERVAL_END__
    ) AS oi
    GROUP BY exchange, bucket_start
)
/* LIQ_BLOCK */
, liq_agg AS (
    SELECT
        exchange,
        bucket_start,
        count(*) AS liquidation_event_count,
        bool_or(side = 'long') AS liquidation_has_long,
        bool_or(side = 'short') AS liquidation_has_short
    FROM (
        SELECT
            exchange,
            side,
            date_bin('5 minutes', ts, TIMESTAMPTZ '1970-01-01 00:00:00+00') AS bucket_start
        FROM liquidations
        WHERE symbol = 'BTCUSDT'
          AND exchange IN ('binance', 'bybit', 'okx')
          AND ts >= __LOOKBACK_START__
          AND ts < __INTERVAL_END__
    ) AS liq
    GROUP BY exchange, bucket_start
)
/* END_LIQ_BLOCK */
/* PIT_BLOCK */
, pit_agg AS (
    SELECT
        g.bucket_start,
        g.exchange,
        count(h.effective_from) AS pit_row_count,
        CASE
            WHEN count(h.effective_from) = 1 THEN min(h.quantity_unit)
            ELSE NULL
        END AS pit_quantity_unit,
        CASE
            WHEN count(h.effective_from) = 1 THEN COALESCE(bool_or(
                h.contract_multiplier IS NOT NULL
                AND h.contract_multiplier > 0
                AND h.contract_multiplier < 'Infinity'::float8
            ), FALSE)
            ELSE NULL
        END AS pit_multiplier_present
    FROM grid AS g
    LEFT JOIN exchange_instrument_history AS h
      ON h.exchange = g.exchange
     AND h.symbol = 'BTCUSDT'
     AND h.market_type = 'perp'
     AND h.effective_from <= g.bucket_start
     AND (h.effective_until IS NULL OR g.bucket_start < h.effective_until)
    GROUP BY g.bucket_start, g.exchange
)
/* END_PIT_BLOCK */
-- OUTPUT_COLUMNS
SELECT
    g.bucket_start AS bucket_start,
    g.exchange AS exchange,
    COALESCE(b.live_bar_row_count, 0) AS live_bar_row_count,
    COALESCE(b.distinct_expected_live_minutes, 0) AS distinct_expected_live_minutes,
    COALESCE(b.offslot_live_bar_count, 0) AS offslot_live_bar_count,
    b.first_live_minute_ts AS first_live_minute_ts,
    b.last_live_minute_ts AS last_live_minute_ts,
    COALESCE(b.first_expected_bar_present, FALSE) AS first_expected_bar_present,
    b.first_expected_open_is_zero AS first_expected_open_is_zero,
    COALESCE(b.taker_split_complete_expected_minutes, 0)
        AS taker_split_complete_expected_minutes,
    COALESCE(o.live_oi_row_count, 0) AS live_oi_row_count,
    COALESCE(o.usable_oi_distinct_timestamps, 0) AS usable_oi_distinct_timestamps,
    COALESCE(o.oi_duplicate_timestamp_count, 0) AS oi_duplicate_timestamp_count,
    COALESCE(o.oi_distinct_unit_count, 0) AS oi_distinct_unit_count,
    o.oi_units AS oi_units,
    COALESCE(o.first_usable_oi_is_zero_or_null, TRUE) AS first_usable_oi_is_zero_or_null,
    o.first_usable_oi_ts AS first_usable_oi_ts,
    o.last_usable_oi_ts AS last_usable_oi_ts,
    __PIT_TABLE_PRESENT__ AS pit_table_present,
    CASE
        WHEN __PIT_TABLE_PRESENT__ THEN COALESCE(p.pit_row_count, 0)
        ELSE NULL
    END AS pit_row_count,
    CASE
        WHEN __PIT_TABLE_PRESENT__ THEN p.pit_quantity_unit
        ELSE NULL
    END AS pit_quantity_unit,
    CASE
        WHEN __PIT_TABLE_PRESENT__ THEN p.pit_multiplier_present
        ELSE NULL
    END AS pit_multiplier_present,
    __LIQ_TABLE_PRESENT__ AS liquidation_table_present,
    CASE
        WHEN __LIQ_TABLE_PRESENT__ THEN COALESCE(l.liquidation_event_count, 0)
        ELSE NULL
    END AS liquidation_event_count,
    CASE
        WHEN __LIQ_TABLE_PRESENT__ THEN l.liquidation_has_long
        ELSE NULL
    END AS liquidation_has_long,
    CASE
        WHEN __LIQ_TABLE_PRESENT__ THEN l.liquidation_has_short
        ELSE NULL
    END AS liquidation_has_short,
    (g.bucket_start >= __REQUESTED_START__) AS in_requested_interval
FROM grid AS g
LEFT JOIN bar_agg AS b
  ON b.exchange = g.exchange AND b.bucket_start = g.bucket_start
LEFT JOIN oi_agg AS o
  ON o.exchange = g.exchange AND o.bucket_start = g.bucket_start
LEFT JOIN liq_agg AS l
  ON l.exchange = g.exchange AND l.bucket_start = g.bucket_start
LEFT JOIN pit_agg AS p
  ON p.exchange = g.exchange AND p.bucket_start = g.bucket_start
ORDER BY g.bucket_start, g.exchange
