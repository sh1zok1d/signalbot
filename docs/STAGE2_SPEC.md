# Stage 2 — Technical Specification (Phase 0 output)

This document proposes the Stage 2 architecture, DB schema, config schema,
symbol lifecycle model, worker/cadence model, and structural-level design,
adapted to what `STAGE2_DATA_AUDIT.md` found in the actual Stage 1 codebase.
Nothing here is implemented yet — this is the design to review before
Stage 2.1 coding starts.

## 1. Proposed Stage 2 architecture

Stage 1's convention is flat, lowercase, single-purpose top-level packages
(`common/`, `data_ingestion/`, `backfill/`, `storage/`). Stage 2 should
follow the same convention rather than introducing a different nesting
style:

```
analytics/
├── __init__.py
├── feature_engine/        # price/range/volume/taker-delta/OI-change per window
├── percentile_engine/     # 7d/30d percentiles, confidence tiers (reuses
│                          #   the _confidence_tier pattern already in
│                          #   storage/validate.py)
├── market_context/        # regime detection — Phase 2+, stub interfaces only now
└── data_quality/          # DataHealthSnapshot + gap detection (NEW — see
                            #   STAGE2_DATA_AUDIT.md §4, nothing like this
                            #   exists in Stage 1)

symbols/
└── registry.py            # symbol registry + lifecycle (ACTIVE/DRAINING/
                            #   DISABLED/DELISTED/DATA_UNAVAILABLE), same
                            #   declarative-table-plus-idempotent-seed
                            #   pattern as common/capabilities.py

structure/                 # Phase 2/3 — interfaces sketched in §6, not built
├── swing_detector/
├── level_registry/
└── target_selector/

signals/                   # Phase 2/3 — not built in Stage 2.1
├── detectors/
├── confirmation/
├── scoring/
├── state_machine/
└── explanation/

evaluation/                 # Phase 5 — not built in Stage 2.1
├── historical_runner/
├── outcome_tracker/
└── metrics/

config/
└── stage2.yaml             # separate from config.yaml (Stage 1's file is
                             #   untouched); typed inheritance loader
```

