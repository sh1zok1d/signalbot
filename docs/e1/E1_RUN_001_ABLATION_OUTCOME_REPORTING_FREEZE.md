# E1-RUN-001 — Ablation outcome reporting freeze

Status: **FROZEN BEFORE ANY ABLATION/SIMPLE-BASELINE OUTCOME INSPECTION**.

The outcome-free development ablation census has been inspected. No post-T outcome for any ablation/simple-baseline variant has been inspected yet.

## Fixed window / seal

- Development candidate window: `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)`.
- Full `+4h` outcome eligibility requires `T <= 2026-08-15T20:00:00Z`.
- Sealed holdout starts `2026-08-16T00:00:00Z`.
- DB market reads for this analysis are hard-capped strictly before holdout.

## Fixed outcome metrics

Exactly the same definitions as the already-consumed candidate development outcome evaluator:

- pre-T directional returns: 15m / 30m / 60m;
- post-T terminal directional returns: 15m / 30m / 60m / 120m / 240m;
- positive directional-return share;
- median and mean directional return;
- median MFE / MAE;
- 1m historical bar-start resolution for time-to-extreme where retained in row-level output.

No threshold tuning, family-specific horizon selection, or cost/delay adjustment is introduced here.

## Load-bearing comparison rule for nested ablations

A FULL population is mechanically contained in its gate-removal ablation whenever the ablation only removes a gate. Therefore the common FULL rows and ablation rows have the same `(T,direction)` and necessarily the same market outcome. They are **not independent evidence**.

For every nested ablation report three populations:

1. `FULL` — frozen production family population.
2. `ABLATION_ALL` — all rows admitted after removing the frozen gate(s).
3. `ADDED_ONLY` — `ABLATION_ALL - FULL` by exact `(T,direction)` key.

`ADDED_ONLY` is the primary diagnostic of whether the removed gate filtered useful vs harmful/noisy opportunities. Do not run a fake paired-return test on common rows whose outcomes are deterministically identical.

Expected nested relationships, asserted before market outcomes are summarized:

- `TP_FULL ⊆ TP_NO_4H`
- `TP_FULL ⊆ TP_NO_1H`
- `TP_FULL ⊆ TP_NO_CONTEXT`
- `CB_FULL ⊆ CB_NO_TAKER`
- `CB_FULL ⊆ CB_SIMPLE_COMPRESSION_BREAKOUT`
- `FB_FULL ⊆ FB_NO_CONTEXT`
- `FB_NO_CONTEXT == FB_DUMB_48H_LEVEL_BREAKOUT` exactly; the alias is reported once and never counted as independent evidence.

`CB_ORDINARY_RANGE_BREAKOUT` is a distinct price-only baseline, not assumed nested with CB_FULL.

## Interpretation frozen before outcomes

For a removed gate to show useful incremental filtering on development, the evidence should not merely show a smaller FULL population. The rows excluded by the gate (`ADDED_ONLY`) should be materially worse than the retained FULL population in the intended direction across the registered horizon set. A single favorable horizon is descriptive only.

If FULL is no better than the simpler ALL population and the ADDED_ONLY rows are not materially worse, the removed complexity has not demonstrated incremental value on development.

If the simpler baseline materially outperforms FULL, prefer `SIMPLIFY`/`DEMOTE_TO_BASELINE` over adding features or retuning thresholds.

No final family or global E1 verdict is authorized from development alone; sealed holdout remains the final frozen comparison after reporting/delay rules are complete.
