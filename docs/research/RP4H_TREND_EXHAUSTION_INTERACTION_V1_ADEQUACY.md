# RP4H_TREND_EXHAUSTION_INTERACTION_V1 — exact parity, exposure audit and information-adequacy gate

**Date:** 2026-10-11. **Author:** chief architect.
**Verdict:** **`TREND_EXHAUSTION_REPLICATION_INFORMATIONALLY_INSUFFICIENT`.** Under the frozen rule neither candidate surface is adequately powered at 1× the discovery magnitude. **No market interaction outcome was read**, and no replication will run under this rule.
**Records:**
- protocol `RP4H_TREND_EXHAUSTION_INTERACTION_V1_ADEQUACY_PROTOCOL.md`, frozen at commit `cf75f2c7` before any simulation summary;
- full record `RP4H_TREND_EXHAUSTION_INTERACTION_V1_ADEQUACY.json`;
- code `scripts/research/rp4h_trend_exhaustion_v1/`;
- tests `tests/research/test_rp4h_trend_exhaustion_v1.py`.

**Status kept:** `DISCOVERY_CANDIDATE_FROM_SIGN_REVERSED_PRIMARY_HYPOTHESIS`. Unit 1 stays `TREND_REGIME_MODULATION_NOT_DETECTED`.

## 1. Exact Unit-1 parity

| quantity | frozen definition (recovered from `scripts/research/rp4h_trend_regime_v1/`) |
|---|---|
| TS_24H | \|log(close_i/close_{i−288})\| / √(Σ_{k=i−287..i} log(close_k/close_{k−1})²), via `spa_family`; requires the 289 closes i−288..i (vacuous on CORE: 0 missing closes, identical TS on all 175,292 anchors) |
| RP4H, RET_4H, RV_4H, R_1H | the RP4H parent code on each surface's 5m grid; RP4H 15-minute anchor phase |
| **PRIMARY interaction_b0** | partial Spearman(R_1H, P \| RP4H, TS, RET_4H, RV_4H), with P = (rank RP4H − mean)(rank TS − mean). The Unit-1 function is imported; the vectorized twin equals it to 1e-12 (tests and validation) |
| discovery (CORE 2020–24) | −0.01187 [−0.02021, −0.00403], N 175,292, 262 weeks |
| secondary (no route) | the same with RET_1H and RET_15M in the controls; no CORE value exists |
| diagnostics | A: RP4H \| RET_4H, RV_4H. B: TS \| RP4H, RET_4H, RV_4H. Unit-1 tercile edges 0.3603 / 0.8529 as descriptive strata |

## 2. Exposure audit (read-only; current branch and all remote branches)

**Method:** a read-only grep and record audit. Nothing was computed.
- **Refs:** 148 (every remote ref: 132 `origin/*` including 51 Cursor branches, plus 13 `pr/*`, the local `pr383` and `pr387`, and HEAD), and the commit messages of `--all`.
- **Patterns:** RP4H and range-position names (incl. stochastic, %K, Williams, Donchian, close location) crossed with trend-strength names (TS_24H, \|RET_24H\|, efficiency, variance ratio, ADX, trend regime or tercile, exhaustion, strong or preceding move, chop, Hurst).

**BitMEX XBTUSD 2016–19: QUESTION_FRESH.** No EXACT or EQUIVALENT read.

| prior read | relation | class |
|---|---|---|
| RP4H Unit A; Cursor's BitMEX twin (`027948e2`) | RP4H → R_1H (raw, \| B0, \| local path), quintiles, years, halves; no trend split ("no … trend subset") | ADJACENT (subgroup source) |
| OCC_MEAN_4H replication | OCC \| B0/B1 | ADJACENT |
| Cursor's RP4H forecast prototype (`6c244233`, 2026-10-10; Track A) | additive logistic P(UP 1h) on RET_4H, RV_4H, RET_1H, RET_15M plus RP4H; no interaction, no trend strength | ADJACENT |
| D2 corrected replication | RV_24H > P90 × sign(RET_24H) → 24h aligned MAE; no position | ADJACENT / unrelated |
| D7, #357/#368 resolution, LEVEL_VOLATILITY_TRANSITION; DH1/DH2 (never reached replication); DH3 V3 (Binance spot 2017–19, retests; TREND24 signed, a nuisance on CORE) | — | NONE |

