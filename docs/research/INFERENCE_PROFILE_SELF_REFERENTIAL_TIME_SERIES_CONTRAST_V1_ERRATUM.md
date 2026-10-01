# Final erratum before the self-referential contrast freeze

**Amends:** `INFERENCE_PROFILE_SELF_REFERENTIAL_ENVELOPE_RESOLUTION_V1`

**Incorporated by:** `INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1_FROZEN_CONTRACT`

**Review status:** `PROFILE_CONTRACT_READY_TO_FREEZE`

No implementation, no simulation of the inference procedure, no RNG stream, and no BitMEX lag-1 inspection. Method selection is not reopened.

`PRIMARY_METHOD = STUDENTIZED_FULL_IF_DWB`

`PRIMARY_METHOD_CHANGED = false`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

## A. Bandwidth rate

The envelope resolution said that the multiplier theorem requires `L_T = o(T^{1/3})`, equivalently `L_T^3 / T → 0`, and that `L_T = O(T^{1/3})` does not meet that limit. That statement is replaced.

The bandwidth condition maintained for Shao (2010) Theorem 3.1 is

`L_T^{-1} + L_T / T^{δ/(2+2δ)} → 0`

for the same `δ > 2` that appears in the mixing assumption. This is `L_T → ∞` together with

`L_T = o(T^{δ/(2+2δ)})`.

The exponent equals `1/3` at `δ = 2`, because `2 / (2 + 4) = 1/3`. For `δ > 2` it is strictly larger than `1/3`: `3δ > 2 + 2δ` rearranges to `δ > 2`. Therefore a bandwidth of exact order `T^{1/3}` still satisfies

`T^{1/3} / T^{δ/(2+2δ)} = T^{1/3 - δ/(2+2δ)} → 0`.

`L_T = O(T^{1/3})` is permitted under the maintained `δ > 2`. It is not restated as `o(T^{1/3})`.

The executed rule stays

`B_T = L_T = max(H_mechanical, ceil(T^{1/3}))`.

When the ceiling is the active branch, that rule is `Θ(T^{1/3})` and meets the corrected rate. The sentence that treated this order as outside the theorem is withdrawn.

## B. Mechanical horizon

`H_mechanical(T) / T → 0` remains necessary. It is not sufficient for the bandwidth condition in A. If the horizon is the active branch of the maximum, `L_T` inherits the horizon's order, and the theorem asks for a smaller order than `o(T)`.

The theoretical-domain requirement is

`H_mechanical(T) = o(T^{δ/(2+2δ)})`

for the maintained `δ > 2`. An adapter that cannot justify this rate is `PROFILE_ADMISSION_OUT_OF_THEORETICAL_DOMAIN`.

A simpler sufficient condition is

`H_mechanical(T) = O(T^{1/3})`.

Section A then puts `L_T = O(T^{1/3})` inside the permitted rate. An adapter may use this sufficient condition and does not have to exhibit the sharper exponent.

D7 uses the fixed integer `H_mechanical = 721`. A fixed horizon is `O(T^{1/3})` and `o(T^{δ/(2+2δ)})` for every `δ > 2`. Its theoretical-domain status is unchanged. At `T = 30354` the floor is the active branch because `721 > ceil(30354^{1/3})`. That comparison selects the bandwidth. It is not a domain failure.

## C. Cumulants

Fourth-order joint cumulant summability is not recorded as the same statement as the mixing assumption, and it is not recorded as an automatic corollary of that assumption.

The maintained theorem assumptions are separate:

- Shao Assumption 3.1-style strong mixing and moments: `Z_t` is strong mixing, or near-epoch dependent on a strong-mixing sequence, and there exists `δ > 2` such that `sum_j α(j)^{δ/(2+δ)} < ∞` and `E|Z_t|^{2+δ} < ∞`.
- Shao Assumption 3.2-style fourth-order joint cumulant summability of the coordinates that enter the smooth-function expansion.

Primitive coordinates are bounded, so `E|Z_t|^{2+δ} < ∞` holds for every `δ > 2`. That disposes of the moment half of the first assumption. It does not dispose of the mixing sum, and it does not dispose of the cumulant sum.

A stronger mixing condition than Assumption 3.1 may be maintained as a sufficient condition for the cumulant sum. If an adapter uses that route, the stronger condition is an additional maintained assumption. It is not a rewording of Assumption 3.1.

## D. What this erratum does not change

`NUMERIC_G_REQUIRED = ONLY_FOR_FINITE_UNIFORM_CLAIM`

`G_MAX_REMOVED = true`

`GENERIC_TYPE_I_SIM_N = 9559`

`D7_ADMISSION_TYPE_I_SIM_N = 9559`

Validation anchors, the validated domain, and hypothesis-geometry admission stay three different objects. The Bartlett form stays positive definite, with `V_obs = 0` only when the block-centered influence is identically zero. Nonpositive bootstrap variance fails the confirmatory run closed. The seed remains the HMAC-SHA256 derivation from the freeze tree, the adapter digest, and the first NIST Beacon 2.0 pulse after that commit. `R = 9999`. There is no automatic method switching. The null remains the global composite `θ ≤ 0`, with boundary `θ = 0`.

The prior statement that structural gaps and deterministic block centering are an extension beyond a single stationary segment is unchanged. This erratum corrects the bandwidth and cumulant wording. It does not add a proof of that extension.

## E. Status

These are the corrections required before the freeze. The canonical statement is `INFERENCE_PROFILE_SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1_FROZEN_CONTRACT`.

`PROFILE_CONTRACT_READY_TO_FREEZE`

Implementation is not started.
