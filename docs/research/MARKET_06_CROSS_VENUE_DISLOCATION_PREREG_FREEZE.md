# MARKET-06 CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK — prereg freeze authority

- **Status:** `FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21

**Not a RESULT. Not an ARM. Not MARKET-06 execution. Not an evaluator.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document is a docs-only PREREG FREEZE record. It establishes that
the exact already-materialized MARKET-06 preregistration bytes — at
materialization commit `b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1` /
tree `ce436bf3d025340752f5afea765ea0cbe50e499e` — are the sole
scientific authority for later MARKET-06 implementation.

It does **not** modify those prereg files, rewrite any scientific
choice in them, implement the MARKET-06 evaluator, inspect MARKET
outcomes, execute MARKET-06, modify V3, or create V4.

Canonical machine-readable twin:
`docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json`.

The prereg files' internal materialization-unit status string
(`PREREGISTERED_OUTCOME_BLIND_UNFROZEN`) is left unchanged because
those exact bytes are the frozen object. Current freeze authority is
**this document**, not that internal label.

---

## Bound content

```text
PRE_PREREG_HEAD            = a75a5272f994f9728308c47c524f2839b73762a7
PRE_PREREG_TREE            = 7272614b7a2799aaf82a80f5d7c9cb1207af01ac
ACCEPTED_PREREG_CONTENT_HEAD = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
ACCEPTED_PREREG_CONTENT_TREE = ce436bf3d025340752f5afea765ea0cbe50e499e

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact never depends on a circular
self-hash of its own freeze-commit digest — matching the established
repository freeze convention. Binding is to the materialization
HEAD/tree and the blob hashes below, independently recomputed from
that exact commit before this freeze was written.

---

## Frozen prereg artifacts

Independently recomputed from
`git cat-file -p b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1:<path>`
immediately before writing this freeze. Both matched the expected
materialization hashes. Neither file's bytes are touched by this
commit.

```text
docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md
  SHA256 = 0489fc71e999b48a7a82223615bd0acd50b1f69af8bc9901d1c681834e55cfcc
  size   = 19122 bytes

docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json
  SHA256 = 332d91140c7ead87f4539b49c8a5647064f9c5e1d0bb8178c16dcc7eaf7a88f4
  size   = 12248 bytes
```

---

## Authority chain

```text
PRE_PREREG_HEAD            = a75a5272f994f9728308c47c524f2839b73762a7
SOURCE_FEASIBILITY_HEAD    = ef439110684e5bef5d6b6f31b664c21a114111b2
PREREG_MATERIALIZATION     = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
                             (tree ce436bf3d025340752f5afea765ea0cbe50e499e)
```

---

## Data authorities already contained in the frozen prereg (cross-check only)

```text
DATASET_ID                 = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID                = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
DURABLE_EVIDENCE_ROOT_SHA256 = f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f
PERP                       = Binance USD-M BTCUSDT 5m TRADE_PRICE
SPOT                       = OKX BTC-USDT 5m confirm=1
DECISION_T                 = 00:05:00 UTC daily
FEATURE_CUTOFF             = T-5m
PRIMARY_FEATURE            = ABS_DISLOCATION_Z
```

This freeze does not expand, shrink, or reinterpret those authorities.

---

## Freeze semantics

1. The prereg scientific payload is immutable authority.
2. Implementation may only implement the frozen payload.
3. Implementation cannot choose new scientific constants/algorithms.
4. Any required scientific change discovered during implementation
   invalidates execution authorization and requires an explicit
   pre-outcome amendment/re-freeze, not a silent edit.
5. No MARKET outcomes may be inspected by this freeze.
6. No MARKET-06 execution is authorized.
7. No ARM is authorized.
8. Protected 2025 validation and 2026 OOS remain forbidden.
9. B2-06 remains `BLOCKED_MISSING_OBSERVABLE`.
10. No selective rerun / post-outcome threshold repair.

Scientific constants already bound in the frozen prereg — including
daily `00:05`, `FEATURE_CUTOFF=T-5m`, `D_e=ln(perp_close/spot_close)`,
8640 MAD z-score, `24H_DIRECTION_ALIGNED_BTC_MAE` on 288 Binance perp
bars with `ENTRY=open` at `T`, OLS baseline versus
`+ABS_DISLOCATION_Z`, 2022-02-01..2022-12-30 train, 2023/2024 holdouts
through Dec 30, no Dec 31, no refit, circular MBB 14/5000/seed
`2026092106`, six gates with `G5>=0.02`, and
`PROMOTION` versus `NO_EVIDENCE` — are not restated as new choices here.

---

## Preserved limitations

1. MARKET-06 uses a **new** confirmatory statistical identity. It is
   **not** V3. Do not call `evaluate_v3_world` on MARKET data.
2. `MARKET_06_TEST_CALIBRATED = NO`.
3. V3 synthetic calibration does **not** validate the MARKET-06 OLS +
   chronological prediction + block-bootstrap test.
4. No new synthetic calibration phase is authorized. `DEFAULT_V4 = NO`.
5. `MARKET_06_PROMOTED_HISTORICAL_CANDIDATE`, if it ever occurs later,
   does **not** mean validated alpha, causal proof, profitable
   strategy, production readiness, permission to trade, or automatic
   protected-OOS promotion.

---

## Explicit state

```text
market_06_outcome_inspected              = false
market_06_prereg_materialized            = true
market_06_prereg_ready                   = true
market_06_prereg_frozen                  = true
market_06_freeze_required                = false
market_06_executed                       = false
market_06_armed                          = false
market_06_implementation_authorized      = true   (frozen contract only)
market_06_execution_authorized           = false
market_06_test_calibrated                = false
protected_oos_authorized                 = false
protected_oos_touched                    = false
v3_reused_as_market_06_test              = false
v3_methodology_claimable                 = false
b2_06_execution_authorized               = false
default_v4                               = false
```

Do **not** mark ARMED, EXECUTING, EXECUTED, DETECTED, or
PROMOTED_HISTORICAL_CANDIDATE. No outcome-dependent state is legal in
this unit.

---

## Next lifecycle state

```text
NEXT_UNIT = MARKET_06_IMPLEMENTATION_OUTCOME_BLIND
```

Implement the already-frozen MARKET-06 contract. Not execution. Not ARM.

---

## Validation performed before this commit

- `git cat-file -p b21bf46d…:docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md` → SHA256 matched expected `0489fc71…`.
- `git cat-file -p b21bf46d…:docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json` → SHA256 matched expected `332d9114…`.
- `git merge-base --is-ancestor a75a5272f994f9728308c47c524f2839b73762a7 HEAD` confirmed.
- No MARKET-06 prereg bytes are present in this commit's intended diff.
- No evaluator, runner, V3, or V4 files are present in this commit's intended diff.
- No MARKET outcomes were inspected.
