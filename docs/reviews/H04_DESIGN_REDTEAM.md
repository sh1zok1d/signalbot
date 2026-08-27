# H04 Trend Pullback → Continuation — Pre-Outcome Design Red-Team

**Status:** DESIGN REVIEW ONLY. Not a preregistration. Not an implementation.
**Reviewed proposal:** the H04 design as specified in the task prompt (trend
lookback ladder, established-trend threshold, pullback-depth construction,
structural/negative controls, search surface, gates, verdicts).
**Output:** `docs/research/H04_DESIGN_FROZEN_DRAFT.md` contains the complete
corrected design produced by this review. No H04 code was written. No H04
market outcomes were computed. 2025/2026 were not inspected.

This document classifies every reviewed design decision as `BLOCKER`,
`MAJOR`, `MINOR`, or `NO ISSUE`. For every `BLOCKER`/`MAJOR` finding: exact
section, failure mode, FP-or-FN risk, concrete example, and the narrow
remediation actually adopted in the frozen draft.

---

## Summary table

| # | Section | Classification | One-line issue |
|---|---|---|---|
| 1 | Temporal decomposition | MINOR | shared pivot bar `close(T-P)` couples trend-leg and pullback-leg noise |
| 2 | Trend lookback ladder `L` | NO ISSUE | doubling 4h/8h/16h family is a reasonable, batch-consistent scale ladder |
| 3 | Established-trend threshold `q=0.80` | MINOR | single fixed q is not robustness-checked against neighbors; must be disclosed, not hidden |
| 4 | Pullback-depth ratio construction | MAJOR | fixed `P=60m` numerator against an `L`-scaled denominator means "pullback" is a different fraction of trend duration at each `L` |
| 5 | **Primary depth thresholds (nested)** | **BLOCKER** | nested `d <= DEPTH < 1.0` makes "coherent d neighborhood" mechanically close to guaranteed, not a real robustness signal |
| 6 | Refractory (60m) | MINOR | 60m does not establish statistical independence across a multi-hour pullback episode |
| 7 | **Structural control (mirror extension)** | **BLOCKER** | same-direction extension is itself plausibly mean-reversion-prone, which would make pullback look artificially good for a reason unrelated to pullback |
| 8 | Matched-random baseline | MINOR | must proactively avoid the exact panel-index-vs-position bug found in H03 |
| 9 | Calendar residual diagnostic | NO ISSUE | design already requires real timestamps and a regression test; directly responsive to the H03 TVD erratum |
| 10 | Negative control (+6h) | NO ISSUE | inherited, already validated in H03, no H04-specific complication found |
| 11 | MPIE / CONTROL_DELTA_MIN reuse | NO ISSUE | reusing frozen Batch01 anchors, unchanged, is the *safer* choice, not an adaptivity risk |
| 12 | Dependence / uncertainty | MINOR | must require the week-block bootstrap to actually be wired into cell output, unlike H03's implementation gap |
| 13 | Direction symmetry | NO ISSUE | claim is genuinely symmetric; requiring both sides is correct |
| 14 | Global adaptivity (mechanism) | NO ISSUE | mechanism class verified pre-dating H01-H03 in `RESEARCH_ROADMAP.md` |
| 15 | Global adaptivity (numeric choices) | disclosed as **PARTIAL** | `q=0.80`'s looseness plausibly reflects batch-learned caution from H03's fragile tight-tail cells |

Two `BLOCKER` findings were corrected inside this same design pass (per
task instruction: "choose exactly one corrected ladder/construction NOW").
The frozen draft reflects the corrected constructions, not the raw
proposal.

---

## 1. Temporal decomposition — MINOR

**Section:** proposed temporal decomposition, `[T-P-L, T-P)` / `[T-P, T)`.

**Failure mode:** the two intervals are disjoint (no bar return is counted
twice), so there is no double-counting bug. But the two legs share exactly
one boundary price, `close(T-P)`: it is the trend leg's endpoint and the
pullback leg's start. A single noisy/outlier bar exactly at `T-P` (a wick,
a thin-liquidity print) can simultaneously (a) inflate the measured
`TREND_RET_L` magnitude and (b) manufacture the *appearance* of a
"pullback" as price reverts away from that same noisy pivot — without any
real countertrend mechanism.

**FP risk:** yes — a spurious pivot-bar print can jointly produce
"strong trend" + "deep pullback" candidates that are pure single-bar noise,
not a real trend-then-retrace episode.

