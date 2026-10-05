# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — effective calibration protocol V4 (amendments V1–V4 applied; not executed)

**Status:** `EFFECTIVE_PROTOCOL / EXECUTION_NOT_AUTHORIZED / NOT_RUN / NO_OUTCOME_READ`. Owner decision 2026-10-04 after executor commit `9ad1803` (accepted as implementation candidate; official run not authorized). No new CAL or EVAL cells.

**What this document is.** Protocols V1–V3 and amendments V1–V3 stay immutable, as do the original freeze, the 621-cell grid, the 198-cell probe grid and the 4 716-cell dense grid. This V4 restates the protocol as amended by `…_FREEZE_AMENDMENT_V4.json` (immutable). Everything not repeated here is unchanged from V3. Written before any CAL or EVAL replicate exists; Run 1 outcomes not read.

---

## D1. Candidate preference state machine (replaces V3 C6 `SELECTED_CANDIDATE` / `CLASS_STATUS`)

A → B → C is a **preference order**, not a sort of eligible candidates. A lower-priority candidate is considered only when **every** higher-priority candidate is `NOT_ELIGIBLE_DECISIVE`. Candidate states are unchanged (`ELIGIBLE`, `NOT_ELIGIBLE_DECISIVE`, `ERROR_STATE`, `UNRESOLVED_STATE`; C6 definitions). Exact class machine:

```
for X in (A, B, C):
    ELIGIBLE               -> CLASS_STATUS = CALIBRATION_CLASS_PASS, SELECTED_CANDIDATE = X; stop
    ERROR_STATE            -> CLASS_STATUS = CALIBRATION_CLASS_EXECUTION_ERROR, no selection; stop
    UNRESOLVED_STATE       -> CLASS_STATUS = CALIBRATION_CLASS_INDETERMINATE, no selection; stop
    NOT_ELIGIBLE_DECISIVE  -> consider the next candidate
all three NOT_ELIGIBLE_DECISIVE -> CLASS_STATUS = CALIBRATION_CLASS_FAIL_INFORMATION_INSUFFICIENT
```

A lower candidate never bypasses an unresolved or error higher-priority candidate. Global precedence (V3 C6) is unchanged: EXECUTION_ERROR > FAIL_INFORMATION_INSUFFICIENT > INDETERMINATE > PASS over the required classes; a class PASS is preserved in the per-class table whatever the other classes do. Reference implementation: `amendment_v4.class_decision` / `class_state`.

## D2. CLUSTERED truth with heterogeneous cluster sizes (replaces the F3 HETERO truth rule of the grid)

For a CLUSTERED cell with realized sizes `m_1..m_G` and cross-cluster AR parameter `φ`:

```
v_g = ICC + (1 − ICC) / m_g
X_g = sqrt(v_g) · Z_g,          Cov(Z_g, Z_h) = φ^|g−h|   (Z stationary unit-variance AR(1))
VAR_TRUE = G · Var( mean_g X_g | m_1..m_G ) = (1/G) · Σ_g Σ_h sqrt(v_g v_h) · φ^|g−h|
```

This exact conditional finite-G variance is the **single authoritative truth** of every CLUSTERED replicate (EQUAL sizes included: there it equals `v · ar_factor(G, φ)`, and with `φ = 0` it equals `ICC + (1−ICC)/m`). The executor no longer carries a frozen-formula value or a `TRUTH_MATCHES_FROZEN` flag; every active replicate has one truth `T`.

**Documented conflict with an immutable artifact.** The frozen grid V1 (and the probe and dense grids built from it) record for F3 HETERO cells `PER_REPLICATE = true` with the formula string `(1/G) · Σ_g σ²(ICC + (1−ICC)/m_g) × ar_factor(G, φ_G)`. For `φ_G > 0` and unequal sizes no process has exactly that variance; the string was written for the equal-size case. Amendment V4 supersedes that string for the realized truth of F3 HETERO cells with the exact formula above. The grid files are not edited; the cells, levels and seeds are unchanged. Affected: HETERO × `φ_G ∈ {0.3, 0.6}` cells. For `φ_G = 0` or EQUAL sizes the two rules coincide.

## D3. Stage A decisions locked per check (binds the sequential rule)

