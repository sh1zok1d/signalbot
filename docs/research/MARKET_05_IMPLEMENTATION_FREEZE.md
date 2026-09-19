# MARKET-05 implementation freeze

- **Status:** `IMPLEMENTATION_FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET_05_CROSS_ASSET_IMPLEMENTATION_FREEZE`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Short name:** `MARKET-05`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_05_IMPLEMENTATION_FREEZE.json`](MARKET_05_IMPLEMENTATION_FREEZE.json)
- **Bound prereg:** [`MARKET_05_CROSS_ASSET_PREREG.md`](MARKET_05_CROSS_ASSET_PREREG.md)

This unit freezes the exact executable rendering of the MARKET-05
preregistration. It does **not** ARM, execute, create RESULT, or inspect
scientific outcomes on real development rows.

```text
FULL_PREREGISTRATION_FROZEN = true
IMPLEMENTATION_FROZEN = true
ARMED = false
EXECUTION_AUTHORIZED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
PROTECTED_OOS_TOUCHED = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
MARKET_05_TEST_CALIBRATED = NO
RESULT_CREATED = false
ARM_CREATED = false
```

Bound authority:

```text
PRE_IMPLEMENTATION_HEAD = 5b2a582cd3c42af7114ded7fe61ac7c9f39c9dd5
PRE_IMPLEMENTATION_TREE = c5f949ce158a43078da4828e85db986db4f6ae5b
PREREG_MD_SHA256 = 31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e
PREREG_JSON_SHA256 = f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25
```

This freeze commit is a docs/authority descendant of the reviewed
implementation. Freeze commit identifiers are filled by the commit that
adds this file.

```text
IMPLEMENTATION_HEAD = UNSET_UNTIL_THIS_COMMIT
IMPLEMENTATION_TREE = UNSET_UNTIL_THIS_COMMIT
```

---

## Frozen scientific constants

```text
DECISION_TIME = 00:00:00 UTC
DECISION_FREQUENCY = DAILY
FEATURE_LOOKBACK = 24 hours
OUTCOME_HORIZON = 24 hours
ETH_CONFIRMATION = BTC_SIDE * Z_ETH
PRIMARY_OUTCOME = BTC_DIRECTION_ALIGNED_MAE_24H
BASELINE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H
CANDIDATE_MODEL = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION
MODEL = OLS
MATERIALITY = 0.02
BOOTSTRAP_KIND = CIRCULAR_MOVING_BLOCK
BLOCK_LENGTH = 14
BOOTSTRAP_REPLICATES = 5000
RANDOM_SEED = 2026091905
CI = 2.5th / 97.5th percentiles
PREDICTIVE_BOOTSTRAP_REFIT = false
COEFFICIENT_BOOTSTRAP_REFIT = true
```

RNG: local `SplitMix64` seeded by `RANDOM_SEED`. Block starts are
`next_u64() % n`. Blocks wrap end -> beginning. The final block is
truncated so replicate length equals the original sample length.
Reproducibility is not delegated to implicit library/global RNG state.

Invalid coefficient-bootstrap replicate (rank deficiency, zero training
sd, non-finite design, ETH_CONFIRMATION collinearity) is
`MARKET_05_INCOMPLETE_EXECUTION`. Replicates are never silently dropped.
Prereg does not authorize changing the effective bootstrap distribution
by discarding invalid replicates.

---

## Data authorities

```text
BTC_DATASET = CORE_BTC_BINANCE_V0
BTC_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
ETH_DATASET = CORE_ETH_BINANCE_V0
ETH_SNAPSHOT = 4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15
ETH_DATASET_ACCEPTED = true
ETH_INVENTORY_SHA256 = 033a06428d5d2a56fcde23a8fe64ebe4d8afa2f57d5d3263e3d0b9c6db38e49e
```

ETH companion rematerialization verified 104/104 bound Vision checksums,
3,497,760 1m rows, 0 missing, 0 duplicates, first open
`2020-01-01T00:00:00Z`, last open `2026-08-25T23:59:00Z`, bar-end-exclusive.
Development-window timestamp coverage `[2020-01-01T00:00:00Z, 2025-01-01T00:00:00Z)`
is complete (2,630,880 rows). Snapshot identity hashes verified ZIP bytes
plus timestamp coverage. Price values are not retained in the snapshot
payload. Protected 2025/2026 timestamps were audited for
coverage/order/duplicates only. Scientific OHLC evaluation of those
values was not performed. CORE BTC is not redefined.

---

## Implementation files

```text
scripts/research/market05_cross_asset_lib.py
  SHA256 = 7599e6267b52a22c51fdd100dd2a214c2de992cf2cc2e6cd6a6f3e2a5ea02631
