# Signalbot — Agent Runtime Protocol

**Status:** `OPERATIONS / ACTIVE`  
**Date:** 2026-09-24

This file is the canonical runtime protocol for Signalbot coding/review agents that perform Generator V0 live-provider, smoke, calibration, or paid-LLM work. It does not override frozen scientific contracts or protected-data rules.

## 1. Task-scoped authorization

A paid call requires explicit authorization in the current task, including an absolute budget and allowed roles/call count. Do not infer live-call authorization from history.

For an explicitly authorized Generator V0 operational task, older repository notes such as `NO_PAID_LLM_CALL`, `INFRASTRUCTURE_ONLY`, or `READY_FOR_*_REVIEW` may be historical/stale. Record the discrepancy, but do not repeatedly stop on the same stale operational note when the current owner instruction is explicit.

This does **not** authorize protected data, scientific interpretation, or changes to frozen experiment contracts.

## 2. Verify the checkout

Before a live task confirm:
- repository: `sh1zok1d/signalbot`;
- requested branch/PR exists;
- requested HEAD matches;
- requested TREE matches when supplied.

Never spend against an unverified checkout.

## 3. Cloud VMs are ephemeral

Assume every fresh cloud-agent VM loses:
- `/tmp` and scratch files;
- prior journals and generated cards;
- proxy ports;
- local worktrees;
- uncommitted drivers.

If a later step depends on a paid artifact, either complete the dependent work in the same VM or persist an explicitly allowed durable artifact before ending. Never tell a later agent to recover authoritative state from another VM's `/tmp`.

## 4. Secrets

Never print, echo, log, commit, or report credentials.

Anthropic may be supplied as `SIGNALBOT_ANTHROPIC_API_KEY`. A subprocess mapping to `ANTHROPIC_API_KEY` may be used only when required and must not be persisted.

In the cloud-agent environment, OpenAI provider authentication is supplied by the sandbox proxy. A real `OPENAI_API_KEY` is not expected to be present.

## 5. Verified cloud OpenAI network binding

Verified 2026-09-24:
- direct `HTTPSConnection("api.openai.com")` is blocked by sandbox egress with HTTP 403;
- `HTTPS_PROXY` is present and its port may change between VM/session restarts;
- `GET /v1/models` through the proxy with no Authorization header returned HTTP 200 and exposed `gpt-6-sol` and `gpt-6-luna`;
- the reviewed cloud adapter strips only `Authorization` at the sandbox-proxy boundary and preserves method, path, body bytes, and all other provider-generated headers;
- the sandbox proxy supplies OpenAI authentication.

For cloud-agent OpenAI calls:
- the canonical runner sets `OPENAI_NETWORK_MODE = CLOUD_PROXY` explicitly (`first-30-card`, or `--provider routed --openai-network-mode CLOUD_PROXY`);
- do not infer cloud mode from `HTTPS_PROXY`;
- read `HTTPS_PROXY` dynamically on every call;
- never hardcode proxy host/port;
- use `scripts/research/generator_v0/cloud_openai_transport.py:CloudProxyOpenAITransport` via `OpenAIProvider(..., transport=..., network_mode='CLOUD_PROXY')`;
- never use the default direct socket in this environment;
- never search for or inject a real OpenAI API key;
- a missing Anthropic credential (`SIGNALBOT_ANTHROPIC_API_KEY` or `ANTHROPIC_API_KEY`) fails closed;
- production `OpenAIProvider` remains authoritative for request bytes, model, reasoning effort, schemas, background semantics, parsing and accounting;
- `Caller` / `Ledger` remain authoritative for identity, exactly-once state, provenance and budget.

The cloud adapter is an environment transport boundary, not scientific logic.

For Cursor/local routed runs with direct provider credentials, `ladder-40-card` may be invoked with explicit `--openai-network-mode DIRECT`. DIRECT requires `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`; it is never inferred from proxy variables. Omitting the flag on `ladder-40-card` preserves the `CLOUD_PROXY` default, and `first-30-card` remains forced to `CLOUD_PROXY`. The chosen mode is part of transport/run identity, so resume under a different mode is rejected.

