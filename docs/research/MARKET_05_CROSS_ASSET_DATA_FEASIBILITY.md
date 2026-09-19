# MARKET-05 cross-asset data / temporal feasibility

- **Status:** `MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE`
- **Unit ID:** `MARKET_05_CROSS_ASSET_DATA_FEASIBILITY`
- **Research ID:** `MARKET-05_CROSS_ASSET_CONFIRMATION_ADVERSE_PATH_RISK`
- **Date:** 2026-09-19
- **Machine-readable twin:** [`MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.json`](MARKET_05_CROSS_ASSET_DATA_FEASIBILITY.json)
- **Candidate freeze:** [`MARKET_05_CROSS_ASSET_CANDIDATE.md`](MARKET_05_CROSS_ASSET_CANDIDATE.md)

This unit audits whether a clean Binance USD-M BTCUSDT + ETHUSDT
historical construction can support a later MARKET-05 experiment. It does
**not** preregister, execute, implement a scientific evaluator, or inspect
scientific outcomes.

```text
feasibility_classification = MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE
btc_dataset = CORE_BTC_BINANCE_V0
eth_dataset = CORE_ETH_BINANCE_V0
same_support_required = true
common_decision_timestamps_feasible = true
scientific_outcomes_inspected = false
protected_oos_touched = false
SIGNALBOT_PROTECTED_OOS_UNTOUCHED = YES
execution_authorized = false
full_preregistration_frozen = false
implementation_frozen = false
armed = false
```

---

## 1. Preferred construction

Preferred historical data is first-party Binance USD-M perpetual:

```text
TARGET  = BTCUSDT
CONTEXT = ETHUSDT
venue   = Binance
instrument_class = USD_M_FUTURES
source_family = official Vision klines
native_interval = 1m
```

Do **not** mix BTC perpetual + ETH spot, or BTC Binance + ETH another
exchange. The preferred construction did **not** fail. No substitute
venue or instrument class is adopted.

---

## 2. BTC authority remains CORE_BTC_BINANCE_V0

`CORE_BTC_BINANCE_V0` remains the BTC authority. It is not redefined.

| Item | Recorded fact |
|---|---|
| Dataset | `CORE_BTC_BINANCE_V0` |
| Status | `ACCEPTED_FOR_DISCOVERY`; `confirmatory_authorized = false` |
| Snapshot | `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415` |
| Venue / instrument | Binance USD-M perpetual `BTCUSDT` |
| Native interval | 1m official klines |
| Evidence tier | `OFFICIAL_ARCHIVE` / `HISTORICAL_COMPARABLE` |
| Frozen range | `[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)` |
| Observed first / last open | `2020-01-01T00:00:00Z` … `2026-08-25T23:59:00Z` |
| Accepted 1m rows | `3,497,760` |
| Missing minutes | `0` |
| Duplicates | `0` |
| Source objects | 79 monthly (`2020-01`..`2026-07`) + 25 daily (`2026-08-01`..`2026-08-25`) |

Manifest: `docs/manifests/CORE_BTC_BINANCE_V0.yaml`.
Contract: `docs/CORE_BTC_BINANCE_V0_CONTRACT.md`.
Evidence: `docs/research_data/CORE_BTC_BINANCE_V0/`.

```text
BTC_BAR_AVAILABILITY_SEMANTICS = bar_end_exclusive
available_at = open_time + 60s
eligible iff bar_end_exclusive <= T
close_time is last millisecond inside the source bar
close_time is not available_at
```

Do not infer availability from a bar that has not fully closed.
`feature_information_time <= T` is required.

---

## 3. ETH companion identity CORE_ETH_BINANCE_V0

ETH requires a new frozen companion identity. It does **not** silently
redefine `CORE_BTC_BINANCE_V0`.

```text
dataset_id = CORE_ETH_BINANCE_V0
status = SOURCE_INVENTORY_BOUND_NOT_MATERIALIZED_NOT_ACCEPTED
research_authorized = false
confirmatory_authorized = false
accepted_for_discovery = false
```

| Item | Bound fact |
|---|---|
| Provider | Binance |
| Market type | `USD_M_FUTURES` |
| Instrument | `ETHUSDT` |
| Data type | official Vision `klines` |
| Native interval | `1m` |
| Archive root | `https://data.binance.vision/data/futures/um` |
| Schema | same 12-column USD-M kline schema as CORE BTC |
| Target range | `[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)` |
| Object inventory | 104/104 expected ZIP + 104/104 CHECKSUM objects present |
| Monthly objects | `2020-01` through `2026-07` (79) |
| Daily objects | `2026-08-01` through `2026-08-25` (25) |
| Checksum filename mismatches | `0` |
| Probe first open | `2020-01-01T00:00:00Z` |
| Probe last open | `2026-08-25T23:59:00Z` |
| Probe last `bar_end_exclusive` | `2026-08-26T00:00:00Z` |
| Full continuity audit | **not complete** |
| Accepted 1m rows | **unset** (not accepted) |
| Expected 1m rows if complete | `3,497,760` |

