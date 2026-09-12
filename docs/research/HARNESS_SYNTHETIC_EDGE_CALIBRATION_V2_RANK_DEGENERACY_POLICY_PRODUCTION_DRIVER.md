# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — production driver

**Status: `PRODUCTION_DRIVER_IMPLEMENTATION_AWAITING_INDEPENDENT_REVIEW`.**

This is **not** an execution freeze and **not** an ARM. It is an
implementation unit that adds the execution layer the frozen V2 fixture
intentionally omits, awaiting independent review before any freeze/ARM unit
may reference it.

## What this unit is

The V2 fixture module
(`scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py`,
frozen at HEAD `a310837bab4ee60c7495cca3bdb476abdc58a041`, implementation
frozen at HEAD `f96197d109fc22c12e4c8ba19715d67c65187c0e`) is fixture-only: it
hard-refuses production N (`assert_not_production_grid`) and has zero import
path to any production/ARM machinery. Before this unit, V2 lacked:

1. a canonical V2 production-plan derivation;
2. a V2 production driver/runtime;
3. a V2 runtime ARM-authorization function.

This unit adds exactly those three things, in a new file:
`scripts/research/harness_synthetic_edge_calibration_v2_production.py`. It
does **not** modify the frozen fixture, the freeze artifact, the original
prereg, or Amendment_001.

## Base policy freeze bound by this unit

- `POLICY_FREEZE_HEAD = f96197d109fc22c12e4c8ba19715d67c65187c0e`
- `POLICY_FREEZE_TREE = ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5`
- reviewed V2 policy `HEAD = a310837bab4ee60c7495cca3bdb476abdc58a041` /
  `TREE = b15c4102b01514ff73e1728aec072eda9b528815`
- original prereg `HEAD = ada237edc330b44bc412332e263f124757919e93` /
  `TREE = ba1c0873879b7ea8556c3e238f8b962b91da6dc2`
- Amendment_001 `HEAD = d8f0a996bc4341d0cbe01a1a061130b889ed5e75` /
  `TREE = 09dca9b1240a43d5de9de0dadf32d27e00e7eaea`

## Canonical V2 plan: `FROZEN_V1_PRODUCTION_GRID + FROZEN_V2_RANK_POLICY`

`canonical_v2_plan()` does not invent a new scientific grid. It:

- reuses `harness_synthetic_edge_calibration_v1_production.frozen_production_grid()`
  and `planned_production_jobs()` **unmodified** for the world set, cell
  ordering, scenario ids, N values, worlds-per-cell, and root-seed/seed
  derivation authority (`canonical_v2_production_jobs() ==
  planned_production_jobs()`, proven by test, byte-for-byte, not merely
  "equivalent");
- binds the V2 policy source's exact git blob/SHA256/size on top;
- serializes both deterministically (`canonical_json_bytes`, sorted keys) and
  SHA256s the result.

`CANONICAL_WORLD_COUNT = 3200`. Changing only the V2 policy identity, or only
the V1 grid identity, changes the plan's SHA256 (both proven by test).

## Execution-authoritative V2 files

- `scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py`
  (frozen fixture; unmodified; semantic reference/oracle)
- `scripts/research/harness_synthetic_edge_calibration_v2_production.py`
  (this unit; thin orchestration only)
- the five V1 TCB files (unmodified; hash-pinned)

## No scientific reimplementation

Per-world classification is never reimplemented. The production driver's
per-world function calls the frozen fixture's own private inner function
(`_evaluate_v2_world_inner`) — the exact function object the fixture's public
`evaluate_v2_world` calls internally — with the same "no fixture-only
injection" defaults the public wrapper uses. The only code duplicated is the
public wrapper's ~15-line guard-adjacent exception-to-`WORLD_INVALID`
conversion glue (not classification logic), and
`test_harness_synthetic_edge_calibration_v2_production.py` proves this glue is
byte-for-byte equivalent to the fixture's own wrapper, exhaustively, across
every scenario × non-production N × world index the fixture's public API can
reach, including the forced-lookahead → `WORLD_INVALID` path.

