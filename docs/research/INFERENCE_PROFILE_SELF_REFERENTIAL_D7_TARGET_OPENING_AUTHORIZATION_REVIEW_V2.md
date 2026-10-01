# D7 target-opening authorization review V2

**Profile:** `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`

**Decision:** `D7_TARGET_OPENING_AUTHORIZED`

This unit is review only. It does not open the protected BitMEX target, read lag-1 pairs, compute the D7 effect, fetch a NIST beacon, generate a confirmatory stream, or rerun validation, admission, or power. It does not change the statistical or decision contract.

```
FREEZE_MANIFEST_INTACT = true
FINAL_PASS_CONJUNCTION_UNIQUE = true
MAGNITUDE_RULE_FULLY_SPECIFIED = true
TEMPORAL_POWER_ALREADY_EXECUTED = true
TEMPORAL_GATE_POWER_VALIDATED_IN_OFFICIAL_D7_POWER_RUN = true
ADAPTER_DIGEST_TARGET_BLIND = true
INTEGRITY_PASS_NONADAPTIVE = true
SERVER_FREEZE_TIME_ACCEPTABLE = true
BEACON_RULE_EXECUTABLE = true
CONFIRMATORY_RNG_CONTRACT_EXECUTABLE = true
CONFIRMATORY_RNG_READY_BUT_UNGENERATED = true
SINGLE_RUN_SEMANTICS_FROZEN = true
POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL = true
D7_TARGET_OPENING_AUTHORIZED
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
BEACON_FETCHED = false
TARGET_OPENING = FORBIDDEN
```

`TARGET_OPENING = FORBIDDEN` is the state of this unit. The decision authorizes one later opening. This review does not execute it.

## A. Freeze identity

`CONFIRMATORY_FREEZE_COMMIT = 5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b`

`FREEZE_MANIFEST_SHA256 = 2aaa228c40a486f3b7fa208ec62f3c19bb63318a65e8d7d19b8c1e211c751e07`

The SHA-256 of `docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json` at that commit is that digest. The manifest lists 18 covered files, does not list itself, and does not list the pointer.

Pointer commit `710a0131aca7e592be8457489151cf89c2a0687b` has parent `5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b`. Its only path change is `docs/research/D7_CONFIRMATORY_FREEZE_POINTER_V1.json`. Every covered file is byte-identical between the freeze commit and the pointer commit, and each matches the manifest hash.

`FREEZE_MANIFEST_INTACT = true`

## B. Final pass Boolean

The frozen decision rule, the contract, and `directional_confirmation_pass` use one conjunction:

`D7_DIRECTIONAL_CONFIRMATION_PASS = PRIMARY_COMPLETED AND STATISTICAL_REJECT AND TEMPORAL_PASS AND INTEGRITY_PASS`

`STATISTICAL_REJECT` means `inference_status = PRIMARY_COMPLETED`, `V_obs > 0`, `R_CONFIRMATORY = 9999`, primary method `STUDENTIZED_FULL_IF_DWB`, `p = (1 + exceedance_count) / 10000`, and `exceedance_count <= 499`.

`constants.PRIMARY_METHOD` is `STUDENTIZED_FULL_IF_DWB`. `constants.R_CONFIRMATORY` is `9999`. `run_primary` records that method. `finite_r_tail` sets `p = (1 + exceedance_count) / (R + 1)` with `Fraction`, and rejects when `p <= 1/20`. At `R = 9999` that inequality is exactly `exceedance_count <= 499`. `counts_as_exceedance` counts a tie with `>=`. Variance failure returns before `PRIMARY_COMPLETED`.

`TEMPORAL_PASS` means year-level `theta_hat` is defined and `> 0` in at least 2 of `{2017, 2018, 2019}`. 2016 is diagnostic only.

`theta_hat >= 0.05` is `PRACTICAL_MAGNITUDE_DIAGNOSTIC`. It is absent from the pass conjunction. The claim change states that magnitude `>= 0.05` is no longer a D7 confirmation PASS condition. The historical `FINAL_PASS_RULE` remains a historical document. The freeze manifest contains one operative conjunction.

`FINAL_PASS_CONJUNCTION_UNIQUE = true`

