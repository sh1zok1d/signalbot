# FORWARD_MARKET_OBSERVABILITY_V1 — Implementation

**Status:** `IMPLEMENTED_FROZEN_NOT_AUTHORITATIVE_COLLECTION`
**Unit kind:** data acquisition infrastructure.
**Not** a scientific experiment. **Not** MARKET-06. **Not** M04-FWD.

Freeze authority:
[`FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.md`](FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.md)

Package:
`scripts/research/forward_market_observability_v1/`

## What was implemented

Minimal Binance USD-M BTCUSDT collector with three independently
timestamped sources:

- `BINANCE_UM_BTCUSDT_MARK_PRICE_WS` — mark price / funding / next-funding
- `BINANCE_UM_BTCUSDT_PREMIUM_INDEX_REST` — premium / basis
- `BINANCE_UM_BTCUSDT_OPEN_INTEREST_REST` — open interest (own clock)

`legal_available_at = local_received_at_utc`, assigned before JSON
parsing. Monotonic ns is process-local order only.

Raw evidence is append-only JSONL chunks with fsync + atomic finalize.
Parsed records are rebuildable derivatives that reference raw SHA256.

## CLI

```text
python3 -m scripts.research.forward_market_observability_v1 smoke
python3 -m scripts.research.forward_market_observability_v1 collect
```

`collect` is refused until a later
`FORWARD_MARKET_OBSERVABILITY_V1_AUTHORITATIVE_COLLECTION_START` unit.

Smoke sessions are labeled `INFRASTRUCTURE_SMOKE_TEST_ONLY` and are
not scientific evidence.

## Storage

```text
artifacts/forward_market_observability_v1/sessions/<session_id>/
  SESSION.json
  raw/<source_id>/chunk-NNNNNN.jsonl
  manifests/<source_id>.json
  parsed/<source_id>.jsonl
  events/<source_id>.jsonl
  health/<source_id>.json
```

## Explicitly not done

- MARKET-06
- M04-FWD preregistration
- authoritative collection start
- future return / MAE / beta / prediction / classification
- using smoke bytes to tune a later hypothesis
