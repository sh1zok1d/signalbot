# Harness Synthetic Edge Calibration V3 — Confirmatory design direction

Status: **DESIGN_DIRECTION_REVISED / NOT PREREGISTERED / NOT FROZEN / NOT ARMED**

Date: 2026-09-16

This document records the revised V3 methodological direction after the canonical V2 control-calibration result `ffce3daa…`, the read-only V2 forensic review, and a second adversarial review of the proposed V3 design.

It is intentionally **not** a preregistration, execution freeze, ARM, implementation authorization, or permission to generate fresh acceptance outcomes.

The governing project constraint is explicit:

> V3 is a bounded repair of one measured sensitivity problem. It must not become an open-ended attempt to perfect the Microscope before real market research resumes.

## 0. What V2 actually established

V2 produced a valid but unacceptable confirmatory-power profile:

- EASY MODEL_DETECTED: `365/400 = 0.9125`; frozen two-sided 95% Wilson lower `0.8807` → `INDETERMINATE` against the historical 0.90 lower-bound requirement.
- MODERATE MODEL_DETECTED: `108/400 = 0.27`; frozen two-sided 95% Wilson lower `0.2288` → `FAIL` against the historical 0.70 lower-bound requirement.
- NULL MODEL_DETECTED: `2/400 = 0.005`; frozen two-sided 95% Wilson upper `0.0180` → `PASS` against the historical 0.05 upper-bound requirement.
- TRAP: `PASS`.

The important attrition result is not ambiguous:

- MODERATE: 400 identifiable → 355 primary-positive → 334 placebo-separated → only 108 bootstrap-positive → 108 MODEL_DETECTED.
- all 292 MODERATE misses fail bootstrap confirmation;
- 226/292 MODERATE misses pass both the primary sign and placebo separation but fail bootstrap;
- all 35 EASY misses are likewise bootstrap-only misses after primary + placebo pass.

Therefore V3 is justified by a concrete measured problem: the current confirmatory uncertainty gate is much less sensitive than the point-estimate and placebo paths on the preregistered MODERATE DGP.

However, V2 does **not** prove that the observed NULL point estimate of 0.5% is the true false-positive rate, nor that V3 should preserve or improve that exact number. The relevant V2 scientific constraint was the prospectively frozen false-positive ceiling, not minimization of FPR at any cost.

## 1. Revised V3 objective

The previous wording — "increase sensitivity while preserving or improving the observed NULL rate" — is rejected as unnecessarily conservative and partly outcome-anchored.

The V3 design objective is instead:

> **maximize confirmatory sensitivity to a predeclared effect subject to a prospectively fixed acceptable false-positive budget and preserved nonstationary/trap protection.**

The design must not treat a lower false-positive point estimate as automatically better if it is purchased by severe false negatives.

For continuity and to avoid post-outcome target shopping, the default V3 specificity budget inherits the original ORACLE NULL ceiling:

`NULL false-positive rate <= 0.05`

The V2 observation `2/400 = 0.005` is evidence about V2, **not** a new V3 target.

Any change to the 0.05 budget before V3 freeze would require an independent pre-outcome justification unrelated to making V3 pass.

## 2. Governing anti-overfit rule

V2 is development-consumed.

The V2 3200 worlds and their forensic diagnosis may be used to motivate and design V3, but they cannot be reused as confirmatory evidence for V3.

Required sequence:

`V2 diagnosis → bounded V3 design/development → V3 prereg/freeze → fresh sealed worlds/seeds → one acceptance execution → immutable result`

No V3 acceptance threshold, statistic, dependence rule, confidence rule, or false-positive budget may be selected after fresh V3 acceptance outcomes are inspected.

Fresh seeds protect against seed overfit only; they do not prove universal validity across every possible DGP. V3 is allowed to establish adequacy on the canonical synthetic stress family. Generalization to real market research must be learned from real market studies, not from an ever-expanding synthetic scenario catalog.

## 3. V3 core is confirmatory, not discovery

V3 core answers one question:

> given one frozen hypothesis/claim, can the validator detect its predeclared incremental predictive effect with adequate power while respecting the false-positive budget?

