# H02 Failed Breakout → Mean Reversion — Development Results

**Status:** FROZEN_EVIDENCE / EXPLORATORY
**Hypothesis ID:** `H02_FAILED_BREAKOUT_MEAN_REVERSION`
**Development verdict:** `H02_KILL`
**Machine-readable:** `docs/research/H02_DEV_RESULTS.json`
**Preregistration:** `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md`

This document records the development-only outcome inspection. It is not a confirmatory result, not a trading strategy, not a liquidity-sweep claim, and not authorization to open 2025 validation or 2026 OOS.

## Identity

| Field | Value |
|---|---|
| dataset | `CORE_BTC_BINANCE_V0` |
| snapshot_id | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| prereg commit | `92d130f0e26aa993e8e0a231eceb95db20ff47f0` |
| research code SHA at outcome run | `92d130f0e26aa993e8e0a231eceb95db20ff47f0` |
| development window | 2020-02-01T00:00:00Z → 2025-01-01T00:00:00Z |
| t_max_inclusive | 2024-12-31T19:55:00Z |
| 2025 validation inspected | NO |
| 2026 OOS inspected | NO |

H01 remains `H01_KILL` and is not reinterpreted here.

## Search surface

3 lookbacks (60/120/240m) × 3 overshoot thresholds (s=0.00/0.05/0.10) × 5 horizons (15/30/60/120/240m) = **45 primary cells**.

## Sample

UTC 5m grid; 30m either-side refractory; N identical across H because `T+240m < 2025-01-01` is applied to every event.

| L | s | raw pre-dedup | post-refractory N | UPPER share |
|---|---|---|---|---|
| 60 | 0.00 | 65195 | 38426 | 0.501 |
| 60 | 0.05 | 39127 | 28201 | — |
| 60 | 0.10 | 23084 | 18872 | 0.464 |
| 120 | 0.00 | 41923 | 26326 | 0.505 |
| 240 | 0.00 | 26411 | 16985 | 0.508 |
| 240 | 0.10 | 5307 | 4834 | — |

By year (L=60, s=0.00): 2020=7039, 2021=7960, 2022=7793, 2023=7456, 2024=8178.

## Primary result

Without cherry-picking:

- Short horizons (15–30m) at **s=0.00** show a small positive mean `NORM_REV_RET` (~0.03–0.06) versus matched-random near 0. `P(REV>0)` is only **0.52–0.57**. Mean raw reversion is about **0.7–1.4 bps**.
- The same cells fade toward 0 or negative by 120–240m.
- Stronger overshoot is **not** better: s=0.10 is weaker or negative versus s=0.00 on most L×H.
- Median `NORM_REV_RET` can look more positive than the mean because tails are wide (p05 ~ −3.5, p95 ~ +3.3 at L=60 s=0 H=15).

This is not a broad, strength-monotonic failed-breakout reversion surface.

## Structural control

Successful breakouts, given the **same** hypothetical reversion sign, have **higher** mean `NORM_REV_RET` than failed breakouts in 44/45 cells (typical failed-minus-success **−0.07 to −0.15**). Closing back inside the range is not incremental information beyond breaching the boundary. If anything, closes that finish outside revert more on this sign convention.

That contrast is the preregistered test of the failed-breakout mechanism. It fails.

## Matched random and time shift

True s=0 short-horizon timing beats matched-random (several week-block CIs exclude 0, e.g. L=60 s=0 H=15: +0.041, CI 0.013–0.067). +6h same-day shifts sit near 0 or slightly negative and therefore weaken that short-horizon bump.

Those controls say *some* boundary-timing information exists at 15–30m. They do not rescue the failed-close definition after the successful-breakout control.

## Parameter robustness

**NO.** Desired shape was a plateau or stronger-overshoot-non-worse response. Observed: s=0.00 is the least-bad cell family; s=0.05/0.10 degrade. L=60/120/240 agree on that inversion. One isolated L=240 s=0.10 H=15 winner (mean 0.104) sits next to negative H=60/120/240 cells.

## Chronological stability (L=60 s=0 H=15 candidate-minus-matched)

2020: +0.101
2021: +0.051
2022: +0.024
2023: +0.013
2024: +0.023

All five years positive in that one short-horizon s=0 slice. Longer horizons and higher s reverse in 2021/2023 often. Year stability of a 15m s=0 bump is not enough for candidate status.

## Side stability

LOWER failed-breaks carry more of the positive short-horizon mean. UPPER is smaller and is near zero/negative at L=240 s=0 H=15 (UPPER −0.006 vs LOWER +0.121). H02 is not redefined as lower-only.

## Concentration

largest month share: **~1.9–2.1%**
top-5 month share: **~9–10%**
median spacing after refractory: **55–200 minutes** depending on L×s
clustering: refractory collapsed raw counts by ~30–40% (e.g. 65195 → 38426 at L=60 s=0)

## Secondary path

Mean normalized MAE exceeds MFE. `P(MFE>MAE)` is ~0.50–0.52. Path metrics do not rescue close-return.

## Candidate-for-R3 criteria (all required)

| # | Criterion | Result |
|---|---|---|
| 1 | beats matched random in a broad neighborhood | partial: s=0, 15–30m only |
| 2 | beats/separates from successful-breakout | **no; successful is stronger** |
| 3 | +6h weakens | yes for the short-H bump |
| 4 | neighboring s plateau/strength-response | **no; inverted** |
| 5 | two adjacent horizons | partial: 15 and 30 at s=0 |
| 6 | 4 of 5 years positive | yes for s=0 H=15; not the full neighborhood |
| 7 | UPPER and LOWER expected sign | partial; UPPER weak/negative at L=240 |
| 8 | no dominant month | yes |
| 9 | bootstrap compatible with positive | partial; 10/45 CIs entirely positive |
| 10 | primary close-return supports the mechanism | **no** (~1 bp; structural control fails) |

`H02_CANDIDATE_FOR_R3` is not met.

## Development verdict

**H02_KILL** — failed-breakout mean reversion did not earn further complexity.

Do not add volume/taker/trend gates. Do not reframe the short-horizon boundary bounce as a new authorized hypothesis in this task.

Do not inspect 2025. Do not inspect 2026. Do not start R3. Do not modify forecasting/product architecture.
