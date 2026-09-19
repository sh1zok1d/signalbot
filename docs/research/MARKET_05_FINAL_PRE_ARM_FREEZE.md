# MARKET-05 — FINAL PRE-ARM IMPLEMENTATION FREEZE

- **Status:** `MARKET_05_FINAL_PRE_ARM_IMPLEMENTATION_FROZEN`
- **Unit ID:** `MARKET_05_FINAL_PRE_ARM_IMPLEMENTATION_FREEZE`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** `MARKET_05_FINAL_PRE_ARM_FREEZE.json`

This freeze makes the already-preregistered MARKET-05 experiment
**actually executable once**. It does not ARM, execute, or inspect
scientific outcomes.

## 1. Prior audit, recorded honestly

```text
PRE_REPAIR_HEAD     = da66716ac4fc273db2cce2156042b2edeeb37491
PRE_REPAIR_TREE     = 69d03914f3ababb81cbcaa4cf84546ce4266ac2f
PRE_REPAIR_VERDICT  = MARKET_05_DO_NOT_ARM
```

Independent read-only red-team at that head found production blockers
F1–F10. This freeze repairs those blockers without changing preregistered
mathematics, hypothesis parameters, or promotion gates.

## 2. Frozen science, unchanged

```text
PREREG_CHANGED          = NO
SCIENTIFIC_MATH_CHANGED = NO

DECISION_TIME = 00:00 UTC
FEATURE_LOOKBACK = 24h
OUTCOME_HORIZON = 24h
ETH_CONFIRMATION = BTC_SIDE * Z_ETH
PRIMARY_OUTCOME = BTC_DIRECTION_ALIGNED_MAE_24H
BASELINE = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H
CANDIDATE = Y ~ BTC_SIDE + ABS_Z_BTC + RV_BTC_24H + ETH_CONFIRMATION
MODEL = OLS
MATERIALITY = 0.02
BOOTSTRAP = CIRCULAR_MOVING_BLOCK
BLOCK_LENGTH = 14
REPLICATES = 5000
SEED = 2026091905
PREDICTIVE_BOOTSTRAP_REFIT = false
COEFFICIENT_BOOTSTRAP_REFIT = true
```

## 3. Claim-before-outcomes one-shot

```text
PRE-FLIGHT
  -> ATOMIC EXECUTION CLAIM   (O_CREAT|O_EXCL + fsync file + fsync dir)
  -> load outcomes
  -> evaluate
  -> write canonical RESULT JSON (tmp + fsync + rename + fsync dir)
  -> optional MD render of that JSON
```

Creating `docs/research/MARKET_05_EXECUTION_CLAIM.json` **is** scientific
consumption (`CANONICAL_EXECUTIONS_CONSUMED = 1`). Crash after claim:
**NO RERUN**. Incomplete RESULT is an integrity state
(`MARKET_05_INCOMPLETE_EXECUTION`), never fabricated `NO_EVIDENCE` or
`PROMOTED`. RESULT presence does not block post-claim finalization;
pre-claim authorization and post-claim completion are separate.

Protocol: `MARKET_05_ATOMIC_O_EXCL_CLAIM_V1`.

## 4. Data bindings

```text
BTC_DATASET  = CORE_BTC_BINANCE_V0
BTC_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
ETH_DATASET  = CORE_ETH_BINANCE_V0
ETH_SNAPSHOT = 4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15
ETH_EXECUTION_DATA_ID = b5c6228a2c4214b641cd10fda87010c2898040e3fc53cdacee9211e028752484
```

Development requires the exact 60 monthly 1m objects covering
2020-01 through 2024-12. Missing one object is
`MARKET_05_INCOMPLETE_EXECUTION`. 2025/2026 objects are never parsed.
ETH execution parquet is bound by
`docs/research_data/CORE_ETH_BINANCE_V0/MARKET_05_EXECUTION_BINDING.json`
to the original accepted ZIP SHA256 values. Production loader reads
`open_time_ms`, `high`, `low`, `close`.

## 5. Runtime and RESULT

```text
NUMPY_VERSION_REQUIRED   = 2.1.3
PYARROW_VERSION_REQUIRED = 17.0.0
RESULT_SCHEMA_IDENTITY   = market_05_cross_asset_result/1.2.0
```

Canonical RESULT JSON is scientific evidence. MD is a rendering of that
JSON. Partial MD after durable JSON does not authorize rerun.

## 6. Executable vs documentary authority

`MARKET_05_ARM_SEMANTIC_CONTRACT.json` is the non-self-referential
semantic payload. `ARM_SEMANTIC_CONTRACT_SHA256` is bound into
`RUN_IDENTITY` and authenticated at runtime.

`MARKET_05_ARM_CONTRACT.{md,json}` is a **documentary mirror** of the
prior freeze. Production code + `RUN_IDENTITY` are executable authority.

## 7. Current state — still unarmed

```text
ARMED                           = false
EXECUTION_AUTHORIZED            = false
CANONICAL_EXECUTIONS_AUTHORIZED = 0
CANONICAL_EXECUTIONS_CONSUMED   = 0
REAL_ARM_CREATED                = false
RESULT_CREATED                  = false
SCIENTIFIC_OUTCOMES_INSPECTED   = false
PROTECTED_OOS_TOUCHED           = false
NEXT_UNIT                       = INDEPENDENT_FINAL_MARKET_05_PRE_ARM_RED_TEAM
```

Exact `RUN_IDENTITY`, implementation hashes, and scientific
implementation commit/tree are in the JSON twin. The scientific
implementation HEAD is filled after the scientific repair commit; a
later documentation-only commit may record `authority_root_head` and is
never presented as the scientific implementation commit.
