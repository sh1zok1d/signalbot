# HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — Frozen Design Preregistration

**Status:** `PREREG_CANDIDATE_OUTCOME_BLIND`  
**Unit ID:** `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1`  
**Unit type:** methodology calibration, not a market hypothesis  
**Base main at design start:** `79f68df395ecdda064386050d4d280cb994c4bbf`  
**This document:** design-only. No synthetic execution, no real-market outcome access, no B2-06 evaluator, no 2025 validation, no 2026 OOS.

Machine-readable twin: [`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json`](HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PREREG.json).

---

## 0. Purpose and authority

Signalbot currently has strong defenses against false edge: outcome-blind preregistration, same-support comparison, causal availability rules, placebo controls, block bootstrap, stability gates, anti-rescue rules, exact Git/evidence authority, and untouched validation/OOS boundaries.

The unresolved methodological question is different:

> Has the research process become so conservative that it is good at proving the absence of strong/simple edge but has low power for small, noisy, sparse, conditional edge?

This unit calibrates the measurement instrument itself before B2-06 scientific execution.

It does **not** attempt to prove that any market edge exists. Synthetic data are not market evidence and may never be cited as market validation.

The calibration becomes a mandatory methodology gate before the first B2-06 scientific outcome is opened.

`B2-06_LEVERAGE_CROWDING` remains separately blocked by `FUNDING_PUBLICATION_LATENCY_UNPROVEN`. Passing this calibration does not authorize B2-06 data consumption or execution.

---

## 1. Explicit non-goals and hard boundaries

This design unit does not:

- read CORE, OI, funding, market parquet, exchange APIs, or any real market dataset;
- inspect or derive B2-06 predictive outcomes;
- open 2025 validation or 2026 OOS;
- modify `docs/research/V2_FORMULATION_INVENTORY.md`;
- rerun B2-01 through B2-05;
- reopen B2-05 recovery;
- create a B2-07 hypothesis;
- promote any market candidate;
- claim that a synthetic pass implies tradeability, PnL, or economic alpha;
- weaken provenance/no-lookahead/evidence-retention guarantees.

Frozen flags for this unit:

```text
synthetic_execution_authorized = false
real_market_data_access_authorized = false
b2_06_scientific_execution_authorized = false
validation_2025_authorized = false
oos_2026_authorized = false
```

No implementation runner may be added in the design-only PR. The implementation/execution PR is a later unit after independent red-team acceptance of this preregistration.

---

## 2. What V1 is and is not calibrating

V1 separates two questions that must not be conflated.

### 2.1 ORACLE_CONFIRMATORY mode

The evaluator is explicitly given the correct candidate feature representing the injected mechanism.

Question:

> If the formulation is already correct, can a Signalbot-style strict confirmatory gate detect a small noisy conditional increment over a baseline?

This diagnoses **confirmatory power**. Failure here means the harness can miss a real edge even after the correct mechanism has already been specified.

### 2.2 BLIND_LIBRARY_DISCOVERY mode

The evaluator receives a fixed, preregistered library of candidate features under generic feature identities. Exactly one library member is the true injected mechanism in positive worlds; none is true in null worlds.

Question:

> Given a bounded preregistered search surface, can the process identify a sparse conditional mechanism without selecting placebo structure?

This diagnoses **bounded discovery sensitivity**.

V1 does **not** claim to calibrate unrestricted ML discovery, arbitrary feature engineering, threshold mining, or open-ended human hypothesis generation. If BLIND_LIBRARY_DISCOVERY performs poorly while ORACLE_CONFIRMATORY performs well, the conclusion is specifically that the bottleneck is discovery/search rather than strict confirmation.

---

## 3. Primary estimand

The primary output is a detection surface, not a single PASS/FAIL world:

```text
P(DETECT | scenario, support, injected_effect, sample_size, noise_profile)
```

with a paired false-positive surface under null/placebo worlds.

Primary methodology outputs:

1. `ORACLE_DETECTION_RATE` for each positive scenario;
2. `BLIND_DISCOVERY_RATE` for each positive scenario;
3. `NULL_FALSE_POSITIVE_RATE` for confirmatory and discovery modes;
4. gate-level attrition rates showing which required gate rejected the true mechanism;
5. a declared `DETECTION_FLOOR` region where the process has insufficient power to interpret `NO_PROMOTION` as strong evidence of no edge.

