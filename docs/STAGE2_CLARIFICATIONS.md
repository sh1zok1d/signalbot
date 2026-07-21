# Stage 2 — Clarifications

Consolidated decisions supplementing `docs/STAGE2_SPEC.md` and
`docs/STAGE2_IMPLEMENTATION_PLAN.md`. All threshold values below are
**starting parameters for testing, not final calibration** — everything
must be configurable (see `config/stage2.yaml`, `STAGE2_SPEC.md` §3).

## 1. Entry, invalidation, targets

- **Entry**: only formed after `TRIGGERED`. `entry_reference = close of the
  confirming candle + fee/slippage model` (slippage added for LONG,
  subtracted for SHORT). Using a candle's wick/extreme as entry is
  forbidden (unrealistic backtest). Explanation stores
  `trigger_candle_open_time`, `trigger_candle_close_time`, `raw_entry_price`,
  `modeled_entry_price`, `fee_model`, `slippage_model`. First version uses
  one deterministic entry model (`CONFIRMATION_CLOSE`); `NEXT_BAR_OPEN` /
  `RETEST_LIMIT` are future options.
- **Invalidation**: structural, not a fixed percentage.
  - LONG sweep/reclaim: `sweep_low - protection_buffer`.
  - SHORT sweep/reclaim: `sweep_high + protection_buffer`.
  - Breakout: beyond the confirmed level, or beyond the retest extreme if
    that's a tighter structural boundary.
  - Absorption: beyond the defended extreme.
  - `protection_buffer = max(minimum_tick_buffer, spread_buffer,
    ATR_buffer)`, `minimum_tick_buffer = 3 × tick_size`,
    `ATR_buffer = configurable_fraction × ATR(14)`. If no logical structural
    invalidation can be determined, the event cannot reach `TRIGGERED`.
- **Risk unit**: `R = abs(entry_price - invalidation_price)`. If `R` is
  zero, too small relative to spread, or anomalously large relative to
  current volatility, the signal is blocked. Historical Evaluator tracks
  outcomes at `+0.5R/+1R/+1.5R/+2R/+3R/-1R` independent of the actual
  targets, so different event types compare on one scale.
- **Structural targets**: derived from market structure (session/anchored
  VWAP, range midpoint/boundary, swing/session/day highs-lows, liquidity
  clusters, next confirmed S/R). Hierarchy depends on setup family (e.g.
  LONG sweep/reclaim: T1 = nearest significant level above entry, T2 = next
  structural level, T3 = extended if supported; range breakout: T1 =
  nearest external structural level, T2 = next liquidity level). Each
  target stores `target_type`, `target_price`, `target_distance`,
  `target_r_multiple`, `target_confidence`, `source_timeframe`,
  `level_timestamp`.
- **Minimum R/R**: `minimum_RR = 1.5` (configurable per setup family) —
  required for `TRIGGERED`; otherwise `status=BLOCKED,
  reason=INSUFFICIENT_RISK_REWARD`. A fixed 2R target may be computed by
  the Historical Evaluator as an analytical reference point but must never
  substitute for a missing structural target in a live signal.
- **Outcome evaluation**: per `TRIGGERED` event, track MFE/MAE (% and R),
  `time_to_{0.5R,1R,1.5R,2R,3R,T1,T2,invalidation}`, `T1_hit`, `T2_hit`,
  `invalidation_hit`, `expired_before_resolution`. If target and
  invalidation could both have occurred within one OHLC candle and tick
  sequence isn't available, resolve conservatively or with more granular
  data — never auto-pick the outcome favorable to the strategy.

## 2. Risk-flag severity

Every flag carries `flag_type`, `severity`, `reason`, `detected_at`,
`source_metrics`, `expires_at`. Severity levels: `BLOCK` / `PENALTY` /
`WARNING` / `INFO`.

- **BLOCK** (forbid new `TRIGGERED`): `STALE_DATA`; `DATA_GAP` when it
  touches a required window/metric; `LOW_DATA_COVERAGE` below minimum
  consensus; `LATE_ENTRY`; `MACRO_EVENT` inside a configured lock window.
  Also block (may not be stored as risk flags per se):
  `NO_VALID_INVALIDATION`, `INSUFFICIENT_RISK_REWARD`,
  `NO_PRICE_CONFIRMATION`, `INVALID_EVENT_STATE`.
- **PENALTY** (lower score/confidence, don't block):
  `SPOT_PERP_DIVERGENCE`, `PERP_ONLY_MOVE`, `HTF_CONFLICT`,
  `LOW_LIQUIDITY`, `ORDERBOOK_SPOOF_RISK`, partial `DATA_GAP` not touching
  a required metric, partial coverage reduction.
- **WARNING/INFO**: contextual only (approaching macro event, degraded
  optional external provider, orderbook feature disabled, stale
  ETF/on-chain context not used as a trigger).
- Severity has a default but can be **detector-specific** (e.g.
  `SPOT_PERP_DIVERGENCE` is `PENALTY` for a plain sweep/reclaim but `BLOCK`
  for a setup that depends on confirmed spot demand). Resolved severity +
  reason is stored in the explanation.

## 3. Cadence and computation model

Hybrid: **authoritative** features/signals are computed only on closed
candles (bucket close → cascade to 5m/15m/1h/4h → percentiles → detector →
confirmation/scoring/state machine) — protects against repaint.
**Provisional** (intra-candle, `provisional=true`) calculations may detect
early spikes / update `EARLY` / update active-event monitoring, but can
never transition an event to `TRIGGERED` on their own. Provisional
calculations are optional for Stage 2.1 but the data interfaces must allow
adding them later. Continuous aggregates are used for rollups/history/
backfill/restart-recovery/Historical Evaluator — **not** relied on for the
live authoritative path (a live worker reacts to bucket close directly and
does incremental calculation). Initial latency SLA (operational, not a
market guarantee): bucket finalization ≤5s, feature calc ≤10s, event/state
update ≤15s after close; exceeding it produces `STALE_DATA`. Thresholds are
configurable per provider/metric.

## 4. Gap detection and provider health

Phase 0 must check what Stage 1 already provides (sequence gaps, missing
candles, message lateness, out-of-order handling, WS reconnect tracking,
REST backfill, duplicate handling, provider heartbeat, last-successful-event
timestamp) **before** building a second independent gap detector — see
`STAGE2_DATA_AUDIT.md` §4 for the actual findings (summary: connection-level
health is solid; structured persisted gap detection does not exist yet and
is new Stage 2 work). Stage 2 should reuse a single data-quality contract
from ingestion wherever possible: `DataHealthSnapshot` (`provider`,
`exchange`, `market_type`, `metric`, `last_event_at`, `expected_interval`,
`lateness_ms`, `gap_count`, `largest_gap`, `backfill_status`,
`coverage_window`, `is_stale`, `is_usable`). `DATA_GAP` is only critical
when the gap crosses the window a specific event's calculation needs.
Missing data is never replaced with zero.

## 5. Retention and compression

Phase 0 must measure daily row/disk growth, index size, compression ratio,
query latency, and required backfill depth (see
`STAGE2_IMPLEMENTATION_PLAN.md` "Storage and retention estimate" — measured
only structurally here, real DB size not available during this audit).
Existing production data must not be auto-deleted before that measurement.
Proposed starting policy (not applied): raw trades compress after 1d/retain
30d; raw orderbook snapshots compress after 6h/retain 7–14d (N/A — no
orderbook ingestion exists); raw liquidations compress after 7d/retain 90d;
1m aggregates compress after 7d/retain ≥365d; 5m/15m/1h/4h aggregates and
feature vectors compress after 30d/retain ≥2y; signal events, state
transitions, explanations, historical outcomes retain indefinitely;
provider health/gap logs retain ≥180d. Retention is applied via its own
safely-repeatable migration, never automatically.

## 6. Event deduplication

Each event gets a deterministic `event_key` (symbol, setup_family,
direction, anchor_level_id/zone, source_timeframe, initial_detection_bucket,
market_regime_id) with a DB unique constraint. While an event is
`EARLY`/`ARMED`/`TRIGGERED`, new matching evidence **updates** the existing
event (score, evidence, risk flags, data confidence, confirmation state,
`last_seen_at`) rather than creating a new one; every score/state change is
appended to `signal_score_history`/`signal_state_history`. A new event of
the same type is only allowed after a reset condition: prior event
`INVALIDATED`/`EXPIRED`, price left the anchor zone, a new independent
structural level formed, direction changed, or a configured cooldown
elapsed (structural reset preferred over a timer alone for sweeps).
Starting fallback cooldown for 1m/5m detectors: 15 minutes, configurable.

## 7. Feature flags and configuration

`.env` stays secrets-only (DSN, API keys, environment overrides) — unchanged
from Stage 1's existing convention. Stage 2 parameters (enabled detectors,
feature families, timeframes, percentile windows, score thresholds, risk
severity, latency thresholds, cooldowns, ATR buffers, minimum R/R, provider
requirements, external context settings) live in `config/stage2.yaml`, a
typed config separate from Stage 1's `config/config.yaml` (see
`STAGE2_SPEC.md` §3). Every run/event stores `config_version`,
`config_hash`, `code_version`, `feature_schema_version`, `scoring_version`
for reproducible historical evaluation. No uncontrolled hot reload in the
first version — config changes apply after a verified worker restart or at
a safe bucket boundary; a signal is always computed within exactly one
config version.

