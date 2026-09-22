# Heterogeneous family rotation V2

**Unit:** `HETEROGENEOUS_FAMILY_ROTATION_V2`  
**Kind:** hypothesis-generation policy freeze  
**Date:** 2026-09-22  
**Status:** `FROZEN`  
**Machine-readable record:** `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.json`

This freeze re-evaluates families A–I after canonical D7. It does not
execute discovery cards, open 2025/2026, create MARKET-07, rerun D7, or
execute D8.

`HETEROGENEOUS_FAMILY_ROTATION_V1` remains the historical Sprint 02
policy. This file supersedes **routing only**.

`SIGNALBOT_MANDATE_V1.md` is **not** on `origin/main` at
`9b25131e92ab654e46175ddba34e8cccc1db6765`. It was read from draft PR
#197 (`docs/signalbot-mandate-v1-refresh`) as program philosophy. This
unit does not merge that PR.

## Program counters after D7

```
INTERNAL_DISCOVERY_CARDS_EXECUTED = 5
INTERNAL_PROMISING_PROTOTYPES     = 2
INTERNAL_DISCOVERY_WARNING        = null
INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = false
```

Completed internal cards: D2 `PROMISING_PROTOTYPE`, D3/D4/D5
`NO_USEFUL_STRUCTURE`, D7 `PROMISING_PROTOTYPE`. D1 remains deferred.
D6 remains external/deferred. D8 remains
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` and is **not** counted as
executed and is **not** a negative scientific result.

## D7 confirmation routing

```
D7_CONFIRMATION_CANDIDATE    = true
D7_CONFIRMATION_SELECTED_NOW = false
MARKET_07_CREATED            = false
```

The program continues heterogeneous discovery before spending
confirmatory cost. D2 and D7 should later be compared together with any
Sprint 03/04 prototype at the pre-automation research-maturity gate.

Family E is in **cooldown**. Do not select another IMPACT_PROXY
threshold, P85/P95/P99, 720h-window variant, 30m/2h/4h clone, or any
card whose primary rationale is “D7 worked”.

## Families

| ID | Name | This rotation |
|---|---|---|
| A | `CONDITIONAL_RISK_ABSTENTION` | `NOT_SELECTED_THIS_ROTATION` — D2 neighbors forbidden |
| B | `DIRECTIONAL_EXPECTATION` | `NOT_SELECTED_THIS_ROTATION` — near M05/M06 low priority |
| C | `PATH_MORPHOLOGY` | `NOT_SELECTED_THIS_ROTATION` — near D3 low priority |
| D | `RELATIVE_CROSS_ASSET_STRUCTURE` | `NOT_SELECTED_THIS_ROTATION` — rolling-corr neighbors low priority; D4 lead-lag still deferred |
| E | `LIQUIDITY_EXECUTION_STATE` | `COOLDOWN_AFTER_POSITIVE` — D7 consumed as discovery |
| F | `REGIME_TRANSITION` | `DEFERRED_BLOCKER_UNRESOLVED` — D1 null-model blocker |
| G | `EVENT_RESPONSE_RECOVERY` | `NOT_SELECTED_THIS_ROTATION` — must not rescue D8 |
| H | `CROSS_SECTIONAL_OR_VENUE_STRUCTURE` | **selected** as D9 (`VENUE_STRUCTURE` subfamily) |
| I | `EXTERNALLY_DERIVED_BENCHMARK_MECHANISMS` | `DEFERRED_SOURCE_NOT_PINNED` — diagnostic only; not an internal success |

A true cross-sectional panel is still absent. Family H is no longer
dismissed solely as “no panel”: `MARKET_06_OKX_BINANCE_FEASIBILITY_V0`
already supplies a point-in-time two-venue 5m surface
(snapshot `e0403e40…`, 2022-01-01 → 2025-01-01 exclusive).

Data unavailability does not erase a scientifically valuable family.
Sprint 03 nevertheless uses the already-available orthogonal H surface
rather than building new data infrastructure.

## Application

Exactly one internal card: `DISCOVERY_SPRINT_03` / D9.

```
SCIENTIFIC_OUTCOMES_COMPUTED = false
D9_EXECUTED = false
D9_SCIENTIFIC_OUTCOME_COMPUTED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
MARKET_07_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
PRODUCT_BUILD_FROZEN = true
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
```

CORE BTC parquet/raw scientific bytes are gitignored under `artifacts/`
and currently lack a verified durable object-storage restore path
despite frozen identity/hashes. That follow-up is recorded, not
implemented here.
