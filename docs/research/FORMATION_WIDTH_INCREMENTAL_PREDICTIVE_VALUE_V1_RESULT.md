# FORMATION_WIDTH_INCREMENTAL_PREDICTIVE_VALUE_V1 — OOS read

`outcome_read = true`
`evidence_class = POST_OUTCOME_CHARACTERIZATION / MODEL_DEVELOPMENT`
`interpretation = POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO`

Point estimates favor a gain from width on both venues. The uncertainty intervals do not both lie entirely above zero.

The historical rule `rho >= +0.10` is not applied. The Bybit route `POSITIVE_BUT_BELOW_PRACTICAL_SCALE` is unchanged. Venues are not pooled. A future dedicated validation is not decided here. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

Read `2026-10-09T09:44:11Z`. Evaluator `29597cb6f547`.

## binance

- analysis N `1820`
- OOS N `1455`
- OOS ISO weeks `210`
- MSE baseline `0.04506725539102009`
- MSE candidate `0.044778529303822555`
- absolute improvement `0.00028872608719753256`
- relative improvement `0.006406560255166168`
- relative percent `0.6406560255166168`
- interval `[-0.0002194528657344146, 0.0008069594899082358]`
- share of bootstrap means above zero `0.851`
- Spearman baseline `0.7026846266851142`
- Spearman candidate `0.7068849157696045`

| test start | n train | n test | MSE baseline | MSE candidate | delta | relative |
| --- | --- | --- | --- | --- | --- | --- |
| 2021-01-01 | 365 | 364 | 0.030561876734962128 | 0.02964918721295321 | 0.0009126895220089165 | 0.02986366085839288 |
| 2022-01-01 | 729 | 363 | 0.05404004597458843 | 0.053921630464097786 | 0.00011841551049064647 | 0.0021912548065989744 |
| 2023-01-01 | 1092 | 363 | 0.04919966196378457 | 0.048307496210708345 | 0.0008921657530762267 | 0.018133574855309816 |
| 2024-01-01 | 1455 | 365 | 0.04649950542679073 | 0.04726378906463622 | -0.0007642836378454892 | -0.016436382082574724 |

## bybit

- analysis N `1613`
- OOS N `1352`
- OOS ISO weeks `201`
- MSE baseline `0.04392028870659988`
- MSE candidate `0.043634792115537384`
- absolute improvement `0.00028549659106249197`
- relative improvement `0.006500335026704653`
- relative percent `0.6500335026704652`
- interval `[-0.00015741674029945098, 0.0007445495241849586]`
- share of bootstrap means above zero `0.8965`
- Spearman baseline `0.7022674322712014`
- Spearman candidate `0.7058682258652623`

| test start | n train | n test | MSE baseline | MSE candidate | delta | relative |
| --- | --- | --- | --- | --- | --- | --- |
| 2021-01-01 | 261 | 351 | 0.0301108371638057 | 0.029630564747413927 | 0.0004802724163917721 | 0.015950151561015934 |
| 2022-01-01 | 612 | 362 | 0.05114146053140795 | 0.05111176755486416 | 2.9692976543795047e-05 | 0.0005806047820155516 |
| 2023-01-01 | 974 | 331 | 0.04713214155619246 | 0.046618326260651606 | 0.0005138152955408565 | 0.010901590264644972 |
| 2024-01-01 | 1305 | 308 | 0.04771876272518782 | 0.04759995086599917 | 0.00011881185918864723 | 0.0024898352849776154 |

POINT_ESTIMATES_FAVOR_GAIN_INTERVALS_DO_NOT_BOTH_EXCLUDE_ZERO

Not a confirmation. Not a cause. Not a product change. Prospective forward association was not read.
