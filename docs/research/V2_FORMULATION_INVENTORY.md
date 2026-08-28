# Signalbot V2 Formulation Inventory

**Status:** `OUTCOME_BLIND / EFFECTIVE_AS_FROZEN_ON_ACCEPTED_MERGE`  
**Program:** `V2_RESEARCH_PROGRAM_CHARTER`  
**Primary instrument:** BTC  
**Current CORE substrate:** `CORE_BTC_BINANCE_V0`  
**Real Batch02 outcomes opened by this unit:** NO  
**2025 validation opened by this unit:** NO  
**2026 OOS opened by this unit:** NO  
**New data authorized by this unit:** NO

## 1. Purpose

This document is the finite pre-outcome formulation inventory required by
`V2_RESEARCH_PROGRAM_CHARTER`.

It converts the lessons of Batch01 into a bounded Batch02 research program.

The inventory is intentionally small. It contains six admitted formulations:

1. `B2-01_VOLATILITY_TRANSITION`
2. `B2-02_BOUNDARY_INTERACTION_PATH`
3. `B2-03_IMPULSE_MORPHOLOGY`
4. `B2-04_MODERATE_PULLBACK_STRUCTURE`
5. `B2-05_FLOW_ABSORPTION`
6. `B2-06_LEVERAGE_CROWDING`

The inventory does not create six trading strategies and does not authorize any
outcome read. Each item still requires its own frozen preregistration,
implementation, promotion contract, CI, CodeRabbit review, independent
adversarial review, merge, and only then development-outcome access.

## 2. Freeze semantics

This PR is itself the pre-outcome admission/adjudication unit.

The six formulations below are proposed as
`ADMIT_TO_V2_INVENTORY`. They become the frozen current-program inventory only
when the final exact PR HEAD:

1. passes CI;
2. passes CodeRabbit novelty/governance review;
3. passes independent adversarial review;
4. has all findings adjudicated; and
5. is merged into `main`.

Once the first real Batch02 outcome is read, this inventory is immutable under
the program charter.

For every admitted formulation:

- exactly one hypothesis-specific preregistration/search surface may be frozen;
- changing thresholds, windows, horizons, state labels, signs, filters, or
  nearby indicators after outcome inspection does not create a second attempt;
- if its frozen promotion contract fails, the formulation becomes
  `CLOSED_NO_PROMOTION`;
- a materially new later idea requires a future explicit program version and
  cannot extend the current V2 program.

## 3. Batch01 inheritance rule

Batch01 closed 0/5 promoted. It did not show that BTC has no predictable
structure.

Its strongest program-level lesson is:

> A raw association is insufficient. A candidate must add stable information
> beyond a simpler causal market-state baseline on the same support.

The inventory therefore uses Batch01 residuals only as hypothesis-generation
material. No post-hoc Batch01 observation is treated as evidence or as a pass.

### Batch01 findings carried forward

- H01: compression -> expansion was rejected; lower recent volatility instead
  predicted lower subsequent realized volatility. Reverse volatility
  persistence is `POSTHOC_UNTESTED`.
- H02: failed-breakout-specific mean reversion was rejected; closing back
  inside the range was not unique incremental information. Some short-horizon
  boundary timing existed, but this does not establish successful-breakout
  continuation.
- H03: extreme impulse continuation/exhaustion produced a mixed/null,
  sign-unstable surface. Impulse magnitude alone is not carried forward.
- H04: the broad pullback-continuation claim failed, but isolated
  moderate-depth/local controlled effects remained `POSTHOC_UNTESTED`.
- H05: raw BUY/SELL asymmetry existed, but MPIE and structural incremental gates
  were 0/45 on both preregistered orientations. Imbalance alone is not carried
  forward as a standalone edge.

## 4. Admission table

| ID | Primary family | Admission | Initial formulation status | Current data |
|---|---|---|---|---|
| B2-01 | F3 | `ADMIT_TO_V2_INVENTORY` | `PLANNED` | CORE sufficient |
| B2-02 | F1 | `ADMIT_TO_V2_INVENTORY` | `PLANNED` | CORE sufficient |
| B2-03 | F1 | `ADMIT_TO_V2_INVENTORY` | `PLANNED` | CORE sufficient |
| B2-04 | F1 | `ADMIT_TO_V2_INVENTORY` | `PLANNED` | CORE sufficient |
| B2-05 | F4 | `ADMIT_TO_V2_INVENTORY` | `PLANNED` | CORE sufficient |
| B2-06 | F5 | `ADMIT_TO_V2_INVENTORY` | `BLOCKED_MISSING_OBSERVABLE` | OI + funding required |

No other formulation is admitted to the current V2 program.

