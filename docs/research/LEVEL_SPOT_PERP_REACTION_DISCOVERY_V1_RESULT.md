# LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The question is whether, after a structural first touch, the Binance spot market adds a late-BREAK difference once Binance's end position and the other perpetual venues' 15-minute move are already in the model. This note does not change the product. It does not say that spot led, confirmed, or caused the later barrier. The cross-perp control is not a confirmation of the prior unit.

## Provenance

Design SHA `98c750a4cf8df7d2b7b1262506129372bb2dc785`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`. Outcomes read: True. Claim ceiling `L2`.

Dependencies, not rewritten:

- touch: `dfc9e0f04358de15606382472badeb5aee787039`
- memory: `c3d39bffda861b535605a98205d7578c0c84c782`
- method: `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`
- approach: `aa85e5b43c405ee225336ff385e3a3383fa59d09`
- structure: `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`
- confirmation: `c1cd4e0102e700f7860d21a9af0d243c3bc367be`
- positioning_flow: `e6e5f307cfa098db607544a556bae01a2310eb6a`
- joint_state: `bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2`
- liquidity: `181debc4aa626637f2cd560103447d2d4adc96b1`
- post_touch_reaction: `44726ded55c75fefecc6848ab8b76971ead83721`
- acceptance_path: `b005eaac895d3a4c644d16101d2e5eb7d2ff8d5f`
- cross_venue: `f22100177e2f89a43c6271929aba0d63f7b4552f`

## Novelty

The object is the 15 minutes after the touch, on events still unresolved at D, with late BREAK versus REJECT as the outcome. It is not DH1-L1 or DH2-L1 (`SPOT_CONFIRMED_APPROACH_HOLD_4H`): those used spot taker flow over the hour into the touch and a 4h hold. DH2-L1 was an informative null. It is not DH1-B1 sign confirmation, not DH1-B2 / DH2-B2 spot share, not D9 or DH3 stress lead/lag, and not MARKET-06. No binary "spot confirms", no volume share, and no first-mover lag was computed. Atlas row `PRICE_STRUCTURE.levels`, column `SPOT`. Reopen key `NEW_MECHANISM` relative to the closed `SPOT_PERP` rows. `BLOCKED_REOPENING_SPOT_CONFIRMATION_CELL` does not apply.

`OTHER_VENUE_MEDIAN_MOVE` is the frozen #363 CV1, copied as a nuisance. Its coefficient in this baseline is not in the FDR family and is not a confirmation that the cross-perp result is level-specific.

## Data

Structural reference is Binance USD-M BTCUSDT perpetual, `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.

Other perpetuals are the pinned #363 series, not reminted. Bybit BTCUSDT linear perpetual, canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. OKX `BTC-USDT-SWAP`, canonical SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`. Not OKX spot.

Spot is `DH1_BINANCE_SPOT_BTCUSDT_5M_V0`, Binance spot BTCUSDT official 5m klines, taker field `taker_buy_quote_volume`, object-list SHA256 `5a27ea4883284c995bbb091067867b45927b67e3d4b244ed11c3b97e5887cb37`. Months read: 2020-04 through 2024-12. 499613 bars of 499968 expected, 355 missing (fraction 0.000710), left missing. No bar at or after 2025-01-01. Earlier pinned spot months were not read.

Event window `[2020-04-01T00:05:00Z, 2025-01-01T00:00:00Z)`. Alignment tolerance 0. A missing bar makes the affected feature missing. Missing is not a flat return.

T is the open of the Binance touch bar. D = T+15m. The price baseline is the close of the bar opening at T−5m. The price endpoint is the close of the bar opening at T+10m. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.

Seed 20261020. Bootstrap draws 2000. Cluster is the ISO week of the real touch. FDR q=0.10 over the three retained spot features. Practical scale 3 pp per +1 SD.

## Cohort

Structural episodes 4076. Real geometry-legitimate first touches 1856. Outside the window 96. No touch 2124.
Early BREAK 286, early REJECT 265, early ambiguous 13, unresolved at D 1292, unavailable 0.
Unresolved with finite baseline controls 1235. Feature-complete unresolved, all three spot features finite: 1234. SP3 legal rate 1.0, so SP3 was retained. One unresolved baseline row lacked a finite spot feature.
Late labels on those 1234 rows: BREAK 439, REJECT 620, NEITHER 174, ambiguous 1. Primary N = 1059. Week clusters = 238.
Unresolved feature-complete slices: DAY 1099, WEEK 122, MONTH 13; resistance 708, support 526; years 174 / 269 / 297 / 225 / 269.
Pseudo unresolved feature-complete pairs, outcome-blind: 623. That count is not a matched primary N.

## Features

All three features were retained. Maximum absolute correlation among them before outcomes is 0.082. Nothing met the 0.90 redundancy rule.

Correlation with the controls, reported and not used as a drop rule: SP1 with `OTHER_VENUE_MEDIAN_MOVE` is 0.998, and SP1 with `END_POSITION_X` is 0.690. SP2 with those controls is −0.136 and −0.072. SP3 with those controls is −0.030 and −0.004.

- SP1 `SPOT_ORIENTED_MOVE_15M`: d times the spot 15-minute log return.
- SP2 `SPOT_EXCESS_VS_PERP_COMPLEX`: SP1 minus the median of the three oriented perpetual log returns (Binance, Bybit, OKX).
- SP3 `RELATIVE_SPOT_TAKER_PRESSURE_15M`: oriented spot taker imbalance minus oriented Binance-perp taker imbalance on the three reaction bars.

Rough planning MDE on the unresolved feature-complete N, at the frozen 50% resolve fraction, was 6.31 pp. That figure was not a stop. The information gate passed before outcomes.

## Baseline

