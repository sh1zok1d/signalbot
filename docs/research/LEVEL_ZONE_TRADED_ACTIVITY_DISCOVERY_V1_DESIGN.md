# LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any late BREAK or REJECT label is joined to zone-traded activity. A null is a complete result. The unit does not create an absorption state, an acceptance state, a volume-confirmation badge, or a level-strength score. It does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment. It does not start a volatility-transition study, a different zone width, a 30m or 60m volume window, a taker split, a large-trade threshold, a BitMEX replication, or a prospective confirmation.

## Question

After a structural first touch, with `END_POSITION_X` and `OTHER_VENUE_MEDIAN_MOVE` already known, does the amount of actual executed quote notional inside the frozen structural zone during `[T, D)` add information about later BREAK versus REJECT?

The observable is unsigned executed activity at the zone. It is not candle volume, not signed taker flow, and not displayed order-book depth. No absorption, acceptance, defense, or institutional-buying interpretation is assumed.

## Novelty audit

Read before acquisition and before any late label: H05 taker imbalance, B2-05 flow-absorption governance, DH1/DH2 spot flow, DH3-S large prints, DH3-V level results, #358 positioning/flow, #359 joint state, #360 displayed depth, #361 oriented taker reaction, #362 path memory, #363 cross-venue reaction, #366 break/reject sequence, and the Atlas rows `FLOW.taker_imbalance`, `FLOW.absorption`, `FLOW.participant_composition`, `PRICE_STRUCTURE.levels`, and `MICROSTRUCTURE`.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| H05 | Signed taker imbalance and a future return. Closed on `FLOW.taker_imbalance`. | This unit does not use buy/sell imbalance, delta, CVD, or an aggressor-side predictor. |
| B2-05 | Absorption governance on `FLOW.absorption`. Exposed, not this test. | The cell stays closed. This unit does not name absorption. |
| DH1/DH2 | Spot flow and directional level-hold or barrier probabilities. No cell cleared the bar. | This unit uses Binance USD-M executions only, and the outcome is the existing late BREAK label. |
| DH3-S | Stress-hour spot/perp lead score and a count of large perp prints. | That reduced file is not level turnover. It is not an input. |
| DH3-V | Level cards on price structure. | Those cards are not zone-notional intensities. |
| #358 / #359 | Positioning and joint state before or around the touch. | Neither measured executions inside the structural zone. |
| #360 | Displayed cumulative depth around price before the first touch. Result `NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE`. | Displayed liquidity is not traded liquidity. This unit does not reinterpret #360. |
| #361 | Oriented taker reaction and `END_POSITION_X`. | The taker coordinate stays closed. `END_POSITION_X` is a control, not a new claim. |
| #362 | Three 5m close-path bits. Result `NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT`. | No close-path bit, re-entry, crossing count, or wick. Activity may correlate with time near the zone. It is a different observable. That null is not rescued. |
| #363 | Cross-perpetual median move. | `OTHER_VENUE_MEDIAN_MOVE` is a control. This unit does not confirm CV1. |
| #366 | Post-first opposite-barrier sequence versus pseudo. | Sequence classes are not features here. |

`BLOCKED_REOPENING_ZONE_TRADED_ACTIVITY_CELL` does not apply. The new object is unsigned Binance USD-M quote notional inside the exact #352 structural zone during the first 15 minutes after a first touch, incremental to endpoint and cross-perp movement, with touch offset as a nuisance. Reopen key: `NEW_MECHANISM`. The row stays `PRICE_STRUCTURE.levels`. The column is `PERP_FLOW` because the new surface is aggTrades. The unit is not placed on `FLOW.taker_imbalance` or `FLOW.absorption`. The taxonomy is not edited. Aggressor-side fields in aggTrades are out of scope and are not read into a feature.

## Sources

Structural level, zone, touch bar, barriers, `END_POSITION_X`, and the late outcome come from `CORE_BTC_BINANCE_V0`. They are not rebuilt.

`OTHER_VENUE_MEDIAN_MOVE` comes from `LEVEL_CROSS_VENUE_PERP_5M_V0` through the #363 assembly. That dataset is not rebuilt.

Trade source: Binance USD-M BTCUSDT perpetual official aggTrades, Atlas identity `BINANCE_UM_TRADES_AGGTRADES_ARCHIVE`. URL prefix `https://data.binance.vision/data/futures/um/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-{month}.zip`. No spot aggTrades. No Bybit trades. No OKX trades.

