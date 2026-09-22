# Discovery Sprint 03

**Unit:** `DISCOVERY_SPRINT_03_HETEROGENEOUS_CARD_DEFINITION`
**Parent policy:** `HETEROGENEOUS_FAMILY_ROTATION_V2`
**Date:** 2026-09-22
**Status:** `DEFINED` (pre-outcome amendment)
**Memory:** `docs/research/MECHANISM_MEMORY_V0.{json,md}`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_03.json`

Outcome-blind card definition only. Three internal cards. No scientific
outcomes. No D7 rerun. No D8 execution. No 2025/2026. No MARKET-07.

```
INTERNAL_CARDS = D9, D10, D11
SPRINT03_SELECTION_INCOMPLETE = false
D9_CHOSEN_ESTIMAND = RELATIVE_RESOLUTION_ATTRIBUTION
D9_ALGEBRAIC_IDENTIFICATION_FIXED = true
NEXT_UNIT = DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

The next unit may run cheap non-outcome feasibility and outcome-blind
implementation for DATA_READY cards (D9, D10), and pin the D11 calendar
without inspecting RV outcomes. It must **not** automatically build
heavy D7-style one-shot infrastructure per card.

## D9 estimand correction (pre-outcome)

The first PR #198 draft used

`RESOLUTION_IMBALANCE = PERP_LEG_CLOSURE - SPOT_LEG_CLOSURE = -s*(rp+rs)`.

That functional is sensitive to common-mode BTC motion. If `rp == rs ≠ 0`,
`D` is unchanged but the old target is nonzero. It cannot be read as
“which venue closed the gap.”

Two coherent estimands were compared without inspecting real D9 outcomes:

- **A. RELATIVE RESOLUTION ATTRIBUTION** (selected). Studies actual
  convergence of `D`. `TOTAL_CLOSURE = -s*(rp-rs)`. Primary
  `PERP_RESOLUTION_SHARE` is defined **only if** `TOTAL_CLOSURE > 0`.
  `rp == rs` is ineligible. Widening is ineligible, never recoded as
  positive resolution. Conditional-on-closure collider is explicit:
  a null does not mean gaps fail to close.
- **B. FUTURE CONSENSUS / PRICE-DISCOVERY LEADERSHIP** (rejected).
  A later common mid from two synchronous 5m BTC closes is dominated by
  `rp+rs`. That disguises future common-price movement as gap closing
  and is not identified as venue leadership on this surface.

Synthetic invariants for A are encoded in
`tests/research/test_discovery_sprint_03.py`.

## Selected cards

| ID | Name | Family | Data |
|---|---|---|---|
| D9 | `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` | H venue-structure | `DATA_READY` MARKET-06 two-leg 5m |
| D10 | `BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE` | D relative cross-asset | `DATA_READY` CORE BTC+ETH |
| D11 | `SCHEDULED_MACRO_EVENT_VOL_RESPONSE` | G event-response | `ACQUIRABLE_FREE_HISTORICAL` FOMC calendar + CORE BTC |

All three differ in primary family. They are not the three neighboring
family-H candidates from the first draft.

Six history-aware candidates were compared against `MECHANISM_MEMORY_V0`.
Not selected: options IV (acquisition budget; C4), true panel (dataset
build; C5), OKX L2 (family-E cooldown / D7 follow-on; C6).

## Non-claims

```
SCIENTIFIC_OUTCOMES_COMPUTED = false
D9_EXECUTED = false
D10_EXECUTED = false
D11_EXECUTED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```
