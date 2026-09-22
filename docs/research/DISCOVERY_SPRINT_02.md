# Discovery Sprint 02

**Unit:** `DISCOVERY_SPRINT_02_HETEROGENEOUS_CARD_DEFINITION`  
**Parent policy:** `HETEROGENEOUS_FAMILY_ROTATION_V1`  
**Date:** 2026-09-22  
**Status:** `DEFINED`  
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_02.json`

Outcome-blind card definition only. Two internal cards. No scientific
outcomes. No 2025/2026. No MARKET-07. No confirmatory preregistration.

```
DISCOVERY_SPRINT_02_INTERNAL_CARDS = 2
D7_STATUS = DEFINED_NOT_EXECUTED
D8_STATUS = DEFINED_NOT_EXECUTED
SCIENTIFIC_OUTCOMES_COMPUTED = false
DATA_LABEL = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
NEXT_UNIT = DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION
```

The next unit may run non-outcome feasibility censuses, implementation,
synthetic tests, and outcome-blind review. It must not execute D7/D8
scientific outcomes automatically.

## D7 — `KLINE_FLOW_IMPACT_STATE` (family E)

Kline-derived hourly execution-impact state on `CORE_BTC_BINANCE_V0`
only.

- **KLINE_PROXY_ONLY** = true
- **NOT_ORDERBOOK_LIQUIDITY** = true
- **NOT_REALIZED_SLIPPAGE** = true
- **FUNCTION:** state characterization / persistence. Not terminal-return
  prediction, not directional alpha, not D2 abstention rescue.
- **TIME_SCALE / UNIT:** one completed UTC hour from closed 1m bars.
- **STATE (one frozen rule):** `IMPACT_PROXY_t > P90(previous 720 valid
  IMPACT_PROXY)`, current `t` excluded, strict `>`.
- **IMPACT_PROXY:** `RET_ABS_1H / QREL_1H` where `QREL_1H` is current
  hourly quote volume over the median of the previous 720 valid hourly
  quote volumes. Nonpositive/nonfinite denominator → ineligible. No
  epsilon.
- **PRIMARY TARGET:** `NEXT_HOUR_HIGH_IMPACT_STATE` — the same frozen
  state at `t+1`. Continuous `IMPACT_PROXY_{t+1}` is diagnostic only.
- **SIMPLE_BASELINE:** rate-matched random state within
  `calendar_year × RV_BUCKET`. `RV_1H = RET_ABS_1H`. Four trailing
  quantile buckets (P25/P50/P75 of previous 720). Purpose: do not
  rediscover volatility clustering and call it liquidity.
- **SMALL_SEARCH_SURFACE:** one construction, one P90, one 720-hour
  window. No P85/P95. No alternate windows. `TAKER_IMBALANCE_1H` is
  diagnostic only.
- **WHAT_A_NULL_DEPRIORITIZES:** Binance kline-only volume/trade/taker-flow
  proxies as persistent execution-impact states beyond contemporaneous
  volatility.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** proposing a confirmatory
  execution-state study **or** acquiring L2/spread/slippage data. Not
  calling CORE V0 an order-book dataset.
- **MAX_ENGINEERING_SCOPE:** existing CORE loader + one aggregation/state
  evaluator. No new dataset, no L2, no execution simulator.

Legal hours: open in `[2020-01-01T00:00:00Z, 2025-01-01T00:00:00Z)`.

## D8 — `ENDOGENOUS_SHOCK_RECOVERY` (family G)

Event-time recovery after one frozen endogenous BTC shock. No external
calendar.

- **FUNCTION:** event response / recovery. Not generic terminal-return
  prediction, not D2 high-RV filtering, not D3 path morphology.
- **EVENT (one frozen definition):** completed 1h bar is a shock iff
  `ABS_EVENT_RETURN_t > P99(previous 720)` **and**
  `EVENT_VOLUME_t > P90(previous 720)`. Current `t` excluded. Strict `>`.
  Knowable only after the event hour closes.
- **OVERLAP:** keep the first event; drop later candidates within 6h.
- **PRIMARY TARGET:** `RECOVERY_6H = -sign(EVENT_RETURN) *
  log(price_{t+6h} / event_close_t) / abs(EVENT_RETURN)`.
  Positive = retracement. `RECOVERY_24H` is diagnostic only and cannot
  rescue the primary.
- **SIMPLE_BASELINE:** `calendar_year × EVENT_SIGN × magnitude-bucket`
  matched **non-event** controls. Magnitude buckets: four trailing
  quantiles of `ABS_EVENT_RETURN`. Question: do high-activity shocks
  recover differently than similarly large/sign-matched moves that fail
  the full shock definition?
- **FEASIBILITY (selector-only, before outcomes):** event counts,
  year/sign splits, baseline support. No recovery values.
- **MINIMUM SUPPORT (frozen):** `MIN_NONOVERLAPPING_EVENTS = 20`,
  `MIN_YEARS_WITH_EVENTS = 3`, at least two years with ≥3 events.
  If inadequate: `DEFERRED_INSUFFICIENT_EVENT_SUPPORT`. No weaker
  thresholds.
- **WHAT_A_NULL_DEPRIORITIZES:** this endogenous high-magnitude +
  high-activity shock/recovery scale. Not exogenous news, liquidations,
  or other CORE-unavailable event families.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** a separately frozen
  event-response confirmation study. Not strategy construction.
- **MAX_ENGINEERING_SCOPE:** one event constructor + one recovery
  evaluator. No news/calendar acquisition.

## Distinctness

See `ANTI_RESCUE_MATRIX` in the JSON. Summary:

- D7 ≠ D2 (hourly kline impact-state vs daily RV abstention)
- D7 ≠ MARKET-05/06 (no additive 24h MAE cell; no external observable)
- D8 ≠ D3 (sparse shock recovery vs generic path morphology)
- D8 ≠ H02 (endogenous P99/P90 event vs killed failed-breakout)
- D7 ≠ D8 (recurring state vs sparse event recovery)

## Other families

F remains `DEFERRED_BLOCKER_UNRESOLVED`. H remains
`DEFERRED_DATA_LIMITATION`. I remains `DEFERRED_SOURCE_NOT_PINNED`.
A/B/C/D are `NOT_SELECTED_THIS_ROTATION`.

```
MARKET_07_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
PRODUCT_BUILD_FROZEN = true
D7_EXECUTED = false
D8_EXECUTED = false
```