## 8. Structured explanation contract

Signal explanation is a versioned structured JSON (not just prose text),
e.g.:

```json
{
  "schema_version": 1,
  "event": {"event_id": "...", "event_type": "LOW_SWEEP_RECLAIM",
            "symbol": "BTCUSDT", "direction": "LONG", "status": "ARMED"},
  "scores": {"setup_score": 68, "flow_quality": 84, "reclaim_quality": 57,
             "data_confidence": 92, "context_alignment": 61},
  "components": [{"family": "ORDER_FLOW", "feature": "taker_sell_percentile_15m",
                   "value": 97.4, "points": 8, "max_points": 10,
                   "reason_code": "EXTREME_SELL_FLOW",
                   "coverage": {"available": 3, "expected": 3}}],
  "confirmations": [], "blockers": [{"code": "NO_CONFIRMED_RECLAIM", "reason": "..."}],
  "risk_flags": [], "levels": {"entry": null, "invalidation": 64210.0, "targets": []},
  "data_quality": {"is_usable": true, "coverage_score": 92, "stale_sources": []},
  "versions": {"config_hash": "...", "code_version": "...", "scoring_version": 1}
}
```

CLI/Telegram human text is generated *from* this JSON; the Historical
Evaluator consumes the same contract rather than re-deriving score meaning.

## 9. Production gates

Telegram never connects on first results. Four gates, each **independent
per symbol** (see §12):

- **Gate 1 — Technical validation**: Stage 1 keeps working; no look-ahead
  bias; no duplicates; replay is deterministic; gaps/stale data correctly
  detected; state transitions valid; targets/invalidation reproducible.
- **Gate 2 — Historical out-of-sample validation**: on data not used to
  tune thresholds. Minimum sample: ≥100 `TRIGGERED` events total, ≥30 per
  admitted setup family, ≥30 calendar days, ≥2 distinct volatility regimes
  (below that, results are preliminary). Evaluate expectancy after
  fees/slippage, hit rate, invalidation rate, MFE/MAE, time-to-target, by
  setup family, by direction, by regime, by score bucket. Hit rate is never
  judged apart from average R/R. Core bar: **positive expectancy after
  fees and slippage**; bootstrap confidence interval desirable; higher
  score buckets must not systematically underperform lower ones (85+
  should not lose to 70–79) — if score isn't monotonic with outcome
  quality, scoring needs recalibration.
- **Gate 3 — Shadow mode**: signals computed live, not sent. ≥14 days
  recommended. Checks live latency, provider degradation, restart
  behavior, dedup, signal frequency, target correctness, live-vs-historical
  pipeline divergence.
- **Gate 4 — Private alerts**: only after Gates 1–3 pass. Not a license for
  auto-trading — auto-trading is out of Stage 2 entirely.

## 10. Additions to Phase 0

