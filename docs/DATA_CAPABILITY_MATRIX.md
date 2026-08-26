# Signalbot — Historical Data Capability Matrix

**Status:** ACTIVE / RESEARCH DATA DESIGN  
**Verified:** 2026-08-26  
**Scope:** candidate market-data sources for the 2020/2021–2026 research program.

This document answers a narrower question than `HISTORICAL_DATA_STRATEGY.md`:

> **What market history can Signalbot actually obtain, from which source, with what semantics, and for which research claim?**

It is not an authorization to download every available feed. The goal is to establish the smallest defensible dataset that can test simple mechanisms over multiple regimes before buying or engineering richer history.

---

## 1. Decision summary

### Recommended first research dataset

Use **Binance USDⓈ-M BTCUSDT** as the canonical long-history CORE source.

Initial target:

- 1m OHLCV;
- quote/base volume;
- trade count;
- taker-buy base/quote volume embedded in the official kline archive;
- optionally raw trades/aggTrades only when an intrabar hypothesis actually needs them.

Target start: **2020-01-01**.

Why:

- official public downloadable archive;
- daily/monthly immutable files plus checksums;
- sufficient history to cover multiple crypto regimes;
- 1m bars already contain a useful taker-side flow decomposition;
- no paid vendor is required to begin mechanism discovery.

### Secondary replication source

Use **Bybit BTCUSDT** as the first independent venue replication layer.

Verified public BTCUSDT kline files exist from **2020-04** for 1m/5m/15m/30m/60m intervals.

Do not force Binance and Bybit into one mandatory intersection for every experiment. The Binance-only 2020-Q1 period remains usable for Binance-scoped discovery; cross-venue claims begin only where the secondary source is available.

### OKX role

Use OKX as an additional replication/enrichment venue, but not as the dependency that defines CORE start date.

Official OKX downloadable history currently advertises:

- tick trades from **2021-09**;
- funding from **2022-03**;
- L2 order book from **2023-03**;
- downloadable OHLC from **2023-07**.

The public API also exposes historical candles from recent years, but exact instrument-by-instrument earliest reliable coverage must be probed before assigning a stronger evidence tier.

### Paid rich-history role

Treat **Tardis.dev** as an optional RICH / historical-reconstruction provider, not a prerequisite for initial edge discovery.

It can materially extend derivatives history:

- Binance USDⓈ-M data since 2019-11-17;
- Binance OI captured approximately every 30s since 2020-05-13/14;
- Bybit inverse contracts since 2019-11-07 and linear contracts since 2020-05-28;
- Bybit liquidations since 2020-12-18;
- OKX perpetual swaps since 2019-03-30;
- OKX swap liquidations since 2020-12-18.

Do not purchase full rich history before a CORE mechanism earns evidence that justifies the incremental-data question.

---

## 2. Evidence-tier vocabulary

| Tier | Meaning |
|---|---|
| `OFFICIAL_ARCHIVE` | downloadable exchange-produced historical files with documented schema |
| `OFFICIAL_API_HISTORY` | historical public API; exact depth still needs source-specific probing/version capture |
| `VENDOR_CAPTURED_RAW` | third party recorded exchange-native real-time feed historically |
| `VENDOR_NORMALIZED` | third party normalized historical feed; normalization/version must be pinned |
| `LIVE_ACCUMULATED` | Signalbot's own forward-collected raw data |
| `NEEDS_PROBE` | endpoint/source exists, but earliest reliable coverage or semantics are not yet verified |

Access class:

- `FREE` — no paid historical-data subscription required;
- `PAID` — full-history access requires a vendor plan/licence;
- `SAMPLE_ONLY_FREE` — free samples exist but not complete history.

---

## 3. Capability matrix — Binance

### Binance USDⓈ-M Futures

