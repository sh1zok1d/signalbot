# SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0

**Status:** IDENTITY_FROZEN / RAW_BYTES_GITIGNORED  
**Dataset ID:** `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0`  
**Legal months:** 2019-12 through 2024-12 inclusive.  
**Protected 2025/2026:** listed in S3 XML when present; **never fetched**.

Binance Vision spot monthly 1d klines for USDT-quoted symbols, including
delisted histories retained in the public archive. Enumeration is from pinned
S3 listing bytes, not from live `exchangeInfo`.

## What is tracked in git

- `listings/` — exact S3 ListBucket XML pages (symbol prefixes and per-symbol 1d keys)
- `symbol_prefixes.json` — USDT symbol enumeration + listing digest
- `object_key_index.json` — legal zip/CHECKSUM keys 2019-12..2024-12
- `object_ledger.json` — per-file SHA256, sidecar CHECKSUM, sizes, timestamp diagnostics
- `fee_authority/` — first-party Binance Regular User spot taker pin
- `UNIVERSE_IDENTITY.json` — per-Monday selected top-N identity (no returns)
- `README.md` — this restore contract

Raw zip/CHECKSUM bytes live at gitignored

`artifacts/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/raw/`

This follows the CORE BTC pattern: identity and checksums are durable in git;
payload bytes are restored. There is no object-storage backing in this unit.
That is an explicit durability debt: scientific execution must fail closed if
local bytes do not match the ledger.

## Restore

```bash
python3 -m scripts.research.discovery_sprint_04.restore_d13_panel
```

The restorer downloads only ledger keys (2019-12..2024-12), refuses 2025/2026,
and verifies each zip against its CHECKSUM sidecar and the frozen ledger
SHA256. It does not compute returns or IC.

## Unicode ticker

`币安人生USDT` appears in the prefix listing. URL-encoded S3 listing shows
only 2026 monthly objects. Those keys are pinned and not downloaded.
