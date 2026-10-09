# DIRECTIONAL_STATE_SEARCH_V2 — RESULT (one bounded discovery cycle)

**Mode:** `DISCOVERY`. **Exposure class:** `ADAPTIVE_HISTORICAL_DISCOVERY`. **Claim ceiling:** `DISCOVERY_ONLY` (every number here is discovery on an exposed surface). `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `a361ff35fdb30cd051d7c6f6de1d4b9c70a5329f3250933963396a3d31b52c52` (commit `99205a3a`), frozen before this read. **Pre-outcome ledger SHA256:** `5ae1a8048666f339da62b9a07703a5858a0ca76bef367d6481f6dc55de2698e6`. **Evaluator digest:** `2c0dbd8f7e51ec5205333b848e12b8fc965142a23628dde8a4aa19b4d4180570`.
**Surface:** CORE_BTC_BINANCE_V0 BTCUSDT perpetual 2020-01-01..2024-12-31 (5m from 1m); CORE digest `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`; tzdata `2026c`.
**Parity:** close_pos_4h → R_1H on the discovery anchors reproduced exactly: N 175356, ρ -0.057773446228651.
**Bootstrap:** ISO-week block bootstrap of fixed rank residuals, 2000 draws, seed 20261120, 262 ISO weeks.

## Primary objects (target R_1H; incremental = partial Spearman given B0 = RP4H, RET_4H, RV_4H + listed extras)

| id | state | N | weeks | raw ρ [95 %] | incremental ρ [95 %] | z | years same sign | extra controls |
|---|---|---|---|---|---|---|---|---|
| F1a | `SPA_24H` | 175292 | 262 | -0.0224 [-0.0310, -0.0141] | **+0.0024** [-0.0066, +0.0111] | +0.54 | 4/5 | RET_24H, RV_24H |
| F1b | `UPFRAC_24H` | 175292 | 262 | -0.0156 [-0.0236, -0.0069] | **+0.0058** [-0.0019, +0.0150] | +1.34 | 4/5 | RET_24H, RV_24H |
| F2a | `OCC_MEAN_4H` | 175292 | 262 | +0.0256 [+0.0185, +0.0329] | **+0.0202** [+0.0130, +0.0277] | +5.31 | 4/5 | — |
| F3a | `REJ_DECAY_24H` | 25439 | 262 | +0.0013 [-0.0203, +0.0220] | **+0.0031** [-0.0176, +0.0233] | +0.29 | 3/5 | RP_24H |
| F4a | `CMD_UP_24H` | 175292 | 262 | -0.0187 [-0.0263, -0.0114] | **+0.0005** [-0.0079, +0.0086] | +0.13 | 2/5 | RET_24H |
| F6a | `US_OPEN_DRIVE` | 1258 | 262 | -0.0432 [-0.1026, +0.0158] | **-0.0297** [-0.0891, +0.0294] | -0.97 | 3/5 | — |
| F6b | `SESSION_HANDOFF` | 1258 | 262 | -0.0535 [-0.1100, +0.0024] | **-0.0556** [-0.1096, -0.0023] | -1.95 | 5/5 | — |
| F7a | `FLOW_RESPONSE_CHANGE_4H` | 175262 | 262 | -0.0051 [-0.0122, +0.0021] | **-0.0025** [-0.0102, +0.0051] | -0.63 | 3/5 | IMB_4H |
| F7b | `SIDE_ASYM_CHANGE_4H` | 175060 | 262 | +0.0036 [-0.0041, +0.0118] | **+0.0020** [-0.0061, +0.0105] | +0.49 | 3/5 | IMB_4H |

## Per-year incremental points

| id | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|
| F1a | +0.0121 | -0.0025 | +0.0010 | +0.0011 | +0.0119 |
| F1b | +0.0044 | +0.0148 | +0.0063 | +0.0233 | -0.0194 |
| F2a | +0.0218 | -0.0006 | +0.0238 | +0.0420 | +0.0194 |
| F3a | +0.0059 | +0.0124 | -0.0023 | -0.0371 | +0.0230 |
| F4a | -0.0096 | +0.0256 | -0.0173 | -0.0138 | +0.0109 |
| F6a | +0.0966 | -0.1239 | -0.0959 | -0.0355 | +0.0103 |
| F6b | -0.0538 | -0.0296 | -0.0026 | -0.0847 | -0.1118 |
| F7a | +0.0020 | -0.0039 | -0.0017 | +0.0014 | -0.0094 |
| F7b | +0.0033 | -0.0052 | +0.0185 | +0.0057 | -0.0072 |

## Quintiles (description only; P(UP), mean and median R_1H in bp)

**F1a `SPA_24H`** — all: P(UP) 0.5085, mean +0.59, median +0.68
- by state: Q1 0.527 / +0.85 / +2.28; Q2 0.525 / +0.93 / +1.96; Q3 0.505 / -0.66 / +0.37; Q4 0.495 / +0.73 / -0.41; Q5 0.491 / +1.07 / -0.82
- by residual of state on controls: Q1 0.506 / +0.45 / +0.44; Q2 0.517 / +0.79 / +1.46; Q3 0.506 / +0.44 / +0.58; Q4 0.505 / +1.61 / +0.43; Q5 0.508 / -0.37 / +0.53

**F1b `UPFRAC_24H`** — all: P(UP) 0.5085, mean +0.59, median +0.68
- by state: Q1 0.525 / -0.31 / +2.12; Q2 0.514 / +0.08 / +1.03; Q3 0.514 / +1.11 / +1.04; Q4 0.499 / +0.26 / -0.03; Q5 0.492 / +1.70 / -0.60
- by residual of state on controls: Q1 0.501 / -1.07 / +0.09; Q2 0.517 / +0.46 / +1.54; Q3 0.509 / +0.81 / +0.69; Q4 0.509 / +1.63 / +0.79; Q5 0.506 / +1.10 / +0.45

**F2a `OCC_MEAN_4H`** — all: P(UP) 0.5085, mean +0.59, median +0.68
- by state: Q1 0.491 / +0.70 / -0.66; Q2 0.494 / -0.17 / -0.54; Q3 0.510 / +0.58 / +0.87; Q4 0.515 / +0.15 / +1.20; Q5 0.534 / +1.67 / +2.74
- by residual of state on controls: Q1 0.491 / +0.81 / -0.65; Q2 0.499 / -0.16 / -0.07; Q3 0.506 / +0.16 / +0.44; Q4 0.517 / +0.86 / +1.41; Q5 0.530 / +1.27 / +2.43

**F3a `REJ_DECAY_24H`** — all: P(UP) 0.5050, mean -0.52, median +0.37
- by state: Q1 0.500 / -1.43 / -0.01; Q2 0.514 / -1.02 / +1.30; Q3 0.493 / -0.38 / -0.58; Q4 0.510 / +0.62 / +0.68; Q5 0.508 / -0.40 / +0.61
- by residual of state on controls: Q1 0.496 / -2.03 / -0.35; Q2 0.515 / -0.08 / +1.55; Q3 0.491 / -1.65 / -0.78; Q4 0.517 / +2.56 / +1.14; Q5 0.506 / -1.41 / +0.37

**F4a `CMD_UP_24H`** — all: P(UP) 0.5085, mean +0.59, median +0.68
- by state: Q1 0.526 / +0.22 / +2.27; Q2 0.518 / +0.75 / +1.42; Q3 0.510 / +0.73 / +0.70; Q4 0.500 / +0.38 / +0.01; Q5 0.489 / +0.84 / -0.92
- by residual of state on controls: Q1 0.513 / +0.01 / +1.10; Q2 0.512 / +0.62 / +0.94; Q3 0.511 / +0.29 / +0.80; Q4 0.502 / +1.43 / +0.16; Q5 0.505 / +0.58 / +0.37

**F6a `US_OPEN_DRIVE`** — all: P(UP) 0.4809, mean -3.81, median -3.92
- by state: Q1 0.516 / -0.20 / +3.13; Q2 0.530 / -1.55 / +3.95; Q3 0.492 / -4.74 / -2.21; Q4 0.458 / -8.05 / -5.43; Q5 0.409 / -4.52 / -10.13
- by residual of state on controls: Q1 0.512 / +2.20 / +1.12; Q2 0.506 / -7.84 / +2.27; Q3 0.468 / -11.00 / -5.97; Q4 0.482 / +6.42 / -2.14; Q5 0.437 / -8.81 / -8.26

**F6b `SESSION_HANDOFF`** — all: P(UP) 0.4881, mean -0.27, median -1.21
- by state: Q1 0.571 / +23.77 / +13.66; Q2 0.482 / -6.16 / -3.21; Q3 0.413 / -14.23 / -11.03; Q4 0.498 / -0.66 / +0.00; Q5 0.476 / -4.11 / -2.89
- by residual of state on controls: Q1 0.516 / +0.02 / +1.64; Q2 0.542 / +6.91 / +4.37; Q3 0.476 / +6.97 / -3.88; Q4 0.502 / -2.48 / +0.92; Q5 0.405 / -12.77 / -8.94

**F7a `FLOW_RESPONSE_CHANGE_4H`** — all: P(UP) 0.5085, mean +0.58, median +0.68
- by state: Q1 0.509 / +0.05 / +0.64; Q2 0.511 / +1.42 / +0.93; Q3 0.512 / +0.21 / +1.05; Q4 0.505 / +1.09 / +0.50; Q5 0.505 / +0.15 / +0.33
- by residual of state on controls: Q1 0.504 / -0.05 / +0.27; Q2 0.513 / +1.62 / +1.09; Q3 0.511 / +0.29 / +0.90; Q4 0.507 / +0.97 / +0.68; Q5 0.508 / +0.09 / +0.57

**F7b `SIDE_ASYM_CHANGE_4H`** — all: P(UP) 0.5085, mean +0.59, median +0.68
- by state: Q1 0.502 / +1.01 / +0.15; Q2 0.502 / -0.58 / +0.17; Q3 0.515 / +1.46 / +1.27; Q4 0.516 / +1.19 / +1.36; Q5 0.507 / -0.13 / +0.55
- by residual of state on controls: Q1 0.504 / +0.24 / +0.27; Q2 0.502 / +0.00 / +0.16; Q3 0.515 / +1.05 / +1.24; Q4 0.513 / +1.04 / +1.01; Q5 0.509 / +0.61 / +0.72

## Variant, sensitivity, placebo clocks, interactions

- **F2a-v** (variant of F2a, `OCC_THIRDS_4H`): raw +0.0255 [+0.0184, +0.0328]; incremental +0.0212 [+0.0140, +0.0287]; years same sign 4/5.
- **F7a-s** (sensitivity of F7a; controls RP4H, RET_4H, RV_4H, IMB_4H, LOG_LAMBDA_4H): -0.0023 [-0.0101, +0.0052].
- **F6a placebo clocks** (same statistic at every other anchor, N 174032): incremental -0.0293 [-0.0343, -0.0243]; clock − placebo -0.0004 [-0.0607, +0.0597].
- **F6b placebo clocks** (same statistic at every other anchor, N 174008): incremental -0.0118 [-0.0195, -0.0039]; clock − placebo -0.0438 [-0.0986, +0.0087].
- **Session Holm-adjusted p (F6a, F6b):** F6b 0.1024, F6a 0.3326
- **F2a × RP4H** (stage 2): interaction -0.0045 [-0.0111, +0.0023]; RP4H partial by state tercile: T1 -0.0371, T2 -0.0253, T3 -0.0391.
- **F6b × RP4H** (stage 2): interaction +0.0249 [-0.0316, +0.0858]; RP4H partial by state tercile: T1 +0.0903, T2 -0.0302, T3 -0.0322.

## Blocked before outcome

- **FAILED_PROGRESS:** inside the owner-closed divergence / selling-exhaustion line (catalog §6 price-only momentum divergence; E2 price leg)
- **OI_RESPONSE:** inside the owner-closed DH3 line (catalog E3/E4) or exact-consumed MARKET-01; OI-only read needs its own owner permit

## Search exposure and the promotion bar

Cells read in this cycle: 27. Bar (rules §4): family-wise α 0.10 Bonferroni over m = 840 (813 CORE × DIRECTION before + this cycle) → |z| ≥ 3.848.

| rank | id | |incremental| | interval excludes 0 | years same sign | z | clears bar | eligible |
|---|---|---|---|---|---|---|---|
| 1 | F2a | 0.0202 | True | 4/5 | +5.31 | True | True |
| 2 | F6b | 0.0556 | True | 5/5 | -1.95 | False | False |
| 3 | F6a | 0.0297 | False | 3/5 | -0.97 | False | False |
| 4 | F1b | 0.0058 | False | 4/5 | +1.34 | False | False |
| 5 | F1a | 0.0024 | False | 4/5 | +0.54 | False | False |
| 6 | F7a | 0.0025 | False | 3/5 | -0.63 | False | False |
| 7 | F3a | 0.0031 | False | 3/5 | +0.29 | False | False |
| 8 | F7b | 0.0020 | False | 3/5 | +0.49 | False | False |
| 9 | F4a | 0.0005 | False | 2/5 | +0.13 | False | False |

**TOP 3 by the frozen rule:** F2a.

Interpretation, the claim decision and the replication proposals are in the program's design note follow-up and the owner report; this file is the frozen evaluator output.
