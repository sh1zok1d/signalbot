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

## Saturated region

`LOW_PRIORITY / SATURATED_FOR_NOW`:

> ONE standalone observable X, measured at a single instant at a daily
> decision cutoff, entered as an **additive linear** term alongside BTC's
> own directional and volatility controls, evaluated by incremental
> reduction in **mean** 24h direction-aligned adverse-path excursion (MAE)
> on a ~1000-row daily holdout, under a ≥2% relative-improvement gate.

Closed cells:

| information source | target | form | verdict |
|---|---|---|---|
| derivative positioning (OI expansion) | 24h adverse-path / continuation | additive linear, mean MAE | MARKET-01 null |
| cross-asset (ETH confirmation) | 24h direction-aligned adverse path | additive linear, mean MAE | MARKET-05 null¹ |
| cross-venue (perp-vs-spot dislocation) | 24h direction-aligned adverse path | additive linear, mean MAE | MARKET-06 null |

¹ unverified on this branch.

**Why this is the right unit of saturation.** Three *materially different*
information sources failed at the *same* (function, target, horizon,
functional-form) cell. The repeated failure is evidence about the **cell**,
not about the information sources.

**Explicitly not disproven:** cross-venue information, cross-asset
information, open interest, funding, or microstructure *as concepts*. Each
was tested in one functional form, against one target, at one horizon, on
one instrument, under one evaluation functional. Nothing here licenses a
claim that those families are uninformative.

## Orthogonal candidate regions

Six regions, **deliberately unranked** — selected for search-space coverage
and information gain, not for expected profitability. Full fields are in
the JSON twin.

| id | region | function | information | horizon |
|---|---|---|---|---|
| R-A | structural regime/state detection | state detection | BTC path second-order structure | structural, days–weeks |
| R-B | conditional abstention / risk reduction | filtering | any existing observable | short, per decision |
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
