# H01 Compression → Expansion — Development Results

**Status:** FROZEN_EVIDENCE / EXPLORATORY
**Hypothesis ID:** `H01_COMPRESSION_EXPANSION`
**Development verdict:** `H01_KILL`
**Machine-readable:** `docs/research/H01_DEV_RESULTS.json`
**Preregistration:** `docs/research/H01_COMPRESSION_EXPANSION_PREREG.md`

This document records the development-only outcome inspection. It is not a confirmatory result, not a directional edge, not a product change, and not authorization to open 2025 validation or 2026 OOS.

## Identity

| Field | Value |
|---|---|
| dataset | `CORE_BTC_BINANCE_V0` |
| snapshot_id | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| prereg commit | `52d8731fbb2a8b0eea42d66a3772ba876f319331` |
| research code SHA at outcome run | `d90a9e126a27af28bb652e0645fa2a5c403ca26d` |
| generated_at_utc | `2026-08-26T18:59:14Z` |
| development window | 2020-02-01T00:00:00Z → 2025-01-01T00:00:00Z |
| t_max_inclusive | 2024-12-31T19:45:00Z |
| 2025 validation inspected | NO |
| 2026 OOS inspected | NO |

## Search surface

3 lookbacks (30/60/120m) × 3 thresholds (q=0.10/0.20/0.30) × 5 horizons (15/30/60/120/240m) = **45 primary cells**.

Secondary families: expansion probability (Q75 frozen) and normalized high-low range. Decile bins are diagnostics, not extra selectable strategies.

## Sample

Eligible development 15m boundaries: **172400**.

Candidate N is identical across H for a given L×q because the max-forward rule `T+240m < 2025-01-01` is applied to every boundary before outcomes.

| config | N | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|
| L30 q0.1 | 20719 | 4206 | 4446 | 4654 | 3650 | 3763 |
| L30 q0.2 | 38252 | 7364 | 8216 | 8531 | 6896 | 7245 |
| L30 q0.3 | 55152 | 10350 | 11679 | 12196 | 10174 | 10753 |
| L60 q0.1 | 21124 | 4341 | 4592 | 4751 | 3667 | 3773 |
| L60 q0.2 | 38718 | 7479 | 8356 | 8659 | 6974 | 7250 |
| L60 q0.3 | 55441 | 10525 | 11715 | 12272 | 10155 | 10774 |
| L120 q0.1 | 21513 | 4436 | 4745 | 4834 | 3717 | 3781 |
| L120 q0.2 | 38982 | 7594 | 8454 | 8650 | 6993 | 7291 |
| L120 q0.3 | 55908 | 10697 | 11886 | 12264 | 10227 | 10834 |

## Primary result

The preregistered question is whether unusually low recent realized volatility predicts a **subsequent increase** in realized volatility, measured as `FUTURE_RV_H / PAST_MEDIAN_RV_H` (not future/current compressed RV).

Observed shape, without cherry-picking:

- every one of the 45 cells has mean normalized future RV in **0.61–0.80**, versus unconditional baseline A **~1.18–1.25**;
- every cell has `P(EXPANSION)` in **0.023–0.072**, versus baseline **~0.255**;
- every cell is **below** matched-random timing (true-minus-matched **−0.55 to −0.32**);
- week-block bootstrap 95% intervals for candidate-minus-baseline are **entirely negative** in every cell;
- all five development years are negative in every cell;
- stronger compression (q=0.10) is **more negative** than q=0.20/0.30 on every L×H;
- L=30/60/120 agree;
- all five horizons are negative, with the deficit fading toward (but remaining below) 1.0 at 240m.

This is the opposite of the hypothesized compression→expansion transition. It is consistent with ordinary volatility persistence: quiet recent windows remain quieter than the local 30-day scale over the next 15–240 minutes.

## Primary table (L × q × H)

mean/median = normalized future RV. minus matched = candidate mean minus matched-random replicate mean. perm = month-permuted compression scores. boot CI = UTC-week block bootstrap 95% interval for candidate minus baseline A. year diffs = 2020..2024 candidate-minus-baseline mean normalized RV.

