# DH3 — result: five cards of three (direction and range)

**Program:** `DIRECTIONAL_AND_RANGE_DH3` (`DH3_DESIGN.md`)
**Executed:** 2026-10-04, one shot per surface. The preregistration was committed and pushed first (`189ce8d`; `DH3_PREREG.json` sha256 `c1cddcc9…b315`).
**Machine records:** `DH3_RESULT_DISCOVERY.json`, `DH3_RESULT_REPLICATION.json`

```
EXECUTED = 14 of 15 (DH3-S2 INFORMATIONALLY_WEAK at feasibility)
PROMISING_PROTOTYPE = 2: DH3-P3 (crowd long -> fewer up-first moves), DH3-V3 (retested levels hold more often)
DH3-V3 replication (spot 2017-2019) = REPLICATION_INCONCLUSIVE: -0.71 pp, CI -4.75..+3.06 (underpowered; did not show the effect)
SIGNIFICANT BUT BELOW THE RANGE BAR (log 1.15) = P1 +13.4 %, O2 +9.6 %, L3 +6.5 %, S1 -5.9 %, V2 +2.3 %
NULL = P2, L1, L2, O3, V1; HETEROGENEOUS (sign changes by year) = O1, O3, S3
SUPPORTED = 0 | OBJECTS_2025_2026_USED = none | E1 / B2-06 untouched
```

## 1. Results (discovery; range effects as % change of the next-4h range, directional as pp)

| Cell | Question | N (state / comparator) | Adjusted effect | 95 % CI | Holm p | Skill | Class |
|---|---|---|---|---|---|---|---|
| **P3** | crowd long (long/short account ratio, top 20 % of its 30-day z) vs crowd short → up first in 4h | 14218 (7109 / 7109) | **−5.92 pp** (47.7 % vs 53.5 %) | −8.32 … −3.52 | 0.0015 | Brier +0.0024 | **PROMISING_PROTOTYPE** |
| P1 | OI built up over 4h in a quiet market → next 4h range | 12397 (3581 / 8816) | +13.4 % | +9.9 … +17.1 | 0.0015 | MSE +0.0077 | NO_INCREMENTAL (below the 15 % bar; magnitude varies by year) |
| P2 | OI flush (1h OI change, bottom decile) → range | 37147 (3715 / 33432) | +0.7 % | −1.3 … +2.7 | 0.50 | — | NO_INCREMENTAL |
| L1 | thin book (±1 % depth, bottom quintile of its 7-day median) → range | 101112 | +3.1 % | −0.3 … +6.9 | 0.14 | — | NO_INCREMENTAL |
| L2 | bid-heavy vs ask-heavy book (±1 %) → up first | 41076 | +0.21 pp | −1.23 … +1.58 | 0.78 | — | NO_INCREMENTAL |
| L3 | book not recovered 30 min after a sharp move → range | 4101 (1369 / 2732) | +6.5 % | +1.9 … +11.1 | 0.012 | MSE +0.0008 | NO_INCREMENTAL (below the bar) |
| O1 | DVOL-implied above realized → range | 65464 | +6.8 % | +3.6 … +9.9 | 0.0015 | MSE +0.0057 | NO_INCREMENTAL (heterogeneous: −9 / +5 / −8 / −1 % by year) |
| O2 | DVOL jump (1h, top decile) → range | 65464 (6548 / 58916) | +9.6 % | +6.6 … +12.5 | 0.0015 | MSE +0.0001 | NO_INCREMENTAL (below the bar; BTC alone +10.5 %) |
| O3 | DVOL rising with price over 24h → up first | 65464 | +0.56 pp | −0.58 … +1.70 | 0.34 | — | NO_INCREMENTAL (heterogeneous) |
| V1 | session high/low vs random level at the same distance → 4h hold | 120212 | −0.39 pp (45.3 % vs 45.7 %) | −0.90 … +0.11 | 0.13 | — | NO_INCREMENTAL |
| V2 | key level vs random level → range after the touch | 52004 | +2.3 % | +1.4 … +3.2 | 0.0015 | MSE +0.0003 | NO_INCREMENTAL (real but tiny) |
| **V3** | second touch of PDH/PDL after a retreat vs first touch → 4h hold | 13622 (4531 / 9091) | **+3.87 pp** (47.2 % vs 45.0 %) | +1.58 … +6.15 | 0.002 | Brier +0.0010 | **PROMISING_PROTOTYPE** |
| S1 | spot-led vs perp-led stress hour (1-second lead) → range | 4299 (967 / 3332) | −5.9 % | −10.1 … −1.4 | 0.016 | MSE +0.0020 | NO_INCREMENTAL (below the bar; opposite to the stated mechanism) |
| S3 | many perp prints ≥ 1M USD in a stress hour → range | 4299 | −3.9 % | −8.2 … +0.5 | 0.08 | — | NO_INCREMENTAL (heterogeneous) |
| S2 | spot-led stress → continuation | 4299 | — | — | — | — | INFORMATIONALLY_WEAK (MDE 6.7 pp), not run |

