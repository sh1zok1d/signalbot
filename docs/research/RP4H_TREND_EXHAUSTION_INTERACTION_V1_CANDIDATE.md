# RP4H_TREND_EXHAUSTION_INTERACTION_V1 — future candidate (recorded only; not designed, not run)

**Date:** 2026-10-10. **Recorded by:** chief architect, on the owner's decision (Track B, 2026-10-10).
**Status:** `DISCOVERY_CANDIDATE_FROM_SIGN_REVERSED_PRIMARY_HYPOTHESIS`.

**This record does not:**
- confirm anything;
- rewrite `RP4H_TREND_REGIME_MODULATION_V1`;
- authorize a design or a run.

## Origin

`RP4H_TREND_REGIME_MODULATION_V1` (design `175c95e2`, SHA `c1343df4…`) closed with **`TREND_REGIME_MODULATION_NOT_DETECTED`**. That is the final result of its hypothesis: a strong trend weakens the RP4H mean reversion. The hypothesis was not supported.

After that outcome a new, opposite hypothesis was formed:

> After a strong preceding directional move, the edge of the short range may give a *stronger* subsequent mean reversion / exhaustion, not continuation.

## Discovery evidence it rests on (CORE 2020–24, one read; DISCOVERY_ONLY)

| quantity | value |
|---|---|
| RP4H partial, weak-trend tercile (T1) | −0.029 [−0.040, −0.016] |
| RP4H partial, strong-trend tercile (T3) | −0.042 [−0.054, −0.030] |
| primary T3 − T1 (the original route) | −0.013 [−0.032, +0.005], interval includes 0 |
| continuous rank interaction RP4H × TS_24H (secondary) | −0.012 [−0.020, −0.004], interval below 0 |
| beyond the local path: T1 / T3 | −0.007 / −0.020 |

## Status rules

- **This is a post-outcome hypothesis.** It came from reading the sign of a failed primary and a secondary. It is not a confirmation of anything.
- **CORE 2020–24 is now exposed for it.** No further CORE read can test it.
- **A test needs a fresh surface for the contrast** and its own design note before any outcome.
  - Candidates: BitMEX 2016–19 or Binance spot 2017–19 (not both); Binance 2025–26 on the Unit B surface; prospective live data.
  - The RP4H level is read on all of them, so none is pristine.
- **Nothing is fixed now:** no trend threshold, tercile cut, lookback, signed form or horizon. The regime variable TS_24H and its CORE terciles are recorded facts of the closed unit, not frozen choices for this candidate.
- **Execution needs a separate owner decision.**

## Adequacy gate (2026-10-11, owner decision; no market interaction outcome read)

- **Protocol:** `RP4H_TREND_EXHAUSTION_INTERACTION_V1_ADEQUACY_PROTOCOL.md` (commit `cf75f2c7`). Exact Unit-1 parity: primary interaction_b0; TS_24H via `spa_family`.
- **Result:** `RP4H_TREND_EXHAUSTION_INTERACTION_V1_ADEQUACY.md` / `.json` → **`TREND_EXHAUSTION_REPLICATION_INFORMATIONALLY_INSUFFICIENT`**.
- **P(SUPPORTED) at 1× the discovery magnitude:**
  - BitMEX 2016–19: 0.77 (homoskedastic 0.67); MDE80 1.07×;
  - Binance 2025–26: 0.44; MDE80 1.65×.
- **Status unchanged:** `DISCOVERY_CANDIDATE_FROM_SIGN_REVERSED_PRIMARY_HYPOTHESIS`. No replication under the frozen rule.
