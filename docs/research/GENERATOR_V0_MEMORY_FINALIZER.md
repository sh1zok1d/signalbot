# Generator V0 — memory finalizer V1

**Status:** `ACTIVE / CANONICAL`  
**Date:** 2026-09-24  
**Mode:** offline infrastructure; no provider calls, no market data, no protected data

```
NO_SCIENTIFIC_STATUS   = true
MARKET_OUTCOMES_TESTED = false
PROTECTED_DATA_OPENED  = false
```

This replaces the manual memory-ingestion workflow. After a completed Generator V0
campaign, one deterministic command turns the structured campaign record into an
append-only memory event. No LLM decides what is written.

```
completed campaign -> deterministic validation -> MEMORY_DELTA -> append-only event
  -> derive full mechanism memory -> derive blind generator projection
  -> derive novelty governance authority -> verify chain and role boundaries
  -> atomic publish (HEAD switch) -> MEMORY_FINALIZED
```

Code: `scripts/research/generator_v0/memory_store.py` (chain, replay, projections,
publish), `memory_finalizer.py` (rules, source adapters, dispositions),
`finalize_memory.py` (operator CLI). Tests: `tests/research/test_generator_v0_memory_finalizer.py`.

## 1. Authority model

The **event chain** in `docs/research/generator_v0_memory/` is the historical
authority:

- `events/NNNNNN-<EVENT_HASH>.json`: one event per finalization;
- `deltas/<SHA256>.json`: the append-only delta each event binds;
- `snapshots/NNNNNN-<hash16>/`: an immutable copy of the replayed state at each event;
- `HEAD.json`: the chain head, which is the only publish point.

Each event binds `SCHEMA_VERSION`, `EVENT_TYPE`, `SEQUENCE`, `CAMPAIGN_ID`,
`SOURCE_ARTIFACT_IDENTITY`, `SOURCE_SHA256`, `PREVIOUS_EVENT_HASH`,
`MEMORY_DELTA_SHA256`, `RULES_DIGEST`, `FINALIZER_CODE_DIGEST`, the resulting memory,
blind-map, authority and attempt digests, a `SUMMARY`, and `EVENT_HASH`. `EVENT_HASH`
is SHA256 of the canonical event without `EVENT_HASH`. Each event names the previous
`EVENT_HASH`, so editing any old event or delta breaks verification.

The current memory is whatever deterministic replay of `LEGACY_BOOTSTRAP` + deltas
produces under the frozen design rules. Replay never re-derives from campaign
sources and never consults Git.

### Frozen design vs dynamic memory

`HYPOTHESIS_GENERATOR_V0_DESIGN.json` keeps the rules: schemas, role boundaries,
relation semantics, the novelty decision table, state meanings, projection rules and
anti-rescue policy. It no longer embeds governance ROWS. `ROWS_SOURCE` points here.
`GOVERNANCE_REGION_AUTHORITY_V0` is the design's governance header plus ROWS projected
from memory. Finalization never edits the design. The old `context.materialize()`,
which rebuilt authority from the design's embedded copy, is removed.

### Derived caches

These files are **byte copies of the head snapshot**, kept for compatibility:

- `MECHANISM_MEMORY_V0.json`
- `BLIND_MECHANISM_MAP_V0.json`
- `GOVERNANCE_REGION_AUTHORITY_V0.json`

`GENERATOR_V0_CONTEXT_PINS.json` is a runtime drift cache over the design, the
rotation file, those three mirrors and `HEAD.json`. It is regenerated from the
published snapshot. It is **not** a trust root: re-pinning proves nothing about
history, only the chain does. At runtime, `Contexts` checks the pins, replays the
chain, checks the head snapshot, and refuses any mirror that differs from it.

## 2. Two kinds of memory

**Full memory** covers `MECHANISM_MEMORY_V0` entries plus `ATTEMPT_RECORDS`. It
holds pipeline dispositions, critic verdicts, failed checks, blockers and provenance.
It may later hold market-test results (section 8). Only `HUMAN` reads it in full.

