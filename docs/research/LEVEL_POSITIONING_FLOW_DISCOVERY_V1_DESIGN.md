# LEVEL_POSITIONING_FLOW_DISCOVERY_V1

MODE = DISCOVERY

Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim ceiling L2.
`PRODUCT_INTEGRATION_CANDIDATE = NO` is frozen here, before any outcome. A discovery candidate is not a product change.

Owner go: the task that opened this unit. One official run after this note is committed. No rescue after the outcome.

This note is the freeze. The evaluator must not run while this file is uncommitted, and it must not be edited after an outcome is read.

## 1. Provenance

Source main at the start of the research chain: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

Dependencies, not rewritten:

- #352 `LEVEL_TOUCH_DEGRADATION_V1` `dfc9e0f04358de15606382472badeb5aee787039`
- #353 `LEVEL_REJECTION_MEMORY_V1` `c3d39bffda861b535605a98205d7578c0c84c782`
- #354 discovery-first methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- #355 `LEVEL_APPROACH_STATE_DISCOVERY_V1` `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- #356 `LEVEL_STRUCTURE_DISCOVERY_V1` `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`
- #357 `LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1` `c1cd4e0102e700f7860d21a9af0d243c3bc367be` (branch point)

#357, on BitMEX 2017–2019, found that the first touch of a pre-known structural level resolved into BREAK or REJECT within 4h more often than the matched pseudo-price: Δ RESOLVED = +8.0 pp, 95% +4.4..+11.8, N = 548. This unit does not ask whether levels exist, and it does not reread that contrast.

## 2. Search object

The question is which point-in-time positioning and aggressive-flow states, if any, immediately before the first touch of a structural level carry extra information about how that event resolves, beyond the already frozen market context, and whether that information is specific to the structural location or is a generic market-state effect that also appears at the matched pseudo-price.

This is not a rescue of a closed cell:

- not generic taker imbalance predicting a future return (H05, `FLOW.taker_imbalance`, closed on its surface);
- not an H05 threshold variant;
- not "OI increase implies continuation" (MARKET-01 / MARKET-02, `DERIVATIVES.oi_buildup`, no structure);
- not DH1-X2;
- not a price/OI directional threshold;
- not funding crowding or a leverage long/short identity (B2-06 remains blocked on funding publication latency).

The new mechanism is `PRICE_STRUCTURE.levels`: market state legally available at the open of a confirmed structural first touch, mapped to the resolution type of that event. Reopening those closed cells under a new name is forbidden.

## 3. OI authority

The owner task authorizes an OI-only read for this unit only. It does not authorize B2-06 science, does not set `research_authorized`, and does not enable the B2-06 evaluator. The B2-06 contract is not edited.

Outcome-blind checks, all required:

