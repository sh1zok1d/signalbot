# MARKET-05 CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK — ARM

- **Status:** `MARKET_05_ARMED`
- **Unit ID:** `MARKET_05_CROSS_ASSET_ARM`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** `MARKET_05_ARM.json`

**This is the real ARM.** It authorizes exactly one canonical MARKET-05
execution. It does not itself execute anything, create the execution
claim, load scientific rows, or produce a RESULT — those belong to the
one-shot canonical execution unit that follows.

## 1. Authority chain

```text
authority_head                 = f59679603ec4e0d2b4b11056828ef57e11f12349
authority_tree                 = a1796efe01ab5370035970109e3f2d8d79f6efc8
scientific_implementation_head = 23d9d18a58f43307d14a2c9c1890636cd581cba3
scientific_implementation_tree = 957d41f4382ec3ef4d65ad93dfe68b58ff1e3237
```

Bound after an independent final pre-ARM red-team audit returned
`MARKET_05_FINAL_PRE_ARM_RED_TEAM_CLEAN` (0 CRITICAL, 0 HIGH findings)
against this exact authority/tree pair.

## 2. Bound identities

```text
PREREG_MD_SHA256   = 31349f8863be3a79604d0c8dc93ca7037451ab16edb83a432d31af81f8a0193e
PREREG_JSON_SHA256 = f2b2f6b98a3674412b584e6bd2686efa8fb9ce08b5d936e503e5d570a2428b25

BTC_SNAPSHOT        = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
ETH_SNAPSHOT        = 4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15
ETH_EXECUTION_DATA_ID = b5c6228a2c4214b641cd10fda87010c2898040e3fc53cdacee9211e028752484

RESULT_SCHEMA_IDENTITY   = market_05_cross_asset_result/1.2.0
EXECUTION_CLAIM_PROTOCOL = MARKET_05_ATOMIC_O_EXCL_CLAIM_V1
SEMANTIC_CONTRACT_SHA256 = 1591c0b8fd70a0e1dfb4f1cad8aa9c66786b691a6fff087db0b3d3d7821f994e

NUMPY_VERSION_REQUIRED   = 2.1.3
PYARROW_VERSION_REQUIRED = 17.0.0
```

## 3. RUN_IDENTITY

```text
RUN_IDENTITY = 6957613de4b035d850fc97edb833565c5fd3d7b085aa158e0992b88142190635
```

Not trusted from this document. Production authority recomputes it
independently from frozen constants on every authorization decision and
refuses on any mismatch (`MARKET_05_ARM_RUN_IDENTITY_MISMATCH`).

## 4. What this ARM does NOT do

- does not create `MARKET_05_EXECUTION_CLAIM.json`;
- does not load real CORE BTC/ETH rows;
- does not compute Y, MAE, beta, bootstrap, or classification;
- does not authorize protected OOS (`[2025-01-01T00:00:00Z, onward)`);
- does not redefine any scientific constant — every value in the JSON
  twin's `scientific_constants` block is required to equal the frozen
  value exactly, or authentication refuses.

## 5. Lifecycle

```text
MARKET_05_ARMED                  = true
MARKET_05_EXECUTED                = false
MARKET_05_OUTCOMES_INSPECTED      = false
authorization_consumed            = false
CANONICAL_EXECUTIONS_AUTHORIZED   = 1
CANONICAL_EXECUTIONS_CONSUMED     = 0
protected_oos_authorized          = false
```

Paired with `MARKET_05_RESERVATION.json`, which durably represents the
same unconsumed `1/0` authorization on disk. Neither artifact consumes the
run; only the atomic execution claim (created by the canonical execution
bootstrap, immediately before any scientific data loads) does that.

Next unit: `MARKET_05_ONE_SHOT_CANONICAL_EXECUTION`.
