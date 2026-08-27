# H03 Extreme Impulse → Continuation vs Exhaustion — Development Results

**Status:** FROZEN_EVIDENCE / EXPLORATORY
**Hypothesis ID:** `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION`
**Development verdict:** `H03_REJECTED_SPECIFIC_CLAIM`
**Machine-readable:** `docs/research/H03_DEV_RESULTS.json`
**Preregistration:** `docs/research/H03_EXTREME_IMPULSE_PREREG.md`

This document records the development-only outcome inspection. It is not a confirmatory result, not a trading strategy, not a liquidation/news/market-maker claim, and not authorization to open 2025 validation, 2026 OOS, R3, or H04.

H01 remains `H01_KILL`. H02 remains `H02_KILL`. Neither is reinterpreted here.

## Identity

| Field | Value |
|---|---|
| dataset | `CORE_BTC_BINANCE_V0` |
| snapshot_id | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| dataset root | `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0` |
| materializer provenance | `71d13afdae4456163316b850f340436af1eeed65` |
| prereg commit (`H03_PREREG_SHA`) | `e2c370d70ca3dc5952ad9c82808e6b877805f998` |
| research code SHA at outcome run | `4e995440e649b37bdc0a9f0100a3e0b369573f6c` |
| generated_at_utc | `2026-08-27T09:54:28Z` |
| development window | 2020-02-01T00:00:00Z → 2025-01-01T00:00:00Z |
| t_max_inclusive | 2024-12-31T19:45:00Z |
| 2025 validation inspected | NO |
| 2026 OOS inspected | NO |
| pyarrow | 17.0.0 |

The frozen preregistration HEAD (`e2c370d`) IndexError'd in `build_matched_random_pool` before any cell outcome (panel indices fancy-indexed into `len(elig)`). Membership exclusion was committed as `4e99544` after preregistration and before this single outcome run. No research parameter, seed, window, W/q/H, refractory, MPIE, or control was changed. `H03_PREREG_SHA` was not amended.

2020–2024 canonical 1m parquet SHA vs accepted snapshot evidence: **60 / 60 exact**. Corresponding provenance JSON: **60 / 60 exact**. 2025/2026 parquet files were not opened.

## Search surface

3 impulse windows (`W=15/30/60`m) × 3 tail thresholds (`q=0.90/0.95/0.98`) × 5 horizons (`H=15/30/60/120/240`m) = **45 primary cells**.

Both continuation (`S=+1`) and exhaustion (`S=−1`) were preregistered competing readings of the same signed statistic `CONT_RET_H = direction × RET_H`, normalized by trailing 30d median `|RET_H|` with no floor.

Global prior: H01 = 45 cells, H02 = 45 cells. H03 is the third R2 Batch 01 family on the same 2020–2024 discovery lab.

## Sample

UTC 15-minute grid; 60-minute either-direction refractory. N is identical across H for a given W×q because `T+240m < 2025-01-01` is applied to every eligible event.

| W | q | raw pre-refractory N | post-refractory N | UP share | DOWN share | 2020 | 2021 | 2022 | 2023 | 2024 |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 0.90 | 18095 | 10785 | 0.499 | 0.501 | 2073 | 2220 | 2073 | 2230 | 2189 |
| 15 | 0.95 | 9275 | 6090 | 0.491 | 0.509 | 1187 | 1272 | 1163 | 1248 | 1220 |
| 15 | 0.98 | 3832 | 2810 | 0.494 | 0.506 | 551 | 578 | 566 | 553 | 562 |
| 30 | 0.90 | 18123 | 9561 | 0.503 | 0.497 | 1873 | 1962 | 1763 | 1992 | 1971 |
| 30 | 0.95 | 9259 | 5207 | 0.496 | 0.504 | 1043 | 1069 | 1005 | 1050 | 1040 |
| 30 | 0.98 | 3840 | 2317 | 0.496 | 0.504 | 458 | 479 | 456 | 454 | 470 |
| 60 | 0.90 | 17987 | 7860 | 0.508 | 0.492 | 1556 | 1577 | 1439 | 1628 | 1660 |
| 60 | 0.95 | 9191 | 4087 | 0.503 | 0.497 | 835 | 806 | 755 | 843 | 848 |
| 60 | 0.98 | 3874 | 1771 | 0.494 | 0.506 | 353 | 359 | 336 | 346 | 377 |

