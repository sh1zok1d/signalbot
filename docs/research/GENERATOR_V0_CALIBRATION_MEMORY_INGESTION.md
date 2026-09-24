# Generator V0 — calibration memory ingestion amendment

**Status:** `ACTIVE RECORD`  
**Date:** 2026-09-24  
**Mode:** offline, no provider calls  
**Source:** `GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.{json,md}`

Five cost/pipeline calibration cards are now durable prior-work signatures for
future generation. They remain **non-scientific fixtures**: no market outcomes
were tested and protected 2025/2026 data remain unopened.

| Calibration card | Stable memory signature | Governance state | Meaning |
|---|---|---|---|
| C001 | `GV0CAL-C001` | `CONSUMED` | already-generated participant-composition / variance-ratio mechanism; do not regenerate cosmetic/parameter neighbors |
| C002 | `GV0CAL-C002` | `CONSUMED` | already-generated perp-vs-spot price-discovery/DST mechanism |
| C003 | `GV0CAL-C003` | `DEFERRED_OR_BLOCKED` | causal-identification + confounding blocker; only an explicit blocker-resolving redesign may advance |
| C004 | `GV0CAL-C004` | `DEFERRED_OR_BLOCKED` | confounding blocker; only an explicit blocker-resolving redesign may advance |
| C005 | `GV0CAL-C005` | `CONSUMED` | already-generated listing-age cross-sectional mechanism |

## Role separation

The raw mechanism memory retains pipeline disposition and why a card was blocked.
The generator does not receive those fields. `BLIND_MECHANISM_MAP_V0` projects
only `ID, MECHANISM, INFORMATION_SOURCE, FUNCTION, TARGET_FAMILY` plus the same
neutral `REGION_STATE = PRIOR_WORK_SIGNATURE` for every signature.

The novelty critic receives `GOVERNANCE_REGION_AUTHORITY_V0`. Its existing
decision table is unchanged. Therefore future generation can avoid rediscovering
the same mechanism space without optimizing Opus toward Sol's PASS/REJECT labels.

## Stable IDs

Run-local candidate IDs such as `C001` are not used as durable memory IDs because
future campaigns reuse the Cxxx namespace. The stable prefix `GV0CAL-` prevents
identity collision while preserving the source-card mapping.

## Files updated

- `MECHANISM_MEMORY_V0.{json,md}`
- `BLIND_MECHANISM_MAP_V0.json`
- `GOVERNANCE_REGION_AUTHORITY_V0.json`
- embedded authority in `HYPOTHESIS_GENERATOR_V0_DESIGN.json`
- `GENERATOR_V0_CONTEXT_PINS.json`
- focused context tests

No provider/model routing, prompt, schema, selector, exactly-once, budget, or
protected-data rule changed. The 30-card architecture freeze remains in force.

`NO_LIVE_API_CALLS = true`  
`NO_SCIENTIFIC_STATUS = true`  
`MARKET_OUTCOMES_TESTED = false`  
`PROTECTED_DATA_OPENED = false`
