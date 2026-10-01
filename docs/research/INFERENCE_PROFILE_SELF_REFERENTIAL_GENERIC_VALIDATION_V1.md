# Self-referential generic finite-sample validation

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `FINITE_SAMPLE_STRESS_VALIDATED`

**Executed implementation:** `ebb26aca6ed37c12bbf3b3f578973d3078407d99`

**Tree:** `aa484e77852c7505fd309b25abe4f19377a25d22`

This is the first official held-out generic screen. It is a material-anticonservatism stress of the frozen studentized full-influence dependent wild bootstrap. It does not claim `true type I <= 0.06`, does not validate every law in the asymptotic class, does not verify BitMEX mixing, and does not admit or confirm D7.

## Identity

| Item | Value |
| --- | --- |
| Branch at execution | `cursor/self-referential-cancelling-null-repair-c58d` |
| HEAD | `ebb26aca6ed37c12bbf3b3f578973d3078407d99` |
| Tree | `aa484e77852c7505fd309b25abe4f19377a25d22` |
| Working tree | clean |
| Amendment | `VALIDATION_PROTOCOL_AMENDMENT_V1` |
| Amendment markdown SHA-256 | `4c0b08e7104db344294c82d3e62cb19bfda8648ab67c4a076456b5eafcceb7a1` |
| Amendment JSON SHA-256 | `5db80f60bba42ab35334a03d9a2ac979c08c55453b732c08845553c4b7bec1dd` |
| Prior implementation audit | `IMPLEMENTATION_AUDIT_FAIL_REPAIR_REQUIRED` |
| Independent re-audit | `IMPLEMENTATION_AUDIT_PASS` |
| Primary method | `STUDENTIZED_FULL_IF_DWB` |

Official start `2026-09-30T15:11:31Z`. Result file `2026-09-30T15:40:09Z`.

## Frozen screen

`GENERIC_OUTER_WORLD_N = 1600`

`R_VALIDATION = 999`

Aggregate gate: `TOTAL_REJECT_COUNT <= 95`

Regions: 8 × 200. A region fails when `REGION_REJECT_COUNT >= 21`.

Suite and HMAC purpose: `GENERIC_STRESS_SCREEN`

Master seed SHA-256: `566a1039833df6da74c6f808a51c9fd8adede3d40d256d59c9c9691e8ac32df1`

Canonical master string: `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1/VALIDATION_PROTOCOL_AMENDMENT_V1/MASTER_VALIDATION_SEED`

Workers were chosen before any world result: 4 processes, `cpu_count = 4`, about 4.7 GiB available. Chunk size 1. Draw batch size 64. `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `NUMEXPR_NUM_THREADS` were `1`. NumPy 2.1.3.

Manifest SHA-256: `c16a27b266b2db8cc6f4ae39b6cd666b7a936c92d63e71e3e9bbbb587caa7b7d`

Per-world records SHA-256: `1d77a1a3b2fd9bc26b9859e3d6e0f3429be95f09ff048e85ec290d5015c658e3`

## Completion

1600 worlds, each `PRIMARY_COMPLETED`. Seed digests match the pre-execution manifest. The finite-R reject rule matches exceedance count `<= 49`. No world was replaced and no seed was changed.

One infrastructure write (`OSError EIO` on `worlds.jsonl`) stopped the first process after 101 completed records. Those records were kept. The remaining 1499 indices were executed once under the frozen seeds. `statistical_reruns = 0`. `infrastructure_retries = 1`.

## Aggregate

`TOTAL_REJECT_COUNT = 75` / 1600 (`0.046875`).

Aggregate gate: `PASS` (`75 <= 95`).

Descriptive Wilson 95% interval for the rejection fraction: `0.037559` to `0.058362`. It does not enter the decision.

## Regions

| Region | Rejects / 200 | Gate |
| --- | ---: | --- |
| `R1_IID_BERNOULLI` | 10 | PASS |
| `R2_INTERLACED_WEAK` | 4 | PASS |
| `R3_INTERLACED_STRONG` | 14 | PASS |
| `R4_MA_EVEN` | 13 | PASS |
| `R5_CANCELLING_CELLS` | 9 | PASS |
| `R6_VARIANCE_REGIMES` | 6 | PASS |
| `R7_LABEL_MARKOV_MODERATE` | 6 | PASS |
| `R8_LABEL_MARKOV_PERSISTENT` | 13 | PASS |

Every region is below 21.

## Diagnostics

These counts are not gates.

| Family | Rejects / worlds |
| --- | ---: |
| `IID_BERNOULLI` | 10 / 200 |
| `INTERLACED_LAG2` | 18 / 400 |
| `MA_EVEN` | 13 / 200 |
| `CANCELLING_CELLS` | 9 / 200 |
| `VARIANCE_REGIMES` | 6 / 200 |
| `LABEL_MARKOV` | 19 / 400 |

| T | Rejects / worlds |
| --- | ---: |
| 2048 | 33 / 544 |
| 16384 | 22 / 544 |
| 65536 | 20 / 512 |

| J | Rejects / worlds |
| --- | ---: |
| 1 | 33 / 800 |
| 4 | 42 / 800 |

| Gap | Rejects / worlds |
| --- | ---: |
| none | 34 / 800 |
| interior | 41 / 800 |

Parameter counts are in the result JSON. Lexicographic dealing leaves unequal world counts across parameters inside a region. No configuration was removed.

## Performance

Completing process: wall `1379.88` s for the remaining 1499 worlds, `1.086` worlds/s, `1085` bootstrap draws/s. Sum of per-world runtimes `1769.27` s. Sum of process times `1765.47` s. Peak worker RSS `375476` KiB. Worker utilization on the completing process `0.313`. Clock from official start through the result file is `15:11:31Z` to `15:40:09Z`, including the write failure and the resume.

## Status

`PROFILE_VALIDATION_EXECUTED = true`

`PROFILE_VALIDATED = true`

`FINITE_SAMPLE_STRESS_VALIDATED` means the frozen procedure passed the predefined finite-sample material-anticonservatism screen.

`D7_GEOMETRY_ADMISSION_EXECUTED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

Profile next action: `READY_FOR_D7_EXACT_GEOMETRY_ADMISSION`. That stage was not run.