UP/DOWN composition is essentially balanced. Years are balanced. Refractory collapses raw counts by roughly half at q90 and less at q98.

## Primary effect shape — MIXED-NULL

Without cherry-picking:

- **All 45 cells** have `P(CONT_RET_H > 0)` in **0.429–0.481** (all below 0.5).
- **All 45 cells** have **negative median** `NORM_CONT_RET_H` (about −0.46 to −0.19).
- Mean `NORM_CONT_RET_H` is mixed: **14 positive, 31 negative**. Across-cell mean of means ≈ **−0.025**.
- Mean raw continuation is typically **a few bps** (range about −8.2 to +4.7 bps). Positive means are right-tail pulls against a negative median.
- Short-H / more-extreme-q cells sometimes show a positive mean; longer H more often a negative mean. The sign **flips with horizon**.

This is not a broad continuation surface and not a broad exhaustion surface. It is a mixed-null primary: count/median mildly against continuation, means unstable and tail-driven.

Gates (preregistered, auto-computed, not trusted blindly):

| Gate | True | False |
|---|---|---|
| MPIE continuation (`S=+1`, Δ≥0.10 vs matched) | 3 | 42 |
| MPIE exhaustion (`S=−1`, Δ≥0.10 vs matched) | 11 | 34 |
| structural continuation (Δ≥0.05 vs moderate) | 8 | 37 |
| structural exhaustion (Δ≥0.05 vs moderate) | 17 | 28 |
| +6h continuation (Δ≥0.05 vs shifted) | 12 | 33 |
| +6h exhaustion (Δ≥0.05 vs shifted) | 25 | 20 |

Continuation MPIE cells (only): `W=15 q=0.98 H=15`, `W=15 q=0.98 H=30`, `W=60 q=0.95 H=15`. Those are isolated, not a neighborhood. Neighbor `W=60 q=0.98 H=15` has the **opposite** sign (exhaustion MPIE).

## All 45 primary cells

meanN / medN = mean/median `NORM_CONT_RET_H`. bps = mean `CONT_RET_H` in basis points. match = matched-random mean. dMat = extreme − matched. mod = moderate-momentum mean. dMod = extreme − moderate. shft = +6h shifted mean. dSh = extreme − shifted. MC/ME/SC/SE/NC/NE = MPIE continuation/exhaustion, structural continuation/exhaustion, +6h continuation/exhaustion.

