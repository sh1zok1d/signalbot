# LEVEL_STRUCTURE_DISCOVERY_V1 — design note

**Status.** Design, committed before any feature-conditioned break, reject or neither rate is read. The preflight section is outcome-blind. It is an amount of information, not a gate.

**Mode.** `DISCOVERY`. This unit maps a bounded structural-level space. It does not pre-assert a sign. A relation selected because it looked best is `DISCOVERY_ONLY` on this selection surface and needs a separate `MODE = CONFIRMATION` unit. This note does not authorize that successor.

**Unit.** `LEVEL_STRUCTURE_DISCOVERY_V1`, family `LEVEL_BEHAVIOR_V1`.

**Dependencies.** `#352` `LEVEL_TOUCH_DEGRADATION_V1` `dfc9e0f04358de15606382472badeb5aee787039` → `#353` `LEVEL_REJECTION_MEMORY_V1` `c3d39bffda861b535605a98205d7578c0c84c782` → `#354` methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26` → `#355` `LEVEL_APPROACH_STATE_DISCOVERY_V1` `aa85e5b43c405ee225336ff385e3a3383fa59d09` → this unit. Source main: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`. This branch starts at the #355 head. It does not edit a parent result and it does not merge to main.

**Tracks.** `STRUCTURE` + `PRODUCT_EVIDENCE`. Not `EDGE`.

**Claim ceiling.** A family-level statement that reports the whole search, with no winner selected, may be L2 under `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` when the analysis N is at least 30. A cell named because it passed the successor rule is `DISCOVERY_ONLY`, not L3 and not L4. No current probability. No direct trade call. `PRODUCT_INTEGRATION_CANDIDATE` stays `NO`.

**Code.** `scripts/research/level_structure_discovery_v1/`. Constants in `constants.py` are the freeze. The parent packages are imported and not retuned. `evaluate.py` is not run before this note is committed. Frozen scales and the redundancy decision live in `docs/research/LEVEL_STRUCTURE_DISCOVERY_V1_PREFLIGHT.json`.

## 1. Question

Which point-in-time properties of the structural level itself, if any, contain reproducible level-specific historical information about the subsequent `BREAK_FIRST` / `REJECT_FIRST` / `NEITHER`, above the already known touch history and the general market nuisance factors?

Level-specific means the association on the real structural price differs from the same association on a predeclared pseudo price that keeps the structural metadata and the market clock and moves only the price location. The screened object is

`Δ_level_specific = β_real − β_pseudo`.

A slope that is the same size at the rotated price is a description of the market around that metadata. It is not evidence that the structural price location matters. No sign is assumed for age, confluence, zone width or formation geometry. This unit does not test the claims "confluence is stronger", "an old level is weaker", or "an extreme with a large close-off is stronger".

## 2. What is context, not a rescue

`#352`. Touch ordinal carries information in that cohort: touch 3+ had a lower `BREAK_FIRST` frequency. Touch ordinal is a nuisance here. No new touch threshold is searched.

`#353`. Prior rejection speed added no incremental information. It is not re-windowed.

`#355`. Price-only approach geometry produced associations that also appeared on pseudo-levels. This unit does not search new speed, efficiency or dwell thresholds and does not interact those features. They enter only as one predeclared sensitivity, and only for a relation that already passed the successor rule.

## 3. What is reused unchanged

From `LEVEL_TOUCH_DEGRADATION_V1`: PDH/PDL, PWH/PWL, PMH/PML; zone half-width 0.0015; birth clustering and later absorption; independent-touch and refractory rules; touch numbering; support/resistance from the approach side; barrier `X = 0.5 × 1.2816 × σ × √48`; `σ` the DH1 rolling sigma shifted one bar; 4h window of 48 bars; same-bar `AMBIGUOUS` drop; `NEITHER` kept; `CORE_BTC_BINANCE_V0` 2020–2024.

The parent half-rotation, inside `(family, struct_side)`, supplies the non-structural price and keeps the real episode's lifetime. Section 8 says what this unit then does with that price. The rotation is not refit.

Parent volatility tercile edges, not refit: `0.0012364306616934476` and `0.001790567553180052`.

## 4. Data

`CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT 5m, 2020–2024, loaded by the parent `load_discovery_bars`. OHLC. Quote volume is the Binance kline quote field, summed over the anchor's completed source period. Taker-buy quote is not read.

Forbidden and not read: open interest, funding, taker flow, liquidations, order book, live tape, 2025/2026, any other venue, and the E1 holdout `[2026-08-16, 2026-08-25 17:20)`.

## 5. Cohort

The population is the #352 feature-eligible structural touches. A visible approach episode is not required. `feature_eligible` is the parent availability flag: usable pre-touch X, approach side in `{+1, −1}`, a complete 4h window, and an open time at or after 2020-02-01. It is not an outcome.

After the feature audit, rows are restricted to source episodes that have at least one feature-complete real touch and at least one feature-complete pseudo touch. That intersection is computed from the predictor rows, before any outcome is attached. `AMBIGUOUS` bars are dropped only after the intersection is fixed. A side that then becomes thin is reported. It is not repaired by changing the match.

The #355 approach-eligible subset is not the primary cohort.

Level family is a nuisance and a stratification variable. It is not a candidate. This note does not conclude that a month level is stronger than a day level.

## 6. Decision boundary

`T` is the open of the touch bar `j`.

| clock | features |
| --- | --- |
| `AVAILABLE_AS_OF = level_birth` | formation range, formation volume, close-off-extreme, extreme timing, extreme density |
| `AVAILABLE_AS_OF = immediately_before_touch` | age, confluence, timeframe diversity, zone span |

Birth features use the anchor's completed source period. That period is closed before the level's active period opens. The active period's bars are not inputs to those features.

Membership, age and zone span use constituents whose `available_i0 ≤ j`. A level born at `i0` is known at the open of `i0`. A constituent with a later index is future and is excluded. The touch bar's outcome, the path after `j`, a later touch, a later confluence, and a later period extreme are not inputs.

The touch's own pre-touch primary X is known before the touch bar and is the scale for zone span. It is not refit.

## 7. Merge semantics that the features have to follow

The parent birth rule clusters instances that open on the same bar when successive prices, after sorting, satisfy `(higher − lower) / lower ≤ 0.0015`. The anchor is the highest-priority kind in the cluster (`PMH > PML > PWH > PWL > PDH > PDL`). The zone box is fixed at birth and does not expand when a later instance is absorbed.

A later instance whose price lies inside that box, or within 0.0015 of the anchor, joins the ledger at its own `i0`. It does not open a new touch counter. Same-family multiples arrive by that later absorption: the generator emits one high and one low per period, so two highs of one family do not share a birth bar. A high and a low of one family can share a birth cluster when their prices are within 0.15%. Different families can share a birth cluster on the same rule.

Confluence and diversity therefore count only members already known at `j`. Zone span uses those members' prices, which can include a later member once it is known. The zone box itself is not the span.

There is no composite level-strength score. Structural-feature interactions estimated in this unit: 0.

## 8. Feature formulas

No sign is a hypothesis.

| id | name | as of | formula |
| --- | --- | --- | --- |
| S1 | age | immediately before the touch | `(j − i0) / (i1 − i0)`. Undefined when `j` is outside `[i0, i1]` or `i1 ≤ i0`. |
| S2 | confluence | immediately before the touch | count of ledger members with `available_i0 ≤ j`. Coding in section 9. |
| S3 | diversity | immediately before the touch | number of distinct families among those members. Coding in section 9. |
| S4 | zone span | immediately before the touch | `0` when one known member. Otherwise `(max price − min price) / min price / x_primary`. |
| S5 | formation range | level birth | `log(range_rel / median of prior same-family ranges)`. `range_rel = (high − low) / open` on the anchor source period. |
| S6 | formation volume | level birth | the same log ratio on the source-period sum of quote volume. |
| S7 | close off extreme | level birth | high anchor: `(high − close) / (high − low)`. Low anchor: `(close − low) / (high − low)`. |
| S8 | extreme timing | level birth | index of the last source bar that reaches the final extreme, divided by `(last − first)`. |
| S9 | extreme density | level birth | share of finite source bars that reach the final extreme. |

The formation baseline is the last 20 completed prior periods of the same family whose key is strictly less than the source key. The source period is excluded. Fewer than 4 usable priors, a non-positive range, or a non-positive baseline makes the log ratio undefined. Quote is usable when at least 90% of the source bars have a finite nonnegative quote and the sum is positive. Incomplete periods follow the parent full-period rule (`frac ≥ 0.95`, and a bar-count floor when the family has an expected length). Month has no expected bar count.

A bar reaches a high extreme when `high ≥ final_high × (1 − 0.0005)`, and a low extreme when `low ≤ final_low × (1 + 0.0005)`. The tolerance is 5 bp. It is not the confluence tolerance 0.0015. It is not chosen from an outcome.

Close-off-extreme is formation geometry. This note does not call it rejection strength.

S5–S9 are properties of the anchor source period. They can describe the regime of that period rather than a quality of the price location. That is why the pseudo-location comparison and the year, family and volatility controls are part of the primary estimand.

## 9. Outcome-blind audit

Allowed inputs: zone and touch counts, member-count distribution, missingness, predictor distributions, pairwise Pearson correlations, algebraic equivalence, sparsity, pseudo coverage, matched coverage, cluster counts. Not allowed: a feature-conditioned outcome rate, a real-minus-pseudo outcome difference, a slope, a candidate ranking.

Missingness cap: a feature missing on more than 1% of the real feature-eligible touches, before the match, is dropped. On that population the two formation features are each missing on 0.9257% of touches, which is under the cap, so quote volume stays. Every other raw feature is missing on 0%. The common matched sample below is the rows on which every surviving candidate is finite.

Sparse-count rule, decided on the matched real predictor distribution and then applied unchanged to the pseudo rows. It is not recomputed on the pseudo distribution.

- no variation: drop;
- share of count ≥ 3 is at least 0.05: keep the integer and z-score it;
- otherwise: binary multi (`count ≥ 2`) versus singleton. The integer is not also entered as a score.

Result, before any outcome:

| feature | decision |
| --- | --- |
| confluence | binary. Share of count ≥ 3 is 0.0155. Unique integer values: 4. |
| diversity | binary. Share of count ≥ 3 is 0.0053. Unique integer values: 3. |

Redundancy: Pearson `|ρ| ≥ 0.90`, including the 0/1 coding. Greedy keep order is the table in section 8. Age is the duration nuisance. A later feature that matches age at the cut is dropped. Age is not dropped for matching itself. A feature is not removed because a later slope is small.

Diversity versus confluence, after the binary coding, has `ρ = 1` within floating-point noise. The earlier feature, confluence, is kept. Diversity leaves the family. On this surface the binary "more than one family" indicator is the same indicator as "more than one member". The integer three-family share, 0.53%, stays below the continuous-count threshold, so it is not entered as a score and it is not merged into a new bucket.

No other pair among the retained features reaches 0.90. Formation range and formation volume have `ρ = 0.768`. Confluence and zone span have `ρ = 0.485`. Both pairs stay.

Retained, in keep order: age, confluence, zone span, formation range, formation volume, close-off-extreme, extreme timing, extreme density. Eight features. Dropped before outcomes: diversity only.

Zone span is a continuous spread with a point mass at 0 (the singleton formula). Its frozen tertile edges are both 0. Extreme density's tertile edges are both `1/288`. In both cases the middle shape band is empty under the predeclared `≤ q33` / `> q66` rule. The shape label is then `insufficient`. The primary model still uses the +1 SD slope. The tertile edges are not replaced after the outcomes.

Multi-member touches in the matched real sample: 285 of 2649. That count is information. It is not a reason to invent another confluence definition.

## 10. Pseudo-level construction

The parent control episode keeps the real episode's `(i0, i1)`, family, structural side and period open, and it places the anchor at another episode's signed distance from the open. The first non-colliding partner in a half-rotation within `(family, struct_side)` is kept. That construction destroys the structural ledger: the control episode stores `n_members = 1` and a synthetic kind, and it has no formation.

This unit does not read those destroyed fields. For a control touch:

- formation features are the real anchor's birth features;
- age, confluence, diversity and zone span are computed from the real constituent ledger at the control touch's own `j`, with the control touch's own pre-touch X;
- the outcome is the parent 4h label at the rotated zone.

What is preserved: market lifetime, family, structural side of the anchor, the real constituent clock, and the real anchor's formation geometry. What is destroyed: the special price location. The rotated zone is the location being tested. It is not a new source extreme.

A control touch is eligible only when its `shadow_id` is a real episode that itself has a feature row. After feature completeness, section 5 keeps only episodes present on both sides. Touch times are not paired one-to-one. The match key is the real episode id. Real and pseudo touches of that episode are one cluster.

The control was not chosen after an effect. There is no second control.

## 11. Nuisance, fixed before outcomes

The stacked model adjusts for:

- family WEEK and MONTH (reference: DAY);
- touch ordinal 2 and 3+ (reference: 1);
- support (reference: resistance, approach from below);
- pre-touch volatility tercile mid and high, parent edges (reference: low);
- year 2021–2024 (reference: 2020);
- age, z-scored on the frozen real scale, for every feature other than age;
- confluence, as the frozen 0/1 contrast, when the feature is zone span.

Session and time of day are not nuisances. #352 did not use them, and this family has no frozen session dependence for these barrier outcomes. They are not added after the result. No nuisance-by-real interaction is estimated: a nuisance shift is assumed common to the real price and the rotated price. That is a limitation of the specification.

The 70% DAY cap from #355 is a frozen rule of that unit only. It is not applied here. The matched real sample is 2009/2649 DAY (75.8%). That share is a description of the population. It does not remove a candidate. Family concentration is handled by the family adjustment, the family-specific slopes, the minimum N, and leave-one-family-out. Leave-one-family-out of DAY leaves 640 real touches and 689 pseudo touches, both above the predeclared floor of 30, so that diagnostic is computable. A remaining sample under 30 is skipped. It is not an automatic scientific failure. No new share threshold is introduced after the result.

## 12. Primary estimand

For each retained feature `F` and each outcome `Y`, one stacked linear probability model on the real and pseudo rows together. Not a classifier.

```
Y = intercept
  + β_pseudo · x
  + real
  + Δ · (x × real)
  + touch and family and side and volatility and year
  + age when F is not age
  + confluence when F is zone span
