# RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1 — design

**Status:** frozen before any model is fit and before any forecast metric is computed.
**Parents:** `PRE_IMPULSE_STATE_ATLAS_V1`, `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1`, `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1`, `RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1`.
**Object status at opening:** `CROSS_VENUE_AND_MULTI_EPOCH_REPLICATED_DIRECTIONAL_STATE / HISTORICAL_ONLY`.
**Evidence class of this unit:** `RETROSPECTIVE_FORECAST_PROTOTYPE / ALREADY_CONSUMED_SURFACES`.
**Claim ceiling:** `RETROSPECTIVE_FORECAST_PROTOTYPE`. The three surfaces below were already read for this feature. This is not a pristine out-of-sample validation. It is not an L3 probability and not a current probability. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

## Question

Does the frozen `RANGE_POSITION_4H` improve a walk-forward probabilistic prediction of the next-hour BTC direction beyond recent returns and volatility?

The target is `Y(T) = 1` when `R_1H(T) > 0` and `Y(T) = 0` when `R_1H(T) < 0`, with `R_1H(T) = log(close[T+1h] / close[T])`. The forecast is `P(UP next 1h | information available at T)`.

An exact zero return is excluded from training and from scoring. The rule name is `ZERO_RETURN_EXCLUDED`. It is not revised after a metric.

No new formula, no new horizon, no threshold search, no trading rule.

## Estimand

Incremental forecast value of one continuous feature, `RANGE_POSITION_4H`, beyond a frozen price-state baseline.

Primary losses, both on the walk-forward test rows:

- `ΔBrier = Brier(candidate) − Brier(baseline)`
- `ΔLogLoss = LogLoss(candidate) − LogLoss(baseline)`

An improvement is a negative difference. No minimum size is required.

## Surfaces

Three segments. Bybit is omitted. The grids are not stitched. No venue dummy is a feature.

| Segment | Price path | Interval on bar opens | Training rows for a test block |
|---|---|---|---|
| `BITMEX_2016_2019` | `D2_BITMEX_PRE2020_XBTUSD` `canonical_5m.jsonl.gz`, SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa` | first stored open through `2020-01-01T00:00:00Z` exclusive | BitMEX labeled anchors with `T` strictly before the block start |
| `BINANCE_2020_2024` | `CORE_BTC_BINANCE_V0` via `scripts.research.dh1.data.load_binance_perp_5m`. Snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`. Complete 5-minute bins aggregated from pinned 1-minute klines. No fill. | `2020-01-01T00:00:00Z` inclusive through `2025-01-01T00:00:00Z` exclusive | Binance 2020–2024 labeled anchors with `T` strictly before the block start |
| `BINANCE_2025_2026` | `RANGE_POSITION_4H_BINANCE_2025_2026_V1` `canonical_5m.jsonl.gz`, SHA256 `64c1646acf7b371904ee6fcb25373383589e16c368d23267f136f4481f9894b9` | `2025-01-01T00:00:00Z` inclusive through `2026-10-09T00:00:00Z` exclusive | Binance labeled anchors from 2020–2024 and from 2025–2026 with `T` strictly before the block start |

BitMEX prices stay in last-trade space. The inverse contract is not inverted. `RP4H` is dimensionless. Returns are log returns. `RV_4H` is dimensionless. Those facts are why a Binance model may train on earlier Binance rows. They are not a reason to put BitMEX rows in a Binance fit.

The 2025–2026 feature at `T` is computed on the 2025–2026 grid alone. Bars from 2024 are not bridged into that lookback. The E1 objects stay unread. The stored hole `2026-08-16T00:00:00Z` through `2026-08-25T23:55:00Z` stays missing. An anchor whose lookback, decision bar, or 1-hour future touches a missing bar is ineligible.

The 2020–2024 path is the discovery surface, already consumed for this feature. The discovery scan started anchors at global index 96. This prototype does not use that scan warmup. Eligibility is the replication rule: 48-bar lookback, residue 2, complete 1-hour future. The extra anchors this admits sit inside the already consumed window.

