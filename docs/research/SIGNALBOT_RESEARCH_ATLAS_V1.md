# SIGNALBOT_RESEARCH_ATLAS_V1

**Status:** ACTIVE — the permanent research map (2026-10-03). It replaces numbered generation campaigns (G01 → G02 → …) as the way research is chosen. It does not authorize execution: every batch still needs its own owner go under `PRODUCT_FIRST_DECISION_V1` §1 and `PRODUCT_DECISION_V2_DECISION_SUPPORT.md`. It does not override frozen experiment contracts, the evaluation contract, protected-data rules or sealed verdicts. Where it differs from a sealed record, the record wins and the atlas is corrected.

**Origin.** Owner proposal of 2026-10-03:
- one permanent map, Mechanism × Data surface × Research state, instead of campaign-by-campaign generation;
- a family is never reopened for a new threshold;
- a new branch is allowed only with a new mechanism or a new data surface.

This V1 transfers every past research unit onto that map. It also adds a few structural pieces, listed in §11.

## 1. What is on the map

| Item | Count | Source |
|---|---|---|
| Regions (mechanism groups) | 13 | `atlas/ATLAS_TAXONOMY_V1.yaml` |
| Rows (mechanisms) | 66 | taxonomy |
| Columns (data surfaces) | 10: CANDLES, PERP_FLOW, POSITIONING, LIQUIDATIONS, ORDER_BOOK, SPOT, CROSS_VENUE, CROSS_ASSET, OPTIONS, FLOWS_ONCHAIN | taxonomy |
| Applicable cells | 436 (a cell exists only where the mechanism can be observed, §2) | derived |
| Datasets / surfaces | 44, each with coverage, availability and an exposure ledger | `atlas/ATLAS_SURFACES_V1.yaml` |
| Research units | 145 | `atlas/ATLAS_UNITS_V1.yaml` |

**What the 145 units cover:**
- all 79 entries of `MECHANISM_MEMORY_V0.json`: H01–H05, B2-01..06, D1–D13, MARKET-01..06, and Generator V0 calibration, GV0R01 and GV0V03L40;
- OWNER_CARDS_R03 (12);
- AUTOGEN_G01 (14);
- the divergence / selling-exhaustion program (14);
- the Sprint 03/04 candidate pools;
- the SEED backlog;
- TWAP V1, E1-RUN-001 and V3;
- the product V2 statistics (marked as exposure);
- the K1 event-corridor track.

**Fail-closed coverage.**
- Every memory entry and every id in `config/beta_research_findings.yaml` must be on the map, by id or alias, or the build fails.
- Owner decisions and pure tooling are not units. They appear as records of the units they govern: the divergence owner decisions V1–V3, GV0R02/GV0R03 tooling and the campaign lineage.

## 2. Structure

**Cell = mechanism (row) × data surface (column).**
- Each row lists its applicable columns. The first is its **native** layer, the one that defines the mechanism.
- Any other applicable column means *the native layer plus that layer*. Example: liquidity withdrawal + OI is `MICROSTRUCTURE.liquidity_withdrawal × POSITIONING`.
- A combination where the mechanism cannot be observed does not exist. Order-book imbalance on candles alone is one such case.
- Calendars, release schedules and synthetic generators are **lenses**, not data columns: they say *when* something happens and sit under `LENS` in the surfaces file.

**Unit = one research object** (a tested hypothesis, a card, a seed, a frozen experiment) placed in exactly one cell. Every unit carries:
- what was tested (mechanism, function);
- data (datasets), period and independent units;
- the practical bar and the verdict with its own numbers;
- why it closed;
- what would reopen it;
- forbidden rescues;
- records (repository paths, checked to exist);
- a revisit trigger where one exists.

Memory units take these texts from the memory chain at build time. Later facts are added on top: records, aliases, a corrected state with a note.

**Cell state** = the first state, in the precedence order, present among the cell's units. The cell also keeps the count of every state, so a mixed cell is never reported as one state only (`*` in the matrix).

## 3. States

