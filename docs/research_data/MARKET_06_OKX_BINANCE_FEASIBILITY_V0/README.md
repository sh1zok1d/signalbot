# MARKET_06_OKX_BINANCE_FEASIBILITY_V0

**Snapshot ID:** `e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68`
**Window:** `[2022-01-01T00:00:00Z, 2025-01-01T00:00:00Z)`
**Scientific outcomes inspected:** `false`

Outcome-blind source identity for the MARKET-06 OKX spot route review.
Does not preregister, arm, or test the hypothesis. Does not contain
price-derived quantities.

The scientific snapshot identity files below are **unchanged** from
materialization (HEAD `ef439110…`). `SNAPSHOT_ID` is not reminted.

| Git-bound identity file | SHA256 |
|---|---|
| `binance_object_ledger.json` | `437f10220b49a7f74e2c76445f5388ffc4006673d232c8b90f1946fe97e40fbf` |
| `okx_page_manifest.json` | `22702942c3860cd3c026784a4abda129470d893149bbb612cd36b33a99f1a9d9` |
| `timestamp_census.json` | `ad96ec9756ec77092a2eb26a6178e77b1a7dad4c2af21fdbc9ce92b3a2159d70` |
| `snapshot.json` | `dfc6006f020af551d56b26caee6b694967c26557a405e9c668a78d77f74d4ba7` |

`snapshot.json` still records the mint-time durability string
`IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`. A later
retention unit bound the same bytes into Git without changing that file:

- durable exact bytes: `durable_raw/binance/` (36 ZIPs + CHECKSUM sidecars)
  and `durable_raw/okx/` (1053 HTTP bodies)
- manifest: `DURABLE_RETENTION_MANIFEST.json`
- `DURABLE_EVIDENCE_ROOT_SHA256` =
  `f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f`
- offline verifier: `scripts/research/market_06_durable_retention.py`

`probes/` holds redacted OKX structural-probe summaries (timestamps /
`confirm` / counts only; no OHLC).

Parent review: `docs/research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.md`.
Retention unit: `docs/research/MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.md`.
The Bybit-route artifact `docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.md`
is preserved historically and was not rewritten.
