# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Repaired Outcome-Blind Preregistration

**Status:** `PREREG_CANDIDATE_OUTCOME_BLIND_REPAIRED_AFTER_REDTEAM`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Unit type:** methodology calibration, not a market hypothesis  
**Base main at design start:** `79f68df395ecdda064386050d4d280cb994c4bbf`  
**Execution status:** `synthetic_execution_authorized = false`

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json).

---

## 0. Purpose

This unit asks whether the current Signalbot-style research process can detect small, noisy, sparse, conditional predictive structure while continuing to reject false structure.

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

The purpose is diagnostic. Synthetic data are never market evidence.

The calibration remains a mandatory methodology gate before B2-06 scientific execution, but it cannot authorize B2-06. `B2-06_LEVERAGE_CROWDING` remains independently blocked by `FUNDING_PUBLICATION_LATENCY_UNPROVEN` and closed research/outcome/evaluator authorization.

---

## 1. Hard boundaries

This preregistration does not authorize or perform:

- synthetic production execution;
- implementation of the production calibration runner;
- access to CORE, OI, funding, exchange APIs, or any real market data;
- B2-06 predictive outcome access;
- 2025 validation or 2026 OOS access;
- any modification to `V2_FORMULATION_INVENTORY.md`;
- any rerun of B2-01 through B2-05;
- any B2-05 recovery change;
- any market promotion.

Frozen flags:

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

### 2.1 `ORACLE_CONFIRMATORY`

The evaluator receives the correct candidate feature `F03`, but receives no truth metadata, no privileged support labels and no generator internals.

Question:

> Once the correct candidate formulation is already specified, at which stage does the process lose power?

### 2.2 `BLIND_LIBRARY_DISCOVERY`

The evaluator receives a fixed library of ten opaque candidate IDs and applies the complete frozen search → select → evaluate procedure.

Question:

> Within a bounded preregistered search surface, can the process find true or legitimate proxy structure without selecting pure placebo structure?

This is a bounded discovery calibration. It is not unrestricted ML discovery, human feature engineering or independent confirmation after search.

---

## 3. Four-stage diagnostic contract

### `GROUND_TRUTH_VISIBLE`

Ground-truth-aware artifact diagnostic only. The true trigger may be used here after a world has been generated, but it is forbidden from candidate fitting, candidate selection, placebo generation and tie-breaking.

### `MODEL_DETECTED`

Literal conjunction:

```text
primary_positive
AND bootstrap_positive
AND placebo_separation
```

This asks whether the model/evaluation machinery sees incremental predictive structure before materiality and long-horizon stability requirements are applied.

### `STRICT_PASS_EX_MATERIALITY`

Literal conjunction:

```text
primary_positive
AND bootstrap_positive
AND placebo_separation
AND era_stability
AND support_sanity
```

### `STRICT_PASS`

```text
STRICT_PASS_EX_MATERIALITY
AND RELATIVE_MAE_IMPROVEMENT >= 0.02
```

The 2% pooled relative-MAE threshold is intentionally unchanged. It is an object of calibration, not a target to tune against synthetic outcomes.

---

## 4. Synthetic chronology

Each world has ordered rows `t = 0..N-1` and five equal contiguous eras `E1..E5`.

Primary size:

```text
N = 5000
```

SMALL sample-size sensitivity:

```text
N ∈ {2500, 10000}
```

`E1` is training only. Scored eras are `E2..E5` using expanding chronology:

- fit E1 → score E2;
- fit E1+E2 → score E3;
- fit E1+E2+E3 → score E4;
- fit E1+E2+E3+E4 → score E5.

Random split and future information are forbidden.

---

## 5. Frozen DGP

All continuous quantities are float64. RNG is NumPy `Generator(PCG64)`.

Baseline states:

```text
X1_t = 0.70*X1_(t-1) + sqrt(1-0.70^2)*U1_t
X2_t = 0.40*X2_(t-1) + sqrt(1-0.40^2)*U2_t
U1_t, U2_t ~ N(0,1)
X1_0 = X2_0 = 0
MU_BASE_t = 0.20*X1_t - 0.15*X2_t
```

The baseline is deliberately correctly specified. V1 therefore does **not** calibrate a candidate absorbing baseline-model misspecification.

### 5.1 Persistent sparse support

The original iid trigger is replaced pre-outcome by a persistent two-state Markov trigger `S_t`.

For each scenario with target stationary support `p`:

```text
rho = 0.90
P(S_t=1 | S_(t-1)=1) = rho
P(S_t=1 | S_(t-1)=0) = p01
p01 = p*(1-rho)/(1-p)
S_0 ~ Bernoulli(p)
TRUE_TRIGGER_t = S_t
```

