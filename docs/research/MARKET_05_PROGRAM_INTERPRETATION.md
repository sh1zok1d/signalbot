# MARKET-05 — Program Interpretation and Closeout

**Status:** `MARKET_05_SCIENTIFICALLY_SPENT / PROGRAM_UPDATED_INFORMATION_SET_EXPANSION`
**Unit kind:** program evidence / governance. **Not** a new scientific experiment.
**Machine-readable twin:** [`MARKET_05_PROGRAM_INTERPRETATION.json`](MARKET_05_PROGRAM_INTERPRETATION.json)

This document binds the canonical MARKET-05 RESULT and records the
program-level decision that follows it. It does not rerun MARKET-05,
inspect protected OOS, create MARKET-06, invent a rescue child, or
change the frozen classification.

```text
SCIENTIFIC_OUTCOMES_INSPECTED_DURING_UPDATE = false
PROTECTED_OOS_TOUCHED = false
MARKET_06_CREATED = false
```

## 1. Canonical RESULT identity

```text
RESULT_HEAD = 828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b
RESULT_TREE = 338e72d23ff7f5547191221527b762a47e4e48bc
RUN_IDENTITY = 6957613de4b035d850fc97edb833565c5fd3d7b085aa158e0992b88142190635
CLASSIFICATION = MARKET_05_NO_EVIDENCE
result_json_sha256 = 80a29335dc697e784c1bb6d47c81dd1760f2f19bc49d36573b59372255a47f14
result_md_sha256 = f0849bdaf3cf1fb0e939696d2fdc230342045717f902fcb5ef12f28b889db6ed
```

Bound headline quantities (copied from the sealed RESULT; not recomputed):

```text
eligible_rows = 1825
BETA_ETH_CONFIRMATION = -0.0002567502511611957
BETA_ETH_CONFIRMATION_CI = [-0.0023464584123732146, 0.0015931596784811688]
POOLED_MAE_BASELINE = 0.01474832634118777
POOLED_MAE_CANDIDATE = 0.014768642312125536
RELATIVE_MAE_IMPROVEMENT = -0.0013775102657600513
RELATIVE_MAE_IMPROVEMENT_CI = [-0.00249762914797686, -0.000375839559399871]
YEAR_2022 = 0.000026398780684000478
YEAR_2023 = -0.004303506211586372
YEAR_2024 = -0.00045725937785223714
G1 = PASS
G2 = FAIL
G3 = FAIL
G4 = FAIL
G5 = FAIL
G6 = FAIL
PROTECTED_OOS_TOUCHED = false
```

## 2. Scientific interpretation

MARKET-05 closes the exact preregistered formulation:

- daily 00:00 UTC decisions
- 24h BTC state
- continuous ETH confirmation
- 24h BTC direction-aligned adverse-path risk
- BTC-only baseline vs baseline + ETH_CONFIRMATION

The candidate did not provide stable incremental predictive value.

MARKET-05 is scientifically spent. No rerun.

The negative relative MAE does **not** authorize a reverse hypothesis.

Do **not** write:

- cross-asset context is useless;
- ETH contains no predictive information;
- divergence is validated;
- reverse sign is validated;
- ETH worsens BTC forecasting generally.

`NO_EVIDENCE` means the exact frozen formulation missed the frozen
historical gates. It is not a general claim about ETH, divergence, or
cross-asset context.

## 3. Program-level state after MARKET-05

```text
INTERNAL_HISTORICAL_CANDIDATES_PROMOTED = 0
VALIDATED_OOS_CANDIDATES = 0
PROTECTED_OOS_TOUCHED = false

MARKET_01 = NO_EVIDENCE
MARKET_02 = NO_EVIDENCE
MARKET_03 = EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION
MARKET_04 = BLOCKED_OBSERVABLE / NOT_TESTED
MARKET_05 = NO_EVIDENCE
```

Do not count experiment number as independent evidence.

- M01/M02 are dependent/sequential.
- M03 is external historical reproduction.
- M05 is a distinct information-family test but remains historical
  development evidence.

MARKET-04 remains:

```text
SELECTED
NOT TESTED
BLOCKED HISTORICAL OBSERVABLE
```

Do **not** mark MARKET-04 rejected. The parent hypothesis remains
scientifically alive. The blocker was historical availability /
provenance, not mechanism failure.

MARKET-04H remains:

```text
OUTCOME_BLIND_OBSERVABLE_SUBSTITUTION_AFTER_TEMPORAL_FEASIBILITY_FAILURE
BLOCKED OBSERVABLE
```

It is not scientific negative evidence and is not an independent
scientific evidence unit.

## 4. Program decision

```text
SAME_INFORMATION_SET_HYPOTHESIS_GENERATION_PAUSED = true
NEXT_PROGRAM_PHASE = INFORMATION_SET_EXPANSION
NEXT_INFORMATION_FAMILY = POINT_IN_TIME_FUNDING_PREMIUM_OBSERVABILITY
NEXT_UNIT = FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION
```

Do **not** immediately create MARKET-06 from another simple transform of
the same existing price/OI/cross-asset information set.

Reason: the program has now spent several distinct historical
formulations without producing an internal candidate:

- OI directional state
- OI confirmation
- cross-asset confirmation
- multiple prior H/B price/flow mechanisms

Further nearby feature generation has declining information gain and
increasing adaptive-search risk.

This is **not** termination of Signalbot research. It is a transition:

- FROM: more hypothesis generation on the same information set
- TO: expand / improve the information set

## 5. Next information priority

Highest-priority unresolved information family:

`FUNDING / PREMIUM / LEVERAGE STATE`

Why:

- MARKET-03 externally reproduced a funding-filter drawdown effect;
- MARKET-04 was selected specifically to test whether funding state
  contains incremental adverse-path-risk information;
- MARKET-04 was not rejected scientifically;
- the blocker was historical availability/provenance, not mechanism
  failure.

Do **not** attempt a third historical proxy salvage.
Do **not** reinterpret current Binance historical archives as
point-in-time safe.

This does not guarantee that funding will work. It only resolves the
largest scientifically relevant information gap currently identified.

Collection start must precede any future `M04-FWD`
preregistration/execution. That later hypothesis is **not** frozen here.

## 6. What this unit does not do

- rerun MARKET-05
- inspect protected 2025/2026 OOS
- create MARKET-06
- invent a rescue child of MARKET-05
- change MARKET-05 interpretation
- reinterpret its negative result as a reverse effect
- implement or run a collector
- select thresholds or outcome gates
- compute future return / MAE / drawdown / prediction / beta /
  classification on any newly collected stream
'''