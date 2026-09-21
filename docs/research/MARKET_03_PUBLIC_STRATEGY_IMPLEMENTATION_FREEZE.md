# MARKET-03 PUBLIC STRATEGY IMPLEMENTATION FREEZE

- **Status:** `IMPLEMENTATION_FROZEN`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE`
- **Date:** 2026-09-18
- **Machine-readable twin:** `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.json`

**Not a RESULT. Not an ARM. Not MARKET-03 execution. Not outcome
inspection. Not parameter search. Not prereg or data modification.**

This document freezes the independently re-reviewed MARKET-03 LEVEL_2
implementation identity so that a later ARM can bind exactly these
bytes. It does **not** modify the scientific implementation files,
prereg bytes, spot snapshot, or funding snapshot.

This freeze commit is a docs/test descendant of the reviewed
implementation. It does **not** claim that this freeze HEAD itself was
the code HEAD independently reviewed.

```text
FROZEN_IMPLEMENTATION_HEAD = 03411aaa1a2f938169f07f8f3576f17227a2b14b
FROZEN_IMPLEMENTATION_TREE = 87a1da250a56343c44625e3f5187a6877035d1da
RE_REVIEW_HEAD             = 03411aaa1a2f938169f07f8f3576f17227a2b14b
RE_REVIEW_TREE             = 87a1da250a56343c44625e3f5187a6877035d1da
RE_REVIEW_VERDICT          = READY_FOR_IMPLEMENTATION_FREEZE

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT

IMPLEMENTATION_FROZEN                = YES
MARKET_03_ARMED                      = NO
CANONICAL_EXECUTIONS_AUTHORIZED      = 0
CANONICAL_EXECUTIONS_CONSUMED        = 0
MARKET_03_STRATEGY_EXECUTED          = NO
MARKET_03_OUTCOMES_INSPECTED         = NO
MARKET_03_PARAMETER_SEARCH           = NO
PROTECTED_OOS_TOUCHED                = NO
```

The freeze commit's `FREEZE_COMMIT_HEAD` / `FREEZE_COMMIT_TREE` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact never depends on a circular
self-hash of its own freeze-commit digest.

Scientific `scripts/research/market_03_public_strategy_{lib,authority,execute}.py`
are **not** rewritten by this unit. The reviewed `authority.py` still
contains `IMPLEMENTATION_FROZEN = False` as the unarmed code identity.
Changing that flag would change the frozen SHA256 and invalidate this
freeze. ARM must later bind **this** freeze identity.

---

## Frozen prereg (unchanged)

```text
PREREG_MD_SHA256   = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
PREREG_MD_SIZE     = 15063
PREREG_JSON_SIZE   = 15587
PREREG_FREEZE      = docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.md
```

---

## Frozen scientific implementation

Independently recomputed from working-tree bytes immediately before
this freeze. Must equal reviewed HEAD `03411aaa…` / tree `87a1da25…`.

```text
scripts/research/market_03_public_strategy_lib.py
  SHA256   = 46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5
  git_blob = 979f9e735163cf53a265a4e8c3dc93ba37f8b20e
  size     = 38012

scripts/research/market_03_public_strategy_authority.py
  SHA256   = 97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4
  git_blob = bb922ee9755e911dabf6ead1250ea1295ffa162e
  size     = 13235

scripts/research/market_03_public_strategy_execute.py
  SHA256   = 90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf
  git_blob = 7d04ae75651060c52bea8e7ae848c6f97b6233dd
  size     = 1292
```

Any later change to these bytes invalidates this implementation freeze
and requires explicit re-review / re-freeze.

---

## External source

```text
EXTERNAL_REPO     = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_COMMIT   = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE     = f7717e681c911ea3ccce15492246053cf15883cb
REPLICATION_LEVEL = LEVEL_2_FAITHFUL_REIMPLEMENTATION
FAMILY            = EmaCross vs EmaCrossFunding
```

---

## Data authorities

```text
SPOT_DATASET_ID     = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT_SNAPSHOT_ID    = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256    = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4

FUNDING_DATASET_ID  = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
FUNDING_SNAPSHOT_ID = d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256 = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb

B2-06 is not MARKET-03 funding authority.
```

---

## Temporal identity

```text
WARMUP_INTERVAL     = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
PROTECTED_OOS       = [2025-01-01T00:00:00Z, inf)  inaccessible
```

---

## Primary scientific rule

Authoritative MDD is the signed `metrics.py` ratio `float(dd.min())`
on daily wallet equity.

```text
REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline)
                         and (MDD_filtered > MDD_baseline)
```

Magnitude fidelity is descriptive only. No p-value, bootstrap,
parameter search, or alternative promotion criterion.

```text
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

---

## Bound targeted re-review

```text
RE_REVIEW_HEAD = 03411aaa1a2f938169f07f8f3576f17227a2b14b
RE_REVIEW_TREE = 87a1da250a56343c44625e3f5187a6877035d1da
VERDICT        = READY_FOR_IMPLEMENTATION_FREEZE

F1_CLOSED = YES
F2_CLOSED = YES
F3_CLOSED = YES
F5_CLOSED = YES

F1_REPRODUCIBLE_AFTER_REPAIR         = NO
F2_PREWARMUP_INFLUENCE_AFTER_REPAIR  = NO
F3_WALLET_MATCH                      = YES
F5_CANONICAL_AUTHORITY_FAIL_CLOSED   = YES

FUNDING_ALIGNMENT_MATCH    = YES
FUNDING_PERCENTILE_MATCH   = YES
SIGNAL_TIMING_MATCH        = YES
STOPLOSS_MATCH             = YES
TRAILING_STOP_MATCH        = YES
FEE_ACCOUNTING_MATCH       = YES
MDD_MATCH                  = YES
BASELINE_FILTER_ISOLATION  = YES

EXACT_DIFFERENTIAL_TESTS = PARTIAL
```

Do not upgrade `PARTIAL` to `YES`.

---

## Test status at freeze

```text
compileall                         = PASS
focused MARKET-03 suite at review  = 98 passed
git diff --check                   = PASS
FULL_PYTEST_AT_REVIEW              = NOT_COMPLETED
```

`FULL_PYTEST_AT_REVIEW = NOT_COMPLETED` is not rewritten as PASS.

---

## Post-freeze immutability

Any change to prereg scientific bytes, scientific implementation
bytes, external source identity, spot authority, funding authority,
or temporal identity invalidates this freeze and requires explicit
re-review / re-freeze.

ARM must later bind this exact frozen identity. This freeze does not
authorize canonical execution.

---

## Next (not this unit)

ARM, then at most one canonical execution. This unit authorizes
neither.
