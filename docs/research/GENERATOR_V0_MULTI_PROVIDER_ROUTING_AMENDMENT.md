# Generator V0 — outcome-blind multi-provider routing amendment

**Completion state:** `READY_FOR_MULTI_PROVIDER_INDEPENDENT_REVIEW`
**Base:** `8fc5c4c01a724a8b5ec3e0f9209f5dbaf7fcff3e` (PR #214, verified `READY_FOR_PROVIDER_SMOKE_TEST`)
**Machine-readable twin:** `docs/research/GENERATOR_V0_MULTI_PROVIDER_ROUTING_AMENDMENT.json`

This unit is infrastructure only:
- no real API call, no live shadow, no protected 2025/2026 data, no scientific outcome;
- sealed v6/v7 unchanged;
- all provider behaviour is exercised through fake transports.

## Amendment (outcome-blind)

Only the provider/model/effort that implements each role changes. This is recorded as an outcome-blind design amendment because model choice can affect scientific output. It was decided before any output of the new routing exists.

Why:
- **High-quality ideation uses Opus.** The generator carries the creative load.
- **Independent scientific critique uses a different model family and provider** (Sol). Criticism is cross-model and blind: critics receive only the candidate and the frozen research context, never provider or model metadata (tested).
- **Cheap, near-deterministic work uses Luna** (feasibility against the catalog, the advisory selector).
- **Code stays authoritative for deterministic operations.** The ordinal selection order is computed in code; the Luna selector call is advisory and cannot change or abort the result.

Unchanged:
- candidate count, 40-slot structure, card schema;
- LEGAL_RANGE and protected-data rules;
- novelty, feasibility and red-team semantics;
- deterministic ordering, `MIN_VALID_CANDIDATES`, the human-review boundary, HARD_FAIL / REVIEW_FAILED behaviour;
- the owner ceiling (USD 17.10), output caps and batch size.

## Routing (`scripts/research/generator_v0/routing.py`, authoritative)

| Role | Provider | Model | Effort | Max output tokens |
|---|---|---|---|---|
| GENERATOR | ANTHROPIC | claude-opus-5-5 | effort=high | 32768 |
| NOVELTY_CRITIC | OPENAI | gpt-6-sol | reasoning_effort=high | 12000 |
| RED_TEAM | OPENAI | gpt-6-sol | reasoning_effort=high | 8000 |
| FEASIBILITY_CRITIC | OPENAI | gpt-6-luna | reasoning_effort=low | 6000 |
| SELECTOR | OPENAI | gpt-6-luna | reasoning_effort=none | 2000 |

- Routing digest: `c0eefdfa06e7f2607be905aac961bf0d46fd609ea8482ab852052efe8b90be38` (router identity: registry + adapter transport identities).
- The digest covers provider, model, effort, prices, output caps, structured-output mode and transport.
- Every request carries `route_provider` and `route_digest`, so the call key differs across providers and models: a call made on Opus can never replay as a call on Sol or Luna.
- The legacy OpenAI-only map (`models.ROLE_MODEL_MAP`) remains only for the `--provider openai` regression path.

## Architecture

runner / roles → Caller → `RoutedProvider` → `AnthropicProvider` (Opus) | `OpenAIProvider` (routed mode: Sol, Luna)

- The Caller still owns one budget, one ledger, one call-key system and one retry/reconcile state machine.
- The router is stateless. It checks each adapter against the registry and never falls back across providers.
- `runner.py` and `roles.py` are unchanged.

## Anthropic request (GENERATOR)

`POST /v1/messages` with headers `x-api-key` (from `ANTHROPIC_API_KEY`, never persisted), `anthropic-version: 2023-06-01` and `content-type: application/json`. The body:

```
{"model":"claude-opus-5-5","max_tokens":32768,"system":<frozen GENERATOR prompt>,
 "messages":[{"role":"user","content":canonical({"context":…,"slots":[…]})}],"stream":false,
 "output_config":{"effort":"high","format":{"type":"json_schema","schema":<Anthropic projection>}}}
```

- The request has no thinking parameter (Opus 5.5 thinking is adaptive), no temperature, no tools/tool_choice, no citations, no cache_control, no batch and no streaming.
- **Schema.** Claude structured outputs do not support numerical or complex-array constraints, so the request carries the exact provider generator schema with only `minimum`, `maximum` (MAX_VARIANTS) and `maxItems` (DATA_REQUIRED) removed: 3 per card, 30 per round.
  - Everything else is identical: keyed slot IDs, required fields, enums, the LEGAL_RANGE pattern.
  - Every removed constraint is still enforced after decoding. Intake validates each card against the exact provider schema, then the V02 rules.
  - An offline Anthropic subset checker passes on all four round schemas. Provider acceptance is not proven offline.
- **Response.** Only a `message` with a `msg_` id, the requested model, `stop_reason=end_turn`, valid usage and exactly one non-empty text block is usable.
  - Thinking blocks are dropped and never persisted.
  - `raw` is the verbatim text, with `raw_sha256`; the envelope is represented by `wire_sha256`.

## Anthropic failure taxonomy

| Situation | Class | Effect |
|---|---|---|
| 400, 401, 402, 403, 404, 413 | NOT_BILLED, not retryable | `PAUSED_PROVIDER_REJECTED` |
| 429 `rate_limit_error`, 529 `overloaded_error` (documented error body) | NOT_BILLED, retryable | backoff, new transport-attempt key |
| 429/529 without that body, 408, 409, 500, 502, 503, 504, other | UNCERTAIN | pause, reconcile; never re-sent |
| Connection loss or timeout after dispatch; crash after dispatch | UNCERTAIN / DISPATCHED | pause, reconcile; never re-sent |
| Oversized response | UNCERTAIN | pause |
| 200 unparseable | BILLED at reservation | content retry allowed by the consumer |
| 200 with max_tokens, refusal, model_context_window_exceeded, tool_use, unexpected blocks, wrong model/id, not exactly one text block | BILLED with usage cost (reservation if usage invalid) | content retry allowed by the consumer |
| 200 with missing, malformed or over-bound usage | BILLED at reservation | — |

## Usage and cost

- Recorded fields: `input_tokens`, `output_tokens`, cache read/creation (5m and 1h split), and `thinking_tokens` when present.
- Integer micro-USD with ROUND_CEILING.
- Output tokens are authoritative: no reasoning surcharge.
- Cache tokens use their own rates: read 0.20, 5m write 5, 1h write 8. An unsplit write uses the higher 1h rate. Caching is not enabled.
- **Bound:** request bytes + 4096 tokens of scaffolding at the standard input rate, plus `max_tokens` at the output rate. No cache or batch discount.
  - A computed cost above the bound is charged at the reservation and flagged, so recorded cost never exceeds the reservation (property-tested).

## Budget (fresh 40-card run, worst-case reservation — not expected cost)

| Role | Route | Calls | Worst case, single attempt (USD) |
|---|---|---|---|
| FEASIBILITY_CRITIC | OPENAI / gpt-6-luna / reasoning_effort=low | 40 | 0.187775 |
| GENERATOR | ANTHROPIC / claude-opus-5-5 / effort=high | 4 | 3.584336 |
| NOVELTY_CRITIC | OPENAI / gpt-6-sol / reasoning_effort=high | 40 | 13.852300 |
| RED_TEAM | OPENAI / gpt-6-sol / reasoning_effort=high | 40 | 4.194940 |
| SELECTOR | OPENAI / gpt-6-luna / reasoning_effort=none | 1 | 0.001938 |

- Fresh single attempt: **USD 21.821289**; with allowed content retries: **USD 43.640640**.
- If this run were counted inside the v7 campaign authority: USD 26.768039.
- A v7-derived routed run is not applicable: it would mix generator models inside one batch, and derive of routed journals is not implemented.
- The single campaign ceiling spans both providers (tested). The owner ceiling is unchanged, and no live run is authorized.

**Product/cost targets** (for later empirical calibration; not authorization to weaken gates or change the design): `TARGET_EXPECTED_FULL_40_CARD_RUN_USD <= 10`, `TARGET_4_RUN_MONTH_USD <= 40`.

## Mixed-provider noisy offline E2E

Opus generator → Luna feasibility → Sol novelty → Sol red team → deterministic selection → `PENDING_HUMAN_REVIEW`.

- Injected faults: Anthropic 529, a dropped card, a non-canonical range, a max_tokens stop plus a protected-year card, novelty omission and truncation, a Luna 429 and double-malformed answer, and a crash after POST on Sol.
- Result:
  - 122 POSTs = 122 journal rows (6 to `/v1/messages`, 116 to Chat Completions);
  - NOT_BILLED without evidence refused;
  - every role on its route (checked from journal rows).

## CLI

- `--provider routed`. `preflight` needs no secrets and prints the routing table, digest, schema digests and bounds.
- `run`/`resume` require `--allow-real-llm`, a nonzero budget, and **both** `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.
- The run config records the role maps, parameters, price table, routing digest, transport identities and schema digests, never credentials.
- `--provider openai` is unchanged (legacy).

## Deferred (after provider smoke and empirical 5-card cost calibration)

- Anthropic Batch API and OpenAI Batch API;
- prompt caching;
- Opus second opinion / disagreement arbitration;
- adaptive routing on critic confidence;
- batch-size change;
- lowering scientific-quality roles to hit budget.

## Remaining blockers / open items

- Provider acceptance of the Anthropic projection (including the LEGAL_RANGE `pattern`) and of the OpenAI strict schemas is proven offline only.
- The Anthropic input bound adds a fixed 4096-token margin for provider-side scaffolding; this is not calibrated.
- Worst-case bounds exceed USD 17.10. A live run needs a recorded budget-stop acceptance or an owner decision.
- Derive/import of routed journals is not implemented (fails closed).
- Real Anthropic error bodies and usage fields are taken from documentation, not observed.
