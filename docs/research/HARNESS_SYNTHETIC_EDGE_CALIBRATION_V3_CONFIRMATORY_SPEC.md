# Harness Synthetic Edge Calibration V3 — Confirmatory methodology spec

Status: **DESIGN_COMPLETE / READY_FOR_PREREG_REVIEW / NOT FROZEN / NOT ARMED**

Date: 2026-09-16
Parent design direction: `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_CONFIRMATORY_DESIGN.md`
Parent branch identity at start: `8a6015cffe132b9261810c8c4820cddb29191c9f`

This artifact closes the bounded V3 design unit. It is not a preregistration, freeze, ARM, execution authorization, or permission to inspect fresh V3 acceptance outcomes.

## 1. Scientific question and estimand

V3 tests one prospectively frozen conditional claim at a time:

> inside a predeclared market state/support, does the candidate add positive out-of-sample predictive information relative to the frozen baseline?

For binary support, `w_t in {0,1}` and support is fixed before confirmation. If support is learned, the lifecycle is `development -> freeze support -> confirmation`; confirmation outcomes may not alter support.

V3 intentionally changes the primary estimand from V2's mainly pooled predictive-improvement question to a claim-aligned conditional incremental effect. This semantic change must remain explicit in every V3 result.

The primary raw loss is squared forecast error:

`L(y, yhat) = (y - yhat)^2`

`e_B,t = y_t - yhat_B,t`

`e_C,t = y_t - yhat_C,t`

For the V3 nested candidate construction, the primary adjusted differential is Clark-West-style:

`d*_t = e_B,t^2 - (e_C,t^2 - (yhat_B,t - yhat_C,t)^2)`

and the claim-aligned effect is

`theta_hat = mean(d*_t | w_t = 1)`.

This adjustment is authorized only when the candidate is actually nested in the frozen baseline construction. It is not a universal Signalbot loss transform. If implementation review finds that the concrete V3 candidate is not nested in the required sense, execution must remain blocked and the spec must be revised before freeze, without using fresh V3 outcomes.

Raw unadjusted conditional MSE differential and unconditional/pool-wide MSE differential are mandatory diagnostics and are not substitute acceptance statistics.

## 2. Primary confirmatory statistic

The hypothesis is one-sided:

`H0: theta <= 0`

`H1: theta > 0`.

The sole significance-like primary statistic is

`T = theta_hat / SE_dep(theta_hat)`

where `SE_dep` and the decision distribution are obtained from the single dependence-aware confirmatory procedure in section 3.

Per-world type-I level is fixed at:

`alpha = 0.05`, one-sided.

A valid world is `DETECTED` iff its frozen dependence-aware confirmatory decision has `p_one_sided <= 0.05` and `theta_hat > 0`.

V3 must not restore V2's `primary AND bootstrap AND placebo` conjunction under different names.

## 3. Dependence-aware calibration

The V3 confirmatory resampling family is the **Politis-Romano stationary bootstrap** applied to the ordered scored claim-aligned series used by the primary statistic. Ordinary row permutation is forbidden for the primary decision.

The stationary-bootstrap expected block length is selected by one predeclared automatic **Politis-White / Patton-Politis-White automatic block-length rule** implemented and unit-tested before freeze. No manual block-length choice based on V2 outcomes is permitted.

The implementation review must bind the exact published rule/version, edge handling, finite-sample fallback, and deterministic RNG semantics. If the automatic selector is undefined/non-finite for a world, the world is invalid; no hand-selected rescue block is allowed.

The final preregistration must freeze the exact number of stationary-bootstrap replicates. This design artifact does not authorize choosing that count after acceptance outcomes.

WORLD_RECORDS must persist the selected expected block length, observed `theta_hat`, `SE_dep`, `T`, one-sided p-value/critical quantity, decision margin, and sufficient resampling-distribution summaries to explain a miss.

## 4. Support validity and effective sample size

The inherited canonical DGP has `N=5000`, four scored eras (`E2..E5`), target support 0.20 for EASY and 0.10 for MODERATE/NULL/TRAP. The historical preregistration therefore expected roughly 1000/500 trigger rows over full N for EASY/MODERATE respectively; the scored subset remains comfortably above the historical candidate-positive floor in ordinary worlds.

V3 does **not** introduce an outcome-motivated `effective_N >= 30` hard gate. Under the frozen persistent Markov support (`rho=0.90`), dependence can make effective N much smaller than raw support even when the canonical scenario is behaving exactly as designed. Adding a new arbitrary threshold would risk manufacturing another power veto.

The hard support validity rule is therefore:

- `support_count >= 50` finite scored support observations;
- the inherited effective-support-N calculation must be finite and within `[1, support_count]`;
- `effective_N` is mandatory reporting and diagnostic, not an additional power veto in V3 synthetic acceptance.

Any future MARKET claim may impose a stronger prospectively justified effective-N requirement based on its own sampling/dependence semantics. That is outside this synthetic calibration.