**Concrete example:** a single 15m bar at `T-P` prints a wick 0.3% away
from the surrounding price level purely from a thin order book; this
alone can push `TREND_PCTL_L` over `0.80` and simultaneously produce a
`PULLBACK_DEPTH` in the primary range as price "reverts" to the
surrounding level in the next 60 minutes.

**Why this is not a construction bug:** sharing the endpoint is inherent
to *any* "pullback measured from where the trend leg ended" definition
(the standard retracement/Fibonacci-pullback concept); there is no
simpler alternative construction that removes the shared pivot without
abandoning the concept of "pullback from the recent trend's own endpoint."

**Remediation (disclosure, not redesign):** the frozen draft (§6) states
this coupling explicitly as a known limitation and requires that
`close(T-P)` itself be a fully resolved, standard canonical close (no
special pivot-smoothing) — consistent with the project's existing
no-lookahead conventions — and notes that the structural control (finding
#7) and negative control partially absorb this risk since they are
constructed under the same pivot-sharing property.

---

## 2. Trend lookback ladder `L ∈ {240, 480, 960}` minutes — NO ISSUE

Doubling 4h/8h/16h mirrors the batch's established doubling convention
(H01: 30/60/120; H02: 60/120/240; H03: 15/30/60). The three scales are
meaningfully distinct (intraday vs. multi-session) without being
degenerate/redundant. `16h` paired with `H<=4h` outcomes is not itself a
flaw: the H04 claim is that a shallow give-back *within* an established
multi-hour trend resolves quickly once it ends, which is coherent with
testing short-to-medium horizons right after the pullback window closes,
not a claim that the 16h trend itself predicts something 4h later in
isolation. No replacement ladder is adopted.

---

## 3. Established-trend threshold `q = 0.80` — MINOR

**Failure mode:** freezing a single `q` (rather than a 3-value family like
every other primary dial in this batch) means `q=0.80` cannot itself be
robustness-checked against neighbors the way `L`, depth, and `H` can.

**Why this is the right call anyway:** the H04 search budget is
explicitly allocated to `L × depth × H`; adding a `q` family would blow
the surface to 135 cells and would also conflate two different question
types — "how established must the trend be" (a gate) versus "how severe
is the specific dial under test" (the thing whose neighborhood must be
checked). `q=0.80` (top quintile) is also economically appropriate for
identifying a broad *state* ("in an established trend"), as opposed to
H01/H03's rare-tail *event* percentiles (0.90/0.95/0.98) — established
trends are not rare bursts.

**Remediation:** frozen draft explicitly discloses that `q=0.80` is a
single a-priori gate, not a robustness-tested family, and states this as
a real, acknowledged limitation on the trend-establishment definition
rather than omitting it. No q-family is added.

---

## 4. Pullback-depth ratio construction — MAJOR

**Section:** `PULLBACK_DEPTH(T) = -SIGNED_PB_RET(T) / abs(TREND_RET_L(T))`.

**Is the ratio itself sensible?** Yes — this is the standard
scale-invariant retracement-ratio concept (compare directly to Fibonacci
retracement percentages), and `depth < 1.0` is a legitimate, principled
boundary ("the pullback has not fully erased the trend leg").

**Failure mode actually found:** the pullback *observation window* `P` is
fixed at 60 minutes regardless of `L`. As a fraction of the trend leg's
own duration, `P/L` ranges from 25% (`L=240`) down to 6.25% (`L=960`) — a
4x spread. The *same* nominal depth band (e.g. `[0.25,0.40)`) therefore
describes a materially different economic event at each `L`: at `L=240` it
is a comparatively slow, quarter-of-the-trend-duration give-back; at
`L=960` it is a fast, small-fraction-of-duration snap. "Coherence across
`L`" is not automatically comparing the same phenomenon at different
scales.

**FP/FN risk:** both directions are possible. A real but genuinely
`L`-scale-specific mechanism could be unfairly read as "incoherent" (FN)
if a reviewer expects scale-invariance the design does not actually
provide; conversely, an apparent multi-`L` "coherent" signal could be
partly an artifact of the varying `P/L` ratio rather than a single
robust mechanism (FP), if not disclosed.

**Concrete example:** `d=0.25` at `L=960` selects pullbacks that retraced
25% of a 16-hour move within just 1 hour (a comparatively sharp,
fast-moving retracement); `d=0.25` at `L=240` selects pullbacks that
retraced the same 25% of a 4-hour move over the same 1 hour (a
comparatively slower, larger-fraction-of-duration retracement). These are
not obviously the same "shape" of pullback.

