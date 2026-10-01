# Hypothesis evaluation contract V1

**Status:** `ADOPTED` (owner, 2026-10-01). Active contract for every hypothesis card registered after adoption. Adoption is recorded below.
**Date:** 2026-10-01
**Review:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.md`
**Proposal:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_PROPOSAL.md`

**Scope.** V1 governs every hypothesis card registered after adoption. It is not retroactive: every frozen preregistration, permit, result and verdict keeps its force. `EDGE_RESEARCH_PROTOCOL.md` still governs whatever V1 does not cover. The GV0R02 feasibility compiler and the generator feasibility contract are updated to V1 in a separate unit.

**Design rule for V1 itself.** A rule exists to stop noise and post-hoc choices from passing as findings. A rule that would often reject a real, homogeneous effect of the planned size is miscalibrated and must be fixed, not kept. Every rejection rule in this contract is calibrated against a constant-effect null (§4).

## 1. Twin preregistration

The discovery plan and the confirmation plan are frozen together, before any outcome of the card is computed. The preregistration fixes:
- the discovery surface and the time-disjoint confirmation surface (§7), plus a fallback chosen by outcome-blind support only;
- the claim type (§2);
- the estimand and its weights;
- the inference procedure, kept separate from the estimand;
- horizons and primary cells (§6);
- the practical bar (§4);
- the target class: unconditional or conditional;
- planning power at 50% and 75% of a planning effect on both surfaces;
- the code and data identities.

## 2. Claim type, domain and variable roles

**Claim type.** It is declared in the preregistration and cannot change after outcomes.
- `CONTEXT_DESCRIPTIVE` is a non-directional statement about what followed a state: range, volatility, or the state's own frequency. The comparator is an ordinary-conditions base, such as the same time of day or a rate-matched random state, and the claim text names it. It says nothing about what caused the effect.
- `INCREMENTAL` covers any mechanism claim, any directional claim, and anything trading-relevant. It must beat the nuisance baseline (§3).

**Variables.** The preregistration names three kinds:
- `REGIME_VARIABLES`: where the claim operates. Required for a conditional claim.
- `MECHANISM_VARIABLES`: what defines the mechanism. Never conditioned away.
- `NUISANCE_BASELINE_VARIABLES`: obvious explanations the baseline removes.

Every regime and every event is computable point-in-time at the decision boundary, and frozen in code before outcomes.

## 3. Nuisance baseline

**For `INCREMENTAL` claims**, a standard nuisance set is mandatory:
- time of day, for intraday claims;
- prior realized volatility at the decision time;
- the lagged target, which covers persistence of the target itself.

Obvious card-specific explanations are added. Example: prior net taker flow for any order-flow claim.

**Excluding a standard variable** needs a written argument that it defines the mechanism, a red-team check, and the support diagnostic. Example: the lagged target in a persistence claim.

**For `CONTEXT_DESCRIPTIVE` claims**, the ordinary-conditions comparator is primary. The nuisance-matched estimate is still computed and reported as a diagnostic, and it decides the wording. If the effect disappears against the nuisance, the claim must say it reflects the general volatility regime and must never present the state as extra information.

**Support diagnostic** (outcome-blind, before outcomes): cell counts after matching. If support is insufficient, the design coarsens the nuisance as a frozen choice, or the card is `INCONCLUSIVE`.

## 4. Gates

All gates are conjunctive and mechanical:
1. **Integrity.** Identities match and the run is one-shot.
2. **Statistical.** Dependence-aware by default: block or HAC methods, with block or lag length covering construction overlap. An exchangeable or IID null needs a written justification. Effective N is reported.
3. **Practical.** The bar is frozen with its justification:
   - trading-relevant claims: above costs;
   - context claims: product relevance.
4. **Epoch heterogeneity.** This replaces "positive in k of n years". The epochs are calendar years unless declared otherwise; at least 3 epochs need a defined estimate.
   - **Heterogeneity test.** The between-epoch dispersion of the epoch estimates is compared with a dependence-preserving null that holds the effect constant across epochs. That null is a block permutation of units across epochs, with the block length covering dependence. Seed and draws are frozen; `alpha_het = 0.05`.
   - **Opposite-sign test.** An epoch fails if its estimate has the opposite sign to the pooled estimate with one-sided `p < 0.05`, using a dependence-aware standard error.
   - **Outcome:**
     - heterogeneity not significant: the gate passes. This means consistent with homogeneity at this power, not that homogeneity is shown;
     - heterogeneity significant but no epoch significantly opposite: the gate passes with `MAGNITUDE_VARIES_BY_EPOCH`, and product wording must not claim more magnitude precision than the epochs support;
     - heterogeneity significant and at least one epoch significantly opposite: the gate fails, and the class is `HETEROGENEOUS_UNEXPLAINED`.
   - **Diagnostics only.** The largest epoch share and the leave-one-epoch-out estimates are reported but never decide. With few or noisy units a hard share rule rejects many homogeneous effects (review §3).
   - **Low power.** If the heterogeneity test has under 50% power, computed outcome-blind, to detect a 2× difference between epochs, it is recorded as `NOT_ASSESSABLE` and does not fail the card.
   - **Not evidence of stability.** Neither `NOT_ASSESSABLE` nor a non-significant result is evidence that the effect is stable across epochs. Records and product wording say "heterogeneity could not be reliably assessed at this N". They never say "stable across epochs". Only a replication that passes raises that confidence.

