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

## 3. Finite formulation inventory and novelty gate

Every Batch02+ proposal inside this V2 program must map to exactly one primary family
`F1...F6` from Section 4.

Before the **first real Batch02 outcome is read**, the program must freeze a finite
`V2_FORMULATION_INVENTORY`. The inventory must enumerate every formulation that is
eligible to be tested inside the current V2 program and record, for each entry:

- formulation ID;
- primary F1-F6 family;
- novelty justification;
- simpler causal comparator;
- same-support rule;
- required observable/data contract;
- deterministic close condition.

The inventory may contain any finite number of entries; this charter does not invent an
arbitrary numeric cap. Finiteness comes from freezing the actual named inventory before
outcomes.

Before that inventory freeze, a proposed entry is admissible only if it satisfies at
least one of the following:

1. **Materially new mechanism formulation inside a mapped family:** it claims a
   genuinely different market process from the already tested/retired formulations
   occupying that family.
2. **New observable information for a mapped family:** it requires a data observable
   not present in the current information set and gives a causal reason why that
   observable is needed to test the mapped mechanism.
3. **New state-mechanism interaction:** it claims that a known mechanism changes
   behavior across a predeclared market state in a way that is itself the object of
   the test.

The proposal must also state:

- which existing family/formulation it is closest to;
- why it is not merely a transformation of that formulation;
- the simpler causal baseline it must beat;
- the same-support comparison it will use;
- what result would close the formulation/family path.

Every admission/rejection decision before inventory freeze must receive independent
novelty adjudication in reviewed, frozen documentation and end in exactly one state:

- `ADMIT_TO_V2_INVENTORY`; or
- `REJECT_REFORMULATION_OR_OUT_OF_SCOPE`.

Deferral is not an admissible adjudication state.

Once the first real Batch02 outcome is read, the V2 formulation inventory is immutable.
No new H-number, threshold family, regime, state, filter, cluster, observable-driven
formulation, or post-hoc child may be added to the current V2 program. A newly conceived
idea after that point remains `POSTHOC_UNTESTED` and can enter research only through a
future explicit program charter/version with its own clean evaluation path. It cannot
extend the life of the current V2 program.

The F1-F6 map is fixed for this V2 program. A genuinely new mechanism that cannot be
mapped honestly to F1-F6 is **outside the current program**. It requires a new explicit
research-program charter/version before outcome access. It may not be appended
mid-stream as F7 merely to keep the search alive.

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

## 5. Family and formulation accounting

Every inventory formulation must point to exactly one primary family `F1...F6`.

The ledger has two separate scopes.

### Family status

Each F1-F6 family has exactly one `family_status`:

- `UNTESTED`
- `ACTIVE`
- `BLOCKED_MISSING_OBSERVABLE`
- `CLOSED_NO_PROMOTION`
- `PROMOTED_CANDIDATE`
- `RETIRED`

### Formulation status

Each named formulation has exactly one `formulation_status`:

- `PLANNED`
- `ACTIVE`
- `BLOCKED_MISSING_OBSERVABLE`
- `CLOSED_NO_PROMOTION`
- `PROMOTED_CANDIDATE`
- `RETIRED_CURRENT_FORMULATION`
- `POSTHOC_UNTESTED`

`RETIRED_CURRENT_FORMULATION` and `POSTHOC_UNTESTED` are formulation-level states.
They never close a family by themselves.

Family transitions are deterministic:

- `UNTESTED` while the frozen inventory contains eligible formulations but none has
  started;
- `ACTIVE` while any frozen-inventory formulation is `PLANNED` or `ACTIVE`;
- `BLOCKED_MISSING_OBSERVABLE` only when no runnable frozen-inventory formulation
  remains and at least one unresolved formulation is blocked on a missing observable;
- `PROMOTED_CANDIDATE` when any formulation has legitimately promoted;
- `CLOSED_NO_PROMOTION` only when every frozen-inventory formulation in that family is
  terminal as `CLOSED_NO_PROMOTION` or `RETIRED_CURRENT_FORMULATION`, with no
  promoted, planned, active, or blocked formulation remaining;
- `RETIRED` only through an explicit pre-outcome or outcome-blind program decision
  that no frozen-inventory formulation remains eligible and no unresolved observable
  dependency remains.

Post-hoc observations may be recorded as `POSTHOC_UNTESTED`, but after inventory
freeze they are not eligible members of the current V2 inventory and do not change the
family status. They may only seed a future program version.

`BLOCKED_MISSING_OBSERVABLE` is **not** an exhausted state. Before the program can be
declared exhausted, that dependency must either be resolved through an authorized
data-expansion unit and the frozen formulation tested, or be explicitly retired as
infeasible/out-of-scope.

## 6. Stop rules for the current BTC research program

The current BTC edge-search program stops when all four conditions are true:

### S1 — Frozen formulation inventory exhausted

Every F1-F6 family is deterministically terminal under Section 5:

- `CLOSED_NO_PROMOTION`; or
- `RETIRED`.

A family that is still `ACTIVE`, `UNTESTED`, `PROMOTED_CANDIDATE`, or
`BLOCKED_MISSING_OBSERVABLE` prevents an exhaustion declaration.

