# MARKET-06 — Cross-Venue Dislocation Adverse-Path Risk: Historical Feasibility

Status: `MARKET_06_FEASIBILITY_HOST_BLOCKED`
Date: 2026-09-21
`MARKET_06_STATUS = CONCEPT_SELECTED_NOT_PREREGISTERED`

## What this is

This is an **outcome-blind historical-data feasibility unit only**. It does
not test, preregister, or arm the MARKET-06 hypothesis. No price-derived
quantity of any kind was computed, because no price data was ever
retrieved.

## Concept (not tested in this unit)

`MARKET_06_ID`: `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
`FAMILY`: `CROSS_VENUE_MICROSTRUCTURE`

Conditional on BTC's own state, test whether unusually large disagreement
between BTC perpetual and BTC spot prices contains stable incremental
information about subsequent BTC adverse-path risk.

This is explicitly **not** a funding rescue, an OI rescue, a MARKET-05
rescue, or another ETH-confirmation variant, and none of those were tested
here either.

## Preferred data route

- **Spot leg**: Bybit, `category=spot`, `symbol=BTCUSDT`, `interval=5`,
  official Bybit V5 historical Kline API (`GET /v5/market/kline`).
- **Perpetual leg**: Binance USD-M perpetual futures, `symbol=BTCUSDT`,
  `interval=5m`, official Binance Public Data archive
  (`data/futures/um/.../klines/BTCUSDT/5m/`), trade-price klines — mark
  price is explicitly not a substitute for the perpetual leg.
- Both legs use the same quote asset (`BTCUSDT`), so the primary
  dislocation does not mechanically mix BTC-USD spot with BTC-USDT
  perpetual, and does not inject USD/USDT stablecoin basis as an
  uncontrolled component. No source substitution (e.g. Coinbase BTC-USD)
  was made or considered necessary.
- Target historical overlap: `2022-01-01T00:00:00Z` through
  `2024-12-31T23:59:59Z`. 2025 and 2026 are protected and were not opened.

## What was actually done in this unit

1. Created a dedicated feasibility branch
   (`cursor/market-06-cross-venue-feasibility-0474`) from the exact
   accepted `BASE_HEAD` (`4158403b942c3ac0e2af3fb602f074f0064690fd`),
   touching no `FORWARD_MARKET_OBSERVABILITY_V1` collector or authority
   file.
2. Attempted a bare connectivity probe (no data request, no structural
   schema inspection) against the two required official hosts, through
   this session's normal, unmodified network egress path — no proxy
   bypass, no alternate route, no VPN/tunnel substitution:
   - `https://data.binance.vision` (Binance public-data archive index for
     the BTCUSDT 5m USD-M futures klines prefix)
   - `https://api.bybit.com` (`/v5/market/time`, a bare reachability
     check; no kline request was attempted since even this endpoint could
     not be reached)
3. Both probes failed identically: `curl: (56) CONNECT tunnel failed,
   response 403`. The session's own proxy diagnostics
   (`$HTTPS_PROXY/__agentproxy/status`) classify both as
   `connect_rejected: gateway answered 403 to CONNECT (policy denial or
   upstream failure)` — a rejection of the CONNECT tunnel itself, before
   any request reached Binance or Bybit. No HTTP status and no bytes were
   ever produced by either venue.
4. This is the same failure signature already observed for
   `fapi.binance.com:443` and `fstream.binance.com:443` during the
   `FORWARD_MARKET_OBSERVABILITY_V1` readiness checks run from this same
   host — consistent with a general outbound network policy on this
   execution host, not a per-endpoint anomaly and not evidence about
   either venue's actual availability.

No archive was listed, no ZIP was downloaded, no checksum was verified, no
Bybit page was fetched, no timestamp index was built, and no cross-venue
alignment was computed, because no bytes were ever received from either
source.

## Why this is not `MARKET_06_HISTORICAL_FEASIBILITY_REJECTED`

Per the frozen fail-closed rule for this unit: when the official historical
source cannot be reached because of *this host's* network policy, that
must not be classified as scientific infeasibility of the sources
themselves. `data.binance.vision` and `api.bybit.com` are well-documented,
long-standing official public archives; there is no evidence here that
BTCUSDT 5m history is unavailable on either venue for 2022–2024 — only
that this execution host cannot currently reach either host to check.

- `source_unavailable_historically = false`
- `source_inaccessible_from_current_execution_host = true`

## What this unit deliberately does NOT contain

- No dislocation, spread, z-score, correlation, future return, MAE,
  drawdown, regression, bootstrap, coefficient, or threshold computation.
- No price series was inspected, charted, or manually reviewed.
- No `MARKET_06_PREREGISTRATION`, `MARKET_06_ARM`, or `MARKET_06_RESULT`
  artifact was created. `MARKET_06_STATUS` remains
  `CONCEPT_SELECTED_NOT_PREREGISTERED`.
- No 2025/2026 data, and no protected OOS dataset, was opened.
- No `M04-FWD` change. `FORWARD_MARKET_OBSERVABILITY_V1` collector and
  authority artifacts are untouched.
- `SCIENTIFIC_OUTCOMES_INSPECTED = false`.

## Next unit

`MARKET_06_HISTORICAL_FEASIBILITY_RETRY_FROM_UNBLOCKED_HOST` — re-run this
exact feasibility unit, unchanged in concept, source route, and target
window, from a deployment host whose network egress can reach
`data.binance.vision` and `api.bybit.com`. This is a reachability blocker
only; no design or code change is implied.
