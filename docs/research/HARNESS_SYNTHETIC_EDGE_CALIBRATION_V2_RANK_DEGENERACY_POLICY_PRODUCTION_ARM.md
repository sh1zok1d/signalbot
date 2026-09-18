# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2 — control-calibration production ARM

**Status:** `ARMED_FOR_ONE_CANONICAL_V2_PRODUCTION_EXECUTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`

**Canonical ARM artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json)

**Not a RESULT. Not an execution. Not B2-06, 2025, or 2026 authorization. Not market-hypothesis authorization.**

This document is a docs/authority-artifact-only ARM record. It authorizes
exactly one canonical 3200-world V2 control-calibration production run
against the control-calibration execution freeze parent below. It does not
rewrite frozen prereg, amendment, V2 policy, or V1 TCB bytes. It does not
execute the 3200-world calibration. It does not mint a RESULT, persist
WORLD_RECORDS, create a reservation, or mint a durable claim.

## Topology

```text
IMPLEMENTATION 8917c776ac8c148828bfab4395fd84890ff3c847
        ↓
FREEZE_PARENT_HEAD = bd5b5d3030f811faf7055517f314a2b1a51ba41e
FREEZE_PARENT_TREE = 3e993a5672ebe01c518c9700de6f69bb41cce1d3
        ↓
ARM (this commit)

REVIEWED_IMPLEMENTATION_HEAD = 8917c776ac8c148828bfab4395fd84890ff3c847
REVIEWED_IMPLEMENTATION_TREE = 15664b6a47b7196fcd230619e134f6a89feec23e

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

Runtime verification derives freeze F as this ARM's own immediate parent
and implementation I as F's own immediate parent. Caller-supplied
freeze/implementation identity is not authority.

No implementation, frozen scientific lib, methodology, or freeze bytes
change between the freeze parent and this ARM.

## Authorized scope

```text
authorized_unit = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY
authorized_execution_kind = synthetic_production_monte_carlo
authorized_plan = exact_frozen_3200_world_plan
authorized_plan_sha256 = b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
authorized_world_count = 3200
authorized_run_count = 1
scope = production_synthetic_calibration_only
one_shot = true
```

This ARM does **not** authorize the historical plan `7fa12fd3…`. Historical
ARM `18ebb4c` remains the authority for that plan and for RUN_IDENTITY
`2088e76f…`.

This ARM does **not** authorize any market-hypothesis execution.

## Bound freeze artifact

```text
freeze_artifact_path   = docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json
freeze_artifact_sha256 = b8fca8688e92e11dba4c2b22befae1e5ca6228aa41e624e19fc57eca0a458eb1
freeze_artifact_size   = 18745
```

## Bound rank-policy

```text
v2_policy_sha256 = 1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec
v2_policy_size   = 46396
```

## Historical distinction

```text
HISTORICAL_ARM_HEAD = 18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea
HISTORICAL_PLAN_SHA = 7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800
HISTORICAL_RUN_IDENTITY = 2088e76f99685c36e65387117b6f8a49482b3b68939f01d827023e0d36991818
NEW_ARM_PLAN_SHA = b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f
```

## Visibility

```text
visibility_limitation = UNRESOLVED_FAIL_CLOSED
```

This ARM does not resolve, bypass, or authorize resolving visibility for
the control calibration.

## Not authorized / not done

```text
authorization_consumed = false
reservation_created = false
production_executed = false
result_minted = false
world_records_created = false
```
