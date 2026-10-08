# LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any spot feature is joined to a late BREAK or REJECT label. A null is a complete result. The unit does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment. It does not start lead/lag, time-to-resolution, a volatility transition, confirmation, a 30-minute window, a liquidation map, or prospective tracking.

## Question

`LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1` showed that Binance `END_POSITION_X` at T+15m is strongly associated with later BREAK among structural first touches that are still unresolved. `LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1` did not show that three Binance closes add a further difference once that endpoint is held fixed. `LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1` found a discovery association for the median oriented 15-minute move of Bybit and OKX perpetuals after the same endpoint control (`OTHER_VENUE_MEDIAN_MOVE` about +8.87 pp per +1 SD). That result is discovery only. It is not treated here as confirmed or as level-specific.

This unit asks a different question.

After a structural first touch, once Binance's location and the other perpetual venues' 15-minute move are already in the model, does the Binance spot market add information about later BREAK versus REJECT?

The descriptive reading is whether the move is also present in the spot market or is mostly a state of the leveraged perpetual complex. A positive oriented spot return means the spot price moved in the structural break direction during the window. It does not mean spot led, confirmed causally, or that a participant intended the barrier.

## What #363 contributes

`OTHER_VENUE_MEDIAN_MOVE` is a mandatory baseline control, copied from the frozen #363 definition and the pinned `LEVEL_CROSS_VENUE_PERP_5M_V0` series. It is not re-tested and it is not in the FDR family. A coefficient on that control in this baseline is not a confirmation of #363.

## Novelty audit

Read before any outcome: DH1-L1, DH2-L1, DH1-B1, DH1-B2, DH2-B2, DH3 stress lead/lag, D9, MARKET-06, the Atlas `SPOT_PERP` rows, and #363.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| DH1-L1 / DH2-L1 `SPOT_CONFIRMED_APPROACH_HOLD_4H` | Spot taker net flow over the hour **into** the first touch, as a same-direction state, predicting a 4h hold. DH1 closed at feasibility. DH2 pooled six coins and was an informative null (adjusted −1.75 pp, interval −3.78..+0.36). Row `SPOT_PERP.spot_confirmation`. | This predictor is the 15 minutes **after** the touch. The cohort is still unresolved at D. The outcome is late BREAK versus REJECT, not a 4h hold. The baseline contains `END_POSITION_X` and the cross-perp median move. The spot price feature is a continuous oriented log return, not a binary same-direction flag. |
| DH1-B1 sign confirmation | Spot taker flow had the same sign as a sharp 15-minute move in 97.6% of moves. The sign state was degenerate. No outcome. | No yes/no "spot confirms" feature is built. Exact zero stays a numeric zero. |
| DH1-B2 / DH2-B2 spot share | Spot share of spot+perp quote volume in a sharp move, versus which barrier is reached first. DH2-B2 was `NO_INCREMENTAL_STRUCTURE`. Row `SPOT_PERP.volume_share`. | No volume-share feature and no share threshold. |
| D9 and DH3 stress lead/lag | Who moved first, on other event populations. | No first-mover, no lag in seconds or minutes, no Hasbrouck share. SP2 is a same-window relative magnitude. |
| MARKET-06 | Daily absolute Binance-perp versus OKX-spot dislocation predicting 24h adverse-path MAE. `MARKET_06_NO_EVIDENCE`. | No daily basis z-score, no OKX spot, no 24h adverse excursion. |
| #363 | Other linear perpetuals' 15-minute reaction, incremental to the Binance endpoint. | Spot is the new layer. The #363 feature is held fixed as a nuisance. |

DH1's own reopen note said a non-degenerate state such as spot imbalance relative to perp would be a new candidate, not a repair of the sign state. SP3 is that relative-flow object, measured on the post-touch 15-minute window and only if the pinned taker fields are legal. It is not a rescore of DH1-B1.

