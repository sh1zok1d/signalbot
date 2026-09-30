# Review of DEPENDENT_TIME_SERIES_CONTRAST_V1

**Reviewed contract:** `docs/research/INFERENCE_PROFILE_DEPENDENT_TIME_SERIES_CONTRAST_V1.md`

**Review status:** `PRIMARY_METHOD_RECONSIDERATION_REQUIRED`

This review does not edit that contract, the D7 artifacts, the generator, or the target pipeline. The contract files remain the design that was submitted. This document is the authorization reading of that design.

`DEPENDENT_TIME_SERIES_CONTRAST_V1` is not implementation-authorized.

`PROFILE_VALIDATED = false`

`TARGET_OPENING = FORBIDDEN`

`D7_HYPOTHESIS_FAILED = false`

`D7_BITMEX_PRIMARY_TARGET_OPENED = false`

`D7_PRIMARY_EFFECT_COMPUTED = false`

No validation draw, RNG stream, or BitMEX lag-1 diagnostic was run for this review.

## Self-reference

`SELF_REFERENTIAL_D7 = true`

The frozen D7 outcome is the next hour of the same state that defines treatment:

`Y_t = D7_STATE_{t+1} = X_{t+1}`

with `X_t = D7_STATE_t`.

The contrast therefore asks whether this one binary process has a stratified excess lag-1 transition probability. It is not a contrast between an exogenous treatment path and a separate outcome path.

The V1 calibration model draws a synthetic `Y` independent of a fixed `X`, apart from a dependence structure placed in `Y` alone. Under that model the weights are treated as an exogenous design. Under D7 the weights are functions of `X_t` and the outcome is `X_{t+1}`, so the design and the outcome are adjacent values of one path. A reference built from independent synthetic `Y` on fixed `X` is not the D7 null. It cannot be used for D7 target admission.

## Why the primary method is not accepted

1. `c(b, q)` was not established as a pivotal critical value for the geometry the profile claims to cover. The table is a Gaussian-white-noise t-statistic on fixed rate-matched weights, contiguous balanced strata, and prevalence 0.10. D7's weights are functions of the same binary path as the outcome, the strata interleave, and the score is not an exogenous-design residual. No theorem in the contract shows that the resulting t-statistic has that table's null limit.

2. The generic validation family does not cover a persistent, clustered treatment geometry of the kind D7's own definition produces. Treatment in the V1 family is an auxiliary Markov path, independent of `Y` under the null, with mean run length drawn only up to 24 hours. In D7 the treatment path is the state path, and the outcome is its shift. Clustering of treatment and serial dependence of the outcome are one fact. An independent-`Y` design cannot represent that fact. This review does not measure BitMEX run lengths, autocorrelation, or episode durations to make the point. The identification `Y_t = X_{t+1}` is enough.

3. Because of that identification, conditioning on the completed realized `X` path conditions on the outcome. Fixed-weight calibration that holds the BitMEX candidate path fixed and resamples an independent target is the wrong experiment for admission.

`FIXED_B_BARTLETT_HAC` is not accepted as the primary method. This review does not select a replacement.

## What the failure is not

The hypothesis did not fail. No BitMEX primary effect was computed. The target remains procedurally sealed: the confirmation contrast has not been opened as an authorized result.

The same target is potentially recoverable from the already built D7 state path, because the outcome at `t` is the state at `t+1`. Any operation that shifts, joins, or otherwise pairs that path with itself reconstructs the sealed contrast. The following stay forbidden on BitMEX for this review and for any use of the V1 profile:

- lag-1 pairing `X_t -> X_{t+1}`;
- autocorrelation of the D7 state;
- run lengths;
- episode persistence;
- predictor-memory diagnostics that use the complete BitMEX D7-state path.

Published marginal counts that do not pair adjacent hours are not a new opening. They are also not a substitute for a valid null.

## Disposition

V1 stays on record as an unadopted design. Its validation seed, Brownian-table seed, and fixed-b rule are not an implementation permit and are not the acceptance set for a later profile. A self-referential hypothesis needs a separate class. That class is not defined by editing V1 into a pass.