scripts/research/market05_cross_asset_authority.py
  SHA256 = 25005aefb69e2a87556604492e210632893e4dc8028edb254b8165624b131957
scripts/research/market05_cross_asset.py
  SHA256 = 1a587d58c970e99c5db49478f89cfb5f040537658ff8034af403fa378f0a997c
scripts/research/market05_cross_asset_data.py
  SHA256 = 0eb94fcf531b81fe85073a04b498d5fdfd704d3349320f9a0d66a0269167adc7
scripts/research/core_eth_binance_v0_acceptor_lib.py
  SHA256 = 6f86ae1ed08fe7595a0de3eb4e0c273aa2850a8238675d72696bbd088c118764
scripts/research/core_eth_binance_v0_acceptor.py
  SHA256 = 1f550909800b5bfd0edcf5cf6efda9689460dd9c16e69d9915a662192ca88292
```

Tests:

```text
tests/research/test_market05_cross_asset_implementation.py
  SHA256 = 5fce5e0d090cc3b1d8c226e36935e8351e98a3911c03d79ca516a842ad84f293
tests/research/test_market05_cross_asset_bootstrap.py
  SHA256 = eff31e9c4453d4574c046c85ced5ac007db5a77583f5f390f2e45e152f1c495f
tests/research/test_market05_cross_asset_execution_gate.py
  SHA256 = 1301368cb2031033689aea4d24a63e3b7223205ccaa79c1511d082f2ca6243b0
```

---

## Authorization barrier

Scientific execution requires a later ARM artifact. Before ARM:

- `pytest`, `compileall`, module import, and CLI `--help` cannot execute
  MARKET-05 science;
- production CLI refuses with `MARKET_05_EXECUTION_NOT_AUTHORIZED`;
- real development outcome-row loading is refused **before** outcome bars
  are read;
- scientific RESULT instantiation is forbidden.

Protected `[2025-01-01T00:00:00Z, onward)` scientific parse is always
forbidden for development execution. A source containing 2025 timestamps
is rejected as a whole; values are not surfaced to evaluator logic.

Same-support: one eligible-row mask. Missing ETH, missing BTC feature
minute, missing BTC outcome minute, missing prefix, or duplicate minute
invalidates the row for BOTH models.

Training-only standardization: mean/sd from the training partition of
each fold only. INTERCEPT and BTC_SIDE are not standardized.

---

## No-outcome attestation

This unit did not produce from real BTC/ETH 2020-2024 data:

- Y_T;
- BTC_DIRECTION_ALIGNED_MAE_24H associations;
- ETH_CONFIRMATION / outcome associations;
- fitted scientific coefficients;
- BETA_ETH_CONFIRMATION;
- fold predictions;
- baseline/candidate MAE;
- relative MAE improvement;
- yearly improvement;
- bootstrap scientific distributions;
- confidence intervals;
- promotion gates;
- final scientific classification.

No `MARKET_05_ARM.*` and no `MARKET_05_RESULT.*` exist.

---

## Implementation audit answers

1. Can any ordinary test/import command trigger scientific execution? **NO**
2. Can evaluator read protected OOS? **NO**
3. Is baseline support exactly candidate support? **YES** (same-support mask; invalid path **NO**)
4. Can missing ETH selectively remove candidate rows only? **NO**
5. Can test-fold values affect training standardization? **NO**
6. Can bootstrap randomness vary between runs? **NO**
7. Can classification be promoted with materiality <2%? **NO**
8. Can 1/3 positive years pass temporal gate? **NO**
9. Can one year exactly -2% pass? **NO**
10. Can predictive bootstrap refit models accidentally? **NO**
11. Can coefficient bootstrap avoid refit accidentally? **NO**
12. Can real-data outcomes be produced before ARM? **NO**

---

## Lifecycle

```text
NEXT_UNIT = OUTCOME_BLIND_MARKET_05_IMPLEMENTATION_RED_TEAM_AUDIT
```

Do not ARM. Do not execute. Do not inspect scientific outcomes.