| W | q | H | N | raw | meanN | medN | bps | p>0 | match | dMat | mod | dMod | shft | dSh | MC | ME | SC | SE | NC | NE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 0.90 | 15 | 10785 | 18095 | 0.0176 | -0.3615 | 0.505 | 0.443 | 0.0011 | 0.0165 | -0.0312 | 0.0488 | -0.0441 | 0.0617 | N | N | N | N | Y | N |
| 15 | 0.90 | 30 | 10785 | 18095 | -0.0148 | -0.2829 | -0.578 | 0.453 | 0.0035 | -0.0182 | -0.0477 | 0.0329 | -0.0255 | 0.0108 | N | N | N | N | N | N |
| 15 | 0.90 | 60 | 10785 | 18095 | -0.0427 | -0.2640 | -1.345 | 0.452 | 0.0039 | -0.0467 | -0.0098 | -0.0330 | 0.0128 | -0.0556 | N | N | N | N | N | Y |
| 15 | 0.90 | 120 | 10785 | 18095 | -0.0780 | -0.2645 | -3.207 | 0.452 | 0.0105 | -0.0884 | 0.0076 | -0.0856 | 0.0278 | -0.1058 | N | N | N | Y | N | Y |
| 15 | 0.90 | 240 | 10785 | 18095 | -0.0409 | -0.2114 | -3.435 | 0.458 | 0.0104 | -0.0512 | 0.0204 | -0.0613 | 0.0379 | -0.0788 | N | N | N | Y | N | Y |
| 15 | 0.95 | 15 | 6090 | 9275 | 0.0821 | -0.4001 | 1.328 | 0.449 | 0.0014 | 0.0808 | -0.0312 | 0.1133 | -0.0689 | 0.1511 | N | N | Y | N | Y | N |
| 15 | 0.95 | 30 | 6090 | 9275 | 0.0081 | -0.3372 | 0.438 | 0.453 | 0.0022 | 0.0059 | -0.0477 | 0.0558 | -0.0492 | 0.0574 | N | N | Y | N | Y | N |
| 15 | 0.95 | 60 | 6090 | 9275 | -0.0410 | -0.3127 | -0.848 | 0.453 | 0.0057 | -0.0466 | -0.0098 | -0.0312 | 0.0430 | -0.0840 | N | N | N | N | N | Y |
| 15 | 0.95 | 120 | 6090 | 9275 | -0.0942 | -0.3153 | -3.147 | 0.454 | 0.0122 | -0.1065 | 0.0076 | -0.1019 | 0.0410 | -0.1352 | N | Y | N | Y | N | Y |
| 15 | 0.95 | 240 | 6090 | 9275 | -0.0661 | -0.2703 | -4.529 | 0.451 | 0.0162 | -0.0823 | 0.0204 | -0.0865 | 0.0766 | -0.1427 | N | N | N | Y | N | Y |
| 15 | 0.98 | 15 | 2810 | 3832 | 0.2864 | -0.2231 | 4.743 | 0.472 | 0.0013 | 0.2851 | -0.0312 | 0.3176 | -0.0935 | 0.3799 | Y | N | Y | N | Y | N |
| 15 | 0.98 | 30 | 2810 | 3832 | 0.1426 | -0.1926 | 3.600 | 0.481 | 0.0053 | 0.1372 | -0.0477 | 0.1903 | 0.0158 | 0.1268 | Y | N | Y | N | Y | N |
| 15 | 0.98 | 60 | 2810 | 3832 | 0.0231 | -0.2748 | 1.158 | 0.463 | 0.0044 | 0.0187 | -0.0098 | 0.0329 | 0.0890 | -0.0659 | N | N | N | N | N | Y |
| 15 | 0.98 | 120 | 2810 | 3832 | -0.1183 | -0.2736 | -3.066 | 0.464 | 0.0031 | -0.1214 | 0.0076 | -0.1259 | 0.1717 | -0.2900 | N | Y | N | Y | N | Y |
| 15 | 0.98 | 240 | 2810 | 3832 | -0.1246 | -0.2028 | -6.215 | 0.466 | 0.0116 | -0.1362 | 0.0204 | -0.1451 | 0.1733 | -0.2979 | N | Y | N | Y | N | Y |
| 30 | 0.90 | 15 | 9561 | 18123 | -0.0557 | -0.4445 | -0.855 | 0.429 | 0.0003 | -0.0560 | -0.0480 | -0.0077 | -0.0611 | 0.0054 | N | N | N | N | N | N |
| 30 | 0.90 | 30 | 9561 | 18123 | -0.0598 | -0.3922 | -1.491 | 0.434 | -0.0003 | -0.0595 | -0.0467 | -0.0130 | -0.0301 | -0.0297 | N | N | N | N | N | N |
| 30 | 0.90 | 60 | 9561 | 18123 | -0.1028 | -0.3229 | -2.850 | 0.445 | 0.0009 | -0.1037 | -0.0322 | -0.0706 | 0.0144 | -0.1172 | N | Y | N | Y | N | Y |
| 30 | 0.90 | 120 | 9561 | 18123 | -0.1044 | -0.2931 | -4.235 | 0.450 | 0.0036 | -0.1080 | -0.0245 | -0.0799 | 0.0395 | -0.1439 | N | Y | N | Y | N | Y |
| 30 | 0.90 | 240 | 9561 | 18123 | -0.0578 | -0.2472 | -4.585 | 0.455 | 0.0105 | -0.0683 | -0.0136 | -0.0442 | 0.0783 | -0.1361 | N | N | N | N | N | Y |
| 30 | 0.95 | 15 | 5207 | 9259 | 0.0886 | -0.4260 | 0.894 | 0.447 | -0.0015 | 0.0901 | -0.0480 | 0.1366 | -0.0704 | 0.1590 | N | N | Y | N | Y | N |
| 30 | 0.95 | 30 | 5207 | 9259 | -0.0101 | -0.3913 | -0.366 | 0.451 | 0.0011 | -0.0111 | -0.0467 | 0.0367 | -0.0125 | 0.0025 | N | N | N | N | N | N |
| 30 | 0.95 | 60 | 5207 | 9259 | -0.0679 | -0.3599 | -2.093 | 0.450 | 0.0099 | -0.0777 | -0.0322 | -0.0357 | 0.0399 | -0.1078 | N | N | N | N | N | Y |
| 30 | 0.95 | 120 | 5207 | 9259 | -0.1311 | -0.3125 | -5.199 | 0.454 | 0.0155 | -0.1466 | -0.0245 | -0.1066 | 0.0218 | -0.1529 | N | Y | N | Y | N | Y |
| 30 | 0.95 | 240 | 5207 | 9259 | -0.1110 | -0.2940 | -8.210 | 0.452 | 0.0179 | -0.1290 | -0.0136 | -0.0974 | 0.0314 | -0.1424 | N | Y | N | Y | N | Y |
| 30 | 0.98 | 15 | 2317 | 3840 | 0.0883 | -0.4323 | 1.011 | 0.451 | 0.0084 | 0.0799 | -0.0480 | 0.1363 | -0.0913 | 0.1796 | N | N | Y | N | Y | N |
| 30 | 0.98 | 30 | 2317 | 3840 | 0.0707 | -0.3761 | 1.938 | 0.462 | 0.0095 | 0.0612 | -0.0467 | 0.1174 | -0.0052 | 0.0759 | N | N | Y | N | Y | N |
| 30 | 0.98 | 60 | 2317 | 3840 | -0.0436 | -0.3713 | -2.149 | 0.457 | 0.0111 | -0.0546 | -0.0322 | -0.0114 | 0.1815 | -0.2251 | N | N | N | N | N | Y |
| 30 | 0.98 | 120 | 2317 | 3840 | -0.1496 | -0.2682 | -5.259 | 0.462 | 0.0179 | -0.1675 | -0.0245 | -0.1251 | 0.0922 | -0.2418 | N | Y | N | Y | N | Y |
| 30 | 0.98 | 240 | 2317 | 3840 | -0.1052 | -0.2037 | -5.668 | 0.468 | 0.0266 | -0.1318 | -0.0136 | -0.0916 | 0.0891 | -0.1943 | N | Y | N | Y | N | Y |
| 60 | 0.90 | 15 | 7860 | 17987 | 0.0580 | -0.4051 | 0.498 | 0.441 | 0.0050 | 0.0530 | 0.0094 | 0.0487 | -0.1011 | 0.1591 | N | N | N | N | Y | N |
| 60 | 0.90 | 30 | 7860 | 17987 | 0.0454 | -0.3749 | 0.596 | 0.442 | 0.0096 | 0.0358 | -0.0020 | 0.0473 | -0.0489 | 0.0943 | N | N | N | N | Y | N |
| 60 | 0.90 | 60 | 7860 | 17987 | 0.0012 | -0.2820 | -0.175 | 0.454 | 0.0132 | -0.0120 | -0.0006 | 0.0018 | 0.0249 | -0.0238 | N | N | N | N | N | N |
| 60 | 0.90 | 120 | 7860 | 17987 | -0.0039 | -0.2226 | -1.146 | 0.462 | 0.0187 | -0.0225 | 0.0173 | -0.0211 | 0.0335 | -0.0374 | N | N | N | N | N | N |
| 60 | 0.90 | 240 | 7860 | 17987 | -0.0016 | -0.1967 | -2.132 | 0.463 | 0.0244 | -0.0260 | 0.0260 | -0.0276 | 0.0519 | -0.0535 | N | N | N | N | N | Y |
| 60 | 0.95 | 15 | 4087 | 9191 | 0.1290 | -0.4009 | 1.080 | 0.450 | 0.0067 | 0.1224 | 0.0094 | 0.1197 | -0.1070 | 0.2360 | Y | N | Y | N | Y | N |
| 60 | 0.95 | 30 | 4087 | 9191 | -0.0078 | -0.3925 | 0.361 | 0.448 | 0.0132 | -0.0211 | -0.0020 | -0.0058 | -0.0494 | 0.0415 | N | N | N | N | N | N |
| 60 | 0.95 | 60 | 4087 | 9191 | -0.0556 | -0.3201 | -0.894 | 0.455 | 0.0162 | -0.0718 | -0.0006 | -0.0550 | 0.0552 | -0.1108 | N | N | N | Y | N | Y |
| 60 | 0.95 | 120 | 4087 | 9191 | -0.0138 | -0.2485 | -1.704 | 0.462 | 0.0183 | -0.0321 | 0.0173 | -0.0311 | 0.0485 | -0.0623 | N | N | N | N | N | Y |
| 60 | 0.95 | 240 | 4087 | 9191 | 0.0100 | -0.1989 | -2.315 | 0.467 | 0.0279 | -0.0179 | 0.0260 | -0.0160 | 0.0821 | -0.0721 | N | N | N | N | N | Y |
| 60 | 0.98 | 15 | 1771 | 3874 | -0.1774 | -0.4637 | -1.256 | 0.451 | 0.0185 | -0.1960 | 0.0094 | -0.1868 | -0.1520 | -0.0254 | N | Y | N | Y | N | N |
| 60 | 0.98 | 30 | 1771 | 3874 | -0.0507 | -0.4402 | 1.979 | 0.459 | 0.0216 | -0.0723 | -0.0020 | -0.0487 | -0.1699 | 0.1192 | N | N | N | N | Y | N |
| 60 | 0.98 | 60 | 1771 | 3874 | -0.1388 | -0.3682 | -3.181 | 0.455 | 0.0167 | -0.1555 | -0.0006 | -0.1382 | -0.0551 | -0.0838 | N | Y | N | Y | N | Y |
| 60 | 0.98 | 120 | 1771 | 3874 | -0.0642 | -0.2123 | -2.526 | 0.472 | 0.0237 | -0.0879 | 0.0173 | -0.0815 | -0.0029 | -0.0613 | N | N | N | Y | N | Y |
| 60 | 0.98 | 240 | 1771 | 3874 | -0.0599 | -0.1967 | -5.421 | 0.470 | 0.0385 | -0.0984 | 0.0260 | -0.0859 | 0.0854 | -0.1453 | N | N | N | Y | N | Y |