Event window, exact #363: `[2020-04-01T00:05:00Z, 2025-01-01T00:00:00Z)`. It is not enlarged because aggTrades exist earlier. March 2020 is a lookback month for the pre-touch hour of the earliest events. No March event is added. No 2025 object, no 2026 object, and no E1 object is requested. A timestamp at or after 2025-01-01 inside a legal monthly file aborts the reduction.

Raw monthly zips are checksum-verified, reduced to event aggregates, and deleted. Git receives the source inventory, official checksums, the event-level aggregate file, and its digest. Dataset id `LEVEL_ZONE_TRADES_V0`.

## Population, zone, and clock

First touch only, of PDH, PDL, PWH, PWL, PMH, PML. Level identity, merged zone, zone bounds, approach side, X, BREAK, REJECT, and ambiguity are the #352 objects. The traded zone is exactly `zone_low <= price <= zone_high`. It is not replaced by a ±0.05% or ±0.10% band.

`T` is the open of parent touch bar `j`. `D = T + 15m`. The feature window is `[T, D)`. The late outcome begins only after `D`, on the existing #361 late window `j+3 .. j+48`. `D` is not redefined around the trade timestamp.

`TAU_TOUCH` is the timestamp of the first aggTrade inside the structural zone during parent bar `j`, that is `[T, T+5m)`. `TOUCH_OFFSET_SECONDS = (TAU_TOUCH - T) / 1000`. It does not replace `T`. A legal offset lies in `[0, 300)`.

## Trade semantics

Exchange transact time. A trade is in the feature window iff `T <= trade_ts < D`. It is in the pre-touch hour iff `T - 60m <= trade_ts < T`. It is in zone iff `zone_low <= price <= zone_high`. Quote notional is `price × quantity`. USD-M BTCUSDT quantity is base BTC. The first chunk of each month must have median price in `[1000, 200000]`, median quote notional in `[1, 5e7]`, and positive median quantity. The header, when present, must be `agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker`. `is_buyer_maker` is not a feature.

A trade may update two scientific events when their windows overlap. That is recorded and not removed. Each event feature is its own observable.

`RAW_TOUCH_MATCH_RATE` is the share of geometry-legitimate real first touches with at least one in-zone trade during bar `j`. The frozen minimum is `0.95`. Below that, the route is `AGGTRADE_TOUCH_IDENTITY_FAILED` and late labels are not read. The zone is not loosened. The pseudo match rate is reported separately. If it is below `0.95`, the real question still proceeds when its own gate passes, and specificity is `NOT_ESTIMATED`. A real candidate can then only be generic.

## Features

At most three. No feature is added after outcomes. Redundancy drops the later feature of a pair with absolute Spearman rho at least `0.90`, in the order ZA1, ZA2, ZA3. A dropped feature is not replaced. Spearman correlations with baseline controls are reported and do not by themselves drop a feature. A design with condition number above `1e8` is withheld.

`PRE60_TOTAL_NOTIONAL` is total perp quote notional on `[T-60m, T)`. `PRE15_EQUIV_NOTIONAL = PRE60_TOTAL_NOTIONAL / 4`. The 60-minute window is frozen.

- ZA1 `ZONE_NOTIONAL_INTENSITY_15M = log(ZONE_NOTIONAL_15M / PRE15_EQUIV_NOTIONAL)`. Both notionals must be strictly positive. If either is not, ZA1 is missing. No epsilon is introduced.
- ZA2 `ZONE_NOTIONAL_SHARE_15M = ZONE_NOTIONAL_15M / TOTAL_NOTIONAL_15M`, defined only when total notional is positive. The range is `[0, 1]`. A zero zone with positive total is a legal zero.
- ZA3 `ZONE_ACTIVE_SECONDS_15M` is the count of distinct UTC seconds in `[T, D)` with at least one in-zone execution, divided by `900`. It is not a trade count.

Forbidden as primary features: buy/sell imbalance, taker delta, CVD, buyer-maker fraction, large-trade threshold, whale count, trade-size percentile, crossing count, re-entry count, VWAP versus the level, volume-profile bins, alternative zone widths, and 30m or 60m activity.

## Outcome, baseline, and scaling

Primary cohort: `UNRESOLVED_AT_D` (`early_status == UNRESOLVED`). Primary outcome: `LATE_BREAK_GIVEN_RESOLVED`. BREAK is 1, REJECT is 0. NEITHER and AMBIGUOUS are excluded. The outcome is not changed to range, hold, any-resolution, or return.

