# V2 E1 Detector Separation — Pre-registration

Status: **PRE-REGISTERED BEFORE VPS OUTCOME INSPECTION; DEVELOPMENT NOW CONSUMED, HOLDOUT STILL SEALED**  
Date: 2026-08-25  
Frozen implementation base: `main@8081eb31657f127141efb3a455f86690258164bc`  
Evidence level: `E1_DETECTOR_SEPARATION` only.

The original preregistration remains authoritative. Development evidence has now been consumed without opening the chronological holdout. The prospective final holdout/reporting/delay/friction amendment is frozen in:

- `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`

Development ablation evidence is recorded in:

- `docs/e1/E1_RUN_001_DEVELOPMENT_ABLATIONS.md`

No detector threshold, family definition, direction, horizon, baseline, delay grid, cost grid, or holdout decision rule may now be changed inside E1-RUN-001.

## 1. Question

Does frozen Stage-5 V2 setup qualification separate future BTCUSDT perp market behavior from simple/matched controls **before** Stage-6 lifecycle machinery is allowed to influence the result?

This study is a falsification gate. It is not a full V2 backtest and cannot promote V2 by itself.

## 2. Scope freeze

Included production logic:

- Stage 3 aligned inputs;
- Stage 4 `4h` regime and `1h` bias;
- frozen Stage-5 detectors:
  - `TREND_PULLBACK`;
  - `COMPRESSION_BREAKOUT`;
  - `CONFIRMED_BREAKOUT`.

Explicitly excluded:

- `V2EpisodeHistory`;
- Stage-6 Unit 2/3 routing/lifecycle state;
- `evaluate_early_signal_transition()`;
- `build_episode_transition_event()`;
- `CONFIRMED`, `EXPIRED`, `INVALIDATED`, `WEAKENING`, `COMPLETED` semantics;
- Telegram/runtime delivery logic;
- any parameter tuning after seeing outcomes.

PR #67 is intentionally not a dependency of this E1 study.

## 3. Temporal/no-lookahead contract

- Candidate qualification at T may use only information selected by frozen production Stage-3/4/5 semantics at T.
- Future outcome paths are read only after candidate artifacts are frozen.
- Binance raw 1m bars are the outcome source.
- Historical sub-minute delay results are forbidden.
- Missing required paths are incomplete, never interpolated or silently dropped.

## 4. Candidate population / dependence

The raw E1 population is every frozen Stage-5 qualification point. Raw qualifications are not independent episodes.

Required dependence reporting:

- raw N;
- family/direction/day counts;
- family overlap;
- time-gap clustering;
- UTC-day concentration/block uncertainty.

No Stage-6 episode reconstruction is used for E1 deduplication.

## 5. Reference price / outcomes

Reference price at T is the canonical usable Binance reference 5m close for the closed bucket ending at T.

Frozen horizons:

- +15m
- +30m
- +1h
- +2h
- +4h

Directional return:

- LONG: `(P_future / P_T) - 1`
- SHORT: `(P_T - P_future) / P_T`

Report terminal directional return, MFE, MAE, time-to-MFE and path completeness. Pre-T reactivity is measured at -15m/-30m/-1h.

## 6. Frozen variants

TREND_PULLBACK:

- `TP_FULL`
- `TP_NO_4H`
- `TP_NO_1H`
- `TP_NO_CONTEXT`
- matched random

COMPRESSION_BREAKOUT:

- `CB_FULL`
- `CB_NO_TAKER`
- `CB_SIMPLE_COMPRESSION_BREAKOUT`
- `CB_ORDINARY_RANGE_BREAKOUT`
- matched random

CONFIRMED_BREAKOUT:

- `FB_FULL`
- `FB_NO_CONTEXT`
- `FB_DUMB_48H_LEVEL_BREAKOUT`
- matched random

`FB_NO_CONTEXT` and `FB_DUMB_48H_LEVEL_BREAKOUT` are structurally the same Stage-5 population and are not double-counted as independent evidence.

Negative controls include direction inversion, deterministic matched random (`seed=20260825`), same-day time shift, and only semantics-safe permutations if used.

## 7. Historical delay stress

Allowed historical delays:

- 0s
- +60s
- +120s

No +15s/+30s synthetic history.

Final exact delay semantics and generic friction stress are frozen prospectively in `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`.

## 8. Final chronological split

Candidate inventory window:

- `[2026-08-02T00:00:00Z, 2026-08-25T17:20:00Z)`
- `6,832` legal 5m decision boundaries
- `290` raw FULL qualifications
- TP=198, CB=47, FB=45

The first 21-Aug split was superseded before outcomes because it contained no CB holdout candidates.

The final split was selected before outcomes by the frozen family-balance rule: choose the latest UTC-midnight boundary whose holdout contains >=25% of all qualifications and >=20% of each family.

Final split:

- development `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)` — `149` FULL candidates (`TP=93`, `CB=30`, `FB=26`)
- holdout `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` — `141` FULL candidates (`TP=105`, `CB=17`, `FB=19`)

The +4h development purge requires outcome-eligible T <= `2026-08-15T20:00:00Z`, so development SQL never reads a bar in the sealed holdout.

## 9. Development evidence state

Development outcomes, direction inversion, matched-random controls, and preregistered ablation/simple-baseline outcomes have now been consumed. Holdout outcomes and holdout market rows remain unopened.

The consumed evidence window may not be reused to justify detector changes within E1-RUN-001. Any behavior-affecting modification creates a new research version.

## 10. Decision rule

Allowed family verdicts:

- `SURVIVES`
- `SIMPLIFY`
- `DEMOTE_TO_BASELINE`
- `KILL`
- `INCONCLUSIVE_SAMPLE`

Global Level-0 fail condition remains:

> If all three frozen Stage-5 families fail to separate from simple/matched controls and the full variants do not beat simpler price-only/ablated versions, stop downstream V2 lifecycle/product expansion and conduct a hypothesis review rather than adding features or tuning thresholds.

The detailed prospective holdout application of these verdicts is frozen in `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`.

## 11. Output provenance

Research artifacts must preserve git/rules/calculation/feature-schema identities, candidate/control/ablation rows, outcome rows, denominator trees, concentration/cluster diagnostics and machine-readable outputs. Primary E1 candidate generation must fail closed if Stage-6 episode/lifecycle machinery is imported or invoked.
