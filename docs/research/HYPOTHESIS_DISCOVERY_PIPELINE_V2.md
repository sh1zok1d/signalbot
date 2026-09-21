# Hypothesis Discovery Pipeline V2

**Unit:** `HYPOTHESIS_DISCOVERY_PIPELINE_V2`
**Unit type:** `RESEARCH_PROCESS_REDESIGN_NOT_A_MARKET_HYPOTHESIS`
**Date:** 2026-09-21
**Parent selection commit:** `a711086c36eb7129fc3f0660732049de93dd1629`
**Machine-readable record:** `docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.json`

This unit is a **research-process redesign**, not a market hypothesis. It is
not MARKET-07, does not preregister R-A or any other region, does not open
protected 2025/2026, does not execute a confirmatory experiment, and does not
build new generic infrastructure.

## Program pivot

- `ORTHOGONAL_REGION_SELECTION_PRESERVED = true`
- `R_A_SELECTION_RETRACTED = false`
- `R_A_SOLE_NEXT_PATH_SUPERSEDED = true`

Signalbot has strong falsification/validation machinery (frozen
preregistration, ARM/claim/one-shot execution, sealed RESULT, red-team
hardening), but `INTERNAL_PROMISING_PROTOTYPES = 0`. Every internally
generated MARKET hypothesis executed so far (MARKET-01, 02, 05, 06) returned
`NO_EVIDENCE` at the confirmatory stage. MARKET-03 is an **external**
public-strategy reproduction and must not be counted as internal discovery.
The evidence does not support routing R-A directly into another single
confirmatory attempt; it supports first testing whether the internal
discovery/generation process itself can produce a promising prototype at
all, across several orthogonal mechanism regions at once, before committing
further confirmatory-lifecycle cost to any one of them.

R-A is reclassified as `DISCOVERY_SPRINT_01 / D1 = STRUCTURAL_STATE_DETECTION`.
It is **not** MARKET-07 and **not yet** a confirmatory hypothesis.

## Supersession of a711086's routing

Commit `a711086c36eb7129fc3f0660732049de93dd1629` remains the valid,
unmodified historical record of the orthogonal-region selection
(`REGION_SELECTED = R-A`, `SELECTION_STATUS =
REGION_SELECTED_NOT_HYPOTHESIS_CREATED`). This unit does not merge, rebase,
or edit that commit. It supersedes only the **routing** that followed from
it (`NEXT_UNIT =
STRUCTURAL_REGIME_STATE_DETECTION_MECHANISM_CLASS_AND_NULL_MODEL_FEASIBILITY`),
by recording this later, separate program-level decision in a new commit.

### R-B / R-F "fresh surface" correction

a711086 stated that R-B and R-F "need a fresh evaluation surface that does
not exist." That statement is correct but was written without distinguishing
discovery from confirmatory use, and is hereby **scoped to confirmatory use
only**. Neither R-B nor R-F has an unexposed surface available for a
confirmatory claim of independent evidence. It does not follow that R-B or
R-F cannot be explored at all: cheap, outcome-inspecting, non-evidentiary
adaptive discovery on historically exposed 2020-2024 data is explicitly
permitted for both, under the constraints below.

`DISCOVERY_FEASIBILITY != CONFIRMATORY_FEASIBILITY`. Discovery feasibility
asks only whether a mechanism class can be cheaply screened for a
non-trivial pattern using data already exposed to prior program adaptation,
with outcome inspection allowed and no evidentiary claim implied.
Confirmatory feasibility asks whether a materially fresh, non-adapted,
outcome-blind surface exists to test that pattern as independent evidence.

- R-B may be explored on historically exposed data (see Discovery Sprint 01
  card D2); any resulting pattern remains exploratory and requires an
  independent future confirmation surface before it can support a
  MARKET-0N claim.
- R-F may be explored only under a tightly bounded, pre-frozen search
  surface (see card D5), with its HIGH rescue/multiple-testing risk
  explicitly recorded, not laundered away by relabelling it "discovery."

## Three stages

### 1. `ADAPTIVE_DISCOVERY`

Cheap, outcome-inspecting exploration of a candidate mechanism class on
historically exposed 2020-2024 research data. Outcomes MAY be inspected
during construction and iteration -- unlike confirmatory work.

Data must be labelled `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`.
Discovery results are explicitly **not**: independent evidence, clean
out-of-sample evaluation, confirmation, or validation.

Allowed terminal states (exactly these, no other evidentiary language):

- `PROMISING_PROTOTYPE`
- `NO_USEFUL_STRUCTURE`
- `INCONCLUSIVE_DISCOVERY`
- `INVALID_DISCOVERY`

