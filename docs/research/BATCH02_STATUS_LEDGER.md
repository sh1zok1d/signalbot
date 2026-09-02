# Signalbot Batch02 Status Ledger

**Ledger type:** post-outcome status record  
**Frozen inventory source:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Inventory mutability:** IMMUTABLE after first real Batch02 outcome  
**Current Batch02 outcome count:** 2 completed formulations  
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
| `B2-02_BOUNDARY_INTERACTION_PATH` | F1 | `CLOSED_NO_PROMOTION` | completed one-shot development verdict; see `B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` |
| `B2-03_IMPULSE_MORPHOLOGY` | F1 | `PLANNED` | no real outcomes opened |
| `B2-04_MODERATE_PULLBACK_STRUCTURE` | F1 | `PLANNED` | no real outcomes opened; explicit H04 post-hoc child |
| `B2-05_FLOW_ABSORPTION` | F4 | `PLANNED` | no real outcomes opened |
| `B2-06_LEVERAGE_CROWDING` | F5 | `BLOCKED_MISSING_OBSERVABLE` | OI + funding data expansion still required |

## 3. Family ledger

| Family | Status | Reason |
|---|---|---|
| F1 Directional persistence | `ACTIVE` | B2-02 closed without promotion; B2-03 and B2-04 remain frozen and planned |
| F2 Reversion/failure | `RETIRED` | no novelty-qualified F2 formulation exists in frozen inventory |
| F3 Volatility dynamics | `CLOSED_NO_PROMOTION` | sole frozen F3 formulation B2-01 closed without promotion |
| F4 Participation/order-flow | `UNTESTED` | B2-05 remains frozen and unopened |
| F5 State-mechanism interaction | `BLOCKED_MISSING_OBSERVABLE` | B2-06 requires separately authorized OI/funding observables |
| F6 State routing | `RETIRED` | no current-V2 routing formulation admitted |

## 4. Canonical state after B2-02

```text
BATCH01 = CLOSED
V2_RESEARCH_HARNESS_V1 = ACCEPTED
V2_RESEARCH_PROGRAM = CHARTER_ACCEPTED
V2_FORMULATION_INVENTORY = FROZEN_6_IMMUTABLE

REAL_BATCH02_OUTCOMES = OPENED_B2_01_AND_B2_02

B2_01 = CLOSED_NO_PROMOTION
B2_02 = CLOSED_NO_PROMOTION
B2_03 = PLANNED
B2_04 = PLANNED
B2_04_POSTHOC_PROVENANCE = H04_EXPLICIT_CHILD
B2_05 = PLANNED
B2_06 = BLOCKED_MISSING_OBSERVABLE

F1 = ACTIVE
F2 = RETIRED
F3 = CLOSED_NO_PROMOTION
F4 = UNTESTED
F5 = BLOCKED_MISSING_OBSERVABLE
F6 = RETIRED

NEXT_FROZEN_FORMULATION = B2_03_IMPULSE_MORPHOLOGY

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

## 6. B2-02 terminal record

```text
FORMULATION = B2-02_BOUNDARY_INTERACTION_PATH
VERDICT = B2_02_CLOSED_NO_PROMOTION
FORMULATION_STATUS = CLOSED_NO_PROMOTION
FAMILY = F1
FAMILY_STATUS = ACTIVE
RESULT_ARTIFACT_SHA256 = b5bc240bc30cff92e26b1cf5a7fca4e546c70c80b7f60d113f73f580b439e971
EXECUTION_SHA = a976a3fa3143f7290851ab8b2ddc5a9d811c891a
REVIEWED_IMPLEMENTATION_SHA = 37051de39f49b5b331a0ddbc3b37f8316811f9ef
EXECUTION_TREE = f220590be0a6323df29b8e35b47399d42c3ea137
PREREG_MERGE_SHA = cbf447276c1dc47c9a755038cfd6013199207eef
DATASET_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

F1 remains `ACTIVE` because B2-03 and B2-04 are still eligible frozen-inventory
formulations. B2-02's terminal result closes only this formulation.

## 7. Anti-rescue rule

Completed B2-01 and B2-02 outcomes do not authorize post-outcome rescue inside
current V2.

For B2-01 this includes another transition threshold, W/D/H grid, sign,
volatility normalization, target, loss, support minimum, nearby substitute, or
best-looking failed-cell child.

For B2-02 this includes another breach threshold, L/H grid, path window,
context/path-state cutpoint, target scaling rule, training-history length,
support minimum, placebo mapping, bootstrap rule, sign reversal, or child based
on an attractive failed cell.

Any such idea conceived after these outcomes remains future-program material
only and cannot enter current V2.

## 8. Next allowed research unit

The next frozen formulation is:

`B2-03_IMPULSE_MORPHOLOGY`

This ledger does not preregister B2-03, implement B2-03, or authorize B2-03
development outcomes.

B2-03 must independently complete its own frozen preregistration,
implementation, exact-SHA CI/review/merge, and only then receive a separate
development-outcome authorization.

## 9. Validation boundary

No 2025 validation or 2026 OOS outcome has been opened by Batch02 so far.

B2-01 and B2-02 are both closed at development and have no promoted candidate,
therefore neither has a validation path to open.