## 6. Current routed architecture authority

For routed runs, `scripts/research/generator_v0/routing.py` is authoritative.

First 30-card architecture freeze:
- GENERATOR → Anthropic `claude-opus-5-5`, effort high, 10 cards per round, max output 100000;
- NOVELTY_CRITIC → OpenAI `gpt-6-sol`, high, background Responses;
- FEASIBILITY_CRITIC → OpenAI `gpt-6-luna`, low, synchronous Chat Completions;
- RED_TEAM → OpenAI `gpt-6-sol`, high, background Responses;
- SELECTOR → deterministic application logic; `SELECTOR_LLM_CALLS = 0` on the first 30-card run (`NOT_CALLED`);
- GENERATOR → `GENERATOR_CONTENT_ATTEMPTS = 1`, so a 30-card run has `MAX_GENERATOR_POSTS = 3`.

See `docs/research/GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.md`.

## 7. Background Responses exactly-once rule

For background roles:
1. persist DISPATCHED before the create POST;
2. create exactly once;
3. persist a usable `response_id` immediately;
4. after `response_id`, use GET polling only;
5. ambiguous create failure → `UNCERTAIN`, no replay;
6. polling failure after `response_id` preserves resumable GET-only state;
7. best-effort DELETE after local persistence must not change logical completion.

No custom retry loops.

## 8. Scratch orchestration

A narrow smoke/calibration may use a scratch-only driver when explicitly authorized, but it must reuse production:
- `Contexts`;
- `routing.ROUTES`;
- `Ledger`;
- `Caller`;
- `RoutedProvider`;
- `AnthropicProvider`;
- `OpenAIProvider`;
- `Roles`;
- production schemas/intake;
- deterministic selector.

Do not reimplement scientific validation, routing, pricing, retries, identity, or normalization. Do not hand-build model payloads.

## 9. Mock rehearsal before new live orchestration

A new orchestration path must first pass a zero-cost fake/mock rehearsal covering:
- call counts;
- budget reservations;
- candidate flow;
- critic ordering;
- stop conditions;
- resume behavior where relevant.

Do not change the rehearsed orchestration between rehearsal and live execution except credential/network binding.

## 10. Budget

Every live task must define `ABSOLUTE_CAP_MICRO_USD`.

Before the first paid POST, compute the conservative reservation for the complete required task when the task says the full plan must fit. Historical charges/reservations belong to the same cap when the task says they are the same lineage.

Never interpret an absolute cap as an additional allowance.

## 11. Failure semantics

Use production classifications:
- `COMPLETE`: safely persisted usable result;
- `FAILED_WITH_COST` / billed: charge known usage or conservative bound;
- `UNCERTAIN`: billing/outcome ambiguous; preserve reservation, no replay;
- `NOT_BILLED`: only when provider/environment semantics establish that safely.

Do not turn ambiguous 5xx responses into NOT_BILLED.

## 12. Provenance

- `raw_sha256` = SHA256 of usable verbatim model text;
- `wire_sha256` = SHA256 of provider response envelope;
- if no usable model text exists, `raw_sha256` is null/absent;
- hidden reasoning/thinking content must not be persisted; token counts may be.

## 13. Protected data and scientific boundary

Infrastructure smoke/calibration:
- `NO_SCIENTIFIC_STATUS = true`;
- protected 2025/2026 stays unopened unless the current task explicitly authorizes otherwise;
- generated calibration cards and critic judgments are not evidence of profitability or a validated edge.

Do not use sealed historical runs as convenient fixtures. For transport-only tests, prefer canonical synthetic fixtures in `scripts/research/generator_v0/mock.py`.

## 14. Artifact survival