**Remediation:** keep the ratio construction (no simpler alternative is
clearly superior), but the frozen draft (§13) makes the `P/L` inconsistency
an explicit, disclosed property of the design, and the parameter-robustness
language (§28) is amended to state this as the specific, named reason a
genuinely scale-specific (single-`L`) result would be an expected and
acceptable outcome — not silently expected to generalize across `L` by
default. This is a disclosure fix, not a construction change, consistent
with "do not add complexity merely for rigor theater."

---

## 5. Primary depth thresholds (nested) — BLOCKER

**Section:** proposed candidate rule `TREND_PCTL_L >= 0.80 AND
SIGNED_PB_RET < 0 AND d <= PULLBACK_DEPTH < 1.0` for `d ∈ {0.10, 0.25,
0.40}`.

**Failure mode:** this is a *nested* threshold family — the `d=0.10` cell
is a strict superset of the `d=0.25` cell, which is a strict superset of
the `d=0.40` cell. Any single strong effect concentrated in the deepest
band (`d=0.40`) mechanically contaminates the `d=0.10` and `d=0.25` cells'
averages too, because the `d=0.40` candidates are literally *members* of
those cells. "Neighboring `d` behave similarly" is therefore not
independent confirmation across disjoint sub-populations — it is, in
part, a population-containment artifact.

**Why this is worse for H04 specifically than the batch's existing nested
q/s families:** in H01 (compression `q`) and H03 (impulse-severity `q`),
the hypothesis is an explicit monotonic dose-response ("more extreme →
stronger effect if real"), so nested "at least this severe" thresholds are
the *correct* way to test a monotonic tail relationship, and neighboring
agreement is genuinely informative under that framing. H04's depth
dimension has no equivalent a-priori monotonic direction: a very deep
pullback (`d=0.40`, close to fully erasing the trend) is at least as
plausibly a sign of trend *exhaustion* as of a "healthy" continuation-
friendly retracement. Because the hypothesized direction of the
depth-response is not fixed a priori, nested containment across depth
creates a materially higher risk that an isolated deep-band effect gets
laundered into an apparent "coherent neighborhood" across all three cells.

**FP risk:** requirement #5 of the candidate-for-freeze list ("depth
construction shows coherent neighborhood rather than one threshold
accident") would be close to mechanically satisfied whenever *any* one
band is strong, defeating the purpose of the gate.

**Concrete example:** suppose only very deep pullbacks (`depth` in
`[0.40, 0.60)`) show a genuine continuation effect and everything shallower
is pure noise. Under nesting, the `d=0.10` and `d=0.25` cells both include
those same deep-band candidates, so their means are pulled toward the same
positive effect, and the surface would misleadingly read as "coherent
across `d=0.10/0.25/0.40`" when only one narrow band actually carries the
mechanism.

**Remediation adopted now (per task instruction — no menu, exactly one
corrected construction):** replace the nested lower-bound rule with
**three mutually exclusive depth bands**, matching the same threshold
values as edges rather than floors:

```
shallow:  0.10 <= PULLBACK_DEPTH < 0.25
moderate: 0.25 <= PULLBACK_DEPTH < 0.40
deep:     0.40 <= PULLBACK_DEPTH < 1.00
```

No candidate can belong to more than one primary depth cell. "Coherent
sign across depth bands" is now a genuine robustness signal (three
disjoint populations agreeing), not a containment artifact. This aligns
the primary construction with the *already-exclusive* fixed diagnostic
bands (`[0,0.10), [0.10,0.25), [0.25,0.40), [0.40,0.60), [0.60,1.00)`),
which is a minimal, non-redundant, low-complexity fix — the fine 5-bin
diagnostic remains purely descriptive and unchanged; the coarse 3-band
partition becomes the frozen primary search dimension. Search surface
size is unchanged (`3 L × 3 depth bands × 5 H = 45`).

---

## 6. Refractory (60 minutes) — MINOR

**Failure mode:** 60 minutes does not establish statistical independence
across a multi-hour trend/pullback episode. Because `TREND_PCTL_L>=0.80`
states can persist for hours, and pullback depth can oscillate in and out
of a band as price chops during the retracement, multiple candidates more
than 60 minutes apart can still all describe the *same* underlying
macro-episode, inflating apparent `N` without adding independent evidence.

**Why 60m is still the right frozen choice:** it is principled (equals the
pullback observation window `P`, an internally-consistent, non-outcome-
derived rationale — not selected because H03 happened to show a favorable
result at 60m), and matches the batch's already-validated refractory
mechanics from H03 (earliest-keep, either-direction suppression).

