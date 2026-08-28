# V2 E1 Detector Separation — Pre-registration

Status: **PRE-REGISTERED BEFORE VPS OUTCOME INSPECTION**  
Date: 2026-08-25  
Frozen implementation base: `main@8081eb31657f127141efb3a455f86690258164bc`  
Evidence level: `E1_DETECTOR_SEPARATION` only.

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

## 3. Data audit comes before outcomes

Before opening any detector outcome result, record for the VPS database:

- exact row coverage by source/table/exchange/timeframe;
- exact `calculation_version` and `feature_schema_version` populations;
- Binance reference 1m OHLCV coverage and gap characteristics;
- Stage-2 exchange/consensus/percentile coverage;
- OI source cadence and source labels;
- funding coverage;
- liquidation live-only coverage;
- historical taker-flow availability;
- detector qualification counts by family/direction **without future outcomes**.

Each study row must later receive one evidence tier:

- `LIVE_EQUIVALENT`;
- `PARTIAL_HISTORICAL`;
- `NON_COMPARABLE_FEED_SEMANTICS`;
- `NOT_EVALUABLE`.

Headline results may not silently mix tiers.

## 4. Temporal rules / no-lookahead

For detector qualification at logical decision boundary `T`:

- all Stage-3/4/5 inputs must be selected exactly as production code selects them at `T`;
- no feature, baseline, ablation, or control may read a row whose availability belongs after `T`;
- future path data may be read only by the separate outcome evaluator after the candidate row is frozen;
- raw outcome path uses Binance `klines_1m` only;
- no interpolation of missing sub-minute data;
- historical delay tests below one minute are forbidden unless genuine sub-minute historical data exist.

## 5. Candidate population

The raw E1 population is **every Stage-5 qualification point** produced by the frozen detectors on eligible decision boundaries.

Do not pretend raw qualification points are independent. Report:

- raw qualification count;
- count by family/direction/calendar block;
- overlap among families;
- UTC-day clustered/bootstrap uncertainty;
- concentration of results in the top few UTC days / market blocks.

No Stage-6 episode reconstruction is used to deduplicate E1.

## 6. Reference price and outcomes

Reference price at `T`:

- canonical Binance reference 5m close for the closed bucket ending at `T`, subject to the existing reference usability gate.

Primary forward horizons:

- `+15m`;
- `+30m`;
- `+1h`;
- `+2h`;
- `+4h`.

Directional return convention:

- LONG: `(P_future / P_T) - 1`;
- SHORT: `(P_T - P_future) / P_T`.

For each horizon, compute from future Binance 1m bars:

- terminal directional return;
- MFE;
- MAE;
- time-to-MFE;
- path completeness.

LONG:

- `MFE = max(high / P_T - 1)`;
- `MAE = min(low / P_T - 1)`.

SHORT:

- `MFE = max((P_T - low) / P_T)`;
- `MAE = min((P_T - high) / P_T)`.

A missing required 1m path is reported as incomplete; it is never silently dropped and the denominator tree must show it.

## 7. Reactivity diagnostic

To test the V1 failure mode directly, record directional movement before `T` over:

- `-15m`;
- `-30m`;
- `-1h`.

Compare pre-`T` movement with post-`T` distributions.

Red flag: detector strength/qualification strongly explains movement already completed before `T` while future distributions remain near controls.

## 8. Pre-registered family comparisons

### TREND_PULLBACK

Primary variants:

1. `TP_FULL` — frozen detector;
2. `TP_NO_4H` — research-only 4h conditioning ablation;
3. `TP_NO_1H` — research-only 1h bias ablation;
4. `TP_NO_CONTEXT` — both context layers neutralized while preserving the same price-structure definition;
5. matched random control.

Interpretation: if `TP_FULL` is not materially better than its simpler variants/controls, MTF context has not earned its complexity.

### COMPRESSION_BREAKOUT

Primary variants:

1. `CB_FULL` — frozen detector;
2. `CB_NO_TAKER` — remove taker-flow gate only;
3. `CB_SIMPLE_COMPRESSION_BREAKOUT` — price compression + breakout only;
4. `CB_ORDINARY_RANGE_BREAKOUT` — no compression requirement;
5. matched random control.

### CONFIRMED_BREAKOUT

Primary variants:

1. `FB_FULL` — frozen detector;
2. `FB_DUMB_48H_LEVEL_BREAKOUT` — simple 48h high/low breakout;
3. `FB_NO_CONTEXT` — same breakout without 4h/1h compatibility gate;
4. matched random control.

`CONFIRMED_BREAKOUT` is treated as a baseline-like family until it demonstrates incremental separation.

## 9. Negative controls

Pre-registered controls:

- direction inversion (`LONG <-> SHORT`);
- deterministic time-matched random control with fixed seed `20260825`;
- time-shift control within the same UTC day/eligible decision grid;
- feature-family permutation only where semantics and no-lookahead can be preserved.

A negative control performing similarly to the real detector is evidence against incremental information.

## 10. Historical delay stress

Allowed from current historical resolution:

- `0s` contract-point result;
- `+60s`;
- `+120s`.

Do not fabricate `+15s`/`+30s` historical prices from 1m bars.

