# Rangecast V2 paired shadow — forecast side of the paired shadow contract (V2)

**Status:** `IMPLEMENTED_NOT_WIRED / RECORDING_OFF` (2026-10-12).

**Owner decision of 2026-10-12.** The paired shadow is stored only in the journal track's store: `beta/paired_shadow.py` and `beta/paired_shadow_pg.py`, tables `beta_shadow_*`, contract `BETA_PAIRED_SHADOW_CONTRACT_V1.md`. There is no second shadow-claims system. The `_RCV2` classes in `beta_claims` that `RANGECAST_V2_SHADOW_CONTRACT_V1.md` proposed are withdrawn.

**Ownership:**
- **Forecast track** (this branch): numbers and identities. Files: `beta/rangecast_v2.py` (the contract functions), `beta/rangecast_shadow.py` (the hourly record, nightly snapshots), `beta/rangecast_paired.py` (the rule).
- **Journal track:** the hour path (`plan_shadow_record`, `execute_hour`, `scripts/beta/run_paired_shadow_hour.py`), storage, outcomes, Monitor V2 and the V1 / V2 books.

Nothing here writes a table, a claim or a user text. V1 and the sharp-move detector are unchanged.

## 1. Contract functions (`beta/rangecast_v2.py`)

| Function | Returns | Refuses |
|---|---|---|
| `shadow_spec_digest()` | `paired_shadow.V2_SPEC_DIGEST`, the digest of `spec()` | raises `SPEC_IDENTITY_MISMATCH` when this code no longer computes it |
| `shadow_snapshot_id(model)` | sha256 of the fitted coefficients (`params_digest`) | — |
| `bind_shadow_model(model, state_by_horizon, *, snapshot_id)` | a `paired_shadow.BoundShadowModel` with procedure `RANGECAST_V2`, spec `W_L1`, the spec digest and the snapshot id; `touch_probability` = `touch_probability_v2`, `neither_probability` = `neither_prob` | a model that is not W_L1 or has another math spec; a snapshot id that is not the model's; a horizon without a finite state (asking for it raises); a side other than ±1 |

`rangecast_shadow.paired_forecast` computes every W_L1 number through `bind_shadow_model`, and every V1 number through `paired_shadow.bind_rangecast_v1`.

## 2. Identity

| Procedure | `spec_digest` in the store | What it covers | Guard on this side |
|---|---|---|---|
| `RANGECAST_V2` / `W_L1` | `00539f2d2a1660c861d4ee7cbd411a010b2f296f3af3826b8ab527cc98727246` | `rangecast_v2.spec()`: version, level, half-life, horizons, floor, quantile grid, ridge, clip quantiles, season minimum, lookback, every feature window, calendar terms, feature list, event kinds, joint levels, anchor stride. It is also the frozen artifact's own spec digest | `shadow_spec_digest()` and `validate_v2_model` refuse when `spec()` changes; the store refuses a record whose W_L1 digest is not the pin |
| `RANGECAST_V1` / `RANGECAST_V1` | `76867603601d82f3dd450097c7a01dc359add1a737ea4aac7cf97f41e2b5e28e`, the store's name-level identity | the procedure name, surface and symbol | `v1_math_spec()` (version, horizons, features, past windows, event kinds, floor, `P_GRID`, joint levels, anchor stride) must hash to the pinned `V1_MATH_DIGEST` = `eff8e649f17ebe2f4d1d92d8c2c065c5b75fca3c5d3cdc341aadac41dec7f58f`; otherwise V1 is `MODEL_INVALID` and nothing is stored |

