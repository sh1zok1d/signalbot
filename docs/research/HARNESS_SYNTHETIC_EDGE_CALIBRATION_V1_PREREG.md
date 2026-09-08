# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Repaired Outcome-Blind Preregistration

**Status:** `PREREG_CANDIDATE_OUTCOME_BLIND_REPAIRED_AFTER_REDTEAM`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Unit type:** methodology calibration, not a market hypothesis  
**Base main at design start:** `79f68df395ecdda064386050d4d280cb994c4bbf`  
**Execution status:** `synthetic_execution_authorized = false`

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json).

---

## 0. Purpose and diagnostic stack

This unit asks whether the Signalbot research process can detect small, noisy, sparse, **clustered** conditional predictive structure while continuing to reject false structure. Synthetic data are never market evidence.

The frozen diagnostic stack is:

```text
GROUND_TRUTH_VISIBLE
        ↓
MODEL_DETECTED
        ↓
STRICT_PASS_EX_MATERIALITY
        ↓
STRICT_PASS
```

`GROUND_TRUTH_VISIBLE` is truth-aware reporting only. `MODEL_DETECTED = primary_positive AND bootstrap_positive AND placebo_separation`. `STRICT_PASS_EX_MATERIALITY = MODEL_DETECTED AND era_stability AND support_sanity`. `STRICT_PASS = STRICT_PASS_EX_MATERIALITY AND RELATIVE_MAE_IMPROVEMENT >= 0.02`.

The unchanged 2% pooled-MAE requirement is therefore an object of calibration, not the sole definition of detection.

This unit is a mandatory methodology gate before B2-06 science but cannot authorize B2-06. `FUNDING_PUBLICATION_LATENCY_UNPROVEN` and all B2-06 research/outcome/evaluator authorization remain closed independently.

---

## 1. Hard boundaries

```text
synthetic_execution_authorized = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
market_promotion_possible = false
```

No production synthetic run, real market data, B2-06 outcomes, 2025/2026 access, V2 inventory change, B2-01..B2-05 rerun, or B2-05 recovery change is authorized.

---

## 2. Calibration modes

`ORACLE_CONFIRMATORY` receives only the correct candidate `F03`; it receives no truth class metadata or privileged support information.

`BLIND_LIBRARY_DISCOVERY` receives ten opaque candidate IDs and performs the complete frozen search-select-evaluate procedure. It calibrates bounded discovery, not unrestricted ML or independent post-search confirmation.

---

## 3. Chronology

Each world has `N` ordered rows split into five equal contiguous eras E1..E5. All frozen N values are divisible by five.

Primary N = 5000. SMALL additionally uses N = 2500 and 10000.

```text
E1: training only
E2: fit E1, score E2
E3: fit E1+E2, score E3
E4: fit E1+E2+E3, score E4
E5: fit E1+E2+E3+E4, score E5
```

All training/scoring rows are in ascending t. Random splitting and future information are forbidden.

---

## 4. Frozen DGP

All continuous quantities are float64. RNG is NumPy `Generator(PCG64)`.

```text
X1_t = 0.70*X1_(t-1) + sqrt(1-0.70^2)*U1_t
X2_t = 0.40*X2_(t-1) + sqrt(1-0.40^2)*U2_t
U1_t,U2_t ~ N(0,1)
X1_0=X2_0=0
MU_BASE_t = 0.20*X1_t - 0.15*X2_t
```

The baseline is intentionally correctly specified; V1 does not calibrate candidate absorption of baseline misspecification.

For scenario stationary support p:

```text
rho = 0.90
P(S_t=1|S_(t-1)=1) = rho
P(S_t=1|S_(t-1)=0) = p*(1-rho)/(1-p)
S_0 ~ Bernoulli(p)
TRUE_TRIGGER_t = S_t
```

Support is clustered. U1, U2, transition uniforms and noise innovations are mutually independent.

```text
RAW_t ~ StudentT(df=5)/sqrt(5/3)
ETA_t = 0.25*ETA_(t-1) + sqrt(1-0.25^2)*RAW_t
ETA_0=0
SIGMA_t = 1.0 + 0.30*abs(X1_t)
NOISE_t = SIGMA_t*ETA_t
Y_t = MU_BASE_t + beta_t*S_t + NOISE_t
```

---

## 5. Scenario ladder and pre-outcome scale reference

Pre-outcome analytic reference: residual SD ≈ 1.253 and mean absolute noise ≈ 0.919.

| scenario | support | beta | beta / residual SD | expected positives at N=5000 | approximate ideal max pooled relative-MAE gain |
|---|---:|---:|---:|---:|---:|
| NULL | 10% generated support | 0.00 | 0.000 | 500 | 0.000% |
| EASY | 20% | 0.40 | 0.319 | 1000 | 1.07% |
| MODERATE | 10% | 0.25 | 0.200 | 500 | 0.24% |
| SMALL | 5% | 0.18 | 0.144 | 250 | 0.064% |
| TINY_NOISY | 2.5% | 0.12 | 0.096 | 125 | 0.014% |

