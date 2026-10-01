# D7 final contract integrity repair V1

Outcome-blind contract and integrity repair. This unit does not open the protected BitMEX target, read lag-1 pairs, compute the D7 effect, inspect transitions or `m_XY`, fetch a beacon, generate a confirmatory stream, or rerun generic validation, D7 admission, or D7 power.

```
PROFILE_VALIDATED = true
D7_PROFILE_ADMISSION = PASS
D7_POWER_GATE_PASS
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
TEMPORAL_POWER_ALREADY_EXECUTED = true
TEMPORAL_GATE_POWER_VALIDATED_IN_OFFICIAL_D7_POWER_RUN = true
CLAIM_CHANGE: magnitude >= 0.05 is no longer a D7 confirmation PASS condition
NEXT_ACTION = READY_TO_REPEAT_FINAL_TARGET_OPENING_AUTHORIZATION_REVIEW
```

The previous authorization review remains `D7_TARGET_OPENING_NOT_AUTHORIZED:FINAL_PASS_CONJUNCTION_NOT_UNIQUE` with `CONFIRMATORY_RNG_READY_BUT_UNGENERATED = false`. This repair pins one directional confirmation Boolean and one executable seed rule. It does not itself authorize target opening.

## A. Power and temporal provenance

`OFFICIAL_POWER_DETECTION_BOOLEAN = PRIMARY_COMPLETED AND statistical_reject AND temporal_gate`

`statistical_reject` is the sealed power-world rule: `R = 999` and exceedance count `<= 49`. `temporal_gate` is year-level `theta_hat > 0` in at least 2 of `{2017, 2018, 2019}`. 2016 is diagnostic. The sample comparison `theta_hat >= 0.05` is stored as `practical_gate_diagnostic` and is not part of detection.

`TEMPORAL_POWER_ALREADY_EXECUTED = true`

The pre-world-0 identity is the official power manifest `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_POWER_GATE_V1_MANIFEST.json`, SHA-256 `9c35900d7cf33ccdda42dc7a1e94eac4c47482bcd64087e5e7e8f509b3b2f50c`. Its `detection_rule` is that Boolean, and its body records `D7_POWER_GATE_STARTED = false`. Git publication of those bytes is commit `fa17793a0d2a755565a1b30139fc8bda61794b03`. The manifest digest, not the later result commit, is the pre-world rule.

The executable that produced the sealed 6000-world result is `/opt/cursor/artifacts/official_d7_power_gate_v1/run_official_d7_power_gate.py`, SHA-256 `d86ff74d6201b3e6715d21d97f527c1b30693c2f3a9935429a662502416e4572`. Function `_record` sets `detection` at line 455:

`detection = bool(status == STATUS_PRIMARY_COMPLETED and reject and temporal)`

`temporal` is `temporal_hits >= 2` over `("2017", "2018", "2019")` at lines 447–452. Line 454 records the practical comparison and line 455 does not use it. The sealed power count uses result field `detection`. Aggregation is `_wilson(sum(1 for row in family_rows if row["detection"]), len(family_rows))` at line 759. The sealed result records `successes = 2000` and `temporal_pass_count = 2000` in each of the three families.

The dependent-profile sentence that left the temporal gate out of a power count is not the official D7 power manifest. This repair does not substitute that older document for the executed Boolean.

## B. Claim change

`CLAIM_CHANGE: magnitude >= 0.05 is no longer a D7 confirmation PASS condition`

Historical D7 materials, including `FINAL_PASS_RULE` in `docs/research/D7_BITMEX_DEPENDENCE_INFERENCE_REVIEW_V0.json`, defined replication as statistical rejection and `theta_hat >= 0.05` and temporal agreement and integrity. That review had not created a confirmation preregistration.

The validated self-referential design uses population `theta = 1/20` as the practical-effect point for power. At that population value, a sample requirement `theta_hat >= 0.05` is a boundary event and materially lowers power. The sealed practical diagnostics, which were not a power gate, are homogeneous `963 / 2000`, year heterogeneous `911 / 2000`, and cell heterogeneous `951 / 2000`.

The main confirmation label is directional:

`D7_DIRECTIONAL_CONFIRMATION_PASS`

A directional pass does not establish `theta >= 0.05`.

## C. Magnitude classification

`theta_hat` is published. The one-sided lower bound is the inversion of the frozen DWB test, using the same studentized replicates that form the confirmatory exceedance count.

`T(theta0) = sqrt(T) * (theta_hat - theta0) / sqrt(V_obs)`

`H0: theta <= theta0` is rejected when `#{T*_r >= T(theta0)} <= 499` at `R = 9999`. That event is `T(theta0) > c`, where `c` is the largest replicate `t` with `#{T* >= t} > 499`. At `R = 9999` this is the ascending order statistic `sorted_studentized[9499]`.

`L = theta_hat - c * sqrt(V_obs) / sqrt(T)`

`L > 0` is the same event as rejection of `H0: theta <= 0`. The primary reject Boolean remains the exceedance count. Computing `L` retains those replicates; it does not change the multiplier path or the count.