The owner's seven states, plus four that the transfer showed are needed (marked +).

| State | Meaning | Routing | Outcome-neutral |
|---|---|---|---|
| OPEN_FRONTIER | Nothing defined in this cell | Generation allowed (row anti-rescue still applies) | yes |
| + CANDIDATE_UNTESTED | A card/seed exists, no market outcome computed | Do not regenerate; may be selected for feasibility/freeze as is | yes |
| + BLOCKED_METHOD | Stopped by a method blocker (identification, confounding, lookahead, null model, red team) | A redesign must name and resolve the blocker | yes |
| BLOCKED_DATA | No permitted data (missing, unpinned, not legally timestamped, not collected) | Reopens when the surface becomes available | yes |
| INFORMATIONALLY_WEAK | Legitimate question, too few independent units (MDE above the bar) | Do not run now; no proxy or pooling to manufacture N | yes |
| FUTURE_NATURAL_ACCUMULATION | Weak now; testable when units accumulate | Revisit at the recorded trigger, nothing earlier | yes |
| EXPOSED_ONLY | Data looked at (descriptively, for the product, for feasibility, exploratorily) without a confirmatory test | Cannot confirm this mechanism; confirmation needs fresh data | no |
| + LIVE_SIGNAL | Discovery or replication result not yet confirmed | Only a pre-registered confirmation on a fresh surface | no |
| + CONFIRMED | Pre-registered confirmation on an independent surface passed | Do not re-confirm; product use under its own gate; new work only as a new mechanism/surface | no |
| NO_STRUCTURE | Tested under a frozen contract, no practically meaningful effect | Closed on this surface; reopen only with a new mechanism or surface | no |
| CLOSED_ON_SURFACE | Tested; the outcome is specific to the claim or surface (rejected claim, external reproduction, mixed) | Closed on this surface for this function | no |

Precedence: CONFIRMED > LIVE_SIGNAL > NO_STRUCTURE > CLOSED_ON_SURFACE > FUTURE_NATURAL_ACCUMULATION > INFORMATIONALLY_WEAK > BLOCKED_METHOD > BLOCKED_DATA > CANDIDATE_UNTESTED > EXPOSED_ONLY > OPEN_FRONTIER.

## 4. Two lenses

The generator role matrix (`docs/research/GENERATOR_V0_MEMORY_FINALIZER.md`) forbids outcomes in generator context, so the atlas is built in two views from the same sources:

| View | File | Readers | Carries |
|---|---|---|---|
| FULL_GOVERNANCE | `atlas/SIGNALBOT_RESEARCH_ATLAS_V1.json`, `atlas/ATLAS_MATRIX_V1.md` | owner, selector, red team, novelty critic | everything: states, verdicts, numbers, why closed, reopen, forbidden, exposure, frontier |
| GENERATOR_BLIND | `atlas/ATLAS_GENERATOR_VIEW_V1.json` | hypothesis generators | rows, applicable columns, surfaces (coverage, availability), per cell one of OPEN / PRIOR_WORK / DATA_REQUIRED / UNDERPOWERED_NOW, prior signatures (mechanism + function only), outcome-neutral frontier value |

**How the blind view is built.**
- Prior signatures of memory units come from `BLIND_MECHANISM_MAP_V0.json`.
- Other units contribute only their scrubbed mechanism and their short card name.
- A survivor and a closed card look the same.

**Guarantees, enforced by tests (`tests/research/test_research_atlas_v1.py`).**
- **No outcome words.** No outcome word, verdict key or effect number appears in the blind view.
- **Flip test.** Flipping every NO_STRUCTURE ↔ LIVE_SIGNAL and rewriting every verdict leaves the blind view byte-identical.

## 5. Reopening and forbidden moves

**A closed cell reopens only with one of these keys:**
- `NEW_MECHANISM`: orthogonal, not a relabel;
- `NEW_SURFACE`: a layer, venue or instrument the closed unit did not use, with its own preregistration;
- `NEW_INDEPENDENT_UNITS`: accumulated naturally to the recorded N;
- `BLOCKER_RESOLVED`;
- `PROSPECTIVE_DATA`: collected after a freeze;
- `OWNER_DECISION`.

