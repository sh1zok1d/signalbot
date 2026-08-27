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
delta must survive (a) stratification on contemporaneous price return
strength (§10) and (b) a matched-random timing baseline (§13), not merely
a raw candidate-vs-population gap.

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

**Matching/standardization (candidate-weighted, deterministic, reusing
the H04 post-outcome-correction pattern):**

- Match strata: `(calendar_month, D, price_strength_bin)` where
  `price_strength_bin` is a 2-level split of `abs(PRICE_RET_W(T))` at its
  own trailing-30-day midrank percentile `0.50` (§10) — i.e. "weaker
  contemporaneous move" vs. "stronger contemporaneous move," computed with
  the same causal, trailing-only percentile machinery as
  `ABS_IMBALANCE_PCTL_W`.
- For each stratum present in the **candidate** population, control rows
  in the same stratum are weighted by the candidate row count in that
  stratum (candidate-weighted standardization); strata that appear only
  in the control population (never in the candidate population) receive
  **zero weight** and do not enter the standardized comparison.
- Candidates in a stratum with **no** matching control rows are retained
  and reported as **unmatched candidates** (count and share), not
  silently dropped from the candidate population — they simply do not
  contribute to the standardized-delta computation's denominator for that
  stratum.
- The gate compares the candidate population's outcome distribution to
  the **standardized** (candidate-weighted) control distribution — never
  to an unstandardized full-population baseline.

**Why not over-match:** the strata are limited to three dimensions
(month, direction, one coarse price-strength bin). A fourth stratifying
dimension (e.g. activity/volume, §11) is deliberately not added, to avoid
fragmenting the control population into strata too sparse to estimate
reliably — an explicit, disclosed trade-off, not an oversight.

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

Only magnitude is stratified (not sign): direction `D` already anchors
sign in the structural-control stratification, so a redundant sign-match
on `PRICE_RET_W` would double-count direction information already present
via `D` and needlessly shrink stratum sizes.

The design gate (§14) requires the candidate-vs-standardized-control delta
to remain material *after* this stratification — a raw, unstratified
candidate-vs-population gap that disappears once conditioned on
contemporaneous price-return strength would indicate H05 is merely
restating price momentum, not adding incremental information, and must
not pass.

---

## 11. Activity / volume confound — decision (not mandatory stratum)

**Decision (frozen):** trailing activity/volume level (e.g. trailing
30-day `TOTAL_W` percentile) is **not** added as a mandatory structural
control stratum. It is computed and reported as a **descriptive-only**
diagnostic (candidate vs. control trailing-activity-percentile summary
statistics), but never used to gate, threshold, or select cells.

**Rejected alternative:** adding activity/volume as a fourth match
stratum was considered and rejected, because it would further fragment
already-narrow month×D×price-strength strata, risking too many
zero-weighted or unmatched strata to produce a stable standardized
comparison. This is disclosed as an unresolved limitation (see false-
positive risk #3 in the final response) rather than silently omitted.

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
- Reported per cell: mean, median, `p025`, `p50`, `p975` of the matched
  outcome distribution, and `candidate_minus_matched` (candidate summary
  statistic minus the matched-random mean).

---

## 14. Negative control

`+6h` circular time shift of the outcome window, **preserving each
candidate's own `D`** (the shift moves which return window is attached to
a given candidate's flow-direction label, without altering direction
itself). Collision fraction (shifted timestamps that land on another
already-used candidate timestamp) is computed and reported per cell.

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

- `MPIE = 0.10` (Minimum Practically Important Effect, outcome-independent
  floor), reused unchanged from H01–H04.
- `CONTROL_DELTA_MIN = 0.05` ("materially" above the standardized
  structural control and the matched-random baseline), reused unchanged.

**Justification for reuse (not re-derivation):** both thresholds are
protocol-level floors fixed in `docs/R2_SCREENING_PROTOCOL_V1.md` /
`docs/EDGE_RESEARCH_PROTOCOL.md` before H01 began; they are not
re-optimized per hypothesis. Reusing them here, unchanged, is the
adaptivity-safe choice — inventing a new MPIE or `CONTROL_DELTA_MIN`
specifically for H05 without a documented protocol-level reason would
itself be an undisclosed adaptive choice.

---

## 18. Parameter robustness (frozen, pre-outcome)

