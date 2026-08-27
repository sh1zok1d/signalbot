# H05 — Taker Imbalance → Subsequent Return Distribution: Design (Pre-Outcome)

**Status:** DESIGN / PREREGISTRATION-PLANNING ONLY. No prereg freeze SHA
exists yet. No implementation code exists yet. No real H05 outcomes have
been computed.
**Real H05 outcomes computed:** **NONE.**
**2025 inspected:** **NO.** **2026 inspected:** **NO.**
**Predecessor state:** H04 result commit
`0c89fc01ac464028440039aff34f92204b2588b9`
(`H04_REJECTED_SPECIFIC_CLAIM`). H01, H02: REJECTED/KILL. H03:
`H03_REJECTED_SPECIFIC_CLAIM`.
**Companion document:** `docs/reviews/H05_DESIGN_REDTEAM.md` (adversarial
review; every decision below is the output of that review, not a raw
restatement of the task's starting proposal).
**Batch position:** H05 is the fifth and **final** primary mechanism
family of R2 Batch 01. No H06 is authorized to open automatically once H05
closes. The next mandatory step after H05 closes is **Batch01 synthesis**.
**Amendment history:** this design has undergone two PRE-OUTCOME DESIGN
CORRECTIONS, neither made by inspecting any real H05 outcome:

1. Closed two material control gaps (price sign/alignment, §9–§10;
   mandatory activity control, §9/§11) and two formalization gaps
   (dependence-diagnostic naming, §21; the 1w/2w/4w "survives" criterion,
   §22 item 12), and re-evaluated `W` robustness (§18).
2. **(This revision.)** Formalized exact sign symmetry for the two
   preregistered claim orientations via a frozen `S` variable (§2), so
   that every gate (`MPIE`, structural, matched, `+6h`, bootstrap,
   `q`/`H`/`W` neighborhoods, year stability, BUY/SELL symmetry) is
   expressed as an explicit oriented inequality rather than a positive-
   only inequality that silently assumed continuation. Restored `MPIE`'s
   intended Batch01 semantics as a floor on the matched-random separation
   (`ORIENTED_MATCHED_DELTA`, §17), not an undefined "standardized effect
   size." Made the `+6h` negative-control gate an exact frozen contrast
   (`ORIENTED_SHIFT_DELTA >= CONTROL_DELTA_MIN`, §14/§17) instead of a
   qualitative "does not reproduce" description.

The overall mechanism, `W`/`q`/`H` surface, sign alternatives, primary
feature, refractory rule, `MPIE`/`CONTROL_DELTA_MIN` numeric values,
seeds, and Batch01 cell accounting are unchanged by either correction.

This document freezes the H05 design *before* any real market outcome is
computed. Nothing in this document may be amended after real H05 outcomes
are seen, except through the same pre-outcome / post-hoc-quarantine
discipline used in H03/H04 (a pre-outcome correction is permitted only if
it is justified without reference to any real H05 outcome; anything
justified by looking at real H05 outcomes is `POSTHOC_UNTESTED` and cannot
rescue a killed cell).

---

## 0. Global adaptivity disclosure

H05's mechanism family (taker aggressor-side imbalance → subsequent
return) was named in `docs/R2_SCREENING_PROTOCOL_V1.md`'s Batch 01 list
before any of H01–H04 were run, so it is not a post-hoc addition to the
batch.

This design **reuses implementation lessons** from H03 and H04:

- membership-based (not positional) set exclusion for matched-random pools
  (H03 audit fix);
- real-timestamp, never panel-index, calendar keys (H03 audit fix);
- candidate-weighted deterministic stratified standardization for
  structural controls, with unmatched candidates reported and
  control-only strata zero-weighted (H04 post-outcome-correction pattern);
- 1w/2w/4w dependence-sensitivity wired in from the initial implementation
  commit, not discovered as a gap later (H04 implementation-completion
  lesson);
- exclusive vs. nested threshold-family reasoning applied fresh to H05's
  own dial, not copy-pasted from H04's conclusion (see §6).

This design does **not** reuse any outcome-derived market conclusion from
H01–H04 (e.g., no assumption is imported about whether momentum,
compression, impulse, or pullback effects were found to exist or not; H05
stands on its own mechanism).

**Adaptivity disclosure — PARTIAL.** One frozen parameter,
`q_moderate = 0.80` used as the fixed lower edge of the "ordinary" control
band (§9), is chosen to numerically match H03's already-frozen moderate
band and H04's `q = 0.80` looseness threshold. This is disclosed as a
partial (not independent) parameter choice, exactly as H04 disclosed its
own reuse of `q = 0.80`. It is an implementation-lesson reuse (a
convention for what counts as "ordinary" flow), not an outcome-derived
market conclusion.

---

## 1. Research question

Not: "Do large taker-buy periods occur before positive returns?" (this
would trivially reproduce ordinary price momentum, since taker-buy
imbalance and same-window price return are mechanically correlated within
a bar).

H05 asks: **does aggressive taker-flow imbalance contain incremental
information about subsequent BTC return distribution beyond
contemporaneous price movement, ordinary market activity, and matched
timing?**

"Incremental" is operationalized as: the candidate-vs-structural-control
delta must survive (a) stratification on the **sign (alignment) and
magnitude** of contemporaneous price return relative to `D` (§9–§10), (b)
stratification on contemporaneous trailing activity level (§9/§11), and
(c) a matched-random timing baseline (§13) — not merely a raw
candidate-vs-population gap. All three are now mandatory structural-match
dimensions (see §9); activity is no longer descriptive-only, which is
what makes the "beyond ordinary market activity" clause of this question
actually supportable by the design (see §11).

---

## 2. Claim sign(s) — both preregistered

Two competing, mutually exclusive interpretations of the same signed
statistic are preregistered together, exactly as H03 preregistered
continuation vs. exhaustion for impulse severity:

- **(A) FLOW CONTINUATION:** buy imbalance → subsequent positive return;
  sell imbalance → subsequent negative return. `sign(outcome) == D`.
- **(B) FLOW EXHAUSTION / REVERSAL:** buy imbalance → subsequent negative
  return; sell imbalance → subsequent positive return.
  `sign(outcome) == -D`.

