# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY — production driver

**Status: `PRODUCTION_LIFECYCLE_IMPLEMENTATION_AWAITING_INDEPENDENT_REVIEW` (session/reservation-authorization narrow repair applied; inherited-ladder binding intentionally stopped pending a methodology amendment — see below).**

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
3. A repair unit closed BLOCKER 1 and wired the aggregation machinery, but a
   second independent rereview found the session/reservation repair
   incomplete: `evaluate_v2_world_in_session` accepted a forged/`None`
   session with no ARM anywhere in the repository, the reservation
   primitives were never actually invoked by the execution path (two
   sessions against the same unreserved ARM both fully executed), and
   `inherited_detection_conclusions` was an unverified caller parameter that
   could change the final RESULT's conclusions for identical evidence.
4. **This unit** makes the session object unforgeable, wires reservation
   into the required VERIFY → RESERVE → OPEN SESSION → EXECUTE ordering, and
   performs (per an explicit stop condition) a provenance audit of the
   inherited-ladder mapping rather than implementing it — see
   `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_PROVENANCE_AUDIT.md`.

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

## BLOCKER 2 — durable one-shot authority: reservation now gates execution (closed)

Previously, `assert_v2_reservation_available` existed but was never called by
anything on the execution path — two sessions against the same unreserved ARM
both fully executed. This unit adds `establish_v2_durable_reservation(repo_root,
arm_commit)`, which enforces the required ordering by construction:

```
VERIFY ARM  ->  VERIFY PLAN/POLICY/TCB  ->  ESTABLISH DURABLE RESERVATION  ->  OPEN SESSION  ->  EXECUTE
```

It re-checks `assert_v2_reservation_available` immediately before writing,
writes the reservation document via the same atomic-write primitive used for
checkpoints, and commits it. `open_v2_production_session` now refuses unless
a matching reservation is already tracked at HEAD
(`_verify_v2_reservation_committed`) — there is no path from "ARM exists" to
"scientific computation happens" that skips reservation.

**Guarantee level, stated precisely (not oversold):** within one shared git
repository/checkout, this is airtight — git's own commit/ref locking means
only one reservation commit can ever land as HEAD's next commit; a losing
concurrent `git commit` call fails and `establish_v2_durable_reservation`
converts that into a clean refusal before either process could have reached
`open_v2_production_session`. Proven by test: two real (not merely
standalone-check) attempts through `establish_v2_durable_reservation`, with
one already having executed via a genuine session, the second still fails
closed; a "crash after reservation, before any world" scenario (a fresh
session opened later against the same, still-durable, reservation) proceeds
correctly without needing or being able to create a second reservation.
Across independent, not-yet-synchronized clones (no shared filesystem,
communication only via eventual git push/fetch), this repository-local
design cannot detect a concurrent reservation attempt in a *different* clone
before both begin computation. This residual race is not weakened away or
hidden: it requires operational discipline (a single authoritative execution
host/clone, or an external distributed lock/CI concurrency guard) beyond
what git commits alone provide. Even then, only one reservation/evidence/
RESULT chain can ever become part of the single shared canonical remote
history (the loser's push is rejected as non-fast-forward and must not be
force-pushed or auto-retried) — wasted duplicate computation is possible in
that scenario, a duplicate *authoritative* RESULT is not.

## Genuine, unforgeable session (closed)

Previously, `evaluate_v2_world_in_session(None, "NULL", 5000, 0)` executed
successfully with no ARM anywhere in the repository — the session object was
never validated. `V2ProductionSession` is now `@dataclass(frozen=True,
eq=False)`: `eq=False` makes its identity fall back to plain object identity
(`id()`) instead of dataclass structural equality, so a copy with identical
field values is not the same session. A module-private
`_SESSION_REGISTRY` (`WeakKeyDictionary`) is populated only by
`_issue_v2_production_session` — called by `open_v2_production_session` and,
internally, by `mint_v2_world_records`/`verify_historical_v2_result` (which
still independently re-establish authority themselves first; they never
trust a caller-supplied session) — storing a snapshot of the session's bound
fields at issuance. `_require_genuine_session` rejects anything that is not
literally a registered object, or whose current fields no longer match the
stored snapshot (catching mutation via `object.__setattr__`, which bypasses
`frozen=True`). Proven by test against `None`, `False`, `True`, `{}`, a
manually-instantiated `V2ProductionSession` with copied field values, a
`dataclasses.replace()` copy, a bare string, and a mutated genuine session —
all refused before `simulate_dgp` is ever called; a freshly-issued genuine
session still works. This defends against callers who do not go through the
intended API; it does not defend against an adversary with arbitrary code
execution in the same interpreter (who could reach into the registry
directly) — that matches Python's actual security ceiling, not a gap
specific to this design.

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