- **`q` robustness (hard, part of the candidate-for-freeze gate):** at
  least **2 of the 3** `q` cells adjacent in severity must show a
  consistent-sign, gate-passing reading for a given `H` before that `H`
  can be promoted (mirrors H04's relaxed "2 of 3 adjacent" rule, applied
  to `q` here since `q` is H05's severity dial, analogous to H04's depth
  bands).
- **`H` robustness (hard):** at least **2 adjacent** horizons must
  jointly pass for the same `q`.
- **`W` robustness (soft, NOT a hard gate):** `W` is treated as a *scale*
  dimension (how much history feeds the imbalance measurement), not a
  *severity* dimension — analogous to how H04 treated its own `L` window
  as a soft dimension. The frozen check is only: no severe sign
  contradiction across adjacent `W` values (a passing cell at one `W`
  must not be directly contradicted by an opposite-sign, gate-passing
  reading at an adjacent `W` for the same `q, H`). `W` failing this soft
  check is reported as a caveat, not an automatic kill, and is not
  required to jointly pass 2-of-3 the way `q` and `H` are.

---

## 19. Direction symmetry

Both `D = +1` (buy imbalance) and `D = -1` (sell imbalance) must support
the **same** preregistered sign (continuation or reversal) for a cell to
be eligible for `CANDIDATE_FOR_FREEZE` under that sign. A one-sided result
(only buy-side or only sell-side passing) is recorded as
`POSTHOC_UNTESTED` for symmetry purposes and cannot be promoted on its
own.

---

## 20. Year stability and concentration

- Per-year breakdown across `2020–2024` (discovery/development pool
  years only). At least **4 of 5** years must show the same qualifying
  sign for a passing cell. No shock-year or single-regime rescue is
  permitted (e.g., a cell that only passes because of concentrated
  2020-03 or 2021 volatility is not promoted on year-count alone).
- Concentration reporting: the share of a cell's total signed-outcome
  contribution attributable to its single most extreme candidate (and top
  decile of candidates) is reported per cell, to surface tail-driven
  results independent of the year-stability check.

---

## 21. Dependence and long-dependence diagnostic

- **Primary uncertainty:** UTC-week block bootstrap, master seed
  `20260905`, **2000 replicates**.
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
- **Candidate-independent long-dependence diagnostic:** autocorrelation of
  the candidate indicator series (not the outcome) at fixed lags
  `{1, 2, 4, 8, 16, 32, 64}` days; the diagnostic reports the
  largest lag at which autocorrelation exceeds `0.20`. This diagnostic is
  computed identically regardless of which cell or sign is being
  evaluated (candidate-independent), and informs interpretation of
  effective sample size — it does not itself gate promotion.

---

## 22. 14-item candidate-for-freeze checklist

A cell (for a given sign, `q`, `H`) may only be marked
`CANDIDATE_FOR_FREEZE` if **all** of the following hold:

1. `MPIE` gate: standardized effect size `>= 0.10`.
2. `CONTROL_DELTA_MIN` gate: candidate-vs-standardized-structural-control
   delta `>= 0.05`.
3. Candidate-vs-matched-random delta also `>= CONTROL_DELTA_MIN`, and
   consistent in sign with item 2.
4. Structural-control standardization used candidate-weighted strata
   (§9), not an unstandardized full-population comparison.
5. Unmatched-candidate share reported and below a disclosed sanity bound
   (no numeric threshold newly invented here; reported for interpretive
   context alongside the gate).
6. `q` robustness: 2 of 3 adjacent `q` cells pass (§18).
7. `H` robustness: 2 adjacent `H` cells pass (§18).
8. `W` soft check: no severe cross-`W` sign contradiction (§18).
9. Direction symmetry: both `D=+1` and `D=-1` support the same sign
   (§19).
10. Year stability: `>= 4/5` years 2020–2024 support the same sign, no
    shock-year rescue (§20).
11. Negative control (`+6h`) does not reproduce the candidate effect.
12. Dependence-adjusted significance survives at 1w, 2w, and 4w block
    sizes (not merely the 1w bootstrap).
13. Price-return-confound stratification (§10) is applied, and is tied
    explicitly to item 4: the standardized delta in item 2 already
    includes the price-strength stratum, so a cell cannot pass item 2
    while failing to show incremental separation over contemporaneous
    momentum — there is no separate, weaker path to satisfy item 2
    without also satisfying the momentum-incrementality requirement.
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
2. Adding a fourth structural-control stratum (e.g. activity/volume, §11)
   after seeing that the 3-stratum control produced a null or weak
   result.
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
