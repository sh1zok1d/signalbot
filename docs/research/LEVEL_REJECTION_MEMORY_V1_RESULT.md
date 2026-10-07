# LEVEL_REJECTION_MEMORY_V1 — result

Dependency: `LEVEL_TOUCH_DEGRADATION_V1` / PR #352 / `dfc9e0f04358de15606382472badeb5aee787039`.
Design note commit `c8a1d4d2ac91b769aa8091b006c320df4b352f5e`.
Tracks: STRUCTURE, PRODUCT_EVIDENCE. One run. Not a rescore of the dependency unit.

## estimate

Among structural BTC levels whose previous independent touch was REJECT_FIRST and that were tested again, one SD faster prior rejection (frozen −log bars to the reject barrier) lined up with a -0.1 pp difference in the next touch's 4h BREAK_FIRST frequency after adjustment for touch ordinal, family, side, volatility tercile, year and log wait (N=1151, 95% -2.9..+2.6 pp).

Primary coefficient (cell 1): -0.1 pp, 95% -2.9..+2.6 pp, N=1151, clusters=283.

## decomposition

- REJECT_FIRST: +1.0 pp (-1.9..+3.9 pp), N=1151, clusters=283.
- NEITHER: -0.8 pp (-2.7..+1.0 pp), N=1151, clusters=283.

Speed tertiles (slow / mid / fast), crude next-touch shares:

- slow: N=385, BREAK 39.2%, REJECT 47.8%, NEITHER 13.0%
- mid: N=408, BREAK 39.7%, REJECT 47.1%, NEITHER 13.2%
- fast: N=358, BREAK 39.4%, REJECT 50.6%, NEITHER 10.1%

Fast minus slow: BREAK +0.2 pp (-6.5..+7.2 pp).

## uncertainty

95% percentile interval from 2000 resamples of the predeclared cluster (product week of the next touch for day and week levels; episode id for month levels), seed 20261008. Not a p-value. The claim sentence cites cell 1 only.

## touch ordinal and time since rejection

- without touch-ordinal control: -0.2 pp (-2.9..+2.5 pp), N=1151, clusters=283.
- without log-gap control: +0.2 pp (-2.4..+3.0 pp), N=1151, clusters=283.
- inside next-touch bucket 2: -1.8 pp (-5.8..+2.3 pp), N=553, clusters=251.
- inside next-touch bucket 3+: +1.6 pp (-2.3..+5.8 pp), N=598, clusters=220.

## stability

| slice | N | coef | 95% |
|---|---:|---:|---|
| 2020 | 213 | -3.4 pp | -10.9..+2.9 pp |
| 2021 | 230 | -3.2 pp | -10.4..+4.2 pp |
| 2022 | 216 | +5.5 pp | -0.7..+12.4 pp |
| 2023 | 238 | +1.3 pp | -3.2..+5.7 pp |
| 2024 | 254 | +0.4 pp | -6.5..+7.8 pp |
| DAY | 696 | +0.6 pp | -3.2..+4.3 pp |
| WEEK | 340 | -1.1 pp | -6.7..+4.5 pp |
| MONTH | 115 | -1.3 pp | -8.9..+8.0 pp |
| side_resistance | 556 | -2.5 pp | -6.7..+1.4 pp |
| side_support | 595 | +2.0 pp | -1.8..+6.1 pp |

Busiest year share 22.1%. Busiest family share 60.5%.

## sensitivity

- linear −bars, per 1 SD faster: +0.5 pp (-2.2..+3.3 pp), N=1151, clusters=283.
- overshoot, per 1 SD deeper: +1.2 pp (-2.0..+4.3 pp), N=1151, clusters=283.

## falsification

- pseudo-level primary: +1.2 pp (-1.9..+4.3 pp), N=1055, clusters=245.
- control 2020: N=208, +4.8 pp (-1.2..+10.9 pp).
- control 2021: N=331, -2.5 pp (-8.6..+3.2 pp).
- control 2022: N=218, +1.4 pp (-5.9..+8.2 pp).
- control 2023: N=130, +15.5 pp (+5.0..+27.8 pp).
- control 2024: N=168, -9.0 pp (-17.2..-0.5 pp).

## information

Analysis pairs N=1151. Clusters=283. Next-touch buckets {'2': 553, '3+': 598}. Ambiguous next touches excluded: 4.

## limitations

The cohort is conditional on two events: the previous independent touch was REJECT_FIRST, and the same zone was later touched again. The estimate is about levels with an observed rejection that were retested. It is not a causal effect of a strong rejection on every level. Touch number already predicts BREAK_FIRST in LEVEL_TOUCH_DEGRADATION_V1, so the primary coefficient is the one that still adjusts for the next touch's bucket. Several pairs can share a level; day and week pairs are clustered on the product week of the next touch, and month pairs on the episode. That does not model every shared path. A 5m bar that hits both barriers is dropped rather than ordered. The sample is one venue and one symbol, 2020–2024, on a surface already exposed for level research. A historical frequency in this cohort is not a current probability.

## search exposure

28 predeclared contrasts. Primary multiplicity family size 1. No contrast was added after the rates were read.

## method before outcome

`c8a1d4d2ac91b769aa8091b006c320df4b352f5e` — `docs/research/LEVEL_REJECTION_MEMORY_V1_DESIGN.md`.

## evidence summary

Among structural BTC levels whose previous independent touch was REJECT_FIRST and that were tested again, one SD faster prior rejection (frozen −log bars to the reject barrier) lined up with a -0.1 pp difference in the next touch's 4h BREAK_FIRST frequency after adjustment for touch ordinal, family, side, volatility tercile, year and log wait (N=1151, 95% -2.9..+2.6 pp).

## claim decision

Ladder: `L2`. PRODUCT_INTEGRATION_CANDIDATE = NO.

В истории структурных уровней BTC, которые ранее дали REJECT_FIRST и позже были протестированы снова (PDH/PDL, PWH/PWL, PMH/PML; Binance USD-M, 2020–2024), более быстрый предыдущий rejection на 1 SD по −log(числа 5m баров до reject-барьера) был связан с отличием частоты BREAK_FIRST на следующем независимом касании на -0.1 pp после выравнивания по номеру следующего касания, типу уровня, стороне подхода, терцилю волатильности, году и логарифму ожидания после rejection (N=1151; 95% интервал -2.9..+2.6 pp). Это частота в когорте уровней с наблюдавшимся rejection и последующим тестом, не текущая вероятность пробоя и не причинное усиление уровня.

Not integrated. No `/levels` change, no findings-registry edit, no deploy.

## successors not run

- LEVEL_APPROACH_STATE_V1
- LEVEL_CONFLUENCE_V1
