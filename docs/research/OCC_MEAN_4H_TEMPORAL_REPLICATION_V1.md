# OCC_MEAN_4H_TEMPORAL_REPLICATION_V1

**Route:** `OCC_TEMPORAL_REPLICATION_INCREMENTAL_SUPPORTED`.
**Evidence class:** `HISTORICAL_TEMPORAL_REPLICATION / QUESTION_FRESH_REPLICATION`. **Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `788029c561570900bab4f54682265c98cc08bfb22d791a8339ec395afa9cf75d` (commit `e7f88ad8`), frozen before this read. **Evaluator digest:** `225449cdfdfba68a6defe56786cbd128a1cfc134718c7c0135ac9e3388961e72`.
**Series:** `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz` SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`. Nothing else was read: spot, Binance 2025/2026, CORE, OCC variants, other horizons, interactions, OI, E1.

## Sample
Rows 382033, holes 288 (the documented gap), zero-trade bars kept 22728. Analysis N 127303, ISO weeks 191, T 2016-05-13T16:00:00Z .. 2019-12-31T23:00:00Z.

## Estimates (95 % ISO-week block interval)

| Estimand | Point | 95 % interval | valid draws |
|---|---|---|---|
| Raw Spearman(OCC, R_1H) | +0.035503 | [+0.027351, +0.043547] | 2000/2000 |
| Secondary A: partial | B0 (parity with discovery) | +0.029897 | [+0.020874, +0.039062] | 2000/2000 |
| Secondary B: partial | B0 + RET_1H | +0.012488 | [+0.003790, +0.021174] | 2000/2000 |
| **PRIMARY: partial | B1 = B0 + RET_1H + RET_15M** | +0.010961 | [+0.002143, +0.019867] | 2000/2000 |

Discovery (Binance 2020–24, not recomputed): partial | B0 +0.0202 [+0.0130, +0.0277]; local-path-controlled discovery point not computed.

## Years and halves (points)

| piece | N | raw | B0 | B0 + RET_1H | PRIMARY B1 |
|---|---|---|---|---|---|
| 2016 | 22188 | +0.028193 | +0.018893 | +0.004175 | -0.000188 |
| 2017 | 35038 | +0.028102 | +0.013781 | -0.001527 | -0.002426 |
| 2018 | 35040 | +0.045055 | +0.038995 | +0.016711 | +0.015587 |
| 2019 | 35037 | +0.032973 | +0.041732 | +0.021894 | +0.019829 |
| first | 63652 | +0.027541 | +0.016248 | +0.003439 | +0.002315 |
| second | 63651 | +0.042967 | +0.043587 | +0.019554 | +0.017658 |

All anchors: P(UP) 0.5115, mean +0.86 bp, median +1.22 bp.

## Quintiles (description only; P(UP) / mean bp / median bp)

- OCC: Q1 0.4877 / +0.57 / +0.00; Q2 0.4928 / -1.19 / +0.00; Q3 0.5164 / +0.84 / +1.49; Q4 0.5215 / +2.75 / +2.07; Q5 0.5392 / +1.35 / +3.27
- OCC residual on B1 ranks: Q1 0.4981 / +0.53 / +0.00; Q2 0.4995 / +1.25 / +0.00; Q3 0.5143 / +1.01 / +1.42; Q4 0.5229 / +1.79 / +2.23; Q5 0.5229 / -0.26 / +1.81