## 5. B2-01 — Volatility transition

**ID:** `B2-01_VOLATILITY_TRANSITION`  
**Primary family:** F3 — volatility-state dynamics  
**Batch01 source:** H01 reverse volatility-persistence residual  
**Admission:** `ADMIT_TO_V2_INVENTORY`

### Mechanism claim

The predictive content of realized-volatility state may lie in its transition
dynamics rather than in the simple label "compressed" or "expanded".

The testable claim is:

> A predeclared volatility-transition state adds stable information about future
> realized-volatility behavior beyond the current volatility level alone.

This is not a second compression -> expansion test.

### Novelty case

H01 tested whether unusually low recent realized volatility predicts subsequent
expansion. It did not test whether the direction/rate/persistence of change in
volatility adds information conditional on the current volatility level.

The new object is therefore the **transition process**, not a new compression
threshold.

### Simpler causal baseline

Current realized-volatility state/level only, using the same decision times and
future outcome windows.

### Same-support rule

Candidate and baseline must be evaluated on exactly the same eligible decision
times. Any transition feature used at decision time must be available as-of
that decision boundary.

### Future preregistration may define

One finite search surface for transition-state construction, horizons, and
promotion gates.

It may not create multiple sequential children after outcomes.

### Close condition

If the frozen transition formulation does not show stable incremental
information over current volatility level on the same support under its full
promotion contract, `B2-01` becomes `CLOSED_NO_PROMOTION`.

No new compression/expansion/transition threshold variant is admitted afterward
inside current V2.

## 6. B2-02 — Boundary interaction path

**ID:** `B2-02_BOUNDARY_INTERACTION_PATH`  
**Primary family:** F1 — directional persistence / continuation  
**Batch01 source:** H02 boundary-timing residual and failed-close failure  
**Admission:** `ADMIT_TO_V2_INVENTORY`

### Mechanism claim

A boundary breach is not treated as informative merely because price crossed a
range edge.

The testable claim is:

> Conditional on the same pre-breach market state and comparable boundary
> displacement, the decision-time-observable path of interaction with the
> breached boundary adds incremental information about directional persistence.

The relevant concept is acceptance/rejection **path structure**, not the
binary H02 label "closed back inside".

### Novelty case

H02 rejected failed-breakout-specific mean reversion. It did not establish
successful-breakout continuation and it did not test a preregistered
post-boundary path state conditional on the same breach magnitude/state.

This formulation must not use H02's stronger successful-breakout control as if
it were positive evidence for continuation.

### Simpler causal baseline

Boundary breach magnitude + pre-breach price/volatility state, without the
post-breach interaction-path descriptor.

### Same-support rule

Candidate and baseline use exactly the same qualifying breaches. No support may
be selected based on which path state later looks favorable.

### Future preregistration may define

One finite path-state construction using only information available by decision
time, for example a frozen combination of residence beyond the boundary,
retest/re-entry behavior, path depth, and directional efficiency.

Those examples are not authorization for post-outcome feature shopping.

### Close condition

If the single frozen path formulation does not add stable continuation
information beyond the breach/state baseline under the full promotion contract,
`B2-02` becomes `CLOSED_NO_PROMOTION`.

No second acceptance/rejection definition is admitted in current V2.

## 7. B2-03 — Impulse morphology

**ID:** `B2-03_IMPULSE_MORPHOLOGY`  
**Primary family:** F1 — directional persistence / continuation  
**Batch01 source:** H03 failure of impulse magnitude as a robust mechanism  
**Admission:** `ADMIT_TO_V2_INVENTORY`

### Mechanism claim

Two price displacements of similar magnitude may have different informational
content when one is concentrated in a short shock and another is produced by
distributed directional pressure.

The testable claim is:

> Conditional on comparable signed displacement, volatility state, and decision
> horizon, predeclared impulse-path morphology adds stable incremental
> information about subsequent directional persistence.

### Novelty case

H03 varied impulse windows and tail thresholds around impulse magnitude and
found sign instability. This formulation does not retune extremeness.

Its distinct object is the **shape of the realized path that generated the same
displacement**.

### Simpler causal baseline

Signed displacement magnitude + current volatility state over the same support.

### Same-support rule

Morphology candidate and displacement baseline are paired on the exact same
impulse events. The morphology descriptor cannot change event eligibility after
outcomes are inspected.

### Future preregistration may define

One finite morphology descriptor/search surface, potentially using predeclared
quantities such as return concentration, path efficiency, or counter-move depth.

The preregistration must freeze the descriptor family before outcomes and may
not test an open-ended menu of candle/path indicators.

### Close condition

If morphology does not provide stable incremental information beyond same-event
displacement/volatility baseline, `B2-03` becomes
`CLOSED_NO_PROMOTION`.

