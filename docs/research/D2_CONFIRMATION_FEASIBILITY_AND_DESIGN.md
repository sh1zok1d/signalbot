# D2 confirmation feasibility and design

**Unit:** `D2_CONFIRMATION_FEASIBILITY_AND_DESIGN`
**Kind:** `OUTCOME_BLIND_CONFIRMATION_DESIGN`
**Date:** `2026-09-21`
**Candidate:** `D2 / RULE_1 / RV_ABSTENTION`
**Discovery status:** `PROMISING_PROTOTYPE` (adaptive discovery only; not evidence)

This unit does **not** execute confirmation, inspect 2025/2026 BTC price
values, materialize protected parquet, create MARKET-07, or ARM anything.
The scientific confirmation design is unchanged: same rule, target,
comparator, P90 / trailing-250 / 24h horizon / severity target /
random-abstention comparator / 20% practical gate / P95 statistical gate.

## Verdict

| Field | Value |
|---|---|
| `PRIMARY_CONFIRMATION_SURFACE` | `2025` |
| `SECOND_RESERVED_SURFACE` | `2026` |
| `CONFIRMATION_FEASIBILITY` | `UNDERPOWERED_SINGLE_YEAR_2025` |
| `ONE_YEAR_STATISTICAL_POWER_AT_20PCT` | `0.011` |
| `ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT` | `0.006` |
| `PRIMARY_PROSPECTIVE_POWER_CRITERION` | `STATISTICAL_POWER_AT_20PCT_EFFECT` |
| `MINIMUM_ACCEPTABLE_CONFIRMATION_POWER` | `0.8` |
| `TWO_YEAR_STATISTICAL_POWER_AT_20PCT` | `0.903` |
| `THREE_YEAR_STATISTICAL_POWER_AT_20PCT` | `1.0` |
| `FOUR_YEAR_STATISTICAL_POWER_AT_20PCT` | `1.0` |
| `MIN_REQUIRED_FRESH_DECISION_ROWS` | `728` |
| `MIN_REQUIRED_FRESH_YEARS` | `2` |
| `CONFIRMATION_SURFACE_REQUIREMENT` | `TWO_YEARS_INDEPENDENT_FRESH` |
| `POTENTIAL_FUTURE_SURFACE` | `2025_PLUS_FULL_2026` |
| `AUTHORIZED_TO_OPEN` | `false` |
| `EXPECTED_2025_ELIGIBLE_N` | `364` |
| `EXPECTED_2025_ABSTAIN_COUNT` | `39` |
| `2025_OPEN_AUTHORIZED` | `false` |
| `MARKET_07_CREATED` | `false` |
| `ARM_CREATED` | `false` |
| `PROTECTED_2025_PRICE_VALUES_INSPECTED` | `false` |
| `PROTECTED_2026_PRICE_VALUES_INSPECTED` | `false` |
| `RULE_CHANGED` | `false` |
| `TARGET_CHANGED` | `false` |
| `GATES_CHANGED` | `false` |
| `NEXT_UNIT` | `D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_2026_WITHOUT_OPENING` |

Historical joint field `POWER_AT_20PCT_MIN_EFFECT` remains `0.006`
and is **not** the primary prospective criterion.

## POWER_INTERPRETATION_CORRECTION

Primary prospective power criterion:

`STATISTICAL_POWER_AT_20PCT_EFFECT >= 0.80`

That is the probability the frozen statistical gate
`MU_RULE > P95(random-control means)` passes when the true relative
effect is 20%.

`JOINT_PASS_PROBABILITY_AT_20PCT_EFFECT` (both statistical and practical
gates) is diagnostic only. The practical gate itself is unchanged and
remains an actual execution-time requirement:

`DELTA >= 0.20 * UNCONDITIONAL_MEAN`

TRUE_EFFECT = 20% relative is the same magnitude as the frozen practical confirmation gate DELTA >= 20% * UNCONDITIONAL_MEAN. power_practical_gate at that exact boundary is therefore approximately 0.5 by construction / sampling variability of MU_CONTROL_MEAN. The observed original value power_practical_gate ~= 0.499 is not itself evidence that the study is underpowered.

This amendment is an interpretation correction plus fresh-surface size
planning. It is **not** a scientific-design rescue. The 20% effect bar
is not lowered.

