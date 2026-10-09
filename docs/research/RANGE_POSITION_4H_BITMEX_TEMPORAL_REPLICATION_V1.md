# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1

**Route:** `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED`.
**Evidence class:** `TEMPORAL_HISTORICAL_REPLICATION / ONE_SHOT`. **Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `d9caaadd27da6e54f6f47fe372b4439cf0d208825dd61936af9688c77a88f2ad` (commit `52734bfb`), frozen before this read. **Parent:** `RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1` (`8132f181fd4ced19ee1c356a99022e195c005f0b2e95ac2135074ad7cc4c0e7d`).
**Series:** `docs/research_data/D2_BITMEX_PRE2020_XBTUSD/canonical_5m.jsonl.gz` SHA256 `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`. **Evaluator digest:** `2b55bd18012cf89b26a63104796fc125dffe1a209063b4e757192b22a0346494`.
Nothing else was read: no Binance 2025-26, no spot, no Bybit or Binance 2020-24 outcome, no fees.

## Sample
Grid slots 382321, bars 382033, holes 288 (the documented gap); zero-trade bars kept 22728. Phase anchors 127440, analysis N 127303, ISO weeks 191, T 2016-05-13T16:00:00Z .. 2019-12-31T23:00:00Z.

## Estimates
| Estimand | Point | 95 % week-block interval |
|---|---|---|
| Raw Spearman(RP4H, R_1H) | -0.076018 | [-0.084128, -0.068304] (2000/2000) |
| **Primary** partial given RET_4H, RV_4H | -0.047428 | [-0.054898, -0.039664] (2000/2000) |
| Secondary 1 (parent): partial given RET_4H | -0.047161 | [-0.054599, -0.039440] (2000/2000) |
| Secondary 2 (local path): given RET_4H, RV_4H, RET_1H, RET_15M | -0.010628 | [-0.018597, -0.002444] (2000/2000) |

Width diagnostic: Spearman(RP4H, width) 0.016108; partial also given width -0.047290. Attenuation by RET_4H -0.028857, share 0.379602.

## Quintiles (description, no gate)
| bin | N | P(UP) | mean R | median R |
|---|---|---|---|---|
| 1 | 25461 | 0.581556 | 0.0003503277807978311 | 0.0006352375548247062 |
| 2 | 25460 | 0.541555 | -4.844774511460366e-05 | 0.0003655022321259188 |
| 3 | 25461 | 0.507796 | 2.8929223505369215e-05 | 7.823195779456579e-05 |
| 4 | 25460 | 0.483857 | 0.00023027505948982265 | -7.60779359500964e-05 |
| 5 | 25461 | 0.442873 | -0.00012918700434812078 | -0.00039715636567953333 |

## Years and halves
| piece | N | raw | primary |
|---|---|---|---|
| 2016 | 22188 | -0.115734 | -0.069732 |
| 2017 | 35038 | -0.062368 | -0.030232 |
| 2018 | 35040 | -0.081863 | -0.046403 |
| 2019 | 35037 | -0.076113 | -0.058521 |
| first | 63652 | -0.078054 | -0.047915 |
| second | 63651 | -0.078803 | -0.049751 |

