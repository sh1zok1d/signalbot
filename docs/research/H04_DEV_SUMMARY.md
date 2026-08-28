# H04 Trend Pullback → Continuation — Development Results

**Status:** FROZEN_EVIDENCE / EXPLORATORY
**Hypothesis ID:** `H04_TREND_PULLBACK_CONTINUATION`
**Development verdict:** `H04_REJECTED_SPECIFIC_CLAIM`
**Machine-readable:** `docs/research/H04_DEV_RESULTS.json` (exact runner output; numerical values not edited)
**Preregistration:** `docs/research/H04_TREND_PULLBACK_PREREG.md`

This document records the one authorized development-only outcome inspection. It is not confirmatory, not a trading system, not an exhaustion candidate, and not authorization to open 2025 validation, 2026 OOS, R3, or H05.

H01 remains `H01_KILL`. H02 remains `H02_KILL`. H03 remains `H03_REJECTED_SPECIFIC_CLAIM`. None is reinterpreted here. H01/H02/H03 post-hoc observations are not H04 gates.

## Identity

| Field | Value |
|---|---|
| dataset | `CORE_BTC_BINANCE_V0` |
| snapshot_id | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| dataset root | `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0` |
| H04_PREREG_SHA | `c629cac4c6ed1a0d129b812ef022d98a0dba4c1b` |
| H04_RESEARCH_CODE_FREEZE_SHA | `7bfdc44a305035a641c25f9d3ee75c6ef652ece0` |
| research_code_sha in JSON | `7bfdc44a305035a641c25f9d3ee75c6ef652ece0` |
| generated_at_utc | `2026-08-27T12:42:08Z` |
| development window | 2020-02-01T00:00:00Z → 2025-01-01T00:00:00Z |
| t_max_inclusive | 2024-12-31T19:45:00Z |
| 2025 validation inspected | NO |
| 2026 OOS inspected | NO |
| pyarrow | 17.0.0 |
| 2020–2024 parquet SHA | 60 / 60 exact |
| 2020–2024 provenance SHA | 60 / 60 exact |
| one real `--stage dev-run` | YES |

HEAD at the outcome run was the freeze SHA. No H04 source, test, or preregistration file was modified before or after the run.

## Search surface

3 trend lookbacks (`L=240/480/960`m) × 3 exclusive depth bands (`shallow` / `moderate` / `deep`) × 5 horizons (`H=15/30/60/120/240`m) = **45 primary cells**.

Continuation-only. No exhaustion alternative. Global prior: H01 45, H02 45, H03 45.

Matched-random seed `20260902` × 100. Week-block bootstrap seed `20260903` × 2000, plus fixed 1w/2w/4w sensitivity. MPIE 0.10 vs matched-random. `CONTROL_DELTA_MIN=0.05` for standardized structural delta and true-minus-+6h.

## Sample

UTC 15-minute grid. N is identical across H for a given L×band because `T+240m < 2025-01-01` is applied to every eligible event. Structural unmatched candidate share is 0 except L=960 moderate (2 / 892 = 0.0022).

| L | band | raw | post-refractory N | UP share | DOWN share | largest month | largest share | top-5 share | median spacing (min) |
|---|---|---|---|---|---|---|---|---|---|
| 240 | shallow | 6203 | 4000 | 0.518 | 0.482 | 2021-05 | 0.0288 | 0.1247 | 330 |
| 240 | moderate | 3471 | 2511 | 0.470 | 0.530 | 2021-05 | 0.0319 | 0.1398 | 540 |
| 240 | deep | 3271 | 2075 | 0.460 | 0.540 | 2020-03 | 0.0342 | 0.1658 | 532.5 |
| 480 | shallow | 6538 | 3804 | 0.510 | 0.490 | 2021-05 | 0.0310 | 0.1354 | 240 |
| 480 | moderate | 2354 | 1691 | 0.444 | 0.556 | 2021-05 | 0.0408 | 0.1632 | 630 |
| 480 | deep | 1645 | 975 | 0.463 | 0.537 | 2020-03 | 0.0513 | 0.2041 | 997.5 |
| 960 | shallow | 5568 | 3094 | 0.499 | 0.501 | 2021-05 | 0.0339 | 0.1422 | 240 |
| 960 | moderate | 1313 | 892 | 0.447 | 0.553 | 2021-01 | 0.0493 | 0.2096 | 1080 |
| 960 | deep | 627 | 370 | 0.500 | 0.500 | 2020-03 | 0.0541 | 0.2297 | 2640 |

