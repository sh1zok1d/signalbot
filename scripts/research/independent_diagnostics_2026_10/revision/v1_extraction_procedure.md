# Forecast V1 shadow data — read-only extraction procedure (VPS)

Scope: BTCUSDT / perp / 5m shadow predictions written by `analytics/forecasting/*`
(`rule_version = 'forecast-rules-v0.1.0'`, `outcome_version = 'forecast-outcome-v0.1.0'`,
`model_family = 'v1'`), window **2026-07-25 .. 2026-08-26 UTC**, plus the 5m
`consensus_feature_vectors` rows for the same window.

Everything below is **read-only**: `PGOPTIONS='-c default_transaction_read_only=on'`
on the session (the pattern already used in `docs/BETA_AUDIT_DEIDENTIFY_V1.md`), an
explicit `BEGIN TRANSACTION READ ONLY`, `SET LOCAL statement_timeout` /
`lock_timeout`, `COPY (...) TO STDOUT` (no server-side file, no `TO PROGRAM`), and
`ROLLBACK` at the end. Plain `SELECT`/`COPY TO STDOUT` take only `ACCESS SHARE`
locks; the ingestion service and the beta timers are not blocked. No secret is
needed: inside the container `psql -U btcbot` authenticates over the unix socket
exactly as `deploy/backup.sh` does for `pg_dump`.

## 0. Names (from the deploy docs — never from `.env` contents)

| Item | Value | Source |
|---|---|---|
| Postgres container | `btcbot_timescaledb` | `docker-compose.yml` `container_name` |
| DB role / database | `${POSTGRES_USER:-btcbot}` / `${POSTGRES_DB:-btcbot}` | `docker-compose.yml`, `deploy/backup.sh:16-17` |
| Env var names (values stay in `/opt/signalbot/.env`, never printed) | `POSTGRES_HOST/PORT/USER/PASSWORD/DB`, optional `POSTGRES_DSN` | `.env.example`, `common/config.py:86-112` |
| Shadow writer unit | `signalbot-shadow.service` / `.timer` (`main.py --shadow-once --shadow-reference-exchange binance`) | `deploy/signalbot-shadow.service`, `docs/SHADOW_TIMER_DEPLOY.md` |
| Backup pattern this copies | `docker exec btcbot_timescaledb pg_dump -U btcbot -d btcbot` | `deploy/backup.sh:29`, `docs/VPS_DEPLOY.md` §10 |

Run as an admin with docker access (the `signalbot` user has none by design,
`docs/VPS_DEPLOY.md` §10). Do **not** stop any service; nothing here needs it.

## 1. Preflight (read-only, seconds)

```bash
C=btcbot_timescaledb; U="${POSTGRES_USER:-btcbot}"; DB="${POSTGRES_DB:-btcbot}"
RO() { docker exec -i -e PGOPTIONS='-c default_transaction_read_only=on' "$C" \
         psql -X -q -v ON_ERROR_STOP=1 -U "$U" -d "$DB" "$@"; }

RO <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '120s';
SET LOCAL lock_timeout = '5s';
SELECT current_setting('transaction_read_only') AS txn_read_only;   -- must print "on"
SELECT to_regclass('public.forecast_predictions')      AS fp,
       to_regclass('public.forecast_outcomes')         AS fo,
       to_regclass('public.consensus_feature_vectors') AS cfv;
-- row counts + version namespaces in the window (small; uses ix_fp_symbol_tf_ts)
SELECT rule_version, calculation_version, code_version, model_family,
       min(bucket_ts) AS first_bucket, max(bucket_ts) AS last_bucket, count(*) AS n
FROM forecast_predictions
WHERE symbol = 'BTCUSDT' AND market_type = 'perp' AND timeframe = '5m'
  AND bucket_ts >= '2026-07-25T00:00:00Z' AND bucket_ts < '2026-08-27T00:00:00Z'
GROUP BY 1,2,3,4 ORDER BY first_bucket;
SELECT horizon, outcome_version, evaluation_exchange, count(*) AS n
FROM forecast_outcomes
WHERE symbol = 'BTCUSDT' AND market_type = 'perp' AND timeframe = '5m'
  AND bucket_ts >= '2026-07-25T00:00:00Z' AND bucket_ts < '2026-08-27T00:00:00Z'
GROUP BY 1,2,3 ORDER BY 1,2,3;
ROLLBACK;
SQL
```

