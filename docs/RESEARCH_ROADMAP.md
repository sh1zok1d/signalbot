# Signalbot Research Roadmap

**Status:** ACTIVE  
**Updated:** 2026-09-22
**Current phase:** `POST_D2_INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`

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

- **D1** `STRUCTURAL_STATE_DETECTION` — `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`
- **D2** `CONDITIONAL_ABSTENTION_TAIL_RISK` — `PROMISING_PROTOTYPE`
- **D3** `PATH_MORPHOLOGY` — `NO_USEFUL_STRUCTURE`
- **D4** `BTC_ETH_RELATIVE_STRUCTURE` (`ROLLING_CORRELATION_90D`) — `NO_USEFUL_STRUCTURE`; `LEAD_LAG_1DAY` remains deferred
- **D5** `COMPOSED_DECISION_MECHANISM` — `NO_USEFUL_STRUCTURE`
- **D6** `EXTERNAL_MECHANISM_BENCHMARK` — `DEFERRED` (diagnostic only, not internal discovery, never counted with MARKET-03)

`INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`.
`INTERNAL_PROMISING_PROTOTYPES = 1`.
`D2_PROGRAM_CLASS = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`.
`D2_DECOMPOSITION_DESIGN_STATUS = FROZEN`.
`NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.

D2 discovery remains a `PROMISING_PROTOTYPE` (adaptive discovery label). Outcome-blind
confirmation design for RULE_1 / `RV_ABSTENTION` found calendar 2025
metadata-complete but **underpowered** as a single independent year
(`ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011`; joint `0.006` is
diagnostic). Authoritative year-matched whole-year-block size planning
on 2020-2024 only: `POWER_N728 = 0.64 < 0.80`; three-year `N=1092`
reaches 1.0. Refined grid plus one 5-row local pass:
`MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (power `0.801`). Pre-2020 BitMEX
XBTUSD official 5m history yields `1069` legal decision rows and is
`FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION`. The BitMEX
replication preregistration is frozen
(`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`). The execution
implementation has been reviewed outcome-blind (`EXECUTION_READY = true`,
`EXECUTION_AUTHORIZED = false`). The original one-shot BitMEX execution
classified `D2_BITMEX_REPLICATION_INVALID` (constructed eligible `N=1067`
vs frozen census `N=1069`; primary metrics not computed). Integrity
adjudication classed this
`REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`. The corrected
one-shot then passed identity `1317/250/1067` and classified
`D2_BITMEX_REPLICATION_SUPPORTED` on the independent pre-2020 cross-venue
temporal surface. This is not `EXACT_BINANCE_CONFIRMATION`, not
`PROVEN_ALPHA`, and not `VALIDATED_TRADING_EDGE`. Original INVALID run
preserved. No rerun. 2025 is not opened. 2026 is not consumed.

Program decision after that result: D2 is
`INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Discovery and independent
pre-2020 BitMEX replication claims are supported. Market-mechanism,
trading-edge, and product claims are not. Binance 2025/2026 stay sealed.
Hypothesis generation rotates across families A–I; D2 neighbors are
forbidden. Product remains frozen. MARKET-07 is not created. Mechanism-
decomposition **design** is now frozen (`DESIGN_STATUS = FROZEN`):
selector unchanged, primary target `ADVERSE_SHARE`, seed `20260922131`.
No real decomposition outcome. Next unit is implementation and
outcome-blind review:
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.

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
