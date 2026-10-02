# Generator V0 ladder-40 V03 r01 — paused, then frozen as an infrastructure failure

**Status:** `INFRASTRUCTURE_FAILED_FROZEN` (journal status stays `PAUSED_UNCERTAIN_CALL`)
**Date:** 2026-10-02
**Code HEAD:** `f00a014581426c85148cb841c4fab0f7e331915e`
**Journal snapshot:** `docs/research/generator_v0_ladder40_v03_r01/run.sqlite`
**Journal SHA256:** `72b7aaa774dfbf62c6caa3303eb40ae1c380b3e6bb0ace1f95e015953391be0b`

## Owner decision (2026-10-02, after this record was written)

r01 is frozen as a technically failed run. It is not a campaign result and is not continued.

- **Not UNKNOWN, not replay.**
  - The uncertain call is not reconciled `UNKNOWN`.
  - The create is never replayed.
  - The run is never resumed. The code after `ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1` also refuses to resume it, because its run config holds the synchronous routing digest.
- **Billing is bookkeeping, not a blocker.**
  - When the Anthropic console shows the exact cost of this request, it is recorded with the offline `reconcile --resolution BILLED`, with the cost and that evidence.
  - Until then the USD 2.210772 reservation stays charged in this journal only.
- **The cause is the transport.** A synchronous Messages call with no early provider id is fixed once by `GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.md`.
- **The next unit is r02**, a clean repeat of this technically failed campaign with the identical V03 design. It needs a fresh owner live authorization.

The "What is not authorized" section below records the state before this decision. Its next unit (reconcile, then resume r01) is superseded.

## Original pause record

This is the owner-authorized fresh `GENERATOR_CONTRACT_V03` 40-card shadow campaign. It stopped on the first generator call. It did not produce cards, critic judgments, or a shortlist. It did not test a market hypothesis. Protected 2025/2026 data stayed unopened.

## Execution

- Entry point: `python3.11 -m scripts.research.generator_v0 ladder-40-card --allow-real-llm --budget-usd 12 --accept-budget-stop --actor owner --openai-network-mode DIRECT --run-dir artifacts/generator_v0/ladder-40-card-v03-r01`
- Absolute cap: USD 12.00. Worst case did not fit, so budget-stop acceptance was recorded before the first POST.
- Routes were the frozen V03 table. OpenAI network mode was `DIRECT`.
- Offline preflight: `PREFLIGHT_PASS`. No smoke and no calibration call.

## The open call

| Field | Value |
|---|---|
| Role | GENERATOR, slot `generation:0` |
| Provider / model | Anthropic `claude-opus-5-5`, effort high |
| State | `UNCERTAIN` |
| Error | `TimeoutError` |
| Call key | `ae215fdf93381475470783cc79bb51e96f3902bc1b126abea12aedb42ca32304` |
| Response id | none |
| Reserved | USD 2.210772 |
| Recorded cost | none |

The create was marked `DISPATCHED` before the POST. The synchronous Messages connection stayed open until the frozen 1800-second client timeout. No response bytes and no message id were stored. Billing is unresolved. The reservation stays charged against the USD 12 cap.

No later call was sent. OpenAI POSTs: 0. Retries: 0. Candidates: 0.

## What is not authorized

- Do not replay this create.
- Do not start a new campaign or a new run directory.
- Do not change contract, prompts, schemas, models, routing, caps, or budget-stop semantics to get a different answer.
- Do not finalize memory. The finalizer requires a completed campaign.
- Do not seal this journal. Sealing would block the existing reconcile path.
- A later continuation, if the owner authorizes it, is a reconcile of this call and then a resume of this same run.

The tracked sqlite is a consistent snapshot of the paused journal. It is not a sealed archive.
