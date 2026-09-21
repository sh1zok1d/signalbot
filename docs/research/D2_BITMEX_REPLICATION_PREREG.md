# D2 BitMEX replication preregistration

**Unit:** `D2_BITMEX_REPLICATION_PREREG_FREEZE`  
**Kind:** outcome-blind replication preregistration. **Not executed.**

## Evidence class

`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`

This is **not** `EXACT_BINANCE_CONFIRMATION`. A later positive result would
show portability of `D2 / RULE_1 / RV_ABSTENTION` across an earlier era,
BitMEX, and an inverse perpetual last-trade environment. Protected Binance
2025/2026 remains an unopened same-venue reserve.

## Frozen rule (unchanged)

Candidate: `D2 / RULE_1 / RV_ABSTENTION`

ABSTAIN(t)=1 iff RV_BTC_24H(t) > P90 of the previous 250 COMPLETED valid decision-point RV values with t excluded.

`RV_BTC_24H(t)` is the frozen D2 definition: `sqrt(sum of 288 squared 5m log
returns)` via `rv_btc_24h`. No threshold sweep, no P85/P95 companion, no
alternate RV estimator, no alternate trailing window.

Direction: `BTC_SIDE(t) = sign(BTC_RET_24H(t)) via frozen btc_ret_24h / btc_side_from_ret`. Last-trade XBTUSD path. Do not invert
because the contract is inverse. Do not use mark, index, funding, or inverse
PnL. Exact-zero 24h return remains ineligible.

Entry: 5m open at `T = 00:05:00Z` (MARKET-05/06 convention, not redesigned).  
Outcome: 288 future 5m bars.  
Severity: frozen `arithmetic_mae` price-path metric.

## Sealed BitMEX authority

Parser `D2_BITMEX_PRE2020_PARSER_V1`. Timestamp = bucket end;
`open_time = timestamp - 5m`. Reacquisition of a different dataset is
forbidden. Execution must fail closed if authority or canonical hashes change.

- authority SHA256: `2a48e025a9ecb596f7a37646a39367cae031e5aa3fd0555416c3fab692594dff`
- canonical JSONL SHA256: `b145013cbcda34294104a0234c89fa9e27965bded66e3bc18b23753dde03fd0f`
- canonical gzip SHA256: `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`

## Interval and missing data

```
FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00.000Z
LAST_RULE_ELIGIBLE_T  = 2019-12-30T00:05:00.000Z
EXPECTED_ELIGIBLE_N   = 1069
2017 / 2018 / 2019    = 341 / 364 / 364
```

All 24h future paths complete strictly before `2020-01-01T00:00:00Z`.
Do not subsample to 815. 815 is a power floor only.

Known gap: 288 missing 5m opens
`2016-12-06T23:55:00.000Z` through `2016-12-07T23:50:00.000Z`.
Handling: `NO_FILL_NO_INTERPOLATION_NO_FORWARD_FILL_NO_SYNTHETIC`. Decisions whose RV window, trailing
valid history, entry, or future path need those bars are ineligible. Gap-day
decisions 2016-12-06/07/08 are excluded. Trailing-250 uses previous completed
valid decision-point rows, not fabricated calendar dates.
`TRAILING_250_VALID_HISTORY_VERIFIED = true`.

If constructed sample identity at execution differs from 1069 / frozen first /
frozen last, classify `D2_BITMEX_REPLICATION_INVALID`.

## Comparator and randomization

`RATE_MATCHED_RANDOM_ABSTENTION` with **year-matched** `K_y` inside 2017, 2018,
and 2019. Pooled-K across years is forbidden.

```
N_RANDOM_CONTROLS = 10000
REPLICATION_RANDOM_SEED = 20260921125
RNG = numpy.random.Generator(numpy.random.PCG64(20260921125))
```

`MC_P` is diagnostic. The percentile gate is authoritative.

## Gates (unassigned)

```
STATISTICAL_GATE = MU_RULE > CONTROL_P95
PRACTICAL_GATE   = DELTA >= 0.20 * UNCONDITIONAL_MEAN
PRIMARY_PASS_RULE = STATISTICAL_GATE and PRACTICAL_GATE
```

Yearly 2017/2018/2019 breakdowns are diagnostic only. They cannot rescue or
replace the pooled primary decision. No 2/3-year requirement.

Classifications frozen, **not assigned**:
`D2_BITMEX_REPLICATION_SUPPORTED` /
`D2_BITMEX_REPLICATION_NOT_SUPPORTED` /
`D2_BITMEX_REPLICATION_INVALID`.

## Power planning (not a sampling cap)

`REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (power `0.801`, Wilson 95% CI
`[0.7751234971811168, 0.824572794210579]`). `N=820` point-estimate `0.794`.
No further power search. Use all 1069 legal rows.

## Implementation binding

Reuse frozen `rv_btc_24h`, `btc_ret_24h`, `arithmetic_mae`. Adapt BitMEX
timestamp plumbing only. Execution is **not** authorized in this unit.

## Not created / not opened

- BitMEX D2 outcome: false
- Protected 2025/2026: false / false
- MARKET-07 / ARM: false

`NEXT_UNIT = D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`  
`PR_READY_TO_MERGE = True`
