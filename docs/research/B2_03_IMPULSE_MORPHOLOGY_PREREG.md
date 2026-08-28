# B2-03 Impulse Morphology — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-03_IMPULSE_MORPHOLOGY`  
**Primary family:** F1 — directional persistence / continuation  
**Frozen inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Dataset:** `CORE_BTC_BINANCE_V0`  
**Required snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Machine-readable freeze:** `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.json`

This preregistration instantiates the already-frozen B2-03 inventory entry. It
does not add a formulation and does not authorize any real B2-03 outcome read.

## 1. Research question

Conditional on the same signed displacement magnitude and current realized
volatility, does the **distribution of directional progress inside the completed
move** add stable information about subsequent continuation?

H03 tested impulse extremeness/magnitude. B2-03 does not retune extremeness and
contains no q/tail threshold.

## 2. Chronology and source identity

Use accepted `CORE_BTC_BINANCE_V0` only. Canonical source is 1m; the morphology
descriptor is computed from UTC-epoch-aligned complete 5m bars. All underlying
1m identities, derived 5m aligned timestamps, and availability timestamps remain
provenance.

Warmup/reference: 2020-01-01 to 2020-02-01 UTC. Development: 2020-02-01
inclusive to 2025-01-01 exclusive. 2025 validation and 2026 OOS are forbidden.

Decision time T is a UTC-epoch-aligned 15m boundary. Every source bar entering a
feature must have `available_at <= T`. Every scored event must satisfy
`T+240m < 2025-01-01T00:00:00Z`.

## 3. Frozen morphology windows

`W ∈ {30m, 60m, 120m}`.

Morphology interval: `[T-W,T)`.

Let the complete 5m log returns inside W be `r_1...r_n`, where
`n=W/5m`.

`NET_RET = sum(r_i) = ln(close(T)/close(T-W))`.

Exact `NET_RET=0` is unavailable. Direction:

`d = sign(NET_RET)`.

`ABS_DISP = abs(NET_RET)`.

Current realized volatility uses accepted 1m returns entirely inside
`[T-W,T)`:

`RV_W = sqrt(sum(r_1m^2))`.

Require finite `RV_W>0`.

No displacement threshold, extremeness percentile, or candidate event filter is
used. All otherwise eligible aligned T records enter the formulation.

## 4. Single morphology descriptor

For each complete 5m return in W define directional progress:

`p_i = max(d * r_i, 0)`.

Require `sum(p_i)>0`.

Define:

`PROGRESS_CONCENTRATION = sum(p_i^2) / (sum(p_i)^2)`.

Define the single frozen morphology descriptor:

`DISTRIBUTED_PROGRESS = 1 - PROGRESS_CONCENTRATION`.

Higher values mean directional progress was distributed across more of the
completed path; lower values mean progress was concentrated into fewer/sharper
submoves.

This is the only B2-03 morphology descriptor. No path-efficiency,
counter-move-depth, candle-pattern, wick, impulse-threshold, or alternative
descriptor may be substituted after outcomes.

## 5. Causal morphology state

For each W and move side at T, reference only historical records with:

- same W;
- same side;
- historical decision `T_e<T`;
- `T_e>=T-180 calendar days`;
- finite DISTRIBUTED_PROGRESS available by `T_e`.

Minimum reference N = 120.

Current record is excluded. Use deterministic midrank percentile and freeze:

- LOW: [0,1/3)
- MID: [1/3,2/3)
- HIGH: [2/3,1]

Each historical morphology state is computed exactly once as-of its own
`T_e` and stored. It may never be recomputed using later records, a later
week, or full-development quantiles.

Frozen expected ordering after baseline control:

`HIGH > MID > LOW`

for continuation information.

## 6. Simpler causal baseline

B2-03 uses causal weekly walk-forward OLS. For each W,H, refit at UTC ISO-week
start S and hold fixed for the week.

Baseline features:

1. intercept;
2. `ABS_DISP`;
3. `RV_W`;
4. `ABS_DISP / RV_W`;
5. `SIDE_UP` (1 when NET_RET>0).

The candidate adds only:

- `MORPH_LOW`;
- `MORPH_HIGH`;

with MID as reference.

Thus B2-03 must beat displacement magnitude + volatility on the same current
records. It cannot win from H03-style magnitude/extremeness alone.

Baseline training uses all mature baseline-valid rows in `[S-365d,S)`.
Candidate training is the subset with valid stored morphology state. Both
require `T_e+H<=S`.

