# D2 BitMEX replication prereg amendment V1

**Unit:** `D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1`  
**Kind:** identity amendment only. Historical prereg bytes are unchanged.

The original prereg remains the frozen historical contract that produced
the INVALID run. This amendment records the mechanically corrected
scientific sample identity for a possible later integrity-repair
execution. It does not change the candidate rule, target, threshold,
comparator, data, or seed.

```
ORIGINAL_RUN_IDENTITY = b873d473e5d5ef1394d161d557b1e0ca7602bfa92e6d78d8e80df8f4d1493d71
ORIGINAL_EXPECTED_N = 1069
CORRECTED_EXPECTED_N = 1067
CORRECTED_YEAR_2017_N = 341
CORRECTED_YEAR_2018_N = 363
CORRECTED_YEAR_2019_N = 363
CORRECTED_FIRST_T = 2017-01-24T00:05:00Z
CORRECTED_LAST_T = 2019-12-30T00:05:00Z
SCIENTIFIC_RULE_CHANGED = False
TARGET_CHANGED = False
THRESHOLD_CHANGED = False
COMPARATOR_CHANGED = False
DATA_CHANGED = False
REPLICATION_RANDOM_SEED = 20260921125
EXECUTION_AUTHORIZED = False
ORIGINAL_RERUN_AUTHORIZED = False
```

`EXACT_REASON_FOR_AMENDMENT`: ORIGINAL_EXPECTED_N counted timestamp-complete decisions. Frozen construct_discovery_row already excludes BTC_RET_24H_EQ_0. Two timestamp-complete decisions are ineligible under that predeclared rule. Historical prereg bytes are preserved.
