# Stage 2 — Data Audit (Phase 0)

Source reviewed: full read-only copy of `/opt/signalbot` at the current HEAD
(tag lineage: `stage1-accepted-bitget-deferred` → `stage1-three-exchanges`).
No production code, schema, or systemd config was modified to produce this
document.

## 1. Current architecture

Single Python 3.12 asyncio process (`main.py`), four flat top-level packages:

- `common/` — `config.py` (YAML + `.env` loader, `Config` dataclass wrapper),
  `capabilities.py` (declarative exchange×metric capability table),
  `logging_setup.py`.
- `data_ingestion/` — `base_client.py` (abstract `ExchangeClient`, dataclasses
  `Trade`/`OpenInterest`/`Funding`/`MarkPrice`/`Liquidation`), one concrete
  client per exchange (`binance_client.py`, `bybit_client.py`, `okx_client.py`,
  `bitget_client.py`), `bar_builder.py` (tick→1m OHLCV aggregator),
  `manager.py` (`IngestionManager`: owns all clients, coverage tracking,
  heartbeat).
- `backfill/backfill.py` — 30-day REST backfill per exchange/source
  (klines, OI, funding, mark price), idempotent via `backfill_runs`.
- `storage/` — `db.py` (asyncpg pool + schema init + typed batch writers),
  `schema.sql` (DDL, TimescaleDB hypertables + continuous aggregates),
  `redis_client.py` (hot state: exchange connection status, heartbeat),
  `validate.py` (read-only `--validate` report).
- `deploy/` — systemd unit (`signalbot.service`, hardened,
  `ProtectSystem=strict`, dedicated unprivileged user), `docker-compose.yml`
  (TimescaleDB 2.17.2/pg16 + Redis 7.4, loopback-only), backup/restore
  scripts with a self-test restore path.

Entry modes (`main.py`): full run (backfill if needed → gap-fill → live),
`--backfill-only`, `--skip-backfill`, `--validate` (read-only report, no
writes). No `percentile_engine` / `signal_engine` / Telegram code exists yet
— confirmed absent from the tree, consistent with `docs/PRODUCT_SPEC_V0.md`
and `docs/STAGE1_ACCEPTANCE.md` ("intentionally NOT part of this stage").

Scope actually running today: **BTCUSDT, USDT-M perpetual futures only**,
on **3 active exchanges** (Binance, Bybit, OKX). Bitget is structurally
implemented but disabled (`config.enabled_exchanges`); its client code and
previously-collected data are retained but it does not connect, poll,
backfill, or count toward coverage.

## 2. Current data flow

**Live path:** exchange WS trade ticks → `LiveBarBuilder.add_trade` (per
exchange, in-memory) accumulates OHLCV + taker buy/sell split → on minute
rollover the closed `Bar1m` fires `IngestionManager._on_bar_closed` →
`db.insert_klines(source='live')` (upsert on `(exchange, symbol, ts)`).
OI/funding/mark price come from a 15s REST poll per exchange, written
directly (no in-memory aggregation needed — each poll is one row).
Liquidations arrive as discrete WS events and are inserted immediately
(no dedup key beyond an autoincrement `id`).

**Coverage/health path:** `IngestionManager._coverage_loop` runs every 15s,
computes `idle = now - last_message_ts` per client, writes a snapshot to
Redis (`exchange_status` hash) and opens/closes a per-exchange "outage"
window, logging `connectivity_events` rows (`disconnect`/`restore` with
downtime) only when an outage crosses `reliability.exchange_alert_after_min`
(3 min) — short blips are intentionally silent. A separate 30s heartbeat
loop writes `bot:last_heartbeat` to Redis (process-wide, not per-exchange).

