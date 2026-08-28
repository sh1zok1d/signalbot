# B2-05 Flow Absorption / Price Impact — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-05_FLOW_ABSORPTION`  
**Primary family:** F4 — participation / order-flow information  
**Frozen inventory:** `docs/research/V2_FORMULATION_INVENTORY.md`  
**Dataset:** `CORE_BTC_BINANCE_V0`  
**Required snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Machine-readable freeze:** `docs/research/B2_05_FLOW_ABSORPTION_PREREG.json`

This preregistration instantiates the already-frozen B2-05 inventory entry. It
does not revive H05 imbalance-alone and does not authorize real B2-05 outcomes.

## 1. Research question

Conditional on the same contemporaneous taker imbalance, price response,
activity, and realized volatility, does the **interaction between aggressive
flow and contemporaneous price response** add stable information about
subsequent movement in the flow direction?

H05 tested imbalance magnitude itself and failed. B2-05 contains no q/tail
threshold search and cannot promote imbalance alone.

## 2. Chronology and source identity

Use accepted `CORE_BTC_BINANCE_V0` only. Source timeframe is canonical 1m;
decision grid is UTC-epoch-aligned 15m.

Warmup/reference: 2020-01-01 to 2020-02-01 UTC. Development: 2020-02-01
inclusive to 2025-01-01 exclusive. 2025 validation and 2026 OOS are forbidden.

Every feature input must have `available_at<=T`. Every scored event must
satisfy `T+240m < 2025-01-01T00:00:00Z`.

## 3. Frozen flow windows

`W ∈ {15m,30m,60m}`.

Use accepted 1m rows entirely inside `[T-W,T)`.

Let:

`TOTAL_W = sum(base_volume)`.

`TAKER_BUY_W = sum(taker_buy_base_volume)`.

Require finite `TOTAL_W>0` and each 1m taker-buy value satisfy
`0<=taker_buy_base_volume<=base_volume`. Corruption fails closed.

`TAKER_SELL_W = TOTAL_W-TAKER_BUY_W`.

Frozen imbalance:

`IMB = (TAKER_BUY_W-TAKER_SELL_W)/TOTAL_W`
     `= (2*TAKER_BUY_W-TOTAL_W)/TOTAL_W`.

Exact IMB=0 is unavailable. Flow direction:

`d=sign(IMB)`.

`ABS_IMB=abs(IMB)`.

There is no imbalance percentile threshold or BUY/SELL-specific candidate.

## 4. Price/volatility/activity controls

Contemporaneous flow-direction price response:

`FLOW_RET = d*ln(close(T)/close(T-W))`.

Realized volatility:

`RV_W=sqrt(sum(r_1m^2))` over `[T-W,T)`; require finite >0.

Activity:

`LOG_ACTIVITY=ln(TOTAL_W)`; require finite.

The baseline explicitly contains ABS_IMB and FLOW_RET, so B2-05 cannot win by
rediscovering raw imbalance or raw contemporaneous price movement.

## 5. Single impact/absorption descriptor

The single frozen B2-05 interaction descriptor is:

`IMPACT_INTERACTION = ABS_IMB * FLOW_RET`.

Interpretation:

- high positive: strong imbalance accompanied by aligned price response;
- near zero: aggressive-flow state with little aligned response / absorption;
- negative: price moved opposite the aggressive-flow direction.

This is a main-effect interaction. No ratio, epsilon floor, order-book proxy,
alternative impact measure, imbalance threshold, BUY-only/SELL-only child, or
second descriptor is admitted.

## 6. Causal impact state

For each W and flow side at decision T, reference historical records with:

- same W;
- same BUY/SELL side;
- `T_e<T`;
- `T_e>=T-180 calendar days`;
- finite IMPACT_INTERACTION known by T_e.

Minimum reference N=120. Current event excluded. Deterministic midrank tertiles:

- LOW [0,1/3)
- MID [1/3,2/3)
- HIGH [2/3,1]

Each historical impact state is computed exactly once as-of its own T_e and
stored. Never recompute using later data/full-sample quantiles.

Expected post-baseline ordering:

`HIGH > MID > LOW`

for future movement in the flow direction.

## 7. Strong baseline and candidate

Causal UTC-week walk-forward OLS. For each W,H, refit at Monday 00:00 UTC S and
hold fixed through the week.

Baseline features:

1. intercept;
2. `ABS_IMB`;
3. `FLOW_RET`;
4. `RV_W`;
5. `LOG_ACTIVITY`;
6. `SIDE_BUY`.

Candidate adds only:

- `IMPACT_LOW`;
- `IMPACT_HIGH`;

with MID reference.

Thus the candidate must add information beyond both components from which the
interaction is formed.

Baseline training uses mature baseline-valid rows in `[S-365d,S)` with
`T_e+H<=S`. Candidate training is the subset with valid stored impact state
**and** both valid stored placebo nuisance bins defined in §12. The nuisance
bins are not candidate predictors; requiring them here ensures the causal
placebo never creates a hidden training subset. Baseline training does not
require the nuisance bins and may therefore contain more historical rows.

