# MARKET program update after MARKET-06

Date: 2026-09-21
Unit: `MARKET_PROGRAM_UPDATE_POST_M06`

## MARKET-06 sealed

```
FINAL_CLASSIFICATION  = MARKET_06_NO_EVIDENCE
RESULT_COMMIT         = 80c7d19f622cc7b5576154de59dbb9cdf85d4dcf
RESULT_PAYLOAD_SHA256 = 67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53
```

**Scientific conclusion.** Absolute BTC perpetual-vs-spot cross-venue
dislocation, conditional on BTC's own recent directional and volatility
state, did not provide stable incremental information about subsequent 24h
direction-aligned adverse-path risk under the frozen MARKET-06 design.

| gate | value |
|---|---|
| G1 | true |
| G2 | false |
| G3 | false |
| G4 | false |
| G5 | false |
| G6 | false |

```
pooled relative MAE improvement = -0.03756596483364705
CI95                            = [-0.0644801374915513, -0.014898013948610516]
2023                            = -0.02814838672162434
2024                            = -0.045320425619876925
```

**No reverse effect is inferred.** The negative improvement is a null for
the preregistered direction. The frozen design was neither specified nor
powered to test a contrarian reading, and per program governance a negative
relative MAE must not be reinterpreted as a reverse effect.

## Evidence map

Verifiable on this branch:

- `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION` — `NO_EVIDENCE` (sealed)
- `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK` — `NO_EVIDENCE` (sealed, this unit)

Carried from program-level instructions, **not** independently verified
against artifacts on this branch: MARKET-02 `NO_EVIDENCE`; MARKET-03
`EXTERNAL_REPRODUCTION / REPRODUCED_DIRECTION`; MARKET-04 `SELECTED /
NOT_TESTED / BLOCKED_OBSERVABLE` (not rejected); MARKET-05 `NO_EVIDENCE`.

```
INTERNAL_HISTORICAL_CANDIDATES_PROMOTED = 0
PROTECTED_2025_2026_OPENED              = false
```

## Correction (v1.1.0)

Version 1.0.0 of this document claimed that *"three materially different
information sources … produced nulls at the **same** (function, target,
horizon, functional-form) cell"*, counting MARKET-01 in that cell. **That
was an overstatement and is retracted.**

Checked against MARKET-01's frozen preregistration on this branch, its
primary claim is materially different from MARKET-05/MARKET-06:

| | MARKET-01 | MARKET-05 / MARKET-06 |
|---|---|---|
| outcome | `reversal_return = -D · ln(close(T+60m)/close(T))` | 24h direction-aligned adverse-path MAE |
| horizon | 60 minutes (alternatives forbidden) | 24 hours |
| design | event/episode, 30m impulse + 30m state + 60m outcome, 120m span, overlap policy | daily decision grid |
| estimand | stratified two-group OLS candidate-group effect, explicitly `not_nested_ols_on_regular_bar_grid` | additive incremental regressor |
| resampling | Politis–Romano stationary bootstrap over episodes | 14-day circular MBB |

MARKET-01 is therefore **removed** from the exact cell. The saturation
claim is restated at two levels.

## Saturated region — two levels

### Level 1 — the exact/near-exact narrow cell

> one external/cross-market observable → additive incremental term
> alongside BTC own-state controls → 24h direction-aligned adverse-path
> prediction → evaluated by holdout MAE improvement

Evidence carried for this cell:

- `MARKET-05` = `NO_EVIDENCE` (cross-asset ETH confirmation) — *unverified on this branch*
- `MARKET-06` = `NO_EVIDENCE` (cross-venue perp-vs-spot dislocation) — verified, sealed

`MARKET-01` does **not** belong to this cell.

```
EXACT_CELL_STATUS = REPEATED_NULL / LOW_PRIORITY_FOR_NOW
```

Honest limit: two nulls, one of them unverified here. That supports
deprioritisation — not a claim that the cell is exhausted or globally
disproven.

### Level 2 — the broader family

> short-horizon BTC conditional relationship studies in which a relatively
> narrow observable or state is expected to provide incremental predictive
> information about a scalar future return/path/risk outcome

Members with recorded failures: MARKET-01 (verified), MARKET-02
(unverified here), MARKET-05 (unverified here), MARKET-06 (verified), plus
relevant earlier H/B2 families in program history.

These studies differ in target, horizon, design, estimand and resampling,
so the conclusion is **not** "the same cell repeatedly failed".

```
BROADER_FAMILY_STATUS = LOW_PRIORITY / SATURATED_FOR_NOW
```

Reason: many nearby formulations, across different observables and several
short-horizon scalar targets, have repeatedly failed to produce robust
incremental evidence. This is a **program-level search-priority
conclusion**, not a claim that every member of the family is false, and
not a statistical result about the family.

### Explicitly NOT disproven

Open interest as an information source; cross-asset information;
cross-venue information; funding/premium information; microstructure;
filtering mechanisms; execution mechanisms; structural regime/state
mechanisms; cross-sectional mechanisms.

Each was tested in a small number of functional forms against a small
number of targets. No reverse effect is inferred from MARKET-06.

## Orthogonal candidate regions

Six regions, **deliberately unranked** — selected for search-space coverage
and information gain, not for expected profitability. Full fields are in
the JSON twin.

| id | region | function | information | horizon |
|---|---|---|---|---|
| R-A | structural regime/state detection | state detection | BTC path second-order structure | structural, days–weeks |
| R-B | conditional abstention / tail selection | filtering | observables null as mean/scalar predictors | short, per decision |
| R-C | cross-sectional relative structure | relative ranking | multi-instrument panel | short–medium |
| R-D | liquidity & market-structure state | state detection / conditioning | order book, trades | intraday |
| R-E | execution-cost mechanism | execution | spread, depth, intensity | per fill |
| R-F | composed joint state (non-additive) | prediction under composition | several null observables jointly | short |

Axis coverage: prediction (R-F) vs filtering (R-B) vs risk reduction (R-B)
vs state detection (R-A, R-D) vs execution (R-E); absolute (R-A, R-B, R-F)
vs relative/cross-sectional (R-C); price/path (R-A, R-F) vs
liquidity/structure (R-D, R-E); short-horizon (R-B, R-F) vs structural
(R-A, R-C); standalone (R-D, R-E) vs composed (R-F); entry signal (R-F) vs
position management (R-B).

Two honest notes:

- **R-D and R-E are acquisition-blocked for history.** Their near-term
  value is deciding whether forward collection is worth committing to,
  which connects directly to `FORWARD_MARKET_OBSERVABILITY_V1`.
- **R-F carries the highest rescue risk in the set.** It is listed for
  coverage completeness only, and must never be used to re-interrogate the
  MARKET-06 target on the consumed window.

## Binding constraints on whatever is selected next

- The 2022–2024 OKX/Binance 5m window is now **consumed** for the 24h
  direction-aligned MAE target; it must not be silently reused for a
  variant of that target.
- Protected 2025/2026 remain unopened and need separate explicit
  authorization.
- No parameter variant, sign flip, venue swap, horizon tweak, or threshold
  change of MARKET-01…MARKET-06.

MARKET-07 is **not** created and no hypothesis is selected.

Next unit: `MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`.
