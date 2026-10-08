# FROZEN_HOUR_RANGE post-outcome diagnosis V1

`MODE = POST_OUTCOME_DIAGNOSIS`
`EVIDENCE_UPGRADE = NONE`
`ORIGINAL_RESULT_UNCHANGED = true`
`CONFIRMATION = false`
`PRODUCT_CHANGE = none`
`CLAIM_CEILING = L2, unchanged`
`ROUTE, unchanged = FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`

This note rereads the pairs already scored by the one historical outcome of `OPENING_RANGE_OBJECT_V1`. It does not replace that result, does not rerun the official evaluator, and does not start a successor. The official result file is byte-identical to the published read: SHA256 `9d21dafa4272bc0dab16329187edd65a7acf50adad071b80c8d63f2ea3c57fae`. The diagnosis script checks that every foundation delta and every published year delta matches that file before it writes anything.

Machine twin: `docs/research/FROZEN_HOUR_RANGE_POST_OUTCOME_DIAGNOSIS_V1.json`.
Figures, descriptive only: `docs/research/figures/frozen_hour_range_diagnosis/`.

Surface: `CORE_BTC_BINANCE_V0` `[2020-01-01, 2025-01-01)`, the surface already consumed by the outcome read. No 2025, 2026, E1, BitMEX, prospective, or product tape.

## What the published result already said

Foundation real minus pseudo, 4h resolution: UTC_00 +9.48 pp (N 1719), UTC_08 +6.59 pp (N 1716), UTC_12 +4.93 pp (N 1704), UTC_16 +7.48 pp (N 1698). Route `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`. On UTC_00 the map was direction extension-first +7.04 pp, outside occupancy −0.86 pp, outward excursion −0.264 W. UTC_00 year deltas were −2.0, −5.6, +3.1, +33.5, +18.0 pp. Those sentences stay as written.

## Descriptive definitions used here

These are labels for this note. They are not new endpoints and not a second map.

- `P0` is the close of the last formation bar. The frozen pseudo bounds are already placed on that close.
- Relative width is `W / P0`. Asymmetry is `(u − d) / (u + d)` with `u = log(high / P0)` and `d = log(P0 / low)`.
- Pre-formation RV is the square root of summed squared 5-minute log returns on the 12 closes before the formation hour. Post-decision RV is the same functional on the 48 returns after the decision close. Both use the clock of the object day, so real and pseudo share them.
- Partner lag is the calendar distance from the object day to the weekday that supplied `u` and `d`. The match itself is the published half-rotation. Nothing was rematched.
- Width bins are round and reciprocal: `PSEUDO_WIDER` if `W_real / W_pseudo < 0.8`, `SIMILAR` if the ratio is in `[0.8, 1.25]`, otherwise `REAL_WIDER`. Not a searched match.
- A paired mean ± 1.96 sample standard errors is a descriptive Wald interval. It is not a family test and not a pass/fail.
- Shares of windows whose max excursion reaches 0.5W, 1.0W, or 1.5W are shape marks only.
- `EARLY` means 2020–2022 and `LATE` means 2023–2024. That split is the one already printed in the result. It is not a new threshold, and no year is tested as a winner.

The one linear description below, `resolution difference = a + b log(W_real / W_pseudo)`, is marked `EXPLORATORY_POST_OUTCOME`. Its intercept is not an adjusted claim. On this sample the mean log width ratio is about zero, so the intercept copies the raw average and does not answer the equal-width question. The similar-width bin does.

## 1. Where the foundation delta comes from

The real resolution rate barely moves. The pseudo rate falls, and it falls hardest in 2023H2.

UTC_00, published pairs:

| Year | N | Real | Pseudo | Delta | Count difference | Descriptive SE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 | 352 | 89.5% | 91.5% | −1.99 pp | −7 | 2.18 pp |
| 2021 | 319 | 92.5% | 98.1% | −5.64 pp | −18 | 1.69 pp |
| 2022 | 355 | 90.1% | 87.0% | +3.10 pp | +11 | 2.27 pp |
| 2023 | 337 | 92.9% | 59.3% | +33.53 pp | +113 | 3.05 pp |
| 2024 | 356 | 94.1% | 76.1% | +17.98 pp | +64 | 2.52 pp |

