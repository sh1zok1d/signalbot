# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production execution driver

**Status:** `PRODUCTION_EXECUTION_DRIVER_IMPLEMENTED_UNARMED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Not a RESULT. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This unit completes the canonical production execution path on top of the
frozen #115 durability/aggregation layer. Production remains unarmed. This HEAD
does not run the 3200-world calibration and does not mint a production RESULT.

## Sequence

```text
C_reviewed_driver
    exact independently-reviewed implementation

↓

C_driver_freeze
    docs/metadata-only descendant
    records reviewed implementation identity and exact reviewed production SHA256

↓

C_arm
    immediate child of C_driver_freeze
    authorizes exact parent
    modifies NO execution-authority bytes

↓ canonical execution
```

`reviewed_implementation_head` must be a strict ancestor of the authorized
parent. ARM cannot self-bless `reviewed_implementation_head == parent`.
Future ARM verification reads the tracked driver-freeze artifact at the
authorized parent rather than trusting caller-updated ARM fields.

This repair unit does **not** add the live freeze artifact. The actual freeze
comes after OPUS closes this repair.

No further code-changing commit is required between a later ARM and the
canonical run.

Successful complete execution emits a machine-readable stdout envelope
`kind=COMPLETE_RESULT` containing the canonical RESULT bytes and the exact
canonical WORLD_RECORDS bytes. Crash/partial emits `kind=PARTIAL_NOT_RESULT`.
RESULT and WORLD_RECORDS are not written into the worktree.

## RESULT verification authority models

RESULT verification has two distinct functions. They do not silently switch
authority models.

```text
verify_bound_result_document(document, records)
    LIVE / execution-context
    re-derives the expected core from current HEAD, worktree, and
    caller-supplied records

verify_bound_result_from_tracked_authority(repo_root, result_document_or_path)
    TRACKED / historical
    reads execution_head from the RESULT core itself
    loads execution-authority blobs from that exact commit via git objects
    re-verifies ARM/freeze topology at execution time
    loads the tracked WORLD_RECORDS artifact from git objects, not the worktree
    recomputes record evidence, aggregates, and all derived scientific fields
    reconstructs the expected core and compares it exactly
    current HEAD need not be armed
```

Caller-supplied execution commits cannot authorize historical verification.
After a later RESULT commit `C_result`, `production_monte_carlo_arm_authorized`
at current HEAD is correctly false. Historical verification still proves that
`C_arm` was correctly armed for its freeze parent and execution bytes.

Captured canonical RESULT bytes → tracked RESULT commit → historical RESULT
verification → `durable_result_claim_from_tracked_authority()` is the complete
#115-compatible claim path. The helper returns a claim document; it does not
write the worktree. Duplicate/conflicting terminal RESULT blobs are refused.

A post-RESULT rerun refuses because the terminal production RESULT already exists
(one-shot consumed), not merely because current HEAD is unarmed. First
execution still requires ARM.

## Historical ARM #116

`#116` HEAD `940d85bf58673396c6c0cc05ce2134a2e2e92809` remains historical
evidence that the parent-authorizing ARM mechanism works. It is **not**
merged into this branch.

```text
OPUS verdict = REPAIR_REQUIRED
Reason = ARM mechanism sound, sequencing invalid
Status = REJECTED_NOT_MERGED / SUPERSEDED_BY_DRIVER_FIRST_SEQUENCE
production execution = NO
RESULT = NO
authority consumption = NO
```

This unit starts from frozen #115 HEAD
`502a62ddee0a3106967b21f0095be7e1629a56b2` / tree
`f21570983530f785d85639554741f3dd82164278`.

## Canonical driver

`run_canonical_production_execution()` is the only production driver. It:

1. verifies exact executed production authority using #115 machinery
2. requires production ARM authorization
3. acquires/uses #115 durable reservation semantics
4. obtains the frozen production grid
5. enumerates exactly `planned_production_jobs()`
6. requires exactly 3200 planned worlds
7. evaluates each world through the frozen production evaluator
8. preserves every invalid world in the denominator
9. never rerolls a failed/invalid world
10. aggregates through frozen aggregation logic
11. forces incomplete-execution semantics already frozen in #115
12. persists partial/crash state using #115 semantics
13. mints exactly one immutable final RESULT only after invariants hold
14. persists claim/RESULT using #115 commit-mediated durability
15. consumes one-shot authority only through the existing durable state
    transition (tracked RESULT at HEAD)

#115 remains authoritative for reservation/claim/result/run_identity. This
unit does not create a second durability system.

## RESULT mint authority

