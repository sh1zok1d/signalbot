# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — effective calibration protocol V1 (pre-run amendment applied; not executed)

**Status:** `EFFECTIVE_PROTOCOL / EXECUTION_NOT_AUTHORIZED / NOT_RUN / NO_OUTCOME_READ`. Owner decision 2026-10-04 after the calibration freeze commit `4c5dcee` (accepted as audit artifact; execution not authorized).

**What this document is.** The frozen spec (`…_CALIBRATION_SPEC_V1.md`, sha256 `4524e043…`), grid (`…_CALIBRATION_GRID_V1.json`, sha256 `440fe897…`), builder (sha256 `8a924bf0…`) and freeze record V1 are **not edited**. This protocol is the spec **as amended** by `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_FREEZE_AMENDMENT_V1.json` (immutable). Where the two disagree, the amendment wins; everything the amendment does not touch stays as frozen in the spec. The amendment was written before any CAL or EVAL replicate exists and without reading Run 1 outcomes.

---

## A1. Coverage decision rule (replaces spec §6 "Coverage")

Constants: `MISS_TARGET = 0.01`, `MISS_UNACCEPTABLE = 0.02`. Miss `= 1{VAR_TRUE > U}`, `s` misses in `n` replicates. With the one-sided exact Clopper–Pearson bounds at confidence `CONF_CANDIDATE` (A2):

- `PASS` iff `cp_upper(s, n) ≤ MISS_TARGET`;
- `FAIL` iff `cp_lower(s, n) > MISS_UNACCEPTABLE`;
- otherwise `ESCALATE` (Stage A → Stage B); after Stage B an undecided check is `CALIBRATION_INDETERMINATE`.

The regions are disjoint by construction: `cp_lower ≤ s/n ≤ cp_upper`, so `cp_lower > 0.02` implies `cp_upper > 0.01`. No precedence rule is needed. Deterministic check at the frozen stage sizes (`CONF_CANDIDATE`): Stage A 4 000 → `PASS` iff `s ≤ 23`, `FAIL` iff `s ≥ 106`; Stage B 20 000 → `PASS` iff `s ≤ 162`, `FAIL` iff `s ≥ 456`; no `s` is in both.

## A2. Candidate-selection multiplicity (new)

Selectable candidates: A, B, C. D is reference-only and is never selected. Because A, B and C are judged on the same EVAL surface and the first eligible one is selected, the confidence level accounts for candidate selection with a deterministic Bonferroni allocation of a family error budget `ALPHA_FAMILY = 0.01`:

`ALPHA_CANDIDATE = 0.01 / 3 = 0.003333…`, `CONF_CANDIDATE = 1 − 0.01/3 = 0.996666…` (exact rational `299/300`).

Every candidate-decisive check (coverage and utility, A1 and A3) of A, B and C uses one-sided exact Clopper–Pearson bounds at `CONF_CANDIDATE`. Within a candidate, the cells form an intersection–union requirement (every MUST cell must pass), which needs no further adjustment. D is reported at the spec's `0.99` as a reference; it never enters selection. No alpha is changed after a result is read.

## A3. Candidate eligibility and selection (replaces spec §3 "preference order" and §7.1–7.4)

Utility check per cell and candidate, `UTIL = 1{ρ ≤ 1.5}`, `u` successes in `n`: `PASS` iff `cp_lower(u, n) ≥ 0.80`; `FAIL` iff `cp_upper(u, n) < 0.80`; else `ESCALATE` → Stage B → `CALIBRATION_INDETERMINATE`. Bounds at `CONF_CANDIDATE`.

For a candidate X ∈ {A, B, C}:

