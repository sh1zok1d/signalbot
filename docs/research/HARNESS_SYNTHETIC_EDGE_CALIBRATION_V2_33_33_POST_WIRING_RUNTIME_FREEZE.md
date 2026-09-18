# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33 — post-wiring runtime freeze

**Status:** `FROZEN_BEFORE_V2_PRODUCTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_POST_WIRING_RUNTIME_FREEZE`

**Not a RESULT. Not an ARM. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This document is a docs/test-plumbing IMPLEMENTATION/RUNTIME FREEZE record.
It freezes the exact independently reviewed post-wiring V2 33/33 executable
runtime. It does not rewrite frozen prereg, amendments, V2 rank-policy, V1
TCB, or the historical 33/33 implementation freeze. It does not arm
production. It does not execute the 3200-world calibration. It does not mint
a RESULT. It does not create WORLD_RECORDS.

Canonical machine-readable twin:
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_POST_WIRING_RUNTIME_FREEZE.json`.

## Authority distinction

The historical 33/33 implementation freeze remains valid historical
authority. It is **not** invalid. It remains exact evidence of
implementation `614295d`.

```text
HISTORICAL_33_33_FREEZE_VALID = YES
HISTORICAL_33_33_FREEZE_HEAD  = e50fceebfe83b82ea9de2f98954ee7ad6c9a4308
HISTORICAL_33_33_FREEZE_TREE  = 2f2b0943fffe143324da4c10545d560d6048079e
HISTORICAL_33_33_FREEZE_ARTIFACT_SHA256 =
  89ca1ba0b416a4e2af07aa03d32b0ed2e9a9ec0ecee0327e3fda113c07ff74d7
HISTORICAL_33_33_BINDS_IMPLEMENTATION =
  614295d4c0bf7a263bd2c6dc9a5c595e2c80055f
```

`production.py` later changed through independently reviewed
authorization-only repairs:

```text
84f4c566fcea106156c00cfea1a825f3a050946f
  tree 82d4e2f4d41cc02bf4d6d9f3d819137633a97dfc
  V2 ARM authorization wiring repair

c1d6acc9f3db3b35f06a02d7fb2361b8d4ea69c5
  tree 67f19c997d7480f77ef741e2e2715c06cf3e8fcd
  V2 ARM live-runtime session-binding repair
```

Scientific methodology did **not** change. The currently imported production
runtime therefore cannot legitimately execute under the older
implementation-byte freeze. This artifact is the current executable runtime
freeze.

```text
CURRENT_EXECUTABLE_RUNTIME_FREEZE = this artifact
```

## Freeze semantics

The freeze commit is a docs/test descendant of the reviewed runtime. It
necessarily has a new HEAD and tree. This freeze does **not** claim that the
docs-only descendant itself was the exact code HEAD reviewed independently.

It freezes the implementation identity below, resolved from git objects at
that commit — not from working-tree bytes, not from a branch name, and not
from a caller-supplied digest.

```text
REVIEWED_IMPLEMENTATION_HEAD = c1d6acc9f3db3b35f06a02d7fb2361b8d4ea69c5
REVIEWED_IMPLEMENTATION_TREE = 67f19c997d7480f77ef741e2e2715c06cf3e8fcd

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact does not depend on a circular
self-hash of its own freeze-commit digest.

## Independent review verdict

```text
IMPLEMENTATION_REVIEW_VERDICT = GO_FOR_NEW_IMPLEMENTATION_FREEZE
```

## Authority chain

Inspectable from tracked repository state:

```text
approved post-wiring runtime commit
  c1d6acc9f3db3b35f06a02d7fb2361b8d4ea69c5
  tree 67f19c997d7480f77ef741e2e2715c06cf3e8fcd
    → exact implementation bytes (git blob + SHA256 below)
    → exact frozen V2 methodology authority (prereg + A001 + A003 + A004)
    → exact frozen V1 inherited TCB (five files)
    → historical 33/33 freeze preserved unmodified
```

Amendment_002 is **rejected historical authority** and **cannot govern
executable science**. It is retained unmodified as historical evidence.
Amendment_003 supersedes it. Amendment_004 amends Amendment_003. Production
derivation binds Amendment_003 + Amendment_004 only.

