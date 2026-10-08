# LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1

MODE = CONFIRMATION

Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim ceiling L2.

Owner go: the task that opened this unit. One predeclared contrast. No rescue after the outcome.

This note is the freeze. The evaluator must not run while this file is uncommitted, and it must not be edited after an outcome is read.

## 1. Provenance

Source main at the start of the research chain: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

Dependencies, not rewritten:

- #352 `LEVEL_TOUCH_DEGRADATION_V1` `dfc9e0f04358de15606382472badeb5aee787039`
- #353 `LEVEL_REJECTION_MEMORY_V1` `c3d39bffda861b535605a98205d7578c0c84c782`
- #354 discovery-first methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- #355 `LEVEL_APPROACH_STATE_DISCOVERY_V1` `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- #356 `LEVEL_STRUCTURE_DISCOVERY_V1` `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d` (branch point)

The candidate is a post-hoc description of the #352 first-touch table, not a primary hypothesis of #352. On Binance USD-M BTC 2020–2024 the published touch-1 row is BREAK_FIRST 40.1%, REJECT_FIRST 50.3%, NEITHER 9.6% (N=1905), so RESOLVED_WITHIN_4H = 90.4% (`docs/research/LEVEL_TOUCH_DEGRADATION_V1_RESULT.md`). The owner stated the matching pseudo-touch description as BREAK_FIRST 29.5%, REJECT_FIRST 48.9%, NEITHER 21.6%, so RESOLVED_WITHIN_4H = 78.4%, a difference of about +12 pp. This unit does not recompute that table. The +12 pp gap is not a required replication magnitude.

## 2. Why the Binance 2020–2024 surface cannot confirm this

#352 read touch outcomes on `CORE_BTC_BINANCE_V0` for 2020-02-01 .. 2025-01-01. A relation noticed after that read is not confirmed by reading the same surface again (`docs/research/DISCOVERY_FIRST_RESEARCH_DECISION_V1.md` §1.B). Binance 2025/2026 is not a substitute.

## 3. Confirmation surface

`DH1_BITMEX_XBTUSD_TRADES_5M_V0`. BitMEX XBTUSD public trades aggregated to 5m OHLC. Inventory days `2017-08-01..2019-12-31`. Canonical SHA256 `df3c32922e95bdca80fcf0fa695ec2c8f29455cf8c1ab930277e92c994b4995f`. Object-list SHA256 `649710ec605b4e16334c5281f830efe77c27a014e684d8f0b913be630f157100`.

Exposure status, fixed before any barrier label on this cohort:

`TIME_DISJOINT / OUTCOME_UNREAD_FOR_THIS_CLAIM / FEASIBILITY_EXPOSED`

This surface is not pristine.

- Atlas `ATLAS_SURFACES_V1.yaml` marks `DH1_BITMEX_XBTUSD_TRADES_5M_V0` / `PRICE_STRUCTURE.levels` as `EXPOSED`: DH1 replication-surface feasibility counted events and states only.
- `docs/research/DH1_RESULT.md`: nothing reached `PROMISING_PROTOTYPE`, so the DH1 replication outcomes were not read.
- `docs/research/DH1_FEASIBILITY.md`: written with `MARKET_OUTCOMES_OPENED = false`. The DH1-L2 replication count is an event/state planning count.
- DH1-L2 discovery hold rates were computed on Binance 2020–2024 for a different endpoint (confluent versus lone 4h hold).
- No BitMEX record in `docs/research` names `RESOLVED_WITHIN_4H` or this real-versus-pseudo first-touch contrast.

DH1's own level-event definition includes round numbers and POC and is not the #352 structural set. D2 and other BitMEX programs read price paths for other estimands. Those facts are why the surface is feasibility-exposed. They are not a prior reading of this contrast. If that contrast had already been read here, this unit would stop before outcomes.

## 4. Event window

Grid `[2017-08-01, 2020-01-01)`. Event window `[2017-09-01, 2020-01-01)`.

