# Discovery-first research — owner decision V1

**Status:** `OWNER_DECISION_RECORDED (2026-10-07) / APPLIES TO NEW DISCOVERY UNITS / NOT RETROACTIVE`

**Subordinate to:** protected-data rules, sealed experiment rules, `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`, the Research Atlas, and all experiment-specific frozen authorities.

**Does not reopen:** closed research lines, consumed one-shots, compiler V3, E1, V3 Microscope, divergence/exhaustion, or any sealed verdict.

## 0. Decision

Signalbot research should not start by choosing a trader story and then searching for evidence that supports it.

For product-serving market research, the preferred order is:

1. define a bounded, point-in-time observable state space before outcomes;
2. measure what structure the market actually shows across that space;
3. report effect sizes, uncertainty, stability, controls and search exposure for the whole declared search;
4. only then formulate a narrower market mechanism or hypothesis from the observed structure;
5. freeze that successor hypothesis before a separate confirmation attempt;
6. only confirmed/calibrated evidence may graduate into stronger product claims under the existing L0-L4 ladder.

Short form:

> **Research should discover structure before explaining it.**

And:

> **Do not search for a “working hypothesis”; search for reproducible information.**

This is a routing rule for discovery. It is not permission for unconstrained data mining.

## 1. Two unit modes

New product-serving research may declare one of two modes in its design note.

### A. `DISCOVERY`

Purpose: map a bounded family of observable market states and identify where stable information may exist.

Before outcomes, freeze at minimum:

- the market question / object;
- the data surface and exposure status;
- the outcome family or state transition family;
- the complete feature family to be inspected;
- allowed transformations / normalizations;
- horizons and event semantics;
- nuisance variables / baselines;
- stability slices;
- falsification / negative controls;
- the full search grid or a deterministic way to enumerate it;
- the selection / ranking rule, if candidates will be named;
- multiplicity / search-exposure handling;
- what evidence would justify a separate successor unit.

A discovery unit does **not** need to pre-assert the sign of an effect or name one favoured feature as the answer.

It must not add features, thresholds, horizons, outcomes or subgroup definitions after reading results merely to rescue or strengthen a pattern.

The result reports the whole declared search surface, including null, unstable and contradictory cells.

### B. `CONFIRMATION`

Purpose: test a specific relation that was selected before this unit began.

Before outcomes, freeze:

- the exact predictor / state;
- exact outcome;
- exact horizon;
- exact comparison / baseline;
- exact estimator;
- nuisance controls;
- falsification;
- stopping / sample rule where applicable;
- the surface to be used and why it is sufficiently independent of the discovery that generated the hypothesis.

No rescue inside the unit.

A relationship chosen because of a discovery result does not become confirmed by re-reading the same search surface with a nicer threshold or explanation.

## 2. Bounded discovery, not “let the model find anything”

“Let the market speak” means that the sign, magnitude, interaction and useful representation are not imposed in advance.

It does **not** mean:

- unlimited features;
- arbitrary technical indicators;
- arbitrary windows;
- arbitrary thresholds;
- arbitrary outcomes;
- automatic feature generation;
- black-box model selection without an exposure ledger;
- choosing only visually attractive cells;
- treating the best historical cell as a probability for now.

Discovery must be bounded enough that the project can state exactly what was searched.

Prefer heterogeneous information sources over many transformations of the same source.

For example, a future market-state discovery family may contain distinct observables from:

- price structure;
- path / approach geometry;
- volume;
- volatility;
- positioning;
- aggressive flow;
- liquidity;
- derivatives;
- event/time context;

but every included observable must be justified, PIT-safe and declared before outcomes.

## 3. Evidence first, explanation second

Discovery results are interpreted in this order:

1. **Observed structure** — what relationship was measured.
2. **Robustness** — uncertainty, stability, concentration, falsification, dependence and search exposure.
3. **Incremental information** — whether the relationship remains after relevant nuisance / already-known features.
4. **Mechanism candidate** — only after 1-3, propose why the structure may exist.
5. **Successor hypothesis** — freeze a narrower relation for separate confirmation.

