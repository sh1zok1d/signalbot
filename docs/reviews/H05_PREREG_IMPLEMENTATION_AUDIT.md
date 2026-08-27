# H05 Preregistration + Implementation Audit

**Status:** PRE-OUTCOME IMPLEMENTATION AUDIT. Not a market-outcome
computation. Not a design change. Not R3. Not H06.
**Design parent:** `docs/research/H05_TAKER_IMBALANCE_DESIGN.md` @
`deaf6503896920685f25a03230174d360a07ab9a` (branch
`research/h05-design-redteam`, PR #82, OPEN/DRAFT/UNMERGED).
**This freeze's branch:** `research/h05-taker-imbalance-discovery`,
created from that exact design HEAD.
**Real H05 outcomes computed:** **NONE.**
**2025 inspected:** **NO.** **2026 inspected:** **NO.**
**Amendment 1:** this audit was updated in place (section 6, 26, 27) to
record one PRE-OUTCOME STRUCTURAL-SUPPORT CORRECTION, which superseded
`H05_PREREG_SHA_V1 = 9502006eb4797a9947c61d8d04acd1345ed41e5e` (preserved,
unamended). No real H05 outcome was inspected to make this correction.
**Amendment 2 (this revision):** a second, independent pre-outcome audit
found B-01 (structural support) `CLOSED` on independent re-verification,
plus five further findings (M-01, M-02, M-03, M-04, M-05) against
`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1` (also preserved, unamended,
now superseded), all repaired in a bounded pre-outcome fix — see section
28. **This HEAD is a REPAIR CANDIDATE only and is not itself
independently audited or outcome-ready.** No real H05 outcome was
inspected to make any of these findings or repairs.

This audit checks that the preregistration
(`docs/research/H05_TAKER_IMBALANCE_PREREG.md` /
`.json`) and the implementation
(`scripts/research/h05_taker_imbalance_lib.py`,
`scripts/research/h05_taker_imbalance.py`,
`tests/research/test_h05_taker_imbalance.py`) encode the authoritative
design without introducing new research discretion. Per the task's
absolute rule, the design at `deaf650` is not redesigned here; any
ambiguity the design left unstated is resolved and documented explicitly
below, not silently chosen.

---

## 1. Exact design parent

Confirmed: `docs/research/H05_TAKER_IMBALANCE_PREREG.json` ->
`design_authority.design_head_sha` = `deaf6503896920685f25a03230174d360a07ab9a`,
matching the task's stated authoritative design HEAD exactly. The design
document and red-team review were read in full before any code was
written; no line of the design was reinterpreted to make implementation
easier.

## 2. No real outcome access

`scripts/research/h05_taker_imbalance_lib.load_development_1m` only reads
columns `open_time_ms, available_at_ms, close, base_volume,
taker_buy_base_volume` and only from paths returned by
`list_development_parquet_paths`, which enumerates the `canonical/1m/
monthly` directory and skips any filename beginning `2025-`/`2026-`
**before** ever calling `pq.read_table` on it — forbidden-window access is
structurally difficult, not merely filtered after a full-directory scan.
`--stage dev-run` was not invoked against real accepted parquet at any
point in this task; `tests/research/test_h05_taker_imbalance.py` uses
only in-memory synthetic fixtures (hand-built 1m/15m frames with
Gaussian-random or hand-picked base/taker-buy volumes and closes,
unrelated to real BTC history). `python -m compileall` and the test suite
were run; `--stage dev-run` was not.

## 3. Feature formula

`compute_taker_imbalance` implements `BUY_W = rolling_sum(taker_buy_base_
volume, w_bars)`, `SELL_W = rolling_sum(base_volume - taker_buy_base_
volume, w_bars)`, `TOTAL_W = BUY_W + SELL_W`, `TAKER_IMBALANCE_W =
(BUY_W-SELL_W)/TOTAL_W`, exactly matching the design's formula
(`docs/research/H05_TAKER_IMBALANCE_PREREG.json` ->
`primary_flow_feature`). `TOTAL_W==0` or non-finite yields `NaN` (never
`0`) and is counted in `ineligible_total_w_n` — verified by
`test_03_zero_total_w_is_explicit_ineligibility_not_zero` and
`test_03b_nonfinite_total_w_is_explicit_ineligibility`. Quote-volume is
never referenced anywhere in the library
(`test_02_base_is_primary_quote_is_not_wired_into_gates`,
`test_57_quote_diagnostic_cannot_alter_verdict` both grep the source for
the string `quote` and assert it is absent) — this is a stronger
guarantee than "diagnostic only, never gates": it cannot even leak into a
report field by accident.

## 4. Time semantics

15-minute UTC grid, `T = bar_end_exclusive`, unchanged from H03/H04's
convention (`aggregate_1m_to_15m`, identical boundary assertions).
`BUY_W(T)`/`SELL_W(T)` are trailing sums over the `w_bars` bars ending at
(and including) the bar whose own `bar_end_exclusive == T` — i.e. exactly
`[T-W, T)` — verified by
`test_05_feature_window_excludes_bar_starting_at_t` (a large volume value
placed one bar past `T` must not appear in `BUY_W(T)`/`TOTAL_W(T)`).

## 5. Complete-path embargo

`compute_horizon_return` is unchanged in structure from H03/H04: a
candidate is only eligible if `T+H` resolves strictly before
`dev_end_ms`; ineligible rows are `NaN`, never truncated —
`test_06_complete_horizon_embargo_excludes_not_truncates`.
`development_t_max_ms` retains the same `DEV_END_MS - MAX_H_MIN*BAR_MS -
HTF_MS` formula.

## 6. Structural control

Fixed ordinary band `[0.60, 0.80)`, decoupled from `q`
(`ordinary_control_mask`, `ORDINARY_BAND = (0.60, 0.80)`) — verified never
to overlap any `q` cell's candidate band for `q` in `{0.80,0.90,0.95}`
(`test_10_candidate_and_control_never_overlap_for_any_q`). Five mandatory
match strata (`calendar_month, D, price_alignment, price_strength_bin,
activity_bin`) implemented in `structural_control_bundle` via 5-tuple
stratum keys (`test_15_16_17_18_structural_strata_and_standardization`).

**PRE-OUTCOME STRUCTURAL-SUPPORT CORRECTION (this revision, BLOCKER
closed — supersedes `H05_PREREG_SHA_V1` =
`9502006eb4797a9947c61d8d04acd1345ed41e5e`):** this section originally
flagged, as a non-blocking implementation clarification, that the gate
compared the FULL (unrestricted) `candidate_mean` against a control mean
standardized only over overlap strata — a literal reading of the design
text, but a comparison of quantities on different support. A second,
independent pre-outcome audit correctly identified this as a genuine
methodological problem, not merely a clarification: if unmatched
candidate strata have systematically different outcomes, they can move
the full candidate mean while having no corresponding structural-control
observation at all, letting a structural gate pass or fail on composition
the control never actually saw. This is closed by making the structural
comparison **like-with-like**: `structural_control_bundle` now computes
both `candidate_overlap_standardized_mean` and
`structural_control_standardized_mean` over exactly the same overlap
strata, with exactly the same candidate-frequency weights `w_s`, and
returns `structural_delta = candidate_overlap_standardized_mean -
structural_control_standardized_mean` as the single quantity every
`ORIENTED_STRUCTURAL_DELTA` gate now consumes directly (via the new
`oriented_from_delta`/`gate_from_delta` helpers, distinct from
`oriented_delta`/`gate_control_delta`, which continue to difference two
independent means for the matched/shift gates). The full,
unrestricted candidate-population mean is retained in the bundle's output
as `full_candidate_mean`, for transparency/contrast only — it is no
longer used anywhere in the structural delta, and continues, unchanged,
to be the estimand for every OTHER gate (primary, matched, shift,
bootstrap, year stability, BUY/SELL symmetry), since matched-random and
`+6h` have their own candidate/reference semantics and are not restricted
by structural-control overlap. `directional_support` (the `W`-robustness
helper) was updated identically, so the `W` neighborhood check's
structural-direction component also reads the corrected `structural_delta`
rather than differencing the full candidate mean against a
partial-support control mean.

Verified by the structural-support-correction regression suite:
`test_regression_01_structural_gate_uses_overlap_mean_not_full_mean` and
`test_regression_02_unmatched_candidate_outcomes_cannot_change_structural_delta`
construct exactly the scenario this correction targets — one overlap
stratum with zero candidate/control difference, plus an unmatched
candidate stratum given huge (`50.0`/`999.0`) positive outcomes — and
confirm the full candidate mean moves materially (`>100` in the second
test) while `candidate_overlap_standardized_mean`/`structural_delta`
remain exactly unchanged (`0.0` delta) and the structural gate stays
`False` for **both** signs.
`test_regression_03_continuation_orientation_exact_s_plus_1` and
`test_regression_04_reversal_orientation_exact_s_minus_1` pin the mirror
-exact `S=+1`/`S=-1` behavior of the corrected `oriented_from_delta`.
`test_regression_05_control_only_strata_receive_zero_weight` and
`test_regression_06_candidate_and_control_use_identical_overlap_weights`
confirm the single shared weight dict (`w_s`) is applied identically to
both sides and that a control-only stratum never enters it.
`test_regression_07_zero_overlap_yields_no_fabricated_structural_effect`
and `test_58_insufficient_structural_support_yields_none_not_fabricated`
confirm zero overlap strata routes to `None`/`INCONCLUSIVE`, never a
fabricated `0.0` or any other numeric effect.
`test_regression_08_five_dimensional_strata_remain_exact` confirms the
five-dimensional strata definition itself is unchanged by this
correction.

Control-only strata receive zero candidate weight by construction (they
never enter `cand_stratum_n`/`weight`); unmatched candidates are counted
and reported, never dropped
(`test_control_only_stratum_receives_zero_weight`). No numeric overlap
threshold is invented: when `total_overlap_cand_n == 0`,
`structural_delta` (and both standardized means) is `None`, which the
design maps to `INCONCLUSIVE`
(`test_58_insufficient_structural_support_yields_none_not_fabricated`).

## 7. Price alignment

`price_alignment_index` implements `ALIGNED` iff `D * PRICE_RET_W > 0`,
else `OPPOSED` (including exact zero) — verified by
`test_11_price_alignment_exact` and
`test_12_zero_signed_price_return_is_opposed`. Kept strictly binary, per
design.

## 8. Activity control

`activity_bin` uses the same causal trailing-30d midrank percentile
machinery as `price_strength_bin`/`abs_imbalance_pctl`, applied to
`TOTAL_W`, split at `0.50` (`bin_index_at_median`,
`test_14_activity_bin_causal_median_split`). It is a mandatory structural
-match dimension, not descriptive-only, per the design's own correction
round.

## 9. Matched random

Match on `calendar_month + D` only (no price/activity matching) —
`matched_random_bundle` groups pools strictly by month, assigns paired
`D` labels. Pool exclusion is membership-based (`np.isin` via
`build_matched_random_pool`), never positional
(`test_19_matched_random_pool_membership_not_positional`). Seed `20260904`
consumed exactly once per cell across all 100 replicates
(`test_20_21_matched_random_deterministic_seed_and_reps`).

## 10. +6h

`shift_plus_6h_same_utc_day` wraps within the same UTC day
(`test_22_23_plus_6h_shift_preserves_d`); each candidate's own `D` is
carried through unchanged in `negative_control_bundle` (the shifted row's
own feature state at the shifted timestamp is irrelevant — only its
return/scale eligibility is checked, matching "do not redetect the
candidate at the shifted timestamp" by construction: the shifted position
is used purely as an outcome-window lookup, never re-evaluated as a
candidate itself). Collision fraction is exact
(`test_24_collision_fraction_exact`). Gate is the exact
`ORIENTED_SHIFT_DELTA >= CONTROL_DELTA_MIN` contrast
(`test_33_oriented_shift_delta_exact`, `test_34_continuation_gates_exact`).

## 11. S symmetry

`claim_evaluation` computes all four oriented quantities and gates from
one shared `sign` parameter; `test_35_reversal_mirrored_gates_exact` and
`test_reversal_impossible_under_positive_only_reading_regression`
specifically pin the addendum-2 BLOCKER this preregistration closes: a
genuine reversal effect (negative `candidate_mean`) passes its own
oriented gates, which the prior bare-positive-inequality wording could
not have supported.

## 12. MPIE estimand

`gate_matched_mpie(candidate_mean, matched_mean, sign, mpie=MPIE)` gates
`ORIENTED_MATCHED_DELTA` specifically — never the structural delta, never
the candidate mean alone — matching the design's restored semantics
exactly (`docs/research/H05_TAKER_IMBALANCE_PREREG.json` ->
`mpie.applies_to == "ORIENTED_MATCHED_DELTA"`).

## 13. 1w/2w/4w

`dependence_sensitivity_bundle`/`block_bootstrap_sensitivity` reuse the
H04 implementation-completion pattern exactly: bare seed for
`block_size_weeks==1`, `SeedSequence([seed, size])` for `{2,4}`, terminal
partial block retained
(`test_47_terminal_partial_block_retained`), no row ever split across
blocks (`test_48_no_row_split_across_blocks`), deterministic across
repeated calls (`test_44`-`test_46`). `bootstrap_sign_gate` implements the
exact `p025>0`/`p975<0` rule at all three block sizes jointly
(`test_49_continuation_bootstrap_p025_gate`,
`test_50_reversal_bootstrap_p975_gate`), and is applied only to
`candidate_mean` (`X`), never to the matched/structural/shift deltas —
three separate estimands are never conflated in the per-cell output
(`matched_random`, `structural_control`, `negative_control`, and
`dependence_sensitivity` are always distinct dict keys in
`evaluate_cell`'s output; none is derived from another).

## 14. W/q/H robustness

`has_adjacent_pair_support` (reused verbatim from the H04 pattern) gates
`q` (2-of-3 adjacent) and `H` (2-adjacent).
`has_adjacent_w_directional_support` implements the newly-tightened `W`
rule: at least one adjacent `W` with `directional_support` (direction-only
`ORIENTED_PRIMARY/MATCHED/STRUCTURAL > 0`, not the full numeric gates) —
verified by `test_38_w_directional_support_gate`,
`test_39_isolated_w_cannot_promote`, and
`test_directional_support_direction_only_not_full_gate` (a tiny positive
delta that would fail the full `CONTROL_DELTA_MIN` numeric gate still
counts as directional support).

## 15. BUY/SELL

`direction_symmetry_gate` requires `ORIENTED_PRIMARY > 0` independently
for both `D=+1` and `D=-1` under the same `sign`
(`test_40_buy_sell_symmetry_gate`, `test_41_one_sided_cannot_promote`).

## 16. Year rule

`year_stability_gate` requires `S * yearly_mean(y) > 0` in at least 4 of
5 years, with no `exclude`/`drop` parameter in its signature at all —
there is no code path by which a shock year could be silently removed
before the count is taken (`test_42_four_of_five_year_rule`,
`test_43_no_shock_year_exclusion_path`).

## 17. Concentration

`concentration_from_times` reports `largest_month_share`,
`top5_month_share`, `buy_share`/`sell_share`, `median_spacing_minutes`,
plus the two new fields the design requires:
`largest_candidate_contribution_share` and
`top_decile_contribution_share` (computed from `|X|`-weighted
contribution shares, never PnL). `structural_control` additionally
reports `unmatched_candidate_N`/`unmatched_candidate_share`.

## 18. Candidate clustering

`candidate_clustering_diagnostic` is computed from the **post-refractory
kept candidate indicator** (never outcome/return values) at the fixed
lags `{1,2,4,8,16,32,64}` days, reporting the largest qualifying lag
(`test_53_l_dep_uses_largest_qualifying_lag`, mirroring H04's own
largest-lag lesson for its analogous long-dependence diagnostic).

**Implementation clarification (resolved here, not silently chosen):**
the design's own text ("candidate indicator series for each cell") does
not explicitly say whether "candidate" means the raw pre-refractory
qualifying mask or the post-refractory kept set. This implementation uses
the **post-refractory kept set**, because that is the population that
actually enters every other per-cell gate (matched-random, structural,
shift, bootstrap) — using a different, pre-refractory population for the
clustering diagnostic alone would make it describe a different
population than the one the gates evaluate. This choice does not change
any numeric threshold, does not add a new selectable parameter, and does
not gate promotion (the diagnostic remains descriptive-only either way).

## 19. 45-cell completeness

`evaluate_h05` iterates `W_WINDOWS × Q_THRESHOLDS × HORIZONS` = `3×3×5 =
45` and asserts this via
`test_54_55_56_search_surface_and_dual_sign_emission` and
`test_evaluate_h05_no_forbidden_months` (which runs the full pipeline
end-to-end on a synthetic fixture and checks `len(cells) == 45`). Every
cell's `claim_evaluation` dict always contains both `"continuation"` and
`"reversal"` keys — dual-sign emission is unconditional, not
cell-dependent.

## 20. 225-cell cumulative accounting

`evaluate_h05`'s `search_surface.batch01_cumulative_cells` is hardcoded to
`225` (`45×5` families), matching
`docs/research/H05_TAKER_IMBALANCE_PREREG.json` ->
`search_surface.batch01_cumulative_cells` and the design document's own
accounting (H01-H04 = 180, +45 = 225). Sign multiplicity (continuation +
reversal on the same 45 cells) is recorded as a separate field
(`sign_multiplicity`), never added into the 225 total.

## 21. 2025/2026 guards

`ValidationWindowForbidden` is raised by
`assert_development_outcome_window`, `load_development_1m` (if the loaded
1m bars reach 2025+), and `_forbid_partition_name` (called before any
2025/2026-named file is opened). `evaluate_h05` additionally asserts, as a
defense-in-depth check, that no cell's `concentration.by_month` contains a
`"2025"` or `"2026"` key before returning — verified by
`test_evaluate_h05_no_forbidden_months` and
`test_60_loader_rejects_2025_2026_partitions`.

## 22. No H01-H04 outcome-derived design import

`h05_taker_imbalance_lib.py` does not import, reference, or reuse any
function, threshold, or constant from
`h01`/`h02`/`h03`/`h04_trend_pullback_continuation_lib.py`. Every
implementation-lesson reuse (membership-safe exclusion, real-timestamp
calendar keys, candidate-weighted standardization, 1w/2w/4w wiring from
the first commit) is a freshly written, independent implementation of the
same *pattern*, not a shared import — consistent with the design
document's own adaptivity disclosure (section 0). No H01-H04 files were
read, modified, or executed as part of writing this module.

## 23. No product code touched

Only `scripts/research/h05_taker_imbalance*.py`,
`tests/research/test_h05_taker_imbalance.py`,
`docs/research/H05_TAKER_IMBALANCE_PREREG.{md,json}`,
`docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md`, and
`docs/RESEARCH_LEDGER.md` were created or modified in this task. No
`app/`, `services/`, or forecasting/product code path was touched.

## 24. Both-signs-conflict audit-failure rule

`docs/research/H05_TAKER_IMBALANCE_PREREG.json` ->
`both_signs_cannot_pass_simultaneously.if_conflicting_promotion_
conditions_appear == "AUDIT_FAILURE_STOP"`. No code in this freeze
computes a single automatic "winning sign" — `evaluate_cell` always
returns both `claim_evaluation["continuation"]` and
`claim_evaluation["reversal"]` independently, and no downstream function
in this freeze collapses them into one verdict. Final promotion
decisions (the cross-cell `q`/`H`/`W`-neighborhood, year-stability, and
symmetry aggregation across the 45-cell grid) are deliberately left to a
future development-result round that will actually run against real
outcomes — this freeze provides the tested building blocks
(`has_adjacent_pair_support`, `has_adjacent_w_directional_support`,
`year_stability_gate`, `direction_symmetry_gate`) but does not itself
invoke them to declare one automatic verdict, exactly as H04's own
`evaluate_h04` left final promotion to a human-reviewed development
summary rather than auto-deciding it in code.

## 25. Verification commands run in this task

```
python -m pytest tests/research/test_h05_taker_imbalance.py -q   # 65 passed
python -m compileall -q scripts/research tests/research           # clean
git diff --check                                                  # clean
```

`--stage dev-run` was **not** run. No `*.parquet` file from the accepted
dataset was opened. No real H05 event counts, percentiles, or future
returns were computed.

## 26. Objective blockers remaining (as of this correction round)

**None identified after this correction.** The BLOCKER originally noted
in section 6 (the structural gate compared the full, unrestricted
`candidate_mean` against a control mean standardized only over overlap
strata — quantities on different support) is closed in this revision by
the like-with-like `structural_delta` computation. The
clustering-diagnostic population choice (section 18) remains a
documented, non-blocking clarification, unaffected by this correction.

**Superseded by section 28:** a subsequent, independent pre-outcome audit
found five further findings (M-01 through M-05) against the commit this
section originally cleared (`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1`).
This section's "none identified" conclusion is accurate only for the
narrower B-01 structural-support scope it actually checked — it is
preserved here unedited, per the "do not erase history" requirement of
the repair task that added section 28.

## 27. Freeze identity (as of this correction round)

`H05_PREREG_SHA_V1` = `9502006eb4797a9947c61d8d04acd1345ed41e5e`
(status `SUPERSEDED_PRE_OUTCOME`, preserved unamended — see
`docs/research/H05_TAKER_IMBALANCE_PREREG.json` `version_history`). This
correction is committed as a normal descendant of that commit
(`research(h05): align structural gate on overlap support`), containing
the corrected prereg MD/JSON, the corrected implementation, the
structural-support-correction regression tests, this audit update, and
the ledger correction entry.

**Superseded by section 28:** the sentence below, declaring the resulting
commit (`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1`) to be both
`H05_PREREG_SHA` and `H05_RESEARCH_CODE_FREEZE_SHA`, was itself premature
— a subsequent independent audit found five further findings (M-01
through M-05) against it, and it is now also `SUPERSEDED_PRE_OUTCOME` per
`docs/research/H05_TAKER_IMBALANCE_PREREG.json` `version_history`. Both
identities remain unset pending a further independent re-audit of the
repair in section 28. The original sentence is preserved unedited below,
per the "do not erase history" requirement:

> That descendant commit becomes the new `H05_PREREG_SHA` and, since the
> implementation is fully frozen in the same commit, also the new
> `H05_RESEARCH_CODE_FREEZE_SHA`. No design parameter changed; only the
> structural estimand's support was corrected, pre-outcome, without
> inspecting any real H05 outcome.

---

## 28. Second independent pre-outcome audit round — B-01 re-verification, M-01 through M-05, M-09

**Status:** PRE-OUTCOME AUDIT + BOUNDED REPAIR. Not a market-outcome
computation. Not a design change. Not R3. Not H06. Not Batch01 synthesis.
**Audited commit:** `70797aaeed70fa3d4c584d96ca929f5a8e7e92d1` (repair
candidate, itself now superseded by this repair round's new commit).
**Repair scope:** strictly bounded to findings that could change H05
pass/fail, change the preregistered estimand, create an undeclared
analytical degree of freedom, permit fail-open behavior, or prevent
reproducibility of the frozen analytical procedure. No new hypothesis, no
new threshold, no new control, no new search dimension, no `W`/`q`/`H`
change, no sign-multiplicity change, and no general refactoring were
introduced.

### B-01 (structural support) — independent re-verification

**Classification: `CLOSED`.**

Re-inspected the exact diff `9502006..70797aa` against all seven required
criteria:

1. **Identical overlap strata on both sides** — confirmed: `overlap_strata
   = cand_strata & ctrl_strata`, and both `cand_stratum_mean`/
   `ctrl_stratum_mean` are populated only `for k in overlap_strata`.
2. **Identical candidate-derived weights on both sides** — confirmed: one
   `weight` dict (`{k: n / total_overlap_cand_n ...}`) is applied to both
   `candidate_overlap_standardized_mean` and
   `structural_control_standardized_mean`.
3. **Unmatched candidate strata cannot affect the delta** — confirmed:
   `cand_by_stratum` includes every candidate, but the summation loop only
   ever reads `overlap_strata` keys; unmatched-stratum rows never enter
   `cand_stratum_mean`/`cand_stratum_n`/`weight`.
4. **The candidate-side standardized mean actually enters the gate** —
   confirmed: `structural_delta = candidate_overlap_standardized_mean -
   structural_control_standardized_mean`, and `ORIENTED_STRUCTURAL_DELTA
   = oriented_from_delta(structural_delta, sign)`.
5. **`W` directional structural support uses the same repaired estimand**
   — confirmed: `directional_support` takes `structural_delta` (not a
   mean) and `evaluate_cell` passes `structural["structural_delta"]` into
   it.
6. **No alternative code path still uses the old full-candidate structural
   delta** — confirmed via `grep -n "structural_mean\b\|candidate_
   standardized_mean\b"` across both `h05_taker_imbalance_lib.py` and
   `h05_taker_imbalance.py`: zero matches.
7. **The raw primary `candidate_mean` is unchanged for gates requiring the
   full population** — confirmed: `ORIENTED_PRIMARY`, `ORIENTED_MATCHED_
   DELTA`, and (at the time of this check) `ORIENTED_SHIFT_DELTA` all
   still read the same `candidate_mean` argument, unmodified.

**Independent adversarial re-verification** (constructed fresh, not
reusing the existing regression tests): a synthetic 12-row fixture with
one overlap stratum (candidate mean = control mean = `0.0`) and one
unmatched candidate stratum forced to `1e6`. Result: `full_candidate_mean
= 500000.0` (moved materially), but `candidate_overlap_standardized_mean
= structural_control_standardized_mean = structural_delta = 0.0` and
`structural_gate` is `False` for both `S=+1` and `S=-1`. Reproduced as
`test_b01_structural_gate_unaffected_by_unmatched_extreme_independent_check`.

### M-01 — `+6h` population support drift

**Classification: `REPAIRED`.**

Confirmed the same defect class as B-01, transplanted onto the negative
control: `negative_control_bundle` computed `shifted_mean` only from
candidates with a valid, finite-after-normalization `+6h` comparator (a
subset), while `candidate_minus_shifted` differenced it against `_mean
(cand["norm"])` — the FULL candidate population. Repaired by computing
`candidate_shift_support_mean` over exactly the positions that
contributed to `shifted_mean` (tracked via `shift_support_positions`,
filtered by the same `elig` mask used for `shifted_mean` itself), and
defining `shift_delta = candidate_shift_support_mean - shifted_mean`.
`claim_evaluation`'s `shift_delta` parameter (renamed from
`shifted_mean`) now uses `oriented_from_delta`/`gate_from_delta`, exactly
mirroring the structural fix. The full candidate mean is retained as
`full_candidate_mean` for transparency only. Verified by
`test_m01_01_shift_delta_uses_same_support_not_full_candidate_mean`
(candidates without a valid `+6h` comparator forced to `1e6`; the full
mean moves past `100`, but `shift_delta` stays exactly `0.0` and
`shift_gate` is `False` for both signs) and
`test_m01_02_shift_gate_uses_shift_delta_not_shifted_mean_alone`.

### M-02 — invalid structural strata encoded as `-1`

**Classification: `REPAIRED`.**

Confirmed: `price_alignment_index`/`bin_index_at_median` both return `-1`
where their underlying value is unavailable, and neither `eligible_index`
nor `candidate_mask`/`ordinary_control_mask` previously excluded `-1`
rows — such a row could enter a structural stratum key as an undeclared
level. Repaired by adding `(pa != -1) & (psb != -1) & (ab != -1)` to
`eligible_index` — the single gate both candidate and ordinary-control
indices are intersected with, so both sides fail closed identically. No
`UNKNOWN` stratum was invented. Verified by
`test_m02_01_eligible_index_excludes_undeclared_minus1_price_alignment`
(three rows, each with exactly one undeclared `-1` dimension, are all
excluded) and `test_m02_02_valid_rows_unaffected_by_minus1_fix`.

### M-03 — incomplete trailing-30d activity history

**Classification: `REPAIRED`.**

Confirmed: `rolling_midrank_percentile` computed a percentile as soon as
`n_ref > 0` (at least one finite prior reference value), producing an
unintended EXPANDING window for the first `window-1` rows of any series —
not the frozen "trailing 30-day" requirement. This function is shared by
`ABS_IMBALANCE_PCTL_W`, the price-strength percentile, and the activity
percentile alike; the root cause was fixed once, in the shared function,
rather than duplicated per-caller (the narrower, more consistent fix —
special-casing only `activity_bin` would have left the identical bug live
in the imbalance-extremeness and price-strength percentiles, an
inconsistency). Repaired by adding a `pushed_count` clock: a percentile
is now withheld until `pushed_count >= window` (a full window of PRIOR
bars has elapsed — a time/grid requirement, not a "N finite observations"
requirement; some of those prior bars may still be individually
non-finite, correctly yielding a smaller `N_ref`). No future observation
was ever used before this fix and none is used after it. Verified by
`test_m03_01_insufficient_history_is_unavailable`,
`test_m03_02_exact_required_history_becomes_available` (first non-NaN
value is exactly at index `window`, not `1`), `test_m03_03_no_future
_leakage_after_fix`, and `test_m03_04_activity_bin_respects_incomplete
_history` (3 bars against `REF_STEPS=2880` yields entirely unavailable
`activity_bin`, never fabricated).

### M-04 — no machine-enforced final promotion decision

**Classification: `REPAIRED`.**

Confirmed: `evaluate_h05`/`evaluate_cell` computed every individual gate
per cell but never combined them, deliberately leaving cross-cell
`q`/`H`/`W`-neighborhood aggregation and final promotion to a future
human-reviewed development-result round (matching H04's own historical
practice). Per M-04's explicit requirement, implemented
`evaluate_promotion(cells)` (new function) plus a private
`_cell_all_gates_pass(ev)` fail-closed conjunction helper. Uses ONLY the
already-frozen criteria M-04 lists (primary, MPIE, structural, shift,
1w/2w/4w bootstrap, `q` 2-of-3-adjacent full-gate-passing support, `H`
2-adjacent full-gate-passing support, `W` ≥1-adjacent directional support
via the existing `has_adjacent_w_directional_support`, yearly ≥4/5,
BUY-side/SELL-side primary orientation — implemented via the existing
`direction_symmetry_gate`, which already implements exactly that pair of
requirements together, reused rather than duplicated). Every component
check is `is True`, never a truthy check, so `None` is always fail-closed.
Both-signs-promoted returns `AUDIT_FAILURE_BOTH_SIGNS_PROMOTED`, matching
the already-frozen audit-failure rule. Wired into `evaluate_h05`'s output
as `results["promotion"]`. Deliberately does **not** auto-distinguish
`H05_REJECTED_SPECIFIC_CLAIM` from `H05_INCONCLUSIVE` — documented as an
explicit, intentional scope boundary (that distinction is not reducible
to the listed criteria without inventing a new numeric threshold, which
M-04 prohibits), not a gap. Verified by nine tests
(`test_m04_01` through `test_m04_09`): an all-`None` baseline never
promotes; a genuinely constructed passing neighborhood promotes exactly
the expected sign and cell; both-signs-promoted triggers the audit
-failure verdict; a single `None` gate at an otherwise-perfect cell blocks
promotion; non-adjacent `q`, non-adjacent `H`, and an isolated `W` (real
neighbors forced to `directional_support=False`) each independently block
promotion; a missing/`None` `year_stability_gate` and a missing/`None`
`direction_symmetry_gate` each independently block promotion.

### M-05 — dataset identity / manifest optional

**Classification: `REPAIRED`.**

Confirmed: `load_development_1m` only validated
`reports/snapshot_manifest.json` `if runtime_snap.exists()` — a
`dataset_root` with no manifest at all silently skipped identity
verification entirely and proceeded to read whatever parquet was present.
Repaired by making the manifest's existence mandatory: `if not
runtime_snap.exists(): raise H05Error(...)`, before the existing
`snapshot_id` mismatch check. No real parquet content was opened or
inspected while making or testing this fix — every test uses a
`tmp_path`-scoped synthetic directory tree with zero real data. Verified
by `test_m05_01_missing_manifest_fails_closed`,
`test_m05_02_mismatched_snapshot_id_fails_closed`, and
`test_m05_03_matching_manifest_no_longer_short_circuits_missing_check`
(a correct manifest with no parquet at all fails at the next real check,
`list_development_parquet_paths`, proving the manifest check runs first
and, once satisfied, genuinely allows progression rather than silently
succeeding).

### M-09 — numpy/pandas reproducibility

**Classification: `ALREADY_CLOSED`.**

`requirements.txt` already pins `numpy==2.1.3` and `pandas==2.2.3`
(unconditionally, not research-specific). The validated H05 test
environment for this repair round used exactly these versions
(`numpy 2.1.3`, `pandas 2.2.3`), plus `pyarrow==17.0.0` from
`requirements-research.txt` (also already pinned). No repository
dependency file was modified — nothing was unpinned, and no package was
opportunistically upgraded. Recorded here per M-09's own instruction to
"record the versions used": **numpy 2.1.3, pandas 2.2.3, pyarrow
17.0.0, Python 3.11.15.**

### Findings explicitly NOT repaired (out of bounded scope)

None of M-01 through M-05 had a "descriptive-only" component that would
have justified leaving any part unrepaired under the Phase 3 bounded
-repair criteria — all five could change `H05` pass/fail or permitted
fail-open behavior, so all five were repaired in full within their stated
scope. No repair in this round touched quote-volume diagnostics,
clustering-diagnostic cosmetics, bootstrap methodology, alternative
controls, or additional robustness checks — all explicitly out of scope
per the repair task's Phase 3 exclusions.

### Verification (synthetic/unit only, this round)

```
python -m pytest -q tests/research/test_h05_taker_imbalance.py   # 95 passed (73 pre-existing + 22 new)
python -m compileall -q scripts/research tests/research           # clean
git diff --check                                                  # clean
python -c "import json; json.load(open('docs/research/H05_TAKER_IMBALANCE_PREREG.json'))"  # valid JSON
```

`--stage dev-run` was **not** invoked. No `*.parquet` file from the
accepted dataset was opened. No real H05 event counts, percentiles, or
future returns were computed. 2025/2026 were not inspected. Batch01
synthesis was not started.

### Identity after this repair round

This repair is committed as a normal descendant of
`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1` (that commit is not amended).
The resulting commit is a **repair candidate only** —
`H05_PREREG_SHA` and `H05_RESEARCH_CODE_FREEZE_SHA` remain **unset**,
pending a further independent pre-outcome re-audit, per this repair
task's own explicit instruction.
