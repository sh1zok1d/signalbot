# Discovery Sprint 01 — Spec Compilation

**Unit:** `DISCOVERY_SPRINT_01_SPEC_COMPILATION`
**Unit type:** `OUTCOME_BLIND_SPEC_FREEZE_NOT_A_CONFIRMATORY_LIFECYCLE`
**Date:** 2026-09-21
**Parent commits:** `a711086`, `954fb55`, `dcbd16d` (all preserved, none rewritten)
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.json`

This is the final outcome-blind compilation step before Discovery Sprint 01
scientific outcomes are inspected. Each Discovery Card (D1-D6) is converted
into either `EXECUTABLE_DISCOVERY_SPEC` (fully frozen parameters) or
`DEFERRED` (blocking condition unmet). All executable specs are frozen in
this single pass, so no card's design can be informed by another card's
already-observed outcome — at compile time, zero cards in this sprint have
been executed anywhere, so this holds by construction.

No discovery outcome is computed here. No candidate performance is
inspected. Protected 2025/2026 remains unopened. No MARKET-07 is created.
No confirmatory machinery (ARM, claim/reservation, one-shot execution
authority, MARKET-style prereg lifecycle) is introduced — the Discovery
Card contract in `HYPOTHESIS_DISCOVERY_PIPELINE_V2.md` explicitly excludes
that machinery from discovery.

## Red-team review correction (2026-09-21)

This document was reviewed by `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW`
(reviewed commit `7bb92b0bd6238693164b6592c0711fa4c15fc9fe`; full record:
`docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`). **The
original "all six executable" classification below is withdrawn** and
superseded by that review's findings, which were then further corrected
by the final pre-execution correction below.

## Final pre-execution correction (2026-09-21)

`DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4` (reviewed commit
`355a1657aac288fe75b272df1845fd9b5cfcac3f`; full record:
`docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`)
further corrected D3 and D4 only:

- **D3** was direction-aligned via `BTC_SIDE(t)`, contradicting its own
  `UNCONDITIONAL_DESIGN` label and risking smuggled-in directional-
  predictability structure. Redefined as genuinely unconditional/unsigned
  (`MAX_UPSIDE_EXCURSION_24h`, `MAX_DOWNSIDE_EXCURSION_24h`,
  `TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`), with no `BTC_SIDE`
  dependency. Its null was also found to ignore UTC time-of-day, which —
  because every MARKET-06 decision point shares the identical fixed UTC
  decision time — makes `TIME_TO_MAX_EXCURSION` structurally equivalent
  to a time-of-day statistic; corrected to
  `5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP`.
- **D4**'s `INDEPENDENT_BLOCK_BOOTSTRAP` lead-lag null (from the first
  review round) was found to over-destroy, also killing ordinary
  same-time common-factor dependence. `LEAD_LAG_1DAY` is now
  `DEFERRED_FROM_SPRINT_01`; `ROLLING_CORRELATION_90D` is retained
  unchanged and cleanly specified.

**Status after that round:**

| Card | Status |
|---|---|
| D1 | `BLOCKED_PENDING_PRE_OUTCOME_FIX` (RV_20 formula corrected; `D1_NULL_ADEQUACY_GATE` defined, not yet executed) |
| D2 | `EXECUTABLE_DISCOVERY_SPEC` (RULE_2/interval and base-exposure-schedule fixes applied) |
| D3 | `EXECUTABLE_DISCOVERY_SPEC` (unsigned functionals + time-of-day-stratified null) |
| D4 | `EXECUTABLE_DISCOVERY_SPEC`, **ROLLING_CORRELATION_90D only** (`LEAD_LAG_1DAY` deferred) |
| D5 | `EXECUTABLE_DISCOVERY_SPEC` (inherits D2's interval and exposure-schedule fixes) |
| D6 | `DEFERRED` (insufficient diagnostic power — at most one testable historical episode) |

## Final mechanical pre-execution fix (2026-09-21)

`DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX` (reviewed commit
`475072d22f4c4631836ca7d38ccdc5da6ce59222`; full record:
`docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`)
corrected D3, D4's practical-threshold semantics, and D5 only; D1 and D6
unchanged:

- **D3** used HIGH/LOW-based functionals while its surrogate only ever
  produced a close-to-close path — a real/null observable mismatch.
  Redefined as **CLOSE-PATH morphology**, exactly three functionals:
  `MAX_UPSIDE_CLOSE_24H`, `MAX_DOWNSIDE_CLOSE_24H`,
  `TIME_TO_MAX_ABS_CLOSE_EXCURSION`. `PATH_ASYMMETRY` removed (the
  original card allowed at most 2-3 functionals; the prior correction
  had accidentally expanded to 4).
- **D4**'s `ROLLING_CORRELATION_90D` practical-magnitude threshold made
  mathematically exact: `PRACTICAL_EXCESS_RANGE =
  OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN >= 0.15`. Statistical
  gate unchanged.
- **D5**'s "beats best component" check corrected to compare against
  `COMPONENT_A_DELTA_FOR_D5` / `COMPONENT_B_DELTA_FOR_D5` (both on D5's
  exact common interval `2022-02-01 → 2025-01-01`), not D2 RULE_1's
  unrestricted full-2020-2024 result.

**Current final status:**

| Card | Status |
|---|---|
| D1 | `BLOCKED_PENDING_PRE_OUTCOME_FIX` (unchanged) |
| D2 | `EXECUTABLE_DISCOVERY_SPEC` (unchanged) |
| D3 | `EXECUTABLE_DISCOVERY_SPEC` (close-path fix applied) |
| D4 | `EXECUTABLE_DISCOVERY_SPEC`, **ROLLING_CORRELATION_90D only** (practical gate now exact) |
| D5 | `EXECUTABLE_DISCOVERY_SPEC` (common-window comparison fix applied) |
| D6 | `DEFERRED` (unchanged) |

Each card section below retains its original text as historical record,
with `red_team_correction_2026_09_21`, `pre_execution_correction_2026_09_21`
(D3/D4), and `mechanical_pre_execution_fix_2026_09_21` (D3/D4/D5) blocks
layered on top in the JSON twin recording exactly what changed and why.
Read the corrections alongside the original text, not as a silent
replacement of it.

## Dataset authorities referenced

| Dataset | Snapshot ID | Materialized range | Status |
|---|---|---|---|
| `CORE_BTC_BINANCE_V0` | `717d37a4...8dd415` | 2020-01-01 → 2026-08-26 (excl.) | `ACCEPTED_FOR_DISCOVERY` |
| `CORE_ETH_BINANCE_V0` | `4b9c113f...c85ad15` | 2020-01-01 → 2026-08-26 (excl.) | `ACCEPTED_FOR_DISCOVERY`, BTC companion |

The materialized snapshots physically extend past 2025-01-01. This
compilation does **not** authorize querying that later portion: every card
below freezes its own discovery interval ending no later than
`2025-01-01T00:00:00Z`, independent of what the raw snapshot contains, so
protected 2025/2026 stays unopened.

Cards reuse already-frozen MARKET-06 evaluator functions
(`rv_btc_24h`, `btc_ret_24h`, `btc_side_from_ret`, `robust_dislocation_z`,
`REFERENCE_COUNT`, `RV_RETURN_COUNT`, `FUTURE_BARS`, `BAR_MS`) for bar
construction and observables, rather than re-deriving them. This reads
MARKET-06 code; it does not modify it.

**Global discovery interval default** (D1, D2, D3, D4, D5): `2020-02-01T00:00:00Z
-> 2025-01-01T00:00:00Z` — the exact H01/H02 development window already
recorded as `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`, ending
exactly where protected territory begins.

## D1 — `STRUCTURAL_STATE_DETECTION` — `EXECUTABLE_DISCOVERY_SPEC`

- **Dataset:** `CORE_BTC_BINANCE_V0` (snapshot `717d37a4...8dd415`).
- **Interval:** global default.
- **Unit of observation:** one 24h decision point on the existing
  MARKET-06 grid.
- **State definition:** `HIGH_VOL_STATE(t) = 1` if `RV_20(t) >
  median(RV_20(t-250..t-1))`, else `LOW_VOL_STATE(t)`. `RV_20` sums 20
  trailing `ev.rv_btc_24h` values; baseline is the trailing 250 completed
  `RV_20` values (t excluded). Fixed at 2 states, no k sweep.
- **Search surface:** exactly this one construction (window=20,
  baseline=250, k=2 fixed).
- **Target functional:** `MEAN_STATE_RUN_LENGTH` = average of mean
  consecutive-day run lengths of HIGH_VOL_STATE and LOW_VOL_STATE.
- **Null:** GARCH(1,1) with Student-t innovations, fit on the discovery
  interval; circular block-bootstrap of standardized residuals (block
  length 20, matched to the RV window), reinjected through the fitted
  conditional-variance recursion. 1000 replicates, seed
  `D1_NULL_SURROGATE_SEED = 20260921101`. Preserves short-memory vol
  clustering (not under test); destroys longer-horizon regime persistence
  (the structure under test) — a standard, defensible surrogate-testing
  construction, not claimed to be the only one.
- **Temporal breakdown:** 2020 (partial), 2021, 2022, 2023, 2024, plus
  pooled.
- **Promising Prototype fields:** observed statistic above the surrogate
  97.5th percentile; exceeds surrogate median by ≥1.5 days; survives two
  pre-declared companion block lengths (15, 25) at ≥90th percentile; ≥3 of
  5 year-buckets individually exceed their own 90th percentile; no
  lookahead in RV/median construction.

## D2 — `CONDITIONAL_ABSTENTION_TAIL_RISK` — `EXECUTABLE_DISCOVERY_SPEC`

- **Dataset / interval / unit:** as D1, daily grid.
- **Rules:** `RULE_1 (RV_ABSTENTION)`: abstain if `rv_btc_24h(t) >` its own
  trailing-250 P90. `RULE_2 (DISLOCATION_ABSTENTION)`: abstain if
  `robust_dislocation_z(t) > 2.0`. Evaluated independently.
- **Search surface:** exactly these two rules at these fixed thresholds.
- **Target:** `DELTA` = mean adverse-path severity on abstained days minus
  mean adverse-path severity on `RATE_MATCHED_RANDOM_ABSTENTION` control's
  abstained days.
- **Baseline/control:** primary = `RATE_MATCHED_RANDOM_ABSTENTION`
  (year-matched random abstention at the rule's own rate, 1000 replicates);
  secondary reference only = never-abstain distribution.
- **Temporal breakdown:** per-year 2020-2024, per rule.
- **Promising Prototype fields:** DELTA above the random-control 95th
  percentile; ≥20% relative to the secondary baseline; ≥3 of 5 years
  individually positive; confirmed reuse of unmodified `rv_btc_24h` /
  `robust_dislocation_z`.
- **Seed:** `D2_RANDOM_CONTROL_SEED = 20260921102`.

## D3 — `PATH_MORPHOLOGY` — `EXECUTABLE_DISCOVERY_SPEC`

- **Descriptor choice (outcome-blind):** `UNCONDITIONAL_DESIGN` — chosen
  now to avoid introducing an unreviewed new descriptor degree of freedom
  in the same pass that must freeze five other cards.
- **Dataset / interval:** as D1. **Unit:** one forward 24h path (288 5m
  bars) per decision time.
- **Functionals (exactly 3):** `MAX_ADVERSE_EXCURSION_24h`,
  `TIME_TO_MAX_ADVERSE_EXCURSION`, `PATH_ASYMMETRY` (ratio of max adverse
  to max favorable excursion). If any functional collapses to terminal
  24h return/MAE on inspection, it is reported `INVALID_DISCOVERY`, not
  silently redefined.
- **Baseline/control:** reuses D1's exact GARCH(1,1) surrogate family
  (same fit, block length 20), applied to surrogate paths; same 3
  functionals computed on surrogates.
- **Temporal breakdown:** per-year 2020-2024.
- **Promising Prototype fields:** empirical mean outside surrogate
  [2.5th, 97.5th] band; ≥15% deviation from surrogate median; ≥3 of 5
  years same-direction; no terminal-return collapse.
- **Seed:** `D3_NULL_SURROGATE_SEED = 20260921103` (independent draw,
  D1's methodology).

## D4 — `BTC_ETH_RELATIVE_STRUCTURE` — `EXECUTABLE_DISCOVERY_SPEC`

- **Dataset:** `CORE_BTC_BINANCE_V0` + `CORE_ETH_BINANCE_V0` (companion
  snapshots verified matching).
- **Interval:** global default, or later if ETH's own available history
  starts later (an execution-time data-range check, not an outcome
  inspection).
- **Functionals (exactly 2):** `ROLLING_CORRELATION_90D` (90-point
  rolling Pearson correlation of BTC/ETH 24h returns);
  `LEAD_LAG_1DAY` (BTC(t) vs ETH(t+1), one frozen lag, no sweep).
- **Baseline/control:** whole-sample unconditional correlation
  (reference); `BLOCK_BOOTSTRAP_PAIRED_RETURNS` null (circular block
  bootstrap of paired BTC/ETH daily-return vectors, block length 20, 1000
  replicates) for both the rolling-correlation-variance test and the
  lead-lag test.
- **Temporal breakdown:** per-year 2020-2024.
- **Promising Prototype fields:** rolling-correlation variance above the
  null's 97.5th percentile, or `|LEAD_LAG_1DAY|` above its null's 97.5th
  percentile; ≥0.15 correlation-point swing beyond null noise; not
  confined to one year. Any positive result remains a two-asset precursor
  only, never cross-sectional (R-C) evidence.
- **Seed:** `D4_NULL_SEED = 20260921104`.

## D5 — `COMPOSED_DECISION_MECHANISM` — `EXECUTABLE_DISCOVERY_SPEC`

- **Independence justification:** components are chosen on structural
  availability grounds, not performance grounds — at compile time zero
  D1-D4 outcomes exist anywhere (this compilation strictly precedes
  execution of any card), so a performance-based choice is impossible by
  construction. D2's `RULE_1` and `RULE_2` are the only two fully
  specified, already-frozen binary decision rules in the sprint; D1/D3/D4
  characterize state/path/relative-structure and yield no binary
  abstain/expose rule at all, so they are not even candidate components.
- **Components:** Component A = D2 `RULE_1` verbatim. Component B = D2
  `RULE_2` verbatim. Neither retuned.
- **Composition operator:** `OR` (abstain if either fires). `AND` is
  explicitly not tested in this sprint.
- **Search surface:** exactly this one composition of exactly these two
  components at their existing D2 parameterization.
- **Target:** reuses D2's exact `DELTA` definition, applied to the
  composed rule.
- **Baseline/control:** `RATE_MATCHED_RANDOM_ABSTENTION` (D2's exact
  methodology, 1000 replicates); composed `DELTA` must also beat both
  individual components' own `DELTA` from D2.
- **Temporal breakdown:** same per-year structure as D2.
- **Promising Prototype fields:** composed DELTA above the 95th
  percentile of its own random-control distribution; ≥20% relative
  magnitude bar; beats both individual components. **Multiple-testing
  note:** this is a third look at the RV/dislocation family (after D2's
  two rules); any future confirmatory proposal from D5 must account for
  that multiplicity jointly across D2A/D2B/D5.
- **Seed:** `D5_RANDOM_CONTROL_SEED = 20260921105`.

## D6 — `EXTERNAL_MECHANISM_BENCHMARK` — `EXECUTABLE_DISCOVERY_SPEC`

- **Selection basis:** chosen for being fully reconstructible from
  `CORE_BTC_BINANCE_V0` alone (no new acquisition), publicly documented
  with a stated formula, and materially different from MARKET-03. Not
  chosen by comparing candidates' reproduction performance — none has
  been run.
- **Pinned source:** "Pi Cycle Top Indicator" — 111-day SMA crossing above
  2× the 350-day SMA of BTC price, publicly documented (Philip Swift /
  LookIntoBitcoin). No repository/paper version exists; the citable
  version is the canonical public formula, no proprietary variant.
- **Externally stated mechanism:** the crossover has historically
  coincided closely with BTC cycle tops (2013, 2017, 2021 per the
  source's public description).
- **Externally stated target:** calendar-day proximity between a
  crossover date and the subsequent realized local BTC price top.
- **Externally stated comparator:** none published — recorded as an
  explicit limitation, not filled in silently. Signalbot supplies its own
  naive comparator below.
- **Dataset / interval:** `CORE_BTC_BINANCE_V0` daily closes, full
  available history capped at `2025-01-01T00:00:00Z` to keep protected
  2025/2026 unopened. **Known limitation:** the source's 2013/2017
  coincidences predate this dataset's coverage and cannot be reproduced;
  only 2020-2025 crossovers (expected: at most the 2021 cycle-top region)
  are reproducible. Reported, not concealed.
- **Search surface:** reproduction of the externally specified crossover
  only; no SMA-length or multiplier variant search.
- **Signalbot-supplied comparator:** proximity between the nearest local
  BTC max and a random date drawn from a ±180-day window, 1000 replicates,
  seed `D6_COMPARATOR_SEED = 20260921106`.
- **Temporal breakdown:** per discrete crossover event found in-window
  (expected to be few discrete events, not a continuous year series).
- **Promising Prototype fields:** observed proximity closer than ≥95% of
  the 1000 random-date replicates. Diagnostic use only — calibrates the
  pipeline's own baseline/gate design; never counted as internal
  discovery, only toward `EXTERNAL_PROMISING_OR_REPRODUCED`.

## `CROSS_SECTIONAL_PANEL_FEASIBILITY` sidecar — finalized spec

Still outcome-blind; no signal/outcome statistics computed. For each of
the six questions (point-in-time universe availability, listing/delisting
reconstruction, survivorship controls, liquidity eligibility data,
approximate panel size, acquisition/engineering cost), this unit freezes
only the **method** by which it will later be answered (venue listing
metadata, cross-referenced against the repo's existing archive inventory,
as-of construction, simple cardinality counting once eligibility is
defined, and cost scaled from the known CORE_BTC/CORE_ETH acquisition
effort). No numeric answers are computed here.

## Sprint execution manifest

**Superseded by `DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX`**
(reviewed commit `475072d`) — see the correction tables above for the
current status. Full lineage, for record:

| Card | Original | After red-team review (7bb92b0) | After pre-exec correction (355a165) | After mechanical fix (475072d) |
|---|---|---|---|---|
| D1 | `EXECUTABLE_DISCOVERY_SPEC` | `BLOCKED_PENDING_PRE_OUTCOME_FIX` | unchanged | unchanged |
| D2 | `EXECUTABLE_DISCOVERY_SPEC` | `EXECUTABLE_DISCOVERY_SPEC` (fixed) | unchanged | unchanged |
| D3 | `EXECUTABLE_DISCOVERY_SPEC` | `EXECUTABLE_DISCOVERY_SPEC` (fixed) | unsigned + time-of-day-stratified | `EXECUTABLE_DISCOVERY_SPEC` (close-path, 3 functionals) |
| D4 | `EXECUTABLE_DISCOVERY_SPEC` | `EXECUTABLE_DISCOVERY_SPEC` (fixed) | `ROLLING_CORRELATION_90D` only | `EXECUTABLE_DISCOVERY_SPEC` (practical gate exact) |
| D5 | `EXECUTABLE_DISCOVERY_SPEC` | `EXECUTABLE_DISCOVERY_SPEC` (fixed) | unchanged | `EXECUTABLE_DISCOVERY_SPEC` (common-window comparison) |
| D6 | `EXECUTABLE_DISCOVERY_SPEC` | `DEFERRED` | unchanged | unchanged |

`executable_count = 4` (D2, D3, D4 [rolling-correlation only], D5).
`blocked_count = 1` (D1). `deferred_count = 1` (D6).
`zero_useful_cards_executable = false`.

`SCIENTIFIC_OUTCOMES_COMPUTED = false`. `CANDIDATE_PERFORMANCE_INSPECTED =
false`. `MARKET_07_CREATED = false`. `PROTECTED_2025_OPENED = false`.
`PROTECTED_2026_OPENED = false`.

`NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5`.
D1 remains `BLOCKED_PENDING_PRE_OUTCOME_FIX` (pending
`D1_NULL_ADEQUACY_GATE_EXECUTION`) and D6 remains `DEFERRED` (pending
`D6_REPLACEMENT_BENCHMARK_SELECTION`); D4's `LEAD_LAG_1DAY` remains
`DEFERRED_FROM_SPRINT_01`. Neither D1 nor D6 was changed by this unit.
