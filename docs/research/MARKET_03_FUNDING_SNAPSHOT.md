# MARKET-03 DEDICATED FUNDING SNAPSHOT

- **Status:** `FUNDING_SNAPSHOT_READY`
- **Research ID:** `MARKET-03_PUBLIC_STRATEGY_REPLICATION`
- **Unit ID:** `MARKET_03_FUNDING_SNAPSHOT`
- **Date:** 2026-09-18
- **Verdict:** `A. FUNDING_SNAPSHOT_READY`

This unit constructs the dedicated immutable MARKET-03 funding authority
required by the frozen prereg. It does **not** modify the prereg, implement
the strategy, inspect outcomes, ARM, or execute MARKET-03.

Machine-readable twin:
`docs/research/MARKET_03_FUNDING_SNAPSHOT.json`
(SHA256 `870dd3974fa6565b8cca1399be59d100d60a87722d9942ec43eba5eee89e5af3`).

```text
PRE_SNAPSHOT_HEAD = 3f1722476927a13d4e1629510f12ed00f72ba3d8
PRE_SNAPSHOT_TREE = 50f2d54fe4ddfc7a6774808cc7110913ea0b978b
```

---

## 1. Source identity (from frozen acquisition records; not reconstructed)

Previously identified REST JSONL:

```text
SOURCE_PATH   = artifacts/research_data/MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0/canonical/BTCUSDT_UM_fundingRate_rest_authorized.jsonl
SOURCE_SHA256 = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
SOURCE_SIZE   = 442988
endpoint      = /fapi/v1/fundingRate
endpoint_used = https://www.binance.com/fapi/v1/fundingRate
symbol        = BTCUSDT
retrieval     = 2026-09-18T17:06:53Z
request       = [2019-09-01T00:00:00Z, 2025-01-01T00:00:00Z)
startTime_ms  = 1567296000000
endTime_excl  = 1735689600000
pages         = 6
limit         = 1000
```

Those bytes were re-hashed at snapshot construction and matched the
frozen acquisition/prereg identity exactly. B2-06 is **not** this
authority.

---

## 2. Dedicated dataset / snapshot

```text
FUNDING_DATASET_ID  = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
FUNDING_SNAPSHOT_ID = d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256 = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
FUNDING_ROWS        = 5819
FUNDING_TIME_BOUNDS = [2019-09-10T08:00:00Z, 2024-12-31T16:00:00Z]
schema              = fundingRate, fundingTime, symbol
```

Canonical JSONL is an identity copy of the source REST JSONL. For every
retained observation, `fundingTime` and `fundingRate` remain
string/integer identical to the source line. No rounding.

Git identity (raw/canonical JSONL remain gitignored):

| File | SHA256 |
|---|---|
| `docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/SNAPSHOT_d47b7b78.json` | `5cf01f672b2e2de2d6ce7966109d91a0fcfc82ec8dd08fe11fcf0b1321d3b210` |
| `docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/SOURCE_LEDGER_d47b7b78.json` | `7232016e568f06e8328034ee9f665301052267a13feb1645788af40bb395bef6` |
| `docs/research_data/MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0/QUALITY_REPORT_d47b7b78.json` | `01881f1762a4faaa80ba8e6c286165c01dadfc2d91869904c94463ccc20ddde2` |

Durability: `IDENTITY_PROVEN_AT_MATERIALIZATION_RAW_BYTES_NOT_GIT_RETAINED`.

Later ARM must reject any substitute whose `SNAPSHOT_ID`, source SHA256,
or canonical SHA256 differs.

---

## 3. Temporal coverage

Bounds come from frozen prereg semantics, not from strategy outcomes.

- Evaluation begins `2019-10-01T00:00:00Z`.
- Scientific snapshot terminates before `2025-01-01T00:00:00Z`.
- REST request started `2019-09-01`; first returned observation is
  `2019-09-10T08:00:00Z` (62 observations / 496 hours before evaluation).
- Last observation `2024-12-31T16:00:00Z`. The next 8h slot would be
  `2025-01-01T00:00:00Z` and is excluded.

Protected 2025/2026 OOS was not fetched or inspected.

This snapshot stores raw `fundingRate@fundingTime` only. It does **not**
calculate the later frozen 3-day mean, trailing 180-day percentile,
eligibility, EMA, trades, or performance quantities.

---

## 4. Generic validation (no strategy)

```text
schema                         = OK (fundingRate string, fundingTime int, symbol BTCUSDT)
finite fundingRate             = 5819 / 5819
valid fundingTime              = 5819 / 5819
chronological strictly increasing = YES
DUPLICATES
  duplicate fundingTime        = 0
  exact duplicate rows         = 0
  conflicting duplicates       = 0
GAPS
  expected 8h hour-floor events = 5819
  observed 8h hour-floor events = 5819
  missing expected 8h events    = 0
  unexpected hour-floor events  = 0
interval                       = 8h cadence with millisecond residuals
utc hours                      = 00 / 08 / 16 only
```

Material anomaly enumerated and **not repaired**:

```text
FUNDINGTIME_MILLISECOND_RESIDUAL
  count  = 2438
  min_ms = 1
  max_ms = 47
  policy = PRESERVE_RAW_FUNDINGTIME_DO_NOT_ROUND_TO_HOUR
```

---

## 5. fundingTime semantics (not upgraded)

```text
STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN
REPRODUCTION_FUNDINGTIME_ASSUMPTION   = ACCEPTABLE
```

For this LEVEL_2 reproduction only, `fundingTime` is treated as the
observation's historical availability timestamp because that matches the
pinned external implementation. This does **not** prove publication
latency and does **not** set `legal_available_at`.

---

## 6. Spot and prereg immutability

```text
SPOT_DATASET_ID     = MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0
SPOT_SNAPSHOT_ID    = 2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345
SPOT_DATA_SHA256    = e560bebb6ba9d070ee0fa58aaa5cf922caaa24d4b7e2b4eac8c7c0041c9495d4
SPOT_SNAPSHOT_UNCHANGED = YES

PREREG_MD_SHA256    = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256  = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
PREREG_UNCHANGED    = YES
```

The frozen prereg payload still records `FUNDING_SNAPSHOT_READY = NO` as
its freeze-time scientific bytes. This unit does not rewrite those bytes.
Current construction status is this document.

---

## 7. Outcome-blindness

```text
MARKET_03_STRATEGY_EXECUTED            = NO
MARKET_03_OUTCOMES_INSPECTED           = NO
MARKET_03_PARAMETER_SEARCH             = NO
MARKET_03_ARMED                        = NO
CANONICAL_EXECUTIONS_AUTHORIZED        = 0
CANONICAL_EXECUTIONS_CONSUMED          = 0
PROTECTED_OOS_TOUCHED                  = NO
```

This unit does **not** begin implementation, ARM, or MARKET-03 execution.

---

## 8. Verdict

Exactly one verdict:

**A. FUNDING_SNAPSHOT_READY**
