# LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The question is whether a real first touch of a pre-known structural level spends a different amount of unresolved time, inside the original 4h horizon, than its matched pseudo-price touch. This note does not change the product. It does not say that a level expires after a fixed number of minutes, and it does not state a current expected time.

## Provenance

Design SHA `56b162f07e69f3e8a4b6784e18dc497ea5a7d042`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`. Outcomes read: True. Claim ceiling `L2`.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- confirmation: `c1cd4e0102e700f7860d21a9af0d243c3bc367be`
- post_touch_reaction: `44726ded55c75fefecc6848ab8b76971ead83721`
- cross_venue: `f22100177e2f89a43c6271929aba0d63f7b4552f`
- spot_perp: `7c297997da263e286524fd939e4a536dfa42002c`

## Novelty

The object is the time from a structural first touch until the first future bar reaches the frozen BREAK or REJECT barrier. It is not the #352 touch-ordinal BREAK rate. It is not the #357 4h resolution probability: that estimand is a rate, on the 2017–2019 BitMEX surface, and a higher rate is not the same number as a shorter mean unresolved time. It is not the #361 feature slope. A resolved-by-15 checkpoint can be read off this curve; it is not a new claim and it is not the #361 cohort.

It is not generator card `GV0R01-C024`. That card asked whether resting depth at round-number bands slows traversal to a ±0.2% exit, capped at 6h. This population is PDH, PDL, PWH, PWL, PMH, and PML. There is no order book and no ±0.2% exit. Atlas row `PRICE_STRUCTURE.levels`, column `CANDLES`. Reopen key `NEW_MECHANISM`. `BLOCKED_REOPENING_TIME_TO_RESOLUTION_CELL` does not apply.

## Data and clock

Price only. `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. No open interest, taker flow, spot, other venue, book, or liquidation series.

Event window `[2020-02-01T00:00:00Z, 2025-01-01T00:00:00Z)`. No 2025/2026 object was requested.

T is the open of touch bar j. Bar j is not a resolution. The scan is j+1 through j+48. A hit on bar j+k has observed time `5 * k` minutes. A bar that reaches both barriers is AMBIGUOUS at that bucket and counts as resolved for the any-resolution clock. No hit by j+48 is right-censored at 240 minutes. The observed event time of a censored row is null. A missing bar is not filled.

The pseudo touch is the #352 half-rotation, with its own touch time and its own barriers. Real and pseudo rows of one episode are one bootstrap unit. Seed 20261021. Draws 2000. Cluster is the real-touch week. Practical scale 15 minutes.

## Cohort

Structural episodes 4076. Real legitimate first touches 1919. Pseudo legitimate first touches 1962. Incomplete 4h paths: 0 real, 0 pseudo. Matched pairs 1231. Unusable clocks 0. Primary N = 1231. Weeks 254.

Real first events: BREAK 579, REJECT 539, AMBIGUOUS 6, censored 107.
Pseudo first events: BREAK 467, REJECT 549, AMBIGUOUS 8, censored 207.

## Primary

Restricted mean unresolved time over 240 minutes, Kaplan–Meier, any resolution.

| arm | RMUT_240 | 95% interval |
|---|---:|---|
| real | 64.24 min | 59.65..68.81 |
| pseudo | 89.39 min | 84.48..94.39 |
| real − pseudo | −25.15 min | −31.42..−19.07 |

N=1231. 2000/2000 bootstrap draws. The interval excludes 0. The absolute difference is 25.15 minutes, above the frozen 15-minute scale. A negative difference means the real structural touches spend less time unresolved inside the horizon.

Kaplan–Meier quartiles, the times where survival falls through 0.75, 0.50, and 0.25: real 10 / 30 / 95 minutes. Pseudo 15 / 50 / 160 minutes. The pseudo upper quartile is reached; it is not an imputed censor time.

## Checkpoints

`P(resolved by t)` = 1 − `P(still unresolved at t)`.

