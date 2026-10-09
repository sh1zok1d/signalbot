# EXPOSURE_COUNTERS_V1 — surface / target / family counters (initial compilation)

**Date:** 2026-10-09.
**Authority:** `RESEARCH_RULES_DECISION_V1.md` §4.
**Compiled:** read-only from atlas units/surfaces, `RESEARCH_LEDGER.md` WINDOWS_CONSUMED lines, unit records and the unmerged Cursor branches. Nothing was computed.

**What is counted:**
- Distinct feature→outcome cells whose **outcomes were read**, attributed to the surface where the outcome was read.
- Each unit's declared primary grid.
- **Not counted:** slices, sensitivities, controls, λ grids, and units closed before data.
- `*` marks a lower bound.

**Updating:** every unit adds its cells when its outcome is read, whatever the result. Design notes quote the counters as they stand before the unit.

## 1. Surface × target (cells)

| Surface | DIRECTION | LEVEL_RES | RANGE_VOL | PATH_STRESS | ACTIVITY | OTHER |
|---|---|---|---|---|---|---|
| CORE Binance perp BTC 2020–24 | **≈ 840\*** (≈317 recorded units + 496 PRE_IMPULSE_STATE_ATLAS_V1 cells + 27 DIRECTIONAL_STATE_SEARCH_V2 cells, 2026-10-09) | 140\* (≈1.8k counting declared material cells) | 110\* | 10 | 7\* | 4 |
| Binance perp BTC 2025–26 | ≈130\* (≈72 + ≈50 E1 development, §4 correction, + 4 RANGE_POSITION_4H Unit B + 4 OCC_MEAN_4H modern replication, 2026-10-09; Cursor's unmerged parallel RP4H read not yet counted) | 7\* | 8\* | 1 | 0 | 1 |
| Binance alts 2020–24 (incl. pooled ETH) | ≈67\* | 0 | 3 | 1 | 0 | 2 |
| Binance alts 2025–26 (divergence) | ≈60\* | 0 | 0 | 1 | 0 | 1 |
| Live forward 2026 (E1 development, P4) | ≈50\* | 0 | 4 | 0 | 0 | 0 |
| ETH Binance 2020–24 (ETH units) | 4\* | 0 | 2 | 0 | 0 | 1 |
| Binance spot BTC 2020–24 | 3 | 0 | 0 | 1 | 1 | 0 |
| **BitMEX XBTUSD 2016–19** | **8** (RANGE_POSITION_4H Unit A 4 + OCC_MEAN_4H replication 4, 2026-10-09; 0 before) | 1 | 1 | 1 | 0 | 1 |
| Bybit/OKX perp 2020–24 | 0 | 0 | 4 | 0 | 0 | 0 |
| Binance spot BTC 2017–19 | 1 | 2 | 0 | 0 | 0 | 0 |
| OKX spot 2022–24 | 0 | 0 | 0 | 0 | 0 | 1 |
| Binance spot alts 2017–19 | 1 | 0 | 0 | 0 | 0 | 0 |

**Main contributors to CORE × DIRECTION:**
- H02–H05 45 each.
- B2-02 12, B2-03 15, B2-04 15, B2-05 12.
- Divergence full history ≈60.
- SEED-0001 4.
- DH1/DH2/DH3 9.
- The generic hourly race stream 4.
- Product analogues 3\*.
- MARKET-01/02.
- PRE_IMPULSE_STATE_ATLAS_V1 (Cursor branch): 496 ledger cells, features × {1h, 4h, 8h, 24h} × {raw, hour-adjusted}; 24h logged but not ranked.
- DIRECTIONAL_STATE_SEARCH_V2 (2026-10-09): 27 cells, nine states × {raw, incremental} + variant, sensitivity, placebo clocks, stage-2 interactions; R_1H only.

**Main contributors to 2025–26 × DIRECTION:**
- divergence validation 10 and mechanism exploration ≈50 (pooled);
- P3_CONFIRMATION_V1 2;
- the generic-stream calibration feed of the level-race held-out read 4\*;
- the architect's unconditional read 3\*;
- product analogues 3\*;
- E1-RUN-001 development ≈50 (§4 correction);
- RANGE_POSITION_4H Unit B 4 (raw, primary, two secondaries; 2026-10-09);
- OCC_MEAN_4H modern replication 4 (raw, | B0, | B0 + RET_1H, PRIMARY | B1; 2026-10-09).

## 2. Family × target (all surfaces, cells counted once)

| Family | DIR | LR | RV | PS | ACT | OTH |
|---|---|---|---|---|---|---|
| PRICE_STRUCTURE | ≈235 (+ part of the 496 atlas cells) | 150 | 7 | 2 | 0 | 2 |
| VOLATILITY_STATE | 14 | 0 | 80 | 4 | 0 | 2 |
| FLOW | ≈83 | 0 | 1 | 0 | 1 | 0 |
| METHOD (E1, D5) | ≈50 | 0 | 0 | 1 | 0 | 0 |
| CALENDAR | 0 | 0 | 17 | 0 | 7 | 0 |
| DERIVATIVES | 6 | 0 | 6 | 3 | 0 | 0 |
| EVENTS | 0 | 0 | 8 | 0 | 0 | 0 |
| CROSS_ASSET | 2 | 0 | 1 | 1 | 0 | 2 |
| SPOT_PERP | 2 | 0 | 1 | 1 | 0 | 1 |
| OPTIONS | 1 | 0 | 3 | 0 | 0 | 0 |
| MICROSTRUCTURE | 1 | 0 | 2 | 0 | 0 | 0 |
| CROSS_VENUE | 0 | 0 | 0 | 0 | 0 | 0 |

The family split of the 496 PRE_IMPULSE cells follows that unit's feature registry when it is merged.

## 3. Search-exposure penalty in use

- **Promotion from discovery to question-fresh replication** needs the family-wise α 0.10 Bonferroni bound over `m_ST` plus the unit's own cells.
- **On CORE × DIRECTION**, `m_ST` ≈ 813 → p ≤ 1.2e-4 (|t| ≳ 3.8). RANGE_POSITION_4H (week-mean t ≈ −22) clears it.
- **After DIRECTIONAL_STATE_SEARCH_V2**, `m_ST` ≈ 840 → |z| ≳ 3.85 for the next CORE × DIRECTION unit (before its own cells).
- **BitMEX 2016–19 had 0 DIRECTION cells before Unit A; it has 8 now (Unit A 4, OCC_MEAN_4H replication 4).** It is still the least searched directional surface in the project. Binance 2025–26 has about 126 (§4 correction and Unit B), mostly from pooled divergence work and E1 development.

## 4. Known gaps

- Product V2 nightly statistics and the divergence mechanism exploration are approximate.
- Level Engine primary vs material cells (both shown above).
- H03/H05 orientations: two per cell, counted once.
- The architect's unconditional read: its exact number of variants was not recorded.
- Unmerged Cursor units carry `pending_merge` until merged.
- Full per-unit contributor lists are in the compilation transcript summary in the 2026-10-09 ledger entry.
- **Correction (2026-10-09, RP4H exposure audit):** the ≈50 E1-RUN-001 development cells counted under "Live forward 2026" are reads of Binance BTCUSDT perp 2026-08-02 … 08-16 and belong to BINANCE_PERP_BTC_2025_2026 × DIRECTION under rules §3 (same venue and period). Binance 2025–26 × DIRECTION is therefore ≈122\*.
