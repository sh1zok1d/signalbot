# E1-RUN-001 — Control protocol freeze

Recorded: 2026-08-25

Timing/provenance:

- candidate development outcomes had already been viewed;
- **no control outcome had been viewed** when this exact protocol was frozen;
- sealed holdout remained unopened and no holdout market row had been read.

The high-level negative controls and seed were already pre-registered in `docs/E1_DETECTOR_SEPARATION_PREREG.md`. This note closes an implementation-level ambiguity in the phrase `time-matched random control` before control results are inspected.

## Direction inversion

For every full-horizon development candidate, evaluate the same exact `T` with `LONG <-> SHORT` and the same reference price/path. No candidate selection changes.

## Deterministic matched-random control

Seed: `20260825`.

For each full-horizon development candidate:

1. preserve its family;
2. preserve its original LONG/SHORT direction;
3. select a control `T` from the same UTC calendar day;
4. preserve the family decision clock:
   - `TREND_PULLBACK`: 15m formation boundaries only;
   - `COMPRESSION_BREAKOUT`: every legal 5m boundary;
   - `CONFIRMED_BREAKOUT`: every legal 5m boundary;
5. exclude every actual V2 candidate time from any family in the development window;
6. require a usable canonical Binance 5m reference vector and complete raw pre-60m/post-240m path;
7. sample without replacement within each `(family, UTC day)` group;
8. use a deterministic group PRNG seed derived from `(20260825, family, UTC day)`.

Candidate direction is attached to the random time; future price values are never used to choose the random time.

## Interpretation

Because the exact matching details were frozen after candidate development outcomes were seen, the development matched-random comparison is a **diagnostic development comparison**, not fresh confirmatory evidence. The exact same construction is prospectively frozen for any later intentional holdout comparison.

No detector threshold/rule change is authorized by this note.