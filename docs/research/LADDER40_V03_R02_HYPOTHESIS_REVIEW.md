# r02 generated hypothesis review

Offline export of `ladder-40-card-v03-r02`. The cards and critic outputs below are copied from the source journal. This document does not rank them, score them again, or choose any of them.

Critic outputs are `SOURCE_R02_EXISTING_JUDGMENTS`. `SOURCE_CRITIC_OUTPUTS_USED_AS_OFFICIAL_FOR_DERIVED = false`.

## Corpus summary

- Planned slots: 40
- Provider emitted cards: 31
- Valid emitted: 30
- Invalid emitted: 1
- Missing slots: 9
- Duplicate ids: 0
- Malformed items without a usable candidate id: 0
- Valid rate of emitted: 30/31
- Valid rate of planned: 30/40
- Candidate-table VALID: 30
- Candidate-table HARD_FAIL: 10
- Valid by complexity: {"ATOMIC": 12, "COMPOSITE": 2, "CONDITIONAL": 11, "INTERACTION": 5}
- Valid by mechanism family: {"A": 2, "B": 2, "C": 2, "D": 2, "E": 2, "F": 2, "G": 2, "H": 2, "I": 2, "J": 2, "NEW_FAMILY_PROPOSAL": 10}
- Novelty complete: 14
- Feasibility complete: 13
- Red team complete: 13
- Uncertain calls: 1

Generation:1 emitted one card, `C011`, and that card failed intake. `C012` through `C020` were not in the provider list.

## Generator round completeness

Counts below are taken from each round's stored raw response, then checked against the candidate table.

### generation:0

- EXPECTED_SLOT_IDS: C001, C002, C003, C004, C005, C006, C007, C008, C009, C010
- PROVIDER_EMITTED_ITEM_COUNT: 10
- PROVIDER_EMITTED_CANDIDATE_IDS: C001, C002, C003, C004, C005, C006, C007, C008, C009, C010
- VALID: C001, C002, C003, C004, C005, C006, C007, C008, C009, C010
- INVALID_EMITTED: (none)
- MISSING_SLOT_IDS: (none)
- EXTRA_IDS: (none)
- DUPLICATE_IDS: (none)
- MALFORMED_ITEM_INDEXES: (none)
- Call key: `0982c9645c64f368832a671dd24968d7fcc7b0a0c60ca88a297b2b69e40085a6`
- Response id: `msgbatch_01KSKFCfCv65D92PKJx21cNk`

### generation:1

- EXPECTED_SLOT_IDS: C011, C012, C013, C014, C015, C016, C017, C018, C019, C020
- PROVIDER_EMITTED_ITEM_COUNT: 1
- PROVIDER_EMITTED_CANDIDATE_IDS: C011
- VALID: (none)
- INVALID_EMITTED: C011
- MISSING_SLOT_IDS: C012, C013, C014, C015, C016, C017, C018, C019, C020
- EXTRA_IDS: (none)
- DUPLICATE_IDS: (none)
- MALFORMED_ITEM_INDEXES: (none)
- Call key: `e0efc9357cae5a94ba455c22a381fa10bc5f2e1bce76943002b9414eec50358f`
- Response id: `msgbatch_018XX1hF6weUpbhuk4JkmhxU`

### generation:2

- EXPECTED_SLOT_IDS: C021, C022, C023, C024, C025, C026, C027, C028, C029, C030
- PROVIDER_EMITTED_ITEM_COUNT: 10
- PROVIDER_EMITTED_CANDIDATE_IDS: C021, C022, C023, C024, C025, C026, C027, C028, C029, C030
- VALID: C021, C022, C023, C024, C025, C026, C027, C028, C029, C030
- INVALID_EMITTED: (none)
- MISSING_SLOT_IDS: (none)
- EXTRA_IDS: (none)
- DUPLICATE_IDS: (none)
- MALFORMED_ITEM_INDEXES: (none)
- Call key: `aedc723c0adca72b497658a904915e0551473e087601ba19acf2083778d2dcae`
- Response id: `msgbatch_01Rfax8h1jSLJs4rMwcGgxKg`

### generation:3

- EXPECTED_SLOT_IDS: C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- PROVIDER_EMITTED_ITEM_COUNT: 10
- PROVIDER_EMITTED_CANDIDATE_IDS: C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- VALID: C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- INVALID_EMITTED: (none)
- MISSING_SLOT_IDS: (none)
- EXTRA_IDS: (none)
- DUPLICATE_IDS: (none)
- MALFORMED_ITEM_INDEXES: (none)
- Call key: `0c88f84b8e34762784f9f22a7882154281d0cd9edba0de3be4bc12be0c0517f4`
- Response id: `msgbatch_01NZAFijLhuW91norTMToDwF`

## VALID hypotheses

### C001 — Liquidation-sweep wick count and next-24h unsigned tail excursion

Frozen complexity class: ATOMIC
Frozen mechanism family: A
Frozen information source: KLINES
Round: generation:0

#### CANDIDATE_ID

```text
C001
```

#### NAME

```text
Liquidation-sweep wick count and next-24h unsigned tail excursion
```

#### MECHANISM_FAMILY

```text
A
```

#### MECHANISM

```text
Sweep-and-reclaim 1m wicks are footprints of forced liquidation and stop flow hitting a thin book. Such a book state lasts for hours and raises the unsigned tail excursion of the next 24h beyond what RV implies.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Exchange liquidation engines and clustered stop orders send market orders that ignore price. When near-touch depth is thin, such an order walks several levels inside one minute and price then reclaims as makers refill the book. This leaves a long wick with a close back near the bar open. Each sweep imposes adverse selection on resting liquidity providers. They respond for hours by quoting less size, for inventory and toxicity reasons. The leveraged positioning that produced the sweep is usually only partly flushed. A high count of sweep-and-reclaim bars over a day therefore marks a fragile book: later shocks of ordinary size should travel further before meeting resting liquidity. RV cannot separate this fragility from informative trending moves, because RV is high in both cases. The reclaim geometry isolates the non-informative, forced-flow part. As an abstention mechanism, a decision process would stand aside from new exposure when this fragility footprint is elevated.
```

#### INFORMATION_SOURCE

```text
KLINES
```

#### OBSERVABLE

```text
SWEEP_COUNT_24H(T): the number of 1m bars in (T-24h, T] whose high-low range is at least k times the trailing 30-day median 1m range evaluated at T, and whose close retraces at least a fraction r of the wick. For an upper wick the retrace is (high-close)/(high-low); for a lower wick it is (close-low)/(high-low).
```

#### FUNCTION

```text
Unconditional tail-risk characterization: test whether the count of sweep-and-reclaim 1m bars in the 24h before a daily decision time relates to the unsigned maximum close excursion over the next 24h, beyond RV-matched controls, for use as an abstention diagnostic.
```

#### PRIMARY_TARGET

```text
TAIL_EXC_24H: the maximum over 1m closes in (T, T+24h] of |log(close_t/close_T)|, divided by the trailing 30-day mean RV_24H evaluated at T. The contrast is top-quintile SWEEP_COUNT_24H days minus matched controls.
```

#### HORIZON

```text
24 hours from each daily decision time T at 00:00 UTC
```

#### BASELINE_OR_NULL

```text
Controls are decision days in the bottom three SWEEP_COUNT_24H quintiles, matched 1:1 on YEAR x trailing RV_24H decile x weekday and compared within those strata. The null distribution comes from permuting the SWEEP_COUNT_24H quintile label within YEAR x RV decile strata. A second null is a GARCH(1,1)-t surrogate fitted on 1m log returns, with a simulated high-low envelope from the empirical range-to-return ratio. It produces both SWEEP_COUNT_24H and TAIL_EXC_24H from one volatility-clustering model, which tests whether the association is implied by volatility dynamics alone.
```

#### FALSIFIER

```text
The fragility mechanism is rejected for this observable in either of two cases. First, the mean TAIL_EXC_24H on top-quintile SWEEP_COUNT_24H days minus matched controls is at or below the 95th percentile of the within-stratum permutation null. Second, the GARCH surrogate reproduces a gap of comparable size, within its own 5-95 percentile band.
```

#### NEAREST_TESTED_MECHANISM

```text
D2
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D2 abstains on the RV level itself. Here RV is held fixed by matching, and the conditioning variable is the reclaim geometry of individual 1m bars, a microstructure footprint that RV cannot tell apart from informative moves. D7 targets persistence of an hourly impact state rather than next-day tail excursion. D8 conditions on single P99 shocks with high volume, not on a count of reclaimed wicks.
```

#### WHY_NOT_A_RESCUE

```text
It neither re-thresholds D2's RV rule nor reuses its MAE target. The conditioning variable is new and RV is an explicit matched control, so a positive cannot come from relabelling high-RV days.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 6,
  "PARAMETERS": {
    "range_multiple_k": [
      4,
      6,
      8
    ],
    "retrace_fraction_r": [
      0.6,
      0.8
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Bad prints and exchange incidents that create spurious wicks. Weekend thinness. Scheduled macro releases that cluster large bars. Contract-specification or tick changes on the BTCUSDT perpetual. Residual RV differences within matching deciles. Index-price anomalies that trigger mark-price liquidations without real order flow.
```

#### NO_LOOKAHEAD_RULE

