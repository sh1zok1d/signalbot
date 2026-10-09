# FORMATION_WIDTH_ACTIVITY_PROSPECTIVE_V1 support forecast

`outcome_read = false`
`future_association_read = false`
`accrued_analysis_n = 0`
`status = AWAITING_START`

This file is the outcome-blind compiler output. It counts no forward bar and scores no forward association. The dependence model below is a forecast assumption. The inferential engine is the ISO-week block bootstrap at the frozen checkpoints.

Prospective start: `2026-10-10T00:00:00Z`.
Dataset: `BINANCE_UM_LIVE_FORWARD`, Binance USD-M BTCUSDT perpetual, column `CANDLES`.
Practical reference: `0.1`.

## Forecast assumption

Phi `0.5483151377537036` from `docs/research/FORMATION_WIDTH_REGIME_V1_FEASIBILITY.json`.
Discovery counts used only as rates: analysis N `1820`, ISO weeks `262`, calendar days `1827`.
Model: AR(1) inside an ISO week, then Kish effective N, then the Fisher standard error. This is not refit on a forward state, and it is not the test.

## Checkpoints

| N | role | ISO weeks | effective N | SE | MDE80 | single-look power | information time | incremental alpha | sequential power | expected formation date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1095 | FIRST_LOOK | 158 | 410.9596 | 0.049510 | 0.123105 | 0.646150 | 0.500414 | 0.025021 | 0.523998 | 2029-10-13 |
| 1825 | MATURITY | 263 | 684.7057 | 0.038300 | 0.095233 | 0.833002 | 0.833747 | 0.016667 | 0.685418 | 2031-10-16 |
| 2190 | TERMINAL | 315 | 821.2389 | 0.034959 | 0.086925 | 0.887938 | 1.000000 | 0.008313 | 0.679248 | 2032-10-16 |

## Rejected candidates

| N | single-look power | MDE80 | reason |
| --- | --- | --- | --- |
| 90 | 0.137858 | 0.448128 | SINGLE_LOOK_POWER_BELOW_MINIMUM |
| 180 | 0.200097 | 0.309426 | SINGLE_LOOK_POWER_BELOW_MINIMUM |
| 365 | 0.313361 | 0.214628 | SINGLE_LOOK_POWER_BELOW_MINIMUM |
| 540 | 0.408414 | 0.175943 | SINGLE_LOOK_POWER_BELOW_MINIMUM |
| 730 | 0.500233 | 0.151113 | SEQUENTIAL_INCREMENT_POWER_BELOW_MINIMUM |
| 1460 | 0.754457 | 0.106558 | SEQUENTIAL_INCREMENT_POWER_BELOW_MINIMUM |

## Context, not a prior

Discovery point `0.10245095315584887`.
Cross-venue point `0.09903883442772482`.
Cross-venue route `POSITIVE_BUT_BELOW_PRACTICAL_SCALE`.
These numbers do not choose N, alpha, or the spending exponent.

Design SHA256: `d07b83ca9baea11d0af16424da6f7a7a29d43a2a61b6d850d974c8ed80da9612`.
