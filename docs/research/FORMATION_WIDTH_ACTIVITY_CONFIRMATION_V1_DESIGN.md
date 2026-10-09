# FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1

`outcome_read = false`
`claim_selected_pre_outcome = true`
`mode = CONFIRMATION`

This note freezes one confirmation of one already selected claim. It is not a discovery search. It does not retune the hour, the window, the state, the endpoint, the covariate, the rank method, the practical bar, or the sign.

## Selected claim

Relative width of the just-completed UTC formation hour has a positive monotone association with realized activity of the next hour, and that association remains after contemporaneous realized volatility of the same formation hour.

The claim was selected by `FORMATION_WIDTH_REGIME_V1` on `CORE_BTC_BINANCE_V0` `[2020-01-01, 2025-01-01)`.

| identity | value |
| --- | --- |
| discovery design SHA256 | `64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6` |
| amendment A1 SHA256 | `a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e` |
| amendment A2 SHA256 | `a76c0a891fedb7a907544878ef49cd136d3831fb6782d89e56a00ce96e49e07a` |
| pre-outcome evaluator | `b1f36a56a5dfefd96f344238cf1bf071f6c42884` |
| evaluator digest | `94c01af8e2ab9e2a9abc7e7eff54dd92e8dc57afe5e11bf2e948e0e60a8dab31` |
| result file SHA256 | `333f5a778bf56207c3d6f8261d528a2d3271cdc523aba1239c3f013022466669` |
| result read | `2026-10-09T05:40:02Z` |
| discovery route | `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` |
| supporting endpoint | `ACTIVITY` |
| ACTIVITY foundation Spearman | `+0.6811016466273577` |
| ACTIVITY partial Spearman given `RV_FORMATION` | `+0.10245095315584887` |
| family interval | `[+0.04797984625391018, +0.15534901403484885]` |
| practical bar already frozen | `\|rho\| >= 0.10` |
| discovery sign | positive |

`DISPLACEMENT` is not a confirmation target. Its incremental partial Spearman was `+0.01393879464962625` and did not clear. Raw foundation Spearman is context at a later read. It is not a second target. `RV_PREV` is not a covariate and not a route input. The discovery estimate `+0.1025` is not a new magnitude target.

## Exposure audit

The exact incremental cell was computed once, on `CORE_BTC_BINANCE_V0` `2020-01-01..2024-12-31`. That surface is `CONSUMED`. Reading it again would be `EXACT_CLAIM_REANALYSIS`.

`BINANCE_UM_KLINES_5M_PRODUCT` `2025-01-01` through yesterday is the same contract and is time-disjoint, and the exact partial cell has not been computed there. It is not a confirmation surface for this claim. `PRODUCT_DECISION_V2` §4 says 2025/2026 Binance BTCUSDT is no longer an untouched window for a research claim whose features overlap range and volatility, and that such a claim needs a different window or a prospective test. The atlas marks that period `PRODUCT_OPEN` on `VOLATILITY_STATE.range_forecast`. `FORECAST_LAYER_DECISION_V1` reserves the same history for one later level-race read. The discovery unit's reopen line also keeps 2025/2026 closed. E1 `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` stays reserved.

No pinned Binance USD-M BTCUSDT 5m tape exists before `2020-01-01`. A prospective panel from `2026-10-09` is not a mature holdout.

`DH1_BITMEX_XBTUSD_TRADES_5M_V0` `2017-09-01..2019-12-31` is time-disjoint and the exact cell is unread there. It is a different venue, and that tape already consumed a paired 60-minute realized-volatility transition. That neighbor is closer to this endpoint than a 4h barrier contrast.

## Chosen surface

`DH1_BINANCE_SPOT_BTCUSDT_5M_V0`, months `2017-09` through `2019-12`, events `[2017-09-01, 2020-01-01)`.

Same exchange, same BTCUSDT quote, same 5-minute kline grid, time-disjoint from the discovery window, research inventory rather than the product history database. The exact partial cell has not been computed on it.

Exposure class: `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`.

It is not pristine. `FROZEN_HOUR_EQUAL_WIDTH_V1` already consumed a width-held 4h resolution contrast on this window (`2026-10-08T22:02:27Z`, route `NO_WIDTH_HELD_RESOLUTION_DIFFERENCE`). That is a neighboring future path with a different estimand, a 4h barrier, and a different question. DH1 feasibility also counted spot states here without an outcome. Under `EXPOSURE_WEIGHTING_DECISION_V1` the replication is allowed because the claim was frozen on the discovery surface before any read of this cell. The wording stays short of pristine.

The contract is spot, not the USD-M perpetual. A later pass speaks about Binance spot BTCUSDT over this window.

One surface only. If the information forecast below fails, this unit does not open a second surface.

