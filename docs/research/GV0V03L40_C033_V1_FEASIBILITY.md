# GV0V03L40 C033 V1 feasibility

**Status:** `FEASIBLE_FOR_PREREGISTRATION`
**Date:** 2026-10-02

```
MEMORY_CAMPAIGN_ID = GV0V03L40
SOURCE_RUN_ID      = ladder-40-card-v03-r02-derived-critics-v2
CANDIDATE_ID       = C033
C033_NEXT          = PREREGISTRATION_DESIGN
EXECUTION_AUTHORIZED = false
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
LLM_CALLS = 0
SCIENTIFIC_DESIGN_CHANGED_AFTER_COMPILE = false
```

This is an outcome-blind planning screen. It is not a market test and it does not open a preregistration.

## Freeze

The generated card is unchanged. `COMPLEXITY_CLASS = COMPOSITE`. The four components stay the generated sentences. One primary cell is frozen:

```
SHOCK_SIGMA = 3
TAKER_BAND = p1_p99
POST_WINDOW_H = 6
PRIMARY_CELLS = 1
REGIME = ALL_ELIGIBLE_BTC_15M_SHOCKS
```

`SHOCK_SIGMA = 4`, `TAKER_BAND = p2_p98` and `POST_WINDOW_H = 12` stay secondary diagnostic variants. They are outside primary multiplicity.

```
CLAIM_TYPE = INCREMENTAL
TARGET_CLASS = UNCONDITIONAL
INTRADAY = true
ENDPOINT_MOMENT = SECOND_MOMENT
EXPECTED_DIRECTION = NEGATIVE
MECHANISM_VARIABLE = FORCED_FLOW_ALL4_JOINT
PRACTICAL_BAR_BASIS = PRODUCT_RELEVANCE
MIN_MEANINGFUL_EFFECT = 0.20
UNITS = STANDARDIZED_RV_DECAY_SD
NAMED_INFERENCE_CLASS = PERMUTATION_GROUP_INVARIANCE
```

The nuisance baseline is prior realized volatility, the lagged target, time of day, the four component main effects, log shock size, hour of week and year. The joint indicator is not in that baseline.

The BTC shock sigma window is the trailing 30 days of 15m `log(close/open)`, strictly before T. The card names that 30-day window for the ETH sigma and the fragmentation percentile, and it names trailing sigma for the BTC shock without a second length. The 30-day window is the operational reading of that unnamed length. It is not a searched parameter.

Discovery is `BINANCE_2020_2024`, `2020-01-01` through `2025-01-01` exclusive. Replication is prospective `BINANCE_PROSPECTIVE_C033_V1`, starting `2027-01-01`, with `MIN_N = 1000`, `MAX_EPISODES = 1500` and `END_DATE = 2028-12-31`. No BitMEX replication is claimed. No 2025 or 2026 value was opened.

## Outcome-blind count

Pinned monthly zip bytes for `CORE_BTC_BINANCE_V0` and `CORE_ETH_BINANCE_V0`, `2020-01` through `2024-12` only, matched the frozen checksums. 15m bars are aggregated from those minutes. Incomplete buckets are dropped. The detector does not compute `RV_DECAY`, a post-T return, MFE, MAE or a target value.

The nominal sample is the first eligible shock in each 6-hour cluster.

```
TOTAL_ELIGIBLE_SHOCKS = 2926
TOTAL_ALL4_EVENTS = 0
COUNT_BY_YEAR = 2020:211, 2021:286, 2022:299, 2023:288, 2024:299
DISTINCT_DAYS = 971
DEPENDENCE_CLUSTER_COUNT = 1383
NOMINAL_N = 1383
```

On the 2926 eligible shocks, before thinning, the component flags are taker burst 44, fragmentation 53, ETH synchrony 1628 and intrabar overshoot 251. Taker and fragmentation coincide once. That bar does not also have the overshoot flag. The all-four joint label occurs zero times. The thresholds were not changed after this count.

## Compiler

`validate_planning_v1 = PASS`. The sealed object was compiled once under `GV0R02_SCHEMA_V1` / `GV0R02_POLICY_V1`.

```
FEASIBILITY_STATUS = FEASIBLE_FOR_PREREGISTRATION
BLOCKERS = []
NOMINAL_N = 1383
ATTAINABLE_ALPHA = null
MDE_BASE = 0.07533429827293509
MDE_STRESS = 0.15066859654587017
POWER_AT_MIN_MEANINGFUL_EFFECT_BASE = 0.9999999784649516
POWER_AT_MIN_MEANINGFUL_EFFECT_STRESS = 0.9607033310021197
REPLICATION_MDE = 0.1771878069659319
REPLICATION_POWER = 0.8853789898000417
HETEROGENEITY_ASSESSABILITY = NOT_ASSESSABLE
HETEROGENEITY_POWER = 0.19543127514725916
```

`ATTAINABLE_ALPHA` is null because the permutation orbit size was not supplied. The compiler did not raise `ALPHA_UNATTAINABLE`. Heterogeneity assessability is descriptive and is not evidence of stability. It is not a blocker.

The stress screen at the declared shock sample and at replication `MIN_N = 1000` clears the 0.20 practical bar. The decision rule therefore records `C033_NEXT = PREREGISTRATION_DESIGN`. The joint label count of zero is part of that record. It is not a reason to add a cell, lower the bar, or widen the window.