Stage 2.1 (this phase's implementation target) only needs
`analytics/feature_engine/`, `analytics/percentile_engine/`,
`analytics/data_quality/`, `symbols/registry.py`, and `config/stage2.yaml`.
Everything else is scaffolding to keep the eventual module boundaries clean,
per the plan's "add modularly, don't build Stage 2 as one giant change" rule.

**Where feature computation hooks into Stage 1:** `IngestionManager`
already fires a single callback, `_on_bar_closed`, exactly once per closed
1m bar per exchange (`data_ingestion/manager.py`). This is already a
"bucket finalizer" in everything but name. Stage 2.1's authoritative
feature computation should subscribe to the *aggregated* (cross-exchange)
close of a bucket — i.e. a new listener that waits until all enabled
exchanges have closed their 1m bar for a given minute, then computes
features for that bucket. This reuses the existing event-driven flow
instead of polling or re-deriving bucket closure independently. No change
to `bar_builder.py` or `manager.py`'s existing behavior is required — the
new listener is additive (see §"Worker and cadence model" below for exactly
how it attaches).

## 2. Proposed database schema (Stage 2.1 scope) — REVISED 0.2

Changes in Revision 0.2:

- **Coverage, provenance and Data Confidence are per metric family**, not
  global — price, OI, taker flow and liquidations genuinely have different
  coverage on this venue set.
- `volume_base` → **`volume_raw` + `volume_raw_unit`** (the old name
  asserted a unit that is false for OKX).
- Consensus gains the **additive notional sums** needed for buy/sell
  pressure on 5m/15m/1h.
- **`calculation_version`** is part of the logical key of every derived
  table, so a recompute under a new config never overwrites results
  produced under the old one.
- **Instrument metadata is split out** into `exchange_instruments`;
  `symbol_exchange_capabilities` is metric-level only.

Changes carried over from Revision 0.1:

- The single `feature_vectors` table is **replaced by a two-level model**
  (`exchange_feature_vectors` + `consensus_feature_vectors`). Mixing
  per-exchange and cross-exchange values in one row made it structurally
  possible to aggregate incomparable units — which, given the OKX
  contracts-vs-base finding (`STAGE2_DATA_AUDIT.md` §8), is not a
  hypothetical risk.
- `exchange_capabilities` (Stage 1) is **no longer modified at all**. The
  symbol dimension goes into a new additive table.
- Liquidations are split by direction and carry feed provenance.
- CVD is stored as **windowed delta**, never as an open-ended accumulator.
- All snapshot identity is **deterministic** (`snapshot_ts`, not `now()`).
- Every output table carries the full version quadruple.

Additive tables only, following the exact conventions already in
`storage/schema.sql` (`CREATE TABLE IF NOT EXISTS`, explicit hypertable
creation, comment blocks explaining *why*). Delivered as a **separate file**
(`storage/stage2_schema.sql`), applied by a **separate init function**
(`db.init_stage2_schema()`), gated behind the `stage2.enabled` config flag —
so Stage 1's `init_schema()` and its call sites are untouched.

```sql
-- ============================================================
-- Symbol registry (structural + lifecycle). Mirrors the existing
-- exchange_capabilities pattern: declarative Python data, upserted
-- idempotently at startup, queried via SQL by everything downstream.
-- ============================================================
CREATE TABLE IF NOT EXISTS symbols (
    symbol          TEXT PRIMARY KEY,
    base_asset      TEXT NOT NULL,
    quote_asset     TEXT NOT NULL,
    asset_tier      TEXT NOT NULL,             -- 'major' | 'major_alt' | ...
    status          TEXT NOT NULL DEFAULT 'ACTIVE',
    -- ACTIVE | DRAINING | DISABLED | DELISTED | DATA_UNAVAILABLE
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    disable_policy  TEXT NOT NULL DEFAULT 'drain',  -- drain | force_expire
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_symbol_status CHECK (
        status IN ('ACTIVE','DRAINING','DISABLED','DELISTED','DATA_UNAVAILABLE'))
);

-- Audit log per clarifications §18.
CREATE TABLE IF NOT EXISTS symbol_status_history (
    id              BIGSERIAL PRIMARY KEY,
    symbol          TEXT NOT NULL,
    previous_status TEXT,
    new_status      TEXT NOT NULL,
    reason          TEXT,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    changed_by      TEXT,
    config_version  TEXT
);

-- ============================================================
-- REVISION 0.2: instrument metadata and metric capabilities are now
-- SEPARATE tables. They have genuinely different cardinality (one
-- instrument has one tick size, but six metric capabilities) and
-- different lifecycles (instrument metadata is fetched from the
-- exchange; capability is a reviewed declaration). Keeping them in one
-- table duplicated tick_size/contract_multiplier six times per
-- instrument and made a refresh a six-row update with no single source.
--
-- exchange_instruments: ONE row per (exchange, symbol, market_type).
-- This is the authority for unit normalization.
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_instruments (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,          -- canonical, e.g. BTCUSDT
    market_type           TEXT NOT NULL DEFAULT 'perp',
    exchange_instrument_id TEXT NOT NULL,         -- venue-native id, e.g. BTC-USDT-SWAP
    -- Unit metadata. NULL means "unknown", never "1.0". A NULL
    -- contract_multiplier where quantity_unit='contracts' makes this
    -- instrument ineligible for notional consensus (fail-closed).
    quantity_unit         TEXT,                   -- 'base' | 'contracts'
    contract_multiplier   DOUBLE PRECISION,       -- base asset per contract (OKX ctVal)
    tick_size             DOUBLE PRECISION,
    price_precision       INTEGER,
    quantity_precision    INTEGER,
    -- Provenance of the metadata itself (decision: fetch-and-store with
    -- last-known-good fallback + mismatch alarm).
    metadata_source       TEXT NOT NULL,          -- 'exchange_api' | 'declared_fallback' | 'manual'
    fetched_at            TIMESTAMPTZ,
    is_stale              BOOLEAN NOT NULL DEFAULT FALSE,
    note                  TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type),
    CONSTRAINT ck_ei_quantity_unit CHECK (
        quantity_unit IS NULL OR quantity_unit IN ('base','contracts')),
    CONSTRAINT ck_ei_metadata_source CHECK (
        metadata_source IN ('exchange_api','declared_fallback','manual'))
);

-- ============================================================
-- symbol_exchange_capabilities: METRIC-LEVEL capability only.
-- No unit/contract columns — those live in exchange_instruments.
-- Stage 1's exchange_capabilities is NOT altered.
-- ============================================================
CREATE TABLE IF NOT EXISTS symbol_exchange_capabilities (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    metric                TEXT NOT NULL,
    live_supported        BOOLEAN NOT NULL,
    historical_supported  BOOLEAN NOT NULL,
    coverage_type         TEXT NOT NULL,      -- full|snapshot|aggregated|unavailable
    expected_freshness_s  INTEGER,
    enabled               BOOLEAN NOT NULL DEFAULT TRUE,
    note                  TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (exchange, symbol, market_type, metric),
    CONSTRAINT ck_sec_coverage_type CHECK (
        coverage_type IN ('full','snapshot','aggregated','unavailable'))
);

-- ============================================================
-- LEVEL A — exchange-level features. One row per exchange per bucket.
-- These are INDEPENDENT observations; nothing here is cross-exchange.
-- Every quantity column carries an explicit unit in its name so a
-- base-denominated and a contract-denominated value can never be
-- silently added together.
-- ============================================================
CREATE TABLE IF NOT EXISTS exchange_feature_vectors (
    exchange              TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    timeframe             TEXT NOT NULL,       -- 1m|5m|15m|1h|4h
    bucket_ts             TIMESTAMPTZ NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version   TEXT NOT NULL,       -- see §10; part of logical identity

    -- price / structure (unit-safe: percentages)
    price_move_pct        DOUBLE PRECISION,
    range_width_pct       DOUBLE PRECISION,
    close_price           DOUBLE PRECISION,    -- for notional conversion + audit

    -- volume / flow. volume_raw is exchange-denominated in whatever unit
    -- that venue reports (base for binance/bybit, CONTRACTS for OKX) and
    -- is NEVER comparable across exchanges — the unit is stored alongside
    -- it so the name can never imply otherwise. *_notional_usd is the
    -- normalized, comparable form.
    volume_raw            DOUBLE PRECISION,
    volume_raw_unit       TEXT,                -- 'base' | 'contracts'
    volume_notional_usd   DOUBLE PRECISION,
    taker_buy_notional_usd  DOUBLE PRECISION,
    taker_sell_notional_usd DOUBLE PRECISION,
    taker_delta_notional_usd DOUBLE PRECISION,
    -- windowed CVD delta (NOT an open-ended accumulator — see §7)
    cvd_delta_notional_usd  DOUBLE PRECISION,

    -- derivatives
    oi_change_pct         DOUBLE PRECISION,    -- % change within bucket, per exchange only
    oi_unit               TEXT,                -- carried through from open_interest
    funding_rate          DOUBLE PRECISION,

    -- liquidations, split by direction, with provenance
    long_liquidation_notional  DOUBLE PRECISION,
    short_liquidation_notional DOUBLE PRECISION,
    liquidation_event_count    INTEGER,
    liquidation_feed_quality   TEXT,           -- full|snapshot|aggregated|unavailable
    is_snapshot_feed           BOOLEAN,

    -- per-exchange data quality for this bucket
    bars_expected         INTEGER,
    bars_present          INTEGER,
    has_gap               BOOLEAN NOT NULL DEFAULT FALSE,
    is_usable             BOOLEAN NOT NULL DEFAULT TRUE,

    -- provenance / reproducibility (§8 of the review)
    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash           TEXT NOT NULL,
    config_version        TEXT NOT NULL,
    code_version          TEXT NOT NULL,

    PRIMARY KEY (exchange, symbol, market_type, timeframe, bucket_ts, calculation_version)
);
SELECT create_hypertable('exchange_feature_vectors', 'bucket_ts', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_efv_symbol_tf_ts
    ON exchange_feature_vectors (symbol, timeframe, bucket_ts DESC);

-- ============================================================
-- LEVEL B — consensus features. One row per bucket, NO exchange column.
-- Contains ONLY the results of cross-exchange aggregation. Aggregation
-- inputs are normalized quantities (notional USD), percentage changes,
-- and per-exchange percentile ranks — never raw base/contract values,
-- and never a blind sum of raw OI.
-- ============================================================
CREATE TABLE IF NOT EXISTS consensus_feature_vectors (
    symbol                TEXT NOT NULL,
    market_type           TEXT NOT NULL DEFAULT 'perp',
    timeframe             TEXT NOT NULL,
    bucket_ts             TIMESTAMPTZ NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version   TEXT NOT NULL,       -- see §10; part of logical identity

    -- ---- coverage: PER METRIC FAMILY (revision 0.2, families split 0.2.2) ----
    -- A single global exchanges_available was wrong: families genuinely
    -- differ. Coverage, provenance and Data Confidence are all resolved
    -- per family.
    --
    -- The six families (revision 0.2.2):
    --   price_structure : price_move_pct, range_width_pct, close_price
    --   volume          : volume_raw, volume_notional_usd
    --   taker_flow      : taker buy/sell/delta notional, cvd delta
    --   oi              : oi_change_pct
    --   funding         : funding_rate
    --   liquidations    : observed long/short notional, event count
    --
    -- Why volume is split out of price_structure: a missing
    -- contract_multiplier breaks notional normalization, which degrades
    -- `volume` and `taker_flow` — but price_move_pct and range_width_pct
    -- are percentages computed from OHLC alone and are completely
    -- unaffected. Folding them together would let a units problem
    -- silently suppress perfectly good price coverage.
    --
    -- IMPORTANT — coverage is BUCKET-LEVEL, not capability-level.
    -- coverage_by_metric answers "how many venues supplied usable data
    -- FOR THIS BUCKET", not "how many venues have such a feed at all".
    -- The two diverge sharply for liquidations: liquidations are never
    -- backfilled (Stage 1 rule), so in any historical bootstrap bucket
    -- available = 0 even though all three venues have a live feed.
    -- Live capability lives in symbol_exchange_capabilities; feed
    -- quality lives in liquidation_feed_quality_by_exchange. Three
    -- distinct concepts, never conflated. Bitget is disabled and is not
    -- in any denominator.
    --
    -- coverage_by_metric — HISTORICAL BOOTSTRAP bucket (30d ago):
    --   {"price_structure":{"available":3,"expected":3,"ratio":1.0},
    --    "volume":         {"available":3,"expected":3,"ratio":1.0},
    --    "taker_flow":     {"available":1,"expected":3,"ratio":0.33},
    --    "oi":             {"available":2,"expected":3,"ratio":0.67},
    --    "funding":        {"available":3,"expected":3,"ratio":1.0},
    --    "liquidations":   {"available":0,"expected":3,"ratio":0.0}}
    --
    -- coverage_by_metric — LIVE bucket, all feeds healthy:
    --   {"price_structure":{"available":3,"expected":3,"ratio":1.0},
    --    "volume":         {"available":3,"expected":3,"ratio":1.0},
    --    "taker_flow":     {"available":3,"expected":3,"ratio":1.0},
    --    "oi":             {"available":3,"expected":3,"ratio":1.0},
    --    "funding":        {"available":3,"expected":3,"ratio":1.0},
    --    "liquidations":   {"available":3,"expected":3,"ratio":1.0}}
    coverage_by_metric    JSONB NOT NULL,
    -- provenance_by_metric — HISTORICAL BOOTSTRAP bucket:
    --   {"price_structure":{"contributing":["binance","bybit","okx"],"excluded":{}},
    --    "taker_flow":     {"contributing":["binance"],
    --                       "excluded":{"bybit":"NO_HISTORICAL_TAKER_SPLIT",
    --                                   "okx":"NO_HISTORICAL_TAKER_SPLIT"}},
    --    "oi":             {"contributing":["binance","bybit"],
    --                       "excluded":{"okx":"NO_HISTORICAL_OI"}},
    --    "funding":        {"contributing":["binance","bybit","okx"],"excluded":{}},
    --    "liquidations":   {"contributing":[],
    --                       "excluded":{"binance":"NO_HISTORICAL_DATA",
    --                                   "bybit":"NO_HISTORICAL_DATA",
    --                                   "okx":"NO_HISTORICAL_DATA"}}}
    provenance_by_metric  JSONB NOT NULL,
    -- data_confidence_by_metric: 0..100 per family, computed independently.
    -- Historical bootstrap bucket example — liquidations is 0 because no
    -- data exists for that bucket at all, taker_flow is low because only
    -- one venue contributed (below the consensus minimum of 2):
    --   {"price_structure":97.0,"volume":95.0,"taker_flow":0.0,
    --    "oi":64.0,"funding":96.0,"liquidations":0.0}
    -- Live bucket: liquidations sits below price_structure even at full
    -- availability, because confidence accounts for feed quality too.
    --   {"price_structure":97.0,"volume":95.0,"taker_flow":93.0,
    --    "oi":90.0,"funding":96.0,"liquidations":72.0}
    data_confidence_by_metric JSONB NOT NULL,

    -- Rolled-up convenience values. These are DERIVED from the per-metric
    -- maps for reporting only and must never be used as the gate for a
    -- metric-specific decision — a detector requiring OI reads the OI
    -- entry, not this.
    exchanges_expected_max INTEGER NOT NULL,
    min_coverage_ratio     DOUBLE PRECISION,   -- worst family, for quick triage
    data_confidence_overall DOUBLE PRECISION,  -- reporting only

    -- direction agreement (ternary sign −1/0/+1, unit-free — safe across
    -- exchanges). Frozen formula in §11: max(neg,flat,pos)/available;
    -- an all-zero (all-flat) family scores 1.0, not 0.0.
    price_direction_agreement  DOUBLE PRECISION,  -- share agreeing on sign, 0..1
    flow_direction_agreement   DOUBLE PRECISION,
    oi_direction_agreement     DOUBLE PRECISION,

    -- robust aggregates of NORMALIZED values only
    price_move_pct_median      DOUBLE PRECISION,
    range_width_pct_median     DOUBLE PRECISION,
    oi_change_pct_median       DOUBLE PRECISION,
    -- funding consensus (revision 0.2.2). funding_rate is already a
    -- dimensionless rate, so it is directly comparable across venues
    -- with no normalization step. The consensus-scope funding percentile
    -- is computed over funding_rate_median, not over any single venue.
    funding_rate_median        DOUBLE PRECISION,
    funding_rate_mad           DOUBLE PRECISION,

    -- additive notional sums (revision 0.2 — required for buy/sell
    -- pressure assessment on 5m/15m/1h; notional USD IS additive across
    -- venues, raw quantities are not)
    volume_notional_usd_sum       DOUBLE PRECISION,
    taker_buy_notional_usd_sum    DOUBLE PRECISION,
    taker_sell_notional_usd_sum   DOUBLE PRECISION,
    taker_delta_notional_usd_sum  DOUBLE PRECISION,
    cvd_delta_notional_usd_sum    DOUBLE PRECISION,
    -- Revision 0.2.1: named `observed_*` because these are a
    -- provenance-aware LOWER BOUND on liquidations, not a market total.
    -- Binance's feed is rate-capped (under-counts cascades) and OKX's is
    -- aggregated/delayed, so the sum is "what our three feeds reported",
    -- which is strictly less than what the market actually liquidated.
    -- Never compare these to an external aggregated market total without
    -- an explicit normalization step.
    observed_long_liquidation_notional_sum  DOUBLE PRECISION,
    observed_short_liquidation_notional_sum DOUBLE PRECISION,
    observed_liquidation_event_count_sum    INTEGER,
    -- Feed quality is reported ALONGSIDE the sum, never folded into it.
    liquidation_feed_quality_by_exchange    JSONB,  -- {"binance":"snapshot","bybit":"full","okx":"aggregated"}

    -- dispersion / outliers. MAD columns exist ONLY for the three metrics that
    -- carry outlier detection (price_move_pct, oi_change_pct, funding_rate);
    -- funding's MAD is funding_rate_mad above.
    price_move_pct_mad         DOUBLE PRECISION,  -- median absolute deviation
    oi_change_pct_mad          DOUBLE PRECISION,
    -- Frozen metric-first shape (§11), NOT exchange-first:
    --   {"oi_change_pct": {"bybit": {"robust_z": 4.1, "reason": "ROBUST_Z_THRESHOLD"}}}
    -- one exchange may appear under several metrics; keys sorted on write.
    outlier_exchanges          JSONB,

    -- confidence (frozen formulas in §11). data_confidence_overall = mean of the
    -- six family scores; consensus_confidence = min of the six.
    consensus_confidence       DOUBLE PRECISION,  -- 0..100
    is_partial_consensus       BOOLEAN NOT NULL DEFAULT FALSE,

    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash           TEXT NOT NULL,
    config_version        TEXT NOT NULL,
    code_version          TEXT NOT NULL,

    PRIMARY KEY (symbol, market_type, timeframe, bucket_ts, calculation_version)
);
SELECT create_hypertable('consensus_feature_vectors', 'bucket_ts', if_not_exists => TRUE);

-- ============================================================
-- Percentile snapshots — now explicitly two-scoped. `scope` says whether
-- this distribution is one exchange's own history or the consensus
-- series' history. Binance/Bybit/OKX distributions are NEVER pooled;
-- a consensus-scope percentile is computed over the consensus series
-- itself (which is already normalized), not over concatenated
-- per-exchange raw values.
-- ============================================================
CREATE TABLE IF NOT EXISTS percentile_snapshots (
    scope           TEXT NOT NULL,             -- 'exchange' | 'consensus'
    exchange        TEXT NOT NULL DEFAULT '',  -- '' when scope='consensus' (keeps PK non-null)
    symbol          TEXT NOT NULL,
    market_type     TEXT NOT NULL DEFAULT 'perp',
    metric          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    percentile_window TEXT NOT NULL,           -- '7d' | '30d' (`window` is a reserved keyword)
    bucket_ts       TIMESTAMPTZ NOT NULL,
    value           DOUBLE PRECISION,
    percentile_rank DOUBLE PRECISION,
    sample_size     INTEGER NOT NULL,
    -- Strictly-earlier guarantee, stored so it is auditable rather than
    -- merely asserted: the newest bucket that entered the distribution.
    sample_window_start TIMESTAMPTZ,
    sample_window_end   TIMESTAMPTZ,           -- MUST be < bucket_ts
    confidence_tier TEXT NOT NULL,             -- none|low|building|mature
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    config_hash     TEXT NOT NULL,
    config_version  TEXT NOT NULL,
    code_version    TEXT NOT NULL,
    feature_schema_version INTEGER NOT NULL,
    calculation_version TEXT NOT NULL,          -- see §10; part of logical identity
    PRIMARY KEY (scope, exchange, symbol, market_type, metric, timeframe, percentile_window, bucket_ts, calculation_version),
    CONSTRAINT ck_ps_scope CHECK (scope IN ('exchange','consensus')),
    -- Look-ahead guard enforced by the DB, not just by code review.
    CONSTRAINT ck_ps_no_lookahead CHECK (
        sample_window_end IS NULL OR sample_window_end < bucket_ts)
);
SELECT create_hypertable('percentile_snapshots', 'bucket_ts', if_not_exists => TRUE);

-- ============================================================
-- Data health / gap detection. Identity is now DETERMINISTIC:
-- snapshot_ts is aligned to the health-check cadence (config), so a
-- replay of the same period produces the same logical rows.
-- computed_at is wall-clock metadata and is NOT part of the key.
-- ============================================================
CREATE TABLE IF NOT EXISTS data_health_snapshots (
    symbol             TEXT NOT NULL,
    exchange           TEXT NOT NULL,
    market_type        TEXT NOT NULL DEFAULT 'perp',
    metric             TEXT NOT NULL,
    snapshot_ts        TIMESTAMPTZ NOT NULL,   -- bucket-aligned, deterministic
    last_event_at      TIMESTAMPTZ,
    expected_interval_s INTEGER,
    lateness_ms         BIGINT,
    gap_count            INTEGER NOT NULL DEFAULT 0,
    largest_gap_s         INTEGER,
    backfill_status       TEXT,
    coverage_window_start  TIMESTAMPTZ,
    coverage_window_end     TIMESTAMPTZ,
    is_stale                 BOOLEAN NOT NULL DEFAULT FALSE,
    is_usable                 BOOLEAN NOT NULL DEFAULT TRUE,
    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),  -- metadata only
    config_hash              TEXT NOT NULL,
    config_version           TEXT NOT NULL,
    code_version             TEXT NOT NULL,
    -- Revision 0.2.1: health classification is CONFIG-DEPENDENT.
    -- is_stale, is_usable, the gap thresholds and the freshness budgets
    -- all come from configuration — so the same raw data yields a
    -- different health verdict under a different config. A health
    -- snapshot is therefore a computed result like any other and must
    -- not be overwritten by a recompute under a new configuration.
    feature_schema_version   INTEGER NOT NULL,
    calculation_version      TEXT NOT NULL,
    PRIMARY KEY (symbol, exchange, market_type, metric, snapshot_ts, calculation_version)
);
SELECT create_hypertable('data_health_snapshots', 'snapshot_ts', if_not_exists => TRUE);

-- ============================================================
-- Computation watermark — drives restart catch-up and late-data
-- correction (see §8). One row per computation stream.
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_watermarks (
    stream            TEXT NOT NULL,      -- 'exchange_features'|'consensus_features'|'percentiles'|'health'
    symbol            TEXT NOT NULL,
    market_type       TEXT NOT NULL DEFAULT 'perp',
    timeframe         TEXT NOT NULL,
    calculation_version TEXT NOT NULL,    -- watermarks are per calculation_version:
                                          -- a new config starts its own progress line
    last_computed_bucket_ts TIMESTAMPTZ,
    last_run_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (stream, symbol, market_type, timeframe, calculation_version)
);

-- ============================================================
-- Recompute queue — populated when a late/corrected raw bar invalidates
-- already-computed results. Drained by the reconciliation job so
-- correction is explicit and auditable, not implicit.
--
-- REVISION 0.2.1: jobs are RANGED, not per-row. A single corrected 1m
-- bucket invalidates every 30d-window percentile snapshot in the
-- following 30 days — enqueuing one row per affected snapshot would mean
-- tens of thousands of rows per correction (metrics × timeframes ×
-- scopes × buckets). A range job expresses the same work in one row.
--
-- job_type semantics:
--   BUCKET_RECOMPUTE        -> recompute features for a single bucket;
--                              range_start_ts = range_end_ts = bucket_ts
--   PERCENTILE_INVALIDATION -> recompute percentile snapshots whose
--                              sampling window contained a corrected
--                              bucket; range is half-open-ish
--                              (range_start_ts, range_end_ts]
--
-- metric / scope / percentile_window are NULLABLE and mean "all" when NULL, so a
-- broad invalidation is one row rather than a cross-product of rows.
-- NULL therefore carries meaning and MUST participate in dedup — see the
-- partial unique index below, which is what actually enforces that.
--
-- Enqueue semantics (what the dedup index guarantees):
--   * two identical PENDING jobs collapse to one logical pending job,
--     including when metric/scope/percentile_window are all NULL;
--   * once processed_at is set, the same logical job can be enqueued
--     again (a later correction to the same range is not swallowed);
--   * different calculation_version never conflict;
--   * different range, percentile_window, scope, metric or reason never conflict.
-- ============================================================
CREATE TABLE IF NOT EXISTS stage2_recompute_queue (
    id                  BIGSERIAL PRIMARY KEY,
    job_type            TEXT NOT NULL,        -- BUCKET_RECOMPUTE | PERCENTILE_INVALIDATION
    symbol              TEXT NOT NULL,
    market_type         TEXT NOT NULL DEFAULT 'perp',
    timeframe           TEXT NOT NULL,
    -- Revision 0.2.1: a job targets exactly ONE calculation_version.
    -- See "Recompute scope across calculation versions" below.
    calculation_version TEXT NOT NULL,
    range_start_ts      TIMESTAMPTZ NOT NULL,
    range_end_ts        TIMESTAMPTZ NOT NULL,
    metric              TEXT,                 -- NULL = all metrics
    scope               TEXT,                 -- NULL = both ('exchange','consensus')
    percentile_window   TEXT,                 -- NULL = all windows ('7d','30d'); `window` is reserved
    reason              TEXT NOT NULL,        -- LATE_BAR | BACKFILL_CORRECTION | QUEUE_OVERFLOW | MANUAL
    enqueued_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at        TIMESTAMPTZ,
    CONSTRAINT ck_rq_job_type CHECK (
        job_type IN ('BUCKET_RECOMPUTE','PERCENTILE_INVALIDATION')),
    CONSTRAINT ck_rq_range CHECK (range_end_ts >= range_start_ts),
    CONSTRAINT ck_rq_scope CHECK (scope IS NULL OR scope IN ('exchange','consensus'))
);

-- ------------------------------------------------------------
-- Dedup index. A plain table-level UNIQUE was WRONG on two counts
-- (corrected in the schema-correctness patch):
--
--  1. NULL semantics. In a normal UNIQUE, NULLs are DISTINCT — so two
--     "broad" jobs with metric/scope/percentile_window all NULL do NOT conflict and
--     both get inserted. The old comment claimed NULL ("all") would
--     participate in dedup; it did not. Broad jobs are exactly the
--     common case for PERCENTILE_INVALIDATION, so this was the case that
--     mattered most.
--  2. Lifetime. The constraint covered processed rows too, so once a job
--     was completed its row permanently blocked ever enqueuing the same
--     logical job again — a second correction to the same range under
--     the same version would be silently dropped.
--
-- Fix: a PARTIAL unique index scoped to pending rows only, with NULLs
-- treated as equal.
--
-- PostgreSQL 15+ (this deployment runs pg16 via timescale/timescaledb:
-- 2.17.2-pg16, so this is available):
-- ------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job
    ON stage2_recompute_queue (
        job_type, symbol, market_type, timeframe, calculation_version,
        range_start_ts, range_end_ts, metric, scope, percentile_window, reason)
    NULLS NOT DISTINCT
    WHERE processed_at IS NULL;

-- Portable equivalent if NULLS NOT DISTINCT is ever unavailable (pg<15):
-- an expression index that collapses NULL to a sentinel. Functionally
-- identical; kept here so the intent survives a version downgrade.
--
-- CREATE UNIQUE INDEX IF NOT EXISTS ux_rq_pending_job
--     ON stage2_recompute_queue (
--         job_type, symbol, market_type, timeframe, calculation_version,
--         range_start_ts, range_end_ts,
--         COALESCE(metric, '*'), COALESCE(scope, '*'), COALESCE(percentile_window, '*'),
--         reason)
--     WHERE processed_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_rq_pending
    ON stage2_recompute_queue (enqueued_at) WHERE processed_at IS NULL;
```

Explicitly **not** created in Stage 2.1 (per the plan's phasing — these
belong to Phase 2/3+): `events`, `signal_instances`, `signal_score_history`,
`signal_state_history`, `risk_flags`, `signal_explanations`, `targets`,
`structural_levels`, `historical_outcomes`, `evaluation_runs`. Their shapes
are already fully specified in the clarifications doc (multi-symbol
architecture §11.5–11.6, explanation JSON in §8) — no new design work is
needed there when Phase 2 starts, just implementation against an
already-agreed schema.

## 3. Config schema

Stage 1's `common/config.py` is a thin `Config` wrapper around one parsed
YAML dict, with a hard split (secrets in `.env`, everything
threshold/window/cooldown-related in `config.yaml`). Stage 2 keeps that
split and adds its own file rather than growing `config.yaml`:

```
config/stage2.yaml     # new file, loaded by a new Stage2Config class
```

Structure (per clarifications §7 and §11.2, inheritance
`global → asset_tier → symbol`):

```yaml
stage2:
  enabled: false        # master switch — Stage 1 behavior is unchanged when false

defaults:
  percentile_windows: [7d, 30d]
  timeframes: [1m, 5m, 15m, 1h, 4h]
  data_confidence:
    minimum_metric_coverage: 0.95     # upstream bar-completeness param — NOT a consensus-core gate
    minimum_exchange_coverage: 2      # authoritative per-family consensus minimum
    weights:                          # Data Confidence weights (Revision 0.2.3, frozen; see §11)
      coverage: 0.50                  #   each >= 0, coverage > 0, sum == 1.0
      agreement: 0.30
      dispersion: 0.20
  outliers:
    robust_z_threshold: 3.5           # finite, > 0; robust-z scale constant is fixed in code (§11)
  warmup:
    minimum_calendar_days: 7
    preferred_calendar_days: 30

asset_tiers:
  major:
    # BTCUSDT lives here; no overrides needed yet

symbols:
  BTCUSDT:
    tier: major
    enabled: true
    market_types: [perp]     # 'spot' intentionally not listed — not ingested
```

`Stage2Config` resolves `symbol override > asset tier > global default`,
and every computed row (`feature_vectors.config_hash`, etc.) stores the
resolved config's hash — implemented as `hashlib.sha256` over a
canonicalized (sorted-keys) JSON dump of the resolved dict, following the
plan's "config_hash for reproducibility" requirement (clarifications §7.2).

Loader mirrors `common/config.py`'s existing shape (`@classmethod load`,
`__getitem__`/`get`) so it's a familiar pattern to whoever maintains it
next, but lives in its own module (`common/stage2_config.py` or
`analytics/config.py` — open decision, see Implementation Plan) rather than
extending the Stage 1 `Config` class, so Stage 1 imports are never touched.