### Original one-year calculation (preserved historical output)

Method: Year-cycled empirical 2021-2024 severity vectors. For each outer replicate, a random K-subset (K = frozen-rule abstain count that year) is location-shifted so DELTA/UNCONDITIONAL_MEAN equals the predeclared relative effect. Inner RATE_MATCHED_RANDOM_ABSTENTION uses 10000 uniform-without-replacement draws. The random subset is used so power is evaluated at the predeclared effect rather than at the observed discovery DELTA.

Seed `20260921121`, n_outer `1000`,
n_inner `10000`.

Frozen-rule fireable rate = 0.105775
(163 / 1541).

Year-cycled K (not the size-planning frozen-rate K):
`{'2021': 48, '2022': 32, '2023': 23, '2024': 50}`.

- 15% relative (sensitivity only): STATISTICAL_POWER = 0.000; JOINT_PASS_PROBABILITY = 0.000; practical-gate power = 0.000 (diagnostic)
- 20% relative (authoritative 20% true-effect row): STATISTICAL_POWER = 0.011; JOINT_PASS_PROBABILITY = 0.006; practical-gate power = 0.499 (diagnostic)
- 25% relative (sensitivity only): STATISTICAL_POWER = 0.500; JOINT_PASS_PROBABILITY = 0.500; practical-gate power = 1.000 (diagnostic)
- 30% relative (sensitivity only): STATISTICAL_POWER = 0.724; JOINT_PASS_PROBABILITY = 0.724; practical-gate power = 1.000 (diagnostic)

```
ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011
ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT = 0.006
historical POWER_AT_20PCT_MIN_EFFECT (joint) = 0.006
```

Because `0.011` is still far
below 0.80, `CONFIRMATION_FEASIBILITY` remains
`UNDERPOWERED_SINGLE_YEAR_2025`.

## Fresh-surface size planning (2020-2024 only)

Fireable 2020-2024 empirical direction-aligned MAE severity (trailing-250 warmup excluded). Hypothetical fresh surfaces are drawn with replacement. Expected K = round(frozen RULE_1 fireable rate * N). Inner P95 uses 10000 RATE_MATCHED_RANDOM_ABSTENTION replicates. No 2025/2026 prices are used.

Size-planning seed: `20260921122`.

- 1 year ≈ 364 decision rows, expected K = 39: STATISTICAL_POWER_AT_20PCT = 0.000; JOINT_PASS_PROBABILITY_AT_20PCT = 0.000 (diagnostic). Sensitivity: 25% statistical=0.231 / joint=0.231; 30% statistical=0.969 / joint=0.969.
- 2 years ≈ 728 decision rows, expected K = 77: STATISTICAL_POWER_AT_20PCT = 0.903; JOINT_PASS_PROBABILITY_AT_20PCT = 0.450 (diagnostic). Sensitivity: 25% statistical=1.000 / joint=1.000; 30% statistical=1.000 / joint=1.000.
- 3 years ≈ 1092 decision rows, expected K = 116: STATISTICAL_POWER_AT_20PCT = 1.000; JOINT_PASS_PROBABILITY_AT_20PCT = 0.509 (diagnostic). Sensitivity: 25% statistical=1.000 / joint=1.000; 30% statistical=1.000 / joint=1.000.
- 4 years ≈ 1456 decision rows, expected K = 154: STATISTICAL_POWER_AT_20PCT = 1.000; JOINT_PASS_PROBABILITY_AT_20PCT = 0.504 (diagnostic). Sensitivity: 25% statistical=1.000 / joint=1.000; 30% statistical=1.000 / joint=1.000.

```
MIN_REQUIRED_FRESH_DECISION_ROWS = 728
MIN_REQUIRED_FRESH_YEARS = 2
CONFIRMATION_SURFACE_REQUIREMENT = TWO_YEARS_INDEPENDENT_FRESH
POTENTIAL_FUTURE_SURFACE = 2025_PLUS_FULL_2026
AUTHORIZED_TO_OPEN = false
```

2025 remains unopened. 2026 remains unopened. They are not automatically
combined. The sizing result only says whether a future predeclared
combined fresh surface could be scientifically worthwhile.

