# MARKET-06 — Cross-Venue Dislocation Adverse-Path Risk: Historical Feasibility

Status: `MARKET_06_HISTORICAL_FEASIBILITY_REQUIRES_DESIGN_REVIEW`
Date: 2026-09-21
`MARKET_06_STATUS = CONCEPT_SELECTED_NOT_PREREGISTERED`

This is an independent retry of the existing outcome-blind feasibility
unit from this Cursor host. It does **not** reuse the previous
`MARKET_06_FEASIBILITY_HOST_BLOCKED` record at
`97e01bd3f1f187b3885e00cdf7c59374c9c96729`.

## What this is

Outcome-blind historical-data feasibility only. It does not test,
preregister, or arm MARKET-06. No price-derived quantity was computed.

## Concept (not tested in this unit)

`MARKET_06_ID`: `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
`FAMILY`: `CROSS_VENUE_MICROSTRUCTURE`

Conditional on BTC's own state, test whether unusually large disagreement
between BTC perpetual and BTC spot prices contains stable incremental
information about subsequent BTC adverse-path risk.

This is not a funding rescue, an OI rescue, a MARKET-05 rescue, or an
ETH-confirmation variant.

## Preferred data route (unchanged)

- **Spot leg**: Bybit, `category=spot`, `symbol=BTCUSDT`, `interval=5`,
  official Bybit V5 `GET /v5/market/kline`.
- **Perpetual leg**: Binance USD-M perpetual `BTCUSDT` 5m **trade-price**
  klines from `https://data.binance.vision/`
  (`data/futures/um/monthly/klines/BTCUSDT/5m/`). Mark-price klines were
  not substituted.
- Same quote asset on both legs (`BTCUSDT`). No Coinbase BTC-USD
  substitution.
- Target window: `2022-01-01T00:00:00Z` through `2024-12-31T23:59:59Z`.
  2025 and 2026 remain protected and were not opened.

## What was actually done on this host

`HTTPS_PROXY` was unset. No VPN, proxy bypass, or alternate route was
used.

### 1. Independent reachability probes

| Source | Class | Evidence |
|---|---|---|
| `data.binance.vision` prefix index | `SOURCE_REACHABLE` | HTTP 200, `Server: AmazonS3`, CloudFront |
| `BTCUSDT-5m-2022-01.zip.CHECKSUM` | `SOURCE_REACHABLE` | HTTP 200; sidecar SHA256 `dab154b0…`; names zip SHA256 `b2ff8cd0…` |
| S3 list of monthly 5m prefix | `SOURCE_REACHABLE` | HTTP 200; **36/36** zips and **36/36** CHECKSUM objects for 2022-01 through 2024-12 |
| `GET https://api.bybit.com/v5/market/time` | `VENUE_RESPONSE_ERROR` | HTTP 403 CloudFront JSON: distribution configured to block access from your country |
| Bybit V5 kline early 2022 / mid 2023 / late 2024 | `VENUE_RESPONSE_ERROR` | Same CloudFront HTTP 403; no native kline payload |

This is **not** `HOST_EGRESS_BLOCK`. Requests reached Amazon S3 /
CloudFront. It is **not** the previous CONNECT-tunnel 403.

Related but distinct: live `fapi.binance.com` on this host previously
returned a Binance-native HTTP 451. The public-data archive on
`data.binance.vision` is a different endpoint and was reachable.

### 2. What was not done

Because the frozen Bybit V5 route did not return a native kline payload,
the unit did **not**:

- download Binance monthly ZIP payloads;
- verify CHECKSUM sidecars against zip bytes (listing + one sidecar body
  only);
- freeze a Binance snapshot;
- materialize Bybit 2022–2024 history;
- count rows, duplicates, gaps, or aligned timestamps;
- inspect prices, spreads, or any scientific outcome;
- open 2025/2026 objects (later-year keys appeared in the S3 listing and
  were not fetched).

## Why this is not `MARKET_06_FEASIBILITY_HOST_BLOCKED`

The previous HOST_BLOCKED verdict was a gateway CONNECT rejection before
either venue answered. This host received venue/CDN HTTP bodies from both
names. Binance Vision is reachable. Bybit's official V5 distribution
geo-blocks this country. Collapsing that back into HOST_BLOCKED would
erase the new Binance-archive evidence.

`HOST_EGRESS_BLOCK = false`.

## Why this is not `MARKET_06_HISTORICAL_FEASIBILITY_REJECTED`

Binance's official 2022–2024 monthly 5m USD-M BTCUSDT trade-price
archives exist and are listable from this host. Bybit V5 geo-block is not
proof that Bybit spot 5m history is missing. `source_unavailable_historically = false`.

## Why this is not `MARKET_06_HISTORICAL_FEASIBILITY_CONFIRMED`

Confirmation requires both frozen sources to produce valid native
historical observations, checksum-verified Binance bytes, Bybit
raw-response freeze, and timestamp-only overlap/gap/completed-candle
census. Bybit produced no native kline payload. Zip payloads were not
downloaded.

## Structural output

```text
BINANCE_ROWS = null
BYBIT_ROWS = null
BINANCE_DUPLICATES = null
BYBIT_DUPLICATES = null
BINANCE_LONGEST_GAP_BARS = null
BYBIT_LONGEST_GAP_BARS = null
ALIGNED_TIMESTAMPS = null
BINANCE_ONLY_TIMESTAMPS = null
BYBIT_ONLY_TIMESTAMPS = null
ALIGNMENT_RATE = null
COMPLETED_CANDLE_SEMANTICS_USABLE = null
CONSERVATIVE_DECISION_LAG_IMPLEMENTABLE = null
BINANCE_ARCHIVE_CHECKSUMS_VERIFIED = false
BINANCE_SNAPSHOT_FROZEN = false
BYBIT_RAW_RESPONSES_FROZEN = false
2025_OPENED = false
2026_OPENED = false
DISLOCATION_COMPUTED = false
FUTURE_RETURNS_COMPUTED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_PREREG_CREATED = false
MARKET_06_ARM_CREATED = false
MARKET_06_RESULT_CREATED = false
```

Listed but not materialized: 36 Binance monthly zips + 36 CHECKSUM
sidecars, `BTCUSDT-5m-2022-01.zip` through `BTCUSDT-5m-2024-12.zip`.

## What this unit deliberately does NOT contain

- No dislocation, spread, z-score, correlation, future return, MAE,
  drawdown, regression, or threshold computation.
- No price series was inspected.
- No `MARKET_06.md` / prereg / ARM / RESULT.
- No 2025/2026 data and no protected OOS.
- No `M04-FWD` change. `FORWARD_MARKET_OBSERVABILITY_V1` collector and
  authority artifacts were not touched.
- `SCIENTIFIC_OUTCOMES_INSPECTED = false`.

## Next unit

`MARKET_06_BYBIT_OFFICIAL_HISTORICAL_ROUTE_OR_REACHABLE_HOST_REVIEW`

Do not preregister. Completing the frozen two-source feasibility requires
either an execution host that Bybit V5 CloudFront permits, or an explicit
decision on whether another official Bybit historical product may replace
`GET /v5/market/kline` without changing the concept.
