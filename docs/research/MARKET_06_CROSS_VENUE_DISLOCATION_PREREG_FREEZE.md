# MARKET-06 CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK — prereg freeze authority (amendment 002)

- **Status:** `FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE`
- **Research ID:** `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-21

**Not a RESULT. Not an ARM. Not MARKET-06 execution. Not an evaluator.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document is the **live** docs-only PREREG FREEZE record after
pre-outcome amendment 002. It establishes that the exact amended
MARKET-06 preregistration bytes — at materialization commit
`6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59` / tree
`11658516cab22774501daa8e2e966c9a8861c9a3` — are the sole scientific
authority for later MARKET-06 implementation.

Earlier freezes remain historical evidence only:

```text
OLD_PREREG_CONTENT_HEAD (V0) = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
OLD_FREEZE_HEAD (V0)         = 5f14411abc926a2b486d83de5b696ec3cf362488
OLD_LIVE_PREREG_HEAD (V1 / amendment 001) = b4459ab96addd6c39d4baec35248410a8f5cf8e0
OLD_LIVE_FREEZE_HEAD (V1 / amendment 001) = 371f71dd49e2c2c445269aeed1b75a39f33b3422
AMENDMENT_REASON = PRE_OUTCOME_PREDICTIVE_BOOTSTRAP_STRATIFICATION_CORRECTION
OUTCOMES_INSPECTED_BEFORE_AMENDMENT = false
```

Historical exact copies: `*_V0.*` and `*_V1.*`. Amendment artifacts:
`MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.md` and
`MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.md`.

This freeze does **not** modify the amended prereg files, implement the
evaluator, inspect MARKET outcomes, execute MARKET-06, modify V3, or
create V4.

Canonical machine-readable twin:
`docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.json`.

The prereg files' internal materialization-unit status string
(`PREREGISTERED_OUTCOME_BLIND_UNFROZEN`) is left unchanged because
those exact bytes are the frozen object. Current freeze authority is
**this document**.

---

## Bound content

```text
PRE_PREREG_HEAD              = a75a5272f994f9728308c47c524f2839b73762a7
ACCEPTED_PREREG_CONTENT_HEAD = 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59
ACCEPTED_PREREG_CONTENT_TREE = 11658516cab22774501daa8e2e966c9a8861c9a3

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

---

## Frozen prereg artifacts

Independently recomputed from
`git cat-file -p 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59:<path>`
immediately before writing this freeze. Neither file's bytes are
touched by this commit.

```text
docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md
  SHA256 = 70dd8d09e07e1209e77ea6d1c741e412534ef5cccbfc36609bc46924e13cc4c6
  size   = 21434 bytes

docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json
  SHA256 = f60bf0bdbeb5982933c648b1c9b56017f25a5dabb29ad39eac58d53b5f590a24
  size   = 14159 bytes
```

---

## Authority chain

```text
PRE_PREREG_HEAD         = a75a5272f994f9728308c47c524f2839b73762a7
SOURCE_FEASIBILITY_HEAD = ef439110684e5bef5d6b6f31b664c21a114111b2
V0_PREREG / V0_FREEZE   = b21bf46d… / 5f14411…
V1_PREREG / V1_FREEZE   = b4459ab9… / 371f71d…
PREREG_MATERIALIZATION  = 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59
                          (tree 11658516cab22774501daa8e2e966c9a8861c9a3)
```

---

## Data authorities already contained in the frozen prereg (cross-check only)

```text
DATASET_ID                   = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID                  = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
DURABLE_EVIDENCE_ROOT_SHA256 = f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f
```

Bound amendment 002 sampling structure (not a post-outcome choice):

```text
PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR = true
CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED = false
YEAR_SAMPLE_SIZE_PRESERVED_PER_REPLICATE = true
PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP = false
```

Amendment 001 F1–F4 remain bound:

```text
F1_ROBUST_SCALE_1_4826_FIXED = true
F2_ABS_BTC_RET_CONTROL_FIXED = true
F3_ARITHMETIC_MAE_FIXED = true
F4_GATE2_LOWER_BOUND_FIXED = true
GATE_2_EXACT_PREDICATE = BETA_ABS_DISLOCATION_Z_CI95_LOW > 0
```

---

## Freeze semantics

1. The amended prereg scientific payload is immutable live authority.
2. Implementation may only implement the frozen amended payload.
3. Implementation cannot choose new scientific constants/algorithms.
4. V0 and V1 freezes are historical evidence only and must not be implemented.
5. No MARKET outcomes may be inspected by this freeze.
6. No MARKET-06 execution is authorized.
7. No ARM is authorized.
8. Protected 2025 validation and 2026 OOS remain forbidden.
9. B2-06 remains `BLOCKED_MISSING_OBSERVABLE`.
10. No selective rerun / post-outcome threshold repair.

Scientific constants already bound in the frozen amended prereg —
including daily `00:05`, `FEATURE_CUTOFF=T-5m`,
`D_e=ln(perp_close/spot_close)`, 8640 MAD z-score with `1.4826`
robust scale, arithmetic `24H_DIRECTION_ALIGNED_BTC_MAE` on 288
Binance perp bars with `ENTRY_PRICE=open` at `T`, OLS baseline
`Y ~ 1 + BTC_SIDE + ABS_BTC_RET_24H + RV_BTC_24H` versus
`+ABS_DISLOCATION_Z`, 2022-02-01..2022-12-30 train, 2023/2024 holdouts
through Dec 30, no Dec 31, no refit, circular MBB 14/5000/seed
`2026092106` year-stratified by holdout year (no concatenated
2023+2024 sampling, no cross-year wrap), six gates with `G5>=0.02`
and Gate 2 `BETA_ABS_DISLOCATION_Z_CI95_LOW > 0`, and `PROMOTION`
versus `NO_EVIDENCE` — are not restated as new choices here.

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
market_06_implementation_authorized      = true   (frozen amended contract only)
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
PROMOTED_HISTORICAL_CANDIDATE.

---

## Next lifecycle state

```text
NEXT_UNIT = MARKET_06_IMPLEMENTATION_OUTCOME_BLIND
```

Implement the already-frozen amended MARKET-06 contract. Not execution.
Not ARM.

---

## Validation performed before this commit

- `git cat-file -p 6342d24e…:docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md` → SHA256 matched expected `70dd8d09…`.
- `git cat-file -p 6342d24e…:docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.json` → SHA256 matched expected `f60bf0bd…`.
- No MARKET-06 amended prereg bytes are present in this commit's intended diff.
- No evaluator, runner, V3, or V4 files are present in this commit's intended diff.
- No MARKET outcomes were inspected.
