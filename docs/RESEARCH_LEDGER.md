# Signalbot Research Ledger

> Provenance for human research decisions. Code/version provenance is not enough: repeated inspection of historical results can itself overfit the project. Every confirmatory hypothesis/change should be recorded here or in a machine-readable successor before evaluation.

## Rules

1. Record the hypothesis **before** opening the designated validation/OOS result whenever the test is intended to be confirmatory.
2. Mark post-hoc ideas explicitly as `EXPLORATORY`.
3. A viewed OOS/holdout window is consumed for any model revision motivated by that view.
4. Any behavior-affecting change follows the normal model/rules versioning contract; this ledger does not replace code/config identity.
5. Rejected hypotheses stay in the ledger. Do not delete failed experiments.
6. Record null results. “No incremental value” is a useful outcome.
7. Subgroup/regime analyses not predeclared are exploratory and cannot become retroactive promotion evidence.

---

## Entry template

```text
Hypothesis ID:
Date:
Status: PRE_REGISTERED | EXPLORATORY | TESTED_KEEP | TESTED_REJECT | INCONCLUSIVE | DEFERRED
Model/rules version:

Hypothesis:
Economic/causal rationale:
Expected direction of effect:

Primary metric:
Secondary metrics:
Baseline/control:
Negative control (if any):
Ablation/comparison:

Development window:
Validation window:
Untouched OOS window:
Has OOS already been viewed? YES/NO
Live-equivalence requirement:

Parameter/config/code change proposed:
Data/source change proposed:

Result summary:
Uncertainty / sample notes:
Decision: KEEP | REJECT | SIMPLIFY | RETEST_NEW_VERSION | DEFER
Consumed evidence windows:
Follow-up:
```

---

## Initial hypothesis inventory

These are **current project hypotheses to test**, not claims already supported by evidence.

### H-001 — V1 weakness is materially caused by lateness

- Status: `PRE_REGISTERED_DIAGNOSTIC`
- Hypothesis: a meaningful part of V1's practical weakness comes from emitting after too much of the move is already consumed, rather than direction being purely uninformative.
- Required test: formal V1 report with post-delay MFE/MAE, directional outcomes, clustering, simple/time-matched controls.
- Falsification signal: direction remains weak and little actionable residual edge exists even when lateness is separated from directional quality.

### H-002 — Multi-timeframe role separation adds quality beyond simpler structure

- Status: `PRE_REGISTERED`
- Hypothesis: 4h regime + 1h bias + 15m setup + 5m trigger improves episode quality beyond simpler lower-TF/price-structure baselines.
- Required test: Stage-5 event study and later full V2 ablation/baseline challenge.
- Falsification signal: no stable OOS improvement vs lower-TF/simple price structure.

### H-003 — 4h regime conditioning adds incremental value

- Status: `PRE_REGISTERED`
- Required test: remove/neutralize 4h conditioning in a research-only ablation without changing unrelated rules.
- Falsification signal: no degradation or improved generalization without 4h conditioning.

### H-004 — 1h directional bias adds incremental value

- Status: `PRE_REGISTERED`
- Required test: 1h-bias ablation.
- Falsification signal: no degradation or improved generalization without 1h bias.

### H-005 — OI contributes incremental predictive information

- Status: `PRE_REGISTERED`
- Rationale: OI may distinguish position buildup/flush from ordinary price movement.
- Required prerequisite: provider-granularity/live-equivalence audit.
- Required test: OI ablation on comparable evidence.
- Falsification signal: no-OI is indistinguishable or better OOS.

### H-006 — Taker flow contributes incremental predictive information

- Status: `PRE_REGISTERED`
- Required prerequisite: historical/live-equivalence tiering.
- Required test: taker-flow ablation.
- Falsification signal: no-flow is indistinguishable or better OOS.

### H-007 — Liquidation context contributes incremental predictive information

- Status: `PRE_REGISTERED`
- Required prerequisite: venue feed-semantics/completeness inventory and live-equivalent evidence.
- Required test: liquidation ablation on semantically comparable evidence.
- Falsification signal: no-liquidations is indistinguishable or better.

