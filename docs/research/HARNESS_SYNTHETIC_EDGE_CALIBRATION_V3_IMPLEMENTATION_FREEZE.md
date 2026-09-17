# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3 — implementation freeze

**Status:** `FROZEN_BEFORE_V3_ARM`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE`

**Not a RESULT. Not an ARM. Not Monte Carlo authorization. Not a reservation.
Not B2-06, MARKET, 2025, 2026, or V4 authorization.**

This document is a docs/test/authority-plumbing IMPLEMENTATION FREEZE record.
It freezes the exact independently accepted V3 confirmatory implementation
identity and binds the already-frozen prereg canonical execution spec so the
next unit can arm exactly one canonical V3 execution. It does not rewrite
frozen prereg, RNG, V1 inherited scientific authority, or selector semantics.
It does not arm. It does not execute `world_index 10000..10399`. It does not
mint WORLD_RECORDS or RESULT.

Canonical machine-readable twin:
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.json`.

## Freeze semantics

The freeze commit is a docs/ledger/test/authority-helper descendant of the
reviewed implementation. It necessarily has a new HEAD and tree. This freeze
does **not** claim that the docs-only descendant itself was the exact code
HEAD independently reviewed.

It freezes the implementation identity below, resolved from git objects at
that commit — not from working-tree bytes, not from a branch name, and not
from a caller-supplied digest.

```text
REVIEWED_IMPLEMENTATION_HEAD = 70673673f5bc0108e6bcf2aaf55a762ebc49940a
REVIEWED_IMPLEMENTATION_TREE = e94e18cb900a44824b96dee1d4b6cbb574c95e5a

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact does not depend on a circular
self-hash of its own freeze-commit digest.

Historical prereg freeze `fd21ed7f` remains historical and unchanged.

No confirmatory, RNG, prereg, prereg-freeze, or V1 lib bytes are changed
between the reviewed implementation and this freeze except this freeze
documentation, the pre-ARM authority helper, its focused tests, and
status/ledger index plumbing.

## Independent review verdict

```text
IMPLEMENTATION_REVIEW_VERDICT = IMPLEMENTATION_ACCEPTED
F1 = CLOSED
F2 = CLOSED
F3 = CLOSED
```

## Authority chain

```text
prereg freeze
  fd21ed7f8cf8279d367d7a7cf3f1740398d73883
  tree a854578e6d88ef2d6f546824f3196e33f4e95e55
    → original implementation
      e1b750286c9552a5b853a6ac3c68f4d9dffefdc1
        → accepted implementation (this freeze's parent)
          70673673f5bc0108e6bcf2aaf55a762ebc49940a
          tree e94e18cb900a44824b96dee1d4b6cbb574c95e5a
            → exact confirmatory / RNG / prereg / V1 lib / selector hashes
```

## Frozen implementation identity (byte-identical to reviewed HEAD)

```text
scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py
  git_blob = 85314b5bfbfdb1eacf819b4e71bc0e2af283a616
  SHA256   = 38a494917dcf721b828a7c3f885d4c60ab6df437003abc0c71e510e33b4b0505
  size     = 24059

scripts/research/harness_synthetic_edge_calibration_v3_rng.py
  git_blob = 1a5bdd5b9660bf939ef8669e34cd76d3c9f15865
  SHA256   = 8bd6aef151139bc1afd4d890d7ba293b1adec5cf66b405dde677eccb3b06d698
  size     = 2325
```

## Frozen prereg identity (unchanged historical authority)

```text
PREREG_FREEZE_HEAD = fd21ed7f8cf8279d367d7a7cf3f1740398d73883
PREREG_CONTENT_HEAD = 543687fe79ba2e6254e879b0574e58a1909c15fe

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md
  SHA256 = ab03c68a3781c13cf5ba74d08d6c212dd9da42b87f7642700cf79294147918e0
  size   = 29885

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json
  SHA256 = 194fed692018560661879dc67e14a4d139c79978fc0dac00aa6e0f934bd399b5
  size   = 35373
```

## Frozen inherited V1 scientific authority (byte-identical; not rewritten)

```text
scripts/research/harness_synthetic_edge_calibration_v1_lib.py
  SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
  size   = 37636
```

## Frozen arch 8.0.0 selector authority (already pinned by prereg)

```text
package              = arch==8.0.0
source_file          = arch/bootstrap/base.py
source_file_sha256   = 104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21
public_entry_point   = arch.bootstrap.optimal_block_length
public_entry_sha256  = b70543178ffb368cb22490f508de9bf35152eb9882ca4b66f26d338c5f1f4f12
implementing_fn      = _single_optimal_block
implementing_sha256  = 355cfaf81a09a42f32dd643d2cd5fd39a78d16faec1e4cc06a79a83d729b7421
```

## Canonical execution spec (from prereg only; not consumed)

```text
scenarios            = EASY, MODERATE, NULL, NONSTATIONARY_TRAP
world_index          = 10000..10399 inclusive
worlds/cell          = 400
planned_worlds       = 1600
n_rows               = 5000
B                    = 999
feature              = F03
Wilson               = one-sided z=1.6448536269514722
acceptance cells     = EASY / MODERATE / NULL / NONSTATIONARY_TRAP
                       with frozen integer PASS/FAIL/INDETERMINATE boundaries
```

Binding this spec does not execute it and does not reserve it.

## Pre-ARM machinery

`scripts/research/harness_synthetic_edge_calibration_v3_authority.py` is
plumbing for the next ARM unit. It:

- verifies freeze/prereg/implementation/RNG/V1/selector bytes against this
  freeze;
- derives a deterministic scientific run identity from tracked frozen
  authority only;
- refuses caller kwargs, env/path substitution, and canonical execution;
- reports `v3_armed = false` because no ARM artifact exists.

Freeze and ARM remain separable. This unit does not issue one-shot
authorization.

## Freeze flags

```text
V3_IMPLEMENTATION_FROZEN        = YES
V3_PRE_ARM_BINDING_COMPLETE     = YES
V3_RUN_AUTHORIZED               = NO
V3_ARMED                        = NO
DEFAULT_V4                      = NO
B2_06_EXECUTION_AUTHORIZED      = NO
```

## What remains unauthorized

- V3 ARM
- canonical 1600-world execution (`world_index 10000..10399`)
- reservation
- WORLD_RECORDS / RESULT minting
- B2-06 scientific execution
- MARKET / 2025 validation / 2026 OOS
- V4

Next required step: `V3_ONE_SHOT_CANONICAL_ARM` (a later unit).
