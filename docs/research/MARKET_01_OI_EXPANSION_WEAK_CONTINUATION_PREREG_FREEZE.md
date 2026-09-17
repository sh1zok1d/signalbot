# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — prereg freeze authority

- **Status:** `FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Date:** 2026-09-17

**Not a RESULT. Not an ARM. Not MARKET-01 execution. Not an evaluator.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document is a docs-only PREREG FREEZE record. It establishes that
the exact already-materialized MARKET-01 preregistration bytes — at
materialization commit `9c1a661c52ad1ee7295cb898c1e1a048d5281d2f` /
tree `1928969ed4d12896a3793a7048aff163dc1b3dac` — are the sole
scientific authority for later MARKET-01 implementation.

It does **not** modify those prereg files, rewrite any scientific
choice in them, implement the MARKET-01 evaluator, inspect MARKET
outcomes, execute MARKET-01, modify V3, or create V4.

Canonical machine-readable twin:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json`.

The prereg files' internal materialization-unit status string
(`PREREGISTERED_OUTCOME_BLIND_UNFROZEN`) is left unchanged because
those exact bytes are the frozen object. Current freeze authority is
**this document**, not that internal label.

---

## Bound content

```text
ACCEPTED_PREREG_CONTENT_HEAD = 9c1a661c52ad1ee7295cb898c1e1a048d5281d2f
ACCEPTED_PREREG_CONTENT_TREE = 1928969ed4d12896a3793a7048aff163dc1b3dac

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
`git cat-file -p 9c1a661c52ad1ee7295cb898c1e1a048d5281d2f:<path>`
immediately before writing this freeze. Both matched the expected
materialization hashes. Neither file's bytes are touched by this
commit.

```text
docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md
  SHA256 = d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866
  size   = 21718 bytes

docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json
  SHA256 = 6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4
  size   = 22576 bytes
```

---

## Authority chain

```text
FEASIBILITY_COMMIT     = 901f96eaa551e2591a6212a14ddd4488f5528e8e
DESIGN_BLOCKER_COMMIT  = 5a629819676240e98b6b125aa4606e8759c1f0f2
PREREG_MATERIALIZATION = 9c1a661c52ad1ee7295cb898c1e1a048d5281d2f
                         (tree 1928969ed4d12896a3793a7048aff163dc1b3dac)
```

---

## Data authorities already contained in the frozen prereg (cross-check only)

```text
PRICE dataset_id  = CORE_BTC_BINANCE_V0
PRICE snapshot_id = 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415

OI source         = Binance Vision daily/metrics/BTCUSDT
OI field          = sum_open_interest
OI snapshot_id    = 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33

common_period     = [2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)
decision_grain    = UTC-epoch 5-minute boundaries
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
6. No MARKET-01 execution is authorized.
7. No ARM is authorized.
8. Protected 2025 validation and 2026 OOS remain forbidden.
9. B2-06 remains `BLOCKED_MISSING_OBSERVABLE`. Using the bound OI
   snapshot for MARKET-01 does not unblock B2-06.
10. No selective rerun / post-outcome threshold repair.

Scientific constants already bound in the frozen prereg — including
30m/30m/60m windows, 90th/75th/0.25 rules, `PRE_VOL_60`, 3×3 tertiles,
OLS estimand, stationary bootstrap `B=999` `alpha=0.05`, support
floors, five eras, LOEO, concentration `<=0.50`, and classification
mapping — are not restated as new choices here.

---

## Preserved limitations

1. MARKET-01 uses a **new** confirmatory statistical identity. It is
   **not** V3. Do not call `evaluate_v3_world` on MARKET data. Do not
   inherit the V3 Clark-West estimand.
2. `MARKET_01_TEST_CALIBRATED = NO`.
3. V3 synthetic calibration does **not** validate the MARKET-01
   two-group stratified regression/bootstrap test.
4. The V3 `NONSTATIONARY_TRAP` failure motivated the prospective
   MARKET-01 temporal robustness **downgrade** layer only.
5. No new synthetic calibration phase is authorized. `DEFAULT_V4 = NO`.
6. `ROBUST_CANDIDATE`, if it ever occurs later, does **not** mean
   validated alpha, causal proof, profitable strategy, production
   readiness, permission to trade, or automatic protected-OOS
   promotion.

---

## Explicit state

```text
market_01_outcome_inspected              = false
market_01_prereg_materialized            = true
market_01_prereg_ready                   = true
market_01_prereg_frozen                  = true
market_01_freeze_required                = false
market_01_executed                       = false
market_01_armed                          = false
market_01_implementation_authorized      = true   (frozen contract only)
market_01_execution_authorized           = false
market_01_test_calibrated                = false
protected_oos_authorized                 = false
protected_oos_touched                    = false
v3_reused_as_market_01_test              = false
v3_methodology_claimable                 = false
b2_06_execution_authorized               = false
default_v4                               = false
```

Do **not** mark ARMED, EXECUTING, EXECUTED, DETECTED, or
ROBUST_CANDIDATE. No outcome-dependent state is legal in this unit.

---

## Next lifecycle state

Implementation of the already-frozen MARKET-01 contract.

Not execution. Not ARM. MARKET hypotheses in this repository do not
require the V3 synthetic one-shot ARM sequence. A later implementation
unit may still require its own review before any execution
authorization; that review is not this freeze.

---

## Validation performed before this commit

- `git cat-file -p 9c1a661c…:docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md` → SHA256 matched expected `d82b60e1…`.
- `git cat-file -p 9c1a661c…:docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json` → SHA256 matched expected `6885abaf…`.
- `git merge-base --is-ancestor 9c1a661c52ad1ee7295cb898c1e1a048d5281d2f HEAD` confirmed.
- No MARKET-01 prereg bytes are present in this commit's intended diff.
- No evaluator, runner, V3, or V4 files are present in this commit's intended diff.
- No MARKET outcomes were inspected.
