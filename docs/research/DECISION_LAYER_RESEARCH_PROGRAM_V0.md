# Decision-layer research program V0

**Status:** `OWNER_DECISION_RECORDED / DESIGN_ONLY / NO_OUTCOME_OPENED`
**Date:** 2026-10-01
**Authority:** owner decision recorded here. This file does not change any frozen contract, verdict or preregistration.

```
BETA_SCOPE_FROZEN_AS_IS        = true
DECISION_LAYER_GOAL            = EVIDENCE_FOR_FUTURE_STATISTICAL_STATEMENTS
FIRST_MECHANISM                = TWAP_EXECUTION_FOOTPRINT
DELTA_DIRECTION_ARM            = DROPPED (H05_REJECTED_SPECIFIC_CLAIM)
GLOBAL_EVALUATION_REVIEW       = STILL_PENDING (scoped profile below, this program only)
MARKET_OUTCOMES_OPENED         = false
PROTECTED_2025_2026_OPENED     = false
MARKET_07_CREATED              = false
NEXT_UNIT                      = TWAP_FOOTPRINT_OUTCOME_BLIND_FEASIBILITY
```

## 1. Owner decision (2026-10-01)

1. **The beta ships as it is.** No new beta features. Only operations and correctness fixes. Its posture stays descriptive (`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`).
2. **Goal of the next research.** Build evidence for a future "decision" layer: statistical statements about what tended to follow a detected market situation, direction included. Example of the target form: "TWAP sells are running; historically, after such episodes, price was lower 6h later in N of 100 cases (M of 100 in comparable conditions without them)".
3. **Bar for showing a statement.** Only after independent confirmation under rules frozen in advance, and only through a separate promotion gate like `BETA_D7_REGIME_CONTEXT_GATE_V1.md`. A null result is an acceptable outcome. "Direction was even (about 50/50)" is itself a product statement.
4. **First mechanism.** A TWAP-like algorithmic execution footprint. Origin: the owner's observation of a third-party bot (Coinact.gg "Major TWAP Detections"), where price seemed to move in the execution direction for about 6 hours. That observation is a reason to test, not evidence.

**What does not change:**
- there is no edge claim;
- the beta's `PREDICTIVE_PRODUCT_FROZEN` posture holds until a gate says otherwise for one claim;
- protected Binance 2025/2026 stay sealed;
- every closed verdict stays closed;
- MARKET-07 is not created.

## 2. Correction: no Delta-direction arm

Net taker flow → subsequent return was already tested and rejected:
- `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN` = `H05_REJECTED_SPECIFIC_CLAIM`;
- 45 cells (3 W × 3 q × 5 H), both signs;
- Binance 1m klines 2020-02 → 2025-01 (`docs/RESEARCH_LEDGER.md`, 2026-08-27).

A "Delta burst → reversal/continuation" study would be a W/q/H variant of H05, which is forbidden. It is not run in any form.

**Consequence for TWAP:** a TWAP claim is valid only if it is **incremental over net taker flow**. The baseline matches prior net flow, so the regular slicing signature has to carry the information. Otherwise the result is `NO_INCREMENTAL_STRUCTURE`.

## 3. Family placement and priority

**Family B (directional expectation), with a new observable.** The signal is the trade-level execution footprint: repeated equal-size taker prints at regular intervals. Klines cannot express it. The observable is unused by any recorded card.

**Priority.** `HETEROGENEOUS_FAMILY_ROTATION_V3` keeps BTC-own short-horizon scalar prediction at low priority as a search-priority conclusion. The owner re-prioritizes this one observable for product reasons. This overrides search priority only, never a verdict.

**Not a D7 child.** D7's anti-rescue list (IMPACT_PROXY thresholds, windows, L2 "better D7") does not apply, because TWAP uses no impact proxy.

## 4. Step 0: scoped evaluation profile (this program only)

`HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW` is the routed unit after D7. The owner authorized a scoped version that adopts the proposal's elements this program needs:
- **Not done:** the global review, the retrospective replay of D2–D13 and the C-series, and the generator and compiler updates.
- **Still pending:** all of the above, for any other card.

**Profile rules:**
1. **Twin preregistration.** Discovery and confirmation plans are frozen together, before any forward return is computed: surface, estimand, horizons, effect bar, and power at 50% and 75% of a planning effect.
2. **Declared domain.** The domain is the event episodes the frozen detector finds. The decision time is point-in-time.
3. **Nuisance baseline, matched inside the same surface:**
   - UTC hour of day;
   - prior 1h realized volatility tercile;
   - prior return over the episode lookback;
   - prior net taker flow over the episode lookback.
4. **Mechanism variable.** The regular equal-size slicing is never conditioned away.
5. **Dependence-aware inference.** Day-block bootstrap or HAC with a lag covering episode overlap. Effective N is reported.
6. **Practical bar.** The incremental side-signed drift at a primary horizon must reach at least 10 bps, about one perp taker round trip. The lower confidence bound must be above 0.
7. **Concentration.** Leave-one-year-out sign stability. No single year supplies more than half the effect.
8. **Independent replication.** A disjoint era with the same detector and rule.
9. **Outcome classes.** Use the proposal's classes. Only `SUPPORTED_UNCONDITIONAL` or `SUPPORTED_CONDITIONAL`, replicated, can go to a product gate.
10. **No rescue.** Detector parameters are frozen before any forward return. A failed run is never re-scored with new parameters, horizons or sides. A different design is a new research object.

## 5. TWAP execution-footprint card (design draft)

