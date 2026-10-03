# PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0 — E1 holdout overlap erratum

**Status:** `APPEND_ONLY_GOVERNANCE_ERRATUM / EXECUTION_BLOCKED (BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP)`
**Recorded:** 2026-10-03
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
- **E1-RUN-001 is untouched by this erratum and by the pilot.**
  - Its frozen one-shot evaluator has not run.
  - Its records are unchanged.
  - It stays protected and unopened.
- **The overlap invalidates execution on that segment.** No pilot bucket inside the protected interval may be evaluated, and no input read from it may be used.
- **The frozen pilot cannot be executed as frozen.** Its data gate requires exactly 12434 buckets and the P4 counts of 25 DOWN and 19 UP triggered episodes, all of them over the full grid. A grid without the protected segment cannot meet that gate. Under the protocol's own rule ("a changed design is a new pilot identity"), any execution that excludes the segment is therefore a new pilot.

## 3. Conditions for any future execution

1. **New explicit permit.** Execution needs a new, explicit permit recorded after this erratum. Without one, the pilot stays `BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP`.
2. **Earliest eligible grid timestamp: `2026-08-25T17:20:00Z`.** This is the first frozen-grid-compatible timestamp strictly after the protected interval: the 5-minute bucket `[17:20, 17:25)` lies wholly after the half-open interval.
3. **Input-footprint condition.** A permit must also require that no input of an evaluated bucket lies inside the protected interval. Under the frozen design those inputs are:
   - **30-day percentile ranks.** The record shows percentile history from 2026-07-17T19:30Z and first maturity at 2026-08-16T19:30Z.
   - **Persistence.** The predecessor bucket of a two-bucket streak.
   - **Pre-anchor covariates.** Lookback up to 4 hours.
   - **Matched controls.** They are drawn from eligible buckets at or before the anchor.

   Taken together, a decision bucket is input-clean only from **`2026-09-24T17:20:00Z`**, the interval end plus 30 days, with controls limited to that range as well. This is an observation about the frozen design for the future permit to apply; it does not change the design.
4. **E1 stays protected.** E1-RUN-001 remains protected in every case. Nothing here authorizes reading its holdout.

## 4. Related exposure found while recording this erratum (flagged, not adjudicated)

The owner-run P4 descriptive follow-up (`docs/audit/live_archive_price_oi_p4_followup_v0/P4_FINAL_REPORT.md`, `as_of` 2026-09-29T15:03Z) used the same 12434 authorized buckets. It reported 1h/4h realized ranges after triggered PRICE_OI_CONTRACTION states, so live-archive market rows inside the protected calendar span were read by that audit.

This erratum does not decide whether that affects E1-RUN-001:
- E1's own flags concern its frozen evaluator and are unchanged.
- P4 ran no E1 detector or evaluator.

The question is recorded for the owner. The atlas records the P4 read as exposure of the live-archive surfaces for the PRICE_OI row.

## 5. Atlas

The unit `PRICE-OI-PILOT-V0` has state `BLOCKED_GOVERNANCE`, blocker `HOLDOUT_OVERLAP`, reservation `E1_RUN_001_FINAL_HOLDOUT`. It stays there until a future execution permit exists.

```
PRICE_OI_PILOT_V0_EXECUTED = NO
E1_RUN_001_TOUCHED = NO
PREREGISTRATION_EDITED = NO
FUTURE_EXECUTION = NEW_EXPLICIT_PERMIT_REQUIRED (new pilot identity under the protocol's own rule)
EARLIEST_ELIGIBLE_GRID_TIMESTAMP = 2026-08-25T17:20:00Z
INPUT_CLEAN_DECISION_BUCKET_FROM = 2026-09-24T17:20:00Z (frozen 30-day percentile lookback)
```