`MAGNITUDE_AT_0_05_SUPPORTED = true` only if `L >= 0.05` in IEEE-754 binary64. In this Python, `0.05 == 1/20`. Otherwise `MAGNITUDE_CLASS = DIRECTION_ONLY`.

This classification does not alter `D7_DIRECTIONAL_CONFIRMATION_PASS`.

## D. Final pass conjunction

Temporal power was included in the official detection Boolean, so the conjunction is power-qualified for the temporal gate:

`D7_DIRECTIONAL_CONFIRMATION_PASS = PRIMARY_COMPLETED AND STATISTICAL_REJECT AND TEMPORAL_PASS AND INTEGRITY_PASS`

`STATISTICAL_REJECT` means `inference_status = PRIMARY_COMPLETED` and `V_obs > 0` and `R = 9999` and `p = (1 + exceedance_count) / 10000` and `exceedance_count <= 499`.

`TEMPORAL_PASS` means year-level `theta = g(m)` is defined and strictly positive in at least 2 of `{2017, 2018, 2019}`. Each year uses the four year-by-RV cells whose predictor hour falls in that calendar year. The pair is attributed to hour `t`. A calendar-year boundary is not a structural gap. The only structural gap is eligible index 3503. 2016 is diagnostic and is excluded from both sides of the 2-of-3 count. An undefined year is not positive.

`PRACTICAL_MAGNITUDE_DIAGNOSTIC` is the sample comparison `theta_hat >= 0.05`. It is not a PASS condition. The preregistered magnitude label is the lower-bound classification in section C.

## E. Integrity pass

`INTEGRITY_PASS` is mechanical and pre-result. It is true only when every identity below matches the pin and the execution record:

- canonical source SHA-256 equals `33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c`;
- adapter digest equals the SHA-256 of `docs/research/D7_CONFIRMATORY_ADAPTER_V1.json`;
- `T = 30354`;
- year eligible masses are `{2016: 4079, 2017: 8757, 2018: 8759, 2019: 8759}`;
- eligible-index gap break is `3503` and structural segments are `[3503, 26851]`;
- statistical implementation digest equals the digest defined in section J;
- confirmatory seed digest equals the seed derived in section J;
- NumPy version is `2.1.3` and the NumPy RECORD SHA-256 is `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1`;
- `inference_status = PRIMARY_COMPLETED`;
- `target_mutated = false`;
- `forbidden_input_accessed = false`.

No post-result credibility judgment enters `INTEGRITY_PASS`.

## F. Freeze manifest

Commit A of this repair commits the contract, the adapter, the decision rule, the NumPy pin, the statistical package including `confirmatory_contract.py`, and `docs/research/D7_CONFIRMATORY_FREEZE_MANIFEST_V1.json`.

The manifest lists SHA-256 for each covered file. It does not include its own digest and it does not include a git commit SHA. `FREEZE_MANIFEST_SHA256` is SHA-256 of the exact manifest file bytes. That digest is the confirmation identity used in seed derivation. Git metadata is not part of the scientific identity.

Commit B records `CONFIRMATORY_FREEZE_COMMIT` and `FREEZE_MANIFEST_SHA256` in `docs/research/D7_CONFIRMATORY_FREEZE_POINTER_V1.json`. Commit B does not modify a file covered by the manifest.

`ADAPTER_DIGEST = 260dd8f6a30ff48a1cecdb306b4d5bb7c90930d5123095d08b9400234c51b579`

`DECISION_RULE_DIGEST = 39c5a727ee6ac5c6877924670a6acc1520584b312ae6ddf49a206a2656e34751`

`NUMPY_PIN_SHA256 = 0e15e892bc88db400fe08f57c98840a8192124e55b7c514543d4c5073f6f6cb5`

## G. Server freeze time

The randomness-beacon cutoff is not a git author date and not a git committer date. Those timestamps are author-controlled.

This workflow is a branch push, so there is no GitHub-created merge commit to use. After Commit A is visible on the remote, the pointer records:

`FREEZE_SERVER_TIME_SOURCE = GitHub Commit.pushedDate`

`FREEZE_SERVER_TIME` is that server receipt timestamp for Commit A. A PushEvent `created_at` may corroborate it. The value is absent from Commit A because it does not exist until the push is received.

## H. Beacon rule

`BEACON_SELECTION_RULE = first valid NIST Randomness Beacon 2.0 pulse with pulse_time >= FREEZE_SERVER_TIME + 1 hour`

The pulse is valid when its NIST Beacon 2.0 signature verifies and its timestamp and `outputValue` are the pulse's own fields. No later pulse may be chosen when an earlier valid pulse already satisfies the inequality. If the chosen pulse timestamp is earlier than the verified server time, the confirmatory run is invalid.

`beacon_id = NIST-Beacon-2.0`

`purpose = CONFIRMATORY_DWB_MULTIPLIERS`

No beacon is fetched in this repair.

## I. Adapter digest

`ADAPTER_DIGEST_TARGET_BLIND = true`

