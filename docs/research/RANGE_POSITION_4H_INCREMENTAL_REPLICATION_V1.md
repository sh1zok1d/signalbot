# RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1

**Evidence class:** `CROSS_VENUE_HISTORICAL_REPLICATION / ONE_SHOT`.
**Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Route:** `RANGE_POSITION_INCREMENTAL_CROSS_VENUE_SUPPORTED`.
**Design SHA256:** `8132f181fd4ced19ee1c356a99022e195c005f0b2e95ac2135074ad7cc4c0e7d`.
**Design commit:** `4c6c5583ee93f4541224363e129d5b9505167fe8`, written before this read.
**Bybit SHA256:** `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`.
**Evaluator digest:** `bb0f5f548497d9ceec7c849d929973fac9f9aebb43e7f78785225271d5a5e07b`.
**Read:** the numbers below are the one official read. A second call exits `REFUSING_RERUN`.

One frozen check. Not a discovery scan. Rejection and bars-since were not read. `2025/2026` was not read. Binance outcomes were not loaded. Fees were not computed.

## Sample

Bybit BTCUSDT linear perpetual 5-minute file. First open `2020-03-31T21:00:00Z`. Last open `2024-12-31T20:55:00Z`. Grid slots `499968`, occupied `476254`, holes left missing `23714`.

Parent 15-minute phase. Phase anchors `166656`. Analysis intersection `158650` (complete 4h clock path, finite position, finite width, finite 1h target). ISO weeks `240`. `T` from `2020-04-01T01:15:00Z` through `2024-12-31T20:00:00Z`. Years `2020, 2021, 2022, 2023, 2024`.

`RP4H` is the parent ratio on the 48 bars whose closes fall in `(T-4h, T]`, including the bar that closes at `T`. `RET_4H = log(close[T] / close[T-4h])`. `RV_4H` is the square root of the sum of squares of those 48 log returns. `R_1H = log(close[T+1h] / close[T])`.

## Estimates

| Estimand | Point | 95% week-block interval | Draws |
|---|---|---|---|
| Spearman(`RP4H`, `R_1H`) | `-0.05781800690167492` | `[-0.06485654891316102, -0.05103727227273947]` | `2000/2000` |
| Partial given `RET_4H` only | `-0.027418341298313498` | `[-0.034498171117585553, -0.020745636714591814]` | `2000/2000` |
| Primary partial given `RET_4H` and `RV_4H` | `-0.02784152009582924` | `[-0.03483702325812674, -0.02121680501364248]` | `2000/2000` |

Seed `20261117`. The one-covariate point matches `amendment_a1.partial_spearman`. The `RET_4H` partial is not a route input. The primary interval lies entirely below zero, and both points are negative, so the frozen route fires.

Raw minus the `RET_4H` partial: `-0.030399665603361423`. Share of the raw association removed by `RET_4H`: `0.5257819705729216`. About half the raw rank association is the recent signed 4h return. The remaining half stays negative. Adding `RV_4H` moves the point from `-0.027418341298313498` to `-0.02784152009582924`. The attenuation is the signed displacement, not the volatility scale.

Spearman of position with `RANGE_WIDTH_4H`: `0.021063998681372126`. Partial also given width: `-0.027847842706067`. The point does not move. The control set stays the frozen pair.

## Quintiles

Full-sample bins of `RP4H`. Edges `0.2603550295857988`, `0.4393939393939394`, `0.6166825078397975`, `0.7843866171003717`. Not a threshold. Not a Q1/Q5 rule.

| bin | N | P(UP) | mean R | median R |
|---|---|---|---|---|
| 1 | 31729 | 0.5640266002710455 | 0.0001744606410095766 | 0.0005629362904796095 |
| 2 | 31730 | 0.5276709738417901 | -3.218858821571341e-05 | 0.0002074281463642359 |
| 3 | 31731 | 0.5067914657590369 | 1.815439766232693e-05 | 5.4029229826536295e-05 |
| 4 | 31729 | 0.48781871474045824 | 6.0990877264120075e-05 | -8.423180597975475e-05 |
| 5 | 31731 | 0.4534682172008446 | 0.00010883254757863659 | -0.00036901184319832066 |

