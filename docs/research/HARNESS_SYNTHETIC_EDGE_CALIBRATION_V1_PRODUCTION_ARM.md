# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production execution ARM

**Status:** `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNUSED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**ARM ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_ARM`

**Not a RESULT. Not B2-06, 2025, or 2026 authorization. Not real-market research.**

This unit adds the minimal tracked ARM authority that unlocks exactly one
canonical production attempt of the already-frozen synthetic calibration
instrument. It does not rewrite frozen prereg or scientific lib bytes. It does
not rewrite the #115 production-durability implementation. It does not execute
the 3200-world calibration. It does not mint a RESULT. It does not consume
production authority.

## Parent-authorizing ARM semantics

ARM is not a commit/tree fixed point of its own HEAD.

The ARM commit `C_arm` authorizes its exact parent execution/freeze commit
`C_exec`:

```text
HEAD == C_arm
parent(HEAD) == authorized_execution_commit
tree(parent(HEAD)) == authorized_execution_tree
```

```text
AUTHORIZED_PARENT_COMMIT = 502a62ddee0a3106967b21f0095be7e1629a56b2
AUTHORIZED_PARENT_TREE    = f21570983530f785d85639554741f3dd82164278
```

That parent is the #115 implementation freeze HEAD. It is a docs/ledger
descendant of the OPUS-reviewed implementation:

```text
REVIEWED_IMPLEMENTATION_HEAD = d5277c42141a26948b195afe3d4ad30030151855
REVIEWED_IMPLEMENTATION_TREE = 7ab4178f222ecf8a2b5c8bf7d7bec9279fa3cf89
```

A descendant of `C_arm` is not armed. An ancestor ARM cannot arm a later
descendant. Extra implementation-authority byte changes between parent and ARM
fail closed.

## Bound authority

Tracked ARM artifact:

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`

The artifact binds:

- exact authorized parent commit and tree
- frozen production module bytes
- frozen scientific lib SHA256 `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`
- prereg JSON SHA256 `78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708`
- prereg MD SHA256 `a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3`
- frozen 3200-world production grid identity
- `authorized_run_count = 1`
- calibration `unit_id = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`
- production-only synthetic scope

It explicitly does **not** authorize:

- B2-06 scientific execution
- real-market research
- 2025 validation
- 2026 out-of-sample
- any other hypothesis
- any descendant implementation change

## One-shot semantics

This ARM permits exactly one canonical production attempt.

Existing #115 durability semantics remain authoritative for:

- deterministic run identity
- reservation
- claim
- crash/partial handling
- result persistence
- duplicate/conflicting attempts
- recovery

This unit does not invent a parallel execution system. It only unlocks the
frozen existing ARM seam.

```text
production_monte_carlo_arm_authorized = true
authorized_run_count = 1
production_calibration_executed = false
production_result_minted = false
authorization_consumed = false
B2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

## Execution remains unrun

This HEAD may be recognized as armed. Independent OPUS review of the exact
ARM HEAD is still required before the real 3200-world production calibration
is invoked.

The #115 isolated worker still fail-closes after ARM recognition with
`armed production Monte Carlo is not part of this durability unit` because this
unit must not change execution-authority bytes (`lib`, runner, auth,
production). Changing that leftover refuse would invalidate parent-byte ARM
equality.

Canonical `--run-production-grid` is therefore not invoked in this unit.
`evaluate_production_world` remains the frozen world-evaluation seam and is
not called against the live checkout.

## `artifacts` allowlist caveat

`artifacts` remains in the pinned isolated-bootstrap root allowlist. It is
not a tracked top-level package and is not imported in the verified execution
chain. This unit does not activate, import, or create an `artifacts` root
package. Any future unit which makes `artifacts` a real/imported root package
must explicitly re-review the pre-import allowlist authority boundary.
