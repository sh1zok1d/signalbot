# Batch02 Durable Evidence Retention V1

```text
STATUS = IMPLEMENTED_PENDING_INDEPENDENT_REVIEW
SCOPE = B2-03+
OUTCOME_BLIND = YES
REAL_DATA_ACCESSED = NO
2025 = UNTOUCHED
2026 = UNTOUCHED
```

This is an outcome-blind research-infrastructure contract. It does not test
B2-03 or any other market hypothesis. It does not rerun B2-01 or B2-02. It
does not change the B2-02 market verdict.

## 1. Incident being prevented

B2-02 completed exactly once and produced `B2_02_CLOSED_NO_PROMOTION`. The
canonical result bytes were persisted inside an ephemeral execution
environment and then lost when that environment disappeared, before a durable
external copy was verified. That is recorded as
`POST_RUN_EVIDENCE_RETENTION_GAP`. It is not a rerun authorization and not a
`RUN_INTEGRITY_FAILURE`.

Engineering requirement:

- future Batch02 real-outcome access is blocked unless a durable external
  evidence destination has already been proven writable;
- the one-shot authorization is durably claimed on that remote **before**
  dataset access, so loss of the execution VM cannot reopen the run;
- a successful future Batch02 execution may not be reported complete until the
  exact persisted result bytes have been durably archived and independently
  read back with the same SHA256 and byte count.

Copying a result to another path inside the same Cursor/VM is not durable
enough. V1 production transport is the canonical external repository
`github.com/sh1zok1d/signalbot` through an accepted SSH or HTTPS form.
Local bare Git remotes exist only through a private test seam that is not
re-exported from `batch02_contracts`.

## 2. Forward-only scope

Existing consumed B2-01/B2-02 machinery remains historical evidence.

- `prepare_batch02_run()` remains the historical B2-01/B2-02 outcome gate and
  is rejected for numbered B2-03+ hypothesis IDs. Numbered B2 IDs are
  classified case-insensitively (`b2-03`, `b2_03`, `B2-03`, `B2_04_X`
  all require durable retention). Noncanonical casing must never reach
  historical B2-01/B2-02 machinery.
- One-shot uniqueness for numbered B2-03+ is bound to a canonical slot
  key (`B2-03`, `B2-04`, ...), not the raw caller spelling. `B2-03_X`,
  `b2-03_X`, `B2_03_X`, and equivalent zero-padding share
  `refs/heads/research-evidence/batch02/B2-03/<code_sha>`. Distinct
  numbers remain distinct slots. The exact `hypothesis_id` is still
  recorded in reservation/run provenance; an incompatible exact ID on
  an existing slot fails closed and is not overwritten.
- `persist_batch02_result()` semantics are unchanged for already-consumed
  hypotheses.
- B2-02 remains `POST_RUN_EVIDENCE_RETENTION_GAP`.
- The new ceremony is required for `B2-03+`.

## 3. Lifecycle

Canonical B2-03+ order:

```text
verify_batch02_code
prepare_batch02_evidence_reservation
prepare_batch02_retained_run   # durable outcome-access claim, then authorize
persist_batch02_retained_result
archive_batch02_result         # consumes the minted persist proof
```

Remote evidence refs follow an append-only state machine. Only fast-forward
transitions are allowed. Force push is forbidden. Unknown files/state fail
closed. Earlier evidence is never overwritten.

```text
Commit 1:
  reservation.json
  STATE = RESERVED
  remote reservation proves storage readiness

Commit 2:
  reservation.json
  outcome_claim.json
  STATE = OUTCOME_ACCESS_CLAIMED
  remote outcome-access claim durably consumes/claims the one-shot
  authorization before dataset access

Commit 3:
  reservation.json
  outcome_claim.json
  batch02/<hypothesis>/<code>/<digest>.json
  receipt.json
  STATE = ARCHIVED
  remote archive proves preservation of exact result bytes
```

Required meaning of the three remote proofs:

- remote reservation proves storage readiness;
- remote outcome-access claim durably consumes/claims the one-shot
  authorization before dataset access;
- remote archive proves preservation of exact result bytes.

`prepare_batch02_run` refuses B2-03+. Incorrect order such as "prepare run,
load real dataset, then check evidence storage" is not a supported B2-03+
path.

## 4. One-shot claim rule

`RESERVED` is the only state eligible for a new outcome-access claim.

Once the remote ref has advanced beyond a pristine `RESERVED` tree:

- `OUTCOME_ACCESS_CLAIMED` -> no new reservation / no new run
- `ARCHIVED` -> no new reservation / no new run

