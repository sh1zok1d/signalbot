# MARKET-03 PUBLIC STRATEGY — one-shot canonical ARM

- **Status:** `ARMED` / `ARMED_UNUSED`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_ARM`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Date:** 2026-09-19

**Not a RESULT. Not MARKET-03 execution. Not outcome inspection. Not
parameter search. Not prereg, implementation, or data modification.**

Canonical machine-readable twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_ARM.json`.

One-shot reservation twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_RESERVATION.json`.

This ARM authorizes **exactly one** future canonical MARKET-03
execution. The reservation is unused. This unit does **not** consume
it. A later canonical execution must atomically transition
`authorized=1, consumed=0` → `authorized=1, consumed=1` before or as
part of outcome-producing evaluation. A second canonical execution
under this authorization must fail. No replacement reservation is
pre-authorized.

Lifecycle authority lives **outside** the frozen scientific bytes.
Reviewed `scripts/research/market_03_public_strategy_{lib,authority,execute}.py`
remain byte-identical to the implementation freeze. The frozen
`authority.py` still reports `MARKET_03_ARMED = False` as the unarmed
code identity.

```text
PRE_ARM_HEAD = 60c3e3054cd35652d0a4276349ad418967241cc0
PRE_ARM_TREE = c51d068f3bbd0560ee4bc40c3fcb8b96eb7a43a1

FROZEN_IMPLEMENTATION_HEAD = 03411aaa1a2f938169f07f8f3576f17227a2b14b
FROZEN_IMPLEMENTATION_TREE = 87a1da250a56343c44625e3f5187a6877035d1da

RUN_IDENTITY = f68b6de7d6c127f67908c48bf4be73cf986ea5d9daf9257bdae07f9ac626f397

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT

IMPLEMENTATION_FROZEN                = YES
MARKET_03_ARMED                      = YES
CANONICAL_EXECUTIONS_AUTHORIZED      = 1
CANONICAL_EXECUTIONS_CONSUMED        = 0
MARKET_03_STRATEGY_EXECUTED          = NO
MARKET_03_OUTCOMES_INSPECTED         = NO
MARKET_03_PARAMETER_SEARCH           = NO
PROTECTED_OOS_TOUCHED                = NO
```

`RUN_IDENTITY` is `sha256(canonical_json_bytes(scientific_run_identity_payload))`
with `sort_keys=True`, `indent=2`, `ensure_ascii=False`, trailing
newline. No timestamp or random nonce enters the payload.

```text
ARM_JSON_SHA256         = 7c801cdc713d2b2a58c35f4b28a1cd8b6d464b7e06dace1c374ed46ef6a3075c
RESERVATION_JSON_SHA256 = ebc4338acb308d544967558ff1fdf8b7d22740616d139de82b1b7912db60ef9f
```

`ARM_MD_SHA256` is computed from these sealed markdown bytes and bound
in the ARM authority module. It is not written into this file.

---

## Bound authorities

```text
PREREG_MD_SHA256   = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89

IMPLEMENTATION_FREEZE_MD_SHA256   = 5007575f5fa9d6860465341e5bf3f2fa0239e18f3290c35a55da4960d56ebc2f
IMPLEMENTATION_FREEZE_JSON_SHA256 = ff5d53108219aa679463ac8fae8aa334eaf52f0c15d080831f319b2079c05068

LIB_SHA256       = 46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5
AUTHORITY_SHA256 = 97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4
EXECUTE_SHA256   = 90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf

EXTERNAL_REPO   = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_COMMIT = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE   = f7717e681c911ea3ccce15492246053cf15883cb
REPLICATION_LEVEL = LEVEL_2_FAITHFUL_REIMPLEMENTATION

SPOT_DATASET_ID     = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT_SNAPSHOT_ID    = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256    = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4

FUNDING_DATASET_ID  = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
FUNDING_SNAPSHOT_ID = d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256 = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb

WARMUP_INTERVAL     = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
PROTECTED_OOS       = [2025-01-01T00:00:00Z, inf)  inaccessible

PRIMARY_RULE =
  REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline)
                           and (MDD_filtered > MDD_baseline)

MDD is signed negative. Magnitude fidelity is descriptive only.
No alternative success criterion may be introduced after ARM.

REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN

B2-06 is not MARKET-03 funding authority.
```

---

## Single-use rule

```text
CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED   = 0
one_shot                        = YES
rerun_preauthorized             = NO
replacement_reservation_preauthorized = NO
```

Future canonical execution must verify, in this order:

1. exact frozen scientific bytes
2. exact prereg bytes
3. exact implementation freeze bytes
4. exact ARM bytes
5. exact `RUN_IDENTITY`
6. exact spot and funding authorities
7. `authorized=1` and `consumed=0`
8. protected 2025/2026 OOS remains rejected
9. only then may the frozen scientific functions run

This ARM unit does not load bound spot or funding rows into strategy
logic, create trades, calculate wallet paths or MDD, compare
baseline/filtered, or create a RESULT.

---

## Claim boundaries

If later execution returns `REPRODUCED_DIRECTION`, the only allowed
claim is the frozen LEVEL_2 historical-reproduction statement over the
frozen interval under the explicit `fundingTime` assumption.

That result would **not** authorize claims of current alpha, live
profitability, causal funding effect, independent replication, OOS
confirmation, validation of the author's 42-strategy search, calibrated
statistical evidence, or proven funding publication timing.

If later execution returns `NOT_REPRODUCED_DIRECTION`, the only allowed
claim is that this frozen LEVEL_2 reimplementation did not reproduce
the published drawdown-reduction direction. That would **not** authorize
"funding does not work" or "funding filters do not work."

---

## Next (not this unit)

Exactly one canonical MARKET-03 execution. This unit does not execute
it and does not consume the reservation.