## 5. Hard guards versus diagnostics

Hard fail-closed validity/protection guards are limited to distinct failure modes:

1. chronology/no-lookahead violation;
2. invalid support under section 4;
3. non-identifiability, non-finite required fit/prediction/statistic, or invalid confirmatory resampling;
4. the frozen NONSTATIONARY_TRAP protection rule.

The following are mandatory diagnostics but are **not** additional significance vetoes for the same null:

- placebo result;
- raw unadjusted conditional effect;
- unconditional/pool-wide effect;
- era-level effects;
- economic/materiality statistic;
- near-oracle reference if implemented;
- resampling-distribution shape/quantiles beyond the primary decision;
- effective N beyond validity/range checks.

Synthetic V3 does not impose a fees/slippage economic-materiality gate. Economic usefulness belongs to a real MARKET claim. V3 calibrates whether the validator can detect a predeclared statistical effect.

## 6. Monte Carlo acceptance

Fresh acceptance uses new world identities/seeds. V2 worlds are development-consumed and may not count as V3 evidence.

For continuity and bounded compute, the primary V3 cells retain `400` fresh worlds each for EASY, MODERATE, NULL and NONSTATIONARY_TRAP unless preregistration review identifies a pre-outcome arithmetic impossibility. There is no outcome-triggered sample-size extension.

Aggregate confidence uses **95% one-sided Wilson score bounds**. Let `z = Phi^-1(0.95) ~= 1.6448536269514722`. For `x` successes among `n` planned valid worlds, use the standard Wilson center/half-width with this z; the lower or upper endpoint is selected according to the directional claim.

Mechanical targets remain:

- EASY: PASS iff one-sided Wilson lower bound for `DETECTED` rate is `>= 0.90`; FAIL iff the corresponding upper bound is `< 0.90`; otherwise INDETERMINATE.
- MODERATE: PASS iff one-sided Wilson lower bound is `>= 0.70`; FAIL iff upper bound is `< 0.70`; otherwise INDETERMINATE.
- NULL: PASS iff one-sided Wilson upper bound for false-positive `DETECTED` rate is `<= 0.05`; FAIL iff lower bound is `> 0.05`; otherwise INDETERMINATE.
- NONSTATIONARY_TRAP: retain the historical protection ceiling `DETECTED <= 0.20` at aggregate level, evaluated with the one-sided Wilson upper/lower PASS/FAIL convention analogous to NULL. The exact V3 trap detection statistic must be bound in preregistration to the V3 primary decision rather than V2 `STRICT_PASS_EX_MATERIALITY` terminology.

Failed/invalid planned worlds remain in the planned execution accounting. Any scientific-execution invalidity that prevents the frozen aggregate from being evaluated produces `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`; worlds are not replaced or rerolled.

No second acceptance batch is authorized to resolve INDETERMINATE.

## 7. Required persisted diagnostics

For every world, where applicable, persist at least:

- scenario, world identity, seed and exact run identity;
- support count, support fraction, support runs/clusters and effective N;
- raw conditional MSE differential;
- Clark-West-adjusted conditional differential `theta_hat`;
- unconditional/pool-wide MSE differential;
- dependence-aware SE;
- studentized statistic T;
- automatic expected block length and selector status;
- primary one-sided p-value/critical quantity and margin to boundary;
- resampling summaries sufficient to explain misses;
- era-level effects;
- visibility diagnostic;
- identifiability state/reason;
- chronology/leakage state;
- materiality/economic diagnostic without synthetic acceptance authority.

No diagnostic required to explain a miss may be computed and discarded.

## 8. Anti-overfit and execution boundary

This spec was designed using the already-consumed V2 evidence. It may not be evaluated for acceptance on those same V2 worlds.

Required next sequence:

`DESIGN_COMPLETE`
-> `exact implementation + tests`
-> `pre-outcome adversarial methodology/implementation review`
-> `prereg/freeze exact bytes, including bootstrap replicate count and exact automatic-selector implementation`
-> `ARM exactly one fresh acceptance run`
-> `immutable RESULT`
-> `MARKET`.

No threshold, support rule, loss, statistic, block rule, alpha, confidence rule or acceptance mapping may change after fresh acceptance outcomes are inspected.

`DEFAULT_V4 = NO` remains governing policy.

If V3 controls specificity/TRAP but remains underpowered, record the measured detection limits and proceed to MARKET. A further synthetic methodology iteration requires a concrete correctness/specificity blocker or later real-market evidence that measured power is materially preventing useful inference.

## 9. Explicit state

`V3_DESIGN_COMPLETE = YES`

`READY_FOR_PREREG_REVIEW = YES`

`V3_PREREG_FROZEN = NO`

`V3_RUN_AUTHORIZED = NO`

`V3_ARMED = NO`

`DEFAULT_V4 = NO`

`B2_06_EXECUTION_AUTHORIZED = NO`

The design unit is closed. The next authorized work is implementation/spec review only; fresh V3 acceptance outcomes remain forbidden.