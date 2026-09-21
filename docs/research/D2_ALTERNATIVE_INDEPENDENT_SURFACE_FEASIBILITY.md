# D2 alternative independent surface feasibility

**Unit:** `D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY`  
**Kind:** outcome-blind feasibility only. Not confirmation execution.

## Frozen mechanism (unchanged)

Candidate: `D2 / RULE_1 / RV_ABSTENTION`

- rule: ABSTAIN(t)=1 iff ev.rv_btc_24h(t) > P90 of its own trailing 250 completed decision-point values with t excluded.
- target: 24h direction-aligned adverse-path severity using the exact existing 288 x 5m future-bar construction (arithmetic MAE).
- direction: BTC_SIDE(t) = sign(BTC_RET_24H(t))
- practical bar: DELTA >= 0.20 * UNCONDITIONAL_MEAN
- statistical concept: candidate-abstained rows must have unusually high severity versus rate-matched random abstention
- `RULE_CHANGED` / `TARGET_CHANGED` / `GATES_CHANGED` / `CLOCK_CHANGED` = false

00:05 UTC is preserved as the frozen MARKET-05/06 5m grid convention. It was
not redesigned for BitMEX convenience.

## Refined fresh-N power (Binance 2020-2024 only)

Method: `YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK`  
Seed: `20260921124` (previous 728/1092 retained from seed 20260921123 as `{728: 0.64, 1092: 1.0}`)

```
N_BELOW = 800
N_ABOVE = 825
FIVE_ROW_REFINEMENT_GRID = [805, 810, 815, 820]
REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815
POWER_AT_REFINED_MIN_N = 0.801
POWER_95CI_AT_REFINED_MIN_N = [0.7751234971811168, 0.824572794210579]
POWER_USES_BINANCE_2025_2026 = false
POWER_USES_BITMEX_OUTCOMES = false
```

- N=728 stage=coarse power=0.675 95CI=[0.6453485364754667, 0.703312098054589]
- N=750 stage=coarse power=0.704 95CI=[0.6749696568758727, 0.7314690256620207]
- N=775 stage=coarse power=0.754 95CI=[0.7263681599761741, 0.7796878467131639]
- N=800 stage=coarse power=0.761 95CI=[0.7336003718062974, 0.7864020602642429]
- N=825 stage=coarse power=0.806 95CI=[0.7803394533741679, 0.8293185704326724]
- N=850 stage=coarse power=0.827 95CI=[0.8023165344033985, 0.8491807655470485]
- N=875 stage=coarse power=0.844 95CI=[0.8201985055513945, 0.8651686846105435]
- N=900 stage=coarse power=0.893 95CI=[0.8723150421383737, 0.91067712569198]
- N=925 stage=coarse power=0.921 95CI=[0.9026250851159918, 0.9361527842391708]
- N=950 stage=coarse power=0.933 95CI=[0.9157879467581331, 0.9468980803933762]
- N=975 stage=coarse power=0.961 95CI=[0.9471306895804986, 0.9713410390958196]
- N=1000 stage=coarse power=0.97 95CI=[0.9574965858524128, 0.9789062611711653]
- N=1025 stage=coarse power=0.99 95CI=[0.9816905311296853, 0.9945592455544707]
- N=1050 stage=coarse power=0.998 95CI=[0.9927371921365079, 0.9994513564118793]
- N=1075 stage=coarse power=0.998 95CI=[0.9927371921365079, 0.9994513564118793]
- N=1092 stage=coarse power=1.0 95CI=[0.996173241514445, 1.0]
- N=805 stage=five_row_refinement power=0.789 95CI=[0.7626295063588951, 0.813158627236454]
- N=810 stage=five_row_refinement power=0.793 95CI=[0.7667904475082261, 0.8169670720192386]
- N=815 stage=five_row_refinement power=0.801 95CI=[0.7751234971811168, 0.824572794210579]
- N=820 stage=five_row_refinement power=0.794 95CI=[0.7678312571433845, 0.8179186088671091]

1092 is only the smallest previously tested size meeting power, not an
assumed true minimum.

## Primary candidate: BitMEX XBTUSD

Instrument: `XBTUSD` inverse perpetual (`FFWCSX_INVERSE_PERPETUAL`), listing `2016-05-13T12:00:00.000Z`.

Official source: `https://www.bitmex.com/api/v1/trade/bucketed`  
Docs: `https://docs.bitmex.com/api-explorer/get-trade-bucketed`  
Launch: `https://www.bitmex.com/blog/announcing-the-launch-of-the-perpetual-xbtusd-leveraged-swap`  
Timestamp semantics: `BUCKET_END` (open_time = timestamp − 5m).  
Kaggle / third-party cleaned datasets: not used.

```
BITMEX_RAW_DATA_START = 2016-05-13T11:55:00.000Z
BITMEX_FIRST_RV_AVAILABLE_T = 2016-05-15T00:05:00.000Z
BITMEX_FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00.000Z
BITMEX_LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00.000Z
BITMEX_PRE2020_ELIGIBLE_N = 1069
BITMEX_THEORETICAL_COMPLETE_GRID_N = 1072
BITMEX_5M_PATH_AVAILABLE = True
missing_bucket_count = 288
```

Temporal class: `PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION` (class A).  
A 2020-2024 other-venue window is class B and is not counted as independent
temporal confirmation. Protected Binance 2025/2026 remains class C, sealed.

## Semantic compatibility

Classification: `SCIENTIFICALLY_COMPARABLE_CROSS_VENUE`

The frozen adverse-severity metric is a **normalized price-path** observable
(`(entry − min(low))/entry` or `(max(high) − entry)/entry`). It does not use
inverse 1/x PnL, linear USD-M PnL, funding, or mark/index. XBTUSD last-trade
OHLC can carry that target without converting inverse payoff into linear PnL.

It is **not** `EXACT_OBSERVABLE_PORTABLE` (USD vs USDT, venue last-price,
inverse vs linear environment). A later BitMEX result, if executed, is

`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`

not `EXACT_BINANCE_CONFIRMATION`. Future protected Binance 2025/2026 remains
the stronger same-venue OOS reserve.

## Decision

```
CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
NEXT_UNIT = D2_BITMEX_REPLICATION_PREREG_FREEZE
D2_OUTCOME_COMPUTED_ON_BITMEX = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
ARM_CREATED = false
CROSS_VENUE_ROW_COUNT_MULTIPLICATION = false
```

Backup search opened: `False`. BitMEX primary candidate is feasible before any D2 outcome; no backup venue search.

## Not created

- MARKET-07
- confirmation RESULT
- ARM
- execution permit
- candidate outcome
- one-shot run
