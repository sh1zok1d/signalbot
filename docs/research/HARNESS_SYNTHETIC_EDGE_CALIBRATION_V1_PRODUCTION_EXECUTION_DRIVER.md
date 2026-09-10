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
    production path spawns HISTORICAL_RECOMPUTE_MODE through the existing
    isolated-child bootstrap (python -I -B -P, stdlib-only pre-import
    checks, root file/package shadow checks, worktree=HEAD, frozen lib/prereg)
    the child independently:
        proves executing scientific/production blobs match execution_head
        derives the frozen 3200-world plan and seeds internally
        recomputes all 3200 worlds
        compares canonical WORLD_RECORDS evidence against that recomputation
        recomputes aggregates and all derived scientific fields
        reconstructs the expected core and compares it exactly
    the parent treats a bound child success proof as the recomputation
    result and does not re-run or override science in-process
    there is no in-process fallback
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

## Production RESULT is recomputed from frozen execution, not WORLD_RECORDS trust

A production RESULT names its execution commit, but naming a legitimately armed
execution does not make its scientific payload authoritative. Tracked
WORLD_RECORDS are retained evidence / cached output, not self-authenticating
authority. Aggregates, Wilson intervals, verdicts, bands, floors, and
`mechanical_conclusion` are not historical inputs.

Authoritative `verify_bound_result_from_tracked_authority` of a production
RESULT does **not** recompute science in the caller process. It spawns
`HISTORICAL_RECOMPUTE_MODE` through the existing `#115` isolated-child
bootstrap (`python -I -B -P`, stdlib-only pre-import checks, root file and
package shadow checks, worktree=HEAD, frozen lib/prereg). The parent does not
supply an evaluator, plan, seeds, aggregates, record bodies, or module-path
authority. There is no in-process fallback. The isolated child:

- starts from that protected fresh-process/import boundary;
- independently verifies the requested historical execution identity;
- loads exact historical RESULT and WORLD_RECORDS blobs from git objects;
- proves the executing lib/runner/auth/production bytes equal the git objects
  at `execution_head`, so recomputation cannot silently run current-HEAD science
  or a parent-process monkeypatch;
- derives the frozen 3200-world plan and seeds internally;
- independently recomputes all 3200 frozen-plan worlds through
  `_evaluate_planned_world_body` (no reroll; invalid worlds stay in the
  denominator);
- constructs canonical WORLD_RECORDS from those recomputed records and refuses
  any difference from the tracked artifact;
- recomputes `world_set_sha256`, `record_digest_chain`, aggregates, Wilson
  intervals, specificity/power verdicts, SMALL bands, TRUE_DISCOVERY band,
  visibility/model floors, the materiality-only diagnostic,
  `incomplete_execution`, `observed_world_count`, and `mechanical_conclusion`
  from the independently generated records;
- reconstructs the expected canonical RESULT core and compares it exactly.

The parent accepts only a minimal machine-readable success proof bound to
`execution_head`, `run_identity`, RESULT digest/size, WORLD_RECORDS
digest/size, and the recomputed WORLD_RECORDS digest. Malformed, missing, or
duplicate child output fails closed. Durable claims require this isolated
verification first; there is no alternate claim path.

### Verification cost

Authoritative historical verification performs full 3200-world
recomputation (`FULL_3200_RECOMPUTATION`) and is intentionally expensive. On
current hardware it may take many hours. It is synchronous. Spot-check
mode is diagnostic only. Spot-check cannot validate or mint durable
production claims. Operators must not replace full verification with
spot-check because of runtime cost.

A first-and-only self-consistent fabricated WORLD_RECORDS + RESULT pair on a
legitimate freeze → ARM → execution topology is refused because the isolated
child's genuine recomputation does not reproduce the tracked records. Parent
monkeypatches of `_evaluate_planned_world_body`, `aggregate_planned_worlds`,
or `planned_production_jobs` cannot authorize that pair while on-disk bytes
remain unchanged. Durable claims are constructed only after that full
isolated recomputation succeeds, and they explicitly bind RESULT and
WORLD_RECORDS digest/size plus execution/terminal identity.

A sampled spot-check may exist only as a non-authoritative diagnostic. It
cannot mint or validate a durable claim and is not derived from `run_identity`
as cryptographic authenticity.

The canonical WORLD_RECORDS artifact is:

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_WORLD_RECORDS.json`

The worker emits those exact bytes on stdout alongside the RESULT. The operator
persists the captured bytes without regenerating records or recomputing
science. A production RESULT without a tracked WORLD_RECORDS artifact fails
closed.

## Execution status

```text
canonical_production_driver_implemented = true
post_commit_result_verification = true
production_result_scientific_payload_rederived = true
production_result_world_records_bound = true
authoritative_historical_verification = FULL_3200_RECOMPUTATION
authoritative_historical_verification_uses_fresh_child = true
historical_recompute_mode = historical-recompute
full_historical_verification_is_intentionally_expensive = true
spot_check_cannot_validate_or_mint_durable_claims = true
tracked_world_records_are_evidence_not_authority = true
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
