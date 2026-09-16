# Harness Synthetic Edge Calibration V2 — Post-run forensic review

Status: **CANONICAL_RESULT_VALID / V2 DEVELOPMENT-CONSUMED**

Date: 2026-09-16

This document records the read-only forensic review of the V2 confirmatory-power control calibration. It does not mutate methodology, thresholds, scientific code, evaluator semantics, WORLD_RECORDS, VISIBILITY, RESULT, or historical evidence. It does not authorize another run.

## Canonical execution identity

- IMPLEMENTATION: `8917c776ac8c148828bfab4395fd84890ff3c847`
- FREEZE: `bd5b5d3030f811faf7055517f314a2b1a51ba41e`
- ARM: `710cad607ec6740e550698cdc212f7dd33004481`
- RESERVATION: `068874d8fa710f474f91fe61224a7cc54a42e0cd`
- RUN_IDENTITY: `90d38af4951b0bbe00fc5ffaf7989c8940d178c31aad987176901c7ce947ad1e`
- PLAN_SHA: `b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f`
- WORLD_JOB_SHA: `5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6`

Artifacts:

- WORLD_RECORDS SHA256: `e8667f930a4acc7fb5dd26fa62414a8f4b359121336902aac651cb76f4e50dbf`
- RECORDS_INNER SHA256: `f0d18ca1c8ed654856abca03d9e0f8d22b72ab5f6f4683cc11e45f3353bc0559`
- VISIBILITY SHA256: `ed1c17f0e2eb8f04ed917a7c84811d10a0d152f770a9315d2ade1cac1be93f9b`
- RESULT SHA256: `ffce3daa24eb9039526d6de4b11a6ac43cfd36803058fe21827f1cd1f839100b`

Mechanical conclusion:

`METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`

## Integrity verdict

**CANONICAL_RESULT_VALID**

The result is legitimately claimable as the canonical frozen-evaluator output for this ARM/reservation.

The review established:

- `assemble_v2_result_payload_with_visibility` existed in the authorized implementation before outcomes existed.
- `derive_v2_world_visibility_record` existed and was semantically authorized before the run.
- no new scientific authority, threshold, statistic, visibility definition, verdict mapping, or evaluator behavior was introduced after outcomes were known.
- all final 3200 WORLD_RECORDS belong to the same reservation/run identity.
- no selective rerun, replacement world, second reservation, or second canonical attempt occurred.
- the RESULT re-assembles byte-identically from the exact WORLD_RECORDS + VISIBILITY evidence through the frozen assembly path.
- historical WORLD_RECORDS `d372eb00…`, VISIBILITY `9be8dceb…`, and RESULT `761cc9af…` remain immutable at their historical minting commits.

`mint_v2_result` refused by frozen design because the inherited ladder does not itself supply `GROUND_TRUTH_VISIBLE`. The historical visibility bundle authenticator is identity-locked to the previous canonical run and correctly refuses the new WORLD_RECORDS SHA. The authorized new-run path derives per-world visibility through the pre-outcome `derive_v2_world_visibility_record` function and supplies that frozen map to `assemble_v2_result_payload_with_visibility`.

## Execution accounting

- attempted worlds: 3200
- completed worlds: 3200
- WORLD_VALID: 3200
- WORLD_INVALID: 0
- CANDIDATE_IDENTIFIABLE: 31708
- CANDIDATE_NOT_IDENTIFIABLE: 292
- required coverage: ADEQUATE
- cell coverage: ADEQUATE

No scientific-code, threshold, or methodology change occurred after the ARM.

## Confirmatory-power outcome

Frozen semantics:

`MODEL_DETECTED = primary_positive AND bootstrap_positive AND placebo_separation`

`STRICT_PASS` is not the confirmatory power input.

### EASY — oracle F03, N=5000, 400 worlds

| step | count | rate |
|---|---:|---:|
| total | 400 | 1.0000 |
| identifiable | 400 | 1.0000 |
| primary_positive | 400 | 1.0000 |
| bootstrap_positive | 365 | 0.9125 |
| placebo_separation | 400 | 1.0000 |
| MODEL_DETECTED | 365 | 0.9125 |