**Blind generator memory** is `BLIND_MECHANISM_MAP_V0`. It exposes only the design
whitelist `ID, MECHANISM, INFORMATION_SOURCE, FUNCTION, TARGET_FAMILY` plus
`REGION_STATE = PRIOR_WORK_SIGNATURE` for every signature. It never carries
PASS/REJECT, red-team verdicts, scientific classes, effect sizes, p-values,
profitability, or an outcome-based ranking. A survivor and a methodology-blocked
signature look the same to GENERATOR. Changing only non-whitelisted fields,
SUPPORTED vs NULL for instance, cannot change the blind projection (tested).

**Role access** is unchanged from the frozen role matrix:

| Role | Sees |
|---|---|
| GENERATOR | the blind map |
| NOVELTY_CRITIC | the blind map plus the outcome-neutral governance authority |
| FEASIBILITY_CRITIC | blocker requirements derived from the authority |
| RED_TEAM | only a scoped authority row |
| SELECTOR | none of these |

## 3. Attempts vs canonical signatures

Every valid generated candidate becomes an **attempt record** with stable ID
`CAMPAIGN_ID-CANDIDATE_ID`, for example `GV0CAL-C001`:

- `CAMPAIGN_ID` must match `^[A-Z][A-Z0-9]{2,15}$`, and `LEGACY` is reserved;
- `CANDIDATE_ID` must match `^C[0-9]{3}$`.

There is no global counter, so rebuilding the same campaign gives the same IDs.

Only a genuinely distinct mechanism region creates a **canonical signature**, meaning
a memory entry, a governance row and a blind row. The rules below are applied in
candidate-ID order.

| Structured record | Disposition | Signature |
|---|---|---|
| a prior relation `EXACT_DUPLICATE`, `PARAMETER_NEIGHBOR` or `FUNCTIONAL_RELABEL`, or the role's deterministic exact match | `LINKED_PRIOR_DUPLICATE_OR_NEIGHBOR` | none; linked to the prior signature |
| only `RESOLVES_BLOCKER` relations | `LINKED_PRIOR_BLOCKER_RESOLUTION_PROPOSAL` | none; the prior state is not rewritten |
| a non-orthogonal batch relation in either direction, or an identical deterministic signature to a lower ID | `LINKED_BATCH_DUPLICATE_OR_NEIGHBOR` | none; linked to the earlier attempt's signature |
| distinct: red team passed, feasibility passed, `DATA_READY` (the `EXECUTABLE_NOW` stream) | `NEW_SIGNATURE_CONSUMED` | new, `CONSUMED` |
| distinct with any blocker | `NEW_SIGNATURE_DEFERRED_OR_BLOCKED` | new, `DEFERRED_OR_BLOCKED` |
| critic chain incomplete | `REVIEW_INCOMPLETE_NO_SIGNATURE` | none |
| invalid or unparseable generator output | provenance only (`INVALID_OUTPUTS` in the delta) | none, and no attempt record |

`CONSUMED` means only "this prior signature was already generated; do not
regenerate it cosmetically". It does not mean scientifically supported.
`DEFERRED_OR_BLOCKED` means methodology- or data-blocked, not a scientific null.

The finalizer cross-checks every record. The novelty verdict must follow from its
relations under the frozen table. The recorded stream must follow from the critic
verdicts. Relations must name known signatures. Anything inconsistent fails closed.

## 4. Deterministic blocker mapping

Blocker classes come only from structured checks. Free-form or hidden reasoning is
never read.

**RED_TEAM:** rules are ordered and the first match wins; every listed check must be
false for the rule to match.

| Failed checks | Class |
|---|---|
| `NO_LOOKAHEAD` | `METHOD_LOOKAHEAD_VIOLATION` |
| `CAUSALITY` and `CONFOUNDING_ADDRESSED` | `METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING` |
| `CAUSALITY` | `METHOD_CAUSAL_IDENTIFICATION_INADEQUATE` |
| `CONFOUNDING_ADDRESSED` | `METHOD_CONFOUNDING_CONTROL_INADEQUATE` |
| `FALSIFIABLE` | `METHOD_FALSIFIER_INADEQUATE` |
| `BOUNDED_SEARCH` | `METHOD_UNBOUNDED_SEARCH_SURFACE` |
| `NO_TRADING_CLAIM` | `METHOD_TRADING_CLAIM_OUT_OF_SCOPE` |

**Feasibility:**

