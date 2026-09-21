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
PREVIOUS_ROUTING            = D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT
PREVIOUS_ROUTING_SUPERSEDED = true
R_A_CURRENT_STATUS          = DISCOVERY_SPRINT_01_D1
MARKET_07_CREATED           = false
NEXT_UNIT                   = D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION
PROTECTED_2025_OPENED       = false
PROTECTED_2026_OPENED       = false
INTERNAL_DISCOVERY_CARDS_EXECUTED = 4
INTERNAL_PROMISING_PROTOTYPES     = 1
INTERNAL_DISCOVERY_WARNING        = null
FULL_DISCOVERY_CARDS_COMPLETED    = 4
PARTIAL_COMPONENT_OUTCOMES_OBSERVED = 1
PARTIAL_COMPONENT_OUTCOMES        = D2/RULE_2/DISLOCATION_ABSTENTION
D2_RULE_2_DISCOVERY_OUTCOME_OBSERVED = true
D2_RULE_2_GATE_PASS               = false
D2_RULE_2_REPLAY_EXACT_MATCH      = true
POST_OUTCOME_DESIGN_CHANGES       = false
D1_STATUS                         = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
D2_DISCOVERY_STATUS               = PROMISING_PROTOTYPE
CONFIRMATION_FEASIBILITY          = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
2025_OPEN_AUTHORIZED              = false
2026_OPEN_AUTHORIZED              = false
ARM_CREATED                       = false
D2_OUTCOME_COMPUTED_ON_BITMEX     = false
D2_BITMEX_CLASSIFICATION          = D2_BITMEX_REPLICATION_INVALID
D2_BITMEX_CONSTRUCTED_ELIGIBLE_N  = 1067
D2_BITMEX_FROZEN_ELIGIBLE_N       = 1069
RERUN_AUTHORIZED                  = false
PROTECTED_2025_PRICE_VALUES_INSPECTED = false
PROTECTED_2026_PRICE_VALUES_INSPECTED = false
```

Discovery Sprint 01 first attempt (`37921089ce289cd9bcbcebb123724a3e033dcdc3`)
is preserved as blocked: D2/D3/D4 rolling/D5 were
`BLOCKED_MISSING_LOCAL_DATA`; D2 RULE_2 was a partial component outcome
(`GATE_PASS=false`), not a completed card.

After restoring frozen CORE BTC/ETH 2020-2024 only, the same
implementation `26d8f7066533bcae7138d5a1952783f2a16f3c39` was retried.
Preflight BTC/ETH/M06 all present. D2 RULE_2 replayed exactly. Retry
classifications: D2 `PROMISING_PROTOTYPE` (RULE_1 gate pass; RULE_2
still fails), D3/D4/D5 `NO_USEFUL_STRUCTURE`. Adaptive discovery only;
not confirmatory. Protected 2025/2026 unopened. MARKET-07 not created.
No post-outcome design changes.

D1 was then adjudicated for `D1_NULL_ADEQUACY_GATE` and **deferred**:
the frozen daily GARCH null cannot generate the 288×5m `ev.rv_btc_24h`
observable used by `RV_20`, and no already-frozen mapping exists. The
gate was not executed. Independently, gate statistics remain
underspecified. `D1_STATUS = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`.
Deferred D1 is not counted as executed. D6 remains `DEFERRED`.
D4 `LEAD_LAG_1DAY` remains `DEFERRED_FROM_SPRINT_01`.

Result records: `docs/research/discovery_results/`.
Adjudication record: `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.{json,md}`.

D2 RULE_1 (`RV_ABSTENTION`) was then taken through
`D2_CONFIRMATION_FEASIBILITY_AND_DESIGN` without opening 2025/2026
prices or creating MARKET-07/ARM. Calendar 2025 is the proposed first
independent confirmation surface; 2026 remains a second reserved
surface. Metadata-only 2025 monthly source/canonical hashes are bound.
A 2020-2024 power calculation at the predeclared 20% true effect
returned year-cycled `ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011`
(joint pass probability `0.006` is diagnostic only; practical-gate
power `~0.499` at the exact 20% boundary is expected and is not
underpower evidence). Primary prospective criterion is statistical
power `>= 0.80`. `CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025`.
IID two-year power `0.903` is superseded. Authoritative
year-matched whole-year-block plus contiguous partial-block power
gives `POWER_N728 = 0.64 < 0.80` and `POWER_N1092 = 1.0`.
`MIN_REQUIRED_FRESH_DECISION_ROWS = 1092`.
`POTENTIAL_FUTURE_SURFACE = MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE`.
`AUTHORIZED_TO_OPEN = false`. `2025_OPEN_AUTHORIZED = false`.
Do not consume 2025+2026. Full calendar 2026 is not currently available.
Record: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

`D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY` then tested whether the
same frozen RULE_1 / RV_ABSTENTION mechanism can be replicated on pre-2020
BitMEX XBTUSD without waiting for future Binance data and without opening
2025/2026. Refined year-matched power on exposed 2020-2024 only gives
`MIN_REQUIRED_FRESH_DECISION_ROWS = 815` (point-estimate power `0.801`).
Official BitMEX 5m buckets yield `BITMEX_PRE2020_ELIGIBLE_N = 1069` legal
decision rows whose 24h outcomes finish before 2020-01-01. Contract
compatibility is `SCIENTIFICALLY_COMPARABLE_CROSS_VENUE` (price-path MAE,
not inverse PnL). No D2 outcome was computed on BitMEX.
`CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION`.
A later BitMEX result, if executed, is
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`, not exact Binance
confirmation. Protected 2025/2026 remain sealed.
Record: `docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.{json,md}`.

