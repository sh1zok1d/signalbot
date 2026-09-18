# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — canonical RESULT

- **Status:** `RESULT`
- **Unit ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION_RESULT`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Date:** 2026-09-17

Canonical machine-readable twin:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json`.

RESULT SHA256:
`5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`.

This document restates the sealed mechanical classification. It does
not reinterpret it.

```text
FINAL_CLASSIFICATION = NO_EVIDENCE
MARKET_01_TEST_CALIBRATED = NO
PROTECTED_OOS_TOUCHED = NO
B2_06_EXECUTION_AUTHORIZED = NO
DEFAULT_V4 = NO
CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED = 1
```

Execution identity:

```text
EXECUTION_HEAD = 9e6f398e4d0a294adff317354c64fdbce91315a2
EXECUTION_TREE = 0f3092e8d61e040f34cb60f633584764c9cb6a6e
CANONICAL_RUN_IDENTITY = f430399f46e6122a2633a34e99e9bd0ab8fe65c1baf9c05b5982551a4608739d
ARM_SHA256_UNUSED = 5b639453030ae3d18efc40dc3ffffeeade0b152719cc38ba4cac660aecba75dd
RESERVATION_SHA256_UNUSED = ebfa2cae43541c617540d19c879e9858b692c99c60563dc9aa206c9355455845
PRICE_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
OI_SNAPSHOT = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
```

Mechanical confirmatory fields from the sealed JSON:

```text
TOTAL_ELIGIBLE_EPISODES = 7701
CANDIDATE_EPISODES = 1720
BASELINE_EPISODES = 5981
USABLE_STRATA = 3
beta_candidate = -0.00016324445975347867
bootstrap_se = 0.00022218794009876234
bootstrap_p_one_sided = 0.757
DETECTED = NO
robustness = not evaluated (primary DETECTED is false)
```

`NO_EVIDENCE` means only: the frozen primary test was identifiable and
did not satisfy `beta_candidate > 0` and `p_one_sided <= 0.05`.

It does not authorize threshold repair, window change, or a second
canonical execution. It is not a production signal, not validated
alpha, not causal proof, and not OOS validation.

No rerun is authorized.