1. The Git-tracked normalized object `canonical/oi.jsonl` exists on disk and matches the committed identity: snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`, SHA256 `c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94`, 455273 rows, 254313318 bytes. Materializer commit `78d5bdf9d5686b740ebc48e46227bbf0f990cbbe`, tree `2b3e48ba36dd19f40a00fabe5c1a548b0b94d72f`. Re-materialization with that commit's code reproduced those OI bytes. The runtime wrapper snapshot id is `dc7435fe4a5f7c8239edf076954a9072b3b9497a62f3e549c1614abf34a70e18` because three Vision containers (`BTCUSDT-metrics-2024-04-01.zip`, `2024-04-02.zip`, `2024-04-03.zip`) no longer hash to the values stored inside snapshot `5a9d036b`. Their normalized contribution is inside an `oi.jsonl` that is byte-identical to the Git object. This unit binds to that Git digest and refuses any other digest. It does not adopt the new wrapper id and does not rewrite the manifest.
2. Rows are read from `oi.jsonl` only. The loader refuses a path named `funding.jsonl`.
3. Every row satisfies `available_at_ms = period_start_ms + 300000` and `period_end_ms = period_start_ms + 300000`. Native granularity is 5m. There is no upsample to 1m.
4. Reading `sum_open_interest` alone does not weaken the funding publication gate. `research_authorized` stays false. `b2_06_evaluator_enabled` stays false. `b2_06_inputs_legally_consumable` stays false.
5. Funding is not read. Also unused: long/short account ratios, top-trader ratios, the metrics taker long/short ratio, premium, mark price, liquidations, and the order book.
6. The frozen joint period ends at 2025-01-01 exclusive. No row has `period_start_ms >= 2025-01-01`. The E1 holdout is not read. The last OI print has `available_at = 2025-01-01T00:00:00Z` and measures `[2024-12-31T23:55Z, 2025-01-01T00:00Z)`. A decision time T inside this unit is strictly before 2025-01-01, so that boundary print is never an endpoint.
7. The atlas can hold this search object as a new mechanism on `PRICE_STRUCTURE.levels`. The OI surface's `oi_buildup` row stays consumed by MARKET-01/02. This run, if it proceeds, is further discovery exposure, not a confirmation and not a reopening of that row's estimand.

448 OI prints are exactly zero. A non-positive print fails the window closed. Nothing is forward-filled.

## 4. Price and taker identity

`CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. Binance USD-M BTCUSDT 1m klines aggregated by the frozen DH1 helper to complete 5m bins. The discovery grid is 526176 bars, open of the first bar `2020-01-01T00:00:00Z`, exclusive end `2025-01-01T00:00:00Z`.

Taker fields are `quote` and `taker_buy_quote`. Sell quote is the arithmetic difference `quote - taker_buy_quote`. On this grid, taker-buy quote never exceeds quote. 61 bars have quote equal to zero; a window whose summed quote is zero is unavailable. Taker-buy is aggressive executed quote, not new longs, not opening longs, not buyer positions, and not order-book pressure.

A bar is usable only when it is complete and `bar_end_exclusive <= T`. The touch bar is excluded.

## 5. Cohort and decision time

Population: first touch only of PDH, PDL, PWH, PWL, PMH, PML. Zone, merge, lifetime, orientation, barrier, BREAK, REJECT, NEITHER, AMBIGUOUS, and the 4h horizon are the #352 functions (`ZONE_HALF_PRIMARY = 0.0015`, `HOLD_BARS_PRIMARY = 48`, `BARRIER_FRACTION_PRIMARY = 0.5`). Touch 2 and touch 3+ are not in the cohort. #352 `feature_eligible` is not the gate: that flag is tied to 2020-02-01 and does not know about OI.

`T` is the open time of the first touch bar. Orientation `d = side` from the #352 approach rule: `+1` from below, `-1` from above. `oriented flow > 0` means aggressive flow toward the level.

Event window, fixed from coverage rather than from the first observed touch:

- start `2020-09-01T01:05:00Z` inclusive, the first T whose required OI print at `T - 60m` equals the first legal `available_at` (`2020-09-01T00:05:00Z`);
- end `2025-01-01T00:00:00Z` exclusive.

The first observed legitimate touch in the outcome-blind census is `2020-09-01T05:55:00Z` (`1598939700000`). The last is `2024-12-31T12:30:00Z` (`1735648200000`). The empty prefix before the first touch is not trimmed.

Outcome-blind geometry, before any barrier label: 4076 structural episodes, 4076 controls, 1708 legitimate real first touches, 1699 legitimate pseudo first touches, 1082 pairs in which both sides are geometrically legitimate, 227 product weeks among the 1708. Real status counts: legitimate 1708, no touch 2124, outside the window 244, incomplete 4h 0, unknown side 0, unusable X 0, missing sigma 0. All 1708 have a complete taker window and a finite oriented displacement and relative-volume nuisance. 1688 of 1708 (missing rate 1.17%) have a complete 60m OI window. The 20 failures are missing or non-positive OI prints, not fills.

