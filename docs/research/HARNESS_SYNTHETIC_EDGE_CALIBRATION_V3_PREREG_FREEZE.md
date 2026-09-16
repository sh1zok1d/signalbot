# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3 — prereg freeze authority

**Status:** `FROZEN_BEFORE_V3_IMPLEMENTATION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE`

**Not a RESULT. Not an ARM. Not Monte Carlo execution. Not B2-06, 2025, or 2026 authorization.**

This document is a docs-only PREREG FREEZE record. It establishes that the exact, already-independently-reviewed and accepted V3 prereg bytes — `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` / `.json` at commit `4b7e0d6d` — are the sole scientific authority for V3 implementation and eventual execution. It does not modify those files, rewrite any scientific choice in them, touch frozen V1/V2 artifacts, implement V3, run V3 worlds, create a reservation, or create an ARM.

Canonical machine-readable twin: `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json`, committed at the stable path this and any future runtime looks for.

## Why this freeze

The V3 prereg content (estimand, Clark-West adjustment, full-time-axis joint stationary bootstrap, the now-exactly-bound Politis-White/Patton-Politis-White block-length selector, hard guards, aggregate acceptance rules, RNG/world-identity authority) was independently reviewed across two rounds and accepted at exact commit `4b7e0d6dfda1cb9475a610f51ccbec0906fd0133`. This document freezes that acceptance as a durable, git-anchored authority boundary, so implementation has no scientific discretion left.

```text
ACCEPTED_PREREG_CONTENT_HEAD = 4b7e0d6dfda1cb9475a610f51ccbec0906fd0133
ACCEPTED_PREREG_CONTENT_TREE = fe779fc37e31bd23700b6f70d476f4cb1249223d

PREREG_REVIEW_VERDICT = ACCEPTED

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain `UNSET_UNTIL_THIS_COMMIT` so this artifact never depends on a circular self-hash of its own freeze-commit digest — matching the existing `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.md` convention exactly. Binding is entirely to `ACCEPTED_PREREG_CONTENT_HEAD`/`TREE` and the blob hashes below, independently recomputed from that exact commit before this freeze was written (see Validation).

## Frozen prereg artifacts

```text
docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md
  SHA256 = 739247ef228c80988abd40ac60b095e0e4e9e5ee45f81761cb1e3aa846161085
  size   = 24208 bytes

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json
  SHA256 = 2d3a42e7fc9c91bf1b4bafaec01b2947b454e40151c47be9f2ff3f92a6e41617
  size   = 30734 bytes
```

Both recomputed directly from `git cat-file -p 4b7e0d6d:<path>` immediately before writing this freeze; both matched the accepted values exactly. Neither file's bytes are touched by this commit.

## Authority chain

```text
BASE_MAIN_HEAD_AT_DESIGN_START = 3339812a7ea30c7e325d83276f6ce4b5399afe50
PARENT_DESIGN_UNIT_HEAD        = 2759e09449e2ec4c041ea9ec433191c2bbbff9a1  (V3_CONFIRMATORY_SPEC.md, design-complete)

PREREG_CONTENT_COMMIT_CHAIN:
  2759e09  V3_CONFIRMATORY_SPEC.md closed for prereg review
  c4d4566  V3_PREREG.md/.json materialized (no scientific choice left unbound except the selector implementation)
  4b7e0d6  block-length-selector exact implementation authority bound (arch==8.0.0); accepted content frozen by this document
```

## Frozen dependencies already declared by the accepted prereg (cross-check only, not re-derived)

```text
FROZEN_V1_PRIMITIVE_SOURCE = scripts/research/harness_synthetic_edge_calibration_v1_lib.py
FROZEN_V1_PRIMITIVE_SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
FROZEN_V1_PRIMITIVE_SIZE   = 37636 bytes

V3_WORLD_IDENTITY_AUTHORITY:
  n_rows = 5000
  scenarios = EASY, MODERATE, NULL, NONSTATIONARY_TRAP
  world_index = 10000..10399 (400 per scenario; disjoint from V1/V2's 0..399)
  new_rng_namespace_token = "V3_CONFIRMATORY"
  identity function reused unmodified: world_identity(scenario_id, n_rows, world_index)

V2_EVIDENCE_BOUNDARY (reaffirmed, unchanged):
  v2_development_consumed = true
  v2_forbidden_as_v3_acceptance_evidence = true
  v2_canonical_result_sha256 = 761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0
```

## Freeze semantics

1. The prereg scientific payload is immutable authority.
2. Implementation may only implement the frozen payload.
3. Implementation cannot choose new scientific constants/algorithms.
4. Any required scientific change discovered during implementation invalidates execution authorization and requires an explicit pre-outcome amendment/re-freeze, not a silent edit.
5. No fresh V3 acceptance world may be inspected yet.
6. No execution reservation may be created yet.
7. No ARM may be created yet.
8. No MARKET/B2-06/2025-validation/2026-OOS access is authorized.
9. V2 worlds remain development-consumed and cannot become V3 acceptance evidence.
10. No selective rerun/rescue/reroll semantics change.

## Validation performed before this commit

- `git cat-file -p 4b7e0d6d:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` → SHA256 matched the expected value exactly.
- `git cat-file -p 4b7e0d6d:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json` → SHA256 matched the expected value exactly.
- `git merge-base --is-ancestor 4b7e0d6d HEAD` confirmed before proceeding; working tree was clean.
- No V1/V2 frozen scientific artifact is present in this commit's diff.
- No V3 module/test/implementation file is present in this commit's diff.

## Explicit state

```text
v3_design_complete = true
v3_prereg_materialized = true
v3_prereg_review_required = false
v3_prereg_frozen = true
v3_implementation_complete = false
v3_run_authorized = false
v3_armed = false
default_v4 = false
b2_06_execution_authorized = false
```

Implementation may now proceed mechanically against this frozen authority: every scientific constant, formula, and algorithm required is bound in the frozen artifacts above, with no remaining choice delegated to the implementer.
