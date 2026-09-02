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

## 2026-08-27 — H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION preregistration

**Hypothesis:** `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION`

Directional, symmetric mechanism test: after an unusually extreme short-horizon
BTC impulse (top-decile-and-beyond percentile of its own recent absolute
return distribution, W ∈ {15, 30, 60}m), does subsequent price tend toward
continuation in the impulse direction, or toward exhaustion/reversal, versus
matched-random, moderate-momentum-structural and +6h-shift negative controls?

This is preregistration + implementation freeze only. **No development
outcomes have been computed.** No real accepted parquet was read.

- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- prereg commit: this commit (preregistration MD/JSON, implementation,
  tests, and this ledger entry are frozen together in a single commit; see
  `docs/research/H03_EXTREME_IMPULSE_PREREG.md` / `.json`)
- development window: `2020-02-01T00:00:00Z` → `2025-01-01T00:00:00Z` with
  `T + H_minutes < 2025-01-01T00:00:00Z` for every horizon (no truncation)
- development: **NOT YET RUN** (state: `NOT_OPENED`)
- validation: **UNTOUCHED** (2025 not inspected)
- OOS: **UNTOUCHED** (2026 not inspected)
- outcome status: `PRE_REGISTERED / EXPLORATORY`
- primary search surface: 3 impulse windows × 3 tail thresholds × 5 horizons
  = **45 primary cells** (this batch: H01 = 45, H02 = 45, H03 = 45)
- global adaptivity: H03's mechanism class predates H01/H02 (original R2
  roadmap); it inherits the 15m decision grid/30-day local reference from
  H01 and the 15/30/60/120/240m outcome ladder, 100-replicate matched-random
  convention, UTC-week-block bootstrap and +6h timing control from prior
  H01/H02 project convention; it does **not** inherit H02's refractory
  (H02 = 30m, H03 = 60m, not copied), the q90/95/98 tail-threshold grid, or
  the W ∈ {15,30,60}m impulse windows (none copied from H01's 30/60/120m
  lookbacks or H02's 60/120/240m lookbacks) — these are new, pre-outcome
  H03-specific choices. Prior H01/H02 clustering/dependence experience
  influenced the decision to make H03's refractory and dependence reporting
  explicit (disclosed, not hidden). H01/H02 post-hoc observations
  (`POSTHOC_UNTESTED`) did not define H03's mechanism, signs, or thresholds.
  H03 is not claimed to be fully independent of, nor derived from, H01/H02.
- control formulations: moderate-momentum structural control
  (`0.60 <= P_W(T) < 0.80`, matched month+direction where possible);
  matched-random baseline (100 replicates, seed `20260831` consumed
  exactly once, without-replacement sampling, month/direction composition
  preserved, TVD residual diagnostic); +6h same-UTC-day circular-shift
  negative control (collision-fraction against raw true extremes always
  reported, never removed; diurnal-confound limitation disclosed)
- alternative controls attempted: **NONE**
- MPIE (mechanism-relevance floor): `0.10` normalized units, independent of
  candidate outcome; `CONTROL_DELTA_MIN = 0.05` for both structural and
  negative-control gates, frozen, never reinterpreted after outcomes
- long-dependence diagnostic: fixed lags {1,2,4,8,16,32,64} days,
  `|ACF| >= 0.20`, uses the **largest** qualifying lag (not first crossing)
- verdict vocabulary (exactly 4 labels): `H03_CONTINUATION_CANDIDATE_FOR_FREEZE`,
  `H03_EXHAUSTION_CANDIDATE_FOR_FREEZE`, `H03_INCONCLUSIVE`,
  `H03_REJECTED_SPECIFIC_CLAIM`
- real H03 outcomes inspected: **NO**
- no R3 opened; no validation opened; no product/forecasting code touched

Preregistration: `docs/research/H03_EXTREME_IMPULSE_PREREG.md`,
`docs/research/H03_EXTREME_IMPULSE_PREREG.json`
Implementation (frozen, unexercised against real data in this task):
`scripts/research/h03_extreme_impulse.py`,
`scripts/research/h03_extreme_impulse_lib.py`
Tests (synthetic fixtures only): `tests/research/test_h03_extreme_impulse.py`

Do not run real H03 market outcomes under this entry. Do not open 2025 or
2026 for H03. Do not start R3 for H03.

---

## 2026-08-27 — H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION development

**Hypothesis:** `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION`

- `H03_PREREG_SHA`: `e2c370d70ca3dc5952ad9c82808e6b877805f998`
- research-code SHA used for the outcome run: `4e995440e649b37bdc0a9f0100a3e0b369573f6c`
  (software-blocker fix after prereg: matched-random pool excludes by panel-index
  membership; no research-parameter change; prereg SHA not amended)
- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- development: `2020-02-01` → `2025-01-01` (with `T+H` strictly before 2025-01-01)
- validation: **UNTOUCHED**
- OOS: **UNTOUCHED**
- search surface: **45 primary cells**
- global prior: H01 45, H02 45
- outcome status: `EXPLORATORY`
- development verdict: **`H03_REJECTED_SPECIFIC_CLAIM`**

H01 remains `H01_COMPRESSION_EXPANSION = REJECTED / H01_KILL`.
H02 remains `H02_FAILED_BREAKOUT_MEAN_REVERSION = H02_KILL`.
Do not reinterpret either.

Primary result: mixed-null surface. All 45 medians negative; all 45
`P(CONT_RET_H>0)<0.5`; means 14 positive / 31 negative. MPIE 0.10 vs
matched-random holds in only 3 continuation cells and 11 exhaustion cells,
not a q/W/H neighborhood. q95 vs q98 sign-flips at W=60 H=15. Horizon
sign-flips (short-H continuation-looking means vs longer-H exhaustion-looking
means). UP/DOWN mixed in 34/45 cells. Years are not 4/5 stable. Largest-month
share 2.7–3.4%. `L_dep=32 days`. Week-block bootstrap intervals were not
emitted by the frozen runner; not required because there is no candidate.
Secondary MFE/MAE were not persisted at cell level and cannot rescue primary.

Post-hoc observations (all `POSTHOC_UNTESTED`, none may rescue H03):

- isolated W=15 q=0.98 H=15/30 continuation MPIE (and W=60 q=0.95 H=15)
- longer-H more often negative vs matched-random
- DOWN more negative than UP in 39/45 cells
- 2023 often the most negative year
- median/count exhaustion vs tail-pulled positive means

Preregistration: `docs/research/H03_EXTREME_IMPULSE_PREREG.md`
Development evidence: `docs/research/H03_DEV_SUMMARY.md`,
`docs/research/H03_DEV_RESULTS.json`

Do not open 2025 or 2026 for H03. Do not start R3. Do not start H04.

---

## 2026-08-27 — H04_TREND_PULLBACK_CONTINUATION preregistration

**Status of this entry: `SUPERSEDED_PRE_OUTCOME`.** See the entry directly
below ("H04_TREND_PULLBACK_CONTINUATION preregistration correction") for
`H04_PREREG_SHA_V1`'s supersession and the new authoritative prereg SHA.
No real H04 market outcomes were computed under this prereg before
supersession.

**Hypothesis:** `H04_TREND_PULLBACK_CONTINUATION`

Directional, symmetric, continuation-only mechanism test: after BTC
establishes a strong directional move over a longer backward window
(`L ∈ {240, 480, 960}` minutes) and then undergoes a partial counter-trend
pullback that does not erase that move, does subsequent price tend to
continue in the original trend direction? The specific claimed incremental
ingredient is pullback after established trend, not generic trend
persistence — the structural control exists specifically to test this.

This is preregistration + implementation freeze only. **No development
outcomes have been computed.** No real accepted parquet was read.

- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- prereg commit: this commit (preregistration MD/JSON, implementation,
  tests, and this ledger entry are frozen together in a single commit; see
  `docs/research/H04_TREND_PULLBACK_PREREG.md` / `.json`)
- design provenance: `docs/reviews/H04_DESIGN_REDTEAM.md` (Claude red-team,
  branch `research/h04-design-redteam`) and
  `docs/reviews/H04_DESIGN_MAINTAINER_ADDENDUM.md` (maintainer correction of
  the structural control and the depth-band robustness rule); PR #80
- development window: `2020-02-01T00:00:00Z` → `2025-01-01T00:00:00Z` with
  `T + H_minutes < 2025-01-01T00:00:00Z` for every horizon (no truncation)
- development: **NOT YET RUN** (state: `NOT_OPENED`)
- validation: **UNTOUCHED** (2025 not inspected)
- OOS: **UNTOUCHED** (2026 not inspected)
- outcome status: `PRE_REGISTERED / EXPLORATORY`
- primary search surface: 3 trend lookbacks × 3 exclusive depth bands ×
  5 horizons = **45 primary cells** (this batch: H01 = 45, H02 = 45,
  H03 = 45, H04 = 45)
- global adaptivity: H04's mechanism class predates H01/H02/H03 (named in
  the original R2 roadmap before "extreme impulse", verified against
  `docs/RESEARCH_ROADMAP.md`). `L={240,480,960}`, `P=60m`, `q=0.80`, and the
  depth-band construction are new to H04. `q=0.80`'s looseness is disclosed
  as **PARTIALLY** batch-adaptive (plausibly shaped by H03's fragile
  tight-tail `q=0.98` cells); the mechanism class itself is not adaptive.
  H01/H02/H03 post-hoc observations are not imported as H04 gates/features.
