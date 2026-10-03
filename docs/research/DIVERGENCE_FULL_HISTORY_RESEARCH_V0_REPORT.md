# Divergence full-history research V0 — report

**Date:** 2026-10-02
**Design:** `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.{md,json}`, frozen in `c12204079462c0c173eebdc8b81308174d21f457` before any 2025+ byte.

**Stage 1 (validation, evaluated once):**
- **Record:** `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_VALIDATION.json`, with episodes in `divergence_full_history_v0/VALIDATION_EPISODES.csv`.
- **Commit:** `fca3ab54633d7c47e651ffb9d773a779473ae614`, made before any pooled or mechanism step.

**Stage 2 (pooled and mechanism; exploratory):**
- **Record:** `DIVERGENCE_FULL_HISTORY_RESEARCH_V0_RESEARCH.json`.
- **Integrity:** it verified that the validation episodes reproduce the persisted CSV.

```
E1_INTERVAL_TOUCHED     = false (read horizon 2026-08-15T00:00Z; E1 [2026-08-16, 2026-08-25 17:20) never requested)
PIT_TRUNCATION_AUDIT    = 30/30 identical on every symbol, validation slice
DISCOVERY_DIGESTS       = reproduce V0 for all six symbols
PROSPECTIVE_ACTIVATED   = false
SEED0003_CREATED        = false
```

**Labels used throughout:**
- `DISCOVERY 2023–2024`: previously observed.
- `VALIDATION 2025–2026`: previously unseen; the only independent evidence.
- `POOLED FULL HISTORY`: never replication or confirmation.

## 1. Validation slice (VALIDATION / PREVIOUSLY UNSEEN)

**Usable decisions:** 2025-01-01T00:00Z .. 2026-08-11T00:00Z.

**Missing bookDepth days:** SOL and XRP lack 2026-01-14 in the archive. One episode each was excluded by the frozen funnel.

**Counts A / B / C / D:**

| Symbol | A | B | C | D |
|---|---:|---:|---:|---:|
| BTC | 27 | 219 | 61 | 318 |
| ETH | 30 | 183 | 69 | 327 |
| SOL | 23 | 219 | 54 | 315 |
| BNB | 26 | 211 | 50 | 322 |
| DOGE | 28 | 215 | 55 | 364 |
| XRP | 26 | 204 | 53 | 364 |
| **Panel** | **160** | **1251** | **342** | **2010** |

The A episodes fall on 112 distinct dates and in 62 of 85 weekly clusters.

**Raw +1R before −1R within 48h (WIN / LOSS / NEUTRAL):**

| Arm | Counts | Rate |
|---|---|---:|
| A | 80 / 70 / 10 | 0.500 |
| B | 608 / 624 / 19 | 0.486 |
| C | 153 / 159 / 30 | 0.447 |
| D | 936 / 984 / 90 | 0.466 |

**Frozen model** (adjusted, CR1 by week, 85 clusters):

| Estimand | Estimate | 95% CI | p |
|---|---:|---|---:|
| **A − B (primary)** | **+0.011** | **[−0.087, +0.109]**; week bootstrap [−0.083, +0.105] | 0.83 |
| (A − B) − (C − D) | +0.018 | [−0.094, +0.129] | 0.75 |
| A − D (descriptive) | +0.031 | [−0.067, +0.129] | 0.53 |
| C − D (descriptive) | −0.007 | [−0.073, +0.060] | 0.84 |

**Frozen validation tags (A − B and the interaction):**
- `SAME_DIRECTION`;
- `COMPATIBLE_WITH_ZERO`;
- `BELOW_MEOI`;
- `ECONOMICALLY_SMALL`;
- `NO_DETECTED_SYMBOL_HETEROGENEITY` (symbol Q p = 0.46 and 0.87; not evidence of stability).

**What it shows.** The upper 95% bound of A − B is +10.9 pp, so the validation slice is incompatible with the 15 pp effect of interest.

