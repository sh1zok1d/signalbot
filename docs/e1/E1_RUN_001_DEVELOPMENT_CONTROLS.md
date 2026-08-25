# E1-RUN-001 — Development controls

Status: **DEVELOPMENT EVIDENCE CONSUMED; HOLDOUT STILL SEALED**  
Date: 2026-08-25  
Frozen production basis: `main@8081eb31657f127141efb3a455f86690258164bc`  
Calculation namespace: `9bed1b4cf99f1644`

This note records the first pre-registered development controls after the candidate-only development outcomes were opened. It does not authorize a family verdict yet; family ablations/simple baselines remain required before any OOS decision.

## Seal / denominator

- Holdout boundary: `2026-08-16T00:00:00Z`.
- Holdout outcomes opened: **NO**.
- Holdout market rows read by this control run: **NO**.
- Full-horizon development candidates: TP `93`, CB `28`, FB `26`.
- Matched-random seed: `20260825`.
- Matched-random protocol was frozen before control outcomes were inspected; see `E1_RUN_001_CONTROL_PROTOCOL_FREEZE.md`.

## Direction inversion, same T

The inversion control keeps the exact candidate time and flips only LONG/SHORT.

### COMPRESSION_BREAKOUT

- 15m actual mean `+0.0227%`, inversion `-0.0227%`.
- 30m actual mean `+0.0060%`, inversion `-0.0060%`.
- 60m actual mean `-0.0177%`, inversion `+0.0177%`.
- 120m actual mean `-0.0184%`, inversion `+0.0184%`.
- 240m actual mean `+0.0308%`, inversion `-0.0308%`.

Interpretation: unstable sign across horizons; no coherent directional advantage from the frozen direction.

### CONFIRMED_BREAKOUT

- 15m actual mean `-0.0929%`, inversion `+0.0929%`.
- 30m actual mean `-0.0959%`, inversion `+0.0959%`.
- 60m actual mean `-0.1241%`, inversion `+0.1241%`.
- 120m actual mean `-0.1610%`, inversion `+0.1610%`.
- 240m actual mean `-0.2138%`, inversion `+0.2138%`.
- Inversion positive-share rises to `65.4% / 69.2% / 73.1% / 73.1% / 73.1%` over 15/30/60/120/240m.

Interpretation: strong development evidence that the frozen breakout direction is marking exhaustion/reversal rather than continuation on this window.

### TREND_PULLBACK

- 15m actual mean `+0.0130%`, inversion `-0.0130%`.
- 30m actual mean `-0.0007%`, inversion `+0.0007%`.
- 60m actual mean `-0.0221%`, inversion `+0.0221%`.
- 120m actual mean `-0.0641%`, inversion `+0.0641%`.
- 240m actual mean `-0.2053%`, inversion `+0.2053%`.
- Inversion positive-share reaches `63.4%` at 120m and `76.3%` at 240m.

Interpretation: no stable resumption signal; longer-horizon direction is materially adverse on development.

## Candidate vs deterministic matched random

The paired statistic is candidate directional return minus its matched random directional return.

### COMPRESSION_BREAKOUT

Mean candidate-minus-random:

- 15m `+0.0191%`;
- 30m `-0.0176%`;
- 60m `-0.0407%`;
- 120m `-0.0598%`;
- 240m `-0.0138%`.

Candidate-better share is above 50% only at 15m (`53.6%`).

### CONFIRMED_BREAKOUT

Mean candidate-minus-random:

- 15m `-0.0761%`;
- 30m `-0.0983%`;
- 60m `-0.1274%`;
- 120m `-0.1855%`;
- 240m `-0.3330%`.

Candidate-better share falls from `38.5%` at 15m to `23.1%` at 240m.

### TREND_PULLBACK

Mean candidate-minus-random:

- 15m `+0.0332%`;
- 30m `+0.0156%`;
- 60m `-0.0157%`;
- 120m `-0.0850%`;
- 240m `-0.2658%`.

Candidate-better share is approximately chance at 15m (`50.5%`) and falls to `37.6%` at 240m.

## Current interpretation

Development evidence now puts `H-016` under substantial pressure:

- FB is worse than matched random at every registered horizon and inversion is better at every registered horizon.
- TP has no robust short-horizon separation and becomes materially worse than matched random at 2h/4h.
- CB has only a small 15m advantage; it is not stable across the registered horizon set.

This is **not yet a final family verdict**. The pre-registered family ablations/simple price baselines must still answer whether the full V2 rules add value beyond simpler structure. No parameter/rule change may be motivated by these development results without creating a new research version.
