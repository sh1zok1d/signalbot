# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — final production Monte Carlo ARM

**Status:** `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Canonical ARM artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json)

**Not a RESULT. Not an execution. Not B2-06, 2025, or 2026 authorization. Not market-hypothesis authorization.**

This document is a docs/authority-artifact-only ARM record. It authorizes
exactly one frozen synthetic production Monte Carlo calibration against the
canonical PERFORMANCE EXECUTION FREEZE parent. It does not rewrite frozen
prereg or scientific/execution TCB bytes. It does not execute the 3200-world
calibration. It does not mint a RESULT, persist WORLD_RECORDS, create a
reservation, or mint a durable claim.

## Topology

The ARM commit is the immediate child of the performance/execution freeze.
Verification of this ARM record loads the tracked freeze artifact from git
objects at that parent. Caller-supplied freeze identity is not authority.

Canonical production, when executed, MUST use the exact ARM commit object.
A descendant checkout is not armed. A merge commit is not authorized.

```text
REVIEWED_IMPLEMENTATION_HEAD = f47c5394d8cc0c3f6312cd4156f389ba7ee81dbd
REVIEWED_IMPLEMENTATION_TREE = 84b23e4c51a4f7ccf59bb36d5333ef7974ea7eab

FREEZE_PARENT_HEAD = 1499bc5f5e731f226650abd5051447fc846f722b
FREEZE_PARENT_TREE = 1a652db9a1549185da448553e8c57c613808d693

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

No implementation, frozen scientific lib, worker, or prereg bytes change
between the freeze parent and this ARM.

Creating this ARM does not consume one-shot authority. Consumption remains
the existing canonical production execution path.

## Authorized scope

```text
authorized_unit = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1
authorized_execution_kind = synthetic_production_monte_carlo
authorized_plan = exact_frozen_3200_world_plan
authorized_plan_sha256 = 5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6
authorized_run_count = 1
scope = production_synthetic_calibration_only
production_only_scope = true
one_shot = true
WORKER_COUNT_IS_OPERATIONAL = YES
WORKER_COUNT_CHANGES_SCIENCE = NO
```

Worker count is operational, not scientific authority. Changing it must not
change world identity, RNG, scientific output, canonical order, digest chain,
or RESULT.

This ARM does **not** authorize any market-hypothesis execution.

## Bound freeze and reviewed implementation

ARM verification of this artifact reads:

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json`

from the freeze parent git object. SHA256
`2a0daa843e39ac04831e4bf31d85b1b01c3a9d347127368cef60bbfb8bf05d9d`, size 4821.

```text
authorized_execution_commit = freeze parent HEAD
authorized_execution_tree   = freeze parent TREE
reviewed_implementation_head / tree = freeze-recorded reviewed identity
execution-authority bytes at ARM HEAD = freeze parent bytes
```

## Bound execution-authority SHA256 / size

Recomputed from git blobs at the freeze parent and required to match the
tracked performance freeze TCB:

```text
lib         12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51  size 37636
runner      0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a  size 3484
auth        0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507  size 34982
production  9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed  size 193104
worker      9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e  size 3994
prereg_json 78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708
prereg_md   a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3
```

## Protected scope

```text
production_monte_carlo_arm_authorized = true
production_armed = true

production_executed = false
production_calibration_executed = false
production_result_minted = false
result_created = false
world_records_persisted = false
world_records_created = false
authorization_consumed = false

real_market_data_access_authorized = false
B2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
other_hypothesis_authorized = false
market_hypothesis_execution_authorized = false
```

## Superseded ARMs

Unused driver ARM `0abc5fe167e018ebe1f7efbb70694887ac095e17` remains
historical evidence. It does **not** authorize this implementation or freeze.

Historical performance ARM `120ac456df3a22884c48eed45852bdd001706f54` remains
`SUPERSEDED / DOES_NOT_AUTHORIZE_THIS_IMPLEMENTATION`.

Historical ARM `940d85bf58673396c6c0cc05ce2134a2e2e92809` remains
`REJECTED_NOT_MERGED / SUPERSEDED_BY_DRIVER_FIRST_SEQUENCE`.

## What this ARM does not do

- run the 3200-world grid
- persist WORLD_RECORDS
- persist RESULT
- mint a durable claim
- create a reservation
- consume one-shot authority
- freeze a scientific worker count
- open B2-06 / 2025 / 2026 / other hypotheses