Epoch counts on the 1708: 2020Q4 124, 2021 396, 2022 398, 2023 391, 2024 399. Family: DAY 1457 (85.3%), WEEK 217 (12.7%), MONTH 34 (2.0%). Side: from below 915, from above 793. The 70% DAY cap from #355 is not applied. This task did not set it. WEEK and MONTH are both below the frozen tiny-family share 0.15, so clause 6 below can fail a cell if dropping either of them reverses the sign.

Volatility terciles use the #352 edges `0.0012364306616934476` and `0.001790567553180052`, not refit. Counts: low 643, mid 559, high 506. UTC blocks 00–06, 06–12, 12–18, 18–24: 779, 328, 386, 215. Every full-sample nuisance level has both values, so no full-sample dummy is dropped.

## 6. Windows and features

Primary window `[T - 60m, T)`.

Taker: the 12 complete 5m bars with opens `[T - 60m, T)`. The last of them ends at T. The touch bar is not included.

OI: 13 native prints with `available_at` exactly equal to `T - 60m, T - 55m, ..., T`. Each must be finite and strictly positive. A missing timestamp is a failure. There is no forward fill. The print at T measures `[T - 5m, T)` and is available at T. The print at `T + 5m` is the touch bar's OI and is not read.

The 15-minute window is not a second primary specification. It enters only as the predeclared split inside F2 and F4. No 5m, 30m, 2h, or 4h window is estimated.

Let `OI(τ)` be the print with `available_at = τ`.

- F1 `OI_CHANGE_60M = log(OI(T) / OI(T - 60m))`. Positive means outstanding open interest expanded. It does not mean new longs or new shorts.
- F2 `OI_RECENT_ACCELERATION = log(OI(T) / OI(T - 15m)) / 15 - log(OI(T - 15m) / OI(T - 60m)) / 45`, in log open interest per minute. The 15/45 split is frozen.
- F3 `ORIENTED_TAKER_IMBALANCE_60M`. Over the 12 bars, `sell = quote - taker_buy_quote`, `raw = (buy - sell) / total_quote`, `oriented = d × raw`. Total quote must be positive.
- F4 `TAKER_RECENT_SHIFT` = oriented imbalance on the last 3 bars minus oriented imbalance on the prior 9 bars. Either subwindow with total quote zero fails F4 closed. F3 can still exist.

Not estimated: price/flow ratio, absorption, trapped-long or trapped-short scores, an OI×taker score, a crowding score, `LEVEL_STRENGTH`.

## 7. Redundancy, frozen before outcomes

On the nuisance-complete real first touches, pairwise Pearson correlations are:

| pair | rho |
|---|---|
| OI change, OI acceleration | +0.267 |
| OI change, oriented taker 60m | −0.028 |
| OI change, taker shift | −0.004 |
| OI acceleration, oriented taker 60m | −0.021 |
| OI acceleration, taker shift | −0.066 |
| oriented taker 60m, taker shift | +0.010 |

The drop rule is `|rho| >= 0.90` against an earlier feature in the order F1, F2, F3, F4, or a feature with no variation. Nothing is dropped. Retained count = 4. Among the 1688 events with both OI change and oriented taker imbalance finite, 1061 have the same sign and 626 the opposite sign. That alignment is not a feature and is not interacted with an outcome.

Scales are the mean and population SD of each retained feature on the real nuisance-complete rows where that feature is finite, plus displacement and relative volume on all 1708. Tertile edges are the 1/3 and 2/3 quantiles of the same rows. They are stored as float hex in the preflight file. They do not use a barrier label. The evaluator recomputes them and stops if they differ. The same real-cohort scales are used for pseudo rows, for slices, and inside the bootstrap. They are not refit on Y.

## 8. Outcomes

O1 `RESOLVE_4H`: 1 if BREAK or REJECT, 0 if NEITHER. AMBIGUOUS is excluded.

