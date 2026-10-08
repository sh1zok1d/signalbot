# FROZEN_HOUR_EQUAL_WIDTH_V1 — design note

**Status.** Design only. `outcome_read = false`. No market bar is read by this note. No evaluator is run. A later outcome needs a separate owner go.

**Mode.** `CONFIRMATION` of one predeclared relation, under `docs/research/DISCOVERY_FIRST_RESEARCH_DECISION_V1.md`. The relation was selected from the post-outcome diagnosis of `OPENING_RANGE_OBJECT_V1`. It is not a confirmation of that unit's route, and it is not a rerun of that map.

**Tracks.** `STRUCTURE`. Not `EDGE`. Not a product sentence.

**Claim ceiling.** L2. A historical paired difference, with N and a predeclared interval. Not a current probability. Not L3. Not L4. Not a trade.

**Parent.** `OPENING_RANGE_OBJECT_V1`, one read at `2026-10-08T20:41:03Z`, route `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`, unchanged. Diagnosis `docs/research/FROZEN_HOUR_RANGE_POST_OUTCOME_DIAGNOSIS_V1.md`, `EVIDENCE_UPGRADE = NONE`. The published UTC_00 foundation difference is +9.48 pp. That figure is not evidence that the hour's bounds are a special object. This unit asks what remains after width is held fixed. It does not rehabilitate +9.48 pp, whatever it finds.

## 1. Question and estimand

On a day whose frozen hour has width `W`, does the 4h resolution of that printed range differ from the resolution of another same-weekday's log shape after that shape has been scaled, around today's decision close `P0`, so that its dollar width equals `W`?

Primary estimand, UTC_00 only: the equal-weight paired mean

`δ_00 = mean(Y_real − Y_scaled)`.

UTC_12 uses the same functional, `δ_12`. It is the second cell. It is not a second candidate. It cannot be adopted if UTC_00 does not clear, and it cannot rescue UTC_00.

`Y = 1` when any bar in the 48 bars strictly after the touch bar meets either barrier below, including a bar that meets both. `Y = 0` when the window is complete and neither barrier is met. The touch bar is not in the window.

Barriers use that arm's own bounds and that arm's own achieved width. `EXTENSION_FRACTION = 0.5`, one value.

- Upper touch: extension if high ≥ bound_high + 0.5 W_arm. Reentry if low ≤ the midpoint.
- Lower touch: extension if low ≤ bound_low − 0.5 W_arm. Reentry if high ≥ the midpoint.

No required sign. Extension-first, outside occupancy, excursion, and realized volatility are not endpoints.

## 2. Geometry, relative to P0

The real range is the original object. Twelve complete 5m bars, wick touch, 23h life, one object per cell per UTC date. `P0` is the close of the last formation bar. Usable geometry requires `OR_HIGH > OR_LOW` and `OR_LOW < P0 < OR_HIGH`. Log offsets `u = log(OR_HIGH / P0)` and `d = log(P0 / OR_LOW)` are then both positive. `W_real = OR_HIGH − OR_LOW`. The real bounds do not move after the decision.

The partner is the original weekday half-rotation. Inside a cell, group usable days by UTC weekday, order by date, shift `n // 2`, and walk forward in that rotation. A candidate is placed on today's `P0` only after the scale below. The first candidate that scales and does not collide is the partner. If none remains, the day is unpaired and counted.

Scale. Given the partner's `u > 0`, `d > 0` and today's `W_real > 0`, `P0 > 0`, find the unique `k > 0` such that

`P0 × (exp(k u) − exp(−k d)) = W_real`.

`f(k) = exp(k u) − exp(−k d)` is strictly increasing for `k > 0` because `f'(k) = u exp(k u) + d exp(−k d) > 0`, with `f(0) = 0`. The root is unique. It has no elementary closed form when `u ≠ d`. The solver is frozen:

1. IEEE-754 float64 only.
2. `target = W_real / P0`.
3. `k_lo = 0`, `k_hi = 1`. Double `k_hi` at most 60 times until `f(k_hi) ≥ target`. If it still fails, the candidate is `scale_unbounded` and is skipped.
4. Bisect 80 times. At each step `k_mid = (k_lo + k_hi) / 2`. If `f(k_mid) ≥ target`, set `k_hi = k_mid`, otherwise `k_lo = k_mid`.
5. `k = (k_lo + k_hi) / 2`.
6. `pseudo_high = P0 × exp(k u)`, `pseudo_low = P0 × exp(−k d)`.
7. Accept only if `pseudo_low < P0 < pseudo_high` and `|pseudo_high − pseudo_low − W_real| / W_real ≤ 1e-9`. Otherwise the candidate is `scale_tolerance_failed` and is skipped.

The achieved pseudo width is `pseudo_high − pseudo_low`. Barriers use that achieved width. `W_real` is not substituted in after a failed match.

This `k` multiplies both log offsets, so the partner's asymmetry `(u − d) / (u + d)` is unchanged. Dollar width matches today's width within the tolerance. No other `k`, no grid, and no fit to `Y`.

Collision, judged on the scaled bounds: both bounds sit within a relative `1e-9` of the real bounds, the same `REL_COLLIDE` as the parent. Take the next candidate.

Rejected before any read on this surface, and not available later as a sensitivity: scaling the price distances `(high − P0)` and `(P0 − low)` by one factor. That matches dollar width and changes log asymmetry. The object is defined in log offsets, so that transform is not the control.

## 3. Immediate touches

A touch on the first active bar is a valid interaction. It is counted and kept. The decision close is inside both ranges; the next bar is the first bar that was not used to form them, and it may gap onto a bound.

