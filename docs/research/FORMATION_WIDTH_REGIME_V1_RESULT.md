# FORMATION_WIDTH_REGIME_V1 — outcome read

`outcome_read = true`
`route = FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT`

Formation width historically carried monotone information about at least one predeclared next-hour observable beyond contemporaneous realized volatility of the same formation hour, on this exposed discovery surface.

This read does not establish a forecast, a current probability, an edge, a causal mechanism, or a trading signal.

No successor is started. A later question needs its own design and a separate owner go.

Surface `CORE_BTC_BINANCE_V0` `2020-01-01` to `2025-01-01` exclusive.
N 1820. ISO weeks 262. Seed 20261107. Draws 2000.
Pre-outcome evaluator `b1f36a56a5dfefd96f344238cf1bf071f6c42884`.

## Foundation

| endpoint | rho | family interval | clear |
| --- | --- | --- | --- |
| ACTIVITY | +0.6811 | [+0.6340, +0.7222] | true |
| DISPLACEMENT | +0.3214 | [+0.2649, +0.3746] | true |

## Years

- ACTIVITY foundation, stable: 2020 +0.7185 (n 365); 2021 +0.6184 (n 364); 2022 +0.5884 (n 363); 2023 +0.6239 (n 363); 2024 +0.5602 (n 365)
- DISPLACEMENT foundation, stable: 2020 +0.2819 (n 365); 2021 +0.2597 (n 364); 2022 +0.3162 (n 363); 2023 +0.2954 (n 363); 2024 +0.1827 (n 365)

## Incremental given RV_FORMATION

| endpoint | rho | family interval | clear |
| --- | --- | --- | --- |
| ACTIVITY | +0.1025 | [+0.0480, +0.1553] | true |
| DISPLACEMENT | +0.0139 | [-0.0375, +0.0682] | false |

## RV_PREV secondary context

Spearman(V, RV_PREV) +0.6960.
Partial ACTIVITY +0.4530. Partial DISPLACEMENT +0.1643.
These numbers are not route inputs.

## Lag placebo

- ACTIVITY: rho +0.5056, current_state_specific True
- DISPLACEMENT: rho +0.2843, current_state_specific True

route_supporting_endpoints: ['ACTIVITY']
incremental_qualified_but_not_specific_endpoints: []