Minimum baseline training N=500. Minimum candidate training N=500 and at least
100 candidate-training records in each LOW/MID/HIGH state. If either fit is
unavailable, scoring is unavailable for both models.

Sort training rows by canonical `RECORD_ID` before standardization and OLS.
Continuous columns are standardized from each model's own causal training set;
binary/state dummies are not standardized. Fit only with
`numpy.linalg.lstsq(...,rcond=None)`; rank deficiency, nonfinite input,
zero required standard deviation, or fit error fails closed. No fallback model.

## 7. Future target

`H ∈ {30m,60m,120m,240m}`.

`CONT_RET_H(T)=d*ln(close(T+H)/close(T))`.

Scale by the causal trailing-30-calendar-day median absolute H-return on
UTC-aligned 15m boundaries whose outcomes satisfy `t+H<=T`.

`Y_H = CONT_RET_H / PAST_MEDIAN_ABS_RET_H`.

Scale must be finite and positive.

## 8. Same support and identities

Current scoring requires valid current features/state, both frozen weekly fits,
valid future target/scale, and development-boundary compliance.

Candidate and comparator score exactly the same `RECORD_ID` set. The
comparator may use more historical training rows, but may not retain extra
current scored events.

Canonical event identity includes dataset, snapshot, source/derived timeframe,
W, morphology interval start/end, side, and decision T. Scored record identity
is `EVENT_ID|H`. Generic T alone is insufficient.

## 9. Primary metric

`BASE_AE=abs(Y_H-BASE_PRED)`  
`CAND_AE=abs(Y_H-CAND_PRED)`  
`AE_IMPROVEMENT=BASE_AE-CAND_AE`.

Report support N, mean/median improvement, baseline/candidate MAE, relative MAE
improvement, and UTC-week bootstrap CI.

Materiality threshold is frozen at relative MAE improvement >= 2%.

## 10. Structural diagnostic

`BASE_RESIDUAL=Y_H-BASE_PRED`.

Report medians by LOW/MID/HIGH morphology state. Expected ordering:

`median_LOW < median_MID < median_HIGH`.

Also report HIGH-minus-LOW residual separation separately for UP and DOWN moves.

## 11. Causal placebo

Seed `20260903`, 100 replicates.

At each weekly fit, use only the real candidate's causal training rows. Build
causal nuisance bins stored as-of each record's own T_e:

- displacement-magnitude quintile from trailing 180d same W/side history;
- RV quintile from trailing 180d same W/side history.

Strata:

`calendar_month(T_e) × side × displacement_quintile × rv_quintile`.

Sort each stratum by canonical EVENT_ID, then permute only historical morphology
state labels. Seed:

`20260903 | replicate | W | H | week_start_S | stratum_id`.

Leave current-week true morphology states unchanged. Evaluate placebo models on
the exact real-candidate support. Real candidate must exceed placebo p95 mean
AE improvement.

## 12. Bootstrap and stability

UTC-week block bootstrap: seed `20260904`, 2000 replicates, 95% CI.

Fixed years: 2020–2024. Every selected promotion-neighborhood cell must have
positive mean AE improvement in at least 4/5 years.

UP and DOWN are both mandatory: each side must have positive mean AE improvement
and positive HIGH-minus-LOW residual separation.

## 13. Frozen search surface

3 W × 4 H = **12 primary cells**.

No q threshold. No alternative descriptor. No sign reinterpretation. No
one-sided rescue. No additional model family.

Adjacent H pairs: 30/60, 60/120, 120/240.

## 14. Promotion gates

Required gates exactly:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `morphology_ordering`
6. `side_stability`
7. `horizon_robustness`
8. `parameter_robustness`
9. `year_stability`

Per-cell gates are the first six.

Horizon robustness: one W has an adjacent H pair passing all six per-cell gates.

Parameter robustness: the same adjacent H pair passes all six per-cell gates for
at least one additional distinct W.

A full promotion neighborhood additionally requires all four cells to pass
4/5-year stability. If multiple full neighborhoods qualify, select the
lexicographically first by frozen H-pair order then ascending W. Never rank by
effect size or significance.

Missing/nonfinite/errored mandatory evidence is non-pass.

## 15. Verdict and close condition

Allowed market verdicts:

- `B2_03_PROMOTED_CANDIDATE`
- `B2_03_CLOSED_NO_PROMOTION`

Integrity/data/authorization failure aborts without market verdict.

Failure closes B2-03. No second impulse-morphology, extremeness, path-efficiency,
counter-move, or threshold child is admitted in current V2.

No real B2-03 outcomes are authorized by this preregistration.
