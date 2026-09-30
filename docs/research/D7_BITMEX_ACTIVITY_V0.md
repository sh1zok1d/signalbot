# D7 BitMEX activity data V0

**Unit:** `D7_BITMEX_ACTIVITY_DATA_ACQUISITION_AND_PIT_AUDIT`  
**Dataset:** `D7_BITMEX_ACTIVITY_V0`  
**Parser:** `D7_BITMEX_ACTIVITY_PARSER_V0`

Outcome-blind pin of official pre-2020 XBTUSD 5m buckets with activity fields.
The D2 canonical dataset is unchanged. No D7 state, no t+1 target, no effect,
no replication class. Binance 2025/2026 were not opened. No confirmation prereg.

```
SOURCE = BitMEX GET /api/v1/trade/bucketed binSize=5m symbol=XBTUSD partial=false
CANONICAL_GZ_SHA256 = 33ab5c738aca3d7e58ea0bea8d575cc631d931a484b909025f5f3fc5e68b282c
CANONICAL_JSONL_SHA256 = c664fee628e8aafc8304abc72045157853246c02da4a4e57cc60ebb4e13d9ced
ROW_COUNT = 382033
RAW_PAGES = 383
INTERVAL = 2016-05-13T11:55:00.000Z .. 2019-12-31T23:55:00.000Z open time
D2_CANONICAL_GZ_SHA256 = 8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa
```

Timestamp rule matches the D2 parser: the official timestamp is the bucket end,
and `open_time_ms` is that timestamp minus 5 minutes. Raw HTTP bodies are
`raw_pages/page-NNNN.json`. No fill, interpolation, or forward-fill.

## Fields

Present on every row: `volume`, `foreignNotional`, `homeNotional`, `turnover`,
`trades`, OHLC, `timestamp`. `vwap` and `lastSize` are null on the 22728
zero-trade buckets and present otherwise.

`foreignNotional == volume` on all 382033 rows (max absolute difference 0).
`turnover` matches `homeNotional * 1e8` within 1 satoshi on every row, so
`homeNotional` / `turnover` are the XBT side. They are not the selected
activity field. Trade count is not a substitute.

## Contract unit

`CONTRACT_UNIT_PIT_STATUS = CONTRACT_UNIT_PIT_PROVEN_STABLE`

The proof is the pinned historical buckets, not the 2026 instrument row.
The quote-side identity is 1:1 for the whole interval, including 92449 rows
before `2017-03-31T12:00:00Z` and 289584 rows at or after that time. There is
no activity-unit discontinuity.

`CURRENT_INSTRUMENT_NOT_PIT.json` records the settled 2026-09-30 instrument
(`isInverse` true, `quoteCurrency` USD, `multiplier` -100000000, `lotSize` 100).
That row is not evidence for 2016–2019. BitMEX blog pages for the 2017 tick
notice and the 2021 lot-size notice returned HTTP 404 here, so those texts
are not part of the pin.

## Activity decision

```
SELECTED_D7_ACTIVITY_FIELD = foreignNotional
ACTIVITY_PORTABILITY_CLASS = D7_ACTIVITY_SCIENTIFICALLY_COMPARABLE
```

`foreignNotional` is the quote-side notional on this inverse USD contract.
Inside this history it is numerically the same series as contract `volume`,
so the conversion to quote notional is the identity. It is not Binance
USDT linear `quote_volume`, so it is not exactly portable.

## Coverage

```
MISSING_BUCKETS = 288
GAP = 2016-12-06T23:50:00.000Z -> 2016-12-07T23:55:00.000Z
INCOMPLETE_UTC_HOURS = 3
  2016-05-13T11:00:00Z (1 bar, listing)
  2016-12-06T23:00:00Z (11 bars)
  2016-12-07T23:00:00Z (1 bar)
COMPLETE_UTC_HOURS = 31835
ZERO_VOLUME = 22728
ZERO_FOREIGN_NOTIONAL = 22728
DUPLICATE_TIMESTAMPS = 0
NON_MONOTONIC = 0
```

Null counts are 0 for the activity and OHLC fields. `vwap` and `lastSize`
are null on the same 22728 zero-trade buckets.

```
D7_PRIMARY_TARGET_OPENED = false
D7_EFFECT_COMPUTED = false
BINANCE_2025_OPENED = false
BINANCE_2026_OPENED = false
NEXT_UNIT = D7_BITMEX_SUPPORT_AND_POWER_V0
```