## C. Magnitude rule

`theta_hat` is published. The preregistered bound is

`L = theta_hat - c * sqrt(V_obs) / sqrt(T)`

`c` is the largest studentized replicate `t` with `#{T* >= t} > 499`. At `R = 9999`, `bootstrap_critical_floor` returns `sorted_studentized[9499]`.

That order statistic is the frozen finite-R rule, including ties. `#{T* >= c} > 499`, and every value strictly above `c` has exceedance count `<= 499`. Because ties use `>=`, `T_obs = c` does not reject, and `T_obs > c` does. With `se = sqrt(V_obs) / sqrt(T)` and `T_obs = theta_hat / se`, `L > 0` is the same event as rejection of `H0: theta <= 0`. The primary exceedance count is unchanged.

`MAGNITUDE_AT_0_05_SUPPORTED = true` if and only if `L >= 0.05` in IEEE-754 binary64. On this Python, `0.05 == 1/20` and both have hex `0x1.999999999999ap-5`, so the decision-rule phrase `>= 1/20` and the code comparison `>= 0.05` are the same comparison. Otherwise `MAGNITUDE_CLASS = DIRECTION_ONLY`.

`magnitude_classification` sets `changes_directional_pass` false. `directional_confirmation_pass` has no magnitude input.

`MAGNITUDE_RULE_FULLY_SPECIFIED = true`

## D. Temporal power

No power world was rerun.

The pre-world manifest `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_POWER_GATE_V1_MANIFEST.json`, SHA-256 `9c35900d7cf33ccdda42dc7a1e94eac4c47482bcd64087e5e7e8f509b3b2f50c`, has `D7_POWER_GATE_STARTED = false` and detection rule `PRIMARY_COMPLETED` and statistical reject at `R = 999` and year-level `theta_hat > 0` in at least 2 of `{2017, 2018, 2019}`. The sample practical comparison is recorded and is not a second gate.

The executed driver `/opt/cursor/artifacts/official_d7_power_gate_v1/run_official_d7_power_gate.py`, SHA-256 `d86ff74d6201b3e6715d21d97f527c1b30693c2f3a9935429a662502416e4572`, sets `detection` at line 455 from `PRIMARY_COMPLETED`, statistical rejection, and `temporal`. Line 759 sums `row["detection"]`.

The sealed worlds file SHA-256 is `64efb75ad5deda156645ce69cf2f69480e3000c60663f75b1ec3f559d5a8bde3`. It has 6000 unique keys, 25 byte-identical extra lines, and 0 conflicting duplicates. Unique `detection` counts are homogeneous `2000 / 2000`, year heterogeneous `2000 / 2000`, and cell heterogeneous `2000 / 2000`. The sealed result records the same `successes` and `temporal_pass_count`.

`TEMPORAL_POWER_ALREADY_EXECUTED = true`

`TEMPORAL_GATE_POWER_VALIDATED_IN_OFFICIAL_D7_POWER_RUN = true`

Sealed screens read from their result records: generic `75 / 1600` with `PROFILE_VALIDATED = true`; D7 admission `73 / 1600` with `D7_PROFILE_ADMISSION = PASS`.

## E. Adapter safety

`ADAPTER_DIGEST = 260dd8f6a30ff48a1cecdb306b4d5bb7c90930d5123095d08b9400234c51b579`

The adapter file hash matches. Its fields are `T = 30354`, year masses `4079 / 8757 / 8759 / 8759`, the sixteen published cell margins, `K = 3438`, selector identity, the published canonical source digest, the gap, break `3503`, and segments `[3503, 26851]`. Each cell margin matches `ELIGIBLE_N_BY_YEAR_RV_BUCKET` and `CANDIDATE_N_BY_YEAR_RV_BUCKET` in the published support file. The adapter text contains no `m_XY`, lag-1 joint field, transition count, run length, autocorrelation, ordered path, or `DELTA_D7`.

`ADAPTER_DIGEST_TARGET_BLIND = true`

## F. Integrity

`integrity_pass` compares source digest, adapter digest, `T`, year masses, gap break, segments, statistical implementation digest, confirmatory seed digest, NumPy version `2.1.3`, NumPy RECORD SHA-256 `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1`, `inference_status = PRIMARY_COMPLETED`, `target_mutated = false`, and `forbidden_input_accessed = false`. It has no credibility score and no outcome threshold.

