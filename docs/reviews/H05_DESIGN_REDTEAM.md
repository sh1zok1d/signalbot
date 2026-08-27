# H05 Taker Imbalance → Subsequent Return Distribution — Pre-Outcome Design Red-Team

**Status:** DESIGN REVIEW ONLY. Not a preregistration. Not an implementation.
Not a market-outcome computation.
**Reviewed proposal:** the H05 design as specified in the task prompt
(base-volume taker imbalance, extremeness family, price-matched structural
control, matched-random/negative controls, search surface, gates,
verdicts).
**Output:** `docs/research/H05_TAKER_IMBALANCE_DESIGN.md` contains the
complete design produced by this review, already incorporating the fixes
identified below. No H05 code was written. No H05 market outcomes were
computed. 2025/2026 were not inspected. Real accepted parquet was not
opened.

This is the fifth and **final** primary mechanism family of R2 Batch 01.
After H05 closes (by whatever verdict), the next mandatory step is Batch01
synthesis — **not** a new H06.

**Addendum — PRE-OUTCOME DESIGN CORRECTION.** A second, independent
pre-outcome review of this design (still before any real H05 outcome was
computed) found two material control gaps and two formalization gaps in
the version originally produced by this red-team pass. All four are
closed in `docs/research/H05_TAKER_IMBALANCE_DESIGN.md` (current
revision) and are recorded inline at Q4, Q5, Q6, Q8, Q14 (renumbered
discussion), Q16, Q17, Q18 below, plus this addendum summary:

1. **Price sign was not controlled (material).** Matching on `D` (sign of
   taker imbalance) does not control the sign of *contemporaneous price
   return* — the two differ, so a candidate and a control row could share
   `D` while having opposite-signed `PRICE_RET_W`, leaving price-momentum
   direction as an uncontrolled confound. Fixed by adding
   `price_alignment ∈ {ALIGNED, OPPOSED}`, built from
   `SIGNED_PRICE_RET_W(T) = D(T) * PRICE_RET_W(T)`, as a mandatory
   structural-match dimension alongside the existing magnitude-only
   `price_strength_bin`. Exact-zero `SIGNED_PRICE_RET_W` is deterministically
   assigned to `OPPOSED` (design doc §9) — a frozen, symmetric, pre-outcome
   choice, not a third category.
2. **Activity was not actually controlled (material).** The research
   question (§1) claims incremental information "beyond ... ordinary
   market activity," but the design left activity/volume descriptive-only,
   which cannot support that clause. Fixed by promoting `activity_bin`
   (a causal 2-level split of trailing-30-day `TOTAL_W` percentile at
   0.50) to a mandatory structural-match dimension. The claim is retained
   broad (not narrowed) and the control is added, per the reviewed
   preference.
3. **"Candidate-independent" long-dependence diagnostic was misnamed
   (formalization).** The diagnostic is computed from each cell's own
   candidate indicator, which varies with `W`/`q`, so it cannot be
   candidate-independent. Renamed **outcome-independent, cell-specific
   candidate-clustering diagnostic**; the underlying computation (ACF of
   the candidate indicator at fixed lags `{1,2,4,8,16,32,64}` days,
   `|ACF|>=0.20`) is unchanged.
4. **The "1w/2w/4w survives" gate was underspecified (formalization).**
   Now frozen precisely: the UTC-week block-bootstrap interval of the
   candidate primary normalized signed-return mean must exclude zero in
   the declared direction (`p025>0` for continuation, `p975<0` for
   reversal) at each of 1w/2w/4w, explicitly distinguished from the
   matched-random distribution's own `p025/p50/p975` and from the
   structural-control delta — none of the three may be substituted for
   another.

A fifth, lighter re-evaluation (not a blocker, a strengthening) tightened
the `W`-robustness rule from a pure "no severe contradiction" check to a
directional-consistency requirement: a fully isolated `W` (no adjacent `W`
even directionally agreeing) can no longer reach `CANDIDATE_FOR_FREEZE`,
closing a magic-lookback risk the original soft rule under-constrained.
See Q8 below.

