# Rangecast V2 paired shadow — forecast side of the paired shadow contract (V2)

**Status:** `IMPLEMENTED_NOT_WIRED / RECORDING_OFF` (2026-10-12).

**Owner decision of 2026-10-12.** The paired shadow is stored only in the journal track's store: `beta/paired_shadow.py`, tables `beta_shadow_*`, contract `BETA_PAIRED_SHADOW_CONTRACT_V1.md`. There is no second shadow-claims system. The `_RCV2` classes in `beta_claims` that `RANGECAST_V2_SHADOW_CONTRACT_V1.md` proposed are withdrawn.

**Ownership:**
- **Forecast track** (this branch): numbers and identities. Files: `beta/rangecast_v2.py` (the three contract functions), `beta/rangecast_shadow.py` (checks, binding, nightly snapshots), `beta/rangecast_paired.py` (the rule).
- **Journal track:** storage, outcomes, Monitor V2 and the V1 / V2 books.

Nothing here writes a table, a claim or a user text. V1 and the sharp-move detector are unchanged.

## 1. The three contract functions (`beta/rangecast_v2.py`)

| Function | Returns | Refuses |
|---|---|---|
| `shadow_spec_digest()` | `paired_shadow.V2_SPEC_DIGEST` | raises `SPEC_IDENTITY_MISMATCH` when this code no longer computes the pinned identity |
| `shadow_snapshot_id(model)` | sha256 of the fitted coefficients (`params_digest`) | — |
| `bind_shadow_model(model, state_by_horizon, *, snapshot_id)` | a `paired_shadow.BoundShadowModel` with procedure `RANGECAST_V2`, spec `W_L1`, the spec digest and the snapshot id; `touch_probability` = `touch_probability_v2`, `neither_probability` = `neither_prob` | a model that is not W_L1 or has another math spec; a snapshot id that is not the model's; a horizon without a finite state (asking for it raises, so a missing state never becomes a number); a side other than ±1 |

`paired_shadow.plan_issues` is the only caller of a bound model. Nothing in this branch inserts a row.

## 2. One identity for each procedure

Amendment 1 to `BETA_PAIRED_SHADOW_CONTRACT_V1.md`, made before any shadow issue.

- **What changed.** Each identity object gains `procedure_digest`: the sha256 of every constant of the procedure beyond its coefficients.
- **Where it lives.** The value is pinned in `beta/paired_shadow.py`, so the store imports no model code.
- **Fail closed.** The binders refuse to issue when the code computes another value. The store alone would only catch a digest change on an anchor it already holds.

| Procedure | `procedure_digest` covers | Value | `spec_digest` |
|---|---|---|---|
| `RANGECAST_V2` / `W_L1` | `rangecast_v2.shadow_procedure()`: **math** (`spec()`: features and windows, `Q_GRID`, ridge, clip quantiles, season minimum, lookback, joint levels, event kinds, anchor stride, floor); **fit** (nightly, the V1 nightly grid, hourly anchors with closed windows, 90 % feature windows, half-life weights, minimum anchors); **serve** (state on the last complete 5m bar, the live data-quality gate, 10-minute staleness, the event-zone rule, snapshot selection and its 72-hour age limit, probability clip) | `e573ae5d…b3b6` | `9a6b61d0…a20a` |
| `RANGECAST_V1` / `RANGECAST_V1` | `rangecast_shadow.v1_shadow_procedure()`: the constants of `beta.rangecast` that move a touch or «ни один» chance (version, horizons, features, past windows, event kinds, floor, `P_GRID`, joint levels, anchor stride, minimum anchors), the nightly fit, `scale_at`, staleness and the event-zone rule. Read from `beta.rangecast`; V1 is not changed | `4aef58b3…73f7` | `30b8e81e…8273` |

- **Earlier digests.** The earlier `13554464…` (V2) and `76867603…` (V1) were never used for a stored issue.
- **Coefficients.** They are not identity. A refit changes `snapshot_id` only.
- **Unaffected.** The frozen artifact's own `spec_digest` (`00539f2d…`) is the math digest of `spec()`. It is unchanged, so the artifact still loads.

## 3. The evaluated procedure: W_L1 refitted nightly

- **Fit.** `rangecast_shadow.fit_nightly_snapshot(grid, calendar=…, built_at=…)` fits W_L1 on the grid the V1 nightly build reads: `history_stats.load_history_grid`, from the first stored bar to the UTC midnight of the build. It returns a JSON snapshot record: schema, procedure, spec, spec digest, snapshot id, build time, data from and through, calendar version and the coefficients.
  - A grid that ends after the build time is refused.
  - On a grid of production length, about 713 000 bars, one fit takes 1.4 s and under 400 MB. The V1 fit takes 2.8 s on the same grid.
- **Snapshots.** `SnapshotStore(directory)` keeps every snapshot as one write-once JSON file, `<built_at>_<snapshot_id>.json`. No table is involved.
  - The first snapshot of a set of coefficients is kept; an identical later fit adds nothing.
  - Every read is verified: schema, identity, coefficients against the id, and data no later than the build.
- **Selection.** `SnapshotStore.select(issue_time)` returns the newest snapshot built at or before the issue.
  - `NO_SNAPSHOT` when none exists.
  - `STALE_SNAPSHOT` when its data end more than 72 hours before the issue (one missed night is tolerated, two are not).
  - `MODEL_INVALID` when the file fails verification.
