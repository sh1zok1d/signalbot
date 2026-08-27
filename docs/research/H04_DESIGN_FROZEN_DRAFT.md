# H04 Trend Pullback → Continuation — Corrected Design (Complete)

**Status:** DESIGN DRAFT — NOT PREREGISTERED. Not an implementation. Not a
market-outcome computation.
**Hypothesis ID:** `H04_TREND_PULLBACK_CONTINUATION`
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
**Corrects:** the raw design proposal reviewed in
`docs/reviews/H04_DESIGN_REDTEAM.md`. Where this document differs from that
raw proposal, this document is authoritative and the reasons are recorded
in the red-team review, not repeated in full here.

This is the fourth primary mechanism family in R2 Batch 01. H01
(Compression → Expansion), H02 (Failed Breakout → Mean Reversion) and H03
(Extreme Impulse → Continuation vs Exhaustion) are already closed
`REJECTED_SPECIFIC_CLAIM` (H03 additionally carries a post-freeze
classification of `H03_RESULT_VALID_WITH_DESCRIPTIVE_ERRATUM`, which does
not reopen or reinterpret its verdict). H04 uses the same 2020–2024
discovery lab — it is development/discovery only and is **not** independent
confirmation of anything.

## 0. Global adaptivity disclosure (frozen, may not be weakened after outcomes)

- H04's mechanism class predates H01/H02/H03 outcomes: "trend pullback ->
  continuation" is explicitly listed in the original R2 roadmap
  (`docs/RESEARCH_ROADMAP.md` §R2), positioned before "extreme impulse ->
  continuation versus exhaustion" in the same original list, before either
  was executed.
- Several conventions are inherited as project-wide research conventions,
  not selected from H01/H02/H03 outcomes: the 15-minute decision grid and
  30-calendar-day local-reference concept; the 15/30/60/120/240-minute
  outcome ladder; 100 matched-random replicates; UTC-week block
  uncertainty; a `+6h` same-day timing control; MPIE=0.10/
  `CONTROL_DELTA_MIN`=0.05 (frozen for H03 before H03's own outcomes, and
  reused here unchanged — reuse of an already-outcome-independent anchor is
  the safer choice, not a new adaptivity risk); the doubling-ladder
  convention for the primary lookback family; the three-value convention
  for every primary dial.
- **`L = {240, 480, 960}` minutes is new to H04** — not copied from H01's
  30/60/120m compression lookbacks, H02's 60/120/240m range lookbacks, or
  H03's 15/30/60m impulse windows. Freshly derived for a multi-hour
  established-trend timescale question.
- **The pullback observation window `P = 60m` is new to H04** — justified
  by an internal-consistency argument (it equals its own refractory
  length; see §16), not derived from any H03 outcome. It is disclosed that
  60 minutes also happens to be H03's refractory value; this is noted as a
  round-number/batch-style echo, not a claim of independence-by-coincidence
  nor evidence of outcome-driven copying.
- **The established-trend threshold `q=0.80` is new to H04, and its
  looseness relative to H01/H03's tail-severity families (0.10/0.20/0.30
  and 0.90/0.95/0.98) is disclosed as PARTIALLY influenced by batch
  experience**: H03's tightest cells (`q=0.98`) produced small, isolated,
  fragile populations that did not form a coherent neighborhood. Preferring
  a broader, state-like established-trend definition for H04 has an
  independent economic justification (a "trend" is a persistent state, not
  a rare burst, unlike H03's impulses) but the specific preference for
  looseness is disclosed as plausibly, partially shaped by that prior
  experience, per the batch-internal design-adaptation disclosure
  requirement (`docs/R2_SCREENING_PROTOCOL_V1.md` §5). This is disclosed,
  not hidden, and does not by itself block preregistration.
- **The pullback-depth construction `d = {0.10, 0.25, 0.40}` is new to
  H04.** The *count* (three values) is generic batch house style dating to
  H01, not H03-specific. The specific ratio construction and values are
  freshly derived; see §13–§14 for the corrected (exclusive-band) primary
  construction and the reasoning for why the originally proposed nested
  construction was rejected.
- **The structural control is the final maintainer-corrected established-
  trend + near-neutral recent-move baseline.** Mirror extension was rejected
  because extension can itself mean-revert; the red-team's intermediate
  "all trend moments" control was then rejected because it still contains
  other pullbacks/extensions and can contaminate the structural contrast.
  The final control freezes `abs(RECENT_RATIO)<0.10`, reusing the existing
  shallow-depth boundary rather than adding a new tuned number (§20).
- Prior H01/H02/H03 experience with clustering/dependence, matched-random
  implementation correctness, and calendar-key correctness influenced the
  decision to make H04's refractory-independence caveat explicit (§16), to
  require membership-based (not positional) matched-random pool exclusion
  from the start (§21, §31), and to require real-timestamp (never
  panel-index) calendar keys with an explicit regression test (§22). This
  batch-internal influence is stated plainly, not hidden.
- H01's post-hoc observation (low-volatility persistence), H02's post-hoc
  observations (generic short-horizon boundary-breach bounce; lower/upper
  asymmetry), and H03's post-hoc observations (short-vs-long horizon
  asymmetry; DOWN-side exhaustion tendency; median-vs-mean tail asymmetry)
  did **not** define H04's mechanism, sign, or threshold ladder, and are
  not imported as H04 gates or features. All remain `POSTHOC_UNTESTED`.
