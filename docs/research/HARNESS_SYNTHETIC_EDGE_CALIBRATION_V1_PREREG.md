# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Repaired Outcome-Blind Preregistration

**Status:** `PREREG_CANDIDATE_OUTCOME_BLIND_REPAIRED_AFTER_REDTEAM`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Unit type:** methodology calibration, not a market hypothesis  
**Base main at design start:** `79f68df395ecdda064386050d4d280cb994c4bbf`  
**Execution status:** `synthetic_execution_authorized = false`

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json).

---

## 0. Purpose

This unit asks whether the current Signalbot-style research process can detect small, noisy, sparse, **clustered** conditional predictive structure while continuing to reject false structure.

It calibrates four different layers that must not be conflated:

```text
GROUND_TRUTH_VISIBLE
        ↓
MODEL_DETECTED
        ↓
STRICT_PASS_EX_MATERIALITY
        ↓
STRICT_PASS
```

Synthetic data are never market evidence. The calibration is a mandatory methodology gate before B2-06 scientific execution, but it cannot authorize B2-06. `B2-06_LEVERAGE_CROWDING` remains independently blocked by `FUNDING_PUBLICATION_LATENCY_UNPROVEN` and closed research/outcome/evaluator authorization.

---

## 1. Hard boundaries

This preregistration does not authorize or perform synthetic production execution, implementation of the production runner, access to CORE/OI/funding/any real market data, B2-06 predictive outcome access, 2025 validation, 2026 OOS, inventory modification, B2-01..B2-05 reruns, B2-05 recovery changes, or market promotion.

```text
synthetic_execution_authorized = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
market_promotion_possible = false
```

---

## 2. Two calibration modes

### `ORACLE_CONFIRMATORY`

The evaluator receives the correct candidate feature `F03`, but no truth metadata, privileged support labels, or generator internals. This isolates where the path from statistical visibility to prediction, strict confirmation, and materiality loses power once the formulation is already correct.

### `BLIND_LIBRARY_DISCOVERY`

The evaluator receives ten opaque candidate IDs and applies the complete frozen search → select → evaluate procedure. This measures bounded discovery only; it is not unrestricted ML discovery, human feature engineering, or independent confirmation after search.

---

## 3. Four-stage diagnostic contract

`GROUND_TRUTH_VISIBLE` is truth-aware artifact diagnostics only. It is never available to candidate fitting, selection, placebo generation, or tie-breaking.

```text
MODEL_DETECTED = primary_positive
                 AND bootstrap_positive
                 AND placebo_separation

STRICT_PASS_EX_MATERIALITY = MODEL_DETECTED
                             AND era_stability
                             AND support_sanity

STRICT_PASS = STRICT_PASS_EX_MATERIALITY
              AND RELATIVE_MAE_IMPROVEMENT >= 0.02
```

The 2% pooled relative-MAE threshold is intentionally unchanged. It is an object of calibration, not a target to tune against synthetic outcomes.

---

## 4. Synthetic chronology

Each world has ordered rows `t=0..N-1` and five equal contiguous eras `E1..E5`. Every frozen N is divisible by five, so no remainder rule exists.

Primary `N=5000`. SMALL sensitivity also uses `N={2500,10000}`.

- E1 training only;
- fit all E1 rows in ascending t → score all E2 rows;
- fit all E1+E2 rows → score E3;
- fit all E1+E2+E3 rows → score E4;
- fit all E1+E2+E3+E4 rows → score E5.

Random splits and future information are forbidden.

---

## 5. Frozen DGP

All continuous quantities are float64. RNG is NumPy `Generator(PCG64)`.

```text
X1_t = 0.70*X1_(t-1) + sqrt(1-0.70^2)*U1_t
X2_t = 0.40*X2_(t-1) + sqrt(1-0.40^2)*U2_t
U1_t,U2_t ~ N(0,1)
X1_0=X2_0=0
MU_BASE_t = 0.20*X1_t - 0.15*X2_t
```

The baseline is deliberately correctly specified. V1 does not calibrate candidate absorption of baseline-model misspecification.

### Persistent sparse support

For target stationary support `p`:

```text
rho = 0.90
P(S_t=1 | S_(t-1)=1) = rho
P(S_t=1 | S_(t-1)=0) = p*(1-rho)/(1-p)
S_0 ~ Bernoulli(p)
TRUE_TRIGGER_t = S_t
```

Support is sparse and clustered. Mechanism-transition uniforms, `U1`, `U2`, and noise innovations are mutually independent.

