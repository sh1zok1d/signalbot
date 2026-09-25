# GV0R02 outcome-blind feasibility compiler — design

`COMPILER_SCHEMA_VERSION = GV0R02_SCHEMA_V0`
`COMPILER_POLICY_VERSION = GV0R02_POLICY_V0`
`FEASIBILITY_COMPILER_IMPLEMENTED = false`
`NEXT_UNIT = GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_IMPLEMENTATION`

This is the contract for a cheap screen that runs before a full research object is preregistered. It does not decide that a hypothesis is true. Machine-readable fields live in `GV0R02_FEASIBILITY_COMPILER_SCHEMA.json`. Acceptance inputs live in `GV0R02_FEASIBILITY_COMPILER_GOLDEN_CASES.json`.

## What already exists

Reusable:

- `GENERATOR_CONTRACT_V02` in `scripts/research/generator_v0/contract.py`. Cards already forbid success scores, bound the search surface, and stop legal ranges at 2024-12.
- Stream-B triage in `docs/research/GV0R01_STREAM_B_FEASIBILITY_TRIAGE.json`. That is a post-card judgment. Its blocked statuses inform Pass A. It is not the compiler.
- Closed outcome-blind designs for C012, C004, and C020. Those are the full-design layer and the golden cases.
- Dataset digests and point-in-time calendars. The compiler should consume those identities, not invent new provenance.
- `docs/HISTORICAL_DATA_STRATEGY.md` for CORE versus RICH history.
- The D2 BitMEX surface as an independent replication candidate, not as extra Binance discovery length.
- Protected 2025/2026 from the project mandate and the generator's protected end month.

Missing:

- A derived feature registry.
- Deterministic passes for sample size, dependence, inference class, approximate power, era role, and holdout compatibility.
- A blocker ledger and the data-expansion stop rule.
- Versioned compiler policy so later code cannot silently rescore old proposals.
- The implementation and the positive-control run. Both are later units.

## Layer boundary

The generator writes mechanism, claim, direction, event definition, observable, moment, counterfactual class, a minimum meaningful effect with units and rationale, an era-invariance prior, qualitative dependence, feature needs, point-in-time needs, and one named inference class.

The compiler computes coverage, nominal counts, structural dependence, whether that named class can attain alpha, and an approximate MDE under a frozen noise profile. It compares the predeclared effect with that MDE.

A full design unit still freezes the sample, the dependence graph, one procedure, missingness, and preregistration-grade power. Execution stays unauthorized until that contract says otherwise.

The compiler must not estimate those deterministic quantities with an LLM. It must not collapse information into raw event count. A rare directional first-moment idea gets a generator warning below 300 nominal observations. That warning is not a ban. Pass E remains the authority.

## Feature registry

The registry is generated from implemented features, dataset ids, coverage scans, point-in-time metadata, and known breaks. Minimum fields are `feature_id`, `definition_ref`, `definition_digest`, `input_dataset_ids`, `unit`, `normalization_rule`, `lookback_requirement`, `available_at_rule`, `coverage_by_venue`, `coverage_by_instrument`, `completeness`, `known_breaks`, `cross_venue_notes`, and `quality_status`.

There is no feature-level portability grade. Whether a feature travels is a property of the feature, the mechanism, and the era.

## Passes

A. Source and feature availability. Results are data-ready, data-blocked, or point-in-time-blocked.

B. Sample compilation from calendars and eligibility rules only. Counts by year, era, venue, and event family. No conditional market outcomes.

C. Structural dependence: overlapping windows, reused controls, shared baselines, rolling overlap, nesting, and clustering. No overlap is not independence.

D. Inference feasibility for the named class only. An exact randomization claim is unjustified when the observed assignment is outside the reference support. A placebo set reports `REFERENCE_SUPPORT_SIZE` and `REFERENCE_SUPPORT_RESOLUTION`. It does not report that reciprocal as `MIN_ATTAINABLE_P`. An unspecified class waits for the design unit. The compiler does not shop a more powerful class.

