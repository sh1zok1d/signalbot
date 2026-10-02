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

**2026-10-02:** §1.1 ("the beta ships as it is, no new beta features") is superseded for the scope of `BETA_V0_3_MARKET_BRIEFING.md`. Analogue summaries follow `BETA_HISTORICAL_ANALOGUE_GATE_V1.md`. The confirmation bar of §1.3 for decision-layer statements is unchanged.

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

**Superseded 2026-10-01.** The owner adopted `HYPOTHESIS_EVALUATION_CONTRACT_V1.md`, which replaces this profile. The TWAP preregistration is frozen under V1 as an `INCREMENTAL` claim over matched net taker flow. The text below is kept as history.

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

**Mechanism chain (owner decision 2026-10-01).** The card is framed mechanism-first. If the metaorder mechanism is real, it must produce three observable states in order. The test checks the chain, not a bare "TWAP → return" predictor.

| Link | What must appear if M1 is real | Role | Opened |
|---|---|---|---|
| L1 remaining execution | After the decision time, same-side taker volume stays elevated against matched non-episode times with the same prior net flow, until the chain ends | Mechanism-validity gate | Stage 1, flow data only, no price |
| L2 excess drift | Side-signed price drift from the decision time is larger than at matched times with the same prior net taker flow, prior move, prior volatility and time of day | Primary (`INCREMENTAL`) | Stage 2 |
| L3 post-end behaviour | After the detected end of the chain, the accumulated excess move shrinks against the TWAP direction | Primary; fingerprint of temporary execution impact | Stage 2 |

**Staged opening, frozen in the preregistration:**
- **Stage 1** opens only post-decision taker-flow aggregates. No price or return is computed.
- If L1 fails (no elevated same-side flow after detection), the card closes as `NO_INCREMENTAL_STRUCTURE (MECHANISM_NOT_PRESENT)`. Price outcomes are never opened.
- **Stage 2** runs once, only after L1 passes.

