# D7 power gate

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `D7_POWER_GATE_PASS`

**Executed implementation:** `ebb26aca6ed37c12bbf3b3f578973d3078407d99`

**Execution HEAD:** `33359c73ccbc4b70e55551570327737c4ad9a41b`

This is the outcome-blind power gate after generic validation (`75 / 1600`) and D7 exact-geometry admission (`73 / 1600`). Those screens were not rerun. The protected BitMEX target stays closed.

## A. Code identity

| Item | Value |
| --- | --- |
| Branch at execution | `cursor/d7-power-gate-v1-c58d` |
| HEAD | `33359c73ccbc4b70e55551570327737c4ad9a41b` |
| Tree | `05c907c35ff05057260108620a7da36cf3ea53ce` |
| Working tree | clean |
| Audited implementation | `ebb26aca6ed37c12bbf3b3f578973d3078407d99` |
| Diff of `scripts/research/self_referential_contrast_v1` | empty |
| `STATISTICAL_IMPLEMENTATION_CHANGED` | false |

Primary method: `STUDENTIZED_FULL_IF_DWB`. `B_T = L_T = 721`.

## B. Frozen practical effect

`D7_PRACTICAL_EFFECT = 1/20` (`0.05`).

Provenance:

- `scripts/research/discovery_sprint_02_impl.py` sets `D7_PRACTICAL_GATE = 0.05`.
- `docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.md` section L sets the D7 power alternative at population `delta = 0.05`. Section M lists the practical threshold `0.05`.
- `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_NULL_AMENDMENT_V1.md` carries the same adapter threshold.

The BitMEX support-unit contrast is not the alternative.

## C. Frozen power requirement

From the D7 power admission in `INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.md` section L:

- `N = 2000` simulations at population `delta = 0.05`
- base power `>= 0.80`
- stress power `>= 0.50`
- both bars determine pass
- `R = 999` (`R_VALIDATION`), not `R_CONFIRMATORY = 9999`

`D7_REQUIRED_POWER_BASE = 0.80`

`D7_REQUIRED_POWER_STRESS = 0.50`

`GV0R02_POLICY_V0` uses `TARGET_POWER = 0.80`. The D7-specific stress bar remains `0.50`.

The count and the bars were written into the manifest before world 0. Wilson intervals report Monte Carlo uncertainty and do not move the thresholds.

## D. Alternative family

Labels are the published contiguous year × RV margins. States are synthetic. Each same-cell lead uses a mean-preserving Bernoulli shift. A cell-boundary lead is an independent marginal draw. The gap at eligible index `3503` is not crossed.

`g` of the expected moments is exactly `1/20` in each family. Cell coefficients are the manifest fractions.

| Family | Role | Population year contrasts |
| --- | --- | --- |
| `HOMOGENEOUS_EFFECT` | BASE | `1/20` in 2016, 2017, 2018, and 2019 |
| `YEAR_HETEROGENEOUS_EFFECT` | STRESS | 2016 = 0; 2017 and 2019 positive; 2018 = `-89990393/1893854431` |
| `CELL_HETEROGENEOUS_EFFECT` | STRESS | bucket 0 and 1 carry `-1/40` where `pi_s > 1/20`, otherwise 0; buckets 2 and 3 carry the compensating positive level |

The year-heterogeneous signs are the calendar order of the three full years: positive, negative, positive. That pattern meets the temporal rule in population and was fixed before any power world. Every conditional probability stays inside `(0, 1)`.

## E. Full decision rule

A world is a detection when all of the following hold:

- `primary_status = PRIMARY_COMPLETED`
- the frozen primary test rejects (`exceedance_count <= 49` at `R = 999`)
- year-level `theta_hat > 0` in at least 2 of `{2017, 2018, 2019}`

2016 is diagnostic and does not enter the temporal count. The temporal rule is the BitMEX confirmation rule in `D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.md`: positive year-level contrast in at least 2 of the three full years.

