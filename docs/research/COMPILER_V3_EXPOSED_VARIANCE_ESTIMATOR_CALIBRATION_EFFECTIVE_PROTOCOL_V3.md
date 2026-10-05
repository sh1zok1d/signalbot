# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — effective calibration protocol V3 (amendments V1 + V2 + V3 applied; not executed)

**Status:** `EFFECTIVE_PROTOCOL / EXECUTION_NOT_AUTHORIZED / NOT_RUN / NO_OUTCOME_READ`. Owner decision 2026-10-04 after amendment commit `0043ebe` (accepted as audit artifact; executor and CAL/EVAL execution not allowed).

**What this document is.** Protocols V1 (`b3cb784c…`) and V2 (`806b9394…`) stay immutable, as do the original freeze, the 621-cell grid and the 198-cell probe grid. This V3 restates the protocol as amended by `…_FREEZE_AMENDMENT_V3.json` (immutable). Everything not repeated here is unchanged from V2. Written before any CAL or EVAL replicate exists; Run 1 outcomes not read.

---

## C1. Candidate selection is per design class (replaces A3 selection and B3's joint selection)

Required classes (`REQUIRED_FOR_V3 = true`): `TWO_SAMPLE`, `PAIRED_UNITS`, `CLUSTERED`, `RARE_EVENT`. Selectable candidates per class: A, B, C. D is reference-only and outside the selection family.

For each required class independently:

```
SELECTED_CANDIDATE(class) = first ELIGIBLE candidate in the order A -> B -> C
```

A result such as TWO_SAMPLE → A, PAIRED_UNITS → B, CLUSTERED → C, RARE_EVENT → B is intended and valid. No global candidate exists.

## C2. Error budget for per-class selection (replaces A2)

Family budget `ALPHA_FAMILY = 0.01`. Four required classes × three selectable candidates = 12 class-candidate decisions:

`ALPHA_CLASS_CANDIDATE = 0.01 / 12 = 1/1200`, candidate-decisive one-sided exact Clopper–Pearson confidence `CONF_CLASS_CANDIDATE = 1199/1200 = 0.999166…`.

No further Bonferroni over MUST cells: a class-candidate PASS is an intersection–union decision (every required cell must PASS). D stays at 0.99 as reference. Deterministic success-count thresholds at `1199/1200` (coverage: misses `s`; utility: successes `u`):

| Stage | Coverage PASS iff `s ≤` | Coverage FAIL iff `s ≥` | Utility PASS iff `u ≥` | Utility FAIL iff `u ≤` |
|---|---|---|---|---|
| A, 4 000 | 21 | 110 | 3 280 | 3 119 |
| B, 20 000 | 156 | 465 | 16 178 | 15 820 |

Between the two thresholds the check is `ESCALATE` (Stage A) or `CALIBRATION_INDETERMINATE` (after Stage B). PASS and FAIL regions are disjoint for both checks. These numbers are bound in amendment V3 and recomputed by the validator.

## C3. EVAL support surface: every integer count (replaces B1's interval rule)

The CAL table is unchanged: `c_raw` / `c_env` are fitted on the CAL split at the frozen calibrated sizes only (A6). The **EVAL support surface** is extended so that for every integer count in the declared supported range of a class there is a decisive EVAL cell at every required MUST structural level:

| Class | Supported range `[n_min, REALISTIC_MAX]` | Calibrated sizes in range | Probe sizes in range | Dense exact counts | Dense cells |
|---|---|---|---|---|---|
| TWO_SAMPLE (per arm, equal arms) | 30 … 250 | 30, 60, 120, 250 | 42, 85, 173 | 214 | 1 284 |
| PAIRED_UNITS | 40 … 260 | 40, 60, 100, 160, 260 | 49, 77, 126, 204 | 212 | 1 272 |
| CLUSTERED (G) | 8 … 40 | 8, 15, 25, 40 | 11, 19, 32 | 26 | 624 |
| RARE_EVENT (events) | 30 … 100 | 30, 50, 75, 100 | 39, 61, 87 | 64 | 1 536 |

