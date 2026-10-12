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

`spec_digest` for W_L1 is `beta.paired_shadow.V2_SPEC_DIGEST`, the sha256 of:

```json
{"half_life_days": 365, "level": "L1", "market": "binance_usdm", "procedure_digest": "e573ae5d65894bb7b98831014aa3fd3fb3807aa1badaed89eb6b42f5288cb3b6", "procedure_id": "RANGECAST_V2", "spec_id": "W_L1", "symbol": "BTCUSDT"}
```

That object hashes to `9a6b61d01e0816a59752e0e2d66c7b56f9fc29de76832c87fe1227b52361a20a`. `shadow_spec_digest()` returns this value. The V1 identity hashes to `30b8e81e339b35c40506698e064e12301645fb2822c18bbaa433136c36b28273`.

**Amendment 1 (2026-10-12, proposed by the forecast track before any shadow issue; owner instruction: the digest covers the procedure, not only its name).** Both identity objects carry `procedure_digest`: the sha256 of every constant of the procedure beyond its coefficients.
- **W_L1:** `rangecast_v2.shadow_procedure()` (the model math of `rangecast_v2.spec()`, the nightly fit, the serving rules).
- **V1:** `rangecast_shadow.v1_shadow_procedure()` (the constants of `beta.rangecast` that move a touch or «ни один» chance).
- The values are pinned in `beta/paired_shadow.py`, so the store imports no model code.
- `shadow_spec_digest()` and `rangecast_shadow.bind_v1` refuse to issue when the code no longer computes the pinned value. The store itself only rejects a digest change on an anchor it already holds.
- The earlier digests `13554464…` (V2) and `76867603…` (V1) were never used for a stored issue.

Canonical JSON is `beta.state_tape.sha256_json` (sorted keys). A change of level, half-life, feature set, symbol or market is a new `spec_id` and a new identity object.

The production claim journal has no specification column. Monitor V2 reads those rows as procedure `TOUCH_CHANCE_PROCEDURE_V1` and spec `JOURNAL_UNSPECIFIED`. Shadow rows must not use either of those two ids, or they would fall into the user-facing book.

## What Claude implements

Add this to `beta/rangecast_v2.py`. It binds an already fitted model at one issue bar. It does not insert claims.

```python
def shadow_spec_digest() -> str:
    """Return beta.paired_shadow.V2_SPEC_DIGEST."""

def shadow_snapshot_id(model) -> str:
    """sha256 of the fitted coefficients. A refit changes the result."""

def bind_shadow_model(model, state_by_horizon, *, snapshot_id: str):
    """Return an object with procedure_id, spec_id, spec_digest, snapshot_id,
    touch_probability(*, horizon, distance_pct, side) -> float, and
    neither_probability(*, horizon, distance_up_pct, distance_down_pct) -> float.

    horizon is '1h', '4h' or '24h'. side is +1 or -1.
    state_by_horizon[horizon] is the state_at dict for that issue bar.
    Use touch_probability_v2 and neither_prob. Do not write the journal.
    """
```

`beta.paired_shadow.plan_issues` is the only caller. It asks every bound model the same distances and the same neither pairs, then stores the returned probabilities. The first stored probability for `(anchor, procedure, spec)` is kept. A rerun does not create a second row and does not replace the probability.

## Anchors and outcomes

- Symbol is BTCUSDT. The first comparison horizon is 4h. `plan_issues` also accepts 1h and 24h.
- Touch distances default to `beta.claims.TOUCH_GRID_PCT`. A caller may pass other positive distances. Both sides are asked.
- Neither pairs default to the product of `NEITHER_GRID_PCT`.
- The barrier is `price * (1 ± distance/100)` with no cent rounding. The user journal rounds the level it prints. The shadow pair uses this unrounded barrier for both models, so the comparison does not depend on that rounding.
- One outcome is computed by `beta.claims.evaluate` (`TOUCH_V1` / `NEITHER_V1`) and stored on the anchor. Revisions are append-only. The latest revision is the one that is scored. A revision after the first needs a correction note. The stored outcome keeps `touched` or `neither`, coverage and status. High, low, close and the first-touch time are not stored.
- Coverage below 0.9 is unfinished for a hit and for a miss, same as Monitor V2. Those anchors are not in the paired log loss.
- Log loss and Brier are means over paired anchors. The reported difference is V2 minus V1 for one specification pair. The default pair is `RANGECAST_V1` against `W_L1`. A second `spec_id` is a separate comparison and is not folded into that pair.
- The SQL store rejects an insert that keeps `(anchor, procedure, spec)` but changes `spec_digest`. The first probability and snapshot stay. A rerun with the same digest does not add a row.

## What stays off

`SHADOW_RECORDING_ENABLED` is false. `record_issues` and `record_outcome` raise unless the caller passes `allow_write=True`. No hourly job passes that flag. The SQL file is not applied on deploy.

Hidden shadow issues are not `beta_claims` rows and have no `beta_claim_displays` link. They are not user text.

## Owner decisions still required

1. Run the read-only production-journal export in `docs/BETA_CALIBRATION_MONITOR_V2.md` and return the JSONL. That scores the journal that already exists. It does not start paired recording.
2. Allow `storage/beta_paired_shadow_schema.sql` on the production database. Until then the apply script exits without connecting usefully: it requires `PAIRED_SHADOW_SCHEMA_APPROVED=1`.
3. Allow an hourly caller to pass `allow_write=True`. That caller is not in this tree.
4. Keep user wording, `touch_live_cal`, sticky flags and the sharp-move detector on V1.
