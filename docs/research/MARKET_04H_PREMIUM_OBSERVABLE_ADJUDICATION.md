# MARKET-04H Premium Index observable adjudication

- **Status:** `MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED`
- **Research ID:** `MARKET-04H_PREMIUM_INDEX_ADVERSE_PATH_RISK`
- **Parent:** `MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json`](MARKET_04H_PREMIUM_OBSERVABLE_ADJUDICATION.json)

This unit freezes a historical child-design boundary after the parent
settled-funding availability audit failed. It does not execute MARKET-04
or MARKET-04H, inspect scientific outcomes, or rewrite the parent.

```text
parent_research_id = MARKET-04_FUNDING_STATE_ADVERSE_PATH_RISK
research_id = MARKET-04H_PREMIUM_INDEX_ADVERSE_PATH_RISK
lineage_kind = OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE
scientific_outcome_seen_before_substitution = false
independent_confirmation_of_parent = false
market_03_independent_replication = false
observable_name = BINANCE_USD_M_BTCUSDT_PREMIUM_INDEX_KLINES
observable_semantic_role = FUNDING_PRESSURE_PROXY
settled_funding_claimed = false
primary_outcome_family = FUTURE_CROWDING_SIDE_ADVERSE_PATH_RISK
archive_day_timezone = UNRESOLVED
safe_usable_at_rule = null
safe_usable_at_authority = null
safe_usable_at_proven = false
close_time_equals_publication_time = false
revision_ledger_claimed_exhaustive = true
relevant_files_revision_status = REVISION_STATUS_UNRESOLVED
historical_coverage_usable = false
same_support_required = true
scientific_outcomes_inspected = false
protected_oos_touched = false
implementation_frozen = false
armed = false
execution_authorized = false
next_unit = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION
```

Bound parent / audit (not rewritten):

```text
PARENT_SELECTION_HEAD = 33ef39988f03bf634ff61c014671b35ba9b0f6ee
PARENT_SELECTION_TREE = 04ae63d2d3412a3988dea20cc17d3e177fe31205
AUDIT_HEAD = 6e58882a0b7b01036a03cd9c2ec5af7cf7b7e046
AUDIT_TREE = 714cd0b3c4708b410af862448323bfda99f15914
AUDIT_OUTCOME = FUNDING_HISTORICAL_AVAILABILITY_UNRESOLVED
```

---

## 1. Child identity

MARKET-04H is still MARKET-04 lineage. It is not a new independent
hypothesis and is not an independent replication of the parent or of
MARKET-03.

```text
LINEAGE_KIND = OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE
INDEPENDENT_CONFIRMATION_OF_PARENT = NO
```

The parent scientific mechanism remains: funding/crowding state may
contain incremental information about future adverse-path risk beyond
price/trend/volatility state.

The child does **not** claim to observe final settled funding. It asks
whether `PREMIUM_INDEX_STATE`, as a first-party Binance observable related
to the funding mechanism, adds stable incremental information about
subsequent adverse-path risk.

Required label: `FUNDING_PRESSURE_PROXY`.

Forbidden labels: `FINAL_SETTLED_FUNDING`, `EXACT_FUNDING_RATE_AT_T`,
`KNOWN_SETTLED_FUNDING_AT_T`.

---

## 2. First-party authority checklist

A. Funding-rate mechanism includes a premium component: **yes**. Official
USD-M docs title `GET /fapi/v1/premiumIndex` as **Mark Price and Funding
Rate**. Official COIN-M docs name `GET /dapi/v1/premiumIndexKlines`
**合约溢价指数K线** (contract premium-index klines).

B. Premium Index is a Binance-defined market observable: **yes**.

C. Binance Public Data provides futures premium klines: **yes**. Official
python README documents `download-futures-premiumPriceKlines.py`. The
checked-in script and `get_path` use data type `premiumIndexKlines`.
Official Vision listing shows

`data/futures/um/daily/premiumIndexKlines/BTCUSDT/`

with `1d` and `1h` prefixes. The alias path `premiumPriceKlines` is empty.

D. Daily files become available the next day: **yes**, official README.

E. Archived files may later be updated and Binance maintains an update
ledger it calls exhaustive: **yes**, official README Updates table.

These facts do **not** by themselves authorize a no-lookahead historical
construction.

---

## 3. Temporal fail-closed

This unit does **not** treat premium kline `close_time` as publication
time or `legal_available_at`. It does **not** treat `fundingTime` as
publication time.

```text
do_not_treat_fundingTime_as_publication_time = true
do_not_treat_close_time_as_publication_time = true
```