This is **one 45-cell search surface**, not two (see §16 for the
sign-multiplicity disclosure, which is tracked separately from the cell
count exactly as it was for H03).

**Anti-cherry-pick rule (frozen, pre-outcome):** a sign may not be
selected or promoted because the other sign failed first. Both (A) and
(B) checklists (§18) are evaluated in full, independently, against the
same frozen cells and controls. Both results are recorded in the ledger
verdict even if only one sign reaches `CANDIDATE_FOR_FREEZE`. If neither
sign passes, the verdict record still shows both checklists' failure
points.

**Claim-orientation formalism — `S` (frozen this revision, formalization
correction, no real outcome inspected):** the stored primary metric is
unchanged — `X(T,H) = NORM_TAKER_RET_H(T)` (§15) is always computed and
persisted in its own natural sign, never multiplied by anything and never
re-signed in storage. A separate, purely presentational orientation
variable is frozen for evaluating each claim:

```
S = +1   for FLOW CONTINUATION   (A)
S = -1   for FLOW EXHAUSTION / REVERSAL   (B)
```

For a given cell (fixed `W, q, H`) and a given claim sign, define, from
the cell's own already-frozen quantities:

```
candidate_mean   = mean(X) over the candidate population                (§8, §15)
matched_mean     = mean of the matched-random reference statistic       (§13)
structural_mean  = candidate-weighted standardized ordinary-flow control mean (§9)
shifted_mean     = the +6h negative-control mean                        (§14)
```

and the four oriented promotion quantities used by every gate below:

```
ORIENTED_PRIMARY           = S * candidate_mean
ORIENTED_MATCHED_DELTA     = S * (candidate_mean - matched_mean)
ORIENTED_STRUCTURAL_DELTA  = S * (candidate_mean - structural_mean)
ORIENTED_SHIFT_DELTA       = S * (candidate_mean - shifted_mean)
```

This is a **presentational re-orientation only**, applied at the
gate-evaluation layer — it never alters `X`, `candidate_mean`,
`matched_mean`, `structural_mean`, or `shifted_mean` themselves, all of
which remain stored in their own natural sign for both claim orientations
to read from. Under this formalism, `CONTINUATION` passes on sufficiently
**positive** oriented quantities and `REVERSAL` passes on sufficiently
**positive** oriented quantities too (because `S = -1` flips the sign of
what would otherwise be a negative raw delta) — i.e. every gate is written
once, as `ORIENTED_* >= threshold`, and applies identically to both signs
without a second, mirrored copy of each rule. See §17 (MPIE/control
gates), §14 (`+6h` gate), §18 (`q`/`H`/`W` neighborhoods), §19 (BUY/SELL
symmetry), §20 (year stability), and §22 item 12 (bootstrap) for where
`S` and the oriented quantities are used.

---

## 3. Dataset and information-at-T

Dataset: `CORE_BTC_BINANCE_V0`, snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`,
`ACCEPTED_FOR_DISCOVERY`, `research_authorized: true`,
`confirmatory_authorized: false`. Frozen interval
`[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)`.

Evidence pools (unchanged from the R2 protocol, reused verbatim):

| Pool | Range | Use in this design round |
|---|---|---|
| Discovery/development | `2020-02-01` → `2025-01-01` | Design and (later, if authorized) implementation testing on synthetic fixtures only in this round |
| Batch validation | 2025 (full year) | **UNTOUCHED** |
| Final OOS | 2026 through `2026-08-26` | **UNTOUCHED** |

All information used to construct a candidate at decision time `T` must be
observable strictly before or at `T` using only data with
`bar_end_exclusive <= T`. No information from `[T, T+H)` may enter
feature, control, or eligibility computation.

**Horizon boundary rule (reused verbatim from H03/H04):** a candidate's
complete outcome path `close(T) .. close(T+H)` must resolve strictly
before the active pool's `end_exclusive` boundary. Candidates whose
horizon would cross the boundary are **excluded**, never truncated.

---

## 4. Available fields (no invented data)

Only the following raw and arithmetic-derived fields are used:

- `base_volume`, `quote_volume` (raw)
- `taker_buy_base_volume`, `taker_buy_quote_volume` (raw)
- `taker_sell_base_volume = base_volume - taker_buy_base_volume`
  (allowed arithmetic derivation, per
  `docs/manifests/CORE_BTC_BINANCE_V0.yaml`)
- `taker_sell_quote_volume = quote_volume - taker_buy_quote_volume`
  (allowed arithmetic derivation)
- `close` (raw, for return computation)

No order-book data, no trade-level CVD, no open interest, no funding, no
liquidations, and no cross-exchange information are used or invented. H05
remains a CORE-manifest hypothesis using only fields already present in
`CORE_BTC_BINANCE_V0`'s `raw_schema` and `allowed_arithmetic_derivations`.

---

## 5. Decision grid and time semantics

- Base grid: 15-minute UTC bars, aligned to `:00/:15/:30/:45`.
- Feature window for a decision at bar-close time `T`:
  `[T - W, T)`, using only bars with `bar_end_exclusive <= T`.
- `T` itself is a `bar_end_exclusive` boundary — the same convention as
  H03/H04's `bar_end_exclusive` semantics, carried forward to avoid
  reintroducing a timestamp-vs-panel-index bug.
- Outcome window: `[T, T + H)`, requiring `close(T)` and `close(T+H)` both
  observable and `T + H` strictly before the pool's `end_exclusive`.

---

## 6. Primary flow feature

For window size `W`, at decision time `T`:

```
BUY_W(T)   = sum(taker_buy_base_volume)  over bars in [T-W, T)
SELL_W(T)  = sum(taker_sell_base_volume) over bars in [T-W, T)
TOTAL_W(T) = BUY_W(T) + SELL_W(T)   # == sum(base_volume) over the window

TAKER_IMBALANCE_W(T) = (BUY_W(T) - SELL_W(T)) / TOTAL_W(T)
                       = 2 * BUY_W(T) / TOTAL_W(T) - 1
