# Signalbot Batch02 Status Ledger

**Ledger type:** post-outcome status record  
**Frozen inventory source:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Inventory mutability:** IMMUTABLE after first real Batch02 outcome  
**Current Batch02 outcome count:** 1 completed formulation  
**2025 validation:** UNTOUCHED  
**2026 OOS:** UNTOUCHED

## 1. Purpose

This ledger records deterministic status transitions after real Batch02 outcome
reads without editing the frozen `V2_FORMULATION_INVENTORY`.

It is not an admission surface. It cannot add a new formulation, threshold,
state, filter, cluster, child, or mechanism to current V2.

The authoritative formulation set remains the already-frozen six-entry inventory.

## 2. Formulation ledger

| Formulation | Primary family | Status | Evidence state |
|---|---|---|---|
| `B2-01_VOLATILITY_TRANSITION` | F3 | `CLOSED_NO_PROMOTION` | completed development verdict; see `B2_01_VOLATILITY_TRANSITION_RESULT.md` |
| `B2-02_BOUNDARY_INTERACTION_PATH` | F1 | `PLANNED` | no real outcomes opened |
| `B2-03_IMPULSE_MORPHOLOGY` | F1 | `PLANNED` | no real outcomes opened |
| `B2-04_MODERATE_PULLBACK_STRUCTURE` | F1 | `PLANNED` | no real outcomes opened; explicit H04 post-hoc child |
| `B2-05_FLOW_ABSORPTION` | F4 | `PLANNED` | no real outcomes opened |
| `B2-06_LEVERAGE_CROWDING` | F5 | `BLOCKED_MISSING_OBSERVABLE` | OI + funding data expansion still required |

## 3. Family ledger

| Family | Status | Reason |
|---|---|---|
| F1 Directional persistence | `UNTESTED` | B2-02, B2-03, B2-04 remain frozen and none has opened real outcomes |
| F2 Reversion/failure | `RETIRED` | no novelty-qualified F2 formulation exists in frozen inventory |
| F3 Volatility dynamics | `CLOSED_NO_PROMOTION` | sole frozen F3 formulation B2-01 closed without promotion |
| F4 Participation/order-flow | `UNTESTED` | B2-05 remains frozen and unopened |
| F5 State-mechanism interaction | `BLOCKED_MISSING_OBSERVABLE` | B2-06 requires separately authorized OI/funding observables |
| F6 State routing | `RETIRED` | no current-V2 routing formulation admitted |

## 4. Canonical state after B2-01

```text
BATCH01 = CLOSED
V2_RESEARCH_HARNESS_V1 = ACCEPTED
V2_RESEARCH_PROGRAM = CHARTER_ACCEPTED
V2_FORMULATION_INVENTORY = FROZEN_6_IMMUTABLE

REAL_BATCH02_OUTCOMES = OPENED_B2_01_ONLY

B2_01 = CLOSED_NO_PROMOTION
B2_02 = PLANNED
B2_03 = PLANNED
B2_04 = PLANNED_POSTHOC_CHILD
B2_05 = PLANNED
B2_06 = BLOCKED_MISSING_OBSERVABLE

F1 = UNTESTED
F2 = RETIRED
F3 = CLOSED_NO_PROMOTION
F4 = UNTESTED
F5 = BLOCKED_MISSING_OBSERVABLE
F6 = RETIRED

NEXT_FROZEN_FORMULATION = B2_02_BOUNDARY_INTERACTION_PATH

2025_VALIDATION = UNTOUCHED
2026_OOS = UNTOUCHED
```

## 5. B2-01 terminal record

```text
FORMULATION = B2-01_VOLATILITY_TRANSITION
VERDICT = B2_01_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F3
FAMILY_STATUS = CLOSED_NO_PROMOTION
RESULT_ARTIFACT_SHA256 = 3fa3ad61752d4d7d56d1dbfa172af95bec7712aebe5d2e2edfccb725971d4d2a
IMPLEMENTATION_SHA = 1a0709526d6fd4bf4799bf218dba53d2d33e5bb8
PREREG_SHA256 = 7fe105549d756a74fd9360449e7b464bf53f51560705ba1010d127ac943838fb
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

## 6. Anti-rescue rule

The B2-01 result does not authorize:

- another transition threshold;
- another W/D/H grid;
- a sign reversal;
- a different volatility normalization;
- another target;
- another loss;
- another support minimum;
- a nearby indicator substitute;
- a B2-01 child based on the best-looking failed cell.

Any such idea conceived after this outcome remains future-program material only
and cannot enter current V2.

## 7. Next allowed research unit

The next frozen formulation is:

`B2-02_BOUNDARY_INTERACTION_PATH`

This ledger does not preregister B2-02, implement B2-02, or authorize B2-02
development outcomes.

B2-02 must independently complete its own preregistration, implementation,
exact-SHA CI, CodeRabbit review, independent adversarial review, merge, and only
then receive a separate development-outcome authorization.

## 8. Validation boundary

No 2025 validation or 2026 OOS outcome has been opened by Batch02 so far.

B2-01 is closed at development and has no promoted candidate, therefore there is
no B2-01 validation path to open.
