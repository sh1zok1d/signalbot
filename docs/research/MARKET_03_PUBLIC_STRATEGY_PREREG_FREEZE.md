# MARKET-03 PUBLIC STRATEGY REPLICATION — prereg freeze authority

- **Status:** `FROZEN_OUTCOME_BLIND`
- **Unit ID:** `MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Date:** 2026-09-18

**Not a RESULT. Not an ARM. Not MARKET-03 execution. Not implementation.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

This document is a docs-only PREREG FREEZE record. It establishes that
the exact already-materialized MARKET-03 preregistration bytes — at
materialization commit `06d6ec0121a9a35f8ee947fbe89e37e97388b6e2` /
tree `50bc810eb127ea7aea1843ef2ede0dd4fe8905d1` — are the sole
scientific authority for later MARKET-03 implementation.

It does **not** modify those prereg files, rewrite any scientific
choice in them, implement the strategy, inspect MARKET outcomes,
execute MARKET-03, ARM, or open protected OOS.

Canonical machine-readable twin:
`docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.json`.

The prereg files' internal status string (`PREREGISTERED_OUTCOME_BLIND`)
is left unchanged because those exact bytes are the frozen object.
Current freeze authority is **this document**, not that internal label.

---

## Bound content

```text
PRE_PREREG_HEAD = 9454af65398df1d3f5e0cb3af5e48c0986049d2d
PRE_PREREG_TREE = 27531689a1185dda7946f6742d725a87477911e2

ACCEPTED_PREREG_CONTENT_HEAD = 06d6ec0121a9a35f8ee947fbe89e37e97388b6e2
ACCEPTED_PREREG_CONTENT_TREE = 50bc810eb127ea7aea1843ef2ede0dd4fe8905d1

FREEZE_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
FREEZE_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

The freeze commit's `freeze_commit_head` / `freeze_commit_tree` remain
`UNSET_UNTIL_THIS_COMMIT` so this artifact never depends on a circular
self-hash of its own freeze-commit digest — matching the established
repository freeze convention.

---

## Frozen prereg artifacts

Independently recomputed from
`git cat-file -p 06d6ec0121a9a35f8ee947fbe89e37e97388b6e2:<path>`
immediately before writing this freeze. Neither file's bytes are touched
by this commit.

```text
docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md
  SHA256 = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
  size   = 15063 bytes

docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json
  SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
  size   = 15587 bytes
```

---

## Authority chain

```text
DESIGN_COMMIT              = 9454af65398df1d3f5e0cb3af5e48c0986049d2d
DESIGN_TREE                = 27531689a1185dda7946f6742d725a87477911e2
DESIGN_JSON_SHA256         = 91e3624988442901a21693dabd3eb4bfa9502d2fa6ccd8df9b6a7f9e04146a57
PREREG_MATERIALIZATION     = 06d6ec0121a9a35f8ee947fbe89e37e97388b6e2
                             (tree 50bc810eb127ea7aea1843ef2ede0dd4fe8905d1)
```

External source bound in the frozen prereg:

```text
EXTERNAL_REPO   = https://github.com/wiktorj137/btc-strategy-lab
EXTERNAL_COMMIT = b68a5518b4a3eba2fde1733160d7d7de356023b5
EXTERNAL_TREE   = f7717e681c911ea3ccce15492246053cf15883cb
FAMILY          = EmaCross vs EmaCrossFunding
```

---

## Data authorities already contained in the frozen prereg (cross-check only)

```text
SPOT dataset_id     = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT snapshot_id    = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256    = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4

FUNDING             = PRE-ARM REQUIRED ARTIFACT
PROPOSED_DATASET_ID = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
REST_JSONL_SHA256   = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
FUNDING_SNAPSHOT_READY = NO
B2-06 is not MARKET-03 funding authority

WARMUP_INTERVAL     = [2019-08-07T20:00:00Z, 2019-10-01T00:00:00Z)
EVALUATION_INTERVAL = [2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

Primary metric: signed `metrics.py` wallet MDD (`float(dd.min())`).
Primary equation: `REPRODUCED_DIRECTION iff finite(MDD_filtered) and finite(MDD_baseline) and (MDD_filtered > MDD_baseline)`.
Replication level: `LEVEL_2_FAITHFUL_REIMPLEMENTATION`.

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
6. No MARKET-03 execution is authorized.
7. No ARM is authorized.
8. Canonical executions authorized remains 0. Consumed remains 0.
9. Protected 2025 validation and 2026 OOS remain forbidden.
10. B2-06 remains unauthorized and is not MARKET-03 funding authority.
11. Funding named snapshot remains a pre-ARM required artifact.
12. No selective rerun / post-outcome threshold repair.
13. Magnitude and secondary metrics cannot promote a failed direction.

---

## Preserved limitations

1. MARKET-03 is historical reproduction, not independent replication.
2. Evaluation is truncated versus the author's open-ended `20191001-`.
3. `STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN`.
4. `REPRODUCTION_FUNDINGTIME_ASSUMPTION = ACCEPTABLE` is a reproduction
   assumption only.
5. No p-value / bootstrap gate.
6. `DEFAULT_V4 = NO`.
7. `REPRODUCED_DIRECTION`, if it ever occurs later, does **not** mean
   current alpha, live profitability, causal funding effect, independent
   replication, OOS confirmation, validation of the author's selection
   pipeline, calibrated statistical evidence, or proven publication timing.

---

## Explicit state

```text
market_03_outcome_inspected              = false
market_03_prereg_materialized            = true
market_03_prereg_ready                   = true
market_03_prereg_frozen                  = true
market_03_freeze_required                = false
market_03_executed                       = false
market_03_armed                          = false
market_03_implementation_authorized      = true   (frozen contract only)
market_03_execution_authorized           = false
canonical_executions_authorized          = 0
canonical_executions_consumed            = 0
funding_snapshot_ready                   = false
protected_oos_authorized                 = false
protected_oos_touched                    = false
b2_06_execution_authorized               = false
default_v4                               = false
```

Do **not** mark ARMED, EXECUTING, EXECUTED, or RESULT. No
outcome-dependent state is legal in this unit.

---

## Next lifecycle state

Implementation of the already-frozen MARKET-03 contract, including the
pre-ARM funding snapshot identity wrap.

Not execution. Not ARM.

---

## Validation performed before this commit

- `git cat-file -p 06d6ec01…:docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.md` → SHA256 matched `044bb2a6…`.
- `git cat-file -p 06d6ec01…:docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG.json` → SHA256 matched `3f35f9a1…`.
- Prereg files are not modified by this freeze commit.
