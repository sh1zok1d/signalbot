# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — production driver

**Status: `PRODUCTION_LIFECYCLE_IMPLEMENTATION_AWAITING_INDEPENDENT_REVIEW`.**

This is **not** an execution freeze and **not** an ARM. It is a pre-outcome
implementation unit: the complete mechanical lifecycle (plan → ARM
authorization → durable reservation → execution → durable evidence →
aggregation → RESULT → historical verification) now exists in code, so that
no scientific or aggregation decision remains to be made after canonical
outcomes are seen. No real ARM exists anywhere in this repository, and none
is created by this unit.

## History

1. First implementation unit added canonical plan derivation, a thin
   per-world orchestration layer, and HEAD-relative ARM authorization.
2. An independent adversarial review found 4 BLOCKERs and 1 MAJOR: no
   historical (commit-parameterized) authorization; no durable one-shot
   reservation/claim/consumption; RESULT/WORLD_RECORDS mint unimplemented;
   aggregation absent; and per-world re-verification overhead.
3. **This unit** closes all five findings, described below.

## Base policy freeze bound by this unit

- `POLICY_FREEZE_HEAD = f96197d109fc22c12e4c8ba19715d67c65187c0e`
- `POLICY_FREEZE_TREE = ec169d8bd73896308ce4dcf1d5d5fd218cd55bd5`
- reviewed V2 policy `HEAD = a310837bab4ee60c7495cca3bdb476abdc58a041` /
  `TREE = b15c4102b01514ff73e1728aec072eda9b528815`
- original prereg `HEAD = ada237edc330b44bc412332e263f124757919e93` /
  `TREE = ba1c0873879b7ea8556c3e238f8b962b91da6dc2`
- Amendment_001 `HEAD = d8f0a996bc4341d0cbe01a1a061130b889ed5e75` /
  `TREE = 09dca9b1240a43d5de9de0dadf32d27e00e7eaea`

All of these remain byte-identical through this unit (verified by
`git diff`, zero output).

## BLOCKER 1 — historical execution authority (closed)

`verify_historical_v2_execution_authority(repo_root, arm_commit)` proves an
**explicit** historical commit was correctly armed, using only git objects at
that commit — it neither depends on nor requires ambient HEAD to equal
`arm_commit`. It reuses the same generic `_v2_arm_payload_authorizes_at_commit`
primitive the original HEAD-relative `v2_production_arm_authorized()` uses;
this is an additional public entrypoint onto that primitive, not a second
implementation. Proven by test to work identically at the ARM commit, at an
arbitrary descendant commit, and from a clean clone containing the same
commits — and to be unaffected by worktree-only mutation of the ARM file.

## BLOCKER 2 — durable one-shot authority (closed)

`v2_durable_reservation_document` / `v2_durable_claim_document` are pure
identity derivations from an exact historically-verified bound (mirroring
V1's own already-frozen `durable_reservation_document`/`durable_claim_document`
design exactly — those are likewise pure identity functions, not in-process
locks). Durability comes from committing the derived payload to git as a
reachable descendant of the ARM: `assert_v2_reservation_available` fails
closed the moment any of RESERVATION/CLAIM/WORLD_RECORDS/RESULT is already
tracked. This is git-native mutual exclusion — whichever reservation commit
is pushed/merged first durably wins, and every later or concurrent attempt's
own availability check sees the artifact already present and refuses. This
unit does not invent a distributed lock stronger than that; it matches the
guarantee level V1's own already-reviewed design provides. Proven by test for
sequential duplicate reservation and for a simulated two-process race (both
check availability, one commits, the other's re-check then fails closed).

## Durable partial / checkpoint (closed)

`V2DurablePartialWorldStore` is a local, untracked, crash-safe per-world
cache, reusing V1's own atomic-write primitives (`_atomic_replace_bytes`,
`_fsync_directory`) verbatim — no reimplementation of the durability
mechanism. Cached records are structurally checked (kind, completeness, run
identity, digest) but are **never** scientific authority: `mint_v2_world_records`
always independently recomputes and exactly compares every record against
frozen execution before accepting it, so a forged-but-self-consistent
checkpoint cannot mint. Proven by test: checkpoint/resume produces identical
records; a conflicting duplicate write is refused
(`V2ProductionIntegrityError`); a store identity mismatch is refused; and a
forged record — even if it were smuggled past the local cache entirely — is
still caught by mint's independent recomputation.

## BLOCKER 4 — mechanical V2 aggregation (closed for everything already frozen)

