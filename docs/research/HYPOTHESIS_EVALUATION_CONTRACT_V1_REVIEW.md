# Hypothesis evaluation contract V1 — review

**Status:** `REVIEW_COMPLETE / V1_READY_FOR_OWNER_ADOPTION`
**Date:** 2026-10-01
**Unit:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW`, the post-D7 gate in `docs/RESEARCH_ROADMAP.md`. It runs after `D7_CAMPAIGN_CLOSE_V1`.
**Inputs:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_PROPOSAL.md`, plus the recorded results and closures listed in §2.
**Output:** `HYPOTHESIS_EVALUATION_CONTRACT_V1.md`, ready for owner adoption.
**Machine-readable twin:** `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.json`

```
HISTORICAL_VERDICTS_CHANGED        = false
MARKET_OUTCOMES_RECOMPUTED         = false
FAILURES_TURNED_INTO_SUPPORT       = 0
PROMISING_DOWNGRADED_BY_V1         = 2   (D12, C013 -> HETEROGENEOUS_UNEXPLAINED)
CLAIMS_WITH_INCOMPLETE_NUISANCE    = 2   (D7 scope note, D11)
V1_RED_TEAM                        = PASS_WITH_CLOSING_RULES
NEXT_UNIT                          = OWNER_ADOPTION_OF_HYPOTHESIS_EVALUATION_CONTRACT_V1
```

## 1. Replay method

- **Inputs only from the record.** Every number below is copied from a recorded result. The concentration figures are arithmetic on recorded yearly estimates, nothing else. No market file was opened.
- **Equal epoch weights.** Concentration uses equal year weights, because yearly sample sizes are within about ±10% except partial first years. The epoch contribution is the year estimate divided by the sum of year estimates. Leave-one-epoch-out (LOEO) is the mean of the remaining years, divided by the mean of all years.
- **What "V1 class" means.** It is what V1 would have said at that stage of evidence. Discovery-only results stay discovery tier. A "SUPPORTED" class requires the replication that V1 demands.
- **Verdicts are unchanged.** No historical verdict, status or routing changes.

## 2. Replay

