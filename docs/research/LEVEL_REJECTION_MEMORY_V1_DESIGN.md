# LEVEL_REJECTION_MEMORY_V1 — design note

**Status.** Design, committed before any next-touch break, reject or neither rate is read. The preflight section is outcome-blind. It is an amount of information, not a gate.

**Unit.** `LEVEL_REJECTION_MEMORY_V1`, successor in family `LEVEL_BEHAVIOR_V1`. It is not a replication and not a rescore of the dependency.

**Dependency.** `LEVEL_TOUCH_DEGRADATION_V1` / PR #352 / `dfc9e0f04358de15606382472badeb5aee787039`. Source main at that branch point: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`. This unit does not edit that result.

**Tracks.** `STRUCTURE` + `PRODUCT_EVIDENCE`. Not `EDGE`.

**Claim ceiling.** L2 historical directional evidence under `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`. No L3 current probability. No L4. No direct trade call.

**Code.** `scripts/research/level_rejection_memory_v1/`. Constants in `constants.py` are the freeze. The parent package is imported and not retuned. `evaluate.py` is not run before this note is committed.

## 1. Question and estimand

Among ex-ante structural BTC levels whose previous independent touch ended as `REJECT_FIRST` and that were touched again, does the speed of that rejection carry additional historical information about `BREAK_FIRST` on the next independent touch, after the nuisance factors below?

The cohort is conditional on both events. The sentence is about levels with an observed rejection that were later retested. It is not «a strong rejection makes levels stronger».

Primary estimand, one coefficient:

- b = change in P(BREAK_FIRST on touch i+1) per +1 SD of rejection speed

in the linear probability model of §8. +1 SD means a faster rejection. Touch 1 of the dependency unit is not the baseline. The baseline is the same next-touch population at the mean of the frozen speed scale, after the controls.

## 2. What is reused, and what is not a rescore

Reused unchanged from the dependency: level kinds PDH/PDL/PWH/PWL/PMH/PML, zone half-width 0.0015, birth merge, distinct-touch and refractory rules, touch numbering, approach side, 4h horizon, X = 0.5 × 1.2816 × σ × √48, same-bar `AMBIGUOUS` drop, `NEITHER` kept in the break denominator, `CORE_BTC_BINANCE_V0` 2020–2024 price bars, and the deterministic half-rotation pseudo-level.

Not reused as the question: the touch-number contrasts. Those stay the dependency's result. This unit conditions on a previous `REJECT_FIRST` and asks whether the quality of that rejection adds anything. A previous `BREAK_FIRST` followed by a later test is a different mechanism and is not in this cohort.

No canonical point-in-time rejection-strength metric exists in the dependency, in DH1, or in DH3. DH3's retreat is a binary clearance of one barrier-X, which this family already uses as the refractory, not as a strength. The metric below is defined here, once.

## 3. Data

Same surface as the dependency. Price OHLC only. No OI, funding, taker flow, liquidations, order book, live tape, 2025/2026, second venue, or the E1 holdout. The loader is the dependency's `load_discovery_bars`.

## 4. Cohort

A pair is touch i and touch i+1 of the same episode, with consecutive geometric touch numbers.

- Touch i is feature-eligible and its primary outcome is `REJECT`.
- Touch i+1 is feature-eligible.
- The rejection bar is strictly before the next touch bar.

`BREAK` and `NEITHER` on touch i do not form a pair. An ineligible touch stops the parent chain, so there is no later partner to renumber.

Analysis rows are those pairs whose next outcome is `BREAK`, `REJECT` or `NEITHER`. A next touch that is `AMBIGUOUS` is counted and dropped. `NEITHER` stays in the sample as a zero on the break indicator.

## 5. Rejection speed

`bars_to_reject` is the 1-based offset of the first bar in the parent window (bars j+1 … j+48) that hits the reject barrier. It is the same hit index `outcomes.classify` uses. The range is 1…48. It is known on that bar, which is before the next independent touch: a new touch cannot start until clearance, and clearance on the reject side is not earlier than the reject hit.

Primary feature:

`speed_raw = −log(bars_to_reject)`

Larger means faster. The log is the predeclared map for a waiting time. It is not chosen after the outcome.

`speed_z = (speed_raw − mean) / sd`, with mean and sd frozen in the preflight from real feature pairs. The next touch's outcome is not an input. Ambiguous next touches are still in that moment calculation; execution drops them and does not refit the scale. The bootstrap does not refit it either.

## 6. Two sensitivity features, not a score

No weighted strength score. No 0–100 bin. No weak/medium/strong class.

