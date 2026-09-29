# GV0R01-C020 design stopped before a sample was frozen

`C020_DEFINITION_STATUS = UNAMBIGUOUS`
`OUTCOME_BLIND_GATE_RESULT = BLOCKED_BY_MISSING_INPUT`
`MARKET_DATA_OPENED_FOR_C020 = false`
`NEXT_UNIT = GV0R01_C020_HOLIDAY_CALENDAR_PINNING`

The GV0R01-C020 card is a holiday natural experiment on BTC intraday session volume shares. Official regional holidays are supposed to remove a participant block and move quote-volume share away from that region's session. The lead contrast in the card is NYSE weekday closures. The China arm is separate. No second C020 definition was found.

The card requires three point-in-time calendars that are not in the repository:

- `NYSE_HOLIDAY_CALENDAR_ARCHIVE`
- `CN_STATE_COUNCIL_HOLIDAY_NOTICES`
- `US_OPM_FEDERAL_HOLIDAY_LIST`

Each is marked `FEASIBILITY_REQUIRED`. Holiday dates may be used only if they were published before the holiday. No pinned archive supplies those dates or publication times. A convenient third-party list was not substituted.

`CORE_BTC_BINANCE_V0` and `STATUTORY_DST_CALENDARS` are the ready sources. They do not identify the treatment days. No BTC price or volume value was opened. No primary statistic was computed. Inference and power were not reached.

Machine record: `GV0R01_C020_DESIGN_BLOCK.json`.
