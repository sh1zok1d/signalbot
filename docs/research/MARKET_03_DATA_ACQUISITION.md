# MARKET-03 DATA ACQUISITION + PROVENANCE

- **Status:** `DATA_ACQUISITION_COMPLETE_NOT_PREREGISTERED`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_DATA_ACQUISITION`
- **Date:** 2026-09-18
- **Prior unit:** `docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.md`
  (verdict `DATA_ACQUISITION_REQUIRED`; left unchanged as historical record)

This unit closes the two feasibility gaps: missing Binance **SPOT**
BTC/USDT 1h history, and funding source/provenance compatibility with
explicit timing semantics.

It does **not** preregister, implement, ARM, execute, backtest, or
inspect MARKET-03 strategy outcomes.

Selected external source remains:

```text
repo   = https://github.com/wiktorj137/btc-strategy-lab
commit = b68a5518b4a3eba2fde1733160d7d7de356023b5
tree   = f7717e681c911ea3ccce15492246053cf15883cb
family = EmaCross vs EmaCrossFunding
```

Machine-readable twin:
`docs/research/MARKET_03_DATA_ACQUISITION.json`
(SHA256 `f1dfd27c42c39ab09c8047df0f83bd27518cb84d9e82244f4f3954249fe07cf2`).

---

## 1. Binance SPOT dataset

```text
SPOT_DATASET_ID     = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT_SNAPSHOT_ID    = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
exchange            = Binance
market              = SPOT
symbol              = BTCUSDT
native timeframe    = 1h
source              = https://data.binance.vision/data/spot/monthly/klines
documented API      = /api/v3/klines
SPOT_TIME_BOUNDS    = [2019-08-01T00:00:00Z, 2025-01-01T00:00:00Z)
first open          = 2019-08-01T00:00:00Z
last open           = 2024-12-31T23:00:00Z
SPOT_ROWS           = 47477
SPOT_EXPECTED_HOURS = 47520
SPOT_GAPS           = 43
SPOT_DUPLICATES     = 0
SPOT_DATA_SHA256    = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4
```

Acquisition start is the complete native month containing Freqtrade
`startup_candle_count=1300` warmup before the external headline
`2019-10-01` (warmup open `2019-08-07T20:00:00Z`). The start was **not**
chosen from strategy performance.

Not used: USD-M perpetual, COIN-M perpetual, aggregated external price
feeds, other exchanges, or `CORE_BTC_BINANCE_V0` derived 1h bars.

Protected 2025/2026 months were not downloaded. Binance public-data
microsecond kline timestamps (2025+) were therefore not acquired.

Git identity (raw ZIP/canonical JSONL remain gitignored):

| File | SHA256 |
|---|---|
| `docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/SNAPSHOT_2ce1f504.json` | `c4b6236c45e798aa4949ce255d91d9acfdc20833aa4ef4900e10d53e70219242` |
| `docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/OBJECT_LEDGER_2ce1f504.json` | `26184b845cd581170235ffbcf61c58f9a5c4e7d687801e28862e757323db8cc3` |
| `docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/QUALITY_REPORT_2ce1f504.json` | `0532f2f8f27ce194890a869e167fd25014bdec28aa7be7011b15e7e50ec71bfc` |
| `docs/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/FUNDING_COMPATIBILITY_2ce1f504.json` | `3c7a40b85735403dced0d7ee95dcfdd239cf611262e92878c9ce2435972e4384` |

This snapshot is reusable research infrastructure. It is **not**
scientifically bound to MARKET-03.

---

## 2. Raw provenance

Every monthly Vision object records:

- Binance Vision URL (`data/spot/monthly/klines/BTCUSDT/1h/`)
- market type `SPOT`, symbol `BTCUSDT`, interval `1h`
- month request bounds
- retrieval timestamp
- container SHA256 and byte size
- `.CHECKSUM` verification (`VERIFIED` 65/65)
- CSV member SHA256 / size / row count
- earliest and latest `open_time`
- duplicate policy: reject duplicate `open_time`; do not keep first or last
- gap policy: enumerate missing native hours; **do not synthesize**
- normalization: 12-column native CSV; preserve decimal strings; drop unused column 12 from canonical JSONL; no forward-fill; no resample; no perp substitute

---

## 3. Kline semantics and Freqtrade mapping

Native Binance spot kline columns used:

| # | Field | Role |
|---|---|---|
| 1 | `open_time` | candle open UTC ms |
| 2 | `open` | |
| 3 | `high` | |
| 4 | `low` | |
| 5 | `close` | |
| 6 | `volume` | base-asset volume |
| 7 | `close_time` | last millisecond inside the bar |
| 8 | `quote_volume` | |
| 9 | `trade_count` | |
| 10 | `taker_buy_base_volume` | |
| 11 | `taker_buy_quote_volume` | |
| 12 | `ignore` | unused; dropped from canonical |

Freqtrade labels 1h candles by **open time** in dataframe `date`.
Signalbot map:

```text
freqtrade_date = datetime_utc(open_time_ms)
closed-bar availability = open_time_ms + 3600000   # bar_end_exclusive
```

Do not use `close_time` as the Freqtrade label or as availability.

Freqtrade `populate_*` runs on the closed candle; documented fill is the
**next candle open**. That fill rule is not executed in this unit. It
remains a preregistration freeze item.

---

## 4. Integrity (not strategy evaluation)

- timestamps strictly increasing
- 0 duplicate `open_time`
- 0 malformed source rows
- 65/65 monthly checksums `VERIFIED`
- 3 zero-volume native rows kept
- 43 missing native 1h buckets, **not filled**

Gap ranges (UTC open times):

| start | end | missing hours |
|---|---|---:|
| 2019-08-15T02:00:00Z | 2019-08-15T09:00:00Z | 8 |
| 2019-11-13T02:00:00Z | 2019-11-13T03:00:00Z | 2 |
| 2019-11-25T02:00:00Z | 2019-11-25T03:00:00Z | 2 |
| 2020-02-09T02:00:00Z | 2020-02-09T02:00:00Z | 1 |
| 2020-02-19T12:00:00Z | 2020-02-19T16:00:00Z | 5 |
| 2020-03-04T10:00:00Z | 2020-03-04T10:00:00Z | 1 |
| 2020-04-25T02:00:00Z | 2020-04-25T03:00:00Z | 2 |
| 2020-06-28T02:00:00Z | 2020-06-28T04:00:00Z | 3 |
| 2020-11-30T06:00:00Z | 2020-11-30T06:00:00Z | 1 |
| 2020-12-21T15:00:00Z | 2020-12-21T17:00:00Z | 3 |
| 2020-12-25T02:00:00Z | 2020-12-25T02:00:00Z | 1 |
| 2021-02-11T04:00:00Z | 2021-02-11T04:00:00Z | 1 |
| 2021-03-06T02:00:00Z | 2021-03-06T02:00:00Z | 1 |
| 2021-04-20T02:00:00Z | 2021-04-20T03:00:00Z | 2 |
| 2021-04-25T05:00:00Z | 2021-04-25T07:00:00Z | 3 |
| 2021-08-13T02:00:00Z | 2021-08-13T05:00:00Z | 4 |
| 2021-09-29T07:00:00Z | 2021-09-29T08:00:00Z | 2 |
| 2023-03-24T13:00:00Z | 2023-03-24T13:00:00Z | 1 |

One kept degenerate archive row:

```text
open_time  = 2020-12-21T14:00:00Z (1608559200000)
close_time = 1608558440521 (before open_time)
OHLC       = 22646.53000000
volume     = 0
```

Adjacent hours 15:00–17:00 that day are among the 43 gaps. The row is
retained as native source evidence. It is not repaired.

---

## 5. Funding source compatibility

External `EmaCrossFunding` uses Binance USD-M REST
`GET /fapi/v1/fundingRate` fields `fundingRate` and `fundingTime`.

`B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` snapshot `5a9d036b…` stores
Vision `monthly/fundingRate/BTCUSDT` fields `last_funding_rate` and
`calc_time`. That is the same **economic series class** (settled USD-M
BTCUSDT funding) and **not** the same frozen REST object.

Vision monthly objects for 2019-09..2019-12 do **not** exist (`NOT_FOUND`).
Vision objects exist 2020-01..2024-12.

Re-downloaded Vision ZIP `container_sha256` values for the B2-06 joint
funding months 2020-09..2024-12: **52/52 byte-identical** to the B2-06
object ledger. B2-06 remains `research_authorized=false` and is **not**
authorized for B2-06 execution by this unit.

Authorized historical REST slice (endTime exclusive 2025-01-01):

```text
observed REST span     = 2019-09-10T08:00:00Z … 2024-12-31T16:00:00Z
REST rows              = 5819
REST 2019-09-10..2019-12-31 = 338
Vision rows 2020-01..2024-12 = 5481
overlap 2020-01-01..2024-12-31 = 5481
exact fundingTime==calc_time AND Decimal(fundingRate)==Decimal(last_funding_rate)
                       = 5481 / 5481
