# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — implementation freeze

- **Status:** `IMPLEMENTATION_FROZEN`
- **Unit ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Date:** 2026-09-18

**Not a RESULT. Not MARKET-02 execution. Not outcome inspection.
Not an ARM. Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document freezes the independently reviewed MARKET-02
implementation identity. Canonical machine-readable twin:
`docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_IMPLEMENTATION_FREEZE.json`.

Outcome-blind pre-freeze red-team verdict:
`A. READY_FOR_IMPLEMENTATION_FREEZE`.

This freeze commit is a docs/test-invariant descendant of the reviewed
scientific implementation. It does **not** claim that this freeze HEAD
itself was the code HEAD independently reviewed. Scientific lib bytes
must remain the reviewed SHA256 below.

```text
REVIEWED_IMPLEMENTATION_HEAD = 1d2b0abf73d245f37cd9ca55ece99d1628dc80ee
REVIEWED_IMPLEMENTATION_TREE = 9e18ccf690e280bbd4b033f4a44f3b0700a5bedb
IMPLEMENTATION_REVIEW_VERDICT = READY_FOR_IMPLEMENTATION_FREEZE

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

Added in this freeze unit only: freeze records, documentation status,
and a chronological-order invariant test that the canonical
`evaluate_market_02` path supplies confirmatory rows sorted by
`(decision_T_ms, impulse_start_ms)` before bootstrap evaluation.
`evaluate_from_confirmatory_rows` is not redesigned. No scientific
transformation was added.

```text
PREREG_FROZEN                 = YES
IMPLEMENTATION_COMPLETE       = YES
IMPLEMENTATION_FROZEN         = YES
ARMED                         = NO
CANONICAL_EXECUTIONS_CONSUMED = 0
REAL_MARKET_02_OUTCOME_INSPECTION = NO
BOUND_MARKET_02_EXECUTION     = NO
PROTECTED_OOS_TOUCHED         = NO
MARKET_02_TEST_CALIBRATED     = NO
```

---

## Frozen prereg authority (unchanged; files not modified)

```text
PREREG_MD   SHA256 = 4f19fd27435adddf4cc7e3c5568a8e316d8865b64468cdc30a9fd3918ffc3275
PREREG_JSON SHA256 = ffc11ffd0f9d76ca12542ce45f466a6a7f9c651f1a030168a1617af2caa545a7

PREREG_MD_FREEZE_HEAD   = 0f332d3cfd848d95c2fbe5de7f86dfe7aa631540
PREREG_JSON_TWIN_HEAD   = aebdb9570f08c7a05149336d90f6fcd11541d10d
```

MD is the complete scientific authority. JSON never overrides MD.

---

## Frozen scientific implementation identity

Accepted scientific `lib.py` at reviewed HEAD:

```text
scripts/research/market_02_oi_expansion_price_confirmation_lib.py
  reviewed git_blob = bee32e3feb748e122d2469e95be645c5881400d0
  reviewed SHA256   = 51638796db235a999bd1a12d44a57aace9e21f4b0cfffeea14bdabaf3eac7ea6
  reviewed size     = 38441
```

Those bytes must remain unchanged by this freeze.

---

## Seed authority (historical JSON numeric discrepancy)

Already-frozen prereg artifacts disagree on the JSON number encoding of
the bootstrap seed. Neither prereg file is modified by this freeze.

```text
MD authoritative seed     = 1852983754304692007
JSON twin stored numeric  = 1852983754304692000
seed_material_sha256      =
  19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f
int(first 16 hex, 16)     = 1852983754304692007
```

Disposition:

- the discrepancy exists in already-frozen prereg artifacts
- it is a historical documentation/representation (IEEE/JSON number)
  discrepancy, not a second scientific seed
- no silent prereg repair occurred
- implementation uses the MD-authoritative seed `1852983754304692007`
  via `pcg64_generator(namespace_seed(MARKET_02_BOOTSTRAP_SEED,
  "BOOTSTRAP", "PRIMARY_BETA_CONFIRMATION"))`
- JSON never overrides MD; that authority rule is frozen from this point

---

## Transitive scientific dependencies (unchanged)

```text
FAST PRECOMPUTE
  scripts/research/market_01_episode_construction_fast.py
  SHA256 = ddcabb999c2ea033a674ee84a484333802d3f863ab012c6784eb1784af2640ef
  reuse = rolling primitives only; not MARKET-01 EpisodeRecord semantics

