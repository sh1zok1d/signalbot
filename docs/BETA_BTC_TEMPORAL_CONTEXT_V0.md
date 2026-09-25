# Beta V0.2 — `/btc` temporal context V0

Authority for the `/btc` temporal-context amendment to the descriptive private beta
(`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`).

**Problem:** `/btc` overweighted the latest closed 5m bucket, so a strong event vanished from the picture 5–15 minutes later.

**Solution: recent-event memory, not invented persistence.** An independent outcome-blind audit found that no historical detector tape exists from which hysteresis parameters could be frozen. So the current detector episode boundaries are preserved exactly, and `/btc` gains LAST EVENT memory.

Everything authoritative is unchanged:
- `BETA_EVENT_RULES_V1` and rules digest `2e0afa47…5f44`;
- detector episodes and transitions;
- push decisions;
- forward outcomes.

The amendment only adds a deterministic, versioned presentation **projection** of the state tape. It is not a forecast. It contains no direction call, no score and no generated commentary.

## Active episodization: `STRICT_QUALIFICATION_V1`

The episodes are the detector episodes. `beta.context.step_context` replays `beta.detector.step_episode` on exactly the inputs the detector used, which are the LIVE decision rows. An episode therefore:
- opens on the existing detector entry;
- ends on the first bucket that does not QUALIFY, or on a detection gap, a non-evaluable bucket, or a rules / calculation-version change;
- for POSITION_BUILDUP_COMPRESSION, keeps its existing duration cap.

There is no hysteresis, no COOLING, no reactivation and no new episode identity; the episode id is the detector's `EV-…` id.

`episodization.live_hysteresis_enabled` must be `false`: config loading rejects `true`. The version label is pinned to a digest in `beta/context.py`.

**Tests guaranteeing this:**
- A PostgreSQL golden test runs a fixed input sequence with push disabled and with push enabled. Detector episodes, transitions and push decisions are identical to the pre-amendment base commit `234d5ee`.
- A pure test checks that the projection's episodes equal a direct `step_episode` replay on a mixed tape. The tape covers CONDITION_FAILED, DETECTION_GAP, NOT_EVALUABLE and MAX_DURATION.
- A context-failure test checks that a failing projection neither changes nor blocks detection. It runs in its own savepoint after every detector decision of the bucket.

## What `/btc` shows (factual detector state only)

- **Headline:** always the existing fail-closed product status: NO ACTIVE EVENTS, WATCH, EVENT ACTIVE, DATA DEGRADED or DATA STALE.
- **ACTIVE EVENT:** an open detector episode. The summary shows the event, the level reached, and the qualifying window and bucket count.
- **LAST EVENT:** shown when no episode is open. It is the most recently ended detector episode, with its qualifying window, when it ended, and the factual end reason. It stays for `context.last_event_retention_min` (120 min, a presentation setting) after the episode ended, and is never shown as active.
- **Anchor bucket:** one real bucket per episode; every metric shown for it comes from that bucket.

  | Family | Anchor | Why |
  |---|---|---|
  | TAKER_FLOW_EXTREME_BUY / _SELL | Strongest observed bucket: strict improvement of signed taker delta in the event direction, earliest tie. The state at bucket t never holds a later bucket. | The audit rated taker flow SUPPORTED as a single-observable intensity series. |
  | PRICE_OI_CONTRACTION_DOWN / _UP, POSITION_BUILDUP_COMPRESSION | The detector's own trigger bucket, or the opening bucket while not triggered. | These events are conjunctions; ranking a "strongest" bucket would need an invented composite. |
  | LIQUIDATION_STRESS_LONG / _SHORT | Trigger bucket. Shows the rule's own per-venue votes, for example "top 5% on binance, bybit (2 of 3 eligible venues)", and per-venue notionals in Details. | Per-venue voting is preserved; there is no summed cross-venue intensity. |

- **Now:** the latest 5m bucket, labelled with its window, so it can't be confused with the anchor or the last event.
- **1h:** see below.
- **Venues:** coverage, and at the anchor bucket the same-direction agreement from per-venue signs. A single-venue extreme therefore reads as, for example, "same direction on 1/3".
- **Details button:** the full percentiles for the anchor and for now, the 1h ranks, the per-venue breakdown and the versions.
- **Consistency guard:** if the projection's open episodes ever differ from the detector's open episodes in the database, `/btc` shows no projection details.
- **Record of what was shown:** each `/btc` writes a `beta_btc_views` row with the view model, its digest, the rendered text and its SHA-256, plus the context state digest. No user id is stored.

