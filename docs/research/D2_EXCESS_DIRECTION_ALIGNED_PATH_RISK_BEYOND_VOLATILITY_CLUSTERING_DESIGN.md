# D2 excess direction-aligned path-risk beyond volatility clustering

**Unit:** `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`  
**Kind:** post-replication mechanism-decomposition **design**.  
**DESIGN_STATUS:** `FROZEN`

This unit does not execute the new scientific target. It does not open
Binance 2025/2026. It does not reuse BitMEX 2017-2019 as independent
confirmation. It does not change the D2 selector.

Evidence class for any later result on exposed Binance 2020-2024:

```
POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY
```

Not `INDEPENDENT_CONFIRMATION`, `EXACT_CONFIRMATION`, or
`VALIDATED_MECHANISM`.

## Scientific question

The frozen D2 / RULE_1 / `RV_ABSTENTION` replication showed that high
trailing RV days have larger subsequent direction-aligned arithmetic MAE
than year-matched random abstention.

That estimand does not distinguish:

- **A.** a genuinely direction-specific adverse-path orientation;
- **B.** ordinary volatility clustering: high current vol → high future
  vol → larger excursions mechanically in both directions.

This design asks **A vs B** by changing the **target**, not the selector.

## Selector (unchanged)

```
PRIMARY_SELECTOR = D2_RULE_1_RV_ABSTENTION
ABSTAIN(t) = 1 iff RV_BTC_24H(t) > P90(previous 250 valid constructed-row RV)
t excluded. Strict >.
```

Same decision clock, `BTC_RET_24H`, `BTC_SIDE`, 5m open at `T`, 288×5m
future path, valid-row semantics, P90, trailing-250. No P85/P95, no
alternate RV, no alternate horizon, no alternate entry.

Future execution must reconstruct the frozen discovery RULE_1 population
(`N=1791`, years `334/364/364/364/365`, interval
`2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive`) and the exact
`rv_abstention_mask`. If that identity cannot be reconstructed, the later
run is `D2_DECOMPOSITION_INVALID`.

## Primary target

On the **same** 24h future path:

```
SIDE          = sign(BTC_RET_24H)
MAE_SIDE      = arithmetic_mae(SIDE, entry, future_288)
MAE_OPPOSITE  = arithmetic_mae(-SIDE, entry, SAME future_288)
PATH_SCALE    = MAE_SIDE + MAE_OPPOSITE
ADVERSE_SHARE = MAE_SIDE / PATH_SCALE
```

```
PRIMARY_TARGET = ADVERSE_SHARE
```

`PATH_ASYMMETRY = 2 * ADVERSE_SHARE - 1` may be stored. It is not primary.

`ADVERSE_SHARE = 0.5` is approximately symmetric adverse/favorable
opportunity. `ADVERSE_SHARE > 0.5` means more of the observed two-sided
excursion envelope is allocated against the frozen D2 side.

Future execution must re-walk the **same** 288 5m `PerpBar` high/low path
used by frozen `arithmetic_mae`. `DiscoveryRow.future_closes` is not a
substitute for those extrema.

### Primary quantities (future execution)

```
MU_SHARE_RULE       = mean ADVERSE_SHARE on D2-abstained target-eligible rows
CONTROL_SHARE_MEANS = 10000 year-matched random-control means
MU_SHARE_CONTROL    = mean(CONTROL_SHARE_MEANS)
DELTA_SHARE         = MU_SHARE_RULE - MU_SHARE_CONTROL
CONTROL_SHARE_P95   = P95(CONTROL_SHARE_MEANS)
MC_P_SHARE          = (1 + count(CONTROL_SHARE_MEAN >= MU_SHARE_RULE)) / 10001
```

Diagnostic only: `MU_PATH_SCALE_RULE`, `MU_PATH_SCALE_CONTROL`,
`DELTA_PATH_SCALE`.

### Why this is not the original MAE target

`MAE_SIDE` is a one-sided amplitude. If the whole future path scales up,
adverse extrema grow, so `MAE_SIDE` can rise even when orientation is
unchanged. That is the volatility-clustering tautology.

`ADVERSE_SHARE` divides that amplitude by the same path's two-sided
envelope. Uniform amplitude inflation cancels. The question becomes
whether the candidate path is **disproportionately adverse** relative to
its own opposite-side excursion.

This is descriptive decomposition, not causal identification.

### Target-specific ineligibility

If `PATH_SCALE <= 0` or nonfinite:

```
TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE
```

No epsilon stabilization. This does **not** change the D2 selector. It
only restricts the new target population. Any count, and any resulting
change in support, must be reported.

## Anti-tautology limitations

- extreme one-sided paths can dominate share;
- path extrema ignore ordering;
- `SIDE` still depends on the previous 24h return;
- high RV may proxy for other states;
- future realized volatility is **not** a primary matching variable.

## Secondary scale diagnostic

`PATH_SCALE` answers whether D2 high-RV rows simply have larger total
future two-sided excursion. It is **not** the primary gate and cannot
rescue ADVERSE_SHARE statistical, practical, or temporal failure.

Frozen diagnostic elevation (for classification B vs C only):

```
MU_PATH_SCALE_RULE > CONTROL_PATH_SCALE_P95
AND
DELTA_PATH_SCALE >= 0.20 * MU_PATH_SCALE_CONTROL
```

PATH_SCALE elevated + ADVERSE_SHARE not elevated is compatible with
volatility-scale persistence. It does not uniquely prove clustering.

## Comparator

```
YEAR_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION
N_RANDOM_CONTROLS = 10000
RANDOM_SEED = 20260922131
```

Generator: `numpy.random.Generator(numpy.random.PCG64(20260922131))`.
Selected now, before outcomes. Not the D2 discovery seed (`20260921102`)
and not the BitMEX replication seed (`20260921125`).

For candidate count `K_y` in each of 2020–2024, each replicate draws
exactly `K_y` target-eligible rows from that year without replacement.
No pooled K. The same masks are used for PATH_SCALE diagnostics.

`K_y` is the D2-abstain count **inside the path-scale-eligible target
population**. Selector mask construction itself remains unchanged.

## Gates (frozen before outcome)

```
STATISTICAL_GATE = MU_SHARE_RULE > CONTROL_SHARE_P95
PRACTICAL_GATE   = DELTA_SHARE >= 0.05
TEMPORAL_GATE    = DELTA_SHARE > 0 in at least 3 of 5 years 2020-2024
```

`0.05` is five percentage points of the two-sided envelope toward the
adverse side versus rate-matched random dates. Do not replace after seeing
results. Temporal robustness is discovery-only; it does not make exposed
Binance independent evidence.

## Classification vocabulary

| Class | Rule |
|---|---|
| `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PROMISING` | statistical and practical and temporal |
| `D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT` | primary gates fail and PATH_SCALE materially elevated |
| `D2_DECOMPOSITION_NO_USEFUL_STRUCTURE` | primary gates fail and PATH_SCALE not materially elevated |
| `D2_DECOMPOSITION_INVALID` | identity / sample / target construction fails |

No subgroup rescue. Strong ADVERSE_SHARE cannot be strengthened by a
favorable PATH_SCALE slice.

## Surfaces

- Allowed later: reconstructed CORE BTC Binance 2020-2024 RULE_1 rows
  (`ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`).
- Forbidden now and later as independent confirmation of this new target:
  BitMEX 2017-2019.
- Sealed: Binance 2025/2026.

```
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
EXECUTION_AUTHORIZED = false
```

## Future execution route

Do not execute from this unit.

```
NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW
```