## MPIE

Does a broad neighborhood meet 0.10 vs matched random? **NO**.

- Continuation MPIE: **3 / 45** isolated cells.
- Exhaustion MPIE: **11 / 45**, mostly H=120/240, not coherent across q or W.
- `|dMat| ≥ 0.10` in 14/45; the other 31 miss the floor.
- q neighborhood fails: at `W=60 H=15`, q=0.95 is continuation MPIE (`dMat=+0.122`) while q=0.98 is exhaustion MPIE (`dMat=−0.196`).

## Matched random

Seed `20260831`, 100 replicates, without replacement, month and UP/DOWN composition preserved. Pool excludes raw extreme timestamps for that (W,q) only.

- Matched mean `NORM_CONT_RET_H` sits near **0** (about −0.002 to +0.039; across-cell mean ≈ **+0.011**).
- Matched `P(CONT>0)` ≈ **0.498–0.501**.
- Extreme-minus-matched therefore almost equals the extreme mean itself.
- Residual TVD on the last replicate is large (dow ≈ 0.83, dom ≈ 0.97). That diagnostic compares last-draw categorical keys against candidates; it is descriptive only and does not create an alternative baseline. The matched **means and positive-shares** behave like a functioning random control (near 0 / 0.50).

## Structural control

Moderate band `0.60 ≤ P_W < 0.80`, same W, same refractory, same future-outcome semantics. `CONTROL_DELTA_MIN=0.05`.