## Sample

`T` is the bar close. The anchor phase is the replication phase: global 5-minute index from `2020-01-01T00:00:00Z`, floor division, residue 2. That is a close on `:00`, `:15`, `:30`, or `:45`.

`RP4H`, `RET_4H`, `RV_4H`, and `R_1H` come from `scripts.research.range_position_4h_incremental_replication_v1.grid.features`. The window is the 48 completed 5-minute bars whose closes lie in `(T−4h, T]`, including `T`. Span must be positive.

`RET_1H = log(close[T] / close[T−1h])`. `RET_15M = log(close[T] / close[T−15m])`.

A row is feature-eligible when the replication mask is true and `RP4H`, `RET_4H`, `RV_4H`, `RET_1H`, `RET_15M`, and `R_1H` are finite. A feature-eligible row with `R_1H = 0` is dropped. The remaining rows are labeled. No imputation and no forward fill.

The BitMEX and Binance 2025–2026 eligible masks must equal the masks of those replication classifiers before the zero-return drop. A mismatch stops the run as `FORECAST_IMPLEMENTATION_INVALID`.

## Folds

Primary cadence remains 15 minutes. Blocks are ISO weeks of `T` in UTC. The block starts at Monday 00:00:00Z of that ISO week.

Expanding window, inside the training rule of the segment:

- training rows are labeled anchors allowed for that segment with `T` strictly before the block start;
- the week is a test week when those training rows number at least 1000 and cover at least 20 distinct ISO weeks;
- otherwise the week is warm-up and is not scored;
- the test rows are the labeled anchors of that week.

The floors 1000 and 20 are the replication support floors. They are not a skill threshold and they are not tuned.

No shuffle. No random split. No row from the test week, and no later row, enters the fit, the scaler, or the climatology rate.

Secondary cadence, not used for the route: the same protocol on the subset of labeled anchors whose close falls on an exact hour (`T` divisible by 3600000). Train and test both use that subset. The floors are applied to the subset.

The realized week list is `docs/research/RANGE_POSITION_4H_FORECAST_PROTOTYPE_V1_FOLDS.json`, written by the support census before any fit.

A bootstrap block is `(segment, ISO year, ISO week)`. The ISO week that starts on `2024-12-30` contains the last 2024 anchors and the first 2025 anchors. Those anchors stay in different segments and in different blocks. The 2024 anchors of that week are not training rows for the 2025 block that shares the Monday, because their `T` is not strictly before that Monday.

## Models

Baseline features, in this order: `RET_4H`, `RV_4H`, `RET_1H`, `RET_15M`.

Candidate features: those four, then `RANGE_POSITION_4H`.

No RSI, EMA, MACD, extra lags, sessions, volume, open interest, flow, levels, squares, splines, bins, or interactions. No venue indicator.

Model class: unpenalized logistic regression, binomial log-likelihood, Newton–Raphson, intercept included. scikit-learn is not a project dependency, and its default fit is L2, so the fit is the Newton update in `model.py` with no ridge term in the Hessian. There is no `C` and no lambda. The numerical stop is a maximum absolute gradient below `1e-8`, at most 30 iterations. The linear predictor is clipped to `[-30, 30]` only inside the sigmoid. Failure to converge, or a singular Hessian, is `FORECAST_IMPLEMENTATION_INVALID`. The iteration cap is not raised after a loss is seen.

Standardization, fit on the training rows of that block only: subtract the training mean and divide by the training population standard deviation (`ddof = 0`). The intercept column is not scaled. The four shared features use the same training moments in the baseline and the candidate. `RANGE_POSITION_4H` is scaled on those same rows. A non-finite or zero training standard deviation is `FORECAST_IMPLEMENTATION_INVALID`.

Climatology for a test row is the training-window mean of `Y`. It is constant inside a block. It uses no full-sample rate.