**Forbidden moves:**
- `PARAMETER_NEIGHBOR`: threshold, window, horizon, clock or lag of the same function;
- `FUNCTIONAL_RELABEL`;
- `EXACT_DUPLICATE`;
- `OBSERVABLE_SUBSTITUTION`: a better proxy of the same thing;
- `SUBGROUP_MINING`;
- `REVERSE_EFFECT_RESCUE`;
- `COMPOSITION_OF_CONSUMED`;
- `CONFIRMATION_ON_EXPOSED`.

These keys and moves map onto the novelty relations already used by `GOVERNANCE_REGION_AUTHORITY_V0.json` (ORTHOGONAL_MECHANISM, RESOLVES_BLOCKER, PARAMETER_NEIGHBOR, FUNCTIONAL_RELABEL, EXACT_DUPLICATE). Example: "OI build-up + order-book liquidity withdrawal" is a legitimate new branch; "OI build-up with another percentile" is not.

## 6. Frontier value (outcome-neutral)

`value = product_relevance (row, 0-3) + data_readiness (cell, 0-3) + novelty (0/2/3) + confirmation_path (0-2) − saturation (0-3) + owner_priority (0-2)`

**data_readiness** is the best dataset of the column for the row:
- 3: pinned and pristine for the row;
- 2: pinned but exposed, or acquirable from a free public archive and pristine;
- 1: acquirable but exposed, or forward collection only;
- 0: none.

For a combined cell, data_readiness and confirmation_path are each the weaker of the column and the native layer. `needs` restricts a row's native layer to the datasets that can serve it: macro rows need macro series, dealer gamma needs option open interest by strike.

**novelty:**
- 3: the row is untouched;
- 2: the row is explored on other columns only;
- 0: the cell has prior work.

**saturation:** floor(prior units in the row / 3), capped at 3.

**owner_priority** is a dated taxonomy entry. It weights routing; it does not authorize work. As of 2026-10-03: MICROSTRUCTURE +2 and SPOT_PERP +2.

**Lists.**
- Open cells with data, ranked, form the FRONTIER.
- Open cells without usable data form FRONTIER_NEEDS_DATA. Each tells you which surface would open it.
- The METHOD region never enters the frontier.
- No input to the value depends on any outcome.

## 7. Batch protocol (the agent command)

> Choose the next OPEN_FRONTIER cell with the highest value. Do not return to a closed cell without a new mechanism or a new surface. Generate hypotheses, red-team them, check feasibility, freeze, and execute the survivors. Update the map after the batch.

The steps, each under the existing contracts:

1. **Owner go.** A batch starts only on an explicit owner go naming the cell(s). Current posture: research is small, feasibility-confirmed and product-serving.
2. **Select.**
   - The selector reads the FULL view and takes the highest-value frontier cell(s) in the authorized regions.
   - A non-native cell is worked together with its native layer.
   - It records the cell and its reopen key, if a closed cell is touched.
3. **Generate.** Generators read only the GENERATOR_BLIND view plus the selected cell(s). Each card declares its cell and, for PRIOR_WORK cells, its novelty relation.
4. **Red team / novelty critic.** The critic reads the FULL view (scoped) and the governance authority. It closes forbidden moves and checks surface exposure: a card may not use an exposed surface as its confirmation.
5. **Feasibility.** Outcome-blind, under `HYPOTHESIS_EVALUATION_CONTRACT_V1`, with GV0R02/GV0R03 where applicable. INFORMATIONALLY_WEAK and BLOCKED_* are valid stops.
6. **Freeze, then execute survivors.** Use the twin preregistration, at most 3 primary cells, Holm, and a time-disjoint or prospective replication.
7. **Update the map in the same change.**
   - Append each unit, with its verdict, why it closed, reopen key and records, to `ATLAS_UNITS_V1.yaml`.
   - Extend the exposure ledger of every surface read.
   - Run the builder and the tests.
   - Update the findings registry when a unit closes (AGENTS.md research ↔ bot rule).

