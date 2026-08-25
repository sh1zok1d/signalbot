# E1-RUN-001 — Development outcome observation

Recorded: 2026-08-25

This file records the first future-price inspection for `E1-RUN-001`.
It is descriptive evidence only; no family verdict is authorized until the pre-registered controls/ablations are run.

## Evidence boundary

- Frozen production detector base: `main@8081eb31657f127141efb3a455f86690258164bc`
- Research calculation namespace: `9bed1b4cf99f1644`
- Final candidate split: `2026-08-16T00:00:00Z`
- Development candidate window: `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)`
- Full-horizon purge: only `T <= 2026-08-15T20:00:00Z`
- Development candidates: `149`
- Full-horizon eligible/reference-usable: `147`
- Purged: `2` (`COMPRESSION_BREAKOUT`)
- Sealed holdout candidates: `141`
- Holdout market rows read: **NO**
- Holdout outcomes opened: **NO**

The development window is now **CONSUMED EVIDENCE**. Any detector/rule change motivated by these results requires a new research version and may not reuse this development window as fresh confirmatory evidence.

## Descriptive family results

All returns below are directional returns under the frozen candidate direction. Percentages are approximate renderings of the machine-readable decimal outputs.

### COMPRESSION_BREAKOUT (`n=28`)

Pre-T mean directional movement:

- `-15m`: `+0.073%`
- `-30m`: `+0.087%`
- `-60m`: `+0.095%`

Post-T mean / median directional return:

- `+15m`: `+0.023% / +0.017%`, positive share `57.1%`
- `+30m`: `+0.006% / -0.010%`, positive share `39.3%`
- `+1h`: `-0.018% / -0.034%`, positive share `32.1%`
- `+2h`: `-0.018% / -0.029%`, positive share `39.3%`
- `+4h`: `+0.031% / +0.011%`, positive share `57.1%`

Interpretation before controls: weak/unstable continuation; much of the directional move is already visible before T. No edge claim.

### CONFIRMED_BREAKOUT (`n=26`)

Pre-T mean directional movement:

- `-15m`: `+0.290%`
- `-30m`: `+0.322%`
- `-60m`: `+0.487%`

Post-T mean / median directional return:

- `+15m`: `-0.093% / -0.076%`, positive share `34.6%`
- `+30m`: `-0.096% / -0.057%`, positive share `30.8%`
- `+1h`: `-0.124% / -0.099%`, positive share `26.9%`
- `+2h`: `-0.161% / -0.146%`, positive share `26.9%`
- `+4h`: `-0.214% / -0.220%`, positive share `26.9%`

Interpretation before controls: strong reactivity signature — large move completed before T followed by adverse post-T direction across every registered horizon. This is adverse evidence for the frozen continuation direction, but not yet a final family verdict.

### TREND_PULLBACK (`n=93`)

Pre-T mean directional movement:

- `-15m`: `-0.046%`
- `-30m`: `-0.051%`
- `-60m`: `+0.041%`

Post-T mean / median directional return:

- `+15m`: `+0.013% / ~0.000%`, positive share `49.5%`
- `+30m`: `-0.001% / -0.011%`, positive share `46.2%`
- `+1h`: `-0.022% / -0.005%`, positive share `48.4%`
- `+2h`: `-0.064% / -0.042%`, positive share `36.6%`
- `+4h`: `-0.205% / -0.252%`, positive share `23.7%`

Interpretation before controls: near-zero short-horizon separation and increasingly adverse longer-horizon direction. No edge claim.

## Current research status

Development candidate outcomes alone do **not** support a positive directional-edge claim for any family. `CONFIRMED_BREAKOUT` is the clearest reactivity concern. However, E1's pre-registered decision rule requires comparison against simple/matched controls and family ablations before `SURVIVES` / `SIMPLIFY` / `DEMOTE_TO_BASELINE` / `KILL` / `INCONCLUSIVE_SAMPLE` may be assigned.

Next required step: development-only matched random + direction-inversion controls, followed by mechanically defined pre-registered family ablations/simple baselines. The holdout remains sealed.