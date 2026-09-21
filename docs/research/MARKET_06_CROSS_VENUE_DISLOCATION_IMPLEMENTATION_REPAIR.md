# MARKET-06 — Outcome-Blind Implementation Repair

Status: `IMPLEMENTATION_REPAIRED_OUTCOME_BLIND_NOT_EXECUTED`
Date: 2026-09-21
Red-team verdict repaired: **B. `MARKET_06_IMPLEMENTATION_REPAIR_REQUIRED`**

The frozen preregistration is **unchanged**. No prereg amendment was
authorized, required, or made. Every scientific constant is preserved.

## What was repaired

| ID | Severity | Defect | Status |
|---|---|---|---|
| F-01 | CRITICAL | Feature bar-time semantics / no-lookahead | FIXED |
| F-03 | MEDIUM | Corruption silently downgraded to row ineligibility | FIXED |
| F-05 | CRITICAL | Future ARM lifecycle dead end | FIXED |
| F-06 | HIGH | No canonical reconstruction / global invariants | FIXED |
| F-07 | MEDIUM | Mutable working-tree authority | FIXED |
| F-08 | LOW | Unhardened Git object access | FIXED |
| F-09 | HIGH | Tautological cutoff tests | FIXED |
| F-04 | LOW | Near-singular OLS | `HARDENING_OBSERVATION_ACCEPTED_NO_CHANGE` |

### F-01 — bar-end semantics (the load-bearing scientific repair)

Retained data are keyed by candle **open** timestamp, but every frozen
scientific quantity expressed at a clock boundary `U` refers to the
**close of the bar whose `bar_end_exclusive == U`**. The frozen prereg says
so directly: `perp_leg.available_at = "bar_end_exclusive"` and
`no_lookahead.feature_information = "available_at <= FEATURE_CUTOFF only"`.

The superseded implementation looked features up at the cutoff's own
open_time, selecting the bar `[E, E+5m)` — which only completes at `T` and
erased the entire preregistered 5-minute decision lag.

One helper now owns the mapping, and no call site may re-derive it:

```
bar_open_for_close_at(U) = U - BAR_MS
```

Features and BTC state use the **ENDING_AT** helpers
(`get_perp_bar_ending_at`, `get_spot_close_ending_at`); entry and outcome
use the **OPENING_AT** helpers (`get_perp_bar_opening_at`). Entry/outcome
indexing is deliberately unchanged.

For `T = 2024-06-15T00:05:00Z`, `E = 2024-06-15T00:00:00Z`, the consumed
open-times are now asserted exactly:

| quantity | open_time |
|---|---|
| D_E | `2024-06-14T23:55:00Z` |
| newest reference | `2024-06-14T23:50:00Z` |
| oldest reference | `2024-05-15T23:55:00Z` |
| BTC_RET numerator | `2024-06-14T23:55:00Z` |
| BTC_RET denominator | `2024-06-13T23:55:00Z` |
| RV first close bar | `2024-06-13T23:55:00Z` |
| RV last close bar | `2024-06-14T23:55:00Z` |
| entry | `2024-06-15T00:05:00Z` |
| first outcome | `2024-06-15T00:05:00Z` |
| last outcome | `2024-06-16T00:00:00Z` |

The final RV return now ends at **E**, not at **T**.

### F-03 — integrity is not ineligibility

`Market06RowIneligible` is now a distinct typed condition. Only the
preregistered eligibility rules drop a row: a genuinely absent required
timestamp, `BTC_RET_24H == 0` exactly, `MAD_T <= 0`, and
`RV <= 0`/non-finite. Source corruption — non-positive or malformed OHLC,
bad schema, duplicate source timestamp, invalid OKX `confirm`, corrupt
ZIP, wrong SHA — raises `Market06IncompleteExecution` and aborts canonical
execution. Support can no longer be silently improved by discarding
corrupt observations.

### F-05 — permit architecture replaces the dead end

Previously `execution_authorization_artifact_exists()` was a constant
`False`, `require_execution_authorization()` raised on every path, the
retained bytes were permanently unparseable, and — worst — an ARM's
presence made `assert_no_arm_or_result()` *break* authority verification.
The runner's success path ended in `raise RuntimeError("unreachable")`.

