# Stage 1 — Acceptance Record

**Status:** ACCEPTED with one known exception (Bitget 30d historical klines
backfill deferred by product owner).
**Date:** 2026-07-16
**Scope:** `data_ingestion` + `backfill` + `storage`. `percentile_engine` and
`signal_engine` are intentionally NOT part of this stage.
**Git tag:** `stage1-accepted-bitget-deferred` (rollback point:
`stage1-fixes-start`).

> **Amendment (2026-07-17) — 3-exchange MVP.** Bitget is now DISABLED from the
> active MVP via `config.enabled_exchanges: [binance, bybit, okx]` (tags
> `pre-disable-bitget` → `stage1-three-exchanges`). Disabled means: no WS, no
> REST poll, no backfill/gap-fill, not counted in coverage, not shown as
> stale/error, and excluded from percentile voting (`exchange_capabilities.
> enabled=false`). Bitget's stored data and client code are retained. Consensus
> is now over 3 active exchanges: normal ≥2/3, strong 3/3, 1/3 forbids a signal,
> `liquidations_min_sources=2`. Re-enable criteria unchanged — see §5.

---

## 1. What was verified

### Data captured per exchange (Binance, Bybit, OKX, Bitget)
- OHLCV 1m bars (live + 30d REST backfill; Bitget historical deferred — see §4).
- Taker buy/sell split — live for all 4 (computed from trades); historical only
  Binance (others left NULL, never faked).
- Open interest — live (REST poll) for all 4; historical for Binance (~29d) and
  Bybit; OKX/Bitget live-only (no verified 30d endpoint).
- Funding — live + historical for all 4.
- Mark price — live for all 4; historical for Binance/Bybit/OKX; Bitget live-only.
- Liquidations — live only, never backfilled. Real coverage differs by venue
  (see capability registry): Bybit `full`, OKX `aggregated`, Binance `snapshot`,
  Bitget `unavailable`.
- Availability/coverage — Redis `exchange_status` (live) + `connectivity_events`.

### Normalization
- Timestamps: all tables `TIMESTAMPTZ` in UTC.
- OI units: raw values are NOT summed across exchanges. `open_interest` stores
  `oi_raw` + `oi_unit` (base/contracts) + `contract_value` + `oi_base_asset` +
  `oi_notional_usd`. USD is stored only where the exchange provides it directly
  (Bybit `openInterestValue`, OKX `oiUsd`, Binance historical
  `sumOpenInterestValue`); no coefficients are assumed — unknown normalized
  values stay NULL. Verified live: Binance/Bybit/Bitget report base (BTC), OKX
  reports contracts (ctVal 0.01 verified) — never mixed.

### Aggregates
- Continuous aggregates: `klines_5m`, `klines_15m`, `klines_1h`, **`klines_4h`**
  (4h added this stage; idempotent, existing data preserved).

### State distinctions (validate)
- Distinguishes real-zero vs absent-source (`not_available`) vs `NO_DATA`
  (supported but empty) vs `STALE` (older than freshness budget) vs
  `short_history` (partial 30d coverage).
- Per-metric freshness reported separately for ohlcv/taker_flow/open_interest/
  funding/mark_price.
- Liquidations handled as event-driven: a quiet feed is never marked
  stale/unavailable; capability, coverage_type, connection health, events in
  window and last-event time are shown separately.
- Coverage shown per metric; price/OI/order-flow flagged below the 3-exchange
  consensus minimum. Taker-flow data-confidence tier shown per exchange with a
  gate ON/OFF flag for the future percentile_engine.

### Percentile separability
- All raw tables keyed `(exchange, symbol, ts)`; exchange data never mixed, so
  per-exchange percentiles are computable without blending incomparable values.

### Reliability / shutdown
- SIGINT/SIGTERM handlers installed before backfill; backfill/gap-fill are
  cancellable. `db.close()` force-terminates the pool on timeout. Startup sweeps
  any leftover `running` backfill rows to `cancelled`.
- Verified: SIGINT mid-backfill leaves no `idle in transaction`, no ungranted
  locks, DB immediately usable (`scripts/test_shutdown.py` → PASS).

### Key fixes made this stage
- Bitget klines: `/history-candles` (200/req, backward paging) — was capped at 1000.
- Binance historical OI: probe + clamp to now−29d23h, honest `partial` note —
  was `failed` HTTP 400 (−1130).
- Bybit historical mark price: dedicated `mark-price-kline` — was 0 rows.
- Bybit live: subscribe `allLiquidation.{symbol}` — the removed `liquidation.`
  topic had killed the whole subscription (0 live bars).
- **Binance live: WS category `/market/stream`** (aggTrade/forceOrder), not
  `/public/stream`. The earlier "EEA geoblock" conclusion was a mis-diagnosis;
  verified `/market` delivers aggTrade (0 on `/public`).
- Parallel backfill + post-backfill gap-fill (closes backfill→live gap).
- Structural capability registry (`exchange_capabilities`), seeded from
  `common/capabilities.py`, queried via SQL (not the client classes).

---

## 2. Testing commands

```bash
# Infra
docker compose up -d

# Backfill (idempotent; skips completed sources)
python main.py --backfill-only

# Live ingestion (Ctrl+C / SIGINT to stop cleanly)
python main.py --skip-backfill

# Read-only validation report (per-metric freshness, coverage, confidence)
python main.py --validate

# Shutdown safety test (SIGINT mid-backfill; asserts no locks / idle-in-tx)
python scripts/test_shutdown.py

# 1-hour soak
timeout --signal=INT 3600s python main.py --skip-backfill 2>&1 | tee soak-test-1h.log
python main.py --validate
```

