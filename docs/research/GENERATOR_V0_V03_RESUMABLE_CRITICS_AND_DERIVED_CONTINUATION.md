# Generator V0 — resumable V03 OpenAI critics and the r02 derived continuation

`OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1 = IMPLEMENTED (offline)`
`LADDER40_V03_R02 = PAUSED_UNCERTAIN_CALL / IMMUTABLE_SOURCE_FOR_DERIVED_CONTINUATION`
`DERIVED_RUN_ID = ladder-40-card-v03-r02-derived-critics-v1`
`DERIVED_CONTINUATION_LIVE_AUTHORIZED = false`
`SCIENTIFIC_DESIGN_CHANGED = false`
`LIVE_LLM_CALLS = 0`

This is an infrastructure repair. It is not a scientific failure and it does not generate new hypotheses.

## Source run

`ladder-40-card-v03-r02` stopped while reviewing card C024.

- Status: `PAUSED_UNCERTAIN_CALL`.
- Checkpoint branch: `run/ladder40-v03-r02`, head `bb13d8f26a93713fa6fb956703c5207486b6a570`.
- Durable snapshot: persistence PR #299. The byte-identical journal used here is `docs/research/generator_v0_ladder40_v03_r02/run.sqlite`, SHA256 `ffa179220d12986520c214f7a1ad1cfecd084848f9de0158fcd43476d9447a37`.
- Generator: 4/4 rounds `COMPLETE` on Anthropic Message Batches, cost USD 2.192768.
- Candidates: 40 slots, 30 `VALID`, 10 `HARD_FAIL`.
- Critic calls completed before the stop: novelty 14, feasibility 13, red team 13.
- Open call: `FEASIBILITY_CRITIC`, slot `FEASIBILITY_CRITIC:C024`, call key `76ddea9fac6cbafa398ad5c821b1fed99e40f25be8af903ef0634811b0450604`, state `UNCERTAIN`, error `TimeoutError`, response id null, reserved USD 0.005302.
- Source charged total: USD 3.659239, which already includes that reservation.

The open call was not reconciled and the source journal was not modified. r01 stays separately charged at its conservative USD 2.210772.

Cause: on `GENERATOR_CONTRACT_V03`, the generator used Message Batches and novelty and red team used background Responses, but feasibility and the selector still used synchronous Chat Completions. The C024 feasibility call timed out after `DISPATCHED` with no provider id.

## Transport amendment

For `LADDER_ROUTES` only, feasibility and the selector now use `OPENAI_RESPONSES_BACKGROUND`.

| Role | Model | Effort | Max output | Transport |
| --- | --- | --- | --- | --- |
| GENERATOR | claude-opus-5-5 | high | 100000 | Anthropic Message Batches |
| NOVELTY_CRITIC | gpt-6-sol | high | 12000 | OpenAI background Responses |
| FEASIBILITY_CRITIC | gpt-6-luna | low | 6000 | OpenAI background Responses |
| RED_TEAM | gpt-6-sol | high | 8000 | OpenAI background Responses |
| SELECTOR | gpt-6-luna | none | 2000 | OpenAI background Responses (advisory) |

Prompts, schemas, models, effort and the selector's advisory-only rule are unchanged. The structured-output wire wrapper for the two moved roles is the Responses `text.format` wrapper. `ROUTES` (V02 / first-30-card) is unchanged, so those two roles stay on Chat Completions there. No synchronous paid route remains on the V03 ladder.

## Derived continuation

`ladder-40-card-v03-r02-derived-critics-v1` is a derived continuation of r02, not r03 and not a fresh campaign.

- The four `COMPLETE` generator rounds are imported. No new generator POST is required.
- Offline revalidation reproduces the source corpus: 40 slots, 30 `VALID`, 10 `HARD_FAIL`, with the same candidate ids, card bodies and intake verdicts.
- Source critic calls are `PRIOR_ATTEMPTS` only. They are not official judgments of this run. All 30 valid cards are to be reviewed again, uniformly, under the new routing.
- The C024 call stays `UNCERTAIN` in the source. Its USD 0.005302 reservation stays inside the carried source spend. It is not replayed or reconciled here.
- Destination initial charged total: USD 3.659239.
- r02 cap: USD 9.789228. Remaining authorization: USD 6.129989. No new budget authority was created.

Journal: `docs/research/ladder-40-card-v03-r02-derived-critics-v1/`. Status `DERIVED_IMPORTED_REVALIDATED`. A later live resume would still need a separate owner authorization and `authorize-derived-continuation`. This task does not grant that.

## Remaining-work preflight

Offline bound through the current ladder routes. Zero generator calls. Critics for the 30 valid cards, with the frozen two content attempts on critics and one selector call. No proxy cards.

| Figure | USD |
| --- | --- |
| BASE_REMAINING_BOUND (one attempt) | 14.518795 |
| STRESS_REMAINING_BOUND (content retries) | 29.035834 |
| AVAILABLE_R02 | 6.129989 |
| FITS_BASE | false |
| FITS_STRESS | false |

The cap was not increased. Most of the base bound is the novelty worst case (USD 11.349800), then red team (USD 3.011660), feasibility (USD 0.155579) and the selector (USD 0.001756).

Combined lineage if this continuation later spends only its remaining authorization: r01 USD 2.210772 + r02 cap USD 9.789228 = USD 12.000000. Spending past the r02 cap is not authorized.

Protected 2025/2026 was not opened. No market outcome was tested. The memory finalizer was not run.