Worlds are built via the frozen, unmodified `simulate_dgp` — the driver never
accepts a caller-supplied world, seed, or scientific parameter.

## ARM runtime authorization contract

`v2_production_arm_authorized()` recognizes only an ARM (tracked at
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json`,
a path that does not exist anywhere in the repository as of this unit) whose
committed git object bytes, evaluated at the exact commit under test:

- declare `freeze_parent_head`/`freeze_parent_tree` equal to that commit's
  own actual immediate git parent and its tree (not merely "some freeze
  string");
- bind the freeze artifact's exact SHA256/size at that parent;
- bind the V2 policy's exact SHA256/size at that commit;
- bind all five V1 TCB SHA256 hashes, recomputed at that commit;
- bind the canonical V2 plan SHA256, recomputed at that commit;
- bind the exact original-prereg and Amendment_001 HEAD/TREE;
- declare `authorization_consumed: false` and the required one-shot literal
  contract (`V2_ARM_REQUIRED_LITERALS`);
- have no conflicting RESULT/WORLD_RECORDS/RESERVATION/CLAIM artifact
  tracked at that commit.

This makes the ARM commit's own parent chain and byte content the sole
authority — not a worktree file, not a caller argument, not "any child of the
freeze." A worktree-only mutation of the ARM file cannot change the answer
(only a new commit can); a descendant of the ARM does not authorize (its
parent is the ARM, not the freeze); a sibling commit without a matching,
self-consistent ARM payload does not authorize; a V1-style ARM at a different
path does not authorize V2.

`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json`
does not exist in this repository as of this unit. Therefore, at this HEAD:

- `v2_production_arm_authorized() = False`
- `run_canonical_v2_production_grid()` raises `V2ProductionNotArmed`
- `evaluate_v2_production_world(...)` raises `V2ProductionNotArmed`
- `mint_v2_result(...)` raises `V2ProductionNotArmed`

No 3200-world run, no RESULT, no WORLD_RECORDS, no reservation, no claim, no
authority consumption is possible from this unit.

## V1 failure history preserved

- `V1_ATTEMPT_STATUS = INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- `V1_3087_SUBSET_CLAIMABLE = false`

Unchanged and non-resumable, exactly as recorded by the V1 production
history and the V2 prereg/amendment/freeze chain.

## Known limitations (explicit, not silently deferred)

- **Consumption marking** after a real run (writing
  `authorization_consumed: true` durably, reservation/claim persistence
  across process restarts, checkpointing) is not implemented. No run can
  happen without a real ARM, which does not exist yet, so there is nothing to
  mark consumed. A future execution-freeze/ARM unit that actually runs the
  grid must add durable consumption/reservation persistence before that run,
  analogous to `DurablePartialWorldStore` in the V1 production module.
- `mint_v2_result` is a minimal, gated, unreachable stub: it verifies ARM
  authorization and independently recomputes and equality-checks every
  supplied `WorldRecordV2` before doing anything else, then always refuses
  (`RESULT minting is not implemented in this unit`). A future unit must
  replace the final refusal with real aggregate derivation, once a real ARM
  and a real run exist to derive it from.
- Historical/cross-commit ARM verification (`_v2_arm_payload_authorizes_at_commit`)
  is scoped to evaluating whatever commit is checked out as `HEAD`; it does
  not implement V1's more elaborate "search backward from HEAD for a
  historical ARM commit" machinery. This is sufficient for every required
  test case (each is evaluated by checking out the commit in question and
  asking whether that HEAD is authorized) but should be revisited if a future
  unit needs to verify authorization at an ARM commit that is not the live
  HEAD.

## Next required step

`INDEPENDENT_V2_PRODUCTION_DRIVER_AND_ARM_RUNTIME_REVIEW`. This unit is not
self-certifying; the report accompanying this commit lists exact test
commands/results/exclusions for that review to verify independently.
