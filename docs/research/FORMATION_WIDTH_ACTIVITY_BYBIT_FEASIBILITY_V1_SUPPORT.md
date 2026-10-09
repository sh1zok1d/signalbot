# FORMATION_WIDTH_ACTIVITY_BYBIT_FEASIBILITY_V1 — outcome-blind feasibility

`outcome_read = false`
`future_association_read = false`
`owner_go_required_for_outcome = true`
`pre_outcome_route = INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`
`later_outcome_permitted_after_separate_go = true`

This note counts path presence and the width state on one pinned Bybit series. It does not contain the next-hour endpoint or an association with that endpoint.

Surface `LEVEL_CROSS_VENUE_PERP_5M_V0` `Bybit` `BTCUSDT` `linear perpetual`.
Events `2020-04-01` to `2025-01-01` exclusive.
Exposure `SAME_CALENDAR_CROSS_VENUE_EXPOSED_REPLICATION`. Time-disjoint from the Binance discovery window: false.

## Counts

- calendar days: 1736
- usable formations: 1614
- formation incomplete: 122
- RV_FORMATION span incomplete among usable: 0
- next-hour path incomplete among usable: 1
- analysis N: 1613
- ISO weeks: 240
- mean analysis days per week: 6.7208
- first half before 2022-08-17: 838
- second half: 775
- years: {'2020': 261, '2021': 351, '2022': 362, '2023': 331, '2024': 308}
- months: 2020-04 29, 2020-05 30, 2020-06 29, 2020-07 26, 2020-08 31, 2020-09 29, 2020-10 27, 2020-11 29, 2020-12 31, 2021-01 30, 2021-02 28, 2021-03 30, 2021-04 28, 2021-05 29, 2021-06 29, 2021-07 29, 2021-08 28, 2021-09 29, 2021-10 31, 2021-11 29, 2021-12 31, 2022-01 31, 2022-02 27, 2022-03 31, 2022-04 30, 2022-05 31, 2022-06 29, 2022-07 31, 2022-08 31, 2022-09 29, 2022-10 31, 2022-11 30, 2022-12 31, 2023-01 30, 2023-02 28, 2023-03 31, 2023-04 30, 2023-05 31, 2023-06 29, 2023-07 30, 2023-08 28, 2023-09 29, 2023-10 31, 2023-11 30, 2023-12 4, 2024-01 2, 2024-02 27, 2024-03 8, 2024-04 29, 2024-05 31, 2024-06 30, 2024-07 30, 2024-08 31, 2024-09 30, 2024-10 30, 2024-11 29, 2024-12 31

## Width state

- usable n: 1614
- mean: 0.01031241611874118
- quantiles: {'p10': 0.003258650295387011, 'p25': 0.005067069564340346, 'p50': 0.007910679743988507, 'p75': 0.012591335292233358, 'p90': 0.019616891140611572}
- p90/p10: 6.019943646110632
- lag-1 rank correlation of relative width: 0.5185063706050135
- lag pairs: 1569

## Information forecast

The forecast is the confirmation unit's width-lag AR(1) Kish model. It does not use the next-hour endpoint.

- effective N: 645.3604432971196
- Fisher SE: 0.03945577746287656
- independent-day SE: 0.024922239313961342
- one-draw-per-week SE: 0.06495698024616309
- 80% MDE: 0.09810579876388723
- power that the lower bound excludes 0 at +0.10: 0.8131675544359748

A separate owner go is required before any outcome. This file does not give that go.
BitMEX is outside this unit. No second historical surface is opened here.
