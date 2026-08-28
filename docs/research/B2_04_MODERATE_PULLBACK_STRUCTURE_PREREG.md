# B2-04 Moderate Pullback Structure — Preregistration

**Status:** `PREREG_CANDIDATE / OUTCOME_BLIND`  
**Formulation ID:** `B2-04_MODERATE_PULLBACK_STRUCTURE`  
**Primary family:** F1 — directional persistence / continuation  
**Post-hoc provenance:** explicit H04-derived `POSTHOC_UNTESTED` child  
**Dataset:** `CORE_BTC_BINANCE_V0`  
**Required snapshot:** `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`  
**Machine-readable freeze:** `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json`

This is the **one** H04-derived child admitted by the frozen V2 inventory. It
does not reopen H04 depth search and does not authorize real B2-04 outcomes.

## 1. Research question

Inside the already-frozen H04 moderate pullback domain, does one predeclared
property of the **post-pullback recovery path** add stable continuation
information beyond trend state, pullback depth, and the net amount of recovery
already visible by decision time?

The candidate property is path structure, not a better depth threshold.

## 2. H04 inheritance and quarantine

Reuse H04's causal geometry exactly for the trigger event at `t0`:

- UTC-aligned 15m trigger grid;
- trend lookbacks `L ∈ {240m,480m,960m}`;
- antecedent trend interval `[t0-60m-L,t0-60m)`;
- pullback interval `[t0-60m,t0)`;
- established-trend threshold `TREND_PCTL_L(t0)>=0.80`;
- H04 direction = sign of antecedent trend return;
- moderate pullback only:
  `0.25 <= PULLBACK_DEPTH(t0) < 0.40`.

No shallow/deep cells are eligible. No new trend q, depth edge, P window, or
alternative moderate definition may be tested.

## 3. Chronology and availability

Warmup/reference: 2020-01-01 to 2020-02-01 UTC. Development: 2020-02-01
inclusive to 2025-01-01 exclusive. 2025 validation and 2026 OOS are forbidden.

The B2-04 trigger is fully known at t0. B2-04 then observes a fixed recovery
window `R=30m`, and its decision time is:

`T=t0+30m`.

All six 5m recovery bars `[t0,T)` must be complete and available by T. Every
scored event must satisfy `T+240m < 2025-01-01T00:00:00Z`.

## 4. Trigger definitions

`TREND_RET_L = ln(close(t0-60m)/close(t0-60m-L))`.

Exact zero excludes. Trend direction `d=sign(TREND_RET_L)`.

`SIGNED_PB_RET = d*ln(close(t0)/close(t0-60m))`.

Require `SIGNED_PB_RET<0`.

`PULLBACK_DEPTH = -SIGNED_PB_RET/abs(TREND_RET_L)`.

Require `0.25<=PULLBACK_DEPTH<0.40`.

`TREND_PCTL_L(t0)` is H04's causal trailing-30d deterministic midrank
percentile of `abs(TREND_RET_L)`, current record excluded. Require >=0.80.

## 5. Refractory rule

Separately for each L, after accepting the earliest qualifying trigger at t0,
suppress later qualifying triggers of either trend direction with trigger time
in `(t0,t0+60m]`.

Keep earliest. Do not retune. This is at least as strict as the 30m recovery
window and prevents overlapping accepted recovery observations for a given L.

## 6. Single structural property

Recovery window uses six complete 5m returns `r_1...r_6` in `[t0,T)`.

Net recovery in original trend direction:

`RECOVERY_NET = d*ln(close(T)/close(t0))`.

Baseline nuisance control:

`RECOVERY_NET_NORM = RECOVERY_NET/abs(TREND_RET_L)`.

Total recovery-path variation:

`RECOVERY_TV = sum(abs(r_i))`.

Require finite `RECOVERY_TV>0`.

The single frozen B2-04 structural descriptor is:

`RECOVERY_EFFICIENCY = RECOVERY_NET / RECOVERY_TV`.

It lies in [-1,1] up to floating tolerance:

- high positive = direct recovery in original trend direction;
- near zero = choppy/no net recovery;
- negative = continued movement against the original trend.

The baseline already contains RECOVERY_NET_NORM, so B2-04 cannot win merely by
discovering that price had already recovered by T. Candidate incremental value
must come from path efficiency/directness beyond net recovery magnitude.

No second recovery descriptor, speed threshold, wick feature, time-to-reclaim,
depth retune, or alternate recovery window is admitted.

## 7. Causal recovery state

For each L and trend direction, use historical accepted triggers whose own
recovery decision `T_e<T`, `T_e>=T-180d`, and whose RECOVERY_EFFICIENCY was
available by T_e.

Minimum reference N=120. Current event excluded. Deterministic midrank tertiles:

- LOW [0,1/3)
- MID [1/3,2/3)
- HIGH [2/3,1]

Each historical state is frozen exactly once as-of its own T_e and never
recomputed later.

Expected ordering after baseline control:

`HIGH > MID > LOW`.

## 8. Baseline and candidate

Causal UTC-week walk-forward OLS. For each L,H, refit at Monday 00:00 UTC S and
hold fixed for that week.

Baseline features:

1. intercept;
2. `TREND_PCTL_L`;
3. `abs(TREND_RET_L)`;
4. `PULLBACK_DEPTH`;
5. `RECOVERY_NET_NORM`;
6. `SIDE_UP` (1 for uptrend, 0 for downtrend).

Candidate adds:

- `RECOVERY_LOW`;
- `RECOVERY_HIGH`;

with MID reference.

Baseline training: mature baseline-valid rows in `[S-365d,S)` with
`T_e+H<=S`. Candidate training is the subset with valid stored recovery
state.

Minimum baseline N=500. Minimum candidate N=500 and >=100 records in each state.
Comparator may use more historical training rows; current scored support remains
identical. If either weekly fit fails, both models are unavailable for scoring.

Sort by canonical RECORD_ID before standardization/OLS. Standardize continuous
columns from each model's own causal training set. Fit only
`numpy.linalg.lstsq(...,rcond=None)`; nonfinite/rank-deficient/zero-std/error
fails closed. No fallback.

## 9. Future target

`H ∈ {30m,60m,120m,240m}`.

`CONT_RET_H(T)=d*ln(close(T+H)/close(T))`.

Normalize by causal trailing-30-calendar-day median absolute H-return on
UTC-aligned 15m boundaries with `t+H<=T`.

Require finite positive scale.

## 10. Same support and identity

Candidate/comparator score exact same canonical records.

Event identity includes dataset/snapshot, L, trend interval, pullback interval,
trigger t0, trend direction, recovery interval, and decision T. Scored record
identity is `EVENT_ID|H`. Preserve underlying 1m/5m aligned bucket provenance.

## 11. Primary metric and structural diagnostic

Primary loss is absolute error. Define
`AE_IMPROVEMENT=BASE_AE-CAND_AE`.

Material relative-MAE threshold = 2%.

`BASE_RESIDUAL=Y_H-BASE_PRED`.

Expected state ordering:
`median_LOW < median_MID < median_HIGH`.

Report HIGH-minus-LOW separation and AE improvement separately for uptrend and
downtrend triggers.

## 12. Causal placebo

Seed `20260905`, 100 replicates.

At each weekly fit, permute only historical recovery-state labels within:

`calendar_month(T_e) × trend_direction × trend_strength_bin`

where trend-strength bins are exactly H04's existing frozen bins:

- [0.80,0.90)
- [0.90,1.00]

Sort by canonical EVENT_ID before RNG. Seed:
`20260905|replicate|L|H|week_start_S|stratum_id`.

Use only real candidate-training rows, keep all baseline features/targets fixed,
and leave current-week true recovery states unchanged. Evaluate on exact
real-candidate support. Real mean AE improvement must exceed placebo p95.

## 13. Bootstrap, stability, search surface

UTC-week bootstrap: seed `20260906`, 2000 replicates, 95% CI.

Years fixed 2020–2024. Both uptrend and downtrend sides are mandatory.

Search surface exactly:

3 L × 4 H = **12 primary cells**.

Recovery R is fixed 30m. Moderate depth is fixed [0.25,0.40). There is one
descriptor and one model family.

Adjacent H pairs: 30/60, 60/120, 120/240.

## 14. Promotion gates

Required gates exactly:

1. `primary_positive`
2. `material_relative_mae`
3. `bootstrap_positive`
4. `placebo_separation`
5. `recovery_ordering`
6. `direction_stability`
7. `horizon_robustness`
8. `parameter_robustness`
9. `year_stability`

Per-cell gates are the first six.

Direction stability requires both trend directions to have positive mean AE
improvement and positive HIGH-minus-LOW residual separation.

Horizon robustness requires one L with an adjacent H pair passing all six
per-cell gates. Parameter robustness requires the same H pair on at least one
additional L.

Every selected neighborhood cell must be positive in >=4/5 fixed years. If
multiple full neighborhoods qualify, select lexicographically by frozen H-pair
order then ascending L, never by effect magnitude.

Missing/nonfinite/errored evidence fails closed.

## 15. Verdict and close condition

Allowed market verdicts:

- `B2_04_PROMOTED_CANDIDATE`
- `B2_04_CLOSED_NO_PROMOTION`

Failure closes B2-04 and the only current-V2 H04 child path. No second
moderate-depth child is allowed.

No real B2-04 outcomes are authorized by this preregistration.
