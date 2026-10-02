# Generator feasibility contract — V1 mapping

**Status:** `IMPLEMENTED`
**Date:** 2026-10-02
**Version:** `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1`, which emits `GV0R02_SCHEMA_V1` / `GV0R02_POLICY_V1` proposals under `HYPOTHESIS_EVALUATION_CONTRACT_V1`
**Code:** `scripts/research/generator_v0/feasibility_contract_v1.py`
**Tests:** `tests/research/test_gv0r03_generator_feasibility_contract_v1.py`

```
V0_PLANNING_CONTRACT_CHANGED   = false
GENERATOR_CARD_SCHEMA_CHANGED  = false   (GENERATOR_CONTRACT_V02, CANDIDATE_SCHEMA_FROZEN = true)
GENERATOR_PROMPT_CHANGED       = false
COMPILER_CHANGED               = false
LLM_CALLS                      = 0
MARKET_OUTCOMES_OPENED         = false
NEXT_UNIT                      = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN (owner budget decision required)
```

## Decision: V1 lives on the planning object, not on the card

The V1 declarations belong to the planning object built when a shortlisted card is designed. The generator card does not emit them. The declarations are:
- claim type and target class;
- variable roles and nuisance baseline;
- 1–3 primary cells;
- practical-bar basis;
- discovery and replication surfaces;
- epochs.

**Why:**
- **They are design-freeze decisions.** V1 places them in the twin preregistration. A brainstorm card cannot fix surfaces, primary cells or a stopping rule honestly, and an LLM-filled value would look like a commitment it is not.
- **The card schema is frozen.** `HYPOTHESIS_GENERATOR_V0_DESIGN.json` has `CANDIDATE_SCHEMA_FROZEN = true`. The first-campaign architecture freeze reopens the design only for an observed defect or an explicit owner amendment. Adding fields would make a `V03` card contract (the code is `GENERATOR_CONTRACT_V02`), with new provider schemas, prompt rules, quarantine checks and memory-finalizer fields.
- **The card already carries the seeds.** Every V1 decision has a source field on the card, mapped in the table below.

**Alternative not taken.** A `GENERATOR_CONTRACT_V03` card with V1 hints is possible, but it needs a separate owner decision and an amendment to the first-campaign architecture freeze.

## What the V1 planning contract does

It is the V0 planning object (unchanged, re-validated) plus the V1 fields. It **checks shape only**:
- **Required fields.** Every V1 field is present; `INTRADAY` must be boolean.
- **Value sets.** `CLAIM_TYPE`, `TARGET_CLASS` and `PRACTICAL_BAR_BASIS` take values from the V1 sets.
- **`VARIABLE_ROLES`.** Exactly the three role lists.
- **`PRIMARY_CELLS`.** 1 to 3 cells, each with exactly `REGIME`, `ESTIMAND` and `HORIZON`.
- **`EPOCHS`.** `CALENDAR_YEAR`, or a declared list of at least 3 epochs.
- **Surfaces follow the frozen V0 era roles:**
  - discovery lies inside `BINANCE_2020_2024`; historical replication lies inside `BITMEX_2016_2019`;
  - boundaries fall on months;
  - the discovery surface must equal the V0 `HISTORICAL_WINDOW` and the counting window, so the three cannot drift apart.
- **Replication surface shape.** A historical replication carries an outcome-blind nominal count. A prospective replication carries `START`, `STARTS_AFTER_FREEZE` and a `STOPPING_RULE` object.
- **Optional outcome-blind `DECLARED_COUNT_BY_YEAR`.** It is copied into `OUTCOME_BLIND_SAMPLE.COUNT_BY_YEAR`, so the compiler can record heterogeneity assessability. Without it the record is `NOT_ASSESSABLE`, which is never a blocker.
- **No outcome keys** anywhere, including inside V1 fields.

**The compiler stays the single adjudicator of the V1 rules.** It judges:
- a context claim on a directional endpoint;
- a missing standard nuisance without a written argument;
- the practical-bar basis;
- regime versus target class;
- time-disjointness;
- the stopping-rule content;
- a prospective start inside the protected window.

A well-shaped but inconsistent declaration passes the contract and comes back from the compiler as `DEFINITION_INCOMPLETE` or `DATA_BLOCKED` with its blocker code. The rules are not duplicated, so they cannot drift.

**Sealed.** The V0 sealed fields plus every V1 field and the nuisance exclusions are sealed. `reject_downstream_edit_v1` refuses any silent rewrite. A compiler blocker is answered by a new, recorded design version, never by editing the sealed object.

## Crosswalk: card field → planning field