Expectation: one `rule_version` (`forecast-rules-v0.1.0`), possibly **several
`calculation_version`s** (it is `sha256(feature_schema_version, config_hash,
code_version)[:16]`, so every deploy that changed `STAGE2_CODE_VERSION` forks it
and the same `bucket_ts` can hold more than one prediction row — see §4).

## 2. Export (three read-only sessions, CSV to `/tmp` on the host)

Each block is one transaction; the data stream of `COPY ... TO STDOUT` is the only
thing on stdout (`-q` suppresses `BEGIN`/`COPY n`/`ROLLBACK` tags), so the host
redirection yields a clean CSV. Sizes: predictions ≈ 9.5k rows (33 days × 288),
outcomes ≈ 3× that, consensus ≈ 9.5k rows; a few tens of MB at most.

### (a) predictions

```bash
RO > /tmp/v1_predictions.csv <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '600s';
SET LOCAL lock_timeout = '5s';
COPY (
  SELECT
    bucket_ts, calculation_version, rule_version, feature_schema_version,
    model_family, created_at,
    direction, final_score, confidence,
    (component_scores->>'price')::double precision         AS score_price,
    (component_scores->>'flow')::double precision          AS score_flow,
    (component_scores->>'oi')::double precision            AS score_oi,
    (component_scores->>'funding')::double precision       AS score_funding,
    (component_scores->>'liquidations')::double precision  AS score_liquidations,
    (component_scores->>'agreement')::double precision     AS score_agreement,
    reasons::text                                          AS reasons_json,
    horizon_set::text                                      AS horizon_set_json,
    reference_price, reference_price_source,
    exchanges_expected_max, min_coverage_ratio, data_confidence_overall,
    consensus_confidence, is_partial_consensus,
    -- the exact inputs the score was computed from (stored snapshot, not a re-read)
    (consensus_snapshot->>'price_move_pct_median')::double precision            AS snap_price_move_pct_median,
    (consensus_snapshot->>'price_direction_agreement')::double precision        AS snap_price_direction_agreement,
    (consensus_snapshot->>'taker_buy_notional_usd_sum')::double precision       AS snap_taker_buy_usd,
    (consensus_snapshot->>'taker_sell_notional_usd_sum')::double precision      AS snap_taker_sell_usd,
    (consensus_snapshot->>'taker_delta_notional_usd_sum')::double precision     AS snap_taker_delta_usd,
    (consensus_snapshot->>'flow_direction_agreement')::double precision         AS snap_flow_direction_agreement,
    (consensus_snapshot->>'oi_change_pct_median')::double precision             AS snap_oi_change_pct_median,
    (consensus_snapshot->>'oi_direction_agreement')::double precision           AS snap_oi_direction_agreement,
    (consensus_snapshot->>'funding_rate_median')::double precision              AS snap_funding_rate_median,
    (consensus_snapshot->>'observed_long_liquidation_notional_sum')::double precision  AS snap_liq_long_usd,
    (consensus_snapshot->>'observed_short_liquidation_notional_sum')::double precision AS snap_liq_short_usd,
    (consensus_snapshot->>'range_width_pct_median')::double precision           AS snap_range_width_pct_median,
    (consensus_snapshot->>'volume_notional_usd_sum')::double precision          AS snap_volume_usd,
    consensus_snapshot->'coverage_by_metric'   AS snap_coverage_by_metric,
    consensus_snapshot->'provenance_by_metric' AS snap_provenance_by_metric,
    config_hash, config_version, code_version
  FROM forecast_predictions
  WHERE symbol = 'BTCUSDT' AND market_type = 'perp' AND timeframe = '5m'
    AND bucket_ts >= '2026-07-25T00:00:00Z' AND bucket_ts < '2026-08-27T00:00:00Z'
  ORDER BY bucket_ts, created_at, calculation_version
) TO STDOUT WITH (FORMAT csv, HEADER true);
ROLLBACK;
SQL
```

If the full stored snapshot is wanted too (≈2–3 KB per row), add
`consensus_snapshot::text AS consensus_snapshot_json` — it is the entire
`ConsensusFeatureVector` serialised by field name (`storage/stage2_serialization.py:58-103`;
datetimes as ISO-8601 `+00:00`).

