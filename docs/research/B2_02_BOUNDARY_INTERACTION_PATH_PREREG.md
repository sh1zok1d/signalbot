# B2-02 Boundary Interaction Path — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-02_BOUNDARY_INTERACTION_PATH`  
**Primary family:** F1 — directional persistence / continuation  
**Frozen inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Dataset:** `CORE_BTC_BINANCE_V0`  
**Required snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Machine-readable freeze:** `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json`

This document freezes one finite B2-02 formulation before any B2-02 real
development outcome is read.

The V2 formulation inventory is already immutable because B2-01 has completed
its development outcome. This preregistration does not add a formulation. It
only instantiates the already-admitted B2-02 entry.

B2-01 results are not used to choose any B2-02 threshold, window, feature,
target, loss, or gate.

No B2-02 development outcome, 2025 validation outcome, or 2026 OOS outcome is
authorized by this document.

## 1. Research question

For an initial BTC range-boundary breach, does the **observable path of price
interaction with the breached boundary during the next fixed 30 minutes** add
stable information about later directional persistence beyond a simpler causal
description of:

- breach magnitude;
- pre-breach price state;
- pre-breach volatility state;
- breach side; and
- the H02-style event-bar close position itself?

The candidate is not "successful breakout continuation" and is not "failed
breakout mean reversion."

The object under test is the **post-breach path**.

## 2. Relationship to H02

Batch01 H02 tested the binary failed-close claim and returned `H02_KILL`.

H02 established:

- a small short-horizon boundary-timing effect existed in some cells;
- stronger overshoot did not strengthen that effect;
- failed closes did not add unique mean-reversion information;
- the successful-breakout structural control was stronger under H02's
  hypothetical reversion sign in 44/45 cells;
- that control did **not** establish successful-breakout continuation.

B2-02 must not reinterpret any of those observations as positive continuation
evidence.

To prevent B2-02 from winning merely by rediscovering H02's binary
failed/successful event-bar close label, the primary baseline explicitly
contains both:

1. a continuous signed event-bar close distance from the breached boundary; and
2. a binary event-bar close-beyond-boundary indicator.

The candidate must add information beyond that stronger nuisance control.

## 3. Chronology and forbidden windows

All timestamps are UTC.

| Window | Start inclusive | End exclusive | B2-02 use |
|---|---|---|---|
| Warmup/reference | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features/history only |
| Development | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | later separately authorized |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | **FORBIDDEN** |
| OOS | 2026-01-01T00:00:00Z onward | — | **FORBIDDEN** |

For an initial breach event ending at `t0`, the B2-02 decision time is:

`T = t0 + 30m`.

Every scored event, for every primary horizon, must satisfy:

`T + 240m < 2025-01-01T00:00:00Z`.

No 2025 or 2026 partition may be opened by preregistration or implementation
freeze.

## 4. Source timeframe and availability

Canonical source data are accepted 1m CORE bars.

B2-02 derives UTC-epoch-aligned 5m OHLC bars from those accepted 1m bars.

A derived 5m bar `[u-5m, u)` is available at `u` only when all source 1m
bars are available under the CORE `bar_end_exclusive` contract.

Every source bucket keeps:

- dataset/snapshot identity;
- source timeframe;
- original 1m timestamp identity;
- derived 5m aligned interval;
- availability timestamp.

No still-forming 5m bar is usable.

## 5. Initial boundary event

Range lookbacks are frozen:

`L ∈ {60m, 120m, 240m}`.

Let the initial breach bar be:

`B = [t0-5m, t0)`.

The prior range uses complete 5m bars strictly before B:

`[t0-5m-L, t0-5m)`.

Define:

- `R_high = max(high)`;
- `R_low = min(low)`;
- `prior_log_range = ln(R_high / R_low)`.

Require `prior_log_range > 0`.

The event bar must open inside the prior range.

### UPPER event

- `high_B > R_high`;
- `low_B >= R_low`;
- continuation direction `d = +1`.

### LOWER event

- `low_B < R_low`;
- `high_B <= R_high`;
- continuation direction `d = -1`.

If both boundaries are breached in B, exclude as
`AMBIGUOUS_DOUBLE_BREAK`.

