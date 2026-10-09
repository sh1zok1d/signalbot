# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1 — design

**Status:** frozen before the BitMEX association is read.
**Parents:** `PRE_IMPULSE_STATE_ATLAS_V1`, `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1`.
**Evidence class:** `HISTORICAL_TEMPORAL_REPLICATION / QUESTION_FRESH_REPLICATION`.
**Track:** `STRUCTURE`.
**Claim ceiling:** `HISTORICAL_ONLY`. Not a current probability. Not a product probability. Not a target-hit model. Not a trading edge. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## Question

Does `RANGE_POSITION_4H` keep the same negative association with the next 1-hour log return, after the trailing 4-hour signed return and 4-hour realized volatility, on BitMEX XBTUSD in 2016–2019?

Published comparison points, not thresholds: Binance raw Spearman `-0.057773446228651215`. Bybit raw `-0.05781800690167492`, partial given `RET_4H` `-0.027418341298313498`, primary partial `-0.02784152009582924`. No magnitude has to be matched.

## Exposure

The file was already read for D2 tail-risk path MAE and for D7 activity. Those questions are not `RANGE_POSITION_4H → R_1H`. A repository search found no prior computation of this ratio against the next 1-hour log return on this tape. This unit is the first read of that relation.

## Surface

`D2_BITMEX_PRE2020_XBTUSD` / `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz`. SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`. Last-trade XBTUSD open, high, low, close. The contract is inverse. Prices are not inverted. Mark, index, funding, inverse PnL, and contract-return transforms are not used.

D7 gzip SHA256 `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` differs because that file carries activity fields. On the 382033 shared `open_time_ms` values, open, high, low, and close match exactly. This unit reads the D2 file only.

Holes stay missing. Nothing is filled. The known hole is the 288 missing 5-minute opens from `2016-12-06T23:55:00Z` through `2016-12-07T23:50:00Z`. Any other hole is also left missing. An anchor whose lookback or 1-hour future path touches a missing bar is ineligible.

## Anchor

Same 15-minute phase as the Bybit successor. Bar open `t`, global index `(t - 2020-01-01T00:00:00Z) / 5min` using floor division, keep residue `2` (mod 3). That residue is exactly the set of bars whose close falls on a 15-minute boundary. It extends backward through 2016 without a new phase. The Bybit floor `global index >= 96` is the 2020-01-01 warmup and is not applied on this earlier tape. `T` is the bar close, and `T < 2020-01-01T00:00:00Z`. The future bar's open must be before `2020-01-01T00:00:00Z`.

## Formulas

Identical to the Bybit successor. The feature function imported from that unit is the implementation. No second copy of the arithmetic.

`W` is the 48 bars with closes in `(T-4h, T]`, including `T`.

`RP4H = (close[T] - min low(W)) / (max high(W) - min low(W))` when the span is positive and every bar in `W` is present.

`RET_4H = log(close[T] / close[T-4h])`.

`RV_4H = sqrt(sum of squares of the 48 five-minute log returns from close[T-4h] to close[T])`. A missing return makes it missing.

`R_1H = log(close[T+1h] / close[T])`. No other horizon.

The 1-hour future path is complete only when every close from `T+5min` through `T+1h` is present and positive. That is the gap rule. It does not change the target formula.

The analysis sample is the phase anchors where `RP4H`, `RET_4H`, `RV_4H`, and `R_1H` are finite and the future path is complete. No year is dropped. No session, volatility, or trend subset.

## Estimands

Same rank residual definition as the Bybit unit: midranks, mergesort, OLS with an intercept, Pearson of residuals. One covariate goes through `amendment_a1.partial_spearman` and must match on the full sample before a route is written. Two covariates are that helper's algebra with `RET_4H` then `RV_4H`.

1. Raw Spearman of `RP4H` with `R_1H`.
2. Partial given `RET_4H` only. Reported. Not a route input.
3. Primary partial given `RET_4H` and `RV_4H`.

No range width, hour, volume, funding, or efficiency control.

## Uncertainty

ISO week of `T`. `B = 2000`. Seed `20261118`. Percentiles `0.025` and `0.975`. Each draw recomputes the raw Spearman, the primary partial, and the secondary partial. The secondary interval does not route. A draw that is degenerate is omitted. Fewer than `1900` valid draws on the raw Spearman or the primary partial yields `RANGE_POSITION_ESTIMATE_UNAVAILABLE`.

## Route

Discovery sign is negative. Order:

| Route | Rule |
|---|---|
| `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED` | raw point `< 0`, primary point `< 0`, primary interval entirely below 0 |
| `RANGE_POSITION_RAW_TEMPORAL_REPLICATION_INCREMENTAL_UNCERTAIN` | raw point `< 0`, raw interval entirely below 0, primary interval includes 0 |
| `RANGE_POSITION_TEMPORALLY_COMPATIBLE_BUT_UNCERTAIN` | raw point `< 0`, primary point `< 0`, and neither of the first two fired |
| `RANGE_POSITION_NOT_TEMPORALLY_REPLICATED` | raw point `>= 0`, or the primary point is not negative while the primary interval excludes 0 |

No magnitude floor. Quintiles, years, and halves do not route. A same-sign point whose interval includes 0 is not supported.

## Description

Five full-sample bins of `RP4H`, edges `0.2, 0.4, 0.6, 0.8`, `digitize` `right=False`. Each bin: N, P(`R_1H > 0`), mean, median. Calendar year of `T` and a median-`T` split: raw and primary only.

## Support gate

A support census is written before any correlation. It records anchor counts, the known-gap exclusion, weeks, and per-year N. It does not record a return, a rank correlation, or a bin of outcomes. Technical adequacy, not an effect-size gate: eligible anchors `>= 1000` and ISO weeks `>= 20`, and the file's missing opens are exactly the declared 288-bar run. Below that, the outcome is not read.

## Parity with the Bybit successor

| Component | Bybit | BitMEX | Same |
|---|---|---|---|
| Anchor cadence | close on the 15-minute boundary, residue 2 from the 2020-01-01 5m index | same residue, extended before 2020 | yes, except the 2020 warmup floor |
| 4h lookback | 48 completed 5m bars | 48 completed 5m bars | yes |
| T bar inside the range | included | included | yes |
| Target | log close 12 bars ahead over close at T | same | yes |
| `RET_4H` | log close ratio over 48 bars | same function | yes |
| `RV_4H` | sqrt sum of squares of those 48 log returns | same function | yes |
| Missingness | hole stays missing; sample needs finite RP, RET, RV, R | same, plus every close in the next hour present | future-path completeness is the explicit gap rule |
| Partial Spearman | rank residual OLS | imported from that unit | yes |
| Bootstrap | ISO week, B 2000, percentile 95% | same, new seed `20261118` | yes |

## What this unit does not do

No second range length. No second horizon. No rejection feature. No bars-since feature. No threshold search. No product file.