The calibration is diagnostic. It is forbidden to redefine success criteria after seeing the Monte Carlo results.

---

## 4. Synthetic timeline and unit of observation

Each synthetic world contains an ordered sequence of decision-time observations indexed by integer `t = 0..N-1`.

There are no timestamps corresponding to real dates. Synthetic chronology exists only to test causal training, serial dependence, chronological stability, and block resampling.

Each row contains only synthetic fields generated at or before synthetic decision time `t` plus target `Y_t` for evaluation. No field may depend on future synthetic rows except the target-generating innovation for that row.

Primary sample size:

```text
N = 5000 rows per world
```

Sample-size sensitivity for the SMALL scenario only:

```text
N ∈ {2500, 10000}
```

The primary chronological partitions are five equal contiguous eras `E1..E5`, each containing exactly `N/5` rows for N divisible by 5.

---

## 5. Frozen base data-generating process

All continuous synthetic quantities use IEEE-754 float64 and NumPy `Generator(PCG64)` semantics in the future implementation. No global `numpy.random` state is permitted.

For each world, generate two causal baseline states:

```text
X1_t = 0.70 * X1_(t-1) + sqrt(1-0.70^2) * U1_t
X2_t = 0.40 * X2_(t-1) + sqrt(1-0.40^2) * U2_t
U1_t, U2_t ~ iid Normal(0,1)
X1_0 = X2_0 = 0
```

Generate two binary mechanism components independently of the baseline states:

```text
A_t ~ Bernoulli(q)
B_t ~ Bernoulli(q)
TRUE_TRIGGER_t = A_t * B_t
q = sqrt(target_support)
```

Thus expected trigger prevalence is `target_support`; realized support is reported and never forced by outcome-aware resampling.

The true mechanism is an **interaction**. Neither A nor B alone carries injected alpha.

Baseline conditional mean:

```text
MU_BASE_t = 0.20*X1_t - 0.15*X2_t
```

Primary heavy-tail/heteroskedastic/serial noise:

```text
RAW_t ~ StudentT(df=5) / sqrt(5/3)
ETA_t = 0.25*ETA_(t-1) + sqrt(1-0.25^2)*RAW_t
SIGMA_t = 1.0 + 0.30*abs(X1_t)
NOISE_t = SIGMA_t * ETA_t
ETA_0 = 0
```

The Student-t scale factor normalizes the independent innovation to unit variance before serial/heteroskedastic transformation.

Synthetic outcome:

```text
Y_t = MU_BASE_t + beta * TRUE_TRIGGER_t + NOISE_t
```

All positive primary scenarios use `beta > 0`. Post-result sign reversal is forbidden.

This is intentionally not a market simulator. The goal is to reproduce methodological difficulties: small support, baseline structure, heavy tails, heteroskedasticity, serial dependence, chronological evaluation, and incremental rather than unconditional signal.

---

## 6. Frozen primary scenario ladder

Exactly these primary scenarios are preregistered:

| Scenario | Expected support | beta | Purpose |
|---|---:|---:|---|
| `NULL` | 0% effective injected edge | 0.00 | false-positive control |
| `EASY` | 20% | 0.40 | sanity check; should be visible |
| `MODERATE` | 10% | 0.25 | ordinary conditional edge |
| `SMALL` | 5% | 0.18 | primary concern: small sparse edge |
| `TINY_NOISY` | 2.5% | 0.12 | stress/detection-floor case |
| `NONSTATIONARY_TRAP` | 10% | +0.30 in E1-E2; 0 in E3; -0.30 in E4-E5 | stability negative control |

For `NULL`, A/B/trigger features are still generated with q corresponding to 10% expected trigger support, but beta is zero. This prevents the null case from being trivially identifiable because the candidate feature is absent.

For `NONSTATIONARY_TRAP`, the average injected effect is intentionally not a stable positive edge. A correct strict methodology should **not** treat it as a robust detection even if pooled statistics look attractive in some Monte Carlo worlds.

Primary Monte Carlo worlds:

```text
200 independent worlds per primary scenario
```

Additional sample-size sensitivity:

```text
SMALL at N=2500: 200 worlds
SMALL at N=10000: 200 worlds
```

Total planned primary/sensitivity worlds = `6*200 + 2*200 = 1600`.

No new scenario may be added after any calibration outcome is observed. A future V2 requires a new preregistration.

---

## 7. Frozen RNG authority

Root seed literal:

```text
20260908
```

Each world seed is derived from the UTF-8 bytes of:

```text
HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|scenario|N|world_index
```

where `world_index` is zero-based integer `0..199`.

Derivation primitive:

```text
digest = SHA256(root_seed_decimal + "|" + identity_string)
seed_int = int.from_bytes(digest[0:8], byteorder="big", signed=False)
rng = numpy.random.Generator(numpy.random.PCG64(seed_int))
```

Exact serialization, SHA-256 primitive, first-eight-byte slice, big-endian interpretation, and zero-based world index are frozen. Python `hash()` is forbidden.

Bootstrap/permutation RNG must use separately namespaced seed identities and must never consume the generator stream used for the DGP.

---

## 8. Candidate library for bounded discovery

The discovery search surface is fixed before outcomes.

The future implementation must expose generic names `F01..F12` to the discovery evaluator. The mapping to semantic feature definitions is frozen in code/spec before execution and must not be changed between worlds.

Candidate library:

```text
F01 = A
F02 = B
F03 = A*B                         # true interaction in positive worlds
F04 = 1-A
F05 = 1-B
F06 = XOR(A,B)
F07 = I(X1 > 0)
F08 = I(X2 > 0)
F09 = I(X1 > 1)
F10 = I(X2 < -1)
F11 = A * I(X1 > 0)
F12 = B * I(X2 < 0)
```

No thresholds other than the literals above may be searched. No polynomial, tree, neural net, spline, alternate interaction, regime split, continuous transform, or candidate invented after results.

The true feature is F03 by construction, but the discovery evaluator may not receive a privileged `TRUE_TRIGGER` flag or truth metadata.

Discovery may evaluate all 12 candidates using the same frozen procedure. Candidate selection uses the preregistered deterministic rule in Section 13.

---

## 9. Baseline and candidate forecast families

The synthetic comparison intentionally follows the common Signalbot incremental-information pattern rather than copying one market hypothesis verbatim.

Baseline model:

```text
Y ~ intercept + X1 + X2
```

Candidate model for feature `Fj`:

```text
Y ~ intercept + X1 + X2 + Fj
```

Estimator: unweighted ordinary least squares.

Frozen solver contract:

- float64;
- `numpy.linalg.lstsq(X, y, rcond=None)`;
- intercept included;
- no regularization;
- no feature standardization required because X1/X2 are already controlled synthetic states and Fj is binary;
- full returned rank required;
- finite coefficients required;
- no pseudoinverse fallback;
- no column dropping;
- no ridge/lasso rescue;
- candidate and baseline scored on exact same evaluation rows.

The only allowed information increment is one frozen candidate feature.

---

## 10. Chronological fitting and evaluation

Use expanding chronological prediction with five eras.

- `E1` is warm-up/training only and never scored.
- Fit on all rows strictly earlier than the scored era.
- Score `E2`, then refit using `E1+E2` and score `E3`, continuing through `E5`.
- A row's target may enter training only after that row is chronologically before the scored era.
- No random train/test split.
- No future-era information in transforms, thresholds, feature choice, or fit.

The primary evaluation support is the pooled score rows from `E2..E5`, with era identity retained for stability gates.

Both baseline and candidate must be available on the exact same rows. A candidate-specific support filter is forbidden.

---

## 11. Primary incremental metric

For each scored row:

```text
BASE_AE_t = abs(Y_t - BASE_PRED_t)
CAND_AE_t = abs(Y_t - CAND_PRED_t)
AE_IMPROVEMENT_t = BASE_AE_t - CAND_AE_t
```

Pooled metrics:

```text
MEAN_AE_IMPROVEMENT = mean(AE_IMPROVEMENT)
RELATIVE_MAE_IMPROVEMENT = 1 - mean(CAND_AE)/mean(BASE_AE)
```

