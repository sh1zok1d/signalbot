# SEED-0001 prospective confirmation — closed before start

**Status:** `APPEND_ONLY_CLOSURE_RECORD`
**Recorded:** 2026-10-03
**Machine-readable twin:** `SEED0001_PROSPECTIVE_CLOSURE_V1.json`
**Concerns:** test family `TF-SEED0001-RD-PROSP1`, frozen in `SEED0001_REGULAR_DIVERGENCE_PREREG.md` §9 and its twin `SEED0001_REGULAR_DIVERGENCE_PREREG.json`, and registered in `SCIENTIFIC_TEST_LEDGER.json` as `REGISTERED_NOT_STARTED`.

The preregistration and the ledger entry are not deleted or rewritten. Following the ledger's rule, an entry is closed once, with a result digest. This closure has no result, so the ledger entry stays as the registration record. This file and the atlas carry the current status.

```
TF-SEED0001-RD-PROSP1 = CLOSED_BEFORE_START
REASON = superseded by the divergence program closure (owner routing decision, 2026-10-03)
```

## Facts

- **Execution never started.**
  - No permit was issued.
  - No detector ran on the prospective cohort.
  - No eligibility count was taken.
- **No prospective outcome was ever opened.** The cohort is BTC episodes with decision time ≥ `2026-10-05T00:00Z`. That date has not been reached as of this record, so no prospective episode exists.
- **No confirmation surface was consumed.** Prospective BTCUSDT decisions from 2026-10-05 remain unspent, and they are not reserved for this test.
- **What closed it.** The owner closed the divergence / selling-exhaustion line on 2026-10-03: `PROSPECTIVE_DIVERGENCE_STREAM_ACTIVE = false`, and no new divergence or exhaustion unit, SEED or prospective stream may start (`AGENTS.md`; `docs/CURRENT_RESEARCH_STATE.md`, final owner routing decision).

## Restarting

A restart would be a new unit with its own registration, a new `TEST_FAMILY_ID` (the ledger never reuses one) and an explicit owner permit. It cannot reopen this test family.

## Atlas

The unit `SEED-0001-PROSP` has state `CLOSED_BEFORE_START`.
