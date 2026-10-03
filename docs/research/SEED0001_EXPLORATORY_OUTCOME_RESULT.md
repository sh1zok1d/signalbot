# SEED-0001 regular divergence — exploratory outcome result

**Label:** `EXPLORATORY / UNDERPOWERED`. This is not confirmatory evidence.
**Date:** 2026-10-02
**Feasibility verdict (unchanged):** `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`
**Classification (fixed in the permit before outcomes):** `INCONCLUSIVE_DISCOVERY`
**Machine record:** `SEED0001_EXPLORATORY_OUTCOME_RESULT.json`. Per-episode outcomes are in `seed0001/OUTCOMES_{BTCUSDT,ETHUSDT}.csv`.

**Chain of record:**

| Commit or file | Role |
|---|---|
| `8e213d3` | preregistration freeze |
| `138e1c1` | feasibility |
| `df9e351` | owner authorization; permit `SEED0001_EXPLORATORY_OUTCOME_PERMIT.json`, SHA256 `2221b20c…` |
| `1e4f848` | evaluator committed before the run |
| `1e4f848` | the one run, with git HEAD at this commit |

```
FROZEN_ARTIFACTS_CHANGED      = false (prereg, detector, feasibility code/report, episode CSVs, manifest re-verified)
EPISODES_USED                 = frozen sets only (BTC 743, ETH 736); no episode added, removed or regenerated
OUTCOME_WINDOWS_UNAVAILABLE   = 0
PROTECTED_2025_2026_OPENED    = false (every window ends by 2025-01-01T00:00Z)
STATISTICAL_GATE (mechanical) = FAIL
PRACTICAL_GATE (mechanical)   = FAIL
ETH_ROBUSTNESS                = ETH_NOT_SAME_DIRECTION
RERUN_AUTHORIZED              = false
```

## Outcome definitions used

**Preregistered bracket.** The full definitions are in the permit; they are unchanged from the prereg.
- **Entry:** E = close of bar i+3.
- **Stop:** S = low_i; the stop event is a 1m low < S.
- **Target:** the first 1m high ≥ E + k·R, where R = E − S.
- **Same minute:** stop and target in the same minute count as the stop.
- **Window:** 1m bars with open time in [T, T + cap).

**Classes:**
- **WIN:** the target is first.
- **LOSS:** the stop is first, or both fall in the same minute.
- **NEUTRAL:** timeout.
- **Endpoint value:** Y = 1 on WIN.

**Endpoints:**
- **Primary:** Y1_48H.
- **Secondary:** Y2_48H.
- **Sensitivity:** Y1_96H and Y2_96H.

**Descriptive (fixed in the permit before opening; never used for a gate):**
- `FWD_RET_h = C_h/E − 1` and `FWD_R_h = (C_h − E)/R`, where `C_h` is the close of the minute that opens at T + h − 1m.
- `MFE_R_h` and `MAE_R_h`: the window extremes in R units, over the full window.

**Primary model, as preregistered.**
- **Fit:** OLS of Y1_48H on the arm dummies (D reference) and log RV24, sin/cos of the hour, DECLINE_ATR, NETFLOW24 and RISK_ATR.
- **Variance:** CR1 with weekly clusters (G = 101), t on 100 df.
- **Tests:** P1 = A − B, P2 = A − C, Holm at 0.05.
- **Extra interval:** a pairs bootstrap over whole weeks, 4999 resamples, seed 20261004.

## BTC (primary)

**Raw counts, Y1_48H (+1R before −1R within 48h):**

| Arm | N | WIN | LOSS | NEUTRAL | raw rate, CR1 95% CI |
|---|---:|---:|---:|---:|---|
| A support + divergence | 36 | 20 | 15 | 1 | 0.556 [0.413, 0.699] |
| B support only | 259 | 130 | 121 | 8 | 0.502 [0.438, 0.566] |
| C divergence only | 63 | 26 | 29 | 8 | 0.413 [0.293, 0.533] |
| D neither | 385 | 201 | 159 | 25 | 0.522 [0.461, 0.583] |

**Primary contrasts (adjusted risk difference, Y1_48H):**

| Contrast | Estimate | CR1 t 95% CI | Week-bootstrap 95% CI | p (two-sided) | Holm p |
|---|---:|---|---|---:|---:|
| P1 A − B | **+0.042** | [−0.099, +0.184] | [−0.111, +0.180] | 0.554 | 0.554 |
| P2 A − C | **+0.148** | [−0.037, +0.332] | [−0.044, +0.331] | 0.117 | 0.233 |

**Adjusted rates:** A 0.557, B 0.514, C 0.409, D 0.514.

**Mechanical gates (reported only; the classification is fixed):**
- **Statistical: FAIL.** Holm rejects neither contrast.
- **Practical: FAIL.** P1 is 0.042, under the 0.10 bar. The adjusted A rate of 0.557 is under the mean A break-even of 0.564 at 0.10% round-trip cost.

**Secondary and sensitivity** (adjusted; none rejects under Holm):

| | P1 A − B [CR1 95% CI] | P2 A − C [CR1 95% CI] |
|---|---|---|
| S1 Y2_48H (+2R) | −0.012 [−0.159, +0.135] | +0.103 [−0.067, +0.272] |
| S2 Y1_96H | +0.053 [−0.092, +0.198] | +0.110 [−0.079, +0.299] |
| S3 Y2_96H | −0.056 [−0.197, +0.084] | +0.056 [−0.121, +0.232] |
| S4 Y1_48H, 48h-chain clusters (G = 71) | +0.042 [−0.109, +0.194] | +0.148 [−0.047, +0.342] |