An outside-regime null or attenuation is optional specificity evidence, never a gate.

## 5. Outcome classes

The class is a mechanical function of the frozen gates, the claim type and the declared target class:

| Class | Meaning |
|---|---|
| `SUPPORTED_UNCONDITIONAL` | All gates pass across the declared population, and replication passes. |
| `SUPPORTED_CONDITIONAL` | The same bar, inside a regime declared before outcomes. |
| `SUPPORTED_BUT_PRODUCT_SPARSE` | Supported, but the product frequency gate fails. |
| `HETEROGENEOUS_UNEXPLAINED` | Statistical and practical gates pass, but the epoch-heterogeneity gate fails. |
| `NO_INCREMENTAL_STRUCTURE` | A statistical or practical failure against the primary comparator. |
| `INCONCLUSIVE` | Support, power or data are insufficient. |

**Discovery-only results.** At discovery stage a result that passes all gates is `PROMISING_PROTOTYPE`. A `SUPPORTED_*` class needs the replication.

**`HETEROGENEOUS_UNEXPLAINED` does not end the line of research.** It can seed a new hypothesis that declares the regime or era up front. That new hypothesis gets a new test family and is tested on a time-disjoint surface (§7).

**No switching.** The claim type and target class cannot be switched after outcomes.

## 6. Search surface and multiplicity

- Each (regime, estimand, horizon) is one primary cell. At most 3 primary cells per card.
- Holm applies within the card's `TEST_FAMILY_ID`.
- Every cell is registered in `SCIENTIFIC_TEST_LEDGER.json` before any outcome.
- Secondary results are descriptive and never promote.

## 7. Replication

Replication is time-disjoint from discovery and uses the same frozen rule.
- **Earlier or later era.** An earlier or later historical era qualifies.
- **Prospective surface.** Data that did not exist when the analysis was frozen also qualifies. This lets a mechanism that emerged recently be replicated even though older history predates it.
- **Fixed stopping rule for a prospective surface.** Before any confirmatory data exists, the preregistration freezes all of the following:
  - the stopping rule: a fixed number of eligible episodes or a fixed end date, whichever comes first;
  - the minimum N.

  Rules for the window:
  - Before the stop, only counts (eligibility and coverage) may be monitored. No test statistic, no effect estimate and no interim look.
  - Exactly one analysis runs, at the stop.
  - If the end date arrives below the minimum N, the result is `INCONCLUSIVE`. Extending the window is a new preregistration on later data, never a continuation.
  - If the product shows any statistic built from the same observations during the window, the preregistration states how that exposure is handled. See the 2026-09-28 amendment in `BETA_V0_PROSPECTIVE_FORWARD_EVALUATION.md`.
- **Protected data.** Data inside the protected 2025/2026 window, including live collection, still needs a decision under the protected-data rules. V1 does not grant it.
- **Same-period other venue.** A same-period other venue is a robustness check, not replication.

## 8. No rescue

- A failed card is never re-scored with new parameters, regimes, horizons, sides, baselines or claim type.
- A post-hoc regime or variant is a new hypothesis. It gets a new `TEST_FAMILY_ID` and a surface it has not seen.
- Protected data rules are unchanged.

## 9. Product promotion

Only `SUPPORTED_UNCONDITIONAL` or `SUPPORTED_CONDITIONAL` can be promoted, and only after all of these:
- the product frequency gate;
- a claim-specific promotion gate with exact strings and forbidden wording, like `BETA_D7_REGIME_CONTEXT_GATE_V1`.

**Wording.** A `CONTEXT_DESCRIPTIVE` claim names its comparator and never implies a mechanism or a direction. A directional or trading-relevant claim must be `INCREMENTAL`, with the practical bar above costs on both surfaces.

No other class is ever promoted.

## Adoption

| Field | Value |
|---|---|
| Adopted | 2026-10-01 |
| By | owner ("V1 принимаю, мержи #278") |
| Adopted text | this file as merged in PR #278, merge commit `0db19833adcfa97feac754c3a2108b86122469c5`, including the pre-adoption amendments A1 (fixed stopping rule for prospective replication) and A2 (no stability claim from heterogeneity tests) |
| Applies from | the commit that records this adoption; it covers cards registered after it, and it is not retroactive |
| Supersedes | the scoped evaluation profile in `DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §4 |
| Not yet aligned | the GV0R02 feasibility compiler and the generator feasibility contract (next unit) |
