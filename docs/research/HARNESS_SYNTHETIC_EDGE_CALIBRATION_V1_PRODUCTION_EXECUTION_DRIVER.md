# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production execution driver

**Status:** `PRODUCTION_EXECUTION_DRIVER_IMPLEMENTED_UNARMED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Not a RESULT. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This unit completes the canonical production execution path on top of the
frozen #115 durability/aggregation layer. Production remains unarmed. This HEAD
does not run the 3200-world calibration and does not mint a production RESULT.

## Sequence

```text
C_driver  (this unit)
    production implementation fully complete
    canonical 3200-world driver exists
    production remains unarmed

↓ independent OPUS review / freeze

C_arm
    docs/authority-only child
    authorizes exact C_driver/freeze parent
    modifies NO execution-authority bytes

↓ canonical execution
```

No further code-changing commit is required between a later ARM and the
canonical run.

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

## Execution status

```text
canonical_production_driver_implemented = true
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
