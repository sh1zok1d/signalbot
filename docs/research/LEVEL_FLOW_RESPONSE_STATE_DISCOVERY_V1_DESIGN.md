# LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1

MODE = DISCOVERY

Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is the outcome-blind freeze. No resolution rate by state has been computed. The partition below was fit on the five predictors only.

## Question

Among first touches of pre-known structural levels, which joint configurations of positioning, aggressive flow and observed price progress exist in the predictor space, and do those frozen states differ in historical `RESOLVE_4H` or `BREAK_GIVEN_RESOLVED` frequency after the predeclared context adjustment?

The unit does not ask whether open interest works, whether taker flow works, or whether absorption exists.

## Novelty audit

Compared with the closed objects before any outcome of this unit:

| Object | Population | Predictors | Outcome |
|---|---|---|---|
| H05 | generic taker-imbalance cells on CORE | taker imbalance magnitude | subsequent return |
| B2-05 | generic UTC 15m grid | `IMPACT_INTERACTION = ABS_IMB * FLOW_RET`, with `FLOW_RET` oriented by `sign(IMB)` | subsequent flow-direction return |
| #355 | structural touches with an observed approach | price-path geometry, one feature at a time | 4h BREAK / REJECT / NEITHER |
| #358 | structural first touches | four univariate OI and taker slopes | RESOLVE_4H and BREAK given resolved |
| This unit | structural first touches only | unsupervised partition of five PIT observables, including open interest and approach-oriented price progress | RESOLVE_4H and BREAK given resolved |

This is not an exact or near-exact reopen of H05 or B2-05.

- The population is the replicated structural first touch, not the generic 15m grid.
- Open interest is a required dimension. H05 and B2-05 do not use it.
- `IMPACT_INTERACTION` is not computed. Price progress is not multiplied by flow and not divided by flow.
- Price progress is oriented by the structural approach side from #352, not by the sign of taker imbalance.
- The outcome is the level-event resolution label, not a subsequent return.
- States are formed before any label is read.
- Univariate slopes of X1–X4 are not re-estimated. X5 alone is not a candidate family. #358 is not rescued by a lower q, a lower 3 pp bar, a new window, a threshold, or a subgroup.

Atlas row for this unit is `PRICE_STRUCTURE.levels`, not `FLOW.absorption` and not `FLOW.taker_imbalance`. B2-05 remains `EXPOSED_ONLY` on `FLOW.absorption` and is not confirmed here. H05 remains `CLOSED_ON_SURFACE` on `FLOW.taker_imbalance`.

`BLOCKED_REOPENING_CLOSED_FLOW_ABSORPTION` is not returned.

## Data

`CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. Quote volume and taker-buy quote volume only. Sell quote is the arithmetic difference.

OI git snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`. `oi.jsonl` SHA256 `c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94`, 455273 native 5m rows. Field `sum_open_interest` only. `available_at = period_start + 5m`. Funding is not opened. The B2-06 contract is not edited.

No 2025/2026, no E1, no spot, no other venue, no long/short ratio, no premium, no mark, no liquidation, no order book.

## Cohort and decision time

First touch only of PDH, PDL, PWH, PWL, PMH, PML. Zone, merge, lifetime, side, barrier, BREAK, REJECT, NEITHER, AMBIGUOUS and the 4h horizon are the #352 definitions, imported and not rewritten.

`T` is the open time of the touch bar. The touch bar is outside every state feature.

Event window `[2020-09-01T01:05:00Z, 2025-01-01T00:00:00Z)`. The start is the first `T` whose 60-minute lookback can see a legal OI print. On the predictor-complete rows the observed first open is 2020-09-01T05:55:00Z and the last is 2024-12-31T12:30:00Z. The empty prefix is not trimmed.

Geometry-legitimate first touches: 1708. Predictor-complete training rows: 1688. The same 1688 rows also have the nuisance fields. Geometry pairs: 1082. Pseudo rows with a complete five-vector, assigned and not refit: 1074.

One window: `[T-60m, T)`. No other window is estimated.

## Observables

X1 `OI_CHANGE_60M` and X2 `OI_RECENT_ACCELERATION` are the #358 formulas on the 13 legal OI prints from `T-60m` through `T`.

X3 `ORIENTED_TAKER_IMBALANCE_60M` and X4 `TAKER_RECENT_SHIFT` are the #358 formulas on the 12 complete bars with opens in `[T-60m, T)`.

X5 `ORIENTED_PRICE_PROGRESS_60M` = `d × log(close of the bar that ends at T / open of the bar that opens at T-60m)`. This is the #358 oriented displacement, used here as a coordinate of the joint state. It is not a ratio and not a product.