MARKET-01 LIB PRIMITIVES (clocks/OI/impulse/stratum; not estimand)
  scripts/research/market_01_oi_expansion_weak_continuation_lib.py
  SHA256 = 9a8f46b39114558d38ae61600cb632fb963c7751d37e7699c4f155d91126dc09

PRE_VOL_60
  scripts/research/b2_03_impulse_morphology_lib.py
  SHA256 = 6da1e590f83edab09247b8d238e410ef7ce4333f4f20ef0d8d1ad205391eb6ce

RNG
  scripts/research/harness_synthetic_edge_calibration_v1_lib.py
  SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51

STATIONARY BLOCK SELECTOR (algorithm identity only)
  scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py
  SHA256 = 38a494917dcf721b828a7c3f885d4c60ab6df437003abc0c71e510e33b4b0505
  function SHA256 = 66ed0ea015b773f8e469a470ddcd0e648806803249c93de14211ff6b8a4782b1
  not V3 DETECTED; not MARKET-02 calibration

arch==8.0.0
  arch/bootstrap/base.py
  SHA256 = 104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21
```

MARKET-01 frozen RESULT/prereg/scientific bytes remain untouched.

---

## Data authority (bound, not executed)

```text
PRICE  CORE_BTC_BINANCE_V0
       snapshot 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
OI     Vision daily/metrics/BTCUSDT sum_open_interest
       snapshot 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
COMMON [2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

No funding. No B2-06 execution. No protected OOS. Bound snapshots remain
refused until a separate ARM.

---

## Canonical ordering invariant

Canonical path:

```text
construct_episodes -> confirmatory_rows -> evaluate_from_confirmatory_rows
```

`confirmatory_rows` sorts by `(decision_T_ms, impulse_start_ms)` before
the confirmatory bootstrap. This freeze does not change that function
and does not redesign the row API.

---

## Interpretation constraints (frozen with the implementation)

These constraints were identified by the outcome-blind pre-freeze review.
They do not change the estimand, threshold, bootstrap, or decision rule.

### 1. Pooled estimand

The primary `beta_confirmation` is a pooled within-stratum contrast.

A DETECTED result does **not** imply:

- positive effect in every stratum
- monotonic confirmation/continuation relation
- universal validity of threshold 0.25

### 2. Bootstrap limitation

The stationary bootstrap resamples the chronological filtered
confirmatory episode sequence. It does not establish known operating
characteristics under realistic market regime/calendar dependence.

`MARKET_02_TEST_CALIBRATED = NO`.

A future p-value must not be described as a calibrated real-market
false-positive probability.

### 3. Program-level interpretation

MARKET-02 is one preregistered experiment in a sequential research
program after sealed MARKET-01 `NO_EVIDENCE`.

A future DETECTED result must not be described as:

- validated Signalbot alpha
- independent replication of MARKET-01
- rescue/reclassification of MARKET-01
- program-level discovery

### 4. Temporal persistence

LOEO/concentration robustness is DETECTED-only and downgrade-only.

Passing robustness does **not** establish:

- current edge
- persistent edge
- production validity
- untouched OOS confirmation

### 5. Exact allowed DETECTED claim

Within the preregistered occupancy-thinned population of
qualifying-impulse AND OI-expansion episodes satisfying the frozen
completeness/support rules, `continuation_ratio > 0.25` versus `<= 0.25`
is tested as a pooled within-stratum contrast in direction-adjusted
subsequent 60m continuation under the frozen OLS/bootstrap procedure.

DETECTED is only the mechanical result of that frozen test.

It is a relationship-study result and the MARKET-02 test is uncalibrated.

---

## Lifecycle

```text
MARKET_02_ARMED = NO
MARKET_02_EXECUTED = NO
next = MARKET_02_ARM_IF_AUTHORIZED
```

This freeze does not ARM or execute MARKET-02.