E. Approximate power at the proposal's minimum meaningful effect, under `GV0R02_POWER_PROFILE_V0`. Base and one predeclared stress. Analytic when the design allows it. Otherwise a small capped simulation. Not the later preregistration budget, and not fit on the candidate's outcome windows.

F. Era roles. Binance 2020–2024 is discovery. BitMEX 2016–2019 is a historical replication candidate. 2025–2026 is protected holdout. Eras are not pooled unless the proposal's era-invariance prior is `EXPECTED`. In that case the compiler reports both a homogeneous-effect screen and a zero-effect-in-one-era stress. It does not keep only the kinder one.

G. Holdout compatibility is recorded. A small protected surface is a limitation, not an automatic rejection.

## Statuses

Exactly these, first match wins:

`DEFINITION_INCOMPLETE`, `DATA_BLOCKED`, `PIT_BLOCKED`, `INFERENCE_SUPPORT_INSUFFICIENT`, `STRUCTURAL_INFERENCE_RISK`, `INFORMATIONALLY_WEAK`, `FEASIBLE_FOR_PREREGISTRATION`.

A harder failure is not upgraded by a later pass.

## Plausible effect, revision, blockers

The minimum meaningful effect is the scientific bar and is fixed before MDE is computed. The MDE is statistical. A separate critic, not the proposing generator, may add a labeled plausibility assessment with rationale, sources, and confidence.

One outcome-blind revision is allowed. It may change horizon, event definition, feature choice, or counterfactual class. It may not change the effect bar, the era, pooling, the named inference class, or a normalization chosen to improve the MDE. The original proposal and the first result stay. The revision has its own linked id and a recorded reason.

Every non-feasible result writes a blocker: missing feature, missing source, insufficient history, point-in-time not established, alpha unattainable, MDE too large, dependence too strong, counterfactual unresolved, or definition incomplete.

After a batch of about 30 proposals, three or more `FEASIBLE_FOR_PREREGISTRATION` results mean data is not the bottleneck and acquisition stops. Zero feasible results, with at least three otherwise strong proposals blocked by the same source or feature, make that object eligible for a separate acquisition review. Point-in-time status, cost, maintenance, and information gain are still required. This unit acquires nothing.

## Golden cases and the positive control

C012 must come out `INFORMATIONALLY_WEAK`: the amended inference is valid and the stress MDE is about 0.609 single-window SD against a frozen 0.50 bar. It must not be called inference-support insufficient.

C004 must come out `INFERENCE_SUPPORT_INSUFFICIENT`: orbit 16, minimum p 0.0625, alpha 0.05.

C020 must come out `INFORMATIONALLY_WEAK` with classification `PLACEBO_REFERENCE_DISTRIBUTION`. The reference resolution `1.647e-59` is not an exact p floor. The Monte Carlo floor is `1/1001`. Stress power at `log(0.90)` is 0.40 against a target of 0.80.

These tests read the frozen planning records. They do not recompute market outcomes.

The positive control is not chosen or run here. The later choice must be independent of these three objects, frequent, definable with existing features, and selected as a mechanism class rather than by inspecting outcomes. Its job is to show that the compiler can return `FEASIBLE_FOR_PREREGISTRATION`.

## Degrees of freedom and cost

The power profile, the status priority, the era defaults, and the single-revision rule are versioned. A policy change writes a new result. It does not rewrite an old one.

Passes A–D and G are structural and should finish in seconds. Pass E is the only approximate simulation, and it stays small. Preregistration-grade power stays in the design unit.

## What this unit did not do

C012, C004, and C020 stay closed. No market outcome was opened. No dataset was acquired. The generator was not modified. No new hypothesis was generated. The compiler was not implemented. The positive control was not executed. Protected 2025 and 2026 values were not opened.
