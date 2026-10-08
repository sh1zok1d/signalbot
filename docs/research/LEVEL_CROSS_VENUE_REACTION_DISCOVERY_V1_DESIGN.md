# LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1 — design note

**MODE = DISCOVERY.** Family `LEVEL_BEHAVIOR_V1`. Tracks `STRUCTURE` + `PRODUCT_EVIDENCE`.

This note is frozen before any cross-venue feature is joined to a late BREAK or REJECT label. A null is a complete result. The unit does not change `/btc`, `/levels`, `/check`, `/risk`, Telegram, config, scoring, the findings registry, or deployment. It does not start a spot-versus-perp, lead/lag, time-to-resolution, liquidation, 30-minute, confirmation, or prospective successor.

## Question

`LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1` showed that Binance `END_POSITION_X` at T+15m is strongly associated with later BREAK among structural first touches that are still unresolved then. `LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1` did not show that three Binance closes inside that same 15 minutes add a further difference once `END_POSITION_X` is held fixed.

This unit asks a different question.

At the same Binance location relative to the structural level, does the 15-minute price reaction of other same-class perpetual venues add information about the later BREAK versus REJECT resolution?

Two events can have the same Binance `END_POSITION_X`. On one, Bybit and OKX moved in the same structural direction. On the other, they barely moved or moved the other way. The question is whether that cross-venue state changes the later structural outcome after Binance's own endpoint is held fixed.

The wording stays descriptive. A positive oriented return means the venue's price moved in the structural break direction during the window. It does not mean the venue led, confirmed causally, or that arbitrage caused the resolution.

## What is already established and is not re-tested

The Binance endpoint association is already on the record. This unit does not rescore it and does not turn it into an acceptance, reclaim, or failed-break flag. `END_POSITION_X` enters every primary model as a mandatory control. A cross-venue association that disappears once that control is included is not incremental evidence.

Early resolution before D is not reopened. The primary cohort is `UNRESOLVED_AT_D`.

## Novelty audit

Read before any outcome: MARKET-06 authority, preregistration, and result; the Atlas `CROSS_VENUE_REGION` cells; DH3-X6; GV0R01-C018; V2 `price_direction_agreement`; #361; #362.

| Object | What it tested | Why this unit is a different object |
|---|---|---|
| MARKET-06 | Absolute dislocation z-score between Binance USD-M BTCUSDT perpetual and OKX BTC-USDT **spot**, at one decision per UTC day (00:05), as an incremental predictor of direction-aligned 24h adverse-path MAE. Result `MARKET_06_NO_EVIDENCE`. | Population is an independently replicated structural first touch. The clock is T+15m after the touch. The target is the remaining structural BREAK versus REJECT. The other legs are linear perpetuals, not spot. The feature is an oriented 15-minute log-return state, not a daily basis z-score. The baseline includes Binance `END_POSITION_X`. |
| DH3-X6 `VENUE_GAP_RANGE` | Binance–Bybit price gap to a range outcome. Closed at red team before data because it sat in the MARKET-06 dislocation family. | This unit does not predict a range from a price gap. It does not reopen `CROSS_VENUE_REGION.venue_disagreement`. |
| GV0R01-C018 | Retention of idiosyncratic versus common 5m jumps between the Binance perpetual and OKX spot. Blocked on causal identification. Dataset is the MARKET-06 spot leg. | No jump decomposition, no spot leg, no claim about which venue discovered the price. |
| V2 `price_direction_agreement` | Live multi-venue fraction used as a qualification input, including a `>= 2/3` gate on breakout setups. Flat prints count inside the agreement function. | `DIRECTION_AGREEMENT` here is a continuous share of venues with a strictly positive oriented 15-minute return. Exact zero is neutral. No 2/3 threshold is applied. The cohort is a structural first touch, and Binance endpoint location is controlled. |

The new object is same-class perpetual reaction around a Binance structural first touch, incremental to the Binance endpoint. Atlas row: `PRICE_STRUCTURE.levels`. Column: `CROSS_VENUE`. Reopen key: `NEW_MECHANISM` relative to MARKET-06, DH3-X6, GV0R01-C018, and the V2 agreement gate. `BLOCKED_REOPENING_CROSS_VENUE_CELL` does not apply. The taxonomy is not being edited to avoid that stop.

