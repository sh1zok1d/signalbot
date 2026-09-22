# Program decision after D2 BitMEX replication SUPPORTED

**Unit:** `PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED`  
**Kind:** program-level evidence and routing decision.  
**Date:** 2026-09-22

This unit does not run another D2 experiment, does not open Binance
2025/2026, and does not generate a nearby D2 variant. It decides what the
corrected BitMEX replication changes at the program level.

The original INVALID BitMEX one-shot remains first-class evidence. The
corrected result remains the first valid scientific replication decision.

## What was demonstrated

Internally generated D2 / RULE_1 / `RV_ABSTENTION` went through:

1. adaptive discovery on historically exposed Binance 2020-2024
   (`PROMISING_PROTOTYPE`; RULE_2 did not pass);
2. outcome-blind independent-surface selection (pre-2020 BitMEX XBTUSD);
3. preregistration, implementation review, fail-closed identity handling;
4. one corrected independent temporal + cross-venue replication
   (`D2_BITMEX_REPLICATION_SUPPORTED`).

Primary replication estimand (unchanged, not re-estimated here):

```
ABSTAIN_COUNT = 126
ABSTAIN_RATE  = 0.11808809746954077
MU_RULE       = 0.05374977245962498
MU_CONTROL    = 0.032765565858771904
DELTA         = 0.020984206600853074
RELATIVE_DELTA= 0.67420960209053
MC_P          = 9.999000099990002e-05
STATISTICAL_GATE = true
PRACTICAL_GATE   = true
```

Yearly deltas are diagnostic only and cannot upgrade classification.

## Claim ladder

| Claim | Status | Meaning |
|---|---|---|
| `DISCOVERY_CLAIM` | `SUPPORTED` | RULE_1 is a discovery-stage `PROMISING_PROTOTYPE` on exposed Binance 2020-2024. RULE_2 is not. |
| `REPLICATION_CLAIM` | `SUPPORTED` | Frozen RULE_1 survived the declared independent pre-2020 BitMEX replication under the preregistered MAE vs year-matched random-abstention estimand. Label: `INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED`. |
| `MARKET_MECHANISM_CLAIM` | `NOT_YET_SUPPORTED` | The estimand does not distinguish excess direction-aligned path-risk from mechanical MAE scale under volatility clustering, nor identify RV as the unique state variable. |
| `TRADING_EDGE_CLAIM` | `NOT_TESTED` | No costs, funding, inverse PnL, fully specified strategy, or live/future same-venue test. |
| `PRODUCT_CLAIM` | `NOT_TESTED` | Product usefulness was not a tested question. |

Do **not** call D2 `PROVEN_ALPHA`, `VALIDATED_TRADING_EDGE`,
`EXACT_BINANCE_CONFIRMATION`, or a validated strategy.

## Candidate promotion

```
PREVIOUS_CLASS = PROMISING_PROTOTYPE
D2_PROGRAM_CLASS = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE
```

This is a new lifecycle class between discovery and confirmatory
MARKET-0N / `VALIDATED_CANDIDATE`.

### Lifecycle semantics

An `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`:

- was generated internally;
- survived adaptive discovery as `PROMISING_PROTOTYPE`;
- survived one preregistered independent temporal + cross-venue
  replication of a frozen operationalization;
- may be cited as replicated under that exact estimand and surface;
- is eligible to be *proposed* for a later, different scientific question.

It does **not**:

- skip preregistration / ARM / one-shot / sealed RESULT for any later test;
- create MARKET-07;
- open protected 2025/2026;
- restart product build;
- authorize nearby threshold/horizon/RV-window variants;
- reuse BitMEX 2017-2019 as an independent confirmation surface for new
  D2-family targets or estimands;
- count as `INTERNAL_HISTORICAL_CANDIDATES_PROMOTED` (that counter stays 0).

Discovery status `PROMISING_PROTOTYPE` is retained as historical discovery
label. Program class is the stronger current label.

## Binance 2025/2026

```
BINANCE_2025_2026_DECISION = KEEP_SEALED
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
```

Opening now would spend the last exact same-venue future surface to
re-ask a question already answered on an earlier era and different venue,
without resolving volatility-clustering tautology or costs. Calendar 2025
alone was previously judged underpowered.

**Milestone that would justify consuming it:** a frozen confirmatory
contract whose remaining unanswerable question is exact Binance future
nonstationarity of a fully specified, non-tautological decision rule
(preferably after costs), with power requiring 2025 and/or 2026, *after*
mechanism-decomposition design is complete enough that the reserved
surface is not wasted on a mechanical vol-scale result.

Exact Binance future confirmation is **reserved, not necessary now**.

## What the experiment actually identifies

