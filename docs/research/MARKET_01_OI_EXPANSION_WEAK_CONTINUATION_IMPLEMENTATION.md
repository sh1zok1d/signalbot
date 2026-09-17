# MARKET-01 implementation identity

- **Status:** `IMPLEMENTED_NOT_ARMED`
- **Research ID:** `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`
- **Date:** 2026-09-17

This unit implements the frozen outcome-blind MARKET-01 contract. It is
not an ARM, not execution, and not a RESULT.

Scientific authority remains:

- `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md`
- `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json`
- freeze: `docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md`

Those prereg/freeze bytes are unchanged. Bound CORE/OI snapshot
evaluation is refused. Tests use synthetic fixtures only.

Modules:

- `scripts/research/market_01_oi_expansion_weak_continuation_authority.py`
- `scripts/research/market_01_oi_expansion_weak_continuation_lib.py`

`MARKET_01_TEST_CALIBRATED = NO`. V3 is not the MARKET-01 test.
`DEFAULT_V4 = NO`. B2-06 remains blocked.

Next lifecycle state: independent implementation review against the
frozen prereg. Not ARM. Not execution.
