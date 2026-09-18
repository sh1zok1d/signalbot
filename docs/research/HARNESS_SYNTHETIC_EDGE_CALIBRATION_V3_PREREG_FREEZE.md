# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3 — prereg freeze authority

**Status:** `FROZEN_BEFORE_V3_IMPLEMENTATION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE`

**Not a RESULT. Not an ARM. Not Monte Carlo execution. Not B2-06, 2025, or 2026 authorization.**

This document is a docs-only PREREG FREEZE record. It establishes that the exact, amended, already-independently-accepted V3 prereg bytes — `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` / `.json` plus the new `harness_synthetic_edge_calibration_v3_rng.py` primitive, all at commit `543687fe` — are the sole scientific authority for V3 implementation and eventual execution. It does not modify those files, rewrite any scientific choice in them, touch frozen V1/V2 artifacts, implement V3's confirmatory statistic, run V3 worlds, create a reservation, or create an ARM.

Canonical machine-readable twin: `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.json`, committed at the stable path this and any future runtime looks for.

## Supersedes the original freeze — history preserved, not rewritten

```text
PREVIOUS_FREEZE_HEAD                = 4136f530378e91d545e2644a650f0a7a07a731c3
PREVIOUS_FREEZE_BOUND_CONTENT_HEAD  = 4b7e0d6dfda1cb9475a610f51ccbec0906fd0133
PREVIOUS_FREEZE_BOUND_CONTENT_TREE  = fe779fc37e31bd23700b6f70d476f4cb1249223d
```

`4136f530…` remains reachable, unmodified, valid historical evidence of the **pre-amendment** prereg text. It is not deleted, force-pushed over, or reinterpreted. This document supersedes it as the *current* scientific authority because, before any implementation, ARM, reservation, or V3 outcome existed, the pre-amendment text was found to be:

1. literally unimplementable (the frozen V1 `namespace_seed()` rejects the `"V3_CONFIRMATORY"` token the original text required), and
2. incomplete in one respect (`SE_hat`'s delta-degrees-of-freedom was unbound).

Both were closed by **Amendment 001** (`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` §16 / `amendment_history[0]` in the `.json`), classified `PRE_OUTCOME_CORRECTNESS_AND_SPEC_COMPLETENESS_AMENDMENT` — not outcome-driven, not a power/threshold repair, not a methodology redesign. Nothing else in the prereg changed.

```text
ACCEPTED_PREREG_CONTENT_HEAD = 543687fe79ba2e6254e879b0574e58a1909c15fe
ACCEPTED_PREREG_CONTENT_TREE = 50750efc5fae32b128c3c89c2b9df506d000323c

PREREG_REVIEW_VERDICT = ACCEPTED
AMENDMENT_STATUS = AMENDMENT_001_APPLIED_PRE_OUTCOME

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain `UNSET_UNTIL_THIS_COMMIT` so this artifact never depends on a circular self-hash of its own freeze-commit digest — matching the established convention exactly. Binding is entirely to `ACCEPTED_PREREG_CONTENT_HEAD`/`TREE` and the blob hashes below, independently recomputed from that exact commit before this freeze was written.

## Frozen prereg artifacts

```text
docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md
  SHA256 = ab03c68a3781c13cf5ba74d08d6c212dd9da42b87f7642700cf79294147918e0
  size   = 29885 bytes

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json
  SHA256 = 194fed692018560661879dc67e14a4d139c79978fc0dac00aa6e0f934bd399b5
  size   = 35373 bytes

scripts/research/harness_synthetic_edge_calibration_v3_rng.py
  SHA256 = 8bd6aef151139bc1afd4d890d7ba293b1adec5cf66b405dde677eccb3b06d698
  size   = 2325 bytes
  (new primitive introduced by Amendment 001; now part of frozen authority)
```

All three recomputed directly from `git cat-file -p 543687fe:<path>` immediately before writing this freeze; all matched. None of the three files' bytes are touched by this commit.

## Authority chain

```text
BASE_MAIN_HEAD_AT_DESIGN_START = 3339812a7ea30c7e325d83276f6ce4b5399afe50
PARENT_DESIGN_UNIT_HEAD        = 2759e09449e2ec4c041ea9ec433191c2bbbff9a1  (V3_CONFIRMATORY_SPEC.md, design-complete)

PREREG_CONTENT_COMMIT_CHAIN:
  2759e09  V3_CONFIRMATORY_SPEC.md closed for prereg review
  c4d4566  V3_PREREG.md/.json materialized
  4b7e0d6  block-length-selector exact implementation authority bound (arch==8.0.0)
  4136f53  ORIGINAL freeze of 4b7e0d6 (superseded; valid historical evidence)
  543687f  Amendment 001 (RNG namespace + SE ddof, pre-outcome); accepted content frozen by THIS document
```

## Frozen dependencies already declared by the accepted prereg (cross-check only, unchanged by Amendment 001)

```text
FROZEN_V1_PRIMITIVE_SOURCE = scripts/research/harness_synthetic_edge_calibration_v1_lib.py
FROZEN_V1_PRIMITIVE_SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
FROZEN_V1_PRIMITIVE_SIZE   = 37636 bytes

V3_WORLD_IDENTITY_AUTHORITY:
  n_rows = 5000
  scenarios = EASY, MODERATE, NULL, NONSTATIONARY_TRAP
  world_index = 10000..10399 (400 per scenario; disjoint from V1/V2's 0..399)
  new_rng_namespace_token = "V3_CONFIRMATORY"
  new_rng_namespace_function = v3_namespace_seed(world_seed_int, *context)
  identity function reused unmodified: world_identity(scenario_id, n_rows, world_index)

SE_HAT_CONVENTION (Amendment 001):
  ddof = 1  (sample standard deviation, Bessel's correction; numpy.std(theta_star, ddof=1))

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

- `git cat-file -p 543687fe:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md` → SHA256 matched.
- `git cat-file -p 543687fe:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.json` → SHA256 matched.
- `git cat-file -p 543687fe:scripts/research/harness_synthetic_edge_calibration_v3_rng.py` → SHA256 matched.
- `git merge-base --is-ancestor 4136f530 HEAD` and `git merge-base --is-ancestor 543687fe HEAD` both confirmed; working tree was clean.
- `pytest tests/research/test_harness_synthetic_edge_calibration_v3_rng.py` — 7/7 passing, proving existing V1/V2 namespace outputs and PCG64 stream prefixes are unchanged, and the new `V3_CONFIRMATORY` stream is deterministic and distinct.
- No V1/V2 frozen scientific artifact is present in this commit's diff.
- No V3 confirmatory-statistic module/test/implementation file is present in this commit's diff.
- No `WORLD_RECORDS`/`RESULT`/`RESERVATION`/`ARM` V3 artifact exists anywhere in the tree.

## Explicit state

```text
v3_design_complete = true
v3_prereg_materialized = true
v3_prereg_review_required = false
v3_prereg_frozen = true
v3_implementation_complete = false
v3_implementation_review_required = true
v3_run_authorized = false
v3_armed = false
default_v4 = false
b2_06_execution_authorized = false
```

Implementation may now proceed mechanically against this frozen authority: every scientific constant, formula, and algorithm required — including the RNG-namespace mechanism and the SE ddof convention — is bound in the frozen artifacts above, with no remaining choice delegated to the implementer. The eventual V3 confirmatory-statistic implementation still requires its own independent implementation review before any freeze/ARM of executable code, exactly as for V1/V2.
