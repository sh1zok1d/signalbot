# Discovery Sprint 03 D10 RESULT

**Classification:** `NO_USEFUL_STRUCTURE`
**Execution root:** `e2852f57ee946ec8380f09fa4cf834579c40f872`
**RESULT_PAYLOAD_SHA256:** `32c85b26abd3f73b9bf13a1d24063742496b5f9269f2e8af5cf5aab99e1aa85c`

Adaptive discovery on historically exposed data. Not proven alpha, not a trading edge, not a confirmed mechanism, not causal proof.

```
CLASSIFICATION = NO_USEFUL_STRUCTURE
STATISTICAL_GATE = False
PRACTICAL_GATE = False
TEMPORAL_GATE = True
PROTECTED_2025_OPENED = False
PROTECTED_2026_OPENED = False
```

MEAN_EVENT = -3.2315971654121255e-05
MEAN_MATCHED_CONTROL = -4.6354284587184016e-05
DELTA = 1.403831293306276e-05
DELTA_BPS = 0.1403831293306276
MC_P = 0.45525447455254475

Does not validate MARKET-05. Does not imply generic ETH lead-lag or trading alpha.

YEARLY_DELTA: 2020=-0.0004087763484919691; 2021=0.0006350594045199916; 2022=-0.00032479596281575384; 2023=5.551234662569777e-05; 2024=8.001975126615166e-05

Discovery-stage limitation: D10 events may cluster in calendar time. This repair uses 1:1 YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET matching and stratified label permutation inside those frozen strata. It does not add a post-hoc event refractory or a block bootstrap.
