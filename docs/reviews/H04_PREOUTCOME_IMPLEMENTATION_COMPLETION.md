# H04 Pre-Outcome Dependence-Sensitivity Implementation Completion

**Status:** IMPLEMENTATION COMPLETION ONLY. Not a market-outcome
computation. Not a prereg change. Not R3. Not H05.
**H04_PREREG_SHA (unchanged, not superseded):**
`c629cac4c6ed1a0d129b812ef022d98a0dba4c1b`
**Historical superseded V1:** `314292ed9824e824522274d1b64874bf91d71b23`
**Real H04 market outcomes computed before this completion:** **NONE.**

This is not a correction to the hypothesis, the preregistration, or any
frozen parameter. `H04_PREREG_SHA` is not amended and is not superseded —
the preregistration's semantics were already correct; only an
implementation-completeness gap is closed here.

## 1. Exact missing implementation capability

`docs/research/H04_TREND_PULLBACK_PREREG.md` §17 already froze, before any
H04 outcome:

> Primary: UTC-week block bootstrap ... If a candidate-for-freeze reading
> is plausible: fixed 1w/2w/4w block sensitivity ... all reported. Not
> selectable.

The implementation at `H04_PREREG_SHA` only provided `week_block_bootstrap`
— a single-UTC-week block bootstrap. There was no implemented 2-week or
4-week block-sensitivity construction. This is a straightforward
implementation-completeness gap: the prereg's own required capability was
not yet built, discovered by re-reading the prereg against the code before
any real data was touched.

## 2. The prereg already required 1w/2w/4w sensitivity

No new design choice was introduced by closing this gap. The block sizes
(1, 2, 4 weeks), the metric they apply to
(`NORM_TREND_CONT_RET_H` mean and continuation-positive share), the seed
(`20260903`), and the replicate count (2000) were all already frozen in
the preregistration before this task. This task only makes the already-
required capability actually computable and exposed in per-cell output.

## 3. Exact block construction

For a given cell's candidate population, `week_keys` are the UTC-week keys
(`YYYY-Www`) of each eligible candidate row. Blocks for a fixed block size
`k` weeks are formed by:

1. taking the sorted (chronological) list of distinct UTC weeks present in
   the candidate sample;
2. partitioning that list into consecutive, non-overlapping groups of `k`
   weeks each, starting from the earliest week present (`_block_groups_for_size`);
3. a group's "rows" are the union of every candidate row whose week key
   falls in that group — no row is ever split across two blocks, and no
   row is ever double-counted across blocks (each row belongs to exactly
   one group, by construction of a partition).

This grouping is entirely deterministic given the candidate sample's own
week keys; it is never chosen from, or adjusted because of, any outcome
value.

## 4. Terminal partial-block rule

If the number of distinct weeks is not an exact multiple of the block
size, the final group is shorter than `k` weeks. That shorter terminal
group is **retained as one block** (never discarded, never merged into the
previous block, never redistributed). This is the single frozen treatment
chosen now, pre-outcome — no alternative treatment is implemented or
selectable, and none may be introduced after outcomes.
`tests/research/test_h04_trend_pullback_continuation.py::
test_dep_sens_04_terminal_partial_block_retained_not_discarded` and
`test_dep_sens_02_2w_block_grouping_exact` /
`test_dep_sens_03_4w_block_grouping_exact` pin this exactly.

## 5. Deterministic seed derivation

- `block_size_weeks == 1` uses the frozen master seed `20260903` directly
  (`np.random.default_rng(20260903)`). This is required, not merely
  convenient: it makes the new 1-week sensitivity numerically identical,
  replicate for replicate, to the pre-existing `week_block_bootstrap`
  field (both draw block-resample positions via an equivalent
  `integers(0, n, size=n)` call under the same seed and the same
  single-week block construction). Verified by
  `test_dep_sens_07_1w_agrees_with_legacy_week_block_bootstrap`.
- `block_size_weeks in {2, 4}` derives an independent, deterministic child
  stream from the same frozen master seed via
  `np.random.default_rng(np.random.SeedSequence([20260903, block_size_weeks]))`
  — distinct per block size, but never a new free-standing seed and never
  re-rolled.
- This deliberately deviates from the task's own illustrative example of
  wrapping `block_size_weeks == 1` in `SeedSequence([20260903, 1])` too:
  doing so would **not** numerically reproduce the legacy field's already-
  shipped 1-week output (a `SeedSequence`-derived generator does not
  produce the same bitstream as `np.random.default_rng(20260903)` given
  the same integer seed). The task explicitly allows "an equally
  deterministic documented mapping" in place of the literal example; this
  document is that mapping's record. Both schemes are fully deterministic
  and neither is outcome-dependent.

## 6. No real outcomes seen

No `--stage dev-run` invocation has been made against real accepted
parquet at any point for H04. The gap was identified by comparing the
frozen prereg text against the shipped implementation's function surface
(`week_block_bootstrap` existed; no 2w/4w equivalent existed) — a pure
code/spec consistency check. All new tests
(`tests/research/test_h04_trend_pullback_continuation.py`,
`test_dep_sens_*`) use hand-constructed synthetic week-key/outcome arrays
with no relationship to real BTC price history.

## 7. No primary-search expansion

`dependence_sensitivity` (`{"1w": {...}, "2w": {...}, "4w": {...}}`) is
computed unconditionally for every cell, which is explicitly permitted and
preferred by the completion task ("since no real run has occurred yet, it
is acceptable and cleaner to compute all fixed 1w/2w/4w sensitivities for
every cell ... this avoids any post-outcome code path"). These remain
diagnostics / uncertainty-sensitivity outputs:

- they do not create new primary cells;
- the primary search surface remains `3 L × 3 depth-bands × 5 H = 45`
  cells, unchanged;
- they do not create additional hypotheses;
- `test_dep_sens_12_no_candidate_gate_decision_changes_from_sensitivity_existing`
  confirms `mpie_gate` and `structural_gate` are computed exactly as
  before and are unaffected by the mere presence of
  `dependence_sensitivity` in the cell output.

## 8. Unchanged (verified)

`P=60m`; `L={240,480,960}`; `q=0.80`; exclusive depth bands
(`shallow [0.10,0.25)`, `moderate [0.25,0.40)`, `deep [0.40,1.00)`);
`H={15,30,60,120,240}`; 60m refractory; `MPIE=0.10`;
`CONTROL_DELTA_MIN=0.05`; matched-random seed `20260902`; bootstrap master
seed `20260903`; the frozen deterministic stratified structural
standardization; the `+6h` negative control; the two-adjacent-depth-band
rule; the two-adjacent-horizon rule; the 4/5-year rule; UPTREND/DOWNTREND
symmetry; the 45-cell primary search surface. No H01/H02/H03 files
touched. No product/forecasting code touched.

## 9. Validation contamination

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- Real H04 outcomes computed (before or after this completion): **NO**
- R3 started: **NO**
- H05 started: **NO**
