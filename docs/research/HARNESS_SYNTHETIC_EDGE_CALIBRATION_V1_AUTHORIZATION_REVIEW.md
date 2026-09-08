# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — authorization freeze

**Status:** `AUTHORIZATION_FROZEN_BEFORE_PRODUCTION_EXECUTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Not a RESULT. Not a methodology pass. Not an edge claim. Not Monte Carlo authorization.**

This document records the reviewed one-shot authorization implementation freeze. It does not rewrite frozen scientific semantics, does not arm the production Monte Carlo seam, and does not consume the unused one-shot.

## Frozen authorization authority

```text
reviewed authorization HEAD = 7b308f6520fc8b71e9e51c8cf0013e0edc77874c
reviewed authorization tree = 842a5a8f1a7ea73d08e4d88e2ab58ca39bda42c8
base = a1c9eda737bc527cee3752e0e32f798c08283544
branch = research/harness-synthetic-edge-calibration-v1-one-shot-authorization
focused independent review verdict = GO_FOR_AUTHORIZATION_FREEZE
new blockers = 0
new majors = 0
new minors = 2
exact reviewed-head CI run = 34239284806
exact reviewed-head CI conclusion = success
```

The authorization implementation bytes reviewed above are frozen before any production synthetic execution. The tracked one-shot JSON remains byte-frozen at this reviewed HEAD:

- artifact: `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`
- artifact blob SHA256: `29dd1bbabce33ba53d0f88d44e35fbb500b736cc4e007c000d85c40fba097436`

Frozen scientific implementation identity remains:

- reviewed implementation commit: `c996ba08c49961afde5daba2bd97832fded4725a`
- reviewed implementation tree: `f8c239aafca06f807c02c38ed1a726d1dda9ee31`
- lib SHA256: `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`
- prereg JSON SHA256: `78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708`
- prereg MD SHA256: `a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3`

```text
synthetic_execution_authorized = true
authorized_run_count = 1
production_calibration_executed = false
authorization_consumed = false
production_monte_carlo_arm_authorized = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

## OPUS closure table

| Finding | Status |
|---|---|
| BLK-1 executed-byte binding | CLOSED |
| MAJ-1 local/concurrent reservation safety | CLOSED FOR CURRENT UNARMED STAGE |
| MAJ-2 proof/grid forgery | CLOSED |
| MIN-1 proof replay | CLOSED |
| MIN-2 original adversarial coverage | CLOSED |

Final focused verdict: `GO_FOR_AUTHORIZATION_FREEZE`.

This freeze does not repair the two newly documented residual MINORs below. They are not accepted as permanent assumptions.

## Residual findings — mandatory preconditions before Monte Carlo may be armed

These residuals are current-stage review debt. Production execution MUST NOT be armed until they are closed.

### RESIDUAL-R1 — cross-checkout durability

Current reservation is local to a checkout/filesystem.

Demonstrated:

- the same tracked authorization can independently reach `RESERVED` in another clone/worktree;
- deleting the local reservation permits local replay.

This is acceptable ONLY because the Monte Carlo seam remains unarmed.

Required future closure before production execution:

`same authorization -> at most one globally durable production attempt`

via durable tracked reservation/claim and/or an explicitly authoritative single-runner protocol.

Until closed: `cross_checkout_durable_one_shot = open`

### RESIDUAL-R2 — stale in-process import

Demonstrated:

- a tampered module can be imported;
- disk bytes restored;
- disk/HEAD verification passes;
- stale tampered Python function objects remain in memory.

The current canonical fresh-subprocess CLI does not expose this as a production exploit, but it must be closed before any actual Monte Carlo execution path is armed.

Required future closure should enforce a fresh-process execution boundary or equivalent proof that verified bytes are the actual function objects executing.

Until closed: `stale_import_execution_identity = open`

## Hard gate

```text
production_monte_carlo_arm_authorized = false
```

Production execution MUST NOT be armed until all of the following are true:

- `cross_checkout_durable_one_shot = closed`
- `stale_import_execution_identity = closed`
- `production aggregation/persistence contract = implemented and reviewed`

Do not silently convert these residual findings into accepted permanent assumptions. Closing them requires an explicit later repair/review, not this freeze commit.

## Authority flow at freeze

```text
tracked authorization
        +
exact prereg bytes
        +
exact executed implementation bytes
        +
clean verified checkout
        ↓
atomic local reservation
        ↓
unarmed production boundary
```

Scientific authority is re-derived at the production boundary from frozen module constants and the tracked prereg. A `VerifiedProductionAuthorization` record is diagnostic only. `_MINT` is not a security boundary.

Local `O_CREAT|O_EXCL` excludes concurrent processes on one checkout. That is sufficient only for the current unarmed stage. It is not globally durable one-shot provenance.

## Production execution authority paths

| Path | Role | Binding at reviewed HEAD |
|---|---|---|
| `scripts/research/harness_synthetic_edge_calibration_v1_lib.py` | frozen scientific implementation | executing == worktree == HEAD == `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51` |
| `scripts/research/harness_synthetic_edge_calibration_v1.py` | authorization CLI | executing == worktree == HEAD == tracked `execution_authority.runner_sha256` |
| `scripts/research/harness_synthetic_edge_calibration_v1_auth.py` | authorization implementation | executing == worktree == HEAD == tracked `execution_authority.auth_sha256` |

`lib.run_frozen_production_grid` remains a fail-closed scientific lock. Production verification/reservation is `auth.run_authorized_production_grid`. The unique Monte Carlo seam is unarmed.

## Production execution status

```text
authorization implementation frozen = YES
synthetic_execution_authorized = true
authorized_run_count = 1
production_calibration_executed = false
authorization_consumed = false
production_monte_carlo_arm_authorized = false
caller-controlled authorization bypass = false
production grid caller-mutable = false
local/concurrent second-run refusal implemented = true
cross-checkout durable one-shot = open
stale-import execution identity = open
real-market access possible = false
B2-06 opened = false
2025 touched = false
2026 touched = false
```