1. Linear speed: `−bars_to_reject`, z-scored with its own frozen mean and sd. Same model, same +1 SD = faster direction. This checks the log map.
2. Overshoot: on the rejecting bar only, distance traded past the reject barrier, divided by the price width of X. Known on that bar. It does not use the path after the rejection and does not use the wait until the next touch. +1 SD means a deeper wick through the barrier, not a faster rejection.

Max excursion until the next touch is not used. That path lengthens with the wait.

## 7. Outcome

Next touch only. Parent primary semantics: `BREAK` / `REJECT` / `NEITHER` / `AMBIGUOUS`, horizon 48 bars, same X. No new horizon and no new barrier.

Primary endpoint: the break indicator. The reject indicator and the neither indicator are the same model on the same rows, reported beside it. They are decomposition, not a second claim. The dependency already showed that a lower break frequency can sit next to a flat reject frequency and a higher neither share. This unit shows that split for the speed coefficient.

## 8. Method

Chosen before the outcome. One linear probability model. Not a classifier and not a score.

Columns, reference in parentheses:

- intercept
- `speed_z` (the claim coefficient)
- next touch bucket 3+ (reference: the next touch is touch 2, so the rejection was the first touch)
- family WEEK, family MONTH (reference DAY)
- support side of the next touch (reference: resistance, approach from below)
- volatility tercile mid, high, using the dependency's frozen σ edges 0.0012364306616934476 and 0.001790567553180052 on the next touch's σ (reference: low tercile)
- `gap_z`, the frozen z-score of `log(gap_bars)`
- year 2021, 2022, 2023, 2024 (reference 2020)

`gap_bars` is the number of 5m bars from the rejection bar to the next touch bar. It is the wait after the rejection is known. It is not the time from the previous touch bar: that sum equals `bars_to_reject + gap_bars` and would partial out the predictor. The next touch's approach side is the nuisance, because that side places the next barriers. The previous side is already inside the rejection that was measured.

Uncertainty: 95% percentile interval, 2000 resamples, seed `20261008`. A replicate whose design is not full rank is dropped. If fewer than 90% of replicates survive, the interval is not computable.

Cluster, decided before the outcome: the product week of the next touch for DAY and WEEK episodes, because those episodes sit inside one week and the week also ties different levels together. MONTH episodes span weeks, so those pairs use the episode id. Week-only clusters would split one month level across weeks. Episode-only clusters would split one week of day levels apart.

No p-value is the estimand. No Holm step picks a cell.

## 9. Descriptive tertiles

Tertile edges of `speed_raw` are the 1/3 and 2/3 quantiles on the same outcome-blind feature pairs. `slow` is at or below the lower edge, `fast` is above the upper edge, `mid` is the rest. All three bands are reported. The fast-minus-slow crude differences are cells, not a replacement primary. Edges are not refit on Y.

## 10. Baseline and falsification

The primary comparison is inside this structural cohort: next touches that differ in prior rejection speed, after the controls. Pseudo-levels are not the baseline.

Falsification: the dependency's half-rotation pseudo-level episodes, scanned and paired with the same rules. The regression uses the real cohort's frozen scales, so "1 SD" is the structural scale. The question is whether the same speed coefficient appears where the level is not the structural price.

## 11. Checks that are not a new grid

These are predeclared. They do not authorize a new feature if the primary interval includes 0.

- Cell 4 drops only the touch-ordinal column. If the association lives there and disappears in cell 1, the speed was standing in for touch number.
- Cell 5 drops only the log-gap column. If the association lives there and disappears in cell 1, the speed was standing in for the wait until the retest.
- Cells inside next-touch bucket 2 and bucket 3+ use the same model without the bucket column.
- Year, family and side slices drop only the columns that are constant inside the slice. A slice that flips sign is reported.

## 12. Search exposure

28 contrasts. All are computed. None is added after the result. The claim sentence may cite only cell 1. The integration flag uses cell 1, the year cells, the control cell, and the concentration counts. It does not search the other cells.

1. Primary: speed, BREAK, full controls
2. Speed, REJECT, full controls
3. Speed, NEITHER, full controls
4. Speed, BREAK, no touch-ordinal column
5. Speed, BREAK, no log-gap column
6. Crude P(BREAK | fast) − P(BREAK | slow)
7. Crude P(REJECT | fast) − P(REJECT | slow)
8. Crude P(NEITHER | fast) − P(NEITHER | slow)
9. Linear speed, BREAK, full controls
10. Overshoot, BREAK, full controls
11–15. Speed, BREAK, within 2020, 2021, 2022, 2023, 2024
16–18. Speed, BREAK, within DAY, WEEK, MONTH
19–20. Speed, BREAK, within resistance and within support
21–22. Speed, BREAK, within next-touch bucket 2 and within 3+
23. Control, cell-1 specification
24–28. Control, within each year 2020–2024

