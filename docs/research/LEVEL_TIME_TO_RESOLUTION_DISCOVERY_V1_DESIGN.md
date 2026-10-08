# LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any barrier-hit time, survival curve, or resolved-by-checkpoint count is computed. A null is a complete result. The unit does not create ACTIVE, AGING, STALE, a countdown, a push rule, or a confidence decay. It does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment. It does not start a false-break label, an acceptance rule, a 30-minute threshold, a live hazard, or a product timer.

## Question

The previous level units asked what is associated with BREAK versus REJECT. This unit asks whether a structural first touch has its own resolution clock.

The primary question is whether a real first touch of a pre-known structural level spends less, or more, unresolved time inside the original 4h horizon than its matched pseudo-price touch. The descriptive questions are how the conditional resolution rate changes across predeclared intervals, and whether BREAK and REJECT, as competing first events, have different observed clocks. None of those descriptive questions becomes a second primary after the rates are seen.

A shorter unresolved time means the event stops being unresolved sooner inside this horizon. It does not mean the level caused the barrier, and it does not mean the level expires after a fixed number of minutes.

## Novelty audit

Read before any resolution time: #352, #357, #361, generator card `GV0R01-C024`, the Atlas row `PRICE_STRUCTURE.levels`, and the Atlas row `PRICE_STRUCTURE.path_shape`.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| #352 touch degradation | Touch ordinal 1 / 2 / 3+ and the 4h BREAK-first rate. | This unit keeps touch 1 only and does not estimate a direction rate. The object is the time until the first barrier interaction. |
| #357 resolution confirmation | Whether the first touch resolves to either barrier inside 4h more often than the pseudo touch. The estimand is a probability, on the 2017–2019 BitMEX surface. | This unit's estimand is the restricted mean unresolved time on the Binance discovery surface. A higher resolution rate is not the same number as a shorter mean unresolved time. |
| #361 post-touch reaction | Features on events still unresolved at T+15m, and the association of end position with later BREAK. About 29% resolved before T+15m on that later window. | A count of early resolutions can reappear here as one descriptive checkpoint. It is not the claim. The claim is the paired 4h unresolved-time distribution. |
| `GV0R01-C024` | Round-number bands, resting depth, time to a ±0.2% exit, capped at 6h. Linked as a neighbor of `GV0R01-C017` (`BLOCKED_METHOD` on `PRICE_STRUCTURE.levels` × `CANDLES`). | This population is the exact #352 structural set, not round numbers. There is no order book and no ±0.2% exit. The barrier is the frozen BREAK or REJECT distance. |
| `PRICE_STRUCTURE.path_shape` | Path-shape cards, including blocked generator cards, not this event clock. | The row stays `PRICE_STRUCTURE.levels`. The column is `CANDLES`. |

`BLOCKED_REOPENING_TIME_TO_RESOLUTION_CELL` does not apply. Reopen key: `NEW_MECHANISM` relative to the touch-ordinal rate, the 4h resolution probability, the post-touch feature slope, and the round-number traversal card. The taxonomy is not edited.

## Data and events

Price only, `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. No open interest, taker flow, spot, other venue, book, or liquidation series.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`, the parent discovery boundary. January 2020 remains warm-up. No 2025, 2026, or E1 bar is requested.

Reuse #352 first touches of PDH, PDL, PWH, PWL, PMH, PML, including zone, orientation, X, BREAK, REJECT, NEITHER, and AMBIGUOUS. Touch 1 only. The pseudo touch is the #352 half-rotation: one control episode per real episode, its own touch time, its own barriers, the same 4h horizon. The pseudo path is not built from the real resolution time.

## Clock

T is the open of touch bar j. Bar j is not a resolution, matching #352. The scan is j+1 through j+48.

If the first future bar that reaches a barrier is j+k, the observed time is `5 * k` minutes. That is the 5-minute bucket in which the hit is visible. No intra-bar second is claimed.

A future bar that reaches both barriers is AMBIGUOUS at that same bucket. For the primary any-resolution clock it counts as resolved, because the event stopped being unresolved. For the BREAK and REJECT descriptions it is excluded from both observed-time lists and enters the cumulative incidence only as a competing event.

If neither barrier is reached on j+1..j+48, the row is right-censored at 240 minutes. The observed event time is null. 240 is not written down as a slow resolution.

A non-finite bar is not a hit and is not filled. The parent presence rule still applies: a window with fewer than 90% finite bars is unusable and the pair is dropped. That drop is a data exclusion, not a new threshold.

## Estimand

Primary event: first BREAK, REJECT, or AMBIGUOUS interaction.

