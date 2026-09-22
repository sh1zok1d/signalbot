# Discovery Sprint 01

**Unit:** `DISCOVERY_SPRINT_01`
**Parent unit:** `HYPOTHESIS_DISCOVERY_PIPELINE_V2`
**Parent selection commit:** `a711086c36eb7129fc3f0660732049de93dd1629`
**Date:** 2026-09-21
**Status:** `PARTIAL_SPRINT_EXECUTED_ONE_PROMISING_PROTOTYPE`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01.json`

Six discovery cards were defined in this document. Four INTERNAL cards
have now executed as **adaptive discovery** on historically exposed
2020-2024 data — not confirmatory evidence:

- D2 = `PROMISING_PROTOTYPE`
- D3 = `NO_USEFUL_STRUCTURE`
- D4 = `NO_USEFUL_STRUCTURE`
- D5 = `NO_USEFUL_STRUCTURE`
- D1 is `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH` (adequacy gate not executed)
- D6 remains `DEFERRED`

Card definitions below are the frozen specification. Later sections
preserve the definition-time narrative and the execution history.

Each card follows the Discovery Card contract from
`HYPOTHESIS_DISCOVERY_PIPELINE_V2`.

## D1 — `STRUCTURAL_STATE_DETECTION`

This card **is** the previously-selected R-A, reclassified as a discovery
card rather than a confirmatory hypothesis.

- **MECHANISM_CLASS:** low-dimensional, price-derived, discrete state
  representation of BTC's own path.
- **INFORMATION_SOURCE:** `CORE_BTC_BINANCE_V0` price path only; no new
  acquisition.
- **FUNCTION:** state detection (not alpha/return prediction).
- **TARGET_FAMILY:** discrete state labels / transition-persistence
  structure. No return/MAE/alpha target.
- **TIME_SCALE:** single frozen time scale, chosen outcome-blind.
- **UNIT_OF_OBSERVATION:** one bar/window on the frozen time scale, CORE
  BTC only.
- **MARKET_RELATIONSHIP:** indirect precondition study only; a positive
  state model is not itself an edge claim.
- **SIMPLE_BASELINE:** a frozen lower-order surrogate/null (see null-model
  risk below), chosen outcome-blind.
- **SMALL_SEARCH_SURFACE:** exactly one state-construction class; no
  cluster shopping; no k-sweeping; no post hoc feature-family selection.
- **KNOWN_PRIOR_EXPOSURE:** the price tier was adaptively used by H01/H02
  and confirmatorily consumed by MARKET-01/02/05/06, but never previously
  for a state-detection function.
- **WHAT_A_NULL_DEPRIORITIZES:** only the tested class of low-dimensional,
  price-derived, discrete state representations at the frozen construction.
  Does not close continuous conditioning, other constructions, other time
  scales, cross-sectional structure, order-book regimes, latent states
  outside CORE BTC, or "BTC regimes" generally.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** proposing (not creating) a future
  confirmatory hypothesis conditioning a downstream target on the detected
  state.
- **RESEARCHER_DOF:** HIGH — the primary blocker (cluster shopping, k
  selection, feature-window choice).
- **MAX_ENGINEERING_SCOPE:** one state-construction implementation plus one
  frozen surrogate/null implementation; no additional feature families.

**Null-model risk (carried over from the R-A selection unit):** a null
preserving only marginal distribution + linear autocorrelation is not
automatically acceptable if the candidate representation uses volatility
clustering, vol-of-vol, RV term structure, path roughness, or nonlinear
temporal dependence — such a null can mechanically destroy the very
second-order structure under test and manufacture a guaranteed positive
contrast. The null must preserve every lower-order structure not being
claimed as regime structure, and must be chosen outcome-blind.

Data label: `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

## D2 — `CONDITIONAL_ABSTENTION_TAIL_RISK`

- **MECHANISM_CLASS:** conditional abstention / tail-risk filtering on
  observable families MARKET-05/06 tested as additive predictors.
- **INFORMATION_SOURCE:** CORE BTC own-state observables plus the
  cross-asset/cross-venue observables MARKET-05 and MARKET-06 used.
- **FUNCTION:** filtering / risk reduction — explicitly exploratory, and
  explicitly **not** a claim that MARKET-05/06's null observables have been
  "rescued."
- **TARGET_FAMILY:** filtered-vs-unfiltered adverse-path exposure
  distributions. No additive-linear-term/MAE-improvement target — that
  exact cell is `REPEATED_NULL / LOW_PRIORITY_FOR_NOW` and this card must
  not reintroduce it.
- **TIME_SCALE:** same 24h horizon as MARKET-05/06, reused as a time scale
  only.
- **UNIT_OF_OBSERVATION:** one day (BTC daily grid).
- **MARKET_RELATIONSHIP:** indirect; an exploratory screen, not an edge
  claim.
- **SIMPLE_BASELINE (corrected 2026-09-21):** PRIMARY comparator is
  `RATE_MATCHED_RANDOM_ABSTENTION` — a random abstention control that
  abstains on the same number/share of decision rows as the candidate
  rule, with temporal composition matched where feasible. This tests
  whether the rule selects **which** exposures to avoid better than
  random abstention, not whether taking less exposure differs from taking
  all exposure. The never-abstain / unconditional distribution over the
  same period may remain only as a **secondary reference**, never the
  primary comparator. This is a pre-outcome design correction; no
  scientific outcome is computed by it.
- **SMALL_SEARCH_SURFACE:** one or two frozen, pre-stated
  abstention-threshold rules per already-used observable family; no new
  observable families; no threshold sweep beyond the pre-stated set.
- **KNOWN_PRIOR_EXPOSURE:** observable families and the 2020-2024 surface
  were adaptively used by H01/H02 and confirmatorily consumed by MARKET-05
  and MARKET-06 at the additive-linear-term function.
