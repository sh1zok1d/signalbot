# OPENING_RANGE_OBJECT_V1 — pre-outcome amendment A1

**Status.** Methodology repair. Written while `outcome_read = false`. No resolution label, extension rate, reentry rate, excursion, traverse, or realized-volatility transition was known. This file does not replace the original design's identity and it does not retune the foundation estimand.

## Provenance

| | |
| --- | --- |
| Original design commit | `3be350eb0f71011928b1c99cc92f37059d631252` |
| Original design SHA256 | `7e46d9f5081a4b1c6e3246ff7e2172e96a0c14eba900eefd84731147630250c8` |
| Original support census | `docs/research/OPENING_RANGE_OBJECT_V1_FEASIBILITY.json` |
| What that census read | formation geometry and first-interaction existence for `UTC_00` and `UTC_12` only |
| What it did not read | Y, barriers after the touch, excursion, volatility |
| `outcome_read` at this amendment | false |
| Y / effect known | none |

The original census, unchanged: `UTC_00` paired days 1719 across 262 ISO weeks; `UTC_12` paired days 1704 across 262 weeks. Both were `INFORMATION_ADEQUATE_FOR_LATER_OUTCOME`. Those counts are support, not an effect.

Why this amendment exists, before any outcome:

1. 00:00 UTC is a Binance funding timestamp, not a neutral opening. `docs/research/MARKET_03_FUNDING_SNAPSHOT.md` records the USD-M BTCUSDT funding cadence as 00:00 / 08:00 / 16:00 UTC only, with no missing 8h slot in the retained snapshot.
2. A real touch and its pseudo touch can fall hours apart, so a later 4h window would mix the object with ordinary intraday timing.
3. One resolution definition cannot be read as "the object has no structure of any kind" if it is null.

The amendment does not add a 24-hour search, a new barrier fraction, or a new horizon.

## Naming

The working object name is `FROZEN_HOUR_RANGE`. The primary cell is `UTC_00`, formation `[00:00, 01:00)`.

`OPENING` is a hypothesis label. It is not a route, not a finding, and not wording a later result may use. No route below sets `opening_wording_allowed`.

## Clock cells

Same constructor as the original freeze: 12 complete 5m bars, frozen high and low, `P0` strictly inside, first wick, 23h life until the next object of the same cell, weekday half-rotation of log offsets, 4h window required only as availability.

| Cell | Formation | Role |
| --- | --- | --- |
| `UTC_00` | `[00:00, 01:00)` | primary. Also a funding timestamp. |
| `UTC_08` | `[08:00, 09:00)` | funding-cadence diagnostic |
| `UTC_12` | `[12:00, 13:00)` | off-cadence diagnostic. Kept from the original design. |
| `UTC_16` | `[16:00, 17:00)` | funding-cadence diagnostic |

These are not four candidates. No other hour is added. A later result does not adopt `UTC_08`, `UTC_12`, or `UTC_16` when `UTC_00` fails. The information floor stays 614 paired days and 100 ISO weeks. It is not lowered after the A1 census.

## Direct contrasts

For the foundation observable only:

`δ_h` = paired mean of `Y_real − Y_pseudo` in cell h.

`δ_00,h` = `δ_00 − δ_h` for h in {08, 12, 16}.

A cell passes when the absolute point is at least 0.03 and its 95% interval excludes 0. A contrast passes on the same scale. No expected sign. A cell that passes while another does not is not, by itself, evidence that the two effects differ.

Inference, frozen and not executed: one ISO-week block bootstrap. Each draw resamples weeks once from the union of weeks and recomputes all four cell means, and the three contrasts, inside that draw. Pair is atomic. B = 2000. Seed `20261027` for this joint draw. Percentile interval. A draw missing either side of a contrast is invalid. If the valid fraction is below 0.9, the clock route is not interpreted.

## Touch-time audit

Outcome-blind quantity: minutes from the decision time T (open of the first active bar) to the first interaction. Already implied by the support census. Not a post-touch outcome.

For each clock cell, on paired outcome-eligible days only, the A1 census reports:

- real and pseudo elapsed-time distributions, bins `<60`, `60–<240`, `240–<720`, `≥720` minutes;
- paired difference `elapsed_real − elapsed_pseudo`, mean and the 25/50/75 percentiles;
- absolute difference, same percentiles;
- share with absolute difference `<60` minutes, share `≥240` minutes, share whose touch bars fall in the same UTC clock hour;
- UTC hour of the real touch and of the pseudo touch.

Material imbalance on the primary cell, predeclared before this census: the share with absolute difference `≥240` minutes is at least 0.25, or the median absolute difference is at least 120 minutes.

Handling, one branch, applied by that rule and not revisited after Y:

- Not material: `PUBLISH_AUDIT_NO_CORRECTION`. Every later result prints the audit. No rematch, no stratification, no added control.
- Material, and the subset with absolute difference `<60` minutes still has at least 614 pairs and 100 ISO weeks: `PUBLISH_AUDIT_PLUS_NEARBY_SENSITIVITY`. The primary estimand is unchanged. One sensitivity repeats the foundation estimand on that nearby subset. The sensitivity cannot replace a null primary and cannot be the only reported cell.
- Material, and the nearby subset misses the floor: `PUBLISH_AUDIT_NEARBY_SENSITIVITY_INFORMATION_LIMITED`. The sensitivity is not computed. The later text states that the object contrast includes a difference in interaction time and does not identify a boundary effect separate from timing.

