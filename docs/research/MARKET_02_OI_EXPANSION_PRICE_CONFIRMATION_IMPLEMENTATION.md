# MARKET-02 OI_EXPANSION_PRICE_CONFIRMATION — implementation record

- **Status:** `IMPLEMENTED_NOT_ARMED`
- **Research ID:** `MARKET-02_OI_EXPANSION_PRICE_CONFIRMATION`
- **Date:** 2026-09-18
- **Scientific authority:** `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.md`
- **Machine-readable twin:** `docs/research/MARKET_02_OI_EXPANSION_PRICE_CONFIRMATION_PREREG.json`
- **Implementation module:** `scripts/research/market_02_oi_expansion_price_confirmation_lib.py`

```text
prereg frozen                 = YES
implementation complete       = YES
implementation frozen         = NO
armed                         = NO
executed                      = NO
outcome inspection            = NO
protected OOS touched         = NO
MARKET_02_TEST_CALIBRATED     = NO
```

This unit implements the frozen outcome-blind MARKET-02 scientific
pipeline and tests. It does not freeze the implementation, ARM, execute
on bound CORE/OI snapshots, enumerate real MARKET-02 episodes, inspect
MARKET-02 outcomes, create a RESULT, touch protected 2025/2026 OOS, use
funding, unblock B2-06, or rerun MARKET-01.

## Scientific identity (not MARKET-01)

MARKET-02 is a sequential follow-up after the sealed MARKET-01
`NO_EVIDENCE` RESULT. It is not an independent replication and not a
rescue of MARKET-01.

MARKET-02 is **not** `weak_continuation + OI expansion -> reversal`.

```text
PRIMARY POPULATION = QUALIFYING_IMPULSE AND OI_EXPANSION

within that population:
  candidate = continuation_ratio > 0.25   (PRICE_CONFIRMATION)
  baseline  = continuation_ratio <= 0.25  (WEAK_OR_NONCONFIRMATION)

outcome:
  continuation_return = D * ln(close(T+60m) / close(T))
```

Non-OI-expansion occupying episodes are outside the primary population.
They are not MARKET-02 baselines. Occupancy remains MARKET-01's exact
earliest-first 120m rule on a qualifying impulse, including occupying
episodes that later fail OI/state/outcome inputs.

Frozen geometry: impulse 30m, state 30m, outcome 60m, span 120m.

## Construction

Episode construction uses the proven MARKET-01 fast precompute
primitives (`_close_1m_clock`, legal-OI vector, PRE_VOL energy arrays)
from `scripts/research/market_01_episode_construction_fast.py`. It does
not reintroduce the old O(T×W) path as the contiguous-1m default and
does not delegate MARKET-02 `EpisodeRecord` identity to MARKET-01
`construct_episodes`.

Bound CORE snapshot `717d37a4…` and OI snapshot `5a9d036b…` are refused
because `MARKET_02_ARMED = NO`.

## Bootstrap identity

MD scientific seed is authoritative:

```text
seed_material_sha256 =
19b71ee831e69f273338ef94e65ff4cc339eb6d8054c365fd160c7769955558f

MARKET_02_BOOTSTRAP_SEED = 1852983754304692007
namespace = BOOTSTRAP / PRIMARY_BETA_CONFIRMATION
```

The JSON twin stores `1852983754304692000` from IEEE/JSON number
precision loss. JSON never overrides the MD seed.

## Lifecycle

This is not an implementation freeze and not an ARM. Next authorized
unit, if any: independent implementation-freeze review against the
already frozen prereg. Do not execute until separately armed.