Thus support is sparse **and clustered**. This stresses effective support rather than pretending positive rows are iid.

Mechanism-transition uniforms, `U1`, `U2` and noise innovations are mutually independent.

### 5.2 Noise

```text
RAW_t ~ StudentT(df=5) / sqrt(5/3)
ETA_t = 0.25*ETA_(t-1) + sqrt(1-0.25^2)*RAW_t
ETA_0 = 0
SIGMA_t = 1.0 + 0.30*abs(X1_t)
NOISE_t = SIGMA_t*ETA_t
```

Outcome:

```text
Y_t = MU_BASE_t + beta_t*TRUE_TRIGGER_t + NOISE_t
```

---

## 6. Frozen scenario ladder and pre-outcome scale audit

The red-team arithmetic showed that the original 2% pooled-MAE gate is above the best attainable pooled-MAE gain for every positive stationary rung. We freeze that fact **before execution** rather than hide it or increase beta until the test passes.

Approximate analytic references:

| scenario | support | beta | beta / residual SD | expected trigger rows at N=5000 | asymptotic max pooled relative-MAE improvement |
|---|---:|---:|---:|---:|---:|
| `NULL` | 10% generated support | 0.00 | 0.000 | 500 | 0.000% |
| `EASY` | 20% | 0.40 | 0.319 | 1000 | 1.07% |
| `MODERATE` | 10% | 0.25 | 0.200 | 500 | 0.24% |
| `SMALL` | 5% | 0.18 | 0.144 | 250 | 0.064% |
| `TINY_NOISY` | 2.5% | 0.12 | 0.096 | 125 | 0.014% |

Reference residual SD ≈ `1.253`; mean absolute noise ≈ `0.919`. These are pre-outcome analytic references, not calibration results.

The stationary scenarios are exactly:

- `NULL`: beta = 0;
- `EASY`: support 0.20, beta 0.40;
- `MODERATE`: support 0.10, beta 0.25;
- `SMALL`: support 0.05, beta 0.18;
- `TINY_NOISY`: support 0.025, beta 0.12.

Negative control:

```text
NONSTATIONARY_TRAP support = 0.10
beta(E1)=0.30
beta(E2)=0.30
beta(E3)=0.30
beta(E4)=0.00
beta(E5)=0.00
```

This tests a mechanism that appears stable early and then vanishes, rather than a trivial sign reversal.

A scale-matched diagnostic is mandatory:

```text
MATERIALITY_FRACTION_OF_ATTAINABLE
  = observed_RELATIVE_MAE_IMPROVEMENT
    / asymptotic_max_relative_mae_improvement_approx
```

Unavailable when the denominator is non-positive.

---

## 7. RNG authority

Root seed:

```text
20260908
```

World identity:

```text
HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|scenario|N|world_index
```

`world_index` is zero-based.

Seed derivation:

```text
raw = utf8(root_seed_decimal + "|" + identity_string)
digest = SHA256(raw)
seed_int = int.from_bytes(digest[:8], "big", signed=False)
rng = numpy.random.Generator(numpy.random.PCG64(seed_int))
```

Python `hash()` is forbidden. DGP, bootstrap, placebo and visibility use separate namespaces. Rerolling is forbidden.

---

## 8. Ten distinct discovery candidates

The following mapping is the **only authoritative mapping**:

```text
F01 = S_(t-1), with F01_0 = 0
F02 = S_t * I(X1_t > 0)
F03 = S_t                         # exact true feature
F04 = I(X1_t > 0)
F05 = I(X2_t > 0)
F06 = I(X1_t > 1)
F07 = I(X2_t < -1)
F08 = S_t * I(X2_t > 0)
F09 = I(X1_t + X2_t > 0)
F10 = I(X1_t - X2_t > 0)
```

Frozen classes:

```text
TRUE   = {F03}
PROXY  = {F01, F02, F08}
FALSE  = {F04, F05, F06, F07, F09, F10}
```

The discovery selector receives opaque IDs, not semantic class labels. No feature may be added or reclassified after outcomes.

---

## 9. Forecast family

Baseline:

```text
Y ~ intercept + X1 + X2
```

Candidate `Fj`:

```text
Y ~ intercept + X1 + X2 + Fj
```

Frozen estimator:

```text
numpy.linalg.lstsq(X, y, rcond=None)
```

Unweighted OLS, no regularization, full rank required, finite coefficients required, no pseudoinverse fallback, no column dropping. Baseline and candidate share exact scoring rows.

---

## 10. Prediction metrics

For every scored row:

```text
BASE_AE = abs(Y - BASE_PRED)
CAND_AE = abs(Y - CAND_PRED)
AE_IMPROVEMENT = BASE_AE - CAND_AE
```

Pooled:

```text
MEAN_AE_IMPROVEMENT = mean(AE_IMPROVEMENT)
RELATIVE_MAE_IMPROVEMENT = 1 - mean(CAND_AE)/mean(BASE_AE)
```

Truth-aware diagnostics, never usable for candidate selection:

- realized `SUPPORT_COVERAGE`;
- `SUPPORT_CONDITIONAL_MEAN_AE_IMPROVEMENT`;
- `OFF_SUPPORT_MEAN_AE_IMPROVEMENT`;
- support run-length distribution;
- support cluster count;
- raw positive-support count;
- effective-support-N design-effect diagnostic based on trigger autocorrelation.

This explicitly separates conditional utility/coverage from whole-population MAE dilution.

---

## 11. Ground-truth visibility

Using the same chronological baseline predictions:

```text
BASE_RESIDUAL = Y - BASE_PRED
VISIBILITY_STAT = mean(BASE_RESIDUAL | TRUE_TRIGGER=1)
                - mean(BASE_RESIDUAL | TRUE_TRIGGER=0)
```

Use 500 contiguous-50-row block-bootstrap replicates, never crossing era boundaries.

```text
GROUND_TRUTH_VISIBLE = visibility_bootstrap_q025 > 0
```

This truth-aware statistic is for attribution only. It is forbidden from model fitting, discovery, selection, placebo generation and tie-breaking.

---

## 12. Strict reference gates

Frozen gate order:

1. `primary_positive`: pooled `MEAN_AE_IMPROVEMENT > 0`;
2. `material_relative_mae`: `RELATIVE_MAE_IMPROVEMENT >= 0.02`;
3. `bootstrap_positive`: frozen bootstrap q025 of pooled mean AE improvement `> 0`;
4. `placebo_separation`: real pooled mean AE improvement `> placebo_q95`;
5. `era_stability`: mean AE improvement `> 0` in at least 3 of E2..E5;
6. `support_sanity`: evaluated candidate feature has at least 50 positive scored rows and finite/nonzero support.

For ORACLE `F03`, candidate-positive support equals the true trigger support. In BLIND mode, `support_sanity` is candidate-specific and does not expose true-support labels.

No hidden gate is allowed.

---

## 13. Bootstrap and placebo

### Bootstrap

- block size: 50 contiguous scored rows;
- no block crosses an era;
- 500 replicates;
- statistic: pooled mean `AE_IMPROVEMENT`;
- q025 uses linear quantile interpolation;
- no reroll.

### Placebo

- 999 replicates per evaluated candidate/world;
- candidate labels permuted separately within each scored era;
- Y, X1, X2 and row order stay fixed;
- same expanding-era model procedure is refit;
- statistic: pooled mean AE improvement;
- `placebo_q95` uses linear interpolation;
- all nominal replicates must be finite or placebo separation is false.

---

## 14. Monte Carlo size and interval policy

Primary scenarios:

```text
400 worlds × 6 scenarios = 2400 worlds
```

SMALL sample-size sensitivity:

```text
N=2500: 400 worlds
N=10000: 400 worlds
```

Total planned worlds:

```text
3200
```

Every reported Monte Carlo rate receives a Wilson score 95% interval.

Frozen decision policy:

- specificity passes only when the **Wilson upper bound** is at or below the maximum;
- power passes only when the **Wilson lower bound** is at or above the minimum;
- power fails only when the **Wilson upper bound** is below the minimum;
- if the interval straddles a threshold, result = `INDETERMINATE`.

Point estimates alone may not trigger a methodology consequence.

Failed worlds stay in the denominator and make the aggregate `INCOMPLETE_EXECUTION` unless the exact frozen execution is reproduced before outcomes are opened.

---

## 15. BLIND discovery taxonomy

Evaluate all ten candidates using the same frozen procedure.

Primary ex-materiality selector:

1. retain candidates with `STRICT_PASS_EX_MATERIALITY=true`;
2. choose maximum `MEAN_AE_IMPROVEMENT`;
3. exact tie → ascending `feature_id`;
4. none → `NO_CANDIDATE`.

Also report the analogous selection using full `STRICT_PASS`.

Every world receives exactly one ex-materiality discovery class:

```text
TRUE_DISCOVERY   = selected F03
PROXY_DISCOVERY  = selected F01/F02/F08
FALSE_DISCOVERY  = selected F04/F05/F06/F07/F09/F10
NO_DISCOVERY     = no selected candidate
ANY_EDGE_DECLARED = not NO_DISCOVERY
```

