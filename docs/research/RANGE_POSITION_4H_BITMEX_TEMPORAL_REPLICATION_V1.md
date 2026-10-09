# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1

**Evidence class:** `HISTORICAL_TEMPORAL_REPLICATION / QUESTION_FRESH_REPLICATION`.
**Claim ceiling:** `HISTORICAL_ONLY`. `PRODUCT_INTEGRATION_CANDIDATE = NO`.
**Route:** `RANGE_POSITION_TEMPORAL_REPLICATION_SUPPORTED`.
**Design SHA256:** `124653de520dbacfd3e1945a52162fc9fd18b996866531368113307c6a69db3c`.
**BitMEX SHA256:** `8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa`.
**Evaluator digest:** `d0079c773c6662fbf966fe4c921aa4488950071df08a9b6ed4b6560a94c44ca6`.

One frozen temporal replication. Not a search. Prices are last-trade XBTUSD closes in price space. The inverse contract was not inverted. D7 was not read.

## Sample

Grid slots `382321`, occupied `382033`, holes left missing `288`.
Phase anchors `127440`. Analysis N `127303`. ISO weeks `191`.
Lost to the 2016 gap `116`. Lost to incomplete lookback `18`. Lost to incomplete future `3`.
T from `2016-05-13T16:00:00Z` through `2019-12-31T23:00:00Z`. Years `[2016, 2017, 2018, 2019]`.

## Estimates

Raw Spearman `-0.0760180885175`. Interval `-0.0849305985341` to `-0.0682529803646` (2000 / 2000 draws).

Partial given `RET_4H` `-0.0471614876751`. Interval `-0.054968917812` to `-0.0396918348838`. Not used for the route. Canonical one-covariate helper matches.

Primary partial given `RET_4H` and `RV_4H` `-0.0474283289268`. Interval `-0.0553218242265` to `-0.0398601135546`.

## Quintiles

Full-sample bins of position. Not a route input.

| bin | N | P(UP) | mean R | median R |
|---|---|---|---|---|
| 1 | 25461 | 0.581556105416 | 0.000350327780798 | 0.000635237554825 |
| 2 | 25460 | 0.54155538099 | -4.84477451146e-05 | 0.000365502232126 |
| 3 | 25461 | 0.507796237383 | 2.89292235054e-05 | 7.82319577946e-05 |
| 4 | 25460 | 0.483857030636 | 0.00023027505949 | -7.60779359501e-05 |
| 5 | 25461 | 0.442873414241 | -0.000129187004348 | -0.00039715636568 |

## Years

| year | N | raw | primary |
|---|---|---|---|
| 2016 | 22188 | -0.115733856984 | -0.0697317046147 |
| 2017 | 35038 | -0.0623675971691 | -0.0302318155243 |
| 2018 | 35040 | -0.0818632006636 | -0.0464033597917 |
| 2019 | 35037 | -0.0761132435655 | -0.058521255348 |

## Halves

Median T `2018-03-08T22:15:00Z`.

| half | N | raw | primary |
|---|---|---|---|
| first | 63652 | -0.078054040327 | -0.0479151496522 |
| second | 63651 | -0.0788034974056 | -0.0497512153132 |

Binance discovery Spearman was `-0.057773446228651215`. Bybit raw was `-0.05781800690167492`, partial given `RET_4H` `-0.027418341298313498`, primary `-0.02784152009582924`. This file does not recompute those reads.

Scientific status: `CROSS_VENUE_AND_TEMPORALLY_REPLICATED_DIRECTIONAL_STATE`.
