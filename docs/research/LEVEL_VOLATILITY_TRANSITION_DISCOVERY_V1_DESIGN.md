# LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1

MODE = DISCOVERY. Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This is direction 8 of 8 in the current Level Engine discovery sequence. Owner go is the task that opened this unit. One official run. No confirmation, no successor, no product change, and no merge to `main`.

Parent HEAD: `fcdf650ccf58a96c54f4931c0cb5d16e7d143473` (`LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1`). Source main: `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`. Event constructor: #352 `dfc9e0f04358de15606382472badeb5aee787039`. Prior scientific results are not rewritten.

`outcomes_transition_read = false` in this note. The census below is path presence only.

## Question

Is a structural first touch a volatility-regime change point more than its matched pseudo-price touch?

For each event, compare realized volatility in the 60 minutes after the touch bar with realized volatility in the 60 minutes before that same touch bar. The touch bar itself is in neither window. The primary contrast is the paired difference of those log ratios, real minus the exact #352 pseudo.

This is an event-conditioned difference-in-change. It is not a claim that the range after a level is large.

## Novelty

The audit is against the closed cells that a volatility or level-range reading could be mistaken for. It does not reopen any of them.

| Prior | What it tested | Why this unit is a different object |
| --- | --- | --- |
| H01 | Unusually low recent RV, then later RV. Three lookbacks, compression quantiles 0.10/0.20/0.30, five horizons. `H01_KILL`: compression tended to persist. Atlas `VOLATILITY_STATE.compression` × `CANDLES`. | Every structural first touch is eligible, whatever its pre-touch RV. No quantile, no low-volatility screen, no expansion threshold, no horizon grid. |
| B2-01 | A generic volatility-state transition feature aimed at forecast improvement. `B2_01_CLOSED_NO_PROMOTION`. Atlas `VOLATILITY_STATE.regime_transition` × `CANDLES`. | No B2 threshold, no forecast target, no AE/MAE, no threshold scan. The anchor is the #352 structural first touch. |
| DH3-V2 `KEY_LEVEL_RANGE` | First touch of PD/PW/PM/POC versus random control levels, next 4h log range. About +2.3% (CI +1.4..+3.2), below product materiality. Atlas `PRICE_STRUCTURE.levels` × `CANDLES`, `NO_STRUCTURE`. | Not a 4h high-low range, not an absolute future range, not DH3 random levels, not a six-coin pool, not `RANGE_4H`. |
| DH3-P1 | Quiet-market open-interest tercile toward `RANGE_4H`. Atlas `VOLATILITY_STATE.compression` × `POSITIONING`. | No open interest. No range endpoint. No tercile. |
| V2 `COMPRESSION_BREAKOUT` (MATH-005) | A maximal qualifying compression run inside a fixed 16×15m lookback, as a breakout-quality claim. | Not a compression-run detector and not a breakout claim. |
| #352 | Touch ordinal of the same levels toward 4h `BREAK_FIRST`. | Used only as the event and pseudo constructor. No barrier label is read. |
| #357 | 4h resolution probability on BitMEX, real versus the same pseudo. | Not a resolution rate and not BitMEX. |
| #365 | Minutes unresolved after the first touch, about 25 fewer than pseudo. | Not an input and not combined with this estimand. |
| #367 | Unsigned executed notional inside the zone, null after endpoint and cross-perp. | Not a condition. Volume is not read. |

Atlas placement for the closeout, after the one run, is `PRICE_STRUCTURE.levels` × `CANDLES`. It is not placed on `VOLATILITY_STATE.compression`, `VOLATILITY_STATE.regime_transition`, or `VOLATILITY_STATE.range_forecast`.

`BLOCKED_REOPENING_KEY_LEVEL_RANGE = false`.

`BLOCKED_REOPENING_VOLATILITY_TRANSITION_CELL = false`.

Novelty passes. The design is not altered to avoid a stop, because the stop does not apply.

## Data and population

`CORE_BTC_BINANCE_V0` only. Binance USD-M BTCUSDT 5m closes. Warm-up before February is the existing January 2020 history already inside that surface. No 2025, no 2026, no E1. No volume, trades, open interest, taker, spot, Bybit, OKX, book, or liquidations in the estimand.

Event window: `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`.

Exact #352 structural first touches. `touch_number = 1` only. Kinds PDH, PDL, PWH, PWL, PMH, PML. Same lifetime, merge, zone, approach side, touch bar, and half-rotation pseudo. No new level type. No random level, no time shuffle, no new placebo grid.

`T` is the open time of parent touch bar `j`.

## Windows and formulas

The touch can occur anywhere inside bar `j`. Counting the travel into the level as post-touch volatility would make a real touch look volatile by construction. Bar `j` is excluded from both windows. This rule is frozen.

Return: `r_k = log(close_k / close_{k-1})`.

`RV_PRE60 = sqrt(mean(r_k^2))` on the 12 returns assigned to bars `j-12 .. j-1`. Those returns use closes `j-13 .. j-1`. They are known by `T`.

`RV_POST60 = sqrt(mean(r_k^2))` on the 12 returns assigned to bars `j+1 .. j+12`. The first of them is `log(close_{j+1} / close_j)`. The touch-bar return `log(close_j / close_{j-1})` is in neither window.

No demeaning. No annualization. No other horizon. 15m, 30m, 120m, and 240m are not estimated and are not chosen after the fact.

A primary event needs every required close finite and strictly positive. No forward fill, no nearest bar, no partial 60m window. If either RV is non-finite or `<= 0`, the event is unusable. No epsilon is added. Zero-RV incidence is counted in the official run, not in this census.