`d = +1` for an approach from below and `d = -1` for an approach from above. Positive means toward the level. It is not a long or a short.

No score, weight, product or ratio is formed. Pairwise correlations on the 1688 training rows are all below 0.27 in absolute value. The largest is OI change with OI acceleration, 0.267. No coordinate is dropped.

## Scaler

Fit on the 1688 real predictor-complete rows only. Pseudo rows do not enter the fit.

`z = clip((x − median) / (IQR / 1.349), −5, +5)`. Quantiles use the linear method. A non-positive IQR would have stopped the unit before outcomes. None did.

| Feature | Median | IQR | Values clipped |
|---|---:|---:|---:|
| X1 | 0.0020868662257442234 | 0.008795439675531636 | 27 |
| X2 | 3.580546274503826e-05 | 0.0002965771483191495 | 40 |
| X3 | 0.07362699773930878 | 0.08472701743530485 | 0 |
| X4 | 0.06070963659772181 | 0.18855171931137985 | 1 |
| X5 | 0.005437476965416574 | 0.007019602601124523 | 35 |

Hex forms are in the preflight `scaler_hex`. Relative quote volume, used only as nuisance, has mean `1.4242216933351703` and population SD `0.9559973249877352` on the same 1688 rows.

## K selection

KMeans, Lloyd updates, k-means++ start, 16 deterministic inits, seed `20261014`, at most 50 iterations, centroid tolerance `1e-7`. The lowest inertia wins. An init that does not fill every cluster is discarded. Centroids are then sorted lexicographically on `(X1, X2, X3, X4, X5)`. Labels are `STATE_1` … `STATE_K` in that order.

A K is eligible only if every cluster has N ≥ 100 and share ≥ 5%, and the median adjusted Rand index over 40 predictor-only bootstrap refits is at least 0.75. Each refit assigns every original row to the bootstrap centroids. Among eligible K, the highest silhouette wins. An exact silhouette tie keeps the smaller K.

| K | Min N | Min share | Silhouette | Median ARI | Eligible |
|---:|---:|---:|---:|---:|---|
| 3 | 190 | 0.1126 | 0.2702544991913292 | 0.8916007955760614 | yes |
| 4 | 147 | 0.0871 | 0.1797465617320771 | 0.41596478300420775 | no, ARI |
| 5 | 122 | 0.0723 | 0.17144081986898774 | 0.7751013510680156 | yes, lower silhouette |
| 6 | 98 | 0.0581 | 0.18346546824622387 | 0.7501266950527968 | no, min N |

Selected K = 3. Silhouette hex `0x1.14bd986e7e959p-2`. ARI hex `0x1.c87fe6442c6c8p-1`.

Training-row digest `c59db814c27c0b5d649a60d41699e9464368b0dc46ca1a272b43891652ee31dc`.

## Frozen centroids

Robust-z coordinates, order X1…X5. Counts are the training partition.

`STATE_1`, N=190. Centroid `[-2.240742326531848, -1.4104058837398419, 0.5276229748892165, -0.25303720833452814, 2.1373696531922284]`.

Above-average OI contraction; OI change decelerating; aggressive flow toward the level; near-average flow shift; above-average price progress toward the level.

`STATE_2`, N=1178. Centroid `[-0.03620056391578825, -0.07678119594134862, -0.12661250649048075, 0.15097463877494116, -0.2318033215684267]`.

Near-average on all five coordinates. The word cut is 0.5 robust z and is not a further split.

`STATE_3`, N=320. Centroid `[1.8215581009084008, 1.4015725905122607, 0.28151845423694055, -0.31840367895676347, 1.4714599334888985]`.

Above-average OI expansion; OI change accelerating; near-average aggressive flow; near-average flow shift; above-average price progress toward the level.

These sentences describe coordinates. They are not absorption, buildup, a squeeze, or a participant identity.

Predictor-only median Jaccard of bootstrap membership: STATE_1 0.8441547927461139, STATE_2 0.9561837832267552, STATE_3 0.8799624945138251. A state below 0.50 fails the candidate membership clause. None is below 0.50 on this diagnostic. The diagnostic is not recomputed from outcomes.

## Pseudo assignment

The real scaler and the real centroids stay fixed. A pseudo first touch with a complete five-vector is transformed and assigned to the nearest real centroid. There is no refit on pseudo rows.

## Outcomes, after this commit only

O1 `RESOLVE_4H`: 1 for BREAK or REJECT, 0 for NEITHER. AMBIGUOUS is excluded.

