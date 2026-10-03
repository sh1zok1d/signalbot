-- Private Beta V0.2 post-deploy smoke check. Read-only. No schema changes.
--
-- PostgreSQL 14+ (uses date_bin). Does not read beta_episode_outcomes and does
-- not compute returns, PnL, MAE, MFE, or hit rate.
--
--   psql "$DSN" -v deploy_ts='YYYY-MM-DD HH:MM:SS+00' -f deploy/signalbot-beta-smoke.sql
-- When regime_d7.enabled is true, also pass:
--   -v d7_enabled=true -v d7_deploy_ts='YYYY-MM-DD HH:MM:SS+00'
--
-- One result set: section, status (PASS / WARN / FAIL), detail.
-- Any FAIL is an operational stop. HISTORY BUILDING is not a failure.
-- A measured liquidation zero is not a failure. Repeated full 5m buckets with
-- fewer than 2 live OI observations are a Day-0 blocker; do not wait 30 days.
--
-- Push rows that belong to an episode with a TRIGGERED transition are detector
-- decisions. A readiness change in the same bucket is not, by itself, a push.

\if :{?deploy_ts}
\else
\echo deploy_ts is required: psql -v deploy_ts='YYYY-MM-DD HH:MM:SS+00' -f deploy/signalbot-beta-smoke.sql
\quit 1
\endif

\if :{?d7_enabled}
\else
\set d7_enabled false
\endif

\if :{?d7_deploy_ts}
\else
\set d7_deploy_ts ''
\endif

\set ON_ERROR_STOP on
\pset pager off

BEGIN TRANSACTION READ ONLY;

