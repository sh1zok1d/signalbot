# D7 BitMEX support and power V0

**Unit:** `D7_BITMEX_SUPPORT_AND_POWER_V0`

Outcome-blind selector support and synthetic power on the pinned
`D7_BITMEX_ACTIVITY_V0` authority. The BitMEX primary target
`NEXT_HOUR_HIGH_IMPACT_STATE` is unopened. No t+1 pairing, no
persistence statistic, no BitMEX effect, no replication class.
No confirmation preregistration and no execution permit.

## Data identity

```
DATA_IDENTITY_STATUS = PASS
DATASET_ID = D7_BITMEX_ACTIVITY_V0
CANONICAL_GZ_SHA256 = 33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c
D2_CANONICAL_GZ_SHA256 = 8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa
D2_CANONICAL_MODIFIED = false
ACTIVITY_FIELD = foreignNotional
ACTIVITY_PORTABILITY_CLASS = D7_ACTIVITY_SCIENTIFICALLY_COMPARABLE
ROW_COUNT = 382033
FIRST_OPEN = 2016-05-13T11:55:00.000Z
LAST_OPEN = 2019-12-31T23:55:00.000Z
DUPLICATE_TIMESTAMPS = 0
NON_MONOTONIC = 0
NULL_OPEN = 0
NULL_HIGH = 0
NULL_LOW = 0
NULL_CLOSE = 0
NULL_FOREIGN_NOTIONAL = 0
MISSING_BUCKETS = 288
FIRST_MISSING_BUCKET = 2016-12-06T23:55:00.000Z
LAST_MISSING_BUCKET = 2016-12-07T23:50:00.000Z
MISSING_HALF_OPEN = [2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)
```

No fill, interpolation, or forward-fill. Incomplete UTC hours are
absent from the constructed-hour set.

## Selector

Completed UTC hours use the frozen D7 return: absolute log return
from the first 5m open to the last 5m close, and only when all 12
buckets exist. Quote activity is the sum of `foreignNotional`.
`QREL_1H`, `IMPACT_PROXY`, trailing P90, and `RV_BUCKET` use the
previous 720 valid values. The current hour is excluded. The state
cut is strict `>`. Structural eligibility requires the next
constructed hour to exist and to have a defined D7 state. It does
not read whether that next state is true or false.

```
CONSTRUCTED_HOURS = 31835
VALID_IMPACT_ROWS = 31075
TARGET_STRUCTURALLY_ELIGIBLE_ROWS = 30354
STATE_N = 3446
SELECTOR_N = 3438
SELECTOR_DIGEST = 88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6
STATE_N_BY_YEAR = {'2016': 430, '2017': 1209, '2018': 875, '2019': 932}
```

Year by RV-bucket state counts and eligible counts are in the JSON
twin. Selector timestamps are not listed.

## Control support

```
CONTROL_SUPPORT = CONTROL_SUPPORT_OK
```

A stratum can host 10,000 rate-matched draws when candidate N is
at most eligible N. The frozen discovery census also requires
eligible N >= 2 times candidate N, and the discovery floors
`MIN_D7_STATE_TOTAL = 500` and
`MIN_D7_STATE_PER_YEAR = 50` on each observed
BitMEX calendar year. Binance years 2020–2024 are not copied onto
this surface. Each stratum row reports `eligible_n`, `candidate_n`,
`non_candidate_n`, `candidate_rate`, and the two support flags.
Candidate rates are higher in the top RV bucket because the frozen
impact state uses absolute return and the bucket is the same
absolute return. That is a selector property, not a next-hour result.

## Independence

```
INDEPENDENCE_CLASS = D7_TARGET_FRESH_ON_PREVIOUSLY_EXPOSED_MARKET_SURFACE
```

The pre-2020 XBTUSD price path was already used for D2
`RV_ABSTENTION` / `arithmetic_mae`. That surface is not untouched.
No prior artifact computed the D7 target or a t+1 persistence
statistic on BitMEX. Activity bytes are the new
`D7_BITMEX_ACTIVITY_V0` authority. The D2 canonical gzip is unchanged.

## Power

Planning effect is the frozen Binance discovery result only:
`MU_D7_RULE = 0.18943894389438945`,
`MU_D7_CONTROL = 0.09856569856985697`,
`DELTA_D7 = 0.09087324532453248`.
Synthetic targets use that control probability as `p0` for
non-candidates and `p0 + fraction * delta` for candidates.
No BitMEX t+1 rate enters. The primary power event is the frozen
statistical gate, candidate mean above the 95th percentile of
10000 rate-matched control means. The practical
threshold `0.05` is reported beside it and is not
the primary bar. The Binance temporal-year gate is not scored.

```
POWER_FULL_EFFECT = 1.0
POWER_FULL_EFFECT_95CI = [0.996173241514445, 1.0]
POWER_75PCT_EFFECT = 1.0
POWER_75PCT_EFFECT_95CI = [0.996173241514445, 1.0]
POWER_50PCT_EFFECT = 1.0
POWER_50PCT_EFFECT_95CI = [0.996173241514445, 1.0]
MC_REPLICATES = 1000
POWER_SEED = 20260930171
PRIMARY_BAR = 0.8
POWER_FULL_EFFECT_MEETS_BAR = true
PRACTICAL_PASS_RATE_FULL_INFORMATIONAL = 1.0
PRACTICAL_PASS_RATE_75PCT_INFORMATIONAL = 0.807
PRACTICAL_PASS_RATE_50PCT_INFORMATIONAL = 0.005
```

The practical pass rates use the frozen `0.05` threshold on the
synthetic delta. They are not the primary bar. At half the Binance
delta the expected contrast sits below `0.05`, so that informational
rate is low even when the statistical gate passes.

## Dependence

```
DEPENDENCE_REVIEW_STATUS = INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW
```

Structural dependence is present before any outcome is observed. Each D7 threshold is a 720-hour trailing percentile, so adjacent hours share 719 threshold inputs. QREL, IMPACT_PROXY, and RV_BUCKET use those overlapping histories. The panel is a repeated hourly sequence. calendar_year x RV_BUCKET stratification changes the sampling frame and does not preserve serial dependence. The frozen rate-matched Monte Carlo draws exchangeably inside each stratum. That null is not a dependence-preserving null for an hourly next-state association. This unit does not measure real D7 adjacency and does not invent a block estimator. A confirmation preregistration needs an explicit dependence-preserving inference choice first. The power figures in this unit are the power of that exchangeable gate under independent synthetic targets. They are not a dependence-robust power.

## Decision

```
FEASIBILITY_DECISION = INFERENCE_DESIGN_NEEDS_DEPENDENCE_REVIEW
PRIMARY_BLOCKERS = ['Exchangeable year x RV_BUCKET rate-matched Monte Carlo does not preserve overlapping 720-hour dependence. No replacement estimator is defined in this unit.']
NEXT_UNIT = NONE
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_BITMEX_EFFECT_COMPUTED = false
D7_BITMEX_REPLICATION_CLASS_ASSIGNED = false
BINANCE_2025_OPENED = false
BINANCE_2026_OPENED = false
```

This unit does not classify scientific truth.