| Condition | Class |
|---|---|
| `REJECT` with `LEGAL_RANGE` false | `DATA_LEGAL_RANGE_NOT_SATISFIED` |
| any other `REJECT` | `DATA_READY_CLAIM_NOT_CONFIRMED` |
| `HUMAN_REVIEW` | `DATA_STATUS_DISAGREEMENT_REQUIRES_HUMAN_REVIEW` |
| non-ready data status | `DATA_FEASIBILITY_REQUIRED`, or the `DATA_BLOCKED_*` status itself |

The primary blocker is the first in the order red team, then feasibility verdict,
then data status. It becomes the row's `BLOCKER_CLASS_IF_ANY`. Secondary blockers
are listed in the requirement text and on the attempt record. Requirement texts and
anti-rescue scopes are fixed templates.

## 5. Signature text

The blind and governance text of a new signature is built as follows:

| Field | Source |
|---|---|
| `MECHANISM` | card `NAME` |
| `FUNCTION` | card `FUNCTION` |
| `INFORMATION_SOURCE` | card class plus its `DATA_REQUIRED` datasets |
| `TARGET_FAMILY` | card `PRIMARY_TARGET` |

Any token matching one of these patterns is replaced by `(omitted)`:

- the frozen generator denylist;
- the blind state-language rules;
- the governance outcome rules (years, decimals, p-values, PASS/FAIL, gate/profit wording).

Without this scrub, ordinary card words such as "positive" or "executed" would
hard-fail the next generator context. The verbatim card stays on the attempt record.

## 6. Atomic publish, idempotency, crash safety

`--apply` runs these steps under an exclusive lock:

1. read and fully verify the current chain;
2. build the delta, event and snapshot in `.staging/`;
3. validate the staged bytes;
4. place the content-addressed files;
5. verify the full chain as it will be published;
6. switch `HEAD.json` with one `os.replace`, which is the publish point;
7. regenerate the mirrors and pins.

A crash before step 6 leaves HEAD and every reachable file unchanged. Placed files
are unreachable orphans, and a retry reuses their identical bytes. A crash after
step 6 leaves stale mirrors, which runtime refuses. Re-running the same `--apply`
repairs them.

| Situation | Result |
|---|---|
| same `CAMPAIGN_ID`, same `SOURCE_SHA256`, already finalized | `ALREADY_FINALIZED`: no new event, no new IDs, no drift |
| same `CAMPAIGN_ID`, different `SOURCE_SHA256` | hard failure; a finalized campaign is never reinterpreted |

`SOURCE_SHA256` is:

- for the calibration export, the SHA256 of the file bytes (so the export must not be edited);
- for a run journal, the digest of the completed campaign result payload.

## 7. Legacy bootstrap and GV0CAL

- **Event 0 (`LEGACY_BOOTSTRAP`)** carries verbatim the 30 pre-GV0CAL memory entries
  and governance rows from commit `d4b28dea18a64b3ed00339ebdcde539a78e4d1e1`, with no
  scientific reinterpretation. Replaying it reproduces that commit's memory, blind-map
  and authority files byte for byte.
- **Event 1 (`GV0CAL`)** comes from `GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json`
  and matches the golden states of the manual ingestion:
  - C001/C002/C005: `CONSUMED`;
  - C003: `DEFERRED_OR_BLOCKED`, `METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING`;
  - C004: `DEFERRED_OR_BLOCKED`, `METHOD_CONFOUNDING_CONTROL_INADEQUATE`.

The export records novelty verdicts but not relation values. Under the frozen table
only `ORTHOGONAL_MECHANISM` gives `ALLOW` for every state, so its `ALLOW` verdicts
prove there are no prior links. Any other verdict from that source fails closed.

The manual ingestion (`GENERATOR_V0_CALIBRATION_MEMORY_INGESTION.*`, commit
`64a37a9`) is the migration's golden reference and is preserved. Its hand-written
wording for the five signatures is superseded by the deterministic text from
section 5. IDs, states, blocker classes and blind-projection semantics are the same.

## 8. Market test results (`MARKET_TEST_RESULT`) and multiple testing

`MARKET_TEST_RESULT_EVENT = IMPLEMENTED` (2026-09-25). This section records the decision; it was previously reserved.

