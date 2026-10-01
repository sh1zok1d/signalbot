# D7 exact-geometry admission

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `HYPOTHESIS_GEOMETRY_ADMISSION_PASS`

**Executed implementation:** `ebb26aca6ed37c12bbf3b3f578973d3078407d99`

**Execution HEAD:** `e69fc5c56ba9d4c5d31915f44b30cebf66c5275b`

This is the first official D7 exact-geometry admission that ran worlds. The earlier attempt remains the sealed stop `D7_GEOMETRY_ADMISSION_EXECUTION_FAILED:ELIGIBLE_INDEX_GAP_BREAK_UNPUBLISHED`. The generic screen remains `FINITE_SAMPLE_STRESS_VALIDATED` with `TOTAL_REJECT_COUNT = 75`.

`HYPOTHESIS_GEOMETRY_ADMISSION_PASS` means the frozen 1600-world screen rejected at most 95 worlds. It does not open the BitMEX target, compute the D7 effect, or authorize the power gate.

## A. Preflight

| Item | Value |
| --- | --- |
| Branch at execution | `cursor/d7-eligible-index-gap-break-v1-c58d` |
| HEAD | `e69fc5c56ba9d4c5d31915f44b30cebf66c5275b` |
| Tree | `b0af5849359a125c467e0dcd897b9a5f715bbcd7` |
| Working tree | clean |
| Audited implementation | `ebb26aca6ed37c12bbf3b3f578973d3078407d99` |
| Audited implementation is an ancestor | yes |
| Diff of `scripts/research/self_referential_contrast_v1` against the audited commit | empty |
| `STATISTICAL_IMPLEMENTATION_CHANGED` | false |
| Primary method | `STUDENTIZED_FULL_IF_DWB` |
| `B_T = L_T` | 721 |

Geometry checks used the published amendment only. The extractor was not rerun.

| Check | Value |
| --- | --- |
| `T` | 30354 |
| Year masses | 4079, 8757, 8759, 8759 |
| Declared cells | 16 |
| `K` | 3438 |
| Published gap | `[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)` |
| `ELIGIBLE_COUNT_BEFORE_GAP` | 3503 |
| `ELIGIBLE_COUNT_AFTER_GAP` | 576 |
| `ELIGIBLE_INDEX_GAP_BREAK` | 3503 |
| `3503 + 576` | 4079 |
| Structural segments | 3503, 26851 |
| Year boundaries | deterministic blocks |

Provenance, matching `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_ELIGIBLE_INDEX_GAP_BREAK_V1.md` and its JSON twin:

| Digest | SHA-256 |
| --- | --- |
| Geometry markdown | `09f77beceb64d41311b3ab21dba6426a9fa8abe556e7184c403409a934fb37c0` |
| Geometry JSON | `0d767e248f06ec58279384ba73789d8f01fe8abdb8bc8c782025aab71692c6ea` |
| Source canonical gz | `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` |
| Extractor | `84e0c19b37c60fe2639e1db570b0869580409a94f4077870a374e7c1197f814a` |
| Derivation rule | `b3c041b174fa206fc328d540cd00395e3d632d583c4cf03ee5fb0a06ac469162` |
| Derivation file | `9fd9c1964775a84f666178641e7c712de5e9ae8ad6112757dc5548fe4eaf1a5e` |

`PROTECTED_D7_PATH_REACHABLE_FROM_ADMISSION_RUNNER = false`. The admission runner builds synthetic labels and synthetic Bernoulli states. It does not import the BitMEX bar loader, the predictor frame, or the confirmatory HMAC.

## B. Official manifest

Official start `2026-09-30T16:41:18Z`, after the manifest and seed map were on disk.

| Item | Value |
| --- | --- |
| `N` | 1600 |
| `R` | 999 |
| Pass threshold | `D7_ADMISSION_REJECT_COUNT <= 95` |
| Workers | 4 |
| Chunk size | 1 |
| Draw batch size | 64 |
| Suite | `D7_GEOMETRY_ADMISSION` |
| Purpose | `D7_EXACT_GEOMETRY_ADMISSION` |
| Master admission seed SHA-256 | `1ba93cdf4b5f0c0422c636015a499fc3f502d4ab48b269b4d8e492b6b9851656` |
| Canonical master-string SHA-256 | `566a1039833df6da74c6f808a51c9fd8adede3d40d256d59c9c9691e8ac32df1` |
| Manifest SHA-256 | `907059b383f2b4278326ed1aa9d8e89a937d66089be40a75fddc95064afa73db` |
| Seed map SHA-256 | `2fdf7e3bfeae290ee6bdc26d0dc4131ea0b65fe28eea24eeecd12dcd45a70f30` |

