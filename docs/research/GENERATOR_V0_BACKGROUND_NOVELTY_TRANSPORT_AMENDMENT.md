# Generator V0 — background Responses transport for routed NOVELTY_CRITIC

Date: 2026-09-24. Stacked on PR #217 (`f614935`). Offline amendment; no live
API call was made in this unit. No research window, hypothesis or protected
data consumed. `SCIENTIFIC_CONTRACT_CHANGED = false`.

## Why

The five-card cost calibration (infrastructure only, no scientific status) hit
two independent ambiguous, non-JSON HTTP 502 answers. Both were on production-
shaped five-card routed `NOVELTY_CRITIC` requests (`gpt-6-sol`,
`reasoning_effort=high`, synchronous Chat Completions). In the same runs:

- Luna feasibility: 2 completed.
- Sol red team: 2 completed.
- Sol novelty: 2 completed, 2 ended `UNCERTAIN`.

2 of 4 is not a production failure-rate estimate; the sample is too small. It
is enough to change the transport before more calibration spend. The owner
decision is to change only the transport of routed `NOVELTY_CRITIC`.

## Change

| Role | Before | After |
|---|---|---|
| NOVELTY_CRITIC | `POST /v1/chat/completions`, synchronous, `stream=false` | `POST /v1/responses` with `background=true`, `store=true`, `stream=false`; then `GET /v1/responses/{response_id}` until terminal |
| FEASIBILITY_CRITIC | Chat Completions (sync) | unchanged |
| RED_TEAM | Chat Completions (sync) | unchanged |
| SELECTOR (advisory) | Chat Completions (sync) | unchanged |
| GENERATOR | Anthropic Messages | unchanged |

What does not change:

- **Model and effort:** `gpt-6-sol`, `reasoning_effort=high`, 12000 output tokens.
- **Content:** the novelty prompt, the request context, the five-card `BATCH_RELATIONS` shape, and every relation enum.
- **Schema:** the strict schema is the same object, keyed by all 31 leaf signature IDs and the other batch candidate IDs. Responses carries it as `text.format.{type=json_schema, name, strict=true, schema}` instead of Chat's `response_format.json_schema`.
- **Contract, logic and budget:** the application contract, normalization, critic logic, selector, and budget authority.

The Responses path reuses the existing legacy-generator background design:

- the same `create_background`, `retrieve_background` and `delete_background` adapter methods;
- the same `Caller._await_background` state machine;
- the same ledger states and store policy (`STORE_TRUE_REQUIRED_FOR_RESUME`).

No new polling or reconciliation architecture was added.

Code:

- **`routing.py`:**
  - Adds `OPENAI_RESPONSES_BACKGROUND_TRANSPORT`, used only by the NOVELTY_CRITIC route (`ENDPOINT=OPENAI_RESPONSES_BACKGROUND`, `STRUCTURED_OUTPUT=OPENAI_RESPONSES_TEXT_FORMAT_JSON_SCHEMA_STRICT`).
  - The routes fail closed on any endpoint a provider does not support, and on a background GENERATOR.
- **`openai_provider.py` (routed mode):**
  - Background Responses is used for roles whose route endpoint is background.
  - The Responses payload for those roles uses the route's model, effort and cap.
  - Polled envelopes are stripped of reasoning-item content before they are journaled.
  - Responses usage records `cached_tokens` when present.
- **`routed_provider.py`:** background calls are delegated to the single background adapter. The adapter's background mode must agree with the route.
- **`provider.py`:** polling uses the provider's poll sleeper when one exists. A guard that refuses transport-replay backoff therefore cannot stop polling. Legacy providers are unchanged.

## Exactly-once and uncertainty

The Caller commits `DISPATCHED` before the create POST. A usable create
acknowledgement is persisted at once as `BACKGROUND_SUBMITTED` with its
`response_id`. On resume that row is only polled with `GET`; there is never a
second POST.

