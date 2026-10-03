# Divergence conditional-support feasibility V1 — report

**Question:** conditional on an already-present support state, does regular bullish divergence add practically meaningful trading value?
**Primary estimand:** `A − B`. This is the conditional increment, not an interaction.
**Secondary estimand:** `(A − B) − (C − D)`.
**Minimum effect of interest:** 15 pp.
**Date:** 2026-10-02
**Design:** `DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_DESIGN.json`, frozen in `323451e` before any computation
**Machine record:** `DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_REPORT.json`

```
HISTORICAL_ONLY_VERDICT   = INFORMATIONALLY_WEAK          (STRESS gate 0.813 / 0.789 vs 0.80; fails on one proxy)
COMBINED_DESIGN_VERDICT   = FEASIBLE_FOR_PREREGISTRATION  (window + ~4 prospective weeks; thin margin)
V0_VERDICT                = INFORMATIONALLY_WEAK          (unchanged)
OUTCOMES_COMPUTED         = false
PROTECTED_2025_2026_OPENED = false
SEED0003_CREATED          = false
NEXT_UNIT                 = OWNER_DECISION_AFTER_DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1
```

The six-symbol panel, the unchanged SEED-0001 detector and all V0 per-symbol episode digests reproduce. The dependence profiles are those of V0:

| Profile | Shock |
|---|---|
| INDEPENDENT | none (diagnostic) |
| BASE | one per UTC date, latent ICC 0.25 |
| **STRESS (gate)** | one per (UTC date, arm) across symbols, latent ICC 0.50 |
| COLLAPSED | same-day same-arm episodes merged into one unit |

## 1. Primary A − B power (2000 replicates per cell; gate cells 10 000)

**Proxy 1: the first 85 weeks of 2023–2024.**

| Profile | 10 pp | **15 pp** | 20 pp | MDE80 A − B |
|---|---:|---:|---:|---:|
| INDEPENDENT | 0.60 | 0.92 | 1.00 | 0.150 |
| BASE | 0.56 | 0.89 | 0.99 | 0.150 |
| **STRESS** | 0.46 | **0.82** (gate, 10k: **0.813 ± 0.004**) | 0.97 | 0.150 |
| COLLAPSED | 0.43 | 0.80 | 0.96 | 0.175 |

**Proxy 2: the last 85 weeks of 2023–2024.**

| Profile | 10 pp | **15 pp** | 20 pp | MDE80 A − B |
|---|---:|---:|---:|---:|
| INDEPENDENT | 0.58 | 0.89 | 1.00 | 0.150 |
| BASE | 0.54 | 0.87 | 0.99 | 0.150 |
| **STRESS** | 0.45 | **0.79** (gate, 10k: **0.789 ± 0.004**) | 0.96 | 0.175 |
| COLLAPSED | 0.43 | 0.74 | 0.95 | 0.175 |

**Full 2023–2024 layout (reference only; spent):** STRESS A − B at 15 pp is 0.87, and MDE80 is 0.150.

## 2. Projected protected-window counts (structural stand-ins; no protected byte)

| | Proxy 1 | Proxy 2 | Rate-scaled estimate (V0) |
|---|---:|---:|---:|
| A episodes | 134 | 125 | ~130 |
| B episodes | 1213 | 1195 | ~1193 |
| A decision dates | 98 | 88 | — |
| A week clusters | 57 | 55 | — |
| B week clusters | 85 | 85 | — |
| A max symbol share | 22% (BTC 30) | 22% (BTC 28) | — |
| A max epoch share | 32% | 35% | — |

**A by symbol:**

| Symbol | Proxy 1 | Proxy 2 |
|---|---:|---:|
| BTC | 30 | 28 |
| ETH | 27 | 24 |
| BNB | 25 | 25 |
| SOL | 23 | 23 |
| DOGE | 15 | 12 |
| XRP | 14 | 13 |

