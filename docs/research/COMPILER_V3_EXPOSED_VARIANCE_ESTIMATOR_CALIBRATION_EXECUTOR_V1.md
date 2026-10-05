# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — executor V1 (implementation record; execution not authorized)

**Status:** `IMPLEMENTED / EXECUTION_NOT_AUTHORIZED / NO_FROZEN_REPLICATE_EXECUTED / NO_C_TABLE_FROM_FROZEN_CELLS / NO_RESULT_ARTIFACT`. Owner authorization 2026-10-04: implementation only. The authoritative design is amendment V3 (`b654d3a`) with effective protocol V3; nothing frozen was edited.

Package: `scripts/research/compiler_v3_estimator_calibration/` — `generators.py`, `estimators.py`, `cells.py`, `ctable.py`, `checkpoint.py`, `engine.py`, `aggregate.py`, `run.py` (plus the earlier builders and validators). Tests: `tests/research/test_compiler_v3_estimator_calibration_executor.py` (DEV fixtures only). Digests: `python -m scripts.research.compiler_v3_estimator_calibration.run --digests`.

## 1. State machine: CAL → seal → EVAL

```
PHASE CAL   (engine.run_cal; cells.cal_cells() = the 258 MUST cells of the 621 grid)
  for each CAL cell, each seed in SEED_RANGE.CAL (4000):     skip if checkpointed
      sample = generators.generate(cell, seed)               (ONE sample per (cell, seed))
      row    = {V_A, NU_A, VAR_TRUE_USED, VAR_TRUE_FROZEN_FORMULA, TRUTH_MATCHES_FROZEN, ERROR}
  table = ctable.build_c_table(CAL rows)                     c_raw = order statistic rank ceil(0.99 M) of VAR_TRUE/V_A
                                                             pooled over all MUST cells of (class, n); c_env = suffix max
  (official) assert table sizes == frozen calibrated sizes
SEAL        ctable.seal_c_table -> COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_C_TABLE_V1.json
            (refuses to overwrite; records class, n, M, rank, c_raw, c_env, CAL cell ids, CAL seed ranges,
             input digests, executor digest) ; CAL_COMPLETION_RECORD.json binds its SHA-256
PHASE EVAL  (engine.run_eval) gate = CAL_COMPLETION_RECORD.STATUS == COMPLETE
                                     and sealed C-table exists and its SHA-256 == record
                                     and (official) record.INPUT_DIGESTS == frozen digests == amendment V3 digests
                                     and (official) executor digest unchanged since CAL
  for each EVAL cell (621 + 198 + 4716):
      c_factor = c_env(class, largest calibrated n_i <= n)   (None below n_min)
      Stage A: seeds [lo, lo+4000)             -> rows with V_A, V_B, U_A, U_B, U_C, U_D, MISS_x, UTIL_x
      decisions per candidate (A/B/C at 1199/1200; D at 0.99)
      if any A/B/C check ESCALATE: Stage B seeds [lo+4000, lo+20000), pooled decision; residual ESCALATE -> CALIBRATION_INDETERMINATE
AGGREGATE   (aggregate.aggregate) per class: required cells = calibrated MUST in range + probes in range + dense
            -> amendment_v3.class_state (C6) -> SELECTED_CANDIDATE(class) = first ELIGIBLE of A, B, C
            -> global_status (C6 precedence) -> C7 per-class PASS output
```

The EVAL path has no writer for the C-table: `ctable.py` contains exactly one `write_text` (inside `seal_c_table`), and `run_eval`, `eval_gate`, `eval_replicate`, `_decide` call neither `seal_c_table` nor `build_c_table` nor any file write (AST test).

## 2. Exact formulas per class

Sample variance uses `ddof = 1`. `L(n) = ceil(n^(1/3))`; `gamma(l) = (1/n) Σ_{t=l+1..n} (x_t − x̄)(x_{t−l} − x̄)`; `Ω = gamma(0) + 2 Σ_{l=1..L} [1 − l/(L+1)] gamma(l)`.