- **Control formulations considered:** two structural-control formulations
  were considered for the central "isolate pullback beyond trend-state"
  question (mirror extension; trend-only baseline). Mirror extension was
  rejected pre-outcome for the reason above and is not used. One negative
  control (`+6h` circular shift) was considered and adopted. No alternative
  formulation was tried and discarded after seeing any real H04 outcome —
  this rejection occurred entirely at the design-review stage, before any
  H04 data was touched.
- H04 is not independent confirmation. It uses the same 2020–2024
  discovery lab as H01/H02/H03.

## 1. Research question

When BTC has established a strong directional move over a longer backward
window (`L`) and then undergoes a partial counter-trend pullback that does
not erase the prior directional move, does subsequent price movement tend
to continue in the original trend direction?

The specific claimed incremental ingredient is **pullback after established
trend**, not generic trend/momentum persistence. A valid H04 result must
show that trend-plus-pullback carries information beyond simply being in
an established trend state at all (§20).

## 2. Claim sign

**One preregistered candidate sign: CONTINUATION.** Exhaustion/reversal is
not an alternate H04 candidate. If a reversal pattern appears in the
data, H04's specific continuation claim is rejected, and any observed
reversal pattern is recorded as `POSTHOC_UNTESTED` only — it cannot be
promoted, relabeled, or used to redefine H04 in this batch.

## 3. Dataset and information at T

Use accepted `CORE_BTC_BINANCE_V0` only, snapshot
`717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`. Fail
closed if the repository manifest's `snapshot_id`, `status`, or
`research_authorized` differ from what this document requires. The
development runner loads 2020–2024 canonical 1m monthly parquet only and
must not open 2025/2026 partitions. Price columns are canonical decimal
strings; parse with `float(Decimal(...))` before arithmetic, never
lexicographically.

## 4. Chronological windows (UTC)

| Window | Start inclusive | End exclusive | Outcome inspection |
|---|---|---|---|
| Warmup | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features only |
| Development / discovery | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | allowed |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | **forbidden** |
| Untouched OOS | 2026-01-01T00:00:00Z | 2026-08-26T00:00:00Z | **forbidden** |

An observation is eligible for horizon `H` only if its entire frozen
future `H` path resolves strictly before `2025-01-01T00:00:00Z`. No horizon
truncation. No future read across evidence-pool boundaries.

## 5. Decision grid

UTC-aligned 15-minute boundaries. `T` is the `bar_end_exclusive` of the
fully closed 15-minute bar ending at `T`. Only information available at or
before `T` is used. The still-forming bar is never used.

## 6. Temporal decomposition

Pullback observation window: `P = 60` minutes. For trend lookback `L`:

```
trend interval:    [T-P-L, T-P)
pullback interval:  [T-P, T)
```

The pullback window does not contribute to measurement of the preceding
trend leg — the intervals are disjoint. They share exactly one boundary
price, `close(T-P)` (the trend leg's endpoint and the pullback leg's
start); this is inherent to any "pullback measured from where the trend
ended" construction and is disclosed, not hidden: a single noisy pivot bar
can jointly inflate measured trend strength and manufacture the appearance
of a pullback. This risk is partially, not fully, absorbed by the
structural control (§20) and negative control (§23), which are constructed
under the same pivot-sharing property so a pure single-bar-noise effect
should not systematically differ between candidate and control.

