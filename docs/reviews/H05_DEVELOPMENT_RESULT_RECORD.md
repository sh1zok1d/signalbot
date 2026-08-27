# H05 Development Result Record

**Status:** RECORD of the one authorized real H05 development run. Not a new run. Not a code change. Not a repair.

| Item | Value |
|---|---|
| branch | `research/h05-taker-imbalance-discovery` |
| HEAD at outcome run | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| frozen design | `deaf6503896920685f25a03230174d360a07ab9a` |
| H05_PREREG_SHA | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| H05_RESEARCH_CODE_FREEZE_SHA | `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1` |
| dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| PR | #83 (keep DRAFT / OPEN / UNMERGED) |
| independent pre-outcome re-audit | `A. H05_REPAIR_CANDIDATE_PASSES_PRE_OUTCOME_REAUDIT` |

`deaf650` is an ancestor of `faac097`. Working tree was clean at run time. No H05 source/tests/prereg files were modified before or after the run.

## Frozen code used

- `scripts/research/h05_taker_imbalance.py`
- `scripts/research/h05_taker_imbalance_lib.py`
- `docs/research/H05_TAKER_IMBALANCE_PREREG.md` / `.json`

Runtime pins: numpy 2.1.3, pandas 2.2.3, pyarrow 17.0.0, Python 3.12.3.

## Dataset

Runtime root: `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0`.
Manifest: `reports/snapshot_manifest.json`. Loader mandatory identity check ran (`--stage` identity then `dev-run`). snapshot_id matched `717d37a4…`.

Selected partitions: **60** monthly parquet names `2020-01.parquet` … `2024-12.parquet`. 2025/2026 filenames exist on disk and were skipped by path-level loader rules. Those parquet files were not opened.

`t_max_inclusive` = `2024-12-31T19:45:00Z`. Development window 2020-02-01 → 2025-01-01 exclusive.

## One-run discipline

Exact command, once:

```
PYTHONPATH=/tmp/signalbot python3 scripts/research/h05_taker_imbalance.py \
  --stage dev-run \
  --dataset-root /tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0 \
  --out-dir /tmp/signalbot/artifacts/h05 \
  --prereg-commit-sha faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1
```

Start ≈ `2026-08-27T21:22:22Z`. `generated_at_utc` = `2026-08-27T21:23:46Z`. Exit 0. No rerun. No parameter change. No post-outcome code change.

JSON identity:

- `hypothesis_id` = `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN`
- `snapshot_id` = `717d37a4…`
- `prereg_commit_sha` = `faac097…`
- `research_code_sha` = `faac097…` (exact freeze SHA)
- `search_surface.primary_threshold_cells` = 45
- `search_surface.sign_multiplicity` = continuation, reversal
- `windows.validation_untouched` = true
- `windows.oos_untouched` = true
- `forbidden_windows_inspected` = `{2025: false, 2026: false}`

`docs/research/H05_DEV_RESULTS.json` SHA256 `37794ba525212681d0687cf4d35f9c5bf775ff63171c9efdb1b25a3acd947011` is a byte-for-byte copy of the runner JSON. Numerical values were not edited.

## 45-cell completeness

3 W `{15,30,60}` × 3 q `{0.80,0.90,0.95}` × 5 H `{15,30,60,120,240}` = 45 unique cells, none missing/duplicate.

Every cell includes: primary metrics, N, matched_random (seed 20260904, 100 replicates), structural_control with overlap `structural_delta`, negative_control same-support `shift_delta`, `claim_evaluation` for both signs, year_breakdown 2020–2024, direction_breakdown BUY/SELL, concentration, `week_block_bootstrap`, `dependence_sensitivity` with `1w`/`2w`/`4w`, candidate_clustering.

## Machine promotion

```json
{
  "continuation": {
    "promoted": false,
    "promoted_cells": []
  },
  "reversal": {
    "promoted": false,
    "promoted_cells": []
  },
  "verdict": "H05_REJECTED_SPECIFIC_CLAIM"
}
```

Formal first-run status: **`C. H05_DEVELOPMENT_NOT_PROMOTED`**.

Not `AUDIT_FAILURE_BOTH_SIGNS_PROMOTED`. Not continuation-promoted. Not reversal-promoted.

## Forbidden-window audit (result metadata only)

Walk of result JSON for `2025-` / `2026-` **market month/event keys** in candidate/control populations: **none**.

Hits that are not market outcomes:

- `forbidden_windows_inspected.2025` / `.2026` boolean flags (both false);
- `generated_at_utc` = `2026-08-27T21:23:46Z` (clock stamp);
- window labels such as development_end_exclusive `2025-01-01T00:00:00Z` (exclusive bound, not an inspected month).

Concentration `by_month` keys run `2020-02` … `2024-12` only.

2025 market outcomes inspected: **NO**
2026 market outcomes inspected: **NO**

## Post-outcome code change

**NONE.** After the run, only result-recording documents are added:

- `docs/research/H05_DEV_RESULTS.json`
- `docs/research/H05_DEV_SUMMARY.runner.md`
- `docs/research/H05_DEV_SUMMARY.md`
- `docs/research/H05_RUN_PROVENANCE.json`
- this record
- `docs/RESEARCH_LEDGER.md`

2025 inspected: **NO**
2026 inspected: **NO**
real H05 rerun after the one authorized run: **NO**
H05 research code modified: **NO**
Batch01 synthesis: **NOT STARTED**
H06: **NOT STARTED**
