# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1

**Evidence class:** `MODERN_TIME_DISJOINT_HISTORICAL_REPLICATION / QUESTION_FRESH_REPLICATION`.
**Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Route:** `RANGE_POSITION_MODERN_TEMPORAL_REPLICATION_SUPPORTED`.
**Design SHA256:** `9c510da7adff58996cc83f1c72c8ffd30f998161c5ad1aa665af27aa017b8370`.
**Series SHA256:** `64c1646acf7b371904ee6fcb25373383589e16c368d23267f136f4481f9894b9`.
**Evaluator digest:** `51d8aa6beccaa89dab428df9688268f84a2199311f985c84fd76fac90e2fb19b`.

One frozen modern-time replication. Not a search. The E1 holdout objects were not requested. No product file was changed.

## Sample

Grid slots `186048`, occupied `183168`, holes left missing `2880`.
Phase anchors `62015`. Analysis N `61016`. ISO weeks `92`.
Lost to the rejected August objects `980`. Lost to incomplete lookback `16`. Lost to incomplete future `3`.
T from `2025-01-01T04:15:00Z` through `2026-10-08T23:00:00Z`. Years `[2025, 2026]`.

## Estimates

Raw Spearman `-0.0416826229318`. Interval `-0.0526161522532` to `-0.0311930095123` (2000 / 2000 draws).

Partial given `RET_4H` `-0.0328891437174`. Interval `-0.0450323075058` to `-0.0208605997478`. Not used for the route. Canonical one-covariate helper matches.

Primary partial given `RET_4H` and `RV_4H` `-0.0330920941973`. Interval `-0.0451282598216` to `-0.021199227878`.

Robustness partial given `RET_4H`, `RV_4H`, `RET_1H` and `RET_15M` `-0.0208593343018`. Interval `-0.0331062199079` to `-0.0080108272084`. Not used for the route.

Spearman of position with `RANGE_WIDTH_4H`: `-0.00488047840181`. Partial also given width: `-0.0330739503531`. Diagnostic only.

## Quintiles

Full-sample bins of position. Not a route input.

| bin | N | P(UP) | mean R | median R |
|---|---|---|---|---|
| 1 | 12203 | 0.536835204458 | 1.1206445055e-05 | 0.000262059008151 |
| 2 | 12203 | 0.515528968286 | 7.24333644192e-06 | 8.50055519763e-05 |
| 3 | 12203 | 0.506432844383 | -3.20422724577e-05 | 4.38122243186e-05 |
| 4 | 12203 | 0.494304679177 | 4.16301094169e-05 | -3.36140103226e-05 |
| 5 | 12204 | 0.461569977057 | -0.000145923122535 | -0.000241471776925 |

## Years

| year | N | raw | primary |
|---|---|---|---|
| 2025 | 35023 | -0.0288106645822 | -0.0332694733015 |
| 2026 | 25993 | -0.0604752733646 | -0.0347841874703 |

## Halves

Median T `2025-11-14T23:07:30Z`.

| half | N | raw | primary |
|---|---|---|---|
| first | 30508 | -0.0278515545107 | -0.0325220801228 |
| second | 30508 | -0.0565107546865 | -0.0353693513853 |

BitMEX primary was `-0.04742832892681095`. Bybit primary was `-0.02784152009582924`. Binance 2020-2024 discovery raw was `-0.057773446228651215`. This file does not recompute those reads.

Modern temporal generalization established: `true`.
