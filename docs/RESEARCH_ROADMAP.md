## Generator V0 limited offline repair (after PR #215 verification) — 2026-09-23

`NEXT_UNIT = GENERATOR_V0_LIMITED_REPAIR_READY_FOR_RE_VERIFICATION`.
Limited offline repair of the five blockers found by the independent
verification (PR #215):
- keyed novelty prompt/schema/parser contract;
- sealed journals refused inside `Ledger`;
- dispatch state machine so a possibly-POSTed call is never re-sent without evidence;
- Unicode-normalized structural temporal/protected/trade checks;
- budget preflight for fresh and derived journals, with a scenario table and no run shape chosen.
Completion state is `READY_FOR_RE-VERIFICATION`, not a provider smoke test or live shadow. No paid call, no protected data, no scientific outcome; v6/v7 sealed and untouched. See `docs/research/GENERATOR_V0_LIMITED_REPAIR.md`.

## Generator V0 pre-live repair (offline) — 2026-09-23

`SUPERSEDED_NEXT_UNIT = GENERATOR_V0_PRE_LIVE_REPAIR_READY_FOR_INDEPENDENT_REVIEW` (reviewed by PR #215; see the limited repair above).
Offline repair of the audit findings behind the v4–v7 one-failure-per-run
history: per-card quarantine instead of campaign aborts, a single V02 rule
contract (prompt and validator derived from one table), decoding-level
schemas, explicit provider failure classes with reconcile, an advisory
selector, and lineage-cumulative spend (a derive from v7 keeps USD 4.946750
charged). Completion state is `READY_FOR_INDEPENDENT_REVIEW`, not ready for a
live shadow. No paid call, no protected data, no scientific outcome; v6/v7
sealed and untouched. See `docs/research/GENERATOR_V0_PRE_LIVE_REPAIR.md`.

---

## Generator V0 first-shadow-v7 fail-closed — 2026-09-23

`NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_FAIL_CLOSED`.
Live first-shadow-v7 ran generation:3 under the USD 17.100000 absolute
ceiling, then fail-closed on `ambiguous protected range`. New spend
USD 1.167200; cumulative USD 4.946750. Critics and selector were not
started. No scientific outcome. Protected 2025/2026 remain unopened.
`first-shadow-v6` and `first-shadow-v7` are sealed. Do not resume v7. Do
not extend LEGAL_RANGE or the C033 exclusion parser from observed
generation:3 wrappers. Frozen design/historical records retain their
historical labels.

---

# Signalbot Research Roadmap

**Status:** ACTIVE  
**Updated:** 2026-09-23
**Current phase:** `GENERATOR_V0_LIMITED_REPAIR_READY_FOR_RE_VERIFICATION`

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

`INTERNAL_DISCOVERY_CARDS_EXECUTED = 10`.
`INTERNAL_PROMISING_PROTOTYPES = 4`.
`D2_PROGRAM_CLASS = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`.
`D2_DECOMPOSITION_DESIGN_STATUS = FROZEN`.
`D2_DECOMPOSITION_IMPLEMENTATION_REVIEW = PASS`.
`D2_DECOMPOSITION_EXECUTION_READY = false`.
`D2_DECOMPOSITION_IMPLEMENTATION_REVIEW_CANONICAL_SELECTOR_DIGEST_FROZEN = false`.
`D2_DECOMPOSITION_SELECTOR_IDENTITY_AUTHORITY = FROZEN`.
`D2_DECOMPOSITION_CANONICAL_SELECTOR_DIGEST_FROZEN = true`.
`D2_DECOMPOSITION_EXECUTION_PERMIT_CREATED = true`.
`D2_DECOMPOSITION_EXECUTION_AUTHORIZED = true`.
`REAL_DECOMPOSITION_OUTCOME_COMPUTED = true`.
`RESULT_CREATED = true`.
`D2_DECOMPOSITION_CLASSIFICATION_ASSIGNED = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`.
`RERUN_AUTHORIZED = false`.
`HETEROGENEOUS_FAMILY_ROTATION_V1 = FROZEN_HISTORICAL_SPRINT_02_POLICY`.
`HETEROGENEOUS_FAMILY_ROTATION_V2 = FROZEN_HISTORICAL_SPRINT_03_POLICY`.
`HETEROGENEOUS_FAMILY_ROTATION_V3 = FROZEN`.
`DISCOVERY_SPRINT_02 = D7_EXECUTED_D8_DEFERRED`.
`DISCOVERY_SPRINT_02_INTERNAL_CARDS = 2`.
`DISCOVERY_SPRINT_03 = CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED`.
`DISCOVERY_SPRINT_03_INTERNAL_CARDS = 3`.
`SPRINT03_SELECTION_INCOMPLETE = false`.
`SPRINT04_HYPOTHESES_SELECTED = true`.
`DISCOVERY_SPRINT_04 = CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED`.
`DISCOVERY_SPRINT_04_INTERNAL_CARDS = 2` (D12, D13; D14 not selected).
`D7_STATUS = PROMISING_PROTOTYPE`.
`D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`.
`D9_STATUS = NO_USEFUL_STRUCTURE`.
`D10_STATUS = NO_USEFUL_STRUCTURE`.
`D11_STATUS = PROMISING_PROTOTYPE`.
`D12_STATUS = PROMISING_PROTOTYPE`.
`D13_STATUS = NO_USEFUL_STRUCTURE`.
`D9_CHOSEN_ESTIMAND = RELATIVE_RESOLUTION_ATTRIBUTION`.
`D7_CONFIRMATION_CANDIDATE = true`.
`D7_CONFIRMATION_SELECTED_NOW = false`.
`D8_SCIENTIFIC_EXECUTION_ELIGIBLE = false`.
`DATA_IDENTITY_MODE = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION`.
`PREVIOUS_UNIT = DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION` (consumed).
`PREVIOUS_UNIT = POST_SPRINT04_AUTOMATION_MATURITY_DECISION` (decided:
`HYPOTHESIS_GENERATOR_V0_INFRA_READY`; no Sprint 05; design frozen in
`docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.{json,md}`, not built).
`NEXT_ACTION = STOP_NO_RESUME_NO_VALIDATOR_REPAIR`.
`NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_FAIL_CLOSED`.

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
selector unchanged, primary target `ADVERSE_SHARE`, comparator
`YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION`, seed `20260922131`.

That frozen design has now been implemented and reviewed outcome-blind by
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
(`IMPLEMENTATION_REVIEW = PASS`, `SCIENTIFIC_KERNEL_READY = true`,
`CANONICAL_ORCHESTRATION_READY = true`, `PERMIT_VERIFIER_READY = true`,
`EXACT_SELECTOR_IDENTITY_IMPLEMENTED = true`,
`CANONICAL_SELECTOR_DIGEST_FROZEN = false`, `EXECUTION_READY = false`,
`EXECUTION_AUTHORIZED = false`). The design was not redesigned; the
evaluator re-walks the exact 288×5m `PerpBar` future path so `MAE_SIDE`
and `MAE_OPPOSITE` share one path, and cross-checks `MAE_SIDE` against
the frozen `DiscoveryRow.severity`. The dormant canonical route is fully
wired behind a tracked-permit firewall that does not exist in this unit.
The canonical route requires a tracked selector-identity authority and
compares the reconstructed ordered digest to it before any ADVERSE_SHARE
/ PATH_SCALE evaluation. The implementation-review unit did **not** create
the authority (`CANONICAL_SELECTOR_DIGEST_FROZEN = false` at review time).
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`
has now frozen that authority from legal CORE BTC 2020-2024
(`SELECTOR_IDENTITY_AUTHORITY = FROZEN`, current
`CANONICAL_SELECTOR_DIGEST_FROZEN = true`). The one-shot permit commit then
created the tracked execution permit and runner
(`EXECUTION_PERMIT_CREATED = true`, `EXECUTION_AUTHORIZED = true`,
`ONE_SHOT = true`, `RERUN_AUTHORIZED = false`). The exact permit commit
was then executed once. Canonical classification (not reinterpreted):
`D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT`.
`REAL_DECOMPOSITION_OUTCOME_COMPUTED = true`. No rerun. 2025/2026 sealed.
MARKET-07 not created.
`HETEROGENEOUS_FAMILY_ROTATION_V1` is preserved as the historical Sprint 02
policy. Sprint 02 defined D7 (family E) and D8 (family G). D7 selector
identity is frozen; D8 is non-executable for that card
(`DEFERRED_INSUFFICIENT_CONTROL_SUPPORT`).
`DATA_IDENTITY_MODE = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION`.
The D7 one-shot was executed once. Classification (not reinterpreted):
`D7_PROMISING_PROTOTYPE`. Family E is in cooldown. D8 remains deferred
and is not a negative scientific result. Rotation V2 selected three
Sprint 03 families D/G/H as D10/D11/D9. The canonical scientific
execution from `e2852f57ee946ec8380f09fa4cf834579c40f872` classified
D9/D10 `NO_USEFUL_STRUCTURE` and D11 `PROMISING_PROTOTYPE`. Do not
rescue D9/D10. D11 is unsigned scheduled-FOMC vol only; not D8 rescue;
not a FOMC trading strategy. Sprint 04 is not selected here.
D9 estimand remains `RELATIVE_RESOLUTION_ATTRIBUTION`
(`TOTAL_CLOSURE=-s*(rp-rs)`; unclipped median SHARE; not price-discovery
leadership). D10 is no-intercept OLS and reuses frozen pre-event `beta_t`
at t+1. D11 is official scheduled FOMC only, calendar pinned
(`YEAR × WEEKDAY × UTC_HOUR`). The old common-mode
`RESOLUTION_IMBALANCE=-s*(rp+rs)` is rejected.
D7 is a confirmation candidate but is not selected for confirmation now.
`RESEARCH_DATA_DURABILITY_V1_REQUIRED = true` (not implemented here).
`PREVIOUS_UNIT = DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION` (decided).
The post-Sprint 03 program decision
(`docs/research/POST_SPRINT03_PROGRAM_DECISION.{json,md}`) records D9/D10
consumed `NO_USEFUL_STRUCTURE`, D11 consumed `PROMISING_PROTOTYPE`, and
keeps D7/D11 confirmation unselected. Because all three prototypes are
volatility/activity-level structures, Sprint 04 selects no
volatility-level card. Under `HETEROGENEOUS_FAMILY_ROTATION_V3` it selects
D12 `PARTICIPATION_CLOCK_ANCHORING_DST_NATURAL_EXPERIMENT` (new family J;
existing CORE BTC) and D13 `CROSS_SECTIONAL_WEEKLY_RELATIVE_RETURN_STRUCTURE`
(H true panel; bounded free Binance Vision acquisition,
now `CANONICAL_SCIENTIFIC_EXECUTION_CONSUMED`). After Sprint 04 execution: a mandatory
automation maturity decision (`HYPOTHESIS_GENERATOR_V0_INFRA_READY` or
`AT_MOST_ONE_FINAL_SPRINT05`); `AUTOMATIC_SPRINT05 = false`.
The canonical Sprint 04 one-shot from `d2a62da6e5c907def603a258505b9cc1f92ae3a5`
classified D12 `PROMISING_PROTOTYPE` and D13 `NO_USEFUL_STRUCTURE`. Do not
rescue D13. Do not use the EU diagnostic to reclassify D12. Do not
automatically create Sprint 05. Do not build the hypothesis generator here.
`PREVIOUS_UNIT = POST_SPRINT04_AUTOMATION_MATURITY_DECISION` (decided:
`HYPOTHESIS_GENERATOR_V0_INFRA_READY`; no Sprint 05; design frozen in
`docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.{json,md}`, not built).
`NEXT_ACTION = STOP_NO_RESUME_NO_VALIDATOR_REPAIR`.
`NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_FAIL_CLOSED`.

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
