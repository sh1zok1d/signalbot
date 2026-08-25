# E1-RUN-001 — Holdout Coverage Readiness Clarification

Status: **RECORDED BEFORE ANY HOLDOUT PRICE/OUTCOME READ**  
Date: 2026-08-25

The first timestamp-only holdout coverage preflight returned `85` missing 1m timestamps while `prices_read=false` and `outcomes_opened=false`.

Observed structure:

- one already-historical Binance 1m gap at `2026-08-24T12:29:00Z`;
- the remaining missing timestamps were an unobserved/future tail because the frozen holdout's latest candidate at `2026-08-25T17:15:00Z` requires a full `+4h` path through the 1m bar starting `2026-08-25T21:14:00Z`.

The original preregistration already specifies that a missing required 1m path is reported as incomplete and remains visible in the denominator; it is never silently dropped. Therefore requiring *zero* missing timestamps globally would be stricter than the preregistration and would permanently block E1 because of one honest historical gap.

Prospective operational clarification before any holdout outcome read:

- timestamp-only readiness is `READY` only when the final required 1m bar timestamp (`2026-08-25T21:14:00Z`) has been observed;
- missing timestamps at or before the latest observed 1m bar are classified as historical gaps and do **not** block opening the holdout;
- historical gaps are not repaired/interpolated for E1-RUN-001; the frozen evaluator must mark affected paths incomplete and expose them in the denominator;
- missing timestamps after the latest observed bar are classified as an unobserved tail and keep the holdout blocked;
- no OHLC values, returns, MFE/MAE, controls or holdout outcomes were inspected to make this clarification.

This changes only the preflight's operational readiness test. It does not change detector definitions, candidate populations, horizons, path-completeness rules, verdict criteria, controls, delay stress, cost stress, or any frozen outcome statistic.