| Class | A (`V_A`, `ν_A`) | B (`V_LR`, `ν_B`) | C |
|---|---|---|---|
| TWO_SAMPLE (equal arms `n`) | `((n−1)s²_a + (n−1)s²_b)/(2n−2)`, `ν_A = 2n−2` | `((n−1)Ω_a + (n−1)Ω_b)/(2n−2)`, `ν_B = ⌊2n/(L(2n)+1)⌋ − 1` | `V_A · c_env(TWO_SAMPLE, n_i)` |
| PAIRED_UNITS | `s²` of the `N` unit differences, `ν_A = N−1` | `Ω` of the ordered differences, `ν_B = ⌊N/(L(N)+1)⌋ − 1` | `V_A · c_env(PAIRED_UNITS, n_i)` |
| CLUSTERED | `s²` of the `G` cluster-level means, `ν_A = G−1` | `Ω` of the ordered cluster means, `ν_B = ⌊G/(L(G)+1)⌋ − 1` | `V_A · c_env(CLUSTERED, n_i)` |
| RARE_EVENT | `s²` of the `n_e` venue-averaged event statistics, `ν_A = n_e−1` | `Ω` of the ordered event statistics, `ν_B = ⌊n_e/(L(n_e)+1)⌋ − 1` | `V_A · c_env(RARE_EVENT, n_i)` |

Bounds: `U_A = V_A·ν_A/χ²_{0.01,ν_A}`, `U_B = V_LR·ν_B/χ²_{0.01,ν_B}`, `U_C = V_A·c_env`, `U_D = 4`. Any non-finite or non-positive `Ω`, `V`, `U` raises `CalibrationExecutionError`; the replicate is recorded with `ERROR` and nothing is repaired. No clipping, no floor, no alternate kernel, bandwidth or divisor. ERA_STRATIFIED: `KeyError` (unsupported).

Miss `= VAR_TRUE_USED > U_x`; utility `= U_x / VAR_TRUE_USED ≤ 1.5`.

## 3. Structural level → synthetic process

RNG: `root = SeedSequence(seed); data_ss, reserved_ss = root.spawn(2); DATA = default_rng(data_ss)`; child 1 unused. Innovations: `GAUSS` standard normal; `T4`/`T3` Student t scaled to unit variance. `ar1_unit(n, φ)`: `x_1 = e_1`, `x_t = φ x_{t−1} + √(1−φ²) e_t` (marginal variance 1, stationary start). `ar_factor(n, φ) = 1 + 2 Σ_{h=1}^{n−1} (1 − h/n) φ^h`.

| Family | Process | `VAR_TRUE_USED` |
|---|---|---|
| F1 TWO_SAMPLE | two independent arms, each `ar1_unit(n, φ)` with the cell's tail | `ar_factor(n, φ)` per observation (equals the frozen formula) |
| F2 PAIRED_UNITS | `ar1_unit(N, φ)` | `ar_factor(N, φ)` |
| F3 CLUSTERED | `m_g = 24` (EQUAL) or `Uniform{12..36}` per replicate (HETERO); `v_g = ICC + (1−ICC)/m_g`; `s_g = √v_g · z_g`, `z = ar1_unit(G, φ_G)` | EQUAL or `φ_G = 0`: `mean(v_g)·ar_factor(G, φ_G)` (frozen formula). HETERO with `φ_G > 0`: the exact process variance `(1/G) Σ_g Σ_h √(v_g v_h) φ^{|g−h|}` (see interpretation I-1) |
| F4 RARE_EVENT | `c = (1+2v)/3`; HETERO: per-event innovation multiplier `m_g = exp(0.5 Z_g)`; `s = √c · ar1_unit(n_e, φ_e, scale = m)` | `c · E[m²] · ar_factor(n_e, φ_e)` with `E[m²] = e^{0.5}` (exact for this process; equals the frozen formula) |
| F5 OUT_OF_DOMAIN | the base family's process at variance 1 | `λ ×` the base truth |

Every row carries `VAR_TRUE_USED`, `VAR_TRUE_FROZEN_FORMULA` and `TRUTH_MATCHES_FROZEN`. No Run 1 artifact and no market data is read by any generator.

