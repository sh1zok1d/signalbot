# Generator V0 — resumable Anthropic generator transport (`ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1`)

**Status:** `IMPLEMENTED`, offline only
**Date:** 2026-10-02
**Authority:** owner decision 2026-10-02, after `ladder-40-card` r01 lost its first generator call
**Record:** `GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.json`
**Code:**
- `scripts/research/generator_v0/anthropic_provider.py` (batch path);
- `provider.py` (Caller);
- `ledger.py`;
- `routing.py`;
- `routed_provider.py`;
- `checkpoint.py` (new);
- `runner.py`;
- `__main__.py`.

**Tests:**
- `tests/research/test_generator_v0_anthropic_batch_transport.py`;
- `tests/research/test_generator_v0_ladder_rehearsal.py`, now on the batch route.

```
TRANSPORT_AMENDMENT        = IMPLEMENTED (infrastructure only)
SCIENTIFIC_DESIGN_CHANGED  = false
V02_ROUTES_CHANGED         = false
LLM_CALLS                  = 0
PAID_CALLS                 = 0
LADDER40_V03_R01           = INFRASTRUCTURE_FAILED_FROZEN (see GENERATOR_V0_LADDER40_V03_R01_PAUSE.md)
NEXT_UNIT                  = LADDER40_V03_R02 (needs a fresh owner live authorization)
```

## Why

**What happened in r01.**
- The generator call was one synchronous Messages POST with up to 100000 output tokens and effort high.
- The connection stayed open until the 1800 s client timeout.
- No message id ever reached the journal, so the call could only become `UNCERTAIN`.
- Nothing could poll it, and nothing could prove it was not billed.

**The failure is in the transport, not in that one call.** Any long synchronous generation can end the same way.

## What changes

**The ladder GENERATOR goes through Message Batches.** Each generator round is a one-request Message Batch:
- a short create POST returns the batch id;
- the batch id is journaled before any polling;
- from then on the call is only polled by that id.

**This applies to V03 ladder runs only.**
- `routing.LADDER_ROUTES` equals `routing.ROUTES` except for the GENERATOR endpoint (`ANTHROPIC_MESSAGE_BATCHES`) and its transport.
- `routes_for_contract` selects the ladder routes for `GENERATOR_CONTRACT_V03`.
- A live V03 run on the synchronous route is refused before any call.

**The request is the same.**
- The batch `params` are byte-for-byte the synchronous request without `stream`.
- That means the same model, effort high, `max_tokens` 100000, system prompt, compact wire, `output_config.format` schema and slots.
- A test pins this equality.

### States

| Journal state | Meaning | On resume |
|---|---|---|
| `RESERVED` | bound reserved, nothing sent | dispatched under the same key |
| `DISPATCHED` + recovery intent | `custom_id` and dispatch time journaled in the same commit, before the create POST | the batch is searched in the workspace listing; no POST |
| `BACKGROUND_SUBMITTED` (= `PROVIDER_ACCEPTED`) | the batch id is journaled; an external checkpoint is written before the first poll | polled by the id; no POST |
| same, `provider_status` `in_progress` (= `POLLING`) | each poll is journaled | polled by the id |
| `COMPLETE` | validated message, cost at batch prices | returned from the journal |

The ledger keeps its existing state names. `PROVIDER_ACCEPTED` and `POLLING` are the `BACKGROUND_SUBMITTED` state that OpenAI background Responses already use.

### Failure handling

| Failure | Result |
|---|---|
| process dies after the create POST, before the id is journaled | resume finds the batch by `custom_id` and adopts it (`PROVIDER_JOB_RECOVERED`); never POSTed again |
| create response lost (timeout, 5xx, 529, malformed 200) | the same search runs in the same invocation |
| the search shows no batch carries the `custom_id` | `FAILED_NOT_BILLED` (cost 0, listing evidence journaled); the next transport attempt is a new call key |
| a batch in the dispatch window is still processing | `PENDING`: absence is never concluded while a candidate may be ours |
| create refused: 400 / 401 / 402 / 403 / 404 / 413 | `FAILED_NOT_BILLED`, `PAUSED_PROVIDER_REJECTED` |
| create refused: 429 | `FAILED_NOT_BILLED`, retried (at most 3 new attempts per invocation) |
| poll timeout, connection error or 5xx | keeps polling; at the per-invocation wait limit (6 h) the run is `PAUSED_BACKGROUND_PENDING` with the id kept |
| poll 401 / 402 / 403 / 404 | `PAUSED_BACKGROUND_PENDING` at once; fix the credential or workspace, then resume |
| result `errored` with `rate_limit_error`, `overloaded_error`, `api_error` or `timeout_error`, or `expired` | `FAILED_NOT_BILLED` (the provider does not bill these), retried under a new key |
| result `errored` with any other error type, or `canceled` | `FAILED_NOT_BILLED`, `PAUSED_PROVIDER_REJECTED` |
| result `succeeded` but unusable (`max_tokens`, refusal, malformed) | `FAILED_WITH_COST` at batch usage cost; generator content is not retried (unchanged) |
| result does not hold exactly this `custom_id` | `UNCERTAIN` with the batch id (integrity); never re-POSTed |