`BLIND_LIBRARY_NULL_FPR` is `ANY_EDGE_DECLARED` under NULL **after the complete search-select-evaluate procedure**, not a per-feature FPR.

No claim of independent confirmation is made from the same world used for search and selection.

---

## 16. Frozen acceptance/interpretation rules

### Specificity

Using Wilson **upper bounds**:

```text
ORACLE NULL MODEL_DETECTED FPR <= 0.05
BLIND full-pipeline NULL ANY_EDGE_DECLARED FPR <= 0.10
NONSTATIONARY_TRAP STRICT_PASS_EX_MATERIALITY detection <= 0.20
```

### Sanity power

Using Wilson **lower bounds**:

```text
EASY ORACLE MODEL_DETECTION >= 0.90
MODERATE ORACLE MODEL_DETECTION >= 0.70
```

### SMALL sensitivity bands

Bands use `MODEL_DETECTION_RATE`:

```text
HIGH       >= 0.80
MODERATE   >= 0.50 and < 0.80
LOW        >= 0.20 and < 0.50
VERY_LOW   < 0.20
```

A band label is allowed only if the **entire Wilson interval** lies inside one band; otherwise `INDETERMINATE`.

### Detection-floor attribution

For each difficulty region:

```text
if GROUND_TRUTH_VISIBLE Wilson upper < 0.50:
    VISIBILITY_FLOOR
elif MODEL_DETECTION Wilson upper < 0.50:
    MODEL_FLOOR
else:
    ABOVE_MEASURED_FLOOR
```

Materiality is reported separately by comparing `STRICT_PASS_EX_MATERIALITY` with `STRICT_PASS` and by `MATERIALITY_FRACTION_OF_ATTAINABLE`.

Thus a sparse edge can be classified as:

- statistically not visible at this effective support;
- visible but not captured by the model/evaluation procedure;
- captured and confirmatory-stable but rejected by the 2% pooled materiality floor;
- fully strict-pass.

---

## 17. Required result artifact

A future authorized production run must retain at least:

- exact implementation commit/tree;
- exact prereg MD/JSON blob identities;
- world/scenario/N/world-index identities and seeds;
- realized support and support-run statistics;
- support cluster count and effective-support-N diagnostic;
- pooled and support-conditional metrics;
- every gate boolean and raw gate statistic;
- `GROUND_TRUTH_VISIBLE`, `MODEL_DETECTED`, `STRICT_PASS_EX_MATERIALITY`, `STRICT_PASS` per world;
- materiality fraction of attainable ceiling;
- every discovery candidate result;
- selected feature and TRUE/PROXY/FALSE/NO_DISCOVERY taxonomy;
- aggregate rates with Wilson 95% intervals;
- SMALL N sensitivity;
- detection-floor reason labels;
- mechanically generated methodology conclusion.

---

## 18. B2-06 consequences

Synthetic calibration never authorizes market execution.

Frozen interpretations:

- specificity failure → `METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06`;
- EASY/MODERATE model-power failure → `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`;
- `VISIBILITY_FLOOR` → a comparable negative market result cannot strongly establish absence of edge;
- `MODEL_FLOOR` → model/evaluation sensitivity requires repair or an explicit power caveat before interpreting comparable `NO_PROMOTION`;
- materiality-only failure → record that the unchanged 2% pooled materiality criterion suppresses otherwise detectable sparse structure.

A materiality-only finding does **not** authorize changing a market gate. Any such change requires a separate outcome-blind preregistration.

`INDETERMINATE` produces no binary methodology claim and cannot be resolved by tuning thresholds on the same outcomes.

---

## 19. Anti-rescue

After any production synthetic outcome is opened, forbidden changes include:

- lowering the 2% gate;
- changing beta, support, rho, noise, scenario definitions or sample sizes;
- changing which diagnostic layer drives a conclusion;
- dropping hard/failed worlds;
- seed selection or reroll;
- denominator replacement;
- candidate addition or proxy reclassification;
- sign reversal;
- bootstrap/block/placebo changes;
- treating synthetic success as market evidence.

Any scientific change after outcome opening requires a new calibration version.

---

## 20. Execution ceremony

Required order:

1. independent red-team accepts this repaired prereg;
2. implementation is written using synthetic fixture tests only;
3. implementation is independently reviewed without production-grid execution;
4. exact implementation commit/tree is frozen;
5. one production calibration is explicitly authorized;
6. complete result is persisted before methodology changes;
7. outcomes are inspected once;
8. any subsequent methodology change becomes a new version.

Current state:

```text
implementation_exists = false
production_calibration_executed = false
synthetic_execution_authorized = false
```
