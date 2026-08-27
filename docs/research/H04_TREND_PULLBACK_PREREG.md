# H04 Trend Pullback → Continuation — Preregistration

**Status:** PREREGISTERED_EXPLORATORY
**Hypothesis ID:** `H04_TREND_PULLBACK_CONTINUATION`
**Machine-readable freeze:** `docs/research/H04_TREND_PULLBACK_PREREG.json`
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`

This document is frozen **before** any H04 development forward outcomes are
computed. A clean null is a successful research result. This is not a
trading strategy, entry/exit system, trend-following product, forecasting
product, R3 candidate, or validation result.

This is the fourth primary mechanism family in R2 Batch 01. H01
(Compression → Expansion), H02 (Failed Breakout → Mean Reversion) and H03
(Extreme Impulse → Continuation vs Exhaustion) are already closed
`REJECTED_SPECIFIC_CLAIM` (H03 additionally carries a post-freeze
classification `H03_RESULT_VALID_WITH_DESCRIPTIVE_ERRATUM`, which does not
reopen or reinterpret its verdict). H04 uses the same 2020–2024 discovery
lab as H01/H02/H03 — it is development/discovery only and is **not**
independent confirmation of anything.

Authoritative source: `docs/research/H04_DESIGN_FROZEN_DRAFT.md` as
produced by `docs/reviews/H04_DESIGN_REDTEAM.md` and corrected by
`docs/reviews/H04_DESIGN_MAINTAINER_ADDENDUM.md`. Where any earlier
red-team-intermediate wording conflicts with the maintainer addendum, the
maintainer addendum wins; this preregistration follows the maintainer-
corrected design throughout (in particular: the final structural control is
the `abs(RECENT_RATIO)<0.10` established-trend-plus-near-neutral-recent-move
baseline, **not** mirror extension and **not** the red-team's intermediate
"all established-trend moments irrespective of the P-window" baseline; and
depth-band robustness requires only two of three adjacent bands, not all
three).

## 0. Global adaptivity disclosure (completed, frozen, may not be weakened after outcomes)

- H04's mechanism class predates H01/H02/H03 outcomes: "trend pullback ->
  continuation" is explicitly listed in the original R2 roadmap
  (`docs/RESEARCH_ROADMAP.md` §R2), positioned before "extreme impulse ->
  continuation versus exhaustion" in the same original list, before any of
  H01/H02/H03 were executed.
- Several conventions are inherited as project-wide research conventions,
  not selected from H01/H02/H03 outcomes: the 15-minute decision grid and
  30-calendar-day local-reference concept; the 15/30/60/120/240-minute
  outcome ladder; 100 matched-random replicates; UTC-week block
  uncertainty; a `+6h` same-day timing control; `MPIE=0.10` /
  `CONTROL_DELTA_MIN=0.05` (frozen for H03 before H03's own outcomes, and
  reused here unchanged); the doubling-ladder convention for the primary
  lookback family; the three-value convention for every primary dial.
- **`L = {240, 480, 960}` minutes is new to H04** — not copied from H01's
  30/60/120m compression lookbacks, H02's 60/120/240m range lookbacks, or
  H03's 15/30/60m impulse windows.
- **The pullback observation window `P = 60m` is new to H04** — justified
  by an internal-consistency argument (it equals its own refractory
  length), not derived from any H03 outcome. 60 minutes also happens to be
  H03's refractory value; this is disclosed as a round-number/batch-style
  echo, not a claim of independence-by-coincidence nor evidence of
  outcome-driven copying.
- **The established-trend threshold `q=0.80` is new to H04, and its
  looseness relative to H01/H03's tail-severity families (0.10/0.20/0.30
  and 0.90/0.95/0.98) is disclosed as PARTIALLY influenced by batch
  experience**: H03's tightest cells (`q=0.98`) produced small, isolated,
  fragile populations that did not form a coherent neighborhood. This is
  disclosed, not hidden, and does not by itself block preregistration.
- **The pullback-depth construction (`d = {0.10, 0.25, 0.40}` used as
  exclusive band edges) is new to H04.** The count (three) is generic batch
  house style dating to H01, not H03-specific.
- **The structural control is the maintainer-corrected established-trend +
  near-neutral-recent-move baseline** (`abs(RECENT_RATIO)<0.10`). Two
  earlier formulations were considered and rejected pre-outcome: mirror
  extension (same-direction extension can itself be mean-reversion-prone,
  which would make pullback look artificially good for a reason unrelated
  to pullback) and an "all established-trend moments irrespective of the
  P-window" baseline (contaminated by containing other pullbacks/
  extensions, diluting the contrast). Neither alternative is used. No
  new numeric parameter was introduced for the final control — it reuses
  the already-frozen shallow-depth edge (0.10).
- Prior H01/H02/H03 experience with clustering/dependence, matched-random
  implementation correctness, and calendar-key correctness influenced the
  decision to make H04's refractory-independence caveat explicit, to
  require membership-based (not positional) matched-random pool exclusion
  from the start, and to require real-timestamp (never panel-index)
  calendar keys with an explicit regression test. This batch-internal
  influence is stated plainly, not hidden.
- H01's post-hoc observation (low-volatility persistence), H02's post-hoc
  observations (generic short-horizon boundary-breach bounce; lower/upper
  asymmetry), and H03's post-hoc observations (short-vs-long horizon
  asymmetry; DOWN-side exhaustion tendency; median-vs-mean tail asymmetry)
  did **not** define H04's mechanism, sign, or threshold ladder, and are
  not imported as H04 gates or features. All remain `POSTHOC_UNTESTED`.
- **Control formulations considered:** three structural-control
  formulations were considered in sequence for the central "isolate
  pullback beyond trend-state" question — mirror extension (rejected),
  "all established-trend moments" (rejected), and the final near-neutral
  `abs(RECENT_RATIO)<0.10` baseline (adopted). One negative control (`+6h`
  circular shift) was considered and adopted. All rejections occurred at
  the design-review stage, before any H04 data was touched.
- H04 is not independent confirmation. It uses the same 2020–2024
  discovery lab as H01/H02/H03.

## 1. Research question

When BTC has established a strong directional move over a longer backward
window (`L`) and then undergoes a partial counter-trend pullback that does
not erase the prior directional move, does subsequent price movement tend
to continue in the original trend direction? The specific claimed
incremental ingredient is **pullback after established trend**, not
generic trend/momentum persistence — a valid result must show that
trend-plus-pullback carries information beyond simply being in an
established trend state at all (§11 structural control).

## 2. Claim sign

**One preregistered candidate sign: CONTINUATION.** Exhaustion/reversal is
not an alternate H04 candidate. If a reversal pattern appears, H04's
specific continuation claim is rejected, and the reversal pattern is
recorded as `POSTHOC_UNTESTED` only.

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

An observation is eligible for horizon `H` only if its entire frozen future
`H` path resolves strictly before `2025-01-01T00:00:00Z`. No horizon
truncation. No future read across evidence-pool boundaries.

## 5. Decision grid

UTC-aligned 15-minute boundaries. `T` is the `bar_end_exclusive` of the
fully closed 15-minute bar ending at `T` — equivalently, `close(T)` is the
close of the canonical 15-minute interval `[T-15m, T)`. Only information
available at or before `T` is used. The still-forming bar is never used.

## 6. Temporal decomposition

`P = 60` minutes. For trend lookback `L`:

```
trend interval:    [T-P-L, T-P)
pullback interval: [T-P, T)
```

Disjoint intervals — the pullback window does not contribute to
measurement of the preceding trend leg. They share exactly one boundary
price, `close(T-P)` (trend leg's endpoint / pullback leg's start); this is
inherent to any "pullback measured from where the trend ended"
construction and is disclosed, not hidden, as a source of shared-pivot
noise coupling. Partially, not fully, absorbed by the structural (§11) and
negative (§14) controls, which are constructed under the same
pivot-sharing property.

## 7. Trend lookbacks

`L ∈ {240, 480, 960}` minutes (4h / 8h / 16h).

```
TREND_RET_L(T) = ln(close(T-P) / close(T-P-L))
```

Direction: `+1` if `> 0`, `-1` if `< 0`. Exact zero: excluded.
`ABS_TREND_L(T) = abs(TREND_RET_L(T))`.

## 8. Trend-strength reference and established-trend threshold

Reference: same `L`, same UTC 15m grid, preceding 30 calendar days,
strictly before `T` (current `T` excluded; no future observations; no
full-dataset or year-wide percentile). Frozen H01/H03-compatible midrank
percentile:

```
TREND_PCTL_L(T) = (count(ref < x) + 0.5*count(ref == x)) / N_ref,  x = ABS_TREND_L(T)
```

Established trend: `TREND_PCTL_L(T) >= 0.80`. Exactly one `q` — no `q`
search. This is a single a-priori gate, not a robustness-tested family;
this is disclosed as a real, acknowledged limitation (§0), not swept under
other diagnostics.

## 9. Reference-overlap disclosure (descriptive only, not a pass/fail gate)

- nominal `N_ref` (~2,880 for a complete 30-day 15m grid);
- `N_eff_L = floor(30*24*60 / L_minutes)`: **180** (`L=240`), **90**
  (`L=480`), **45** (`L=960`);
- q80 upper-tail count proxy: `0.20 * N_eff_L` (36 / 18 / 9 respectively).

For the `H`-horizon normalization reference (§13): `N_eff_H =
floor(30*24*60 / H_minutes)` (2880/1440/720/360/180 for
H=15/30/60/120/240). Descriptive transparency diagnostics only, not
estimated iid sample sizes; no arbitrary adequacy cutoff. `N_eff_L` at
`L=960` is small (45); disclosed explicitly and is one reason a single
isolated `L=960` cell cannot promote H04 alone (§20).

## 10. Pullback return and depth

```
SIGNED_PB_RET(T) = DIRECTION * ln(close(T) / close(T-P))
```

`< 0` = counter-trend movement (candidate pullback). `> 0` = same-direction
continuation/extension during `P` (not a pullback candidate; used only in
the structural control, §11).

For counter-trend observations (`SIGNED_PB_RET < 0`):

```
PULLBACK_DEPTH(T) = -SIGNED_PB_RET(T) / abs(TREND_RET_L(T))
```

Require `abs(TREND_RET_L(T))` finite and `> 0` (guaranteed in practice by
the `q>=0.80` gate; treated as an explicit ineligibility condition, never
floored). Require `0 < PULLBACK_DEPTH(T) < 1.0`. `depth >= 1.0` excludes
the observation from the primary candidate population (the pullback has
erased at least the complete magnitude of the preceding trend leg).

**Disclosed limitation:** `P=60m` is fixed across all `L`, so `P/L` ranges
from 25% (`L=240`) to 6.25% (`L=960`). The same nominal depth band
therefore describes a different fraction of the trend leg's own duration
at each `L`. "Coherent sign across `L`" (§20) must be interpreted with this
in mind: a genuinely `L`-specific result is an expected, acceptable
possible outcome, not necessarily evidence against a real, narrower-scope
mechanism.

## 11. Primary depth bands (exclusive) and structural control

**Primary depth construction — three mutually exclusive bands** (not
nested; a nested `d <= DEPTH < 1.0` family was considered and rejected
because it makes "coherent neighborhood" mechanically close to guaranteed
whenever any one band is strong):

```
shallow:  0.10 <= PULLBACK_DEPTH < 0.25
moderate: 0.25 <= PULLBACK_DEPTH < 0.40
deep:     0.40 <= PULLBACK_DEPTH < 1.00
```

Primary candidate rule for band `b`: `TREND_PCTL_L(T) >= 0.80 AND
SIGNED_PB_RET(T) < 0 AND PULLBACK_DEPTH(T) in band b`. No candidate belongs
to more than one primary depth band. `PULLBACK_DEPTH < 0.10` is excluded
from the primary search entirely (visible only in the diagnostic bands,
§12).

**Structural control (maintainer-final — established trend + near-neutral
recent move).** Two earlier formulations were rejected pre-outcome: mirror
extension (same-direction extension is itself plausibly mean-reversion-
prone, which could make pullback look artificially good for a reason
unrelated to pullback) and an "all established-trend moments irrespective
of the `P`-window" baseline (contaminated by containing other pullbacks/
extensions, diluting the contrast). The frozen control reuses the
already-defined ratio scale and the already-frozen shallow-depth edge
(0.10), introducing no new numeric parameter:

```
RECENT_RATIO(T) = SIGNED_PB_RET(T) / abs(TREND_RET_L(T))