## 7. Trend lookbacks

`L ∈ {240, 480, 960}` minutes (4h / 8h / 16h). Doubling ladder, consistent
with the batch's established scale-family convention. Not copied from
H01/H02/H03's own lookback values.

## 8. Prior trend return

```
TREND_RET_L(T) = ln(close(T-P) / close(T-P-L))
```

Direction: `+1` if `TREND_RET_L > 0`, `-1` if `< 0`. Exact zero: excluded.

```
ABS_TREND_L(T) = abs(TREND_RET_L(T))
```

## 9. Trend-strength reference

For each `L`: construct `ABS_TREND_L` on the same UTC 15m grid over the
preceding 30 calendar days, strictly before `T` (current `T` excluded; no
future observations; no full-dataset or year-wide percentile). Frozen
H01/H03-compatible midrank percentile:

```
TREND_PCTL_L(T) = (count(ref < x) + 0.5*count(ref == x)) / N_ref,  x = ABS_TREND_L(T)
```

## 10. Established-trend threshold

`TREND_PCTL_L(T) >= 0.80`. A single primary trend-strength cutoff — no
`q` family is searched. This is a single a-priori gate, not a
robustness-tested family; results are conditional on this specific
trend-establishment definition, and this is disclosed as a real,
acknowledged limitation (§0), not swept under other diagnostics. The
looseness of this specific value (relative to H01/H03's tail-severity
families) is disclosed as partially batch-adaptive in §0. No alternative
`q` may be substituted after outcomes.

## 11. Reference-overlap disclosure (descriptive only, not a pass/fail gate)

For the trend-strength percentile reference, report:

- nominal `N_ref` (~2,880 for a complete 30-day 15m grid);
- `N_eff_L = floor(30*24*60 / L_minutes)`: **180** for `L=240`, **90** for
  `L=480`, **45** for `L=960`;
- q80 upper-tail count proxy: `0.20 * N_eff_L` (36 / 18 / 9 respectively).

For the `H`-horizon normalization reference (§18), report separately:
`N_eff_H = floor(30*24*60 / H_minutes)` (2880/1440/720/360/180 for
H=15/30/60/120/240). These are conservative transparency diagnostics, not
estimated iid sample sizes; no arbitrary adequacy cutoff is used. `N_eff_L`
at `L=960` is small (45); this is disclosed explicitly, not hidden, and is
one reason a single isolated `L=960` cell cannot promote H04 alone (§28).

## 12. Pullback return

```
SIGNED_PB_RET(T) = DIRECTION * ln(close(T) / close(T-P))
```

`SIGNED_PB_RET < 0` = counter-trend movement (candidate pullback).
`SIGNED_PB_RET > 0` = same-direction continuation/extension during `P`
(not a pullback candidate; used only for the corrected structural control,
§20).

## 13. Pullback depth (ratio construction, with disclosed limitation)

For counter-trend observations (`SIGNED_PB_RET < 0`):

```
PULLBACK_DEPTH(T) = -SIGNED_PB_RET(T) / abs(TREND_RET_L(T))
```

Require `abs(TREND_RET_L(T))` finite and `> 0` (guaranteed in practice by
the `q>=0.80` gate; treated as an explicit ineligibility condition, never
floored, consistent with the project's no-floor normalization
philosophy). Require `0 < PULLBACK_DEPTH(T) < 1.0`. `depth >= 1.0` means
the pullback has erased at least the complete magnitude of the preceding
trend leg, so H04 no longer treats the prior trend as intact and the
observation is excluded from the primary candidate population.

**Disclosed limitation (not corrected — see red-team §4):** `P=60m` is
fixed across all `L`, so `P/L` ranges from 25% (`L=240`) to 6.25%
(`L=960`). The same nominal depth band therefore describes a different
fraction of the trend leg's own duration at each `L`. "Coherent sign across
`L`" (§28) must be interpreted with this in mind: a genuinely `L`-specific
result is an expected, acceptable possible outcome of this design, not
necessarily evidence against a real, narrower-scope mechanism.