An immediate touch is not a reason to drop the day, rematch the partner, shrink the range, or delay the touch. Whether that first bar touches depends on the path after the decision. Removing those days would select on that path.

The result also records, as `DESCRIPTIVE_NOT_A_CANDIDATE`, the immediate-touch rate of each arm and the paired mean on the subset where neither arm's first touch is the first active bar. The subset mean is printed only when that subset has at least 30 pairs. It has no interval in the route. It cannot replace `δ_00`.

## 4. Estimator

The point is the equal-weight mean of the pair deltas. A day is one pair.

Uncertainty is a percentile interval from a week-block bootstrap. The block is the ISO week of the real object's UTC date. A draw resamples those weeks with replacement and recomputes the pair-weighted mean: a week drawn `m` times contributes `m` times its sum of deltas and `m` times its pair count. `B = 2000`. Seeds: UTC_00 `20261031`, UTC_12 `20261102`. NumPy Generator, no scipy. The interval is `numpy.quantile` at 0.025 and 0.975 with `method="linear"`. A cell whose valid draws are under 90% of 2000 has no interpretable interval and does not clear.

The two bootstraps are separate. There is no max-T and no Holm. The family has one primary cell.

## 5. What would change our mind

Support is counted before any `Y`. A cell is information-adequate at `N ≥ 614` paired outcome-eligible days and at least 100 ISO weeks of those days. The same floor as the parent. It is not lowered because this window is shorter. If either cell fails, no `Y` is read on either cell, and the route is `INFORMATION_LIMITED_STOP_BEFORE_OUTCOME`.

A cell clears only if its absolute point is at least 0.03 and its interval excludes 0. The 0.03 scale is the parent's rate scale. It is not retuned to the diagnosis's similar-width bin.

- `WIDTH_HELD_DIFFERENCE_PRESENT` if UTC_00 clears. Width does not account for the whole resolution contrast on this surface. This does not restore +9.48 pp and does not adopt an hour.
- `NO_WIDTH_HELD_RESOLUTION_DIFFERENCE` if UTC_00 does not clear. The width-held contrast does not show a resolution difference here. That is compatible with the diagnosis. It is not proof that the parent's delta was only width: the instrument and the era are different.
- UTC_12 is printed beside whichever of those two routes UTC_00 takes. If UTC_00 cleared and UTC_12 did not, the note may say the remainder is not shared with noon on this surface. If both cleared, the note may say the remainder is not specific to midnight among these two cells. If only UTC_12 clears, it is reported and not adopted.

No year, side, or immediate-touch subset is a winner.

## 6. Surface

`DH1_BINANCE_SPOT_BTCUSDT_5M_V0`. Binance spot BTCUSDT official 5m klines. Events: UTC dates `[2017-09-01, 2020-01-01)`. Monthly objects requested: 2017-09 through 2019-12 only. No 2017-08 listing stub. No month from 2020-01 onward. A noon life that runs into 2020-01-01 is truncated and is not filled. Missing bars stay missing. No forward fill. No perpetual bar, no 2025/2026 object, no E1 bar, no product tape.

Calendar length is 852 UTC dates. That is not a market read. Eligible N will be smaller and is unknown until a later support census.

Exposure of this window, checked against `docs/research/atlas/ATLAS_SURFACES_V1.yaml` and the ledger, without opening the files:

- `EXACT_CLAIM_PREVIOUSLY_READ = false`.
- `POST_TOUCH_BARRIER_PATH_PREVIOUSLY_READ = false` on these months. The parent's 4h resolution was read on `CORE_BTC_BINANCE_V0` 2020–2024 perpetual. BitMEX 2017-09..2019-12 has a consumed 4h high/low path and is not used. Spot months 2020-04..2024-12 were consumed by `LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1` and are not used.
- The pin's 2017–2024 span is `EXPOSED` for DH1 outcome-blind counts of spot states at level touches. Those counts are not this estimand and are not a barrier path.
- `DIRECTIONAL_HYPOTHESES_DECISION_V1` names 2017-09..2019-12 spot as DH1 confirmation data. `DH1_RESULT` records that the replication outcome was not read, because discovery had nothing to replicate. The slot is unused. It is not an atlas reservation. This design spends it on a different estimand only if a later go says so.

Reservation check. `reservations:` in `ATLAS_SURFACES_V1.yaml` has one entry, `E1_RUN_001_FINAL_HOLDOUT`, `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`, permit required, holder `E1-RUN-001`. That period does not intersect this window. The spot pin is named on that reservation because the holdout covers every BTC market row in those ten days, not because 2017–2019 spot is held. This design does not request a permit and does not touch the holdout.

Also not used, and not available as a fallback if this window is short: the level-race held-out perpetual history from 2025-01-01, the `#368` prospective perpetual panel from 2026-10-09, product 2025/2026 klines, and `STAGE1_LIVE_KLINES_3VENUE`.

Surface class: `TIME_DISJOINT_OUTCOME_UNREAD`. Not `PRISTINE_CONFIRMATION`. Not the discovery surface.

## 7. Variants

Counted before the read: two cells, one estimand, one scale, one horizon, one barrier fraction, one partner rule. The rejected price-distance scale is recorded and is not a second arm. No UTC_08, UTC_16, or any other hour. No new duration.

## 8. What this note does not do

It does not write an evaluator, open the spot files, count formations, or score `Y`. It does not edit the parent's JSON result. It does not change the route. It does not change a product surface, a forecast, or the `#368` accrual.

Search grid after `Y` is a new unit: another scale, another lag, another hour, another horizon, another barrier fraction, or a read of the discovery surface under this control.
