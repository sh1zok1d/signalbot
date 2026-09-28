# Beta V0.2 — `/btc` temporal context V0

Authority for the `/btc` temporal-context amendment to the descriptive private beta
(`docs/PRIVATE_BETA_V0_RESTART_DECISION.md`).

**Problem:** `/btc` overweighted the latest closed 5m bucket, so a strong event vanished from the picture 5–15 minutes later.

**Solution: recent-event memory, not invented persistence.** An independent outcome-blind audit found that no historical detector tape exists from which hysteresis parameters could be frozen. So the current detector episode boundaries are preserved exactly, and `/btc` gains LAST EVENT memory.

Everything authoritative is unchanged:
- `BETA_EVENT_RULES_V1` thresholds. The rules digest changed only because the state-tape schema moved to V2; see below.
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

The main view is a compact mobile layout in sections: headline, then ACTIVE EVENT or LAST EVENT, then `NOW · 5m`, then `1H CONTEXT`, then venues / readiness / data freshness, then the disclaimer. It is rendered only from the persisted view model (`beta_btc_views.payload`). Ranks, anchor kind, the normal end reason, unanimous venue agreement, per-venue values and the per-rule readiness breakdown are in **Details** / **Readiness**, not in the main view.

- **Headline:** DATA STALE, then DATA DEGRADED, then WATCH / EVENT ACTIVE (the existing fail-closed product status, unchanged). When the product status is NO ACTIVE EVENTS, the headline becomes HISTORY BUILDING (or DETECTOR NOT READY) unless the Price/OI families are actually evaluable. See the warm-up and readiness section of `docs/PRIVATE_BETA_V0_DEPLOY.md`.
- **Detector readiness (`beta/readiness.py`, read model `BETA_READINESS_V0`):** derived per family from the latest LIVE tape row. It is READY exactly when the detector's own rule evaluation for that bucket was evaluable. Otherwise the rules' own gates classify it as HISTORY_BUILDING, DATA_UNAVAILABLE, DEGRADED or DISABLED. Progress is the percentile core's span. The readiness block is persisted with each `beta_btc_views` row and never produces a push.
- **ACTIVE EVENT:** an open detector episode. The summary shows the event, the level reached, and the qualifying window and bucket count. Other open episodes are listed as "Also open".
- **LAST EVENT:** shown when no episode is open. It is the most recently ended detector episode, with its qualifying window and when it ended. The end reason is shown on the main view only when it is not the normal `condition no longer met`; Details always shows it. It stays for `context.last_event_retention_min` (120 min, a presentation setting) after the episode ended, and is never shown as active.
- **Anchor bucket:** one real bucket per episode; every metric shown for it comes from that bucket. The main view shows the event's two primary raw values at it (prefixed `At HH:MM–HH:MM:` when the episode spans more than that bucket); Details shows the anchor kind and every percentile.

  | Family | Anchor | Why |
  |---|---|---|
  | TAKER_FLOW_EXTREME_BUY / _SELL | Strongest observed bucket: strict improvement of signed taker delta in the event direction, earliest tie. The state at bucket t never holds a later bucket. | The audit rated taker flow SUPPORTED as a single-observable intensity series. |
  | PRICE_OI_CONTRACTION_DOWN / _UP, POSITION_BUILDUP_COMPRESSION | The detector's own trigger bucket, or the opening bucket while not triggered. | These events are conjunctions; ranking a "strongest" bucket would need an invented composite. |
  | LIQUIDATION_STRESS_LONG / _SHORT | Trigger bucket. The main view shows the rule's own vote count, for example "votes 2 of 3 eligible venues"; Details names the voting venues and per-venue notionals. | Per-venue voting is preserved; there is no summed cross-venue intensity. |

- **Now (`NOW · 5m`):** the latest 5m bucket (it ends at "Data through"): price and OI with their tail label when in a 20% tail, and the volume level.
- **1h:** see below.
- **Venues:** the latest bucket's coverage for the event's family (price otherwise). Partial same-direction agreement at the anchor bucket is shown in the event section, for example "Same direction on 1/3 venues"; unanimous agreement and the per-venue signs are in Details.
- **Details button:** the full percentiles for the anchor and for now, the 1h ranks, the per-venue breakdown and the versions.
- **Consistency guard:** if the projection's open episodes ever differ from the detector's open episodes in the database, `/btc` shows no projection details.
- **Record of what was shown:** each `/btc` writes a `beta_btc_views` row with the view model, its digest, the rendered text and its SHA-256, plus the context state digest. No user id is stored.

## State-tape schema V2

The temporal context needs inputs that the V1 tape did not record, so the tape moved to an explicit **`state_schema_version = 2`**. The payload shape is a function of the version; a schema-1 configuration still writes V1 rows byte-for-byte.

**V2 = V1 plus:**
- per-venue raw Stage-2 values, in the snapshot's `venue_raw`;
- per-venue 5m `klines_1m` OHLC: `metrics` keys `x:<venue>:kline_*` and the venue's `ohlc` entry.

All of these are inside `feature_digest`, which is the V2 correction identity. A genuine change to any of them, for example a revised kline high, is detected as a normal `CORRECTION_CHECK`.

**Rules digest:** the `BETA_EVENT_RULES_V1` thresholds are unchanged. The digest covers `state_schema_version`:

| Schema | Rules digest |
|---|---|
| 1 (historical identity) | `2e0afa47…5f44` |
| 2 (active) | `9e9d2c631a1abfdb710dc2147835b3a0ccd4620512d3a0d6828140c96de17210` |

Both are pinned in `tests/beta/test_beta_config.py`.

**Transition rules:**
- **Correction checks compare like with like.** Only rows of the current rules digest and schema version share a correction identity. Re-checking a bucket that was decided only under another schema version returns `SCHEMA_VERSION_BOUNDARY`: nothing is appended, no episode is flagged, and no market-data correction is ever inferred from a payload-shape change.
- **Episodes:** because the rules digest changes, an episode still open under V1 ends at the first V2 bucket with the existing `DETECTOR_VERSION_CHANGED`. The previous-bucket streak is not carried across, and the context projection (keyed by rules digest) restarts empty under V2. This is the existing detector behaviour for any rules-digest change, and it is preferable to merging across incompatible representations.
- **Detector percentile history:** reads V1 and V2 rows (`PERCENTILE_HISTORY_SCHEMA_VERSIONS`). V2 only adds keys, so every consensus and liquidation metric, and every 30-day percentile, is identical, and detection is unaffected by an upgrade.
- **Rolling-1h history:** reads rows of the current V2 schema only. V1 rows, which have no OHLC, are never mixed into a window and never defaulted.
- **1h warm-up after an upgrade:** the 1h context is unavailable until 12 contiguous V2 buckets exist, and becomes available at the 12th. Its percentile labels stay "n/a (history building)" until 30 days of V2 rolling-1h history are mature. On a fresh deployment the bootstrap writes V2 rows, so the history is V2 from the start.
- **Replay:** the context state records `state_schema_version`, and `step_context` refuses any tape row of another schema version. A V2 replay can never reinterpret a V1 row.

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
