# FORWARD_MARKET_OBSERVABILITY_V1 — Implementation freeze

**Status:** `IMPLEMENTED_FROZEN_NOT_AUTHORITATIVE_COLLECTION`
**Unit kind:** data acquisition infrastructure freeze.
**Not** a scientific experiment. **Not** MARKET-06. **Not** M04-FWD.
**Not** authorization to start authoritative collection.

Machine-readable twin:
[`FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.json`](FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION_FREEZE.json)

```text
PRE_IMPLEMENTATION_HEAD = 649ea868ba95a78e3718bdd4acbbe542ddd1befd
PRE_IMPLEMENTATION_TREE = 8a1ea21cf958740b33b6318643a2cee3694a6e94
COLLECTOR_HEAD = UNSET_UNTIL_THIS_COMMIT
COLLECTOR_TREE = UNSET_UNTIL_THIS_COMMIT
RAW_ENVELOPE_SCHEMA = forward_market_observability_v1_raw_envelope/1.0.0
CHUNK_SCHEMA = forward_market_observability_v1_chunk/1.0.0
MANIFEST_SCHEMA = forward_market_observability_v1_manifest/1.0.0
LEGAL_AVAILABLE_AT = local_received_at_utc
AUTHORITATIVE_COLLECTION_STARTED = false
AUTHORITATIVE_COLLECTION_START_UTC = null
MARKET_06_CREATED = false
M04_FWD_CREATED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
NEXT_UNIT = FORWARD_MARKET_OBSERVABILITY_V1_AUTHORITATIVE_COLLECTION_START
```

`COLLECTOR_HEAD` / `COLLECTOR_TREE` remain `UNSET_UNTIL_THIS_COMMIT`
because they are the identity of this freeze commit. Binding is to the
collector file SHA256 map in the JSON twin, plus the schema identities
above.

## What is frozen

Minimal Binance USD-M BTCUSDT collector:

- `BINANCE_UM_BTCUSDT_MARK_PRICE_WS` — mark price / funding / next-funding
- `BINANCE_UM_BTCUSDT_PREMIUM_INDEX_REST` — premium / basis
- `BINANCE_UM_BTCUSDT_OPEN_INTEREST_REST` — open interest on its own clock

Receipt rule: `legal_available_at = local_received_at_utc`, assigned
before JSON parsing, together with `local_received_monotonic_ns`.
Exchange event time is descriptive metadata only.

Raw append-only JSONL chunks are the root evidence. Parsed records are
rebuildable derivatives. Completed chunks are not overwritten. Crash
leaves `.partial` as `INCOMPLETE`/`QUARANTINED`. Reconnect is a new
connection identity; a coverage gap is a gap. REST backfill, if used
later, is `source_type=BACKFILL` and cannot masquerade as original live
receipt.

## Explicitly not started

Authoritative collection using this frozen implementation has **not**
begun. A short live smoke ran and is labeled
`INFRASTRUCTURE_SMOKE_TEST_ONLY`. Those bytes remain scientifically
excluded. Do not use smoke or later live values to tune M04-FWD.

Do not create MARKET-06. Do not create M04-FWD in this unit.

## Next unit

```text
NEXT_UNIT = FORWARD_MARKET_OBSERVABILITY_V1_AUTHORITATIVE_COLLECTION_START
```