August is warm-up for the 24h volatility scale and for previous-month levels. The window is not moved earlier to gain N.

Outcome-blind completeness, from the preflight:

- 254304 grid bars, 254252 trade bins, finite close fraction 0.9998, 52 missing bars, longest missing run 18.
- August 2017 has 8928 bars (31 × 288) and fraction 0.9993, so the parent full-month rule accepts it. September PMH/PML are available. The start stays 2017-09-01.
- The first week chunk has 1728 bars (Tuesday 2017-08-01 through Sunday) and is not a full week. The first week level waits for a full previous week. That does not move the event start.
- Day, week and month construction is the parent rule in `level_touch_degradation_v1.events.level_instances`.

Epochs, by the open time of the real first touch:

- `2017H2`: 2017-09-01 .. 2018-01-01
- `2018`: 2018
- `2019`: 2019

## 5. Structural levels

Exact reuse of #352. Kinds: PDH, PDL, PWH, PWL, PMH, PML. UTC period construction, level birth, active lifetime, zone half-width 0.0015, merge and confluence, touch entry, independent-touch clearance at 1.0 × primary X, support/resistance from the approach side, barrier X = 0.5 × 1.2816 × σ × √48, refractory, same-bar ambiguity, and the 0.9 presence rule are the parent functions. No round numbers, POC, VWAP, session levels, or new level types.

`feature_eligible` on the parent touch is not reused. That flag requires an open at or after 2020-02-01 and would drop every BitMEX touch. Eligibility here is the same geometric predicates (touch number 1, known side, usable X, complete 4h window) with this unit's event window. The parent package is not edited.

The confirmation grid ends at 2020-01-01, so a 4h window that would cross that instant fails the series-length check inside the parent scanner. The parent's default clock bound of 2025-01-01 does not extend the grid.

## 6. First touch only

Primary cohort: `touch_number = 1`. Touch 2 and touch 3+ stay out. The candidate came from the first-touch real-versus-pseudo description. Later touches are a selected retest population and were studied as their own question.

## 7. Pseudo control

`level_touch_degradation_v1.control.control_episodes`, unchanged. For each real episode the control keeps the active interval, family and structural side, and places the anchor at a half-rotation of signed open-distance within `(family, struct_side)`. The first non-colliding partner is kept. The pseudo zone is scanned with the same touch and 4h barrier machinery. The rotation is a function of episode order. It is not refit after outcomes.

On this grid the control built one pseudo episode for every structural episode (`NO_CONTROL = 0`). The algorithm transferred. No new control is introduced.

## 8. Matched cohort

A pair enters the availability set when the same source episode has a legitimate real first touch and a legitimate pseudo first touch. Legitimate means touch number 1, open inside the event window, known approach side, usable primary X, and a complete 4h window. Ambiguous bars are not counted here; they are dropped at execution if either label is `AMBIGUOUS` or unclassified.

Outcome-blind census (`LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1_PREFLIGHT.json`):

| quantity | count |
|---|---:|
| structural episodes | 1981 |
| controls built | 1981 |
| real geometric first touches | 920 |
| pseudo geometric first touches | 944 |
| real legitimate first touches | 890 |
| pseudo legitimate first touches | 891 |
| matched pairs | 558 |
| missing real (episode not legitimate) | 1091 |
| missing pseudo | 1090 |
| real legitimate without a legitimate pseudo | 332 |
| pseudo legitimate without a legitimate real | 333 |
| incomplete 4h, real / pseudo | 0 / 0 |
| real first touch outside the event window | 30 |
| pseudo first touch outside the event window | 53 |
| unknown side / unusable X | 0 / 0 |
| product weeks among matched real touches | 120 |

Epochs of matched pairs: 2017H2 101, 2018 253, 2019 204. Families: DAY 485, WEEK 63, MONTH 10. Real approach side: resistance 271, support 287.