## 14. Primary depth bands (corrected — exclusive, not nested)

**This section corrects the originally proposed nested threshold rule
`d <= PULLBACK_DEPTH < 1.0`.** Nesting made the "coherent neighborhood"
requirement mechanically close to guaranteed whenever any single band was
strong, because shallower cells fully contain deeper cells' candidates.
See `docs/reviews/H04_DESIGN_REDTEAM.md` §5 for the full reasoning.

**Frozen primary construction — three mutually exclusive depth bands:**

```
shallow:  0.10 <= PULLBACK_DEPTH < 0.25
moderate: 0.25 <= PULLBACK_DEPTH < 0.40
deep:     0.40 <= PULLBACK_DEPTH < 1.00
```

Primary candidate rule for band `b`:

```
TREND_PCTL_L(T) >= 0.80  AND  SIGNED_PB_RET(T) < 0  AND  PULLBACK_DEPTH(T) in band b
```

No candidate belongs to more than one primary depth band. Observations
with `PULLBACK_DEPTH < 0.10` are excluded from the primary search entirely
(too shallow to count as a deliberate pullback; visible only in the
diagnostic bands, §15). This is the sole frozen primary depth construction
— it replaces, and may not coexist with, the originally proposed nested
rule.

## 15. Fixed depth-band diagnostic (unchanged, descriptive only)

Independent of the primary construction (§14), report a finer, purely
descriptive 5-bin decomposition of the same `PULLBACK_DEPTH` scale:

```
[0.00, 0.10), [0.10, 0.25), [0.25, 0.40), [0.40, 0.60), [0.60, 1.00)
```

For each: `N`, mean `NORM_TREND_CONT_RET_H`, `P(continuation > 0)`.
Diagnostic only — no new threshold may be selected from these bins. A
strong-looking isolated bin is `POSTHOC_UNTESTED` only and cannot redefine
H04's primary depth bands. This diagnostic and the primary construction in
§14 do not conflict: §14 is the coarse, exclusive, gating partition; this
section is a finer, non-gating descriptive view of the same scale
(including the sub-0.10 tail the primary construction excludes).

## 16. Refractory

60 minutes. Within each `L × depth-band` configuration: after accepting one
qualifying event at `T`, ignore further qualifying events of either trend
direction during `(T, T+60m)`; keep the earliest. Report raw pre-refractory
`N` and post-refractory `N`. 60 minutes equals the pullback observation
window `P` (an internally-consistent, non-outcome-derived rationale) and
matches H03's already-validated refractory mechanics; it is **not** selected
because H03 happened to show a favorable result at 60m.

**Disclosed limitation:** 60m does not establish statistical independence
across a multi-hour trend/pullback episode — a `TREND_PCTL_L>=0.80` state
can persist for hours, and depth can oscillate in and out of a band as
price chops during the retracement, so multiple >60m-apart candidates can
still describe the same underlying macro-episode. This is not corrected by
changing the refractory value; it is the explicit reason the
dependence/concentration reporting (§26), the long-dependence ACF
diagnostic (§27), and the UTC-week block bootstrap (§27) exist and must be
inspected, not treated as formalities. Refractory is never retuned after
outcomes.

## 17. Forward horizons

`H ∈ {15, 30, 60, 120, 240}` minutes. Inherited project directional-
research convention; not selected from H03's observed short-vs-long
horizon behavior. Complete future `H` path must resolve strictly before
`2025-01-01T00:00:00Z`. No truncation.

## 18. Primary outcome and normalization

```
RET_H(T) = ln(close(T+H) / close(T))
TREND_CONT_RET_H(T) = DIRECTION * RET_H(T)
```

`TREND_CONT_RET_H > 0` → continuation of the established trend.
`TREND_CONT_RET_H < 0` → reversal against it. Only positive continuation
may promote H04 (§2). Never flip the sign after outcomes.