## 2. Discovery vs validation vs pooled (A − B unless stated; adjusted; CR1 by week)

| Outcome | DISCOVERY 2023–2024 | VALIDATION 2025–2026 | POOLED |
|---|---|---|---|
| **+1R/−1R, 48h (primary)** | +0.026 [−0.058, +0.110] | +0.011 [−0.087, +0.109] | +0.019 [−0.047, +0.084] |
| interaction, 48h | +0.019 [−0.090, +0.128] | +0.018 [−0.094, +0.129] | +0.021 [−0.057, +0.099] |
| A − D, 48h | +0.029 | +0.031 | +0.032 [−0.031, +0.095] |
| C − D, 48h | +0.007 | −0.007 | −0.002 [−0.047, +0.042] |
| +2R/−1R, 48h | +0.013 [−0.060, +0.087] | +0.026 [−0.067, +0.120] | +0.020 [−0.039, +0.080] |
| +1R/−1R, 96h | +0.027 | +0.030 | +0.029 [−0.037, +0.094] |
| +2R/−1R, 96h | −0.011 | +0.050 | +0.020 [−0.039, +0.078] |
| net R (1R bracket, after costs), 48h | +0.050 [−0.117, +0.216] | +0.063 [−0.122, +0.247] | +0.056 [−0.071, +0.182] |
| forward R, 48h | −0.97 [−2.10, +0.16] | +0.40 [−0.56, +1.36] | −0.30 [−1.05, +0.45] |
| MFE in R, 48h | −0.52 [−1.09, +0.05] | +0.15 [−0.59, +0.89] | −0.18 [−0.66, +0.29] |
| MAE in R, 48h | +0.67 | −0.26 | +0.23 [−0.57, +1.03] |
| time to MFE, 48h (hours) | −2.7 | +2.1 | −0.4 [−2.5, +1.7] |

**Raw A rate on the primary:** 0.494 in discovery, 0.500 in validation and 0.497 pooled. For B it is 0.474, 0.486 and 0.479.

**Mean net R per trade after costs** is negative in every arm and slice. For A it is −0.067, −0.049 and −0.058. For B it is −0.106, −0.124 and −0.114.

**Validation minus discovery.** For A − B on the primary, the difference is −0.000 [−0.131, +0.131]. The only nominally different series is forward R (p = 0.03). It is a heavy-tailed series in R units; that difference is noise-dominated and not interpreted.

## 3. Stability (pooled, descriptive)

**Years, A − B on the primary:**

| Year | A − B |
|---|---:|
| 2023 | +0.012 |
| 2024 | +0.052 |
| 2025 | +0.002 |
| 2026 to Aug | +0.039 |

Heterogeneity Q p = 0.94. No year stands out.

**Validation half-years:**

| Half-year | A − B |
|---|---:|
| 2025H1 | +0.014 |
| 2025H2 | +0.011 |
| 2026H1 | +0.021 |
| 2026H2 partial | +0.11 (12 A episodes) |

All four are positive and all are compatible with zero.

**Symbols, pooled A − B:**

| Symbol | A − B |
|---|---:|
| BNB | +0.11 |
| XRP | +0.12 |
| BTC | −0.00 |
| ETH | −0.04 |
| SOL | −0.00 |
| DOGE | −0.05 |

Q p = 0.40, so the signs are mixed. No single symbol carries an effect that the CIs separate from zero.

**Effective information.** Pooled A is 316 episodes in 129 of 186 weekly clusters. All symbols in a week share one cluster.

## 4. Mechanism (EXPLORATORY; pooled; support episodes A ∪ B unless stated)

