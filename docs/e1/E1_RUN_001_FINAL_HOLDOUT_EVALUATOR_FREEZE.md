# E1-RUN-001 — Final Holdout Evaluator Freeze

Status: **FROZEN BEFORE ANY HOLDOUT OHLC / OUTCOME READ**  
Date: 2026-08-26  
Evaluator introduced at commit: `f093fc35c5095110fddb2e76f287aa045fd06e7f`  
Evaluator: `scripts/research/v2_e1_final_holdout_evaluator.py`

This document records the concrete single-open implementation of the already-frozen rules in `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`. It is recorded while the holdout still has `prices_read=false`, `outcomes_opened=false`, and `holdout_market_price_rows_read=false`.

## Preconditions

The evaluator fails closed unless:

- source artifact is `HOLDOUT_ABLATION_INVENTORY_NO_OUTCOMES`;
- FULL populations reproduce exactly `TP=105`, `CB=17`, `FB=19`;
- FB no-context / dumb-48h alias identity is exact;
- all frozen nested FULL-subset invariants hold;
- the strengthened timestamp-only preflight is `READY`;
- primary +4h coverage is complete through its required final timestamp;
- frozen FULL-family fixed `+6h` same-day circular time-shift +4h coverage is also complete through its required final timestamp;
- neither the final output artifact nor the local one-shot `.OPENED` marker already exists.

The evaluator connects to PostgreSQL first, then atomically reserves the local `.OPENED` marker immediately before the first holdout OHLC query. A failed authentication attempt therefore does not consume the one-shot marker. Any later failure is treated as a holdout-open incident requiring explicit correctness review rather than silent rerun.

## Frozen computation in the single process

Before printing any outcome-derived metric, the evaluator computes and writes one artifact containing:

1. every preregistered FULL / ablation / simple-baseline holdout population at 15m/30m/60m/120m/240m;
2. raw N, LONG/SHORT N, reference/path completeness, mean/median terminal directional return, positive share, median MFE/MAE;
3. 30m and 60m time-gap cluster counts;
4. per-UTC-day concentration/result tables;
5. UTC-day block bootstrap of mean directional return, fixed seed `20260825`, `10,000` resamples, 95% percentile interval;
6. fixed total round-trip friction stresses `0/5/10/20 bps`;
7. nested `FULL / ABLATION_ALL / ADDED_ONLY` on exact `(T,direction)` identity;
8. same-T direction inversion for each FULL family;
9. fixed `+6h` (`72 x 5m`) circular same-UTC-day time shift for each FULL family, with collision share;
10. deterministic matched-random controls for every independent evaluated variant/evidence population, fixed seed `20260825`, matched within variant/family + UTC day, preserving direction, excluding own candidate times and sampling without replacement where feasible; unmatched rows remain explicit;
11. delay stresses `0/+60/+120 seconds`.

To avoid an outcome-driven second read, delay diagnostics are computed prospectively for **all** preregistered variants in the same final run. This is stricter/non-selective relative to the freeze requirement (which requires FULL plus any simplified variant that could earn `SIMPLIFY`) and does not alter any delay value or candidate definition.

`FB_DUMB_48H_LEVEL_BREAKOUT` remains an exact alias of `FB_NO_CONTEXT` and is not counted as independent evidence.

## Random-control legal boundary definition

A matched-random decision boundary is legal only when it:

- lies on the frozen 5m holdout decision grid `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`;
- has the frozen reference 5m vector usable under the same identity/gap/completeness checks used for candidates;
- has a complete raw Binance 1m path through the longest registered `+240m` horizon;
- is not one of that population's own candidate times.

No fallback matching rule is used when a stratum lacks enough unused legal boundaries; those candidate rows are reported unmatched.

## Delay semantics

- `0s`: frozen contract point `P_T`;
- `+60s`: entry is the close of the Binance 1m bar starting at `T`, i.e. the bar ending at `T+60s`;
- `+120s`: entry is the close of the 1m bar starting at `T+60s`, i.e. ending at `T+120s`;
- terminal endpoint remains the original frozen `T+h`;
- delayed MFE/MAE begin after the delayed entry and end at the original `T+h` endpoint;
- missing entry/path data remain incomplete, never interpolated.

## Output / interpretation seal

The evaluator does **not** automatically assign `SURVIVES`, `SIMPLIFY`, `DEMOTE_TO_BASELINE`, `KILL`, or `INCONCLUSIVE_SAMPLE`. Those qualitative verdicts are applied only after the complete final artifact exists, using the already-frozen prospective logic.

The script prints only a completion/seal summary after the artifact is atomically written. No partial holdout metric is intentionally emitted to stdout during computation.
