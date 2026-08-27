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

---

## Summary table

| # | Topic | Classification | One-line resolution |
|---|---|---|---|
| 1 | Sign alternatives (continuation vs reversal) | resolved, disclosed | both preregistered as competing interpretations of one signed statistic (mirrors H03), not a magnitude expansion of the 45-cell surface |
| 2 | Base-volume vs quote-volume imbalance | NO ISSUE | base-volume is primary; quote-volume is descriptive-only, cannot rescue |
| 3 | Extremeness family construction (nested vs exclusive) | resolved, explicit reasoning | NESTED thresholds (unlike H04's depth bands) — imbalance severity has a monotonic dose-response prior under both candidate signs |
| 4 | Structural control's "ordinary" population definition | **MAJOR gap, closed** | fixed `[0.60,0.80)` band, decoupled from the q-cell under test — the raw proposal left this ambiguous, which is exactly the kind of discretion that must be closed pre-outcome |
| 5 | Price-return confound stratification | resolved | `PRICE_RET_W` magnitude, 2 coarse bins via the same trailing midrank machinery already used for imbalance |
| 6 | Activity/volume confound | resolved, one decision made | NOT a mandatory matching stratum (over-fragmentation risk); reported descriptively only |
| 7 | Refractory rule | resolved | either-direction suppression, keep earliest, 60m — matches H03/H04 precedent exactly, not re-derived |
| 8 | W (lookback) robustness | resolved | soft "no severe cross-W contradiction" check only, not a hard 2-of-3 gate |
| 9 | Search surface size | NO ISSUE | kept at 45 cells; sign multiplicity disclosed separately, not double-counted as cells |
| 10 | Whether the mechanism can collapse into price momentum | **disclosed limitation, not resolved** | the structural control is the best available pre-outcome mitigation; it cannot achieve perfect identification in an observational design |

No `BLOCKER` findings remain — the one `MAJOR` finding (item 4) is closed
within this same pass by fully specifying the structural control's
"ordinary" population, matching the batch's practice of closing design gaps
before preregistration rather than after.

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

**Matching/standardization:** candidate-weighted deterministic
standardization across exact overlap strata of (calendar month) ×
(direction `D`) × (price-return-strength bin — see Q5), restricted to
strata where both populations have observations, weighted by the
candidate's own stratum frequency — this is the H04 post-outcome-
correction lesson (`docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md`),
reused from the start this time rather than discovered as a bug. Control-
only strata get zero candidate weight; unmatched candidates are reported
(`matched_candidate_N`/`unmatched_candidate_N`/`unmatched_candidate_share`),
never silently dropped, and never rescued by an invented post-outcome
overlap threshold.

**Is the control "strong enough"?** It is the best available pre-outcome
observational design, not a perfect one — see Q4/Q17 for the honest limit
of what any structural control of this kind can achieve.

## 5. Should total activity/volume be controlled?

**Decision (one, pre-outcome): NOT a mandatory matching stratum.** Adding
a third stratifying dimension (activity bucket) on top of month × direction
× price-strength risks exactly the over-fragmentation the batch has
learned to avoid (H04's own structural control already uses three
dimensions; a fourth risks destroying overlap and inflating
`unmatched_candidate_share` for no principled reason). The rejected
alternative — matching on a trailing activity percentile of `TOTAL_W` — is
recorded here, not silently discarded: it is retained as a **descriptive-
only** diagnostic (report the trailing activity percentile of candidate
vs. control populations per cell) so a stark activity disparity remains
visible without gating promotion. If extreme imbalance systematically
co-occurs with unusually thin or unusually thick markets, that possible
confound is disclosed, not resolved by this design — an honest limitation,
not swept under the diagnostic.

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
among the five `H` values. `W` gets a **weaker, explicitly different**
requirement: "no severe cross-`W` contradiction" (no other `W` at the same
`q, H` clearing matched-random/structural in the *opposite* declared
sign) rather than a hard two-of-three agreement requirement. This
distinguishes `W` (a *scale* choice, like H04's `L`, where a genuinely
scale-specific real mechanism is an acceptable outcome) from `q` (a
*severity/dose-response* dial, where neighboring agreement is the
scientifically meaningful signal) and from `H` (an *outcome-timescale*
dial with the same established convention). Requiring hard `W`-agreement
would risk making a genuinely single-lookback-specific mechanism
definitionally unpromotable; requiring nothing at all on `W` would let a
lone contradicted `W` slip through unexamined. The chosen middle path
matches the task's own explicit phrasing ("no severe contradiction," not
"must agree") for `W` specifically.

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

