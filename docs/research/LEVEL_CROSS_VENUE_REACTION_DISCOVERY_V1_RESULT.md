# LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1

MODE = DISCOVERY

One official discovery run. The question is whether the 15-minute price reaction of other same-class perpetual venues adds a late-BREAK difference after Binance's own end position is held fixed. This note does not change the product. It does not say that a venue led, confirmed, or caused the later barrier.

## Provenance

Design SHA `f21be5a6cd022e3c8aacceccf8d13c61106e3b83`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
Exposure `DISCOVERY_ONLY`. Outcomes read: True. Tier `TIER_A`. Claim ceiling `L2`.

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

## Novelty

The object is not MARKET-06. MARKET-06 asked whether absolute Binance USD-M versus OKX BTC-USDT spot dislocation at a daily clock improved 24h adverse-path MAE, and closed as `MARKET_06_NO_EVIDENCE`. This unit uses structural first touches, a decision at T+15m, a remaining BREAK versus REJECT label, same-class linear perpetuals, and a mandatory Binance `END_POSITION_X` control. It is not a daily basis z-score and not a 24h adverse excursion. It is not a reopen of `CROSS_VENUE_REGION.venue_disagreement`, DH3-X6, or the V2 live `price_direction_agreement` gate.

## Data

Reference structure is Binance USD-M BTCUSDT linear perpetual only. CORE zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`.

Other venues, pinned as `LEVEL_CROSS_VENUE_PERP_5M_V0`:

- Bybit BTCUSDT linear USDT perpetual, public MT4 5m closes. Label clock is fixed UTC+3; canonical open is the label minus 3 hours. Canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. 476254 bars, first open 2020-03-31T21:00:00Z, last open 2024-12-31T20:55:00Z. 23714 bars missing in four public-file holes and left missing. Two trade-tape close audits passed before outcomes (shift −3h, match rate above 0.95, max absolute close residual at most 4 USDT).
- OKX BTC-USDT-SWAP linear perpetual, `history-candles` with `confirm=1` only. Canonical SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`. 499968 bars, 2020-04-01T00:00:00Z through 2024-12-31T23:55:00Z, zero missing bars. Not OKX spot and not mark price.

Event window 2020-04-01T00:05:00Z inclusive to 2025-01-01T00:00:00Z exclusive. No 2025/2026 object was requested. Alignment tolerance is 0 ms. A missing venue bar makes the whole cross-venue family missing. Missing is not a flat return.

T is the open of the Binance touch bar. D = T+15m. The return baseline is the close of the bar opening at T−5m. The return at D is the close of the bar opening at T+10m. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.

Seed 20261019. Bootstrap draws 2000. Cluster is the ISO week of the real touch. FDR q=0.10 over the four retained features. Practical scale 3 pp per +1 SD.

## Cohort

Structural episodes 4076. Real geometry-legitimate first touches 1856. Outside the venue window 96. No touch 2124.
Early BREAK 286, early REJECT 265, early ambiguous 13, unresolved at D 1292, unavailable 0.
Feature-complete unresolved 1235. The only missingness among unresolved events is `RET_BYBIT` = 57.
Unresolved feature-complete slices: DAY 1100, WEEK 122, MONTH 13; resistance 708, support 527; years 174 / 270 / 297 / 225 / 269.
Pseudo geometry-legitimate 1885. Pseudo unresolved feature-complete pairs 624.
Late labels on the feature-complete unresolved rows: BREAK 439, REJECT 621, NEITHER 174, ambiguous 1. Primary N = 1060. Pseudo primary matched N = 612. Week clusters on the primary support = 238.

## Features

All four features were retained. Maximum absolute correlation before outcomes is 0.630 (`OTHER_VENUE_MEDIAN_MOVE` with `DIRECTION_AGREEMENT`). Nothing met the 0.90 redundancy rule.

- CV1 `OTHER_VENUE_MEDIAN_MOVE`: mean of the Bybit and OKX oriented 15m log returns.
- CV2 `CROSS_VENUE_CONFIRMATION_GAP`: oriented Binance return minus CV1. Signed.
- CV3 `CROSS_VENUE_DISPERSION`: population standard deviation of the three unoriented log returns.
- CV4 `DIRECTION_AGREEMENT`: share of the three oriented returns that are strictly positive. Exact zero is neutral.

Rough planning MDE on the unresolved feature-complete N, at the frozen 50% resolve fraction, was 6.30 pp. That figure was not a stop.

## Baseline

On the primary support, `END_POSITION_X` is +20.30 pp per +1 SD (95% +17.41..+23.17, N=1060, 2000/2000 draws). The same-model endpoint slope stays in every candidate fit below.

## Primary matrix