Count differences sum to +163, and 163 / 1719 is the published +9.48 pp. As an accounting identity, 2023 contributes 69% of that pooled delta and 2024 contributes 39%. The three earlier years contribute −9% together. That is not a ranking of years.

The same split, real rate versus pseudo rate, on every cell:

| Cell | Early real | Early pseudo | Early delta | Late real | Late pseudo | Late delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| UTC_00 | 90.6% | 92.0% | −1.36 pp | 93.5% | 68.0% | +25.54 pp |
| UTC_08 | 97.1% | 96.6% | +0.59 pp | 97.1% | 81.8% | +15.31 pp |
| UTC_12 | 95.8% | 95.0% | +0.78 pp | 97.8% | 86.7% | +11.13 pp |
| UTC_16 | 93.0% | 92.3% | +0.69 pp | 95.2% | 77.6% | +17.54 pp |

Early is N about 1014–1026. Late is N about 683–699. Real rates stay in a band of roughly 90–98% at every hour and every block. Pseudo rates leave that band only in the late block.

Half years show the step is inside 2023, not a smooth five-year drift. UTC_00 pseudo resolution is 79.8% in 2022H2, 79.7% in 2023H1, then 36.9% in 2023H2 (N 160, delta +56.2 pp), then 73.0% and 79.1% in the two halves of 2024. The other three hours drop in the same half: 2023H2 pseudo rates are 60.7% at UTC_08, 67.3% at UTC_12, and 53.6% at UTC_16. Real rates in that half stay at 93–98%. Monthly series in the figure show July–September 2023 as the trough and a partial recovery through 2024. No month is nominated as a breakpoint.

## 2. Geometry, and whether coupling strengthened after 2022

Median relative width, UTC_00:

| Year | Real W/P0 | Pseudo W/P0 | Median W_real/W_pseudo | Share pseudo wider | Median partner lag |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2020 | 0.85% | 0.68% | 1.35 | 36% | +910 days |
| 2021 | 1.39% | 0.54% | 2.60 | 12% | +910 days |
| 2022 | 0.87% | 0.79% | 1.00 | 50% | +910 days |
| 2023 | 0.52% | 1.22% | 0.48 | 77% | −917 days |
| 2024 | 0.62% | 1.06% | 0.60 | 76% | −917 days |

Absolute dollar width rises with the BTC price and is the wrong comparison. Relative width is the one that scales the barriers. Asymmetry stays near zero (UTC_00 median real asymmetry between −0.08 and +0.04). It does not flip with the delta. The width ratio does.

The partner is not a nearby weekday. On every cell the median absolute lag is 910 or 917 days, which is 130 or 131 weeks: the frozen half-rotation of a five-year same-weekday list, plus an occasional one-week collision step. Object year and partner year:

- 2020 takes 2022/2023
- 2021 takes 2023/2024
- 2022 is split between 2020 and 2024
- 2023 takes 2020/2021
- 2024 takes 2021/2022

2023H2 is the sharp half because its partners are 2021 (97% of UTC_00 pairs, lag −917 days). Median pseudo relative width in 2023H2 is 1.78%. Median real relative width in 2021H1 is 1.78%. The other way around, 2021H1 pseudo relative width is 0.45%, and 2023H2 real relative width is 0.45%. The rotation swaps those two halves. 2021H1 + 910 days lands on 30 June 2023 through 27 December 2023.

Real relative width tracks the object day's own volatility in every year. On UTC_00 the Spearman correlation of real `W/P0` with post-decision 4h RV is +0.67, +0.57, +0.56, +0.56, +0.55 from 2020 through 2024. The same correlation for pseudo width is +0.18, −0.05, +0.11, −0.12, +0.13. Pooled, real is +0.66 against post-decision RV and +0.67 against pre-formation RV (N 1718 for the pre window; one early day has no prior hour). Pseudo is −0.12 and −0.13. Real and pseudo relative widths correlate at −0.15. The other three hours look the same: real stays near +0.55 to +0.70, pseudo stays near zero.