- Wilson lower: `0.8807392673857086`
- frozen conclusion: `INDETERMINATE`
- all 35 misses are `primary + placebo + NOT bootstrap`.
- GROUND_TRUTH_VISIBLE: 400/400.

The EASY point estimate exceeds 0.90, but the frozen Wilson lower bound does not.

### MODERATE — oracle F03, N=5000, 400 worlds

| step | count | rate |
|---|---:|---:|
| total | 400 | 1.0000 |
| identifiable | 400 | 1.0000 |
| primary_positive | 355 | 0.8875 |
| bootstrap_positive | 108 | 0.2700 |
| placebo_separation | 334 | 0.8350 |
| MODEL_DETECTED | 108 | 0.2700 |

- Wilson lower: `0.22883278412268437`
- frozen conclusion: `FAIL`
- 292/292 MODEL_DETECTED misses fail bootstrap.
- 226/292 misses are bootstrap-only after primary + placebo pass.
- 45/292 fail primary + bootstrap + placebo.
- 21/292 pass primary but fail bootstrap + placebo.
- GROUND_TRUTH_VISIBLE: 345/400; 237 visible worlds still miss MODEL_DETECTED.

### NULL

- MODEL_DETECTED: 2/400 = 0.005
- Wilson upper: `0.018044918436243156`
- conclusion: `PASS`

The same bootstrap gate that suppresses MODERATE power also contributes to strong NULL protection. This is coherent conservatism, not evidence that the confirmatory component is mechanically broken.

### TRAP and visibility

- TRAP: `PASS`
- MODEL_FLOOR: `ABOVE_MEASURED_FLOOR`
- VISIBILITY_FLOOR: `ABOVE_MEASURED_FLOOR`
- TINY_NOISY: `VISIBILITY_FLOOR`

Identifiability and visibility do not explain the MODERATE power failure.

## Read-only scientific diagnosis

Dominant supported diagnosis:

1. **Bootstrap confirmation is the dominant gate.** Every MODERATE MODEL_DETECTED miss fails the frozen block-bootstrap `q025 > 0` test.
2. **MODERATE carries materially less detectable information than EASY.** Its injected effect/support combination produces a much smaller location of the AE-improvement distribution, so the lower bootstrap quantile falls below zero much more often.
3. Placebo separation, candidate identifiability, and the primary statistic are not the dominant bottlenecks.

The existing artifacts do not persist `bootstrap_q025` or `placebo_q95`, even though those values are computed. Therefore the exact distance to the bootstrap/placebo boundary cannot be reconstructed from canonical WORLD_RECORDS without re-evaluation. V3 should persist these diagnostic statistics prospectively.

## Performance forensic finding

The long wall-clock time was not the cost of one uninterrupted scientific grid alone.

Observed path:

1. original grid evaluated all 3200 worlds with parallel workers and checkpointed them;
2. the operational driver then died on artifact/logging I/O after all worlds were already checkpointed;
3. durable grid resume found `cached=3200, pending=0` and assembled in approximately 0.5 s;
4. mint authentication then re-executed frozen `evaluate_v2_world_in_session` for all 3200 jobs as an independent comparison;
5. that full scientific re-evaluation took approximately `19999` seconds (~5 h 33 min);
6. visibility derivation was comparatively small (~46 s);
7. RESULT assembly was effectively instantaneous.

The artifact path also suffered I/O stalls. `/opt/cursor/artifacts` was observed as a dangling symlink to `/cursor/stores/self/artifacts`; the original process died with `OSError [Errno 5]`, and subsequent logging stalls were observed on the order of ~10, ~16, and ~30 minutes.

Interpretation: a substantial fraction of the ~8+ hour user-observed latency came from full mint-time re-authentication and broken artifact I/O, not from the fundamental cost of the initial synthetic 3200-world grid.

This document does not authorize a performance repair. Performance work must remain subordinate to the scientific transition to V3 and must not delay market research without a concrete blocker.

## V2 disposition

V2 is now **DEVELOPMENT-CONSUMED** for methodology design.

Its canonical outcome remains immutable. V2 artifacts may be used to understand failure modes and design V3, but no V3 claim may be validated on these same 3200 worlds.

A future V3 design must be frozen before any fresh acceptance outcomes are inspected.

No B2-06 execution is authorized.
