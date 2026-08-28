# V2 Research Harness v1

**Status:** `IMPLEMENTATION_CANDIDATE / SYNTHETIC_TESTS_ONLY`  
**Initial branch point:** `main @ d983597898babf732e39dd5847ecb5d0b9e576c4`  
**Current PR base:** `main` (CI evaluated through GitHub's current synthetic merge)  
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

### 1. Exact clean Git freeze before outcome access

A real outcome runner must call `verify_git_freeze(...)` against a predeclared
full 40-character commit SHA.

The check requires:

- current `HEAD` exactly equals that SHA; and
- the working tree is clean, including untracked files.

`build_run_identity(...)` accepts only the resulting verified code-freeze
proof, not an arbitrary caller-supplied SHA string.

### 2. Dataset identity before outcome paths

Harness v1 is discovery-only. Its dataset authorization contract is fixed to
`ACCEPTED_FOR_DISCOVERY`, `research_authorized=true`, and
`confirmatory_authorized=false`; a caller cannot weaken those requirements.

A new experiment must obtain an `AuthorizedDataset` by verifying both:

- the repository dataset manifest; and
- the runtime `reports/snapshot_manifest.json`.

Only after both identities match may the runner request monthly parquet paths.
The runtime dataset ID is mandatory and is read from either a top-level field
or the materializer's canonical `identity_payload.dataset_id`.
Direct construction of `AuthorizedDataset` fails closed; the authorization
factory is the intended path.

The partition selector enumerates explicit allowed years such as
`2020-*.parquet`; it does not broadly load all years and filter rows later.
Every `allowed_year` must also fall inside the frozen policy time-window.

Before any selected parquet path is returned to a runner, its bytes are hashed
and must match the frozen SHA256 recorded in the runtime snapshot's
`output_checksums`. Missing checksum registration or byte drift fails closed.

### 3. Outcome-window boundary

Harness v1 authorizes only the `development` stage. The project-wide discovery
embargo is hard-coded at `2025-01-01T00:00:00Z`; a policy ending later is
rejected before any outcome path is authorized.

Every candidate outcome window must satisfy the experiment's frozen
`OutcomeAccessPolicy`.

For an end-exclusive boundary `E`, `T + H >= E` is rejected.

### 4. No-lookahead availability

Every input used at decision time `T` must satisfy:

`available_at_ms <= T`

Equality is allowed. Any future availability fails closed. Integer-like
NumPy scalar timestamps are handled as scalar timestamps rather than iterable
objects.

### 5. Same-support comparisons

Candidate/control deltas must be computed on exactly the same support.

Two reusable forms exist:

- paired support by observation identity;
- weighted support by structural/stratum key.

Silent key intersection is forbidden. If candidate/control supports differ, the
experiment must supply an explicit predeclared support subset or fail.

This specifically prevents the H05 B-01/M-01 class in which a full candidate
mean can be compared with a comparator estimated on only a restricted subset.

### 6. Fail-closed promotion gates

Mandatory gates pass only when every required gate exists and is literal
Python `True`.

Missing values, `None`, truthy integers such as `1`, or an empty required-gate
list do not promote.

Hypothesis-specific neighborhood/robustness logic remains part of the
preregistered experiment; this harness deliberately does not invent one
universal promotion rule.

### 7. Immutable result/provenance artifact

`build_run_identity(...)` records the hypothesis/stage/code SHA, dataset
identity, authorized window, command, and stochastic seeds.

`write_json_new(...)` creates a canonical JSON artifact exactly once,
refuses overwrite, rejects non-finite JSON numbers such as NaN/Infinity, and
returns the artifact SHA256.

## Self-red-team hardening already applied

Before independent review, this implementation candidate was repaired against
the following bypass classes without opening real outcomes:

- allowed years inconsistent with the frozen time window;
- caller-supplied/unverified code SHA or dirty working tree;
- direct construction of an authorized dataset proof;
- NumPy integer-scalar availability timestamps;
- caller-selected validation/confirmatory stage or an outcome policy reaching 2025;
- caller weakening of accepted/research-authorized dataset status;
- missing runtime dataset identity despite a matching snapshot ID;
- non-finite NaN/Infinity values in supposedly canonical result JSON.

These are implementation repairs, not evidence about market behavior.

## Adversarial synthetic tests

The v1 test suite currently contains 18 synthetic test cases and must cover at least:

- attempts to weaken accepted/research-authorized dataset status;
- non-development stage or policy reaching the 2025 validation pool;
- allowed year outside the frozen time-window;
- missing repository manifest;
- attempted direct construction of an authorized dataset proof;
- missing/mismatched runtime dataset identity and runtime snapshot mismatch;
- selected parquet missing from frozen output checksums or changed bytes;
- a 2025 partition physically present but invisible to a 2020-2021 policy;
- wrong/abbreviated Git SHA and dirty-tree freeze attempts;
- outcome-window boundary reach;
- future `available_at_ms`;
- silent paired-support intersection;
- full-candidate vs overlap-only structural comparison;
- non-positive structural weights;
- missing/`None`/integer promotion gates;
- attempted result overwrite;
- non-finite NaN/Infinity result serialization.

No test in this unit may require or inspect real market outcomes.

## Required usage for Batch02

Every new Batch02 experiment must:

1. verify an exact clean Git freeze SHA before outcome access;
2. define its dataset identity and outcome policy before outcome access;
3. use the access guard to obtain allowed data paths;
4. check feature availability at each decision boundary;
5. use same-support primitives for any comparator whose support can differ;
6. expose machine-readable gate values and use fail-closed conjunction for
   mandatory per-cell gates;
7. persist provenance + results through a non-overwriting artifact path;
8. add hypothesis-specific adversarial tests before the first real outcome
   run.

## Mandatory independent review gate

For Research Harness changes and every new Batch02+ hypothesis implementation,
independent review is a required pre-outcome gate, not an optional courtesy.

The canonical review sequence is:

1. implementation/self-red-team;
2. CI green on the exact candidate SHA;
3. CodeRabbit independent code review;
4. independent adversarial LLM review (Claude Code or Cursor) focused on
   research-integrity bypasses;
5. final adjudication of all findings;
6. freeze the exact reviewed SHA;
7. merge only after the gate is closed.

Reviewer responsibilities are intentionally different:

- **CodeRabbit:** implementation defects, API misuse, Python edge cases,
  maintainability hazards, and suspicious diff-level behavior;
- **Claude Code / Cursor adversarial review:** embargo/outcome-access bypasses,
  Git/dataset provenance forgery, no-lookahead failures, same-support failures,
  promotion forgery, and evidence mutability;
- **final adjudication:** classify every finding as blocker, material,
  non-blocking, irrelevant, or false positive and decide whether repair is
  required.

All independent reviewers must review the **same exact commit SHA**.

No reviewer may silently repair the candidate during review. If any repair
commit is created:

- the previously reviewed SHA is no longer the acceptance candidate;
- CI must run again;
- CodeRabbit must review the new SHA again;
- adversarial LLM review must review the new SHA again;
- final adjudication must be repeated;
- only the final fully reviewed SHA may be frozen.

A review of an ancestor SHA does not count for a repaired descendant.

For pre-outcome research code, the minimum acceptance condition is therefore:

`CI_GREEN && CODERABBIT_REVIEWED && ADVERSARIAL_LLM_REVIEWED && FINDINGS_ADJUDICATED`

before freeze/merge or first outcome access.

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
- CodeRabbit must independently review the exact candidate SHA;
- an independent pre-outcome adversarial LLM red-team must attack Git identity,
  no-lookahead, support, dataset identity, promotion forgery, and evidence
  mutability on that same exact SHA;
- all findings must be adjudicated;
- any repair must remain outcome-blind and resets the independent-review gate;
- the final reviewed SHA must be frozen before Batch02 outcome access.

Until then:

```text
V2_RESEARCH_HARNESS_V1 = IMPLEMENTATION_CANDIDATE
BATCH02 = NOT_STARTED
REAL_OUTCOMES_OPENED_BY_HARNESS_UNIT = NO
```
