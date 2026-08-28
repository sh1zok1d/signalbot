# H03 Post-Freeze Correction + Result Forensic Audit

**Status:** AUDIT ONLY. Not a new H03 run. Not a parameter change. Not R3. Not H04.

| Item | SHA |
|---|---|
| prereg (`H03_PREREG_SHA`) | `e2c370d70ca3dc5952ad9c82808e6b877805f998` |
| post-prereg correctness fix | `4e995440e649b37bdc0a9f0100a3e0b369573f6c` |
| development result | `b30df4ea7810c5eeeacaaa977a93e9e157f9b7b2` |

Required ancestry verified locally (no rewrite):

`e2c370d` → `4e99544` → `b30df4e`

Parents: `4e99544^ == e2c370d`, `b30df4e^ == 4e99544`.

2025 inspected: **NO**
2026 inspected: **NO**
real H03 rerun: **NO**
`--stage dev-run` invoked in this audit: **NO**

Provisional development verdict under audit: `H03_REJECTED_SPECIFIC_CLAIM`.

This audit does not try to save or kill H03. It checks correctness of the post-prereg fix, pre-crash exposure, matched-random residual TVD, and persisted-result consistency.

---

## 1. Exact `4e99544` diff classification

`git diff e2c370d70ca3dc5952ad9c82808e6b877805f998 4e995440e649b37bdc0a9f0100a3e0b369573f6c`

Two files, 19 insertions, 3 deletions. No preregistration, no seeds, no W/q/H, no refractory, no MPIE, no control definitions, no runner CLI.

### `scripts/research/h03_extreme_impulse_lib.py` — `build_matched_random_pool` only

Pre-fix (e2c370d):

```python
excluded = np.zeros(len(all_grid_idx), dtype=bool)
excluded[raw_extreme_idx] = True
return all_grid_idx[~excluded]
```

Post-fix (4e99544):

```python
excluded = np.isin(all_grid_idx, raw_extreme_idx)
return all_grid_idx[~excluded]
```

Plus a docstring stating that `all_grid_idx` and `raw_extreme_idx` are values in the same index space (panel positions) and that fancy-indexing into `len(all_grid_idx)` is only valid on a `0..n-1` grid.

### `tests/research/test_h03_extreme_impulse.py` — `test_16` extension only

Added a synthetic case with non-contiguous high panel ids `{100, 250, 172400, 172517, 200000}` excluding `{172517, 100}`. No production-parameter test.

### Call-site contract (unchanged at both SHAs)

`evaluate_cell` already did (e2c370d and 4e99544):

```python
elig = eligible_index(...)                         # panel ids
raw_extreme_in_elig = np.flatnonzero(raw_mask & elig_set)  # panel ids
pool_idx = build_matched_random_pool(elig, raw_extreme_in_elig)
```

Preregistered matched-random semantics (H03 prereg §12), unchanged:

- exclude raw qualifying extreme timestamps for the same W×q (before refractory);
- sampling without replacement;
- month composition preserved;
- UP/DOWN composition preserved;
- no surrounding-regime exclusion.

On a `0..n-1` grid the two bodies return identical arrays (confirmed synthetically). On the real eligible-development subset, the pre-fix body is not a different research rule — it is an illegal fancy-index and raises `IndexError` before any cell is returned.

**Classification: `SEMANTICS_PRESERVING_CORRECTNESS_FIX`**

Not `RESEARCH_SEMANTICS_CHANGED`.

---

## 2. Pre-crash exposure

Runner `main(--stage dev-run)` order:

1. print identity JSON (`stage`, `snapshot_id`, `dataset_id`);
2. `load_development_1m` (2020–2024 1m only);
3. `aggregate_1m_to_15m`;
4. `build_panel` (features + candidate-independent ACF diagnostic, in memory);
5. `evaluate_h03` → first cell `W=15, q=0.90, H=15` → `evaluate_cell`;
6. only after `evaluate_h03` returns: write `artifacts/h03/H03_DEV_RESULTS.json` / `.md` and print `H03_DEV_COMPLETE`.

Inside `evaluate_cell`, crash site is **before** `matched_random_bundle`, **before** `negative_control_bundle`, **before** the `return` dict:

1. raw mask / refractory / eligible index / `outcome_bundle` for candidates (in memory);
2. moderate-band `outcome_bundle` (in memory);
3. `build_matched_random_pool(elig, raw_extreme_in_elig)` → **IndexError**.

Nothing after step 1 of `main` is printed. No result files are written until step 6. The failed invocation left no `H03_DEV_COMPLETE` artifact. Files now under `artifacts/h03/` belong to the later successful run at `4e99544`, not to the crash.

Terminal evidence from the crash (no market table): `IndexError: index 172517 is out of bounds for axis 0 with size 172400`. Those two integers are an illegal fancy-index (panel id vs `len(elig)`), not `CONT_RET_H`.