Atlas row: `PRICE_STRUCTURE.levels`. Column: `SPOT`. Reopen key: `NEW_MECHANISM` relative to `SPOT_PERP.spot_confirmation`, `SPOT_PERP.volume_share`, `SPOT_PERP.lead_lag`, `SPOT_PERP.stress_lead_lag`, and `SPOT_PERP.basis_dislocation`. The unit is not placed on the closed spot-confirmation cell. `BLOCKED_REOPENING_SPOT_CONFIRMATION_CELL` does not apply. The taxonomy is not edited.

## Data identities

Structural levels, touch time, orientation, X, and the pseudo control come only from Binance USD-M BTCUSDT perpetual (`CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`).

Other perpetuals are the pinned #363 series `LEVEL_CROSS_VENUE_PERP_5M_V0`. They are not reminted.

- Bybit BTCUSDT linear perpetual, canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. Label clock UTC+3, already shifted in the canonical file.
- OKX `BTC-USDT-SWAP` linear perpetual, canonical SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`.

Spot is the existing pin `DH1_BINANCE_SPOT_BTCUSDT_5M_V0`: Binance spot BTCUSDT official 5m klines from `data.binance.vision`, columns open, high, low, close, volume, quote volume, and taker-buy quote volume. Each month is checked against the inventory SHA256. Months read: 2020-04 through 2024-12, the overlap with the perpetual window. Earlier pinned spot months are not read. No 2025 or 2026 object is requested. A missing spot bar stays missing. There is no forward fill.

The common event window is the #363 window `[2020-04-01T00:05:00Z, 2025-01-01T00:00:00Z)`. Spot history is longer and is not used to extend it.

If the spot grid inside that window is missing more than 1% of 5m bars, the identity audit fails and late labels are not read.

## Event, clock, and outcome

Reuse #352 first touches of PDH, PDL, PWH, PWL, PMH, PML, including zone, orientation, X, BREAK, REJECT, NEITHER, and AMBIGUOUS. Touch 1 only.

T is the open of the Binance touch bar. D = T+15m. The price baseline is the close of the completed bar opening at T−5m. The price endpoint is the close of the bar opening at T+10m, which closes at D. Early passage uses bars j+1 and j+2 and excludes the event from the predictive sample. Late passage uses j+3 through j+48. The original T+4h boundary is unchanged.

Primary outcome: `LATE_BREAK_GIVEN_RESOLVED` among events unresolved at D that resolve to a non-ambiguous BREAK or REJECT before T+4h. 1 = BREAK, 0 = REJECT. `LATE_RESOLVE_BY_4H` is descriptive only and is not in the FDR family.

## Baseline

Every primary model contains:

- B1 `END_POSITION_X`, the #361 definition.
- B2 `OTHER_VENUE_MEDIAN_MOVE`, the #363 CV1: the mean of the oriented Bybit and OKX 15-minute log returns. One missing venue makes CV1 missing.

Nuisance, and nothing else: family DAY/WEEK/MONTH, support versus resistance, year, the parent pre-touch volatility tercile, the UTC 6-hour block of T, and the pre-touch approach displacement from #362.

## Features

Maximum three. Formulas are frozen.

- SP1 `SPOT_ORIENTED_MOVE_15M` = d × log(spot close at D / spot close at T−5m). d = +1 from below and −1 from above.
- SP2 `SPOT_EXCESS_VS_PERP_COMPLEX` = SP1 − median of the three oriented perpetual log returns (Binance, Bybit, OKX). Median of three is the middle value. Positive means spot moved farther in the structural direction than the perpetual complex. This is not a lead in time.
- SP3 `RELATIVE_SPOT_TAKER_PRESSURE_15M` = d × spot raw − d × Binance-perp raw, where raw = (buy quote − sell quote) / total quote summed over reaction bars j, j+1, and j+2. A bar is legal only when quote > 0 and 0 ≤ taker-buy quote ≤ quote. One illegal bar makes SP3 missing.

SP3 is dropped before outcomes if, among unresolved rows with a finite SP1, fewer than 95% have a legal SP3. No substitute feature is added. No binary confirmation, 2/3 threshold, spot-volume share, lead/lag, basis percentile, funding, open interest, liquidation, or order book is computed.

If |ρ| ≥ 0.90 between two spot features on the outcome-blind support, the later feature is dropped. Correlation with the baseline controls is reported and does not by itself drop a spot feature.

## Estimator

On the real unresolved rows where every retained spot feature is finite, freeze z = (x − mean) / sd with ddof = 0. Store the means and sds as hex. Pseudo and matched fits use those scales.

For each retained feature, on that same support:

- Baseline: Y ~ END_POSITION_X + OTHER_VENUE_MEDIAN_MOVE + nuisance.
- Candidate: the same model plus the spot feature.

The reported estimand is the spot coefficient per +1 SD. Week-cluster bootstrap, B = 2000, seed 20261020, percentile 95% interval only when at least 90% of draws return a coefficient. FDR q = 0.10 over the retained spot features only. Practical scale 3 pp per +1 SD. It is not lowered.

Year rule for five eligible years (resolved N ≥ 30 and a finite coefficient): at least 4/5 share the full-sample sign. Leave-one-year-out must keep that sign on every omit with remaining N ≥ 30. Opposite estimable DAY and WEEK signs fail. Opposite estimable resistance and support signs fail. A missing MONTH or a missing side slope is not a contradiction. Tertile cuts are the 1/3 and 2/3 quantiles, frozen before outcomes, ties to the lower bin. No threshold is searched.

## Matched specificity

Applied only after the full-sample candidate rule passes, and only when at least 100 matched pairs exist.

A pair is eligible when both the real event and the pseudo event are primary-eligible for that feature: unresolved at D, resolved to BREAK or REJECT inside the original 4h, baseline controls finite, and the feature finite. The pseudo touch is the #352 half-rotation at its own time. Spot and other-venue prices are the actual prices at that clock. Orientation, displacement, endpoint, and CV1 use the pseudo path.

Fit two separate models with the same columns, the same scales, and the same nuisance vocabulary:

- Y_real ~ END_POSITION_X_real + CV1_real + SP_k_real + nuisance_real
- Y_pseudo ~ END_POSITION_X_pseudo + CV1_pseudo + SP_k_pseudo + nuisance_pseudo

There is no stacked interaction regressor. A nuisance column that does not vary inside either matched sample is omitted from both. `endpos_z`, `cv1_z`, and `feature_z` are never omitted.

The bootstrap resamples real-touch weeks. The real row and the pseudo row of one source episode always move together. Each replicate fits both models and stores β_real − β_pseudo. The interval is the percentile interval of that difference.

`LEVEL_SPOT_PERP_INTERACTION_CANDIDATE` requires the full-sample rule, a matched real slope with the same sign that is not materially smaller, |Δ| ≥ 3 pp, and a Δ interval that excludes 0.

Materially contradictory, frozen before outcomes: the matched real slope has the opposite sign, or its absolute value is below 3 pp while the full-sample absolute value is at least 3 pp. In that case the status is `SUPPORT_SENSITIVE`, the feature class is at most `GENERIC_SPOT_PERP_REACTION_CANDIDATE`, and the route is `SPECIFICITY_NOT_ESTABLISHED_SUPPORT_SENSITIVE` unless another feature is an interaction candidate. A large pseudo difference does not rescue a real null.

## Information gate

Late labels are read only if the spot identity audit passes, at least one retained feature has at least 400 feature-complete unresolved real events, and the planning resolve fraction 0.50 implies at least 200 primary events. Otherwise the route is `SPOT_PERP_REACTION_INFORMATION_INSUFFICIENT` and outcomes are not read.

## Routes and ceiling

`LEVEL_SPOT_PERP_STRUCTURE_PRESENT` if any interaction candidate. `SPECIFICITY_NOT_ESTABLISHED_SUPPORT_SENSITIVE` if a full-sample candidate's matched slope disagrees and none is an interaction candidate. `GENERIC_SPOT_PERP_REACTION_STRUCTURE` if a real candidate remains without that disagreement and without an interaction pass. `STRUCTURE_PRESENT_BUT_UNSTABLE` if a statistical pass fails stability. `INFORMATION_LIMITED` if the resolved sample is under 200 or every interval is withheld or wider than 20 pp. Otherwise `NO_INCREMENTAL_SPOT_PERP_REACTION`.

Claim ceiling L2 / discovery only. No current probability. No L3. No L4. No trade instruction. `PRODUCT_INTEGRATION_CANDIDATE = NO`. `SUCCESSOR_CANDIDATE` stays none.

One official evaluator run. A second invocation returns `REFUSING_RERUN`.

## Outcome-blind census

Filled from `LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1_PREFLIGHT.json` in this same commit, before any late label. `outcomes_read` is false. `resolved_after_d` is null. No BREAK or REJECT count by feature is in that file.

Spot identity audit passed. Dataset `DH1_BINANCE_SPOT_BTCUSDT_5M_V0`, instrument Binance spot BTCUSDT, 5m official klines, taker field `taker_buy_quote_volume`, object-list SHA256 `5a27ea4883284c995bbb091067867b45927b67e3d4b244ed11c3b97e5887cb37`. Months read: 2020-04 through 2024-12. Grid from 2020-04-01T00:00:00Z through the last open 2024-12-31T23:55:00Z: 499613 bars present of 499968 expected, 355 missing (fraction 0.000710). That is under the 1% stop. No bar at or after 2025-01-01T00:00:00Z.

Event window stays `[2020-04-01T00:05:00Z, 2025-01-01T00:00:00Z)`. Structural episodes 4076. Real legitimate first touches 1856; outside window 96; no touch 2124. Early status on the 1856: BREAK 286, REJECT 265, ambiguous 13, unresolved 1292, unavailable 0. Unresolved with finite baseline controls: 1235. Feature-complete unresolved, all three spot features finite: 1234. SP3 legal rate among unresolved rows with finite SP1: 1.0, so SP3 is retained. Planning expected primary N at resolve fraction 0.50: 617, above 200. Gate pass. Rough 80% MDE about 6.3 pp. It is not a stop.

Redundancy among the three spot features, maximum |ρ| 0.082. Nothing dropped. All three are retained: `SPOT_ORIENTED_MOVE_15M`, `SPOT_EXCESS_VS_PERP_COMPLEX`, `RELATIVE_SPOT_TAKER_PRESSURE_15M`.

Correlation with the baseline controls, reported and not used to drop a feature: SP1 with `OTHER_VENUE_MEDIAN_MOVE` is 0.998, and SP1 with `END_POSITION_X` is 0.690. SP2 with those controls is −0.136 and −0.072. SP3 with those controls is −0.030 and −0.004. The near-collinearity of SP1 with CV1 is a pre-outcome fact. The candidate model still contains both columns. The incremental SP1 coefficient is the question the design asked; it is not removed because the two series move together.

Outcome-blind scales on the N=1234 support (mean, sd): END_POSITION_X −0.580, 0.616; OTHER_VENUE_MEDIAN_MOVE 0.002926, 0.004458; SP1 0.002902, 0.004448; SP2 −0.0000186, 0.000224; SP3 0.0210, 0.117; approach displacement 0.00689, 0.00663. Hex forms are in the preflight file and are the scales the outcome run must reuse.

Unresolved feature-complete slices: DAY 1099, WEEK 122, MONTH 13; resistance 708, support 526; years 174 / 269 / 297 / 225 / 269. Pseudo events that are themselves unresolved, baseline-complete, and feature-complete, paired to a real row: 623. That count is not the matched primary N. Matched primary eligibility still requires both sides to resolve after D, and that count is not known until outcomes.
