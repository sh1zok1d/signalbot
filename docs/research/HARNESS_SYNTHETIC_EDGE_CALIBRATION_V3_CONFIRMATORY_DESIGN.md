# Harness Synthetic Edge Calibration V3 — Confirmatory design direction

Status: **DESIGN_DIRECTION_ACCEPTED / NOT PREREGISTERED / NOT FROZEN / NOT ARMED**

Date: 2026-09-16

This document records the accepted methodological direction for V3 after the canonical V2 control-calibration result `ffce3daa…` and its read-only forensic review.

It is intentionally not a preregistration, execution freeze, ARM, or implementation authorization. No fresh outcomes may be generated under this document alone.

## Problem V3 must solve

V2 established a coherent but unacceptable sensitivity/specificity profile:

- EASY MODEL_DETECTED: 365/400 = 91.25%, frozen Wilson lower 0.8807 → INDETERMINATE.
- MODERATE MODEL_DETECTED: 108/400 = 27%, frozen Wilson lower 0.2288 → FAIL.
- NULL MODEL_DETECTED: 2/400 = 0.5%, Wilson upper 0.0180 → PASS.
- TRAP: PASS.

The dominant bottleneck is the confirmatory bootstrap veto: all MODERATE misses and all EASY misses fail `bootstrap_positive`; identifiability and placebo separation are not dominant.

V3 must increase power by improving statistical efficiency, **not by weakening evidence requirements after observing V2**.

The design goal is:

> increase sensitivity to predeclared real effects while preserving or improving false-positive protection under NULL.

## Governing anti-overfit rule

V2 is development-consumed.

The V2 3200 worlds, their outputs, and the forensic diagnosis may be used to design V3. They may not be reused as confirmatory evidence for V3.

The sequence must be:

`V2 diagnosis → V3 design/development → V3 prereg/freeze → fresh sealed worlds/seeds → one acceptance execution → immutable result`

No acceptance threshold, null budget, block rule, statistic, or multiplicity rule may be selected after observing fresh V3 acceptance outcomes.

## 1. Align the estimand with the frozen claim

For event/state hypotheses, the primary estimand should measure incremental predictive value on the observations for which the hypothesis actually claims an effect.

The active support/state must be defined prospectively and independently of the outcome being tested.

V3 must not discover a profitable support region from the same outcomes used to validate it.

If support is learned, the lifecycle must separate learning from confirmation:

`development/train → freeze support definition → validation`

V3 must retain an explicit minimum support / effective-sample-size requirement so that a tiny support cannot manufacture a seemingly large effect.

## 2. Candidate contribution should be incremental by construction

Preferred production semantics:

`candidate prediction = frozen baseline prediction + candidate overlay inside frozen support`

Outside claim support, the candidate should fall back to the baseline rather than allowing an unrelated global refit to dilute or alter the estimand.

The purpose is to isolate the incremental claim being tested and avoid averaging a sparse 10% effect across 90% observations where the claim predicts no change.

A preregistered global-harm guard must remain so that a locally positive candidate cannot hide material damage to the overall forecast or to excluded observations.

## 3. One primary confirmatory test

V2 combined multiple significance-like gates in an AND conjunction:

`primary_positive AND bootstrap_positive AND placebo_separation`

V3 should not use multiple correlated significance tests as independent binary vetoes for the same confirmatory claim.

The preferred V3 architecture is one primary confirmatory statistic/test, with additional resampling/stability mechanisms retained as diagnostics and falsification evidence rather than duplicate significance gates.

## 4. Studentized prequential OOS statistic

The preferred primary statistic is a studentized out-of-sample incremental loss differential aligned to the frozen support.

Conceptually:

`T = estimated incremental OOS effect / dependence-aware uncertainty estimate`

The exact loss function, standard-error estimator, dependence treatment, and support weighting must be frozen prospectively.

The purpose is to distinguish a stable small effect from an equally sized but noisy effect and improve statistical efficiency without loosening the false-positive budget.

## 5. Dependence-aware null calibration

The primary confirmatory test should derive its decision from a dependence-aware null/randomization or resampling distribution rather than from an ad-hoc post-outcome threshold change.

Candidate methods include block/circular randomization and dependent bootstrap families. The exact invariance/exchangeability assumptions and implementation must be reviewed before preregistration.

Important limitation: ordinary permutation does not automatically provide exact type-I control for dependent market-like time series. V3 may claim calibrated type-I control only under an explicitly justified dependence-preserving scheme and must still demonstrate NULL protection on fresh sealed synthetic worlds.

The empirical p-value, test statistic, and margin to the null boundary must be persisted per world/candidate.

## 6. Multiplicity control

When a frozen family contains multiple candidate features/hypotheses, V3 should control family-wise false positives prospectively.

Preferred direction: dependence-aware **step-down maxT / Westfall–Young-like** adjustment rather than a single coarse maxT cutoff, subject to validity under the selected resampling scheme.

This controls multiplicity inside one frozen family. It does not by itself solve adaptive research-wide multiple testing across repeatedly generated hypotheses; that remains a separate research-governance problem.

## 7. Separate sensitivity, specificity, and robustness

V3 should explicitly separate three roles:

### Sensitivity