A `MARKET_TEST_RESULT` event attaches one frozen, executed scientific test to **full** memory of an existing signature.
- **Record.** It is appended as `MECHANISM_MEMORY_V0.MARKET_TEST_RESULTS[TEST_FAMILY_ID]`.
- **Identity.** It carries the signature and hypothesis identity, the prereg and permit identity (prereg SHA256, permit path and pre-outcome commit), the test-family and search-family IDs, and the result provenance (path, SHA256, schema). It also carries the frozen classification and evidence tier, the multiplicity counts and method, the dataset snapshot, and the primary, controlled and gate values copied verbatim. A fixed statement says it is not a validated edge.
- **Append-only.** `ADD_ENTRIES`, `ADD_ROWS` and `ATTEMPTS` must be empty. Existing entries, governance rows (including `STATE = CONSUMED`) and attempt records are never rewritten.
- **Blind boundary.** The blind map, governance authority and attempt records are byte-identical before and after. The finalizer fails closed if any of their digests would change. Generator and novelty contexts therefore never see a classification, p-value, effect, gate or yearly value. `CONSUMED` still means only "already generated; do not cosmetically regenerate".
- **Source.** `source_from_market_test_result` reads the canonical result file and the `SCIENTIFIC_TEST_LEDGER.json` entry for its test family. It binds that entry by its own digest, not the whole growing ledger. It also reads the prereg and the execution permit. It fails closed unless all of these hold:
  - the result SHA256 matches the ledger;
  - the classification matches between ledger and result;
  - the ledger `STATUS = EXECUTED` and `RERUN_AUTHORIZED = false`;
  - the prereg SHA256 agrees across ledger, result and permit;
  - the permit authorizes exactly this one-shot test;
  - the search family exists once, and `EXECUTED_TESTS` counts this execution;
  - the result attests protected 2025/2026 unopened;
  - the hypothesis is the attempt record that generated the signature.
- **Unit and idempotence.** The unit ID is `TEST_FAMILY_ID` without `TF-` and without hyphens, for example `GV0R01C013MT1`. It occupies the historical `CAMPAIGN_ID` event field, which stays unique across the chain. Re-running the same source is a no-op (`ALREADY_FINALIZED`). The same test family with a different source is a hard failure. A second, distinct test family may attach to the same signature.
- **Schema.** It stays `GENERATOR_V0_MEMORY_CHAIN_V1`, and old events replay exactly as before. The event carries the same fields, uses the same atomic HEAD publish, and has the same crash and repair semantics as `CAMPAIGN_FINALIZATION`.

First event: `GV0R01C013MT1` at sequence 3, event `853ef4514460a18b5aa16bf3fff86ece027c52e4b58d92dfbf98034f1fde9373`, delta `3b7c5485…`. It attaches `TF-GV0R01-C013-MT1`, classified `PROMISING_PROTOTYPE`, which is discovery tier and not a validated edge. The chain is `LEGACY_BOOTSTRAP → GV0CAL → GV0R01 → GV0R01C013MT1`. Memory holds 57 entries, 35 attempt records and 1 market result.

Generated hypotheses are not executed market tests. `docs/research/SCIENTIFIC_TEST_LEDGER.json` counts executed scientific tests and search families, not generated cards. The finalizer copies a frozen classification and never creates or upgrades one.

## 9. Operator commands

```bash
python -m scripts.research.generator_v0.finalize_memory --verify
python -m scripts.research.generator_v0.finalize_memory --rebuild
python -m scripts.research.generator_v0.finalize_memory --dry-run --campaign-id <ID> --run-journal <run.sqlite>
python -m scripts.research.generator_v0.finalize_memory --apply   --campaign-id <ID> --run-journal <run.sqlite>
python -m scripts.research.generator_v0.finalize_memory --dry-run --market-test-result <result.json>
python -m scripts.research.generator_v0.finalize_memory --apply   --market-test-result <result.json>
```

- **`--dry-run`** writes nothing. It prints the campaign ID, source hash, previous
  head, attempt/new-signature/link counts and the resulting digests.
- **`--apply`** fails closed on any verification error.
- **`--verify`** checks every event hash, link and delta digest, replay, snapshots,
  blind projection, governance coverage, duplicate IDs, mirrors and pins.
- **`--rebuild`** replays bootstrap + deltas and compares the result with every
  published snapshot.

The run journal must be the completed campaign's `run.sqlite`. Finalize in the same
VM (`docs/AGENT_RUNTIME_PROTOCOL.md` §3), then commit the chain.