- control formulations considered (all pre-outcome, at the design-review
  stage): mirror extension (rejected — same-direction extension is itself
  plausibly mean-reversion-prone), "all established-trend moments
  irrespective of the P-window" (rejected — contaminated by containing
  other pullbacks/extensions), final adopted: established trend + near-
  neutral recent move (`abs(RECENT_RATIO)<0.10`, reusing the existing
  shallow-depth edge, no new numeric parameter); negative control: `+6h`
  circular shift
- alternative controls attempted: the two rejected structural-control
  formulations above (mirror extension; all-trend-moments) — recorded here
  per the ledger's control-formulations-attempted requirement, not silently
  omitted
- MPIE = `0.10` (reused unchanged from H03, before H03's own outcomes);
  `CONTROL_DELTA_MIN = 0.05`
- implementation carries forward three H03 post-freeze-audit lessons:
  membership-based (not positional) matched-random pool exclusion;
  real-timestamp (never panel-index) calendar keys; the week-block
  bootstrap wired into per-cell output from the start (H03 left this
  library-only and unwired)
- real H04 outcomes inspected: **NO**
- no R3 opened; no H05 opened; no product/forecasting code touched

Preregistration: `docs/research/H04_TREND_PULLBACK_PREREG.md`,
`docs/research/H04_TREND_PULLBACK_PREREG.json`
Implementation (frozen, unexercised against real data in this task):
`scripts/research/h04_trend_pullback_continuation.py`,
`scripts/research/h04_trend_pullback_continuation_lib.py`
Tests (synthetic fixtures only): `tests/research/test_h04_trend_pullback_continuation.py`

Do not run real H04 market outcomes under this entry. Do not open 2025 or
2026 for H04. Do not start R3 or H05 for H04.

---

## 2026-08-27 — H04_TREND_PULLBACK_CONTINUATION preregistration correction

**Hypothesis:** `H04_TREND_PULLBACK_CONTINUATION`

Narrow pre-outcome correction discovered during independent implementation
review — not a research-parameter change, not a market-result-motivated
change. **Real H04 market outcomes inspected before this correction: NO.**

- original prereg (`H04_PREREG_SHA_V1`): `314292ed9824e824522274d1b64874bf91d71b23`
  — status **`SUPERSEDED_PRE_OUTCOME`**, preserved unamended
- new prereg (`H04_PREREG_SHA`): this commit (the correction, the updated
  MD/JSON, the implementation fix, the new synthetic regression tests, and
  this ledger entry are frozen together in a single normal descendant
  commit; `H04_PREREG_SHA_V1` was not amended)
- reason for supersession: `structural_control_bundle` computed the primary
  structural-control comparison from the entire eligible near-neutral
  control population, while the frozen design's calendar-month ×
  trend-direction × trend-strength-bin matching was implemented only as a
  coverage diagnostic rather than the actual comparison. A generic
  composition difference between the candidate and near-neutral control
  populations (e.g. concentration in different trend-strength bins) could
  therefore be mistaken for a pullback-specific effect, in either direction
  (false positive or false negative)
- correction: `structural_control_bundle` now computes a frozen
  deterministic stratified standardization — the structural comparison is
  restricted to the exact overlap strata (candidate and control both
  present), weighted by the candidate's own stratum frequency;
  control-only strata receive zero candidate weight; unmatched candidates
  are reported explicitly, never silently dropped, and do not enter the
  standardized comparison. No new bins, no random matching seed, no new
  numeric parameter
- bootstrap-scope clarification (not a redesign): the prereg MD/JSON now
  explicitly state that the UTC-week block bootstrap applies only to the
  candidate population's own primary outcome mean/positive-share, is not a
  confidence interval for the MPIE candidate-minus-matched contrast, and
  that matched-random uncertainty remains the frozen 100-replicate
  distribution, now additionally summarized by persisted `p025`/`p50`/`p975`
- unchanged by this correction: `P=60m`; `L={240,480,960}`; `q=0.80`;
  exclusive depth bands; `H={15,30,60,120,240}`; 60m refractory;
  `MPIE=0.10`; `CONTROL_DELTA_MIN=0.05`; `+6h` negative control;
  two-adjacent-depth-band rule; two-adjacent-horizon rule; 4/5-year rule;
  UPTREND/DOWNTREND symmetry; matched-random seed `20260902`; bootstrap
  seed `20260903`; 45-cell primary search surface
- validation: **UNTOUCHED**; OOS: **UNTOUCHED**
- outcome status: `PRE_REGISTERED / EXPLORATORY`
- real H04 market outcomes inspected before or during this correction:
  **NO**

Design audit: `docs/reviews/H04_PREREG_PREOUTCOME_CORRECTION.md`

Do not open 2025 or 2026 for H04. Do not start R3 or H05 for H04.

---

## 2026-08-27 — H04_TREND_PULLBACK_CONTINUATION implementation completion

**Hypothesis:** `H04_TREND_PULLBACK_CONTINUATION`

Implementation-completeness gap closed pre-outcome — **not** a prereg
change. The preregistration already froze fixed 1w/2w/4w UTC-week
block-sensitivity reporting (§17); only `week_block_bootstrap` (single-week
blocks) had been implemented. **Real H04 market outcomes inspected before
this completion: NO.**

- `H04_PREREG_SHA` (unchanged, not superseded, not amended):
  `c629cac4c6ed1a0d129b812ef022d98a0dba4c1b`
- `H04_RESEARCH_CODE_FREEZE_SHA`: this commit (the completed
  `dependence_sensitivity_bundle` implementation, the new synthetic
  regression tests, and this ledger entry are frozen together in a single
  normal descendant commit)
- gap: no 2-week/4-week block-sensitivity implementation existed; fixed by
  `block_bootstrap_sensitivity` / `dependence_sensitivity_bundle`
  (`scripts/research/h04_trend_pullback_continuation_lib.py`), computed
  unconditionally for every cell (no post-outcome code path)
- block construction: consecutive, non-overlapping groups of the frozen
  block size over chronologically sorted UTC weeks present in the
  candidate sample; a final incomplete group is retained as one shorter
  terminal block (never discarded)
- seed derivation: `1w` uses the frozen master seed `20260903` directly
  (numerically identical to the legacy `week_block_bootstrap`); `2w`/`4w`
  derive independent deterministic child streams via
  `np.random.SeedSequence([20260903, block_size_weeks])` — never
  outcome-dependent, never re-rolled
- primary search surface, all frozen parameters, and all gates: unchanged
  (`45` primary cells; `P=60m`; `L={240,480,960}`; `q=0.80`; exclusive
  depth bands; `H={15,30,60,120,240}`; 60m refractory; `MPIE=0.10`;
  `CONTROL_DELTA_MIN=0.05`; matched-random seed `20260902`; structural
  standardization; `+6h` control; two-adjacent-band/H rules; 4/5-year rule;
  UP/DOWN symmetry)
- these remain diagnostics/uncertainty sensitivity — no new primary cells,
  no additional hypotheses
- real H04 outcomes before or during this completion: **NO**

Implementation audit: `docs/reviews/H04_PREOUTCOME_IMPLEMENTATION_COMPLETION.md`

Do not open 2025 or 2026 for H04. Do not start R3 or H05 for H04.

---

## 2026-08-27 — H04_TREND_PULLBACK_CONTINUATION development

**Hypothesis:** `H04_TREND_PULLBACK_CONTINUATION`

- `H04_PREREG_SHA`: `c629cac4c6ed1a0d129b812ef022d98a0dba4c1b`
- `H04_RESEARCH_CODE_FREEZE_SHA`: `7bfdc44a305035a641c25f9d3ee75c6ef652ece0`
- research-code SHA in runner JSON: `7bfdc44a305035a641c25f9d3ee75c6ef652ece0`
- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- development outcome access: **CONSUMED** (one `--stage dev-run`, 2020-02-01 → 2025-01-01)
- 2025 validation: **UNTOUCHED**
- 2026 final OOS: **UNTOUCHED**
- search surface: **45 primary cells** (3 L × 3 exclusive depth bands × 5 H)
- global prior: H01 45, H02 45, H03 45
- outcome status: `EXPLORATORY`
- development verdict: **`H04_REJECTED_SPECIFIC_CLAIM`**

H01/H02/H03 remain rejected/killed. Do not reinterpret them. Their post-hoc observations were not used as H04 gates.

Primary result: mixed 45-cell surface. MPIE 0.10 holds in 16/45 cells, concentrated in the exclusive **moderate** band at L=480 and L=960. Adjacent shallow misses MPIE at short H. Adjacent deep is often negative vs matched-random at H=15. Frozen rule: one isolated depth band cannot promote H04. Standardized structural delta and +6h are incomplete even inside the best slices. Largest-month share 2.9–5.4%. `L_dep=32 days`. No H04 source change after outcomes.

Post-hoc observations (all `POSTHOC_UNTESTED`, none may rescue H04):

- L=480/960 moderate-only continuation
- L=960 shallow H=120/240 MPIE
- deep short-H reversal at L=480/960
- 2022 often the most negative year on shorter L
- UPTREND stronger than DOWNTREND in many shallow cells

Preregistration: `docs/research/H04_TREND_PULLBACK_PREREG.md`
Development evidence: `docs/research/H04_DEV_SUMMARY.md`, `docs/research/H04_DEV_RESULTS.json`
Audit: `docs/reviews/H04_DEVELOPMENT_RESULT_AUDIT.md`

Do not open 2025 or 2026 for H04. Do not start R3. Do not start H05.

---

### H05 — Taker Imbalance -> Subsequent Return Distribution (design, pre-outcome)

Branch: `research/h05-design-redteam`, created from H04 result commit
`0c89fc01ac464028440039aff34f92204b2588b9`. PR: draft, base
`research/h04-trend-pullback-discovery`.

**H05 development: NOT OPENED. 2025: UNTOUCHED. 2026: UNTOUCHED. Real H05
outcomes: NO.**

This round is design/red-team only: `docs/research/H05_TAKER_IMBALANCE_DESIGN.md`
(the frozen-candidate design) and `docs/reviews/H05_DESIGN_REDTEAM.md`
(the adversarial review that produced it). No prereg SHA has been cut. No
implementation code exists. No synthetic-fixture tests exist yet. No real
`CORE_BTC_BINANCE_V0` parquet rows were read; only the manifest schema
(field names / allowed arithmetic derivations) and repository governance
documents were consulted.

Frozen in this design (subject to the same pre-outcome-only correction
discipline used for H03/H04): primary feature `TAKER_IMBALANCE_W`
(base-volume primary, quote-volume diagnostic-only); both **continuation**
and **reversal** signs preregistered together with an explicit
anti-cherry-pick rule; nested `q ∈ {0.80, 0.90, 0.95}` extremeness family
on a trailing-30-day midrank percentile of `ABS_IMBALANCE_W`; fixed
`W ∈ {15, 30, 60}` / `H ∈ {15, 30, 60, 120, 240}` (45-cell primary search
surface, sign multiplicity disclosed separately); structural control with
a fixed "ordinary" band `[0.60, 0.80)` decoupled from the `q` under test
(closing a cross-cell-contamination gap present in the raw starting
proposal), candidate-weighted standardization over five strata (see
correction below); matched-random baseline (month + direction, seed
`20260904`, 100 replicates); `+6h` negative control; `MPIE=0.10` /
`CONTROL_DELTA_MIN=0.05` reused unchanged; UTC-week block bootstrap (seed
`20260905`, 2000 replicates) with 1w/2w/4w sensitivity wired in from the
start; 14-item candidate-for-freeze checklist; 4-label verdict
vocabulary.

Global search-surface ledger: H01-H04 previously accounted for 180 cells;
H05 adds 45 -> running total **225** cells. Sign multiplicity (2 signs on
the same 45 cells) recorded separately, not added to the 225 total.

No H01/H02/H03/H04 files were modified. No H03/H04 mechanism conclusions
were imported as H05 design inputs; only implementation lessons
(membership-safe pool exclusion, real-timestamp calendar keys,
candidate-weighted standardization, 1w/2w/4w wiring, post-hoc quarantine
discipline) were reused.

**PRE-OUTCOME DESIGN CORRECTION (same round, no real H05 outcomes
inspected):** independent pre-outcome review found two material control
gaps and two formalization gaps, all closed without seeing any real H05
outcome:

1. Matching on `D` (sign of taker imbalance) did not control the sign of
   contemporaneous price return, leaving price-momentum direction
   uncontrolled. Fixed by adding `price_alignment = sign(D * PRICE_RET_W)
   ∈ {ALIGNED, OPPOSED}` (exact zero -> `OPPOSED`, frozen/deterministic)
   as a mandatory structural-match dimension alongside the existing
   magnitude-only `price_strength_bin`.
2. Activity/volume was left descriptive-only, which cannot support the
   research question's "beyond ordinary market activity" clause. Fixed by
   promoting `activity_bin` (causal 2-level split of trailing-30d
   `TOTAL_W` percentile at 0.50) to a mandatory structural-match
   dimension. The structural control now standardizes over five strata:
   `calendar_month x D x price_alignment x price_strength_bin x
   activity_bin`. Insufficient overlap support under this stratification
   yields `INCONCLUSIVE`, never a post-outcome loosening.
3. The long-dependence diagnostic was mislabeled "candidate-independent"
   while being computed from each cell's own candidate indicator (which
   varies with `W`/`q`). Renamed **outcome-independent, cell-specific
   candidate-clustering diagnostic**; computation unchanged.
