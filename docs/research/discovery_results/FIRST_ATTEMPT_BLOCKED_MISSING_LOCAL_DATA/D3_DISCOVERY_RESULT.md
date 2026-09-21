# D3 PATH_MORPHOLOGY

Adaptive discovery result. Not confirmatory.

## DISCOVERY_ID

```json
"D3"
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
  "CORE_BTC_BINANCE_V0": "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
}
```

## SEEDS

```json
{
  "D3_NULL_SURROGATE_SEED": 20260921103
}
```

## ROW_COUNTS

```json
{
  "N": 0
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
  "BLOCK_LENGTH": 12,
  "COMPANIONS": {},
  "COMPANION_BLOCK_LENGTHS": [
    6,
    24
  ],
  "NULL": "5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP"
}
```

## PROTOTYPE_GATE_FIELDS

```json
{
  "btc_side_used": false,
  "exactly_three_functionals": true,
  "high_low_used": false,
  "path_asymmetry_included": false,
  "practical_magnitude_threshold": "|emp_mean - surrogate_median| > 15% of |surrogate_median|",
  "statistical_threshold": "empirical mean outside surrogate-mean [2.5, 97.5]",
  "temporal_consistency_check": "at least 3 year-buckets same-direction vs surrogate median"
}
```

## SEARCH_SURFACE_ATTEMPTED

```json
[
  "MAX_UPSIDE_CLOSE_24H",
  "MAX_DOWNSIDE_CLOSE_24H",
  "TIME_TO_MAX_ABS_CLOSE_EXCURSION"
]
```

## FILES_OPENED

```json
[]
```

## KNOWN_LIMITATIONS

```json
[
  "Adaptive discovery on historically exposed 2020-2024 data.",
  "Unconditional close-path design; not a terminal-return card.",
  "missing:CORE_BTC_BINANCE_V0_MONTHLY_PARQUET"
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