Total dense cells 4 716 (`…_GRID_DENSE_SUPPORT_V1.json`, built by `build_dense_support_cells.py`; EVAL-only, decisive, seed base `9·10¹² + 10¹⁰·family_index (21–24) + 10⁶·cell_index`, ranges `[9 210 000 100 000, 9 244 715 119 999]`, verified pairwise disjoint and disjoint from Run 1, from the 621 calibration cells and from the 198 probes; no existing cell renumbered). The calibrated sizes 500 (TWO_SAMPLE) and 400 (PAIRED_UNITS) and the probes 354 and 322 remain CAL/EVAL cells but lie above the supported range: they serve the CAL table and are reported, and are not supported counts. The supported range ends at `REALISTIC_MAX` because support requires utility, and utility is defined only in range (B4).

**Support set.** `SUPPORT_SET = sorted (class, n, structural-level key)` over every EVAL support cell in range: 5 148 rows, sha256 `c6b0444de824281c7bdea7724ed51a63fb34ab82e9d9ef6c94900b0d0620fe5e`, recorded in the dense artifact and bound in amendment V3.

**Count support rule (per class and candidate X).** A count `n` is **SUPPORTED** for X iff `n` is inside the class range, `n` is in the support set, and every EVAL cell at `(class, n)` (all MUST levels) is coverage `PASS` and utility `PASS` for X. A count with any `FAIL` cell is `UNSUPPORTED_DECISIVE`; a count with no `FAIL` but an unresolved cell is `UNSUPPORTED_UNRESOLVED`; a count absent from the support set is unsupported. No interpolation claim and no monotonicity assumption fill a missing or failed count. Outside the range: `NOT_FEASIBLE_INFORMATION_INSUFFICIENT`.

## C4. Candidate C application (replaces B1 application)

For a supported exact count `n` of a class: take the largest calibrated size `n_i ≤ n`, use the frozen `c_env(class, n_i)`, and require the EVAL cell at exactly `n` (all MUST levels) to have passed coverage and utility under that factor. Counts below the smallest and above the largest calibrated size are unsupported; a count must also lie inside the declared class range. For a calibrated size the calibrated EVAL cells are themselves the support evidence. Candidates A and B apply their own formulas at `n` and are supported at `n` under the same count support rule.

## C5. TWO_SAMPLE allocation (binds this unit)

`TWO_SAMPLE_ALLOCATION_DOMAIN = EQUAL_ARMS_ONLY`. Every CAL, EVAL, probe and dense claim for TWO_SAMPLE refers to `n_a = n_b` only. Unequal arms → `NOT_FEASIBLE_INFORMATION_INSUFFICIENT`. No sparse 1:2 or 1:4 ratios are added, and none would count as arbitrary-allocation support. If the operational compiler needs unequal binary contrasts after this calibration, a separate preregistered unit `TWO_SAMPLE_UNEQUAL_ALLOCATION_CALIBRATION` with its own two-dimensional outcome-blind surface is created; that is a separate design, not an amendment after this unit's results are read.

## C6. Per-class and global state machine (literal; replaces A3 eligibility and B4's candidate-level aggregation)

Required cells of a class for candidate X: the calibrated MUST EVAL cells of the class **at the calibrated sizes inside the supported range**, the probe cells in range, and the dense cells. Utility uses B4 with `S` = all in-range sizes that carry cells (calibrated, probe, dense).

