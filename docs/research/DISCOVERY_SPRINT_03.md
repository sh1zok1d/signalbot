# Discovery Sprint 03

**Unit:** `DISCOVERY_SPRINT_03_HETEROGENEOUS_CARD_DEFINITION`
**Parent policy:** `HETEROGENEOUS_FAMILY_ROTATION_V2`
**Date:** 2026-09-22
**Status:** `OUTCOME_BLIND_IMPLEMENTATION_FROZEN` (no scientific outcomes)
**Memory:** `docs/research/MECHANISM_MEMORY_V0.{json,md}`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_03.json`
**Implementation freeze:** `docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.{json,md}`

Outcome-blind implementation and structural feasibility only. Three
internal cards. No scientific outcomes. No D7 rerun. No D8 execution.
No 2025/2026. No MARKET-07.

```
INTERNAL_CARDS = D9, D10, D11
SPRINT03_SELECTION_INCOMPLETE = false
D9_CHOSEN_ESTIMAND = RELATIVE_RESOLUTION_ATTRIBUTION
D9_PRIMARY_LOCATION_STATISTIC = MEDIAN_PERP_RESOLUTION_SHARE
D9_SCIENTIFIC_CLAIM_MAY_ESTABLISH = CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION
D9_SHARE_NOT_CLIPPED = true
D10_FIXED_PRE_EVENT_BETA = true
D10_REGRESSION_SPECIFICATION = NO_INTERCEPT_OLS
D11_FOMC_ONLY = true
D11_OFFICIAL_SOURCE_PINNED = true
D9_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D10_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D11_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
EXECUTION_AUTHORIZED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_IMPLEMENTATION_RED_TEAM_AND_EXECUTION_DECISION
```

The next unit is an independent implementation red-team and execution
decision. It must not treat this freeze as a RESULT. Real scientific
evaluation remains unauthorized.

## D9 estimand

`TOTAL_CLOSURE = -s*(rp-rs)`.
`PERP_RESOLUTION_SHARE = (-s*rp)/TOTAL_CLOSURE` only if `TOTAL_CLOSURE>0`.

SHARE is **not** clipped or winsorized. Values `<0` or `>1` are legal when
one venue opposes closure and the other over-compensates.

- `SHARE = 0.5` — equal signed contribution to net closure
- `SHARE > 0.5` — perp contributed more net closure than spot
- `SHARE < 0.5` — spot contributed more net closure than perp
- `SHARE > 0` alone does **not** mean perp contributed more

D9 may establish only `CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION`.
Synchronous 5m closes cannot establish `PRICE_DISCOVERY_LEADERSHIP`,
`CAUSAL_LEADERSHIP`, or `WHICH_VENUE_MOVED_FIRST`. A positive may justify
a later higher-resolution / third-venue price-discovery study; it is not
itself price-discovery proof. Primary SHARE is conditional on observed
`TOTAL_CLOSURE > 0`.

Old `-s*(rp+rs)` imbalance remains rejected. Estimand B remains rejected.
Primary location statistic is `MEDIAN_PERP_RESOLUTION_SHARE` because SHARE
is a ratio with an arbitrarily small positive denominator. Mean SHARE is
not used. No outcome-derived `TOTAL_CLOSURE` cutoff.

## D10 target beta

`OPTION A` no-intercept OLS: `beta_t = sum(x*y)/sum(x^2)` on exactly the
previous 720 valid completed hours strictly before event hour `t`.
The t+1 residual **reuses** that same `beta_t`. Do not recompute beta at
t+1. Do not let hour `t` enter the target beta. Do not fit an intercept
and then drop it.

Matched baseline (frozen): `YEAR × sign(e_t) × |r_btc_t|` trailing-quantile
bucket, plus a small `|e_t|` control population. No threshold/horizon search.

## D11 event family

D11 is exactly `SCHEDULED_FOMC_EVENT_VOL_RESPONSE`. Official Federal
Reserve / FOMC scheduled monetary-policy announcement calendar is pinned
in `docs/research_data/D11_FOMC_OFFICIAL_V0`. No CPI, NFP, ECB, or later
macro substitution. Unscheduled/emergency actions and notation votes are
excluded. Baseline is `YEAR × WEEKDAY × UTC_HOUR`. DST from the official
announcement timestamp (`For release at 2:00 p.m. EST/EDT`). Unsigned
`POST_EVENT_RV_6H` only. If support is insufficient:
`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`.

## Selected cards

| ID | Name | Family | Data |
|---|---|---|---|
| D9 | `VENUE_DISLOCATION_RESOLUTION_STRUCTURE` | H venue-structure | `DATA_READY` MARKET-06 two-leg 5m |
| D10 | `BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE` | D relative cross-asset | `DATA_READY` CORE BTC+ETH |
| D11 | `SCHEDULED_FOMC_EVENT_VOL_RESPONSE` | G event-response | `ACQUIRABLE_FREE_HISTORICAL` official FOMC calendar + CORE BTC |

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