Aggressive-taker-flow windows are not randomly distributed across market
conditions; they may cluster in specific volatility/liquidity regimes
(e.g., thin-liquidity hours) that have their own generic subsequent-return
tendencies unrelated to imbalance per se. If that regime effect survives
into both the matched-random baseline and the price-matched structural
control (because neither explicitly matches on the activity/liquidity
regime — see Q5), a real regime effect could masquerade as an "imbalance"
effect. This is the central reason the activity-diagnostic (descriptive
only, not gating) is retained rather than dropped entirely, and the reason
this risk is disclosed rather than claimed to be fully resolved.

## 17. What is the strongest plausible false-negative story?

The price-matched structural control, by design, removes variation that
correlates with contemporaneous `PRICE_RET_W`. Since aggressive imbalance
and contemporaneous price movement are mechanically linked in a liquid,
continuously-arbitraged market (large aggressive orders directly walk the
book), a *real* imbalance-specific information effect that is partly
transmitted *through* the very price move it also causes could be
partially netted out by the structural standardization, biasing the
apparent incremental effect toward zero. This is an inherent tension in
any design built to isolate "beyond contemporaneous momentum" — the
control cannot be made stronger without directly attenuating a real
information channel that operates partly through price itself.

## 18. What exact evidence would justify CANDIDATE_FOR_FREEZE?

All fourteen criteria in the frozen candidate-requirements checklist (see
design doc §"Candidate-for-freeze requirements"), for one declared sign:
correct primary sign; MPIE cleared in a broad two-adjacent-`q` neighbor-
hood; the price-matched structural standardized delta clears
`CONTROL_DELTA_MIN`; the `+6h` negative control clears
`CONTROL_DELTA_MIN`; two adjacent `H` support the sign; no severe `W`
contradiction; ≥4/5 development years; both `D=+1` and `D=-1` support the
same sign; no single month/episode dominates; dependence-aware bootstrap
(including 1w/2w/4w) compatible with a real effect; adequate structural
overlap (low unmatched-candidate share, not an invented pass/fail number
but visibly adequate); and the primary close-return outcome itself (not a
secondary statistic) carries the effect.

## 19. What exact result would make us kill H05 without rescue?

Any material, non-isolated failure among: no sign is stable across a
two-adjacent-`q`/two-adjacent-`H` neighborhood for either declared sign;
the price-matched structural delta fails `CONTROL_DELTA_MIN` for whichever
cells otherwise looked attractive (indicating the apparent effect is
substantially contemporaneous momentum in disguise); `+6h` fails to
weaken the effect; BUY and DOWN sides disagree in sign across the
promoted neighborhood; year sign is unstable. Any such failure is
`H05_REJECTED_SPECIFIC_CLAIM` for that sign — isolated cells, single-`W`
results, single-direction results, or quote-imbalance-only results remain
`POSTHOC_UNTESTED` and cannot rescue it, per the post-hoc quarantine list.

## 20. Non-negotiable framing check

H05 is `REJECTED_SPECIFIC_CLAIM` unless a specific, preregistered,
symmetric, price-controlled, matched-random-controlled,
neighborhood-robust signed effect survives — not merely "large taker-buy
periods occur before positive returns," which is explicitly named in the
task as a trivial, uninformative restatement of contemporaneous momentum
this design is built to rule out as sufficient evidence.

---

## Findings not adopted

No additional `BLOCKER` or `MAJOR` findings were identified beyond item 4
above (already closed). Sections not listed with an issue (decision grid,
horizon ladder, normalization, MPIE/`CONTROL_DELTA_MIN` reuse, negative
control semantics, verdict vocabulary, year-stability rule, long-
dependence diagnostic) were reviewed and found consistent with established
batch convention and free of the failure modes solicited by this review.
