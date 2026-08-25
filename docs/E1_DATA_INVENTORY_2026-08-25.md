# E1 Data Inventory — 2026-08-25

Source: read-only VPS inventory executed against production TimescaleDB on 2026-08-25 before any E1 outcome inspection.

## Key findings

1. Raw 1m OHLCV is available for Binance/Bybit/OKX from 2026-06-17 through 2026-08-25 with only a handful of isolated 120s gaps in the live segment.
2. Live taker-flow is present on all three venues from 2026-07-17 19:27 UTC onward. Historical backfill taker-flow exists only on Binance before that boundary.
3. OI:
   - Binance historical + live;
   - Bybit historical + live;
   - OKX live only from 2026-07-17 19:27 UTC.
   Historical provider cadence is 5m; live polling cadence is ~15s. Research must not infer sub-provider cadence from forward-filled historical values.
4. Funding exists historically/live on all three venues.
5. Liquidations are live-only. Binance is snapshot/undercount semantics, Bybit full realtime; no OKX liquidation rows were present in the inspected table.
6. Stage-2 derived history is materially incomplete for V2 E1:
   - `exchange_feature_vectors`: only `5m` rows are materialized;
   - `consensus_feature_vectors`: only `5m` rows are materialized;
   - `percentile_snapshots`: zero rows;
   - `stage2_watermarks`: zero rows.
   Therefore current production DB cannot yet replay Stage 3->4->5 for V2 honestly, because 15m/1h/4h context/setup inputs and required percentile rows are absent.
7. Dominant existing Stage-2 calculation namespace is `3b1135aa6cfc4811`, with 5m coverage from 2026-07-25 07:15 UTC through 2026-08-25 17:10 UTC.
8. Raw data, not derived data, is the limiting distinction: there is enough underlying raw history to materialize the missing V2 research inputs without touching outcomes.

## Current E1 evidence policy

- Do NOT run future-return/MFE/MAE evaluation yet.
- Do NOT use Unit-3 lifecycle code.
- Do NOT infer that zero Stage-5 candidates from the current DB means detector failure; current derived inputs are incomplete.
- Materialize missing Stage-2 15m/1h/4h features and required percentiles with the same frozen production computation code before candidate-count replay.
- Keep the full post-2026-07-17 live-equivalent period quarantined from outcome inspection until candidate counts and the chronological split are frozen.

## Provisional evaluation eligibility window

Coverage-only lower bound for full three-venue live-equivalent flow/OI evidence:

`2026-07-17 19:30 UTC`

Use `2026-07-18 00:00 UTC` as the provisional first candidate boundary to avoid partial-start edge effects. This is not yet the final development/holdout split; that split remains frozen only after candidate counts are known and before outcomes are opened.

## Required preflight before materialization

Before writing derived research rows, verify:

- exact `config_hash`, `config_version`, `code_version` for the dominant Stage-2 namespace;
- historical instrument metadata (`exchange_instrument_history`) coverage as-of the provisional E1 window;
- publication/coherence state needed by replay readers;
- whether the research materialization should extend an existing semantic calculation namespace or use an isolated research namespace while preserving the frozen formula/version identity.

No outcome evidence has been inspected at this stage.