Every model contains `END_POSITION_X` and `OTHER_VENUE_MEDIAN_MOVE`. On the primary support the endpoint slope is +13.36 pp per +1 SD (95% +9.38..+17.51, N=1059, 2000/2000 draws). The cross-perp control on that same baseline is +9.08 pp per +1 SD (95% +5.17..+12.84, p=2.10e-6). The control is close to the prior unit's primary slope on a nearly identical cohort. It is not re-tested here, it is not in the FDR family, and it is not evidence that the prior slope is level-specific.

## Primary matrix

Adjusted change in `LATE_BREAK_GIVEN_RESOLVED` per +1 SD. The candidate adds one spot feature to the baseline. Benjamini–Hochberg q=0.10 over the three features.

| feature | coef | 95% CI | p | q | N | class |
|---|---:|---|---:|---:|---:|---|
| SPOT_ORIENTED_MOVE_15M | +32.97 pp | −12.36..+76.94 | 0.152 | 0.228 | 1059 | NONE |
| SPOT_EXCESS_VS_PERP_COMPLEX | +2.29 pp | −0.30..+5.12 | 0.0976 | 0.228 | 1059 | NONE |
| RELATIVE_SPOT_TAKER_PRESSURE_15M | −1.29 pp | −4.04..+1.57 | 0.385 | 0.385 | 1059 | NONE |

Same-model endpoint slopes stay near the baseline: +13.07 pp with SP1, +13.13 pp with SP2, +13.28 pp with SP3. Same-model cross-perp slopes: −23.66 pp with SP1 (95% −66.91..+21.39), +9.53 pp with SP2, +9.10 pp with SP3. Brier deltas are descriptive only: +0.00049, +0.00069, +0.00017.

SP1's point estimate is large and its standard error is 23.0 pp. The pre-outcome correlation of 0.998 with the cross-perp control is why. Putting both columns in one model does not separate a spot price move from the perpetual move. The interval includes 0, q is 0.228, and the statistical gate fails. The raw SP1 tertiles (late-break rate 0.2384 / 0.3666 / 0.6431, N=365 / 341 / 353) repeat the cross-perp gradient. They are not an incremental spot result.

SP2 is the relative magnitude the design asked for. Its slope is +2.29 pp, under the 3 pp scale, and the interval includes 0. Tertiles are flat: 0.4314 / 0.4011 / 0.4109 (N=357 / 354 / 348). SP3 is −1.29 pp, interval through 0. Tertiles are flat: 0.4298 / 0.4090 / 0.4056 (N=342 / 357 / 360).

No feature passes the statistical gate. No feature is a `SPOT_PERP_REACTION_CANDIDATE`.

## Years, family, side, leave-one-year-out

Five eligible years, 2020–2024. The frozen rule asks for at least 4/5 point estimates on the full-sample sign. A 2023 interval is withheld on every feature because fewer than 90% of that year's bootstrap draws returned a coefficient. The 2023 point still counts as eligible.

SP1 signs are + / + / − / + / −. Three of five match. 2020 is +111.23 pp (95% +18.82..+201.75, N=154). 2022 is −22.63 pp and 2024 is −27.20 pp; both intervals include 0. DAY is +34.24 pp (N=932) and WEEK is −4.38 pp (N=115), opposite estimable signs. MONTH is not estimable (N=12). Resistance +43.13 pp (N=593, interval through 0); support +14.91 pp with the interval withheld (N=466). Leave-one-year-out stays positive; every interval includes 0. Failed gates: statistical, years, family.

SP2 signs are + / + / − / + / −. Three of five match. 2020 is +7.54 pp (95% +1.98..+14.54, N=154). That year is reported. It is not a subgroup rescue. 2022 and 2024 points are negative and inside 3 pp. DAY +2.23 pp and WEEK +2.91 pp, same sign, both intervals through 0. Both side points are positive; the support interval is withheld. Leave-one-year-out stays positive; every interval includes 0. Failed gates: statistical, years.

SP3 signs are + / + / − / − / −. Three of five match the negative full-sample sign. Every reported year interval includes 0 or is withheld. DAY −1.13 pp and WEEK −0.60 pp, same sign. Resistance +0.18 pp (interval through 0) and support −3.71 pp (interval withheld) are opposite point signs, so the frozen side rule fails. That is not a side candidate. Leave-one-year-out stays negative; every interval includes 0. Failed gates: statistical, years, side.

## Matched specificity

Not applied. The full-sample candidate rule failed for every feature, so the paired real and pseudo models were not fit. `n_pairs` in the result file is 0 and the status is `NOT_APPLIED`. There is no Δ and no support-sensitivity comparison, because there is no full-sample candidate to compare. The outcome-blind count of 623 pseudo unresolved pairs is not a substitute.

## Routing

`NO_INCREMENTAL_SPOT_PERP_REACTION`. Candidate class `NONE`. `SUCCESSOR_CANDIDATE = NONE`.

Primary N is 1059. SP2 and SP3 intervals are about 5 pp wide, so the sample is not information-limited under the frozen width rule. SP1's interval is wide because the column repeats the cross-perp control, not because the cohort is small.

## Claim

L2. Discovery only. In this unresolved first-touch cohort, the spot 15-minute move, the spot excess over the perpetual complex, and the relative spot-versus-perp taker pressure do not add a late-BREAK difference beyond Binance end position and the other perpetual venues' 15-minute move. This is not a current probability. It is not a statement that the move lives only in the leveraged complex in a causal sense. The descriptive reading of the pre-outcome correlation is that the spot price over this same 15 minutes moves with the other perpetuals, so it does not supply a separate price signal once that move is in the model.

## Product

`PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings-registry, config, or deploy change.

Not started: lead/lag, time-to-resolution, a volatility transition, confirmation, a 30-minute window, a liquidation map, prospective tracking.