Adjusted change in `LATE_BREAK_GIVEN_RESOLVED` per +1 SD, controlling for `END_POSITION_X` and the frozen nuisance.

| feature | coef | 95% CI | p | q | N | class |
|---|---:|---|---:|---:|---:|---|
| OTHER_VENUE_MEDIAN_MOVE | +8.87 pp | +5.02..+12.67 | 4.25e-6 | 1.70e-5 | 1060 | LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE |
| CROSS_VENUE_CONFIRMATION_GAP | +0.67 pp | −2.17..+3.44 | 0.647 | 0.647 | 1060 | NONE |
| CROSS_VENUE_DISPERSION | −1.57 pp | −5.05..+1.59 | 0.344 | 0.541 | 1060 | NONE |
| DIRECTION_AGREEMENT | +1.32 pp | −1.78..+4.39 | 0.406 | 0.541 | 1060 | NONE |

Same-model `END_POSITION_X` slopes: +13.43 pp with CV1, +20.21 pp with CV2, +20.48 pp with CV3, +19.50 pp with CV4. Brier deltas are descriptive only: +0.00275, +0.00005, +0.00021, +0.00004.

## CV1 diagnostics

Years, point and interval, resolved N: 2020 −1.86 pp (−16.49..+11.26, N=154); 2021 +6.35 (−2.77..+15.35, N=230); 2022 +8.28 (+1.17..+15.91, N=248); 2023 +15.64 (interval withheld, N=194); 2024 +7.35 (−3.52..+17.34, N=234). Five eligible years. Four match the full-sample sign, so the frozen 4/5 rule passes. The 2020 point is negative and its interval includes 0.

Leave-one-year-out, all positive and excluding 0: omit 2020 +10.08 pp (N=906); omit 2021 +9.44 (N=830); omit 2022 +8.77 (N=812); omit 2023 +6.33 (N=866); omit 2024 +9.12 (N=826).

Family: DAY +8.63 pp (+4.70..+12.82, N=933); WEEK +5.60 (−9.25..+19.24, N=115); MONTH no coefficient (N=12). DAY and WEEK have the same sign.

Side: resistance +5.10 pp (+0.09..+9.57, N=593); support +13.63 (interval withheld, N=467). Both points are positive.

Frozen tertiles of the late-BREAK rate: T1 0.244 (N=365), T2 0.349 (N=341), T3 0.653 (N=354). Descriptive only. No threshold was fit.

Pseudo-only slope −1.61 pp (−6.17..+2.85, N=612, 1967/2000 draws). The interval includes 0.

Stacked matched sample: beta_pseudo +4.17 pp, beta_real −0.07 pp, delta −4.24 pp (95% −7.96..−0.05, N=1223, 1965/2000 draws). Absolute delta is at least 3 pp and the interval excludes 0, so the frozen specificity rule names `LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE`.

Limitation, not a refit: the stacked real slope is about zero and does not reproduce the primary +8.87 pp. The stacked rows are the matched pairs in which both the real event and the pseudo event were unresolved at D and then resolved inside the original 4h. The interval on the delta barely excludes 0. The separate pseudo fit is near zero. The classification is the one the frozen rule wrote. It was not recomputed.

## Other features

CV2, CV3 and CV4 fail the statistical gate. Their year, leave-one-year-out, family and side slices do not form a candidate. CV3 resistance is −4.73 pp with an interval excluding 0, and the support point is +1.96 pp with the interval withheld. That opposition is diagnostic only: the cell already failed the primary gate, and there is no side-specific winner.

CV4 tertiles collapse. T1 holds all 1060 resolved rows and T2/T3 are empty, because the unresolved agreement distribution is piled at 1 (preflight mean 0.753, median 1, sd 0.426, tertile cuts both 1). No two-thirds or unanimity threshold was created.

Pseudo-only slopes for CV2, CV3 and CV4 are +0.35, −1.49 and −2.15 pp. Each interval includes 0. Their stacked deltas are −1.72, −0.64 and +2.70 pp. Each interval includes 0. A large pseudo difference was not available to rescue those nulls, and none was used.

## Routing

`LEVEL_CROSS_VENUE_STRUCTURE_PRESENT`.

Named class on CV1: `LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE`.
CV2, CV3 and CV4: `NONE`.
`SUCCESSOR_CANDIDATE = NONE`.
`PRODUCT_INTEGRATION_CANDIDATE = NO`.

Claim ceiling L2 / discovery only. The coefficients are historical adjusted associations in this unresolved first-touch cohort. They are not a current probability. No trade call. No product line.

Direction #4 was not started: no spot-versus-perp comparison, no lead or lag, no time-to-resolution, no liquidation map, no 30-minute window, no confirmation, and no prospective tracking.