Useful SQL:
```sql
SELECT exchange, source, count(*), min(ts), max(ts) FROM klines_1m GROUP BY 1,2;
SELECT exchange, oi_unit, count(*), count(oi_notional_usd) FROM open_interest GROUP BY 1,2;
SELECT * FROM exchange_capabilities ORDER BY exchange, metric;
-- gap check per exchange (internal missing minutes):
SELECT exchange, count(*) gaps FROM (
  SELECT exchange, ts, lead(ts) OVER (PARTITION BY exchange ORDER BY ts) - ts AS d
  FROM klines_1m WHERE symbol='BTCUSDT') t
WHERE d > interval '60 seconds' GROUP BY exchange;
```

---

## 3. 1-hour soak test result

Run: `timeout --signal=INT 3600s python main.py --skip-backfill` — ran the full
window 2026-07-16 22:18Z → 23:18Z, then a clean SIGINT shutdown. A live
`--validate` snapshot was taken immediately after.

Per-exchange over the soak hour:

| exchange | live bars | taker bars | internal gaps | liquidations |
|----------|-----------|------------|---------------|--------------|
| binance  | 61 | 61 | 0 | 90 |
| bybit    | 61 | 61 | 0 | 26 |
| okx      | 61 | 61 | 0 | 0 (aggregated feed quiet this hour) |
| bitget   | 60 | 60 | 1 (one 120s gap on a WS reconnect) | 0 (unavailable) |

Checks required and their outcomes:
- fresh live bars 4/4 — **PASS** (validate ohlcv 4/4 `ok`)
- taker flow 4/4 — **PASS** (validate taker_flow 4/4 `ok`; every live bar had a split)
- Bitget reconnect does not stop writes — **PASS** (survived ~19 server-side
  `no close frame` disconnects, kept writing: 60 bars over the hour)
- gaps do not grow — **PASS for binance/bybit/okx (0 gaps)**; bitget had a single
  1-minute gap on one reconnect (not accumulating). See limitation §4.6.
- no idle in transaction — **PASS** (0)
- no ungranted locks — **PASS** (0)
- no unexplained errors — **PASS**. Only explained warnings: bitget periodic WS
  reconnect (auto-recovered), and 2 one-off DNS blips
  (`Temporary failure in name resolution`) caught by the poll loop and retried.

Liquidations behaved as event-driven sources should: real events arrived
(binance 90, bybit 26), OKX's aggregated feed was quiet (0) and was reported as
`supported`/`conn+healthy`, NOT stale; bitget `unavailable`.

Full logs: `soak-test-1h.log` (gitignored).

---

## 4. Known limitations

1. **Bitget 30d historical klines — DEFERRED** by product owner. Bitget live 1m
   bars work; historical depth is currently short (~ intraday). Refill is a
   single ~2-minute background run of `_klines_bitget` over the 30d window
   (216 pages @ 200/req). Real persisted count is tracked in `klines_1m`
   (source='backfill'); the pre-fix run's bookkeeping was corrected to
   `partial`/`cancelled`, existing bars kept.
2. **Historical OI**: OKX and Bitget have no verified public 30d OI endpoint —
   marked `partial`, accumulate live from process start (not faked).
3. **Historical mark price**: Bitget has no verified endpoint — live-only.
4. **Liquidations** are a full consensus source on only Bybit (`full`) and,
   with caveats, OKX (`aggregated`); Binance is `snapshot` (under-counts
   cascades) and Bitget is `unavailable`. Consensus therefore uses
   `liquidations_min_sources: 2`.
5. **Binance live** requires the `/market` WS path; `/public` silently returns
   no trades (not a geoblock — a category difference).
6. **Bitget WS reconnects** ~every 2.5 min (server sends no close frame); the
   client auto-reconnects and keeps writing, but the in-progress 1m bar can be
   lost if a minute boundary falls inside the reconnect — observed as 1 missing
   bar over the 1h soak (60/61). Not silent zero-fill (the gap is visible) and
   not accumulating. Startup gap-fill closes such gaps; a periodic gap-fill (or
   process supervisor) is the recommended self-heal for long-running operation
   (candidate for stage 2 / ops hardening).

---

## 5. Criteria for including Bitget in percentile voting

Bitget is a valid **price / OHLCV / taker-flow / OI** venue (it is NOT a valid
liquidations source — `coverage_type: unavailable`). It is included in a given
metric's multi-exchange percentile voting only when ALL of the following hold
for **that metric**:

1. **Capability**: `exchange_capabilities.live_supported = true` for the metric
   (true for ohlcv/taker_flow/open_interest; false for liquidations → never
   votes on liquidations).
2. **Sufficient history for percentiles**: the per-exchange sample span for the
   metric ≥ `percentiles.min_days_for_confidence` (3d) — i.e. data-confidence
   tier ≥ `low`. Below that, the percentile is not yet meaningful and Bitget is
   excluded / its gate is OFF (same rule applied to all live-only sources).
   - OHLCV/price: needs Bitget klines covering the percentile window. Until the
     deferred 30d backfill runs, this is met only after ≥3d of live+gap-filled
     bars accumulate (or immediately once the 30d refill is done).
   - Taker flow: live-only for Bitget → gate OFF until ≥3d live taker history.
   - OI: live-only for Bitget → OI percentile valid only after ≥3d live OI.
3. **Freshness**: the metric is currently fresh (within its freshness budget) so
   Bitget counts toward live coverage at decision time.
4. **No internal gaps** materially breaking the percentile window (validate
   gap check clean for the window in use).

Until (2) is satisfied per metric, Bitget contributes to raw ingestion/storage
but is excluded from that metric's percentile voting, and the price/OI/order-
flow consensus is met by the other three venues (min 3).
