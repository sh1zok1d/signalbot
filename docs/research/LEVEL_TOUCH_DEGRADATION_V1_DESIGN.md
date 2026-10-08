# LEVEL_TOUCH_DEGRADATION_V1 — design note

**Status.** Design, committed before any break or reject rate is read. The preflight section is outcome-blind (counts, missingness, feature cuts). It is an amount of information, not a gate.

**Unit.** `LEVEL_TOUCH_DEGRADATION_V1`, first unit of family `LEVEL_BEHAVIOR_V1`.

**Tracks.** `STRUCTURE` + `PRODUCT_EVIDENCE`. Not `EDGE`.

**Claim ceiling.** L2 historical evidence under `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`. No L3 current probability. No L4. No direct trade call.

**Source main.** `1a2e425303fb29e1044ca57452b8ad9b6f0a831b` (unchanged at design time; the research authority of this task is the same HEAD the task named).

**Code.** `scripts/research/level_touch_degradation_v1/`. Constants in `constants.py` are the freeze. `outcomes.py` is not imported by the preflight.

## 1. Question and estimand

Among BTC levels whose price was fixed before the touch, does the historical frequency of `BREAK_FIRST` within 4h differ between the first independent touch, the second, and the third-or-later?

Primary estimand, two contrasts, touch 1 as the reference:

- Δ₂ = standardized P(BREAK_FIRST | touch 2) − standardized P(BREAK_FIRST | touch 1)
- Δ₃ = standardized P(BREAK_FIRST | touch 3+) − standardized P(BREAK_FIRST | touch 1)

Standardization is in §9. The crude rates are reported beside the standardized contrasts and cannot replace them.

The population for touch 2 and touch 3+ is the levels that were still there to be tested again. A difference is a difference among levels that reached that touch, not a causal effect of the touch itself. The allowed sentence is of the form «among levels that reached an independent Nth test, the historical frequency differed by …». It is not «each touch weakens the level».

## 2. Why this is not a rescore of DH1-L2 or DH3-V3

DH1-L2 asked whether a confluent level's 4h close-hold differs from a lone level's. DH3-V3 asked whether the second same-day touch of PDH/PDL, after a one-sided retreat of one barrier-X, has a different 4h close-hold from the first touch. Both are closed. This unit does not reopen them.

What is different, and why the reopen key is `OWNER_DECISION` plus `NEW_MECHANISM` rather than a parameter neighbour:

- The outcome is barrier first-passage through the zone versus away from it (`BREAK_FIRST` / `REJECT_FIRST`), not the sign of the close 4h later.
- The touch is an entry into a zone after a two-sided clearance, numbered 1 / 2 / 3+ over the level's whole active life (day, week or month), not a binary same-day retest of PDH/PDL.
- The estimand is the touch-number gradient under a predeclared standardization, on six structural kinds only.

DH1's barrier machinery (which bar hits first, same-bar tie, 90% bar presence, 4h, X = half of the 4h corridor half-width) is reused as a procedure. The barriers are placed on the zone edges, not on the event close. DH3's retreat is not the touch definition. This unit does not confirm or overturn DH3-V3, and it does not read `LEVEL_HOLD_4H`.

Round numbers, POC, session extremes, opens, OI, funding, taker flow, order book and liquidation clusters are out. The owner's candidate set is the product's structural set (`PUSH_LEVELS` in `beta/levels.py`): PDH, PDL, PWH, PWL, PMH, PML. That set is used because it is already the canonical ex-ante structural set and it matches the question. The wider DH1 set (rounds, POC) is not structural in the same sense.

## 3. Data surface and exposure

`CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT, 1m klines aggregated to complete 5m bins by the frozen DH1 loader (`scripts/research/dh1/data.py`). No forward-fill. Price OHLC only.

- Warm-up: 2020-01-01 inclusive (first month level and the 24h scale).
- Events: touch open time in `[2020-02-01, 2025-01-01)`.
- Nothing at or after 2025-01-01 is requested or kept. The E1-RUN-001 holdout is outside this window and the loader refuses it anyway.

Exposure: the 2020–2024 surface is `EXPOSED` for the whole column and `CONSUMED` for `PRICE_STRUCTURE.levels` by DH1-L2. This unit is a new mechanism on an already exposed surface. It is not a confirmation. 2025/2026 is not a fresh OOS. No second venue.

## 4. Level construction

Product period rules (`beta.levels.period_keys`, `_period_table`, `_full_period`), UTC, week = Monday 00:00 via `(day + 3) // 7`.