`VOL_TRANSITION_60 = log(RV_POST60 / RV_PRE60)`.

On source episodes where both arms are usable:

`PAIR_DELTA_i = VOL_TRANSITION_REAL_i - VOL_TRANSITION_PSEUDO_i`

`DELTA_TRANSITION = mean(PAIR_DELTA_i)`

Multiplicative reading: `100 * (exp(DELTA_TRANSITION) - 1)` percent. That reading is not a probability.

Positive means the structural touch has a stronger expansion, or a weaker contraction, than its pseudo. Negative means the opposite. Both are meaningful. Inference is two-sided. No direction is imposed.

## Practical scale and inference

Practical magnitude is a 10% difference in the pre→post RV multiplier: `abs(DELTA_TRANSITION) >= log(1.10)`. It is not lowered after the result. No stricter governing bar applies to this difference-in-change; the DH1 3 pp bar and the DH3 range bar are for other estimands.

Paired ISO-week block bootstrap. The atomic unit is the real/pseudo pair. The block key is the ISO week of the real structural touch. `B = 2000`. Seed `20261024`. Each draw resamples weeks, moves both arms together, and recomputes the mean pair delta. 95% percentile interval. If valid draws are below 90% of 2000, the interval is withheld.

Two-sided p is the Wald tail from the bootstrap standard error: `se = std(ddof=1)` of the valid bootstrap means, `p = erfc(|point/se| / sqrt(2))`. One primary hypothesis. No q-value.

There is no second pseudo-specificity stage. The pseudo is already inside the primary estimand. There is no adjusted sensitivity. The within-event ratio is the comparison. No pre-RV tercile, decile, or compression split is computed, even as a descriptive subgroup.

## Information gate

Before any transition is read, the path-complete census must have at least 800 matched pairs with every required bar present, at least 150 ISO-week clusters, and at least 4 calendar years with at least 100 pairs. The owner text's `"«="` marks are frozen as `>=`, the same eligibility direction as the rest of this chain. A less-than reading would invert the gate.

If the official run then finds fewer than 800 pairs with both RV values finite and positive, or the usable week or year support fails the same counts, or the bootstrap interval is withheld, the route is `VOLATILITY_TRANSITION_INFORMATION_INSUFFICIENT`.

## Stability

Years 2020–2024, on the usable pairs. An eligible year has at least 100 pairs.

- Five eligible years: at least 4 of 5 share the pooled sign.
- Four: at least 3 of 4 share it, and every opposite year has absolute log effect strictly below `log(1.10)`.
- Three: all three share it.
- Fewer: stability fails.

Leave-one-year-out runs only if the full primary clears both the 10% magnitude and an interval that excludes 0. Every estimable leave-one-year-out point (remaining N at least 100) must keep the pooled sign. No leave-one-year-out significance requirement. These are point refits.

DAY, WEEK, and MONTH are reported. An eligible family has at least 50 pairs. The candidate fails a material family contradiction only when DAY and WEEK have opposite signs and both absolute effects are at least `log(1.10)`. MONTH is diagnostic. No family-specific candidate.

Resistance and support use the same material rule with at least 100 pairs each. No side-specific candidate.

## Candidate

`LEVEL_VOLATILITY_TRANSITION_CANDIDATE` only if all of these hold: practical magnitude, interval excludes 0, year stability, leave-one-year-out sign, no material DAY/WEEK contradiction, no material side contradiction, usable support passes the information gate, no partial-window or filled-close artifact, and novelty passed.

Routes:

- full conjunction: `LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT`
- magnitude and interval pass, stability does not: `STRUCTURE_PRESENT_BUT_UNSTABLE`
- otherwise, with adequate support: `NO_INCREMENTAL_LEVEL_VOLATILITY_TRANSITION`
- support fails: `VOLATILITY_TRANSITION_INFORMATION_INSUFFICIENT`
- the two blocked routes above, neither of which applies

Claim ceiling: `L2 / DISCOVERY_ONLY`. Allowed wording is historical: realized volatility changed more or less across a structural first touch than across its matched pseudo-price touch, with the post/pre multiplier differing by about X%. Not allowed: a statement that volatility will expand now, a current probability, a current expected RV, a trade direction, a breakout recommendation, or a claim that the level causes volatility. No L3. No L4.

No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings registry, or deploy change. No volatility badge, confirmation state, or alert.

Pre-RV balance (means, medians, and the paired log difference of `RV_PRE60`) is reported with the result. It is not a covariate and not a reason to rematch.

`#365` and `#367` stay separate. No joint model.

## Outcome-blind census

Computed by `scripts/research/level_volatility_transition_discovery_v1/preflight.py` before any `RV_POST60`.

- Structural episodes: 4076
- Real legitimate first touches: 1919
- Pseudo legitimate first touches: 1962
- Matched pairs: 1231
- Path-complete pairs: 1231
- ISO weeks: 254
- Years: 2020 = 242, 2021 = 334, 2022 = 258, 2023 = 181, 2024 = 216. Five eligible years.
- Family: DAY 1071, WEEK 138, MONTH 22
- Side: resistance 690, support 541
- Incomplete 4h: 0 real, 0 pseudo
- `pre_outcome_gate_pass = true`

Zero-RV counts are not in this census. They require return magnitudes.

## What this unit does not do

No compression subgroup. No alternative horizon. No 4h range, 4h RV, corridor, or range percentile. No adjusted regression. No second run. No BitMEX replication. No candidate selection across the eight units. No Level Engine build. After the result, `LEVEL_ENGINE_DISCOVERY_8_OF_8_COMPLETE = YES` and the sequence stops. The next phase needs a separate owner go: discovery synthesis, then candidate selection, then confirmation design.