- Moderate means cluster near **0** (about −0.048 to +0.026; across-cell mean ≈ **−0.012**).
- Extreme minus moderate is **not** a stable ≥0.05 same-sign neighborhood.
- Structural continuation True in 8/45; exhaustion True in 17/45.
- Extreme is not systematically more continuative or more exhaustive than moderate momentum. The simplest structural alternative is not beaten on a coherent surface.

## +6h negative control

Same-UTC-day circular +6h shift, original direction preserved, collisions with raw extremes reported not removed. `CONTROL_DELTA_MIN=0.05`.

- Shifted means mixed (about −0.17 to +0.18; across-cell mean ≈ **+0.009**).
- Collision fraction ≈ **0.05–0.17** (higher at q90, lower at q98), as disclosed.
- Gate True in 12/45 continuation and 25/45 exhaustion. Timing often differs from the extreme timestamp, but that does not salvage a mixed primary.

## Parameter robustness

**q neighborhood:** **NO.** q90/q95/q98 do not form a coherent same-sign family. The most extreme tail is not monotonically stronger in one sign; W=60 H=15 reverses from q95 continuation to q98 exhaustion.

**W neighborhood:** **NO.** W=15/30/60 do not agree on a selected sign. W=30 is more often negative; W=15 q98 short-H is the continuation outlier.

