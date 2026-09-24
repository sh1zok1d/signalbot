# Generator V0 — first 30-card architecture freeze

**Status:** `ACTIVE / CANONICAL`  
**Date:** 2026-09-24  
**Base HEAD:** `df0fccf13c1babadb7ccc4da46c6d9d524101c4e`  
**Base TREE:** `78c20b03da337f641a8fa93c8e232d40778e236d`

`ARCHITECTURE_FROZEN_FOR_FIRST_30_CARD_RUN = true`

This freeze closes the transport/routing repair cycle for the first real Generator V0 campaign. It is an operational architecture freeze, not a scientific result and not an authorization to open protected outcomes.

## Frozen routes

| Role | Provider/model | Effort | Transport |
|---|---|---:|---|
| GENERATOR | Anthropic `claude-opus-5-5` | high | normal Anthropic request, 10 cards/round, max output 100000 |
| NOVELTY_CRITIC | OpenAI `gpt-6-sol` | high | background Responses: create once, GET polling |
| FEASIBILITY_CRITIC | OpenAI `gpt-6-luna` | low | synchronous Chat Completions |
| RED_TEAM | OpenAI `gpt-6-sol` | high | background Responses: create once, GET polling |
| SELECTOR | deterministic code | n/a | no selector LLM call |

For cloud agents, OpenAI uses the canonical runtime adapter in `scripts/research/generator_v0/cloud_openai_transport.py`, which reads the current `HTTPS_PROXY` dynamically and removes `Authorization` only at the sandbox proxy boundary. Request construction, schemas, model/effort, parsing, accounting, call identity and exactly-once state remain production responsibilities.

## Live evidence before freeze

- Anthropic compact GENERATOR accepted live; the 100000 output cap completed a 10-card round.
- Two successful production-shaped generator samples cost USD 0.937152 and USD 0.892012.
- Background NOVELTY completed live and passed strict schema/application validation.
- Background RED_TEAM completed live and passed strict schema/application validation.
- FEASIBILITY Luna completed live.
- Five-card critic calibration completed all final critic chains with no unresolved calls in the completed continuation journal.

The calibration has **no scientific status**.

## Calibration cost observations

Successful-call observations only:

- generator sample 1 / 10 cards: USD 0.937152;
- generator sample 2 / 10 cards: USD 0.892012;
- generator mean / 10 cards: USD 0.914582;
- novelty mean / card: USD 0.031955;
- feasibility mean / card: USD 0.000507;
- background red-team mean / card: USD 0.014777;
- complete critic-chain mean / card: USD 0.047239;
- critic-chain min / median / max: USD 0.043931 / 0.046675 / 0.053037.

Historical transport failures, UNKNOWN reconciliation charges, and synthetic smoke costs are development spend and are excluded from the successful-run estimate.

## First campaign size

`FIRST_FULL_RUN_SIZE = 30`

The first campaign uses exactly three 10-card generator rounds. This run size was chosen because 40 cards do not fit the current Anthropic balance with a reasonable margin, while 30 cards do based on observed generator spend.

Observed 30-card projection:

- Anthropic generator mean: USD 2.743746;
- OpenAI critics mean from five-card calibration: USD 1.417164;
- selector: USD 0;
- total mean: USD 4.160910;
- max-observed projection: USD 4.402566.

The OpenAI novelty estimate from a five-card batch is not treated as an upper bound for a 30-card batch; the real 30-card novelty context is larger. Provider-specific run caps must therefore be checked again immediately before execution.

## Generator budget rule

The first 30-card run permits:
- exactly three planned generator rounds;
- at most three generator POSTs;
- no generator retry;
- fail closed if a generator round fails, becomes uncertain, or cannot fit the authorized Anthropic spend.

Do not spend a fourth generator call merely to rescue the first campaign.

## Freeze boundary

Before the first 30-card run, do not change:
- provider/model assignment;
- reasoning effort;
- generator round size;
- generator output cap;
- novelty transport;
- feasibility transport;
- red-team transport;
- critic prompts/schemas;
- deterministic selector authority;
- exactly-once semantics.

Do not add precautionary smoke/calibration cycles after this freeze. Reopen the design only for a concrete defect observed in execution or an explicit owner amendment.

## Scientific boundary

`NO_SCIENTIFIC_STATUS = true` for all smoke/calibration evidence used to reach this freeze.

Protected 2025/2026 remain unopened. The first 30-card Generator V0 campaign is a hypothesis-generation/governance run, not proof of a trading edge.

Operational rules: `docs/AGENT_RUNTIME_PROTOCOL.md`.