```text
V2_PREREG_HEAD            = ada237edc330b44bc412332e263f124757919e93
V2_PREREG_TREE            = ba1c0873879b7ea8556c3e238f8b962b91da6dc2
AMENDMENT_001_HEAD        = d8f0a996bc4341d0cbe01a1a061130b889ed5e75
AMENDMENT_001_TREE        = 09dca9b1240a43d5de9de0dadf32d27e00e7eaea
AMENDMENT_002_HEAD        = f84607594f4459f8ee1cbd14a7ab16294d586301
AMENDMENT_002_TREE        = 810f0a987e4a3dda1fc128905772727c0dcafee9
AMENDMENT_002_STATUS      = REJECTED_HISTORICAL_AUTHORITY
AMENDMENT_002_GOVERNS     = false
AMENDMENT_003_HEAD        = dfba85d2bfbb4bc3f9f3c34ea87dc3ae82a2dd18
AMENDMENT_003_TREE        = c0b4c00dd701eb262de021f34481161a7afe1f6f
AMENDMENT_004_HEAD        = df5dcde63581198d4766fa662de89eae3e7c461e
AMENDMENT_004_TREE        = 95814ae17922c399350200a4f2b55b1021113442
APPROVED_METHODOLOGY_HEAD = df5dcde63581198d4766fa662de89eae3e7c461e
APPROVED_METHODOLOGY_TREE = 95814ae17922c399350200a4f2b55b1021113442

V2_POLICY_REVIEWED_HEAD   = a310837bab4ee60c7495cca3bdb476abdc58a041
V2_POLICY_REVIEWED_TREE   = b15c4102b01514ff73e1728aec072eda9b528815
V2_POLICY_FREEZE_HEAD     = f96197d109fc22c12e4c8ba19715d67c65187c0e
V2_POLICY_FREEZE_TREE     = ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5
```

## Frozen implementation identity (byte-identical to reviewed HEAD)

```text
scripts/research/harness_synthetic_edge_calibration_v2_inherited_ladder.py
  git_blob = b6be00edf4e42460fb03a29266fcc0ff0564dd2b
  SHA256   = e3ef3801da5a200c43b3f3e14c84045c9f7bf52cc85e0d8f5f43a4e087591193
  size     = 37038
  unchanged since historical 33/33 implementation = YES

scripts/research/harness_synthetic_edge_calibration_v2_production.py
  git_blob = 7c89f4c9159fcf5b2c639bc5de31b17885b951b5
  SHA256   = 3d002c3ac42507d3845f527c4bfe530dcb04d142a3d846dad6cd4d0619ab04ba
  size     = 66686
  unchanged since historical 33/33 implementation = NO
  change class = authorization_security_repairs_only
```

## Frozen V2 policy / freeze dependency (unchanged)

```text
scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py
  git_blob = ac4ee082405e5291c7b093ba407f1a41203cb752
  SHA256   = 36336e0d6e1006a11d04911f91034898e6b5d8a52cb370fd83a2a1bdd19a2289
  size     = 42588

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json
  git_blob = ad72a2092118e07540fb977a9d748aca8354c2b5
  SHA256   = 64a5dfb99411940658a69ce7b6b0339851158c2a987ad12b94bb1fbf96fce2ad
  size     = 3813
```

## Frozen V1 TCB identity (byte-identical; not rewritten)

```text
LIB        SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
RUNNER     SHA256 = 0a5e577cc3797b018e9912865b7c3e385908764dc6cb36a6555626205855432a
AUTH       SHA256 = 0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507
PRODUCTION SHA256 = 9e784ecdcbd53ae4128d803d9325c8ff0f6db49ce70a0a63b13c4fc6a548a4ed
WORKER     SHA256 = 9aee03fdae012f9054c59adc4cea8072b88493521456fb6141ced926961c886e
```

## Canonical V2 plan

```text
CANONICAL_V2_PLAN_SHA256 = 7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800
CANONICAL_WORLD_COUNT    = 3200
```

Derived by `canonical_v2_plan()` at the reviewed implementation commit
(`FROZEN_V1_PRODUCTION_GRID` + `FROZEN_V2_RANK_POLICY`). Not a tracked plan
file.

## Known non-blocking limitations (recorded, not repaired)

```text
MINOR-1: load_v2_inherited_ladder_authority() currently lacks memoization
         and may incur repeated git/JSON work at production scale.

MINOR-2: full mint_v2_result cannot currently be exercised with ADEQUATE
         FINAL_OVERALL without reaching the already-disclosed
         visibility-blocked sibling ids.

PREEXISTING-DIRECT-ENTRYPOINT-RESERVATION:
  evaluate_v2_production_world / run_canonical_v2_production_grid do not
  require a committed reservation; session entrypoints do. Recorded as
  pre-existing technical debt. This freeze does not redesign that split.

VISIBILITY_LIMITATION = UNRESOLVED_FAIL_CLOSED
  sentinel = V2VisibilityStatisticUnavailable
```

These are **not** methodology changes and are **not** authorization to repair
them in this freeze unit.

## Freeze flags

```text
implementation_frozen = true

production_armed = false
production_executed = false
result_minted = false
world_records_created = false
authority_consumed = false
arm_created = false
execution_authorized = false
canonical_3200_run_started = false

READY_FOR_ARM_CREATION = NO
READY_FOR_CANONICAL_3200_RUN = NO
```

## What remains unauthorized

- V2 production ARM
- canonical 3200-world execution
- RESULT minting
- WORLD_RECORDS creation
- reservation consumption
- B2-06 scientific execution
- 2025 validation
- 2026 out-of-sample
- repairing MINOR-1 / MINOR-2
- resolving the visibility gap
- rewriting the historical 33/33 freeze

Next required step: `INDEPENDENT_V2_POST_WIRING_FREEZE_REVIEW`.