**No transport timeout on an accepted batch can produce `UNCERTAIN`.** The provider keeps a batch for 24 h of processing and its results for 29 days, so a resume can always read it.

**How the search works.**
- The `custom_id` is `gv0-` followed by `digest(RUN_ID, CALL_KEY)` truncated to 60 characters.
- It is unique to the run and to the attempt, so another run's batch can never be adopted.
- The search reads the workspace listing, newest first and paginated.
- It considers only one-request batches created within the dispatch time ± 600 s, plus the 120 s create timeout.
- It matches the `custom_id` in the results of ended batches.
- Absence is concluded only after every candidate in that window has ended, and 900 s after the window closed.

### External checkpoints

**Checkpoint stages.** `ledger.checkpoint(stage)` runs at:
- `PROVIDER_ACCEPTED` — after the batch id is journaled, before the first poll;
- `ROUND_COMPLETE` — after each generation round;
- `REVIEW_BLOCK` — every 10 reviewed cards;
- `CAMPAIGN_RESULT`;
- `CAMPAIGN_<status>` — on every stop or pause.

**What a checkpoint writes.**
- A consistent SQLite snapshot (the online backup API, never a raw copy of a live WAL).
- `CHECKPOINT.json`, which names every open provider id and `custom_id` in plain text.

**Targets.**
- `--checkpoint-git-branch <current branch>`: commits only `<run-dir>/checkpoint/{run.sqlite,CHECKPOINT.json}` and pushes the branch. It never force-pushes and retries the push at 2, 4, 8 and 16 s.
- `--checkpoint-dir <durable dir>`.

**A live V03 run or resume refuses to start without one of them.**

**A checkpoint that cannot be made durable stops the run.**
- The status becomes `PAUSED_CHECKPOINT_FAILED`.
- The journal is intact, and a resume polls the accepted ids.

**Critic calls are checkpointed per stage, not per acceptance.**
- 80 background critic acceptances would mean 80 commits of the journal.
- OpenAI background responses are stored server-side by id, and their ids are journaled locally at once.

### Price and budget bound

**Batch prices.** Official pricing on 2026-10-02 for Claude Opus 5.5 at batch rates: input USD 2 and output USD 10 per MTok, half of standard.
- The batch route prices both the reservation bound and the recorded usage at these rates.
- The price table is part of the route's transport, so it is in the routing digest.

**Conservative fallbacks.**
- A usage record whose `service_tier` is not `batch` is priced at standard rates.
- A cost above the bound charges the reservation, as before.

**Bound per generator round.**

| | Reservation |
|---|---|
| Before (synchronous) | USD 2.210772 |
| Now (batch) | about USD 1.1054 |

**Fresh V03 worst case.**

| | Single attempt | With content retries |
|---|---|---|
| Before | USD 30.749115 | USD 61.496292 |
| Now | USD 26.326979 | USD 52.652020 |

The critic bounds are unchanged. The USD 12 cap still needs `--accept-budget-stop`.

## What does not change

**Scientific design:**
- `GENERATOR_CONTRACT_V03`, the slot plan 16/14/7/3 and `LADDER_IDENTITY`;
- prompts, schemas, the compact wire, models and effort;
- the 100000-token cap, critics and routes for every critic;
- the shortlist 2/2/1, `INCOMPLETE_BUDGET_STOP` and the memory finalizer.

**V02 routing is byte-identical:**
- `routing_digest()` = `c636f14a…`;
- the routed identity, DIRECT = `e44543e3…`;
- `first-30-card` keeps the synchronous route.

**r01 cannot be resumed with this code.** Its run config holds the synchronous routing digest, so a resume is refused as a configuration difference. Its only remaining operation is the offline `reconcile`.

## Verified provider facts

