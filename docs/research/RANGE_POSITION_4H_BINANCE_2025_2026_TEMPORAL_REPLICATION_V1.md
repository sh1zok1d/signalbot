# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1

**Route:** `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED`.
**Evidence class:** `TEMPORAL_HISTORICAL_REPLICATION / ONE_SHOT`. **Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `b38013d06f706057ddd1232609a375509771d4f65a04451bfcf511d496ae575d` (commit `6f4a5d32`), frozen before this read. **Sibling:** `RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1`; **parent:** `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1`.
**Objects:** `docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json` list SHA256 `5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621`. **Evaluator digest:** `1cb514ffcda3df199095e636badaca3c4e62474c012e5376223b2f10edd8edef`.
Nothing else was read: no spot, no BitMEX/Bybit/Binance 2020-24 outcome, no rejection or bars-since, no fees. The E1-RUN-001 window and the E1-development slice [2026-08-02, 2026-08-16) were never requested (pre-fixed exclusions).

## Sample
Grid slots 186048, bars 179136, holes 6912 (E1 window 2800, E1-development slice 4032, rest of the refused 25th 80, other 0). Phase anchors 62015, analysis N 59672, ISO weeks 90, T 2025-01-01T04:15:00Z .. 2026-10-08T23:00:00Z.

## Estimates
| Estimand | Point | 95 % week-block interval |
|---|---|---|
| Raw Spearman(RP4H, R_1H) | -0.043035 | [-0.053876, -0.032645] (2000/2000) |
| **Primary** partial given RET_4H, RV_4H | -0.034441 | [-0.047298, -0.021718] (2000/2000) |
| Secondary 1 (parent): partial given RET_4H | -0.034233 | [-0.047056, -0.021608] (2000/2000) |
| Secondary 2 (local path): given RET_4H, RV_4H, RET_1H, RET_15M | -0.022229 | [-0.034977, -0.008860] (2000/2000) |

Width diagnostic: Spearman(RP4H, width) -0.005658; partial also given width -0.034426. Attenuation by RET_4H -0.008802, share 0.204534.

## Quintiles (description, no gate)
| bin | N | P(UP) | mean R | median R |
|---|---|---|---|---|
| 1 | 11935 | 0.538919 | 1.737172197723849e-05 | 0.00029061685148977544 |
| 2 | 11934 | 0.515418 | 9.440297318684437e-06 | 8.666364115485984e-05 |
| 3 | 11934 | 0.506033 | -3.755670341771375e-05 | 4.539994334978772e-05 |
| 4 | 11934 | 0.494134 | 4.0279267339773676e-05 | -3.575154124317131e-05 |
| 5 | 11935 | 0.460829 | -0.00015167030993742142 | -0.0002542732940493336 |

## Years and halves
| piece | N | raw | primary |
|---|---|---|---|
| 2025 | 35023 | -0.028811 | -0.033269 |
| 2026 | 24649 | -0.064634 | -0.038413 |
| first | 29836 | -0.027801 | -0.030806 |
| second | 29836 | -0.059041 | -0.040025 |

