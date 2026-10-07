# LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any feature is joined to a late resolution label. A null is a complete result. The unit does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment.

## Question

Structural first touch is an independently replicated event zone. Pre-touch static properties, approach geometry, OI, taker flow, their joint state, and broad ±1% book liquidity did not reliably separate BREAK, REJECT, and NEITHER.

The decision time now moves. After the touch, 15 minutes of new information exist. Which simple point-in-time reactions of price, activity, taker flow, and open interest, if any, carry historical information about what happens after those 15 minutes?

This is a state update: touch, observe 15 minutes, update. It is not a forecast from before the touch.

## What is already established

`LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1` replicated the resolution difference of a real structural first touch against a matched pseudo-price (BitMEX 2017–2019, Δ RESOLVE +8.0 pp, 95% +4.4..+11.8). Later discovery units on Binance did not find a robust incremental account of that resolution in pre-touch structure, approach, positioning, flow, joint state, or local book state. Those nulls are not rescued here.

## Novelty audit

Closed breakout objects stay closed.

| Object | What it tested | Why this unit is not that object |
|---|---|---|
| H02 | A 5m bar that opens and closes inside a 60/120/240m range and wicks through it, then a signed return over 15–240m. Verdict `H02_KILL`. | Population is a rolling-range wick, not a #352 structural first touch. Outcome is a signed return, not the remaining barrier passage. |
| B2-02 | Breakout cell on CORE BTC, closed on the surface. | Same breakout row. This unit does not reopen it. |
| V2 `CONFIRMED_BREAKOUT` | First 5m close beyond a 48-bucket 1h high or low, plus a directional-context gate. Stage-5 qualification. Retired formulation. | Different level definition, different clock, and a qualification flag this unit does not emit. |
| Episode false-break | Stage-6 lifecycle rule. | Not evaluated. |

The new object is a conditional post-touch update on an independently replicated structural first touch.

1. Population: #352 first touches of PDH, PDL, PWH, PWL, PMH, PML only.
2. The touch has already happened.
3. Decision boundary D = T + 15 minutes.
4. Predictors use only information that has appeared by D, and the reaction pieces use bars that open at or after T.
5. The predictive sample is events that have not reached either barrier by D.
6. The outcome starts after D and ends on the original T+4h boundary.
7. There is no generic breakout detector, no acceptance flag, and no failed-break flag.

Atlas row: `PRICE_STRUCTURE.levels`. Reopen key: `NEW_MECHANISM`. This is further exposure of an already consumed level surface, so the run is `DISCOVERY_ONLY`. It is not `CONFIRMATION_ON_EXPOSED` and not a functional relabel of `PRICE_STRUCTURE.breakout`.

`BLOCKED_REOPENING_BREAKOUT_CELL` does not apply.

## Data

Price, quote volume, and taker-buy quote: `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. Complete 5m aggregates. No 2025/2026 object. No E1 holdout.

Open interest: `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0`, snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`, `sum_open_interest` only. Native 5m. `available_at = period_start + 5m`. Funding is not opened. Long/short ratios, top-trader ratios, liquidations, the order book, spot, Bybit, and OKX are not read. No threshold or sign is taken from #358 or #359.

## Event window

Inclusive start `2020-09-01T00:05:00Z`. That is the first touch time at which an OI print is legally available. A 60-minute OI path is not required, so the start is earlier than the #358 01:05Z bound. The 24h price lookback sits inside the CORE panel. Exclusive end `2025-01-01T00:00:00Z`.

## Clocks

T is the open time of touch bar `j`, the bar `[T, T+5m)`.

D = T + 15 minutes. At D the three bars `j`, `j+1`, `j+2` are closed. That is `[T, D)`.

The parent #352 outcome starts at `j+1` and ends at `j+48`. The touch bar is not turned into a BREAK or a REJECT.

Early resolution uses that same barrier rule on `j+1` and `j+2` only. If either barrier is reached there, or both are reached on the same bar, the event is `EARLY_RESOLVED` or `EARLY_AMBIGUOUS`. It is counted and then left out of the predictive sample. Predictors of early events are not compared as a result.

`UNRESOLVED_AT_D` means neither barrier has been reached on `j+1` or `j+2`.

The late window is `j+3` through `j+48`. It ends on the original 4h bar. It is not extended by 15 minutes. About 3h45m remain.

## Features

All reaction features are known at D. The maximum set is five. Simplicity order is the order below. A later feature is dropped before outcomes if `|rho| >= 0.90` with an earlier retained feature, or if it has no variation. Nothing is dropped after a look at Y.

**R1 `END_POSITION_X`.** Close of bar `j+2`, in units of the barrier distance. From below: `(close_D - zone_high) / (zone_high × X)`. From above: `(zone_low - close_D) / (zone_low × X)`. Positive means the close sits beyond the zone in the break direction. This is not an acceptance class.

**R2 `RELATIVE_ACTIVITY_15M`.** `POST_QV` is the sum of quote volume on `j..j+2`. `PRE_QV_RATE` is the sum of quote volume on the twelve bars `[T-60m, T)` divided by 4. Feature: `log(POST_QV / PRE_QV_RATE)`. Every bar in both windows must be finite and nonnegative, and both sums must be positive. Otherwise the feature is missing.

**R3 `ORIENTED_TAKER_REACTION_15M`.** On the three post-touch bars, pooled `(buy_quote - sell_quote) / total_quote`, multiplied by the #352 approach side. Positive means aggressive flow continues in the break direction. The formula is the #358 imbalance on this shorter window.

**R4 `TAKER_CHANGE_VS_PRE`.** R3 minus the #358 oriented taker imbalance on `[T-60m, T)`.