mismatches             = 0
REST JSONL SHA256      = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
```

`fapi.binance.com` returned HTTP 451 from this runtime. The same path
`/fapi/v1/fundingRate` was queried on `https://www.binance.com` with
`startTime`/`endTime` bounded before 2025-01-01. Unbounded “latest”
funding pages were not used for this comparison.

Numeric representation: both sources are decimal strings. 2403 overlap
rows have a non-zero millisecond residual on **both** REST `fundingTime`
and Vision `calc_time`; they still matched exactly, so the residual is
shared source timing, not a REST-vs-Vision rewrite.

---

## 6. Funding availability semantics

```text
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

For LEVEL_2 faithful reimplementation of the pinned external code,
MARKET-03 may adopt:

```text
REPRODUCTION_ASSUMPTION:
A funding observation is treated as available at its Binance fundingTime,
matching the pinned external implementation.
```

This assumption does **not** imply:

- Binance guarantees zero publication latency
- strict real-time as-of availability has been proven
- the B2-06 publication-timing blocker has been solved

It **is** sufficient for LEVEL_2 because the external implementation
joins `fundingTime` onto Freqtrade candle `date` with `ffill` and never
stores a separate publication clock. LEVEL_1 remains blocked by the
unproven publication clock.

---

## 7. Feasibility reassessment

Exactly one verdict:

**A. READY_FOR_MARKET_03_PREREG_DESIGN**

```text
replication level = LEVEL_2_FAITHFUL_REIMPLEMENTATION
```

Not LEVEL_1: spot data acquisition does not prove funding publication
latency, does not pin `freqtrade>=2026.7`, and does not freeze trailing
defaults / JSON sidecars / next-open fills. Those are preregistration
items, not remaining data-acquisition blockers.

Not B: native spot 1h history now exists with provenance; REST/Vision
funding overlap is record-equivalent on the authorized slice; 2019-09-10
..2019-12 REST funding exists where Vision does not.

Not C as the primary label: remaining engine-default ambiguities are
unchanged from the source-feasibility unit and can be frozen in prereg.

Not D: the object of study remains this public family.

This unit does **not** begin preregistration.

---

## 8. Stop flags

```text
MARKET_03_STRATEGY_EXECUTED     = NO
MARKET_03_OUTCOMES_INSPECTED    = NO
MARKET_03_PARAMETER_SEARCH      = NO
MARKET_03_PREREGISTERED         = NO
MARKET_03_ARMED                 = NO
PROTECTED_OOS_USED_FOR_SCIENCE  = NO
```

No EMA600, funding percentile, funding 3d mean, entries, exits, trades,
equity curve, return, CAGR, drawdown, Sharpe, Sortino, or parameter
sensitivity was computed.
