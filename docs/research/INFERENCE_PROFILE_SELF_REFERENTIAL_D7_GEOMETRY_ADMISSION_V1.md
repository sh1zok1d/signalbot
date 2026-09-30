# D7 exact-geometry admission

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `D7_GEOMETRY_ADMISSION_EXECUTION_FAILED:ELIGIBLE_INDEX_GAP_BREAK_UNPUBLISHED`

**Recorded:** `2026-09-30T16:11:05Z`

This is the first official D7 exact-geometry admission attempt. It stops before world 0. No admission world was drawn, no admission seed stream was generated, and the generic screen was not rerun.

`PROFILE_VALIDATED` stays true. The generic result remains `FINITE_SAMPLE_STRESS_VALIDATED` with 75 rejections in 1600 worlds. `D7_PROFILE_ADMISSION` is `NOT_DECIDED`. Pass and fail are defined only after 1600 ordinary completed worlds.

## A. Code identity

| Item | Value |
| --- | --- |
| Branch at preflight | `cursor/self-referential-generic-validation-v1-c58d` |
| HEAD | `898ce8cfc04d7f5172ddd1f1b6d50bc4f8810949` |
| Tree | `686eed815b2c05ee59b48b77a9e06476259ac07a` |
| Working tree | clean |
| Audited implementation | `ebb26aca6ed37c12bbf3b3f578973d3078407d99` |
| Audited tree | `aa484e77852c7505fd309b25abe4f19377a25d22` |
| Statistical diff versus the audited implementation | empty |
| Descendant class | result and provenance artifacts only |
| Primary method | `STUDENTIZED_FULL_IF_DWB` |

Generic result SHA-256 `cdc1c74d668b0ab955fd8a71163fd3bcfa9b26f4d73535ab995395e532c5ef3a`.

Generic worlds SHA-256 `1d77a1a3b2fd9bc26b9859e3d6e0f3429be95f09ff048e85ec290d5015c658e3`.

D7 admission protocol digest SHA-256 `8c7959c0f84b01fba42c274e4b848c43df0353ab4130b282de884c8846341b8f`.

The digest covers, in order, the freeze amendment, the envelope resolution, and the validation-protocol amendment.

## B. Geometry that is published

| Item | Value |
| --- | --- |
| `T` | 30354 |
| `H_mechanical` | 721 |
| `B_T = L_T` | 721 |
| Gap | `[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)` |
| Year eligible masses | 2016: 4079, 2017: 8757, 2018: 8759, 2019: 8759 |
| Declared cells | 16 |
| Candidate total `K` | 3438 |
| Frozen `N` | 1600 |
| Frozen `R` | 999 |
| Frozen gate | `TOTAL_REJECT_COUNT <= 95` |
| Workers | not selected |
| Admission seed digest | not generated |

Cell margins are the published `eligible_n` and `candidate_n` maps in `D7_BITMEX_SUPPORT_AND_POWER_V0.json`. The machine record lists them. Sample counts are not pinned. `D7_EXACT_GEOMETRY_ADMISSION_STARTED` remains false because the segment break could not be frozen.

## C. Completion

Completed valid worlds: 0 / 1600.

Execution failure: `ELIGIBLE_INDEX_GAP_BREAK_UNPUBLISHED`.

The freeze amendment says the eligible-index break is the one that abuts the published gap on timestamps alone. No published integer locates that break inside the 4079 eligible 2016 rows.

Complete UTC hours, from the published coverage endpoints and the three incomplete hours, are 4979 before the gap and 576 after it inside 2016. The 2016 complete total is 5555. The four-year complete total is 31835, matching `CONSTRUCTED_HOURS`.

A successor-only rule on those complete hours does not yield eligible mass 4079. Applying the published builder order with two trailing windows of 720, and treating every complete hour as volume-valid, yields 4116 eligible 2016 hours. That is 37 above the published mass. The locations of the residual hours are not in the published aggregates. They depend on `state_defined`, which depends on notional and absolute return. Those series are in the raw activity pages. Those pages also carry the D7 state path. The admission runner was not written and did not read them.

## D. Admission result

`D7_ADMISSION_REJECT_COUNT` is unset. No world returned a p-value.

## E. Gate

`D7_GEOMETRY_ADMISSION_EXECUTION_FAILED:ELIGIBLE_INDEX_GAP_BREAK_UNPUBLISHED`

## F. Diagnostics

No DGP rejection breakdown exists. No law was executed.

## G. Performance

Wall time of admission worlds: 0. Workers: none. Worlds/sec: none. Bootstrap draws/sec: none. Peak RSS: none. Infrastructure retries: 0. Statistical reruns: 0.

## H. Profile and D7 status

`PROFILE_VALIDATED = true`

`D7_PROFILE_ADMISSION = NOT_DECIDED`

A type-I fail was not observed. The generic pass stays in force.

## I. Target safety

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

No confirmatory beacon stream was generated. No power calculation used protected outcomes. No lag-1 pairs were read.

## J. Next action

`D7_EXACT_GEOMETRY_ADMISSION_STOPPED_BEFORE_WORLD_0`

The power gate is not authorized and was not run.