V3 core does **not** solve multi-candidate discovery, research-wide adaptive multiple testing, strategy search, or model selection across a large family.

Therefore step-down maxT / Westfall–Young / SPA / Reality-Check-style multi-candidate machinery is **not part of the mandatory V3 confirmatory core**.

Those procedures may become relevant later for the discovery/search layer. They must not delay the confirmatory validator repair or MARKET work.

## 4. Claim-aligned primary estimand

The scientific core of V3 is not an overlay implementation detail. It is the estimand.

For each scored observation define the out-of-sample loss differential:

`d_t = L(BASE_t, Y_t) - L(CANDIDATE_t, Y_t)`

A frozen hypothesis defines a prospective claim weight/support `w_t`, independent of the outcome being tested.

For a binary event/state hypothesis:

`w_t in {0,1}`

The primary claim-aligned estimand is conceptually:

`theta = sum(w_t * d_t) / sum(w_t)`

For a future hypothesis with a non-binary predeclared exposure, a prospectively frozen weight definition may be used instead. V3 must not discover profitable weights/support from the same outcomes used for confirmation.

If support/weights are learned, lifecycle separation is mandatory:

`development/train → freeze support/weights → confirmation`

Minimum support and effective-sample-size requirements remain necessary to prevent a tiny support from manufacturing a large-looking conditional effect.

### Explicit semantic change from V2

V2 primarily judged pooled predictive improvement over the entire scored population. V3 intentionally targets the conditional/incremental effect asserted by the frozen claim.

This is a new estimand, not merely a more powerful implementation of the identical pooled question. It is adopted because Signalbot's intended market hypotheses are commonly event/state conditional.

Unconditional/pool-wide effect remains mandatory reporting, but is not the primary confirmatory estimand for a conditional claim.

## 5. Candidate prediction semantics

A clean implementation may use:

`candidate prediction = frozen baseline prediction + frozen candidate contribution inside claim support`

with exact fallback to baseline outside support.

This is preferred when it faithfully represents the claim because it isolates the incremental component and avoids unrelated global refit drift.

However, the overlay form itself is **not** the scientific objective. A different implementation is acceptable if it preserves the same prospectively frozen estimand and chronology.

If candidate prediction is exactly equal to baseline outside support, an additional off-support significance test is redundant by construction. V3 should report unconditional effect and economic/materiality diagnostics rather than add another duplicate significance veto.

If a future model changes predictions outside support, then a distinct harm guard may again be scientifically necessary.

## 6. One primary confirmatory test

V2 required a conjunction of significance-like gates:

`primary_positive AND bootstrap_positive AND placebo_separation`

V3 must not stack multiple correlated tests of essentially the same null as independent binary vetoes without a distinct scientific reason.

The mandatory architecture is:

`claim-aligned OOS loss differential`
→ `one primary studentized statistic`
→ `one dependence-aware confirmatory null calibration`
→ `DETECTED / NOT_DETECTED`

Other checks may still fail closed when they target a genuinely different failure mode, such as chronology leakage, invalid support, non-identifiability, or a predeclared nonstationary trap. They must not become redundant significance gates merely because more gates appear more rigorous.

## 7. Studentization: useful normalization, not assumed power repair

Preferred statistic:

`T = estimated claim-aligned OOS effect / dependence-aware uncertainty estimate`

Studentization is retained because the same raw effect can imply very different evidence under different noise/dependence levels, and because a normalized statistic is useful for dependence-aware resampling.

But V3 must not assume that studentization automatically improves power. A poor uncertainty estimator for sparse clustered support can simply create a different bad test.

The exact loss function, uncertainty estimator, finite-sample behavior, and handling of nested baseline/candidate forecasts must be justified prospectively and tested on fresh NULL/MODERATE acceptance worlds.

Nested forecast comparison is an explicit concern: the baseline and candidate may be nested, so under the null the larger model can incur estimation noise even when the incremental coefficient is zero. The V3 design/review must verify that the selected confirmatory procedure is appropriate for the actual forecast construction rather than blindly importing an equal-predictive-accuracy test intended for another setting.

