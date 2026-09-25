# Beta V0.2 — `/btc` temporal context V0

Authority for the `/btc` temporal-context amendment to the descriptive private beta
(`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`). It fixes one product problem: `/btc`
overweighted the latest closed 5m bucket, so a strong event vanished from the picture
5–15 minutes later.

The 5m detector (`BETA_EVENT_RULES_V1`) is the fast detection layer and is **unchanged**:
- rules, thresholds and the rules digest `2e0afa47…5f44`;
- detector episodes and their transitions;
- forward outcomes, which stay anchored to the detector decision time.

The amendment adds a deterministic, versioned **projection** of the state tape around it.
It is not a forecast. It contains no direction call, no score and no generated commentary.

## Layers

| Layer | Where | Role |
|---|---|---|
| 5m state tape | `beta_state_tape` (existing) | The underlying truth, recorded by value. It now also stores each venue's raw `price_move_pct`, `oi_change_pct`, `range_width_pct`, `volume_notional_usd` and `taker_delta_notional_usd`, plus the bucket's `klines_1m` OHLC (`x:<venue>:kline_open/high/low/close`). The change is additive: existing metrics and percentiles are unchanged, and so are `state_schema_version` and the rules digest. |
| Context projection | `beta.context`, `beta_context_snapshots` | One append-only state per closed 5m bucket per (episodization, context, rules) version, chained by `prev_state_digest`. It is computed inside the detector's bucket transaction. |
| What `/btc` showed | `beta_btc_views` | The view model, its digest, the rendered text and its SHA-256, plus the context state digest it was built from. No user id is stored. |

## Episodization `BETA_EPISODES_V0`

The version label is pinned to a parameter digest (`KNOWN_EPISODIZATION_DIGESTS` in `beta/context.py`). Any parameter change without a new label makes config loading fail.

Every episode has two independent axes:
- **Confirmation:** the highest detector lifecycle level reached (EARLY, ARMED or TRIGGERED). It is computed with the detector's own `lifecycle()`, and a test checks it against a replay of `step_episode` over the same tape.
- **Phase:** ACTIVE, COOLING or ENDED.

**Primary observable.** This was an owner decision: the directional leg of each rule.

| Event | Primary observable | Direction |
|---|---|---|
| `PRICE_OI_CONTRACTION_DOWN` / `_UP` | consensus 5m price move | − / + |
| `POSITION_BUILDUP_COMPRESSION` | consensus OI change | + |
| `TAKER_FLOW_EXTREME_BUY` / `_SELL` | summed taker delta | + / − |
| `LIQUIDATION_STRESS_LONG` / `_SHORT` | side liquidation notional summed over healthy venues | + |

For liquidations, the exit test uses the per-venue side percentile ranks, because the summed notional has no percentile.

**Rule** (applied per closed bucket, in this order):
1. **Timeout:** an open episode whose start bucket is at least `max_episode_duration_min` old ends with `MAX_DURATION`.
2. **Continuation:**
   - If the event QUALIFIES, the episode goes ACTIVE (a reactivation if it was COOLING) and the countdown resets.
   - Otherwise, if the primary observable is beyond the exit percentile, the countdown resets. The episode stays ACTIVE or stays COOLING; there is no reactivation without a qualifying bucket.
   - Otherwise it goes COOLING and the countdown increments. A missing, stale or not-evaluable bucket counts here.
   - After `cooling_buckets_to_end` consecutive such buckets, the episode ends with `COOLED_DOWN`.
3. **Entry:** the detector's entry condition (QUALIFIES with `streak == lifecycle.entry_streak`), when no episode of the same type is open.
4. **Opposite side:** an opposite-side entry while the other side is COOLING ends that episode with `SUPERSEDED_BY_OPPOSITE`. The new episode takes over its `cluster_id` and records `supersedes`. Nothing is described as a "reversal".
5. **Running peak:** the bucket with the strictly most extreme primary observable in the event direction; ties keep the earliest. The state at bucket t therefore never holds a later bucket. Every PEAK metric is that bucket's own `bucket_view`.

**Parameters: UNFROZEN** (`episodization.frozen: false`).