Positive values favor the candidate.

No PnL, Sharpe, hit-rate, directional trade simulation, transaction cost, or market interpretation is permitted in V1.

---

## 12. Strict reference gate

The strict reference gate is designed to expose where a Signalbot-style confirmatory process loses power. It is not retroactively claimed to be identical to every Batch02 hypothesis.

A candidate `STRICT_PASS = true` only if all of the following are literal true:

1. `primary_positive`: pooled `MEAN_AE_IMPROVEMENT > 0`;
2. `material_relative_mae`: `RELATIVE_MAE_IMPROVEMENT >= 0.02`;
3. `bootstrap_positive`: lower 2.5% bound of the frozen block-bootstrap distribution of pooled mean AE improvement is `> 0`;
4. `placebo_separation`: real pooled mean AE improvement is strictly greater than the 95th percentile of the frozen within-era candidate-label permutation distribution;
5. `era_stability`: pooled mean AE improvement is `> 0` in at least 3 of 4 scored eras (`E2..E5`);
6. `support_sanity`: realized candidate-positive support among scored rows is finite, nonzero, and at least 50 rows.

The 2% relative-MAE threshold is intentionally retained as a strict reference because this type of materiality floor already exists in Batch02 methodology. The calibration is allowed to reveal that this gate is too insensitive; it may not lower the threshold after seeing results.

Gate-level booleans and raw statistics must be reported for every world so power loss can be attributed to a specific criterion rather than hidden behind the conjunction.

---

## 13. Block bootstrap and placebo contract

### 13.1 Bootstrap

Synthetic rows are partitioned into contiguous non-overlapping blocks of 50 scored rows within each era. No block crosses an era boundary.

Use 500 bootstrap replicates per evaluated candidate/world.

For each replicate, sample the same number of blocks with replacement from the pooled ordered block list and compute pooled mean `AE_IMPROVEMENT` over concatenated whole blocks.

Bootstrap seed identity:

```text
HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|BOOTSTRAP|scenario|N|world_index|feature_id
```

Seed derivation uses the same SHA-256/first-8-big-endian primitive, but a distinct namespace from DGP generation.

No reroll of failed replicates. Any nonfinite replicate invalidates `bootstrap_positive` for that candidate/world.

### 13.2 Placebo permutation

Use 100 permutation replicates per candidate/world.

Permutation is performed **within each scored era separately** on the candidate feature labels, leaving `Y`, X1, X2, row order, and baseline predictions fixed. The candidate model is refit under the same expanding-era rules for each placebo replicate.

Placebo seed identity:

```text
HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1|PLACEBO|scenario|N|world_index|feature_id|replicate_index
```

Replicate index is zero-based.

The placebo statistic is pooled mean `AE_IMPROVEMENT`.

`placebo_q95` is valid only if all 100 placebo statistics are finite. Quantile method = NumPy `linear`.

---

## 14. ORACLE_CONFIRMATORY decision

In ORACLE mode only F03 is evaluated.

For each world:

```text
ORACLE_DETECTED = STRICT_PASS(F03)
```

The evaluator may know that F03 is the candidate being tested, but may not inspect scenario truth, beta, or realized injected outcome contribution while computing the gate.

Primary ORACLE outputs are detection rates across the 200 worlds per scenario and exact binomial Wilson 95% confidence intervals.

---

## 15. BLIND_LIBRARY_DISCOVERY decision

All 12 candidates are evaluated with the same strict reference gate.

Selection rule:

1. retain candidates with `STRICT_PASS = true`;
2. among retained candidates, choose the largest `MEAN_AE_IMPROVEMENT`;
3. ties at exact float equality resolve by ascending generic feature ID (`F01` before `F02`, etc.);
4. if none pass, discovery returns `NO_CANDIDATE`.

World-level discovery outcomes:

```text
TRUE_DISCOVERY      = selected_feature == F03
FALSE_DISCOVERY     = selected_feature not in {F03, NO_CANDIDATE}
NO_DISCOVERY        = selected_feature == NO_CANDIDATE
```

For `NULL`, there is no true candidate. Any selected feature is a false positive.

