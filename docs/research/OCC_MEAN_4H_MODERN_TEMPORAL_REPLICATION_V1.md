# OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1

**Route:** `OCC_MODERN_NOT_REPLICATED`. **Status after the route:** `HISTORICALLY_REPLICATED_BUT_NOT_MODERNLY_STABLE`.
**Evidence class:** `MODERN_TIME_DISJOINT_HISTORICAL_REPLICATION / QUESTION_FRESH_REPLICATION`. **Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Design SHA256:** `6878c6e133c733a2142d494536b0e14afbe11862f7594b9b7a60c71e44184a56` (commit `39e84dfc`), frozen before this read. **Evaluator digest:** `94ea6902205dcde3ab79742f0ad2dff327b5ac84e06a4ea1c1e48c1df685af1a`.
**Objects:** `docs/research_data/RP4H_BINANCE_UM_BTCUSDT_5M_2025_2026_V0/MANIFEST.json` list SHA256 `5369e8dc265ada989fa048fd49e8d694a2478e69916338223fe118f0dd0db621`. E1 window: never requested (product guard; object level); E1-development slice: [2026-08-02, 2026-08-16) never requested (Unit B canonical exclusion). Not read: CORE / Binance 2020-24 (no B1 recomputation), spot, BitMEX, OCC variants, other windows, other horizons, interactions, OI, E1, PnL.

## Sample
Rows 179136, holes 6912 (E1 window 2800, E1-development slice 4032, rest of the refused 25th 80, other 0). Analysis N 59672, ISO weeks 90.

## Estimates (95 % ISO-week block interval; B 2000, seed 20261117)

| Estimand | Point | 95 % interval | valid draws |
|---|---|---|---|
| Raw Spearman(OCC, R_1H) | -0.000552 | [-0.016557, +0.014328] | 2000/2000 |
| Secondary: partial | B0 | +0.000548 | [-0.015262, +0.015104] | 2000/2000 |
| Secondary: partial | B0 + RET_1H | -0.000447 | [-0.014832, +0.012893] | 2000/2000 |
| **PRIMARY: partial | B1 = B0 + RET_1H + RET_15M** | -0.001693 | [-0.016249, +0.011947] | 2000/2000 |

## Years and halves (points; diagnostics only)

| piece | N | raw | B0 | B0 + RET_1H | PRIMARY B1 |
|---|---|---|---|---|---|
| 2025 | 35023 | +0.003025 | +0.006416 | +0.005495 | +0.004061 |
| 2026 | 24649 | -0.005851 | -0.009834 | -0.010692 | -0.011698 |
| first | 29836 | +0.000460 | +0.002897 | +0.003277 | +0.001858 |
| second | 29836 | -0.001625 | -0.003150 | -0.005023 | -0.006091 |

All anchors: P(UP) 0.5031, mean -0.24 bp, median +0.20 bp.

## Quintiles (description only; P(UP) / mean bp / median bp)

- OCC: Q1 0.5039 / +0.07 / +0.23; Q2 0.4992 / -0.05 / -0.07; Q3 0.5035 / -0.26 / +0.25; Q4 0.5044 / -0.15 / +0.27; Q5 0.5043 / -0.83 / +0.31
- OCC residual on B1 ranks: Q1 0.5024 / -0.34 / +0.16; Q2 0.4999 / +0.23 / +0.00; Q3 0.5026 / -0.22 / +0.17; Q4 0.5052 / -0.36 / +0.36; Q5 0.5052 / -0.53 / +0.30

## Cross-era comparison (quoted, not pooled, not recomputed)

| surface | OCC \| B0 | OCC \| B1 |
|---|---|---|
| Binance 2020–24 (discovery) | +0.0202 [+0.0130, +0.0277] | never computed |
| BitMEX 2016–19 | +0.0299 [+0.0209, +0.0391] | +0.0110 [+0.0021, +0.0199] |
| Binance 2025–26 (this unit) | +0.000548 [-0.015262, +0.015104] | -0.001693 [-0.016249, +0.011947] |

Heterogeneity (descriptive): modern − BitMEX PRIMARY -0.0127, approximate SE 0.0085 (from the two percentile intervals), z -1.49.
