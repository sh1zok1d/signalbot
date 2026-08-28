# V2 Research Harness v1

**Status:** `IMPLEMENTATION_CANDIDATE / SYNTHETIC_TESTS_ONLY`  
**Outcome access in this unit:** `NONE`  
**Batch02:** `NOT_STARTED`

## Purpose

Batch01 closed with 0/5 promoted families. H05 then showed that several
research-integrity controls were too important to rediscover independently
inside every new hypothesis.

`V2_RESEARCH_HARNESS_V1` turns the minimum reusable controls into executable
defaults for Batch02+.

It does not define a market hypothesis, promotion threshold, estimand, or
trading rule. Frozen H01-H05 code remains untouched historical evidence.

## Mandatory primitives

### 1. Exact tracked-code freeze

A real outcome runner must call `verify_git_freeze(...)` against a predeclared
full 40-character commit SHA.

The mechanical check requires:

- Git `HEAD` exactly equals that SHA;
- the supplied repo root is the Git top-level;
- the ordinary worktree is clean, including untracked non-ignored files;
- no tracked file uses `skip-worktree` or `assume-unchanged`;
- every tracked worktree blob hashes to the exact blob stored in `HEAD`.

The proof stores both the commit SHA and tree object ID.

The freeze is rechecked before dataset authorization and again when run
provenance is built.

This guarantee is deliberately limited to tracked repository bytes. The harness
is not an OS/Python security sandbox and does not claim to attest arbitrary
ignored files, external packages, interpreter internals, or malicious in-process
monkeypatching. Those remain review/environment responsibilities.

### 2. Dataset identity bound to the frozen Git commit

Dataset authorization requires the verified code-freeze proof.

For dataset `DATASET_ID`, the harness reads the canonical manifest from the
verified commit itself:

`docs/manifests/DATASET_ID.yaml`

using `git show <verified_sha>:<path>`.

The manifest's canonical `snapshot_manifest_path` is then read from the same
verified Git commit. A caller cannot substitute a different repository manifest
path or self-author a new checksum ledger without changing the frozen SHA.

The following must agree:

- frozen repository manifest dataset/snapshot identity;
- frozen Git snapshot evidence;
- runtime `reports/snapshot_manifest.json`;
- dataset authorization status.

Runtime `output_checksums` must exactly equal the checksum map frozen in Git.
A runtime JSON + parquet co-update therefore cannot redefine the accepted
snapshot.

### 3. Only authorized partitions are carried forward

Authorization enumerates only explicit allowed years and validates each selected
monthly parquet against the Git-frozen SHA256.

Selected parquet symlinks are rejected.

The returned `AuthorizedDataset` does not expose `dataset_root`. It carries
only the already-selected partition paths and their frozen checksums.

`list_monthly_partitions()` re-hashes those files before returning them, and
`build_run_identity(...)` rechecks them again before provenance is emitted.

This is an integrity boundary for compliant research code, not a filesystem
sandbox: a malicious Python process can still call `open()` on arbitrary paths.
Such direct access is outside harness compliance and must fail hypothesis
implementation review.

### 4. Outcome-window boundary

Harness v1 authorizes only the `development` stage.

The discovery/validation boundary is hard-coded at:

`2025-01-01T00:00:00Z`

A policy ending later is rejected.

For end-exclusive boundary `E`, any candidate with:

`T + H >= E`

is rejected.

### 5. No-lookahead availability

Every input used at decision time `T` must satisfy:

`available_at_ms <= T`

The helper accepts integer-like epoch-millisecond values, including NumPy
integer scalars.

It rejects:

- floats rather than truncating them;
- bools;
- strings/bytes;
- implausible epoch-millisecond magnitudes such as second timestamps;
- empty sequences;
- mismatched decision/availability lengths;
- future availability.

The helper does not prove that a hypothesis called it for every feature. That
remains a mandatory implementation/audit responsibility.

### 6. Same-support comparisons

Candidate/reference comparisons require exact support equality.

Reusable forms:

- paired support by observation identity;
- weighted support by structural/stratum key.

The generic helpers no longer expose `support_ids` / `support_keys` subset
arguments. Silent intersection and helper-level post-hoc overlap selection are
therefore forbidden.

NaN-like support keys and non-finite values fail closed. Structural weights
must be finite and strictly positive.

If a hypothesis legitimately requires a restricted support, that support must
be defined deterministically in the frozen hypothesis implementation before
outcome inspection and independently reviewed.

### 7. Promotion gate contract

Mandatory gate names are represented by an immutable
`PromotionGateContract`.

The contract:

- must be non-empty;
- must contain unique non-empty strings;
- is converted to an immutable tuple;
- has a deterministic SHA256;
- is recorded in run provenance.

`fail_closed_gate_conjunction(...)` passes only when every gate named by that
contract exists and is literal Python `True`.

The harness cannot prove the wall-clock moment at which a Python caller decided
which gates to place in source code. Therefore every Batch02 hypothesis must
show, during pre-outcome review, that its gate contract is declared in the
frozen implementation/preregistration rather than constructed from observed
results.

### 8. Immutable result/provenance artifact

`build_run_identity(...)` records at least:

- hypothesis and stage;
- exact code commit SHA;
- exact Git tree object ID;
- dataset and snapshot ID;
- canonical frozen manifest/snapshot Git paths;
- selected partition relative paths + SHA256;
- authorized outcome window;
- promotion gate names + gate-contract SHA256;
- command;
- stochastic seeds.

Before emitting provenance, the function rechecks the code freeze and selected
partition bytes.

`write_json_new(...)`:

- uses exclusive create;
- refuses overwrite;
- rejects NaN/Infinity;
- fsyncs the written file;
- re-reads persisted bytes;
- returns SHA256 of the bytes actually persisted.

## Independent red-team repair round

The independent audit of candidate
`82fa21da32d258fdeaea2ec35b187a91f5cdd3a4` returned:

`B. HARNESS_V1_REPAIR_REQUIRED`

No real outcomes were opened during that review.

The repair round targets the confirmed findings:

- hidden tracked modifications through `skip-worktree` /
  `assume-unchanged`;
- runtime checksum self-attestation not bound to Git-frozen evidence;
- proof object exposing the full dataset root;
- lossy/ambiguous no-lookahead timestamp coercion;
- helper-level post-hoc gate/support subset footguns;
- runtime/frozen snapshot identity inconsistencies;
- provenance missing selected partition/gate evidence;
- persisted-artifact hashing based only on in-memory encoded bytes.

These repairs are implementation work, not market evidence.

## Adversarial synthetic coverage

The synthetic suite must cover at least:

- relaxed discovery authorization attempts;
- validation/confirmatory stage attempts;
- 2025+ outcome-window reach;
- mutable/invalid allowed years;
- hidden tracked modifications via `skip-worktree`;
- hidden tracked modifications via `assume-unchanged`;
- dirty worktree after a freeze proof was minted;
- runtime JSON + parquet co-update against a frozen Git checksum ledger;
- frozen/runtime snapshot identity disagreement;
- physical 2025 partitions excluded from the authorized proof;
- selected symlink partitions;
- partition mutation after authorization;
- floats, seconds, strings, bools, empty inputs, and future no-lookahead inputs;
- unequal paired support;
- unequal weighted support;
- helper-level subset arguments no longer accepted;
- NaN-like support keys;
- non-positive weights;
- missing/None/integer promotion gates;
- lookalike proof objects;
- provenance partition/gate evidence;
- attempted result overwrite;
- non-finite result JSON.

No test in this unit may inspect real market outcomes.

## Required usage for Batch02

Every new Batch02 experiment must:

1. verify an exact Git freeze before outcome access;
2. obtain dataset authorization through that freeze;
3. use only paths carried by the resulting authorized proof;
4. check every outcome window;
5. check feature availability at every decision boundary;
6. use exact same-support primitives for relevant comparators;
7. define promotion gates in frozen pre-outcome code/preregistration;
8. emit machine-readable gate values;
9. build provenance before interpreting outcomes;
10. persist provenance/results through non-overwriting evidence paths;
11. add hypothesis-specific adversarial tests;
12. pass independent review before first real outcome access.

## Mandatory independent review gate

For Harness changes and every new Batch02+ hypothesis implementation, the
canonical sequence is:

1. implementation/self-red-team;
2. CI green on the exact candidate SHA;
3. CodeRabbit review on the exact candidate SHA;
4. independent adversarial LLM review on the exact candidate SHA;
5. final adjudication;
6. freeze;
7. merge;
8. only then authorize the next research stage.

All independent reviewers must review the same exact SHA.

Any repair commit resets the gate:

- old CI does not count;
- old CodeRabbit review does not count;
- old adversarial review does not count;
- the repaired descendant must pass the complete gate again.

Minimum acceptance condition:

`CI_GREEN && CODERABBIT_REVIEWED && ADVERSARIAL_LLM_REVIEWED && FINDINGS_ADJUDICATED`

## Explicit residual boundary

This harness is an integrity library plus a mandatory research process. It is
not a hostile-code sandbox.

It does not mechanically prevent a deliberately malicious researcher from:

- importing private module globals and forging Python objects;
- mutating objects with reflection;
- bypassing the harness and opening arbitrary filesystem paths;
- loading arbitrary external/ignored code after a clean tracked-code check;
- deciding a research rule after outcomes and then lying about when it was
  decided.

Those actions are non-compliant and are addressed by frozen code,
preregistration, exact-SHA review, provenance, and independent audit.

The merge criterion is therefore not "impossible to bypass inside hostile
Python." The criterion is that the documented mechanical guarantees are true,
common accidental/self-deceptive bypasses fail closed, and remaining
process/security limits are explicit rather than falsely advertised.

## Non-goals

This unit does not:

- rerun or modify H01-H05;
- open 2025 validation;
- open 2026 OOS;
- create H06;
- design Batch02 hypotheses;
- set statistical promotion thresholds;
- turn Python into a security boundary.

## Acceptance boundary

Until the repaired exact SHA passes the complete independent-review gate:

```text
V2_RESEARCH_HARNESS_V1 = IMPLEMENTATION_CANDIDATE
BATCH02 = NOT_STARTED
REAL_OUTCOMES_OPENED_BY_HARNESS_UNIT = NO
```
