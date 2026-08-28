# Signalbot V2 Research Program Charter

**Status:** `PROGRAM_CHARTER_CANDIDATE / OUTCOME_BLIND`  
**Applies to:** Batch02+  
**Primary instrument:** BTC  
**Current research substrate:** `CORE_BTC_BINANCE_V0`  
**Harness dependency:** `V2_RESEARCH_HARNESS_V1`  
**Real 2025 validation opened by this unit:** NO  
**Real 2026 OOS opened by this unit:** NO  
**Batch02 hypothesis defined by this unit:** NO

## 1. Purpose

This charter prevents the V2 research program from becoming an unbounded sequence of
`H06 -> H07 -> ... -> Hn` reformulations.

The program is finite at the level of **mechanism families and information families**.
Individual hypothesis numbers are bookkeeping only. A new number does not make an idea
scientifically new.

The purpose of V2 is not to prove that "edge does not exist anywhere." That claim is
not testable. The practical stopping claim is narrower:

> Within a predeclared information set and a finite map of economically distinct
> mechanisms, Signalbot either finds reproducible incremental information or exhausts
> that research program.

Batch01 remains closed at 0/5 promoted families. Its central inherited lesson is:

> Raw association is insufficient. A candidate must add stable information beyond a
> simpler causal market-state baseline on the same support.

## 2. Research-space unit: mechanism family, not hypothesis number

A **mechanism family** is defined by the economic/market process that is claimed to
create incremental predictive information.

Changing only one or more of the following does **not** create a new family:

- threshold;
- lookback/window;
- horizon;
- indicator implementation of substantially the same information;
- normalization;
- smoothing;
- sign convention;
- entry wording;
- nearby parameter grid;
- filtering a failed family into a subset after observing outcomes.

Such work remains inside the same family and does not reset exhaustion.

A family can contain more than one preregistered formulation, but reformulations do
not give the program an unlimited life.

## 3. Novelty gate for any new family

A proposed new family is admissible only if, before outcome inspection, it satisfies
at least one of the following:

1. **New mechanism:** it claims a materially different market process from already
   tested/retired families.
2. **New observable information:** it requires a data observable not present in the
   current information set and gives a causal reason why that observable is needed.
3. **New state-mechanism interaction:** it claims that a known mechanism changes
   behavior across a predeclared market state in a way that is itself the object of
   the test.

The proposal must also state:

- which existing family it is closest to;
- why it is not merely a transformation of that family;
- the simpler causal baseline it must beat;
- the same-support comparison it will use;
- what result would close the family.

If the novelty case cannot be written clearly before outcomes, the proposal is not a
new family.

## 4. Finite V2 mechanism map

The map is intentionally broad enough to cover genuinely different ideas, but narrow
enough to be exhaustible.

### F1 — Directional persistence / continuation

Claim class: recent market state contains incremental information that continuation is
more likely than a simpler baseline predicts.

Batch01 H03/H04 and retired E1 continuation formulations occupy part of this space.
Future work is allowed only if it passes the novelty gate.

### F2 — Reversion / failure / exhaustion

Claim class: a completed or failed move creates incremental information for reversal
or mean reversion beyond a simpler state description.

Batch01 H02/H03 occupy part of this space. Parameter-only descendants do not reopen it.

### F3 — Volatility-state dynamics

Claim class: compression, expansion, persistence, or transition in realized market
activity contains incremental information about future volatility or directional
behavior beyond simpler volatility-state baselines.

Batch01 H01 occupies part of this space. Its post-hoc reverse pattern remains
`POSTHOC_UNTESTED`, not promoted evidence.

### F4 — Participation / order-flow information

Claim class: participation, aggressor imbalance, volume composition, or closely
related current-market observables add information beyond price/volatility state.

Batch01 H05 occupies part of this space. Raw asymmetry alone is not sufficient; future
candidates must clear an incremental-information comparator.

### F5 — Predeclared state-mechanism interaction

Claim class: a mechanism has materially different predictive value in a market state
that is observable at decision time.

This is not permission to slice a failed hypothesis after seeing outcomes. The state
definition and interaction claim must be frozen before the relevant outcome read.

### F6 — State-conditional strategy routing

This is a **meta-family**, not a rescue rule.

Claim class:

> A predeclared router from observable market state to strategy/action provides
> stable incremental value over a predeclared static comparator under the same
> evaluation contract.

The allowed output may include:

- Strategy A;
- Strategy B;
- another preregistered strategy;
- `NO_TRADE`.

`NO_TRADE` is a first-class valid state. Signalbot is not required to produce a
trade in every market condition.

The router must satisfy all of the following:

- state is computable using information available at decision time;
- state taxonomy is finite and frozen before outcomes;
- strategy eligibility per state is frozen before outcomes;
- comparator selection rule is frozen before outcomes;
- router and comparator are evaluated on an explicitly defined common support;
- promotion requires incremental value over the static comparator, not merely positive
  standalone performance;
- a failed global strategy may not be "rescued" by inventing a successful-looking
  state after the failure is observed.

If the preregistered state-routing program fails its incremental-value gates, F6 is
closed. Adding another state, threshold, or cluster after the fact does not create F7.

## 5. Family accounting and exhaustion

Every admissible Batch02+ hypothesis must point to exactly one primary family
`F1...F6`.

The program ledger for each family must use one of:

- `UNTESTED`
- `ACTIVE`
- `CLOSED_NO_PROMOTION`
- `PROMOTED_CANDIDATE`
- `BLOCKED_MISSING_OBSERVABLE`
- `RETIRED_CURRENT_FORMULATION`

A new formulation inside a family updates that family's evidence record; it does not
create a new family merely by receiving a new H-number.

