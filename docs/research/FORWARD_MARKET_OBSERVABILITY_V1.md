# FORWARD_MARKET_OBSERVABILITY_V1 — Design (not an implementation)

**Status:** `DESIGN_ONLY_NOT_IMPLEMENTED`
**Unit kind:** infrastructure / data collection design.
**Not** a hypothesis test. **Not** MARKET-06. **Not** a preregistration.
**Machine-readable twin:** [`FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_CONTRACT.json`](FORWARD_MARKET_OBSERVABILITY_V1_COLLECTOR_CONTRACT.json)

```text
IMPLEMENTATION_AUTHORIZED = false
SCIENTIFIC_TEST_AUTHORIZED = false
MARKET_HYPOTHESIS_FROZEN = false
THRESHOLDS_SELECTED = false
OUTCOME_GATES_DEFINED = false
COLLECTION_MAY_NOT_TUNE_A_LATER_HYPOTHESIS = true
COLLECTION_START_MUST_PRECEDE_FUTURE_M04_FWD_PREREGISTRATION = true
```

## 1. Goal

Collect future funding / premium / leverage observables with locally
provable point-in-time availability.

This resolves the historical publication-latency ambiguity that blocked
MARKET-04. It does **not** guarantee that funding will work. It does
**not** freeze a new MARKET hypothesis.

## 2. What this is / is not

This is:

- an append-only acquisition contract for exchange messages;
- a provenance design so later science can cite `legal_available_at`;
- hypothesis-neutral enough to support a later separate preregistration.

This is **not**:

- a collector implementation;
- a scientific execution;
- MARKET-06;
- a third historical proxy salvage;
- authorization to treat current Binance historical archives as
  point-in-time safe;
- permission to compute future return, MAE, drawdown, prediction, beta,
  or classification during collection setup.

## 3. Evidence model

Every received exchange message produces **immutable raw evidence** plus
an optional **derivative parsed record**. No parsed record may replace
the raw immutable evidence.

### 3.1 Required fields on every received message

Preserve at minimum:

| Field | Requirement |
|---|---|
| `local_received_at_utc` | Generated locally **before** parsing or analysis. This is the conservative scientific availability clock. |
| `exchange_event_time` | Stored if present on the message. **Not** `legal_available_at`. |
| `instrument` | Exact exchange instrument identity (e.g. `BTCUSDT`, market type). |
| `stream/source` | Stream name, REST path, or equivalent source identity. |
| `raw exact message bytes` | Unmodified payload as received. |
| `sha256(raw bytes)` | Content hash of those exact bytes. |
| parsed fields | Derivative record only. |
| `collector_version` / git identity | Bound collector source version. |
| `connection/session identity` | Distinguishes reconnects. |
| sequence/order information | Where the exchange provides it. |

### 3.2 Legal available-at (conservative)

```text
legal_available_at = local_received_at_utc
```

**Not:**

```text
legal_available_at = exchange_event_timestamp
```

unless a later **separate** proof establishes a stronger rule.

This removes the historical publication-latency ambiguity that blocked
MARKET-04. A later unit may attempt a stronger proof. This design does
not claim that proof.

## 4. Initial observable family

Support, where legitimately available from the exchange:

- funding-rate state
- premium / basis state
- mark-price state
- next-funding metadata
- open-interest state **if** available through a separately timestamped
  collector (do not silently merge OI into funding/premium clocks)

Do **not** freeze:

- a new MARKET hypothesis;
- thresholds;
- outcome gates;
- feature transforms chosen by later predictive performance.

The collector must remain hypothesis-neutral.

## 5. Immutability / retention

### 5.1 Raw objects

- Raw messages are append-only.
- Each object/chunk has SHA256.
- A manifest binds ordered objects.
- Collector source version is bound into the manifest.
- `received_at` is generated before parsing/analysis.
- Later parser changes cannot alter historical raw bytes.
- Scientific code never overwrites acquisition evidence.

Suggested object grain (design, not implementation):

1. session start record (collector git identity, config hash, clock source);
2. append-only chunk files of raw frames/payloads;
3. per-chunk SHA256;
4. manifest listing chunk order, first/last `local_received_at_utc`,
   message count, and chunk hashes;
5. derivative parquet/JSON parsed from raw bytes, referencing chunk
   identity + byte offset. Rebuildable. Not authoritative.

### 5.2 Crash / reconnect behavior

- On crash, un-fsynced tail may be lost. The next start opens a **new**
  session identity. It does not rewrite the previous session.
- Incomplete chunks are marked `INCOMPLETE` and never completed in
  place. A successor chunk may continue the stream.
- Reconnect is a new connection/session identity. Gap between last
  durable `local_received_at_utc` and first new receipt is recorded as a
  coverage hole, not filled by exchange event time.
- Sequence gaps, if the exchange provides sequence numbers, are recorded
  as missingness. They are not repaired by backfill into the raw log.
- Optional later backfill is a **separate** source with its own
  `local_received_at_utc` and must not be labeled as the original live
  receipt.

### 5.3 Clock

- `local_received_at_utc` is assigned at the moment the collector
  process has the bytes in hand, before JSON/protobuf parse.
- Host clock source and offset/NTP status should be recorded per
  session. This design does not claim host-clock truth beyond local
  receipt.

## 6. No forward science yet

During collection setup and while this design governs collection:

Do **not** test any relationship.
Do **not** compute:

- future return
- future MAE
- drawdown
- prediction
- beta
- classification

Do **not** use collected early observations to tune a later hypothesis.

Collection start must precede future `M04-FWD` preregistration /
execution. That later identity is not created here.

## 7. Next unit

```text
NEXT_UNIT = FORWARD_MARKET_OBSERVABILITY_V1_IMPLEMENTATION
```

Implementation is a later authorized unit. This file is design only.
'''