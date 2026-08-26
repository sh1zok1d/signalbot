# Signalbot Research Ledger

**Status:** ACTIVE

This ledger records human research decisions, consumed windows and hypothesis state. Code provenance alone is not enough: repeated inspection of historical results can overfit the research process itself.

## Rules

1. Record confirmatory hypotheses before opening designated validation/OOS whenever possible.
2. Label post-hoc ideas `EXPLORATORY`.
3. A viewed validation/OOS window is consumed for any model revision motivated by that result.
4. Rejected/null experiments remain in the ledger.
5. Threshold/parameter optimization is legitimate on development data, but the selected candidate must be frozen before confirmatory evaluation.
6. Track material search surface/variants; do not present the winning result as one prespecified test if many were tried.
7. Regime explanations discovered after outcomes are exploratory until prospectively gated and independently reproduced.
8. `NO EDGE`, `REJECTED`, and `INCONCLUSIVE_SAMPLE` are valid outcomes.

See `EDGE_RESEARCH_PROTOCOL.md` for the current general protocol.

---

## 2026-08-26 — Project research-direction change

**Decision:** `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN`

Reasoning:

- the current rich historical overlap is roughly one month and is insufficient for durable-edge claims;
- architecture/correctness work has progressed ahead of evidence;
- E1 development results do not justify automatically adding more lifecycle/product complexity;
- the project should first identify and independently validate market mechanisms, then design architecture around what survives.

Active sequence is now:

`finish frozen E1 -> historical expansion -> hypothesis discovery -> development-only tuning -> independent validation/OOS -> rich-feature incremental tests -> forward shadow -> architecture/product restart`.

This decision does **not** reinterpret old E1 results and does not authorize modification of `E1-RUN-001`.

---

## 2026-08-26 — CORE_BTC_BINANCE_V0 accepted for discovery

**Decision:** `CORE_BTC_BINANCE_V0` → `ACCEPTED_FOR_DISCOVERY`

This is dataset authorization only. It is not an edge claim, not a hypothesis result, and not `ACCEPTED_FOR_CONFIRMATORY`.

- snapshot_id: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- date: `2026-08-26`
- frozen interval: `[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)`
- accepted 1m rows: `3,497,760` complete
- missing minutes: `0`
- duplicates: `0`
- conflicting duplicates: `0`
- checksums: `104 / 104` VERIFIED
- materializer SHA: `71d13afdae4456163316b850f340436af1eeed65`
- quality_report_sha256: `c59034e41be571142232d9c283ba898c786b69d6db485dfd2f4641bc84601242`
- source_inventory_sha256: `a4bb39245365b1cc49b626a3dfc2cdcdb00c5be8c622ecd1e123a18d85186ea6`
- contract_sha256: `1c49c8205a92eb9491a065fa1e93bb1fa5592964babdf96fe30b09212e962d3e`
- manifest: `docs/manifests/CORE_BTC_BINANCE_V0.yaml`
- frozen evidence: `docs/research_data/CORE_BTC_BINANCE_V0/`

`research_authorized: true`
`confirmatory_authorized: false`

**NEXT AUTHORIZED PHASE:** mechanism-first discovery research.

Operational start of that phase also requires the materializer implementation commit above to be remotely preserved. This ledger entry does not record any hypothesis test.

---

## Initial hypothesis inventory

These IDs preserve the earlier research history; statuses below do not imply validation.

| ID | Hypothesis | Status |
|---|---|---|
| H-001 | V1 weakness is materially caused by lateness | `DIAGNOSTIC_CONSUMED` |
| H-002 | Multi-timeframe role separation adds quality beyond simpler structure | `E1_TESTING` |
| H-003 | 4h regime conditioning adds incremental value | `E1_TESTING` |
| H-004 | 1h directional bias adds incremental value | `E1_TESTING` |
| H-005 | OI contributes incremental predictive information | `UNRESOLVED` |
| H-006 | Taker flow contributes incremental predictive information | `E1_TESTING` |
| H-007 | Liquidation context contributes incremental predictive information | `UNRESOLVED` |
| H-008 | Funding contributes useful intraday information | `UNRESOLVED` |
| H-009 | Three-venue consensus adds information beyond robust single/median venue baselines | `UNRESOLVED` |
| H-010 | The three V2 setup families are empirically distinct | `E1_TESTING` |
| H-011 | Model confidence meaningfully orders episode quality | `V1_NEGATIVE / V2_UNRESOLVED` |
| H-012 | V2 beats frozen V1 on comparable periods/metrics | `UNRESOLVED` |
| H-013 | V2 beats simple deterministic price-structure controls | `E1_TESTING` |
| H-014 | Any observed edge survives realistic execution delay and costs | `E1_TESTING` |
| H-015 | Any observed edge is not concentrated in one narrow regime/block | `E1_TESTING` |
| H-016 | Stage-5 detectors separate future outcomes from matched controls before lifecycle machinery | `E1_TESTING` |

---

## V1 diagnostic / autopsy

**Status:** `CONSUMED_DIAGNOSTIC`

Observed Telegram shadow sample:

- 5,093 BTCUSDT LONG/SHORT messages;
- 5,085 unique bucket signals;
- 2026-07-25 07:20 UTC -> 2026-08-25 12:45 UTC;
- median cadence ~5m;
- adjacent-direction flip rate ~43.8%;
- exact-5m pair flip rate ~40.1%;
- ~159 signals/day average.

Latency was approximately one extra 5m cycle for nearly all messages. Signal alignment was strong with **past** short-term momentum and weak with future horizons. Confidence was largely a transform of absolute score and did not show convincing future-outcome ordering.

Working death certificate:

> V1 was primarily a 5m reactive momentum detector used as though it were a 15m/1h/4h forecasting product. Additional derivatives/cross-exchange processing did not demonstrate convincing incremental directional value over simple momentum in the inspected sample, while notification latency consumed much of any very-short continuation.

This does not prove that all MTF/derivatives/forecasting hypotheses fail.

---

## E1-RUN-001 — Frozen V2 Stage-5 detector separation

**Date opened for development research:** 2026-08-25  
**Current status:** `DEVELOPMENT_CONSUMED / HOLDOUT_STILL_UNOPENED / FINAL_EVALUATOR_FROZEN`

### Frozen basis

- implementation base: `main@8081eb31657f127141efb3a455f86690258164bc`;
- calculation namespace: `9bed1b4cf99f1644`;
- primary generation excludes Stage-6 lifecycle;
- full candidate window: `[2026-08-02T00:00:00Z, 2026-08-25T17:20:00Z)`;
- legal 5m decision boundaries: `6,832`;
- raw FULL candidates: `290` (`TP=198`, `CB=47`, `FB=45`).

### Frozen split

Candidate-count-only split selected before outcomes:

- development `[2026-08-02T00:00:00Z, 2026-08-16T00:00:00Z)` — `149` FULL (`TP=93`, `CB=30`, `FB=26`);
- holdout `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)` — `141` FULL (`TP=105`, `CB=17`, `FB=19`);
- development +4h purge prevents development future reads from entering holdout.

### Development evidence consumed

- FULL outcomes: 147 full-horizon eligible/reference-usable candidates;
- same-T direction inversion;
- deterministic matched-random controls;
- preregistered ablation/simple-baseline census/outcomes;
- development ablation outcome rows: 2,232 eligible, 28 purged.

### Development-only provisional interpretation

**TREND_PULLBACK**
- FULL near zero at short horizons and adverse at longer horizons;
- removing 4h/1h/context admitted populations that were generally less adverse;
- current MTF context has not earned complexity;
- no simplified positive-edge claim yet.

Prospective pre-holdout state: `SIMPLIFY/KILL`.

**COMPRESSION_BREAKOUT**
- compression selection looked better than ordinary-range breakout;
- taker gate changed little;
- context/taker incremental value not demonstrated;
- stable directional edge not demonstrated.

Prospective pre-holdout state: `SIMPLIFY/INCONCLUSIVE`.

**CONFIRMED_BREAKOUT**
- frozen direction adverse across development horizons;
- inversion/control evidence unfavorable;
- context removal did not rescue it.

Prospective pre-holdout state: strong `KILL` candidate.

### Frozen holdout population

Outcome-free holdout ablation census reproduced FULL exactly:

- TP_FULL = 105;
- CB_FULL = 17;
- FB_FULL = 19;
- FB holdout direction = 19 LONG / 0 SHORT.

This population information was inspected without holdout prices/outcomes.

### Frozen final holdout protocol

Authoritative artifacts:

- `E1_DETECTOR_SEPARATION_PREREG.md`
- `e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`
- `e1/E1_RUN_001_FINAL_HOLDOUT_EVALUATOR_FREEZE.md`
- related `docs/e1/` protocol/clarification files.

The final one-shot evaluation includes, as preregistered/frozen:

- all five horizons;
- FULL / ABLATION_ALL / ADDED_ONLY;
- matched random controls;
- FULL direction inversion;
- fixed +6h same-day circular time-shift control;
- delay 0/+60/+120s;
- total friction 0/5/10/20 bps;
- 30m/60m cluster counts;
- UTC-day concentration/block bootstrap.

### Last verified timestamp-only coverage state

No OHLC/outcomes were read by the preflight.

Last inspected enhanced preflight:

- primary original +4h outcomes: coverage complete;
- preregistered +6h time-shift control: not yet complete at inspection time;
- latest observed Binance 1m bar start: `2026-08-25T21:39:00Z`;
- required shifted-control last bar start: `2026-08-26T00:44:00Z`;
- one historical gap: `2026-08-24T12:29:00Z` (kept as incomplete-path evidence; not repaired);
- `ready_for_single_holdout_outcome_open=false` at that last verified run.

The wall clock has since advanced, but **coverage is not considered passed until the frozen preflight is actually rerun**. Do not infer outcomes from time passage.

### E1 mutation rule

No threshold tuning, direction flip, family change, regime rescue or variant search may occur inside RUN-001 after development inspection.

If E1 suggests a new threshold/regime/strategy, record it as a new exploratory hypothesis and validate it in a new research version/window.