Syntactic aliases of the same numbered B2 slot cannot open a second
ref. Changing `B2` casing, `-` vs `_` after `B2`, or equivalent
zero-padding is not a new one-shot authorization.

A successful archived run cannot be replayed from a fresh clone. A
post-outcome archive failure also remains permanently blocked from an
automatic rerun because the remote `OUTCOME_ACCESS_CLAIMED` record survives
loss of the execution VM.

Existing-ref inspection is fail-closed. A pristine reusable reservation must
contain only `reservation.json` with the exact allowed pre-outcome bytes. If
the ref contains a claim, receipt, result artifact, archived state, or any
unknown extra evidence, it is not a fresh reservation. The implementation
does not delete or reset it.

The claim transition:

1. starts from the exact verified reservation head;
2. adds `outcome_claim.json` with no market outcomes;
3. fast-forwards the evidence ref;
4. pushes normally, with no force;
5. independently fetches and reads back the claim;
6. verifies exact claim bytes/digest and expected parent;
7. only then permits `authorize_dataset_access`.

The claim binds `schema_version`, `kind = batch02_outcome_access_claim`,
`reservation_sha256`, `hypothesis_id`, `stage`, `code_sha`, `code_tree`,
`dataset_id`, `snapshot_id`, development window, `gate_contract_sha256`,
`seeds`, `remote_repository_identity`, and `reservation_commit_sha`. It
contains no market values.

If the claim push times out, errors after the remote mutation was
attempted, or independent readback cannot be proven, dataset
authorization is blocked. The claim is not reset or deleted. The
explicit fail-closed state is `AMBIGUOUS_OUTCOME_ACCESS_CLAIM`.
Operator adjudication is required. Scientific safety is more important
than preserving an unused run slot.

## 5. Production transport

The public B2-03+ production API inspects the actual fetch URL(s) and push
URL(s) before any outcome access. Production requires exactly the canonical
repository `github.com/sh1zok1d/signalbot` through SSH or credential-helper
HTTPS. Evidence fetch/push uses that verified endpoint, not the mutable
`origin` remote name.

Production rejects:

- local/filesystem Git remotes;
- credential-bearing URL forms (redacted in errors);
- multiple or divergent push URLs;
- `insteadOf` / `pushInsteadOf` rewrite configuration that can redirect the
  evidence transport.

There is no public `allow_local_remote=True` escape hatch and no
caller-controlled environment variable that weakens production durability.
Local bare remotes are available only through
`prepare_test_evidence_reservation()`, which is not re-exported from
`batch02_contracts`, is not callable by hypothesis runners, and is not a
normal caller argument on the production API.

Isolated evidence Git commands ignore system/global Git config so those
rewrites cannot affect the commands used. Local rewrite configuration in the
execution repository is still inspected and rejected.

The isolated Git environment also removes inherited SSH-transport
overrides (`GIT_SSH`, `GIT_SSH_COMMAND`, `GIT_SSH_VARIANT`). There is no
public escape hatch that restores them. Credential helpers and an SSH
agent socket may remain usable; the caller cannot replace the SSH
executable or command.

Every evidence Git subprocess is bounded by `GIT_TIMEOUT_SECONDS` (60).
No `ls-remote`, fetch, push, remote inspection, or readback may hang
indefinitely. `subprocess.TimeoutExpired` becomes `GitTimeoutError` and
is classified by lifecycle stage.

## 6. Exact-byte archival

`archive_batch02_result()` consumes a `PersistedBatch02ResultProof` minted
only by `persist_batch02_retained_result()`. It does not accept a caller-
supplied artifact digest.

The minted persist proof binds the canonical result path, artifact SHA256,
artifact size, `run_identity_sha256`, `hypothesis_id`, code SHA/tree, and
the remote outcome-claim identity. It is non-forgeable under the same trust
model as the other minted authority objects.

Archival reads the persisted file as bytes. It does not parse-and-reserialize,
pretty-print, normalize whitespace, or change newline convention.

Required equality:

```text
source_sha256 == remote_sha256
source_size_bytes == remote_size_bytes
```

The archive commit must be a direct fast-forward child of the exact remote
claim head that authorized outcome access, not merely any descendant of the
original reservation. Reservation-head drift, claim-head drift, an alternate
claim, or an unknown intermediate commit fail closed as post-outcome.

Deterministic append-only path, keyed by the canonical B2 slot:

`batch02/<B2-NN>/<code_sha>/<artifact_sha256>.json`

plus `receipt.json` on the same evidence ref. Path traversal, caller-selected
filesystem destinations, overwrite, and silent replacement are rejected.

