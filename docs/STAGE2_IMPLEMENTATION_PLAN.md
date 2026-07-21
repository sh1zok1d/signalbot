# Stage 2.1 — Implementation Plan (Phase 0 output)

Scope: **Stage 2.1 Foundation only** (Feature Engine + Percentile Engine +
Data Confidence + validation CLI, BTCUSDT only, 3 active exchanges). No
event detection, scoring, state machine, Telegram, or multi-symbol
ingestion in this phase. Nothing in this plan has been executed — it is the
proposal to approve before writing code.

> **Consensus Contract Revision 0.2.3 — frozen for Stage 2.1.** The
> cross-exchange aggregation formulas (coverage, ternary direction agreement,
> dispersion, Data Confidence weights + applicable-component matrix, roll-ups,
> outlier robust-z, liquidation-quality source, `is_usable` gating, replay
> denominator) are now fully specified and frozen in `STAGE2_SPEC.md` §11. The
> config surface for it (`data_confidence.weights`, `outliers.robust_z_threshold`)
> ships in `config/stage2.yaml` and is validated by `common/stage2_config.py`;
> it enters `config_hash`/`calculation_version`. `consensus.py` and its models
> are NOT built in this step — only the contract and its config are frozen.

> **Percentile Contract Revision 0.2.4 — frozen for Stage 2.1.** The Percentile
> Engine's every calculation rule — mid-rank empirical percentile (0..1, no
> rounding), `[B − W, B)` window membership, scope isolation, the per-scope
> metric allow-list + source mapping, NULL/NaN/duplicate behavior, span-based
> confidence tiers, purity, and schema parity — is frozen in `STAGE2_SPEC.md`
> §12. Its config surface (`defaults.percentiles.confidence_tiers`) ships in
> `config/stage2.yaml` and is validated in `common/stage2_config.py`; it enters
> `config_hash`/`calculation_version`. The Percentile Engine itself
> (`analytics/percentile_engine/`) is **NOT** built in this step.

> **Data Quality Contract Revision 0.2.5 — frozen for Stage 2.1.** The Data
> Quality / gap-detection rules — deterministic `snapshot_ts` cadence; boolean
> health model (`is_stale`/`is_usable`) with a complete ordered derived label set
> (`not_available` / `unavailable_historical` / `disconnected` /
> `connection_unknown` / `no_data` / `stale` / `gap_exceeded` / `ok`); raw-source
> mapping on the real `ts` column (`ohlcv` serving price_structure+volume as one
> row); `expected_interval_s` from the frozen `(metric, source_mode)` mapping
> (live vs historical cadence); **fail-closed** event-driven liquidation handling
> (quiet ≠ stale, but unknown/absent connection ⇒ unusable); `lateness_ms`/
> `is_stale`; interval-based gap detection with `largest_gap_s = ceil(max delta)`
> and `gap_exceeded`; coverage window; `backfill_status` as a validated
> orchestration input; calculation-version isolation with **raw observations
> carrying no calculation_version** — are frozen in `STAGE2_SPEC.md` §13.
> Historical maturity is NOT a data-quality concern (it lives in Percentile §12).
> Its config surface (`defaults.data_quality`, four keys) ships in
> `config/stage2.yaml` and is validated in `common/stage2_config.py`; it enters
> `config_hash`/`calculation_version`. The Data Quality core
> (`analytics/data_quality/`) is **NOT** built in this step.

## Files to create — REVISED 0.1

```
config/stage2.yaml
common/stage2_config.py              # Stage2Config loader + global→tier→symbol resolution
common/symbol_mapper.py              # NEW (decision F): canonical symbol → per-exchange instrument id
common/versioning.py                 # config_hash / code_version / calculation_version derivation
common/instrument_metadata.py        # NEW (decision J): fetch-and-store ctVal/tick, LKG fallback, mismatch alarm

analytics/__init__.py
analytics/feature_engine/__init__.py
analytics/feature_engine/bucket_listener.py   # live cross-exchange bucket-close hook (supervised)
analytics/feature_engine/exchange_features.py # LEVEL A — per-exchange feature computation
analytics/feature_engine/consensus.py         # LEVEL B — cross-exchange aggregation
analytics/feature_engine/units.py             # notional normalization (base vs contracts)
analytics/percentile_engine/__init__.py
analytics/percentile_engine/compute.py        # 7d/30d, exchange+consensus scope, strictly-earlier
analytics/data_quality/__init__.py
analytics/data_quality/health.py              # DataHealthSnapshot, deterministic snapshot_ts
analytics/data_quality/gaps.py                # gap/missing-bucket detection (new capability)
analytics/bootstrap/__init__.py
analytics/bootstrap/historical.py             # --stage2-backfill job (SPEC §8.2)
analytics/bootstrap/reconcile.py              # late-data correction / recompute queue (SPEC §8.3)
analytics/supervisor.py                       # failure isolation, backoff, DEGRADED (SPEC §9)

symbols/__init__.py
symbols/registry.py                  # declarative symbol + symbol_exchange_capabilities data

storage/stage2_schema.sql            # new tables from STAGE2_SPEC.md §2 (all additive)

docs/STAGE2_SPEC.md                  # committed
docs/STAGE2_IMPLEMENTATION_PLAN.md   # this file, committed
docs/STAGE2_DATA_AUDIT.md            # committed
docs/STAGE2_CLARIFICATIONS.md        # committed

tests/analytics/test_exchange_features.py
tests/analytics/test_consensus.py            # incl. no-raw-OI-sum, 2/3 partial consensus
tests/analytics/test_units.py                # base vs contracts normalization
tests/analytics/test_percentile_engine.py    # incl. strictly-earlier / no-lookahead
tests/analytics/test_data_quality.py
tests/analytics/test_bootstrap_idempotency.py
tests/analytics/test_catchup_and_late_data.py   # incl. double-scan race, drop-oldest requeue
tests/analytics/test_percentile_invalidation.py # 7d/30d recompute ranges (rev 0.2)
tests/analytics/test_calculation_version.py     # config change forks results, no overwrite
tests/analytics/test_failure_isolation.py
tests/common/test_symbol_mapper.py           # silent-mislabel prevention
tests/common/test_instrument_metadata.py     # LKG fallback, mismatch alarm, fail-closed
tests/symbols/test_registry.py
```