O2 `BREAK_GIVEN_RESOLVED`: among BREAK and REJECT, 1 for BREAK and 0 for REJECT.

For each state and each outcome, the estimand is the adjusted difference `P(Y | STATE_k) − P(Y | not STATE_k)` from one linear probability model. The state enters as a 0/1 indicator, not as a standardized slope. Same support inside one outcome: every nuisance-complete, labeled, state-assigned real row.

Nuisance, and not the five coordinates again: family, support versus resistance, year, parent volatility tercile, UTC six-hour block, and relative quote volume on the frozen activity scale. Cluster is the product week of the touch. Bootstrap: 2000 draws, seed `20261015`, percentile 95% interval. Benjamini–Hochberg q=0.10 on the 6 primary cells. Practical scale: 3 percentage points on the probability difference.

## Candidate rule

A state/outcome passes the real-cohort conjunction only if q ≤ 0.10, the absolute adjusted difference is at least 3 pp, the 95% interval excludes 0, every epoch with N ≥ 30 has the same point-estimate sign and at least four such epochs exist, every leave-one-year-out refit with N ≥ 30 keeps that sign, dropping a family whose share is below 0.15 does not flip the sign, the cell and the state each have N ≥ 100, and the frozen membership Jaccard is at least 0.50.

Leave-one-year-out keeps the scaler and the centroids. It does not refit the partition.

Specificity, estimated for every primary cell and used only after the conjunction passes: stacked model, `Δ = β_real − β_pseudo`. Material level difference: the interval for Δ excludes 0, `|Δ| ≥ 0.03`, `|β_real| > |β_pseudo|`, and both `β_real` and `Δ` have the primary sign. A similar pseudo effect: not material, same sign, and `|β_pseudo| ≥ 0.5 × |primary|`. These two definitions are the #358 pre-outcome specificity rule. They are not taken from the #358 coefficients.

Classification:

- material specificity → `LEVEL_STATE_CANDIDATE`
- similar pseudo effect → `GENERIC_MARKET_STATE_CANDIDATE`
- conjunction passes and neither of those → `STATE_SUCCESSOR_SPECIFICITY_UNRESOLVED`

A real-minus-pseudo gap does not create a candidate when the real conjunction fails.

`SUCCESSOR_CANDIDATE` lists every state/outcome in those three labels. If the list is empty it is `NONE`.

Routing, in order:

1. any `LEVEL_STATE_CANDIDATE` → `JOINT_LEVEL_STATE_STRUCTURE_PRESENT`
2. else any `GENERIC_MARKET_STATE_CANDIDATE` → `GENERIC_JOINT_MARKET_STATE_ONLY`
3. else any unresolved successor from the conjunction → `STATE_SUCCESSOR_SPECIFICITY_UNRESOLVED`
4. else a cell that clears q, 3 pp, the interval and N, but fails stability → `STRUCTURE_PRESENT_BUT_UNSTABLE`
5. else if the RESOLVE support has N < 100 or fewer than 20 weeks → `STATE_PARTITION_INFORMATION_LIMITED`
6. else `NO_INCREMENTAL_JOINT_STATE_STRUCTURE`

The third route is predeclared because sections 23 and 26 of the task make a real-cohort pass a successor even when the pseudo contrast is neither material nor similar, and the two named classes do not cover that case. It is not a level-specific claim.

The #355 70% DAY cap is not a clause of this unit. DAY is 1442 of 1688 training rows.

## Search exposure

Five raw variables. One 60-minute window. Four predictor-only K diagnostics. Selected K = 3. Primary cells 6. Pseudo cells 6. Specificity cells 6. Stability cells 60. Leave-one-year-out cells 30. One three-way frequency map per state, not a second search. Individual slope models 0. Interactions 0. Extra windows 0.

## What this commit does not do

No product file changes. `PRODUCT_INTEGRATION_CANDIDATE` stays false. No confirmation, no state split, no funding, no liquidation layer, no order book, no 2025/2026 read, no level score. Claim ceiling L2. A selected state would be a historical association in this cohort, not a current probability.

Dependencies, not rewritten: #352 `dfc9e0f04358de15606382472badeb5aee787039`, #353 `c3d39bffda861b535605a98205d7578c0c84c782`, #354 `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`, #355 `aa85e5b43c405ee225336ff385e3a3383fa59d09`, #356 `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`, #357 `c1cd4e0102e700f7860d21a9af0d243c3bc367be`, #358 `e6e5f307cfa098db607544a556bae01a2310eb6a`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
