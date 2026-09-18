# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — canonical RESULT

- **Status:** `RESULT`
- **Unit ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Date:** 2026-09-18

Canonical machine-readable twin:
`docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json`.

RESULT SHA256:
`68e084b35201d227ecd9f48e99cc65a937b15fcb55a5849b1630c5d61850b478`.

This document restates the sealed mechanical classification. It does
not reinterpret it.

```text
FINAL_CLASSIFICATION = NO_EVIDENCE
MARKET_02_TEST_CALIBRATED = NO
PROTECTED_OOS_TOUCHED = NO
B2_06_EXECUTION_AUTHORIZED = NO
DEFAULT_V4 = NO
CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED = 1
rerun_occurred = NO
```

Execution identity:

```text
EXECUTION_HEAD = 6486dfadd920fc24a72fabe37d7dd906154cbc76
EXECUTION_TREE = 6f022334ea015756c8551bad73debed81ba4f8a9
FROZEN_IMPLEMENTATION_HEAD = 124da2bfdb0b5dfb6e0a8da5789a474af526f27f
FROZEN_IMPLEMENTATION_TREE = 7303a4507cba716209ea012f2c4e180eef31ba18
CANONICAL_RUN_IDENTITY = 4ef6a6c543f6a11930fe0ae26cb6bfbe7f19feac4c645d8fed992eebcd36a032
ARM_SHA256_UNUSED = 4cbb2212f4bf6ba2ded8d109d437434b79c24e436473acf9c771d80cd84542ae
ARM_SHA256_CONSUMED = c6807868e691c7c6b6b1c277eebefc1db6d4e6e090de15e6799bd35c3552c482
RESERVATION_SHA256_UNUSED = ca0eb13a0a0559c9227e4b99be0491b3845bb03566426d4e01da68cbc21c59c1
RESERVATION_SHA256_CONSUMED = 086d2c00c2395cf8a6edf00068ab672246b866fce2df0316d993059e43bb1a06
PREREG_MD_SHA256 = 4f19fd27435adddf4cc7e3c5568a8e316d8865b64468cdc30a9fd3918ffc3275
PREREG_JSON_SHA256 = ffc11ffd0f9d76ca12542ce45f466a6a7f9c651f1a030168a1617af2caa545a7
IMPLEMENTATION_FREEZE_JSON_SHA256 = 204da4872393461185f568ce46552cd9c4893b1f04db3264ba671cdf153d06fb
PRICE_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
PRICE_IDENTITY_SHA256 = a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630
OI_SNAPSHOT = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
OI_IDENTITY_SHA256 = bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e
MD_SEED = 1852983754304692007
```

Mechanical confirmatory fields from the sealed JSON:

```text
TOTAL_ELIGIBLE_EPISODES = 2487
CANDIDATE_EPISODES = 767
BASELINE_EPISODES = 1720
USABLE_STRATA = 3
usable_stratum_ids = HIGH|HIGH, HIGH|LOW, HIGH|MID
beta_confirmation = -0.00018378788969437528
bootstrap_se = 0.0004006951864901606
bootstrap_p_one_sided = 0.647
bootstrap_b_hat = 2.53178951058852
t_obs = -0.4586725668063106
DETECTED = NO
identifiable = YES
robustness = not evaluated (primary DETECTED is false)
exclusion_confirmatory_eligible = 2487
exclusion_missing_or_invalid_oi = 25
exclusion_not_oi_expansion = 5214
exclusion_not_qualifying_impulse = 270457
exclusion_overlap_skip = 177698
```

`NO_EVIDENCE` means only: the frozen primary test was identifiable and
did not satisfy `beta_confirmation > 0` and `p_one_sided <= 0.05`.

It does not prove that no relationship exists. It does not authorize
threshold repair, window change, alternative specification, or a second
canonical execution. It is not a production signal, not validated
alpha, not a causal OI effect, and not OOS validation.
`MARKET_02_TEST_CALIBRATED` remains `NO`.

No rerun is authorized.