P(UP) and the median step down as position rises. The mean does not. The same shape was in the Binance discovery table. These bins are descriptive.

## Years and halves

| year | N | raw | primary |
|---|---|---|---|
| 2020 | 26395 | -0.06603288172370304 | -0.04789009984849811 |
| 2021 | 35040 | -0.037415891826256535 | 0.0019259518922127197 |
| 2022 | 35040 | -0.07029352094362909 | -0.04114602869211298 |
| 2023 | 32449 | -0.07131875854407313 | -0.035911267739738136 |
| 2024 | 29726 | -0.05874076432188619 | -0.03876439018036863 |

Median `T` is `2022-07-06T08:22:30Z`.

| half | N | raw | primary |
|---|---|---|---|
| first | 79325 | -0.04787167154058692 | -0.01650464773411807 |
| second | 79325 | -0.06902903987672047 | -0.03932397360896029 |

No stability gate was frozen. The route does not depend on these rows. They are part of the record: the raw sign is negative in every year; the primary point is negative in four years and about zero in 2021 (`+0.0019259518922127197`). Both halves stay negative.

## Evidence record

- **Estimate.** Primary partial Spearman `-0.02784152009582924`. Raw Spearman `-0.05781800690167492`.
- **Uncertainty.** Week-block percentile interval of the primary partial `[-0.03483702325812674, -0.02121680501364248]`, 2000 of 2000 draws, seed `20261117`.
- **Information.** Analysis N `158650`. ISO weeks `240`. Phase anchors before the complete-path filter `166656`.
- **Stability.** Raw sign negative in all five years and both halves. Primary sign negative in four years, in both halves, and flat in 2021.
- **Falsification check.** The predeclared alternative is that position is the recent signed return. Removing `RET_4H` cuts the association by about half and leaves an interval below zero. `RV_4H` and range width do not account for the remainder.
- **Limitations.** One venue, one horizon, overlapping 15-minute anchors, in-sample quintiles, 2021 incremental point near zero, parent cell chosen from an adaptive scan. Not a fee-aware edge. Not a probability that price reaches a target.
- **Search exposure.** Two inferential estimands, raw and primary, frozen before the outcome. One secondary partial and one width diagnostic, not used to route. No horizon search. No threshold search. Rejection features were not computed.
- **Method before outcome.** `docs/research/RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1_DESIGN.md`, commit `4c6c5583ee93f4541224363e129d5b9505167fe8`.
- **Evidence summary.** On this Bybit sample the rank association of 4h range location with the next 1h return stays negative after the 4h signed return and 4h realized volatility are removed, and the week-block interval lies below zero.
- **Claim decision.** L2 historical association for this frozen estimand on this surface. Not an L3 current probability. Not an L4 action. No bot line.

## Reading

This is Case A of the design on the pooled sample. The raw cross-venue association has the discovery sign, and the primary partial does too. Location inside the trailing 4h range is not only `log(close[T] / close[T-4h])`, and it is not the 4h volatility scale.

The Binance discovery Spearman was `-0.057773446228651215`. The Bybit raw point is `-0.05781800690167492`. The discovery quintile P(UP) values were `0.5626`, `0.5304`, `0.5086`, `0.4884`, `0.4527`. The Bybit descriptive ladder is `0.5640`, `0.5277`, `0.5068`, `0.4878`, `0.4535`. The parent number was not recomputed here.

What remains open: 2021 does not carry the incremental association; the mean return is still not a monotone function of position; nothing here is a target-hit model; rejection and bars-since are still unread. A separate successor may ask whether those boundary features add anything beyond `RANGE_POSITION_4H`. This file does not open that unit.

Parent Binance discovery Spearman was `-0.057773446228651215`, discovery only. This file does not recompute it.