| Data | Earliest research target / verified availability | Native / useful granularity | Access | Evidence tier | Decision |
|---|---|---:|---|---|---|
| BTCUSDT OHLCV | 2020-01-01 target; official downloader supports archive from 2020 | 1m and higher | FREE | `OFFICIAL_ARCHIVE` | **CORE PRIMARY** |
| Kline taker-buy volume | same kline archive | 1m and higher | FREE | `OFFICIAL_ARCHIVE` | **CORE PRIMARY FLOW** |
| Trade count | same kline archive | per kline | FREE | `OFFICIAL_ARCHIVE` | CORE |
| Raw trades | official public archive from 2020 | tick | FREE | `OFFICIAL_ARCHIVE` | Acquire only if hypothesis requires intrabar flow |
| AggTrades | official public archive from 2020 | aggregated tick | FREE | `OFFICIAL_ARCHIVE` | Same rule as raw trades |
| Mark-price klines | official futures archive tooling from 2020 | 1m+ | FREE | `OFFICIAL_ARCHIVE` | Optional CORE/diagnostic |
| Index-price klines | official futures archive tooling from 2020 | 1m+ | FREE | `OFFICIAL_ARCHIVE` | Optional CORE/diagnostic |
| Premium-index klines | official futures archive tooling from 2020 | 1m+ | FREE | `OFFICIAL_ARCHIVE` | Candidate derivatives enrichment |
| Historical funding | public API/source exists; full earliest archive path not yet frozen here | funding interval | FREE | `NEEDS_PROBE` | Probe before CORE inclusion |
| Historical OI | exchange-native historical depth is not being assumed here | n/a | — | `NEEDS_PROBE` | Do not make CORE depend on it |
| OI via Tardis | captured since 2020-05-13/14 | ~30s REST poll in vendor capture | PAID | `VENDOR_CAPTURED_RAW` / normalized derivative ticker | **RICH candidate** |
| Liquidations / force orders via Tardis | raw forceOrder channel historically captured; completeness semantics vary by exchange/API era | event/snapshot | PAID | `VENDOR_CAPTURED_RAW` | RICH only; completeness audit mandatory |

Important Binance archive note:

Official kline rows contain:

- OHLC;
- base volume;
- quote volume;
- number of trades;
- taker-buy base volume;
- taker-buy quote volume.

This means a first taker-flow feature does **not** require reconstructing millions of tick trades.

Archive integrity:

- official files provide checksum files;
- archive files may later be replaced after discovered data issues;
- dataset manifests must therefore store downloaded-file checksum, not only URL/path.

---

## 4. Capability matrix — Bybit

### Bybit BTCUSDT / derivatives

| Data | Verified availability | Native / useful granularity | Access | Evidence tier | Decision |
|---|---|---:|---|---|---|
| BTCUSDT public kline files | verified directory files from 2020-04 | 1m, 5m, 15m, 30m, 60m visible | FREE | `OFFICIAL_ARCHIVE` | **CORE REPLICATION** |
| Historical klines API | historical endpoint with start/end pagination | 1m+ | FREE | `OFFICIAL_API_HISTORY` | Gap-fill / verification source |
| Public trading history | official historical-data product | tick | FREE | `OFFICIAL_ARCHIVE` | Optional intrabar research |
| Premium-index price history | official historical-data product | exchange-defined | FREE | `OFFICIAL_ARCHIVE` | derivatives enrichment |
| Index-price history | official historical-data product | exchange-defined | FREE | `OFFICIAL_ARCHIVE` | diagnostics/enrichment |
| Order book history | official historical-data product exists | exchange-defined | FREE / source-dependent | `OFFICIAL_ARCHIVE` | Do not acquire until mechanism requires it |
| Funding history API | paginated historical funding endpoint | funding interval | FREE | `OFFICIAL_API_HISTORY` | **RICH/CORE-secondary candidate** |
| OI history API | endpoint states query can extend to symbol launch time | minimum 5m; also 15m/30m/1h/4h/1d | FREE | `OFFICIAL_API_HISTORY` | **RICH candidate worth probing early** |
| Tardis derivatives capture | inverse from 2019-11-07; linear from 2020-05-28 | tick/raw channels | PAID | `VENDOR_CAPTURED_RAW` | Vendor alternative / validation source |
| Tardis liquidations | since 2020-12-18 | event-level exchange publication | PAID | `VENDOR_NORMALIZED` / raw | RICH only |

Critical OI rule:

If Bybit OI is used at 5m, it remains a **5m observation**. It may be joined to 1m bars using an as-of rule, but forward-fill must not be described as 1m OI information.

---

## 5. Capability matrix — OKX

