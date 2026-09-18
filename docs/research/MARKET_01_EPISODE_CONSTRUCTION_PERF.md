# MARKET-01 episode-construction throughput

**Status:** RESEARCH INFRASTRUCTURE / NOT SCIENTIFIC EVIDENCE  
**Date:** 2026-09-18

Post-close investigation of why canonical MARKET-01 spent an unexpectedly
long time in `construct_episodes`. This document is not a RESULT, not a
rerun, and not a change to frozen MARKET-01 thresholds, estimand, or
classification.

Canonical MARKET-01 remains closed: `FINAL_CLASSIFICATION = NO_EVIDENCE`,
RESULT SHA256 `5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`.
Do not rerun it. Protected OOS was not opened.

## Measured diagnosis (synthetic, non-outcome-bearing)

Workload: contiguous 1m GBM-like price + native 5m OI,
`SYNTHETIC_SNAPSHOT`, `n_days_hist=30`, `n_days_eval=2`, `seed=1`
(`scripts/research/market_01_episode_construction_perf_bench.py`).
Does not load CORE/OI snapshots and does not consume the reservation.

cProfile of frozen `construct_episodes` (instrumented 28.065s; uninstrumented
wall 9.235s):

| Hotspot | calls | cumtime s | Role |
|---|---:|---:|---|
| `b2_03.pre_vol_60` / `_close_ending_at` via `_pre_vol_series` | 138,256 / 8,432,836 | 15.75 / 8.76 | PRE_VOL_60 at every 5m tau in the 30d window, for each occupying episode |
| `close_at` / `_impulse_return` / `_abs_impulse_series` | 4,648,890 / 2,322,686 / 269 | 6.13 / 9.86 / 10.98 | rolling 30d \|impulse\| percentile on every non-overlap-skipped t |
| `legal_oi_at` / `_delta_oi_at` | 276,512 / 138,240 | 0.83 / 1.08 | PIT OI + 30d ΔOI percentile after occupancy |
| `midrank_percentile` | 301 | 0.01 | not a bottleneck |
| `construct_episodes` itself | 1 | 28.07 | occupancy loop / `EpisodeRecord` allocation is cheap |

Complexity of the frozen path is O(T × W) with W = 8640 five-minute
steps in 30d history: each qualifying-impulse attempt rebuilds the
historical `|log-return|` series by calling `close_at` twice per tau;
each occupying episode then rebuilds PRE_VOL_60 the same way (60
`_close_ending_at` calls per tau). Repeated `np.asarray` inside
`legal_oi_at` is visible but secondary.

Not material on this workload: overlap occupancy, `EpisodeRecord`
storage, bootstrap/OLS (not in this path).

Canonical scale implication: ~7.7k occupying episodes × ~8.6k PRE_VOL
lookups, plus impulse scans on every non-skipped 5m t, matches the
observed multi-hour canonical construction time.

## Semantics-preserving fix

New module `scripts/research/market_01_episode_construction_fast.py`.
Frozen `market_01_oi_expansion_weak_continuation_lib.py` is unchanged
(lifecycle SHA256 `9a8f46b3…`). Fast construction:

- precomputes 5m close, signed/abs 30m impulse, PIT OI, ΔOI;
- precomputes 1m `math.log` returns and PRE_VOL_60 on the 5m clock
  with the same 60-term `math.sqrt` accumulation as `b2_03.pre_vol_60`;
- batched `searchsorted` PIT OI (staleness ≤ 300000 ms, no per-call
  `np.asarray`);
- same occupancy/eligibility loop and `EpisodeRecord` fields;
- falls back to frozen `construct_episodes` if 1m price is not a
  contiguous `bar_end_exclusive` grid.

Not changed: windows, percentile definition, PIT/overlap/support rules,
OLS, bootstrap, classification.

## Same-workload before/after

Same synthetic as the profile, uninstrumented wall:

| path | seconds | episodes |
|---|---:|---|
| frozen `construct_episodes` | 9.235 | 607 (16 occupying, 15 eligible) |
| `construct_episodes_fast` | 0.069 | 607 (16 occupying, 15 eligible) |

Speedup ≈ 135×. Episode scientific fields: exact equality.

## Remaining throughput notes

At multi-year CORE length the remaining cost is ordinary O(N) Python
precompute (1m log returns, 5m PRE_VOL 60-term sums) plus per-t
`EpisodeRecord` construction and O(W) midrank on occupying episodes.
That is no longer the O(T × W) close-lookup scan. Fast construction is
not wired into the frozen MARKET-01 evaluator; later hypotheses should
call `construct_episodes_fast` (or an equivalent precompute) rather
than the frozen O(T × W) loop.