| Situation | Outcome |
|---|---|
| Create timeout or connection loss | `UNCERTAIN`, never replayed |
| Ambiguous create answer (5xx other than 503, 200 without an id, non-JSON 200) | `UNCERTAIN`, never replayed |
| Polling timeout, connection loss or 5xx | keep polling the same `response_id`; past the operator wait, `BackgroundPending` and a resumable `BACKGROUND_SUBMITTED` row |
| Terminal `incomplete` / `failed` / `cancelled`, or `completed` without usable text | `FAILED_WITH_COST`, with usage cost when present (else the reservation), no raw text |
| `completed` with text that breaks the application contract | journaled as `COMPLETE` (billed) and rejected by the consumer (`RoleContractError`) |

Create answers 429 and 503 keep the existing `classify_http` semantics. This
is the same classification the synchronous novelty path used; no retry was
added.

## Identity

| | Before (PR #217) | After |
|---|---|---|
| NOVELTY route digest | `b784767e…4f03` | `597296d5…0760` |
| Routing digest | `e925b578…4f1b` | `9c99dc12…df66` |
| Reference novelty call key (identity-dump request) | `6f701215…25e2` | `2c12988a…1bca` |
| FEASIBILITY / RED_TEAM / SELECTOR / GENERATOR route digests | — | unchanged |
| Reference Luna and Sol red-team call keys | `e13d21ca…434a`, `ef4bebf2…8eb6` | unchanged |

Every request carries `provider=OPENAI_RESPONSES_BACKGROUND` and the new route
digest. An old synchronous novelty request, including either of the two
UNCERTAIN 502 attempts, cannot be mistaken for a background call: the router
refuses it.

## Provenance, usage, cost

- `raw_sha256` is the hash of the verbatim output text.
- `wire_sha256` is the hash of the untouched terminal envelope bytes.
- A failed attempt has no `raw_sha256`.
- The response id and terminal provider status are journaled.
- Reasoning items keep only `type` and `id`: no summary, no encrypted content.
- Price authority is unchanged (`gpt-6-sol` USD 2 / 10 per 1M tokens).
- Cached input is recorded but priced at the standard input rate (conservative).
- The bound formula is unchanged. The novelty payload bytes differ slightly: the 40-card novelty worst case moves from USD 13.852300 to USD 13.848380 (`BUDGET_SCENARIOS.json` regenerated).

## Offline timing diagnostic of the four live novelty calls

Neither calibration journal records per-call timestamps. The response
envelopes were not persisted, and response ids carry no time. Available
evidence is file timestamps only:

- **Attempt 1 (C001 novelty, 502):** about 31 s from journal creation to the recorded failure, including an offline precheck. The failure came within about 30 s of dispatch.
- **Attempt 2:** 7 calls took 127 s end to end (13:51:42 → 13:53:49 UTC). This covers C001 and C002 novelty, feasibility and red team (all completed), then C003 novelty (502). Per-call durations, including the two successful novelty calls and the second 502, cannot be isolated.
- **Clustering:** no common failure duration can be established from this data.
- **Proxy causation:** not proven. The session proxy reported no relay failures. The 502 bodies were non-JSON and only their hashes were kept.
- **Evidence the first 502 reached OpenAI:** in attempt 2, the C001 novelty prompt was served almost entirely from OpenAI's prompt cache (10,453 of 10,456 input tokens). So attempt 1's identical request reached OpenAI and was processed at least as far as caching its prompt. Its billing remains unknown, and its conservative UNKNOWN charge stands.

## Validation

Focused tests only (see the PR). New: `tests/research/test_generator_v0_background_novelty.py`.
`compileall` and `git diff --check` pass. Sealed v7 SHA256 is unchanged
(`e27eb1ce…f36457`). The full repository pytest was not run.

`COMPLETION_STATE = READY_FOR_BACKGROUND_NOVELTY_INDEPENDENT_REVIEW`