A level exists only when the source period and the next period are consecutive and both pass the product completeness rule (day and week: at least 98% of the expected bars and 95% finite; month: 95% finite). The price is the source period's high or low. The active interval is the next period only. Bars inside the source period are not touches: the extreme is still being formed there.

No level is added after the result. H vs L is stored as `struct_side` and is not a separate contrast. Break direction follows the approach side (§6), which can disagree with H vs L when price approaches a high from above or a low from below.

## 5. Zone and confluence

A level is not a point.

Primary half-width `w = 0.0015` (product `ZONE_TOL_PCT` = 0.15%). One sensitivity, `w = 0.0003` (product `AT_LEVEL_PCT` = 0.03%). The sensitivity replaces both the touch half-width and the birth-merge tolerance. It is not chosen after the result.

At each birth time, levels that start together and are not already inside an active zone are chain-merged when `(higher − lower) / lower ≤ w`. The anchor is the highest-priority member (product order PMH, PML, PWH, PWL, PDH, PDL; then lower price; then kind name). The zone is `[min price × (1−w), max price × (1+w)]` and does not move later. The episode lasts until the anchor's period ends.

A level that appears later and lies inside that zone, or within `w` of the anchor, is absorbed. It does not get its own touch counter. `n_members` and `absorbed_later` are descriptive fields. Confluence is not a hypothesis of this unit.

## 6. Distinct touch and orientation

Consecutive 5m bars inside the zone are one touch.

- Touch 1 is the first bar of the active interval whose range intersects the zone, including a period that opens already inside it. The level price is known at the open; there is no earlier touch of this level to continue.
- A later touch starts only after a clearance bar: the bar lies entirely outside the zone and at least `R = 1.0 × X` beyond the near edge, on either side. `X` is the primary barrier distance at that touch (§8). The refractory multiplier is not sensitized.
- If `X` is not finite or not in `(1e-8, 0.5)`, the touch is ineligible and the chain stops. The distance is not replaced with another rule.

Approach side, from information before the touch bar:

- Walk back to the last bar that does not intersect the zone. Close below the zone → side +1 (resistance, break is up). Close above → side −1 (support, break is down).
- If the touch is the first bar of the episode, the previous bar's close is the reference. If that close is inside the zone, the zone midpoint decides.

Touch number is geometric. An ineligible touch keeps its number; later eligible touches are not renumbered down. Buckets are `1`, `2`, and `3+`. Counts 4, 5, 6… are not separate groups.

## 7. Outcome

Horizon primary: 48 bars (4h), the product intraday horizon and the DH1 horizon. Sensitivity: 12 bars (1h), same touches, same `X` scale (the distance still uses `sqrt(48)`; only the window shortens).

`X = 0.5 × 1.2816 × σ × √48`. `σ` is the standard deviation of 5m log returns over the 288 bars ending at the bar before the touch (DH1's `rolling_sigma` shifted by one bar, so the touch bar's return is outside the scale). Present-fraction floor 0.9, the DH1 floor.

Side +1: break price = `zone_high × (1+X)`, reject price = `zone_low × (1−X)`. Side −1 swaps the directions. The window is bars `j+1 … j+horizon` (the touch bar is not in it).

- `BREAK` if the break price is hit on a strictly earlier bar than the reject price.
- `REJECT` if the reject price is hit strictly earlier.
- `NEITHER` if the window ends with neither hit. `NEITHER` stays in the denominator: P(BREAK_FIRST) = breaks / (breaks + rejects + neither).
- `AMBIGUOUS` if one 5m bar hits both and no earlier bar hit either. Order inside the bar is unknown, so the event is dropped from the denominator and counted. It is not coded 0.5.
- The window is missing (dropped, not a class) when fewer than 90% of its bars are finite or the window would end at or after 2025-01-01.

Sensitivity barrier fraction 1.0 rescales `X` by 2 and does not rebuild touches. Same-bar and `NEITHER` rules are unchanged.

## 8. Method

Chosen before the outcome. Direct standardization, not a model score.

Strata `s` = family {DAY, WEEK, MONTH} × approach side {+1, −1} × volatility tercile {3}. Eighteen cells. Year is a stability cut, not a stratum: a year axis would split the month family into empty cells.