### H-008 — Funding contributes useful intraday information

- Status: `PRE_REGISTERED`
- Required test: funding ablation.
- Falsification signal: no incremental OOS value.

### H-009 — Three-venue consensus adds information beyond robust single/median venue baselines

- Status: `PRE_REGISTERED`
- Interpretation rule: agreement is initially a robustness mechanism, not three independent observations.
- Required test: Binance/reference-only, reduced venue set, median/robust aggregation, full consensus.
- Falsification signal: negligible incremental predictive benefit from full consensus.
- If falsified: keep consensus only for data-quality/reliability if useful.

### H-010 — The three V2 setup families are empirically distinct

- Status: `PRE_REGISTERED`
- Required test: event-time overlap, direction overlap, latent-move clustering, outcome correlation.
- Falsification signal: families largely identify the same underlying events with similar outcomes.

### H-011 — Model confidence meaningfully orders episode quality

- Status: `PRE_REGISTERED`
- Important: confidence remains non-probabilistic regardless of result.
- Required test: ordered bins vs feasibility, post-delay MFE, MAE, cost-adjusted utility.
- Falsification signal: no stable monotonic/ordered relationship.

### H-012 — V2 beats frozen V1 on comparable periods/metrics

- Status: `PRE_REGISTERED`
- Required test: same-period comparison with only genuinely comparable metrics.
- Falsification signal: no meaningful improvement.

### H-013 — V2 beats simple deterministic TA/price-structure controls

- Status: `PRE_REGISTERED`
- Required test: pre-registered simple baselines under identical delay/cost/denominator semantics.
- Falsification signal: no meaningful improvement.

### H-014 — Any observed edge survives realistic execution delay and costs

- Status: `PRE_REGISTERED`
- Required test: canonical contract point + research delay curve/cost stress.
- Falsification signal: advantage disappears under realistic 60–120s delay or conservative execution costs.

### H-015 — Any observed edge is not concentrated in one narrow regime/block

- Status: `PRE_REGISTERED`
- Required test: chronological block/regime/concentration analysis.
- Falsification signal: most utility is explained by one/few volatility/news/regime blocks.

### H-016 — Stage-5 detectors separate future outcomes from matched controls before lifecycle machinery

- Status: `PRE_REGISTERED`
- Dependency: H2e coherent replay.
- Required test: detector event study against time-matched/simple/negative controls.
- Falsification signal: candidate distributions are materially indistinguishable from controls.

---

## Concrete pre-registered runs

### E1-RUN-001 — Frozen V2 Stage-5 detector separation

- Date: `2026-08-25`
- Status: `PRE_REGISTERED`
- Hypothesis IDs: `H-002`, `H-003`, `H-004`, `H-006`, `H-010`, `H-013`, `H-014`, `H-015`, `H-016`
- Frozen implementation base: `main@8081eb31657f127141efb3a455f86690258164bc`
- Stage-6 lifecycle dependency: **FORBIDDEN for primary E1 candidate generation**
- Full pre-registration: `docs/E1_DETECTOR_SEPARATION_PREREG.md`

Hypothesis:

> Frozen Stage-5 qualifications should alter the post-`T` directional return/MFE/MAE distribution relative to simple and time-matched controls. If they do not, later lifecycle machinery is not allowed to be treated as a source of predictive information.

Primary evidence:

- post-`T` directional return at `15m/30m/1h/2h/4h`;
- MFE/MAE and time-to-MFE from Binance raw 1m bars;
- family-vs-simple-baseline separation;
- UTC-day clustered/concentration diagnostics.

Controls/ablations are frozen in `docs/E1_DETECTOR_SEPARATION_PREREG.md`; deterministic random seed is `20260825`.

Candidate-only inventory completed before outcome inspection:

- calculation namespace: `9bed1b4cf99f1644`;
- candidate window: `[2026-08-02T00:00:00Z, 2026-08-25T17:20:00Z)`;
- legal 5m boundaries: `6,832`;
- raw qualifications: `290`;
- `TREND_PULLBACK=198` (`LONG=126`, `SHORT=72`);
- `COMPRESSION_BREAKOUT=47` (`LONG=27`, `SHORT=20`);
- `CONFIRMED_BREAKOUT=45` (`LONG=36`, `SHORT=9`);
- candidate artifact reported `outcomes_included=false`;
- replay mode: one `REPEATABLE READ` snapshot via the research-only legacy-VPS adapter.

Initial count-only split (historical, superseded before outcomes):

- development `[2026-08-02T00:00:00Z, 2026-08-21T00:00:00Z)`;
- holdout `[2026-08-21T00:00:00Z, 2026-08-25T17:20:00Z)`;
- `202/290` development vs `88/290` holdout;
- candidate-only population audit showed this holdout had `COMPRESSION_BREAKOUT=0/47` and `CONFIRMED_BREAKOUT=6/45`;
- no outcome had been opened, so the split was superseded rather than accepted as an unusable family-level OOS design.

Final count-only split rule was frozen before scanning candidate split counts:

> choose the latest UTC-midnight boundary whose holdout contains at least `25%` of all qualifications and at least `20%` of each family.

Final frozen split selected mechanically by that rule:

- **Development candidate window:** `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)`;
- **Untouched chronological holdout:** `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`;
- development `149/290`: `TP=93`, `CB=30`, `FB=26`;
- holdout `141/290` (`48.6%`): `TP=105`, `CB=17`, `FB=19`;
- holdout family shares: TP `53.0%`, CB `36.2%`, FB `42.2%`.

Maximum forward horizon is `+4h`, therefore development outcomes use a purged/embargoed edge:

- full-horizon outcome-eligible development candidates require `T <= 2026-08-15T20:00:00Z`;
- candidate boundaries after `20:00` and before the split remain in candidate counts but are excluded from full-horizon development outcome metrics;
- development outcome SQL must never read a market bar at or after `2026-08-16T00:00:00Z`.

Has holdout/OOS outcome already been viewed for this run? **NO**.  
Has any future-return/MFE/MAE outcome been viewed before recording the final split? **NO**.  
Holdout status: **SEALED at `2026-08-16T00:00:00Z`**.

Candidate-only dependence audit before outcomes:

- exact same-`T` multi-family overlap: `0`;
- development raw qualifications under the historical 21-Aug split were `202`, corresponding to `123/109/96` time-gap clusters at `15/30/60m` sensitivity;
- the clustering result is a dependence diagnostic only, not Stage-6 episode reconstruction;
- TP showed the strongest repeat qualification dependence;
- day concentration was moderate rather than dominated by one UTC day.

Parameter/config/code change proposed: none to frozen production detector semantics.  
Data/source change proposed: no production source change; research-only historical Stage-2 materialization was performed in isolated calculation namespace `9bed1b4cf99f1644` from persisted raw data.

Decision rule:

- `SURVIVES`, `SIMPLIFY`, `DEMOTE_TO_BASELINE`, `KILL`, or `INCONCLUSIVE_SAMPLE` per family;
- global Level-0 fail if all three frozen families fail simple/matched controls and full variants do not beat simpler ablations.

Result summary: candidate population and final sealed split established; predictive result still pending.  
Uncertainty / sample notes: `290` are raw qualification points, **not independent episodes**; clustering/concentration must remain visible in outcome interpretation.  
Consumed evidence windows: none yet.  
Next step: development-only outcome analysis with the `+4h` purge enforced. Holdout remains unopened until development outcome, baseline, ablation, negative-control and reporting code are frozen.

---

## Future-hypothesis quarantine

Ideas may be recorded here without entering V2-v0.

Examples currently **not authorized as implementation work** before the empirical GO gate:

- cross-venue lead/lag/divergence alpha;
- order-book features;
- spot/CVD;
- CoinGlass/vendor liquidation maps;
- macro/news features;
- ML/adaptive thresholds;
- new setup families;
- multi-symbol expansion for rescuing weak BTC results.

Recording an idea is not permission to implement it.