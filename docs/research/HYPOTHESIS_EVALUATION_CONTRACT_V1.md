# Hypothesis evaluation contract V1

**Status:** `READY_FOR_OWNER_ADOPTION`. It has no force until the owner adopts it. Adoption is recorded below.
**Date:** 2026-10-01
**Review:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.md`
**Proposal:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_PROPOSAL.md`

**Scope.** V1 governs every hypothesis card registered after adoption. It is not retroactive: every frozen preregistration, permit, result and verdict keeps its force. `EDGE_RESEARCH_PROTOCOL.md` still governs whatever V1 does not cover. The GV0R02 feasibility compiler and the generator feasibility contract are updated to V1 in a separate unit.

## 1. Twin preregistration

The discovery plan and the confirmation plan are frozen together, before any outcome of the card is computed. The preregistration fixes:
- the discovery surface and the time-disjoint confirmation surface, plus a fallback chosen by outcome-blind support only;
- the estimand and its weights;
- the inference procedure, kept separate from the estimand;
- horizons and primary cells (§6);
- the practical bar (§4);
- the target class: unconditional or conditional;
- planning power at 50% and 75% of a planning effect on both surfaces;
- the code and data identities.

## 2. Domain and variable roles

The preregistration names three kinds of variables:
- `REGIME_VARIABLES`: where the claim operates. Required for a conditional claim.
- `MECHANISM_VARIABLES`: what defines the mechanism. Never conditioned away.
- `NUISANCE_BASELINE_VARIABLES`: obvious explanations the baseline removes.

Every regime and every event is computable point-in-time at the decision boundary, and frozen in code before outcomes.

## 3. Nuisance baseline

**Standard nuisance set** (mandatory):
- time of day, for intraday claims;
- prior realized volatility at the decision time;
- the lagged target, which covers persistence of the target itself.

**Card-specific nuisance.** Obvious explanations specific to the card are added. Example: prior net taker flow for any order-flow claim.

**Exclusions.** Excluding a standard variable needs a written argument that it defines the mechanism, a red-team check, and the support diagnostic.

**Support diagnostic** (outcome-blind, before outcomes): cell counts after matching. If support is insufficient, the design coarsens the nuisance as a frozen choice, or the card is `INCONCLUSIVE`.

## 4. Gates

All gates are conjunctive and mechanical:
1. **Integrity.** Identities match and the run is one-shot.
2. **Statistical.** Dependence-aware by default: block or HAC methods, with block or lag length covering construction overlap. An exchangeable or IID null needs a written justification. Effective N is reported.
3. **Practical.** The bar is frozen with its justification:
   - trading-relevant claims: above costs;
   - context claims: product relevance.
4. **Concentration** (this replaces "positive in k of n years"):
   - at least 3 epochs (calendar years unless declared otherwise);
   - no epoch contributes more than 0.5 of the summed epoch effects;
   - every leave-one-epoch-out estimate keeps the pooled sign and at least 0.5 of its magnitude.

An outside-regime null or attenuation is optional specificity evidence, never a gate.

## 5. Outcome classes

The class is a mechanical function of the frozen gates and the declared target class:

| Class | Meaning |
|---|---|
| `SUPPORTED_UNCONDITIONAL` | All gates pass across the declared population, and time-disjoint replication passes. |
| `SUPPORTED_CONDITIONAL` | The same bar, inside a regime declared before outcomes. |
| `SUPPORTED_BUT_PRODUCT_SPARSE` | Supported, but the product frequency gate fails. |
| `HETEROGENEOUS_UNEXPLAINED` | Statistical and practical gates pass, but concentration fails. It may seed a new hypothesis. |
| `NO_INCREMENTAL_STRUCTURE` | Statistical or practical failure against the nuisance baseline. |
| `INCONCLUSIVE` | Support, power or data are insufficient. |

**Discovery-only results.** At discovery stage a result that passes all gates is `PROMISING_PROTOTYPE`. A `SUPPORTED_*` class needs the replication.

**No switching.** The target class cannot be switched after outcomes.

## 6. Search surface and multiplicity

- Each (regime, estimand, horizon) is one primary cell. At most 3 primary cells per card.
- Holm applies within the card's `TEST_FAMILY_ID`.
- Every cell is registered in `SCIENTIFIC_TEST_LEDGER.json` before any outcome.
- Secondary results are descriptive and never promote.

## 7. Replication

Replication is time-disjoint from discovery and uses the same frozen rule. A same-period other venue is a robustness check, not replication.

## 8. No rescue

- A failed card is never re-scored with new parameters, regimes, horizons, sides or baselines.
- A post-hoc regime or variant is a new hypothesis. It gets a new `TEST_FAMILY_ID` and a surface it has not seen.
- Protected data rules are unchanged.

## 9. Product promotion

Only `SUPPORTED_UNCONDITIONAL` or `SUPPORTED_CONDITIONAL` can be promoted, and only after all of these:
- the product frequency gate;
- a claim-specific promotion gate with exact strings and forbidden wording, like `BETA_D7_REGIME_CONTEXT_GATE_V1`.

A directional or trading-relevant claim also needs the practical bar above costs on both surfaces. No other class is ever promoted.

## Adoption

| Field | Value |
|---|---|
| Adopted | not yet |
| By | owner |
| Applies from | the adoption commit |