O2 `BREAK_GIVEN_RESOLVED`: among BREAK or REJECT only, 1 if BREAK and 0 if REJECT. This is a historical contrast, not a current probability.

The primary family is these two outcomes, not three separate BREAK/REJECT/NEITHER models. The result still reports the crude BREAK, REJECT, and NEITHER frequencies.

## 9. Estimator

For each retained feature, the adjusted change in historical probability per +1 SD of that feature.

Real primary model, one row per real event:

`Y = a + b z + nuisance`

`z` is the feature on the frozen real scale. `b` is the cell.

Nuisance, frozen, not chosen from Y:

- family, DAY as reference (`fam_week`, `fam_month`);
- support versus resistance, resistance (`side = +1`) as reference;
- year, 2020 as reference (`y2021`..`y2024`); inside a leave-one-year-out sample the earliest remaining year is the reference;
- volatility tercile, low as reference;
- prior-60m oriented price displacement, standardized;
- relative quote volume: sum of quote on the 12 bars divided by 12 times the mean finite non-negative quote on the prior 288 bars, requiring at least 90% of those 288 bars finite, standardized;
- UTC block, 00–06 as reference.

Touch ordinal is not a nuisance: the cohort is first touch only.

Inside one estimation sample, a nuisance dummy that does not vary is omitted. The feature column, the real indicator, and the interaction are not omitted. This is rank hygiene. It is not a new specification. A fit whose Gram matrix has condition number above 1e8 is inestimable. A bootstrap draw that makes an estimand column constant, or that fails that condition check, is an invalid draw.

Same support: a row enters a cell only when that feature, every required nuisance input, and the outcome are all present. Primary cells do not share a single N when OI is missing and taker is not. The nuisance for a cell is fit on that cell's rows, not on a larger baseline.

Pseudo-only cells use the same formula on the pseudo touch, with the pseudo event's own family, side, year, volatility, displacement, relative volume, clock, and week as the cluster. They are restricted to pairs whose real and pseudo sides both have the feature, the nuisance, and a usable label.

Specificity uses one stacked model on those same pairs. Two rows per pair. `β_pseudo` is the coefficient on `z`. `Δ = β_real − β_pseudo` is the coefficient on `z × real`. Cluster is the product week of the real touch, so the pair stays together. Scales remain the real-cohort scales.

Uncertainty: cluster bootstrap, 2000 draws, seed `20261013`, streams `20261013 + 1000 × feature_index + 100 × outcome_index + kind` with kind 0 primary, 1 pseudo, 2 specificity. Percentile 95% interval. A cell with fewer than 90% finite draws has a null interval. The Wald p-value uses the bootstrap standard error. Slice, leave-one-year-out, and leave-one-family-out fits are point estimates; the conjunction uses their signs, not a second interval family.

FDR: Benjamini-Hochberg at q = 0.10 on the 8 primary cells only. A missing p-value enters as 1. Raw estimates and intervals are reported whether or not they pass.

Practical scale: `|b| >= 0.03` per +1 SD. This is the product level-reaction floor (`MATERIAL_DIFF`), the same reading scale as #352, #355, #356, and #357. It is not the DH1 bar of 3 pp plus a positive Brier skill score. That bar applies to a directional probability claim this unit does not make. `EVIDENCE_AND_CLAIMS` does not set a stricter discovery-screening number. The scale is not changed after the result.

## 10. Shape, stability, specificity

Tertiles use the frozen real quantiles: low `<= q33`, high `> q66`, otherwise mid. The result shows the rate in each band. A U-shape is an `EXPLORATORY_SUCCESSOR_IDEA`. No threshold is fit.

Stability, for every primary cell, point estimates in:

- 2020Q4, 2021, 2022, 2023, 2024;
- DAY, WEEK, MONTH;
- support and resistance.