The seed map has 1600 distinct digests. Each world stream is `HMAC-SHA256(master_validation_seed, suite, configuration, world_index, purpose)`. That stream is the admission RNG. It is separate from the confirmatory beacon.

Lexicographic allocation from the frozen `d7_world_specs()` list gives 95 worlds to the first two configuration ids and 94 to each of the other fifteen. Every gating law uses `g(m) = 0` by the frozen synthetic adaptation in the manifest: published `pi_s`, the envelope cancelling pair, and the listed moving-average cells.

## C. Completion

1600 unique world indices, `0` through `1599`, each `PRIMARY_COMPLETED`. Execution failures: 0.

The world file contains 1605 lines. Indices `1041`, `1099`, `1366`, `1368`, and `1489` each appear twice. The second line of each pair is byte-identical to the first, including runtime. The gate counted each index once. `statistical_reruns = 0`.

Per-world seed digests match the pre-execution seed map. For every completed world, `p_numerator * 1000 = (1 + exceedance_count) * p_denominator`, and `reject` matches `exceedance_count <= 49`.

## D. Result

`D7_ADMISSION_REJECT_COUNT = 73` / 1600.

## E. Gate

`HYPOTHESIS_GEOMETRY_ADMISSION_PASS`

`73 <= 95`. The threshold was frozen before world 0.

## F. Diagnostics

These counts are not gates.

| Family | Rejects / worlds |
| --- | ---: |
| `CANCELLING_CELLS` | 0 / 284 |
| `IID_BERNOULLI` | 5 / 94 |
| `INTERLACED_LAG2` | 21 / 470 |
| `LABEL_MARKOV` | 14 / 282 |
| `MA_EVEN` | 19 / 282 |
| `VARIANCE_REGIMES` | 14 / 188 |

| Parameter | Rejects / worlds |
| --- | ---: |
| `c=0.02/0.7` | 0 / 95 |
| `c=0.05/0.7` | 0 / 95 |
| `c=0.10/0.7` | 0 / 94 |
| `p=0.05,0.40` | 8 / 94 |
| `p=0.10,0.50` | 6 / 94 |
| `p=0.25` | 5 / 94 |
| `q=1\|theta=0.40` | 10 / 94 |
| `q=2\|theta=0.30,0.20` | 4 / 94 |
| `q=4\|theta=0.20,0.15,0.10,0.05` | 5 / 94 |
| `rho=0` | 6 / 94 |
| `rho=0.25` | 5 / 94 |
| `rho=0.50` | 4 / 94 |
| `rho=0.75` | 1 / 94 |
| `rho=0.90` | 5 / 94 |
| `stay=0.50` | 6 / 94 |
| `stay=0.80` | 5 / 94 |
| `stay=0.95` | 3 / 94 |

| Construction | Rejects / worlds |
| --- | ---: |
| Year blocks `YEAR_BLOCKS_4079_8757_8759_8759` | 73 / 1600 |
| Cells `CONTIGUOUS_PUBLISHED_MARGINS` | 59 / 1318 |
| Cells `MARKOV_16_PUBLISHED_WEIGHTS` | 14 / 282 |
| Gap segments `[3503, 26851]` | 73 / 1600 |

## G. Performance

Completing process, after the manifest existed: wall `2150.951` s, `0.743857` worlds/s, `743.113` bootstrap draws/s. Workers: 4. Sum of per-world runtimes `1898.45` s. Sum of process times `1893.96` s. Maximum sampled worker `VmRSS`: `42988` KiB. `infrastructure_retries = 0`. `statistical_reruns = 0`. Official start `2026-09-30T16:41:18Z`.

External driver SHA-256: `aa11324e1f21d854fe397b1a42f2b153b74098a160b7be2b8fa3d2e17afc1bc2`.

World-file SHA-256: `e51eeaab63a15bb7f1d00da8c155e9bf9ffd1c0d162d16c7ab425ef4ae78544f`.

Result-file SHA-256: `0b0fe2ecf1d42c58cfae7ecebf3affccda7d11d173215b8f367a6ee018dcb665`.

## H. Status

`PROFILE_VALIDATED = true`

`D7_PROFILE_ADMISSION = PASS`

`D7_EXACT_GEOMETRY_ADMISSION_STARTED = true`

`D7_GEOMETRY_ADMISSION_EXECUTED = true`

## I. Target safety

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

## J. Next action

`READY_FOR_D7_POWER_GATE`

The power gate was not executed.