Minimum baseline N=500. Minimum candidate N=500 and >=100 records in each
LOW/MID/HIGH state. The comparator may use more historical training rows.
Current scored support remains exact same-support. If either weekly fit fails,
both models are unavailable for scoring.

Sort by canonical RECORD_ID before standardization/OLS. Continuous columns are
standardized from each model's own causal training set; binary/state dummies are
not. Fit only `numpy.linalg.lstsq(...,rcond=None)`; nonfinite, rank-deficient,
zero-std, or fit error fails closed. No fallback.

## 8. Future target

`H ∈ {30m,60m,120m,240m}`.

`FLOW_CONT_RET_H(T)=d*ln(close(T+H)/close(T))`.

Normalize by the causal trailing-30-calendar-day median absolute H-return on
UTC-aligned 15m boundaries satisfying `t+H<=T`.

Scale must be finite and positive.

## 9. Exact support and identities

Current scoring requires valid current features/state, both frozen weekly fits,
valid future target/scale, and development-boundary compliance.

Candidate and comparator score exactly the same RECORD_ID set. No BUY-only,
SELL-only, horizon-only, or year-only support selection is allowed.

Canonical identity includes dataset/snapshot, source timeframe, W, interval
start/end, flow side, and T. Scored identity is `EVENT_ID|H`. Preserve exact
underlying 1m bucket provenance.

## 10. Primary incremental metric

`BASE_AE=abs(Y_H-BASE_PRED)`  
`CAND_AE=abs(Y_H-CAND_PRED)`  
`AE_IMPROVEMENT=BASE_AE-CAND_AE`.

Report N, mean/median improvement, baseline/candidate MAE, relative MAE
improvement, and UTC-week bootstrap 95% CI.

Materiality threshold = relative MAE improvement >=2%.

## 11. Structural diagnostic

`BASE_RESIDUAL=Y_H-BASE_PRED`.

Expected ordering:
`median_LOW < median_MID < median_HIGH`.

Report HIGH-minus-LOW separation separately for BUY and SELL flow directions.

## 12. Causal nuisance bins and placebo

For placebo stratification only, compute/store as-of each T_e deterministic
trailing-180d same-W/side midrank quintiles for:

- ABS_IMB;
- FLOW_RET.

For each nuisance percentile separately, exclude the current historical record
and require at least **120** earlier same-W/side records in the trailing
180-calendar-day window. Use deterministic midrank percentiles. Each nuisance
quintile is computed exactly once as-of its record's own `T_e` and stored; later
records, later week starts, full-development quantiles, and backfills may not
change it. If either bin is unavailable, that row is ineligible for candidate
training but may remain baseline-training eligible.

These nuisance bins never enter the candidate feature vector or promotion as
independent predictors. Their eligibility role exists only to make placebo and
real-candidate training support identical.

Placebo seed `20260907`, 100 replicates.

At each weekly fit, use exactly the real candidate's causal training records.
No placebo-only row dropping is allowed. Strata:

`calendar_month(T_e) × side × imbalance_quintile × flow_return_quintile`.

Sort by canonical EVENT_ID before RNG and permute only historical impact-state
labels. Seed:

`20260907|replicate|W|H|week_start_S|stratum_id`.

Keep baseline features, target, timestamps, and current-week true impact states
unchanged. Evaluate on exact real-candidate support. Real mean AE improvement
must exceed placebo p95.

## 13. Bootstrap and stability

UTC-week block bootstrap: seed `20260908`, 2000 replicates, 95% CI.

Years fixed: 2020–2024.

BUY and SELL both mandatory: each side must have positive mean AE improvement
and positive HIGH-minus-LOW residual separation.

## 14. Frozen search surface

3 W × 4 H = **12 primary cells**.

W={15,30,60}; H={30,60,120,240}.

No q threshold, no second impact descriptor, no ratio/epsilon variant, no
BUY-only/SELL-only rescue, no alternative model family.

Adjacent H pairs: 30/60, 60/120, 120/240.

## 15. Promotion gates

Required gates exactly:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `impact_ordering`
6. `side_stability`
7. `horizon_robustness`
8. `parameter_robustness`
9. `year_stability`

Per-cell gates are the first six.

Horizon robustness: one W has an adjacent H pair passing all six per-cell gates.

Parameter robustness: same adjacent H pair passes all six on at least one
additional W.

Every cell in the selected full neighborhood must be positive in >=4/5 years.
If multiple qualify, select lexicographically by frozen H-pair order then
ascending W, never by effect magnitude/significance.

Missing/nonfinite/errored mandatory evidence fails closed.

## 16. Verdict and close condition

Allowed market verdicts:

- `B2_05_PROMOTED_CANDIDATE`
- `B2_05_CLOSED_NO_PROMOTION`

Failure closes B2-05. No further taker-imbalance threshold, impact ratio,
BUY/SELL rescue, or alternative absorption child is admitted in current V2.

No real B2-05 outcomes are authorized by this preregistration.