| Object | Recorded verdict | Decisive recorded facts | V1 class | Effect of V1 |
|---|---|---|---|---|
| D1 structural state | `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH` | null not executable | not evaluable | none |
| D2 RULE_1 RV abstention | `PROMISING_PROTOTYPE`; BitMEX `SUPPORTED`; excess decomposition `VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT` | rule = abstain on high-RV days; comparator = rate-matched random abstention, not volatility-matched; years 2020–24 max share 0.32, LOEO ≥ 0.84; BitMEX years max share 0.37, LOEO ≥ 0.94 | `NO_INCREMENTAL_STRUCTURE` as a mechanism beyond volatility. As a plain volatility-persistence statement it is the nuisance itself. | V1's mandatory volatility baseline would have answered the mechanism question in the first run, without the later decomposition unit. |
| D2 RULE_2 dislocation abstention | gate fail | `DELTA = −0.0013`; statistical, practical and temporal all fail | `NO_INCREMENTAL_STRUCTURE` | none |
| D3 path morphology | `NO_USEFUL_STRUCTURE` | `MAX_DOWNSIDE` statistical pass; practical 10.8% < 15% bar | `NO_INCREMENTAL_STRUCTURE` | none: the practical bar is kept |
| D4 BTC–ETH rolling correlation | `NO_USEFUL_STRUCTURE` | statistical fail; excess range 0.039 < 0.15 | `NO_INCREMENTAL_STRUCTURE` | none |
| D5 composition | `NO_USEFUL_STRUCTURE` | composed `DELTA = 0.0043` does not beat the best component (0.0107) | `NO_INCREMENTAL_STRUCTURE` | none |
| D6 external benchmark | `DEFERRED` | not executed | not evaluable | none |
| D7 impact-state persistence | `PROMISING_PROTOTYPE`; BitMEX `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS` | baseline = rate-matched random state in `year × 4 RV quartiles`; discovery years max share 0.23, LOEO ≥ 0.96; confirmation 2017–19 max share 0.41, LOEO ≥ 0.88 | `SUPPORTED_UNCONDITIONAL` for state persistence **relative to a coarse-volatility-matched base** | Claim scope note: persistence beyond within-bucket volatility and relative volume is not tested (`D7_CAMPAIGN_CLOSE_V1`). The beta claim (state frequency) is unaffected. |
| D8 recovery clock | `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` | not executed | not evaluable | none |
| D9 venue dislocation resolution | `NO_USEFUL_STRUCTURE` | statistical gate = `P_HALF < 0.05 AND P_CONTROL < 0.05`; `P_HALF = 0.64` fails (`P_CONTROL = 0.002`); practical and temporal fail | `NO_INCREMENTAL_STRUCTURE` | none. The conjunctive gate is kept: one passing comparison never replaces a failed conjunct. |
| D10 BTC–ETH residual persistence | `NO_USEFUL_STRUCTURE` | `p = 0.455`; 0.14 bps | `NO_INCREMENTAL_STRUCTURE` | none |
| D11 FOMC → 6h RV | `PROMISING_PROTOTYPE` | baseline `year × weekday × UTC hour`, no prior-volatility matching; 39 events; years all positive, max share 0.30, LOEO ≥ 0.87 | discovery tier; at best `SUPPORTED_BUT_PRODUCT_SPARSE` (about 8 events a year) | Any future confirmation needs a prior-volatility nuisance baseline. Not promotable. |
| D12 DST participation clock | `PROMISING_PROTOTYPE` | 10 US transitions; yearly mean A 0.065, 0.015, −0.069, 0.256, 0.401; 2024 share 0.60; LOEO without 2024 = 0.4995 | `HETEROGENEOUS_UNEXPLAINED` | **Stricter.** It passed "k of n" rules but fails V1 concentration. |
| D13 cross-sectional weekly return | `NO_USEFUL_STRUCTURE` | statistical pass; practical fail | `NO_INCREMENTAL_STRUCTURE` | none |
| D2 excess path-risk decomposition | `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT` | statistical and practical fail beyond the year × side matched base | `NO_INCREMENTAL_STRUCTURE` | none. It is the V1 nuisance test, run late. |
| GV0R01-C013 wick morphology | `PROMISING_PROTOTYPE` | yearly −0.069, −0.068, −0.031, +0.032, +0.036; 2020 share 0.69; LOEO without 2020 = 0.38; controlled partial already includes nuisance | `HETEROGENEOUS_UNEXPLAINED` | **Stricter.** Two of five years have the opposite sign. Confirmation is already deferred as underpowered. |
| GV0R01-C004 | `CLOSED_OUTCOME_BLIND_INFERENCE_SUPPORT_INSUFFICIENT` | exact floor 0.0625 > alpha | `INCONCLUSIVE` (not executed) | none. V1's dependence-aware default agrees with the closure. |
| GV0R01-C012 | `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK` | MDE 0.61 > 0.50 | `INCONCLUSIVE` (not executed) | none |
| GV0R01-C020 | `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST` | stress power 0.40 | `INCONCLUSIVE` (not executed) | none |

**Summary of the replay:**
- **No failure becomes support.** Every recorded failure fails a statistical or practical bar, which V1 keeps. No failure rested on the temporal gate alone.
- **Two prototypes are downgraded.** D12 and C013 pass "k of n years" but concentrate in one or two epochs.
- **Two claims have an incomplete nuisance baseline:**
  - **D7:** the claim scope is recorded. The product claim is unaffected.
  - **D11:** its confirmation design must add a prior-volatility baseline.
- **D2 shows the cost of the missing baseline.** Two units (the BitMEX replication and the excess decomposition) were spent establishing what a volatility-matched baseline would have shown at discovery.

**What the replay cannot test.** The proposal's first concern is dilution: a pooled test can hide a regime effect. The record cannot show it, because finding a hidden regime would need new outcomes. V1 therefore admits regime claims only when declared in advance (§3).

## 3. Red team: new false-positive paths and their closing rules

