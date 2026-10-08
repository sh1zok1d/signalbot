# LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1

Mode: `CONFIRMATION`.
Surface class: `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`. Not pristine.
Routing: `REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION`.
Evidence label: `REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE`.
Claim ceiling: L2.
Independence from the resolution clock: `UNRESOLVED`.

The frozen structural first-touch volatility-transition relation discovered on Binance 2020–2024 was evaluated on time-disjoint BitMEX 2017–2019 under the unchanged 60m pre/post definition. The BitMEX surface had previously been used for a neighboring 4h barrier-path outcome, so this is an exposed-surface historical replication rather than a pristine confirmation.

## Cohort

- Real legitimate first touches: 890
- Pseudo legitimate first touches: 891
- Matched pairs: 558
- Path-complete pairs: 554
- Usable pairs: 554
- ISO weeks: 120
- Non-positive RV drops: {'real_nonpositive_rv': 0, 'pseudo_nonpositive_rv': 0, 'pairs_dropped': 0, 'path_complete_pairs': 554}

## Realized volatility

- Real PRE60 mean/median: 0.00294914 / 0.0021841
- Real POST60 mean/median: 0.0041052 / 0.00304439
- Pseudo PRE60 mean/median: 0.00292705 / 0.00229447
- Pseudo POST60 mean/median: 0.00384544 / 0.00273449
- Real transition mean/median: 0.357175 / 0.305587
- Pseudo transition mean/median: 0.26063 / 0.176722

## Primary

- DELTA_TRANSITION: 0.0965449 (+10.136%)
- 95% CI: [0.0217805 .. 0.168173]
- CI multiplicative: [2.201940328754759, 18.314106054374978]
- SE: 0.0380671
- Wald p: 0.011207
- Bootstrap: 2000/2000 seed 20261025
- Practical bar log(1.10) cleared: True
- CI excludes 0: True
- CI contains log(1.10): True
- CI contains discovery point 0.106803: True

## Pre-RV balance

- Paired mean log(real pre / pseudo pre): -0.0207578 (-2.054%)
- Paired median of that log: 0
Not used as an adjustment.

## Expansion fraction, descriptive

- Real P(transition > 0): 0.702166
- Pseudo P(transition > 0): 0.631769
- Difference: 0.0703971

## Epochs

- 2017H2: N=100 delta=0.142477 (+15.313%)
- 2018: N=250 delta=0.00281157 (+0.282%)
- 2019: N=204 delta=0.188898 (+20.792%)

## Family

- DAY: N=483 delta=0.105763 (+11.156%)
- WEEK: N=62 delta=0.0474811 (+4.863%)
- MONTH: N=9 delta=-0.0601614 (-5.839%)

## Side

- resistance: N=269 delta=0.123457 (+13.140%)
- support: N=285 delta=0.0711433 (+7.374%)

## Leave-one-epoch-out

- omit_2017H2: N=454 delta=0.0864277 (+9.027%)
- omit_2018: N=304 delta=0.173628 (+18.961%)
- omit_2019: N=350 delta=0.0427161 (+4.364%)

## Discovery comparison, not pooled

- Binance discovery point: 0.106803 (+11.272%)
- The two samples were not pooled.

No product change. No prospective collection. No cross-venue unit. Clock independence remains unresolved.

## Limitations

The route above was frozen before the outcome and was not changed after these facts were seen.

- The 2018 epoch is +0.28%. It is positive and practically null. The frozen epoch rule is a sign rule.
- Leave-one-epoch-out stays positive. Omitting 2017H2 is about +9.03%, and omitting 2019 is about +4.36%. Both are below `log(1.10)`. The frozen leave-one-epoch-out rule asks for the sign only.
- The 95% interval starts near +2.20%. It contains multipliers below 10%, and it also contains `log(1.10)` and the discovery point +0.106803. The frozen support rule does not require the whole interval to sit above the bar.
- Support is about +7.37% and WEEK is about +4.86%. Both keep the positive sign and sit below the bar. The inherited material-contradiction rule does not treat that as a failure.
- MONTH has N=9 and is opposite. It is below the family minimum and is diagnostic only.
- The paired pre-RV log difference is about −2.05%. It was not used to rematch.
- #357 had already read the neighboring 4h high/low barrier path on this surface. This replication is not pristine.
- `INDEPENDENCE_FROM_RESOLUTION_CLOCK = UNRESOLVED`. A pass does not say the transition is separate from resolution dynamics.
- The ceiling is L2. This is not a current probability, not an expected current RV, and not a trading edge.
- Prospective collection was not started. #363 was not started. The Binance and BitMEX samples were not pooled.
