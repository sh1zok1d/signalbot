# MARKET-06 OKX spot source-route design review

Status: `MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED`
Date: 2026-09-21
`MARKET_06_STATUS = CONCEPT_SELECTED_NOT_PREREGISTERED`

This is a **pre-preregistration source-route design review**. It does not
test MARKET-06. It does **not** rewrite
`docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.md` (Bybit-route
feasibility; preserved historically).

Machine-readable twin:
[`MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.json`](MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.json)

Identity evidence:
[`../research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/`](../research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/)

```text
PRE_REVIEW_HEAD = e5daf3acb739883681b27ad1e6028e5842370882
OLD_SPOT_SOURCE = BYBIT_BTCUSDT_SPOT
OLD_SOURCE_REJECTION_REASON = VENUE_COUNTRY_ACCESS_RESTRICTION_FROM_CURRENT_EXECUTION_HOST
NEW_SPOT_SOURCE = OKX_BTC_USDT_SPOT
SOURCE_CHANGE_OCCURRED_BEFORE_PREREG = true
SOURCE_CHANGE_OCCURRED_BEFORE_OUTCOMES = true
SCIENTIFIC_OUTCOMES_INSPECTED = false
```

## Concept (still not tested)

`MARKET_06_ID`: `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`

Conditional on BTC's own state, test whether unusually large disagreement
between BTC perpetual and BTC spot prices contains stable incremental
information about subsequent BTC adverse-path risk.

## Source-route change

The previous preferred spot leg was Bybit V5 `GET /v5/market/kline`
(`category=spot`, `symbol=BTCUSDT`, `interval=5`). From this host Bybit's
CloudFront distribution returned HTTP 403 country-block JSON
(`VENUE_RESPONSE_ERROR`). That is not a post-outcome rescue: MARKET-06
has never been preregistered, armed, or executed.

This review asks whether OKX spot can replace that leg **before**
preregistration, keeping:

- cross-venue structure (Binance perp vs non-Binance spot);
- BTC/USDT quote consistency;
- spot-vs-perpetual market distinction;
- 2022-01-01T00:00:00Z through 2024-12-31T23:59:59Z overlap;
- completed-candle no-lookahead semantics.

Binance spot was **not** adopted. Same-venue Binance spot-vs-perp would
move the family toward a basis-premium design and may overlap M04.

## Legs used in this review

**Perpetual (unchanged):** Binance USD-M `BTCUSDT` 5m **trade-price**
klines from official Public Data
`data/futures/um/monthly/klines/BTCUSDT/5m/`. Mark-price klines were not
substituted.

**Spot (new):** OKX official `GET /api/v5/market/history-candles`
`instId=BTC-USDT` `bar=5m`. No aggregator or third-party dataset.

## Structural probes (OHLC not reported)

Official OKX history-candles, `limit=10`, `after` = 01:00 UTC on the
probe day so the page lands in that month. Inspected: HTTP/API success,
schema, timestamps, `confirm`, record count. OHLC values were not
printed.

| Probe | HTTP | `code` | n | in-month | `confirm` | 5m-aligned |
|---|---|---|---|---|---|---|
| 2022-01 | 200 | 0 | 10 | 10 | all `1` | true |
| 2023-06 | 200 | 0 | 10 | 10 | all `1` | true |
| 2024-12 | 200 | 0 | 10 | 10 | all `1` | true |

`ts` is the candle **opening** timestamp (OKX docs; empirically 5m-grid
aligned, e.g. `00:55`, `00:50`, …). `bar_end = ts + 5 minutes`.
Completed candles are identifiable with `confirm=1`. A later MARKET-06
design can legally use only bars with `bar_end` strictly before decision
time. No MARKET-06 decision clock is frozen here.

Early-2022 data **was** retrieved. The window was not shortened.

## Materialization (2022-2024 only)

2025 and 2026 were not opened. No interpolation, forward-fill, or gap
repair.

**Binance:** 36/36 monthly ZIPs + CHECKSUM sidecars downloaded from
Vision. Every sidecar parsed; every ZIP SHA256 matched. Local raw bytes
live under gitignored `artifacts/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/raw/binance/`.
Git retains the object ledger (SHA256 identities), not the ZIP bytes.

**OKX:** 1053 official pages, `limit=300`, paginated with `after` from
`2025-01-01T00:00:00Z` exclusive end backward until the page crossed
`2022-01-01T00:00:00Z`. Exact HTTP bodies stored locally under
`.../raw/okx/page-NNNNNN.json`. Git retains the page manifest (request
parameters, retrieval UTC, payload SHA256, first/last timestamp, row
count), not the HTTP bodies.

## Timestamp-only census

Target grid: 5m bars on `[2022-01-01T00:00:00Z, 2025-01-01T00:00:00Z)`
= 315,648 expected timestamps.

```text
BINANCE_ROWS = 315648
OKX_ROWS = 315648
BINANCE_UNIQUE_TIMESTAMPS = 315648
OKX_UNIQUE_TIMESTAMPS = 315648
BINANCE_DUPLICATES = 0
OKX_DUPLICATES = 0
BINANCE_MISSING_TIMESTAMPS = 0
OKX_MISSING_TIMESTAMPS = 0
BINANCE_LONGEST_GAP_BARS = 0
OKX_LONGEST_GAP_BARS = 0
ALIGNED_TIMESTAMPS = 315648
BINANCE_ONLY_TIMESTAMPS = 0
OKX_ONLY_TIMESTAMPS = 0
ALIGNMENT_RATE = 1.0
BINANCE_FIRST_UTC = 2022-01-01T00:00:00Z
BINANCE_LAST_UTC = 2024-12-31T23:55:00Z
OKX_FIRST_UTC = 2022-01-01T00:00:00Z
OKX_LAST_UTC = 2024-12-31T23:55:00Z
```

OKX in-window rows used `confirm=1` only. All 1053 pages had 9-field
rows, `confirm=1`, and 5m-aligned `ts`.

## What this unit does not contain

- No price comparison, perp-minus-spot spread, dislocation, z-score,
  correlation, future return, MAE, regression, beta, or threshold.
- No Binance spot fallback.
- No `MARKET_06` prereg / ARM / RESULT.
- `SCIENTIFIC_OUTCOMES_INSPECTED = false`.

## Verdict

`MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED`

The OKX spot leg preserves the frozen design constraints on this host
with complete 2022–2024 timestamp overlap against Binance USD-M 5m
trade-price klines.

NEXT_UNIT = `MARKET_06_PREREGISTRATION_DESIGN`