```

- **Base-volume is primary.** Quote-volume is computed identically
  (`BUY_W_Q`, `SELL_W_Q`, `TAKER_IMBALANCE_W_Q`) but is **secondary,
  diagnostic-only** — reported alongside the primary result, never used
  to gate, threshold, or rescue a base-volume result. Base volume avoids
  a price-weighting confound: quote-volume imbalance is mechanically
  inflated during large price moves within the same window (a unit of
  base volume traded at a higher price contributes more quote-volume
  weight), which would partially reproduce the very price-return confound
  §10 exists to isolate.
- `TAKER_IMBALANCE_W(T) ∈ [-1, +1]` by construction.
- If `TOTAL_W(T)` is zero or otherwise invalid (missing/non-finite inputs
  anywhere in the window), the candidate at that `T` is **explicitly
  ineligible** — never coerced to `0`, never silently dropped without a
  record. Ineligible timestamps are counted and reported per cell.

---

## 7. Flow direction

```
D(T) = sign(TAKER_IMBALANCE_W(T))   ∈ {+1, -1}
```

`D(T) = 0` (exact tie) is **excluded** — not assigned to either direction.
`D` is the sole direction label used throughout matching, controls, and
the refractory rule.

---

## 8. Flow extremeness (threshold family)

`ABS_IMBALANCE_W(T) = abs(TAKER_IMBALANCE_W(T))`.

Reference distribution: the **trailing 30-day, same-15-minute-grid**
empirical distribution of `ABS_IMBALANCE_W` up to and including `T`
(strictly causal, no future information, no global/whole-sample
percentile). Percentile rank is midrank (average-rank-for-ties), exactly
as used in H03/H04's percentile machinery.

```
ABS_IMBALANCE_PCTL_W(T) = trailing_30d_midrank_percentile(ABS_IMBALANCE_W, T)
```

**Threshold family (frozen, NESTED):**

```
q ∈ {0.80, 0.90, 0.95}
candidate membership at q:  ABS_IMBALANCE_PCTL_W(T) >= q
```

**Why nested, not exclusive (the H04 lesson applied, not copied):** H04
required *exclusive* depth bands because "pullback depth" had no
monotonic a-priori dose-response prior — a very deep pullback could
equally plausibly mean "healthy retracement, buy the dip" (continuation)
or "structural breakdown" (exhaustion), so a nested "at least this deep"
family would silently mix those two populations inside every wider band.
H05's dial is different: under **either** preregistered sign (§2), the
*mechanism story* itself is monotonic in severity — a more extreme
aggressor-flow imbalance is hypothesized to carry *more* information
(continuation) or provoke *more* exhaustion pressure (reversal) than a
mild one, not to flip character at some interior depth. There is no H05
analogue of H04's "could mean either regime" ambiguity. A nested "at
least q" family is therefore the correct, non-mechanical choice here,
matching H01's and H03's convention.

`q = 0.80` is the loosest threshold and is disclosed as a partial
adaptivity reuse (§0), not an independently optimized choice.

Maximum 3 thresholds, as instructed; no fourth threshold is added.

---

## 9. Structural control — the non-negotiable control

This is the most important control in the design, per the task's own
framing, and is where the raw starting proposal contained a real,
closeable gap (identified and closed in `H05_DESIGN_REDTEAM.md` §5).

**The gap:** if the control's "ordinary" comparison population were
defined relative to the `q` under test (e.g. "below this cell's `q`"),
then a looser cell's control population would silently include rows that
a tighter cell would classify as candidates elsewhere in the family —
different cells would not share a stable comparison population, and
cross-cell contamination would make the 3-`q` family impossible to
interpret jointly.

**Fix (frozen):** the "ordinary" control population is a single **fixed**
band, decoupled from whichever `q` is under evaluation, reusing H03's
exact frozen moderate band verbatim:

```
ordinary control population:  0.60 <= ABS_IMBALANCE_PCTL_W(T) < 0.80
(same D convention: control rows carry their own D, matched as below)
```

This band is identical across all three `q` cells; it never overlaps any
candidate band (`>= 0.80`, `>= 0.90`, or `>= 0.95`), so no candidate row
can ever also be a control row.

**PRE-OUTCOME DESIGN CORRECTION (this revision):** independent pre-outcome
review found that matching on `D` (the sign of taker imbalance) does
**not** control the sign of contemporaneous price return — a BUY-imbalance
candidate with a positive contemporaneous return and a BUY-imbalance
control row with a *negative* contemporaneous return of similar magnitude
could previously land in the same stratum, leaving ordinary price
momentum/mean-reversion direction as an uncontrolled confound. This is
closed below by adding an explicit price-alignment dimension, and a
matching activity-control gap (§11) is closed by adding a mandatory
activity dimension. Neither correction was made by inspecting any real
H05 outcome.

**Signed price alignment (new):**

```
SIGNED_PRICE_RET_W(T) = D(T) * PRICE_RET_W(T)

price_alignment(T) = ALIGNED  if SIGNED_PRICE_RET_W(T) >  0
                    = OPPOSED  if SIGNED_PRICE_RET_W(T) <= 0
