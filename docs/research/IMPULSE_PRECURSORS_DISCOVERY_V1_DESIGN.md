# IMPULSE_PRECURSORS_DISCOVERY_V1 — design, frozen before outcomes

`MODE = DISCOVERY`

Evidence class: `DISCOVERY / EXPOSED_HISTORY`.

Claim ceiling: `DISCOVERY_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

`outcome_read = false` in this note. One later exploratory pass may read the declared surface. That pass is not a confirmation and not a pristine holdout.

## Question

At a decision time `T`, does a bounded point-in-time state improve the probability that BTC first hits a volatility-scaled barrier during `(T, T+4h]`, relative to the driftless barrier geometry and to the historical frequency?

Estimand: walk-forward `P(IMPULSE | state at T)` for

`IMPULSE = 1` if the first resolved barrier is uniquely up or uniquely down, else `0`.

This is an occurrence forecast. It is not a signed-return forecast and not a post-impulse continuation test.

## What this is not

- Not H03. H03 asks what signed return follows an extreme impulse. This unit does not condition on an impulse having already occurred. H03 stays `H03_REJECTED_SPECIFIC_CLAIM`.
- Not a second `PRE_IMPULSE_STATE_ATLAS_V1` scan. That scan's target was a later signed return and its reopen text keeps that formula on this tape closed. The target here is a two-barrier first passage. The 62-series atlas list is not reused. `RANGE_POSITION_4H` results, including Track A, are not treated as confirmation.
- Not a reopen of H01. H01 asked whether a quiet window predicts higher future realized variance. Here the barriers already scale with trailing 24h quadratic variation, and that scale is the B1 control. Compression ratios are residual covariates. H01 is not rescored.
- Not H05 or B2-05. Taker imbalance is coverage-only and is not a model feature and not a ranked cell.
- No open interest, funding, order book, 2025/2026 bars, or E1 objects.

Reopen key relative to the closed impulse cells: `NEW_MECHANISM`.

## Surface

`CORE_BTC_BINANCE_V0`, snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.

Loader: `scripts.research.dh1.data.load_binance_perp_5m`. Legal months are 2020-01 through 2024-12 only. Every bar open must be strictly before `2025-01-01T00:00:00Z`. Missing 5-minute bins stay missing. Nothing is filled.

Decision `T` is the close of a completed 5-minute bar and is divisible by 15 minutes. `T` satisfies `2020-01-01T00:00:00Z <= T < 2025-01-01T00:00:00Z` and `T + 4h <= 2025-01-01T00:00:00Z`. The last forward bar may close exactly at the exclusive end; its open is still in 2024.

## Outcome

Past scale, on the 288 completed 5-minute log returns ending at `T`:

`sigma_5m^2 = mean(r^2)` (not demeaned). `sigma_4h = sigma_5m * sqrt(48)`.

Primary multiplier, chosen from the driftless series before any market path was labeled: `K = 1.5`. At the midpoint this null gives `P(IMPULSE) ≈ 0.267`. `K = 1` is an ordinary excursion. `K = 2` is rare. Those two values are descriptive counts only. They do not enter the model, the ranking, or the verdict.

```text
UP_BARRIER(T)   = close(T) * exp(+K * sigma_4h)
DOWN_BARRIER(T) = close(T) * exp(-K * sigma_4h)
```

The path is the high and low of the next 48 completed 5-minute bars. The first bar that touches either barrier decides:

- `UP_FIRST` if that bar trades the up barrier and not the down barrier;
- `DOWN_FIRST` if it trades the down barrier and not the up barrier;
- `AMBIGUOUS` if that same bar trades both;
- `NEITHER` if the window is complete and neither barrier is traded.

A gap, a malformed bar, a non-positive scale, or a non-finite feature drops the row. An ambiguous row is counted and excluded from every probability model. `Y = 1` for `UP_FIRST` or `DOWN_FIRST`, else `0`.

The geometric probability is `race_raw` from `scripts/research/level_race_forecast_v1/b0.py` at the decision close, the two barriers, `sigma_5m`, and `tau = 48`. `P_geom = P_up + P_down` before the product floor. For this symmetric construction it does not depend on the volatility level. If it is not constant across kept rows, the run is invalid.

## Catalog

Descriptive only. Walk kept impulse rows in time. Keep the earliest row, then ignore later impulse rows until that episode's touch time. Record direction, touch time, duration, signed barrier amplitude in `sigma_4h` units, wick amplitude, the frozen `rv_ratio_4h_24h` bin, and the count of nested impulse rows. The predictive sample is every kept decision row, not the catalog.

## Features

All windows end at `T` and use only completed bars. A zero range or a zero 24h quote sum drops the row.

B1 column: `log_rv_24h = log(sigma_5m)`.

Candidate columns, in order: `log_rv_24h`, `ret_15m_z`, `ret_1h_z`, `ret_4h_z`, `range_pos_4h`, `rv_ratio_15m_1h`, `rv_ratio_1h_4h`, `rv_ratio_4h_24h`, `range_vs_sigma_4h`, `vol_ratio_15m`, `vol_ratio_1h`, `vol_ratio_4h`, `hour_sin`, `hour_cos`, `dow_sin`, `dow_cos`, `ix_pos_ret4`, `ix_rv_range`, `ix_vol_range`, `ix_pos_rv4`.

Returns are log closes over 3, 12, and 48 bars, divided by `sigma_4h`. `range_pos_4h` is the close location inside the 48-bar high-low range. Realized-volatility ratios are square-root mean-square ratios over 3/12, 12/48, and 48/288 bars. `range_vs_sigma_4h` is the 48-bar log range divided by `sigma_4h`. Volume ratios are quote-sum ratios against the trailing 288-bar mean. Clock features are sine and cosine of UTC hour and of Monday-based weekday.

`accel = ret_15m_z - ret_1h_z / 4` is an exact linear combination of two candidate columns. It is binned in the state map and omitted from the unpenalized design matrix.

Interactions: `range_pos_4h * ret_4h_z`, `rv_ratio_15m_1h * range_vs_sigma_4h`, `vol_ratio_1h * range_vs_sigma_4h`, `range_pos_4h * rv_ratio_4h_24h`.

No other transform, lag, or indicator is computed.

## State map

Fixed edges, not sample quantiles.

- z features `ret_15m_z`, `ret_1h_z`, `ret_4h_z`, `accel`: edges `-1, -0.25, 0.25, 1` (5 bins).
- ratio features, three RV and three volume: edges `0.7, 1.0, 1.4` (4 bins).
- `range_pos_4h`: edges `0.2, 0.4, 0.6, 0.8` (5 bins).
- `range_vs_sigma_4h`: edges `1, 2, 3` (4 bins).
- UTC sessions `[0,7), [7,13), [13,21), [21,24)`.
- Seven weekdays.

Six joints: short RV `< 0.7` and log-range `< 1`; short RV `>= 1.4` and log-range `>= 2`; range position `>= 0.8` and `ret_4h_z >= 0.25`; range position `< 0.2` and `ret_4h_z <= -0.25`; 1h volume `< 0.7` and log-range `< 1`; 1h volume `>= 1.4` and log-range `< 1`.

That is 64 univariate cells and 6 joints. Plus two diagnostic-K pooled rates and one candidate-versus-B1 comparison: 73 material cells. Every cell is stored. None is dropped after the read.

On scored rows, `A` is the cell hit rate and the comparable baseline is the mean B1 probability of the same rows. The interval resamples ISO weeks, `B = 2000`, seed `20261122`, without refitting. A cell needs `N >= 200`. Year slices need `N >= 200`. The score is `abs(delta) * year_sign_agreement * min(1, N/1000)` when at least four years qualify and the pooled delta is nonzero; otherwise the score is 0. Agreement is the share of qualifying years whose delta has the pooled sign.

A successor name is recorded only if the verdict is `PRECURSOR_DISCOVERY_PROMISING` and the best score is positive. Otherwise no successor is named.

## Models

Same kept rows for every model. Expanding ISO week of `T`. A training row is admitted only when `T + 48 * 300000 <= Monday 00:00 UTC` of the test week. Floors: 1000 training rows and 20 training weeks. Scaler: training mean and population standard deviation, `ddof = 0`. A zero scale is invalid.

- B0: training mean of `Y`.
- B_geom: the constant `race_raw` probability. Not fitted.
- B1: unpenalized logistic on `log_rv_24h` only.
- Candidate: unpenalized logistic on the 20 candidate columns.

Newton–Raphson, maximum 30 iterations, gradient tolerance `1e-8`, sigmoid clip 30. No penalty and no fallback. Failure is `PRECURSOR_DISCOVERY_INVALID`. Log loss clips probabilities to `[1e-12, 1-1e-12]` after the probability. Brier uses the raw probability. Calibration is an unpenalized logistic of `Y` on `logit(clip(p, 1e-6, 1-1e-6))`. The slope is not a recalibration.

Primary uncertainty: ISO-week resampling of stored probabilities, `B = 2000`, seed `20261121`, no refit. At least 1900 finite draws. Percentiles 0.025 and 0.975.

2020–2022 is the development block. 2023–2024 is a predeclared temporal diagnostic on the same exposed surface. It is not independent confirmation.

Alert rule, for practical counts only: `p_candidate >= p_b1 + 0.05`. Report precision, recall, missed-impulse share, false alarms per scored UTC day, alerts per day, and lead time from `T` to the catalog touch among warned episodes.

Reliability bins of the candidate probability: `(-inf, 0.15), [0.15, 0.25), [0.25, 0.35), [0.35, 0.45), [0.45, inf)`.

## Verdict

`delta` means candidate minus B1.

- `PRECURSOR_DISCOVERY_INVALID`: non-convergence, leakage, a non-constant geometric probability, fewer than 1900 bootstrap draws, or a missing era block.
- `PRECURSOR_DISCOVERY_NO_INCREMENTAL_INFORMATION`: `delta_brier >= 0` or `delta_logloss >= 0`.
- `PRECURSOR_DISCOVERY_PROMISING`: both point deltas negative, both bootstrap upper bounds negative, calibration slope `>= 0`, and both era blocks have negative `delta_brier`.
- `PRECURSOR_DISCOVERY_WEAK`: every remaining finite case.

`PROMISING` is a reason to freeze a successor. It is not a confirmed edge, not a live probability, and not a trading result. AUROC does not enter the verdict. Diagnostic `K` does not enter the verdict.

## Mind-changer

The candidate fails to improve both Brier and log loss on B1, or the Brier interval does not lie below zero, or the 2023–2024 block does not keep the sign.

## Tracks

`STRUCTURE` and `PRODUCT_EVIDENCE`. Not `EDGE`. Ladder ceiling inside this unit: L2 historical frequencies. No L3 wording.
