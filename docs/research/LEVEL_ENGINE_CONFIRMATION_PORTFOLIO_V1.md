# LEVEL_ENGINE_CONFIRMATION_PORTFOLIO_V1

Parent synthesis: `docs/research/LEVEL_ENGINE_DISCOVERY_SYNTHESIS_V1.md`.

This portfolio does not freeze a preregistration and does not assign a design SHA. The synthesis selection below did not itself read a market outcome. A later owner go executed one exposed-surface replication of the P3-1 claim. That run is recorded here and is not a rewrite of the selection.

Selection rule: a target enters only when the exact discovery claim can be restated unchanged, it was selected before any new confirmation outcome, the recorded effect is practically meaningful, uncertainty on the discovery record is acceptable, it is not obviously redundant with #357, a surface can be described honestly, the confirmation does not repair a threshold from outcomes, the estimator can be frozen later, and the run would add information rather than reread the same surface.

There is no P1 and no P2. No same-instrument historical surface is both outcome-unread and free of a neighbor-path problem for these claims. Empty P1 is the result. Prospective targets are not relabeled P1.

## P0 — already confirmed

- **Priority.** `P0_FOUNDATION_ALREADY_CONFIRMED`
- **Unit.** #357 `LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1`
- **Claim.** Structural first touch resolves BREAK or REJECT within 4h more often than the matched half-rotation pseudo touch: 91.1% vs 83.0%, Δ +8.0 pp, 95% +4.4..+11.8, N=548.
- **Action.** Do not rerun. Do not open the BitMEX labels again.

## P3-1 — volatility transition

- **Priority.** `P3_PROSPECTIVE_ONLY`. First in the prospective order.
- **Unit.** #368 `LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1`
- **Exact frozen claim.** Paired mean of `log(RV_POST60 / RV_PRE60)` for a structural first touch minus the same quantity for its matched #352 pseudo touch.
- **Why it matters.** It is the only remaining structural measurement that passed its discovery conjunction and is not already the 4h resolution label.
- **Beyond #357.** A volatility-ratio contrast. #357 did not estimate RV. Independence from the resolution clock is `INDEPENDENCE_UNRESOLVED`, so a pass still does not prove a second mechanism.
- **Required surface.** A prospective Binance USD-M BTCUSDT 5m close panel, declared before outcomes, that does not reuse 2020–2024 discovery rows, 2025/2026 product-open history, or the E1 holdout.
- **Available historical surfaces at synthesis time.** None recommended as pristine. BitMEX status then: `BITMEX_VOL_EXACT_ESTIMAND_UNREAD_NEIGHBOR_PATH_EXPOSED`. Spot 2017–2019 is a different instrument.
- **Exposure.** Prospective-only. Discovery N=1231 and 254 weeks are not a forecast of the future sample.
- **Expected N / clusters.** Not estimated. The collection rule sets them before outcomes.
- **Feasibility.** The definition is already frozen in the #368 design. Prospective collection is not started.
- **Major risk.** The post-60m window overlaps the hour in which #365 already shows a large resolution gap. A replicated multiplier can still be the same resolution process.
- **Would confirm.** The paired multiplier difference replicates under the frozen definition and the inherited bar `log(1.10)`.
- **Would not confirm.** Independence from RMUT or from the 4h resolution rate. A current expected volatility. A breakout. L3.
- **Later execution (2026-10-08).** `LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1`, design `6d97157be44f02ad09344a00df58b715e5c8aa13`. Surface class `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`. Not pristine. Route `REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION`. Evidence label `REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE`. Paired delta +0.096545 log, about +10.14% (95% +0.02178..+0.16817, about +2.20%..+18.31%, N=554, 120 weeks). The inherited bar `log(1.10)` is cleared by the point estimate. The interval excludes 0 and also contains values below that bar. Epoch signs agree; 2018 is +0.28%. Leave-one-epoch-out stays positive. Ceiling L2. Clock independence `UNRESOLVED`. The two samples were not pooled.
- **Prospective protocol (2026-10-08).** `LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1` is `PROSPECTIVE_CONFIRMATION_STARTED`. Design `d30622de19f90efe3ee12b56fc5e2d017ef38c57`. Start `2026-10-09T00:00:00Z`, the first UTC midnight after that commit. Accrual clock `AWAITING_START`. No prospective effect has been computed. The evaluator refuses. `#363` is not started.

### Sketch (not a preregistration)

- **Estimand.** Mean paired difference of the frozen log RV ratio. Touch bar excluded. Twelve pre returns and twelve post returns. `RV = sqrt(mean(r^2))`.
- **Comparator.** Exact #352 half-rotation pseudo touch.
- **Outcome.** The ratio itself. Not RANGE_4H. Not a directional label.
- **Practical bar.** Inherited: absolute paired delta at least `log(1.10)`, interval excludes 0, and the frozen sign-stability rules of #368.
- **Falsifier.** The paired delta misses that bar, the interval includes 0, or the frozen sign rules fail, on the predeclared prospective surface.
- **Prospective collection.** Required.
- **Key exposure issue.** Do not backfill the prospective window with product-open 2025/2026 rows. The BitMEX 2017–2019 close path is now consumed for this exact RV claim. It is not a second replication surface.

## P3-2 — cross-venue primary coefficient

