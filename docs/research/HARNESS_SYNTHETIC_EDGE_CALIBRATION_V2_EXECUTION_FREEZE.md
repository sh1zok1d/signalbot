# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2 — control-calibration execution freeze

**Status:** `FROZEN_BEFORE_V2_PRODUCTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_CONTROL_CALIBRATION_EXECUTION_FREEZE`

**Not a RESULT. Not an ARM. Not Monte Carlo execution. Not B2-06, 2025, or 2026 authorization.**

This document is a docs/test-plumbing IMPLEMENTATION/RUNTIME FREEZE record.
It freezes the independently reviewed confirmatory-power control-calibration
runtime at implementation `8917c776`. It does not rewrite frozen prereg,
amendments, V1 TCB, historical freezes, or old canonical WORLD_RECORDS /
VISIBILITY / RESULT blobs. It does not arm production. It does not execute
the 3200-world calibration. It does not mint a RESULT.

Canonical machine-readable twin:
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json`, committed at
the stable path the runtime always looks for.

## Why this freeze

The previous consumable execution freeze (`2523b389`) binds `baf9f23` and
canonical plan `7fa12fd3…`. The control calibration requires the reviewed
confirmatory-power rank-policy (`1700ada1…`) and the rebound plan identity
`b0ed1553…`. Those bytes are a different implementation; a new freeze is
required. The old freeze and ARM remain valid historical authority for the
already-minted canonical evidence.

```text
REVIEWED_IMPLEMENTATION_HEAD = 8917c776ac8c148828bfab4395fd84890ff3c847
REVIEWED_IMPLEMENTATION_TREE = 15664b6a47b7196fcd230619e134f6a89feec23e

IMPLEMENTATION_REVIEW_VERDICT = TARGETED_REPAIR_COMPLETE
READY_FOR_CONTROL_FREEZE_ARM = YES

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact does not depend on a circular
self-hash of its own freeze-commit digest.

## Authority distinction

```text
HISTORICAL_SELF_REFERENCE_EXECUTION_FREEZE_VALID = YES
HISTORICAL_SELF_REFERENCE_EXECUTION_FREEZE_HEAD  = 2523b389e10585c81e18a69f43cc1e38fface41f
HISTORICAL_ARM_HEAD = 18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea
HISTORICAL_PLAN_SHA = 7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800
HISTORICAL_RUN_IDENTITY = 2088e76f99685c36e65387117b6f8a49482b3b68939f01d827023e0d36991818

CURRENT_EXECUTION_FREEZE_BINDS_IMPLEMENTATION = 8917c776ac8c148828bfab4395fd84890ff3c847
CURRENT_CANONICAL_PLAN_SHA256 = b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
AUTHORIZED_WORLD_COUNT = 3200
V1_PLANNED_JOBS_SHA256 = 5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6
```

This freeze commit does not carry historical ARM / RESULT / WORLD_RECORDS /
RESERVATION files. Those blobs remain byte-identical at their historical
commits. Freeze authentication forbids a freeze commit from carrying ARM or
protected result artifacts.

## Bound execution-authoritative implementation

Recomputed from git blobs at `8917c776`:

```text
scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py
  SHA256 = a206f97cdc597ec8e8c68943df80f21ce3eed508459b2dc2c298fa50159fec17
  size   = 37701

scripts/research/harness_synthetic_edge_calibration_v2_production.py
  SHA256 = 79aac05a9fa16795c52191d5e43113a93ff2601b52aa21175ea5e30fc47ad3ed
  size   = 76011
```

## Bound rank-policy source (reviewed confirmatory-power repair)

```text
scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py
  SHA256 = 1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec
  size   = 46396
```

## Scientific semantics (frozen, not redesigned)

```text
MODEL_DETECTED = primary_positive AND bootstrap_positive AND placebo_separation
EASY_POWER_INPUT = MODEL_DETECTED
MODERATE_POWER_INPUT = MODEL_DETECTED
MODEL_FLOOR_INPUT = MODEL_DETECTED
NULL_FPR_INPUT = MODEL_DETECTED
STRICT_PASS = unchanged
MATERIALITY = 0.02
EASY Wilson lower >= 0.90
MODERATE Wilson lower >= 0.70
NULL Wilson upper <= 0.05
TRAP protection = unchanged
identifiability semantics = unchanged
visibility semantics = unchanged
```

## Old canonical evidence (immutable historical blobs)

```text
WORLD_RECORDS = d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821
VISIBILITY    = 9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65
RESULT        = 761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0
```

This freeze does not remint, rewrite, or reinterpret those artifacts.

## Visibility

```text
visibility_limitation = UNRESOLVED_FAIL_CLOSED
sentinel = V2VisibilityStatisticUnavailable
```

This freeze does not resolve visibility for the control calibration.

## Freeze flags

```text
production_armed = false
production_executed = false
result_minted = false
world_records_created = false
authority_consumed = false
arm_created = false
execution_authorized = false
canonical_3200_run_started = false
```