4. The checklist's "dependence-adjusted significance survives at 1w/2w/4w"
   wording was underspecified. Frozen precisely: the candidate primary
   mean's own UTC-week block-bootstrap interval must exclude zero in the
   declared direction (`p025>0` continuation / `p975<0` reversal) at each
   of 1w/2w/4w, explicitly distinguished from the matched-random
   distribution and the structural-control delta (three separate
   estimands, never substituted for one another).

A fifth, lighter re-evaluation tightened `W` robustness from a pure
"no severe contradiction" check to a directional-consistency requirement:
at least one adjacent `W` must agree in the direction of primary sign,
`candidate_minus_matched`, and structural delta (without needing to clear
full `MPIE`/`CONTROL_DELTA_MIN`); a fully isolated `W` can no longer reach
`CANDIDATE_FOR_FREEZE`.

Unchanged by this correction: mechanism, both signs, `W`/`q`/`H` surface
(still 45 cells), Batch01 225-cell total, refractory rule, `MPIE`,
`CONTROL_DELTA_MIN`, all seeds, `+6h` negative control, BUY/SELL symmetry,
4/5-year rule. 2025/2026 remain untouched throughout.

**PRE-OUTCOME SYMMETRIC-GATE FORMALIZATION (same round, no real H05
outcomes inspected):** a third independent pre-outcome review found the
candidate-for-freeze checklist expressed `MPIE`, structural, and matched
gates as bare positive inequalities, which silently assumed CONTINUATION
and made REVERSAL semantics ambiguous/impossible, and that `MPIE` had
drifted from its established Batch01 meaning (practical separation from
the matched-random baseline) toward an undefined "standardized effect
size"; the `+6h` gate was also only qualitatively described. Closed via
one frozen orientation variable:

```
S = +1 (CONTINUATION) / -1 (REVERSAL)
ORIENTED_PRIMARY          = S * candidate_mean
ORIENTED_MATCHED_DELTA    = S * (candidate_mean - matched_mean)
ORIENTED_STRUCTURAL_DELTA = S * (candidate_mean - structural_mean)
ORIENTED_SHIFT_DELTA      = S * (candidate_mean - shifted_mean)
```

with every gate now `ORIENTED_* >= threshold`, applying identically to
both signs. The **stored** primary metric `X = NORM_TAKER_RET_H` is
unchanged and never re-signed; `S` is applied only at the gate-evaluation
layer. Restored: `MPIE=0.10` gates `ORIENTED_MATCHED_DELTA` specifically;
`CONTROL_DELTA_MIN=0.05` gates both `ORIENTED_STRUCTURAL_DELTA` and
`ORIENTED_SHIFT_DELTA`; `ORIENTED_PRIMARY > 0` is now an explicit,
separate requirement (control separation alone cannot promote a cell
whose own raw effect points the wrong way). The `q`/`H`/`W` neighborhood
rules, BUY/SELL symmetry, and year-stability rule are restated using the
same `S` so "supports the declared sign" has one unambiguous meaning for
both claim orientations. No numeric threshold, seed, mechanism, or
`W`/`q`/`H` surface value changed — only the sign-orientation and
precision of the existing gates.

