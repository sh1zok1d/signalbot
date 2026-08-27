# H03 — Extreme Impulse → Continuation vs Exhaustion — Design Draft

**Status: DESIGN DRAFT — NOT A PREREGISTRATION.**

This document is the design-red-team-corrected version of the proposed H03
family. It is not yet a frozen preregistration under
`docs/R2_SCREENING_PROTOCOL_V1.md`: that additionally requires H01/H02's
remote durability to be completed and confirmed first, and requires this
draft to be turned into an actual preregistration commit at the moment
development opens (not before). No development has started, no market
outcomes have been computed, and 2025/2026 remain untouched.

**Governing protocol:** `docs/R2_SCREENING_PROTOCOL_V1.md` (as corrected by
`docs/reviews/R2_SCREENING_PROTOCOL_V1_MAINTAINER_ADDENDUM.md`) and
`docs/EDGE_RESEARCH_PROTOCOL.md`.
**Design red-team:** `docs/reviews/H03_DESIGN_REDTEAM.md` — read that report
for the full rationale behind every change from the originally proposed
design; only the corrected result is repeated here.
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`.

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
  design review cannot verify from the artifacts available to it whether
  specific numeric choices below (60-minute refractory, the
  15/30/60/120/240-minute horizon ladder, the q90/95/98 percentile ladder)
  were newly derived for H03 or carried over as house convention from
  H01/H02's actual implementation. **This must be stated affirmatively, not
  left silent, before development opens.** Whoever writes the actual H03
  preregistration must add a concrete statement here (e.g., "the 60-minute
  refractory matches H02's own refractory, chosen for cross-family
  convention consistency, not because of any H02 outcome" or the honest
  alternative if that is not the case).
- **Control formulations considered:** exactly one structural control
  (moderate-momentum band) and one negative control (`+6h` circular shift)
  were considered for this design. No alternative formulation was tried and
  discarded. If that changes before preregistration, the discarded
  alternative(s) must be logged here, not silently dropped.
- **Design changes caused by this red-team** (full rationale in
  `docs/reviews/H03_DESIGN_REDTEAM.md`):
  1. added this Global Adaptivity disclosure section (§0);
  2. added effective-sample-size disclosure for rolling percentile
     statistics (§4);
  3. added a floor on the normalization denominator (§8);
  4. made decision-boundary `T` an explicit `bar_end_exclusive` definition
     (§2);
  5. required disclosure of unmatched structural-control cases (§10);
  6. disclosed the negative control's diurnal-confounding limitation (§12);
  7. made the matched-random seed's single-use discipline explicit (§11);
  8. disclosed that no alternative control formulations were considered
     (§0, §10, §12);
  9. defined the exact, fixed dependence diagnostic the canonical protocol
     required in the abstract (§14).
- **Search-surface ledger note:** H01 = 45 primary cells, H02 = 45 primary
  cells, H03 (this design) = 45 primary cells. H03 does not expand the
  per-family search surface relative to precedent.

---

## 1. Question (mechanism discovery, not a trading strategy)

After an unusually large short-horizon BTC directional move relative to its
recent local distribution, does subsequent price movement systematically:

- **A. continue** in the impulse direction,
- **B. reverse/exhaust** against the impulse direction, or
- **C.** show no practically meaningful robust effect?

Both continuation and exhaustion are preregistered competing possibilities.
This is mechanism discovery. It is explicitly **not** a trading strategy, a
PnL claim, a liquidation explanation, a news classifier, or a market-maker
explanation.

## 2. Decision grid

UTC-aligned 15-minute boundaries. Only information available at decision
time `T` may define the event. **`T` is defined as the `bar_end_exclusive`
of the 15-minute bar ending at `T`** (matching
`docs/manifests/CORE_BTC_BINANCE_V0.yaml`'s `canonical_available_at:
bar_end_exclusive` / `eligibility_rule: bar_end_exclusive <= decision_time`
convention) — not the bar's open, and not any later bar. *(m1 fix)*

## 3. Impulse windows

`W ∈ {15m, 30m, 60m}`.

```
IMPULSE_RET_W(T) = ln(close(T) / close(T-W))
```

Direction: `+1` for positive impulse, `-1` for negative impulse. Exact zero
impulse: excluded (a vacuous safeguard in practice given continuous price
data, kept for completeness).

## 4. Extremeness

```
ABS_IMPULSE_W(T) = abs(IMPULSE_RET_W(T))
```

Reference distribution: the same statistic, on the same 15-minute grid,
over the preceding 30 calendar days, strictly before `T` (current `T`
excluded).

`P_W(T)` = percentile rank of `ABS_IMPULSE_W(T)` in that reference
distribution.

Candidate thresholds: `q90`, `q95`, `q98`. No extra thresholds. Candidate
event: `P_W(T) >= threshold`.

**Effective-sample-size disclosure (M2 fix, required, not a new gate):**
for every `(W, q)` cell, report both:

- nominal reference-window observation count (~2,880 for a 30-day, 15-minute
  grid), and
- **effective (non-overlapping) count**, computed as
  `floor(30 * 24 * 60 / W_minutes)` — e.g. 2,880 for `W=15m`, 1,440 for
  `W=30m`, 720 for `W=60m`.

Any `(W, q)` cell whose effective count times `(1 - q)` (the expected number
of non-overlapping observations exceeding the threshold) falls below **200**
must be flagged for interpretive caution in the writeup. This is a fixed,
predeclared disclosure rule — it does not change which cells are tested or
add a new selectable threshold.

## 5. Refractory

60 minutes. Within each `(W, q)` cell: keep the earliest qualifying event;
suppress either-direction qualifying events during the following 60
minutes. Report pre-refractory and post-refractory event counts for every
cell. The refractory deduplicates *trigger identification* only; it is not
a claim of outcome-level independence between events spaced further apart
than 60 minutes — that is handled entirely by the dependence-sensitivity
machinery in §11 of `docs/R2_SCREENING_PROTOCOL_V1.md` (block bootstrap +
the diagnostic defined in §9 below), not conflated here.

## 6. Outcome horizons

`H ∈ {15m, 30m, 60m, 120m, 240m}`.

**Boundary rule (canonical, unchanged from the proposal — already correct):**
a development observation is eligible for horizon `H` only when the entire
frozen future `H` path resolves strictly before `2025-01-01T00:00:00Z`. No
horizon truncation. No future read into 2025. The identical rule applies
at the `2025 → 2026` boundary when validation/OOS phases are eventually
opened. This is a verbatim implementation of the maintainer-adopted
boundary-embargo fix in `docs/R2_SCREENING_PROTOCOL_V1.md` §1
("exclude, do not truncate").

## 7. Primary outcome

```
RET_H(T)      = ln(close(T+H) / close(T))
CONT_RET_H(T) = impulse_direction(T) * RET_H(T)
```

Positive = continuation. Negative = exhaustion. The sign convention is
fixed here, before any outcome is inspected, and must never be flipped
after outcomes are opened.

## 8. Normalization

```
PAST_MEDIAN_ABS_RET_H(T) = median of H-horizon absolute returns on the
    same 15m grid, over the preceding 30 calendar days, using only
    observations fully resolved strictly before T.