| L | q | H | N | mean | median | p(exp) | base A | base p(exp) | matched | minus matched | perm | boot CI | year diffs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 0.10 | 15 | 20719 | 0.6088 | 0.5454 | 0.023 | 1.2546 | 0.255 | 1.1600 | -0.5511 | 1.1522 | -0.705,-0.591 | -0.696,-0.482,-0.612,-0.800,-0.667 |
| 30 | 0.10 | 30 | 20719 | 0.6248 | 0.5607 | 0.027 | 1.2405 | 0.256 | 1.1460 | -0.5212 | 1.1378 | -0.675,-0.560 | -0.659,-0.455,-0.579,-0.772,-0.643 |
| 30 | 0.10 | 60 | 20719 | 0.6458 | 0.5770 | 0.032 | 1.2260 | 0.255 | 1.1324 | -0.4865 | 1.1213 | -0.639,-0.525 | -0.614,-0.426,-0.538,-0.739,-0.614 |
| 30 | 0.10 | 120 | 20719 | 0.6733 | 0.6013 | 0.037 | 1.2072 | 0.255 | 1.1153 | -0.4420 | 1.1026 | -0.592,-0.479 | -0.564,-0.389,-0.488,-0.682,-0.576 |
| 30 | 0.10 | 240 | 20719 | 0.7051 | 0.6364 | 0.046 | 1.1850 | 0.254 | 1.0951 | -0.3900 | 1.0866 | -0.539,-0.426 | -0.498,-0.351,-0.436,-0.616,-0.528 |
| 30 | 0.20 | 15 | 38252 | 0.6736 | 0.6054 | 0.032 | 1.2546 | 0.255 | 1.1737 | -0.5001 | 1.1666 | -0.638,-0.526 | -0.642,-0.428,-0.547,-0.718,-0.590 |
| 30 | 0.20 | 30 | 38252 | 0.6886 | 0.6184 | 0.035 | 1.2405 | 0.256 | 1.1602 | -0.4716 | 1.1548 | -0.610,-0.498 | -0.604,-0.406,-0.513,-0.688,-0.568 |
| 30 | 0.20 | 60 | 38252 | 0.7057 | 0.6314 | 0.040 | 1.2260 | 0.255 | 1.1464 | -0.4407 | 1.1426 | -0.577,-0.466 | -0.569,-0.381,-0.479,-0.651,-0.539 |
| 30 | 0.20 | 120 | 38252 | 0.7271 | 0.6522 | 0.047 | 1.2072 | 0.255 | 1.1289 | -0.4018 | 1.1247 | -0.537,-0.427 | -0.529,-0.353,-0.434,-0.603,-0.500 |
| 30 | 0.20 | 240 | 38252 | 0.7555 | 0.6835 | 0.057 | 1.1850 | 0.254 | 1.1083 | -0.3528 | 1.1042 | -0.485,-0.378 | -0.478,-0.322,-0.385,-0.531,-0.449 |
| 30 | 0.30 | 15 | 55152 | 0.7260 | 0.6507 | 0.041 | 1.2546 | 0.255 | 1.1855 | -0.4595 | 1.1799 | -0.586,-0.475 | -0.595,-0.388,-0.494,-0.653,-0.527 |
| 30 | 0.30 | 30 | 55152 | 0.7381 | 0.6637 | 0.043 | 1.2405 | 0.256 | 1.1715 | -0.4333 | 1.1676 | -0.560,-0.448 | -0.564,-0.368,-0.464,-0.623,-0.505 |
| 30 | 0.30 | 60 | 55152 | 0.7538 | 0.6761 | 0.049 | 1.2260 | 0.255 | 1.1577 | -0.4039 | 1.1535 | -0.529,-0.418 | -0.533,-0.346,-0.431,-0.585,-0.478 |
| 30 | 0.30 | 120 | 55152 | 0.7731 | 0.6939 | 0.057 | 1.2072 | 0.255 | 1.1403 | -0.3672 | 1.1387 | -0.491,-0.381 | -0.498,-0.320,-0.390,-0.536,-0.438 |
| 30 | 0.30 | 240 | 55152 | 0.7999 | 0.7224 | 0.069 | 1.1850 | 0.254 | 1.1196 | -0.3197 | 1.1187 | -0.440,-0.333 | -0.452,-0.291,-0.343,-0.466,-0.384 |
| 60 | 0.10 | 15 | 21124 | 0.6088 | 0.5407 | 0.024 | 1.2546 | 0.255 | 1.1569 | -0.5481 | 1.1442 | -0.706,-0.590 | -0.685,-0.481,-0.613,-0.810,-0.674 |
| 60 | 0.10 | 30 | 21124 | 0.6227 | 0.5551 | 0.027 | 1.2405 | 0.256 | 1.1426 | -0.5199 | 1.1354 | -0.677,-0.562 | -0.654,-0.455,-0.580,-0.783,-0.652 |
| 60 | 0.10 | 60 | 21124 | 0.6440 | 0.5723 | 0.033 | 1.2260 | 0.255 | 1.1290 | -0.4850 | 1.1225 | -0.641,-0.526 | -0.615,-0.426,-0.537,-0.743,-0.624 |
| 60 | 0.10 | 120 | 21124 | 0.6693 | 0.5944 | 0.038 | 1.2072 | 0.255 | 1.1122 | -0.4429 | 1.1067 | -0.597,-0.482 | -0.563,-0.395,-0.490,-0.689,-0.588 |
| 60 | 0.10 | 240 | 21124 | 0.6997 | 0.6295 | 0.047 | 1.1850 | 0.254 | 1.0920 | -0.3923 | 1.0895 | -0.545,-0.430 | -0.498,-0.358,-0.438,-0.623,-0.544 |
| 60 | 0.20 | 15 | 38718 | 0.6733 | 0.6011 | 0.034 | 1.2546 | 0.255 | 1.1724 | -0.4990 | 1.1700 | -0.640,-0.526 | -0.638,-0.431,-0.544,-0.723,-0.591 |
| 60 | 0.20 | 30 | 38718 | 0.6848 | 0.6129 | 0.035 | 1.2405 | 0.256 | 1.1582 | -0.4735 | 1.1571 | -0.614,-0.501 | -0.608,-0.410,-0.516,-0.694,-0.571 |
| 60 | 0.20 | 60 | 38718 | 0.7018 | 0.6261 | 0.040 | 1.2260 | 0.255 | 1.1445 | -0.4427 | 1.1425 | -0.582,-0.469 | -0.574,-0.386,-0.482,-0.655,-0.544 |
| 60 | 0.20 | 120 | 38718 | 0.7233 | 0.6468 | 0.047 | 1.2072 | 0.255 | 1.1271 | -0.4037 | 1.1265 | -0.541,-0.430 | -0.531,-0.360,-0.436,-0.607,-0.505 |
| 60 | 0.20 | 240 | 38718 | 0.7530 | 0.6793 | 0.057 | 1.1850 | 0.254 | 1.1062 | -0.3532 | 1.1067 | -0.488,-0.379 | -0.478,-0.326,-0.384,-0.533,-0.456 |
| 60 | 0.30 | 15 | 55441 | 0.7257 | 0.6488 | 0.042 | 1.2546 | 0.255 | 1.1840 | -0.4583 | 1.1826 | -0.587,-0.475 | -0.597,-0.390,-0.494,-0.649,-0.529 |
| 60 | 0.30 | 30 | 55441 | 0.7348 | 0.6594 | 0.043 | 1.2405 | 0.256 | 1.1698 | -0.4350 | 1.1697 | -0.563,-0.452 | -0.570,-0.373,-0.468,-0.622,-0.509 |
| 60 | 0.30 | 60 | 55441 | 0.7498 | 0.6720 | 0.048 | 1.2260 | 0.255 | 1.1560 | -0.4062 | 1.1554 | -0.534,-0.422 | -0.539,-0.351,-0.436,-0.584,-0.484 |
| 60 | 0.30 | 120 | 55441 | 0.7685 | 0.6887 | 0.056 | 1.2072 | 0.255 | 1.1382 | -0.3696 | 1.1388 | -0.495,-0.386 | -0.503,-0.325,-0.394,-0.540,-0.443 |
| 60 | 0.30 | 240 | 55441 | 0.7956 | 0.7176 | 0.068 | 1.1850 | 0.254 | 1.1173 | -0.3218 | 1.1191 | -0.444,-0.337 | -0.454,-0.297,-0.347,-0.471,-0.387 |
| 120 | 0.10 | 15 | 21513 | 0.6191 | 0.5460 | 0.028 | 1.2546 | 0.255 | 1.1565 | -0.5374 | 1.1540 | -0.696,-0.579 | -0.672,-0.474,-0.602,-0.800,-0.667 |
| 120 | 0.10 | 30 | 21513 | 0.6316 | 0.5584 | 0.031 | 1.2405 | 0.256 | 1.1428 | -0.5112 | 1.1406 | -0.669,-0.553 | -0.639,-0.451,-0.571,-0.775,-0.647 |
| 120 | 0.10 | 60 | 21513 | 0.6505 | 0.5730 | 0.035 | 1.2260 | 0.255 | 1.1289 | -0.4784 | 1.1256 | -0.636,-0.519 | -0.601,-0.425,-0.532,-0.735,-0.622 |
| 120 | 0.10 | 120 | 21513 | 0.6734 | 0.5947 | 0.040 | 1.2072 | 0.255 | 1.1122 | -0.4388 | 1.1067 | -0.595,-0.479 | -0.553,-0.391,-0.489,-0.682,-0.593 |
| 120 | 0.10 | 240 | 21513 | 0.7027 | 0.6288 | 0.049 | 1.1850 | 0.254 | 1.0920 | -0.3893 | 1.0873 | -0.544,-0.427 | -0.485,-0.354,-0.434,-0.625,-0.553 |
| 120 | 0.20 | 15 | 38982 | 0.6828 | 0.6061 | 0.036 | 1.2546 | 0.255 | 1.1699 | -0.4871 | 1.1640 | -0.631,-0.516 | -0.630,-0.420,-0.536,-0.712,-0.583 |
| 120 | 0.20 | 30 | 38982 | 0.6915 | 0.6148 | 0.039 | 1.2405 | 0.256 | 1.1560 | -0.4645 | 1.1520 | -0.607,-0.494 | -0.603,-0.404,-0.509,-0.686,-0.565 |
| 120 | 0.20 | 60 | 38982 | 0.7065 | 0.6269 | 0.043 | 1.2260 | 0.255 | 1.1425 | -0.4359 | 1.1369 | -0.578,-0.465 | -0.570,-0.384,-0.477,-0.649,-0.539 |
| 120 | 0.20 | 120 | 38982 | 0.7268 | 0.6465 | 0.049 | 1.2072 | 0.255 | 1.1253 | -0.3985 | 1.1196 | -0.538,-0.426 | -0.526,-0.356,-0.433,-0.604,-0.502 |
| 120 | 0.20 | 240 | 38982 | 0.7539 | 0.6779 | 0.059 | 1.1850 | 0.254 | 1.1046 | -0.3507 | 1.1013 | -0.488,-0.377 | -0.471,-0.325,-0.383,-0.538,-0.457 |
| 120 | 0.30 | 15 | 55908 | 0.7373 | 0.6547 | 0.046 | 1.2546 | 0.255 | 1.1830 | -0.4457 | 1.1787 | -0.576,-0.463 | -0.587,-0.380,-0.483,-0.634,-0.517 |
| 120 | 0.30 | 30 | 55908 | 0.7434 | 0.6626 | 0.048 | 1.2405 | 0.256 | 1.1688 | -0.4254 | 1.1672 | -0.555,-0.443 | -0.563,-0.364,-0.461,-0.612,-0.500 |
| 120 | 0.30 | 60 | 55908 | 0.7561 | 0.6744 | 0.052 | 1.2260 | 0.255 | 1.1548 | -0.3986 | 1.1547 | -0.527,-0.416 | -0.533,-0.344,-0.431,-0.581,-0.474 |
| 120 | 0.30 | 120 | 55908 | 0.7748 | 0.6907 | 0.060 | 1.2072 | 0.255 | 1.1370 | -0.3623 | 1.1376 | -0.488,-0.380 | -0.494,-0.322,-0.390,-0.536,-0.432 |
| 120 | 0.30 | 240 | 55908 | 0.7987 | 0.7197 | 0.072 | 1.1850 | 0.254 | 1.1162 | -0.3175 | 1.1184 | -0.440,-0.333 | -0.446,-0.297,-0.347,-0.474,-0.379 |

