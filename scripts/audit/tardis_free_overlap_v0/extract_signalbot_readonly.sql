-- Read-only extraction for Tardis free overlap V0.
-- Dates: 2026-08-01 UTC and 2026-09-01 UTC, half-open [day, next day).
-- Symbol: BTCUSDT. Venues: binance, bybit, okx.
-- Kline and open-interest rows must be source = 'live'.
-- No Telegram, user, chat, or credential columns.

-- klines_1m, live bars only. ts is the 1-minute bar open.
SELECT exchange, symbol, ts, open, high, low, close, volume,
       taker_buy_volume, taker_sell_volume, trades_count, source
FROM klines_1m
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND source = 'live'
  AND (
        (ts >= TIMESTAMPTZ '2026-08-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-08-02 00:00:00+00')
     OR (ts >= TIMESTAMPTZ '2026-09-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-09-02 00:00:00+00')
      )
ORDER BY exchange, ts;

-- How many rows in the same window were excluded because source was not live.
-- Counts only. Those rows are not part of the gold file.
SELECT 'klines_1m' AS table_name, exchange, source, count(*) AS n
FROM klines_1m
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND (
        (ts >= TIMESTAMPTZ '2026-08-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-08-02 00:00:00+00')
     OR (ts >= TIMESTAMPTZ '2026-09-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-09-02 00:00:00+00')
      )
GROUP BY exchange, source
ORDER BY exchange, source;

-- open_interest. ts is the collector receive time. Live rows only.
SELECT exchange, symbol, ts, oi_raw, oi_unit, contract_value,
       oi_base_asset, oi_notional_usd, source
FROM open_interest
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND source = 'live'
  AND (
        (ts >= TIMESTAMPTZ '2026-08-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-08-02 00:00:00+00')
     OR (ts >= TIMESTAMPTZ '2026-09-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-09-02 00:00:00+00')
      )
ORDER BY exchange, ts;

SELECT 'open_interest' AS table_name, exchange, source, count(*) AS n
FROM open_interest
WHERE symbol = 'BTCUSDT'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND (
        (ts >= TIMESTAMPTZ '2026-08-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-08-02 00:00:00+00')
     OR (ts >= TIMESTAMPTZ '2026-09-01 00:00:00+00'
         AND ts <  TIMESTAMPTZ '2026-09-02 00:00:00+00')
      )
GROUP BY exchange, source
ORDER BY exchange, source;

-- PIT instrument history overlapping the two sample dates.
-- Applied as-of each bucket start. A missing OKX multiplier stays fail-closed.
SELECT exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
       contract_multiplier, tick_size, price_precision, quantity_precision,
       metadata_source, observed_at, effective_from, effective_until, note,
       accepted_metadata_revision
FROM exchange_instrument_history
WHERE symbol = 'BTCUSDT'
  AND market_type = 'perp'
  AND exchange IN ('binance', 'bybit', 'okx')
  AND effective_from < TIMESTAMPTZ '2026-09-02 00:00:00+00'
  AND (effective_until IS NULL OR effective_until > TIMESTAMPTZ '2026-08-01 00:00:00+00')
ORDER BY exchange, effective_from;

-- Current instrument row, exported for inspection only.
-- The comparison does not treat this row as a historical multiplier.
SELECT exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
       contract_multiplier, tick_size, price_precision, quantity_precision,
       metadata_source, fetched_at, is_stale, note
FROM exchange_instruments
WHERE symbol = 'BTCUSDT'
  AND market_type = 'perp'
  AND exchange IN ('binance', 'bybit', 'okx')
ORDER BY exchange;