**Binance USD-M BTCUSDT 2025–26: QUESTION_FRESH.** No EXACT or EQUIVALENT read.

| prior read | relation | class |
|---|---|---|
| RP4H Unit B; Cursor's 2025–26 twin (`7b55fff4`; its file includes the E1-development slice) | RP4H partials, years 2025 and 2026 | ADJACENT (subgroup source) |
| OCC_MEAN_4H modern replication | OCC \| B0/B1 | ADJACENT |
| Cursor's forecast prototype (`6c244233`; Track A) | additive logistic, as above; its 2025–26 file includes the E1-development slice | ADJACENT |
| **E1-RUN-001 development** (2026-08-02 … 08-15) | **signed** strong-4h-regime gate × retracement from the 12h trend-leg extreme (TREND_PULLBACK); a context gate rejecting range-edge breakouts against a strong opposite 4h regime (CB/FB); direction-aligned outcome at 15m–4h; N 26–1,071 | **ADJACENT (the closest)**: signed rather than unsigned, not the 4h range; **inside the slice Unit B already excludes** |
| DIVERGENCE_FULL_HISTORY_RESEARCH_V0 (six symbols, to 2026-08-11) | selling exhaustion or divergence at swing lows in support; 22 features vs ±1R at 48h/96h; signed, bullish, episode-conditioned; no RP4H | ADJACENT (owner-closed exhaustion line) |
| P3_CONFIRMATION_V1; product analogue statistics; LEVEL_RACE and level statistics | no range position × trend strength | ADJACENT / unrelated |

**Notes:**
- **Borderline:** the E1 TP/CB/FB setups are the only read crossing a trend gate with range-edge position against direction. If the owner counts them as equivalent, the E1-development slice stays excluded, as on the Unit B surface.
- **Same period:** Binance spot 2017–19 covers the same years as BitMEX 2016–19 (protocol §3: not both).
- **Limits:** the audit is grep- and record-based. Uncommitted reads cannot be ruled out; the records show none for this interaction.
- **Track A (reported for the owner, not acted on):** Cursor's RANGE_POSITION_4H forecast prototype was executed on its branch, with `owner_go: true` (commit `6c244233`, 2026-10-10). This branch's records still describe it as frozen and unrun in a few places (e.g. ADAPTIVE_B1_FORECAST_V1_DESIGN §9). Its RESULT.json stores row-level outcomes for BitMEX and its 2025–26 file. **The interaction was not computed there,** so the classes above stand. Under the owner's Track A separation, Track A records were not edited and its outcome was not opened here.

## 3. Support (outcome-free)

| surface | anchors | ISO weeks | span | TS undefined (dropped) | share in Unit-1 terciles T1 / T2 / T3 |
|---|---|---|---|---|---|
| BitMEX XBTUSD 2016–19 | **127,143** | **191** | 2016-05-14 … 2019-12-31 | 160 (around the documented 288-bar gap) | 0.316 / 0.344 / 0.341 |
| Binance USD-M BTCUSDT 2025–26 | **59,512** | **90** | 2025-01-02 … 2026-10-08 | 160 (around the excluded E1 days) | 0.307 / 0.344 / 0.348 |

TS quantiles (10 / 50 / 90 %):
- BitMEX 0.104 / 0.604 / 1.430;
- Binance 0.114 / 0.617 / 1.485.

These are close to CORE's frozen terciles.

## 4. Synthetic DGP and calibration