## Parameter robustness

Desired expansion shape: q10 effect ≥ q20 ≥ q30, and more than one lookback.

Observed: q10 is strictly more negative than q20, which is strictly more negative than q30, for every L and H. Lookbacks agree. Horizons agree. The monotonicity is real and is the reverse of expansion.

Robustness for the **hypothesized expansion mechanism:** **NO**.

## Controls

Matched-random (seed 20260826, 100 replicates, month-count preserved) stays near **1.09–1.19**, close to baseline A.

Within-month permutation of compression scores (seed 20260827) restores means near **1.09–1.18** and expansion probabilities near **0.20–0.22**.

True compression timing therefore contains information, but that information is **lower** subsequent RV, not expansion. True timing did **not** outperform controls on the preregistered expansion hypothesis.

## Chronological stability (representative L=60, q=0.10, H=60)

| year | N | mean norm RV | baseline | diff | p(exp) | baseline p(exp) |
|---|---|---|---|---|---|---|
| 2020 | 4341 | 0.6982 | 1.3129 | -0.6147 | 0.050 | 0.273 |
| 2021 | 4592 | 0.7312 | 1.1577 | -0.4265 | 0.041 | 0.247 |
| 2022 | 4751 | 0.6388 | 1.1763 | -0.5374 | 0.034 | 0.231 |
| 2023 | 3667 | 0.5524 | 1.2953 | -0.7430 | 0.021 | 0.266 |
| 2024 | 3773 | 0.5713 | 1.1949 | -0.6236 | 0.013 | 0.260 |