```

`price_alignment` expresses whether the contemporaneous price move over
`[T-W, T)` points the **same way** as the taker-imbalance direction
(`ALIGNED`) or not (`OPPOSED`). **Exact-zero treatment (frozen,
deterministic, decided pre-outcome):** `SIGNED_PRICE_RET_W(T) == 0` is
assigned to `OPPOSED`, not to a separate `FLAT` category and not to
`ALIGNED`. Rationale: (a) keeping `price_alignment` strictly binary avoids
adding a third stratification level on top of the already-mandatory
strength and activity splits below, which would fragment strata further
without a compensating scientific reason; (b) `OPPOSED` is the
conservative choice — a bar with *no* directionally-confirming price move
provides no evidence that price momentum is doing the work, so folding it
into `ALIGNED` would risk inflating the "ordinary flow looks like this
too" pool with rows that do not actually instantiate the confound this
control exists to isolate; (c) the rule is applied identically regardless
of `D`'s sign or which claim sign (§2) is under evaluation, so it does
not asymmetrically favor continuation over reversal or vice versa. With
continuous close prices, exact zero is a measure-zero event in practice
but the rule must still be frozen for determinism.

**Matching/standardization (candidate-weighted, deterministic, reusing
the H04 post-outcome-correction pattern):**

- Match strata (five dimensions, all mandatory):
  `(calendar_month, D, price_alignment, price_strength_bin, activity_bin)`
  where:
  - `price_strength_bin` is the same 2-level causal split of
    `abs(PRICE_RET_W(T))` described in §10 (unchanged by this
    correction — it still measures magnitude only; §10 explains why sign
    is handled separately via `price_alignment` rather than folded into
    this bin);
  - `activity_bin` is the new mandatory activity-level split defined in
    §11.
- For each stratum present in the **candidate** population, control rows
  in the same stratum are weighted by the candidate row count in that
  stratum (candidate-weighted standardization); strata that appear only
  in the control population (never in the candidate population) receive
  **zero weight** and do not enter the standardized comparison.
- Candidates in a stratum with **no** matching control rows are retained
  and reported as **unmatched candidates** (count and share), not
  silently dropped from the candidate population — they simply do not
  contribute to the standardized-delta computation's denominator for that
  stratum. If the unmatched share is large enough that the standardized
  comparison lacks support, the correct downstream verdict is
  `INCONCLUSIVE` (§23) — **not** a post-outcome loosening of the strata.
  No overlap-support threshold is invented now or later based on real
  outcomes; insufficient support is reported and results in
  `INCONCLUSIVE`, exactly as instructed.
- The gate compares the candidate population's outcome distribution to
  the **standardized** (candidate-weighted) control distribution — never
  to an unstandardized full-population baseline.

**Why not over-match further:** the strata are limited to five dimensions
(month, direction, price alignment, one coarse price-strength bin, one
coarse activity bin). No sixth stratifying dimension is added. This is
already a denser stratification than the prior revision, and is adopted
only because both corrections (price sign, activity) are scientifically
required by the claim in §1 — not because finer stratification is free.
Unmatched-candidate and zero-weighted-stratum shares are reported per
cell so that any resulting support loss is visible, not hidden.

---

## 10. Price-return confound

```
PRICE_RET_W(T) = log(close(T) / close(T - W))
```

`PRICE_RET_W` is the same-window contemporaneous log return used both (a)
as the price-strength stratification input for the structural control
(§9) and (b) as the explicit confound variable the design must show H05
survives. `abs(PRICE_RET_W(T))` is stratified into 2 bins at its own
trailing-30-day midrank percentile 0.50, computed independently per `W`.

**PRE-OUTCOME DESIGN CORRECTION (this revision):** the previous revision
argued that stratifying only on magnitude was sufficient because `D`
already anchors sign. That reasoning was wrong: `D` is the sign of
*taker imbalance*, not the sign of *contemporaneous price return* — the
two are correlated but not identical, and a candidate/control pair can
share the same `D` while having opposite-signed `PRICE_RET_W`. This left
price-momentum direction as an uncontrolled confound, exactly the
mechanism H05's central claim must rule out. The fix is `§9`'s new
`price_alignment` dimension, built from `SIGNED_PRICE_RET_W(T) =
D(T) * PRICE_RET_W(T)`: this is the correct way to fold sign back in,
because it expresses sign *relative to* `D` (whether the contemporaneous
move agrees with the imbalance direction) rather than sign in isolation,
so it does not collapse into a redundant re-statement of `D` itself.
`price_strength_bin` (this section) continues to carry **magnitude only**
— `price_alignment` (§9) carries the relative-sign information. Together
they fully specify the contemporaneous price-return confound without
duplicating `D`.

The design gate (§14/§22) requires the candidate-vs-standardized-control
delta to remain material *after* stratifying on both `price_alignment`
and `price_strength_bin` — a raw, unstratified candidate-vs-population
gap that disappears once conditioned on the sign and magnitude of
contemporaneous price return would indicate H05 is merely restating price
momentum (or momentum-direction-conditional mean-reversion), not adding
incremental information, and must not pass.

---

## 11. Activity / volume confound — mandatory stratum (revised)

**PRE-OUTCOME DESIGN CORRECTION (this revision, supersedes the prior
descriptive-only decision):** the prior revision left trailing
activity/volume level as a descriptive-only diagnostic. Independent
pre-outcome review found this inconsistent with §1's research question,
which explicitly claims incremental information "beyond ... ordinary
market activity" — a descriptive diagnostic cannot support that clause of
the claim, because it never actually removes activity as an explanation
for any observed effect. This is corrected now, before any real outcome
is inspected.

**Causal activity definition (frozen):**

```
activity_bin(T) = LOWER  if trailing_30d_midrank_percentile(TOTAL_W, T) <  0.50
                 = UPPER  if trailing_30d_midrank_percentile(TOTAL_W, T) >= 0.50
