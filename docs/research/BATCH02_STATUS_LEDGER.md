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
| `B2-02_BOUNDARY_INTERACTION_PATH` | F1 | `CLOSED_NO_PROMOTION` | completed development verdict; see `B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` |
| `B2-03_IMPULSE_MORPHOLOGY` | F1 | `PLANNED` | no real outcomes opened |
| `B2-04_MODERATE_PULLBACK_STRUCTURE` | F1 | `PLANNED` | no real outcomes opened; explicit H04 post-hoc child |
| `B2-05_FLOW_ABSORPTION` | F4 | `PLANNED` | no real outcomes opened |
| `B2-06_LEVERAGE_CROWDING` | F5 | `BLOCKED_MISSING_OBSERVABLE` | OI + funding data expansion still required |

## 3. Family ledger

| Family | Status | Reason |
|---|---|---|
| F1 Directional persistence | `OPEN` | B2-02 closed without promotion; B2-03 and B2-04 remain frozen and unopened |
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

F1 = OPEN
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
FAMILY_STATUS = OPEN
RESULT_ARTIFACT_SHA256 = 971b645a0eb8b45293f7c2f589c9666a037fe602a6f228751162b13bf0054646
IMPLEMENTATION_SHA = a976a3fa3143f7290851ab8b2ddc5a9d811c891a
REVIEWED_IMPLEMENTATION_SHA = 37051de39f49b5b331a0ddbc3b37f8316811f9ef
GIT_TREE = f220590be0a6323df29b8e35b47399d42c3ea137
PREREG_JSON_SHA256 = 3dd11009cd738ab02ab3a3a0a552de9a25a6c4db765d6510f63937c922a6d7b1
PREREG_MERGE_SHA = cbf447276c1dc47c9a755038cfd6013199207eef
RERUN_AUTHORIZED = NO
REFORMULATION_CURRENT_V2 = NO
```

## 7. Anti-rescue rule

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

The B2-02 result does not authorize:

- another path window;
- another path-score weighting or component substitution;
- a binary inside/outside-close filter;
- a sign reversal of `PATH_SEPARATION`;
- another L/H grid;
- another support minimum;
- a one-sided UPPER/LOWER rescue;
- a B2-02 child based on the `L=60 H=30` placebo pass or any other failed cell;
- opening 2025 or 2026 to rescue this development verdict.

Any such idea conceived after these outcomes remains future-program material
only and cannot enter current V2.

## 8. Next allowed research unit

The next frozen formulation is:

`B2-03_IMPULSE_MORPHOLOGY`

This ledger does not preregister B2-03, implement B2-03, or authorize B2-03
development outcomes.

B2-03 must independently complete its own preregistration, implementation,
exact-SHA CI, CodeRabbit review, independent adversarial review, merge, and only
then receive a separate development-outcome authorization.

B2-02 rerun after this completed market verdict is **NOT AUTHORIZED**.

## 9. Validation boundary

No 2025 validation or 2026 OOS outcome has been opened by Batch02 so far.

B2-01 and B2-02 are both closed at development and have no promoted candidate,
therefore there is no B2-01 or B2-02 validation path to open.
