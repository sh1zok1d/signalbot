# Generator V0 — Anthropic GENERATOR output-cap amendment (offline repair)

**Completion state:** `READY_FOR_FINAL_RE_SMOKE_REVIEW`
**Base:** `d10d0a277edc2f95b007eeba2e47138a83a8027e` (PR #216)
**Machine-readable twin:** `docs/research/GENERATOR_V0_ANTHROPIC_OUTPUT_CAP_AMENDMENT.json`

## Trigger: live compact re-smoke (2026-09-24)

One authorized Anthropic GENERATOR request was sent through the production routed path. It used the compact wire `ANTHROPIC_COMPACT_CANDIDATE_ARRAY_V1` with one 10-slot round (generation:0).

- HTTP 200. The compact schema was accepted: no grammar rejection, and decoding ran.
- Response `msg_011CfN3ZuBMiCqeAeRNdWSsJ`, `stop_reason = max_tokens`.
- Usage: input 14,493 tokens; output 32,768 tokens (the full cap), of which 17,396 were thinking tokens.
- Ledger state `FAILED_WITH_COST`, cost USD 0.713332 (reserved 0.782028).
- Call key `f8207e1f0fa229f24eec50b0c894d704dd32ad1fece59672e2d2440b47ea930e`; wire SHA256 `968550f7935eaf873a08b1d846a7b314cca797d37f49ab5e64cc2d8035922af2`.
- No usable text, so the round was never parsed or run through intake, and no critic call was made. Live POSTs: 1. Nothing was retried.

## Owner decision

Increase **only** the routed Anthropic GENERATOR output cap from 32,768 to 100,000 tokens. Claude Opus 5.5 supports up to 128K output tokens. This is execution headroom, not a scientific change.

Preserved:
- `claude-opus-5-5`, `effort=high`;
- round size 10 and 40 candidates;
- the compact Anthropic projection;
- all V02 scientific rules;
- the legacy OpenAI generator cap (`models.GENERATOR_MAX_OUTPUT_TOKENS = 32768`).

## Change

- `routing.ANTHROPIC_GENERATOR_MAX_OUTPUT_TOKENS = 100000` is the GENERATOR route's `MAX_OUTPUT_TOKENS`. `validate_routes` requires exactly this cap for an Anthropic GENERATOR route and 32,768 for an OpenAI one.
- The runner and the budget bound path take the generator cap from the provider's route (`runner.generator_max_output_tokens`). The legacy OpenAI provider, the mock and `derive.expected_generator_request` still use 32,768.
- The Anthropic adapter still refuses a request whose `max_output_tokens` differs from the route. An old 32,768 request cannot be sent on the new route.
- Operator preflight and run config report the provider's generator cap.

## Identity

The cap enters identity in two places:
- the request `parameters.max_output_tokens`;
- the GENERATOR route digest carried in every request.

As a result, every round has a new call key.

| Round | New call key | Bound (USD) |
|---|---|---|
| generation:0 | `b1ed0d8333ae4b823e72e4175ef7680e0896cfc02915aa476d3278fa56d5cc93` | 2.126672 |
| generation:1 | `0133c0e927ffe8cee38d71cd455db1290645b24a5bad5eefca6273f01c2e0104` | 2.126732 |
| generation:2 | `25cb753aec9bce02ba1b8d9258f0e3bb396864d0a66e8a81e7954b2217411ebc` | 2.126716 |
| generation:3 | `b3b49ca295e90a8bf76c572a0b68e7f8c93720da97e8d4b0168271c6d0593db1` | 2.127392 |

- None equals the billed failed 32,768 call (`f8207e1f…`) or the earlier keyed grammar rejection (`767fd9e1…`). Both facts are tested.
- A journal holding the failed row posts the new call under a new key and leaves the old row unchanged (tested).
- Routing digest: `ef21451e…` becomes `e925b578bfc0cdc2bfe354406178f56068d3745b784e36933b7d76cd5b344f1b`.
- Router identity: `d3d389e3740b37ede85b15c1e73b5b1fb0ab8f61fda4d97c48aadae4b753375a`.
- Critic route digests and call keys are unchanged.

## Hash provenance fix

`Ledger.failed` used to store the provider-envelope hash under `raw_sha256`. It now enforces the following:

- `raw_sha256` is the hash of usable verbatim model text only. It is written by `finish` on COMPLETE.
- `wire_sha256` is the hash of the provider envelope.
- A failed attempt (billed, not billed or uncertain) never has `raw_sha256`. It has `wire_sha256` when an envelope was received, and neither hash when none was received (for example, a timeout).

The live smoke row above lives in an external smoke ledger created before this fix; its `raw_sha256` field holds the wire hash. Its true values are `RAW_SHA256 = null` and `WIRE_SHA256 = 968550f7…`.

## Recalculated bounds

Worst-case reservations: maximum output on every call, with no discount.

| Item | Before | After |
|---|---|---|
| Anthropic GENERATOR round, generation:0 (input bound 31,668 tokens + 100,000 output) | 0.782028 | 2.126672 |
| 4 generator rounds | 3.128936 | 8.507512 |
| Fresh 40-card routed, single attempt | 21.365889 | 26.744465 |
| Fresh 40-card routed, with content retries | — | 53.486992 |

- Both fresh 40-card figures exceed the owner ceiling of USD 17.10. The single-attempt figure already did before this change. A fresh routed campaign therefore still needs an explicit budget decision or a recorded budget-stop acceptance. This amendment authorizes no campaign.
- Legacy OpenAI budget scenarios are unchanged.
- `OFFLINE_GATE_REPORT.json` was regenerated. Only the mixed-provider noisy E2E spend changed: USD 2.475682 became 3.706682.
  - +1.344644: the synthetic generation:0 `RECONCILED_UNKNOWN` fault is charged at its reserved bound, which grew by that amount.
  - −0.113644 (= 0.895672 − 0.782028): the committed report predated the compact projection and was stale.
  - No other row changed.

## Smoke budget (owner authorization)

- Absolute smoke ceiling: USD 3.10 (3,100,000 micro-USD). This includes historical spend.
- Historical actual smoke spend: 0.713332.
- Next re-smoke reservations:
  - Opus GENERATOR, 100,000 cap: 2.126672;
  - Luna FEASIBILITY: 0.003950;
  - Sol NOVELTY, with a single-candidate batch so `BATCH_RELATIONS = {}`: 0.194770.
- Total: 3.038724. This **fits**, with 0.061276 headroom.
- Tested in `test_smoke_reservations_fit_the_absolute_smoke_ceiling_including_history`.

## Follow-up: timeout and smoke-budget guard

Independent review accepted the output cap. Two operational guards were added before any further live call. No scientific field changed, and no live call was made in this follow-up.

The Anthropic synchronous timeout is 1800 s. `stream=false` is unchanged. There is no streaming and no Message Batches. 299 s × 100000 / 32768 is about 912 s, so the old 900 s timeout could expire during a valid full response. The timeout stays in the adapter transport identity. Router identity is now `338df127c4f8f0a41c3b21cb4cb3fbac33e6ab4a115d724414ec0a183140e336`. The routing digest and the generation:0 call key `b1ed0d83…` are unchanged. The OpenAI timeout stays 600 s.

The re-smoke entry is `resmoke.run_resmoke`. It opens a ledger with `CAP_MICRO_USD = 3100000` and lineage `PRIOR_SPEND_MICRO_USD = 713332`, and it refuses to POST unless both are present. `Ledger.reserve` then rejects any reservation that would put lineage + journal + bound over USD 3.10. A fresh process cannot be given USD 3.10 of new spend on top of the historical USD 0.713332.

A COMPLETE generator row is not enough to call critics. Resume loads that row's raw text and journaled wire format, then uses the same parse and idempotent intake as a fresh response. An unusable round stays `STOPPED_UNUSABLE_ROUND`. A round that admits nobody stays `STOPPED_NOTHING_ADMITTED`. Neither resume sends Luna or Sol.

`run_resmoke` makes at most one Anthropic POST. It does not call `_round_output`, so `MAX_CONTENT_ATTEMPTS = 2` cannot send a second generator request. A billed or unusable generator response stops the smoke, and a second invocation does not POST. An UNCERTAIN attempt is not replayed. A retryable transport failure cannot sleep and post again. Luna and Sol run only after a COMPLETE, parseable round that intake admitted, and only while their reservations still fit. There is no RED_TEAM call.

New-spend room is USD 2.386668. Planned reservations remain 2.126672 + 0.003950 + 0.194770 = 2.325392. With history that is USD 3.038724 of the USD 3.10 ceiling.

## Validation actually recorded

For the output-cap commit, before this follow-up: Generator V0 subset 695 passed; `compileall` passed; `git diff --check` passed. Full-repository pytest was started, ran for more than 90 minutes, and did not complete. No full-suite result is available. No GitHub Actions run was recorded for that head.

This follow-up adds `tests/research/test_generator_v0_resmoke_guard.py`. Its result is reported with the commit. No live API call was made. No protected 2025/2026 data was opened. The sealed v7 journal is unchanged (`e27eb1ce…`).