The frozen rule abstains when trailing 24h BTC RV exceeds the P90 of the
previous 250 valid constructed-row RV values. The target is arithmetic
MAE of a simple 24h `sign(BTC_RET_24H)` exposure from the 5m open at `T`.

That supports a **conditional-abstention / state-dependent path-risk**
operationalization: high trailing realized-volatility days have larger
subsequent direction-aligned adverse excursion than year-matched random
days at the same abstention rate.

It does **not** establish:

- that the gap exceeds mechanical MAE scaling from volatility clustering;
- that RV is the causal state rather than a proxy for any high-vol marker;
- that the state predicts unsigned path risk independently of the
  direction rule;
- that abstention improves a costed directional strategy.

Conceptual family: `CONDITIONAL_ABSTENTION_AND_STATE_DEPENDENT_PATH_RISK`.
Not proven: volatility-clustering tautology rejected; directional-edge;
execution-state; product filter.

## Discovery-engine lessons (generation priors, not beliefs)

Failed internal H / B2 / MARKET-01/02/05/06 work mostly asked whether an
extra observable improved the same short-horizon scalar prediction cell.
D2 asked a different function: when *not* to take a already-specified
naive exposure.

Priors for later generation, not hard-coded claims:

1. Rotate the **function** (filter / state / abstain / morphology /
   relative structure), not only the predictor list for one scalar.
2. Match the baseline to the decision (here: year-matched rate-matched
   random abstention, not only unconditional mean).
3. Predeclare a practical-magnitude gate.
4. Select an independent surface outcome-blind before treating discovery
   as more than a prototype.
5. Fail closed on identity; do not silently repair inside a consumed run.
6. Do not proliferate the first success. Nearby RV/threshold/horizon
   variants are forbidden as the next search move.
7. A replicated path-MAE filter can still be vol clustering. Prefer
   questions that a mechanical alternative can kill.
8. After a family is weak (M05/M06 additive cell; D3 morphology; D4
   rolling correlation), do not generate near-neighbors.

## Hypothesis generation policy

`HYPOTHESIS_GENERATION_POLICY_CHANGED = true`.

Candidate generation must rotate across families:

| ID | Family | Sprint-01 note |
|---|---|---|
| A | conditional risk / abstention | D2 RULE_1 occupies this; no immediate neighbors |
| B | directional expectation | low-priority / saturated-for-now near M05/M06 |
| C | path morphology | D3 `NO_USEFUL_STRUCTURE`; no immediate neighbors |
| D | relative / cross-asset structure | D4 rolling `NO_USEFUL_STRUCTURE`; lead-lag still deferred |
| E | liquidity / execution state | largely untested internally |
| F | regime transition | D1 deferred on null/observable mismatch |
| G | event-response / recovery | untested internally |
| H | cross-sectional or venue structure | panel sidecar; confirmatory panel still missing |
| I | externally-derived benchmarks | D6 deferred; never counted as internal discovery |

Each new experiment must eliminate or support a meaningful region. Weak
evidence in a family deprioritizes near-neighbors. This policy does not
create MARKET-07.

## Next D2 scientific question (not executed)

Not another threshold, horizon, or RV window.

```
D2_NEXT_SCIENTIFIC_QUESTION =
D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN
```

Question: does the high trailing-RV state predict **excess
direction-aligned** adverse excursion beyond the mechanical scale of
subsequent volatility (unsigned path risk / vol clustering)?

That question changes what the mechanism is. After-cost strategy tests
and exact Binance confirmation wait until this is designed; they would
otherwise spend reserved surfaces on a possibly tautological result.

Do not execute that design in this unit. Do not reuse BitMEX 2017-2019 as
independent confirmation for it.

## Product

```
PRODUCT_BUILD_FROZEN = true
OPERATING_MODE = RESEARCH_FIRST / PRODUCT_BUILD_FROZEN
```

One replicated filter is not product evidence.

**Threshold to consider product experiments:** an independently replicated
mechanism candidate **and** a fully specified, costed decision rule that
survives a reserved independent confirmatory surface **after** the
vol-clustering / direction-alignment ambiguity is addressed, such that the
remaining uncertainty is operational usefulness rather than scientific
existence.

## Next research queue

1. `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`
   — design only; no execution; no 2025/2026; no D2 variants.
2. `DISCOVERY_SPRINT_02_HETEROGENEOUS_CARD_DEFINITION`
   — new cards under the generation policy; prefer untested families
   (E, G, and F/I only if their blockers are resolved); not D2 variants.
3. `PROTECTED_BINANCE_2025_2026_REMAINS_SEALED`
   — standing constraint, not an experiment.

```
MARKET_07_CREATED = false
NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN
```