Every primary model includes `END_POSITION_X`, `OTHER_VENUE_MEDIAN_MOVE`, and `TOUCH_OFFSET_SECONDS`. Additional frozen nuisance, and nothing else: day/week/month family, support/resistance, year, pre-touch RV tercile, UTC 6-hour block, and pre-touch approach displacement. No post-touch volume, return, taker, or open interest is added.

Baseline: `Y ~ END_POSITION_X + OTHER_VENUE_MEDIAN_MOVE + TOUCH_OFFSET_SECONDS + frozen nuisance`.

Each retained feature: the same model plus that one feature. Estimator: linear probability model, week-cluster bootstrap, 2000 draws, seed `20261023` with frozen offsets `seed + feature_index * 17 + kind` (`kind` 0 baseline, 1 full model, 100 matched). Year, family, side, and leave-one-year-out slices are point refits. No nonlinear search.

Scaling support, frozen before outcomes: real rows that are unresolved, baseline-ready, and finite for every retained feature. `z = (x - mean) / population_sd` with `ddof = 0`. The same scales apply to pseudo rows. Tertile cuts are the 1/3 and 2/3 quantiles of each retained feature on that support. They are descriptive. A top tertile is not a threshold and is not named "high volume at level".

The pre-outcome count used for the information gate is this common support, which is at least as strict as "at least one retained feature".

## Estimand and candidate rule

For each retained feature, the estimand is the adjusted percentage-point change in `P(LATE_BREAK | later resolved)` per `+1 SD`, conditional on endpoint, cross-perp movement, touch offset, and the frozen nuisance.

Practical scale: `3 pp` per `+1 SD`. It is not lowered. BH `q = 0.10` across retained features only. Baseline coefficients are not in the FDR family.

`ZONE_TRADED_ACTIVITY_CANDIDATE` requires all of: absolute effect at least 3 pp; CI95 excludes 0; BH q at most 0.10; the model contains endpoint, CV1, and touch offset; temporal stability; leave-one-year-out preserves sign; day versus week is not materially contradictory; support versus resistance is not materially contradictory; and there is no aggTrades identity or coverage artifact.

Material contradiction means opposite signs and both absolute effects at least 3 pp, with both slices at least N=30. Month is descriptive when small. A q failure is not an instability.

Eligible years are 2020–2024 with resolved N at least 30. Five eligible years need at least 4/5 on the pooled sign. Four need at least 3/4, and every opposite point must be strictly inside 3 pp. Three require all three on the pooled sign. Fewer than three fails.

Leave-one-year-out runs for a feature that passes the pooled scale, CI, and q gates. Every estimable leave-one-year-out point (N at least 30) must keep the pooled sign. Each one does not need its own interval. Fewer than three estimable leave-one-year-out fits fails.

## Specificity

Specificity is computed only after a full real candidate passes the pooled conjunction. Pseudo features are actual Binance executions inside the exact pseudo structural zone during that pseudo event's `[T, D)`. Pseudo volume is not fabricated. Pseudo cannot rescue a real null.

Matched episodes require both arms primary-eligible, with the feature and the baseline controls present. The same columns are fit separately:

`Y_real ~ END_POSITION_X_real + CV1_real + TOUCH_OFFSET_real + ZA_real + nuisance_real`

`Y_pseudo ~ END_POSITION_X_pseudo + CV1_pseudo + TOUCH_OFFSET_pseudo + ZA_pseudo + nuisance_pseudo`

A nuisance column is kept only when it varies in both samples. Protected columns stay. Scaling is the frozen real pre-outcome scale. The pair-preserving bootstrap moves a source episode together and clusters on the real touch week. `DELTA_SPECIFIC = beta_real_matched - beta_pseudo_matched`. Minimum matched N is 100.

If the matched real slope reproduces the sign without material disagreement, absolute delta is at least 3 pp, and the delta interval excludes 0: `LEVEL_ZONE_TRADED_ACTIVITY_INTERACTION_CANDIDATE`.

If the full real candidate passes and specificity does not: `GENERIC_TRADED_ACTIVITY_CANDIDATE`.

Material disagreement between the full slope and the matched real slope is an opposite sign, or a matched slope inside 3 pp while the full slope cleared 3 pp. A missing matched slope is `NOT_ESTIMATED`, not that disagreement. The route is then `SPECIFICITY_NOT_ESTABLISHED_SUPPORT_SENSITIVE` when the disagreement is present.

## Information gate and routing

Before the late-outcome join, all of the following are required:

1. Official aggTrades identity verified.
2. Every used monthly archive checksum-verified.
3. Real `RAW_TOUCH_MATCH_RATE >= 0.95`.
4. No 2025 or 2026 object.
5. At least 400 real unresolved rows on the common retained-feature support.
6. Expected resolved N, using the frozen factor 0.50, at least 200. Late labels are not counted for this gate.
7. At least one ZA feature retained.

