# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production durability contract

**Status:** `PRODUCTION_DURABILITY_IMPLEMENTED_UNARMED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Not a RESULT. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This document records the production durability, aggregation, and result-persistence
layer above the frozen scientific primitives. It does not rewrite frozen prereg or
scientific lib bytes. It does not execute the 3200-world calibration.

## Closed residuals

- **R1 stale import:** canonical production execution spawns a fresh Python
  interpreter and re-verifies exact HEAD/tree plus execution-authority bytes inside
  that process immediately before evaluation. Restoring on-disk bytes after a
  stale import cannot authorize execution from the stale in-process objects.
- **R2 cross-checkout replay:** `run_identity` is a pure function of tracked
  authority at the exact execution commit. Deleting a local untracked reservation
  cannot mint a distinct identity. Another clone/worktree of the same commit can
  only reproduce the same identity. This contract does **not** claim global
  process exclusion.

## Canonical tracked paths

| Role | Path | Present in this unit |
|---|---|---|
| reservation | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESERVATION.json` | absent |
| claim | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_EXECUTION_CLAIM.json` | absent |
| result | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_RESULT.json` | absent |
| partial | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_PARTIAL.json` | optional diagnostic only |
| arm | `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json` | absent; later explicit arming unit |

A descendant commit is not armed by an ancestor ARM artifact. Arming requires
`production_monte_carlo_arm_authorized=true` bound to that commit's exact HEAD and
tree.

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
