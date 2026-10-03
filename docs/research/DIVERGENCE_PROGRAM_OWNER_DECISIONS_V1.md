# Divergence program — owner decisions V1

**Date:** 2026-10-02
**Decided by:** owner
**Context:** `DIVERGENCE_RESEARCH_MAP_V0.md`
**Feasibility design (frozen before counts):** `DIVERGENCE_PANEL_FEASIBILITY_V0_DESIGN.json`

```
DIVERGENCE_PANEL_FEASIBILITY_V0       = AUTHORIZED (2023-2024 only; outcome-blind)
HOLDOUT_SPEND_WINDOW                  = 2025-01-01 .. 2026-08-11 (CONDITIONAL on the feasibility gate)
E1_RUN_001_HOLDOUT                    = STRICTLY PROTECTED [2026-08-16T00:00Z, 2026-08-25T17:20Z)
D2_RESERVATION_ON_SPEND_SURFACE       = RELEASED (superseding decision; D2 history unchanged)
MINIMUM_EFFECT_OF_INTEREST            = 0.15
PRIMARY_ESTIMAND                      = (A - B) - (C - D); A - B retained as the key secondary
PROTECTED_2025_2026_OPENED            = false
SEED0003_PREREG_CREATED               = false
```

## 1. Panel feasibility authorized

`DIVERGENCE_PANEL_FEASIBILITY_V0` runs now.
- **Data it may use:** only the already-spent or discovery surface, 2023–2024, for BTC, ETH, SOL, XRP, BNB and DOGE. Downloading about 1.5 GB for SOL, XRP, BNB and DOGE is authorized.
- **What it must not do:** compute an outcome, or open or evaluate 2025–2026.

## 2. Conditional spend window

The future holdout spend window is decisions `2025-01-01 .. 2026-08-11`. It is approved only under the feasibility gate (section 4).
- **E1-RUN-001 stays strictly protected.** No input window, baseline, feature construction, outcome horizon or auxiliary calculation may touch `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`.
- **The window respects that.** The last decision plus 96h ends at 2026-08-15T00:00Z, and trailing baselines only look backward.

## 3. D2 reservation released (superseding)

**What is released.** D2's historical reservation on the divergence spend surface: 2025 (its `PRIMARY_CONFIRMATION_SURFACE`) and the safe pre-E1 part of 2026 (its `SECOND_RESERVED_SURFACE`).

**Why.** The frozen D2 confirmation design has negligible information yield on a one-year surface: `ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011` in `D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.md`.

**What stays:**
- D2's history is not rewritten. Its records keep their text and are superseded on this point only.
- D2 remains a valid historical research object.
- Any future D2 confirmation needs a new independent dataset or a prospective surface.

## 4. Design target and gate

**Effect sizes:**
- **Minimum effect of interest: 15 pp.** It must be practically testable before any protected spend.
- **10 pp** is reported as a diagnostic only.
- **20 pp** is the stress or easy case. Passing only at 20 pp is not sufficient authorization to open 2025–2026.

**Gate.** If the panel cannot reach the repository's normal preregistration power standard (0.80) for a 15 pp effect:
- feasibility stops;
- the report gives the required sample and history;
- the holdout is not spent.

## 5. Scientific target

**Primary estimand.** The interaction `(A − B) − (C − D)`:
- A = support + divergence;
- B = support only;
- C = divergence only;
- D = neither.

**Key secondary.** `A − B`, the directly interpretable question: "does divergence add value conditional on support?"

**Frozen relationship.** Primary and secondary are frozen now. SEED-0003 freezes them again before protected data are opened. They are never chosen after outcomes.

## 6. Panel dependence

Episodes on BTC, ETH, SOL, XRP, BNB and DOGE are not independent merely because they occur on different symbols. The feasibility must quantify:
- nominal episodes per symbol and arm;
- distinct decision timestamps and dates;
- within-symbol overlap;
- cross-symbol simultaneous and near-simultaneous episodes;
- common-market temporal clusters;
- the effective cluster count;
- concentration by symbol and by epoch;
- the dependence assumptions of the planned inference.

**Rule.** Power and MDE are computed under a dependence structure that accounts for common crypto-market episodes. A panel that appears feasible only when simultaneous cross-symbol signals count as independent fails.

## 7. What SEED-0003 must freeze before any 2025–2026 opening

1. symbol panel;
2. PIT detector;
3. support definition;
4. divergence definition;
5. all feature transformations;
6. arm assignment;
7. primary estimand;
8. primary outcome;
9. costs;
10. inference procedure;
11. clustering and dependence structure;
12. exclusion rules;
13. minimum effect of interest;
14. power rule;
15. missing-data policy;
16. the exact historical spend interval;
17. the protected E1 exclusion boundary.

No tuning after protected data are opened.

## 8. Order

Feasibility runs first, then the owner reviews it. SEED-0003 is not created, and 2025–2026 is not opened, until then.

## Policy note

`AGENTS.md` and `PROJECT_STATUS.md` still say protected 2025/2026 remain sealed. That stays true until an opening decision.
- **Why not now.** The spend is conditional.
- **What happens at opening.** The policy text and a new GV0R02 compiler policy version are updated in the same decision that opens the surface.
