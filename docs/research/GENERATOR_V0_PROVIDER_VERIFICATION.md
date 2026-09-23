# Real-provider API verification

Verified 2026-09-23 against official sources, without an API call:

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/models/gpt-6-sol
- https://developers.openai.com/api/docs/models/gpt-6-luna
- https://developers.openai.com/api/docs/pricing

Concrete adapter: OpenAI Chat Completions, `POST https://api.openai.com/v1/chat/completions`,
Bearer authentication, **Structured Outputs** (`response_format.type=json_schema`,
`json_schema.strict=true`), role-specific stable model IDs, `max_completion_tokens`,
nonstreaming, no tools, no storage, standard service tier.

JSON mode (`response_format.type=json_object`) is not used. It guarantees JSON
syntax only and allowed a real `gpt-4.1-mini` response to emit an extra `STREAM`
field. Strict JSON Schema is generated from the existing application role
builders. Application-side validators remain mandatory and are not weakened.

Role map (Chat Completions; official catalog has no dated snapshots;
cached-input discounts ignored; Standard short-context rates):

| Role | Model | Input / output USD per 1M | Request params |
|---|---|---|---|
| GENERATOR | `gpt-6-astra` | 10.00 / 50.00 | `reasoning_effort=high`; no temperature |
| NOVELTY_CRITIC | `gpt-6-sol` | 2.00 / 10.00 | `reasoning_effort=medium`; no temperature |
| RED_TEAM | `gpt-6-sol` | 2.00 / 10.00 | `reasoning_effort=medium`; no temperature |
| FEASIBILITY_CRITIC | `gpt-6-luna` | 0.10 / 0.50 | `reasoning_effort=low`; no temperature |
| SELECTOR | `gpt-6-luna` | 0.10 / 0.50 | `reasoning_effort=none`; no temperature |

GPT-6 Astra, Sol, and Luna all support Chat Completions and Structured
Outputs. Astra does not support `reasoning_effort=none`; Sol and Luna do.
When reasoning effort is not `none`, temperature / top_p / logprobs are
not sent. Unknown models and missing verified prices fail closed.

The archived partial run `artifacts/generator_v0/first-shadow` used
`gpt-4.1-mini-2025-04-14` with JSON mode; it is sealed and must not be
resumed. That snapshot is not in the live routing table.

Every object in the provider JSON Schema sets `additionalProperties: false`
and lists every property as required. Frozen `SEARCH_SURFACE.PARAMETERS` is a
dict; OpenAI strict schema cannot express free-form keys, so the provider
encoding is an array of `{NAME,VALUES}` that is converted back to the frozen
dict before application validation. Semantic checks (protected years, empty
strings, unverified DATA_READY, lookahead language) remain application-side.

Transport has no automatic retries or redirects. The real HTTPS timeout is
`OPENAI_REQUEST_TIMEOUT_SECONDS = 600` (bounded 1..1800, fail-closed) and is
stored in run configuration identity. A timeout or malformed structured
envelope retains its reservation and is never automatically replayed. This
is a local conservative budget ledger, not a replacement for provider
billing records. No real call was made during this adapter change.
