# FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1

`outcome_read = false`
`future_association_read = false`
`accrued_analysis_n = 0`
`status = AWAITING_START`
`mode = PROSPECTIVE_SEQUENTIAL_VALIDATION`

This note freezes a prospective sequential validation of one already selected claim. It is not a discovery. It is not another historical surface. The historical loop for this claim is closed.

No forward association is computed in this change. The evaluator returns `REFUSING_OUTCOME_BEFORE_OWNER_GO` and does not load a panel.

## Question

Does the positive incremental relation of formation width to next-hour activity, given formation-hour realized volatility, persist on forward Binance bars that open only after this freeze, and does that forward information support a practically meaningful magnitude around `+0.10`, without retuning the historical object?

## Exact claim

Relative width of the just-completed UTC formation hour has a positive monotone association with realized activity of the next hour, and that association remains after contemporaneous realized volatility of the same formation hour.

The object, the endpoint, the covariate, the rank procedure, the UTC hour, and the 60-minute horizon are unchanged.

| identity | value |
| --- | --- |
| discovery design SHA256 | `64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6` |
| amendment A1 SHA256 | `a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e` |
| amendment A2 SHA256 | `a76c0a891fedb7a907544878ef49cd136d3831fb6782d89e56a00ce96e49e07a` |
| discovery result SHA256 | `333f5a778bf56207c3d6f8261d528a2d3271cdc523aba1239c3f013022466669` |
| discovery read | `2026-10-09T05:40:02Z` |
| discovery route | `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` |
| supporting endpoint | `ACTIVITY` |

## Definitions

Formation: UTC `[00:00, 01:00)`, twelve 5-minute bars. Decision time `T = 01:00` UTC.

State: `V = (high − low) / P0`. `P0` is the close of the last formation bar. Usable means the twelve bars are finite, `high ≥ low`, width is positive, and `low < P0 < high`.

Future endpoint: `ACTIVITY = RV_NEXT = sqrt(sum r_k^2)` on the twelve log returns whose ends lie in `[01:00, 02:00)`. Return pairs are `(form+11, form+12)` through `(form+22, form+23)`, with `form` the 00:00 bar.

Covariate: `RV_FORMATION = sqrt(sum r_k^2)` on the twelve formation-hour log returns. Return pairs are `(form−1, form)` through `(form+10, form+11)`. The two return sets are disjoint. They share only `close[form+11] = P0`.

Primary statistic: partial Spearman of `V` with `ACTIVITY` given `RV_FORMATION`.

Procedure:

1. average ranks, mergesort, ties averaged;
2. OLS of `rank(V)` on `rank(RV_FORMATION)` plus an intercept;
3. OLS of `rank(ACTIVITY)` on `rank(RV_FORMATION)` plus an intercept;
4. Pearson correlation of the two residual vectors.

One covariate. Degenerate when the residual sum of squares is at most `1e-12` of the total sum of squares, or the length is under 3.

Analysis row: usable formation, complete `RV_FORMATION` close span, and complete next-hour close span. `RV_PREV` is not required. A row counts only when its formation date is on or after the prospective start.

Not in this unit: displacement, a high-low future range, a signed return, a thresholded activity, `RV_PREV`, ATR, open interest, funding, volume, taker flow, another UTC hour, another horizon, a second covariate.

## Frozen historical context

These numbers are provenance. They are not an empirical prior. They do not choose the checkpoint grid, the spending exponent, or the alpha. They are not rounded onto the reference.

| source | value | role |
| --- | --- | --- |
| Binance discovery partial Spearman | `+0.10245095315584887` | context |
| Bybit cross-venue partial Spearman | `+0.09903883442772482` | context |
| Bybit route | `POSITIVE_BUT_BELOW_PRACTICAL_SCALE` | context |

The Bybit point is not `0.10`. The sign and the rough scale repeated on that exposed same-calendar tape. The exact practical claim `rho >= +0.10` did not receive cross-venue confirmation. The discovery result on `CORE_BTC_BINANCE_V0` `2020-01-01..2024-12-31` is unchanged.

Scientific reference, unchanged: `+0.10`.

## Why this is not another historical read

`CORE_BTC_BINANCE_V0` `2020–2024` is consumed for this cell. Bybit `2020-04-01..2024-12-31` is consumed for this cell. Spot `2017-09-01..2019-12-31` was read only for path presence and was informationally weak; that endpoint stays unread and is not reopened here.

