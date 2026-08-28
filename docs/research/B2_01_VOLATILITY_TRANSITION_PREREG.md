# B2-01 Volatility Transition — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-01_VOLATILITY_TRANSITION`  
**Primary family:** F3 — volatility-state dynamics  
**Inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Machine-readable freeze:** `docs/research/B2_01_VOLATILITY_TRANSITION_PREREG.json`  
**Dataset:** `CORE_BTC_BINANCE_V0` snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Real Batch02 outcomes opened by this unit:** NO  
**2025 validation opened:** NO  
**2026 OOS opened:** NO

This document defines the one allowed current-program B2-01 formulation before any
B2-01 development outcome is read.

A clean failure is a valid result. Failure closes B2-01 inside current V2; it does
not authorize a second compression/transition threshold search.

## 1. Research question

Does a causal, decision-time volatility-transition state improve prediction of
future realized-volatility behavior beyond a simpler predictor that knows only
the current volatility level?

The tested object is **transition dynamics conditional on current level**.

This is not:

- H01 compression -> expansion again;
- a directional LONG/SHORT signal;
- a PnL/backtest optimization;
- a search for the best compression threshold;
- a new indicator family.

## 2. Mechanism rationale

H01 showed the opposite of its preregistered compression->expansion claim:
unusually quiet windows tended to remain quieter than their local scale.

That result is compatible with volatility-state persistence, but it does not
answer whether the **direction of movement through volatility state** contains
incremental information once current level is already known.

Mechanism claim:

> At the same current realized-volatility level, a market whose volatility has
> been rising into that level is in a different state from one whose volatility
> has been falling into it. If transition dynamics are real, a causal
> transition-aware forecast should outperform a current-level-only forecast on
> the exact same decision records.

The preregistered expected ordering is persistence-like:

> higher recent transition state -> higher subsequent volatility target,
> conditional on current volatility level.

This sign is frozen before outcomes.

## 3. Information and identity at decision time T

Use accepted `CORE_BTC_BINANCE_V0` 1m canonical bars only.

At decision time `T`:

- every feature input must satisfy `available_at <= T`;
- no later backfill/revision may replace the value that was available by `T`;
- no 2025/2026 partition may be opened by the development runner;
- source dataset identity, 1m timeframe identity, and original aligned bucket
  timestamps remain part of provenance.

Decision records are UTC-epoch-aligned 15-minute boundaries.

Canonical B2-01 event identity must be deterministic and include at least:

`snapshot_id | decision_time_T | feature_window_W | transition_lag_D | horizon_H`.

Candidate and comparator predictions must retain the same canonical B2-01 event
ID. Equality of a generic decision timestamp alone is not sufficient.

## 4. Chronological boundary

| Window | Start inclusive | End exclusive | Use |
|---|---|---|---|
| Warmup/reference | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | features/history only |
| Development | 2020-02-01T00:00:00Z | 2025-01-01T00:00:00Z | authorized only after exact-SHA gate |
| Reserved validation | 2025-01-01T00:00:00Z | 2026-01-01T00:00:00Z | forbidden |
| Untouched OOS | 2026-01-01T00:00:00Z | current snapshot boundary | forbidden |

Every evaluated event must satisfy `T + 240m < 2025-01-01T00:00:00Z`.

## 5. Current volatility level

For each feature window `W`:

`r_t = ln(close_t / close_{t-1})`

`RV_W(T) = sqrt(sum(r_t^2))`

using only complete 1m returns available by `T`.

Frozen feature windows:

- `W = 60m`
- `W = 120m`

No other W belongs to B2-01.

For each W, define `LEVEL_W(T)` as the midrank percentile of `RV_W(T)`
against the same W on the aligned 15m grid in the preceding 30 calendar days,
excluding T.

Current-level state uses five fixed bins:

- L1: [0.00, 0.20)
- L2: [0.20, 0.40)
- L3: [0.40, 0.60)
- L4: [0.60, 0.80)
- L5: [0.80, 1.00]