- `COVERAGE(X) = PASS` iff every MUST cell is `PASS`; `FAIL` iff any MUST cell is `FAIL`; else `INDETERMINATE`.
- `UTILITY(X)`: for each MUST design class, its **utility frontier** is the smallest grid `n ≤ REALISTIC_MAX(class)` at which every MUST cell at that `n` is utility `PASS`. `UTILITY(X) = PASS` iff every class has a frontier. `UTILITY(X) = FAIL` iff for some class every grid `n ≤ REALISTIC_MAX(class)` has at least one MUST cell that is utility `FAIL` (no `n` can qualify whatever Stage B does). Otherwise `INDETERMINATE`.
- `X` is **`ELIGIBLE`** iff `COVERAGE(X) = PASS` and `UTILITY(X) = PASS` and no cell of `X` is in an execution-error or `CALIBRATION_INDETERMINATE` state.
- `X` is **`NOT_ELIGIBLE_DECISIVE`** iff `COVERAGE(X) = FAIL` or `UTILITY(X) = FAIL`.
- otherwise `X` is **`UNRESOLVED`**.

Selection order A → B → C; the selected candidate is the first `ELIGIBLE` one. If A passes coverage but fails utility, B is examined; if B is not eligible, C. If no candidate is `ELIGIBLE`:

- all three `NOT_ELIGIBLE_DECISIVE` → `ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT` (sub-reasons recorded per candidate: `COVERAGE` / `UTILITY`);
- at least one `UNRESOLVED` candidate that could become the first eligible one (no `ELIGIBLE` candidate precedes it in the order) → `CALIBRATION_INDETERMINATE`.

A candidate later in the order than an `ELIGIBLE` one is reported but never selected.

## A4. Target variance objects (new field `TARGET_VARIANCE_OBJECT`)

| Class | `TARGET_VARIANCE_OBJECT` | Independent unit | Planner's SE² at planned count `N_plan` |
|---|---|---|---|
| `TWO_SAMPLE` | variance of **one observation within an arm** (long-run, including within-arm serial dependence) | observation | `σ²·(1/n_a + 1/n_i)` |
| `PAIRED_UNITS` | variance of the **paired difference** of one unit (long-run across units) | unit | `σ²_d / N` |
| `CLUSTERED` | variance of the **independent cluster-level mean/statistic** (long-run across ordered clusters), **not** the marginal per-hour (per-observation) variance | cluster (date) | `σ²_cluster / G` |
| `RARE_EVENT` | variance of the **venue-averaged event statistic** (long-run across ordered events) | event | `σ²_event / n_e` |
| `ERA_STRATIFIED` | undefined (S6 excluded) | — | — |

**Consequence for Run 1 (recorded, not a change of Run 1).** Official Run 1 validated the floor for S4 on a **different statistical object**: a per-hour (per-observation) variance with a separate `DEFF = 1 + (m − 1)·ICC` term in the oracle and the compiler. A future compiler planning `CLUSTERED` designs on the cluster-level variance bound of this unit uses a different planning object, so the Run 1 S4 result **does not transfer automatically** to it. If a clustered candidate is accepted here, the downstream variance-model validation for `CLUSTERED` must be separate or revalidated under the cluster-level planning object. Run 1 S4 rows are not converted post hoc, and no ICC is estimated for the sake of keeping the old formula.

## A5. Exactness language (replaces the wording of spec §1.2 and §3)

Candidate A is an **exact** chi-square bound only in cells where its assumptions hold: independent Gaussian units with equal variance (F1/F2 with `φ = 0`, `GAUSS`; F3 `EQUAL` sizes, `φ_G = 0`, `GAUSS`; F4 `HOMO`, `φ_e = 0`, `GAUSS`). In every other MUST or STRESS cell A is a **candidate formula** whose coverage is checked empirically, and the word "exact" is not extended to it. Candidate B's effective-df chi-square construction is **explicitly approximate** everywhere; its right to be used comes only from independent EVAL coverage, never from its analytic name.

## A6. Candidate C fully defined before execution (replaces spec §3 row C and §5 "Splits" for C)

