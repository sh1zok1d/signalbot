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

```
PREVIOUS_ROUTING            = STRUCTURAL_REGIME_STATE_DETECTION_MECHANISM_CLASS_AND_NULL_MODEL_FEASIBILITY
PREVIOUS_ROUTING_SUPERSEDED = true
R_A_CURRENT_STATUS          = DISCOVERY_SPRINT_01_D1
MARKET_07_CREATED           = false
NEXT_UNIT                   = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5
PROTECTED_2025_OPENED       = false
PROTECTED_2026_OPENED       = false
```

All six Discovery Sprint 01 cards (D1-D6) were converted to frozen
`EXECUTABLE_DISCOVERY_SPEC` records (none deferred) by
`DISCOVERY_SPRINT_01_SPEC_COMPILATION`, recorded in
`docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`. That unit
is an outcome-blind spec freeze, not a confirmatory lifecycle: no ARM, no
claim/reservation, no one-shot execution authority. No discovery outcome
has been computed and no candidate performance has been inspected.

**Superseded by `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`** (reviewed commit
`7bb92b0bd6238693164b6592c0711fa4c15fc9fe`,
`docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`), which
checked whether each frozen spec was actually mechanically executable, not
merely well-worded. Seven suspected defects (F1-F7) were reviewed
outcome-blind: F1, F2, F3, F4, F6 were confirmed and fixed (per-rule legal
intervals + bound cross-venue dataset authority for D2/D5's
dislocation-based rule; an explicit base exposure schedule for D2/D5; a
corrected native-5m-granularity null for D3, replacing a mechanically
broken daily-granularity reuse; a corrected split null for D4's lead-lag
vs. rolling-correlation functionals; a corrected variance-level RV_20
formula for D1). F5 found D1's null defensibility had been asserted, not
verified -- a `D1_NULL_ADEQUACY_GATE` (non-target summary statistics only)
is now defined but not yet executed. F7 found D6's external benchmark has
at most one testable historical episode given `CORE_BTC_BINANCE_V0`'s
2020 start versus the source's 2013/2017/2021 claims, judged
diagnostically insufficient.

**Superseded again by `DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4`**
(reviewed commit `355a1657aac288fe75b272df1845fd9b5cfcac3f`,
`docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`),
D3 and D4 only; D1, D2, D5, D6 unchanged from the red-team review above.
D3's excursion functionals were direction-aligned via `BTC_SIDE(t)`,
contradicting its own `UNCONDITIONAL_DESIGN` label and risking
smuggled-in directional-predictability structure; redefined as genuinely
unsigned (`MAX_UPSIDE_EXCURSION_24h`, `MAX_DOWNSIDE_EXCURSION_24h`,
`TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`). D3's null was also found to
ignore UTC time-of-day -- since every MARKET-06 decision point shares the
same fixed UTC decision time, bar-offset structurally equals
time-of-day, making `TIME_TO_MAX_EXCURSION` a near-certain seasonality
confound -- corrected to a time-of-day-stratified block bootstrap. D4's
`INDEPENDENT_BLOCK_BOOTSTRAP` lead-lag null was found to also destroy
ordinary same-time common-factor dependence, not just the tested cross-lag;
`LEAD_LAG_1DAY` is now `DEFERRED_FROM_SPRINT_01` (no complex replacement
null invented), `ROLLING_CORRELATION_90D` retained unchanged.

**Current per-card status:** `D1 = BLOCKED_PENDING_PRE_OUTCOME_FIX`;
`D2, D3, D5 = EXECUTABLE_DISCOVERY_SPEC`; `D4 =
EXECUTABLE_DISCOVERY_SPEC (ROLLING_CORRELATION_90D only, LEAD_LAG_1DAY
deferred)`; `D6 = DEFERRED`.
`EXECUTION_AUTHORIZED = PARTIAL (D2, D3, D4 [rolling-correlation only], D5)`.

The orthogonal-region selection is recorded in
`docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.{json,md}` (commit
`a711086c36eb7129fc3f0660732049de93dd1629`) and remains a valid historical
record: R-A was chosen because it materially changes the FUNCTION axis
(scalar outcome prediction -> state detection), does not rescue
MARKET-05/06, and is feasible with existing point-in-time price data. That
selection is **preserved, not retracted**.

A later, separate program-level decision recorded in
`docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.{json,md}` and
`docs/research/DISCOVERY_SPRINT_01.{json,md}` **supersedes only the
routing** that followed from a711086 (i.e. turning R-A directly into the
next confirmatory research unit). Signalbot has strong
falsification/validation machinery but `INTERNAL_PROMISING_PROTOTYPES = 0`
across MARKET-01/02/05/06; MARKET-03 is external reproduction, not internal
discovery. R-A is therefore reclassified as `DISCOVERY_SPRINT_01 / D1 =
STRUCTURAL_STATE_DETECTION`: it is explored first as one of six cheap,
outcome-inspecting, non-evidentiary discovery cards (D1-D6), not
immediately preregistered as a confirmatory hypothesis. R-A's null-model
risk (surrogate/null must preserve lower-order structure, chosen
outcome-blind) carries over unchanged into card D1.

a711086's statement that R-B and R-F "need a fresh evaluation surface that
does not exist" is now scoped to **confirmatory** use only.
`DISCOVERY_FEASIBILITY != CONFIRMATORY_FEASIBILITY`: both may be explored
under adaptive discovery on historically exposed 2020-2024 data (cards D2
and D5 respectively), but any resulting pattern remains exploratory and
requires an independent future confirmation surface, and D5 (R-F) carries
an explicitly recorded HIGH rescue/multiple-testing risk. R-C is still the
most orthogonal region but has no panel data and no listing/delisting
reconstruction (see the `CROSS_SECTIONAL_PANEL_FEASIBILITY` sidecar in
`DISCOVERY_SPRINT_01`). R-D and R-E remain forward-collection only.

Do not create MARKET-07. `DISCOVERY_SPRINT_01_CARD_EXECUTION` must stop and
require a program-level decision if, after 6-10 materially orthogonal
internal discovery cards, `INTERNAL_PROMISING_PROTOTYPES == 0`.

### Historical surface exposure

2020-2024 is a **historically exposed/adapted program research surface**:
H01/H02 and further H/BATCH work adapted on 2020-02-01 -> 2025-01-01 with
outcome inspection allowed, and MARKET-01/02/05/06 consumed confirmatory
windows inside it. A chronological split inside 2020-2024 must be called
"chronological held-out evaluation on historically exposed research data",
never out-of-sample or independent confirmation. The earlier claim that
2020-2021 was unconsumed is retracted.

## Hard boundaries

- no MARKET-05 or MARKET-06 rescue, sign flip, venue swap, threshold tweak, horizon tweak, or rerun;
- no opening protected 2025/2026 merely to search for a survivor;
- no V4;
- B2-06 remains blocked;
- product build remains frozen until evidence justifies a concrete restart.

For detailed history use `docs/RESEARCH_LEDGER.md`; for immutable experiment semantics use each experiment's frozen artifacts.