| Question | Answer |
|---|---|
| candidate event counts visible before crash | **NO** (computed in memory for cell 1 only; never printed or written) |
| primary CONT_RET outcomes visible | **NO** |
| matched-random effect visible | **NO** (crash is at pool construction) |
| structural-control effect visible | **NO** (in memory for cell 1; never returned) |
| negative-control effect visible | **NO** |
| year/side outcome tables visible | **NO** |

Was ANY information available that could reasonably have motivated the specific indexing correction or changed a research parameter?

**NO.** The traceback plus reading `evaluate_cell` / `build_matched_random_pool` is sufficient to see that panel ids were used as positions into `elig`. No cell mean, MPIE, year table, or sign was observable.

`4e99544` was a response to a **deterministic implementation exception**, not to an observed market result.

---

## 3. Regression test for the original index-space bug

Synthetic-only test added: `test_16c_original_fancy_index_crash_and_membership_semantics`.

It reconstructs the pre-fix fancy-index body, asserts `IndexError` on panel ids such as `172517` into a length-5 `elig`, and asserts the current `np.isin` body:

- excludes exactly the intended raw extreme panel ids;
- does not treat those ids as positions inside `elig`;
- does not exclude unrelated eligible timestamps;
- agrees with the pre-fix body on a `0..n-1` grid.

**Result: current implementation PASSES.** No production code change in this audit.

---

## 4. TVD forensic audit

Frozen formula in `total_variation_distance`:

`TVD = 0.5 * sum_i |p_i - q_i|` over the union of keys, with `p_i = count_a[i] / n_a` and `q_i = count_b[i] / n_b` (`n=0` protected by `or 1`).

That formula is correct. Synthetic checks: identical → 0; disjoint → 1; small perturbation in (0,1); same proportions different N → 0; missing category via union → correct.

### Why reported DOW TVD ≈ 0.83 and DOM TVD ≈ 0.97

`matched_random_bundle` (unchanged from e2c370d through b30df4e):

```python
last_dow_dist = categorical_counts([utc_dow_key(int(x)) for x in picked])
last_dom_dist = categorical_counts([utc_dom_key(int(x)) for x in picked])
real_dow = categorical_counts(list(cand["dow"]))
real_dom = categorical_counts(list(cand["dom"]))
```

`picked` is an array of **panel indices**. `utc_dow_key` / `utc_dom_key` interpret their argument as **epoch milliseconds**.

Typical panel ids (100 … 200000) as milliseconds all fall on **1970-01-01**, UTC Thursday, `weekday()=3`, DOM=`01`. Matched last-replicate DOW/DOM therefore collapse to near point masses `{"3": N}` and `{"01": N}`.

Candidate `cand["dow"]` / `cand["dom"]` were already keyed from real `t_ms` (2020–2024 UTC weekdays / days of month).

Uniform 7-day vs point mass on `"3"`: TVD = 6/7 ≈ **0.857**.  
Uniform 30-day vs point mass on `"01"`: TVD = 29/30 ≈ **0.967**.

Persisted residual TVD ranges: DOW **0.827–0.838**, DOM **0.969–0.973**. That is the key-space bug, not a real calendar imbalance of that size.

Secondary diagnostic limitation (not the magnitude driver): TVD is computed on the **last replicate only**, not aggregated across 100 replicates. With correct timestamp keys that would still be a noisy but small residual, not ~0.85.

Category universe: DOW keys are `"0"`…`"6"` (Monday=0); DOM keys are `"01"`…`"31"`. Union handling in the formula is correct. The matched-side keys are simply the wrong objects.

**TVD implementation (formula): correct. TVD inputs on the matched side: wrong (panel ids as ms).**

---

## 5. Scope: does TVD affect matching or gates?

Call graph (traced, not inferred from names):

- `sample_matched_random_once` uses `pool_by_month`, `need_up`, `need_down` only. No TVD.
- Matched mean / positive-share: `labels * ret[picked]`, then mean of `norm`. No TVD.
- `residual_diagnostic` is written after sampling and is never read back.
- `evaluate_cell` MPIE gates: `mpie_gate(mean_extreme, mean_matched, ±1)` using `matched["mean_norm_cont_ret"]` only.
- Structural gates: `control_gate(mean_extreme, mean_moderate, ±1)`.
- Negative-control gates: `control_gate(mean_extreme, mean_shifted, ±1)`.
- Verdict criteria in the persisted envelope use those gates, year/side tables, q/W/H neighborhoods, concentration. They do not use `dow_tvd` / `dom_tvd`.

Prereg §12: residual TVD is **“Descriptive only; does not create an alternative matched baseline.”**

Matched means in the persisted JSON sit near 0 (about −0.0015 to +0.039) with `P(CONT>0)` ≈ 0.498–0.504 — the behaviour of a functioning random baseline, inconsistent with a truly broken matched sample of TVD 0.97.

