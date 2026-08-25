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

## Initial hypothesis inventory

### H-001 — V1 weakness is materially caused by lateness
- Status: `PRE_REGISTERED_DIAGNOSTIC`

### H-002 — Multi-timeframe role separation adds quality beyond simpler structure
- Status: `PRE_REGISTERED`

### H-003 — 4h regime conditioning adds incremental value
- Status: `PRE_REGISTERED`

### H-004 — 1h directional bias adds incremental value
- Status: `PRE_REGISTERED`

### H-005 — OI contributes incremental predictive information
- Status: `PRE_REGISTERED`

### H-006 — Taker flow contributes incremental predictive information
- Status: `PRE_REGISTERED`

### H-007 — Liquidation context contributes incremental predictive information
- Status: `PRE_REGISTERED`

### H-008 — Funding contributes useful intraday information
- Status: `PRE_REGISTERED`

### H-009 — Three-venue consensus adds information beyond robust single/median venue baselines
- Status: `PRE_REGISTERED`

### H-010 — The three V2 setup families are empirically distinct
- Status: `PRE_REGISTERED`

### H-011 — Model confidence meaningfully orders episode quality
- Status: `PRE_REGISTERED`

### H-012 — V2 beats frozen V1 on comparable periods/metrics
- Status: `PRE_REGISTERED`

### H-013 — V2 beats simple deterministic TA/price-structure controls
- Status: `PRE_REGISTERED`

### H-014 — Any observed edge survives realistic execution delay and costs
- Status: `PRE_REGISTERED`

### H-015 — Any observed edge is not concentrated in one narrow regime/block
- Status: `PRE_REGISTERED`

### H-016 — Stage-5 detectors separate future outcomes from matched controls before lifecycle machinery
- Status: `PRE_REGISTERED`

---

## Concrete pre-registered runs

### E1-RUN-001 — Frozen V2 Stage-5 detector separation

- Date: `2026-08-25`
- Status: `DEVELOPMENT_EVIDENCE_CONSUMED_HOLDOUT_SEALED`
- Hypothesis IDs: `H-002`, `H-003`, `H-004`, `H-006`, `H-010`, `H-013`, `H-014`, `H-015`, `H-016`
- Frozen implementation base: `main@8081eb31657f127141efb3a455f86690258164bc`
- Stage-6 lifecycle dependency: **FORBIDDEN for primary E1 candidate generation**
- Full preregistration: `docs/E1_DETECTOR_SEPARATION_PREREG.md`
- Development outcome note: `docs/e1/E1_RUN_001_DEVELOPMENT_OUTCOMES.md`
- Development control note: `docs/e1/E1_RUN_001_DEVELOPMENT_CONTROLS.md`
- Development ablation note: `docs/e1/E1_RUN_001_DEVELOPMENT_ABLATIONS.md`
- Final prospective holdout/reporting freeze: `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`

Hypothesis:

> Frozen Stage-5 qualifications should alter the post-`T` directional return/MFE/MAE distribution relative to simple and time-matched controls. If they do not, later lifecycle machinery is not allowed to be treated as a source of predictive information.

Candidate census / split provenance:

- calculation namespace: `9bed1b4cf99f1644`;
- full candidate window: `[2026-08-02T00:00:00Z, 2026-08-25T17:20:00Z)`;
- legal 5m boundaries: `6,832`;
- raw FULL qualifications: `290` (`TP=198`, `CB=47`, `FB=45`);
- final family-balanced split was selected from candidate counts only before any outcome inspection;
- development: `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)` — `149` raw FULL candidates (`TP=93`, `CB=30`, `FB=26`);
- holdout: `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` — `141` raw FULL candidates (`TP=105`, `CB=17`, `FB=19`);
- maximum +4h horizon uses a purge so development future-path SQL never reaches the holdout.

Development evidence consumed:

- FULL development outcomes opened for `147` full-horizon eligible/reference-usable candidates;
- direction inversion and deterministic matched-random controls consumed;
- outcome-free ablation/simple-baseline census consumed;
- ablation/simple-baseline development outcomes consumed for `2232` full-horizon eligible rows, with `28` purged at the split edge;
- holdout market rows read: `false`;
- holdout outcomes opened: `false`.

Development-only provisional interpretation:

- `TREND_PULLBACK`: the frozen 4h/1h context stack selected a materially worse longer-horizon subset than the candidates excluded by either gate. `TP_FULL` therefore has not earned MTF complexity; simpler variants still have no positive-edge claim. Prospective state: `SIMPLIFY/KILL`.
- `COMPRESSION_BREAKOUT`: the compression structure performs useful selection versus the dumb ordinary-range breakout, while taker/context have not shown incremental value. Prospective state: `SIMPLIFY/INCONCLUSIVE`.
- `CONFIRMED_BREAKOUT`: adverse in the frozen direction across all development horizons; direction inversion/control evidence is unfavorable; removing context does not rescue the setup. Prospective state: strong `KILL` candidate.

Important consumed-window rule:

Any detector/rule change motivated by these development outcomes creates a new research version. E1-RUN-001 may not tune thresholds, flip directions, add features, or select new variants before its untouched holdout is opened.

Final pre-holdout protocol is now frozen prospectively:

- all registered horizons reported equally;
- nested ablations reported as `FULL`, `ABLATION_ALL`, and `ADDED_ONLY`;
- matched-random controls reused with seed `20260825`, including for simplified variants before they may support `SIMPLIFY`;
- same-T direction inversion retained for FULL families;
- fixed same-day +6h time-shift control;
- delay stress only at `0s/+60s/+120s`;
- generic friction stress at `0/5/10/20` bps total round-trip;
- nominal N plus 30m/60m cluster N, UTC-day concentration, and fixed-seed UTC-day block bootstrap;
- holdout opened once; no post-holdout rule changes inside E1-RUN-001.

Next authorized action:

1. run outcome-free holdout ablation/simple-baseline census;
2. hard-require FULL reproduction `TP=105`, `CB=17`, `FB=19`;
3. inspect counts/overlap only;
4. freeze that artifact;
5. only then implement/run the single holdout outcome evaluation under `docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`.

Global Level-0 fail condition remains the original preregistered rule: if all three frozen Stage-5 families fail simple/matched controls and FULL does not beat simpler ablations, stop downstream V2 lifecycle/product expansion and return to hypothesis review rather than feature/tuning escalation.

---

## Future-hypothesis quarantine

Ideas may be recorded here without entering V2-v0. They are not authorized as implementation work before the empirical GO gate:

- cross-venue lead/lag/divergence alpha;
- order-book features;
- spot/CVD;
- CoinGlass/vendor liquidation maps;
- macro/news features;
- ML/adaptive thresholds;
- new setup families;
- multi-symbol expansion for rescuing weak BTC results.

Recording an idea is not permission to implement it.