The sample comparison `theta_hat >= 0.05` is stored as `practical_gate_diagnostic`. Section L of the dependent-profile power admission does not fold that sample comparison into the power count. The population alternative is already `0.05`. The diagnostic counts are `963 / 2000`, `911 / 2000`, and `951 / 2000`. They are not a gate.

## F. Power manifest

Official start `2026-09-30T17:38:06Z`.

| Item | Value |
| --- | --- |
| `N_POWER` per family | 2000 |
| Families | 3 |
| Worlds | 6000 |
| `R` | 999 |
| Workers | 4 |
| Chunk size | 1 |
| Draw batch size | 64 |
| Suite | `D7_POWER_GATE` |
| Purpose | `D7_POWER_GATE` |
| Master seed SHA-256 | `1ba93cdf4b5f0c0422c636015a499fc3f502d4ab48b269b4d8e492b6b9851656` |
| Manifest SHA-256 | `9c35900d7cf33ccdda42dc7a1e94eac4c47482bcd64087e5e7e8f509b3b2f50c` |
| Seed-map SHA-256 | `4e2059961970df91e1b01bb0f72f9242f8833ac1b14a62fb021b42007bf68a2a` |

The 6000 power digests are distinct from each other and from the 1600 admission digests. The stream is not the confirmatory beacon.

Admission canonical index, before any power world: `UNIQUE_WORLD_COUNT = 1600`, `PROVENANCE_DUPLICATE_RECORDS = 5`, `STATISTICAL_DUPLICATE_WORLDS = 0`. The five extra admission lines are the byte-identical copies of indices `1041`, `1099`, `1366`, `1368`, and `1489`. The admission gate stays `73 / 1600`.

## G. Completion

6000 unique worlds, each `PRIMARY_COMPLETED`. Execution failures: `0`.

The world file has 6025 lines. Twenty-five keys appear twice. Each second line is byte-identical to the first, including runtime. The gate counted each key once. `statistical_reruns = 0`.

Every completed world matches its pre-execution seed. `p_numerator * 1000 = (1 + exceedance_count) * p_denominator`, and statistical rejection matches `exceedance_count <= 49`.

## H. Power result

| Family | Role | Detections | Point | Binomial SE | Wilson 95% |
| --- | --- | ---: | ---: | ---: | --- |
| `HOMOGENEOUS_EFFECT` | BASE | 2000 / 2000 | 1 | 0 | 0.998083 to 1 |
| `YEAR_HETEROGENEOUS_EFFECT` | STRESS | 2000 / 2000 | 1 | 0 | 0.998083 to 1 |
| `CELL_HETEROGENEOUS_EFFECT` | STRESS | 2000 / 2000 | 1 | 0 | 0.998083 to 1 |

The binomial SE is 0 because every world was a detection. The Wilson interval is the Monte Carlo uncertainty report. At `N = 2000` and a true rate of `0.80`, the binomial SE would have been `0.00894`. The observed rate is above that design point.

Statistical rejects: `2000 / 2000` in each family. Temporal passes: `2000 / 2000` in each family.

## I. Gate

`D7_POWER_GATE_PASS`

Base `1 >= 0.80` and both stress families `1 >= 0.50`.

## J. Scientific status

`D7_HYPOTHESIS_FAILED = false`

`PROFILE_VALIDATED = true`

`D7_PROFILE_ADMISSION = PASS`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

## K. Next action

`READY_FOR_FINAL_TARGET_OPENING_AUTHORIZATION_REVIEW`

The target was not opened. No confirmatory multiplier stream was generated.

## Performance

Completing process: wall `5019.197` s, `1.195` worlds/s, `1194.215` bootstrap draws/s. Workers: 4. Maximum sampled worker `VmRSS`: `44568` KiB. `infrastructure_retries = 0`. `statistical_reruns = 0`.

World-file SHA-256: `64efb75ad5deda156645ce69cf2f69480e3000c60663f75b1ec3f559d5a8bde3`.

Result-file SHA-256: `d024c9f5dbbfa4de2e97144d1c3744c35b5153fdc8dfdad0bd8216139e668f18`.

External driver SHA-256: `d86ff74d6201b3e6715d21d97f527c1b30693c2f3a9935429a662502416e4572`.