- **WHAT_A_NULL_DEPRIORITIZES:** filtering/abstention use of these specific
  observable families at this horizon, independent of their already
  established null as additive predictors.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** proposing a future confirmatory
  abstention-rule hypothesis on an independent surface (the 2020-2024
  exposure means this card cannot itself be confirmatory evidence).
- **RESEARCHER_DOF:** MEDIUM-HIGH — threshold choice and rule construction,
  bounded by the small search surface.
- **MAX_ENGINEERING_SCOPE:** reuse of existing MARKET-05/06 observable
  construction code; one filtering-rule evaluation script; no new data
  acquisition.

This card is the explicit exercise of the a711086 R-B routing correction:
R-B may be explored on historically exposed data under discovery
feasibility; any resulting pattern remains exploratory and requires an
independent future confirmation surface.

Data label: `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

## D3 — `PATH_MORPHOLOGY`

- **MECHANISM_CLASS:** trajectory / path characterization of BTC price
  paths over a fixed forward window.
- **INFORMATION_SOURCE:** `CORE_BTC_BINANCE_V0` price path only.
- **FUNCTION:** trajectory/path characterization (not terminal-return
  prediction). Examples: adverse/favorable excursion, time-to-extreme,
  path asymmetry.
- **TARGET_FAMILY:** path-shape functionals conditioned on a simple, frozen
  prior-state descriptor. Must not reduce to predicting the terminal 24h
  return/MAE — a candidate that collapses to that must be reported
  `INVALID_DISCOVERY`, not silently redefined.
- **TIME_SCALE:** same 24h forward window used elsewhere in the program,
  for comparability, scored on path shape.
- **UNIT_OF_OBSERVATION:** one forward-looking 24h path per decision time.
- **MARKET_RELATIONSHIP:** indirect; could plausibly inform future
  execution/risk work, but no such claim is made here.
- **SIMPLE_BASELINE:** path-shape statistics of an unconditional
  (state-blind) sample of 24h paths over the same period.
- **SMALL_SEARCH_SURFACE:** two or three pre-stated path functionals; no
  functional-family fishing; no post hoc redefinition after inspecting
  results.

**Execution bound (added 2026-09-21): D3 is NOT EXECUTABLE** until exactly
one prior-state descriptor (or an explicit unconditional design) is frozen
outcome-blind. No selecting a descriptor after viewing path-morphology
results. The descriptor is deliberately not chosen in this corrective unit
— choosing it is a separate future step that must itself be outcome-blind.
- **KNOWN_PRIOR_EXPOSURE:** 24h-forward windows were used by MARKET-05/06
  for a terminal MAE target, but never previously for a path-shape
  functional.
- **WHAT_A_NULL_DEPRIORITIZES:** path-shape functionals as a useful
  conditioning target at this horizon and data tier.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** proposing a future confirmatory
  path-morphology hypothesis, with its own fresh-surface and feasibility
  review.
- **RESEARCHER_DOF:** MEDIUM — functional choice, bounded by the small
  search surface.
- **MAX_ENGINEERING_SCOPE:** path-functional computation script reusing
  existing bar-construction code; no new data acquisition.

Data label: `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

## D4 — `BTC_ETH_RELATIVE_STRUCTURE`

- **MECHANISM_CLASS:** two-asset relative/relational structure between BTC
  and ETH.
- **INFORMATION_SOURCE:** `CORE_BTC` and `CORE_ETH` price paths (the only
  two instruments with an existing core historical tier).
- **FUNCTION:** relative relationship characterization (e.g. lead-lag,
  relative strength, co-movement regime) — explicitly a two-asset
  exploratory precursor only.
- **TARGET_FAMILY:** BTC-ETH relative-structure functionals. Not a
  cross-sectional panel statistic.
- **TIME_SCALE:** same conventions as D1/D3, chosen outcome-blind.
- **UNIT_OF_OBSERVATION:** one BTC-ETH paired observation per decision
  time.
- **MARKET_RELATIONSHIP:** indirect; any pattern is a two-asset curiosity,
  not evidence about broader cross-sectional structure.
- **SIMPLE_BASELINE:** unconditional BTC-ETH correlation/co-movement
  statistic over the same period.
- **SMALL_SEARCH_SURFACE:** one or two pre-stated relative-structure
  functionals; no combinatorial lag search.
- **KNOWN_PRIOR_EXPOSURE:** CORE BTC/ETH tiers exist from prior work, but
  no prior MARKET unit tested BTC-ETH relative structure as a function.
- **WHAT_A_NULL_DEPRIORITIZES:** simple BTC-ETH pairwise relative-structure
  functionals as a useful mechanism at this time scale.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** motivating the case for
  eventually funding real cross-sectional panel acquisition — **not** a
  claim that two-asset relative structure equals cross-sectional (R-C)
  evidence.
- **RESEARCHER_DOF:** MEDIUM — functional and lag choice, bounded by the
  small search surface.
- **MAX_ENGINEERING_SCOPE:** one relative-structure computation script
  reusing existing CORE BTC/ETH loaders; no new data acquisition.

This card is explicitly **not** equivalent to true cross-sectional panel
evidence (R-C); it is a two-asset precursor only.

