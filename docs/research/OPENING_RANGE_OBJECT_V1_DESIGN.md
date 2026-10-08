# OPENING_RANGE_OBJECT_V1 — design note

**Amendment pointer.** The sections below are the original pre-outcome freeze, commit `3be350eb`, file SHA256 `7e46d9f5081a4b1c6e3246ff7e2172e96a0c14eba900eefd84731147630250c8`. They are not rewritten. Amendment A1 (`docs/research/OPENING_RANGE_OBJECT_V1_AMENDMENT_A1.md`) is the authority for clock cells, naming, touch-time handling, the observable map, and routes. At the time A1 was written, `outcome_read` was still false and no resolution label was known.

**Status.** Design, committed before any post-interaction resolution label. The support census counts formations and first-interaction existence only. It does not score extension, reentry, excursion, time outside, or realized volatility.

**Unit.** `OPENING_RANGE_OBJECT_V1`. Family `OPENING_RANGE_V1`. This is a new line. It is not a Level Engine unit and it does not add a level kind.

**Mode.** `DISCOVERY` under `docs/research/DISCOVERY_FIRST_RESEARCH_DECISION_V1.md`. No pre-asserted sign.

**Tracks.** `STRUCTURE` + `PRODUCT_EVIDENCE`. Not `EDGE`.

**Claim ceiling.** L2 historical evidence under `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md`. A historical frequency against a baseline, with N and uncertainty, is the strongest sentence this unit can later support. No L3 current probability. No L4. No direct trade call.

**Source main.** `03ad8ef3a3434b4426154aab2af6b651c9807de8`.

**Code.** `scripts/research/opening_range_object_v1/`. Constants in `constants.py` are the freeze. There is no outcome module.

## 1. Question

Does a price range that is formed in a predeclared clock hour, frozen at the end of that hour, and then interacted with for the first time, organize the next 4h differently from a same-clock band built from another day's formation geometry?

The question is whether the printed bounds are a market object. It is not whether an opening-range breakout continues, and it is not whether volatility is higher after midnight.

## 2. Novelty

The exact estimand has not been read.

Neighbors, and why this is not a rescore of them:

- **DH3-V1 `SESSION_EXTREME`.** First touch of the last completed Asia/EU/US session high or low within 24h, versus two random levels at distances drawn from the real distance distribution, endpoint `LEVEL_HOLD_4H`. Result about −0.39 pp. Closed `NO_STRUCTURE`. Reopen only as a new mechanism or a new surface. This unit's object is the high and low of one completed formation hour, frozen before any later interaction, compared with another day's log-offset geometry placed on today's decision price. It is not a running session extreme and not a distance-matched random level.
- **DH3-V2 `KEY_LEVEL_RANGE`.** First touch of prior-day, prior-week, prior-month, or POC levels versus random levels, next 4h log range. Not an opening range.
- **DH3-V3 `RETEST`.** Second same-UTC-day touch of PDH/PDL. Not a formation window.
- **Level Engine (#352–#368).** Prior completed period extremes (PDH/PDL/PWH/PWL/PMH/PML). The price is known before the active period. That is the pattern this design follows (PIT-safe, known before interaction, one lifecycle). The prices themselves are not an opening range. This unit does not import those episodes, those touch labels, or those outcomes.
- **Family J / `CALENDAR.sessions`.** Participation-clock mechanisms are closed. DH1-X4 treated time of day as a nuisance, not a mechanism. R03-C2 compared the Monday 09:30–10:30 America/New_York hour with the same hour on Tuesday–Thursday. R03-C4 did the same for the Friday US close. G01-X8 and G01-X3 closed because a UTC-hour profile does not identify an institutional clock. A session opening range (Asia/Europe/US) would reopen that family and would be identified with the time-of-day effect this design exists to separate.

Reopen key relative to DH3-V1 and to the participation-clock row: `NEW_MECHANISM`. Row `PRICE_STRUCTURE.levels` × column `CANDLES`, because the object is a frozen price extreme. It is not placed on `CALENDAR.sessions`.

`EXACT_CLAIM_PREVIOUSLY_READ = false`. `NEIGHBORING_PATH_PREVIOUSLY_READ = true` (DH3-V1 4h hold after session-extreme touches; Level Engine 4h barrier path, resolution clock, and 60m RV around structural first touches; R03 hour-range at the US cash open). Surface class `DISCOVERY_ON_EXPOSED_SURFACE`. Not `PRISTINE_CONFIRMATION`. Not a confirmation. Not a replication of #368.

## 3. Why the canonical object is the first UTC hour

One object. The duration is not a grid.

**Anchor.** 00:00 UTC. The first formation bar opens at 00:00. The decision time T is 01:00 UTC, the open of the first bar after the formation hour.

**Duration.** 12 complete 5m bars, `[00:00, 01:00)`. This is the first clock hour on the research grid. It is not chosen because a trading desk uses a 60-minute opening range. A 15/30/45/90/120-minute scan is not part of this unit. `FORMATION_BARS = 12` is the only formation length.

**Why not a session anchor.** US, Europe, and Asia opens move with daylight-saving time or, where they do not, collapse into a generic UTC-hour profile. That is the confound the control has to avoid, and it is already why the participation-clock row is closed. The UTC midnight hour has no special economic claim. It does not need one. The contrast holds the clock fixed, so the anchor is a deterministic label, not a theory of participation.

**Noon veto.** The same constructor at 12:00 UTC, formation `[12:00, 13:00)`, decision time 13:00 UTC. One predeclared negative control, maximally separated from midnight on the hour grid. It is not a second candidate. If both cells later meet the reading rule, the finding is a frozen one-hour range, and the word "opening" is not used. If only the noon cell meets it, the opening object fails, and noon is not adopted. No other hour is added after the census or after a later outcome.

Initial Balance, as a longer window, is the same object with a different duration. It is not a separate V1.

## 4. Object

For a cell whose formation starts at offset `H` bars after UTC midnight:

- Formation bars are the 12 bars `[H, H+12)`.
- `OR_HIGH` is the maximum high. `OR_LOW` is the minimum low. All 12 highs, lows, and closes must be finite, and each bar's high must be at least its low. A missing bar is an incomplete formation. Nothing is filled.
- `P0` is the close of the last formation bar (00:55 for the primary cell, 12:55 for the veto).
- Usable geometry requires `OR_HIGH > OR_LOW` and `OR_LOW < P0 < OR_HIGH`. A flat hour, or a decision close sitting on a bound, is counted and excluded. Log offsets `u = log(OR_HIGH / P0)` and `d = log(P0 / OR_LOW)` are then both positive.
- The bounds do not move after T.

**Lifespan.** The object is active for the next 276 bars (23 hours) and dies when the next object of the same cell starts. The primary object dies at the next 00:00. The noon object dies at the next 12:00. There is one object per cell per day. Repeat touches are not new events. The primary object does not overlap the next primary object. The noon object overlaps the next primary object's life; the two cells are never pooled.

A lifespan that the legal panel truncates (the noon object on 2024-12-31 needs bars after 2025-01-01 00:00, which are not read) is counted as truncated. An interaction is outcome-eligible only when its 4h window lies entirely inside the panel and inside the lifespan. No 2025 bar is requested to finish it.

## 5. First interaction

A touch is a wick, not a close-cross. On an active bar, high ≥ `OR_HIGH` meets the upper bound and low ≤ `OR_LOW` meets the lower bound.

- The touch bar is the first active bar that meets either bound. Bars inside the formation hour are not interactions. The bounds are still being formed there.
- A touch on the first active bar is a valid immediate interaction. It is counted and kept. The close that ends the formation is inside the range by the usable-geometry rule; the next bar may gap onto a bound.
- The same bar meeting both bounds is `ambiguous`. It is counted and excluded from the side-specific and paired outcome support.
- Later touches of the same object are not events.
- A non-finite bar is not a touch and is not filled. The scan continues.
- The 4h outcome window is the 48 bars strictly after the touch bar. The touch bar is not part of the window. The window is available only when all 48 bars are finite and the last of them still belongs to the lifespan. A touch in the last 4h of the life is an interaction and is not outcome-eligible. Availability is a count. It is not a resolution label.

## 6. Outcome family (frozen, not computed here)

One primary estimand. No feature list. The only contrast is the printed range versus its pseudo range.

Among paired days on which both the printed range and the pseudo range have an unambiguous first interaction with a complete 4h window:

`Y = 1` if any bar in the 48-bar window meets either barrier below, including a bar that meets both. `Y = 0` if the window is complete and neither barrier is met.

Barriers, both scaled by the frozen width `W = OR_HIGH − OR_LOW`. The fraction is `EXTENSION_FRACTION = 0.5`, one value, not a grid. The pseudo arm uses the pseudo bounds and the pseudo width.

- Upper interaction: extension if high ≥ `OR_HIGH + 0.5 W`. Reentry if low ≤ `(OR_HIGH + OR_LOW) / 2`.
- Lower interaction: extension if low ≤ `OR_LOW − 0.5 W`. Reentry if high ≥ the midpoint.

Primary estimand: the paired mean of `Y_real − Y_pseudo`. No required sign.

Companion, which cannot replace a failed primary: among events with `Y = 1` and a unique first barrier, the paired difference in the share whose first barrier was the extension. A bar that meets both barriers is `Y = 1` for the primary and is dropped from the companion. The companion is a decomposition, not a second search.

Not in this family: realized-volatility transition, time spent outside, a traverse rate as its own selected endpoint, excursion magnitude, a 15/30/120/240-minute horizon, and any Level Engine `BREAK` / `REJECT` label.

**Reading rule for a later outcome run, frozen now and not applied.** Report the estimate, the 95% interval, N, and weeks for both cells.

- `OPENING_RANGE_RESOLUTION_DIFFERENCE_PRESENT` only if the primary point has absolute value at least 0.03, its interval excludes 0, and the noon cell does not also meet that same pair of conditions.
- `FROZEN_HOUR_RANGE_NOT_OPENING_SPECIFIC` if both cells meet them.
- `OPENING_OBJECT_NOT_SUPPORTED` if only the noon cell meets them. Noon is not adopted.
- `NO_OPENING_RANGE_RESOLUTION_DIFFERENCE` if the primary interval includes 0 or the primary point is inside ±0.03, and the noon cell does not uniquely meet the rule.
- `VETO_INFORMATION_LIMITED` if the primary cell is information-adequate and the noon cell is not. The primary estimate may be reported as a frozen-hour result. The word "opening" is not used.
- `INFORMATION_LIMITED_STOP_BEFORE_OUTCOME` if the primary cell fails the information floor in §9. No Y is computed.

Practical scale for that reading rule: 3 percentage points, the project's predeclared rate-difference scale. It is not a power target. Under the conservative planning variance in §9, this surface is powered for a gap on the order of the level-foundation 8pp benchmark, and a true 3pp gap can remain inside the interval. That limitation is reported with any later estimate. It is not a reason to lower 0.03 after seeing Y, and it is not a reason to switch the estimand.

Inference for that later run, frozen now and not executed: paired ISO-week block bootstrap, the pair is atomic, the block is the ISO week of the real object's UTC date, B = 2000, seed `20261027`. Percentile 95% interval. No scipy. No FDR. The noon cell is a veto, not a second test that can be selected.

Stability slices for that later run, not computed now: calendar year (eligible at ≥ 30 paired days) and side (eligible at ≥ 100). A side or a year is not a winner. No volatility tercile and no preceding-return split.

Search grid: two cells, one primary estimand, one companion that cannot rescue the primary, one formation length, one extension fraction, one horizon. Adding a duration, an anchor, a barrier fraction, or a horizon after Y is a new unit.

What would justify a successor: a separate confirmation design on a time-disjoint surface, only after this unit's later outcome route is `OPENING_RANGE_RESOLUTION_DIFFERENCE_PRESENT`. Not started. Not 2025/2026. Not a BitMEX run inside this unit.

## 7. Control

Weekday half-rotation of log offsets. Same decision clock, same subsequent path, another day's formation shape.

Inside each cell, group usable days by UTC weekday. Order each group by date. Shift is `n // 2`. The partner is the first later slot in that rotation whose offsets, placed on today's `P0`, do not reproduce today's bounds.

`pseudo_high = P0 × exp(u_partner)`, `pseudo_low = P0 × exp(−d_partner)`.

Collision: both pseudo bounds sit within a relative `1e-9` of the real bounds. Take the next partner. If none remains, the day is unpaired and counted.

This holds time of day, weekday, and the day's future bars fixed. It does not match today's width, today's preceding return, or a volatility tercile. Matching those as well would ask whether two nearly identical bands differ, which is overmatching. Width is part of the object: the printed hour has its own shape, and the control has another day's shape.

The population of the estimand is days on which both bands were actually interacted with, each with a complete 4h window. Days on which only the printed range is touched are counted and are not in the paired mean. The result does not describe them.

The control does not, by itself, prove that midnight is special. The noon cell is the veto for that word.

Not used: the product's random distance-matched levels, `control_episodes` from the level constructor, a seeded shuffle, a same-day width match, or a US-cash-open clock.

## 8. Data and exposure

`CORE_BTC_BINANCE_V0`, Binance USD-M BTCUSDT, 1m klines aggregated to complete 5m bins by the frozen DH1 loader. The census calls `scripts.research.level_touch_degradation_v1.data.load_discovery_bars` only as that loader. It does not build level episodes.

- Events: UTC dates `[2020-01-01, 2025-01-01)`.
- No warm-up month is required. The object is intra-day. An incomplete first day fails the 12-bar rule and is counted as incomplete.
- Nothing at or after 2025-01-01 is requested. The E1-RUN-001 holdout is outside this window and the loader refuses it.

`PRICE_STRUCTURE.levels` on 2020–2024 is already `CONSUMED` for other estimands (DH1-L2, the Level Engine units, the level-race history table). This census is further exposure of a new estimand: formation geometry and first-interaction existence. The resolution estimand is not consumed because it is not computed. Exposure status for this pass is `EXPOSED`, not `CONSUMED`.

2025/2026 is not opened. Product history tables are not the sample. The prospective volatility panel is not the sample.

## 9. Information floor (applied to counts, not to Y)

Planning variance `0.5` is a conservative bound for a paired difference of two Bernoulli outcomes (independent `p = 0.5`, or half the pairs discordant). It is not an estimated variance.

Planning benchmark `0.08` is the scale of the already published level-foundation resolution gap. It is a power reference for "could this surface see an effect of that size", not a predicted opening-range effect.

`Z_95 = 1.959963984540054`, `Z_80 = 0.8416212335729143`.

Minimum paired outcome-eligible days:

`N > 0.5 / (0.08 / (Z_95 + Z_80))²`, which is `N ≥ 614`.

Minimum ISO weeks of those paired days: `100`, the same temporal-spread floor as the touch-degradation reading rule.

`INFORMATION_ADEQUATE_FOR_LATER_OUTCOME` requires both. Otherwise `INFORMATION_LIMITED_STOP_BEFORE_OUTCOME`, and a later outcome run is not authorized by this note.

The legal window has 1827 UTC dates. At N = 1827 the conservative 95% half-width is about 3.24 pp, so a 3pp true effect is not what this surface was powered to separate. The floor of 614 is the 8pp benchmark under the same variance. Eligible N will be smaller than 1827 because of incomplete hours, ambiguous bars, late touches, and the requirement that both arms are touched. The census reports that N. It does not change 614, 100, 0.03, 0.08, the hour, or the control.

At the floor, the conservative half-width is about 5.6 pp. A later interval must be read with that width in view.

## 10. What this pass computes

The census reports, separately for `UTC_00` and `UTC_12`:

- calendar days, incomplete formations, non-positive width, decision close not strictly inside, usable geometry;
- lifespan truncated by the panel;
- no interaction, first interaction, ambiguous, high side, low side, immediate;
- one-sided interactions whose 4h window is incomplete;
- one-sided outcome-eligible real interactions;
- pseudo one-sided outcome-eligible interactions among days that received a partner;
- paired outcome-eligible days, unpaired days, ISO weeks, year counts, weekday counts;
- the planning half-width and the information status.

It does not report a resolution rate, a barrier direction, an excursion, a volatility ratio, or a real-minus-pseudo effect. The two interaction counts are support sizes. Their difference is not an estimand.

`outcome_read` stays false. This artifact does not authorize the outcome run by itself. A later run needs a separate go, and only if the primary information status is adequate. If it is limited, the stop stands.

## 11. What would make a later result uninterpretable

- Choosing the hour or the duration after seeing which one moves.
- Treating a time-of-day volatility difference as a property of the range.
- A control that does not hold the clock fixed.
- Using the noon cell as the object after the primary cell fails.
- Conditioning on Level Engine break or reject labels.
- Matching on today's width, a volatility tercile, and the preceding return in addition to the rotation.
- Reading 2025/2026 or the E1 holdout.
- Pooling these days with Level Engine touches.
- Stating Y as a current probability, an L3 claim, or a trade.
- Changing the information floor, the 3pp reading scale, or the 8pp planning benchmark after seeing the eligible N or after seeing Y.

## 12. Product

No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings-registry, or deploy change. No opening-range badge. The forecast-layer next unit is unchanged. The accruing #368 prospective confirmation is unchanged and is not an input.