### (b) outcomes joined to their prediction

Join key = the prediction PK `(symbol, market_type, timeframe, bucket_ts,
calculation_version, rule_version)`; one outcome row per `(horizon,
evaluation_exchange, evaluation_price_source, outcome_version)`.

```bash
RO > /tmp/v1_outcomes.csv <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '600s';
SET LOCAL lock_timeout = '5s';
COPY (
  SELECT
    o.bucket_ts, o.calculation_version, o.rule_version,
    o.horizon, o.outcome_version, o.evaluation_exchange, o.evaluation_price_source,
    o.direction, o.prediction_final_score, o.prediction_confidence,
    o.reference_price, o.reference_price_source,
    o.evaluation_start_ts, o.evaluation_end_ts, o.target_bar_ts,
    o.bars_expected, o.bars_present,
    o.target_close_price, o.window_high_price, o.window_low_price,
    o.market_return_pct, o.peak_return_pct, o.trough_return_pct,
    o.directional_return_pct, o.mfe_pct, o.mae_pct,
    o.computed_at, o.code_version,
    (p.bucket_ts IS NOT NULL) AS prediction_row_present,
    p.created_at              AS prediction_created_at
  FROM forecast_outcomes o
  LEFT JOIN forecast_predictions p
    ON  p.symbol = o.symbol AND p.market_type = o.market_type AND p.timeframe = o.timeframe
    AND p.bucket_ts = o.bucket_ts AND p.calculation_version = o.calculation_version
    AND p.rule_version = o.rule_version
  WHERE o.symbol = 'BTCUSDT' AND o.market_type = 'perp' AND o.timeframe = '5m'
    AND o.bucket_ts >= '2026-07-25T00:00:00Z' AND o.bucket_ts < '2026-08-27T00:00:00Z'
  ORDER BY o.bucket_ts, o.calculation_version,
           CASE o.horizon WHEN '15m' THEN 0 WHEN '1h' THEN 1 WHEN '4h' THEN 2 END,
           o.evaluation_exchange, o.outcome_version
) TO STDOUT WITH (FORMAT csv, HEADER true);
ROLLBACK;
SQL
```

### (c) 5m consensus feature vectors (past-5m state per bucket)

```bash
RO > /tmp/v1_consensus_5m.csv <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '600s';
SET LOCAL lock_timeout = '5s';
COPY (
  SELECT
    bucket_ts, calculation_version, feature_schema_version, computed_at,
    price_move_pct_median, price_move_pct_mad, range_width_pct_median,
    price_direction_agreement, flow_direction_agreement, oi_direction_agreement,
    volume_notional_usd_sum,
    taker_buy_notional_usd_sum, taker_sell_notional_usd_sum,
    taker_delta_notional_usd_sum, cvd_delta_notional_usd_sum,
    oi_change_pct_median, oi_change_pct_mad,
    funding_rate_median, funding_rate_mad,
    observed_long_liquidation_notional_sum, observed_short_liquidation_notional_sum,
    observed_liquidation_event_count_sum,
    liquidation_feed_quality_by_exchange::text AS liq_feed_quality_json,
    exchanges_expected_max, min_coverage_ratio, data_confidence_overall,
    consensus_confidence, is_partial_consensus,
    coverage_by_metric::text        AS coverage_by_metric_json,
    provenance_by_metric::text      AS provenance_by_metric_json,
    data_confidence_by_metric::text AS data_confidence_by_metric_json,
    outlier_exchanges::text         AS outlier_exchanges_json,
    config_hash, config_version, code_version
  FROM consensus_feature_vectors
  WHERE symbol = 'BTCUSDT' AND market_type = 'perp' AND timeframe = '5m'
    AND bucket_ts >= '2026-07-25T00:00:00Z' AND bucket_ts < '2026-08-27T00:00:00Z'
  ORDER BY bucket_ts, calculation_version
) TO STDOUT WITH (FORMAT csv, HEADER true);
ROLLBACK;
SQL
```

Optional (d): the per-venue inputs behind the consensus, same window, if the
single-venue (Binance-only) approximation is to be checked against the real
Binance leg:

```bash
RO > /tmp/v1_exchange_features_5m.csv <<'SQL'
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '600s';
SET LOCAL lock_timeout = '5s';
COPY (
  SELECT exchange, bucket_ts, calculation_version,
         price_move_pct, range_width_pct, close_price,
         volume_notional_usd, taker_buy_notional_usd, taker_sell_notional_usd,
         taker_delta_notional_usd, cvd_delta_notional_usd,
         oi_change_pct, oi_unit, funding_rate,
         long_liquidation_notional, short_liquidation_notional, liquidation_event_count,
         liquidation_feed_quality, is_snapshot_feed,
         bars_expected, bars_present, has_gap, is_usable
  FROM exchange_feature_vectors
  WHERE symbol = 'BTCUSDT' AND market_type = 'perp' AND timeframe = '5m'
    AND bucket_ts >= '2026-07-25T00:00:00Z' AND bucket_ts < '2026-08-27T00:00:00Z'
  ORDER BY bucket_ts, exchange, calculation_version
) TO STDOUT WITH (FORMAT csv, HEADER true);
ROLLBACK;
SQL
```

## 3. Verify, then move the files off the box

```bash
wc -l /tmp/v1_predictions.csv /tmp/v1_outcomes.csv /tmp/v1_consensus_5m.csv
head -c 600 /tmp/v1_predictions.csv          # header + first row only
chmod 600 /tmp/v1_*.csv
# copy with scp/rsync to the analysis machine; the files hold market data only, no credentials.
```

## 4. Caveats for the offline evaluation

1. **Duplicate buckets across `calculation_version`.** Predictions are insert-once
   per `(bucket_ts, calculation_version, rule_version)`; the recovery pass may have
   re-created a bucket under a new `calculation_version` after a deploy. Deduplicate
   per `bucket_ts` (keep the earliest `created_at`, i.e. the row that was actually
   "live"), or evaluate per `calculation_version` and report both.
2. **NEUTRAL rows** are stored with `direction='NEUTRAL'`, `confidence=0.0`, the full
   `component_scores`/`final_score`, and `reasons` = the gate codes
   (`INSUFFICIENT_COVERAGE`, `LOW_CONSENSUS_CONFIDENCE`, `WEAK_PRIMARY_SIGNAL`,
   `SCORE_BELOW_ACTION_THRESHOLD`). Their outcome rows exist (market return, peak,
   trough) but `directional_return_pct`/`mfe_pct`/`mae_pct` are NULL
   (`storage/stage2_schema.sql` `ck_fo_directional_metrics`).
3. **Outcome timing.** `evaluation_start_ts = bucket_ts + 5m` (the prediction is
   made at the close of bucket `[bucket_ts, bucket_ts+5m)`), target = close of the
   1m bar at `evaluation_end_ts - 1m`; returns are vs `reference_price` =
   Binance 5m close of the prediction bucket. Only COMPLETE windows (all 15/60/240
   1m bars present) were persisted; missing outcomes mean missing bars, not a
   skipped prediction.
4. **E1-RUN-001 holdout overlap.** The window includes `[2026-08-16T00:00Z,
   2026-08-25T17:20Z)`. The V1 rows are derived products that the shadow runner
   wrote at the time, and the owner has ruled the holdout no longer pristine
   (`docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md`
   §6), but nothing has released it for new use. If the analysis is to stay clear
   of it, add to every `WHERE`:
   `AND NOT (bucket_ts >= '2026-08-16T00:00:00Z' AND bucket_ts < '2026-08-25T17:20:00Z')`
   (and note that 4h outcomes of buckets from `2026-08-15T19:55Z` onward read 1m
   bars inside it). Decide this with the owner before running; it is a governance
   question, not a technical one.
5. **Known data defects inside the window** (affect the `liquidations` component
   only): Bybit liquidation sides were swapped until 2026-10
   (`data_ingestion/bybit_client.py:77-82`, rows with `liquidations.mapping_version IS NULL`),
   and OKX stored zero liquidations because its channel was refused
   (`data_ingestion/okx_client.py:5-8`) while the structural capability still said
   "available", so OKX contributed a measured 0. The stored `component_scores.liquidations`
   reflects those inputs as they were; do not "repair" the stored rows.