## Estimand

State, unchanged:

`V = (high − low) / P0`

of the twelve 5-minute bars in UTC `[00:00, 01:00)`. `P0` is the close of the 00:55 bar, at `T = 01:00` UTC. Usable means those twelve bars are finite, `high ≥ low`, width is positive, and `low < P0 < high`.

Endpoint, one:

`ACTIVITY = RV_NEXT = sqrt(sum r_k^2)`

over the twelve log returns whose end bars lie in `[01:00, 02:00)`. Return pairs are `(form+11, form+12)` through `(form+22, form+23)`, with `form` the 00:00 bar. This is the discovery future index.

Covariate, one:

`RV_FORMATION = sqrt(sum r_k^2)`

over the twelve formation-hour log returns. Return pairs are `(form−1, form)` through `(form+10, form+11)`. The close span is 13 closes, `form−1` through `form+11`. The return sets of `RV_FORMATION` and `ACTIVITY` are disjoint. They share only `close[form+11] = P0`.

Primary statistic, one cell:

partial Spearman of `V` with `ACTIVITY` given `RV_FORMATION`.

Procedure, the discovery rank-residual procedure:

1. average ranks, mergesort, ties averaged;
2. OLS of `rank(V)` on `rank(RV_FORMATION)` plus an intercept;
3. OLS of `rank(ACTIVITY)` on `rank(RV_FORMATION)` plus an intercept;
4. Pearson correlation of the two residual vectors.

One covariate. No joint regression. Degenerate when the residual sum of squares is at most `1e-12` of the total sum of squares, or the length is under 3.

Analysis row: usable formation, complete `RV_FORMATION` close span, and complete next-hour close span `form+11` through `form+23` (13 closes, finite and positive). The previous-hour `RV_PREV` span is not required.

## Direction and success

The discovery sign is positive. Confirmation is directional: `rho_partial > 0`. A negative estimate does not confirm the claim, including when its interval excludes 0.

The cell passes the statistical and practical rule only when all of the following hold:

1. point estimate `rho_partial >= +0.10`;
2. the one-sided 95% lower bound is strictly above 0;
3. the sign is positive;
4. the information floor in this note passed before the outcome;
5. the stability rule passes;
6. the lag-placebo specificity rule passes.

The practical threshold stays `+0.10`. It is not lowered, and it is not replaced by the discovery point `0.1025`.

## Inference, frozen before any outcome

One primary cell, so the discovery two-cell quantiles `0.0125` and `0.9875` are not used.

- alpha: `0.05`, one-sided, positive direction;
- interval: ISO-week block bootstrap percentile;
- lower decision bound: quantile `0.05`;
- upper descriptive quantile: `0.95` (a central 90% interval is stored; the decision uses the lower end);
- draws: `B = 2000`;
- seed: `20261108`, one NumPy Generator, not a previously used seed;
- ranks recomputed inside each draw;
- weeks are the ISO week of the formation date, drawn with replacement;
- a draw is finite when the partial correlation is finite;
- the cell is interpretable only when at least 90% of draws are finite;
- within the single draw the only scored cell is the partial correlation.

Raw Spearman of `V` with `ACTIVITY` may be printed as a point, with no interval and no route input.

## Information floor, frozen before the census

The support census may run before any outcome. It may count calendar span, complete formations, `RV_FORMATION` span presence, next-hour path presence, analysis N, ISO weeks, year and month coverage, missingness, the width distribution, and the lag-1 rank correlation of relative width. It must not compute `ACTIVITY`, a return on the next hour, raw Spearman, partial Spearman, or any future association.

The sample is informationally adequate only when every line below holds:

- analysis N `>= 500`;
- ISO weeks `>= 100`;
- each calendar half has analysis N `>= 100`;
- lag-1 width pairs `>= 30` and the correlation is finite;
- width `p90/p10 >= 1.05`;
- under the dependence model below, power to obtain a positive lower bound at a planted association of `+0.10` is at least `0.80`.

Dependence model, outcome-blind: take the lag-1 average-rank correlation of relative width on the analysis sample; set negative values to 0 and cap the value at `0.95`; treat that number as an AR(1) correlation inside each ISO week; convert block sizes to a Kish effective N; use the Fisher standard error `1/sqrt(n_eff − 3)`. Power is the normal power of the one-sided 95% lower bound. This uses persistence of the state as a stand-in for persistence of the later residual association. It does not use the endpoint.

Two descriptive standard errors are stored and do not set the gate: independent days, and one draw per ISO week. The week-total bound is harsher than the discovery bootstrap of this same cell, which stayed close to the independent-day error, so it is not the gate.

When the planted association equals the bar `0.10`, the probability that the point estimate also clears `0.10` is at most one half. That probability is reported. It is not the adequacy gate. The gate is power to exclude 0. The bar remains a separate magnitude rule.

