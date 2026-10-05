# Beta C1 — same-day-type reference (product change V1)

**Status:** `MAPPING_COMMITTED_BEFORE_CODE / IMPLEMENTATION_ON_BRANCH / NOT_MERGED / NOT_DEPLOYED`
**Decision:** owner GO 2026-10-05, `CHANGE_BASELINE -> C1` from `WEEKDAY_WEEKEND_BASELINE_UNIT_V2_RESULT.md`.
**Frozen evaluator (the reference implementation):** `scripts/product/weekday_weekend_baseline_v2/evaluate.py` (`86b2c09`, sha256 `5bda5d60e9b55812…`). C1 is implemented exactly as evaluated. It is not re-optimized or re-defined.

## 1. Exact mapping evaluator → production

| Evaluator (§9.2–9.3 of the unit) | Production |
|---|---|
| Day type: WEEKEND iff the **UTC date of the window start** is Saturday or Sunday (`is_weekend_day(start_day(j, n))`) | `beta/day_type.py::window_day_type(end_bucket, n)`: the window start is `end_bucket − (n − 1)·5m`, then its UTC date's `weekday() >= 5`. No Kyiv time, no DST handling (UTC has none) |
| Evaluated window: `n` buckets ending at bucket `j` (`n = 12` for 1h, `48` for 4h) | `context_1h(..., horizon)` at `bucket_ts`, unchanged |
| Reference: samples at buckets `b ∈ [t − 30d, t)` of the **same** day type as the evaluated window; a sample's type is its own window start's date | `context_1h`: the same `[bucket_ts − 30d, bucket_ts)` sample set, filtered by `window_day_type(b, n) == window_day_type(bucket_ts, n)` **for the three evaluated metrics only** |
| Rank: mid-rank `(less + 0.5·equal) / N` over the reference | `compute_percentile_snapshot` on the filtered samples (the same mid-rank; parity-tested) |
| Usable iff C0 is usable (the production tier over the **unfiltered** 30-day samples is `mature`) **and** ≥ 8 distinct same-type window-start dates | tier = the unfiltered (C0) tier when that is not `mature`; tier `day_type_building` when it is mature but fewer than 8 same-type dates have a present sample; otherwise `mature` |
| Metrics: range, move (signed), volume | `range_width_pct_median`, `price_move_pct_median`, `volume_notional_usd_sum`. **Taker delta and OI change keep the pooled C0 reference**: the unit did not evaluate them |
| TOD, 1h windows, range and volume: days `d = 1..30` whose day type (the date of `W − d days − 1h`) = `T`; the daily median of the ±30-minute samples; the median of the daily medians; usable iff ≥ 8 such days | `beta/horizons.py::_baseline_tod(..., n=12)`: range and volume medians use the same-type days with ≥ 8; **the price-move median and the 4h and 24h baselines are unchanged** (not evaluated) |

**Missing data.** The evaluator ran on a gapless panel, so it defines no gap behaviour. Production keeps C0's existing gap semantics unchanged:
- a sample whose window has a missing bucket is absent;
- the current window with a missing bucket is `None`;
- a same-type date counts when at least one of its samples is present.

**No fallback.** When C1 is not usable, the rank is **not** replaced by the pooled C0 rank. The metric is `day_type_building` (not mature), and every consumer already treats a non-mature tier as unavailable:
- the gate: `IMMATURE`;
- interpretation: «мало истории»;
- labels: none;
- TOD: no median, so no ratio.

## 2. Second computation site of the same labels: «что было после похожих»

`beta/analogues.py` labels Binance history with the same `interpret()` over the same 1h / 4h ranks, and the live label is looked up in that history. If live labels used C1 while the history used C0, a live label would be matched to a cohort defined differently. So the history labels use the same C1 rule for the same three metrics:
- same-type samples among the previous 30 days;
- ≥ 8 same-type dates;
- the existing ≥ 80 % window-coverage rule kept as the C0 maturity.

Taker, OI and the volatility tercile stay pooled. `ANALOGUES_VERSION` becomes `BETA_ANALOGUES_V2`. `lookup()` returns no card when the stored stats carry another analogues version, so a live C1 label is never matched to C0 history. Cards return after the next `--beta-history-build`.

**Not changed (not evaluated by the unit):**
- research live states (`beta/research_states.py`, frozen research definitions);
- Stage-2 tape percentiles;
- the 24h and 4h TOD baselines;
- corridors, levels, `/risk` and the volatility tercile;
- the push policy, caps, cooldowns, quiet hours and notifier.

## 3. Versions and migration

| Identity | Before | After |
|---|---|---|
| context | `BETA_CONTEXT_1H_V2` (`68ec9dbd…`) | `BETA_CONTEXT_1H_V3`: payload V2 + `reference: SAME_UTC_DAY_TYPE`, the metric list, `min_same_type_dates: 8`, `fallback: NONE`. V2's payload is frozen as a legacy payload, so its digest stays verifiable |
| horizons | `BETA_HORIZON_TOD_V2` (`f64700b7…`) | `BETA_HORIZON_TOD_V3`: definition + `baseline_1h_day_type` |
| analogues | `BETA_ANALOGUES_V1` | `BETA_ANALOGUES_V2` |
| rules / episodization / tape schema | unchanged | unchanged |

**Episode state.**
- **Predecessor.** V3 declares V2 as its predecessor (`CONTEXT_PREDECESSORS`).
- **What carries over.** On the first V3 bucket the detector adopts **only the episode memory**: open episodes, last ended per type, the as-of bucket and the last input. Episodes are stepped from the detector's rule evaluations (`step_context`), which do not read context ranks, so their meaning does not change.
- **What is cleared.** The context readings (1h / 4h ranks and labels) are cleared by `adopt_predecessor_state` and recomputed under V3.
- **What is not reinterpreted.** No V2 reading is reinterpreted as V3. Push decisions already recorded keep their V2 context, and new decisions use V3.

## 4. Rollout and rollback (summary; procedures in the PR)

- **Monitoring.** Live calibration is reported separately for weekday and weekend against nominal rates and the unit's historical expectation. The condition "≥ 12 weekend days and C1 worse than C0 by > 2 pp" is a **`REVIEW_TRIGGER`**, not an automatic rollback.
- **Automatic rollback** only for an engineering failure or invalid state (version error, exceptions, a stalled detector).
- **Rollback** = redeploy the previous commit (context V2). The V2 snapshot chain resumes from its last V2 state, within the detector's 30-day gap rule.
- **C0 is reconstructible offline** from the persisted tape for any head-to-head (`--beta-c1-replay` computes C0 and C1 side by side). No new telemetry.