**Primary cells.** There are three, the V1 maximum, with Holm across them:
- L2 at `T + 1h` (during execution);
- L2 at `T + 6h` (the owner's observation);
- L3 over the hour after the detected end.

**Why L2 is matched on net flow.** The question is whether the TWAP execution structure carries information beyond a large directional flow of the same size. If ordinary flow of +5 units gives the same drift as a TWAP of +5, the pattern adds nothing for a trader. If the TWAP still gives excess drift at equal aggregate flow, that is the finding.

**Only pre-decision information in the matching.** Every comparator is defined strictly from information available at the decision (anchor) time. That covers net flow over the episode lookback ending at `T`, the prior move, prior volatility and time of day. Post-decision flow is never a matching variable. Matching on it would remove exactly the persistence that L1 measures.

**How to read L3.** Reversion after the detected end supports the temporary-impact reading. No reversion does not refute L1/L2, because:
- the parent order may have been informed;
- the market may have moved on for another reason;
- the permanent impact component may be large.

No reversion only separates the result from a pure temporary-impact mechanism. In V1 terms, an L3 null never reclassifies the L1/L2 result.

**Detected end.** The end is point-in-time: the first moment the chain has missed its slice tolerance long enough to be declared ended, with the rule frozen in the detector. It is never the true end, which is only known afterwards.

**Wording consequence.** The product statement follows the links that hold:
- **L2 and L3:** "during execution, price tended to move with it; after it ended, it partly gave back".
- **L2 without L3:** "during execution, price tended to move with it; after it ended, there was no typical give-back".

**Multiplicity.** V1 requires Holm across the three primary cells, and that is kept. The L1 gate runs before them and can only stop the card, so it does not inflate the error rate. Fixed-sequence (hierarchical) gatekeeping would also fit this nested chain, but the contract is not changed for it. Holm is more conservative.

**V1 declaration (planned):**
- `CLAIM_TYPE = INCREMENTAL`, `TARGET_CLASS = UNCONDITIONAL`, `INTRADAY = true`.
- Nuisance variables: time of day, prior realized volatility, prior return over the episode lookback (the lagged target), and prior net taker flow (card-specific).
- Mechanism variables: regular slicing (constant quantity or notional at a near-constant period).
- Practical floor: L2 must reach at least 10 bps. The floor is chosen in advance as the smallest economically meaningful scale. It is not a claim that 10 bps is net-profitable after fees, maker/taker mix and slippage.

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
- L2: side-signed log return from the decision time to `T + 1h` and `T + 6h`, minus the matched-control mean.
- L3: the side-signed return over the hour after the detected end. A negative value means the accumulated excess move shrinks. The comparator is matched times after a same-side flow burst of similar size and duration without regular slicing, matched on information available at the detected end.
- L1 (gate): same-side taker notional per hour over the remaining-execution window, against the matched controls.
- 4h is a diagnostic only.
- The hit rate is reported for display; the gates test the mean.

**Surfaces:**
- **Discovery:** Binance spot BTCUSDT, 2020-01 → 2024-12.
- **Confirmation candidate:** Binance spot BTCUSDT, 2017-08 → 2019-12 (same venue and observable, disjoint era).
- **Fallback:** BitMEX XBTUSD trades 2016–2019.
- Outcome-blind episode counts decide between them before discovery.
- No 2025+ file is downloaded.

**Feasibility gate (outcome-blind):**
- At least 300 discovery episodes on at least 100 distinct days.
- At least 100 confirmation episodes.
- The detector's frozen end rule is part of the feasibility unit. The outcome-blind counts report:
  - `N_detected`;
  - `N_persistence_eligible` (a full remaining-execution window for L1);
  - `N_with_identifiable_end`;
  - `N_with_complete_post_end_hour`.

  If the last count makes L3 underpowered, that is recorded before any price is opened.
- L1 (post-decision flow) and L2/L3 (price) are not computed in feasibility.
- Null chain rate at most 10% of the real rate at the frozen parameters.
- Planning power at least 80% for the practical bar under day-block dependence.
- Failing the gate closes the card as `INFORMATIONALLY_WEAK` before any outcome.

**Product path, only if confirmed:**
- A separate gate with exact strings.
- Live detection needs a trade-stream collector. That is a future product decision; the beta is frozen.

## 6. Sequence

1. `TWAP_FOOTPRINT_OUTCOME_BLIND_FEASIBILITY`: detector, null and recall checks, and monthly episode counts. No forward return.
2. Twin preregistration freeze under `HYPOTHESIS_EVALUATION_CONTRACT_V1`: detector parameters and end rule, the mechanism chain and its staged opening, matching, cells, bar, inference, and both surfaces.
3. Discovery one-shot on 2020–2024: stage 1 (L1, flow only), then stage 2 (L2 and L3) only if L1 passes.
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

## 8. Sealed end-to-end execution protocol (owner decision 2026-10-01, before any data)

**Decision.** The owner replaced the human approval between feasibility and scientific outcomes with deterministic gates. One run goes as far as the frozen gates allow, then returns one final report. The protection against bias is not elapsed time. It is that every outcome-sensitive choice below is frozen **before the first scientific outcome**. Nothing in this section may change after a scientific outcome is opened.

**Scientific outcomes**, opened only in this order:
1. post-detection flow (H1);
2. future price (H2);
3. post-end price (H3);
4. replication outcomes.

### Phase 0 — outcome-blind detector validation and feasibility

**Data.** Binance spot BTCUSDT `aggTrades`, checksum-verified.
- **Discovery:** 2020-01 → 2024-12.
- **Replication:** 2017-08 → 2019-12.
- No file from 2025 or later is downloaded.

**Detector candidates (pre-declared grid).** Fixed for every candidate:
- one-sided taker prints of at least $1,000;
- keyed by an identical quantity **or** an identical quote notional, rounded to $10;
- regular slices: the consecutive gap is within the absolute tolerance of the running period; period 2–300 s; at most one missed slice;
- the end rule (`TWAP_END`): the chain is declared ended once there has been no matching slice for 3 × period after the last slice. The end time is that declaration time, so it is point-in-time.

The grid itself:

| Parameter | Values |
|---|---|
| absolute gap tolerance | 250 ms, 500 ms |
| minimum slices `K` | 20, 40 |
| minimum duration | 15 min, 30 min |

**Calibration month: 2024-06, structure only.** Three quantities per candidate:
- **Recall:** 200 synthetic TWAPs (seed 20261002) are injected into the real background. They vary period (3–60 s), slice size ($2k–$50k), quantity versus notional slicing, and duration (20–120 min). `RECALL` = qualified injections / 200.
- **Shuffled false positives per day:** the hour-preserving time shuffle is repeated 5 times (seeds 20261003–20261007). Each repetition keeps each key's per-hour print count and draws times uniformly within the hour. `FP_PER_DAY` = the mean over the 5 repetitions of qualified shuffled episodes per calendar day of the month.
- **Specificity ratio:** `FP_RATIO` = (mean qualified shuffled episodes over the 5 repetitions) / (qualified real episodes in 2024-06). If the denominator is 0, the candidate is inadmissible.

**Selection rule, deterministic.** Real episode counts are never a selection criterion; they only feed the feasibility gates.
- Admissible candidates: `RECALL ≥ 0.80` and `FP_RATIO ≤ 0.10`.
- Among them, choose in this order:
  1. the lowest `FP_PER_DAY`;
  2. then the highest `RECALL`;
  3. then the simplest specification: the smaller tolerance, then the larger `K`, then the longer minimum duration, i.e. the stricter detector.
- If no candidate is admissible, stop with `FEASIBILITY_FAILED` (`DETECTOR_NOT_SPECIFIC`).

**Episodes:**
- Overlapping same-side chains merge.
- The decision time `T` is the qualifying print.
- A same-side refractory of 6 h after each `T` applies.
- Every exclusion is logged per episode with its reason: data gap in a window, file-boundary gap, window crossing the surface end.

**The four counts, per surface:**
- `N_detected`;
- `N_persistence_eligible` (a full 60-minute post-`T` window);
- `N_end_identified`;
- `N_post_end_1h_complete`.

**Feasibility gates:**
- **Discovery** needs `N_persistence_eligible ≥ 300` on at least 100 distinct UTC days. Otherwise stop with `FEASIBILITY_FAILED` (`SUPPORT`).
- **H3 support.** If discovery `N_post_end_1h_complete < 150`, H3 is not run and is marked `INFERENCE_INSUFFICIENT`. H1 and H2 continue.
- **Replication support.** If replication `N_persistence_eligible < 100`, replication is marked `INFERENCE_INSUFFICIENT`, without a substitute surface.

### Phase 1 — automatic freeze

If phase 0 passes, the run writes `TWAP_SEALED_SPEC_V1.json` before any scientific outcome. It contains:
- the chosen detector;
- the counts, exclusions, code SHA, data digests;
- this section's rules.

The run then commits and pushes it, records its SHA-256, and continues without asking.

### Matching (all phases)

**Controls for an anchor `T`:**
- times `T'` with no detected episode within ±6 h;
- the same UTC hour;
- the same tercile of prior 1h realized volatility (trailing-30-day reference);
- the same quintile of signed net taker notional over the prior 60 min (trailing-30-day reference);
- the same sign of the prior 60-minute return.

Up to 5 nearest-in-time controls per anchor, drawn without replacement. All matching variables use information available at or before `T'` only. **Post-detection flow is never a matching variable.**

**H3 anchors** are matched the same way at the end time.

**Price** is the last trade price at or before a given time, taken from the same `aggTrades`.

### Phase 2 — H1 mechanism gate

| Item | Definition |
|---|---|
| Statistic | mean over episodes of the log ratio of same-side taker notional in `[T, T+60m]`, episode against its controls' mean |
| Inference | day-block bootstrap, 10,000 draws, seed 20261002, one-sided |
| Pass | `p < 0.05` **and** the ratio ≥ 1.10, i.e. at least 10% more same-side flow |
| Fail | stop with `MECHANISM_NOT_SUPPORTED`; H2 and H3 are never computed |

### Phase 3 — price outcomes (only after H1 passes)

**H2 at 1h and at 6h.** The statistic is the mean side-signed log return from `T` to `T+h`, minus the matched-control mean.

**H3.** The statistic is the mean side-signed log return over `[end, end+1h]`, minus the matched-control mean.
- Reversal is the temporary-impact fingerprint.
- An H3 null never changes H1 or H2.

**Inference.** Day-block bootstrap, two-sided, with Holm across the three cells at `alpha = 0.05`.

**Practical floor.** At least 10 bps absolute for H2 and for H3. It is chosen in advance as the smallest economically meaningful scale. It is not a claim of net profitability.

**V1 epoch-heterogeneity gate (frozen exactly as in V1 §4).** It runs on each cell that passes Holm and the floor. Epochs are calendar years 2020–2024.
- **Heterogeneity test:** the SD of the yearly cell estimates is compared against a block permutation of 26-week blocks across years. 2,000 draws, seed 20261008, `alpha_het = 0.05`.
- **Opposite-sign test:** a year fails if its estimate has the opposite sign to the pooled estimate with one-sided `p < 0.05` (day-block bootstrap within that year, 2,000 draws).
- **Outcome:**
  - heterogeneity significant **and** at least one year significantly opposite: the cell is `HETEROGENEOUS_UNEXPLAINED` and does not count as supported;
  - heterogeneity significant with no opposite year: the cell passes with `MAGNITUDE_VARIES_BY_EPOCH`;
  - otherwise the cell passes.
- **Low power.** If the outcome-blind power to detect a 2× difference between the two smallest years is under 0.50, the result is `NOT_ASSESSABLE` and is not a failure. It is never reported as stability.

### Phase 4 — replication

This phase runs only for the cells that pass discovery. It uses the same frozen specification on Binance spot BTCUSDT 2017-08 → 2019-12.

**Provenance class, fixed before outcomes:** `TIME_DISJOINT_SAME_VENUE_SAME_INSTRUMENT_REPLICATION`.
- Discovery is also Binance spot BTCUSDT `aggTrades`, so it is the same instrument and the same feature construction. The surface is time-disjoint, so under V1 §7 it counts as replication.
- Declared limitation: 2017–2019 spot microstructure differs (lower volume, fewer algorithms). If the support gate fails, the replication status is `INFERENCE_INSUFFICIENT`.
- A perpetual or other-venue surface would be classed `CROSS_MARKET_VALIDATION`, not replication. None is used in this run.

A cell passes replication if all three hold:
- the sign is the same as in discovery;
- one-sided `p < 0.05`;
- the magnitude is at least 10 bps.

No substitute surface is used if the support gate fails.

### Final classification

The most specific status applies:
- `FEASIBILITY_FAILED`;
- `MECHANISM_NOT_SUPPORTED`;
- `MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED`;
- `DISCOVERY_SUPPORTED_REPLICATION_FAILED`;
- `DISCOVERY_SUPPORTED_REPLICATION_INSUFFICIENT`;
- `SUPPORTED_WITH_REPLICATION`;
- `INFERENCE_INSUFFICIENT`;
- `DATA_PROVENANCE_LIMITATION`.

**Blocker rule.** If a contradiction makes honest execution impossible, the run stops and reports the blocker. It never improvises.
