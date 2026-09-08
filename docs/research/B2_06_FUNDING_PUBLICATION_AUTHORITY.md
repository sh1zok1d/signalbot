# B2-06 funding publication authority

- **Question:** At what time can a historical settled Binance USD-M `BTCUSDT` `last_funding_rate` value be proven to have become publicly available to a market participant?
- **Verdict:** `FUNDING_PUBLICATION_LATENCY_UNPROVEN`
- **Date:** 2026-09-08
- **Scope:** first-party Binance material only. Third-party blogs, inferred 8h cadence, archive `calc_time`, and guessed safety delays are not authority.
- **Consequence:** materializing Vision funding bytes does **not** make funding legally consumable at a decision time `T`. B2-06 remains blocked.

This note is not a B2-06 RESULT, not a crowding-threshold freeze, and not authorization to open 2025 or 2026.

---

## 1. What would count as a proven rule

A first-party source would have to state, in substance:

1. which timestamp is the **event** (`fundingTime` / archive `calc_time` / settlement instant);
2. which timestamp is **public availability** to a market participant;
3. whether availability is simultaneous with settlement, delayed by a documented interval, or only defined for live websocket/REST snapshots.

Conservative handling of remaining ambiguity would then freeze `legal_available_at` as a deterministic function of those documented clocks. No such function is frozen here.

---

## 2. First-party sources inspected

### 2.1 Official Vision archive README

Source: `https://github.com/binance/binance-public-data` README (fetched 2026-09-08 from `master`).

Quoted semantic:

> The website Binance Data Collection offers easy access for anyone to download Binance's public market data, which is aggregated into daily or monthly files.
> All symbols are supported, with new daily data becoming available the next day and new monthly data at the first monday of the month.

What this proves:

- Vision files are official Binance public-data dumps;
- **archive file** publication is next day (daily) / first Monday (monthly);
- checksum sidecars exist for container integrity.

What this does **not** prove:

- when a settled `last_funding_rate` became visible to a trader at the settlement instant;
- that CSV `calc_time` is `legal_available_at`;
- any millisecond publication latency.

The README does not document USD-M `fundingRate` file columns at all. Treating “daily file available the next day” as the trader-available clock for an 8h funding settlement would mix **archive-object publication** with **market-data publication**. That substitution is rejected.

### 2.2 Official USD-M REST funding-rate history

Endpoint identity (first-party Binance USD-M futures REST):

- `GET /fapi/v1/fundingRate`

Documented response fields in the official futures API family include `symbol`, `fundingTime`, and `fundingRate`. Companion mark-price / premium-index documents expose `lastFundingRate` and `nextFundingTime`.

Inspected surfaces:

- `https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History` (JS-gated from this environment on 2026-09-08);
- historical first-party futures docs in the Binance API documentation family describing `fundingTime` as the funding-fee time and `lastFundingRate` as the last/latest funding rate.

What this proves:

- Binance publishes a historical funding-rate series keyed by `fundingTime`;
- a live premium-index snapshot has a last rate and a next funding time.

What this does **not** prove:

- that `fundingTime` / archive `calc_time` is the public-availability timestamp;
- zero publication latency;
- a documented delay that could be added conservatively;
- that a REST record existing *now* was queryable by a participant at `fundingTime`.

The current presence of a REST row is retrieval-time evidence, not decision-time evidence.

### 2.3 Vision funding CSV schema used by the frozen contract

Frozen archive member columns:

- `calc_time`
- `funding_interval_hours`
- `last_funding_rate`

`calc_time` is frozen as **source event time only**. First-party column names do not include `published_at`, `available_at`, or a latency field. Column presence is not a publication-clock proof.

---

## 3. Explicitly rejected non-authority

The following are **not** used to invent `legal_available_at`:

- “funding is normally every 8 hours”;
- archive `calc_time` coinciding with an 8h UTC grid;
- a REST endpoint currently returning the record;
- third-party websites describing Binance funding;
- a guessed +1s / +1m / +5m safety delay;
- Vision “daily data available the next day” as if it were trader availability at settlement.

---

## 4. Frozen fail-closed rule

```text
funding_publication_semantics_status = FUNDING_PUBLICATION_LATENCY_UNPROVEN
funding_calc_time_is_legal_available_at = false
legal_available_at = null
legal_consumption_from_calc_time_alone = false
caller_constructed_row_cannot_self_attest_publication = true
```

Until a later unit pins a first-party publication rule with quoted semantics and provenance of the authority itself, scientific consumption of materialized funding remains unauthorized.

OI bar-end-exclusive availability (`available_at = create_time + 300000ms`) is a separate, already-frozen conservative rule. It does not rescue funding.

---

## 5. Authorization impact

| Gate | State |
|---|---|
| Funding bytes may be materialized | yes |
| Funding decision-time availability proven | **no** |
| B2-06 inputs legally consumable | **no** |
| `research_authorized` | **false** |
| `outcome_access_authorized` | **false** |
| `b2_06_evaluator_enabled` | **false** |