```
PAST_MEDIAN_ABS_RET_H(T) = median of H-horizon absolute returns on the same
    UTC 15m grid, over the preceding 30 calendar days, using ONLY
    observations fully resolved strictly before T.

NORM_TREND_CONT_RET_H(T) = TREND_CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

No full-development statistical floor is used (would violate as-of
semantics for earlier `T` by depending on later development-window scale
states, exactly as corrected for H03). The denominator must be finite and
strictly positive using only trailing, fully-resolved pre-`T` history; if
zero, non-finite, or unavailable, the outcome is ineligible and counted
explicitly. No post-outcome floor or winsorization.

For every `H`, report the denominator distribution (minimum, p01, p05,
p25, p50) and the share of total absolute normalized-outcome magnitude
contributed by the largest 1% of `|NORM_TREND_CONT_RET_H|` observations, as
fixed diagnostics only.

## 19. MPIE and control materiality (frozen numbers, reused unchanged)

```
MPIE (primary, matched-random gate):
  mean_pullback - mean_matched >= 0.10   normalized units

CONTROL_DELTA_MIN = 0.05

Structural-control requirement:
  mean_pullback - mean_trend_only >= 0.05

Timing-negative-control requirement:
  mean_true - mean_shifted >= 0.05
```

Reused unchanged from the Batch01 convention frozen for H03 before H03's
own outcomes were known. Reuse, unchanged, is the methodologically safer
choice here (an anchor never conditioned on H04 at all is a stronger form
of "anchored independent of this candidate's own sample" than a fresh
derivation would be), not an adaptivity risk (§0, §11 of the red-team
review). Raw mean `TREND_CONT_RET_H` in bps must also be reported
(descriptive; not PnL). `CONTROL_DELTA_MIN` may not be reinterpreted after
outcomes.

## 20. Structural control (maintainer-corrected — established trend + near-neutral recent move)

**The original mirror-extension proposal remains rejected.** A same-
direction extension can itself be an overextension / short-horizon mean-
reversion state and could make pullbacks look artificially good.

**The red-team's intermediate "all established-trend moments irrespective
of the P-window" control is also rejected before preregistration.** That
population can contain other H04 pullbacks (including candidate timestamps
from the other exclusive depth bands) and large same-direction extensions.
It therefore does not provide a clean "trend without the pullback
ingredient" comparison and can dilute the structural contrast.

Freeze one simpler structural control using the same already-defined ratio
scale and the already-frozen 0.10 shallow-pullback edge, introducing no new
numerical tuning parameter:

```
RECENT_RATIO(T) = SIGNED_PB_RET(T) / abs(TREND_RET_L(T))