The sequential rule is per `(CELL_ID, CANDIDATE, METRIC)`, `METRIC ∈ {COVERAGE, UTILITY}`. At Stage A (4 000) a `PASS` or `FAIL` is **final**; only `ESCALATE` proceeds to Stage B. If any selectable candidate/metric of a cell escalates, the Stage-B replicates (seeds 4 000–19 999 of the cell's range) are generated **once** and shared, but they decide only the checks whose own Stage-A state was `ESCALATE`, using the pooled 20 000 rows; a residual `ESCALATE` after Stage B is `CALIBRATION_INDETERMINATE`. A Stage-A decisive decision is never revised by Stage-B data generated for another check. Each check records `STAGE_A`, `STAGE_B` (null if not consumed), `FINAL`, `DECIDED_AT`. Reference: `engine.decide_cell`.

## D4. TWO_SAMPLE Candidate-B effective df (replaces the `NU_B` metadata of the grids and amendment V2's `NU_B_TWO_SAMPLE`)

`TWO_SAMPLE_ALLOCATION_DOMAIN = EQUAL_ARMS_ONLY` (unequal arms are a `CalibrationExecutionError`). For arm size `n`:

```
L = ceil(n^(1/3));   nu_arm = floor(n / (L + 1)) − 1;   nu_B = 2 · nu_arm
V_LR = ((n−1)·Ω_a + (n−1)·Ω_b) / (2n − 2)            (per-arm Bartlett with bandwidth L(n), divisor n)
U_B  = V_LR · nu_B / chi2_ppf(0.01, nu_B)
```

No total-sample bandwidth `L(2n)` enters the df while the estimator uses per-arm bandwidths. The grids' `NU_B` field for TWO_SAMPLE cells (computed with `L(2n)`) is metadata that the executor does not read; it is superseded, not edited. PAIRED_UNITS / CLUSTERED / RARE_EVENT keep `nu_B = floor(n/(L+1)) − 1`. Candidate B remains explicitly approximate.

## D5. RARE_EVENT truth identity (verified, no redesign)

Generated process: `x_1 = m_1 e_1`, `x_t = φ x_{t−1} + sqrt(1−φ²) m_t e_t`, `s = sqrt(c) x`, `c = (1 + 2v)/3`, `m_t = exp(0.5 Z_t)` (HETERO) or 1, `e_t` unit-variance innovations, all independent. Then `Var(x_1) = E[m²]`, `Var(x_t) = φ² Var(x_{t−1}) + (1−φ²) E[m²] = E[m²]` (stationary) and `Cov(x_t, x_{t−h}) = φ^h E[m²]`, so

`VAR_TRUE = n · Var(mean s) = c · E[m²] · ar_factor(n, φ)`, `E[m²] = e^{0.5}` for HETERO,

exactly the frozen formula. The validator recomputes it by the explicit linear map `x = A w`, `Cov(x) = A · E[m²] I · Aᵀ`, for `n ∈ {30, 61, 100}`, `φ ∈ {0, 0.3, 0.6}`, `v ∈ {0.5, 0.9}`, HOMO/HETERO, to 1e-9. No mismatch; no blocker.

## D6. Slim canonical checkpoint (binds the official checkpoint schema)

`replicates.jsonl`, append-only, canonical JSON lines (`sort_keys`, compact separators, `allow_nan = false`). First line: `{"HEADER": {EXECUTOR_DIGEST, INPUT_DIGESTS, SCHEMA: "SLIM_V4"}}`; a header mismatch on resume is `EXECUTION_INTEGRITY_ERROR`. Rows:

| Phase | Keys | Meaning |
|---|---|---|
| CAL | `P, C, S, VA, T, E` | phase, CELL_ID, seed, Candidate-A estimate, authoritative truth, error or null |
| EVAL | `P, C, S, VA, VB, T, E` | plus the Bartlett long-run estimate |

Everything else (`ν_A`, `ν_B`, `U_A`, `U_B`, `U_C = VA · c_env`, `U_D`, misses, utility flags, Stage decisions) is recomputed deterministically from the row, the cell and the sealed C-table. No raw sample vectors are stored. Idempotence by `(P, C, S)`; a non-identical duplicate is `EXECUTION_INTEGRITY_ERROR`. Expected size at the frozen scale (frozen CELL_IDs average 57 characters): CAL ≈ 137 B/row → 1.03 M rows ≈ 0.14 GB; EVAL Stage A ≈ 162 B/row → 22.14 M rows ≈ 3.6 GB; full Stage B on every cell (worst case) would add ≈ 14.4 GB.

## D7. Unchanged

Everything else in V3: per-class selection and the 1199/1200 confidence with its thresholds (C2), the EVAL support surface and count support rule (C3/C4), equal-arms domain (C5), the per-class PASS output fields (C7), the 621 + 198 + 4 716 cells and their seeds, Stage sizes, reference class D, Candidate C fitting (A6) and the exact Bartlett estimator (B2).

## D8. Still not done

No frozen CAL or EVAL replicate executed; no C-table from frozen cells; no result artifact; no run authorization; no Run 1 outcome read; no adoption; no PR, no merge.
