# Discovery Sprint 01

**Unit:** `DISCOVERY_SPRINT_01`
**Parent unit:** `HYPOTHESIS_DISCOVERY_PIPELINE_V2`
**Parent selection commit:** `a711086c36eb7129fc3f0660732049de93dd1629`
**Date:** 2026-09-21
**Status:** `SIX_CARDS_DEFINED_NONE_EXECUTED`
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01.json`

Six discovery cards are defined below. **None is executed in this unit.**
Each follows the Discovery Card contract from
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

| Counter | Value |
|---|---|
| `INTERNAL_DISCOVERY_CARDS_PLANNED` | 5 (D1-D5) |
| `INTERNAL_PROMISING_PROTOTYPES` | 0 |
| `EXTERNAL_BENCHMARK_CARDS_PLANNED` | 1 (D6) |
| `EXTERNAL_PROMISING_OR_REPRODUCED` | 0 |

All counters reflect card **definition/planning** only — no card has been
executed in this unit.

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

`SCIENTIFIC_OUTCOMES_COMPUTED = false`. `MARKET_07_CREATED = false`.
`PROTECTED_2025_OPENED = false`. `PROTECTED_2026_OPENED = false`.
`NEXT_UNIT = DISCOVERY_SPRINT_01_CARD_EXECUTION` (unchanged).

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