Candidate rule considered, then **not adopted**:

```text
SAFE_USABLE_AT(D) = start of calendar day D+2
safe_usable_at_proven = false
```

Required first-party conditions were:

1. timezone/calendar boundary of archive day `D`;
2. that the daily file must have become available during `D+1`;
3. therefore by the beginning of `D+2` it already existed publicly.

Official README proves (2) only as the words “the next day”. Official
scripts use naive `YYYY-MM-DD` `date` objects with no timezone.
No first-party source in this audit states that archive day `D` is UTC,
UTC+8, or any other zone. Unanswered official-repo issue #479 asks for
UTC-day containment and is not authority.

```text
archive_day_timezone = UNRESOLVED
```

Without that boundary, `D+2` is not a logically unavoidable ordering.
The rule is not adopted. No conservative extra delay is invented.

---

## 4. Revision / retrospective archive risk

Official README: archived files may be updated; the listed updates are
called exhaustive.

Inspected ledger members (path lists only):

- `updates/2022-08-08_kline_updates.zip` — spot daily klines only; **0**
  `premiumIndexKlines` rows; **0** `futures/um` rows.
- `updates/2022-04-21_aggregate_trade_updates.zip` — spot monthly
  aggTrades; no premium futures paths.

So the documented replacements do not cover BTCUSDT USD-M
premiumIndexKlines.

That is **not** proof the current objects are the historically first
published bytes. Official Vision listing metadata for
`BTCUSDT-1d-2019-12-24.zip` shows `LastModified 2023-07-07T07:10:16.000Z`,
after both ledger dates, with no matching original/replacement CHECKSUM
row.

```text
relevant_files_revision_status = REVISION_STATUS_UNRESOLVED
current_download_treated_as_original = false
```

A file downloaded today cannot be treated as the historically available
version. No first-party historical byte recovery is available. The
required period is therefore unusable for a no-lookahead child.

---

## 5. Outcome

```text
adjudication_outcome = MARKET_04H_PREMIUM_OBSERVABLE_BLOCKED
historical_coverage_usable = false
data_manifest_created = false
```

No `MARKET_04H_PREMIUM_DATA_MANIFEST.json` is created because feasibility
did not pass.

If a later first-party source established archive-day timezone **and**
historical byte identity, the simplest later interval to adjudicate would
be official daily `1d` premiumIndexKlines, using a continuous Premium
Index summary (arithmetic mean, or time-weighted mean only if missing
intervals require it). That later choice is not made here and is not
chosen by returns.

---

## 6. Frozen question family only

Does Premium Index funding-pressure state add stable incremental information about future crowding-side adverse-path risk beyond price/trend/volatility state?

This unit does not inspect future returns.

```text
PRIMARY_OUTCOME_FAMILY = FUTURE_CROWDING_SIDE_ADVERSE_PATH_RISK
pnl_is_primary_outcome = false
```

Horizon, adverse-path statistic, baseline specification, uncertainty
method, and materiality remain for a later preregistration unit **if**
the observable is later unblocked. This unit does not inspect future MAE,
inspect future returns, calculate correlations, compare Premium Index
buckets, search horizons, or run regressions.

Same-support contract, if later unblocked:

```text
BASELINE  = simple price/trend/volatility state
CANDIDATE = exact BASELINE + Premium Index funding-pressure proxy
same_support_required = true
```

Every feature would require `safe_usable_at <= T`. That predicate cannot
be implemented while `safe_usable_at` is unproven.

---

## 7. Lineage fences

MARKET-03 may motivate the mechanism only. This unit does not inherit
EMA600, funding threshold 55, 180d percentile, strategy entry rules, or
the author backtest drawdown objective. A later positive MARKET-04H
would not be an independent replication of MARKET-03.

MARKET-01 / MARKET-02 are lineage context only. They are not positive
support for this Premium Index adverse-path formulation.

---

## 8. Anti-rescue and one-shot

Once later executed under a new unblocked identity or a later unblocked
continuation, this research identity cannot be rescued by changing
observable, aggregation, sign, horizon, primary outcome, baseline,
materiality, uncertainty method, subset, year range, regime, or side
treatment. A material post-outcome change needs a new identity.

```text
implementation_frozen = false
armed = false
execution_authorized = false
scientific_outcomes_inspected = false
protected_oos_touched = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
```

No run token is consumed. No RESULT or ARM is created.

---

## 9. Next unit

```text
NEXT_UNIT = BLOCKED_OBSERVABLE_OR_NEW_CANDIDATE_SELECTION
```

This unit does not automatically choose another candidate.
