# `COMPILER_V3_EXPOSED_VARIANCE_ESTIMATOR_CALIBRATION_V1` — executor V2 (amendment V4 repairs; execution not authorized)

**Status:** `IMPLEMENTED / EXECUTION_NOT_AUTHORIZED / NO_FROZEN_REPLICATE_EXECUTED / NO_C_TABLE_FROM_FROZEN_CELLS / NO_RESULT_ARTIFACT`. Supersedes `…_EXECUTOR_V1.md` (kept as record). Authoritative design: amendment V4 with effective protocol V4.

Repairs relative to executor V1:
- **D1** aggregation uses the strict preference machine `amendment_v4.class_state` (A → B → C; a lower candidate is considered only when every higher one is `NOT_ELIGIBLE_DECISIVE`).
- **D2** `generators.clustered_truth` is the single authoritative CLUSTERED truth, `(1/G) Σ_g Σ_h sqrt(v_g v_h) φ^|g−h|`; the frozen-formula field and `TRUTH_MATCHES_FROZEN` flag are removed everywhere.
- **D3** `engine.decide_cell` locks Stage-A `PASS`/`FAIL` per `(CELL_ID, CANDIDATE, METRIC)`; Stage-B rows are generated once per cell and decide only the checks whose Stage-A state was `ESCALATE`; each check records `STAGE_A`, `STAGE_B`, `FINAL`, `DECIDED_AT`.
- **D4** `estimators.long_run_variance` for TWO_SAMPLE returns `nu_B = 2·(⌊n/(L(n)+1)⌋ − 1)` with per-arm bandwidth and raises on unequal arms.
- **D5** rare-event truth identity verified by `amendment_v4.rare_event_truth_by_covariance`.
- **D6** slim checkpoint rows (`P, C, S, VA, [VB], T, E`) with a header line carrying the executor digest and input digests; bounds, misses and utility flags are recomputed by `engine.derive`.
- Guards run over every cell before the checkpoint file is touched, so a refused call leaves no file behind.

State machine, formulas and generator mapping otherwise as in executor V1 §1–§3 with the D2/D4 replacements. Digests: `python -m scripts.research.compiler_v3_estimator_calibration.run --digests`. Tests: `tests/research/test_compiler_v3_estimator_calibration_executor.py`, `…_amendment_v4.py` (DEV fixtures only).
