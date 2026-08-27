# H03 Design — Maintainer Addendum

**Reviewed PR:** #76  
**Claude red-team HEAD reviewed:** `9d7b7a9ca0e700c8df4be8639d08d6c74f273f42`  
**Maintainer correction commit:** `dba4594e538248898725dfac14403910eb74bca5`

The independent red-team correctly found no blocker and substantially improved the H03 design. Before accepting the design for preregistration, the maintainer independently inspected PRs #77/#78 and the corrected draft and closed several remaining methodological degrees of freedom.

## 1. Global adaptivity disclosure is now complete

Remote H01/H02 artifacts were inspected directly.

Facts now frozen into §0:

- H03 mechanism class predates H01/H02 outcomes and already existed in the original R2 roadmap.
- 15m decision-grid / 30d local-reference conventions are inherited from H01.
- the 15/30/60/120/240m outcome ladder is shared by H01 and H02 and is treated as a project research convention, not selected from their outcomes;
- matched-random / weekly-block / +6h timing-control conventions are inherited research conventions as applicable;
- H02 used a 30m refractory; H03's 60m refractory is therefore **not** copied from H02 and is frozen as a new pre-outcome clustering choice;
- q90/q95/q98 is new to H03 and was not present in H01/H02;
- H01/H02 post-hoc directional findings did not define H03's mechanism/sign alternatives.

The batch-internal influence of prior clustering/dependence lessons is disclosed rather than hidden.

## 2. Percentile convention is frozen

`P_W(T)` now uses H01's existing midrank formula:

`(#{ref < x} + 0.5*#{ref == x}) / N_ref`.

This removes tie-handling as an implementation degree of freedom.

## 3. Reference-window effective-N disclosure is corrected

The previous draft used only `W` while claiming to cover normalization statistics based on `H`.

The corrected design separately reports:

- `N_eff_W` for impulse-percentile construction;
- expected q-tail count proxy;
- moderate-band count proxy;
- per-decile count proxy;
- `N_eff_H` for H-horizon normalization references.

The prior arbitrary 200-observation caution threshold was removed. These quantities are transparency diagnostics, not a new pass/fail gate.

## 4. Full-development denominator floor is removed

The red-team's proposed 5th-percentile floor was computed from the full development-window series of trailing scales. Even though each scale observation itself was pre-T, using a quantile of the entire 2020–2024 series as the floor for earlier T would violate strict as-of semantics.

Canonical H03 rule:

- use the trailing pre-T median absolute H-return scale directly;
- zero/non-finite/unavailable denominator => ineligible and counted;
- no post-outcome statistical floor or winsorization;
- report denominator quantiles and a fixed top-1%-normalized-influence diagnostic so any instability is visible instead of silently repaired.

## 5. Matched-random contamination is prevented

Within each replicate:

- sample without replacement;
- exclude raw qualifying extreme timestamps for the same `(W,q)` from the random pool;
- do **not** exclude surrounding hours/regimes.

This prevents the baseline from directly sampling treated timestamps without manufacturing an artificially quiet control regime.

Day-of-month/day-of-week residual imbalance is now reported with deterministic total-variation distance rather than an undefined visual judgment.

## 6. Negative-control collision is disclosed

For the +6h control, report how often shifted timestamps collide with a raw true extreme timestamp for the same `(W,q)`.

Do not remove collisions post hoc.

## 7. Dependence diagnostic is made conservative to non-monotone ACF

The prior "first lag below 0.20" rule could report short dependence if ACF dipped early then rose again.

Canonical diagnostic:

`L_dep = max{L in {1,2,4,8,16,32,64} days : |ACF(L)| >= 0.20}`.

Report `<1 day` if none; `>=64 days` if 64d still qualifies.

This remains a single non-selectable descriptive diagnostic.

## 8. "Materially" is numerically frozen

Primary MPIE remains:

`0.10` normalized units vs matched random.

For structural/negative-control separation:

`CONTROL_DELTA_MIN = 0.05`

(equal to one-half of MPIE) is frozen pre-outcome.

For selected sign `S` (+1 continuation, -1 exhaustion):

- structural: `S*(mean_extreme - mean_moderate) >= 0.05`;
- timing control: `S*(mean_true - mean_shifted) >= 0.05`.

This removes post-outcome reinterpretation of the word "material."

## Final maintainer assessment

After these corrections:

- no unresolved methodological blocker remains in the H03 design;
- H03 is ready for actual preregistration + implementation freeze;
- development outcomes must still remain unopened until that freeze commit exists.

Validation state:

- 2025 inspected: **NO**
- 2026 inspected: **NO**
- H03 real outcomes computed: **NO**

**Maintainer verdict: READY TO PREREGISTER.**
