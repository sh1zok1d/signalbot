# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — Fixture implementation

**Status:** `FIXTURE_IMPLEMENTATION_UNARMED`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`  
**Does not rewrite:** the frozen original prereg or Amendment_001.

This document records fixture-only implementation identity. It is not a RESULT,
not an ARM, and not production authorization.

## Frozen methodology contract

Read together; Amendment_001 controls where it clarifies or retires a rule.

```text
original prereg HEAD = ada237edc330b44bc412332e263f124757919e93
original prereg TREE = ba1c0873879b7ea8556c3e238f8b962b91da6dc2
Amendment_001 HEAD   = d8f0a996bc4341d0cbe01a1a061130b889ed5e75
Amendment_001 TREE   = 09dca9b1240a43d5de9de0dadf32d27e00e7eaea
```

Independent rereview of the amendment: `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`,
`GO_FOR_V2_IMPLEMENTATION`.

## Implementation identity

```text
implementation_exists = true          # fixture module + targeted tests only
fixture_only = true
synthetic_execution_authorized = false
v2_production_arm_authorized = false
production_calibration_executed = false
result_mint_authorized = false
authority_consumed = false
next_required_step = INDEPENDENT_NARROW_REVIEW_OF_REPAIR
```

Code:

- `scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py`
- `tests/research/test_harness_synthetic_edge_calibration_v2_rank_policy.py`

The module has no production entrypoint. `run_frozen_production_grid` and
production N / 3200-world planned sizes fail closed. V1 TCB files are not
modified. DGP, RNG, seeds, candidates, full-rank OLS, bootstrap, placebo,
visibility, checkpoint trust, mint auth, and historical recompute science
are imported unchanged from the V1 lib.

BLIND taxonomy is exactly `taxonomy_of(selected)` with no scenario-specific
reinterpretation. Chronology/lookahead is a world-level failure and cannot
become a candidate reason. This fixture stage does not execute bootstrap,
placebo, or visibility; reserved non-finite reasons are fixture-forced only
via `force_candidate_reason`, which cannot enter production N.

This stage does not mint RESULT or WORLD_RECORDS, does not consume V1 ARM
authority, and does not authorize B2-06.
