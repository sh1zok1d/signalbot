# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — authorization-boundary review packet

**Status:** `ONE_SHOT_SYNTHETIC_EXECUTION_AUTHORIZATION_READY_FOR_FOCUSED_REDTEAM`

**Audience:** independent adversarial authorization-boundary re-review

**Not a RESULT. Not a methodology pass. Not an edge claim. Not an authorization freeze.**

## Identity

- base SHA: `a1c9eda737bc527cee3752e0e32f798c08283544`
- branch: `research/harness-synthetic-edge-calibration-v1-one-shot-authorization`
- previous reviewed HEAD: `f5ea3da66765855b803cd0921f4903f5c5d57c05`
- HEAD / tree: filled at review time from the exact repair commit
- frozen prereg JSON SHA256: `78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708`
- frozen prereg MD SHA256: `a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3`
- frozen implementation review commit: `c996ba08c49961afde5daba2bd97832fded4725a`
- frozen implementation tree: `f8c239aafca06f807c02c38ed1a726d1dda9ee31`
- implementation freeze commit: `65b2ee2675dab4235ddbab9da7f4ee425f94d600`
- authorization artifact: `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_EXECUTION_AUTHORIZATION.json`
- authorization artifact blob SHA256: `29dd1bbabce33ba53d0f88d44e35fbb500b736cc4e007c000d85c40fba097436`

## OPUS closure table

| Finding | Repair | Status |
|---|---|---|
| BLK-1 executed-byte binding | Clean `verify_git_freeze` plus executing/worktree/HEAD identity for the three production-authority paths; HEAD scientific lib must equal frozen `c996ba0` bytes, not merely ancestry | CLOSED |
| MAJ-1 one-shot reservation | Atomic `O_CREAT\|O_EXCL` reservation bound to authorization/prereg/execution/grid/run identity; uncommitted claim/reservation consume; crash/failure becomes `FAILED_CONSUMED`; no automatic retry | CLOSED |
| MAJ-2 proof/grid forgery | Production plan and seam re-derive the frozen grid from tracked/module authority; proof objects cannot authorize or override seed/N/scenarios | CLOSED |
| MIN-1 proof replay | `AuthorizedExecutionBoundaryReached` exposes diagnostics only; `.proof` is `None`; executors refuse caller-supplied proof objects | CLOSED |
| MIN-2 test gaps | Adversarial regressions for worktree/descendant/skip-worktree tamper, sequential/concurrent reservation, failure consumption, path substitution, and forged proofs | CLOSED |

## Authority flow

```text
tracked authorization
        +
exact prereg bytes
        +
exact executed implementation bytes
        +
clean verified checkout
        ↓
atomic reservation
        ↓
production boundary
        ↓
EXECUTED_CONSUMED / FAILED_CONSUMED
```

Scientific authority is re-derived at the production boundary from frozen module constants and the tracked prereg. A `VerifiedProductionAuthorization` record is diagnostic only. `_MINT` is not a security boundary.

## Production execution authority

| Path | Role | Binding |
|---|---|---|
| `scripts/research/harness_synthetic_edge_calibration_v1_lib.py` | frozen scientific implementation | executing == worktree == HEAD == `12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51` at reviewed commit `c996ba08c49961afde5daba2bd97832fded4725a` |
| `scripts/research/harness_synthetic_edge_calibration_v1.py` | repaired CLI | executing == worktree == HEAD == tracked `execution_authority.runner_sha256` |
| `scripts/research/harness_synthetic_edge_calibration_v1_auth.py` | repaired authorization implementation | executing == worktree == HEAD == tracked `execution_authority.auth_sha256`; not bound to superseded PR #114 SHA |

The scientific lib production lock `run_frozen_production_grid` again always raises `SYNTHETIC_EXECUTION_NOT_AUTHORIZED`. Production verification/reservation is `auth.run_authorized_production_grid`.

## One-shot semantics

```text
NOT_AUTHORIZED
AUTHORIZED_UNUSED
RESERVED
EXECUTED_CONSUMED
FAILED_CONSUMED
```

This PR keeps the tracked artifact at `AUTHORIZED_UNUSED`. It does not create a reservation, claim, or RESULT on the live checkout.

`authorized_run_count = 1`. Consumption begins when the production entrypoint obtains the local exclusive reservation at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json`. A later tracked claim at `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` is additional durable success evidence.

Worktree existence of reservation or claim is sufficient to refuse a second start. Uncommitted files are not ignored.

### Unavoidable machine/crash assumptions

- `O_CREAT|O_EXCL` is atomic local exclusion on one checkout/filesystem, not an atomic Git commit.
- SIGKILL after exclusive create may leave `RESERVED` instead of `FAILED_CONSUMED`; both are non-reusable.
- Deleting the reservation file, using a fresh clone, or reverting a later committed reservation can reopen that checkout.
- Intended operator workflow: never delete reservation/claim evidence; never automatically retry; a failed attempt requires a new explicit authorization.

## Runner authority flow

1. Public `run_frozen_production_grid` remains a frozen scientific lock and rejects production.
2. `run_authorized_production_grid` rejects any args/kwargs.
3. Repo root is derived from the tracked module path, not a caller authority path.
4. Refuse if reservation or claim exists in worktree or HEAD.
5. `verify_git_freeze` requires exact HEAD, clean worktree, and rejects skip-worktree/assume-unchanged.
6. Authorization JSON is read only as `HEAD:<canonical path>`.
7. Verify unit, schema, unused lifecycle, run count 1, and closed real-market/B2-06/2025/2026 flags.
8. Verify HEAD prereg blob SHA256 matches the artifact and executed prereg bytes.
9. Verify reviewed implementation commit is an ancestor of HEAD **and** that current HEAD/executed scientific lib bytes equal the frozen reviewed lib identity.
10. Verify runner/auth HEAD+executed bytes equal tracked `execution_authority` hashes.
11. Verify authorized grid equals frozen production authority (3200 worlds, seed 20260908, 500/999/500, block 50).
12. Atomically create the reservation bound to those identities.
13. Re-derive the 3200-world identity plan from frozen authority, never from a proof object.
14. Enter the unique Monte Carlo seam, which this PR does not arm.

## Negative boundary tests

Covered in `tests/research/test_harness_synthetic_edge_calibration_v1_authorization.py`:

- missing artifact, malformed JSON, wrong unit/prereg/implementation identity, modified grid
- `authorized=True` / `force=True` / alternate path kwargs
- environment variables
- untracked worktree file cannot substitute HEAD
- worktree tamper of lib, runner, and auth
- descendant scientific lib change while frozen implementation remains ancestor
- skip-worktree / assume-unchanged
- sequential second reservation
- concurrent reservation exactly one winner
- failure after reservation stays consumed
- uncommitted claim consumes
- reservation bound to wrong authorization
- reservation/claim path substitution
- forged `VerifiedProductionAuthorization` / `_MINT` cannot alter grid
- production plan re-derives frozen grid
- production seam rejects grid mismatch
- captured boundary does not export reusable proof
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