Band rates are the components of cells 6–8, not extra cells.

## 13. What would change our mind

There is no pass/fail word.

The 3pp figure is the same practical reading scale the dependency used for a level-reaction frequency difference (`MATERIAL_DIFF` 0.03). Here it is applied to a 1 SD speed contrast. It is not the DH1 3pp-plus-Brier rule, and it is not refit after this outcome.

`PRODUCT_INTEGRATION_CANDIDATE = YES` only if every one of these is true:

1. |b| on cell 1 is at least 0.03 and its 95% interval excludes 0.
2. At least 4 of the within-year coefficients that have N ≥ 30 have the same sign as cell 1.
3. The control |b| is smaller than half of |cell 1|, or the control interval includes 0. If the control interval is not computable, only the half-magnitude test is used.
4. The busiest year holds at most 40% of analysis pairs, and the busiest family at most 70%.
5. At least 100 clusters contain an analysis pair.

If cell 1's interval includes 0 after the touch-ordinal and gap adjustment, the candidate is NO even when cell 4 or cell 5 looks large. That is evidence against a separate rejection memory, not a reason to pick another threshold, map or horizon.

A predeclared near-zero reading is: |cell 1| < 0.03 and its interval includes 0.

The flag is not permission to change `/levels`, a score, or a Telegram line.

## 14. Claim rule

L2 wording is allowed when the analysis N is at least 30 and the cell-1 interval was computable. The sentence is past tense and quantitative: historical break frequency, the 1 SD speed contrast, the adjustment list, N, the interval, and the conditioning on a previous rejection plus a later retest.

Below 30 pairs, or with no interval, there is no L2 line. The estimate is still shown, with «мало данных».

Forbidden: a present-tense probability, «сильный уровень», «этот уровень выдержит», «уровень защищён», a trade recommendation, and any verdict word.

## 15. Selection

This unit conditions on a previous `REJECT_FIRST` and on a later independent touch. Levels that broke, levels that were not retested, and rejections that never cleared the refractory are outside the estimate. Repeating that limit is part of the result, not a caveat added after the sign is known.

## 16. Preflight

Source: `docs/research/LEVEL_REJECTION_MEMORY_V1_PREFLIGHT.json`, computed before this note was committed. The next touch's break, reject and neither labels were not aggregated. No technical change followed the counts. The method in §§5–15 stays as written.

The grid is the dependency's 526,176 five-minute bars. Feature-eligible touches: 4,213, of which 2,098 are `REJECT`. Feature pairs: 1,155. Non-positive gaps: 0. Rejected touches whose successor is not feature-eligible: 0. Clusters: 283 (about 4.1 pairs per cluster).

By year: 2020 = 215, 2021 = 230, 2022 = 217, 2023 = 238, 2024 = 255. Busiest year share 22.1%. By family: DAY 697, WEEK 342, MONTH 116. Busiest family share 60.3% (DAY). Next-touch buckets: 2 = 554, 3+ = 601. Side: resistance 557, support 598. Volatility terciles: 391 / 374 / 390.

`bars_to_reject` runs from 1 to 48, median 7 (p25 = 3, p75 = 18). The correlation of `speed_raw` with `log(gap)` is −0.11, so the wait is not a relabeling of the speed. Overshoot is defined on all 1,155 pairs (median 0.15 barrier-widths). Frozen scales are the `scales` object in the preflight file. Speed tertile edges: −2.6390573296152584 and −1.3862943611198906.

Planning MDE for an unadjusted unit-variance coefficient at rate 0.5 is about 4.6 pp with design effect 1.25, and about 8.3 pp at the pairs-per-cluster design effect. Both are larger than the 3 pp reading scale. That scale is not a gate and is not raised. The cluster interval is the uncertainty.

Control feature pairs: 1,056 in 245 clusters (DAY 645, WEEK 317, MONTH 94). `method_computable = true`. Month within-slice N is 116. The month coefficient is still estimated; the column set is not reduced because of that count.

## 17. Out of this unit

No product change. No findings-registry edit. No second feature, horizon, threshold or cohort after the coefficient is read.

Not run: `LEVEL_APPROACH_STATE_V1`, `LEVEL_CONFLUENCE_V1`, and any combined level-strength score.