Current V2 then contains no further "extreme move shape" child.

## 8. B2-04 — Moderate-depth pullback structure

**ID:** `B2-04_MODERATE_PULLBACK_STRUCTURE`  
**Primary family:** F1 — directional persistence / continuation  
**Batch01 source:** H04 isolated moderate-depth/local residual  
**Admission:** `ADMIT_TO_V2_INVENTORY`  
**Post-hoc provenance:** explicit `POSTHOC_UNTESTED` child

### Mechanism claim

H04 showed that a broad depth-neighborhood continuation claim was false. The
only allowed child asks whether the isolated moderate-depth effect corresponds
to a specific structural interaction rather than to depth itself.

The testable claim is:

> Within an established directional state and a preregistered moderate pullback
> domain, one predeclared structural property of the pullback/recovery process
> adds stable continuation information beyond trend state + pullback depth
> alone.

### Novelty case

This is the **one** H04-derived child allowed by the Batch01 synthesis.

It is not permission to search for a better depth threshold, another trend
indicator, or whichever H04 cell looked best.

The child must explain a causal structural property that H04 did not directly
test.

### Simpler causal baseline

Established-trend state + the preregistered moderate-depth condition.

### Same-support rule

Candidate and baseline use exactly the same moderate-domain events. The
structural property may score/classify those events but may not silently change
the support.

### Future preregistration may define

Exactly one structural property family and one finite evaluation surface.

The preregistration must explicitly cite the H04 post-hoc origin and must not
claim independence from Batch01 discovery.

### Close condition

Failure of the full promotion contract closes `B2-04` and closes the H04
child path inside current V2.

No second moderate-depth child is admitted.

## 9. B2-05 — Flow absorption / price impact

**ID:** `B2-05_FLOW_ABSORPTION`  
**Primary family:** F4 — participation / order-flow information  
**Batch01 source:** H05 failure of imbalance-alone incremental value  
**Admission:** `ADMIT_TO_V2_INVENTORY`

### Mechanism claim

Aggressive flow is potentially informative through the market's **price
response to that flow**, not through imbalance magnitude alone.

The testable claim is:

> Conditional on comparable taker-flow imbalance and price/volatility state,
> a predeclared measure of contemporaneous price impact/absorption adds stable
> information about subsequent directional behavior.

Conceptually, strong aggressive buying that moves price efficiently is a
different state from strong aggressive buying that is absorbed with little
price response.

### Novelty case

H05 directly tested extreme taker imbalance -> subsequent return and found no
MPIE/structural promotion in 45/45 cells for either orientation.

This formulation therefore cannot promote imbalance itself. Its new object is
the interaction between aggressive flow and contemporaneous price response.

### Simpler causal baseline

Taker imbalance + current price/volatility state on the exact same events.

### Same-support rule

The absorption/impact candidate and imbalance baseline must use identical event
support. No BUY-only, SELL-only, horizon-only, or year-only support may be
selected after outcomes.

### Future preregistration may define

One finite impact/absorption descriptor/search surface from currently authorized
CORE observables.

### Close condition

If price-response/absorption does not add stable information beyond
imbalance + state under the full promotion contract, `B2-05` becomes
`CLOSED_NO_PROMOTION`.

No further taker-imbalance threshold child is admitted in current V2.

## 10. B2-06 — Leverage crowding

**ID:** `B2-06_LEVERAGE_CROWDING`  
**Primary family:** F5 — predeclared state-mechanism interaction  
**Batch01 source:** program-level missing-information diagnosis, not a positive
Batch01 residual  
**Admission:** `ADMIT_TO_V2_INVENTORY`  
**Initial status:** `BLOCKED_MISSING_OBSERVABLE`

### Mechanism claim

Price moves with different leverage/positioning states may have different
subsequent behavior even when the visible price/volatility/flow state is
similar.

The testable claim is:

> A predeclared BTC perpetual leverage-crowding state formed from open interest
> and funding changes the predictive value of a comparable price displacement,
> adding stable information beyond a price/volatility/flow-only baseline.

This is a state-mechanism interaction, not "high funding is bearish" or
"rising OI is bullish".

### Missing observable

Current `CORE_BTC_BINANCE_V0` does not contain the required historical
decision-time open-interest and funding observables.

Required observable classes:

- BTC perpetual/futures open interest;
- BTC perpetual funding rate and its decision-time availability semantics.

Exact venue, symbol/contract identity, calculation version, timestamps,
granularity, provenance, and snapshot hashes are **not authorized here** and
must be frozen in a separate data-expansion unit before any B2-06 outcome
access.

