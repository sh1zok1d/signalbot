# MARKET-06 CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK — implementation freeze

- **Status:** `IMPLEMENTATION_FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21

**Not a RESULT. Not an ARM. Not MARKET-06 execution. Not outcome
inspection. Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document freezes the MARKET-06 implementation identity so a later
red-team review can inspect those exact bytes. It does not authorize
canonical execution.

Canonical machine-readable twin:
`docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.json`.

```text
IMPLEMENTATION_HEAD = 81c8e0a8619190329971f5a85435c7ac4f9cb86e
IMPLEMENTATION_TREE = 7f4e0a85dc3738924eb52bb28f85794d6a8daa7a
PREREG_FREEZE_HEAD  = e2d543eadb5425473b6d4b8d24c177c1d7ae7930
PREREG_FREEZE_TREE  = a1706c775154fc65ad1d5eaaa5818f87b834a2b7
PREREG_CONTENT_HEAD = 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59
PREREG_CONTENT_TREE = 11658516cab22774501daa8e2e966c9a8861c9a3

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

This freeze does not hash itself.

---

## Bound implementation modules

Independently recomputed from
`git cat-file -p 81c8e0a8619190329971f5a85435c7ac4f9cb86e:<path>`.

```text
scripts/research/market_06_cross_venue_dislocation_authority.py
  SHA256 = dcfdc92843c91871317dae88d0b40e58b01387e10d52337090b543bdec44523f
  size   = 14399 bytes

scripts/research/market_06_cross_venue_dislocation_parsers.py
  SHA256 = 057a6e763aaa1f822571dd670a8e0d65c786fb4df5796fa50a12ae94c9f265c6
  size   = 5625 bytes

scripts/research/market_06_cross_venue_dislocation_bootstrap.py
  SHA256 = 773b7631f76885f34532dc16a845fd07711e9ca44496d7ef18a8079e98a63ec7
  size   = 4557 bytes

scripts/research/market_06_cross_venue_dislocation_evaluator.py
  SHA256 = c280c609db64362ec76a5810ce0cedc25cc609ef9fdcbc87e0cd935e6d8c6545
  size   = 17616 bytes

scripts/research/market_06_cross_venue_dislocation_runner.py
  SHA256 = e07470d1f371f0656d95d9e2116f4e5f983a416ad6f9ac8defaa619c1c416025
  size   = 1659 bytes

scripts/research/market_06_year_stratified_circular_mbb.py
  SHA256 = e8545dab9c3cf28eba556b3a0fe36d0b06cf412437a48516b3dc038a9a082da3
  size   = 2988 bytes

tests/research/test_market_06_implementation.py
  SHA256 = 9caac63b74f661a1e6cda7d20c958666aef0d5e885d514f15f8cdf449e414e7d
  size   = 21332 bytes
```

---

## Data authority (cross-check)

```text
DATASET_ID                   = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID                  = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
DURABLE_EVIDENCE_ROOT_SHA256 = f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f
```

---

## Freeze semantics

1. Implementation may only implement the frozen amended prereg.
2. Canonical execution remains unauthorized.
3. No ARM. No RESULT.
4. Protected 2025/2026 remain forbidden.
5. V0 and Amendment-001 preregs remain historical only.
6. `concatenated_then_sample` is not a production path.
7. No selective rerun / post-outcome threshold repair.

```text
REAL_CANONICAL_EXECUTION_REFUSED = true
market_06_executed = false
market_06_armed = false
scientific_outcomes_inspected = false
```

---

## Next lifecycle state

```text
NEXT_UNIT = MARKET_06_IMPLEMENTATION_RED_TEAM_REVIEW
```

Not execution. Not ARM.