**Explicit, deliberate scope boundary, now backed by a full provenance
audit:** `mechanical_conclusion_v2`'s third input, the inherited V1-ladder
verdict for each of the 33 named conclusions, is **not** computed by this
unit. A dedicated audit
(`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_PROVENANCE_AUDIT.md`)
traced every one of the 33 ids against the frozen V1 prereg's `acceptance`
and `conclusion_authority` sections and Amendment_001's explicit map: 18 are
mechanically unambiguous (explicit frozen thresholds, banding rules, or
floor rules), 15 are not yet confirmed unambiguous (either no explicit
threshold exists at all, or resolving them would require inferring an alias
relationship the frozen text does not itself state). Per the governing stop
condition, since not all 33 are unambiguous, this unit does not implement
the mapping — doing so for even the 18 alone while leaving the rest
caller-supplied would not close the underlying finding (a caller could still
alter the 15 unresolved verdicts). `derive_v2_mechanical_conclusions`
therefore still takes `inherited_detection_conclusions` as a **required**
parameter (fails closed if any of the 33 ids is missing) that a **separate,
dedicated, independently reviewed methodology amendment** must supply before
a real mint. See `KNOWN_LIMITATIONS`.

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

## MAJOR — per-world authorization overhead (closed, without reintroducing forgeability)

`open_v2_production_session` authorizes once (TCB + historical ARM authority
+ durable reservation, in that order) and returns an unforgeable
`V2ProductionSession` (see above); each world executes through
`evaluate_v2_world_in_session`/`run_canonical_v2_production_grid_in_session`
without re-verifying git/TCB/ARM/reservation state per world — but every call
does re-verify session genuineness against the private registry (an O(1)
dict lookup and field comparison, not a git subprocess call), so the
performance objective is preserved. `mint_v2_world_records` /
`mint_v2_result` / `verify_historical_v2_result` still never accept or trust
a caller-supplied session; they always independently re-establish authority
from git objects and issue (and register) their own internal session purely
to reuse the per-world evaluation code path.

## No scientific reimplementation (unchanged from the prior unit)

Per-world classification is still delegated verbatim to the frozen fixture's
private `_evaluate_v2_world_inner`. Worlds are still built via the frozen,
unmodified `simulate_dgp`. No caller-supplied world, seed, or scientific
parameter is ever accepted.

## V1 failure history preserved

- `V1_ATTEMPT_STATUS = INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- `V1_3087_SUBSET_CLAIMABLE = false`

## KNOWN_LIMITATIONS

- **Inherited-ladder mapping is still caller-supplied, deliberately.** A
  provenance audit of frozen V1/V2 material
  (`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_PROVENANCE_AUDIT.md`)
  found only 18 of the 33 required-coverage-map conclusion ids are
  mechanically unambiguous from already-frozen sources; the remaining 15
  require either locating more frozen source text or an explicit
  methodology amendment. Per the governing stop condition, this unit does
  **not** implement the mapping and does **not** remove
  `inherited_detection_conclusions` as a caller-supplied parameter — doing
  either would require inventing or inferring at least one of the 15
  unresolved verdicts. Consequently `RESULT_SCIENTIFIC_PAYLOAD_SELF_CONTAINED`
  remains `NO` and a caller can still change the final conclusion for
  identical evidence by supplying a different mapping; this is unchanged
  from the prior rereview's finding and is intentionally NOT worked around
  here. Next step: `PRE_OUTCOME_INHERITED_LADDER_METHODOLOGY_AMENDMENT`.
- The reservation durability model's precise guarantee (airtight within one
  shared repository; a residual, explicitly-documented race across
  independent unsynchronized clones) is stated above, not merely asserted by
  analogy to V1.
- `V2DurablePartialWorldStore` is a new, non-frozen class analogous to (but
  not literally reusing) V1's `DurablePartialWorldStore`, since the latter is
  hardcoded to V1's own record/job shape. It reuses V1's atomic-write
  primitives verbatim; only the per-world dataclass (de)serialization and
  identity-binding glue is V2-specific, non-scientific plumbing.
- The genuine-session registry is a process-local, in-memory mechanism (a
  `WeakKeyDictionary`); it does not and cannot persist across process
  restarts, which is correct and intentional -- a session is only ever
  meant to be a same-process, same-run authorization artifact. Durable,
  cross-process state is the reservation's job (git-committed), not the
  session's.

## Next required step

If a future unit resolves the inherited-ladder audit to 33/33 unambiguous
and binds the mapping (Section E of the repair task this unit executed),
next is `INDEPENDENT_V2_FINAL_PRE_FREEZE_REREVIEW`. Until then:
`PRE_OUTCOME_INHERITED_LADDER_METHODOLOGY_AMENDMENT`. This unit is not
self-certifying; the report accompanying this commit lists exact test
commands/results/exclusions for that review to verify independently.
