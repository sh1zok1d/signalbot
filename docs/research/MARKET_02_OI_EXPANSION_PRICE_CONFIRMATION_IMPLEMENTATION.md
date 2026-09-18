# MARKET-02 implementation identity

- **Status:** `IMPLEMENTED / NOT_FROZEN / NOT_ARMED / NOT_EXECUTED`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Date:** 2026-09-18
- **Frozen prereg HEAD before implementation:** `aebdb9570f08c7a05149336d90f6fcd11541d10d`

Implemented the frozen MARKET-02 scientific mapping without changing the
preregistered claim.

Implementation:
- `scripts/research/market_02_oi_expansion_price_confirmation_lib.py`
- `tests/research/test_market_02_implementation.py`

The implementation reuses the semantics-preserving MARKET-01 fast episode
constructor for the shared PIT price/OI clocks, 30d normalization, overlap,
PRE_VOL_60 and outcome geometry. MARKET-02 then applies its own frozen
population and estimand:

```text
population = QUALIFYING_IMPULSE AND OI_EXPANSION
candidate  = continuation_ratio > 0.25
baseline   = continuation_ratio <= 0.25
outcome    = - MARKET-01 reversal_return
           = D * ln(close(T+60m)/close(T))
```

The evaluator implements the frozen stratified two-group OLS, exact rank
guard, stationary bootstrap identity and seed, support floors, DETECTED rule,
and prospective LOEO/concentration downgrade.

Bound MARKET-02 snapshot execution remains explicitly refused. This unit does
not create ARM/reservation/RESULT authority and does not inspect real
MARKET-02 outcomes or protected OOS.

```text
MARKET_02_PREREG_FROZEN = YES
MARKET_02_IMPLEMENTED = YES
MARKET_02_IMPLEMENTATION_FROZEN = NO
MARKET_02_ARMED = NO
MARKET_02_EXECUTED = NO
MARKET_02_TEST_CALIBRATED = NO
PROTECTED_OOS_TOUCHED = NO
DEFAULT_V4 = NO
B2_06_EXECUTION_AUTHORIZED = NO
```

Next gate: one narrow independent implementation review against the frozen
prereg. If accepted, freeze implementation and ARM separately. Do not inspect
real MARKET-02 outcomes during review.