So the coupling of today's formation with today's later volatility did not strengthen after 2022. It was already there, and it is stable. What changed is which arm carries today's width. A narrow range resolves more often because both barriers are closer: own relative width versus own resolution has Spearman about −0.21 to −0.30 for the real arm and about −0.20 to −0.50 for the pseudo arm. That sign is mechanical.

Median post-decision RV on UTC_00 is 0.0087, 0.0125, 0.0081, 0.0056, 0.0079 across the five years. 2021 is the wide year and 2023 is the quiet year. The real hour records that. The pseudo hour records the opposite year.

## 3. Does anything remain when the widths are similar?

Predeclared bins, UTC_00, all years. `EXPLORATORY_POST_OUTCOME`. Not a control that the original result survives.

| Bin | N | Real resolution | Pseudo resolution | Delta | Descriptive SE | Extension delta | Excursion delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pseudo wider | 724 | 96.4% | 61.5% | +34.9 pp | 1.88 pp | +21.3 pp | +0.75 W |
| Similar, 0.8 to 1.25 | 298 | 91.9% | 93.3% | −1.34 pp | 1.78 pp | +1.34 pp | −0.019 W |
| Real wider | 697 | 86.9% | 99.3% | −12.3 pp | 1.26 pp | −5.3 pp | −1.42 W |

The similar-width interval, descriptive only, is about −4.8 pp to +2.1 pp. Early similar is −0.6 pp (N 180). Late similar is −2.5 pp (N 118). The same pattern holds on the other hours: the positive raw delta sits in the pseudo-wider bin, and the similar bin is within a few percentage points of zero. Late similar deltas are −5.7 pp at UTC_08 (N 106), +1.8 pp at UTC_12 (N 114), and +3.8 pp at UTC_16 (N 130).

The pooled mean log width ratio on UTC_00 is −0.019 and the median ratio is 0.98. Average widths match. The linear intercept at equal width is therefore +9.0 pp, almost the raw +9.48 pp, with slope −0.245 on the log ratio. That intercept is not evidence that a boundary effect remains at equal width. Positive and negative mismatches cancel in the average ratio, while they do not cancel in the resolution rate, because a too-wide range can fail by tens of percentage points and a too-narrow range cannot succeed by more than the gap that remains up to 100%. In 2021 the wide real arm still resolved at 92.5%, so the delta only reached −5.6 pp. In 2023H2 the imported wide pseudo arm resolved at 36.9%, so the delta reached +56 pp.

## 4. The extension / excursion / occupancy trio

The three published UTC_00 signs are three mixtures of the same width swap, not one path that extends first and then stops short.

Pooled UTC_00 excursion: real mean 1.067 W (median 0.66, p90 2.33), pseudo mean 1.331 W (median 0.60, p90 3.23). Share reaching 0.5W is 60.0% real versus 55.6% pseudo. Share reaching 1.0W is 33.7% versus 35.2%. Share reaching 1.5W is 19.4% versus 25.5%. The mean gap is an upper tail. The median goes the other way.

Conditional on a real extension-first path (N 870), the paired excursion difference is +0.07 W, and only 35% of those pairs have a smaller real excursion than their own pseudo. The sentence "real reaches the extension first and then travels less far than its pseudo" is not what those pairs do.

By block, the two map signs come from different years:

| Block | Extension-first delta | Outside delta | Excursion delta |
| --- | ---: | ---: | ---: |
| UTC_00 early | +0.3 pp | −6.9 pp | −0.71 W |
| UTC_00 late | +17.0 pp | +8.0 pp | +0.40 W |

Early, the pseudo arm is the narrow one, so its excursion in units of its own W is large (mean 1.73 versus 1.02) and the extension rates match. Late, the real arm is the narrow one, so it hits the 0.5W extension first more often (+17 pp) and its W-normalized excursion is larger, not smaller. The pooled excursion sign (−0.264 W) is the early tail. The pooled extension sign (+7.04 pp) is the late rate. Outside occupancy is −6.9 pp early and +8.0 pp late, and those cancel to the published −0.86 pp. The null occupancy result is that cancellation.

Among resolved windows, median time from the touch bar to the first barrier is 30 minutes for real and 20 minutes for pseudo. That is descriptive timing, not a new endpoint.

## 5. Touch timing and the four clocks