If any family contains a `PROMOTED_CANDIDATE`, the project exits pure discovery for
that candidate and proceeds to the authorized validation path; it does not keep tuning
that candidate to improve the development result.

### S2 — State-conditional path exhausted

F5/F6 have been honestly tested where justified, or no novelty-qualified
state-mechanism claim remains.

A failed family cannot be kept alive indefinitely by adding narrower regimes.

### S3 — No admissible current-program formulation remains

Every formulation in the frozen `V2_FORMULATION_INVENTORY` is terminal, promoted, or
explicitly blocked/retired under Section 5.

After the first real Batch02 outcome, newly proposed thresholds, windows, indicators,
filters, regimes, clusters, or post-hoc children cannot enter the current V2 inventory
at all. They remain future-program material only.

Therefore more H-numbers cannot defer S3 inside the current program.

### S4 — No unresolved missing-observable case remains

There is no unresolved mechanism for which the project can still state:

> We cannot test this claim with the current information set because observable X is
> missing, and X is causally required for this mechanism.

Any prior `BLOCKED_MISSING_OBSERVABLE` case has therefore been either:

- resolved by a separately authorized data-expansion unit and then tested; or
- explicitly retired as infeasible/out-of-scope.

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

1. name the mapped F1-F6 mechanism;
2. name the missing observable;
3. explain why current CORE data cannot test the mechanism;
4. explain why the new observable is causally related rather than merely promising;
5. freeze the new dataset identity/provenance before outcome access;
6. evaluate the resulting formulation through the V2 harness.

If the proposed new observable is needed for a mechanism that cannot be mapped to
F1-F6, it is outside this V2 program and requires a new explicit program
charter/version first.

Examples of possible observable classes are not authorization to add them. No OI,
funding, liquidation, order-book, cross-exchange, macro, or alternative dataset is
authorized merely because it exists.

"More data might find something" is not sufficient justification.

### Data-contract semantics for any authorized new observable

Missing/immature data and malformed/corrupted data are different states:

- genuinely missing or not-yet-mature data may produce a declared
  `UNAVAILABLE_FOR_DECISION` / blocked research state;
- malformed, internally inconsistent, checksum-invalid, or corrupted data must fail
  closed with the owning data/integrity error and may not be reclassified as merely
  unavailable.

Every research input must preserve exact dataset/input identity. Silent fallback is
forbidden across different symbols, market types, exchanges, calculation versions,
normalization/percentile windows, timeframes, or timeframe-aligned buckets.

If a preregistered contract requires a higher-fidelity/raw field that is present in the
authorized dataset, an adapter may not silently downgrade to a lower-fidelity derived
substitute.

For multi-timeframe research, each input's semantic role must be frozen before
outcomes (for example, decision timeframe versus contextual timeframe). The timeframe
and its aligned bucket timestamp remain part of input identity.

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
- **as-of-T availability:** every historical input used at decision boundary `T`
  must have been available by `T`; later backfills/revisions may not be substituted
  into the historical decision;
- exact timeframe and timeframe-aligned bucket timestamp identity;
- features;
- market-state classification;
- strategy/router logic;
- no-trade decisions;
- promotion/evaluation identity.

A live adapter may not relabel a source bucket with a generic decision timestamp or
collapse distinct timeframe identities merely because the numeric feature value is the
same.

This principle is architectural now; full live implementation is not required for
Batch02 discovery.

## 10. Product transition gate

Product work is separated from evidence maturity.

All promotion/transition gates are deterministic and fail closed. Missing,
unavailable, malformed, non-finite, or errored mandatory gate inputs produce
**non-promotion**, never an implicit pass. Every gate value, failure reason, and final
decision must be recorded in provenance. This applies to discovery promotion and every
later validation/OOS transition.

### G0 — Research only

No promoted reproducible candidate. Focus on mechanism testing and integrity.

### G1 — Discovery candidate

A development candidate passes its frozen promotion contract. This is not yet a
validated edge.

### G2 — Independent validation

The candidate survives the authorized independent validation stage under a frozen,
fail-closed validation contract. Missing or errored mandatory validation evidence is a
non-pass, not grounds to reinterpret or rerun the candidate.

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

1. enumerate all candidate proposals for the finite V2 program;
2. independently adjudicate every proposal as `ADMIT_TO_V2_INVENTORY` or
   `REJECT_REFORMULATION_OR_OUT_OF_SCOPE`;
3. freeze `V2_FORMULATION_INVENTORY` using only entries marked
   `ADMIT_TO_V2_INVENTORY`;
4. choose the first admitted formulation and its F1-F6 family;
5. write the mechanism claim and novelty case;
6. define its simpler comparator;
7. define support, exact input identity, and no-lookahead/as-of-T semantics;
8. define the promotion gate contract;
9. implement through V2 Research Harness v1;
10. pass CI on exact SHA;
11. pass CodeRabbit review on exact SHA;
12. pass independent adversarial LLM review on exact SHA;
13. adjudicate findings;
14. freeze/merge;
15. only then run the authorized development outcomes.

The first real Batch02 outcome read permanently freezes the current V2 formulation
inventory.

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