GitHub regular Git storage rejects a single object above 100 MiB. Artifacts
whose exact byte count is `<= SAFE_SINGLE_BLOB_THRESHOLD_BYTES` (90 MiB)
keep the V1 single-file path above. Artifacts above that safe threshold are
archived as raw byte chunks of `RAW_CHUNK_SIZE_BYTES` (64 MiB) with no
reserialization:

```text
batch02/<B2-NN>/<code_sha>/<artifact_sha256>/manifest.json
batch02/<B2-NN>/<code_sha>/<artifact_sha256>/chunks/00000.part
batch02/<B2-NN>/<code_sha>/<artifact_sha256>/chunks/00001.part
...
```

The remote artifact is valid only after independent readback reconstructs
the original bytes by concatenating chunks in numeric ascending order and
proving `reconstructed_sha256` and `reconstructed_size` equal the local
canonical digest and byte count. This is not a second scientific execution
and does not rewrite reservation or claim bytes.

## 7. Receipt

The committed receipt contains:

- `schema_version`
- `hypothesis_id`, `stage`
- `code_sha`, `code_tree`
- `run_identity_sha256`
- `dataset_id`, `dataset_snapshot`
- `artifact_sha256`, `artifact_size_bytes`
- `remote_repository_identity`
- `evidence_ref`, `evidence_path`
- `reservation_sha256`, `claim_sha256`

The remote archive commit SHA is returned as verified metadata after
successful push/readback. It is not invented inside the committed receipt.

Chunked archives additionally record, in the same committed receipt:

- `archive_representation = raw_chunks`
- `manifest_path`, `manifest_sha256`
- `chunk_count`, `chunk_size_bytes`
- `execution_code_sha`, `execution_code_tree`
- `recovery_code_sha`, `recovery_code_tree`
- `reservation_commit_sha`, `claim_commit_sha`
- `recovery_tool`

First-run archival on the execution commit may honestly set
`recovery_code_sha == execution_code_sha`. Post-outcome crash recovery must
not relabel a later infrastructure commit as the scientific execution SHA.
Execution identity remains the historical commit/tree that produced the
artifact. Recovery identity is the clean checkout that performs retention.

Receipts, logs, and artifacts must not contain secrets, credentials, or
environment tokens.

## 7.1 Fresh-process post-outcome recovery

`archive_batch02_result()` requires minted in-memory reservation/claim/persist
objects from the original scientific process. Those objects die with the
process. `recover_claimed_batch02_artifact()` is the dedicated operator
entry point after process loss.

It is callable from a completely fresh Python process. It does not require
the original `DurableEvidenceReservation`, `DurableOutcomeAccessClaim`,
`PersistedBatch02ResultProof`, or `_EvidenceBackend` objects. It reconstructs
and verifies authority from durable facts. It does not remint a reservation
or push a new claim.

Caller kwargs may only identify the recovery checkout and the tracked
authority path. They may not independently supply artifact digest, size,
run identity, claim SHA, or other scientific identity fields.

Those fields come from a tracked recovery-authority JSON blob that belongs
to the exact clean `recovery_code_sha` / `recovery_code_tree`. The authority
is read as the exact Git blob from that commit. It binds at least:

```text
hypothesis_id
stage
dataset_id
snapshot_id
execution_code_sha
execution_code_tree
evidence_ref
reservation_commit_sha
claim_commit_sha
artifact_sha256
artifact_size_bytes
run_identity_sha256
canonical_artifact_path
historical_artifact_binding
```

`historical_artifact_binding` is required. Omitting it fails closed. The
only accepted value in this contract is `OPERATOR_ADJUDICATED`.
`PREEXISTING_IMMUTABLE_WITNESS` and any stronger historical-origin claim
fail closed because this mechanism does not verify a pre-existing
immutable witness of the artifact digest.

These two statements are not equivalent:

```text
artifact == authority committed during recovery
authority describes the exact artifact originally persisted by the
historical scientific execution
```

Recovery proves only the first. A later clean recovery commit can carry a
newly computed digest for a provenance-preserving mutation of the surviving
local payload. That is operator adjudication of current bytes, not
cryptographic historical persistence. The recovery receipt therefore records:

```text
historical_artifact_binding = OPERATOR_ADJUDICATED
historical_artifact_byte_authority = OPERATOR_ADJUDICATED
recovery_proves = artifact_equals_authority_committed_during_recovery
historical_execution_persistence_proven = false
```