**A vs D**, raw Y1_48H: +0.034 [−0.112, +0.179].

**Win / loss / neutral, A arm:**

| Endpoint | WIN | LOSS | NEUTRAL |
|---|---:|---:|---:|
| Y2_48H | 11 | 23 | 2 |
| Y1_96H | 21 | 15 | 0 |
| Y2_96H | 11 | 25 | 0 |

**Descriptive path, 48h.** Values are medians [IQR] by arm.

| Measure | A | B | C | D |
|---|---|---|---|---|
| FWD_RET | +0.70% [−2.6, +3.7] | +0.34% [−0.9, +2.0] | +0.00% [−1.2, +0.9] | +0.00% [−1.6, +1.6] |
| FWD_R | +0.48 [−1.83, +3.58] | +0.32 [−0.98, +1.72] | +0.02 [−1.52, +0.78] | +0.01 [−1.76, +1.39] |
| MFE_R | 2.39 [1.13, 5.97] | 2.07 [1.03, 3.84] | 1.71 [0.72, 2.95] | 2.00 [0.75, 4.09] |
| MAE_R | 1.57 [0.76, 4.90] | 1.81 [0.69, 3.22] | 2.17 [0.74, 5.04] | 2.14 [0.72, 4.04] |

Means in R units are dominated by small-R episodes; for example, the A mean FWD_R_48H is −0.77 while the median is +0.48. None of the 16 descriptive mean differences is multiplicity-corrected. The single nominal p < 0.05 among them, MFE_R_48H A − C, is not evidence.

**Half-years (descriptive robustness; not a selection rule).** Within each epoch, an arm-only model with CR1 by week.

| Epoch | A / B / C / D | P1 A − B [95% CI] | P2 A − C [95% CI] |
|---|---|---|---|
| 2023H1 | 10 / 74 / 14 / 82 | +0.168 [+0.031, +0.305] | −0.114 [−0.401, +0.173] |
| 2023H2 | 6 / 49 / 22 / 126 | +0.095 [−0.343, +0.533] | +0.303 [−0.124, +0.730] |
| 2024H1 | 9 / 68 / 16 / 85 | −0.070 [−0.365, +0.225] | +0.132 [−0.352, +0.616] |
| 2024H2 | 11 / 68 / 11 / 92 | +0.031 [−0.310, +0.372] | +0.273 [−0.105, +0.651] |

**Across epochs:**
- **Pooled sign:** 3 of 4 epochs share the pooled sign for P1, and 3 of 4 for P2.
- **Heterogeneity:** the preregistered permutation test gives p = 0.55 (P1) and p = 0.35 (P2), with 2000 draws and seed 20261003.
- **Opposite epochs:** no epoch is significantly opposite.
- **What this shows:** the epoch gate was `NOT_ASSESSABLE` before opening, so this shows neither stability nor instability.

## ETH (robustness only; never pooled)

**Y1_48H, A arm:** 13 WIN, 17 LOSS, 2 NEUTRAL of 32; raw rate 0.406 [0.226, 0.586].
- **B:** 135 / 112 / 17, raw rate 0.511.
- **C:** 25 / 20 / 3, raw rate 0.521.
- **D:** 195 / 176 / 21, raw rate 0.497.

| Contrast | Estimate | CR1 t 95% CI | Week-bootstrap 95% CI | p |
|---|---:|---|---|---:|
| P1 A − B | −0.089 | [−0.278, +0.099] | [−0.273, +0.098] | 0.351 |
| P2 A − C | −0.138 | [−0.378, +0.101] | [−0.377, +0.088] | 0.254 |

- **Label:** `ETH_NOT_SAME_DIRECTION`. Both ETH contrasts are negative.
- **Half-years:** 2 of 4 epochs share the P1 pooled sign, and 3 of 4 the P2 pooled sign.
- **Role:** ETH cannot change anything about BTC.

## Observed effect vs evidence strength

**Observed effect (BTC):**
- **Against support only:** A reached +1R before −1R in 20 of 36 episodes (55.6%). That is 4 pp above support-only after adjustment.
- **Against divergence only:** 15 pp above divergence-only after adjustment. Much of that gap is the low C rate (41%) rather than a high A rate, since A is only 3 pp above D.
- **At +2R and 96h:** the P1 point estimate is near zero or negative.

**Evidence strength: weak to none.**
- **Both intervals include zero.** P1 runs from −10 to +18 pp, and P2 from −4 to +33 pp.
- **Holm rejects nothing.**
- **The practical bar is missed.**
- **Power was about 0.10 at 10 pp.** At that power, these estimates are compatible with no effect and with a large one alike.
- **ETH points the other way.**
- **Time blocks:** the direction is mostly but not uniformly the same across half-years, which is uninformative at these Ns.

**Bottom line.** Nothing here supports a confirmatory or product claim. The result stays exploratory / underpowered and `INCONCLUSIVE_DISCOVERY`.

**Not done after outcomes:**
- no threshold, horizon, stop, entry, exit or subgroup search;
- no change to the prospective preregistration.

Any variant needs a new research object / SEED. The 2023–2024 Binance UM 1h outcome surface is now consumed for this card and for nearby questions.