BitMEX is not opened. No further historical venue is opened. `PRODUCT_DECISION_V2` §4 opened Binance USD-M BTCUSDT `2025/2026` 5-minute history for product statistics, and for research that surface is consumed for hypotheses over range and volatility. It is not a prospective sample. E1 `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` is not read. This start sits after that holdout.

## Prospective start

`PROSPECTIVE_START = 2026-10-10T00:00:00Z`.

This design is written on `2026-10-09`, after `08:28Z`. On that calendar date the formation hour `[00:00, 01:00)` and the activity hour `[01:00, 02:00)` had already closed, and the Bybit outcome had been read at `2026-10-09T07:56:02Z`. A start of `2026-10-09T00:00:00Z` would put an already closed endpoint inside the prospective sample.

The legal boundary is the next UTC midnight. The first admitted formation date is `2026-10-10`. The first decision time is `2026-10-10T01:00:00Z`. The first endpoint window is `[2026-10-10T01:00:00Z, 2026-10-10T02:00:00Z)`. That window is not read now.

The rule is the same shape as the level-volatility prospective start: the first UTC midnight strictly after the design commit, with no market bar used to choose it. The precedent unit committed on `2026-10-08` and therefore started `2026-10-09`. This unit is a day later, so its midnight is a day later. If the commit that adds this file is at or after `2026-10-10T00:00:00Z`, this boundary is illegal and the start moves to the following midnight. `2026-10-10` is not backfilled.

Accrued analysis N at this design is 0. The product table is not opened to count bars.

## Venue

Primary venue: Binance USD-M BTCUSDT perpetual. Atlas dataset `BINANCE_UM_LIVE_FORWARD`. Scientific column `CANDLES`. Availability `FORWARD_ONLY`.

One venue in the primary statistic. Bybit and OKX are not pooled with Binance. They are not a V1 robustness layer. A later robustness layer would be a separate design.

Exposure class for formation dates on or after the start, for this exact claim only: `PROSPECTIVE_AFTER_FREEZE`. It is not a reread of the 2020–2024 discovery tape, not a reread of Bybit, and not the product `2025/2026` archive. It is not called a pristine historical confirmation. Neighboring product use of earlier range features does not score this forward cell.

## Why not an always-valid sequence

An always-valid confidence sequence for this partial Spearman would need a martingale or a mixingale bound for a rank residual correlation under serial dependence. The published lag-1 rank correlation of relative width on the discovery tape is about `0.55`. Partial Spearman is not a sample mean. No such bound is derived here. Inventing one would be pseudo-theory.

The frozen method is sparse checkpoints plus alpha spending. There is no look between checkpoints and no daily decision.

## Information forecast, separate from the test

The forecast uses `information_forecast` from the confirmation package. It is labeled `FORECAST_ASSUMPTION`. It is not the inferential engine.

Inputs, all published and not recomputed from a tape in this unit:

- phi `0.5483151377537036`, the discovery feasibility lag-1 average-rank correlation of relative width;
- analysis days per ISO week `1820/262`;
- analysis accrual `1820/1827` of calendar days.

Negative phi would be set to 0 and phi is capped at `0.95` inside the imported function. This phi is inside that range. Phi is not refit on forward width.

Week sizes in the forecast are as equal as possible and sum to the candidate N, with the week count `round(N * 262 / 1820)`. Effective N is the Kish size under an AR(1) inside each week. The standard error is the Fisher error `1/sqrt(n_eff − 3)`. Single-look power is the normal power of a one-sided `0.05` lower bound when the planted value is `+0.10`.

The AR(1)-Kish model forecasts precision. The test at a checkpoint is the bootstrap below.

## Checkpoint rule

Annual candidates considered: `365, 730, 1095, 1460, 1825, 2190`. Also reported and not eligible for admission: `90, 180, 540`.