## 8. Maintenance

- **Sources (hand-maintained):** `docs/research/atlas/ATLAS_TAXONOMY_V1.yaml`, `ATLAS_SURFACES_V1.yaml`, `ATLAS_UNITS_V1.yaml`.
- **Derived (never edit by hand):** `SIGNALBOT_RESEARCH_ATLAS_V1.json`, `ATLAS_GENERATOR_VIEW_V1.json`, `ATLAS_MATRIX_V1.md`. Rebuild with `python -m scripts.research.atlas.build_atlas`; `--check` fails when they are stale or a source is invalid.
- **Read-only inputs:**
  - `MECHANISM_MEMORY_V0.json`, `GOVERNANCE_REGION_AUTHORITY_V0.json` and `BLIND_MECHANISM_MAP_V0.json` are derived caches of the generator memory chain. The atlas never edits them, and Generator V0 memory is still ingested only through `finalize_memory`.
  - `config/beta_research_findings.yaml`.
- **Validation fails closed on:**
  - unknown rows, columns or datasets;
  - a unit in a cell where its mechanism cannot be observed;
  - missing why-closed, reopen or forbidden fields, or a missing revisit trigger;
  - a record path that does not exist;
  - a memory entry or findings id that is not on the map.
- **Post-memory facts.** When a sealed record changed a memory unit's status after the memory snapshot, the units file records the corrected state with the record that changed it. The memory entry itself is left untouched. On 2026-10-03 this applied to D7 (→ CONFIRMED) and GV0V03L40-C033 (→ BLOCKED_METHOD), and records were added to C004, C012, C013 and C020.

## 9. Snapshot 2026-10-03 (what the map shows)

**Units:**

| State | Units |
|---|---|
| BLOCKED_METHOD | 45 |
| INFORMATIONALLY_WEAK | 19 |
| BLOCKED_DATA | 18 |
| NO_STRUCTURE | 17 |
| CANDIDATE_UNTESTED | 16 |
| CLOSED_ON_SURFACE | 12 |
| EXPOSED_ONLY | 10 |
| LIVE_SIGNAL | 4 |
| FUTURE_NATURAL_ACCUMULATION | 3 |
| CONFIRMED | 1 |

**Cells:** 73 of 436 hold prior work. 328 open cells have data and 17 do not.

**Readings:**
- **Concentration.** Research so far piled up in a few native cells:
  - PRICE_STRUCTURE × CANDLES;
  - CROSS_ASSET cross-section (10 units);
  - EVENTS × CANDLES;
  - CALENDAR;
  - the divergence × ORDER_BOOK cell (8 units).

  Spot↔perp holds 7 units in two cells. The SPOT_PERP region (30 cells) has prior work in 2. MICROSTRUCTURE has prior work in 3 of 41 cells, and none of it was executed to an outcome.