**Backfill path:** on startup (unless `--skip-backfill`), `run_backfill`
launches all enabled exchanges concurrently (`asyncio.gather`, shared
semaphore, `_CONCURRENCY=4`) fetching 30d of klines/OI/funding/mark-price per
exchange via REST, each `(exchange, symbol, source)` tracked in
`backfill_runs` with status `running→complete|partial|failed` and skipped on
re-run if already `complete` (`has_complete_backfill`). Immediately before
live ingestion starts, `run_gap_fill` closes the residual gap between the
newest stored bar and the last fully-closed minute via REST, using the
*same* per-exchange kline-fetch functions as backfill (`KLINES_FETCHERS`,
shared code — no drift risk between the two paths).

**Continuous aggregates:** `klines_5m/15m/1h/4h` are TimescaleDB continuous
aggregates over `klines_1m`, each with its own refresh policy
(1min/5min/15min/30min schedules). Schema init (`db.init_schema`) splits
`schema.sql` into individual statements and executes each in its own
implicit transaction — required because `CREATE MATERIALIZED VIEW ...
WITH (timescaledb.continuous)` and `add_continuous_aggregate_policy(...)`
cannot run inside a transaction block. All DDL is idempotent
(`IF NOT EXISTS`), so re-running init on an existing DB is a no-op — this is
the pattern Stage 2 migrations should reuse.

## 3. Existing data inventory

| Table | Grain | Hypertable | Notes |
|---|---|---|---|
| `klines_1m` | exchange, symbol, 1m | yes | OHLCV + `taker_buy_volume`/`taker_sell_volume` (NULL, not zero, where unknown) + `trades_count`; `source` = `backfill`\|`live` |
| `open_interest` | exchange, symbol, ts | yes | `oi_raw` + `oi_unit` (`base`\|`contracts`) + `contract_value` + `oi_base_asset` + `oi_notional_usd` (only when the exchange provides USD directly — never assumed). Legacy `oi_contracts`/`oi_notional` kept in parallel for continuity. **Never summed across exchanges** (units differ, enforced by convention not by a DB constraint) |
| `funding_rate` | exchange, symbol, ts | yes | |
| `mark_price` | exchange, symbol, ts | yes | |
| `liquidations` | exchange, symbol, ts, event | yes | `side`, `price`, `qty`, `notional`, `is_snapshot_feed` flag. **No dedup key** beyond `(id, ts)` PK where `id` is a bare serial — a retransmitted event on WS reconnect would double-insert (see Risks) |
| `connectivity_events` | exchange, event | no | `disconnect`/`restore`, JSONB `detail` (idle/downtime seconds) |
| `backfill_runs` | exchange, symbol, source | no | idempotency + partial/failed bookkeeping |
| `exchange_capabilities` | **exchange, metric only — no symbol column** | no | structural (what an exchange's public API can do) × `enabled` (what's active in the MVP). PK `(exchange, metric)` |

**Per-exchange coverage actually verified** (from `docs/STAGE1_ACCEPTANCE.md`,
confirmed by a passing 1h soak test):

| Exchange | OHLCV | Taker split | Open Interest | Funding | Mark price | Liquidations |
|---|---|---|---|---|---|---|
| Binance | live+hist | live+**hist** (only exchange) | live+hist (~29d23h retention) | live+hist | live+hist | live-only, `snapshot` (under-counts cascades) |
| Bybit | live+hist | live-only | live+hist | live+hist | live+hist | live-only, `full` |
| OKX | live+hist (100/req paging) | live-only | **live-only** (no verified 30d endpoint) | live+hist | live+hist | live-only, `aggregated`/delayed |
| Bitget (disabled) | hist short/deferred | live-only | live-only | live+hist | live-only | **unavailable** entirely |

Every raw table is keyed `(exchange, symbol, ts)` — exchange values are never
blended, so per-exchange percentiles are directly computable without a
Stage 1 rework.

**What is categorically NOT collected today (confirmed by full-repo read,
not just absence of a mention):**

- **Spot market data of any kind.** Every client connects to the
  perpetual-futures endpoint only (`fapi.binance.com`, Bybit
  `category=linear`, OKX/Bitget `SWAP`/`USDT-FUTURES`). There is no spot WS
  client, no spot REST backfill, nothing. `spot_cvd` as described in the
  Stage 2 plan **cannot be computed** — this needs a new ingestion module,
  it is not a Stage 2.1 feature-engine task.
