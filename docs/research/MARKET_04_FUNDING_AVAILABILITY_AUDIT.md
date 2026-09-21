# MARKET-04 funding availability audit

- **Status:** `FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED`
- **Audit ID:** `MARKET_04_FUNDING_AVAILABILITY_AUDIT`
- **MARKET-04 ID:** `MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK`
- **Role:** `RISK_STATE_FILTER`
- **Primary outcome family:** `FUTURE_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_04_FUNDING_AVAILABILITY_AUDIT.json`](MARKET_04_FUNDING_AVAILABILITY_AUDIT.json)

This unit is a data-semantics / temporal-authority audit only. It does not
run MARKET-04, inspect outcomes, inspect future returns, inspect future MAE,
inspect protected 2025/2026 OOS, ARM an experiment, implement an evaluator,
or create RESULT / preregistration files.

It does not search funding thresholds, search funding percentile windows, or search horizons.

Bound candidate freeze:

```text
PREVIOUS_HEAD = 33ef39988f03bf634ff61c014671b35ba9b0f6ee
PREVIOUS_TREE = 04ae63d2d3412a3988dea20cc17d3e177fe31205
```

```text
audit_outcome = FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED
settled_funding_source = BINANCE_USD_M_HISTORICAL_FUNDINGRATE_AND_VISION_FUNDINGRATE
settled_funding_field = fundingRate_or_last_funding_rate
event_time_semantics = FUNDINGTIME_OR_CALC_TIME_IS_EVENT_OR_SETTLEMENT_CLOCK_NOT_PROVEN_PUBLICATION
settlement_time_semantics = UNPROVEN_AS_PUBLIC_AVAILABILITY_CLOCK
publication_time_semantics = UNSPECIFIED
current_api_semantics_known = true
historical_availability_proven = false
legal_available_at_rule = null
legal_available_at_authority = null
market_04_funding_observable_usable = false
execution_authorized = false
B2_06_FUNDING_BLOCKER_IMPLICATION = UNCHANGED
scientific_outcomes_inspected = false
protected_oos_touched = false
market_03_fundingtime_assumption_is_authority = false
event_time_equals_publication_time = false
MARKET_04_NEXT_STEP = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION
```

---

## 1. Existing blocker

Project authority already states `FUNDING_PUBLICATION_LATENCY_UNPROVEN`
and `legal_available_at = unset` for settled Vision funding. MARKET-03
accepted `fundingTime` availability only as a
`LEVEL_2_FAITHFUL_REIMPLEMENTATION` assumption. That assumption is **not**
scientific authority for MARKET-04.

B2-06 remains blocked because publication semantics were not proven. This
audit does not execute B2-06 and does not change its scientific outcome.

---

## 2. Clock distinction

These clocks remain different unless first-party authority binds them:

```text
EVENT_TIME
SETTLEMENT_TIME
CALCULATION_TIME
PUBLICATION_TIME
API_RESPONSE_TIME
RETRIEVAL_TIME
LEGAL_AVAILABLE_AT
```

A timestamp describing the economic event is not automatically proof that
the final historical value was publicly observable at that exact
timestamp.

Current API field presence is `CURRENT_API_SEMANTICS`. It is not
`HISTORICAL_AVAILABILITY_AUTHORITY`.

---

## 3. Questions

### A. What does `/fapi/v1/fundingRate` `fundingTime` represent?

Official USD-M docs title the endpoint **Get Funding Rate History** and
return `symbol`, `fundingRate`, and `fundingTime`. `startTime` / `endTime`
are documented as inclusive query bounds on that history series.

Evidence strength for field existence and history-query identity:
`DIRECT_FIRST_PARTY_AUTHORITY`.

Evidence strength for “`fundingTime` is the economic funding-event /
settlement clock”: `FIRST_PARTY_INFERENCE` from the field name and history
endpoint. This is not elevated to documented publication fact.

Evidence strength for “`fundingTime` is publication time / legal_available_at”:
`UNPROVEN`.

### B. What does Vision `fundingRate.calc_time` represent?

The official Vision README does not document USD-M `fundingRate` columns
at all. The frozen B2-06 contract observed header
`calc_time,funding_interval_hours,last_funding_rate` and treated
`calc_time` as source event time only.

Evidence strength for an official Vision definition of `calc_time`:
`UNPROVEN`.

Evidence strength for `calc_time == publication time`: `UNPROVEN`.

### C. Is settled `fundingRate` guaranteed known at `fundingTime`?

No. `UNPROVEN`.

### D. Is publication documented as before / at / after settlement?

Publication timing is `UNSPECIFIED`.

### E. Does Binance distinguish predicted, current estimated, and settled rates?

Partially, as current-API identity only:

- historical settled-style series: `GET /fapi/v1/fundingRate` `fundingRate`
  at `fundingTime`;
- live latest rate: `GET /fapi/v1/premiumIndex` `lastFundingRate`
  (“This is the lasted funding rate”);
- live next funding time: `nextFundingTime` / stream `T`;
- live stream `r` labeled only “Funding rate”.

No official historical predicted-funding series with a publication clock
is established here. Predicted / premium-index series must not silently
replace settled funding.