For `NONSTATIONARY_TRAP`, selecting F03 still does not count as successful robust detection if F03 fails the strict gate. The expected scientific behavior is usually `NO_CANDIDATE`; the realized rate is measured, not assumed.

No top-k rescue, manual inspection rescue, sign reversal, threshold rescue, or second selection rule is allowed.

---

## 16. Calibration acceptance and interpretation rules

The project needs both specificity and sensitivity. Therefore the calibration produces separate conclusions rather than one opaque global verdict.

### 16.1 Specificity criterion

For the 200 primary `NULL` worlds:

```text
ORACLE_NULL_FPR <= 0.05
BLIND_LIBRARY_NULL_FPR <= 0.10
```

The discovery FPR allowance is wider because it tests 12 preregistered candidates, but a 10% false-discovery frequency remains the maximum acceptable calibration target.

`NONSTATIONARY_TRAP` robust-detection rate must be `<= 0.20` in ORACLE mode. Higher values indicate that the stability contract is too permissive.

### 16.2 Sanity-power criterion

```text
ORACLE EASY detection rate >= 0.90
ORACLE MODERATE detection rate >= 0.70
```

Failure means the strict reference process is too insensitive even to effects that this calibration considers non-marginal.

### 16.3 SMALL-edge sensitivity classification

`SMALL` is deliberately not assigned an arbitrary must-pass threshold before calibration. Instead classify observed ORACLE power using frozen bands:

```text
>= 0.80  => HIGH_SENSITIVITY
0.50-0.799999... => MODERATE_SENSITIVITY
0.20-0.499999... => LOW_SENSITIVITY
< 0.20  => VERY_LOW_SENSITIVITY
```

This is the central diagnostic result.

If `SMALL` ORACLE sensitivity is below 0.50, future `NO_PROMOTION` outcomes for hypotheses believed to live in a comparable sparse/noisy regime must not be described as strong evidence of absence without a power caveat.

### 16.4 Detection floor

A scenario is inside the declared `DETECTION_FLOOR` if ORACLE detection rate is `< 0.50`.

The detection-floor label is a statement about harness sensitivity under the synthetic DGP, not a statement about market truth.

### 16.5 Discovery bottleneck diagnosis

For each positive scenario compute:

```text
DISCOVERY_GAP = ORACLE_DETECTION_RATE - BLIND_DISCOVERY_RATE
```

Interpretation:

- small gap + low oracle power => confirmatory strictness/statistical power bottleneck;
- large gap + adequate oracle power => bounded discovery/search bottleneck;
- both adequate => no synthetic evidence in V1 that either layer is grossly underpowered for that scenario.

No business/product claim follows from these labels.

---

## 17. Gate attrition diagnosis

For F03 in every positive world, record the first failed gate in this frozen order:

```text
primary_positive
material_relative_mae
bootstrap_positive
placebo_separation
era_stability
support_sanity
PASS
```

Also retain all gate booleans independently; the first-failure view is only a diagnostic summary.

This matters because a low detection rate caused primarily by the 2% materiality floor requires a different methodology discussion from low detection caused by bootstrap uncertainty or chronological instability.

Changing/removing a gate after observing attrition is forbidden inside V1. Any repair becomes `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2` or a separately preregistered methodology revision.

---

## 18. Required output artifact

The future execution must produce one immutable machine-readable result with at least:

- exact code Git commit/tree;
- exact prereg MD/JSON blob identities;
- schema/version;
- root seed and seed-derivation contract;
- scenario definitions;
- world count expected/completed/failed;
- per-world realized support;
- per-world raw pooled metrics;
- per-world six gate booleans;
- per-world first failed gate;
- ORACLE detection outcome;
- all 12 discovery candidate outcomes;
- selected discovery feature;
- aggregate detection/FPR rates;
- Wilson 95% intervals;
- sample-size sensitivity results;
- detection-floor labels;
- explicit conclusion text generated mechanically from frozen rules.

Partial world subsets may not silently replace the planned denominator. Any failed world remains in the denominator and makes aggregate calibration `INCOMPLETE_EXECUTION` unless the failure is repaired and the entire exact planned run is reproduced under the same frozen code identity before result opening.