Two independent fresh years (~728 decision rows) meet the primary statistical-power criterion at a 20% true effect. That does not authorize opening. POTENTIAL_FUTURE_SURFACE = 2025_PLUS_FULL_2026 is recorded only as a scientifically worthwhile future predeclared combined fresh surface. AUTHORIZED_TO_OPEN = false. 2025 remains unopened. 2026 remains unopened. They are not automatically combined now.

## Candidate (exact survivor only)

`ABSTAIN(t)=1 iff ev.rv_btc_24h(t) > P90 of its own trailing 250 completed decision-point values with t excluded. No threshold sweep.`

Not confirmed: DISLOCATION_ABSTENTION, D5 OR composition, AND rule, another RV threshold, another horizon, another direction definition, another outcome, another volatility estimator.

Mechanism preserved from frozen D2 / implementation `26d8f7066533bcae7138d5a1952783f2a16f3c39`:

- schedule: one daily BTC decision on MARKET-05/06 00:05:00Z grid
- exposure: full-size BTC perpetual in direction BTC_SIDE(t)
- direction: BTC_SIDE(t)=sign(ev.btc_ret_24h(t)); zero-return rows ineligible
- entry: frozen entry_open(t) from D2 / MARKET-05/06
- target: 24h direction-aligned adverse-path severity using the exact existing 288 x 5m future-bar construction (arithmetic MAE). Not terminal return, close-only MAE, MFE, drawdown, volatility, or PnL.

## Independent surface