The conversion is done once per shortlisted card, outcome-blind, and sealed before the compiler runs. The card text is not modified. "Decided at design freeze" means the card only seeds the field and the designer commits to it.

| V1 planning field | Seeded by card field(s) | Rule |
|---|---|---|
| `CLAIM_TYPE` | `FUNCTION`, `PRIMARY_TARGET` | Non-directional context (volatility, participation, regime description) → `CONTEXT_DESCRIPTIVE`. A claim of value beyond a baseline → `INCREMENTAL`. Decided at design freeze. |
| `TARGET_CLASS` | `FUNCTION` | A claim that holds only inside a named state → `CONDITIONAL`, with the state as a regime variable. Otherwise `UNCONDITIONAL`. |
| `VARIABLE_ROLES.MECHANISM_VARIABLES` | `OBSERVABLE`, `MECHANISM`, `INFORMATION_SOURCE` | The variables the mechanism says carry the effect. Never also a nuisance variable. |
| `VARIABLE_ROLES.NUISANCE_BASELINE_VARIABLES` | `MAIN_CONFOUNDERS`, `BASELINE_OR_NULL` | Always `PRIOR_REALIZED_VOLATILITY` and `LAGGED_TARGET`, plus `TIME_OF_DAY` if intraday, plus the card's named confounders. |
| `VARIABLE_ROLES.REGIME_VARIABLES` | `FUNCTION` | Only for conditional claims. |
| `NUISANCE_EXCLUSIONS` | `CAUSAL_OR_STRUCTURAL_STORY`, `MECHANISM_DISTANCE_ARGUMENT` | Only with a written mechanism argument for why conditioning on that nuisance would remove the mechanism itself. |
| `INTRADAY` | `HORIZON` | `true` for any horizon under one day. |
| `PRIMARY_CELLS` (1–3) | `PRIMARY_TARGET` × `HORIZON`; `SEARCH_SURFACE` | At most 3 declared cells. The rest of the card's search surface (up to 100 variants) becomes secondary or diagnostic, never primary. Holm runs over the declared cells. |
| `PRACTICAL_BAR_BASIS` | follows `CLAIM_TYPE` and the endpoint | Context → `PRODUCT_RELEVANCE`; directional `INCREMENTAL` → `COSTS`. |
| `DISCOVERY_SURFACE` | `DATA_REQUIRED` `LEGAL_RANGE` | The intersection with the `BINANCE_2020_2024` discovery era. |
| `REPLICATION_SURFACE` | `DATA_REQUIRED`, `DATA_GAP_CLASS` | Either historical inside `BITMEX_2016_2019`, with an outcome-blind count, or prospective, with a stopping rule (amendment A1). Prospective starts before 2027-01-01 hit the protected window: an owner decision. |
| `EPOCHS` | — | `CALENDAR_YEAR` unless the design declares otherwise. |
| V0: `MECHANISM`, `FALSIFIABLE_CLAIM`, `COUNTERFACTUAL_CLASS`, `EVENT_OR_STATE_DEFINITION`, `PRIMARY_OBSERVABLE` | `MECHANISM`, `FALSIFIER`, `BASELINE_OR_NULL`, `FUNCTION`, `OBSERVABLE` | Copied in meaning, then sealed. |

## Acceptance (tests, no LLM, no market data)

- A synthetic V1 planning object maps without interpretation and compiles to `FEASIBLE_FOR_PREREGISTRATION`. The heterogeneity record carries `NOT_EVIDENCE_OF_STABILITY`.
- The V0 contract and its `GV0R02_SCHEMA_V0` mapping are unchanged, and a V0 object is refused by the V1 contract.
- Each omitted V1 field and each shape violation is refused, and so are wrong-era or drifting surfaces and out-of-surface yearly counts.
- An outcome key inside a V1 field is refused.
- The compiler, not the contract, blocks:
  - a directional context claim;
  - a missing standard nuisance;
  - a conditional claim without a regime;
  - a prospective replication starting 2026-11 (`DATA_BLOCKED`, `PROTECTED_SURFACE_DECISION_REQUIRED`).
- A downstream rewrite of any V1 design field is refused.
- The generator card schema is still frozen and carries no V1 field.

## Next unit

`GENERATOR_V0_FRESH_SHADOW_CAMPAIGN`: a fresh Generator V0 shadow campaign under a new run ID with a capped budget. It follows `docs/AGENT_RUNTIME_PROTOCOL.md` and the first-campaign architecture freeze, and it is a paid LLM run, so the owner sets the budget cap before it starts. Then:
1. a shortlist of at most 5;
2. a V1 planning object per shortlisted card, through this contract;
3. GV0R02 V1 compilation;
4. one or two preregistrations.