`INTEGRITY_PASS_NONADAPTIVE = true`

## G. Server freeze time

`FREEZE_SERVER_TIME = 2026-10-01T06:09:59Z`

`FREEZE_SERVER_TIME_SOURCE` is the GitHub commit status `created_at` for context `CodeRabbit` on commit `5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b`.

Re-read during this review: `GET /repos/sh1zok1d/signalbot/commits/5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b/status` returns `sha = 5b3e5cdcedd615ae63bc2c2ff8eb804b5485b92b`, one status, context `CodeRabbit`, `created_at = 2026-10-01T06:09:59Z`, `updated_at = 2026-10-01T06:09:59Z`.

1. The status is attached to that exact commit.
2. `created_at` is a GitHub status-resource field. The git author and committer timestamps on the same commit are `2026-10-01T06:09:40Z` and are not the cutoff.
3. A status can be attached only after the commit is on GitHub, so `2026-10-01T06:09:59Z` is not earlier than the external visibility of that commit.
4. A receipt later than the push moves the beacon cutoff later. The target was closed, so the later clock is conservative.
5. The pointer records `BEACON_FETCHED = false`. This review did not fetch a beacon.

`SERVER_FREEZE_TIME_ACCEPTABLE = true`

## H. Beacon

`BEACON_SELECTION_RULE = first valid NIST Randomness Beacon 2.0 pulse with pulse_time >= FREEZE_SERVER_TIME + 1 hour`

The cutoff instant is `2026-10-01T07:09:59Z`. The pulse is valid when its NIST Beacon 2.0 signature verifies and its timestamp and `outputValue` are the pulse's own fields. The earliest such pulse at or after the cutoff is the only eligible pulse. A pulse timestamp earlier than `2026-10-01T06:09:59Z` makes the run invalid.

`BEACON_RULE_EXECUTABLE = true`

`BEACON_FETCHED = false`

## I. RNG

`CONFIRMATORY_BIT_GENERATOR = NUMPY_PCG64`

NumPy `2.1.3`. RECORD SHA-256 `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1`.

`seed_digest = SHA256(canonical_json(seed_message))`. `digest_to_seedsequence_words` feeds all 32 bytes as eight little-endian uint32 words and rebuilds the digest. `seed_sequence_from_confirmatory_digest` requires `SeedSequence.entropy` to equal those words. There is no 64-bit truncation and no byte-sum mixer.

The TEST-ONLY known-answer test reproduced message SHA-256 `c3be1f21c3f3eb4da160c82c83dcfb0353e26cf738ea362226ef3fad663631e0` and the eight frozen standard normals in `docs/research/D7_CONFIRMATORY_NUMPY_PIN_V1.json` through `indexed_epsilon_sampler` at draw 0, segment 0, width 8. Nine contract tests passed. The test beacon id is `TEST_ONLY_NOT_A_NIST_PULSE`.

`CONFIRMATORY_RNG_CONTRACT_EXECUTABLE = true`

`CONFIRMATORY_RNG_READY_BUT_UNGENERATED = true`

`CONFIRMATORY_RNG_GENERATED = false`

`STATISTICAL_IMPLEMENTATION_DIGEST = 3347d43575ac7532b9ae34a831a1783d95a4b9b3def923b35d4b099562d87d20` remains the pointer value. This review does not alter the implementation tree.

## J. Resume

The contract freezes one manifest, one eligible beacon, one seed digest, one confirmatory stream, and one protected target execution. Infrastructure resume requires the same manifest digest, source digest, adapter digest, beacon, seed digest, NumPy identity, RNG draw offset, and target bytes. The draw offset is the next `(draw_index, segment_index)`. A partial execution does not create a new beacon or seed.

`SINGLE_RUN_SEMANTICS_FROZEN = true`

## K. Target safety

```
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
BEACON_FETCHED = false
TARGET_OPENING = FORBIDDEN
```

`POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL = true`

## L. Authorization

Every required flag is true. No target-safety blocker remains.

`D7_TARGET_OPENING_AUTHORIZED`
