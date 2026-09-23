# Real-provider API verification

Verified 2026-09-23 against official sources, without an API call:

- https://developers.openai.com/api/docs/models/gpt-4.1-mini
- https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create/
- https://developers.openai.com/api/docs/guides/structured-outputs

Concrete first adapter: OpenAI Chat Completions, pinned
`gpt-4.1-mini-2025-04-14`, `POST https://api.openai.com/v1/chat/completions`,
Bearer authentication, text-only JSON object mode, `max_completion_tokens`,
nonstreaming, no tools, no storage, standard service tier.
The official model page lists the snapshot and standard text-token pricing:
USD 0.40 input and 1.60 output per million tokens. Cached-input discount is
ignored for conservative accounting. Model availability for an individual
account is not tested by offline preflight.

JSON mode does not guarantee schema compliance. Every generated card and
critic response is validated locally before use; malformed paid responses
remain journaled and are not automatically replayed. API refusal, truncation,
missing usage and HTTP errors stop the run. Transport has no automatic retries
or redirects. A timeout remains fully reserved and blocks automatic replay.

Input reservation uses UTF-8 byte count plus 1024 framing tokens; output uses
the enforced completion limit. Rates and model are pinned; no arbitrary model
name can silently use these prices. Usage outside the conservative bound
stops processing with the reservation retained. This is a local conservative
budget ledger, not a replacement for provider billing records or account limits.
Reverify prices/API support before operating against materially changed provider
terms. No real call was made during this implementation.
