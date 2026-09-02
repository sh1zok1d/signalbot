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
- a successful future Batch02 execution may not be reported complete until the
  exact persisted result bytes have been durably archived and independently
  read back with the same SHA256 and byte count.

Copying a result to another path inside the same Cursor/VM is not durable
enough. V1 uses a remote Git evidence backend bound to the execution
repository's configured `origin` (normally GitHub). Tests use a temporary
local bare Git remote.

## 2. Forward-only scope

Existing consumed B2-01/B2-02 machinery remains historical evidence.

- `prepare_batch02_run()` remains the historical B2-01/B2-02 outcome gate and
  is rejected for numbered B2-03+ hypothesis IDs.
- `persist_batch02_result()` semantics are unchanged for already-consumed
  hypotheses.
- B2-02 remains `POST_RUN_EVIDENCE_RETENTION_GAP`.
- The new ceremony is required for `B2-03+`.

## 3. Lifecycle

Canonical B2-03+ order:

1. verify exact Git code freeze (`verify_batch02_code`)
2. establish durable evidence reservation remotely
   (`prepare_batch02_evidence_reservation`)
3. verify that reservation by independent remote readback
4. only then authorize real dataset/outcome access
   (`prepare_batch02_retained_run`)
5. compute result
6. persist canonical local result exactly once (`persist_batch02_result`)
7. archive exact persisted bytes to the reserved remote evidence location
   (`archive_batch02_result`)
8. remote readback
9. verify SHA256 and byte count
10. produce durable archive receipt
11. only then report successful completed execution

Step 4 is impossible to implement legitimately before a successful step 3:
`prepare_batch02_retained_run` requires a minted reservation token whose
backend state is created only after remote push and independent
readback. `prepare_batch02_run` refuses B2-03+.

Incorrect order such as "prepare run, load real dataset, then check evidence
storage" is not a supported B2-03+ path.

## 4. Pre-outcome remote reservation

The reservation contains no market outcomes. It binds, where available
pre-outcome:

- `hypothesis_id`
- `stage`
- `code_sha` / `code_tree`
- `dataset_id` / `snapshot_id`
- development window and allowed years
- required gate names and gate-contract digest
- seeds
- sanitized repository identity

Payload serialization is canonical JSON. The reservation identity is the
SHA256 of those exact bytes.

Remote ref namespace:

`refs/heads/research-evidence/batch02/<hypothesis_id>/<code_sha>`

Force pushes are forbidden. An existing reservation is accepted only after
exact byte identity verification. An incompatible existing reservation fails
closed.

The evidence remote is the execution repository's `origin`. Callers cannot
supply an arbitrary remote URL. Credential-bearing HTTPS URLs are rejected.
SSH and credential-helper-backed HTTPS to the canonical repository may be
used. Local bare Git remotes are for tests.

## 5. Exact-byte archival

After `persist_batch02_result` returns, archival reads the persisted file as
bytes. It does not parse-and-reserialize, pretty-print, normalize whitespace,
or change newline convention.

Required equality:

```text
source_sha256 == remote_sha256
source_size_bytes == remote_size_bytes
```

Deterministic append-only path:

`batch02/<hypothesis_id>/<code_sha>/<artifact_sha256>.json`

plus `receipt.json` on the same evidence ref. Path traversal, caller-selected
filesystem destinations, overwrite, and silent replacement are rejected.
Collision with different bytes is a hard failure. Exact same bytes already
present may be accepted only after full identity verification.

## 6. Receipt

The committed receipt contains:

- `schema_version`
- `hypothesis_id`, `stage`
- `code_sha`, `code_tree`
- `run_identity_sha256`
- `dataset_id`, `dataset_snapshot`
- `artifact_sha256`, `artifact_size_bytes`
- `remote_repository_identity`
- `evidence_ref`, `evidence_path`
- `reservation_sha256`

The remote archive commit SHA is returned as verified metadata after
successful push/readback. It is not invented inside the committed receipt.

Receipts, logs, and artifacts must not contain secrets, credentials, or
environment tokens.

## 7. Failure semantics

### A. Pre-outcome retention failure

Examples: missing/invalid remote, credentials/push failure, reservation
readback failure, incompatible existing reservation, dirty/invalid code
freeze, forged or mutated reservation token, credential-bearing URL, path
traversal in hypothesis ID.

Required behavior:

- no market outcome access
- no dataset read
- no development run consumed
- fail closed

### B. Post-outcome archival failure

State: `POST_OUTCOME_RETENTION_FAILURE`

```text
OUTCOME CONSUMED = YES
RERUN AUTHORIZED = NO
LOCAL CANONICAL ARTIFACT MUST BE PRESERVED
OPERATOR RECOVERY REQUIRED
```

The system must not delete the local canonical result, must not rerun
automatically, must not authorize another market run, and must not pretend
the execution never happened. Local evidence lock/reservation state and any
remote reservation ref are preserved. There is no automatic cleanup of failed
post-outcome evidence.

## 8. Execution worktree isolation

Evidence Git operations run in an isolated temporary Git directory. They must
not dirty or rewrite the verified execution worktree. After archival the
execution repository must still satisfy the Git-freeze invariant.

## 9. B2-03 integration prerequisite

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
persist_batch02_result
archive_batch02_result
```

not historical `prepare_batch02_run`.

## 10. Historical compatibility

B2-01 and B2-02 artifacts/statuses are unchanged by this unit. Their old
execution records are not invalidated because they predate V1 retention
hardening.
