# MARKET-05 — IMPLEMENTATION RE-FREEZE (outcome-blind)

- **Status:** `MARKET_05_IMPLEMENTATION_REFROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET_05_CROSS_ASSET_IMPLEMENTATION_REFREEZE`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** `MARKET_05_IMPLEMENTATION_REFREEZE.json`

## 1. What was wrong, stated honestly

```text
PREVIOUS_IMPLEMENTATION_HEAD = 0016e4fc616af9222f9c9fd581a4a4199b1bdccf
PREVIOUS_IMPLEMENTATION_TREE = 9c8575f6380977de2b2ad0d4d4c935ad819da6ef
REPAIR_REASON = PRE_ARM_LIFECYCLE_GATE_COULD_NOT_TRANSITION_TO_VALID_ARM_WITHOUT_CODE_CHANGE
```

The previous freeze **did not** have the property that a valid future ARM
could authorize it. This re-freeze does not claim otherwise.

A pre-ARM red-team audit found that every execution-authority function was
total-to-exception, with no reachable authorized branch:

- `inspect_market_05_authorization_state()` returned hardcoded `False`/`0`
  literals; it computed `arm_exists` and never used it.
- `require_execution_authorized_before_outcome_load()` and
  `refuse_unarmed_canonical_execution()` treated the *existence* of an ARM
  artifact as itself an error — inverted polarity — and then refused
  unconditionally regardless.
- `refuse_scientific_result_instantiation()` and
  `instantiate_scientific_result()` refused unconditionally.
- `load_real_development_scientific_rows()` was refused three times over,
  including by an input guard that rejected the real bound snapshots by
  construction.

A future legitimate ARM would therefore have required editing frozen
scientific/authority source after freeze, which violates the research
lifecycle.

## 2. What the repair changed

The gate became lifecycle-capable; the science did not move.

```text
PREREG_CHANGED          = NO
SCIENTIFIC_MATH_CHANGED = NO
```

Feature construction, outcome construction, folds, standardization,
regression, the bootstrap statistic and classification are byte-identical
in intent and behaviour: the only edit inside
`market05_cross_asset_lib.py` is `instantiate_scientific_result()`, which
is a RESULT-authority function containing no math, and which now validates
the RESULT schema instead of refusing forever.

New files carry the lifecycle:

```text
scripts/research/market05_cross_asset_arm_authority.py
scripts/research/market05_cross_asset_canonical_execution.py
```

## 3. Lifecycle now reachable without source modification

```text
UNARMED
  -> add authenticated ARM + RESERVATION artifacts
  -> the SAME frozen bytes become authorized
  -> exactly ONE canonical scientific execution
  -> RESULT at predeclared paths
  -> authorization consumed durably on disk
```

Proven end-to-end in an isolated temporary repository with fixture data,
asserting that the live implementation bytes are unchanged before and
after. See `tests/research/test_market05_arm_lifecycle.py`.

## 4. Current state — still unarmed

```text
FULL_PREREGISTRATION_FROZEN     = true
IMPLEMENTATION_FROZEN           = true
ARMED                           = false
EXECUTION_AUTHORIZED            = false
CANONICAL_EXECUTIONS_AUTHORIZED = 0
CANONICAL_EXECUTIONS_CONSUMED   = 0
SCIENTIFIC_OUTCOMES_INSPECTED   = false
PROTECTED_OOS_TOUCHED           = false
REAL_ARM_CREATED                = false
RESULT_CREATED                  = false
ARM_CONTRACT_FROZEN             = true
POST_ARM_CODE_CHANGE_REQUIRED   = false
```

## 5. RUN_IDENTITY

```text
RUN_IDENTITY = 0cbd5c23259ec6a43b8fdaf032822c6cecb53ad69ec7a2b9b760609b56c74c0e
```

Recomputed independently by the authority on every authorization decision
and compared against the ARM; never trusted from the ARM. Construction is
documented in `MARKET_05_ARM_CONTRACT.md` §3.

## 6. Bound scientific implementation

Exact hashes are in the JSON twin. `market05_cross_asset_arm_authority.py`
cannot pin its own hash, so it is bound here and in the ARM contract
instead. The scientific library imports only the standard library and
numpy (pinned `2.1.3`); no unbound project module can alter behaviour.

## 7. Relationship to the previous freeze

`MARKET_05_IMPLEMENTATION_FREEZE.{md,json}` remains valid as a record of
what was frozen at `0016e4fc…`. It is superseded as *current* authority by
this document, and it is annotated to say so. Its implementation hashes
intentionally still describe the pre-repair bytes.
