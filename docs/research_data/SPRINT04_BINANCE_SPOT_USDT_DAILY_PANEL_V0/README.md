# SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0

**Status:** IDENTITY_FROZEN / RAW_BYTES_GITIGNORED  
**Dataset ID:** `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0`  
**Legal months:** 2019-12 through 2024-12 inclusive.  
**Protected 2025/2026:** listed in S3 XML when present; **never fetched**.

Binance Vision spot monthly 1d klines for USDT-quoted symbols, including
delisted histories retained in the public archive. Enumeration is from pinned
S3 listing bytes, not from live `exchangeInfo`.

## Durability model

The frozen `object_ledger.json` is the scientific execution authority for
the file-key set. Mutable or current S3 listing state is not.

`D13_SNAPSHOT_ID` binds symbol-enumeration digest, `FILE_LEDGER_DIGEST`,
canonicalization version, and legal months. Runtime loaders derive the legal
zip list from that snapshot-bound ledger. `object_key_index.json` is
provenance/acquisition metadata only; feasibility verifies exact-set equality
with the ledger and fail-closes on `INDEX_LEDGER_KEYSET_MISMATCH`.

Raw monthly zips are restored from the frozen ledger with exact SHA256
verification. Scientific execution must fail closed if local bytes do not
match the ledger.

## What is tracked in git

- compact symbol enumeration authority (`symbol_prefixes.json`)
- top-level symbol listing pages (`listings/symbols_page_*.xml`)
- canonical legal object-key index (`object_key_index.json`, provenance only)
- exact object ledger with SHA256/CHECKSUM evidence (`object_ledger.json`)
- universe identity (`UNIVERSE_IDENTITY.json`)
- exclusion authority (`EXCLUSION_LISTS.json`)
- fee authority (`fee_authority/`)
- this restore contract (`README.md`)
- unicode ticker note (`listings/unicode_symbol_note.json`)

## What is not tracked

- raw monthly data zips / CHECKSUM sidecars
- raw per-symbol ListBucket XML pages

Raw zip/CHECKSUM bytes live at gitignored

`artifacts/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/raw/`

Future per-symbol ListBucket responses, if retained, belong under gitignored

`artifacts/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/listings/per_symbol_1d/`

This follows the CORE BTC pattern: identity and checksums are durable in git;
payload bytes are restored. There is no object-storage backing in this unit.

## Restore

```bash
python3 -m scripts.research.discovery_sprint_04.restore_d13_panel
```

The restorer downloads only ledger keys (2019-12..2024-12), refuses 2025/2026,
and verifies each zip against its CHECKSUM sidecar and the frozen ledger
SHA256. It does not compute returns or IC.

## Unicode ticker

`币安人生USDT` appears in the prefix listing. URL-encoded S3 listing shows
only 2026 monthly objects. Those keys are recorded in
`listings/unicode_symbol_note.json` and are not downloaded. Raw per-symbol
ListBucket XML for that ticker is not a tracked scientific authority.
