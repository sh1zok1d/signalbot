# HARNESS_PERFORMANCE_V1 — production-path performance repair

**Status:** `PERFORMANCE_EXECUTION_FROZEN_UNARMED / NOT_A_PRODUCTION_RESULT / NOT_AN_ARM`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Parent ARM (unused, must not be reused):** `0abc5fe167e018ebe1f7efbb70694887ac095e17`

**Reviewed sequential oracle:** `3fadc391ee0002e35463b526301d287d4a662828`

**Previous reviewed implementation (performance, REPAIR_REQUIRED):**
HEAD `c461f09e3d7eafac8ddd95ff87cd741b3af29534` /
TREE `e23199bb28f6b2f61eaee0f682d1b351ae34f8ee`

This is a performance-only descendant of the frozen synthetic production
calibration. It does not change scientific methodology, does not consume the
existing ARM, does not create a new ARM, and does not execute the canonical
3200-world grid.

Independent review accepted the performance result as genuine and required
repairs, now implemented on this HEAD:

1. **BLOCKER-1** — pin `harness_synthetic_edge_calibration_v1_worker.py` in the
   live execution TCB from git objects (`WORKER_PATH` / `WORKER_SHA256` /
   `WORKER_SIZE`). A worker-byte change after freeze must invalidate that
   freeze/ARM.
2. **MAJOR-1** — crash-safe durable partial world evidence, distinct from
   canonical `WORLD_RECORDS` / scientific RESULT. Partial evidence is not
   one-shot consumption. Resume is exact and identity-bound.
3. **BLOCKER-2** — checkpoint bytes are untrusted cached compute. A
   self-consistent forged record (honest SHA256, valid schema/identity) must
   not become scientific authority. Authoritative mint authenticates every
   cached/computed record against isolated frozen git execution bytes. Secrets
   and HMAC are not scientific authority.

Required topology after this unit:

```
REVIEWED IMPLEMENTATION
    9c573df81dad55829f52cff0f94e8c5918c30fd9 /
    b9d928687e5ea4e9773f07b0cb6f8e287b65562f
        |
        v
PERFORMANCE_EXECUTION_FREEZE  (this docs/metadata-only freeze)
        |
        v
NEW immediate-child ARM  (not created)
        |
        v
canonical production run  (not executed)
```