Now a tracked ARM, read from immutable Git objects, is authenticated by a
**generic** verifier and mints an opaque `ExecutionPermit`. The verifier
deliberately hardcodes no future freeze SHA (that commit cannot exist yet);
the ARM names its implementation freeze and the verifier authenticates
whatever it names:

1. read the ARM from an immutable commit (never the working tree);
2. resolve and authenticate the implementation freeze it names;
3. verify that freeze binds the research id, a concrete implementation
   commit/tree, an exact module SHA-256 inventory, this live prereg freeze,
   and this dataset/snapshot/durable root;
4. verify the module bytes **executing now** are exactly those bytes;
5. verify the ARM descends from that implementation freeze;
6. verify no scientific module drifted between freeze and ARM;
7. verify one-shot and exact run-identity binding.

`authorize=True`, `force=True`, environment variables, CLI flags, and
caller-supplied hashes/paths/snapshots cannot mint a permit. The permit
itself cannot be forged: construction without the module-private token
raises.

### F-06 — real global reconstruction

`market_06_canonical_reconstruction` consumes only Git-retained bytes and
enforces exact inventory (36 Binance objects, 1053 OKX pages), per-object
SHA-256 and byte length, **global cross-object timestamp uniqueness**,
5m alignment, exact first/last timestamp, exact count `315648`, no missing
timestamps, and Binance/OKX timestamp-set equality. A cross-object
duplicate fails even when the duplicated values are identical. Nothing is
interpolated, forward-filled, or de-duplicated. Out-of-window rows on
fixed-size OKX pages are trimmed at the boundary and counted, never
silently merged.

### F-09 — adversarial temporal tests

The superseded suite stored a bar at key `e_ms` and asserted a lookup of
that same key, canonizing the bug. Every fixture now represents
`open_time`, `bar_end`, `FEATURE_CUTOFF` and `T` separately, asserts exact
open-times, and includes a **malicious** extreme-priced bar at
`[E, E+5m)` that must not move `D_E`, `ABS_DISLOCATION_Z`, `BTC_RET_24H`,
`BTC_SIDE`, `ABS_BTC_RET_24H`, or `RV_BTC_24H`.

### F-04 — deliberately not changed

No condition-number cutoff, ridge, `pinv`, `lstsq`, or regularization was
introduced, because no such guard was preregistered. The solver remains
`numpy.linalg.solve(X'X, X'y)`; exactly-singular and non-finite
coefficients remain `MARKET_06_INCOMPLETE_EXECUTION`. A test now enforces
that no conditioning threshold creeps in.

## One-shot lifecycle (infrastructure only — nothing armed)

Schemas and verifiers exist for ARM, EXECUTION RESERVATION, and RESULT.
**None of those live artifacts were created.** A future reservation binds
the ARM authority, run identity, implementation freeze, dataset, and result
target paths, with `consumed = false` before evaluation. A canonical
RESULT for a run identity makes any further canonical run refuse. An
atomic `O_CREAT|O_EXCL` local lock guards accidental double invocation on
the same checkout — explicitly **not** a distributed mutex; the
authoritative one-shot guarantees are the tracked reservation and the
tracked RESULT.

## Scientific firewall

`REAL_DATA_PARSED_FOR_SCIENCE = false`, `REAL_DISLOCATION_COMPUTED =
false`, `REAL_ELIGIBLE_ROWS_COMPUTED = false`, `REAL_OUTCOMES_COMPUTED =
false`, `REAL_MODELS_FIT = false`, `REAL_BOOTSTRAP_RUN = false`,
`REAL_GATES_COMPUTED = false`, `SCIENTIFIC_OUTCOMES_INSPECTED = false`,
2025 and 2026 unopened. Only byte hashing and timestamp-only structure
were used.

## History

The old implementation (`81c8e0a`) and its freeze (`b71e69f`) are
preserved as historical evidence. The old freeze artifact is annotated
`is_current_authority: false` and its byte inventory is now verified
against the immutable commit it describes rather than the repaired tree.

Next unit: `MARKET_06_IMPLEMENTATION_REPAIR_RED_TEAM_REVIEW`.