Do not start H05 implementation until this design review is separately
authorized to proceed. Do not open 2025 or 2026 for H05. After H05
closes, the next mandatory step is Batch01 synthesis, not H06.

---

### H05 — Taker Imbalance -> Subsequent Return Distribution (prereg + implementation freeze)

Branch: `research/h05-taker-imbalance-discovery`, created from the
authoritative design HEAD `deaf6503896920685f25a03230174d360a07ab9a`
(branch `research/h05-design-redteam`, PR #82, OPEN/DRAFT/UNMERGED). This
freeze round base branch is `research/h05-design-redteam` (PR isolates
prereg/implementation diff from the completed design).

**H05 status: PRE_REGISTERED / IMPLEMENTATION_FROZEN /
DEVELOPMENT_NOT_OPENED.**

Dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
(`CORE_BTC_BINANCE_V0`, `ACCEPTED_FOR_DISCOVERY`).

`H05_PREREG_SHA` and `H05_RESEARCH_CODE_FREEZE_SHA` (initially the same
commit): see the commit that adds this entry (suggested message
`research(h05): freeze taker imbalance prereg and implementation`).

Artifacts: `docs/research/H05_TAKER_IMBALANCE_PREREG.md` (prose
preregistration), `docs/research/H05_TAKER_IMBALANCE_PREREG.json`
(machine-readable frozen spec — every frozen rule that appears in the MD
also appears in the JSON), `scripts/research/h05_taker_imbalance_lib.py` /
`scripts/research/h05_taker_imbalance.py` (frozen implementation, CLI
supports `--stage identity` and `--stage dev-run`),
`tests/research/test_h05_taker_imbalance.py` (65 synthetic-fixture-only
tests, all passing), `docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md`
(independent pre-outcome implementation audit; no objective blockers
found).

This preregistration encodes, without redesigning, the authoritative
design: `TAKER_IMBALANCE_W` (base-volume primary, quote-volume never even
referenced in the implementation); both continuation (`S=+1`) and
reversal (`S=-1`) preregistered on the same 45 cells with the anti-cherry
-pick rule; nested `q ∈ {0.80,0.90,0.95}`; `W ∈ {15,30,60}` /
`H ∈ {15,30,60,120,240}`; fixed ordinary-flow band `[0.60,0.80)`; five
-dimensional candidate-weighted structural strata (`calendar_month × D ×
price_alignment × price_strength_bin × activity_bin`); matched-random
(month+D, seed `20260904`, 100 replicates, membership-safe exclusion);
`+6h` negative control with the exact `ORIENTED_SHIFT_DELTA >=
CONTROL_DELTA_MIN` gate; the full `S`-oriented gate formalism
(`ORIENTED_PRIMARY>0`, `ORIENTED_MATCHED_DELTA>=MPIE`,
`ORIENTED_STRUCTURAL_DELTA>=CONTROL_DELTA_MIN`,
`ORIENTED_SHIFT_DELTA>=CONTROL_DELTA_MIN`); UTC-week block bootstrap (seed
`20260905`, 2000 replicates) with 1w/2w/4w sensitivity wired in from this
first commit; the outcome-independent, cell-specific candidate-clustering
diagnostic; `q`/`H`/`W` robustness rules (2-of-3 adjacent `q`, 2-adjacent
`H`, ≥1-adjacent-directional-support `W`); 4/5-year stability; BUY/SELL
symmetry; the 4-label verdict vocabulary; and the full post-hoc
quarantine list.

Search accounting: 45 primary cells (`W=3 × q=3 × H=5`). Batch01
cumulative: **225** cells (H01-H04 = 180 + H05's 45). Sign multiplicity
(continuation + reversal on the same 45 cells) disclosed separately, not
added to the 225 total.

**Real H05 outcomes computed: NO. Development: NOT OPENED** (`--stage
dev-run` was not invoked against real accepted parquet in this task —
only `--stage identity` and the synthetic test suite were exercised).
**2025: UNTOUCHED. 2026: UNTOUCHED.**

No H01-H04 files were modified. No H01-H04 outcome-derived market
conclusion was imported; only implementation lessons (membership-safe
pool exclusion, real-timestamp calendar keys, candidate-weighted
structural standardization, 1w/2w/4w wiring from the first commit) were
reused, matching this module's own independent implementation (no shared
import from any H01-H04 script).

Do not run `--stage dev-run` against real data yet. Do not open 2025 or
2026 for H05. Do not start Batch01 synthesis yet. Do not start H06 (H05
is the fifth and final primary mechanism family of R2 Batch 01 — Batch01
synthesis is the next mandatory step once H05 actually closes with a
real-outcome verdict).

---

### H05 — pre-outcome structural-support correction

`H05_PREREG_SHA_V1` = `9502006eb4797a9947c61d8d04acd1345ed41e5e` is
preserved, unamended, status **SUPERSEDED_PRE_OUTCOME**.

**Reason:** an independent pre-outcome audit found that V1's structural
gate/delta compared the FULL (unrestricted) candidate-population mean
against a control mean standardized only over candidate/control overlap
strata — quantities on different support. If unmatched candidate strata
had systematically different outcomes, they could move the full candidate
mean while having no corresponding structural-control observation at all,
letting the gate pass or fail on composition the control never actually
saw. **No real H05 outcome was inspected to find or fix this.**

**Fix (this round, normal descendant commit, suggested message
`research(h05): align structural gate on overlap support`):** the
structural comparison is now like-with-like — both
`candidate_overlap_standardized_mean` and
`structural_control_standardized_mean` are computed over exactly the same
overlap strata with exactly the same candidate-frequency weights `w_s`;
`structural_delta` is their difference, and every `ORIENTED_STRUCTURAL_
DELTA` gate consumes this delta directly. The full, unrestricted
candidate mean (`full_candidate_mean`) is retained for transparency only
and no longer enters the structural delta; it remains unchanged as the
estimand for every other gate (primary, matched, shift, bootstrap, year
stability, BUY/SELL symmetry) — matched-random and `+6h` are not
restricted by structural-control overlap. Zero overlap strata still
routes to `INCONCLUSIVE` (`structural_delta = None`), never a fabricated
numeric effect.

**New `H05_PREREG_SHA`** and, since the implementation is fully frozen in
the same commit, **new `H05_RESEARCH_CODE_FREEZE_SHA`**: the commit that
adds this entry. Updated files:
`docs/research/H05_TAKER_IMBALANCE_PREREG.md` / `.json` (version_history
entry added, `structural_control`/`claim_orientation` sections
corrected), `scripts/research/h05_taker_imbalance_lib.py`
(`structural_control_bundle`, `claim_evaluation`, `directional_support`
corrected; new `oriented_from_delta`/`gate_from_delta` helpers),
`tests/research/test_h05_taker_imbalance.py` (8 new
structural-support-correction regression tests, all existing tests
updated for the corrected field names — 73 tests total, all passing),
`docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md` (section 6/26/27
updated in place), and this ledger entry.

No design parameter changed: mechanism, both signs, `W`/`q`/`H` surface
(45 cells), Batch01 225-cell total, five structural dimensions,
price-alignment/activity semantics, refractory, seeds, `MPIE=0.10`,
`CONTROL_DELTA_MIN=0.05`, `+6h`, `q`/`H`/`W` robustness rules, 4/5-year
rule, BUY/SELL symmetry, candidate-clustering diagnostic, and 2025/2026
protection are all unchanged.

Real H05 outcomes computed: **NO**. Development: **NOT OPENED**. 2025:
**UNTOUCHED**. 2026: **UNTOUCHED**. `--stage dev-run` was not invoked;
only `--stage identity` and the synthetic test suite were exercised.

Do not run `--stage dev-run` against real data yet. Do not open 2025 or
2026 for H05. Do not start Batch01 synthesis yet. Do not start H06.

---

### H05 — second pre-outcome audit round: B-01 re-verification + M-01..M-05 bounded repair

Branch: `research/h05-taker-imbalance-discovery`, PR #83
(OPEN/DRAFT/UNMERGED). Normal descendant commit of
`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1` (not amended). Audited that
commit's real-data run attempt (blocked earlier by a missing dataset, no
outcomes computed) and this repair are entirely separate: this round
performs **no** real-data access whatsoever.

