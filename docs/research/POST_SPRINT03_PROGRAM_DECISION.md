# Post-Sprint 03 Program Decision

**Unit:** `DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION`
**Date:** 2026-09-22
**Base:** `origin/main` `d74255545f709d002733b2cb5d0aa447d7b30198` (tree `9162dfdbd00d0d28ebf9a4be2bc053ca72748f31`)
**Machine-readable record:** `docs/research/POST_SPRINT03_PROGRAM_DECISION.json`

This is a program-level decision. It computes no scientific outcome, does
not modify the D9/D10/D11 RESULT artifacts, and does not confirm D7 or D11.

## Card states

```
D9  = consumed NO_USEFUL_STRUCTURE
D10 = consumed NO_USEFUL_STRUCTURE
D11 = consumed PROMISING_PROTOTYPE

INTERNAL_DISCOVERY_CARDS_EXECUTED = 8
INTERNAL_PROMISING_PROTOTYPES     = 3

D7_CONFIRMATION_SELECTED_NOW  = false
D11_CONFIRMATION_SELECTED_NOW = false
```

D7 and D11 remain confirmation candidates. Neither is selected now because
the bottleneck is still mechanism-space coverage and discovery-method
maturity, not confirmation of every positive discovery.

D9 and D10 are not rescued. No threshold, horizon, window, refractory,
bootstrap, clipping, or relabel child of either is permitted.

## Program observations

1. **Second-moment concentration.** All three promising prototypes are
   volatility or activity-level structures: D2 decomposed as
   volatility-scale compatible (not excess direction-aligned risk), D7 is
   impact-state persistence, D11 is unsigned event volatility. Every
   direction/return card so far is null. The three positives may partly be
   one phenomenon (volatility clustering / heteroskedasticity) and must not
   be counted as three independent mechanisms until that is assessed.
2. **Information concentration.** All eight executed internal cards used
   BTC, plus at most ETH or one second venue. No card has used a true
   cross-section, forward expectations, or an identification design.
3. **D11 matching note.** D11 matched controls on UTC hour within year,
   which mixes different New York clock positions across DST. This is
   recorded only as a design consideration for any future D11
   confirmation. The consumed D11 RESULT is not modified or reinterpreted.

## Consequences

- Sprint 04 selects **no volatility-level card**. It selects D12
  (participation timing, natural experiment) and D13 (first true
  cross-sectional panel, relative-return target). See
  `docs/research/DISCOVERY_SPRINT_04.md`.
- Hypothesis-generation policy moves to
  `HETEROGENEOUS_FAMILY_ROTATION_V3` (V2 preserved as history).
- `MECHANISM_MEMORY_V0` is left unchanged. It is frozen as of
  post-Sprint 03 and already contains D9, D10 and D11. The post-Sprint 04
  decision needs mechanism memory extended through the D12/D13 outcomes
  after they execute; existing entries are not rewritten.

## Post-Sprint 04 automation checkpoint

```
EXPECTED_INTERNAL_DISCOVERY_CARDS_EXECUTED_AFTER_SPRINT04 = 10
POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED       = true
AUTOMATIC_SPRINT05                                        = false
```

After Sprint 04 the project must choose exactly one:

- **A.** `HYPOTHESIS_GENERATOR_V0_INFRA_READY`
- **B.** `AT_MOST_ONE_FINAL_SPRINT05`

B requires a named, uncovered mechanism region whose omission would make
the evaluation of the discovery process materially incomplete. "Search a
little more" and "maybe another positive" are not sufficient. The only
region named now as potentially B-eligible is **forward expectations**
(options implied vs realized, candidate S4-C04): it is the only major
information class with zero executed cards.

### Generator readiness criteria (assessed at that decision)

| Criterion | State now |
|---|---|
| ≥10 executed internal cards | 8 now; 10 expected after Sprint 04 |
| ≥6 distinct mechanism families executed | A, C, D, E, G, H + composed D5; J added by D12 |
| ≥4 clean negatives | D3, D4 rolling, D5, D9, D10 |
| ≥2 prototypes with distinctness assessed | 3 exist; second-moment concentration must be assessed |
| Structured mechanism memory current through D13 | required; V0 is current through D11 and must be extended with D12/D13 outcomes |
| Machine-readable anti-rescue lineage | rotation V2/V3 and card definitions |
| Data-feasibility metadata per candidate | Sprint 03/04 candidate pools |
| Deterministic card schema | contract fields exist; must be consolidated and validated |
| Evidence-state semantics | in use |
| Duplicate-detection history | Sprint 01–04 pools (~30 candidates with reasons) |

Initial generator KPI: reduce active human hypothesis-discovery effort by
about 70–80% without lowering research quality (duplicate rate, rescue
rate, feasibility accuracy, reviewer acceptance). The generator is not
built in this unit.

## Outcome boundary

```
SCIENTIFIC_OUTCOMES_COMPUTED = false
D12_EXECUTED = false
D13_EXECUTED = false
D14_EXECUTED = NOT_SELECTED
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
D7_CONFIRMATION_EXECUTED = false
D11_CONFIRMATION_EXECUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```
