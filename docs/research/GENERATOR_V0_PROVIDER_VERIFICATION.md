# Real-provider API verification

Verified 2026-09-23 against official sources, without an API call:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/background
- https://developers.openai.com/api/reference/resources/responses
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/models/gpt-6-sol
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/pricing

Mixed adapter. GENERATOR uses OpenAI Responses,
`POST https://api.openai.com/v1/responses`, `background=true`, `store=true`,
Bearer authentication, **Structured Outputs** via
`text.format.{type=json_schema,name,strict=true,schema}`, `reasoning.effort`,
`max_output_tokens`, nonstreaming, no tools, standard service tier.
Critics and the selector remain Chat Completions,
`POST https://api.openai.com/v1/chat/completions`,
`response_format.type=json_schema`, `json_schema.strict=true`,
`max_completion_tokens`, nonstreaming, no tools, `store=false`, standard
service tier.

`BACKGROUND_STORE_POLICY = STORE_TRUE_REQUIRED_FOR_RESUME`. Official
background guidance: after the ~10 minute polling window, a background
Response is retained only if `store=true` is explicit. That is required
for crash-safe resume of the same `response_id`. After local COMPLETE
persist, `DELETE /v1/responses/{id}` is a supported best-effort cleanup
and must not fail the run.

JSON mode (`response_format.type=json_object`) is not used. It guarantees JSON
syntax only and allowed a real `gpt-4.1-mini` response to emit an extra `STREAM`
field. Strict JSON Schema is generated from the existing application role
builders. Application-side validators remain mandatory and are not weakened.

Role map (official catalog has no dated snapshots; cached-input discounts
ignored; Standard short-context rates). GENERATOR is billed at Astra
Standard generation prices; polling GETs do not reserve a new generation:

| Role | Model | Input / output USD per 1M | Request params |
|---|---|---|---|
| GENERATOR | `gpt-6-astra` | 10.00 / 50.00 | `reasoning_effort=high`; no temperature |
| NOVELTY_CRITIC | `gpt-6-sol` | 2.00 / 10.00 | `reasoning_effort=medium`; no temperature |
| RED_TEAM | `gpt-6-sol` | 2.00 / 10.00 | `reasoning_effort=medium`; no temperature |
| FEASIBILITY_CRITIC | `gpt-6-luna` | 0.10 / 0.50 | `reasoning_effort=low`; no temperature |
| SELECTOR | `gpt-6-luna` | 0.10 / 0.50 | `reasoning_effort=none`; no temperature |

GPT-6 Astra, Sol, and Luna all support Chat Completions and Structured
Outputs. Astra additionally supports Responses background mode, which is
used only for GENERATOR. Astra does not support `reasoning_effort=none`;
Sol and Luna do. When reasoning effort is not `none`, temperature / top_p /
logprobs are not sent. Unknown models and missing verified prices fail closed.

The archived partial runs `artifacts/generator_v0/first-shadow`,
`first-shadow-v2`, and `first-shadow-v3` are sealed and must not be
resumed. Those snapshots are not in the live routing table.

Every object in the provider JSON Schema sets `additionalProperties: false`
and lists every property as required. Frozen `SEARCH_SURFACE.PARAMETERS` is a
dict; OpenAI strict schema cannot express free-form keys, so the provider
encoding is an array of `{NAME,VALUES}` that is converted back to the frozen
dict before application validation. Semantic checks (protected years, empty
strings, unverified DATA_READY, lookahead language) remain application-side.

Transport has no automatic POST retries or redirects. Polling GET may
retry on `TimeoutError`, `OSError`, and HTTP 5xx without creating a new
paid request. GENERATOR create timeout is 60 seconds; critic Chat
Completions timeout remains `OPENAI_REQUEST_TIMEOUT_SECONDS = 600`
(bounded 1..1800, fail-closed). Polling policy: interval 3 seconds
(bounded 2..5), GET timeout 45 seconds (bounded 30..60), operator wait
3600 seconds. These values are stored in run configuration identity. A
create timeout or missing `response_id` retains its reservation as
`UNCERTAIN` and is never automatically replayed. A known `response_id`
is recovered by GET. This is a local conservative budget ledger, not a
replacement for provider billing records. No real call was made during
this adapter change.