**H05_REPAIR_CANDIDATE_SHA:** the commit that adds this entry.
**`H05_PREREG_SHA` and `H05_RESEARCH_CODE_FREEZE_SHA` remain UNSET** —
both require a further independent pre-outcome re-audit before being set,
per this round's own explicit instruction.

An independent pre-outcome audit re-verified **B-01** (the structural
-support finding closed in the prior round) as genuinely `CLOSED` (all 7
required criteria confirmed, plus a fresh independent adversarial
construction), and found five further findings against
`70797aaeed70fa3d4c584d96ca929f5a8e7e92d1`, all now `REPAIRED`:

- **M-01** (`+6h` same-support drift): `shifted_mean` was computed only
  over candidates with a valid `+6h` comparator, but differenced against
  the FULL candidate mean — the identical support-mismatch defect B-01
  closed, just for the negative control. Fixed: `shift_delta =
  candidate_shift_support_mean - shifted_mean`, both sides restricted to
  the same valid-comparator subset.
- **M-02** (undeclared `-1` structural strata): `price_alignment`/
  `price_strength_bin`/`activity_bin` rows with an unavailable underlying
  value (`-1`) were not excluded from candidate/control eligibility,
  risking an undeclared analytical stratum level. Fixed: `eligible_index`
  now excludes `-1` on all three dimensions for both sides.
- **M-03** (incomplete trailing-30d history): the shared
  `rolling_midrank_percentile` helper (used by `ABS_IMBALANCE_PCTL_W`,
  price-strength, and activity alike) returned a percentile from an
  unintended EXPANDING window for the first `window-1` rows instead of
  requiring the full trailing 30-day history. Fixed once, at the shared
  root cause: a percentile is now withheld until a full `window` of PRIOR
  bars has elapsed.
- **M-04** (no machine-enforced promotion decision): implemented
  `evaluate_promotion(cells)`, a deterministic, fail-closed evaluator over
  exactly the already-frozen candidate-for-freeze criteria (no new
  criterion), wired into `evaluate_h05`'s output as `results["promotion"]`.
  Deliberately does not auto-distinguish `REJECTED_SPECIFIC_CLAIM` from
  `INCONCLUSIVE` (documented scope boundary, not a gap).
- **M-05** (dataset identity optional): `load_development_1m` only
  validated the snapshot manifest IF one happened to exist. Fixed: the
  manifest's existence is now mandatory; its absence raises `H05Error`
  before any parquet is read.
- **M-09** (numpy/pandas pinning): `ALREADY_CLOSED` — `requirements.txt`
  already pins `numpy==2.1.3`/`pandas==2.2.3`, matching the validated H05
  test environment (`numpy 2.1.3`, `pandas 2.2.3`, `pyarrow 17.0.0`,
  Python 3.11.15). No dependency file changed.

95 tests total (73 pre-existing + 22 new), all passing on synthetic
fixtures only. `python -m compileall` and `git diff --check` clean. No
`W`/`q`/`H` change, no sign-multiplicity change, no new threshold/control/
search dimension, no general refactoring. Full detail:
`docs/reviews/H05_PREREG_IMPLEMENTATION_AUDIT.md` section 28.

Real H05 outcomes computed: **NO**. Real accepted parquet opened: **NO**.
2025: **UNTOUCHED**. 2026: **UNTOUCHED**. Batch01 synthesis: **NOT
STARTED**.

Do not run `--stage dev-run` against real data yet. Do not open 2025 or
2026 for H05. Do not start Batch01 synthesis yet. Do not start H06. Do
not treat this repair candidate as independently audited or
outcome-ready.

---

## 2026-08-27 — H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN development

**Hypothesis:** `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN`

- frozen design SHA: `deaf6503896920685f25a03230174d360a07ab9a`
- `H05_PREREG_SHA`: `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`
- `H05_RESEARCH_CODE_FREEZE_SHA`: `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`
- research-code SHA in runner JSON: `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`
- Git HEAD at outcome run: `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`
- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- development outcome access: **CONSUMED** (one `--stage dev-run`, 2020-02-01 → 2025-01-01)
- 2025 validation: **UNTOUCHED**
- 2026 final OOS: **UNTOUCHED**
- search surface: **45 primary cells** (3 W × 3 nested q × 5 H); both signs evaluated; Batch01 cumulative 225
- outcome status: `EXPLORATORY`
- machine `results["promotion"]`: continuation `promoted=false`, reversal `promoted=false`, verdict **`H05_REJECTED_SPECIFIC_CLAIM`**
- formal first-run status: **`C. H05_DEVELOPMENT_NOT_PROMOTED`**