Touch speed is not matched away. It may be part of the object. The audit measures the confound. It does not delete it.

## Observable map

Bounded, predeclared, all cells reported. No cell is chosen after the outcomes. Clock contrasts are computed for the foundation observable only. The other rows are `UTC_00` only.

| Id | Role | Estimand | Scale |
| --- | --- | --- | --- |
| `FOUNDATION_RESOLUTION` | foundation | paired P(resolve within 4h). Unchanged: extension of `0.5 W` or midpoint reentry, 48 bars after the touch bar | 0.03 |
| `DIRECTION_EXTENSION_FIRST` | same barrier family | paired P(the first barrier is the extension). Unresolved and reentry-first count as 0 | 0.03 |
| `OUTSIDE_OCCUPANCY` | orthogonal | paired mean of the share of the 48 bars that lie entirely outside the frozen range | 0.03 |
| `OUTWARD_EXCURSION` | orthogonal | paired mean of the maximum outward distance beyond the touched side, divided by W | 0.25 W |

Seeds for the later non-joint bootstraps, in this order and not used now: direction `20261028`, outside occupancy `20261029`, excursion `20261030`.

`DIRECTION_EXTENSION_FIRST` shares the foundation barriers. A direction shift can exist when the resolution rate does not, so it is reported. It cannot rename a null foundation into a day-boundary or opening claim.

Excluded, with reasons:

- **Resolution clock.** Level Engine `#365` already estimated restricted mean time to the same style of barrier on structural first touches. On this object that clock is largely a transform of the foundation barriers. It is not a fifth row. A later unit may ask it only after this map has a candidate, under its own design.
- **Volatility transition.** `#368` estimated the paired 60m log realized-volatility ratio on structural first touches and replicated it on BitMEX. Copying that endpoint onto this object now would be that family under a new name. Excluded. Not a claim that volatility cannot move.
- **Traversal as its own endpoint, extra horizons, extra barrier fractions, the other twenty hours.** Not in the map.

A null foundation cell is a null of that question. It does not say the frozen hour range has no structure, and it does not close an observable outside this map. `NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE` means every row that this map actually checks failed on this surface. It does not close a new orthogonal observable that was not in the map.

## Routes

Applied only after a later outcome read. The A1 census does not apply them.

`opening_wording_allowed` is false on every route. `hour_adopted` is null on every route.

1. `UTC_00` foundation information is limited → `INFORMATION_LIMITED`. Y for that failure is not required; the floor is already known if the census says so.
2. `UTC_00` foundation passes, and any of `UTC_08`, `UTC_12`, `UTC_16` is information-limited → `CLOCK_SPECIFICITY_INFORMATION_LIMITED`. The `UTC_00` foundation estimate may be described as a frozen-hour result. Not day-boundary, not funding, not generic, not opening.
3. `UTC_00` passes and the direct contrasts against `UTC_08`, `UTC_16`, and `UTC_12` all pass → `UTC_DAY_BOUNDARY_RANGE_CANDIDATE`. This is specificity to the 00:00 cell. It is not an economic opening mechanism and it is not a funding-causality claim.
4. `UTC_00`, `UTC_08`, and `UTC_16` all pass, neither funding contrast passes, and `UTC_12` also passes with its contrast failing → `GENERIC_FROZEN_HOUR_RANGE_STRUCTURE`.
5. `UTC_00`, `UTC_08`, and `UTC_16` all pass, and neither funding contrast passes, while noon is not similar in that same sense → `FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE`. Shared clock with the funding cadence. Not a claim that funding causes the range.
6. `UTC_00` foundation passes but no pattern above fits, including the case where other cells fail their own tests and the direct contrasts also fail → `INCONCLUSIVE`.
7. `UTC_00` foundation fails, a diagnostic hour passes → `INCONCLUSIVE`. That hour is not adopted.
8. `UTC_00` foundation fails, no diagnostic hour passes, and at least one of direction, occupancy, or excursion passes → `ORTHOGONAL_CANDIDATE_ON_UTC_00`. Clock specificity is not claimed.
9. `UTC_00` foundation fails and every checked diagnostic hour and every other map row fails → `NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE` inside this map and this surface.

Orthogonal candidates are listed. They are not ranked. A clock route does not hide them, and they do not upgrade the route into opening wording.

## Evaluator

`python -m scripts.research.opening_range_object_v1.evaluate` raises `REFUSING_OUTCOME_BEFORE_OWNER_GO`. The joint-bootstrap CLI does the same. Neither loads a market path for Y. Tests use synthetic inputs.

## What a later owner go may run

One outcome read of the four map rows and the three foundation contrasts, under the seeds and scales above, plus the single touch-time sensitivity only if this amendment's handling says the nearby subset clears the floor. Then stop. No new hour, no new horizon, no product change, no 2025/2026, no E1 window.