`mint_final_result` no longer accepts caller-supplied records. A fabricated
complete 3200-record set cannot mint.

Final RESULT can be minted only from records produced by the current verified
canonical execution session. The driver creates a module-private in-process
capability (`object()` identity) after executed-authority verification, ARM
verification, reservation acquisition, and exact `run_identity`
establishment. Callers cannot construct that capability. Tokens, UUIDs,
dicts, kwargs, and public constructors are not proof.

The capability is not a replacement for tracked durability. It only proves that
the records came through this canonical verified execution session.

## Fixture driver

`run_canonical_fixture_driver` exercises the same orchestration with an explicit
tiny non-production plan. It cannot encode the frozen 3200-world grid or
production N `{2500, 5000, 10000}`. Tests may use disposable ARM fixtures.
They must not weaken production guards.

## Future ARM machine checks

Because `production.py` changed in this driver unit, future ARM verification
now machine-checks material contract fields:

- `authorized_run_count == 1`
- `scope == "production_synthetic_calibration_only"`
- `production_only_scope == true`
- `authorization_consumed == false`
- `descendant_implementation_change_authorized == false`
- `real_market_data_access_authorized == false`
- `other_hypothesis_authorized == false`
- `B2_06_scientific_execution_authorized == false`
- `validation_2025_authorized == false`
- `oos_2026_authorized == false`
- `authorized_grid` exactly equals the frozen grid

Future ARM must also bind the independently reviewed driver implementation:

```text
reviewed_implementation_head / reviewed_implementation_tree
execution_authority_sha256.production == SHA256(reviewed production.py)
parent execution-authority bytes == reviewed execution-authority bytes
```

A caller may not keep a reviewed identity whose `production.py` bytes differ
from the authorized parent by rewriting ARM digests or reviewed fields.

This unit does **not** add a live ARM artifact.

## Identity

`production_durability_identity()` reports the actual verified ARM state. It
does not grant authority. Absent ARM reports unarmed. A valid disposable ARM
reports armed. Malformed ARM fails closed. Identity must not say UNARMED while
the canonical ARM verifier says armed.

## Production RESULT scientific payload is recomputed from WORLD_RECORDS

A production RESULT names its execution commit, but naming a legitimately armed
execution does not make its scientific payload authoritative. Aggregates,
Wilson intervals, verdicts, bands, floors, and `mechanical_conclusion` are
not historical inputs. Historical verification of a production-shaped RESULT:

- checks the protected literals exactly — `production_calibration_executed`
  true, `production_monte_carlo_arm_authorized` true, and
  `real_market_data_access_authorized`, `B2_06_scientific_execution_authorized`,
  `validation_2025_authorized`, `oos_2026_authorized` all false — and refuses a
  core that declares `fixture` or `not_a_production_result`;
- loads the tracked sibling WORLD_RECORDS artifact from git objects at HEAD,
  not from the worktree and not from RESULT-declared aggregates;
- verifies canonical path, digest, size, kind, execution identity, frozen grid,
  and the exact 3200-job plan in canonical order;
- preserves invalid worlds, refuses missing/duplicate/extra jobs, and
  recomputes `world_set_sha256` and `record_digest_chain` from those records;
- recomputes production aggregates from those records, then every derived
  scientific field: per-arm successes/n, Wilson intervals, specificity and
  power verdicts, SMALL bands, TRUE_DISCOVERY band, visibility and model
  floors, the materiality-only diagnostic, `incomplete_execution`,
  `observed_world_count`, and `mechanical_conclusion`;
- reconstructs the expected canonical RESULT core and compares it exactly.

The canonical WORLD_RECORDS artifact is:

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_WORLD_RECORDS.json`

The worker emits those exact bytes on stdout alongside the RESULT. The operator
persists the captured bytes without regenerating records or recomputing
science. A production RESULT without a tracked WORLD_RECORDS artifact fails
closed. A first-and-only RESULT whose aggregates were rewritten to a different
self-consistent payload is refused while the original WORLD_RECORDS remain.

## Execution status

```text
canonical_production_driver_implemented = true
post_commit_result_verification = true
production_result_scientific_payload_rederived = true
production_result_world_records_bound = true
production_monte_carlo_arm_authorized = false
ACTUAL_PRODUCTION_EXECUTION_RUN = NO
PRODUCTION_RESULT_MINTED = NO
AUTHORITY_CONSUMED = NO
B2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
ARTIFACTS_ROOT_PACKAGE_ACTIVATED = NO
```

No tracked live ARM artifact authorizes this HEAD. Frozen scientific lib and
prereg bytes are unchanged.