A claim-aligned, statistically efficient primary statistic should extract the signal the hypothesis actually asserts.

### Specificity

A prospectively frozen null-calibrated confirmatory test plus multiplicity control should determine the false-positive budget.

### Robustness

Bootstrap intervals, placebo diagnostics, era stability, support sanity, materiality, and related checks should remain visible and may still support explicit falsification/guard conditions, but they should not be stacked as redundant significance vetoes without a separate scientific reason.

## 8. Oracle / near-oracle power benchmark

V3 Microscope development should include a synthetic-only oracle or near-oracle benchmark using information available only because the DGP is known.

Purpose:

> determine whether the predeclared MODERATE DGP contains enough information for the desired power at the selected false-positive budget.

Interpretation:

- if an oracle/near-oracle test has high MODERATE power but the production validator does not, the production statistic/test is inefficient;
- if even the oracle/near-oracle benchmark cannot reach the target power, the calibration target or DGP may be information-limited rather than merely suffering from a poor production test.

The oracle benchmark is Microscope-only. It must never become production evidence or use protected market outcomes.

## 9. Persist diagnostic statistics prospectively

V3 WORLD_RECORDS should preserve, at minimum where applicable:

- raw incremental effect / loss differential;
- support count and effective N;
- uncertainty estimate / SE;
- studentized statistic;
- unadjusted empirical p-value;
- multiplicity-adjusted p-value;
- bootstrap lower quantile(s), including the analogue of `q025` if retained;
- placebo/null upper quantile(s), including the analogue of `q95` if retained;
- margin between observed statistic and decision boundary;
- selected/frozen dependence or block parameter;
- era-level effects;
- visibility state;
- identifiability state and reason;
- global-harm diagnostic/guard result.

No required diagnostic should be computed and discarded if it is needed to explain an acceptance failure later.

## 10. NULL acceptance must be prospectively powered

V3 must not choose its nominal alpha or NULL threshold merely because V2 happened to observe `2/400` NULL detections.

The acceptable false-positive budget must be chosen on scientific/product grounds before the sealed run.

If V3 intends to make a very strict claim such as an upper false-positive rate near 0.5%, the NULL acceptance suite must contain enough fresh replicates to support that claim with the predeclared confidence method. A small 400-world NULL cell may be insufficient to prove such a low upper bound even if it observes zero false detections.

The acceptance grid may therefore be asymmetric: more NULL replications can be allocated without multiplying every other cell equally.

## 11. V2 acceptance targets are not to be weakened post hoc

The prior EASY/MODERATE objectives remain the reference objectives:

- EASY: high confirmatory power, historically targeted around 90% lower-bound criterion.
- MODERATE: materially useful confirmatory power, historically targeted around 70% lower-bound criterion.

V3 design must not lower these targets merely because V2 failed.

Before final V3 preregistration, the oracle/near-oracle benchmark should establish whether the desired MODERATE target is information-theoretically reasonable at the prospectively chosen false-positive budget. Any change to the calibration target must be justified prospectively by that feasibility analysis, not by the V2 failure alone.

## 12. Fresh sealed acceptance

After methodology development is complete:

1. freeze V3 scientific semantics;
2. freeze DGPs, seed namespace, world identities, acceptance rules, and diagnostics;
3. independently review the freeze;
4. ARM exactly one fresh acceptance execution;
5. use fresh worlds/seeds not consumed by V2 development;
6. persist complete evidence;
7. evaluate mechanically;
8. no rescue, threshold change, selective rerun, or second attempt after outcomes.

## 13. Performance is secondary to scientific validity

The V2 performance forensic showed that a large fraction of wall-clock latency came from full mint-time scientific re-authentication and artifact I/O stalls rather than the first grid itself.

V3 design may later separate scientific execution cost from evidence-authentication cost and remove avoidable duplicate work only when exact equivalence/authenticity is preserved.

Performance work is not authorized by this design document and must not become another open-ended infrastructure program.

## Explicit non-decisions / items still requiring methodology review

Before a V3 preregistration can be frozen, the following must be resolved prospectively:

- exact support-aligned estimand and loss function;
- exact studentization / dependence-aware uncertainty estimator;
- exact dependence-preserving randomization/bootstrap scheme;
- exact block/dependence parameter rule, including how it is selected without acceptance-outcome leakage;
- exact family-wise multiplicity procedure and assumptions;
- exact global-harm guard;
- exact false-positive budget / nominal alpha;
- exact NULL replication count and confidence criterion;
- exact oracle/near-oracle benchmark definition;
- exact EASY/MODERATE/NULL/TRAP acceptance criteria for the fresh sealed run.

## Current verdict

`GO_FOR_V3_DESIGN`

`GO_FOR_V3_RUN = NO`

`B2_06_EXECUTION_AUTHORIZED = NO`

The intended V3 architecture is:

`frozen claim-aligned incremental effect`
→ `studentized prequential OOS statistic`
→ `one dependence-aware confirmatory null test`
→ `step-down family-wise multiplicity control`
→ `separate robustness diagnostics / harm guards`
→ `fresh sealed acceptance`

The goal is not to make MODERATE pass by relaxing V2. The goal is to build a more statistically efficient confirmatory instrument while keeping false-positive protection independently constrained.