Deep L=960 is the sparsest (N=370) with the widest spacing. Structural overlap is not a limitation: unmatched share is essentially zero. No invented N pass/fail threshold is applied.

## Primary effect shape — MIXED; isolated moderate-band continuation; not a depth neighborhood

Without cherry-picking:

- Means: **34 positive / 11 negative**. Medians: **35 positive / 9 negative** (one median = 0). `P(CONT>0)`: **35 above 0.5 / 10 below**.
- MPIE (`dMat ≥ 0.10`): **16 / 45**. Structural (`sDelta ≥ 0.05`): **26 / 45**. +6h (`true−shifted ≥ 0.05`): **15 / 45**. All three gates: **10 / 45**.
- Continuation that meets MPIE concentrates in **moderate** bands at L=480 and L=960, plus a few isolated deep/shallow cells. It is **not** a two-adjacent-band neighborhood inside any L.
- Adjacent **deep** cells at short H are often **negative** vs matched-random (L=480/960 deep H=15 dMat −0.15 / −0.29). That is the opposite of a depth-robust pullback-continuation mechanism.
- Adjacent **shallow** cells at L=480/960 are often positive but **below MPIE 0.10** at short H.

The frozen claim is established-trend + material counter-trend pullback as incremental continuation, robust across a depth neighborhood. An isolated moderate band cannot promote H04 (§19: one isolated band cannot promote).

## All 45 primary cells

meanN / medN = mean/median `NORM` trend-direction continuation. bps = mean raw continuation. dMat = candidate−matched. sDelta = standardized pullback−neutral. d6h = true−+6h. MP/ST/N6 = MPIE / structural / +6h gates.