| # | Path V1 could open | Closing rule (in the contract) |
|---|---|---|
| R1 | Regime shopping: choosing the regime after seeing outcomes | The regime is declared in the preregistration, computable point-in-time, and frozen in code before any outcome. A post-hoc regime only seeds a new hypothesis with a new test family and an unseen surface. |
| R2 | Declaring many regimes in advance | Each (regime, estimand, horizon) is one primary cell. At most 3 primary cells per card. Holm within the card's test family. All cells are registered in `SCIENTIFIC_TEST_LEDGER.json` before outcomes. |
| R3 | Outcome-class shopping | The target class (unconditional or conditional) is declared in the preregistration. The class is a mechanical function of the frozen gates. No switching. |
| R4 | Weakening the nuisance baseline by calling a nuisance variable "mechanism" | A standard nuisance set is mandatory: time of day where intraday, prior realized volatility at the decision time, and the lagged target. An exclusion needs a written mechanism argument in the preregistration, a red-team check, and an outcome-blind support diagnostic. |
| R5 | The opposite error: conditioning away the mechanism and losing support | An outcome-blind support check before outcomes, with cell counts. If matching leaves insufficient support, the design coarsens the nuisance as a frozen choice, or the card is `INCONCLUSIVE`. This is never decided after outcomes. |
| R6 | Concentration rules looser than year-universality | Maximum single-epoch contribution ≤ 0.5. Every LOEO estimate keeps the pooled sign and at least 0.5 of its magnitude. At least 3 epochs. Effective N reported. The replay shows this is stricter (D12, C013) and never looser. |
| R7 | Promoting sparse regimes | `SUPPORTED_BUT_PRODUCT_SPARSE` is never promotable on its own. The product frequency gate is separate. |
| R8 | "Replication" on overlapping data | Replication must be time-disjoint from discovery, using the same frozen rule. A same-period other venue is a robustness check, not replication. |
| R9 | Practical bar chosen to fit | The practical bar and its justification are frozen in the preregistration. Trading-relevant claims tie it to costs; context claims tie it to product relevance. |

With these rules, V1 is stricter than the current practice on concentration and baselines, and no looser anywhere.

## 4. Decisions the proposal required

1. **Product-promotable classes.** Only `SUPPORTED_UNCONDITIONAL` and `SUPPORTED_CONDITIONAL`, and only after all of the following:
   - time-disjoint replication with the same frozen rule passes;
   - the product frequency gate passes;
   - a claim-specific promotion gate with exact strings exists, like `BETA_D7_REGIME_CONTEXT_GATE_V1`.

   A directional or trading-relevant claim also needs a practical magnitude above costs on both surfaces. Every other class is never promotable.
2. **Regime choices in the search surface.** Each declared (regime, estimand, horizon) cell is one registered primary test under the card's `TEST_FAMILY_ID`, with Holm inside the family. A derived conditional hypothesis gets a new family ID and a fresh surface.

## 5. Consequences

**Records:**
- **D7:** claim scope recorded in `D7_CAMPAIGN_CLOSE_V1`.
- **D11:** a future confirmation design must add the prior-volatility baseline. Nothing is authorized.
- **D12 and C013:** verdicts unchanged. A future confirmation design must address concentration before any power claim.

**Decision-layer program** (`DECISION_LAYER_RESEARCH_PROGRAM_V0.md`):
- Once V1 is adopted, its scoped profile is superseded by V1.
- The TWAP footprint preregistration will be the first card frozen under V1.
- The outcome-blind TWAP feasibility unit is unaffected.

**Sequence after adoption:**
1. `GV0R02` feasibility compiler and generator feasibility-contract mapping update.
2. A fresh Generator V0 shadow campaign under a new run ID, not a continuation of v7. Its slot plan requires orthogonal families.
3. A shortlist of at most 5.
4. Feasibility compiler.
5. One or two preregistrations.
6. One-shot discovery.
7. Time-disjoint confirmation.

## 6. Recommendation

Adopt `HYPOTHESIS_EVALUATION_CONTRACT_V1.md` as written. It does not apply retroactively. It covers cards registered after adoption.
