# RP4H_TREND_REGIME_MODULATION_V1

**Route:** `TREND_REGIME_MODULATION_NOT_DETECTED`. **Clears the search bar:** False (z -1.44023 vs |z| ≥ 3.850).
**Mode:** `DISCOVERY`. **Claim ceiling:** `DISCOVERY_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `c1343df4a7399e9c5cb7bab475605c7b2b8feaa289bbbee953df47c8cc2d94d1` (commit `175c95e2`). **Evaluator digest:** `9da1b59324f9d5c26ef3af18f493ae244c8dd5ce623274f6f77ec78475e9b8de`.
**Surface:** CORE_BTC_BINANCE_V0 BTCUSDT perpetual 2020-01-01..2024-12-31 (5m from 1m). N 175292, ISO weeks 262. TS tercile edges 0.3603 / 0.8529; N by tercile [58431, 58430, 58431].

| Estimand | Point | 95 % interval | valid |
|---|---|---|---|
| RP4H partial | RET_4H, RV_4H — ranging tercile (T1, low TS) | -0.02906 | [-0.04037, -0.01644] | 2000/2000 |
| RP4H partial | RET_4H, RV_4H — middle tercile (T2) | -0.01651 | [-0.02933, -0.00383] | 2000/2000 |
| RP4H partial | RET_4H, RV_4H — trending tercile (T3, high TS) | -0.04228 | [-0.05393, -0.03029] | 2000/2000 |
| **PRIMARY Δ = T3 − T1 (B0 controls)** | -0.01322 | [-0.03203, +0.00461] | 2000/2000 |
| T1 with local path (B1) | -0.00671 | [-0.01698, +0.00396] | 2000/2000 |
| T3 with local path (B1) | -0.01952 | [-0.03199, -0.00747] | 2000/2000 |
| Δ with local path (B1) | -0.01281 | [-0.03125, +0.00441] | 2000/2000 |
| Continuous rank interaction RP4H × TS | -0.01187 | [-0.02021, -0.00403] | 2000/2000 |

## Years (points)

| year | N | T1 | T3 | Δ |
|---|---|---|---|---|
| 2020 | 35039 | -0.05302 | -0.06716 | -0.01414 |
| 2021 | 35040 | -0.00334 | -0.02153 | -0.01819 |
| 2022 | 35040 | -0.04548 | -0.06519 | -0.01972 |
| 2023 | 35040 | -0.02275 | -0.02864 | -0.00589 |
| 2024 | 35133 | -0.03118 | -0.03981 | -0.00863 |

## RP4H quintiles within regime (description only; P(UP) / mean bp / median bp)

- ranging_t1: Q1 0.5546 / +0.89 / +3.65; Q2 0.5294 / -0.09 / +1.92; Q3 0.5135 / +0.55 / +0.75; Q4 0.4956 / +0.34 / -0.29; Q5 0.4591 / +1.09 / -2.87
- trending_t3: Q1 0.5747 / +3.54 / +8.50; Q2 0.5317 / -0.64 / +2.89; Q3 0.5011 / -0.20 / +0.13; Q4 0.4864 / +1.82 / -1.37; Q5 0.4465 / +1.61 / -5.36