**Scope: `DESCRIPTIVE_ONLY`.** Not `AFFECTS_MATCHING`.

---

## 6. Persisted-result consistency

Read only `docs/research/H03_DEV_RESULTS.json` and `docs/research/H03_DEV_SUMMARY.md`. No parquet recomputation.

| Check | JSON | Summary |
|---|---|---|
| 45 primary cells | YES, 45 unique | YES, 45 table rows |
| 3 W × 3 q × 5 H | W={15,30,60}, q={0.90,0.95,0.98}, H={15,30,60,120,240}; none missing/duplicate | same |
| all 45 medians negative | YES (45/45) | YES |
| `P(CONT_RET>0)` range | 0.429–0.481; all < 0.5 | 0.429–0.481 |
| means 14 positive / 31 negative | YES | YES |
| MPIE continuation / exhaustion | 3/45 and 11/45 | YES |
| continuation MPIE cells | (15, 0.98, 15), (15, 0.98, 30), (60, 0.95, 15) | YES |
| structural continuation / exhaustion | 8/45 and 17/45 | YES |
| +6h continuation / exhaustion | 12/45 and 25/45 | YES |
| both sides mean>0 / both<0 / mixed | 6 / 5 / 34 | YES |
| largest-month share | 2.7–3.4% | YES |
| L_dep | 32 days; ACF64=0.192 | YES |
| verdict | `H03_REJECTED_SPECIFIC_CLAIM` | YES |

Wording erratum (does not change cell data or verdict):

- Summary/envelope post-hoc line “DOWN mean_norm more negative than UP in 39/45 cells” conflates **DOWN mean < 0** (true for **39/45**) with **DOWN mean < UP mean** (true for **45/45**; mixed cells are all UP+/DOWN−). Both readings remain asymmetric. Recorded here only.

Matched-random **means and positive-shares** in the JSON are internally consistent with a near-null random baseline. Residual TVD values are internally consistent with the panel-id-as-ms bug, not with those matched means.

**45 cells: YES. Reported gate counts verified: YES.**

---

## 7. Verdict sensitivity — discard TVD entirely

Frozen candidate-for-freeze requirements, evaluated from persisted cell fields **without** `residual_diagnostic`:

| # | Requirement | Without TVD |
|---|---|---|
| 1 | broad MPIE neighborhood | FAIL (3 continuation + 11 exhaustion isolated cells) |
| 2 | structural separation neighborhood | FAIL (8 / 17 of 45; not coherent) |
| 3 | +6h separation neighborhood | FAIL (12 / 25 of 45; not coherent) |
| 4 | q robustness | FAIL (W=60 H=15 q=0.95 continuation MPIE vs q=0.98 exhaustion MPIE) |
| 5 | W robustness | FAIL |
| 6 | adjacent horizons | FAIL (H sign-flips) |
| 7 | 4/5 years | FAIL |
| 8 | UP/DOWN symmetry | FAIL (34/45 mixed sides) |
| 9 | concentration | PASS (largest month 2.7–3.4%) |
| 10 | primary signed outcome | FAIL (mixed-null; all medians negative; all p>0 < 0.5) |

**WOULD H03 STILL FAIL CANDIDATE-FOR-FREEZE IF TVD WERE REMOVED COMPLETELY? YES.**

This is not permission to remove the diagnostic. It shows a descriptive-input bug cannot have produced the rejection.

---

## 8. Final classification

**B. `H03_RESULT_VALID_WITH_DESCRIPTIVE_ERRATUM`**

- `4e99544` is semantics-preserving implementation correctness.
- The first crash exposed no actionable market outcomes.
- Matched-random **sampling and matched means** remain valid.
- Residual DOW/DOM TVD is a non-gating diagnostic with wrong matched-side keys (panel ids passed to timestamp formatters). Formula is correct. Last-replicate-only is a secondary limitation.
- Persisted 45-cell primary/control/gate surface is internally consistent.
- Rejection does not depend on TVD.

Do not rerun real H03 for this erratum. Do not amend `e2c370d`, `4e99544`, or `b30df4e`.

Erratum text for the record:

> H03 residual TVD (DOW ≈ 0.83, DOM ≈ 0.97) is not a calendar-imbalance measurement. `matched_random_bundle` applied `utc_dow_key` / `utc_dom_key` to panel indices rather than `t_ms[picked]`, collapsing the matched side to 1970-01-01. The diagnostic is descriptive-only and was not used for MPIE, structural, +6h, or the development verdict. Matched-random means/positive-shares are unaffected.

---

## 9. Tests run in this audit

```
python -m pytest -q tests/research/test_h03_extreme_impulse.py
```

`--stage dev-run` was not invoked.

---

## 10. Contamination

2025 inspected: **NO**
2026 inspected: **NO**
real H03 rerun: **NO**
R3: **NOT STARTED**
H04: **NOT STARTED**