The preregistration freezes the final values.

**Mechanism, and its competitors:**
- **M1 (continuation).** A detectable one-sided execution schedule means a parent order is still in progress. Its remaining volume pushes price in the execution direction, beyond what net flow already shows.
- **M0 (no incremental information).** Drift after episodes equals that of matched non-episode times with the same prior net flow and move.
- **M2 (impact decay).** After execution, price partially reverts. This is the classical metaorder result.

The test is two-sided.

**Observable:**
- Binance spot BTCUSDT `aggTrades`. Fields used: trade time, quantity, taker side (`is_buyer_maker`), and the trade price at the print, for notional only.
- A taker print is all aggTrades of one side in the same millisecond.
- Known limitations:
  - two takers in the same millisecond merge;
  - size-randomized TWAPs are missed;
  - the data is single-venue.

**Detector (calibrated outcome-blind):**
- The fixed-tolerance identical-quantity chain was rejected by the §7 probe: no specificity.
- The feasibility unit defines a regularity statistic:
  - prints of one side keyed by constant quantity or constant quote notional;
  - the number of near-periodic consecutive gaps per key and hour, tested against an hour-preserving Poisson null with a frozen significance threshold;
  - minimum notional per slice `$X`.
- An episode qualifies at the first print where its regular slices reach at least `K` and it lasts at least `D_min`.
- Quality is checked without prices:
  - **specificity:** a time-shuffled null keeps each size's per-hour count but destroys the timing;
  - **recall:** synthetic TWAP injection.

**Event and decision time:**
- One event per episode: overlapping same-side chains merge.
- The decision time is the qualifying print.
- The event carries side, `$`/h and elapsed duration.

**Estimand:**
- Side-signed log return from the decision time to `T + H`.
- Primary horizons: 1h (during execution) and 6h (the owner's observation), Holm-adjusted.
- 4h is a diagnostic only.
- The hit rate is reported for display; the gate tests the mean.

**Surfaces:**
- **Discovery:** Binance spot BTCUSDT, 2020-01 → 2024-12.
- **Confirmation candidate:** Binance spot BTCUSDT, 2017-08 → 2019-12 (same venue and observable, disjoint era).
- **Fallback:** BitMEX XBTUSD trades 2016–2019.
- Outcome-blind episode counts decide between them before discovery.
- No 2025+ file is downloaded.

**Feasibility gate (outcome-blind):**
- At least 300 discovery episodes on at least 100 distinct days.
- At least 100 confirmation episodes.
- Null chain rate at most 10% of the real rate at the frozen parameters.
- Planning power at least 80% for the practical bar under day-block dependence.
- Failing the gate closes the card as `INFORMATIONALLY_WEAK` before any outcome.

**Product path, only if confirmed:**
- A separate gate with exact strings.
- Live detection needs a trade-stream collector. That is a future product decision; the beta is frozen.

## 6. Sequence

1. `TWAP_FOOTPRINT_OUTCOME_BLIND_FEASIBILITY`: detector, null and recall checks, and monthly episode counts. No forward return.
2. Twin preregistration freeze: detector parameters, matching, horizons, bar, inference, and both surfaces.
3. Discovery one-shot on 2020–2024.
4. Confirmation one-shot on the disjoint era.
5. Promotion gate, only for a supported and replicated class.

## 7. Feasibility log

### Prototype probe — one month, 2026-10-01 (exploratory, not frozen)

**Input:** Binance spot `BTCUSDT-aggTrades-2024-06.zip`, checksum verified.
- Fields used: trade time, quantity, taker side, and the price at the print (for notional).
- **No forward return was computed.**
- 27,774,325 aggTrades; 15,713,978 taker prints; 3,646,371 prints of at least $1,000.

**Finding 1: the naive detector has no specificity.**
- Rule: identical quantity, gap within `max(1 s, 10%)` of the period, period 2–300 s, at least 10 slices, at least 15 min.
- It found 6,037 chains. An hour-preserving time-shuffled null found 11,005.
- Tightening the tolerance to `max(1 s, 2%)` still gave 1,723 real against 6,213 null.
- The real chains had 1–3 s gap jitter, so they were coincidences of common sizes at long periods.
- That rule is rejected.

**Finding 2: real regular execution exists.**
- Statistic: per (side, identical quantity, UTC day), the number of consecutive gaps within ±1 s of the modal gap.
- Compared against five hour-preserving shuffles:
  - 118 key-days had at least 20 such gaps and at least 3× the largest shuffle value (27 days; 47 buy, 71 sell);
  - 23 key-days had at least 50.
- Periods are mostly 3–4 s, with some at 14, 30 and 59 s.
- Examples:
  - 2 BTC buys every 3 s: 196 regular gaps against a shuffle mean of 29, about $27M;
  - 0.5 BTC sells every 4 s: 173 against 10.6.

**Finding 3: some executions slice by notional, not quantity.**
- Many key-days are runs of about $50,000 slices with varying BTC quantity (0.745–0.782 BTC).
- Each exact quantity appears only while the price is stable.
- The detector must key on constant quote notional as well as constant quantity.

**Consequences for the feasibility unit:**
- Key prints by constant quantity **or** constant quote notional (tolerance to be set).
- Test regularity per key and hour against an hour-preserving Poisson null with a significance threshold, instead of fixed tolerances.
- Episodize within a day.
- Validate recall with synthetic injection.
- Then run monthly counts on 2020–2024 and on the confirmation candidate, 2017-08 → 2019-12.
