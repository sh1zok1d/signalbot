# GENERATOR_CONTRACT_V04 — Atlas routing (design only)

**Status:** `DESIGN_ONLY / NOT_ACTIVE` (2026-10-03).
- **Not implemented.** No generator code, prompt, role matrix, memory chain or finalizer is changed.
- **V0 stays active.** The frozen Generator V0 implementation and `GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.md` remain the operational authority until an owner decision activates V04.

**Machine-readable twin:** `GENERATOR_CONTRACT_V04_ATLAS_ROUTING_DESIGN.json` (packet and card fields).

## 1. Routing rule

1. **The atlas selects the cell, the generator does not.** A deterministic selector (no LLM) picks exactly one cell from `SIGNALBOT_RESEARCH_ATLAS_V1`. The generator cannot choose, widen or switch it; a card naming any other cell is rejected before any critic runs.
2. **FRONTIER lane (default).**
   - The selector takes the highest-value `OPEN_FRONTIER` cell. The cell must be in the frontier, have `data_readiness > 0`, and sit in a region the owner's go names.
   - Ties are broken by the atlas order: owner priority, product relevance, data readiness, then row and column.
3. **REOPEN lane (only by recorded decision).** A cell with prior work is routed only when the selector records one reopen key with its evidence:
   - `NEW_MECHANISM`, `NEW_SURFACE` or `NEW_CONFIRMATION_SURFACE`;
   - `RECORDED_REOPEN_CONDITION`, the unit's own recorded condition, met with the record that shows it.

   `BLOCKER_RESOLVED`, `NEW_INDEPENDENT_UNITS`, `PROSPECTIVE_DATA` and `OWNER_DECISION` are recorded the same way. The generator never proposes a reopen.
4. **Closed cells are never reopened by parameter.** A threshold, percentile, horizon, lookback, window, clock, lag or other nearby parameter of a prior signature is `PARAMETER_NEIGHBOR`. That is forbidden in every lane and is not a reopen key.

## 2. What the generator receives (the V04 packet)

The packet is built only from `ATLAS_GENERATOR_VIEW_V1.json` and the selection record; the full governance view is never an input.

| Field | Content |
|---|---|
| `atlas` | atlas version, sources digest, head event hash of `ATLAS_EVENTS_V1.jsonl` |
| `lane` | `FRONTIER` or `REOPEN` |
| `cell` | row, column, row name, region, native layer, and whether the cell is native or native plus an added layer |
| `row_context` | the row's applicable columns and the blind prior signatures of the whole row (mechanism and function only) |
| `allowed_surfaces` | datasets that serve the cell's native and added layers, are available, and are not wholly reserved; each with coverage, availability and `unavailable_periods` |
| `reopen_conditions` | FRONTIER: the forbidden-move list relative to the row's prior signatures. REOPEN: the recorded key plus a selector-written, outcome-neutral statement of what must be new. The unit's own reopen text stays in the full view, because it may carry outcome detail. |
| `restrictions` | reserved and protected periods (the E1-RUN-001 holdout today), plus the rule that exposed surfaces cannot serve as confirmation |
| `rules` | the generator-view rules: OPEN, PRIOR_WORK, DATA_REQUIRED, UNDERPOWERED_NOW, UNAVAILABLE_PERIODS, BLINDNESS |

The packet carries no state names beyond those four generator states, no verdict, effect size, direction, pass/fail word or number from any result. The frozen scrub of `memory_finalizer.scrub` applies to every text. The atlas flip test is extended to packets: flipping outcome labels leaves the packet byte-identical.

## 3. What a V04 card must add

Each card adds these fields to the V0 card:
- **`atlas_cell`:** must equal the selected cell.
- **`lane`.**
- **Layers:** the native layer and, if any, the added layer.
- **`novelty_relation`:** none for an empty row, otherwise `ORTHOGONAL_MECHANISM`, `NEW_SURFACE` or `RESOLVES_BLOCKER`, stated against the named prior signatures.
- **`reopen_key`:** REOPEN lane only, and equal to the recorded key.
- **`datasets`:** a subset of `allowed_surfaces`.
- **`confirmation_plan`:** a time-disjoint or prospective surface. It must not be exposed for the row, and must not be reserved unless a permit names the card.

## 4. Admission (before any LLM critic)

A card is rejected deterministically if any of the following holds:
1. Its cell differs from the selection.
2. A dataset is outside `allowed_surfaces`, or a used period meets an `unavailable_periods` entry.
3. It is a `PARAMETER_NEIGHBOR`, `FUNCTIONAL_RELABEL`, `EXACT_DUPLICATE` or `OBSERVABLE_SUBSTITUTION` of a prior signature in the row. Signature comparison comes first and the novelty critic confirms.
4. It composes consumed components (`COMPOSITION_OF_CONSUMED`), or plans confirmation on an exposed or reserved surface (`CONFIRMATION_ON_EXPOSED`).
5. In the REOPEN lane, its stated novelty does not match the recorded reopen key.

Survivors then go through the existing V0 critics, feasibility (GV0R02/GV0R03), freeze and execution rules. V04 changes routing and admission only.

## 5. After a batch

Each closed or blocked card becomes an atlas unit in the same change, with its exposure added to the surfaces it read. The builder is rerun, and an `ATLAS_EVENTS_V1.jsonl` event is appended. A card that never reached outcomes is recorded with an outcome-neutral state: `CANDIDATE_UNTESTED`, `BLOCKED_*`, `INFORMATIONALLY_WEAK` or `CLOSED_BEFORE_START`.

## 6. Activation checklist (owner decision required)

1. Owner decision to activate V04, recorded with its date.
2. Implement the packet builder and admission checks in the generator code, with tests:
   - the blind packet flip test;
   - rejection of every forbidden move on fixtures;
   - the cell-mismatch reject;
   - the reserved-period reject.
3. Amend the Generator V0 architecture freeze (or supersede it) and the role matrix to name the packet as the generator's only atlas input.
4. Dry run with a mock provider and no market data. Then the first batch, under its own owner go.
