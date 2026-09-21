# Discovery Sprint 01 — Final Mechanical Pre-Execution Fix

**Unit:** `DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX`
**Unit type:** `OUTCOME_BLIND_MECHANICAL_PRE_EXECUTION_FIX`
**Date:** 2026-09-21
**Reviewed commit:** `475072d22f4c4631836ca7d38ccdc5da6ce59222`
**Scope:** D3 close-path redefinition, D4 practical-threshold exactness,
D5 common-window component comparison **only**. D1 and D6 unchanged.
**Machine-readable record:** `docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.json`

No Discovery Sprint 01 card was executed. No scientific/candidate
performance was inspected. Protected 2025/2026 remains unopened. No
MARKET-07 was created.

## D3 — real/null observable mismatch

The real D3 functionals used 5m bar HIGH/LOW values, but the frozen
surrogate (`5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP`) only ever
generates a synthetic close-to-close log-return path — it never
synthesizes intra-bar high/low. Real and surrogate were therefore not
the same observable, despite sharing functional names. No synthetic
high/low is invented. Instead, D3 is redefined so real and surrogate
paths are mechanically identical objects: a sequence of 288 5m close
prices.

**Corrected functionals (exactly three):**

1. `MAX_UPSIDE_CLOSE_24H = max(0, max_k((close_k - entry_open) / entry_open))`
2. `MAX_DOWNSIDE_CLOSE_24H = max(0, max_k((entry_open - close_k) / entry_open))`
3. `TIME_TO_MAX_ABS_CLOSE_EXCURSION` = earliest 5m bar offset attaining
   `max(MAX_UPSIDE_CLOSE_24H, MAX_DOWNSIDE_CLOSE_24H)`

`close_k` is used identically for the real path (real
`future_bar_k.close`) and the surrogate path (the cumulative-return-
compounded close series the null already produces). No high/low field is
read or synthesized by D3 in either case.

**`PATH_ASYMMETRY` is removed from Sprint 01**, because: the original D3
card allowed at most 2-3 functionals; the prior correction round
accidentally expanded the surface to 4 by adding it; and it is
derivative of the two excursion functionals anyway.

Floors: `MAX_UPSIDE_CLOSE_24H >= 0`, `MAX_DOWNSIDE_CLOSE_24H >= 0`.
Ties: earliest bar offset wins. Entry reference: `entry_open =
ev.get_perp_bar_opening_at(perp, t_ms).open` — unchanged. The
time-of-day-stratified bootstrap null itself is kept unchanged (block
length 12, 1000 replicates, seed `D3_NULL_SURROGATE_SEED = 20260921103`,
companion checks at block lengths 6/24, all slot-stratified) — it
already generates exactly the observable D3 now needs.

**D3 status: `EXECUTABLE_DISCOVERY_SPEC`.**

## D4 — make the practical gate exact

`ROLLING_CORRELATION_90D`'s practical magnitude threshold ("swings by at
least 0.15 correlation-points beyond null-implied noise") was not
mathematically pinned. Corrected:

```
OBSERVED_CORRELATION_RANGE = max(real rolling_corr_90d) - min(real rolling_corr_90d)
NULL_RANGE_MEDIAN          = median over the 1000 bootstrap replicates of
                              [max(null rolling_corr_90d) - min(null rolling_corr_90d)]
PRACTICAL_EXCESS_RANGE     = OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN

practical gate: PRACTICAL_EXCESS_RANGE >= 0.15
```

The existing statistical variance-vs-null gate is **kept unchanged**,
alongside this now-exact practical gate — neither replaces the other.
`LEAD_LAG_1DAY` remains `DEFERRED_FROM_SPRINT_01`.

**D4 status: `EXECUTABLE_DISCOVERY_SPEC`, scoped to
`ROLLING_CORRELATION_90D` only.**

## D5 — common-window component comparison

D5's own execution interval is correctly restricted to
`2022-02-01T00:05:00Z → 2025-01-01T00:00:00Z` (bound by component_B/
RULE_2's cross-venue data availability). D2 RULE_1 (component_A),
however, reports its `DELTA` over its own full `2020-02-01 →
2025-01-01` interval. Comparing D5's `DELTA` against RULE_1's
full-interval result would not be apples-to-apples — different N,
different sub-periods and regimes.

**Corrected comparison:**

- `COMPONENT_A_DELTA_FOR_D5` = D2 RULE_1 evaluated on the exact D5 common
  interval (`2022-02-01T00:05:00Z → 2025-01-01T00:00:00Z`), **not**
  RULE_1's own broader 2020-2024 reported result. This requires RULE_1
  to be evaluated a second time, restricted to this narrower window,
  solely as a comparison input.
- `COMPONENT_B_DELTA_FOR_D5` = D2 RULE_2 evaluated on the same common
  interval — this already coincides with RULE_2's own native interval,
  so no additional computation is needed beyond RULE_2's own D2 result.
- `COMPOSED_BEATS_COMPONENTS` iff `D5_DELTA > max(COMPONENT_A_DELTA_FOR_D5,
  COMPONENT_B_DELTA_FOR_D5)`.

D2 RULE_1's own broader 2020-2024 discovery result is **not** replaced —
it may still be separately reported under D2's own card. The
narrower-window evaluation exists solely as a D5-scoped comparison
input. This overlap-window comparison is a pre-declared requirement
specific to D5, frozen now, outcome-blind, and must not be selected or
adjusted after observing any card's outcome.

**D5 status: `EXECUTABLE_DISCOVERY_SPEC`.**

## Final report

```
D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX (unchanged)
D2_STATUS = EXECUTABLE_DISCOVERY_SPEC (unchanged)
D3_STATUS = EXECUTABLE_DISCOVERY_SPEC (close-path fix applied)
D4_STATUS = EXECUTABLE_DISCOVERY_SPEC / ROLLING_CORRELATION_90D only (practical gate now exact)
D5_STATUS = EXECUTABLE_DISCOVERY_SPEC (common-window comparison fix applied)
D6_STATUS = DEFERRED (unchanged)

EXECUTION_AUTHORIZED = D2, D3, D4_ROLLING, D5

SCIENTIFIC_OUTCOMES_COMPUTED   = false
CANDIDATE_PERFORMANCE_INSPECTED = false
PROTECTED_2025_OPENED          = false
PROTECTED_2026_OPENED          = false
MARKET_07_CREATED              = false

NEXT_UNIT = DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5
```
