# LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1

Routing: `LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT`.
Class: `LEVEL_VOLATILITY_TRANSITION_CANDIDATE`.
Claim ceiling: L2 / DISCOVERY_ONLY.
LEVEL_ENGINE_DISCOVERY_8_OF_8_COMPLETE = YES.

## Cohort

- Real legitimate first touches: 1919
- Pseudo legitimate first touches: 1962
- Matched pairs: 1231
- Path-complete pairs: 1231
- Usable pairs (both RV finite and positive): 1231
- ISO weeks: 254
- Non-positive RV drops: {'real_nonpositive_rv': 0, 'pseudo_nonpositive_rv': 0, 'pairs_dropped': 0, 'path_complete_pairs': 1231}

## Realized volatility

- Real PRE60 mean/median: 0.00208184 / 0.00165837
- Real POST60 mean/median: 0.00290024 / 0.00221674
- Pseudo PRE60 mean/median: 0.00203711 / 0.00168196
- Pseudo POST60 mean/median: 0.00257305 / 0.00200996
- Real transition mean/median/p25/p75: 0.298374 / 0.245473 / -0.0917017 / 0.643198
- Pseudo transition mean/median/p25/p75: 0.191571 / 0.148142 / -0.179264 / 0.518741

## Primary

- DELTA_TRANSITION: 0.106803 log units
- Multiplicative: +11.272%
- CI95: [0.0665477 .. 0.146661]
- p: 1.048e-07
- Bootstrap: 2000/2000 seed 20261024
- Practical 10% pass: True
- CI excludes 0: True

## Pre-RV balance

- Paired log(pre real / pre pseudo) mean: 0.00562311 (+0.564%)
- At or above the 10% scale: False

## Expansion fraction (descriptive)

- Real P(transition > 0): 0.69537
- Pseudo P(transition > 0): 0.610885
- Difference: 0.0844842

## Years

- 2020: N=242 delta=0.156417 (+16.931%)
- 2021: N=334 delta=0.113755 (+12.048%)
- 2022: N=258 delta=0.00102434 (+0.102%)
- 2023: N=181 delta=0.161414 (+17.517%)
- 2024: N=216 delta=0.121052 (+12.868%)

## Family

- DAY: N=1071 delta=0.0958646 (+10.061%)
- WEEK: N=138 delta=0.228151 (+25.628%)
- MONTH: N=22 delta=-0.121871 (-11.474%)

## Side

- resistance: N=690 delta=0.134006 (+14.340%)
- support: N=541 delta=0.0721083 (+7.477%)

## Leave-one-year-out

- omit_2020: N=989 delta=0.0946629 (+9.929%)
- omit_2021: N=897 delta=0.104215 (+10.984%)
- omit_2022: N=973 delta=0.134851 (+14.437%)
- omit_2023: N=1050 delta=0.0973892 (+10.229%)
- omit_2024: N=1015 delta=0.103771 (+10.935%)

## Stability

`{'years': {'pass': True, 'n_eligible': 5, 'n_matched': 5, 'n_opposite': 0}, 'family': {'pass': True, 'contradiction': False, 'day_estimable': True, 'week_estimable': True}, 'side': {'pass': True, 'contradiction': False}, 'loyo': {'pass': True, 'n_checked': 5}, 'failed': []}`

No product integration. No confirmation. No successor. The 8-step discovery sequence stops here.
