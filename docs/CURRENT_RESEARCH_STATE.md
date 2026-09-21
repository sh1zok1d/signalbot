# Signalbot — Current Research State

**Status date:** 2026-09-21  
**Status:** `ACTIVE / CANONICAL ROUTING INDEX`  
**Main integration baseline before this status commit:** `b25d9ca99498630183813d0ccb8c6d67b93ad915`

This file is the compact answer to “what controls the project now?”. Frozen preregistrations/results remain authoritative for reproducing their own experiments; this file controls current routing only.

## Program state

| Unit | Current state | Canonical reference |
|---|---|---|
| MARKET-01 | `NO_EVIDENCE`, consumed, no rerun | `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json` |
| MARKET-02 | `NO_EVIDENCE`, consumed, no rerun | result lineage head `70f9489bd4fed905255b6791adcd23dc1e7d5dfa` |
| MARKET-03 | `REPRODUCED_DIRECTION` historical external reproduction; not internal validated alpha | RESULT `9c360a19a8e35ba0e7638fd125a0e6ae32f15846` |
| MARKET-04 / 04H | `BLOCKED_OBSERVABLE / NOT_TESTED`; not rejected | adjudication `e8d77b3b5c016582304db55c6ff2dacff92f0210` |
| MARKET-05 | `MARKET_05_NO_EVIDENCE`, consumed, no rerun | RESULT `828c6916fdb0da7b3f9fbad2bc0a97d87efcbb4b` |
| Forward observability | collector implementation frozen; authoritative collection not started by repo cleanup | `4158403b942c3ac0e2af3fb602f074f0064690fd` |
| MARKET-06 | `MARKET_06_NO_EVIDENCE`, one canonical shot consumed, no rerun | RESULT `80c7d19f622cc7b5576154de59dbb9cdf85d4dcf` |

MARKET-06 sealed identity:

- run identity: `f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22`;
- RESULT payload SHA256: `67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53`;
- classification: `MARKET_06_NO_EVIDENCE`;
- pooled relative MAE improvement: `-0.03756596483364705`, CI95 `[-0.0644801374915513, -0.014898013948610516]`;
- 2023: `-0.02814838672162434`; 2024: `-0.045320425619876925`;
- G1=true; G2-G6=false;
- protected 2025/2026 unopened.

Program-level correction is sealed in `docs/research/MARKET_PROGRAM_UPDATE_POST_M06.*`: MARKET-01 is **not** in the exact M05/M06 cell. The exact cell is repeated-null / low-priority-for-now; the broader short-horizon BTC conditional scalar-prediction family is low-priority / saturated-for-now as a search-priority judgement.

## Exact next unit

`NEXT_UNIT = MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`

Do not create MARKET-07 yet. Select one materially orthogonal region before feasibility/preregistration:

- R-A structural regime/state detection;
- R-B conditional abstention / tail selection;
- R-C cross-sectional relative structure;
- R-D liquidity / market-structure state;
- R-E execution-cost mechanism;
- R-F composed joint state (highest rescue risk; must not re-interrogate consumed M06 target/window).

Selection criterion: information gain and search-space coverage, not “most likely profitable”.

## Hard boundaries

- no MARKET-05 or MARKET-06 rescue, sign flip, venue swap, threshold tweak, horizon tweak, or rerun;
- no opening protected 2025/2026 merely to search for a survivor;
- no V4;
- B2-06 remains blocked;
- product build remains frozen until evidence justifies a concrete restart.

For detailed history use `docs/RESEARCH_LEDGER.md`; for immutable experiment semantics use each experiment's frozen artifacts.