`derive_v2_cell_aggregates` / `derive_v2_coverage_verdicts` /
`derive_v2_baseline_coverage_verdicts` / `derive_v2_required_coverage_status`
/ `derive_v2_mechanical_conclusions` wire the **frozen fixture's own
already-reviewed aggregation pipeline** — `aggregate_v2_records`,
`CellAggregateV2.result_schema()` (world_valid_count, per-candidate
identifiable/non-identifiable/detection counts and rates, L distribution
with reconciliation, BLIND-by-L + pooled + reconciliation status),
`evaluate_cell_coverage` (the frozen 80-entry threshold table + hard floor +
Wilson), `required_coverage_for_conclusion` (the frozen 33-entry required
coverage map), and `mechanical_conclusion_v2` (structural incompleteness >
insufficient identifiability > inherited ladder) — onto real evidence. **No**
aggregation/coverage/precedence logic is reimplemented; this is orchestration
over already-frozen functions only.

**Explicit, deliberate scope boundary:** `mechanical_conclusion_v2`'s third
input, the inherited V1-ladder verdict for each of the 33 named conclusions,
is **not** computed by this unit. `frozen_required_coverage_map()`'s entries
carry only a human-readable `inherited_claim` string (e.g. `"ORACLE NULL
MODEL_DETECTED FPR <= 0.05"`), not a machine-executable threshold/kind
binding, and no existing frozen function already maps that string to a
verdict. Reconstructing that mapping from prose would itself be an
unreviewed scientific choice — exactly what this whole framework's
prereg-first discipline exists to prevent. `derive_v2_mechanical_conclusions`
therefore takes `inherited_detection_conclusions` as a **required** parameter
(fails closed if any of the 33 ids is missing) that a **separate, dedicated,
independently reviewed** unit must supply before a real mint. See
`KNOWN_LIMITATIONS`.

## BLOCKER 3 — WORLD_RECORDS + RESULT mint (closed, modulo the same boundary)

`mint_v2_world_records` requires historical ARM authority (not ambient HEAD),
requires exactly the canonical world count, and independently re-evaluates
every supplied record before serializing (deterministic, digest-bound).
`mint_v2_result` derives aggregation and mechanical conclusions internally
from that same evidence and binds run identity, ARM commit, canonical plan
identity, and WORLD_RECORDS digest/size/count. No caller-supplied aggregate,
digest, or record can become authority. Never invoked with a real ARM by
this unit — none exists.

## §7 — historical RESULT verification (closed)

`verify_historical_v2_result` recomputes and compares a persisted
RESULT/WORLD_RECORDS pair entirely from scratch, from any checkout: it
establishes authority solely via `verify_historical_v2_execution_authority`
(commit-parameterized), independently recomputes every world record from the
frozen DGP/policy (never trusting the payload), and independently
re-derives the aggregation and conclusions. Proven by test to succeed for
honest evidence from the ARM commit, a descendant commit, and a clean clone;
and to correctly reject a forged-but-self-consistent WORLD_RECORDS payload,
a tampered RESULT aggregate, and a fabricated conclusions block.

## MAJOR — per-world authorization overhead (closed)

`open_v2_production_session` authorizes once (historical auth + V1 TCB
check) and returns an immutable `V2ProductionSession`; each world executes
through `evaluate_v2_world_in_session`/`run_canonical_v2_production_grid_in_session`
without re-verifying git/TCB/ARM state per world. The session grants no
forgeable "authorized=True" boolean by itself — `mint_v2_world_records` /
`mint_v2_result` / `verify_historical_v2_result` never accept or trust a
session object; they always independently re-establish authority from git
objects. The session is strictly an operational optimization, exactly as
required.

## No scientific reimplementation (unchanged from the prior unit)

Per-world classification is still delegated verbatim to the frozen fixture's
private `_evaluate_v2_world_inner`. Worlds are still built via the frozen,
unmodified `simulate_dgp`. No caller-supplied world, seed, or scientific
parameter is ever accepted.

## V1 failure history preserved

- `V1_ATTEMPT_STATUS = INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- `V1_3087_SUBSET_CLAIMABLE = false`

## KNOWN_LIMITATIONS

- **Inherited-ladder mapping** (see BLOCKER 4 above): the 33 conclusion ids'
  original V1-methodology verdicts must be supplied by a separate, frozen,
  independently reviewed mapping before a real mint. This is the one
  remaining piece of "what does this specific inherited claim mechanically
  evaluate to" that this repair unit deliberately does not invent.
- The reservation/claim durability model matches V1's own already-accepted
  guarantee level (git-native "first commit wins" exclusion checked at
  authorization time), not a stronger distributed lock; this is a deliberate
  match to precedent, not a shortfall relative to it.
- `V2DurablePartialWorldStore` is a new, non-frozen class analogous to (but
  not literally reusing) V1's `DurablePartialWorldStore`, since the latter is
  hardcoded to V1's own record/job shape. It reuses V1's atomic-write
  primitives verbatim; only the per-world dataclass (de)serialization and
  identity-binding glue is V2-specific, non-scientific plumbing.

## Next required step

`INDEPENDENT_V2_PRODUCTION_LIFECYCLE_REREVIEW`. This unit is not
self-certifying; the report accompanying this commit lists exact test
commands/results/exclusions for that review to verify independently.
