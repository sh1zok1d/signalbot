# V2 Research Harness v1

**Status:** `IMPLEMENTATION_CANDIDATE / SYNTHETIC_TESTS_ONLY`  
**Base:** `main @ d983597898babf732e39dd5847ecb5d0b9e576c4`  
**Outcome access in this unit:** `NONE`

## Purpose

Batch01 closed with 0/5 promoted families, but H05's red-team cycle exposed
several research-integrity controls that should not have to be rediscovered
inside every future hypothesis.

`V2_RESEARCH_HARNESS_V1` makes the minimum controls executable for Batch02+.
It is not a trading model, does not define a hypothesis, does not define
promotion thresholds, and does not authorize Batch02 outcome access.

Frozen H01-H05 code remains untouched. Those runners are historical evidence,
not refactoring targets.

## Mandatory primitives

### 1. Dataset identity before outcome paths

A new experiment must obtain an `AuthorizedDataset` by verifying both:

- the repository dataset manifest; and
- the runtime `reports/snapshot_manifest.json`.

Only after both identities match may the runner request monthly parquet paths.

The partition selector enumerates explicit allowed years such as
`2020-*.parquet`; it does not broadly load all years and filter rows later.

### 2. Outcome-window boundary

Every candidate outcome window must satisfy the experiment's frozen
`OutcomeAccessPolicy`.

For an end-exclusive boundary `E`, `T + H >= E` is rejected.

### 3. No-lookahead availability

Every input used at decision time `T` must satisfy:

`available_at_ms <= T`

Equality is allowed. Any future availability fails closed.

### 4. Same-support comparisons

Candidate/control deltas must be computed on exactly the same support.

Two reusable forms exist:

- paired support by observation identity;
- weighted support by structural/stratum key.

Silent key intersection is forbidden. If candidate/control supports differ, the
experiment must supply an explicit predeclared support subset or fail.

This specifically prevents the H05 B-01/M-01 class in which a full candidate
mean can be compared with a comparator estimated on only a restricted subset.

### 5. Fail-closed promotion gates

Mandatory gates pass only when every required gate exists and is literal
Python `True`.

Missing values, `None`, truthy integers such as `1`, or an empty required-gate
list do not promote.

Hypothesis-specific neighborhood/robustness logic remains part of the
preregistered experiment; this harness deliberately does not invent one
universal promotion rule.

### 6. Immutable result/provenance artifact

`build_run_identity(...)` records the hypothesis/stage/code SHA, dataset
identity, authorized window, command, and stochastic seeds.

`write_json_new(...)` creates a canonical JSON artifact exactly once and
refuses overwrite. It returns the artifact SHA256.

## Adversarial synthetic tests

The v1 test suite must cover at least:

- missing repository manifest;
- runtime snapshot mismatch;
- a 2025 partition physically present but invisible to a 2020-2021 policy;
- outcome-window boundary reach;
- future `available_at_ms`;
- silent paired-support intersection;
- full-candidate vs overlap-only structural comparison;
- non-positive structural weights;
- missing/`None`/integer promotion gates;
- attempted result overwrite.

No test in this unit may require or inspect real market outcomes.

## Required usage for Batch02

Every new Batch02 experiment must:

1. define its dataset identity and outcome policy before outcome access;
2. use the access guard to obtain allowed data paths;
3. check feature availability at each decision boundary;
4. use same-support primitives for any comparator whose support can differ;
5. expose machine-readable gate values and use fail-closed conjunction for
   mandatory per-cell gates;
6. persist provenance + results through a non-overwriting artifact path;
7. add hypothesis-specific adversarial tests before the first real outcome
   run.

## Non-goals

This unit does **not**:

- rerun or modify H01-H05;
- open 2025 validation or 2026 OOS;
- create H06;
- design Batch02 hypotheses;
- standardize a single statistical estimand for every hypothesis;
- set MPIE/control/bootstrap thresholds;
- replace independent red-team review.

## Acceptance boundary

Before this harness becomes the canonical Batch02 base:

- implementation tests must pass;
- an independent pre-outcome red-team must attempt no-lookahead, support,
  dataset-identity, and promotion-forgery attacks;
- any repair must remain outcome-blind;
- the audited SHA must be frozen before Batch02 outcome access.

Until then:

```text
V2_RESEARCH_HARNESS_V1 = IMPLEMENTATION_CANDIDATE
BATCH02 = NOT_STARTED
REAL_OUTCOMES_OPENED_BY_HARNESS_UNIT = NO
```