WITH
params AS (
    SELECT :'deploy_ts'::timestamptz AS deploy_ts,
           now() AS as_of,
           2 AS schema_version,
           '9e9d2c631a1abfdb710dc2147835b3a0ccd4620512d3a0d6828140c96de17210' AS rules_digest,
           'BETA_CONTEXT_1H_V2' AS context_version,
            '68ec9dbdb87ad4505d3b000dbc695ec7ff73b638edf9b7624d6acf98c8d63f25' AS context_digest,
           :'d7_enabled'::boolean AS d7_enabled,
           CASE
                WHEN :'d7_enabled'::boolean
                    THEN NULLIF(:'d7_deploy_ts', '')::timestamptz
                ELSE NULL
            END AS d7_deploy_ts,
           420::double precision AS max_lag_s
),
bounds AS (
    SELECT p.*,
           CASE
               WHEN date_bin('5 minutes', p.deploy_ts, TIMESTAMPTZ '2000-01-01 00:00:00+00') = p.deploy_ts
                   THEN p.deploy_ts
               ELSE date_bin('5 minutes', p.deploy_ts, TIMESTAMPTZ '2000-01-01 00:00:00+00')
                    + interval '5 minutes'
           END AS first_full_bucket,
           date_bin('5 minutes', p.as_of, TIMESTAMPTZ '2000-01-01 00:00:00+00')
               - interval '5 minutes' AS last_closed_bucket
    FROM params p
),
venues AS (
    SELECT unnest(ARRAY['binance', 'bybit', 'okx']) AS exchange
),
liq_fields AS (
    SELECT unnest(ARRAY['long_liquidation_notional', 'short_liquidation_notional']) AS field
),
expected_buckets AS (
    SELECT gs AS bucket_ts
    FROM bounds b
    JOIN LATERAL generate_series(b.first_full_bucket, b.last_closed_bucket, interval '5 minutes') AS gs
        ON b.first_full_bucket <= b.last_closed_bucket
),
a_rows AS (
    SELECT t.*
    FROM beta_state_tape t
    JOIN bounds b ON t.evaluated_at >= b.deploy_ts
    WHERE t.origin = 'LIVE'
      AND t.symbol = 'BTCUSDT'
      AND t.market_type = 'perp'
      AND t.timeframe = '5m'
      AND t.bucket_ts + interval '5 minutes' > b.deploy_ts
),
written AS (
    SELECT DISTINCT a.bucket_ts
    FROM a_rows a
    JOIN params p ON a.state_schema_version = p.schema_version
                 AND a.rules_digest = p.rules_digest
),
missing AS (
    SELECT e.bucket_ts
    FROM expected_buckets e
    LEFT JOIN written w ON w.bucket_ts = e.bucket_ts
    JOIN bounds b ON TRUE
    WHERE w.bucket_ts IS NULL
),
tape_shape AS (
    SELECT a.tape_id, a.bucket_ts,
           (a.state_schema_version = p.schema_version) AS schema_ok,
           (a.rules_digest = p.rules_digest) AS digest_ok,
           a.materialized,
           a.evaluation_fresh,
           (a.snapshot->>'evaluation_lag_s')::double precision AS lag_s,
           (
               a.snapshot ? 'venue_raw'
               AND a.snapshot->'venues' ? 'binance'
               AND a.snapshot->'venues' ? 'bybit'
               AND a.snapshot->'venues' ? 'okx'
               AND a.snapshot->'venue_raw' ? 'binance'
               AND a.snapshot->'venue_raw' ? 'bybit'
               AND a.snapshot->'venue_raw' ? 'okx'
           ) AS venue_objects_ok
    FROM a_rows a
    CROSS JOIN params p
),
field_gaps AS (
    SELECT a.tape_id, v.exchange
    FROM a_rows a
    CROSS JOIN venues v
    WHERE a.state_schema_version = (SELECT schema_version FROM params)
      AND (
          NOT COALESCE(a.snapshot->'venue_raw'->v.exchange ? 'price_move_pct', FALSE)
          OR NOT COALESCE(a.snapshot->'venue_raw'->v.exchange ? 'oi_change_pct', FALSE)
          OR NOT COALESCE(a.snapshot->'venue_raw'->v.exchange ? 'range_width_pct', FALSE)
          OR NOT COALESCE(a.snapshot->'venue_raw'->v.exchange ? 'volume_notional_usd', FALSE)
          OR NOT COALESCE(a.snapshot->'venue_raw'->v.exchange ? 'taker_delta_notional_usd', FALSE)
          OR NOT COALESCE(a.snapshot->'venues'->v.exchange ? 'ohlc', FALSE)
          OR NOT COALESCE(a.snapshot->'venues'->v.exchange->'ohlc' ? 'open', FALSE)
          OR NOT COALESCE(a.snapshot->'venues'->v.exchange->'ohlc' ? 'high', FALSE)
          OR NOT COALESCE(a.snapshot->'venues'->v.exchange->'ohlc' ? 'low', FALSE)
          OR NOT COALESCE(a.snapshot->'venues'->v.exchange->'ohlc' ? 'close', FALSE)
          OR NOT COALESCE(a.snapshot->'metrics' ? ('x:' || v.exchange || ':kline_open'), FALSE)
          OR NOT COALESCE(a.snapshot->'metrics' ? ('x:' || v.exchange || ':kline_high'), FALSE)
          OR NOT COALESCE(a.snapshot->'metrics' ? ('x:' || v.exchange || ':kline_low'), FALSE)
          OR NOT COALESCE(a.snapshot->'metrics' ? ('x:' || v.exchange || ':kline_close'), FALSE)
      )
),
oi_pts AS (
    SELECT o.exchange,
           date_bin('5 minutes', o.ts, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS bucket_ts,
           o.ts, o.oi_raw, o.oi_unit
    FROM open_interest o
    JOIN bounds b ON o.ts >= b.first_full_bucket AND o.ts < b.as_of
    WHERE o.symbol = 'BTCUSDT'
      AND o.source = 'live'
      AND o.exchange IN ('binance', 'bybit', 'okx')
      AND o.oi_raw IS NOT NULL
      AND o.oi_unit IS NOT NULL
),
oi_bucket AS (
    SELECT exchange, bucket_ts,
           count(DISTINCT ts) AS n,
           count(DISTINCT oi_unit) AS n_units,
           (array_agg(oi_raw ORDER BY ts))[1] AS oi_first
    FROM oi_pts
    GROUP BY exchange, bucket_ts
),
oi_full AS (
    SELECT v.exchange, e.bucket_ts, COALESCE(ob.n, 0) AS n,
           ob.n_units, ob.oi_first
    FROM venues v
    CROSS JOIN expected_buckets e
    LEFT JOIN oi_bucket ob ON ob.exchange = v.exchange AND ob.bucket_ts = e.bucket_ts
),
oi_stats AS (
    SELECT exchange,
           count(*) AS buckets,
           min(n) AS min_n,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY n) AS median_n,
           max(n) AS max_n,
           count(*) FILTER (WHERE n < 2) AS below_2,
           avg((n >= 2)::int)::double precision AS pct_ge_2
    FROM oi_full
    GROUP BY exchange
),
tape_bucket AS (
    SELECT DISTINCT ON (bucket_ts) bucket_ts, snapshot, materialized
    FROM a_rows
    WHERE state_schema_version = (SELECT schema_version FROM params)
      AND rules_digest = (SELECT rules_digest FROM params)
    ORDER BY bucket_ts, tape_id DESC
),
oi_null_where_expected AS (
    SELECT ob.exchange, count(*) AS n,
           min(ob.bucket_ts) AS first_bucket
    FROM oi_bucket ob
    JOIN expected_buckets e ON e.bucket_ts = ob.bucket_ts
    JOIN tape_bucket t ON t.bucket_ts = ob.bucket_ts
    WHERE ob.n >= 2
      AND ob.n_units = 1
      AND ob.oi_first <> 0
      AND t.materialized
      AND (t.snapshot->'venue_raw'->ob.exchange->>'oi_change_pct') IS NULL
    GROUP BY ob.exchange
),
latest AS (
    SELECT a.*
    FROM a_rows a
    ORDER BY a.bucket_ts DESC, a.tape_id DESC
    LIMIT 1
),
kline_bucket AS (
    SELECT k.exchange,
           date_bin('5 minutes', k.ts, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS bucket_ts,
           count(*) AS bars,
           count(*) FILTER (
               WHERE k.open IS NOT NULL AND k.high IS NOT NULL
                 AND k.low IS NOT NULL AND k.close IS NOT NULL
           ) AS ohlc_bars,
           count(*) FILTER (
               WHERE k.taker_buy_volume IS NOT NULL AND k.taker_sell_volume IS NOT NULL
           ) AS taker_bars,
           count(*) FILTER (
               WHERE k.taker_buy_volume IS NOT NULL AND k.taker_sell_volume IS NOT NULL
                 AND k.taker_buy_volume <> k.taker_sell_volume
           ) AS nonzero_bars
    FROM klines_1m k
    JOIN bounds b ON k.ts >= b.first_full_bucket AND k.ts < b.as_of
    JOIN expected_buckets e
      ON e.bucket_ts = date_bin('5 minutes', k.ts, TIMESTAMPTZ '2000-01-01 00:00:00+00')
    WHERE k.symbol = 'BTCUSDT'
      AND k.source = 'live'
      AND k.exchange IN ('binance', 'bybit', 'okx')
    GROUP BY k.exchange, 2
),
kline_stats AS (
    SELECT v.exchange,
           (SELECT count(*) FROM expected_buckets) AS expected_buckets,
           count(kb.bucket_ts) AS buckets_with_bars,
           COALESCE(sum(kb.bars), 0) AS bars,
           COALESCE(sum(kb.ohlc_bars), 0) AS ohlc_bars,
           COALESCE(sum(kb.taker_bars), 0) AS taker_bars,
           COALESCE(sum(kb.nonzero_bars), 0) AS nonzero_bars,
           count(*) FILTER (WHERE kb.ohlc_bars = 5) AS full_ohlc_buckets
    FROM venues v
    LEFT JOIN kline_bucket kb ON kb.exchange = v.exchange
    GROUP BY v.exchange
),
taker_gap AS (
    SELECT count(*) AS n
    FROM a_rows a
    WHERE a.materialized
      AND a.snapshot->'families'->'taker_flow'->>'usable' = 'true'
      AND (a.snapshot->'metrics'->>'c:taker_delta_notional_usd_sum') IS NULL
),
taker_present AS (
    SELECT count(*) AS n
    FROM a_rows a
    WHERE a.materialized
      AND (a.snapshot->'metrics'->>'c:taker_delta_notional_usd_sum') IS NOT NULL
),
liq_class AS (
    SELECT v.exchange,
           f.field,
           CASE
               WHEN COALESCE(a.snapshot->'venues'->v.exchange->>'declared_available', '') = 'true'
                AND COALESCE(a.snapshot->'venues'->v.exchange->>'heartbeat_healthy', '') = 'true'
                   THEN TRUE
               ELSE FALSE
           END AS eligible,
           jsonb_typeof(a.snapshot->'metrics'->('x:' || v.exchange || ':' || f.field)) AS kind,
           CASE
               WHEN jsonb_typeof(a.snapshot->'metrics'->('x:' || v.exchange || ':' || f.field)) = 'number'
                   THEN (a.snapshot->'metrics'->>('x:' || v.exchange || ':' || f.field))::double precision
           END AS measured
    FROM a_rows a
    CROSS JOIN venues v
    CROSS JOIN liq_fields f
    WHERE a.state_schema_version = (SELECT schema_version FROM params)
),
liq_counts AS (
    SELECT exchange,
           count(*) FILTER (
               WHERE NOT eligible AND kind = 'number'
           ) AS numeric_on_ineligible,
           count(*) FILTER (
               WHERE eligible AND COALESCE(kind, 'null') = 'null'
           ) AS null_on_eligible,
           count(*) FILTER (
               WHERE eligible AND kind = 'number' AND measured = 0
           ) AS measured_zero,
           count(*) FILTER (
               WHERE eligible AND kind = 'number' AND measured <> 0
           ) AS measured_value,
           count(*) FILTER (
               WHERE NOT eligible AND COALESCE(kind, 'null') = 'null'
           ) AS unknown_on_ineligible,
           count(*) FILTER (WHERE eligible) AS eligible_cells
    FROM liq_class
    GROUP BY exchange
),
liq_events AS (
    SELECT v.exchange, count(l.id) AS n
    FROM venues v
    LEFT JOIN liquidations l
      ON l.exchange = v.exchange
     AND l.symbol = 'BTCUSDT'
     AND l.ts >= (SELECT deploy_ts FROM bounds)
     AND l.ts < (SELECT as_of FROM bounds)
    GROUP BY v.exchange
),
hb AS (
    SELECT v.exchange,
           count(a.tape_id) AS rows_n,
           avg((
               COALESCE(a.snapshot->'venues'->v.exchange->>'heartbeat_healthy', '') = 'true'
           )::int)::double precision AS healthy_rate
    FROM venues v
    LEFT JOIN a_rows a
      ON a.state_schema_version = (SELECT schema_version FROM params)
    GROUP BY v.exchange
),
views AS (
    SELECT v.*
    FROM beta_btc_views v
    JOIN bounds b ON v.requested_at >= b.deploy_ts
),
view_flags AS (
    SELECT
        count(*) AS n,
        count(*) FILTER (
            WHERE payload->>'headline' = 'NO ACTIVE EVENTS'
              AND COALESCE(payload->'readiness'->>'core_ready', 'false') <> 'true'
        ) AS false_no_active,
        count(*) FILTER (
            WHERE payload->>'product_status' IN ('DATA STALE', 'DATA DEGRADED', 'WATCH', 'EVENT ACTIVE')
              AND payload->>'headline' IS DISTINCT FROM payload->>'product_status'
        ) AS precedence_breaks
    FROM views
),
view_headlines AS (
    SELECT COALESCE(string_agg(headline || '=' || n::text, ', ' ORDER BY headline), '(none)') AS summary
    FROM (
        SELECT payload->>'headline' AS headline, count(*) AS n
        FROM views
        GROUP BY 1
    ) s
),
view_groups AS (
    SELECT COALESCE(string_agg(grp || ' ' || status || '=' || n::text, ', ' ORDER BY grp, status), '(none)') AS summary
    FROM (
        SELECT g->>'group' AS grp, g->>'status' AS status, count(*) AS n
        FROM views v
        CROSS JOIN LATERAL jsonb_array_elements(COALESCE(v.payload->'readiness'->'groups', '[]'::jsonb)) g
        GROUP BY 1, 2
    ) s
),
push_decisions AS (
    SELECT p.*
    FROM beta_push_decisions p
    JOIN bounds b ON p.recorded_at >= b.deploy_ts
),
push_orphan AS (
    SELECT count(*) AS n
    FROM push_decisions p
    WHERE NOT EXISTS (
        SELECT 1 FROM beta_episode_transitions t
        WHERE t.episode_pk = p.episode_pk AND t.to_state = 'TRIGGERED'
    )
),
push_triggered AS (
    SELECT count(*) AS n
    FROM push_decisions p
    WHERE EXISTS (
        SELECT 1 FROM beta_episode_transitions t
        WHERE t.episode_pk = p.episode_pk AND t.to_state = 'TRIGGERED'
    )
),
delivery_without_push AS (
    SELECT count(*) AS n
    FROM beta_notification_deliveries d
    JOIN bounds b ON d.created_at >= b.deploy_ts
    WHERE NOT EXISTS (
        SELECT 1 FROM beta_push_decisions p
        WHERE p.decision_id = d.decision_id AND p.decision = 'PUSH'
    )
),
sent_while_disabled AS (
    SELECT count(*) AS n
    FROM beta_notification_deliveries d
    JOIN bounds b ON d.created_at >= b.deploy_ts
    JOIN beta_push_decisions p ON p.decision_id = d.decision_id
    WHERE d.state = 'SENT'
      AND p.push_enabled_effective IS NOT TRUE
),
context_gaps AS (
    SELECT w.bucket_ts
    FROM written w
    CROSS JOIN params p
    WHERE NOT EXISTS (
        SELECT 1 FROM beta_context_snapshots c
        WHERE c.symbol = 'BTCUSDT'
          AND c.bucket_ts = w.bucket_ts
          AND c.context_version = p.context_version
          AND c.context_digest = p.context_digest
    )
),
d7_complete AS (
    SELECT date_bin('1 hour', k.open_time, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS hour_start
    FROM beta_d7_klines_1m k
    CROSS JOIN params p
    WHERE p.d7_enabled
      AND p.d7_deploy_ts IS NOT NULL
      AND k.open_time >= date_bin('1 hour', p.d7_deploy_ts, TIMESTAMPTZ '2000-01-01 00:00:00+00')
      AND k.open_time < date_bin('1 hour', p.as_of, TIMESTAMPTZ '2000-01-01 00:00:00+00')
    GROUP BY 1
    HAVING count(*) = 60
),
d7_missing AS (
    SELECT c.hour_start
    FROM d7_complete c
    WHERE NOT EXISTS (
        SELECT 1 FROM beta_d7_hour_states s WHERE s.hour_start = c.hour_start
    )
),
-- Stage-1 startup recovery (common.startup_recovery): the newest readiness row,
-- and decided buckets whose raw 1m bars arrived after the bucket was decided
-- ("raw recovered, tape still stale"). Window: deploy_ts - 24h .. last closed bucket.
recovery_run AS (
    SELECT r.id, r.status, r.started_at, r.finished_at, r.note
    FROM backfill_runs r
    WHERE r.source = 'startup_recovery' AND r.exchange = '*' AND r.symbol = 'BTCUSDT'
    ORDER BY r.id DESC
    LIMIT 1
),
decided_bucket AS (
    SELECT DISTINCT ON (t.bucket_ts) t.bucket_ts, t.snapshot
    FROM beta_state_tape t
    JOIN bounds b ON t.bucket_ts >= b.deploy_ts - interval '24 hours'
                 AND t.bucket_ts <= b.last_closed_bucket
    WHERE t.symbol = 'BTCUSDT'
      AND t.market_type = 'perp'
      AND t.timeframe = '5m'
      AND t.origin IN ('LIVE', 'CORRECTION_CHECK')
      AND t.state_schema_version = (SELECT schema_version FROM params)
      AND t.rules_digest = (SELECT rules_digest FROM params)
    ORDER BY t.bucket_ts, t.tape_id DESC
),
raw_bucket AS (
    SELECT k.exchange,
           date_bin('5 minutes', k.ts, TIMESTAMPTZ '2000-01-01 00:00:00+00') AS bucket_ts,
           count(*) AS bars
    FROM klines_1m k
    JOIN bounds b ON k.ts >= b.deploy_ts - interval '24 hours' AND k.ts < b.as_of
    WHERE k.symbol = 'BTCUSDT'
      AND k.exchange IN ('binance', 'bybit', 'okx')
    GROUP BY 1, 2
),
stale_after_raw AS (
    SELECT d.bucket_ts, v.exchange,
           COALESCE((d.snapshot->'venues'->v.exchange->>'bars')::int, 0) AS stored_bars,
           r.bars AS raw_bars
    FROM decided_bucket d
    CROSS JOIN venues v
    JOIN raw_bucket r ON r.exchange = v.exchange AND r.bucket_ts = d.bucket_ts
    WHERE r.bars > COALESCE((d.snapshot->'venues'->v.exchange->>'bars')::int, 0)
),
checks AS (
    SELECT '0. window'::text AS section, 'PASS'::text AS status,
           format('deploy_ts=%s as_of=%s transaction=READ ONLY', deploy_ts, as_of) AS detail
    FROM bounds

    UNION ALL
    SELECT 'A. V2 tape identity',
           CASE WHEN (SELECT count(*) FROM a_rows) = 0 THEN 'FAIL' ELSE 'PASS' END,
           format('LIVE rows after deploy whose bucket had not closed before deploy_ts: %s',
                  (SELECT count(*) FROM a_rows))

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('state_schema_version <> 2 on %s LIVE row(s)', count(*))
    FROM tape_shape
    WHERE NOT schema_ok
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('rules_digest is not the V2 digest on %s LIVE row(s)', count(*))
    FROM tape_shape
    WHERE NOT digest_ok
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('materialized=false on %s LIVE row(s)', count(*))
    FROM tape_shape
    WHERE NOT materialized
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('evaluation_fresh=false on %s LIVE row(s)', count(*))
    FROM tape_shape
    WHERE NOT evaluation_fresh
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('evaluation_lag_s > 420 or missing on %s LIVE row(s); max lag=%s',
                  count(*), max(lag_s))
    FROM tape_shape
    CROSS JOIN params p
    WHERE lag_s IS NULL OR lag_s > p.max_lag_s
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('V2 venue_raw/OHLC objects missing on %s LIVE row(s)', count(*))
    FROM tape_shape
    WHERE schema_ok AND NOT venue_objects_ok
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity', 'FAIL',
           format('V2 venue_raw or kline OHLC field missing on %s venue-row(s)', count(*))
    FROM field_gaps
    HAVING count(*) > 0

    UNION ALL
    SELECT 'A. V2 tape identity',
           CASE
               WHEN (SELECT count(*) FROM expected_buckets) = 0 THEN 'WARN'
               WHEN (SELECT count(*) FROM missing m JOIN bounds b ON m.bucket_ts + interval '5 minutes' + interval '90 seconds' <= b.as_of) > 0
                   THEN 'FAIL'
               WHEN (SELECT count(*) FROM missing) > 0 THEN 'WARN'
               ELSE 'PASS'
           END,
           format('expected full 5m buckets=%s written V2=%s missing=%s missing_sample=%s',
                  (SELECT count(*) FROM expected_buckets),
                  (SELECT count(*) FROM written w JOIN expected_buckets e ON e.bucket_ts = w.bucket_ts),
                  (SELECT count(*) FROM missing),
                  COALESCE((SELECT string_agg(bucket_ts::text, ', ' ORDER BY bucket_ts)
                            FROM (SELECT bucket_ts FROM missing ORDER BY bucket_ts LIMIT 8) s), '(none)'))

    UNION ALL
    SELECT 'A. V2 tape identity',
           CASE WHEN n = 0 THEN 'PASS' ELSE 'WARN' END,
           format('revised rows (revision>=2) after deploy=%s; a correction append is reported for review and is not itself an identity mismatch', n)
    FROM (
        SELECT count(*) AS n
        FROM beta_state_tape t
        JOIN bounds b ON t.evaluated_at >= b.deploy_ts
        WHERE t.revision >= 2
    ) s

    UNION ALL
    SELECT 'A. V2 tape identity',
           CASE WHEN n = 0 THEN 'PASS' ELSE 'WARN' END,
           format('LIVE buckets with more than one row=%s', n)
    FROM (
        SELECT count(*) AS n FROM (
            SELECT bucket_ts FROM a_rows GROUP BY bucket_ts HAVING count(*) > 1
        ) d
    ) s

    UNION ALL
    SELECT 'A. V2 tape identity',
           CASE WHEN n = 0 THEN 'WARN' ELSE 'PASS' END,
           format('materialized_rate=%s evaluation_fresh_rate=%s over %s LIVE row(s)',
                  round(mat::numeric, 4), round(fresh::numeric, 4), n)
    FROM (
        SELECT count(*) AS n,
               COALESCE(avg(materialized::int), 0)::double precision AS mat,
               COALESCE(avg(evaluation_fresh::int), 0)::double precision AS fresh
        FROM a_rows
    ) s

    UNION ALL
    SELECT 'B. OI live sampling',
           CASE
               WHEN (SELECT count(*) FROM expected_buckets) = 0 THEN 'WARN'
               WHEN COALESCE((SELECT bool_or(below_2 > 0) FROM oi_stats), FALSE) THEN 'FAIL'
               WHEN COALESCE((SELECT bool_or(median_n < 10) FROM oi_stats), FALSE) THEN 'WARN'
               ELSE 'PASS'
           END,
           CASE
               WHEN (SELECT count(*) FROM expected_buckets) = 0
                   THEN 'no fully closed 5m bucket since deploy_ts; live OI gate not scored yet'
               ELSE 'per venue min/median/max live OI observations and buckets with <2. '
                    || 'Hard gate is >=2. About 20/bucket is what 15s polling produces. '
                    || COALESCE((
                        SELECT string_agg(format('%s min=%s median=%s max=%s below2=%s pct_ge_2=%s',
                                                 exchange, min_n, round(median_n::numeric, 2), max_n,
                                                 below_2, round((pct_ge_2 * 100)::numeric, 1) || '%'),
                                          '; ' ORDER BY exchange)
                        FROM oi_stats
                    ), 'no venue stats')
           END

    UNION ALL
    SELECT 'B. OI live sampling',
           CASE WHEN COALESCE((SELECT sum(n) FROM oi_null_where_expected), 0) = 0 THEN 'PASS' ELSE 'FAIL' END,
           format('venue_raw oi_change_pct null where >=2 same-unit live observations and oi_first<>0: %s',
                  COALESCE((
                      SELECT string_agg(format('%s=%s first=%s', exchange, n, first_bucket), ', ' ORDER BY exchange)
                      FROM oi_null_where_expected
                  ), 'none'))

    UNION ALL
    SELECT 'B. OI live sampling',
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM latest) THEN 'WARN'
               WHEN (SELECT snapshot->'families'->'oi'->>'usable' FROM latest) = 'true' THEN 'PASS'
               ELSE 'WARN'
           END,
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM latest)
                   THEN 'no LIVE tape row yet; OI family usability not available'
               ELSE format('latest bucket %s OI family usable=%s available=%s expected=%s (immature percentiles are warm-up, not this gate)',
                           (SELECT bucket_ts FROM latest),
                           (SELECT snapshot->'families'->'oi'->>'usable' FROM latest),
                           (SELECT snapshot->'families'->'oi'->>'available' FROM latest),
                           (SELECT snapshot->'families'->'oi'->>'expected' FROM latest))
           END

    UNION ALL
    SELECT 'C. Taker flow',
           CASE
               WHEN (SELECT count(*) FROM expected_buckets) = 0 THEN 'WARN'
               WHEN COALESCE((SELECT bool_or(bars = 0) FROM kline_stats), TRUE) THEN 'FAIL'
               WHEN COALESCE((SELECT bool_or(taker_bars = 0) FROM kline_stats), TRUE) THEN 'FAIL'
               WHEN COALESCE((SELECT bool_or(full_ohlc_buckets < expected_buckets) FROM kline_stats), FALSE) THEN 'WARN'
               WHEN COALESCE((SELECT bool_or(nonzero_bars = 0) FROM kline_stats), FALSE) THEN 'WARN'
               ELSE 'PASS'
           END,
           COALESCE((
               SELECT string_agg(format('%s live_1m=%s ohlc_bars=%s full_ohlc_buckets=%s/%s taker_bars=%s nonzero_signed=%s',
                                        exchange, bars, ohlc_bars, full_ohlc_buckets, expected_buckets,
                                        taker_bars, nonzero_bars),
                                 '; ' ORDER BY exchange)
               FROM kline_stats
           ), 'no kline stats')

    UNION ALL
    SELECT 'C. Taker flow',
           CASE WHEN n > 0 THEN 'FAIL' ELSE 'PASS' END,
           format('materialized rows with usable taker family and null c:taker_delta_notional_usd_sum=%s; rows with consensus taker delta present=%s',
                  n, (SELECT n FROM taker_present))
    FROM taker_gap

    UNION ALL
    SELECT 'C. Taker flow',
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM latest) THEN 'WARN'
               WHEN (SELECT snapshot->'families'->'taker_flow'->>'usable' FROM latest) = 'true' THEN 'PASS'
               ELSE 'WARN'
           END,
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM latest) THEN 'no LIVE tape row yet; taker family usability not available'
               ELSE format('latest bucket %s taker_flow usable=%s available=%s expected=%s',
                           (SELECT bucket_ts FROM latest),
                           (SELECT snapshot->'families'->'taker_flow'->>'usable' FROM latest),
                           (SELECT snapshot->'families'->'taker_flow'->>'available' FROM latest),
                           (SELECT snapshot->'families'->'taker_flow'->>'expected' FROM latest))
           END

    UNION ALL
    SELECT 'D. Liquidations',
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM a_rows) THEN 'WARN'
               WHEN COALESCE((SELECT sum(numeric_on_ineligible + null_on_eligible) FROM liq_counts), 0) > 0
                   THEN 'FAIL'
               ELSE 'PASS'
           END,
           CASE
               WHEN NOT EXISTS (SELECT 1 FROM a_rows)
                   THEN 'no LIVE tape row; UNKNOWN vs measured-zero not scored'
               ELSE COALESCE((
                   SELECT string_agg(format('%s eligible_cells=%s unknown_on_ineligible=%s measured_zero=%s measured_value=%s numeric_on_ineligible=%s null_on_eligible=%s',
                                            exchange, eligible_cells, unknown_on_ineligible, measured_zero,
                                            measured_value, numeric_on_ineligible, null_on_eligible),
                                     '; ' ORDER BY exchange)
                   FROM liq_counts
               ), 'no liquidation cells')
               || '. A measured zero is not a failure. NULL on an ineligible venue is UNKNOWN.'
           END

    UNION ALL
    SELECT 'D. Liquidations',
           CASE WHEN COALESCE(sum(n), 0) = 0 THEN 'WARN' ELSE 'PASS' END,
           format('liquidation-source rows since deploy_ts: %s. No rows means the window was quiet; a 5m measured zero is still not a failure. %s',
                  COALESCE(sum(n), 0),
                  COALESCE(string_agg(format('%s=%s', exchange, n), ', ' ORDER BY exchange), ''))
    FROM liq_events

    UNION ALL
    SELECT 'D. Liquidations',
           CASE
               WHEN rows_n = 0 THEN 'WARN'
               WHEN healthy_rate < 1 THEN 'WARN'
               ELSE 'PASS'
           END,
           format('%s heartbeat_healthy_rate=%s over %s V2 LIVE row(s)',
                  exchange, round(COALESCE(healthy_rate, 0)::numeric, 4), rows_n)
    FROM hb

    UNION ALL
    SELECT 'E. /btc rendered views',
           CASE
               WHEN n = 0 THEN 'WARN'
               WHEN false_no_active > 0 OR precedence_breaks > 0 THEN 'FAIL'
               ELSE 'PASS'
           END,
           format('renders=%s false_NO_ACTIVE_EVENTS_while_price_oi_not_ready=%s stale_or_active_precedence_breaks=%s headlines=%s',
                  n, false_no_active, precedence_breaks, (SELECT summary FROM view_headlines))
    FROM view_flags

    UNION ALL
    SELECT 'E. /btc rendered views',
           CASE WHEN (SELECT n FROM view_flags) = 0 THEN 'WARN' ELSE 'PASS' END,
           format('readiness group counts from recorded /btc payloads: %s', summary)
    FROM view_groups

    UNION ALL
    SELECT 'F. Push safety',
           CASE WHEN n > 0 THEN 'FAIL' ELSE 'PASS' END,
           format('deliveries after deploy_ts with no decision=PUSH row=%s', n)
    FROM delivery_without_push

    UNION ALL
    SELECT 'F. Push safety',
           CASE WHEN n > 0 THEN 'FAIL' ELSE 'PASS' END,
           format('SENT deliveries whose push decision has push_enabled_effective=false=%s', n)
    FROM sent_while_disabled

    UNION ALL
    SELECT 'F. Push safety',
           CASE WHEN n > 0 THEN 'FAIL' ELSE 'PASS' END,
           format('push decisions after deploy_ts with no TRIGGERED episode transition=%s. Decisions that join a TRIGGERED transition are detector events and are not counted here, including when /btc readiness changed in the same bucket.', n)
    FROM push_orphan

    UNION ALL
    SELECT 'F. Push safety', 'PASS',
           format('push decisions joined to a TRIGGERED episode transition=%s (detector events; not readiness-only)', n)
    FROM push_triggered

    UNION ALL
    SELECT 'G. Context coverage',
           CASE WHEN (SELECT count(*) FROM context_gaps) > 0 THEN 'FAIL' ELSE 'PASS' END,
           format('LIVE V2 tape buckets in the smoke window with no %s snapshot=%s',
                  (SELECT context_version FROM params),
                  (SELECT count(*) FROM context_gaps))

    UNION ALL
    SELECT 'H. D7 hour states',
           CASE
               WHEN NOT (SELECT d7_enabled FROM params) THEN 'PASS'
               WHEN (SELECT d7_deploy_ts FROM params) IS NULL THEN 'FAIL'
               WHEN (SELECT count(*) FROM d7_missing) > 0 THEN 'FAIL'
               ELSE 'PASS'
           END,
           CASE
               WHEN NOT (SELECT d7_enabled FROM params)
                   THEN 'D7 disabled; hour-state coverage not required'
               WHEN (SELECT d7_deploy_ts FROM params) IS NULL
                   THEN 'd7_enabled is true and d7_deploy_ts is missing'
               ELSE format('complete hours since d7_deploy_ts=%s missing hour states=%s',
                           (SELECT count(*) FROM d7_complete),
                           (SELECT count(*) FROM d7_missing))
           END

    UNION ALL
    SELECT 'I. Startup recovery',
           CASE
               WHEN r.id IS NULL THEN 'WARN'
               WHEN r.status = 'complete' THEN 'PASS'
               WHEN r.status = 'partial' THEN 'WARN'
               WHEN r.status = 'running' AND p.as_of - r.started_at < interval '60 minutes' THEN 'WARN'
               ELSE 'FAIL'
           END,
           CASE
               WHEN r.id IS NULL
                   THEN 'no Stage-1 startup_recovery row: Stage-1 predates the readiness signal, the detector does not wait'
               ELSE format('newest Stage-1 startup recovery run=%s status=%s started=%s finished=%s %s',
                           r.id, r.status, r.started_at, COALESCE(r.finished_at::text, '-'),
                           COALESCE(r.note, ''))
           END
    FROM params p
    LEFT JOIN recovery_run r ON TRUE

    UNION ALL
    SELECT 'I. Startup recovery',
           CASE
               WHEN count(*) = 0 THEN 'PASS'
               WHEN count(*) FILTER (WHERE stored_bars = 0) > 0 THEN 'FAIL'
               ELSE 'WARN'
           END,
           CASE
               WHEN count(*) = 0
                   THEN 'raw recovered, tape stale: none (no decided bucket has fewer bars than raw now holds)'
               ELSE format('raw recovered, tape stale: buckets=%s venue-buckets=%s with no stored bar=%s first=%s last=%s (runbook: startup recovery)',
                           count(DISTINCT bucket_ts), count(*), count(*) FILTER (WHERE stored_bars = 0),
                           min(bucket_ts), max(bucket_ts))
           END
    FROM stale_after_raw
),
rollup AS (
    SELECT 'Z. rollup'::text AS section,
           CASE
               WHEN count(*) FILTER (WHERE status = 'FAIL') > 0 THEN 'FAIL'
               WHEN count(*) FILTER (WHERE status = 'WARN') > 0 THEN 'WARN'
               ELSE 'PASS'
           END AS status,
           format('FAIL=%s WARN=%s PASS=%s',
                  count(*) FILTER (WHERE status = 'FAIL'),
                  count(*) FILTER (WHERE status = 'WARN'),
                  count(*) FILTER (WHERE status = 'PASS')) AS detail
    FROM checks
)
SELECT section, status, detail
FROM (
    SELECT section, status, detail FROM checks
    UNION ALL
    SELECT section, status, detail FROM rollup
) reported
ORDER BY section, CASE status WHEN 'FAIL' THEN 0 WHEN 'WARN' THEN 1 ELSE 2 END, detail;

COMMIT;
