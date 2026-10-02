# GV0V03L40 shortlist final readiness

**Status:** `COMPLETE`
**Date:** 2026-10-02

Outcome-blind readiness only. No market target was computed. No card was repriced after a compiler result. C033 was read from its sealed V2 artifact and was not recompiled.

| Card | Class | Final | Blockers |
|---|---|---|---|
| C005 | CONDITIONAL | `PIT_BLOCKED` | PERP_LISTING_HISTORY_UNVERIFIED |
| C024 | CONDITIONAL | `DATA_BLOCKED` | ORDER_BOOK_DEPTH_HISTORY |
| C031 | ATOMIC | `PIT_BLOCKED` | ADDRESS_LABEL_PROVENANCE_AND_EXCHANGE_POLICY_POINT_IN_TIME |
| C033 | COMPOSITE | `TERMINAL_NOT_PREREGISTRABLE` | PRIMARY_MECHANISM_SUPPORT_ZERO, ALPHA_UNATTAINABLE, PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED |
| C037 | ATOMIC | `PIT_BLOCKED` | POINT_IN_TIME_SUPPLY_HISTORY |

TEST_QUEUE = []
PREREG_DRAFTS_CREATED = []
TEST_IMPLEMENTATION_SPECS_CREATED = []
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
PAID_DATA_SPEND_USD = 0
LLM_CALLS = 0

## C005

The public delisting catalog's oldest notice is 2022-02-24. USD-M history required by the card starts in 2019-09. data.binance.vision has no exchangeInfo snapshot archive. A live exchangeInfo snapshot was not used.

```
CLASS = CONDITIONAL
DATA_STATUS = PUBLIC_CMS_NOT_A_PIT_REGISTRY
PIT_STATUS = PIT_BLOCKED
PRIMARY_VARIANT = null
NOMINAL_N = null
MECHANISM_ACTIVE_N = null
MECHANISM_INACTIVE_N = null
ALPHA_ATTAINABLE = null
MIN_ATTAINABLE_P = null
GV0R02_V2_STATUS = NOT_COMPILED
BLOCKERS = PERP_LISTING_HISTORY_UNVERIFIED
OWNER_DECISION_REQUIRED = null
FINAL_READINESS = PIT_BLOCKED
NEXT_UNIT = STOP. A later unit needs a pinned PIT launch and delisting archive for 2019-09..2024-12, including delisted USD-M contracts, and historical onboardDate snapshots. Do not use a live exchangeInfo snapshot.
VARIANTS = 4
```

## C024

USD-M daily bookDepth for BTCUSDT and ETHUSDT has no 2022 objects. The first listed key is 2023-01-01 for both symbols. The frozen window was not shortened. Tardis was not bought.

```
CLASS = CONDITIONAL
DATA_STATUS = DATA_BLOCKED
PIT_STATUS = NOT_ASSESSED_COVERAGE_ABSENT
PRIMARY_VARIANT = null
NOMINAL_N = null
MECHANISM_ACTIVE_N = null
MECHANISM_INACTIVE_N = null
ALPHA_ATTAINABLE = null
MIN_ATTAINABLE_P = null
GV0R02_V2_STATUS = NOT_COMPILED
BLOCKERS = ORDER_BOOK_DEPTH_HISTORY
OWNER_DECISION_REQUIRED = null
FINAL_READINESS = DATA_BLOCKED
NEXT_UNIT = STOP. Do not shorten discovery to 2023-01 and do not buy Tardis L2.
VARIANTS = 8
```

## C031

No as-of Binance BTC deposit-address label archive and no dated confirmation-count policy were found. Aggregated exchange-flow metrics are not address attribution. Today's labels and today's confirmation count were not used.

```
CLASS = ATOMIC
DATA_STATUS = LABEL_AND_POLICY_ARCHIVE_ABSENT
PIT_STATUS = PIT_BLOCKED
PRIMARY_VARIANT = null
NOMINAL_N = null
MECHANISM_ACTIVE_N = null
MECHANISM_INACTIVE_N = null
ALPHA_ATTAINABLE = null
MIN_ATTAINABLE_P = null
GV0R02_V2_STATUS = NOT_COMPILED
BLOCKERS = ADDRESS_LABEL_PROVENANCE_AND_EXCHANGE_POLICY_POINT_IN_TIME
OWNER_DECISION_REQUIRED = null
FINAL_READINESS = PIT_BLOCKED
NEXT_UNIT = STOP. A later unit needs as-of-dated Binance BTC deposit-address labels and a dated confirmation-count policy. Do not use today's labels or today's confirmation count.
VARIANTS = 8
```

## C033

Canonical V2 result. Active support is 0 on 1383 inactive kept shocks. Orbit size is 1 and alpha is not attainable. No ALL3 or threshold change was attempted.

```
CLASS = COMPOSITE
DATA_STATUS = OUTCOME_BLIND_COUNT_RECORDED
PIT_STATUS = NOT_THE_BINDING_CONSTRAINT
PRIMARY_VARIANT = {'SHOCK_SIGMA': 3, 'TAKER_BAND': 'p1_p99', 'POST_WINDOW_H': 6}
NOMINAL_N = 1383
MECHANISM_ACTIVE_N = 0
MECHANISM_INACTIVE_N = 1383
ALPHA_ATTAINABLE = false
MIN_ATTAINABLE_P = 1.0
GV0R02_V2_STATUS = DEFINITION_INCOMPLETE
BLOCKERS = PRIMARY_MECHANISM_SUPPORT_ZERO, ALPHA_UNATTAINABLE, PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED
OWNER_DECISION_REQUIRED = null
FINAL_READINESS = TERMINAL_NOT_PREREGISTRABLE
NEXT_UNIT = STOP / NOT_PREREGISTRABLE_UNDER_FROZEN_DESIGN
VARIANTS = 0
```

## C037

No pinned point-in-time circulating supply. The named volume_share_proxy variant has no frozen arithmetic, so it was not selected and no turnover estimator was invented.

```
CLASS = ATOMIC
DATA_STATUS = PIT_SUPPLY_HISTORY_ABSENT
PIT_STATUS = PIT_BLOCKED
PRIMARY_VARIANT = null
NOMINAL_N = null
MECHANISM_ACTIVE_N = null
MECHANISM_INACTIVE_N = null
ALPHA_ATTAINABLE = null
MIN_ATTAINABLE_P = null
GV0R02_V2_STATUS = NOT_COMPILED
BLOCKERS = POINT_IN_TIME_SUPPLY_HISTORY
OWNER_DECISION_REQUIRED = null
FINAL_READINESS = PIT_BLOCKED
NEXT_UNIT = STOP. A later unit needs daily circulating supply as known on each date, including unlock revisions. The volume-share proxy was not selected because the frozen card does not define its arithmetic.
VARIANTS = 8
```