Data label: `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

## D5 — `COMPOSED_DECISION_MECHANISM`

- **MECHANISM_CLASS:** composed rule/filter combining two or more
  already-explored observable families into one decision mechanism.
- **INFORMATION_SOURCE:** observable families already used in
  MARKET-01/02/05/06 and/or D1-D4, composed rather than searched for anew.
- **FUNCTION:** composed rule/filter — very small, frozen search surface;
  no combinatorial interaction mining.
- **TARGET_FAMILY:** filtered/composed decision outcome, mirroring D2's
  filtering framing across more than one observable family.
- **TIME_SCALE:** same 24h horizon used elsewhere in the program.
- **UNIT_OF_OBSERVATION:** one day (BTC daily grid), same as D2/MARKET-05/06.
- **MARKET_RELATIONSHIP:** indirect and explicitly high-risk — composed/
  interaction claims are the easiest to construct after the fact to look
  meaningful.
- **SIMPLE_BASELINE:** each individual component rule evaluated alone (the
  composition must beat its best individual component, not just beat doing
  nothing).
- **SMALL_SEARCH_SURFACE:** exactly one pre-stated composition of exactly
  two pre-stated component rules; no combinatorial search over which
  components to combine; no interaction mining across the full observable
  set.
- **KNOWN_PRIOR_EXPOSURE:** every component observable family has already
  been adaptively and/or confirmatorily used on the 2020-2024 surface. This
  card composes previously tested pieces; it does not introduce a new
  information source.
- **WHAT_A_NULL_DEPRIORITIZES:** this specific pre-stated two-component
  composition as a useful decision mechanism — narrow by design, given the
  high rescue risk of this mechanism class.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** extremely cautious — a future
  confirmatory test would require an independent surface AND explicit
  multiple-testing accounting across everything already tried in this
  program at this cell. A positive result here alone does not justify
  skipping that accounting.
- **RESEARCHER_DOF:** HIGH — composed/interaction mechanisms carry the
  highest post hoc rescue and multiple-testing risk in the sprint; recorded
  explicitly, not minimized.
- **MAX_ENGINEERING_SCOPE:** one composition-evaluation script reusing
  existing component implementations; no new observable families; no
  parameter retuning of the component rules.

This card is the explicit exercise of the a711086 R-F routing correction:
R-F may be explored only under a tightly bounded search surface, with HIGH
rescue/multiple-testing risk explicitly recorded, not merely because
individually-null variables might interact.

**Anti-adaptive-composition bound (added 2026-09-21):** D5 may **not**
select its two components based on observed D1-D4 results from the same
sprint. Before D5 execution, exactly two component rules, their
parameterization, and the composition operator must be frozen without
reference to D1-D4 scientific outcomes. If this cannot be done cleanly, D5
must be **DEFERRED** rather than assembled from whichever prior cards
looked promising. No components have been selected in this corrective
unit.

Data label: `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.

## D6 — `EXTERNAL_MECHANISM_BENCHMARK`

- **MECHANISM_CLASS:** externally/publicly sourced mechanism used
  diagnostically to calibrate the discovery process itself, not to search
  for a new internal edge.
- **INFORMATION_SOURCE:** a publicly documented external mechanism or
  strategy, materially different in construction from the MARKET-03
  external reproduction.
- **FUNCTION:** diagnostic benchmark reproduction — checks whether the
  discovery process (search surface, baseline, prototype gate) correctly
  identifies a mechanism already known externally to have some structure.
- **TARGET_FAMILY:** whatever target family the external source itself
  defines, reproduced as faithfully as feasible.
- **TIME_SCALE / UNIT_OF_OBSERVATION:** whatever the external source
  defines.
- **MARKET_RELATIONSHIP:** diagnostic only.
- **SIMPLE_BASELINE:** the external source's own stated naive/unconditional
  comparator, where available.
- **SMALL_SEARCH_SURFACE:** reproduction of the externally specified
  mechanism only; no internal variant search.
- **KNOWN_PRIOR_EXPOSURE:** materially different from MARKET-03; this
  card's external source and construction must differ materially, not
  merely be renamed.
- **WHAT_A_NULL_DEPRIORITIZES:** nothing about internal mechanism-space
  priority — a null says only that this external benchmark did not
  reproduce as expected, itself diagnostic about pipeline sensitivity.
- **WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT:** confidence calibration only —
  evidence the pipeline's baseline/search-surface/prototype-gate design is
  not so conservative it would miss real structure. Must **not** be
  recorded as an internal discovery success.
- **RESEARCHER_DOF:** LOW — the mechanism is externally specified.
- **MAX_ENGINEERING_SCOPE:** one reproduction script following the external
  source's published methodology; no internal extension.

This card must **not** count toward `INTERNAL_DISCOVERY_CARDS` or
`INTERNAL_PROMISING_PROTOTYPES`. It belongs only to
`EXTERNAL_BENCHMARK_CARDS` / `EXTERNAL_PROMISING_OR_REPRODUCED`, exactly as
MARKET-03 belongs only to external evidence/history.

**Pinning bound (added 2026-09-21): D6 is NOT EXECUTABLE** until one
external/public source is selected and pinned before inspecting its
reproduction outcome. Must freeze: source identity / URL / repository
commit or paper version; externally stated mechanism; externally stated
target; externally stated comparator where available. No browsing multiple
external candidates and selecting based on Signalbot performance. No
source has been selected in this corrective unit.

Data label: `EXTERNAL_SOURCE_NOT_HISTORICALLY_EXPOSED_INTERNAL_DATA`.

## Cross-Sectional Panel Feasibility sidecar

`CROSS_SECTIONAL_PANEL_FEASIBILITY` — explicitly **not** one of the six
discovery cards. An outcome-blind feasibility sidecar only; no
signal/outcome statistics computed.

Questions to answer later (not now): point-in-time universe availability;
listing/delisting reconstruction; survivorship controls; liquidity
eligibility data; approximate panel size; acquisition/engineering cost.

Status: `NOT_STARTED_NO_ANSWERS_RECORDED_IN_THIS_UNIT`.

## Program diagnostic state after this unit

**Definition-time record** (when this document was a specification-only
unit; not current routing):

| Counter | Value |
|---|---|
| `INTERNAL_DISCOVERY_CARDS_PLANNED` | 5 (D1-D5) |
| `INTERNAL_PROMISING_PROTOTYPES` | 0 |
| `EXTERNAL_BENCHMARK_CARDS_PLANNED` | 1 (D6) |
| `EXTERNAL_PROMISING_OR_REPRODUCED` | 0 |

