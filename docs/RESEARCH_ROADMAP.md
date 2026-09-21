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

## 3. Next unit

`MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`

Choose exactly one region before creating a new hypothesis ID:

- **R-A** structural regime/state detection;
- **R-B** conditional abstention/tail selection;
- **R-C** cross-sectional relative structure;
- **R-D** liquidity/market-structure state;
- **R-E** execution-cost mechanism;
- **R-F** composed joint state, with the highest post-hoc rescue risk.

Selection must maximize information gain / search-space coverage. A negative result should eliminate a materially different mechanism-space cell. Do not select merely because a region is easiest to test or most likely to produce a positive chart.

## 4. After a region is selected

1. write a decision card: mechanism, function, information source, target, horizon, comparator, smallest useful effect, and what each outcome eliminates;
2. check point-in-time data feasibility before preregistration;
3. freeze the exact hypothesis and analysis contract outcome-blind;
4. implement/review;
5. execute once;
6. update the program map.

No same-window rescue of consumed M06, no protected-OOS fishing, no automatic queue of M07/M08/etc.

## 5. Product boundary

Product build remains frozen. Research infrastructure is justified only by a concrete selected research blocker.