### OKX spot / perpetual swap

| Data | Verified availability | Native / useful granularity | Access | Evidence tier | Decision |
|---|---|---:|---|---|---|
| Historical candle API | documented as recent-years history; 1s limited to recent 3 months | interval-specific | FREE | `OFFICIAL_API_HISTORY` | `NEEDS_PROBE` for exact earliest BTC coverage |
| Downloadable tick trades | from 2021-09 | tick | FREE | `OFFICIAL_ARCHIVE` | **Cross-venue replication from 2021-09** |
| Downloadable funding | from 2022-03 | funding interval | FREE | `OFFICIAL_ARCHIVE` | RICH incremental test |
| Downloadable L2 order book | from 2023-03 | high-resolution L2 | FREE | `OFFICIAL_ARCHIVE` | Deferred |
| Downloadable candlesticks | from 2023-07 | OHLC | FREE | `OFFICIAL_ARCHIVE` | Secondary convenience source, not CORE start anchor |
| Public funding history API | historical funding endpoint, max 400 rows per page | funding interval | FREE | `OFFICIAL_API_HISTORY` | Probe earlier-than-download coverage separately |
| Current open-interest endpoint | current OI available; no multi-year OI archive assumed | current | FREE | current only | Not historical evidence |
| Tardis OKX Swap | all perpetual swaps available since 2019-03-30 | exchange-native tick/raw feed | PAID | `VENDOR_CAPTURED_RAW` | Strong optional RICH source |
| Tardis OKX swap funding | v3 swap funding channel historically captured | exchange event updates | PAID | `VENDOR_CAPTURED_RAW` | RICH candidate |
| Tardis OKX liquidations | since 2020-12-18 | event/poll-derived depending era | PAID | vendor captured | RICH only |
| Tardis V5 OI/taker-volume channels | V5 channel set recorded from 2021-12-23 era | exchange channel | PAID | `VENDOR_CAPTURED_RAW` | Cross-venue derivatives enrichment |

OKX has a major historical semantic boundary around the transition from older API generations to V5. Any vendor or official history spanning this boundary must record API/channel-era metadata rather than pretending the schema was stationary.

---

## 6. Tardis.dev — what it would buy us

Tardis normalized `derivative_ticker` can contain:

- funding rate;
- funding timestamp;
- predicted funding rate where supplied;
- open interest;
- last price;
- index price;
- mark price.

It also provides historical trades, L2 updates/snapshots, quotes and liquidations where supported.

### Strengths

- long derivatives history;
- exchange-native replay is available on higher plans;
- local arrival timestamps are retained;
- explicit per-exchange incident/history documentation;
- unified normalized schemas useful for cross-venue studies.

### Research risks

- vendor polling can create a cadence different from the exchange's idealized feed (Binance historical OI is explicitly vendor-polled at ~30s);
- normalized data adds a transformation layer that must be versioned;
- liquidation feeds are only as complete as what exchanges published;
- some exchange API generations changed during the sample;
- buying a rich source after weak results can become data-source shopping.

### Current decision

**Do not buy Tardis yet solely to make Signalbot's dataset look richer.**

Revisit when one of these becomes true:

1. a CORE edge candidate survives independent validation and specifically predicts an incremental role for OI/funding/liquidations/order book;
2. a high-value hypothesis cannot be tested at all with official free history;
3. we need independent vendor reconstruction to validate an exchange API/archive semantic question.

---

## 7. Proposed dataset ladder

### `CORE_BTC_BINANCE_V0`

Purpose: broad discovery and falsification of simple mechanisms.

Target range:

`2020-01-01 -> latest frozen acquisition date`

Fields:

- 1m OHLC;
- base/quote volume;
- trade count;
- taker-buy base/quote volume;
- derived taker-sell volume only as arithmetic residual where valid;
- deterministic higher-timeframe bars generated from 1m data.

No OI requirement.  
No liquidation requirement.  
No OKX/Bybit availability requirement.

### `CORE_BTC_BYBIT_REPLICATION_V0`

Purpose: venue replication of price/volume mechanisms.

Target start:

`2020-04-01` subject to complete-file/gap audit.

Use the same outcome definitions as Binance where semantics permit. Do not retune a failed Binance hypothesis on Bybit and then call Bybit independent confirmation.

