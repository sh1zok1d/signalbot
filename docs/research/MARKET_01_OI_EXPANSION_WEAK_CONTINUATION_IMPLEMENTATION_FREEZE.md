# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — implementation freeze

- **Status:** `IMPLEMENTATION_FROZEN`
- **Unit ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Date:** 2026-09-17

**Not a RESULT. Not MARKET-01 execution. Not outcome inspection.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document freezes the independently accepted MARKET-01
implementation identity so that exactly one later canonical execution
can be armed against those bytes. Canonical machine-readable twin:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.json`.

This freeze commit is a docs/authority-plumbing descendant of the
reviewed implementation. It does **not** claim that this freeze HEAD
itself was the code HEAD independently reviewed.

```text
REVIEWED_IMPLEMENTATION_HEAD = 1019c5725a58c62d460276159a5683a202c1c3ea
REVIEWED_IMPLEMENTATION_TREE = 2a7a5ce74f9b0c419cf40093271df243ffb02d46
IMPLEMENTATION_REVIEW_VERDICT = IMPLEMENTATION_ACCEPTED

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

ARM plumbing in this same unit may change only bound-execution
authentication. Scientific episode construction, overlap, clocks,
thresholds, PRE_VOL_60, strata, OLS, bootstrap, robustness, and
classification are not rewritten.

---

## Frozen prereg / prereg-freeze authority (unchanged)

```text
PREREG_MD   SHA256 = d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866
PREREG_JSON SHA256 = 6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4
FREEZE_MD   SHA256 = e0e0da9e22ebed9a9663e3c5f973237e3231e991f13227378288779e6ea07fe4
FREEZE_JSON SHA256 = 902863878acd2897c9dacdee6fae068ee17f87f6e10893d3c756b1f49b488176

PREREG_FREEZE_HEAD = 8fa0d361d137271754909034026f42d4dfdfc00a
PREREG_FREEZE_TREE = acde57e3cf4c17c9888016ff96928be2822e1866
```

---

## Frozen implementation identity

Accepted scientific `lib.py` at reviewed HEAD:

```text
scripts/research/market_01_oi_expansion_weak_continuation_lib.py
  reviewed git_blob = 44a7cca7db612406430857278159834c5fe40722
  reviewed SHA256   = ad81bc279b381285e81deca6cd78bdd40673b203ea8aa8f8190b1507e33a424a
  reviewed size     = 33175
```

Armed-lifecycle descendant of that file (gate/flags only):

```text
armed SHA256 = 9a8f46b39114558d38ae61600cb632fb963c7751d37e7699c4f155d91126dc09
armed size   = 33797
```

Reviewed authority helper at accepted HEAD:

```text
scripts/research/market_01_oi_expansion_weak_continuation_authority.py
  git_blob = 37b1dc92cbee99d035f5007509ad6c8d9fffab5b
  SHA256   = af8fc88d6d274badbf7deca3a2c388bfbcbd16e03028bae4113e742d00ffa216
  size     = 3635
```

---

## Transitive scientific dependencies

```text
PRE_VOL_60
  scripts/research/b2_03_impulse_morphology_lib.py
  SHA256 = 6da1e590f83edab09247b8d238e410ef7ce4333f4f20ef0d8d1ad205391eb6ce

RNG
  scripts/research/harness_synthetic_edge_calibration_v1_lib.py
  SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
  functions = namespace_seed, pcg64_generator

STATIONARY BLOCK SELECTOR (algorithm identity only)
  scripts/research/harness_synthetic_edge_calibration_v3_confirmatory.py
  SHA256 = 38a494917dcf721b828a7c3f885d4c60ab6df437003abc0c71e510e33b4b0505
  function = optimal_stationary_block_length
  function SHA256 = 66ed0ea015b773f8e469a470ddcd0e648806803249c93de14211ff6b8a4782b1
  not V3 DETECTED; not Clark-West

arch==8.0.0
  arch/bootstrap/base.py
  SHA256 = 104d3552a8e79a801e2f8cd0401160f83a7263b4ff13da44a82d763e5664fd21
```

---

## Data authority

```text
PRICE  CORE_BTC_BINANCE_V0
       snapshot 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
OI     Vision daily/metrics/BTCUSDT sum_open_interest
       snapshot 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
COMMON [2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

No funding. No B2-06 execution. No protected OOS.

---

## Bootstrap identity

```text
seed_material = MARKET-01_OI_EXPANSION_WEAK_CONTINUATION|CONFIRMATORY_STATIONARY_BOOTSTRAP|B=999
seed_material_sha256 = a960350293eacee83f5cfcb21e138f5f4dbbea1af4547d298e5a1da2ec571dbe
MARKET_01_BOOTSTRAP_SEED = 12204813275361890024
B = 999
alpha = 0.05
```

---

## Preserved limitations

```text
MARKET_01_TEST_CALIBRATED = NO
v3_reused_as_market_01_test = NO
DEFAULT_V4 = NO
B2_06_EXECUTION_AUTHORIZED = NO
PROTECTED_OOS_TOUCHED = NO
MARKET_01_EXECUTED = NO
MARKET_01_OUTCOME_INSPECTED = NO
```

This freeze does not execute MARKET-01.