Probabilities used for decisions are the raw logistic probabilities. No Platt scaling and no isotonic regression.

Log loss clips probabilities to `[1e-12, 1−1e-12]` after the probability is formed. Brier score uses the unclipped probability. The clip is numerical, not a tuned threshold.

## Metrics

Primary, on the pooled 15-minute test rows of the three segments, weighted by row count:

- Brier score of climatology, baseline, and candidate
- log loss of climatology, baseline, and candidate
- `ΔBrier` and `ΔLogLoss`

Each segment's own losses are reported. They do not have a separate pass/fail. The unweighted mean of the three segment deltas is reported and is not the route.

Uncertainty: ISO-week block bootstrap of the stored test probabilities. A block is `(segment, iso year, iso week)`. `B = 2000`. Seed `20261120`. Percentiles `0.025` and `0.975`. A draw resamples blocks with replacement and recomputes climatology, baseline, and candidate Brier and log loss, and both deltas, on the sampled rows. A repeated block repeats its rows. The draw does not refit. Fewer than 1900 finite draws is `FORECAST_IMPLEMENTATION_INVALID`.

Secondary, not gates: AUROC; calibration slope and intercept from an unpenalized logistic regression of `Y` on `logit(clip(p, 1e-6, 1−1e-6))` fit on the pooled test predictions; the reliability table; the distribution of predicted probabilities; the separation of predicted probabilities between realized up and down.

Catastrophic calibration failure, used only as a route condition: the candidate calibration slope on the pooled test predictions is negative.

Fixed probability bins, descriptive, not retuned: `(-inf, 0.44)`, `[0.44, 0.47)`, `[0.47, 0.50)`, `[0.50, 0.53)`, `[0.53, 0.56)`, `[0.56, inf)`. Each bin reports N, mean predicted probability, observed `P(UP)`, and the difference of those two rates.

Era table, descriptive, no year gate: calendar years 2016 through 2026. For each, N, both Brier scores, `ΔBrier`, both log losses, mean predicted `P(UP)`, and observed `P(UP)`.

Amplitude, descriptive: the distribution of `P_candidate − P_baseline` on the pooled test rows, with minimum, 10th, 25th, 50th, 75th, and 90th percentiles, maximum, and the median absolute shift.

Coefficient table, diagnostic: standardized coefficients by segment and by test fold, plus the last fold of each segment. Not a claim.

Illustrative probabilities, not a live forecast and not a chosen timestamp: on the last test fold of each segment, set the four baseline features to their training means and set `RANGE_POSITION_4H` to 0.1, 0.5, and 0.9. Report the candidate probability at those three points.

## Route

Evaluated in this order.

| Route | Rule |
|---|---|
| `FORECAST_IMPLEMENTATION_INVALID` | Eligibility diverges from a replication mask, a fit or a scaler fails, a test row sees data at or after its block start, or fewer than 1900 bootstrap draws are finite |
| `FORECAST_INCREMENTAL_SKILL_SUPPORTED` | `ΔBrier < 0`, `ΔLogLoss < 0`, the 95% interval for `ΔBrier` has upper end strictly below 0, and the candidate calibration slope is greater than or equal to 0 |
| `FORECAST_INCREMENTAL_SKILL_UNCERTAIN` | Both point estimates are negative, and the supported rule does not apply |
| `FORECAST_NO_INCREMENTAL_SKILL` | Otherwise |

AUROC is not a gate. A negative calibration slope blocks the supported route. If the two loss points are still negative, that case is uncertain rather than a claim of skill.

## Not in this unit

PnL, fees, Sharpe, a long/short rule, entries, stops, target-hit, leverage, a user-facing probability, a bot finding, and a prospective calibration. A supported result would leave the next question as `RANGE_POSITION_4H_PROSPECTIVE_CALIBRATION_V1` or `FORECAST_ENGINE_V0`. This design does not start either one.

The evaluator entry point exits `AWAITING_OWNER_GO` until a later owner approval. The support census counts rows and weeks only.