`D2_BITMEX_REPLICATION_PREREG_FREEZE` then froze the outcome-blind
replication contract without executing it. Evidence class
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`. Rule, target,
clock, year-matched comparator, 10000-replicate seed `20260921125`,
statistical `MU_RULE > CONTROL_P95`, and practical
`DELTA >= 0.20 * UNCONDITIONAL_MEAN` are bound. Mechanical census
reproduced `N=1069`, first `2017-01-24T00:05:00Z`, last
`2019-12-30T00:05:00Z`. Classification unassigned. No BitMEX D2 outcome.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_PREREG.{json,md}`.

`D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW` then
replaced the firewalled stub evaluator with a reviewed execution
implementation without computing BitMEX outcomes. Timestamp census still
reproduces `N=1069`. Execution remains unauthorized: no permit exists.
`IMPLEMENTATION_REVIEW = PASS`. `EXECUTION_READY = true`.
`EXECUTION_AUTHORIZED = false`.
Record: `docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.{json,md}`.

`D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION` then created the immutable
permit and executed once. Timestamp census still matches frozen
`N=1069` / `2017-01-24T00:05:00Z` / `2019-12-30T00:05:00Z` /
years `341/364/364`. Constructed eligible rows after frozen
`construct_discovery_row` were `N=1067` (years `341/363/363`). The
sample-identity gate therefore classified
`D2_BITMEX_REPLICATION_INVALID`. Primary MU_RULE / control metrics were
not computed. This is not `NOT_SUPPORTED` and not a rescue. No rerun.
Protected 2025/2026 unopened. MARKET-07 not created.
Record: `docs/research/D2_BITMEX_REPLICATION_RESULT.{json,md}`.
`NEXT_UNIT = D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION`.

All six Discovery Sprint 01 cards (D1-D6) were converted to frozen
`EXECUTABLE_DISCOVERY_SPEC` records (none deferred) by
`DISCOVERY_SPRINT_01_SPEC_COMPILATION`, recorded in
`docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`. That unit
is an outcome-blind spec freeze, not a confirmatory lifecycle: no ARM, no
claim/reservation, no one-shot execution authority. At compilation time
no discovery outcome had been computed. The first partial batch is
preserved as blocked; the CORE-restore retry completed D2-D5 as recorded
in the next-unit box above.

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

**Superseded once more by `DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX`**
(reviewed commit `475072d22f4c4631836ca7d38ccdc5da6ce59222`,
`docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`),
D3, D4's practical-threshold semantics, and D5 only; D1 and D6 unchanged.
D3's real functionals used 5m HIGH/LOW while its surrogate only ever
produced a close-to-close path -- a real/null observable mismatch, fixed
(without inventing synthetic high/low) by redefining D3 as CLOSE-PATH
morphology: `MAX_UPSIDE_CLOSE_24H`, `MAX_DOWNSIDE_CLOSE_24H`,
`TIME_TO_MAX_ABS_CLOSE_EXCURSION` (exactly 3 functionals; `PATH_ASYMMETRY`
removed, since the original card allowed at most 2-3 and it is derivative
of the other two anyway). D4's `ROLLING_CORRELATION_90D` practical gate
made mathematically exact: `PRACTICAL_EXCESS_RANGE =
OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN >= 0.15`. D5's
"beats best component" check corrected to compare against
`COMPONENT_A_DELTA_FOR_D5` / `COMPONENT_B_DELTA_FOR_D5` (both evaluated
on D5's exact common interval `2022-02-01 -> 2025-01-01`), not D2
RULE_1's unrestricted full-2020-2024 result.

**Current per-card status:** `D1 = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH`
(adequacy gate not executed); `D2 = PROMISING_PROTOTYPE` (adaptive
discovery; RULE_1 only; 2025 confirmation remains underpowered as a
single year; pre-2020 BitMEX one-shot classified
`D2_BITMEX_REPLICATION_INVALID` on constructed N=1067 vs frozen N=1069);
`D3 = NO_USEFUL_STRUCTURE`; `D4
ROLLING_CORRELATION_90D = NO_USEFUL_STRUCTURE` (`LEAD_LAG_1DAY` still
deferred); `D5 = NO_USEFUL_STRUCTURE`; `D6 = DEFERRED`. First blocked
attempt preserved. D2–D5 scientific bytes unchanged.

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