Beyond the base Phase 0 checklist: verify existing Stage 1 gap detection
(done, see `STAGE2_DATA_AUDIT.md` §4); verify trade-side classification
availability/quality (done, §3 — live for all 3 active exchanges, historical
only Binance); verify spot trade availability for spot CVD (done, §3 —
**none exists**); analyze daily storage growth (done structurally,
`STAGE2_IMPLEMENTATION_PLAN.md`, real number pending); design
retention/compression (done, §5 above, not applied); design event
fingerprint + unique constraints (done, §6 above + `STAGE2_SPEC.md` §2);
design structured explanation JSON (done, §8 above); choose authoritative
live cadence (done, §3 above); design config versioning (done, §7 above);
exact entry/invalidation/target model per setup family (done, §1 above —
model defined, per-family parameter values still to be tuned in Phase 2/3);
plan a look-ahead-free Historical Evaluator (design done, §1/§9; not built —
Phase 5); quantitative production gates (done, §9); verify restart-safe
recomputation (open — needs a Stage 2.1 integration test, see
Implementation Plan acceptance criteria); define required vs. optional
metrics per detector (deferred to Phase 2, detectors don't exist yet);
risk-flag severity matrix with overrides (done, §2 above).

## 11. Multi-Symbol Architecture

First working Stage 2 version runs **BTC only**; the architecture must not
hardcode `BTCUSDT` anywhere it doesn't already have to (see
`STAGE2_DATA_AUDIT.md` §6 for exactly where it currently does — OKX
client/backfill, `exchange_capabilities`'s missing symbol column). Every
calculation scopes explicitly to `(exchange, market_type, symbol,
timeframe, bucket_timestamp)`.

- **11.1 Symbol registry**: declarative config per symbol (`enabled`,
  `asset_class`, `base_asset`, `quote_asset`, `asset_tier`, lifecycle
  `status`) in the `symbols` table. **Per-instrument exchange metadata**
  (`exchange_instrument_id`, `quantity_unit`, `contract_multiplier`,
  `tick_size`, `price_precision`, `quantity_precision`) lives in the
  separate `exchange_instruments` table, one row per
  (exchange, symbol, market_type), populated by fetch-and-store —
  **not** in the symbol registry and **not** in
  `symbol_exchange_capabilities`, which is metric-level capability only.
  None of it is hardcoded into the Signal Engine.
  See `STAGE2_SPEC.md` §2/§4.
- **11.2 Config inheritance**: `symbol override > asset tier > global
  default`; resolved config (or its hash) stored per event, not just a
  pointer to the global config.
- **11.3 Per-symbol parameters**: minimum/maximum RR, cooldown, ATR
  timeframe/multiplier, tick buffer, spread/liquidity/volume thresholds,
  minimum exchange coverage, percentile windows/min sample size, data
  freshness thresholds, late-entry threshold, event expiry, target search
  distance, score thresholds, risk-flag severity, macro lock behavior —
  all overridable by symbol/tier. BTC-tuned values must never be assumed
  correct for ETH/SOL.
- **11.4 Percentiles isolated by symbol**: scope is (symbol, market_type,
  metric, timeframe, session bucket, historical window); distributions
  across symbols are never mixed. New symbols get a `WARMING_UP` state
  (Data Confidence reduced, `TRIGGERED` forbidden, `EARLY` observation
  allowed) until minimum history accumulates — see §19 warm-up policy.
- **11.5 Database requirements**: every Stage 2 table carries `symbol`
  (feature vectors, percentile snapshots, market contexts, events, signal
  instances/history, risk flags, explanations, targets, historical
  outcomes, provider health, data gaps, evaluation runs). Unique
  constraints include `symbol` explicitly even when `event_key` already
  encodes it. Historical Evaluator queries filter efficiently by symbol.
- **11.6 Event identity**: `event_key` includes `symbol`, `market_type`,
  `setup_family`, `direction`, `anchor_zone`, `source_timeframe`,
  `initial_detection_bucket`. BTC and ETH events can never merge, even with
  identical timing/setup family. Cooldown/reset conditions apply
  per-symbol.

## 12. Independent symbol validation

Gate 1–4 passage by one symbol does **not** transfer to another. Each new
symbol independently passes Gates 1–4; per-symbol historical requirements
(§9) apply per symbol; if a setup family doesn't reach minimum sample for a
given symbol, that family is not approved for Gate 4 on that symbol even if
approved on BTC (approval is stored per `symbol × setup_family × direction
× scoring_version × config_version`). Historical Evaluator's fee/slippage
model is also per-symbol (spread distribution, liquidity, typical slippage,
fees, tick size, order-size assumptions, market type) — never evaluate SOL
with BTC's execution model.

## 13. Structural Level and Target Engine

A dedicated module (`structure/`, see `STAGE2_SPEC.md` §6), not hidden
inside a detector or the Historical Evaluator.

- **13.1 Level types**: local swing high/low, confirmed pivot, range
  high/low/midpoint, session/day/previous-day/weekly high-low, VWAP,
  anchored VWAP, high-volume node (if data available), liquidity cluster,
  confirmed support/resistance zone. Each level: `level_id`, `symbol`,
  `level_type`, `price`, `price_zone_low/high`, `source_timeframe`,
  `created_at`, `last_confirmed_at`, `touch_count`, `rejection_count`,
  `break_count`, `volume_evidence`, `strength_score`, `is_active`,
  `invalidated_at`.
- **13.2 No future-data rule**: a level is only usable for an event after
  its `level_confirmation_timestamp` (never `level_price_timestamp`) — see
  `STAGE2_SPEC.md` §6 for the exact invariant.
- **13.3 Target selection**: Target Selector takes symbol/direction/entry/
  invalidation/setup family/context/active levels, discards
  wrong-direction and stale/invalidated levels, merges nearby levels into
  zones, computes distance/R-multiple/rank, selects T1/T2/(T3). Belongs to
  Phase 2/3, must exist before a full Historical Evaluator is meaningful.

## 14. ATR scope

`ATR(14)` timeframe is not fixed globally — it's set by setup family and
confirmation timeframe (e.g. 1m sweep/reclaim uses ATR(14) on 1m with an
additional 5m check; 5m/15m breakouts use ATR on their own timeframe;
absorption uses ATR on the defended structure's timeframe; higher-timeframe
setups use the confirmation timeframe). Rule: **protection ATR timeframe =
the timeframe on which the invalidation structure is confirmed.**
Explanation stores `atr_value`, `atr_period`, `atr_timeframe`,
`atr_multiplier`, `minimum_tick_buffer`, `spread_buffer`,
`final_protection_buffer`. Per-symbol/per-setup overrides supported via
config (`detectors.<name>.symbol_overrides.<SYMBOL>.atr_multiplier`, etc.).

## 15. Multi-symbol latency

Current SLA (§3) is a **BTCUSDT-only baseline**; adding symbols requires a
separate load test measuring per-symbol/per-timeframe latency, queue depth,
DB query duration, CPU/memory, worker utilization, percentile/event
evaluation duration. Partition key = `symbol + market_type`; events within
one partition process sequentially, different partitions may run in
parallel; a heavy SOL backfill must never block live BTC processing —
historical jobs and live workers need separate queues/resource limits. New
SLAs are defined after each new symbol's load test, not assumed in advance.
See `STAGE2_SPEC.md` §5 for why Stage 2.1 doesn't need this yet (nothing to
partition at one symbol) and clarifications §21 for the staged scaling plan
(1–3 symbols: single process; 4–20: multiple processes + shared queue;
20+: horizontal split + sticky routing + separate live/historical
deployments) — a reference plan, not something to build prematurely.

## 16. Cross-symbol independence

In the first version, every setup is scored independently per symbol.
Future cross-asset context (BTC impulse/volatility shock/direction
agreement, ETH-or-SOL/BTC relative strength, market-wide liquidation
events) is a separate `CROSS_ASSET_CONTEXT` feature family, out of Stage
2.1 scope. Until it's built, implicit dependencies like "BTC drops →
automatically lower all SOL LONG scores" are forbidden — any future
cross-symbol influence must be explicit, explainable, and recorded in the
structured explanation JSON.

## 17. Additions to Phase 0 (multi-symbol)

