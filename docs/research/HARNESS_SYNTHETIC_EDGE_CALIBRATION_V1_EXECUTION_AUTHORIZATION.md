# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — one-shot execution authorization

**Status:** `AUTHORIZATION_FROZEN_BEFORE_PRODUCTION_EXECUTION`

**Machine authority:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json)

**Freeze record:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_AUTHORIZATION_REVIEW.md`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_AUTHORIZATION_REVIEW.md)

This document is not a RESULT, not a methodology verdict, and not market evidence. The tracked JSON bytes are unchanged by the authorization freeze.

```text
reviewed authorization HEAD = 7b308f6520fc8b71e9e51c8cf0013e0edc77874c
reviewed authorization tree = 842a5a8f1a7ea73d08e4d88e2ab58ca39bda42c8
base = a1c9eda737bc527cee3752e0e32f798c08283544
OPUS verdict = GO_FOR_AUTHORIZATION_FREEZE
implementation frozen = YES
authorization implementation frozen = YES
synthetic one-shot execution authorized = YES
authorized_run_count = 1
production execution performed = NO
authorization consumed = NO
production_monte_carlo_arm_authorized = NO
real-market access = NO
B2-06 execution = NO
2025 validation = NO
2026 OOS = NO
```

Permission is exactly one production calibration of the already frozen instrument, and that production path remains unarmed.

Authority is the conjunction of:

1. the tracked authorization JSON blob in Git HEAD;
2. exact frozen prereg bytes;
3. exact executed implementation bytes from this checkout;
4. a clean verified Git freeze;
5. an atomic local reservation created before any Monte Carlo computation.

Caller kwargs, environment variables, alternate paths, minted proof objects, and historical ancestry alone cannot authorize.

## Hard gate before Monte Carlo may be armed

```text
production_monte_carlo_arm_authorized = false
```

Production execution MUST NOT be armed until:

- `cross_checkout_durable_one_shot = closed`
- `stale_import_execution_identity = closed`
- production aggregation/persistence contract = implemented and reviewed

See residual findings RESIDUAL-R1 and RESIDUAL-R2 in the freeze record. They are not accepted permanent assumptions.

## Production execution authority paths

These paths are the production execution authority. Runtime requires executing bytes, worktree bytes, and HEAD blobs to be identical, and requires those SHA256 identities to match the tracked authorization artifact.

- `scripts/research/harness_synthetic_edge_calibration_v1_lib.py` — frozen scientific implementation; HEAD bytes must equal reviewed commit `c996ba08c49961afde5daba2bd97832fded4725a` / SHA256 `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`
- `scripts/research/harness_synthetic_edge_calibration_v1.py` — authorization CLI/entrypoint; SHA256 pinned in the authorization artifact
- `scripts/research/harness_synthetic_edge_calibration_v1_auth.py` — authorization implementation; SHA256 pinned in the authorization artifact

The scientific lib remains the exact reviewed implementation bytes. Authorization wiring lives in `auth.py` and the CLI. `lib.run_frozen_production_grid` remains a fail-closed scientific lock.

## One-shot reservation

```text
AUTHORIZED_UNUSED
        ↓
atomic local reservation (O_CREAT|O_EXCL)
        ↓
RESERVED
        ↓
EXECUTED_CONSUMED
or
FAILED_CONSUMED
```

The canonical reservation path is `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json`. It is intentionally absent. Creating it consumes the local one-shot. A later immutable claim at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` is additional success evidence, not the first local consumption event.

Local reservation safety is closed for the current unarmed stage only. Cross-checkout durability remains open (RESIDUAL-R1). The Monte Carlo seam is reached after reservation and is not armed. This freeze does not run 3200 worlds.