558 matched pairs are above the predeclared floor of 30. The confirmation proceeds. The #355 70% DAY cap is not a clause of this unit. DAY is 485/558 of this cohort because the structural set is mostly previous-day levels; that share was not used to change the cohort.

Volatility terciles are the 1/3 and 2/3 quantiles of sigma on the matched real first touches: `0.0015306816339365449` and `0.002742945442702028` (hex `0x1.91424e3bbedf1p-10`, `0x1.6785f9f1364e8p-9`). They are not the Binance 2020–2024 edges. They are not refit on the outcome or inside the bootstrap.

## 9. Primary endpoint

`RESOLVED_WITHIN_4H` = 1 when the frozen 4h label is `BREAK` or `REJECT`, and 0 when it is `NEITHER`. `AMBIGUOUS` is excluded, exactly as #352 excludes a same-bar tie. This is an aggregation of the three frozen labels, not a new classifier. The parent `outcomes.classify` / `outcomes.attach` functions are called only by the evaluator and by tests.

## 10. Estimand and estimator

One primary estimand, in probability (reported in percentage points):

`Δ_resolution = mean(Y_real − Y_pseudo)`

over analysis pairs. Positive means the real structural first touch resolves into BREAK or REJECT within 4h more often than the matched pseudo first touch. The unit is the source episode. Touch 2 and touch 3+ are not in the mean.

The estimator is that paired mean. It equals `(n_real_only − n_pseudo_only) / N` for this binary endpoint. No regression replaces it.

## 11. Uncertainty

Week-block bootstrap, 2000 draws, seed `20261012`, 95% percentile interval. A draw is kept only if at least 90% of draws are finite.

The block is the product week of the real first touch, the same `(day + 3) // 7` id as `beta.levels`. Every pair whose real touch falls in that week is resampled together. The pair is one row, so the real and pseudo outcomes are never split.

Week is the block because neighbouring level episodes share a regime, and an episode-iid draw would treat them as independent. A year block would leave three clusters. DH1 planning used week clustering (design effect 1.25). The choice is frozen before the outcome.

Each reported cell uses its own stream `default_rng(20261012 + cell)`, so an empty slice does not move another cell's draws. Cell order: 0 primary, 1 BREAK, 2 REJECT, 3 NEITHER, 4–6 epochs `2017H2` / `2018` / `2019`, 7–9 families DAY / WEEK / MONTH, 10–11 resistance / support, 12–14 leave-one-epoch-out in that epoch order, 15 adjusted coefficient.

## 12. Adjusted sensitivity

Secondary only. Stacked rows, one real and one pseudo per analysis pair. The coefficient on the real-touch indicator in

`Y = α + β Real + γ' Z + ε`

with Z the frozen columns. β does not replace Δ_resolution.

Columns, screened before outcomes on the availability-matched stacked rows: drop a dummy with mean below 0.02 or above 0.98, then drop any column that makes the design short of full rank, in this order: `family_week`, `family_month`, `support`, `vol_mid`, `vol_high`, `epoch_2018`, `epoch_2019`.

Kept: `family_week`, `support`, `vol_mid`, `vol_high`, `epoch_2018`, `epoch_2019`.

Dropped for share: `family_month` (10/558 pairs). Dropped for rank: none.

`support` is the approach side of that row's own touch. Volatility uses that row's own pre-touch sigma and the frozen real-touch edges. Epoch dummies use that row's own open. Family and epoch are constant within the pair, so on a balanced pair they do not move β; support and volatility can differ across the two touches and can move β. The bootstrap resamples real-touch weeks and refits β. Draws that are short rank are invalid.

## 13. What would change our mind

Practical scale: 3 percentage points. Same reading scale as the parent level-reaction floor (`PRACTICAL_SCALE = 0.03`). Not the DH1 bar of 3 pp plus a positive Brier skill score. Not a requirement to recover 12 pp.

Confirmation-supporting evidence requires all five:

1. Δ_resolution > 0
2. the two-sided 95% interval lies entirely above 0
3. the point estimate is at least +3 pp
4. the point estimate is positive in at least 2 of the 3 epochs that have at least 30 analysis pairs (an epoch with fewer than 30 pairs is ineligible; if fewer than 2 epochs are eligible the clause fails)
5. each leave-one-epoch-out point estimate stays above 0

Evidence labels, applied in this order, are descriptions of that rule:

- all five clauses: `REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE`
- otherwise, if the 95% upper bound is below +3 pp: `NO_MATERIAL_POSITIVE_RESOLUTION_DIFFERENCE`
- otherwise, if clauses 1–3 hold and 4 or 5 fails: `POSITIVE_RESOLUTION_DIFFERENCE_UNSTABLE`
- otherwise: `INFORMATION_LIMITED`

These words are not PASS or FAIL. A near-zero estimate with a tight interval is evidence against a materially positive resolution difference. An interval that admits both a difference of at least +3 pp and 0 or a negative difference is information-limited. No threshold is added after the estimate is seen.

## 14. Stability and leave-one-epoch-out

Diagnostics, not a second primary and not a search for a winning slice:

- epochs `2017H2`, `2018`, `2019`
- families DAY, WEEK, MONTH
- real-touch approach side: resistance (`side = +1`), support (`side = −1`)

Leave-one-epoch-out drops the pairs whose real touch is in the named epoch. Definitions, the pseudo rotation, the tercile edges and the column list are not refit.

## 15. Decomposition

Paired differences for BREAK, REJECT and NEITHER, with the same week-block interval. They add up to the primary contrast: Δ_BREAK + Δ_REJECT = Δ_resolution and Δ_NEITHER = −Δ_resolution on the analysis pairs. They do not decide the confirmation and they are not a multiple-testing family.

Search exposure is 16 cells: 1 primary, 3 decomposition, 1 adjusted coefficient, 3 epochs, 3 families, 2 sides, 3 leave-one-epoch-out cuts. No FDR grid.

## 16. No rescue

After the outcome, this unit does not change the horizon, the barrier, the zone, the pseudo rotation, or the level set. It does not split a fast break, add a resolution threshold, cut on age, confluence or dwell, add volume, open interest or flow, change the timeframe, or optimize X. A new observation is a `FOLLOW_UP_IDEA` with no new calculation.

Discordant-pair counts are a restatement of the primary binary contrast, not an extra test.

## 17. Claim and product

If the analysis N is at least 30, the claim is L2: the quantitative historical contrast (rate on the real first touch, rate on the pseudo first touch, difference, N, interval). A supporting label is a replicated historical mechanism and is still L2. It is not L3. L3 would require prospective calibration of this claim class. L4 is out of scope. A historical frequency is not a current probability. No direct trade call.

The allowed sentence, if the supporting label holds, is that the first touch of a pre-known structural level resolved into one of the two barrier outcomes within 4 hours more often than the matched first touch of the deterministic pseudo-price. That is a statement about resolution. It is not a statement that the level is strong, that it holds, that it will break, that support means buy, that resistance means sell, or that the chance of a move now is a stated percent.

`PRODUCT_INTEGRATION_CANDIDATE = YES` only when the supporting label holds and the claim is issued. Otherwise NO. Nothing in `/btc`, `/levels`, `/check`, `/risk`, scoring, the findings registry, Telegram or deploy changes in this unit. Integration needs a separate owner go.

## 18. Execution

One official run of `scripts/research/level_first_touch_resolution_confirmation_v1/evaluate.py` after this file is committed. The evaluator recomputes the census and the tercile edges and stops before any barrier label if they differ from the preflight. It refuses to overwrite a result file. A crash before the result file is written may be repaired only when the bug is not motivated by an outcome, the outcome was not read, the repair is committed, and the new evaluator is what runs.

Compiler V3 is not run. No new universal validator is added.
