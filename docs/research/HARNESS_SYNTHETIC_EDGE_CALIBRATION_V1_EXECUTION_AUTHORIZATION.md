# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — one-shot execution authorization

**Status:** `ONE_SHOT_SYNTHETIC_EXECUTION_AUTHORIZATION_READY_FOR_FOCUSED_REDTEAM`

**Machine authority:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json)

This document is not a RESULT, not a methodology verdict, and not market evidence.

```text
implementation frozen = YES
synthetic one-shot execution authorized = YES
production execution performed = NO
authorization consumed = NO
real-market access = NO
B2-06 execution = NO
2025 validation = NO
2026 OOS = NO
```

Permission is exactly one production calibration of the already frozen instrument.

Authority is the conjunction of:

1. the tracked authorization JSON blob in Git HEAD;
2. exact frozen prereg bytes;
3. exact executed implementation bytes from this checkout;
4. a clean verified Git freeze;
5. an atomic local reservation created before any Monte Carlo computation.

Caller kwargs, environment variables, alternate paths, minted proof objects, and historical ancestry alone cannot authorize.

## Production execution authority paths

These paths are the production execution authority. Runtime requires executing bytes, worktree bytes, and HEAD blobs to be identical, and requires those SHA256 identities to match the tracked authorization artifact.

- `scripts/research/harness_synthetic_edge_calibration_v1_lib.py` — frozen scientific implementation; HEAD bytes must equal reviewed commit `c996ba08c49961afde5daba2bd97832fded4725a` / SHA256 `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51`
- `scripts/research/harness_synthetic_edge_calibration_v1.py` — repaired authorization CLI/entrypoint; SHA256 pinned in the authorization artifact
- `scripts/research/harness_synthetic_edge_calibration_v1_auth.py` — repaired authorization implementation; SHA256 pinned in the authorization artifact, not the superseded PR #114 bytes

The scientific lib is restored to the exact reviewed implementation bytes. Authorization wiring lives in `auth.py` and the CLI. `lib.run_frozen_production_grid` remains a fail-closed scientific lock.

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

The canonical reservation path is `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json`. It is intentionally absent from this PR. Creating it consumes the one-shot. A later immutable claim at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` is additional success evidence, not the first consumption event.

Invoking the production entrypoint obtains the reservation even though Monte Carlo remains unarmed. Automatic retry is not authorized. A crash after reservation does not return the authorization to `AUTHORIZED_UNUSED`.

### Unavoidable machine assumptions

Local `O_CREAT|O_EXCL` excludes concurrent processes on the same checkout/filesystem. It is not a Git commit and cannot by itself create durable remote provenance.

Documented limits of this contract:

- a SIGKILL after exclusive create may leave `RESERVED` rather than `FAILED_CONSUMED`; both states are non-reusable;
- deleting the reservation file, checking out a fresh clone, or reverting a later committed reservation can reopen the local checkout;
- the intended operator workflow never deletes reservation/claim evidence and never reruns the same authorization.

The Monte Carlo seam is reached after reservation and is not armed here. This PR does not run 3200 worlds.
