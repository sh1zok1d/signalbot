# GV0V03L40 shortlist blocker triage

**Status:** `OUTCOME_BLIND / NOT_COMPILED`
**Date:** 2026-10-02

```
MEMORY_CAMPAIGN_ID = GV0V03L40
SOURCE_RUN_ID      = ladder-40-card-v03-r02-derived-critics-v2
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
```

Only C033 is in V1 planning. These four shortlist cards stay blocked. Their datasets are not repaired here, and none of them is compiled.

| Card | Current data status | Blocker class | Exact missing data or point-in-time requirement | Zero-cost resolution possible | Next feasibility action |
|---|---|---|---|---|---|
| C005 | `FEASIBILITY_REQUIRED` | `PERP_LISTING_HISTORY_UNVERIFIED` | Effective launch timestamp of each Binance USD-M perpetual per base asset, including delisted perpetuals, and the delisting or settlement timestamp of each. The card names `BINANCE_UM_PERPETUAL_LISTING_ANNOUNCEMENTS_ARCHIVE` and `BINANCE_UM_EXCHANGEINFO_ONBOARDDATE_SNAPSHOTS`. | unknown | Pin a point-in-time listing and delisting archive, including delisted names, before any V1 compile. Do not fill the gap from a current exchange-info snapshot. |
| C024 | `FEASIBILITY_REQUIRED` | `ORDER_BOOK_DEPTH_HISTORY` | Binance USD-M bookDepth snapshots for BTCUSDT and ETHUSDT with a verified start date, snapshot cadence and gap list, and near-touch depth within 0.5 percent and 1 percent of mid at hourly cadence. The paid `TARDIS_BINANCE_FUTURES_L2_INCREMENTAL` path stays `DATA_BLOCKED_COST`. | unknown | Verify the public bookDepth archive's coverage and gaps. Do not buy the L2 feed. |
| C031 | `DATA_BLOCKED_PROVENANCE` | `ADDRESS_LABEL_PROVENANCE_AND_EXCHANGE_POLICY_POINT_IN_TIME` | As-of-dated Binance BTC deposit-address cluster labels, the historical Binance BTC deposit confirmation count by effective date, and block first-seen arrival timestamps as distinct from miner-set header timestamps. | unknown | Leave the card blocked until an as-of label set and a dated confirmation-policy archive are pinned. Do not buy a label vendor feed. |
| C037 | `DATA_BLOCKED_POINT_IN_TIME_SEMANTICS` | `POINT_IN_TIME_SUPPLY_HISTORY` | Point-in-time daily circulating supply per token, and token unlock-schedule revisions. The card names `CIRCULATING_SUPPLY_HISTORY_AGGREGATOR`. | unknown | Leave the card blocked until a point-in-time supply history is pinned. Do not substitute a revised current supply series. |

Critic scores are copied from the completed run and are not re-interpreted: C033 is the only shortlist card with `FEASIBILITY = 3`, `CHEAPNESS = 3`, `STREAM = EXECUTABLE_NOW` and `DATA_STATUS = DATA_READY`.