UTC_00 median real touch latency stays at 15–20 minutes in every year, and the real immediate-touch rate stays at 23–28%. The pseudo immediate-touch rate is 66% in 2021, when the pseudo range is narrow, and 17% in 2023, when it is wide. Pseudo median latency moves from 0 minutes in 2021 to 50 minutes in 2023. High-side share stays near one half on both arms (about 47–53%). The break is not a change of side.

UTC_00, UTC_08, UTC_16, and UTC_12 share the 910-day partner, the quiet-2023 versus wide-2021 swap, and the 2023H2 pseudo trough. Noon is milder because its imported range fails less far (2023 pseudo resolution 78.9%, against 59.3% at UTC_00), not because its real rate is lower. Late real rates are 93.5%, 97.1%, 97.8%, and 95.2% at 00/08/12/16. The largest foundation delta has the lowest late real rate. The extra size of the UTC_00 delta is a deeper pseudo failure. This note does not call funding the cause, and it does not open any other hour.

## 6. Competing descriptions

Plausibility here is exploratory. It is not an evidence class and it does not move the claim off L2.

1. **Pseudo-construction artifact, highest.** The frozen pseudo places another same-weekday's log offsets on today's `P0`, about 910 days away. 2023H2 receives 2021H1's width, and 2021H1 receives 2023's width. For the swap: the partner calendar, the exchanged relative widths (1.78% and 0.45%), and the pseudo rate falling while the real rate does not. Against a pure bookkeeping error: the pairs and the deltas match the official file, and the rotation is the rule that was frozen before the read. What is still open is only whether a different, predeclared pseudo would leave a remainder. This diagnosis does not build that pseudo.

2. **Contemporaneous width coupling, the transmission, also high.** Today's real width tracks today's pre and post RV every year (Spearman about +0.55 to +0.67), and a narrower arm resolves more often. Against "the coupling appeared after 2022": the real correlation is slightly lower in 2023 than in 2020, and pseudo width is uncorrelated with today's RV in every year, which is what a 910-day draw should look like. Coupling is how a width swap becomes a resolution gap. It is not a new regime of predictability.

3. **A volatility regime difference between 2021 and 2023, real, but not a new boundary.** Post-decision RV and real `W/P0` both mark 2021 as wide and 2023 as quiet. Against "the boundary started working in 2023": the real resolution rate did not jump. The regime matters because the pseudo imports the other regime.

4. **A genuine frozen boundary, not supported once width is held in the descriptive bin.** The similar-width bin is −1.3 pp on UTC_00, with extension +1.3 pp and excursion −0.02 W. Against discarding the idea completely: that bin still allows a 25% width gap, N is 298, and the descriptive interval still reaches about +2 pp. A small remainder is not separable here. It is not the source of the published +9.48 pp.

5. **An 8-hour or funding-adjacent clock, not identified.** All four frozen hours, including noon, break in the same half. Against a fully generic-hour claim: noon is milder, and hours outside this set were not read, on purpose. Nothing in the partner lag or the real rates singles out 00/08/16 as a funding mechanism.

## 7. What would separate the descriptions later

Not started. Not a design note. Not to be run on this consumed surface.

1. **Width-held pseudo, the informative one.** On a fresh surface, keep the frozen hour and the 4h resolution estimand, and predeclare a pseudo that still uses another day's log shape but is scaled so `W_pseudo = W_real` before the path is scored. The diagnosis says the paired resolution difference should then sit near the similar-bin result, about zero, if the published delta was the 910-day width swap. A difference that remains is the part width does not account for. Fitting that scale on 2020–2024, or residualizing the published pairs and calling the residual a result, would not be that test.

2. **The same width-held contrast at UTC_00 and UTC_12, only as part of that fresh comparison.** If both are null, the milder noon cell was a milder width swap. If UTC_00 remains and UTC_12 does not after width is held, a clock-specific boundary question is still open. No new hour. No funding wording. No product line.

## What was not changed

Design `3be350eb`, amendment A1 `fb57fc8d`, amendment A2 `e4963fe8`, the evaluator manifest, and both official result files are untouched. The evaluator package digest is unchanged because the diagnosis script lives outside that package. The atlas outcome unit was not rewritten. No successor, forecast, product change, or new surface was started.
