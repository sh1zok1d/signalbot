# FORMATION_WIDTH_REGIME_V1 — pre-outcome amendment A2

**Status.** Routing repair only. Written while `outcome_read = false` and `future_association_read = false`. No future observable was read. This file does not replace the original design or amendment A1.

## Provenance

| | |
| --- | --- |
| Original design | `docs/research/FORMATION_WIDTH_REGIME_V1_DESIGN.md` |
| Original design SHA256 | `64407200533eec23abe63391f546ba83c3fae69c30d4a4f83a6d468300985ae6` |
| Amendment A1 | `docs/research/FORMATION_WIDTH_REGIME_V1_AMENDMENT_A1.md` |
| Amendment A1 SHA256 | `a2e00c68e4360fe08db89ade31e4f222dc148ace0aea58e9143a27d4d386d49e` |
| Parent HEAD when A2 was opened | `666f2b9e4aa9f6b20cd085cdf3a6ba05d7de84fa` |
| `outcome_read` | false |
| `future_association_read` | false |

A1 set `interpretable_as_current_state` from both endpoints at once. A foundation failure on one endpoint, with a large lag placebo, could withhold a state reading that the other endpoint had earned on its own chain. A null endpoint is not a veto.

## What did not change

`V`, `ACTIVITY`, `DISPLACEMENT`, `RV_FORMATION`, the `RV_PREV` role, partial Spearman, foundation, the week-block bootstrap, family percentiles, `|rho| ≥ 0.10`, the year rule, the surface, the sample, the horizon, the seed, and the lag-placebo formula. Analysis N stays 1820. ISO weeks stay 262. No new census.

## Specificity

For each endpoint, on its own numbers:

`current_state_specific = |lag_placebo| < |foundation|`

The later result prints, for each endpoint and in the frozen order `ACTIVITY` then `DISPLACEMENT`: foundation rho, foundation clear, year stable or unstable, incremental rho, incremental clear, lag-placebo rho, and `current_state_specific`. The list is not sorted by effect size.

## Route

The route function is `amendment_a2.assign_route`. Hierarchy:

1. `INFORMATION_LIMITED` when the support floor fails.
2. `FORMATION_WIDTH_NO_DETECTABLE_FUTURE_STRUCTURE` when no foundation endpoint clears.
3. `TEMPORALLY_UNSTABLE_WIDTH_RELATION` when every foundation-clearing endpoint is year-unstable.
4. `WIDTH_IS_REDUNDANT_WITH_CONTEMPORANEOUS_VOLATILITY` when every foundation-clearing year-stable endpoint fails its `RV_FORMATION` incremental cell.
5. `FORMATION_WIDTH_REGIME_STRUCTURE_PRESENT` when at least one endpoint clears foundation, is year-stable, clears incremental, and is `current_state_specific`. The names are `route_supporting_endpoints`.
6. `CURRENT_STATE_SPECIFICITY_NOT_SATISFIED` when at least one endpoint clears foundation, is year-stable, and clears incremental, and none of those endpoints is `current_state_specific`. The names are `incremental_qualified_but_not_specific_endpoints`.

`RV_PREV` does not enter the route. The outcome evaluator still returns `REFUSING_OUTCOME_BEFORE_OWNER_GO`.