If any floor line fails, the pre-outcome route is `INFORMATIONALLY_WEAK_BEFORE_OUTCOME`. The endpoint stays unread. No second surface is opened inside this unit. A later owner go does not authorize the endpoint on a sample this note has already called weak.

## Stability

One split, frozen on the calendar, not on a result.

Boundary: `2018-11-01T00:00:00Z`, the midpoint of the 852-day window `[2017-09-01, 2020-01-01)`.

After an authorized outcome read, compute the partial Spearman point on each half. The relation is temporally unstable when both halves have N `>= 100` and the two points have strictly opposite signs. Zero is not a sign. There is no year search and no second boundary.

## Lag placebo

Discovery compared the absolute lag Spearman of today's `V` with the previous analysis day's endpoint to the absolute foundation Spearman. That comparison is attached to the foundation cell. Copying it onto this confirmation would mix the raw association with the incremental cell.

The guard that matches the selected cell, with the same previous-analysis-row alignment:

`lag_partial` is the partial Spearman of today's `V` with the previous analysis row's `ACTIVITY`, given today's `RV_FORMATION`.

`current_state_specific` is true when `lag_partial` is defined on at least 100 pairs and `|lag_partial| < |rho_partial|`.

Both sides use the same rank-residual procedure and the same covariate. The comparison is a point comparison. It is not bootstrapped. It is a route requirement, declared here, before any outcome. If it fails while the magnitude and the interval would otherwise pass, the route is `NO_CONFIRMATION_OF_INCREMENTAL_ACTIVITY_RELATION` with reason `LAG_PLACEBO_SPECIFICITY_NOT_SATISFIED`. That reason is not a new route name.

## Routes

Evaluated in this order. The first match wins.

1. Information floor failed before the outcome: `INFORMATIONALLY_WEAK_BEFORE_OUTCOME`. The endpoint stays unread.
2. The cell is not interpretable, or the point is not strictly positive, or the lower bound is not strictly above 0: `NO_CONFIRMATION_OF_INCREMENTAL_ACTIVITY_RELATION`.
3. The point is strictly positive, the lower bound is strictly above 0, and the point is below `+0.10`: `POSITIVE_BUT_BELOW_PRACTICAL_SCALE`.
4. The point is at least `+0.10`, the lower bound is strictly above 0, and the stability rule fails: `TEMPORALLY_UNSTABLE_CONFIRMATION`.
5. Those lines pass and the lag-placebo rule fails: `NO_CONFIRMATION_OF_INCREMENTAL_ACTIVITY_RELATION`, reason `LAG_PLACEBO_SPECIFICITY_NOT_SATISFIED`.
6. All lines pass: `CONFIRMED_INCREMENTAL_ACTIVITY_RELATION`.

No discovery route is created. `DISPLACEMENT`, other hours, a 4h horizon, ATR, percentiles, z-scores, bins, a nonlinear control, open interest, funding, and taker flow are outside this unit.

## What a pass can say

A pass is L2 historical evidence: on this time-disjoint exposed spot window, the frozen incremental association was positive, at least `+0.10`, and its one-sided 95% lower bound excluded 0, with the frozen stability and specificity rules.

A pass is not a live calibrated probability, not a forecast, not an edge, not a causal claim, and not a product line. L3 would require prospective or live calibration of this exact claim class. This historical confirmation does not create that calibration. The exposure class stays `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`, so the result is not called pristine. The sentence is about Binance spot BTCUSDT on `2017-09-01..2019-12-31`, not about the USD-M perpetual and not about 2025/2026.

## What a failure can say

If the route is `NO_CONFIRMATION_OF_INCREMENTAL_ACTIVITY_RELATION`, `POSITIVE_BUT_BELOW_PRACTICAL_SCALE`, or `TEMPORALLY_UNSTABLE_CONFIRMATION`, the discovery result remains a discovery result on the exposed perpetual surface. This unit did not confirm the incremental claim on the spot window. No product wording follows. The discovery numbers are not rewritten.

If the route is `INFORMATIONALLY_WEAK_BEFORE_OUTCOME`, there is no new evidence about the association. The endpoint was not read. The discovery result is unchanged. The weakness is a property of this frozen surface under the frozen forecast, not a reason to choose another tape inside this unit.

## Evaluator

Until a separate owner go, `scripts/research/formation_width_activity_confirmation_v1/evaluate.py` returns only `REFUSING_OUTCOME_BEFORE_OWNER_GO`. It does not load the panel. Support code does not compute `ACTIVITY`. Tests of the gate and of the forecast are synthetic.

A later go, if the information status is `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`, is one read of this single cell on this single surface, with the rules in this note. That go is not given here.