**Remediation:** frozen draft explicitly states "60m refractory does not
establish independence from a multi-hour pullback episode" and points to
the *already-required* dependence/concentration reporting, the long-
dependence ACF diagnostic, and the UTC-week block bootstrap as the actual
mechanisms for catching and disclosing this — not a change to the
refractory value itself.

---

## 7. Structural control (mirror extension) — BLOCKER

**Section:** proposed control — same established trend, but the `P` window
moves in the *same* direction as the trend ("extension"), matched on
month/direction/trend-strength bin.

**Failure mode:** short-horizon "overextended" price states are
independently plausible candidates for near-term mean reversion/pause —
a well-documented microstructure pattern, and indeed one that the R2
project's own H01/H03 development runs already touched on (compression/
impulse persistence questions). If the mirror-extension population is
itself systematically *depressed* on the future-continuation metric
because it is overextended (not because "extension" per se is a bad
setup), then `mean_pullback − mean_mirror_extension >= 0.05` could pass
purely because the control group is artificially weak — not because the
pullback carries genuine incremental continuation information. This is
the opposite of a control being "too similar to the candidate" (the usual
worry); here the control could be biased in a direction that makes the
candidate look artificially good.

**FP risk:** high, and specific to this control choice — it could let a
non-mechanism through the single most important gate in the design.

**Concrete example:** established uptrend, `P` window extends further up
(mirror-extension candidate); short-term mean-reversion pulls the next
60-240 minutes down relative to trailing scale, depressing
`mean_mirror_extension`. Meanwhile actual pullback candidates, having
already partially reverted, are not subject to the same "just extended,
due for a pause" dynamic. The resulting positive
`mean_pullback − mean_mirror_extension` reflects the asymmetry between
"just extended" and "already pulled back," not a genuine pullback-specific
continuation edge.

**Remediation adopted now (exactly one corrected control, no menu):**
**trend-only baseline.** Use all `TREND_PCTL_L >= 0.80` qualifying moments
*irrespective of what the `P` window did* (any `SIGNED_PB_RET` — up, down,
or flat), matched on calendar month, trend direction, and the same
trend-strength bins (`[0.80,0.90)`, `[0.90,1.00]`), under the same
refractory and future-outcome semantics, **explicitly excluding the exact
raw pullback-candidate timestamps from the control pool** (membership
exclusion, matching the same "exclude exact treated timestamps, not
surrounding regime" principle already used for the matched-random
baseline). This directly operationalizes the design's own stated
requirement — "isolate the incremental value of pullback beyond being in
an established trend" — without introducing a second conditioning
direction (extension) that carries its own independent confound. No
`EXTENSION_RATIO` construct is needed under this control and is dropped
from the frozen draft.

---

## 8. Matched-random baseline — MINOR (implementation carry-forward)

The proposed construction (100 replicates, seed `20260902`, without
replacement, exclude raw qualifying candidates from the pool, preserve
month/direction composition) is sound and mirrors H03's design. H03's own
post-freeze audit found a real bug in this exact family of code
(`build_matched_random_pool` fancy-indexing panel ids into `len(elig)`
instead of using membership exclusion) that IndexError'd on real,
non-contiguous panel indices. This is a MINOR finding only because it is
an implementation-carry-forward requirement, not a new design flaw: the
frozen draft's implementation notes (§31) explicitly require membership-
based (`np.isin`-equivalent) pool exclusion from the start, plus a
synthetic regression test using non-contiguous panel ids mirroring H03's
`test_16c`, before any real H04 data is touched.

---

## 9. Calendar residual diagnostic — NO ISSUE

The proposed design already explicitly requires real event/matched
timestamps (never panel ids) for DOW/DOM keys, and already requires a
synthetic timestamp-vs-panel-id regression test. This is a direct,
correct response to the H03 post-freeze audit's TVD erratum
(`docs/reviews/H03_POSTFREEZE_RESULT_AUDIT.md` §4) and needs no further
correction here — carried into the frozen draft unchanged.

---

## 10. Negative control (+6h circular shift) — NO ISSUE

Inherited, unmodified convention, already implemented and exercised
successfully in H03 (collision-fraction reporting, no post-hoc removal,
disclosed diurnal-confound limitation). No H04-specific complication was
found that would make this control inappropriate or require a different
shift value. Kept as-is.

---

## 11. MPIE (0.10) / CONTROL_DELTA_MIN (0.05) reuse — NO ISSUE