Covered by `STAGE2_DATA_AUDIT.md` §6 and this audit's file lists: checked
the whole codebase for hardcoded `BTCUSDT`/`BTC-USDT-SWAP` (found — OKX
client + backfill, 3 occurrences); checked whether `symbol`/`market_type`
are part of required primary/unique keys (raw tables: yes already;
`exchange_capabilities`: no, needs migration); symbol registry schema
proposed (`STAGE2_SPEC.md` §2); config inheritance proposed (§3 there);
percentile-cache isolation by symbol confirmed as a *design* requirement
(nothing to check in existing code — percentiles don't exist yet);
cooldown/event-state isolation by symbol — same, design-only at this
stage; Structural Level Engine proposed (§6); Target Selector interface
proposed (no-look-ahead invariant documented); ATR timeframe per setup
family defined (§14 above); per-symbol validation state designed (§12);
load-test plan proposed (§15/§21); components requiring change before
ETH/SOL are listed explicitly (`STAGE2_DATA_AUDIT.md` §6). ETH/SOL are
**not** connected to production ingestion or signals as part of this
audit or Stage 2.1.

## 18. Symbol lifecycle

`symbols.enabled`/`status` govern both new computation and the fate of
already-open events. States: `ACTIVE`, `DRAINING`, `DISABLED`, `DELISTED`,
`DATA_UNAVAILABLE` — full behavior table in `STAGE2_SPEC.md` §4. `DISABLED`
behavior is configurable (`symbol_disable_policy: drain` default, or
`force_expire`). `DELISTED` forces `EARLY`/`ARMED` to `EXPIRED` and
`TRIGGERED` to `EXPIRED`/`UNRESOLVED` with reason `SYMBOL_DELISTED` — never
treated as an ordinary invalidation. `DATA_UNAVAILABLE` blocks new
`TRIGGERED`, preserves active events, and pauses/separately-tracks state
timeouts; if price ordering during the outage can't be determined
reliably, outcome = `UNRESOLVED_DATA_GAP` rather than guessing target vs.
invalidation. Every status change is logged to `symbol_status_history`
(`symbol`, `previous_status`, `new_status`, `reason`, `changed_at`,
`changed_by`, `config_version`).

## 19. Warm-up policy

Explicit and configurable, not implicitly tied to percentile-window
existence:

```yaml
warmup:
  minimum_calendar_days: 7
  minimum_complete_buckets: {1m: 9000, 5m: 1800, 15m: 600, 1h: 150}
  preferred_calendar_days: 30
  minimum_metric_coverage: 0.95
  minimum_exchange_coverage: 2
```

States: `COLD` (all signal states forbidden) → `WARMING_UP` (features
compute, `EARLY` allowed for diagnostics only) → `MINIMUM_READY` (`EARLY`/
`ARMED` allowed; `TRIGGERED` allowed only with reduced Data Confidence if a
separate config flag opts in — **default for the first production version
is `TRIGGERED` forbidden until `FULLY_READY`**) → `FULLY_READY` (full
detector/scoring) → `DEGRADED` (previously-ready symbol lost required data
quality; new `TRIGGERED` blocked/limited, existing events keep tracking).
Warm-up is computed **per** symbol × market_type × metric family ×
timeframe × provider coverage — a symbol is never "fully ready" overall
just because price history is complete while OI or taker-flow history
isn't; every detector must declare its required feature families.

## 20. Structural Level Strength (design item, not finalized)

`strength_score` is explicitly *not* considered settled. A future
`STRUCTURAL_LEVEL_STRENGTH_MODEL` design item (Phase 2/3) will weigh touch
count, rejection count, break-and-reclaim history, volume at level, time
spent near level, rejection distance, recency, source timeframe,
cross-exchange agreement, session significance, independent confirmation
count, level age, and volatility-adjusted zone width — explicitly **not**
"more touches = always stronger" (repeated tests can exhaust liquidity
instead of confirming it). Before that model is approved: versioned
algorithm; separate level-formation features from post-confirmation
features; no future data; breakdown stored in the explanation JSON; feature
ablation in the Historical Evaluator; compare multiple ranking variants;
`strength_score` must never generate a signal by itself. Until approved,
use a small, deterministic, explainable baseline.

## 21. Worker pool scaling plan

Phase 0 prepares a scaling *plan*, not full horizontal scaling (see
`STAGE2_SPEC.md` §5 for why Stage 2.1 needs none of this at BTC-only
scale). Base partition key `symbol + market_type`; guarantees: one
partition processes sequentially, different partitions may run in
parallel, bucket-timestamp order within a partition is preserved, redelivery
is idempotent. Logical pipeline: `Bucket Finalizer → Partitioned Work Queue
→ Feature Workers → Event/Scoring Workers → State Persistence`. Historical
jobs (replay, large backfill, percentile rebuild, new-symbol bootstrap) get
a separate queue/resource limits so they can never block live BTC
processing. To define once actually needed: initial/max worker count, DB
connection pool size, connections per worker, queue implementation,
partition ordering mechanism, retry policy, dead-letter handling,
backpressure, graceful shutdown, crash recovery. Reference scaling
thresholds: 1–3 symbols → one process, partitioned worker pool; 4–20 →
multiple processes + shared partitioned queue + DB concurrency limit; 20+ →
horizontal split + sticky routing by partition key + separate live/
historical deployments. A reference, not a preemptive build requirement.

## 23. Exact feature contract (Revision 0.1)

Binding definitions for every Stage 2.1 feature. Nothing here may be
implemented "approximately" — where a value cannot be computed exactly, the
column is NULL and the reason is recorded, never substituted.

### 23.0 Global rules

1. **NULL ≠ 0.** A missing source row, a NULL taker split, or an
   unconvertible unit all produce NULL. Zero means "measured, and it was
   zero". This mirrors Stage 1's existing discipline
   (`taker_buy_volume` is left NULL for non-Binance backfilled bars).
2. **No cross-exchange aggregation of raw quantities.** Consensus operates
   on notional USD, percentage changes, direction signs, and percentile
   ranks. Raw OI is never summed; raw base/contract volume is never summed
   (see `STAGE2_DATA_AUDIT.md` §8).
3. **Unit tagging is mandatory.** The normative model (corrected in
   revision 0.2.2 — the earlier wording required exchange-denominated
   quantities to be named `*_base`, which is exactly the false unit
   assertion this rule exists to prevent):
   - a **raw quantity** is named `*_raw` and carries a companion
     `*_raw_unit` column stating its actual unit (`base` | `contracts`);
   - a **normalized comparable quantity** is named `*_notional_usd`;
   - **raw quantities of differing units are never aggregated** — not
     summed, not averaged, not pooled into one percentile distribution.
   No column name may assert a unit that is not guaranteed true for every
   venue writing to it.
4. **Notional conversion** for an exchange reporting in contracts requires
   `contract_multiplier` from `exchange_instruments`. If it is NULL, the
   notional column is NULL and the exchange is listed in that metric
   family's `provenance_by_metric[...].excluded` with reason
   `MISSING_CONTRACT_MULTIPLIER` — it is **not** silently treated as base.
   This is **fail-closed**: a missing multiplier removes a venue from
   notional consensus rather than degrading the number silently.
5. **Minimum coverage, per metric family.** A consensus value for a family
   is emitted when that family's `available >=
   consensus.price_oi_orderflow_min` (currently 2, from Stage 1's
   `config.yaml`), and flagged `is_partial_consensus=true` when
   `available < expected`. Below the minimum, that family's consensus
   value is NULL — never a single-exchange value dressed up as consensus.
   **Coverage is resolved independently per family** (§23.2a); a strong
   price coverage never masks weak OI coverage.

### 23.1 Per-feature contract

Abbreviations: **Src** = source table; **Hist** = historical availability
over the existing ~30d backfill.

---

**`price_move_pct`** — exchange level
- Src: `klines_1m` (or the matching `klines_{tf}` continuous aggregate)
- Columns: `open`, `close`
- Formula: `(close_last - open_first) / open_first * 100` over the bucket
- Units: percent
- NULL if: no bar in bucket, or `open_first = 0`
- Min coverage: 1 exchange (it is a per-exchange feature)
- Aggregation: consensus uses **median** across exchanges + direction
  agreement on `sign()`
- Hist: full 30d for binance/bybit/okx

**`range_width_pct`** — exchange level
- Src: `klines_1m` / `klines_{tf}`
- Columns: `high`, `low`, `open`
- Formula: `(max(high) - min(low)) / open_first * 100`
- Units: percent
- NULL if: no bar in bucket, or `open_first = 0`
- Aggregation: consensus **median**
- Hist: full 30d

**`volume_raw`** + **`volume_raw_unit`** — exchange level, **NOT
cross-exchange comparable** *(renamed from `volume_base` in revision 0.2 —
the old name asserted a unit that is false for OKX)*
- Src: `klines_1m`, `exchange_instruments`
- Columns: `volume`; `quantity_unit`
- Formula: `volume_raw = sum(volume)`;
  `volume_raw_unit = exchange_instruments.quantity_unit`
- Units: **whatever that venue reports** — `base` for
  binance/bybit/bitget, **`contracts` for OKX**
  (`STAGE2_DATA_AUDIT.md` §8). The unit travels with the value in its own
  column so no reader can mistake it
- NULL if: no bar in bucket. `volume_raw_unit` NULL if instrument
  metadata is missing
- Aggregation: **forbidden.** Stored for audit/debug/reconciliation only;
  never summed, averaged, or percentiled across exchanges
- Hist: full 30d

**`volume_notional_usd`** — exchange level, comparable
- Src: `klines_1m` + `exchange_instruments`
- Columns: `volume`, `close`, `quantity_unit`, `contract_multiplier`
- Formula:
  - `quantity_unit='base'` → `sum(volume_i * close_i)` per 1m bar, summed
    over the bucket
  - `quantity_unit='contracts'` → `sum(volume_i * contract_multiplier * close_i)`
- Units: USD
- NULL if: any required input NULL, or `quantity_unit='contracts'` and
  `contract_multiplier IS NULL` (**fail-closed** — the exchange is
  excluded from notional consensus with reason
  `MISSING_CONTRACT_MULTIPLIER`, never assumed to be base)
- **Accepted approximation (decided, revision 0.2): `BAR_CLOSE`.** The
  bar's close is used as the price for that bar's volume; true per-bar
  VWAP is not stored by Stage 1. Error is bounded by intra-bar range and
  is acceptable at 1m granularity. The approximation identifier
  `BAR_CLOSE` is recorded in the feature documentation and in the
  explanation contract, so a later switch to exact quote-volume is a
  visible, versioned change (it would alter `calculation_version`).
  Revisit during the spot-ingestion phase, when the ingestion layer is
  being modified anyway
- Aggregation: consensus **sum** → `volume_notional_usd_sum`
- Hist: full 30d

**`taker_buy_notional_usd`** / **`taker_sell_notional_usd`** — exchange level
- Src: `klines_1m` + `exchange_instruments`
- Columns: `taker_buy_volume` / `taker_sell_volume`, `close`,
  `quantity_unit`, `contract_multiplier`
- Formula: as `volume_notional_usd`, on the respective taker column
- Units: USD
- NULL if: taker split is NULL (**all non-Binance backfilled history** —
  Stage 1 correctly left these NULL rather than faking them), or unit
  conversion unavailable
- Aggregation: consensus **sum**, subject to the minimum-coverage rule
  (§23.0 rule 5 and §23.1a below)
- Hist: **live-only for bybit/okx**; Binance has historical taker split.
  This is the single biggest historical-coverage constraint in Stage 2.1 —
  cross-exchange taker-flow percentiles only become meaningful after
  enough live history accumulates. The percentile confidence-tier thresholds
  (span-based; default `none_below_days=3`) are frozen in `STAGE2_SPEC.md` §12
  and sourced from Stage 2 config (`defaults.percentiles.confidence_tiers`), NOT
  the Stage 1 `percentiles.*` block. Warm-up must be evaluated **per metric
  family**, exactly
  as clarifications §19 requires

### 23.1a Historical taker flow: one venue is not a consensus (revision 0.2.2)

For historical buckets, taker-flow coverage is **1/3** (Binance only) and
the consensus minimum is **2**. The required behavior, stated explicitly
because the temptation to "just use Binance" is real:

| Layer | Behavior |
|---|---|
| `exchange_feature_vectors` (binance) | taker buy/sell/delta and CVD delta **are computed and stored normally** — the data is real and per-exchange percentiles over Binance's own history are valid |
| `exchange_feature_vectors` (bybit, okx) | NULL for those fields (no historical split exists) |
| `consensus_feature_vectors` taker fields | **NULL** — `taker_buy_notional_usd_sum`, `taker_sell_notional_usd_sum`, `taker_delta_notional_usd_sum`, `cvd_delta_notional_usd_sum` are all NULL |
| `coverage_by_metric["taker_flow"]` | stays `{"available":1,"expected":3,"ratio":0.33}` — **not** rounded up, not relabelled |
| `provenance_by_metric["taker_flow"]` | `{"contributing":["binance"],"excluded":{"bybit":"NO_HISTORICAL_TAKER_SPLIT","okx":"NO_HISTORICAL_TAKER_SPLIT"}}` |
| `data_confidence_by_metric["taker_flow"]` | reflects the 1/3 shortfall (low or 0) |

**Binance's single-venue value must never be written into a consensus
field.** A consensus row asserts cross-exchange agreement; a
single-venue number carrying that label would let a downstream consumer
believe three venues agreed when only one reported. The exchange-level
row remains fully available to anyone who genuinely wants Binance-only
taker flow — they read it from the exchange layer, where its provenance
is unambiguous.

The same rule applies to any family that falls below the consensus
minimum for any reason, not just taker flow historically.

**`taker_delta_notional_usd`** — exchange level
- Formula: `taker_buy_notional_usd - taker_sell_notional_usd`
- Units: USD (signed)
- NULL if: either side NULL
- Aggregation: consensus **sum** + direction agreement on `sign()`
- Hist: as taker components

**`cvd_delta_notional_usd`** — exchange level
- Src: derived from `taker_delta_notional_usd`
- Formula: sum of per-1m `taker_delta_notional_usd` across the row's own
  timeframe window (i.e. the CVD *change* over that window)
- Units: USD (signed)
- NULL if: any constituent 1m delta is NULL **and** the gap exceeds the
  allowed missing-bar tolerance; otherwise computed over present bars with
  `bars_present`/`bars_expected` recorded
- **Never a running accumulator** — see `STAGE2_SPEC.md` §7
- Aggregation: consensus **sum**
- Hist: as taker components

**`oi_change_pct`** — exchange level, **per exchange only**
- Src: `open_interest`
- Columns: `oi_raw`, `oi_unit`
- Formula: `(oi_last - oi_first) / oi_first * 100` within the bucket,
  computed **only between rows of the same exchange with the same
  `oi_unit`**
- Units: percent
- NULL if: fewer than 2 OI observations in the bucket, `oi_first = 0`, or
  `oi_unit` differs between the two observations (a unit change mid-window
  means the series is not continuous — do not compute across it)
- **Raw OI is never summed across exchanges** — this is why the feature is
  a percentage change, not a level
- Aggregation: consensus **median of the per-exchange percentage changes**
  + direction agreement on `sign()`
- Hist: binance ~29d23h, bybit 30d, **okx live-only** (no verified
  historical endpoint) — so OI consensus during bootstrap will frequently
  be 2/3, correctly flagged partial

**`funding_rate`** — exchange level
- Src: `funding_rate`; Columns: `funding_rate`
- Formula: last value at or before bucket end
- Units: rate (dimensionless) — **directly comparable across venues with
  no normalization step**, unlike volume/taker flow
- NULL if: no observation in or before the bucket
- Aggregation: consensus **median** → `funding_rate_median`, with
  `funding_rate_mad` as the dispersion measure. The **consensus-scope
  funding percentile is computed over `funding_rate_median`**, never over
  any single venue's rate and never over a pool of the three venues' raw
  rates
- Min coverage: 2 venues for a consensus median, per §23.0 rule 5
- Hist: full 30d all venues (`funding` is one of only two families —
  with `price_structure` — at full historical coverage)

**`long_liquidation_notional`** / **`short_liquidation_notional`** — exchange level
- Src: `liquidations`
- Columns: `side`, `notional`, `is_snapshot_feed`
- Formula: `sum(notional) FILTER (WHERE side='long')` and `...='short'`
- Units: USD
- NULL vs 0 — **important distinction**: `0` where the feed is healthy and
  genuinely had no liquidations; `NULL` where the feed is
  `unavailable`/disconnected for that bucket. A quiet feed is not a broken
  feed (Stage 1's `validate.py` already encodes this rule and it carries
  forward unchanged)
- Aggregation: consensus **sum** into `observed_long_/short_liquidation_
  notional_sum`, with per-exchange `coverage_type` carried alongside in
  `liquidation_feed_quality_by_exchange`. A rate-capped Binance feed and
  a full Bybit feed are never silently averaged, and the result is
  documented as a **lower bound**, not a market total (§23.2b,
  `STAGE2_DATA_AUDIT.md` §9)
- Hist: **live-only, never backfilled** (Stage 1 rule, unchanged).
  Liquidation percentiles are therefore only meaningful over accumulated
  live history

**`liquidation_event_count`** — exchange level
- Formula: `count(*)` per bucket per exchange
- Units: count; NULL/0 semantics as above
- Aggregation: consensus **sum**, provenance preserved

### 23.2 Consensus-level contract

| Field | Formula | Notes |
|---|---|---|
| `*_direction_agreement` | `max(count(sign>0), count(sign<0)) / available` for that family | unit-free, safe across venues |
| `*_median` | median of per-exchange normalized values | robust to one bad venue |
| `*_mad` | median absolute deviation | dispersion measure |
| `funding_rate_median` | median of per-exchange `funding_rate` | funding is a dimensionless rate — directly comparable, no normalization needed |
| `funding_rate_mad` | MAD of per-exchange `funding_rate` | venue divergence in funding is itself informative |
| `volume_notional_usd_sum` | sum of per-exchange `volume_notional_usd` | notional is additive |
| `taker_buy_notional_usd_sum` | sum of per-exchange `taker_buy_notional_usd` | buy pressure |
| `taker_sell_notional_usd_sum` | sum of per-exchange `taker_sell_notional_usd` | sell pressure |
| `taker_delta_notional_usd_sum` | sum of per-exchange `taker_delta_notional_usd` | net aggression |
| `cvd_delta_notional_usd_sum` | sum of per-exchange `cvd_delta_notional_usd` | |
| `observed_long_/short_liquidation_notional_sum` | sum per direction across reporting venues | **lower bound**, see §23.2b |
| `observed_liquidation_event_count_sum` | sum of per-exchange event counts | lower bound |
| `liquidation_feed_quality_by_exchange` | `{exchange: coverage_type}` | quality reported beside the sum, never folded into it |
| `outlier_exchanges` | exchanges whose value deviates > configured MAD multiple | recorded, not silently dropped |
| `consensus_confidence` | function of coverage, agreement and dispersion (weights configurable; initial proposal coverage 50% / agreement 30% / inverse-dispersion 20%) | 0..100 |
| `is_partial_consensus` | any family has `available < expected` | |

The four `*_sum` notional fields plus the liquidation sums are what make
buy/sell pressure assessable on 5m/15m/1h without a consumer having to
re-aggregate per-exchange rows itself (revision 0.2 requirement).

### 23.2a Per-metric-family coverage, provenance and confidence (revision 0.2)

A single global `exchanges_available` was wrong for this venue set. On
BTCUSDT across binance/bybit/okx the families genuinely differ.

**The six families (revision 0.2.2):**

| Family | Members | Live coverage | Historical coverage | Why |
|---|---|---|---|---|
| `price_structure` | `price_move_pct`, `range_width_pct`, `close_price` | **3/3** | **3/3** | percentages from OHLC alone — no unit normalization involved |
| `volume` | `volume_raw`, `volume_notional_usd` | **3/3** | **3/3** | needs `contract_multiplier` for OKX notional |
| `taker_flow` | taker buy/sell/delta notional, CVD delta | **3/3** | **1/3** | only Binance carries a historical taker split |
| `oi` | `oi_change_pct` | **3/3** | **2/3** | OKX has no verified 30d historical OI endpoint |
| `funding` | `funding_rate` | **3/3** | **3/3** | full live + historical everywhere |
| `liquidations` | observed long/short notional, event count | **3/3 available**, mixed quality | **0/3** | never backfilled (Stage 1 rule); quality differs live (§23.2b) |

**Why `volume` is separated from `price_structure` (0.2.2).** They were
previously one `price` family, which was wrong: a missing
`contract_multiplier` breaks notional normalization and legitimately
degrades `volume` and `taker_flow`, but `price_move_pct` and
`range_width_pct` are percentages derived from OHLC and are entirely
unaffected by any unit problem. With the families merged, a units issue
on one venue would have silently suppressed perfectly good price
coverage — and any detector gated on price structure would have been
blocked for no real reason.

Collapsing families into one number would either overstate
OI/liquidation confidence or understate price confidence — and a detector
that needs OI would be gated on the wrong figure.

Therefore `consensus_feature_vectors` stores three JSONB maps keyed by
family:

- `coverage_by_metric` — `{"available", "expected", "ratio"}` per family.
  **This is bucket-level**: `available` counts venues that supplied
  usable data *for this bucket*, not venues that possess such a feed in
  principle. `expected` is counted dynamically from
  `symbol_exchange_capabilities` (`enabled AND live_supported` for that
  family's metrics), never hardcoded.
- `provenance_by_metric` — `{"contributing": [...], "excluded":
  {exchange: reason}}` per family. Exclusion reasons are explicit
  (`NO_HISTORICAL_DATA`, `NO_HISTORICAL_OI`,
  `NO_HISTORICAL_TAKER_SPLIT`, `MISSING_CONTRACT_MULTIPLIER`,
  `LATE_BAR`, `FEED_UNAVAILABLE`, `STALE`).
- `data_confidence_by_metric` — 0..100 computed **independently per
  family** from that family's own coverage, agreement, dispersion and
  freshness.

**Three distinct concepts, never conflated** (0.2.2):

| Concept | Where it lives | Answers |
|---|---|---|
| Live capability | `symbol_exchange_capabilities` | does this venue have such a feed at all? |
| Bucket coverage | `coverage_by_metric` | did this venue supply usable data **for this bucket**? |
| Feed quality | `liquidation_feed_quality_by_exchange` | how complete is the data it does supply? |

The clearest case where they diverge is liquidations in a historical
bootstrap bucket: capability is 3/3 (all venues have live feeds), quality
is `snapshot`/`full`/`aggregated`, and bucket coverage is **0/3** —
because liquidations are never backfilled, so no venue supplied anything
for that bucket. See §23.2c.

Rule for consumers: **a decision that depends on a metric family must read
that family's entry.** The rolled-up `data_confidence_overall` and
`min_coverage_ratio` exist for reporting and triage only; using them as a
gate for a family-specific decision is a defect. When Phase 3 scoring
arrives, each detector declares its required families (§19) and is gated
on exactly those.

### 23.2b Liquidation availability vs. feed quality (revision 0.2.1)

These are **two orthogonal properties** and must never be collapsed into
one ratio.

**Availability** — does the venue provide a live liquidation feed at all?
Across the active set (binance, bybit, okx):

```
live liquidation availability = 3/3 active venues
```

Bitget is **not** in the denominator. It is disabled
(`config.enabled_exchanges`), and a disabled venue is excluded from
coverage entirely — the same rule Stage 1's `validate.py` already
applies. Describing liquidation coverage as "2/3 effective because of
Bitget" was wrong on two counts: Bitget isn't in the active set, and the
shortfall being described was actually about *quality*, not availability.

**Quality** — how complete is each feed?

| Venue | Availability | `coverage_type` | What it means |
|---|---|---|---|
| Binance | available | `snapshot` | rate-capped ~1 event/symbol/1000ms; **under-counts cascades** |
| Bybit | available | `full` | real-time, complete |
| OKX | available | `aggregated` | batched/delayed |

So the correct statement is: **availability 3/3, with one full feed, one
rate-capped feed and one aggregated feed.** Both facts are carried into
the consensus row — availability via `coverage_by_metric["liquidations"]`,
quality via `liquidation_feed_quality_by_exchange` — and neither is
allowed to overwrite the other.

**Why the sums are named `observed_*`.** Because two of the three feeds
are lossy by construction, the summed notional is a
**provenance-aware lower bound on liquidations our feeds saw**, not the
market's true liquidation total. Concretely:

- It is *not* comparable to an external aggregated market total
  (CoinGlass and similar) without an explicit normalization step —
  such a comparison would read the shortfall as a market signal when it
  is a measurement artifact.
- It *is* internally consistent over time for percentile purposes, since
  the same feeds with the same caps produce the same bias in every
  bucket — which is why percentiles over `observed_*` are meaningful
  even though the absolute level is biased low.
- Any future external-provider integration (Phase 4) that compares these
  numbers must do so through a declared normalization, and that
  normalization must appear in the explanation JSON.

### 23.2c Liquidations in historical buckets: unavailable, not zero (revision 0.2.2)

Liquidations are **never backfilled** — this is a Stage 1 rule
(`schema.sql`: *"absence of rows for a period means absence of data, not
zero liquidations"*), and it carries forward unchanged.

Consequence for any bucket older than the start of live collection:

| Field | Value | Not |
|---|---|---|
| `coverage_by_metric["liquidations"].available` | `0` | ~~3~~ |
| `coverage_by_metric["liquidations"].expected` | `3` | |
| `coverage_by_metric["liquidations"].ratio` | `0.0` | |
| `provenance_by_metric["liquidations"].contributing` | `[]` | |
| `provenance_by_metric["liquidations"].excluded` | `{"binance":"NO_HISTORICAL_DATA","bybit":"NO_HISTORICAL_DATA","okx":"NO_HISTORICAL_DATA"}` | |
| `observed_long_liquidation_notional_sum` | **`NULL`** | ~~`0`~~ |
| `observed_short_liquidation_notional_sum` | **`NULL`** | ~~`0`~~ |
| `observed_liquidation_event_count_sum` | **`NULL`** | ~~`0`~~ |
| `data_confidence_by_metric["liquidations"]` | `0.0` | |

The NULL-vs-zero distinction is the whole point: `0` would assert *"we
measured this period and the market liquidated nothing"*, which for a
30-day-old bucket is simply false. A percentile distribution built over
thousands of fake zeros would then rank any real liquidation as extreme,
producing exactly the spurious signal this project's rules exist to
prevent.

Note the contrast with a **live** bucket where feeds are healthy and no
liquidation happened: there `available = 3` and the sums are genuinely
`0` — measured, and it was zero. Stage 1's `validate.py` already draws
this same line ("a quiet feed is not a stale feed"); Stage 2 inherits it.

### 23.3 Percentile scoping

- **exchange scope**: distribution of one exchange's own history for that
  metric/timeframe/window. Binance, Bybit and OKX distributions are
  **never pooled**.
- **consensus scope**: distribution of the *consensus series itself* (which
  is already normalized) over its own history — not a concatenation of
  per-exchange raw values.
- Both scopes record `sample_window_start`/`sample_window_end`, and the
  `ck_ps_no_lookahead` constraint enforces `sample_window_end <
  bucket_ts` at the database level. Percentile rank for a bucket is
  computed **strictly from earlier buckets**; the current and all future
  buckets are excluded by construction.

## 24. Blocked roadmap items (not descoped)

Per review decisions 10-C and 10-D, these remain on the Stage 2 roadmap
with explicit markers and named prerequisite phases:

- `BLOCKED_BY_SPOT_INGESTION` — spot CVD, spot/perp divergence,
  spot-confirmed demand setups, and the `SPOT_PERP_DIVERGENCE` risk flag's
  BLOCK-severity variant (§2). Prerequisite: **Phase 1.5 — Spot
  Ingestion** (`STAGE2_IMPLEMENTATION_PLAN.md`).

Schema-correctness patch (post-0.2.1, no architectural change):
`stage2_recompute_queue` dedup replaced with a **partial unique index
scoped to `WHERE processed_at IS NULL`** using `NULLS NOT DISTINCT` (with
a `COALESCE` expression-index equivalent documented as a fallback) — the
previous table-level `UNIQUE` neither deduplicated broad jobs (SQL NULLs
are distinct by default, so `metric`/`scope`/`window` = NULL never
collided) nor permitted re-enqueue after completion (a processed row
blocked the same logical job forever). Stale normative text also
corrected: the liquidation-coverage comment in `STAGE2_SPEC.md` now reads
availability 3/3 across active venues with quality tracked separately,
the `coverage_by_metric` example shows liquidations `available=3,
expected=3`, and the remaining stale identifiers were updated
(`volume_base` → `volume_raw`, `liquidation_event_count_sum` →
`observed_liquidation_event_count_sum`, instrument metadata attributed to
`exchange_instruments` rather than `symbol_exchange_capabilities` or the
symbol registry). Historical mentions of the superseded names remain only
where the text explicitly identifies them as the previous, incorrect
version.

Revision 0.2.2 (semantic-contradiction cleanup, no new architecture):
bucket-level coverage separated from live capability and from feed
quality — three distinct concepts, with liquidations in a historical
bootstrap bucket now correctly `available=0`, all venues excluded as
`NO_HISTORICAL_DATA`, and `observed_*` sums NULL rather than a measured
zero (§23.2c); metric families split from four into **six**
(`price_structure`, `volume`, `taker_flow`, `oi`, `funding`,
`liquidations`) so a missing `contract_multiplier` degrades only `volume`
and `taker_flow` and never `price_structure` (§23.2a); funding consensus
contract added (`funding_rate_median`, `funding_rate_mad`, with the
consensus-scope funding percentile computed over the median) (§23.2,
§23.1); historical taker-flow behavior fixed so that 1/3 coverage yields
NULL consensus values while Binance's exchange-level features remain
available and are never passed off as consensus (§23.1a); the
unit-tagging rule corrected to `*_raw` + `*_raw_unit` versus
`*_notional_usd`, dropping the requirement that exchange-denominated
quantities be named `*_base` (§23.0 rule 3); the inaccurate claim that
Stage 2 `symbol` columns already have a foreign-key target removed, with
FKs deferred pending TimescaleDB integration testing
(`STAGE2_SPEC.md` §4); and acceptance criteria rewritten onto current
schema fields (per-family maps, `liquidation_feed_quality_by_exchange`,
same-`calculation_version` replay comparison)
(`STAGE2_IMPLEMENTATION_PLAN.md`).
- `BLOCKED_BY_ORDERBOOK_INGESTION` — orderbook imbalance, limit walls,
  wall persistence/execution/cancellation/refill, distance-from-price,
  spoof risk, and the `ORDERBOOK_SPOOF_RISK` flag. Prerequisite:
  **Phase 1.6 — Orderbook Ingestion**.

Until their prerequisite phase ships, any detector depending on these
must declare the dependency in its required-feature-families list (§19)
and will simply not be admitted — rather than running on substituted or
absent data.

## 25. Status (Phase 0 + Architecture Review 0.1)

Active production symbol remains **BTCUSDT only**; ETH/SOL live ingestion
and signal processing are **not** connected as part of this audit or this
review. Stage 2.1 is **not implemented** — this document, together with
`STAGE2_SPEC.md`, `STAGE2_IMPLEMENTATION_PLAN.md`, and
`STAGE2_DATA_AUDIT.md`, is documentation-only output awaiting a separate
go-ahead before any code is written. No production code, systemd unit,
ingestion path, or database was modified to produce these documents.

Revision 0.1 incorporated: two-level exchange/consensus feature model
(§23, `STAGE2_SPEC.md` §2); exact feature contract with units and NULL
semantics (§23); CVD delta model replacing the accumulator
(`STAGE2_SPEC.md` §7); direction-split liquidations with feed provenance
(§23.1); historical bootstrap, restart catch-up and late-data correction
(`STAGE2_SPEC.md` §8); deterministic snapshot identity and full version
quadruple on all outputs (`STAGE2_SPEC.md` §2); runtime failure isolation
(`STAGE2_SPEC.md` §9); blocked-not-descoped roadmap markers (§24); and
resolved open decisions A–H (`STAGE2_IMPLEMENTATION_PLAN.md`).

Revision 0.2 incorporated: per-metric-family coverage, provenance and
Data Confidence (§23.2a); `volume_base` renamed to `volume_raw` +
`volume_raw_unit` (§23.1); five additive consensus notional sums
(§23.2); `calculation_version` as part of logical identity
(`STAGE2_SPEC.md` §10); startup double-scan closing the catch-up race and
drop-oldest requeueing into the recompute queue (`STAGE2_SPEC.md`
§8.1/§8.1a); explicit percentile invalidation ranges for 7d/30d windows
(`STAGE2_SPEC.md` §8.3); instrument metadata split into
`exchange_instruments` separate from metric capability
(`STAGE2_SPEC.md` §2); and resolved decisions I–N — DB size measured now
and again at 24h, fetch-and-store instrument metadata with
last-known-good fallback / mismatch alarm / fail-closed notional,
48h configurable correction horizon, rotating JSONL liquidation-payload
side-channel disabled by default, 5s soft grace and 15s hard deadline on
bar close, and `BAR_CLOSE` accepted as the Stage 2.1 notional
approximation (`STAGE2_IMPLEMENTATION_PLAN.md`).

Revision 0.2.1 incorporated: `data_health_snapshots` versioned with
`feature_schema_version` + `calculation_version` in its logical key
(health verdicts are config-dependent, so a recompute must not overwrite
an earlier configuration's verdict); `stage2_recompute_queue` made
ranged and version-scoped (`job_type`, `calculation_version`,
`range_start_ts`/`range_end_ts`, nullable `metric`/`scope`/`window`) with
one row per `calculation_version` and no automatic fan-out across
retained versions (`STAGE2_SPEC.md` §8.3a); liquidation **availability
(3/3 active venues) separated from feed quality**, Bitget correctly
excluded from the denominator as a disabled venue, and consensus sums
renamed `observed_*` and documented as a provenance-aware lower bound
rather than a market total (§23.2b); and the Phase 1.5 spot-ingestion
claim corrected — Stage 1 raw tables are keyed `(exchange, symbol, ts)`
with no `market_type`, so spot would silently overwrite perp via the
existing upserts; separate spot/v2 raw tables are the preferred baseline
(`STAGE2_IMPLEMENTATION_PLAN.md`).