**Adjacent H:** **NO** as a freeze neighborhood. Isolated W=15 q=0.98 H=15 and H=30 share continuation MPIE, then H=60 collapses and H=120/240 flip to exhaustion MPIE. Horizon sign-flip is the opposite of adjacent-horizon coherence.

## Chronological stability

Year-wise mean `NORM_CONT_RET_H` is **not** 4/5-year stable for either sign across the surface.

Representative pattern (not a selected candidate):

- **2020:** often negative, especially W=30 and W=60 q≥0.95.
- **2021:** mixed; short-H q98 W=15 positive, many other cells negative.
- **2022:** more often positive at short H (a continuation-looking year in several W×q).
- **2023:** frequently the most negative year (W=15 q=0.98 all five H negative; W=30 q=0.90 all five H negative).
- **2024:** mixed-to-positive at short H for several configs; not a 4/5-year continuation claim and not a 4/5-year exhaustion claim.

No shock-year was excluded.

## Direction symmetry

H03 is a symmetric claim: continuation requires both UP and DOWN continuation overall; exhaustion requires both UP and DOWN exhaustion overall.

- Both sides mean>0: **6 / 45** cells.
- Both sides mean<0: **5 / 45** cells.
- Mixed sides: **34 / 45** cells.
- DOWN mean is more negative than UP in **39 / 45** cells.
- DOWN `P(CONT>0) < 0.5` in **45 / 45**; UP in **38 / 45**.

