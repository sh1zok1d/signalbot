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
PROMISING_DOWNGRADED_BY_V1         = 1   (C013 -> HETEROGENEOUS_UNEXPLAINED)
CLAIMS_WITH_INCOMPLETE_NUISANCE    = 2   (D7 scope note, D11)
OVERSTRICT_RULES_FOUND_AND_FIXED   = 3   (hard share rule; no context-claim type; no prospective replication)
V1_RED_TEAM                        = PASS_WITH_CLOSING_RULES
NEXT_UNIT                          = OWNER_ADOPTION_OF_HYPOTHESIS_EVALUATION_CONTRACT_V1
```

## 1. Replay method

- **Inputs only from the record.** Every number comes from a recorded result. That includes the D12 per-transition values and the C013 weekly series, both already stored in their result files. No market file was opened.
- **Heterogeneity checks.** They run on those recorded values:
  - block permutation of units across epochs (D12: transitions; C013: 13- and 26-week blocks);
  - per-epoch Newey–West standard errors (lag 4) for C013.
- **Shares.** The epoch share is the year estimate divided by the sum of year estimates, with equal year weights. Leave-one-epoch-out (LOEO) is the mean of the remaining years divided by the mean of all years. Both are reported as diagnostics only.
- **What "V1 class" means.** It is what V1 would have said at that stage of evidence. Discovery-only results stay discovery tier.
- **Verdicts are unchanged.** No historical verdict, status or routing changes.

## 2. Replay

| Object | Recorded verdict | Decisive recorded facts | V1 class | Effect of V1 |
|---|---|---|---|---|
| D1 structural state | `DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH` | null not executable | not evaluable | none |
| D2 RULE_1 RV abstention | `PROMISING_PROTOTYPE`; BitMEX `SUPPORTED`; excess decomposition `VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT` | comparator = rate-matched random abstention; all years positive (2020–24 and BitMEX 2017–19) | as `INCREMENTAL`: `NO_INCREMENTAL_STRUCTURE` beyond volatility. As `CONTEXT_DESCRIPTIVE`: supported and replicated against its stated comparator. | V1's volatility baseline would have answered the mechanism question at discovery. The context reading could be proposed for a risk-context gate later. Nothing is authorized here. |
| D2 RULE_2 dislocation abstention | gate fail | `DELTA = −0.0013`; statistical, practical and temporal all fail | `NO_INCREMENTAL_STRUCTURE` | none |
| D3 path morphology | `NO_USEFUL_STRUCTURE` | `MAX_DOWNSIDE` statistical pass; practical 10.8% < 15% bar | `NO_INCREMENTAL_STRUCTURE` | none |
| D4 BTC–ETH rolling correlation | `NO_USEFUL_STRUCTURE` | statistical fail; excess range 0.039 < 0.15 | `NO_INCREMENTAL_STRUCTURE` | none |
| D5 composition | `NO_USEFUL_STRUCTURE` | composed `DELTA = 0.0043` does not beat the best component (0.0107) | `NO_INCREMENTAL_STRUCTURE` | none |
| D6 external benchmark | `DEFERRED` | not executed | not evaluable | none |
| D7 impact-state persistence | `PROMISING_PROTOTYPE`; BitMEX `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS` | baseline = rate-matched random state in `year × 4 RV quartiles`; every year positive in both eras | `SUPPORTED_UNCONDITIONAL` as `CONTEXT_DESCRIPTIVE` (state frequency against a coarse-volatility-matched base) | Claim scope note: persistence beyond within-bucket volatility and relative volume is not tested (`D7_CAMPAIGN_CLOSE_V1`). The beta claim is unaffected. |
| D8 recovery clock | `DEFERRED_INSUFFICIENT_CONTROL_SUPPORT` | not executed | not evaluable | none |
| D9 venue dislocation resolution | `NO_USEFUL_STRUCTURE` | statistical gate = `P_HALF < 0.05 AND P_CONTROL < 0.05`; `P_HALF = 0.64` fails (`P_CONTROL = 0.002`); practical and temporal fail | `NO_INCREMENTAL_STRUCTURE` | none. One passing comparison never replaces a failed conjunct. |
| D10 BTC–ETH residual persistence | `NO_USEFUL_STRUCTURE` | `p = 0.455`; 0.14 bps | `NO_INCREMENTAL_STRUCTURE` | none |
| D11 FOMC → 6h RV | `PROMISING_PROTOTYPE` | baseline `year × weekday × UTC hour`, no prior-volatility matching; 39 events; every year positive | discovery tier; at best `SUPPORTED_BUT_PRODUCT_SPARSE` (about 8 events a year) | Any future confirmation needs the prior-volatility diagnostic, and the prior-volatility baseline if framed as `INCREMENTAL`. |
| D12 DST participation clock | `PROMISING_PROTOTYPE` | 10 US transitions; yearly mean A 0.065, 0.015, −0.069, 0.256, 0.401; heterogeneity `p = 0.087`; no year significantly negative | discovery tier, unchanged (heterogeneity not significant, low power) | none. The 2023–24 strength may seed a declared-era hypothesis. |
| D13 cross-sectional weekly return | `NO_USEFUL_STRUCTURE` | statistical pass; practical fail | `NO_INCREMENTAL_STRUCTURE` | none |
| D2 excess path-risk decomposition | `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT` | statistical and practical fail beyond the year × side matched base | `NO_INCREMENTAL_STRUCTURE` | none. It is the V1 nuisance test, run late. |
| GV0R01-C013 wick morphology | `PROMISING_PROTOTYPE` | yearly −0.069 (t −8.0), −0.068 (t −5.4), −0.031 (t −2.7), +0.032 (t +3.4), +0.036 (t +2.8); heterogeneity `p < 0.0001` (13-week blocks), `p = 0.016` (26-week blocks) | `HETEROGENEOUS_UNEXPLAINED` | **Stricter, and correctly so.** The sign genuinely reverses: 2023 and 2024 are significantly opposite. Confirmation was already deferred as underpowered. |
| GV0R01-C004 | `CLOSED_OUTCOME_BLIND_INFERENCE_SUPPORT_INSUFFICIENT` | exact floor 0.0625 > alpha | `INCONCLUSIVE` (not executed) | none |
| GV0R01-C012 | `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK` | MDE 0.61 > 0.50 | `INCONCLUSIVE` (not executed) | none |
| GV0R01-C020 | `CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST` | stress power 0.40 | `INCONCLUSIVE` (not executed) | none |

**Summary of the replay:**
- **No failure becomes support.** Every recorded failure fails a statistical or practical bar, which V1 keeps.
- **One prototype is downgraded: C013.** Its sign reversal is real.
- **D12 is not downgraded.** Its apparent concentration is within noise for 10 units. That does not show stability: at N = 10, heterogeneity cannot be reliably assessed.
- **Two claims have an incomplete nuisance baseline:**
  - **D7:** the claim scope is recorded; the product claim is unaffected;
  - **D11:** a confirmation needs the prior-volatility check.
- **D2 shows the cost of the missing baseline.** Two units (the BitMEX replication and the excess decomposition) established what a volatility-matched diagnostic would have shown at discovery.

**What the replay cannot test.** The proposal's first concern is dilution: a pooled test can hide a regime effect. The record cannot show it, because finding a hidden regime would need new outcomes. V1 therefore admits regime claims only when declared in advance.

## 3. Calibration: is V1 too strict?

The owner asked that "stricter" must not mean killing real mechanisms. The rule for V1 itself (contract preamble) is that a rejection rule which often rejects a real, homogeneous effect is miscalibrated. Three such rules were found in the first draft and fixed.

**F1. Hard concentration share. Replaced by a calibrated test.**

The first draft required that no year contribute more than half of the effect, and that every LOEO estimate keep half of it. On recorded data, under a null where the effect is the same in every year:

| Case | `P(max share > 0.5)` under constant effect | Observed share | `P(share ≥ observed)` |
|---|---|---|---|
| D12 (10 transitions, years exchangeable) | 0.33 | 0.60 | 0.07 |
| C013 (weekly series, 13-week blocks) | 0.46 | 0.69 | 0.07 |
| C013 (26-week blocks) | 0.84 | 0.69 | 0.31 |

The share rule would reject a third to most of the genuinely homogeneous effects of this size and noise. It has been replaced by a dependence-preserving heterogeneity test plus a per-epoch opposite-sign test, with shares kept as diagnostics. A heterogeneity test that cannot reach 50% power is recorded as `NOT_ASSESSABLE`, not as a failure. Results:
- **D12:** heterogeneity `p = 0.087`. It stays a prototype.
- **C013:** heterogeneity `p < 0.0001` (13-week blocks) or `0.016` (26-week blocks), with 2023 and 2024 significantly opposite. It stays flagged.

**F2. Every product claim forced to beat the nuisance baseline. Split by claim type.**

Requiring every claim to be incremental over volatility would block replicated, useful risk context. D2 is the example: "after very volatile days the next day's adverse move was larger" is true, replicated, and relevant to a risk decision. It does not beat volatility, because it *is* volatility persistence.
- **Fix:** `CONTEXT_DESCRIPTIVE` claims use a stated ordinary-conditions comparator. The nuisance-matched number is mandatory as a diagnostic and decides the wording: no claim of extra information if it vanishes.
- **Unchanged:** directional, mechanism and trading-relevant claims must still be `INCREMENTAL`.

**F3. Replication only on historical eras. Prospective surface added.**

A mechanism that appeared recently cannot replicate on an older era that predates it.
- **Fix:** data collected after the analysis is frozen counts as time-disjoint replication.
- **Protected data:** data inside the protected 2025/2026 window still needs its own decision; V1 does not grant it.

**`HETEROGENEOUS_UNEXPLAINED` also no longer reads as a dead end.** It explicitly seeds a declared-regime or declared-era hypothesis.

**What stays strict, and why it does not kill real mechanisms:**
- **Pre-declared regimes, claim type and target class.** These restrict choices, not effects.
- **Dependence-aware inference.** It removes overstated certainty. A real effect with enough data still passes.
- **The practical bar.** It is frozen with a justification, so it is not tuned to kill or to pass.
- **No rescue.** A failed card can still lead to a new, pre-declared hypothesis on unseen data.

### Pre-adoption amendments (owner review, 2026-10-01)

Two lines were made explicit before adoption:
- **A1. Fixed stopping rule for prospective replication.** The episode count or end date (whichever first) and the minimum N are frozen before the data exists. Only counts are monitored, and there is one analysis at the stop. A shortfall is `INCONCLUSIVE`; it is not extended.
- **A2. No stability claim from heterogeneity tests.** `NOT_ASSESSABLE` or a non-significant heterogeneity test is never reported as stability across epochs. Example: D12 is "not downgraded; heterogeneity could not be reliably assessed at N = 10", not "stable".

## 4. Red team: new false-positive paths and their closing rules

| # | Path V1 could open | Closing rule (in the contract) |
|---|---|---|
| R1 | Regime shopping: choosing the regime after seeing outcomes | The regime is declared in the preregistration, computable point-in-time, and frozen in code before any outcome. A post-hoc regime only seeds a new hypothesis with a new test family and an unseen surface. |
| R2 | Declaring many regimes in advance | Each (regime, estimand, horizon) is one primary cell. At most 3 primary cells per card. Holm within the card's test family. All cells are registered in `SCIENTIFIC_TEST_LEDGER.json` before outcomes. |
| R3 | Outcome-class or claim-type shopping | Claim type and target class are declared in the preregistration. The class is a mechanical function of the frozen gates. No switching. |
| R4 | Weakening the nuisance baseline by calling a nuisance variable "mechanism" | For `INCREMENTAL` claims a standard nuisance set is mandatory: time of day where intraday, prior realized volatility at the decision time, and the lagged target. An exclusion needs a written mechanism argument, a red-team check, and an outcome-blind support diagnostic. |
| R4b | Presenting a context claim as new information | The nuisance-matched number is mandatory for `CONTEXT_DESCRIPTIVE` claims and decides the wording. A context claim may never be directional. |
| R5 | The opposite error: conditioning away the mechanism and losing support | An outcome-blind support check before outcomes, with cell counts. If matching leaves insufficient support, the design coarsens the nuisance as a frozen choice, or the card is `INCONCLUSIVE`. This is never decided after outcomes. |
| R6 | A heterogeneity rule that is too loose, or too strict (F1) | A dependence-preserving heterogeneity test with a frozen `alpha_het`, plus a per-epoch opposite-sign test. Power is computed outcome-blind. Shares are diagnostic. |
| R7 | Promoting sparse regimes | `SUPPORTED_BUT_PRODUCT_SPARSE` is never promotable on its own. The product frequency gate is separate. |
| R8 | "Replication" on overlapping data, a prospective surface chosen after seeing data, or optional stopping | Replication is time-disjoint with the same frozen rule. A prospective surface counts only if the analysis and a fixed stopping rule were frozen before the data existed, with counts-only monitoring and one analysis at the stop. A same-period other venue is robustness only. Protected-window data needs its own decision. |
| R9 | Practical bar chosen to fit | The practical bar and its justification are frozen in the preregistration. Trading-relevant claims tie it to costs; context claims tie it to product relevance. |

## 5. Decisions the proposal required

1. **Product-promotable classes.** Only `SUPPORTED_UNCONDITIONAL` and `SUPPORTED_CONDITIONAL`, and only after all of these:
   - time-disjoint replication with the same frozen rule passes (historical or prospective);
   - the product frequency gate passes;
   - a claim-specific promotion gate with exact strings exists, like `BETA_D7_REGIME_CONTEXT_GATE_V1`.

   A `CONTEXT_DESCRIPTIVE` claim names its comparator and is never directional. A directional or trading-relevant claim must be `INCREMENTAL`, with a practical magnitude above costs on both surfaces. Every other class is never promotable.
2. **Regime choices in the search surface.** Each declared (regime, estimand, horizon) cell is one registered primary test under the card's `TEST_FAMILY_ID`, with Holm inside the family. A derived conditional hypothesis gets a new family ID and a fresh surface.

## 6. Consequences

**Records:**
- **D7:** claim scope recorded in `D7_CAMPAIGN_CLOSE_V1`.
- **D11:** a future confirmation needs the prior-volatility check. Nothing is authorized.
- **D12:** unchanged. A declared-era hypothesis about growing US-clock anchoring is a possible future card.
- **C013:** unchanged verdict. Any future work must address the sign reversal before any power claim.
- **D2:** its replicated context reading is eligible to be proposed for a risk-context promotion gate. That needs its own owner decision.

**Decision-layer program** (`DECISION_LAYER_RESEARCH_PROGRAM_V0.md`):
- Once V1 is adopted, its scoped profile is superseded by V1.
- The TWAP footprint preregistration will be the first card frozen under V1, as an `INCREMENTAL` claim over net taker flow.
- The outcome-blind TWAP feasibility unit is unaffected.

**Sequence after adoption:**
1. `GV0R02` feasibility compiler and generator feasibility-contract mapping update.
2. A fresh Generator V0 shadow campaign under a new run ID, not a continuation of v7. Its slot plan requires orthogonal families.
3. A shortlist of at most 5.
4. Feasibility compiler.
5. One or two preregistrations.
6. One-shot discovery.
7. Time-disjoint confirmation.

## 7. Recommendation

Adopt `HYPOTHESIS_EVALUATION_CONTRACT_V1.md` as written. It does not apply retroactively. It covers cards registered after adoption.
