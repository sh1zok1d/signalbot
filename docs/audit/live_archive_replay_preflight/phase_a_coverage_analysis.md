# Live-archive replay preflight — Phase A coverage analysis

Coverage classification of the owner-run read-only export. Detector events, episode counts, and forward outcomes were not computed. Production was not queried by this analysis.

- EXPORT_HASH_VERIFICATION: `True`
- ARCHIVE_OBSERVED_START: `2026-07-17T19:27:00Z`
- ARCHIVE_OBSERVED_END: `2026-09-29T07:26:00Z`
- TOTAL_5M_BUCKETS: `21312` (`2026-07-17T00:00:00Z` through `2026-09-28T23:55:00Z`)
- CORE_FAMILIES: `price_structure, oi, volume`
- PIT required for: `volume, taker_flow`
- CONNECTIVITY_EVENT_COUNT: `0`
- CONNECTIVITY_STATUS_INTERPRETATION: `NO_EVIDENCE_OF_OUTAGE_HEARTBEAT_NOT_HISTORICALLY_PROVABLE`
- LIQUIDATION_HISTORICAL_HEALTH_PROVABLE: `False`
- FULL_CURRENT_DETECTOR_REPLAY_ELIGIBILITY: `NOT_ELIGIBLE`
- PHASE_A_DECISION: `ARCHIVE_PARTIALLY_ELIGIBLE_FOR_EVENT_FAMILY_REPLAY`
- SOURCE_SEMANTICS_CHANGES: `False`
- REPLAY_AUTHORIZED: `False`
- Quorum buckets starting before the first live kline: `{"oi": {"count": 1, "timestamps": ["2026-07-17T19:25:00Z"]}, "price_structure": {"count": 0, "timestamps": []}, "taker_flow": {"count": 0, "timestamps": []}, "volume": {"count": 0, "timestamps": []}}`

A 5-minute bucket can start before the first live 1-minute kline and still contain live observations from later in that bucket. Those buckets are live rows. They are not lookback rows and they are not backfill.

## Per venue

- `binance` 5/5 `21072` (0.988739) OI>=2 `21076` (0.988926) mixed OI units `0` PIT `0` (0.0) liquidation rows present `True` longest price ineligible `234` price gaps after first eligible `3` (gt 1 bucket `1`) longest OI ineligible `233` OI gaps after first eligible `1` (gt 1 bucket `1`)
- `bybit` 5/5 `21064` (0.988363) OI>=2 `21076` (0.988926) mixed OI units `0` PIT `0` (0.0) liquidation rows present `True` longest price ineligible `234` price gaps after first eligible `11` (gt 1 bucket `1`) longest OI ineligible `233` OI gaps after first eligible `1` (gt 1 bucket `1`)
- `okx` 5/5 `21062` (0.98827) OI>=2 `21076` (0.988926) mixed OI units `0` PIT `0` (0.0) liquidation rows present `False` longest price ineligible `234` price gaps after first eligible `13` (gt 1 bucket `1`) longest OI ineligible `233` OI gaps after first eligible `1` (gt 1 bucket `1`)

## OI units and PIT

- Live OI units: `{"binance": ["base"], "bybit": ["base"], "okx": ["contracts"]}`
- Live OI unit transitions: `{"binance": 0, "bybit": 0, "okx": 0}`
- PIT: `{"history_rows_by_venue": {"binance": "no_history_rows", "bybit": "no_history_rows", "okx": "no_history_rows"}, "pit_history_present_bucket_rows": 0}`
- Taker buy/sell splits meet venue quorum on the counted buckets. Taker notional stays ineligible because `exchange_instrument_history` has no PIT row. That blocks `TAKER_FLOW_EXTREME_*` only.
- Volume notional stays ineligible on every bucket for the same missing PIT history. That blocks `POSITION_BUILDUP_COMPRESSION` and `CORE_FAMILIES` usability. It does not block `PRICE_OI_CONTRACTION_*`.

## Predicates

- `bar_5_of_5_quorum_buckets`: `21074`
- `bar_5_of_5_quorum_fraction`: `0.988833`
- `price_feature_quorum_buckets`: `21074`
- `oi_ge_2_quorum_buckets`: `21076`
- `oi_ge_2_quorum_fraction`: `0.988926`
- `oi_eligible_quorum_buckets`: `21076`
- `taker_split_complete_quorum_buckets`: `21074`
- `taker_split_complete_quorum_fraction`: `0.988833`

## Family quorum

- `price_structure` eligible `21074` (0.988833) quorum-and-mature `12434` first quorum `2026-07-17T19:30:00Z` first mature `2026-08-16T19:30:00Z`
- `oi` eligible `21076` (0.988926) quorum-and-mature `12436` first quorum `2026-07-17T19:25:00Z` first mature `2026-08-16T19:25:00Z`
- `volume` eligible `0` (0.0) quorum-and-mature `0` first quorum `None` first mature `None`
- `taker_flow` eligible `0` (0.0) quorum-and-mature `0` first quorum `None` first mature `None`

## Maturity

- FIRST_MATURE_PRICE_TIMESTAMP: `2026-08-16T19:30:00Z`
- FIRST_MATURE_OI_TIMESTAMP: `2026-08-16T19:25:00Z`
- FIRST_MATURE_VOLUME_TIMESTAMP: `None`
- FIRST_MATURE_TAKER_TIMESTAMP: `None`
- FIRST_MATURE_LIQUIDATION_TIMESTAMP: `None`

## Event families

The longest ineligible run includes the prefix before the first mature bucket. Interior gap counts do not include that prefix or a trailing suffix. A gap greater than 1 hour is longer than 12 buckets. A gap greater than 1 day is longer than 288 buckets.

