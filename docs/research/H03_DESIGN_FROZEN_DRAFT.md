# H03 — Extreme Impulse → Continuation vs Exhaustion — Design Draft

**Status: DESIGN DRAFT — NOT A PREREGISTRATION.**

This document is the design-red-team-corrected version of the proposed H03
family, updated in round 2 to incorporate the expanded design proposal
(primary/secondary metrics, matched-random detail, decile diagnostic,
dependence/effective-sample reporting, explicit verdict vocabulary). It is
not yet a frozen preregistration under `docs/R2_SCREENING_PROTOCOL_V1.md`:
that requires this draft to be turned into an actual preregistration commit
at the moment development opens, with §0's remaining honest-disclosure gap
filled in with concrete specifics. No development has started, no market
outcomes have been computed, and 2025/2026 remain untouched.

**Governing protocol:** `docs/R2_SCREENING_PROTOCOL_V1.md` (as corrected by
`docs/reviews/R2_SCREENING_PROTOCOL_V1_MAINTAINER_ADDENDUM.md`) and
`docs/EDGE_RESEARCH_PROTOCOL.md`.
**Design red-team:** `docs/reviews/H03_DESIGN_REDTEAM.md` — read that report
for the full rationale behind every change from the originally proposed
design; only the corrected result is repeated here.
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.
**H01/H02 remote durability:** satisfied. `research/h01-compression-expansion-discovery`
@ `9a7ae2f93e9765b37262713359d39fc3ef3930b9` (draft PR #77) and
`research/h02-failed-breakout-mean-reversion-discovery` @
`dd0898811a30e412de182dbf094c96647e7d175d` (draft PR #78) are pushed to
GitHub, exact SHAs preserved, both open/unmerged.

---

## 0. Global adaptivity disclosure (required by §5 before development opens)

- H03 is the **third** of five R2 Batch 01 families. H01 (Compression →
  Expansion) and H02 (Failed Breakout → Mean Reversion) were previously
  attempted and closed `REJECTED_SPECIFIC_CLAIM`.
- H01 produced a post-hoc observation (low-volatility persistence),
  status `POSTHOC_UNTESTED`. H02 produced post-hoc observations (a small
  generic short-horizon boundary-breach bounce; failed breakout did not
  outperform a successful-breakout structural control), status
  `POSTHOC_UNTESTED`. Neither observation may rescue H01/H02 or seed H03
  directly.
- **Mechanism-class independence:** "extreme impulse → continuation versus
  exhaustion" is not a reactive pivot invented after H01/H02 failed — it is
  already named as one of the original R2 mechanism candidates in
  `docs/RESEARCH_ROADMAP.md` §R2, listed alongside H01 and H02 before either
  was executed.
- **Numeric-choice independence — honest, incomplete disclosure:** this
  design review cannot itself verify whether specific numeric choices below
  (60-minute refractory, the 15/30/60/120/240-minute horizon ladder, the
  q90/95/98 percentile ladder) were newly derived for H03 or carried over as
  house convention from H01/H02's actual implementation. H01/H02's history
  is now remotely durable (PRs #77/#78 above), so this question is
  concretely answerable by inspecting those artifacts — but doing so is
  outside this design-review's own scope (which does not open, run, or
  materially inspect prior discovery implementations beyond what is already
  stated in `docs/RESEARCH_LEDGER.md`/the task context). **This must be
  stated affirmatively, not left silent, before development opens.**
  Whoever writes the actual H03 preregistration must add a concrete
  statement here (e.g., "the 60-minute refractory matches H02's own
  refractory, chosen for cross-family convention consistency, not because
  of any H02 outcome" or the honest alternative if that is not the case),
  using PRs #77/#78 as the source of truth.
- **Control formulations considered:** exactly one structural control
  (moderate-momentum band) and one negative control (`+6h` circular shift)
  were considered for this design. No alternative formulation was tried and
  discarded. If that changes before preregistration, the discarded
  alternative(s) must be logged here, not silently dropped.
- **H03 is not independent confirmation.** It uses the same 2020–2024
  discovery lab as H01/H02 — repeated exploration of that lab is allowed for
  hypothesis generation/development, but this run can never be described as
  independent confirmation of anything.
- **Design changes caused by this red-team** (full rationale in
  `docs/reviews/H03_DESIGN_REDTEAM.md`):
  1. added this Global Adaptivity disclosure section (§0);
  2. added effective-sample-size disclosure for rolling percentile/median
     statistics — extremeness thresholds, the moderate-control band, the
     normalization scale, and the decile-diagnostic bins (§4, §19);
  3. added a floor on the normalization denominator (§8);
  4. made decision-boundary `T` an explicit `bar_end_exclusive` definition
     (§2);
  5. required disclosure of unmatched structural-control cases (§10);
  6. disclosed the negative control's diurnal-confounding limitation (§12);
  7. made the matched-random seed's single-use discipline explicit (§11);
  8. disclosed that no alternative control formulations were considered
     (§0, §10, §12);
  9. defined the exact, fixed dependence diagnostic the canonical protocol
     required in the abstract (§16);
  10. added a fixed, disclosure-only day-of-month/day-of-week comparison
      between real candidate events and matched-random draws (§11);
  11. clarified that candidate requirement #6 (adjacent-horizon coherence)
      applies to the primary `CONT_RET_H` metric, not to MFE/MAE, which are
      mechanically monotonic across nested horizons by construction (§17).
- **Search-surface ledger note:** H01 = 45 primary cells, H02 = 45 primary
  cells, H03 (this design) = 45 primary cells. H03 does not expand the
  per-family search surface relative to precedent.

---

## 1. Question (mechanism discovery, not a trading strategy)

After an unusually large short-horizon BTC directional move relative to its
recent local distribution, does subsequent price movement systematically:

- **A. continue** in the impulse direction,
- **B. exhaust/reverse** against the impulse direction, or
- **C.** show no practically meaningful robust conditional directional
  effect?

Both continuation and exhaustion are preregistered competing possibilities,
fixed before any real H03 outcome is inspected. This is mechanism
discovery. It is explicitly **not** a trading strategy, a PnL claim, a
liquidation hypothesis, a news classifier, a market-maker explanation, or a
product detector.

## 2. Decision grid

UTC-aligned 15-minute boundaries. Only fully available information at
decision time `T` may define an event; the still-forming bar is never used.
**`T` is defined as the `bar_end_exclusive` of the 15-minute bar ending at
`T`** (matching `docs/manifests/CORE_BTC_BINANCE_V0.yaml`'s
`canonical_available_at: bar_end_exclusive` /
`eligibility_rule: bar_end_exclusive <= decision_time` convention) — not the
bar's open, and not any later bar. *(fix)*

## 3. Impulse windows

`W ∈ {15m, 30m, 60m}`.

```
IMPULSE_RET_W(T) = ln(close(T) / close(T-W))
```

where all required closes are available by `T`. Direction: `+1` if
`IMPULSE_RET_W(T) > 0`, `-1` if `< 0`. Exact zero: excluded (a vacuous
safeguard in practice given continuous price data, kept for completeness).

## 4. Extremeness

```
ABS_IMPULSE_W(T) = abs(IMPULSE_RET_W(T))
```

Reference distribution: same `W`, same UTC 15-minute grid, preceding 30
calendar days, strictly before `T` (current `T` excluded; no future
observations; no full-dataset or year-wide percentile).

`P_W(T)` = empirical percentile rank of `ABS_IMPULSE_W(T)` within the
trailing 30-day reference distribution.

Candidate thresholds: `q ∈ {0.90, 0.95, 0.98}`. Extreme-impulse condition:
`P_W(T) >= q`. No thresholds are added after real outcomes are opened.

**Effective-sample-size disclosure (fix, required, not a new gate):**
for every `(W, q)` cell, report both:

- nominal reference-window observation count (~2,880 for a 30-day,
  15-minute grid), and
- **effective (non-overlapping) count**, computed as
  `floor(30 * 24 * 60 / W_minutes)` — 2,880 for `W=15m`, 1,440 for `W=30m`,
  720 for `W=60m`.

Any `(W, q)` cell whose effective count times `(1 − q)` (the expected
number of non-overlapping observations exceeding the threshold) falls below
**200** must be flagged for interpretive caution in the writeup. This is a
fixed, predeclared disclosure rule — it does not change which cells are
tested or add a new selectable threshold, and it applies identically to the
decile-diagnostic bins in §19.

## 5. Refractory

60 minutes. Within each `(W, q)` configuration: after accepting one
qualifying event at `T`, ignore further qualifying events of either
direction during `(T, T+60m)`; keep the earliest event only. Report raw
pre-refractory `N` and post-refractory `N` for every cell. The refractory
never changes after outcomes are opened.

The refractory deduplicates *trigger identification* only; it is not a
claim of outcome-level independence between events spaced further apart
than 60 minutes — that is handled entirely by the dependence-sensitivity
machinery in §16, not conflated here.

## 6. Forward horizons

`H ∈ {15m, 30m, 60m, 120m, 240m}`.

**Boundary rule (canonical, verbatim — already correct):** an observation
is eligible for horizon `H` only if the complete frozen future `H` path
resolves strictly before the current evidence pool's `end_exclusive`. For
development, that means `T + H` must resolve strictly before
`2025-01-01T00:00:00Z`. No horizon truncation. No future read across
evidence-pool boundaries. The identical rule applies at the `2025 → 2026`
boundary when validation/OOS phases are eventually opened. This is a
verbatim implementation of the maintainer-adopted boundary-embargo fix in
`docs/R2_SCREENING_PROTOCOL_V1.md` §1 ("exclude, do not truncate") — the
single strongest piece of evidence this design tracks the current canonical
protocol rather than an earlier or ad hoc understanding of it.

## 7. Primary outcome

```
RET_H(T)      = ln(close(T+H) / close(T))
CONT_RET_H(T) = impulse_direction(T) * RET_H(T)
```

`CONT_RET_H > 0` → continuation. `CONT_RET_H < 0` → exhaustion/reversal.
The sign convention is fixed here, before any outcome is inspected, and
must never be flipped after outcomes are opened.

## 8. Local normalization

```
PAST_MEDIAN_ABS_RET_H(T) = median of H-horizon absolute returns on the
    same UTC 15m grid, over the preceding 30 calendar days, using only
    observations fully resolved strictly before T. Current
    candidate/future outcome excluded.
```

**Floor (fix, required, fixed and outcome-independent):**
`PAST_MEDIAN_ABS_RET_H(T)` is floored at the corresponding statistic's own
5th percentile computed over the full development window using only data
available strictly before `T`. This prevents a division blow-up during
unusually quiet historical stretches from producing degenerate,
artificially enormous normalized outcomes — a fixed rule declared here,
before outcomes, not a parameter chosen after seeing results.

```
NORM_CONT_RET_H(T) = CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)   [floored]
```

If the trailing scale is unavailable even after flooring, the outcome is
ineligible. No future normalization; `PAST_MEDIAN_ABS_RET_H(T)` uses only
pre-T data, so it is independent of the candidate's own current or future
outcome — satisfying the canonical protocol's MPIE-anchoring requirement
(§8 of the canonical protocol).

## 9. MPIE (minimum practically interesting effect)

```
|candidate mean NORM_CONT_RET_H − matched-random mean NORM_CONT_RET_H| >= 0.10
```

for the preregistered candidate neighborhood. Interpretation: the
conditional signed directional effect must shift by at least 10% of the
local typical (trailing, pre-T) absolute `H`-horizon move. This anchor is
independent of the candidate's own development-sample result because the
normalization scale is a trailing, pre-T distributional statistic —
satisfying `docs/R2_SCREENING_PROTOCOL_V1.md` §8's maintainer-corrected
anchoring rule.

Also report the raw mean `CONT_RET_H` in bps, descriptively. Raw bps does
not replace the normalized MPIE and is not a profitability requirement.
Execution cost is explicitly **not** the primary MPIE anchor for this
mechanism-discovery experiment.

*Design-red-team assessment: 0.10 is a defensible, pre-anchored order of
magnitude — neither trivially small (which would make promotion easy to
game) nor implausibly large (which would kill real effects for no
principled reason). The anchor is genuinely independent of candidate
outcomes (§8's floor makes this robust even in quiet markets). No better
outcome-independent anchor without a new tunable parameter was identified.
No change proposed to the magnitude or construction.*

## 10. Structural control

Moderate-impulse population: `0.60 <= P_W(T) < 0.80`, same `W`, same
impulse-direction rule, same UTC grid, same 60-minute refractory.
Month- and direction-matched against extreme candidates where possible;
**any case where matching is not possible must be explicitly counted and
reported, not silently defaulted to an unmatched comparison** *(fix)*.
Compare extreme vs. moderate impulse under identical future-outcome
semantics using the same primary outcome.

This is the simplest available control that isolates "extremeness" as the
specific incremental ingredient while holding "directional momentum exists
at all" constant — it directly answers the design brief's own audit
question ("does extremeness add information beyond ordinary momentum?")
affirmatively as the appropriate structural control. No alternative
structural control was considered or discarded for this design *(disclosed
in §0)*.

## 11. Matched-random baseline

For each `(W, q)` configuration: sample the same number of eligible UTC
15-minute boundaries, preserving calendar-month candidate counts and
UP/DOWN candidate-direction composition. Assign each matched observation
the corresponding real candidate's direction label (this is the correct,
standard construction for a "matched random timing" negative/baseline
control on a *signed* claim per `docs/EDGE_RESEARCH_PROTOCOL.md` §7 — it is
not a flaw that the matched draw's own organic direction is discarded in
favor of the paired real event's label; that substitution is precisely what
makes the matched control's `CONT_RET_H` comparable in the same units as
the real candidate's).

Deterministic seed: `20260831`. **This seed is used exactly once and is
never re-rolled after any early inspection of results** *(fix)*. 100
replicates. Report candidate-minus-matched for mean `NORM_CONT_RET_H` and
continuation positive-share. Replicates estimate the control distribution
only; they are not independent market evidence.

**Residual-imbalance diagnostic (fix, required, descriptive only):**
report a fixed day-of-month and day-of-week distribution comparison between
real candidate events and the matched-random draws for each `(W, q)`
configuration, so a reviewer can visually confirm no gross residual
clustering imbalance remains beyond month/direction matching. This is
purely descriptive — it does not create an additional matched baseline to
choose between, and month-level matching itself is not changed.

## 12. Negative control

`+6` hour circular shift within the same UTC day, preserving the original
impulse direction. Do not redetect an impulse at the shifted `T`. Require
valid past/future coverage at the shifted `T`.

*Design-red-team disclosure (fix):* a quarter-day shift moves most control
observations into a different part of the UTC day, which may introduce
mild diurnal/session-timing differences rather than a perfectly pure "same
regime, different specific trigger" placebo. This matches the project's
own established convention (`docs/RESEARCH_LEDGER.md`, E1-RUN-001's "fixed
+6h same-day circular time-shift control") and is not materially flawed
enough to require a replacement. This limitation is recorded here as a
known, accepted scope limitation, not an unstated assumption. No
alternative negative control was considered or discarded for this design
*(disclosed in §0)*.

## 13. Search surface

`3 W × 3 q × 5 H = 45` primary cells. Decile relationships (§19) may be
reported diagnostically but must not create additional selectable
thresholds. This matches H01's and H02's own stated 45-cell search
surfaces — H03 does not expand the per-family search surface relative to
precedent. The eventual preregistration must state plainly that H03 is the
**third** tested mechanism family in R2 Batch 01, never written as if one
isolated cell were tested once.

## 14. Primary metrics

For every `W × q × H` cell, report:

- `N`;
- mean and median `NORM_CONT_RET_H`;
- mean raw `CONT_RET_H` in bps;
- `P(CONT_RET_H > 0)`, `P(CONT_RET_H < 0)`;
- 5th, 25th, 75th, 95th percentiles of `NORM_CONT_RET_H`.

No PnL, no Sharpe, no leverage — mechanism discovery only.

## 15. Secondary path metrics

For each `H`, additionally report:

- MFE in the impulse direction and MAE against the impulse direction over
  `[T, T+H]`, each normalized by the same (floored) trailing local scale
  `PAST_MEDIAN_ABS_RET_H(T)` available at `T`;
- `P(MFE_impulse > MAE_opposite)`.

Secondary metrics cannot rescue a failed primary close-return outcome.

*Design-red-team mechanical-overlap assessment:* MFE/MAE are, by
construction, path statistics of the same price path that produces the
primary close-return outcome, so they are not statistically independent of
it — this is expected and already correctly guarded against by the
"cannot rescue" rule above, not a defect. `P(MFE_impulse > MAE_opposite)`
is not mechanically biased away from 50% under a symmetric, zero-drift null
(by reflection symmetry, MFE and MAE magnitudes share the same marginal
distribution in that case), so it remains a meaningful diagnostic rather
than a statistic that trivially favors one side regardless of any real
effect.

## 16. Decile diagnostic

For each `W` and `H`, report fixed percentile bins `[0,10), [10,20), ...,
[90,100]` of `P_W(T)`: `N`, mean `NORM_CONT_RET_H`, `P(CONT_RET_H > 0)` per
bin. These bins are diagnostic only and may not create new selectable `q`
thresholds inside H03. A visually attractive isolated bin may only become
`POSTHOC_UNTESTED` for a later research batch, never a rescue for H03 in
this batch. The §4 effective-sample-size disclosure requirement applies
identically to each decile bin *(fix)*.

## 17. Dependence / effective sample (candidate-event concentration)

Report, per configuration: raw qualifying `N`; post-refractory `N`; unique
UTC days; unique UTC weeks; unique months; events by year; events by month;
largest-month share; top-5-month share; UP share; DOWN share; median event
spacing. This is distinct from, and complements, §4's reference-window
effective-N disclosure: §4 is about the statistical reliability of the
*rolling reference distribution* used to construct `P_W(T)` and the
normalization scale; this section is about *clustering/concentration of
the candidate events themselves* (a single volatility episode producing
many temporally clustered qualifying events, which the block-bootstrap and
chronological-stability checks below must be interpreted alongside). Both
disclosures are required; neither substitutes for the other.

## 18. Uncertainty

Primary: UTC-week block bootstrap. Fixed sensitivity for any proposed R3
survivor: 1-week, 2-week, and 4-week blocks — robustness checks, not
selectable alternatives. The conclusion must not depend on choosing the
block length that gives the narrowest favorable interval.

**Canonical non-selectable dependence diagnostic, defined exactly once
(design-red-team deliverable, refined in round 2 to explicitly reach into
multi-month territory):**

> **ACF-crossing dependence-half-life proxy.** On the full development
> window (embargo-respecting), compute the **daily** series of total
> absolute 15-minute log-returns (a realized-volatility-activity proxy,
> computed independently of any candidate event or outcome). Compute its
> autocorrelation function at the fixed, predeclared lag set
> `{1, 2, 4, 8, 16, 32, 64}` calendar days. Report the diagnostic as **the
> smallest lag in that set at which the ACF first falls below 0.2** (a
> fixed, non-tuned threshold). If the ACF has not fallen below 0.2 by lag
> 64, report the diagnostic as `>64 days`.

This is not a new selectable block length — it is a single reported
number. A value at or beyond 16–32 days is a direct signal that 1w/2w/4w
block sensitivity may understate true persistence; a value reaching 64
days explicitly demonstrates dependence extending into multi-month
territory. Either must be disclosed and flagged for qualitative caution in
any freeze writeup — it does not by itself gate promotion. Fully
reproducible and interpretable from the frozen dataset and this fixed
formula alone; no "inspect ACF and decide" judgment call.

## 19. Chronological stability

Report 2020, 2021, 2022, 2023, 2024 separately. For an unconditional H03
claim, the candidate neighborhood's required sign should normally hold in
at least 4 of 5 years; one year may be weaker/null; repeated sign
reversals block promotion.

**No named shock-year exclusions. No deletion of 2020 or 2022. No
event-calendar exclusions** — matching the maintainer's canonical
correction: a named calendar-year escape hatch is itself vulnerable to
adaptive historical selection, since those episodes are already known
during discovery. If a genuinely regime-scoped version of this mechanism
is ever wanted, it must be a separate, fully preregistered hypothesis using
a deterministic state classifier built only from information available at
`T` — **H03 as scoped here is not made regime-specific in this task.**

## 20. Direction scope (symmetry)

H03 is symmetric. A continuation candidate requires both UP and DOWN
impulses to show continuation overall; an exhaustion candidate requires
both UP and DOWN impulses to show exhaustion overall. If only one side
survives:

- the symmetric H03 claim is `REJECTED_SPECIFIC_CLAIM`;
- the one-sided observation is recorded as `POSTHOC_UNTESTED`;
- it cannot rescue H03 and cannot enter Batch 01 validation directly.

*Design-red-team fairness assessment:* this is the correct separation
between falsifying a specific preregistered claim and declaring the
underlying phenomenon impossible. A genuine one-sided effect is not erased
— it is preserved, honestly labeled, and available to seed a future,
properly preregistered hypothesis; it is simply not permitted to rescue
the symmetric claim or skip the batch-freeze discipline in this run. Fair
in both directions: a real broad (symmetric) mechanism has a clear path to
survive, and a real narrow (one-sided) one is not discarded, only
correctly re-scoped.

## 21. Parameter robustness

Do not select the best cell. For each `W`, inspect `q90`/`q95`/`q98`: a
credible mechanism should show the same qualitative sign across
neighboring thresholds, and preferably a non-weaker (not necessarily
monotonically stronger) effect as extremeness increases. Compare `W=15m`,
`W=30m`, `W=60m`. One isolated `W`/`q` combination cannot promote H03 — it
may only generate a future `POSTHOC_UNTESTED` idea. See §4 for the
effective-N caveat: a coherent-looking plateau across thresholds partially
mitigates, but does not fully eliminate, the reference-window
estimation-noise risk, since correlated estimation error across thresholds
sharing the same methodology could still produce a spuriously coherent
result.

## 22. Candidate-for-freeze requirements

For either preregistered sign (continuation or exhaustion), a candidate
must satisfy all of:

1. primary close-return effect has that sign;
2. candidate-minus-matched normalized mean magnitude meets or materially
   exceeds the frozen MPIE;
3. extreme impulse materially separates from moderate momentum (§10);
4. the fixed negative control (§12) materially weakens/destroys the
   effect;
5. `q90`/`q95`/`q98` form a coherent same-sign neighborhood/sensible
   strength response (§21; subject to the §4 effective-N caveat);
6. **at least two adjacent horizons `H` support the same sign, evaluated on
   the primary `CONT_RET_H`/`NORM_CONT_RET_H` metric specifically — not on
   MFE/MAE, which are mechanically monotonic across nested horizons by
   construction and would trivially "cohere" regardless of any real effect
   (§15, fix)**;
7. the proposed sign appears in at least 4 of 5 development years (§19);
8. UP and DOWN both support the symmetric claim (§20);
9. no single month/regime dominates (§17);
10. dependence-aware uncertainty (block bootstrap + §18 diagnostic) is
    compatible with a real effect;
11. the §18 dependence diagnostic does not reveal an obviously misleading
    effective-N interpretation without explicit caution being disclosed in
    the writeup;
12. the primary outcome itself, not only MFE/MAE, supports the mechanism
    (§15).

## 23. Possible verdicts

The future development run must choose exactly one:

- `H03_CONTINUATION_CANDIDATE_FOR_FREEZE`
- `H03_EXHAUSTION_CANDIDATE_FOR_FREEZE`
- `H03_INCONCLUSIVE`
- `H03_REJECTED_SPECIFIC_CLAIM`

No validation is opened at this point. No R3 optimization is started
inside the development run.

---

**Reminder: this is still a design draft, not a preregistration.**
Preregistration additionally requires this draft to be committed as the
actual frozen preregistration text at the moment development opens, with
§0's remaining honest-disclosure gap (whether specific numeric conventions
were carried over from H01/H02) filled in with concrete specifics by
whoever opens development, using PRs #77/#78 as the source of truth for
H01/H02's real implementation.