Those counters reflected card **definition/planning** only — no card had
been executed in the definition unit.

**Current program diagnostic** (after D1 null-adequacy adjudication; D2–D5 unchanged):

| Counter | Value |
|---|---|
| `INTERNAL_DISCOVERY_CARDS_PLANNED` | 5 (D1-D5) |
| `INTERNAL_DISCOVERY_CARDS_EXECUTED` | 4 (D2, D3, D4 rolling, D5) |
| `INTERNAL_PROMISING_PROTOTYPES` | 1 (D2) |
| `INTERNAL_DISCOVERY_WARNING` | `null` |
| `D1_STATUS` | `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH` |
| `D2_STATUS` | `PROMISING_PROTOTYPE` |
| `D3_STATUS` | `NO_USEFUL_STRUCTURE` |
| `D4_STATUS` | `NO_USEFUL_STRUCTURE` |
| `D5_STATUS` | `NO_USEFUL_STRUCTURE` |
| `D6_STATUS` | `DEFERRED` |

`SCIENTIFIC_OUTCOMES_COMPUTED = true` (adaptive discovery, not confirmatory).
`MARKET_07_CREATED = false`.
`PROTECTED_2025_OPENED = false`. `PROTECTED_2026_OPENED = false`.
`NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.

### Stall-gate semantics (corrected 2026-09-21)

D6 is `EXTERNAL_BENCHMARK`, diagnostic only, and never counts toward the
6-10 internal-card stall rule — exactly as MARKET-03 never counts as
internal discovery. `DISCOVERY_SPRINT_01` plans only 5 internal cards
(D1-D5), so completion of Sprint 01 alone **cannot** trigger
`INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED` solely because D1-D5 all
fail — the formal gate requires at least 6 materially orthogonal internal
cards (i.e. a Discovery Sprint 02+ internal card beyond D1-D5).

If D1-D5 all return `NO_USEFUL_STRUCTURE` / `INCONCLUSIVE_DISCOVERY` /
`INVALID_DISCOVERY` with zero `PROMISING_PROTOTYPE`, the correct record is
the interim warning `INTERNAL_DISCOVERY_WARNING =
ZERO_PROMISING_AFTER_FIRST_5_INTERNAL_CARDS`, not the formal
`INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED` gate.

`SCIENTIFIC_OUTCOMES_COMPUTED = false` at definition time (historical).
Current value is `true` after the CORE-restore retry, still adaptive
discovery rather than confirmatory evidence.
`MARKET_07_CREATED = false`.
`PROTECTED_2025_OPENED = false`. `PROTECTED_2026_OPENED = false`.
Definition-time `NEXT_UNIT = DISCOVERY_SPRINT_01_CARD_EXECUTION` is
historical; current `NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.

## Corrective unit (2026-09-21)

A narrow, pre-outcome design correction was applied on top of commits
`a711086c36eb7129fc3f0660732049de93dd1629` and
`954fb550aa56682708a7673e2b548182ba2f965d`, without rewriting either:

1. D2's primary comparator corrected to `RATE_MATCHED_RANDOM_ABSTENTION`;
   the unconditional distribution demoted to a secondary reference.
2. D3 marked not executable until a prior-state descriptor (or explicit
   unconditional design) is frozen outcome-blind.
3. D5 marked not executable with adaptively-selected components; its two
   components, parameterization, and composition operator must be frozen
   without reference to D1-D4 outcomes, or the card must be deferred.
4. D6 marked not executable until one external source is pinned before
   inspecting its reproduction outcome.
5. Internal/external card counters renamed to `*_PLANNED`; D6 explicitly
   excluded from the 6-10 internal-card stall gate; an interim
   `INTERNAL_DISCOVERY_WARNING` state introduced below the formal gate
   threshold.

No scientific outcome was computed by this correction.

## Spec compilation (2026-09-21)

All six cards were converted to fully frozen `EXECUTABLE_DISCOVERY_SPEC`
records (none deferred) in
`docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`. That unit
freezes exact dataset authority, discovery interval, unit of observation,
feature/state/rule definitions, small search surfaces, target functionals,
simple baselines/controls, temporal breakdowns, lightweight
`PROMISING_PROTOTYPE` evaluation fields, and deterministic seeds for each
card, still outcome-blind: no discovery outcome computed, no candidate
performance inspected, protected 2025/2026 unopened, no MARKET-07.

`NEXT_UNIT = DISCOVERY_SPRINT_01_EXECUTION`.

## Red-team review (2026-09-21)

`DISCOVERY_SPRINT_01_RED_TEAM_REVIEW` (reviewed commit `7bb92b0`) found
seven suspected defects (F1-F7) in the spec compilation above. F1, F2,
F3, F4, F6 were confirmed and fixed outcome-blind (per-rule legal
intervals + cross-venue dataset authority for D2/D5; explicit base
exposure schedule for D2/D5; a corrected native-5m-granularity null for
D3; a split null for D4's lead-lag vs. rolling-correlation functionals;
a corrected variance-level RV_20 formula for D1). F5 found the D1 null's
defensibility had been asserted, not verified — a `D1_NULL_ADEQUACY_GATE`
is now defined (non-target statistics only) but not yet executed. F7
found D6's diagnostic value insufficient (at most one testable historical
episode).

**Updated status:** D1 `BLOCKED_PENDING_PRE_OUTCOME_FIX`; D2/D3/D4/D5
`EXECUTABLE_DISCOVERY_SPEC`; D6 `DEFERRED`.

`NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4_D5`, gated
separately on `D1_NULL_ADEQUACY_GATE_EXECUTION` and
`D6_REPLACEMENT_BENCHMARK_SELECTION`.

Full record: `docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`.

