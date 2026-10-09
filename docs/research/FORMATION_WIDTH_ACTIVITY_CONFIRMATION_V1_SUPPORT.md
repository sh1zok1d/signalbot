# FORMATION_WIDTH_ACTIVITY_CONFIRMATION_V1 — outcome-blind support

`outcome_read = false`
`claim_selected_pre_outcome = true`
`information_status = INFORMATIONALLY_WEAK_BEFORE_OUTCOME`
`pre_outcome_route = INFORMATIONALLY_WEAK_BEFORE_OUTCOME`

This file counts path presence and the width state. It does not contain the next-hour endpoint or an association with that endpoint.

Surface `DH1_BINANCE_SPOT_BTCUSDT_5M_V0` `2017-09-01` to `2020-01-01` exclusive.
Exposure `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`.

## Counts

- calendar days: 852
- usable formations: 828
- formation incomplete: 24
- RV_FORMATION span incomplete among usable: 1
- next-hour path incomplete among usable: 0
- analysis N: 827
- ISO weeks: 123
- mean analysis days per week: 6.7236
- first half before 2018-11-01: 405
- second half: 422
- years: {'2017': 110, '2018': 356, '2019': 361}
- months: 2017-09 24, 2017-10 28, 2017-11 27, 2017-12 31, 2018-01 31, 2018-02 23, 2018-03 31, 2018-04 30, 2018-05 30, 2018-06 30, 2018-07 29, 2018-08 31, 2018-09 29, 2018-10 31, 2018-11 30, 2018-12 31, 2019-01 30, 2019-02 28, 2019-03 31, 2019-04 30, 2019-05 31, 2019-06 30, 2019-07 30, 2019-08 31, 2019-09 30, 2019-10 31, 2019-11 29, 2019-12 30

## Width state

- usable n: 828
- mean: 0.013814
- quantiles: {'p10': 0.004137160704953873, 'p25': 0.006043633768667895, 'p50': 0.010464549392621893, 'p75': 0.01656245069792364, 'p90': 0.026162217016189107}
- p90/p10: 6.323713
- lag-1 rank correlation of relative width: 0.5724856987358486
- lag pairs: 806

## Information forecast

The forecast uses the width lag as an AR(1) stand-in for within-week dependence of the later association. It does not use the next-hour endpoint.

- effective N: 298.0134
- Fisher SE: 0.05822093261541339
- independent-day SE: 0.034836650714580884
- one-draw-per-week SE: 0.09128709291752768
- 80% MDE: 0.1447648853045097
- power that the lower bound excludes 0 at the practical bar: 0.5289941554479648
- probability the point clears the bar and the bound excludes 0, when the planted value equals the bar: 0.5

Separate owner go to read the endpoint: False.
The support census does not authorize that read.
