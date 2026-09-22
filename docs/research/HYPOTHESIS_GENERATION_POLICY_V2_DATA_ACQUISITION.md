# Hypothesis Generation Policy V2 — Data Acquisition

**Unit:** `HYPOTHESIS_GENERATION_POLICY_V2_DATA_ACQUISITION`  
**Status:** `FROZEN`  
**Date:** 2026-09-22  
**Base main:** `68f5c964f7f19e7d358a3362057d6aede5eae8b1`

This policy applies **from the next hypothesis-generation cycle**. It does **not** redesign or interrupt the already-defined D7/D8 work.

## Core correction

Signalbot must not let its current dataset inventory define its hypothesis space.

```
MISSING_DATA != REJECTED_HYPOTHESIS
DATA_AVAILABILITY = EXECUTION_COST / FEASIBILITY ATTRIBUTE
NOT = SCIENTIFIC PRIORITY
```

Hypotheses are generated first from mechanism-space. Only after that do we classify the data requirement and decide execution order.

Allowed feasibility classes:

- `DATA_READY`
- `ACQUIRABLE_FREE_HISTORICAL`
- `ACQUIRABLE_PAID_HISTORICAL`
- `NEW_DATASET_BUILD_REQUIRED`
- `FORWARD_COLLECTION_ONLY`
- `CURRENTLY_INFEASIBLE`

A stronger and more orthogonal hypothesis must not disappear merely because a weaker hypothesis already fits the current parquet inventory.

## Selection dimensions

Future research selection considers:

- information gain;
- scientific novelty;
- orthogonality to prior search;
- mechanism plausibility;
- confirmatory potential;
- provenance / point-in-time quality;
- data-acquisition cost;
- engineering cost.

Data cost may change **execution order**, but it must not erase a mechanism from the search map.

## Explicit new-information-source budget

Future discovery sprints must reserve search budget for hypotheses requiring information not already present in Signalbot, including:

- full L2/L3 order books;
- tick trades / replenishment / queue proxies;
- liquidations;
- options IV, skew and term structure;
- cross-venue microstructure;
- true cross-sectional universes;
- macro event timestamps;
- news/event data;
- on-chain state.

No generic data platform is authorized by this rule. A new dataset must still be justified by a concrete scientific card.

## Source map — checked 2026-09-22

### Strong free / official sources

**Binance Public Data — `FREE_OFFICIAL`**

Official daily/monthly archives provide exchange-native klines, trades and aggTrades, plus several futures datasets such as book ticker, funding and price-index series. The archive also exposes futures metrics and daily book-depth-related data, and Binance publishes options archives such as BVOLIndex/EOHSummary. Checksums are available. Coverage and schema vary by dataset and known archive issues mean every new tier still needs gap/schema/checksum audits.

Important: free Binance `bookDepth` must **not** automatically be treated as a complete tick-by-tick historical L2 reconstruction.

Source: https://data.binance.vision/  
Docs: https://github.com/binance/binance-public-data

**OKX Historical Market Data — `FREE_OFFICIAL`**

Particularly valuable for future microstructure work:

- tick-level trade history from Sep 2021;
- funding from Mar 2022;
- high-resolution L2 order book from Mar 2023;
- borrowing rates from Dec 2021;
- OHLC from Jul 2023.

This means a serious L2 hypothesis does **not automatically require a paid vendor** if a 2023+ OKX surface is scientifically appropriate.

Source: https://www.okx.com/en-us/historical-data

**Coin Metrics Community — `FREE_NONCOMMERCIAL`**

Useful for free community network/on-chain metrics, reference rates and a subset of market data. Good candidate for cross-sectional/on-chain discovery, but community history/granularity is intentionally narrower than Pro. License is CC BY-NC 4.0, so future commercial use needs explicit review.

Source: https://community-api.coinmetrics.io/v4

**Federal Reserve / FRED / ALFRED — `FREE_OFFICIAL`**

High-quality macro series, vintage/revision information, release dates, FOMC calendars/statements and historical materials. Useful for outcome-blind macro-event definitions.

Sources:
- https://fred.stlouisfed.org/docs/api/fred/
- https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm

**GDELT — `FREE_OPEN`**

Completely free global news/event data and knowledge graph. Useful for event discovery and broad news features, but not assumed finance-grade without deduplication, taxonomy and timestamp validation.

Source: https://gdeltproject.org/

### Free but intentionally limited

**Tardis.dev samples — `FREE_SAMPLE_ONLY`**

Tardis exposes the first day of each month without an API key for datasets including incremental L2, snapshots, trades, options chains, derivative tickers and liquidations. This is excellent for schema checks, feasibility work and cross-vendor validation, but not enough for a continuous historical study.

Source: https://docs.tardis.dev/downloadable-csv-files

### Paid sources worth considering only when a card justifies them

**CoinGlass — low/medium-cost derivatives layer**

Useful for historical OI, funding, liquidations and multi-exchange aggregates.

Public prices checked 2026-09-22:
- Hobbyist: **$29/mo**
- Startup: **$79/mo**
- Standard: **$299/mo**
- Professional: **$699/mo**

Lower tiers restrict interval granularity; the cheapest plan is useful for coarse feasibility, not every microstructure question.

Source: https://www.coinglass.com/pricing

**CoinAPI — usage-based historical market data**

No traditional free plan, but PAYG currently includes $25 signup credits. Historical order-book products are available; flat-file L2 pricing starts at roughly **$8/GiB for the first 1 GiB/day/SKU**.

Useful for targeted pulls where buying a small historical slice is cheaper than building ingestion.

Source: https://www.coinapi.io/products/flat-files/pricing

**Tardis.dev — high-quality granular history**

Strong candidate when Signalbot genuinely needs continuous tick-level L2/L3, reconstructed books, options chains, liquidations or normalized multi-exchange replay.

Public Solo pricing checked 2026-09-22 is roughly:
- Perpetuals: **$700/mo**
- Options: **$700/mo**
- Derivatives: **$900/mo**
- All Exchanges: **$1,200/mo**

Yearly Solo access currently includes four years of historical data. Do not buy this speculatively; use it when a high-information-gain card is blocked by historical coverage.

Source: https://tardis.dev/

**Kaiko — institutional**

Broad normalized L1/L2 coverage, raw order-book snapshots, spread/depth/slippage and tick-level feeds. Published pricing is around **$2,000/mo** for L2 aggregation and **$2,500/mo** for L2 tick-level. Too expensive for default exploratory use, but relevant if Signalbot eventually needs institutional normalized history.

Source: https://www.kaiko.com/products/l1-l2-data

**Amberdata — institutional / normalized**

Historical spot/futures/options, order-book events/snapshots, funding, OI, liquidations and liquidity analytics. Pricing depends on package. Monthly subscriptions provide roughly one year of API lookback; yearly subscriptions can provide full historical API access.

Source: https://www.amberdata.io/market-data

## Forward collection is a first-class option

If a valuable hypothesis needs data whose historical archive is unavailable or unreliable, do **not** delete the hypothesis.

Classify:

```
FORWARD_COLLECTION_ONLY
```

and begin point-in-time capture from public exchange WebSockets where feasible.

Full future L2, trades, quotes and derivatives streams can often be collected directly from public exchange APIs without buying a historical vendor. The cost is our own storage, monitoring, timestamp/provenance handling and waiting for enough fresh observations.

## Purchase rule

Buy data only when a concrete scientific card is blocked by access and one of these holds:

1. free exchange-native history does not cover the necessary period/granularity;
2. normalization/provenance across venues would dominate engineering time;
3. full options-chain or full-depth history is central to the claim;
4. consistent multi-venue liquidation/OI history is necessary;
5. the hypothesis has high expected information gain and data access is the main remaining blocker.

Do **not** buy data for generic platform completeness, speculative hoarding, or rescue of a weak near-neighbor hypothesis.

## Current lifecycle unaffected

```
D7_EXECUTED = false
D8_EXECUTED = false
D7_D8_REDESIGNED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
PRODUCT_BUILD_RESTARTED = false
```

D7/D8 continue exactly as already defined. This policy governs what comes after them.
