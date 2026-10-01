# GV0R02 feasibility compiler — V1 mapping

**Status:** `IMPLEMENTED`
**Date:** 2026-10-01
**Versions:** `GV0R02_SCHEMA_V1` / `GV0R02_POLICY_V1`, under `HYPOTHESIS_EVALUATION_CONTRACT_V1`
**Code:** `scripts/research/gv0r02_feasibility_compiler_v1.py`
**Tests:** `tests/research/test_gv0r02_feasibility_compiler_v1.py`

```
V0_COMPILER_CHANGED        = false
OLD_RESULTS_RESCORED       = false
MARKET_OUTCOMES_OPENED     = false
GENERATOR_CHANGED          = false
NEXT_UNIT                  = GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING
```

## What it is

A V1 layer over the unchanged V0 compiler:
- **V0 passes run unchanged.** That covers source and feature availability, point-in-time status, structural dependence, inference support and the era policy. Their harder statuses carry through.
- **New in V1:** the definition checks of `HYPOTHESIS_EVALUATION_CONTRACT_V1`, Holm-adjusted power over the declared primary cells, a replication power screen, a protected-window check, and an epoch-heterogeneity assessability record.
- **Unchanged:** the status set and its priority.
- **Version scope.** V0 proposals keep compiling under V0. A proposal compiled under V1 must carry the V1 fields.

## V1 fields

| Field | Values | Contract § |
|---|---|---|
| `CLAIM_TYPE` | `CONTEXT_DESCRIPTIVE`, `INCREMENTAL` | 2 |
| `TARGET_CLASS` | `UNCONDITIONAL`, `CONDITIONAL` | 1, 5 |
| `VARIABLE_ROLES` | `REGIME_VARIABLES`, `MECHANISM_VARIABLES`, `NUISANCE_BASELINE_VARIABLES` | 2 |
| `INTRADAY` | boolean | 3 |
| `NUISANCE_EXCLUSIONS` | `[{VARIABLE, MECHANISM_ARGUMENT}]`, optional | 3 |
| `NUISANCE_DIAGNOSTIC_PLANNED` | must be `true` for context claims | 3 |
| `PRIMARY_CELLS` | 1–3 cells of `{REGIME, ESTIMAND, HORIZON}` | 6 |
| `PRACTICAL_BAR_BASIS` | `COSTS`, `PRODUCT_RELEVANCE` | 4, 9 |
| `DISCOVERY_SURFACE` | `{ID, START, END}`, end exclusive | 1 |
| `REPLICATION_SURFACE` | `HISTORICAL {ID, START, END, NOMINAL_OBSERVATION_COUNT}`, or `PROSPECTIVE {ID, START, STARTS_AFTER_FREEZE, STOPPING_RULE}` | 7 |
| `EPOCHS` | `CALENDAR_YEAR`, or a declared list | 4 |

## Checks

**Definition checks.** Each failure gives `DEFINITION_INCOMPLETE` with its own blocker code:

| Blocker | Rule |
|---|---|
| `V1_FIELDS_MISSING` | any V1 field absent |
| `CLAIM_TYPE_INVALID`, `TARGET_CLASS_INVALID`, `INTRADAY_INVALID` | value outside its set |
| `MECHANISM_VARIABLES_MISSING` | no mechanism variable named |
| `MECHANISM_CONDITIONED_AWAY` | a mechanism variable is also a nuisance variable |
| `REGIME_MISSING_FOR_CONDITIONAL_CLAIM`, `REGIME_DECLARED_FOR_UNCONDITIONAL_CLAIM` | regime variables inconsistent with the target class |
| `CONTEXT_CLAIM_DIRECTIONAL` | a context claim on `FIRST_MOMENT` or `RELATIVE_VALUE` |
| `CONTEXT_NUISANCE_DIAGNOSTIC_MISSING` | a context claim without the planned nuisance-matched diagnostic |
| `STANDARD_NUISANCE_MISSING` | an `INCREMENTAL` claim without `PRIOR_REALIZED_VOLATILITY`, `LAGGED_TARGET` and, if intraday, `TIME_OF_DAY`, and without a written exclusion argument |
| `PRACTICAL_BAR_BASIS_INVALID` | a context claim not on product relevance, or a directional `INCREMENTAL` claim not on costs |
| `PRIMARY_CELLS_INVALID` | 0 or more than 3 cells; a cell without estimand or horizon; a conditional cell without a regime |
| `DISCOVERY_SURFACE_INVALID`, `REPLICATION_SURFACE_INVALID` | unparsable or empty interval, or unknown kind |
| `REPLICATION_NOT_TIME_DISJOINT` | the replication interval overlaps discovery, or a prospective start falls before the discovery end |
| `REPLICATION_COUNT_MISSING` | a historical replication without a declared nominal count |
| `PROSPECTIVE_NOT_AFTER_FREEZE` | `STARTS_AFTER_FREEZE` is not `true` |
| `STOPPING_RULE_MISSING`, `STOPPING_RULE_INVALID` | any of these fails: `MAX_EPISODES` or `END_DATE`; `MIN_N`; `COUNTS_ONLY_MONITORING = true`; `PRODUCT_EXPOSURE_HANDLING`; `MIN_N ≤ MAX_EPISODES`; end date after start (amendment A1) |
| `MULTIPLICITY_NOT_ADJUSTED` | a frozen power screen for more than one cell without `MULTIPLICITY_ADJUSTED = true` |

**Protected window.** A discovery or historical replication surface that overlaps 2025-01-01 to 2027-01-01, or a prospective surface that starts before 2027-01-01, gives `DATA_BLOCKED` with blocker `PROTECTED_SURFACE_DECISION_REQUIRED`. The compiler never grants protected access.

**Power:**
- **Discovery.** The frozen `GV0R02_POWER_PROFILE_V0`, at the first Holm step `alpha / k`, where `k` is the number of primary cells. A stress shortfall gives `INFORMATIONALLY_WEAK` with blocker `MDE_TOO_LARGE`.
- **Replication.** The same profile at the declared historical count, or at the prospective `MIN_N`. A shortfall gives `INFORMATIONALLY_WEAK` with blocker `REPLICATION_MDE_TOO_LARGE`. This is the twin preregistration's power on both surfaces.

**Heterogeneity assessability:**
- **How it is computed.** It is the stress power to detect a difference of the minimum meaningful effect between the two smallest epochs, at `alpha_het = 0.05`.
- **Result.** At 0.50 or more it is `ASSESSABLE`. Otherwise, or with fewer than three epochs with counts, it is `NOT_ASSESSABLE`.
- **Never a blocker.** The record always carries `NOT_EVIDENCE_OF_STABILITY = true` (amendment A2).

## Acceptance

| Case | V1 status |
|---|---|
| Golden C012 + neutral V1 declaration | `INFORMATIONALLY_WEAK` (same as V0) |
| Golden C004 + neutral V1 declaration | `INFERENCE_SUPPORT_INSUFFICIENT` (same as V0) |
| Golden C020 + neutral V1 declaration | `INFORMATIONALLY_WEAK` (same as V0) |
| V0 positive control + V1 declaration | `FEASIBLE_FOR_PREREGISTRATION` |
| Positive control with 3 cells at N = 850 | `INFORMATIONALLY_WEAK`; it is `FEASIBLE` with 1 cell |
| Live prospective surface starting 2026-11 | `DATA_BLOCKED` (`PROTECTED_SURFACE_DECISION_REQUIRED`) |

**Test-suite note.** `test_gv0r02_feasibility_compiler_design.py::test_compiler_is_outside_the_generator` had failed on `main` since GV0R03 added `generator_v0/feasibility_contract.py`. Its intent, the compiler outside the generator, is kept. It now checks for `*compiler*` instead of `*feasibility*`.

## Not done here

The generator-side planning contract (`GV0R03`) and the generator card prompt do not emit the V1 fields yet. That is the next unit, `GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING`, followed by the fresh shadow run with a capped budget.