## 11. Development / holdout discipline

The first VPS pass may inspect **coverage and detector counts only**, not future outcomes.

Only after coverage/counts are known will a chronological development/holdout boundary be recorded. The final chronological holdout must remain unopened during development analysis.

If any detector/rule is changed after viewing an outcome window, that window is consumed and the modified candidate becomes a new research version.

### 11.1 Initial split amendment — historical record, later superseded before outcomes

Recorded on `2026-08-25` after the candidate-only inventory completed and while `outcomes_included=false`.

Candidate inventory window:

- `[2026-08-02T00:00:00Z, 2026-08-25T17:20:00Z)`;
- `6,832` legal 5m decision boundaries;
- `290` raw Stage-5 qualifications;
- `TREND_PULLBACK=198`;
- `COMPRESSION_BREAKOUT=47`;
- `CONFIRMED_BREAKOUT=45`.

Initial chronological split:

- development: `[2026-08-02T00:00:00Z, 2026-08-21T00:00:00Z)`;
- holdout: `[2026-08-21T00:00:00Z, 2026-08-25T17:20:00Z)`.

The boundary was selected from calendar position + qualification counts only. It contained `202/290` development qualifications and `88/290` holdout qualifications. No future return, MFE, MAE, hit-rate, baseline outcome, or control outcome had been inspected.

Candidate-only family-balance audit then showed the initial holdout contained `COMPRESSION_BREAKOUT=0/47` and only `CONFIRMED_BREAKOUT=6/45`. Because this made family-level OOS evaluation impossible/weak, the initial split was superseded **before any outcome inspection** by the mechanical rule in §11.2. The initial split is retained here as research history and is no longer operative.

### 11.2 Final split freeze — family-balanced count-only rule, before outcomes

Before scanning candidate split counts, the following rule was frozen:

> Among UTC-midnight boundaries in the audited range, choose the **latest** boundary whose holdout contains at least `25%` of all raw qualifications and at least `20%` of each Stage-5 family. Use candidate metadata/counts only; do not read future prices or outcomes.

The count-only audit selected:

- **final development candidate window:** `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)`;
- **final untouched holdout candidate window:** `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`.

Counts at the frozen boundary:

- development: `149/290` raw qualifications;
  - `TREND_PULLBACK=93`;
  - `COMPRESSION_BREAKOUT=30`;
  - `CONFIRMED_BREAKOUT=26`;
- holdout: `141/290` raw qualifications (`48.6%` of all qualifications);
  - `TREND_PULLBACK=105` (`53.0%` of TP);
  - `COMPRESSION_BREAKOUT=17` (`36.2%` of CB);
  - `CONFIRMED_BREAKOUT=19` (`42.2%` of FB).

At final split freeze:

- source candidate artifact still had `outcomes_included=false`;
- the split-balance audit was `COUNT_ONLY_SPLIT_BALANCE_AUDIT_NO_OUTCOMES`;
- no future return/MFE/MAE, baseline outcome, control outcome, or holdout outcome had been viewed.

The `2026-08-16T00:00:00Z` holdout is now **SEALED** and this split supersedes §11.1.

### 11.3 Development outcome purge / embargo

The maximum primary forward horizon is `+4h`. To prevent a development candidate's future path from reading any raw market bar inside the sealed holdout, the development outcome evaluator must enforce:

- outcome-eligible development candidates: `T <= 2026-08-15T20:00:00Z`;
- purge/embargo candidate region: `(2026-08-15T20:00:00Z, 2026-08-16T00:00:00Z)`;
- all future-path SQL for development must have an exclusive end `<= 2026-08-16T00:00:00Z`.

Purged candidates remain part of the frozen candidate population/count audit but are not used for development outcome metrics requiring the full `+4h` path. The denominator tree must report them explicitly. Holdout candidates `T >= 2026-08-16T00:00:00Z` must not receive outcome reads until the holdout gate is intentionally opened later.

## 12. Primary decision rule

E1 is not judged by one accuracy number.

A family `SURVIVES` only if its post-`T` return/MFE/MAE distribution shows meaningful, reasonably stable separation from the relevant simple and matched controls, with uncertainty/concentration reported and without depending on one narrow block.

Possible family verdicts:

- `SURVIVES`;
- `SIMPLIFY`;
- `DEMOTE_TO_BASELINE`;
- `KILL`;
- `INCONCLUSIVE_SAMPLE`.

Global V2 Level-0 fail condition:

> If all three frozen Stage-5 families fail to separate from simple/matched controls and the full variants do not beat simpler price-only/ablated versions, stop downstream V2 lifecycle/product expansion and conduct a hypothesis review rather than adding features or tuning thresholds.

## 13. Output artifacts

The E1 harness must write immutable run artifacts containing at least:

- git SHA;
- rules/calculation/feature-schema identities;
- CLI arguments and UTC run timestamp;
- data coverage/equivalence summary;
- raw candidate rows;
- control/ablation rows;
- outcome rows;
- denominator tree;
- family summary tables;
- concentration/cluster diagnostics;
- machine-readable JSON/CSV plus a human-readable report.

Research code must fail closed if it accidentally imports or invokes Stage-6 episode/lifecycle modules for primary E1 candidate generation.