```

`x` is the frozen real-sample z-score (`ddof = 0`) for a continuous feature, so +1 SD is the structural scale, applied to both populations. A binary feature stays 0/1. Its coefficient is the adjusted probability difference, multi minus singleton.

`β_real = β_pseudo + Δ`. All three come from the same fit. The real main effect absorbs the average outcome-rate difference between the two populations so that difference is not forced into `Δ`.

Scales, tertile edges and the binary coding are the preflight object. They are not refit on Y, inside a bootstrap, on a slice, or after ambiguous touches are dropped. Ambiguous touches remain inside the frozen moments.

The three outcome models are separate. Their probabilities are not constrained to sum to one.

Uncertainty is a cluster bootstrap, 2000 draws, seed `20261011`, percentile 95% interval. The cluster is the real episode id. A 95% interval is reported only when at least 90% of draws return a finite coefficient. The two-sided p-value is the Wald p-value from the bootstrap standard error (`ddof = 1`) via `erfc`. A missing p-value enters Benjamini–Hochberg as 1.

## 13. Multiplicity and practical scale

The FDR family is the 8 × 3 = 24 primary `Δ` cells. Benjamini–Hochberg, `q = 0.10`. Raw estimates and intervals are reported for every cell. FDR is a screen. It does not replace the effect size or the stability checks. `β_real`, `β_pseudo`, the no-touch companion, the shape contrast and the slice slopes are not in the FDR family.

Practical magnitude, frozen before outcomes: `|Δ| ≥ 0.03`, per +1 SD or per the binary contrast. This is the same probability-difference reading scale the parent touch unit called a material difference and the approach discovery reused. It is a few percentage points. It is not a universal 0.5 SD bar and it is not the DH1 promotion rule (3 percentage points plus a positive Brier skill score). It is one clause of the successor rule, not a gate on what is printed.

## 14. Successor rule

A feature/outcome cell is a `SUCCESSOR_CANDIDATE` only when every clause holds.

1. `Δ` has Benjamini–Hochberg `q ≤ 0.10` inside the 24-cell family.
2. `|Δ| ≥ 0.03` and the 95% interval excludes 0.
3. The sign of `β_real` agrees in at least 4 years that have both `n_real ≥ 30` and `n_pseudo ≥ 30`. A year under that floor is ineligible, not a disagreement.
4. The sign of `Δ` agrees in at least 4 such years.
5. Among families with both sides at least 30, if at least two families are eligible then at least two share the primary `Δ` sign. Fewer than two eligible families does not by itself fail the cell.
6. Every leave-one-year-out `Δ` is finite and has the primary sign. Definitions, scales, controls, the pseudo construction and the cuts are not refit. Leaving 2020 out drops the 2021 dummy, so 2021 is the reference.
7. Every leave-one-family-out with both remaining sides at least 30 keeps the sign. A thinner remainder is skipped. Leaving DAY out drops the week dummy, so week is the reference and the month dummy stays.
8. The cell is not a sign-reversal of the known touch-ordinal pattern. The primary model already includes the touch dummies. The cell fails only when the companion without those dummies has `|Δ| ≥ 0.03`, an interval that excludes 0, and the opposite sign.
9. No point-in-time leak. This is a construction invariant of sections 6–8, checked by the tests, not a second search after the slopes.

If none pass, `SUCCESSOR_CANDIDATE = NONE`. That is a complete result.

## 15. Shape, stability, and the approach sensitivity

Shape uses tertile edges `q33` and `q66` from the matched real predictor distribution. For each band the result shows the real outcome rate, the pseudo outcome rate, and the difference. The continuous contrast is `(real − pseudo in the high band) − (real − pseudo in the low band)`, cluster-bootstrap. The binary contrast is the crude multi-minus-singleton probability difference on the real rows minus the same difference on the pseudo rows. Labels: `near_zero` when the absolute contrast is below 0.03 and the interval includes 0; `monotonic` when the three differences are ordered and the ends differ; `u_shape` when the middle lies outside the ends; `binary_contrast` for a 0/1 feature; `insufficient` when a required band difference is missing; otherwise `other`. A shape that suggests a threshold is an `EXPLORATORY_SUCCESSOR_IDEA` with no new cut and no new fit.

Every primary cell also has point estimates by year (2020–2024), family (DAY/WEEK/MONTH), side (support/resistance) and touch ordinal (1/2/3+). Those slices are diagnostics. They are not a place to name a new winner.

The approach sensitivity is not a search. If and only if a cell passed section 14, the same stacked model is refit on the rows where the #355 approach features exist, with those seven features added as further adjustments: velocity, efficiency, persistence, acceleration, range state, relative volume, dwell. They describe the path into the price being tested, real zone or rotated zone, using the approach unit's primary band of 1.0× X and bars strictly before `j`. Their scales are the preflight object `approach_scales`, frozen on the matched real rows that have a complete approach episode (N = 1271). The sensitivity reports the loss of N against the primary N. It cannot create a candidate. If there is no candidate, the sensitivity is not run.

## 16. Search exposure

Per retained feature and outcome, 24 material cells: the primary stacked `Δ` (its `β_real` and `β_pseudo` are components of that one fit), the no-touch companion, the shape contrast, 5 year points, 3 family points, 2 side points, 3 touch-ordinal points, 5 leave-one-year-out points, 3 leave-one-family-out points.

Eight retained features give `8 × 3 × 24 = 576` material cells. The FDR family size is 24. The approach sensitivity is outside both counts. No cell is added after the outcomes are read.

## 17. Routing

One primary label, from the predeclared order:

| condition | label |
| --- | --- |
| at least one successor candidate | `LEVEL_SPECIFIC_STRUCTURE_PRESENT` |
| else any primary `Δ` with `\|Δ\| ≥ 0.03` and an interval excluding 0 | `STRUCTURE_PRESENT_BUT_UNSTABLE` |
| else any primary `β_real` of that size whose interval excludes 0 | `NO_LEVEL_SPECIFIC_STRUCTURE` |
| else any no-touch `Δ` of that size whose interval excludes 0 | `REDUNDANT_WITH_KNOWN_STATE` |
| else | `NO_LEVEL_SPECIFIC_STRUCTURE` |

A binary confluence feature sets `sparse_binary_present` and does not, by itself, switch the primary label to `INFORMATION_LIMITED`. The rarity is reported with N. Atlas state: `NO_LEVEL_SPECIFIC_STRUCTURE` and `REDUNDANT_WITH_KNOWN_STATE` map to `NO_STRUCTURE`. The two "present" labels map to `CLOSED_ON_SURFACE`. Claim level: `DISCOVERY_ONLY` when a successor exists; otherwise L2 when the real analysis N is at least 30; otherwise `not_issued`.

These labels are descriptions of the search. They are not PASS, FAIL, CONFIRMED or REJECTED.

## 18. Preflight counts

Parent panel: 526176 bars, 4076 real episodes, 4076 control episodes, 4213 feature-eligible real touches. No outcome was classified to produce this table.

Matched feature-complete sample, before the ambiguous drop:

| | real | pseudo |
| --- | ---: | ---: |
| touches | 2649 | 2646 |
| episodes | 1228 | 1228 |
| DAY / WEEK / MONTH | 2009 / 544 / 96 | 1957 / 562 / 127 |
| touch 1 / 2 / 3+ | 1228 / 724 / 697 | 1228 / 722 / 696 |
| resistance / support | 1381 / 1268 | 1368 / 1278 |
| 2020–2024 | 496 / 760 / 542 / 370 / 481 | 505 / 756 / 571 / 356 / 458 |

Multi-member real touches: 285. Approach-overlap real touches: 1271.

## 19. Product and what this note does not start

Nothing in the product changes. No `/btc`, `/levels`, `/check`, `/risk`, scoring, level strength, config, findings registry, Telegram text or deploy. A discovery winner is not integrated. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

Not started by the result, and not authorized here: a confirmation unit on this 2020–2024 surface, a confluence rescue, a new formation threshold, open interest, taker flow, liquidations, funding, a book, a flow increment, a combined level score, a model, or a structural interaction.

## 20. Allowed wording

A historical frequency in this structural-touch cohort, the level-specific increment against the rotated price, the analysis N, and the interval. Not a current probability. Not a statement that confluence, age or close-off makes a level strong.