Symmetric mechanism supported: **NO**.

A DOWN-only exhaustion reading is `POSTHOC_UNTESTED` and cannot enter Batch 01 validation.

## Concentration

| W | q | largest month | largest share | top-5 share | median spacing (min) | unique days | unique weeks | unique months |
|---|---|---|---|---|---|---|---|---|
| 15 | 0.90 | 2020-11 | 0.0274 | 0.1300 | 120.0 | 1710 | 258 | 59 |
| 15 | 0.95 | 2021-05 | 0.0299 | 0.1396 | 180.0 | 1524 | 258 | 59 |
| 15 | 0.98 | 2021-05 | 0.0335 | 0.1448 | 360.0 | 1152 | 255 | 59 |
| 30 | 0.90 | 2021-05 | 0.0274 | 0.1323 | 120.0 | 1677 | 258 | 59 |
| 30 | 0.95 | 2021-05 | 0.0313 | 0.1408 | 195.0 | 1469 | 258 | 59 |
| 30 | 0.98 | 2021-05 | 0.0319 | 0.1502 | 405.0 | 1012 | 254 | 59 |
| 60 | 0.90 | 2020-03 | 0.0282 | 0.1341 | 135.0 | 1610 | 258 | 59 |
| 60 | 0.95 | 2020-03 | 0.0328 | 0.1500 | 225.0 | 1303 | 256 | 59 |
| 60 | 0.98 | 2021-05 | 0.0344 | 0.1592 | 442.5 | 819 | 247 | 59 |

Largest-month share **2.7–3.4%**; top-5 **13–16%**. No single month dominates. Typical top months: 2021-05, 2020-03, 2020-11, 2021-01, 2023-01.

## Dependence

Week-block bootstrap (seed `20260901`, 2000 replicates, 1w/2w/4w sensitivity): **NOT EMITTED** by the frozen runner's `evaluate_cell`. `N_BOOT` / `SEED_BOOT` exist in the library but were not wired into cell output. Per freeze rules this was **not added after outcomes**. **NOT REQUIRED** because there is no candidate-for-freeze.

Long-dependence diagnostic (candidate/outcome-independent daily total |15m log-return| ACF):

| lag (days) | ACF |
|---|---|
| 1 | 0.727 |
| 2 | 0.562 |
| 4 | 0.509 |
| 8 | 0.400 |
| 16 | 0.270 |
| 32 | 0.235 |
| 64 | 0.192 |

`L_dep = 32 days` (largest lag with `|ACF| ≥ 0.20`; lag 64 is 0.192, just below threshold). Effective N is not iid; 1w/2w/4w bootstrap would need caution even if a candidate had existed. `n_eff_h` = 2880/1440/720/360/180 for H=15/30/60/120/240 (30d×96 / H-bars).

## Normalization diagnostics

Denominator = trailing 30d median `|RET_H|`, no floor. Finite and strictly positive on reported events.

- min ≈ **4.7e-4 to 1.6e-3** (grows with H, as expected).
- p50 ≈ **1.3e-3 to 4.9e-3**.
- top-1% share of total `|NORM_CONT_RET_H|` magnitude: **0.086–0.119**.

Pathology (zero/nonfinite denominator, or top-1% swallowing the mean): **NO**. Right-tail pull of some means vs negative medians is a distributional fact, not a denominator bug.

Reference-overlap disclosure (prereg §7): `n_eff_w=2880`; at q=0.90 tail proxy ≈ 288 overlapping 15m steps, moderate-band proxy 576, decile proxy 288. Raw N is not an iid count.

## Decile diagnostics

Fixed midrank `P_W` deciles, diagnostic only — no new threshold may be selected.

Across W×H, upper-decile bins (`[90,100]`, which contain the H03 candidates before refractory) have `P(CONT>0)` about **0.44–0.47** and means near 0 or slightly negative at H≥30. Lower deciles are not a monotone continuation ladder. The top decile is not a distinct continuation engine. These bins cannot promote H03.