No silent fallback across venue, symbol, market type, funding calculation, OI
definition, or timeframe is permitted.

### Why the observable is causally relevant

OI helps distinguish position accumulation/reduction from price movement alone.
Funding describes the cost/skew of perpetual positioning. Jointly they provide a
directly different information layer from price, volatility, and taker-volume
features already explored in Batch01.

### Simpler causal baseline

Comparable price displacement + current price/volatility/flow state, without
OI/funding.

### Same-support rule

Once the data contract is authorized, candidate and baseline must use the exact
same timestamps for which all required as-of-T inputs are valid. Missing or
corrupted positioning data cannot be filled by another venue or contract.

### Close condition

If the required data cannot be authorized with adequate exact identity and
decision-time semantics, `B2-06` is explicitly retired as infeasible/out of
scope.

If the data are authorized and the frozen leverage-crowding interaction fails
its full promotion contract, `B2-06` becomes `CLOSED_NO_PROMOTION`.

No second OI/funding crowding formulation is admitted in current V2.

## 11. Family ledger after inventory acceptance

The intended family ledger after this inventory is accepted is:

| Family | Status | Reason |
|---|---|---|
| F1 Directional persistence | `UNTESTED` | B2-02, B2-03, B2-04 admitted |
| F2 Reversion/failure | `RETIRED` | no novelty-qualified reversion formulation admitted after H02/H03 |
| F3 Volatility dynamics | `UNTESTED` | B2-01 admitted |
| F4 Participation/order-flow | `UNTESTED` | B2-05 admitted |
| F5 State-mechanism interaction | `BLOCKED_MISSING_OBSERVABLE` | B2-06 requires OI/funding |
| F6 State routing | `RETIRED` | no component evidence exists pre-outcome; routing between unproven mechanisms is not admitted |

`F6 = RETIRED` is deliberate for the **current** V2 inventory. A future
program version may reconsider a router if independent component evidence later
exists, but the current program will not add F6 after outcomes merely because
some component looks promising.

## 12. Execution order

Default execution order:

1. `B2-01_VOLATILITY_TRANSITION`
2. `B2-02_BOUNDARY_INTERACTION_PATH`
3. `B2-03_IMPULSE_MORPHOLOGY`
4. `B2-04_MODERATE_PULLBACK_STRUCTURE`
5. `B2-05_FLOW_ABSORPTION`
6. `B2-06_LEVERAGE_CROWDING` after a separately authorized data-expansion unit

Execution order is operational, not evidence. It may change for engineering
reasons before a formulation starts, but no formulation may be added or
redefined by that reordering.

## 13. Explicitly rejected proposals for current V2

The following are not admitted:

- another compression threshold / expansion threshold;
- another failed-breakout mean-reversion definition;
- another extreme-impulse threshold or sign choice;
- more than one H04 moderate-depth child;
- taker-imbalance threshold retuning;
- BUY-only or SELL-only H05 rescue;
- ETH/SOL duplication of failed BTC formulations;
- generic RSI/MACD/EMA/candle-pattern substitutions;
- generic "add more indicators";
- liquidation/order-book/on-chain/macro/sentiment data without a separately
  mapped missing-observable mechanism;
- state router/F6 in the current V2 inventory.

These may not be added after the first Batch02 outcome.

## 14. Batch02 start boundary

Inventory acceptance does **not** authorize outcome access.

For `B2-01`, the next unit after inventory acceptance must still:

1. write the exact hypothesis/preregistration;
2. freeze one finite transition-state search surface;
3. freeze the simpler comparator and exact same-support semantics;
4. freeze the promotion-gate contract;
5. implement through V2 Research Harness v1;
6. add hypothesis-specific adversarial tests;
7. pass CI on exact SHA;
8. pass CodeRabbit on exact SHA;
9. pass independent adversarial LLM review on exact SHA;
10. adjudicate all findings;
11. merge the exact reviewed SHA;
12. only then authorize B2-01 development outcomes.

## 15. Canonical project state after inventory acceptance

```text
BATCH01 = CLOSED
V2_RESEARCH_HARNESS_V1 = ACCEPTED
V2_RESEARCH_PROGRAM = CHARTER_ACCEPTED
V2_FORMULATION_INVENTORY = FROZEN_6
PRIMARY_INSTRUMENT = BTC
B2_01 = PLANNED
B2_02 = PLANNED
B2_03 = PLANNED
B2_04 = PLANNED_POSTHOC_CHILD
B2_05 = PLANNED
B2_06 = BLOCKED_MISSING_OBSERVABLE
F2 = RETIRED_CURRENT_PROGRAM
F6 = RETIRED_CURRENT_PROGRAM
REAL_BATCH02_OUTCOMES = UNOPENED
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```