H01/H02/H03/H04 remain rejected/killed. Do not reinterpret them. Their post-hoc observations were not used as H05 gates. No preferred sign was selected.

Universal blockers: MPIE 0/45 and overlap-structural 0/45 on both signs; full per-cell conjunction 0/45; therefore q-adjacent and H-adjacent full-gate support 0/45. Continuation primary 9/45, SELL oriented-primary 0/45, bootstrap 0/45. Reversal primary 36/45 but MPIE/structural never clear 0.10/0.05. No 2025/2026 month keys in results. No H05 source change after outcomes.

Post-hoc observations (all `POSTHOC_UNTESTED`, none may rescue H05):

- largest |candidate_mean| cells are negative (short-H / high-q)
- continuation-leaning cells concentrate at H=240 and fail BUY/SELL symmetry
- SELL-side means negative in all 45 cells; BUY-side means positive in 37/45
- structural unmatched share ≤ 0.00082 (not an overlap artifact)

Preregistration: `docs/research/H05_TAKER_IMBALANCE_PREREG.md`
Development evidence: `docs/research/H05_DEV_SUMMARY.md`, `docs/research/H05_DEV_RESULTS.json`, `docs/research/H05_RUN_PROVENANCE.json`, `docs/research/H05_DEV_SUMMARY.runner.md`
Record: `docs/reviews/H05_DEVELOPMENT_RESULT_RECORD.md`

Do not open 2025 or 2026 for H05. Do not retune q/W/H. Do not start Batch01 synthesis. Do not start H06.

---

## 2026-08-27 — H05 post-run review and closure

**Status:** `H05_POSTRUN_REVIEW_STATUS = CLOSED_DEVELOPMENT_REJECTED`

This entry is a chronological review/closure of the H05 development-run
entry immediately above; it does not overwrite, edit, or reinterpret that
entry. It independently re-verified the recorded evidence from commit
`fcec589fc1631dfaf7220d7fad53625eba7ecdaf` (parent
`faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`, the frozen H05 analytical
identity) without recomputing any market outcome:

- `docs/research/H05_DEV_RESULTS.json` SHA256:
  `37794ba525212681d0687cf4d35f9c5bf775ff63171c9efdb1b25a3acd947011`
  (recomputed locally from the recorded file, matches).
- 45 unique `(W, q, H)` cells present, matching the frozen 45-cell search
  surface exactly.
- `results["promotion"]`: `continuation.promoted = false`,
  `reversal.promoted = false`, both `promoted_cells` empty, `verdict =
  "H05_REJECTED_SPECIFIC_CLAIM"` — independently recomputed from the
  per-cell `claim_evaluation` gates (fail-closed conjunction over
  primary/MPIE/structural/shift/bootstrap-1w-2w-4w/year-stability/
  direction-symmetry) and matches the recorded verdict exactly.
- MPIE pass count: continuation `0/45`, reversal `0/45`.
- Structural pass count: continuation `0/45`, reversal `0/45`.
- Full per-cell gate conjunction: continuation `0/45`, reversal `0/45`.
- Primary-gate-only count (diagnostic, not a promotion criterion on its
  own): continuation `9/45`, reversal `36/45`.
- `forbidden_windows_inspected`: `{"2025": false, "2026": false}`;
  `windows.validation_untouched`/`windows.oos_untouched`: both `true`.

**Canonical post-run status:**

```
H05_POSTRUN_REVIEW_STATUS = CLOSED_DEVELOPMENT_REJECTED
H05_MACHINE_VERDICT = H05_REJECTED_SPECIFIC_CLAIM
H05_DEVELOPMENT_ACCESS = CONSUMED
H05_2025_VALIDATION = UNTOUCHED
H05_2026_OOS = UNTOUCHED
H05_ANALYTICAL_CODE_POST_OUTCOME_CHANGE = NO
```

**Decisive evidence (restated from the run entry, not altered):** MPIE
`0/45` continuation and `0/45` reversal; structural `0/45` continuation
and `0/45` reversal; full per-cell conjunction `0/45` on both
orientations; neither orientation promoted. This is not an inconclusive
result — the preregistered H05 claim, under both preregistered
orientations, did not promote.

**Explicit closure rules (frozen, no exceptions):**

- H05 must **not** be retuned (no new `q`/`W`/`H`, no alternate seeds, no
  alternate controls).
- H05 must **not** be rerun with alternate settings.
- H05 must **not** select reversal post hoc because continuation failed
  first, or vice versa — both orientations were evaluated together and
  both failed to promote.
- 2025 must **not** be opened to "rescue" this rejected development
  result.
