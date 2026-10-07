# LEVEL_TOUCH_DEGRADATION_V1 — result

Design note commit `65015c2b707b0f455ea61f790a3e5fb4d15bf7c4`.
Tracks: STRUCTURE, PRODUCT_EVIDENCE. Claim ceiling recorded below. One run.

## estimate

Among structural BTC levels that reached the touch, the 2020–2024 historical BREAK_FIRST frequency was 40.1% on touch 1 (N=1905), 37.6% on touch 2 (N=1101) and 33.6% on touch 3+ (N=1185); the touch-1-standardized differences were -2.3 pp (95% -6.0..+1.5 pp) and -6.6 pp (95% -10.7..-2.2 pp).

| bucket | N | BREAK_FIRST | REJECT_FIRST | NEITHER | ambiguous (excluded) |
|---|---:|---:|---:|---:|---:|
| 1 | 1905 | 40.1% | 50.3% | 9.6% | 14 |
| 2 | 1101 | 37.6% | 50.5% | 11.9% | 4 |
| 3+ | 1185 | 33.6% | 49.3% | 17.1% | 4 |

Standardized Δ(touch 2 − touch 1) = -2.3 pp, 95% -6.0..+1.5 pp, retained touch-1 weight 0.979003.
Standardized Δ(touch 3+ − touch 1) = -6.6 pp, 95% -10.7..-2.2 pp, retained touch-1 weight 0.979003.
Crude companions: Δ2 -2.5 pp (-6.0..+1.0 pp), Δ3 -6.5 pp (-9.4..-3.5 pp).

Reading of these same rates, added at closeout, with no new contrast: REJECT_FIRST stays near 50% (50.3% / 50.5% / 49.3%) while NEITHER rises from 9.6% to 17.1% as BREAK_FIRST falls. The touch-3+ difference is fewer resolved breaks among levels that were retested, not a higher rejection rate, and not the saying that a level weakens with each touch. 2023 crude Δ3 is about zero (+0.1 pp). Support-side crude Δ3 is −1.9 pp; resistance-side crude Δ3 is −10.9 pp. Week and month families show a larger crude Δ3 than the day family. The pseudo-level control moves the other way.

## uncertainty

95% percentile interval from 2000 resamples of the product week of the touch, seed 20261007. Not a p-value and not a Holm-adjusted interval. Two primary contrasts were predeclared; the intervals are unadjusted and the claim sentence cites only those two.

## information

Analysis N = 4191 (ambiguous same-bar events excluded). Week clusters = 258. Feature-eligible preflight N = 4213. Planning MDE at rate 0.5 and DEFF 1.25 was about 6 pp; the week-cluster upper bound (DEFF = events/weeks) was about 21 pp. Those are amounts of information, not gates.

## stability

| year | N1 | N2 | N3+ | crude Δ2 | crude Δ3 |
|---|---:|---:|---:|---:|---:|
| 2020 | 331 | 193 | 218 | -1.7 pp | -7.3 pp |
| 2021 | 394 | 232 | 257 | -7.1 pp | -10.8 pp |
| 2022 | 395 | 234 | 204 | -5.3 pp | -7.7 pp |
| 2023 | 390 | 220 | 225 | -0.1 pp | +0.1 pp |
| 2024 | 395 | 222 | 281 | +1.8 pp | -6.5 pp |

Busiest year share of analysis events: 21.4%. Busiest family share of touch 3+: 42.2%.

Family crude Δ3: DAY -4.5 pp (N3=480), WEEK -16.3 pp (N3=500), MONTH -13.9 pp (N3=205).

Approach-side crude Δ3: resistance -10.9 pp, support -1.9 pp.

## falsification

Pseudo-level standardized Δ2 +7.3 pp (+3.8..+10.7 pp), Δ3 +4.7 pp (-0.1..+9.8 pp).

Control crude Δ3 by year: 2020 +6.0 pp, 2021 +1.6 pp, 2022 +9.1 pp, 2023 +5.7 pp, 2024 +1.4 pp.

## limitations

Touch 2 and touch 3+ exist only for levels that were retested, so the contrast is conditional on survival to that touch and is not a causal effect of the touch. Touches of the same level, and levels in the same week, are dependent; the interval resamples weeks and does not model a richer dependence. The same price path can host several structural levels; confluence merges those that share a zone, and the rest still share the week shock. A 5m bar that hits both barriers is dropped rather than ordered. The sample is one venue and one symbol, 2020–2024, on a surface already exposed for level research. The association can differ by family and by year. REJECT_FIRST stays near 50% across buckets while NEITHER rises from 9.6% to 17.1% as BREAK_FIRST falls, so the touch-3+ difference is fewer resolved breaks, not a higher rejection rate. 2023 crude Δ3 is about zero, and the support-side crude Δ3 is much smaller than the resistance-side one. The pseudo-level control moves the other way. A historical frequency in this cohort is not a current probability.

## search exposure

42 predeclared contrasts. Primary multiplicity family size 2. No contrast was added after the rates were read. Sensitivity and slices are descriptive and cannot replace contrasts 1 and 2.

## sensitivity

- zone_half_0.0003: Δ2 -4.0 pp (-7.8..-0.3 pp), Δ3 -7.8 pp (-12.1..-3.3 pp), analysis N=4090.
- barrier_fraction_1: Δ2 -4.0 pp (-7.3..-0.8 pp), Δ3 -8.9 pp (-12.9..-4.8 pp), analysis N=4207.
- horizon_12: Δ2 -6.8 pp (-10.0..-3.4 pp), Δ3 -12.3 pp (-15.8..-8.6 pp), analysis N=4191.

## method before outcome

`65015c2b707b0f455ea61f790a3e5fb4d15bf7c4` — `docs/research/LEVEL_TOUCH_DEGRADATION_V1_DESIGN.md`.

## evidence summary

Among structural BTC levels that reached the touch, the 2020–2024 historical BREAK_FIRST frequency was 40.1% on touch 1 (N=1905), 37.6% on touch 2 (N=1101) and 33.6% on touch 3+ (N=1185); the touch-1-standardized differences were -2.3 pp (95% -6.0..+1.5 pp) and -6.6 pp (95% -10.7..-2.2 pp).

## claim decision

Ladder: `L2`. PRODUCT_INTEGRATION_CANDIDATE = YES.

- touch2: В истории независимых касаний заранее известных структурных уровней BTC (PDH/PDL, PWH/PWL, PMH/PML; Binance USD-M, 2020–2024) среди уровней, дошедших до этого теста, BREAK_FIRST за 4ч был в 37.6% против 40.1% при первом касании (-2.3 п.п. после выравнивания по типу уровня, стороне подхода и терцилю волатильности; N₁=1905, N=1101; 95% интервал -6.0..+1.5 п.п.). Это частота в той когорте, не текущая вероятность пробоя.
- touch3: В истории независимых касаний заранее известных структурных уровней BTC (PDH/PDL, PWH/PWL, PMH/PML; Binance USD-M, 2020–2024) среди уровней, дошедших до этого теста, BREAK_FIRST за 4ч был в 33.6% против 40.1% при первом касании (-6.6 п.п. после выравнивания по типу уровня, стороне подхода и терцилю волатильности; N₁=1905, N=1185; 95% интервал -10.7..-2.2 п.п.). Это частота в той когорте, не текущая вероятность пробоя.

Not integrated. No `/levels` change, no findings-registry edit, no deploy.

## successors not run

- LEVEL_REJECTION_MEMORY_V1
- LEVEL_APPROACH_STATE_V1
- LEVEL_CONFLUENCE_V1
