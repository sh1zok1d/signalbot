# MARKET-05 CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK — ARM CONTRACT

- **Status:** `ARM_CONTRACT_DOCUMENTARY_MIRROR`
- **Unit ID:** `MARKET_05_CROSS_ASSET_ARM_CONTRACT`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** `MARKET_05_ARM_CONTRACT.json`

**This document is NOT an ARM. It authorizes nothing.**

**Executable authority is not this file.** Runtime authorization is
production code + independently recomputed `RUN_IDENTITY` +
`docs/research/MARKET_05_ARM_SEMANTIC_CONTRACT.json`
(`ARM_SEMANTIC_CONTRACT_SHA256`). Hash maps in this document describe
the prior freeze at scientific implementation `46a7f6e0…` and are **not**
re-checked at runtime. Do not treat this markdown or its JSON twin as
stronger than the live `RUN_IDENTITY` payload.

No ARM artifact exists; `ARMED = false`, `EXECUTION_AUTHORIZED = false`,
`CANONICAL_EXECUTIONS_AUTHORIZED = 0`.

Current executable freeze: `docs/research/MARKET_05_FINAL_PRE_ARM_FREEZE.md`.


## 1. Why this contract exists

The previous implementation freeze
(`0016e4fc616af9222f9c9fd581a4a4199b1bdccf`) was structurally incapable of
transitioning to a valid ARMed state. Every authority function was
total-to-exception, and two of them treated the *existence* of an ARM
artifact as itself an error. A future legitimate ARM would therefore have
required editing frozen scientific/authority source after freeze.

This contract, together with the repaired lifecycle gate, makes the
transition possible without any post-ARM source modification:

```text
UNARMED
  -> add authenticated ARM + RESERVATION artifacts
  -> the SAME frozen bytes become authorized
  -> exactly ONE canonical scientific execution
  -> RESULT at predeclared paths
  -> authorization consumed (durably, on disk)
```

## 2. Bound identities

```text
PREREG_HEAD       = 5b2a582cd3c42af7114ded7fe61ac7c9f39c9dd5
PREREG_MD_SHA256  = 31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e
PREREG_JSON_SHA256= f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25

BTC_DATASET  = CORE_BTC_BINANCE_V0
BTC_SNAPSHOT = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
ETH_DATASET  = CORE_ETH_BINANCE_V0
ETH_SNAPSHOT = 4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15

CANONICAL_EXECUTIONS_AUTHORIZED = 1
PROTECTED_OOS_AUTHORIZED        = false
```

## 3. RUN_IDENTITY

```text
RUN_IDENTITY = d683c3b25377e61917eeb37a4fc6cda9ebf3f8000dbe2011323a03fc37f7417a
```

Derived as `sha256(canonical_json_bytes(scientific_run_identity_payload()))`.
The preimage binds: research id, prereg identity (head + both hashes), the
full scientific implementation hash set, both dataset snapshots, the
development window, the protected-OOS boundary, every scientific and
bootstrap constant, the RESULT schema identity, the pinned numpy version,
and the authorized execution count.

Canonical serialization is `json.dumps(sort_keys=True, indent=2,
ensure_ascii=False, allow_nan=False)` plus a trailing newline. It reads no
clock, generates no UUID, and depends on no filesystem ordering.

**The authority recomputes this value independently and compares.** An ARM
that merely contains a `run_identity` proves nothing; a mismatch is
refused with `MARKET_05_ARM_RUN_IDENTITY_MISMATCH`.

## 4. Scientific implementation authority

Every file able to materially change a MARKET-05 result is bound
byte-for-byte and re-verified before any authorization is granted, so a
source mutation after ARM is detected and refused:

```text
scripts/research/market05_cross_asset_lib.py
scripts/research/market05_cross_asset_authority.py
scripts/research/market05_cross_asset_data.py
scripts/research/market05_cross_asset.py
scripts/research/market05_cross_asset_canonical_execution.py
scripts/research/core_eth_binance_v0_acceptor_lib.py
```

Exact hashes are in the JSON twin. `market05_cross_asset_arm_authority.py`
cannot pin its own hash (self-reference), so an independent root of trust,
`market05_cross_asset_authority_root.py`, pins its **git blob id** and is
itself anchored by the frozen commit/tree recorded in the re-freeze
artifact. Code pins blobs; docs pin the commit. Canonical execution and the
data loader verify that root BEFORE invoking the ARM authority, so a
mutation of the ARM authority is refused before any scientific data opens. The scientific library imports only
the standard library and numpy (pinned `2.1.3`), so no unbound project
module can alter behaviour — this is not a fake freeze.

## 5. What the ARM may NOT do

The ARM has **no authority to redefine any scientific parameter**. Its
`scientific_constants` block must equal the frozen values exactly
(decision time, 24h lookback, 24h horizon, `BTC_SIDE * Z_ETH`,
`BTC_DIRECTION_ALIGNED_MAE_24H`, both model formulas, OLS, materiality
`0.02`, `CIRCULAR_MOVING_BLOCK`, block length `14`, `5000` replicates,
seed `2026091905`, predictive-refit `false`, coefficient-refit `true`).
Any deviation raises `MARKET_05_ARM_SCIENTIFIC_CONSTANT_REDEFINED`.

The ARM must not carry outcome-shaped fields (classification, gates,
coefficients, bootstrap, MAEs, year metrics, row/fold counts, …). Any
occurrence raises `MARKET_05_ARM_CONTAINS_OUTCOME_FIELD`.

The ARM must be git-tracked and a regular file; untracked drop-ins and
symlinked authority are refused.

## 6. Protected OOS

`[2025-01-01T00:00:00Z, onward)` is never authorized, **even under a valid
development ARM**. An ARM asserting `protected_oos_authorized` is refused,
a dataset object named for a protected period is refused, and any row at
or beyond the boundary is refused. A future OOS study requires a separate
explicit research unit.

## 7. RESULT

RESULT may be written only at the predeclared paths
`docs/research/MARKET_05_RESULT.json` / `.md`, only under a valid ARM and
a valid unconsumed reservation, and never over an existing RESULT. The
RESULT's authority fields are populated from the authority module, not
from evaluator output, so a RESULT cannot self-attest its own authority.

## 8. One-shot execution

The reservation carries durable on-disk `AUTHORIZED = 1 / CONSUMED = 0`.
The canonical execution claims it and writes `CONSUMED = 1`. Because
authentication re-reads the artifact, a crash/retry cannot yield two
different scientific runs: after consumption every further attempt fails
at `MARKET_05_RESERVATION_CONSUMED`.