| L | band | H | N | raw | meanN | medN | bps | p>0 | dMat | sDelta | d6h | MP | ST | N6 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 240 | shallow | 15 | 4000 | 6203 | -0.0194 | 0.0534 | -0.095 | 0.509 | -0.0280 | 0.0446 | -0.0756 | N | N | N |
| 240 | shallow | 30 | 4000 | 6203 | 0.0092 | 0.0220 | 0.433 | 0.505 | 0.0029 | -0.0051 | -0.0666 | N | N | N |
| 240 | shallow | 60 | 4000 | 6203 | 0.0194 | -0.0523 | 0.414 | 0.488 | -0.0001 | -0.0304 | 0.0055 | N | N | N |
| 240 | shallow | 120 | 4000 | 6203 | 0.0178 | -0.0786 | 0.136 | 0.480 | -0.0063 | -0.0667 | -0.0540 | N | N | N |
| 240 | shallow | 240 | 4000 | 6203 | -0.0096 | -0.1194 | -2.588 | 0.466 | -0.0440 | -0.0465 | -0.1514 | N | N | N |
| 240 | moderate | 15 | 2511 | 3471 | 0.0672 | 0.2476 | 0.935 | 0.548 | 0.0684 | 0.1543 | 0.1173 | N | Y | Y |
| 240 | moderate | 30 | 2511 | 3471 | 0.0795 | 0.1402 | 1.700 | 0.529 | 0.0781 | 0.0978 | 0.0755 | N | Y | Y |
| 240 | moderate | 60 | 2511 | 3471 | 0.0416 | 0.0514 | 1.440 | 0.510 | 0.0387 | 0.0194 | 0.1393 | N | N | Y |
| 240 | moderate | 120 | 2511 | 3471 | -0.0040 | -0.0257 | -0.973 | 0.493 | -0.0068 | -0.0684 | 0.0364 | N | N | N |
| 240 | moderate | 240 | 2511 | 3471 | -0.0033 | -0.0759 | -3.229 | 0.484 | -0.0066 | -0.0172 | -0.0653 | N | N | N |
| 240 | deep | 15 | 2075 | 3271 | 0.1269 | 0.4174 | 1.597 | 0.570 | 0.1235 | 0.1787 | 0.0703 | Y | Y | Y |
| 240 | deep | 30 | 2075 | 3271 | 0.1580 | 0.3424 | 2.378 | 0.554 | 0.1537 | 0.1441 | 0.1031 | Y | Y | Y |
| 240 | deep | 60 | 2075 | 3271 | 0.0934 | 0.1681 | 1.093 | 0.529 | 0.0796 | 0.0463 | 0.0362 | N | N | N |
| 240 | deep | 120 | 2075 | 3271 | -0.0527 | -0.0353 | -2.326 | 0.493 | -0.0737 | -0.1694 | -0.0594 | N | N | N |
| 240 | deep | 240 | 2075 | 3271 | -0.0239 | -0.0515 | -1.994 | 0.494 | -0.0379 | -0.0330 | -0.1742 | N | N | N |
| 480 | shallow | 15 | 3804 | 6538 | 0.0809 | 0.1888 | 1.123 | 0.537 | 0.0646 | 0.1223 | 0.0552 | N | Y | Y |
| 480 | shallow | 30 | 3804 | 6538 | 0.0676 | 0.1760 | 1.557 | 0.540 | 0.0495 | 0.0736 | -0.0168 | N | Y | N |
| 480 | shallow | 60 | 3804 | 6538 | 0.0848 | 0.0852 | 1.902 | 0.517 | 0.0561 | 0.0779 | 0.0072 | N | Y | N |
| 480 | shallow | 120 | 3804 | 6538 | 0.0345 | -0.0070 | 0.967 | 0.498 | -0.0009 | -0.0031 | -0.1255 | N | N | N |
| 480 | shallow | 240 | 3804 | 6538 | 0.0120 | -0.0402 | -0.888 | 0.488 | -0.0327 | -0.0535 | -0.1853 | N | N | N |
| 480 | moderate | 15 | 1691 | 2354 | 0.1815 | 0.3714 | 2.647 | 0.580 | 0.1931 | 0.2356 | 0.0972 | Y | Y | Y |
| 480 | moderate | 30 | 1691 | 2354 | 0.1673 | 0.3311 | 2.866 | 0.559 | 0.1699 | 0.1873 | 0.0142 | Y | Y | N |
| 480 | moderate | 60 | 1691 | 2354 | 0.1405 | 0.2269 | 1.952 | 0.543 | 0.1387 | 0.1752 | 0.0770 | Y | Y | Y |
| 480 | moderate | 120 | 1691 | 2354 | 0.1464 | 0.0440 | 2.481 | 0.509 | 0.1374 | 0.1294 | 0.0534 | Y | Y | Y |
| 480 | moderate | 240 | 1691 | 2354 | 0.0834 | 0.0000 | 1.108 | 0.500 | 0.0587 | 0.0604 | -0.0032 | N | Y | N |
| 480 | deep | 15 | 975 | 1645 | -0.1308 | 0.4969 | -0.481 | 0.554 | -0.1527 | -0.0602 | -0.4324 | N | N | N |
| 480 | deep | 30 | 975 | 1645 | 0.0048 | 0.3566 | 0.478 | 0.564 | -0.0236 | 0.0148 | -0.3004 | N | N | N |
| 480 | deep | 60 | 975 | 1645 | -0.0264 | 0.2078 | -0.130 | 0.529 | -0.0445 | -0.0130 | -0.1414 | N | N | N |
| 480 | deep | 120 | 975 | 1645 | -0.0699 | 0.0739 | -2.416 | 0.508 | -0.0886 | -0.1166 | -0.1833 | N | N | N |
| 480 | deep | 240 | 975 | 1645 | 0.1771 | 0.2033 | 9.488 | 0.536 | 0.1450 | 0.1160 | 0.1291 | Y | Y | Y |
| 960 | shallow | 15 | 3094 | 5568 | 0.0509 | 0.2619 | 0.712 | 0.548 | 0.0451 | 0.0943 | 0.0369 | N | Y | N |
| 960 | shallow | 30 | 3094 | 5568 | 0.0758 | 0.1830 | 1.081 | 0.542 | 0.0645 | 0.0679 | -0.0640 | N | Y | N |
| 960 | shallow | 60 | 3094 | 5568 | 0.1181 | 0.1183 | 1.897 | 0.521 | 0.0988 | 0.0658 | 0.0580 | N | Y | Y |
| 960 | shallow | 120 | 3094 | 5568 | 0.2133 | 0.1073 | 5.549 | 0.524 | 0.1708 | 0.1275 | -0.0068 | Y | Y | N |
| 960 | shallow | 240 | 3094 | 5568 | 0.2201 | 0.0542 | 7.264 | 0.514 | 0.1589 | 0.0671 | -0.1881 | Y | Y | N |
| 960 | moderate | 15 | 892 | 1313 | 0.4113 | 0.5452 | 5.465 | 0.605 | 0.4168 | 0.4448 | 0.3678 | Y | Y | Y |
| 960 | moderate | 30 | 892 | 1313 | 0.4078 | 0.5263 | 7.126 | 0.582 | 0.4111 | 0.3732 | 0.5274 | Y | Y | Y |
| 960 | moderate | 60 | 892 | 1313 | 0.2180 | 0.2534 | 4.130 | 0.550 | 0.2074 | 0.1654 | 0.3432 | Y | Y | Y |
| 960 | moderate | 120 | 892 | 1313 | 0.2289 | 0.1414 | 6.352 | 0.531 | 0.2070 | 0.1484 | 0.0139 | Y | Y | N |
| 960 | moderate | 240 | 892 | 1313 | 0.1898 | 0.0523 | 6.000 | 0.504 | 0.1486 | 0.0590 | -0.0908 | Y | Y | N |
| 960 | deep | 15 | 370 | 627 | -0.2580 | 0.5337 | -2.479 | 0.554 | -0.2850 | -0.2403 | -0.4158 | N | N | N |
| 960 | deep | 30 | 370 | 627 | -0.1665 | 0.3970 | -2.297 | 0.549 | -0.2063 | -0.1926 | -0.3471 | N | N | N |
| 960 | deep | 60 | 370 | 627 | 0.1822 | 0.4663 | 5.748 | 0.559 | 0.1337 | 0.1644 | 0.1879 | Y | Y | Y |
| 960 | deep | 120 | 370 | 627 | 0.1243 | 0.3147 | 2.988 | 0.546 | 0.0699 | 0.0652 | -0.1788 | N | Y | N |
| 960 | deep | 240 | 370 | 627 | 0.2977 | 0.1405 | 13.055 | 0.530 | 0.2183 | 0.1254 | 0.0303 | Y | Y | N |