A Discovery Card must exist before any code is written for a mechanism
class. No ARM, claim, reservation, or one-shot execution authority applies
at this stage.

### 2. `PROMISING_PROTOTYPE`

A discovery result that survives the Promising Prototype Gate. It is a
discovery-stage filter outcome, not confirmatory evidence, and does not by
itself authorize a MARKET-0N preregistration. It authorizes only
**eligibility to be proposed** as a future confirmatory hypothesis --
proposal is a separate, later program-level decision requiring its own
information-gain and feasibility review, exactly like
`MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`.

It does **not** authorize creating MARKET-07 (or any MARKET-0N id) directly
from this unit, opening protected 2025/2026, or skipping preregistration,
ARM/claim/one-shot execution, or sealed RESULT for the eventual confirmatory
test.

### 3. `CONFIRMATORY_RESEARCH`

The existing, unchanged heavy MARKET-0X lifecycle: frozen preregistration,
outcome-blind analysis contract, point-in-time data feasibility check,
ARM/reservation/claim authority chain, one-shot canonical execution, sealed
RESULT. Requires a materially fresh or explicitly-accounted-for surface per
confirmatory feasibility. A `PROMISING_PROTOTYPE` is at most a candidate
input to a future confirmatory preregistration decision; it carries no
evidentiary weight of its own and must not be cited as support inside a
confirmatory RESULT.

## Discovery Card contract

Each card must specify exactly these fields: `DISCOVERY_ID`,
`MECHANISM_CLASS`, `INFORMATION_SOURCE`, `FUNCTION`, `TARGET_FAMILY`,
`TIME_SCALE`, `UNIT_OF_OBSERVATION`, `MARKET_RELATIONSHIP`,
`SIMPLE_BASELINE`, `SMALL_SEARCH_SURFACE`, `KNOWN_PRIOR_EXPOSURE`,
`WHAT_A_NULL_DEPRIORITIZES`, `WHAT_A_POSITIVE_WOULD_JUSTIFY_NEXT`,
`RESEARCHER_DOF`, `MAX_ENGINEERING_SCOPE`.

Discovery must remain cheap.

**Requires:** deterministic data identity, no lookahead, a reproducible
script, an explicit statement of the attempted search surface, simple
controls/baselines, reporting of all attempted variants.

**Does not require:** ARM, one-shot authority, implementation freeze chain,
or confirmatory lifecycle machinery -- none of the heavy MARKET-06-style
lifecycle infrastructure applies to discovery cards.

## Promising Prototype Gate

A discovery result may become `PROMISING_PROTOTYPE` only if the pattern is
NOT merely: one magic cell, one isolated year, negligible practical
magnitude, worse than a trivial baseline, leakage/mechanical artifact, or
the product of a large hidden search surface.

Lightweight considerations: practical magnitude; neighborhood/parameter
stability where relevant; temporal/regime consistency; simple
baseline/control comparison; adequate support; absence of obvious artifact.

This is a discovery filter, not confirmatory evidence.

## Program diagnostic

Track separately: `INTERNAL_DISCOVERY_CARDS`, `INTERNAL_PROMISING_PROTOTYPES`,
`EXTERNAL_BENCHMARK_CARDS`, `EXTERNAL_PROMISING_OR_REPRODUCED`. MARKET-03
belongs only to external evidence/history. These counters are used
diagnostically, never as formal success probabilities.

After 6-10 materially orthogonal internal discovery cards, if
`INTERNAL_PROMISING_PROTOTYPES == 0`, record
`INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = true` and require a
program-level decision before continuing another batch. The correct
response is **not** to generate another cluster of nearby variants.

## Information-gain rule

Each new discovery card must either (A) produce a promising prototype worth
confirmation, or (B) materially reduce priority for a distinct
mechanism-space region. Cards whose null would teach essentially nothing
must not be created.

## Cross-sectional sidecar

`DISCOVERY_SPRINT_01` additionally records one outcome-blind feasibility
sidecar, `CROSS_SECTIONAL_PANEL_FEASIBILITY`. It is explicitly **not** one
of the six discovery cards and computes no signal/outcome statistics.

## Explicit non-actions in this unit

`MARKET_07_CREATED = false`; no hypothesis preregistered;
`PROTECTED_2025_OPENED = false`; `PROTECTED_2026_OPENED = false`; no
confirmatory experiment executed; no discovery card executed; no new
generic infrastructure built; `SCIENTIFIC_OUTCOMES_COMPUTED = false`; no
frozen artifact modified.

## Related artifacts

- Parent selection: `docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.json`
  (commit `a711086c36eb7129fc3f0660732049de93dd1629`)
- Discovery sprint: `docs/research/DISCOVERY_SPRINT_01.{json,md}`
