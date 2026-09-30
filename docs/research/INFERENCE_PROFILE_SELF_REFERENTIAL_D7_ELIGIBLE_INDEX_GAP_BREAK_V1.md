# D7 eligible-index gap break

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Minimum required geometry:** `ELIGIBLE_INDEX_GAP_BREAK`

**Next action:** `READY_TO_RETRY_D7_EXACT_GEOMETRY_ADMISSION_PREFLIGHT`

This unit publishes the missing eligible-index position of the already published structural gap. It does not run admission worlds, does not generate an admission seed, and does not compute a D7 effect.

`PROFILE_VALIDATED` stays true. `D7_PROFILE_ADMISSION` stays `NOT_DECIDED`. `D7_EXACT_GEOMETRY_ADMISSION_STARTED` stays false.

## A. Minimum required geometry

The frozen admission geometry has one structural gap. Year boundaries are not gaps. Hours that fail eligibility are absent from the eligible index and are not extra segment breaks.

The eligible index is the calendar order of eligible hours. Every eligible hour before the published gap is a prefix of that index, and every eligible hour after it is the suffix. The prefix length is the only missing scalar.

`MINIMUM_REQUIRED_GEOMETRY = ELIGIBLE_INDEX_GAP_BREAK`

Per-hour locations of ineligible hours are not required and are not published.

## B. Gap break

`ELIGIBLE_COUNT_BEFORE_GAP = 3503`

`ELIGIBLE_COUNT_AFTER_GAP = 576`

`ELIGIBLE_INDEX_GAP_BREAK = 3503`

`3503 + 576 = 4079`. The eligible-index segments implied by this scalar and the published `T` are a prefix of length 3503 and a suffix of length `30354 - 3503`.

## C. Consistency

| Check | Value |
| --- | --- |
| 2016 | 4079 |
| 2017 | 8757 |
| 2018 | 8759 |
| 2019 | 8759 |
| `T` | 30354 |
| Eligible hours inside the published gap | 0 |
| Eligible hours before the gap outside 2016 | 0 |

`YEAR_MASSES_MATCH_PUBLISHED = true`

`T_MATCHES_PUBLISHED = true`

`CONSISTENT = true`

The after-gap 2016 count 576 equals the complete UTC hours in 2016 after the published gap. The published gap identity is `[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)`.

## D. Target-blind safety

`GEOMETRY_EXTRACTOR_TARGET_BLIND = true`

The extractor output schema is aggregate counts, the published gap identity, and digests. The source audit found no read of the state boolean, returns, notional, RV labels, or ordered cell labels into the output. The sealed artifact contains no extra timestamp and no forbidden field. Audit finding codes: none.

The frozen builder still executes its existing `state_defined` branch. This unit does not read the resulting state boolean and does not report it.

## E. Provenance

| Digest | SHA-256 |
| --- | --- |
| Canonical source `canonical_5m.jsonl.gz` | `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` |
| Extractor `scripts/research/d7_eligible_index_gap_break_v1.py` | `84e0c19b37c60fe2639e1db570b0869580409a94f4077870a374e7c1197f814a` |
| Derivation rule | `b3c041b174fa206fc328d540cd00395e3d632d583c4cf03ee5fb0a06ac469162` |
| Derivation file `d7_bitmex_support_and_power_v0.py` | `9fd9c1964775a84f666178641e7c712de5e9ae8ad6112757dc5548fe4eaf1a5e` |
| Audit `d7_eligible_index_gap_break_audit_v1.py` | `e10153cefed861921b225654e7994c85896bf266f4b050cfea1f1ffb920b3c23` |

Parent of this metadata unit: HEAD `efee07428a7d119cebf768b3118d09941fd4ff96`, tree `8c3932864716441895b47a5bbe50685df039dfa9`.

Eligibility uses the frozen hour aggregation, the frozen `state_defined` rule, and `structural_target_eligible`. Warmup, valid-data criteria, the published gap, and year boundaries are unchanged.

## F. Admission status

`D7_EXACT_GEOMETRY_ADMISSION_STARTED = false`

`D7_GEOMETRY_ADMISSION_EXECUTED = false`

Unchanged screen parameters: `N = 1600`, `R = 999`, rejection threshold `95`, `B = L = 721`. No admission seed was generated.

## G. Next action

`READY_TO_RETRY_D7_EXACT_GEOMETRY_ADMISSION_PREFLIGHT`

## Target safety

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`