| Parameter | Value | Entry threshold for comparison |
|---|---|---|
| `cooling_buckets_to_end` | 3 | — |
| `max_episode_duration_min` | 240 | — |
| Exit rank, DOWN | ≤ 0.20 | 0.05 |
| Exit rank, UP | ≥ 0.80 | 0.95 |
| Exit rank, BUILDUP (OI) | ≥ 0.65 | 0.80 |
| Exit rank, taker | ≥ 0.80 / ≤ 0.20 | 0.95 / 0.05 |
| Exit rank, liquidations | ≥ 0.80 on 1 venue | 0.95 on 2 venues |

- **Why unfrozen:** no historical beta tape exists yet, so N could not be evaluated on condition-series structure. These are configurable placeholders, not tuned values.
- **Validation:** config loading enforces that every exit threshold is laxer than its entry.
- **Freezing later:** use `beta.context.episode_structure_stats`, which reports episode counts, reactivations and lengths per candidate N. It never reads post-event prices or outcomes. Freezing means recording the chosen values under a new version label.

## Rolling 1h context `BETA_CONTEXT_1H_V0`

- **Window:** the last 12 closed 5m buckets, computed from raw tape values. 5m percentiles are never averaged.
- **Metrics:**
  - range: the median over venues of (max high − min low) / first open;
  - price move: the median over venues of (last close − first open) / first open;
  - volume: the sum of the 5m cross-venue volume sums.
- **Baseline:**
  - Each value is ranked against the rolling-1h values sampled at every 5m step in the preceding 30 days.
  - The ranking uses the frozen percentile core (timeframe `1h`) and reads the tape as of the bucket's LIVE row (`tape_id` bound).
- **Missing data:** 1h is n/a when any of the 12 buckets is missing.
- **Labels:** fixed thresholds on the percentile rank: normal < 0.80 ≤ elevated < 0.95 ≤ high < 0.99 ≤ extreme. Labels are shown only when the history is mature.

**Signed values.** The system's percentiles are signed distributions, not `abs(x)`. `/btc` always prints the signed raw value, and adds `top X%` / `bottom X%` only within the 20% tails. Below 1% it prints `<1%`, never "100th percentile".

## `/btc`

- **Headline:** DATA STALE / DATA DEGRADED always win, fail-closed as before. Otherwise the headline is WATCH or EVENT ACTIVE (existing vocabulary, by confirmation) for an ACTIVE episode, COOLING, or NO ACTIVE EVENTS.
- **Compact lines:**
  1. event · confirmation · start (and reactivations);
  2. running peak (a single bucket);
  3. now (the latest bucket);
  4. 1h range / volume labels and the signed 1h price move;
  5. venues: coverage and peak direction agreement from per-venue signs, so a single-venue extreme reads for example "peak direction on 1/3";
  6. reference price and "data through".
- **No active episode:** the summary shows now, 1h and "Last event: … ended Nm ago".
- **Details:** the button opens the full now and peak percentiles, the 1h ranks, the venue breakdown, phase, confirmation, reactivations, linked detector episode ids and the versions.

## Notifications

There is one loud push per context episode. A detector trigger inside a context episode that already produced a would-push decision is recorded as `SUPPRESSED` / `CONTEXT_EPISODE_NOTIFIED` (`would_push = false`). The existing push choice (TRIGGERED) and every other gate are unchanged. An opposite-side episode is a new episode and is eligible for its own push.

## Replay

- **What the user saw:** the `beta_btc_views` rows. Pushes are the existing outbox rows.
- **What replay recomputes:** `beta.detector.replay_context` recomputes the states from the LIVE decision rows, which are the revisions the detector used, and from the as-of 1h history, under the configured episodization version.
- **Tests:** integration tests check that the recomputed states are byte-identical (`state_digest`) to the persisted chain, and that a replay of any prefix equals the live state at that bucket.
- **Corrections:** later `CORRECTION_CHECK` revisions never rewrite past states.
- **Gaps:** the detector steps through buckets it skipped (no row counts as below exit). After more than 30 days without any state, it restarts empty.

## Deferred (not in V0)

- 15m context.
- Time-of-day normalized thresholds.
- Flow persistence in the summary.
- Free-form narrative, a composite activity score, forecasting, trade suggestions, new event families, and outcome-based tuning.
- Silently editing the original push message on later phase changes. There is no edit path in the delivery outbox yet, so later changes are visible through `/btc` only.
- CPI/FOMC annotation: there is no authoritative beta calendar integration.
- 1h OI change: per-venue OI first/last values are not on the tape.
