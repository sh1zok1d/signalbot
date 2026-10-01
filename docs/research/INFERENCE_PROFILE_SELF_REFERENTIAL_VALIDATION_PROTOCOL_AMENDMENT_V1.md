# Pre-validation protocol amendment

**Amends:** the finite-sample validation protocol and execution architecture of `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Does not amend:** `PRIMARY_METHOD`, the target-confirmatory procedure, `R_CONFIRMATORY`, the global null, the inference statistic, the bandwidth rule, the multiplier law, the maintained assumptions, or any D7 scientific status.

**Status:** `VALIDATION_PROTOCOL_AMENDED = true`

No official held-out validation of this profile has been executed. The earlier `9559` counts exist only as unexecuted contract text. This amendment is therefore before first official validation, and it does not open a new profile id.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`R_CONFIRMATORY = 9999`

`R_VALIDATION = 999`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`PROFILE_VALIDATION_EXECUTED = false`

`D7_GEOMETRY_ADMISSION_EXECUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

The frozen contract file is unchanged. Where it sets a per-configuration `9559` Wilson screen, this amendment replaces that validation protocol.

## 1. Purpose of the finite-sample screen

`SCREEN_PURPOSE = MATERIAL_ANTICONSERVATISM_SCREEN`

The screen looks for materially inflated rejection rates, especially around or above `0.07`. It does not claim `TRUE_TYPE_I <= 0.06`.

## 2. Generic aggregate gate

`GENERIC_OUTER_WORLD_N = 1600`

The 1600 worlds are allocated across the envelope-resolution generic design by the deterministic rule in section 4. The design factors are `T ∈ {2048, 16384, 65536}`, `J ∈ {1, 4}`, gap `none` or one interior split, and the gating laws `IID_BERNOULLI`, `INTERLACED_LAG2`, `MA_EVEN`, `CANCELLING_CELLS`, `VARIANCE_REGIMES`, and `LABEL_MARKOV`. Laws `ρ = 0.98` and label stay `0.99` stay outside the screen.

Generic worlds use `H_mechanical = 0`, so the executed bandwidth is the cube-root branch. The binding mechanical floor is not a generic-screen factor. It is measured as a compute case and is the subject of exact-geometry admission.

`GENERIC_REJECT_COUNT <= 95`

Binomial pass probabilities of that count gate, `Bin(1600, p)`:

| true rejection probability | P(count ≤ 95) |
| --- | --- |
| 0.050 | 0.959443 |
| 0.055 | 0.796123 |
| 0.060 | 0.485162 |
| 0.065 | 0.195353 |
| 0.070 | 0.050353 |
| 0.075 | 0.008395 |

These are the operating characteristics of the frozen count. They match the predeclared approximate targets `0.959, 0.796, 0.485, 0.195, 0.050, 0.008`. The gate is built to detect material anticonservatism around 7% or greater. It is not a proof of a 6% ceiling.

## 3. Regional catastrophe guard

The same 1600 worlds are partitioned into 8 regions of 200 before any official execution.

| region | laws |
| --- | --- |
| `R1_IID_BERNOULLI` | Bernoulli `0.25` |
| `R2_INTERLACED_WEAK` | interlaced `ρ ∈ {0, 0.25, 0.50}` |
| `R3_INTERLACED_STRONG` | interlaced `ρ ∈ {0.75, 0.90}` |
| `R4_MA_EVEN` | the three even moving-average laws |
| `R5_CANCELLING_CELLS` | the three cancelling coefficients |
| `R6_VARIANCE_REGIMES` | both variance schedules |
| `R7_LABEL_MARKOV_MODERATE` | stay `∈ {0.50, 0.80}` |
| `R8_LABEL_MARKOV_PERSISTENT` | stay `0.95` |

Every region is crossed with the full `(T, J, gap)` list. Within a region, worlds are dealt to configurations in lexicographic `configuration_id` order. The first `200 mod n_configs` configurations receive one extra world. No worlds are added for the guard.

A region fails when `REGION_REJECT_COUNT >= 21`.

The aggregate gate and every regional gate must pass. The regional rule stops a mild average from hiding one anticonservative geometry region.

