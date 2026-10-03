# Divergence panel feasibility V0 — report

**Verdict:** `INFORMATIONALLY_WEAK`. 15 pp is not testable to standard on the approved spend window. **Stop: the holdout is not spent.**
**Date:** 2026-10-02
**Design:** `DIVERGENCE_PANEL_FEASIBILITY_V0_DESIGN.json`, frozen in `1404346` before any download or count
**Machine record:** `DIVERGENCE_PANEL_FEASIBILITY_V0_REPORT.json`
**Data manifest:** `docs/research_data/DIVERGENCE_PANEL_V0_BINANCE_UM/DATASET_MANIFEST.json`

```
OUTCOMES_COMPUTED                  = false (no symbol; SOL/XRP/BNB/DOGE outcomes unopened)
PROTECTED_2025_2026_OPENED         = false (no byte dated 2025 or later)
DETECTOR                           = SEED0001_DETECTOR_V1 unchanged; BTC and ETH reproduce the frozen SEED-0001 digests
PIT_TRUNCATION_AUDIT               = 30/30 identical on each of the six symbols
GATE (STRESS power, interaction, 15 pp, projected spend layouts) = 0.655 / 0.609 < 0.80
NEXT_UNIT                          = OWNER_DECISION_AFTER_DIVERGENCE_PANEL_FEASIBILITY_V0
```

## Data

| Object | Result |
|---|---|
| 1m klines 2022-11..2024-12, SOL / XRP / BNB / DOGE | 104/104 months verified against the published checksums; 0 incomplete 1h bars. BTC and ETH reuse the SEED-0001 objects. |
| bookDepth 2023-01-01..2024-12-31 | Missing in the archive: BNB 2023-02-08, 2023-02-09, 2023-11-16; DOGE 2023-02-08, 2023-02-09, 2024-04-18; SOL 2023-02-08, 2023-02-09, 2023-11-13, 2024-04-18; XRP 2023-02-08, 2023-02-09, 2023-11-01. Book-hour coverage is 98.4–98.6% on every symbol, above the 95% floor. |

## Counts by symbol (decisions 2023-01-01..2024-12-28)

| Symbol | A | B | C | D | A distinct dates | 48h chains (within symbol) |
|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | 36 | 259 | 63 | 385 | 33 | 71 |
| ETHUSDT | 32 | 264 | 48 | 392 | 27 | 75 |
| SOLUSDT | 28 | 262 | 58 | 382 | 24 | 81 |
| BNBUSDT | 28 | 193 | 52 | 462 | 25 | 82 |
| DOGEUSDT | 16 | 233 | 56 | 433 | 16 | 76 |
| XRPUSDT | 16 | 223 | 53 | 464 | 16 | 80 |
| **Panel** | **156** | **1434** | **330** | **2518** | | |

## Nominal versus distinct units (panel)

| Unit | All arms | A | C |
|---|---:|---:|---:|
| nominal episodes | 4438 | 156 | 330 |
| distinct decision times | 2085 | 135 | 259 |
| distinct UTC dates | 666 | 110 | 215 |
| panel-wide week clusters | 101 | 67 | 89 |
| market chains (24h, all symbols) | 138 (mean 32, max 147) | 96 (A only) | |
| market chains (48h, all symbols) | 14 (max 1560) | | |

The 48h single-linkage chains merge nearly the whole period into 14 clusters. With six symbols and overlapping windows, "independent market events" barely exist at that scale. The planned inference therefore clusters by panel-wide UTC week, and power is computed with shared cross-symbol shocks.

## Cross-symbol overlap of A episodes

| Another symbol has an episode… | any arm | an A episode |
|---|---:|---:|
| at the same decision hour | 115 / 156 (74%) | 38 / 156 (24%) |
| within ±6h | 147 (94%) | 51 (33%) |
| within ±24h | 156 (100%) | 83 (53%) |

**Concentration of A:**
- **By symbol:** max share 23% (BTC); HHI 0.18.
- **By half-year:** 43 / 37 / 32 / 44 (max share 28%).
- **Rule check:** no symbol exceeds the 50% rule.

## Dependence and effective N

**Planned inference.**
- **Model:** a linear probability model with symbol fixed effects.
- **Variance:** CR1 with panel-wide UTC-week clusters, t(G − 1). All symbols in a week form one cluster, so any within-week cross-symbol correlation is allowed.
- **Residual dependence across week boundaries** remains a known limitation.

**Profiles, all on synthetic outcomes:**

| Profile | Shock |
|---|---|
| INDEPENDENT | none (diagnostic) |
| BASE | one per UTC date, shared by all symbols and arms, latent ICC 0.25 |
| **STRESS (gate)** | one per (UTC date, arm), shared across symbols, latent ICC 0.50 |
| COLLAPSED | same-day same-arm episodes merged into one unit |

**Design effect on the interaction variance:** BASE 1.03 and STRESS 1.35. Under STRESS the 4438 nominal episodes are worth about 3290 independent ones. The binding constraint is the small A and C cells, not the large B and D cells.

