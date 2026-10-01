# D7 target-opening authorization review

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `D7_TARGET_OPENING_NOT_AUTHORIZED:FINAL_PASS_CONJUNCTION_NOT_UNIQUE`

This unit does not open the protected BitMEX target. It does not compute the D7 effect, read lag-1 pairs, generate confirmatory multipliers, fetch a beacon, or run a simulation. The completed power result stays `D7_POWER_GATE_PASS` at `2000 / 2000` on each predeclared family. That result is not rerun and is not used to choose a target critical value.

`PROVENANCE_CHAIN_COMPLETE = true`

`STATISTICAL_IMPLEMENTATION_CHANGED = false`

`POWER_POPULATION_EFFECT_EXACT = true`

`POWER_TARGET_BLIND = true`

`STATISTICAL_DUPLICATE_WORLDS = 0`

`TEMPORAL_GATE_FULLY_SPECIFIED = true`

`CONFIRMATORY_RNG_READY_BUT_UNGENERATED = false`

## A. Provenance chain

`HYPOTHESIS -> PROFILE -> IMPLEMENTATION -> AUDIT -> GENERIC VALIDATION -> D7 ADMISSION -> POWER -> TARGET OPENING`

Target opening has not occurred. Every artifact below predates it.

| Step | Artifact | Commit / digest |
| --- | --- | --- |
| Hypothesis | `docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.md` | `77447661e3eb8c4438edc87b20fc091e47bbe5bf`, SHA-256 `bfe4e8236b6a0121c951ebf7f97322fd63ec2d6c95c89bbdec4f4a816a872a69` |
| Global null | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_NULL_AMENDMENT_V1.md` section A, `H0_global: Delta <= 0` | `1ccd6d0d035e2112ba26c7709737d80eb53588fd`, SHA-256 `24e128324594780e82c89928cc3d1fc523de3ea1b8baaf51d34ca0ae93a8c15d` |
| Practical effect `0.05` | `scripts/research/discovery_sprint_02_impl.py` `D7_PRACTICAL_GATE = 0.05`; dependent-profile section L population `delta = 0.05` | carried unchanged into the power manifest as `1/20` |
| Inference profile | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1_FROZEN_CONTRACT.md` | `53050d6a4a3610bf562881185fb981ae807e524d`, SHA-256 `0ce75cbaf6815774044190bd12126da057bbe32f504bba6a3c643f2284f17768` |
| Primary `STUDENTIZED_FULL_IF_DWB` | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_PRIMARY_METHOD_V1.md` | `8e27916125cdc2aca43371c9d4561355b2c0bbf3`, SHA-256 `5306ca18be3080117b9e10397b04211d5af7930de40de92f430c704fbbd5222f` |
| Confirmatory seed text | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_FREEZE_AMENDMENT_V1.md` section K | `f2cf608d5811d09c399431d8231b5e56566886f0`, SHA-256 `48496d21c73ef47407b71bff9f0d949c7b2fc153f2955c5efa8a2b68922d8123` |
| Implementation | `ebb26aca6ed37c12bbf3b3f578973d3078407d99`, tree `aa484e77852c7505fd309b25abe4f19377a25d22` | committer time `2026-09-30T14:45:45Z` |
| Audit fail, then pass | external `/opt/cursor/artifacts/audit_self_ref_v1.json` SHA-256 `1f54ceada1089bcac99eefb38dd3235b78a13d6c36b51734ad94ddff9aff0930`; re-audit `/opt/cursor/artifacts/reaudit_self_ref_v1.json` SHA-256 `6ed85782c939cbf02e61956e4c7879dd7c1f802e65b5bb293aaa66e44ac0e655`; in-repo attestation in the generic-validation record: `IMPLEMENTATION_AUDIT_PASS` | re-audit file time `2026-09-30T14:58Z`, before the generic screen |
| Generic validation | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_GENERIC_VALIDATION_V1.md` | `898ce8cfc04d7f5172ddd1f1b6d50bc4f8810949`; worlds SHA-256 `1d77a1a3b2fd9bc26b9859e3d6e0f3429be95f09ff048e85ec290d5015c658e3`; result SHA-256 `cdc1c74d668b0ab955fd8a71163fd3bcfa9b26f4d73535ab995395e532c5ef3a` |
| Geometry amendment | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_ELIGIBLE_INDEX_GAP_BREAK_V1.md` | `e69fc5c56ba9d4c5d31915f44b30cebf66c5275b`, SHA-256 `09f77beceb64d41311b3ab21dba6426a9fa8abe556e7184c403409a934fb37c0` |
| D7 admission | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_EXACT_GEOMETRY_ADMISSION_V1.md` | `33359c73ccbc4b70e55551570327737c4ad9a41b`; worlds SHA-256 `e51eeaab63a15bb7f1d00da8c155e9bf9ffd1c0d162d16c7ab425ef4ae78544f`; result SHA-256 `0b0fe2ecf1d42c58cfae7ecebf3affccda7d11d173215b8f367a6ee018dcb665` |
| Power | `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_POWER_GATE_V1.md` | `fa17793a0d2a755565a1b30139fc8bda61794b03`; worlds SHA-256 `64efb75ad5deda156645ce69cf2f69480e3000c60663f75b1ec3f559d5a8bde3`; result SHA-256 `d024c9f5dbbfa4de2e97144d1c3744c35b5153fdc8dfdad0bd8216139e668f18`; manifest SHA-256 `9c35900d7cf33ccdda42dc7a1e94eac4c47482bcd64087e5e7e8f509b3b2f50c` |

`PROVENANCE_CHAIN_COMPLETE = true`. The chain records that the seed contract exists. It does not make that contract executable. See section I.

## B. Code identity

The statistical package that a later opening would have to use is `ebb26aca6ed37c12bbf3b3f578973d3078407d99`.

Current `HEAD` `fa17793a0d2a755565a1b30139fc8bda61794b03` is a descendant of that commit. `git diff ebb26aca6ed37c12bbf3b3f578973d3078407d99 -- scripts/research/self_referential_contrast_v1` is empty. The working tree is clean.

`STATISTICAL_IMPLEMENTATION_CHANGED = false`

## C. Power sanity

Independent reconstruction from the published margins, the gap break `3503`, and the power driver's predeclared allocation. No world was rerun. Cell fractions match the power manifest. In every family

`theta = sum_s n_same_s * pi_s * delta_s / K = 1/20`

with `K = 3438`. Same-cell counts are `n_s - 1` except `2019:3`, where the terminal lead stays inside the cell, so `n_same = 2173`. `2016:3` is split by the gap and still has `n_same = 992`.

| Family | Population `theta` | What `delta_s` is |
| --- | --- | --- |
| `HOMOGENEOUS_EFFECT` | `1/20` | `(1/20) * n_s / n_same_s` in every cell. Year contrasts are `1/20`. |
| `YEAR_HETEROGENEOUS_EFFECT` | `1/20` | 2016 is `0`. 2018 cells with `pi_s > 1/20` are `-1/20`. 2017 and 2019 share one positive level. |
| `CELL_HETEROGENEOUS_EFFECT` | `1/20` | Buckets 0 and 1 are `-1/40` where `pi_s > 1/20`, otherwise `0`. Buckets 2 and 3 share one positive level. |

`POWER_POPULATION_EFFECT_EXACT = true`

The additive shift on `P(Y=1 | X=1)` is `delta_s` itself. Setting that shift to `1/20` in every cell, without the `n_s / n_same_s` factor, produces population `theta = 191330864229816652079062891104778837951 / 3828374123181132803739062656364270929800` (`0.049977...`), not `1/20`. Setting every `delta_s = 1/2` produces about `0.4998`. The largest absolute homogeneous coefficient is `471/9410` (`0.05005`). Every conditional probability in all three families lies in `(0, 1)`.

## D. Target blindness

The power driver reads `ELIGIBLE_N_BY_YEAR_RV_BUCKET` and `CANDIDATE_N_BY_YEAR_RV_BUCKET` from `docs/research/D7_BITMEX_SUPPORT_AND_POWER_V0.json`. It does not read a power field, a stored contrast, or a transition table. States are synthetic Bernoulli draws on the published contiguous margins. The name `confirmatory_hmac_digest` appears only inside the driver's denylist. No path constant points at `raw_pages` or `canonical_5m`. The admission driver has the same property.

`POWER_TARGET_BLIND = true`

## E. Canonical world counts

Recount of the committed JSONL files. Keys are `(suite_id, configuration_id, world_index)`. Duplicate copies were compared as raw lines. Nothing was rerun.

| Screen | Lines | Unique worlds | Byte-identical extra lines | Conflicting keys |
| --- | ---: | ---: | ---: | ---: |
| Generic `GENERIC_STRESS_SCREEN` | 1600 | 1600 | 0 | 0 |
| Admission `D7_GEOMETRY_ADMISSION` | 1605 | 1600 | 5 | 0 |
| Power `D7_POWER_GATE` | 6025 | 6000 | 25 | 0 |

Admission extras are indices `1041`, `1099`, `1366`, `1368`, and `1489`. The existing admission index SHA-256 is `050aaf9d1b5be3b7cac96771884ae90e32768c960732726115e43640f391059b`. Generic reject count remains `75`. Admission reject count remains `73`. Power detections remain `2000 / 2000` in each family, and every unique power row has `population_theta = 1/20` and `primary_status = PRIMARY_COMPLETED`.

`STATISTICAL_DUPLICATE_WORLDS = 0`

The committed generic file does not contain extra lines. The admission and power extras are provenance copies.

## F. Final D7 decision rule

The profile statistical gate is unique:

```
STATISTICAL_REJECT =
  inference_status = PRIMARY_COMPLETED
  AND V_obs > 0
  AND R = 9999
  AND p = (1 + exceedance_count) / 10000
  AND exceedance_count <= 499