Canonical freeze artifact:
[`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json)

Independent final review: `GO_FOR_PERFORMANCE_FREEZE`. BLOCKERS=0 MAJORS=0 MINORS=0.
BLOCKER-1, MAJOR-1, and BLOCKER-2 remain CLOSED.

Do not shortcut that topology. The unused ARM at `0abc5fe` authorizes the
freeze-parent driver bytes, not this implementation. No migration of old
partial evidence onto a different implementation/freeze is authorized.
This freeze does not arm production.

## What changed

Same science, same randomness, same logical results, faster execution.

1. **Placebo BASE cache.** Frozen `placebo_q95` refits `Y ~ 1+X1+X2` on every
   placebo replicate. BASE expanding-era predictions are now computed once per
   candidate and reused. The candidate model is still refit on every
   within-era permutation. Permutation RNG consumption is unchanged.
2. **Single-factorization rank.** Frozen `fit_lstsq` calls `matrix_rank` then
   `lstsq`. `numpy.linalg.lstsq(..., rcond=None)` already returns rank under the
   same default cutoff. The hot path uses lstsq rank and still raises
   `IncompleteWorld("design is not full rank")` without returning coefficients
   when rank-deficient. Success-path coefficients are the lstsq result.
   This optimization is retained only because exact equality vs frozen
   `fit_lstsq` was demonstrated (random designs + DGP expanding-era designs).
3. **World-level multiprocessing.** Independent planned jobs may run in spawn
   workers. Unordered completed records are reordered to `planned_production_jobs()`
   / the explicit diagnostic plan before any digest chain, aggregation, or
   mint. Worker PID, wall clock, worker index, and completion order do not seed
   science. Default worker count is **1**. `--workers N` is explicit.
   Conservative operator hint: `conservative_worker_count()` = half of
   detected CPUs, capped at 16. Do not blindly spawn `os.cpu_count()`.
   Isolated mint-time authentication and claim-time historical recomputation
   reuse the same spawn semantics via `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_WORKERS`
   (falls back to `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS` if unset).
   Worker count is operational, not scientific authority. Changing it must
   not change identities, seeds, records, digests, or conclusions. The two
   trust passes remain distinct: mint auth does not replace claim-time
   `FULL_3200_RECOMPUTATION`.
4. **BLAS limits.** Workers set `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1`,
   `MKL_NUM_THREADS=1`, `NUMEXPR_NUM_THREADS=1` before importing numpy.

Frozen scientific library bytes are unchanged
(`FROZEN_REVIEWED_LIB_SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`).

## What did not change

3200 production worlds, scenario definitions/order, N values, world
identities, `world_seed` / namespace RNG, DGP, `FEATURE_IDS`, candidate
ordering, visibility=500, bootstrap=500, placebo=999, OLS specification,
era definitions, expanding-era prediction semantics, metrics, thresholds,
gates, invalid-world/denominator/Wilson/aggregation/mechanical-conclusion
semantics, canonical JSON schema, `record_digest_chain`,
`world_set_sha256`, preregistration.

No reduction in scientific workload.

## Fail-closed parallelism

If any worker crashes, times out via exception, returns malformed data,
returns a duplicate/unknown identity, omits a planned world, or the
completed set does not match the planned set:

- NO RESULT
- NO WORLD_RECORDS
- NO AUTHORITY CONSUMPTION
- no reroll, no replacement seeds, no skipped worlds

## Production isolation

`scripts/research/harness_synthetic_edge_calibration_v1_performance.py` is
labelled `NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC`. It cannot:

- treat an ARM as permission
- consume production authority
- write RESULT / WORLD_RECORDS / reservation / claim
- encode production N `{2500, 5000, 10000}` or the 3200-world plan
- invoke `--run-production-grid`
- touch B2-06, validation 2025, OOS 2026, or real market data

Equivalence tests load sequential oracle bytes from git commit `3fadc39`,
not by aliasing the live optimized module.

## Operator notes (future armed run only)

```text
python3 -m scripts.research.harness_synthetic_edge_calibration_v1 \
  --run-production-grid --expected-head <NEW_ARM_HEAD> --workers N
```

This unit does **not** execute that command. Default `N=1`. Isolated
production reads `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS`.

A future ARM that authorizes this performance HEAD must pin
`harness_synthetic_edge_calibration_v1_worker.py` in addition to the existing
execution-authority paths. Live execution TCB is:

- `scripts/research/harness_synthetic_edge_calibration_v1_lib.py`
- `scripts/research/harness_synthetic_edge_calibration_v1.py`
- `scripts/research/harness_synthetic_edge_calibration_v1_auth.py`
- `scripts/research/harness_synthetic_edge_calibration_v1_production.py`
- `scripts/research/harness_synthetic_edge_calibration_v1_worker.py`

Authority is git-object bytes at the authorized commit (`path` / `sha256` /
`size`), not worktree trust, filename-only binding, or caller-supplied digests.
`scripts/research/harness_synthetic_edge_calibration_v1_performance.py` remains
outside the TCB.

## Durable partial world evidence

Completed worlds may be checkpointed under
`artifacts/research/harness_synthetic_edge_calibration_v1/durable_partial_world_evidence`
(`DURABLE_PARTIAL_WORLD_EVIDENCE`). That directory is not:

- `PRODUCTION_WORLD_RECORDS`
- `PRODUCTION_RESULT`
- `AUTHORITY_CONSUMED`
- `CALIBRATION_COMPLETE`

Writes are per-world atomic (`*.tmp` + fsync + `os.replace`). Torn/truncated
files fail closed. Incomplete in-flight worlds are not persisted and are
recomputed from the frozen identity. Resume verifies execution/plan identity,
rejects duplicates/unexpected/malformed/foreign records, schedules only
missing worlds, and canonical-reorders before aggregation. Worker completion
order remains irrelevant.

Checkpoint trust states are derived, not persisted:

```
CHECKPOINT_CACHED
CHECKPOINT_STRUCTURALLY_VALID   # resume may retain these without recomputing
CHECKPOINT_SCIENTIFICALLY_VERIFIED  # derived by isolated frozen-git verifier only
```

`HASH(checkpoint content) == stored hash` is not proof that the scientific
computation occurred. Resume may use STRUCTURALLY_VALID records to continue
compute. Canonical `WORLD_RECORDS` / RESULT mint requires isolated
`authenticate-cached-records` against exact frozen git execution bytes, the
frozen plan, and exact world identities. A self-consistent forgery, a
whole-checkpoint fabrication, or a mixed legitimate+forged store fails
closed. Persisted `verified=true` metadata is ignored/refused; verification
status is not trusted from checkpoint content.

Authoritative verification cost is a separate isolated scientific pass at
production mint and a distinct claim-time `FULL_3200_RECOMPUTATION`. Both
isolated children may use the same world-parallel spawn path as compute.
Worker count is operational (`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_WORKERS`,
falling back to `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS`). The two
trust passes stay independent. Parent authentication proofs must match
`observed_world_count` to the submitted/planned world count; digest agreement
alone is not enough. Resume does not immediately recompute completed worlds.

State machine:

```
AUTHORIZED -> RUNNING/PARTIAL -> COMPLETE -> RESULT CLAIM
```

An aborted run with durable partial evidence is not consumed. Resume
is allowed only under the exact execution identity that created the partial
evidence. A different implementation/freeze/ARM must not reuse it. Partial
evidence is not scientific authority.

## Bounded diagnostic measurements (not production N)

Fixture: `NON_PRODUCTION_PERFORMANCE_DIAGNOSTIC`, 3 worlds, `n=80`,
production replicate counts (visibility 500 / bootstrap 500 / placebo 999).
Host: 4 logical CPUs. Python 3.12.3.

These rows are **MEASURED** on the diagnostic fixture. They are not n=5000.

| configuration | s/world | worlds/hour | speedup vs frozen sequential oracle | peak RSS (KB) |
|---|---|---|---|---|
| OLD frozen sequential oracle | 2.8707 | 1254 | 1.00 | 55456 |
| NEW sequential workers=1 | 1.2840 | 2804 | 2.24 | 55456 |
| NEW workers=2 | 1.0098 | 3565 | 2.84 | 55720 |
| NEW workers=4 | 0.6576 | 5475 | 4.37 | 55720 |

Parent `process_time` does not include spawn-worker CPU; wall-clock is the
throughput metric for workers>1.

Workers=4 on only 3 worlds cannot demonstrate 4-way linear scaling (at most
3 worlds run at once). Parallel efficiency from that cell is not a 3200-world
scaling law.

Prior aborted production run (**MEASURED_PRIOR_RUN**, n=5000): 11.92 s/world,
~302 worlds/hour, 10.5–13 h projected sequential 3200.

If the 2.24× sequential diagnostic speedup versus the frozen oracle also holds
at n=5000, sequential production would be about 5.3 s/world (**EXTRAPOLATED**,
~4.7 h for 3200). Dedicated 16-core execution at ~70% of linear scaling on that
rate would be about 0.4–0.5 h (**EXTRAPOLATED**). That is a target-shaped
extrapolation from mixed n=80/n=5000 evidence, not a measured 3200-world runtime.
Do not treat n=80 × 3200 as a production estimate.

## Isolated verifier parallelism (operational, not scientific)

Mint-time `authenticate-cached-records` and claim-time
`FULL_3200_RECOMPUTATION` remain distinct trust passes. Both reuse
`_evaluate_jobs_for_verification` → spawn `worker.evaluate_job_payload`.
Spawn children inherit the parent's `sys.path`; the parent therefore puts
the frozen worker repository root first before creating the Pool, so
children cannot import a live checkout of the same module name.

Worker count is operational:

- `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_VERIFY_WORKERS`
- fallback: `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_WORKERS`
- explicit `workers=` argument on the parent authenticator
- default: 1

Changing worker count must not change identities, seeds, records, digests,
or conclusions. Parent proofs still omit worker count. Parent additionally
requires `proof["observed_world_count"] == len(payload["records"]) == planned
world count`.

### n=5000 verifier engine (**MEASURED**, not 3200 production)

Shared authentication/historical recompute engine:
`_evaluate_jobs_for_verification`. Host: 4 logical CPUs. Python 3.12.3.
Fixture worlds: `NULL` n=5000. Production replicate counts. Not the 3200-world
grid.

| workers | worlds timed | wall s | s/world | speedup vs 1W | notes |
|---|---|---|---|---|
| 1 | 1 | 5.6371 | 5.6371 | 1.00 | parent CPU ≈ wall |
| 2 | 2 | 6.0889 | 3.0444 | 1.85 | ~1.94 child CPUs / wall |
| 4 | 4 | 6.0596 | 1.5149 | 3.72 | ~3.89 incremental child CPUs / wall |

workers=1 vs workers=4 on the same 4-world n=5000 set: **exact** canonical
JSON equality (identities, seeds, records, digest chain).

AUTH and historical isolated children use this same engine. Isolated
interpreter spawn/compare overhead is extra and small relative to n=5000
world cost. These rows are **MEASURED**. They are not a 3200-world runtime.

### Lifecycle wall-clock model (MAIN + mint AUTH + claim HIST)

Three scientific passes over 3200 worlds. Worker count does not remove a
pass. It only changes wall clock.

Using the **MEASURED** n=5000 s/world rates:

| workers | s/world | 3×3200 projected wall | class |
|---|---|---|---|
| 1 | 5.6371 | 15.03 h | MEASURED_RATE × 3200×3 |
| 4 | 1.5149 | 4.04 h | MEASURED_RATE × 3200×3 |
| 8 | not measured | this 4-CPU host cannot beat ~4.04 h; on ≥8 CPUs at the measured 93% 4-wide efficiency: ~2.02 h; conservative 70% of 8-wide: ~2.68 h | EXTRAPOLATED |
| 16 | not measured | 16-core at 70% of linear vs 1W: ~1.34 h; at 93% efficiency: ~1.01 h | EXTRAPOLATED |

Do not claim linear scaling beyond the 1/2/4-worker measurements. 8- and
16-worker figures are host-capacity extrapolations, not measurements.