`RMUT_240` is the area under the Kaplan–Meier curve `P(still unresolved at t)` from 0 to 240 minutes. It is the restricted mean unresolved time. It does not assume proportional hazards. No Cox model is fit.

`Δ_RMUT = RMUT_real − RMUT_pseudo` on the paired sample. A negative value means the real touches spend less time unresolved inside the horizon.

The hypothesis written in advance is that the real structural touch has the lower RMUT. The interval is two-sided. A material difference in either direction can meet the magnitude rule. The sign is reported, not imposed.

Practical scale: 15 minutes. It is three native bars. It is not lowered after the result.

Kaplan–Meier median and quartiles are descriptive. So are the predeclared checkpoints 15, 30, 60, 120, and 240 minutes, reported as `P(unresolved at t)` and `P(resolved by t)` for real and for pseudo. No checkpoint is promoted.

Conditional resolution rates, descriptive only, on (0, 15], (15, 30], (30, 60], (60, 120], and (120, 240]: events in the interval divided by the number still unresolved at the left edge. The best interval is not searched. A front-loaded gap, if one appears, is described and is not turned into an ACTIVE window.

BREAK and REJECT times are competing first events. There is no Kaplan–Meier of BREAK that censors REJECT as if it were independent. The directional report is the observed-time quartiles among rows whose first event is that kind, plus the Aalen–Johansen cumulative incidence at the same checkpoints. Neither can create a directional candidate.

No predictor is tested. End position, cross-venue move, spot, open interest, and flow stay out of this unit.

## Sample, bootstrap, stability

A primary pair requires a legitimate real first touch and a legitimate pseudo first touch, each with a complete 4h path under the parent rule, inside the event window. The real-touch week is the cluster. Real and pseudo rows of one episode are resampled together. Draws: 2000. Seed: 20261021. The 95% interval is the percentile interval, and it is withheld if fewer than 90% of draws return a delta.

`LEVEL_RESOLUTION_CLOCK_CANDIDATE` requires all of:

1. absolute delta at least 15 minutes;
2. the 95% interval excludes 0;
3. at least 4 of 5 eligible years share the full-sample sign when five years are eligible; four eligible years need 3; three eligible years need all three; fewer than three fails;
4. leave-one-year-out keeps the sign on every omit with remaining N at least 30;
5. DAY and WEEK are not both estimable, opposite in sign, and both at least 15 minutes in absolute value;
6. resistance and support are not both estimable under that same strong-opposite rule;
7. no unusable clock in the paired sample;
8. at least 400 matched pairs.

An eligible slice has N at least 30 and a finite delta. MONTH is reported and is not part of the family contradiction. A small opposite point, under 15 minutes, is not a strong contradiction.

The outcome-blind gate is 400 matched pairs and no touch year outside 2020–2024. Below the gate, resolution times are not read and the route is `INFORMATION_LIMITED`.

After outcomes, a material interval that excludes 0 but fails stability is `STRUCTURE_PRESENT_BUT_UNSTABLE`. A sample under 200, a withheld interval, or an interval wider than 60 minutes is `INFORMATION_LIMITED`, except when the interval already excludes 0 and the point clears 15 minutes: that case is a candidate or an unstable structure, not an information failure. Otherwise the route is `GENERIC_OR_NO_RESOLUTION_CLOCK_DIFFERENCE`.

## Ceiling

L2 / discovery only. No current probability. No current expected minutes. No trading instruction. No sentence of the form "the level expires after N minutes." `PRODUCT_INTEGRATION_CANDIDATE = NO`. `SUCCESSOR_CANDIDATE` stays none.

One official evaluator run. A second invocation returns `REFUSING_RERUN`.

## Outcome-blind census

Filled from `LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1_PREFLIGHT.json` in this same commit, before any resolution time. `outcomes_read` is false. `resolution_times_read` is false. No survival curve and no resolved-by-15 count is in that file.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`. Structural episodes 4076. Real legitimate first touches 1919. Outside the window 33. No touch 2124. Incomplete 4h paths 0. Unknown side 0. Unusable X 0.

Pseudo legitimate first touches 1962. No control 0. Pseudo no-touch 2086. Pseudo outside the window 28. Pseudo incomplete 4h paths 0.

Matched pairs, both legitimate with a complete 4h path: 1231. Weeks 254. That is above the gate of 400. Years, by the real touch: 242 / 334 / 258 / 181 / 216. No year outside 2020–2024. Family: DAY 1071, WEEK 138, MONTH 22. MONTH is below the slice minimum of 30 and stays descriptive. Side: resistance 690, support 541. Gate pass.
