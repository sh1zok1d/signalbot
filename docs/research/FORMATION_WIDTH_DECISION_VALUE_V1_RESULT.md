# FORMATION_WIDTH_DECISION_VALUE_V1 — decision-value read

`outcome_read = true`
`evidence_class = POST_OUTCOME_CHARACTERIZATION / FORECAST_ARCHITECTURE_DEVELOPMENT`
`interpretation = WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN`

Point estimates favor a gain from width on at least one primary estimand, and the intervals do not all lie above zero.

No magnitude floor is applied. Product labels 0.80 / 0.95 / 0.99 were not adopted. Venues are not pooled. Width does not enter the forecast architecture in this unit. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

Read `2026-10-09T10:05:39Z`. Evaluator `b79a9e36a73c`.

## binance

- OOS N `1455`
- high rate `0.24261168384879725`
- decision-change rate `0.009621993127147767`
- changed `14`
- correct changes `8`
- harmful changes `6`
- upgrades `4` hit rate `0.5`
- downgrades `10` hit rate `0.6`
- net `0.0013745704467353953` interval `[-0.0034411562284927736, 0.006237222649436389]`
- Brier baseline `0.12343031000351473`
- Brier candidate `0.1234315638658109`
- Brier gain `-1.2538622961901123e-06` interval `[-0.001003668578568562, 0.0010193103821482337]`
- AUROC baseline `0.8463699788692205`
- AUROC candidate `0.8447684611548408`
- AUROC change `-0.0016015177143796633` interval `[-0.004624017444946393, 0.0012268419825246424]`

| test start | n test | change rate | net | Brier gain |
| --- | --- | --- | --- | --- |
| 2021-01-01 | 364 | 0.013736263736263736 | 0.008241758241758242 | 0.0018725255924849024 |
| 2022-01-01 | 363 | 0.01928374655647383 | -0.0027548209366391185 | -0.0021145290399659884 |
| 2023-01-01 | 363 | 0.0 | 0.0 | -0.000126594689591816 |
| 2024-01-01 | 365 | 0.005479452054794521 | 0.0 | 0.00035644994116170397 |

## bybit

- OOS N `1352`
- high rate `0.28106508875739644`
- decision-change rate `0.0036982248520710057`
- changed `5`
- correct changes `3`
- harmful changes `2`
- upgrades `2` hit rate `0.5`
- downgrades `3` hit rate `0.6666666666666667`
- net `0.0007396449704142012` interval `[-0.0022388477701113553, 0.0037425149700598802]`
- Brier baseline `0.1310349207515012`
- Brier candidate `0.13126987371224236`
- Brier gain `-0.00023495296074117734` interval `[-0.000889142861202315, 0.00042004189670593006]`
- AUROC baseline `0.8612559562486463`
- AUROC candidate `0.8601269763915963`
- AUROC change `-0.001128979857049961` interval `[-0.00312715116574063, 0.000943636618526019]`

| test start | n test | change rate | net | Brier gain |
| --- | --- | --- | --- | --- |
| 2021-01-01 | 351 | 0.002849002849002849 | -0.002849002849002849 | 0.0004091142642342059 |
| 2022-01-01 | 362 | 0.0027624309392265192 | 0.0027624309392265192 | -0.0012110492757595136 |
| 2023-01-01 | 331 | 0.0 | 0.0 | -0.0003340311627541863 |
| 2024-01-01 | 308 | 0.00974025974025974 | 0.003246753246753247 | 0.00028476832152045904 |

Descriptive cuts and quartile slices are not route inputs.

WIDTH_SIGNAL_PRESENT_DECISION_VALUE_UNCERTAIN

Not a confirmation. Not a cause. Not a product change. Prospective forward association was not read.
