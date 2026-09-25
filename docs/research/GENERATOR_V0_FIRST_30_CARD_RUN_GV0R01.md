# Generator V0 first 30-card run — GV0R01

**Status:** `PENDING_HUMAN_REVIEW` (campaign complete; memory finalized)
**Date:** 2026-09-24 (run), 2026-09-25 (seal and memory finalization)
**Machine-readable twin:** `docs/research/GENERATOR_V0_FIRST_30_CARD_RUN_GV0R01.json`
**Sealed journal:** `docs/research/generator_v0_gv0r01/run.sqlite`
**Journal SHA256:** `de22f7c2aeb0487842a2477e5a2f44e3df7a9cbf007785cfaf213cbcd648be62`

This is the first real Generator V0 campaign. It generated and governed 30 hypothesis cards. It did not test any hypothesis against market data. The critic verdicts, streams and shortlist are outcome-blind triage. They are not evidence of a market effect, profitability or a validated edge. Protected 2025/2026 data stayed unopened.

## Source and execution

- Source: `claude/signalbot-cost-calibration-hgv3yu` at HEAD `2412a372b5212def2256b1662b5d45f16a91f515`, tree `c9e120ff03572ac7da7181e7a1c0a96fa00da44d`.
- Entry point: `python -m scripts.research.generator_v0 first-30-card --budget-usd 10.00 --accept-budget-stop --actor owner`.
- Hard campaign cap: USD 10.00. The conservative size-30 bound (USD 19.516751) did not fit, so the owner accepted a clean `STOPPED_BUDGET` in advance. The stop was not needed.
- Routes are the frozen first 30-card architecture:
  - GENERATOR: Opus, effort high, 3 × 10 cards, one POST per round;
  - NOVELTY_CRITIC: Sol, high, background;
  - FEASIBILITY_CRITIC: Luna, low;
  - RED_TEAM: Sol, high, background;
  - SELECTOR: deterministic ordinal order only.
- OpenAI network mode: `CLOUD_PROXY`.
- Memory head at run time: `358f06d4e2d1f7d1657c89544fc702d7dffe7bf6c1ec920ceab4228f7a50c3ad` (GV0CAL).

## Calls and spend

| Item | Value |
|---|---|
| Logical calls | 93, all `COMPLETE`; unresolved 0 |
| Generator POSTs | 3 (no retry) |
| Novelty / feasibility / red team | 30 / 30 / 30 |
| Critic content retries | 0 |
| Selector LLM calls | 0 (`NOT_CALLED`) |
| Total spend | USD 5.091486 |
| Anthropic (generator) | USD 2.836676 |
| OpenAI (critics) | USD 2.254810 (novelty 1.719060, red team 0.518480, feasibility 0.017270) |
| Remaining under cap | USD 4.908514 |

| Round | Call key | Cost (USD) | Output / thinking tokens | raw_sha256 |
|---|---|---|---|---|
| generation:0 | `c614d97c…6c6814a911` | 0.904556 | 42017 / 16027 | `4243aa2e…5b3bbb` |
| generation:1 | `a6fa912f…a978f08b619a` | 0.955064 | 44540 / 21941 | `620b7700…fe7a31b6` |
| generation:2 | `ed8e912e…a6045b8c0c` | 0.977056 | 45608 / 22044 | `5febfbcc…c60481` |

Full keys and hashes are in the JSON twin.

## Result

- Slots 30, valid 30, hard fails 0, reviewed 30, review failures 0.
- Stream A (`EXECUTABLE_NOW`): C013.
- Stream B (`HIGH_VALUE_DATA_BLOCKED`): C004, C006, C012, C014, C016, C020.
- The other 23 cards are in neither stream.
- Deterministic shortlist: C013, C014, C006, C012, C016. Candidates are sorted by mechanism distance, then information gain, then feasibility, then cheapness (each descending), with ties broken by candidate ID.
- Semantic result digest: `b9ca7a3d4fe1f11d1f40d8b9839bfa68474e25c81bff83ffc148a2a2ba81fcf6`.

## Seal and archive

The journal was sealed with the existing `Ledger.seal()`. The seal records actor `owner`, `OPEN_CALLS = 0`, a WAL checkpoint with truncate, and journal mode `DELETE`. Before sealing, the file SHA256 was `841840cc…ccd9264`. The sealed file was copied byte for byte to the tracked path above. It is registered by hash in `GENERATOR_V0_SEALED_RUNS.json`, and the operator refuses to open it for writing at any path. Sealing did not change the campaign result or the finalizer source SHA.

## Memory finalization

Memory was finalized with Memory Finalizer V1 from the tracked sealed journal. The source SHA256 is `f5992fff8219a2d6736c99de5ee5e6ae653044299a752fe3a0192c34a44a8579`.

- Event `416b22fabd1663be9094bce18c5bce2a8b3d062b0b01525a25395d195788bead` (sequence 2), with delta `63bfdb6f40278ef83d8f31cdc2122907999da0a5f132504d1051d5c0f3abe85c`.
- Previous head: GV0CAL `358f06d4…`.
- Attempt records: 30.
- New canonical signatures: 22. Of these, 1 is `CONSUMED` (GV0R01-C013) and 21 are `DEFERRED_OR_BLOCKED` with deterministic blocker classes.
- Links to prior signatures: 4 (C001 and C011 → D2, C009 → D6 as a blocker-resolution proposal, C019 → D6 and MARKET-03). These attempts get no new signature.
- Links to batch signatures: 4 (C023 → C007, C024 → C017, C027 → C003, C028 → C020).
- Resulting memory: 57 entries, 35 attempt records. The chain `LEGACY_BOOTSTRAP → GV0CAL → GV0R01` verifies.

The generator's blind map shows every signature, including GV0R01-C013, as an outcome-neutral `PRIOR_WORK_SIGNATURE`. It exposes no critic verdict, stream, shortlist membership, governance state or market outcome.

## Scientific boundary

`MARKET_OUTCOMES_TESTED = false`. `HYPOTHESES_EXECUTED = false`. `PROTECTED_2025_2026_OPENED = false`.

C013 is the only current GV0R01 `EXECUTABLE_NOW` research candidate after generator and critic governance. Its market outcome is completely untested. The other signatures are durable prior work, and they must not be regenerated with cosmetic changes.