**R5 `OI_REACTION_15M`.** `log(OI_D / OI_T)`. `OI_T` is the latest print with `available_at <= T`. `OI_D` is the latest print with `available_at <= D`. Each age must be between 0 and one native period (5 minutes) inclusive. A longer gap is missing. The two prints must be distinct, and the D print must not be after D. Both values must be positive. Funding is not a substitute.

Not in this unit: closes beyond the level, time beyond the level, reclaim, false break, recross, penetration-and-reclaim, or a confirmed-breakout state. Those belong to a later acceptance-path unit if the owner asks for one.

## Sample, scaling, outcomes

Primary rows are unresolved at D, with the predeclared nuisance fields present, and with the feature present. R2–R5 also require R1, because R1 is their nuisance.

Scaling is standard z, `(x - mean) / sd`, `ddof = 0`, plus tertile cuts at one third and two thirds for shape only. Moments are frozen on unresolved, nuisance-complete rows (feature moments on rows where that feature is finite). No clip. No threshold. No percentile state.

**O1 `LATE_RESOLVE_BY_4H`.** 1 if the first passage after D and by `j+48` is BREAK or REJECT. 0 if that window ends NEITHER. AMBIGUOUS is excluded.

**O2 `LATE_BREAK_GIVEN_RESOLVED`.** Among late BREAK and REJECT only: 1 = BREAK, 0 = REJECT.

Five features by two outcomes is ten primary cells if none is dropped.

## Nuisance and estimator

Every cell adjusts for level family (DAY reference), support versus resistance, year epoch (2020Q4 reference when present), the parent pre-touch volatility tercile, UTC 6-hour block, pre-touch approach displacement, and pre-touch relative quote activity. Displacement and the 60-minute taker baseline use the #358 definitions and stop at T. For R2–R5 the cell also adjusts for R1. R1 is not a covariate of itself. Reaction features are not entered as covariates of each other.

Estimator: linear probability model. The reported number is the adjusted historical probability change per +1 standard deviation. Cluster is the product week of the real touch. The stacked bootstrap puts both members of a pair on that week. Draws: 2000. Seed: `20261017`. Percentile 95% interval. Benjamini–Hochberg q = 0.10 on the ten primary cells only. Practical scale: 3 percentage points per +1 SD. Not lowered after the result.

## Specificity

The pseudo touch is the #352 half-rotation. Its price is not moved by the reaction. The same D, the same features, the same early exclusion, and the same remaining horizon are applied at the pseudo touch. Specificity is estimated only after a real cell passes the conjunction: stacked `β_real`, `β_pseudo`, and `Δ = β_real - β_pseudo`.

`LEVEL_POST_TOUCH_REACTION_CANDIDATE`: the real conjunction passes, `|Δ| >= 3` pp, the interval for Δ excludes 0, `|β_real| > |β_pseudo|`, and the signs of the real slope, the stacked real slope, and Δ agree.

`GENERIC_POST_TOUCH_STATE_CANDIDATE`: the real conjunction passes, the contrast is not material, the pseudo slope has the same sign, and its magnitude is at least half the real slope.

A large real-minus-pseudo gap does not rescue a null real effect. If the conjunction passes and neither label applies, the route is `STRUCTURE_PRESENT_BUT_UNSTABLE`.

## Candidate conjunction

All of the following, frozen before outcomes:

1. BH q ≤ 0.10.
2. Absolute effect at least 3 pp.
3. The 95% interval excludes 0.
4. At least four year epochs have N ≥ 30, and at least four of those eligible epochs keep the primary sign. One eligible epoch may differ.
5. Every leave-one-year-out refit with N ≥ 30 keeps the sign. A missing coefficient on such a refit fails.
6. Every leave-one-family-out refit with N ≥ 30 keeps the sign. A missing coefficient fails. There is no 70% DAY ceiling.
7. If both sides have N ≥ 30, their coefficients are not opposite signs. No side-specific candidate is created.
8. Point-in-time failure is structural: reaction slices stop before D, and a stale OI print is missing.

Epochs are 2020Q4, 2021, 2022, 2023, 2024. Families are DAY, WEEK, MONTH. MONTH may be small; that is reported with N, not promoted.

Shape is tertiles only. A U-shape is recorded as `EXPLORATORY_SUCCESSOR_IDEA` and is not fit.

## Information

Before outcomes the preflight reports a rough 80% minimum detectable effect under a Bernoulli bound and a design effect of 1.25. That number is context. It is not a gate and it does not lower the 3 pp scale. `INFORMATION_LIMITED` is available after the run if the largest late-resolve cell has N < 100 or fewer than 20 week clusters and no other route applies.

## Search exposure

One reaction window. Two outcomes. No interaction, no acceptance flag, no second lag, no horizon extension. Early counts are a census. They are not a third endpoint and not a real-versus-pseudo test.

## Routes

`POST_TOUCH_REACTION_STRUCTURE_PRESENT`, `GENERIC_POST_TOUCH_INFORMATION_ONLY`, `NO_INCREMENTAL_POST_TOUCH_REACTION_STRUCTURE`, `STRUCTURE_PRESENT_BUT_UNSTABLE`, `INFORMATION_LIMITED`. `BLOCKED_REOPENING_BREAKOUT_CELL` was the stop that the novelty audit did not take.

Claim ceiling: L2 historical association, discovery only. Not a current probability. Not a trade call. `SUCCESSOR_CANDIDATE` stays `NONE` inside this run. An acceptance-path unit, a 30-minute window, an interaction, a confirmation, or any other successor needs its own owner go.

## What this note does not do

It does not rerun #352–#360. It does not edit their results. It does not open funding. It does not read the order book. It does not score a level as strong or weak.
