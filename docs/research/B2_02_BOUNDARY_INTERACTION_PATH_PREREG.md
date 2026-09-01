# B2-02 Boundary Interaction Path — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-02_BOUNDARY_INTERACTION_PATH`  
**Primary family:** F1 — directional persistence / continuation  
**Inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Machine-readable freeze:** `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.json`  
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Real B2-02 outcomes opened by this unit:** NO  
**2025 validation opened:** NO  
**2026 OOS opened:** NO

This is an outcome-blind draft of the one allowed current-program B2-02 formulation. It does not authorize development outcomes.

## 1. Research question

Conditional on comparable boundary-breach magnitude and the same pre-breach market state, does the path observed immediately after a breach add stable information about subsequent continuation in the breach direction?

The tested object is the **post-breach interaction path**. This is not H02 failed-breakout mean reversion again, not a binary inside/outside-close rule, and not a search for a new breakout threshold.

## 2. H02 inheritance and novelty boundary

Reuse H02's canonical local-range geometry so the new formulation does not redefine what a boundary is:

- UTC-epoch-aligned 5-minute grid;
- prior-range lookbacks `L ∈ {60, 120, 240}m`;
- prior range formed from complete 5m bars strictly before the breach bar;
- 30-minute refractory clustering, keeping the earliest qualifying breach of either side.

B2-02 differs from H02 in exactly one core way: the breach bar does **not** need to close back inside or outside. All otherwise valid single-edge breaches belong to the same predeclared population. Candidate and baseline use exactly the same breaches.

## 3. Dataset, chronology and decision-time rule

Use accepted `CORE_BTC_BINANCE_V0` only. Canonical 5m bars are derived from accepted 1m history.

| Window | Start inclusive | End exclusive | Use |
|---|---|---|---|
| Warmup/reference | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features/history only |
| Development | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | authorized only after exact-SHA gate |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | forbidden |
| Untouched OOS | 2026-01-01T00:00:00Z | current snapshot boundary | forbidden |

Initial breach time is `T0`. The path-observation window is frozen at `P = 30m`. The actual prediction decision time is `T = T0 + 30m`.

The path consists of exactly six complete 5m bars:
`[T0,T0+5m), [T0+5m,T0+10m), ..., [T0+25m,T]`.
Their availability times are `T0+5m, ..., T`; equivalently, the path observations have `available_at in (T0,T]`. The breach bar itself is `[T0-5m,T0)` and is fully known at `T0`.

Every path input must satisfy `available_at <= T`. Every training outcome used for a forecast at T must already be known by T. Every evaluated event must satisfy `T + 240m < 2025-01-01T00:00:00Z`.

On the 5m grid the last legal initial breach is `T0 = 2024-12-31T19:25:00Z`, giving `T = 2024-12-31T19:55:00Z` and a last 240m target close at 23:55Z. `T0 = 19:30Z` is not legal because it would make `T+240m = 2025-01-01T00:00:00Z`, violating the strict end-exclusive rule.

## 4. Prior range and qualifying breach

For lookback `L`, event bar `B = [T0-5m, T0)` is the last complete 5m bar at initial breach time.

Reference interval: `[T0-5m-L, T0-5m)`.

`R_high = max(high)`  
`R_low = min(low)`  
`prior_log_range = ln(R_high / R_low)`, requiring `prior_log_range > 0`.

The breach bar must open inside the prior range.

UPPER breach:
- `high_B > R_high`
- `low_B >= R_low`
- continuation direction `d = +1`

LOWER breach:
- `low_B < R_low`
- `high_B <= R_high`
- continuation direction `d = -1`

If both edges are breached in the same event bar: `AMBIGUOUS_DOUBLE_BREAK` and exclude. No close-location condition is used.

Direction-normalized breach magnitude:

UPPER: `BREACH_MAG = ln(high_B / R_high) / prior_log_range`  
LOWER: `BREACH_MAG = ln(R_low / low_B) / prior_log_range`

Require `BREACH_MAG > 0`. No post-outcome thresholding of breach magnitude is allowed.

## 5. Same-support identity

Canonical B2-02 event identity must include at least:

`snapshot_id | source_timeframe=1m | derived_timeframe=5m | L | side | T0 | T | H`

The horizon `H` is part of the canonical scored-record identity so candidate/comparator pairing cannot silently drift across outcome horizons. Candidate and comparator retain the exact same canonical ID. The post-breach path descriptor may classify/score an event but may not change the qualifying breach population.

The 30m refractory rule is applied once to the qualifying breach population before candidate/baseline construction.

## 6. Frozen pre-breach baseline state

The simpler baseline uses only information available by `T0` plus breach magnitude.

For every event, construct three causal context states using trailing 30-calendar-day qualifying B2-02 breach references with the same `L`, pooling UPPER/LOWER after direction normalization. A reference event must have its breach information fully known strictly before the current `T0`; the current event is excluded.

