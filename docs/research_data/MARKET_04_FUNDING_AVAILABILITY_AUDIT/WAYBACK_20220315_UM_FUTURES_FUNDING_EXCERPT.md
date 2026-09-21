# Excerpt: official Binance USD-M Futures API (Wayback 2022-03-15)

- **Publisher:** Binance
- **Original URL:** https://binance-docs.github.io/apidocs/futures/en/
- **Archive URL:** https://web.archive.org/web/20220315120000id_/https://binance-docs.github.io/apidocs/futures/en/
- **Captured document date in page changelog:** 2022-03-01 (latest dated Change Log entry on this snapshot)
- **Accessed:** 2026-09-19
- **Full snapshot SHA256:** `e152c724228a18a87f685f1987231ef1f5bf00770aaa2b863c9dd6382b59134e`
- **Purpose:** bind first-party wording for `fundingTime`, `lastFundingRate`, and mark-price stream `r` / `T` / `E`.
- **Not stored here:** live funding values used as scientific outcomes. Example JSON numbers below are documentation examples from the official page.

This file is an excerpt. It does not rewrite the official page.

---

## Mark Price (`GET /fapi/v1/premiumIndex`)

Official heading: `Mark Price`

Official subtitle: `Mark Price and Funding Rate`

Official example comments:

```text
"lastFundingRate": "0.00038246",  // This is the lasted funding rate
"nextFundingTime": 1597392000000,
"interestRate": "0.00010000",
"time": 1597370495002
```

`lasted` is the official spelling on this page.

---

## Get Funding Rate History (`GET /fapi/v1/fundingRate`)

Official heading: `Get Funding Rate History`

Official response example fields: `symbol`, `fundingRate`, `fundingTime`.

No comment on this snapshot defines `fundingTime` as publication time, available-at time, or zero-latency public observability.

Official parameter table:

```text
startTime  Timestamp in ms to get funding rate from INCLUSIVE.
endTime    Timestamp in ms to get funding rate  until INCLUSIVE.
limit      Default 100; max 1000
```

Official notes:

```text
If startTime and endTime are not sent, the most recent limit datas are returned.
If the number of data between startTime and endTime is larger than limit, return as startTime + limit.
In ascending order.
```

---

## Mark Price Stream

Official comments:

```text
"E": 1562305380000,         // Event time
"r": "0.00038167",          // Funding rate
"T": 1562306400000          // Next funding time
```

Official prose:

```text
Mark price and funding rate for a single symbol pushed every 3 seconds or every second.
```

The page does not state whether stream field `r` is the last settled rate, a predicted next rate, or when a historical REST `fundingRate` row became queryable.