These were frozen for H03 *before* H03's own outcomes were computed
(R2_SCREENING_PROTOCOL_V1.md §8 requires MPIE from H03 onward, anchored
independent of the candidate's own development-sample effect). Reusing
the identical numbers, unchanged, for H04 is the methodologically safer
choice: it satisfies the "anchored independent of this candidate's own
sample" requirement even more strongly than a fresh derivation would,
since the number was never conditioned on H04 at all. Inventing a new
MPIE specifically calibrated for H04 would introduce more, not less,
adaptivity risk. No change adopted.

---

## 12. Dependence / uncertainty — MINOR (implementation carry-forward)

H03's post-freeze audit found that the week-block bootstrap (seed,
replicates) existed in the library but was never wired into per-cell
output (`H03_POSTFREEZE_RESULT_AUDIT.md` §"Dependence": "NOT EMITTED by
the frozen runner"). This is a design-adjacent implementation gap, not a
design flaw, and is called out explicitly in the frozen draft's
implementation notes (§31) as a requirement: per-cell week-block bootstrap
output must be wired end-to-end before any real H04 development run.

---

## 13. Direction symmetry — NO ISSUE

The H04 research question is phrased without directional favoritism
("does subsequent price movement tend to continue in the original trend
direction" — applies equally to uptrends and downtrends). Requiring both
sides to independently support continuation before a symmetric
continuation claim is promoted is consistent with
`R2_SCREENING_PROTOCOL_V1.md` §11 and with the H03 precedent. No change.

---

## 14/15. Global adaptivity audit

**Mechanism class influence:** `docs/RESEARCH_ROADMAP.md` §R2 lists "trend
pullback -> continuation" as an initial hypothesis class, positioned
before "extreme impulse -> continuation versus exhaustion" in the same
original list, written before H01/H02/H03 were executed. Verified directly
against the current file. **Mechanism class was NOT influenced by
H01/H02/H03 outcomes.**

**Numeric-choice influence — declared PARTIAL, not hidden:**

- `P = 60m`: independently justified by an internal-consistency argument
  (equals its own observation window / matches the refractory length),
  not derived from any H03 outcome. Noted as a round-number/batch-style
  echo (60 minutes also appears as H03's refractory), but not judged to be
  outcome-adaptive.
- `L = {240, 480, 960}`: freshly derived for the trend-vs-outcome-horizon
  scale question; not copied from, or tuned to resemble, any prior
  family's numbers or observed effect. No influence found.
- `q = 0.80` (established-trend threshold): **declared PARTIAL
  influence.** Choosing a single, comparatively *loose* threshold — rather
  than a tighter single value, or a 3-value tail-severity family matching
  H01/H03's convention — plausibly reflects batch-internal learning from
  H03, whose tightest tail cells (`q=0.98`) produced small, isolated,
  fragile-looking populations (raw N as low as ~1,771–3,874) that did not
  form a coherent neighborhood. Preferring a broader, state-like
  established-trend definition for H04 is a reasonable design choice on
  its own economic merits (trends are states, not rare bursts, unlike
  H03's impulses) — but the specific preference for *looseness* is
  disclosed here as plausibly, partially shaped by the batch's accumulated
  experience with tight-tail fragility, per
  `R2_SCREENING_PROTOCOL_V1.md` §5's batch-internal design-adaptation
  disclosure requirement. This is disclosed, not hidden, and does not by
  itself block preregistration.
- `d = {0.10, 0.25, 0.40}`: the *count* (three values) is generic batch
  house style (true since H01, not H03-specific); the specific values are
  freshly derived for the retracement-ratio concept. No H03-specific
  influence found beyond the generic three-value convention.

**Overall: mechanism = NO influence; numeric choices = PARTIAL influence
(specifically the looseness of `q=0.80`), explicitly disclosed.**

---

## Findings not adopted

No additional `BLOCKER` or `MAJOR` findings were identified beyond the two
above. Sections not listed with an issue above (forward horizons, primary
outcome/normalization, primary metrics, reference-overlap disclosure,
dependence/concentration reporting, chronological stability, parameter
robustness language, candidate-for-freeze list items 1/2/4/6/7/8/9/11/12,
uncertainty/long-dependence diagnostic, verdict labels) were reviewed and
found consistent with established batch convention and free of the
failure modes solicited by this review (leakage, mathematical ratio
artifacts beyond #4, hidden control shopping beyond #7, undefined
discretion). They are carried into the frozen draft unchanged except where
candidate-for-freeze language needed updating to match the corrected depth
and structural-control constructions (§29 of the frozen draft).
