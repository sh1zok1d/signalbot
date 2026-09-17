# MARKET-01 OI_EXPANSION_WEAK_CONTINUATION — one-shot canonical ARM

- **Status:** `ARMED_NOT_EXECUTED`
- **Unit ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION_ARM`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Date:** 2026-09-17

**Not a RESULT. Not an execution. Not outcome inspection.
Not B2-06, 2025, or 2026 authorization. Not V3. Not V4.**

Canonical machine-readable twin:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_ARM.json`.

This ARM authorizes **exactly one** canonical MARKET-01 execution
against the frozen prereg, the accepted implementation, and the bound
CORE/OI authorities. Creating this ARM does not consume it and does
not execute it.

```text
REVIEWED_IMPLEMENTATION_HEAD = 1019c5725a58c62d460276159a5683a202c1c3ea
REVIEWED_IMPLEMENTATION_TREE = 2a7a5ce74f9b0c419cf40093271df243ffb02d46
RUN_IDENTITY = f430399f46e6122a2633a34e99e9bd0ab8fe65c1baf9c05b5982551a4608739d

CANONICAL_EXECUTIONS_AUTHORIZED = 1
CANONICAL_EXECUTIONS_CONSUMED = 0
MARKET_01_ARMED = YES
MARKET_01_EXECUTED = NO
MARKET_01_OUTCOME_INSPECTED = NO

ARM_COMMIT_HEAD = UNSET_UNTIL_THIS_COMMIT
ARM_COMMIT_TREE  = UNSET_UNTIL_THIS_COMMIT
```

No rerun is pre-authorized. A failed execution must be adjudicated
under existing lifecycle rules; this ARM does not silently issue a
replacement reservation.

`MARKET_01_TEST_CALIBRATED = NO`. V3 is not the MARKET-01 test.
`DEFAULT_V4 = NO`. B2-06 remains blocked. Protected OOS remains
untouched.

The next and only next scientific action is one canonical MARKET-01
execution. Not this unit.