Exact raw quantities:

1. **BREACH_MAG_STATE** — causal tertile of the already-defined `BREACH_MAG`.
2. **PRE_VOL_STATE** — causal tertile of
   `PRE_VOL = sqrt(sum(r_t^2))`, where `r_t = ln(close_t/close_{t-1})` over complete accepted 1m returns in the 60 minutes ending at `T0`, all with `available_at <= T0`.
3. **PRE_DRIFT_STATE** — causal tertile of
   `PRE_DRIFT = d * ln(close(T0) / close(T0-60m))`, using canonical aligned closes known by `T0`.

Each state uses canonical `rolling_midrank_percentile` tie semantics: midrank `(# less + 0.5 * # equal) / N`, mapped to tertiles [0,1/3), [1/3,2/3), [2/3,1]. If the required 30d reference set is empty, malformed, or any raw quantity is unavailable/non-finite, the event is `UNAVAILABLE_FOR_DECISION` for both candidate and baseline. No side-specific, neighboring-L, or full-history fallback is allowed.

No alternative state variables or cut points belong to B2-02.

## 7. Frozen post-breach path descriptor

Observe exactly the six complete 5m bars in `(T0, T]`.

Build four direction-normalized components. Let the breached boundary be `R_high` for UPPER and `R_low` for LOWER.

1. **RESIDENCE** — among the six path closes, the fraction strictly beyond the boundary:
   UPPER `close_i > R_high`; LOWER `close_i < R_low`.
2. **TERMINAL_EXTENSION** —
   UPPER: `ln(close(T)/R_high) / prior_log_range`;
   LOWER: `ln(R_low/close(T)) / prior_log_range`.
   Positive means the terminal close remains beyond the boundary.
3. **MAX_EXTENSION** — path extrema only:
   UPPER: `max_i ln(high_i/R_high) / prior_log_range`;
   LOWER: `max_i ln(R_low/low_i) / prior_log_range`,
   with `i` restricted to the six 5m path bars.
4. **PATH_EFFICIENCY** —
   `d * ln(close(T)/close(T0)) / sum_i abs(ln(close_i/close_{i-1}))`
   over the six 5m path returns. If the denominator is zero, PATH_EFFICIENCY is undefined and the scored record is unavailable for **both** candidate and baseline.

For each component, compute a causal midrank percentile against qualifying B2-02 breaches from the trailing 30 calendar days with the same `L`, pooling sides after direction normalization. A reference event is eligible only when its full 30m path was already known strictly before the current `T`; exclude the current event. Use canonical midrank tie semantics. Empty/malformed/non-finite reference sets make the current event jointly `UNAVAILABLE_FOR_DECISION`; no side-specific, neighboring-L, or full-history fallback is permitted.

`PATH_SCORE = mean(PCTL_RESIDENCE, PCTL_TERMINAL_EXTENSION, PCTL_MAX_EXTENSION, PCTL_PATH_EFFICIENCY)`.

Path state is frozen to tertiles:

- `LOW`: [0, 1/3)
- `MID`: [1/3, 2/3)
- `HIGH`: [2/3, 1]

No alternative weighting, component substitution, extra path metric, or second path-state definition is allowed after outcomes.

## 8. Future target

Frozen horizons after decision time T:

- `H = 30m`
- `H = 60m`
- `H = 120m`
- `H = 240m`

`DIR_RET_H(T) = d * ln(close(T+H) / close(T))`.

`PAST_MEDIAN_ABS_RET_H(T)` is the median absolute H-horizon close return on prior aligned 5m decision times in the preceding 30 calendar days whose H outcome was fully known by T.

Primary normalized target:

`Y_H(T) = DIR_RET_H(T) / PAST_MEDIAN_ABS_RET_H(T)`.

The denominator must be finite, positive, and known by T.

## 9. Causal walk-forward forecasts

Training set for an event at T and horizon H: preceding **90 calendar days** only, requiring every training record's `t + H <= T`. The 90d window is frozen before outcomes because the exact-state baseline has 27 tertile combinations and the candidate adds a third PATH_STATE; under the 30m refractory cap a 30d window cannot support the frozen 80/40 minima in a meaningful fraction of cells even in principle. This is a structural capacity choice, not a count tuned on B2-02 data.

Baseline forecast:
`BASE_PRED(T)` = median historical `Y_H` with the same:
- L;
- BREACH_MAG_STATE;
- PRE_VOL_STATE;
- PRE_DRIFT_STATE.

Candidate forecast:
`CAND_PRED(T)` = median historical `Y_H` with the same baseline context plus PATH_STATE.

Minimum history:
- baseline cell >= 80;
- candidate joint cell >= 40.

A scored record is admitted only by one **joint eligibility predicate**. The record is `UNAVAILABLE_FOR_DECISION` for both candidate and baseline if any required breach/context/path/target scale value is unavailable or non-finite, if PATH_EFFICIENCY is undefined, if any causal percentile reference is empty/invalid, or if either history minimum fails. Only records satisfying the complete joint predicate are scored, and candidate/baseline then carry identical canonical IDs including `H`.