## Power (interaction `(A − B) − (C − D)`; key secondary `A − B`)

**2023–2024 layout (101 weeks).** This is for reference; the surface is spent for BTC and ETH.

| Profile | Interaction at 10 / 15 / 20 pp | A − B at 15 pp | MDE80 interaction |
|---|---|---:|---:|
| INDEPENDENT | 0.48 / 0.85 / 0.98 | 0.95 | 0.150 |
| BASE | 0.50 / 0.83 / 0.98 | 0.94 | 0.150 |
| **STRESS** | 0.38 / **0.71** / 0.93 | 0.87 | 0.175 |
| COLLAPSED | 0.35 / 0.67 / 0.90 | 0.84 | 0.200 |

**Projected spend window (85 weeks = decisions 2025-01-01..2026-08-11).** The proxies are the first and the last 85 weeks of the 2023–2024 layout.

| Profile | First 85 weeks: 10 / 15 / 20 pp | Last 85 weeks: 10 / 15 / 20 pp | MDE80 interaction |
|---|---|---|---:|
| INDEPENDENT | 0.44 / 0.78 / 0.96 | 0.43 / 0.76 / 0.94 | 0.175 |
| BASE | 0.44 / 0.79 / 0.96 | 0.42 / 0.73 / 0.93 | 0.175 |
| **STRESS (gate)** | 0.33 / **0.655** / 0.87 | 0.33 / **0.609** / 0.86 | **0.200** |
| COLLAPSED | 0.31 / 0.61 / 0.85 | 0.31 / 0.58 / 0.82 | 0.200 |

**Key secondary A − B, STRESS, at 15 pp:** 0.82 and 0.78.

**Inference support:**
- **Minimum week clusters with A** on a projected layout: 55, against a 30 floor.
- **Minimum with C:** 73.
- **Alpha:** attainable, because the t reference is continuous.

## Episodes the frozen design would see in the spend window (estimate, no outcome)

This scales the 2023–2024 rates by the window length: 587 days versus about 707 mature decision days.

| Symbol | A | B | C | D |
|---|---:|---:|---:|---:|
| BTCUSDT | 30 | 215 | 52 | 320 |
| ETHUSDT | 27 | 220 | 40 | 326 |
| SOLUSDT | 23 | 218 | 48 | 318 |
| BNBUSDT | 23 | 161 | 43 | 384 |
| DOGEUSDT | 13 | 194 | 47 | 360 |
| XRPUSDT | 13 | 186 | 44 | 386 |
| **Panel** | **~130** | **~1193** | **~274** | **~2094** |

## Verdict

The frozen order applies:
1. **Data:** OK.
2. **Inference support:** OK (55 and 73 ≥ 30).
3. **Concentration:** OK (23% ≤ 50%).
4. **Power:** STRESS power of the interaction at 15 pp is 0.655 and 0.609 on the projected layouts, below 0.80. The verdict is **`INFORMATIONALLY_WEAK`**.

**The failure is not an artifact of the dependence model.** Even with episodes treated as independent, the projected power at 15 pp is 0.78 and 0.76, which also fails. Passing at 20 pp (STRESS 0.87 and 0.86) is not sufficient by the owner's rule.

## Required sample / history

**Extrapolation.** STRESS power of the interaction at 15 pp on the 2023–2024 panel layout stacked k times:

| Panel history at the 2023–2024 density | STRESS power at 15 pp |
|---|---:|
| 1.9 years (k = 1) | 0.71 |
| 3.9 years (k = 2) | 0.94 |
| 5.8 years (k = 3) | 0.995 |

The stacked copies are independent, so this is optimistic.

**What would reach 0.80.** About **2.5–3 years** of six-symbol panel history at this density, or about 1.6–1.9 times the approved 1.6-year spend window. That is roughly 200–240 A and 430–510 C episodes. The window itself would give about 130 A and 274 C.

## What this means (owner decision; nothing authorized here)

**Fact.** The 2025-01-01..2026-08-11 window cannot test a 15 pp interaction to standard with this panel and detector. By the owner's rule, the holdout is not spent, and no SEED-0003 prereg is written.

**Options that change the sample before any opening.** Each needs its own outcome-blind feasibility and an owner decision.
1. **A larger panel.** More UM perps with bookDepth since 2023, chosen by a fixed rule before counting. The gain shrinks with co-movement: the design effect is already 1.35.
2. **Spend window plus the prospective stream.** Add, in one pre-declared surface, the prospective panel stream after 2026-10-05, collected blinded until a fixed stop. That interacts with the SEED-0001 prospective leg, which is BTC only and must stay separate, so it needs its own design.
3. **A more efficient estimand,** declared before any opening. Examples: graded support and divergence strength instead of binary arms, or the A − B secondary as the primary. A − B reaches about 0.80 at 15 pp under STRESS on the projected layouts (0.82 and 0.78), so it is borderline.
4. **Accept a larger minimum effect.** The owner has excluded 20 pp as a sole basis.
