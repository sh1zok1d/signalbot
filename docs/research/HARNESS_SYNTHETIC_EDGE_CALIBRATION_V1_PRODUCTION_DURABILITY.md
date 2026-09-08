# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production durability contract

**Status:** `PRODUCTION_DURABILITY_IMPLEMENTED_UNARMED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Not a RESULT. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This document records the production durability, aggregation, and result-persistence
layer above the frozen scientific primitives. It does not rewrite frozen prereg or
scientific lib bytes. It does not execute the 3200-world calibration.

## Closed residuals

- **R1 stale import:** canonical production execution spawns an isolated Python
  interpreter (`python -I -B -P -c` bootstrap) that inserts the exact resolved repo
  root into `sys.path`, imports the canonical package module
  `scripts.research.harness_synthetic_edge_calibration_v1_production`, and
  re-verifies exact HEAD/tree plus execution-authority bytes inside that process
  immediately before evaluation. User site, sitecustomize/usercustomize,
  inherited `PYTHONPATH`, and `scripts/research` script-directory shadowing cannot
  authorize or substitute execution. Restoring on-disk bytes after a stale parent
  import cannot authorize execution from the stale in-process objects.
- **R2 cross-checkout replay:** `run_identity` is a pure function of tracked
  authority at the exact execution commit. Deleting a local untracked reservation
  cannot mint a distinct identity. Another clone/worktree of the same commit can
  only reproduce the same identity. This contract does **not** claim global
  process exclusion.

## ARM authority (parent execution commit)

ARM is not a commit/tree fixed point of its own HEAD.

An ARM artifact tracked in commit `C_arm` authorizes its **parent** execution
commit `C_exec`:

- `HEAD == C_arm`
- ARM is tracked at `HEAD:docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`
- `parent(HEAD) == authorized_execution_commit`
- `tree(parent(HEAD)) == authorized_execution_tree`
- listed `execution_authority_sha256` digests match parent blobs for frozen lib,
  runner, auth, production executor, prereg JSON, and prereg MD
- HEAD execution-authority bytes equal parent execution-authority bytes
  (the arming commit may add ARM/docs only)

A descendant of `C_arm` is not armed. An ancestor ARM cannot arm a later descendant.
This unit does **not** add a live ARM artifact.

## Invalid worlds and incomplete execution

Invalid planned worlds remain in the exact planned denominator. They are not
rerolled or replaced. If any planned world is invalid, or any planned job is
missing:

- `incomplete_execution = true`
- mechanical conclusion is `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- no methodology PASS/FAIL conclusion may be emitted
- `mint_final_result` refuses to mint a terminal RESULT

Extra `(scenario_id, n_rows, world_index)` identities that are not in
`planned_production_jobs()` fail closed.

## Result envelope

Canonical finalization starts from the exact complete world records. Aggregates,
reservation identity, claim identity, and `world_set_sha256` are derived
internally. Caller-supplied aggregates or digests cannot mint a RESULT.

```text
core        = canonical scientific result payload
core_sha256 = sha256(canonical_json_bytes(core))
core_size   = len(core_bytes)

envelope = {
  core: ...,
  core_sha256: ...,
  core_size: ...
}
```

`core_sha256` / `core_size` hash the core, not the envelope. The persisted
artifact digest/size, if any, is maintained by the external claim/persistence
layer and is not embedded self-referentially inside the core.

Verification re-derives the core from the supplied canonical world records and
tracked git authority. A self-checking document is not authority.

## Persistence lifecycle

```text
execution commit
  → ARM commit (later unit; not in this HEAD)
  → compute artifact outside the tracked tree (in-memory / staging)
  → claim/result commit persists the exact artifact
  → verification reads the artifact from the Git object DB at that commit
```

Writing an uncommitted RESULT or partial into a canonical tracked path is not
executable authority and dirties the freeze. Recovery reads
`HEAD:canonical_path` from git objects and binds the artifact's named execution
commit/tree/`run_identity`/grid/digest/size/world-set identity. Current HEAD
may be a later claim/result commit; the named execution commit must be an
ancestor of HEAD.

## Canonical tracked paths

| Role | Path | Present in this unit |
|---|---|---|
| reservation | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json` | absent |
| claim | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` | absent |
| result | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESULT.json` | absent |
| partial | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_PARTIAL.json` | optional diagnostic only |
| arm | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json` | absent; later explicit arming unit |

## Execution status

```text
production_monte_carlo_arm_authorized = false
production_calibration_executed = false
production_result_minted = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

The #114 local one-shot reservation is superseded on any HEAD that tracks the
production durability module. Production remains fail-closed until a separate
later arming unit.