The current-level-only comparator may use this state and nothing derived from
the transition feature.

## 6. Transition feature

Frozen transition lags:

- `D = 60m`
- `D = 120m`

For each W,D:

`RAW_TRANSITION_W_D(T) = ln(RV_W(T) / RV_W(T-D))`.

Both RV values must be strictly positive and available by T. If either is
unavailable or non-positive, the decision record is unavailable for that W,D;
no epsilon substitution or fallback is allowed.

Define `TRANSITION_PCTL_W_D(T)` as the midrank percentile of the raw transition
score against the same W,D transition score on the aligned 15m grid during the
preceding 30 calendar days, excluding T.

Transition state uses three fixed bins:

- DOWN: [0.00, 1/3)
- FLAT: [1/3, 2/3)
- UP: [2/3, 1.00]

No alternative cut points may be introduced after outcome access.

## 7. Future target

Frozen horizons:

- H = 30m
- H = 60m
- H = 120m
- H = 240m

For each H:

`FUTURE_RV_H(T)` = realized volatility of complete 1m returns with
`available_at in (T, T+H]`.

Define `PAST_MEDIAN_FUTURE_RV_H(T)` from aligned 15m historical decision
records in the preceding 30 calendar days whose complete H outcome was already
known by T.

Primary target:

`Y_H(T) = ln(FUTURE_RV_H(T) / PAST_MEDIAN_FUTURE_RV_H(T))`.

The denominator must be positive and known by T.

## 8. Causal walk-forward forecasts

For every event T and horizon H, use only historical training records from the
preceding 30 calendar days with `t + H <= T`.

No full-development fit is allowed.

### Baseline forecast

`BASE_PRED(T)` = median historical `Y_H` among training records with the same
current-level quintile L1...L5.

### Transition-aware candidate

`CAND_PRED(T)` = median historical `Y_H` among training records with the same:

- current-level quintile; and
- transition state DOWN/FLAT/UP.

Minimum historical state count:

- baseline cell: 80
- candidate joint cell: 40

If the candidate joint cell is immature, the B2-01 record is
`UNAVAILABLE_FOR_DECISION` for that W,D,H. The baseline is then evaluated on
the same final candidate-eligible support; it may not retain extra events.

No neighboring-bin fallback, smoothing fallback, another W/D, or full-sample
fallback is permitted.

## 9. Primary incremental metric

Per canonical event ID:

`BASE_AE = abs(Y_H - BASE_PRED)`

`CAND_AE = abs(Y_H - CAND_PRED)`

`AE_IMPROVEMENT = BASE_AE - CAND_AE`.

Positive values favor the transition-aware candidate.

Primary per-cell statistics:

- mean `AE_IMPROVEMENT`;
- median `AE_IMPROVEMENT`;
- relative MAE improvement:
  `1 - mean(CAND_AE) / mean(BASE_AE)`;
- UTC-week block bootstrap 95% interval for mean `AE_IMPROVEMENT`.

Squared-error improvement is diagnostic only and cannot rescue the primary MAE
gate.

## 10. Structural mechanism diagnostic

For each event, define baseline residual:

`LEVEL_RESIDUAL = Y_H - BASE_PRED`.

Within the exact same support, report standardized transition separation:

`TRANSITION_SEPARATION = median(LEVEL_RESIDUAL | UP) - median(LEVEL_RESIDUAL | DOWN)`.

The frozen expected sign is positive.

This diagnostic checks whether transition state adds ordered information beyond
the current-level baseline rather than merely reducing error accidentally.

## 11. Negative control

Within each calendar month × current-level quintile, deterministically permute
transition-state labels across eligible decision records.

Seed: `20260830`.

Use 100 replicates.

For each W,D,H, recompute the transition-aware historical forecast using the
permuted transition labels while preserving:

- decision records;
- current-level state;
- outcomes;
- calendar-month composition.

The true candidate must exceed the 95th percentile of placebo mean
`AE_IMPROVEMENT`.

Permutation is a control, not another selectable candidate.

