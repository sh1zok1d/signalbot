# RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1 — design

**Status:** frozen before the Bybit outcome is read.
**Parent:** `PRE_IMPULSE_STATE_ATLAS_V1`, review `PRE_IMPULSE_STATE_ATLAS_V1_INDEPENDENT_REVIEW.md`.
**Evidence class:** `CROSS_VENUE_HISTORICAL_REPLICATION / ONE_SHOT`.
**Track:** `STRUCTURE`.
**Claim ceiling:** historical only. Not a current probability. Not L3 or L4. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Not this unit:** a new discovery scan, a second horizon, rejection or bars-since, fees, entries, stops, PnL.

## Question

On Bybit, does `RANGE_POSITION_4H` contain directional information about the next 1-hour BTC return beyond the recent signed 4-hour return and 4-hour realized volatility?

The published Binance discovery sign is negative. Same sign alone is not the scientific conclusion.

## Surface

`LEVEL_CROSS_VENUE_PERP_5M_V0` / `bybit_btcusdt_linear_5m.csv.gz`. Bybit BTCUSDT linear perpetual 5-minute bars. Canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. Header `open_ms,open,high,low,close`. No bar at or after `2025-01-01T00:00:00Z` may be read. Binance outcomes are not loaded.

Holes stay missing. Nothing is carried forward and nothing is interpolated.

## Anchor

Parent phase, on the clock: bar open `t0 + i * 5min` with `t0 = 2020-01-01T00:00:00Z`, keep `i >= 96` and `i % 3 == 2`. `T` is the close of that bar, `T = open + 5min`, and `T < 2025-01-01T00:00:00Z`.

Bybit's file starts later than bar 96, so the parent's warmup index is already satisfied. The formulas below still need 48 complete clock slots before `T`. That is the parent window, not an extra thinning rule. A missing slot inside a window drops that anchor. Complete bars are not thinned further.

## Formulas

Window `W` is the 48 five-minute bars whose closes fall in `(T-4h, T]`, inclusive of the bar that closes at `T`. In index form on a complete grid this is `[i-47, i]`.

`RP4H(T) = (close[T] - min low(W)) / (max high(W) - min low(W))` when the span is finite and positive and every bar in `W` is present. Otherwise missing.

`RET_4H(T) = log(close[T] / close[T-4h])`. `close[T-4h]` is the close 48 bars before `T`.

`RV_4H(T) = sqrt(sum of the squares of the 48 five-minute log returns from close[T-4h] to close[T])`. A missing return makes `RV_4H` missing. This is the parent `rv_4h`. A hole between the endpoints drops `RV_4H`, so the analysis sample keeps only complete clock paths. On those paths the endpoint ratio is the sum of the same 48 log returns.

`R_1H(T) = log(close[T+1h] / close[T])`. `T+1h` is 12 bars after `T`. The future bar's open must be before `2025-01-01T00:00:00Z`. No other horizon.

`RANGE_WIDTH_4H(T) = log(max high(W)) - log(min low(W))` when the lows are positive. This is the parent `log_range_4h`. Diagnostic only.

The analysis sample is the intersection where `RP4H`, `RET_4H`, `RV_4H`, `RANGE_WIDTH_4H`, and `R_1H` are all finite. One sample for every estimand.

## Estimands

Method, frozen: average ranks with midranks, mergesort tie order, the same ranks as `amendment_a1.average_ranks`. Residualize by OLS with an intercept. A residual is degenerate when its residual sum of squares is at most `1e-12` of the total sum of squares, or the total is zero. The association is the Pearson correlation of the two residuals. One covariate is `amendment_a1.partial_spearman`. Two or three covariates are that same algebra with extra OLS columns, because the project helper accepts one covariate. The one-covariate point on the full sample must match the helper before a route is written.

1. **Raw replication.** `rho_raw = Spearman(RP4H, R_1H)`.
2. **Primary.** Partial Spearman of `RP4H` with `R_1H` given `RET_4H` and `RV_4H`, columns in that order.
3. **Secondary, not a route.** The same partial given `RET_4H` only.
4. **Width diagnostic, not a route.** Spearman of `RP4H` with `RANGE_WIDTH_4H`, and the partial of `RP4H` with `R_1H` given `RET_4H`, `RV_4H`, and `RANGE_WIDTH_4H`. The point is compared with the primary point. The control set is not revised after the outcome.

`attenuation_by_ret = rho_raw - rho_given_ret`. When `rho_raw` is not zero, `share_removed_by_ret = attenuation_by_ret / rho_raw`. These describe the secondary partial. They do not route.

## Uncertainty

ISO week of `T` in UTC. Resample weeks with replacement, `B = 2000`, seed `20261117`, percentile interval `0.025` and `0.975`. Inside each draw recompute raw Spearman, the primary partial, and the secondary partial. The width partial is a point only. A draw that is degenerate is omitted from that interval. If fewer than `1900` draws are valid for the raw Spearman or for the primary partial, the route is `RANGE_POSITION_ESTIMATE_UNAVAILABLE`.

## Description, not a rule

Five bins of `RP4H` on the full analysis sample, edges at `0.2, 0.4, 0.6, 0.8`, `digitize` with `right=False`. Each bin reports N, P(`R_1H > 0`), mean `R_1H`, median `R_1H`. No threshold is selected. No Q1/Q5 rule.

Calendar year of `T`, and a split at the median `T`: raw Spearman and primary partial in each piece. No stability gate.

## Route

Evaluated in this order. The discovery sign is negative.

| Route | Rule |
|---|---|
| `RANGE_POSITION_INCREMENTAL_CROSS_VENUE_SUPPORTED` | raw point `< 0`, primary point `< 0`, primary interval entirely below 0 |
| `RANGE_POSITION_REPLICATES_RAW_BUT_INCREMENTAL_UNCERTAIN` | raw point `< 0`, raw interval entirely below 0, primary interval includes 0 |
| `RANGE_POSITION_DIRECTIONALLY_COMPATIBLE_BUT_UNCERTAIN` | raw point `< 0`, raw interval includes 0, and the first route did not fire |
| `RANGE_POSITION_NOT_REPLICATED` | raw point `>= 0` |
| `RANGE_POSITION_INCREMENTAL_SIGN_OPPOSES_DISCOVERY` | raw point `< 0`, raw interval entirely below 0, primary interval entirely above 0 |

No magnitude floor. The fifth route is the cell the four named rules do not cover: the raw sign replicates and the incremental interval lies on the other side of zero.

## What would change the reading

- Supported: location inside the recent range still lines up with the next hour after the signed 4h return and 4h volatility are removed.
- Raw replicates, incremental interval includes zero: the cross-venue pattern is carried by the ordinary recent-price state. `RANGE_POSITION_4H` is not promoted.
- Raw point is not negative: the Binance discovery did not replicate. The exact candidate stops.
- Sign-opposes: the raw pattern replicates and the incremental association has the other sign. `RANGE_POSITION_4H` is not promoted as the discovery object.

Rejection and bars-since stay unread. A later incremental question about them is a different unit, and only a supported route makes that question worth opening. This design does not open it.

## Variants

One target. One feature. One primary control pair. One secondary control. One width diagnostic. Year and half splits are reports, not searched endpoints. Count of inferential estimands: 2 (raw and primary). The other numbers are diagnostics.