**Model** (protocol §4): R = overlapping 12-bar noise + σ·(β_main·g_main + β_int·g_int).
- Primary DGP: the noise scale is past-only real volatility (bars k−60..k−13), i.e. heteroskedastic. Sensitivity DGP: homoskedastic.
- A main RP4H partial of −0.030 is planted at every level.
- Ladder: interaction 0 / 0.5 / 1 / 1.5 / 2 / 3 × (−0.01187).

**Calibration** (paired, 16 draws):

| surface | κ_int (hetero / homo) | κ_main (hetero / homo) |
|---|---|---|
| BitMEX | 0.904 / 0.976 | 0.842 / 0.977 |
| Binance 2025–26 | 0.940 / 0.977 | 0.917 / 0.977 |

**Checks:**
- **Planted main effect:** recovered at −0.029 to −0.033 at every level.
- **Bootstrap:** the canonical re-rank bootstrap of a real run against the fast one, 2 draws per surface at 1×. Width ratio 0.988–1.003, below the redo threshold of 1.10. The point equals the Unit-1 function to 1e-15.

## 5. Power curves (primary DGP, 400 replications per level)

**BitMEX XBTUSD 2016–19**

| level | P(SUPPORTED) | P(UNCERTAIN) | P(NOT) | P(SIGN_OPPOSES) | P(correct sign) | mean point | sd point | CI width 5/50/95 % |
|---|---|---|---|---|---|---|---|---|
| 0 | **0.058** | 0.562 | 0.367 | 0.013 | 0.620 | −0.0016 | 0.0050 | 0.0170 / 0.0189 / 0.0209 |
| 0.5× | 0.318 | 0.613 | 0.070 | 0 | 0.930 | −0.0074 | 0.0049 | |
| **1×** | **0.773** | 0.225 | 0.003 | 0 | 0.998 | −0.0131 | 0.0046 | 0.0173 / 0.0190 / 0.0210 |
| 1.5× | 0.968 | 0.033 | 0 | 0 | 1.000 | −0.0193 | 0.0050 | |
| 2× | 1.000 | 0 | 0 | 0 | 1.000 | −0.0252 | 0.0047 | |
| 3× | 1.000 | 0 | 0 | 0 | 1.000 | −0.0374 | 0.0049 | |

Homoskedastic sensitivity:
- null: P(SUPPORTED) 0.015, P(OPPOSES) 0.035;
- **1×: P(SUPPORTED) 0.670.**

**Binance USD-M BTCUSDT 2025–26**

| level | P(SUPPORTED) | P(UNCERTAIN) | P(NOT) | P(SIGN_OPPOSES) | P(correct sign) | mean point | sd point | CI width 5/50/95 % |
|---|---|---|---|---|---|---|---|---|
| 0 | **0.050** | 0.515 | 0.422 | 0.013 | 0.565 | −0.0011 | 0.0072 | 0.0245 / 0.0279 / 0.0315 |
| 0.5× | 0.163 | 0.632 | 0.205 | 0 | 0.795 | −0.0064 | 0.0073 | |
| **1×** | **0.440** | 0.525 | 0.035 | 0 | 0.965 | −0.0128 | 0.0071 | 0.0242 / 0.0280 / 0.0319 |
| 1.5× | 0.740 | 0.247 | 0.013 | 0 | 0.988 | −0.0189 | 0.0074 | |
| 2× | 0.938 | 0.062 | 0 | 0 | 1.000 | −0.0248 | 0.0069 | |
| 3× | 1.000 | 0 | 0 | 0 | 1.000 | −0.0365 | 0.0072 | |

Homoskedastic sensitivity:
- null: P(SUPPORTED) 0.015, P(OPPOSES) 0.025;
- **1×: P(SUPPORTED) 0.440.**

**MDE80 (primary DGP):**

| surface | MDE80 | as interaction |
|---|---|---|
| BitMEX | 1.07× | −0.0127 |
| Binance 2025–26 | 1.65× | −0.0196 |