**Fitting (CAL split only).** For each class and each frozen CAL size `n_i` of that class (F1 per-arm `{30, 60, 120, 250, 500}`; F2 `{40, 60, 100, 160, 260, 400}`; F3 `{8, 15, 25, 40}`; F4 `{30, 50, 75, 100}`): pool the replicate-level ratios `R = VAR_TRUE / V̂_A` of **all MUST cells** of that class at `n_i` (all dependence, tail, ICC, size and scale levels; `4 000` CAL replicates per cell). `c_raw(class, n_i)` is the order statistic of rank `⌈0.99·M⌉` of the `M` pooled ratios (the "higher" quantile, never interpolated). STRESS and OUT_OF_DOMAIN cells are excluded from the pool.

**Envelope (deterministic, non-increasing in `n`).** `c_env(class, n_i) = max_{j ≥ i} c_raw(class, n_j)` (suffix maximum over the ordered sizes). This is the only transformation; no smoothing, no monotonicity repair other than the suffix maximum, no interpolation, no class regrouping.

**Application to arbitrary `n` (frozen now; binds the future compiler as well as the EVAL evaluation).**
- `n < n_min(class)` → `U_C` is `NOT_APPLICABLE`; a compiler must return `NOT_FEASIBLE_INFORMATION_INSUFFICIENT` for that design;
- `n_min ≤ n ≤ n_max` → `U_C = V̂_A · c_env(class, n⁻)` with `n⁻` the **largest calibrated size ≤ n** (nearest lower; identical to `c_env(class, n)` on the grid);
- `n > n_max(class)` → `U_C = V̂_A · c_env(class, n_max)` (the factor of the largest calibrated size, held constant; conservative under the non-increasing envelope). This is the pre-declared extrapolation rule; no other extrapolation exists.

**Locks.** After the first EVAL replicate is read, the quantile (0.99, rank `⌈0.99·M⌉`), the pooling rule, the class grouping, the envelope, the nearest-lower rule, the extrapolation rule and the candidate grid are immutable. The EVAL split is never used for fitting or tuning C. The CAL table (`c_raw`, `c_env` per class and size) is written with its digest **before** any EVAL replicate is drawn and bound in the run record.

## A7. Information and outcome terminology (replaces "nothing from outcomes" in spec §1.2 / §5)

- The compile-time information set `I` is characterized as **`NO_EVALUATION_WINDOW_OUTCOMES_AVAILABLE`**: a future real estimator may read only the declared exposed, PIT-legal surface and its counts and statistics; evaluation and holdout outcomes are not available to it. Every such read is an exposure-ledger row under contract V2 draft §7 (surface, unit, purpose `variance source`, date, digest), and a surface may serve as a variance source only when already exposed for that family.
- The present synthetic calibration is **`NO_MARKET_OUTCOMES_USED`**: truths are known by construction; no market data of any window is read.
- The two labels are distinct and both are required in the run record.

## A8. Relationship to Official Run 1 (recorded; Run 1 is not invalidated or rewritten)

Run 1 validates floor behaviour **conditional on a controlled** `q = VAR_EXPOSED_ESTIMATE / VAR_TRUE`. It does **not** validate a real exposed estimator, because no such estimator existed in GV0R02 V0–V2. Estimator calibration is a separate prerequisite on the operational compiler path. A PASS of this calibration unit adopts nothing by itself.

## A9. Unchanged by the amendment

Estimator definitions (§1.2–1.3 except the exactness wording), the calibration question, the families F1–F5 and their MUST/STRESS/OUT_OF_DOMAIN labels, the 621 cells and their seed ranges (no renumbering; `GRID_DELTA = NONE`), the Stage A/B sizes, `REALISTIC_MAX`, the 1.5× utility event, the `UTILITY_OK` bound 0.80, the reference class D, the independence statement, and the limitation label `STRUCTURAL_UNDERSTATEMENT_NOT_COVERABLE_AT_COMPILE_TIME`.

## A10. Still not done

No executor, no CAL or EVAL simulation, no Run 1 outcome read for this amendment, no Official Run 2, no V2 adoption, no PR, no merge. Execution needs a separate owner authorization, an executor whose digest is bound before the run, and a run authorization artifact.