- **Signals.**
  - CONFIRMED: D7 (kline-derived execution-impact state; BitMEX confirmation).
  - LIVE_SIGNAL: D2 (replicated), D11, D12 and GV0R01-C013 (C013's confirmation needs about 9 years of fresh weeks).
- **Order-book surfaces are not pristine.** Binance USD-M bookDepth for BTC/ETH in 2023–2024, and for six symbols from 2025-01-01 to 2026-08-14, was read with outcomes through the SEED-0001 / divergence "book support" state, which is a ±5% depth imbalance. Book imbalance and depth asymmetry on that surface therefore count as **exposed**. Pristine order-book surfaces are:
  - OKX L2 archives (from 2023-03, acquirable);
  - Binance bookDepth on symbols never used;
  - forward collection.
- **Top of the frontier.**
  - With owner priority: spot confirmation of funding/OI moves (SPOT_PERP.spot_confirmation; 13), spot volume-share migration, spot/perp lead-lag around stress, then order-book imbalance, depth asymmetry and book recovery (11).
  - Without owner priority, the best cells score 10: breakout, impulse and level reactions with taker flow or spot added, absorption on spot, and price response conditional on flow (native).
- **Revisits.**
  - K1 event corridor (CPI/FOMC): after the K1 freeze, about 12 prospective releases.
  - G01-B1 ETF fixing hour: from 2027 onward, prospectively.
  - GV0R01-C013: needs about 468 fresh weeks.
- **Open questions found during the transfer (not resolved here):**
  1. **E1 overlap.** The frozen PRICE_OI pilot grid starts 2026-08-16T19:30Z, inside the calendar span of the E1-RUN-001 holdout. The pilot record does not discuss E1. Resolve this with the owner before the runner is used.
  2. **SEED-0001 prospective leg.** It is still REGISTERED_NOT_STARTED in the test ledger, although the divergence line was closed on 2026-10-03. A record retiring it is missing.
  3. **Stale memory statuses.** Memory entries for some ids still show pre-closure statuses. The atlas records the later facts; the memory chain is unchanged.
  4. **PR #303.** CURRENT_RESEARCH_STATE says PR #303 is not merged; git history shows it merged as `04e1300` and then restored by `a7d738f`.

## 10. Known limits of V1

- **Readiness is coarse.** It is judged per column and dataset. It does not grade resolution (hourly book features vs L2) or the exposure of the outcome period. Outcome-period exposure stays with the evaluation contract, which requires time-disjoint or prospective replication.
- **Placement is a judgement.** Each unit sits in one cell by its primary information source. Cross-cutting units name their other layers in the note.
- **Some states are judgements too.** Red-team and dedupe closures from candidate pools are BLOCKED_METHOD. Sprint pool candidates not selected for budget reasons are CANDIDATE_UNTESTED.

## 11. Additions beyond the owner proposal, and proposals for owner decision

**Implemented in V1:**
1. **Four extra states.**
   - CANDIDATE_UNTESTED separates "never run" from "underpowered".
   - BLOCKED_METHOD separates a method blocker from missing data.
   - LIVE_SIGNAL and CONFIRMED separate a discovery from a confirmed mechanism.
2. **Two lenses** with machine-checked generator blindness (§4).
3. **Applicability** (native layer plus added layer): no fake cells, and combined cells are scored by their weaker layer.
4. **Per-dataset exposure ledger.** It is what showed the first frontier's order-book surface is not pristine on Binance BTC/ETH.
5. **Outcome-neutral frontier value**, with owner priority as an explicit, dated input.
6. **Revisit schedule** for FUTURE_NATURAL_ACCUMULATION and LIVE_SIGNAL units.
7. **Fail-closed coverage** of memory and of the bot's research findings.

**Proposed, not implemented (each needs an owner decision):**
1. **Generator contract V04 reads the atlas.** The generator receives the blind view plus one selected cell, and every card declares its cell and reopen key. This changes the Generator V0 architecture freeze.
2. **Surface openers ranked by value of information.** For each acquirable or forward dataset, count the frontier cells it would open or upgrade, for example OKX L2 2023-03+, Bybit OI history, Deribit DVOL with point-in-time proof, and a forward Binance depth collector. Acquisitions are then chosen by that count, not by the last result.
3. **Pristine reserve.** Declare some surfaces as confirmation-only reserve (for example BitMEX 2016–2019 per region, OKX L2) so discovery cannot spend them.
4. **Confirmation budget per region.** Cap confirmatory looks per region and surface, so surfaces are not spent silently.
5. **Prospective-first lane for LIVE_SIGNAL units** (D2, D11, D12, C013). Collectors accumulate fresh units for the revisit triggers instead of new discovery. This requires unfreezing a forward collector.
6. **Append-only atlas event log.** Each batch appends a hashed event, and the units file becomes derived from the log, as with the memory chain. This makes the map tamper-evident.
7. **Product bridge.** When a cell changes state, the matching «Проверено: …» line in the bot updates in the same change.