## Files to modify — REVISED 0.1

| File | Change | Risk |
|---|---|---|
| `storage/db.py` | Add `init_stage2_schema()` (mirrors `init_schema()`'s statement-splitting), `seed_symbols()` + `seed_symbol_exchange_capabilities()` (mirror `seed_capabilities()`), Stage 2 upsert writers, watermark/recompute-queue helpers. All gated by `stage2.enabled` | Low — purely additive methods, no existing method touched |
| `main.py` | Add `--stage2-validate` and `--stage2-backfill [--from --to]` CLI flags; when `stage2.enabled`, start the supervised listener task alongside `IngestionManager` | Low — new code paths only |
| `data_ingestion/okx_client.py` | **Separate isolated PR, before Stage 2.1** (decision F): replace module constant `INST_ID` with `symbol_mapper.to_exchange_symbol('okx', symbol)` | Medium — Stage 1 production file; covered by dedicated tests |
| `backfill/backfill.py` | **Same separate PR**: replace all three hardcoded `"BTC-USDT-SWAP"` literals with the shared mapper | Medium — same |

**`storage/schema.sql` is NOT modified.** Revision 0.1 removes the
`exchange_capabilities` PK change entirely (decision E) — Stage 1's table
keeps its exact current shape and Stage 1 keeps reading it unchanged.

## Prerequisite ingestion phases (blocked work, not descoped)

Per decisions C and D, these are scheduled phases rather than deletions:

- **Phase 1.5 — Spot Ingestion** (prerequisite for anything marked
  `BLOCKED_BY_SPOT_INGESTION`). Unblocks: spot CVD, spot/perp divergence,
  spot-confirmed demand setups.

  **Correction (revision 0.2.1): spot does NOT slot additively into the
  existing raw tables.** The previous revision claimed it did; that was
  wrong. Every Stage 1 raw hypertable is keyed
  `PRIMARY KEY (exchange, symbol, ts)` — there is **no `market_type`
  column anywhere in `storage/schema.sql`**. Writing spot BTCUSDT into
  `klines_1m` would therefore collide directly with perp BTCUSDT on the
  same `(exchange, 'BTCUSDT', ts)` key, and because every writer uses
  `ON CONFLICT ... DO UPDATE`, the collision would not error — **spot and
  perp bars would silently overwrite each other**. That is a data-loss
  bug, not a schema inconvenience.

  Phase 1.5 must therefore begin with its own short design audit
  choosing between:
  1. **Separate spot raw tables** (`spot_klines_1m`, `spot_trades`, …) —
     no change to any running Stage 1 hypertable;
  2. **v2 raw tables** carrying `market_type` in the primary key, with
     Stage 1 writing to the old tables until cutover;
  3. **In-place migration** of the existing hypertables to add
     `market_type` to their primary keys.

  **Preferred baseline: option 1 (or 2) — separate tables, leaving the
  working Stage 1 hypertables untouched.** Option 3 means rewriting the
  primary key of live, populated TimescaleDB hypertables holding the
  project's only source-of-truth data, which is the single riskiest
  operation available in this codebase and buys little that option 1
  doesn't. The final choice is deferred to the Phase 1.5 audit, not
  settled here.

  Note that Stage 2's own tables already carry `market_type` in their
  keys, so the *feature* layer is ready for spot; it is only the raw
  ingestion layer that is not.
- **Phase 1.6 — Orderbook Ingestion** (prerequisite for anything marked
  `BLOCKED_BY_ORDERBOOK_INGESTION`). Scope: depth snapshots + incremental
  updates, a new raw table, and a retention policy of its own (orderbook is
  by far the highest-volume data type in the plan — its storage cost must
  be measured before it is enabled). Unblocks: orderbook imbalance, wall
  persistence/execution/cancellation, spoof risk.

Neither is part of Stage 2.1. Both must be separately scoped, and both
gate specific detectors listed in `STAGE2_CLARIFICATIONS.md` §24.

## Migration plan — REVISED 0.1

All migrations idempotent and safe to re-run, following `schema.sql`'s
existing `IF NOT EXISTS` convention exactly. **Revision 0.1 makes the whole
migration purely additive — there is no longer any change to an existing
Stage 1 table.**

1. **New tables only (10)** — `symbols`, `symbol_status_history`,
   `exchange_instruments`, `symbol_exchange_capabilities`,
   `exchange_feature_vectors`, `consensus_feature_vectors`,
   `percentile_snapshots`, `data_health_snapshots`, `stage2_watermarks`,
   `stage2_recompute_queue`. Each `CREATE TABLE IF NOT EXISTS` +
   `create_hypertable(..., if_not_exists => TRUE)` where time-series.
   Zero risk to any existing table; Stage 1 code never reads or writes
   any of them.
2. **`exchange_capabilities` — NOT TOUCHED.** No new column, no PK change,
   no reseed change. Stage 2's symbol/market_type dimension lives in
   `symbol_exchange_capabilities` (metric-level capability) and the
   instrument/unit metadata in `exchange_instruments` (one row per
   instrument) — split in revision 0.2 because they have different
   cardinality and different lifecycles: capability is a reviewed
   declaration, instrument metadata is fetched from the venue (decision
   J). Both are seeded with the same idempotent-upsert pattern
   `seed_capabilities()` already uses; where capability overlaps the
   Stage 1 declaration, `symbol_exchange_capabilities` is seeded *from*
   it so there is one authoring source, not two competing ones.
3. **Down-migration**: `DROP TABLE IF EXISTS` on the ten new tables. Since
   every one of them is derived data (features, percentiles, health,
   watermarks) rebuildable by `--stage2-backfill` from untouched raw
   Stage 1 data, a full rollback loses no source-of-truth information.
   This is a materially better rollback story than the previous draft,
   which required restoring a modified PK on a live table.
4. **Feature-flag gate**: none of the above runs unless `stage2.enabled:
   true` in `config/stage2.yaml`. With it `false`, `main.py` behaves
   byte-for-byte like current Stage 1 — `init_stage2_schema()` is never
   called and no Stage 2 table is created.

## Historical bootstrap — operational design

Design contract is in `STAGE2_SPEC.md` §8.2; this is the operational
wrapper.

```bash
# Full bootstrap from whatever raw history exists (idempotent, resumable)
python main.py --stage2-backfill

# Bounded range (e.g. re-derive one week after a config change)
python main.py --stage2-backfill --from 2026-07-01 --to 2026-07-08
```

- Runs as its **own process** with its own DB pool (`stage2.bootstrap.
  pool_size`, separate from the live pool) so it cannot starve live
  ingestion of connections.
- Processes buckets in ascending order; writes exchange features →
  consensus features → percentiles per bucket before advancing.
- Advances `stage2_watermarks` per completed bucket, which doubles as the
  resume point — an interrupted run continues, it does not restart.
- Configurable inter-batch sleep (`stage2.bootstrap.throttle_ms`) to bound
  DB load.
- Percentile ranks use **only** buckets strictly earlier than the one being
  computed, enforced both in the query and by the
  `ck_ps_no_lookahead` CHECK constraint.
- Safe to run while live ingestion is running; safe to run repeatedly.
- **Expected output at first run**: roughly 30 days of price/OI/funding
  features for binance/bybit (OKX OI live-only), and taker-flow/CVD
  features that are **Binance-only for historical periods** and become
  3-exchange from the point live collection started — exactly the coverage
  asymmetry documented in `STAGE2_CLARIFICATIONS.md` §23.1. The bootstrap
  must report this asymmetry explicitly rather than presenting a uniformly
  "complete" 30d history.

## Liquidation dedup — evidence first (decision G)

The naive fix is rejected: a `UNIQUE (exchange, symbol, ts, side, price,
qty)` index would silently discard genuinely distinct liquidations that
share those values during a cascade — under-reporting precisely when the
data matters most (`STAGE2_DATA_AUDIT.md` §10).

Required sequence, in order:

1. **Capture raw payloads.** Add temporary raw-payload logging (or a
   `raw_payload JSONB` column, decision pending) for each provider's
   liquidation feed and collect a sample including at least one cascade.
2. **Determine per provider**: is there a provider-side event/order ID?
   What is the timestamp resolution (ms? sub-ms?)? Does the provider ever
   redeliver on reconnect, and is redelivery marked?
3. **Then choose the model**, per provider:
   - **If a provider event ID exists** → `UNIQUE (exchange, symbol,
     provider_event_id)`. Exact, no false merges.
   - **If not** → a bounded dedup model: treat as duplicate only within a
     narrow reconnect window (e.g. events re-received within N seconds of a
     reconnect, matching on full content), and **only** when the client is
     known to have just reconnected. Outside that window, identical events
     are treated as distinct — the default bias is to keep data.
4. **Never delete a raw event as a duplicate without sufficient
   confidence.** Where confidence is low, mark rather than remove
   (`suspected_duplicate BOOLEAN`), so the feature layer can choose and
   the raw record survives.

Until this is resolved, liquidation-derived **percentiles** are still computed
normally, and their `percentile_snapshots.confidence_tier` remains the **generic
sample-maturity tier** from the frozen confidence-span formula (`STAGE2_SPEC.md`
§12.6) — unresolved liquidation dedup does **not** mutate that tier and there is
no metric-specific tier override. Instead, liquidation percentiles are
**prohibited from scoring / admission** until the separate liquidation
feed-quality (provider-aware dedup) requirement is satisfied. That restriction is
a Phase-3 admission gate, not a change to the Stage 2.1 tier.

## Storage and retention estimate

I do not have a live connection to the actual database, so this is a
structural estimate from the schema + documented cadence, not a measured
number. `docs/VPS_DEPLOY.md` §12 already has the exact command to get the
real figure — recommend running it and comparing against this estimate
before finalizing any retention policy:

```bash
sudo docker exec btcbot_timescaledb psql -U btcbot -d btcbot \
  -c "SELECT pg_size_pretty(pg_database_size('btcbot'));"
```

**Stage 1 today (order of magnitude, BTCUSDT, 3 exchanges):**
- `klines_1m`: 3 × 1,440/day ≈ 4,300 rows/day — small, well under 1 MB/day
  uncompressed.
- `open_interest` / `funding_rate` / `mark_price`: 3 exchanges × ~4/min
  (15s poll) each ≈ 17,000 rows/day per table — still small numeric rows.
- `liquidations`: event-driven, variable; the 1h soak observed ~116 events
  combined (binance 90 + bybit 26) in a moderately active hour — a volatile
  day could plausibly reach low thousands of rows.
- 30 days retained today per `backfill.window_days`; no compression policy
  exists yet in `schema.sql` (nothing else to say here — Stage 1 doesn't
  set one).

**Stage 2.1 additions (BTCUSDT only) — revised for the two-level model:**
- `exchange_feature_vectors`: rows/day × **3 exchanges** now.
  Per exchange: 1m 1,440 + 5m 288 + 15m 96 + 1h 24 + 4h 6 ≈ 1,854/day
  → **≈ 5,560 rows/day** across three venues. Each row ~25 columns.
- `consensus_feature_vectors`: ≈ **1,854 rows/day** (no exchange
  dimension), each row wider (arrays + JSONB).
- `percentile_snapshots`: now **two scopes**. Exchange scope ≈ metrics
  (~10) × timeframes (5) × windows (2) × 3 exchanges; consensus scope the
  same without the exchange factor. Order of magnitude **tens of
  thousands of rows/day** — the largest single Stage 2.1 contributor, and
  the one most worth measuring early.
- `data_health_snapshots`: (symbol × 3 exchanges × ~6 metrics) per
  health cadence; at one snapshot per minute ≈ 26,000 rows/day, so the
  health cadence should be configurable and probably coarser than 1m
  (proposal: align to 1m for gap accuracy but revisit once measured).
- `stage2_watermarks` / `stage2_recompute_queue`: negligible.

The two-level split and the second percentile scope roughly **quadruple**
the earlier estimate. Still small in absolute terms at one symbol, but no
longer trivially so — which reinforces that retention (decision H) should
be set from measurement, not assumption.

**Revision 0.2 multiplier — `calculation_version`.** Because
`calculation_version` is part of the logical key, every retained
configuration keeps its own full result set. Two retained versions ≈ 2×
the above; N versions ≈ N×. In steady state the version changes only when
config or analytics code changes, so this is bounded in practice — but it
means "how many superseded calculation versions do we keep" is now a real
retention question (folded into decision H), and `--stage2-validate` must
report distinct versions and their row counts so the growth is visible
rather than discovered later.

**Measurement plan (decision I).** Take a `pg_database_size` reading plus
per-table row counts **now**, and a second identical reading **24 hours
later**. The pair gives both the absolute baseline and the true daily
growth rate — a single reading gives neither. Record both here when
available; retention values stay draft until then.

**Conclusion:** Stage 2.1 at BTCUSDT-only scale is very unlikely to be a
storage concern — the dominant cost today is almost certainly the
15s-poll tables (OI/funding/mark price), not anything Stage 2.1 adds. The
clarifications doc's proposed retention/compression policy (§5 there) is
reasonable to adopt as a target, but should be validated against the real
`pg_database_size` figure first, and **must not be applied automatically**
per the plan's explicit instruction — proposed only, not run.

## Stage 2.1 acceptance criteria — REVISED 0.1

Modeled on `docs/STAGE1_ACCEPTANCE.md`'s per-check format. Items marked
**[R]** are the mandatory tests added by Architecture Review 0.1.

### Functional

- [ ] Exchange Feature Engine writes one `exchange_feature_vectors` row per
      enabled exchange per bucket for `1m/5m/15m/1h/4h`, covering the full
      contract in `STAGE2_CLARIFICATIONS.md` §23.1, with no modification to
      `klines_1m`/`open_interest`/`liquidations` or their write paths.
- [ ] Consensus Feature Engine writes one `consensus_feature_vectors` row
      per bucket containing only aggregation results (coverage, direction
      agreement, robust aggregates, dispersion, outliers, confidence).
- [ ] Percentile Engine computes 7d and 30d percentiles at **both**
      `exchange` and `consensus` scope, with sample size and confidence
      tier (`none`/`low`/`building`/`mature`) reusing the exact boundaries
      in `storage/validate.py::_confidence_tier`.
- [ ] Data Confidence uses a **dynamic** exchange denominator from
      `symbol_exchange_capabilities.enabled` — never a hardcoded `/3`
      or `/4`.
- [ ] `data_health_snapshots` populated with deterministic `snapshot_ts`,
      distinguishing `not_available`/`no_data`/`stale`/`short_history`/`ok`
      consistently with `validate.py::_classify`.
- [ ] `python main.py --stage2-validate` (read-only, no writes) reports
      feature/percentile/health/coverage state, styled consistently with
      the existing `--validate` output, and explicitly surfaces the
      historical coverage asymmetry (Binance-only historical taker flow,
      OKX live-only OI).
- [ ] `python main.py --stage2-backfill` builds features and percentile
      history from existing raw history, resumable and idempotent.

### Correctness — mandatory review tests

- [ ] **[R]** Per-exchange features are never mixed: a test asserts that
      no `exchange_feature_vectors` row's values are derived from more
      than one exchange's raw rows.
- [ ] **[R]** Raw OI is never summed across exchanges: a test asserts the
      consensus OI path consumes only per-exchange `oi_change_pct`, and
      fails if any code path sums `oi_raw` across exchanges.
- [ ] **[R]** 2-of-3 coverage produces a correct **partial** consensus
      *(updated 0.2.2 to current schema fields)*:
      `coverage_by_metric["<family>"] == {"available":2,"expected":3,
      "ratio":0.67}`, `is_partial_consensus=true`, aggregates computed
      from the two available venues, and the third listed in
      `provenance_by_metric["<family>"].excluded` with a reason.
- [ ] **[R]** NULL never becomes 0: fixtures with missing bars, NULL taker
      splits, and a missing `contract_multiplier` all yield NULL feature
      values (and a recorded exclusion reason), never `0`.
- [ ] **[R]** LONG and SHORT liquidations are separated *(updated 0.2.2)*:
      `observed_long_/short_liquidation_notional_sum` are distinct, and
      feed provenance survives into the consensus row via
      `liquidation_feed_quality_by_exchange` — **not** via a bare
      `is_snapshot_feed` column, which exists only on the exchange-level
      row.
- [ ] **[R]** Live and historical replay agree: features computed live for
      a period equal, field-for-field, the features produced by
      `--stage2-backfill` over the same period, **compared under the same
      `calculation_version`** *(updated 0.2.2 — comparing across
      calculation versions is meaningless by construction, since a
      different version means different config or code)*.
- [ ] **[R]** Repeated replay is idempotent: running `--stage2-backfill`
      twice over the same range produces identical logical rows (no
      duplicates, no changed values, `computed_at` may differ).
- [ ] **[R]** Restart catch-up: killing the process, letting buckets
      elapse, and restarting recomputes exactly the missed buckets and
      advances the watermark correctly.
- [ ] **[R]** Late-bar correction: upserting a corrected `klines_1m` bar
      inside the correction horizon enqueues and recomputes the containing
      `1m/5m/15m/1h/4h` buckets and the dependent percentile rows.
- [ ] **[R]** Stage 2 crash does not stop Stage 1: injecting a runtime
      exception into the feature listener leaves ingestion writing bars
      uninterrupted, sets Stage 2 to `DEGRADED`, and restarts with bounded
      backoff.
- [ ] **[R]** `stage2.enabled: false` preserves prior behavior byte-for-
      byte (verified by the existing 1h soak procedure from
      `docs/STAGE1_ACCEPTANCE.md` §2 with the flag off; `--validate`
      output unchanged).
- [ ] **[R]** Percentile calculation never uses the current or any future
      bucket: a test asserts `sample_window_end < bucket_ts` for every
      written row, and that the DB `ck_ps_no_lookahead` constraint rejects
      a deliberately-violating insert.
- [ ] **[R]** The `1m` feature-vector scope is explicitly consistent with
      the configured timeframe list: a test asserts `1m` rows are written
      and that the set of written timeframes equals the configured set
      (`STAGE2_SPEC.md` §5.1).

### Correctness — added by Revision 0.2

- [ ] **[R2]** Coverage/provenance/confidence are per metric family: a
      fixture where `price_structure` is 3/3 but `oi` is 2/3 produces
      distinct entries in `coverage_by_metric` / `provenance_by_metric` /
      `data_confidence_by_metric`, and the `oi` entry is **not** improved
      by full price coverage. All six families
      (`price_structure`, `volume`, `taker_flow`, `oi`, `funding`,
      `liquidations`) are present as keys.
- [ ] **[R2]** `volume_raw` carries `volume_raw_unit`, and a test asserts
      no code path sums or percentiles `volume_raw` across exchanges with
      differing units.
- [ ] **[R2]** The five consensus notional sums
      (`volume_/taker_buy_/taker_sell_/taker_delta_notional_usd_sum`,
      `observed_liquidation_event_count_sum`) are present and equal the sum of the
      contributing per-exchange rows, with non-contributing venues
      excluded and recorded.
- [ ] **[R2]** `calculation_version` is deterministic (same three inputs →
      same value) and a config change produces a **new parallel result
      set**: a test computes a bucket under config A, changes config,
      recomputes, and asserts both rows coexist with distinct
      `calculation_version`s and the config-A values are unchanged.
- [ ] **[R2]** Startup double-scan closes the race: a test that forces a
      bucket to close during Scan A asserts it is computed by Scan B (and
      that a bucket computed by both Scan B and the live subscription
      yields one identical row, not a duplicate or a conflict).
- [ ] **[R2]** Queue overflow requeues: forcing a drop-oldest event
      asserts a `stage2_recompute_queue` row with
      `reason='QUEUE_OVERFLOW'` exists and that the reconciliation job
      subsequently computes that bucket.
- [ ] **[R2]** Percentile invalidation range: correcting a bucket at
      `corrected_ts` recomputes exactly the 7d snapshots in
      `(corrected_ts, corrected_ts+7d]` and the 30d snapshots in
      `(corrected_ts, corrected_ts+30d]`, both clamped to `now`, at both
      scopes — and re-running the same correction is idempotent.
- [ ] **[R2]** Instrument metadata is fail-closed: with
      `contract_multiplier` absent for an instrument whose
      `quantity_unit='contracts'`, notional features are NULL, the venue
      is excluded with `MISSING_CONTRACT_MULTIPLIER` in
      `provenance_by_metric["volume"]` and
      `provenance_by_metric["taker_flow"]`, and it is **not** treated as
      base-denominated.
- [ ] **[R2]** Metadata last-known-good + mismatch alarm: a failed refetch
      reuses the stored row and marks `is_stale=true`; a refetch returning
      a different `contract_multiplier` raises the mismatch alarm rather
      than silently overwriting.
- [ ] **[R2]** Bar-close timing: a venue arriving within 5s yields full
      coverage; a venue arriving after 15s yields a partial-coverage
      bucket flagged `LATE_BAR`, and the subsequent late arrival triggers
      a correction that recomputes it at full coverage.

### Correctness — added by Revision 0.2.1

- [ ] **[R2.1]** Health snapshots coexist under two calculation versions:
      computing health for the same (symbol, exchange, metric,
      snapshot_ts) under two configs with different staleness/gap
      thresholds yields **two rows** with different
      `calculation_version` and different `is_stale`/`is_usable`
      verdicts — neither overwriting the other.
- [ ] **[R2.1]** Recompute queue isolates calculation versions: a
      correction enqueued for the active version does **not** enqueue or
      process work for a superseded version, and a `MANUAL` job naming a
      superseded version repairs only that version.
- [ ] **[R2.1]** Percentile range job is idempotent and ranged: a single
      corrected bucket produces **one** `PERCENTILE_INVALIDATION` row per
      (timeframe, window, calculation_version) — not one per affected
      snapshot — and running the job twice over the same range yields
      identical values with no duplicate rows.
- [ ] **[R2.1]** Liquidation availability and feed quality are not
      collapsed: a fixture with all three venues reporting **in a live
      bucket** asserts `coverage_by_metric["liquidations"].available == 3`
      **and** `liquidation_feed_quality_by_exchange` distinguishing
      `snapshot`/`full`/`aggregated`; a disabled venue (Bitget) does not
      appear in the denominator; and the summed fields are named
      `observed_*`.
### Correctness — added by Revision 0.2.2

- [ ] **[R2.2-A]** Historical liquidation bucket is unavailable, not a
      measured zero: for a bucket predating live collection,
      `coverage_by_metric["liquidations"] == {"available":0,"expected":3,
      "ratio":0.0}`, `provenance_by_metric["liquidations"].contributing
      == []` with all three venues excluded as `NO_HISTORICAL_DATA`, and
      `observed_long_/short_liquidation_notional_sum` and
      `observed_liquidation_event_count_sum` are **NULL**, not `0`.
      Contrast case in the same test: a live bucket with healthy feeds
      and no liquidations yields `available == 3` and sums of `0`.
- [ ] **[R2.2-B]** Live liquidation availability is separate from feed
      quality: a live bucket where all three venues report asserts
      `available == 3` **and** that
      `liquidation_feed_quality_by_exchange` still records
      `binance=snapshot`, `bybit=full`, `okx=aggregated` — quality never
      reduces the availability count, and availability never masks
      quality.
- [ ] **[R2.2-C]** Price coverage survives a volume normalization
      failure: with OKX's `contract_multiplier` missing,
      `coverage_by_metric["volume"]` and
      `coverage_by_metric["taker_flow"]` degrade to 2/3 while
      `coverage_by_metric["price_structure"]` remains 3/3 and
      `price_move_pct_median` / `range_width_pct_median` are computed
      from all three venues.
- [ ] **[R2.2-D]** Funding consensus supports consensus-scope
      percentiles: `funding_rate_median` and `funding_rate_mad` are
      populated from the per-exchange rates, and the consensus-scope
      funding percentile is computed over `funding_rate_median` (not over
      any single venue's rate, and not over a pool of the three raw
      rates).
- [ ] **[R2.2-E]** 1/3 historical taker flow produces NULL consensus:
      Binance exchange-level taker/CVD features exist and are non-NULL,
      while `taker_buy_/sell_/delta_notional_usd_sum` and
      `cvd_delta_notional_usd_sum` on the consensus row are **NULL**,
      `coverage_by_metric["taker_flow"]` stays `1/3`, and Binance's value
      is nowhere present in a consensus field.
- [ ] **[R2.2-F]** Acceptance criteria reference only current schema
      fields: a lint/grep check over the test suite and docs asserts no
      remaining use of `exchanges_available`, `exchanges_expected`,
      `excluded_exchanges`, `volume_base`, or a bare
      `liquidation_event_count_sum` outside explicitly historical notes.

### Correctness — recompute-queue dedup (schema-correctness patch)

- [ ] **[R2.2-A]** Duplicate pending broad job is deduplicated:
      enqueueing the same `PERCENTILE_INVALIDATION` job twice while the
      first is still pending yields **one** pending row.
- [ ] **[R2.2-B]** Processed job does not block re-enqueue: after
      `processed_at` is set, enqueueing the identical logical job again
      succeeds and creates a new pending row (a second correction to the
      same range must not be silently swallowed).
- [ ] **[R2.2-C]** NULL `metric`/`scope`/`window` participate in logical
      identity: two jobs with all three NULL are treated as the **same**
      job (this is the case a plain `UNIQUE` got wrong, since SQL NULLs
      are distinct by default), while a job with `window='7d'` and one
      with `window=NULL` remain distinct.
- [ ] **[R2.2-D]** Different `calculation_version` remains isolated: the
      same range/metric/scope/window under two different
      `calculation_version` values yields two independent pending rows.

- [ ] **[R2.1]** Spot/perp raw keys cannot collide: a test asserts that
      writing a spot bar and a perp bar for the same
      (exchange, symbol, ts) targets **distinct storage** — i.e. the
      Phase 1.5 design does not route both into a table whose primary key
      is `(exchange, symbol, ts)`. Until Phase 1.5 exists this is a
      guard test asserting no spot writer targets the Stage 1 raw
      tables.

### Safety / non-regression

- [ ] `python main.py --validate` output is unchanged.
- [ ] No modification to `storage/schema.sql`, `exchange_capabilities`,
      `deploy/signalbot.service`, or `docker-compose.yml`.
- [ ] `symbols` seeded with exactly one row (`BTCUSDT`, `ACTIVE`); no
      other symbol is queried or ingested.
- [ ] Symbol mapper has a test asserting that requesting an unmapped
      symbol **raises** rather than silently falling back to a BTC
      instrument (silent-mislabel prevention, decision F).
- [ ] At least one integration test against a real TimescaleDB via
      `docker-compose.yml`, matching how Stage 1 was verified.

## Risks — REVISED 0.1

- **Volume/taker-flow unit incompatibility (NEW, highest priority).** OKX
  reports volume in contracts while Binance/Bybit report base asset, and
  nothing in the pipeline normalizes this
  (`STAGE2_DATA_AUDIT.md` §8). Any consensus aggregation over raw
  `volume`/`taker_*` would be wrong by ~100× on the OKX leg. Mitigated by
  the **raw+unit vs normalized notional split** (`*_raw` with a companion
  `*_raw_unit`, versus `*_notional_usd`), mandatory `quantity_unit` /
  `contract_multiplier` in `exchange_instruments`, and the
  unit-normalization test — but it must be treated as a correctness
  blocker for the consensus layer, not a nice-to-have.
- **`contract_multiplier` correctness.** A wrong or stale `ctVal` silently
  corrupts every OKX notional feature with no loud failure. Needs the
  source decision (open decision 2) and a mismatch alarm.
- **OKX's hardcoded `"BTC-USDT-SWAP"`** (client + backfill, 3 occurrences)
  — approved for an isolated pre-Stage-2.1 fix (decision F) via a shared
  symbol mapper with mislabel-prevention tests. Until that lands, no
  second symbol may be enabled anywhere.
- **`exchange_capabilities` migration risk — ELIMINATED.** Revision 0.1
  no longer modifies the Stage 1 table at all (decision E); the entire
  Stage 2.1 migration is now purely additive and fully rollback-safe by
  dropping derived tables.
- **Liquidation dedup could make things worse if done naively** — a
  content-based UNIQUE index would drop real cascade events
  (`STAGE2_DATA_AUDIT.md` §10). Mitigated by the evidence-first sequence
  (decision G); the risk is now "we ship without dedup for a while",
  which is acceptable, rather than "we silently lose data".
- **Historical coverage is asymmetric, and could be misread as complete.**
  Taker flow/CVD is Binance-only historically; OKX OI is live-only. A
  bootstrap that reports "30 days built" without qualifying this would
  give false confidence in percentile maturity. The `--stage2-validate`
  report must surface it per metric per exchange.
- **No existing gap-detection code** means `data_health_snapshots` is
  genuinely new engineering, not a thin wrapper over something that
  already exists — should be scoped and estimated as such, not assumed
  to be "just expose the existing gap detector" (there isn't one, see
  `STAGE2_DATA_AUDIT.md` §4).
- **Liquidations have no dedup key.** Not a Stage 2.1 blocker (liquidation
  percentile/consensus logic can tolerate rare double-counts for now), but
  should be fixed before the Percentile Engine's liquidation metrics are
  trusted for anything scoring-related in Phase 3.
- **OKX/Bitget's short historical OI/mark-price coverage** means their
  Percentile Engine warm-up for those specific metrics will lag price by a
  long margin — expected given `STAGE2_DATA_AUDIT.md` §3/§7, not a defect,
  but worth setting expectations that "3/3 coverage" won't apply uniformly
  across all metrics from day one.
- **No spot data exists.** Any Stage 2 detector referencing `spot_cvd` or
  spot/perp divergence is unbuildable until a separate spot-ingestion
  project is scoped and built — this is a scope risk for the overall
  Stage 2 plan (not Stage 2.1 specifically), since several sections of the
  original plan document assume spot data is available.
- **Storage/retention figures in this plan and in the clarifications doc
  are estimates, not measurements** — no live DB access was available
  during this audit. Should be confirmed against the real
  `pg_database_size` before any retention/compression policy is finalized.

## Resolved decisions (Architecture Review 0.1)

| # | Decision | Resolution |
|---|---|---|
| A | Stage2Config location | **Separate `common/stage2_config.py`.** Stage 1's `common/config.py` is not extended or modified |
| B | Worker model | **In-process asyncio listener for BTC-only Stage 2.1**, with mandatory failure isolation (`STAGE2_SPEC.md` §9). No distributed worker pool now |
| C | Spot features | **Not descoped.** Marked `BLOCKED_BY_SPOT_INGESTION`; prerequisite **Phase 1.5 — Spot Ingestion** scheduled before any spot-dependent detector |
| D | Orderbook/spoofing | **Not descoped.** Marked `BLOCKED_BY_ORDERBOOK_INGESTION`; prerequisite **Phase 1.6 — Orderbook Ingestion** as its own phase |
| E | `exchange_capabilities` | **Stage 1 table unchanged.** New purely-additive `symbol_exchange_capabilities` keyed `(exchange, symbol, market_type, metric)` |
| F | OKX hardcode | **Fix before Stage 2.1, isolated commit/PR.** Shared `common/symbol_mapper.py` (`BTCUSDT→BTC-USDT-SWAP`, `ETHUSDT→ETH-USDT-SWAP`, `SOLUSDT→SOL-USDT-SWAP`) used by both live client and backfill, with tests preventing silent mislabeling. **No ETH/SOL ingestion enabled** |
| G | Liquidation dedup | **Required before liquidation percentiles are used.** No naive content-based UNIQUE index — provider payloads must be inspected first for event IDs and timestamp resolution; then a provider-aware fingerprint or bounded reconnect-window model. Raw events are never deleted on insufficient confidence (see §"Liquidation dedup — evidence first") |
| H | Retention/compression | **Not applied.** All values stay draft until real DB size and row-growth are measured |

## Resolved decisions (Revision 0.2)

| # | Decision | Resolution |
|---|---|---|
| I | DB size / growth measurement | **Measure now, and again after 24h.** Two `pg_database_size` + per-table row-count readings 24h apart give both an absolute figure and a real daily growth rate, which is what retention actually needs. Command in `docs/VPS_DEPLOY.md` §12; record both readings in this document when available |
| J | `ctVal` / tick size source | **Fetch-and-store** into `exchange_instruments` from each venue's instruments endpoint, with **last-known-good fallback** (a previously fetched row is reused if the fetch fails, marked `is_stale=true`), a **mismatch alarm** if a refetched value differs from the stored one, and **fail-closed** behavior: no usable multiplier ⇒ that venue is excluded from notional consensus rather than assumed to be base |
| K | Correction horizon | **48h, configurable** (`stage2.correction_horizon`) |
| L | Liquidation payload capture | **Temporary rotating JSONL side-channel, disabled by default** (`stage2.debug.capture_liquidation_payloads`). No Stage 1 schema change; enabled deliberately for a bounded window to gather the evidence decision G needs, with rotation + size cap so it cannot fill the disk |
| M | Bar-close timing | **Soft grace 5s, hard deadline 15s**, both configurable (`STAGE2_SPEC.md` §5.2) |
| N | Notional conversion | **`BAR_CLOSE` approximation accepted for Stage 2.1.** Recorded as an explicit named approximation; switching to exact quote-volume later is a versioned change (alters `calculation_version`) |

### Notes on J (metadata fetch)

The fetch runs at startup and on a configurable refresh interval, **not**
on the hot path. Startup ordering: if the fetch fails and no
last-known-good row exists for an instrument whose `quantity_unit` is
`contracts`, Stage 2 starts in `DEGRADED` for that venue's notional
features rather than refusing to start — Stage 1 ingestion is never gated
on it. The mismatch alarm matters because a silently changed `ctVal` would
corrupt every historical notional comparison; a change should force a
deliberate decision (and, if accepted, a `calculation_version` bump).

### Notes on L (payload capture)

Disabled by default is the important part: this writes raw exchange
payloads to disk, and the production unit runs with
`ProtectSystem=strict` and no writable paths. Enabling it therefore also
requires a deliberate, temporary `ReadWritePaths` addition — which is a
feature, not friction: it makes the capture window explicitly bounded and
visible rather than something left running indefinitely.

## Remaining open decisions

Only two remain, and neither blocks starting Stage 2.1:

1. **Permanent liquidation dedup model** — cannot be decided until the
   payload capture (decision L) produces evidence about provider event IDs
   and timestamp resolution. Sequence is in §"Liquidation dedup — evidence
   first". Blocks: use of liquidation percentiles in scoring (Phase 3),
   not Stage 2.1 itself.
2. **Retention / compression values** (decision H) — stay draft until the
   two measurements from decision I are in hand. Note that
   `calculation_version` retention is now part of this question: how many
   superseded calculation versions to keep, and for how long, is a
   retention decision that did not exist before revision 0.2.