Noise:

```text
RAW_t ~ StudentT(df=5)/sqrt(5/3)
ETA_t = 0.25*ETA_(t-1) + sqrt(1-0.25^2)*RAW_t
ETA_0=0
SIGMA_t = 1.0 + 0.30*abs(X1_t)
NOISE_t = SIGMA_t*ETA_t
Y_t = MU_BASE_t + beta_t*S_t + NOISE_t
```

---

## 6. Scenario ladder and pre-outcome scale audit

The red-team arithmetic established before execution that the original 2% pooled-MAE gate exceeds the best attainable pooled-MAE improvement for every positive stationary rung. We freeze that fact rather than hide it or increase beta until the test passes.

Reference residual SD ≈ `1.253`; mean absolute noise ≈ `0.919`. These are analytic references, not calibration outcomes.

| scenario | support | beta | beta / residual SD | expected positive rows at N=5000 | asymptotic max pooled relative-MAE improvement |
|---|---:|---:|---:|---:|---:|
| NULL | 10% generated support | 0.00 | 0.000 | 500 | 0.000% |
| EASY | 20% | 0.40 | 0.319 | 1000 | 1.07% |
| MODERATE | 10% | 0.25 | 0.200 | 500 | 0.24% |
| SMALL | 5% | 0.18 | 0.144 | 250 | 0.064% |
| TINY_NOISY | 2.5% | 0.12 | 0.096 | 125 | 0.014% |

Negative control:

```text
NONSTATIONARY_TRAP support=0.10
beta(E1)=0.30
beta(E2)=0.30
beta(E3)=0.30
beta(E4)=0.00
beta(E5)=0.00
```

This is an initially stable edge that vanishes, not a trivial sign reversal.

Mandatory materiality diagnostic:

```text
MATERIALITY_FRACTION_OF_ATTAINABLE
 = observed_RELATIVE_MAE_IMPROVEMENT
   / asymptotic_max_relative_mae_improvement_approx
```

Unavailable when the denominator is non-positive.

---

## 7. RNG authority

Root seed `20260908`.

World identity:

```text
HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|scenario|N|world_index
```

`world_index` is zero-based.

World seed:

```text
raw = UTF8(root_seed_decimal + "|" + world_identity)
digest = SHA256(raw)
world_seed_int = uint64_big_endian(digest[0:8])
```

Auxiliary namespace seed:

```text
raw = UTF8(world_seed_int_decimal + "|" + namespace + optional ordered context fields)
digest = SHA256(raw)
seed_int = uint64_big_endian(digest[0:8])
```

Namespaces are exactly `DGP`, `BOOTSTRAP`, `PLACEBO`, `VISIBILITY`. Python `hash()` and rerolls are forbidden.

---

## 8. Ten distinct discovery candidates

This table is the only authoritative mapping:

```text
F01 = S_(t-1), F01_0=0
F02 = S_t*I(X1_t>0)
F03 = S_t                         # exact true feature
F04 = I(X1_t>0)
F05 = I(X2_t>0)
F06 = I(X1_t>1)
F07 = I(X2_t<-1)
F08 = S_t*I(X2_t>0)
F09 = I(X1_t+X2_t>0)
F10 = I(X1_t-X2_t>0)
```

Frozen classes:

```text
TRUE  = {F03}
PROXY = {F01,F02,F08}
FALSE = {F04,F05,F06,F07,F09,F10}
```

The discovery selector receives opaque IDs, not class labels. Candidate addition or proxy reclassification after outcomes is forbidden.

---

## 9. Forecast family

Baseline:

```text
Y ~ intercept + X1 + X2
```

Candidate:

```text
Y ~ intercept + X1 + X2 + Fj
```

Estimator is `numpy.linalg.lstsq(X,y,rcond=None)`, unweighted, no regularization, full rank and finite coefficients required, no pseudoinverse or column-drop fallback. Baseline/candidate share exact scoring rows.

---

## 10. Prediction and conditional metrics

```text
BASE_AE = abs(Y-BASE_PRED)
CAND_AE = abs(Y-CAND_PRED)
AE_IMPROVEMENT = BASE_AE-CAND_AE
MEAN_AE_IMPROVEMENT = mean(AE_IMPROVEMENT)
RELATIVE_MAE_IMPROVEMENT = 1-mean(CAND_AE)/mean(BASE_AE)
```

Truth-aware reporting additionally requires:

- `SUPPORT_COVERAGE = mean(S==1)` on scored rows;
- support-conditional mean AE improvement, unavailable if no positive scored trigger rows;
- off-support mean AE improvement, unavailable if no negative scored trigger rows;
- support-run lengths, with era boundaries breaking runs;
- support-cluster count;
- raw positive support count;
- effective-support-N diagnostic.

Effective-support-N is frozen as:

```text
N_eff = N_positive / (1 + 2*sum(rho_k, k=1..K))
```

where `rho_k` is sample autocorrelation of the binary true-trigger series over scored rows and K is the largest lag before the first pair `(rho_k + rho_(k+1)) <= 0`. For `N_positive>0`, cap to `[1,N_positive]`. This is reporting only, never a gate.

Truth-aware quantities never enter discovery selection.

---

## 11. Ground-truth visibility

Using the same chronological baseline predictions:

```text
BASE_RESIDUAL = Y-BASE_PRED
VISIBILITY_STAT = mean(BASE_RESIDUAL | S=1) - mean(BASE_RESIDUAL | S=0)
```

Visibility bootstrap is exactly 500 replicates. Within each scored era, partition rows from era start into consecutive non-overlapping blocks of 50; retain a final shorter block. For each replicate, sample that era's original number of blocks with replacement, concatenate in sampled-block order, then truncate the resampled era back to its original row count. Concatenate eras in E2,E3,E4,E5 order. Blocks never cross eras.

`q025` uses NumPy linear quantile interpolation.

```text
GROUND_TRUTH_VISIBLE = visibility_bootstrap_q025 > 0
```

If either trigger class is absent in any nominal visibility replicate, that replicate is invalid; any invalid nominal replicate makes that world's `GROUND_TRUTH_VISIBLE=false` and records `visibility_invalid=true`. No replacement/reroll is allowed.

Truth access is restricted to this artifact diagnostic.

---

## 12. Strict gates

Frozen gate order:

1. `primary_positive`: pooled mean AE improvement > 0;
2. `material_relative_mae`: pooled relative MAE improvement >= 0.02;
3. `bootstrap_positive`: block-bootstrap q025 of pooled mean AE improvement > 0;
4. `placebo_separation`: real pooled mean AE improvement > placebo q95;
5. `era_stability`: positive mean AE improvement in at least 3 of E2..E5;
6. `support_sanity`: evaluated candidate has at least 50 positive scored rows and finite/nonzero support.

For ORACLE F03, candidate-positive support equals true trigger support. In BLIND mode this gate is candidate-specific and does not expose true-support labels.

No hidden gate is allowed.

---

## 13. Prediction bootstrap and placebo

Prediction bootstrap uses the identical era-local 50-row block construction/resampling/truncation rule from §11, applied to rows carrying `AE_IMPROVEMENT`. There are 500 nominal replicates. Statistic = pooled mean AE improvement after concatenating E2..E5. q025 uses linear interpolation. All nominal replicates must be finite; no reroll.

Placebo uses 999 nominal replicates per candidate/world. The literal evaluated `Fj` vector is permuted within each original era. For each replicate, historical candidate labels are permuted within their original era and reused consistently in every expanding fit that contains that era; scored-era labels are likewise permuted within their era. `Y`, `X1`, `X2`, timestamps/order, and all noncandidate fields remain fixed. The exact expanding-era model is refit. Statistic = pooled mean AE improvement; q95 uses linear interpolation. All nominal replicates must be finite or placebo separation is false.

Truth/proxy class metadata are forbidden from the placebo operation.

---

## 14. Monte Carlo precision

Primary: 400 worlds for each of six scenarios = 2400 worlds. SMALL additionally receives 400 worlds at N=2500 and 400 at N=10000. Total = 3200.

Every aggregate rate receives a Wilson score 95% interval with:

```text
z = 1.959963984540054
center = (p_hat + z^2/(2n)) / (1 + z^2/n)
half = z/(1+z^2/n) * sqrt(p_hat*(1-p_hat)/n + z^2/(4*n^2))
interval = [center-half, center+half]
```

Frozen decisions:

- specificity pass only if Wilson upper <= maximum;
- specificity fail only if Wilson lower > maximum;
- power pass only if Wilson lower >= minimum;
- power fail only if Wilson upper < minimum;
- otherwise `INDETERMINATE`.

Point estimates alone cannot trigger methodology consequences. Failed worlds stay in the denominator and make the aggregate `INCOMPLETE_EXECUTION` unless exact frozen execution is reproduced before result opening.

