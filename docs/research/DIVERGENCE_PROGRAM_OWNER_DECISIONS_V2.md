# Divergence program — owner decisions V2

**Date:** 2026-10-02
**Decided by:** owner, after `DIVERGENCE_PANEL_FEASIBILITY_V0`
**Supersedes:** nothing in V1; it adds a new research design. `DIVERGENCE_PROGRAM_OWNER_DECISIONS_V1.md` stays in force.
**Frozen design:** `DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_DESIGN.json`

```
PROTECTED_2025_PLUS_OPENED                      = false (do not open yet)
DIVERGENCE_PANEL_FEASIBILITY_V0                 = INFORMATIONALLY_WEAK (unchanged; not reinterpreted or rescued)
DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1   = AUTHORIZED (outcome-blind)
PRIMARY_ESTIMAND                                = A - B   (conditional incremental value of divergence inside support)
SECONDARY_ESTIMAND                              = (A - B) - (C - D)   (mechanistic interaction)
MINIMUM_EFFECT_OF_INTEREST                      = 0.15 (not reduced)
E1_PROTECTION                                   = absolute
D2_RESERVATION                                  = released (as in V1)
SEED0003                                        = not created; only if V1 establishes a credible confirmatory design for A - B at 15 pp
```

## The new question

"Conditional on an already-present support state, does regular bullish divergence add practically meaningful trading value?"

- **A** = support + regular bullish divergence.
- **B** = support only.
- **Not an interaction effect.** A − B is never described as one. The interaction `(A − B) − (C − D)` stays available as a secondary mechanistic estimand.

## Why this redesign is allowed

- Protected 2025+ outcomes remain unopened.
- V0 was an outcome-blind feasibility calculation.
- This is a new research design, not a reinterpretation of the V0 verdict.
- 2023–2024 is the discovery surface, already spent, and is treated as such.

## What V1 must evaluate before any protected opening

1. **Power and MDE for A − B** under STRESS, BASE, INDEPENDENT and COLLAPSED, on both V0 proxy windows.
2. **Projected counts:**
   - A and B episodes;
   - A decision dates;
   - A week clusters;
   - symbol and epoch concentration.
3. **The historical window alone.** Whether `2025-01-01 .. 2026-08-11` alone meets the 15 pp standard under STRESS.
4. **A combined design, if not.** If the window alone fails, a pre-specified combined design: the window plus a prospective panel stream from 2026-10-05.
   - **Stopping rule:** fixed, from pre-outcome information only (A episodes, week clusters, a maximum date). It is never chosen after outcomes.
   - **Required continuation:** the report estimates how much prospective information A − B needs.

## Limits

- **Continuous strength models** may be evaluated only as secondary concepts. They are never promoted to primary for better simulated power.
- **No panel expansion** merely to inflate nominal N. An expansion needs:
  - a fixed eligibility rule;
  - PIT availability;
  - liquidity and history;
  - explicit dependence analysis;
  - a separate information-gain comparison.

## Design note added at freeze (for the owner)

**The overlap.** The SEED-0001 prospective leg covers BTC decisions from 2026-10-05 and has P1 = A vs B. That is almost the same contrast, on the same BTC episodes, as a prospective A − B leg of SEED-0003.

**What V1 does.** It sizes the combined design twice: once with all six symbols, and once with BTC excluded from the prospective part.

**Decision needed before SEED-0003 is frozen.** Either:
- retire the SEED-0001 prospective leg in favour of SEED-0003; or
- keep the legs disjoint.
