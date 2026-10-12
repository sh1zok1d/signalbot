# Paired shadow contract V1

**Status:** `FROZEN_INTERFACE / RECORDING_OFF` (2026-10-12).

This is the interface between Rangecast V2 and the measurement store. Claude implements the V2 side in `beta/rangecast_v2.py`. He does not change `beta_claims`, `beta_claim_outcomes`, user text, `touch_live_cal`, or the sharp-move detector. The store in `beta/paired_shadow.py` does not import V2 coefficients.

Monitor V2 thresholds are unchanged. Each procedure and specification is its own six books (touch and neither, at 1h, 4h and 24h). The 10% confirmation bound stays inside that family of six. It is not recomputed across V1 and V2 together.

## What is identified

| Field | Role | What a change does |
|---|---|---|
| `procedure_id` | `RANGECAST_V1` or `RANGECAST_V2` | A different procedure is a different Monitor V2 book. |
| `spec_id` | `RANGECAST_V1` or `W_L1` | A new specification starts a new stream. The old stream stays. |
| `spec_digest` | sha256 of the identity object below | The digest is fixed for a `spec_id`. A different digest needs a new `spec_id`. |
| `snapshot_id` | digest of the fitted coefficients at issue | A nightly refit changes this on later issues only. It does not rewrite earlier probabilities and does not reset the book. |
| `eval_rule_id` | `TOUCH_V1` or `NEITHER_V1` | The outcome rule. An outcome under another digest is rejected. |
| `anchor_key` | slot, horizon, family, distance, side, rule | Shared by both procedures. The procedure is not part of the key. |

`spec_digest` for W_L1 is `beta.paired_shadow.V2_SPEC_DIGEST` = `00539f2d2a1660c861d4ee7cbd411a010b2f296f3af3826b8ab527cc98727246`.

That is the sha256 of `beta.rangecast_v2.spec()` at commit `16c0916ece165d14a2e0e0d3717fc400ddc2699a`, not a short label. The hashed object is named `RANGECAST_V2_W_L1` and includes the version, level L1, half-life 365.0, horizons, floor, quantile grid, ridge, clip quantiles, season minimum, lookback, range / realized-volatility / activity / move windows, signed inputs (empty at L1), calendar terms, feature list, event kinds, joint levels and anchor stride. Coefficients are not in it. The V1 stream digest is `76867603601d82f3dd450097c7a01dc359add1a737ea4aac7cf97f41e2b5e28e`.

One `spec_id` has one `spec_digest` for every anchor. The first write registers it. A later anchor, including a different hour, is rejected when the digest differs. A change of any constant in `spec()` is a new `spec_id`. A nightly refit keeps `W_L1` and changes `snapshot_id` only. The frozen artifact `RANGECAST_V2_W_L1_MODEL_V1` (file sha256 `2c7e3eca0d90f12d11e7a10558ffaed8d719ff63d630f2c7b252fd6030f70533`, params digest `095f409f024c3a968d0ec4dc14ca99a3cea67d27c58c3329c241fce02569e261`) is the first snapshot.

The production claim journal has no specification column. Monitor V2 reads those rows as procedure `TOUCH_CHANCE_PROCEDURE_V1` and spec `JOURNAL_UNSPECIFIED`. Shadow rows must not use either of those two ids, or they would fall into the user-facing book.

## What Claude provides

`beta.rangecast_shadow.paired_forecast` is the number source. It does not write. This store does not add claim classes and does not insert into `beta_claims`.

His record labels are mapped on the way in:

| Record | Stored |
|---|---|
| procedure `TOUCH_CHANCE_PROCEDURE_V1` | `RANGECAST_V1` / spec `RANGECAST_V1` |
| procedure `TOUCH_CHANCE_PROCEDURE_RCV2_W_L1`, spec `RANGECAST_V2_W_L1` | `RANGECAST_V2` / spec `W_L1` |
| `spec_digest` | must equal the pin above, or the hour is `MODEL_INVALID` and no probability is stored |
| `params_digest` | `snapshot_id` |
| `stats_digest` | V1 `snapshot_id` |

`plan_shadow_record` is the mapping. `execute_hour` stores it. The first probability for `(anchor, procedure, spec)` is kept. A rerun does not create a second row and does not replace the probability. A horizon whose status is not `OK` stores that status and no probability.

## Anchors and outcomes

- Symbol is BTCUSDT. The first comparison horizon is 4h. `plan_issues` also accepts 1h and 24h.
- Touch distances default to `beta.claims.TOUCH_GRID_PCT`. A caller may pass other positive distances. Both sides are asked.
- Neither pairs default to the product of `NEITHER_GRID_PCT`.
- The barrier is `price * (1 ± distance/100)` with no cent rounding. The user journal rounds the level it prints. The shadow pair uses this unrounded barrier for both models, so the comparison does not depend on that rounding.
- One outcome is computed by `beta.claims.evaluate` (`TOUCH_V1` / `NEITHER_V1`) and stored on the anchor. Revisions are append-only. The latest revision is the one that is scored. A revision after the first needs a correction note. The stored outcome keeps `touched` or `neither`, coverage and status. High, low, close and the first-touch time are not stored.
- Coverage below 0.9 is unfinished for a hit and for a miss, same as Monitor V2. Those anchors are not in the paired log loss.
- Log loss and Brier are means over paired anchors. The reported difference is V2 minus V1 for one specification pair. The default pair is `RANGECAST_V1` against `W_L1`. A second `spec_id` is a separate comparison and is not folded into that pair.
- The SQL store rejects a `spec_digest` that differs from the digest already registered for that `(procedure_id, spec_id)`, on this anchor or any other. The first probability and snapshot stay. A rerun with the same digest does not add a row.
- `scripts/beta/run_paired_shadow_hour.py` prints a dry-run. `--write` exits unless `PAIRED_SHADOW_HOUR_APPROVED=1`. That variable is not set.

## What stays off

`SHADOW_RECORDING_ENABLED` is false. `record_issues` and `record_outcome` raise unless the caller passes `allow_write=True`. No hourly job passes that flag. The SQL file is not applied on deploy. `execute_hour` writes an outcome only when `score=True` and the horizon has elapsed; until then a 24h book stays unfinished and Monitor V2 reports `INCOMPLETE_DATA` instead of a calibration verdict.

Hidden shadow issues are not `beta_claims` rows and have no `beta_claim_displays` link. They are not user text.

## Owner decisions still required

1. Run the read-only production-journal export in `docs/BETA_CALIBRATION_MONITOR_V2.md` and return the JSONL. That scores the journal that already exists. It does not start paired recording.
2. Allow `storage/beta_paired_shadow_schema.sql` on the production database. Until then the apply script exits without connecting usefully: it requires `PAIRED_SHADOW_SCHEMA_APPROVED=1`.
3. Allow `scripts/beta/run_paired_shadow_hour.py --write` by setting `PAIRED_SHADOW_HOUR_APPROVED=1`. Until then `--write` exits 2. Scoring still needs `execute_hour(..., score=True)` with the bar history; the script stores the issued probabilities and the hour status only.
4. Keep user wording, `touch_live_cal`, sticky flags and the sharp-move detector on V1.
