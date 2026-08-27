# H04 Development Result Audit

**Status:** AUDIT of the one authorized real H04 development run. Not a new run. Not a code change.

| Item | Value |
|---|---|
| branch | `research/h04-trend-pullback-discovery` |
| HEAD at outcome run | `7bfdc44a305035a641c25f9d3ee75c6ef652ece0` |
| H04_PREREG_SHA | `c629cac4c6ed1a0d129b812ef022d98a0dba4c1b` |
| H04_RESEARCH_CODE_FREEZE_SHA | `7bfdc44a305035a641c25f9d3ee75c6ef652ece0` |
| dataset snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| PR | #81 (keep DRAFT / OPEN / UNMERGED) |

`c629cac` is an ancestor of `7bfdc44` (`git merge-base --is-ancestor` exit 0). Working tree was clean. No H04 source/tests/prereg files were modified before or after the run.

## Frozen code used

- `scripts/research/h04_trend_pullback_continuation.py`
- `scripts/research/h04_trend_pullback_continuation_lib.py`
- `docs/research/H04_TREND_PULLBACK_PREREG.md` / `.json`

Pre-data tests: `python -m pytest -q tests/research/test_h04_trend_pullback_continuation.py` → 67 passed. `compileall` and `git diff --check` clean. pyarrow 17.0.0.

## Dataset

Runtime root: `/tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0`. Manifest `docs/manifests/CORE_BTC_BINANCE_V0.yaml`: `CORE_BTC_BINANCE_V0`, snapshot `717d37a4…`, `ACCEPTED_FOR_DISCOVERY`, `research_authorized: true`, `confirmatory_authorized: false`.

2020–2024 canonical 1m monthly parquet SHA vs accepted snapshot evidence: **60/60 exact**. Provenance JSON: **60/60 exact**. 2025/2026 parquet contents were not hashed or opened.

Identity stage confirmed dataset_id and snapshot_id without computing outcomes.

## One-run discipline

Exact command, once:

```
python3 scripts/research/h04_trend_pullback_continuation.py \
  --stage dev-run \
  --dataset-root /tmp/signalbot/artifacts/research_data/CORE_BTC_BINANCE_V0 \
  --out-dir /tmp/signalbot/artifacts/h04 \
  --prereg-commit-sha c629cac4c6ed1a0d129b812ef022d98a0dba4c1b
```

`PYTHONPATH=/tmp/signalbot` only (import path; not a research-code change). Output directory was empty beforehand. Runner printed `H04_DEV_COMPLETE`, 45 cells. No rerun. No parameter change. No post-outcome code change.

JSON identity:

- `hypothesis_id` = `H04_TREND_PULLBACK_CONTINUATION`
- `snapshot_id` = `717d37a4…`
- `prereg_commit_sha` = `c629cac…`
- `research_code_sha` = `7bfdc44…` (exact freeze SHA)
- `search_surface.primary_threshold_cells` = 45
- `windows.validation_untouched` = true
- `windows.oos_untouched` = true
- `forbidden_windows_inspected` = `{2025: false, 2026: false}`

`docs/research/H04_DEV_RESULTS.json` is a byte-for-byte copy of the runner JSON. Numerical values were not edited.

## 45-cell completeness

3 L `{240,480,960}` × 3 bands `{shallow,moderate,deep}` × 5 H `{15,30,60,120,240}` = 45 unique cells, none missing/duplicate.

Every cell includes: primary metrics, raw/post-refractory N, matched_random (seed 20260902, 100 replicates), structural_control with `standardized_delta` and `structural_gate`, negative_control, `mpie_gate`, `structural_gate`, `negative_control_gate`, year_breakdown, direction_breakdown, concentration, `week_block_bootstrap`, `dependence_sensitivity` with `1w`/`2w`/`4w`.

## Structural standardization actually used for the gate

Each cell stores `structural_control.standardized_delta` and `structural_control.structural_gate`. Cell-level `structural_gate` matches that object. The gate is not taken from `full_control_unstandardized_mean`. Unmatched candidate share is 0 except L=960 moderate (2/892).

## Matched random exact frozen seed

`matched_random.seed` = **20260902** on cells. `N_replicates` = 100.

## +6h exact frozen semantics

Per-cell `negative_control` includes N, `mean_norm_trend_cont_ret`, `p_trend_cont_ret_pos`, `collision_fraction`. `negative_control_gate` is the CONTROL_DELTA_MIN=0.05 comparison of true vs shifted.

## 1w/2w/4w outputs present

Every cell has `dependence_sensitivity["1w"|"2w"|"4w"]` with `norm_p025`/`norm_p975` and `week_block_bootstrap`. Seed 20260903, 2000 replicates.

## Forbidden-window audit (result metadata only)

Walk of result JSON for `2025-` / `2026-` **market month/event keys** in candidate/control populations: **none**.

Hits that are not market outcomes:

- `forbidden_windows_inspected.2025` / `.2026` boolean flags (both false);
- `generated_at_utc` = `2026-08-27T12:42:08Z` (clock stamp);
- window labels such as development_end_exclusive `2025-01-01T00:00:00Z` (exclusive bound, not an inspected month).

Concentration `by_month` keys run `2020-02` … `2024-12` only.

2025 market outcomes inspected: **NO**
2026 market outcomes inspected: **NO**

## Verdict follows frozen requirements

Frozen labels only: `H04_CONTINUATION_CANDIDATE_FOR_FREEZE` / `H04_INCONCLUSIVE` / `H04_REJECTED_SPECIFIC_CLAIM`. Continuation only; no exhaustion candidate.

Mandatory conditions 2 (broad MPIE neighborhood), 5 (two adjacent exclusive depth bands), and 12 (primary supports the scoped mechanism) fail. Moderate-band continuation at L=480/960 is real in several cells and is quarantined as `POSTHOC_UNTESTED`. It cannot promote because one isolated exclusive band cannot promote H04.

Not `INCONCLUSIVE`: N in shallow/moderate is large; structural unmatched share ≈ 0; the two-adjacent-band claim is resolvable and fails.

Recorded verdict: **`H04_REJECTED_SPECIFIC_CLAIM`**.

## POSTHOC_UNTESTED remain quarantined

Listed only in the summary/ledger as `POSTHOC_UNTESTED`. No child tests. No sign flip. No H01/H02/H03 post-hoc imported as gates.

## Post-outcome code change

**NONE.** After the run, only `docs/research/H04_DEV_RESULTS.json`, `docs/research/H04_DEV_SUMMARY.md`, this audit, and `docs/RESEARCH_LEDGER.md` are added.

2025 inspected: **NO**
2026 inspected: **NO**
real H04 rerun after the one authorized run: **NO**
H04 research code modified: **NO**
R3: **NOT STARTED**
H05: **NOT STARTED**