## Final pre-execution correction (2026-09-21)

`DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4` (reviewed commit
`355a1657`) corrected D3 and D4 only; D1, D2, D5, D6 unchanged from the
red-team review above.

D3's `MAX_ADVERSE_EXCURSION_24h`/`TIME_TO_MAX_ADVERSE_EXCURSION` were
direction-aligned via `BTC_SIDE(t)`, contradicting D3's own
`UNCONDITIONAL_DESIGN` label and risking smuggled-in directional-
predictability structure (momentum/mean-reversion, already tested
elsewhere in the program) masquerading as "path morphology." Redefined
as genuinely unsigned: `MAX_UPSIDE_EXCURSION_24h`,
`MAX_DOWNSIDE_EXCURSION_24h`, `TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`
— no `BTC_SIDE` dependency at all. Separately, D3's null was found to
ignore UTC time-of-day; because every MARKET-06 decision point shares
the identical fixed UTC decision time (`00:05:00Z`), bar-offset directly
equals time-of-day, making `TIME_TO_MAX_EXCURSION` structurally a
time-of-day statistic — a near-certain confound with ordinary session
seasonality, shown outcome-blind from the frozen decision-grid design.
Corrected to `5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP`
(resampling stays within the same UTC hour-slot across historical days).
`PATH_ASYMMETRY` zero-denominator handling, `TIME_TO_MAX_EXCURSION` tie
handling, and the entry/reference convention were also frozen.

D4's `INDEPENDENT_BLOCK_BOOTSTRAP` lead-lag null (from the first review
round) was found to over-destroy: it kills not just the true
`BTC(t)→ETH(t+1)` cross-lag but also ordinary same-time common-factor
dependence, which is not the target being tested — no outcome-blind
demonstration exists that it isolates lead-lag specifically. Per the
preferred minimal resolution, `LEAD_LAG_1DAY` is
`DEFERRED_FROM_SPRINT_01` (no complex new lead-lag null was invented to
keep it); `ROLLING_CORRELATION_90D` is retained unchanged and cleanly
specified.

**Final status:** D1 `BLOCKED_PENDING_PRE_OUTCOME_FIX`; D2, D3, D5
`EXECUTABLE_DISCOVERY_SPEC`; D4 `EXECUTABLE_DISCOVERY_SPEC` scoped to
`ROLLING_CORRELATION_90D` only (`LEAD_LAG_1DAY` deferred); D6 `DEFERRED`.

`NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5`,
gated separately on `D1_NULL_ADEQUACY_GATE_EXECUTION`,
`D4_LEAD_LAG_REPLACEMENT_NULL_OR_PERMANENT_DEFERRAL`, and
`D6_REPLACEMENT_BENCHMARK_SELECTION`.

Full record: `docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`.

## Final mechanical pre-execution fix (2026-09-21)

`DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX` (reviewed commit
`475072d`) corrected D3, D4's practical-threshold semantics, and D5
only; D1 and D6 unchanged.

D3's real functionals used 5m bar HIGH/LOW values, but the frozen
surrogate (time-of-day-stratified 5m return block bootstrap) only ever
produces a close-to-close log-return path — a real/null observable
mismatch, without inventing synthetic intra-bar high/low. D3 is redefined
as **CLOSE-PATH morphology**, exactly three functionals:
`MAX_UPSIDE_CLOSE_24H`, `MAX_DOWNSIDE_CLOSE_24H`,
`TIME_TO_MAX_ABS_CLOSE_EXCURSION` (earliest bar offset attaining the max
of the two), both floored at zero. `PATH_ASYMMETRY` is removed (the
original card allowed at most 2-3 functionals; the previous correction
round had accidentally expanded to 4). The time-of-day-stratified null
itself is unchanged — it already generates exactly the close-path
observable this fix needs.

D4's `ROLLING_CORRELATION_90D` practical magnitude threshold is made
exact: `PRACTICAL_EXCESS_RANGE = OBSERVED_CORRELATION_RANGE -
NULL_RANGE_MEDIAN >= 0.15`, where `NULL_RANGE_MEDIAN` is the median,
across the 1000 bootstrap replicates, of each replicate's own
rolling-correlation range. The existing statistical variance-vs-null
gate is kept unchanged alongside it. `LEAD_LAG_1DAY` remains
`DEFERRED_FROM_SPRINT_01`.

D5's exact interval (`2022-02-01T00:05:00Z → 2025-01-01T00:00:00Z`) does
not match D2 RULE_1's own broader `2020-02-01 → 2025-01-01` interval, so
comparing D5's `DELTA` against RULE_1's full-interval result would not
be apples-to-apples. `COMPONENT_A_DELTA_FOR_D5` (RULE_1 re-evaluated on
D5's exact common window) and `COMPONENT_B_DELTA_FOR_D5` (RULE_2,
already on that same window) are frozen as the comparison inputs; D2
RULE_1's own broader result is unaffected and may still be separately
reported. This is a pre-declared, D5-scoped comparison, decided
outcome-blind.

**Final status:** D1 `BLOCKED_PENDING_PRE_OUTCOME_FIX`; D2, D3, D5
`EXECUTABLE_DISCOVERY_SPEC`; D4 `EXECUTABLE_DISCOVERY_SPEC` scoped to
`ROLLING_CORRELATION_90D` only; D6 `DEFERRED`.

`EXECUTION_AUTHORIZED = D2, D3, D4_ROLLING, D5`.
`NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5`.

Full record: `docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`.

## Partial execution (2026-09-21)

First authorized batch ran on `research/discovery-sprint-01-execution`
from main `067231e`, implementation commit `26d8f7066533bcae7138d5a1952783f2a16f3c39`.

Local preflight:

