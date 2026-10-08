# LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1 — design

Mode: `CONFIRMATION`.

Surface evidence class: `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`.

Not `PRISTINE_CONFIRMATION`. The exact RV claim has not been read on this surface. The neighboring 4h high/low barrier path was read by #357.

This note is committed before any BitMEX `RV_POST`, transition, or pair delta. The census below is path availability only.

Parent discovery: `LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1`, design `54338b7faab9598152e2fa1270d2fb51a4beed18`, result HEAD `fb6598aa62fc9b47cec2e9095959aa98182f0407`. Synthesis parent `e455b13a5205e79c624065125a780150c93fb60a`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.

Governing exposure rule: `docs/research/EXPOSURE_WEIGHTING_DECISION_V1.md`.

## Claim carried over unchanged

`DELTA_TRANSITION` is the mean of `log(RV_POST60 / RV_PRE60)` on the real first touch minus the same quantity on its matched half-rotation pseudo touch.

`RV = sqrt(mean(r^2))` with `r_k = log(close_k / close_{k-1})`. No demean, no annualization, no epsilon. Touch bar `j` is in neither window. Pre returns are `j-12..j-1`. Post returns are `j+1..j+12`. The first post return is `log(close_{j+1} / close_j)`.

Practical bar: `log(1.10) = 0.09531017980432493`. It is not lowered. The predeclared sign is positive. A negative result is reported in full and is not redefined as an absolute effect.

No inverse-contract adjustment. Closes only. No volume, funding, taker side, trade count, or spread.

## Events

The event constructor is the #357 BitMEX constructor: `PDH/PDL/PWH/PWL/PMH/PML`, first touch only, the parent zone and lifetime, support/resistance side, and the deterministic half-rotation pseudo. Event window `[2017-09-01T00:00:00Z, 2020-01-01T00:00:00Z)`. August 2017 is warm-up only.

`window_ok_48` is the #357 availability flag for a complete 4h bar span. It is not a BREAK, REJECT, or NEITHER label. Those labels do not enter eligibility, the model, or any subgroup. First-hit time, RMUT, and hazard are not computed.

A pair is usable only when both arms have finite positive closes for the 12 pre returns, the touch close, and the 12 post returns, and all four RV values are finite and strictly positive. No forward fill.

## Surface

`DH1_BITMEX_XBTUSD_TRADES_5M_V0`. Canonical SHA256 `df3c32922e95bdca80fcf0fa695ec2c8f29455cf8c1ab930277e92c994b4995f`. Days 2017-08-01..2019-12-31. No new download.

`EXACT_CLAIM_PREVIOUSLY_READ = false`.

`NEIGHBORING_POST_TOUCH_PATH_PREVIOUSLY_READ = true`.

`SURFACE_PRISTINE = false`.

`REPLICATION_ALLOWED_BY_EXPOSURE_WEIGHTING_DECISION_V1 = true`.

## Outcome-blind census

Structural episodes 1981. Real legitimate first touches 890. Pseudo legitimate 891. Matched legitimate pairs 558. Path-complete pairs 554. ISO weeks 120.

Epochs, path-complete: 2017H2 100, 2018 250, 2019 204. All three are at or above the #357 epoch minimum of 30 pairs.

Families: DAY 483, WEEK 62, MONTH 9. Sides: resistance 269, support 285.

Four matched pairs fail the 60m close path. They are not dropped because of a resolution label.

## Information gate

Planning uses the published #368 week-bootstrap SE `0.020082572381346548` at 254 weeks, scaled by `sqrt(254 / target weeks)`. It does not use a BitMEX transition.

At 120 weeks the planning SE is 0.02922 and the 95% half-width is 0.05727, below `log(1.10)`. The 80% MDE is 0.08186. Gate: `REPLICATION_INFORMATION_ADEQUATE`. The outcome read is allowed. The Binance N=800 gate is not copied.

## Inference

Paired ISO-week bootstrap. The pair is atomic. The block is the ISO week of the real BitMEX touch. B=2000. Seed `20261025`, chosen before the outcome read. 95% percentile interval. Wald p from the bootstrap SE, the same function as #368.

Leave-one-epoch-out runs only if the full sample is positive, at least `log(1.10)`, and the interval excludes 0. Every estimable omit (retained N at least 30) must stay positive. No separate significance test.

Epoch stability for full support: all three epochs have N at least 30 and a positive point. Family and side use the #368 material-contradiction rule (DAY and WEEK, N at least 50; both sides, N at least 100; opposite signs kill only when both absolute effects clear `log(1.10)`). MONTH is reported and is not required. No family winner and no side winner.

## Routes, frozen now

- `REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION` with evidence label `REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE`: positive, at least `log(1.10)`, interval excludes 0, epoch rule, leave-one-epoch-out, no material family or side contradiction, no artifact.
- `REPLICATION_POSITIVE_BELOW_PRACTICAL_BAR`: positive, interval excludes 0, point below `log(1.10)`.
- `REPLICATION_POSITIVE_UNSTABLE`: the practical bar and the interval clear, and a frozen stability clause fails.
- `REPLICATION_INCONCLUSIVE`: the interval includes 0. The note says whether that interval still contains `log(1.10)` and the discovery point `0.106803`.
- `REPLICATION_CONTRADICTS_DISCOVERY`: point at or below 0 and the interval excludes 0.
- `REPLICATION_INFORMATION_LIMITED`: the planning gate fails, or the interval cannot be formed.

Claim ceiling L2. Not L3. Not a current probability. `INDEPENDENCE_FROM_RESOLUTION_CLOCK = UNRESOLVED` even if the route supports the transition.

No product change. No prospective collection in this unit. No #363 run.
