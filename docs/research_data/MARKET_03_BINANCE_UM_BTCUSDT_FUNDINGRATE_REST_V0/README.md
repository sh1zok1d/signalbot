# MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0 snapshot evidence

**Status:** `SNAPSHOT_MATERIALIZED_PRE_ARM`
**Snapshot ID:** `d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68`
**Construction parent commit:** `3f1722476927a13d4e1629510f12ed00f72ba3d8`

Dedicated Binance USD-M `BTCUSDT` REST `/fapi/v1/fundingRate` identity for MARKET-03. Not B2-06. Not a strategy result. Not ARM.

Raw REST JSONL and canonical JSONL are gitignored. This snapshot proves exact historical identity at materialization time.

| Archival file | Runtime source | SHA-256 |
|---|---|---|
| `SNAPSHOT_d47b7b78.json` | `reports/snapshot_manifest.json` | `5cf01f672b2e2de2d6ce7966109d91a0fcfc82ec8dd08fe11fcf0b1321d3b210` |
| `SOURCE_LEDGER_d47b7b78.json` | `reports/source_ledger.json` | `7232016e568f06e8328034ee9f665301052267a13feb1645788af40bb395bef6` |
| `QUALITY_REPORT_d47b7b78.json` | `reports/quality_report.json` | `01881f1762a4faaa80ba8e6c286165c01dadfc2d91869904c94463ccc20ddde2` |

Authorized REST window `[2019-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`:

- 5819 raw funding rows
- first fundingTime `2019-09-10T08:00:00Z`
- last fundingTime `2024-12-31T16:00:00Z`
- duplicate fundingTime: 0
- missing expected 8h hour-floor events: 0
- canonical JSONL SHA256 `e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb`

```text
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

Durability: `IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`.

Canonical repository manifest: `docs/manifests/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0.yaml`.
Provenance record: `docs/research/MARKET_03_FUNDING_SNAPSHOT.md`.