If the event bar opens outside the prior range, exclude.

**There is no event-bar close requirement.**

Both H02-style failed closes and closes beyond the boundary remain in the same
B2-02 event population.

There is no overshoot threshold `s` in B2-02.

## 6. Breach magnitude and H02 close nuisance controls

Boundary is:

- `R_high` for UPPER;
- `R_low` for LOWER.

Frozen breach strength:

UPPER:

`BREACH_STRENGTH = ln(high_B / R_high) / prior_log_range`

LOWER:

`BREACH_STRENGTH = ln(R_low / low_B) / prior_log_range`

Require finite `BREACH_STRENGTH > 0`.

Frozen signed event-close distance:

`EVENT_CLOSE_DIST = d * ln(close_B / boundary) / prior_log_range`

Frozen H02 binary nuisance control:

`EVENT_CLOSE_BEYOND = 1` iff
`d * ln(close_B / boundary) > 0`, else `0`.

Thus a close back inside and a close beyond the boundary are explicitly
represented in the baseline rather than treated as B2-02 evidence.

## 7. Refractory clustering

Clustering is frozen separately for each L.

After accepting the earliest qualifying event at `t0`, ignore any later
qualifying initial breach of either side for the same L with event end in:

`(t0, t0 + 30m]`.

This prevents two accepted events for the same L from sharing any of the fixed
post-breach path bars.

Do not retune this refractory rule after outcomes.

Different L values remain distinct preregistered parameter cells.

## 8. Fixed post-breach observation path

The path observation duration is frozen:

`P = 30m`.

Decision time:

`T = t0 + P`.

The initial breach bar B is **not** part of the path descriptor.

Use exactly the six complete 5m bars after the breach bar:

- `[t0, t0+5m)`;
- ...
- `[T-5m, T)`.

Their availability timestamps are in `(t0, T]`.

The breached boundary is frozen from the original event and is not recomputed
during the path.

For each post-breach path bar j with close `C_j`:

`DIST_j = d * ln(C_j / boundary) / prior_log_range`.

Define the **single B2-02 path descriptor**:

`PATH_AREA = mean(DIST_j for the six post-breach bars)`.

Interpretation:

- larger positive values = greater time/depth beyond the breached boundary;
- negative values = greater integrated re-entry inside the original boundary.

No second path descriptor, retest threshold, wick metric, candle pattern,
residence threshold, efficiency measure, or alternative acceptance/rejection
definition is part of current B2-02.

## 9. Causal path state

The candidate uses one three-state path classification derived from PATH_AREA.

For each current event of a given L and side at decision time T, form a
reference set from qualifying post-refractory historical events that satisfy:

- same L;
- same side;
- historical decision time `T_e < T`;
- `T_e >= T - 180 calendar days`;
- finite PATH_AREA available by `T_e`.

The current event is excluded.

Minimum reference count:

`120`.

If fewer than 120 historical path records are available, the current event is
`UNAVAILABLE_FOR_DECISION`.

`PATH_PCTL(T)` is the deterministic midrank percentile of current PATH_AREA
against that historical reference set.

Each historical event's PATH_PCTL/PATH_STATE is computed exactly once as-of its
own decision time `T_e` using only records earlier than `T_e`. That stored
as-of-T_e state is the only path label allowed in later model training or
placebo permutations. Historical PATH_STATE may never be recomputed using a
later week-start S, later events, full-development quantiles, or backfilled
future information.

Frozen states:

- `LOW`: `[0, 1/3)`;
- `MID`: `[1/3, 2/3)`;
- `HIGH`: `[2/3, 1]`.

No full-development quantiles are permitted.

Expected mechanism ordering is frozen:

`HIGH > MID > LOW`

for subsequent continuation information after controlling for the baseline.

## 10. Pre-breach price/volatility controls

All controls below are known no later than t0.

Let `u0 = t0 - 5m`, the start of the initial breach bar.

### Pre-breach drift

`PRE_DRIFT_NORM = d * ln(close(u0) / close(u0-60m)) / prior_log_range`.

Both closes must be from fully known bars available by their boundaries.

### Pre-breach realized volatility

Use 1m log returns whose availability lies in:

`(u0-60m, u0]`.

`PRE_RV60 = sqrt(sum(r_1m^2))`.

Require finite `PRE_RV60 > 0`.

Normalize:

`PRE_RV_NORM = PRE_RV60 / prior_log_range`.

These controls exclude the initial breach bar.

## 11. Primary baseline and candidate models

B2-02 uses causal UTC-week walk-forward ordinary least squares.

For each L and outcome horizon H, models are refit at each UTC ISO-week start
`S` (Monday 00:00 UTC) and then held fixed for every B2-02 decision event in
that week.

Baseline training records must satisfy:

- historical B2-02 event decision time `T_e < S`;
- `T_e >= S - 365 calendar days`;
- `T_e + H <= S`;
- valid target;
- valid baseline features.

Candidate training records are the subset of those baseline-eligible records
that also possess a valid stored causal PATH_STATE computed as-of their own
`T_e`.

The comparator therefore may use strictly more historical training records than
the candidate when path-state history is immature. The baseline must never be
artificially weakened merely to match candidate training availability. Current
evaluation support remains exact same-support.

The 365 days are a maximum trailing lookback, not a requirement to possess a
full 365 days before any model can become available.

Minimum baseline training N:

`500`.

Minimum candidate training N:

`500`.

Additionally, candidate training requires at least `100` historical records in
each of LOW, MID, and HIGH.

If either weekly fit is unavailable, current-week scoring is unavailable for
both candidate and comparator.

### Shared baseline feature vector

The baseline contains:

1. intercept;
2. `BREACH_STRENGTH`;
3. `prior_log_range`;
4. `PRE_DRIFT_NORM`;
5. `PRE_RV_NORM`;
6. `EVENT_CLOSE_DIST`;
7. `EVENT_CLOSE_BEYOND`;
8. `SIDE_UPPER` (1 for UPPER, 0 for LOWER).

This is deliberately stronger than the inventory's minimum comparator because
it explicitly controls the H02 event-close classification.

### Candidate feature vector

The candidate contains every baseline feature plus two one-hot path-state
terms:

- `PATH_LOW`;
- `PATH_HIGH`;

with MID as the reference state.

No interaction terms, polynomial terms, alternate models, regularization
search, tree models, or feature selection are permitted.

### Fit semantics

Continuous baseline columns are standardized using means and standard
deviations computed only from the shared historical training set at S.

Binary columns and path-state dummy columns are not standardized.

Baseline continuous-column standardization is computed from the baseline's own
causal training set. Candidate continuous-column standardization is computed
from the candidate's own causal training subset. These choices are frozen and
may not be switched after outcomes.

Before constructing either design matrix, sort its training rows by canonical
`EVENT_ID|H`. The resulting order is deterministic and is also the order used
for any audit hashes. Floating-point fit order may not depend on filesystem,
DataFrame, dictionary, or parquet iteration order.

Fit by deterministic ordinary least squares using
`numpy.linalg.lstsq(..., rcond=None)`.

A non-finite design, zero standard deviation in a required continuous column,
rank-deficient required design, fit error, or non-finite coefficient makes the
weekly model unavailable and fails closed.

No fallback model is permitted.

## 12. Future target

Horizons are frozen:

`H ∈ {30m, 60m, 120m, 240m}`.

Continuation return:

`CONT_RET_H(T) = d * ln(close(T+H) / close(T))`.

`close(T)` is the last fully known 5m close at decision time T.

Define a causal volatility-free scale:

`PAST_MEDIAN_ABS_RET_H(T)`

as the median absolute H-horizon close return on UTC-aligned 5m boundaries in
the preceding 30 calendar days whose H outcome is fully known by T:

`t + H <= T`.

Require a finite positive scale.

Primary normalized target:

`Y_H(T) = CONT_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)`.

The target is never available to feature construction or model fitting before
its maturity boundary.

## 13. Exact evaluation support

For each L,H, a current event is scored only when:

- every frozen current-event feature is valid;
- PATH_STATE is available causally;
- both weekly models were successfully frozen before the event;
- the future target and its scale are valid;
- the event satisfies the global development boundary.

Candidate and baseline are evaluated on exactly the same scored event IDs.