1. Maturity is the smallest annual candidate whose forecast 80% MDE is at most `+0.10`. That candidate is `N = 1825`.
2. Terminal is the next annual candidate after maturity. That candidate is `N = 2190`. Nothing after `2190` is a checkpoint. The grid is not extended because a later year looks attractive.
3. The first look is the earliest annual candidate before the terminal whose power, as a first look, is at least `0.50`. That power uses the spent alpha `0.05 * t`, where `t` is forecast effective N divided by forecast effective N at the terminal. The first look is `N = 1095`.
4. A later annual candidate is admitted only when the alpha increment it would spend, given the looks already admitted, has sequential power at least `0.50` for a lower bound above 0 at planted `+0.10`. `N = 1460` fails that increment. `N = 1825` passes. The terminal is always the last look.

`N = 90`, `180`, `365`, and `540` have single-look power below `0.50` (`0.138`, `0.200`, `0.313`, `0.408`). They are not checkpoints.

`N = 730` has single-look power `0.500` at alpha `0.05`, and sequential power about `0.315` if it were the first look under this spending. The single-look figure is not the gate. `730` is not a checkpoint.

Admitted checkpoints:

| N | role | forecast effective N | forecast SE | MDE80 | information time | incremental alpha | sequential power | expected formation date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1095 | first look | 410.96 | 0.04951 | 0.1231 | 0.5004 | 0.025021 | 0.524 | 2029-10-13 |
| 1825 | maturity | 684.71 | 0.03830 | 0.0952 | 0.8337 | 0.016667 | 0.685 | 2031-10-16 |
| 2190 | terminal | 821.24 | 0.03496 | 0.0869 | 1 | 0.008313 | 0.679 | 2032-10-16 |

Expected dates use calendar span `N * 1827/1820` from `2026-10-10`. They move later if forward completeness is worse than the discovery accrual rate. They do not move earlier by admitting pre-start days. The sample at checkpoint `N_k` is the first `N_k` analysis rows in calendar order. A day adds at most one row, so the count does not jump over a checkpoint.

Information time is frozen from this forecast. It is not recomputed from prospective residuals or from a new phi.

Minimum first look: analysis N `1095`, about 158 ISO weeks, forecast effective N `411`. Before that, the only state is `PROSPECTIVE_INFORMATION_IMMATURE`. No owner go authorizes a look at a smaller N.

Maximum horizon: analysis N `2190`. Expected formation date `2032-10-16`. There is no further look.

## Alpha spending

Two one-sided families, each with total alpha `0.05`. The spending function is the Kim–DeMets power family with exponent `1`: cumulative alpha `0.05 * t`. Exponent `3` was rejected because it leaves the first look with sequential power near `0.10`, which recreates a single late test. Exponent `1` spends in proportion to forecast information, and every admitted look has sequential power at least `0.50` under that spend.

At look `k`, the increment is `delta_k = 0.05 * t_k − 0.05 * t_{k−1}`, with `t_0 = 0`. The three increments sum to `0.05`.

The bootstrap lower quantile is `delta_k`. The bootstrap upper quantile is `1 − delta_k`. The same increments are used for both families. Under positive dependence of successive looks, the probability of ever claiming a lower bound above 0 when the association is not positive is at most `0.05`, and the probability of ever claiming an upper bound below `+0.10` when the association is at least `+0.10` is at most `0.05`. This is a union bound on the increments. It is not an always-valid continuous sequence.

If the truth equals `+0.10`, the probability that the lower bound is at least `+0.10` stays near the spent increment. That route is a strong claim. It is not expected to fire merely because the truth sits on the reference. Compatibility with the reference, without establishing the lower bound at `+0.10`, is a different state.

## Inference at a checkpoint

ISO-week block bootstrap. The week is the ISO week of the formation date. Weeks are drawn with replacement. Every analysis row in a drawn week enters. Ranks are recomputed inside the draw. The only scored cell is the partial correlation.

- draws `B = 2000`;
- seed `20261109`, a new Generator at every checkpoint, not a stream continued from an earlier look;
- a draw is finite when the partial correlation is finite;
- the look is interpretable only when at least 90% of draws are finite;
- quantile method is the NumPy linear percentile, matching the earlier formation-width bootstraps;
- no other cell is scored inside the draw.

The smallest increment is about `0.008`, so the upper and lower percentiles sit near order statistics 17 and 1983 of 2000 draws. That Monte Carlo error is accepted. `B` is not raised after a look.

A non-interpretable look before the terminal does not stop and does not reallocate its alpha. The next look keeps its predeclared increment.

## Decision rules

Stopping routes, first match:

1. Interpretable, point strictly positive, and lower bound at least `+0.10`: `PROSPECTIVE_PRACTICAL_MAGNITUDE_SUPPORTED`. This may stop at any formal checkpoint.
2. The checkpoint is maturity or terminal, the look is interpretable, and the upper bound is strictly below `+0.10`: `PROSPECTIVE_PRACTICAL_MAGNITUDE_NOT_SUPPORTED`.
3. The checkpoint is terminal, the look is interpretable, the point is strictly positive, and the lower bound is strictly above 0: `PROSPECTIVE_POSITIVE_RELATION_SUPPORTED`.
4. The checkpoint is terminal and none of the above fired, including a non-interpretable terminal look: `PROSPECTIVE_INCONCLUSIVE_AT_TERMINAL`.

Before maturity, an upper bound below `+0.10` does not stop and is not called magnitude-not-supported. The first look can stop only for the strong magnitude route.

While accrual continues, a look with a positive point and a lower bound strictly between 0 and `+0.10`, and an upper bound at least `+0.10`, is recorded as an interim positive relation. That label is not a stop. The unit keeps accruing. The route is not final until a stopping rule fires.

Before `N = 1095` the state is `PROSPECTIVE_INFORMATION_IMMATURE`. No interval is computed.

The point estimate is not compared with `+0.10` as a pass/fail knife-edge. `+0.099` and `+0.100` are not different routes. The interval is the decision.

## Lag placebo

Option A. The lag partial is a specificity diagnostic on the stopping sample only. It is not computed at a look that continues. It is not a route input. It is not a second sequential gate.

Definition, unchanged in form: partial Spearman of today's `V` with the previous analysis row's `ACTIVITY`, given today's `RV_FORMATION`, on the stopping sample. If that point is defined on at least 100 pairs and its absolute value is at least the absolute primary point, the wording does not claim current-state specificity. The route name does not change.

## Stability

Not a route input. No calendar-year search. No regime hunt.

When a checkpoint is scored, `N` is at least `1095`, which is above the minimum `365`. Split the scored rows in calendar order at `floor(N/2)`. Report the two partial points. Strictly opposite signs are noted. They do not veto the route. Zero is not a sign. There is no second boundary.

## Routes and evidence ceiling

Historical state, already earned, unchanged by this design: L2 discovery on Binance `2020–2024`, plus cross-venue support that the sign and the rough scale repeated on Bybit, while exact practical confirmation at `+0.10` did not pass.

| route | when | ceiling |
| --- | --- | --- |
| `PROSPECTIVE_INFORMATION_IMMATURE` | before N `1095`, or a continuing look that has not stopped | no new prospective evidence; historical L2 stands |
| `PROSPECTIVE_POSITIVE_RELATION_SUPPORTED` | terminal, lower bound above 0, lower bound below `+0.10`, upper bound at least `+0.10` | prospective L2 that the forward association is positive after `RV_FORMATION`; magnitude at `+0.10` is not established |
| `PROSPECTIVE_PRACTICAL_MAGNITUDE_SUPPORTED` | any checkpoint, lower bound at least `+0.10` | prospective L2 that the forward lower bound reached the reference under the spent alpha |
| `PROSPECTIVE_PRACTICAL_MAGNITUDE_NOT_SUPPORTED` | maturity or terminal, upper bound below `+0.10` | prospective L2 that the forward interval is incompatible with the reference; discovery numbers are not rewritten |
| `PROSPECTIVE_INCONCLUSIVE_AT_TERMINAL` | terminal, interval still crosses the decision region, or the look is not interpretable | no resolution; historical L2 stands |

None of these routes is L3. L3 would require a predeclared probability mapping and a live calibration count in the claim journal. An association check is not that mapping. This unit does not authorize L3 wording.

`PRODUCT_INTEGRATION_CANDIDATE = NO` on every route. A later pass does not change `/btc`, a push, copy, a probability, or a recommendation. Product use needs a separate owner decision after a result.

## What stays unread until a separate go

The evaluator refuses before any load. A separate owner go is required for the first formal checkpoint, and only once analysis N has reached `1095`. That go is not given here. It does not authorize a smaller N, a BitMEX read, another historical venue, a change of hour, horizon, state, covariate, or reference, a pooled venue statistic, or a product change.

Between checkpoints the association is not computed. A first look before `N = 1095` is a breach of this note.