## 8. Dependence-aware confirmatory calibration

Ordinary row permutation is not the default V3 direction. Exchangeability cannot be assumed for clustered/dependent market-like series.

Preferred bounded design direction:

> use **one** established dependence-aware resampling/test family for the studentized claim-aligned loss differential, with one prospectively defined dependence/block-parameter rule.

A stationary/block-bootstrap-type family is the current preferred direction, subject to methodology review of its assumptions for the final statistic.

The design unit must choose one defensible method; it must **not** become a tournament across many resampling procedures optimized on V2 outcomes.

The dependence/block parameter must not be hand-picked because `50` performed poorly in V2. Use one predeclared automatic rule or one independently justified fixed rule before fresh acceptance outcomes.

The final per-world evidence must persist the observed statistic, null/resampling distribution summary, empirical/derived decision quantity, critical value or p-value, and margin to the boundary.

## 9. Specificity and aggregate confidence rule

V3 distinguishes two layers:

1. per-world confirmatory decision under a prospectively frozen type-I rule;
2. Monte Carlo evidence that the complete validator meets the desired sensitivity/specificity envelope across fresh worlds.

The V2 aggregate gate used two-sided 95% Wilson intervals (`z≈1.96`) even though the acceptance questions are one-sided (`power >= threshold`, `FPR <= threshold`). That is conservative but not wrong.

V3 must make this choice explicit rather than inherit it accidentally.

Current design direction:

> use **95% one-sided confidence bounds** for one-sided Monte Carlo acceptance claims, unless independent pre-freeze review establishes a specific reason to retain the more conservative two-sided construction.

This change cannot by itself rescue MODERATE `27%`; it merely aligns the confidence construction with the directional acceptance question.

Historical reference objectives are not lowered because V2 failed:

- EASY target: power at least 0.90;
- MODERATE target: power at least 0.70;
- NULL ceiling: false-positive rate at most 0.05;
- TRAP/nonstationarity protection remains required.

Exact fresh-world counts and the mechanical one-sided confidence formulas must be frozen before the acceptance run. There is no requirement to enlarge NULL solely to prove a 0.5% FPR, because 0.5% is not the V3 target.

## 10. Robustness diagnostics remain separate from significance

V3 should report, where applicable:

- support/effective N;
- unconditional pooled effect;
- era-level effects;
- economic/materiality diagnostics;
- bootstrap/null distribution summaries;
- visibility;
- identifiability and reason;
- chronology/leakage status;
- nonstationary/trap behavior.

A robustness item may remain a hard guard only when it protects a distinct failure mode. It must not be converted into another correlated significance veto merely to make the validator look stricter.

## 11. Near-oracle synthetic diagnostic — non-authoritative and non-blocking

The earlier V3 draft described an oracle as an "information-theoretic" feasibility benchmark. That wording is rejected as too strong.

A DGP-aware oracle can have access to information unavailable to a production validator, so high oracle power does not prove that an operational procedure can attain the same power.

V3 may include a **limited near-oracle diagnostic reference** if it can be implemented cheaply and without delaying the main design:

- same scored observations;
- same claim support/weights visible to the production claim;
- same loss target;
- only clearly specified idealized nuisance knowledge.

Its role is descriptive:

> determine whether the synthetic signal appears statistically recoverable under a favorable reference procedure.

It is not production evidence, not an acceptance gate, not an information-theoretic bound, and not a prerequisite for V3 execution.

## 12. Persist complete diagnostic statistics prospectively

V3 WORLD_RECORDS must preserve, at minimum where applicable:

- raw claim-aligned incremental effect/loss differential;
- unconditional/pool-wide effect;
- support count and effective N;
- uncertainty estimate / SE;
- studentized statistic;
- decision p-value/critical value or equivalent;
- margin to decision boundary;
- resampling/null distribution summaries required to explain a miss;
- selected/frozen dependence/block parameter;
- era-level effects;
- visibility state;
- identifiability state and reason;
- chronology/leakage status;
- materiality/economic diagnostic.

