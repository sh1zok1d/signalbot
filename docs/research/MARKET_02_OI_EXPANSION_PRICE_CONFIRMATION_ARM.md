# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — one-shot canonical ARM

- **Status:** `ARMED_NOT_EXECUTED` / `AUTHORIZED_UNUSED`
- **Unit ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION_ARM`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Date:** 2026-09-18

**Not a RESULT. Not MARKET-02 execution. Not outcome inspection.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

Canonical machine-readable twin:
`docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_ARM.json`.

Reservation:
`docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESERVATION.json`.

This ARM authorizes **exactly one** canonical MARKET-02 execution
against the already-frozen implementation. The reservation is unused.
This ARM does not itself consume the execution. No rerun is
pre-authorized. No RESULT file is created by this unit.

```text
REVIEWED_IMPLEMENTATION_HEAD = 1d2b0abf73d245f37cd9ca55ece99d1628dc80ee
REVIEWED_IMPLEMENTATION_TREE = 9e18ccf690e280bbd4b033f4a44f3b0700a5bedb
FROZEN_IMPLEMENTATION_HEAD   = 124da2bfdb0b5dfb6e0a8da5789a474af526f27f
FROZEN_IMPLEMENTATION_TREE   = 7303a4507cba716209ea012f2c4e180eef31ba18
RUN_IDENTITY                 = 4ef6a6c543f6a11930fe0ae26cb6bfbe7f19feac4c645d8fed992eebcd36a032

CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED   = 0
MARKET_02_ARMED                 = YES
MARKET_02_EXECUTED              = NO
MARKET_02_OUTCOME_INSPECTED     = NO
MARKET_02_TEST_CALIBRATED       = NO
PROTECTED_OOS_TOUCHED           = NO
```

MD bootstrap seed `1852983754304692007` remains authoritative. The
frozen JSON twin numeric `1852983754304692000` is the historical
IEEE/JSON representation discrepancy; it is not repaired and does not
override MD.

Bound in-sample inputs (identity documents only; parquet contents and
protected 2025/2026 OOS are not opened by this ARM):

```text
CORE price  CORE_BTC_BINANCE_V0
            snapshot 717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
            identity docs/research_data/CORE_BTC_BINANCE_V0/SNAPSHOT_717d37a4.json
            SHA256   a104a4036ed7b4c7a4a9954ce1aeee247b6bbbb91d6abf2563b78b6bd9f84630
            size     74422
            native   1m
OI          B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0
            snapshot 5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33
            identity docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/SNAPSHOT_5a9d036b.json
            SHA256   bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e
            size     1863449
            native   5m sum_open_interest
ALLOWED     [2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)
```

Reserved RESULT destination (file must not exist yet):
`docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_RESULT.json`.

ARM does not upgrade methodology status. ARM does not imply validated
alpha, calibrated Type I, persistence, profitability, independent
replication, or OOS confirmation. The frozen DETECTED interpretation
is unchanged. `MARKET_02_TEST_CALIBRATED = NO`.