structural control: TREND_PCTL_L(T) >= 0.80  AND  abs(RECENT_RATIO(T)) < 0.10
```

Interpretation: the same established-trend state, but the recent
60-minute window is small relative to the antecedent trend leg — neither a
primary H04 pullback (`PULLBACK_DEPTH >= 0.10`) nor a material
same-direction extension on the same ratio scale. Same `L`, UTC grid,
independent 60-minute refractory, future-outcome semantics. Matched where
possible on calendar month, trend direction, and trend-strength bin
(`[0.80,0.90)`, `[0.90,1.00]`); unmatched cases counted and reported
(matched `N`, unmatched `N`, unmatched share), never silently dropped. No
alternative structural control may be added after outcomes.

## 12. Fixed depth-band diagnostic (descriptive only)

```
[0.00, 0.10), [0.10, 0.25), [0.25, 0.40), [0.40, 0.60), [0.60, 1.00)
```

For each: `N`, mean `NORM_TREND_CONT_RET_H`, `P(continuation > 0)`.
Diagnostic only — no new threshold may be selected from these bins. Does
not conflict with §11's coarse exclusive gating partition.

## 13. Refractory, horizons, primary outcome, normalization

**Refractory:** 60 minutes. Within each `L × depth-band`: after accepting
one qualifying event at `T`, ignore further qualifying events of either
trend direction during `(T, T+60m)`; keep the earliest. Report raw
pre-refractory `N` and post-refractory `N`. Equals `P` (internally
consistent, non-outcome-derived); not selected because H03 showed a
favorable result at 60m. **Disclosed limitation:** does not establish
statistical independence across a multi-hour trend/pullback episode — see
§16/§17 diagnostics.

**Horizons:** `H ∈ {15, 30, 60, 120, 240}` minutes. Complete future `H`
path must resolve strictly before `2025-01-01T00:00:00Z`. No truncation.

**Primary outcome:**

```
RET_H(T) = ln(close(T+H) / close(T))
TREND_CONT_RET_H(T) = DIRECTION * RET_H(T)
```

`> 0` → continuation. `< 0` → reversal. Only positive continuation may
promote H04 (§2). Never flip the sign after outcomes.

**Normalization:**

```
PAST_MEDIAN_ABS_RET_H(T) = median of H-horizon absolute returns on the same
    UTC 15m grid, preceding 30 calendar days, using ONLY observations
    fully resolved strictly before T.