No hand-edited summary may override machine-readable results.

---

## 19. Blinding and anti-tuning ceremony

V1 does not rely on secrecy as its primary protection; it relies on freeze-before-outcome discipline. Nevertheless the future implementation should preserve separation between truth and evaluation interfaces.

Required execution ordering:

1. independent red-team accepts this preregistration;
2. implementation PR is written against this frozen design using synthetic fixture tests only;
3. implementation PR is independently reviewed without running the 1600-world production calibration;
4. exact implementation commit/tree is frozen;
5. one production calibration execution is authorized;
6. result artifact is persisted before any methodology change;
7. only then may humans inspect aggregate calibration outcomes and gate attrition;
8. any methodology change creates a new frozen version and may not overwrite V1 results.

During evaluation, the API used by BLIND_LIBRARY_DISCOVERY must expose only generic feature IDs and must not expose a boolean `is_true_feature`, beta, injected contribution, or scenario-specific hand tuning hook.

Synthetic fixture/unit tests may use tiny toy worlds with explicit expected answers. They must not execute the frozen production seed/scenario grid before authorization.

---

## 20. Anti-rescue rules

After V1 calibration outcomes are opened, all of the following are forbidden as V1 reinterpretation:

- lowering the 2% materiality gate and calling the same run a pass;
- changing beta/support definitions;
- dropping hard worlds;
- increasing N only for failed scenarios and replacing the primary result;
- changing Student-t df, AR coefficient, heteroskedasticity, eras, block size, bootstrap count, permutation count, or candidate library;
- selecting only favorable seeds;
- replacing denominator 200 with successful worlds only;
- redefining true discovery to include correlated placebo features;
- adding feature candidates after seeing which pattern would have worked;
- treating `TINY_NOISY` failure as proof of methodological failure without considering its preregistered stress-test role;
- treating synthetic success as evidence of real B2-06 edge.

A methodology modification is allowed only in a new preregistered unit with V1 retained as historical calibration evidence.

---

## 21. Decision consequences for B2-06

This calibration is a mandatory **methodology gate**, not a scientific B2-06 result.

After V1 execution:

### Case A — specificity fails

If NULL FPR or NONSTATIONARY_TRAP control exceeds its frozen bound:

```text
METHODOLOGY_REPAIR_REQUIRED_BEFORE_B2_06
```

B2-06 remains blocked even if funding publication authority is later solved.

### Case B — EASY or MODERATE oracle power fails

```text
METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06
```

The current strict process is not trusted to interpret B2-06 failure.

### Case C — specificity and sanity power pass, SMALL is low

B2-06 may later proceed only after its own data/legal gates are solved and preregistration is frozen, but any negative interpretation must carry the calibration's detection-floor caveat if B2-06 effective support/effect regime is comparable.

This result may motivate a separately preregistered discovery-methodology improvement before B2-06; it does not automatically authorize changing B2-06 after outcomes.

### Case D — specificity and sanity power pass, SMALL sensitivity is moderate/high

No methodology repair is required by V1. This still does not solve funding availability and does not authorize real outcomes.

---

## 22. Design acceptance gate

This preregistration is not frozen merely because it is committed.

Before any implementation/execution:

- independent adversarial review must verify the DGP mathematics, RNG identity, null/control logic, chronological causal semantics, gate definitions, discovery multiplicity behavior, denominator policy, and anti-rescue boundary;
- all Blockers and Majors must be closed;
- accepted exact HEAD/tree must be recorded;
- then status may advance from `PREREG_CANDIDATE_OUTCOME_BLIND` to `FROZEN_BEFORE_IMPLEMENTATION`.

Until then:

```text
synthetic_execution_authorized = false
```

---

## 23. Why this calibration exists

A rigorous research harness has two independent failure modes:

1. it may be too permissive and manufacture edge from noise;
2. it may be too conservative and systematically erase real but small conditional information.

Signalbot has spent substantial effort defending against the first failure mode. `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1` makes the second failure mode measurable before more negative market results are interpreted too strongly.

The desired outcome is not that every injected edge passes. The desired outcome is that we know, quantitatively and before B2-06, **what size/support/noise regime the current methodology can and cannot see**.