Planning manifest: `docs/manifests/CORE_ETH_BINANCE_V0.yaml`.
Source inventory: `docs/research_data/CORE_ETH_BINANCE_V0/SOURCE_INVENTORY.json`.
Inventory SHA256:
`033a06428d5d2a56fcde23a8fe64ebe4d8afa2f57d5d3263e3d0b9c6db38e49e`.

```text
ETH_BAR_AVAILABILITY_SEMANTICS = bar_end_exclusive
available_at = open_time + 60s
eligible iff bar_end_exclusive <= T
close_time is last millisecond inside the source bar
close_time is not available_at
legal_availability_convention = CORE_BTC_BINANCE_V0 bar-end-exclusive contract
```

ETH extra monthly object `ETHUSDT-1m-2026-08.zip` exists on Vision but
is **outside** the CORE cutoff and is not adopted. Extending the cutoff
would be a new dataset revision.

---

## 4. Outcome-blind ETH source-capability probe

Six ETH objects were downloaded and audited for timestamp identity,
schema, completeness, duplicates, and checksum verification only. Price
values were not retained. Returns, MAE, future outcomes, confirmation
buckets, and ETH–BTC predictive statistics were not computed.

| Period | Class | Rows | Missing | Duplicates | First open | Last `bar_end_exclusive` | Checksum |
|---|---|---:|---:|---:|---|---|---|
| 2020-01 | monthly | 44640 | 0 | 0 | 2020-01-01T00:00:00Z | 2020-02-01T00:00:00Z | VERIFIED |
| 2021-05 | monthly | 44640 | 0 | 0 | 2021-05-01T00:00:00Z | 2021-06-01T00:00:00Z | VERIFIED |
| 2024-03 | monthly | 44640 | 0 | 0 | 2024-03-01T00:00:00Z | 2024-04-01T00:00:00Z | VERIFIED |
| 2026-07 | monthly | 44640 | 0 | 0 | 2026-07-01T00:00:00Z | 2026-08-01T00:00:00Z | VERIFIED |
| 2026-08-01 | daily | 1440 | 0 | 0 | 2026-08-01T00:00:00Z | 2026-08-02T00:00:00Z | VERIFIED |
| 2026-08-25 | daily | 1440 | 0 | 0 | 2026-08-25T00:00:00Z | 2026-08-26T00:00:00Z | VERIFIED |

2026-07 and 2026-08 objects were inspected only for file existence,
open-time grid completeness, and checksum identity. They were **not**
used to choose normalization, lookback, horizon, year retention, or any
scientific parameter.

```text
outcome_blind_identifiability_diagnostic_performed = false
```

---

## 5. Common support

```text
BTC_COVERAGE = [2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)
ETH_COVERAGE = [2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)
COMMON_COVERAGE = [2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)
COMMON_DECISION_TIMESTAMPS_FEASIBLE = true
same_support_required = true
```

Both assets can be sampled on identical decision timestamps `T` under
the same bar-end-exclusive rule: use the latest BTC and ETH 1m bars
with `bar_end_exclusive <= T`. The future predicate is
`feature_information_time <= T` for both BTC and ETH.

This unit identifies common historical coverage only. It does **not**
select the scientific development window. Later preregistration must
freeze that window before outcomes are computed. Protected 2025/2026
OOS remains untouched for science.

Duplicate handling follows the CORE contract: never silent last-write-wins;
identical duplicates may be canonicalized only in a documented step;
conflicting duplicates fail closed.

Missing bars are not filled, not synthesized, and not repaired from the
other asset. If BTC or ETH is missing at `T`, the row is ineligible for
**both** BASELINE and CANDIDATE.

---

## 6. Retrieval / materialization procedure

Later ETH materialization must reuse the existing CORE BTC pipeline
semantics with symbol `ETHUSDT`, the same frozen range, the same monthly
then daily packaging, source checksum verification, and bar-end-exclusive
availability. It must not invent a new availability clock.

This unit did **not** rematerialize a full ETH parquet snapshot and did
**not** accept `CORE_ETH_BINANCE_V0` for discovery. Rematerialization and
acceptance are later gates before ARM/execution. They are ordinary
dataset work, not an unresolved temporal-authority block.

---

## 7. Classification

```text
feasibility_classification = MARKET_05_CANDIDATE_FROZEN_DATA_FEASIBLE
NEXT_UNIT = OUTCOME_BLIND_MARKET_05_EXACT_PREREGISTRATION
```

A is returned because:

- the MARKET-05 identity is cleanly frozen;
- BTC/ETH same-exchange same-instrument data exists;
- common object-level support covers the full CORE window;
- bar-end-exclusive availability is already an accepted Signalbot
  convention for this source family;
- probe months are calendar-complete;
- no unresolved fatal data issue blocks writing an outcome-blind
  preregistration that names `CORE_ETH_BINANCE_V0` and requires
  materialization/acceptance before execution.

Residual (not a fatal block): full ETH 104-object continuity is not yet
accepted. Later prereg may bind the companion identity now and must
require acceptance before ARM/execution.