**No real H05 outcome was inspected to make any of these five corrections.**
The overall mechanism, sign alternatives, `W`/`q`/`H` surface (still 45
cells), refractory rule, `MPIE`, `CONTROL_DELTA_MIN`, seeds, and Batch01
225-cell accounting are unchanged by this addendum.

---

## Summary table

| # | Topic | Classification | One-line resolution |
|---|---|---|---|
| 1 | Sign alternatives (continuation vs reversal) | resolved, disclosed | both preregistered as competing interpretations of one signed statistic (mirrors H03), not a magnitude expansion of the 45-cell surface |
| 2 | Base-volume vs quote-volume imbalance | NO ISSUE | base-volume is primary; quote-volume is descriptive-only, cannot rescue |
| 3 | Extremeness family construction (nested vs exclusive) | resolved, explicit reasoning | NESTED thresholds (unlike H04's depth bands) — imbalance severity has a monotonic dose-response prior under both candidate signs |
| 4 | Structural control's "ordinary" population definition | **MAJOR gap, closed** | fixed `[0.60,0.80)` band, decoupled from the q-cell under test — the raw proposal left this ambiguous, which is exactly the kind of discretion that must be closed pre-outcome |
| 4b | Structural control's price-sign confound | **MATERIAL gap, closed (addendum)** | `D` does not control the sign of `PRICE_RET_W`; added mandatory `price_alignment ∈ {ALIGNED,OPPOSED}` from `D * PRICE_RET_W`, exact-zero → `OPPOSED` (frozen, symmetric) |
| 5 | Price-return confound stratification | resolved (revised, addendum) | sign via `price_alignment` (new) + magnitude via `price_strength_bin` (2 coarse bins, same trailing midrank machinery) — the two together, not magnitude alone |
| 6 | Activity/volume confound | **resolved (reversed, addendum)** | now a MANDATORY matching stratum (`activity_bin`, causal trailing-30d `TOTAL_W` percentile split at 0.50) — descriptive-only was insufficient to support the "beyond ordinary market activity" claim |
| 7 | Refractory rule | resolved | either-direction suppression, keep earliest, 60m — matches H03/H04 precedent exactly, not re-derived |
| 8 | W (lookback) robustness | resolved (tightened, addendum) | directional-consistency requirement: ≥1 adjacent W must agree in sign/direction (primary sign, candidate-minus-matched, structural delta); a fully isolated W cannot pass, though it still need not clear full MPIE/CONTROL_DELTA_MIN |
| 9 | Search surface size | NO ISSUE | kept at 45 cells; sign multiplicity disclosed separately, not double-counted as cells |
| 10 | Whether the mechanism can collapse into price momentum | **disclosed limitation, not resolved** | the structural control is the best available pre-outcome mitigation; it cannot achieve perfect identification in an observational design |
| 11 | Long-dependence diagnostic naming | **formalization gap, closed (addendum)** | renamed from "candidate-independent" (internally inconsistent — it uses each cell's own candidate indicator) to "outcome-independent, cell-specific candidate-clustering diagnostic"; computation unchanged |
| 12 | 1w/2w/4w "survives" gate wording | **formalization gap, closed (addendum)** | frozen to a precise sign-exclusion rule on the candidate primary mean's block-bootstrap interval, explicitly distinguished from the matched-random distribution and the structural-control delta |

No `BLOCKER` findings remain. The original `MAJOR` finding (item 4) and
the addendum's two material gaps (items 4b, 6) are all closed pre-outcome;
the two formalization gaps (items 11, 12) and the `W`-robustness
tightening (item 8) are likewise closed pre-outcome, matching the batch's
practice of closing design gaps before preregistration rather than after.

---

## 1. Does the proposed imbalance statistic have clean market semantics?

Yes. `TAKER_IMBALANCE_W = (BUY_W - SELL_W)/TOTAL_W = 2*BUY_W/TOTAL_W - 1`
is a standard aggressor-side volume-imbalance ratio: the net fraction of
traded base volume initiated by buyers versus sellers over `[T-W, T)`,
bounded in `[-1, +1]`. This is a well-defined, economically interpretable
quantity (order-flow imbalance / order-flow toxicity literature) and
requires no new market-semantics invention. `TOTAL_W = 0` or non-finite is
treated as an explicit ineligibility condition, never replaced with zero —
consistent with the project's no-floor normalization philosophy.

## 2. Should base-volume or quote-volume imbalance be primary, and why?

Base-volume is primary. Quote volume ≈ base volume × price within the
window, so a quote-volume imbalance ratio implicitly upweights trades that
occurred at higher intra-window prices — entangling the "which side
initiated more volume" question with a within-window price-level effect
that has nothing to do with the aggressor-imbalance concept itself.
Base-volume imbalance is the cleaner, more standard measure of "which side
accounted for more traded size." Quote-volume imbalance is retained only
as a secondary semantic diagnostic (reported, never gating); base-vs-quote
must not become a second winner-selection axis, and "quote imbalance works
but base imbalance fails" is explicitly enumerated in the post-hoc
quarantine list (§ below) so it cannot rescue a failed primary result.

## 3. Is extreme absolute imbalance the right conditioning variable, and should the threshold family be nested or exclusive?

**Conditioning variable:** yes — `ABS_IMBALANCE_W = abs(TAKER_IMBALANCE_W)`
measured against its own trailing local reference is the direct analog of
H01's compression percentile and H03's impulse-severity percentile: "how
extreme is this window's one-sidedness relative to its own recent
history," with the midrank convention already frozen for those families.

**Nested vs exclusive — the key design choice, resolved explicitly and
differently from H04's lesson:** H04's pullback-depth dimension required
*exclusive* bands because depth had no a-priori monotonic direction (a
very deep pullback is at least as plausibly exhaustion as it is a "healthy"
continuation setup — see `docs/reviews/H04_DESIGN_REDTEAM.md` §5).
Imbalance severity is different: **both** candidate mechanisms in this
design (information-driven continuation *and* liquidity-exhaustion
reversal) predict a *monotonic* dose-response in the *magnitude* of the
effect as imbalance becomes more extreme — they disagree about the *sign*
of that effect, not about whether more extreme imbalance should matter
more. This is exactly the situation (H01, H03) where a **nested** "at
least this severe" threshold family is the scientifically correct
construction, and where the H04-style exclusive-band correction would be
inappropriate to blindly reapply. Freeze: `q ∈ {0.80, 0.90, 0.95}`,
candidate rule `ABS_IMBALANCE_PCTL_W(T) >= q` (nested, matching H01/H03
convention).

**Are these specific values contaminated by H03's own numbers?** `0.95`
overlaps H03's middle value; `0.80`/`0.90` do not match H01's or H03's
families exactly. This is disclosed as a **fresh choice** for H05, not a
copy of any H03 *outcome* — the values are generic round percentiles, and
sharing one value with a sibling family is a stylistic/batch-convention
overlap (like reusing MPIE=0.10 or the 100-replicate count), not an
outcome-derived one. A secondary, honest disclosure: choosing `0.80` as
the loosest gate (rather than mirroring H03's tighter `0.90` floor)
partially reflects the same batch-learned caution H04 already disclosed —
H03's tightest cells (`q=0.98`) produced small, fragile, non-coherent
populations, and a bounded ratio statistic like imbalance (many trades
netting toward the center by a CLT-like effect, especially at larger `W`)
plausibly saturates in extremity differently than a raw return does. This
is declared **PARTIAL** batch-internal adaptivity, exactly as H04 declared
for its own `q=0.80`, not hidden.

## 4. Is the proposed price-matched structural control strong enough, and is it fully specified?

The raw proposal names the *right* variables to match on (calendar month,
direction `D`, contemporaneous price-return strength, possibly activity)
but leaves **the control population's own definition** unspecified: is
"ordinary/non-extreme imbalance" defined as "below the q under test" (which
would make the control population depend on which q-cell is being
evaluated) or as one **fixed** band independent of `q`?

**This is a real, closeable gap (MAJOR).** If "ordinary" meant "percentile
< q for this cell," the `q=0.90` cell's control population would include
percentile-in-`[0.80,0.90)` observations — which are themselves the
`q=0.80` cell's own *candidates*. That cross-cell contamination (candidates
of one cell silently entering another cell's control) is structurally the
same failure mode as H04's original nested-threshold pseudo-robustness
problem, just relocated across cells instead of within one cell.

**Fix (closed in this pass, matching H03's own precedent for exactly this
situation):** freeze the "ordinary" control population as a **single fixed
band, decoupled from the q under test** — `0.60 <= ABS_IMBALANCE_PCTL_W(T)
< 0.80`, same direction convention (`D_ctrl = sign(TAKER_IMBALANCE_W)`,
nonzero). This is H03's own frozen moderate-band definition, reused
verbatim because H05's loosest severity gate (`q=0.80`) is numerically
identical to H03's loosest gate — a deliberate, minimal, already-frozen-
number reuse rather than inventing a new pair of bounds.

**Matching/standardization (revised, addendum):** candidate-weighted
deterministic standardization across exact overlap strata of (calendar
month) × (direction `D`) × (price alignment — new, see below) ×
(price-return-strength bin) × (activity bin — see Q5, now mandatory per
the addendum), restricted
to strata where both populations have observations, weighted by the
candidate's own stratum frequency — this is the H04 post-outcome-
correction lesson (`docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md`),
reused from the start this time rather than discovered as a bug. Control-
only strata get zero candidate weight; unmatched candidates are reported
(`matched_candidate_N`/`unmatched_candidate_N`/`unmatched_candidate_share`),
never silently dropped, and never rescued by an invented post-outcome
overlap threshold. If overlap support is insufficient under this
five-dimensional stratification, the correct verdict is `INCONCLUSIVE`,
not a post-outcome loosening of the strata.

**Addendum finding (material, closed):** the original three-dimensional
matching (month × `D` × price-strength) did not actually control the
*sign* of contemporaneous price return — `D` is the sign of taker
imbalance, not of `PRICE_RET_W`, so a candidate and control row could
share `D` while their contemporaneous price moves point opposite ways.
This left ordinary price-momentum direction as an uncontrolled confound,
directly undermining the "beyond contemporaneous price movement" clause
of the research question. Fixed by adding
`price_alignment = ALIGNED if D*PRICE_RET_W > 0 else OPPOSED` (exact
zero → `OPPOSED`, a frozen, symmetric, pre-outcome tie-break — see design
doc §9) as a mandatory match dimension distinct from the magnitude-only
`price_strength_bin`.

**Is the control "strong enough"?** It is the best available pre-outcome
observational design, not a perfect one — see Q4/Q17 for the honest limit
of what any structural control of this kind can achieve. The addendum's
corrections make it stronger (closing a real confound) at the cost of
finer stratification (see Q6 for the accepted trade-off).

## 5. Should total activity/volume be controlled?

**Decision (revised, addendum): YES — a mandatory matching stratum.**
The original pass in this review decided NOT to add activity as a
mandatory stratum (reasoning preserved below for the record), retaining
it only as a descriptive diagnostic. Independent pre-outcome review found
this insufficient: §1's research question explicitly claims incremental
information "beyond ... ordinary market activity," and a descriptive-only
diagnostic never actually removes activity as an alternative explanation
for an observed effect — it cannot support that clause of the claim.
Between the two ways to resolve this (control activity, or narrow the
claim to drop the clause), the design retains the broad claim and adds
the control, per the reviewed preference. `activity_bin` — a causal
2-level split of trailing-30-day `TOTAL_W` percentile at 0.50 (`LOWER` /
`UPPER`) — is now a mandatory fifth structural-match dimension (design
doc §9/§11), standardized with the same candidate-weighted,
zero-weighted-control-only-strata, unmatched-candidates-reported
discipline as every other dimension.

**Original reasoning (superseded, retained for the record):** adding a
third stratifying dimension (activity bucket) on top of month × direction
× price-strength risks exactly the over-fragmentation the batch has
learned to avoid, and was rejected in the first pass in favor of a
descriptive-only diagnostic (report the trailing activity percentile of
candidate vs. control populations per cell). This is superseded above —
fragmentation risk is real and now disclosed as an accepted trade-off
(see design doc §9's "why not over-match further"), not a reason to leave
the claim's "ordinary market activity" clause uncontrolled.

**Mechanism note:** activity may partly *mediate* genuinely informed
aggressive flow (an informed large order naturally coincides with
elevated volume), so controlling for it risks removing some of the real
mechanism along with the confound. This is accepted deliberately because
H05's claim is specifically that *imbalance itself* — not merely
"unusually high activity" — carries incremental information; that is a
scientific requirement of the claim as stated, not an optional caution.
If structural support becomes insufficient under the now-five-dimensional
stratification, the correct verdict is `INCONCLUSIVE`, never a
post-outcome trigger to drop `activity_bin` again.

## 6. Are continuation and reversal both legitimate preregistered alternatives, or is that excessive sign flexibility?

**Both are preregistered, deliberately, with explicit accounting.**
Market-microstructure theory genuinely supports both directions a priori:
informed-flow models predict continuation (aggressive flow impounds
information into price); liquidity-exhaustion/temporary-impact models
predict reversal (aggression that outpaces available liquidity produces a
transient move that partially reverts). Unlike H04 (where the specific
"pullback after established trend" claim had a clear directional prior),
H05's original Batch01 label never precommitted a sign. This is the exact
situation H03 already handled correctly (both continuation and exhaustion
preregistered as competing interpretations of the *same* signed statistic,
not as a doubling of the 45-cell surface) — H05 follows the identical
precedent. The sign-space doubling is accounted for explicitly (§ Global
search accounting) rather than silently ignored, and a hard rule prevents
the specific adaptive failure mode this flexibility could otherwise enable:
**a sign may not be selected, or promoted, because the *other* sign failed
first.** Both sign-candidate checklists are evaluated together in the same
development pass; if one sign is reported as a candidate, the ledger must
show the other sign's result too, not omit it.

## 7. Is 3W × 3q × 5H = 45 cells defensible?

Yes — it matches every prior family's cell budget exactly (H01=45,
H02=45, H03=45, H04=45) and is not enlarged for H05 despite the raw
proposal's suggestion being open to redesign. No additional `W`, `H`, or
threshold values are added merely to increase the chance of a favorable
cell.

## 8. Is the neighborhood rule strict enough to prevent magic-cell promotion, without making the natural timescale definitionally impossible?

Frozen rule: promotion requires **two adjacent thresholds** among the
nested `q` family (e.g. `q=0.80` and `q=0.90` both supporting the declared
sign with compatible control evidence) **and two adjacent horizons**
among the five `H` values. `W` retains a **weaker, explicitly different**
requirement than `q`/`H` — but is now tightened from a pure
"no-contradiction" check (addendum, see below).

**PRE-OUTCOME re-evaluation (addendum, tightened, not a blocker but a
strengthening):** the original "no severe cross-`W` contradiction" rule
was too permissive: a cell with **no** adjacent-`W` evidence at all
(neither confirming nor contradicting) would still have passed, which is
exactly the magic-lookback risk `W` being part of the searched 45-cell
surface should guard against. The revised rule requires **at least one
adjacent `W`** (same `q, H`, same declared sign) to agree in **direction**
on all three of: declared primary sign, `candidate_minus_matched` sign,
and structural-control-delta sign — without requiring that adjacent `W`
to clear full `MPIE`/`CONTROL_DELTA_MIN`. This distinguishes `W` (a
*scale* choice, like H04's `L`, where a genuinely scale-specific real
mechanism remains representable) from `q` (a *severity/dose-response*
dial, where full 2-of-3 agreement is required) and from `H` (an
*outcome-timescale* dial with the same established 2-adjacent
convention), while closing the specific gap that a **fully isolated** `W`
— no directional support anywhere nearby — could previously reach
`CANDIDATE_FOR_FREEZE` on its own. This correction was made without
inspecting any real H05 outcome.

## 9. Is requiring BUY/SELL symmetry scientifically justified?

Yes. H05's research question ("does aggressive taker-flow imbalance carry
incremental information about subsequent returns") is stated without
directional favoritism — it applies equally to aggressive buying and
aggressive selling. Requiring both sides to independently support the
*same declared sign* (continuation or reversal, whichever is being
evaluated) before promoting the symmetric claim is consistent with
`docs/R2_SCREENING_PROTOCOL_V1.md` §11 and with H03/H04 precedent. A
one-sided survival is `POSTHOC_UNTESTED` only.

## 10. Is the refractory rule appropriate?

60 minutes, either-direction suppression, keep earliest — identical to
H03/H04. Considered and rejected: a direction-aware rule where an
opposite-direction extreme inside the refractory window starts a *new*
episode. Rejected because (a) it introduces a genuinely new discretionary
choice with no batch precedent, increasing the surface for later
scrutiny of "why this rule," and (b) rapid direction flips within a short
window are at least as plausibly describing one volatile two-sided episode
as two distinct ones — exactly the ambiguity either-direction suppression
was designed to resolve conservatively in H03/H04. Reusing the batch-wide
60-minute convention for a third time is the safer, more clearly
non-outcome-driven choice.

## 11. Are matched-random and +6h controls redundant or complementary?

Complementary, not redundant. Matched-random preserves calendar-month and
direction composition only (a generic timing-null baseline, deliberately
*not* matched on price-return strength — adding that would blur it into a
duplicate of the structural control, which is explicitly the tool built to
test the price confound). The `+6h` circular shift attacks a different
axis: whether the *specific timing* of the true event (not just its
"typeness") carries the effect, preserving the original flow direction and
never redetecting. Both are retained; no alternative negative control was
tried and discarded.

## 12. Is the normalization outcome-independent?

Yes — trailing 30-calendar-day median absolute `H`-return on the same UTC
15m grid, using only observations whose own `H`-outcome is fully resolved
strictly before `T`; zero/non-finite/unavailable denominator is explicit
ineligibility, never floored; no full-development floor; no post-outcome
winsorization. Identical construction to H01–H04.

## 13. Is the complete-path 2025 embargo correctly defined?

Yes — an observation is eligible for horizon `H` only if `T + H` resolves
strictly before `2025-01-01T00:00:00Z`; no per-event truncation. Identical
rule to H01–H04, and to `docs/R2_SCREENING_PROTOCOL_V1.md` §1's boundary/
horizon-embargo fix.

## 14. Are 1w/2w/4w sensitivities wired into the planned implementation from the start?

Designed to be, yes — this is an explicit, named lesson from H04's own
implementation-completeness gap (`docs/reviews/
H04_PREOUTCOME_IMPLEMENTATION_COMPLETION.md`): the UTC-week block
bootstrap and its fixed 1-week/2-week/4-week sensitivity must be specified
together, computed unconditionally for every primary cell from the first
implementation commit, with the same deterministic block-grouping rule
(consecutive non-overlapping groups of chronologically ordered UTC weeks,
terminal partial block retained as one shorter block, never discarded) and
the same seed-derivation discipline (bare master seed for 1-week; deter-
ministic `SeedSequence([seed, block_size_weeks])` children for 2-week/
4-week). This design document freezes that requirement now, before any
H05 code exists, rather than allowing a future implementation task to
repeat the gap.

**Addendum (formalization, both closed pre-outcome):** (a) this diagnostic
was originally labeled "candidate-independent," which is internally
inconsistent since it is computed from each cell's own candidate
indicator series (necessarily varying with `W`/`q`) — renamed
**outcome-independent, cell-specific candidate-clustering diagnostic**;
the ACF-at-fixed-lags computation itself is unchanged. (b) the checklist's
"dependence-adjusted significance survives at 1w, 2w, and 4w" wording was
too ambiguous for a preregistration; it is now frozen as an explicit
sign-exclusion rule on the candidate primary mean's own block-bootstrap
interval (`p025>0` continuation / `p975<0` reversal at each block size),
kept explicitly distinct from the matched-random baseline's distribution
and from the structural-control delta — three different estimands that
must not be conflated or substituted for one another (design doc §22
item 12).

## 15. Is any design choice contaminated by H01–H04 post-hoc market observations?

No. Checked explicitly against the enumerated not-allowed list: H01's
low-vol persistence; H02's generic boundary bounce and lower/upper
asymmetry; H03's DOWN-side exhaustion tendency, short-vs-long horizon
asymmetry, and median-vs-mean tail asymmetry; H04's moderate-only
continuation, deep-pullback reversal, and UPTREND asymmetry. None of these
defined H05's mechanism, thresholds, signs, or gates. What *was* reused is
implementation/process discipline only (membership-safe controls,
candidate-weighted standardization, timestamp correctness, complete-
horizon embargo, dependence reporting, 1w/2w/4w sensitivity, post-hoc
quarantine language) — explicitly permitted by the task and consistent
with every prior family's own adaptivity disclosure.

## 16. What is the strongest plausible false-positive story under this design?

**Addendum note:** the version of this risk originally written here relied
on activity being only descriptive; that gap is now closed (Q5, addendum)
by making `activity_bin` a mandatory match dimension, so the specific
"unmatched liquidity regime" story below no longer applies to the frozen
design in its original form. The residual, still-live false-positive
risks are:

1. **Coarse-bin residual confounding.** `activity_bin` and
   `price_strength_bin` are each only 2 levels (a deliberately coarse,
   predeclared split to avoid over-fragmenting the now five-dimensional
   structural control). A finer regime effect that varies *within* the
   `LOWER`/`UPPER` activity or price-strength bins could still leak
   through the coarse split and masquerade as incremental imbalance
   information.
2. **Sparse-stratum standardization noise.** Five mandatory match
   dimensions (month × D × price_alignment × price_strength_bin ×
   activity_bin) shrink per-stratum sample sizes; even with
   candidate-weighting and unmatched-candidate reporting, a cell with many
   thin strata could produce an unstable standardized delta that clears
   `CONTROL_DELTA_MIN` by estimation noise rather than a genuine effect —
   this is exactly why year-stability (§20) and the dependence-adjusted
   bootstrap (§22 item 12) are required in addition to the point estimate,
   not as redundant checks.
3. **45-cell × 2-sign search surface.** Even with `MPIE`/`CONTROL_DELTA_MIN`
   floors and 2-of-3/2-adjacent neighborhood requirements, a wide search
   surface (225 cells cumulative across the batch, 45 + sign multiplicity
   for H05 alone) can produce a spuriously passing cell by chance without
   an explicit global multiple-testing correction beyond the disclosed
   cell count.

## 17. What is the strongest plausible false-negative story?

The price-matched structural control, by design, removes variation that
correlates with contemporaneous `PRICE_RET_W` (now both its sign, via
`price_alignment`, and its magnitude, via `price_strength_bin`). Since
aggressive imbalance and contemporaneous price movement are mechanically
linked in a liquid, continuously-arbitraged market (large aggressive
orders directly walk the book), a *real* imbalance-specific information
effect that is partly transmitted *through* the very price move it also
causes could be partially netted out by the structural standardization,
biasing the apparent incremental effect toward zero. This is an inherent
tension in any design built to isolate "beyond contemporaneous momentum" —
the control cannot be made stronger without directly attenuating a real
information channel that operates partly through price itself.

**Addendum: this risk is now larger, not smaller.** Adding `price_alignment`
and `activity_bin` as two further mandatory match dimensions (five total)
increases the chance that a genuine effect is over-conditioned away,
particularly if aggressive informed flow *itself* tends to coincide with
`ALIGNED` price moves and `UPPER` activity (a plausible mechanism story —
informed aggression both moves price in its own direction and shows up as
elevated volume). The design accepts this trade-off deliberately (Q5/Q4b
addendum) because the claim in §1, as stated, requires it — a false
negative from over-matching is judged less scientifically costly here than
a false positive from an uncontrolled price-direction or activity confound.
If this tension proves severe (e.g., persistently high unmatched-candidate
share, or a pattern of `INCONCLUSIVE` verdicts driven by sparse strata
rather than a genuine null), the appropriate future response is to revisit
the claim's scope in a later round — not to loosen these controls
post-outcome now.

## 18. What exact evidence would justify CANDIDATE_FOR_FREEZE?

All fourteen criteria in the frozen candidate-requirements checklist (see
design doc §22, revised this round), for one declared sign: correct
primary sign; MPIE cleared in a broad two-adjacent-`q` neighborhood; the
price-and-activity-matched structural standardized delta (now over five
strata: month × `D` × `price_alignment` × `price_strength_bin` ×
`activity_bin`) clears `CONTROL_DELTA_MIN`; the `+6h` negative control
clears `CONTROL_DELTA_MIN`; two adjacent `H` support the sign; **at least
one adjacent `W` directionally agrees** (revised — no longer merely "no
contradiction"); ≥4/5 development years; both `D=+1` and `D=-1` support
the same sign; no single month/episode dominates; the candidate primary
mean's own block-bootstrap interval excludes zero in the declared
direction at 1w, 2w, and 4w (precise sign-exclusion rule, revised);
adequate structural overlap across all five strata (low unmatched-
candidate share, resulting in `INCONCLUSIVE` rather than a pass if
inadequate — not an invented post-outcome pass/fail number); and the
primary close-return outcome itself (not a secondary statistic) carries
the effect.

## 19. What exact result would make us kill H05 without rescue?

Any material, non-isolated failure among: no sign is stable across a
two-adjacent-`q`/two-adjacent-`H` neighborhood, or no adjacent `W`
directionally agrees, for either declared sign; the price-and-activity-
matched structural delta fails `CONTROL_DELTA_MIN` for whichever cells
otherwise looked attractive (indicating the apparent effect is
substantially contemporaneous momentum/activity in disguise); `+6h` fails
to weaken the effect; BUY and SELL sides disagree in sign across the
promoted neighborhood; year sign is unstable; or the candidate primary
mean's block-bootstrap interval fails to exclude zero in the declared
direction at any of 1w/2w/4w. Any such failure is
`H05_REJECTED_SPECIFIC_CLAIM` for that sign — isolated cells, a fully
isolated `W`, single-direction results, or quote-imbalance-only results
remain `POSTHOC_UNTESTED` and cannot rescue it, per the post-hoc
quarantine list (design doc §24, revised).

## 20. Non-negotiable framing check

H05 is `REJECTED_SPECIFIC_CLAIM` unless a specific, preregistered,
symmetric, price-controlled, matched-random-controlled,
neighborhood-robust signed effect survives — not merely "large taker-buy
periods occur before positive returns," which is explicitly named in the
task as a trivial, uninformative restatement of contemporaneous momentum
this design is built to rule out as sufficient evidence.

---

## Findings not adopted

No additional `BLOCKER` findings were identified in the original pass
beyond item 4 (closed then) or in the addendum pass beyond items 4b, 5/6,
8, 11, 12 above (all closed in this revision, none by inspecting real H05
outcomes). Sections not listed with an issue (decision grid, horizon
ladder, normalization, MPIE/`CONTROL_DELTA_MIN` reuse, negative control
semantics, verdict vocabulary, year-stability rule) were reviewed and
found consistent with established batch convention and free of the
failure modes solicited by this review, in both the original and addendum
passes.

One alternative considered in the addendum pass and **not** adopted: using
a third `FLAT` category for exact-zero `SIGNED_PRICE_RET_W` instead of
folding it into `OPPOSED`. Rejected to keep `price_alignment` binary
(avoiding a sixth-level stratification dimension) and because `OPPOSED`
is the more conservative, symmetric choice pre-outcome (design doc §9).