## 4. Symbol lifecycle model

Implements clarifications §18 directly on top of the `symbols` table above.
`symbols.status` drives what's permitted; `enabled` (mirrors
`exchange_capabilities.enabled`) is the fast on/off switch, `status` carries
the more granular lifecycle:

| Status | New detections | Active EARLY/ARMED/TRIGGERED | New TRIGGERED |
|---|---|---|---|
| ACTIVE | yes | yes | yes |
| DRAINING | no | continue to resolution | no |
| DISABLED | no | per `disable_policy` (`drain` default, or `force_expire`) | no |
| DELISTED | no | forced to `EXPIRED`, reason `SYMBOL_DELISTED` | no |
| DATA_UNAVAILABLE | no | preserved, timers paused/tracked separately | no |

For Stage 2.1, only `BTCUSDT` / `ACTIVE` is exercised end-to-end — the
state machine and event tables don't exist yet (Phase 2+), so most of this
table is inert until then. It is created now so the symbol registry and
lifecycle states exist as a single queryable source from day one, per the
plan's "don't create architectural constraints that block later
expansion" rule.

**No foreign keys are declared in Stage 2.1** (corrected in revision
0.2.2 — an earlier draft claimed the `symbol` columns already had a
foreign-key target, which was inaccurate: no `REFERENCES` clause exists
anywhere in the proposed DDL). Adding `REFERENCES symbols(symbol)` to
hypertables has TimescaleDB-specific implications (constraint behavior
across chunks, effects on compression and on drop/retention operations)
that have not been verified against this deployment. Referential
integrity is therefore maintained by the writers — every Stage 2 write
path resolves its symbol through the registry — and adding real FKs is
deferred until it can be validated by the TimescaleDB integration test.
Whether to add them at all is left as an implementation-time question,
not asserted here as already done.

## 5. Worker and cadence model

**What Stage 1 already has:** a single asyncio process, one task per
exchange (WS `run_forever` + REST `run_poll_forever`, plus OKX's extra
liquidation WS task), a 15s coverage loop, a 30s heartbeat loop — all
inside one `IngestionManager`. No queue, no worker pool, no multi-process
orchestration anywhere in the tree.

**Stage 2.1 recommendation (BTC-only, 3 exchanges):** do **not** build the
partitioned queue / worker-pool architecture from clarifications §21 yet —
that's explicitly scoped there as a *plan to prepare*, not something to
implement before it's needed, and at one symbol there is nothing to
partition. Instead:

- A new coroutine (`analytics/feature_engine/bucket_listener.py`) subscribes
  to bucket closes the same way `IngestionManager._on_bar_closed` already
  does, but at the cross-exchange level: it waits until the current minute's
  bar exists for every *enabled* exchange (or a configurable grace period
  elapses — feeding `DATA_GAP`/`STALE_DATA` if not), then computes **one
  `exchange_feature_vectors` row per exchange**, followed by **one
  `consensus_feature_vectors` row** aggregating them. This is
  "authoritative calculations on closed buckets only" (clarifications §3.1)
  implemented as a direct extension of the existing closed-bar event, not a
  new polling loop.
- Runs as one more task inside the same process (`asyncio.create_task`,
  same shutdown/cancellation handling `main.py` already has via
  `_run_cancellable` and the SIGINT/SIGTERM handlers) — **but supervised
  and isolated per §9 below**. In-process is approved (review decision
  10-B); unsupervised in-process is not.
- No partition key, no queue, no separate worker processes needed at this
  scale — the existing single-process model already handles 3 exchanges ×
  1 symbol comfortably (soak-tested).
- **Historical bootstrap never runs inside this listener.** It is a
  separate CLI job (§8) so a long backfill can never occupy the live
  path's event loop budget.
- The partitioned `symbol + market_type` worker-pool design from
  clarifications §21 is deferred to whenever a second symbol is actually
  about to go live — at that point it becomes a real requirement (protecting
  BTC's live path from a SOL backfill), not before.

Latency: Stage 1's poll cadence (15s) and coverage loop (15s) already set
the practical floor; the clarifications doc's 5s/10s/15s SLA targets
(bucket finalize / feature calc / event update) are compatible with this
architecture at one symbol but have not been measured — no load test has
been run (there's nothing to load-test yet). Flagged as unverified, not
assumed.

### 5.1 Which timeframes the listener actually writes

Explicitly resolved (review item 11, last bullet): the configured
timeframe list is `[1m, 5m, 15m, 1h, 4h]` and **all five are written**,
including `1m`.

- `1m` rows are the atomic unit: every higher timeframe is derived from
  them, and the late-data correction model (§8) needs a 1m row to know
  which higher buckets a corrected bar invalidates.
- On each closed minute the listener writes the `1m` row unconditionally,
  and additionally writes the `5m`/`15m`/`1h`/`4h` rows **only on their own
  boundary closes** (i.e. a 5m row is written once, when minute % 5 == 0
  and that whole 5m window is closed) — never partially.
- A higher-timeframe row is written only when all of its constituent 1m
  buckets are present or explicitly accounted for as gaps; `bars_present`
  / `bars_expected` / `has_gap` on the row record exactly which.

This resolves the previous ambiguity where "5m/15m/1h/4h windows" in the
acceptance criteria did not state whether `1m` was itself a stored
feature-vector scope.

### 5.2 Bar-close grace and hard deadline (decided, revision 0.2)

Exchanges do not close a minute simultaneously. The listener therefore
waits before treating a bucket as final:

| Parameter | Value | Behavior |
|---|---|---|
| **Soft grace** | **5s** after bucket close | Wait for all enabled exchanges. If all bars arrive, compute at full coverage |
| **Hard deadline** | **15s** after bucket close | Compute with whatever has arrived. Missing venues are excluded from that bucket's coverage with reason `LATE_BAR`, recorded in `provenance_by_metric` |

Both are configurable (`stage2.bucket_close.soft_grace_s`,
`stage2.bucket_close.hard_deadline_s`). Rationale for these specific
values: the soft grace sits just above the observed per-exchange bar-close
spread and comfortably under the 10s feature-calculation SLA
(clarifications §3), while the hard deadline coincides with the 15s
event/state SLA — so a bucket can never silently sit unresolved past the
point where downstream consumers expect it.

A bucket that hits the hard deadline is still **complete and correct for
the venues present** — it is a partial-coverage bucket, flagged as such,
not a failed one. If the late bar arrives afterwards it is handled by the
late-data correction path (§8.3), which recomputes that bucket at full
coverage. If the deadline is exceeded because Stage 2 itself is slow
(rather than an exchange being late), the bucket is additionally enqueued
per §8.1a and `STALE_DATA` is recorded.

## 6. Structural level design (interfaces only — Phase 2/3 implementation)

Per the plan, `structure/` is not built in Stage 2.1. To satisfy "propose
structural level interfaces" without pulling Phase 2 work forward, here is
the interface shape only, consistent with clarifications §13:

```python
@dataclass
class StructuralLevel:
    level_id: str
    symbol: str
    level_type: str            # SWING_HIGH | SWING_LOW | SESSION_HIGH | VWAP | ...
    price: float
    price_zone_low: float
    price_zone_high: float
    source_timeframe: str
    level_price_timestamp: datetime       # when the extreme occurred
    level_confirmation_timestamp: datetime  # when it became knowable — NEVER
                                             # equal to level_price_timestamp;
                                             # enforces the no-future-data rule
    touch_count: int
    is_active: bool
    invalidated_at: datetime | None
```

The critical invariant (clarifications §13.2) — a level may only be
referenced by an event/target using `level_confirmation_timestamp`, never
`level_price_timestamp` — is a Historical Evaluator correctness requirement
with no Stage 2.1 code impact today; documented here so the eventual
Phase 2/3 implementer doesn't have to rediscover it.

## 7. CVD model — REVISED 0.1

The first draft's single `perp_cvd` column was wrong for percentile use and
is removed.

**Problem with an accumulator.** A running CVD has an arbitrary origin: its
absolute level depends entirely on when the process first started
accumulating. A percentile computed over that series measures *how far the
accumulator has drifted since an arbitrary epoch*, not *how unusual current
flow is*. Restarts, backfills, and schema changes all shift the origin,
making the distribution non-stationary and historically irreproducible.

**Stage 2.1 stores windowed deltas instead:**

| Field | Meaning |
|---|---|
| `taker_delta_notional_usd` | net taker flow **within this bucket** (buy − sell, notional USD) |
| `cvd_delta_notional_usd` | CVD change **over the row's own timeframe window** |

Since one row already carries its timeframe, `cvd_delta_1m` / `_5m` /
`_15m` / `_1h` / `_4h` from the review are represented as the
`cvd_delta_notional_usd` value on the `1m` / `5m` / `15m` / `1h` / `4h`
rows respectively — same information, no redundant wide columns, and
percentiles fall out naturally per timeframe.

**Percentiles are computed on the deltas**, never on a cumulative level.

**Session-anchored CVD** (deliberately deferred, interface reserved): a
session-anchored series has a *defined, reproducible* origin (session
open), unlike a free-running accumulator, so it is legitimate — but it
requires a session-boundary definition (which exchange day? UTC? CME?)
that Stage 2.1 does not need and should not guess. Reserved as
`cvd_session_anchored_notional_usd` + `session_anchor_ts` to be added in
Phase 2 alongside the session-level structural work, where the session
definition is already required for `session_high`/`session_low`.

## 8. Restart catch-up, historical bootstrap, late-data correction — NEW 0.1

Three distinct mechanisms, deliberately separated so each is independently
testable.

### 8.1 Watermark and restart catch-up (double-scan — revised 0.2)

`stage2_watermarks` holds `last_computed_bucket_ts` per
(stream, symbol, market_type, timeframe, calculation_version).

**The race the naive version had.** "Catch up, then subscribe" leaves a
window: any bucket that closes *while the catch-up scan is running* is
after the scan's upper bound but before the subscription exists, so it is
silently never computed. On a 30-day bootstrap-sized catch-up that window
can be minutes wide.

**Resolution — double-scan** (chosen over pre-subscribe-and-buffer as the
simpler option at BTC-only scale, per review item 5):

1. **Scan A.** Read watermark; enumerate closed buckets up to the last
   fully-closed bucket at boot; compute in ascending `bucket_ts` order;
   advance watermark.
2. **Subscribe** to live bucket closes. Incoming events are accepted from
   this moment on.
3. **Scan B.** Immediately re-read the watermark and enumerate closed
   buckets between it and the *current* last-closed bucket. This covers
   exactly the buckets that closed during Scan A.
4. Scan B is normally empty or a handful of buckets. Any overlap with a
   bucket already delivered by the live subscription is harmless: writes
   are upserts on a deterministic logical key, so computing the same
   bucket twice produces the identical row.
5. Only after Scan B completes is Stage 2 reported as `RUNNING`; until
   then it is `WARMING_UP`.

Because all writes are upserts on a deterministic key, a catch-up that is
interrupted and re-run produces identical rows, and Scan A/Scan B/live
overlap is idempotent by construction rather than by careful sequencing.

### 8.1a Dropped buckets must be requeued, not just logged (revised 0.2)

The bounded queue's overflow policy is drop-oldest (§9). A dropped bucket
is a **computation gap**, and a log line is not a recovery mechanism —
nothing would ever go back for it.

Therefore: whenever the queue drops an item, the supervisor **must**
insert the corresponding (symbol, market_type, timeframe, bucket_ts) into
`stage2_recompute_queue` with `reason='QUEUE_OVERFLOW'`, in addition to
logging. The reconciliation job then picks it up on its next pass and
computes it exactly as it would a late-data correction. The same applies
to any bucket skipped because the hard deadline (§5.2) elapsed.

This closes the loop: **every path that fails to compute a bucket in the
live path leaves a durable record that causes it to be computed later.**

### 8.2 Historical bootstrap (`--stage2-backfill`)

A **separate CLI job**, never invoked from the live listener. Purpose: on
first enable, build features and percentile history from the ~30 days of
`klines_1m` / `open_interest` / etc. that Stage 1 has already collected, so
Stage 2 is not blind for another 7–30 days.

Contract:
- Reads **only closed historical buckets**; the newest bucket it will touch
  is the last fully-closed one at job start.
- Computes in ascending bucket order, exchange features → consensus
  features → percentiles, so no step ever sees a future value.
- For each bucket's percentile rank, the distribution is built **strictly
  from buckets with `bucket_ts < current bucket_ts`** — enforced in code
  and additionally by the `ck_ps_no_lookahead` CHECK constraint on
  `percentile_snapshots`.
- Idempotent: all writes are upserts on deterministic keys; re-running over
  an already-processed range rewrites identical values.
- Resumable: progress is the watermark itself, so an interrupted run
  continues from the last completed bucket rather than restarting.
- Bounded impact on live: runs in its own process, with its own connection
  pool sized separately from the live pool (config), and a configurable
  inter-batch sleep so it cannot saturate the DB that live ingestion
  depends on.
- `--from` / `--to` restrict the range; without them the job derives the
  range from available raw history and the existing watermark.

### 8.3 Late-data correction

Stage 1 upserts klines, so a late REST gap-fill or a corrected bar can
change a `klines_1m` row **after** Stage 2 has already computed features
from it. Silently leaving stale derived rows would break the "live and
historical replay agree" guarantee.

Model:
- Stage 2 records, per computed bucket, the `bars_present` it saw. A
  reconciliation job periodically re-checks recent raw data against what
  was computed.
- Any 1m bucket whose raw inputs changed within the **correction horizon**
  (`stage2.correction_horizon`, default proposal 48h — configurable) is
  enqueued in `stage2_recompute_queue`, together with **every higher
  timeframe bucket that contains it** (5m, 15m, 1h, 4h) — computed by
  containment, so dependency is explicit rather than assumed.
- The reconciliation job drains the queue in ascending bucket order,
  recomputing exchange features → consensus features → percentiles for
  affected buckets.
- Corrections outside the horizon are **logged, not silently ignored** —
  they surface in the `--stage2-validate` report so a decision to run a
  wider manual recompute is deliberate.

**Percentile invalidation range (revised 0.2 — this was underspecified).**
Correcting a bucket at `corrected_ts` changes not only that bucket's own
percentile row but **every later percentile snapshot whose sampling window
contained it**. Since a window of length `W` at bucket `B` samples
`[B − W, B)` (lower bound inclusive, upper bound exclusive — frozen in §12),
the corrected bucket is in `B`'s sample exactly when
`corrected_ts < B <= corrected_ts + W`. So:

| Window | Percentile snapshots to recompute |
|---|---|
| 7d  | `corrected_ts < bucket_ts <= corrected_ts + 7 days` |
| 30d | `corrected_ts < bucket_ts <= corrected_ts + 30 days` |

with the upper bound additionally clamped to `min(corrected_ts + W, now)`
— there is nothing to recompute in the future.

Properties:
- Applied **per window independently**: a correction triggers a 7d-range
  recompute for 7d snapshots and a 30d-range recompute for 30d snapshots.
- Applied at **both scopes** (`exchange` and `consensus`).
- **Idempotent**: recomputation is an upsert on the deterministic logical
  key, so re-running the same invalidation range rewrites identical
  values. Two overlapping corrections produce the union of ranges, not
  double work with different results.
- Enqueued as a **ranged job** in `stage2_recompute_queue`
  (`job_type='PERCENTILE_INVALIDATION'`, `range_start_ts=corrected_ts`,
  `range_end_ts=min(corrected_ts + W, now)`) rather than performed inline
  or expanded into one row per affected snapshot. One corrected bucket
  produces **one row per (timeframe, window, calculation_version)** — not
  tens of thousands. `metric`/`scope` are left NULL to mean "all", and
  the job is drained under the same throttle as any other reconciliation
  work so it cannot stall the live path.
- Cost note: a single corrected 1m bucket can invalidate up to 30 days of
  30d-window snapshots for that metric/timeframe. This is the main reason
  the correction horizon is bounded (48h) — an unbounded horizon would
  make a late backfill arbitrarily expensive.

### 8.3a Recompute scope across calculation versions (revision 0.2.1)

Since `calculation_version` is part of the logical key, several result
sets can coexist for the same bucket. A correction has to state *which*
of them it repairs.

**Decision: the queue holds one row per `calculation_version`.** A job
targets exactly one version; it never implicitly fans out across all
retained versions.

Default enqueue policy:
- A correction arising from live operation (`LATE_BAR`,
  `QUEUE_OVERFLOW`, `BACKFILL_CORRECTION`) enqueues a job **only for the
  currently active `calculation_version`** — that is the result set the
  running system depends on.
- Superseded versions are **not** repaired automatically. They are
  historical artifacts kept for comparison and reproducibility; silently
  rewriting them would defeat the purpose of retaining them, and
  repairing every retained version on every late bar would multiply
  reconciliation cost by the number of versions kept.
- Repairing a superseded version is possible but must be **explicit**: a
  `MANUAL` job naming that `calculation_version`. `--stage2-validate`
  reports, per retained version, how many buckets are known to be stale
  relative to corrected raw data, so the choice is informed rather than
  invisible.

Consequence to be aware of: a superseded `calculation_version` may
contain buckets computed from raw data that was later corrected. That is
acceptable and intended — it is a faithful record of *what was computed
at the time under that configuration*, which is exactly what
reproducibility requires. It must simply not be mistaken for a
current-best view of history. The validate report labels such versions
`HAS_STALE_BUCKETS` so the distinction is visible.

Rule: **raw data must never be corrected without a corresponding
downstream feature update.** The gap-fill path in `backfill/run_gap_fill`
is the main producer of such corrections and is the primary thing the
reconciliation job is watching.

## 9. Runtime failure isolation — NEW 0.1

In-process is approved for BTC-only Stage 2.1 (review decision 10-B), but
only under these guarantees. The design point is that **Stage 1 ingestion
is the system of record and must survive any Stage 2 defect.**

| Requirement | Mechanism |
|---|---|
| A Stage 2 exception never stops Stage 1 ingestion | The listener runs as its own supervised `asyncio.Task`. It never shares a task with any ingestion coroutine, and `IngestionManager` has no code path that awaits it. Exceptions are caught at the supervisor boundary and never propagate into the ingestion tasks |
| Runtime exception → DEGRADED | The supervisor catches, logs (structured, with bucket context), increments a failure counter, and sets Stage 2 state to `DEGRADED` (per the warm-up state model, clarifications §19). `DEGRADED` blocks new `TRIGGERED` in later phases; in Stage 2.1 it marks feature rows `is_usable=false` rather than writing wrong values |
| Supervised restart with bounded backoff | Restart with exponential backoff, capped — reusing the exact pattern already proven in `ExchangeClient.run_forever` (1s → ×2 → 60s cap) rather than inventing a second retry style. After N consecutive failures (config) the listener stays down in `DEGRADED` and stops retrying, so a persistent bug degrades loudly instead of hot-looping |
| Backlog never blocks exchange message handling | The listener consumes from a **bounded** queue. On overflow the policy is **drop-oldest + record a gap**, never block the producer. Ingestion callbacks (`_on_bar_closed`) must never `await` on a full Stage 2 queue — a slow/stuck Stage 2 must not apply backpressure to the WS read loop |
| Latency breach → STALE_DATA | If the delay between bucket close and completed computation exceeds the configured SLA, the resulting rows are marked and a `STALE_DATA` health condition is recorded on the affected (symbol, exchange, metric) rather than silently emitting late values as if timely |
| Graceful shutdown preserved | The listener honors the same stop event as everything else; `main.py`'s existing `_run_cancellable` + SIGINT/SIGTERM handling is reused unchanged. Shutdown flushes the current bucket's watermark so restart catch-up resumes exactly where it stopped |
| Historical backfill isolated | Runs as a separate CLI process (§8.2), not inside the live listener, with its own DB pool — so a heavy bootstrap cannot exhaust the live path's connections |

A `stage2_state` value (`RUNNING` / `WARMING_UP` / `DEGRADED` / `STOPPED`)
is exposed in Redis alongside the existing `exchange_status` hash, so
`--stage2-validate` and later `/status` can report Stage 2 health without
inspecting logs — mirroring how Stage 1 already surfaces per-exchange
health.

**Queue overflow is a recoverable gap, not a loss.** Per §8.1a, drop-oldest
must enqueue the dropped bucket into `stage2_recompute_queue`. Dropping
without requeueing would silently lose a bucket, which is exactly the class
of failure this design is trying to eliminate.

## 10. `calculation_version` — computation identity (NEW 0.2)

**Problem.** With only `feature_schema_version` in the logical key, two
different configurations producing different numbers for the same bucket
would collide: recomputing under a new config **overwrites** the old
config's results in place. That destroys the ability to compare
configurations, breaks reproducibility of any historical evaluation run
that referenced the old numbers, and makes an ablation study impossible —
the very thing the plan requires in Phase 5.

**Definition.** `calculation_version` is a short deterministic digest over
the three things that can change a computed value:

```
calculation_version = sha256(
    canonical_json({
        "feature_schema_version": <int>,
        "config_hash":            <str>,   # sha256 of resolved config
        "code_version":           <str>,   # git describe / tag of the analytics code
    })
)[:16]
```

Properties:
- **Deterministic** — same three inputs always give the same value, on any
  machine, at any time. It is derived, never assigned by hand.
- **Part of the logical key** of `exchange_feature_vectors`,
  `consensus_feature_vectors`, `percentile_snapshots`, and
  `stage2_watermarks`.
- The three source fields remain stored as separate columns as well, so a
  human can see *why* two `calculation_version`s differ without reversing
  a hash.

**Consequences (intended):**
- A config change starts a **new, parallel result set**. Old results are
  retained, not overwritten. Comparing configs becomes a `GROUP BY
  calculation_version` query rather than an archaeology exercise.
- Watermarks are per `calculation_version`, so a new config begins its own
  progress line and `--stage2-backfill` will rebuild history under it
  without disturbing the previous line.
- Historical replay is reproducible by construction: pin the
  `calculation_version` and the numbers are exactly what they were.

**Consequence (must be managed):** storage multiplies per retained
`calculation_version`. Mitigations: `--stage2-validate` reports how many
distinct versions exist and their row counts; superseded versions are
prunable by an explicit, deliberate operation (never automatic — and not
before the retention decision is settled, per decision H); and in normal
operation the version only changes when config or code actually changes,
which is infrequent.

## 11. Consensus Contract — Revision 0.2.3 (FROZEN for Stage 2.1)

**Consensus Contract Revision 0.2.3 — frozen for Stage 2.1.** This section is
the single normative source for how `consensus_feature_vectors` values are
computed. It fully specifies the formulas that earlier revisions left open, and
**supersedes** the pre-0.2.3 language in `STAGE2_CLARIFICATIONS.md` §23.2 —
specifically the "initial proposal" confidence weights, the "configurable
weights" wording without a config path, any mention of *freshness* as a live
confidence component, the exchange-first `outlier_exchanges` example, the
ambiguous liquidation-quality source, and the binary (two-way) zero-direction
semantics. Where those older phrasings conflict with this section, this section
wins. The new config keys (`data_confidence.weights`, `outliers`) are part of
the resolved config and therefore of `config_hash` and `calculation_version`
(§10); changing any of them starts a new parallel result set.

The consensus core is pure/deterministic (no DB, network, clock, env,
subprocess, asyncio, global mutable state) and does **no** rounding internally.

### 11.1 Coverage (per family)

For each of the six families independently:

```
coverage_ratio = available / expected      # expected >= 1 required
```

`expected == 0` is an **invalid request**, not a working case. `available` is
the count of venues that supplied usable data *for this bucket*. The consensus
minimum is `defaults.data_confidence.minimum_exchange_coverage` (currently 2),
applied **independently per family**. When `available < minimum`:

- that family's numeric aggregates (medians, MADs, sums, direction agreement)
  are **NULL**;
- `coverage_by_metric` and `provenance_by_metric` are still written;
- the family confidence score is computed from the coverage component **only**.

### 11.2 Direction agreement

Directional source per family:

| Family | Sign source |
|---|---|
| `price_structure` | `price_move_pct` |
| `taker_flow` | `taker_delta_notional_usd` |
| `oi` | `oi_change_pct` |

`volume`, `funding`, `liquidations` have **no** direction-agreement component.

Sign is **ternary**: negative → −1, flat (exactly 0) → 0, positive → +1.

```
direction_agreement = max(negative_count, flat_count, positive_count) / available
```

An **all-zero** (all-flat) set of contributors scores **1.0** (unanimous flat),
not 0.0.

### 11.3 Dispersion

Dispersion source per family:

| Family | Dispersion source |
|---|---|
| `price_structure` | `price_move_pct` |
| `taker_flow` | `taker_delta_notional_usd` |
| `oi` | `oi_change_pct` |
| `funding` | `funding_rate` |

`volume`, `liquidations` have **no** dispersion component.

```
median = ordinary median of the per-exchange values
MAD    = median(abs(value - median))

dispersion_score =
    1.0                              if MAD == 0
    0.0                              if MAD > 0 and median == 0
    1.0 / (1.0 + MAD / abs(median))  otherwise
```

No epsilon; no internal rounding.

### 11.4 Data Confidence

Config (frozen; in `config_hash`):

```yaml
defaults:
  data_confidence:
    minimum_exchange_coverage: 2
    minimum_metric_coverage: 0.95      # upstream bar-completeness param, NOT a consensus gate
    weights:
      coverage: 0.50
      agreement: 0.30
      dispersion: 0.20
```

Weights are finite, `>= 0`, `coverage > 0`, and sum to exactly `1.0` (float
tolerance `1e-9`). `coverage_score = coverage_ratio` (0..1).

**Applicable component matrix** — a family uses only its applicable components,
with the applicable weights renormalized to their own sum:

| Family | coverage | agreement | dispersion |
|---|:--:|:--:|:--:|
| `price_structure` | ✓ | ✓ | ✓ |
| `volume` | ✓ | | |
| `taker_flow` | ✓ | ✓ | ✓ |
| `oi` | ✓ | ✓ | ✓ |
| `funding` | ✓ | | ✓ |
| `liquidations` | ✓ | | |

```
family_score = 100 * ( Σ_applicable weight_c * component_c ) / ( Σ_applicable weight_c )
```

When `available < minimum` for a family, agreement and dispersion are treated as
**unavailable** and the family score collapses to `coverage_score * 100`. All
six family scores lie in `[0, 100]`.

Roll-ups:

```
data_confidence_overall = arithmetic mean of the six family scores   # reporting only
consensus_confidence    = minimum of the six family scores           # 0..100
```

**Freshness is NOT a separate confidence component in Stage 2.1.** `STALE` and
`LATE_BAR` are represented as exclusion reasons in `provenance_by_metric` and
reduce **coverage**. Adding a distinct freshness component later is a versioned
change (new revision → new `calculation_version`).

### 11.5 Outliers

Config (frozen; in `config_hash`):

```yaml
defaults:
  outliers:
    robust_z_threshold: 3.5      # finite, > 0
```

The robust-z **scale constant is a fixed part of Revision 0.2.3**, baked into
the code (never config): `0.6744897501960817`.

```
robust_z = 0.6744897501960817 * (value - median) / MAD
```

Outlier metrics: `price_move_pct`, `oi_change_pct`, `funding_rate`. Detection
runs **only** for families that reached their minimum contributors.

- `MAD > 0`: `abs(robust_z) > robust_z_threshold` → outlier, reason
  `ROBUST_Z_THRESHOLD`. Equality to the threshold is **not** an outlier.
- `MAD == 0`: `value == median` → not an outlier; `value != median` → outlier
  with `robust_z = null`, reason `MAD_ZERO_NONMEDIAN`.

Outliers are **recorded, never removed**: they do not change contributors, the
aggregate, or coverage. Exact JSON shape (metric-first; keys sorted on write):

```json
{
  "<metric>": {
    "<exchange>": { "robust_z": <finite number or null>,
                    "reason": "ROBUST_Z_THRESHOLD" | "MAD_ZERO_NONMEDIAN" }
  }
}
```

One exchange may appear under several metric maps.

### 11.6 Liquidation feed quality

`liquidation_feed_quality_by_exchange` includes **all expected exchanges**, not
only contributors. The authoritative structural source is
`symbols.registry` `FamilyCapability.coverage_type`; bucket-level availability
comes from the EFV and does **not** replace capability quality. Example
historical-unavailable bucket: Binance `snapshot`, Bybit `full`, OKX
`aggregated`, while liquidation coverage is simultaneously `0/3`.

- **Contributing** exchange: if the EFV `liquidation_feed_quality` disagrees
  with the registry `coverage_type`, consensus computation **fails** (loud, no
  silent reconciliation).
- **Non-contributing historical** exchange: the EFV may be absent or carry
  `unavailable`; the output still uses the registry structural quality.

Feed quality never reduces availability/coverage automatically.

### 11.7 `is_usable` gating

EFV `is_usable` is required for contribution only for the **bar-derived**
families: `price_structure`, `volume`, `taker_flow`. For `oi`, `funding`,
`liquidations`, bar-level `is_usable` is **not** a gate — those sources can be
valid independently of a gap in the OHLC bucket.

### 11.8 Config authority

- Authoritative consensus minimum: `stage2` `defaults.data_confidence.minimum_exchange_coverage`.
- Stage 1's `consensus.price_oi_orderflow_min` is **not** used by the consensus core.
- `minimum_metric_coverage` is **not** used by the consensus core directly — it
  is an upstream bar-completeness / worker parameter.

### 11.9 Replay denominator (request contract — model not built here)

The future `ConsensusFeatureRequest` must receive an **explicit expected
exchange set per family** — the exact sorted/frozen set membership, not merely a
count. Constraints:

- each family's expected set is non-empty;
- exchanges are active/canonical only (Bitget absent);
- the available contributors are a subset of the expected set;
- the registry may be used for *validation*;
- historical replay must **not** silently recompute the denominator from the
  current registry — the denominator travels in the request so a replay is
  reproducible and any change flows through `calculation_version`.

The models themselves are not implemented in this step.

## 12. Percentile Contract — Revision 0.2.4 (FROZEN for Stage 2.1)

**Percentile Contract Revision 0.2.4 — frozen for Stage 2.1.** This section is
the single normative source for how `percentile_snapshots` values are computed.
It freezes every rule the future pure Percentile Engine needs so the
implementation is mechanical. Where earlier prose in this spec, the
implementation plan, or the clarifications differs, **this section wins** —
in particular it resolves the loose `(B − W, B)` phrasing in §8.3 to the exact
`[B − W, B)` membership defined below.

The percentile core is pure/deterministic: no DB, network, wall clock, env,
asyncio, subprocess, or global mutable state, and it does **no** internal
rounding. The caller supplies `bucket_ts`, full identity + version fields, the
current metric value, the historical samples, the window, and the confidence
thresholds; live and historical replay produce field-for-field equal logical
rows. The Percentile Engine is **not implemented in this revision** — this is a
contract-only freeze.

### 12.1 Percentile-rank definition

Rank a single `value` against a historical sample of earlier values using the
**mid-rank (mean) empirical definition**:

```
L = count(sample_values <  value)      # strictly less
E = count(sample_values == value)      # equal (ties)
N = sample_size                        # count of non-NULL earlier samples
percentile_rank = (L + 0.5 * E) / N    # range 0..1, NO internal rounding
```

Ties split symmetrically (the `0.5 * E` term). The output range is **0..1**
(not 0..100). Results are **not rounded** internally. The `value` being ranked
is the current bucket's value and is **not** a member of the sample.

Worked examples:

| sample | value | L | E | N | percentile_rank |
|---|---|---|---|---|---|
| `[1,2,3]` | 1 | 0 | 1 | 3 | `0.5/3 = 0.16666666666666666` |
| `[1,2,3]` | 2 | 1 | 1 | 3 | `1.5/3 = 0.5` |
| `[1,2,3]` | 3 | 2 | 1 | 3 | `2.5/3 = 0.8333333333333334` |
| `[1,2,2,3]` | 2 | 1 | 2 | 4 | `2.0/4 = 0.5` |
| all equal (`[5,5,5]`) | 5 | 0 | 3 | 3 | `1.5/3 = 0.5` |

### 12.2 Window membership and boundaries

For a snapshot at `bucket_ts = B` with window length `W` (`7d` or `30d`), a
historical sample `s` is in the distribution iff:

```
B − W  <=  s.bucket_ts  <  B          # lower bound INCLUSIVE, upper EXCLUSIVE
```

- The upper bound is strictly earlier (`< B`): the current and any future bucket
  are excluded by construction; compatible with the DB guard
  `sample_window_end IS NULL OR sample_window_end < bucket_ts`.
- The lower bound is **inclusive**: `bucket_ts − W` itself **does** participate.
  (This is the reading consistent with the §8.3 recompute rule
  `corrected_ts < B <= corrected_ts + W`.)
- `W` is exact: `7d = timedelta(days=7)`, `30d = timedelta(days=30)`.
- Supplying a sample with `s.bucket_ts >= B` (current or future) is an **invalid
  request** → typed error (never silently dropped).
- `sample_window_start` = the **earliest** included sample `bucket_ts`;
  `sample_window_end` = the **newest** included sample `bucket_ts` (data-derived,
  auditable). Both are `NULL` when the sample is empty.
- Empty sample (no earlier non-NULL values) → a **valid** snapshot with
  `sample_size = 0`, `percentile_rank = NULL`, `sample_window_start/end = NULL`,
  `confidence_tier = 'none'`.

### 12.3 Scope isolation

Two scopes, never mixed:

- `scope='exchange'` — `exchange` is a real active venue (non-empty); the
  distribution is that one venue's own history for the metric. Binance/Bybit/OKX
  histories are **never pooled**.
- `scope='consensus'` — `exchange = ''` (empty string); the distribution is the
  **consensus series' own history**, never a concatenation of per-venue values.

Every historical sample must match the request **exactly** on: `scope`, `symbol`,
`market_type`, `timeframe`, `metric`, `calculation_version`,
`feature_schema_version`, and — for `scope='exchange'` — `exchange`. A sample
mismatched on any of these is an **invalid request** → typed error (the input is
NOT treated as pre-filtered; the core validates and fails loudly, so pooling is
impossible). `scope='exchange'` with empty `exchange`, or `scope='consensus'`
with non-empty `exchange`, is invalid.

### 12.4 Metric allow-list and source-field mapping

Metric keys are the exact source column names. Frozen Stage 2.1 allow-list:

**`scope='exchange'`** (source: `ExchangeFeatureVector`):
`price_move_pct`, `range_width_pct`, `volume_notional_usd`,
`taker_buy_notional_usd`, `taker_sell_notional_usd`, `taker_delta_notional_usd`,
`cvd_delta_notional_usd`, `oi_change_pct`, `funding_rate`,
`long_liquidation_notional`, `short_liquidation_notional`,
`liquidation_event_count`.

**`scope='consensus'`** (source: `ConsensusFeatureVector`):
`price_move_pct_median`, `range_width_pct_median`, `oi_change_pct_median`,
`funding_rate_median`, `volume_notional_usd_sum`, `taker_buy_notional_usd_sum`,
`taker_sell_notional_usd_sum`, `taker_delta_notional_usd_sum`,
`cvd_delta_notional_usd_sum`, `observed_long_liquidation_notional_sum`,
`observed_short_liquidation_notional_sum`, `observed_liquidation_event_count_sum`.

Invariants: raw `volume_raw` (and `volume_raw_unit`) is **never** percentiled;
consensus **funding** percentile is over `funding_rate_median` (never a single
venue, never pooled raw rates); consensus metrics use the **consensus series'**
history; CVD uses the **windowed delta** (`cvd_delta_*`), never an accumulator;
liquidation metrics use the `observed_*` names; a NULL feature value is an
**absent observation**, never numeric zero. A metric outside the scope's
allow-list is an **invalid request** → typed error.

**Explicitly NOT percentiled in 2.1** (deferred future candidates, not invented
here): `close_price`, `volume_raw`, `oi_unit`, all `*_mad`,
`*_direction_agreement`, `data_confidence_*`, `consensus_confidence`,
`min_coverage_ratio`, `exchanges_expected_max`, `is_partial_consensus`, and the
coverage/provenance/outlier/liquidation-quality maps.

### 12.5 NULL / invalid-number behavior

- **Current value NULL** → valid snapshot: `value = NULL`, `percentile_rank =
  NULL`; `sample_size`/window/tier still computed from the earlier distribution.
- **Historical sample value NULL** → an absent observation: excluded from the
  distribution and **not** counted in `sample_size` (NULL ≠ 0).
- **NaN / +Inf / −Inf** in the current value or any sample → **invalid request**
  → typed error (never silently dropped or coerced).
- **Duplicate samples at the same `bucket_ts`**: identical value →
  deterministically collapsed to one; **conflicting** values at the same
  `bucket_ts` → **invalid request** → typed error.
- **Negative values** for signed metrics (e.g. `price_move_pct`,
  `taker_delta_*`, `oi_change_pct`, `funding_rate`) are valid and included.
- **Zero values** are valid measured values and are included.

Invalid *requests* (bad identity/version, out-of-window or future sample,
non-finite number, conflicting duplicate, unknown metric/scope) raise a typed
`PercentileError`. Merely *absent data* (empty sample, or current value NULL)
yields a valid snapshot with `percentile_rank = NULL`.

### 12.6 Sample size and confidence tier

`sample_size` = count of **non-NULL earlier** samples that entered the
distribution. The current value never counts toward `sample_size` (the
distribution is strictly earlier).

Confidence tier is a function of the **confidence span** — the age of the
oldest included sample measured against the snapshot bucket `B = bucket_ts`, NOT
against `sample_window_end`. Measuring `end − start` would be self-limiting:
because samples live in `[B − W, B)`, `end − start < W` always, so `building`
(7d) and `mature` (30d) would be mathematically unreachable. The correct span is:

```
confidence_span_days =
    0                                  if sample_size < 2
    (bucket_ts − sample_window_start) / 1 day   otherwise

tier =
  'none'      if confidence_span_days <  none_below_days
  'low'       if none_below_days     <= confidence_span_days <  low_below_days
  'building'  if low_below_days       <= confidence_span_days <  building_below_days
  'mature'    if confidence_span_days >= building_below_days
```

`sample_window_start` and `sample_window_end` remain **data-derived** for the
output schema (earliest / newest included `bucket_ts`); only the *tier* span is
measured against `bucket_ts`. `sample_window_end` is still strictly earlier than
`bucket_ts` (upper bound exclusive), and the current bucket still never enters
`sample_size`.

Thresholds are Stage-2 config (§12.8), frozen default `none_below_days=3`,
`low_below_days=7`, `building_below_days=30` — numerically identical to Stage 1's
`storage/validate.py::_confidence_tier`, but **sourced from Stage 2 config** so
the pure core never reads the Stage 1 `Config`. Tier is **span-based, not
row-count-based** in 2.1 (a deliberate, documented choice; row-count gating is a
deferred future revision, not invented here).

Frozen worked examples (thresholds 3 / 7 / 30; `B = bucket_ts`):

| # | history | `sample_size` | `sample_window_start` | `confidence_span_days` | tier |
|---|---|---|---|---|---|
| 1 | one sample | 1 | that sample's ts | `0` (size < 2) | `none` |
| 2 | ≥ 2 samples, earliest exactly `B − 3d` | ≥ 2 | `B − 3d` | `3` | `low` |
| 3 | complete 7d window beginning exactly at `B − 7d` | many | `B − 7d` | `7` | `building` |
| 4 | complete 30d window beginning exactly at `B − 30d` | many | `B − 30d` | `30` | `mature` |
| 5 | earliest sample one minute later than `B − 30d` | many | `B − 30d + 1m` | `≈29.999` | `building` |

**Window-reachability (frozen):** because a `W`-day window's oldest possible
sample is at `B − W` (lower bound inclusive), `confidence_span_days` reaches at
most `W`. Therefore the **7d** percentile window can reach at most `building`,
and only the **30d** window can reach `mature`. Both windows use the same tier
function over their own included samples.

### 12.7 Determinism, purity, and the request contract

The future `PercentileRequest` carries: `scope`, `exchange` (`''` for consensus),
`symbol`, `market_type`, `metric`, `timeframe`, `percentile_window`,
`bucket_ts`, the current `value` (nullable), the historical `samples`
(each `bucket_ts` + nullable value, with identity fields for validation), the
confidence-tier thresholds, and the version quadruple (`config_hash`,
`config_version`, `code_version`, `feature_schema_version`,
`calculation_version`). Input order of samples does not affect output. No DB,
network, wall clock, env, asyncio, subprocess, or global mutable state; no
internal rounding. Nested request/output structures are deeply immutable.

### 12.8 Config surface (Stage 2, frozen)

```yaml
defaults:
  percentile_windows: [7d, 30d]     # authoritative window key (unchanged)
  percentiles:
    confidence_tiers:               # the ONLY key under `percentiles`
      none_below_days: 3            # span < 3d  -> 'none'
      low_below_days: 7             # [3, 7)     -> 'low'
      building_below_days: 30       # [7, 30)    -> 'building'; >= 30 -> 'mature'
```

There is no `percentiles.windows` key — the window list stays at
`defaults.percentile_windows`. `defaults.percentiles` accepts **only**
`confidence_tiers`; any other key is rejected.

Validation (in `common/stage2_config.py`): three ints, each `> 0` (bool
rejected), **strictly increasing** (`none_below < low_below < building_below`).
These keys enter the resolved config and therefore `config_hash` /
`calculation_version` (§10) — changing a threshold starts a new parallel result
set, consistent with `calculation_version` being in the `percentile_snapshots`
key.

### 12.9 Output / schema parity

The future pure output model mirrors the `percentile_snapshots` columns **except
`computed_at`** (DB default/writer): `scope`, `exchange`, `symbol`,
`market_type`, `metric`, `timeframe`, `percentile_window`, `bucket_ts`, `value`,
`percentile_rank`, `sample_size`, `sample_window_start`, `sample_window_end`,
`confidence_tier`, `config_hash`, `config_version`, `code_version`,
`feature_schema_version`, `calculation_version`. No invented columns.


## 13. Data Quality & Gap Detection Contract — Revision 0.2.5 (FROZEN for Stage 2.1)

**Data Quality Contract Revision 0.2.5 — frozen for Stage 2.1.** This section is
the single normative source for how `data_health_snapshots` values are computed.
It freezes every health / gap rule so the future
`analytics/data_quality/{health,gaps}.py` is mechanical. Where earlier prose in
this spec, the implementation plan, the clarifications, or the data audit
differs, **this section wins**. The Data Quality core is **not implemented in
this revision** — this is a contract-only freeze.

The core is pure/deterministic: no DB, network, wall clock, env, Redis, asyncio,
subprocess, or global mutable state, and it does **no** internal rounding of the
classification math. **The caller supplies everything**: identity, `snapshot_ts`
(the reference "now"), the per-metric capability facts, `expected_interval_s`,
connection/backfill state, the configuration thresholds, and the observation
timestamps. Same logical input → same output; observation order does not matter;
live and historical replay produce field-for-field equal logical rows.

Operational health is **separate from percentile-history maturity**. Data
Quality answers *"is this metric's recent raw feed usable right now?"* It does
**not** measure how many days of history exist and it does **not** feed the
percentile `confidence_tier` — historical maturity belongs **exclusively** to
Percentile Contract §12 (`confidence_tier`). An operationally healthy metric is
usable regardless of percentile-history maturity; backfill completeness is
represented separately by `backfill_status` (§13.9).

### 13.1 Snapshot identity and cadence

- **Identity / PK** (matches `data_health_snapshots`): `(symbol, exchange,
  market_type, metric, snapshot_ts, calculation_version)`.
- `snapshot_ts` is the **END** of the health interval — the reference time
  against which freshness is measured. Deterministic: timezone-aware **UTC**
  (offset 0), aligned to the health **cadence** (`(epoch_seconds % cadence_s) ==
  0`, whole second, zero microsecond). A non-aligned / non-UTC / naive
  `snapshot_ts` is an invalid request.
- **Cadence is global** (`data_quality.cadence_s`, one health stream) — NOT per
  metric or per symbol.
- **Replay**: because `snapshot_ts` and all inputs are supplied, a replay
  produces identical logical rows. `computed_at` is wall-clock **metadata only**
  and is NOT part of the key.
- **Two calculation versions coexist**: `calculation_version` is in the PK, so a
  snapshot under a new config/threshold set is a parallel row (§13.10).
- Output model = the `data_health_snapshots` columns **except `computed_at`**
  (§13.11).

### 13.2 Health status model (booleans persisted; labels derived)

The schema persists **booleans + numeric facts**, not a status string. The
report classification (§13.5) is **derived** for `--stage2-validate`, never a new
column. Persisted: `is_stale`, `is_usable`, `lateness_ms`, `last_event_at`,
`expected_interval_s`, `gap_count`, `largest_gap_s`, `coverage_window_start`,
`coverage_window_end`, `backfill_status`.

### 13.3 Health metrics, source mapping, and `expected_interval_s`

Stage 2.1 health is computed on **raw Stage 1 sources**. The raw timestamp column
is **`ts`** in every source table (`storage/schema.sql`):

| health `metric` | raw table | source ts col | serves families | continuous? | freshness-gated? |
|---|---|---|---|---|---|
| `ohlcv` | `klines_1m` | `ts` | price_structure **and** volume | yes | yes |
| `taker_flow` | `klines_1m` (taker cols) | `ts` | taker_flow | yes | yes |
| `open_interest` | `open_interest` | `ts` | oi | yes | yes |
| `funding` | `funding_rate` | `ts` | funding | yes | yes |
| `liquidations` | `liquidations` | `ts` | liquidations | **no (event-driven)** | **no** |

- **`price_structure` and `volume` share the same raw bars → ONE `ohlcv` health
  row.** `volume`'s missing-`contract_multiplier` degradation is a feature-layer
  concern (`MISSING_CONTRACT_MULTIPLIER`), not a data-health condition.
- `mark_price` is ingested by Stage 1 but not consumed by Stage 2 cores → **out
  of Stage 2.1 health scope**.
- An **observation** = the `ts` of a raw row whose payload is **complete for that
  metric**. A present `klines_1m` row with NULL taker columns is not a
  `taker_flow` observation (absent for taker_flow, present for ohlcv).

**`expected_interval_s` — authoritative source (frozen).** `expected_interval_s`
is an **explicit, required, validated request input** for continuous metrics
(and `NULL` for `liquidations`). The caller MUST derive it from the frozen
`(metric, source_mode)` mapping below, whose values come from the actual repo —
never from the freshness budget, never invented. `source_mode ∈ {live,
historical}` is a required discriminator on the request.

| metric | `live` interval_s | `historical` interval_s | repo authority |
|---|---|---|---|
| `ohlcv` | 60 | 60 | `config.candles.klines_interval = 1m`; 1-minute bars, same live and backfill |
| `taker_flow` | 60 | 60 | same `klines_1m` bars (taker columns) |
| `open_interest` | 15 | 300 | client `poll_interval_s = 15.0` (live REST poll); `config.candles.oi_history_interval_fallback = 5m` (backfill) |
| `funding` | 15 | 28800 | client `poll_interval_s = 15.0` (live poll writes a `funding_rate` row each poll); historical funding-rate history is per 8-hour settlement |
| `liquidations` | `NULL` | `NULL` | event-driven — no interval (§13.4) |

The core **validates** `expected_interval_s`: it must be a positive int for a
continuous metric and `NULL` for `liquidations`; the `(metric, source_mode)` pair
must be one of the rows above. Invalid combinations (continuous metric with
`NULL` interval, `liquidations` with a non-`NULL` interval, an interval not
matching the mapping for the given mode) are invalid requests. The supplied
`expected_interval_s` is **echoed** to the output column. When
`common/capabilities.py` / `exchange_capabilities` is later extended to also
carry `expected_interval_s`, that becomes the storage of this same mapping; until
then this table is authoritative and the value travels in the request.

Freshness budgets remain the capability `expected_freshness_s`
(`common/capabilities.py`: 120s for `ohlcv`/`taker_flow`, 60s for
`open_interest`/`funding`, `NULL` for `liquidations`), supplied per request and
**never** reused as the interval.

### 13.4 Liquidations (event-driven; connection-based, fail-closed)

Liquidation health is **never** time-since-last-event. `is_stale` is **always
false**, `gap_count = 0`, `largest_gap_s = NULL`, `expected_interval_s = NULL`.
Usability is **fail-closed**: positive usability requires explicit healthy
connection evidence. **Precedence (first match wins):**

1. **structural unavailable** — `not live_supported` OR `coverage_type ==
   'unavailable'` → `is_usable=false`, label `not_available`.
2. **historical-unavailable** — `is_historical_bucket == true` (never
   backfilled) → `is_usable=false`, label `unavailable_historical`.
3. **connection down** — `connection_up == false` → `is_usable=false`, label
   `disconnected`.
4. **connection unknown** — `connection_up is None` → `is_usable=false`, label
   `connection_unknown` (absence of positive evidence is not health).
5. **connection up** — `connection_up == true` → `is_usable=true` (quiet
   connected feed with zero events is usable), label `ok`.

`last_event_at` = newest liquidation observation in window (or `NULL`). A `NULL`
`last_event_at` on a healthy connected feed is absence of events — never a
measured zero and never staleness.

### 13.5 Derived report classification (complete, ordered, mutually exclusive)

The report label is the **first** matching rule (highest precedence first). Not a
schema column. Continuous metrics never take liquidation-only labels and vice
versa.

| # | label | condition |
|---|---|---|
| 1 | `not_available` | `not live_supported` OR `coverage_type == 'unavailable'` |
| 2 | `unavailable_historical` | event-driven metric, `is_historical_bucket == true` |
| 3 | `disconnected` | event-driven, structurally available, `connection_up == false` |
| 4 | `connection_unknown` | event-driven, structurally available, `connection_up is None` |
| 5 | `no_data` | continuous, structurally available, zero observations |
| 6 | `stale` | continuous, `is_stale == true` |
| 7 | `gap_exceeded` | continuous, `largest_gap_s is not NULL and largest_gap_s > max_usable_gap_s` |
| 8 | `ok` | none of the above |

**Report inputs.** Labels 1–4 require the **capability + connection inputs**
(`live_supported`, `coverage_type`, `is_historical_bucket`, `connection_up`) in
addition to the persisted snapshot — they are **not** reconstructable from the
persisted fields alone (`not_available` and `no_data` both persist as
`is_usable=false`, `last_event_at=NULL`). Labels 5–8 are derivable from persisted
fields alone. The report therefore joins the snapshot with the capability
registry / supplied connection state; the snapshot deliberately does not
duplicate those facts. **No `status` column is added.**

### 13.6 Freshness (`lateness_ms`, `is_stale`)

Reference time is **`snapshot_ts`** (never a wall clock). Budget = supplied
capability `expected_freshness_s` (`NULL` for event-driven).

```
last_event_at = max(observation_ts)   or NULL if no observations
lateness_ms   = NULL                                     if last_event_at is NULL
              = whole milliseconds in (snapshot_ts − last_event_at)   otherwise
                # days*86400000 + seconds*1000 + microseconds//1000  (floor to ms)
is_stale = (last_event_at is not NULL)
           and (freshness_budget_s is not NULL)          # event-driven never stale
           and (lateness_ms > freshness_budget_s * 1000) # boundary EXCLUSIVE
```

Exactly at budget → fresh (`>` strict). `last_event_at is NULL` → `is_stale=
false` (that is `no_data`). Negative lateness is impossible: an observation `>=
snapshot_ts` is an invalid request (§13.8). Freshness is per-metric independent.

### 13.7 Gap detection (interval-based; continuous metrics only)

Interval-based (aligned with the Stage-1-documented `lead(ts) − ts > interval`,
`STAGE2_DATA_AUDIT.md` §4). Liquidations are exempt (§13.4).

Let `I = expected_interval_s`, `factor = gap_tolerance_factor`, over the in-window
observation timestamps (deduped, sorted). For each pair of **consecutive**
observations with exact delta `d` seconds (microsecond precision):

```
gap_detected(d) = d > I * factor                # exact seconds, no rounding here
gap_count       = number of consecutive pairs with gap_detected == true   # contiguous runs
largest_gap_s   = ceil( max{ d : gap_detected(d) } )   in whole seconds   # NULL if no gaps
gap_exceeded    = (largest_gap_s is not NULL) and (largest_gap_s > max_usable_gap_s)
```

- **`gap_count` counts contiguous gap runs** (each oversized consecutive delta is
  one run), NOT the number of missing points. One missing point → one run of one
  oversized delta; two *adjacent* missing points → still **one** run (one larger
  delta); two *separated* holes → two runs.
- **`largest_gap_s` uses `ceil`** so a fractional gap just above a threshold
  cannot be rounded down into "usable": exact `300.000s` → `300`; `300.001s` →
  `301`. This keeps the persisted integer and the `gap_exceeded` classification
  consistent and safety-preserving.
- **Edges are not interior gaps**: the span from `coverage_window_start` to the
  first observation, and from the last observation to `snapshot_ts`, are covered
  by presence / freshness, not `gap_count`.

### 13.8 Coverage window and observation validity

- `coverage_window_end = snapshot_ts`; `coverage_window_start = snapshot_ts −
  coverage_window_s` (config, default `86400` = 24h). Deterministic.
- Observations must satisfy `coverage_window_start <= ts < snapshot_ts` (lower
  inclusive, upper exclusive). A `ts >= snapshot_ts` (current/future) or `ts <
  coverage_window_start` is an **invalid request** (never silently discarded).
  Off-grid / jittery poll timestamps are allowed (interval-based needs no grid).
  Duplicate timestamps **collapse** deterministically; order is irrelevant.
- **Empty window** → a **valid** snapshot: `last_event_at=NULL`,
  `lateness_ms=NULL`, `gap_count=0`, `largest_gap_s=NULL`, `is_stale=false`,
  `is_usable=false` (unless event-driven with `connection_up == true`), with
  `coverage_window_start/end` populated.
- The health **coverage window** (recent operational health) is **distinct** from
  the percentile **windows** (7d/30d distribution history, §12).

### 13.9 `is_usable` (per-exchange, per-metric)

Per-metric gate — does **not** reuse the consensus `minimum_exchange_coverage`,
and does **not** consider percentile-history maturity.

`is_usable = false` when **any** of:
- structurally unavailable (`not live_supported` OR `coverage_type ==
  'unavailable'`);
- event-driven and not positively connected (`connection_up != true`, §13.4) or
  `is_historical_bucket == true`;
- continuous `no_data` (zero observations);
- continuous `is_stale == true`;
- continuous `gap_exceeded` (`largest_gap_s > max_usable_gap_s`).

`is_usable = true` otherwise — including a valid **partial** history (interior
gaps within tolerance) and an event-driven **quiet connected** feed. Percentile
maturity never affects `is_usable`.

### 13.10 `backfill_status`

An **orchestration input**, validated and echoed — the pure core does **not**
infer a running process from observation timestamps. Allowed normalized values
(`NULL` = not tracked): `not_applicable`, `not_started`, `in_progress`,
`complete`, `partial`, `failed`. Frozen mapping from Stage 1 orchestration state:

| Stage 1 backfill run state | normalized `backfill_status` |
|---|---|
| running | `in_progress` |
| complete | `complete` |
| partial | `partial` |
| failed | `failed` |
| no run yet | `not_started` |
| not supported / live-only metric | `not_applicable` |

### 13.11 Calculation-version isolation

Health classification is config-dependent: the `data_quality` thresholds enter
the resolved config → `config_hash` → `calculation_version` (§10). Snapshots
under different `calculation_version`s **coexist** (PK). **Raw observations are
NOT calculation-versioned**: they carry only their raw identity dimensions
(`exchange`, `symbol`, `market_type`, `metric`, `ts`, value) and are validated
only on those + timestamp/value semantics. The **same** raw history is reused to
compute multiple parallel snapshots under different `calculation_version`s;
changing a threshold recomputes a separate output row from that same raw history.
There is **no `calculation_version` on Stage 1 raw data** and no rule rejecting a
"mismatched" observation version. `calculation_version` belongs to the Data
Quality **request and output snapshot only**.

### 13.12 Output / schema parity

Output mirrors `data_health_snapshots` **except `computed_at`**: `symbol`,
`exchange`, `market_type`, `metric`, `snapshot_ts`, `last_event_at`,
`expected_interval_s`, `lateness_ms`, `gap_count`, `largest_gap_s`,
`backfill_status`, `coverage_window_start`, `coverage_window_end`, `is_stale`,
`is_usable`, `config_hash`, `config_version`, `code_version`,
`feature_schema_version`, `calculation_version`. No invented columns.

### 13.13 Config surface (Stage 2, frozen)

```yaml
defaults:
  data_quality:
    cadence_s: 60              # health snapshot cadence + snapshot_ts alignment (global)
    coverage_window_s: 86400   # health coverage window length (24h)
    gap_tolerance_factor: 1.5  # consecutive delta > interval * factor => a gap
    max_usable_gap_s: 300      # largest interior gap over this => is_usable=false
```

`data_quality` accepts **only** these four keys (any other rejected). There is
**no `short_history_min_days`** — historical maturity is Percentile §12, not Data
Quality. Validation (`common/stage2_config.py`): `cadence_s`,
`coverage_window_s`, `max_usable_gap_s` are ints `> 0`; `gap_tolerance_factor` is
a finite number `> 1`; bool rejected everywhere. All four enter `config_hash` /
`calculation_version`. Per-metric `expected_interval_s` (§13.3) and
`freshness_budget_s` are supplied per request, never in this config.

### 13.14 Errors

Typed `DataQualityError` for invalid **requests**: bad identity / version fields;
non-UTC / non-cadence-aligned / naive `snapshot_ts`; unknown metric; unknown
`backfill_status`; an observation out of window or at/after `snapshot_ts`; a
non-finite (NaN/±Inf) or bool numeric input; an invalid
`(metric, source_mode, expected_interval_s)` combination; an invalid config
threshold. Merely **absent data** (empty window, quiet connected feed, NULL
`last_event_at`) yields a **valid** snapshot per the rules above — absence is
never an error and never a zero.

### 13.15 Worked examples

Defaults: `cadence_s=60`, `coverage_window_s=86400` (24h), `gap_tolerance_factor=
1.5`, `max_usable_gap_s=300`; `S = snapshot_ts`. **Every observation lies inside
`[S − 86400s, S)`.**

1. **24h healthy OHLCV** — `ohlcv` `live`, `I=60`, a bar every minute across the
   whole 24h window, newest at `S−60s`: `lateness_ms=60000 ≤ 120000` →
   `is_stale=false`; consecutive deltas all `60s ≤ 90s` → `gap_count=0`,
   `largest_gap_s=NULL`; `is_usable=true`; label `ok`.
2. **Exact freshness boundary** — newest at `S−120s`, budget 120s →
   `lateness_ms=120000`, `120000 > 120000` false → `is_stale=false`, `ok`.
3. **1 ms beyond freshness** — newest at `S−120.001s` → `lateness_ms=120001 >
   120000` → `is_stale=true`, `is_usable=false`, label `stale`.
4. **No-data continuous** — `open_interest` `live`, structurally available, zero
   observations in window → `last_event_at=NULL`, `lateness_ms=NULL`,
   `is_stale=false`, `gap_count=0`, `is_usable=false`, label `no_data`.
5. **Structural unavailable** — `liquidations` on `bitget`
   (`live_supported=false`/`coverage_type='unavailable'`) → `is_usable=false`,
   label `not_available`.
6. **One missing point** — `ohlcv` `I=60`; bars at `…, S−180s, S−60s` (the
   `S−120s` bar missing): one delta `120s > 90s` → `gap_count=1`,
   `largest_gap_s=ceil(120)=120`; `120 ≤ 300` → not exceeded, `is_usable=true`.
7. **Two adjacent missing points** — bars at `…, S−240s, S−60s` (two missing):
   one delta `180s > 90s` → `gap_count=1`, `largest_gap_s=180`, usable.
8. **Two separated gap runs** — two distinct oversized deltas `120s` and `180s` →
   `gap_count=2`, `largest_gap_s=180`, usable.
9. **Exact max-usable gap** — largest interior delta exactly `300.000s` →
   `largest_gap_s=ceil(300.000)=300`; `300 > 300` false → **not** exceeded,
   `is_usable=true` (`gap_count≥1`, label `ok`).
10. **Fractional gap just above max** — largest interior delta `300.001s` →
    `largest_gap_s=ceil(300.001)=301`; `301 > 300` → `gap_exceeded`,
    `is_usable=false`, label `gap_exceeded`.
11. **Quiet connected liquidations** — `live_supported`, `connection_up=true`,
    zero events → `is_stale=false`, `gap_count=0`, `expected_interval_s=NULL`,
    `last_event_at=NULL`, `is_usable=true`, label `ok`.
12. **Disconnected liquidations** — `connection_up=false` → `is_usable=false`,
    label `disconnected` (still `is_stale=false`).
13. **Unknown-connection liquidations** — `connection_up is None` → **fail-closed**
    `is_usable=false`, label `connection_unknown`.
14. **Historical-unavailable liquidations** — `is_historical_bucket=true` (never
    backfilled) → `is_usable=false`, `last_event_at=NULL`, label
    `unavailable_historical`.
15. **Two calculation versions from identical raw data** — the same 24h `ohlcv`
    history with a largest interior gap `largest_gap_s=200`. Config A
    `max_usable_gap_s=300` → `200 > 300` false → `is_usable=true`; config B
    `max_usable_gap_s=150` → `200 > 150` → `gap_exceeded`, `is_usable=false`. A
    and B differ in `config_hash` → different `calculation_version`; both rows
    **coexist** with opposite verdicts, computed from the **same** raw
    observations (which carry no calculation_version).