Primary: calendar **2025 only**, Binance USD-M BTCUSDT perpetual,
`CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.

```
FIRST_T = 2025-01-01T00:05:00Z
LAST_T  = 2025-12-30T00:05:00Z
T in [2025-01-01T00:05:00Z, 2025-12-31T00:00:00Z)
```

2020-2024 is historically exposed and is **not** independent confirmation.
Trailing-250 feature history may use already-exposed 2024 decision points. 2025 outcomes remain unexposed. Metrics are computed only on 2025 T.

## 2025 metadata-only binding

Binding file: `docs/research_data/D2_CONFIRMATION_2025_METADATA_BINDING.json`. No price values. Objects were not
downloaded or materialized.

Months bound: 12/12.
Source hashes bound: `true`.
Canonical hashes bound: `true`.
Issues: none.
2026 object needed for frozen interval: `false`
(last future bar opens `2025-12-31T00:00:00Z`).

- `2025-01` source `BTCUSDT-1m-2025-01.zip` SHA256 `b69ca5b2c2d1ae00d68d2790d09138cb2a44085ff19e0da5dc98b569ea7e489e` parquet `edeff0a5e973ccd392b5461dadb06912117ee8039b4238b0a7de338b8d84ec55`
- `2025-02` source `BTCUSDT-1m-2025-02.zip` SHA256 `d84ca981d06ee6491e16597f8d43955f62cab399a9f4b6efc2ee1b4d3a37f0fc` parquet `565e47956ad62111d59d8067cd424779322c4e3ffc13d973d15b7b4bbc1d025b`
- `2025-03` source `BTCUSDT-1m-2025-03.zip` SHA256 `4837163333c9c9978255b8870a5a6de1bc48bd22a6c72fef54665a8d4e70b4df` parquet `715b2b44022860d3e081879cf79a37ed72be86310f4bf889874aeb1f890f1c0d`
- `2025-04` source `BTCUSDT-1m-2025-04.zip` SHA256 `87bca047ca7e8b1d27913091255018e121210276726c5aa445e85da6f56e2dcc` parquet `ee9c52b247934a16888741ca6d844a0dd83f1ba9b8e54159d6c71777f8ce69a3`
- `2025-05` source `BTCUSDT-1m-2025-05.zip` SHA256 `7acab7e40a74db53a2d6c35373ebe327eefa85b98f8c92fbe58755881e3841ee` parquet `25a3f5d67276d3f8782289b1d10720365805e17a43e314e775ce952e5c188848`
- `2025-06` source `BTCUSDT-1m-2025-06.zip` SHA256 `78872b32c4d0bbc2d89a0459539b90cff47de08a9a56fdf8d233943a32e78efc` parquet `c9e44c67682d7b7dd393af3483d7315466f5ed197049e42635b764beef0ed304`
- `2025-07` source `BTCUSDT-1m-2025-07.zip` SHA256 `cf5fe0891c80e68d2d613eb5457100b7d886eee8cc913ccdd96ef45e757a5aaf` parquet `8a71c561b4979e859e96ceb880ab3c22c1a7cbcca0e027ccb5615cded33ed5cb`
- `2025-08` source `BTCUSDT-1m-2025-08.zip` SHA256 `eaf41354fc1aa96eac94ee50b3fda603cd595f95030ebf30b2ab5bea7a4462c3` parquet `839849f52a065920d179672664260440bdf857e9ee69458e7c3b32e6c2db94ff`
- `2025-09` source `BTCUSDT-1m-2025-09.zip` SHA256 `c296ba45c215934e9750ca82846c7b5d14be661649d8e4423eac834cf57330dc` parquet `b7e613a4e720aaff3fcfd628714ad4fb66ab24df281d866b2452ac8a113de449`
- `2025-10` source `BTCUSDT-1m-2025-10.zip` SHA256 `bb7f53350fe27b6d8e38b5856ffc43f9ecda9d568d5bf31d0db0cd011da7100f` parquet `65b99b8881f85ddcccc562e9bdc0d2d994485ea57384d15eef263e01d913e025`
- `2025-11` source `BTCUSDT-1m-2025-11.zip` SHA256 `981da0b054f99b959fe6245fb363336b46908d358f37251d59bad308f375bc54` parquet `511fc4dd27c3ad088d8141a1d6ba07218bc960d646636ce33d9b7775f5862b14`
- `2025-12` source `BTCUSDT-1m-2025-12.zip` SHA256 `2d5b2e1887dac1dfe450010877de7203a72e19df7a771067b980bbb07ad3069c` parquet `4f6a6319e3ff492f0b174c69d9f5747bf1e89aef16bd0042a74e10093ff9c955`

## Estimand and gates

Comparator: RATE_MATCHED_RANDOM_ABSTENTION. Frozen D2 year-matched convention is retained. On a single-year 2025 surface it reduces to selecting exactly K eligible 2025 rows uniformly without replacement. No month/quarter matching added.

Quantities: `MU_RULE`, `MU_CONTROL_MEAN`, `DELTA = MU_RULE - MU_CONTROL_MEAN`,
`UNCONDITIONAL_MEAN`.

Statistical: MU_RULE > P95 of the 10000 RATE_MATCHED_RANDOM_ABSTENTION replicate mean-severity values. Authoritative pass rule. Monte Carlo one-sided p=(1+count(control_mean>=MU_RULE))/(1+N_REPLICATES) is reported only; it does not replace the percentile gate.

Seed frozen now: `D2_CONFIRMATION_RANDOM_CONTROL_SEED = 20260921120`.
Replicates: `10000`.

Practical: DELTA >= 0.20 * UNCONDITIONAL_MEAN on the independent 2025 surface. Same discovery-era 20% relative bar. Not lowered. Not replaced by the observed +1.42pp discovery DELTA.

Pass: STATISTICAL_GATE and PRACTICAL_MAGNITUDE_GATE both true. No quarterly rescue, threshold change, sign
reversal, alternative comparator, D5 combination, or horizon swap.

Quarters `['2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4']` are
diagnostic only.

Future execution labels (not assigned here):
['CONFIRMED_ON_INDEPENDENT_2025_SURFACE', 'NOT_CONFIRMED_ON_INDEPENDENT_2025_SURFACE', 'INVALID_CONFIRMATION_EXECUTION'].

## Discovery provenance (planning context only)

Eligible 1791, abstain 163, `MU_RULE` 0.04005839896629072,
`MU_CONTROL_MEAN` 0.025856224865193674, `DELTA` 0.014202174101097049,
`GATE_PASS` true, 5/5 positive years.

Do not use +0.0142 as the minimum effect. Do not power solely at that
observed effect. Do not shrink the 20% bar. Do not call it evidence.

## Independence boundary

Protected 2025/2026 price values inspected: `false` / `false`.
Exposed parquet years opened: ['2020', '2021', '2022', '2023', '2024'].
Protected price paths opened: none.

## Not created

- MARKET-07
- ARM
- reservation
- execution permit
- final prereg freeze
- protected-data loader execution
- RESULT artifact