## Secondary MFE/MAE

The frozen runner computed path MFE (impulse direction) and MAE (opposite) inside `outcome_bundle` and normalized them by the same pre-T scale. **Cell-level MFE/MAE summaries were not persisted** in the result JSON. No second run was performed to harvest them after outcomes were seen.

Secondary path metrics **cannot rescue** a failed primary close-return and cannot satisfy the adjacent-horizon coherence gate (mechanically nested). Primary itself fails.

## Post-hoc observations

Each of the following is **`POSTHOC_UNTESTED`**. None may rescue H03, redefine the sign, or enter Batch 01 validation.

- `POSTHOC_UNTESTED:` isolated continuation MPIE at `W=15 q=0.98 H=15/30` and `W=60 q=0.95 H=15`; not a q/W neighborhood.
- `POSTHOC_UNTESTED:` longer-H (120–240m) cells more often negative vs matched-random; horizon sign flip vs short-H means.
- `POSTHOC_UNTESTED:` DOWN mean_norm more negative than UP in 39/45 cells; one-sided DOWN exhaustion cannot promote H03.
- `POSTHOC_UNTESTED:` 2023 often the most negative year; no shock-year exclusion authorized.
- `POSTHOC_UNTESTED:` all 45 medians negative and all 45 `P(CONT_RET_H>0)<0.5` while some means are positive (right-tail pull); median/count exhaustion is not a new authorized claim.

## Candidate-for-freeze criteria (all required)

| # | Criterion | Result |
|---|---|---|
| 1 | primary close-return has a selected sign | **no stable selected sign** (mixed means; all medians negative; all p>0 < 0.5) |
| 2 | MPIE 0.10 vs matched random in a broad neighborhood | **NO** (3 continuation + 11 exhaustion isolated cells) |
| 3 | separates from moderate momentum by 0.05 | partial, not a neighborhood |
| 4 | +6h weakens by 0.05 | partial, not a neighborhood |
| 5 | q90/q95/q98 same-sign neighborhood | **NO** (q95 vs q98 sign flip at W=60 H=15) |
| 6 | two adjacent horizons same sign on primary | partial isolated only; H sign-flips |
| 7 | sign in ≥4/5 development years | **NO** |
| 8 | UP and DOWN both support the same claim | **NO** (34/45 mixed sides) |
| 9 | no single month/regime dominates | yes (largest month 2.7–3.4%) |
| 10 | dependence-aware bootstrap compatible | **NOT REQUIRED** (no candidate; intervals not emitted by frozen runner) |
| 11 | L_dep caution disclosed | `L_dep=32 days`; ACF64=0.192 |
| 12 | primary outcome itself supports the mechanism | **NO** |

`H03_CONTINUATION_CANDIDATE_FOR_FREEZE` is not met.
`H03_EXHAUSTION_CANDIDATE_FOR_FREEZE` is not met.

This is not `H03_INCONCLUSIVE`: the symmetric specific claim was tested on the full 45-cell surface and failed its neighborhood, symmetry, year-stability, and MPIE-breadth requirements cleanly. Isolated cells and one-sided patterns are post-hoc.

## Development verdict

**`H03_REJECTED_SPECIFIC_CLAIM`** — extreme short-horizon impulse, as preregistered (two-sided continuation vs exhaustion, 45 cells, MPIE 0.10, moderate and +6h controls, q/W/H neighborhood, 4/5 years, UP/DOWN symmetry), did not earn further complexity.

Do not add volume/taker/trend/news gates. Do not reframe isolated q98-W15 short-H continuation or DOWN-only longer-H exhaustion as a new authorized hypothesis in this task.

Do not inspect 2025. Do not inspect 2026. Do not start R3. Do not start H04. Do not modify forecasting/product architecture.