- **Proposed to the store** (#459): make `eff8e649…` the V1 spec digest. V1 would then be identified by its math exactly as W_L1 is. Until the journal track decides, the guard above protects the comparison.
- **Coefficients** are not identity. A nightly refit changes `snapshot_id` only.
- **Serving rules** decide whether a number is issued, never its value. They are not in the digest and are pinned by tests: the data-quality gate, 10-minute staleness, the event-zone rule, the 72-hour snapshot age and the probability clip. A change of them is registered as a new spec by rule (§5).

## 3. The evaluated procedure: W_L1 refitted nightly

- **Fit.** `rangecast_shadow.fit_nightly_snapshot(grid, calendar=…, built_at=…)` fits W_L1 on the grid the V1 nightly build reads: `history_stats.load_history_grid`, from the first stored bar to the UTC midnight of the build. It returns a JSON snapshot record: schema, procedure, spec, spec digest, snapshot id, build time, data from and through, calendar version and the coefficients.
  - A grid that ends after the build time is refused.
  - On a grid of production length, about 713 000 bars, one fit takes 1.4 s and under 400 MB. The V1 fit takes 2.8 s on the same grid.
- **Snapshots.** `SnapshotStore(directory)` keeps every snapshot as one write-once JSON file, `<built_at>_<snapshot_id>.json`. No table is involved.
  - The first snapshot of a set of coefficients is kept.
  - Every read is verified: schema, identity, coefficients against the id, and data no later than the build.
- **Selection.** `SnapshotStore.select(issue_time)` returns the newest snapshot built at or before the issue.
  - `NO_SNAPSHOT` when none exists.
  - `STALE_SNAPSHOT` when its data end more than 72 hours before the issue.
  - `MODEL_INVALID` when the file fails verification.
- **Frozen artifact.** `RANGECAST_V2_W_L1_MODEL_V1.json` is kept for reproducibility (parity record, golden outputs, audit). The store's contract names it as the first snapshot. Its snapshot id is its parameter digest, `095f409f…`.

## 4. One hourly record (`rangecast_shadow.paired_forecast`)

```python
from beta import rangecast_shadow as sh, paired_shadow as ps
status, why, snap_v2 = store.select(now)                         # SnapshotStore of the nightly fits
record = sh.paired_forecast(
    sh.Snapshot(bars=capture["bars"], price=block["price"], price_ts=<datetime of block["price_ts"]>,
                now=now, calendar=capture["calendar"]),
    v1_model=capture["model"],                                    # stats["range_model"], the model V1 claims use
    v2_model=snap_v2["model"] if status == sh.OK else None,
    v1_ids={"stats_pk": stats["_stats_pk"], "stats_digest": stats["_payload_digest"]})
ps.execute_hour(record, ledger, issue_slot=<hour of now>, allow_write=<owner's go>)   # the store's hour path
```

- **Checks.** A fresh price and 5m bar (10 minutes), 30 days of bars, the live data-quality gate, and CPI / FOMC event zones under the product's rule (`decision.event_zones`).
- **Binding.** V1 and W_L1 are bound on the same 5m bar.
- **Paired only.** A horizon is `OK` only when both models answer it. The store keeps only `OK` horizons and records the status of the others.
- **Record per model and horizon:**

  | Field | Contents |
  |---|---|
  | identity | `procedure_id` (`RANGECAST_V1` / `RANGECAST_V2`), `spec_id`, `spec_digest`, `snapshot_id`, `model_version` |
  | V1 extra | `stats_pk`, `stats_digest` from `v1_ids` |
  | V2 extra | `params_digest`, `artifact_id` |
  | times | `as_of` = `price_ts` + 1 minute, `horizon_end` |
  | `touch[]` | the journal grid on both sides, then any target prices; each entry has `side`, `distance_pct`, cent-rounded `level`, `subject_key`, `status`, `probability` to 6 decimals, `printed` |
  | `neither[]` | the 16 pairs with `p_up` and `p_down` |

  The store builds its own unrounded barrier from `distance_pct`.
- **Never raises.**

| Status | Meaning |
|---|---|
| `OK` | Both models answer the horizon. |
| `STALE_DATA` | No price, or the price or the last 5m bar is older than 10 minutes. |
| `INSUFFICIENT_HISTORY` | Less than 30 days of bars. |
| `INCOMPLETE_WINDOW` | The live data-quality gate failed: the 1h and 4h windows must be complete; 24h, 7d and 30d need 99 %, 98 % and 95 % of their bars. |
| `EVENT_ZONE` | A CPI / FOMC release r with r − H ≤ now < r + 60 min. |
| `NO_MODEL` | A model was not supplied, for example no snapshot in force. |
| `MODEL_INVALID` | Identity drift, a bad snapshot or the wrong model. |
| `NOT_COMPUTABLE` | One side unavailable, a non-finite state or scale, or any other failure. |
| `INVALID_TARGET` | Per target price: not a number, not positive, or outside 0.05–30 %. |

## 5. Version rules

- **W_L1.** A change of any constant in `spec()` makes the binders refuse to issue. Restarting needs a new `spec_id`, its digest pinned in the store, and a new registered rule. The old stream stays.
- **V1.** A change of a constant in `v1_math_spec()` stops V1 shadow issues in the same way.
- **Serving rules.** A change of a serving rule changes no stored number, but it changes which anchors exist. It is registered the same way: a new `spec_id` and a new rule. The pinning test has to change with it.
- **Refits.** A nightly refit changes `snapshot_id` on later issues only. The store keeps the first probability, and the book is not reset.

## 6. Checked on this branch

Against the store as merged from #459 (`5f47ede1`).

`tests/beta/test_rangecast_shadow_contract.py`:
- **Identity.** It equals the store's. A change to the math (ridge, quantile grid, lookback) or to a V1 constant (floor, windows) refuses to issue. The serving rules are pinned.
- **Bound model.** It is the store's class on the research path.
- **One hourly record through `plan_shadow_record` and `execute_hour`.**
  - 168 rows, every anchor carrying both procedures.
  - Numbers equal each model's own path at 6 decimals.
  - Off by default.
  - Stored once, scored once; a rerun keeps the first probability.
  - Twelve separate monitor books, six per model.
  - The store's paired report and `rangecast_paired` agree on every book to 10⁻¹².
  - No barrier in the export.
- **The production statistics row** can name the V1 snapshot.
- **A nightly refit** changes the snapshot, not the digest.
- **Withheld cases.** An event zone, an incomplete window, a missing model, W_L1 math drift, V1 math drift and a forged digest each store a status and no probability.
- **Snapshots.** Kept, deduplicated, selected by build time, refused when stale or tampered.

Also run:
- the store's PostgreSQL dry run of this record (`tests/beta/test_paired_shadow_claude_dry_run.py`), with a local PostgreSQL 16;
- the audit's checks (`tests/beta/test_rangecast_shadow.py`).

## 7. Before the first shadow issue

1. **Journal track.** Answer the V1 digest proposal of §2. W_L1's `00539f2d…` is agreed.
2. **Owner, store items 2 and 3.** Allow `storage/beta_paired_shadow_schema.sql`, and allow `PAIRED_SHADOW_HOUR_APPROVED=1`.
3. **Owner, the nightly W_L1 fit.** One call of `fit_nightly_snapshot` on the grid the nightly build already loads, plus `SnapshotStore.put` into a directory on the host. This is a production change and is not on this branch.
4. **The clock.** It starts at the first complete ISO week after recording is switched on (`RANGECAST_V2_SHADOW_PLAN_V2.md`).
