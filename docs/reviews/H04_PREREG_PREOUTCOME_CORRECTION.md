# H04 Pre-Outcome Preregistration Correction

**Status:** PRE-OUTCOME CORRECTION ONLY. Not a market-outcome computation.
Not a research-parameter change. Not R3. Not H05.
**Superseded prereg:** `H04_PREREG_SHA_V1` =
`314292ed9824e824522274d1b64874bf91d71b23` — status `SUPERSEDED_PRE_OUTCOME`
(preserved unamended).
**Real H04 market outcomes computed before this correction:** **NONE.**

This correction was discovered during independent implementation review,
not from any observed H04 result. No real accepted parquet has been read
under either `H04_PREREG_SHA_V1` or this correction. 2025 and 2026 remain
untouched.

## 1. Exact issue

`docs/research/H04_TREND_PULLBACK_PREREG.md` §11 (and the corresponding
JSON) always said the structural control — established trend + near-neutral
recent move (`abs(RECENT_RATIO)<0.10`) — should be "matched where possible
on calendar month, trend direction, and trend-strength bin
(`[0.80,0.90)`, `[0.90,1.00]`)".

The implementation at `H04_PREREG_SHA_V1`
(`scripts/research/h04_trend_pullback_continuation_lib.py`,
`structural_control_bundle`) computed that matching only as a **coverage
diagnostic** (`matched_N`/`unmatched_N`/`unmatched_share`, counted from the
control population's perspective). The actual **primary structural
comparison** — the number that feeds `structural_gate` — was
`mean(candidate_norm) - mean(entire_eligible_control_norm)`: the full,
unstandardized control population, not anything restricted or weighted by
the matching strata.

## 2. FP/FN pathway

Because the frozen candidate rule (`TREND_PCTL_L>=0.80` and a specific
depth band) and the frozen control rule (`TREND_PCTL_L>=0.80` and
`abs(RECENT_RATIO)<0.10`) are different selection rules, nothing guarantees
the two populations have the same calendar-month / trend-direction /
trend-strength-bin **composition**. If, for example, pullback candidates
happen to concentrate more in the `[0.90,1.00]` trend-strength bin while
near-neutral controls concentrate more in `[0.80,0.90)` — or the two
populations differ in month or direction mix — then
`mean_pullback - mean_full_control` partly reflects that **composition
difference**, not the incremental value of the pullback shape itself.

This is a genuine two-sided risk:

- **False positive:** a real difference in trend-strength/month/direction
  mix (unrelated to pullback) could push the unstandardized delta over
  `CONTROL_DELTA_MIN=0.05`, making a non-mechanism look like it passes the
  structural gate.
- **False negative:** the same kind of mix difference could offset or mask
  a genuine pullback-specific effect, making a real mechanism look like it
  fails the structural gate.

`tests/research/test_h04_trend_pullback_continuation.py::
test_structural_composition_confound_regression` constructs exactly this:
two trend-strength-bin strata where the *within-stratum* candidate and
control means are identical (no pullback-specific effect), but candidates
and controls have opposite bin composition. The old-style unstandardized
delta is `+0.06` (misleadingly clears `CONTROL_DELTA_MIN=0.05`); the
corrected standardized delta is `0` and `structural_gate` is `False`.

## 3. Exact correction

`structural_control_bundle` now computes a **frozen deterministic
stratified standardization**, not a random-matching procedure and not a
new selectable parameter:

1. strata are exactly calendar month × trend direction × trend-strength
   bin (the same bins already named in the frozen design — no new bins);
2. for every stratum with both candidate and control observations (the
   "overlap" strata), compute the candidate mean and control mean;
3. weight each overlap stratum by the candidate's own frequency in that
   stratum (`w_s = candidate_N_s / total overlap candidate_N`);
4. `STRUCT_CANDIDATE_MEAN` and `STRUCT_CONTROL_MEAN` are the `w_s`-weighted
   averages of the per-stratum means;
5. `STRUCTURAL_DELTA = STRUCT_CANDIDATE_MEAN - STRUCT_CONTROL_MEAN`;
   `structural_gate = STRUCTURAL_DELTA >= CONTROL_DELTA_MIN (0.05)`.

Control-only strata (control observations with no candidate counterpart)
receive zero candidate weight and do not enter `STRUCT_CONTROL_MEAN` — H04
asks what the candidate population looks like relative to the near-neutral
control state, not the unconditional composition of all near-neutral trend
moments. Candidates whose exact stratum has no control counterpart are
outside the overlap population; they are reported explicitly
(`unmatched_candidate_N`/`unmatched_candidate_share`) and never silently
dropped, but they do not enter the standardized comparison. No new
arbitrary unmatched-share pass/fail threshold is introduced — high
unmatched share remains a visible interpretability/concentration warning
for whoever judges a future candidate, exactly as the correction task
required. No post-outcome fallback matching hierarchy exists.

An optional `full_control_unstandardized_mean` descriptive field may still
be reported for transparency, but it is explicitly documented (in code
comments, the prereg, and this audit) as **not permitted to feed the
structural gate**.

## 4. Why no market result could have influenced this correction

- No `--stage dev-run` invocation has ever been made against real accepted
  parquet for H04, under `H04_PREREG_SHA_V1` or since.
- The bug was found by re-reading the frozen prereg's own matching language
  side-by-side with the implementation's return-value usage inside
  `evaluate_cell` — a pure code/spec consistency check, not an inspection
  of any computed effect size.
- The regression test that demonstrates the confound
  (`test_structural_composition_confound_regression`) uses fully synthetic,
  hand-constructed fixture data designed to isolate the composition
  artifact; it does not use, and could not have used, any real BTC price
  history.
- The correction does not change the candidate rule, the control's
  event-level definition (`TREND_PCTL_L>=0.80 AND abs(RECENT_RATIO)<0.10`),
  the depth bands, `L`, `P`, `q`, the horizon ladder, the refractory, MPIE,
  `CONTROL_DELTA_MIN`, the matched-random seed, the bootstrap seed, or the
  45-cell search surface — only *how the already-frozen matching strata are
  used to compute the structural comparison*.

## 5. Bootstrap-scope clarification

Not a redesign. The UTC-week block bootstrap (seed `20260903`, 2000
replicates) was already, in the actual implementation, computed only on
the **candidate** population's own `NORM_TREND_CONT_RET_H` mean and
continuation-positive share — it never computed a bootstrap of the
candidate-minus-matched contrast. This correction makes that scope
**explicit** in both the MD and JSON prereg (§17 / `uncertainty.applies_to`
/ `uncertainty.is_mpie_confidence_interval: false`), so a future reader
cannot mistake the candidate block-bootstrap interval for an uncertainty
band on the MPIE gate. Matched-random uncertainty remains represented
solely by the frozen 100-replicate matched-random distribution, now
additionally summarized by persisted `p025`/`p50`/`p975` for both the
matched mean and the matched positive share (`matched_random_bundle`
output; documented in `matched_random.distribution_summaries`). No new
inference gate is introduced. MPIE is unchanged.

## 6. No search-surface change / no parameter change

Unchanged by this correction: `P=60m`; `L={240,480,960}`; `q=0.80`;
exclusive depth bands (`shallow [0.10,0.25)`, `moderate [0.25,0.40)`,
`deep [0.40,1.00)`); `H={15,30,60,120,240}`; 60m refractory; `MPIE=0.10`;
`CONTROL_DELTA_MIN=0.05`; the `+6h` negative control; the two-adjacent-
depth-band rule; the two-adjacent-horizon rule; the 4/5-year rule; the
UPTREND/DOWNTREND symmetry requirement; the matched-random seed
(`20260902`); the bootstrap seed (`20260903`); the 45-cell primary search
surface. Verified directly against the JSON prereg's frozen fields, which
are otherwise byte-identical to `H04_PREREG_SHA_V1` except for the fields
this correction explicitly documents.

## 7. Validation contamination

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- Real H04 outcomes computed (before or after this correction): **NO**
- R3 started: **NO**
- H05 started: **NO**
