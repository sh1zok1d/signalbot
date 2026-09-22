# Heterogeneous family rotation V1

**Unit:** `HETEROGENEOUS_FAMILY_ROTATION_V1`  
**Kind:** hypothesis-generation policy freeze  
**Date:** 2026-09-22  
**Status:** `FROZEN`  
**Machine-readable record:** `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.json`

This freeze applies the already-recorded generation policy from
`PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED`. It does not
execute discovery cards, open 2025/2026, or create MARKET-07.

## Families

| ID | Name | This rotation |
|---|---|---|
| A | `CONDITIONAL_RISK_ABSTENTION` | `NOT_SELECTED_THIS_ROTATION` — D2 neighbors forbidden |
| B | `DIRECTIONAL_EXPECTATION` | `NOT_SELECTED_THIS_ROTATION` — near M05/M06 low priority |
| C | `PATH_MORPHOLOGY` | `NOT_SELECTED_THIS_ROTATION` — near D3 low priority |
| D | `RELATIVE_CROSS_ASSET_STRUCTURE` | `NOT_SELECTED_THIS_ROTATION` — rolling-corr neighbors low priority |
| E | `LIQUIDITY_EXECUTION_STATE` | **selected** as D7 |
| F | `REGIME_TRANSITION` | `DEFERRED_BLOCKER_UNRESOLVED` — D1 null-model blocker |
| G | `EVENT_RESPONSE_RECOVERY` | **selected** as D8 |
| H | `CROSS_SECTIONAL_OR_VENUE_STRUCTURE` | `DEFERRED_DATA_LIMITATION` — no true panel |
| I | `EXTERNALLY_DERIVED_BENCHMARK_MECHANISMS` | `DEFERRED_SOURCE_NOT_PINNED` |

First application: `DISCOVERY_SPRINT_02` with exactly two internal cards,
D7 (family E) and D8 (family G).

```
SCIENTIFIC_OUTCOMES_COMPUTED = false
MARKET_07_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
PRODUCT_BUILD_FROZEN = true
```