## 4. Exact-geometry admission

`D7_ADMISSION_OUTER_WORLD_N = 1600`

`D7_REJECT_COUNT <= 95`

Admission uses one adapter-supplied exact geometry and the same gating law list. Worlds are dealt across those laws by the same remainder rule. There is no regional split on this suite: the suite is one geometry, and the aggregate count is the finite-sample protection specified for it.

The real state path and the real label trajectory are not inputs. This unit does not run the suite.

## 5. Validation bootstrap size

`R_VALIDATION = 999`

`p_r = (1 + #{T*_b >= T_obs}) / 1000`

`R_VALIDATION + 1 = 1000`, so level `0.05` is on the lattice. A validation world rejects when `p_r <= 0.05`, which is exceedance count `<= 49`.

`R_CONFIRMATORY = 9999` remains the target procedure. Validation worlds do not use it.

Ties use `>=`.

## 6. High-R diagnostic

`HIGH_R_DIAGNOSTIC_N = 200`, with `R = 9999`, purpose `HIGH_R_DIAGNOSTIC`.

Twenty-five worlds are dealt to each generic region by the same remainder rule. The suite is `NON_GATING_R_SENSITIVITY`. It may compare decisions or p-values between `R = 999` and `R = 9999`. It does not change either gate, `R_VALIDATION`, the method, or any parameter.

## 7. Execution architecture

Bartlett variance uses the moving-sum identity

`x' K_B x = (1/B) * sum_u (sum_{j=0}^{B-1} x_{u+j})^2`

with zeros outside each structural segment, cumulative sums, and the same operator for the observed and bootstrap studentizers.

Gaussian multipliers use

`eta_t = L^{-1/2} * sum_{j=0}^{L-1} epsilon_{t-j}`,

`epsilon ~ iid N(0,1)`, with `L - 1` presample shocks on each segment, no wrap-around, and no shock shared across a gap. `L_T = B_T`.

The runner is a process pool over outer worlds. It is not one process per bootstrap draw. `--workers N` selects the pool size. `workers = 1` is the reference mode. The default is `min(cpu_count, 8)` and is an execution choice, not a statistical constant. Each worker sets `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` to `1`.

Chunk size is an execution parameter. Draw batch size is an execution parameter. Neither enters the seed. Draws are indexed by `(world entropy, draw index, segment index)`, so a batch may be computed without changing the stream. Worlds are not stacked into a `1600 × R × T` multiplier array.

Before gates, records are sorted by `(suite_id, configuration_id, world_index)`.

World entropy is HMAC-SHA256 under the master validation seed, with message fields suite, configuration, world index, and purpose. The master seed is SHA-256 of the canonical string

`SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1/VALIDATION_PROTOCOL_AMENDMENT_V1/MASTER_VALIDATION_SEED`.

It is not the confirmatory beacon stream. The confirmatory message builder remains the freeze-amendment HMAC and is not expanded here.

A bootstrap variance failure or an implementation error fails the screen closed. The world is not dropped, not replaced, and not counted as a tail event.

## 8. Status words

`FINITE_SAMPLE_STRESS_VALIDATED` means the predefined 1600-world generic screen passed its aggregate gate and all eight regional gates. It does not mean `true type I <= 0.06`.

`HYPOTHESIS_GEOMETRY_ADMISSION_PASS` means the predefined 1600-world exact-geometry screen passed its aggregate gate.

`PROFILE_VALIDATION_DESIGN` remains the finite anchor list. `PROFILE_VALIDATED_DOMAIN` remains the subset of those anchors that have passed. Neither admits a geometry by interpolation. Both objects exist. Neither screen has been executed.

## 9. What stays frozen after the first official world

Once the first official validation world of either screen is executed, the following stay fixed: both outer sample sizes, the region map, `R_VALIDATION`, the p-value rule, the allocation, the DGP parameters, the seeds, the worker-independent RNG map, and both count thresholds. A later performance change is allowed only when it is bit-identical on the result records. No statistical redesign follows a partial official result.

This unit executes none of those official worlds. The development benchmark is a separate purpose and is not a screen.
