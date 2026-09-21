# FORWARD_MARKET_OBSERVABILITY_V1 — Collector Refreeze (ARM Lifecycle Repair)

Status: `FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_REFROZEN_OUTCOME_BLIND`
Date: 2026-09-19

## What this is

This is **infrastructure**, not a scientific experiment.
`scientific_outcomes_forbidden = true` is enforced structurally throughout
this program and remains true after this refreeze.

## Why a refreeze was needed

The previous freeze
(`docs/research/FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.json`,
commit `7dfae71b8d3cfe7c941f489f5502813dba7272e9`) described collector bytes
that could **never** themselves transition into authoritative collection:

- `cli.py`'s `collect` subcommand called `_refuse_authoritative()`
  unconditionally, regardless of any config, artifact, or network outcome.
- `default_config()` hardcoded `authoritative_collection_authorized = False`
  as a field nothing ever read.

This is the same defect class already found and repaired for MARKET-05
(see `docs/research/MARKET_05_IMPLEMENTATION_REFREEZE.json`). The fix here
mirrors that repair's shape exactly: a genuine lifecycle repair, not a
constant flip, and not a restatement of the old freeze.

## What changed

- Added `authority_root.py`: an independent, git-blob-id-anchored root of
  trust. Pins the git blob id of every collector/authority file (including
  `collection_authority.py`), and separately anchors its own integrity by
  comparing its live bytes against the frozen `collector_source_head` commit
  recorded in this refreeze artifact. Fails closed — no exported-tree /
  no-git authorization mode exists.
- Added `collection_authority.py`: authenticates an external
  `FORWARD_MARKET_OBSERVABILITY_V1_COLLECTION_ARM.json` artifact by bound
  content (program id, frozen source head/tree, per-file implementation
  hashes, schema identities, instrument/market/venue, source definitions,
  `legal_available_at_rule`, `scientific_outcomes_forbidden`,
  `market_06_created=false`, `m04_fwd_created=false`, a deterministic
  `collection_run_identity`, and `authoritative_collection_authorized`).
  Verification order: independent authority root first, then frozen
  collector bytes, before any ARM field is trusted.
- Added `schemas.classify_source_observation_validity()` and threaded a new
  `source_observation_valid` field through `envelope.py`/`collector.py`/
  `health.py`. REST is valid only on the expected 2xx status AND a
  schema-valid native payload; WS is valid only on a schema-valid native
  payload. HTTP error bodies and malformed/control frames are retained
  operationally (for diagnostics) but are **never** counted as valid market
  observations.
- Rewrote `cli.py` with three subcommands:
  - `smoke` — always infrastructure-only, always excluded from any
    authoritative accounting.
  - `readiness` — a fresh, infra-only probe of all three frozen sources.
    Also always excluded from authoritative accounting.
  - `collect` — authenticates the collection ARM, re-probes readiness
    fresh (never reuses a `smoke`/`readiness` session), and only then
    starts a **new** authoritative session.
- Removed the dead `authoritative_collection_authorized` config field from
  `default_config()`; bumped the config schema to
  `forward_market_observability_v1_config/1.1.0`.
- `session.py` gained explicit `authoritative_collection` /
  `collection_authority_identity` handling with mutual-exclusivity guards
  against non-authoritative labels (`INFRASTRUCTURE_SMOKE_TEST_ONLY`,
  `INFRASTRUCTURE_READINESS_CHECK_ONLY`).

## What this refreeze deliberately does NOT do

- Does not create `FORWARD_MARKET_OBSERVABILITY_V1_COLLECTION_ARM.json`/`.md`.
  No collection ARM exists yet. `armed = false`,
  `authoritative_collection_authorized = false` in this artifact.
- Does not start authoritative collection.
  `authoritative_collection_started = false`.
- Does not create MARKET-06 or M04-FWD.
  `market_06_created = false`, `m04_fwd_created = false`.
- Does not inspect, compute, or reason about any scientific outcome.
  `scientific_outcomes_inspected = false`.
- Does not touch canonical V3, E1-RUN-001, or MARKET-01/03/05 artifacts.

## Two-commit provenance (avoiding circularity)

Following the MARKET-05 pattern, this repair uses two distinct commit
identities:

- **`collector_source_head` / `collector_source_tree`** — the commit
  containing all repaired collector SOURCE and its tests, with no
  collection ARM and no refreeze artifact yet in that same commit.
- A later, separate, **docs-only** commit records this refreeze artifact
  (recording the source commit's own hash) and changes no collector source
  file. That later commit is never itself the `collector_source_head`/
  `collector_source_tree` recorded here — a file cannot embed a literal
  constant equal to the hash of the commit that contains it.

## Next unit

`FORWARD_MARKET_OBSERVABILITY_V1_SOURCE_READINESS_CHECK` — run the frozen
`readiness` CLI command from the actual deployment environment against the
live Binance endpoints. Only if all three sources
(`MARK_PRICE_WS_NATIVE_READY`, `PREMIUM_INDEX_NATIVE_READY`,
`OPEN_INTEREST_NATIVE_READY`) report ready may a collection ARM be created
and authoritative collection be started. If any is not ready, the correct
outcome is `FORWARD_OBSERVABILITY_SOURCE_NOT_READY` — no ARM, no
authoritative start timestamp.
