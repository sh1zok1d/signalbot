# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — effective calibration protocol V2 (amendments V1 + V2 applied; not executed)

**Status:** `EFFECTIVE_PROTOCOL / EXECUTION_NOT_AUTHORIZED / NOT_RUN / NO_OUTCOME_READ`. Owner decision 2026-10-04 after amendment commit `f96217e` (accepted; CP thresholds and candidate-adjusted confidence accepted; one last repair ordered).

**What this document is.** Protocol V1 (sha256 `b3cb784c…`) stays immutable. This V2 restates the protocol as amended by `…_FREEZE_AMENDMENT_V2.json` (immutable) on top of amendment V1 (sha256 `ee319868…`). Everything not repeated here is unchanged from protocol V1 and the frozen spec. Written before any CAL or EVAL replicate exists; Run 1 outcomes not read.

---

## B1. Candidate C: fitted table versus supported application domain (replaces A6 "Application")

Two objects are kept apart:

- **`FITTED_TABLE`** — `c_raw` and `c_env` per class at the frozen calibrated sizes, fitted on CAL only, exactly as in A6 (rank-`⌈0.99·M⌉` pooled quantile, suffix-max envelope). Fitting is unchanged.
- **`SUPPORTED_APPLICATION_DOMAIN`** — the set of counts `n` at which a bound may be applied. It is **empirical**, never inferred from the envelope's monotonicity alone.

**Decision: option B.** The real compiler plans at arbitrary counts (the R03 planning counts are 41–260 units, replication 36–156), so interior probe cells are added **before** the executor exists: `…_CALIBRATION_GRID_PROBES_V1.json` (198 cells, sha256 in amendment V2), built by `build_probe_cells.py` from the frozen grid without editing it. For each class and each interval `(n_i, n_{i+1})` between consecutive calibrated sizes, one probe size `p_i = round(√(n_i·n_{i+1}))` at **every MUST structural level** of the class:

| Class | Calibrated sizes | Probe sizes |
|---|---|---|
| TWO_SAMPLE (per arm) | 30, 60, 120, 250, 500 | 42, 85, 173, 354 |
| PAIRED_UNITS | 40, 60, 100, 160, 260, 400 | 49, 77, 126, 204, 322 |
| CLUSTERED (G) | 8, 15, 25, 40 | 11, 19, 32 |
| RARE_EVENT (events) | 30, 50, 75, 100 | 39, 61, 87 |

Probe cells are **EVAL-only** (seed family indices 11–14, ranges verified pairwise disjoint, disjoint from all 621 CAL/EVAL ranges and from Run 1). They never enter the CAL pool. At a probe, candidate C applies the **nearest-lower** factor `c_env(class, n_i)`; candidates A and B apply their formulas at `p_i`; D its constant. Coverage and utility at a probe are decided by the same rules and at the same `CONF_CANDIDATE = 299/300` as calibrated cells, and probe cells are **decisive** (they count as MUST cells of their class for `COVERAGE(X)` and for the utility frontier).

**Application rule (final, binds the future compiler).** For candidate X and class with calibrated sizes `n_1 < … < n_K`:

- `n < n_1` → `NOT_FEASIBLE_INFORMATION_INSUFFICIENT`;
- `n > n_K` → `NOT_FEASIBLE_INFORMATION_INSUFFICIENT` (the constant extrapolation of A6 is **withdrawn**);
- `n = n_i` → supported iff the calibrated EVAL cells at `n_i` pass for X;
- `n_i < n < n_{i+1}` → supported iff **both** the calibrated EVAL cells at `n_i` **and** the probe cells at `p_i` pass for X; then C uses `c_env(class, n_i)`, A/B use their formula at `n`.

The support argument for an interval is recorded as what it is: a two-point empirical verification (`n_i` and `p_i`) under the frozen structural levels, plus the monotone-in-`n` behaviour of sampling understatement at a fixed factor. It is not a proof for every `n` in the interval, and it is labelled `INTERVAL_SUPPORT_TWO_POINT`. The `SUPPORTED_APPLICATION_DOMAIN` of each class is written into the result as an explicit list of supported sizes and supported intervals. No probe may be added after the first CAL or EVAL replicate is read.