Tercile edges are the 1/3 and 2/3 quantiles of `σ` on feature-eligible touches (usable scale, known side, complete primary window, event window). They are computed in the preflight from features only, written below, and reused at execution. They are not refit on `Y`, and they are not recomputed inside the bootstrap. The zone-width sensitivity recomputes edges on its own feature-eligible sample by the same rule; its edges are also in the preflight. Barrier and horizon sensitivities use the primary edges.

Weight `w_s` is the touch-1 count in stratum `s`. A stratum is kept for a contrast only when both arms have at least `MIN_ARM = 15` events. Weights are renormalized. The retained touch-1 weight share is reported.

`P` in a stratum is the break count over (breaks + rejects + neither). Δ is the weighted difference of those rates. Crude Δ, with no strata, is the companion.

Uncertainty: percentile interval, 95%, from 2000 resamples of the product week of the touch (`BOOT_SEED = 20261007`). A replicate that cannot form the contrast is dropped. If fewer than 90% of replicates survive, the interval is reported as not computable. Weeks are the dependence clusters (same week id the product uses for levels).

No p-value is the estimand. No Holm step picks a winner.

## 9. Baseline

The baseline is touch 1 in the same structural population, after the standardization above (same horizon, volatility tercile in the stratum, family and approach side balanced to the touch-1 mix). That is the comparable baseline L2 asks for.

## 10. Falsification

The product random-level control scores a single first touch at a matched distance. It has no second touch, so it cannot answer whether a touch-number pattern appears away from a structural level. It is not used.

The control is deterministic. Within each (family, structural side) group, episodes are ordered by `(start, anchor price, id)`. Episode `i` takes the signed open-distance of the episode half a rotation away, applied to its own open. If that price lies within `w` of any real structural instance whose active interval overlaps the episode, the next partner in the rotation is tried. If none remains, the control episode is dropped. One control per real episode that finds a price. The same scanner, numbering, outcome and standardization are applied. Control terciles use the real primary edges, so the volatility scale is the real sample's scale.

The control contrasts are §12 items 31–42. They are not a second primary.

## 11. Nuisance controls

In the standardization: level family, approach side, pre-touch volatility tercile. Year is reported as stability, not partialled out of the primary weights, so a year shift remains visible.

Time of day and approach speed are not in this unit. Approach speed is the successor `LEVEL_APPROACH_STATE_V1`, not a nuisance discovered after the fact.

## 12. Search exposure

Forty-two contrasts. All are computed. None is added after the result. Multiplicity handling: the claim sentence may cite only contrasts 1 and 2. The integration flag (§14) is a predeclared function of those two, of the year signs, and of the control contrast. It does not search the other cells. Sensitivity and slices are shown whatever sign they have.

Primary (the only claim contrasts):

1. Standardized Δ₂
2. Standardized Δ₃

Companions on the same primary events:

3. Crude Δ₂
4. Crude Δ₃
5–10. Crude Δ₂ and Δ₃ inside DAY, WEEK, MONTH
11–14. Crude Δ₂ and Δ₃ inside resistance and inside support
15–24. Crude Δ₂ and Δ₃ inside 2020, 2021, 2022, 2023, 2024

Sensitivity (standardized Δ₂ and Δ₃ only):

25–26. Zone half-width 0.03%
27–28. Barrier fraction 1.0
29–30. Horizon 12 bars

Falsification:

31–32. Control standardized Δ₂ and Δ₃
33–42. Control crude Δ₂ and Δ₃ inside each year 2020–2024

Bucket rates (break, reject, neither, ambiguous counts) are the components of these contrasts, not extra cells.

## 13. Stability and concentration

For each year 2020–2024 the result states N, the sign, and the crude Δ. A year where the sign flips or the contrast is missing is reported. Also reported: the share of analysis events in the busiest year, and the share of touch-3+ analysis events in the busiest family.

## 14. What would change our mind

There is no pass/fail word and no bar invented after the result.

The 3pp figure is the product's existing level-reaction materiality floor (`beta/levels.py` `MATERIAL_DIFF = 0.03`, the floor behind PRODUCT_DECISION_V2 §3's «отличается»). It is a practical scale for reading a level-reaction difference. It is not the DH1 rule (3pp and a positive Brier skill on an incremental probability), and this unit does not apply Holm or emit «отличается».

`PRODUCT_INTEGRATION_CANDIDATE = YES` only if every one of these is true, and otherwise `NO`:

1. |Δ₃| ≥ 0.03 and its 95% interval excludes 0.
2. Δ₂ is nonzero and has the same sign as Δ₃.
3. At least 4 of the 5 years have at least 30 analysis events in both touch 1 and touch 3+, and the crude Δ₃ in those years has the same sign as the primary Δ₃.
4. The control standardized |Δ₃| is smaller than half the real |Δ₃|, or the control 95% interval includes 0. If the control interval is not computable, only the half-magnitude test is used.
5. The busiest year holds at most 40% of analysis events, and the busiest family holds at most 70% of touch-3+ analysis events.
6. At least 100 week clusters contain an analysis event.

A separate, also predeclared, reading of "no practically large difference showed up" is: both |Δ₂| and |Δ₃| are below 0.03 and both intervals include 0. Anything between that reading and the integration flag is reported as the numbers, with candidate `NO`.

The flag is not permission to change `/levels`, a score, or a Telegram line.

## 15. Claim decision rule

L2 wording is allowed for a primary contrast when both arms have at least 30 analysis events and the 95% interval was computable. The sentence is past tense and quantitative: historical frequency, touch-1 baseline, difference in percentage points, N, interval. It states the survivor-bias qualifier in §1.

Below 30 events, or with no interval, that contrast does not get an L2 line. The record still shows the estimate and says the information is thin («мало данных (N)»).

Forbidden in every wording: a present-tense probability, «уровень скорее всего пробьют», «сильный/слабый» as a truth scale, a trade recommendation, and any verdict word (PASS, FAIL, CONFIRMED, REJECTED).

## 16. Preflight

Source: `docs/research/LEVEL_TOUCH_DEGRADATION_V1_PREFLIGHT.json`, computed before this note was committed. No break rate was read. The grid is 526,176 five-minute bars from 2020-01-01 through 2024-12-31, every close present.

No technical change followed the counts. The method in §§5–14 stays as written. Two facts are recorded so they are not mistaken for a later surprise:

- The planning MDE at a rate of 0.5 is about 6 pp with the DH1 planning design effect 1.25, and about 21 pp if the design effect is the events-per-week upper bound (4,213 / 258 ≈ 16.3). Both are larger than the 3 pp practical scale. That scale is not a gate and is not raised. The interval from the week resample is the uncertainty.
- Touch 1 of month levels is 41 events. Many month × side × tercile cells will miss `MIN_ARM = 15` and drop out of the standardized weights. `MIN_ARM` is not lowered. The month crude slice still reports that family.

Primary feature-eligible touches: 4,213 (touch 1 = 1,919, touch 2 = 1,105, touch 3+ = 1,189) in 258 weeks. Geometric touches: 4,275. The 62-touch gap is entirely before 2020-02-01. Chain stops: 0. Incomplete 4h windows: 0. Unknown approach side: 0.

By year (feature-eligible): 2020 = 749, 2021 = 886, 2022 = 838, 2023 = 836, 2024 = 904. Busiest year share 21.5%. By family: DAY 2,997, WEEK 932, MONTH 284. Touch 3+ by family: DAY 481, WEEK 501, MONTH 207 (busiest share 42.1%, the week family). Approach: 2,161 from below, 2,052 from above.

Episodes: 4,076 (DAY 3,478, WEEK 504, MONTH 94). Birth merges: 77. Later absorptions: 135. Instances emitted: 4,288. Drops for a non-consecutive or incomplete period: 4 level slots (2 source, 2 active).

Frozen primary σ terciles, from these feature-eligible touches: 0.0012364306616934476 and 0.001790567553180052. Zone-width sensitivity edges, from its own feature-eligible sample: 0.0012525362471446921 and 0.001802081401349861. Execution reads these numbers from the preflight file and does not refit them on Y.

Control episodes placed: 4,076 (one for every real episode). Feature-eligible control touches: 4,108 (1,962 / 1,091 / 1,055). The falsification contrast is computable. Narrow-zone feature-eligible touches: 4,117. `method_computable = true` in the preflight sense (every primary bucket is non-empty). That flag does not authorize a claim.

## 17. Out of this unit

No product change. No `beta_research_findings.yaml` edit. No second outcome definition, horizon, width, baseline or grouping after the rates are read. A post-hoc idea is named, not estimated.

Not run, even if the result is large: `LEVEL_REJECTION_MEMORY_V1`, `LEVEL_APPROACH_STATE_V1`, `LEVEL_CONFLUENCE_V1`. They are the only successor names this unit may list.