- `BTC_DATA_PRESENT = false` (`artifacts/research_data/CORE_BTC_BINANCE_V0` monthly parquet absent)
- `ETH_DATA_PRESENT = false`
- `M06_CROSS_VENUE_DATA_PRESENT = true` (36 Binance 5m zips 2022-01..2024-12 + 1053 OKX pages)

No online substitution and no new snapshot reconstruction.

Classifications (adaptive discovery only):

| Card | Classification |
|---|---|
| D2 | `BLOCKED_MISSING_LOCAL_DATA` |
| D3 | `BLOCKED_MISSING_LOCAL_DATA` |
| D4 `ROLLING_CORRELATION_90D` | `BLOCKED_MISSING_LOCAL_DATA` |
| D5 | `BLOCKED_MISSING_LOCAL_DATA` |

D2 RULE_2 (`DISLOCATION_ABSTENTION`) was attempted on retained MARKET-06 durable raw because that identity was present; D2 RULE_1 was not run. The frozen two-rule card therefore remains blocked rather than classified as a completed prototype/null. D4 `LEAD_LAG_1DAY` was not executed.

Program diagnostic (bookkeeping correction of result commit `37921089ce289cd9bcbcebb123724a3e033dcdc3`):

- `INTERNAL_DISCOVERY_CARDS_EXECUTED = 0`
- `INTERNAL_PROMISING_PROTOTYPES = 0`
- `INTERNAL_DISCOVERY_WARNING = null` (the first-result warning `ZERO_PROMISING_AFTER_FIRST_EXECUTED_INTERNAL_CARDS` was invalid at executed count 0 and is removed until at least one INTERNAL card completes)
- `FULL_DISCOVERY_CARDS_COMPLETED = 0`
- `PARTIAL_COMPONENT_OUTCOME_OBSERVED = true`
- `PARTIAL_COMPONENT_OUTCOMES = ["D2/RULE_2/DISLOCATION_ABSTENTION"]`
- `PARTIAL_COMPONENT_OUTCOMES_OBSERVED = 1`
- `D2_RULE_2_DISCOVERY_OUTCOME_OBSERVED = true`
- `D2_RULE_2_GATE_PASS = false`
- D2 as a CARD remains `BLOCKED_MISSING_LOCAL_DATA` because RULE_1 was not executable; RULE_2 is not counted as an executed card
- formal `INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED` not triggered
- `D1 = BLOCKED_PENDING_PRE_OUTCOME_FIX`
- `D6 = DEFERRED`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- `MARKET_07_CREATED = false`
- `POST_OUTCOME_DESIGN_CHANGES = false`

Result records: `docs/research/discovery_results/`.

`NEXT_UNIT = DISCOVERY_SPRINT_01_RETRY_D2_D3_D4ROLLING_D5_WHEN_CORE_LOCAL_MATERIAL_PRESENT`.

## Retry after CORE restore (2026-09-21)

Legal 2020-2024 CORE BTC (`717d37a4…`) and CORE ETH (`4b9c113f…`) monthly parquet was restored from frozen authorities (no 2025/2026 objects requested). First blocked attempt is preserved at `docs/research/discovery_results/FIRST_ATTEMPT_BLOCKED_MISSING_LOCAL_DATA/` (`FIRST_ATTEMPT_RESULT_COMMIT = 37921089ce289cd9bcbcebb123724a3e033dcdc3`).

Retry used the same scientific implementation `26d8f7066533bcae7138d5a1952783f2a16f3c39`.

Preflight: `BTC_DATA_PRESENT = true`, `ETH_DATA_PRESENT = true`, `M06_CROSS_VENUE_DATA_PRESENT = true`.

D2 RULE_2 replay matched the first-attempt partial component exactly (`D2_RULE_2_REPLAY_EXACT_MATCH = true`): eligible 1062, `ABSTAIN_COUNT = 78`, `DELTA = -0.0012558171628350885`, `MU_RULE = 0.018083076558621618`, `MU_CONTROL_MEAN = 0.019338893721456706`, `GATE_PASS = false`.

| Card | Classification |
|---|---|
| D2 | `PROMISING_PROTOTYPE` (RULE_1 `GATE_PASS=true`; RULE_2 remains `GATE_PASS=false`) |
| D3 | `NO_USEFUL_STRUCTURE` (exactly 3 close-path functionals; none passed) |
| D4 `ROLLING_CORRELATION_90D` | `NO_USEFUL_STRUCTURE` (`LEAD_LAG_1DAY` not executed) |
| D5 | `NO_USEFUL_STRUCTURE` (OR composition; did not beat best same-window component) |

This is adaptive discovery on historically exposed 2020-2024 data, not confirmatory evidence. No threshold/sign/window rescue after outcomes.

D2 statistical-gate wording (documentation sync to implementation
`26d8f7066533bcae7138d5a1952783f2a16f3c39`; not a post-outcome gate
change): `MU_RULE > P95` of the 1000 `RATE_MATCHED_RANDOM_ABSTENTION`
replicate mean-severity values. `DELTA = MU_RULE -
mean(random-control replicate means)`.

ETH parquet compatibility: the frozen MARKET-05 ETH schema has no `open`
column. `ETH open := close` exists only so D4 `ROLLING_CORRELATION_90D`
can compute close-to-close returns against that schema. It is **not**
authorized for any future experiment that scientifically uses ETH open
prices.

Program diagnostic:

- `INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`
- `INTERNAL_PROMISING_PROTOTYPES = 1`
- `INTERNAL_DISCOVERY_WARNING = null`
- formal `INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED` not triggered (stall gate still requires >= 6 materially orthogonal internal cards)
- `D1 = BLOCKED_PENDING_PRE_OUTCOME_FIX` (historical status of this retry unit; superseded below)
- `D6 = DEFERRED`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- `MARKET_07_CREATED = false`
- `POST_OUTCOME_DESIGN_CHANGES = false`

