# D4 BTC_ETH_RELATIVE_STRUCTURE

Adaptive discovery result. Not confirmatory.

## DISCOVERY_ID

```json
"D4"
```

## TERMINAL_CLASSIFICATION

```json
"BLOCKED_MISSING_LOCAL_DATA"
```

## SPEC_AUTHORITY

```json
"docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md} superseded in place by DISCOVERY_SPRINT_01_RED_TEAM_REVIEW, DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4, and DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX (latest explicit correction blocks are authority)"
```

## IMPLEMENTATION_COMMIT

```json
"26d8f7066533bcae7138d5a1952783f2a16f3c39"
```

## INTERVAL_USED

```json
"2020-02-01T00:05:00Z -> 2025-01-01T00:00:00Z exclusive"
```

## DATASET_IDENTITIES

```json
{
  "CORE_BTC_BINANCE_V0": "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415",
  "CORE_ETH_BINANCE_V0": "4b9c113f659e1c1ca71498096dfdc2628a1016346aed40e19020efb64c85ad15"
}
```

## SEEDS

```json
{
  "D4_NULL_SEED": 20260921104
}
```

## ROW_COUNTS

```json
{
  "N_PAIRS": null
}
```

## YEAR_BREAKDOWN

```json
{}
```

## PRIMARY_METRICS

```json
{}
```

## BASELINE_METRICS

```json
{
  "BLOCK_LENGTH": 20,
  "NULL": "BLOCK_BOOTSTRAP_PAIRED_RETURNS",
  "UNCONDITIONAL_CORRELATION": null
}
```

## PROTOTYPE_GATE_FIELDS

```json
{
  "LEAD_LAG_1DAY": "DEFERRED_FROM_SPRINT_01",
  "PRACTICAL_EXCESS_RANGE_FORMULA": "OBSERVED_CORRELATION_RANGE - NULL_RANGE_MEDIAN",
  "practical_gate": "PRACTICAL_EXCESS_RANGE >= 0.15",
  "statistical_gate": "observed rolling-corr variance > null 97.5th percentile"
}
```

## SEARCH_SURFACE_ATTEMPTED

```json
[
  "ROLLING_CORRELATION_90D"
]
```

## FILES_OPENED

```json
[]
```

## KNOWN_LIMITATIONS

```json
[
  "Two-asset precursor only; not cross-sectional panel structure.",
  "LEAD_LAG_1DAY deferred from Sprint 01.",
  "missing:CORE_BTC_BINANCE_V0_MONTHLY_PARQUET",
  "missing:CORE_ETH_BINANCE_V0_MONTHLY_PARQUET"
]
```

## PROTECTED_2025_OPENED

```json
false
```

## PROTECTED_2026_OPENED

```json
false
```