- **Priority.** `P3_PROSPECTIVE_ONLY`. Second. It does not wait on P3-1 to be scientifically allowed. It is second so a failed structural measurement is known before a directional layer is added.
- **Unit.** #363 `LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1`
- **Exact frozen claim.** The primary-model slope of `OTHER_VENUE_MEDIAN_MOVE` on later BREAK versus REJECT, among structural first touches still unresolved at T+15m, with `END_POSITION_X` in the model. Discovery estimate +8.87 pp per +1 SD (95% +5.02..+12.67, N=1060).
- **Not the claim.** `LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE`. That class is `HOLD_METHOD_REPAIR` until a design separates the full primary specification from the stacked matched support. This portfolio does not repair it and does not confirm it.
- **Why it matters.** It is the only directional increment that survived discovery after the generic endpoint, and the records do not show it is the same object as #357.
- **Beyond #357.** A 15m other-venue price association with the later side of resolution. #357 has no second venue and no direction claim.
- **Required surface.** A prospective three-perpetual panel (Binance USD-M BTCUSDT, Bybit BTCUSDT linear, OKX BTC-USDT-SWAP, or the same instrument definitions frozen before outcomes) that does not reuse the 2020-04..2024-12 consumed series.
- **Available historical surfaces.** None. BitMEX 2017–2019 does not host Bybit and OKX. The pinned Bybit and OKX histories start in 2020-04 and are consumed. `MARKET-06` is OKX spot plus Binance perp and is consumed. Live three-venue klines are product-open and E1-exposed.
- **Exposure.** Prospective-only.
- **Expected N / clusters.** Not estimated.
- **Feasibility.** Inventory says the historical three-perp panel for 2017–2019 is absent. No acquisition in this task.
- **Major risk.** Replication of the primary slope would still leave level specificity unestablished. The endpoint control is itself a generic path feature.
- **Would confirm.** The primary coefficient, under the same feature definitions, replicates on a new surface.
- **Would not confirm.** Level specificity. Venue leadership. A current probability. The stacked class name.
- **Next action.** Owner go for a prospective design, or stop. Do not refit the stacked model on the discovery sample.

### Sketch (not a preregistration)

- **Estimand.** Adjusted association, per +1 SD, of the mean of the Bybit and OKX oriented 15m log returns with later BREAK versus REJECT.
- **Comparator.** The model includes the frozen `END_POSITION_X` control. The pseudo stacked contrast is not the estimand.
- **Outcome.** The late BREAK/REJECT label inside the original 4h, on events unresolved at T+15m.
- **Practical bar.** Inherited from discovery: at least 3 pp and the discovery statistical gate, frozen again before prospective outcomes.
- **Falsifier.** The coefficient is below 3 pp or its interval includes 0 on the predeclared prospective support.
- **Prospective collection.** Required.
- **Key exposure issue.** The discovery Bybit and OKX files, and the live product tape, are not an untouched confirmation panel.

## Rejected

| Unit | Class | Why it is not a target |
|---|---|---|
| #365 clock | `DO_NOT_CONFIRM` | Likely the survival-curve form of the resolution object #357 already confirmed. BitMEX status `BITMEX_CLOCK_NOT_INDEPENDENT_ENOUGH`. A prospective RMUT run without a new decomposition would reread resolution speed. This synthesis does not add that decomposition. |
| #361 endpoint | `DO_NOT_CONFIRM` | `DO_NOT_CONFIRM_AS_LEVEL_SPECIFIC`. The pseudo slope is larger. The useful claim is generic path progress, not a level object. |
| #363 specificity name | `HOLD_METHOD_REPAIR` | Primary and stacked specifications disagree. Not repaired here. |
| #352 ordinal claim | `DO_NOT_CONFIRM` | Not an incremental layer. The event constructor stays as the sampling frame only. |
| #353, #355, #356, #358, #359, #360, #362, #364, #366, #367 | `DO_NOT_CONFIRM` | Nulls for a Level Engine layer. Closed neighborhoods, not rescue studies. |

## Order

1. Leave #357 as the confirmed foundation. Do not rerun it.
2. The exact #368 claim has one exposed-surface historical replication, and it supports. The prospective protocol is now frozen and accruing toward its first checkpoint. It is not a result. Do not treat the BitMEX pass as that result.
3. The prospective #363 primary-coefficient design is second. It may be written in the same owner go. It is not blocked by the volatility result, and it is not promoted ahead of it.
4. Do not schedule #365, #361, or the #363 specificity class.

## Stop tree

```text
#357 foundation (already confirmed; not rerun)
   If that record is withdrawn later:
      stop P3-1 and stop P3-2
   If it stands:
      P3-1 historical exposed-surface replication (executed once, 2026-10-08)
         REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION
         class TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION
         not pristine; ceiling L2; clock independence unresolved
         prospective node below remains unstarted
      P3-1 prospective volatility transition
         PASS:
            record a replicated transition measurement
            independence from the resolution clock stays unresolved
            do not add a clock run
            P3-2 remains a separate decision
         FAIL:
            no second structural-dynamics field
            P3-2 is not cancelled
            do not replace the failed transition with a clock, an endpoint, or a nearby RV window
      P3-2 prospective cross-venue primary coefficient
         PASS:
            the primary slope replicated
            level specificity stays NOT_ESTABLISHED
            no composite with the transition
         FAIL:
            no cross-venue layer
            the foundation stands either way
```

A failed P3-1 does not authorize a search for a replacement structural feature. A passed P3-2 does not authorize a level-specificity claim. Neither pass authorizes a product change.