```

`p <= 1/20` sits on that lattice: `k = 499` gives `500/10000 = 0.05`, and `k = 500` gives `501/10000 > 0.05`. `H0` is `theta <= 0`. The boundary used for the null distribution is `theta = 0`. There is no sign short-circuit and no second method.

The temporal predicate is also unique. See section G.

```
TEMPORAL_PASS =
  |{y in {2017, 2018, 2019} : year_theta(y) is defined and year_theta(y) > 0}| >= 2
```

The practical comparison is

```
PRACTICAL_COMPARISON = (theta_hat >= 1/20)
```

Its role in the final D7 pass is not unique, so this review does not adopt either Boolean.

- `docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.json` writes `D7_BITMEX_REPLICATION_SUPPORTED_IFF = STATISTICAL_GATE AND PRACTICAL_GATE AND TEMPORAL_GATE AND INTEGRITY_GATE`, with `PRACTICAL_GATE = delta_hat >= 0.05`. The same file sets `CONFIRMATION_PREREG_CREATED = false`, `DECISION = NO_VALID_EQUIVALENT_INFERENCE_DESIGN`, and binds that statistical gate to `EXACT_DELTA_NW_BARTLETT_LAG_721`. That method was not authorized.
- `docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.md` calls the practical and temporal gates confirmation rules and keeps them out of the power count. That profile was not implementation-authorized.
- `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1.md` leaves `delta_hat >= 0.05` outside the statistical class.
- The null amendment's permitted confirmation sentence is rejection of `H0_global`. The practical threshold is adapter metadata. The frozen contract's pass label is a result under the DWB procedure.
- The power manifest's detection rule records the sample comparison and does not use it as a gate. That sentence governs the power count. It is not a repeal or an adoption of the target conjunction.

Choosing either conjunction now would edit the contract or use the completed power result to decide whether `0.05` binds. This unit does neither.

## G. Temporal gate

`TEMPORAL_GATE_FULLY_SPECIFIED = true`

`year_theta(y)` is `g(m)` on the four year × RV cells whose predictor hour falls in calendar year `y`. Pair `(X_t, X_{t+1})` is attributed to the cell of hour `t`. A year boundary is not a structural gap, so the last hour of a year keeps its lead into the next year. The December 2016 gap is the only structural break and is not crossed. Weights are the frozen candidate weights inside that year, which is what `g` does. The value does not change if moments are divided by the year length instead of by `T`. An undefined year estimand is not positive. 2016 is stored and is excluded from both the numerator and the denominator of the 2-of-3 count. No other partition, eligibility subset, or unweighted year mean is authorized.

## H. Target data boundary

Not opened in this unit. If a later unit is authorized, the primary opening may compute only:

- the ordered eligible D7 state `X_t` and the lead `Y_t = X_{t+1}` inside each structural segment;
- the frozen year × RV cells, the four deterministic year blocks, and the single segment break at eligible index `3503`;
- primitive moments, `theta_hat`, the full influence, one deterministic-block centering, and the primary DWB at `R = 9999`, `B_T = L_T = 721`;
- `year_theta` for 2016, 2017, 2018, and 2019;
- the recorded comparison of `theta_hat` with `1/20`, without this review deciding whether that comparison is a gate;
- the normal-critical full-influence HAC as `SENSITIVITY_ONLY`. Disagreement sets `INFERENCE_SENSITIVE` and does not flip the primary.

Identity checks that do not analyze pairs may confirm the pinned canonical gzip SHA-256 `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c` and selector digest `88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6`. Binance 2025/2026 stays unread.

After the primary result is sealed, the only named descriptions are autocorrelation, run lengths, and variance stability across the predetermined cells. They do not change bandwidth, method, sample, strata, or the number of confirmatory evaluations. Numeric warning bands for those descriptions were never frozen. This review does not set them, so `ASSUMPTION_DIAGNOSTIC_SEVERE_WARNING` has no executable cutoff.

## I. Confirmatory RNG

`CONFIRMATORY_RNG_READY_BUT_UNGENERATED = false`

Specified and unused:

- profile id `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`, version `FREEZE_AMENDMENT_V1`;
- purpose `CONFIRMATORY_DWB_MULTIPLIERS`;
- beacon id `NIST-Beacon-2.0`;
- HMAC key `profile_id/profile_version`;
- message fields `v1`, `tree`, `adapter`, `beacon_id`, `beacon_time`, `beacon_value`, `purpose`;
- `R = 9999`, one stream, no rerun near a threshold;
- `CONFIRMATORY_RNG_GENERATED = false`. No beacon was fetched. `confirmatory_hmac_digest` was not called on a pulse.

Not executable:

- Section K names the tree and the pulse clock as "the implementation-and-admission freeze commit." No later artifact pins that commit's SHA, tree, or committer time.
- The amendment takes the first pulse strictly later than that commit. The frozen-contract summary says "at or after." Those rules can select different pulses.
- `adapter_digest` is SHA-256 of "the UTF-8 JSON of the D7 geometry in B." Section B is prose. The amendment JSON does not contain the 16 cell margins or eligible index `3503`. No canonical adapter bytes are pinned.
- The audited multiplier sampler expands an entropy digest with NumPy `PCG64`. The package contains no HMAC_DRBG. The contract says the HMAC digest is the entropy input of HMAC_DRBG.

## J. Failure semantics

These statuses are execution outcomes. They are not scientific non-rejection and they do not authorize a new seed, method, bandwidth, deleted row, altered cell, or altered temporal rule.

| Condition | Status | Behavior |
| --- | --- | --- |
| Empty declared cell or candidate mass `0` | `ESTIMAND_UNDEFINED` | Stop. Not a pass and not a hypothesis failure. |
| Observed `Gamma0 = 0`, or `V_obs` inside the negative tolerance | `VARIANCE_DEGENERATE` | Not a pass and not a fail. |
| `V_obs` below the negative tolerance | `INFERENCE_IMPLEMENTATION_ERROR` | Stop. |
| A bootstrap draw with `Gamma0 = 0` or `V_r* = 0` | `BOOTSTRAP_VARIANCE_DEGENERATE` | Stop. The draw is not dropped, `R` is not reduced, and `T_r* = +infinity` is not used. |
| A bootstrap draw with `V_r*` inside the negative tolerance | `BOOTSTRAP_VARIANCE_NUMERICAL` | Stop. Same prohibitions. |
| Beacon missing, or the freeze commit still unpinned | execution failure | No substitute pulse, no second purpose, no PCG64 fallback. |
| Infrastructure interruption | resume only | The same beacon value, the same digest, and the same draw index must be preserved. A fresh stream is not a resume. |

## K. Evidence labels

Frozen before any target value:

- Statistical reject, with the maintained mixing and cumulant assumptions still maintained rather than verified on the sealed series: `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`.
- The same statistical reject, if a pre-frozen diagnostic cutoff were contradicted: `STATISTICAL_GATE_PASSED_BUT_ASSUMPTIONS_NOT_SUPPORTED`. No such cutoff exists, so this label cannot be applied.
- `INFERENCE_SENSITIVE` may be reported beside a pass when the normal-critical sensitivity disagrees. It does not change the pass.
- Statistical non-rejection is non-rejection. The frozen documents do not name that event `D7_HYPOTHESIS_FALSE` or `D7_HYPOTHESIS_FAILED`. `D7_HYPOTHESIS_FAILED` stays `false`.
- The discovery label `D7_NO_USEFUL_STRUCTURE` belongs to the Binance discovery evaluator. It is not the BitMEX confirmatory label.
- An execution status in section J is not a scientific failure.

## L. Authorization

`D7_TARGET_OPENING_NOT_AUTHORIZED:FINAL_PASS_CONJUNCTION_NOT_UNIQUE`

The confirmatory generator is also not executable (`CONFIRMATORY_RNG_READY_BUT_UNGENERATED = false`). Either fact is sufficient to keep the target closed. This review does not repair either fact.

## M. Current scientific status

`D7_HYPOTHESIS_FAILED = false`

`PROFILE_VALIDATED = true`

`D7_PROFILE_ADMISSION = PASS`

`D7_POWER_GATE_PASS` remains the sealed power result.

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`CONFIRMATORY_RNG_GENERATED = false`

`TARGET_OPENING = FORBIDDEN`

Next action: keep the target closed until a separately authorized contract unit pins one final pass conjunction and one executable confirmatory seed, without reading the BitMEX lead.
