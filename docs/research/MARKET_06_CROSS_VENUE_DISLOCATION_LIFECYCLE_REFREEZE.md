# MARKET-06 — Lifecycle Refreeze (post L10/L11/L12 repair)

Status: `LIFECYCLE_REPAIRED_AND_REFROZEN_OUTCOME_BLIND`
Date: 2026-09-21

Supersedes `MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_REFREEZE.json`
(implementation `378e8fd`, freeze `6fc1b62`), which remains historical
evidence for the commit it describes.

## Bound authority

- Repaired implementation head: `0ff43e6f9dff4e32c65f85466ea9a3c48b1f01e1`
- Repaired implementation tree: `b1f0c02d0cece83be5b19a482d1b823590f5c05f`
- Live prereg freeze: `e2d543eadb5425473b6d4b8d24c177c1d7ae7930` (**unamended**)
- Canonical data source commit: `e2d543eadb5425473b6d4b8d24c177c1d7ae7930`
  (caller override impossible)
- Dataset `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`, snapshot
  `e0403e40…183e68`, durable root `f4b9e16a…0cdc6f`
- Run identity:
  `28cfa4884b638f91dd1074e93673ed37215d42334eef1746c89967f4a356a88f`

The run identity changed because it is a content hash over the scientific
and lifecycle module bytes, which this repair modified. No scientific
definition changed.

## Authority chain

```
CLAIM  ->  RESERVATION  ->  ARM  ->  IMPLEMENTATION FREEZE
  C           R              A              F
```

No lifecycle artifact contains its own commit SHA; each is authoritative
because of the commit it is read from. `A` must be an ancestor of `R`, and
`R` an ancestor of `C`.

Canonical science requires the durable tracked **CLAIM**, not merely an
ARM. `future_arm_can_authorize_same_frozen_implementation = true` and
`post_arm_scientific_code_change_required = false`.

## Module inventory

Ten modules are bound by SHA-256: authority, parsers, bootstrap, evaluator,
runner, year-stratified MBB, canonical reconstruction, execution lifecycle,
git authority, and result persistence. Exact digests are in the JSON twin,
with the bound test inventory.

## Explicit state

`market_06_armed = false`, `market_06_arm_created = false`,
`market_06_reservation_created = false`, `market_06_claim_created = false`,
`market_06_result_created = false`,
`market_06_execution_authorized = false`,
`real_canonical_execution_refused = true` (`MARKET_06_NO_TRACKED_CLAIM`),
`scientific_outcomes_inspected = false`, 2025/2026 unopened.

This is not an ARM, not a reservation, not a claim, and not a RESULT.

Next lifecycle state: `MARKET_06_FINAL_LIFECYCLE_RED_TEAM`.