The baseline may not retain extra scored events when the candidate is
unavailable.

No support selection may depend on the sign or magnitude of the future target.

## 14. Canonical identities

Canonical event identity must deterministically include at least:

- dataset ID;
- snapshot ID;
- source timeframe `5m`;
- L;
- side;
- prior-range start;
- prior-range end;
- initial breach-bar start;
- initial breach time `t0`;
- path decision time `T`.

Canonical scored record identity is:

`EVENT_ID | H`.

The exact underlying 1m source bucket identities and derived 5m aligned
timestamps remain provenance and may not be replaced by a generic decision
timestamp.

Candidate and comparator retain identical scored record IDs.

## 15. Primary incremental metric

For each scored event:

`BASE_AE = abs(Y_H - BASE_PRED)`

`CAND_AE = abs(Y_H - CAND_PRED)`

`AE_IMPROVEMENT = BASE_AE - CAND_AE`.

Positive favors the path-aware candidate.

Primary statistics per L,H:

- support N;
- mean AE improvement;
- median AE improvement;
- baseline MAE;
- candidate MAE;
- relative MAE improvement:
  `1 - candidate_MAE / baseline_MAE`;
- UTC-week block-bootstrap 95% CI for mean AE improvement.

Squared-error metrics may be reported diagnostically only and cannot rescue
B2-02.

## 16. Structural path diagnostic

Define:

`BASE_RESIDUAL = Y_H - BASE_PRED`.

For current scored events, compute median BASE_RESIDUAL separately for
LOW/MID/HIGH path states.

The frozen expected ordering is:

`median(LOW) < median(MID) < median(HIGH)`.

Also compute HIGH-minus-LOW separation separately for UPPER and LOWER events.

## 17. Causal placebo

Seed:

`20260901`.

Replicates:

`100`.

For each weekly model refit S, L, H, and replicate:

1. use exactly the candidate's causal historical training records;
2. stratify training records by:
   `calendar_month(T_e) × side × EVENT_CLOSE_BEYOND`;
3. sort each stratum by canonical EVENT_ID before RNG;
4. permute only historical PATH_STATE labels inside that stratum;
5. preserve all baseline features, targets, timestamps, and stratum
   composition;
6. derive RNG seed deterministically from:
   `20260901 | replicate | L | H | week_start_S | stratum_id`;
7. fit the placebo candidate with the permuted historical path labels;
8. evaluate on the exact same current-week scored events while leaving each
   current event's true decision-time PATH_STATE unchanged.

No label from a record outside the causal training set may enter the
permutation pool.

For each replicate, aggregate mean AE improvement over the exact real-candidate
cell support.

The real candidate must exceed the 95th percentile of the 100 placebo mean
improvements.

Permutation is a negative control, not another candidate.

## 18. Bootstrap

UTC-week block bootstrap.

Seed:

`20260902`.

Replicates:

`2000`.

CI:

95%.

Blocks preserve all events belonging to the same UTC ISO week.

## 19. Year and side stability

Fixed year blocks:

2020, 2021, 2022, 2023, 2024.

For each L,H report mean AE improvement separately by year.

No year may be removed.

Also report UPPER and LOWER separately for:

- support N;
- mean AE improvement;
- HIGH-minus-LOW residual separation.

B2-02 cannot be redefined as one-sided after outcomes.

## 20. Frozen search surface

Exactly:

3 L × 4 H = **12 primary cells**.

Frozen dimensions:

- L: 60m, 120m, 240m;
- path observation P: fixed 30m;
- H: 30m, 60m, 120m, 240m;
- one PATH_AREA descriptor;
- one LOW/MID/HIGH state construction;
- one baseline model specification;
- one candidate model specification.

There is:

- no overshoot threshold search;
- no path-window search;
- no second boundary definition;
- no second path descriptor;
- no BUY/SELL or UPPER/LOWER rescue;
- no alternative regression/model family;
- no trading-rule search.

## 21. Mandatory promotion gates

Required gate names are exactly:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `path_ordering`
6. `side_stability`
7. `horizon_robustness`
8. `parameter_robustness`
9. `year_stability`

Missing, unavailable, malformed, non-finite, errored, or non-literal-True
mandatory evidence is a non-pass.