```

using `TOTAL_W(T)` (§6) — the same causal, trailing-30-day, same-grid,
midrank-percentile machinery already used for `ABS_IMBALANCE_PCTL_W` and
`price_strength_bin`, applied instead to total traded base volume over
the window. One coarse, predeclared 2-level split only (`LOWER`/`UPPER`
at percentile 0.50) — no finer activity binning is introduced.

`activity_bin` is now one of the five mandatory structural-match strata
(§9): `(calendar_month, D, price_alignment, price_strength_bin,
activity_bin)`, standardized with the same candidate-weighted,
control-only-zero-weight, unmatched-candidates-reported discipline as
every other stratum dimension.

**Mechanism/causal-mediation note:** activity may partly *mediate*
genuinely informed aggressive flow (e.g. a large informed order naturally
coincides with elevated volume). Controlling for it therefore risks
removing some of the genuine mechanism along with the confound. This
trade-off is accepted deliberately: H05's claim in §1 is specifically that
**imbalance itself** — not merely "unusually high activity" — carries
incremental information, so the claim as stated requires activity to be
controlled, not left descriptive. The alternative (narrowing the claim to
drop the "beyond ordinary market activity" clause) was considered and
rejected in favor of retaining the broad claim and adding the control, per
the review's own stated preference; this is recorded as the frozen
choice, not left open for a later, outcome-informed pick.

**If structural support becomes insufficient** under this five-dimensional
stratification (too many unmatched candidates / zero-weighted strata),
the correct verdict is `INCONCLUSIVE` (§23), never a signal to drop the
`activity_bin` or `price_alignment` dimensions after outcomes are seen —
see the post-hoc rule (§24, item 9).

---

## 12. Refractory / episode control

**Frozen rule:** **either-direction, 60-minute refractory**, keep the
earliest qualifying timestamp within any 60-minute window and suppress
subsequent qualifying timestamps of *either* direction inside that window,
matching the H03/H04 precedent exactly.

**Rejected alternative:** a direction-aware rule that would start a new
episode as soon as the opposite extreme direction appears (even inside the
60-minute refractory window) was considered and rejected — it would
implicitly encode an assumption that a direction flip is mechanistically
meaningful before any outcome evidence exists, which is exactly the kind
of pre-outcome mechanism assumption this design avoids making. The single,
direction-agnostic rule is chosen pre-outcome and is not selectable.

---

## 13. Matched-random baseline

- Match keys: **calendar month + direction (`D`)** only — deliberately
  **not** additionally bucketed by price-strength, to avoid duplicating
  the structural control's own stratification (§9). The matched-random
  baseline and the structural control are intended to answer related but
  distinct questions (arbitrary-timing-within-month-and-direction vs.
  price-return-and-activity-matched "ordinary flow"), and collapsing them
  into the same stratification would make one of the two controls
  redundant.
- Replicates: **100**, matching the established H03/H04 convention.
- Sampling: without replacement, membership-based (not positional) set
  exclusion when drawing replicate pools — the direct implementation
  lesson from the H03 post-freeze audit bug.
- Seed: `20260904` (frozen, deterministic, master seed for the
  matched-random draw).
- Reported per cell: mean (`matched_mean`, §2), median, `p025`, `p50`,
  `p975` of the matched outcome distribution, and `candidate_minus_matched`
  (`candidate_mean - matched_mean`; the claim-oriented gate,
  `ORIENTED_MATCHED_DELTA = S * candidate_minus_matched`, is defined in
  §2 and gated against `MPIE` in §17). This matched-random distribution's
  own `p025/p50/p975` describes the spread of `matched_mean` under
  resampling — a distinct estimand from the candidate primary mean's own
  bootstrap interval (§22 item 12); the two are never substituted for one
  another.

---

## 14. Negative control

`+6h` circular time shift of the outcome window, **preserving each
candidate's own `D`** (the shift moves which return window is attached to
a given candidate's flow-direction label, without altering direction
itself). The resulting mean of the shifted-outcome statistic is
`shifted_mean` (§2). Collision fraction (shifted timestamps that land on
another already-used candidate timestamp) is computed and reported per
cell.

**PRE-OUTCOME FORMALIZATION CORRECTION (this revision):** the gate is now
an exact frozen contrast rather than the qualitative "does not reproduce
the candidate effect" description used previously:

```
ORIENTED_SHIFT_DELTA = S * (candidate_mean - shifted_mean) >= CONTROL_DELTA_MIN (0.05)
```

equivalently: `candidate_mean - shifted_mean >= +0.05` for `CONTINUATION`
(`S=+1`), and `candidate_mean - shifted_mean <= -0.05` for `REVERSAL`
(`S=-1`) — i.e. the `+6h`-shifted timing must **not** reproduce the
candidate's own oriented effect to at least the same `CONTROL_DELTA_MIN`
margin used for the structural control (§9/§17). Collision-fraction
reporting is unchanged by this correction.

Every control formulation actually attempted (matched-random
stratification choices, negative-control shift amount) is logged in the
design/implementation record, not only the final frozen choice — reusing
the H03/H04 discipline of recording rejected alternatives.

---

## 15. Primary outcome and normalization

```
raw_outcome(T, H)  = log(close(T+H) / close(T))
signed_outcome(T,H) = D(T) * raw_outcome(T, H)
NORM_TAKER_RET_H(T) = signed_outcome(T,H) / trailing_30d_median_abs_H_return(T)
```

`trailing_30d_median_abs_H_return(T)` is the trailing 30-day median of
`abs(raw_outcome)` over horizon `H`, computed strictly causally up to `T`,
with **no future normalization** (no whole-sample or forward-looking
denominator). This is the same normalization discipline used in H04 for
`NORM_TREND_CONT_RET_H`.

The primary outcome is a **normalized signed return**, not PnL, not a
trading rule, and not a Sharpe-like ratio.

---

## 16. Search surface and sign-multiplicity accounting

Primary search surface:

```
W ∈ {15, 30, 60}   (3)
q ∈ {0.80, 0.90, 0.95}   (3)
H ∈ {15, 30, 60, 120, 240}   (5)
3 × 3 × 5 = 45 cells
```

No additional dial is added beyond `W`, `q`, `H`. This is not enlarged
relative to the task's starting proposal.

**Global search-surface ledger update:** H01–H04 previously accounted for
`180` cells. H05 adds `45` cells → running total **225** cells across R2
Batch 01. The **sign multiplicity** (both continuation and reversal
preregistered on the same 45 cells) is disclosed **separately** from the
225-cell count, exactly as H03's continuation-vs-exhaustion multiplicity
was disclosed separately rather than doubling its own cell count. This
avoids conflating "how many distinct (W, q, H) cells were searched" with
"how many sign-interpretations were tested against each cell" — both
numbers are recorded, but only the former is added to the running
225-cell total.

---

## 17. MPIE and control materiality

**PRE-OUTCOME FORMALIZATION CORRECTION (this revision):** the prior
revision's checklist expressed these gates as bare positive inequalities
("standardized effect size `>= 0.10`"), which (a) left `REVERSAL`
semantics ambiguous/impossible under a purely positive-only reading, and
(b) drifted from the established Batch01 convention that `MPIE` measures
practical separation from the **matched-random** baseline specifically,
not an undefined generic "standardized effect size." Both are restored/
clarified below using the `S`/oriented-quantity formalism from §2. This
is a clarification of already-intended semantics, not a new parameter and
not a numeric change.

- **`MPIE = 0.10`** — frozen as the practical minimum for
  `ORIENTED_MATCHED_DELTA` (§2):

  ```
  ORIENTED_MATCHED_DELTA = S * (candidate_mean - matched_mean) >= 0.10
  ```

  i.e. `candidate_mean - matched_mean >= +0.10` for `CONTINUATION`, and
  `candidate_mean - matched_mean <= -0.10` for `REVERSAL`. `MPIE` is
  **not** redefined as the candidate mean alone, as the structural
  standardized delta, or as a statistical-significance criterion — it is
  specifically the matched-random separation, matching H01–H04's own
  established use of `MPIE`.
- **`CONTROL_DELTA_MIN = 0.05`** — frozen as the practical minimum for
  **both** `ORIENTED_STRUCTURAL_DELTA` (§9) and `ORIENTED_SHIFT_DELTA`
  (§14):

  ```
  ORIENTED_STRUCTURAL_DELTA = S * (candidate_mean - structural_mean) >= 0.05
  ORIENTED_SHIFT_DELTA      = S * (candidate_mean - shifted_mean)    >= 0.05
  ```

  i.e. for `CONTINUATION`: `candidate_mean - structural_mean >= +0.05`
  and `candidate_mean - shifted_mean >= +0.05`; for `REVERSAL`, both
  differences `<= -0.05`.
- **Primary sign requirement (restored, not previously stated as an
  explicit gate):** `ORIENTED_PRIMARY = S * candidate_mean > 0` is
  required independently — `MPIE`/`CONTROL_DELTA_MIN` separation from a
  reference cannot promote a cell whose own raw primary effect points the
  wrong way (see §22 item 1, added this revision).

**Justification for reuse (not re-derivation):** both numeric thresholds
are protocol-level floors fixed in `docs/R2_SCREENING_PROTOCOL_V1.md` /
`docs/EDGE_RESEARCH_PROTOCOL.md` before H01 began; they are not
re-optimized per hypothesis, and their numeric values (`0.10`, `0.05`)
are unchanged by this correction — only the estimand each applies to, and
the sign-orientation of the inequality, are clarified/restored.

---

## 18. Parameter robustness (frozen, pre-outcome)

**PRE-OUTCOME FORMALIZATION CORRECTION (this revision):** all neighborhood
rules below are now stated explicitly in terms of the `S`/oriented-quantity
formalism (§2) so that "supports the declared sign" has one unambiguous
meaning for both `CONTINUATION` and `REVERSAL`, rather than an implicit
positive-only reading.

- **`q` robustness (hard, part of the candidate-for-freeze gate):** at
  least **2 of the 3** `q` cells adjacent in severity must be
  gate-passing (all of §17's oriented gates satisfied) for a given `H`
  before that `H` can be promoted (mirrors H04's relaxed "2 of 3 adjacent"
  rule, applied to `q` here since `q` is H05's severity dial, analogous to
  H04's depth bands).
- **`H` robustness (hard):** at least **2 adjacent** horizons must
  jointly be gate-passing for the same `q`.
- **`W` robustness (revised — directional-consistency requirement, still
  short of a hard 2-of-3 gate):** `W` remains a searched dimension
  (`{15, 30, 60}`, 3 values feeding the 45-cell surface), so a promoted
  cell that is a **fully isolated** `W` — i.e. no adjacent `W` shows even
  directional agreement — is a magic-lookback risk under the global
  225-cell search. The prior revision's purely "no severe contradiction"
  check was too permissive to rule this out, since a cell with no
  adjacent-`W` evidence either way (neither confirming nor contradicting)
  would still have passed. **PRE-OUTCOME DESIGN CORRECTION (this
  revision):** a promoted `(q, H)` cell does **not** require an adjacent
  `W` to clear full `MPIE`/`CONTROL_DELTA_MIN` (that remains a soft
  requirement, since `W` is a scale, not severity, dimension — H05's
  mechanism is not assumed to hold identically at every lookback length).
  It **does** now require that **at least one adjacent `W`** (for the
  same `q, H`, same claim sign, using the same fixed `S`) show all three
  of:
  1. `ORIENTED_PRIMARY > 0` (§2);
  2. `ORIENTED_MATCHED_DELTA > 0` (§2, §13) — direction only, not the full
     `MPIE` magnitude;
  3. `ORIENTED_STRUCTURAL_DELTA > 0` (§2, §9) — direction only, not the
     full `CONTROL_DELTA_MIN` magnitude;

  even if that adjacent `W` does not itself clear the numeric `MPIE` or
  `CONTROL_DELTA_MIN` thresholds. A cell with **no** adjacent `W`
  satisfying all three directional-consistency conditions is not eligible
  for
  `CANDIDATE_FOR_FREEZE` (§22 item 8, revised) — it may still be reported,
  but only as `INCONCLUSIVE` or `REJECTED_SPECIFIC_CLAIM`, never promoted
  on the strength of one isolated `W` alone. This is a real hard
  requirement, but a lighter one than requiring an adjacent `W` to fully
  pass every gate the way `q` and `H` must (§18 above), because `W` is
  still conceptually a scale dimension rather than a severity dimension —
  a genuine effect concentrated at one particular lookback length remains
  representable, but not from directional silence alone.

---

## 19. Direction symmetry

**PRE-OUTCOME FORMALIZATION CORRECTION (this revision):** stated
explicitly in terms of `S` (§2): for each `D` side computed separately
(`D=+1` buy imbalance, `D=-1` sell imbalance), `ORIENTED_PRIMARY = S *
candidate_mean > 0` must hold, using the **same fixed `S`** for both
sides. Concretely: `CONTINUATION` (`S=+1`) requires both the buy-side and
the sell-side candidate populations to support a positive `D`-normalized
future return (`D(T) * raw_outcome > 0` on average for each side);
`REVERSAL` (`S=-1`) requires both sides to support a negative
`D`-normalized future return. Both `D = +1` and `D = -1` must support the
**same** declared sign for a cell to be eligible for
`CANDIDATE_FOR_FREEZE` under that sign. A one-sided result (only one side
satisfying `ORIENTED_PRIMARY > 0`) is recorded as `POSTHOC_UNTESTED` for
symmetry purposes and cannot be promoted on its own.

---

## 20. Year stability and concentration

- Per-year breakdown across `2020–2024` (discovery/development pool
  years only). **PRE-OUTCOME FORMALIZATION CORRECTION (this revision):**
  stated explicitly using `S` (§2) — for each year `y`,
  `S * yearly_candidate_primary_mean(y) > 0` must hold in at least **4 of
  5** years for a cell to pass this item. Years and the 4/5 threshold are
  unchanged; only the sign-orientation of "qualifying" is now explicit.
  No shock-year or single-regime rescue is permitted (e.g., a cell that
  only passes because of concentrated 2020-03 or 2021 volatility is not
  promoted on year-count alone), and no yearly significance test is
  introduced.
- Concentration reporting: the share of a cell's total signed-outcome
  contribution attributable to its single most extreme candidate (and top
  decile of candidates) is reported per cell, to surface tail-driven
  results independent of the year-stability check.

---

## 21. Dependence and long-dependence diagnostic

- **Primary uncertainty:** UTC-week block bootstrap, master seed
  `20260905`, **2000 replicates**, applied to the candidate population's
  own primary mean (`candidate_mean`, §2) — unchanged by the §2/§17
  formalization correction; the `p025 > 0` (continuation) /
  `p975 < 0` (reversal) rule (§22 item 12) is equivalent to requiring the
  claim-oriented candidate-primary confidence interval to exclude zero,
  and is not itself re-expressed via `S` (it is already sign-specific by
  construction).
- **1w/2w/4w block-size sensitivity wired in from the first
  implementation commit** (not added later as a completion patch, per the
  H04 lesson): block construction is the same deterministic,
  candidate-sample-derived partition-into-consecutive-week-groups scheme
  used in H04 (`_block_groups_for_size` pattern), with the **terminal
  partial block retained**, never discarded or merged.
- Seed derivation: `block_size_weeks == 1` uses
  `np.random.default_rng(20260905)` directly; `block_size_weeks in {2, 4}`
  derive independent child streams via
  `np.random.default_rng(np.random.SeedSequence([20260905, block_size_weeks]))`
  — mirroring the H04 implementation-completion documented mapping exactly
  (chosen for the same reason: reproducing a legacy 1-week field exactly
  under the bare-seed convention).
- **Outcome-independent, cell-specific candidate-clustering diagnostic
  (renamed; PRE-OUTCOME FORMALIZATION CORRECTION, this revision):** the
  prior revision called this diagnostic "candidate-independent," which
  was internally inconsistent — it is computed from each cell's own
  candidate indicator series, which necessarily varies with `W` and `q`
  (and, through eligibility/refractory interaction, potentially `H`), so
  it cannot be independent of the candidate definition. What it *is*
  independent of is the real H05 **outcome** (it never touches
  `close`/return values — only whether a timestamp qualifies as a
  candidate) and it is computed identically, with no cell-specific tuning
  of its own procedure, for whichever cell is being evaluated. It is
  renamed accordingly: the **outcome-independent, cell-specific
  candidate-clustering diagnostic**. Definition and numeric parameters
  are otherwise unchanged from the prior revision: autocorrelation of the
  candidate indicator series (not the outcome) at fixed lags
  `{1, 2, 4, 8, 16, 32, 64}` days; the diagnostic reports the largest lag
  at which `|ACF| >= 0.20`. It informs interpretation of effective sample
  size and clustering — it does not itself gate promotion.

---

## 22. 14-item candidate-for-freeze checklist

**PRE-OUTCOME FORMALIZATION CORRECTION (this revision):** items 1–3 and
11 are rewritten below using the `S`/oriented-quantity formalism (§2) so
that no gate is expressed as a bare positive inequality that silently
assumes `CONTINUATION` — every gate below applies identically, by
construction, to whichever sign (`S=+1`/`S=-1`) is being evaluated. No
item is added beyond the existing 14; item 1 below makes explicit (not
new) the requirement that the raw primary effect itself must point the
declared way, which `MPIE`/control separation alone cannot substitute
for.

A cell (for a given sign, `q`, `H`) may only be marked
`CANDIDATE_FOR_FREEZE` if **all** of the following hold:

1. **Primary sign gate:** `ORIENTED_PRIMARY = S * candidate_mean > 0`
   (§2, §17). A cell whose own raw primary effect points the wrong way
   cannot be promoted by `MPIE`/control separation alone.
2. `MPIE` gate: `ORIENTED_MATCHED_DELTA = S * (candidate_mean -
   matched_mean) >= 0.10` (§2, §17; restores the established Batch01
   semantics — `MPIE` is a floor on practical separation from the
   matched-random baseline, not an undefined "standardized effect size").
3. `CONTROL_DELTA_MIN` gate: `ORIENTED_STRUCTURAL_DELTA = S *
   (candidate_mean - structural_mean) >= 0.05` (§2, §9, §17).
4. Structural-control standardization used candidate-weighted strata
   over the full five-dimensional stratification `(calendar_month, D,
   price_alignment, price_strength_bin, activity_bin)` (§9, revised this
   round), not an unstandardized full-population comparison and not a
   subset of these dimensions.
5. Unmatched-candidate share reported; if support is insufficient under
   the five-dimensional stratification, the cell is `INCONCLUSIVE` (§9,
   §23) rather than passing on a weakened/subset stratification.
6. `q` robustness: 2 of 3 adjacent `q` cells pass (§18).
7. `H` robustness: 2 adjacent `H` cells pass (§18).
8. `W` directional-consistency requirement (revised, §18): at least one
   adjacent `W` (same `q, H`, same `S`) has `ORIENTED_PRIMARY > 0`,
   `ORIENTED_MATCHED_DELTA > 0`, and `ORIENTED_STRUCTURAL_DELTA > 0`
   (direction only, not the full numeric gates) — a fully isolated `W`
   with no adjacent directional agreement cannot pass this item.
9. Direction symmetry: both `D=+1` and `D=-1` support the same sign
   (§19).
10. Year stability: `>= 4/5` years 2020–2024 support the same sign, no
    shock-year rescue (§20).
11. Negative control gate (exact, §14, §17): `ORIENTED_SHIFT_DELTA = S *
    (candidate_mean - shifted_mean) >= 0.05` (`CONTROL_DELTA_MIN`) — the
    `+6h`-shifted timing does not reproduce the candidate's own oriented
    effect to at least this margin.
12. Dependence-adjusted significance survives at 1w, 2w, and 4w block
    sizes, under the precise frozen criterion (§21 bootstrap procedure;
    revised definition below): for the candidate population's primary
    normalized signed-return mean (`NORM_TAKER_RET_H`, §15), computed
    under the declared claim sign, the UTC-week block-bootstrap interval
    at each of 1w/2w/4w must exclude zero in the declared direction —
    `p025 > 0` for continuation, `p975 < 0` for reversal (same D-signed
    outcome convention in both cases). This bootstrap interval is an
    estimate of uncertainty in the **candidate primary mean itself**; it
    is a distinct estimand from (a) the matched-random distribution's
    `p025/p50/p975` (§13, which characterizes the matched-random
    baseline's own spread, not the candidate's) and (b) the standardized
    structural-control delta (§9, a point comparison between two
    standardized populations). None of these three uncertainty/comparison
    outputs may be substituted for another when reporting or gating.
13. Price-return-confound control is applied as **two parts**: sign
    (`price_alignment`, §9) and magnitude (`price_strength_bin`, §10),
    both mandatory structural-match dimensions, tied explicitly to item
    4 — the standardized delta in item 3 already includes both, so a
    cell cannot pass item 3 while failing to show incremental separation
    over contemporaneous price direction and magnitude; there is no
    separate, weaker path to satisfy item 3 without also satisfying this
    requirement. Activity control (`activity_bin`, §11) is likewise
    mandatory and tied to item 4 on the same basis, supporting the "beyond
    ordinary market activity" clause of the research question (§1).
14. All eligibility, refractory, and boundary/horizon-embargo rules (§3,
    §5, §12) applied identically pre-outcome, with no candidate admitted
    via truncated horizon data.

---

## 23. Verdict vocabulary

Four labels, applied per sign:

- `CANDIDATE_FOR_FREEZE` — all 14 items in §22 satisfied.
- `REJECTED_SPECIFIC_CLAIM` — the specific frozen claim (this sign, this
  search surface, these controls) fails; does not preclude a different
  mechanism formulation in a future round.
- `INCONCLUSIVE` — data/robustness insufficient to conclude either way
  (e.g., too few eligible candidates after refractory + eligibility
  filtering, or dependence-adjusted uncertainty too wide to distinguish
  from noise).
- `POSTHOC_UNTESTED` — any result, pattern, or refinement that depends on
  having seen real H05 outcome data (including one-sided direction
  results per §19, or any parameter choice justified after real-outcome
  inspection). Cannot rescue a killed cell or sign, by construction.

---

## 24. Post-hoc rule (frozen, pre-outcome)

The following, and anything like them, are `POSTHOC_UNTESTED` if proposed
or adopted after real H05 outcomes are inspected, and cannot rescue a
kill:

1. Narrowing `q` to a value outside `{0.80, 0.90, 0.95}` because a
   particular value "looked better."
2. Removing, merging, or weakening any of the five mandatory
   structural-match dimensions (`calendar_month`, `D`, `price_alignment`,
   `price_strength_bin`, `activity_bin`, §9/§11) after seeing that the
   fully-stratified control produced a null, weak, or support-starved
   (`INCONCLUSIVE`) result.
3. Switching the primary feature from base-volume to quote-volume
   imbalance after seeing base-volume fail.
4. Changing the refractory rule (§12) to the rejected direction-aware
   alternative after seeing the frozen rule's results.
5. Redefining the "ordinary" control band away from `[0.60, 0.80)` after
   seeing that band's comparison outcome.
6. Selecting only the buy-side or only the sell-side result as "the
   finding" after seeing that the other side does not support the same
   sign.
7. Dropping or reweighting shock years after seeing that removing them
   changes the year-stability count.
8. Adopting a new horizon `H` outside `{15, 30, 60, 120, 240}`, or a new
   window `W` outside `{15, 30, 60}`, because the frozen set did not show
   a passing cell.
9. Redefining the exact-zero `SIGNED_PRICE_RET_W` treatment (`OPPOSED`,
   §9) or loosening the `W` directional-consistency requirement (§18,
   §22 item 8) after seeing which `W`/cells pass or fail under the frozen
   rules.
10. Treating a support-starved (`INCONCLUSIVE`, §9) cell as a passing
    `CANDIDATE_FOR_FREEZE` by narrowing the five-dimensional
    stratification specifically for that cell after outcomes are seen.
11. Redefining `S`'s mapping to `CONTINUATION`/`REVERSAL` (§2), swapping
    which of `MPIE`/`CONTROL_DELTA_MIN` applies to which oriented delta
    (§17), or reinterpreting any `ORIENTED_*` gate's inequality direction,
    after seeing which sign or cells pass or fail under the frozen
    formalism.

---

## 25. No-real-data-access constraint (this round)

This design round used only: repository governance documents, the
`CORE_BTC_BINANCE_V0` manifest schema (field names and allowed arithmetic
derivations — metadata, not row data), and prior H03/H04 design/audit
documents for implementation-lesson reuse. No real parquet was opened, no
2025 or 2026 data was inspected, and no real H05 candidate, control, or
outcome value was computed. If and when implementation proceeds, all
development-phase testing must use synthetic fixtures only, exactly as in
H03/H04's own pre-freeze implementation rounds.

---

## 26. Implementation notes (not yet built)

No prereg implementation exists yet. When implementation is separately
authorized, it must carry forward, from the first commit (not as a later
completion patch):

- membership-safe (set-based) pool exclusion for matched-random draws;
- real-timestamp (not panel-index) calendar/week keys throughout;
- 1w/2w/4w dependence sensitivity computed unconditionally per cell from
  the start;
- complete-horizon embargo enforced at data-eligibility time, not as a
  post-hoc filter;
- candidate-weighted deterministic stratified standardization for the
  structural control, matching §9 exactly;
- both signs (§2) implemented and evaluated together, with the
  anti-cherry-pick rule enforced in code (both checklists computed, both
  recorded, not merely one).

This document alone does not authorize writing that implementation; per
the task instructions, prereg implementation begins only if this design
review explicitly passes and the task is separately expanded.