| Question | Finding |
|---|---|
| Does divergence add information inside support? | M0 gives DIV +0.022 [−0.044, +0.088]. With the 12 mechanism features (M1) it is +0.017 [−0.051, +0.086]. So: very little either way. |
| Does the classical MACD divergence carry information? | No. The MACD family flag gives +0.008 [−0.053, +0.070], and +0.015 with the mechanism features. RSI family +0.057 (p = 0.06); CVD family −0.052 (p = 0.14). |
| Is "divergence" a proxy for a deeper selling-exhaustion state? | `DEEPER_STATE_FLOW_OI` (selling weakened into the new low and OI did not expand; no oscillator input) gives +0.038 [−0.000, +0.075], p = 0.050. With DIV in the model: deeper state +0.036 (p = 0.06), DIV +0.015 (p = 0.65). The flow/OI state carries at least as much information as the oscillator flag. Both are small, about 2–4 pp, and this is not confirmatory. |
| What distinguishes successful from failed A episodes? | Nothing survives Holm across 22 features. The smallest is the 7-day return, raw p = 0.03, Holm 0.73. |
| Inside B (support only) | The continuous RSI14 and RSI21 deltas between the pivots associate with a higher +1R rate: about +3.8 pp per SD, Holm p = 0.03 for both. A deeper new low and higher RV24 associate with a lower rate (Holm 0.07 and 0.34). A graded momentum change carries a little information that the binary divergence flag does not. This is exploratory and was found on data that includes the validation slice. |
| Is support necessary? Does divergence without support help? | Support alone vs neither (B − D) is about +0.013. Divergence alone (C − D) is −0.002. Neither layer shows a useful effect on its own. |
| What do the mechanism features look like? | Divergence episodes differ strongly on the features that define divergence (SMD 1–1.9) and on selling-pressure change (SMD about 1). They differ only mildly elsewhere: |0.2–0.5| for leg depth, net flow, EMA168 distance and the 7-day return. Missingness is at most 0.15%. |

## 5. Interpretation

**Observed.**
- **Win rate.** Inside a support state, regular bullish divergence goes with +1R before −1R about 1–3 pp more often than support alone. The same small edge appears over 96h and at +2R.
- **Net R.** After costs, the 1R bracket loses money in every arm and slice (mean −0.05 to −0.13 R).
- **Payoff shape.** Divergence does not change the excursions or the timing.

**Independently validated (validation slice only).**
- **No large effect.** A conditional effect of the size the owner cares about (≥ 15 pp) is not present. The CI excludes it.
- **No effect distinguishable from zero.** The direction matches discovery, but the effect is compatible with zero and economically small.
- **No mechanistic difference.** The interaction behaves the same.

**Exploratory.** These come from pooled data that includes the validation slice, so they are not independent evidence:
- the flow/OI selling-exhaustion state (about +3.8 pp, borderline);
- the graded RSI change inside support-only episodes (about +3.8 pp per SD).

**Economically meaningful.** Nothing. The best point estimate of the divergence increment, about +0.06 R per trade, does not turn the negative bracket economics positive, and its CI includes zero.

**Statistically uncertain.** Everything at the ±5 pp scale: the per-symbol and per-year signs, the deeper-state effect and the RSI gradient.

## 6. Candidate hypotheses for a future prospective SEED (recommendations only; nothing created or activated)

1. **Do not spend prospective data on A − B ≥ 15 pp.** The validation slice already excludes it, and a confirmation would answer a settled question.
2. **The candidate most worth a new object, if any.** A selling-exhaustion state inside support, defined without oscillators: selling weakened into the new low, OI not expanding, support present.
   - **Size.** The observed size is about 4 pp, so a confirmatory test needs a very large prospective panel. That needs its own feasibility unit, and it may well be `INFORMATIONALLY_WEAK`.
   - **Reframing.** It may be better reframed as a context description (what followed such states, with N and spread) than as a trading edge.
3. **A graded RSI momentum-change model inside support.** Small, exploratory, and same caveat as (2).
4. **Reasonable alternative.** Close regular bullish divergence as a trading-edge line, and use the divergence and support features only as descriptive context in the product, under the existing gates.

The choice among these is the owner's. SEED-0003 has not been created.