**Pooled BitMEX + Binance 2025–26** (informational, never selectable):
- 1×: P(SUPPORTED) 0.90;
- null: P(SUPPORTED) 0.0625;
- SE ≈ 0.0040.

**Finding for any later read: a small negative null bias.**
- Under heteroskedastic noise with a real main RP4H effect and **no** planted interaction, the rank interaction has a mean of −0.0011 (Binance) and −0.0016 (BitMEX). Under homoskedastic noise it is 0.0000 / −0.0002.
- The rank transform pools volatility regimes, so part of a main effect leaks into the product term.
- The effect is about 1/3 SE. It inflates null false support on BitMEX to 0.058, and it would also be present in the CORE discovery.

## 6. Frozen adequacy criterion and surface rule (protocol §6–§7)

| criterion | BitMEX | Binance 2025–26 |
|---|---|---|
| null P(SUPPORTED) and P(OPPOSES) ≤ 0.05, primary DGP | **0.058** / 0.013 ❌ | 0.050 / 0.013 ✅ |
| same, sensitivity DGP | 0.015 / 0.035 ✅ | 0.015 / 0.025 ✅ |
| P(SUPPORTED \| 1×) ≥ 0.80, primary | **0.773** ❌ | **0.440** ❌ |
| P(SUPPORTED \| 1×) ≥ 0.80, sensitivity | **0.670** ❌ | **0.440** ❌ |
| **adequately powered** | **no** | **no** |

**Rule:**
- Binance 2025–26 is not adequate.
- BitMEX is not adequate: it misses power under both DGPs, and null control under the primary one.

→ **`TREND_EXHAUSTION_REPLICATION_INFORMATIONALLY_INSUFFICIENT`. No market outcome is read. STOP.**

Both surfaces are question-fresh (§2), so freshness does not change the verdict.

## 7. Routes frozen for any later run (protocol §8)

| route | condition |
|---|---|
| `TREND_EXHAUSTION_INTERACTION_REPLICATION_SUPPORTED` | point < 0 and the whole 95 % interval < 0 |
| `TREND_EXHAUSTION_INTERACTION_DIRECTION_COMPATIBLE_UNCERTAIN` | point < 0 and the interval includes 0 |
| `TREND_EXHAUSTION_INTERACTION_NOT_REPLICATED` | otherwise (point ≥ 0 with the interval including 0) |
| `TREND_EXHAUSTION_INTERACTION_SIGN_OPPOSES` | the whole interval > 0 |
| `IMPLEMENTATION_INVALID` | provenance, support or leakage failure, or < 1,900 valid draws |

The interval is the ISO-week block bootstrap with ranks recomputed per draw (B 2000, seed 20261125). There is no magnitude threshold.

## 8. What this does and does not say

**It does not say** the interaction is absent. A replication on either single surface could not reliably separate an effect of the discovery's size from none:
- BitMEX: power 0.67–0.77 at 1×;
- Binance 2025–26: power 0.44.

**Note:** the discovery estimate came from reading the sign of a failed primary, so its true size is more likely smaller than −0.012 than larger. That makes the gap wider, not narrower.

**Possible owner paths (none started):**
- Keep the candidate as recorded and **revisit when the modern surface has grown.** Live Binance accrues about 35k anchors a year (4 per hour). Power 0.80 at 1× needs roughly (1.65)² × 59.5k ≈ 162k anchors, about three more years.
- A pooled BitMEX + modern design is not covered by the frozen rule. Its synthetic power at 1× is 0.90, but its null false support is 0.0625. It would need its own owner decision and its own adequacy criterion.

## 9. Confirmations

- **No market interaction outcome was read.**
  - The loaders pop R_1H before anything else runs.
  - All outcomes are synthetic.
  - The noise scale uses only past bar returns (before every affected anchor).
- **Real RP4H main-effect results on BitMEX and 2025–26 were not used.** They were read in earlier units; the planted main effect is a fixed −0.030.
- The E1 holdout and the E1-development slice were never requested.
- No product, Track A or PnL work.