Do not reverse this order by inventing the mechanism first and treating the data as a confirmation exercise.

A plausible story is not evidence.

## 4. Relation to the L0-L4 claim ladder

`EVIDENCE_AND_CLAIMS_DECISION_V1` remains the authority for what may be said.

This decision changes how candidate relations are generated, not the standards for user-facing claims.

Discovery may report internally:

- estimates;
- historical frequencies;
- gradients;
- interactions;
- nulls;
- uncertainty;
- stability;
- controls;
- full search exposure.

However, a relationship selected **because it looked best in the discovery outcomes** is marked `DISCOVERY_ONLY` for that selection.

It must not be presented as:

- a current probability (L3);
- actionable edge (L4);
- a product “strong/weak” truth score;
- a confirmed market mechanism.

For a selected discovery relation to become a product-facing directional claim, prefer a separate frozen successor confirmation or prospective calibration appropriate to the intended claim level.

A predeclared family-level statement that reports the entire family without winner-selection remains governed directly by the existing L1/L2 rules.

## 5. Search exposure and candidate selection

Every discovery unit records:

- number of raw candidate features;
- number of transformations;
- number of horizons;
- number of outcome classes;
- number of interaction / subgroup cells;
- total material cells examined;
- how dependencies and multiplicity are handled;
- the deterministic rule used to call something a successor candidate.

Candidate selection should prefer:

- stable gradients or monotonic relationships over isolated bins;
- repeated sign across eras over one large year;
- incremental information over redundant transforms;
- survival under falsification;
- broad parameter plateaus over narrow optima;
- simple interpretable state variables over a complex score, unless complexity is separately justified.

A large historical effect with poor stability is not automatically a better candidate than a smaller, stable and incremental one.

## 6. Nulls are first-class outputs

Discovery is successful when it reduces uncertainty about the market, including by showing that a plausible feature does not add information.

Examples:

- touch history adds information;
- rejection speed does not;
- a flow feature is redundant after price state;
- an interaction exists only in one era;
- no stable relation exists in the declared search space.

Do not rescue a null by changing the question after outcomes.

A null narrows the future Market State Engine and is therefore useful product research.

## 7. Path toward a future forecast system

The intended long-run architecture is:

```text
raw observations
    ↓
PIT-safe features
    ↓
market objects / states
    ↓
reproducible state relationships
    ↓
confirmed transition structure
    ↓
prospective calibration
    ↓
claim-specific probabilities
```

The forecast layer must emerge from reproducible state-transition evidence.

It must not be created by assigning intuitive weights to trader markers or by asking an LLM to infer probabilities from raw market data.

## 8. Immediate consequence for the level program

The level work illustrates the rule:

- `LEVEL_TOUCH_DEGRADATION_V1` found information in touch history;
- `LEVEL_REJECTION_MEMORY_V1` found no independent information in simple rejection speed.

Future level research should therefore avoid inventing a fixed story such as “fast approach breaks” or “strong rejection protects”.

A discovery-style `LEVEL_APPROACH_STATE` unit should instead predeclare a bounded family of PIT-safe approach-state measurements and ask which, if any, contain stable incremental information about post-touch state.

Any selected relation then becomes a separate frozen successor hypothesis.

This paragraph records routing only. It does not authorize a new execution.

## 9. What this decision does not change

- No existing result or verdict changes.
- No current product code changes.
- No product wording changes.
- No scoring system is authorized.
- No research unit is started.
- No new data surface is opened.
- No protected / sealed surface is consumed.
- No compiler or universal validator is reinstated.
- Existing `EVIDENCE_AND_CLAIMS_DECISION_V1` result fields remain required.
- Experiment-specific frozen contracts remain authoritative for their own units.

## 10. Implementation rule

A new discovery unit's design note must declare:

`MODE = DISCOVERY`

A confirmation unit must declare:

`MODE = CONFIRMATION`

If a unit cannot clearly state its bounded search space before outcomes, it is not ready to run.

If a discovery result suggests a new feature, interaction, threshold or outcome that was not in the frozen search space, record it as a successor candidate and stop. Do not evaluate it inside the same unit.