## Tape additions (additive)

- **Per-venue raw Stage-2 values:** stored by value in the snapshot (`venue_raw`) for venue agreement.
- **Per-venue 5m `klines_1m` OHLC:** stored in `metrics` (`x:<venue>:kline_*`), because the rolling-1h history needs it.
- **Unchanged:** existing metrics, percentiles, `state_schema_version` and the rules digest. This is also the evidence a future calibration will need.

## Rolling 1h context: `BETA_CONTEXT_1H_V0`

- **Window:** the last 12 closed 5m buckets, computed from raw values. 5m percentiles are never averaged.
- **Metrics:**
  - range: the median over venues of (max high − min low) / first open;
  - price move: the median over venues of (last close − first open) / first open;
  - volume: the sum of the 5m cross-venue volume sums.
- **Baseline:** each value is ranked against the rolling-1h values at every 5m step in the prior 30 days. The ranking uses the frozen percentile core (timeframe `1h`) and reads the tape as of the bucket's LIVE row.
- **Labels:** fixed thresholds on the percentile rank: normal < 0.80 ≤ elevated < 0.95 ≤ high < 0.99 ≤ extreme. Labels are shown only when the history is mature.
- **Signed values:** the system's percentiles are signed distributions. `/btc` prints the signed raw value, and adds "top/bottom X%" only within the 20% tails. Below 1% it prints "<1%", never "100th percentile".

## Replay

- **Storage:** `beta_context_snapshots` holds one append-only state per bucket per (episodization, context, rules) version, chained by `prev_state_digest`.
- **Recompute:** `beta.detector.replay_context` recomputes the states from the LIVE decision rows plus the as-of 1h history.
- **Tests:** replay must be byte-identical to the persisted chain, and a replay of any prefix must equal the state at that bucket.
- **Corrections:** later `CORRECTION_CHECK` revisions never rewrite past states.
- **Gaps:** buckets the detector skipped are recorded with no input and not stepped, exactly as in the detector.

## Shadow / calibration code (dormant)

`beta/context_calibration.py` holds the `EXPERIMENTAL_TAKER_HYSTERESIS_UNFROZEN` offline simulation.
- It covers the taker families only; the conjunction families and liquidation voting are deliberately unsupported.
- `structure_stats` reports condition-series structure per candidate parameter set (episodes ended or still open, reactivations, mean length). It never reads forward prices or outcomes.
- No runtime module imports it (an AST test enforces this). Nothing from it is persisted, rendered or delivered, and it has no config section.
- Freezing any hysteresis later requires real tape history, a separate approval, and a new episodization version.

## Performance

**Measured on local PostgreSQL 16, not TimescaleDB.** The dataset was a synthetic dense 30-day-plus-1h tape of 8,652 rows, and each variant ran 40 closed-bucket evaluations, including fake Stage-2 materialization.

| Variant | p50 | p95 | Metrics JSON in the 30-day history |
|---|---|---|---|
| Old 14-key tape, no context | 0.69 s | 0.77 s | 5.2 MB |
| New 26-key tape, no context | 0.81 s | 0.92 s | 9.5 MB |
| New tape, context on | 1.60 s | 1.76 s | 9.5 MB |

- **Context path query count:** 3 statements per bucket in steady state: the latest state, one 30-day-plus-55-minute tape history fetch (about 8,650 rows), and one insert.
- **Worst-case catch-up:** 12 buckets, about 21 s, inside the 240 s unit timeout.
- **Not validated:**
  - the added OHLC aggregation in the Stage-1 `klines_1m` bucket query on a real TimescaleDB hypertable;
  - any real deployment dataset.

## Deferred

- 15m context and time-of-day normalized thresholds.
- Live hysteresis / COOLING, which needs frozen parameters from real tape and a separate approval.
- Flow persistence in the summary.
- Narrative, composite scores, forecasting and trade suggestions.
- New event families and outcome-based tuning.
- Editing push messages in place.
- CPI/FOMC annotation.
- 1h OI change: per-venue OI first and last values are not on the tape.