Post-hoc observations may generate a future preregistered child, but they remain
`POSTHOC_UNTESTED` until a clean evaluation path exists. Post-hoc children do not
retroactively change a failed result.

## 6. Stop rules for the current BTC research program

The current BTC edge-search program stops when all four conditions are true:

### S1 — Mechanism map exhausted

Every relevant family in F1-F6 has been either:

- tested and closed;
- retired with no remaining novelty-qualified formulation; or
- shown to require an unavailable observable.

### S2 — State-conditional rescue path exhausted

F5/F6 have been honestly tested where justified, or no novelty-qualified
state-mechanism claim remains.

A failed family cannot be kept alive indefinitely by adding narrower regimes.

### S3 — New proposals fail the novelty gate

The remaining proposals are predominantly:

- threshold changes;
- window changes;
- indicator substitutions;
- filters on failed setups;
- re-labeling of old mechanisms;
- outcome-motivated subsets.

At this point more H-numbers are not more research space.

### S4 — No concrete missing-observable case remains

There is no specific mechanism for which the project can state:

> We cannot test this claim with the current information set because observable X is
> missing, and X is causally required for this mechanism.

If S1-S4 hold, the canonical conclusion is:

> Signalbot did not find reproducible exploitable edge in BTC within the current
> information set, finite mechanism map, and frozen research protocol. Search inside
> this program is stopped.

This does **not** claim that no edge exists anywhere.

## 7. BTC-first instrument policy

Adding more instruments is not an automatic response to negative BTC results.

Default rule:

> Do not expand to ETH, SOL, other crypto instruments, or multi-asset search while the
> current BTC program is unresolved.

A negative BTC family result does not authorize "try the same thing on ETH."

A future instrument expansion requires a **new explicit research-program decision**.
It must not be presented as continuation/rescue of a failed BTC hypothesis.

Until such a decision is separately justified, BTC remains the primary instrument.

## 8. Data-expansion policy

Instrument expansion and information expansion are different decisions.

New BTC data types may be added only when a pre-outcome proposal contains a
**missing-observable justification**:

1. name the mechanism;
2. name the missing observable;
3. explain why current CORE data cannot test the mechanism;
4. explain why the new observable is causally related rather than merely promising;
5. freeze the new dataset identity/provenance before outcome access;
6. evaluate the new family through the V2 harness.

Examples of possible observable classes are not authorization to add them. No OI,
funding, liquidation, order-book, cross-exchange, macro, or alternative dataset is
authorized merely because it exists.

"More data might find something" is not sufficient justification.

## 9. Research-to-live parity principle

Research and live execution must not evolve into two independent implementations of
the same strategy logic.

Target architecture:

```text
canonical feature / state / decision logic
                |
        +-------+-------+
        |               |
historical adapter   live adapter
        |               |
     replay            live
```

Before any validated candidate becomes live-capable, the project must prove that a
historical replay through the live path reproduces the canonical research decisions
under the same data-availability contract.

The same definitions must govern, where applicable:

- timestamp semantics;
- availability;
- features;
- market-state classification;
- strategy/router logic;
- no-trade decisions;
- promotion/evaluation identity.

This principle is architectural now; full live implementation is not required for
Batch02 discovery.

## 10. Product transition gate

Product work is separated from evidence maturity.

### G0 — Research only

No promoted reproducible candidate. Focus on mechanism testing and integrity.

### G1 — Discovery candidate

A development candidate passes its frozen promotion contract. This is not yet a
validated edge.

### G2 — Independent validation

The candidate survives the authorized independent validation stage.

Only here may serious shadow-live engineering begin.

### G3 — OOS + research/live parity

The candidate survives untouched OOS and the live/replay path reproduces research
logic.

Only here is it reasonable to build a product whose value proposition depends on the
candidate.

### G4 — Live evidence

Sufficient live evidence exists to evaluate degradation, reliability, and operational
behavior.

Pricing, scaling, strong performance claims, and major commercial investment belong
here, not at G0.

This charter deliberately does not freeze a final moat, customer segment, pricing
model, or business model.

## 11. Mandatory comparator principle

Every future candidate must answer:

> What simpler causal explanation of the same market state could produce this apparent
> effect?

Where a meaningful simpler comparator exists, promotion requires stable incremental
information over that comparator on the same support.

A favorable raw conditional mean, hit rate, `P(Y|X)`, or visually attractive
backtest is not enough by itself.

## 12. Batch02 design boundary

This charter authorizes **Batch02 design**, not any specific Batch02 hypothesis.

Before first real Batch02 outcome access:

1. choose the first mechanism family from F1-F6;
2. write the mechanism claim and novelty case;
3. define its simpler comparator;
4. define support and no-lookahead semantics;
5. define the promotion gate contract;
6. implement through V2 Research Harness v1;
7. pass CI on exact SHA;
8. pass CodeRabbit review on exact SHA;
9. pass independent adversarial LLM review on exact SHA;
10. adjudicate findings;
11. freeze/merge;
12. only then run the authorized development outcomes.

No 2025 validation or 2026 OOS is opened merely by entering Batch02.

## 13. Non-goals

This charter does not:

- design H06;
- select Batch02 thresholds;
- define a trading rule;
- authorize new instruments;
- authorize new data sources;
- open 2025 validation;
- open 2026 OOS;
- revive H01-H05;
- convert post-hoc observations into evidence;
- claim that all possible market edge has been disproved;
- freeze the final Signalbot business model.

## 14. Canonical project state after charter acceptance

```text
BATCH01 = CLOSED
V2_RESEARCH_HARNESS_V1 = ACCEPTED
V2_RESEARCH_PROGRAM = CHARTER_ACCEPTED
PRIMARY_INSTRUMENT = BTC
BATCH02 = DESIGN_AUTHORIZED
H06 = NOT_YET_DEFINED
2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```
