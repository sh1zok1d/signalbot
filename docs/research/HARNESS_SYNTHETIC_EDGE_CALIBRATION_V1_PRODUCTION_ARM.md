# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — final production Monte Carlo ARM

**Status:** `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Canonical ARM artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json)

**Not a RESULT. Not an execution. Not B2-06, 2025, or 2026 authorization. Not market-hypothesis authorization.**

This document is a docs/authority-artifact-only ARM record. It authorizes
exactly one frozen synthetic production Monte Carlo calibration against the
canonical DRIVER FREEZE parent. It does not rewrite frozen prereg or
scientific lib bytes. It does not execute the 3200-world calibration. It
does not mint a RESULT, persist WORLD_RECORDS, create a reservation, or
mint a durable claim.

## Topology

The ARM commit is the immediate child of the canonical DRIVER FREEZE.
Verification loads the tracked freeze artifact from git objects at that
parent. Caller-supplied freeze identity is not authority.

```text
REVIEWED_IMPLEMENTATION_HEAD = 3fadc391ee0002e35463b526301d287d4a662828
REVIEWED_IMPLEMENTATION_TREE = 5fb77727c418cc42bf3c1c6553355a0475f42efc

FREEZE_PARENT_HEAD = 40e54b8c0497593aa3daf0bddc0e014bf048489f
FREEZE_PARENT_TREE = 0f6be102b29ce964f0ea8f3947927854888eef08

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

No implementation, frozen scientific lib, or prereg bytes change between
the freeze parent and this ARM. The only test change is converting the
pre-ARM “live HEAD remains unarmed / ARM absent” assertions into a live
schema check of this ARM artifact. That is ARM validation, not driver or
scientific logic.

A descendant of this ARM commit is not armed. One-shot consumption remains
the existing canonical production execution path: successful RESULT at HEAD
consumes authorization. This ARM does not consume itself.

## Authorized scope

```text
authorized_unit = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1
authorized_execution_kind = synthetic_production_monte_carlo
authorized_plan = exact_frozen_3200_world_plan
authorized_run_count = 1
scope = production_synthetic_calibration_only
production_only_scope = true
one_shot = true
```

This ARM does **not** authorize any market-hypothesis execution.

## Bound freeze and reviewed implementation

ARM verification reads:

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.json`

from the freeze parent. It requires:

```text
authorized_execution_commit = freeze parent HEAD
authorized_execution_tree   = freeze parent TREE
reviewed_implementation_head / tree = freeze-recorded reviewed identity
execution-authority bytes at ARM HEAD = freeze parent bytes
```

## Bound execution-authority SHA256

Recomputed from git blobs at the freeze parent and required to match the
tracked freeze artifact:

```text
lib         12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
runner      5d6e93f27584dfa181de86e43541fc927cbc143cdc5df66c2d63e988b9c41200
auth        0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507
production  3fa11f9980bf1b51f4585cc53d8290c969887f277d85551dd65facd8b5d1e613
prereg_json 78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708
prereg_md   a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3
```

## Protected scope

```text
driver_implementation_frozen = true
production_monte_carlo_arm_authorized = true

production_calibration_executed = false
production_result_minted = false
world_records_persisted = false
authorization_consumed = false

real_market_data_access_authorized = false
B2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
other_hypothesis_authorized = false
market_hypothesis_execution_authorized = false
```

No protected market data is available to this run.

## Historical ARM #116

HEAD `940d85bf58673396c6c0cc05ce2134a2e2e92809` remains historical evidence
that the parent-authorizing ARM mechanism works. It is **not** this ARM and
is not merged into this branch.

```text
status = REJECTED_NOT_MERGED / SUPERSEDED_BY_DRIVER_FIRST_SEQUENCE
```

## What this ARM does not do

- run the 3200-world grid
- persist WORLD_RECORDS
- persist RESULT
- mint a durable claim
- create a reservation
- consume one-shot authority
- open B2-06 / 2025 / 2026 / other hypotheses