```text
SWEEP_COUNT_24H, the trailing 30-day median 1m range and the RV_24H decile use only 1m bars closed at or before T. Quintile cut points are computed on a trailing 365-day window ending at T. TAIL_EXC_24H uses only bars strictly inside (T, T+24h]. Matching strata are fixed from information at T.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m open, high, low and close used for wick geometry, trailing range medians, RV_24H and close-path excursions",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low: one ready dataset, 1m aggregation into daily counts, stratified matching, a permutation null and one GARCH surrogate simulation.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That a forced-flow footprint carries tail-risk information orthogonal to RV level. Abstention rules could then be keyed to book fragility rather than to volatility, which motivates direct depth measurement.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate sweep-reclaim wick counts as an abstention variable beyond RV. It would also show that kline-level forced-flow footprints are subsumed by volatility clustering, which lowers the priority of order-book fragility work built on this premise.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It separates forced-flow book fragility from volatility level using only ready data, and its outcome decides whether liquidation footprints justify costly order-book follow-up.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `ecf8444bda17d75a1dde9f504092a4b16e679e3395df82de95cd1179e13855d6`
  - Response id: `resp_0c35fdd1279f6a7b006abfb30e55f887d1ae35cb3b5797ea3a`
  - Actual cost USD: 0.108136
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29028,
    "output_tokens": 5008,
    "reasoning_tokens": 3860
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 1,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `f98d378334a0c802df8f9d918d5b3ff607367d074cafb111baa96be1f0ee1720`
  - Response id: `null`
  - Actual cost USD: 0.000624
  - Usage:

  ```json
  {
    "completion_tokens": 360,
    "prompt_tokens": 4438,
    "reasoning_tokens": 269
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 3,
    "CHECKS": {
      "BLOCKER_RESOLVED": true,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": true,
      "POINT_IN_TIME": true,
      "PROVENANCE": true
    },
    "DATA_STATUS": "DATA_READY",
    "FEASIBILITY": 3,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `7ac45e9e455a7e0efcd191295797817ae764c747b3d7e191e1e9d923e62a0203`
  - Response id: `resp_0321f0e3c8158a3f006abfb3567fc087d1aab8a0add0c03a05`
  - Actual cost USD: 0.025684
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1927,
    "output_tokens": 2183,
    "reasoning_tokens": 2070
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": false,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 2
    }
  }
  ```


### C002 — Weekend perp-premium propagation into OKX spot

Frozen complexity class: CONDITIONAL
Frozen mechanism family: B
Frozen information source: CROSS_VENUE
Round: generation:0

#### CANDIDATE_ID

```text
C002
```

#### NAME

```text
Weekend perp-premium propagation into OKX spot
```

#### MECHANISM_FAMILY

```text
B
```

#### MECHANISM

```text
While fiat rails and institutional desks are inactive on weekends, a Binance perp premium over OKX spot carries the directional demand of leveraged participants, and spot drifts toward the perp rather than the perp reverting.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
On weekdays, cross-venue relative-value desks with fiat and collateral access close Binance-perp versus OKX-spot gaps by taking offsetting positions on both legs, so neither leg drifts in a predictable direction. On weekends bank transfer rails are closed and many institutional desks run reduced books and reduced collateral mobility. Leveraged perpetual participants then dominate incremental price formation, while OKX spot makers update quotes toward the perp with a lag. If a weekend perp premium reflects real directional demand from leveraged participants, not noise, the spot leg should drift in the premium's direction over the next minutes to hours. The constraint is the weekend immobility of balance-sheet capital that would otherwise neutralize the gap.
```

#### INFORMATION_SOURCE

```text
CROSS_VENUE
```

#### OBSERVABLE

```text
Z_D(T): the aligned 5m-close log(perp/OKX spot) at T minus its trailing 7-day median, divided by its trailing 7-day median absolute deviation
```

#### FUNCTION

```text
Regime fixed in advance: WEEKEND, meaning decision times T from Saturday 00:00 UTC to Sunday 23:55 UTC. Within this regime only, measure the mean OKX spot log return over (T, T+H] signed by sign(Z_D(T)), for events with |Z_D(T)| at least z. Weekday events are neither pooled nor used to choose z or H.
```

#### PRIMARY_TARGET

```text
ALIGNED_SPOT_RET_H: sign(Z_D(T)) x log(OKX spot close at T+H / OKX spot close at T), averaged over de-clustered weekend events with |Z_D(T)| at least z, minus the matched within-regime control mean
```

#### HORIZON

```text
H in {30 minutes, 2 hours} after each weekend 5m event close T, with events de-clustered to a minimum 2-hour spacing
```

#### BASELINE_OR_NULL

```text
The within-regime controls are weekend 5m times with |Z_D| below 0.5, matched on hour-of-day and on the trailing 1h perpetual absolute-return bucket. A sign-flip null randomizes sign(Z_D) within week x hour blocks. A block-bootstrap null resamples joint perp and spot 5m returns within weekends in 1-hour blocks; it keeps contemporaneous co-movement, destroys signed premium-to-spot lead structure, and produces the full ALIGNED_SPOT_RET_H statistic.
```

#### FALSIFIER

```text
The weekend propagation claim is rejected in either of two cases. First, the mean ALIGNED_SPOT_RET_H over weekend events minus the matched within-regime control mean does not exceed the 95th percentile of the sign-flip null. Second, the statistic is negative, meaning the perp reverts toward spot rather than spot following the perp.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C002
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C002 conditions on which leg opened the dislocation and measures the cross-venue midpoint. This card conditions on the signed premium level, measures only the spot leg, and fixes a weekend regime motivated by capital immobility. MARKET-06 used the unsigned dislocation for adverse-path MAE, and D9 attributed closure among extremes, not signed spot drift.
```

#### WHY_NOT_A_RESCUE

```text
The regime comes from an external institutional fact, the weekend closure of fiat rails, not from outcomes. The observable is the signed premium level rather than opening-leg identity. No weekday result is reused or re-cut.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "dislocation_z_threshold": [
      2,
      3
    ],
    "horizon": [
      "30m",
      "2h"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Stale OKX spot closes on thin weekend bars, which would cause mechanical catch-up rather than information transfer; the dataset holds closes only, so staleness cannot be controlled with spot volume. Binance funding settlements at 00:00 UTC on weekend days. USDT pricing differences between venues. Weekend liquidation cascades that move the perp first. Bar alignment errors in the feasibility snapshot.
```

#### NO_LOOKAHEAD_RULE

```text
Z_D(T) uses aligned 5m closes at or before T, with its trailing 7-day median and MAD ending at T. The return is measured from the close at T to the close at T+H. The regime label depends only on the UTC calendar. Thresholds z and H are frozen before outcomes are computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Binance BTCUSDT perpetual and OKX BTC spot aligned 5m closes used for Z_D, spot returns and the bootstrap null",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low: one ready aligned 5m dataset, event de-clustering, matched controls and two resampling nulls.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That the absence of balance-sheet capital changes which leg resolves a cross-venue gap, and that weekend perp premia carry leveraged-participant information that spot absorbs with a lag.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate the weekend capital-immobility channel as a source of directional information in the perp premium. It would also suggest that weekend premia are noise resolved symmetrically or by the perp leg.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It tests a specific institutional-calendar channel for directional information in the cross-venue premium, which no prior card measured on the spot leg.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `dbb5a5445009e2f8baf60e33bb73798c51fe5a681a6be8ab4eca58d9f9a8a764`
  - Response id: `resp_04fbf63b2468e31f006abfb37735e087d19b3a5ffd4cf21211`
  - Actual cost USD: 0.091110
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 28895,
    "output_tokens": 3332,
    "reasoning_tokens": 2184
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 0,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `a4e7678d6311f4a3b7438b5a1d87678f32cdd153b1a7a8b885ca5080ce8cb957`
  - Response id: `null`
  - Actual cost USD: 0.000666
  - Usage:

  ```json
  {
    "completion_tokens": 470,
    "prompt_tokens": 4305,
    "reasoning_tokens": 379
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 3,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": true,
      "POINT_IN_TIME": true,
      "PROVENANCE": true
    },
    "DATA_STATUS": "DATA_READY",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `58e708c43e5ef635e7ff07ba4afb6478a60489cbe97cb9f387aea9aa2bbb5a8a`
  - Response id: `resp_08b30905bdc97bc0006abfb3a8525087d1aaa2b613cd2bb790`
  - Actual cost USD: 0.023158
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1794,
    "output_tokens": 1957,
    "reasoning_tokens": 1844
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": false,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 2,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 2
    }
  }
  ```


### C003 — Inverse-collateral convexity and down-move cascade run length

Frozen complexity class: INTERACTION
Frozen mechanism family: C
Frozen information source: PRE2020_SURFACE
Round: generation:0

#### CANDIDATE_ID

```text
C003
```

#### NAME

```text
Inverse-collateral convexity and down-move cascade run length
```

#### MECHANISM_FAMILY

```text
C
```

#### MECHANISM

```text
Inverse-contract payoff convexity accelerates margin depletion of leveraged longs on falling prices. Down-move cascades should therefore be more contiguous on BitMEX XBTUSD than on the linear Binance perpetual, beyond the general direction asymmetry and the general contract difference.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
On the inverse XBTUSD contract, margin and PnL are in BTC while the contract is denominated in USD. The BTC loss of a leveraged long is N(1/P - 1/P0), which grows convexly as price falls, and the collateral also loses USD value. As price drops, each further tick consumes more of the BTC margin of leveraged longs, so liquidation thresholds bunch up and forced selling begets more forced selling. On the up side, the BTC loss of leveraged shorts is concave and bounded. On USDT-margined linear contracts, PnL is linear in price and collateral is stable, so this convexity is absent. Down-move cascades should therefore run longer than up-move cascades on the inverse contract, by more than they do on the linear contract. A general down-vs-up asymmetry (leverage effect, panic) and any general venue or era difference are main effects; the contract-design channel lives only in the interaction.
```

#### INFORMATION_SOURCE

```text
PRE2020_SURFACE
```

#### OBSERVABLE

```text
RUN_LEN(J): the number of consecutive 5m bars immediately after trigger bar J whose return has the same sign as J and an absolute value of at least m trailing-30-day 5m return standard deviations. Trigger bars are 5m bars with |return| at or above the q-th percentile of trailing 30-day 5m absolute returns.
```

#### FUNCTION

```text
Interaction characterization of path morphology in a 2x2 design, DIRECTION (down, up) x CONTRACT (BitMEX inverse in the pre-2020 sample, Binance linear in 2020-01..2024-12), estimated within daily-RV bins.
```

#### PRIMARY_TARGET

```text
The coefficient on the product of the down-direction and inverse-contract indicators in a regression of log(1+RUN_LEN) with daily-RV-bin fixed effects. This equals [inverse down minus inverse up] minus [linear down minus linear up] within matched RV bins.
```

#### HORIZON

```text
A run of at most 12 consecutive 5m bars (60 minutes) after each trigger bar
```

#### BASELINE_OR_NULL

```text
The main-effect baseline regresses log(1+RUN_LEN) on Down-move direction of the triggering 5m jump, on Inverse-collateral contract structure of BitMEX XBTUSD versus USDT-margined Binance perpetual, and on daily-RV-bin fixed effects within each contract. The claim is only the coefficient on the product of the two components, beyond both main effects. For the null, within each contract every UTC day's 5m return path is multiplied by an independent random sign. This keeps intraday clustering, magnitudes and run structure, but equalizes down and up dynamics within each contract. The surrogate produces RUN_LEN and the full interaction statistic, so its distribution is centered on no direction-specific contract effect.
```

#### FALSIFIER

```text
The inverse-collateral convexity channel is rejected at 5m resolution if the interaction coefficient is at or below the 95th percentile of the day-sign-flip surrogate distribution, or if it is negative.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C003
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C003 compared unsigned contiguity of the largest daily 5m moves between eras. This card signs moves, measures run length after a trigger bar, and identifies a payoff-convexity channel through a direction x contract interaction that differences out the era main effect. H03 and B2-03 address continuation after impulses on one contract, not contract design.
```

#### WHY_NOT_A_RESCUE

```text
It does not re-test whether eras differ in contiguity; that main effect sits in the baseline. The claim exists only in the signed interaction implied ex ante by inverse payoff algebra.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "run_threshold_multiple_m": [
      1.0,
      1.5
    ],
    "trigger_percentile_q": [
      99,
      99.5
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Contract and calendar era are collinear, so any era-specific change in down-vs-up asymmetry loads on the interaction. Examples are a shift in spot-holder composition, leverage caps, insurance-fund and auto-deleveraging rules, and mark-price liquidation design. Binance users with coin-margined positions dilute the linear contrast. BitMEX 5m bar construction may differ from Binance aggregation. Extreme single episodes such as the March 2020 crash fall in the linear era.
```

#### NO_LOOKAHEAD_RULE

```text
Trigger percentiles and the trailing 5m standard deviation are computed from 30-day windows ending at the trigger bar close. Daily RV bins use cut points from each contract's trailing 365 days. RUN_LEN counts only bars strictly after the trigger bar. All thresholds are frozen before outcomes are computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "D2_BITMEX_PRE2020_XBTUSD",
    "LEGAL_RANGE": "pre-2020",
    "OBSERVABLE": "BitMEX XBTUSD 5m closes for trigger jumps, run lengths and daily RV bins on the inverse contract",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Binance BTCUSDT perpetual 1m closes aggregated to 5m for trigger jumps, run lengths and daily RV bins on the linear contract",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low to moderate: two ready datasets, harmonized 5m bars, trailing percentile triggers, a 2x2 regression with RV-bin effects and a day-sign-flip surrogate.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That contract collateral design shapes the path morphology of liquidation cascades, an atomic structural ingredient that coin-margined versus stable-margined comparisons could reuse.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate inverse payoff convexity as a detectable driver of cascade contiguity at 5m resolution. It would also suggest that era differences in cascade shape stem from other causes.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate to high. It is a rare structural identification of a contract-design channel in path morphology using only ready data, and it adds a base mechanism (payoff convexity) that later composite claims can draw on.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
INTERACTION
```

#### COMPONENTS

```json
[
  "Down-move direction of the triggering 5m jump",
  "Inverse-collateral contract structure of BitMEX XBTUSD versus USDT-margined Binance perpetual"
]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `33d1b584c0284c0f6075de15e1bf7f261c48cd9ca8b38c903238550730e94edf`
  - Response id: `resp_068dba36096b6c71006abfb3c6b7e487d1b57ff82b83f836d9`
  - Actual cost USD: 0.089700
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29100,
    "output_tokens": 3150,
    "reasoning_tokens": 2002
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "FUNCTIONAL_RELABEL"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 0,
      "NON_RESCUE": 1,
      "NOVELTY": 0
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `8f7c31b74d95f9b2bf9bd3f67defc1115f9b583a1f87a9ec25eafa3dbd68f0fb`
  - Response id: `null`
  - Actual cost USD: 0.000597
  - Usage:

  ```json
  {
    "completion_tokens": 292,
    "prompt_tokens": 4510,
    "reasoning_tokens": 201
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 2,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": true,
      "POINT_IN_TIME": true,
      "PROVENANCE": true
    },
    "DATA_STATUS": "DATA_READY",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `39808e7efe201d8156619efac9b3000c4043e85200a929026c77713aad5ce600`
  - Response id: `resp_0e73004afbcaf8ae006abfb3f3e9f887d1aa3138d20a81addf`
  - Actual cost USD: 0.016388
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1999,
    "output_tokens": 1239,
    "reasoning_tokens": 1126
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": false,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": false,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 2,
      "NULL_INFORMATION_GAIN": 1,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C004 — ETH residual return in the window after scheduled Ethereum network-upgrade activation

Frozen complexity class: ATOMIC
Frozen mechanism family: D
Frozen information source: OFFICIAL_CALENDAR
Round: generation:0

#### CANDIDATE_ID

```text
C004
```

#### NAME

```text
ETH residual return in the window after scheduled Ethereum network-upgrade activation
```

#### MECHANISM_FAMILY

```text
D
```

#### MECHANISM

```text
Pre-announced hard-fork activation concentrates ETH-specific protocol risk at a known block. When activation passes without failure, holders who had reduced ETH relative to BTC unwind, leaving a positive ETH residual versus BTC after activation.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
A scheduled Ethereum mainnet upgrade concentrates protocol-failure risk at a pre-announced block: consensus splits, client bugs, or stalled finality. That risk is specific to ETH and absent for BTC. Some ETH holders, especially funds with mandates on operational risk, reduce ETH relative to BTC ahead of activation or carry offsetting relative positions. Makers in ETH also widen and lean their inventory. Once activation passes without failure, the risk is resolved and those relative positions are unwound, so ETH should outperform its BTC beta in the hours to days after activation. The calendar is set by core developers through public calls weeks ahead. It is exogenous to short-run ETH price action, which makes it a clean source of relative cross-asset variation.
```

#### INFORMATION_SOURCE

```text
OFFICIAL_CALENDAR
```

#### OBSERVABLE

```text
Activation timestamp A of each scheduled Ethereum mainnet upgrade, defined as the chain timestamp of the fork block or epoch, admitted only when the activation point was publicly announced at least 7 days before A
```

#### FUNCTION

```text
Unconditional event characterization of the ETH idiosyncratic return, after removing BTC with a frozen pre-event beta, over a fixed window after each scheduled Ethereum mainnet upgrade activation. The candidate events to verify are Berlin 2021-04, London 2021-08, Arrow Glacier 2021-12, Gray Glacier 2022-06, Paris 2022-09, Shapella 2023-04 and Dencun 2024-03.
```

#### PRIMARY_TARGET

```text
RESID_H: the sum over 1h bars in (A, A+H] of [ETH log return minus beta_pre x BTC log return], with beta_pre fitted by OLS on 1h returns over (A-60d, A-7d], averaged across events
```

#### HORIZON

```text
H in {24 hours, 168 hours} after each activation timestamp A
```

#### BASELINE_OR_NULL

```text
Placebo times are drawn with the same weekday and UTC hour as each activation and lie at least 30 days away from any listed upgrade, with beta frozen in the same way. The null distribution of the event-mean RESID_H comes from repeatedly drawing as many placebo times as there are events. Under the null of no upgrade effect it reproduces the ETH residual statistic.
```

#### FALSIFIER

```text
The resolution-unwind mechanism is rejected if mean RESID_H across upgrades does not exceed the 95th percentile of the placebo distribution, or if fewer than half of the events show a positive RESID_H. With roughly seven events, a null whose placebo dispersion is wider than the hypothesized effect is reported as uninformative rather than confirmatory of no effect.
```

#### NEAREST_TESTED_MECHANISM

```text
D10
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D10 studied the persistence of endogenous ETH residual shocks with a frozen beta. This card uses an exogenous protocol calendar and a resolution-of-risk channel. GV0R01-C004 studied ETH residual variance share in FOMC windows, a macro event common to both assets, whereas here the event is specific to ETH by construction.
```

#### WHY_NOT_A_RESCUE

```text
No prior ETH residual card is re-cut. The event source is new and exogenous, and the beta freeze and placebo design are fixed before outcomes.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 2,
  "PARAMETERS": {
    "post_activation_hours": [
      24,
      168
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Upgrade-specific narratives such as the supply change at Paris and the staking-withdrawal flows enabled at Shapella. Unrelated ETH news in the windows, including ETF filings. Instability of BTC beta around events. Difficulty-bomb delays carrying little perceived risk, which dilutes the effect. A small event count. Announcement-timing drift if activation blocks were rescheduled.
```

#### NO_LOOKAHEAD_RULE

```text
An event is admitted only if its activation block was publicly announced at least 7 days before A. beta_pre is fitted on (A-60d, A-7d]. RESID_H uses only 1h bars strictly inside (A, A+H]. Placebo times follow the same beta-freeze rule. The event list is frozen before any return is computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_ETH_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "ETHUSDT perpetual 1m closes aggregated to 1h log returns",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 1h log returns",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "ETHEREUM_MAINNET_UPGRADE_ACTIVATION_CALENDAR",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Fork activation block or epoch, its chain timestamp, and the timestamp of the first public announcement of the activation block for each mainnet upgrade",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "first public announcement timestamp of each mainnet upgrade activation block",
  "verified chain timestamp of each upgrade activation block or epoch"
]
```

#### DATA_GAP_CLASS

```text
OFFICIAL_CALENDAR_POINT_IN_TIME_UNVERIFIED
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low once the calendar is verified. Assembling activation timestamps and announcement dates from developer-call notes and client release posts is a manual provenance task.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That official protocol calendars create asset-specific risk premia which resolve at activation, an exogenous base mechanism for relative cross-asset structure.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate scheduled protocol-risk resolution as a visible driver of ETH-versus-BTC relative returns at hourly-to-weekly scale.
```

#### EXPECTED_INFORMATION_GAIN

```text
Low to moderate given the small number of events. It adds an exogenous official-calendar base mechanism for ETH-specific risk, which the cross-asset library lacks.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `881c1e7e6575079a1180475ded9ce3951fbc5f18a31b886806bba6e545d41a1c`
  - Response id: `resp_0cee164a322f93b6006abfb406aed887d18eea5cfd2d79ea42`
  - Actual cost USD: 0.072080
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 28965,
    "output_tokens": 1415,
    "reasoning_tokens": 264
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 3,
      "NON_RESCUE": 3,
      "NOVELTY": 3
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `b4281e35e471fb6dfbffd66300160d179f5f38cafbccf311eee249283c1fdbec`
  - Response id: `null`
  - Actual cost USD: 0.000660
  - Usage:

  ```json
  {
    "completion_tokens": 445,
    "prompt_tokens": 4375,
    "reasoning_tokens": 352
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 2,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "FEASIBILITY_REQUIRED",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `96365a9ab12391ed37a7f53db6e09254bda3ad2dbe77ac325327b0d1701783c2`
  - Response id: `resp_09f78b5b19e3dadb006abfb41e70ec87d1b547b127af938bab`
  - Actual cost USD: 0.021238
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1864,
    "output_tokens": 1751,
    "reasoning_tokens": 1638
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 3,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 1,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C005 — Perpetual-cover spread gap on BTC stress days

Frozen complexity class: CONDITIONAL
Frozen mechanism family: E
Frozen information source: CROSS_SECTIONAL_PANEL
Round: generation:0

#### CANDIDATE_ID

```text
C005
```

#### NAME

```text
Perpetual-cover spread gap on BTC stress days
```

#### MECHANISM_FAMILY

```text
E
```

#### MECHANISM

```text
On BTC stress days, makers in spot names lacking a same-asset Binance perpetual cannot offset inventory and hit risk limits, so they widen effective spreads relative to matched names with perpetual cover.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Market makers quoting a Binance spot altcoin carry inventory risk. If the same base asset has a Binance USD-M perpetual, they can neutralize inventory instantly in the perpetual and keep quoting tight. If there is no perpetual, inventory must be worked off in spot, or covered only through a noisy BTC proxy. On days of large BTC moves, inventory turnover and inventory risk spike. Makers in names without perpetual cover face a binding risk limit and widen quotes or pull size, while makers in names with cover do not. The constraint is the availability of a same-asset derivative for inventory offset. Within the stress regime, the effective spread of names without cover should exceed that of matched names with cover.
```

#### INFORMATION_SOURCE

```text
CROSS_SECTIONAL_PANEL
```

#### OBSERVABLE

```text
PERP_COVER_i(d): equal to 1 if a Binance USD-M perpetual on the same base asset had an effective launch at or before the close of day d and had not been delisted by then, and 0 otherwise
```

#### FUNCTION

```text
Regime fixed in advance: a BTC stress day is a UTC day d whose absolute BTCUSDT spot daily log return is at or above the trailing 365-day p-th percentile evaluated at the close of d. Within this regime only, compare the Abdi-Ranaldo spread proxy over days d+1..d+D between names without a Binance USD-M perpetual and matched names with one.
```

#### PRIMARY_TARGET

```text
SPREAD_GAP: the mean over stress days d of [mean log Abdi-Ranaldo spread over days d+1..d+D for names without perpetual cover minus the same for matched names with cover]
```

#### HORIZON

```text
Days d+1 through d+D after each stress day d, with D in {2, 5}
```

#### BASELINE_OR_NULL

```text
On each regime day, every name without perpetual cover is matched to a name with cover from the same trailing 30-day quote-volume decile, trailing 30-day volatility decile and log-price bucket, and the comparison is made within these cells. The null permutes the PERP_COVER label within those cells on each regime day, which preserves the cross-sectional distribution of the spread proxy and produces the full SPREAD_GAP statistic. The same gap on non-stress days is reported descriptively only, not as part of the claim.
```

#### FALSIFIER

```text
The perpetual-cover inventory channel is rejected in the stress regime if mean SPREAD_GAP over regime days is at or below the 95th percentile of the within-cell label-permutation null, or if it is negative.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C005
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C005 measured an illiquidity gradient over base liquidity rank in stress weeks. This card holds liquidity fixed by matching and isolates a different structural variable, the availability of a same-asset derivative for inventory offset, with a daily spread proxy rather than an illiquidity ratio. GV0R01-C029 studied tick-size changes, which is a different institutional lever.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse the stress-week gradient over liquidity rank. Liquidity is a matching control, and the treatment variable and data source are new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "spread_window_days_D": [
      2,
      5
    ],
    "stress_percentile_p": [
      90,
      95
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Perpetual listing selects names with more attention and speculative demand, which matching on volume may not absorb. Perpetuals on other venues give cover not recorded here. Delisting-risk names cluster among those without cover. Fee promotions and quote-asset migrations shift maker activity. The Abdi-Ranaldo estimator is biased on days with gaps or zero-range bars. Stress days cluster in a few episodes.
```

#### NO_LOOKAHEAD_RULE

```text
PERP_COVER uses only perpetuals whose launch was effective at or before the close of d. The regime percentile uses BTC returns over the 365 days ending at d. Matching deciles use trailing windows ending at d. Universe membership requires a listing at least 60 days before d and does not depend on later survival. Spreads use only bars d+1..d+D.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0",
    "LEGAL_RANGE": "2019-12..2024-12",
    "OBSERVABLE": "Daily open, high, low, close and quote volume per USDT-quoted spot name, including delisted names and pinned listing dates, plus BTCUSDT daily returns for the regime flag",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "BINANCE_UM_PERPETUAL_LISTING_ANNOUNCEMENTS_ARCHIVE",
    "LEGAL_RANGE": "2019-09..2024-12",
    "OBSERVABLE": "Announcement time and effective launch time of each USD-M perpetual per base asset, including later-delisted perpetuals",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "BINANCE_UM_EXCHANGEINFO_ONBOARDDATE_SNAPSHOTS",
    "LEGAL_RANGE": "2019-09..2024-12",
    "OBSERVABLE": "Per-symbol onboardDate and delivery or settlement dates for USD-M perpetual contracts",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "effective launch timestamp of each Binance USD-M perpetual per base asset, including delisted perpetuals",
  "delisting or settlement timestamp of each Binance USD-M perpetual per base asset"
]
```

#### DATA_GAP_CLASS

```text
PERP_LISTING_HISTORY_UNVERIFIED
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Moderate: the panel is ready, but a point-in-time perpetual listing history per base asset must be assembled and reconciled across announcements and exchange metadata.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That maker inventory constraints, relieved by derivative availability, shape stress-time liquidity across the spot cross-section. This is a base mechanism for listing-event designs.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate same-asset derivative cover as a binding determinant of spot liquidity supply under stress at daily resolution.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It identifies derivative availability as a liquidity-supply mechanism in the cross-section, which no prior card isolated.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `74ff40050e6d0e0eca1ece61f3cdb8ce1d1b7a84935c3d1d7b3d9e7d04b93ffa`
  - Response id: `resp_065c54e190f2997a006abfb439e77487d1953a7ad71f8032c0`
  - Actual cost USD: 0.081296
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29008,
    "output_tokens": 2328,
    "reasoning_tokens": 893
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 3
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `ee24f425b61d9751fd8c3953cba6dadaae69b38e2760f2f597a975c7cca55776`
  - Response id: `null`
  - Actual cost USD: 0.000632
  - Usage:

  ```json
  {
    "completion_tokens": 379,
    "prompt_tokens": 4418,
    "reasoning_tokens": 286
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 2,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "FEASIBILITY_REQUIRED",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `1ce09085054091ceab8a03e73d8ca50ee83295394e8fa447ae6e4e361370a33d`
  - Response id: `resp_0467c7ead569fb2d006abfb45a702887d19c31615343c15ff7`
  - Actual cost USD: 0.012324
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1907,
    "output_tokens": 851,
    "reasoning_tokens": 738
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": true,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C006 — Front-end implied-volatility term inversion and entry into a high-RV regime

Frozen complexity class: ATOMIC
Frozen mechanism family: F
Frozen information source: OPTIONS
Round: generation:0

#### CANDIDATE_ID

```text
C006
```

#### NAME

```text
Front-end implied-volatility term inversion and entry into a high-RV regime
```

#### MECHANISM_FAMILY

```text
F
```

#### MECHANISM

```text
Inversion of the front-end implied-volatility term structure reveals concentrated short-dated protection demand absorbed by short-gamma dealers. That demand carries event-timing information and precedes entry into a high realized-volatility regime.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
BTC option dealers on Deribit are typically net short gamma in front-month options sold to directional and protection-seeking clients. When participants who expect a near-term volatility event (an unlock, a court ruling, a leverage build-up) demand short-dated protection, dealers must raise front-end implied volatility relative to longer tenors to ration their short-gamma capacity. An inverted front end therefore reveals concentrated, time-specific protection demand that realized history has not yet shown. If those participants are partly informed, the inversion should precede entry into a high realized-volatility regime. This holds beyond what the IV level relative to RV conveys, because the level mixes a broad risk premium with event timing, while the slope isolates timing.
```

#### INFORMATION_SOURCE

```text
OPTIONS
```

#### OBSERVABLE

```text
TERM_SLOPE(T): ATM implied volatility at the short constant maturity minus ATM implied volatility at the longer constant maturity, interpolated from Deribit BTC option marks with snapshot times at or before T
```

#### FUNCTION

```text
Unconditional regime-transition characterization: test whether the front-end ATM implied-volatility term slope at a daily decision time relates to entry into the top realized-volatility tercile over the next N days, beyond realized-history and IV-level controls.
```

#### PRIMARY_TARGET

```text
ENTRY_N(T): equal to 1 if annualized RV from 5m returns over (T, T+N] lies in the top tercile of the trailing 365-day RV_N distribution evaluated at T, among days whose trailing RV_N at T is not in the top tercile. The contrast is the incremental TERM_SLOPE coefficient beyond the baseline logistic model.
```

#### HORIZON

```text
N in {3, 7} days after each daily decision time T at 00:00 UTC
```

#### BASELINE_OR_NULL

```text
The baseline is a logistic model of ENTRY_N on trailing RV_7d, RV_30d, the DVOL-minus-RV_30d gap and the year. The claim is the increment of TERM_SLOPE beyond that model. The first null permutes TERM_SLOPE in 30-day blocks relative to outcomes. The second is a HAR-RV surrogate path with an implied-volatility proxy built as a fixed smooth function of simulated past RV; it produces the term slope and the entry indicator jointly with no forward-looking information.
```

#### FALSIFIER

```text
The protection-demand timing mechanism is rejected for regime entry if the TERM_SLOPE coefficient beyond the baseline model lies within the central 95 percent of the block-permutation null, or if top-minus-bottom quintile entry frequency is not positive.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C006
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C006 used the IV level relative to trailing RV, which is included here as a baseline control. This card isolates the shape of the IV term structure as a timing signature of dealer-absorbed demand. GV0R01-C014 studied ETH-BTC relative implied variance, not BTC term shape. H01 and B2-01 used realized history only.
```

#### WHY_NOT_A_RESCUE

```text
The prior IV-level observable is a control, not the claim. The new variable has a distinct dealer-inventory rationale, and its horizons and tenors are fixed in advance.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "horizon_days_N": [
      3,
      7
    ],
    "tenor_pair": [
      "7d_minus_30d",
      "14d_minus_60d"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Scheduled events that everyone sees on the calendar, such as FOMC or quarterly expiries, which mechanically invert the front end and raise RV without any informed demand. Expiry-day distortions of short-tenor interpolation. Deribit index and mark methodology changes. Sparse short-dated strikes early in the sample. The eligibility restriction to non-high-RV days, which is fixed at T but changes the sample composition over time.
```

#### NO_LOOKAHEAD_RULE

```text
TERM_SLOPE uses option marks with snapshot timestamps at or before T. Tercile cut points come from the 365 days ending at T. Eligibility is set by trailing RV_N at T. RV_N for the outcome uses only 5m bars in (T, T+N]. DVOL values must carry publication times at or before T.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "DERIBIT_BTC_OPTIONS_MARK_IV_VENDOR_HISTORY",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Per-instrument mark implied volatility, strike, expiry and underlying index price at hourly snapshots, for interpolating 7-day, 14-day, 30-day and 60-day ATM IV",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "DERIBIT_DVOL_INDEX_PUBLIC_API",
    "LEGAL_RANGE": "2021-03..2024-12",
    "OBSERVABLE": "Hourly BTC DVOL index values for the baseline IV-minus-RV gap control",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 5m log returns for trailing RV controls and the RV_N outcome",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_COST
```

#### MISSING_OBSERVABLES

```json
[
  "7-day and 30-day constant-maturity ATM implied volatility for BTC at each daily decision time",
  "snapshot timestamp of each Deribit option mark used in the interpolation"
]
```

#### DATA_GAP_CLASS

```text
PAID_OPTIONS_SURFACE_HISTORY
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High: it needs a paid option-chain history and an interpolation of constant-maturity ATM IV per day; the outcome side is cheap.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That dealer-absorbed short-dated demand encodes when volatility arrives, not only how much is priced, which gives an atomic timing mechanism for regime transitions.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate front-end term shape as carrying regime-timing information beyond the IV level and realized history, and would remove the case for buying chain-level options history for transition work.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate to high. It separates event-timing information in the IV term structure from the IV level already covered, and informs whether paying for options history serves regime work.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `d765a05c592e7d5f9a24bea693a2419d0e7297d98fa4f86cf0f5ec4017364ef1`
  - Response id: `resp_0e7f34ff2be7be02006abfb468921087d193e229246a8d2537`
  - Actual cost USD: 0.074656
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29023,
    "output_tokens": 1661,
    "reasoning_tokens": 513
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 0,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `1bdd9742c405409a8964ff11ec747876a228da7e4ae6d640f892de7f97c3a058`
  - Response id: `null`
  - Actual cost USD: 0.000642
  - Usage:

  ```json
  {
    "completion_tokens": 396,
    "prompt_tokens": 4433,
    "reasoning_tokens": 303
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 1,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "DATA_BLOCKED_COST",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `aba9e4375a526fb29006c4a586fff7297a865bde6f1662f065e74ad4c14c2abe`
  - Response id: `resp_08368789a4c90678006abfb48318c487d1aaccf3dc7f5981de`
  - Actual cost USD: 0.011614
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1922,
    "output_tokens": 777,
    "reasoning_tokens": 664
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C007 — On-chain stablecoin exchange inflow and recovery inside down-shock windows

Frozen complexity class: CONDITIONAL
Frozen mechanism family: G
Frozen information source: ONCHAIN
Round: generation:0

#### CANDIDATE_ID

```text
C007
```

#### NAME

```text
On-chain stablecoin exchange inflow and recovery inside down-shock windows
```

#### MECHANISM_FAMILY

```text
G
```

#### MECHANISM

```text
Within liquidation-driven down shocks, a net on-chain USDT inflow to exchange deposit addresses marks discount-absorbing capital in transit. Because of transfer latency it reaches the book once forced flow is exhausted, enlarging the 6h recovery.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Many participants with spare capital keep stablecoin reserves in self-custody or off-exchange wallets for counterparty-risk reasons. When a sharp liquidation-driven drop opens a discount, those who want to absorb it must first move USDT on-chain to an exchange deposit address. This takes blocks plus exchange confirmation, minutes to tens of minutes. The transfer is visible on-chain before the capital is fully deployed in the order book. A large net inflow in the shock window marks discount-absorbing capital in transit. Shocks met by such inflow should recover more over the next hours than equally sized shocks without it, because that additional resting demand arrives once the forced flow is exhausted. The constraint is the custody-to-exchange transfer latency.
```

#### INFORMATION_SOURCE

```text
ONCHAIN
```

#### OBSERVABLE

```text
INFLOW_Z(T): the net USDT amount (ERC20 plus TRC20) moved into labelled exchange deposit and hot wallets with block timestamps in (T-w, T], excluding Tether treasury and intra-exchange transfers, minus the trailing 30-day same-hour median and divided by the trailing 30-day same-hour MAD
```

#### FUNCTION

```text
Regime fixed in advance: down-shock events, meaning 1h BTCUSDT perpetual bars whose log return is at or below the trailing 365-day s-th percentile of 1h returns, de-clustered by 12 hours. Within this regime only, compare the 6h signed recovery between shocks with high and low net USDT inflow to labelled exchange addresses during the shock window.
```

#### PRIMARY_TARGET

```text
RECOVERY_6H: log(close at T+6h / close at T) for each down shock. The contrast is the top INFLOW_Z tercile minus the bottom tercile within shock-magnitude decile x year strata.
```

#### HORIZON

```text
6 hours after the close T of each down-shock 1h bar
```

#### BASELINE_OR_NULL

```text
Within the down-shock regime, top-tercile INFLOW_Z shocks are compared with bottom-tercile shocks matched on shock-magnitude decile and year. The null permutes INFLOW_Z labels among shocks within year x shock-magnitude strata, which produces the full RECOVERY_6H contrast. A placebo uses inflow measured over the same clock window one day earlier, (T-26h, T-24h], to test whether a generally high inflow level, rather than shock-window inflow, drives the result.
```

#### FALSIFIER

```text
The transit-capital recovery mechanism is rejected within down shocks in any of three cases: the top-minus-bottom tercile RECOVERY_6H contrast is at or below the 95th percentile of the within-strata permutation null; the contrast is negative; or the one-day-earlier placebo inflow produces a contrast of similar size.
```

#### NEAREST_TESTED_MECHANISM

```text
D8
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D8 conditioned recovery on price and volume shock features within klines. This card keeps the shock regime and adds an independent on-chain capital-arrival variable with a latency rationale. GV0R01-C007 and GV0R01-C015 studied issuance or supply events as unconditional triggers, not exchange inflow inside a predefined shock regime.
```

#### WHY_NOT_A_RESCUE

```text
It does not re-threshold D8's shock definition to revive a weak result. The regime is defined independently, and the conditioning variable comes from a different information source with its own causal channel.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "inflow_window_w": [
      "1h",
      "2h"
    ],
    "shock_percentile_s": [
      1,
      0.5
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Reverse timing: inflows may respond to the drop within the same window. Tether treasury mints and transfers to exchanges that are unrelated to investor demand. Internal exchange wallet reshuffles. Label coverage that grows over time and creates level drift. Tron fee changes that shift chain mix. Exchange-specific incidents. Shocks clustered in a few crisis episodes.
```

#### NO_LOOKAHEAD_RULE

```text
INFLOW_Z uses only transfers with block timestamps in (T-w, T] and only address labels first attributed publicly at or before T. Its standardization uses the trailing 30 days ending at T. The shock percentile uses the 365 days ending at T. Tercile cut points are fitted on shocks observed up to T. RECOVERY_6H uses bars strictly in (T, T+6h].
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 1h returns for the regime flag, shock magnitude and RECOVERY_6H",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "ETHEREUM_USDT_ERC20_TRANSFER_LOGS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "USDT Transfer events with block timestamp, sender, recipient and amount on Ethereum",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "TRON_USDT_TRC20_TRANSFER_LOGS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "USDT TRC20 transfer events with block timestamp, sender, recipient and amount on Tron",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "EXCHANGE_DEPOSIT_ADDRESS_LABELS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Address-to-exchange attribution for deposit and hot wallets, with the date each attribution first became public",
    "STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_POINT_IN_TIME_SEMANTICS
```

#### MISSING_OBSERVABLES

```json
[
  "exchange deposit and hot-wallet address labels with first public attribution dates",
  "pinned byte-exact USDT transfer log extracts for Ethereum and Tron"
]
```

#### DATA_GAP_CLASS

```text
POINT_IN_TIME_ADDRESS_LABELS
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High: it requires full USDT transfer extraction on two chains, exchange-address attribution with first-attribution dates, exclusion of Tether treasury and internal exchange transfers, and a matched event design.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That custody-to-exchange latency makes on-chain flows an early view of recovery capital, a base mechanism linking on-chain state to event recovery.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate visible on-chain capital transit as a determinant of shock recovery at hourly resolution. Recovery would then appear driven by venue-internal liquidity alone.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It tests whether on-chain capital movement adds to shock recovery beyond the price and volume conditioning of D8, and clarifies whether exchange-label point-in-time work is worth funding.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `7b4242d93dab63474092e94820954e64f8d95cc35e8f68f22002e005e00371c0`
  - Response id: `resp_0ad371240fbc07ed006abfb49178b487d18ca8987783064bcd`
  - Actual cost USD: 0.080098
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29124,
    "output_tokens": 2185,
    "reasoning_tokens": 1034
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 3
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `0603cee74e85d2d7c6dd0b60921c9b874cb71d836ae2e3feb86af3e427b053cd`
  - Response id: `null`
  - Actual cost USD: 0.000656
  - Usage:

  ```json
  {
    "completion_tokens": 404,
    "prompt_tokens": 4534,
    "reasoning_tokens": 305
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 0,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `009ebb76c921509fd71202c643620c50e376684927bf8529a34294da526d8133`
  - Response id: `resp_0af2d260252c2c90006abfb4af902887d1b8c49c1fb2875197`
  - Actual cost USD: 0.020456
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 2023,
    "output_tokens": 1641,
    "reasoning_tokens": 1528
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": true,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C008 — Depth-spread joint thinness and venue resolution of perp-spot dislocations

Frozen complexity class: INTERACTION
Frozen mechanism family: H
Frozen information source: ORDER_BOOK
Round: generation:0

#### CANDIDATE_ID

```text
C008
```

#### NAME

```text
Depth-spread joint thinness and venue resolution of perp-spot dislocations
```

#### MECHANISM_FAMILY

```text
H
```

#### MECHANISM

```text
A venue that is simultaneously thin in near-touch depth and wide in quoted spread has makers who have withdrawn. Its price absorbs a disproportionate share of cross-venue dislocation closure, beyond the separate depth and spread effects.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
When the Binance perpetual and OKX spot dislocate, cross-venue relative-value desks take liquidity on the venue where execution is cheaper, and makers on the other venue reprice passively toward the leader. Closure is split between the venues according to how cheaply each venue's resting liquidity is moved. Depth near the touch measures how far a given order walks the book. The quoted spread measures how stale and defensive the top of book already is. A venue that is only thin is walked but may refill fast; a venue that is only wide has defensive makers but deep resting size. A venue that is both thin and wide has makers who have already withdrawn and little size to absorb flow. Its price should carry a share of the closure larger than the separate depth and spread effects imply. This is a venue-structure claim about where adjustment happens, not about direction.
```

#### INFORMATION_SOURCE

```text
ORDER_BOOK
```

#### OBSERVABLE

```text
For each 5m event with |Z_D| at least 2: LOG_DEPTH_RATIO(T) is log(perpetual depth within b bps of mid divided by OKX spot depth within b bps of mid), and LOG_SPREAD_RATIO(T) is log(perpetual quoted spread divided by OKX spot quoted spread), each time-averaged over the 5m bar ending at T
```

#### FUNCTION

```text
Interaction characterization of venue structure: at 5m dislocation events, regress the perpetual's share of absolute leg movement on relative depth, relative spread and their product, with dislocation-size, hour and RV controls.
```

#### PRIMARY_TARGET

```text
The coefficient on LOG_DEPTH_RATIO x LOG_SPREAD_RATIO in a regression of PERP_MOVE_SHARE_W. Here PERP_MOVE_SHARE_W equals |perpetual log move over (T, T+W]| divided by the sum of the absolute perpetual and spot log moves over the same window, which is defined for every event with any movement.
```

#### HORIZON

```text
W in {15 minutes, 60 minutes} after each 5m dislocation event close T
```

#### BASELINE_OR_NULL

```text
The main-effect baseline regresses PERP_MOVE_SHARE_W on Relative near-touch depth of the Binance perpetual versus OKX spot, on Relative quoted spread of the Binance perpetual versus OKX spot, on the |Z_D| bucket, on hour-of-day and on the trailing 1h RV bucket. The claim is only the coefficient on the product of the two components, beyond both main effects. The null permutes LOG_SPREAD_RATIO within LOG_DEPTH_RATIO quintile x hour-of-day x month strata. This destroys the joint term while preserving both marginals and their coarse dependence, and it produces the full interaction statistic.
```

#### FALSIFIER

```text
The joint-thinness channel is rejected if the interaction coefficient lies within the central 95 percent of the stratified permutation null. It is also rejected if the coefficient has the sign opposite to the claim, meaning a perpetual that is jointly thin and wide absorbs less of the closure than the main effects imply.
```

#### NEAREST_TESTED_MECHANISM

```text
D9
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D9 attributed closure among closing extremes using prices only. GV0R01-C008 linked daily depth share to next-day price-discovery share. This card works at event level with book state on both venues and makes no claim about either main effect. Its claim is the depth x spread joint term, which neither prior card examined.
```

#### WHY_NOT_A_RESCUE

```text
It does not revisit D9's unclipped share or GV0R01-C008's daily share claims. The target is redefined so that it holds for every event, and the claim lives only in a pre-specified joint term.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 6,
  "PARAMETERS": {
    "depth_band_bps_b": [
      5,
      10,
      25
    ],
    "resolution_window_W": [
      "15m",
      "60m"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Both ratios respond to the same volatility shock that created the dislocation. Hidden and iceberg liquidity are invisible in L2. Spot-perp funding pressure near settlement times. OKX spot activity relative to other spot venues, since OKX may not be the dominant spot leg. Timestamp alignment between vendor book data and kline closes. Event clustering in stress periods.
```

#### NO_LOOKAHEAD_RULE

```text
Depth and spread ratios are averaged over book states with timestamps inside the 5m bar ending at T. Z_D uses trailing 7-day statistics ending at T. RV and hour controls use information at T. Leg moves are measured over (T, T+W] only. Events are frozen before outcomes are computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Binance perpetual and OKX spot BTC aligned 5m closes for Z_D events and leg moves",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "TARDIS_BINANCE_FUTURES_L2_INCREMENTAL",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual L2 book updates for depth within b bps of mid and quoted spread, averaged per 5m bar",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "TARDIS_OKX_SPOT_L2_INCREMENTAL",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "OKX BTC-USDT spot L2 book updates for depth within b bps of mid and quoted spread, averaged per 5m bar",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "BINANCE_UM_BOOKTICKER_PUBLIC_ARCHIVE",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual best bid and ask price and size for a free cross-check of the perpetual spread",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_COST
```

#### MISSING_OBSERVABLES

```json
[
  "near-touch depth within b bps of mid for the Binance BTCUSDT perpetual per 5m bar",
  "near-touch depth within b bps of mid and quoted spread for OKX BTC-USDT spot per 5m bar",
  "coverage start month of the Binance USD-M bookTicker public archive"
]
```

#### DATA_GAP_CLASS

```text
PAID_L2_ORDER_BOOK_HISTORY
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High: paid L2 histories for two venues, book reconstruction, 5m aggregation of depth and spread, and event-level regression with a stratified permutation null.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That maker withdrawal, visible as joint thinness and width, governs the locus of cross-venue adjustment, a reusable component for composite venue-state claims.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate the joint depth-spread state as an incremental determinant of which venue adjusts. Either book dimension alone would then suffice in later venue-structure models.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate to high. It would give the first book-state account of where cross-venue adjustment happens and justify or retire paid L2 acquisition for venue-structure work.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
INTERACTION
```

#### COMPONENTS

```json
[
  "Relative near-touch depth of the Binance perpetual versus OKX spot",
  "Relative quoted spread of the Binance perpetual versus OKX spot"
]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `498e7cb49d01cf5cfa2566a5de0c41eace0a8635001d8fc5ebc94359dfd3637d`
  - Response id: `resp_085a9535706b7374006abfb4c8bbbc87d187563d20636107f2`
  - Actual cost USD: 0.089864
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29212,
    "output_tokens": 3144,
    "reasoning_tokens": 1996
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 1,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `86d38de0cbaa5b3865e4fce60c0b4a279ef082fcb0543018d82f709d78149828`
  - Response id: `null`
  - Actual cost USD: 0.000658
  - Usage:

  ```json
  {
    "completion_tokens": 391,
    "prompt_tokens": 4622,
    "reasoning_tokens": 298
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 0,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "DATA_BLOCKED_COST",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `9c0417b78404e7756bb1d246134be46ffce60f53a9c633ac8e7cf36dd960c2f5`
  - Response id: `resp_0a929e91455dd26e006abfb510ba0c87d1bb0c218f5370a9fe`
  - Actual cost USD: 0.029952
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 2111,
    "output_tokens": 2573,
    "reasoning_tokens": 2460
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": false,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 2,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 1,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C009 — Leveraged-token daily rebalance footprint in the BTC perpetual (Cheng-Madhavan adaptation)

Frozen complexity class: ATOMIC
Frozen mechanism family: I
Frozen information source: KLINES
Round: generation:0

#### CANDIDATE_ID

```text
C009
```

#### NAME

```text
Leveraged-token daily rebalance footprint in the BTC perpetual (Cheng-Madhavan adaptation)
```

#### MECHANISM_FAMILY

```text
I
```

#### MECHANISM

```text
Fixed-leverage token issuers must add exposure in the direction of the day's return at their scheduled daily rebalance, by an amount proportional to L(L-1) x AUM x day return. This produces a rebalance-window return aligned with the day's return.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Cheng and Madhavan documented that leveraged ETFs with fixed daily leverage L must rebalance at each close by adding exposure in the direction of that day's return. The rebalance amount is proportional to L(L-1) x AUM x day return, and it produces end-of-day flows aligned with the day's move. FTX's BTC leveraged tokens (3x bull, 3x bear, and others) followed a documented daily rebalance near 00:02 UTC with the same algebra. Both bull and bear tokens add exposure in the direction of the day's move, because L(L-1) is positive for L = 3 and for L = -3. If their combined AUM was material relative to liquidity in that minute window, a BTC perpetual return aligned with the day's return should appear in the rebalance window. This reproduction tests whether a mechanically documented external flow mechanism leaves a footprint in Binance perpetual klines. It also checks the footprint against the exchange-funding clock, which coincides at 00:00 UTC.
```

#### INFORMATION_SOURCE

```text
KLINES
```

#### OBSERVABLE

```text
DAY_RET(D): the log return of the BTCUSDT perpetual from the 00:00 UTC close of day D to the 23:57 UTC close of day D
```

#### FUNCTION

```text
Diagnostic reproduction of an externally documented flow mechanism, leveraged-ETF style daily rebalancing, on the BTC perpetual at the documented leveraged-token rebalance time. It is measured over the pre-specified sample 2020-01..2022-10, while the issuer operated, with a placebo sample 2022-12..2024-12.
```

#### PRIMARY_TARGET

```text
The OLS slope of WIN_RET(D) on DAY_RET(D) over 2020-01..2022-10, where WIN_RET(D) is the perpetual log return over the L-minute window starting at 23:57 UTC of day D
```

#### HORIZON

```text
A fixed window of L minutes starting at 23:57 UTC, with L in {10, 20}, around the documented 00:02 UTC rebalance on each day
```

#### BASELINE_OR_NULL

```text
Placebo windows of the same length are placed at the other 23 UTC hour boundaries; for each, the window return is regressed on the 24h return ending just before the window. The 00:00 UTC slope must exceed the placebo-hour distribution, and must separately exceed the 08:00 and 16:00 UTC slopes, which share the Binance funding settlement but not the token rebalance. An out-of-mechanism placebo computes the same 00:00 UTC slope over 2022-12..2024-12, when the FTX tokens no longer existed. A day-block bootstrap of 1m returns produces the null distribution of the slope.
```

#### FALSIFIER

```text
The leveraged-token rebalance footprint is rejected as detectable in Binance perpetual klines if the 00:00 UTC slope over 2020-01..2022-10 does not exceed the 95th percentile of the placebo-hour distribution, or does not exceed both funding-hour placebos. It is also rejected if the same slope is equally large over 2022-12..2024-12.
```

#### NEAREST_TESTED_MECHANISM

```text
MARKET-03
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
MARKET-03 reproduced a published directional strategy. This card reproduces a mechanical flow-accounting mechanism with an exact clock time and a natural termination date, which gives built-in placebos. It does not resemble H03 continuation after impulses, because the conditioning is the full UTC-day return at a fixed clock, not an extreme impulse.
```

#### WHY_NOT_A_RESCUE

```text
No prior directional reproduction is re-cut. The mechanism, clock and natural-ending placebo come from external documentation and are fixed before any outcome.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 2,
  "PARAMETERS": {
    "window_length_minutes_L": [
      10,
      20
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Binance funding settlement at 00:00 UTC, controlled by the 08:00 and 16:00 placebos. The UTC daily candle close, used as an anchor by chart-based participants. Index rebalancing by other products at 00:00 UTC. Binance leveraged tokens, which used different rebalance rules. Intraday threshold rebalances on large-move days that pre-empt the daily flow. Unknown token AUM, which limits power.
```

#### NO_LOOKAHEAD_RULE

```text
DAY_RET uses 1m closes from 00:00 UTC up to the window start at 23:57 UTC. The window return uses closes strictly inside the window. Sample windows and the rebalance time are fixed from documentation before returns are computed. Placebo hours use the same construction.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes for DAY_RET, rebalance-window returns and placebo-hour windows",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "FTX_LEVERAGED_TOKEN_REBALANCE_DOCUMENTATION_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2022-11",
    "OBSERVABLE": "Documented daily rebalance timestamp, target leverage and intraday threshold rebalance rule for BTC leveraged tokens, from archived web captures",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "archived documentation of the FTX BTC leveraged-token daily rebalance timestamp and leverage rule"
]
```

#### DATA_GAP_CLASS

```text
EXTERNAL_MECHANISM_SPEC_PROVENANCE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low: the kline computation is trivial, and the main task is verifying archived documentation of the rebalance time and rules.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That mechanically scheduled third-party flows can be identified in perpetual klines by clock time and termination date, which validates the clock-plus-natural-ending design for other flow mechanisms.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate leveraged-token rebalancing as a detectable kline footprint on the Binance perpetual. Flow mechanisms of comparable scale would then need order-level data to be seen.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It is a clean external benchmark with a built-in natural ending, which shows whether mechanically known flows of plausible size are detectable in kline data at all and calibrates later flow-footprint cards.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `8fe55bfd739c6f1edfa2e3eaa16baffd265c03ac97543b5d804a4f93c99371c3`
  - Response id: `resp_0a386db345a0b7c4006abfb538f0a487d1ae29a5462c4ea6a2`
  - Actual cost USD: 0.083070
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29065,
    "output_tokens": 2494,
    "reasoning_tokens": 1346
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 1,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `828506b3c7a43b425fcdc505bcc1e68b5bc644369aea23c21d2fd940ecb35815`
  - Response id: `null`
  - Actual cost USD: 0.000743
  - Usage:

  ```json
  {
    "completion_tokens": 590,
    "prompt_tokens": 4475,
    "reasoning_tokens": 497
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 3,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "FEASIBILITY_REQUIRED",
    "FEASIBILITY": 2,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `a3604d1f97d1ac1007e509145104c75ddf288ba89684da80674fff151f57e5cb`
  - Response id: `resp_083ec2be35be0008006abfb55f152087d19e83d3284fced6d2`
  - Actual cost USD: 0.015398
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1964,
    "output_tokens": 1147,
    "reasoning_tokens": 1034
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": true,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C010 — CME Globex Sunday reopen clock and Binance perpetual versus OKX spot dislocation

Frozen complexity class: CONDITIONAL
Frozen mechanism family: J
Frozen information source: CROSS_VENUE
Round: generation:0

#### CANDIDATE_ID

```text
C010
```

#### NAME

```text
CME Globex Sunday reopen clock and Binance perpetual versus OKX spot dislocation
```

#### MECHANISM_FAMILY

```text
J
```

#### MECHANISM

```text
At the CME Sunday reopen, basis desks reprice the weekend CME gap through spot-linked offsets, so spot venues move first and the absolute Binance perpetual versus OKX spot dislocation rises transiently. The step is anchored to the Chicago clock.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
CME bitcoin futures stop over the weekend and reopen on Globex at 17:00 Chicago time on Sunday, which is 23:00 UTC under US standard time and 22:00 UTC under US daylight time. Basis desks and institutions that reference CME then reprice the accumulated weekend gap between CME and crypto venues. To do so they offset CME exposure with spot-linked positions, because cash-and-carry books hold spot, and this sends concentrated flow to spot venues first. Binance perpetual participants respond with a lag, so the absolute perpetual-spot dislocation should rise transiently right after the reopen. If the reopen is the cause, the step must follow the Chicago clock and move one UTC hour with US DST. A fixed UTC hour or crypto-native Sunday-evening activity would not move.
```

#### INFORMATION_SOURCE

```text
CROSS_VENUE
```

#### OBSERVABLE

```text
ABS_D(t): |log(perpetual close / OKX spot close)| at aligned 5m closes on Sundays, minus its trailing median over a lookback ending at the start of the pre-reopen window
```

#### FUNCTION

```text
Regime fixed in advance: Sunday windows containing the CME Globex weekly reopen of bitcoin futures (17:00 Chicago time), excluding holiday-modified reopens. Within this regime only, measure the change in mean absolute perpetual-spot dislocation from the hour before the reopen to the hour after it. Then test whether the change tracks the Chicago clock across US DST states rather than a fixed UTC hour.
```

#### PRIMARY_TARGET

```text
STEP: the mean ABS_D over (R, R+M] minus the mean ABS_D over (R-M, R], with R the Chicago-anchored reopen time. The anchoring contrast is the STEP at R minus the STEP at the alternative UTC hour, pooled across DST states.
```

#### HORIZON

```text
M minutes on each side of the Sunday CME reopen, with M in {30, 60}
```

#### BASELINE_OR_NULL

```text
Within the Sunday regime, the anchoring contrast compares the STEP at the Chicago-anchored reopen hour with the STEP at the alternative UTC hour, the one that would be the reopen under the other US DST state. Pseudo-reopen steps are computed at every other full-hour boundary from Sunday 12:00 to 23:00 UTC. The null is a block bootstrap of whole-Sunday ABS_D paths across weeks within the same DST state. It preserves intraday shape, destroys any link between a week's DST state and its hour of step, and produces the full contrast statistic.
```

#### FALSIFIER

```text
The CME-reopen clock mechanism is rejected in either of two cases. First, mean STEP at the Chicago-anchored reopen does not exceed the alternative-UTC-hour STEP beyond the 95th percentile of the block-bootstrap null. Second, the Chicago-anchored STEP is not positive and the pseudo-reopen hours show steps of equal size.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C010
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C010 used staggered US-EU DST windows to ask which clock governs the full intraday dislocation profile. GV0CAL-C002 measured DST displacement of the perpetual-spot discovery-share profile. This card isolates one institutional session event, a regulated futures reopen with a sharp step prediction, and uses DST only to separate the Chicago clock from a fixed UTC hour within that event. GV0CAL-C004 studied CME settlement-window activity, not the reopen.
```

#### WHY_NOT_A_RESCUE

```text
It does not re-estimate DST weights for the full profile. The regime is a single pre-specified institutional event, and DST serves only as an identification device fixed in advance.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "demean_lookback": [
      "7d",
      "28d"
    ],
    "half_window_minutes_M": [
      30,
      60
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Sunday-evening Asia-morning activity, which overlaps the reopen hours. Funding settlement at 00:00 UTC Monday, one to two hours later. Weekly candle-close anchoring at Monday 00:00 UTC. Stale OKX spot closes on thin Sunday bars. Weekend-specific shocks that are large relative to the step. The small number of weeks per DST state in 2022-01..2024-12.
```

#### NO_LOOKAHEAD_RULE

```text
ABS_D is de-meaned with a trailing median whose window ends at the start of the pre-reopen window. The reopen time and DST state come from official calendars fixed before each Sunday. The pre-window and post-window use only bars inside their own intervals. The list of excluded holiday weeks is frozen before outcomes are computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Binance perpetual and OKX spot BTC aligned 5m closes for ABS_D on Sundays",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "STATUTORY_DST_CALENDARS",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "US DST transition dates for mapping the Chicago reopen to a UTC hour",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CME_GLOBEX_CRYPTO_SESSION_HOURS_AND_HOLIDAY_ARCHIVE",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Weekly Sunday reopen time of CME bitcoin futures and the dates of holiday-modified reopens",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "verified weekly Sunday reopen time of CME bitcoin futures per week in the sample",
  "dates of holiday-modified CME Globex reopens in the sample"
]
```

#### DATA_GAP_CLASS

```text
OFFICIAL_SESSION_CALENDAR_UNVERIFIED
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low: ready price data and DST calendars, plus verification of the CME session and holiday archive for the sample months.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
That a regulated futures session clock transmits into crypto cross-venue structure through spot-linked offsets, giving a sharply timed participant-clock base mechanism.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate the CME reopen as a participant clock for cross-venue dislocation. It would also suggest that regulated-venue sessions do not anchor crypto-venue price alignment at this resolution.
```

#### EXPECTED_INFORMATION_GAIN

```text
Moderate. It adds a participant clock tied to a regulated venue's session, distinct from the DST and holiday anchors already studied, and needs only ready price data once the calendar is verified.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `8d6de7afa66492698991ee4a5615f7d7c0ef3789c2bf1d8a4908d94b33ad5d57`
  - Response id: `resp_07d28ba544a03bb5006abfb570e3c887d18b2cbf5813db7386`
  - Actual cost USD: 0.088048
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29089,
    "output_tokens": 2987,
    "reasoning_tokens": 1552
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 2
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `36d8e27b0d9e3457efd3f49e685067b6a0cd8d702b65acc0fa809c2c44758b74`
  - Response id: `null`
  - Actual cost USD: 0.000649
  - Usage:

  ```json
  {
    "completion_tokens": 398,
    "prompt_tokens": 4499,
    "reasoning_tokens": 305
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 3,
    "CHECKS": {
      "BLOCKER_RESOLVED": true,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "FEASIBILITY_REQUIRED",
    "FEASIBILITY": 2,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `54684e83d22648eec7047ac5cdcb4ad2fa0d38b2dd3130b2f8e18776236ccb80`
  - Response id: `resp_026336c5c341e839006abfb5982af487d1a9d660521bb1d0d4`
  - Actual cost USD: 0.019056
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 1988,
    "output_tokens": 1508,
    "reasoning_tokens": 1395
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 1,
      "FALSIFIABILITY": 2,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 1,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C021 — Attention-spike names under high market-wide volatility: joint drawdown-tail exposure in the Binance spot USDT panel

Frozen complexity class: INTERACTION
Frozen mechanism family: A
Frozen information source: CROSS_SECTIONAL_PANEL
Round: generation:2

#### CANDIDATE_ID

```text
C021
```

#### NAME

```text
Attention-spike names under high market-wide volatility: joint drawdown-tail exposure in the Binance spot USDT panel
```

#### MECHANISM_FAMILY

```text
A
```

#### MECHANISM

```text
Abstention-relevant tail risk may arise when a name-level turnover attention spike coincides with a market-wide BTC volatility state. Attention-driven marginal holders and inventory-constrained liquidity providers in that name both withdraw when market-wide risk budgets tighten, so the subsequent drawdown tail should be larger than the sum of the two separate effects.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Two actors are involved. First, attention-driven participants (mostly retail and short-horizon momentum traders) arrive in a name during a turnover spike; they hold small, low-conviction, often margin-funded positions with tight stop levels. Second, liquidity providers in small spot names quote against inventory that they offset with BTC or major pairs; when BTC volatility is high their offsetting instrument is itself volatile and their inventory risk becomes correlated across names, so they cut size first in the least liquid books. Each layer alone raises drawdown tails modestly: a new holder base is fragile, and high BTC volatility widens all books. Jointly, the fragile holder base tends to exit into books that makers have already thinned, so the drawdown tail should be super-additive. If the two layers act independently, the joint cell's tail frequency equals the additive prediction.
```

#### INFORMATION_SOURCE

```text
CROSS_SECTIONAL_PANEL
```

#### OBSERVABLE

```text
At Monday 00:00 UTC decision time T, for each eligible name i: ATTN_i = quote volume summed over the 7 daily bars closed at or before T, divided by 7 times the median daily quote volume over the 30 daily bars ending 7 days before T. MKT_VOL = realized volatility of BTCUSDT daily log returns over the 7 daily bars closed at or before T, ranked within its trailing 365-day distribution at T.
```

#### FUNCTION

```text
Interaction characterization for conditional abstention. It estimates whether the cross-sectional frequency of severe subsequent drawdowns is elevated in the joint cell (attention spike AND high market-wide BTC volatility) beyond the additive main effects of each layer, controlling for liquidity, trailing return and trailing own volatility.
```

#### PRIMARY_TARGET

```text
TAIL_DD_i(T) = 1 if the minimum over daily closes in (T, T+H] of log(close / close at T) is at or below log(1 - D), else 0. The continuous MAXDD_i(T) is reported as a secondary readout. A name delisted inside (T, T+H] contributes its final listed close and is flagged.
```

#### HORIZON

```text
H = 7 or 14 calendar days from each Monday 00:00 UTC decision time T; decision times from 2021-01 to 2024-12, restricted to those whose outcome window closes on or before 2024-12-31.
```

#### BASELINE_OR_NULL

```text
Baseline: pooled linear-probability model (risk-difference scale, the scale relevant for abstention) of TAIL_DD with main effects for Name-level turnover attention spike and Market-wide BTC volatility state, plus controls for trailing 30-day quote-volume rank, trailing 28-day return rank, trailing 28-day own-volatility rank and listing-age bucket. A logistic version is reported alongside. The claim is only the increment of the joint term Name-level turnover attention spike x Market-wide BTC volatility state over those two main effects and controls. Null 1: within each week x liquidity-tercile stratum, permute the attention-spike label across names, preserving the number of spike names per stratum and each week's market-volatility state, then re-estimate the joint coefficient (1000 draws). Null 2: permute the market-volatility label across whole weeks within calendar year, keeping each week's cross-section intact. Inference is clustered by week because tail outcomes co-move across names.
```

#### FALSIFIER

```text
The joint risk-difference term (joint-cell tail frequency minus the frequency implied by adding both main effects to the neither-cell frequency) lies inside the central 90% of either permutation null. Alternatively, it has the opposite sign in at least 3 of the 4 calendar years from 2021 to 2024 evaluated separately, or it reverses sign between the top and bottom liquidity terciles.
```

#### NEAREST_TESTED_MECHANISM

```text
D2
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D2 is a time-series abstention rule on BTC's own RV state, evaluated against matched random decisions. Here the outcome is a name-level cross-sectional drawdown tail, and the claim is a joint term between a name-level participation layer and a market-wide layer, with BTC volatility entering only as one main effect. GV0R01-C005 studied the stress-week gradient of execution-cost proxies across illiquidity ranks, not drawdown tails, and it had no attention layer.
```

#### WHY_NOT_A_RESCUE

```text
No prior map signature tested name-level turnover spikes, and this card does not re-parameterize D2's BTC RV filter: BTC volatility is only one of two layers and is absorbed as a main effect. The claim lives only in the joint term, every threshold is frozen in the 16-variant surface, and a null joint term is a reportable outcome.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 16,
  "PARAMETERS": {
    "ATTN_THRESHOLD": [
      3,
      5
    ],
    "DRAWDOWN_D": [
      0.2,
      0.3
    ],
    "H_DAYS": [
      7,
      14
    ],
    "MKT_VOL_CUT": [
      "top_tercile",
      "top_quintile"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Listing age, because young listings show both turnover spikes and deep drawdowns; it is controlled by bucket. Token unlocks and project news drive both turnover and price; these are unobserved. Pump-and-revert dynamics, where the spike coincides with a large trailing gain; this is controlled by trailing return rank. Delisting announcements produce volume spikes before removal; these are flagged and reported separately. Mechanical scaling, because high-volatility names draw down more; this is controlled by own-volatility rank. Clustered crash weeks make outcomes dependent across names; inference is week-clustered.
```

#### NO_LOOKAHEAD_RULE

```text
All features use daily bars closed at or before T. The universe at T contains names with at least 60 listed days and a trailing 30-day quote-volume rank inside the top N, including names delisted later; universe membership never depends on survival over (T, T+H]. The BTC volatility percentile uses only the 365 days ending at T. Delisting flags come from pinned listing records and are used only for outcome bookkeeping, never as features. All thresholds are frozen before any outcome is computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0",
    "LEGAL_RANGE": "2019-12..2024-12",
    "OBSERVABLE": "Daily OHLC and quote volume for all USDT-quoted spot names including delisted symbols, pinned listing and delisting dates, and BTCUSDT daily closes",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to daily closes, used as a cross-check of the market-volatility state",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. Weekly panel construction from pinned daily bars, two binary layers, one pooled regression per variant, and two permutation nulls of 1000 draws each across 16 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that a name-level participation state and a market-wide volatility state combine non-additively in tail risk. That supports a holder-fragility plus maker-withdrawal story, and it means abstention rules in the cross-section should be conditioned jointly rather than layered additively.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate super-additive joint-condition abstention in this panel. Drawdown tails would be additive in name-level attention and market-wide volatility, so separate single-layer filters would capture everything this pair offers.
```

#### EXPECTED_INFORMATION_GAIN

```text
It decides whether name-level abstention filters in this panel need a market-state interaction term or whether single-layer filters are sufficient. It also adds an attention-participation layer to the base-mechanism library, which no prior map signature covers.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
INTERACTION
```

#### COMPONENTS

```json
[
  "Name-level turnover attention spike",
  "Market-wide BTC volatility state"
]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `27c46aee52408cac9a63a16bfb9b797d9b3d1d1172de5086a1a3ec819f936ce3`
  - Response id: `resp_037b735dab33fafd006abfb5b19c3c87d18ff1152abb4eaf96`
  - Actual cost USD: 0.078302
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29431,
    "output_tokens": 1944,
    "reasoning_tokens": 793
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 3
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `a0d97af9634731378523ae7bb3dbb55a2c943cb146fd86649d11d26a12a509ef`
  - Response id: `null`
  - Actual cost USD: 0.000739
  - Usage:

  ```json
  {
    "completion_tokens": 509,
    "prompt_tokens": 4841,
    "reasoning_tokens": 418
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 3,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": true,
      "POINT_IN_TIME": true,
      "PROVENANCE": true
    },
    "DATA_STATUS": "DATA_READY",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `c69060d2b1a8da3379500df28ad530344da4e969f3dbf0db023ddf1e6a7b2aeb`
  - Response id: `resp_0b40d206393738b6006abfb5d0a24487d1a482c2d3ea0722c3`
  - Actual cost USD: 0.021310
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 2330,
    "output_tokens": 1665,
    "reasoning_tokens": 1552
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": false,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": true,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 3,
      "SEARCH_SURFACE_DISCIPLINE": 2
    }
  }
  ```


### C022 — Options-implied synthetic forward deviation and Binance perpetual drift during CME-closed weekends

Frozen complexity class: CONDITIONAL
Frozen mechanism family: B
Frozen information source: OPTIONS
Round: generation:2

#### CANDIDATE_ID

```text
C022
```

#### NAME

```text
Options-implied synthetic forward deviation and Binance perpetual drift during CME-closed weekends
```

#### MECHANISM_FAMILY

```text
B
```

#### MECHANISM

```text
While CME bitcoin futures are closed for the weekend, institutional directional demand that would normally go to CME is partly expressed through Deribit options. The put-call-parity synthetic forward on Deribit then moves before the Binance perpetual, and options market makers offsetting delta, together with cross-venue relative-value traders, pull the perpetual toward the options-implied forward over the following hours.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
When CME bitcoin futures are closed, institutions that normally take or offset directional exposure on CME lose that venue. Some move that demand to Deribit options, which trade continuously. Customer demand for calls over puts, or the reverse, at a strike moves the parity-implied forward before options market makers have fully offset their delta in perpetual markets. Cross-venue relative-value traders then carry the price toward the options-implied level with a lag of minutes to hours. On weekdays the same information is absorbed through CME, so the lag should be shorter there. The regime is fixed by the exchange calendar, not by any outcome.
```

#### INFORMATION_SOURCE

```text
OPTIONS
```

#### OBSERVABLE

```text
SYNTH_DEV(T) = log(F_syn(T) / P_perp(T)) minus its trailing 7-day median at T. F_syn(T) = K + C_usd - P_usd, from the call and put mids at the strike nearest the Deribit index, for the nearest expiry meeting the expiry rule, sampled at the snapshot nearest to and at or before T. BTC-denominated premia are converted to USD with the Deribit index at quote time. P_perp(T) is the Binance BTCUSDT perp 1m close at T.
```

#### FUNCTION

```text
Conditional directional characterization. The regime is fixed in advance as the CME-closed weekend window: from the CME bitcoin futures Friday close (16:00 US Central time) to the Sunday reopen (17:00 US Central time), mapped to UTC with the US DST calendar and excluding CME holiday-extended closures unless they are in the pinned schedule. Within this regime only, the card estimates the mean sign-aligned Binance BTCUSDT perp return after decision hours where the options-implied synthetic forward deviates strongly from the perp price.
```

#### PRIMARY_TARGET

```text
ALIGNED_RET_H = sign(SYNTH_DEV(T)) x log(P_perp(T+H) / P_perp(T)) on the Binance BTCUSDT perpetual, averaged over weekend decision hours where |SYNTH_DEV(T)| is in the top quantile of its trailing 90-day distribution.
```

#### HORIZON

```text
H in {1, 4, 12} hours; the window (T, T+H] must lie inside the same CME-closed weekend window; weekend decision hours from 2020-04 to 2024-12.
```

#### BASELINE_OR_NULL

```text
Null 1: the same ALIGNED_RET statistic at weekday decision hours when CME is open, matched on UTC hour-of-day, trailing 24h RV decile and |SYNTH_DEV| quantile bin; the claim requires the weekend mean to exceed the matched weekday mean. Null 2: a weekend-block bootstrap that resamples whole weekends with random sign assignment to SYNTH_DEV, which generates the same statistic under no directional content and respects within-weekend dependence. Baseline drift: the unconditional mean weekend perp return is subtracted after alignment, so a generic weekend drift cannot pass as forward-led drift.
```

#### FALSIFIER

```text
Any of the following falsifies the card: the weekend mean ALIGNED_RET at H = 4 is at or below zero or inside the central 90% of the weekend-block bootstrap; the weekend mean does not exceed the matched weekday mean; or the weekend sign disagrees with the pooled sign in at least 3 of the 5 calendar years from 2020 to 2024.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C002
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C002 conditions on which leg of a Binance perp versus OKX spot dislocation moved first, using klines only. This card uses a forward implied from a different instrument class (options, via put-call parity) and a regime defined by the calendar of a competing venue being closed. GV0R01-C014 and GV0R01-C006 used implied variance, a non-directional quantity, and GV0R01-C022 studied strike pinning at expiry, not forward-led drift.
```

#### WHY_NOT_A_RESCUE

```text
No prior card used parity-implied forwards or the CME-closed calendar regime. The regime is fixed by an external calendar before outcomes, the search surface is small and frozen, and the weekday comparison is part of the falsifier rather than an exit route.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 12,
  "PARAMETERS": {
    "DEV_QUANTILE": [
      0.8,
      0.9
    ],
    "EXPIRY_RULE": [
      "nearest_ge_2d",
      "nearest_ge_5d"
    ],
    "H_HOURS": [
      1,
      4,
      12
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Stale or wide weekend option quotes make the mid noisy. The parity forward may simply mirror the Deribit futures or perp price, so the deviation would be a Deribit-Binance basis rather than information. The carry and interest-rate level is removed only by demeaning against the trailing median. Errors in converting BTC-denominated premia to USD through the index matter. Perp funding settlements at 00:00, 08:00 and 16:00 UTC fall inside weekend windows. Weekend news shocks hit both venues. Thin weekend liquidity mechanically enlarges both deviations and returns.
```

#### NO_LOOKAHEAD_RULE

```text
Option quotes or trades must carry exchange timestamps at or before T. The expiry series is chosen from the expiry calendar as published at T. Trailing medians and quantiles end at T. CME session boundaries come from the frozen DST calendar and the pinned holiday schedule. The perp price at T is the 1m close at T, and outcomes use only closes after T inside the same weekend window.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "DERIBIT_OPTIONS_QUOTES_VENDOR_HISTORY",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTC option best bid and ask by strike and expiry with exchange timestamps, plus Deribit index price at each quote",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "DERIBIT_OPTIONS_TRADES_PUBLIC_HISTORY",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTC option trade price, strike, expiry, timestamp and index price at trade, as a fallback for parity forwards built from trades",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "STATUTORY_DST_CALENDARS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "US DST transition dates for mapping CME Central-time session hours to UTC",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CME_BITCOIN_FUTURES_TRADING_HOURS_AND_HOLIDAY_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "CME bitcoin futures weekly close and reopen times and holiday session schedules",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_COST
```

#### MISSING_OBSERVABLES

```json
[
  "Deribit BTC option best bid and ask mids by strike and expiry at hourly snapshots",
  "Pinned CME bitcoin futures holiday session schedule",
  "Verification that public Deribit option trade history is complete enough to build a parity forward from trades within 10 minutes of each weekend hour"
]
```

#### DATA_GAP_CLASS

```text
PAID_OPTIONS_QUOTE_HISTORY_AND_CALENDAR_PROVENANCE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High. It needs a paid options quote history, or a validated trade-based parity fallback, a USD conversion of inverse option premia, CME session mapping with DST and holidays, and a weekend-block bootstrap over 12 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that options-implied forwards lead the perpetual when the CME channel is closed. That identifies a calendar-gated price-discovery route and an options-derived directional observable for later conditional and interaction cards.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate weekend migration of directional information into Deribit options as a source of Binance perp drift. Parity-forward deviations would then be noise or carry, not leadership.
```

#### EXPECTED_INFORMATION_GAIN

```text
It would provide the first directional quantity in the library derived from options rather than klines. It tests whether price-discovery leadership migrates across instrument classes when a competing institutional venue is closed by calendar.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `62982d63e0d43c4c28849722d6b55046152f87cd496ef76969d64c62938ee5ff`
  - Response id: `resp_01de808e736ae170006abfb5e8b6c087d1872f7e22772eb5c3`
  - Actual cost USD: 0.096268
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29469,
    "output_tokens": 3733,
    "reasoning_tokens": 2588
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "FUNCTIONAL_RELABEL"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 1,
      "NON_RESCUE": 0,
      "NOVELTY": 1
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "FUNCTIONAL_RELABEL",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `4058f514a4e2bd076fc801596a1ec202e47b185883ee4278febf55aac3fa0852`
  - Response id: `null`
  - Actual cost USD: 0.000651
  - Usage:

  ```json
  {
    "completion_tokens": 325,
    "prompt_tokens": 4879,
    "reasoning_tokens": 232
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 0,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "DATA_BLOCKED_COST",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 2
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `791b8b36d59a7a2bb813509e600b1bd66ab7d3fdb5a7adc99284845c539becf3`
  - Response id: `resp_0f8fa4f48b151bac006abfb61d163887d190ad81c51ec84e68`
  - Actual cost USD: 0.019716
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 2368,
    "output_tokens": 1498,
    "reasoning_tokens": 1385
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": false,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": true,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 2,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 3,
      "NULL_INFORMATION_GAIN": 2,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C023 — Large-holder BTC exchange deposits and downside-dominant subsequent path shape

Frozen complexity class: ATOMIC
Frozen mechanism family: C
Frozen information source: ONCHAIN
Round: generation:2

#### CANDIDATE_ID

```text
C023
```

#### NAME

```text
Large-holder BTC exchange deposits and downside-dominant subsequent path shape
```

#### MECHANISM_FAMILY

```text
C
```

#### MECHANISM

```text
A holder who moves a large BTC output (at least S BTC) into a labeled exchange deposit address is preparing to dispose of it on-venue. Such disposals are worked in slices over hours, which should produce a staircase-down path whose downside excursion dominates its upside excursion, even when the net window return is near zero.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Large holders (funds, miners, early holders) who move BTC onto an exchange are usually preparing to dispose of it there. Because a block of hundreds of BTC would move the book if executed at once, it is typically worked over hours by execution algorithms or OTC-to-exchange desks in slices. Each slice consumes bid depth and makers re-quote lower, which produces a staircase of small down legs with weak rebounds. Counterparties who watch the same chain data may lean against the flow in advance, so the net return over the window can stay near zero while the path shape is still asymmetric. That is why the outcome is path morphology rather than mean return.
```

#### INFORMATION_SOURCE

```text
ONCHAIN
```

#### OBSERVABLE

```text
DEP_EVENT: an on-chain BTC transaction whose outputs to point-in-time-labeled exchange deposit addresses sum to at least S BTC and are funded from a single input cluster, timestamped by its containing block.
```

#### FUNCTION

```text
Atomic path-morphology characterization. It compares the downside-excursion share of the Binance BTCUSDT perp path after large exchange-deposit events with matched non-event windows.
```

#### PRIMARY_TARGET

```text
DOWN_SHARE_H = MAXDOWN / (MAXUP + MAXDOWN). MAXDOWN = -min over 5m closes in (T, T+H] of log(close / close at T), floored at 0, and MAXUP = max of the same quantity, floored at 0, both on the Binance BTCUSDT perp. Windows with MAXUP + MAXDOWN = 0 are kept with DOWN_SHARE = 0.5 to avoid selection on a defined ratio. The statistic is the mean event-minus-matched-control DOWN_SHARE.
```

#### HORIZON

```text
H = 6 or 24 hours from the event decision time T; events from 2020-01 to 2024-12 whose windows close on or before 2024-12-31.
```

#### BASELINE_OR_NULL

```text
Matched controls: for each event, up to 5 non-event 5m decision times in the same calendar month with the same hour-of-week, the same trailing 24h RV decile and the same trailing 6h signed-return tercile, and with no deposit event within plus or minus H. Null: pseudo-events formed by reassigning event timestamps at random within month x hour-of-week strata. These pseudo-events produce DOWN_SHARE from the same price process, and the event-minus-control mean is recomputed 1000 times. Placebo: same-size BTC transfers to addresses not labeled as exchange deposit addresses.
```

#### FALSIFIER

```text
Any of the following falsifies the card: the mean event-minus-control DOWN_SHARE at H = 6 lies inside the central 90% of the pseudo-event null; it is negative in at least 3 of the 5 calendar years from 2020 to 2024 evaluated separately; or the same-size placebo transfers to unlabeled addresses show an equal effect, which would point to a generic large-transaction or block-timing artifact.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C007
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C007 measured mean return and RV after on-chain USDT issuance, a demand-side stablecoin event. This card uses supply-side BTC deposits and an outcome that is path asymmetry rather than mean return or volatility. D3 characterized the unconditional 24h close path, while this card conditions on an on-chain event and contrasts it with matched controls.
```

#### WHY_NOT_A_RESCUE

```text
No prior map card used BTC deposit flows or targeted path asymmetry after on-chain events. The outcome, matching and placebo are fixed in advance, and the surface has only 4 variants.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "H_HOURS": [
      6,
      24
    ],
    "S_BTC": [
      100,
      500
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Internal exchange wallet reshuffles mislabeled as deposits. Deposits made for collateral or margin rather than disposal. Clustering of large transfers in already falling markets, controlled by matching on the trailing signed return. Miner timestamp drift. Label sets built in hindsight from later behavior. Concurrent news driving both transfers and price.
```

#### NO_LOOKAHEAD_RULE

```text
The event time T is the close of the first 5m bar ending at least 60 minutes after the block header timestamp, which absorbs miner timestamp drift and propagation. Only addresses whose first-labeled date is on or before the block date in the frozen label snapshot count. Labels inferred in hindsight from behavior observed after the event are disallowed. Clustering uses only transactions in blocks at or before the event block. Matched controls use only information at or before their own decision times.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "BITCOIN_BLOCKCHAIN_FULL_NODE_EXPORT",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Transactions with inputs, outputs, values, block height and block header timestamp",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "EXCHANGE_DEPOSIT_ADDRESS_LABELS_POINT_IN_TIME",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Exchange deposit address labels with first-labeled date and labeling source",
    "STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 5m closes",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_POINT_IN_TIME_SEMANTICS
```

#### MISSING_OBSERVABLES

```json
[
  "Point-in-time exchange deposit address labels with auditable first-labeled dates",
  "Input-clustering output frozen per block height so clusters use no transactions from blocks after the event block",
  "Verified full-node export completeness for 2020-01..2024-12"
]
```

#### DATA_GAP_CLASS

```text
POINT_IN_TIME_ADDRESS_LABELS
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium to high. It needs a full-node export and input clustering frozen per block height, a label set whose first-labeled dates can be audited, and an event-matched kline study across 4 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that on-chain disposal intent leaves a measurable footprint in intraday path asymmetry even without a net return effect, which separates execution-path information from directional information.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate large exchange deposits as a path-shape state. Either such disposals are absorbed without asymmetric excursions, or the labels do not capture disposal intent.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds an on-chain supply-side base mechanism to the library, distinct from the stablecoin-demand events already mapped. It also tests whether on-chain intent shows up in path shape rather than in net return.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `f475baa5efb3ff6ea6c7c8d2b9ffafd998bd1130dae766285326ff4fc2473a3b`
  - Response id: `resp_03efd28c54208c87006abfb635059087d1a53b512ae2d0b62c`
  - Actual cost USD: 0.083186
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29148,
    "output_tokens": 2489,
    "reasoning_tokens": 1338
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C024",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 3
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: COMPLETE
  - Call key: `cf31d4cdf3751eddc9a22236dac91621aa46e8b28f0bb039878a78a9fd5f8455`
  - Response id: `null`
  - Actual cost USD: 0.000686
  - Usage:

  ```json
  {
    "completion_tokens": 460,
    "prompt_tokens": 4558,
    "reasoning_tokens": 361
  }
  ```

  - Normalized result:

  ```json
  {
    "CHEAPNESS": 1,
    "CHECKS": {
      "BLOCKER_RESOLVED": false,
      "LEGAL_RANGE": true,
      "OBSERVABLE_SUPPORTED": false,
      "POINT_IN_TIME": false,
      "PROVENANCE": false
    },
    "DATA_STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS",
    "FEASIBILITY": 1,
    "JUDGMENTS": {
      "DATA_SPECIFICITY": 3,
      "IMPLEMENTATION_BOUNDEDNESS": 3
    }
  }
  ```

- RED_TEAM: COMPLETE
  - Call key: `c3d2497fae092e7832cc047b2114787e8f5840841d642707497fd88768f89ef3`
  - Response id: `resp_0dd12f055ccc8b53006abfb65666ac87d19d3d270e66f07e41`
  - Actual cost USD: 0.012774
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 2047,
    "output_tokens": 868,
    "reasoning_tokens": 755
  }
  ```

  - Normalized result:

  ```json
  {
    "CHECKS": {
      "BOUNDED_SEARCH": true,
      "CAUSALITY": true,
      "CONFOUNDING_ADDRESSED": true,
      "FALSIFIABLE": true,
      "NO_LOOKAHEAD": false,
      "NO_TRADING_CLAIM": true,
      "RUNG_CONSISTENT": true
    },
    "JUDGMENTS": {
      "CONFOUNDING_AWARENESS": 3,
      "FALSIFIABILITY": 3,
      "NO_LOOKAHEAD_QUALITY": 1,
      "NULL_INFORMATION_GAIN": 3,
      "SEARCH_SURFACE_DISCIPLINE": 3
    }
  }
  ```


### C024 — Relative ETH-versus-BTC book thinness and ETH pass-through beta in high-volatility hours

Frozen complexity class: CONDITIONAL
Frozen mechanism family: D
Frozen information source: ORDER_BOOK
Round: generation:2

#### CANDIDATE_ID

```text
C024
```

#### NAME

```text
Relative ETH-versus-BTC book thinness and ETH pass-through beta in high-volatility hours
```

#### MECHANISM_FAMILY

```text
D
```

#### MECHANISM

```text
Cross-asset market makers and relative-value desks that quote ETH and BTC perps and offset inventory across them transmit BTC shocks into ETH. When ETH near-touch depth is thin relative to BTC, each relative to its own trailing level, a BTC-originated shock meets less resting liquidity in ETH, so ETH's pass-through beta over the following hours should be higher. This inventory constraint binds in the high-volatility regime.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
The actors are market makers and relative-value desks that quote ETH and BTC perps together and offset inventory across the pair. Common shocks usually arrive first through BTC. When ETH resting depth is unusually thin relative to BTC, the same cross-asset rebalancing flow moves ETH further, so ETH's beta rises. Inventory limits bind hardest when BTC volatility is high, because makers then face larger and more frequent cross-asset offsetting needs; that is why the regime is the high-volatility state. In calm regimes depth differences matter less because flows are small relative to resting size.
```

#### INFORMATION_SOURCE

```text
ORDER_BOOK
```

#### OBSERVABLE

```text
REL_THIN(T) = log(DEPTH_BTC(T) / MED30_BTC(T)) - log(DEPTH_ETH(T) / MED30_ETH(T)). DEPTH is the summed bid plus ask notional within plus or minus B of mid in the Binance USD-M bookDepth snapshot at or before T, and MED30 is the trailing 30-day median of the same UTC hour-of-day snapshot. Positive values mean ETH is relatively thinner.
```

#### FUNCTION

```text
Conditional relative-structure characterization. The regime is fixed in advance: hourly decision times T whose trailing 24h BTC realized volatility, from 5m returns closed at or before T, lies in the top part of its trailing 365-day distribution as set by REGIME_CUT. Within this regime only, the card estimates whether relative ETH-versus-BTC book thinness predicts the subsequent realized ETH-on-BTC beta beyond trailing beta.
```

#### PRIMARY_TARGET

```text
Coefficient on REL_THIN(T) in a regression, within the regime, of BETA_H(T) on trailing 7-day 5m beta, trailing ETH-to-BTC RV ratio and REL_THIN(T). BETA_H(T) is the OLS slope of ETHUSDT perp 5m log returns on BTCUSDT perp 5m log returns over (T, T+H].
```

#### HORIZON

```text
H = 1 or 6 hours from hourly decision times inside the high-volatility regime; decision times from 2022-01 to 2024-12, subject to bookDepth coverage verification.
```

#### BASELINE_OR_NULL

```text
Baseline model inside the regime: BETA_H regressed on trailing 7-day 5m ETH-on-BTC beta and the trailing 7-day ratio of ETH to BTC RV. The claim is the coefficient on REL_THIN(T) beyond that baseline. Null: permute REL_THIN across days within the same UTC hour-of-day and regime-membership stratum, moving whole days to preserve autocorrelation, and re-estimate the coefficient (1000 draws). Stale-depth placebo: REL_THIN measured 24 hours before T replaces REL_THIN(T), to separate an instantaneous depth state from a slow-moving pair characteristic.
```

#### FALSIFIER

```text
Any of the following falsifies the card: the REL_THIN coefficient lies inside the central 90% of the day-block permutation null; the stale-depth placebo coefficient is as large as the contemporaneous one; or the coefficient changes sign between the halves of the regime sample split at 2023-07.
```

#### NEAREST_TESTED_MECHANISM

```text
D4
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D4 characterized 90-day rolling correlation ranges and a 1-day lead-lag from klines, and D10 studied ETH residual persistence. This card targets short-horizon beta conditional on an order-book observable that no prior card used for cross-asset structure. GV0R01-C016 used depth thinning for single-asset RV transitions, not cross-asset pass-through.
```

#### WHY_NOT_A_RESCUE

```text
This is not a re-window of D4's correlation study. The observable is a new order-book quantity, the regime is stated before outcomes, the outcome is short-horizon beta rather than correlation level, and the surface of 8 variants is frozen.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "DEPTH_BAND": [
      "0.5pct",
      "1pct"
    ],
    "H_HOURS": [
      1,
      6
    ],
    "REGIME_CUT": [
      "top_tercile",
      "top_quintile"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
ETH-specific news that thins the ETH book and raises ETH volatility at the same time. Changes in Binance bookDepth snapshot methodology. Funding settlement hours. Tick-size and price-level effects on depth in percentage bands. Joint liquidation cascades that thin both books. Mechanical beta noise in 1h windows with few 5m returns, addressed by the 6h variant.
```

#### NO_LOOKAHEAD_RULE

```text
Depth is read from the snapshot with timestamp at or before T. Trailing medians cover the 30 days ending at T. Regime membership uses RV from 5m returns closed at or before T and a 365-day distribution ending at T. The beta outcome uses only 5m returns in (T, T+H]. Regime cuts and depth bands are frozen before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "BINANCE_UM_BOOKDEPTH_PUBLIC_ARCHIVE",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "BTCUSDT and ETHUSDT perpetual bookDepth snapshots with cumulative notional by percentage band from mid and snapshot timestamps",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "TARDIS_BINANCE_FUTURES_L2_INCREMENTAL",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Full L2 incremental book updates for BTCUSDT and ETHUSDT perpetuals to reconstruct near-touch depth",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2021-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 5m returns",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_ETH_BINANCE_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "ETHUSDT perpetual 1m closes aggregated to 5m returns",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "Binance USD-M bookDepth snapshots for BTCUSDT and ETHUSDT with verified start date, snapshot cadence and gap list",
  "Near-touch depth within 0.5 percent and 1 percent of mid at hourly cadence for both perpetuals"
]
```

#### DATA_GAP_CLASS

```text
ORDER_BOOK_DEPTH_HISTORY
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium. The work is verifying bookDepth archive coverage and cadence, aligning depth snapshots to hourly decision times, running rolling beta regressions, and running a day-block permutation over 8 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that cross-asset beta has a liquidity component that varies with relative book state under inventory stress. Relative structure is then partly a market-making artifact rather than only fundamental co-movement.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate relative resting depth as a driver of short-horizon cross-asset beta in stressed regimes. Pass-through would then be governed by factor exposure and trailing beta rather than by liquidity asymmetry.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds an order-book determinant of cross-asset pass-through to the library. This separates liquidity-driven beta variation from the correlation-level structure already mapped under D4 and D10.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: COMPLETE
  - Call key: `806b942bb606a5795bb699091d305cf83848920da965e2e380347c2437968fbd`
  - Response id: `resp_0c1539e4bfe48e9b006abfb664bcc487d1833a736b0f874b07`
  - Actual cost USD: 0.087684
  - Usage:

  ```json
  {
    "cached_tokens": 0,
    "input_tokens": 29287,
    "output_tokens": 2911,
    "reasoning_tokens": 1760
  }
  ```

  - Normalized result:

  ```json
  {
    "BATCH_RELATIONS": [
      {
        "CANDIDATE_ID": "C001",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C002",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C003",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C004",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C005",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C006",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C007",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C008",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C009",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C010",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C021",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C022",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C023",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C025",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C026",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C027",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C028",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C029",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C030",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C031",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C032",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C033",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C034",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C035",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C036",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C037",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C038",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C039",
        "RELATION": "ORTHOGONAL_MECHANISM"
      },
      {
        "CANDIDATE_ID": "C040",
        "RELATION": "ORTHOGONAL_MECHANISM"
      }
    ],
    "JUDGMENTS": {
      "MECHANISM_DISTANCE": 2,
      "NON_RESCUE": 3,
      "NOVELTY": 2
    },
    "PRIOR_RELATIONS": [
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "B2-06"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D1"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D10"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D11"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D12"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D13"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D2"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D3"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.LEAD_LAG_1DAY"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D4.ROLLING_CORRELATION_90D"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D5"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D6"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D7"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D8"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "D9"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C001"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0CAL-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C002"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C003"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C004"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C005"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C006"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C007"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C008"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C010"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C012"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C013"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C014"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C015"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C016"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C017"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C018"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C020"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C021"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C022"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C025"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C026"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C029"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "GV0R01-C030"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "H05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-01"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-02"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-03"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-04"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-05"
      },
      {
        "RELATION": "ORTHOGONAL_MECHANISM",
        "SIGNATURE_ID": "MARKET-06"
      }
    ]
  }
  ```

- FEASIBILITY: UNCERTAIN
  - Call key: `76ddea9fac6cbafa398ad5c821b1fed99e40f25be8af903ef0634811b0450604`
  - Response id: `null`
  - Reserved USD: 0.005302
  - Journal error: TimeoutError
- RED_TEAM: NOT_RUN

### C025 — Inventory-loading one-sided bursts and minute-scale liquidity resilience on the BTC perpetual

Frozen complexity class: ATOMIC
Frozen mechanism family: E
Frozen information source: KLINES
Round: generation:2

#### CANDIDATE_ID

```text
C025
```

#### NAME

```text
Inventory-loading one-sided bursts and minute-scale liquidity resilience on the BTC perpetual
```

#### MECHANISM_FAMILY

```text
E
```

#### MECHANISM

```text
Liquidity providers who absorb a one-sided taker burst end the minute carrying inventory. Until that inventory is offset they quote less size, so impact per unit of volume should stay elevated for tens of minutes. A two-sided burst of equal volume leaves aggregate maker inventory roughly flat and should not depress resilience.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Market makers on the Binance BTC perpetual quote both sides under inventory limits. A taker burst that is overwhelmingly one-sided leaves the makers who filled it with a large net position. Until they offset it on other venues or wait for opposite flow, they quote smaller size and wider spreads, so each unit of subsequent volume moves price more. A burst of the same size that is two-sided nets out across makers and leaves aggregate inventory roughly flat, so resilience should be unaffected. Matching on volume and absolute return isolates the inventory channel from the pure activity channel.
```

#### INFORMATION_SOURCE

```text
KLINES
```

#### OBSERVABLE

```text
BURST(t): a 1m Binance BTCUSDT perp bar whose quote volume is at or above quantile q of the trailing 30-day per-minute quote-volume distribution at t. ONE_SIDE(t) = 2 x |taker-buy quote volume / quote volume - 0.5|. A burst is one-sided if ONE_SIDE is at or above theta and two-sided if ONE_SIDE is at or below 0.3.
```

#### FUNCTION

```text
Atomic liquidity-state characterization. It compares the post-burst execution-impact ratio after one-sided 1m taker bursts with that after volume-matched two-sided bursts.
```

#### PRIMARY_TARGET

```text
IMPACT_RATIO_W = log[(sum of |1m log returns| / sum of 1m quote volume) over (t, t+W]] - log[the same ratio over the 60 minutes ending at the start of bar t]. The statistic is the mean IMPACT_RATIO_W for one-sided bursts minus that for matched two-sided bursts.
```

#### HORIZON

```text
W = 15, 30 or 60 minutes from the close of the burst bar; bursts from 2020-01 to 2024-12.
```

#### BASELINE_OR_NULL

```text
Two-sided bursts (ONE_SIDE at or below 0.3) matched on quote-volume percentile bin, absolute 1m return bin, UTC hour and calendar year. Null 1: permute the one-sided versus two-sided label within each matched stratum (1000 draws). Null 2: compute IMPACT_RATIO at random non-burst minutes with the same pre-window impact decile, to measure mechanical reversion of the ratio. Bursts with another burst inside the outcome window are excluded from both arms.
```

#### FALSIFIER

```text
Any of the following falsifies the card: the one-sided minus two-sided mean IMPACT_RATIO at W = 30 is at or below zero, or lies inside the central 90% of the label-permutation null; the difference is no larger than the reversion measured by Null 2; or the sign disagrees with the pooled sign in at least 3 of the 5 calendar years from 2020 to 2024.
```

#### NEAREST_TESTED_MECHANISM

```text
D7
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D7 measured persistence of an hourly kline-derived high-impact state without separating inventory from activity. B2-05 and H05 used taker flow to describe subsequent returns, not impact. This card works at minute scale and holds volume and absolute return fixed, so the only contrast is taker one-sidedness, the observable proxy for maker inventory loading.
```

#### WHY_NOT_A_RESCUE

```text
This does not re-test D7's hourly persistence. The time scale, the observable (one-sidedness at fixed volume) and the matched two-sided comparison arm are all new, and the surface is frozen at 12 variants.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 12,
  "PARAMETERS": {
    "ONE_SIDE_THETA": [
      0.7,
      0.8
    ],
    "VOLUME_QUANTILE": [
      0.999,
      0.9995
    ],
    "W_MINUTES": [
      15,
      30,
      60
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Forced liquidation cascades: one-sided bursts are often liquidations that cluster in time, raising subsequent absolute returns mechanically. These are partly handled by excluding overlapping bursts. Information arrival, where one-sided bursts carry news and the next minutes are volatile for that reason rather than because of maker inventory. Larger absolute returns in one-sided bursts, handled by matching. Semantics of the Binance kline taker field. Funding settlement minutes.
```

#### NO_LOOKAHEAD_RULE

```text
Burst classification uses the burst bar and the trailing 30-day per-minute distribution ending at that bar. The pre-window impact covers the 60 minutes ending at the start of the burst bar. The outcome uses only minutes after the burst bar closes. Matching strata use only burst-bar and pre-burst information, and all thresholds are frozen in the surface.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m OHLC, quote volume and taker-buy quote volume",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It needs per-minute trailing percentiles, burst classification, stratified matching and permutation over 12 variants on one dataset.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that resilience depends on the direction structure of flow, not only its size. Inventory-constrained market making then becomes a measurable base mechanism for later liquidity-state conditionals.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate maker inventory loading as a driver of minute-scale resilience on this venue. Post-burst impact would then be explained by activity level and absolute move size alone.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a minute-scale maker-inventory resilience mechanism to the library. This separates inventory loading from activity level, which hourly impact persistence (D7) could not.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C026 — Leverage-led fragile calm: joint cross-venue state and low-to-high volatility transitions

Frozen complexity class: COMPOSITE
Frozen mechanism family: F
Frozen information source: CROSS_VENUE
Round: generation:2

#### CANDIDATE_ID

```text
C026
```

#### NAME

```text
Leverage-led fragile calm: joint cross-venue state and low-to-high volatility transitions
```

#### MECHANISM_FAMILY

```text
F
```

#### MECHANISM

```text
Volatility transitions may start from a fragile calm in which leveraged positioning concentrates in the perpetual without spot confirmation. In that state the perp trades at a premium to spot, leads price discovery and draws rising participation, while low realized volatility keeps margin requirements loose. A modest shock then forces concentrated perp liquidations that cross-venue traders spread to spot, producing a regime transition.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Leveraged traders build positions in the perpetual while spot buyers do not confirm, which shows up as a perp premium over OKX spot, perp-led price discovery and rising perp participation. Low realized volatility keeps margin requirements and liquidation distances comfortable, so positions keep growing. The resulting state is fragile because liquidation thresholds are concentrated in one venue. A modest move forces margin calls there, and cross-venue relative-value traders transmit the forced flow to spot. Each component alone is a weak and common condition; the hypothesis is that only their co-occurrence marks fragile leverage.
```

#### INFORMATION_SOURCE

```text
CROSS_VENUE
```

#### OBSERVABLE

```text
Four binary components at hourly decision time T. (1) PREM(T), the mean over the 24h ending at T of log(Binance perp 5m close / OKX spot 5m close), in the top quantile q of its trailing 90-day distribution. (2) Trailing BTC RV over lookback L from Binance perp 5m returns in the bottom tercile of its trailing 365-day distribution. (3) LL(T) = corr(perp r(t-1), spot r(t)) - corr(spot r(t-1), perp r(t)) over 5m returns in the 24h ending at T, positive and in the top tercile of its trailing 90 days. (4) Perp 24h quote volume at or above 1.5 times the median 24h quote volume over the trailing 30 days.
```

#### FUNCTION

```text
Composite regime-transition characterization. It estimates whether the joint state of a perp premium over spot, low realized volatility, perp-led lead-lag and elevated perp participation predicts low-to-high volatility transitions beyond each component taken separately.
```

#### PRIMARY_TARGET

```text
TRANSITION_H(T) = 1 if the trailing-24h BTC realized volatility evaluated at any hourly close in (T, T+H] enters the top tercile of the 365-day distribution frozen at T. Eligibility is limited to decision hours whose RV at T is not already in the top tercile; this selection uses only information at T.
```

#### HORIZON

```text
H = 24 or 72 hours from hourly decision times T; decision times from 2022-04 to 2024-12 whose windows close on or before 2024-12-31.
```

#### BASELINE_OR_NULL

```text
Baseline: logistic hazard of TRANSITION_H on main effects of Perp premium over OKX spot elevated, Low trailing BTC realized volatility, Perp-led cross-venue lead-lag and Elevated perp participation, plus UTC-hour and calendar-quarter controls. The claim is the increment of the four-way joint-state indicator over those main effects; a secondary check also includes all pairwise products. Null: circularly shift the daily series of each component by independent random offsets within the sample (1000 draws). This destroys co-occurrence while preserving each component's marginal frequency and autocorrelation, and the joint-state transition frequency minus its additive prediction is recomputed.
```

#### FALSIFIER

```text
The joint-state increment over main effects lies inside the central 90% of the circular-shift null. Alternatively, the joint state contains fewer than 15 non-overlapping episodes, in which case it is reported as untestable rather than positive, or the increment's sign differs from the pooled sign in at least 2 of the 3 calendar years 2022, 2023 and 2024.
```

#### NEAREST_TESTED_MECHANISM

```text
H01
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
H01 used RV compression alone to describe expansion. B2-06 used OI and funding crowding, which are data-blocked here. MARKET-06 used dislocation magnitude as an additive MAE term. GV0R01-C026 measured cross-venue transmission speed, and GV0R01-C016 used depth thinning. None tested a joint state of premium, lead-lag, participation and compression as a transition precursor, and the claim here lives only in the joint term.
```

#### WHY_NOT_A_RESCUE

```text
This does not recombine H01 to save it. Compression is one main-effect control among four components, the claim is the joint increment, the episode-count rule prevents claims from sparse states, and the 8-variant surface is frozen.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "H_HOURS": [
      24,
      72
    ],
    "PREM_QUANTILE": [
      0.8,
      0.9
    ],
    "RV_LOOKBACK": [
      "24h",
      "72h"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
USDT pricing differences between venues contaminate the premium. OKX spot liquidity varies over time. Funding settlement hours shift premia. Exogenous macro events cause transitions regardless of state. Low RV mechanically predicts expansion through mean reversion, which is why it is a main-effect control. Sparse joint-state occurrences give low power.
```

#### NO_LOOKAHEAD_RULE

```text
All components use 5m or 1m bars closed at or before T, and trailing distributions (90-day and 365-day) end at T. The eligibility exclusion uses only RV state at T. The outcome uses RV evaluated at hourly closes in (T, T+H] against the distribution frozen at T. Thresholds are frozen in the surface before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Aligned 5m closes of the Binance BTCUSDT perpetual and OKX BTC spot",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2021-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes and quote volume for RV and participation state",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low to medium. It needs four hourly component series, a hazard regression with interaction terms, and a circular-shift null over 8 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that regime transitions have a structural precursor visible only in the co-occurrence of cross-venue leverage indicators. That motivates later decomposition into pairwise interactions to locate the active subset.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate the fragile-calm composite as a transition precursor beyond its parts. Transitions would then be explained additively by compression and the separate cross-venue states.
```

#### EXPECTED_INFORMATION_GAIN

```text
It tests whether volatility transitions are better described by a joint cross-venue leverage state than by compression alone. It is also the first composite in the library built only from cross-venue kline observables, without blocked OI or funding data.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
COMPOSITE
```

#### COMPONENTS

```json
[
  "Perp premium over OKX spot elevated",
  "Low trailing BTC realized volatility",
  "Perp-led cross-venue lead-lag",
  "Elevated perp participation"
]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C027 — Inverse-margin liquidation convexity and down-versus-up shock recovery on BitMEX XBTUSD

Frozen complexity class: CONDITIONAL
Frozen mechanism family: G
Frozen information source: PRE2020_SURFACE
Round: generation:2

#### CANDIDATE_ID

```text
C027
```

#### NAME

```text
Inverse-margin liquidation convexity and down-versus-up shock recovery on BitMEX XBTUSD
```

#### MECHANISM_FAMILY

```text
G
```

#### MECHANISM

```text
In the inverse-margined BitMEX contract, collateral is denominated in BTC, so a price fall erodes both position equity and collateral value and makes long liquidations convex. Price rises damp liquidations of the opposite position. Down shocks should therefore carry a larger non-informational forced-flow component, which is later recovered more than in up shocks.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
On BitMEX XBTUSD, leveraged long holders post BTC as collateral. When price falls, their position loses value and the USD value of their collateral falls too, so margin ratios collapse faster than in a linear contract and liquidations cascade convexly. Holders of the opposite position have collateral that gains USD value as price rises, which damps their liquidations. Liquidation flow is forced and carries no information, so the part of a move driven by liquidations tends to be recovered as liquidity providers and value-oriented participants step in. Down shocks therefore contain more forced flow and should be recovered more than up shocks of the same size.
```

#### INFORMATION_SOURCE

```text
PRE2020_SURFACE
```

#### OBSERVABLE

```text
Shock bars are 5m XBTUSD bars whose |log return| is at or above quantile q of the trailing 30-day 5m |return| distribution, with sign s = +1 for up and -1 for down. Shocks within H of a prior shock are excluded.
```

#### FUNCTION

```text
Conditional event-response characterization. The regime is fixed in advance: the inverse-margined BitMEX XBTUSD venue in the full pre-2020 5m sample pinned in the catalog, when BitMEX hosted a dominant share of BTC perpetual positioning. Within that regime, the card compares recovery after extreme down 5m shocks with recovery after extreme up 5m shocks.
```

#### PRIMARY_TARGET

```text
REC_H = -s x log(close at T+H / close at T) / |shock log return|, where T is the shock bar close. The statistic is mean REC_H over down shocks minus mean REC_H over matched up shocks.
```

#### HORIZON

```text
H = 1 or 6 hours from the close of each shock bar, within the pre-2020 BitMEX XBTUSD 5m sample; the Binance diagnostic uses shock bars from 2020-01 to 2024-12.
```

#### BASELINE_OR_NULL

```text
Matched comparison inside the regime: each down shock is matched to up shocks on the same |shock| quantile bin, trailing 24h RV decile, UTC hour and calendar quarter. Null 1: permute shock-sign labels within matched strata and recompute the down-minus-up recovery (1000 draws). Null 2: a stationary block bootstrap of the BitMEX 5m return series, which produces shocks and recoveries with no sign-specific forced-flow mechanism. Diagnostic only, not part of the claim: the same statistic on the linear USDT-margined Binance perp from 2020-01 to 2024-12.
```

#### FALSIFIER

```text
Within the BitMEX regime, the mean down-minus-up REC at H = 6 is at or below zero, or lies inside the central 90% of the sign-permutation null. As a separate test of attribution, the down-minus-up asymmetry on the linear Binance perp is equal to or larger than on BitMEX, which would point to generic downside overshoot rather than inverse-margin convexity.
```

#### NEAREST_TESTED_MECHANISM

```text
D8
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D8 studied unsigned recovery after joint return and volume shocks on Binance, compared with non-high-activity controls. This card contrasts shock sign inside a contract-design regime and attributes any asymmetry to collateral convexity. GV0R01-C003 used the BitMEX era for cascade contiguity, not for sign-specific recovery.
```

#### WHY_NOT_A_RESCUE

```text
This is not a re-cut of D8. The regime is a different venue and contract type, the contrast is shock sign, the Binance comparison is a falsifier of attribution rather than a fallback, and only 4 variants are frozen.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "H_HOURS": [
      1,
      6
    ],
    "SHOCK_QUANTILE": [
      0.99,
      0.995
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
A generic leverage effect and downside momentum that is not tied to inverse margin. Exchange overload episodes that delayed liquidations or quotes. Mark-price versus last-price wicks. Auto-deleveraging and insurance-fund dynamics. Clustering of shocks in time, handled by excluding shocks within H of a prior shock. Different holder composition between eras, which affects the diagnostic.
```

#### NO_LOOKAHEAD_RULE

```text
The shock threshold uses the trailing 30-day 5m |return| distribution ending at the shock bar. Matching strata use only shock-bar and pre-shock information. The recovery outcome uses closes after the shock bar. The regime is defined by venue and sample, both fixed before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "D2_BITMEX_PRE2020_XBTUSD",
    "LEGAL_RANGE": "pre-2020",
    "OBSERVABLE": "BitMEX XBTUSD 5m OHLC closes",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 5m for the linear-margin diagnostic",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It needs shock detection with trailing quantiles, sign-matched recovery statistics and two nulls over 4 variants, plus one diagnostic replication on Binance.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that contract margining design shapes event recovery. That links microstructure outcomes to collateral denomination, which matters wherever coin-margined contracts dominate positioning.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate inverse-margin collateral convexity as a source of sign-asymmetric recovery. Shock recovery would then be sign-symmetric, or its asymmetry would be unrelated to contract design.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a contract-design mechanism (collateral convexity) to the event-response library. The pre-2020 surface provides a regime that the Binance-era data cannot.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C028 — Tax-year-end loss realization without a wash-sale constraint: late-December turnover of calendar-year losers

Frozen complexity class: ATOMIC
Frozen mechanism family: H
Frozen information source: OFFICIAL_CALENDAR
Round: generation:2

#### CANDIDATE_ID

```text
C028
```

#### NAME

```text
Tax-year-end loss realization without a wash-sale constraint: late-December turnover of calendar-year losers
```

#### MECHANISM_FAMILY

```text
H
```

#### MECHANISM

```text
Taxable holders on a calendar tax year realize losses before 31 December. Because the US wash-sale rule did not cover digital assets in tax years from 2020 to 2024, they can re-enter exposure immediately. The mechanism therefore predicts abnormal two-way turnover concentrated in the largest calendar-year losers during late December.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Taxable holders on a calendar tax year, including US individuals and holders in many other jurisdictions, have an incentive to realize capital losses before 31 December. In equities the US wash-sale rule makes holders wait 30 days before re-establishing exposure, which creates net price pressure. For digital assets in tax years from 2020 to 2024 the rule did not apply, so holders could realize a loss and re-enter exposure within minutes. That predicts concentrated two-way turnover in the largest calendar-year losers during late December. The outcome is turnover because round trips without a waiting period should leave volume, not necessarily price, as the footprint.
```

#### INFORMATION_SOURCE

```text
OFFICIAL_CALENDAR
```

#### OBSERVABLE

```text
CY_LOSS_RANK_i = cross-sectional rank of R_i = log(close at day D of December / first daily close of the same calendar year), for names listed throughout that calendar year.
```

#### FUNCTION

```text
Atomic cross-sectional characterization anchored to the official calendar tax-year end. It measures whether the largest calendar-year losers in the Binance spot USDT cross-section show abnormal late-December turnover relative to winners, compared with placebo month-ends.
```

#### PRIMARY_TARGET

```text
LOSER_TURN_GAP(Y) = mean residualized ABN_TURN over the bottom calendar-year-return group minus the mean over the top group in December of year Y, ranked against the 11 placebo-month gaps of year Y. ABN_TURN_i = log(mean daily quote volume over day D+1 to 31 December / mean daily quote volume over the 60 days ending at day D).
```

#### HORIZON

```text
Outcome window from day D+1 to 31 December of each year from 2020 to 2024; formation from the first daily bar of that calendar year to day D of December.
```

#### BASELINE_OR_NULL

```text
Placebo months: the same LOSER_TURN_GAP is computed at day D of each of the 11 non-December months of year Y, with formation over the trailing returns ending at that day and outcome over the rest of that month. The null is that December's gap ranks uniformly among the 12 monthly gaps of each year; pooled over 5 years, a rank-sum test is used. Controls: ABN_TURN is residualized cross-sectionally on trailing 30-day return rank, trailing volatility rank and liquidity rank before forming the gap, so generic loser-turnover patterns are removed.
```

#### FALSIFIER

```text
December's LOSER_TURN_GAP is not among the top 3 of the 12 monthly gaps in at least 3 of the 5 years from 2020 to 2024, or the pooled rank-sum lies inside the central 90% of the uniform-rank null. It is also falsified if the December gap disappears once the formation return is replaced by the trailing 30-day return, which would indicate turnover driven by short-term losses rather than tax-year anchoring.
```

#### NEAREST_TESTED_MECHANISM

```text
D13
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D13 measured weekly cross-sectional return rank structure, and GV0CAL-C005 measured listing-age drift. Neither used an official calendar date or a turnover outcome. GV0R01-C020 used official holidays for session volume shares of BTC alone, not cross-sectional loser turnover.
```

#### WHY_NOT_A_RESCUE

```text
No prior card used a statutory tax calendar. The outcome is turnover rather than return, the identification is a rank against placebo months fixed in advance, and the surface is frozen at 8 variants.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "FORMATION_END_DAY": [
      10,
      15
    ],
    "GROUP_SPLIT": [
      "quintile",
      "tercile"
    ],
    "UNIVERSE_TOP_N": [
      100,
      200
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Holiday-season liquidity changes that affect all names. Exchange-side wash trading inflating volume in small names. Year-end fund window dressing. Token-specific December events such as unlocks or delisting notices. Jurisdictions with non-calendar tax years diluting the effect. Cost basis being unobservable, so calendar-year return only proxies the size of realizable losses.
```

#### NO_LOOKAHEAD_RULE

```text
Formation uses daily closes up to day D. The universe requires listing at the first daily bar of the calendar year and a trailing liquidity rank inside the top N at day D, and it includes names delisted later. Turnover in the outcome window uses only bars after day D. Placebo month-ends follow the same rule. The tax-year end is a statutory date fixed before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0",
    "LEGAL_RANGE": "2019-12..2024-12",
    "OBSERVABLE": "Daily closes and quote volume for all USDT-quoted spot names including delisted symbols, with pinned listing dates",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "US_IRC_1091_WASH_SALE_SCOPE_AND_TAX_YEAR_REFERENCE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Pinned statutory text and IRS guidance on calendar tax-year end and wash-sale scope for digital assets",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "Pinned statutory and IRS guidance text confirming that wash-sale rules excluded digital assets in tax years from 2020 to 2024"
]
```

#### DATA_GAP_CLASS

```text
OFFICIAL_RULE_PROVENANCE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It needs annual and monthly cross-sectional sorts, residualized turnover and a rank test over 12 months x 5 years for 8 variants, plus pinning one statutory reference.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that a statutory calendar date organizes cross-sectional participation in crypto. A turnover footprint without the equity-style waiting period would be consistent with the regulatory asymmetry, which a later card could test on price.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate calendar tax-year loss realization as a visible organizer of cross-sectional turnover in this panel. Either such activity is negligible on Binance spot, or it is spread out rather than concentrated at year-end.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a cross-sectional mechanism anchored to an official calendar in which the identification comes from a statutory date, not from price. It also tests a regulatory asymmetry between crypto and equities.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C029 — Lottery-demand MAX effect in the Binance spot USDT cross-section inside a risk-on regime

Frozen complexity class: CONDITIONAL
Frozen mechanism family: I
Frozen information source: CROSS_SECTIONAL_PANEL
Round: generation:2

#### CANDIDATE_ID

```text
C029
```

#### NAME

```text
Lottery-demand MAX effect in the Binance spot USDT cross-section inside a risk-on regime
```

#### MECHANISM_FAMILY

```text
I
```

#### MECHANISM

```text
This reproduces the externally documented MAX effect: participants with lottery preferences overpay for names whose recent maximum daily return is extreme, and those names then underperform. Here it is tested only inside a risk-on regime, when retail lottery demand in small crypto names is expected to be largest.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
The external benchmark is the MAX effect documented in equities by Bali, Cakici and Whitelaw: investors who prefer lottery-like payoffs overpay for assets that recently delivered extreme single-day gains, and those assets then underperform. In crypto the marginal holders of small names are largely retail participants with strong lottery preferences, and their inflows are largest in risk-on phases when BTC has been rising. The overpricing should therefore be largest, and its correction most measurable, inside the risk-on regime. The regime is fixed by BTC's trailing return at the decision time, which is public at T.
```

#### INFORMATION_SOURCE

```text
CROSS_SECTIONAL_PANEL
```

#### OBSERVABLE

```text
MAX_i(T) = maximum daily log return of name i over the 28 daily bars closed at or before T; the variant is the mean of the top 3 daily returns.
```

#### FUNCTION

```text
Conditional reproduction of an external benchmark. The regime is fixed in advance: Monday 00:00 UTC decision times T at which BTCUSDT's 28-day log return over daily closes at or before T is positive. Within these weeks only, the card estimates the cross-sectional association between a name's maximum recent daily return and its subsequent relative return, controlling for size proxy, trailing return and trailing volatility.
```

#### PRIMARY_TARGET

```text
Mean over risk-on weeks of the weekly Fama-MacBeth slope of relative log return over (T, T+H] on the cross-sectional rank of MAX_i(T), with control ranks included. The relative return is the name's return minus the equal-weight eligible-universe return. The external benchmark predicts a negative sign.
```

#### HORIZON

```text
H = 7 or 28 days from weekly decision times T; decision times from 2020-03 to 2024-12 whose outcome windows close on or before 2024-12-31.
```

#### BASELINE_OR_NULL

```text
Baseline: a weekly Fama-MacBeth regression with control ranks only (trailing 30-day quote volume as a size proxy, trailing 28-day return and trailing 28-day volatility). The MAX coefficient is measured in a model that includes these controls. Null: a weekly sign-flip Monte Carlo on the MAX slopes (as in D13), with non-overlapping holding windows or Newey-West correction for H = 28. Placebo: the rank of MIN, the minimum daily return over the same window, replaces MAX. The unconditional all-weeks slope is reported as a diagnostic and is not the claim.
```

#### FALSIFIER

```text
Any of the following falsifies the card: the mean risk-on MAX slope is at or above zero, or lies inside the central 90% of the sign-flip null; the MAX slope disappears once trailing volatility rank is included, so MAX is only a volatility proxy; the MIN placebo shows a slope of equal size and sign; or the risk-on slope has a sign different from the pooled sign in at least 3 of the 5 calendar years from 2020 to 2024.
```

#### NEAREST_TESTED_MECHANISM

```text
MARKET-03
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
MARKET-03 reproduced an external directional claim on BTC alone. D13 tested a 1-week formation and 1-week holding return rank structure without a lottery observable or a regime. This card applies a specific external behavioral mechanism, with a distinct observable (maximum daily return) and placebo (minimum daily return), conditioned on a regime fixed in advance.
```

#### WHY_NOT_A_RESCUE

```text
This is not a re-cut of D13's return-rank result. The observable comes from an external published mechanism, the regime is stated in advance, a MIN placebo and a volatility collapse test are built in, and the surface is frozen at 8 variants.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "H_DAYS": [
      7,
      28
    ],
    "MAX_DEFINITION": [
      "max1",
      "mean_top3"
    ],
    "UNIVERSE_TOP_N": [
      100,
      200
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
MAX overlaps with idiosyncratic volatility and short-term reversal, handled by control ranks. New listings with extreme first-week returns, handled by a 60-day minimum listing age. Delistings in the holding window, handled with the final listed close. Overlapping 28-day windows, handled by Newey-West correction or a non-overlapping subsample. Risk-on regimes cluster in a few long episodes, which reduces effective sample size.
```

#### NO_LOOKAHEAD_RULE

```text
MAX, the controls and the regime all use daily bars closed at or before T. The universe at T requires at least 60 listed days and a trailing liquidity rank inside the top N, including names delisted later. Relative returns over (T, T+H] use the equal-weight eligible universe fixed at T. The regime threshold is fixed at zero before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0",
    "LEGAL_RANGE": "2019-12..2024-12",
    "OBSERVABLE": "Daily closes and quote volume for all USDT-quoted spot names including delisted symbols, pinned listings, and BTCUSDT daily closes for the regime",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It needs weekly cross-sectional regressions with three controls, sign-flip Monte Carlo and a MIN placebo over 8 variants on one dataset.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that an external behavioral benchmark transfers to the crypto cross-section, conditional on market phase. It also provides a reference effect against which crypto-native cross-sectional mechanisms can be compared.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate the equity MAX effect as a transferable benchmark for this panel in its most favorable regime. That limits the value of lottery-preference mechanisms in crypto cross-sections.
```

#### EXPECTED_INFORMATION_GAIN

```text
It provides a clean regime-conditioned reproduction of a well-known external mechanism. This calibrates whether behavioral cross-sectional benchmarks transfer to crypto and whether they depend on market phase.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C030 — Which clock governs Deribit BTC option activity: fixed-UTC expiry versus European working hours

Frozen complexity class: ATOMIC
Frozen mechanism family: J
Frozen information source: OPTIONS
Round: generation:2

#### CANDIDATE_ID

```text
C030
```

#### NAME

```text
Which clock governs Deribit BTC option activity: fixed-UTC expiry versus European working hours
```

#### MECHANISM_FAMILY

```text
J
```

#### MECHANISM

```text
Deribit options expire at 08:00 UTC year-round, a contractual UTC anchor, while many of its market makers and desks keep European working hours that shift by one UTC hour at EU DST transitions. If participant clocks dominate, the intraday option-activity profile should move with the EU clock; if the expiry clock dominates, it should stay fixed in UTC.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Deribit BTC options expire every day at 08:00 UTC throughout the year, which gives a contractual UTC anchor. A large part of Deribit options activity comes from European-based market makers and institutional desks whose working day is set by local clocks, which shift by one UTC hour at EU DST transitions. If participants' working hours dominate, the morning ramp of option activity moves one UTC hour at each EU transition. If the expiry and associated rolling dominate, the profile stays fixed in UTC. Windows are chosen so that the US clock does not change inside them, which isolates the EU clock.
```

#### INFORMATION_SOURCE

```text
OPTIONS
```

#### OBSERVABLE

```text
Hourly count of Deribit BTC option trades across all strikes and expiries, normalized to a daily share profile over UTC hours and averaged over the 7 days of each window.
```

#### FUNCTION

```text
Atomic participant-clock characterization. It estimates the displacement, in UTC hours, of the Deribit BTC option trade-count intraday profile across EU DST transitions, using windows in which the US clock is unchanged.
```

#### PRIMARY_TARGET

```text
SHIFT_EU = the UTC-hour displacement, on a 0.25-hour grid from -1.5 to 1.5 with interpolated profiles, that best aligns the after-window profile with the before-window profile. It is signed so that +1 means a full move with the European clock and pooled as a mean over transitions.
```

#### HORIZON

```text
One week before and one week after each EU DST transition from 2020-03 to 2024-11, totalling 10 transitions.
```

#### BASELINE_OR_NULL

```text
Pseudo-transition null: the same SHIFT statistic computed at pseudo-Sundays, meaning non-transition Sundays at least 3 weeks from any US or EU DST transition, with identical 1-week before and after windows and the same weekday composition. This null produces the observable from the same activity process with no clock change. Reference comparison, not the claim: the same statistic on the Binance BTCUSDT perp hourly quote-volume profile over identical windows.
```

#### FALSIFIER

```text
Mean SHIFT_EU over the 10 transitions lies inside the central 90% of the pseudo-Sunday null, which indicates anchoring to the UTC expiry clock or a global mix. It is also falsified if SHIFT_EU is not distinguishable from the Binance perp reference shift computed on the same windows, which would mean there is no options-specific participant clock.
```

#### NEAREST_TESTED_MECHANISM

```text
D12
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D12 measured US DST effects on Binance BTC quote-volume timing. GV0CAL-C002 and GV0R01-C010 measured DST effects on cross-venue price-discovery and dislocation profiles. None studied an options venue where a fixed contractual UTC anchor competes with participant clocks, and none isolated the EU clock through windows in which the US clock is unchanged.
```

#### WHY_NOT_A_RESCUE

```text
This does not re-run D12 on another series. The venue and instrument class are new, the competing contractual anchor is explicit, the EU clock is isolated by window design, and the surface is frozen at 8 variants.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "EXCLUDE_EXPIRY_HOUR": [
      "yes",
      "no"
    ],
    "HOUR_RANGE": [
      "00_24",
      "04_12"
    ],
    "PROFILE_METRIC": [
      "xcorr_shift",
      "morning_centroid"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Weekly and monthly expiry Fridays falling unevenly in the windows. Changes in Deribit's participant mix or product listings. Gaps in the public trade history. Asian-session activity that shifts with neither clock and dilutes the displacement. Changes in market-wide volatility between the before and after weeks. Tight autumn spacing between EU and US transitions limits windows to one week.
```

#### NO_LOOKAHEAD_RULE

```text
DST transition dates are statutory and fixed in advance. Pseudo-Sundays are selected by a frozen rule before any profiles are computed. Profiles use only trades inside each window. Hour ranges and metrics are frozen in the surface. No price or return outcome is involved.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "DERIBIT_OPTIONS_TRADES_PUBLIC_HISTORY",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTC option trade timestamps, strike and expiry for hourly trade counts",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "STATUTORY_DST_CALENDARS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "US and EU DST transition dates",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual hourly quote volume for the reference profile",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "DERIBIT_EXPIRY_TIME_POLICY_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Deribit option expiry time policy records",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "Deribit BTC option trade timestamps with completeness verified per day within one week of each EU DST transition",
  "Deribit expiry-time policy record confirming 08:00 UTC across the sample"
]
```

#### DATA_GAP_CLASS

```text
OPTIONS_TRADE_HISTORY_COMPLETENESS
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium. It needs public trade-history retrieval and per-day completeness checks around 10 transitions, profile alignment and a pseudo-Sunday null over 8 variants.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that participant clocks override a fixed contractual anchor on the main crypto options venue. Options-derived intraday observables should then be aligned to European local time rather than to UTC.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It would eliminate European participant working hours as the organizer of Deribit option activity timing. That points to the contractual UTC expiry or a globally mixed clock as the anchor.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds an options-venue participant-clock measurement to the library. It distinguishes contractual from participant anchoring in a venue where the two clocks can be separated, which complements the perp-based DST work.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C031 — Deposit credit-latency footprint of large on-chain BTC inflows to exchange addresses

Frozen complexity class: ATOMIC
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: ONCHAIN
Round: generation:3

#### CANDIDATE_ID

```text
C031
```

#### NAME

```text
Deposit credit-latency footprint of large on-chain BTC inflows to exchange addresses
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Holders who move BTC on-chain to a Binance deposit address in order to dispose of it cannot place spot orders until the exchange credits the deposit at a fixed confirmation depth K. If such inflows are motivated by disposal, aggressor selling pressure should be timed to the credit-eligible block rather than to the first-inclusion block. The reason is that the confirmation rule is a hard constraint on when the coins become usable.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
The exchange confirmation policy is a rule-based delay that splits one event into two moments. The first is when the transfer becomes visible on-chain at the inclusion block, which every observer can see. The second is when the depositor can act, at the credit block. Reactions by observers to the information should load on inclusion. Mechanical disposal by the depositor should load on credit. Block arrival is close to a Poisson process, so the inclusion-to-credit gap varies randomly from event to event. That gives within-event identification: the taker-sell share should step up at the credit time, and the clock position of the credit time is random relative to hour-of-day effects. Disposal on Binance spot reaches the USD-M perpetual through cross-market intermediaries. The perp taker-sell share is therefore used as the measured footprint.
```

#### INFORMATION_SOURCE

```text
ONCHAIN
```

#### OBSERVABLE

```text
Events are single transaction outputs of at least MIN_BTC to an address labelled as a Binance deposit cluster as of the inclusion block. For each event e, I_e is the inclusion-block arrival time. C_e is the arrival time of the block at depth K_e under the confirmation policy in force at I_e. STEP_e is the taker-sell share of BTCUSDT perpetual 1m quote volume in (C_e, C_e+W] minus the same share in (I_e, C_e].
```

#### FUNCTION

```text
Event-time characterization of whether disposal pressure is clocked by the exchange credit rule. Identification comes from the random gap between inclusion and credit.
```

#### PRIMARY_TARGET

```text
Mean STEP_e over events, and the rank of the true confirmation depth K among pseudo depths 1..12 applied to the same events
```

#### HORIZON

```text
Minutes per event: the window (I_e, C_e+W] with W of 15 or 60 minutes
```

#### BASELINE_OR_NULL

```text
Null 1: pseudo-credit depths K' in 1..12, excluding the true K, are applied to the same events and give a distribution of mean STEP. The true K should rank at the top if the credit rule clocks disposal. Null 2: equal-size transfers to unlabelled non-exchange addresses, with the true K applied and matched on UTC hour, weekday and year. Null 3: block arrival times are redrawn from an exponential with the same rate while the kline series is kept. This generates the STEP observable when there is no credit-clock link.
```

#### FALSIFIER

```text
Any one of the following falsifies the claim: (1) mean STEP for exchange inflows does not exceed the non-exchange control; (2) the true K does not rank above the median of the pseudo depths, in the pooled or in the per-year estimates; (3) the step appears equally at inclusion time, which would point to observer reaction rather than depositor disposal.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C007
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C007 studies the BTC response to USDT issuance on Ethereum and Tron, which is a stablecoin-supply event analysed with demand-state matching. This card uses BTC-chain deposits into exchange addresses and identifies the effect from a rule-based confirmation delay. That is a within-event timing contrast, not an event-versus-control return comparison. The outcome is the composition of taker flow, not return or volatility.
```

#### WHY_NOT_A_RESCUE

```text
No prior signature measured exchange-deposit timing or confirmation-clock effects. The card does not reuse a failed observable or a re-tuned threshold from GV0R01-C007. The identifying variation, the random inclusion-to-credit gap, is new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "K_SOURCE": [
      "policy_K",
      "policy_K_plus_1"
    ],
    "MIN_BTC": [
      100,
      500
    ],
    "W_MIN": [
      15,
      60
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Deposits decided because of a price move already underway; internal exchange wallet reshuffles mislabelled as deposits; batching of many small deposits; confirmation-policy changes over time; transmission lag from spot to perp; deposits intended as perp collateral rather than for disposal; noise in miner-set header timestamps.
```

#### NO_LOOKAHEAD_RULE

```text
Address labels must be those valid at the inclusion block. Labels derived from later sweep behaviour of the same address are excluded, or are recomputed from transactions at or before I_e only. Block arrival time is the first-seen time where it exists, and otherwise the maximum of the header timestamp and median-time-past. An event is used only when its credit block is observed at or before the start of the measured post window. Policy K is the documented value in force at I_e. All thresholds are frozen before any outcome is computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "BITCOIN_BLOCKCHAIN_FULL_NODE_BLOCKS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Block height, header timestamp, median-time-past and transaction outputs with values and addresses",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "EXCHANGE_DEPOSIT_ADDRESS_LABELS_BTC",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "As-of-dated label of Binance BTC deposit address clusters",
    "STATUS": "DATA_BLOCKED_PROVENANCE"
  },
  {
    "DATASET": "BINANCE_BTC_DEPOSIT_CONFIRMATION_POLICY_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Required BTC confirmation count for deposit credit by effective date",
    "STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m quote volume and taker-buy quote volume",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_PROVENANCE
```

#### MISSING_OBSERVABLES

```json
[
  "as-of-dated Binance BTC deposit address cluster labels",
  "historical Binance BTC deposit confirmation count by effective date",
  "block first-seen arrival timestamps as distinct from miner-set header timestamps"
]
```

#### DATA_GAP_CLASS

```text
ADDRESS_LABEL_PROVENANCE_AND_EXCHANGE_POLICY_POINT_IN_TIME
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High. It needs full-node block parsing and exchange address-cluster labelling with strict as-of discipline. The kline side is trivial.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that a hard exchange rule, not information, sets the timing of part of BTC disposal flow. It would also show that the perp tape carries a footprint of spot-venue deposits on a clock set by confirmation depth.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates the idea that visible exchange inflows act as a mechanically timed supply shock on the Binance perp tape at minutes resolution. Any relation between inflows and returns would then have to be informational or slower.
```

#### EXPECTED_INFORMATION_GAIN

```text
It separates the mechanical channel from the informational channel in on-chain exchange-flow metrics. These metrics are widely cited but rarely identified. Either outcome constrains how on-chain flow observables should be timed in later cards.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C032 — Weekend hedge-venue closure and maker depth replenishment after taker sweeps

Frozen complexity class: CONDITIONAL
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: ORDER_BOOK
Round: generation:3

#### CANDIDATE_ID

```text
C032
```

#### NAME

```text
Weekend hedge-venue closure and maker depth replenishment after taker sweeps
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Market makers on the Binance USD-M BTCUSDT book absorb a taker sweep into inventory and normally offload part of that risk on CME bitcoin futures or other hedge venues. When CME is closed, the hedge leg is unavailable and inventory limits bind sooner. Makers then re-post depth on the swept side more slowly. So within the closure regime, the half-life of depth replenishment after a sweep should be longer.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Replenishing depth is a supply decision by liquidity providers who face inventory limits. After a maker absorbs a sweep, the cost of re-posting is the cost of carrying unhedged inventory. That cost rises when the cheapest external hedge venue is shut. The weekly CME closure is scheduled and exogenous to crypto order flow, so the regime is fixed in advance. Inside it, the card measures the depth recovery process. In a frictionless maker model that process should not depend on the calendar.
```

#### INFORMATION_SOURCE

```text
ORDER_BOOK
```

#### OBSERVABLE

```text
Swept-side notional depth within DEPTH_BAND_PCT of mid, taken from Binance USD-M bookDepth snapshots before and after each sweep minute. A sweep minute is identified from 1m klines: absolute 1m return beyond SWEEP_SIGMA times trailing-30d sigma, with the taker share on the sweep side above 0.7.
```

#### FUNCTION

```text
Pre-stated regime CME_CLOSED covers Saturday 00:00 UTC to Sunday 21:00 UTC, plus full-day CME holiday closures on weekdays. Inside the regime, estimate the half-life of swept-side depth recovery after taker sweeps. Compare it with sweeps outside the regime, matched on sweep size, UTC hour and trailing RV bucket.
```

#### PRIMARY_TARGET

```text
Log ratio of median HALF_LIFE inside CME_CLOSED to median HALF_LIFE of matched sweeps outside it. HALF_LIFE is the number of minutes until swept-side depth regains RECOVERY_FRACTION of the loss from pre-sweep level to trough. It is right-censored at 120 minutes and the median is estimated by Kaplan-Meier.
```

#### HORIZON

```text
0 to 120 minutes after each sweep minute
```

#### BASELINE_OR_NULL

```text
Baseline: matched out-of-regime sweeps within year x UTC hour x sweep-size x RV strata. Null 1: the CME_CLOSED label is permuted within those strata. Null 2: pseudo-closures of equal length placed Tuesday to Wednesday, which tests whether any 45-hour block produces the same ratio.
```

#### FALSIFIER

```text
Any one of the following falsifies the claim: (1) the in-regime half-life ratio lies inside the permutation null; (2) the effect disappears after normalizing depth by the regime's own baseline depth level; (3) the pseudo-closures produce equal ratios.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C016
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C016 uses depth thinning as a hazard predictor of transitions in the RV regime. This card instead measures how depth recovers after a discrete sweep, which is a maker-supply response, and conditions on a hedge-venue closure regime. The target is a replenishment duration, not volatility.
```

#### WHY_NOT_A_RESCUE

```text
It does not re-test depth thinning as a predictor and does not add a threshold to C016. Neither the observable (post-sweep recovery time) nor the regime (hedge-venue closure) appears in any prior signature.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "DEPTH_BAND_PCT": [
      1,
      2
    ],
    "RECOVERY_FRACTION": [
      0.5
    ],
    "SWEEP_SIGMA": [
      4,
      6
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Lower weekend participation lowers baseline depth whether or not makers can hedge; weekend takers differ in composition; maker rebate or fee-tier changes; snapshot cadence may be coarser than the replenishment speed; the Sunday CME reopening; liquidity patterns specific to holidays.
```

#### NO_LOOKAHEAD_RULE

```text
Sweep minutes are identified from bars closed at or before the sweep-minute close, using trailing-30d sigma. Pre-sweep depth is the last snapshot timestamped at or before the sweep-minute open. The regime label comes from the CME schedule published before each closure. All thresholds are frozen before outcomes are computed.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "BINANCE_UM_BOOKDEPTH_PUBLIC_ARCHIVE",
    "LEGAL_RANGE": "2023-01..2024-12",
    "OBSERVABLE": "BTCUSDT notional depth by percentage band from mid, per snapshot timestamp",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2023-01..2024-12",
    "OBSERVABLE": "1m OHLC, quote volume and taker-buy quote volume for sweep identification",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CME_BITCOIN_FUTURES_TRADING_HOURS_ARCHIVE",
    "LEGAL_RANGE": "2023-01..2024-12",
    "OBSERVABLE": "Scheduled weekly and holiday closure intervals of CME bitcoin futures",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "first available date and snapshot cadence of Binance USD-M bookDepth files",
  "gap map and completeness of bookDepth daily files",
  "CME holiday-closure intervals for weekday closures"
]
```

#### DATA_GAP_CLASS

```text
ORDER_BOOK_ARCHIVE_COVERAGE_UNVERIFIED
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium. Steps: download and gap-audit the bookDepth daily files, align snapshots to 1m klines, and run the survival estimation.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that external hedge availability governs crypto maker supply on a minutes clock. CME closure would then be a structural liquidity regime for later execution-state cards.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates hedge-venue closure as a determinant of Binance depth resilience. Weekend liquidity differences would then be level effects only.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a base mechanism, maker replenishment speed, under an exogenous regime. This is a prerequisite for later composite claims about weekend execution cost.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C033 — Forced-flow deleveraging state and realized-volatility decay speed

Frozen complexity class: COMPOSITE
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: KLINES
Round: generation:3

#### CANDIDATE_ID

```text
C033
```

#### NAME

```text
Forced-flow deleveraging state and realized-volatility decay speed
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Liquidation engines send price-insensitive market orders that are finite in quantity. Once the inventory of margin-deficient positions is exhausted, the forcing stops. A shock produced by forced flow should therefore lose volatility faster than an equal-size shock driven by discretionary information. The forced-flow state is identified only when several independent footprints occur together.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Volatility after a shock reflects how long the forcing persists. Discretionary information arrivals prompt repeated revisions by many participants. Liquidation flow is a finite stock that ends when margin-deficient positions are closed. Each footprint alone is ambiguous. One-sided taker flow also occurs with news. High fill counts per notional also occur with retail bursts. Cross-asset synchrony also comes from macro news. Intrabar overshoot also comes from thin books. The conjunction is the state in which forced, price-insensitive flow is most plausible, and the claim concerns that state alone.
```

#### INFORMATION_SOURCE

```text
KLINES
```

#### OBSERVABLE

```text
At each BTC 15m shock bar T, four binary component flags computed from bars closed at or before T, plus their joint indicator.
```

#### FUNCTION

```text
Characterize how fast realized volatility decays after large BTC 15m shocks when four independent footprints of forced flow co-occur, compared with the decay implied by each footprint separately.
```

#### PRIMARY_TARGET

```text
RV_DECAY is the log of per-minute realized variance from 1m BTCUSDT perp log returns over the post window, divided by per-minute realized variance over (T-1h, T]. The quantity of interest is the coefficient on the joint indicator.
```

#### HORIZON

```text
(T+1h, T+1h+POST_WINDOW_H] with POST_WINDOW_H of 6 or 12 hours
```

#### BASELINE_OR_NULL

```text
Baseline regression of RV_DECAY on separate indicators for each component: One-sided taker burst: 15m taker-buy share of quote volume outside the frozen trailing-90d percentile band; Trade fragmentation: 15m trade count per unit quote volume above the trailing-30d 95th percentile; Cross-asset synchrony: ETH 15m return of the same sign as the BTC shock and beyond 3 trailing-30d ETH sigma; Intrabar overshoot: the 15m extreme in the shock direction exceeds the 15m close by at least 40 percent of the 15m high-low range. Controls are log shock size, pre-shock RV level, hour-of-week and year. The claim is the coefficient on the all-four joint indicator over these main effects. Null: the joint label is permuted within year x shock-size strata, keeping the counts of each component fixed.
```

#### FALSIFIER

```text
The joint coefficient lies inside the permutation null. Alternatively, it has the opposite sign, meaning slower decay, in at least 3 of 5 years.
```

#### NEAREST_TESTED_MECHANISM

```text
D8
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D8 measures signed 6h price recovery after return-plus-volume shocks. This card targets the decay rate of unsigned volatility, not price recovery. Its state uses fill fragmentation, cross-asset synchrony and intrabar overshoot, none of which D8 used. The claim is the increment of the joint state over each component.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse D8's signed recovery target or its P99/P90 thresholds. It does not revisit a failed variant. The outcome dimension (volatility lifetime) and the state components are new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "POST_WINDOW_H": [
      6,
      12
    ],
    "SHOCK_SIGMA": [
      3,
      4
    ],
    "TAKER_BAND": [
      "p1_p99",
      "p2_p98"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Volatility mean-reverts mechanically after any spike, which the baseline handles; events overlap, so clustered events are thinned to the first in each 6h; component thresholds interact with shock size; exchange-wide outages; changes in the tick-size or matching engine that alter trade counts.
```

#### NO_LOOKAHEAD_RULE

```text
T is the close of the 15m shock bar. All percentiles and sigmas are trailing windows ending at or before T. The universe of shocks is BTC 15m bars with absolute return beyond SHOCK_SIGMA times trailing sigma, frozen before outcomes. The post window starts at T+1h so that it does not overlap the defining bars.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m OHLC, quote volume, trade count and taker-buy quote volume",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_ETH_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "ETHUSDT perpetual 1m OHLC",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. The card uses only catalog klines: a 15m aggregation, four component flags and a regression with permutation.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that forced and discretionary shocks have distinguishable volatility lifetimes that are visible in public klines. Shock origin would then be a mechanism variable in its own right.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates the idea that kline footprints can isolate a finite-forcing state distinct from ordinary shocks. Liquidation-type narratives would then require order-book or liquidation-feed data.
```

#### EXPECTED_INFORMATION_GAIN

```text
It tests whether a forced-flow state can be identified from klines alone through its volatility signature. It also gives a reusable state definition for later decompositions, or else removes it.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
COMPOSITE
```

#### COMPONENTS

```json
[
  "One-sided taker burst: 15m taker-buy share of quote volume outside the frozen trailing-90d percentile band",
  "Trade fragmentation: 15m trade count per unit quote volume above the trailing-30d 95th percentile",
  "Cross-asset synchrony: ETH 15m return of the same sign as the BTC shock and beyond 3 trailing-30d ETH sigma",
  "Intrabar overshoot: the 15m extreme in the shock direction exceeds the 15m close by at least 40 percent of the 15m high-low range"
]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C034 — Inventory-asymmetric closure of perp-discount versus perp-premium cross-venue dislocations

Frozen complexity class: ATOMIC
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: CROSS_VENUE
Round: generation:3

#### CANDIDATE_ID

```text
C034
```

#### NAME

```text
Inventory-asymmetric closure of perp-discount versus perp-premium cross-venue dislocations
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
A perp premium over spot is absorbed by cross-venue intermediaries who pay USDT for spot BTC on OKX and hedge with perp exposure. Cash is plentiful, so this side is rarely constrained. A perp discount requires them to deliver spot BTC that they already own or must borrow. That is constrained by inventory and borrow capacity. So discount dislocations should decay more slowly than premium dislocations of equal size.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Closing a dislocation means taking the opposite side on the two venues. When the perp is rich, cash is the binding resource, and cash is abundant. When the perp is cheap, spot inventory or spot borrow on OKX is the binding resource. Borrow capacity is limited and costs a rate. A frictionless model predicts symmetric decay. An inventory-constrained model predicts slower decay of discounts.
```

#### INFORMATION_SOURCE

```text
CROSS_VENUE
```

#### OBSERVABLE

```text
Sign of the demeaned dislocation at the event close T. The dislocation is D = log(Binance perp close) - log(OKX spot close), and the demeaned value is D minus its trailing 7-day median. Discount means negative; premium means positive.
```

#### FUNCTION

```text
Unconditional characterization of whether the speed at which a cross-venue dislocation closes depends on its sign.
```

#### PRIMARY_TARGET

```text
Remaining fraction R_H = demeaned D at T+H divided by demeaned D at T. The quantity of interest is mean R_H for discount events minus mean R_H for premium events, within year x absolute-dislocation bucket x RV bucket strata.
```

#### HORIZON

```text
30, 60 or 120 minutes after each first-crossing event
```

#### BASELINE_OR_NULL

```text
Null 1: discount and premium labels are permuted within year x absolute-dislocation bucket x RV bucket strata. Null 2: a sign-symmetric AR(1) model fitted to the demeaned dislocation series is simulated to produce the same event set and R_H statistic.
```

#### FALSIFIER

```text
Mean R_H for discount events is not above that for premium events within matched strata. Alternatively, the sign of the contrast reverses in 2 of the 3 years.
```

#### NEAREST_TESTED_MECHANISM

```text
D9
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D9 attributes which venue moves to close a dislocation among closing extremes. MARKET-06 relates dislocation magnitude to BTC adverse path. This card asks whether decay speed is asymmetric by sign because of an inventory constraint. The observable is the sign and the target is the remaining fraction.
```

#### WHY_NOT_A_RESCUE

```text
The card is not D9's resolution-share statistic recut by sign. It tests a new hypothesis, inventory asymmetry, with its own target and null, and does not rely on any failed prior result.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 6,
  "PARAMETERS": {
    "HORIZON_MIN": [
      30,
      60,
      120
    ],
    "THRESH_BP": [
      10,
      20
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
The basis level drifts with funding, which removing the trailing median handles; USDT price differences between venues; stale 5m closes on the less active venue; venue outages and withdrawal suspensions; dislocation sign correlated with price direction and therefore with volatility regime.
```

#### NO_LOOKAHEAD_RULE

```text
The trailing 7-day median is computed from closes at or before T. An event is the first 5m close at which the absolute demeaned dislocation crosses THRESH_BP after at least 60 minutes below it. Both the RV bucket and the threshold are fixed from data at or before T and frozen before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Aligned 5m closes of Binance BTCUSDT perpetual and OKX BTC spot",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "1m closes for trailing RV bucket",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It uses aligned catalog closes, an event detector and a stratified permutation.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that the scarcity of spot inventory, not cash, governs cross-venue price convergence. This would locate the binding constraint of cross-venue intermediaries.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates sign-dependent inventory constraints as a material feature of Binance-OKX dislocation dynamics at 5m resolution.
```

#### EXPECTED_INFORMATION_GAIN

```text
It isolates a single inventory-constraint mechanism on catalog data. That makes it a base building block for later cross-venue interaction cards, including the on-chain transfer-cost card.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C035 — Inverse-margin collateral convexity: move sign x contract margin design in follow-on large-move intensity

Frozen complexity class: INTERACTION
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: PRE2020_SURFACE
Round: generation:3

#### CANDIDATE_ID

```text
C035
```

#### NAME

```text
Inverse-margin collateral convexity: move sign x contract margin design in follow-on large-move intensity
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
On an inverse contract, leveraged holders of positive exposure post BTC as margin. A price fall reduces both the position value and the USD value of the collateral, so liquidation prices are reached faster and down cascades are self-reinforcing. On a linear USDT-margined contract the collateral value does not depend on BTC price. The down-minus-up asymmetry in follow-on large moves should therefore be larger on the inverse contract.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Inverse contracts have a payoff in BTC terms that is nonlinear in USD, and margin is held in the same asset as the underlying. On a fall, leveraged holders of positive exposure lose twice: on the position, and on the USD value of their collateral. That pulls liquidation prices closer and makes forced closes self-reinforcing. Holders of negative exposure on a rise see their BTC collateral appreciate, which partly offsets the loss. Linear contracts lack this asymmetry. Era-wide differences such as market depth or participant mix should affect both signs similarly, and the main effect of design absorbs them.
```

#### INFORMATION_SOURCE

```text
PRE2020_SURFACE
```

#### OBSERVABLE

```text
For each initial 5m shock bar: its sign and the contract design of the venue.
```

#### FUNCTION

```text
Test whether the sign asymmetry in follow-on large moves after a 5m shock is larger on an inverse BTC-margined contract than on a linear USDT-margined contract, beyond the main effects of sign and contract design.
```

#### PRIMARY_TARGET

```text
FOLLOW_ON is the count of same-sign 5m returns beyond 2 trailing sigma within the follow window. The quantity of interest is the interaction: mean FOLLOW_ON(down - up) on BitMEX minus the same on Binance, within daily-RV deciles.
```

#### HORIZON

```text
30 or 60 minutes after each initial 5m shock bar
```

#### BASELINE_OR_NULL

```text
Two main effects are controlled. The first is Initial move sign: down versus up for a 5m return beyond SHOCK_SIGMA trailing-30d sigma, which captures the generic leverage effect present on any contract. The second is Contract margin design: BitMEX XBTUSD inverse BTC-margined versus Binance BTCUSDT linear USDT-margined, which captures era and venue level differences. Both are estimated within daily-RV decile strata normalized per era. The claim is the sign x design interaction: (down - up) on inverse minus (down - up) on linear. Null: a stratified bootstrap over days that resamples sign labels within venue x RV-decile strata.
```

#### FALSIFIER

```text
The interaction estimate lies inside the bootstrap null. Alternatively, the down-minus-up asymmetry is at least as large on the linear contract.
```

#### NEAREST_TESTED_MECHANISM

```text
GV0R01-C003
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
GV0R01-C003 compares unsigned contiguity of the top intraday moves across the BitMEX and Binance eras. This card is signed and tests a specific contract-design mechanism, collateral convexity, through a sign x design interaction. Neither era contrast nor sign asymmetry alone counts as the claim.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse C003's contiguity ratio or its era comparison as the claim. The interaction with move sign is a new hypothesis, specified in advance with its own null.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "FOLLOW_SIGMA": [
      2
    ],
    "FOLLOW_WINDOW_MIN": [
      30,
      60
    ],
    "SHOCK_SIGMA": [
      3,
      4
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Contract design is confounded with era (pre-2020 versus 2020-01..2024-12): market maturity, BTC trend regimes, venue market share and liquidation-engine rules all differ; BitMEX auto-deleveraging and insurance-fund behaviour; index composition differences; the BitMEX sample is dominated by a few crash episodes.
```

#### NO_LOOKAHEAD_RULE

```text
Shock sigma is a trailing-30d estimate ending at the shock bar open. The daily-RV decile uses the prior day. Follow-on counting starts at the bar after the shock bar. Thresholds are frozen per era before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "D2_BITMEX_PRE2020_XBTUSD",
    "LEGAL_RANGE": "pre-2020",
    "OBSERVABLE": "XBTUSD 5m OHLC",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m OHLC aggregated to 5m",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_READY
```

#### MISSING_OBSERVABLES

```json
[]
```

#### DATA_GAP_CLASS

```text
NONE
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low. It needs 5m alignment of two catalog datasets, era-normalized sigma, event counting and a bootstrap.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that contract design, specifically the currency of the collateral, shapes cascade asymmetry. Pooling inverse and linear venues in other cards would then be a modelling error.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates the margin currency as a material driver of cascade asymmetry at 5m resolution. Cross-era differences in cascades would then be attributed to other factors.
```

#### EXPECTED_INFORMATION_GAIN

```text
It tests a contract-design mechanism on archived data. The result gives a base layer that tells later cards whether the margin currency of a venue must be modelled.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
INTERACTION
```

#### COMPONENTS

```json
[
  "Initial move sign: down versus up for a 5m return beyond SHOCK_SIGMA trailing-30d sigma",
  "Contract margin design: BitMEX XBTUSD inverse BTC-margined versus Binance BTCUSDT linear USDT-margined"
]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C036 — FOMC communications blackout and US-hours BTC jump intensity

Frozen complexity class: CONDITIONAL
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: OFFICIAL_CALENDAR
Round: generation:3

#### CANDIDATE_ID

```text
C036
```

#### NAME

```text
FOMC communications blackout and US-hours BTC jump intensity
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Fed officials speak mostly during US business hours, and their speeches are unscheduled policy-information arrivals that macro-sensitive participants price into BTC. The official communications blackout before each meeting removes these arrivals. US-hours jump intensity relative to non-US hours should therefore fall inside blackout.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
The blackout is set mechanically by the meeting calendar, which is published far in advance. It removes a class of unscheduled information events during US hours without changing scheduled data releases. If BTC prices respond to policy-communication shocks, the US-hours share of jumps should fall during blackout. Non-US hours serve as a within-day control for crypto-specific shocks.
```

#### INFORMATION_SOURCE

```text
OFFICIAL_CALENDAR
```

#### OBSERVABLE

```text
Daily counts of 5m BTCUSDT perp jumps, defined as absolute 5m return above JUMP_THRESHOLD times local bipower volatility, split into US hours (US_WINDOW in ET mapped to UTC) and non-US hours.
```

#### FUNCTION

```text
Pre-stated regime BLACKOUT runs from the second Saturday before each scheduled FOMC meeting's first day through midnight ET of the day after the meeting ends. It excludes the statement day and the day after. Inside this regime, measure the intensity of BTC perpetual 5m jumps during US business hours relative to non-US hours, against matched non-blackout days.
```

#### PRIMARY_TARGET

```text
Log incidence-rate ratio of US-hours jumps to non-US-hours jumps, estimated by a Poisson model with day fixed effects. The quantity of interest is the ratio on blackout days minus that on matched non-blackout days.
```

#### HORIZON

```text
Intraday: 5m bars within each UTC day, aggregated per day
```

#### BASELINE_OR_NULL

```text
Matched non-blackout days with the same weekday composition and the same year, excluding statement days and the day after each statement. Null: pseudo-blackout windows of identical length, shifted by 2 or 3 weeks away from each true blackout and kept clear of meetings. The rank of the true estimate is read in the pseudo-window distribution. Both the null and the target use the same Poisson count model.
```

#### FALSIFIER

```text
Any one of the following falsifies the claim: (1) the blackout rate ratio is not below the pseudo-window distribution; (2) the speech-count manipulation check shows no reduction in Fed speeches during blackout; (3) the effect is explained by excluding CPI-release days.
```

#### NEAREST_TESTED_MECHANISM

```text
D11
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D11 measures the RV response to the scheduled statement itself, and GV0R01-C012 measures pre-announcement drift. This card instead uses the rule-defined absence of unscheduled Fed communication over multi-day windows. It excludes statement days and targets the intraday location of jumps.
```

#### WHY_NOT_A_RESCUE

```text
It does not re-measure FOMC statement-window RV or pre-statement drift. Its windows and target are disjoint from D11 and C012.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "JUMP_THRESHOLD": [
      3,
      4
    ],
    "US_WINDOW": [
      "09:00-17:00 ET",
      "08:00-16:00 ET"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Pre-FOMC quieting or positioning unrelated to speeches; CPI and other macro releases landing inside blackout windows; the emergency intermeeting actions of March 2020; equity market hours coinciding with US hours; seasonal clustering of meetings.
```

#### NO_LOOKAHEAD_RULE

```text
Blackout windows come from the meeting calendar as published before each window. Jump thresholds use bipower variation over a trailing 1-day window ending at the bar open. US hours are mapped with the DST calendar. Thresholds are frozen before outcomes.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "D11_FOMC_OFFICIAL_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Scheduled FOMC meeting dates and statement release times",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "STATUTORY_DST_CALENDARS",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "US DST transition dates for ET to UTC mapping",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT perpetual 1m closes aggregated to 5m",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "FED_SPEAKER_CALENDAR_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Dated Fed official speeches and interviews with times",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "BLS_CPI_RELEASE_SCHEDULE_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Scheduled CPI release dates and times",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "timestamped archive of Fed official speeches and interviews",
  "scheduled CPI release times for exclusion strata"
]
```

#### DATA_GAP_CLASS

```text
SPEAKER_AND_RELEASE_CALENDAR_VERIFICATION
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Low to medium. Rule-based blackout construction and jump detection use catalog data. Verifying the speaker and CPI calendars requires archival collection.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that unscheduled policy communication is a measurable source of US-hours BTC jump risk, with timing set by an institutional rule.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates unscheduled Fed communication as a measurable source of US-hours BTC jumps.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a base mechanism on how unscheduled policy communication reaches BTC. It uses an institutional rule as a natural experiment, which no prior card has used.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C037 — Disposition-driven capital-gains overhang in Binance spot USDT names

Frozen complexity class: ATOMIC
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: CROSS_SECTIONAL_PANEL
Round: generation:3

#### CANDIDATE_ID

```text
C037
```

#### NAME

```text
Disposition-driven capital-gains overhang in Binance spot USDT names
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Disposition-prone holders, a large share of alt spot holders, realize gains too early and hold losses. Names whose price is far above holders' turnover-weighted cost basis face realization supply that holds the price below its clearing level, followed by a catch-up drift. Names far below cost basis face supply as the price approaches break-even.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Disposition-prone holders' propensity to realize depends on their unrealized gain, not on recent return alone. Their supply depresses prices of names with large gains below the price that would otherwise clear the market. As that supply is absorbed, the gap closes, so CGO should predict relative return beyond momentum. Turnover-weighted reference prices approximate the average cost basis of holders.
```

#### INFORMATION_SOURCE

```text
CROSS_SECTIONAL_PANEL
```

#### OBSERVABLE

```text
CGO_i(T) = log(close_T / RP_i(T)), where RP is a turnover-weighted reference price over 365 days. Turnover is base volume divided by circulating supply, or a volume-share proxy.
```

#### FUNCTION

```text
Cross-sectional rank association between capital-gains overhang and subsequent relative return across Binance spot USDT names, controlling for trailing return and liquidity.
```

#### PRIMARY_TARGET

```text
Weekly mean partial Spearman IC between CGO rank and the rank of relative log return over the holding window
```

#### HORIZON

```text
(T, T+7d] or (T, T+28d] from Monday 00:00 UTC decision times
```

#### BASELINE_OR_NULL

```text
Baseline: a partial IC that controls for trailing 28d and 365d relative return and liquidity rank, so the claim is the increment of CGO over momentum and reversal. Null: CGO ranks are permuted within liquidity-decile strata each week. A two-sided sign-flip test is applied to the weekly ICs.
```

#### FALSIFIER

```text
The partial IC is indistinguishable from zero under the permutation null. Alternatively, it has the opposite sign in at least 3 of 5 years, or it disappears once trailing returns are controlled.
```

#### NEAREST_TESTED_MECHANISM

```text
D13
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D13 tests one-week formation and one-week holding return ranks. CGO is a path-dependent cost-basis measure weighted by turnover, and it is evaluated beyond trailing return. It is a holder-behaviour mechanism, not return autocorrelation.
```

#### WHY_NOT_A_RESCUE

```text
It does not refit D13's horizon. It uses a new observable and a new mechanism.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 8,
  "PARAMETERS": {
    "HOLD_DAYS": [
      7,
      28
    ],
    "TOP_N": [
      100,
      200
    ],
    "TURNOVER_SOURCE": [
      "circulating_supply",
      "volume_share_proxy"
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
CGO is strongly correlated with trailing return; token unlocks inflate supply; volume on other venues is unobserved; wash volume distorts turnover; listing age; delisting risk.
```

#### NO_LOOKAHEAD_RULE

```text
The universe at T is the top-N names by trailing 28d quote volume with at least 365d of history, including names later delisted. RP uses only bars closed at or before T. Supply values must be as known at each date.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Daily close, base volume and quote volume per symbol including delisted symbols and pinned listings",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CIRCULATING_SUPPLY_HISTORY_AGGREGATOR",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Daily circulating supply per token as known on each date",
    "STATUS": "DATA_BLOCKED_POINT_IN_TIME_SEMANTICS"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_POINT_IN_TIME_SEMANTICS
```

#### MISSING_OBSERVABLES

```json
[
  "point-in-time daily circulating supply per token",
  "token unlock schedule revisions"
]
```

#### DATA_GAP_CLASS

```text
POINT_IN_TIME_SUPPLY_HISTORY
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium. The reference-price recursion is simple. The supply-history point-in-time audit is the expensive part.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that holder cost-basis structure organizes relative returns separately from momentum.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates holder cost-basis effects as distinct from momentum in this universe.
```

#### EXPECTED_INFORMATION_GAIN

```text
It tests a holder-behaviour mechanism that is separate from return-only effects in the crypto spot cross-section.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C038 — Option dealers' pricing of scheduled FOMC jump variance and its realization in BTC

Frozen complexity class: CONDITIONAL
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: OPTIONS
Round: generation:3

#### CANDIDATE_ID

```text
C038
```

#### NAME

```text
Option dealers' pricing of scheduled FOMC jump variance and its realization in BTC
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Deribit market makers embed a discrete variance bump for scheduled FOMC jumps in expiries that span the statement. The size of that bump should scale with the realized jump variance in BTC.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Market makers set prices on scheduled event variance much as equity option dealers do around earnings. If BTC option quotes treat FOMC as a jump, the term structure should show a kink at the event. Whether the realized jump matches that kink measures the event variance premium.
```

#### INFORMATION_SOURCE

```text
OPTIONS
```

#### OBSERVABLE

```text
IEV = (s2^2 t2 - s1^2 t1) - base forward variance x (t2 - t1), from ATM implied volatilities of adjacent expiries
```

#### FUNCTION

```text
Pre-stated regime FOMC_STRADDLE: decision time T at 08:00 UTC on the day before a scheduled FOMC statement, with at least one Deribit expiry before the statement and one after it. Inside this regime, extract the implied event variance from adjacent-expiry ATM total variance and relate it to realized post-statement variance.
```

#### PRIMARY_TARGET

```text
Slope of realized event variance (5m squared returns over the post window, minus matched weekday-hour baseline variance) on IEV across events, together with the mean realized-to-implied ratio
```

#### HORIZON

```text
2h or 6h after each scheduled statement
```

#### BASELINE_OR_NULL

```text
Null 1: the same IEV extraction is run at pseudo-event dates (same weekday, non-FOMC weeks) and gives an IEV distribution. Null 2: event pairings of IEV and realized variance are permuted to test the slope.
```

#### FALSIFIER

```text
The IEV at FOMC dates lies inside the pseudo-event distribution. Alternatively, the slope is indistinguishable from the permutation null.
```

#### NEAREST_TESTED_MECHANISM

```text
D11
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
D11 measures realized RV after FOMC without options data. This card measures options-implied event pricing and how it maps to realized jumps.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse D11's realized-only target. The observable is new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "MONEYNESS": [
      "ATM_forward",
      "25d_avg"
    ],
    "POST_WINDOW_H": [
      2,
      6
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Weekend variance in the term structure; illiquid expiries; CPI releases near FOMC; the March 2020 intermeeting actions.
```

#### NO_LOOKAHEAD_RULE

```text
Implied volatilities are snapshots at or before T. The base forward variance comes from an expiry pair that does not straddle the event, observed at T.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "DERIBIT_OPTIONS_HISTORICAL_MARKS_VENDOR",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTC option mark implied volatility by expiry and strike at 08:00 UTC snapshots",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "DERIBIT_EXPIRY_CALENDAR_ARCHIVE",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Listed BTC expiries per date",
    "STATUS": "FEASIBILITY_REQUIRED"
  },
  {
    "DATASET": "D11_FOMC_OFFICIAL_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Scheduled statement times",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "1m closes for 5m realized variance",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_COST
```

#### MISSING_OBSERVABLES

```json
[
  "Deribit BTC option mark implied volatility per expiry at 08:00 UTC snapshots",
  "listed expiry set per decision time"
]
```

#### DATA_GAP_CLASS

```text
VENDOR_OPTIONS_HISTORY_COST
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High. It requires vendor options history, an expiry audit and a term-structure fit.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that the options market prices scheduled macro event risk in BTC, and how well that pricing matches realized jumps.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates the idea that BTC option quotes price scheduled FOMC jumps.
```

#### EXPECTED_INFORMATION_GAIN

```text
It gives the first options-based base mechanism for how scheduled macro risk is priced in BTC.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
CONDITIONAL
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C039 — On-chain transfer cost x dislocation magnitude in cross-venue convergence

Frozen complexity class: INTERACTION
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: ONCHAIN
Round: generation:3

#### CANDIDATE_ID

```text
C039
```

#### NAME

```text
On-chain transfer cost x dislocation magnitude in cross-venue convergence
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Cross-venue intermediaries rebalance depleted inventory by on-chain transfers. When fees and confirmation delays are high, rebalancing slows, so large dislocations decay more slowly than they otherwise would.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Pre-positioned inventory absorbs small dislocations. Large ones deplete that inventory and need on-chain transfers to restore it. Mempool congestion delays those transfers and makes them more costly, so dislocations persist longer only when both conditions hold together.
```

#### INFORMATION_SOURCE

```text
ONCHAIN
```

#### OBSERVABLE

```text
At each event: the large-dislocation flag and the fee percentile
```

#### FUNCTION

```text
Test whether on-chain transfer cost slows the closure of large cross-venue dislocations, beyond the main effect of each layer.
```

#### PRIMARY_TARGET

```text
Remaining fraction of the demeaned dislocation at T+60m. The quantity of interest is the coefficient on the large-dislocation x high-fee term.
```

#### HORIZON

```text
60 minutes after each dislocation event
```

#### BASELINE_OR_NULL

```text
The baseline controls both main effects: Cross-venue dislocation magnitude: absolute Binance perp minus OKX spot log price minus trailing 7d median; On-chain BTC transfer cost: block median fee rate as a trailing 30d percentile. It also includes an RV x dislocation-magnitude control. The claim is the joint term. Null: the fee series is block-permuted in 30-day blocks.
```

#### FALSIFIER

```text
The joint coefficient lies inside the block-permutation null. Alternatively, it is explained by the RV x dislocation-magnitude control.
```

#### NEAREST_TESTED_MECHANISM

```text
MARKET-06
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
MARKET-06 links dislocation magnitude to BTC adverse path. This card targets the persistence of the dislocation itself as a function of an on-chain friction.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse MARKET-06's adverse-path target. The fee layer is new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "DISLOC_BP": [
      15,
      30
    ],
    "FEE_PCTL": [
      80,
      90
    ],
    "HORIZON_MIN": [
      60
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Fees co-move with volatility; exchange withdrawal suspensions; ordinal inscription episodes; stablecoin rails bypass the BTC chain.
```

#### NO_LOOKAHEAD_RULE

```text
The fee percentile uses blocks that arrived at or before T, with a lag of 2 blocks. The dislocation median is computed from trailing data only.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "MARKET_06_OKX_BINANCE_FEASIBILITY_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Aligned 5m closes",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "1m closes for RV",
    "STATUS": "DATA_READY"
  },
  {
    "DATASET": "BITCOIN_BLOCKCHAIN_FULL_NODE_BLOCKS",
    "LEGAL_RANGE": "2022-01..2024-12",
    "OBSERVABLE": "Per-block median fee rate in sat/vB with block arrival time",
    "STATUS": "FEASIBILITY_REQUIRED"
  }
]
```

#### DATA_STATUS

```text
FEASIBILITY_REQUIRED
```

#### MISSING_OBSERVABLES

```json
[
  "per-block median fee rate with block arrival time",
  "exchange withdrawal suspension windows"
]
```

#### DATA_GAP_CLASS

```text
ONCHAIN_FEE_ARRIVAL_TIMING
```

#### EXPECTED_IMPLEMENTATION_COST

```text
Medium. It requires full-node fee extraction plus the catalog dislocation data.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that settlement-layer friction constrains how fast prices converge across venues.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates BTC-chain transfer frictions as a constraint on cross-venue convergence.
```

#### EXPECTED_INFORMATION_GAIN

```text
It connects an on-chain friction to cross-venue price structure, testing whether that friction constrains convergence.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
INTERACTION
```

#### COMPONENTS

```json
[
  "Cross-venue dislocation magnitude: absolute Binance perp minus OKX spot log price minus trailing 7d median",
  "On-chain BTC transfer cost: block median fee rate as a trailing 30d percentile"
]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

### C040 — Hidden replenishment at touched price levels and level break-through

Frozen complexity class: ATOMIC
Frozen mechanism family: NEW_FAMILY_PROPOSAL
Frozen information source: ORDER_BOOK
Round: generation:3

#### CANDIDATE_ID

```text
C040
```

#### NAME

```text
Hidden replenishment at touched price levels and level break-through
```

#### MECHANISM_FAMILY

```text
NEW_FAMILY_PROPOSAL
```

#### MECHANISM

```text
Large passive participants who work orders by re-posting show only a slice of their size. Aggressors must exhaust the unseen size, so levels with a high refill ratio are breached less often than levels with the same displayed depth.
```

#### CAUSAL_OR_STRUCTURAL_STORY

```text
Displayed depth understates the true supply at a level when passive participants keep re-posting. To break the level, aggressors must exhaust that unseen supply. The refill ratio reveals it after the fact, but it is known before the outcome window.
```

#### INFORMATION_SOURCE

```text
ORDER_BOOK
```

#### OBSERVABLE

```text
REFILL_RATIO = executed taker volume at the level during the touch episode divided by the maximum displayed size at that level during the episode
```

#### FUNCTION

```text
Test whether hidden replenishment at a touched level predicts whether the level is breached.
```

#### PRIMARY_TARGET

```text
BREACH_60 = 1 if trade price passes the level by at least BREACH_BAND_PCT within 60 minutes after the episode ends
```

#### HORIZON

```text
60 minutes after each touch episode ends
```

#### BASELINE_OR_NULL

```text
Touch episodes matched on displayed size, distance from mid, RV and UTC hour, analysed by logistic regression with controls. Null: refill ratios are permuted within strata.
```

#### FALSIFIER

```text
The breach rate does not decrease with refill ratio beyond what matched controls show.
```

#### NEAREST_TESTED_MECHANISM

```text
B2-05
```

#### MECHANISM_DISTANCE_ARGUMENT

```text
B2-05 infers flow absorption from klines. This card measures absorption at the price-level scale from book and trade data.
```

#### WHY_NOT_A_RESCUE

```text
It does not reuse B2-05's kline-based fields. The observable is new.
```

#### SEARCH_SURFACE

```json
{
  "MAX_VARIANTS": 4,
  "PARAMETERS": {
    "BREACH_BAND_PCT": [
      0.05,
      0.1
    ],
    "HORIZON_MIN": [
      60
    ],
    "REFILL_THRESHOLD": [
      2,
      4
    ]
  }
}
```

#### MAIN_CONFOUNDERS

```text
Spoofed displayed size; round-number levels; volatility bursts; match-engine latency.
```

#### NO_LOOKAHEAD_RULE

```text
The refill ratio uses only data up to the episode end. The outcome window starts after the episode end.
```

#### DATA_REQUIRED

```json
[
  {
    "DATASET": "TARDIS_BINANCE_FUTURES_L2_INCREMENTAL",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "BTCUSDT L2 book updates with timestamps",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "TARDIS_BINANCE_FUTURES_TRADES",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "Trades with price, size and aggressor side",
    "STATUS": "DATA_BLOCKED_COST"
  },
  {
    "DATASET": "CORE_BTC_BINANCE_V0",
    "LEGAL_RANGE": "2020-01..2024-12",
    "OBSERVABLE": "1m closes for RV",
    "STATUS": "DATA_READY"
  }
]
```

#### DATA_STATUS

```text
DATA_BLOCKED_COST
```

#### MISSING_OBSERVABLES

```json
[
  "tick-level L2 updates",
  "trades with aggressor side"
]
```

#### DATA_GAP_CLASS

```text
PAID_L2_AND_TRADES_HISTORY
```

#### EXPECTED_IMPLEMENTATION_COST

```text
High. It needs paid tick data and episode reconstruction.
```

#### WHAT_POSITIVE_WOULD_TEACH

```text
It would show that unseen passive supply governs whether price levels hold.
```

#### WHAT_NULL_WOULD_ELIMINATE

```text
It eliminates detectable hidden liquidity as a determinant of whether levels hold.
```

#### EXPECTED_INFORMATION_GAIN

```text
It adds a base hidden-liquidity mechanism for order-book cards.
```

#### PROTECTED_DATA_REQUIREMENT

```json
false
```

#### COMPLEXITY_CLASS

```text
ATOMIC
```

#### COMPONENTS

```json
[]
```

Existing source critics:

- NOVELTY: NOT_RUN
- FEASIBILITY: NOT_RUN
- RED_TEAM: NOT_RUN

## Invalid emitted cards

### C011

Frozen complexity class: CONDITIONAL
Frozen mechanism family: A
Frozen information source: PRE2020_SURFACE
Round: generation:1
Intake state: HARD_FAIL
Candidate table state: HARD_FAIL

Intake failures:

```json
[
  {
    "DETAIL": "string enum",
    "RULE": "PROVIDER_SCHEMA"
  }
]
```

Emitted provider item, which is also the intake-retained card:

```json
{
  "BASELINE_OR_NULL": "Matched random abstention inside the same weekend regime: remove the same fraction of weekend decision times at random within trailing-24h-RV decile x calendar-year strata, 2000 draws, and recompute the abstention delta. The IMPACT_PCT flag delta is compared with this null distribution. As a descriptive reference only, the same rule is also computed on weekday decision times. That reference is not part of the claim.",
  "CANDIDATE_ID": "C011",
  "CAUSAL_OR_STRUCTURAL_STORY": "Who acts: market makers quoting BitMEX XBTUSD, the BitMEX liquidation engine, and highly leveraged traders. BitMEX allowed up to 100x leverage on a BTC-margined inverse perpetual. Liquidations were sent by the engine as market orders. Makers kept their XBTUSD inventory flat by hedging on fiat spot venues such as Bitstamp, Coinbase and Kraken, and they moved USD between those venues over bank rails. Constraint: on Saturdays and Sundays the bank rails are closed, OTC desks run with fewer staff, and hedge venues are thinner. Makers who cannot rebalance collateral or hedge cheaply cut their displayed size and widen their quotes. Why the effect should exist: when the book is thin, each unit of volume moves price further (high IMPACT_PCT). A modest liquidation burst then reaches the next layer of leveraged liquidation prices, and the excursion compounds. On weekdays, rebalancing capacity refills depth quickly, so the same impact level should carry less tail consequence. The claim is limited to the weekend regime, where the capacity constraint binds by construction.",
  "COMPLEXITY_CLASS": "CONDITIONAL",
  "COMPONENTS": [],
  "DATA_GAP_CLASS": "NONE",
  "DATA_REQUIRED": [
    {
      "DATASET": "D2_BITMEX_PRE2020_XBTUSD",
      "LEGAL_RANGE": "pre-2020",
      "OBSERVABLE": "XBTUSD 5m open, high, low, close and contract volume",
      "STATUS": "DATA_READY"
    }
  ],
  "DATA_STATUS": "DATA_READY",
  "EXPECTED_IMPLEMENTATION_COST": "Low. One dataset, an hourly decision grid, trailing percentiles and a stratified permutation null. Roughly one day of engineering.",
  "EXPECTED_INFORMATION_GAIN": "Separates a liquidity-capacity channel from the volatility channel in tail-path abstention on a leverage-heavy venue, under an institutional constraint (bank-rail closure) that is fixed in advance. Either outcome refines the base library of abstention mechanisms.",
  "FALSIFIER": "Any of the following falsifies the claim: (1) the IMPACT_PCT abstention delta inside the weekend regime lies within the central 90% of the RV-matched random-abstention null; (2) its sign flips across calendar years of the pre-2020 sample in at least half of those years; (3) the delta disappears once flagged and unflagged decision times are compared within the same trailing-RV decile, which would mean impact-per-volume carries no tail information beyond RV.",
  "FUNCTION": "Conditional abstention characterization inside a regime fixed in advance. The regime is the weekend: hourly decision times whose UTC weekday is Saturday or Sunday, on BitMEX XBTUSD 5m bars in the pre-2020 sample. Within that regime only, the card compares the 6h maximum adverse excursion of decision times flagged by a high IMPACT_PCT against same-frequency random abstention matched on trailing RV decile.",
  "HORIZON": "6 hours from each hourly weekend-regime decision time, measured on 5m bars",
  "INFORMATION_SOURCE": "PRE2020_SURFACE",
  "MAIN_CONFOUNDERS": "Weekend realized volatility is lower on average, which is handled by RV-decile matching. Contract volume on the inverse contract is USD-denominated, so the impact scale shifts with price level; this is handled by trailing percentiles. BitMEX system-overload episodes rejected maker orders and could mimic thin books. CME futures weekend closure overlapped part of the sample. Hour-of-day composition differs between flagged and unflagged hours. Data gaps in the 5m archive may cluster around stress.",
  "MECHANISM": "",
  "MECHANISM_DISTANCE_ARGUMENT": "",
  "MECHANISM_FAMILY": "E",
  "MISSING_OBSERVABLES": [
    ""
  ],
  "NAME": "",
  "NEAREST_TESTED_MECHANISM": "D2",
  "NO_LOOKAHEAD_RULE": "",
  "OBSERVABLE": "",
  "PRIMARY_TARGET": "",
  "PROTECTED_DATA_REQUIREMENT": false,
  "SEARCH_SURFACE": {
    "MAX_VARIANTS": 1,
    "PARAMETERS": [
      {
        "NAME": "x",
        "VALUES": [
          1
        ]
      }
    ]
  },
  "WHAT_NULL_WOULD_ELIMINATE": "",
  "WHAT_POSITIVE_WOULD_TEACH": "",
  "WHY_NOT_A_RESCUE": ""
}
```

## Missing slots

The provider emitted no usable item for these planned slots. The candidate table records each as `HARD_FAIL` with `SLOT_IDENTITY` / `missing card for slot`.

- `C012` generation:1 ATOMIC family B source OFFICIAL_CALENDAR
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C013` generation:1 ATOMIC family C source CROSS_SECTIONAL_PANEL
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C014` generation:1 COMPOSITE family D source OPTIONS
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C015` generation:1 CONDITIONAL family E source ONCHAIN
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C016` generation:1 INTERACTION family F source ORDER_BOOK
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C017` generation:1 ATOMIC family G source KLINES
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C018` generation:1 CONDITIONAL family H source CROSS_VENUE
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C019` generation:1 INTERACTION family I source PRE2020_SURFACE
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`
- `C020` generation:1 ATOMIC family J source OFFICIAL_CALENDAR
  - Intake failures: `[{"DETAIL": "missing card for slot", "RULE": "SLOT_IDENTITY"}]`

## Observed cost statistics

Computed from COMPLETE source calls only. Uncertain reservations are listed separately and are not included in these actual-cost figures. Percentiles use linear interpolation at index `p*(n-1)`.

| Role | N complete | Total USD | Mean USD | Median USD | P90 USD | Max USD | Mean input tokens | Mean output tokens | Mean reasoning tokens | Max output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GENERATOR | 4 | 2.192768 | 0.548192 | 0.576044 | 0.648975 | 0.668290 | 24697.25 | 49879.75 | 30432 | 61896 |
| NOVELTY_CRITIC | 14 | 1.203498 | 0.085964 | 0.085435 | 0.094721 | 0.108136 | 29131.71428571428571428571429 | 2770.071428571428571428571429 | 1580.214285714285714285714286 | 5008 |
| FEASIBILITY_CRITIC | 13 | 0.008603 | 0.000662 | 0.000656 | 0.000728 | 0.000743 | 4529.769230769230769230769231 | 416.8461538461538461538461538 | 323.5384615384615384615384615 | 590 |
| RED_TEAM | 13 | 0.249068 | 0.019159 | 0.019716 | 0.025179 | 0.029952 | 2018.769230769230769230769231 | 1512.153846153846153846153846 | 1399.153846153846153846153846 | 2573 |

Token fields: input is `input_tokens` or else `prompt_tokens`; output is `output_tokens` or else `completion_tokens`; reasoning is `reasoning_tokens` or else `thinking_tokens`.

### OBSERVED_COST_EXTRAPOLATION_ONLY

For each critic role, the count of VALID cards without a COMPLETE result multiplied by that role's observed mean cost of COMPLETE calls, then rounded to the nearest micro-dollar and summed. Informational. It does not authorize a call and does not replace the conservative reservation bound.

C024 feasibility is UNCERTAIN and already reserved at USD 0.005302. It is one of the feasibility rows in this extrapolation. Do not add this extrapolation on top of that existing reservation.

This figure does not authorize execution and does not replace the conservative reservation bound.

- NOVELTY_CRITIC: 16 missing complete results × mean 0.085964 = 1.375426
  - Candidate ids: C025, C026, C027, C028, C029, C030, C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- FEASIBILITY_CRITIC: 17 missing complete results × mean 0.000662 = 0.011250
  - Candidate ids: C024, C025, C026, C027, C028, C029, C030, C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- RED_TEAM: 17 missing complete results × mean 0.019159 = 0.325704
  - Candidate ids: C024, C025, C026, C027, C028, C029, C030, C031, C032, C033, C034, C035, C036, C037, C038, C039, C040
- Total extrapolated USD: 1.712380

### Uncertain calls

- FEASIBILITY_CRITIC:C024 state UNCERTAIN call key `76ddea9fac6cbafa398ad5c821b1fed99e40f25be8af903ef0634811b0450604` response id `None` reserved USD 0.005302
  - Journal error: TimeoutError

## Integrity

- Source journal SHA256: `ffa179220d12986520c214f7a1ad1cfecd084848f9de0158fcd43476d9447a37`
- Source journal mutated: false
- Source calls reconciled by this export: 0
- Provider calls made by this export: 0
- Normalized cards round-trip to the stored candidate representation: true
- Emitted and missing slots were read from the raw round responses: true