### `CORE_BTC_OKX_REPLICATION_V0`

Purpose: third-venue replication.

Conservative start for tick-derived bars:

`2021-09-01`

Aggregate official trade history deterministically when necessary rather than pretending the newer downloadable candlestick product existed throughout the period.

### `RICH_BYBIT_DERIVATIVES_V0`

Potential fields:

- 5m OI;
- funding;
- premium/index context.

This is attractive because a meaningful part may be obtainable from official public APIs without a paid vendor.

### `RICH_VENDOR_MULTIEXCHANGE_V0`

Not authorized yet.

Would be considered for:

- long-history OI;
- liquidation events;
- normalized derivatives tickers;
- historical L2/order-book questions;
- precise cross-exchange agreement studies.

---

## 8. Acquisition order

Do not download everything at once.

### Phase A — free CORE

1. Binance BTCUSDT USDⓈ-M 1m monthly klines from 2020-01 onward.
2. Download accompanying checksums.
3. Validate continuity, duplicate timestamps, bar spacing, price/volume sanity and archive replacements.
4. Materialize deterministic higher timeframes locally.
5. Produce the first frozen manifest.

### Phase B — free replication

1. Bybit BTCUSDT public 1m history from earliest reliable month.
2. Run the same gap/semantic audit.
3. Add OKX tick-derived replication from 2021-09 if needed.

### Phase C — free derivatives enrichment

Probe before bulk acquisition:

- Bybit OI history depth and pagination to symbol launch;
- Bybit funding history depth;
- Binance funding history depth;
- OKX funding history depth;
- exact OKX candle API earliest reliable BTC date.

The probe should request tiny slices from several old dates, not start a full backfill.

### Phase D — vendor decision

Only after CORE evidence identifies a specific incremental-data hypothesis.

---

## 9. Required semantic probes before implementation

The following remain deliberately unresolved:

| Probe | Why it matters |
|---|---|
| exact first complete Binance BTCUSDT USDⓈ-M 1m month | freeze canonical start date |
| exact first complete Bybit BTCUSDT 1m month | replication start |
| Bybit OI oldest successful page + pagination behavior | determine whether free multi-year OI is genuinely practical |
| Binance historical funding oldest successful record | decide whether funding can join long CORE cheaply |
| OKX history-candles oldest reliable BTC swap/spot record | distinguish API capability from marketing wording |
| OKX funding oldest successful page | compare API depth with downloadable March-2022 archive |
| symbol/instrument contract metadata changes | prevent silent unit changes |
| archive corrections/checksum changes | reproducibility |

No research claim should use a stronger data tier than these probes justify.

---

## 10. Storage/reproducibility requirements

For every downloaded source file record:

- provider;
- exchange;
- market/instrument;
- source URL/path;
- requested period;
- download timestamp;
- source checksum when provided;
- locally computed SHA-256;
- byte size;
- parser version;
- source schema/version notes;
- first/last event timestamp;
- expected vs observed row/bar count;
- missing/duplicate intervals;
- evidence tier.

Do not overwrite a raw historical file in place when the upstream archive changes. Store a revision identity and decide explicitly whether a later experiment migrates to the corrected source.

---

## 11. What this matrix does NOT authorize

This document does not authorize:

- new production forecasting logic;
- V3 implementation;
- a universal backtesting framework;
- ML feature generation;
- paid bulk historical data purchase;
- downloading full L2/order-book history speculatively;
- combining all venues into one synthetic market before individual-source validation;
- treating resampled coarse derivatives data as fine-grained observations.

The immediate objective is still:

> **obtain enough clean multi-regime CORE history to discover and falsify market mechanisms without letting data richness manufacture complexity.**

---

## 12. Source references verified on 2026-08-26

Primary sources used for this matrix:

- Binance public-data repository / Data Vision archive documentation;
- Bybit V5 historical kline, funding-history and open-interest API documentation;
- Bybit public historical-data/download directories;
- OKX historical-market-data page and V5 public API documentation;
- Tardis.dev per-exchange historical-data documentation and normalized data-type schema.

Availability can change. Before an actual bulk acquisition, re-run the small capability probes and freeze the resulting source/version identity in the dataset manifest.
