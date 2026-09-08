# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — authorization-boundary review packet

**Status:** `ONE_SHOT_SYNTHETIC_EXECUTION_AUTHORIZATION_READY_FOR_REDTEAM`  
**Audience:** independent adversarial authorization-boundary review  
**Not a RESULT. Not a methodology pass. Not an edge claim.**

## Identity

- base SHA: `a1c9eda737bc527cee3752e0e32f798c08283544`
- branch: `research/harness-synthetic-edge-calibration-v1-one-shot-authorization`
- HEAD / tree: filled at review time from the exact authorization commit
- frozen prereg JSON SHA256: `78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708`
- frozen prereg MD SHA256: `a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3`
- frozen implementation review commit: `c996ba08c49961afde5daba2bd97832fded4725a`
- frozen implementation tree: `f8c239aafca06f807c02c38ed1a726d1dda9ee31`
- implementation freeze commit: `65b2ee2675dab4235ddbab9da7f4ee425f94d600`
- authorization artifact: `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`
- authorization artifact blob SHA256: `5edaf8bbae45bb7aabdca2c07df152a55b9ea441d48da9ff9b15d7c755fd28fb`

## One-shot semantics

```text
NOT_AUTHORIZED
AUTHORIZED_UNUSED
CONSUMED
```

This PR creates `AUTHORIZED_UNUSED` only.

```text
AUTHORIZED_UNUSED
        ↓
production execution (later ceremony; not this PR)
        ↓
immutable RESULT / execution claim
        ↓
AUTHORIZATION_CONSUMED
```

`authorized_run_count = 1`. Durable consumption is a later tracked claim at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json`. That file is intentionally absent here.

## Runner authority flow

1. Public `run_frozen_production_grid` rejects any args/kwargs.
2. Repo root is derived from the tracked module path, not a caller authority path.
3. Authorization JSON is read only as `HEAD:<canonical path>`.
4. Verify unit, schema, unused lifecycle, run count 1, and closed real-market/B2-06/2025/2026 flags.
5. Verify HEAD prereg blob SHA256 matches the artifact.
6. Verify reviewed implementation commit is an ancestor of HEAD and its tree/lib SHA256 match the artifact.
7. Verify authorized grid equals frozen production authority (3200 worlds, seed 20260908, 500/999/500, block 50).
8. Refuse if the durable claim blob exists at HEAD.
9. Mint `VerifiedProductionAuthorization` with a process-local token.
10. Build the 3200-world identity plan without simulation.
11. Enter the unique Monte Carlo seam, which this PR does not arm.

## Negative boundary tests

Covered in `tests/research/test_harness_synthetic_edge_calibration_v1_authorization.py`:

- missing artifact
- malformed JSON
- wrong unit ID
- wrong prereg identity
- wrong implementation identity
- modified production grid
- `authorized=True` / `force=True` / alternate path kwargs
- environment variables
- untracked worktree file cannot substitute HEAD
- consumed claim refuses a second run
- real-market / B2-06 / 2025 / 2026 flags cannot be flipped true
- fixture envelope unchanged

## Production execution status

```text
synthetic_execution_authorized = true
authorized_run_count = 1
production_calibration_executed = false
authorization_consumed = false
caller-controlled authorization bypass = false
production grid caller-mutable = false
second-run refusal implemented = true
real-market access possible = false
B2-06 opened = false
2025 touched = false
2026 touched = false
```