**P3 by year:** −16.4, −7.6, −3.7, −9.2 and −3.7 pp (2020–2024), all negative. Heterogeneity p 0.31, but its power is low, so it could not be reliably assessed. BTC only; the ratio is Binance's global long/short account ratio.

**V3 by year and coin:**
- years: +4.1, +6.1, +3.0, +4.4, +0.9 pp;
- coins: BTC +5.4, ETH −0.2, BNB +3.4, XRP +3.8, DOGE +3.6, SOL +8.0 pp.

**V3 replication** (spot BTC/ETH/BNB/XRP 2017–2019, frozen discovery model):
- 47.5 % vs 51.2 % raw; adjusted −0.71 pp (CI −4.75 … +3.06); Brier skill −0.001.
- The replication surface was planned underpowered (MDE 7.5 pp), so the frozen class is `REPLICATION_INCONCLUSIVE`. The status «Гипотеза» stays, and live tracking decides.
- **Reading:** the earlier era did not show the effect.

## 2. What the bot may say

| Status | Cells |
|---|---|
| «Гипотеза» (found on 2020–2024, not confirmed) | **P3** and **V3** |
| «Есть, но слабее порога» (below the 15 % range bar) | P1, O2, L3, S1, V2 |
| «Не подтвердилось» | P2, L1, L2, O1, O3, V1, S3 |

All are entries in `config/beta_research_findings.yaml`, in `/research` only. No alert text changes and no probability line is added to live screens: that needs a product change and a deploy go.

**What the two «Гипотеза» lines say:**
- **P3:** when the share of accounts long on Binance is unusually high, price went up first less often over the next 4h than when the crowd was short, 48 % vs 54 %.
- **V3:** a retested daily high or low held slightly more often than at the first touch, 47 % vs 45 %, and this did not repeat on 2017–2019.

## 3. What we learned

- **The first directional effect above the bar.** The crowd-positioning contrarian effect (P3) is the first directional effect in the project to pass discovery at the 3 pp bar with calibration. It is BTC only, has no earlier-era data, and needs live tracking (about 3,300 qualifying hours a year) before it can be «Проверено».
- **Range states are real but small.** OI build-up in quiet markets (+13 %), DVOL jumps (+10 %), an unrecovered book after a move (+6.5 %) and spot-led stress (−6 %) all move the next 4h range. All stay below the product's 15 % materiality bar after the volatility nuisance.
- **The book and options did not help direction.** Book imbalance, the DVOL/price co-movement and session extremes carry no directional information.

## 4. Records

- `DH3_DESIGN.md`, including §6, the pre-freeze correction
- `DH3_FEASIBILITY.{md,json}`
- `DH3_PREREG.json`
- `DH3_RESULT_{DISCOVERY,REPLICATION}.json`
- `SCIENTIFIC_TEST_LEDGER.json` (TF-DH3-P/L/O/V/S)
- `docs/research_data/DH3_*`
- `scripts/research/dh3/`
- `tests/research/test_dh3.py`