## B2. TWO_SAMPLE Bartlett long-run estimator (exact; replaces spec §1.3 for this class and removes its 0.25 floor)

For arm `h ∈ {a, b}` with observations `x_{h,1..n_h}` in time order and mean `x̄_h`:

```
L_h       = ceil( n_h ** (1/3) )
gamma_h(l) = (1 / n_h) * sum_{t = l+1 .. n_h} ( x_{h,t} - x̄_h ) * ( x_{h,t-l} - x̄_h )      for l = 0 .. L_h
Omega_h   = gamma_h(0) + 2 * sum_{l = 1 .. L_h} [ 1 - l / (L_h + 1) ] * gamma_h(l)
V̂_LR     = ( (n_a - 1) * Omega_a + (n_b - 1) * Omega_b ) / ( n_a + n_b - 2 )
```

Bound semantics: `V̂_LR` estimates the **common per-observation long-run variance** used by TWO_SAMPLE planning (`SE²_plan = V̂_LR · (1/n_a + 1/n_b)`). The autocovariance divisor is `n_h` (never `n_h − l`); the kernel is Bartlett only; the bandwidth rule is `ceil(n_h^(1/3))` only; no clipping or truncation of `Omega_h` or `V̂_LR`. **Numerical-error rule (frozen now):** if any `Omega_h` or `V̂_LR` is not finite or is `≤ 0`, the replicate is recorded as `CALIBRATION_EXECUTION_ERROR`, the cell enters the error state (which blocks eligibility of every candidate, A3), and nothing is repaired or substituted. The same error rule and the same removal of the 0.25 floor apply to the Bartlett estimator of PAIRED_UNITS, CLUSTERED (over ordered cluster means) and RARE_EVENT (over ordered event statistics), each with its single ordered sequence of length `n` and `L = ceil(n^(1/3))`. Candidate B uses `V̂_LR` with `ν_B = ⌊(n_a + n_b)/(L_pool + 1)⌋ − 1`, `L_pool = ceil((n_a + n_b)^(1/3))` for TWO_SAMPLE, as recorded in the grid's `NU_B`.

**Allocation.** The frozen F1 grid and the F1P probes contain **equal arms only** (`n_a = n_b = n`). The pooled formula is algebraically valid for unequal arms, but it has no empirical support here. **Equal allocation is frozen as a domain requirement:** the TWO_SAMPLE `SUPPORTED_APPLICATION_DOMAIN` contains only `n_a = n_b`; any other allocation returns `NOT_FEASIBLE_INFORMATION_INSUFFICIENT` until a separate, outcome-blind, pre-run probe amendment adds unequal-arm cells. This is recorded as an open owner item (a real binary mechanism contrast usually has unequal arms).

## B3. PASS output semantics (supersedes spec §7.6 and A3's "selected candidate" wording)

A result with status `ESTIMATOR_CALIBRATION_PASS` reports **per design class** (TWO_SAMPLE, PAIRED_UNITS, CLUSTERED, RARE_EVENT) a record with exactly these fields:

| Field | Content |
|---|---|
| `SELECTED_CANDIDATE` | `A`, `B` or `C` — the first eligible candidate (eligibility is still decided over all MUST classes jointly, A3; the record repeats it per class) |
| `ESTIMATOR` | the exact estimator formula of §1.2 / B2 for the class (`V̂_A` or `V̂_LR`), with df |
| `UPPER_BOUND_FORMULA` | the exact `U` of the candidate for the class (`V̂·ν/χ²_{0.01,ν}` with the class's `ν`, or `V̂_A·c_env(class, n⁻)` with the fitted table and its digest) |
| `CONFIDENCE_SEMANTICS` | coverage target `P(VAR_TRUE ≤ U) ≥ 0.99`, decided at `CONF_CANDIDATE = 299/300` (family budget 0.01 over three selectable candidates), miss tolerance `MISS_UNACCEPTABLE = 0.02` |
| `SUPPORTED_APPLICATION_DOMAIN` | explicit supported sizes and intervals (B1), allocation requirement (B2), `NOT_FEASIBLE_INFORMATION_INSUFFICIENT` outside |
| `DEPENDENCE_ASSUMPTIONS` | the structural levels under which coverage held (serial dependence up to the MUST level, ICC range, size/scale heterogeneity, venue correlation, tails), and the label `STRUCTURAL_UNDERSTATEMENT_NOT_COVERABLE_AT_COMPILE_TIME` for between-window variance change |
| `BOUND_KIND` | `ANALYTIC_EXACT` (only in the cells of A5 where A is exact), `APPROXIMATE_EVAL_VALIDATED` (A elsewhere, B everywhere) or `CAL_FITTED_EVAL_VALIDATED` (C) |
| `UTILITY_FRONTIER` | the smallest supported size at which every MUST and probe cell of the class is utility `PASS`, and `REALISTIC_MAX` |
| `DOWNSTREAM_REVALIDATION` | for CLUSTERED always "variance-model validation must be redone on the cluster-level planning object; Run 1 S4 does not transfer"; for other classes any item the result identifies |

A single "selected class" line without these fields is not a valid PASS output. `FAIL` and `INDETERMINATE` results carry the same per-class table with the candidate states of A3 in place of the selection.

## B4. Utility state machine (literal; replaces A3 "UTILITY(X)")

For candidate X and design class with in-range sizes `S = {s ∈ grid sizes ∪ probe sizes : s ≤ REALISTIC_MAX(class)}`, and for each `s ∈ S` the set `C_s` of required MUST cells (calibrated MUST cells at `s`, or probe cells at `s`):

```
size_state(s)   = PASS   if every cell in C_s is utility PASS
                = FAIL   if at least one cell in C_s is utility FAIL
                = OPEN   otherwise (no FAIL, at least one ESCALATE / CALIBRATION_INDETERMINATE)
frontier(class) = min { s in S : size_state(s) = PASS }      (undefined if none)
UTILITY(X, class) = PASS           if frontier(class) is defined
                  = FAIL           if size_state(s) = FAIL for every s in S
                  = INDETERMINATE  otherwise
UTILITY(X)      = PASS           if UTILITY(X, class) = PASS for every MUST class
                = FAIL           if UTILITY(X, class) = FAIL for any MUST class
                = INDETERMINATE  otherwise
```

Notes the executor may not override: a size with a mixture of PASS and OPEN cells is `OPEN`, never `PASS`; a single `FAIL` cell makes its size `FAIL` whatever the other cells show; `UTILITY(X, class) = FAIL` requires **every** in-range size to be decisively ruled out; a class with some `FAIL` sizes and some `OPEN` sizes and no `PASS` size is `INDETERMINATE` after Stage B, and the unit then ends `CALIBRATION_INDETERMINATE` (A3) unless an earlier candidate in the order is `ELIGIBLE`. Sizes above `REALISTIC_MAX` never enter `S`, even if supported. The frontier, once defined, is the smallest `PASS` size; `OPEN` sizes below it do not undefine it.

## B5. Unchanged

Coverage rule A1, confidence A2, eligibility and selection A3 (with B4 as its utility sub-machine), target variance objects A4, exactness language A5, Candidate C fitting A6 (fitting part), terminology A7, Run 1 relationship A8, the 621 cells and their seeds (`GRID_DELTA = NONE`), Stage A/B sizes, `REALISTIC_MAX`, the 1.5× event and the 0.80 utility bound, reference class D.

## B6. Still not done

No executor, no CAL or EVAL simulation, no Run 1 outcome read, no execution authorization, no Official Run 2, no adoption, no PR, no merge.
