# MARKET-06 — Implementation Refreeze (post red-team repair)

Status: `IMPLEMENTATION_REPAIRED_AND_REFROZEN_OUTCOME_BLIND`
Date: 2026-09-21

This refreeze supersedes
`MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json`, which
remains **historical evidence** for the pre-repair commit it describes.

## Bound authority

- Repaired implementation head: `378e8fd710040c5b4bd2471379b2ce4446ce80f2`
- Repaired implementation tree: `37f2c6ffa0802aca27757288d7b9e19837c96e3a`
- Live prereg freeze: `e2d543eadb5425473b6d4b8d24c177c1d7ae7930`
  (content `6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59`, **unamended**)
- Dataset: `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`
- Snapshot: `e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68`
- Durable evidence root:
  `f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f`
- Run identity:
  `d0fd9934f77843a45ccc6823ee1b454a256c5c45a50a88fd570dd7436fbe7d97`

`freeze_commit_head` is the sentinel `UNSET_UNTIL_THIS_COMMIT`: a docs-only
freeze commit cannot embed its own SHA. The repaired implementation commit
is recorded exactly in `implementation_head`, and that sentinel is never
that value.

## Module inventory bound by this freeze

| module | sha256 |
|---|---|
| `market_06_cross_venue_dislocation_authority.py` | `968cd24521ed…5bde07a171` |
| `market_06_cross_venue_dislocation_parsers.py` | `471fe3ff04b2…fe92c3cd32` |
| `market_06_cross_venue_dislocation_bootstrap.py` | `773b7631f768…9e98a63ec7` |
| `market_06_cross_venue_dislocation_evaluator.py` | `3e54a92b4713…41bcb12236` |
| `market_06_cross_venue_dislocation_runner.py` | `041217a9670b…0d7ffb49eb3` |
| `market_06_year_stratified_circular_mbb.py` | `e8545dab9c3c…38a9a082da3` |
| `market_06_canonical_reconstruction.py` | `2550596411ca…5904a7aca5` |
| `market_06_execution_lifecycle.py` | `dd218d253b31…1e5236f54d` |
| `market_06_git_authority.py` | `7788b850faa4…ebb033f84de` |

Exact full digests are in the JSON twin, together with the bound test
inventory.

## Lifecycle position

```
IMPLEMENTATION_REPAIRED_AND_FROZEN   <- you are here
  -> RED_TEAM_PASS
  -> ARM payload / ARM-bound freeze
  -> one-shot execution reservation
  -> canonical execution
  -> deterministic RESULT persistence
  -> second canonical execution refused
```

`future_arm_can_authorize_same_frozen_implementation = true` and
`post_arm_scientific_code_change_required = false`: a later tracked ARM
authenticates these exact module bytes and mints an execution permit
without editing the evaluator, parsers, bootstrap, reconstruction, or
scientific runner logic.

## Explicit state

`market_06_armed = false`, `market_06_executed = false`,
`market_06_arm_created = false`, `market_06_reservation_created = false`,
`market_06_result_created = false`,
`market_06_execution_authorized = false`,
`real_canonical_execution_refused = true`,
`scientific_outcomes_inspected = false`,
`protected_2025_opened = false`, `protected_2026_opened = false`.

This is not an ARM and not a RESULT.

Next lifecycle state: `MARKET_06_IMPLEMENTATION_REPAIR_RED_TEAM_REVIEW`.