---

## 2026-08-26 — H01_COMPRESSION_EXPANSION development

**Hypothesis:** `H01_COMPRESSION_EXPANSION`

Non-directional mechanism test: does unusually low recent BTC realized volatility relative to its own recent history predict a subsequent increase in realized volatility?

- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- prereg commit: `52d8731fbb2a8b0eea42d66a3772ba876f319331`
- research code SHA at outcome run: `d90a9e126a27af28bb652e0645fa2a5c403ca26d`
- development window: `2020-02-01T00:00:00Z` → `2025-01-01T00:00:00Z` with `T + 240m < 2025-01-01T00:00:00Z`
- validation: **UNTOUCHED** (2025 not inspected)
- OOS: **UNTOUCHED** (2026 not inspected)
- search surface: 3 L × 3 q × 5 H = 45 primary cells
- outcome status: `EXPLORATORY`
- development verdict: **`H01_KILL`** / **`REJECTED`**

Eligible development 15m boundaries: 172400.

Primary result: all 45 cells show lower—not higher—normalized future RV after compression (means ~0.61–0.80 vs baseline ~1.18–1.25). Expansion probability ~0.023–0.072 vs baseline ~0.255. Matched-random and month-permutation controls restore values near the unconditional baseline. Week-block bootstrap 95% intervals for candidate-minus-baseline are entirely negative. All five development years are negative. Stronger compression is more negative. Secondary range agrees.

This is consistent with volatility persistence, which is the opposite of the preregistered expansion mechanism. The reverse relationship is **not** promoted to a new candidate in this entry.

Preregistration: `docs/research/H01_COMPRESSION_EXPANSION_PREREG.md`
Development evidence: `docs/research/H01_DEV_SUMMARY.md`, `docs/research/H01_DEV_RESULTS.json`

Do not open 2025 or 2026 for H01. Do not start R3 for H01.

The reverse volatility-persistence pattern is **not** validated evidence and is not a new authorized hypothesis.

---

## 2026-08-26 — H02_FAILED_BREAKOUT_MEAN_REVERSION development

**Hypothesis:** `H02_FAILED_BREAKOUT_MEAN_REVERSION`

Directional mean-reversion test: when BTC briefly breaches a local 5m range but closes back inside, does subsequent price tend to continue toward the range versus an ordinary/random boundary event?

- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- prereg commit: `92d130f0e26aa993e8e0a231eceb95db20ff47f0`
- research code SHA at outcome run: `92d130f0e26aa993e8e0a231eceb95db20ff47f0`
- development window: `2020-02-01T00:00:00Z` → `2025-01-01T00:00:00Z` with `T + 240m < 2025-01-01T00:00:00Z`
- validation: **UNTOUCHED**
- OOS: **UNTOUCHED**
- search surface: 3 lookbacks × 3 overshoot thresholds × 5 horizons = 45 primary cells
- outcome status: `EXPLORATORY`
- development verdict: **`H02_KILL`**

H01 remains `H01_COMPRESSION_EXPANSION = REJECTED / H01_KILL`. Do not reinterpret H01 reverse-volatility as validated evidence.

Primary result: a small short-horizon (15–30m) s=0.00 bump versus matched-random (~0.03–0.06 normalized, ~1 bp, P(REV>0)~0.54) that weakens under +6h shift, but successful-breakout control is *stronger* on the same reversion sign. Stronger overshoot is worse. Effect fades by 120–240m. UPPER is weaker than LOWER. Closing back inside did not earn a failed-breakout-specific mechanism.

Preregistration: `docs/research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md`
Development evidence: `docs/research/H02_DEV_SUMMARY.md`, `docs/research/H02_DEV_RESULTS.json`

Do not open 2025 or 2026 for H02. Do not start R3. Do not add volume/taker/trend gates.

---

## Next research program — hypothesis discovery after E1

Status: `AUTHORIZED_FOR_DISCOVERY / NOT YET CONFIRMATORY`.

`CORE_BTC_BINANCE_V0` is `ACCEPTED_FOR_DISCOVERY` (snapshot `717d37a4`).

Recorded discovery runs:

- `H01_COMPRESSION_EXPANSION` = `REJECTED / H01_KILL`
- `H02_FAILED_BREAKOUT_MEAN_REVERSION` = `H02_KILL`

Remaining mechanism classes still untested:

- trend pullback -> continuation;
- extreme impulse -> continuation vs exhaustion;
- price/OI divergence;
- crowded positioning -> reversal risk.

These are not edge claims and not implementation authorization.

A new run receives its own ID, dataset split, variant/search accounting and frozen confirmatory protocol under `EDGE_RESEARCH_PROTOCOL.md`.

---

## Future-hypothesis quarantine

The following remain ideas only until justified by a specific mechanism and research plan:

- cross-venue lead/lag/divergence alpha;
- order-book features;
- spot/CVD;
- vendor liquidation maps;
- macro/news features;
- ML/adaptive thresholds;
- new setup families;
- broad multi-symbol expansion used merely to increase row count.

Recording an idea is not permission to implement it.