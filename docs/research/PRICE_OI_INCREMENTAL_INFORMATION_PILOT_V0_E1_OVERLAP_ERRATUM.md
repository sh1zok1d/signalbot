# PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0 — E1 holdout overlap erratum

**Status:** `APPEND_ONLY_GOVERNANCE_ERRATUM / EXECUTION_BLOCKED (BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP)`, amended by §6 (owner decision on P4 / E1).
**Recorded:** 2026-10-03; Amendment 1 recorded 2026-10-03.
**Machine-readable twin:** `PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.json`
**Concerns:** `PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0.md` and its twin `price_oi_incremental_information_pilot_v0.json`. Both were frozen on 2026-09-29 and stay byte-for-byte unchanged. This record is appended beside them; it does not edit the preregistration and does not change any constant the runner checks.

## 1. Finding

The frozen rule-evaluation grid starts inside the protected E1-RUN-001 final holdout.

| Item | Value | Source |
|---|---|---|
| Protected E1 interval | `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` | `AGENTS.md`; E1-RUN-001 records in `docs/e1/` |
| Frozen pilot grid | `AUTHORIZED_BUCKETS = 12434` 5-minute buckets, 2026-08-16T19:30Z–2026-09-25T12:40Z and 2026-09-25T13:05Z–2026-09-28T23:55Z | pilot protocol §3 |
| Grid buckets inside the interval | 2566 (2026-08-16T19:30Z through 2026-08-25T17:15Z) | counted from the two rows above |
| Grid buckets after the interval | 9868 | same |

The pilot reads the Signalbot live archive (`source = 'live'`): 5-minute state-tape buckets, 1-minute klines and OI percentiles. Those are the market rows the E1 holdout protects.

## 2. What did and did not happen

- **The runner was never executed.** The pilot protocol records "not run"; nothing in the repository or in this change runs it. No pilot outcome exists.
- **The pilot did not read E1-RUN-001; P4 did (§6).**
  - The pilot never ran, so it read nothing.
  - E1's frozen one-shot evaluator has not run, its sealed artifacts were not opened, and its records are unchanged.
  - Its protected outcome surface was opened by the owner-run P4 follow-up. The owner has ruled that the holdout is no longer pristine (§6).
- **The overlap invalidates execution on that segment.** No pilot bucket inside the protected interval may be evaluated, and no input read from it may be used.
- **The frozen pilot cannot be executed as frozen.** Its data gate requires exactly 12434 buckets and the P4 counts of 25 DOWN and 19 UP triggered episodes, all of them over the full grid. A grid without the protected segment cannot meet that gate. Under the protocol's own rule ("a changed design is a new pilot identity"), any execution that excludes the segment is therefore a new pilot.

## 3. Conditions for any future execution

1. **New explicit permit.** Execution needs a new, explicit permit recorded after this erratum. Without one, the pilot stays `BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP`.
2. **Earliest eligible grid timestamp: `2026-08-25T17:20:00Z`.** This is the first frozen-grid-compatible timestamp strictly after the protected interval: the 5-minute bucket `[17:20, 17:25)` lies wholly after the half-open interval.
   **Superseded by §6.** This boundary only considered the E1 interval, not P4's exposure.
3. **Input-footprint condition.** **Superseded by §6.** A permit must also require that no input of an evaluated bucket lies inside the protected interval. Under the frozen design those inputs are:
   - **30-day percentile ranks.** The record shows percentile history from 2026-07-17T19:30Z and first maturity at 2026-08-16T19:30Z.
   - **Persistence.** The predecessor bucket of a two-bucket streak.
   - **Pre-anchor covariates.** Lookback up to 4 hours.
   - **Matched controls.** They are drawn from eligible buckets at or before the anchor.

   Taken together, a decision bucket is input-clean only from **`2026-09-24T17:20:00Z`**, the interval end plus 30 days, with controls limited to that range as well. This is an observation about the frozen design for the future permit to apply; it does not change the design.
4. **The E1 reservation stands.** Nothing here authorizes reading or using the E1 holdout. Its pristine status is invalidated (§6), but that does not release it.

## 4. Related exposure found while recording this erratum (adjudicated by the owner in §6)

The owner-run P4 descriptive follow-up (`docs/audit/live_archive_price_oi_p4_followup_v0/P4_FINAL_REPORT.md`, `as_of` 2026-09-29T15:03Z) used the same 12434 authorized buckets. It reported 1h/4h realized ranges after triggered PRICE_OI_CONTRACTION states, so live-archive market rows inside the protected calendar span were read by that audit.

As first recorded, this erratum left open whether that affects E1-RUN-001, because E1's own flags concern its frozen evaluator and P4 ran no E1 detector or evaluator. The owner has since decided: §6.

## 5. Atlas

The unit `PRICE-OI-PILOT-V0` has state `BLOCKED_GOVERNANCE`, blocker `HOLDOUT_OVERLAP`, reservation `E1_RUN_001_FINAL_HOLDOUT`. It stays there until a future execution permit exists.

```
PRICE_OI_PILOT_V0_EXECUTED = NO
E1_EVALUATOR_TOUCHED = NO
E1_SEALED_ARTIFACTS_OPENED = NO
E1_OUTCOME_SURFACE_OPENED_BY_P4 = YES
E1_PRISTINE_HOLDOUT_STATUS = INVALIDATED_FOR_P4_OVERLAP
PREREGISTRATION_EDITED = NO
FUTURE_EXECUTION = NEW_EXPLICIT_PERMIT_REQUIRED (new pilot identity under the protocol's own rule)
EARLIEST_ELIGIBLE_GRID_TIMESTAMP = 2026-08-25T17:20:00Z (superseded by §6)
INPUT_CLEAN_DECISION_BUCKET_FROM = 2026-09-24T17:20:00Z (superseded by §6)
```