No lead/lag, Granger test, Hasbrouck share, or information share is computed. No spot series is read. No open interest, taker flow, funding, liquidation, or order book is read.

## Data identities

Structural levels, touch time, orientation, barrier distance, and the pseudo control come only from Binance USD-M BTCUSDT perpetual. Other venues do not create levels and do not move T.

| Venue | Instrument | Class | Source | Clock |
|---|---|---|---|---|
| Binance | USD-M BTCUSDT perpetual | linear, USDT | `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b` | exchange 5m open, UTC, parent #352 panel |
| Bybit | BTCUSDT perpetual | linear, USDT | `https://public.bybit.com/kline_for_metatrader4/BTCUSDT/` 5m files, not `spot/` and not `premium_index/` | label is fixed UTC+3; canonical open = label − 3h |
| OKX | `BTC-USDT-SWAP` | linear perpetual, settle USDT, `ctVal` 0.01 BTC, listed 2019-11-12, `state=live` | `GET /api/v5/market/history-candles`, `bar=5m`, `confirm=1` only | candle open in milliseconds, UTC |

The OKX spot series used by MARKET-06 is not a substitute. The mark-price candle endpoint is not used. No index price is used. No inverse contract is mixed in.

Dataset id: `LEVEL_CROSS_VENUE_PERP_5M_V0`.

- Bybit canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`. 476254 bars. UTC open from `2020-03-31T21:00:00Z` through `2024-12-31T20:55:00Z`. 23714 missing bars in four runs: `2023-12-05T01:00Z`–`2023-12-31T21:00Z` (7728), `2024-01-02T06:20Z`–`2024-01-31T21:00Z` (8528), `2024-02-27T08:10Z`–`2024-02-29T21:00Z` (730), `2024-03-08T12:20Z`–`2024-03-31T21:00Z` (6728). The public monthly files are truncated there. Those bars stay missing.
- OKX canonical SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`. 499968 bars. UTC open from `2020-04-01T00:00:00Z` through `2024-12-31T23:55:00Z`. Zero missing bars. Every stored candle had `confirm=1`.
- No bar with open at or after `2025-01-01T00:00:00Z` is stored. The Bybit December file's labeled `2025-01-01 00:00` fencepost was dropped before the canonical write. 2025 and 2026 objects were not requested.

Bybit close identity, outcome-blind, against the public linear trade tape (`timestamp,symbol,side,size,price`), shift −3 hours:

- 2020-04-01: 284/288 closes exact, max absolute residual 4 USDT.
- 2020-07-15: 279/288 closes exact, max absolute residual 2 USDT.

July uses the same −3 hour shift as April, so the label is not a DST clock. MT4 opens equal the previous close and are not required to equal the first trade. The unit uses closes only. Residuals above 10 USDT, or agreement below 95 percent on either audited day, would have failed the pre-outcome gate. The observed audits pass that rule. The few-USDT residuals are left as published; they are not edited.

**Tier A is frozen.** Binance, Bybit, and OKX. `CROSS_VENUE_DISPERSION` is in the primary family. The unit cannot move to a two-venue tier after outcomes.

Common overlap used for events is the parent structural window intersected with a legal reaction on all three venues. Event start is `2020-04-01T00:05:00Z`, so the pre-touch close at `2020-04-01T00:00:00Z` exists on OKX and, after the Bybit shift, on Bybit as well. Event end remains the parent exclusive bound `2025-01-01T00:00:00Z`. A missing other-venue bar makes the event unavailable. It is not filled.

## Event population and clocks

Reuse #352 exactly: kinds PDH, PDL, PWH, PWL, PMH, PML; birth, lifetime, merge, zone half `0.0015`, approach side, `X = 0.5 × 1.2816 × σ × √48`, BREAK, REJECT, NEITHER, same-bar ambiguity. Touch number 1 only. The pseudo control is the parent half-rotation inside `(family, struct_side)`. It is not rebuilt from venue prices.

