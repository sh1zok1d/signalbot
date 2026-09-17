# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3 — one-shot canonical ARM

**Status:** `ARMED_FOR_ONE_CANONICAL_V3_PRODUCTION_EXECUTION`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3`

**Canonical ARM artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.json)

**Not a RESULT. Not an execution. Not a reservation. Not B2-06, MARKET, 2025,
2026, or V4 authorization.**

This document is a docs/authority-artifact-only ARM record. It authorizes
exactly one canonical 1600-world V3 confirmatory execution against the
implementation-freeze parent below. It does not rewrite frozen prereg,
implementation, RNG, V1 lib, or selector bytes. It does not execute
`world_index 10000..10399`. It does not mint WORLD_RECORDS or RESULT. It
does not create a reservation. Creating this ARM does not consume it.

## Topology

```text
ACCEPTED IMPLEMENTATION 70673673f5bc0108e6bcf2aaf55a762ebc49940a
        ↓
IMPLEMENTATION FREEZE / PRE-ARM HEAD = 76f2100715b67799231eab8132cd856823fdf3f8
IMPLEMENTATION FREEZE TREE           = dd59466b02c56f101764cb17052a6d5eb514b945
        ↓
ARM (this commit)

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

Runtime verification derives freeze F as this ARM's own immediate parent.
Caller-supplied freeze/implementation identity is not authority.

No confirmatory, RNG, prereg, or V1 lib bytes change between the freeze
parent and this ARM.

## Authorized scope

```text
authorized_unit            = HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3
authorized_execution_kind  = synthetic_confirmatory_monte_carlo
authorized_run_identity    = ce66442985a637f05508c980257f5ca8b869df15e2b94b87d1110c3ef75fd69f
authorized_world_count     = 1600
authorized_run_count       = 1
one_shot                   = true
lifecycle                  = AUTHORIZED_UNUSED
consumption_path           = canonical_reservation_then_execution_only
```

Canonical grid (already frozen; not redefined here):

```text
scenarios       = EASY, MODERATE, NULL, NONSTATIONARY_TRAP
world_index     = 10000..10399
worlds/cell     = 400
n_rows          = 5000
B               = 999
feature         = F03
Wilson/acceptance = exact frozen one-sided integer boundaries
```

## One-shot semantics

- tracked at the canonical ARM path
- exact-authority-bound to freeze parent `76f21007` / tree `dd59466b` and
  run identity `ce664429…`
- initially `AUTHORIZED_UNUSED`
- consumable only through the canonical reservation then execution path
- not reusable after legitimate consumption
- not redirectable to another run identity, grid, or implementation
- not consumable by disposable fixture execution
- ARM creation and ARM validation do **not** consume it

## Not authorized / not done

```text
authorization_consumed = false
reservation_created    = false
canonical_execution_started = false
result_minted          = false
world_records_created  = false
default_v4             = false
b2_06_execution_authorized = false
```
