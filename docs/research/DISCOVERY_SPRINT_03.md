# Discovery Sprint 03

**Unit:** `DISCOVERY_SPRINT_03_HETEROGENEOUS_CARD_DEFINITION`  
**Parent policy:** `HETEROGENEOUS_FAMILY_ROTATION_V2`  
**Date:** 2026-09-22  
**Status:** `DEFINED`  
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_03.json`

Outcome-blind card definition only. Exactly one internal card. No
scientific outcomes. No D7 rerun. No D8 execution. No 2025/2026. No
MARKET-07. No confirmatory preregistration. No D9 evaluator.

```
DISCOVERY_SPRINT_03_INTERNAL_CARDS = 1
D9_STATUS = DEFINED_NOT_EXECUTED
D9_EXECUTED = false
D9_SCIENTIFIC_OUTCOME_COMPUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
DATA_LABEL = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
NEXT_UNIT = DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

The next unit may run the listed non-outcome feasibility censuses,
implementation, synthetic tests, and outcome-blind review. It must not
execute D9 scientific outcomes automatically.

## Canonical D7 (recorded, not rerun)

```
D7_NAME           = KLINE_FLOW_IMPACT_STATE
D7_FAMILY         = E / LIQUIDITY_EXECUTION_STATE
D7_STATUS         = PROMISING_PROTOTYPE
CLASSIFICATION    = D7_PROMISING_PROTOTYPE
STATISTICAL_GATE  = true
PRACTICAL_GATE    = true
TEMPORAL_GATE     = true
YEARLY_DELTA_D7   positive in all five years 2020–2024
EVIDENCE_LABEL    = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
NOT_INDEPENDENT_CONFIRMATION = true
NOT_PROVEN_ALPHA = true
NOT_VALIDATED_TRADING_EDGE = true
NOT_ORDERBOOK_LIQUIDITY_CLAIM = true
D7_CONFIRMATION_CANDIDATE = true
D7_CONFIRMATION_SELECTED_NOW = false
```

D8 remains `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`. That is not
`D8_NO_USEFUL_STRUCTURE`.

Internal counters: executed 5, promising 2. D1 deferred. D6
external/deferred. D8 deferred, not counted as executed.

## Family-H candidate comparison (outcome-blind)

Three materially different venue-structure mechanisms were compared
using novelty, orthogonality to MARKET-06/D2/D7, falsifiability,
information gain, baseline defensibility, support, DOF, and cost.
No new scientific target was inspected to choose among them.

### H1 — `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` (selected as D9)

Who closes an unusually large Binance-perp vs OKX-spot 5m dislocation
over the next hour? Studies the venue relationship itself.

- **DATA_FEASIBILITY_CLASS:** `DATA_READY`
- **NULL would deprioritize:** this pair as a price-discovery /
  venue-leadership mechanism at extreme 5m dislocations.
- **Positive would justify:** proposing a later confirmatory
  venue-structure study or adding a third venue — not MARKET-07 now.

### H2 — `CROSS_VENUE_SHOCK_TRANSMISSION` (not selected)

Lead-lag after an extreme own-venue 5m return. Rejected: common-factor
null is the same fragile class that deferred D4 `LEAD_LAG_1DAY`.

### H3 — `DISLOCATION_PROCESS_DYNAMICS` (not selected)

Does `D` itself decay? Rejected: two quotes of the same BTC are
expected to be tightly bound; a null mostly restates a tautology.
Lower information gain than H1.

A fourth idea, high-dislocation **state persistence**, was not even
promoted to a candidate: that FUNCTION is a D7 neighbor.

## D9 — `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` (family H)

Venue-structure subfamily on the existing MARKET-06 two-leg surface.
Not a true cross-sectional panel.

- **DATASET / SNAPSHOT:** `MARKET_06_OKX_BINANCE_FEASIBILITY_V0` /
  `e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68`
- **LEGS:** Binance USD-M BTCUSDT perp 5m trade-price close + OKX
  BTC-USDT spot 5m trade-price close.
- **WINDOW:** `[2022-01-01T00:00:00Z, 2025-01-01T00:00:00Z)`.
- **STRUCTURAL CENSUS (already tracked, not recomputed here):**
  315648 aligned 5m timestamps, alignment rate 1.0, no interpolation /
  forward-fill.
- **D(u):** `ln(perp_close(u) / spot_close(u))`. Definition reused
  from MARKET-06; the *claim* is not reused.
- **EVENT (one frozen rule):** `|D(u)| > P90(previous 8640 valid |D|)`,
  current `u` excluded, strict `>`. Window length 8640 = 30d at 5m,
  reused from MARKET-06's dislocation reference length so this card
  does not search a new lookback.
- **OVERLAP:** keep the first event; drop later candidates within 12
  bars.
- **PRIMARY TARGET:** `RESOLUTION_IMBALANCE` over 12 bars (1h):
  `PERP_LEG_CLOSURE - SPOT_LEG_CLOSURE`, where
  `PERP_LEG_CLOSURE = -sign(D(u)) * ln(perp_close(u+1h)/perp_close(u))`
  and
  `SPOT_LEG_CLOSURE = sign(D(u)) * ln(spot_close(u+1h)/spot_close(u))`.
  Positive = Binance perp contributed more gap-closing move than OKX
  spot.
- **SIMPLE_BASELINE:** `YEAR_SIGN_RV_MATCHED_RATE_MATCHED_RANDOM_NON_EVENT`.
  Same year, same `sign(D)`, same trailing `RV_5M` bucket, **fails**
  the P90 event rule. Rate-matched without replacement. Do not weaken
  P90. If controls are insufficient:
  `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`.
- **SMALL_SEARCH_SURFACE:** one event, one 12-bar primary horizon,
  one imbalance target, one control. 6-bar imbalance and
  `TOTAL_CLOSURE` are diagnostic only.
- **PROTECTED BOUND (strict):** `u + 1h < 2025-01-01T00:00:00Z`.
- **MAX_ENGINEERING_SCOPE:** existing MARKET-06 5m loader + one
  event/resolution evaluator. No new dataset, no third venue, no L2,
  no durability implementation in the next unit.

### Why D9 is not a MARKET-06 rescue

MARKET-06 asked whether daily `ABS_DISLOCATION_Z` adds 24h
direction-aligned BTC MAE information beside own-state controls. That
claim is consumed (`MARKET_06_NO_EVIDENCE`). D9 asks which venue's
subsequent return closes an extreme 5m dislocation. Different
function, clock, unit, target, and baseline. Forbidden: 24h MAE,
additive regression, `ABS_DISLOCATION_Z` as a BTC-path predictor,
terminal-return prediction, D2 dislocation-abstention, threshold
rescue of MARKET-06.

### Why D9 is not a D7 neighbor

D7 is family E on CORE BTC 1h kline `IMPACT_PROXY` state persistence.
D9 is family H on two-venue 5m `D(u)` resolution imbalance. No shared
proxy, trailing window, or persistence target. Family E is in cooldown.

## Other families

See rotation V2. F remains `DEFERRED_BLOCKER_UNRESOLVED`. G must not
rescue D8. I remains deferred/diagnostic. A/B/C/D remain unselected.

```
MARKET_07_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
PRODUCT_BUILD_FROZEN = true
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
D9_EXECUTED = false
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
RESEARCH_DATA_DURABILITY_V1_IMPLEMENTED = false
```