No statistic needed to explain an acceptance failure should be computed and discarded as V2 discarded the useful `bootstrap_q025` / `placebo_q95` values from canonical WORLD_RECORDS.

## 13. Fresh sealed acceptance

After the bounded methodology design is complete:

1. freeze the V3 estimand, loss, statistic, dependence method, dependence-parameter rule, false-positive budget, aggregate confidence rule, DGPs, seeds/world identities, acceptance thresholds, and diagnostics;
2. independently review that exact freeze;
3. ARM exactly one fresh acceptance execution;
4. use fresh world identities/seeds not consumed by V2 development;
5. persist complete evidence;
6. evaluate mechanically;
7. no rescue, threshold change, selective rerun, favorable reroll, or second acceptance attempt after outcomes.

Fresh V3 acceptance worlds may reuse the canonical synthetic scenario family; V3 does not need a large new catalog of DGPs before MARKET.

## 14. Hard stop against infinite Microscope work

V3 is intended to be the final scheduled Microscope iteration before MARKET.

Allowed sequence:

`one bounded methodology-design unit`
→ `one implementation + independent review unit`
→ `one fresh sealed V3 acceptance run`

There is **no default V4**.

Post-V3 policy:

- if V3 satisfies sensitivity, specificity, and trap requirements: close the Microscope program and move to MARKET;
- if V3 breaks specificity materially or exposes a concrete correctness flaw: one narrow blocker repair may be justified;
- if V3 retains controlled specificity but remains underpowered: record the measured detection limits and proceed to MARKET rather than automatically building V4.

Under the underpowered case, negative market results must be phrased as "not detected by a validator with measured power limits", not as proof of absence of edge.

Further validator work is authorized only when real market studies demonstrate that the measured power limitation is materially blocking research throughput or inference quality.

B2-06 remains independently blocked by its own observable/publication-authority problem; V3 does not waive that blocker. Conversely, the Microscope must not indefinitely block unrelated market research after the bounded V3 decision.

## 15. Performance is subordinate

The V2 post-run forensic showed that much of the ~8+ hour wall-clock latency came from full mint-time scientific re-authentication and broken artifact I/O rather than the first scientific grid.

No performance optimization program is required before V3 unless the V3 run cannot be completed reliably.

After V3, duplicate scientific recomputation and artifact I/O may be optimized only if a concrete throughput need exists and exact scientific/evidence equivalence is preserved.

Performance work must not become another prerequisite for MARKET.

## Explicit pre-freeze decisions still required

Only the following scientific decisions remain mandatory before V3 prereg/freeze:

1. exact claim-aligned loss function and support/weight semantics;
2. exact studentized statistic / uncertainty estimator, including nested-model treatment;
3. exactly one dependence-aware resampling/test family;
4. exactly one dependence/block-parameter rule;
5. exact one-sided Monte Carlo confidence formula and fresh-world counts;
6. exact mechanical EASY/MODERATE/NULL/TRAP acceptance mapping;
7. exact minimum support/effective-N validity rule;
8. exact list of distinct hard guards versus descriptive diagnostics.

Not mandatory before V3 freeze/run:

- step-down maxT / Westfall–Young or other multi-candidate discovery correction;
- research-wide alpha spending/FDR machinery;
- a large new synthetic DGP catalog;
- a perfect oracle benchmark;
- a performance rewrite;
- a trader-facing product layer.

## Current verdict

`GO_FOR_V3_DESIGN = YES`

`GO_FOR_V3_RUN = NO`

`DEFAULT_V4 = NO`

`B2_06_EXECUTION_AUTHORIZED = NO`

The revised V3 core is:

`frozen claim/support`
→ `claim-aligned conditional OOS loss differential`
→ `one studentized dependence-aware confirmatory test`
→ `fixed false-positive budget`
→ `separate robustness / validity diagnostics`
→ `fresh sealed acceptance`
→ `MARKET`

The goal is not to make MODERATE pass by relaxing V2. The goal is to correct one measured inefficiency, characterize the remaining detection limits, and then start accumulating real market evidence instead of indefinitely optimizing the measurement instrument.