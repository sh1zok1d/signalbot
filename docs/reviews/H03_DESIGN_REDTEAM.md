# H03 Design Red-Team — Extreme Impulse → Continuation vs Exhaustion

**Round 2** — re-review of an expanded design proposal (primary/secondary
metrics, matched-random detail, decile diagnostic, dependence/effective
-sample reporting, explicit verdict vocabulary added since round 1) and
updated context: H01/H02 discovery history is now remotely durable.

**Scope:** pre-outcome design review only. No H03 run, no market outcomes
computed, no 2025/2026 data inspected, no development started.
**Repo:** `sh1zok1d/signalbot`
**Canonical methodology reviewed against:** `research/r2-screening-protocol-v1` @ `6c729b1b605ed3f8d078ce64d40154b9083076a2`
**Accepted dataset snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` (verified present, `ACCEPTED_FOR_DISCOVERY`, `research_authorized: true`, `confirmatory_authorized: false` — unchanged by this review)
**H01/H02 remote durability (new since round 1):** confirmed intact —
`research/h01-compression-expansion-discovery` @
`9a7ae2f93e9765b37262713359d39fc3ef3930b9` (draft PR #77, open, unmerged)
and `research/h02-failed-breakout-mean-reversion-discovery` @
`dd0898811a30e412de182dbf094c96647e7d175d` (draft PR #78, open, unmerged,
based on H01). This resolves the "remote durability" precondition round 1's
verdict was conditioned on.
**Docs read completely before forming judgment:** `docs/R2_SCREENING_PROTOCOL_V1.md`, `docs/EDGE_RESEARCH_PROTOCOL.md`, `docs/RESEARCH_ROADMAP.md`, `docs/reviews/R2_SCREENING_PROTOCOL_V1_REDTEAM.md`, `docs/reviews/R2_SCREENING_PROTOCOL_V1_MAINTAINER_ADDENDUM.md`, `docs/manifests/CORE_BTC_BINANCE_V0.yaml`

---

## H01/H02 independence assessment (required before anything else)

**H03's mechanism class is not reactive to H01/H02.** "Extreme impulse →
continuation versus exhaustion" is already named as one of the original R2
mechanism candidates in `docs/RESEARCH_ROADMAP.md` (§R2, written before
H01/H02 were executed), alongside compression→expansion (H01) and
failed-breakout→mean-reversion (H02). Choosing to test it next is not a
reactive pivot invented after H01/H02 failed.

**The proposed design still does not fully complete the disclosure the
canonical protocol requires, though the precondition for completing it
honestly is now met.** `docs/R2_SCREENING_PROTOCOL_V1.md` §5 (as corrected
by the maintainer addendum) requires design-influence to be declared before
development results are opened. The design brief does not state whether
specific numeric choices (60m refractory, the 15/30/60/120/240m horizon
ladder, the q90/95/98 ladder) were carried over from H01/H02's actual
implementation conventions versus derived independently for H03. Round 1
could not verify this at all, since H01/H02 existed only as an
unpreserved local history at that time. **That has changed:** H01/H02 are
now pushed to GitHub with exact SHAs preserved (PRs #77/#78), so this
question is now concretely answerable by inspecting those artifacts —
inspecting them is still outside this design-review's own scope (a
pre-outcome *design* review, not an implementation audit of prior closed
hypotheses), so the disclosure remains a required, not-yet-filled gap
(**Finding M1**, unchanged from round 1) — but it is no longer a gap that
*cannot* be filled; it is one that has not yet been filled.

I am not asserting H03 is fully independent, and I am not asserting it is
not. **The honest position, unchanged from round 1: independence of the
mechanism class is supported by the roadmap precedent; independence of the
specific numeric design choices is undeclared and must be stated
affirmatively — now against real, remotely-durable H01/H02 artifacts —
before development opens.** The frozen draft states this plainly rather
than asserting either extreme.

---

## Findings

### BLOCKER

None. Unchanged from round 1: the proposed design correctly incorporates
every major canonical-protocol correction that post-dates the original R2
freeze (see "Confirmed sound" below) and contains no defect that would make
H03, as scoped, an unfair test in either direction. All findings below are
fixable by disclosure or a narrow numerical/interpretive safeguard, not a
redesign.

### MAJOR

**M1 — Missing mandatory Global-Adaptivity/design-influence disclosure (§5). Unchanged from round 1, now concretely completable.**
- **Failure mode:** the design brief never states whether H03's specific
  parameter choices were influenced by H01/H02's execution or post-hoc
  findings, nor whether alternative control formulations were considered
  and discarded before settling on the ones proposed.
- **Risk:** false positive (an adaptively-shaped design smuggled in as if
  independent) — the exact failure mode §5 exists to close.
- **Concrete example:** if H03's 60-minute refractory or
  15/30/60/120/240m horizon ladder happens to numerically match a
  convention established during H01/H02's implementation, a future reader
  has no way to tell whether that's coincidental convention-reuse or
  convention-reuse it should discount as non-independent, because nothing
  was declared either way.
- **What changed since round 1:** H01/H02's implementation history is now
  remotely durable (PRs #77/#78), so the disclosure this finding requires
  can now be written against real artifacts rather than only in the
  abstract.
- **Remediation:** the frozen draft's §0 states plainly what is and is not
  known, and requires the actual preregistration to complete the
  declaration with specifics, citing PRs #77/#78, before development opens.

**M2 — Rolling reference-window statistics lack an effective-sample-size disclosure (Extremeness / Structural Control / Normalization / Decile Diagnostic). Unchanged in substance from round 1; scope explicitly extended to the new decile-diagnostic section.**
- **Failure mode:** `P_W(T)` (the extremeness percentile), the
  moderate-impulse control band, the normalization scale
  `PAST_MEDIAN_ABS_RET_H(T)`, and now also the new fixed percentile-bin
  decile diagnostic, are all computed from a 30-calendar-day trailing
  reference window sampled every 15 minutes. For `W = 60m` stepped every 15
  minutes, each window shares 45 of 60 minutes with its neighbor. The
  *nominal* observation count (~2,880 over 30 days) materially overstates
  the *effective* (non-overlapping) sample size feeding a tail-percentile
  estimate — most severely for `q98` at `W = 60m`, where the effective
  count of genuinely non-overlapping 60-minute windows in 30 days is
  roughly 720, and the number of those actually exceeding a 98th-percentile
  cut is on the order of a few dozen.
- **Not the same concern as the new "Dependence / Effective Sample"
  section:** that section (candidate-event concentration: unique
  days/weeks/months, largest-month share, median event spacing) reports
  clustering of the *qualifying events themselves*, which is a genuinely
  different and already well-designed disclosure (directly matches
  `docs/EDGE_RESEARCH_PROTOCOL.md` §9). It does not address the
  reference-window overlap this finding is about, so it does not close
  M2 — both disclosures are needed, and neither substitutes for the other.
- **Risk:** both directions. A noisily-estimated tail threshold can
  spuriously loosen (false positive: ordinary moves cross an artificially
  low threshold in some 30-day windows) or spuriously tighten (false
  negative: a genuine extreme fails to qualify because the trailing window
  was itself unusually volatile).
- **Concrete example:** a 30-day window dominated by one clustered
  volatility episode (common in BTC) can shift the estimated `q98` cutoff
  for `W=60m` up or down by a large relative amount from one month to the
  next, purely from estimation noise, before any real regime change has
  occurred.
- **Remediation (bounded, no new tunable parameter):** require every
  rolling percentile/median statistic used by the design (extremeness
  thresholds, moderate-control band, normalization scale, and decile bins)
  to report a fixed, non-selectable effective-N alongside its nominal N —
  `floor(reference_window_days × 24 × 60 / W_or_H_minutes)`. Cells whose
  effective-N for `q98` falls below a fixed, predeclared adequacy floor
  (200 non-overlapping observations) must be flagged for caution.
- **Partial mitigation already present:** candidate requirement #5
  (coherent sign/plateau across `q90→q95→q98`) provides some protection —
  correlated estimation error across thresholds sharing the same
  reference-window methodology could still produce a spuriously coherent
  plateau, so this reduces but does not eliminate the risk.

**M3 — No floor on the normalization denominator `PAST_MEDIAN_ABS_RET_H(T)`. Unchanged from round 1.**
- **Failure mode:** dividing by a rolling 30-day trailing median absolute
  return with no floor risks numerical blow-up during unusually quiet
  historical stretches (BTC has had genuine multi-week low-volatility
  periods).
- **Risk:** false positive. A handful of near-zero-denominator
  observations can produce enormous `NORM_CONT_RET_H` values that dominate
  a mean-based effect-size estimate, and now also distort the §15 MFE/MAE
  normalization, which uses the same denominator.
- **Concrete example:** during a historically quiet multi-week BTC
  stretch, `PAST_MEDIAN_ABS_RET_H(T)` for `H=240m` could be small enough
  that a single subsequent ordinary move produces a normalized outcome an
  order of magnitude larger than any other observation in the sample.
- **Remediation (bounded, predeclared, outcome-independent):** floor
  `PAST_MEDIAN_ABS_RET_H(T)` at the corresponding statistic's own 5th
  percentile computed over the full development window (pre-T data only)
  before it is used as any denominator — including for MFE/MAE
  normalization in §15.

### MINOR

**m1 — Decision boundary `T` should be explicitly defined as `bar_end_exclusive`.** Unchanged from round 1. **Fix applied** (§2 of the frozen draft).

**m2 — "Where possible" matching is a silent-failure hedge for the structural control.** Unchanged from round 1. **Fix applied** (§10).

**m3 — The `+6h` circular-shift negative control mildly confounds with diurnal/session timing.** Unchanged from round 1; still matches E1-RUN-001 precedent, still not materially flawed enough to warrant replacement. **Disclosed, kept as-is** (§12).

**m4 — Matched-random seed single-use discipline should be explicit.** Unchanged from round 1. **Fix applied** (§11).

**m5 — No statement on whether alternative control formulations were considered/discarded.** Unchanged from round 1. **Fix applied** (§0, §10, §12).

**m6 — (new in round 2) The matched-random baseline's residual-regime-imbalance question is asked but not given a concrete answer.** The proposed design explicitly asks to "audit... possible residual regime imbalance" for month+direction-only matching. Month-level matching is a reasonable, standard granularity for a screening-stage gate (matching the project's own conventions elsewhere), and the deeper concern — real extreme events preferentially clustering in locally volatile sub-periods while unconstrained random draws do not — is not actually a flaw: it is the intended, complementary contrast between the loose matched-random baseline (tier 1) and the tighter moderate-momentum structural control (tier 2, §10), which exists precisely to isolate "extremeness" from "being in a volatile neighborhood." **Fix applied (descriptive only, no new selectable baseline):** added a fixed day-of-month/day-of-week distribution comparison between real events and matched draws, so a reviewer can visually confirm no gross residual clustering imbalance beyond month/direction matching (§11).

**m7 — (new in round 2) Candidate requirement #6 ("at least two adjacent horizons support the same sign") is ambiguous as to which metric it applies to.** MFE/MAE (§15) are running-extremum statistics that are mechanically non-decreasing/monotonic as the horizon window extends, so they would trivially "cohere" across adjacent horizons by construction, regardless of any real market mechanism — making them unsuitable for a coherence-across-horizons robustness check. Requirement #12 already separately states "primary outcome, not only MFE/MAE, supports mechanism," implying #6 was intended to apply to the primary metric, but this was not stated explicitly. **Fix applied:** requirement #6 in the frozen draft (§22) now states explicitly that it is evaluated on `CONT_RET_H`/`NORM_CONT_RET_H`, not MFE/MAE.

### NO ISSUE (explicitly checked, found sound)

Everything confirmed sound in round 1 remains sound and is carried forward
unchanged: H03 family framing (three-way falsifiable, non-strategy,
non-PnL); decision grid/no-lookahead discipline; the rolling local
percentile-rank extremeness construction itself (only the effective-N
*disclosure* was missing, not the construction); the fixed `q90/95/98`
threshold set (no threshold inflation); the refractory's correct scoping as
trigger-dedup only; the outcome-horizon boundary rule (still the strongest
part of the proposal — a verbatim, correct implementation of the
maintainer-adopted pool-boundary embargo); the fixed pre-outcome sign
convention; the normalization anchor's independence from candidate outcomes
(sound in principle, needs only the M3 floor); the MPIE magnitude (0.10)
and its outcome-independent anchoring; the structural control's choice
(moderate-momentum band, the simplest available isolator of "extremeness");
the matched-random control's basic construction (fixed seed, 100
replicates, correctly framed as not new market evidence); the 45-cell
search surface (matches H01/H02 precedent, no escalation); the
chronological-stability rule (correctly follows the maintainer's
no-shock-exclusion correction, correctly declines to make H03 regime
-specific per explicit task instruction); the UP/DOWN symmetry scope
(exact match to the canonical protocol's own worked H03 example); and the
candidate-for-freeze requirements list (a faithful, now-complete restatement
of the canonical protocol's §15, subject only to the m7 clarification).

**Newly reviewed in round 2, found sound:**

- **Primary metrics list** (§14) — `N`, mean/median `NORM_CONT_RET_H`,
  raw bps, `P(>0)`/`P(<0)`, 5th/25th/75th/95th percentiles, with explicit
  "no PnL, no Sharpe, no leverage" — correctly scoped for mechanism
  discovery, matches `docs/EDGE_RESEARCH_PROTOCOL.md` §8's "report the
  distribution, not just win rate" guidance.
- **Matched-random baseline's borrowed-direction-label construction** (§11)
  — assigning each matched draw the real candidate's own direction label
  is not a flaw; it is the correct, standard way to build a "matched random
  timing" control for a *signed* claim (`docs/EDGE_RESEARCH_PROTOCOL.md`
  §7), making the matched control's `CONT_RET_H` comparable in the same
  units as the real candidate's.
- **Decile diagnostic** (§16) — correctly forecloses becoming a new
  selectable threshold ("may not create new selectable q thresholds") and
  correctly routes an isolated attractive bin to `POSTHOC_UNTESTED` rather
  than letting it rescue H03. Well-designed; only the M2 effective-N
  disclosure needed to be explicitly extended to cover it.
- **Secondary path metrics / MFE-MAE** (§15) — the mechanical non
  -independence from the primary outcome (MFE/MAE are path statistics of
  the same price path) is real but already correctly guarded against by
  the explicit "secondary metrics cannot rescue a failed primary outcome"
  rule. `P(MFE_impulse > MAE_opposite)` is not mechanically biased away
  from 50% under a symmetric zero-drift null (MFE and MAE magnitudes share
  the same marginal distribution by reflection symmetry in that case), so
  it remains a meaningful diagnostic rather than a statistic that
  automatically favors continuation regardless of any real effect.
- **Dependence / effective-sample (candidate-event concentration)
  reporting** (§17) — comprehensive and well-designed, directly
  operationalizing `docs/EDGE_RESEARCH_PROTOCOL.md` §9's clustering
  /concentration requirements (unique days/weeks/months, month share,
  direction imbalance, event spacing). This is a genuinely different,
  complementary disclosure to M2, not a substitute for it (see M2 above).
- **Possible verdicts vocabulary** (§23) — correctly bifurcates
  `CANDIDATE_FOR_FREEZE` by sign (continuation vs. exhaustion) since H03
  uniquely allows either preregistered sign, correctly maps onto the
  canonical protocol's verdict semantics, and correctly forecloses opening
  validation or starting R3 optimization inside the development run.
- **Candidate requirement #11** (dependence diagnostic must not reveal an
  obviously misleading effective-N interpretation without explicit
  caution) — this is a new, welcome, self-imposed discipline that
  independently anticipates part of the concern raised in M2/M6 of round 1
  for the dependence diagnostic specifically; no change needed beyond
  confirming it's compatible with the round-1 dependence-diagnostic
  definition (refined slightly below).

---

## Final dependence diagnostic (refined in round 2 for explicit multi-month coverage)

The canonical protocol requires "a fixed, non-selectable
autocorrelation-decay or effective-sample-size diagnostic," described only
in the abstract; round 1 operationalized it concretely, and round 2's task
explicitly emphasizes it must be "capable of revealing multi-month
persistence" — so the lag set is extended:

**ACF-crossing dependence-half-life proxy.** On the full development
window (embargo-respecting), compute the **daily** series of total
absolute 15-minute log-returns (a realized-volatility-activity proxy,
computed independently of any candidate event or outcome). Compute its
autocorrelation function at the fixed, predeclared lag set
**{1, 2, 4, 8, 16, 32, 64} calendar days**. Report the diagnostic as **the
smallest lag in that set at which the ACF first falls below 0.2** (a fixed,
non-tuned threshold). If the ACF has not fallen below 0.2 by lag 64, report
the diagnostic as `>64 days`.

- Not a new selectable block length — a single reported number.
- A value at/beyond 16–32 days signals 1w/2w/4w block sensitivity may
  understate true persistence; a value reaching 64 days explicitly
  demonstrates multi-month dependence — either must be disclosed and
  flagged for qualitative caution, never gating promotion by itself.
- Fully reproducible and interpretable from the frozen dataset and this
  fixed formula alone; no "inspect ACF and decide" judgment call.

## Final control recommendation

Keep the structural control (moderate-momentum band) and negative control
(`+6h` circular shift) exactly as proposed. Add only: (a) the m3 disclosure
of the negative control's mild diurnal-confounding limitation, (b) the m5
disclosure that no alternative control formulations were tried and
discarded, and (c) the new m6 residual-imbalance descriptive diagnostic for
the matched-random baseline. No replacement control is warranted for
either.

---

## False-positive risks

Concentrated in M2 (noisy tail-percentile thresholds at `W=60m`/`q98`,
now also affecting the decile diagnostic) and M3 (normalization
denominator blow-up during quiet markets, now also affecting §15's MFE/MAE
normalization) — both could inflate an apparent effect through
estimation/numerical artifacts rather than a real conditional relationship.
M1 remains a structural false-positive vector (adaptively-shaped design
passed off as independent) until the disclosure is actually completed.

## False-negative risks

Concentrated in M2 — an unusually volatile trailing 30-day reference
window could push the extremeness threshold up enough to under-select
genuine extreme events in the following period. No other false-negative
risk was found in round 2's expanded sections: the new decile diagnostic,
secondary-path-metrics rule, and dependence/concentration reporting all
correctly preserve, rather than foreclose, a path for a real, narrow
mechanism to survive.

## Fixes

Applied (3 MAJOR carried forward + scope-extended, 7 MINOR: 5 carried
forward + 2 new) as the corrected design in
`docs/research/H03_DESIGN_FROZEN_DRAFT.md` — still a design draft, not a
preregistration.

- fix branch: `research/h03-design-redteam`
- fix SHA: `1bd4c1a97b245cc8f1538ba304243f5e7e283d66` (round 2, on top of round-1 base `6c729b1b605ed3f8d078ce64d40154b9083076a2`)
- fix PR: #76, draft, against `research/r2-screening-protocol-v1`, not merged

## Validation contamination

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- H03 real outcomes computed: **NO**

## Final verdict

**B — H03 DESIGN SOUND WITH FIXES — CORRECTED DESIGN READY TO PREREGISTER.**

No blocker was found in either round. The design correctly incorporates
every canonical-protocol correction that post-dates the original R2 freeze
(boundary embargo, MPIE anchoring, no-shock-exclusion, symmetry scoping),
and round 2's expanded sections (primary/secondary metrics, matched-random
detail, decile diagnostic, dependence/concentration reporting, explicit
verdict vocabulary) are all sound or now fixed. Three MAJOR findings
(adaptivity disclosure, reference-window effective-N disclosure, and
normalization floor — all carried forward from round 1 with scope
extended to the new sections) and seven MINOR findings (five carried
forward, two new) are fixed narrowly in the frozen draft. Unlike round 1,
this verdict is **not** conditioned on H01/H02 remote durability — that
precondition is now satisfied (PRs #77/#78). The remaining gap before an
actual preregistration commit is §0's honest numeric-convention disclosure,
which requires inspecting H01/H02's now-durable artifacts — a task for
whoever opens development, not this design review.