The 2% gate is expected to be unreachable even under ideal pooled prediction for these stationary positive scenarios. This mismatch is deliberately retained and diagnosed; beta/support may not be changed to force passage.

`NONSTATIONARY_TRAP` uses support 10% and beta by era: E1=.30, E2=.30, E3=.30, E4=0, E5=0. It tests an initially stable edge that vanishes.

Mandatory diagnostic:

```text
MATERIALITY_FRACTION_OF_ATTAINABLE
 = observed_RELATIVE_MAE_IMPROVEMENT
   / asymptotic_max_relative_mae_improvement_approx
```

Unavailable when denominator <= 0.

---

## 6. RNG authority

Root seed = `20260908`.

World identity = `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|scenario|N|world_index`, zero-based index.

World seed = SHA256 of UTF-8 `root_seed_decimal|world_identity`, first eight raw digest bytes interpreted big-endian unsigned.

Auxiliary seed = SHA256 of UTF-8 `world_seed_int_decimal|namespace|optional ordered context`, same eight-byte conversion. Namespaces are exactly `DGP`, `BOOTSTRAP`, `PLACEBO`, `VISIBILITY`. Python `hash()` and rerolls are forbidden.

---

## 7. Ten distinct candidates

Only authoritative mapping:

```text
F01 = S_(t-1), F01_0=0
F02 = S_t*I(X1_t>0)
F03 = S_t
F04 = I(X1_t>0)
F05 = I(X2_t>0)
F06 = I(X1_t>1)
F07 = I(X2_t<-1)
F08 = S_t*I(X2_t>0)
F09 = I(X1_t+X2_t>0)
F10 = I(X1_t-X2_t>0)
```

```text
TRUE  = {F03}
PROXY = {F01,F02,F08}
FALSE = {F04,F05,F06,F07,F09,F10}
```

The selector sees opaque IDs, not taxonomy. Post-outcome candidate addition or proxy reclassification is forbidden.

---

## 8. Forecast contract

Baseline: `Y ~ intercept + X1 + X2`.

Candidate: `Y ~ intercept + X1 + X2 + Fj`.

Estimator: `numpy.linalg.lstsq(X,y,rcond=None)`, unweighted, no regularization, full rank and finite coefficients required, no fallback, exact same scoring support.

---

## 9. Metrics and clustered-support diagnostics

```text
BASE_AE = abs(Y-BASE_PRED)
CAND_AE = abs(Y-CAND_PRED)
AE_IMPROVEMENT = BASE_AE-CAND_AE
MEAN_AE_IMPROVEMENT = mean(AE_IMPROVEMENT)
RELATIVE_MAE_IMPROVEMENT = 1-mean(CAND_AE)/mean(BASE_AE)
```

Truth-aware reporting also includes support coverage; support-conditional and off-support mean AE improvement (unavailable if respective class empty); support run lengths with era boundaries breaking runs; cluster count; raw positive count; and effective support N.

```text
N_eff = N_positive / (1 + 2*sum(rho_k, k=1..K))
```

`rho_k` is sample autocorrelation of the binary true-trigger series over scored rows. K is the largest lag before the first pair `(rho_k + rho_(k+1)) <= 0`. For positive support, cap N_eff into `[1,N_positive]`. N_eff is diagnostic only.

---

## 10. Ground-truth visibility

```text
BASE_RESIDUAL = Y-BASE_PRED
VISIBILITY_STAT = mean(BASE_RESIDUAL|S=1) - mean(BASE_RESIDUAL|S=0)
```

Use 500 visibility bootstrap replicates. Within each scored era, make consecutive nonoverlapping 50-row blocks from era start; retain a shorter terminal block. Per replicate, sample that era's original number of blocks with replacement, concatenate in draw order, truncate to original era row count, then concatenate E2,E3,E4,E5. Blocks never cross eras. q025 uses linear interpolation.

`GROUND_TRUTH_VISIBLE = q025 > 0`.

If any nominal replicate lacks either S class, that replicate is invalid; any invalid nominal replicate makes the world's visibility false and records `visibility_invalid=true`. No replacement or reroll.

Truth access is forbidden from candidate fitting, selection, placebo and ties.

---

## 11. Strict gates

Frozen gate order:

1. pooled mean AE improvement > 0;
2. pooled relative MAE improvement >= 0.02;
3. prediction-bootstrap q025 > 0;
4. real pooled mean AE improvement > placebo q95;
5. positive mean improvement in at least 3 of four scored eras;
6. evaluated candidate has finite/nonzero positive scored count >=50.

ORACLE F03 candidate support equals true support; BLIND support_sanity is candidate-specific.

No hidden gate.

---

