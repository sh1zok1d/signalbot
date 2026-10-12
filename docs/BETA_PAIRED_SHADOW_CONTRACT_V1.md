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

`spec_digest` is the sha256 of the identity object, including `procedure_digest`. Amendment 1 (2026-10-12, `docs/RANGECAST_V2_SHADOW_CONTRACT_V2.md`, before any shadow issue) puts `procedure_digest` on both identities: the sha256 of every constant of the procedure beyond its coefficients. The values are pinned in `beta/paired_shadow.py`. The store imports no model code. The forecast binders refuse to issue when the code computes another value.

| Procedure | `procedure_digest` | `spec_digest` |
|---|---|---|
| `RANGECAST_V2` / `W_L1` | `e573ae5d65894bb7b98831014aa3fd3fb3807aa1badaed89eb6b42f5288cb3b6` | `9a6b61d01e0816a59752e0e2d66c7b56f9fc29de76832c87fe1227b52361a20a` |
| `RANGECAST_V1` / `RANGECAST_V1` | `4aef58b31d70164e15486cd71b9468349fc517935deb6262d8035bf2881873f7` | `30b8e81e339b35c40506698e064e12301645fb2822c18bbaa433136c36b28273` |

W_L1's `procedure_digest` is `rangecast_v2.shadow_procedure()`: the math of `spec()`, the nightly fit, and the serving rules. Half-life in the identity is the integer 365. V1's `procedure_digest` is `rangecast_shadow.v1_shadow_procedure()`, read from `beta.rangecast` without changing V1. Coefficients are not in either digest. A nightly refit keeps the same `spec_id` and changes `snapshot_id` only.

The frozen artifact `RANGECAST_V2_W_L1_MODEL_V1` (file sha256 `2c7e3eca0d90f12d11e7a10558ffaed8d719ff63d630f2c7b252fd6030f70533`, params digest `095f409f024c3a968d0ec4dc14ca99a3cea67d27c58c3329c241fce02569e261`) keeps its own math digest `00539f2d2a1660c861d4ee7cbd411a010b2f296f3af3826b8ab527cc98727246`, which is sha256 of `rangecast_v2.spec()`. That digest loads the artifact. It is not `V2_SPEC_DIGEST` and it is not the stream id.

One `spec_id` has one `spec_digest` for every anchor. The first write registers it. A later anchor, including a different hour, is rejected when the digest differs. A change of any constant covered by `procedure_digest` is a new `spec_id`.

The production claim journal has no specification column. Monitor V2 reads those rows as procedure `TOUCH_CHANCE_PROCEDURE_V1` and spec `JOURNAL_UNSPECIFIED`. Shadow rows must not use either of those two ids, or they would fall into the user-facing book.

## What Claude provides

`beta.rangecast_shadow.plan_paired_issues` returns the store rows for one hour. `paired_forecast` returns the same probabilities as a record and stores nothing. `execute_hour` maps that record. Neither path writes `beta_claims`. The stored `spec_digest` must equal the Amendment 1 pin above.

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

`SHADOW_RECORDING_ENABLED` is false. `record_issues`, `record_outcome` and `settle_due` raise unless the caller passes `allow_write=True`. No production hourly job passes that flag. The SQL file is not applied on deploy.

A write through `execute_hour` or `scripts/beta/run_paired_shadow_hour.py --write` records the forecasts and then launches settlement. Settlement is `settle_due`: it selects only anchors whose horizon has elapsed and which have no outcome yet, at most `limit` per batch and at most `settle_batches` batches per run. It does not load the issue journal. An anchor that already has an outcome is skipped, so a restart continues at the next elapsed anchor. One settler runs at a time. Without bar history the launch reports `NO_BARS` and stores nothing. A 24h anchor before its horizon is not selected. Monitor V2 labels that anchor `PENDING`. Pending rows are outside the unfinished fraction, so they do not move the book to `INCOMPLETE_DATA`. `NO_DATA`, a missing outcome after the horizon, and coverage below 0.9 remain unfinished.

Hidden shadow issues are not `beta_claims` rows and have no `beta_claim_displays` link. They are not user text.

## Owner decisions still required

1. Run the read-only production-journal export in `docs/BETA_CALIBRATION_MONITOR_V2.md` and return the JSONL. That scores the journal that already exists. It does not start paired recording.
2. Allow `storage/beta_paired_shadow_schema.sql` on the production database. Until then the apply script exits without connecting usefully: it requires `PAIRED_SHADOW_SCHEMA_APPROVED=1`.
3. Allow `scripts/beta/run_paired_shadow_hour.py --write` by setting `PAIRED_SHADOW_HOUR_APPROVED=1`, and pass `--bars` with the 5m history. Until then `--write` exits 2. The write records the hour and launches `settle_due`. The default limit is 500 anchors per batch and 8 batches per run. A 12-week backlog is drained by repeating that run; each run resumes after the last stored outcome. The nightly W_L1 fit (`fit_nightly_snapshot` and `SnapshotStore`) is a further owner decision and is not started by this writer.
4. Keep user wording, `touch_live_cal`, sticky flags and the sharp-move detector on V1.