All 45 cells × 5 years = 225 year-blocks are negative on the primary difference. 2021 is the least negative; 2023 is typically the most negative. No year supports expansion.

## Concentration (L=60, q=0.10, H=60)

- unique UTC days: 1069
- unique UTC weeks: 231
- unique UTC months: 59
- max single-month share: 3.8%
- top-5 month share: 17.9%
- adjacent-boundary fraction: 0.811
- max run length: 76
- mean run length: 5.28
- n runs: 3999

Across the nine L×q configurations, max month share is about 3.0–3.8% and top-5 share about 14–18%. Concentration is not a single-month artifact. Clustering is high (overlapping 15m qualifications), so raw N is not iid; week-block bootstrap is the uncertainty used above.

## Decile diagnostic (L=60, H=60)

Spearman of bin-mean normalized future RV versus decile order: **1.0** (same sign for every L×H). Lower compression percentile (stronger compression) corresponds to **lower** future RV, not higher.

| bin | N | mean norm RV | median | p(exp) |
|---|---|---|---|---|
| [0,10) | 21064 | 0.6438 | 0.5722 | 0.033 |
| [10,20) | 17593 | 0.7708 | 0.6875 | 0.050 |
| [20,30) | 16728 | 0.8609 | 0.7701 | 0.065 |
| [30,40) | 16484 | 0.9482 | 0.8420 | 0.098 |
| [40,50) | 16085 | 1.0353 | 0.9239 | 0.124 |
| [50,60) | 15989 | 1.1424 | 1.0188 | 0.176 |
| [60,70) | 16268 | 1.2606 | 1.1268 | 0.247 |
| [70,80) | 16566 | 1.4333 | 1.2671 | 0.365 |
| [80,90) | 17025 | 1.6987 | 1.4911 | 0.562 |
| [90,100] | 18598 | 2.4795 | 2.0151 | 0.822 |