## 4. Checkpoint / resume

`replicates.jsonl` is append-only, keyed by `(PHASE, CELL_ID, SEED)`, rows in canonical JSON (`sort_keys`, compact separators, `allow_nan = False`). A recorded replicate is never executed again. A duplicate record that is not bit-identical raises `ExecutionIntegrityError` (`EXECUTION_INTEGRITY_ERROR`), on write and on load. Resume executes only the missing frozen seeds; no new seed can be introduced because seeds come from the frozen cell ranges only. Execution order is free; `rows()` returns the canonical order phase → class → CELL_ID → SEED, and the C-table and results are order-independent (tested).

## 5. Guards

`--official` requires `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_RUN_AUTHORIZATION_V1.json`, which does not exist: refused. Without `--official`, any cell whose `CELL_ID` is in the frozen sets, any `CELL_ID` not prefixed `DEV-`, and any seed `≥ 10⁹` is refused. DEV fixtures use sizes that are not frozen sizes and seeds `< 10⁹`.

## 6. Expected compute (not run on frozen cells; timed on DEV cells of the largest sizes)

Per replicate: CAL 0.1–0.6 ms, EVAL 0.3–0.9 ms (single core; the AR loop is Python-level). CAL: 258 cells × 4 000 ≈ 1.0 M replicates ≈ 5 min. EVAL Stage A: 5 535 cells × 4 000 ≈ 22.1 M replicates ≈ 3–5 h single-core. Stage B: + 16 000 per escalated A/B/C check, worst case ≈ 88 M replicates ≈ 12–20 h. Parallel execution over cells is allowed by the checkpoint design. **Checkpoint size:** the current verbose row (~450 bytes) would make the EVAL checkpoint ≈ 10 GB at Stage A alone; see interpretation I-4.

## 7. Interpretations the implementation had to make (for the audit; none changes a frozen artifact)

- **I-1 CLUSTERED HETERO with `φ_G > 0`.** The frozen grid gives `PER_REPLICATE = true` and the formula string `(1/G) Σ_g σ²(ICC + (1−ICC)/m_g) × ar_factor(G, φ_G)`. For heteroskedastic cluster means under an AR(1) across clusters, no process has exactly that variance unless the sizes are equal; the executor uses the exact variance of the generated process and records the frozen-formula value beside it with `TRUTH_MATCHES_FROZEN = false`. Affected: HETERO × `φ_G = 0.3` MUST cells (and `0.6` STRESS). The owner must confirm "exact process variance" as the realized-truth rule, or amend the generator definition, before authorization.
- **I-2 RARE_EVENT HETERO.** The per-event SD multiplier is applied to the innovation of the event-level AR(1) process, which makes the frozen formula `c·E[m²]·ar_factor` exact. Venues are not materialized because the estimators read only the venue-averaged statistic and the frozen truth is defined on it.
- **I-3 CAL phase scope.** CAL replicates are executed only for the 258 MUST cells, since only they enter the Candidate C pool; STRESS and OUT_OF_DOMAIN cells have CAL ranges in the grid that are left unused.
- **I-4 Checkpoint row size.** Rows store derivable fields (bounds, miss and utility flags) for auditability; at the frozen scale that is ≈ 10 GB. A slimmer row (seed, `V_A`, `V_B`, `ν`, truth, error) from which everything else is recomputed would be ≈ 2 GB. The audit should choose before authorization; the choice does not affect any decision.
- **I-5 Candidate C at counts outside the supported range.** `U_C` is still computed there (with `c_env` of the largest calibrated size ≤ n) so that the cell can be reported; support is decided only in aggregation (range rule), never by the bound's existence.
- **I-6 Execution error mapping in aggregation.** A `CALIBRATION_EXECUTION_ERROR` cell makes the candidate `ERROR_STATE` for the class unless the candidate is already decisively not eligible; in the coverage list it is treated as unresolved. This follows C6 literally.

## 8. Not done

No frozen CAL or EVAL replicate executed; no C-table from frozen cells; no result artifact; no run authorization; no Run 1 outcome read; no adoption; no PR, no merge.