## Matched random

Seed `20260902`, 100 replicates, month and UPTREND/DOWNTREND composition preserved.

Matched means sit near 0. Candidate-minus-matched therefore tracks the candidate mean. MPIE 0.10 holds in 16/45 cells, clustered in moderate L=480/960, not a two-band neighborhood.

## Structural control

Established-trend + `abs(RECENT_RATIO)<0.10`, standardized by calendar-month × trend-direction × trend-strength-bin matching. Gate uses `standardized_delta`, not the unstandardized full-control mean.

Standardized delta ≥ 0.05 in 26/45. Unmatched candidate share ≈ 0 (max 0.0022). Structural overlap is not why H04 fails. Moderate bands often beat the near-neutral control; adjacent deep short-H cells often do not.

## +6h negative control

Same-UTC-day circular +6h, original trend direction preserved. Collision fraction ≈ 0.02–0.06.

True-minus-shifted ≥ 0.05 in 15/45. Even the strongest moderate slices miss this gate at some adjacent H (L=480 moderate H=30 d6h=0.014; L=960 moderate H=120/240 negative).

## Depth robustness

**NO** as a freeze neighborhood.

Promotion requires two **adjacent** exclusive bands within one L. Observed:

- L=240: shallow null; moderate below MPIE; deep MPIE only at H=15/30 (not adjacent to a second MPIE band).
- L=480: moderate MPIE at H=15–120; adjacent shallow below MPIE; adjacent deep negative at short H (isolated H=240 triple-gate).
- L=960: moderate MPIE at all five H; adjacent shallow MPIE only at H=120/240 and +6h mostly fails; adjacent deep negative at H=15/30.

One isolated moderate band cannot promote H04.

## Horizon robustness

Within L=480 moderate and L=960 moderate, several adjacent H are positive on the primary metric. That local adjacent-H support is real and is **not** enough: it sits inside a single exclusive depth band, and +6h / bootstrap do not hold across those H.

Elsewhere, H sign-flips (short-H continuation vs longer-H fade at L=240; short-H reversal vs long-H bounce in deep L=480/960).

## Year stability

Not 4/5-year stable across the 45-cell surface.

L=960 moderate is the most year-stable slice (H=15/30/240 all 5/5 positive; H=60/120 4/5 with 2021 negative). L=480 moderate H=15 is 4/5 (2022 negative); H=60/120 only 3/5. 2022 is frequently the negative year on shorter L. No year was excluded.

## UP/DOWN symmetry

H04 requires both UPTREND and DOWNTREND continuation.

- L=480 moderate: both sides positive at all five H.
- L=960 moderate: both sides positive at H=15–120; H=240 DOWNTREND slightly negative.
- Many shallow cells: UPTREND positive, DOWNTREND weaker or negative.
- Deep short-H L=480/960: UPTREND often negative.