## 12. Prediction bootstrap and placebo

Prediction bootstrap: 500 replicates using the same era-local block construction/sampling/truncation as visibility, but on rows carrying AE improvement. Statistic = pooled mean AE improvement; q025 linear; all nominal replicates finite required.

Placebo: 999 replicates per candidate/world. Permute the literal Fj vector separately within each original era per replicate. The same replicate-specific permuted historical table is reused consistently by each expanding fit containing that era. Y/X1/X2/order remain fixed. Statistic = pooled mean AE improvement; q95 linear; all nominal replicates finite required. Truth/proxy metadata never enter permutation.

---

## 13. Monte Carlo precision

400 worlds per six primary scenarios = 2400. SMALL gets 400 additional worlds at N=2500 and 400 at N=10000. Total = 3200.

Every aggregate rate uses Wilson score 95% intervals with:

```text
z=1.959963984540054
center=(p_hat+z^2/(2n))/(1+z^2/n)
half=z/(1+z^2/n)*sqrt(p_hat*(1-p_hat)/n+z^2/(4*n^2))
```

Specificity pass if upper<=max; specificity fail if lower>max. Power pass if lower>=min; power fail if upper<min. Otherwise `INDETERMINATE`. Point estimates alone do not trigger conclusions.

Failed worlds remain in the denominator and cause `INCOMPLETE_EXECUTION`.

---

## 14. BLIND discovery

Evaluate all F01..F10. Among candidates with `STRICT_PASS_EX_MATERIALITY=true`, choose max pooled mean AE improvement; exact tie uses ascending feature ID; none=`NO_CANDIDATE`. Also report analogous full-STRICT selection.

```text
TRUE_DISCOVERY  = F03
PROXY_DISCOVERY = F01/F02/F08
FALSE_DISCOVERY = F04/F05/F06/F07/F09/F10
NO_DISCOVERY    = none
ANY_EDGE_DECLARED = not none
```

NULL FPR is ANY_EDGE_DECLARED after the entire search-select-evaluate pipeline. Same-world search is not independent confirmation.

---

## 15. Acceptance and floor attribution

Specificity thresholds, judged by Wilson upper:

```text
ORACLE NULL MODEL_DETECTED FPR <= .05
BLIND NULL full-pipeline FPR <= .10
NONSTATIONARY_TRAP STRICT_PASS_EX_MATERIALITY detection <= .20
```

Sanity power, judged by Wilson lower:

```text
EASY ORACLE MODEL_DETECTION >= .90
MODERATE ORACLE MODEL_DETECTION >= .70
```

SMALL MODEL_DETECTION bands: HIGH >=.80; MODERATE [.50,.80); LOW [.20,.50); VERY_LOW <.20. Entire Wilson interval must fit the band or result is `INDETERMINATE`.

Detection floor:

```text
if visibility Wilson upper < .50: VISIBILITY_FLOOR
elif model-detection Wilson upper < .50: MODEL_FLOOR
else: ABOVE_MEASURED_FLOOR
```

Materiality is independently diagnosed from strict-ex-materiality vs full strict plus fraction-of-attainable.

---

## 16. Mechanical conclusion authority

The future result may only emit consequences from these frozen mappings:

- specificity failure → `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`;
- EASY/MODERATE model-power failure → `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`;
- VISIBILITY_FLOOR → comparable negative market evidence cannot strongly establish absence of edge;
- MODEL_FLOOR → model/evaluation requires repair or explicit power caveat;
- materiality-only failure → record suppression by the 2% pooled gate; **no market-gate change is authorized**;
- `INDETERMINATE` → no binary methodology claim.

Passing calibration never authorizes B2-06.

---

## 17. Required immutable result

Future authorized execution must retain exact implementation commit/tree and prereg blobs; world identities/seeds; support runs/clusters/effective N; pooled and conditional metrics; every raw gate statistic and boolean; all four ORACLE stages; materiality fraction; all discovery candidate results and taxonomy; aggregate Wilson intervals; SMALL N sensitivity; floor labels; and mechanically generated conclusion.

---

## 18. Anti-rescue

After outcomes: no lowering 2%; no beta/support/rho/noise/sample-size changes; no switching diagnostic layer; no dropping worlds; no reroll/favorable seed; no denominator replacement; no candidate/proxy reclassification; no sign reversal; no bootstrap/placebo alteration; no synthetic result as market evidence.

Any scientific change after outcome opening requires a new version.

---

## 19. Execution ceremony

1. independent red-team accepts repaired prereg;
2. fixture-only implementation;
3. independent implementation review before production grid;
4. freeze exact implementation commit/tree;
5. explicit authorization for one production calibration;
6. persist full result before methodology changes;
7. inspect outcomes once;
8. any methodology change requires a new version.

Current state:

```text
implementation_exists = false
production_calibration_executed = false
synthetic_execution_authorized = false
```
