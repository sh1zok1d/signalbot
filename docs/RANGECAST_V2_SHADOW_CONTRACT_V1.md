# Rangecast V2 paired shadow — interface contract V1

**Status:** `PROPOSED` (2026-10-12) by the forecast-engine track to the journal and monitor track (calibration monitor V2, PR #458). Nothing here is wired; no table, claim class or user text changes on this branch.
**Ownership:**
- **Forecast engine** (this branch) provides numbers and identities: `beta/rangecast_shadow.py`, the frozen artifact, `beta/rangecast_paired.py`.
- **Journal and monitor track** stores them, resolves outcomes, keeps the V1 and V2 books apart and runs the measurement.

## 1. The call

```python
from beta import rangecast_shadow as sh
rec = sh.paired_forecast(
    sh.Snapshot(bars=capture["bars"], price=block["price"], price_ts=<datetime of block["price_ts"]>,
                now=now, calendar=capture["calendar"]),
    v1_model=capture["model"],                       # stats["range_model"], the model V1 claims use
    v2_model=sh.load_frozen_model(),                 # verified artifact; raises ShadowModelError if altered
    v1_ids={"stats_pk": stats["_stats_pk"], "stats_digest": stats["_payload_digest"]})
```

- **Inputs:** the inputs `beta.claims.record_claims` already has in the hourly write window (`capture` from `decision.build_decision`).
- **Timing:** call it once per hour, in the same window and with the same snapshot.
- **Failures:** it never raises. A failure is a status.

## 2. The record

Top level: `schema` (`RANGECAST_SHADOW_RECORD_V1`), `adapter_version`, `status`, `reason`, `now`, `as_of` (= `price_ts` + 1 min, as the V1 claims), `price`, `anchor_close_ms` (close of the last complete 5m bar), `horizons`.

Per horizon (`1h`, `4h`, `24h`): `status`, `reason`, `paired` (both sides `OK`), `pair_key` (sha256 of schema, as-of, anchor, price, horizon), and one record per model:

| Field | V1 | V2 |
|---|---|---|
| `procedure_id` | `TOUCH_CHANCE_PROCEDURE_V1` (= the monitor's V1 id) | `TOUCH_CHANCE_PROCEDURE_RCV2_W_L1` |
| model identity | `model_version`, `stats_pk`, `stats_digest` | `model_version`, `spec_id` `RANGECAST_V2_W_L1`, `spec_digest`, `params_digest`, `artifact_id` `RANGECAST_V2_W_L1_MODEL_V1` |
| `as_of`, `horizon_end` | identical on both sides | identical |
| `state` | `{scale_pct}` | `{scale_pct}` |
| `touch[]` | `source` (`GRID` / `TARGET`), `side`, `distance_pct`, `level`, `subject_key` (`+1:0.25` … as `claims.touch_claims`; targets `T+1:<price>`), `status`, `probability` (6 decimals), `printed` | same keys, same order |
| `neither[]` | `up_pct`, `down_pct`, `level_up`, `level_down`, `subject_key` (`0.5:1.0` …), `status`, `probability`, `p_up`, `p_down`, `printed` | same |

Statuses:

| Status | Meaning |
|---|---|
| `OK` | The number exists. |
| `STALE_DATA` | No price, a price older than 10 minutes, or a last 5m bar older than 10 minutes (the decision block's rule). |
| `INSUFFICIENT_HISTORY` | Less than 30 days of bars. |
| `INCOMPLETE_WINDOW` | The live data-quality gate failed: the 1h and 4h windows must be complete, and 24h / 7d / 30d need 99 / 98 / 95 % of their bars. |
| `EVENT_ZONE` | A CPI / FOMC release r with r − H ≤ now < r + 60 min (`decision.event_zones`). |
| `NO_MODEL` | The model was not supplied. |
| `MODEL_INVALID` | The V2 artifact or its spec digest is wrong. |
| `NOT_COMPUTABLE` | Any other failure, or one side unavailable (the pair is then unpaired). |
| `INVALID_TARGET` | Per target: not a number, not positive, or outside 0.05–30 % (`/check`'s range). |

## 3. Proposed journal mapping (the journal track decides)

1. **Write only V2 as new classes, never shown:** `L3_DISTANCE_TOUCH_{1H,4H,24H}_RCV2` and `L3_NEITHER_{1H,4H,24H}_RCV2` (`rangecast_shadow.SHADOW_CLASSES`).
   - **In `claims.CLASSES`:** each class takes its V1 class's level, templates and rule.
   - **Subject fields:** the V1 claim's fields (`side`, `level`, `distance_pct`, `horizon`, `price`, `scale_pct` / `level_up`, `level_down`, `up_pct`, `down_pct`).
   - **Evaluation rules:** unchanged, `TOUCH_V1` / `NEITHER_V1`. The outcome of a V2 row is then the outcome of the V1 claim with the same subject by construction.
   - **Unique key** `(claim_class, subject_key, issue_slot)`: it does not collide with V1.
2. **The V2 row carries the pair.**
   - `numbers` = `{probability: p_v2, p_v1: <the adapter's V1 value>, printed, pair_key, params_digest}`.
   - The V1 production claim stays as it is.
   - A V1 value that differs from the V1 production claim of the same subject by more than 5·10⁻⁵ (4-decimal rounding) is a parity fault.
3. **Identities in the row.**
   - `rule_version` = `RANGECAST_V2_W_L1+<params_digest[:16]>+RANGECAST_SHADOW_ADAPTER_V1` (`rangecast_shadow.shadow_rule_version`).
   - `stats_digest` = `params_digest`, which becomes the monitor's `snapshot_id`.
   - `stats_pk` = NULL.
4. **No row when a horizon's status is not `OK`.** The status counts per hour go into one health component (proposed `rangecast_shadow`), so pairing completeness can be measured.
5. **Monitor mapping.**
   - `calibration_monitor.observation_from_journal_row` today maps every `L3_*_TOUCH_*` and `L3_NEITHER_*` row to `TOUCH_CHANCE_PROCEDURE_V1`, and its class pattern does not match the `_RCV2` suffix. V2 rows are therefore ignored until the mapping is added, and never pooled with V1 (checked against PR #458 at `1c82e638`).
   - The addition: `_RCV2` classes map to `TOUCH_CHANCE_PROCEDURE_RCV2_W_L1`, with the same families, horizons and rules. The six V2 books are then separate from the six V1 books.
6. **The hourly groups.** `claims.HOURLY_GROUPS["touch"]` takes every class that starts with `L3_`. The `_RCV2` classes must be left out of it and form their own group, proposed `rangecast_shadow`.
   - Otherwise a V2 row already written for the hour makes `record_claims` skip that hour's V1 claims.
   - The V2 rows can go in the same transaction as the V1 rows or after them, never instead of them.
7. **No table change.** `beta_claims` already accepts these rows (test):
   - `claim_class` matches `^L[123]_[A-Z0-9_]+$` and starts with `L3`;
   - `stats_digest` = `params_digest` is 64 hex characters, and `stats_pk` may be NULL;
   - the unique key does not collide with V1;
   - `claims.evaluate` dispatches on the evaluation rule id, so `TOUCH_V1` and `NEITHER_V1` resolve the V2 rows with no change.
8. **Export.** Add `numbers.p_v1`, `numbers.pair_key` and `subject.distance_pct` to the JSONL whitelist, so `beta.rangecast_paired` can read the export directly. Prices stay excluded.

## 4. Version rules

- **Spec:** a change of any procedure constant changes `spec_digest`. The old artifact is then refused (`load_frozen_model`), and the change is a new procedure id and a new registered shadow.
- **Artifact:** the shadow uses one artifact from start to finish. A refit is a new `artifact_id` and `params_digest` and a new procedure id suffix. It is never folded into the running books.
- **V1:** the nightly refit keeps `TOUCH_CHANCE_PROCEDURE_V1`, which is the monitor's existing rule for snapshots.

## 5. Checked on this branch

- **V1 values:** the adapter's V1 values equal `claims.touch_claims` for the distance grid and «ни один» up to the journal's 4-decimal rounding (`tests/beta/test_rangecast_shadow.py`).
- **V2 values:** they equal the research path at every 5-minute offset (tests). On the 2024 fold the live slice equals the vectorized path within 4.6·10⁻¹⁴ (`RANGECAST_V2_SHADOW_PARITY.json`).
- **Event zones:** the adapter's event-zone horizons equal `decision.event_zones` (test).
- **Storage:** the proposed rows fit the `beta_claims` checks, and the V2 classes resolve with the V1 classes' rules (test).
- **Monitor V2:** this branch merged with PR #458 at `1c82e638` has one index-line conflict, and the monitor, export, claims and shadow tests pass together (107 passed; the skips need PostgreSQL).
- **No coupling:** no schema change; the monitor's module imports no rangecast code; no product module imports the adapter (test).

## 6. Needed from the journal track before the shadow starts

1. The writer, behind a setting `rangecast_shadow.enabled`, default off. It writes the `_RCV2` rows from `paired_forecast` in the hourly window.
2. The six classes in `claims.CLASSES` and their own hourly group, outside `touch` (§3.1, §3.6).
3. The monitor mapping of §3.5.
4. The export fields of §3.8.
5. A builder from the export to `beta.rangecast_paired` rows: `pair_key`, `horizon`, `family`, `subject_key`, `source`, `as_of`, `p_v1`, `p_v2`, `outcome`, `status`, `coverage`, `distance_pct`.
6. The owner's go to deploy and switch the setting on. The plan's clock starts at the first complete ISO week after that.