Symmetric claim is **not** supported as a depth neighborhood. L=480 moderate both-sides support is `POSTHOC_UNTESTED` as an isolated-band observation.

## Concentration

Largest-month share **2.9–5.4%**. Top-5 **12–23%**. Typical top months: 2021-05, 2020-03, 2021-01, 2020-11, 2023-01. No single month dominates. Median spacing 240–2640 minutes (wider in deep L=960).

## Dependence

Week-block bootstrap (seed 20260903, 2000 replicates) and 1w/2w/4w sensitivity are present on every cell.

CIs that exclude 0 on the candidate normalized mean are uncommon. The clearest: L=960 moderate H=15 and H=30, 1w/2w/4w all entirely positive; L=960 shallow H=120/240 likewise; L=480 moderate H=15 1w/2w/4w entirely positive. Most other MPIE cells have intervals that include 0.

Long-dependence diagnostic (candidate-independent daily |15m log-return| ACF):

| lag (days) | ACF |
|---|---|
| 1 | 0.727 |
| 2 | 0.562 |
| 4 | 0.509 |
| 8 | 0.400 |
| 16 | 0.270 |
| 32 | 0.235 |
| 64 | 0.192 |

`L_dep = 32 days`. Effective N is not iid. Disclosed; does not rescue the neighborhood failure.

## Candidate-for-freeze criteria (all required)

| # | Criterion | Result |
|---|---|---|
| 1 | positive primary continuation | **PARTIAL** (34/45 means positive; mixed surface) |
| 2 | MPIE 0.10 in a broad neighborhood | **NO** (16/45; concentrated in one exclusive band) |
| 3 | standardized structural delta ≥ 0.05 | PARTIAL (26/45; not two adjacent bands) |
| 4 | true-minus-+6h ≥ 0.05 | PARTIAL (15/45; fails inside the best slices) |
| 5 | two adjacent exclusive depth bands | **NO** (moderate isolated; deep often opposite at short H) |
| 6 | two adjacent H | PARTIAL (yes inside moderate L=480/960 only) |
| 7 | sign in ≥4/5 years | PARTIAL (yes in L=960 moderate short H; not the surface) |
| 8 | UPTREND and DOWNTREND both | PARTIAL (yes L=480 moderate; fail many other cells) |
| 9 | no dominant month | **YES** (2.9–5.4%) |
| 10 | bootstrap compatible with real positive | PARTIAL (few cells; not a neighborhood) |
| 11 | L_dep disclosed | `L_dep=32 days`; ACF64=0.192 |
| 12 | primary close-return supports mechanism | **NO** as scoped (isolated band; adjacent deep often reverses) |

`H04_CONTINUATION_CANDIDATE_FOR_FREEZE` is not met.

This is not `H04_INCONCLUSIVE`: structural overlap is excellent, N in shallow/moderate is large, and the specific two-adjacent-band continuation claim can be resolved. It fails.

No exhaustion alternative is defined for H04.

## Post-hoc observations

Each is **`POSTHOC_UNTESTED`**. None may rescue H04, change sign, or start a child test in this task.

- `POSTHOC_UNTESTED:` L=480 and L=960 **moderate-only** continuation (MPIE on several adjacent H; L=480 moderate both UP and DOWN). Isolated exclusive band.
- `POSTHOC_UNTESTED:` L=960 shallow longer-H (120/240) MPIE with bootstrap CIs excluding 0; +6h fails.
- `POSTHOC_UNTESTED:` deep short-H reversal vs matched-random at L=480/960 H=15 (dMat −0.15 / −0.29). Not an authorized exhaustion claim.
- `POSTHOC_UNTESTED:` 2022 often the most negative year on shorter L.
- `POSTHOC_UNTESTED:` UPTREND stronger than DOWNTREND in many shallow cells.

## Development verdict

**`H04_REJECTED_SPECIFIC_CLAIM`** — established-trend + material counter-trend pullback, as preregistered (45 cells, MPIE 0.10, standardized near-neutral structural control, +6h, two adjacent exclusive depth bands, two adjacent H, 4/5 years, UP/DOWN symmetry), did not earn further complexity.

Do not add indicators. Do not promote moderate-only. Do not create an exhaustion candidate. Do not inspect 2025. Do not inspect 2026. Do not start R3. Do not start H05.

2025 inspected: **NO**
2026 inspected: **NO**
