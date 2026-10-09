# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1 — design

**Status:** frozen before the Binance 2025–2026 association is read.
**Parents:** `PRE_IMPULSE_STATE_ATLAS_V1`, `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1`, `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1`.
**Evidence class:** `MODERN_TIME_DISJOINT_HISTORICAL_REPLICATION / QUESTION_FRESH_REPLICATION`.
**Claim ceiling:** `HISTORICAL_ONLY`. Not a current probability. Not a product probability. Not a target-hit model. Not a trading edge. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## Question

Does `RANGE_POSITION_4H` keep a negative association with the next 1-hour log return after `RET_4H` and `RV_4H` on Binance USD-M BTCUSDT in 2025–2026?

The primary estimand is the partial Spearman of `RP4H` with `R_1H` given `RET_4H` and `RV_4H`. The rank-residual implementation is the one imported from the Bybit successor. No magnitude has to match BitMEX `-0.04742832892681095`, Bybit `-0.02784152009582924`, or the Binance 2020–2024 discovery raw `-0.057773446228651215`.

## Exposure

The exact relation `RANGE_POSITION_4H → R_1H`, and the same ratio under the names `close_pos_4h` and `dist_lower_4h`, was read on `CORE_BTC_BINANCE_V0` for decisions before `2025-01-01T00:00:00Z`, on Bybit 2020–2024, and on BitMEX 2016–2019. A repository search found no evaluation of that relation, or of an algebraically equivalent transform, on Binance bars at or after `2025-01-01`. The 2025–2026 product kline surface has been used for other questions (range forecast, levels, flow, open interest, and event days). This read is question-fresh on a surface that is not a pristine holdout.

## Surface

Official Binance Vision USD-M BTCUSDT 5-minute klines. The object list is `beta.history_data.plan_objects` as of `2026-10-09`, klines only, from `2025-01-01` through yesterday. A missing monthly object would be replaced by its days that do not intersect the protected window. Every requested zip is checksum-verified before its rows are kept. The realized keys and SHA-256 values are `docs/research_data/RANGE_POSITION_4H_BINANCE_2025_2026_V1/OBJECTS.json`. The price path used for the association is `canonical_5m.jsonl.gz` in that directory: `open_time_ms`, `open`, `high`, `low`, `close`.

Bars included: open time `2025-01-01T00:00:00Z` inclusive through `2026-10-08T23:55:00Z` inclusive. The surface end is `2026-10-09T00:00:00Z` exclusive.

## E1

`E1-RUN-001` stays closed. The protected interval is `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`. These objects are not requested:

- `monthly/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08.zip`
- `daily/klines/BTCUSDT/5m/BTCUSDT-5m-2026-08-16.zip` through `BTCUSDT-5m-2026-08-25.zip`

No row whose open lies in the protected interval is stored. Because those ten days are refused as whole objects, opens from `2026-08-16T00:00:00Z` through `2026-08-25T23:55:00Z` are absent. Nothing is interpolated or bridged. An anchor whose 4-hour lookback, nuisance path, decision bar, or 1-hour future path touches a missing bar is ineligible.

## Anchor and formulas

Same 15-minute phase as the frozen object. Bar open `t`, global index `(t - 2020-01-01T00:00:00Z) / 5min` using floor division, residue `2` (mod 3). `T` is the bar close and `T < 2026-10-09T00:00:00Z`. The future bar's open must be before that instant.

`RP4H`, `RET_4H`, `RV_4H`, `RANGE_WIDTH_4H`, and `R_1H` are the function imported from the Bybit successor. `W` is the 48 bars with closes in `(T-4h, T]`, including `T`. Positive span is required. The 1-hour future path is complete only when every close from `T+5min` through `T+1h` is present and positive.

`RET_1H = log(close[T] / close[T-1h])`. `RET_15M = log(close[T] / close[T-15m])`. They enter only the robustness partial.

## Estimands

1. Raw Spearman of `RP4H` with `R_1H`.
2. Partial given `RET_4H` only. Reported. Not a route input.
3. Primary partial given `RET_4H` and `RV_4H`.
4. Robustness partial given `RET_4H`, `RV_4H`, `RET_1H`, and `RET_15M`. Reported. Not a route input.

No other control. One covariate is checked against `amendment_a1.partial_spearman` on the full sample before a route is written.

`RANGE_WIDTH_4H` is a diagnostic only: its Spearman with `RP4H`, and the partial that also conditions on width. It does not route.

## Uncertainty

ISO week of `T`. `B = 2000`. Seed `20261119`. Percentiles `0.025` and `0.975`. Each draw recomputes the raw Spearman, the `RET_4H` partial, the primary partial, and the robustness partial. Fewer than `1900` valid draws on the raw Spearman or the primary partial yields `RANGE_POSITION_MODERN_ESTIMATE_UNAVAILABLE`.

## Route

Order:

| Route | Rule |
|---|---|
| `RANGE_POSITION_MODERN_TEMPORAL_REPLICATION_SUPPORTED` | raw point `< 0`, primary point `< 0`, primary interval entirely below 0 |
| `RANGE_POSITION_MODERN_RAW_SUPPORTED_INCREMENTAL_UNCERTAIN` | raw point `< 0`, raw interval entirely below 0, primary interval includes 0 |
| `RANGE_POSITION_MODERN_COMPATIBLE_BUT_UNCERTAIN` | raw point `< 0`, primary point `< 0`, and neither stronger route fired |
| `RANGE_POSITION_MODERN_NOT_REPLICATED` | a completed estimate that matches none of the three |

No magnitude floor. No requirement that every year agree. Quintiles, years, halves, width, and the robustness partial do not route.

## Description

Five full-sample bins of `RP4H`, edges `0.2, 0.4, 0.6, 0.8`, `digitize` `right=False`. Each bin: N, P(`R_1H > 0`), mean, median. Calendar year of `T`: raw and primary. Median-`T` split: raw and primary.

## Support gate

A census is written before any correlation. It records the object list, the E1 exclusion, missing runs, anchor counts, weeks, and per-year N. It does not record a future-return association, a rank correlation, a quintile, P(UP), or a mean future return. Technical adequacy: eligible anchors `>= 1000`, ISO weeks `>= 20`, and every hole lies inside the rejected August object span. Below that, the outcome is not read.

## What this unit does not do

No second range length. No second horizon. No rejection feature. No bars-since feature. No session split. No threshold search. No product file. No forecast-engine prototype.
