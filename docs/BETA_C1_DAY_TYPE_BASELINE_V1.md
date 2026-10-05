# Beta C1 — same-day-type reference (product change V1)

**Status:** `IMPLEMENTED_ON_BRANCH claude/product-weekday-weekend-c1 / PARITY_TESTED / NOT_MERGED / NOT_DEPLOYED` (the mapping in §1–§3 was committed before the code, `d4b2e5b`)
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

## 5. Validation done on the branch

- **Parity with the frozen evaluator** (`tests/beta/test_beta_c1_day_type.py`, 22 tests):
  - 1h ranks for a weekday, Saturday, Sunday, both edges (`[Fri 23:00, Sat 00:00)` is a weekday window, `[Sun 23:00, Mon 00:00)` a weekend one) and the year boundary;
  - 4h ranks;
  - gate flags and interpretation bands derived from those ranks;
  - the 1h TOD baseline;
  - the analogue history ranks;
  - the maturity boundary (the first window with a sample at `t − 30d`; the first weekend window, which has 9 weekend dates);
  - no lookahead.

  Production and evaluator ranks were **identical** on all 33 compared ranks (max |diff| = 0). The tests tolerate one reference sample (1/N), in case a numpy-vs-Python-float tie ever flips.
- **Missing buckets:**
  - a reference sample whose window has a gap is absent, and the rank equals the evaluator's mid-rank over the remaining same-type samples;
  - a whole missing weekend leaves 7 dates, so `day_type_building`: the gate is `IMMATURE` and there is no pooled fallback, although the pooled V2 rank on the same tape is mature;
  - a gap in the current window gives no reading;
  - the TOD has fewer than 8 same-type days, so no median.
- **Migration:**
  - V2 → V3 adopts the episode memory and carries no V2 reading, checked in both the pure and the PostgreSQL detector paths;
  - V0 and V1 are not adopted by V3;
  - V2's digest is unchanged.
- **Suites:** `tests/beta`, `tests/beta_user_sim` and `tests/product` pass with a local PostgreSQL. The one exception is `test_research_feeds_role_pg::test_the_install_script_applies_the_grants…`, which fails identically on `main` because its install script needs the server on the default port; it is environmental.

## 6. Expected behaviour change (from the unit, Binance 2020–2024)

| | Weekday | Weekend |
|---|---|---|
| Hours qualifying as unusual (gate) | 7.1 % → 5.9 % | 2.4 % → 5.9 % |
| Range / volume / price flag rates | 6.8 / 6.8 / 12.7 % → 5.7 / 5.5 / 10.8 % | 2.5 / 2.0 / 5.7 % → 5.6 / 5.6 / 10.7 % |
| 1h labels that change | ≈ 15 % of hours | ≈ 34 % of hours |
| «сжатие» range band (rank ≤ 0.20) | 14 % → 21 % | 37 % → 21 % |
| 1h "above usual" (TOD) range / volume | 56 % / 59 % → 49 % / 50 % | 32 % / 29 % → 48 % / 50 % |

**Notification volume.**
- **Gate-qualified hours per week:**
  - C0: 120 × 7.13 % + 48 × 2.39 % ≈ **9.7**;
  - C1: 120 × 5.91 % + 48 × 5.85 % ≈ **9.9**, i.e. **+2 %**.
- **The shift is between days, not upward.** About **+0.8 qualified hours per weekend day** (0.57 → 1.40), and about **−0.3 per weekday** (1.71 → 1.42).
- **Push budget unchanged.** A push additionally needs a TRIGGERED detector episode and passes the unchanged policy (cooldowns, quiet hours, the daily cap of 2 per UTC day), so the weekly push ceiling is unchanged. Weekend pushes rise and weekday pushes fall by similar amounts.
- **Briefing and `/catchup`** «Необычные часы» lists stay capped at 3.
- **Other alerts:** market alerts (levels, sharp moves) do not read these ranks and are unchanged.

## 7. Offline replay of the recorded beta history (needs the VPS)

The recorded beta tape and push decisions live in the production database, which this development environment cannot reach, so the replay is the owner's step. It is read-only and can run **before** any deploy, from a separate checkout of this branch with the deployment `.env`:

```bash
cd /opt/signalbot-c1-check   # a separate checkout of claude/product-weekday-weekend-c1; never the running tree
.venv/bin/python main.py --beta-c1-replay --dry-run-days 7 --dry-run-stride 12 --beta-json > /tmp/c1_replay.json
```

What the report shows (`c1_replay`):
- `by_day_type.{WEEKDAY,WEEKEND}`:
  - `btc_state_changed` (any /btc label, level label or gate status differs) and `changed:*` per field;
  - `C0:/C1:gate_qualified`;
  - `C0:/C1:compression_1h|4h`;
  - `C0:/C1:flag_*` against `mature_1h`, beside `nominal_flag_rates` and `historical_expectation_unit_v2`;
  - `tod_*:status_changed`.
- `push_decisions`: per recorded decision, whether the gate would have flipped. Key fields: `recorded_push_that_C1_would_suppress` and `recorded_hour_not_unusual_that_C1_would_pass`; the later policy steps still apply.
- `gate_qualified_samples_per_day` (`max_C0` / `max_C1`): an unexpected notification-volume jump shows here first.

**Caveat on the live tape.** Its V2 rows exist since 2026-10-01. While the 30-day ranks are immature, both C0 and C1 report `IMMATURE`, and the replay shows few or no differences until the end of October.

## 8. Deployment procedure (after the owner's merge GO; nothing done yet)

1. **Merge order:** PR #328 (research decision and the frozen evaluator), then this PR.
2. **Pre-deploy replay** (§7) from a separate checkout, then the owner reads it.
3. **Update the code** on the VPS (`git fetch && git checkout <merge commit>`). There is no schema change, no new dependency and no config key change: only `context.version: BETA_CONTEXT_1H_V3`.
4. **Rebuild the statistics immediately:** `.venv/bin/python main.py --beta-history-build --beta-json`. Until this runs, «после похожих» cards are hidden on purpose (an analogues version mismatch), never shown from C0 history.
5. **Restart the bot:** `sudo systemctl restart signalbot-beta-bot.service`. The detector, notifier and outcome timers pick up the code on their next run, and the first detector bucket under V3 adopts the V2 episode memory.
6. **Smoke** (`deploy/signalbot-beta-smoke.sql`, now pinning V3):
   ```bash
   psql "$DSN" -v deploy_ts='<UTC deploy ts>' -f deploy/signalbot-beta-smoke.sql
   ```
   Any `FAIL` is an operational stop. Then check `--beta-health`, and `/btc` and `/catchup` in Telegram.
7. **Read-only SQL after an hour:**
   - `SELECT context_version, count(*) FROM beta_context_snapshots WHERE bucket_ts > '<deploy ts>' GROUP BY 1;` should show V3 only;
   - `SELECT payload->'analogues'->>'version' FROM beta_hist_stats ORDER BY stats_pk DESC LIMIT 1;` should show `BETA_ANALOGUES_V2`.

## 9. Rollout monitoring and rollback

**Live calibration.**
- **Weekly:** run `--beta-c1-replay --dry-run-days 7` on the VPS. C0 is reconstructed offline from the persisted tape, so no new telemetry is needed.
- **Compare per day type:** C1's `flag_*` rates against the nominal 5 / 5 / 10 % and against `historical_expectation_unit_v2`, and C1 against C0.

**Review trigger.**
- **Condition:** after ≥ 12 weekend days of mature live ranks, C1's weekend gap on a gate flag is worse than C0's by > 2 pp.
- **Action:** that is **`REVIEW_TRIGGER`**, an owner review. It is **not** an automatic rollback.

**Automatic rollback only for an engineering failure or invalid state:**
- `ContextVersionError` or detector exceptions after deploy;
- no V3 snapshots after 3 closed buckets;
- the smoke check `FAIL`.

**Rollback steps:**
1. Check out the previous commit (context V2 code and config).
2. Run `--beta-history-build` at once. The V2-era `lookup()` has no version guard, so the analogue stats must be rebuilt under V1 before cards are trusted again.
3. Restart the bot.

**What happens to the state on rollback.**
- The V2 chain resumes from its last V2 snapshot when that is younger than 30 days (`CONTEXT_MAX_GAP_BUCKETS`), and replays the buckets in between from the tape. That catch-up takes a few minutes per day of V3 runtime.
- The V3 snapshots stay as records.
- No data is deleted.
