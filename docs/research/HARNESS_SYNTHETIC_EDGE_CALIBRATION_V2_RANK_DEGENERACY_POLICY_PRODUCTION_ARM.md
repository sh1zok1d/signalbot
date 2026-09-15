# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2 — production ARM

**Status:** `ARMED_FOR_ONE_CANONICAL_V2_PRODUCTION_EXECUTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`

**Canonical ARM artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json)

**Not a RESULT. Not an execution. Not B2-06, 2025, or 2026 authorization. Not market-hypothesis authorization.**

This document is a docs/authority-artifact-only ARM record. It authorizes
exactly one canonical 3200-world V2 production calibration against the
execution freeze parent below. It does not rewrite frozen prereg,
amendment, V2 policy, or V1 TCB bytes. It does not execute the 3200-world
calibration. It does not mint a RESULT, persist WORLD_RECORDS, create a
reservation, or mint a durable claim.

## Topology

The ARM commit is the immediate child of the V2 execution freeze. Runtime
verification of this ARM record derives the freeze commit F as this ARM's
own immediate parent, and the implementation commit I as F's own immediate
parent -- both from git topology, never from a hardcoded or caller-supplied
identity. Caller-supplied freeze/implementation identity is not authority.

Canonical production, when executed, MUST use the exact ARM commit object.
A descendant checkout is not armed. A merge commit is not authorized.

```text
FREEZE_PARENT_HEAD = 2523b389e10585c81e18a69f43cc1e38fface41f
FREEZE_PARENT_TREE = c779d293214e0e1e7994464afbbc2be928d6ce4d

REVIEWED_IMPLEMENTATION_HEAD = baf9f23045f4c19418eaaf3a9a7a1b69e21aff98
REVIEWED_IMPLEMENTATION_TREE = bd7aee5db2e6194058196d96c8a054bca08d0b86

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

No implementation, frozen scientific lib, methodology, or freeze bytes
change between the freeze parent and this ARM.

Creating this ARM does not consume one-shot authority and does not open a
production session. Consumption remains the existing canonical reservation
and session-based execution path.

## Authorized scope

```text
authorized_unit = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY
authorized_execution_kind = synthetic_production_monte_carlo
authorized_plan = exact_frozen_3200_world_plan
authorized_plan_sha256 = 7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800
authorized_world_count = 3200
authorized_run_count = 1
scope = production_synthetic_calibration_only
one_shot = true
```

This ARM does **not** authorize any market-hypothesis execution.

## Bound freeze artifact

ARM verification of this artifact reads
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json`
from the freeze parent git object.

```text
freeze_artifact_sha256 = 662424d5186b5abf861e291b8c11235da1c3cde56cb96a9af05febe3d878ba7f
freeze_artifact_size   = 15774
```

## Bound execution-authoritative implementation

Recomputed from git blobs at the reviewed implementation commit (`baf9f23`)
and required to match the tracked execution freeze:

```text
scripts/research/harness_synthetic_edge_calibration_v2_production.py
  SHA256 = ca04e53aca9f5260c00ab529036e0690a7652f5448b1dfa1c9e39651c75e02df
  size   = 73721

scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py
  SHA256 = e3ef3801da5a200c43b3f3e14c84045c9f7bf52cc85e0d8f5f43a4e087591193
  size   = 37038
```

## Bound scientific authority

```text
original_prereg_head = ada237edc330b44bc412332e263f124757919e93
original_prereg_tree = ba1c0873879b7ea8556c3e238f8b962b91da6dc2
amendment_001_head   = d8f0a996bc4341d0cbe01a1a061130b889ed5e75
amendment_001_tree   = 09dca9b1240a43d5de9de0dadf32d27e00e7eaea
amendment_002_status = REJECTED_HISTORICAL_AUTHORITY
amendment_002_governs_executable_science = false
amendment_003_md_sha256   = 10f26bbaeca30d47051026878ca8afd6622efdb8cc30562e44a7860abe896300
amendment_003_json_sha256 = f9856e8ed957bf9ed800121ef17c9c73223eee3bc4af2711130f19bf1a59b7db
amendment_004_md_sha256   = 9002838f4dc14a27a5f83870abb7cad4bd83a5c84abc75723263562045f646ca
amendment_004_json_sha256 = 8c3f9d2d662e5ce807baf4b65f94c145ed84c7337c41653493867d25e6a4ea55
```

## Bound V1 TCB (recomputed at ARM commit, unchanged)

```text
lib         12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51  size 37636
runner      0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a  size 3484
auth        0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507  size 34982
production  9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed  size 193104
worker      9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e  size 3994
```

## Visibility

```text
visibility_limitation = UNRESOLVED_FAIL_CLOSED
sentinel = V2VisibilityStatisticUnavailable
```

This ARM does not resolve, bypass, or authorize resolving the visibility
gap. Six visibility-dependent conclusion ids/inputs remain blocked.

## Protected scope

```text
status = ARMED_FOR_ONE_CANONICAL_V2_PRODUCTION_EXECUTION
authorized_run_count = 1
authorization_consumed = false

descendant_implementation_change_authorized = false
real_market_data_access_authorized = false
other_hypothesis_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

## Superseded / non-authoritative freezes

Historical 33/33 implementation freeze `e50fceebfe83b82ea9de2f98954ee7ad6c9a4308`
and historical post-wiring runtime freeze
`75f12bd31eac631a3baedd4a627344c0f2d40190` remain valid historical evidence
of their respective implementations. Neither authorizes this ARM; only the
freeze parent bound above does.

## What this ARM does not do

- run the 3200-world grid
- persist WORLD_RECORDS
- persist RESULT
- mint a durable claim
- create a reservation
- consume one-shot authority
- open B2-06 / 2025 / 2026 / other hypotheses
- resolve the visibility gap