| t | real unresolved | real resolved by | pseudo unresolved | pseudo resolved by |
|---:|---:|---:|---:|---:|
| 15m | 0.599 | 0.401 | 0.701 | 0.299 |
| 30m | 0.471 | 0.529 | 0.590 | 0.410 |
| 60m | 0.327 | 0.673 | 0.452 | 0.548 |
| 120m | 0.193 | 0.807 | 0.304 | 0.696 |
| 240m | 0.087 | 0.913 | 0.168 | 0.832 |

The resolved-by gap is about +10.2, +11.9, +12.6, +11.0, and +8.1 percentage points at those five times. The 240-minute gap is a descriptive rate difference on this Binance matched sample. It is not a rescoring of the #357 BitMEX confirmation.

## Conditional intervals

Resolved during the interval, divided by the number still unresolved at the left edge.

| interval | real | pseudo |
|---|---:|---:|
| 0–15m | 494/1231 = 0.401 | 368/1231 = 0.299 |
| 15–30m | 157/737 = 0.213 | 137/863 = 0.159 |
| 30–60m | 178/580 = 0.307 | 169/726 = 0.233 |
| 60–120m | 164/402 = 0.408 | 183/557 = 0.329 |
| 120–240m | 131/238 = 0.550 | 167/374 = 0.447 |

The real conditional rate is higher in every predeclared interval. The gap is not confined to the first 15 or 30 minutes. No interval was chosen after the fact, and no ACTIVE window is defined.

## BREAK and REJECT, descriptive

These are competing first events. REJECT is not censored inside a BREAK survival curve. Quartiles below are observed event times among rows whose first event is that kind. They condition on the kind.

| kind | arm | N | q25 | q50 | q75 |
|---|---|---:|---:|---:|---:|
| BREAK | real | 579 | 5 | 20 | 50 |
| BREAK | pseudo | 467 | 15 | 40 | 102.5 |
| REJECT | real | 539 | 10 | 30 | 82.5 |
| REJECT | pseudo | 549 | 10 | 30 | 80 |

Aalen–Johansen incidence by 240 minutes: real BREAK 0.470, real REJECT 0.438; pseudo BREAK 0.379, pseudo REJECT 0.446. AMBIGUOUS competes and is in neither incidence. This is not a directional candidate. The primary remains any-resolution unresolved time.

## Stability

Years, real-touch year, point Δ_RMUT: 2020 −40.39 (N=242), 2021 −29.84 (N=334), 2022 −7.75 (N=258), 2023 −22.65 (N=181), 2024 −23.70 (N=216). Five eligible years, all five negative. The frozen rule is a sign rule. It passes. The 2022 point is under the 15-minute scale. That fact is reported. It does not rewrite the rule, and it is not a separate year study.

Leave-one-year-out: −21.42, −23.41, −29.76, −25.58, −25.46. All five keep the sign, and each remains beyond 15 minutes in absolute value.

Family: DAY −24.91 (N=1071), WEEK −28.91 (N=138). Same sign, both beyond 15 minutes. MONTH −13.18 (N=22) is below the slice minimum and is descriptive only.

Side: resistance −22.88 (N=690), support −28.05 (N=541). Same sign, both beyond 15 minutes.

## Routing

`LEVEL_RESOLUTION_CLOCK_CANDIDATE`. Routing `LEVEL_RESOLUTION_CLOCK_STRUCTURE_PRESENT`. `SUCCESSOR_CANDIDATE = NONE`.

## Claim

L2. Discovery only. On this matched Binance sample, first touches of the pre-known structural levels historically spent about 25 minutes less unresolved, inside the same 4h horizon, than the deterministic pseudo-price touches. The 95% interval is −31.4 to −19.1 minutes. This is a historical restricted mean. It is not a current expected number of minutes. It is not a statement that the level expires after 15, 30, or any other cutoff.

## Product

`PRODUCT_INTEGRATION_CANDIDATE = NO`. No ACTIVE, AGING, or STALE label. No countdown, push rule, or confidence decay. No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings-registry, config, or deploy change.

The curve separates across the whole horizon, so this result by itself does not pick a minute at which a touch should be called stale. A product timer would need its own decision and, for any current timing claim, prospective calibration.

Not started: false-break outcome semantics, acceptance, a 30-minute threshold, current hazard calibration, a product timer.