No candidate-only shrinkage, neighboring-bin, side-only, horizon-only, full-sample, smoothing, or alternate-history fallback is allowed.

UPPER and LOWER events are direction-normalized into the same primary model, but side-specific results must be reported and cannot rescue a failed overall formulation.

## 10. Primary incremental metric

Per event:

`BASE_AE = abs(Y_H - BASE_PRED)`  
`CAND_AE = abs(Y_H - CAND_PRED)`  
`AE_IMPROVEMENT = BASE_AE - CAND_AE`.

Positive favors the path-aware candidate.

Per-cell statistics:
- N;
- mean/median AE improvement;
- relative MAE improvement `1 - mean(CAND_AE) / mean(BASE_AE)`;
- UTC-week block-bootstrap 95% interval for mean AE improvement.

## 11. Structural diagnostic

`BASE_RESIDUAL = Y_H - BASE_PRED`.

On the exact same support:

`PATH_SEPARATION = median(BASE_RESIDUAL | HIGH) - median(BASE_RESIDUAL | LOW)`.

Frozen expected sign: positive. A more acceptance-like path should correspond to more continuation after controlling for the baseline context.

## 12. Negative control

Use causal permutation of historical PATH_STATE labels only.

- seed: `20260902`
- replicates: 100
- within each forecast event's causal 90d training set, using only records with `t + H <= T`;
- stratify by `L × BREACH_MAG_STATE × PRE_VOL_STATE × PRE_DRIFT_STATE`;
- sort each stratum by canonical event ID before RNG;
- derive the RNG seed from exactly `20260902 | replicate_index | L | H | decision_time_T | stratum_id`;
- permute only historical PATH_STATE labels within that stratum;
- leave the evaluation event's own path state unchanged;
- never use a future record merely to preserve eventual calendar composition.

The true candidate's mean AE improvement must exceed the 95th percentile of placebo improvements.

## 13. Dependence and reporting

UTC-week block bootstrap:
- seed `20260903`
- 2000 replicates
- 95% interval.

Report every primary cell:
- support N;
- unique UTC days/weeks/months;
- yearly 2020...2024 mean AE improvement;
- UPPER/LOWER counts and side-specific mean improvement;
- baseline-state counts;
- PATH_STATE counts;
- largest-month and top-5-month support share;
- mean/median AE improvement;
- relative MAE improvement;
- bootstrap interval;
- PATH_SEPARATION;
- placebo 95th percentile.

## 14. Frozen search surface

Exactly:

- 3 prior-range lookbacks L ×
- 1 path observation window P=30m ×
- 4 future horizons H

= **12 primary cells**.

There are no breach-strength thresholds, no binary failed/successful-breakout child, no second path window, no alternate path-score weights, and no one-sided rescue.

## 15. Mandatory promotion gates

Required gate names:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `path_ordering`
6. `horizon_robustness`
7. `parameter_robustness`
8. `year_stability`

Per-cell:
- mean AE improvement > 0;
- relative MAE improvement >= 0.02;
- bootstrap lower bound > 0;
- true improvement > placebo 95th percentile;
- `PATH_SEPARATION > 0`.

Neighborhood:
- horizon robustness: for one L, at least two adjacent H in [30,60,120,240] pass all five per-cell gates;
- parameter robustness: the same adjacent-H pair also passes for at least one other L.

Year stability:
- every cell in the proposed promotion neighborhood has positive mean AE improvement in at least 4 of 5 years 2020...2024.

Missing/malformed/non-finite mandatory inputs are non-passes.

## 16. Verdict

Exactly one market verdict after an authorized development run:

### `B2_02_PROMOTED_CANDIDATE`

Only if the full frozen promotion contract passes. Promotion does not authorize 2025 validation, 2026 OOS, or live use.

### `B2_02_CLOSED_NO_PROMOTION`

If the frozen path formulation does not satisfy the promotion contract.

An integrity/data failure aborts without a market verdict. Failure does not authorize another acceptance/rejection definition inside current V2.

## 17. Implementation gate

Planned paths:

- runner: `scripts/research/b2_02_boundary_interaction_path.py`
- library: `scripts/research/b2_02_boundary_interaction_path_lib.py`
- tests: `tests/research/test_b2_02_boundary_interaction_path.py`

Before development outcomes:
- use the canonical Batch02 contracts merged by PR #93;
- exact clean Git identity;
- authorized development-only dataset;
- exact same-support event IDs;
- explicit no-lookahead checks for path/training availability;
- immutable canonical persistence/provenance;
- hypothesis-specific regression tests;
- exact-SHA CI + CodeRabbit + one independent completion review.

`outcome_access_authorized = false` until that sequence is complete.