### Per-cell gates

A cell passes `primary_positive` iff:

`mean(AE_IMPROVEMENT) > 0`.

A cell passes `material_relative_mae` iff:

`relative_MAE_improvement >= 0.02`.

A cell passes `bootstrap_positive` iff the 95% week-block bootstrap lower
bound for mean AE improvement is strictly greater than zero.

A cell passes `placebo_separation` iff real mean AE improvement is strictly
greater than the 95th percentile of the 100 causal-placebo improvements.

A cell passes `path_ordering` iff all three path states have scored support
and:

`median_residual_LOW < median_residual_MID < median_residual_HIGH`.

A cell passes `side_stability` iff, separately for both UPPER and LOWER:

- mean AE improvement is strictly positive; and
- HIGH-minus-LOW BASE_RESIDUAL separation is strictly positive.

If either side or either required path state is unavailable, side stability
fails closed.

### Robust-neighborhood gates

Adjacent H pairs are frozen:

- 30/60;
- 60/120;
- 120/240.

`horizon_robustness` requires at least one L for which both members of one
adjacent H pair pass all six per-cell gates.

`parameter_robustness` requires the **same adjacent H pair** to pass all six
per-cell gates for at least one additional distinct L.

Thus one magic L,H cell cannot promote.

### Year stability

A promotion neighborhood exists only if one frozen adjacent-H pair passes all
six per-cell gates for at least two distinct L values **and** every one of those
four cells has mean AE improvement strictly positive in at least 4 of the 5
fixed years 2020-2024.

If multiple neighborhoods satisfy the full contract, record the
lexicographically first neighborhood using the frozen adjacent-H order
`30/60`, `60/120`, `120/240`, then ascending L. Selection may not use effect
magnitude, p-value, support size, or any other outcome ranking.

No failed year may be removed.

## 22. Development verdict

Allowed market verdicts are exactly:

- `B2_02_PROMOTED_CANDIDATE`;
- `B2_02_CLOSED_NO_PROMOTION`.

An integrity, data, authorization, identity, no-lookahead, fit, or artifact
failure aborts the run without a market verdict.

Promotion is G1 discovery only.

Promotion does not authorize:

- 2025 validation;
- 2026 OOS;
- live deployment;
- parameter tuning.

If the full frozen promotion contract fails:

`B2-02 = CLOSED_NO_PROMOTION`.

No second acceptance/rejection definition, path window, path descriptor,
threshold family, or B2-02 child is admitted in current V2.

## 23. Implementation freeze requirements

Planned paths:

- runner:
  `scripts/research/b2_02_boundary_interaction.py`;
- library:
  `scripts/research/b2_02_boundary_interaction_lib.py`;
- tests:
  `tests/research/test_b2_02_boundary_interaction.py`.

Implementation must use Harness v1 controls including:

- `verify_git_freeze`;
- `authorize_dataset_access`;
- `assert_no_lookahead`;
- exact canonical event/record identities;
- exact candidate/comparator paired-support proof;
- `PromotionGateContract` using the nine frozen gate names;
- `fail_closed_gate_conjunction`;
- immutable new-file result persistence.

Implementation review must remain outcome-blind.

At minimum adversarial tests must attack:

1. using the initial breach bar inside PATH_AREA;
2. using any post-decision path bar;
3. recomputing the boundary after t0;
4. accepting an overlapping refractory event at `t0+30m`;
5. future events entering PATH_PCTL;
6. H02 binary close omitted or silently removed from the baseline;
7. candidate-only scored-support shrinkage;
8. model training records with `T_e+H>S`;
9. intraweek model refit after observing current-week outcomes;
10. placebo future-label injection;
11. event-ID collision/forgery;
12. single-cell promotion;
13. one-L-only promotion;
14. mismatched adjacent-H pairs across L;
15. one-sided UPPER/LOWER rescue;
16. missing/non-finite mandatory gate evidence;
17. wrong dataset/snapshot/2025/2026 access.

No real B2-02 outcomes are authorized until the exact implementation SHA passes
CI, CodeRabbit, independent adversarial review, is merged, and receives a
separate explicit development-outcome authorization.
