# Timestamp-only tape census — specification V1

**Status:** `SPEC_WRITTEN / NOT_RUN` (hashed before any run; the digest is recorded in `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1.json`)
**Purpose, the only one:** operational feasibility of C1 (surface B availability per stratum, common support) and the expected prospective horizon for `WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1`.
**Authorized by the owner (2026-10-03):** read-only, before the full freeze, only after this spec is written and hashed.

## What it reads (and nothing else)

From `beta_state_tape` only, through the production row selection (`DISTINCT ON (bucket_ts) … ORDER BY bucket_ts, tape_id DESC`, `materialized`, `symbol = 'BTCUSDT'`, `market_type = 'perp'`, `timeframe = '5m'`, the current `calculation_version` and the current state schema version):

| Column / expression | Why |
|---|---|
| `bucket_ts` | clock-hour grid, dates, weekday type, ISO week, month |
| `metrics ? 'x:<venue>:kline_open'` … `kline_high`, `kline_low`, `kline_close` and `jsonb_typeof(metrics -> key) <> 'null'` per venue | per-venue OHLC **presence** (boolean), never the value |
| `metrics ? 'c:volume_notional_usd_sum'` and `jsonb_typeof(…) <> 'null'` | presence of the cross-venue volume sum (boolean) |

The SQL selects booleans produced inside PostgreSQL; no numeric or string market value leaves the database. No join to `beta_episodes`, `beta_push_decisions`, `beta_context_snapshots`, `beta_d7_*` or any outcome table. No OHLC, return, volume value, OI, funding, rank, percentile, flag or episode outcome is read.

## What it computes (pure functions of the above)

For every UTC clock hour `H` in the census period (first tape bucket .. last complete clock hour), with the window `[H−1:00, H:00)` and the stratum from the date of `H−1:00`:

1. `MISSING_1H_BUCKET`: any of the 12 buckets absent.
2. `VENUE_COVERAGE_BELOW_MIN`: fewer than `min_venue_coverage` venues with all four OHLC keys present and non-null in all 12 buckets.
3. `REFERENCE_IMMATURE`: span of present buckets in `[t − 30d, t)` below 30 days (the `mature` tier by span).
4. `INSUFFICIENT_SAME_TYPE_DATES` (C1 only): fewer than 8 distinct same-type UTC dates with a present bucket in `[t − 30d, t)`.
5. Usable under C0 = none of 1–3; usable under C1 = none of 1–4; common support = both.

Outputs per stratum (`WEEKDAY`, `WEEKEND`, `AGGREGATE`): clock hours, usable hours per scheme, common-support hours, counts per unusable reason per scheme, missing-bucket share, first bucket at which both schemes are usable for both strata (`PROSPECTIVE_START` candidate), distinct dates/ISO weeks/months. Nothing else.

## What it may not do

- change C1 to C1-LONG or any parameter;
- compute a rank, rate, gap, flag or qualification;
- be re-run with a different reason order, minimum or lookback.

If the result shows the §5 item 0 availability rule or the Stage P horizon (§7) cannot be met by construction, the design status becomes `DESIGN_BLOCKED_BY_FEASIBILITY` and the owner decides.

## Runner

`scripts/product/weekday_weekend_census.py` (offline tooling; not imported by any runtime module). Its SHA256 is recorded beside this spec's digest. It prints the counts above as JSON and writes `docs/WEEKDAY_WEEKEND_CALIBRATION_CENSUS_RESULT.json`.