Failure before the join uses `AGGTRADE_TOUCH_IDENTITY_FAILED` when the real touch rate fails, and `ZONE_TRADED_ACTIVITY_INFORMATION_INSUFFICIENT` otherwise. After a join, `INFORMATION_LIMITED` is the route when resolved N is below 200 or no retained interval is within 20 pp, and no contrast has already cleared the statistical gate.

Route order: novelty block; touch-identity failure; pre-outcome information failure; any level-specific interaction candidate; any support-sensitive disagreement; any generic real candidate; statistical but unstable; information-limited; otherwise `NO_INCREMENTAL_ZONE_TRADED_ACTIVITY`.

One official run. A second invocation raises `REFUSING_RERUN`. After the result, zone width, activity window, pre-touch normalization, feature formulas, baseline, FDR, the 3 pp bar, and the candidate rule are not changed.

Claim ceiling: `L2 / DISCOVERY_ONLY`. Allowed wording is a historical association between executed activity inside the zone and later BREAK or REJECT after controlling for price position and cross-perpetual movement. Forbidden: absorption, defense, smart money, volume confirms breakout, a current probability, and a trading instruction.

## Census

Filled from the outcome-blind preflight in the same commit as this note. `outcomes_read = false`. Late labels are not in the preflight. Early status is the #361 status known at D.

Structural episodes 4076. Geometry-legitimate real first touches in the #363 window: 1856. Outside that window: 96. No touch: 2124. Pseudo geometry-legitimate: 1885. Paired windows extracted: 1183. Event windows reduced: 3039.

Months required and checksum-verified: 58, `2020-03` through `2024-12`. No missing object. No 2025 or 2026 object. Official header present. March 2020 notional audit: median price 8582.21, median quantity 0.171 BTC, median quote notional 1466.10 USDT. December 2024: median price 96386.7, median quantity 0.013 BTC, median quote notional 1250.53 USDT. Quantity is base BTC. Aggressor side was not used. Raw zips were deleted. Aggregate digest `af1eb088ac0fc7e860cbd211f654d3fd7cf8332588fa03c91b22131f37e34970`. Object-list digest `14cf41ddf67f11d8fb81eaa7644ff1d29fa75ffab401529fc2fe2a9701ea9022`. Trade rows scanned: 2,441,799,281. Trades assigned to at least one event: 286,267,510. Trades that fell in two or more event windows: 72,322,341. That cross-event overlap is kept. Overlapping real `[T, D)` windows: 67 pairs. Event coverage of legitimate real touches: 1. Pre-touch hour positive: 0.9881.

`RAW_TOUCH_MATCH_RATE` real = 1832/1856 = 0.987069. Pseudo = 1163/1183 = 0.983094. Both clear 0.95. Touch identity passes. Pseudo identity passes, so specificity is allowed if a real candidate passes.

Early status on the 1856 real touches: BREAK 286, REJECT 265, AMBIGUOUS 13, UNRESOLVED 1292, unavailable 0. Unresolved with cross-venue nuisance: 1235. Unresolved and baseline-ready: 1216. Common retained-feature support: 1215. Expected resolved primary N at the frozen 0.50 factor: 607.5. Planning MDE about 6.35 pp. The 3 pp bar is not lowered. The pre-outcome gate passes.

ZA3 is dropped before outcomes. Spearman rho of ZA2 with ZA3 is 0.9245. ZA1 with ZA2 is 0.8382. ZA1 with ZA3 is 0.8303. Retained features: ZA1 and ZA2. On the 1215-row support, ZA1 mean −0.6101, sd 1.4916; ZA2 mean 0.3102, sd 0.2191; touch offset mean 139.37 seconds, sd 90.33, range 0.001 to 299.18. Spearman with endpoint and CV1 stays below 0.90 (ZA1 0.332 and 0.413; ZA2 0.217 and 0.202). Those controls stay in the model and do not drop a feature.

Among unresolved nuisance rows, ZA1 missing rate 0.0162 with no exact zeros among finite values; ZA2 missing rate 0.0154; ZA3 zero rate 0.0154 and no missing values, because a covered window can have zero active seconds. ZA1 has no epsilon.

Slice counts on the 1215-row support: years 165, 270, 286, 225, 269; families DAY 1081, WEEK 121, MONTH 13; resistance 695, support 520. Scales and tertile cuts are the hex values in the preflight. The evaluator checks them for drift and does not refit them after seeing Y.