## 6. Amendment 1 — owner decision on P4 / E1 (2026-10-03)

**Decision.** The owner ruled that P4 contaminated the E1 protected outcome surface for every timestamp it read inside the E1 protected interval. The historical E1 records in `docs/e1/` and the E1 preregistration are not rewritten; this amendment is the record.

```
E1_EVALUATOR_TOUCHED = NO
E1_SEALED_ARTIFACTS_OPENED = NO
E1_OUTCOME_SURFACE_OPENED_BY_P4 = YES
E1_PRISTINE_HOLDOUT_STATUS = INVALIDATED_FOR_P4_OVERLAP
```

### 6.1 P4's read footprint, derived from its records

P4 left no row-level log in the repository. Its manifest records `raw_p4_output_committed = false` and `raw_p4_output_hashes_captured = false`. The footprint is therefore derived from the records P4 does have: its manifest, and the frozen code its manifest names.

| Record | What it fixes |
|---|---|
| `docs/audit/live_archive_price_oi_p4_followup_v0/p4_followup_summary.json` | replay class `CURRENT_RULE_SEMANTIC_RECONSTRUCTION`; `authorized_buckets = 12434`; follow-up `HISTORICAL_FOLLOW_UP_V0` at source `9e1ba036`; `as_of = 2026-09-29T15:03:00Z` |
| `scripts/audit/live_archive_replay_preflight/run_price_oi_semantic_replay.py` and `price_oi_semantic_replay.py` at `364db27` | The owner-executable semantic replay, committed 2026-09-29T08:27Z, before P4's `as_of`. Its `PHASE_A_AUTHORIZED_BUCKETS = 12434` is P4's authorized grid. The later commit `caadf28` added only an in-memory field and did not change the read window. |
| same files, the SQL | `klines_1m` (exchange, ts, open, high, low, close, volume) and `open_interest` (exchange, ts, oi_raw, oi_unit), `symbol = 'BTCUSDT'`, `source = 'live'`, `ts >= 2026-07-17T19:30:00Z AND ts < 2026-09-29T00:00:00Z`. No exclusion inside the window. Every 5-minute bucket from `HISTORY_START = 2026-07-17T19:30Z` is reconstructed as percentile history. The only frozen gap, 2026-09-25T12:45–13:00Z, lies outside the E1 interval. |
| `beta/followup.py` at `9e1ba036` | Outcome horizons 1h and 4h only. Controls and the 30-day tercile look back from the anchor within the replay window, so an outcome window ends at most 4h after an anchor. The last grid bucket (2026-09-28T23:55Z) closes at 2026-09-29T00:00Z, so no follow-up read can end later than 2026-09-29T04:00:00Z. Whether bars in [2026-09-29T00:00Z, 04:00Z) were actually read is not recorded: 3 DOWN and 2 UP events were excluded as outcome-incomplete. |

**P4-exposed timestamps:**

| Scope | Interval | Basis |
|---|---|---|
| Inside the E1 protected interval | **`[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`**, the whole interval | The recorded replay read window strictly contains it, with no excluded timestamp inside. Both ends are the protected interval's own bounds; neither is estimated. |
| Recorded read window, overall | `[2026-07-17T19:30:00Z, 2026-09-29T00:00:00Z)` | replay SQL at `364db27` |
| Maximal follow-up extension | `[2026-09-29T00:00:00Z, 2026-09-29T04:00:00Z)` | an upper bound from the frozen horizons and the last grid bucket; actual reads not recorded, so treated as exposed |
| **Treated as P4-exposed** | **`[2026-07-17T19:30:00Z, 2026-09-29T04:00:00Z)`** | the union of the two rows above |

Tables read: `klines_1m` and `open_interest`, BTCUSDT, live source, every exchange in the archive. Outcomes computed by P4: 1h/4h realized ranges after triggered and ordinary anchors on the 12434-bucket grid.

### 6.2 Rules for any future confirmatory PRICE_OI or related pilot

1. **Exclude every P4-exposed outcome timestamp:** `[2026-07-17T19:30:00Z, 2026-09-29T04:00:00Z)`.
2. **Exclude every anchor whose feature, lookback or control window touches a P4-exposed timestamp.** Under the V0 design's lookbacks, this means anchors only from **`2026-10-29T04:00:00Z`**, with controls and covariates drawn only from that range as well. Those lookbacks are:
   - 30-day percentile ranks;
   - the persistence predecessor bucket;
   - 4h pre-anchor covariates;
   - matched controls at or before the anchor.

   The date is the exposure end plus 30 days, derived from those lookbacks, not chosen. A changed design recomputes it from its own lookbacks.
3. **A new explicit execution permit,** recorded after this amendment.
4. **The old frozen data gate is not reused as if pristine.** The gate (12434 buckets; the P4 counts of 25 DOWN and 19 UP) is defined on the P4-exposed grid. A new pilot needs its own gate on its own eligible range.

§3 items 2 and 3 above are superseded by these rules. The E1 reservation stays `RESERVED`; its pristine status is recorded as `INVALIDATED_FOR_P4_OVERLAP`. Whether E1-RUN-001 is still run or closed is not decided here; that remains under E1's own rules and with the owner.