- **Order book data** (depth, imbalance, walls). No orderbook client, table,
  or field exists anywhere in the tree. The "Стакан и spoofing" section of
  the plan is entirely unbuildable on current data.
- **CVD (cumulative volume delta)** as a stored/computed series — raw
  `taker_buy_volume`/`taker_sell_volume` per bar exist, but nothing
  accumulates them into a running delta yet. This is in-scope, expected
  Stage 2.1 work (Feature Engine), not a gap.
- Any external data (CoinGlass/aggregated, on-chain, ETF flows, macro
  calendar) — expected, out of Phase-0 scope (Phase 4 per the plan).

## 4. Gap-detection capabilities (what Stage 1 actually has vs. what Stage 2 needs)

This matters directly: the clarifications doc requires *"не создавать
второй независимый gap detector, пока не изучен Stage 1"* and lists 9
specific capabilities to check. Verified against the code:

| Capability | Status | Detail |
|---|---|---|
| WebSocket reconnect tracking | **Yes, solid** | `ExchangeClient.run_forever` — exponential backoff (1s→60s cap), `ConnectionState` (connected/attempts/disconnected_since), soak-tested (Bitget reconnected ~every 2.5 min over 1h and kept writing) |
| Provider heartbeat | **Partial** | `bot:last_heartbeat` in Redis is process-wide (one key), not per-exchange. Per-exchange liveness exists separately via `exchange_status` hash (`connected`, `healthy`, `seconds_since_last_message`), refreshed every 15s — usable as a per-exchange heartbeat, just not named/shaped as one |
| Last successful event timestamp | **Partial** | In-memory/Redis only (`last_message_ts`, WS-message granularity). Per-*metric* last-timestamp is computed only on-demand inside `validate.py` (`max(ts)` query at report time), not persisted or continuously tracked |
| REST backfill | **Yes, solid** | `backfill_runs` bookkeeping, idempotent skip, partial/failed status with human-readable notes (never silently zero-fills) |
| Out-of-order handling | **Implicit, not explicit** | Klines are upserted by `(exchange, symbol, ts)`, so late/reordered bars self-correct. No explicit sequence-number or ordering check exists (not needed for bar data; would matter more for tick-level replay, which isn't stored) |
| Duplicate trade handling | **N/A for trades** (not persisted individually — only aggregated into bars) / **missing for liquidations** — see Risks | |
| Sequence gap detection | **No** | Not implemented as code. `docs/STAGE1_ACCEPTANCE.md` documents a manual SQL snippet (`lead(ts) OVER (...) - ts > interval '60s'`) as something you *can* run by hand; `storage/validate.py` does **not** compute or report internal gap counts anywhere in its output |
| Missing candle detection | **No** (same as above) | |
| Message lateness (persisted, continuous) | **No** | `validate.py` computes `age_s` (staleness of the newest row) at report time only; there is no continuously-updated lateness metric stored anywhere |

**Bottom line:** connection-level health (is the WS up, how long has it been
down, did it recover) is production-tested and solid. **Structured,
queryable, continuously-maintained gap detection — the `DataHealthSnapshot`
concept from the clarifications doc — does not exist as code today.** It
needs to be built new for Stage 2. This is expected/in-scope work, not a
Stage 1 defect, but it should not be assumed to already exist. The existing
`exchange_capabilities` table (structural capability × runtime `enabled`
flag, queried via SQL rather than by inspecting client classes) is a strong,
directly reusable pattern for `DataHealthSnapshot` and for the symbol
registry — same declarative-table-plus-idempotent-seed design should be
repeated, not reinvented.

## 5. Missing data relative to Stage 2 plan requirements

- Spot trades / spot CVD — absent, needs new ingestion (see §3).
- Order book / spoofing signals — absent, needs new ingestion (see §3).
- CVD accumulation — absent but in-scope for Stage 2.1 (Feature Engine),
  computable today from existing `taker_buy_volume`/`taker_sell_volume`
  (**perp CVD only** — spot CVD stays out of scope until spot ingestion
  exists).
- Structured gap-detection / `DataHealthSnapshot` — absent, needs new code
  (see §4), buildable entirely additively on top of `klines_1m` +
  `exchange_capabilities`.
- Symbol registry / multi-symbol schema — see §6, the schema is
  *structurally* ready (every hypertable already carries `symbol`) but the
  orchestration/config layer is single-symbol by design.
- Liquidation event dedup key — absent (flagged as a risk in §7, not a
  blocker).
- Everything Phase 2+ (structural levels, event detection, scoring, state
  machine, historical evaluator, external providers) — absent, expected,
  correctly out of Stage 2.1 scope per the plan's own phasing.

## 6. Hardcoded-BTC findings

Full-repo review for symbol hardcoding, with the concrete goal of answering
"what breaks the moment someone flips `ETHUSDT: enabled: true`":

1. **`data_ingestion/okx_client.py`** — `INST_ID = "BTC-USDT-SWAP"` is a
   **module-level constant**, and `self._inst_id = INST_ID` in `__init__`
   **ignores the `symbol` constructor argument entirely**. Every OKX
   WS subscription and REST poll call always targets `BTC-USDT-SWAP`
   regardless of what symbol string is passed in.
   **This is the single highest-risk hardcode in the repo**: if a symbol
   registry is added and ETHUSDT is enabled without also fixing this file,
   the OKX client would keep silently ingesting **BTC price/OI/funding
   data while labeling every row `symbol='ETHUSDT'`** in the database —
   silent data corruption, not a crash, so it would not be caught by a
   smoke test that only checks "rows are landing."
2. **`backfill/backfill.py`** — the same `inst_id = "BTC-USDT-SWAP"` literal
   is independently re-declared **three separate times**: inside
   `_klines_okx`, and inside the `funding()` and `mark_price()` closures of
   `backfill_okx` (the `klines()` closure at least reuses `_klines_okx`, so
   that one path is shared — the other two are not). Same silent-mislabel
   risk applies to backfilled OI/funding/mark-price history for OKX.
3. **`config/config.yaml` / `common/config.py`** — `symbol: BTCUSDT` is a
   single top-level scalar; `Config.symbol` returns one string. This is a
   deliberate single-symbol design, not a bug, but it means every
   downstream consumer (`IngestionManager`, `run_backfill`, `run_gap_fill`,
   `validate_ingestion`) is parameterized on one symbol, not a list/registry.
4. **`data_ingestion/manager.py`** — `IngestionManager.__init__` sets
   `self.symbol = cfg.symbol` (singular); one manager instance = one
   symbol's worth of clients/bar-builders/coverage-tracking. Multi-symbol
   would need either N manager instances or a refactor to loop internally
   over a symbol list.
5. **`common/capabilities.py` / `storage/schema.sql`
   (`exchange_capabilities`)** — the capability registry has **no symbol
   dimension at all**; its primary key is `(exchange, metric)`. This is a
   schema-level gap, not just a code hardcode: today's implicit assumption
   is "capabilities are the same for whatever the one global symbol is,"
   which stops being true the moment a second symbol is added (e.g. a
   symbol might not trade on all 3 exchanges, or might have different
   historical-endpoint coverage than BTC).

**What is correctly *not* hardcoded** (good precedent to copy forward):
`bar_builder.py`, `base_client.py`, `binance_client.py`, `bybit_client.py`,
`bitget_client.py` all take `symbol` as a constructor argument and use it
consistently for every WS subscription, REST call, and outgoing
`Trade`/`OpenInterest`/etc. row. The **raw data tables themselves**
(`klines_1m`, `open_interest`, `funding_rate`, `mark_price`, `liquidations`)
already carry `symbol` as part of their composite primary key — they are
schema-ready for multi-symbol today; only OKX's client/backfill code and the
capability registry actually need to change before a second symbol is safe
to enable.

## 7. Data-quality risks worth flagging now (not blockers for Stage 2.1)

- **Liquidations have no dedup safeguard.** `insert_liquidations` is a bare
  `INSERT`, no `ON CONFLICT`; the table PK is `(id, ts)` where `id` is an
  autoincrement serial, so it can never conflict with itself. If any
  exchange ever redelivers the same liquidation event across a WS
  reconnect, it would be double-counted. Cheap to fix (a content-based
  dedup key), but is a Stage-1-adjacent change and should be called out as
  a decision (see Implementation Plan §"Open decisions").
- **OKX/Bitget have short or absent historical OI/mark-price coverage**
  (no verified 30d endpoint for either). The Percentile Engine's warm-up
  state (per the clarifications doc, §19) will legitimately stay
  `WARMING_UP` far longer for OI on these two venues than for price — this
  is real, not a bug, and the per-metric-family warm-up design already
  anticipates it correctly.
- **`exchange_capabilities` capability rows are declarative Python data**
  (`common/capabilities.py`), re-seeded (upsert) on every process start.
  Any Stage 2 addition to this table (e.g. adding `symbol`) must preserve
  that re-seed-is-idempotent property. **Revision 0.1 decision:** this
  table is now left *entirely untouched*; the symbol dimension goes into a
  new additive table instead (see `STAGE2_SPEC.md` §2).

---

# Revision 0.1 — additional findings (Architecture Review)

The following were found on a second pass driven by the Architecture Review
0.1 requirements (exact feature units, liquidation provenance, dedup
safety). They materially change the Stage 2.1 design and are the reason
several features below are marked "needs normalization" rather than
"ready to compute".

## 8. Unit incompatibility across exchanges — `volume` is NOT comparable

This is the most consequential new finding, and it directly affects any
naive cross-exchange aggregation.

`klines_1m.volume` (and therefore `taker_buy_volume` /
`taker_sell_volume`, which are accumulated from the same `trade.qty` in
`bar_builder.py`) is stored **in whatever unit the exchange's trade feed
reports**, with no normalization anywhere in the pipeline:

| Exchange | Feed | `qty` / `vol` unit | Comparable to Binance? |
|---|---|---|---|
| Binance | `aggTrade.q` | base asset (BTC) | — (reference) |
| Bybit | `publicTrade.v` | base asset (BTC) | yes |
| OKX | `trades.sz` (SWAP) | **contracts** (`ctVal` = 0.01 BTC) | **no — off by ~100×** |
| Bitget (disabled) | `trade.size` | base asset (BTC) | yes |

The same applies to the backfill path: `_klines_okx` reads `c[5]` from
`/market/history-candles`, which for a SWAP instrument is volume **in
contracts**, not base currency (`volCcy` would be the base-denominated
field, and is not read).

**Consequence:** exactly the same class of error the project already
guarded against for open interest (`oi_unit` tagging, "never sum raw OI
across exchanges") is currently **unguarded for volume and taker flow**.
Any consensus feature that averages or sums `volume_raw` across
binance/bybit/okx today would be silently wrong by roughly two orders of
magnitude on the OKX leg. Nothing in Stage 1 is broken by this (Stage 1
never aggregates across exchanges — every query is per-exchange), which is
why it has gone unnoticed; it becomes a correctness bug the moment Stage
2's consensus layer exists.

**Required in Stage 2.1** (reflected in the feature contract,
`STAGE2_CLARIFICATIONS.md` §23):
- Volume/taker-flow features must carry an explicit unit, the same way OI
  already does. **Revision 0.2:** the field is named `volume_raw` with a
  companion `volume_raw_unit` — the earlier name `volume_base` asserted a
  unit that is simply false for OKX, which is precisely the mistake this
  finding is about.
- Cross-exchange aggregation must operate on **notional USD** or on
  **normalized/percentage changes and percentile ranks** — never on raw
  base/contract quantities.
- OKX conversion requires `ctVal`; it is currently hardcoded nowhere and
  read from nowhere. **Revision 0.2:** it comes from the dedicated
  `exchange_instruments` table (one row per exchange/symbol/market_type),
  populated by fetch-and-store with last-known-good fallback and a
  mismatch alarm, and is **fail-closed** — a missing multiplier excludes
  that venue from notional consensus rather than defaulting to base.
  Instrument metadata is deliberately separate from metric capability:
  one instrument has one tick size but six metric capabilities, and the
  two have different lifecycles (fetched vs. declared).

## 9. Liquidation feed semantics differ per provider (provenance must be preserved)

Confirmed from the client implementations, and relevant to Review item 4
(splitting liquidations by direction):

| Exchange | Topic | Side semantics as parsed | Feed quality | `is_snapshot_feed` |
|---|---|---|---|---|
| Binance | `forceOrder` | `o.S == "SELL"` → a **long** was liquidated | `snapshot` — rate-capped ~1 event/symbol/1000ms, **under-counts cascades** | `True` |
| Bybit | `allLiquidation` | `S == "Buy"` → a **short** was liquidated (force-buy-back) | `full` real-time | `False` |
| OKX | `liquidation-orders` (business WS) | `details[].posSide` used directly (`long`/`short`) | `aggregated`/delayed | `True` |
| Bitget | — | no public feed | `unavailable` | n/a |

Three different derivation rules for the same logical field, two of the
three feeds explicitly lossy, and one venue with no data at all. The
`is_snapshot_feed` flag and the `coverage_type` in `exchange_capabilities`
already capture this correctly — the Stage 2 requirement is simply that
they must be **carried through into the feature layer** rather than
collapsed. A single summed `liquidation_notional` across venues would
average a rate-capped feed, a delayed aggregate, and a complete feed into
one number with no way to tell which dominated.

## 10. No provider-side liquidation event ID exists in the currently-parsed payloads

Relevant to Review item 10-G (dedup must not be naive). Checking what each
client actually extracts today:

- Binance `forceOrder`: reads `o.T`, `o.S`, `o.q`, `o.ap`/`o.p`. **No
  identifier is parsed.**
- Bybit `allLiquidation`: reads `T`, `S`, `v`, `p`. **No identifier is
  parsed.**
- OKX `liquidation-orders`: reads `details[].ts`, `bkPx`, `sz`,
  `posSide`. **No identifier is parsed.**

So a content-based unique key on `(exchange, symbol, ts, side, price,
qty)` is the *only* thing available from stored data today — and it is
demonstrably unsafe: during a cascade, two genuinely distinct liquidations
of the same size at the same price within the same millisecond are
entirely plausible, and a naive `UNIQUE` index would silently discard the
second one. That is a worse failure than the double-count it's meant to
prevent, because it under-reports exactly during the cascades the signal
engine most cares about.

**Also unknown from the code alone:** whether the raw exchange payloads
contain an ID field that the client simply doesn't parse (e.g. Binance's
`forceOrder` order-level fields beyond those read). This cannot be
determined from the repository — it requires inspecting a live raw
message.

**Therefore the dedup fix is blocked on evidence, not on design**: the
first step must be to capture and inspect full raw liquidation payloads
per provider before choosing a dedup strategy. The proposed sequencing is
in `STAGE2_IMPLEMENTATION_PLAN.md` §"Liquidation dedup — evidence first".

**Revision 0.2 decision (L):** the capture mechanism is a **temporary
rotating JSONL side-channel, disabled by default** — no Stage 1 schema
change, no permanent write path. Note the operational consequence: the
production unit runs `ProtectSystem=strict` with no writable paths, so
enabling capture also requires a deliberate temporary `ReadWritePaths`
grant. That friction is desirable — it bounds the capture window
explicitly instead of leaving payload logging on indefinitely.

## 12. Coverage differs by metric family — not a single number

Recorded here because revision 0.2 makes it structural. Across the three
active venues on BTCUSDT, coverage is genuinely heterogeneous:

| Family | Live | Historical (30d) | Limiting factor |
|---|---|---|---|
| price / OHLCV | 3/3 | 3/3 | — |
| funding | 3/3 | 3/3 | — |
| open interest | 3/3 | **2/3** | OKX has no verified 30d historical OI endpoint |
| taker flow / CVD | 3/3 | **1/3** | only Binance carries a historical taker split; bybit/okx accumulate live-only |
| liquidations | **3/3 available**, mixed quality | **0/3** | never backfilled, so a historical bucket has *no* liquidation data from any venue — bucket coverage is 0, not 3 (see below) |

**Correction (revision 0.2.1) — liquidation coverage was stated wrongly
above in the previous revision.** It read "2/3 effective" and attributed
the shortfall partly to Bitget. Both parts were wrong:

- **Bitget is not in the denominator.** It is disabled via
  `config.enabled_exchanges`, and a disabled venue is excluded from
  coverage entirely — the rule Stage 1's `validate.py` already applies.
  It cannot reduce a ratio it is not part of.
- **The real issue is quality, not availability.** All three active
  venues *do* provide a live liquidation feed:
  `live availability = 3/3`. What differs is completeness — Binance
  `snapshot` (rate-capped, under-counts cascades), Bybit `full`, OKX
  `aggregated` (batched/delayed).

Availability and quality are therefore tracked as **separate**
properties (`STAGE2_CLARIFICATIONS.md` §23.2b), and the consensus
liquidation sums are named `observed_*` to make explicit that they are a
provenance-aware **lower bound** on what the market liquidated, not a
market total.

**Further refinement (revision 0.2.2): there is a third concept.** Live
capability, per-bucket coverage and feed quality are all distinct, and
liquidations are where they diverge most visibly:

| Concept | Historical bucket | Live bucket |
|---|---|---|
| Live capability (does a feed exist?) | 3/3 | 3/3 |
| Bucket coverage (did data arrive *for this bucket*?) | **0/3** | 3/3 |
| Feed quality | snapshot / full / aggregated | snapshot / full / aggregated |

Because liquidations are never backfilled, every bucket older than the
start of live collection has **zero** contributing venues — so
`coverage_by_metric["liquidations"].available = 0` there, and the
`observed_*` sums are **NULL**, not `0`. Writing `0` would assert that
the period was measured and nothing liquidated, which is false for a
30-day-old bucket and would poison any percentile distribution built over
it. Details and the contrasting live-quiet-feed case are in
`STAGE2_CLARIFICATIONS.md` §23.2c.

A single global `exchanges_available` would have to pick one of these to
represent, and would be wrong about the others — which is why
`consensus_feature_vectors` now carries `coverage_by_metric`,
`provenance_by_metric` and `data_confidence_by_metric` keyed by family
(`STAGE2_CLARIFICATIONS.md` §23.2a). The practical consequence for
bootstrap: price and funding percentiles mature immediately from existing
history, OI percentiles mature at 2/3 coverage, and **taker-flow/CVD
percentiles are effectively Binance-only for the historical period** and
only become genuine 3-venue features after enough live history accrues.
The `--stage2-validate` report must state this per family rather than
presenting one "30 days available" figure.

## 11. Roadmap items blocked by missing ingestion (not descoped)

Per Review decisions 10-C and 10-D, these stay on the Stage 2 roadmap with
explicit blocking markers rather than being removed:

| Capability | Marker | Blocked because |
|---|---|---|
| spot CVD, spot/perp divergence, spot-confirmed demand setups | `BLOCKED_BY_SPOT_INGESTION` | No spot client, table, or backfill exists anywhere in the tree (§3). Requires a prerequisite spot-ingestion phase |
| orderbook imbalance, limit walls, wall persistence/execution/cancellation, spoof risk | `BLOCKED_BY_ORDERBOOK_INGESTION` | No orderbook client, table, or field exists anywhere in the tree (§3). Requires a separate orderbook-ingestion phase |

Both prerequisite phases are scoped in
`STAGE2_IMPLEMENTATION_PLAN.md` §"Prerequisite ingestion phases".
