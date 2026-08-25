# E1-RUN-001 — Development Ablation Evidence

Status: **DEVELOPMENT EVIDENCE CONSUMED / HOLDOUT STILL SEALED**  
Date: 2026-08-25  
Frozen production basis: `main@8081eb31657f127141efb3a455f86690258164bc`

This note records the development-only ablation/simple-baseline results after their candidate populations and reporting semantics were frozen. It does not authorize tuning and it does not contain holdout outcomes.

## Seal / denominator

- source variant rows: `2260`
- full-horizon eligible after the +4h purge: `2232`
- purged near split: `28`
- reference usable: `2232/2232`
- holdout market rows read: `false`
- holdout outcomes opened: `false`

## Candidate-population invariants

The outcome-free census reproduced the frozen FULL populations exactly:

- `TP_FULL=93`
- `CB_FULL=30`
- `FB_FULL=26`

`FB_NO_CONTEXT=29` and `FB_DUMB_48H_LEVEL_BREAKOUT=29`, with identical direction counts (`LONG=17`, `SHORT=12`), confirming the preregistered Stage-5 population equivalence. They are one piece of evidence and must not be double-counted.

## TREND_PULLBACK

Development full-horizon counts after purge:

- `TP_FULL=93`
- `TP_NO_1H=294`
- `TP_NO_4H=443`
- `TP_NO_CONTEXT=1071`

### FULL

Directional return means:

| Horizon | Mean | Median | Positive share |
| --- | ---: | ---: | ---: |
| 15m | +0.0130% | -0.0005% | 49.5% |
| 30m | -0.0007% | -0.0107% | 46.2% |
| 1h | -0.0221% | -0.0052% | 48.4% |
| 2h | -0.0641% | -0.0418% | 36.6% |
| 4h | -0.2053% | -0.2520% | 23.7% |

4h path diagnostics: median `MFE=+0.1739%`, median `MAE=-0.4804%`.

### Removed-gate diagnostics

`TP_NO_1H` adds `201` pre-purge candidates. Its `ADDED_ONLY` rows are materially better than FULL across development, especially at longer horizons:

- 1h mean `+0.0172%` vs FULL `-0.0221%`;
- 2h mean `+0.0137%` vs FULL `-0.0641%`;
- 4h mean `-0.0122%` vs FULL `-0.2053%`;
- 4h positive share `43.8%` vs FULL `23.7%`.

`TP_NO_4H` adds `357` pre-purge candidates (`350` full-horizon rows). Again the removed-gate population is substantially less adverse than FULL:

- 2h mean `-0.0253%` vs FULL `-0.0641%`;
- 4h mean `-0.0345%` vs FULL `-0.2053%`;
- 4h positive share `48.3%` vs FULL `23.7%`.

`TP_NO_CONTEXT` adds `991` pre-purge candidates (`978` full-horizon rows). Even this broad added-only population is less adverse at 4h than FULL (`-0.0575%` vs `-0.2053%`; positive share `44.2%` vs `23.7%`).

The MFE/MAE picture is consistent with the terminal-return result. At 4h:

- FULL: median `MFE=+0.1739%`, `MAE=-0.4804%`;
- NO_1H: `+0.2275% / -0.3314%`;
- NO_4H: `+0.2476% / -0.3184%`;
- NO_CONTEXT: `+0.2223% / -0.3135%`.

**Development interpretation:** the frozen 4h/1h context stack does not earn its complexity as a TP filter on this window. The FULL intersection selected a materially worse longer-horizon subset than the candidates excluded by either context gate. This is evidence against the frozen MTF-conditioning hypothesis, not permission to retune the gates.

## COMPRESSION_BREAKOUT

Full-horizon counts after purge:

- `CB_FULL=28`
- `CB_NO_TAKER=31`
- `CB_SIMPLE_COMPRESSION_BREAKOUT=39`
- `CB_ORDINARY_RANGE_BREAKOUT=149`

### FULL

FULL is weak/unstable: `+0.0227%` mean at 15m, approximately flat/adverse from 30m through 2h, and `+0.0308%` mean at 4h. This was already insufficient to establish stable separation from the matched-random control.

### Taker/context gates

Removing taker adds only `3` rows. The resulting distributions are nearly unchanged; `n=3` added-only is too small to establish an independent benefit of the taker gate.

`CB_SIMPLE_COMPRESSION_BREAKOUT` adds `11` pre-purge rows. The added-only medians are positive at 15m, 30m, 1h, 2h and 4h, while means remain mixed. FULL is not demonstrably superior to this simpler compression+breakout population.

### Compression versus ordinary range breakout

The price-only `CB_ORDINARY_RANGE_BREAKOUT` population is materially broader (`149` full-horizon rows) and adverse at every registered terminal horizon:

- 15m mean `-0.0165%`
- 30m `-0.0218%`
- 1h `-0.0312%`
- 2h `-0.0271%`
- 4h `-0.0469%`

By contrast `CB_SIMPLE_COMPRESSION_BREAKOUT` is positive at 15m (`+0.0159%`) and 4h (`+0.0267%`) and less adverse around 1h/2h. This is development evidence that the compression structure performs useful selection relative to a dumb ordinary-range breakout. It is **not yet evidence of standalone predictive edge versus matched/random controls**.

**Development interpretation:** compression is the only CB component that has earned continued scrutiny. Taker/context have not demonstrated incremental value. Provisional structural direction is `SIMPLIFY`, not `SURVIVES`.

## CONFIRMED_BREAKOUT

Full-horizon counts:

- `FB_FULL=26`
- `FB_NO_CONTEXT=29`
- `FB_DUMB_48H_LEVEL_BREAKOUT=29` (same population as NO_CONTEXT)

FULL is adverse on every registered horizon:

- 15m mean `-0.0929%`
- 30m `-0.0959%`
- 1h `-0.1241%`
- 2h `-0.1610%`
- 4h `-0.2138%`

At 4h median `MFE=+0.2447%` versus median `MAE=-0.5449%`.

Removing context does not rescue the setup. The dumb/no-context variant is also adverse at every horizon, including 4h mean `-0.1928%` and positive share `27.6%`.

Only three rows are added by removing context; they cannot explain the failure. Combined with the already-consumed direction-inversion and matched-random controls, the problem is located in the breakout/fresh-cross hypothesis itself rather than the MTF compatibility gate.

**Development interpretation:** `CONFIRMED_BREAKOUT` is a strong `KILL` candidate under its frozen directional interpretation. Holdout remains necessary as the prospective check before the E1 family verdict is finalized.

## Development-only provisional state

These are not final OOS verdicts:

- `TREND_PULLBACK`: **SIMPLIFY candidate / frozen context stack falsified on development**. No simpler variant has yet earned a positive edge claim.
- `COMPRESSION_BREAKOUT`: **SIMPLIFY candidate**. Compression retains a plausible selection effect; taker/context have not earned complexity.
- `CONFIRMED_BREAKOUT`: **KILL candidate**.

The global Level-0 fail condition is not finalized until the untouched chronological holdout is opened under a frozen reporting/delay protocol.
