# Hypothesis evaluation contract V1 — proposal

**Status:** `DEFERRED` · `PROPOSED / DEFERRED_UNTIL_D7_CAMPAIGN_CLOSE`
**Recorded:** 2026-09-30
**Authority:** none. This file does not change how any hypothesis is evaluated today.
**Reviewed 2026-10-01:** see `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.md`. The contract text, ready for owner adoption, is `HYPOTHESIS_EVALUATION_CONTRACT_V1.md`.

```
ACTIVE_CONTRACT_CHANGED   = false
CURRENT_D7_RULES_CHANGED  = false
NEXT_REVIEW               = HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW
NEXT_REVIEW_TRIGGER       = AFTER_D7_CAMPAIGN_CLOSE
```

`EDGE_RESEARCH_PROTOCOL.md`, the GV0R02 feasibility compiler, and every frozen
preregistration, permit, and result keep their current force. The D7 BitMEX
confirmation campaign runs entirely under its own frozen rules. Nothing here may
be used to reinterpret a D7 outcome or any other historical verdict.

## Why a review is required after D7

1. **A pooled or unconditional test can dilute a strong conditional effect.**
   For example, a mechanism worth +0.10 that is active 20% of the time shows up
   as about +0.02 in a pooled test. It then fails the practical gate, although it
   is useful inside its regime.
2. **Calendar-year stability is not scientific robustness.** A rule such as
   "positive in k of n years" measures one kind of concentration. It is not
   evidence of a mechanism, and requiring universality searches for something
   markets rarely offer.
3. **The baseline must remove obvious volatility and volume persistence without
   conditioning away the mechanism itself.** D2 (`VOLATILITY_SCALE_COMPATIBLE`),
   the PRICE_OI P4 follow-up (volatility clustering), and D7 (which relative-volume
   persistence may partly explain) all point to second-moment persistence that
   the baseline did not remove. Conditioning on a variable that defines the
   mechanism has the opposite problem: it removes support. For D7 an RV × relative
   volume stratification makes the state almost deterministic in the extreme cells.
4. **Scientific validity and product usefulness are different questions** and
   need separate gates.

The goal is precision, not leniency. In the recorded discovery results checked
for this note (D5, D9, D10, D13 and the D2 excess-alignment decomposition), every
failing card also failed a statistical or practical gate. None failed on a
temporal gate alone. D13 passed the statistical gate and failed the practical
gate. The review must check that V1 does not simply add ways to declare success.

## Proposed V1

- The hypothesis declares its **domain / regime** before any outcome is seen.
- The regime must be **point-in-time observable** at the decision time and
  frozen.
- The **primary effect** is evaluated inside the declared domain.
- The **nuisance baseline** is matched inside the same domain.
- Variable roles are separated explicitly:
  - `REGIME_VARIABLES` define where the mechanism is claimed to operate;
  - `MECHANISM_VARIABLES` define the mechanism and must not be conditioned away;
  - `NUISANCE_BASELINE_VARIABLES` capture the obvious explanations (volatility,
    volume and target persistence, time of day, window-overlap artifacts) that the
    baseline must remove.
- **Practical magnitude** remains required.
- Naive year-universality is replaced by **evidence-concentration checks**:
  - effective number of independent episodes;
  - epoch concentration, meaning no single period supplies most of the effect;
  - leave-one-epoch-out robustness.
- **Independent replication** remains required (another era or venue, with the
  same regime rule).
- **Product frequency** (how often the regime is on, and whether it is actionable)
  is a separate product gate, not a scientific truth gate.
- **An outside-regime null or attenuation** is optional mechanism-specificity
  evidence, not a requirement.
- **Post-hoc regime discovery cannot rescue the original hypothesis.** It can
  only generate a new conditional hypothesis, which needs fresh validation on a
  surface it has not seen.

### Potential outcome classes (draft)

| Class | Draft meaning |
|---|---|
| `SUPPORTED_UNCONDITIONAL` | Effect beyond the nuisance baseline across the whole declared population, practically large, not concentrated, replicated. |
| `SUPPORTED_CONDITIONAL` | The same bar, met inside a regime declared before outcomes. |
| `SUPPORTED_BUT_PRODUCT_SPARSE` | Scientifically supported, but the regime is too rare or too hard to act on for the product gate. |
| `HETEROGENEOUS_UNEXPLAINED` | Aggregate effect present, but it is concentrated or unstable across epochs, with no pre-declared explanation. It may seed a new conditional hypothesis. |
| `NO_INCREMENTAL_STRUCTURE` | No effect beyond the nuisance baseline, or below the practical bar. |
| `INCONCLUSIVE` | Support, power, or data are insufficient to decide. |

Which classes may be promoted into the product is decided in the review, before
V1 is adopted. That decision is not left open for later.

## Carried over from the D7 design work, as review inputs

These came up while designing the D7 BitMEX confirmation. They are inputs to the
review, not adopted rules.

- **Twin preregistration.** Freeze the conditional confirmation plan together with
  the discovery design: surface, estimand, effect bar, and power at 50% and 75%
  of the discovery effect. Then nothing needs to be decided between discovery and
  confirmation.
- **Estimand separate from inference.** Name the estimated quantity and its
  weights (for example ATT over candidate states) separately from the procedure
  used for its uncertainty. The practical bar is tied to the estimand.
- **Dependence-aware inference by default.** Use HAC or block methods with a lag
  or block length that covers the construction overlap, and report the effective
  N. Use exchangeable or IID nulls only with a written justification.
- **Portable gates.** Express gates as a fraction of eligible periods, plus an
  eligibility rule, plus the pass probability under random signs, instead of
  surface-specific counts such as "3 of 5 years".
- **Calibration acceptance direction.** Accept a test's type-I calibration only
  when the upper confidence bound is below a tolerance ceiling. The ceiling and
  the number of simulations are fixed before the calibration run.

## Before adoption: `HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW`

This is a separate unit, run after the D7 confirmation campaign is closed. Steps:

1. Replay the verdicts of D2–D13 and the GV0R01 C-series (C004, C012, C013,
   C020) retrospectively under V1. Historical results are not changed. The replay
   reports what each verdict would have been and why.
2. Audit whether V1 creates new false-positive paths: regime shopping, outcome-class
   shopping, weaker baselines, or promotion of sparse regimes.
3. Decide which outcome classes are product-promotable, and how regime choices
   are counted in the search surface (`SCIENTIFIC_TEST_LEDGER.json`).
4. Only then adopt V1 as a new contract version, and update the GV0R02
   feasibility compiler and the generator contract to match it.