An epoch or a leave-one-out refit with N below 30 is not a disagreement. Leave-one-year-out and leave-one-family-out are computed for every primary cell, not only for cells that already look large, so the conjunction does not choose the slice after seeing Y. Definitions, scales, and tertile edges are not refit.

Specificity, predeclared:

- material level difference: the 95% interval for `Δ` excludes 0, `|Δ| >= 0.03`, `|β_real| > |β_pseudo|`, and `β_real` and `Δ` have the same sign as the real primary coefficient;
- similar pseudo effect: not material, `β_pseudo` has the same sign as the real primary coefficient, and `|β_pseudo| >= 0.5 × |primary|`. The half-magnitude rule is the #352 control rule.

## 11. Candidate rule

A feature/outcome cell is a candidate only when all of the following hold on the real primary cell:

1. BH q ≤ 0.10;
2. `|adjusted effect| ≥ 0.03`;
3. the 95% interval excludes 0;
4. every epoch with N ≥ 30 has a finite point estimate of the same sign, and at least 4 such epochs exist;
5. every leave-one-year-out refit with N ≥ 30 has a finite point estimate of that same sign;
6. dropping a family whose share is below 0.15 does not reverse the sign when the remaining N is at least 30;
7. N ≥ 100;
8. no point-in-time or data-quality failure. A failure of the OI identity, a use of funding, a filled gap, or a touch-bar feature is a failure of the run, not a cell-level excuse.

Then:

- material level difference → `LEVEL_INTERACTION_CANDIDATE`;
- similar pseudo effect → `GENERIC_STATE_CANDIDATE`;
- conjunction holds but neither specificity clause holds → `SPECIFICITY_UNRESOLVED`, which is not a candidate;
- conjunction fails → no candidate.

`SUCCESSOR_CANDIDATE = NONE` when no cell receives either candidate label. That is a complete result.

Routing, in this order, and not as PASS or FAIL:

- any `LEVEL_INTERACTION_CANDIDATE` → `POSITION_FLOW_STRUCTURE_PRESENT`;
- else any `GENERIC_STATE_CANDIDATE` → `GENERIC_MARKET_STATE_ONLY`;
- else any `SPECIFICITY_UNRESOLVED` → `SPECIFICITY_UNRESOLVED`;
- else any cell that passes q, scale, interval, and N but fails the stability clauses → `STRUCTURE_PRESENT_BUT_UNSTABLE`;
- else if the largest `RESOLVE_4H` primary N is below 100 or its cluster count is below 20 → `INFORMATION_LIMITED`;
- else `NO_INCREMENTAL_POSITION_FLOW_STRUCTURE`.

## 12. Search exposure

Counted before outcomes, with 4 retained features:

- raw features 4, dropped 0, retained 4;
- windows 2 (60m primary; 15m only inside F2 and F4);
- outcomes 2;
- primary cells 8, which is the FDR family;
- shape cells 8;
- pseudo cells 8;
- specificity cells 8;
- stability cells 80 (5 epochs + 3 families + 2 sides, times 8);
- leave-one-year-out cells 40;
- leave-one-family-out cells 24;
- interactions 0;
- extra window sensitivities 0.

No OI×taker, OI×volume, flow×volatility, absorption, price-response×flow, long/short quadrant, or state score is estimated after the result. If the tertile rates are U-shaped, the result records the idea and stops.

## 13. What this run does not do

It does not change `/btc`, `/levels`, `/check`, `/risk`, scoring, config, the findings registry, Telegram, or deploy. It does not start a confirmation, an interaction successor, an absorption successor, a funding study, a liquidation study, an order-book study, a cross-venue study, a 2025/2026 read, or a level-strength score.

Wording that remains forbidden even if a cell is selected: OI up means new longs or new shorts; OI down means long closing; aggressive flow means a participant identity; the historical frequency is a current probability; a direct trade call; "the level will break" or "the level will hold".