```

**Floor (M3 fix, required, fixed and outcome-independent):**
`PAST_MEDIAN_ABS_RET_H(T)` is floored at the corresponding statistic's own
5th percentile computed over the full development window using only data
available strictly before `T`. This prevents a division blow-up during
unusually quiet historical stretches from producing degenerate,
artificially enormous normalized outcomes. This floor is a fixed rule
declared here, before outcomes — not a parameter chosen after seeing
results.

```
NORM_CONT_RET_H(T) = CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)   [floored]
```

No future normalization; `PAST_MEDIAN_ABS_RET_H(T)` uses only pre-T data,
so it is independent of the candidate's own current or future outcome —
satisfying the canonical protocol's MPIE-anchoring requirement (§8).

## 9. MPIE (minimum practically interesting effect)

```
|candidate mean NORM_CONT_RET_H − matched-random mean NORM_CONT_RET_H| >= 0.10
```

for the preregistered candidate neighborhood. Interpretation: the
conditional directional mean must shift by at least 10% of the local
typical (trailing, pre-T) absolute H-horizon move. This anchor is
independent of the candidate's own development-sample result because the
normalization scale is a trailing, pre-T distributional statistic, not
derived from the candidate's outcome — satisfying
`docs/R2_SCREENING_PROTOCOL_V1.md` §8's maintainer-corrected anchoring rule.

Also report the raw mean effect in bps, descriptively; raw bps does not
replace the normalized MPIE and is not a profitability requirement.
Execution cost is explicitly **not** the primary MPIE anchor for this
mechanism-discovery experiment.

*Design-red-team assessment: 0.10 is a defensible, pre-anchored order of
magnitude — neither trivially small (which would make promotion easy to
game) nor implausibly large (which would kill real effects for no
principled reason). No change proposed.*

## 10. Structural control

Moderate-impulse population: `0.60 <= P_W(T) < 0.80`, same `W`, same
direction, same 60-minute refractory. Month- and direction-matched against
extreme candidates where possible; **any case where matching is not
possible must be explicitly counted and reported, not silently defaulted to
an unmatched comparison** *(m2 fix)*. Compare extreme vs. moderate impulse
using the same primary outcome.

This is the simplest available control that isolates "extremeness" as the
specific incremental ingredient while holding "directional momentum exists
at all" constant. No alternative structural control was considered or
discarded for this design *(m5 disclosure — see §0)*.

## 11. Matched random control

Month-matched and direction-composition-matched random UTC 15-minute
boundaries. 100 deterministic replicas. Seed: `20260831`. **This seed is
used exactly once and is never re-rolled after any early inspection of
results** *(m4 fix)*. Replicas estimate the control distribution only; they
are not new market evidence.

## 12. Negative control

`+6` hour circular shift within the same UTC day, preserving the original
impulse direction. Do not redetect an impulse at the shifted `T`. Require
valid past/future coverage at the shifted `T`.

*Design-red-team disclosure (m3):* a quarter-day shift moves most control
observations into a different part of the UTC day, which may introduce
mild diurnal/session-timing differences rather than a perfectly pure
"same regime, different specific trigger" placebo. This matches the
project's own established convention (`docs/RESEARCH_LEDGER.md`,
E1-RUN-001's "fixed +6h same-day circular time-shift control") and is not
materially flawed enough to require a replacement. This limitation is
recorded here as a known, accepted scope limitation, not an unstated
assumption. No alternative negative control was considered or discarded for
this design *(m5 disclosure — see §0)*.

## 13. Search surface

`3 W × 3 q × 5 H = 45` primary cells. Decile relationships may be reported
diagnostically but must not create additional selectable thresholds. This
matches H01's and H02's own stated 45-cell search surfaces — H03 does not
expand the per-family search surface relative to precedent.

## 14. Dependence handling

Primary: UTC-week block bootstrap. Fixed sensitivity for any proposed R3
survivor: 1-week, 2-week, and 4-week blocks — robustness checks, not
selectable alternatives.

**Canonical non-selectable dependence diagnostic, defined exactly once
(design-red-team deliverable):**

> **ACF-crossing dependence-half-life proxy.** On the full development
> window (embargo-respecting), compute the **daily** series of total
> absolute 15-minute log-returns (a realized-volatility-activity proxy,
> computed independently of any candidate event or outcome). Compute its
> autocorrelation function at the fixed, predeclared lag set
> `{1, 2, 4, 8, 16, 32}` calendar days. Report the diagnostic as **the
> smallest lag in that set at which the ACF first falls below 0.2** (a
> fixed, non-tuned threshold). If the ACF has not fallen below 0.2 by lag
> 32, report the diagnostic as `>32 days`.

This is not a new selectable block length — it is a single reported number.
A value at or beyond 16–32 days is a direct signal that 1w/2w/4w block
sensitivity may understate true dependence, and must be disclosed and
flagged for qualitative caution in any freeze writeup; it does not by
itself gate promotion. Fully reproducible and interpretable from the frozen
dataset and this fixed formula alone.

## 15. Chronological stability

Report 2020, 2021, 2022, 2023, 2024 separately. For an unconditional H03
claim, the candidate neighborhood's required sign should normally hold in
at least 4 of 5 years; one year may be weaker/null; repeated sign
reversals block promotion.

**No named shock-year exclusions. No deletion of 2020 or 2022** — matching
the maintainer's canonical correction: a named calendar-year escape hatch
is itself vulnerable to adaptive historical selection, since those episodes
are already known during discovery. If a genuinely regime-scoped version of
this mechanism is later wanted, it must be a separate, fully preregistered
hypothesis using a deterministic state classifier built only from
information available at `T` — **H03 as scoped here is not made
regime-specific.**

## 16. Direction scope (symmetry)

H03 is symmetric. A continuation candidate requires both UP and DOWN
impulses to show continuation overall; an exhaustion candidate requires
both UP and DOWN impulses to show exhaustion overall. If only one side
survives:

- the symmetric H03 claim is `REJECTED_SPECIFIC_CLAIM`;
- the one-sided observation is recorded as `POSTHOC_UNTESTED`;
- it cannot rescue H03 or enter Batch 01 validation directly.

## 17. Candidate-for-freeze requirements

For either sign (continuation or exhaustion), a candidate must satisfy all
of:

1. primary effect has the preregistered sign;
2. candidate-minus-matched-random normalized mean magnitude meets the MPIE;
3. extreme impulse materially separates from the moderate-momentum
   structural control;
4. the `+6h` negative control materially weakens the effect;
5. `q90`/`q95`/`q98` show a coherent sign / plateau / sensible strength
   response (not a single isolated spike — see §4's effective-N disclosure
   for the caveat this partially, but not fully, mitigates);
6. at least two adjacent horizons `H` support the same sign;
7. the sign holds in at least 4 of 5 development years (§15);
8. UP and DOWN both support the symmetric claim (§16);
9. no single month/regime dominates the result;
10. dependence-aware uncertainty (block bootstrap + §14 diagnostic) is
    compatible with a real effect;
11. the primary close-return outcome itself supports the mechanism.

Secondary MFE/MAE metrics cannot rescue a failed primary outcome.

---

**Reminder: this is still a design draft, not a preregistration.**
Preregistration additionally requires (a) H01/H02 remote durability to be
completed and confirmed, and (b) this draft to be committed as the actual
frozen preregistration text at the moment development opens, with §0's
honest-disclosure gaps filled in with concrete specifics by whoever opens
development, using access to H01/H02's real implementation artifacts.