- **Frozen artifact.** `RANGECAST_V2_W_L1_MODEL_V1.json` is kept for reproducibility: the parity record, the golden outputs and the audit. It is one possible snapshot (its snapshot id is its parameter digest). It is not the evaluated procedure.

## 4. One hourly issue (`rangecast_shadow.plan_paired_issues`)

```python
from beta import rangecast_shadow as sh, paired_shadow as ps
status, why, snap_v2 = store.select(now)                         # SnapshotStore of the nightly fits
out = sh.plan_paired_issues(
    sh.Snapshot(bars=capture["bars"], price=block["price"], price_ts=<datetime of block["price_ts"]>,
                now=now, calendar=capture["calendar"]),
    v1_model=capture["model"],                                    # stats["range_model"], the model V1 claims use
    v2_model=snap_v2["model"] if status == sh.OK else None)
ledger.record_issues(out["rows"], allow_write=<owner's go>)      # Cursor's store; nothing else is written
```

- **Checks.** A fresh price and 5m bar (10 minutes), 30 days of bars, the live data-quality gate, and CPI / FOMC event zones under the product's rule (`decision.event_zones`).
- **Binding.** V1 is bound through `paired_shadow.bind_rangecast_v1` behind the V1 identity check (`rangecast_shadow.bind_v1`). W_L1 is bound through `bind_shadow_model`. Both use the same 5m bar.
- **Both or neither.** A horizon either model cannot answer is withheld for both, so every stored anchor is paired. The report gives the status per horizon and model, for the completeness count.
- **Times.**
  - `as_of` = `price_ts` + 1 minute, as in the claim journal.
  - `issue_slot` = the hour of `now`.
  - `issued_at` = `now`.
- **Horizons.** 1h, 4h and 24h, each with the journal's distance grid on both sides and its 16 «ни один» pairs. The barrier is unrounded (store contract).
- **Never raises.** A failure leaves `rows` empty and says why.

| Status | Meaning |
|---|---|
| `OK` | Both models answer the horizon. |
| `STALE_DATA` | No price, or the price or the last 5m bar is older than 10 minutes. |
| `INSUFFICIENT_HISTORY` | Less than 30 days of bars. |
| `INCOMPLETE_WINDOW` | The live data-quality gate failed: the 1h and 4h windows must be complete; 24h, 7d and 30d need 99 %, 98 % and 95 % of their bars. |
| `EVENT_ZONE` | A CPI / FOMC release r with r − H ≤ now < r + 60 min. |
| `NO_MODEL` | A model was not supplied, for example no snapshot in force. |
| `MODEL_INVALID` | Identity drift, a bad snapshot or the wrong model. |
| `NOT_COMPUTABLE` | A non-finite state or scale, or any other failure. |

`paired_forecast` asks the same bound models for arbitrary target prices, for diagnostics. It stores nothing; invalid targets get `INVALID_TARGET`.

## 5. Version rules

- **New spec.** A change of any constant in §2 makes the binders refuse to issue. Restarting needs a new `spec_id`, a new identity object pinned in the store, and a new registered rule. The old stream stays.
- **Refit.** A nightly refit changes `snapshot_id` on later issues only. It never rewrites a stored probability: the store keeps the first, and the book is not reset.
- **V1.** The nightly V1 refit is identical in kind, and its `snapshot_id` is the digest of its fitted horizons.

## 6. Checked on this branch

The integration tests in `tests/beta/test_rangecast_shadow_contract.py` run against `beta/paired_shadow.py` as merged from #459.

- **Identity.** It equals the store's. A change to the math (ridge, `Q_GRID`), the fit or the serving rules (the data gate, the snapshot age), or to a V1 constant, refuses to issue.
- **Bound model.** It is the store's class. Its numbers are the research path. A missing state, a wrong snapshot id or a wrong side raises.
- **One issue through the store.**
  - 168 rows, every anchor carrying both procedures.
  - V1 numbers equal `rangecast.touch_probability` on `scale_at`.
  - Recording is refused without `allow_write`.
  - A rerun adds nothing.
  - One outcome per anchor comes from `score_anchor`.
  - The store's `paired_report` and `rangecast_paired` agree on every book to 10⁻¹².
  - `monitor_observations` keeps W_L1 on its own books.
  - The export carries no barrier.
- **Nightly refit.** It changes the snapshot id, not the spec digest; a rerun keeps the first probability.
- **Withheld cases.** An event zone, an incomplete window, a missing model, identity drift and a store failure each store nothing.
- **Snapshots.** Kept, deduplicated, selected by build time, refused when stale or tampered.

Still covered from the audit (`tests/beta/test_rangecast_shadow.py`):
- V1 numbers equal `claims.touch_claims`;
- V2 equals the research path at every 5-minute offset;
- statuses, event zones, tails, «ни один» monotonicity and Fréchet bounds, and the golden outputs.

## 7. Before the first shadow issue

1. **Journal track.** Take Amendment 1, the two `procedure_digest` lines, into #459, or reply with a different identity before anything is recorded.
2. **Owner, store items 2 and 3.** Allow `storage/beta_paired_shadow_schema.sql`, and allow the hourly caller to pass `allow_write=True`.
3. **Owner, the nightly W_L1 fit.** One call of `fit_nightly_snapshot` on the grid the nightly build already loads, plus `SnapshotStore.put` into a directory on the host. This is a production change and is not on this branch.
4. **The clock.** It starts at the first complete ISO week after recording is switched on (`RANGECAST_V2_SHADOW_PLAN_V2.md`).