---

## 15. BLIND discovery taxonomy

Evaluate F01..F10 using the same frozen process.

Ex-materiality selection:

1. keep `STRICT_PASS_EX_MATERIALITY=true` candidates;
2. choose max pooled mean AE improvement;
3. exact tie → ascending feature ID;
4. none → `NO_CANDIDATE`.

Also report analogous full-`STRICT_PASS` selection.

```text
TRUE_DISCOVERY  = F03
PROXY_DISCOVERY = F01/F02/F08
FALSE_DISCOVERY = F04/F05/F06/F07/F09/F10
NO_DISCOVERY    = no candidate
ANY_EDGE_DECLARED = not NO_DISCOVERY
```

`BLIND_LIBRARY_NULL_FPR` is `ANY_EDGE_DECLARED` under NULL after the complete search-select-evaluate procedure. Same-world search is not described as independent confirmation.

---

## 16. Acceptance and detection-floor rules

Specificity uses Wilson upper bounds:

```text
ORACLE NULL MODEL_DETECTED FPR <= 0.05
BLIND full-pipeline NULL ANY_EDGE_DECLARED FPR <= 0.10
NONSTATIONARY_TRAP STRICT_PASS_EX_MATERIALITY detection <= 0.20
```

Sanity power uses Wilson lower bounds:

```text
EASY ORACLE MODEL_DETECTION >= 0.90
MODERATE ORACLE MODEL_DETECTION >= 0.70
```

SMALL sensitivity bands on `MODEL_DETECTION_RATE`:

```text
HIGH       >=0.80
MODERATE   >=0.50 and <0.80
LOW        >=0.20 and <0.50
VERY_LOW   <0.20
```

A band is assigned only if the entire Wilson interval lies within one band; otherwise `INDETERMINATE`.

Detection-floor attribution:

```text
if GROUND_TRUTH_VISIBLE Wilson upper < 0.50:
    VISIBILITY_FLOOR
elif MODEL_DETECTION Wilson upper < 0.50:
    MODEL_FLOOR
else:
    ABOVE_MEASURED_FLOOR
```

Materiality is independently diagnosed from `STRICT_PASS_EX_MATERIALITY` versus `STRICT_PASS` and the fraction-of-attainable metric. Full `STRICT_PASS` is not the sole calibration success variable.

---

## 17. Required result artifact

Any future authorized production run must retain exact implementation commit/tree and prereg blob identities; per-world identities/seeds; realized support, runs, clusters and effective-N diagnostic; pooled and conditional metrics; every raw gate statistic/boolean; four-stage oracle diagnostics; materiality fraction of attainable; all discovery-candidate results; selected feature and TRUE/PROXY/FALSE/NO_DISCOVERY taxonomy; aggregate rates with Wilson intervals; SMALL N sensitivity; detection-floor labels; and mechanically generated conclusions.

---

## 18. B2-06 consequences

Synthetic calibration never authorizes market execution.

- specificity failure → `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`;
- EASY/MODERATE model-power failure → `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`;
- VISIBILITY_FLOOR → comparable negative market results cannot strongly establish absence of edge;
- MODEL_FLOOR → model/evaluation sensitivity needs repair or an explicit power caveat;
- materiality-only failure → record that unchanged 2% pooled materiality suppresses otherwise detectable sparse structure.

A materiality-only finding does not authorize changing any market gate. Any such change requires a separate outcome-blind preregistration. `INDETERMINATE` produces no binary methodology claim and cannot be resolved by tuning on these outcomes.

---

## 19. Anti-rescue

After any production outcome opens: no lowering the 2% threshold; no beta/support/rho/noise changes; no switching diagnostic layers post hoc; no dropping worlds; no rerolls/favorable seeds; no denominator replacement; no candidate addition/proxy reclassification; no sign reversal; no bootstrap/block/placebo changes; no synthetic-success-as-market-evidence.

Any scientific change after outcome opening requires a new calibration version.

---

## 20. Execution ceremony

1. independent red-team accepts repaired prereg;
2. implementation written using synthetic fixture tests only;
3. implementation independently reviewed without production-grid execution;
4. exact implementation commit/tree frozen;
5. one production calibration explicitly authorized;
6. complete result persisted before methodology changes;
7. outcomes inspected once;
8. subsequent methodology changes require a new version.

Current state:

```text
implementation_exists = false
production_calibration_executed = false
synthetic_execution_authorized = false
```