If paid output is required later, do not end with its only authoritative copy in an ephemeral location. Persist only what the task permits. Sanitized durable evidence may include IDs, hashes, usage, cost, logical state and validation status.

## 15. Known verified runtime facts

Do not rediscover these with paid calls:
- Anthropic compact generator schema works;
- Anthropic generator max output 100000 works;
- Opus generator works live;
- Luna feasibility works live;
- Sol novelty background Responses works live;
- Sol red-team background Responses works live;
- cloud OpenAI requires the sandbox proxy;
- the proxy port is ephemeral;
- direct OpenAI is blocked in the cloud-agent environment;
- background schema/application validation and exactly-once resume paths are covered by tests.

Recheck current VM connectivity only when necessary, preferably with a non-inference endpoint.

## 16. Pre-live report

Before live execution report:
- repository / HEAD / TREE;
- purpose;
- live-call authorization;
- absolute cap;
- planned paid POST count;
- role → provider → model → effort;
- cloud OpenAI proxy mode;
- Anthropic credential presence;
- protected/sealed-run status;
- total planned reservation.

## 17. Post-live report

For every attempted paid call record:
- role/provider/model;
- call key / response id;
- logical state / HTTP status;
- input/output/reasoning/cache tokens;
- reservation / actual accounting cost;
- raw/wire hashes.

Then report total paid POSTs, actual cost, charged-or-reserved cost, cap, unresolved/uncertain count, secret scan, protected-data state, sealed-run state and repository modification state.

## 18. Memory finalization after a campaign

A completed campaign is ingested into mechanism memory only by the offline
finalizer (`docs/research/GENERATOR_V0_MEMORY_FINALIZER.md`):

```bash
python -m scripts.research.generator_v0.finalize_memory --dry-run --campaign-id <ID> --run-journal <run.sqlite>
python -m scripts.research.generator_v0.finalize_memory --apply   --campaign-id <ID> --run-journal <run.sqlite>
python -m scripts.research.generator_v0.finalize_memory --verify
```

- Run it in the same VM as the campaign, because the journal is ephemeral (§3), then commit the whole `docs/research/generator_v0_memory/` chain together with the regenerated mirrors and pins.
- It makes no provider calls. It never edits the frozen design, and no LLM decides what is written.
- Re-running a finalized campaign with the same source is a no-op. A different source under the same campaign ID is a hard failure.
- The event chain is the historical authority. Mirrors and `GENERATOR_V0_CONTEXT_PINS.json` are derived caches; never hand-edit them.

## 19. First 30-card run boundary

After the architecture freeze, do not add more precautionary smoke/calibration cycles. The next paid action after operational persistence/review is the first 30-card run. Only a concrete defect observed in execution justifies reopening the frozen transport/routing design.

V03 ladder runs (`ladder-40-card`, `GENERATOR_CONTRACT_V03`) use `routing.LADDER_ROUTES`. They are the routes above except one: the GENERATOR is sent as a one-request Anthropic Message Batch (`ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1`, `docs/research/GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.md`).
- After acceptance the batch is only polled by its journaled id, never POSTed again.
- A poll failure leaves the run `PAUSED_BACKGROUND_PENDING`, to be resumed.
- A live V03 run or resume requires an external journal checkpoint: `--checkpoint-git-branch <current branch>` or `--checkpoint-dir <durable dir>`.

The first 30-card run must:
- use three 10-card generator rounds;
- allow at most three generator POSTs (`GENERATOR_CONTENT_RETRIES = 0`);
- allow no generator retry;
- make zero selector LLM calls;
- set `OPENAI_NETWORK_MODE = CLOUD_PROXY` when run from a Cloud Agent (`python -m scripts.research.generator_v0 first-30-card`);
- fail closed if a required generator round cannot complete inside the authorized Anthropic budget;
- keep protected data unopened;
- use the frozen routes above;
- leave Memory Finalizer V1 unchanged.

`MEMORY_FINALIZER_V1` remains the only memory writer. This repair does not execute the live 30-card campaign.