From the official docs, read on 2026-10-02:
- Batches accept every Messages API parameter except `stream: true`, `speed` and `max_tokens: 0`, which covers structured outputs, effort and adaptive thinking.
- Every active model is supported.
- Request params are validated asynchronously: an invalid request comes back as an `errored` result.
- `errored`, `canceled` and `expired` results are not billed. Usage reports `service_tier: "batch"`.
- A batch expires after 24 h of processing; results stay available for 29 days.
- `custom_id` matches `^[a-zA-Z0-9_-]{1,64}$`.
- The listing is newest first; `after_id=last_id` gives older pages.

## Acceptance (offline, fake transports and a fake clock, no network)

- **Request:** the batch request equals the synchronous request without `stream`; the bound is half.
- **Full ladder campaign:**
  - 4 batch POSTs; 4, 40, 40, 40 and 1 calls by role; shortlist 2/2/1;
  - batch cost recorded;
  - checkpoints at acceptance, every round, every review block and the result;
  - no thinking text, signature or credential in the journal.
- **Acceptance checkpoint:** written before the first poll, and it names the batch id.
- **Lost acknowledgements:**
  - process death after the create POST: the resume finds the batch, still 4 POSTs;
  - lost create response: recovered in the same invocation;
  - a create that made no batch: `FAILED_NOT_BILLED` after the settle window, then a new attempt;
  - a still-processing candidate: `PENDING`, never absence.
- **Polling:**
  - poll timeouts keep polling;
  - a long batch pauses `PENDING` with its id and the resume polls it;
  - poll 401 / 403 / 404 pause `PENDING` and the resume polls the same batch.
- **Provider outcomes:**
  - `errored` (overloaded) and `expired`: cost 0, retried under a new key;
  - `errored` (invalid) and `canceled`: cost 0, `PAUSED_PROVIDER_REJECTED`;
  - `max_tokens`: billed at batch usage cost, not retried.
- **Checkpoints:**
  - a checkpoint failure gives `PAUSED_CHECKPOINT_FAILED`, then the resume polls without a POST;
  - the git checkpointer commits only its two files, pushes the current branch, and fails closed on push failure or the wrong branch.
- **Guards:**
  - a live V03 run on the synchronous route is refused;
  - a `DISPATCHED` row without a recovery intent still needs reconciliation;
  - the CLI refuses a live ladder run without a checkpoint target;
  - bad checkpoint targets (the run directory itself, two targets, a branch that is not checked out) fail before a run exists;
  - the frozen r01 journal snapshot is refused on resume (configuration differs), and its row stays `UNCERTAIN` with the USD 2.210772 reservation.
- **Rehearsal:** the full run, budget stop then resume, and throttling then resume, all on the batch route.

## Known limits

- **Workspace.** Recovery by listing needs the same workspace as the create, which means the same Anthropic key or workspace on resume.
- **Settle time.** A create with no batch is resolved about 27 minutes after dispatch: the 600 s skew plus the 120 s create timeout, plus the 900 s settle time.
- **Expiry.** A batch can take up to 24 h. After the per-invocation wait (6 h), the run is `PAUSED_BACKGROUND_PENDING` and the operator resumes. An expired request is not billed and is retried.
- **Checkpoint branch.** The checkpoint branch must not receive other pushes during a run. A rejected (non-fast-forward) push stops the run at `PAUSED_CHECKPOINT_FAILED`; the operator brings the branch in line, then resumes.
- **Repository size.** Git checkpoints add one journal snapshot per stage: about 20 commits of 0.2 to 2 MB each for a full campaign.

## r02 (not started; needs a fresh owner live authorization)

```
python -m scripts.research.generator_v0 ladder-40-card --allow-real-llm --budget-usd 12 \
  --accept-budget-stop --actor owner --reason "<why>" \
  [--openai-network-mode DIRECT] \
  --checkpoint-git-branch <current branch>   # or --checkpoint-dir <durable dir>
  --run-dir artifacts/generator_v0/ladder-40-card-v03-r02
```

The run directory is git-ignored. The checkpointer force-adds only `<run-dir>/checkpoint/run.sqlite` and `CHECKPOINT.json`; the live journal and its WAL are never committed.

**Design is identical to r01:**
- 40 slots, 16/14/7/3;
- the same prompts, models, critics and routes for every critic;
- shortlist 2/2/1;
- cap USD 12 with `--accept-budget-stop`.

**Resume** uses `resume --provider routed --contract V03` with the same flags and a fresh `--accept-budget-stop`.