### F. Can a historical settled observation be reconstructed without a post-T final value?

Not under a proven no-lookahead rule. Using `fundingTime <= T` would
repeat the MARKET-03 assumption, which is not authority.

### G. Is there an official historical field strong enough for `legal_available_at <= T`?

No.

### H. Is there another first-party funding-state observable with explicit historical availability?

No usable substitute is established. Possible future data paths are listed
below as `ALTERNATIVE_OBSERVABLE_CANDIDATE` only. They are not selected.

---

## 4. Audit outcome

```text
audit_outcome = FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED
```

This is an acceptable result. The audit does not force resolution.

`legal_available_at_rule` remains unset. No +1s / +1m / +5m latency is
invented. No conservative delay is chosen because it seems safe.

A completed prior settlement plus a later decision boundary is also
`UNPROVEN`. First-party sources do not establish that the settled value
existed publicly before that later boundary. An arbitrary delay is not
sufficient.

Therefore MARKET-04 remains `BLOCKED_OBSERVABLE` for the frozen settled
funding series.

---

## 5. Alternative observable candidates

These are **not** authorized and are **not** silent replacements for
settled historical funding:

| ID | Observable | Usable for MARKET-04 `legal_available_at` |
|---|---|---|
| `LIVE_PREMIUMINDEX_LAST_FUNDING_RATE` | live `lastFundingRate` | false |
| `MARKPRICE_STREAM_FUNDING_RATE` | live stream `r` + event time `E` | false |
| `VISION_ARCHIVE_OBJECT_PUBLICATION` | Vision next-day / first-Monday file clock | false |
| `PREMIUM_INDEX_KLINES` | premium-index klines | false |

Vision next-day / first-Monday wording is first-party for **archive-object
publication**, not trader market-data publication. Mixing those clocks
remains forbidden.

---

## 6. B2-06 consequence

```text
B2_06_FUNDING_BLOCKER_IMPLICATION = UNCHANGED
```

New first-party evidence confirms the existing fail-closed state. It does
not resolve publication semantics for the settled Vision series. B2-06 is
not executed and its scientific outcome is not changed. A separate
governance decision would be required even if later authority appeared.

Historical B2-06 and MARKET-03 artifacts are not rewritten.

---

## 7. MARKET-04 consequence

```text
market_04_funding_observable_usable = false
execution_authorized = false
MARKET_04_NEXT_STEP = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION
```

This unit does not automatically choose another candidate.

---

## 8. Primary sources

Accessed 2026-09-19. Full records are in the JSON twin.

1. Binance USD-M Futures API, Wayback 2022-03-15 of
   `https://binance-docs.github.io/apidocs/futures/en/`, changelog date
   2022-03-01. Sections: Mark Price; Get Funding Rate History; Mark Price
   Stream. Strength: `DIRECT_FIRST_PARTY_AUTHORITY`. Proves current-as-of-2022
   field identity. Does **not** prove publication time.
2. Binance Public Data README,
   `https://raw.githubusercontent.com/binance/binance-public-data/master/README.md`.
   Strength: `DIRECT_FIRST_PARTY_AUTHORITY`. Proves archive-file
   publication (daily next day; monthly first Monday). Does **not**
   document `calc_time` or trader availability at settlement.
3. Official connector
   `binance-futures-connector-python` `um_futures/market.py`. Strength:
   `DIRECT_FIRST_PARTY_AUTHORITY`. Proves current endpoint identity and
   retrieval notes. Does **not** prove `legal_available_at`.
4. Official COIN-M delivery testnet API,
   `https://binance-docs.github.io/apidocs/delivery_testnet/en/`,
   changelog 2020-07-30. Strength: `DIRECT_FIRST_PARTY_AUTHORITY`.
   Corroborates last/latest funding-rate and history-field names. Does
   **not** prove USD-M publication latency.
5. Current official location
   `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History`.
   Strength: `DIRECT_FIRST_PARTY_AUTHORITY` for URL identity only. This
   environment received a JavaScript/bot-check page, so current HTML
   wording is not bound as quoted authority.

Bound local evidence:
`docs/research_data/MARKET_04_FUNDING_AVAILABILITY_AUDIT/`.

---

## 9. Explicitly rejected non-authority

- MARKET-03 `fundingTime` LEVEL_2 assumption;
- MARKET-03 external author implementation;
- `calc_time == publication time`;
- `fundingTime == publication time`;
- invented +1 second / +1 minute / +5 minutes;
- a conservative latency chosen because it seems safe;
- Vision next-day archive publication as trader availability;
- current REST row existence as decision-time evidence;
- blogs, Reddit, StackOverflow, trading tutorials, random GitHub
  repositories, third-party datasets, or exchange competitors.

---

## 10. Lifecycle

```text
full_preregistration_frozen = false
implementation_frozen = false
armed = false
execution_authorized = false
scientific_outcomes_inspected = false
protected_oos_touched = false
```

No MARKET-04 RESULT, ARM, evaluator, or full preregistration is created.
No funding/return correlation, MAE, threshold search, or horizon search
is performed.