Do not select a threshold from these bins. They are reported only to show the relationship is monotonic in the persistence direction.

## Secondary range

Normalized future high-low range is also below baseline in every cell (about **0.63–0.87** versus baseline **~1.28–1.32**). Range agrees with the primary RV result and cannot rescue expansion.

## Candidate-for-R3 criteria (all required)

| # | Criterion | Result |
|---|---|---|
| 1 | true compression separates from matched-random for at least one lookback | separates, **opposite sign** |
| 2 | permutation weakens/destroys the relationship | permutation returns near baseline |
| 3 | neighboring q plateau or sensible strength-response | monotonic, **more compression → more negative** |
| 4 | effect on at least two adjacent horizons | all five horizons negative |
| 5 | positive in at least 4 of 5 years | **0 of 5** |
| 6 | no single month dominates | max month share ~3–4% |
| 7 | bootstrap compatible with a real positive expansion effect | **all CIs negative** |
| 8 | primary RV supports the mechanism | **no; primary supports persistence** |

`H01_CANDIDATE_FOR_R3` is not met.

`H01_INCONCLUSIVE` is not used: the expansion relationship is not suggestive; it is consistently rejected.

## Development verdict

**H01_KILL** — compression→expansion did not earn further complexity.

Do not reframe the reverse persistence relationship as a new authorized hypothesis in this task. A later task may preregister a distinct persistence/clustering hypothesis if wanted.

Do not inspect 2025. Do not inspect 2026. Do not start R3. Do not modify forecasting/product architecture.
