# E1-RUN-001 — Coverage Preflight Clarification

Status: **RECORDED BEFORE ANY HOLDOUT OHLC / OUTCOME READ**  
Date: 2026-08-26

This note does not change any detector, family, threshold, horizon, control offset, delay, cost, matching rule, or verdict criterion. It closes a coverage-check omission discovered after the primary holdout +4h timestamp horizon became available but before any holdout OHLC values or outcomes were read.

## Omission

`docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md` prospectively freezes a fixed `+6h` (`72 x 5m`) same-UTC-day circular time-shift diagnostic for every FULL-family holdout candidate, with the shifted row still requiring a complete/reference-usable outcome path.

The first timestamp-only preflight implementation required 1m timestamp coverage only through the maximum original candidate `T + 4h`. That is sufficient for primary holdout candidate outcomes and the frozen delay diagnostics, but it can be insufficient for a late-day fixed `+6h` time-shift row whose own `+4h` path extends beyond the original maximum outcome timestamp.

Opening holdout OHLC under that weaker gate could make time-shift completeness depend on the wall-clock time at which the evaluator happened to be run. That would create avoidable censoring in a preregistered negative control.

## Prospective correction

Before any holdout OHLC/outcome read, the timestamp-only coverage gate is strengthened as follows:

1. derive all FULL-family rows from the already-frozen outcome-free holdout ablation inventory;
2. apply the already-frozen `+6h` same-UTC-day circular shift to each FULL row without reading price values;
3. compute the latest required 1m bar across both:
   - original candidate `T + 4h` paths; and
   - shifted FULL-family `T_shift + 4h` paths;
4. keep the holdout sealed until that final required timestamp has been observed;
5. continue treating earlier genuine historical 1m gaps as explicit incomplete-path evidence rather than silently repairing them or permanently blocking the whole study.

This is a stricter implementation of the already-frozen control, not a new control or a post-outcome rule change.

## Seals at time of clarification

At the time this clarification was made:

- `holdout_ablation_inventory.json` had already reproduced frozen FULL counts `TP=105`, `CB=17`, `FB=19`;
- the earlier timestamp-only preflight had reached `ready_for_single_holdout_outcome_open=true` for the **primary** original-candidate +4h horizon;
- `prices_read=false`;
- `outcomes_opened=false`;
- `holdout_market_price_rows_read=false`;
- no holdout OHLC-derived metric, return, MFE/MAE, control result, delay result, or friction result had been observed.

Therefore this correction is still prospective with respect to all holdout outcome evidence.