Search of committed Git history, committed research/status ledgers, and
committed durable-failure metadata found no immutable source that binds the
local B2-05 artifact digest
`530342759e70a135915ef82382b4b97bd939620ce02925524b745ccf6cc9a57c`.
Uncommitted local sidecars are not Git-immutable evidence. Any future
B2-05 recovery authority for those bytes can therefore only be
`OPERATOR_ADJUDICATED`. This document is not that authority file.

Dual verification:

- historical execution identity is proven from Git objects
  (`commit exists`, SHA match, tree match) without checking out or freezing
  the current worktree to the execution SHA;
- the current recovery checkout must be a clean freeze of
  `recovery_code_sha` / `recovery_code_tree`.

Before the local artifact is read, recovery independently fetches the
evidence ref and requires `OUTCOME_ACCESS_CLAIMED`, exact expected claim
SHA, claim parent = expected reservation SHA, tree exactly
`reservation.json` + `outcome_claim.json`, and reservation/claim identity
fields that match the tracked authority. Any mismatch fails closed with
no push.

The local artifact must then be the authority's canonical path, a regular
non-symlink file whose size and SHA256 equal the authority values. Those
exact raw bytes are later chunked. JSON is parsed only to verify
`artifact["provenance"]` against `build_run_identity` semantics:

```text
sha256(canonical_json(provenance)) == authority.run_identity_sha256
```

Provenance scientific identity must agree with the authority and with the
remote reservation/claim. Reservation/claim payloads are then rebuilt from
provenance plus authority and compared byte-for-byte to the remote blobs.
The artifact is not rewritten or reserialized. Artifacts `<= 90 MiB` keep
the V1 single-blob archive. Larger artifacts use `raw_chunks` / 64 MiB.

The archive commit must be exactly one child of the expected claim SHA.
Immediately before push, remote HEAD must still equal that claim SHA.
Push is ordinary fast-forward only. Force, force-with-lease, ref reset,
and delete+recreate are forbidden.

Independent readback after push requires parent = claim SHA, unchanged
reservation/claim bytes, exact receipt/manifest/chunk paths, exact chunk
SHA256/size, no missing/extra chunks, numeric order, and
`sha256(b"".join(chunks_in_numeric_order))` equal to the expected artifact
digest and size. Only then is the remote state `ARCHIVED`.

## 8. Failure semantics

### A. Pre-outcome retention failure

Examples: missing/invalid remote, credentials/push failure, reservation
readback failure, incompatible or already-claimed existing reservation,
dirty/invalid code freeze, forged or mutated reservation token,
credential-bearing URL, path traversal in hypothesis ID, local production
remote, pushurl/rewrite redirect, Git timeout before any remote claim
mutation, ambiguous claim readback.

Required behavior:

- no market outcome access
- no dataset read
- no development run consumed, except that an already-pushed claim remains
  as durable proof that the slot was used
- fail closed

### B. Post-outcome archival failure

Once the canonical local result has been persisted, every later failure is
`POST_OUTCOME_RETENTION_FAILURE`, including archive-time freeze drift,
reservation/claim authority failure, remote drift, Git timeout during
archival, push/readback failure, and digest mismatch. The extra local
durable-retention lock is a fail-closed concurrent-archive guard, not a
durability substitute.

```text
OUTCOME CONSUMED = YES
RERUN AUTHORIZED = NO
LOCAL CANONICAL ARTIFACT MUST BE PRESERVED
OPERATOR RECOVERY REQUIRED
```

The system must not delete the local canonical result, must not rerun
automatically, must not authorize another market run, and must not pretend
the execution never happened. Local evidence lock/reservation state and any
remote reservation/claim ref are preserved. There is no automatic cleanup of
failed post-outcome evidence.

## 9. Execution worktree isolation

Evidence Git operations run in an isolated temporary Git directory. They must
not dirty or rewrite the verified execution worktree. After archival the
execution repository must still satisfy the Git-freeze invariant.

## 10. B2-03 integration prerequisite

This document does not preregister or implement B2-03.

B2-03 development outcome access remains blocked until:

1. this unit receives independent review;
2. exact-SHA CI is green;
3. this unit is merged;
4. the future B2-03 runner is reviewed for correct integration with this
   contract.

The future runner must use:

```text
verify_batch02_code
prepare_batch02_evidence_reservation
prepare_batch02_retained_run
load_authorized_parquet_table
persist_batch02_retained_result
archive_batch02_result
```

not historical `prepare_batch02_run` or historical `persist_batch02_result`.
`archive_batch02_result` must consume the persisted-result authority returned
from `persist_batch02_retained_result`.

## 11. Historical compatibility

B2-01 and B2-02 artifacts/statuses are unchanged by this unit. Their old
execution records are not invalidated because they predate V1 retention
hardening.