`T` is the open of the Binance touch bar `j`. `D = T + 15m`. Reaction closes use the bar that opens at `T − 5m` and the bar that opens at `T + 10m` (the bar that closes at D). Future resolution uses Binance bars `j+3 .. j+48` only, the original 4h end. Early passage uses bars `j+1` and `j+2` only, imported from #361. An early BREAK, REJECT, or ambiguous passage is excluded from the predictive sample.

## Features

For each venue, `RET_v = log(close_v(D) / close_v(T))`, where `close_v(T)` is the close of the last completed bar before T. Both closes are knowable at D. Absolute BTC prices are never compared across venues.

`d = +1` when the Binance approach side is from below (break direction up). `d = −1` when the approach is from above. `ORIENTED_RET_v = d × RET_v`.

All four features require all three returns. One missing venue sets every feature to missing. Missing is not a zero return. Alignment tolerance is 0 ms. No forward fill, interpolation, or nearest bar.

1. `OTHER_VENUE_MEDIAN_MOVE = median(ORIENTED_RET_Bybit, ORIENTED_RET_OKX)`. With two venues the median is the arithmetic mean.
2. `CROSS_VENUE_CONFIRMATION_GAP = ORIENTED_RET_Binance − OTHER_VENUE_MEDIAN_MOVE`. Signed. Not an absolute value.
3. `CROSS_VENUE_DISPERSION = population standard deviation of (RET_Binance, RET_Bybit, RET_OKX)`, divisor 3, unoriented. No two-venue substitute.
4. `DIRECTION_AGREEMENT = (number of venues with ORIENTED_RET > 0) / 3`. Values in `{0, 1/3, 2/3, 1}`. Exact zero does not count as positive. No `>= 2/3` threshold.

If two retained features have `|rho| >= 0.90` on the unresolved feature-complete rows, the later feature in the list above is dropped before outcomes. The drop is not revisited.

## Outcome, estimand, nuisance

Primary outcome: `LATE_BREAK_GIVEN_RESOLVED`. Among events unresolved at D that then resolve inside the original 4h window, non-ambiguous: `1 = BREAK`, `0 = REJECT`. `NEITHER` and `AMBIGUOUS` stay out of the primary sample.

`LATE_RESOLVE_BY_4H` is descriptive only. It is not in the FDR family and cannot make a candidate.

Estimand: change in `P(LATE_BREAK | resolved)` per +1 SD of the cross-venue feature, adjusted for `END_POSITION_X` and the frozen nuisance.

Nuisance, and nothing else: `END_POSITION_X`; family DAY/WEEK/MONTH; support versus resistance; year; pre-touch realized-volatility tercile at the #352 cuts `0.0012364306616934476` and `0.001790567553180052`; UTC 6-hour block of T; pre-touch approach displacement `d × log(close of the bar ending at T / open of the bar opening at T−60m)`. No other post-touch Binance feature. No open interest or taker flow.

Transparency fits, same rows:

- baseline: `Y ~ END_POSITION_X + nuisance`
- candidate k: `Y ~ END_POSITION_X + nuisance + CV_k`

The reported quantity is the CV coefficient. A Brier difference on predictions clipped to `[0, 1]` is descriptive and does not promote a feature.

Scaling: standard z, `(x − mean) / sd` with `sd` the population standard deviation, on the real unresolved feature-complete rows. Means and sds are stored as hex floats in the preflight and reused for pseudo rows. `DIRECTION_AGREEMENT` is standardized the same way for the coefficient. Native values are kept for the tertile diagnostic.

Estimator: linear probability model. Week cluster is the ISO week of the real touch. 2000 draws. Seed `20261019`, stream `20261019 + 100 × feature_index + kind`. A 95 percent percentile interval is reported only when at least 90 percent of draws return a finite coefficient. Condition number above `1e8` returns no coefficient. Constant nuisance columns are pruned. `END_POSITION_X` is never pruned and is never the feature under test.

## Multiplicity, scale, stability, shape

FDR is Benjamini-Hochberg at `q = 0.10` over the retained CV features only. One primary outcome.

Practical scale: 3 pp per +1 SD. It is not lowered.

A feature is a `CROSS_VENUE_REACTION_CANDIDATE` only when all of the following hold:

1. absolute adjusted effect at least 3 pp per +1 SD;
2. 95 percent interval excludes 0;
3. BH q at most 0.10;
4. the coefficient is adjusted for `END_POSITION_X`;
5. year stability on the rules below;
6. every leave-one-year fit with remaining N at least 30 keeps the full-sample sign;
7. DAY and WEEK do not have opposite estimable signs;
8. support and resistance do not have opposite estimable signs;
9. the venue-clock audit above passed;
10. the conjunction is not rescued by the pseudo sample.

Eligible year: resolved N at least 30 and a finite coefficient. The surface has five calendar labels, 2020 (from April) through 2024, so the five-year rule applies: at least four eligible years share the full-sample sign. If only four years are eligible, at least three share that sign and any opposite year is smaller than 3 pp in absolute value. If only three are eligible, all three share the sign, or two share it and the third is smaller than 3 pp. Fewer than three eligible years fails. This rule is not replaced after the counts are seen.

Leave-one-year-out runs for each of 2020–2024. A remaining sample with N at least 30 must be estimable and must keep the sign. Fewer than three such leave-outs fails.

Family: DAY and WEEK are estimable at N at least 30. Opposite signs fail. A missing coefficient is not a contradiction. Leave-one-family-out is not a gate. MONTH is diagnostic. There is no family-specific candidate.

Side: the same rule for resistance and support. No side-specific winner.

Shape: tertile cuts are the 1/3 and 2/3 quantiles of the feature on the unresolved feature-complete rows, stored as hex before outcomes. Ties at a cut go to the lower bin. The late BREAK rate by tertile is descriptive. No threshold, unanimity state, or percentile rule is added after outcomes.

## Pseudo and specificity

The pseudo touch is the parent half-rotation control. It has its own T and D. Other-venue prices are the actual Bybit and OKX closes at that clock. Orientation, displacement, and `END_POSITION_X` use the pseudo approach and the pseudo Binance path. The control is not built from venue data.

Specificity is estimated when at least 100 pseudo events are unresolved at their own D, feature-complete, and resolved later as BREAK or REJECT, matched to a real event that is also in the primary sample. The stacked coefficient is `β_real − β_pseudo` from `feature_z + real + feature_z × real`, with the real touch's week as the cluster for both rows, and with the real-sample scales.

It is applied only after the real conjunction passes.

- Real conjunction passes and `|β_real − β_pseudo| ≥ 3 pp` with a 95 percent interval that excludes 0: `LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE`.
- Real conjunction passes and that difference does not: `GENERIC_CROSS_VENUE_REACTION_CANDIDATE`.
- Real conjunction fails: class `NONE`. A large pseudo difference cannot promote it.

## Information and routing

Pre-outcome gate, before any late label: at least 400 unresolved feature-complete real events, at least one retained feature, and the venue-clock audit passing. If the gate fails, late labels are not read.

After outcomes, `INFORMATION_LIMITED` when the primary N is below 200, or when every retained interval is withheld or wider than 20 pp.

Routing, in order:

- `LEVEL_CROSS_VENUE_STRUCTURE_PRESENT` if any feature is a level-interaction candidate;
- `GENERIC_CROSS_VENUE_REACTION_ONLY` if any feature is a generic candidate and none is level-specific;
- `STRUCTURE_PRESENT_BUT_UNSTABLE` if a feature meets the effect, interval, q, and endpoint gates but fails year, leave-one-year, family, or side stability;
- `INFORMATION_LIMITED` under the rule above;
- otherwise `NO_INCREMENTAL_CROSS_VENUE_REACTION_STRUCTURE`.

`CROSS_VENUE_HISTORY_INSUFFICIENT` and `BLOCKED_REOPENING_CROSS_VENUE_CELL` were the stops if the observability or novelty audit had failed. They did not.

Claim ceiling: `L2 / DISCOVERY_ONLY`. No current probability. No L3. No L4. No trade instruction. `PRODUCT_INTEGRATION_CANDIDATE = NO`.

One official run. A second invocation finds the result files and exits `REFUSING_RERUN`. After that run the venue set, instruments, alignment, 15-minute window, feature formulas, sign, dispersion divisor, nuisance, FDR, practical scale, and stability rule stay as written here.