- `PRICE_OI_CONTRACTION_DOWN` = `PARTIALLY_REPLAYABLE_WITH_INTERVAL` first `2026-08-16T19:30:00Z` last `2026-09-28T23:55:00Z` buckets `12434` fraction `0.583427` intervals `2` blockers `['INTERIOR_COVERAGE_GAPS']` longest ineligible `44370m` interior gaps `1` gt_1_bucket `1` gt_1_hour `0` gt_1_day `0`
  - interval `2026-08-16T19:30:00Z` through `2026-09-25T12:40:00Z` (11439 buckets)
  - interval `2026-09-25T13:05:00Z` through `2026-09-28T23:55:00Z` (995 buckets)
  - interior gap `2026-09-25T12:45:00Z` through `2026-09-25T13:00:00Z` (4 buckets)
- `PRICE_OI_CONTRACTION_UP` = `PARTIALLY_REPLAYABLE_WITH_INTERVAL` first `2026-08-16T19:30:00Z` last `2026-09-28T23:55:00Z` buckets `12434` fraction `0.583427` intervals `2` blockers `['INTERIOR_COVERAGE_GAPS']` longest ineligible `44370m` interior gaps `1` gt_1_bucket `1` gt_1_hour `0` gt_1_day `0`
  - interval `2026-08-16T19:30:00Z` through `2026-09-25T12:40:00Z` (11439 buckets)
  - interval `2026-09-25T13:05:00Z` through `2026-09-28T23:55:00Z` (995 buckets)
  - interior gap `2026-09-25T12:45:00Z` through `2026-09-25T13:00:00Z` (4 buckets)
- `POSITION_BUILDUP_COMPRESSION` = `BLOCKED` first `None` last `None` buckets `0` fraction `0.0` intervals `0` blockers `['VOLUME_PIT_NOTIONAL_NEVER_ELIGIBLE']` longest ineligible `106560m` interior gaps `0` gt_1_bucket `0` gt_1_hour `0` gt_1_day `0`
- `TAKER_FLOW_EXTREME_BUY` = `BLOCKED` first `None` last `None` buckets `0` fraction `0.0` intervals `0` blockers `['TAKER_FLOW_PIT_NOTIONAL_NEVER_ELIGIBLE']` longest ineligible `106560m` interior gaps `0` gt_1_bucket `0` gt_1_hour `0` gt_1_day `0`
- `TAKER_FLOW_EXTREME_SELL` = `BLOCKED` first `None` last `None` buckets `0` fraction `0.0` intervals `0` blockers `['TAKER_FLOW_PIT_NOTIONAL_NEVER_ELIGIBLE']` longest ineligible `106560m` interior gaps `0` gt_1_bucket `0` gt_1_hour `0` gt_1_day `0`
- `LIQUIDATION_STRESS_LONG` = `INSUFFICIENT_EVIDENCE` first `None` last `None` buckets `0` fraction `0.0` intervals `0` blockers `['CONNECTIVITY_LOG_EMPTY_HEARTBEAT_NOT_HISTORICALLY_PROVABLE']` longest ineligible `106560m` interior gaps `0` gt_1_bucket `0` gt_1_hour `0` gt_1_day `0`
- `LIQUIDATION_STRESS_SHORT` = `INSUFFICIENT_EVIDENCE` first `None` last `None` buckets `0` fraction `0.0` intervals `0` blockers `['CONNECTIVITY_LOG_EMPTY_HEARTBEAT_NOT_HISTORICALLY_PROVABLE']` longest ineligible `106560m` interior gaps `0` gt_1_bucket `0` gt_1_hour `0` gt_1_day `0`

## Product semantics

- NO ACTIVE EVENTS reproducible: `False`
- NO ACTIVE EVENTS blocker: `FAMILY_UNUSABLE:volume`
- DATA DEGRADED volume reason follows from coverage: `True`
- Full status machine replayable: `False`
- Status gates absent from the export: `['materialized', 'stale_barrier', 'evaluation_fresh', 'ingestion_heartbeat']`

## Blockers

- `INTERIOR_COVERAGE_GAPS`
- `VOLUME_PIT_NOTIONAL_NEVER_ELIGIBLE`
- `TAKER_FLOW_PIT_NOTIONAL_NEVER_ELIGIBLE`
- `CONNECTIVITY_LOG_EMPTY_HEARTBEAT_NOT_HISTORICALLY_PROVABLE`
- `CORE_FAMILY_VOLUME_NEVER_USABLE`
- `FULL_PRODUCT_STATUS_GATES_NOT_IN_EXPORT`

NEXT_UNIT: `{"families": ["PRICE_OI_CONTRACTION_DOWN", "PRICE_OI_CONTRACTION_UP"], "replay_authorized": false, "scope": "Isolated non-production replay of only the listed families on their reported intervals. Do not replay blocked or insufficient families, do not compute episode counts or P4 outcomes, and do not touch production.", "unit": "LIVE_ARCHIVE_PRICE_OI_FAMILY_REPLAY_ISOLATED_NON_PRODUCTION"}`

Liquidation code-path quorum, which treats an empty connectivity log as no outage, covers `21074` buckets in `2` interval(s), with `1` interior gap(s). That count is not historical feed-health proof and is not liquidation replay eligibility.

Empty connectivity is no evidence of an outage and is not historical proof of a healthy liquidation feed. Backfill rows were not substituted for live rows. Current instrument metadata was not used as PIT. A 5-minute bucket needs all 5 live minute bars. Open interest needs at least two live observations in one unit. Venue quorum is 2.
