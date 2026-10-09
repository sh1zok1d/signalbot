# FORMATION_WIDTH_REGIME_V1 — pre-outcome amendment A1

**Status.** Incremental-comparator repair. Written while `outcome_read = false` and `future_association_read = false`. No future ACTIVITY, DISPLACEMENT, Spearman with Y, or partial Spearman with Y was computed. This file does not replace the original design and does not retune the object.

## Provenance

| | |
| --- | --- |
| Original design | `docs/research/FORMATION_WIDTH_REGIME_V1_DESIGN.md` |
| Original design commit | `c476e73ea67457242ce28f01b7523b8b01e1077c` |
| Original design SHA256 | `64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6` |
| Support census before A1 | `docs/research/FORMATION_WIDTH_REGIME_V1_FEASIBILITY.json`, read `2026-10-09T04:49:09Z` |
| Branch at the amendment | `cursor/formation-width-regime-v1-08d8` |
| Parent HEAD when A1 was opened | `13391c678db9cd5528466e76433bc29d0ca9c318` |
| `outcome_read` | false |
| What changed | the incremental covariate and the route name that depends on it |

The original design asked whether width adds information beyond `RV_PREV`, the realized variation of `[23:00, 00:00)`. At `T = 01:00` the realized variation of the formation hour itself is already known. A pass against `RV_PREV` alone can be the ordinary fact that a wide hour was also a volatile hour. A1 asks the narrower incremental question against that contemporaneous descriptor.

Foundation is unchanged: Spearman of `V = (high − low) / P0` with Y. `V` is not residualized before that question.

Unchanged with it: UTC `[00:00, 01:00)`, `T`, `P0`, the next 60m, `ACTIVITY`, `DISPLACEMENT`, `|rho| ≥ 0.10`, week blocks, `B = 2000`, seed `20261107`, the two-cell family percentiles 0.0125 and 0.9875, the information floor, and the surface.

## RV_FORMATION

`RV_FORMATION = sqrt(sum r_k^2)` on the twelve log returns of the formation hour. The return ending at bar `j` is `log(close_j / close_{j−1})`.

Bar `form` is the 00:00 bar. Formation returns end on bars `form` through `form+11`. Their close pairs are `(form−1, form)`, …, `(form+10, form+11)`. The last close is `P0` at 01:00. All twelve returns are known at `T`.

Future returns end on bars `form+12` through `form+23`. Their pairs are `(form+11, form+12)`, …, `(form+22, form+23)`.

The two sets of pairs are disjoint. The only shared price is `close[form+11] = P0`: the right endpoint of the last formation return and the left endpoint of the first future return. No squared return enters both sums.

`RV_PREV` pairs end on bars `form−12` through `form−1` and share only the boundary close `close[form−1]` with `RV_FORMATION`. That series is not the incremental covariate.

## Inferential families

`FOUNDATION`: `ACTIVITY`, `DISPLACEMENT`. Spearman(`V`, Y), null of no monotone association.

`INCREMENTAL_CURRENT_STATE`: the same two endpoints, partial Spearman given `RV_FORMATION`. Average ranks of `V`, Y, and `RV_FORMATION`. Residualize the first two on the third by OLS with an intercept. The coefficient is the Pearson correlation of the residuals. One covariate.

Within each two-cell family the interval uses percentiles 0.0125 and 0.9875. The families stay nested. There is no further correction across them.

One bootstrap stream, seed `20261107`. Inside each week-block draw the order is foundation `ACTIVITY`, foundation `DISPLACEMENT`, incremental `ACTIVITY`, incremental `DISPLACEMENT`. Ranks are recomputed inside the draw.

A cell clears only if the absolute estimate is at least 0.10 and its family interval excludes 0.

## RV_PREV

`RV_PREV` is `DESCRIPTIVE / SECONDARY BASELINE CONTEXT`. It is not an inferential cell. A later read may print Spearman(`V`, `RV_PREV`) and the partial Spearman given `RV_PREV`. Those numbers cannot change a route. There is no joint regression of `RV_FORMATION` and `RV_PREV`.

## Routes

1. `INFORMATION_LIMITED` when the support floor fails.
2. `FORMATION_WIDTH_NO_DETECTABLE_FUTURE_STRUCTURE` when no foundation cell clears.
3. `TEMPORALLY_UNSTABLE_WIDTH_RELATION` when every clearing foundation endpoint is year-unstable. The year rule is unchanged: a year counts at analysis `N ≥ 100`, and opposite signs make the endpoint unstable.
4. `WIDTH_IS_REDUNDANT_WITH_CONTEMPORANEOUS_VOLATILITY` when every year-stable clearing foundation endpoint fails its `RV_FORMATION` incremental cell. This replaces `WIDTH_IS_REDUNDANT_WITH_PAST_VOLATILITY`.
5. `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` when at least one endpoint clears foundation, is year-stable, clears its `RV_FORMATION` incremental cell, and the specificity flag below is true.

`RV_PREV` does not enter this list.

## Lag placebo

The comparison of today's `V` with the previous analysis day's future observable is `LAG_PLACEBO_CURRENT_STATE_SPECIFICITY`. It is a specificity diagnostic. It does not refute a relation.

The flag `interpretable_as_current_state` is false when, for any endpoint, the absolute lag-placebo point is at least the absolute contemporaneous foundation point. `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` is then withheld. The recorded label is `CURRENT_STATE_SPECIFICITY_NOT_SATISFIED`. That label does not say the association is absent and does not say width is redundant with volatility.

## Support

The analysis sample stays the original sample intersected with a complete `RV_FORMATION` close span: thirteen finite positive closes from `close[form−1]` through `close[form+11]`.

A1 support, path presence only: `docs/research/FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1_SUPPORT.json`.

- `RV_FORMATION` complete: 1820
- overlap with the original analysis sample: 1820
- analysis days missing `RV_FORMATION`: 0
- A1 analysis sample: 1820
- ISO weeks: 262
- `sample_n_changed = false`

The original floor still passes. The gate does not authorize Y.

## Later go

One outcome read of this amended map, on this surface, in this code. Foundation Spearman and partial Spearman given `RV_FORMATION` only. The evaluator refuses until that go.