NORM_TREND_CONT_RET_H(T) = TREND_CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)
```

No full-development statistical floor is used (would violate as-of
semantics for earlier `T` by depending on later development-window scale
states). Denominator must be finite and strictly positive using only
trailing, fully-resolved pre-`T` history; if zero, non-finite, or
unavailable, the outcome is ineligible and counted explicitly. No
post-outcome floor or winsorization. Report the denominator distribution
(min, p01, p05, p25, p50) and the top-1% normalized-influence share as
fixed diagnostics.

## 14. MPIE, control materiality, matched-random baseline, negative control

```
MPIE (primary, matched-random gate): mean_pullback - mean_matched >= 0.10
CONTROL_DELTA_MIN = 0.05
Structural requirement: mean_pullback - mean_neutral_recent_trend >= 0.05
Timing requirement: mean_true - mean_shifted >= 0.05
```

Reused unchanged from the Batch01 convention frozen for H03 before H03's
own outcomes were known — reuse is the methodologically safer choice, not
an adaptivity risk. Raw mean `TREND_CONT_RET_H` in bps also reported
(descriptive; not PnL). `CONTROL_DELTA_MIN` may not be reinterpreted after
outcomes.

**Matched-random baseline:** for each `L × depth-band`: preserve
calendar-month event counts and UPTREND/DOWNTREND composition. Sampling
without replacement inside each replicate. Random pool excludes every raw
qualifying H04 candidate timestamp for that exact configuration before
refractory deduplication, via **membership exclusion** (`np.isin`-
equivalent, never positional fancy-indexing — H03's post-freeze audit
found exactly this bug class and it must not recur); does not exclude
surrounding periods/regimes. Assign each matched observation the paired
real candidate's trend direction. Seed `20260902`, used exactly once, never
re-rolled. 100 replicates. Report candidate mean, matched mean, candidate-
minus-matched, candidate positive share, matched positive share,
difference.

**Calendar residual diagnostic:** candidate and matched calendar keys must
use actual event/matched timestamps (`t_ms`), never panel indices — direct
required response to H03's post-freeze TVD erratum. `DOW TVD`, `DOM TVD` =
`0.5 * sum over category union of |p_i - q_i|`. Diagnostic only, not a
gate.

**Negative control:** `+6h` circular shift within the same UTC day,
preserving `L`, depth-band, and original trend direction. Do not redetect
trend/pullback at the shifted `T`. Require valid past/future coverage.
Report collision fraction with raw true H04 candidates for the same
`L × depth-band`; never remove collisions post hoc. Known limitation:
session/diurnal displacement. No alternative shift value after outcomes.

## 15. Primary search surface and metrics

`3 L × 3 depth-bands × 5 H = 45` primary cells. H04 is the fourth tested
mechanism family in R2 Batch 01 (H01=45, H02=45, H03=45 cells).

Per cell: `N`; mean/median `NORM_TREND_CONT_RET_H`; mean raw
`TREND_CONT_RET_H` in bps; `P(TREND_CONT_RET_H>0)`, `P(<0)`;
p05/p25/p75/p95. No Sharpe, no PnL, no leverage.

## 16. Dependence / concentration

Per configuration: raw `N`; post-refractory `N`; unique UTC days/weeks/
months; events by year; events by month; largest-month share; top-5-month
share; UPTREND share; DOWNTREND share; median event spacing.

## 17. Uncertainty and long-dependence diagnostic

Primary: UTC-week block bootstrap, seed `20260903`, 2000 replicates. If a
candidate-for-freeze reading is plausible: fixed 1w/2w/4w block
sensitivity, not selectable. **The week-block bootstrap must be wired
into per-cell output** — H03's implementation left this unwired despite
library support; that gap must not recur.

Long-dependence diagnostic (fixed, descriptive only): daily total absolute
15-minute log-returns, ACF at fixed lags `{1,2,4,8,16,32,64}` days:

```
L_dep = max{ L : |ACF(L)| >= 0.20 }
```

`<1 day` if none qualify; `>=64 days` if lag 64 qualifies. Largest
qualifying lag, not first crossing.

## 18. Year stability and direction symmetry

Report 2020–2024 separately. No shock-year exclusion, no deletion of any
named year, no regime rescue. Continuation sign should appear in at least
4/5 years for a promoted neighborhood.

H04 is symmetric: UPTREND-plus-pullback should continue UP; DOWNTREND-
plus-pullback should continue DOWN. Promotion requires both sides. If only
one side survives: symmetric claim `REJECTED_SPECIFIC_CLAIM`, one-sided
result `POSTHOC_UNTESTED` — cannot enter Batch 01 validation.

## 19. Parameter robustness

No best-cell promotion. Report `L={240,480,960}` and the three depth bands
separately. **Because the primary depth bands are mutually exclusive,
promotion requires only two adjacent depth bands** within a predeclared
`L` family to show the same positive primary sign with compatible control
evidence — the third band may be weaker/null; one isolated band cannot
promote H04. At least two adjacent horizons must support the primary sign.
Do not require all three `L` to agree (§10 disclosed `P/L` scale
inconsistency); one isolated `L`/depth-band/`H` cell cannot promote H04.

## 20. Candidate-for-freeze requirements (continuation only)

1. primary trend-direction close-return effect is positive;
2. candidate-minus-matched normalized mean meets or exceeds MPIE (0.10);
3. pullback separates from the structural control (§11) by
   `CONTROL_DELTA_MIN=0.05`;
4. the `+6h` negative control weakens the true effect by at least
   `CONTROL_DELTA_MIN=0.05`;
5. at least two adjacent exclusive depth bands within the promoted `L`
   family support the same positive primary sign with compatible control
   evidence (§19);
6. at least two adjacent horizons support the same sign on the primary
   metric (not MFE/MAE);
7. the sign appears in at least 4/5 development years;
8. UPTREND and DOWNTREND both support the symmetric claim;
9. no single month/regime dominates;
10. dependence-aware uncertainty (block bootstrap + §17 diagnostic) is
    compatible with a real effect;
11. the §17 long-dependence diagnostic does not reveal a misleading
    effective-N interpretation without explicit caution disclosed;
12. the primary outcome itself, not only MFE/MAE, supports the mechanism.

## 21. Development verdict (choose exactly one)

- `H04_CONTINUATION_CANDIDATE_FOR_FREEZE`
- `H04_INCONCLUSIVE`
- `H04_REJECTED_SPECIFIC_CLAIM`

No exhaustion candidate exists for H04 (§2). No validation is opened at
this point. No R3 optimization is started inside the development run.
After the development run: do not inspect 2025 or 2026. Stop before R3
regardless of verdict.

## 22. Implementation notes

Tooling: `scripts/research/h04_trend_pullback_continuation.py` + `_lib.py`.
Tests: `tests/research/test_h04_trend_pullback_continuation.py`. Not a
universal backtester. Does not modify H01/H02/H03 implementations or
production forecasting code.

Required implementation carry-forwards from the H03 post-freeze audit
(true from the first commit):

1. matched-random and structural-control pool exclusion use membership
   testing (`np.isin`-equivalent), never positional fancy-indexing;
2. all calendar-key diagnostics use actual event timestamps, never panel
   indices, with an explicit regression test;
3. the week-block bootstrap is wired into per-cell output from the start;
4. the synthetic-fixture-only test suite covers temporal-decomposition
   correctness, trend-percentile midrank/tie handling, the
   established-trend gate boundary, exclusive depth-band assignment
   (including boundary cases), the structural control's `RECENT_RATIO`
   construction, matched-random correctness, TVD exactness and the
   timestamp-vs-panel-id regression, `+6h` wrap/collision, MPIE/
   `CONTROL_DELTA_MIN` exact-boundary gates, long-dependence largest-
   qualifying-lag correctness (including a non-monotone-ACF fixture),
   symmetric-claim verdict logic, synthetic continuation/null/reversal
   mechanism detection, two-adjacent-band and two-adjacent-horizon
   promotion logic, and 2025/2026 partition/window rejection. This must
   not execute against real accepted parquet as part of this
   preregistration/implementation-freeze task.
