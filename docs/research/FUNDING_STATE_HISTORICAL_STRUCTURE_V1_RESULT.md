# FUNDING_STATE_HISTORICAL_STRUCTURE_V1 — historical structure

`outcome_read = true`
`evidence_class = RETROSPECTIVE_HISTORICAL_STRUCTURE / AVAILABILITY_LIMITED`
`interpretation = INCREMENTAL_ASSOCIATION_UNCERTAIN`

The route uses only the incremental partial Spearman and its interval. There is no magnitude floor. Bins, years, shorter horizons, the absolute excursion, and the funding-sign split are descriptions.

Read `2026-10-09T11:34:47Z`. Evaluator `be9d9d511a80`.

- Funding events `4749`
- Analysis N `4659`
- ISO weeks `223`
- Zero raw rates `0`
- Dropped, state undefined `90`
- Dropped, path `0`
- Dropped, volatility window `0`
- Spearman `0.055772530537571544` interval `[0.0014817922680213926, 0.11027730322243834]`
- Partial Spearman `0.027762672485166194` interval `[-0.008055043619315706, 0.062366554178786546]`
- Valid partial draws `2000` / `2000`
- Share of partial draws above zero `0.941`

| bin | n | mean adverse 8h |
| --- | --- | --- |
| [0, 0.10) | 400 | 0.015845331534509736 |
| [0.10, 0.25) | 956 | 0.011305682792439436 |
| [0.25, 0.75) | 2694 | 0.013819220521512382 |
| [0.75, 0.90) | 380 | 0.017383730133809665 |
| [0.90, 1] | 229 | 0.023425563876680395 |

| year | n | spearman | partial |
| --- | --- | --- | --- |
| 2020 | 276 | 0.25335378217772964 | 0.11664688307459968 |
| 2021 | 1095 | -0.0011977094253379599 | -0.0018202059875871543 |
| 2022 | 1095 | -0.0005087471178070523 | 0.037573836349442516 |
| 2023 | 1095 | 0.10911105690212888 | 0.07357750007772305 |
| 2024 | 1098 | 0.0488511824222843 | 0.029373086948576592 |

| side | n | spearman |
| --- | --- | --- |
| positive_funding | 4105 | 0.06590973227687523 |
| negative_funding | 554 | -0.2526984506298927 |

| secondary | spearman | partial | route input |
| --- | --- | --- | --- |
| adverse_1h | 0.03957509983205247 | 0.002748912154690174 | False |
| adverse_4h | 0.04822279765907132 | 0.01547403632237566 | False |
| abs_excursion_8h | 0.07352234523798994 | 0.0359041701347571 | False |

INCREMENTAL_ASSOCIATION_UNCERTAIN

Evidence class stays retrospective and availability-limited. Not a point-in-time confirmation. Not a cause of the MARKET-03 drawdown change. Not a product change. Premium was not scored. Open interest was not opened.

## Reading

The raw rank association is small and its interval lies above zero. After the 8-hour realized-volatility control the point stays positive and the interval includes zero. The route is therefore `INCREMENTAL_ASSOCIATION_UNCERTAIN`.

Bin means are not monotone. The lowest mean is `[0.10, 0.25)`. The highest mean is the top bin. The bottom decile sits above the next bin and above the middle. The upper tail is the elevated part of the shape. That is a description, not a second hypothesis.

Year signs are not stable. The 2021 raw and partial estimates are essentially flat. The negative-funding side differs from the positive-funding side. That difference is a later-design candidate, not a claim of this unit.

The raw association is compatible with the MARKET-03 drawdown reduction and may help explain a small part of it. It does not establish that funding caused the reduction. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