Historical `NEXT_UNIT` of this retry unit:
`DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE_EXECUTION`.

## D1 null-adequacy gate adjudication (2026-09-21)

Adjudication only. The gate was **not** executed. D1 scientific targets
were **not** computed. D2–D5 bytes are unchanged.

Check A: the frozen D1 null generates a synthetic **daily** 24h-return
path (GARCH(1,1)+Student-t filtered circular block-bootstrap). The
tested state observable is `ev.rv_btc_24h` from **288 × 5m** intra-day
log returns, with `RV_20` L2-aggregating 20 of those daily RV values.
No already-frozen mapping
`daily return path -> synthetic ev.rv_btc_24h -> synthetic RV_20`
exists. F3 had already rejected an arbitrary intraday bridge. Forbidden
substitutes (`abs(daily_return)`, GARCH sigma, squared daily return,
synthetic conditional variance) are not used.

```
D1_NULL_MODEL_OBSERVABLE_MISMATCH = true
D1_NULL_ADEQUACY_GATE_EXECUTED = false
D1_TARGET_OUTCOME_COMPUTED = false
D1_STATUS = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
```

Check B (independent): leverage/asymmetry proxy, RV_20 short-lag ACF lag
set, lagwise pass/fail, skewness/kurtosis joint vs individual, NaN
treatment, and GARCH estimation details remain underspecified.
`D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED = true`. No researcher-defined
substitute is executed.

Why defer rather than repair: D2–D5 outcomes are already known. A new
null or new gate definitions would be a post-sibling-outcome redesign
and must be a future D1-v2 card, not an in-sprint repair.

Deferred D1 is not counted as executed.
`INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`.
`INTERNAL_PROMISING_PROTOTYPES = 1`.
D2 remains `PROMISING_PROTOTYPE`. `MARKET_07_CREATED = false`.
Protected 2025/2026 unopened.

Full record: `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.{json,md}`.

Historical `NEXT_UNIT` of this D1 unit:
`D2_CONFIRMATION_FEASIBILITY_AND_DESIGN`.

## D2 confirmation feasibility and design (2026-09-21)

Outcome-blind confirmation design for the sole survivor
`D2 / RULE_1 / RV_ABSTENTION`. Confirmation was **not** executed.
2025/2026 price values were **not** inspected. MARKET-07 / ARM were
**not** created.

Calendar 2025 is the proposed first independent confirmation surface
(`FIRST_T = 2025-01-01T00:05:00Z`, `LAST_T = 2025-12-30T00:05:00Z`).
2026 remains a second reserved surface and is not consumed. Metadata-only
binding of all 12 2025 monthly source/canonical hashes succeeded; no
2026 object is required for the frozen interval.

Power at the predeclared 20% true effect, estimated from exposed
2020-2024 only. Primary prospective criterion is statistical power
(P95 gate), not joint pass probability:

```
ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011
ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT = 0.006
```

Joint `0.006` and practical-gate power `~0.499` are diagnostic. The
~0.5 practical-gate figure at the exact 20% boundary is expected and
is not itself evidence of underpower. Because statistical power is
still `<< 0.80`, `CONFIRMATION_FEASIBILITY` remains
`UNDERPOWERED_SINGLE_YEAR_2025`.

Fresh-surface size planning (IID pooled-K) on 2020-2024 is **superseded**:
`SUPERSEDED_IID_TWO_YEAR_POWER = 0.903`.

Authoritative method: `YEAR_MATCHED_WHOLE_YEAR_PLUS_CONTIGUOUS_PARTIAL_BLOCK`.
Association-broken circular mask shift, year-matched controls, exact 20%
injection vs expected year-matched control mean.

```
POWER_N550 = 0.446
POWER_N575 = 0.473
POWER_N600 = 0.525
POWER_N625 = 0.545
POWER_N650 = 0.56
POWER_N675 = 0.59
POWER_N700 = 0.636
POWER_N728 = 0.64
THREE_YEAR_STATISTICAL_POWER_AT_20PCT = 1.0
MIN_REQUIRED_FRESH_DECISION_ROWS = 1092
POTENTIAL_FUTURE_SURFACE = MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE
AUTHORIZED_TO_OPEN = false
```

Do not lower the 20% bar. Do not consume 2025+2026: two years remain
below 0.80 under the authoritative method. Full calendar 2026 is not
currently available. D2 remains `PROMISING_PROTOTYPE` (adaptive discovery only).

Full record: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

`NEXT_UNIT` of that size-planning unit was
`D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT`.
That wait-until-future-Binance default is **superseded in routing only** by
the alternative-surface feasibility unit below.

## D2 alternative independent surface feasibility (2026-09-21)

Outcome-blind. Confirmation was **not** executed. BitMEX D2 outcomes were
**not** computed. Protected Binance 2025/2026 remained sealed.

Refined year-matched power on exposed Binance 2020-2024 only, seed
`20260921124`, one 5-row local refinement between `N_BELOW=800` and
`N_ABOVE=825`:

```
REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815
POWER_AT_REFINED_MIN_N = 0.801
POWER_95CI_AT_REFINED_MIN_N = [0.775, 0.825]
```

1092 is only the smallest previously tested size meeting power, not an
assumed true minimum. `N=820` point-estimate `0.794` is a Monte Carlo dip
after `N=815`; the frozen criterion is the smallest tested N with
point-estimate power `>= 0.80`.

Primary pre-2020 candidate: official BitMEX XBTUSD 5m buckets.

```
BITMEX_RAW_DATA_START = 2016-05-13T11:55:00Z
BITMEX_FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00Z
BITMEX_LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00Z
BITMEX_PRE2020_ELIGIBLE_N = 1069
BITMEX_CONTRACT_COMPATIBILITY = SCIENTIFICALLY_COMPARABLE_CROSS_VENUE
BITMEX_TEMPORAL_INDEPENDENCE_CLASS = PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION
CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
```

