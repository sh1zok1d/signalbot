# Generator V0 — complexity ladder amendment (`GENERATOR_CONTRACT_V03`)

**Status:** `IMPLEMENTED`, offline only
**Date:** 2026-10-02
**Authority:** owner decision 2026-10-02 (complexity ladder; slot mix 16/14/7/3; shortlist 2/2/1; class assigned before the LLM call)
**Record:** `GENERATOR_V0_COMPLEXITY_LADDER_AMENDMENT.json`, which holds the digests
**Code:**
- `scripts/research/generator_v0/contract_v03.py` (new);
- `complexity.py` (from the V1 mapping);
- hooks in `schema.py`, `output_schemas.py`, `roles.py`, `runner.py`, `derive.py`, `mock.py` and `__main__.py`.

**Tests:** `tests/research/test_generator_v0_ladder_v03.py`

```
GENERATOR_CONTRACT_V03         = IMPLEMENTED
V02_BYTE_IDENTICAL             = true   (schemas, prompts, digests, mock campaign result)
LLM_CALLS                      = 0
MARKET_OUTCOMES_OPENED         = false
NEXT_UNIT                      = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (paid; owner budget, roles and call counts required)
```

## What changes

The generator goes from simple to complex. The model no longer decides how complex a card is; the rung is set by the system.

**Slot-assigned rung.**
- Each of the 40 slots carries a `COMPLEXITY_CLASS`, assigned deterministically before any LLM call. The model copies it exactly.
- The provider schema pins it to a one-value enum, and intake rejects a card whose rung differs from its slot.
- The mix is set by the owner: 16 `ATOMIC`, 14 `CONDITIONAL`, 7 `INTERACTION`, 3 `COMPOSITE`.
- Every round has 4 atomic slots. The rows are permuted so that each mechanism-family position meets different rungs across rounds.

**Why this mix.** The library of tested simple mechanisms matters most for now. Complex and composite cards should not take a disproportionate share of paid generation for one shortlist seat.

**Card contract V03 = the V02 card plus two fields.**

| Field | Rule |
|---|---|
| `COMPLEXITY_CLASS` | copied from the slot (`SLOT_IDENTITY`) |
| `COMPONENTS` | distinct component names of at most 200 characters: none for `ATOMIC` and `CONDITIONAL`, 2 for `INTERACTION`, 3–5 for `COMPOSITE` |

**Every V02 rule still applies**, including all safety rules on the new fields. Four rules are new:

| Rule | Enforced by | Content |
|---|---|---|
| `COMPONENTS` | intake | the counts above, distinct, nonempty |
| `MAIN_EFFECT_BASELINE` | intake | an interaction or composite `BASELINE_OR_NULL` names every component, so each main effect is controlled |
| `COMPLEXITY_RUNG` | red team (`RUNG_CONSISTENT`) | the card fits its rung; otherwise it does not pass review |
| `SIMPLE_IS_NOT_BANAL` | novelty critic | an indicator threshold or transform mapped to a later outcome is scored low on novelty and mechanism distance |

**Interaction and composite claims are about control, not prior support.** The main effects are in the baseline, and the joint term is the claim. The components need not have effects of their own: A ≈ 0, B ≈ 0 and A × B ≠ 0 is valid.

**Critics.**
- The novelty and red-team prompts gain the ladder text for V03 cards only.
- The red-team schema gains `RUNG_CONSISTENT` for V03 cards only.
- The ladder definitions travel in the prompt and the card, never in the critic context: the frozen `ROLE_CONTEXT_MATRIX` is unchanged.
- The V03 generator prompt passes the generator outcome-leak scanner. One word was reworded for that ("fails review" instead of a denylisted word).

**Shortlist.**
- The quota is 2 `ATOMIC`, 2 `CONDITIONAL` and 1 complex (`INTERACTION` or `COMPOSITE`), drawn from the existing deterministic ordinal order.
- An unfilled seat passes down the ladder, never up.
- The result carries `SHORTLIST_RULE` with each seat and its class.

## Versioning: V02 is untouched

**V03 applies only to ladder slots and ladder cards.** The run config field `GENERATOR_CONTRACT = GENERATOR_CONTRACT_V03` selects the ladder plan. Without it, which is the case for every existing run, the campaign is V02.

**V02 identity is unchanged**, checked against `origin/main`:
- the generator schema digest;
- the Anthropic compact schema digest;
- the generator, novelty and red-team prompt hashes;
- the critic schemas;
- the per-round generator identity;
- a full V02 mock campaign's `SEMANTIC_RESULT_DIGEST`, `cc6a5179…`, which is equal on both.

**Unchanged:**
- `HYPOTHESIS_GENERATOR_V0_DESIGN.json`, the context pins and the memory chain;
- `contract.py` (V02);
- routing, models, effort and output caps;
- the `first-30-card` command (V02 only).

## Entry point

```
python -m scripts.research.generator_v0 ladder-40-card --allow-real-llm --budget-usd <cap> \
  [--accept-budget-stop --actor owner --reason "<why>"] --run-dir <dir>
```

- `--allow-real-llm` and a nonzero budget are required.
- The cap may not exceed the owner ceiling in code (USD 17.10).
- Offline preflight, with no calls: `preflight --provider routed --contract V03`.

## Known limitations (fail closed)

- **Derive.** Carry-forward refuses V03 runs. A paused V03 run resumes in place.
- **Resume.** Resuming a V03 run needs `--contract V03`: the run config must be identical.
- **Memory.** `memory_finalizer` refused V03 campaigns at this amendment. **Resolved in `GENERATOR_V0_PRE_CAMPAIGN_HARDENING.md`**, which also freezes the V03 budget-stop semantics (`INCOMPLETE_BUDGET_STOP`).
- **Not mechanical.** "Simplicity is not banality" is a critic judgment.

## Acceptance (no LLM, no market data)

- **Slot plan.**
  - The mix is exactly 16/14/7/3, with 4 atomic slots per round; it is deterministic, and its V02 fields equal the V02 plan.
  - The mix check refuses a mutated plan; the plan refuses any size other than 40.
  - Family positions meet several rungs.
- **The model never chooses its rung.** The provider schema pins the rung, and a changed rung fails the schema and `SLOT_IDENTITY`. The compact wire offers only the round's rungs, and mixed V02/V03 rounds are refused.
- **Rule table.** The rules, prompt and checks agree: every intake rule has a check, and every critic rule is mapped. The V03 prompt passes the scanner.
- **Fixture cards.** All 40 fixture cards are valid V03 cards.
- **Card rules.** Component counts per rung, distinctness and length, the main-effect baseline, and all V02 safety rules hold on V03 cards.
- **Critics.** V03 prompts and schemas are used for ladder cards only. A false `RUNG_CONSISTENT` rejects the card, and a missing one is a contract error.
- **Mock campaign.**
  - 40 valid cards, 125 calls, 4 generator calls at `generator-v0.3`.
  - The shortlist seats are 2/2/1, and the result is reproducible.
  - When the red team rejects every complex card, the complex seat falls to a conditional card.
- **V02 campaigns are unchanged.**
- **Budget, derive and CLI.**
  - The offline budget bound works for V03.
  - Derive refuses a V03 source.
  - The CLI ladder command needs live authorization, and V03 needs 40 slots.