`docs/research/D7_CONFIRMATORY_ADAPTER_V1.json` is the canonical JSON of published outcome-blind quantities: `T = 30354`; year eligible masses `4079 / 8757 / 8759 / 8759`; deterministic blocks `2016`–`2019`; RV buckets `0`–`3`; the sixteen published `(eligible_n, candidate_n)` margins and `pi_s` as rational strings; `K = 3438`; `selector_n = 3438`; selector digest `88b6e9571e26c0037ee14522249f21ec7f0d46261982dcb5e5bb0964cd396cc6`; the published canonical source SHA-256; gap `[2016-12-06T23:55:00.000Z, 2016-12-07T23:55:00.000Z)`; eligible-index break `3503`; segments `[3503, 26851]`; `H_mechanical = B_T = L_T = 721`; label geometry `CONTIGUOUS_PUBLISHED_YEAR_RV_MARGINS`; estimand `theta=g(m)`.

The adapter does not contain `m_XY`, lag-1 joint counts, transition tables, run lengths, autocorrelation, an ordered state path, an ordered RV trajectory, or the discovery statistic `DELTA_D7`. The canonical gzip and raw pages are not reopened to recompute the source digest.

Encoding is UTF-8 JSON with sorted keys, separators `("," , ":")`, `ensure_ascii`, and no NaN. The file bytes are that string, so the file SHA-256 is the adapter digest.

## J. RNG reproducibility

`CONFIRMATORY_BIT_GENERATOR = NUMPY_PCG64`

No HMAC_DRBG implementation is added. The freeze-amendment HMAC message builder remains in `seeds.confirmatory_hmac_digest` and is not the confirmatory seed. The multiplier path stays `indexed_epsilon_sampler` → `generator_from_digest` → `SeedSequence` → `PCG64` → `standard_normal`, on NumPy `2.1.3`.

Confirmation requires:

- Python `3.11.15`;
- NumPy `2.1.3`;
- NumPy RECORD SHA-256 `ea812052b69c8ef0e08393946a587a2bcc91c50a2fb08394ba84bc03a08b3cc1`;
- NumPy WHEEL SHA-256 `eae5ee06e4c72985475f7f278cb9c38c261193567983069726dcc5aade8b44ac`.

`seed_message = canonical_json` of exactly these keys: `adapter_digest`, `beacon_id`, `beacon_output_value`, `beacon_pulse_time`, `decision_rule_digest`, `freeze_manifest_sha256`, `numpy_record_sha256`, `numpy_version`, `profile_id`, `profile_version`, `purpose`, `r_confirmatory`, `statistical_implementation_digest`, `target_source_digest`.

`purpose` is `CONFIRMATORY_DWB_MULTIPLIERS`. `r_confirmatory` is `9999`. `numpy_version` is `2.1.3`. `profile_id` is `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`. `profile_version` is `D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1`. `target_source_digest` is the published canonical gzip SHA-256. `statistical_implementation_digest` is SHA-256 of the canonical JSON map `{path: sha256}` for manifest files under `scripts/research/self_referential_contrast_v1/`. That digest is computed from the manifest at confirmation and recorded in the pointer commit. It is not embedded in a manifest-covered file.

`seed_digest = SHA256(utf-8 seed_message bytes)`. All 256 bits enter NumPy `SeedSequence` as eight little-endian uint32 words, the conversion in `seed_sequence_from_digest`. The words rebuild the digest. There is no 64-bit truncation and no byte-sum mixer.

The known-answer fixture uses a TEST-ONLY beacon identity `TEST_ONLY_NOT_A_NIST_PULSE` and freeze field `TEST_ONLY_NOT_THE_CONFIRMATION_MANIFEST`. It draws `indexed_epsilon_sampler(seed_digest)(draw_index=0, segment_index=0, width=8)`. The expected binary64 values are in `docs/research/D7_CONFIRMATORY_NUMPY_PIN_V1.json`. Message SHA-256 `c3be1f21c3f3eb4da160c82c83dcfb0353e26cf738ea362226ef3fad663631e0`. A NIST beacon id cannot carry a TEST-ONLY output.

## K. Target safety

```
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
BEACON_FETCHED = false
```

## L. Resume, diagnostics, and next action

One beacon, one seed, one confirmatory RNG stream, and one protected target execution. Infrastructure resume is allowed only when the freeze manifest digest, source digest, adapter digest, beacon, seed digest, NumPy and environment identity, RNG draw offset, and target data bytes are identical. The draw offset is the next `(draw_index, segment_index)` of `indexed_epsilon_sampler`. No new beacon or seed is created after a partial execution.

`POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL = true`

Diagnostics without a numerical threshold frozen before target opening are report-only. They cannot upgrade or downgrade `D7_DIRECTIONAL_CONFIRMATION_PASS`. No assumption-band cutoff is invented here.

`NEXT_ACTION = READY_TO_REPEAT_FINAL_TARGET_OPENING_AUTHORIZATION_REVIEW`

This repair does not open the target.