structural control:
TREND_PCTL_L(T) >= 0.80
AND
abs(RECENT_RATIO(T)) < 0.10
```

Interpretation: the same established-trend state, but the recent 60-minute
window is small relative to the antecedent trend leg and therefore contains
neither a primary H04 pullback (`PULLBACK_DEPTH >= 0.10`) nor a material
same-direction extension on that same ratio scale.

Use the same `L`, UTC grid, independent 60-minute refractory, and future-
outcome semantics. Match where possible on calendar month, trend direction,
and trend-strength bin (`[0.80,0.90)`, `[0.90,1.00]`). Report structural
eligible `N`, matched `N`, unmatched `N`, and unmatched share; never
silently drop unmatched cases.

Primary structural delta:

```
mean_pullback - mean_neutral_recent_trend
```

A continuation candidate requires this delta to meet
`CONTROL_DELTA_MIN = 0.05` in the promoted preregistered neighborhood.

This control is intentionally simple. It does not claim that a near-neutral
recent window is economically identical to a pullback; it asks the narrower
incremental question H04 needs: does a material counter-trend pullback add
continuation information beyond an established trend whose immediately
recent move is not itself material on the frozen depth scale?

No alternative structural control may be added after outcomes.

## 21. Matched-random baseline

For each `L × depth-band`: preserve calendar-month event counts and
UPTREND/DOWNTREND direction composition. Sampling without replacement
inside each replicate. The random pool **excludes every raw qualifying H04
candidate timestamp** for that exact `L × depth-band` configuration before
refractory deduplication (via membership exclusion — `np.isin`-equivalent,
**not** positional fancy-indexing; H03's post-freeze audit found exactly
this class of bug and it must not recur, §31), but does **not** exclude
surrounding periods/regimes. Assign each matched observation the paired
real candidate's trend direction. Seed `20260902`, used exactly once, never
re-rolled. 100 replicates. Report candidate mean, matched mean, candidate-
minus-matched, candidate positive share, matched positive share, and their
difference. Replicates are not independent market evidence.

## 22. Calendar residual diagnostic

Candidate and matched calendar keys **must use actual event/matched
timestamps** (`t_ms`), never panel indices or array positions — this is a
direct, required response to H03's post-freeze TVD erratum
(`docs/reviews/H03_POSTFREEZE_RESULT_AUDIT.md` §4, where
`matched_random_bundle` passed panel indices into timestamp-formatting
functions). Freeze:

```
DOW TVD, DOM TVD = 0.5 * sum over category union of |p_i - q_i|
```

Diagnostic only, not a candidate gate. The future H04 implementation must
include synthetic tests for: identical distributions → 0; disjoint → 1;
missing category (union handling); same proportions at different `N`;
and an explicit timestamp-vs-panel-id regression test (mirroring H03's
`test_16c`/`test_20g`) proving the implementation cannot silently repeat
the H03 erratum.

## 23. Negative control

`+6` hour circular shift within the same UTC day, preserving `L`,
depth-band, and the original trend direction. Do not redetect trend/
pullback at the shifted `T`. Require valid past/future coverage at the
shifted `T`. Report the fraction of shifted timestamps that coincide with
a raw true H04 candidate timestamp for the same `L × depth-band`; do not
remove such collisions post hoc. Known limitation, disclosed and accepted:
session/diurnal displacement (matches the established `+6h` batch
convention). No alternative shift value after outcomes.

## 24. Primary search surface

`3 L × 3 depth-bands × 5 H = 45` primary cells. H04 is the fourth tested
mechanism family in R2 Batch 01 (H01 = 45, H02 = 45, H03 = 45 cells) —
never written as if one isolated cell were tested once.

## 25. Primary metrics

For all 45 cells: `N`; mean/median `NORM_TREND_CONT_RET_H`; mean raw
`TREND_CONT_RET_H` in bps; `P(TREND_CONT_RET_H>0)`,
`P(TREND_CONT_RET_H<0)`; p05/p25/p75/p95. No Sharpe, no PnL, no leverage.

## 26. Dependence / concentration

For every configuration report: raw `N`; post-refractory `N`; unique UTC
days/weeks/months; events by year; events by month; largest-month share;
top-5-month share; UPTREND share; DOWNTREND share; median event spacing.

## 27. Uncertainty and long-dependence diagnostic

Primary: UTC-week block bootstrap, seed `20260903`, 2000 replicates. If a
candidate-for-freeze reading is plausible: fixed sensitivity using 1-week,
2-week, 4-week blocks — fixed, not selectable. **Implementation
requirement (carried forward from the H03 audit): the week-block bootstrap
must actually be wired into per-cell output before any real H04 development
run** — H03's implementation left this unwired despite the library
supporting it; that gap must not recur here.

**Long-dependence diagnostic (fixed, non-selectable, descriptive only):**
on the daily series of total absolute 15-minute log-returns (candidate/
outcome-independent — the same series construction as H03), compute the
ACF at the fixed lag set `{1,2,4,8,16,32,64}` calendar days:

```
L_dep = max{ L : |ACF(L)| >= 0.20 }
```

Report `<1 day` if no lag qualifies, `>=64 days` if lag 64 qualifies. Uses
the largest qualifying lag, not the first crossing below 0.20.

## 28. Year stability, direction symmetry, parameter robustness

Report 2020–2024 separately. No shock-year exclusion, no deletion of any
named year, no regime rescue ("2020 was COVID", "2022 was bear market",
"2023 was weird" are not authorized escape hatches). For a proposed
candidate neighborhood, the continuation sign should appear in at least
4 of 5 years.

H04's claim is symmetric: an UPTREND-plus-pullback candidate should
continue UP; a DOWNTREND-plus-pullback candidate should continue DOWN.
Promotion requires both sides to independently support continuation
overall. If only one side survives, the symmetric claim is
`REJECTED_SPECIFIC_CLAIM` and the one-sided result is `POSTHOC_UNTESTED` —
it cannot enter Batch 01 validation.

No best-cell promotion. Report `L={240,480,960}` and the three depth bands
separately. Because the primary depth bands are now mutually exclusive,
promotion does **not** require all three bands to work. A promoted
neighborhood must contain at least **two adjacent depth bands** within a
predeclared `L` family with the same positive primary sign and compatible
control evidence; the third band may be weaker/null. One isolated depth
band cannot promote H04. This gives a genuine depth-local mechanism a fair
path to survive without recreating the pseudo-robustness of the rejected
nested thresholds.

At least two adjacent horizons must support the primary
`TREND_CONT_RET_H`/`NORM_TREND_CONT_RET_H` sign. Do not require all three
`L` to agree if that would unfairly reject a genuinely scale-specific but
still preregistered family — recall (§13) that the fixed `P=60m` window is
a different fraction of trend duration at each `L`. At the same time, one
isolated `L`/depth-band/`H` cell cannot promote H04.

## 29. Candidate-for-freeze requirements (either promotion, continuation only)

1. primary trend-direction close-return effect is positive;
2. candidate-minus-matched normalized mean meets or exceeds MPIE (0.10,
   §19), in a broad preregistered neighborhood;
3. pullback separates from the trend-only structural control (§20) by
   `CONTROL_DELTA_MIN=0.05`;
4. the `+6h` negative control weakens the true effect by at least
   `CONTROL_DELTA_MIN=0.05`;
5. at least two adjacent exclusive depth bands (§14) within the promoted
   `L` family support the same positive primary sign with compatible
   control evidence; one isolated band cannot promote, while the third band
   may be weaker/null;
6. at least two adjacent horizons support the same sign on the primary
   metric (not MFE/MAE);
7. the sign appears in at least 4/5 development years;
8. UPTREND and DOWNTREND both support the symmetric claim;
9. no single month/regime dominates;
10. dependence-aware uncertainty (block bootstrap + §27 diagnostic) is
    compatible with a real effect;
11. the §27 long-dependence diagnostic does not reveal a misleading
    effective-N interpretation without explicit caution disclosed;
12. the primary outcome itself, not only MFE/MAE, supports the mechanism.

## 30. Development verdict (choose exactly one)

- `H04_CONTINUATION_CANDIDATE_FOR_FREEZE`
- `H04_INCONCLUSIVE`
- `H04_REJECTED_SPECIFIC_CLAIM`

No exhaustion candidate exists for H04 (§2). No validation is opened at
this point. No R3 optimization is started inside the development run.
After the development run: do not inspect 2025 or 2026. Stop before R3
regardless of verdict.

## 31. Implementation notes (not yet implemented)

Tooling (when implemented, not in this task): `scripts/research/
h04_trend_pullback_continuation.py` + `_lib.py`. Tests:
`tests/research/test_h04_trend_pullback_continuation.py`. Not a universal
backtester. Does not modify H01/H02/H03/product code.

Required implementation carry-forwards from the H03 post-freeze audit
(must be true from the first commit, not retrofitted after a crash or a
real run):

1. matched-random and structural-control pool exclusion must use
   membership testing (`np.isin`-equivalent) against real panel/index
   values, never positional fancy-indexing assuming a contiguous `0..n-1`
   grid (§21);
2. all calendar-key diagnostics (DOW/DOM TVD) must be computed from actual
   event timestamps, never panel indices or array positions (§22), with an
   explicit regression test proving this;
3. the week-block bootstrap must be wired into per-cell output from the
   start, not left library-only and unwired (§27);
4. a synthetic-fixture-only test suite must cover: temporal-decomposition
   correctness (no lookahead across the shared pivot bar, §6); trend-
   percentile midrank/tie handling; the established-trend gate boundary;
   the corrected exclusive depth-band assignment (§14) including boundary
   cases at 0.10/0.25/0.40/1.00; the corrected trend-only structural
   control's timestamp-membership exclusion (§20); matched-random without-
   replacement sampling and month/direction preservation; TVD exactness and
   the timestamp-vs-panel-id regression; `+6h` wrap/collision; MPIE/
   `CONTROL_DELTA_MIN` exact-boundary gates; long-dependence
   largest-qualifying-lag correctness (including a non-monotone-ACF
   fixture); symmetric-claim verdict logic; synthetic continuation/null
   mechanism detection; and 2025/2026 partition/window rejection. This
   must not execute against real accepted parquet as part of any future
   preregistration/implementation-freeze task, mirroring H01/H02/H03's own
   staged discipline.