- `H05b` (a child hypothesis built from H05's post-hoc observations) is
  **not authorized**.

**Post-hoc observations remain `POSTHOC_UNTESTED` only** — restated from
the run entry, not upgraded to a finding: BUY/SELL directional asymmetry
(SELL-side means negative in all 45 cells; BUY-side positive in 37/45);
reversal-leaning short/medium-`H` raw primary behavior (reversal primary
`36/45` vs. continuation `9/45`); continuation-leaning `H=240` pattern.
None of these are proven edge, an accepted hypothesis, or grounds to
rescue H05.

**Roadmap status after this closure:**

```
H01 = REJECTED / KILLED
H02 = REJECTED / KILLED
H03 = REJECTED_SPECIFIC_CLAIM
H04 = REJECTED_SPECIFIC_CLAIM
H05 = REJECTED_SPECIFIC_CLAIM / CLOSED_DEVELOPMENT_REJECTED
BATCH01_SYNTHESIS = NEXT_AUTHORIZED_RESEARCH_STAGE
BATCH01_SYNTHESIS_STARTED = NO
H06 = NOT_AUTHORIZED
```

H05 is confirmed as the fifth and final primary mechanism family of the
currently defined Batch01. No H06 is authorized as an automatic
continuation of this sequence. Batch01 synthesis is now the next
authorized research stage; it is **not** performed in this entry or by
this commit.

Post-run evidence and this closure are preserved on a separate reference
branch, `research/h05-postrun-record`, based on
`faac097 -> fcec589 -> <this closure commit>`. `research/h05-taker
-imbalance-discovery` (PR #83, the pre-outcome implementation freeze)
remains at `faac097c7a3aab0e82c35f4fdc7b0b006ac9e4a1`, unmoved.

---

## 2026-08-28 — R2 Batch01 synthesis and E1/VPS closeout

**Decision:** `BATCH01_CLOSED / 0_OF_5_PROMOTED`

The five Batch01 primary mechanism families are now closed on development:

- H01 = `REJECTED / H01_KILL`
- H02 = `REJECTED / H02_KILL`
- H03 = `H03_REJECTED_SPECIFIC_CLAIM`
- H04 = `H04_REJECTED_SPECIFIC_CLAIM`
- H05 = `H05_REJECTED_SPECIFIC_CLAIM / CLOSED_DEVELOPMENT_REJECTED`

No family promoted. H01-H05 2025 validation remains **UNTOUCHED** and 2026 OOS
remains **UNTOUCHED**. These windows are not to be opened to rescue a rejected
Batch01 claim.

Cross-hypothesis conclusion: several families contained raw conditional
structure, but none earned promotion under the required robustness and
incremental-information controls. Raw predictiveness is therefore not treated
as sufficient evidence of unique edge.

The prior VPS/E1 Stage-5 detector formulations are also closed for current
execution:

```
E1_TREND_PULLBACK = RETIRED_CURRENT_FORMULATION
E1_COMPRESSION_BREAKOUT = RETIRED_CURRENT_FORMULATION
E1_CONFIRMED_BREAKOUT = RETIRED_CURRENT_FORMULATION
E1_HOLDOUT = UNOPENED_AND_NOT_SPENT
```

This is **not** a claim that Batch01 reran the exact E1 detector code. The
retirement decision combines the already-consumed E1 development evidence with
the multi-year Batch01 mechanism results and concludes that there is no
research justification to spend the frozen E1 holdout on rescue. A future
materially different trend/compression/breakout hypothesis would require a new
identity and clean protocol.

Post-hoc patterns from H01/H04/H05 and any E1 simplification remain
`POSTHOC_UNTESTED` only.

Canonical next state:

```
BATCH01 = CLOSED
BATCH01_PROMOTED = 0/5
BATCH02 = NOT_STARTED
H06 = NOT_AUTHORIZED
NEXT_ENGINEERING_STAGE = V2_RESEARCH_HARNESS_V1
NEXT_RESEARCH_DESIGN_STAGE = BATCH02_DESIGN
```

Synthesis record: `docs/research/BATCH01_SYNTHESIS.md`.

---

## Next research program — hypothesis discovery after E1

Status: `AUTHORIZED_FOR_DISCOVERY / NOT YET CONFIRMATORY`.

`CORE_BTC_BINANCE_V0` is `ACCEPTED_FOR_DISCOVERY` (snapshot `717d37a4`).

Recorded discovery runs:

- `H01_COMPRESSION_EXPANSION` = `REJECTED / H01_KILL`
- `H02_FAILED_BREAKOUT_MEAN_REVERSION` = `H02_KILL`
- `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION` = `H03_REJECTED_SPECIFIC_CLAIM`
- `H04_TREND_PULLBACK_CONTINUATION` = `H04_REJECTED_SPECIFIC_CLAIM`
- `H05_TAKER_IMBALANCE_SUBSEQUENT_RETURN` = `H05_REJECTED_SPECIFIC_CLAIM`

Remaining mechanism classes still untested:

- price/OI divergence;
- crowded positioning -> reversal risk.

H05 (`Taker Imbalance -> Subsequent Return Distribution`) is the fifth
and final primary mechanism family of R2 Batch 01. Its one authorized
development run is recorded above (`C. H05_DEVELOPMENT_NOT_PROMOTED` /
`H05_REJECTED_SPECIFIC_CLAIM`), and has been reviewed and formally
**CLOSED** (`H05_POSTRUN_REVIEW_STATUS = CLOSED_DEVELOPMENT_REJECTED`,
see the post-run review entry above). No H06 is authorized after H05
closes. Batch01 synthesis is now **complete** (`BATCH01 = CLOSED`, `0/5` primary
families promoted). The next engineering stage is `V2_RESEARCH_HARNESS_V1`,
followed by `BATCH02_DESIGN`. `H06 = NOT_AUTHORIZED`.

These are not edge claims and not implementation authorization.

A new run receives its own ID, dataset split, variant/search accounting and frozen confirmatory protocol under `EDGE_RESEARCH_PROTOCOL.md`.

---

## 2026-09-02 — B2-02_BOUNDARY_INTERACTION_PATH development

**Formulation:** `B2-02_BOUNDARY_INTERACTION_PATH`

This entry records the one authorized B2-02 development outcome. It does not
rerun B2-02. Prior Batch02 state: `B2-01_VOLATILITY_TRANSITION` remains
`CLOSED_NO_PROMOTION` as already recorded in
`docs/research/B2_01_VOLATILITY_TRANSITION_RESULT.md`.

- execution / merge SHA: `a976a3fa3143f7290851ab8b2ddc5a9d811c891a`
- reviewed implementation SHA: `37051de39f49b5b331a0ddbc3b37f8316811f9ef`
- git tree: `f220590be0a6323df29b8e35b47399d42c3ea137`
- prereg merge SHA: `cbf447276c1dc47c9a755038cfd6013199207eef`
- prereg JSON SHA256: `3dd11009cd738ab02ab3a3a0a552de9a25a6c4db765d6510f63937c922a6d7b1`
- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- development outcome access: **CONSUMED** (one
  `scripts.research.b2_02_boundary_interaction_path.run_development` call with
  `outcome_access_acknowledged=True`; window 2020-02-01T00:00:00Z inclusive →
  2025-01-01T00:00:00Z exclusive; years 2020-2024 only)
- result artifact SHA256:
  `971b645a0eb8b45293f7c2f589c9666a037fe602a6f228751162b13bf0054646`
- 2025 validation: **UNTOUCHED**
- 2026 OOS: **UNTOUCHED**
- search surface: **12 primary cells** (3 L × 4 H; P=30m frozen)
- qualifying breaches: 107061
- outcome status: `EXPLORATORY`
- development verdict: **`B2_02_CLOSED_NO_PROMOTION`**

All eight frozen promotion gates failed. All 12 cells have negative mean AE
improvement and negative `PATH_SEPARATION`. No cell passed all five per-cell
gates. The isolated `L=60 H=30` placebo pass remains a worse-than-baseline
forecast and cannot rescue the formulation.

B2-01 remains `CLOSED_NO_PROMOTION`. Do not reinterpret either result. Do not
open 2025 or 2026. Do not rerun B2-02. Do not add a current-V2 B2-02 child.

Preregistration: `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_PREREG.md`
Development closeout: `docs/research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md`
Status ledger: `docs/research/BATCH02_STATUS_LEDGER.md`

Canonical next frozen unit: `B2-03_IMPULSE_MORPHOLOGY`. This entry does not
preregister, implement, or authorize B2-03 outcome access.

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