**Effective information.**
- **Design effect on Var(A − B):** 1.45 under STRESS and 1.14–1.16 under BASE.
- **What that means:** the ~1350 A + B episodes per proxy carry about 930 and 880 independent-equivalent observations under STRESS.
- **The binding constraint** is the ~130 A episodes in ~56 week clusters.

## 3. Historical window alone: `INFORMATIONALLY_WEAK`

**Frozen gate.** STRESS power of A − B at 15 pp must be ≥ 0.80 on both proxies, at 10 000 replicates.

**Result.** It is 0.813 on proxy 1 and 0.789 on proxy 2. The window alone sits on the 0.80 line and fails the frozen gate on one proxy.

**What passes:**
- support (A week clusters 55–57 ≥ 30, B 85 ≥ 30);
- concentration (22% ≤ 50%);
- data.

## 4. Combined design: `FEASIBLE_FOR_PREREGISTRATION` (thin margin)

**Design.** The pre-specified spend window plus a prospective panel stream. Decisions start at 2026-10-05; reads start 2026-08-27, after the E1 holdout. It is searched on the frozen 4-week grid.

| Prospective part | Proxy 1 | Proxy 2 |
|---|---|---|
| all six symbols | 0 weeks (STRESS 0.825, 10k) | **4 weeks** (STRESS 0.812, 10k) |
| without BTC (disjoint from the SEED-0001 prospective leg) | 0 weeks (0.823) | **4 weeks** (0.812) |

At the 4-week pass on proxy 2, the prospective part adds 10 A episodes (7 without BTC) in 4 week clusters.

**Stopping rule in the frozen form** (thresholds from the more demanding proxy):
- **stop condition:** stop at the first decision time when cumulative A episodes ≥ **135** (134 without BTC) AND cumulative A week clusters ≥ **59**;
- **expected stop:** about 2026-11-02;
- **deadline:** 2026-11-30, which is 2 × the expected weeks;
- **below the thresholds at the deadline:** `INCONCLUSIVE`, with no extension.

**Secondary interaction power** under STRESS at 15 pp: 0.64 / 0.61 on the window, and about 0.64 combined. It is underpowered and descriptive only.

## 5. Caveats the owner should weigh before SEED-0003

1. **The margin is thin.** The design is feasible only because a near-0.80 window is topped up by a few weeks. Two things push the window below 0.80:
   - the most conservative dependence model: COLLAPSED gives 0.74–0.80;
   - a smaller-than-projected A yield in 2025–2026.

   The count-based stop protects against the second, but only up to the deadline.
2. **The deadline is tight.** With the frozen rule form it is 2026-11-30. If the window yields, say, 110 A episodes instead of about 130, the prospective part needs about 25 more A, roughly 15+ weeks at about 1.6 A per week. It would then end `INCONCLUSIVE`. SEED-0003 may set a later deadline before opening, which is a pre-outcome choice.
3. **Freeze timing.**
   - **The rule:** prospective data must postdate the freeze.
   - **Consequence:** if SEED-0003 is not frozen before 2026-10-05T00:00Z, the prospective start moves to the first Monday after its freeze. The count-based stop absorbs this.
4. **Protected-data steps that SEED-0003's opening decision must authorize:**
   - counts-only detector runs on the 2025-01-01..2026-08-11 window, which the stop rule needs;
   - the prospective 2026 segment from 2026-10-05.
5. **SEED-0001 overlap.**
   - **The overlap:** the SEED-0001 prospective leg tests a near-identical A vs B contrast on BTC from 2026-10-05.
   - **The way out is cheap:** the without-BTC variant needs the same 4 weeks and thresholds of 134 / 59.
   - **Decision needed:** retire the SEED-0001 prospective leg, or keep the two legs disjoint.
6. **Expectation.** The SEED-0001 exploratory estimates of A − B (BTC +0.04, ETH −0.09; spent data) are far below 15 pp. A powered test of a 15 pp effect may well return no structure. That is a valid answer to the owner's question, not a design flaw.

## 6. Not done

- No continuous or graded model.
- No panel expansion.
- No outcome.
- No protected byte read.
- No SEED-0003.
- The V0 verdict is not reinterpreted.
