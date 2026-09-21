# Signalbot Research Roadmap

**Status:** ACTIVE  
**Updated:** 2026-09-21  
**Current phase:** `POST_M06_ORTHOGONAL_SEARCH_SELECTION`

The previous long-form roadmap is preserved in git history at `b25d9ca99498630183813d0ccb8c6d67b93ad915`. This file controls current execution order.

## 1. Closed / fixed

- V3: closed historical instrumentation; no rerun, no V4.
- MARKET-01: `NO_EVIDENCE`.
- MARKET-02: `NO_EVIDENCE`.
- MARKET-03: external historical `REPRODUCED_DIRECTION`, not validated internal alpha.
- MARKET-04 / 04H: blocked observable, not tested.
- MARKET-05: `NO_EVIDENCE`.
- MARKET-06: `NO_EVIDENCE`, one-shot consumed and sealed; no rescue/rerun.
- Protected 2025/2026: unopened.
- Internal historical promoted candidates: 0.

## 2. Search-space decision after M06

Deprioritize the exact/near-exact M05/M06 cell:

`external/cross-market observable -> additive incremental term beside BTC own-state controls -> 24h direction-aligned adverse-path prediction -> holdout MAE improvement`.

Also deprioritize the broader family of nearby short-horizon BTC conditional scalar-prediction studies for now. This is a portfolio/search decision, not proof the whole family is false.

## 3. Region selection (closed, preserved)

`MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS` selected R-A
(structural regime/state detection) from the six orthogonal regions R-A..R-F,
recorded in `docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.{json,md}`
(commit `a711086c36eb7129fc3f0660732049de93dd1629`). That selection is
preserved and not retracted; only its routing into an immediate
confirmatory unit is superseded (section 3a).

## 3a. Current phase: `HYPOTHESIS_DISCOVERY_PIPELINE_V2`

A program-level decision, recorded in
`docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.{json,md}` and
`docs/research/DISCOVERY_SPRINT_01.{json,md}`, inserts a lightweight
discovery stage ahead of any confirmatory MARKET-0N unit:
`ADAPTIVE_DISCOVERY -> PROMISING_PROTOTYPE -> CONFIRMATORY_RESEARCH`.
This is a research-process redesign, not a market hypothesis — it does not
create MARKET-07, preregister R-A, open protected 2025/2026, or execute a
confirmatory experiment.

`DISCOVERY_SPRINT_01` defined six discovery cards. **Current routing**
after the CORE-restore retry (adaptive discovery, not confirmatory):

- **D1** `STRUCTURAL_STATE_DETECTION` — `BLOCKED_PENDING_PRE_OUTCOME_FIX`
- **D2** `CONDITIONAL_ABSTENTION_TAIL_RISK` — `PROMISING_PROTOTYPE`
- **D3** `PATH_MORPHOLOGY` — `NO_USEFUL_STRUCTURE`
- **D4** `BTC_ETH_RELATIVE_STRUCTURE` (`ROLLING_CORRELATION_90D`) — `NO_USEFUL_STRUCTURE`; `LEAD_LAG_1DAY` remains deferred
- **D5** `COMPOSED_DECISION_MECHANISM` — `NO_USEFUL_STRUCTURE`
- **D6** `EXTERNAL_MECHANISM_BENCHMARK` — `DEFERRED` (diagnostic only, not internal discovery, never counted with MARKET-03)

`INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`.
`INTERNAL_PROMISING_PROTOTYPES = 1`.
`NEXT_UNIT = DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE_EXECUTION`.

Card identities at definition time (unchanged):

- **D1** `STRUCTURAL_STATE_DETECTION` — reclassified R-A;
- **D2** `CONDITIONAL_ABSTENTION_TAIL_RISK` — exploratory R-B, historically exposed data;
- **D3** `PATH_MORPHOLOGY` — trajectory/path characterization, not terminal-return prediction;
- **D4** `BTC_ETH_RELATIVE_STRUCTURE` — two-asset precursor, not cross-sectional panel evidence;
- **D5** `COMPOSED_DECISION_MECHANISM` — bounded exploratory R-F, HIGH rescue risk recorded;
- **D6** `EXTERNAL_MECHANISM_BENCHMARK` — diagnostic only, not internal discovery, never counted with MARKET-03.

Plus one non-card, outcome-blind sidecar: `CROSS_SECTIONAL_PANEL_FEASIBILITY`.

The stall-gate rule is unchanged: if, after 6-10 materially
orthogonal internal cards, `INTERNAL_PROMISING_PROTOTYPES == 0`, record
`INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = true` and require a
program-level decision before another batch — never simply generate more
nearby variants.

## 4. After a card becomes a promising prototype

A `PROMISING_PROTOTYPE` only makes a mechanism eligible to be *proposed* for
a future confirmatory unit; it is not itself evidence. Proposing one still
requires the full existing process:

1. write a decision card: mechanism, function, information source, target, horizon, comparator, smallest useful effect, and what each outcome eliminates;
2. check point-in-time data feasibility before preregistration;
3. freeze the exact hypothesis and analysis contract outcome-blind;
4. implement/review;
5. execute once;
6. update the program map.

No same-window rescue of consumed M06, no protected-OOS fishing, no automatic queue of M07/M08/etc.

## 5. Product boundary

Product build remains frozen. Research infrastructure is justified only by a concrete selected research blocker.
