# OPENING_RANGE_OBJECT_V1 — pre-outcome amendment A2

**Status.** Interpretation only. Written while `outcome_read = false` and `y_known = false`. No resolution label was computed. A2 does not change the object, the four clock cells, the 60-minute formation, the pseudo construction, the touch rule, the touch-time handling, the 4h horizon, the `0.5 W` barrier, the practical scales, the support census, or the map rows.

## Provenance

| | |
| --- | --- |
| Original design | commit `3be350eb0f71011928b1c99cc92f37059d631252`, SHA256 `7e46d9f5081a4b1c6e3246ff7e2172e96a0c14eba900eefd84731147630250c8` |
| Amendment A1 | commit `fb57fc8df8960e336b6dd779a339ec390b74e76b`, file SHA256 `230b8818f154ad3b26450e25baab0fe368360c723c6ccabc86005cab6903803a` |
| What A1 already fixed | clock cells, direct contrasts, touch-time rule, bounded map, routes |
| What A2 changes | which interval or p-value a route may treat as a candidate |
| `outcome_read` | false |
| `y_known` | false |

The original design and A1 are not rewritten. Where A1 says a marginal interval that excludes 0 is enough for a route, A2 replaces that sentence.

## Three families

Point estimates are printed for every row. Marginal 95% percentile intervals are printed. A route uses the family rule below, not the marginal interval.

**`FOUNDATION_CELL_EFFECTS`.** The four foundation means `δ_00`, `δ_08`, `δ_12`, `δ_16`. Procedure: `STUDENTIZED_MAX_T`, single-step, at `α = 0.05`, from the one joint week-block bootstrap already frozen in A1 (seed `20261027`). A cell passes only when the absolute point is at least 0.03 and this simultaneous interval excludes 0. A diagnostic cell that passes is still not adopted as the object.

**`CLOCK_SPECIFICITY`.** The three contrasts `δ_00 − δ_08`, `δ_00 − δ_12`, `δ_00 − δ_16`. Procedure: its own `STUDENTIZED_MAX_T`, from the same joint draws, with its own critical value. The three contrasts are not stacked into the cell-effect max, and they are not three separate 95% intervals. A contrast separates the hours only when the absolute point is at least 0.03 and the simultaneous interval excludes 0. Day-boundary, funding-cadence, and generic routes read these simultaneous flags.

**`NONFOUNDATION_MAP`.** `DIRECTION_EXTENSION_FIRST`, `OUTSIDE_OCCUPANCY`, `OUTWARD_EXCURSION`, in that declaration order. Procedure: `HOLM` step-down on the three two-sided recentered bootstrap p-values, `α = 0.05`, plus the row's own practical scale (0.03, 0.03, and 0.25 W). Those p-values come from the three marginal streams A1 already assigned (`20261028`, `20261029`, `20261030`). No new seed. A row is listed only when its Holm-adjusted p-value is strictly below 0.05 and its absolute point meets its scale.

Max-T is used for the two clock families because those statistics are already one joint draw, and the contrasts share `δ_00`. Holm is used for the map because the rows have different scales and A1 gave them separate bootstrap streams. One correction across all ten statistics is not used: it would make clock specificity and the map share a penalty.

## Roles and the route name

`DIRECTION_EXTENSION_FIRST` stays in the map family so it cannot be selected on a marginal interval. Its role is `BARRIER_FAMILY_DECOMPOSITION`: same barriers as the foundation, not an independent observable.

`OUTSIDE_OCCUPANCY` and `OUTWARD_EXCURSION` have role `INDEPENDENT_OBSERVABLE`.

The route that A1 called `ORTHOGONAL_CANDIDATE_ON_UTC_00` is `NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00`. The result lists every row that cleared, in declaration order, with its role. Rows are not ranked.

`opening_wording_allowed` stays false. No hour is adopted. The other A1 routes keep their names. Their pass and separation flags now use the simultaneous intervals.

A null route requires the primary and the diagnostic cells to fail their simultaneous rules and all three map rows to be present and to fail Holm. A missing map row is not a null.

## Evaluator

`python -m scripts.research.opening_range_object_v1.evaluate` still raises `REFUSING_OUTCOME_BEFORE_OWNER_GO`. A2 adds no market read. Tests use synthetic draws.

## What a later owner go may run

The same one outcome read named in A1. Report every point estimate and every marginal interval. Set routes from the family rules in this amendment. Then stop.