## 12. Dependence and reporting

Use UTC-week block bootstrap:

- seed `20260831`;
- 2000 replicates;
- 95% interval.

Report for every primary cell:

- support N;
- unique UTC days/weeks/months;
- yearly 2020...2024 mean AE improvement;
- transition-state counts;
- current-level-bin counts;
- largest-month support share;
- top-5-month support share;
- mean/median AE improvement;
- relative MAE improvement;
- bootstrap interval;
- transition separation;
- placebo 95th percentile.

Do not treat overlapping horizons as iid.

## 13. Frozen primary search surface

Exactly:

- 2 W values ×
- 2 D values ×
- 4 H values

= **16 primary cells**.

There are no q thresholds, no extra volatility windows, no extra lags, and no
directional trading variants in B2-01.

## 14. Mandatory promotion gates

The machine-readable gate contract contains exactly these mandatory gates:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `transition_ordering`
6. `horizon_robustness`
7. `parameter_robustness`
8. `year_stability`

Missing, malformed, non-finite, unavailable, or errored mandatory gate input is
a non-pass.

### Per-cell gates

For a cell W,D,H:

- **primary_positive:** mean AE improvement > 0.
- **material_relative_mae:** relative MAE improvement >= 0.02.
- **bootstrap_positive:** 95% UTC-week bootstrap lower bound for mean
  AE improvement > 0.
- **placebo_separation:** true mean AE improvement > 95th percentile of the 100
  permuted-state placebo improvements.
- **transition_ordering:** `TRANSITION_SEPARATION > 0`.

### Neighborhood gates

A formulation may promote only if one predeclared neighborhood satisfies both:

- **horizon_robustness:** for one W,D pair, at least two adjacent H from
  [30,60,120,240] pass all five per-cell gates;
- **parameter_robustness:** the same adjacent-H pair also passes all five
  per-cell gates for at least one other W,D pair.

Thus a single magic W,D,H cell cannot promote.

### Year gate

For every cell used in the proposed promotion neighborhood:

- **year_stability:** mean AE improvement > 0 in at least 4 of the 5 yearly
  blocks 2020, 2021, 2022, 2023, 2024.

No year may be removed.

## 15. Verdict

Exactly one research verdict after the authorized development run:

### `B2_01_PROMOTED_CANDIDATE`

Only if all eight mandatory gate names evaluate literal `True` under the
frozen promotion contract and provenance records every gate input.

Promotion is G1 discovery only. It does not authorize 2025 validation, 2026 OOS,
or live trading.

### `B2_01_CLOSED_NO_PROMOTION`

If the complete frozen formulation does not satisfy the promotion contract.

Do not add another W, D, transition cut point, alternative sign, target, loss,
indicator, or child formulation inside current V2.

An integrity/data failure aborts the run without a research verdict; it must not
be converted to a favorable or unfavorable market result.

## 16. Implementation gate

Before any development outcome access, B2-01 must be implemented through V2
Research Harness v1.

Planned implementation identity:

- runner: `scripts/research/b2_01_volatility_transition.py`
- hypothesis library: `scripts/research/b2_01_volatility_transition_lib.py`
- tests: `tests/research/test_b2_01_volatility_transition.py`

Mandatory implementation controls:

- `verify_git_freeze` exact clean HEAD;
- `authorize_dataset_access` only for development partitions;
- `assert_no_lookahead` for all feature/training availability timestamps;
- exact canonical event IDs for candidate/comparator support;
- `paired_same_support_delta` or an equivalent harness-enforced exact-support
  proof for primary comparison;
- `PromotionGateContract` with the eight frozen gate names;
- `fail_closed_gate_conjunction`;
- immutable result/provenance artifact;
- hypothesis-specific adversarial tests for future-feature injection,
  candidate-only support shrinkage, event-ID forgery, historical-training
  leakage, and gate-input omission.

The implementation PR must pass CI, CodeRabbit, and independent adversarial
review on the exact final SHA before any real B2-01 development outcome is
authorized.
