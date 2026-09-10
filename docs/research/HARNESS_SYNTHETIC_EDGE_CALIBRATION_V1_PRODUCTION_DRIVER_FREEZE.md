# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production execution-driver implementation freeze

**Status:** `PRODUCTION_DRIVER_IMPLEMENTATION_FROZEN_UNARMED`

**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`

**Canonical freeze artifact:** [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_DRIVER_FREEZE.json)

**Not a RESULT. Not Monte Carlo authorization. Not B2-06, 2025, or 2026 authorization.**

This document is a docs/metadata-only IMPLEMENTATION FREEZE record. It freezes
the exact independently reviewed production execution-driver implementation
identity. It does not rewrite frozen prereg or scientific lib bytes. It does
not arm production. It does not execute the 3200-world calibration. It does
not mint a RESULT or persist WORLD_RECORDS.

## Freeze semantics

The freeze commit is a docs/ledger/metadata descendant of the reviewed
implementation. It necessarily has a new HEAD and tree. This freeze does
**not** claim that the docs-only descendant itself was the exact code HEAD
reviewed by OPUS.

It freezes the implementation identity below.

```text
REVIEWED_IMPLEMENTATION_HEAD = 3fadc391ee0002e35463b526301d287d4a662828
REVIEWED_IMPLEMENTATION_TREE = 5fb77727c418cc42bf3c1c6553355a0475f42efc

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

No implementation, frozen scientific lib, or prereg bytes are changed between
the reviewed implementation and this freeze. The only test change is converting
the pre-freeze “canonical driver-freeze artifact is absent” assertion into a
live schema check of this freeze artifact. That is freeze validation, not
driver or scientific logic.

Future ARM verification reads this tracked freeze artifact at the authorized
parent. ARM cannot self-bless `reviewed_implementation_head == parent`.

## Freeze flags

```text
driver_implementation_frozen = true

production_monte_carlo_arm_authorized = false
production_calibration_executed = false
production_result_minted = false
world_records_persisted = false
authorization_consumed = false

B2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

## OPUS closure

```text
OPUS FINAL VERDICT = GO_FOR_DRIVER_FREEZE
BLOCKERS = 0
MAJORS = 0
```

GitHub CI for the reviewed implementation HEAD: run `34449032648` SUCCESS.

## Frozen scientific identity (byte-identical; not rewritten)

```text
scripts/research/harness_synthetic_edge_calibration_v1_lib.py
  SHA256 = 12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json
  SHA256 = 78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708

docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.md
  SHA256 = a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3
```

## Authority files the future ARM must bind

Exact SHA256 at reviewed implementation HEAD `3fadc391ee0002e35463b526301d287d4a662828`:

```text
lib        12230dcad714e3a06d3f57de69b78fedcab088be950af3d06f959366f01d6c51
runner     5d6e93f27584dfa181de86e43541fc927cbc143cdc5df66c2d63e988b9c41200
auth       0e174ac6b73530ec28501b0c076e0cad7874ab31bb1ed6941e4b525d12e35507
production 3fa11f9980bf1b51f4585cc53d8290c969887f277d85551dd65facd8b5d1e613
prereg_json 78fcddf03ce84a0369a955d5b571c2423129d12b22e35f77eab26d6ac5eff708
prereg_md   a54c838d2b4903f039b4fd39d79198415ce095f5a9726fc51949cbb47153e5a3
```

`reviewed_production_sha256` is the production durability/driver implementation
digest. Future ARM must bind that digest plus the frozen lib and prereg bytes
above. Execution-authority bytes at the freeze parent must remain identical to
the reviewed implementation.

## Architecture being frozen

The reviewed implementation provides:

- exact 3200 frozen production plan
- deterministic world identities/seeds
- no reroll
- invalid worlds preserved in the denominator
- fresh-process canonical execution
- canonical WORLD_RECORDS evidence
- RESULT derived from session records
- post-commit historical verification
- full 3200-world independent historical recomputation
- tracked WORLD_RECORDS treated as evidence, not authority
- historical recomputation in a fresh isolated `python -I -B -P` child
- no in-process authoritative fallback
- bound child verification proof
- durable RESULT claim explicitly binds WORLD_RECORDS digest/size
- spot-check diagnostic is non-authoritative
- protected B2-06 / validation / OOS scope flags

## Operational caveat

Full authoritative historical verification is intentionally expensive and
synchronous. Current observed single-world cost implies a complete 3200-world
verification may take many hours. The full end-to-end real production
verification path has not yet been run to completion.

This is an operational caveat only. It does **not** weaken the requirement
that durable production claim verification uses full recomputation.
Spot-check remains non-authoritative and cannot mint or validate durable
production claims.

## Required later sequence

```text
REVIEWED DRIVER IMPLEMENTATION
  3fadc391ee0002e35463b526301d287d4a662828
→ DRIVER FREEZE
  this docs-only descendant
→ fresh FINAL ARM immediate child
→ exactly one real 3200-world execution
→ captured WORLD_RECORDS + RESULT
→ persistence
→ authoritative historical verification
→ durable claim
```

This freeze does **not** create the ARM.

## What remains unauthorized

- production Monte Carlo arm
- production 3200-world calibration execution
- RESULT minting
- WORLD_RECORDS persistence
- B2-06 scientific execution
- 2025 validation
- 2026 out-of-sample

A later explicit ARM unit is still required before production execution.
The ARM must be an immediate child of this freeze commit, authorize this
freeze parent, and modify no execution-authority bytes.