A later BitMEX result, if executed, is
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION`, not
`EXACT_BINANCE_CONFIRMATION`. Next unit is prereg freeze, not MARKET-07.

Full record: `docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.{json,md}`.

`NEXT_UNIT` of that feasibility unit: `D2_BITMEX_REPLICATION_PREREG_FREEZE`.

## D2 BitMEX replication preregistration freeze (2026-09-21)

Outcome-blind freeze. Not executed. Classification unassigned.

```
PREREG_FROZEN = true
EVIDENCE_CLASS = INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION
EXPECTED_ELIGIBLE_N = 1069
FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00Z
LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00Z
REPLICATION_RANDOM_SEED = 20260921125
N_RANDOM_CONTROLS = 10000
STATISTICAL_GATE = MU_RULE > CONTROL_P95
PRACTICAL_GATE = DELTA >= 0.20 * UNCONDITIONAL_MEAN
D2_BITMEX_OUTCOME_COMPUTED = false
```

Full record: `docs/research/D2_BITMEX_REPLICATION_PREREG.{json,md}`.

`NEXT_UNIT` of that prereg unit: `D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.

## D2 BitMEX replication implementation review (2026-09-21)

Outcome-blind. Stub lineage preserved. Not executed.

```
IMPLEMENTATION_REVIEW = PASS
EXECUTION_READY = true
EXECUTION_AUTHORIZED = false
EXPECTED_ELIGIBLE_N = 1069
D2_BITMEX_OUTCOME_COMPUTED = false
```

Full record: `docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.{json,md}`.

`NEXT_UNIT` of that review unit: `D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION`.

## D2 BitMEX replication one-shot execution (2026-09-21)

Permit then one-shot. Timestamp census still `N=1069`. Constructed
eligible sample was `N=1067` (2017=341, 2018=363, 2019=363). Classification
`D2_BITMEX_REPLICATION_INVALID`. Primary metrics not computed. Not
`NOT_SUPPORTED`. No rerun. 2025/2026 unopened. MARKET-07 not created.

```
CLASSIFICATION = D2_BITMEX_REPLICATION_INVALID
CONSTRUCTED_ELIGIBLE_N = 1067
FROZEN_ELIGIBLE_N = 1069
D2_BITMEX_OUTCOME_COMPUTED = false
RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Full record: `docs/research/D2_BITMEX_REPLICATION_RESULT.{json,md}`.

`NEXT_UNIT` of that one-shot unit: `D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION`.

## D2 BitMEX replication integrity adjudication (2026-09-21)

Exactly two timestamp-complete decisions fail frozen
`construct_discovery_row` for predeclared `BTC_RET_24H_EQ_0`:
`2018-03-17T00:05:00Z` and `2019-02-10T00:05:00Z`. Class
`REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`. Original INVALID
result preserved. No D2 effect computed. Corrected eligible N=1067.
Original rerun unauthorized. Corrected execution scientifically
permissible; no permit created.

```
ADJUDICATION_CLASS = REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH
TRAILING_HISTORY_AUTHORITY = VALID_CONSTRUCTED_ROWS
CORRECTED_ELIGIBLE_N = 1067
ORIGINAL_PRIMARY_OUTCOME_COMPUTED = false
ORIGINAL_RANDOM_CONTROLS_COMPUTED = false
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = true
ORIGINAL_RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Full record: `docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.{json,md}`.

`NEXT_UNIT` of that adjudication unit: `D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT`.

## D2 BitMEX corrected one-shot execution (2026-09-21)

Integrity-repair permit then one-shot from
`CORRECTED_PERMIT_COMMIT = 14e9c9dfbfd6bdb989ef592b891aab1eb963f6f3`.
Corrected identity `1317/250/1067`, years `341/363/363`, two
`BTC_RET_24H_EQ_0` exclusions retained. Original INVALID run preserved.
Classification `D2_BITMEX_REPLICATION_SUPPORTED`. Not exact Binance
confirmation, not proven alpha, not a validated trading edge. No rerun.
2025/2026 unopened. MARKET-07 not created.

```
CLASSIFICATION = D2_BITMEX_REPLICATION_SUPPORTED
CONSTRUCTED_N = 1317
WARMUP_N = 250
ELIGIBLE_N = 1067
PRIMARY_PASS = true
RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Full record: `docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.{json,md}`.

`NEXT_UNIT` of that corrected-execution unit: `PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED`.

## Program decision after D2 BitMEX SUPPORTED (2026-09-21)

D2 promoted to `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Discovery
and independent pre-2020 BitMEX replication claims supported.
Market-mechanism / trading-edge / product claims not supported or not
tested. Binance 2025/2026 remain sealed. No MARKET-07. No D2 variants.
Product build remains frozen. Hypothesis generation rotates across
families A–I.

```
D2_PROGRAM_CLASS = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE
BINANCE_2025_2026_DECISION = KEEP_SEALED
PRODUCT_BUILD_FROZEN = true
MARKET_07_CREATED = false
```

Full record: `docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.{json,md}`.

`NEXT_UNIT` of that program-decision unit: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`.

## D2 excess path-risk beyond vol-clustering design (2026-09-22)

Outcome-blind post-replication mechanism-decomposition design freeze.
Selector unchanged. Primary target `ADVERSE_SHARE`. Seed `20260922131`.
Evidence class `POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY`.
BitMEX 2017-2019 not reused. 2025/2026 unopened. MARKET-07 not created.
No real decomposition outcome. `DESIGN_STATUS = FROZEN`.

```
DESIGN_STATUS = FROZEN
PRIMARY_SELECTOR = D2_RULE_1_RV_ABSTENTION
PRIMARY_TARGET = ADVERSE_SHARE
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Full record: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.{json,md}`.

`NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`.
