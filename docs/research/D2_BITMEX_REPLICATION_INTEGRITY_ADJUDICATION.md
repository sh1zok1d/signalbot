# D2 BitMEX replication integrity adjudication

**Unit:** `D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION`  
**Class:** `REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`

The original one-shot remains canonical history:

`D2_BITMEX_REPLICATION_INVALID`

Its RESULT bytes are not rewritten. `ORIGINAL_RERUN_AUTHORIZED = false`.

## Dropped timestamp-complete decisions

Exactly two timestamp-complete decisions fail frozen scientific row
construction. Both fail the predeclared `BTC_RET_24H == 0` ineligibility
rule inside frozen `btc_ret_24h` / `construct_discovery_row`. No raw
prices are reproduced here.

- `2018-03-17T00:05:00Z` (`2018`): `BTC_RET_24H_EQ_0`
- `2019-02-10T00:05:00Z` (`2019`): `BTC_RET_24H_EQ_0`

The diagnostic stops before `arithmetic_mae` / adverse severity. No
RV_ABSTENTION K, MU_RULE, controls, or gates were computed.

## Census vs scientific sample

`TIMESTAMP_COMPLETE_DECISION` is a 00:05Z decision whose feature, entry,
and 24h future 5m timestamps exist. The frozen census used that definition
and bound `EXPECTED_ELIGIBLE_N = 1069`.

`SCIENTIFICALLY_ELIGIBLE_D2_ROW` additionally requires frozen
`construct_discovery_row` success, including `BTC_RET_24H_EQ_0` and
`RV_LE_0_OR_NONFINITE`. That definition is older than the BitMEX run
(`zero_return_rows_ineligible = true` in the original prereg; same kernel
as D2 discovery).

`EXPECTED_ELIGIBLE_N = 1069` was therefore mechanically wrong before
execution: it counted timestamp-complete rows that the already-frozen
scientific constructor must drop. This is not an implementation bug, not
source corruption, and not a new post-outcome scientific choice.

## Trailing-250 authority

`TRAILING_HISTORY_AUTHORITY = VALID_CONSTRUCTED_ROWS`

Original D2 discovery `rv_abstention_mask` takes P90 over the previous 250
`DiscoveryRow` objects returned by `construct_discovery_row`. Rows that
return `None` never enter that sequence. The BitMEX evaluator reuses that
mask. Not timestamp-complete calendar decisions.

## Corrected sample identity

```
CORRECTED_CONSTRUCTED_N = 1317
CORRECTED_WARMUP_N = 250
CORRECTED_ELIGIBLE_N = 1067
CORRECTED_YEAR_2017_N = 341
CORRECTED_YEAR_2018_N = 363
CORRECTED_YEAR_2019_N = 363
CORRECTED_FIRST_T = 2017-01-24T00:05:00Z
CORRECTED_LAST_T = 2019-12-30T00:05:00Z
```

`1067 > 815`
(frozen feasibility floor). Power was not recomputed.

## Repair semantics

```
SCIENTIFIC_RULE_CHANGED = False
TARGET_CHANGED = False
THRESHOLD_CHANGED = False
COMPARATOR_CHANGED = False
DATA_CHANGED = False
ORIGINAL_PRIMARY_OUTCOME_COMPUTED = False
ORIGINAL_RANDOM_CONTROLS_COMPUTED = False
ORIGINAL_RERUN_AUTHORIZED = False
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = True
REPLICATION_RANDOM_SEED = 20260921125
NEW_RUN_IDENTITY = 8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43
EXECUTION_AUTHORIZED = False
```

A corrected execution is a new integrity-repair lineage, not a rescue
rerun of `b873d473…`. No execution permit is created in this unit.

## Program flags

```
D2_DISCOVERY_STATUS = PROMISING_PROTOTYPE
D2_REPLICATION_STATUS = INTEGRITY_REPAIR_PENDING_CORRECTED_EXECUTION
PROTECTED_2025_OPENED = False
PROTECTED_2026_OPENED = False
MARKET_07_CREATED = False
NEXT_UNIT = D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT
```
