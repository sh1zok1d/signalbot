# LEVEL_RACE_FORECAST_V1 — development result (CV 2020–2024)

**Stage:** development (`MODE = DISCOVERY`). Design frozen `997ba98615135b263684ad10f9c044335910a346` before any outcome; development code `d7012001b375f672c19e71230c4b170a52a1bc4e` committed before this run. Machine-readable record: `LEVEL_RACE_FORECAST_V1_DEVELOPMENT.json`. Nothing is frozen by this record; the model freeze is a separate commit after the architect's answer. No 2025/2026 object was read.

## Data

`CORE_BTC_BINANCE_V0` (dataset digest `936594956e8b…`), events 2020-02-01..2024-12-31. 1919 T0 rows, 1332 T15 rows; AMBIGUOUS excluded and counted (T0 14, T15 1). Out-of-fold (2021–2024): 1574 T0 + 1117 T15 = 2691 rows, week clusters. Rolling origin by year, 4 folds; week-cluster bootstrap B = 2000, seed 20261008 (the calibration-slope intervals use the same 2000 weights).

## Evidence (pooled out-of-fold, both landmarks; per landmark in the JSON)

| Model | Params | λ / event | Log-loss | Gain vs B0, nats (95 %) | Skill vs B0 | Skill vs B1 |
|---|---|---|---|---|---|---|
| B0 | 0 | — | 0.8987 | 0 | 0 | +0.069 |
| B1 | 6 cells | — | 0.9650 | −0.066 (−0.091..−0.040) | −0.074 | 0 |
| **M1** | 10 | 0.008 | **0.8705** | **+0.028 (+0.014..+0.042)** | +0.031 | +0.098 |
| M1A | 10 | 0.008 | 0.8883 | +0.010 (+0.000..+0.020) | +0.012 | +0.079 |
| M1B | 4 | 0.032 | 0.8902 | +0.009 (+0.000..+0.017) | +0.010 | +0.078 |

Per landmark, M1 gain vs B0: T0 +0.034 (+0.020..+0.048), N = 1574; T15 +0.020 (+0.006..+0.034), N = 1117. M1A and M1B at T15: +0.0005 (intervals through 0).

**Calibration (out of fold).**
- Raw B0: CITL BEYOND +5.7 pp (+3.6..+8.0), NEITHER −4.1 pp (−5.9..−2.4); head R recalibration slope 0.41 (0.26..0.60), head B slope 0.77 (0.67..0.88). B0 under-predicts resolution at structural first touches and its resolve probability carries little ranking information (AUC 0.566).
- M1: CITL BEYOND +0.8 (−1.4..+3.1), BACK −1.9 (−4.1..+0.5), NEITHER +1.0 (−0.7..+2.6) pp; head R slope 0.78 (0.57..1.02), intercept +0.33 (−0.16..+0.80); head B slope 0.78 (0.68..0.90), intercept +0.01 (−0.12..+0.13). AUC R 0.652, B 0.737.
- Brier (stacked Murphy): B0 0.528 (REL 0.0099, RES 0.069); M1 0.516 (REL 0.0030, RES 0.069); uncertainty 0.591. Sharpness (`p_B` outside 40–60 %): B0 0.785, M1 0.735. ECE (descriptive): B0 0.014, M1 0.022.

**Stability (M1 log-loss gain vs B0 by test year, pooled landmarks):** 2021 +0.003 (N 664; trained on 2020 only), 2022 +0.024 (692), 2023 +0.037 (635), 2024 +0.049 (700). Same sign at T0 and T15 in every year. By family: DAY 2021 −0.003, then positive; WEEK positive every year; MONTH N 7–12 per year (descriptive only).

**Full-sample M1 coefficients** (2020–2024, λ 0.008; σ tercile edges 0.001172 / 0.001695):
- head R (resolve, offset logit B0): 1 +0.462, T15 −0.221, FAM_WM +0.485, SIDE −0.182, SIGMA_T −0.560;
- head B (beyond | resolved, offset logit B0): 1 +0.221, T15 +0.003, FAM_WM +0.225, SIDE +0.049, SIGMA_T −0.263.

**C1 (descriptive, T15 rows with the #363 move, N = 1060):** gain vs its base M1 −0.006 nats (−0.012..+0.000); vs B0 +0.016 (−0.000..+0.033). Full-sample OVMM coefficient in head B +0.004 (z-scored; moments 0.00294 / 0.00447). C1 is a live challenger only; these numbers do not gate it.

**Generic stream (§8a):** 35 058 hourly anchors × 4 pairs = 140 181 out-of-fold rows, 210 weeks, about 8 765 non-overlapping 4h windows. GB0 is constant per pair (σ cancels in the pair geometry). GB0 CITL: NEITHER +11.7 pp (+11.0..+12.3), BEYOND (up) −6.4, BACK (down) −5.3 pp; head R slope 0.61. G1 (λ 0.032) gain vs GB0 +0.036 nats (+0.031..+0.041); CITL within ±0.3 pp. Choice by the frozen rule: **G1**. Full-sample G1: head R 1 −0.632, SIGMA_T −0.168; head U 1 −0.042, SIGMA_T −0.049.

## Champion (frozen rule §4)

M1 has the lowest pooled out-of-fold log-loss and is below B0 by more than the tie margin: **champion = M1**, C1 base = M1. Selected on this surface, so `DISCOVERY_ONLY`; the claim of a level effect waits for the held-out read (§7 level-effect rule).

## Interpretation (not a claim)

- Most of M1's gain over B0 sits in head R (resolution). B0 under-predicts resolution at structural first touches (NEITHER −4.1 pp), consistent with #357/#365; at generic hourly anchors B0 *over*-predicts resolution (NEITHER +11.7 pp). The structural-versus-generic difference in the resolve intercept is therefore large; it is what the level calibration intercept would carry (case A) and what case B deliberately does not publish.
- `SIGMA_T` has the largest coefficient in head R (−0.56): higher trailing 24h σ → fewer resolutions than geometry predicts. That is a generic volatility effect (also present in G1), not a level property.
- `FAM_WM` (+0.49 R, +0.22 B): weekly and monthly levels resolve more and more often beyond than geometry predicts; MONTH alone is small.
- C1 adds nothing out of fold here; the #363 coefficient is not reproduced as a forecast gain in this specification.

## Limitations

Discovery surface already consumed for the level row; model selection on the same out-of-fold rows as the reported skill (3 variants × 4 λ); 2020 is a short first training fold; T0 and T15 rows of one event are dependent (clustered by week, not modelled); 114 T0 events start outside the barrier pair (B0 floor); B0 discretisation caveats of the design §2.1; Python 3.13 here, CI is 3.11.

## Search exposure

12 M1-family fits per fold (3 variants × 4 λ), B0, B1, C1 (1 spec), generic GB0 + G1 (4 λ); 2 landmarks; 2 heads; 4 folds. All reported.

## Claim decision

None for users. Development evidence is internal L2 (`DISCOVERY_ONLY` for M1). User-facing L3 wording requires the frozen model, the one held-out read and the gates of §7.
