# MARKET-06 feasibility durable raw-evidence retention

Status: `MARKET_06_DURABLE_RAW_EVIDENCE_RETAINED`
Date: 2026-09-21

This unit does **not** preregister, arm, or test MARKET-06. It does not
change source selection, timestamps, window, or scientific design. It
does **not** rewrite the Bybit feasibility artifact or the accepted OKX
source-route conclusion.

Machine-readable twin:
[`MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.json`](MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.json)

```text
DATASET_ID = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
SOURCE_FEASIBILITY_HEAD = ef439110684e5bef5d6b6f31b664c21a114111b2
NEW_SNAPSHOT_MINTED = false
```

## Why this unit exists

The OKX/Binance feasibility snapshot was scientifically clean but its
raw source bytes lived only under gitignored `artifacts/`. This unit
binds those **already materialized** bytes into Git.

No redownload was performed. Every runtime object was hashed against the
frozen ledgers first. All 36 Binance ZIPs and all 1053 OKX HTTP bodies
matched.

## What was retained

Direct exact-byte files (no pack, no transform, no zip recompression, no
JSON pretty-print):

- `docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/binance/`
  — 36 monthly ZIPs + official CHECKSUM sidecars
- `docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/okx/`
  — 1053 official history-candles HTTP bodies as stored at materialization

Manifest:
`docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/DURABLE_RETENTION_MANIFEST.json`

Offline verifier:
`scripts/research/market_06_durable_retention.py verify`

The frozen identity files (`snapshot.json`, ledgers, census, `HASHES.json`)
were not rewritten, so `SNAPSHOT_ID` remains `e0403e40…`.

## Outcome firewall

No OHLC inspection, dislocation, spread, returns, MAE, or 2025/2026
access. Raw bytes were read only to copy and SHA256.

`SCIENTIFIC_OUTCOMES_INSPECTED = false`

NEXT_UNIT = `MARKET_06_PREREGISTRATION_DESIGN`
