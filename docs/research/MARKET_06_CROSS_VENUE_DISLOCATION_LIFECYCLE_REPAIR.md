# MARKET-06 — Narrow Outcome-Blind Lifecycle Repair

Status: `LIFECYCLE_REPAIRED_OUTCOME_BLIND_NOT_EXECUTED`
Date: 2026-09-21

Repairs exactly three lifecycle defects found after the implementation
repair/refreeze. **No scientific definition changed and no prereg
amendment was made.**

- Pre-repair implementation: `378e8fd710040c5b4bd2471379b2ce4446ce80f2`
- Pre-repair freeze: `6fc1b62935a0cb6d6c6ddbee5b88a7ff1ac8a7d6`

## L10 — ARM / reservation self-reference

The permit's `arm_commit` defaulted to `HEAD`, and the reservation was then
read from `permit.arm_commit`. That made a normal lifecycle impossible: the
ARM and the reservation had to occupy the *same* commit.

The chain is now resolved reservation-first:

```
IMPLEMENTATION FREEZE F  ->  ARM commit A  ->  RESERVATION commit R  ->  CLAIM commit C
```

- `verify_execution_reservation_from_commit(R)` reads the reservation from
  `R`, extracts `arm_commit = A`, authenticates the ARM at exactly `A`, and
  requires `A` to be an ancestor of `R`.
- `verify_execution_arm()` with no `arm_commit` now refuses
  (`MARKET_06_ARM_COMMIT_REQUIRED`) instead of searching `HEAD`.
- No artifact contains its own commit SHA. Its authority is the commit it
  is read **from**. `SELF_REFERENTIAL_FIELDS`
  (`reservation_commit_sha`, `claim_commit_sha`, …) are rejected outright.

## L11 — durable pre-science claim

A local filesystem lock was the only guard before science, so a crash
between outcome computation and RESULT persistence silently returned the
one shot.

The durable tracked **CLAIM** is now the consumption point and must exist
*before* any market data is parsed:

1. freeze implementation → 2. red-team PASS → 3. ARM `A` →
4. reservation `R` → 5. **claim `C`** → 6. invoke runner against `C` →
7. runner authenticates `C → R → A → F` → 8. parse market data →
9. evaluate once → 10. persist deterministic RESULT.

`verify_claim_from_commit(C)` resolves the whole chain and refuses a claim
that carries any outcome field. A local append-only attempt ledger
(`.market_06_canonical_execution_attempts.json`) is fsynced *before*
reconstruction and is **never** rolled back on failure, so a second attempt
refuses with `MARKET_06_CANONICAL_RUN_ALREADY_CLAIMED` even when no RESULT
exists. `assert_claim_creatable` refuses a second claim for the same run
identity. A failure after the claim is `MARKET_06_INCOMPLETE_EXECUTION`
under an already-consumed claim — never an automatic rerun.

The filesystem lock remains only an immediate concurrency guard and is
documented as not a distributed mutex.

## L11 — deterministic RESULT persistence

`market_06_result_persistence` builds a canonical RESULT bound to
`research_id`, `run_identity`, the claim/reservation/ARM commits, the
implementation freeze, the prereg freeze, dataset/snapshot/durable root,
classification, gates, the prereg metrics, eligible support counts, the
reconstruction audit, and the bootstrap constants.

Canonical JSON (`sort_keys=True`, `allow_nan=False`, 2-space indent, single
trailing newline) defines `RESULT_PAYLOAD_SHA256`. Clock, UUID, hostname,
pid, user and path fields are rejected, so identical science always yields
identical bytes. Staging writes only the frozen target paths and does not
commit; the runner returns the exact bytes, paths and digest for the caller
to commit.

## L12 — data source commit override removed

`reconstruct_canonical_dataset` accepted `source_commit`, so a caller could
point canonical reconstruction at any commit whose manifest merely copied
the expected `dataset_id`/`snapshot_id` strings.

The parameter is gone. Canonical raw bytes come only from

```
CANONICAL_DATA_SOURCE_COMMIT = e2d543eadb5425473b6d4b8d24c177c1d7ae7930
```

Any `source_commit` / `source_ref` / `data_commit` / `dataset_commit` /
`path` keyword raises `MARKET_06_DATA_SOURCE_OVERRIDE_FORBIDDEN`. The
authority chain is: hardcoded frozen commit → immutable manifest at that
exact commit → immutable raw objects at that exact commit → exact
hashes/lengths → exact reconstruction.

## OKX window trimming preserved

| quantity | value |
|---|---|
| OKX page records total | `315900` |
| canonical in-window rows | `315648` |
| out-of-window rows | `252` |
| origin | page 1053, timestamps before `2022-01-01` |

Fixed-size OKX pages legitimately straddle the **lower** window boundary,
so those rows are trimmed and counted. A new fail-closed structural guard
raises `PROTECTED_YEAR_ROW_IN_RETAINED_SOURCE` if any retained source row
is at or after `2025-01-01`. That is structural protection, not outcome
inspection.

## Unchanged

F-01's repaired bar-end mapping, `D_E`, the 8640 reference window,
MAD × 1.4826, `ABS_DISLOCATION_Z`, `BTC_RET_24H`/`BTC_SIDE`/
`ABS_BTC_RET_24H`, RV-288, entry/outcome, train 2022, holdouts 2023/2024,
train-only standardization (`ddof=0`), the OLS design, 14-day MBB, 5000
replicates, seed `2026092106`, the six gates, 2% materiality, the
classification rules, and 2025/2026 protection. F-04 remains
`HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE`.

## Live state

No live ARM, reservation, claim, or RESULT exists. Canonical execution
refuses with `MARKET_06_NO_TRACKED_CLAIM`.

`REAL_DATA_PARSED_FOR_SCIENCE = false`, `REAL_OUTCOMES_COMPUTED = false`,
`SCIENTIFIC_OUTCOMES_INSPECTED = false`, 2025/2026 unopened.

Next unit: `MARKET_06_FINAL_LIFECYCLE_RED_TEAM`.
