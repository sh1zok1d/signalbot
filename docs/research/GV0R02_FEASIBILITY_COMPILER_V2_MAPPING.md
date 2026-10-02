# GV0R02 feasibility compiler — V2 mapping

**Status:** `IMPLEMENTED`
**Date:** 2026-10-02
**Versions:** `GV0R02_SCHEMA_V2` / `GV0R02_POLICY_V2`, under `HYPOTHESIS_EVALUATION_CONTRACT_V1`
**Code:** `scripts/research/gv0r02_feasibility_compiler_v2.py`
**Tests:** `tests/research/test_gv0r02_feasibility_compiler_v2.py`

```
V0_COMPILER_CHANGED        = false
V1_COMPILER_CHANGED        = false
OLD_RESULTS_RESCORED       = false
MARKET_OUTCOMES_OPENED     = false
C033_DESIGN_CHANGED        = false
```

## What it is

A stricter layer over the unchanged V1 compiler. `compile_proposal_v1` still scores `GV0R02_SCHEMA_V1` proposals, including the sealed C033 V1 result. A proposal is scored by V2 only when it declares `GV0R02_SCHEMA_V2` and `GV0R02_POLICY_V2`. Passing a V2 schema to V1 stays `DEFINITION_INCOMPLETE`.

V2 does not add a top-level scientific status. It uses the existing priority:

`DEFINITION_INCOMPLETE`, `DATA_BLOCKED`, `PIT_BLOCKED`, `INFERENCE_SUPPORT_INSUFFICIENT`, `STRUCTURAL_INFERENCE_RISK`, `INFORMATIONALLY_WEAK`, `FEASIBLE_FOR_PREREGISTRATION`.

## Primary mechanism support

Every primary cell takes one outcome-blind row in `PRIMARY_MECHANISM_SUPPORT`:

| Field | Rule |
|---|---|
| `KIND` | `BINARY` |
| `MECHANISM_ACTIVE_N` | non-negative integer |
| `MECHANISM_INACTIVE_N` | non-negative integer |
| `MECHANISM_VARIABLE` | optional name |

The row is compiler input. It is not a key inside the sealed `PRIMARY_CELLS` object. No target value is read. The estimand is identifiable only when both counts are positive.

| Condition | Blocker | Status family |
|---|---|---|
| support rows missing, or not one `BINARY` row per cell | `PRIMARY_MECHANISM_SUPPORT_MISSING` | `DEFINITION_INCOMPLETE` |
| `active = 0` and `inactive > 0` | `PRIMARY_MECHANISM_SUPPORT_ZERO` | `INFERENCE_SUPPORT_INSUFFICIENT` |
| `active > 0` and `inactive = 0` | `PRIMARY_MECHANISM_SUPPORT_ZERO` | `INFERENCE_SUPPORT_INSUFFICIENT` |
| both counts are 0 | `PRIMARY_MECHANISM_SUPPORT_ZERO` | `INFERENCE_SUPPORT_INSUFFICIENT` |

When either side is 0, discovery `MDE` and `POWER` are null and `NON_IDENTIFIABLE` is true. Analytic power is not computed from `NOMINAL_OBSERVATION_COUNT`.

## Permutation orbit

For `PERMUTATION_GROUP_INVARIANCE`, an all-zero or all-one binary label has one distinct assignment:

```
PRIMARY_LABEL_ORBIT_SIZE = 1
MIN_ATTAINABLE_P = 1.0
ALPHA_ATTAINABLE = false
```

Blocker: `ALPHA_UNATTAINABLE`. The same inference-support family. When both sides are positive, the two counts do not determine the stratum orbit, and `ALPHA_ATTAINABLE` stays null unless a frozen screen already supplied it.

## Power

For an identifiable binary contrast:

```
EFFECTIVE_N = MECHANISM_ACTIVE_N * MECHANISM_INACTIVE_N / (MECHANISM_ACTIVE_N + MECHANISM_INACTIVE_N)
```

Discovery MDE and power use that effective N and the frozen `GV0R02_POWER_PROFILE_V0` at the V1 Holm alpha. A nominal sample of 10000 with one active observation has effective N `0.9999` and does not inherit the nominal-N power. A shortfall is still `INFORMATIONALLY_WEAK` / `MDE_TOO_LARGE`. Balanced support uses the same formula and can remain feasible when that screen clears.

## Prospective sparse state

A prospective surface is sparse when support is missing, either side is 0, or the smaller side is below `SPARSE_STATE_MINORITY_FRACTION = 0.05` of the contrast sample. That fraction is a compiler fail-closed constant. It is not a C033 threshold and this repair does not choose `MIN_MECHANISM_ACTIVE_N` or `MIN_MECHANISM_INACTIVE_N` for C033.

A sparse prospective design must declare both floors as positive integers on the existing stopping rule. If either floor is absent, the blocker is `PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED` and the status family is `DEFINITION_INCOMPLETE`. Replication MDE and power are null. A prospective design that is not sparse keeps the V1 replication screen at `MIN_N`.

`DEFINITION_INCOMPLETE` outranks `INFERENCE_SUPPORT_INSUFFICIENT`. A sealed plan that has both zero support and no prospective floor therefore reports `DEFINITION_INCOMPLETE`, with both blocker families present.

## Not changed

`GV0R02_SCHEMA_V0`, `GV0R02_POLICY_V0`, `GV0R02_SCHEMA_V1` and `GV0R02_POLICY_V1` are unchanged. The sealed C033 planning object is not edited.