```
COVERAGE(X, class) = PASS   if every required cell is coverage PASS
                   = FAIL   if any required cell is coverage FAIL
                   = OPEN   otherwise
UTILITY(X, class)  = B4 with S = all in-range sizes carrying cells
ERROR(X, class)    = true if any required cell is in CALIBRATION_EXECUTION_ERROR for X
UNRESOLVED(X, class) = any required cell ESCALATE / CALIBRATION_INDETERMINATE for X

ELIGIBLE(X, class)              = COVERAGE PASS and UTILITY PASS and not ERROR and not UNRESOLVED
NOT_ELIGIBLE_DECISIVE(X, class) = COVERAGE FAIL or UTILITY FAIL          (regardless of other cells)
ERROR_STATE(X, class)           = ERROR and not NOT_ELIGIBLE_DECISIVE
UNRESOLVED_STATE(X, class)      = otherwise

SELECTED_CANDIDATE(class) = first X in (A, B, C) with ELIGIBLE(X, class)

CLASS_STATUS(class):
  CALIBRATION_CLASS_PASS                        if SELECTED_CANDIDATE(class) exists
  CALIBRATION_CLASS_EXECUTION_ERROR             else if some X is ERROR_STATE and no X before it in order is ELIGIBLE
  CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT else if every X is NOT_ELIGIBLE_DECISIVE
  CALIBRATION_CLASS_INDETERMINATE               otherwise (an UNRESOLVED_STATE candidate could still become the first eligible)

GLOBAL_STATUS over classes with REQUIRED_FOR_V3:
  ESTIMATOR_CALIBRATION_EXECUTION_ERROR          if any required class is CALIBRATION_CLASS_EXECUTION_ERROR
  ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT else if any required class is CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT
  CALIBRATION_INDETERMINATE                      else if any required class is CALIBRATION_CLASS_INDETERMINATE
  ESTIMATOR_CALIBRATION_PASS                     else (every required class PASS)
```

A class PASS is never erased by another class's failure: the per-class table always reports every class's status and, on PASS, its selected candidate. A candidate that is `ELIGIBLE` for a class but preceded in the order by another `ELIGIBLE` candidate is reported but not selected. Support of individual counts (C3) is reported per class and candidate independently of the class status; a class PASS with an `UNSUPPORTED_DECISIVE` count simply excludes that count from the supported set, because `COVERAGE(X, class)` requires every required cell to pass, a selected candidate has no unsupported-decisive count by construction, and an unsupported-unresolved count cannot occur for a selected candidate either.

## C7. PASS output per class (replaces B3)

On `ESTIMATOR_CALIBRATION_PASS` (and, with candidate states in place of the selection, on every other status) the result reports per required class:

| Field | Content |
|---|---|
| `SELECTED_CANDIDATE` | A, B or C for this class |
| `ESTIMATOR` | exact estimator of §1.2 / B2 with df |
| `UPPER_BOUND_FORMULA` | exact `U` for this class (`V̂·ν/χ²_{0.01,ν}` with the class's `ν`, or `V̂_A·c_env(class, n_i)` with the CAL table digest) |
| `CONFIDENCE_SEMANTICS` | coverage target `P(VAR_TRUE ≤ U) ≥ 0.99`, decided at `CONF_CLASS_CANDIDATE = 1199/1200` (family budget 0.01 over 4 classes × 3 candidates), `MISS_UNACCEPTABLE = 0.02` |
| `SUPPORTED_COUNT_SET` | the exact list of supported counts, and the declared range `[n_min, REALISTIC_MAX]` |
| `ALLOCATION_DOMAIN` | `TWO_SAMPLE: EQUAL_ARMS_ONLY`; other classes: single-sequence designs |
| `DEPENDENCE_DOMAIN` | the MUST structural levels under which coverage held, plus `STRUCTURAL_UNDERSTATEMENT_NOT_COVERABLE_AT_COMPILE_TIME` |
| `BOUND_KIND` | `ANALYTIC_EXACT` / `APPROXIMATE_EVAL_VALIDATED` / `CAL_FITTED_EVAL_VALIDATED` |
| `UTILITY_FRONTIER` | smallest supported count |
| `DOWNSTREAM_REVALIDATION` | CLUSTERED: variance-model validation must be redone on the cluster-level planning object; Run 1 S4 does not transfer; other classes: as identified |

## C8. Unchanged

Coverage rule form A1 (with the C2 thresholds), target variance objects A4, exactness language A5, Candidate C fitting A6, terminology A7, Run 1 relationship A8, exact Bartlett estimator and error rule B2, utility machine B4, the 621 cells, the 198 probes and all their seeds, Stage A/B sizes, reference class D.

## C9. Still not done

No executor, no CAL or EVAL simulation, no Run 1 outcome read, no execution authorization, no Official Run 2, no adoption, no PR, no merge.
