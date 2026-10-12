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

---

## 2026-09-02 — Batch02 durable evidence retention V1 (outcome-blind)

**Decision:** implement `BATCH02_DURABLE_EVIDENCE_RETENTION_V1` as infrastructure
only, pending independent review.

This entry consumes **no** market window and opens **no** Batch02 outcomes.

- B2-01 rerun = NO
- B2-02 rerun = NO
- B2-03 run = NO
- real `CORE_BTC_BINANCE_V0` market partitions = not accessed by this unit
- 2025 validation = UNTOUCHED
- 2026 OOS = UNTOUCHED

B2-02 remains `POST_RUN_EVIDENCE_RETENTION_GAP`. The new contract is
forward-only for B2-03+. See
`docs/research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md`.

---

## 2026-09-03 — B2-03_IMPULSE_MORPHOLOGY development

**Formulation:** `B2-03_IMPULSE_MORPHOLOGY`

This entry records the one authorized B2-03 development outcome. It does not
rerun B2-03.

- hypothesis: `B2-03_IMPULSE_MORPHOLOGY`
- development verdict: **`B2_03_CLOSED_NO_PROMOTION`**
- execution SHA: `8a7490167e086a201ec7b3780878d2cf3252ecfd`
- execution tree: `b83f4f5dfa82da6d9ab219829bbcccd214d2f11a`
- prereg merge SHA: `61bc9cfde80c6a142ac147ebee6487a1ae710324`
- dataset snapshot: `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`
- evidence ref: `refs/heads/research-evidence/batch02/B2-03/8a7490167e086a201ec7b3780878d2cf3252ecfd`
- RESERVED: `5dec8d075e5e35db3946fef4e0b530fd719cc7d3`
- OUTCOME_ACCESS_CLAIMED: `7a7adf1e4236286d8c69bb67efd51271ffc5473e`
- ARCHIVED: `16854498afc34c69f62e46a387ef08e7896a5172`
- result artifact SHA256:
  `a3586344ac9c094eb38670a16b7566b8c1628300b6a1f6605fd69c369894b0c0`
- artifact size: 68487026 bytes
- scientific development executions: **1**
- first invocation: `PRE_CLAIM_OPERATIONAL_ABORT` (isolated Git HTTPS auth;
  no reservation, no claim, no CORE access; not `RUN_INTEGRITY_FAILURE`)
- 2025 validation: **UNTOUCHED**
- 2026 OOS: **UNTOUCHED**
- constructed events: 131469
- search surface: **15 primary cells**
- qualifying neighborhoods: none
- all eight frozen promotion gates failed
- rerun authorized: **NO**

B2-01 and B2-02 remain `CLOSED_NO_PROMOTION`. F1 remains `ACTIVE` because
B2-04 is still untested. Do not reinterpret the result as market direction.
Do not open 2025 or 2026. Do not retune current-V2 morphology. Do not add a
current-V2 B2-03 child.

Preregistration: `docs/research/B2_03_IMPULSE_MORPHOLOGY_PREREG.md`
Development closeout: `docs/research/B2_03_IMPULSE_MORPHOLOGY_RESULT.md`
Status ledger: `docs/research/BATCH02_STATUS_LEDGER.md`

Next planned formulation: B2-04. This B2-03 closeout entry does not
preregister, implement, or authorize B2-04 outcome access.

---

## 2026-09-04 — B2-04_MODERATE_PULLBACK_STRUCTURE preregistration freeze

**Decision:** freeze the outcome-blind B2-04 preregistration design unit.

This entry consumes **no** market window and opens **no** Batch02 outcomes.

- hypothesis: `B2-04_MODERATE_PULLBACK_STRUCTURE`
- primary family: F1
- provenance: explicit `POSTHOC_UNTESTED` child of `H04_REJECTED_SPECIFIC_CLAIM`
- moderate residual is **not** positive evidence
- structural property: exactly one, `INTRA_PULLBACK_RECOVERY` /
  `RECOVERY_FRACTION`
- implementation: **NO** (`scripts/research/b2_04_*.py` forbidden in this unit)
- durable reservation: **NO**
- outcome access claimed: **NO**
- B2-04 run: **NO**
- real `CORE_BTC_BINANCE_V0` market partitions: not accessed by this unit
- 2025 validation: **UNTOUCHED**
- 2026 OOS: **UNTOUCHED**
- inventory file: **UNCHANGED**
- formulation status remains `PLANNED`

Preregistration: `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md`
Machine-readable twin: `docs/research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.json`
Status ledger: `docs/research/BATCH02_STATUS_LEDGER.md`

This entry does not implement B2-04 or authorize B2-04 development outcomes.

Independent review of the first freeze SHA required a same-PR repair:
strict last-legal `T` chronology, continuous `FINAL_DEPTH` OLS depth
isolation replacing `DEPTH_HALF`, construction/scoring lifecycle
separation, and a corrected mixed H04 provenance statement. Still no
CORE access, reservation, claim, or runner.

---

## 2026-09-07 — B2-05 durable-evidence recovery closed

**Decision:** `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED`

This entry records the one authorized production recovery of the already
consumed B2-05 local artifact. It does not rerun B2-05, does not reopen
CORE / 2025 / 2026, and does not convert operator adjudication into
historical cryptographic proof of the original persisted bytes.

- hypothesis: `B2-05_FLOW_ABSORPTION`
- recovery status: **`ARCHIVED`**
- evidence ref: `refs/heads/research-evidence/batch02/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978`
- archive SHA: `e31e5666fe845116197b6f2531289bf17d848027`
- archive parent / claim SHA: `e6590062b3dba06b716199552b74f9c68b14f4b2`
- reservation SHA: `40cd095122b32d0f5fdb731fa429901d546777e3`
- artifact SHA256: `530342759e70a135915ef82382b4b97bd939620ce02925524b745ccf6cc9a57c`
- artifact size: `280017092`
- chunk count: **5** (`raw_chunks`)
- recovery code SHA: `3f1b42a667fe982bf399921d1c200b2b56885a28`
- recovery code tree: `b97a31f9688c2d76176264e420de50511ea1ca6a`
- historical execution SHA: `669ae93c6a5c1d102a46fd129f04292f1beff978`
- historical execution tree: `7a5c31aef771e4bbdeb686045ae154d33e7c8fd4`
- `historical_artifact_binding` = `OPERATOR_ADJUDICATED`
- `historical_execution_persistence_proven` = **false**
- `recovery_proves` = `artifact_equals_authority_committed_during_recovery`
- production recovery invocation count = **1**
- B2-05 rerun = **NO**
- CORE reopened = **NO**
- force push = **NO**
- automatic retry = **NO**
- local artifact unchanged after recovery = **YES**
- evidence ref now points at the exact archive commit = **YES**
- 2025 validation: **UNTOUCHED**
- 2026 OOS: **UNTOUCHED**
- rerun authorized: **NO**

Status ledger: `docs/research/BATCH02_STATUS_LEDGER.md`
Recovery authority: `docs/research/batch02_recovery_authority/B2-05/669ae93c6a5c1d102a46fd129f04292f1beff978.json`

---

## 2026-09-07 — B2-06 OI/funding data-expansion contract frozen

**Decision:** `DATA_EXPANSION_FEASIBLE_TO_FREEZE`
**Unit verdict:** `DATA_CONTRACT_FROZEN_AWAITING_MATERIALIZATION_AND_FUNDING_AVAILABILITY_AUTHORITY`

This entry records an outcome-blind first-party Binance USD-M `BTCUSDT`
open-interest + settled-funding identity freeze. It does **not** execute
B2-06, does not create a RESULT, does not inspect B2-06 predictive
outcomes, does not open 2025 validation or 2026 OOS, does not modify the
frozen inventory, and does not touch B2-05.

- dataset_id: `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0`
- status: `CONTRACT_FROZEN_NOT_MATERIALIZED`
- research_authorized: **false**
- outcome_access_authorized: **false**
- provider/venue: Binance / Binance
- market_type / contract / symbol: `USD_M_FUTURES` / `PERPETUAL` / `BTCUSDT`
- OI: Vision `daily/metrics` `sum_open_interest` (BTC, native 5m, `available_at = period_end`)
- funding: Vision `monthly/fundingRate` settled `last_funding_rate` (8h); `calc_time` is source event time; publication semantics `FUNDING_PUBLICATION_LATENCY_UNPROVEN`; `calc_time` is **not** `legal_available_at`
- joint development overlap: `[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`
- archive-object listing in that overlap: design-time observation only (60 funding months / 1583 OI days listed); not a materialized snapshot
- cross-provider / cross-venue / cross-timeframe fallback: **NO**
- scientific evaluator / crowding thresholds: **NO**
- CORE kline snapshot: not used as an OI/funding source
- formulation status remains: `BLOCKED_MISSING_OBSERVABLE` until a materialized Git-bound snapshot **and** a frozen first-party funding publication rule exist

Contract: `docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md`

---

## 2026-09-08 — B2-06 OI/funding materializer + funding publication authority

**Decision:** `FUNDING_PUBLICATION_LATENCY_UNPROVEN`
**Dataset status at this commit:** materializer implemented; historical snapshot not yet Git-bound (acquire is a later step against this code identity).

First-party Binance Vision README and USD-M `GET /fapi/v1/fundingRate` / premium-index docs were inspected for a public-availability clock for settled `last_funding_rate`. None proves that archive `calc_time` is `legal_available_at`. No latency was invented.

This entry does **not** execute B2-06, does not create a RESULT, does not inspect predictive outcomes, does not open 2025/2026, does not modify the frozen inventory, and does not touch B2-05.

- research_authorized: **false**
- outcome_access_authorized: **false**
- b2_06_evaluator_enabled: **false**
- funding publication: `FUNDING_PUBLICATION_LATENCY_UNPROVEN`
- OI availability rule: unchanged `period_end = create_time + 300000ms`

## 2026-09-08 — B2-06 OI/funding snapshot materialized, research unauthorized

**Decision:** `SNAPSHOT_MATERIALIZED_NOT_RESEARCH_AUTHORIZED`
**Unit verdict:** `SNAPSHOT_MATERIALIZED_FUNDING_PUBLICATION_UNPROVEN_RESEARCH_UNAUTHORIZED`

Git-bound Vision snapshot for `B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0` over
`[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)`:

- snapshot_id: `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`
- snapshot_manifest_sha256: `bb216f9abdb9fcd7c7648bbffb8541e811af06498d062faa5f31037793768e5e`
- materializer git commit/tree: `78d5bdf9d5686b740ebc48e46227bbf0f990cbbe` / `2b3e48ba36dd19f40a00fabe5c1a548b0b94d72f`
- OI objects expected/fetched/accepted/rejected: 1583 / 1583 / 1583 / 0
- funding objects expected/fetched/accepted/rejected: 52 / 52 / 52 / 0
- raw container bytes: 18564934
- normalized JSONL bytes: 256788119
- OI missing native 5m buckets: 631 (MISSING, not filled)
- funding missing settlements: 0

First-party funding publication remains `FUNDING_PUBLICATION_LATENCY_UNPROVEN`.
`calc_time` is not `legal_available_at`. Materialization does **not** execute
B2-06, create a RESULT, inspect predictive outcomes, open 2025/2026, modify
the frozen inventory, or touch B2-05.

- research_authorized: **false**
- outcome_access_authorized: **false**
- b2_06_evaluator_enabled: **false**
- b2_06_inputs_legally_consumable: **false**
- formulation status remains: `BLOCKED_MISSING_OBSERVABLE`

Evidence: `docs/research_data/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0/`
Authority note: `docs/research/B2_06_FUNDING_PUBLICATION_AUTHORITY.md`

## 2026-09-08 — B2-06 evidence hashes anchored; verify-only added

**Decision:** metadata/manifest rebuild only. Snapshot identity unchanged.
**Unit verdict:** unchanged `SNAPSHOT_MATERIALIZED_FUNDING_PUBLICATION_UNPROVEN_RESEARCH_UNAUTHORIZED`

The committed object ledger and quality report are now SHA256-anchored in
`docs/manifests/B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0.yaml`. Verify-only
reads current HEAD blobs and does not download. This does **not** rematerialize
bytes, change `snapshot_id`, authorize B2-06 science, invent funding
publication latency, open 2025/2026, modify the inventory, or touch B2-05.

- snapshot_id: `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33` (unchanged)
- object_ledger_sha256: `521d42a471cc5fec74d808e8a4a3ea0078c87342b801df5dbf3836b4b69b4296`
- quality_report_sha256: `a6b46df8350871bd737f02197b201b58d6069b19896d1767bda4c286bdc6c7b3`
- rematerialization: **no**
- research_authorized: **false**
- outcome_access_authorized: **false**
- b2_06_evaluator_enabled: **false**
- durability: raw ZIP and normalized JSONL remain gitignored; current snapshot proves historical identity at materialization time, not current local recoverability
- `.CHECKSUM` sidecars: transient corroborating evidence, not Git-retained

## 2026-09-08 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 fixture implementation

**Decision:** fixture-only implementation for independent review.
**Unit verdict:** execution remains unauthorized.

Implements the frozen synthetic calibration instrument with tiny deterministic
fixtures only. Does **not** run the 3200-world grid, create a RESULT, inspect
calibration outcomes, access real market data, open B2-06, open 2025/2026,
modify the frozen inventory, or touch B2-05.

- implementation_exists: **true**
- synthetic_execution_authorized: **false**
- production_calibration_executed: **false**
- b2_06_scientific_execution_authorized: **false**

## 2026-09-08 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 one-shot authorization

**Decision:** tracked one-shot production authorization for independent boundary review.
**Unit verdict:** unused; production calibration not executed.

Adds a Git-HEAD-blob authorization contract for exactly one frozen synthetic
calibration run. Does **not** run the 3200-world grid, create a RESULT,
consume the authorization, access real market data, open B2-06, or open
2025/2026.

- implementation_frozen_before_production_execution: **true**
- synthetic_execution_authorized: **true**
- authorized_run_count: **1**
- production_calibration_executed: **false**
- authorization_consumed: **false**
- b2_06_scientific_execution_authorized: **false**

## 2026-09-08 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 authorization-boundary repair

**Decision:** focused repair of OPUS authorization-boundary findings on the existing one-shot authorization.
**Unit verdict:** unused; production calibration not executed; not an authorization freeze.

Binds production execution to exact executed bytes, adds atomic one-shot
reservation, and stops proof objects from defining the production grid. Does
**not** run the 3200-world grid, create a RESULT, consume the live
authorization, access real market data, open B2-06, or open 2025/2026.

- synthetic_execution_authorized: **true**
- production_calibration_executed: **false**
- authorization_consumed: **false**
- b2_06_scientific_execution_authorized: **false**
- status: `ONE_SHOT_SYNTHETIC_EXECUTION_AUTHORIZATION_READY_FOR_FOCUSED_REDTEAM`

## 2026-09-08 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 authorization freeze

**Decision:** freeze the reviewed one-shot authorization implementation before production execution.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Records OPUS `GO_FOR_AUTHORIZATION_FREEZE` at reviewed HEAD
`7b308f6520fc8b71e9e51c8cf0013e0edc77874c` / tree
`842a5a8f1a7ea73d08e4d88e2ab58ca39bda42c8`. Does **not** run the 3200-world
grid, arm the Monte Carlo seam, create a RESULT, consume the live
authorization, access real market data, open B2-06, or open 2025/2026.

Residual findings preserved as hard preconditions before any arming:
cross-checkout durability (RESIDUAL-R1) and stale in-process import
(RESIDUAL-R2).

- synthetic_execution_authorized: **true**
- authorized_run_count: **1**
- production_calibration_executed: **false**
- authorization_consumed: **false**
- production_monte_carlo_arm_authorized: **false**
- b2_06_scientific_execution_authorized: **false**
- status: `AUTHORIZATION_FROZEN_BEFORE_PRODUCTION_EXECUTION`

## 2026-09-08 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 production durability

**Decision:** implement production durability, aggregation, and result
persistence above the frozen scientific primitives without executing the
3200-world calibration.
**Unit verdict:** unarmed; no RESULT minted; #114 local reservation superseded
on this HEAD.

Canonical production execution must cross a fresh Python interpreter and
re-verify exact HEAD/tree plus execution-authority bytes inside that process
(R1). Run identity is a function of tracked commit authority only, so local
reservation deletion or another clone/worktree cannot mint a distinct
authoritative identity (R2). Global process exclusion is not claimed.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- b2_06_scientific_execution_authorized: **false**
- status: `PRODUCTION_DURABILITY_IMPLEMENTED_UNARMED`

Repair of OPUS `REPAIR_REQUIRED` on reviewed HEAD `4aab2f0c`: invalid planned
worlds force `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`; public RESULT minting
cannot bind caller-supplied aggregates; isolated `python -I -B -P` bootstrap
imports the canonical package module; ARM authorizes the parent execution
commit rather than a self-referential HEAD/tree fixed point; IncompleteWorld is
recorded as an invalid world that stays in the planned denominator; persistence
is commit-mediated. Production remains unarmed. No Monte Carlo. No RESULT.

## 2026-09-09 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 production durability implementation freeze

**Decision:** freeze the reviewed production-durability implementation before any
production arming or 3200-world execution.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Records OPUS `GO_FOR_IMPLEMENTATION_FREEZE` (BLOCKERS=0, MAJORS=0, MINORS=0)
at reviewed implementation HEAD
`d5277c42141a26948b195afe3d4ad30030151855` / tree
`7ab4178f222ecf8a2b5c8bf7d7bec9279fa3cf89`. Exact reviewed-head GitHub CI run
`34319781573` SUCCESS. The freeze commit is a docs/ledger/metadata descendant
and is not itself the reviewed code HEAD.

Does **not** run the 3200-world grid, arm the Monte Carlo seam, create a RESULT,
open B2-06, or open 2025/2026. Frozen scientific lib and prereg bytes remain
byte-identical.

Non-blocking observation: `artifacts` exists in the pinned root allowlist but
is not currently a tracked top-level package and is not imported in the verified
execution chain. It was empirically inert during OPUS review and is unchanged
by this freeze. Any future unit which makes `artifacts` a real/imported root
package must explicitly re-review the pre-import allowlist authority boundary.

- implementation_frozen: **true**
- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- b2_06_scientific_execution_authorized: **false**
- validation_2025_authorized: **false**
- oos_2026_authorized: **false**
- status: `PRODUCTION_DURABILITY_IMPLEMENTATION_FROZEN_UNARMED`

## 2026-09-09 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 historical ARM #116 rejected

**Decision:** do not merge ARM HEAD `940d85bf58673396c6c0cc05ce2134a2e2e92809`.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Records OPUS `REPAIR_REQUIRED` on the parent-authorizing ARM unit. The ARM
mechanism is sound; sequencing is invalid because the ARM was created before
the canonical production driver existed. Status:
`REJECTED_NOT_MERGED / SUPERSEDED_BY_DRIVER_FIRST_SEQUENCE`. Git history is
preserved. The ARM artifact is not copied onto the driver-first branch.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `REJECTED_NOT_MERGED / SUPERSEDED_BY_DRIVER_FIRST_SEQUENCE`

## 2026-09-09 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 production execution driver

**Decision:** implement the canonical 3200-world production driver while remaining
unarmed, before any final ARM.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Starts from frozen #115 HEAD `502a62ddee0a3106967b21f0095be7e1629a56b2` /
tree `f21570983530f785d85639554741f3dd82164278`. Replaces the unconditional
armed refusal with `run_canonical_production_execution()`. Final RESULT minting
requires an unforgeable in-process canonical session capability; caller-supplied
records are never sufficient. #115 remains authoritative for reservation,
claim, result, and `run_identity`. Future ARM verification machine-checks
declared contract fields and reviewed-implementation binding. Identity
reporting reflects verified ARM state without granting authority.

Does **not** run the 3200-world grid, add a live ARM artifact, mint a RESULT,
open B2-06, or open 2025/2026. Frozen scientific lib and prereg bytes remain
byte-identical. The `artifacts` root package remains unactivated.

- canonical_production_driver_implemented: **true**
- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_EXECUTION_DRIVER_IMPLEMENTED_UNARMED`

## 2026-09-09 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 production driver OPUS repair

**Decision:** close OPUS `REPAIR_REQUIRED` on driver HEAD `d62e1f3` without arming.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Closes BLK-1 stdout RESULT/partial emission, BLK-2 mint/verify core derivation,
MAJ-1 strict-ancestor + tracked driver-freeze chain, MAJ-2 full-record digest
binding, and MIN-1 BaseException session retirement. No live freeze artifact. No
live ARM. No 3200-world execution. No RESULT persisted.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_EXECUTION_DRIVER_REPAIR_UNARMED`

## 2026-09-09 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 post-commit RESULT verification

**Decision:** close post-commit RESULT verification before freeze without arming.
**Unit verdict:** unused; production calibration not executed; Monte Carlo remains unarmed.

Adds historical RESULT verification from the artifact's embedded
`execution_head`, using git-object blobs and ARM topology at execution time.
Current HEAD need not be armed. Wires `#115` RESULT claim persistence from
tracked authority. Removes the duplicate `abandon_canonical_session` definition.
Post-RESULT rerun reports one-shot consumed rather than merely unarmed. No live
freeze artifact. No live ARM. No 3200-world execution. No RESULT persisted.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_EXECUTION_DRIVER_REPAIR_UNARMED`

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — full historical 3200-world recomputation

Closes the remaining terminal-author trust: a first-and-only fabricated
WORLD_RECORDS + RESULT pair could be authored together on a legitimate freeze
→ ARM → execution topology and pass because historical verification proved
identity plus internal WORLD_RECORDS/RESULT consistency, not that the records
were the deterministic output of frozen execution.

Authoritative historical verification now proves executing scientific and
production blobs match `execution_head`, independently recomputes all 3200
frozen-plan worlds, compares canonical WORLD_RECORDS evidence against that
recomputation, then recomputes aggregates and every derived RESULT field.
Tracked WORLD_RECORDS are retained evidence, not self-authenticating
authority. Spot-checks cannot mint or validate durable claims. Durable claims
are emitted only after full recomputation and explicitly bind RESULT and
WORLD_RECORDS digest/size.

No live freeze artifact. No live ARM. No 3200-world production execution. No
RESULT persisted. Frozen lib and prereg bytes unchanged.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_EXECUTION_DRIVER_REPAIR_UNARMED`

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — isolate authoritative historical recomputation

Closes the remaining stale-import / runtime-mutation class for historical
verification. Authoritative 3200-world recomputation previously ran in the
caller process: it compared on-disk bytes to `execution_head`, but an
in-process monkeypatch of `_evaluate_planned_world_body` (or already-imported
runtime objects) could still make a fabricated WORLD_RECORDS + RESULT pair
verify and mint a durable claim while repository bytes stayed unchanged.

Production `verify_bound_result_from_tracked_authority` now spawns
`HISTORICAL_RECOMPUTE_MODE` through the existing isolated-child bootstrap. The
child independently re-proves historical identity, loads git-object blobs,
proves executing bytes match `execution_head`, derives the frozen plan
internally, recomputes all 3200 worlds, compares tracked WORLD_RECORDS
evidence, and recomputes RESULT science. The parent treats only a bound
child success proof as the recomputation result. There is no in-process
fallback. Durable claims still require this verification first.

Full verification is intentionally expensive and synchronous; it may take
many hours. Spot-check remains diagnostic only and cannot mint or validate
durable production claims.

No live freeze artifact. No live ARM. No 3200-world production execution. No
RESULT persisted. Frozen lib and prereg bytes unchanged.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_EXECUTION_DRIVER_REPAIR_UNARMED`

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — production execution-driver implementation freeze

**Decision:** freeze the independently reviewed #117 production execution
driver without arming.
**Unit verdict:** unused; production calibration not executed; Monte Carlo
remains unarmed.

Records OPUS `GO_FOR_DRIVER_FREEZE` (BLOCKERS=0, MAJORS=0) against reviewed
implementation HEAD `3fadc391ee0002e35463b526301d287d4a662828` / tree
`5fb77727c418cc42bf3c1c6553355a0475f42efc`. The freeze is a docs-only
descendant. It does not claim that the freeze commit itself was the reviewed
code HEAD. Future ARM must bind this freeze parent and the exact reviewed
authority SHA256 values. No live ARM. No 3200-world production execution. No
RESULT or WORLD_RECORDS persisted. Frozen lib and prereg bytes unchanged.

Full authoritative historical verification remains intentionally expensive
and synchronous; the full end-to-end real production verification path has
not yet been run to completion. That operational caveat does not weaken full
recompute as the durable-claim authority model. Spot-check remains
non-authoritative.

- driver_implementation_frozen: **true**
- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_DRIVER_IMPLEMENTATION_FROZEN_UNARMED`

## 2026-09-10 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 final production Monte Carlo ARM

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — final production Monte Carlo ARM

**Decision:** authorize exactly one frozen synthetic production Monte Carlo
as the immediate child of DRIVER FREEZE `40e54b8c0497593aa3daf0bddc0e014bf048489f`.
**Unit verdict:** unused; production calibration not executed; ARM not consumed.

Docs/authority-artifact-only ARM. Binds the tracked freeze artifact at the
freeze parent, the reviewed implementation HEAD
`3fadc391ee0002e35463b526301d287d4a662828` / tree
`5fb77727c418cc42bf3c1c6553355a0475f42efc`, the freeze-recorded
execution-authority SHA256 values, and the exact frozen 3200-world plan.
Does not modify production/scientific/test implementation except live-HEAD
unarmed→armed state-transition tests. Does not execute the 3200-world
calibration. Does not persist WORLD_RECORDS or RESULT. Does not mint a
durable claim. Does not consume one-shot authority. Historical ARM
`940d85bf58673396c6c0cc05ce2134a2e2e92809` remains rejected and is not
this ARM. B2-06 / 2025 / 2026 / other hypotheses / real market data remain
unauthorized.

- driver_implementation_frozen: **true**
- production_monte_carlo_arm_authorized: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED`

## 2026-09-10 — HARNESS_PERFORMANCE_V1 performance-only repair

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — HARNESS_PERFORMANCE_V1

**Decision:** performance-only repair of the frozen synthetic production
path after the aborted canonical run. Same science, same randomness, same
logical results, faster execution. Not a scientific RESULT.

ARM `0abc5fe167e018ebe1f7efbb70694887ac095e17` remains unused and must not be
reused for the optimized implementation. No new production ARM. No 3200-world
grid execution. No RESULT / WORLD_RECORDS / reservation / claim. No B2-06 /
2025 / 2026 / real-market access.

Optimizations: placebo BASE expanding-era cache; lstsq rank in place of a
prior `matrix_rank` SVD where exact IncompleteWorld/float equality holds;
deterministic world-level spawn multiprocessing with canonical reorder;
BLAS thread limits; explicit `--workers N` (default 1).

Oracle is git commit `3fadc391ee0002e35463b526301d287d4a662828`, not a
self-import of the optimized module.

- production_monte_carlo_arm_authorized (live HEAD): **false**
- historical ARM unused: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_ONLY_UNARMED_NOT_A_RESULT`

## 2026-09-10 — HARNESS_PERFORMANCE_V1 authority/durability repair

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — HARNESS_PERFORMANCE_V1 repair

**Decision:** close independent-review findings BLOCKER-1 and MAJOR-1 on the
accepted performance implementation. No scientific-methodology change. No
3200-world production execution. No ARM consume/create. No RESULT /
WORLD_RECORDS.

- BLOCKER-1: live execution TCB now pins worker.py git bytes (path/sha256/size)
  plus lib/runner/auth/production. Old ARM `0abc5fe` still verifies at its
  own commit and does not authorize this HEAD.
- MAJOR-1: crash-safe durable partial world evidence with exact resume.
  Partial ≠ RESULT / WORLD_RECORDS / AUTHORITY_CONSUMED.

Next required step after BLOCKER-1/MAJOR-1 was OPUS review. A remaining
red-team finding (BLOCKER-2) is recorded and closed in the following entry.

- production_monte_carlo_arm_authorized (live HEAD): **false**
- historical ARM unused: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_ONLY_UNARMED_REPAIR_PENDING_OPUS_REVIEW`

## 2026-09-10 — HARNESS_PERFORMANCE_V1 BLOCKER-2 checkpoint authenticity

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — HARNESS_PERFORMANCE_V1 repair

**Decision:** close independent-review finding BLOCKER-2. Durable checkpoint
content remains structurally/digest-checked for resume, but is not scientific
authority. Authoritative production mint authenticates cached/computed world
records in an isolated child from exact frozen git execution bytes. No HMAC
or secret key. No scientific-methodology change. No 3200-world production
execution. No ARM consume/create. No RESULT / WORLD_RECORDS.

- BLOCKER-1 remains closed: worker.py remains in the live execution TCB.
- MAJOR-1 remains closed: crash-safe durable partial evidence and exact resume
  still avoid immediate recompute of completed worlds.
- BLOCKER-2: self-consistent forgery, whole-checkpoint fabrication, mixed
  legitimate+forged stores, and current-module self-attestation are refused
  before canonical mint.

Next required step: OPUS narrow review of BLOCKER-2 on the exact repaired HEAD,
then a new performance/execution freeze and a new immediate-child ARM.

- production_monte_carlo_arm_authorized (live HEAD): **false**
- historical ARM unused: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_ONLY_UNARMED_REPAIR_PENDING_OPUS_REVIEW`

## 2026-09-10 — HARNESS_PERFORMANCE_V1 verifier parallelism + observed_world_count

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — HARNESS_PERFORMANCE_V1 repair

**Decision:** close remaining independent-review MAJOR (sequential isolated
recomputation) and MINOR (`observed_world_count` unvalidated). Isolated
mint-time authentication and claim-time historical recomputation now reuse
the reviewed world-parallel spawn path. Worker count is operational, not
scientific. Parent authentication proofs must equal `observed_world_count`
to submitted and planned counts. No 3200-world production execution. No ARM
consume/create. No RESULT / WORLD_RECORDS.

- BLOCKER-1 remains closed: worker.py remains git-object pinned in the live
  execution TCB (path/sha256/size). Spawn copies parent `sys.path` into
  children before Pool initializer; the parent therefore inserts the frozen
  worker repository root first so children cannot import a live checkout.
- MAJOR-1 remains closed: durable partial evidence and exact resume unchanged.
- BLOCKER-2 remains closed: checkpoint content is still untrusted; forgery
  still fails closed before mint.
- Parent authenticators refuse `observed_world_count` mismatches (count-1,
  count+1, zero, huge, string, bool, correct digests with wrong count).
- n=5000 verifier engine **MEASURED** on this 4-CPU host: 5.6371 / 3.0444 /
  1.5149 s/world at workers=1/2/4 (93% of 4-wide). AUTH and historical
  isolated children share that engine. 8/16-worker lifecycle figures are
  extrapolated; this host cannot beat the 4-worker wall clock.

Next required step: FINAL_OPUS_REVIEW_THEN_PERFORMANCE_FREEZE.

Targeted verifier-parallel tests: 18 passed. Harness unit files: 271
passed. Research suite: 1586 passed (271 harness + 1315 other). Non-research
suite: 5977 passed, 185 skipped. compileall + git diff --check: ok. Canonical
3200-world production was not executed.

- production_monte_carlo_arm_authorized (live HEAD): **false**
- historical ARM unused: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_ONLY_UNARMED_REPAIR_PENDING_OPUS_REVIEW`

## 2026-09-11 — HARNESS_PERFORMANCE_V1 performance/execution freeze

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — PERFORMANCE_EXECUTION_FREEZE

**Decision:** docs/metadata-only freeze of independently reviewed performance
implementation HEAD `9c573df81dad55829f52cff0f94e8c5918c30fd9` / tree
`b9d928687e5ea4e9773f07b0cb6f8e287b65562f`. OPUS `GO_FOR_PERFORMANCE_FREEZE`.
BLOCKERS=0 MAJORS=0 MINORS=0. BLOCKER-1, MAJOR-1, BLOCKER-2 remain CLOSED.

Canonical freeze artifact:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json`.

This freeze does not change execution-TCB bytes, prereg, or scientific plan.
It does not arm production, consume authority, execute the 3200-world grid,
or mint RESULT/WORLD_RECORDS. Old ARM `0abc5fe` does not authorize this
implementation. Next required step: CREATE_NEW_IMMEDIATE_CHILD_ARM.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_EXECUTION_FROZEN_UNARMED`

## 2026-09-11 — HARNESS_PERFORMANCE_V1 production ARM

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — PRODUCTION_MONTE_CARLO_ARM

**Decision:** docs/authority-artifact ARM immediate child of performance
execution freeze `ccaffe135c2b8a9a0a75af30c0712ba3063b82f6`. Authorizes one
synthetic 3200-world production execution against reviewed implementation
`9c573df81dad55829f52cff0f94e8c5918c30fd9`. Worker count is operational.
Does not execute production, consume authority, or mint RESULT/WORLD_RECORDS.
Old ARM `0abc5fe` does not authorize this implementation or freeze.

Canonical ARM:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`.

- production_monte_carlo_arm_authorized (ARM artifact): **true**
- frozen `production.py` verifier still keys `PRODUCTION_DRIVER_FREEZE.json`, so live `production_monte_carlo_arm_authorized()` remains **false** until a later TCB-safe verifier bind
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED`
- next required step: `EXECUTE_CANONICAL_PRODUCTION_FROM_EXACT_ARM_COMMIT` (exact ARM commit object only; spawn currently refuses until verifier bind)

## 2026-09-11 — performance-freeze ARM authorization wiring repair

**Decision:** runtime ARM/freeze authority wiring in
`harness_synthetic_edge_calibration_v1_production.py` now verifies the
canonical performance/execution freeze path. Scientific library, plan, RNG,
and numerical path are unchanged. No production execution. No new freeze or
ARM. ARM `120ac45` remains evidence of the previous mismatch and does not
authorize this repaired HEAD. Old ARM `0abc5fe` remains refused.

- production_monte_carlo_arm_authorized (live repaired HEAD): **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- next required step: `NARROW_AUTHORIZATION_WIRING_REVIEW_THEN_NEW_FREEZE_AND_ARM`

## 2026-09-11 — HARNESS_PERFORMANCE_V1 final runtime freeze

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — FINAL_RUNTIME_FREEZE

**Decision:** docs/metadata-only freeze of independently reviewed repaired
runtime HEAD `f47c5394d8cc0c3f6312cd4156f389ba7ee81dbd` / tree
`84b23e4c51a4f7ccf59bb36d5333ef7974ea7eab`. OPUS `GO_FOR_FINAL_RUNTIME_FREEZE`.
BLOCKERS=0 MAJORS=0 MINORS=0. BLOCKER-1, MAJOR-1, BLOCKER-2 remain CLOSED.

Canonical freeze artifact:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PERFORMANCE_EXECUTION_FREEZE.json`.

This freeze does not change execution-TCB bytes, prereg, or scientific plan.
It does not arm production, consume authority, execute the 3200-world grid,
or mint RESULT/WORLD_RECORDS. Unused driver ARM `0abc5fe` and historical
performance ARM `120ac45` do not authorize this implementation. Next required
step: CREATE_NEW_IMMEDIATE_CHILD_ARM.

- production_monte_carlo_arm_authorized: **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PERFORMANCE_EXECUTION_FROZEN_UNARMED`

## 2026-09-11 — HARNESS_PERFORMANCE_V1 final production ARM

### HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 — PRODUCTION_MONTE_CARLO_ARM

**Decision:** docs/authority-artifact ARM immediate child of final runtime
freeze `1499bc5f5e731f226650abd5051447fc846f722b`. Authorizes one synthetic
3200-world production execution against reviewed implementation
`f47c5394d8cc0c3f6312cd4156f389ba7ee81dbd`. Worker count is operational.
Does not execute production, consume authority, or mint RESULT/WORLD_RECORDS.
Unused driver ARM `0abc5fe` and historical performance ARM `120ac45` do not
authorize this implementation or freeze.

Canonical ARM:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1_PRODUCTION_ARM.json`.

- production_monte_carlo_arm_authorized (ARM artifact): **true**
- live `production_monte_carlo_arm_authorized()` at the exact ARM commit: **true**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_persisted: **false**
- authorization_consumed: **false**
- status: `PRODUCTION_MONTE_CARLO_ARM_AUTHORIZED_UNEXECUTED`
- next required step: `EXECUTE_CANONICAL_3200_WORLD_RUN_FROM_EXACT_FINAL_ARM_COMMIT_WITH_4_WORKERS`

## 2026-09-11 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1 canonical 3200-world attempt

**Decision:** V1 production grid was executed from exact ARM commit
`9ab32fc14c50df0c6f1c7ddfe2a8990d2d49c339` / tree
`8aca4445f4638f678810d64a17de2a253a22763d` with `workers=4`.

- planned / structural complete: 3200 / 3200
- V1-rule valid / invalid: 3087 / 113
- run_identity: `ac1087b75250a671f4a207defec6d2b606050cd8c2fbcfcd894b6b2876be2565`
- RESULT minted: **false**
- WORLD_RECORDS created: **false**
- authority consumed: **false**
- mechanical status (permanent): `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- V1 subset claimable: **false**
- cause class (forensic, not a RESULT): `EXPECTED_DGP_DEGENERACY`

Do not mint a V1 RESULT. Do not salvage the 3087-world subset. Do not
resume V1 production as V2. This ledger entry is not market evidence.

## 2026-09-11 — HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2 rank-degeneracy policy prereg

**Decision:** freeze methodology-only unit
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`
before implementation.

Canonical:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG.md`
and `.json`.

Candidate-level rank failure does not invalidate a world unless the
baseline is not identifiable. Detection uses identifiable denominators.
Coverage gates are frozen prospectively. DGP/RNG/seeds/candidates/OLS
full-rank rule are unchanged. No V2 runtime, freeze, or ARM in this unit.

- implementation_exists: **false**
- synthetic_execution_authorized: **false**
- v2_production_arm_authorized: **false**
- ready_for_v2_implementation_review: **false**
- next required step: `INDEPENDENT_ADVERSARIAL_REVIEW_OF_V2_RANK_DEGENERACY_POLICY_PREREG`

## 2026-09-11 — V2 rank-degeneracy policy amendment 001

**Decision:** docs-only prospective amendment of
`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY`
to close independent-review MAJOR-1 and MINOR-1..4. The original prereg at
`ada237edc330b44bc412332e263f124757919e93` is not rewritten in place.

Canonical:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PREREG_AMENDMENT_001.md`
and `.json`.

- L persisted per WORLD_VALID world; full L=0..10 distribution per cell
- BLIND taxonomy stratified by L; L=0 not credited as NO_DISCOVERY
- closed non-identifiability reason taxonomy + first failing era
- explicit required-coverage map for every inherited conclusion
- F01 moved to F03-like coverage tier on SMALL|2500 (0.65→0.75) and
  TINY_NOISY|5000 (0.60→0.70); no other threshold changes
- selective cell re-execution after a V2 attempt forbidden
- implementation_exists: **false**
- next required step: `INDEPENDENT_REREVIEW_OF_V2_RANK_POLICY_AMENDMENT`

## 2026-09-11 — V2 rank-degeneracy fixture implementation

**Decision:** implement frozen V2 rank-degeneracy semantics as a
fixture-only module. No production grid, RESULT, WORLD_RECORDS, ARM, or
authority consumption.

Canonical implementation identity:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION.md`

Code:
`scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py`
and `tests/research/test_harness_synthetic_edge_calibration_v2_rank_policy.py`.

The original prereg (`ada237e`) and Amendment_001 (`d8f0a99`) are not
rewritten. V1 TCB files are unchanged.

- implementation_exists: **true** (fixture only)
- synthetic_execution_authorized: **false**
- v2_production_arm_authorized: **false**
- production_calibration_executed: **false**
- result minted: **false**
- authority consumed: **false**
- next required step: `INDEPENDENT_IMPLEMENTATION_REVIEW`

## 2026-09-11 — V2 rank-degeneracy fixture implementation repair

**Decision:** narrow repair of the fixture-only V2 rank-policy module
after independent implementation review (`MAJORS=1`, `MINORS=3`).

Closed:

- MAJOR-1: removed unauthorized NULL taxonomy override; taxonomy is
  exactly `taxonomy_of(selected)`
- MINOR-A: lookahead/chronology cannot map to a candidate reason
- MINOR-B: unused precedence helpers removed; live early-return is the
  single authoritative path
- MINOR-C: removed non-frozen bootstrap/placebo/visibility RNG branch

No prereg change. No Amendment_002. No V1 TCB change. No production
run, ARM, RESULT, or authority consumption.

- next required step: `INDEPENDENT_NARROW_REVIEW_OF_REPAIR`

## 2026-09-12 — V2 rank-degeneracy implementation freeze

**Decision:** freeze the reviewed fixture-only V2 rank-policy
implementation at HEAD `a310837bab4ee60c7495cca3bdb476abdc58a041`
(tree `b15c4102b01514ff73e1728aec072eda9b528815`) after the independent
narrow rereview of its repair closed clean (`BLOCKERS=0`, `MAJORS=0`,
`MINORS=0`, `GO_FOR_IMPLEMENTATION_FREEZE`).

Canonical freeze artifact:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json`.

The freeze binds the reviewed implementation HEAD/TREE, the original
prereg (`ada237e`) and Amendment_001 (`d8f0a99`) identities, the
execution-authoritative V2 policy source
(`scripts/research/harness_synthetic_edge_calibration_v2_rank_policy.py`)
by git blob/SHA256/size, and the five unchanged V1 TCB files by
SHA256/size. This freeze commit changes only the freeze artifact, its
verifier test, and status/ledger documentation. The reviewed V2
implementation bytes are unchanged.

- reviewed_implementation_head: `a310837bab4ee60c7495cca3bdb476abdc58a041`
- freeze_parent: `a310837bab4ee60c7495cca3bdb476abdc58a041` (immediate
  parent of this freeze commit)
- production_armed: **false**
- production_executed: **false**
- result_minted: **false**
- world_records_created: **false**
- authority_consumed: **false**
- v1_attempt_status: `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- v1_3087_subset_claimable: **false**

No prereg change. No Amendment_002. No V1 TCB change. No V2
implementation change. No production ARM, RESULT, or WORLD_RECORDS.

- next required step: `CREATE_NEW_V2_PRODUCTION_ARM`

## 2026-09-12 — V2 production driver + canonical plan + ARM runtime authorization

**Decision:** implement, on top of the immutable V2 policy freeze
(`f96197d`), the execution layer the frozen fixture intentionally omits: a
canonical production plan mechanically inherited from the frozen V1 grid, a
thin production orchestration layer, and a V2 ARM-authorization runtime. Not
an execution freeze, not an ARM.

Canonical implementation identity:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_DRIVER.md`.

New code:
`scripts/research/harness_synthetic_edge_calibration_v2_production.py` and
`tests/research/test_harness_synthetic_edge_calibration_v2_production.py`.

- `canonical_v2_production_jobs() == harness_synthetic_edge_calibration_v1_production.planned_production_jobs()`
  byte-for-byte (3200 worlds; no new world set); `canonical_v2_plan()` binds
  that grid's identity plus the frozen V2 policy's exact blob/SHA256/size,
  deterministically serialized and hashed.
- Per-world classification is delegated verbatim to the frozen fixture's own
  private `_evaluate_v2_world_inner`; proven byte-for-byte equivalent to the
  fixture's public `evaluate_v2_world` across every scenario × non-production
  N × world index reachable through the fixture, including the
  forced-lookahead → `WORLD_INVALID` path.
- `v2_production_arm_authorized()` recognizes only a self-consistent ARM
  commit binding freeze parent HEAD/TREE, freeze artifact hash/size, V2
  policy hash/size, all five V1 TCB hashes, the canonical plan hash, and the
  original prereg/Amendment_001 identities, evaluated from committed git
  object bytes (not worktree, not caller arguments).
- No ARM artifact (`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_ARM.json`)
  exists anywhere in the repository as of this unit.

The frozen V2 fixture, its freeze artifact, the original prereg, and
Amendment_001 are all byte-identical to before this unit (verified by
`git diff --stat`, zero output).

- v2_production_arm_authorized (at this HEAD): **false**
- production_calibration_executed: **false**
- production_result_minted: **false**
- world_records_created: **false**
- authorization_consumed: **false**
- v1_attempt_status: `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- v1_3087_subset_claimable: **false**

No prereg change. No Amendment_002. No V1 TCB change. No V2 policy or
freeze-artifact change. No real V2 ARM created anywhere in project history.
No production run, RESULT, or WORLD_RECORDS.

- next required step: `INDEPENDENT_V2_PRODUCTION_DRIVER_AND_ARM_RUNTIME_REVIEW`

## 2026-09-12 — V2 production lifecycle repair (pre-outcome)

**Decision:** close the independent adversarial review's 4 BLOCKERs + 1
MAJOR (no historical authorization; no durable one-shot reservation/claim;
RESULT/WORLD_RECORDS mint unimplemented; aggregation absent; per-world
re-verification overhead) by implementing the complete pre-outcome
production lifecycle on top of the unchanged V2 policy freeze (`f96197d`).
Not an execution freeze, not an ARM.

Canonical implementation identity:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_PRODUCTION_DRIVER.md`.

- `verify_historical_v2_execution_authority(repo_root, arm_commit)`:
  commit-parameterized (not ambient-HEAD) verification, reusing the existing
  generic authorization primitive; proven to work from a descendant commit
  and from a clean clone.
- `v2_durable_reservation_document` / `v2_durable_claim_document` /
  `assert_v2_reservation_available`: pure identity derivations from a
  historically-verified bound (mirroring V1's own already-frozen
  reservation/claim design), with git-committed durability and fail-closed
  checks proven for sequential duplicate and simulated concurrent
  reservation races.
- `V2DurablePartialWorldStore`: local crash-safe per-world checkpoint cache
  reusing V1's atomic-write primitives verbatim; cached records are never
  trusted as authority without independent recomputation at mint time.
- `derive_v2_cell_aggregates` / `derive_v2_coverage_verdicts` /
  `derive_v2_required_coverage_status` / `derive_v2_mechanical_conclusions`:
  wire the frozen fixture's own already-reviewed aggregation pipeline
  (`aggregate_v2_records`, `CellAggregateV2.result_schema`,
  `evaluate_cell_coverage`, `required_coverage_for_conclusion`,
  `mechanical_conclusion_v2`) onto real evidence -- no aggregation logic is
  reimplemented.
- `mint_v2_world_records` / `mint_v2_result` / `verify_historical_v2_result`:
  a real, future-capable mint and independent historical re-verification
  path, proven to accept only honest evidence and reject forged
  checkpoints, tampered WORLD_RECORDS, and tampered RESULT payloads.
- `V2ProductionSession` / `open_v2_production_session`: authorize once per
  run; mint/historical verification never trust the session, only
  independently re-established git-object authority.

**Explicit, deliberate scope boundary (not silently deferred):** the
original V1-methodology verdict for each of the 33 required-coverage-map
conclusions (`frozen_required_coverage_map()`'s `inherited_claim` strings)
is not reconstructed by this unit -- doing so from prose would itself be an
unreviewed scientific choice. `derive_v2_mechanical_conclusions` requires
this mapping as an explicit parameter and fails closed if any of the 33 ids
is missing. A separate, dedicated, independently reviewed mapping unit must
supply it before a real mint.

The frozen V2 fixture, its freeze artifact, the original prereg,
Amendment_001, and all five V1 TCB files remain byte-identical (verified by
`git diff --stat`, zero output).

- v2_production_arm_authorized (at this HEAD): **false**
- real V2 ARM created: **false**
- production run: **false**
- real RESULT minted: **false**
- real WORLD_RECORDS created: **false**
- authorization consumed: **false**
- v1_attempt_status: `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- v1_3087_subset_claimable: **false**

No prereg change. No Amendment_002. No V1 TCB change. No V2 policy or
freeze-artifact change. No real V2 ARM created anywhere in project history.
No production run, RESULT, or WORLD_RECORDS.

- next required step: `INDEPENDENT_V2_PRODUCTION_LIFECYCLE_REREVIEW`

## 2026-09-12 — V2 session/reservation narrow repair + inherited-ladder provenance audit

**Decision:** close the second independent rereview's 3 BLOCKERs (forged/
`None` session executed with no ARM anywhere in the repository; reservation
primitives never invoked by the execution path, so two sessions against the
same unreserved ARM both fully executed; `inherited_detection_conclusions`
an unverified caller parameter able to change the final RESULT for identical
evidence) on top of the unchanged V2 policy freeze. Not an execution freeze,
not an ARM.

- `V2ProductionSession` is now `@dataclass(frozen=True, eq=False)`, made
  genuinely unforgeable via a module-private `WeakKeyDictionary` registry
  populated only by `open_v2_production_session` and the internal mint/
  historical-verification helpers. Proven to refuse `None`, `False`, `True`,
  `{}`, a manually-instantiated session with copied field values, a
  `dataclasses.replace()` copy, a bare string, and a session mutated via
  `object.__setattr__` -- all before `simulate_dgp` is ever called.
- `establish_v2_durable_reservation(repo_root, arm_commit)` enforces VERIFY
  ARM -> VERIFY PLAN/POLICY/TCB -> ESTABLISH RESERVATION -> OPEN SESSION ->
  EXECUTE by construction: `open_v2_production_session` now refuses unless a
  matching reservation is already committed at HEAD. Guarantee level stated
  precisely: airtight within one shared repository (git's own commit/ref
  locking); a residual, explicitly-documented race remains across
  independent unsynchronized clones, where only wasted duplicate
  computation -- never a duplicate authoritative RESULT -- is possible.
- Performed (not implemented) a full provenance audit of the 33
  inherited-ladder conclusion ids against the frozen V1 prereg's
  `acceptance`/`conclusion_authority` sections and Amendment_001's explicit
  map:
  `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_INHERITED_LADDER_PROVENANCE_AUDIT.md`.
  18/33 are mechanically unambiguous; 15/33 are not yet confirmed unambiguous
  (no explicit threshold, or would require inferring an unstated alias).
  Per the governing stop condition, the mapping is **not** implemented or
  bound as authority in this unit -- `inherited_detection_conclusions`
  remains an explicit, required, caller-supplied parameter, and
  `mint_v2_result`'s RESULT remains not scientifically self-contained until
  a dedicated methodology amendment resolves the 15 unresolved ids.

The frozen V2 fixture, its freeze artifact, the original prereg,
Amendment_001, and all five V1 TCB files remain byte-identical (verified by
`git diff`, zero output).

- forged/None session execution: **no longer possible**
- reservation gates execution: **yes, within one shared repository**
- double execution from the same unreserved ARM: **no longer possible**
- caller can still change the final conclusion via the mapping: **yes
  (unresolved; explicit, documented, not worked around)**
- real V2 ARM created: **false**
- production run: **false**
- real RESULT minted: **false**
- real WORLD_RECORDS created: **false**
- authorization consumed: **false**
- v1_attempt_status: `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- v1_3087_subset_claimable: **false**

No prereg change. No Amendment_002. No V1 TCB change. No V2 policy or
freeze-artifact change. No real V2 ARM created anywhere in project history.
No production run, RESULT, or WORLD_RECORDS.

- next required step: `PRE_OUTCOME_INHERITED_LADDER_METHODOLOGY_AMENDMENT`

## 2026-09-15 — V2 33/33 implementation freeze

**Decision:** freeze the independently reviewed V2 33/33 implementation at
HEAD `614295d4c0bf7a263bd2c6dc9a5c595e2c80055f`
(tree `e754b12f8db93db3109a30e3b4d476eb85803e04`) after the independent
implementation review closed `GO_FOR_IMPLEMENTATION_FREEZE`.

Canonical freeze artifact:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json`
(human twin:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.md`).

The freeze binds the reviewed implementation HEAD/TREE, the two
execution-authoritative 33/33 sources
(`harness_synthetic_edge_calibration_v2_inherited_ladder.py`,
`harness_synthetic_edge_calibration_v2_production.py`) by git blob/SHA256/size,
the original V2 prereg (`ada237e`) and Amendment_001 (`d8f0a99`),
Amendment_003 (`dfba85d`) and Amendment_004 (`df5dcde`), the rejected
Amendment_002 identity (`f846075`) as historical non-governing authority,
the frozen V2 rank-policy source and its implementation freeze (`f96197d`),
the five unchanged V1 TCB files, canonical V2 plan SHA256
`7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800`, and
world count 3200. Visibility remains `UNRESOLVED_FAIL_CLOSED`. MINOR-1
(no memoization) and MINOR-2 (ADEQUATE FINAL_OVERALL mint blocked by
visibility siblings) are recorded, not repaired.

This freeze commit changes only the freeze artifact/document, its verifier
test, and status/ledger/index plumbing. Reviewed implementation bytes,
methodology, and V1 TCB are unchanged.

- reviewed_implementation_head: `614295d4c0bf7a263bd2c6dc9a5c595e2c80055f`
- freeze_parent: `614295d4c0bf7a263bd2c6dc9a5c595e2c80055f`
- amendment_002_governs_executable_science: **false**
- production_armed: **false**
- production_executed: **false**
- result_minted: **false**
- world_records_created: **false**
- authority_consumed: **false**
- arm_created: **false**
- execution_authorized: **false**
- canonical_3200_run_started: **false**
- v1_attempt_status: `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM`
- v1_3087_subset_claimable: **false**

No implementation-code change. No methodology change. No prereg/amendment
rewrite. No V1 TCB change. No V2 ARM, RESULT, or WORLD_RECORDS.

- next required step: `INDEPENDENT_V2_33_33_IMPLEMENTATION_FREEZE_REVIEW`

## 2026-09-15 — V2 authorized GROUND_TRUTH_VISIBLE plumbing

**Decision:** supply the already-defined V1 `GROUND_TRUTH_VISIBLE` statistic
for the canonical 3200 world identities as a separate visibility evidence
artifact. Classification B from independent diagnosis: defined pre-outcome,
required input not persisted.

- no second reservation
- no V2 candidate re-evaluation
- canonical WORLD_RECORDS bytes unchanged (`d372eb00…`)
- no RESULT minted
- no threshold/denominator/operator change
- ARM-bound `production.py` / `inherited_ladder.py` bytes unchanged

Canonical visibility evidence:
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_VISIBILITY.json`

- next required step: `INDEPENDENT_VISIBILITY_PLUMBING_REVIEW`

## 2026-09-15 — Canonical V2 RESULT mint

**Decision:** mint the one-shot canonical V2 RESULT from authenticated
WORLD_RECORDS + authenticated visibility evidence via
`assemble_v2_result_payload_with_visibility`. Independent visibility review
verdict was `GO_FOR_RESULT_MINT`. No candidate re-evaluation, no world
regeneration, no second reservation, no WORLD_RECORDS/VISIBILITY modification,
no threshold/denominator/operator change, no post-hoc rescue.

- ARM_HEAD = `18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea`
- PLAN_SHA = `7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800`
- RUN_IDENTITY = `2088e76f99685c36e65387117b6f8a49482b3b68939f01d827023e0d36991818`
- WORLD_RECORDS SHA256 unchanged: `d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821`
- INNER_RECORDS SHA256 unchanged: `763a8ce802b7b5efa133ebe3132103cbb96c86d83c7c2dacc992147c8ee4ef66`
- VISIBILITY SHA256 unchanged: `9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65`
- RESULT path: `docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_RESULT.json`
- RESULT SHA256: `761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0`
- FINAL_OVERALL_MECHANICAL_CONCLUSION = `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`
- VISIBILITY_FLOOR = `ABOVE_MEASURED_FLOOR`
- TINY_NOISY_ORACLE_DIAGNOSTIC = `VISIBILITY_FLOOR`
- MODEL_FLOOR = `MODEL_FLOOR`
- TINY_NOISY_CONCLUSION = `VISIBILITY_FLOOR`
- ORACLE_F03_TINY_NOISY = `VISIBILITY_FLOOR`
- ARM-bound `production.py` / `inherited_ladder.py` bytes unchanged

This entry records the frozen mechanical labels. It does not interpret them.

- next required step: `CANONICAL_V2_RESULT_INTERPRETATION`

## 2026-09-15 — Targeted V2 confirmatory power repair

**Decision:** restore already pre-outcome-defined V1 confirmatory detection
semantics inside the V2 evaluator. Canonical V2 RESULT remains immutable
historical evidence. This is not V3, not threshold tuning, and not a rescue
of `METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`.

Pre-outcome authority verified uniquely before implementation:

- V1 `MODEL_DETECTED` = primary_positive AND bootstrap_positive AND placebo_separation
- V1 production actually executed frozen bootstrap (500) and placebo (999)
- EASY/MODERATE oracle power and MODEL_FLOOR were intended to read MODEL_DETECTED, not STRICT_PASS
- `>=0.02` materiality remains a separate STRICT_PASS / MATERIALITY_ONLY_DIAGNOSTIC identity

Repair:

- execute frozen V1 `prediction_bootstrap` / `placebo_q95` in V2 inner evaluation
- `detected` = `MODEL_DETECTED`
- MATERIALITY_ONLY_DIAGNOSTIC counts STRICT_PASS from gates
- do not lower 2%; do not change Wilson EASY 0.90 / MODERATE 0.70
- do not remint RESULT / WORLD_RECORDS / VISIBILITY
- do not run a new 3200-world calibration in this unit

Canonical hashes unchanged:

- WORLD_RECORDS SHA256 `d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821`
- VISIBILITY SHA256 `9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65`
- RESULT SHA256 `761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0`

- next required step: `INDEPENDENT_POWER_REPAIR_REVIEW`

## 2026-09-15 — V2 control plan identity rebind

**Decision:** rebind `FROZEN_CANONICAL_V2_PLAN_SHA256` from the historical
unrepaired plan identity
`7fa12fd3b939cd210a69da37659fd1013a1dba43aca4c06abb6f5a6442a33800`
to the live `canonical_v2_plan` identity of the independently reviewed
confirmatory-power repair:

`b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f`

The 3200-world job list is unchanged
(`v1_planned_jobs_sha256` =
`5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6`).
The plan SHA changed only because repaired rank-policy bytes are part of
canonical plan identity. No world specification, DGP, scenario, N, seed,
feature library, or cell membership changed.

This is an identity/provenance repair only. It does not create a production
freeze, ARM, reservation, calibration, or RESULT.

Canonical hashes unchanged:

- WORLD_RECORDS SHA256 `d372eb00d4f6df9b4f8a2b0dcb22b051d95787ddeb8494a3c0efc31561e39821`
- VISIBILITY SHA256 `9be8dceb07d8fc43b01ef8630d4ad9f52e7401fd6f095b3c7a5bf364701c8b65`
- RESULT SHA256 `761cc9afc59265bfb94afecbd293082c274abf3affce3d9693f463442326c1e0`

- next required step: `INDEPENDENT_IDENTITY_REBIND_REVIEW`

## 2026-09-16 — V2 control-calibration execution freeze

**Decision:** freeze the independently reviewed confirmatory-power control
calibration runtime at implementation
`8917c776ac8c148828bfab4395fd84890ff3c847`
(tree `15664b6a47b7196fcd230619e134f6a89feec23e`).

Canonical freeze artifact path remains
`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_EXECUTION_FREEZE.json`.
The freeze commit is the immediate child of `8917c776`. It does not rewrite
historical freeze `2523b389` or historical ARM `18ebb4c`. Those remain the
authority for historical plan `7fa12fd3…` and RUN_IDENTITY `2088e76f…`.

This freeze binds plan
`b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f`,
world count 3200, V1 jobs
`5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6`,
and reviewed rank-policy
`1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec`
(size 46396). Freeze authentication forbids carrying ARM/RESULT/
WORLD_RECORDS/RESERVATION on the freeze commit; those historical blobs
remain byte-identical at their minting commits.

- production_armed: **false**
- production_executed: **false**
- result_minted: **false**
- world_records_created: **false**
- arm_created: **false**
- canonical_3200_run_started: **false**

No scientific-code change in the freeze commit. No reservation. No control
calibration execution. No RESULT mint.

- next required step: `CREATE_CONTROL_CALIBRATION_PRODUCTION_ARM`

## 2026-09-16 — V2 control-calibration production ARM

**Decision:** arm exactly one canonical 3200-world V2 control-calibration
production execution as the immediate child of freeze
`bd5b5d3030f811faf7055517f314a2b1a51ba41e`.

ARM binds:

- reviewed implementation `8917c776ac8c148828bfab4395fd84890ff3c847`
- plan `b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f`
- world count 3200
- rank-policy `1700ada1985e622c9b6def95960b313f12cbb95fd290aa608b09eb44f2cad7ec`

Historical ARM `18ebb4c5629e1717a6633ee6bd63cda7c0bb65ea` remains valid for
plan `7fa12fd3…` and RUN_IDENTITY `2088e76f…`. The new ARM does not
authorize that historical plan.

- authorization_consumed: **false**
- reservation_created: **false**
- production_executed: **false**
- result_minted: **false**
- world_records_created: **false**

No scientific-code change. No control calibration execution.

- next required step: `EXECUTE_CONTROL_CALIBRATION_FROM_EXACT_ARM_COMMIT`

## 2026-09-16 — V2 confirmatory-power control calibration executed

**Decision:** execute exactly one canonical 3200-world control calibration
from ARM `710cad607ec6740e550698cdc212f7dd33004481`.

Topology verified before reservation:

- IMPLEMENTATION `8917c776ac8c148828bfab4395fd84890ff3c847`
- FREEZE `bd5b5d3030f811faf7055517f314a2b1a51ba41e`
- ARM `710cad607ec6740e550698cdc212f7dd33004481`
- `ARM_AUTHORIZATION_VALID = YES`

Reservation `068874d8fa710f474f91fe61224a7cc54a42e0cd` created by
`establish_v2_durable_reservation`. RUN_IDENTITY
`90d38af4951b0bbe00fc5ffaf7989c8940d178c31aad987176901c7ce947ad1e`.
PLAN `b0ed15534ef0cf45f1232baa0d7c1881fb3a8aaa086477d67a5ab7e9198c677f`.
WORLD_JOB_SHA `5adf682ee48a868acbe01d9e0b9e33133db26089119396b3539b4e9cb8af5bb6`.

Execution: 3200/3200 worlds completed; WORLD_VALID=3200; WORLD_INVALID=0;
CANDIDATE_IDENTIFIABLE=31708; CANDIDATE_NOT_IDENTIFIABLE=292.
Coverage for all 33 required conclusions: ADEQUATE.

Control-calibration evidence (does not overwrite historical blobs):

- WORLD_RECORDS SHA256 `e8667f930a4acc7fb5dd26fa62414a8f4b359121336902aac651cb76f4e50dbf`
- RECORDS_INNER SHA256 `f0d18ca1c8ed654856abca03d9e0f8d22b72ab5f6f4683cc11e45f3353bc0559`
- VISIBILITY SHA256 `ed1c17f0e2eb8f04ed917a7c84811d10a0d152f770a9315d2ade1cac1be93f9b`
- RESULT SHA256 `ffce3daa24eb9039526d6de4b11a6ac43cfd36803058fe21827f1cd1f839100b`

`mint_v2_result` refused `V2VisibilityStatisticUnavailable`. RESULT assembled
by `assemble_v2_result_payload_with_visibility` from independently derived
per-world `GROUND_TRUTH_VISIBLE`. Frozen evaluator FINAL:
`METHODOLOGY_POWER_REPAIR_REQUIRED_BEFORE_B2_06`.

Historical WORLD_RECORDS `d372eb00…` / VISIBILITY `9be8dceb…` / RESULT
`761cc9af…` remain immutable at their minting commits.

- production_executed: **true**
- world_records_created: **true**
- result_minted: **true** (control-calibration RESULT; `mint_v2_result` refused)
- selective_rerun: **false**
- second_canonical_attempt: **false**

- next required step: `RECORD_FROZEN_CONTROL_CALIBRATION_EVALUATOR_OUTPUT`

## 2026-09-16 — V3 confirmatory preregistration materialized

Materializes `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_CONFIRMATORY_DESIGN.md` /
`_SPEC.md` plus two rounds of independent adversarial methodology review
into a single binding prereg (`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md`
/ `.json`). No scientific choice left to implementation.

Binds: claim-conditional Clark-West-adjusted estimand `theta_hat =
sum(S_t*d*_t)/sum(S_t)` on the unmodified `expanding_era_predictions`
nested BASE/CAND construction (overlay-with-fallback forbidden for this
calibration); full-time-axis joint `(d*_t,S_t)` stationary bootstrap
(gap-closed support-only resampling forbidden); Politis-White (2004) +
Patton-Politis-White (2009) automatic block length on the derived
influence series `z_t=S_t*(d*_t-theta_hat)`, one selector call per world;
`B=999`; recentered bootstrap-t one-sided p-value, `alpha=0.05`; exactly 3
per-world validity guards (chronology, support validity, identifiability
and resampling validity) — `NONSTATIONARY_TRAP` reclassified as a fourth
aggregate acceptance cell, not a guard, using the identical `DETECTED`
indicator; `support_count>=50` hard floor, `effective_N` diagnostic-only;
one-sided Wilson `z=1.6448536269514722`, 400 fresh worlds/cell
(EASY/MODERATE/NULL/NONSTATIONARY_TRAP), exact integer PASS/FAIL
boundaries; fresh `world_index 10000..10399` at `N=5000` (disjoint from
the V1/V2 canonical grid's `0..399`, mechanically not policy-only); new
RNG namespace `V3_CONFIRMATORY`.

No V1/V2 frozen artifact modified. No implementation exists yet. No
freeze, ARM, reservation, execution, or fresh V3 outcome.

- v3_design_complete: **true**
- v3_prereg_materialized: **true**
- v3_prereg_review_required: **true**
- v3_prereg_frozen: **false**
- v3_run_authorized: **false**
- v3_armed: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**

- next required step: `INDEPENDENT_V3_PREREG_REVIEW`

## 2026-09-16 — V3 prereg freeze authority

Independent review of `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG.md`/`.json`
(including the exact Politis-White/Patton-Politis-White selector implementation
binding) closed with verdict `ACCEPTED` at exact commit `4b7e0d6dfda1cb9475a610f51ccbec0906fd0133`
/ tree `fe779fc37e31bd23700b6f70d476f4cb1249223d`.

`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PREREG_FREEZE.md`/`.json` freezes that
exact accepted content as sole scientific authority for V3 implementation.
The accepted prereg bytes are not modified; both SHA256s were independently
recomputed from `4b7e0d6d`'s git objects and matched exactly (MD
`739247ef228c80988abd40ac60b095e0e4e9e5ee45f81761cb1e3aa846161085`,
JSON `2d3a42e7fc9c91bf1b4bafaec01b2947b454e40151c47be9f2ff3f92a6e41617`)
before this freeze was written. `freeze_commit_head`/`freeze_commit_tree`
are intentionally `UNSET_UNTIL_THIS_COMMIT`, matching the existing V2
execution-freeze convention — this artifact never self-hashes.

No V1/V2 frozen artifact touched. No V3 implementation exists. No V3
world/outcome generated or inspected. No reservation or ARM created.

- v3_design_complete: **true**
- v3_prereg_materialized: **true**
- v3_prereg_review_required: **false**
- v3_prereg_frozen: **true**
- v3_implementation_complete: **false**
- v3_run_authorized: **false**
- v3_armed: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**

- next required step: `V3_IMPLEMENTATION`

## 2026-09-16 — V3 prereg Amendment 001 (pre-outcome) + re-freeze

Implementation correctly stopped before writing V3 scientific code: the
frozen prereg (`4136f53d`) was literally unimplementable
(`namespace_seed(world_seed, "V3_CONFIRMATORY", feature_id)` -- the frozen
V1 primitive rejects any token outside `NAMESPACES=(DGP,BOOTSTRAP,PLACEBO,VISIBILITY)`)
and left `SE_hat`'s `ddof` unbound. No V3 world/outcome was generated or
inspected; no ARM/reservation existed.

Classified `PRE_OUTCOME_CORRECTNESS_AND_SPEC_COMPLETENESS_AMENDMENT` --
not outcome-driven, not a power/threshold repair, not a redesign.

Blocker 1: editing `harness_synthetic_edge_calibration_v1_lib.py`'s
`NAMESPACES` allowlist was evaluated and rejected (would break live
`assert_v1_tcb_intact()` unless `FROZEN_V1_TCB_SHA256["lib"]` is also
updated, or, if updated, reintroduce for TCB identity the exact
live-global commit-purity defect already repaired once for canonical
plan identity). Resolved with a new, non-frozen-file-modifying primitive
`scripts/research/harness_synthetic_edge_calibration_v3_rng.py`
(`v3_namespace_seed`), reusing `_uint64_from_digest` verbatim; `v1_lib.py`
SHA256 `12230dcad7...` unchanged. Proven by
`tests/research/test_harness_synthetic_edge_calibration_v3_rng.py`
(7/7): all 4 existing namespace outputs/PCG64 prefixes unchanged;
`V3_CONFIRMATORY` deterministic, distinct from BOOTSTRAP/PLACEBO, and
byte-identical to what `namespace_seed()` itself would compute (proven
via a local, in-memory-only, reverted allowlist extension).

Blocker 2: `SE_hat` bound to `ddof=1` (`numpy.std(theta_star, ddof=1)`).

Nothing else changed. Original freeze `4136f530378e91d545e2644a650f0a7a07a731c3`
remains valid historical evidence of the pre-amendment text, not
rewritten. New freeze binds the amended content at `543687fe79ba2e6254e879b0574e58a1909c15fe`.

- v3_pre_outcome_amendment: **COMPLETE**
- v3_rng_namespace_blocker: **CLOSED**
- v3_se_ddof: **1**
- v3_prereg_frozen: **true**
- v3_implementation_complete: **false**
- v3_implementation_review_required: **true**
- v3_run_authorized: **false**
- v3_armed: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**

- next required step: `V3_IMPLEMENTATION`

## 2026-09-17 — V3 implementation freeze + pre-ARM execution binding

Independent review of the V3 confirmatory implementation closed
`IMPLEMENTATION_ACCEPTED` at exact commit
`70673673f5bc0108e6bcf2aaf55a762ebc49940a` / tree
`e94e18cb900a44824b96dee1d4b6cbb574c95e5a` (lineage `fd21ed7f` →
`e1b7502` → `70673673`; F1/F2/F3 CLOSED).

`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_IMPLEMENTATION_FREEZE.md`/`.json`
freezes that exact accepted implementation identity. Scientific bytes
are not modified. Binding is to:

- confirmatory implementation SHA256 `38a494917dcf721b…` (24059 bytes)
- RNG shim SHA256 `8bd6aef151139bc1…` (2325 bytes)
- frozen prereg MD/JSON SHA256 `ab03c68a…` / `194fed69…`
- inherited V1 lib SHA256 `12230dcad714e3a0…` (37636 bytes)
- arch 8.0.0 selector hashes already pinned by prereg
- canonical grid: EASY/MODERATE/NULL/NONSTATIONARY_TRAP,
  `world_index 10000..10399`, 400/cell, 1600 worlds, B=999, F03,
  frozen one-sided Wilson integer boundaries

`harness_synthetic_edge_calibration_v3_authority.py` is pre-ARM plumbing
only: it derives a deterministic scientific run identity from tracked
frozen authority and refuses caller kwargs, path/env substitution,
reservation, WORLD_RECORDS/RESULT minting, and canonical execution.
Freeze and ARM remain separable. No ARM artifact was created.

- v3_implementation_complete: **true**
- v3_implementation_review_required: **false**
- v3_implementation_frozen: **true**
- v3_pre_arm_binding_complete: **true**
- v3_run_authorized: **false**
- v3_armed: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**

- next required step: `V3_ONE_SHOT_CANONICAL_ARM`

## 2026-09-17 — V3 one-shot canonical ARM

`HARNESS_SYNTHETIC_EDGE_CALIBRATION_V3_PRODUCTION_ARM.md`/`.json` is a
tracked one-shot authorization for the already-frozen V3 canonical
execution. Immediate parent is implementation-freeze HEAD
`76f2100715b67799231eab8132cd856823fdf3f8` / tree
`dd59466b02c56f101764cb17052a6d5eb514b945`. Bound run identity
`ce66442985a637f05508c980257f5ca8b869df15e2b94b87d1110c3ef75fd69f`.
Accepted implementation `70673673f5bc0108e6bcf2aaf55a762ebc49940a`
unchanged.

Lifecycle `AUTHORIZED_UNUSED`. `authorization_consumed = false`. ARM
creation does not consume the one-shot. No reservation, no
`world_index 10000..10399` execution, no WORLD_RECORDS, no RESULT.

- v3_implementation_frozen: **true**
- v3_pre_arm_binding_complete: **true**
- v3_run_authorized: **true**
- v3_armed: **true**
- authorization_consumed: **false**
- canonical_reservation_created: **false**
- canonical_execution_started: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**

- next required step: `V3_CANONICAL_RESERVATION`

## 2026-09-17 — V3 one-shot canonical reservation + RESULT

Exactly one reservation consumed ARM `de7b38341c65eb82b66494d910fefd3395f8b232`
for run identity
`ce66442985a637f05508c980257f5ca8b869df15e2b94b87d1110c3ef75fd69f`.
Reservation identity
`0bb58c95ad4de4909b6157688c7444e35e5cc122ffb10811ccefbfc82e216f34`.
Canonical grid `world_index 10000..10399` executed once (1600/1600
terminal; 0 invalid). WORLD_RECORDS SHA256
`5d09631db5180f562076b2191fe002aa21318a3925d3cd1c4014d83e4b41eb4f`.
RESULT SHA256
`f72eedcdcb511e2c7f22369cbdef164688317dfc99f9ab3e533df14cb2a27866`.

Mechanical cell verdicts (frozen Wilson n=400):

- EASY: 400/400 DETECTED, Wilson lower 0.99328, `PASS`
- MODERATE: 313/400 DETECTED, Wilson lower 0.74673, `PASS`
- NULL: 21/400 DETECTED, Wilson upper 0.07403, `INDETERMINATE`
- NONSTATIONARY_TRAP: 188/400 DETECTED, Wilson lower 0.42929, `FAIL`

`methodology_claimable = false`. No selective rerun, no second
reservation, no second RESULT. `DEFAULT_V4 = NO`. B2-06 and MARKET remain
unauthorized.

- v3_authorization_consumed: **true**
- v3_canonical_reservation_created: **true**
- v3_canonical_execution_complete: **true**
- v3_result_minted: **true**
- v3_rerun_authorized: **false**
- default_v4: **false**
- b2_06_execution_authorized: **false**
- market_execution_authorized: **false**

- next required step: `NONE_V3_RESULT_RECORDED_NO_RERUN_NO_V4_NO_B2_06_NO_MARKET`

## 2026-09-17 — V3 Microscope calibration closed; MARKET phase active

Status/closeout unit only. Canonical V3 RESULT is recorded as immutable
historical evidence and is not repaired, rerun, or reinterpreted.

Canonical RESULT authority: commit
`99b409cae279513eaf489194e7fa206082c60aef`. WORLD_RECORDS SHA256
`5d09631db5180f562076b2191fe002aa21318a3925d3cd1c4014d83e4b41eb4f`.
RESULT SHA256
`f72eedcdcb511e2c7f22369cbdef164688317dfc99f9ab3e533df14cb2a27866`.

Mechanical cell verdicts (unchanged):

- EASY: 400/400 detected, `PASS`
- MODERATE: 313/400 detected, `PASS`
- NULL: 21/400 detected, `INDETERMINATE`
- NONSTATIONARY_TRAP: 188/400 detected, `FAIL`

`methodology_claimable = false`. `incomplete_execution = false`.

Narrow scientific interpretation:

1. V3 successfully repaired the measured V2 confirmatory sensitivity
   problem (`EASY` `PASS`, `MODERATE` `PASS`).
2. V3 did not establish a generally claimable methodology (`NULL`
   `INDETERMINATE`, `NONSTATIONARY_TRAP` `FAIL`,
   `methodology_claimable = false`).
3. Known limitation: the current V3 confirmatory decision is
   insufficiently protected against the frozen nonstationary trap. Do
   not translate 188/400 into a general real-market false-positive rate;
   it applies only to the frozen synthetic trap DGP.
4. Consequence for MARKET research: V3 `DETECTED`/`PASS` is research
   evidence but must not by itself be treated as sufficient evidence of
   a robust market edge. Any promising MARKET result must retain
   explicit regime / nonstationarity scrutiny before stronger promotion
   claims.
5. The limitation is not authorization for immediate V4. Future
   methodology repair requires independent new evidence from actual
   research workload or a separately justified fresh calibration design.

Microscope status:

- `V3_CALIBRATION_CLOSED = YES`
- `V3_RERUN_AUTHORIZED = NO`
- `V3_METHODOLOGY_CLAIMABLE = NO`
- `CONFIRMATORY_SENSITIVITY = DEMONSTRATED_ON_FROZEN_SYNTHETIC_EASY_MODERATE`
- `NONSTATIONARY_TRAP_PROTECTION = INADEQUATE_ON_FROZEN_TRAP_DGP`
- `DEFAULT_V4 = NO`
- `MICROSCOPE_ACTIVE_RESEARCH_PHASE = NO`
- `MARKET_ACTIVE_RESEARCH_PHASE = YES`

The Microscope remains available as scientific instrumentation. It is
not deleted. It is no longer the active research program.

Active next phase: `MARKET`. Next substantive unit: `MARKET-01` (one
real crypto-market hypothesis through the existing research process).
This closeout does not execute `MARKET-01`, does not design a new MARKET
framework, and does not create infrastructure merely because MARKET is
beginning. Post-calibration operating priority: approximately 70–80%
actual market research, 20–30% infrastructure only when concrete
research blockers require it. Primary progress metric: MARKET hypotheses
honestly closed per week. Initial observational milestone: 25–50 real
market hypotheses through the stable research process — not a promise
that 25–50 studies establish alpha.

B2-06 remains `BLOCKED_MISSING_OBSERVABLE` / funding publication-latency
unproven. `MARKET-01` is not B2-06 and does not silently unblock it.

- v3_calibration_closed: **true**
- v3_methodology_claimable: **false**
- v3_rerun_authorized: **false**
- default_v4: **false**
- microscope_active_research_phase: **false**
- market_active_research_phase: **true**
- market_01_executed: **false**
- b2_06_execution_authorized: **false**

- next required step: `MARKET-01`

## 2026-09-17 — MARKET-01 outcome-blind data feasibility (OI_EXPANSION_WEAK_CONTINUATION)

Inspected existing price and OI authorities only. No hypothesis test, no
candidate outcomes, no prereg, no RESULT, no 2025/2026 access, no B2-06
execution.

Working direction (not frozen): after a directional price impulse, OI
expansion plus weak subsequent price continuation may mark a leverage-
accumulation state with possible later-reversal information. Absorption
is interpretation, not an observable.

Price authority: `CORE_BTC_BINANCE_V0` snapshot `717d37a4…` — Binance
USD-M `BTCUSDT` 1m klines, `available_at = bar_end_exclusive`,
`[2020-01-01, 2026-08-26)`, 0 missing minutes,
`ACCEPTED_FOR_DISCOVERY`.

OI authority: Vision `sum_open_interest` in snapshot `5a9d036b…` —
native 5m, `create_time` = bucket start, `available_at = period_end`,
`[2020-09-01, 2025-01-01)`, 455273 rows, 631 missing native buckets,
`oi_decision_time_availability_proven = true`. Dataset
`research_authorized = false` remains the B2-06 funding gate. MARKET-01
does not need funding and does not unblock B2-06.

Common usable overlap: `[2020-09-01T00:00:00Z, 2025-01-01T00:00:00Z)` at
**5m OI grain**. Causal alignment is defensible on exclusive-end clocks.
Local CORE parquet and OI JSONL are not in this worktree.

Mechanical sufficiency:

- `PRICE_POINT_IN_TIME_USABLE = YES`
- `OI_POINT_IN_TIME_USABLE = YES`
- `PRICE_OI_CAUSAL_ALIGNMENT_POSSIBLE = YES`
- `MARKET_01_PREREG_FEASIBLE = YES`

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_DATA_FEASIBILITY.md`.

- market_01_phase: **OUTCOME_BLIND_FEASIBILITY**
- market_01_outcome_inspected: **false**
- market_01_prereg_created: **false**
- market_01_executed: **false**
- b2_06_execution_authorized: **false**

- next required step: `MARKET-01_PREREG`

## 2026-09-17 — MARKET-01 prereg design blocked on three semantics

Outcome-blind design unit. Complete preregistration was **not**
materialized. No MARKET outcomes, no 2025/2026, no V3-on-market, no
B2-06 execution, no V4.

Research ID: `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`.

Unambiguous design intent (not a freeze): 30m impulse / 30m state /
60m outcome; 5m grain; common period `[2020-09-01, 2025-01-01)`; CORE
snapshot `717d37a4…`; OI snapshot `5a9d036b…` OI-only; candidate =
qualifying impulse ∧ OI expansion ∧ weak continuation; primary outcome
= 60m `reversal_return`.

Blockers (existing primitives cannot bind without changing their
estimands; no new matcher/V4/regime framework invented):

1. `BLOCKER_BASELINE_MATCHING_SEMANTICS` — no existing primitive
   implements two-group comparability on impulse magnitude and trailing
   volatility.
2. `V3_CONFIRMATORY_ESTIMAND_NOT_MAPPABLE_TO_TWO_GROUP_REVERSAL_CONTRAST`
   — V3 Clark-West nested OLS on equal synthetic eras cannot consume
   this comparison exactly; V3 was not modified.
3. `BLOCKER_ROBUSTNESS_SEMANTICS` — no existing mechanical
   concentration/downgrade rule binds to
   `DETECTED_BUT_NOT_ROBUST` vs `ROBUST_CANDIDATE` on this overlap.

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_DESIGN.md`.

- market_01_phase: **PREREG_DESIGN**
- market_01_prereg_materialized: **false**
- market_01_prereg_ready: **false**
- market_01_freeze_required: **true**
- market_01_outcome_inspected: **false**
- market_01_executed: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**

- next required step: `MARKET-01_AUTHOR_DECISIONS_ON_MATCHING_V3_MAPPING_ROBUSTNESS`

## 2026-09-17 — MARKET-01 outcome-blind preregistration materialized (unfrozen)

Author decisions resolved the three design blockers and the unbound
support floor. Complete preregistration materialized in human and
machine-readable form. No freeze, no ARM, no evaluator, no MARKET-01
execution, no MARKET outcome inspection, no 2025/2026, no B2-06, no V3
modification, no V4.

Research ID: `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`.

Bound confirmatory identity (new; not V3): stratified OLS
`reversal_return ~ candidate_indicator + stratum FE` on impulse-magnitude
× `PRE_VOL_60` tertiles; one-sided Politis–Romano stationary bootstrap
`B=999`, `alpha=0.05`; support floors `TOTAL>=100`, `CANDIDATE>=30`,
`BASELINE>=30`, `USABLE_STRATA>=3` with both groups `>=5`; LOEO sign
stability across five frozen calendar eras plus candidate-share
`<= 0.50` as a downgrade-only robustness layer.

`MARKET_01_TEST_CALIBRATED = NO`. V3 TRAP motivates the robustness layer
only; V3 synthetic calibration does not validate this test.

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.md`,
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG.json`.
Prior blocker record preserved:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_DESIGN.md`.

- market_01_phase: **PREREG_MATERIALIZATION**
- market_01_prereg_materialized: **true**
- market_01_prereg_ready: **true**
- market_01_freeze_required: **true**
- market_01_outcome_inspected: **false**
- market_01_executed: **false**
- market_01_test_calibrated: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**

- next required step: `MARKET-01_PREREG_FREEZE`

## 2026-09-17 — MARKET-01 preregistration frozen outcome-blind

Docs-only freeze of the exact MARKET-01 preregistration bytes at
materialization commit `9c1a661c52ad1ee7295cb898c1e1a048d5281d2f` /
tree `1928969ed4d12896a3793a7048aff163dc1b3dac`. Prereg files were not
modified. No evaluator, no MARKET-01 execution, no MARKET outcome
inspection, no 2025/2026, no B2-06, no V3 modification, no V4, no ARM.

Research ID: `MARKET-01_OI_EXPANSION_WEAK_CONTINUATION`.

Frozen payload SHA256:

- md `d82b60e1a923e8eb897252abc4a9013b6535357004f2dc7dc08f56f072542866`
- json `6885abaf178401a1307e9adc5c02c69dac4fb5f3034bfddebfafc2439dde2ce4`

`MARKET_01_TEST_CALIBRATED = NO`. Confirmatory identity is not V3.
`DEFAULT_V4 = NO`. B2-06 remains `BLOCKED_MISSING_OBSERVABLE`.

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.md`,
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_PREREG_FREEZE.json`.

- market_01_phase: **PREREG_FREEZE**
- market_01_prereg_materialized: **true**
- market_01_prereg_ready: **true**
- market_01_prereg_frozen: **true**
- market_01_freeze_required: **false**
- market_01_outcome_inspected: **false**
- market_01_executed: **false**
- market_01_test_calibrated: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**

- next required step: `MARKET-01_IMPLEMENTATION`

## 2026-09-17 — MARKET-01 frozen contract implemented, not armed

Implemented the frozen MARKET-01 preregistration as in-memory scientific
machinery. Bound CORE/OI snapshot evaluation is refused. No ARM, no
execution reservation, no MARKET outcome inspection, no 2025/2026, no
B2-06, no V3 modification, no V4. Prereg and freeze bytes unchanged.

Tests use synthetic fixtures only.

Evidence:
`scripts/research/market_01_oi_expansion_weak_continuation_lib.py`,
`scripts/research/market_01_oi_expansion_weak_continuation_authority.py`,
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION.md`.

- market_01_phase: **IMPLEMENTATION**
- market_01_prereg_frozen: **true**
- market_01_implemented: **true**
- market_01_armed: **false**
- market_01_outcome_inspected: **false**
- market_01_executed: **false**
- market_01_test_calibrated: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**

- next required step: `MARKET-01_IMPLEMENTATION_REVIEW`

## 2026-09-17 — MARKET-01 implementation frozen and one-shot ARM

Implementation freeze of accepted HEAD
`1019c5725a58c62d460276159a5683a202c1c3ea` / tree
`2a7a5ce74f9b0c419cf40093271df243ffb02d46` after independent review
verdict `IMPLEMENTATION_ACCEPTED`. Exactly one canonical MARKET-01
execution is armed and unused. No MARKET-01 execution, no MARKET
outcome inspection, no 2025/2026, no B2-06, no V3 modification, no V4.

Run identity:
`f430399f46e6122a2633a34e99e9bd0ab8fe65c1baf9c05b5982551a4608739d`.

`CANONICAL_EXECUTIONS_AUTHORIZED = 1`.
`CANONICAL_EXECUTIONS_CONSUMED = 0`.
`MARKET_01_TEST_CALIBRATED = NO`.

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_IMPLEMENTATION_FREEZE.md`,
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_ARM.md`,
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESERVATION.json`.

- market_01_phase: **ARM**
- market_01_prereg_frozen: **true**
- market_01_implementation_accepted: **true**
- market_01_implementation_frozen: **true**
- market_01_armed: **true**
- market_01_canonical_executions_authorized: **1**
- market_01_canonical_executions_consumed: **0**
- market_01_outcome_inspected: **false**
- market_01_executed: **false**
- market_01_test_calibrated: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**

- next required step: `ONE_CANONICAL_MARKET_01_EXECUTION`

## 2026-09-17 — MARKET-01 canonical execution RESULT (NO_EVIDENCE)

One canonical MARKET-01 execution completed from ARM HEAD
`9e6f398e4d0a294adff317354c64fdbce91315a2` / tree
`0f3092e8d61e040f34cb60f633584764c9cb6a6e`. Reservation consumed
exactly once. No rerun. Protected OOS untouched. B2-06 remains blocked.
`MARKET_01_TEST_CALIBRATED = NO`.

Run identity:
`f430399f46e6122a2633a34e99e9bd0ab8fe65c1baf9c05b5982551a4608739d`.

RESULT SHA256:
`5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`.

Mechanical classification: **`NO_EVIDENCE`**.
`TOTAL_ELIGIBLE_EPISODES = 7701`.
`CANDIDATE_EPISODES = 1720`.
`BASELINE_EPISODES = 5981`.
`USABLE_STRATA = 3`.
`beta_candidate = -0.00016324445975347867`.
`bootstrap_se = 0.00022218794009876234`.
`bootstrap_p_one_sided = 0.757`.
`DETECTED = NO`.
Robustness not evaluated.

Do not change thresholds or rerun. This is not validated alpha, not a
production signal, and not OOS validation.

Evidence:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json`.

- market_01_phase: **RESULT**
- market_01_prereg_frozen: **true**
- market_01_implementation_accepted: **true**
- market_01_implementation_frozen: **true**
- market_01_armed: **true**
- market_01_canonical_executions_authorized: **1**
- market_01_canonical_executions_consumed: **1**
- market_01_outcome_inspected: **true**
- market_01_executed: **true**
- market_01_test_calibrated: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- default_v4: **false**
- final_classification: **NO_EVIDENCE**

- next required step: `NEW_MARKET_HYPOTHESIS_ID_IF_AUTHORIZED` (not MARKET-01 rerun)

## 2026-09-18 — MARKET-01 episode-construction throughput (not a rerun)

Post-close engineering investigation of canonical `construct_episodes`
runtime. Frozen prereg/RESULT/lib/thresholds/estimand unchanged.
Reservation not consumed again. Protected OOS not opened. MARKET-02 not
started. Synthetic `SYNTHETIC_SNAPSHOT` profiling only.

Dominant cost was O(T × W) repeated 30d `|impulse|` and PRE_VOL_60
rebuilds via `close_at` / `b2_03.pre_vol_60`, not occupancy or
`EpisodeRecord` allocation. Semantics-preserving fast path added beside
the frozen library. Canonical RESULT SHA256 remains
`5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`.

- market_01_executed: **true** (prior canonical run; not repeated)
- market_01_scientifically_rerun: **false**
- protected_oos_touched: **false**
- frozen_scientific_bytes_changed: **false**

- next required step: `NEW_MARKET_HYPOTHESIS_ID_IF_AUTHORIZED` (not MARKET-01 rerun)

## 2026-09-21 — MARKET-06 outcome-blind historical feasibility retry

Independent retry of `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`
historical feasibility from this Cursor host. Does not reuse the previous
HOST_BLOCKED CONNECT-tunnel record at `97e01bd3…`.

Probed `data.binance.vision` and `api.bybit.com` on the host default
route (`HTTPS_PROXY` unset; no bypass). Binance Vision returned HTTP 200
AmazonS3/CloudFront; 36/36 monthly USD-M BTCUSDT 5m trade-price ZIP and
CHECKSUM objects for 2022-01 through 2024-12 are listed. Bybit V5
(`/v5/market/time` and structural kline probes for early 2022 / mid 2023
/ late 2024) returned CloudFront HTTP 403 country-block JSON. Class:
Binance `SOURCE_REACHABLE`; Bybit `VENUE_RESPONSE_ERROR`; not
`HOST_EGRESS_BLOCK`.

Zip payloads were not downloaded. No prices, dislocation, future
returns, or other scientific quantities were computed. 2025/2026 were
not opened. No MARKET-06 prereg/ARM/RESULT.

```text
MARKET_06_STATUS = CONCEPT_SELECTED_NOT_PREREGISTERED
VERDICT = MARKET_06_HISTORICAL_FEASIBILITY_REQUIRES_DESIGN_REVIEW
BINANCE_VISION = SOURCE_REACHABLE
BYBIT_V5 = VENUE_RESPONSE_ERROR
HOST_EGRESS_BLOCK = false
DISLOCATION_COMPUTED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_PREREG_CREATED = false
NEXT_UNIT = MARKET_06_BYBIT_OFFICIAL_HISTORICAL_ROUTE_OR_REACHABLE_HOST_REVIEW
```

Evidence: `docs/research/MARKET_06_CROSS_VENUE_FEASIBILITY.md`.

## 2026-09-21 — MARKET-06 OKX spot source-route design review

Pre-preregistration source-route review. Does not test MARKET-06. Does
not rewrite the Bybit feasibility artifact. Bybit remains
`VENUE_COUNTRY_ACCESS_RESTRICTION_FROM_CURRENT_EXECUTION_HOST`. Spot
leg candidate is official OKX `GET /api/v5/market/history-candles`
`instId=BTC-USDT` `bar=5m`. Perp leg remains Binance USD-M BTCUSDT 5m
trade-price Vision klines. Binance spot was not adopted.

Structural probes for 2022-01 / 2023-06 / 2024-12 returned native
completed 5m candles (`confirm=1`). 2022–2024 materialization: 36/36
Binance ZIP checksums verified; 1053 OKX official pages frozen by
SHA256. Timestamp-only census: 315648/315648 aligned, 0 gaps, 0
duplicates, alignment rate 1.0. No prices, dislocation, or future
returns inspected. 2025/2026 not opened.

```text
MARKET_06_STATUS = CONCEPT_SELECTED_NOT_PREREGISTERED
VERDICT = MARKET_06_OKX_HISTORICAL_FEASIBILITY_CONFIRMED
OLD_SPOT_SOURCE = BYBIT_BTCUSDT_SPOT
NEW_SPOT_SOURCE = OKX_BTC_USDT_SPOT
SOURCE_CHANGE_OCCURRED_BEFORE_PREREG = true
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_PREREG_CREATED = false
NEXT_UNIT = MARKET_06_PREREGISTRATION_DESIGN
```

Evidence: `docs/research/MARKET_06_OKX_SPOT_ROUTE_DESIGN_REVIEW.md`.

## 2026-09-21 — MARKET-06 feasibility durable raw-evidence retention

Outcome-blind durability unit only. Did not redownload. Did not mint a
new snapshot. Did not preregister or compute scientific outcomes. Local
runtime raw bytes were verified against frozen ledgers, then copied
byte-for-byte into
`docs/research_data/MARKET_06_OKX_BINANCE_FEASIBILITY_V0/durable_raw/`.

```text
DATASET_ID = MARKET_06_OKX_BINANCE_FEASIBILITY_V0
SNAPSHOT_ID = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
BINANCE_OBJECTS_RETAINED = 36
OKX_PAGES_RETAINED = 1053
ALL_PREEXISTING_SHA256_MATCH = true
RAW_BYTES_GIT_RETAINED = true
NEW_SNAPSHOT_MINTED = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
NEXT_UNIT = MARKET_06_PREREGISTRATION_DESIGN
```

Evidence: `docs/research/MARKET_06_OKX_BINANCE_FEASIBILITY_V0_DURABLE_RETENTION.md`.

## 2026-09-21 — MARKET-06 outcome-blind preregistration freeze

Two-step freeze of `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`.
Payload materialization commit `b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1`
(tree `ce436bf3d025340752f5afea765ea0cbe50e499e`) from
`PRE_PREREG_HEAD = a75a5272f994f9728308c47c524f2839b73762a7`. Docs-only
freeze binds those exact prereg bytes. No evaluator, ARM, RESULT, OHLC
inspection, dislocation-value inspection, or eligible-row counts from
price data.

```text
MARKET_06_STATUS = FROZEN_OUTCOME_BLIND
PRE_PREREG_HEAD = a75a5272f994f9728308c47c524f2839b73762a7
PREREG_CONTENT_HEAD = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
PREREG_MD_SHA256 = 0489fc71e999b48a7a82223615bd0acd50b1f69af8bc9901d1c681834e55cfcc
PREREG_JSON_SHA256 = 332d91140c7ead87f4539b49c8a5647064f9c5e1d0bb8178c16dcc7eaf7a88f4
SNAPSHOT_ID = e0403e40a9b1e2903f15fb9283ec6caf54788e48153038982e364d4318183e68
DURABLE_EVIDENCE_ROOT_SHA256 = f4b9e16a62707c70e782cc318399f3ba53ebb85c792e96cd12c164a98f0cdc6f
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
NEXT_UNIT = MARKET_06_IMPLEMENTATION_OUTCOME_BLIND
```

Evidence: `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG.md` and
`docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md`.

## 2026-09-21 — MARKET-06 pre-outcome prereg amendment and re-freeze

Legal pre-outcome correction of scientific-definition drift (F1 MAD
1.4826 robust scale; F2 `ABS_BTC_RET_24H` control; F3 arithmetic MAE;
F4 Gate-2 lower CI). First freeze retained as V0 historical evidence.
No evaluator, ARM, RESULT, or outcome inspection.

```text
AMENDMENT_REASON = PRE_OUTCOME_SCIENTIFIC_DEFINITION_DRIFT_CORRECTION
OUTCOMES_INSPECTED_BEFORE_AMENDMENT = false
OLD_PREREG_CONTENT_HEAD = b21bf46dcc39a2b9243c4172f731cd4d3fbf79b1
OLD_FREEZE_HEAD = 5f14411abc926a2b486d83de5b696ec3cf362488
AMENDED_PREREG_CONTENT_HEAD = b4459ab96addd6c39d4baec35248410a8f5cf8e0
AMENDED_PREREG_MD_SHA256 = 55f6f3525a4a3a5878f870a757e890faba336e8d944f6b751087a68e94102d06
AMENDED_PREREG_JSON_SHA256 = 191dfcf48996953f5c78873eb54b24e88430dea2307f22adb6120be4e893c7ae
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
NEXT_UNIT = MARKET_06_IMPLEMENTATION_OUTCOME_BLIND
```

Evidence: `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_001.md`
and `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md`.

## 2026-09-21 — MARKET-06 pre-outcome amendment 002 and re-freeze

Legal pre-outcome correction of predictive-bootstrap sampling structure.
Independent circular moving-block resampling of 2023 and 2024 holdouts
(block length 14; wrap within year only; exact N_year preserved;
concatenate after sampling). Amendment 001 F1–F4 and V0/V1 remain
historical evidence. No evaluator, ARM, RESULT, or outcome inspection.

```text
AMENDMENT_REASON = PRE_OUTCOME_PREDICTIVE_BOOTSTRAP_STRATIFICATION_CORRECTION
OUTCOMES_INSPECTED_BEFORE_AMENDMENT = false
OLD_LIVE_PREREG_HEAD = b4459ab96addd6c39d4baec35248410a8f5cf8e0
OLD_LIVE_FREEZE_HEAD = 371f71dd49e2c2c445269aeed1b75a39f33b3422
AMENDED_002_PREREG_HEAD = 6342d24e6d872b6dbce91f9cdb8e7cfe689a6f59
AMENDED_002_PREREG_TREE = 11658516cab22774501daa8e2e966c9a8861c9a3
PREREG_MD_SHA256 = 70dd8d09e07e1209e77ea6d1c741e412534ef5cccbfc36609bc46924e13cc4c6
PREREG_JSON_SHA256 = f60bf0bdbeb5982933c648b1c9b56017f25a5dabb29ad39eac58d53b5f590a24
PREDICTIVE_BOOTSTRAP_STRATIFIED_BY_YEAR = true
CROSS_YEAR_BOOTSTRAP_BLOCKS_ALLOWED = false
YEAR_SAMPLE_SIZE_PRESERVED_PER_REPLICATE = true
PREDICTIVE_MODEL_REFIT_IN_BOOTSTRAP = false
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
NEXT_UNIT = MARKET_06_IMPLEMENTATION_OUTCOME_BLIND
```

Evidence: `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_AMENDMENT_002.md`
and `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_PREREG_FREEZE.md`.

## 2026-09-21 — MARKET-06 outcome-blind implementation freeze

Implemented the frozen amendment-002 MARKET-06 contract. Canonical
evaluation of retained 2022-2024 bytes is refused. Synthetic tests only.
No ARM, RESULT, or outcome inspection.

```text
IMPLEMENTATION_ID = MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION
PREREG_FREEZE_HEAD = e2d543eadb5425473b6d4b8d24c177c1d7ae7930
IMPLEMENTATION_HEAD = 81c8e0a8619190329971f5a85435c7ac4f9cb86e
IMPLEMENTATION_TREE = 7f4e0a85dc3738924eb52bb28f85794d6a8daa7a
REAL_CANONICAL_EXECUTION_REFUSED = true
SCIENTIFIC_OUTCOMES_INSPECTED = false
MARKET_06_EXECUTED = false
MARKET_06_ARMED = false
NEXT_UNIT = MARKET_06_IMPLEMENTATION_RED_TEAM_REVIEW
```

Evidence: `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION.md`
and `docs/research/MARKET_06_CROSS_VENUE_DISLOCATION_IMPLEMENTATION_FREEZE.md`.


## 2026-09-21 — MARKET-06 canonical execution consumed, sealed NO_EVIDENCE

The one canonical historical MARKET-06 run executed exactly once on the
designated canonical checkout through the frozen production runner, under
the tracked authority chain claim `6d28144` -> reservation `de47896` ->
ARM `2d58157` -> implementation freeze `a832252`.

Research ID: `MARKET-06_CROSS_VENUE_DISLOCATION_ADVERSE_PATH_RISK`.

`FINAL_CLASSIFICATION = MARKET_06_NO_EVIDENCE`.
`RESULT_COMMIT = 80c7d19f622cc7b5576154de59dbb9cdf85d4dcf`.
`RESULT_PAYLOAD_SHA256 = 67f6f14c9221d3d0be2c130938f6ff8588aadc6eabc52126dd00a5fbbedd2a53`.
`run_identity = f3aa51372594d710a8f705d761d857f8385d0b848fb0ed59a36b27a16ce25c22`.

Absolute BTC perpetual-vs-spot cross-venue dislocation, conditional on
BTC's own recent directional and volatility state, did not provide stable
incremental information about subsequent 24h direction-aligned
adverse-path risk under the frozen design. Only G1 passed; G2-G6 failed.
Pooled relative MAE improvement -0.0376 (CI95 [-0.0645, -0.0149]); 2023
-0.0281; 2024 -0.0453. No reverse effect is inferred and no rescue is
authorized.

CONSUMED: the 2022 TRAIN and 2023/2024 holdout windows of
`MARKET_06_OKX_BINANCE_FEASIBILITY_V0` (snapshot `e0403e40...`) are spent
for the 24h direction-aligned MAE target. N_TRAIN=333, N_2023=364,
N_2024=365. Protected 2025/2026 remain unopened.

Program update `MARKET_PROGRAM_UPDATE_POST_M06` marks the narrow cell
"single standalone observable -> additive linear term -> mean 24h
direction-aligned MAE on a daily grid" as LOW_PRIORITY/SATURATED_FOR_NOW,
on the basis that three materially different information sources
(derivative positioning, cross-asset, cross-venue) produced nulls at the
same cell. The underlying information families are NOT disproven. Six
orthogonal, deliberately unranked candidate regions are recorded for
coverage.

- `INTERNAL_HISTORICAL_CANDIDATES_PROMOTED = 0`
- `MARKET_07_CREATED = false`
- next required step: `MARKET_NEXT_HYPOTHESIS_SELECTION_FROM_ORTHOGONAL_REGIONS`

## 2026-09-21 — MARKET next-hypothesis selection from orthogonal regions

Selection / search-space design only. No hypothesis preregistered, no
MARKET-07 created, no scientific outcome computed, protected 2025/2026
unopened.

`REGION_SELECTED = R-A / STRUCTURAL_REGIME_STATE_DETECTION`.
`SELECTION_STATUS = REGION_SELECTED_NOT_HYPOTHESIS_CREATED`. The selection
is provisional until a defensible lower-order null model and one low-DoF
state-construction class can both be defined outcome-blind.

Two corrections were recorded before selection.

RETRACTION: an earlier draft claimed 2020-2021 was an unconsumed/fresh
surface because MARKET-06 used only 2022-2024. That is FALSE. H01 and H02
used a 2020-02-01 -> 2025-01-01 development window with adaptation
allowed (21 documents reference it), and MARKET-01's common legal period
starts 2020-09-01 with era splits through 2024/2025. CONSUMED/EXPOSED:
2020-2024 is a historically exposed and adapted program research surface,
carrying both adaptive discovery exposure (H/BATCH work) and confirmatory
consumption (MARKET-01, MARKET-02, MARKET-05, MARKET-06). It remains usable
for exploration, mechanism feasibility and implementation development, but
not as fresh independent confirmation. A chronological split inside
2020-2024 must be described as "chronological held-out evaluation on
historically exposed research data", never as out-of-sample or independent
confirmation.

CORRECTION: the claim that MARKET-01..06 were all scalar prediction is
withdrawn. MARKET-03 is an external public-strategy reproduction scored on
the author's Max drawdown direction; MARKET-04/04H was never executed. The
defensible statement is that internal hypothesis GENERATION was
overconcentrated in short-horizon conditional scalar prediction, namely
MARKET-01/02/05/06 plus earlier H/B2 work.

R-A's closure scope is narrow: a negative result closes only the tested
class of low-dimensional, price-derived, discrete state representations at
the frozen time scale and construction procedure. It does not close
continuous conditioning (which MARKET-01/02/05/06 actually used), other
state constructions, other time scales, cross-sectional structure,
order-book regimes, latent states outside CORE BTC, or "BTC regimes"
generally.

The binding scientific risk is the null model: a surrogate preserving only
marginal distribution and linear autocorrelation can mechanically destroy
the second-order dependence under test and manufacture a guaranteed
positive contrast. The null must preserve every lower-order structure not
being claimed as regime structure and must be chosen outcome-blind.

Evidence: `docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.json`,
`docs/research/MARKET_NEXT_HYPOTHESIS_SELECTION.md`.

- `MARKET_07_CREATED = false`
- `INTERNAL_HISTORICAL_CANDIDATES_PROMOTED = 0`
- next required step: `STRUCTURAL_REGIME_STATE_DETECTION_MECHANISM_CLASS_AND_NULL_MODEL_FEASIBILITY`

## 2026-09-21 — Hypothesis Discovery Pipeline V2 (program pivot, research-process redesign)

`HYPOTHESIS_DISCOVERY_PIPELINE_V2` is a research-process redesign, not a
market hypothesis. It does not create MARKET-07, does not preregister R-A
or any other region, does not open protected 2025/2026, and does not
execute a confirmatory experiment. It is recorded as a new commit on
`research/post-m06-orthogonal-region-selection`, after and without
rewriting commit `a711086c36eb7129fc3f0660732049de93dd1629`, which remains
the valid historical record of the orthogonal-region selection.

`ORTHOGONAL_REGION_SELECTION_PRESERVED = true`.
`R_A_SELECTION_RETRACTED = false`. `R_A_SOLE_NEXT_PATH_SUPERSEDED = true`.

Reason: Signalbot has strong falsification/validation machinery (frozen
preregistration, ARM/claim/one-shot execution, sealed RESULT, red-team
hardening), but `INTERNAL_PROMISING_PROTOTYPES = 0`. Every internally
generated MARKET hypothesis executed so far (MARKET-01, 02, 05, 06)
returned `NO_EVIDENCE` at the confirmatory stage; MARKET-03 is an EXTERNAL
public-strategy reproduction and must not be counted as internal discovery.
This does not support routing R-A directly into another single
confirmatory attempt. It supports first testing whether the internal
discovery/generation process itself can produce a promising prototype at
all, across several orthogonal mechanism regions, before committing
further confirmatory-lifecycle cost to any one of them.

R-A is reclassified as `DISCOVERY_SPRINT_01 / D1 =
STRUCTURAL_STATE_DETECTION`: not MARKET-07, not yet a confirmatory
hypothesis. Its null-model/surrogate risk from the selection unit carries
over unchanged.

CORRECTION (supersession, not a rewrite of a711086): a711086 stated that
R-B and R-F "need a fresh evaluation surface that does not exist." That
statement is correct and unchanged for CONFIRMATORY use. It is now
explicitly scoped to confirmatory use only:
`DISCOVERY_FEASIBILITY != CONFIRMATORY_FEASIBILITY`. R-B may be explored on
historically exposed 2020-2024 data under adaptive discovery (card D2); any
resulting pattern remains exploratory and requires an independent future
confirmation surface. R-F may be explored only under a tightly bounded,
pre-frozen search surface (card D5), with its HIGH rescue/multiple-testing
risk explicitly recorded, never minimized by relabelling it "discovery."

Three stages are defined: `ADAPTIVE_DISCOVERY` (outcome-inspecting,
explicitly not independent evidence/OOS/confirmation/validation, data
labelled `ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA`, allowed
terminal states `PROMISING_PROTOTYPE` / `NO_USEFUL_STRUCTURE` /
`INCONCLUSIVE_DISCOVERY` / `INVALID_DISCOVERY`) -> `PROMISING_PROTOTYPE`
(a discovery-stage filter outcome, not confirmatory evidence, granting only
eligibility to be *proposed* for a future confirmatory unit) ->
`CONFIRMATORY_RESEARCH` (the existing unchanged heavy MARKET-0X lifecycle).

`DISCOVERY_SPRINT_01` defines exactly six discovery cards, none executed:
D1 `STRUCTURAL_STATE_DETECTION` (= R-A), D2
`CONDITIONAL_ABSTENTION_TAIL_RISK` (exploratory R-B), D3 `PATH_MORPHOLOGY`,
D4 `BTC_ETH_RELATIVE_STRUCTURE` (two-asset precursor, not cross-sectional
panel evidence), D5 `COMPOSED_DECISION_MECHANISM` (bounded exploratory R-F,
HIGH rescue risk recorded), D6 `EXTERNAL_MECHANISM_BENCHMARK` (diagnostic
only; never counted as internal discovery, exactly like MARKET-03). Plus
one non-card, outcome-blind sidecar, `CROSS_SECTIONAL_PANEL_FEASIBILITY`
(no signal/outcome statistics).

A Promising Prototype Gate disqualifies: one magic cell, one isolated year,
negligible practical magnitude, worse than a trivial baseline,
leakage/mechanical artifact, or the product of a large hidden search
surface. A program diagnostic tracks `INTERNAL_DISCOVERY_CARDS`,
`INTERNAL_PROMISING_PROTOTYPES`, `EXTERNAL_BENCHMARK_CARDS`,
`EXTERNAL_PROMISING_OR_REPRODUCED` diagnostically, never as a formal
success probability; after 6-10 materially orthogonal internal cards with
`INTERNAL_PROMISING_PROTOTYPES == 0`, `INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED
= true` must be recorded and a program-level decision made before another
batch, never simply more nearby variants.

Evidence: `docs/research/HYPOTHESIS_DISCOVERY_PIPELINE_V2.{json,md}`,
`docs/research/DISCOVERY_SPRINT_01.{json,md}`.

- `MARKET_07_CREATED = false`
- `SCIENTIFIC_OUTCOMES_COMPUTED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `DISCOVERY_SPRINT_01_CARD_EXECUTION`

## 2026-09-21 — Discovery Sprint 01 pre-outcome design corrections (D2/D3/D5/D6)

A narrow corrective unit, before any card execution, no scientific outcome
computed: D2's primary comparator corrected to
`RATE_MATCHED_RANDOM_ABSTENTION` (a random abstention control matched in
rate and temporal composition to the candidate rule; the never-abstain/
unconditional distribution demoted to a secondary reference only). D3
marked not executable until exactly one prior-state descriptor (or an
explicit unconditional design) is frozen outcome-blind. D5 marked not
executable with adaptively-selected components: its two components,
parameterization, and composition operator must be frozen without
reference to D1-D4 outcomes, or the card must be deferred. D6 marked not
executable until one external/public source (identity, mechanism, target,
comparator) is pinned before inspecting its reproduction outcome.
`INTERNAL_DISCOVERY_CARDS` / `EXTERNAL_BENCHMARK_CARDS` renamed to
`*_PLANNED`; D6 explicitly excluded from the 6-10 internal-card stall
rule, so Sprint 01 alone (5 internal cards) cannot trigger
`INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED`; an interim
`INTERNAL_DISCOVERY_WARNING = ZERO_PROMISING_AFTER_FIRST_5_INTERNAL_CARDS`
state was introduced below the formal 6-card gate.

Evidence: `docs/research/DISCOVERY_SPRINT_01.{json,md}`.

- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `DISCOVERY_SPRINT_01_CARD_EXECUTION`

## 2026-09-21 — Discovery Sprint 01 spec compilation (outcome-blind)

`DISCOVERY_SPRINT_01_SPEC_COMPILATION` is the final outcome-blind
compilation step before Discovery Sprint 01 scientific outcomes are
inspected. Each of D1-D6 was converted into either an
`EXECUTABLE_DISCOVERY_SPEC` (fully frozen parameters) or `DEFERRED`. All
six were made `EXECUTABLE_DISCOVERY_SPEC`; none was deferred. No discovery
outcome was computed and no candidate performance was inspected while
compiling these specs. No confirmatory machinery (ARM, claim/reservation,
one-shot execution authority, MARKET-style prereg lifecycle) was
introduced.

For each executable card the unit freezes: exact dataset authority (with
`CORE_BTC_BINANCE_V0` / `CORE_ETH_BINANCE_V0` snapshot IDs), exact
historical discovery interval (capped before 2025-01-01 to keep protected
2025/2026 unopened regardless of what the underlying materialized
snapshots contain), exact unit of observation, exact feature/state/rule
definitions, exact small search surfaces, exact target/functionals, exact
simple baselines/controls, exact temporal breakdowns, lightweight
`PROMISING_PROTOTYPE` evaluation fields, and deterministic seeds. D1 froze
a GARCH(1,1)-filtered block-bootstrap surrogate null (reused by D3). D2
froze its two abstention rules and the exact
`RATE_MATCHED_RANDOM_ABSTENTION` construction. D3 chose the
`UNCONDITIONAL_DESIGN` fallback outcome-blind rather than a new,
unreviewed prior-state descriptor. D5's two components (D2's own rules)
and OR composition operator were justified on structural-availability
grounds, since zero D1-D4 outcomes exist anywhere at compile time. D6
pinned the publicly documented "Pi Cycle Top Indicator" (111-day vs.
2x350-day SMA crossover) before any reproduction, with its data-coverage
limitation (2013/2017 coincidences predate `CORE_BTC_BINANCE_V0`) recorded
explicitly. The `CROSS_SECTIONAL_PANEL_FEASIBILITY` sidecar's spec was
finalized (methods only, no answers).

Evidence: `docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`.

- `EXECUTABLE_DISCOVERY_SPEC_COUNT = 6` (D1-D6)
- `DEFERRED_COUNT = 0`
- `SCIENTIFIC_OUTCOMES_COMPUTED = false`
- `CANDIDATE_PERFORMANCE_INSPECTED = false`
- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `DISCOVERY_SPRINT_01_EXECUTION`

## 2026-09-21 — Discovery Sprint 01 red-team review (outcome-blind)

`DISCOVERY_SPRINT_01_RED_TEAM_REVIEW` (reviewed commit
`7bb92b0bd6238693164b6592c0711fa4c15fc9fe`) checked whether each frozen
`DISCOVERY_SPRINT_01_SPEC_COMPILATION` spec was actually scientifically
and mechanically executable, not merely well-worded. No card was
executed; no candidate performance was inspected; protected 2025/2026
remained unopened; no MARKET-07 was created. The review was explicitly
authorized to demote any card from `EXECUTABLE_DISCOVERY_SPEC` and did
not optimize for keeping all six executable.

Seven suspected defects were reviewed against the actual frozen
MARKET-06 code and artifacts:

- **F1 CONFIRMED and FIXED** — D2's `DISLOCATION_ABSTENTION` rule and D5
  use `ev.robust_dislocation_z`, which requires cross-venue Binance-perp +
  OKX-spot data (`MARKET_06_OKX_BINANCE_FEASIBILITY_V0`, snapshot
  `e0403e40...183e68`), verified available only for `[2022-01-01,
  2025-01-01)` (frozen prereg `RAW_WINDOW`), not 2020-2021. D2's RV-only
  rule (`ev.rv_btc_24h`, `CORE_BTC_BINANCE_V0` only) is unaffected and
  keeps 2020-02-01 -> 2025-01-01. D2's dislocation rule and D5 are
  restricted to 2022-02-01T00:05:00Z -> 2025-01-01T00:00:00Z (reusing the
  frozen MARKET-06 `TRAIN_START_T` verbatim), with the cross-venue dataset
  authority bound explicitly. No 2020-2021 dislocation data is fabricated.
- **F2 CONFIRMED (underspecification) and FIXED** — D2/D5's base exposure
  schedule, direction determination (`sign(ev.btc_ret_24h)`), legal
  knowledge time, and severity metric (`ev.arithmetic_mae`) made explicit,
  reusing MARKET-05/06's frozen construction verbatim.
- **F3 CONFIRMED mechanically broken as written and FIXED** — D1's daily
  GARCH(1,1) null produces one scalar return per day and cannot generate
  D3's required 288x5m intraday path. Replaced with a new native-5m
  pooled circular block-bootstrap null, not an arbitrary intraday bridge.
- **F4 CONFIRMED and FIXED** — the paired contiguous block-bootstrap null
  preserves the true BTC(t)->ETH(t+1) relationship inside every block,
  making it inadequate for `LEAD_LAG_1DAY` specifically.
  `ROLLING_CORRELATION_90D` retains the paired null under a separate
  justification; `LEAD_LAG_1DAY` gets an independent-block-bootstrap null
  that destroys the true cross-series pairing by construction.
- **F5 CONFIRMED as an unverified assertion** — D1's GARCH(1,1)
  defensibility had been asserted, not checked. A `D1_NULL_ADEQUACY_GATE`
  is now defined against six non-target summary statistics (return
  marginal/tails, return ACF, short-lag vs. long-lag absolute-return ACF,
  leverage/asymmetry, RV_20 distribution) that must never use
  `MEAN_STATE_RUN_LENGTH` or the state labels. The gate has not been
  executed (no data was loaded in this review); D1 is blocked until it is
  run and passed.
- **F6 CONFIRMED and FIXED** — D1's `RV_20` was defined as a sum of
  already-square-rooted daily RV values (L1 aggregation), not conventional
  realized volatility, which requires variance-level (L2) aggregation.
  Corrected to `RV_20(t) = sqrt(sum of squared daily RV values)`.
- **F7 CONFIRMED partial defect plus a genuine usefulness problem** —
  D6's "Pi Cycle Top Indicator" mathematical definitions (local-max
  window, tie handling, multiple-crossover debounce) are now frozen, but
  its immutable source pin (archived URL + retrieval date) remains
  incomplete. Separately: `CORE_BTC_BINANCE_V0` begins 2020-01-01 while
  the source's own cited coincidences are 2013/2017/2021, leaving at most
  one testable historical episode -- judged to give the diagnostic
  essentially no statistical calibration power, by the same standard the
  Promising Prototype Gate applies elsewhere. D6 is deferred; a
  replacement external benchmark, selected without Signalbot outcome
  inspection, is required in a future unit.

Evidence: `docs/research/DISCOVERY_SPRINT_01_RED_TEAM_REVIEW.{json,md}`,
amendments layered into `docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`.

- `D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX`
- `D2_STATUS = D3_STATUS = D4_STATUS = D5_STATUS = EXECUTABLE_DISCOVERY_SPEC`
- `D6_STATUS = DEFERRED`
- `SCIENTIFIC_OUTCOMES_COMPUTED = false`
- `CANDIDATE_PERFORMANCE_INSPECTED = false`
- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- `EXECUTION_AUTHORIZED = PARTIAL (D2, D3, D4, D5 only)`
- next required step: `DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4_D5`,
  gated separately on `D1_NULL_ADEQUACY_GATE_EXECUTION` and
  `D6_REPLACEMENT_BENCHMARK_SELECTION`

## 2026-09-21 — Discovery Sprint 01 final pre-execution correction (D3, D4 only)

`DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4` (reviewed commit
`355a1657aac288fe75b272df1845fd9b5cfcac3f`) is a narrow, outcome-blind
follow-up to the red-team review, addressing D3 and D4 only; D1, D2, D5,
D6 are unchanged. No card was executed; no candidate performance was
inspected; protected 2025/2026 remained unopened; no MARKET-07 was
created.

**D3 — direction/native-path null semantics.** D3 was labeled
`UNCONDITIONAL_DESIGN` but its `MAX_ADVERSE_EXCURSION_24h` /
`TIME_TO_MAX_ADVERSE_EXCURSION` functionals were direction-aligned via
`BTC_SIDE(t)` (sign of the prior 24h return) -- a real, historically
informative quantity, not a neutral label. Of the three resolutions
considered (condition on the real shared `BTC_SIDE(t)`; generate a
surrogate pre-history to derive a surrogate `BTC_SIDE`; remove direction
alignment entirely), option C was selected outcome-blind: a real
directional-predictability effect (e.g. mean reversion) could make real
direction-aligned excursions differ from the null for reasons unrelated
to path shape, so any direction-conditioned design risked smuggling in
exactly the structure D1/D2/MARKET-01/02/05/06 already test. D3's
functionals are redefined unsigned: `MAX_UPSIDE_EXCURSION_24h`,
`MAX_DOWNSIDE_EXCURSION_24h`, `TIME_TO_MAX_EXCURSION`, `PATH_ASYMMETRY`,
with no `ev.btc_side_from_ret` dependency.

Separately, the first-round-corrected `5m_RETURN_POOLED_CIRCULAR_BLOCK_BOOTSTRAP`
null (from `DISCOVERY_SPRINT_01_RED_TEAM_REVIEW` F3) pools 5-minute
return blocks from anywhere in history, ignoring time-of-day. Because
every MARKET-06 decision point starts at the identical fixed UTC clock
time (`00:05:00Z`, per the frozen `is_forbidden_decision` check), bar
offset is structurally equivalent to UTC time-of-day for every
observation -- `TIME_TO_MAX_EXCURSION` is a time-of-day statistic, not
merely correlated with one. Ordinary session-based intraday volatility
seasonality would concentrate the real empirical distribution at
specific bar-offsets while a time-of-day-blind null smears it flat: a
near-certain confound, demonstrated structurally from the frozen
decision-grid design, not from any computed outcome. Corrected to
`5m_RETURN_TIME_OF_DAY_STRATIFIED_BLOCK_BOOTSTRAP`: the 288 bar-offsets
are partitioned into 24 fixed 1-hour slots, and each surrogate day's
per-slot block is drawn only from real historical blocks at that same
slot -- preserving the UTC time-of-day volatility profile in addition to
everything the original null preserved, while still destroying
date-specific conditioning and cross-slot dependency. `PATH_ASYMMETRY`
zero-denominator handling (row excluded from that functional only, not
the others), `TIME_TO_MAX_EXCURSION` tie handling (earliest bar-offset
wins), and the entry/reference convention (`entry_open =
ev.get_perp_bar_opening_at(perp, t_ms).open`, reused verbatim) were also
frozen. D3 remains `EXECUTABLE_DISCOVERY_SPEC`.

**D4 — lead-lag null still destroyed too much.** The prior
`INDEPENDENT_BLOCK_BOOTSTRAP` fix for `LEAD_LAG_1DAY` (independent draws
of the BTC and ETH series) destroys not only the true
`BTC(t)->ETH(t+1)` cross-lag but also ordinary same-time common-factor
dependence (shared crypto-market-wide moves), which is not the target
being tested -- no outcome-blind demonstration exists that it isolates
lead-lag specifically, and by construction it cannot, since independent
draws have zero built-in same-time dependence. Per the preferred minimal
resolution, no complex new lead-lag null (e.g. partial-correlation
controlling for contemporaneous co-movement) was invented merely to keep
both functionals: `LEAD_LAG_1DAY` is `DEFERRED_FROM_SPRINT_01` (its
definition retained as historical record, not deleted), while
`ROLLING_CORRELATION_90D` is retained unchanged with its paired-vector
block-bootstrap null. D4 remains `EXECUTABLE_DISCOVERY_SPEC`, scoped to
`ROLLING_CORRELATION_90D` only for Sprint 01 execution.

Evidence: `docs/research/DISCOVERY_SPRINT_01_PRE_EXECUTION_CORRECTION_D3_D4.{json,md}`,
amendments layered into `docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`.

- `D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX` (unchanged)
- `D2_STATUS = D3_STATUS = D5_STATUS = EXECUTABLE_DISCOVERY_SPEC`
- `D4_STATUS = EXECUTABLE_DISCOVERY_SPEC (ROLLING_CORRELATION_90D only)`
- `D4_ROLLING_CORRELATION_STATUS = EXECUTABLE_DISCOVERY_SPEC`
- `D4_LEAD_LAG_STATUS = DEFERRED_FROM_SPRINT_01`
- `D6_STATUS = DEFERRED` (unchanged)
- `SCIENTIFIC_OUTCOMES_COMPUTED = false`
- `CANDIDATE_PERFORMANCE_INSPECTED = false`
- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- `EXECUTION_AUTHORIZED_CARDS = D2, D3, D4 (ROLLING_CORRELATION_90D only), D5`
- next required step: `DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5`,
  gated separately on `D1_NULL_ADEQUACY_GATE_EXECUTION`,
  `D4_LEAD_LAG_REPLACEMENT_NULL_OR_PERMANENT_DEFERRAL`, and
  `D6_REPLACEMENT_BENCHMARK_SELECTION`

## 2026-09-21 — Discovery Sprint 01 final mechanical pre-execution fix (D3, D4, D5 only)

`DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX` (reviewed commit
`475072d22f4c4631836ca7d38ccdc5da6ce59222`) is a narrow, outcome-blind
mechanical correction addressing D3's real/null observable mismatch,
D4's practical-threshold exactness, and D5's component comparison; D1
and D6 unchanged. No card was executed; no scientific/candidate
performance was inspected; protected 2025/2026 remained unopened; no
MARKET-07 was created.

**D3 -- real/null observable mismatch.** D3's real functionals used 5m
bar HIGH/LOW values, but the frozen `5m_RETURN_TIME_OF_DAY_STRATIFIED_
BLOCK_BOOTSTRAP` surrogate generates only a synthetic close-to-close
log-return path -- it never synthesizes intra-bar high/low. Real and
surrogate were therefore not the same observable despite sharing
functional names. No synthetic high/low was invented. D3 is redefined
as CLOSE-PATH morphology so real and surrogate paths are mechanically
identical objects (a sequence of 288 5m close prices), with exactly
three functionals: `MAX_UPSIDE_CLOSE_24H = max(0, max_k((close_k -
entry_open)/entry_open))`, `MAX_DOWNSIDE_CLOSE_24H = max(0,
max_k((entry_open - close_k)/entry_open))`, and
`TIME_TO_MAX_ABS_CLOSE_EXCURSION` (earliest bar offset attaining the max
of the two). `PATH_ASYMMETRY` is removed from Sprint 01: the original
D3 card allowed at most 2-3 functionals, the prior correction round had
accidentally expanded the surface to 4 by adding it, and it is
derivative of the two excursion functionals anyway. Entry reference
(`entry_open = ev.get_perp_bar_opening_at(perp, t_ms).open`) and tie
handling (earliest bar offset wins) are unchanged from the prior
correction; the time-of-day-stratified bootstrap null itself is kept
unchanged, since it already generates exactly the close-path observable
this fix requires.

**D4 -- practical gate made exact.** `ROLLING_CORRELATION_90D`'s
practical magnitude threshold ("swings by at least 0.15
correlation-points beyond null-implied noise") was not mathematically
pinned. Corrected: `OBSERVED_CORRELATION_RANGE = max(real
rolling_corr_90d) - min(real rolling_corr_90d)`; `NULL_RANGE_MEDIAN =
median` over the 1000 bootstrap replicates of each replicate's own
`max - min` range; `PRACTICAL_EXCESS_RANGE = OBSERVED_CORRELATION_RANGE
- NULL_RANGE_MEDIAN`; practical gate `PRACTICAL_EXCESS_RANGE >= 0.15`.
The existing statistical variance-vs-null gate is retained unchanged
alongside this now-exact practical gate. `LEAD_LAG_1DAY` remains
`DEFERRED_FROM_SPRINT_01`.

**D5 -- common-window component comparison.** D5's own execution
interval is correctly restricted to `2022-02-01T00:05:00Z ->
2025-01-01T00:00:00Z` (bound by component_B/RULE_2's cross-venue data
availability), but D2 RULE_1 (component_A) reports its `DELTA` over its
own full `2020-02-01 -> 2025-01-01` interval -- comparing D5's `DELTA`
against RULE_1's full-interval result would not be apples-to-apples
(different N, different sub-periods/regimes). Frozen:
`COMPONENT_A_DELTA_FOR_D5` = D2 RULE_1 evaluated on the exact D5 common
interval (a second, narrower evaluation of RULE_1, solely as this
comparison's input); `COMPONENT_B_DELTA_FOR_D5` = D2 RULE_2 evaluated on
the same interval, which already coincides with RULE_2's own native
interval, so no additional computation is needed. `COMPOSED_BEATS_
COMPONENTS` iff `D5_DELTA > max(COMPONENT_A_DELTA_FOR_D5,
COMPONENT_B_DELTA_FOR_D5)`. D2 RULE_1's own broader 2020-2024 discovery
result is unaffected and may still be separately reported. This
overlap-window comparison is a pre-declared requirement specific to D5,
frozen outcome-blind, and must not be selected or adjusted after
observing any card's outcome.

Evidence: `docs/research/DISCOVERY_SPRINT_01_MECHANICAL_PRE_EXECUTION_FIX.{json,md}`,
amendments layered into `docs/research/DISCOVERY_SPRINT_01_SPEC_COMPILATION.{json,md}`.

- `D1_STATUS = BLOCKED_PENDING_PRE_OUTCOME_FIX` (unchanged)
- `D2_STATUS = D3_STATUS = D5_STATUS = EXECUTABLE_DISCOVERY_SPEC`
- `D4_STATUS = EXECUTABLE_DISCOVERY_SPEC (ROLLING_CORRELATION_90D only)`
- `D6_STATUS = DEFERRED` (unchanged)
- `SCIENTIFIC_OUTCOMES_COMPUTED = false`
- `CANDIDATE_PERFORMANCE_INSPECTED = false`
- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- `EXECUTION_AUTHORIZED = D2, D3, D4_ROLLING, D5`
- next required step: `DISCOVERY_SPRINT_01_PARTIAL_EXECUTION_D2_D3_D4ROLLING_D5`

## 2026-09-21 — Discovery Sprint 01 first partial batch (D2/D3/D4 rolling/D5)

Authorized adaptive-discovery batch executed on
`research/discovery-sprint-01-execution` from main `067231e`,
implementation commit `26d8f7066533bcae7138d5a1952783f2a16f3c39`.

Local data preflight: `BTC_DATA_PRESENT=false`, `ETH_DATA_PRESENT=false`,
`M06_CROSS_VENUE_DATA_PRESENT=true`. No download/re-materialization and
no snapshot substitution.

Classifications: D2/D3/D4/D5 all `BLOCKED_MISSING_LOCAL_DATA`. D2 RULE_2
was attempted on retained MARKET-06 durable raw; RULE_1/D3/D4/D5 could
not complete without CORE monthly parquet. D1 remains
`BLOCKED_PENDING_PRE_OUTCOME_FIX`. D4 `LEAD_LAG_1DAY` and D6 remain
deferred. MARKET-07 was not created. Protected 2025/2026 unopened.
`POST_OUTCOME_DESIGN_CHANGES = false`.

Program diagnostic recorded in result commit
`37921089ce289cd9bcbcebb123724a3e033dcdc3`:
`INTERNAL_DISCOVERY_CARDS_EXECUTED = 0`,
`INTERNAL_PROMISING_PROTOTYPES = 0`, interim warning
`ZERO_PROMISING_AFTER_FIRST_EXECUTED_INTERNAL_CARDS` with executed count
`0`. Formal `INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED` not
triggered.

**Bookkeeping correction (same first attempt, no scientific rerun):**
the `ZERO_PROMISING_AFTER_FIRST_EXECUTED_INTERNAL_CARDS` warning is
invalid while executed count is 0. Correct record:

- `INTERNAL_DISCOVERY_WARNING = null`
- `FULL_DISCOVERY_CARDS_COMPLETED = 0`
- `PARTIAL_COMPONENT_OUTCOME_OBSERVED = true`
- `PARTIAL_COMPONENT_OUTCOMES = ["D2/RULE_2/DISLOCATION_ABSTENTION"]`
- `PARTIAL_COMPONENT_OUTCOMES_OBSERVED = 1`
- `D2_RULE_2_DISCOVERY_OUTCOME_OBSERVED = true`
- `D2_RULE_2_GATE_PASS = false`
- D2 CARD remains `BLOCKED_MISSING_LOCAL_DATA` (RULE_1 not executable)
- RULE_2 is not counted as an executed internal card
- `POST_OUTCOME_DESIGN_CHANGES = false`

Evidence: `docs/research/discovery_results/`,
`docs/research/DISCOVERY_SPRINT_01.{json,md}`.

- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `DISCOVERY_SPRINT_01_RETRY_D2_D3_D4ROLLING_D5_WHEN_CORE_LOCAL_MATERIAL_PRESENT`

## 2026-09-21 — Discovery Sprint 01 CORE restore and frozen-batch retry

Legal 2020-2024 CORE BTC snapshot `717d37a4…` and CORE ETH snapshot
`4b9c113f…` monthly parquet was restored from frozen source URLs /
MARKET-05 ETH execution binding. 2025/2026 objects were not requested.
First blocked attempt remains preserved at
`docs/research/discovery_results/FIRST_ATTEMPT_BLOCKED_MISSING_LOCAL_DATA/`
(`FIRST_ATTEMPT_RESULT_COMMIT = 37921089ce289cd9bcbcebb123724a3e033dcdc3`).

Retry used scientific implementation
`26d8f7066533bcae7138d5a1952783f2a16f3c39`. D2 RULE_2 replayed the
first-attempt partial component exactly (`GATE_PASS=false`, eligible
1062). Completed-card classifications:

- D2 `PROMISING_PROTOTYPE` (RULE_1 `GATE_PASS=true`; RULE_2 remains fail)
- D3 `NO_USEFUL_STRUCTURE`
- D4 `NO_USEFUL_STRUCTURE` (`LEAD_LAG_1DAY` not executed)
- D5 `NO_USEFUL_STRUCTURE`

Adaptive discovery only; not confirmatory; no post-outcome design
changes. `INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`,
`INTERNAL_PROMISING_PROTOTYPES = 1`, `INTERNAL_DISCOVERY_WARNING = null`.
Formal stall gate not triggered. D1 remains
`BLOCKED_PENDING_PRE_OUTCOME_FIX`. D6 remains `DEFERRED`.

- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE_EXECUTION`

## 2026-09-21 — Discovery Sprint 01 D1 null-adequacy gate adjudication

Spec-level adjudication of `DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE`.
This is **not** D1 scientific execution. The gate was **not** run. No
`MEAN_STATE_RUN_LENGTH` / `HIGH_VOL_STATE` / `LOW_VOL_STATE` sequence
was computed. D2–D5 result bytes were not altered. Protected 2025/2026
was not opened. MARKET-07 was not created.

Check A (same observable): frozen D1 null fits GARCH(1,1)+Student-t to
one 24h BTC log-return per decision point, block-bootstraps standardized
daily residuals, and re-injects them through daily GARCH recursion to
produce a synthetic **daily 24h-return path**. Frozen D1 state uses
`ev.rv_btc_24h` from 288 × 5m intra-day log returns, with
`RV_20(t) = sqrt(sum_{i=0..19} [ev.rv_btc_24h(t-i)]^2)`. No
already-frozen mapping from the synthetic daily-return path onto
synthetic `ev.rv_btc_24h` / `RV_20` exists. F3 had already rejected an
arbitrary intraday bridge. Forbidden substitutes
(`abs(daily_return)`, GARCH sigma, squared daily return, synthetic
conditional variance) are not used.

```
D1_NULL_MODEL_OBSERVABLE_MISMATCH = true
D1_NULL_ADEQUACY_GATE_EXECUTED = false
D1_TARGET_OUTCOME_COMPUTED = false
D1_STATUS = DEFERRED_NULL_MODEL_OBSERVABLE_MISMATCH
```

Check B (independent): the frozen gate does not uniquely define the
leverage/asymmetry proxy, the RV_20 short-lag ACF lag set, lagwise
pass/fail, skewness/kurtosis joint vs individual evaluation, NaN /
degenerate treatment, or exact GARCH initialization / estimation
behavior.

```
D1_NULL_ADEQUACY_GATE_UNDERSPECIFIED = true
```

Why defer rather than repair: D2–D5 scientific outcomes are already
known. Sprint 01 specs were intended to be frozen before any card
outcome. A new D1 null or new gate definitions would be a
post-sibling-outcome redesign and must be a future D1-v2 card, not an
in-sprint repair.

Deferred D1 is not counted as executed.

- `INTERNAL_DISCOVERY_CARDS_EXECUTED = 4`
- `INTERNAL_PROMISING_PROTOTYPES = 1`
- `D2_STATUS = PROMISING_PROTOTYPE`
- `MARKET_07_CREATED = false`
- `PROTECTED_2025_OPENED = false`
- `PROTECTED_2026_OPENED = false`
- next required step: `D2_CONFIRMATION_FEASIBILITY_AND_DESIGN`

## 2026-09-21 — D2 RULE_1 confirmation feasibility and design

Outcome-blind confirmation design for the first internally generated
`PROMISING_PROTOTYPE`: `D2 / RULE_1 / RV_ABSTENTION` only. Confirmation
was not executed. 2025/2026 price values were not inspected. Protected
parquet was not materialized. MARKET-07 and ARM were not created. The
D2 discovery result was not mutated.

Proposed first independent surface: calendar 2025,
`FIRST_T = 2025-01-01T00:05:00Z`, `LAST_T = 2025-12-30T00:05:00Z`
(every 24h outcome contained in 2025; Dec 31 decision excluded).
2026 is recorded as `SECOND_RESERVED_SURFACE` and is not consumed.
Feature warmup may use exposed 2024 trailing-250 history.

Metadata-only CORE BTC snapshot `717d37a4…` binding: exactly 12 monthly
2025 objects, all `admitted_to_canonical`, checksum `VERIFIED`, parser
`OK`, source and canonical SHA256 bound. No 2026 object is needed for
the frozen interval.

Confirmatory estimand preserved: `RATE_MATCHED_RANDOM_ABSTENTION` with
the frozen year-matched convention (single-year 2025 reduces to uniform
K-subset). Statistical gate: `MU_RULE > P95` of 10000 replicates, seed
`D2_CONFIRMATION_RANDOM_CONTROL_SEED = 20260921120` frozen now.
Practical gate: `DELTA >= 0.20 * UNCONDITIONAL_MEAN` (not lowered; not
replaced by the discovery +1.42pp). Quarterly 2025 breakdowns are
diagnostic only.

Prospective power used only 2020-2024. Expected 2025 eligible N = 364,
expected abstain count = 39. Joint power at the predeclared 20%
relative effect = 0.006 vs minimum acceptable 0.80.

```
CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025
2025_OPEN_AUTHORIZED = false
MARKET_07_CREATED = false
ARM_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
```

Do not lower the 20% bar. Do not automatically consume 2026. A larger
genuinely fresh surface, or another independent equivalent surface, is
required before opening protected 2025.

Evidence: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`,
`docs/research_data/D2_CONFIRMATION_2025_METADATA_BINDING.json`.

- next required step: `D2_CONFIRMATION_LARGER_FRESH_SURFACE_OR_WAIT`

Evidence: `docs/research/DISCOVERY_SPRINT_01_D1_NULL_ADEQUACY_GATE.{json,md}`.

## 2026-09-21 — D2 confirmation power interpretation and size planning

Interpretation correction plus fresh-surface size planning for the same
frozen D2 RULE_1 confirmation design. Confirmation was not executed.
2025/2026 price values were not inspected. The D2 discovery result was
not mutated. Rule, target, comparator, P90 / trailing-250 / 24h
horizon, severity target, random-abstention comparator, 20% practical
gate, and P95 statistical gate are unchanged.

The original year-cycled one-year Monte Carlo is preserved:

```
ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011
ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT = 0.006
historical power_practical_gate at 20% = 0.499
```

Primary prospective criterion is now statistical power at a 20% true
effect (`>= 0.80`). Joint pass probability is diagnostic only.
`power_practical_gate ~= 0.5` at the exact 20% boundary is expected
and is not evidence of underpower. Because `0.011 << 0.80`,
`CONFIRMATION_FEASIBILITY` remains `UNDERPOWERED_SINGLE_YEAR_2025`.
This is not a scientific-design rescue.

Size planning used only exposed 2020-2024 empirical severity and the
frozen RULE_1 fireable rate (`K = round(rate * N)`), seed
`D2_CONFIRMATION_SIZE_PLANNING_SEED = 20260921122`:

```
N=364  K=39   STATISTICAL_POWER_AT_20PCT = 0.000
N=728  K=77   STATISTICAL_POWER_AT_20PCT = 0.903
N=1092 K=116  STATISTICAL_POWER_AT_20PCT = 1.000
N=1456 K=154  STATISTICAL_POWER_AT_20PCT = 1.000
MIN_REQUIRED_FRESH_DECISION_ROWS = 728
MIN_REQUIRED_FRESH_YEARS = 2
POTENTIAL_FUTURE_SURFACE = 2025_PLUS_FULL_2026
AUTHORIZED_TO_OPEN = false
```

Two independent years would meet the statistical-power bar. 2025 and
2026 remain unopened and are not automatically combined.

```
CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025
2025_OPEN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
RULE_CHANGED = false
TARGET_CHANGED = false
GATES_CHANGED = false
```

Evidence: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

- next required step: `D2_CONFIRMATION_WAIT_FOR_PREDECLARED_2025_PLUS_2026_WITHOUT_OPENING`

## 2026-09-21 — D2 dependence-preserving size planning

Repaired multi-year power planning for the same frozen D2 RULE_1
confirmation design. Confirmation was not executed. 2025/2026 price
values were not inspected. Rule, target, comparator, and gates are
unchanged. Original one-year powers remain:

```
ONE_YEAR_STATISTICAL_POWER_AT_20PCT = 0.011
ONE_YEAR_JOINT_PASS_PROBABILITY_AT_20PCT = 0.006
```

IID pooled-K two-year power `0.903` is preserved as
`SUPERSEDED_IID_SIZE_PLANNING` and is not authoritative.

Authoritative method: year-matched whole-year block resampling from
2021-2024 plus contiguous partial-year blocks; circular non-zero mask
shift; 20% effect injected vs expected year-matched control mean;
10000 year-matched inner replicates; seed `20260921123`.

```
POWER_N550 = 0.446
POWER_N575 = 0.473
POWER_N600 = 0.525
POWER_N625 = 0.545
POWER_N650 = 0.56
POWER_N675 = 0.59
POWER_N700 = 0.636
POWER_N728 = 0.64
THREE_YEAR = 1.0
FOUR_YEAR = 1.0
MIN_REQUIRED_FRESH_DECISION_ROWS = 1092
POTENTIAL_FUTURE_SURFACE = MORE_THAN_2025_PLUS_2026_OR_ALTERNATIVE_INDEPENDENT_SURFACE
AUTHORIZED_TO_OPEN = false
```

Two independent years remain below 0.80. Do not consume 2025+2026.
Full calendar 2026 is not currently available.

```
CONFIRMATION_FEASIBILITY = UNDERPOWERED_SINGLE_YEAR_2025
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
RULE_CHANGED = false
TARGET_CHANGED = false
GATES_CHANGED = false
```

Evidence: `docs/research/D2_CONFIRMATION_FEASIBILITY_AND_DESIGN.{json,md}`.

- next required step: `D2_CONFIRMATION_WAIT_FOR_3Y_INDEPENDENT_FRESH_SURFACE_OR_FIND_EQUIVALENT`

## 2026-09-21 — D2 alternative independent surface feasibility

Do not wait until 2027 as the default route. Outcome-blind feasibility of
replicating frozen `D2 / RULE_1 / RV_ABSTENTION` on a historical surface
Signalbot has never used for discovery or confirmation.

Refined year-matched power on exposed Binance 2020-2024 only (seed
`20260921124`; 728 and 1092 retained; 25-row coarse grid; one 5-row
local refinement between `N_BELOW=800` and `N_ABOVE=825`):

```
REFINED_MIN_REQUIRED_FRESH_DECISION_ROWS = 815
POWER_AT_REFINED_MIN_N = 0.801
POWER_95CI_AT_REFINED_MIN_N = [0.7751234971811168, 0.824572794210579]
POWER_USES_BINANCE_2025_2026 = false
POWER_USES_BITMEX_OUTCOMES = false
```

Primary candidate: official BitMEX XBTUSD inverse perpetual, 5m
`GET /api/v1/trade/bucketed`, timestamps = bucket end. Pre-2020 legal
decision rows (250-point warmup, 24h future fully before 2020-01-01,
Dec 31 excluded):

```
BITMEX_RAW_DATA_START = 2016-05-13T11:55:00Z
BITMEX_FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00Z
BITMEX_LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00Z
BITMEX_PRE2020_ELIGIBLE_N = 1069
missing_5m_buckets = 288 (2016-12-07 24h hole, warmup window)
BITMEX_CONTRACT_COMPATIBILITY = SCIENTIFICALLY_COMPARABLE_CROSS_VENUE
BITMEX_TEMPORAL_INDEPENDENCE_CLASS = PRE_2020_CROSS_VENUE_TEMPORAL_REPLICATION
```

D2 outcomes were not computed on BitMEX. Inverse PnL was not substituted
for arithmetic price-path MAE. 00:05 UTC clock preserved. Protected
Binance 2025/2026 unopened. MARKET-07 / ARM not created. Contemporaneous
venues were not pooled to inflate N.

```
CONFIRMATION_FEASIBILITY = FEASIBLE_PRE2020_BITMEX_CROSS_VENUE_TEMPORAL_REPLICATION
D2_OUTCOME_COMPUTED_ON_BITMEX = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
ARM_CREATED = false
```

Future evidence label if later executed:
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION` (not
`EXACT_BINANCE_CONFIRMATION`). Next unit is prereg freeze.

Evidence: `docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.{json,md}`,
`docs/research_data/D2_BITMEX_PRE2020_SOURCE_AUTHORITY.json`.

- next required step: `D2_BITMEX_REPLICATION_PREREG_FREEZE`

## 2026-09-21 — D2 BitMEX replication preregistration freeze

Outcome-blind freeze of the independent pre-2020 BitMEX XBTUSD
replication contract. Not executed. No MU_RULE, DELTA, candidate/control
severity, randomization p-value, or classification. Feasibility census
reproduced exactly under the sealed source authority and no-fill gap
rule.

```
PREREG_FROZEN = true
EVIDENCE_CLASS = INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION
INSTRUMENT = XBTUSD / FFWCSX inverse perpetual
FIRST_RULE_ELIGIBLE_T = 2017-01-24T00:05:00Z
LAST_RULE_ELIGIBLE_T = 2019-12-30T00:05:00Z
EXPECTED_ELIGIBLE_N = 1069
KNOWN_GAP_HANDLING = NO_FILL_NO_INTERPOLATION_NO_FORWARD_FILL_NO_SYNTHETIC
TRAILING_250_VALID_HISTORY_VERIFIED = true
REPLICATION_RANDOM_SEED = 20260921125
N_RANDOM_CONTROLS = 10000
STATISTICAL_GATE = MU_RULE > CONTROL_P95
PRACTICAL_GATE = DELTA >= 0.20 * UNCONDITIONAL_MEAN
PRIMARY_PASS_RULE = STATISTICAL_GATE and PRACTICAL_GATE
CLASSIFICATION_ASSIGNED = null
D2_BITMEX_OUTCOME_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
EXECUTION_AUTHORIZED = false
```

Use all 1069 legal rows. 815 remains a power floor, not a sampling cap.
Year-matched `K_y` inside 2017/2018/2019; pooled-K forbidden. Yearly
breakdowns are diagnostic only. Classification list frozen unassigned:
`SUPPORTED` / `NOT_SUPPORTED` / `INVALID`.

Evidence: `docs/research/D2_BITMEX_REPLICATION_PREREG.{json,md}`,
`docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json`.

- next required step: `D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`

## 2026-09-21 — D2 BitMEX replication implementation review

Outcome-blind implementation of the frozen BitMEX replication evaluator.
The prereg-bound evaluator SHA was a firewalled stub; this unit records
both that original identity and the reviewed execution implementation.
Synthetic tests cover rule, gates, year-matched controls, and
classification. Real BitMEX scientific execution is refused: no permit.

```
IMPLEMENTATION_REVIEW = PASS
EXECUTION_READY = true
EXECUTION_AUTHORIZED = false
EXPECTED_ELIGIBLE_N = 1069
D2_BITMEX_OUTCOME_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Evidence: `docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.{json,md}`,
`docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json`.

- next required step: `D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION`

## 2026-09-21 — D2 BitMEX replication one-shot execution

Canonical two-commit one-shot. Permit
`d23f48b0c49d28dfbd0bf55047cb0e3d6e2cc0f2` authorized execution without
outcomes. The scientific run reconstructed timestamp-legal `N=1069` but
constructed eligible rows were `N=1067` after frozen
`construct_discovery_row`. Sample-identity gate classified
`D2_BITMEX_REPLICATION_INVALID`. Primary MU_RULE / year-matched controls
were not computed. Not reinterpreted as `NOT_SUPPORTED`. No rerun.
Discovery history preserved. Protected 2025/2026 unopened. MARKET-07
not created.

```
CLASSIFICATION = D2_BITMEX_REPLICATION_INVALID
RUN_IDENTITY = b873d473e5d5ef1394d161d557b1e0ca7602bfa92e6d78d8e80df8f4d1493d71
PERMIT_COMMIT = d23f48b0c49d28dfbd0bf55047cb0e3d6e2cc0f2
RESULT_PAYLOAD_SHA256 = 9af98e72e7afc2c3e8af7f2d359401110e1e9c9829e69185ab23519e06fba48a
EVIDENCE_CLASS = INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION
CENSUS_ELIGIBLE_N = 1069
CONSTRUCTED_ELIGIBLE_N = 1067
FIRST_T = 2017-01-24T00:05:00Z
LAST_T = 2019-12-30T00:05:00Z
D2_BITMEX_OUTCOME_COMPUTED = false
RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
D2_DISCOVERY_STATUS = PROMISING_PROTOTYPE
```

Evidence: `docs/research/D2_BITMEX_REPLICATION_RESULT.{json,md}`,
`docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_PERMIT.json`,
`docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_BINDING.json`.

- next required step: `D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION`

## 2026-09-21 — D2 BitMEX replication integrity adjudication

The INVALID run is preserved. Diagnostic (no severity, no MU_RULE, no
controls) found exactly two timestamp-complete decisions dropped by
frozen `BTC_RET_24H_EQ_0`: `2018-03-17T00:05:00Z` and
`2019-02-10T00:05:00Z`. Adjudication class
`REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH`. Trailing-250
authority is `VALID_CONSTRUCTED_ROWS` from original D2 discovery.
Corrected eligible N=1067 > frozen floor 815; power was not recomputed.
Original rerun unauthorized. New integrity-repair `RUN_IDENTITY` minted.
No execution permit. 2025/2026 unopened. MARKET-07 not created.

```
ADJUDICATION_CLASS = REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH
DROPPED_1 = 2018-03-17T00:05:00Z BTC_RET_24H_EQ_0
DROPPED_2 = 2019-02-10T00:05:00Z BTC_RET_24H_EQ_0
SCIENTIFIC_ELIGIBLE_N = 1067
TRAILING_HISTORY_AUTHORITY = VALID_CONSTRUCTED_ROWS
ORIGINAL_PRIMARY_OUTCOME_COMPUTED = false
ORIGINAL_RANDOM_CONTROLS_COMPUTED = false
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = true
ORIGINAL_RERUN_AUTHORIZED = false
NEW_RUN_IDENTITY = 8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Evidence: `docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.{json,md}`,
`docs/research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.{json,md}`.

- next required step: `D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT`

## 2026-09-21 — D2 BitMEX corrected one-shot execution

Integrity-repair permit `14e9c9dfbfd6bdb989ef592b891aab1eb963f6f3` then
one scientific execution. Corrected identity constructed 1317 / warmup
250 / eligible 1067 (years 341/363/363). Two `BTC_RET_24H_EQ_0` drops
retained. Original INVALID run preserved. Frozen seed `20260921125`.
Classification `D2_BITMEX_REPLICATION_SUPPORTED`. Evidence label
`INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED`. Not
exact Binance confirmation, not proven alpha, not a validated trading
edge. No rerun. 2025/2026 unopened. MARKET-07 not created.

```
CLASSIFICATION = D2_BITMEX_REPLICATION_SUPPORTED
NEW_RUN_IDENTITY = 8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43
CORRECTED_RESULT_PAYLOAD_SHA256 = b7c53bf343936da652c987212575ade962e32c57cc1eed01907621c6f1ad4273
CONSTRUCTED_N = 1317
WARMUP_N = 250
ELIGIBLE_N = 1067
ABSTAIN_COUNT_TOTAL = 126
MU_RULE = 0.05374977245962498
MU_CONTROL_MEAN = 0.032765565858771904
DELTA = 0.020984206600853074
RELATIVE_DELTA = 0.67420960209053
STATISTICAL_GATE = true
PRACTICAL_GATE = true
PRIMARY_PASS = true
RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
```

Evidence: `docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.{json,md}`,
`docs/research_data/D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT.json`.

- next required step: `PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED`

## 2026-09-21 — Program decision after D2 BitMEX SUPPORTED

D2 is classified `INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE`. Discovery
claim and independent pre-2020 BitMEX replication claim are supported.
Market-mechanism claim is not yet supported (vol-clustering / MAE-scale
ambiguity remains). Trading-edge and product claims are not tested.
Binance 2025/2026 remain sealed. Hypothesis generation policy rotates
across families A–I; D2 neighbors forbidden. Product build remains frozen.
MARKET-07 not created. No D2 experiment was run in this unit.

```
D2_PROGRAM_CLASS = INDEPENDENTLY_REPLICATED_MECHANISM_CANDIDATE
JUSTIFIED_CLAIM = INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED
BINANCE_2025_2026_DECISION = KEEP_SEALED
PRODUCT_BUILD_FROZEN = true
HYPOTHESIS_GENERATION_POLICY_CHANGED = true
MARKET_07_CREATED = false
NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN
```

Evidence: `docs/research/PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED.{json,md}`.

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN`

## 2026-09-22 — D2 excess path-risk beyond vol-clustering design freeze

Outcome-blind post-replication mechanism-decomposition design. Selector
remains frozen D2 / RULE_1 / `RV_ABSTENTION` (P90, trailing-250, strict
`>`, t excluded). Primary target changes from MAE_SIDE to
`ADVERSE_SHARE = MAE_SIDE / (MAE_SIDE + MAE_OPPOSITE)` on the same 24h
path. Comparator is year-matched rate-matched random abstention,
`N_RANDOM_CONTROLS = 10000`, seed `20260922131` selected before outcome.
Gates frozen: statistical `MU_SHARE_RULE > CONTROL_SHARE_P95`; practical
`DELTA_SHARE >= 0.05`; temporal `DELTA_SHARE > 0` in at least 3 of 5
years. Evidence class
`POST_REPLICATION_MECHANISM_DECOMPOSITION_DISCOVERY`, not independent
confirmation. BitMEX 2017-2019 not reused for this new target. Protected
2025/2026 unopened. MARKET-07 not created. No real decomposition outcome.
`DESIGN_STATUS = FROZEN`.

```
DESIGN_STATUS = FROZEN
PRIMARY_SELECTOR = D2_RULE_1_RV_ABSTENTION
PRIMARY_TARGET = ADVERSE_SHARE
RANDOM_SEED = 20260922131
N_RANDOM_CONTROLS = 10000
D2_SELECTOR_CHANGED = false
HORIZON_CHANGED = false
RV_RULE_CHANGED = false
TARGET_CHANGED_FROM_ORIGINAL_D2 = true
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW
```

Evidence: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.{json,md}`.

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`

## 2026-09-22 — Pre-outcome year×SIDE comparator correction

Before any decomposition outcome, the design comparator was corrected from
year-only matching to `YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION`.
`ADVERSE_SHARE` is defined relative to frozen `SIDE`; year-only random
matching could confound a high-RV effect with LONG/SHORT composition.
Each replicate now preserves exact `K_{year,SIDE}` inside 2020–2024 ×
LONG/SHORT. Seed `20260922131` unchanged. Selector and target unchanged.
No real decomposition outcome. 2025/2026 unopened. BitMEX not reused.

```
PRIMARY_COMPARATOR = YEAR_SIDE_MATCHED_RATE_MATCHED_RANDOM_ABSTENTION
CONTROL_STRATA = calendar_year × frozen_SIDE
SIDE_MATCHING_ADDED = true
SELECTOR_CHANGED = false
TARGET_CHANGED = false
RANDOM_SEED_CHANGED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
```

Evidence: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_BEYOND_VOLATILITY_CLUSTERING_DESIGN.{json,md}`.

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`

## 2026-09-22 — D2 excess path-risk implementation and outcome-blind review

`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
implemented the frozen decomposition design and reviewed it
adversarially. **No scientific window was consumed and no decomposition
outcome was computed.** This entry records an implementation/review unit,
not evidence.

The frozen design was not redesigned. Selector, SIDE, primary target,
comparator, strata, seed, gates, thresholds and classification order are
imported from the frozen design module rather than reimplemented. The
only new mechanical work is future-path reconstruction: `DiscoveryRow`
stores `future_closes` only, so the evaluator re-walks the exact 288×5m
`PerpBar` sequence opening at `T..T+287*5m` and calls frozen
`arithmetic_mae` twice on that one shared sequence, then cross-checks
recomputed `MAE_SIDE` bit-for-bit against the frozen
`DiscoveryRow.severity`. A wrong window, a close-path substitution, or a
split SIDE/-SIDE path fails closed rather than producing a number.

Target ineligibility (`TARGET_ROW_INELIGIBLE_PATH_SCALE_NONPOSITIVE`, no
epsilon) never rebuilds the D2 selector: the candidate set is the
intersection of selector and target eligibility, and the dropped selector
count is reported per year.

Red-team classes F1–F20 (lookahead, wrong future window, closes instead
of high/low, split SIDE paths, selector drift, SIDE drift, target
ineligibility handling, pooled-K / year-only fallback, LONG/SHORT
composition mismatch, RNG/seed drift, replacement sampling, different
masks for share and scale, separate yearly control generation, future
information matching, gate/classification rescue, authority hash drift,
accidental real execution, protected 2025/2026 access, BitMEX reuse) all
returned `NOT_CONFIRMED`. Three non-blocking observations were recorded,
including that the frozen `STATISTICAL_GATE` strict `>` can be decided by
float noise at an exact tie — left unchanged, because the frozen design
already requires the practical and temporal gates as well.

No scientific ambiguity required a new researcher convention:
`SCIENTIFIC_AMBIGUITY_FOUND = false`.

```
IMPLEMENTATION_REVIEW               = PASS
EXECUTION_READY                     = true
EXECUTION_AUTHORIZED                = false
EXECUTION_PERMIT_CREATED            = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
CLASSIFICATION_ASSIGNED             = null
FROZEN_AUTHORITY_STATUS             = BOUND_NO_DRIFT
PROTECTED_2025_OPENED               = false
PROTECTED_2026_OPENED               = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
MARKET_07_CREATED                   = false
RESULT_CREATED                      = false
ARM_CREATED                         = false
```

Evidence: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.{json,md}`.

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION`
  (an explicit one-shot execution unit, requiring a future permit that
  binds the design hash, the review hash, the implementation hash, the
  CORE BTC snapshot and the recorded run identity)

## 2026-09-22 — D2 excess path-risk implementation-review integrity repair

Integrity/lifecycle repair of
`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW`
before merge. **No scientific window was consumed and no decomposition
outcome was computed.** Frozen scientific design bytes were not changed.

The prior review over-claimed `EXECUTION_READY = true` while
`execute_decomposition()` was only a terminal firewall stub and selector
identity was census-only. This repair:

- implements the full dormant canonical orchestration route (CORE BTC
  snapshot identity, `C.build_rows(perp, RULE1_INTERVAL_START,
  DISCOVERY_END)`, RULE_1 / RV selector, 288×5m PerpBar re-walk,
  MAE_SIDE severity cross-check, `evaluate_decomposition` with seed
  `20260922131` / `N=10000` / identity ON / severity ON), still
  impossible on real CORE because no permit exists;
- binds scientific authority to a tracked permit artifact rather than
  caller kwargs; no permit was created;
- adds exact ordered selector-identity machinery (SHA256 of ordered
  `t_ms` + selector flags) and wires a tracked selector-identity
  authority contract. The canonical route compares the reconstructed
  digest to that authority BEFORE `evaluate_decomposition`. The
  authority artifact is **not** created here
  (`CANONICAL_SELECTOR_DIGEST_FROZEN = false`) because the true digest
  cannot be obtained outcome-blind without opening real CORE BTC. The
  future freeze unit only writes those bytes;
- makes the inherited D2 P95 convention explicit:
  `CONTROL_P95_METHOD = NUMPY_LINEAR_INHERITED_FROM_D2`
  (`np.percentile(..., 95.0, method="linear")`).

```
IMPLEMENTATION_REVIEW                        = PASS
SCIENTIFIC_KERNEL_READY                      = true
CANONICAL_ORCHESTRATION_READY                = true
PERMIT_VERIFIER_READY                        = true
EXACT_SELECTOR_IDENTITY_IMPLEMENTED          = true
CANONICAL_SELECTOR_DIGEST_FROZEN             = false
SELECTOR_IDENTITY_AUTHORITY_CREATED          = false
EXECUTION_READY                              = false
EXECUTION_AUTHORIZED                         = false
EXECUTION_PERMIT_CREATED                     = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED          = false
CLASSIFICATION_ASSIGNED                      = null
PROTECTED_2025_OPENED                        = false
PROTECTED_2026_OPENED                        = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET       = false
MARKET_07_CREATED                            = false
RESULT_CREATED                               = false
ARM_CREATED                                  = false
```

Evidence: `docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_IMPLEMENTATION_REVIEW.{json,md}`.

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`
  (create/freeze the tracked selector-identity authority bytes only;
  do not alter the reviewed scientific execution implementation)

## 2026-09-22 — D2 excess path-risk selector identity census semantics

Correctness repair of selector-identity machinery on the implementation-review
unit. **No scientific window was consumed and no decomposition outcome was
computed.** Frozen scientific formulas, comparator, gates, seed, selector,
horizon, and target were not changed.

`FROZEN_RULE1_N = 1791` / year counts `334/364/364/364/365` are the
**constructed** RULE_1 population (`len(rows)` / `RULE_1_ROW_COUNT` /
`YEAR_BREAKDOWN.RULE_1` from frozen
`docs/research/discovery_results/D2_DISCOVERY_RESULT.json`, SHA
`42ee5d7d…`). They are **not** `mask.sum()`. Historical selector/abstain
census is frozen D2 `PRIMARY_METRICS.RV_ABSTENTION`: `ABSTAIN_COUNT = 163`,
year counts `10/48/32/23/50`. The future selector-identity authority schema
now binds both censuses. `RULE_1_N` remains a backwards-compatible alias
for constructed N. Canonical runtime
`CANONICAL_SELECTOR_DIGEST_FROZEN` is taken from the verified authority
(must be true); the implementation-review module constant stays `false`
because no authority artifact exists in this unit.

```
CANONICAL_SELECTOR_DIGEST_FROZEN             = false
SELECTOR_IDENTITY_AUTHORITY_CREATED          = false
EXECUTION_READY                              = false
EXECUTION_AUTHORIZED                         = false
EXECUTION_PERMIT_CREATED                     = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED          = false
PROTECTED_2025_OPENED                        = false
PROTECTED_2026_OPENED                        = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET       = false
MARKET_07_CREATED                            = false
RESULT_CREATED                               = false
```

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_PRE_OUTCOME_SELECTOR_DIGEST_FREEZE`

## 2026-09-22 — D2 excess path-risk pre-outcome selector digest freeze

Identity freeze only. Reconstructed frozen RULE_1 / RV_ABSTENTION from
legal `CORE_BTC_BINANCE_V0` 2020-2024 via `C.load_core_btc_5m` +
`C.build_rows` + `C.rv_abstention_mask`. Wrote tracked authority
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json`.
**No ADVERSE_SHARE, PATH_SCALE, evaluate_decomposition, permit, or RESULT.**

```
CANONICAL_SELECTOR_DIGEST =
  5eeb8480f8d1e576dec5e23f1a5545354c3d7b0fa16d76e6fbdbb89135b71f69
SELECTOR_IDENTITY_AUTHORITY_SHA256 =
  a982b316254ba54c4974512e0b19fa122a37f1744c8b0c49b2666046f352d13c
RULE_1_CONSTRUCTED_N = 1791
RULE_1_CONSTRUCTED_YEAR_N = 2020=334, 2021=364, 2022=364, 2023=364, 2024=365
SELECTOR_ABSTAIN_N = 163
SELECTOR_ABSTAIN_YEAR_N = 2020=10, 2021=48, 2022=32, 2023=23, 2024=50
CORE_BTC_SNAPSHOT_ID =
  717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
OPENED_FILE_COUNT = 60
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
EXECUTION_PERMIT_CREATED = false
RESULT_CREATED = false
IMPLEMENTATION_REVIEW_AT_TIME: CANONICAL_SELECTOR_DIGEST_FROZEN = false
CURRENT STATE: SELECTOR_IDENTITY_AUTHORITY = FROZEN
CURRENT STATE: CANONICAL_SELECTOR_DIGEST_FROZEN = true
MODULE CONSTANT CANONICAL_SELECTOR_DIGEST_FROZEN = false
```

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION`
  (not authorized by this freeze; no execution permit exists)

## 2026-09-22 — D2 excess path-risk pre-outcome selector digest freeze

Identity freeze only. Reconstructed frozen RULE_1 / RV_ABSTENTION from
legal `CORE_BTC_BINANCE_V0` 2020-2024 via `C.load_core_btc_5m` +
`C.build_rows` + `C.rv_abstention_mask`. Wrote tracked authority
`docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_SELECTOR_IDENTITY.json`.
**No ADVERSE_SHARE, PATH_SCALE, evaluate_decomposition, permit, or RESULT.**

```
CANONICAL_SELECTOR_DIGEST =
  5eeb8480f8d1e576dec5e23f1a5545354c3d7b0fa16d76e6fbdbb89135b71f69
SELECTOR_IDENTITY_AUTHORITY_SHA256 =
  a982b316254ba54c4974512e0b19fa122a37f1744c8b0c49b2666046f352d13c
RULE_1_CONSTRUCTED_N = 1791
RULE_1_CONSTRUCTED_YEAR_N = 2020=334, 2021=364, 2022=364, 2023=364, 2024=365
SELECTOR_ABSTAIN_N = 163
SELECTOR_ABSTAIN_YEAR_N = 2020=10, 2021=48, 2022=32, 2023=23, 2024=50
CORE_BTC_SNAPSHOT_ID =
  717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415
OPENED_FILE_COUNT = 60
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
EXECUTION_PERMIT_CREATED = false
RESULT_CREATED = false
IMPLEMENTATION_REVIEW_AT_TIME: CANONICAL_SELECTOR_DIGEST_FROZEN = false
CURRENT STATE: SELECTOR_IDENTITY_AUTHORITY = FROZEN
CURRENT STATE: CANONICAL_SELECTOR_DIGEST_FROZEN = true
MODULE CONSTANT CANONICAL_SELECTOR_DIGEST_FROZEN = false
```

- next required step: `D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION`
  (not authorized by this freeze; no execution permit exists)

## 2026-09-22 — D2 excess path-risk one-shot permit + runner (commit 1)

Outcome-blind permit commit only. Wrote tracked
`docs/research/D2_EXCESS_PATH_RISK_EXECUTION_PERMIT.json` from
`EV.tracked_permit_expected_authority` and added
`scripts/research/d2_excess_path_risk_one_shot.py`. **Did not execute
`EV.execute_decomposition`, did not open CORE BTC OHLC, did not compute
ADVERSE_SHARE / PATH_SCALE, did not create RESULT.**

```
SELECTOR_IDENTITY_AUTHORITY = FROZEN
EXECUTION_PERMIT_CREATED = true
EXECUTION_AUTHORIZED = true
ONE_SHOT = true
RERUN_AUTHORIZED = false
REAL_DECOMPOSITION_OUTCOME_COMPUTED = false
RESULT_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
MARKET_07_CREATED = false
NEXT_ACTION = EXECUTE_EXACT_PERMIT_COMMIT_ONCE
RUN_IDENTITY =
  bfe92af94df23d7aa6f3adc016dc6f558607d772977a1cc6613394ac9a92625f
DESIGN_JSON_SHA256 =
  485983701d6e05a57f7dc8bb578613467d6d8f6fb1ec1e28c68d7ca42767c75b
IMPLEMENTATION_REVIEW_JSON_SHA256 =
  3e26984e2dfd44764b1de32f4d4198c87dd1f413dead1d1a6b0f471188e9d60b
REVIEWED_EVALUATOR_SHA256 =
  24571cf3e37356133494e7abd756f59c8acf6e1b18a1e859648040c1d4dac3ee
SELECTOR_IDENTITY_AUTHORITY_SHA256 =
  a982b316254ba54c4974512e0b19fa122a37f1744c8b0c49b2666046f352d13c
CANONICAL_SELECTOR_DIGEST =
  5eeb8480f8d1e576dec5e23f1a5545354c3d7b0fa16d76e6fbdbb89135b71f69
```

- next required step: execute the exact permit commit once
  (`D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION`)

## 2026-09-22 — D2 excess path-risk canonical one-shot RESULT

Exact permit commit `29f83a102bd8ece2b078f65ef69a578a52812c7c` executed
once. Classification copied from the evaluator with no reinterpretation.

```
CLASSIFICATION = D2_VOLATILITY_SCALE_COMPATIBLE_NO_EXCESS_ALIGNMENT
PERMIT_COMMIT = 29f83a102bd8ece2b078f65ef69a578a52812c7c
RESULT_PAYLOAD_SHA256 =
  53ce2e20064671f5ae26c9174e77e52986fba8619263b3015143dce4aa874b81
N_CONSTRUCTED_ROWS = 1791
N_SELECTOR_ROWS = 163
N_TARGET_ELIGIBLE_ROWS = 1791
N_CANDIDATE_ROWS = 163
SELECTOR_ROWS_TARGET_INELIGIBLE_N = 0
STATISTICAL_GATE = false
PRACTICAL_GATE = false
TEMPORAL_GATE = true
PATH_SCALE_MATERIALLY_ELEVATED = true
REAL_DECOMPOSITION_OUTCOME_COMPUTED = true
RERUN_AUTHORIZED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = false
MARKET_07_CREATED = false
NEXT_UNIT = HETEROGENEOUS_FAMILY_ROTATION_V1
```

- next required step: continue orthogonal family rotation
  (`HETEROGENEOUS_FAMILY_ROTATION_V1`); do not rerun this one-shot

## 2026-09-22 — Heterogeneous family rotation V1 / Discovery Sprint 02 card definition

Outcome-blind card definition only. Applied frozen
`HETEROGENEOUS_FAMILY_ROTATION_V1`. Created exactly two internal
discovery cards. Did not execute D7/D8. Did not inspect scientific
outcomes. Did not open 2025/2026. Did not create MARKET-07. Did not
modify D2 RESULT / permit / selector / evaluator / design.

```
HETEROGENEOUS_FAMILY_ROTATION_V1 = FROZEN
DISCOVERY_SPRINT_02 = DEFINED
DISCOVERY_SPRINT_02_INTERNAL_CARDS = 2
D7 = KLINE_FLOW_IMPACT_STATE / FAMILY E / LIQUIDITY_EXECUTION_STATE
D8 = ENDOGENOUS_SHOCK_RECOVERY / FAMILY G / EVENT_RESPONSE_RECOVERY
D7_STATUS = DEFINED_NOT_EXECUTED
D8_STATUS = DEFINED_NOT_EXECUTED
D7_EXECUTED = false
D8_EXECUTED = false
F_STATUS = DEFERRED_BLOCKER_UNRESOLVED
H_STATUS = DEFERRED_DATA_LIMITATION
I_STATUS = DEFERRED_SOURCE_NOT_PINNED
A_B_C_D = NOT_SELECTED_THIS_ROTATION
DATA_LABEL = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
SCIENTIFIC_OUTCOMES_COMPUTED = false
MARKET_07_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
PRODUCT_BUILD_FROZEN = true
KLINE_PROXY_ONLY = true
NOT_ORDERBOOK_LIQUIDITY = true
NOT_REALIZED_SLIPPAGE = true
NO_EXOGENOUS_CALENDAR = true
NEXT_UNIT = DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION
```

Evidence: `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V1.{json,md}`,
`docs/research/DISCOVERY_SPRINT_02.{json,md}`.

- next required step: Sprint 02 non-outcome feasibility census,
  implementation, synthetic tests, and outcome-blind review
  (`DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION`); do not
  execute D7/D8 scientific outcomes automatically

## 2026-09-22 — D8 control-comparability and recovery-clock integrity repair

Outcome-blind design repair on the Sprint 02 card definition. D7
unchanged. D8 event thresholds (P99/P90, 720h, 6h target, overlap,
event-support philosophy) unchanged. No scientific outcomes.

```
D8_PRIMARY_BASELINE = RETURN_SHOCK_MATCHED_NON_HIGH_ACTIVITY_CONTROL
D8_CONTROLS_PASS_P99_RETURN_SHOCK = true
D8_CONTROLS_FAIL_ONLY_P90_VOLUME = true
D8_PRIMARY_P25_P50_P75_MAGNITUDE_BUCKETS = false
EVENT_DECISION_T = H + 1h
PROTECTED_BOUND_PRIMARY = EVENT_DECISION_T + 6h < 2025-01-01T00:00:00Z
PROTECTED_BOUND_STRICT = true
IF_INSUFFICIENT_CONTROLS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
NO_P99_WEAKENING_FOR_CONTROLS = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
D7_EXECUTED = false
D8_EXECUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_FEASIBILITY_AND_IMPLEMENTATION
```

- next required step still: Sprint 02 non-outcome feasibility and
  implementation; do not execute D7/D8 scientific outcomes automatically

## 2026-09-22 — Discovery Sprint 02 feasibility and implementation

Selector/support feasibility only on legal CORE BTC 2020-2024. Scientific
evaluators implemented as pure functions and not run on real data. D8
thresholds were not weakened after insufficient controls.

```
D7_IMPLEMENTATION_STATUS = OUTCOME_BLIND_READY
D8_IMPLEMENTATION_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D7_STATE_N = 4545
D8_RETAINED_EVENT_N = 408
D8_MATCHED_PAIR_N = 14
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE
```

Evidence: `docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.{json,md}`,
`docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.{json,md}`.

- next required step: bind reviewed implementation bytes, then D7
  scientific execution freeze only; do not execute D8; do not open
  2025/2026; do not create MARKET-07

## 2026-09-22 — Discovery Sprint 02 outcome-blind integrity hardening

Formalized tracked-snapshot full monthly exact-byte identity. Frozen D7
selector identity. D8 remains deferred and non-executable for this card.
Scientific outcomes were not computed. Protected years were not opened.

```
DATA_IDENTITY_MODE = TRACKED_SNAPSHOT_FULL_MONTHLY_EXACT_BYTE_VERIFICATION
RUNTIME_SNAPSHOT_MANIFEST_FOUND = false
FULL_MONTHLY_EXACT_BYTE_VERIFICATION = true
D7_SELECTOR_N = 4545
D7_SELECTOR_DIGEST = 8794fece9541c9b09f3ed83f09a9aaf8e4d1caf5df7c6fb8ef29ba6c54889b5b
D7_STATUS = OUTCOME_BLIND_READY
D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
D7_SCIENTIFIC_EXECUTION_ELIGIBLE = true
D8_SCIENTIFIC_EXECUTION_ELIGIBLE = false
D8_NOT_D8_NO_USEFUL_STRUCTURE = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE
NEXT_UNIT_SCOPE = D7_ONLY
```

- next required step: D7-only scientific execution freeze; do not
  execute D8; do not rescue D8 thresholds/controls; do not open
  2025/2026; do not create MARKET-07

## 2026-09-22 — Discovery Sprint 02 D7 scientific execution freeze

Outcome-blind freeze of the D7 one-shot route. Permit created.
Scientific outcomes were not computed. D8 remains non-executable.

```
D7_EXECUTION_AUTHORIZED = true
D7_EXECUTED = false
D8_EXECUTION_AUTHORIZED = false
D8_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION
```

- next required step: D7 one-shot scientific execution only; do not
  execute D8; do not open 2025/2026; do not create MARKET-07

## 2026-09-22 — Discovery Sprint 02 D7 execution-freeze integrity repair

Outcome-blind repair of PR #194. Bound one-shot runner bytes in the
tracked permit and replaced self-referential freeze HEAD/TREE with
`AUTHORITY_PARENT_COMMIT` / `AUTHORITY_PARENT_TREE`. Scientific outcomes
were not computed. D8 remains non-executable.

```
F1_RUNNER_BYTES_BOUND = true
PROVENANCE_MODEL = AUTHORITY_PARENT_PLUS_FILE_HASHES
D7_EXECUTION_AUTHORIZED = true
D7_EXECUTED = false
D8_EXECUTION_AUTHORIZED = false
D8_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION
```

- next required step remains D7 one-shot scientific execution only; do
  not execute D8; do not open 2025/2026; do not create MARKET-07

## 2026-09-22 — Discovery Sprint 02 D7 RESULT-persistence integrity repair

Outcome-blind repair of PR #194. Canonical one-shot RESULT persistence
now uses atomic final-path replacement and `RESULT_PAYLOAD_SHA256` over
canonical JSON excluding the digest field. Scientific outcomes were not
computed. D8 remains non-executable.

```
F3_RESULT_PERSISTENCE_DURABLE = true
RESULT_PAYLOAD_SHA256_IMPLEMENTED = true
D7_EXECUTED = false
D8_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION
```

- next required step remains D7 one-shot scientific execution only; do
  not execute D8; do not open 2025/2026; do not create MARKET-07

## 2026-09-22 — Discovery Sprint 02 D7 final pre-merge integrity repair

Outcome-blind repair of PR #194. Fail-closed git worktree / HEAD-blob
identity, consume tracked freeze as a pre-scientific authority, bind
year×RV strata maps, and add synthetic t/t+1 array semantics. Scientific
outcomes were not computed. D8 remains non-executable.

```
GIT_WORKTREE_FAIL_CLOSED = true
TRACKED_FREEZE_CONSUMED_AS_AUTHORITY = true
TARGET_ELIGIBLE_STRATA_BOUND = true
CANDIDATE_STRATA_BOUND = true
ANALYSIS_N = 42407
CANDIDATE_N = 4545
D7_EXECUTED = false
D8_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_02_D7_ONE_SHOT_SCIENTIFIC_EXECUTION
```

- next required step remains D7 one-shot scientific execution only; do
  not execute D8; do not open 2025/2026; do not create MARKET-07

## 2026-09-22 — Canonical D7 one-shot RESULT (consumed)

Canonical Discovery Sprint 02 D7 one-shot from execution root
`0f22d46ab0ee41be78cb45de39842c8a5684b54e`. RESULT commit
`6364670b61eed1e5215bb394b0ba67e8cd2619dd`, merged to main as
`9b25131e92ab654e46175ddba34e8cccc1db6765`. Called `execute_one_shot()`
exactly once. No retry.

```
D7_NAME = KLINE_FLOW_IMPACT_STATE
D7_FAMILY = E / LIQUIDITY_EXECUTION_STATE
D7_STATUS = PROMISING_PROTOTYPE
CLASSIFICATION = D7_PROMISING_PROTOTYPE
MU_D7_RULE = 0.18943894389438945
MU_D7_CONTROL = 0.09856569856985697
DELTA_D7 = 0.09087324532453248
CONTROL_D7_P95 = 0.10517051705170517
MC_P_D7 = 9.999000099990002e-05
STATISTICAL_GATE = true
PRACTICAL_GATE = true
TEMPORAL_GATE = true
YEARLY_DELTA_D7 = positive in all five years 2020–2024
ANALYSIS_N = 42407
CANDIDATE_N = 4545
RESULT_PAYLOAD_SHA256 = 7a7d38ef62630a9b1acac4af90d19a2abe5c7911681a7214fb1f22696fcab1e9
EVIDENCE_LABEL = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
NOT_INDEPENDENT_CONFIRMATION = true
NOT_PROVEN_ALPHA = true
NOT_VALIDATED_TRADING_EDGE = true
NOT_ORDERBOOK_LIQUIDITY_CLAIM = true
D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
RERUN_AUTHORIZED = false
```

D8 remains deferred and is not a negative scientific result. Do not
rerun D7. Do not execute D8. Do not treat D7 as proven alpha.

Evidence: `docs/research/DISCOVERY_SPRINT_02_D7_RESULT.{json,md}`.

## 2026-09-22 — Post-D7 program update and Discovery Sprint 03 selection

Program-level routing after D7. No new scientific outcome. Family
rotation V2 frozen. Exactly one Sprint 03 internal card defined,
not executed.

```
INTERNAL_DISCOVERY_CARDS_EXECUTED = 5
INTERNAL_PROMISING_PROTOTYPES = 2
INTERNAL_DISCOVERY_WARNING = null
INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = false
D7_STATUS = PROMISING_PROTOTYPE
D7_CONFIRMATION_CANDIDATE = true
D7_CONFIRMATION_SELECTED_NOW = false
D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
SPRINT03_D9 = DEFINED_NOT_EXECUTED
D9_NAME = VENUE_DISLOCATION_RESOLUTION_STRUCTURE
D9_FAMILY = H / CROSS_SECTIONAL_OR_VENUE_STRUCTURE
D9_SUBFAMILY = VENUE_STRUCTURE
D9_EXECUTED = false
D9_SCIENTIFIC_OUTCOME_COMPUTED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
RESEARCH_DATA_DURABILITY_V1_IMPLEMENTED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

Family E is in cooldown after D7. D9 studies who closes an extreme
Binance-perp vs OKX-spot 5m dislocation. It is not a MARKET-06 MAE
rescue and not a D7 neighbor. True cross-sectional panel remains
absent. CORE BTC gitignored parquet/raw bytes lack a verified durable
object-storage restore path; durability work is recorded, not
implemented here.

Evidence: `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.{json,md}`
and `docs/research/DISCOVERY_SPRINT_03.{json,md}`.

## 2026-09-22 — Canonical D7 one-shot RESULT (consumed)

Canonical Discovery Sprint 02 D7 one-shot from execution root
`0f22d46ab0ee41be78cb45de39842c8a5684b54e`. RESULT commit
`6364670b61eed1e5215bb394b0ba67e8cd2619dd`, merged to main as
`9b25131e92ab654e46175ddba34e8cccc1db6765`. Called `execute_one_shot()`
exactly once. No retry.

```
D7_NAME = KLINE_FLOW_IMPACT_STATE
D7_FAMILY = E / LIQUIDITY_EXECUTION_STATE
D7_STATUS = PROMISING_PROTOTYPE
CLASSIFICATION = D7_PROMISING_PROTOTYPE
MU_D7_RULE = 0.18943894389438945
MU_D7_CONTROL = 0.09856569856985697
DELTA_D7 = 0.09087324532453248
CONTROL_D7_P95 = 0.10517051705170517
MC_P_D7 = 9.999000099990002e-05
STATISTICAL_GATE = true
PRACTICAL_GATE = true
TEMPORAL_GATE = true
YEARLY_DELTA_D7 = positive in all five years 2020–2024
ANALYSIS_N = 42407
CANDIDATE_N = 4545
RESULT_PAYLOAD_SHA256 = 7a7d38ef62630a9b1acac4af90d19a2abe5c7911681a7214fb1f22696fcab1e9
EVIDENCE_LABEL = ADAPTIVE_DISCOVERY_ON_HISTORICALLY_EXPOSED_DATA
NOT_INDEPENDENT_CONFIRMATION = true
NOT_PROVEN_ALPHA = true
NOT_VALIDATED_TRADING_EDGE = true
NOT_ORDERBOOK_LIQUIDITY_CLAIM = true
D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
RERUN_AUTHORIZED = false
```

D8 remains deferred and is not a negative scientific result. Do not
rerun D7. Do not execute D8. Do not treat D7 as proven alpha.

Evidence: `docs/research/DISCOVERY_SPRINT_02_D7_RESULT.{json,md}`.

## 2026-09-22 — Post-D7 program update and Discovery Sprint 03 selection

Program-level routing after D7. No new scientific outcome. Family
rotation V2 frozen. Exactly one Sprint 03 internal card defined,
not executed.

```
INTERNAL_DISCOVERY_CARDS_EXECUTED = 5
INTERNAL_PROMISING_PROTOTYPES = 2
INTERNAL_DISCOVERY_WARNING = null
INTERNAL_HYPOTHESIS_GENERATION_NOT_DEMONSTRATED = false
D7_STATUS = PROMISING_PROTOTYPE
D7_CONFIRMATION_CANDIDATE = true
D7_CONFIRMATION_SELECTED_NOW = false
D8_STATUS = DEFERRED_INSUFFICIENT_CONTROL_SUPPORT
SPRINT03_D9 = DEFINED_NOT_EXECUTED
D9_NAME = VENUE_DISLOCATION_RESOLUTION_STRUCTURE
D9_FAMILY = H / CROSS_SECTIONAL_OR_VENUE_STRUCTURE
D9_SUBFAMILY = VENUE_STRUCTURE
D9_EXECUTED = false
D9_SCIENTIFIC_OUTCOME_COMPUTED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
RESEARCH_DATA_DURABILITY_V1_REQUIRED = true
RESEARCH_DATA_DURABILITY_V1_IMPLEMENTED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

Family E is in cooldown after D7. D9 studies who closes an extreme
Binance-perp vs OKX-spot 5m dislocation. It is not a MARKET-06 MAE
rescue and not a D7 neighbor. True cross-sectional panel remains
absent. CORE BTC gitignored parquet/raw bytes lack a verified durable
object-storage restore path; durability work is recorded, not
implemented here.

Evidence: `docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.{json,md}`
and `docs/research/DISCOVERY_SPRINT_03.{json,md}`.

## 2026-09-22 — Sprint 03 pre-outcome amendment (three cards + D9 algebra)

Pre-outcome correction of the first Sprint 03 freeze. Rebased onto
`origin/main` `35511b3` (PR #197; `SIGNALBOT_MANDATE_V1` canonical).
D7 RESULT and D8 deferred status unchanged. No scientific outcomes.

`MECHANISM_MEMORY_V0` maps H01–H05, B2-01–B2-06, MARKET-01–06, D1–D8
(`BATCH01_PROMOTED = 0/5`; MARKET-03 not internal discovery; B2-06 not
negative evidence). Six history-aware candidates were compared. Selected
three cards in three families:

```
INTERNAL_CARDS = D9, D10, D11
SELECTED_THIS_ROTATION = D, G, H
SPRINT03_SELECTION_INCOMPLETE = false
D9_NAME = VENUE_DISLOCATION_RESOLUTION_STRUCTURE
D9_FAMILY = H
D9_DATA_FEASIBILITY_CLASS = DATA_READY
D9_CHOSEN_ESTIMAND = RELATIVE_RESOLUTION_ATTRIBUTION
D9_PRIMARY_TARGET = PERP_RESOLUTION_SHARE
D9_ALGEBRAIC_IDENTIFICATION_FIXED = true
OLD_RESOLUTION_IMBALANCE_REJECTED = true
D10_NAME = BTC_ETH_RESIDUAL_SHOCK_PERSISTENCE
D10_FAMILY = D
D10_DATA_FEASIBILITY_CLASS = DATA_READY
D11_NAME = SCHEDULED_MACRO_EVENT_VOL_RESPONSE
D11_FAMILY = G
D11_DATA_FEASIBILITY_CLASS = ACQUIRABLE_FREE_HISTORICAL
D9_EXECUTED = false
D10_EXECUTED = false
D11_EXECUTED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

D9 algebra: `TOTAL_CLOSURE = -s*(rp-rs)`; `PERP_RESOLUTION_SHARE` only
if `TOTAL_CLOSURE>0`. `rp==rs` is ineligible. Widening is ineligible.
Estimand B (future consensus / price-discovery leadership) is rejected
on two synchronous 5m closes. Historical next-unit
`DISCOVERY_SPRINT_03_D9_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION`
is superseded by the batch unit above.

Evidence: `docs/research/MECHANISM_MEMORY_V0.{json,md}`,
`docs/research/HETEROGENEOUS_FAMILY_ROTATION_V2.{json,md}`,
and `docs/research/DISCOVERY_SPRINT_03.{json,md}`.

## 2026-09-22 — Sprint 03 pre-outcome tightening (D9 SHARE / D10 beta / D11 FOMC)

Narrow outcome-blind semantic freeze on PR #198. No scientific outcomes.
No new cards. Families remain H/D/G.

```
D9_SCIENTIFIC_CLAIM_MAY_ESTABLISH = CONDITIONAL_VENUE_RESOLUTION_ATTRIBUTION
D9_SHARE_NOT_CLIPPED = true
D9_SHARE_NOT_WINSORIZED = true
D9_SHARE_MAY_BE_OUTSIDE_UNIT_INTERVAL = true
D9_MUST_NOT_ESTABLISH = PRICE_DISCOVERY_LEADERSHIP / CAUSAL_LEADERSHIP / WHICH_VENUE_MOVED_FIRST
D10_FIXED_PRE_EVENT_BETA = true
D10_PRIMARY_TARGET = sign(e_t) * e_t_plus_1_fixed_beta
D10_MATCH = YEAR x sign(e_t) x |r_btc_t| trailing-quantile bucket + small |e_t|
D11_NAME = SCHEDULED_FOMC_EVENT_VOL_RESPONSE
D11_FOMC_ONLY = true
D11_MATCH = YEAR x WEEKDAY x UTC_HOUR
D11_DST = OFFICIAL_ANNOUNCEMENT_TIMESTAMP
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

Evidence: `docs/research/DISCOVERY_SPRINT_03.{json,md}`.

## 2026-09-22 — Sprint 03 batch feasibility and outcome-blind implementation

Brought D9/D10/D11 from `DEFINED_NOT_EXECUTED` to
`OUTCOME_BLIND_IMPLEMENTATION_READY`. Structural/data feasibility only.
No scientific outcomes. No classifications. No D7 rerun. No D8. No
MARKET-07. Protected 2025/2026 sealed.

```
D9_PRIMARY_LOCATION_STATISTIC = MEDIAN_PERP_RESOLUTION_SHARE
D9_EVENT_N = 8349
D9_CLOSING_EVENT_N = 7184
D9_CONTROL_N = 151167
D9_DATA_IDENTITY_VERIFIED = true
D10_REGRESSION_SPECIFICATION = NO_INTERCEPT_OLS
D10_EVENT_N = 4442
D10_MATCHED_CONTROL_N = 21368
D10_DATA_IDENTITY_VERIFIED = true
D11_OFFICIAL_SOURCE_PINNED = true
D11_EVENT_N = 39
D11_YEAR_COVERAGE = 2020,2021,2022,2023,2024
D11_CONTROL_N = 561
D11_MIN_CONTROLS_AMONG_EVENTS = 44
SCIENTIFIC_OUTCOMES_COMPUTED = false
D9_EXECUTED = false
D10_EXECUTED = false
D11_EXECUTED = false
EXECUTION_AUTHORIZED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_IMPLEMENTATION_RED_TEAM_AND_EXECUTION_DECISION
```

D9 freeze uses median SHARE because the ratio denominator can be
arbitrarily small and positive; no outcome-derived cutoff. D10 freeze
uses OPTION A no-intercept OLS so residual semantics match
`e = r_eth - beta * r_btc`. D11 pins official Fed statement HTML
`For release at 2:00 p.m. EST/EDT` for scheduled 2020-2024 meetings
(2020 March unscheduled/notation excluded).

Evidence: `docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.{json,md}`,
`docs/research_data/D11_FOMC_OFFICIAL_V0/`.

## 2026-09-22 — Sprint 03 targeted red-team repair (F1–F5)

Accepted independent red-team verdict
`C. FIX_REQUIRED_BEFORE_SCIENTIFIC_EXECUTION`. Narrow repair only.
No scientific outcomes. No new cards. No MARKET-07. Protected 2025/2026
sealed. `EXECUTION_AUTHORIZED = false`.

```
D9_RAW_EXTREME_BAR_N = 35157
D9_RETAINED_EVENT_N = 8349
D9_REFRACTORY_DROPPED_EXTREME_N = 26808
D9_CLOSING_EVENT_N = 7184
D9_RAW_ELIGIBLE_CLOSING_CONTROL_N = 130238
D9_MATCHED_CLOSING_CONTROL_N = 7184
D9_ALL_MATCHED_CELLS_BALANCED = true
D9_P_HALF_RULE = two-sided sign-flip vs 0.5, seed 20260922193
D9_P_CONTROL_RULE = two-sided stratified label permutation YEAR x SIGN_D x RV_BUCKET, seed 202609221932
D9_STATISTICAL_GATE_RULE = P_HALF < 0.05 AND P_CONTROL < 0.05
D9_SUPPORT_PASS = true
D10_RAW_ELIGIBLE_CONTROL_N = 21368
D10_EVENT_N = 4442
D10_MATCHED_CONTROL_N = 4442
D10_ALL_MATCHED_CELLS_BALANCED = true
D10_PERMUTATION_RULE = STRATIFIED_LABEL_PERMUTATION YEAR x SIGN_E_T x ABS_BTC_RETURN_BUCKET
D10_SUPPORT_PASS = true
D11_EVENT_N = 39
D11_CONTROL_N = 551
D11_MIN_CONTROLS_AMONG_EVENTS = 44
CLASSIFICATION_IDENTITY_PRECEDENCE = IDENTITY_OK false -> INVALID_DISCOVERY before support failure
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_IMPLEMENTATION_RED_TEAM_AND_EXECUTION_DECISION
```

D9 refractory-dropped P90 extremes are excluded from controls.
D9/D10 controls are 1:1 composition-matched without replacement.
D10 permutation is stratified inside frozen cells.
D11 full 6h control windows exclude FOMC aftermath hours.

Evidence: `docs/research/DISCOVERY_SPRINT_03_IMPLEMENTATION_FREEZE.{json,md}`.

## 2026-09-22 — Sprint 03 canonical scientific execution

One authorized canonical scientific execution of D9/D10/D11 from
`EXECUTION_ROOT = e2852f57ee946ec8380f09fa4cf834579c40f872`
(`EXPECTED_TREE = 8805ee7d39b29c267589e7f9400384ebdb1f66ca`).
Frozen science unchanged. Disappointing results not rescued.
Protected 2025/2026 sealed. D7 not rerun. D8 not executed. MARKET-07
not created. Sprint 04 not selected.

```
D9_CLASSIFICATION = NO_USEFUL_STRUCTURE
D9_MEDIAN_EVENT_SHARE = 0.5802929601004294
D9_MEDIAN_MATCHED_CONTROL_SHARE = -0.5169574135394528
D9_DELTA_VS_HALF = 0.08029296010042941
D9_DELTA_VS_CONTROL = 1.0972503736398822
D9_P_HALF = 0.6375362463753624
D9_P_CONTROL = 0.001999800019998
D9_STATISTICAL_GATE = false
D9_PRACTICAL_GATE = false
D9_TEMPORAL_GATE = false
D9_RESULT_PAYLOAD_SHA256 = 517ce639171b6f420e844064651c7ac54928b6c73255d4880c30215d75a31ab6
D10_CLASSIFICATION = NO_USEFUL_STRUCTURE
D10_MEAN_EVENT = -3.2315971654121255e-05
D10_MEAN_MATCHED_CONTROL = -4.6354284587184016e-05
D10_DELTA = 1.403831293306276e-05
D10_MC_P = 0.45525447455254475
D10_STATISTICAL_GATE = false
D10_PRACTICAL_GATE = false
D10_TEMPORAL_GATE = true
D10_RESULT_PAYLOAD_SHA256 = 32c85b26abd3f73b9bf13a1d24063742496b5f9269f2e8af5cf5aab99e1aa85c
D11_CLASSIFICATION = PROMISING_PROTOTYPE
D11_MEAN_EVENT_RV_6H = 0.025030946621530287
D11_MEAN_CONTROL_RV_6H = 0.014225531431703974
D11_RELATIVE = 0.7595790176066561
D11_MC_P = 0.00019998000199980003
D11_STATISTICAL_GATE = true
D11_PRACTICAL_GATE = true
D11_TEMPORAL_GATE = true
D11_RESULT_PAYLOAD_SHA256 = 54e477ad6389b1ca8969a60c3d30340056f8f01662eaef27271cae92290ddbf3
BATCH_RESULT_PAYLOAD_SHA256 = 1e1d25e13289fbbe2e0e96cd8b0c171b804c233f7b4b1d2771785b284c2e04ea
INTERNAL_DISCOVERY_CARDS_EXECUTED = 8
INTERNAL_PROMISING_PROTOTYPES = 3
SCIENTIFIC_OUTCOMES_COMPUTED = true
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
MARKET_07_CREATED = false
SPRINT04_HYPOTHESES_SELECTED = false
NEXT_UNIT = DISCOVERY_SPRINT_03_POST_RESULT_PROGRAM_DECISION
```

D9/D10 did not pass the frozen discovery gate. Do not rescue.
D11 is a discovery-stage unsigned scheduled-FOMC vol screen only.

Evidence: `docs/research/discovery_results/D9_DISCOVERY_RESULT.{json,md}`,
`docs/research/discovery_results/D10_DISCOVERY_RESULT.{json,md}`,
`docs/research/discovery_results/D11_DISCOVERY_RESULT.{json,md}`,
`docs/research/DISCOVERY_SPRINT_03_RESULT.{json,md}`.

## 2026-09-22 — Post-Sprint 03 program decision and Discovery Sprint 04 outcome-blind selection

Outcome-blind program/selection unit on `origin/main`
`d74255545f709d002733b2cb5d0aa447d7b30198`. No window consumed. No
scientific outcome computed. D9/D10/D11 RESULT artifacts unchanged.

```
D9  = consumed NO_USEFUL_STRUCTURE
D10 = consumed NO_USEFUL_STRUCTURE
D11 = consumed PROMISING_PROTOTYPE
INTERNAL_DISCOVERY_CARDS_EXECUTED = 8
INTERNAL_PROMISING_PROTOTYPES = 3
D7_CONFIRMATION_SELECTED_NOW = false
D11_CONFIRMATION_SELECTED_NOW = false
HYPOTHESIS_GENERATION_POLICY = HETEROGENEOUS_FAMILY_ROTATION_V3
NEW_FAMILY_PROPOSALS = [J PARTICIPANT_CLOCK_ANCHORING]
SPRINT04_CANDIDATE_POOL_N = 12
SPRINT04_SELECTED_CARDS = [D12, D13]
D12 = PARTICIPATION_CLOCK_ANCHORING_DST_NATURAL_EXPERIMENT (J; CORE BTC; data ready)
D13 = CROSS_SECTIONAL_WEEKLY_RELATIVE_RETURN_STRUCTURE (H true panel; Binance Vision; FEASIBILITY_REQUIRED)
D14 = NOT_SELECTED
POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED = true
AUTOMATIC_SPRINT05 = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
D12_EXECUTED = false
D13_EXECUTED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

Program observation: all three prototypes are volatility/activity-level
structures and every direction/return card is null; Sprint 04 therefore
selects no volatility-level card. The only data touched for D13
feasibility was an object-key listing of the public Binance archive (no
price bytes).

Evidence: `docs/research/POST_SPRINT03_PROGRAM_DECISION.{json,md}`,
`docs/research/HETEROGENEOUS_FAMILY_ROTATION_V3.{json,md}`,
`docs/research/DISCOVERY_SPRINT_04.{json,md}`.

## 2026-09-22 — Discovery Sprint 04 pre-outcome amendment 1

Targeted pre-outcome correction of PR #201 (`fe6f252`). No outcome
inspected; no quote-volume profile inspected; candidate pool and
selection unchanged.

```
D12_WINDOW_DAYS = 6 (Monday-Saturday before / after each transition Sunday)
D12_WEEKDAY_COMPOSITION_MATCHED = true
D12_EU_CLOCK_CONSTANT = true
D12_PSEUDO_WINDOW_SEMANTICS_MATCH_REAL = true
MECHANISM_MEMORY_CURRENT_THROUGH = D11
D13_NO_POST_T_SILENT_EXCLUSION = true
D13_NO_POST_T_CLOSE_SELECTED_N = NOT_COMPUTED_IN_THIS_UNIT
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_04_BATCH_FEASIBILITY_AND_OUTCOME_BLIND_IMPLEMENTATION
```

## 2026-09-22 — Discovery Sprint 04 outcome-blind implementation freeze

D12 and D13 brought to `OUTCOME_BLIND_IMPLEMENTATION_READY`. No scientific
outcomes. No D12 profiles/`A_k`. No D13 formation/holding returns or IC.
D7 not rerun. D8 not executed. D7/D11 not confirmed. 2025/2026 sealed.
MARKET-07 not created.

```
D12_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D12_US_TRANSITIONS_FEASIBLE = 10 / 10
D12_PSEUDO_SUNDAY_N = 239
D12_RANDOM_SEED = 20260922196
D13_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D13_N = 82
D13_NO_POST_T_CLOSE_SELECTED_N = 0
D13_PINNED_TAKER_FEE = 0.001
D13_FRICTION_FLOOR = 0.004
D13_RANDOM_SEED = 20260922197
EXECUTION_AUTHORIZED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION_DECISION
```

Evidence: `docs/research/DISCOVERY_SPRINT_04_IMPLEMENTATION_FREEZE.{json,md}`,
`docs/research_data/SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0/`.

## 2026-09-22 — Discovery Sprint 04 F20 pre-outcome identity repair

Targeted repair on PR #202 HEAD `f6e3ecbd`. F20 confirmed: runtime file-set
authority `object_key_index` was not bound to `D13_SNAPSHOT_ID`. Runtime
scientific file set now derives from the snapshot-bound object ledger;
index/ledger exact-set equality is verified fail-closed. Raw per-symbol
ListBucket XML removed from git. Snapshot identity, ledger digest, N, fee,
seeds, and gates unchanged. No scientific outcomes inspected. D12/D13 not
executed.

```
F20_STATUS = CONFIRMED_AND_FIXED_PRE_OUTCOME
D13_RUNTIME_FILE_AUTHORITY = SNAPSHOT_BOUND_OBJECT_LEDGER
INDEX_LEDGER_EXACT_SET_VERIFIED = true
D13_SNAPSHOT_ID = fdd698c66ce894ba981665c1b4bd5661e7a13b275368ad89f532df9bcc455acd
D13_FILE_LEDGER_DIGEST = fc38ea13756d7da9a8500420adcb8d918bcd7632367b0d7026fd31a1636c56cd
D13_UNIVERSE_IDENTITY_DIGEST = 6a63aaa228d581be135b317baa4354bc3c000f7d3e6597886a0abc004b81fb61
D13_N = 82
D12_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
D13_STATUS = OUTCOME_BLIND_IMPLEMENTATION_READY
SCIENTIFIC_OUTCOMES_COMPUTED = false
D12_EXECUTED = false
D13_EXECUTED = false
NEXT_UNIT = DISCOVERY_SPRINT_04_D12_D13_ONE_SHOT_SCIENTIFIC_EXECUTION_DECISION
```

## 2026-09-22 — Discovery Sprint 04 canonical D12/D13 one-shot

Canonical scientific execution from exact `origin/main`
`d2a62da6e5c907def603a258505b9cc1f92ae3a5` (`TREE =
3c5c5262db5c1313c8d5c712c0d1658f32da0edb`) after the tracked permit
commit. Each card executed exactly once. No redesign after outcomes.
No D7 rerun. No D8. No D7/D11 confirmation. 2025/2026 sealed. MARKET-07
not created. No automatic Sprint 05.

```
D12_CLASSIFICATION = PROMISING_PROTOTYPE
D12_US_TRANSITION_N = 10
D12_PSEUDO_SUNDAY_N = 239
D12_MEAN_A = 0.1335535649302866
D12_MC_P = 9.999000099990002e-05
D12_STATISTICAL_GATE = true
D12_PRACTICAL_GATE = true
D12_TEMPORAL_GATE = true
D12_EU_DIAGNOSTIC_MEAN_A = -0.17392447104949169
D12_EU_DIAGNOSTIC_AFFECTS_CLASSIFICATION = false
D12_RESULT_PAYLOAD_SHA256 = 73299c8d8313c7c73f423bb83565a45e3c17da6a534dbc8dc8fbf12f943b6feb
D13_CLASSIFICATION = NO_USEFUL_STRUCTURE
D13_N = 82
D13_WEEK_N = 256
D13_MEAN_WEEKLY_IC = -0.027440631083253317
D13_POOLED_IC_SIGN = -1
D13_STRUCTURE_LABEL = REVERSAL
D13_MC_P = 0.015598440155984402
D13_STATISTICAL_GATE = true
D13_SIGNED_TOP_BOTTOM_SPREAD = -0.007875047071699056
D13_FRICTION_FLOOR = 0.004
D13_PRACTICAL_GATE = false
D13_TEMPORAL_GATE = true
D13_NO_POST_T_CLOSE_SELECTED_N = 0
D13_RESULT_PAYLOAD_SHA256 = c18f7de5821d8ee808732e0278afa53f622bb977d77f1ec71ee7423c96f5effd
SPRINT04_RESULT_PAYLOAD_SHA256 = a70d7c4b9d84e6b5d3b1a1f27b514d5c725dda1f4c0ca7fa38180eb353064ddd
INTERNAL_DISCOVERY_CARDS_EXECUTED = 10
INTERNAL_PROMISING_PROTOTYPES = 4
SCIENTIFIC_OUTCOMES_COMPUTED = true
AUTOMATIC_SPRINT05 = false
POST_SPRINT04_AUTOMATION_MATURITY_DECISION_REQUIRED = true
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
D7_CONFIRMATION_EXECUTED = false
D11_CONFIRMATION_EXECUTED = false
MARKET_07_CREATED = false
NEXT_UNIT = POST_SPRINT04_AUTOMATION_MATURITY_DECISION
```

D12 is a discovery-stage US-clock quote-volume timing screen only.
EU diagnostic must not reclassify it. Do not identify participants.
D13 observed reversal sign is reported, not chosen. Practical gate
failed; do not pick the larger of momentum vs reversal. Do not rescue
either card.

Evidence: `docs/research/discovery_results/D12_DISCOVERY_RESULT.{json,md}`,
`docs/research/discovery_results/D13_DISCOVERY_RESULT.{json,md}`,
`docs/research/DISCOVERY_SPRINT_04_RESULT.{json,md}`,
`docs/research/DISCOVERY_SPRINT_04_EXECUTION_PERMIT.json`.

## 2026-09-22 — Post-Sprint 04 automation maturity decision

Program-level decision on `origin/main`
`547693ce9d725d7aa6f61b107472cd8c2083ad4f`. No window consumed. No
scientific outcome computed. No data acquired. D1–D13 result artifacts
unchanged.

```
MATURITY_DECISION = HYPOTHESIS_GENERATOR_V0_INFRA_READY
OPTION_B_AT_MOST_ONE_FINAL_SPRINT05 = REJECTED
INTERNAL_DISCOVERY_CARDS_EXECUTED = 10
INTERNAL_PROMISING_PROTOTYPES = 4
EFFECTIVE_DISTINCT_PROTOTYPE_CLASSES = 2
DATA_EXPANSION = GENERATOR_FIRST_DEMAND_REVEALED
HYPOTHESIS_GENERATOR_V0_DESIGN = FROZEN_NOT_IMPLEMENTED
GENERATOR_MODE = SHADOW_ONLY
SHADOW_BATCH_SIZE = 40
REAL_LLM_BUDGET_CAP_USD = 30
NEW_DATA_ACQUIRED = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
SPRINT05_CREATED = false
D14_CREATED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
MARKET_07_CREATED = false
D7_RERUN_PERFORMED = false
D8_EXECUTED = false
D7_CONFIRMATION_EXECUTED = false
D11_CONFIRMATION_EXECUTED = false
D12_CONFIRMATION_EXECUTED = false
NEXT_UNIT = HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS
```

Recorded erratum (not rewritten): the Sprint 04 D12 allowed-claim text
names Binance BTCUSDT spot, but CORE_BTC_BINANCE_V0 is the USD-M
perpetual.

Evidence: `docs/research/POST_SPRINT04_AUTOMATION_MATURITY_DECISION.{json,md}`,
`docs/research/HYPOTHESIS_GENERATOR_V0_DESIGN.{json,md}`.

### 2026-09-22 — Generator V0 design, pre-outcome amendment 1

Design-only amendment to `HYPOTHESIS_GENERATOR_V0_DESIGN`, made before any
generator exists or any generator output is observed. No window or
hypothesis consumed.

```
BLIND_REGION_STATE = PRIOR_WORK_SIGNATURE
GENERATOR_SEES_EXECUTION_STATUS = false
GENERATOR_SEES_OUTCOME_LABELS = false
GOVERNANCE_REGION_AUTHORITY_DESIGNED = true
ROLE_CONTEXT_MATRIX_FROZEN = true
STRUCTURAL_CONTEXT_PROVENANCE_GUARD_FROZEN = true
SCANNER_REMAINS_BACKSTOP = true
DEFERRED_REGIONS_NOT_GLOBALLY_CONSUMED = true
D4_MIXED_STATE_REPRESENTED = true
STREAM_B_PRESERVED = true
MATURITY_DECISION = HYPOTHESIS_GENERATOR_V0_INFRA_READY (unchanged)
NEXT_UNIT = HYPOTHESIS_GENERATOR_V0_IMPLEMENTATION_AND_SHADOW_HARNESS
```

The uniform `CONSUMED` blind label would have told the generator that
blocked regions (B2-06, MARKET-04, D1, D6, D8, D4 lead-lag) were closed.
Consumed-versus-deferred adjudication now lives only in
`GOVERNANCE_REGION_AUTHORITY_V0`, read by the novelty critic.

## 2026-09-23 — Generator V0 shadow infrastructure implementation

Completed the frozen design implementation plus the explicitly authorized
single-field GENERATOR_SIDE_RULE provenance amendment (0A). No research
window or hypothesis was consumed. No historical scientific result changed.
Two clean zero-cost mock campaigns: 40 cards, 20 Stream A, 15 Stream B,
5 non-stream cases, shortlist 5, equal normalized semantic digest. This is
infrastructure evidence only, not LLM-quality or scientific evidence.
Concrete real adapter tested with fake HTTP only; all spend flags remain
false. State: `GENERATOR_V0_REAL_SHADOW_CAMPAIGN_READY`, draft PR for review.
See `research/GENERATOR_V0_ADVERSARIAL_REVIEW.md`,
`research/GENERATOR_V0_OPERATOR.md`, and checkpoint records.

## 2026-09-23 — Generator V0 Structured Outputs and role routing

Infrastructure-only adapter change after the archived first paid call
exposed JSON-mode schema leakage (`STREAM` extra field). No scientific
design, blind context, governance, or validator semantics changed.
OpenAI requests now use `json_schema` + `strict: true` generated from
existing role builders. Role-specific Chat Completions snapshots and
prices are pinned in `scripts/research/generator_v0/models.py`. Fake HTTP
only; `REAL_LLM_CALLS_MADE = false` for this unit. The archived run
`artifacts/generator_v0/first-shadow` was not resumed or overwritten.

```
NEXT_UNIT = GENERATOR_V0_STRUCTURED_OUTPUTS_AND_ROLE_ROUTING
STRUCTURED_OUTPUTS_ENABLED = true
ARCHIVED_RUN_UNTOUCHED = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — Generator V0 GPT-6 role routing correction

Infrastructure-only routing table change on the same Structured Outputs
adapter. Official Chat Completions + Structured Outputs support for
`gpt-6-astra`, `gpt-6-sol`, and `gpt-6-luna` was re-verified from current
model/pricing pages. No dated snapshots exist in the catalog. No scientific
design change. No paid LLM call. Archived `first-shadow` run untouched.

```
ROLE_MODEL_MAP = GENERATOR:gpt-6-astra / NOVELTY_CRITIC:gpt-6-sol / RED_TEAM:gpt-6-sol / FEASIBILITY_CRITIC:gpt-6-luna / SELECTOR:gpt-6-luna
REAL_LLM_CALLS_MADE = false
ARCHIVED_RUN_UNTOUCHED = true
```

## 2026-09-23 — Generator V0 long-running request timeout

Infrastructure-only adapter change after `first-shadow-v2` generation:0
timed out at the fixed 60-second HTTPS read. Real Chat Completions timeout
is now `OPENAI_REQUEST_TIMEOUT_SECONDS = 600`, stored in run config identity.
No retry, no streaming, no Responses/background migration. `TimeoutError`
after dispatch remains `UNCERTAIN` and is never auto-replayed. Fake HTTP
only. Archived `first-shadow` and `first-shadow-v2` were not resumed or
overwritten.

```
NEXT_UNIT = GENERATOR_V0_LONG_RUNNING_REQUEST_TIMEOUT
REQUEST_TIMEOUT_SECONDS = 600
REAL_LLM_CALLS_MADE = false
ARCHIVED_RUN_UNTOUCHED = true
```

## 2026-09-23 — Generator V0 background Responses transport

Infrastructure-only mixed-transport change after `first-shadow-v2` (60s)
and `first-shadow-v3` (600s) GENERATOR calls timed out synchronously and
correctly became UNCERTAIN. GENERATOR now uses `POST /v1/responses` with
`background=true` and `store=true`, then bounded `GET /v1/responses/{id}`.
Critics remain Chat Completions. Structured Outputs schema is unchanged.
Exactly-once: POST without a `response_id` is UNCERTAIN and never
auto-replayed; a known `response_id` is polled/resumed only. Polling GETs
do not reserve budget. Operator wall-time expiry stays
`BACKGROUND_SUBMITTED` / resumable, not UNCERTAIN. Fake HTTP only.
Archived `first-shadow`, `first-shadow-v2`, and `first-shadow-v3` were
not opened, resumed, or overwritten.

```
NEXT_UNIT = GENERATOR_V0_BACKGROUND_RESPONSES_TRANSPORT
GENERATOR_ENDPOINT = RESPONSES
GENERATOR_BACKGROUND = true
BACKGROUND_STORE_POLICY = STORE_TRUE_REQUIRED_FOR_RESUME
CRITIC_ENDPOINT = CHAT_COMPLETIONS
REAL_LLM_CALLS_MADE = false
ARCHIVED_RUN_UNTOUCHED = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — Generator V0 output limit and terminal-usage accounting

Infrastructure-only after `first-shadow-v4` GENERATOR round 0 returned
background `incomplete` / `max_output_tokens` at 16000 output tokens
(9322 reasoning tokens inside that bound). GENERATOR
`max_output_tokens` is now the named identity field
`GENERATOR_MAX_OUTPUT_TOKENS = 32768`. Critics unchanged. Terminal
background Responses with trustworthy usage persist actual cost and
usage while remaining `FAILED`; no parse, no retry, no COMPLETE.
`COALESCE(cost, reserved)` then uses actual cost. Fake HTTP only.
Archived `first-shadow` through `first-shadow-v4` were not opened,
resumed, overwritten, or retrofitted.

```
NEXT_UNIT = GENERATOR_V0_OUTPUT_LIMIT_AND_TERMINAL_USAGE_ACCOUNTING
GENERATOR_MAX_OUTPUT_TOKENS = 32768
TERMINAL_USAGE_ACCOUNTING = true
REAL_LLM_CALLS_MADE = false
ARCHIVED_RUN_UNTOUCHED = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — Generator V0 protected-data semantics and COMPLETE carry-forward

Infrastructure-only after `first-shadow-v5` stopped at C018 under a
whole-card `2025|2026` regex. That card declared
`PROTECTED_DATA_REQUIREMENT=false` and `LEGAL_RANGE=2020-01..2024-12`;
the years appeared only in an exclusion (`NO_LOOKAHEAD_RULE`). The
application validator now hard-fails required protected data (flag,
forbidden catalog source, or DATA_REQUIRED legal range) and allowlists
mention-only exclusions. Offline `derive` imports exact-compatible
COMPLETE Generator calls from an immutable source into a new run,
preserves cost against the campaign cap, revalidates, and stops. No POST.
`first-shadow-v5` is sealed. Do not continue to generation:2 in this unit.

```
NEXT_UNIT = GENERATOR_V0_PROTECTED_DATA_SEMANTICS_AND_COMPLETE_CARRY_FORWARD
PROTECTED_DATA_VALIDATOR_SEMANTICS = REQUIREMENT_NOT_MENTION
LEGAL_RANGE_FAIL_CLOSED = true
MENTION_ONLY_ALLOWED = true
COMPLETE_RESPONSE_CARRY_FORWARD = true
REAL_LLM_CALLS_MADE = false
ARCHIVED_RUN_UNTOUCHED = true
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — PR #210 red-team amendment F1–F4

Independent red-team of `a7c44d137a63aadb639259efcfe99c60d247a0b7` was
`RED_TEAM_BLOCKED` on F1–F4. This amendment closes those blockers only.

- F1: operational protected-year tokens fail closed; C018 exclusion in
  `NO_LOOKAHEAD_RULE` still passes; `DATA_REQUIRED` legal-range checks kept.
- F2: `HORIZON="2025"` fails again; F1 examples have explicit FAIL tests.
- F3: `authorize-derived-continuation` is the explicit offline gate from
  `DERIVED_IMPORTED_REVALIDATED` to `DERIVED_CONTINUATION_AUTHORIZED`.
- F4: derive does not write `cards`; campaign finalization inserts once.

Deferred nonblocking findings, not redesigned here:

```
F5_STATUS = DEFERRED_NONBLOCKING_RED_TEAM_FINDING
F6_STATUS = DEFERRED_NONBLOCKING_RED_TEAM_FINDING
F7_STATUS = DEFERRED_NONBLOCKING_RED_TEAM_FINDING
F8_STATUS = DEFERRED_NONBLOCKING_RED_TEAM_FINDING
F9_STATUS = DEFERRED_NONBLOCKING_RED_TEAM_FINDING
F5 = generated LEGAL_RANGE subset vs catalog range
F6 = per-snapshot bound identity
F7 = stronger response-envelope provenance verification
F8 = SQLite WAL/SHM archive immutability hardening
F9 = whole-remaining-campaign worst-case budget preflight
REAL_LLM_CALLS_MADE = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — PR #210 F1 residual: exclusion parser and open-ended aliases

Independent narrow regression after the F1–F4 amendment left F1 open.
This closeout tightens only the remaining F1 parser:

- F1A: `PROTECTED_EXCLUSION_STATEMENT` is now the unambiguous form
  `No 2025[/2026] <non-numeric subject> are/is permitted|allowed`. The
  body cannot contain a digit, `. ; : ! ?`, optional "not", or
  "forbidden". C018 still passes; sentence/semicolon/colon swallows,
  "are not permitted", and "No 2025 data are forbidden" fail.
- F1B: open-ended and post-2024 aliases apply recursively to all
  candidate content outside the recognized `NO_LOOKAHEAD_RULE`
  exclusion. Methodology "current batch"/"current candidate" remain
  non-protected.

F2/F3/F4 remain closed and unmodified. F5–F9 remain
`DEFERRED_NONBLOCKING_RED_TEAM_FINDING`. No paid LLM call. No
first-shadow-v6. No scientific outcome.

## 2026-09-23 — PR #210 H1: bare latest/current false positive

Independent regression after the F1 residual closeout found H1: the
open-ended detector rejected standalone "latest" and "current", so
point-in-time wording failed (`latest closed bar at or before T`,
`current funding rate as-of T`, `current regime state`). This closeout
removes only those bare alternatives. Explicit observation-window forms
(`latest available`, `current bars`, `through today`, `post-2024`, and
the rest of the frozen alias list) still fail. F1–F4 remain closed.
F5–F9 remain `DEFERRED_NONBLOCKING_RED_TEAM_FINDING`. No paid LLM call.
No first-shadow-v6. No scientific outcome.

## 2026-09-23 — PR #210 annotated LEGAL_RANGE compatibility

Read-only revalidation of immutable `first-shadow-v5` found five cards
failing `ambiguous protected range` because `LEGAL_RANGE` used
`Required historical window: YYYY-MM..YYYY-MM; <coverage note>`. This
closeout teaches `classify_legal_range` that exact annotated form only;
the returned class is the inner strict range. Unsafe prefixes, extra
ranges, trailing years/open-ended notes, and extra text still fail.
Cards were not edited. F1–F4 and H1 remain closed. F5–F9 remain
`DEFERRED_NONBLOCKING_RED_TEAM_FINDING`. No paid LLM call. No
first-shadow-v6. No scientific outcome.

## 2026-09-23 — Generator V0 LEGAL_RANGE wrappers and campaign-cap extension

Read-only inspection of immutable `first-shadow-v6` generation:2 found
inspected prose wrappers failing `ambiguous protected range`. This
closeout teaches `classify_legal_range` those exact generation:2 families
in addition to the v5 annotated form. The returned class is the inner
strict range. Free prose, extra ranges, trailing years, open-ended notes,
and digit/open-ended subjects still fail. Cards were not edited.
`first-shadow-v6` is sealed. Offline `authorize-budget-extension` may
raise a campaign cap (USD 7.117536 -> 17.117536 was recorded here as an
incorrect +USD 10 reading; corrected in the next entry) without
rewriting calls, responses, costs, or cards. Prove derive through
generation:2 on a TEMP scratch destination. Do not create live
`first-shadow-v7` here. F5–F8 remain deferred. No replay of generation:2.
No paid LLM call. No scientific outcome.

```
NEXT_UNIT = GENERATOR_V0_LEGAL_RANGE_WRAPPERS_AND_BUDGET_EXTENSION
LEGAL_RANGE_WRAPPERS = V5_ANNOTATED_PLUS_INSPECTED_GEN2
BUDGET_EXTENSION_COMMAND = authorize-budget-extension
OLD_CAP_USD = 7.117536
NEW_CAP_USD = 17.117536
FIRST_SHADOW_V6_SEALED = true
REAL_LLM_CALLS_MADE = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — Generator V0 owner-authorized campaign cap is USD 10 total

Correction: USD 10 is the absolute maximum authorized total campaign
budget, not a +USD 10 increment on the previous internal cap of
USD 7.117536. `authorize-budget-extension` therefore cannot set a cap
above USD 10.000000. After imported generation:0/1/2 spend of
USD 3.779550, remaining authorized spend is USD 6.220450.
`remaining-budget-preflight` computes worst-case remaining reservations
with the same `bound()` path used before every live call. Live
run/resume with a cap above USD 10 is refused. No real LLM call while
the effective cap would exceed USD 10, and no live first-shadow-v7
unless that preflight proves a complete remaining campaign fit.

Executable remaining-budget-preflight on a TEMP derive of sealed
`first-shadow-v6` through generation:2, after raising the dest cap to
USD 10.000000, measured:

```
FITS_AUTHORIZED_REMAINING = false
WORST_CASE_REMAINING_USD = 13.286520
MIN_ADDITIONAL_AUTHORIZATION_USD = 7.066070
MIN_TOTAL_CAP_USD = 17.066070
generation:3 = 1.852570
NOVELTY_CRITIC x40 = 8.164734
FEASIBILITY_CRITIC x40 = 0.171850
RED_TEAM x40 = 3.095374
SELECTOR = 0.001992
LIVE_FIRST_SHADOW_V7_CREATED = false
```

Novelty critics alone already exceed remaining authorized USD 6.220450.
STOP without live LLM calls until additional authorization covers at
least USD 7.066070 more (absolute cap at least USD 17.066070).

```
NEXT_UNIT = GENERATOR_V0_LEGAL_RANGE_WRAPPERS_AND_BUDGET_EXTENSION
OWNER_AUTHORIZED_CAMPAIGN_CAP_USD = 10.000000
OLD_INTERNAL_CAP_USD = 7.117536
NEW_CAP_USD = 10.000000
SPENT_USD = 3.779550
REMAINING_AUTHORIZED_USD = 6.220450
SUPERSEDED_UNAUTHORIZED_CAP_USD = 17.117536
FIRST_SHADOW_V6_SEALED = true
REAL_LLM_CALLS_MADE = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
```

## 2026-09-23 — Generator V0 first-shadow-v7 live under USD 17.10 absolute ceiling

Owner authorized an absolute cumulative campaign ceiling of USD 17.100000,
including already recorded imported spend USD 3.779550. Remaining
authorized additional spend is USD 13.320450. This is not an additional
USD 17.10 allowance. Prior remaining-budget-preflight worst-case remaining
USD 13.286520 fits under that remainder (min total USD 17.066070).
`first-shadow-v6` stays sealed. Live `first-shadow-v7` is authorized after
offline derive through generation:2, cap extension to USD 17.100000, and
`FITS_AUTHORIZED_REMAINING=true`. Fail closed before exceeding USD 17.10.
No protected-data open.

```
NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_LIVE
OWNER_AUTHORIZED_CAMPAIGN_CAP_USD = 17.100000
SPENT_USD = 3.779550
REMAINING_AUTHORIZED_USD = 13.320450
FIRST_SHADOW_V6_SEALED = true
```

## 2026-09-23 — Generator V0 first-shadow-v7 fail-closed after generation:3

Live first-shadow-v7 reused imported generation:0/1/2 COMPLETE rows and
made one new GENERATOR background Responses call for generation:3
(`resp_071edfe3d5c0aaa9006ab3de92a5ac87d28b9f8efaec6c7db7`, actual
USD 1.167200, reservation USD 1.852570). Local `validate_card` then
fail-closed: 9/10 generation:3 cards invalid (8 `ambiguous protected
range`, C033 `protected data requirement`); C037 valid; `cards` table
empty. Critics and selector were not started. Cumulative spend
USD 4.946750 of the USD 17.100000 ceiling. The journaled generation:3
answer was not edited. LEGAL_RANGE wrappers and the C033 exclusion parser
were not extended after observing those outcomes. Source cards C001–C030
were not edited. first-shadow-v6 sqlite SHA256 remains
`ed318020ff5d6c765394c15ba4ff5bd7dc0f89ffe83f7692f678e3f7e124b22d`.
first-shadow-v7 is sealed. No scientific outcome. Protected 2025/2026
unopened. Record: `docs/research/GENERATOR_V0_FIRST_SHADOW_V7.{json,md}`.

```
NEXT_UNIT = GENERATOR_V0_FIRST_SHADOW_V7_FAIL_CLOSED
NEXT_ACTION = STOP_NO_RESUME_NO_VALIDATOR_REPAIR
STATUS = STOPPED_PROTECTED_RANGE_VALIDATION
NEW_SPEND_USD = 1.167200
CUMULATIVE_SPEND_USD = 4.946750
REAL_LLM_CALLS_THIS_UNIT = 1
GENERATION_3_VALID = 1
GENERATION_3_INVALID = 9
CARDS_TABLE_COUNT = 0
CRITICS_RUN = false
SELECTOR_RUN = false
SCIENTIFIC_OUTCOMES_COMPUTED = false
PROTECTED_2025_2026_OPENED = false
VALIDATOR_REPAIRED_AFTER_OUTCOME = false
FIRST_SHADOW_V6_SEALED = true
FIRST_SHADOW_V7_SEALED = true
AUTHORITY_JOURNAL_SHA256 = e27eb1ce77c5152eff4e68e30c2632ad9bd575ef953b5a069775b5ff46f36457
```

### 2026-09-23 — Generator V0 pre-live repair (offline)

No research window, hypothesis or card consumed. No paid call, no protected
data, no scientific outcome. Sealed first-shadow-v6/v7 unchanged.

```
UNIT = GENERATOR_V0_PRE_LIVE_REPAIR
COMPLETION_STATE = READY_FOR_INDEPENDENT_REVIEW
READY_FOR_LIVE_SHADOW = false
CONTRACT = GENERATOR_CONTRACT_V02
LEGACY_COMPATIBILITY = A_GRANDFATHER_ONLY_LISTED_CALL_KEYS (3 calls, 30 cards)
V7_DERIVE_LINEAGE_TOTAL_MICRO_USD = 4946750
NEXT_UNIT = GENERATOR_V0_PRE_LIVE_REPAIR_READY_FOR_INDEPENDENT_REVIEW
```

Outcome-blind design amendments: hard fail per candidate, MIN_VALID_CANDIDATES
= 25, diversity controls on the attempted slot plan, advisory selector call
with the deterministic ordinal order authoritative. Record:
`docs/research/GENERATOR_V0_PRE_LIVE_REPAIR.{json,md}`.

## Generator V0 limited offline repair (after PR #215) — 2026-09-23

No research window, hypothesis or protected data consumed. Infrastructure repair only.

```
BASE = ddda586dc7ea4a9589bc389eef7a6306d64f3d0c
VERIFICATION = PR #215 (B. LIMITED OFFLINE REPAIR REQUIRED)
B1_NOVELTY_PROMPT_SCHEMA = FIXED (keyed objects end to end)
B2_SEALED_BELOW_CLI = FIXED (Ledger refuses sealed journals; read handles refuse mutation)
B3_CRASH_AFTER_POST = FIXED (DISPATCHED before send; NOT_BILLED needs provider evidence; UNKNOWN closes the logical call)
B4_NORMALIZATION = FIXED_NOT_SEMANTICALLY_COMPLETE (external PR #215 corpus: 47 -> 1 admitted of 181, 0 false positives of 26)
B5_BUDGET = FIXED_DECISION_NOT_TAKEN (scenarios A-E in generator_v0_repair/BUDGET_SCENARIOS.json)
V7_LINEAGE_MICRO_USD = 4946750
REAL_LLM_CALLS_MADE = false
COMPLETION_STATE = READY_FOR_RE-VERIFICATION
NEXT_UNIT = GENERATOR_V0_LIMITED_REPAIR_READY_FOR_RE_VERIFICATION
```

Record: `docs/research/GENERATOR_V0_LIMITED_REPAIR.{json,md}`.

## Generator V0 final narrow repair (after re-verification) — 2026-09-23

No research window, hypothesis or protected data consumed. Infrastructure repair only.

```
ABBREVIATED_CROSS_YEAR_RANGES = FIXED
IMPERATIVE_TRADE_LANGUAGE = FIXED_STRUCTURAL_NOT_SEMANTIC
EXECUTION_LAYER_BUDGET_GATE = FIXED (run_campaign fails closed; BUDGET_STOP_ACCEPTED bound to cap/spend/worst case)
REAL_LLM_CALLS_MADE = false
COMPLETION_STATE = READY_FOR_FINAL_RE-VERIFICATION
NEXT_UNIT = GENERATOR_V0_FINAL_NARROW_REPAIR_READY_FOR_FINAL_RE_VERIFICATION
```

## Generator V0 outcome-blind multi-provider routing — 2026-09-24

No research window, hypothesis or protected data consumed. Infrastructure plus an outcome-blind routing amendment (provider/model/effort per role only).

```
GENERATOR = ANTHROPIC / claude-opus-5-5 / effort=high
NOVELTY_CRITIC = OPENAI / gpt-6-sol / reasoning_effort=high
RED_TEAM = OPENAI / gpt-6-sol / reasoning_effort=high
FEASIBILITY_CRITIC = OPENAI / gpt-6-luna / reasoning_effort=low
SELECTOR (advisory) = OPENAI / gpt-6-luna / reasoning_effort=none
ROUTING_DIGEST = c0eefdfa06e7f2607be905aac961bf0d46fd609ea8482ab852052efe8b90be38
FRESH_40_CARD_WORST_CASE_SINGLE_ATTEMPT_USD = 21.821289
REAL_LLM_CALLS_MADE = false
COMPLETION_STATE = READY_FOR_MULTI_PROVIDER_INDEPENDENT_REVIEW
NEXT_UNIT = GENERATOR_V0_MULTI_PROVIDER_ROUTING_READY_FOR_INDEPENDENT_REVIEW
```

## Generator V0 Anthropic compact GENERATOR projection — 2026-09-24

No research window, hypothesis or protected data consumed. Wire-format repair only. The first Anthropic schema-acceptance smoke returned HTTP 400 "compiled grammar is too large", cost USD 0.

```
TRIGGER_CALL_KEY = 767fd9e133e63a6e212277326252679724c3863d9d649e909c0eb1dc2bdf95a0 (never reused)
WIRE_FORMAT = ANTHROPIC_COMPACT_CANDIDATE_ARRAY_V1
SCIENTIFIC_CONTRACT_CHANGED = false
REQUEST_BODY_BYTES = 55982 -> 27571 (generation:0)
SCHEMA_OBJECTS = 42 -> 5; SINGLE_VALUE_ENUMS = 40 -> 1; LEGAL_RANGE_PATTERNS = 10 -> 1
ROUTING_DIGEST = ef21451e433da324430c15cbfda41e514ab114d8f9fd2fa0921d9cc266d32716
SMOKE_RESERVATION_USD = 0.987962 of 3.00 (FITS)
LIVE_RE_SMOKE = NOT_PERFORMED (ANTHROPIC_API_KEY missing); REAL_LLM_CALLS_MADE = false
COMPLETION_STATE = OFFLINE_GATES_PASS / LIVE_RE_SMOKE_BLOCKED
```

Record: `docs/research/GENERATOR_V0_ANTHROPIC_COMPACT_PROJECTION.{md,json}`.

## Generator V0 Anthropic compact live re-smoke and output-cap amendment — 2026-09-24

No research window, hypothesis or protected data consumed. Infrastructure spend only.

```
LIVE_RE_SMOKE_CALL_KEY = f8207e1f0fa229f24eec50b0c894d704dd32ad1fece59672e2d2440b47ea930e (never reused)
LIVE_POSTS = 1 (ANTHROPIC GENERATOR, claude-opus-5-5, effort high, compact wire, generation:0)
HTTP_STATUS = 200; SCHEMA_ACCEPTED = true; STOP_REASON = max_tokens
RESPONSE_ID = msg_011CfN3ZuBMiCqeAeRNdWSsJ
USAGE = input 14493 / output 32768 (thinking 17396)
COST_MICRO_USD = 713332 (reserved 782028); STATE = FAILED_WITH_COST
RAW_SHA256 = null; WIRE_SHA256 = 968550f7935eaf873a08b1d846a7b314cca797d37f49ab5e64cc2d8035922af2
CRITIC_CALLS = 0; RETRIES = 0
OWNER_AMENDMENT = routed Anthropic GENERATOR MAX_OUTPUT_TOKENS 32768 -> 100000 (legacy OpenAI cap unchanged)
NEW_GENERATION_0_CALL_KEY = b1ed0d8333ae4b823e72e4175ef7680e0896cfc02915aa476d3278fa56d5cc93
ROUTING_DIGEST = e925b578bfc0cdc2bfe354406178f56068d3745b784e36933b7d76cd5b344f1b
HASH_PROVENANCE_FIX = failed attempts carry wire_sha256 only, never raw_sha256
SMOKE_CEILING_USD = 3.10 incl. history; HISTORICAL = 0.713332; NEXT_RESERVATIONS = 2.325392; TOTAL = 3.038724 (FITS)
FRESH_40_CARD_ROUTED_WORST_CASE_USD = 26.744465 single attempt (was 21.365889)
SCIENTIFIC_CONTRACT_CHANGED = false; REAL_LLM_CALLS_THIS_REPAIR = 0
COMPLETION_STATE = READY_FOR_OUTPUT_CAP_INDEPENDENT_REVIEW
```

## Generator V0 re-smoke operational guard — 2026-09-24

No research window, hypothesis or protected data consumed. No live call.

```
ANTHROPIC_REQUEST_TIMEOUT_SECONDS = 1800 (was 900; stream=false; no batch, no streaming)
OPENAI_REQUEST_TIMEOUT_SECONDS = 600 (unchanged)
ROUTER_IDENTITY = 338df127c4f8f0a41c3b21cb4cb3fbac33e6ab4a115d724414ec0a183140e336
ROUTING_DIGEST = e925b578bfc0cdc2bfe354406178f56068d3745b784e36933b7d76cd5b344f1b (unchanged)
GENERATION_0_CALL_KEY = b1ed0d8333ae4b823e72e4175ef7680e0896cfc02915aa476d3278fa56d5cc93 (unchanged)
SMOKE_ABSOLUTE_CAP_MICRO_USD = 3100000
SMOKE_HISTORICAL_SPEND_MICRO_USD = 713332 (ledger lineage PRIOR_SPEND)
SMOKE_NEW_SPEND_CAP_MICRO_USD = 2386668
GENERATOR_MAX_NEW_POSTS = 1
CONTENT_RETRY_ALLOWED = false
TRANSPORT_REPLAY_ALLOWED = false
ENTRY = scripts/research/generator_v0/resmoke.py
FULL_PYTEST_FOR_OUTPUT_CAP_COMMIT = STARTED, >90 MINUTES, DID NOT COMPLETE, NO RESULT
REAL_LLM_CALLS_THIS_FOLLOW_UP = 0
COMPLETION_STATE = READY_FOR_FINAL_RE_SMOKE_REVIEW
RESUME_GATE = COMPLETE raw text must parse on the journaled wire format and intake must admit at least one generation:0 card; otherwise STOPPED_UNUSABLE_ROUND or STOPPED_NOTHING_ADMITTED, with no critic POST, on every resume
```

Record: `docs/research/GENERATOR_V0_ANTHROPIC_OUTPUT_CAP_AMENDMENT.{md,json}`.

## Generator V0 final re-smoke, five-card cost calibration attempts, background novelty transport — 2026-09-24

No research window, hypothesis or protected data consumed. Infrastructure spend only. Generated cards and critic outputs have no scientific status.

```
FINAL_RE_SMOKE = SMOKE_COMPLETE (production resmoke.run_resmoke; 3 POSTs)
  GENERATOR  claude-opus-5-5 msg_011CfNLTMVgWaPB8WwpLzNxS end_turn in 14493 / out 43959 (thinking 21448) cost 937152 key b1ed0d83...cc93; 10/10 admitted
  FEASIBILITY gpt-6-luna chatcmpl-ERdnuehSEIxeGOaZOWWumPJrBbcWW stop cost 451
  NOVELTY    gpt-6-sol  chatcmpl-ERdo1NdcpCxG9monO2hZ0Kf08GOTX stop cost 24944 (31 PRIOR_RELATIONS keys, BATCH_RELATIONS {})
  NEW_SPEND_MICRO_USD = 962547; SMOKE_LINEAGE_TOTAL_MICRO_USD = 1675879 of 3100000
CALIBRATION (cap 2000000 micro-USD absolute; cards C001-C005 of the re-smoke round, chosen outcome-blind)
  ATTEMPT_1: 1 POST; C001 NOVELTY gpt-6-sol HTTP 502 non-JSON; key 3d7593020fb5766c6025b7b59e00e55be2e180104e0694cc0d7539ee512176a8
             RECONCILED_UNKNOWN (owner-authorized) cost 214416 (full reservation); journal sealed
  ATTEMPT_2: 7 POSTs; 6 COMPLETE (C001, C002 x novelty/feasibility/red team) cost 94218;
             C003 NOVELTY gpt-6-sol HTTP 502 non-JSON; key 82153d8fba4fd6210a9503a07190535b9eb1adeb9ed7365b0427b3d20846b8d3
             UNCERTAIN reserved 213294 (not reconciled)
  CALIBRATION_LINEAGE_CHARGED_OR_RESERVED_MICRO_USD = 521928; CALIBRATION_STATUS = STOPPED_UNCERTAIN_CALL (incomplete; no cost classification)
BACKGROUND_NOVELTY_TRANSPORT_AMENDMENT (offline; no live call)
  NOVELTY_CRITIC: OPENAI_CHAT_COMPLETIONS -> OPENAI_RESPONSES_BACKGROUND (create once, GET by response_id)
  MODEL/EFFORT/PROMPT/SCHEMA/OTHER ROLES = unchanged
  NOVELTY_ROUTE_DIGEST = 597296d5c91d0b9fe3af97429111b16ed780493a1d198a97ddf2154edd670760
  ROUTING_DIGEST = 9c99dc12b90fb9541113084ec833f5729fb865b5ad80c8c4a943ec0f19dddf66
  COMPLETION_STATE = READY_FOR_BACKGROUND_NOVELTY_INDEPENDENT_REVIEW
```

Record: `docs/research/GENERATOR_V0_BACKGROUND_NOVELTY_TRANSPORT_AMENDMENT.{md,json}`.

## Generator V0 critic calibration continuation and background RED_TEAM transport — 2026-09-24

No research window, hypothesis or protected data consumed. Infrastructure spend only. Generated cards and critic outputs have no scientific status.

```
CALIBRATION_CONTINUATION (absolute cap 4000000 micro-USD; scratch journals, not committed)
  GENERATOR  claude-opus-5-5 effort high; in 14653 / out 41670 (thinking 18008) cost 892012; key e9ea20c2...1a75; 10/10 admitted; C001-C005 selected outcome-blind
  C001 NOVELTY first attempt: direct HTTPSConnection, sandbox egress 403; FAILED_NOT_BILLED cost 0
  CLOUD_OPENAI_TRANSPORT: CONNECT via HTTPS_PROXY (read at call time), Authorization removed at the proxy boundary; GET /v1/models 200
  C001 NOVELTY   gpt-6-sol background; 1 create POST, 5 GETs; in 10298 / out 878 (reasoning 402, cached 0) cost 29376
  C001 FEASIBILITY gpt-6-luna; in 2775 / out 274 (reasoning 183) cost 415
  C001 RED_TEAM  gpt-6-sol synchronous; HTTP 502 UNCERTAIN; key 8e94c966b14feeb7f9c9fd1ae4ab1be8e98ddd1067158470032845fa396c6c39
                 RECONCILED_UNKNOWN (owner rule; no response_id or usage) cost 98806 (full reservation); logical call closed in that journal
  LEDGER_TOTAL_CHARGED_MICRO_USD = 1020609; CALIBRATION_STATUS = STOPPED_UNCERTAIN_CALL (incomplete; no cost classification)
BACKGROUND_RED_TEAM_TRANSPORT_AMENDMENT (offline; no live call)
  RED_TEAM: OPENAI_CHAT_COMPLETIONS -> OPENAI_RESPONSES_BACKGROUND (create once, GET by response_id)
  MODEL/EFFORT/PROMPT/SCHEMA/TOKEN_CAP/OTHER ROLES = unchanged
  RED_TEAM_ROUTE_DIGEST = f6fadb7b8239db5449b265eb7ea1583482befa78b387dca49497cf2d1870a2f2
  ROUTING_DIGEST = c636f14a9e48dc07f8ebca16666c80dd20343171a6535f3ec8c47d8f71afc596
  COMPLETION_STATE = READY_FOR_BACKGROUND_RED_TEAM_SMOKE
```

Record: `docs/research/GENERATOR_V0_BACKGROUND_RED_TEAM_TRANSPORT_AMENDMENT.{md,json}`.


## Generator V0 completed five-card calibration and first 30-card architecture freeze — 2026-09-24

No research window or protected outcome consumed. Calibration cards/critic judgments have no scientific status.

```
BACKGROUND_RED_TEAM_LIVE_SMOKE = PASS
  RED_TEAM gpt-6-sol high background Responses: 1 create POST, 5 GETs, completed
  SYNTHETIC_SMOKE_COST_MICRO_USD = 6570 (engineering spend; excluded from normal-run estimate)

FIVE_CARD_CALIBRATION_FINAL = COMPLETE
  SAMPLE = C001-C005 from recovered 10/10-valid Opus round
  GENERATOR_SAMPLE_1_USD = 0.937152
  GENERATOR_SAMPLE_2_USD = 0.892012
  GENERATOR_MEAN_PER_10_USD = 0.914582
  NOVELTY_MEAN_PER_CARD_USD = 0.031955
  FEASIBILITY_MEAN_PER_CARD_USD = 0.000507
  BACKGROUND_RED_TEAM_MEAN_PER_CARD_USD = 0.014777
  CRITIC_CHAIN_MEAN_PER_CARD_USD = 0.047239
  CRITIC_CHAIN_MIN_MEDIAN_MAX_USD = 0.043931 / 0.046675 / 0.053037
  HISTORICAL_CHARGED_LINEAGE_MICRO_USD = 1227012
  FINAL_CONTINUATION_NEW_COST_MICRO_USD = 206403
  UNRESOLVED_CALLS = 0

FIRST_FULL_RUN_SIZE = 30
  GENERATOR_ROUNDS = 3 x 10
  GENERATOR_RETRY_ALLOWED = false
  PROJECTED_30_CARD_GENERATOR_MEAN_USD = 2.743746
  PROJECTED_30_CARD_OPENAI_CRITICS_MEAN_USD = 1.417164
  PROJECTED_30_CARD_TOTAL_MEAN_USD = 4.160910
  PROJECTED_30_CARD_TOTAL_MAX_OBSERVED_USD = 4.402566

ARCHITECTURE_FROZEN_FOR_FIRST_30_CARD_RUN = true
NEXT_PAID_ACTION = FIRST_30_CARD_RUN_AFTER_OPERATIONAL_PERSISTENCE_REVIEW
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
```

Canonical record: `docs/research/GENERATOR_V0_FIRST_30_CARD_ARCHITECTURE_FREEZE.{md,json}`. Runtime protocol: `docs/AGENT_RUNTIME_PROTOCOL.md`.


## Generator V0 calibration-memory ingestion — 2026-09-24

Offline memory/governance update only. No provider calls, market outcomes, or protected data.

```text
SOURCE = GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT
DURABLE_SIGNATURES = GV0CAL-C001..GV0CAL-C005
MEMORY_ENTRY_COUNT = 35
GENERATOR_VISIBLE_STATE = PRIOR_WORK_SIGNATURE for all five
GV0CAL-C001_STATE = CONSUMED
GV0CAL-C002_STATE = CONSUMED
GV0CAL-C003_STATE = DEFERRED_OR_BLOCKED / METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING
GV0CAL-C004_STATE = DEFERRED_OR_BLOCKED / METHOD_CONFOUNDING_CONTROL_INADEQUATE
GV0CAL-C005_STATE = CONSUMED
GENERATOR_SEES_CRITIC_DISPOSITION = false
NOVELTY_DECISION_TABLE_CHANGED = false
ARCHITECTURE_FREEZE_CHANGED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
NEXT_PAID_ACTION = FIRST_30_CARD_RUN_AFTER_OFFLINE_MEMORY_VALIDATION
```

Record: `docs/research/GENERATOR_V0_CALIBRATION_MEMORY_INGESTION.{json,md}`.

## Generator V0 memory finalizer V1 — 2026-09-24

No research window, hypothesis or protected data consumed. Offline infrastructure only; no provider call.

```
MEMORY_AUTHORITY = APPEND_ONLY_EVENT_CHAIN (docs/research/generator_v0_memory/)
EVENT 0 LEGACY_BOOTSTRAP 54afd1ed229cca6785586534102df3b6fb5129e736def4f5df726225b16773e8
  30 pre-GV0CAL entries + 30 governance rows verbatim from d4b28dea18a64b3ed00339ebdcde539a78e4d1e1
  replay reproduces that commit's memory / blind map / authority byte-for-byte
EVENT 1 GV0CAL 358f06d4e2d1f7d1657c89544fc702d7dffe7bf6c1ec920ceab4228f7a50c3ad (head)
  source GENERATOR_V0_FIVE_CARD_CALIBRATION_EXPORT.json sha256 14146e3aedb4ad67942ddbf5ab3245193cf373282b4bd11d8a926b5bcc6b9f73
  5 attempt records, 5 new canonical signatures, 0 links
  C001/C002/C005 CONSUMED; C003 DEFERRED_OR_BLOCKED METHOD_CAUSAL_IDENTIFICATION_AND_CONFOUNDING;
  C004 DEFERRED_OR_BLOCKED METHOD_CONFOUNDING_CONTROL_INADEQUATE (golden: manual ingestion 64a37a9)
MEMORY_ENTRY_COUNT = 35; ATTEMPT_RECORD_COUNT = 5
DESIGN: embedded governance ROWS removed (rules unchanged); finalization never edits the design
NO_SCIENTIFIC_STATUS = true; MARKET_OUTCOMES_TESTED = false; generated hypotheses != executed market tests
```

Record: `docs/research/GENERATOR_V0_MEMORY_FINALIZER.{md,json}`.

## Generator V0 first 30-card production-path repair — 2026-09-24

No research window, hypothesis, or protected data consumed. Offline only. No provider call.

```
GENERATOR_CONTENT_ATTEMPTS = 1
GENERATOR_CONTENT_RETRIES = 0
MAX_GENERATOR_POSTS_30 = 3
SELECTOR_LLM_CALLS = 0
SELECTOR_AUTHORITY = DETERMINISTIC_ORDINAL_ORDER
OPENAI_NETWORK_MODE = CLOUD_PROXY for Cloud Agent (explicit; not inferred from HTTPS_PROXY)
OPENAI_PROXY_TRANSPORT = CloudProxyOpenAITransport
OPENAI_API_KEY_REQUIRED = false in CLOUD_PROXY
ANTHROPIC_API_KEY_REQUIRED = true
BUDGET_RESERVATION_UNCHANGED = 19516751 micro-USD single-attempt size 30
MEMORY_FINALIZER_V1 = unchanged
LIVE_API_CALLS = 0
```

Record: `docs/research/GENERATOR_V0_FIRST_30_PRODUCTION_PATH_REPAIR.{md,json}`.

## Generator V0 first 30-card run GV0R01 and memory finalization — 2026-09-24/25

Shadow hypothesis generation and governance only. No market window, hypothesis test or protected data consumed. Paid ideation spend belongs to GV0R01. The seal and memory finalization were offline, with no provider call.

```
CAMPAIGN_ID = GV0R01
RUN_ID = first-30-card-r01
SOURCE_HEAD = 2412a372b5212def2256b1662b5d45f16a91f515
CAMPAIGN_STATUS = PENDING_HUMAN_REVIEW
SLOTS = 30; VALID = 30; HARD_FAIL = 0; REVIEW_FAILED = 0
CALLS = 93 COMPLETE (GENERATOR 3, NOVELTY 30, FEASIBILITY 30, RED_TEAM 30); UNRESOLVED = 0
SELECTOR_LLM_CALLS = 0; CRITIC_CONTENT_RETRIES = 0
SPEND_USD = 5.091486 (ANTHROPIC 2.836676, OPENAI 2.254810); HARD_CAP_USD = 10.00
STREAM_A = [C013]; STREAM_B = [C004, C006, C012, C014, C016, C020]
SHORTLIST = [C013, C014, C006, C012, C016]
SEMANTIC_RESULT_DIGEST = b9ca7a3d4fe1f11d1f40d8b9839bfa68474e25c81bff83ffc148a2a2ba81fcf6
SEALED_JOURNAL = docs/research/generator_v0_gv0r01/run.sqlite
JOURNAL_SHA256 = de22f7c2aeb0487842a2477e5a2f44e3df7a9cbf007785cfaf213cbcd648be62
MEMORY_SOURCE_SHA256 = f5992fff8219a2d6736c99de5ee5e6ae653044299a752fe3a0192c34a44a8579
MEMORY_EVENT = 416b22fabd1663be9094bce18c5bce2a8b3d062b0b01525a25395d195788bead (seq 2)
MEMORY_DELTA = 63bfdb6f40278ef83d8f31cdc2122907999da0a5f132504d1051d5c0f3abe85c
NEW_SIGNATURES = 22 (CONSUMED 1: GV0R01-C013; DEFERRED_OR_BLOCKED 21)
LINKED_PRIOR = 4; LINKED_BATCH = 4
MEMORY_ENTRY_COUNT = 57; ATTEMPT_RECORD_COUNT = 35
MARKET_OUTCOMES_TESTED = false; PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = FIRST_MARKET_TEST_DESIGN_FOR_GV0R01
```

The GV0R01 signatures now count as prior search surface. C013 is the only `EXECUTABLE_NOW` candidate, and its market outcome is untested. Record: `docs/research/GENERATOR_V0_FIRST_30_CARD_RUN_GV0R01.{md,json}`.

## GV0R01-C013 market test preregistration — 2026-09-25

Design and preregistration only. No research window consumed, no outcome computed, no protected data opened, no provider call.

```
HYPOTHESIS_ID = GV0R01-C013
TEST_FAMILY_ID = TF-GV0R01-C013-MT1
SEARCH_FAMILY_ID = SF-GENERATOR_V0-GV0R01
PREREG = docs/research/GV0R01_C013_MARKET_TEST_PREREG.json
PREREG_SHA256 = 49dff57b3e068d999c9c4467fb5117de9d73ad564425bf737df727a1096f7625
DATASET = SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0 (file ledger fc38ea13...)
DECISION_DAYS = 2020-01-06..2024-12-29 (260 ISO weeks)
PRIMARY = K5_H1_N50; weekly-mean Spearman(rank CLV, rank WICK_RESID); direction negative
NULL = 1000 within-date quote-volume-tercile permutations; SEED 639284419827364414
PRIMARY_TEST_COUNT = 1; SECONDARY_TEST_COUNT = 7 (descriptive, Holm)
EXECUTION_AUTHORIZED = false
MARKET_TEST_EXECUTED = false
```

The global machine-readable test ledger `docs/research/SCIENTIFIC_TEST_LEDGER.json` starts here. It counts executed tests, not generated cards.

## GV0R01-C013 one-shot market test — executed — 2026-09-25

Consumed: `TF-GV0R01-C013-MT1` on `SPRINT04_BINANCE_SPOT_USDT_DAILY_PANEL_V0` legal 2019-12..2024-12 (decision days 2020-01-06..2024-12-29). Protected 2025/2026 unopened. No LLM call. One execution; no rerun.

```
PERMIT_COMMIT = 386bc10b9b1aad5a7b5c410d48d73e231be9ca4d (pre-outcome)
PREREG_SHA256 = 49dff57b3e068d999c9c4467fb5117de9d73ad564425bf737df727a1096f7625
RESULT = docs/research/GV0R01_C013_MARKET_TEST_RESULT.json
RESULT_SHA256 = 036016c403f83e4c63b2e006379551a0f595e8803cb55a0ef8f27a19ce3a1062
CLASSIFICATION = PROMISING_PROTOTYPE
GATES = STATISTICAL, DIRECTION, TEMPORAL, CONTROL, DEPENDENCE, ADJACENCY all pass
PRIMARY_K5_H1_N50_POOLED = -0.019932; P_TWO_SIDED = 0.001998 (1000 permutations)
CONTROLLED_POOLED = -0.053505; P_TWO_SIDED = 0.001998
HAC_T_LAG4 = -2.479; ADJACENCY_POOLED = -0.021409
YEARLY = 2020 -0.0691, 2021 -0.0677, 2022 -0.0307, 2023 +0.0315, 2024 +0.0363 (3 of 5 share sign)
VALID_DAYS = 1820/1820; VALID_WEEKS = 260; MISSING_TARGET_RATE = 0.000264
SECONDARY_GRID = 7 variants, descriptive only, cannot change classification
SEARCH_FAMILY SF-GENERATOR_V0-GV0R01: EXECUTED_TESTS = 1 (of 30 generated cards)
NEXT_UNIT = GV0R01_C013_INDEPENDENT_CONFIRMATION_DESIGN
```

This is discovery-tier evidence, not a validated edge. The 2023–2024 yearly means are opposite in sign to the pooled result, and that is recorded for the confirmation design. The 2020–2024 legal window of this panel is now consumed for C013 and cannot serve as its confirmation.

## GV0R01-C013 result memory ingestion (MARKET_TEST_RESULT event) — 2026-09-25

Offline memory and provenance only. No research window consumed, no outcome computed, no market data read, no protected data opened, no provider call.

```
MARKET_TEST_RESULT_EVENT = IMPLEMENTED (chain schema GENERATOR_V0_MEMORY_CHAIN_V1 unchanged)
UNIT_ID = GV0R01C013MT1; TEST_FAMILY_ID = TF-GV0R01-C013-MT1; SIGNATURE_ID = GV0R01-C013
SOURCE_SHA256 = 2134503de5ef33a6cd8f03eb4dbe4d6647a3d0204ee898883beb4cbb8a4de271
MEMORY_DELTA_SHA256 = 3b7c5485a6b7fc0d1abe723413e242de4da77867483548c4afc2cfbb46c0962e
EVENT_HASH = 853ef4514460a18b5aa16bf3fff86ece027c52e4b58d92dfbf98034f1fde9373 (sequence 3)
PREVIOUS_EVENT_HASH = 416b22fabd1663be9094bce18c5bce2a8b3d062b0b01525a25395d195788bead
ENTRIES = 57; ATTEMPTS = 35; MARKET_TEST_RESULTS = 1
BLIND_MAP / GOVERNANCE_AUTHORITY / ATTEMPT_RECORDS = byte-identical (digests unchanged)
CLASSIFICATION (copied) = PROMISING_PROTOTYPE, discovery tier, not a validated edge
NEXT_UNIT = GV0R01_C013_INDEPENDENT_CONFIRMATION_DESIGN
```

## GV0R01-C013 independent confirmation feasibility and design — 2026-09-25

Outcome-blind feasibility only. No test registered or executed, no window consumed, protected 2025/2026 values not opened (735 metadata ListBucket requests; 0 payload or checksum GETs), no provider call.

```
DISCOVERY = TF-GV0R01-C013-MT1 PROMISING_PROTOTYPE (consumed)
RESERVED_CONFIRMATION_FAMILY = TF-GV0R01-C013-CONF1 (not registered)
POWER_METHOD = whole-year block resampling of exposed 2020-2024 weekly series (authoritative); MBB 13/26 sensitivity; IID diagnostic
POWER_STAT_AND_DIRECTION_AT_DISCOVERY_EFFECT = 2025: 0.600; 2025+2026 prefix: 0.524; full 2025-2026: 0.687
MIN_FRESH_WEEKS_FOR_0.80 = about 468 (9 years)
ALTERNATIVE_PRE_2019_12_SURFACE = not equivalent (fewer than 50 USDT symbols before 2019-07)
FRESH_SURFACE_DECISION = WAIT_FOR_MORE_FRESH_DATA
NEXT_UNIT = POST_GV0R01_C013_CONFIRMATION_FEASIBILITY_PROGRAM_DECISION
```

## GV0R01 Stream-B feasibility triage and post-C013 program decision — 2026-09-25

Outcome-blind feasibility and routing only. No hypothesis executed, no outcome computed, no window consumed, protected 2025/2026 unopened, no provider call; 13 Binance S3 ListBucket requests, 0 payload GETs.

```
C013_PROGRAM_STATE = PROMISING_PROTOTYPE / CONFIRMATION_DEFERRED_LOW_POWER
C004 = READY_AFTER_FREE_PUBLIC_ACQUISITION (CPI archive; FOMC core ready; D10/D11 overlap)
C006 = BLOCKED_POINT_IN_TIME_SEMANTICS (DVOL non-revision unverifiable; marks paid)
C012 = READY_AFTER_FREE_PUBLIC_ACQUISITION (CPI archive; FOMC arm ready)
C014 = BLOCKED_POINT_IN_TIME_SEMANTICS (DVOL BTC+ETH; quotes paid)
C016 = BLOCKED_EXPENSIVE_DATA (spread/L2 history paid; bookTicker 2023-05-16..2024-03-30 only)
C020 = READY_AFTER_FREE_PUBLIC_ACQUISITION (NYSE, CN State Council, OPM calendars; D12 overlap)
NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C012 (feasibility only)
RUN_GV0R02_NEXT = false
NEXT_UNIT = GV0R01_C012_CPI_CALENDAR_ACQUISITION_AND_OUTCOME_BLIND_DESIGN
```

## BLS CPI release-schedule archive V0 acquisition — 2026-09-25

Data provenance only. No hypothesis executed, no outcome computed, no research window consumed, no CPI values or market data acquired, protected 2025/2026 values not opened, no provider call. Wayback CDX listing plus 190 exact archived payloads and 2 live BLS pages.

```
DATASET_ID = BLS_CPI_RELEASE_SCHEDULE_ARCHIVE_V0
DATASET_DIGEST = 760ed2c5d18b03b7a41c25e6bab157ebde476977fdc3e5f7a3462aa376f4154f
AUTHORITY = bls.gov/schedule/news_release/cpi.htm (first party), dated by web.archive.org captures
EVENTS = 60 (12 per year, 2020-2024); VERIFIED_PREANNOUNCED = 60
SAFE_W6 = 60; SAFE_W12 = 60; SAFE_W24 = 60; RESCHEDULED = 0; UNRESOLVED = 0
DST = STATUTORY_DST_CALENDARS (DISCOVERY_SPRINT_04.json), cross-checked vs EPAct 2005 rule and zoneinfo
CDX_SHA1_MATCH = 189/190 obtained captures (mismatch excluded from evidence)
C012_CPI_BLOCKER_RESOLVED = true; C004_CPI_BLOCKER_RESOLVED = true (observable only; no design)
NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_DESIGN_AND_POWER
```

## GV0R01-C012 outcome-blind design and power — 2026-09-25

Design and ex-ante power only. No hypothesis executed, no market file opened, no return computed, protected 2025/2026 unopened, no provider call, Generator V0 memory unchanged.

```
PRIMARY = FOMC_AND_CPI, PRE_WINDOW_H = 24 (singular; other five card variants cannot decide)
EVENTS = 99 (CPI 60 + FOMC 39); ISO_WEEKS = 94; OVERLAP_PAIRS = 2 (kept); LONG_GAP_CPI = 11 (kept)
INFERENCE = stratified label permutation, 5000 draws, seed 12012, alpha 0.05 two-sided
PLANNING_N = 47 (ISO weeks / variance inflation 2)
MDE_STANDARDIZED = 0.409; POWER_AT_0.50_SIGMA = 0.929; POWER_AT_0.25_SIGMA = 0.403
SIGMA_24H_ASSUMPTIONS = 0.02 / 0.04 / 0.06 (stated, not fit)
OUTCOME_BLIND_GATE = EXECUTION_JUSTIFIED
EXECUTION_AUTHORIZED = false
NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION
```

## GV0R01-C012 one-shot preflight, execution not opened — 2026-09-25

Calendar preflight only. No price file opened, no return computed, protected 2025/2026 unopened.

```
PREFLIGHT_STATUS = PASS
PREFLIGHT_HEAD = 61ce00383d4b8879632e6a0382b9466edcf954ce
EVENTS_WITH_CONTROL = 99; CONTROL_REUSE = 0; WITHIN_STRATUM_GAP >= 7d
CROSS_STRATUM_CONTROL_OVERLAPS = 14; EVENT_CONTROL_OVERLAPS = 5 (not dropped; permutation stays within stratum)
RUN_STATUS = BLOCKED_MARKET_BYTES_ABSENT
MARKET_DATA_OPENED = false
```

## C012 discovery-period market bytes — 2026-09-25

Month objects only. No C012 return, no event window, no protected-year fetch.

```
DATASET = C012_DISCOVERY_BTC_1M_V0
MONTHS = 2020-01..2024-12 (60)
ROWS = 2630880; MISSING_MINUTES = 0; DUPLICATE_OPEN_TIMES = 0
MATCHES_SNAPSHOT_717d37a4 = true
MANIFEST_DIGEST = 78e3f54a6289125769072c5896ddf4516b4d5a98bd1ac5ea4ed7e4d0566f646c
PROTECTED_2025_MARKET_BYTES_FETCHED = false
PROTECTED_2026_MARKET_BYTES_FETCHED = false
C012_PRIMARY_TEST_EXECUTED = false
NEXT_UNIT = GV0R01_C012_ONE_SHOT_EXECUTION
```

## GV0R01-C012 one-shot stopped on permutation dependence — 2026-09-25

Timestamp graph only. No price file opened, no return computed, protected 2025/2026 unopened. The frozen inference procedure was not amended.

```
RUN_STATUS = BLOCKED_INFERENCE_DEPENDENCE_DEFECT
GLOBAL_OVERLAP_GRAPH_COMPONENTS = 177
MAX_OVERLAP_COMPONENT_SIZE = 2
SWAPPABLE_OBSERVATIONS_WITH_DIFFERENT_EXTERNAL_NEIGHBORHOODS = 154
SWAPPABLE_PAIRS = 240
GLOBAL_PERMUTATION_INVARIANCE_STATUS = NOT_ESTABLISHED
MARKET_DATA_OPENED_FOR_C012 = false
C012_PRIMARY_TEST_EXECUTED = false
PRIMARY_EFFECT = NOT_COMPUTED
NEXT_UNIT = GV0R01_C012_OUTCOME_BLIND_INFERENCE_AMENDMENT
```

## GV0R01-C012 outcome-blind inference amendment — 2026-09-25

Inference repair only. No price file opened, no return computed, protected 2025/2026 unopened. The claim, events, controls, and DELTA_24 endpoint are unchanged.

```
OLD_INFERENCE = superseded; failed global invariance gate
AMENDED_GROUP = G_C012_TOPO
OVERLAP_GRAPH = 198 nodes, 21 edges, 177 components, max size 2
PRIMARY_LABEL_ORBIT_SIZE = 3204454418600404451328000000000
STRUCTURAL_INVARIANCE = PASS
STRESS_MDE_SINGLE_WINDOW_SD = 0.609
AMENDED_POWER_GATE_RESULT = INFERENCE_AMENDMENT_VALID_BUT_INFORMATIONALLY_WEAK
MARKET_DATA_OPENED_FOR_C012 = false
C012_PRIMARY_TEST_EXECUTED = false
NEXT_UNIT = NO_EXECUTION_AUTHORIZED
```

## GV0R01-C012 closed outcome-blind — 2026-09-25

No market window consumed. No hypothesis executed. No price opened.

```
C012_STATUS = CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK
C012_EXECUTED = false
C012_MARKET_OUTCOMES_OPENED = false
OLD_INFERENCE = SUPERSEDED_FAILED_GLOBAL_INVARIANCE_GATE
AMENDED_INFERENCE = STRUCTURALLY_VALID
AMENDED_POWER_GATE = FAILED
MDE_SINGLE_WINDOW_SD = 0.6093023255813953
FROZEN_EXECUTION_THRESHOLD = 0.50
PRIMARY_LABEL_ORBIT_SIZE = 3204454418600404451328000000000
SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0
EVIDENCE_ON_ANTICIPATORY_DRIFT = NONE
FURTHER_C012_INFERENCE_AMENDMENT_AUTHORIZED = false
NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C004
NEXT_UNIT = GV0R01_C004_OUTCOME_BLIND_DESIGN_AND_POWER
```

## GV0R01-C004 outcome-blind design and power — 2026-09-25

Design only. No price opened, no C004 statistic executed, no C012 outcome used.

```
C004_DEFINITION_STATUS = UNAMBIGUOUS
PRIMARY = FOMC only, 60m post-statement RESID_SHARE, one-sided lower
EVENTS_PLANNED = 39; COVERED = 38; UNCOVERED = 20200129
CPI_POOLED = false
DEPENDENCE_GRAPH = 76 nodes, 260 beta edges, 0 outcome edges, 1 component
LABEL_ORBIT = 16; MIN_EXACT_P = 1/16; ALPHA_ATTAINABLE = false
EXECUTION_MDE_THRESHOLD = 0.10 RESID_SHARE points
OUTCOME_BLIND_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK
NEXT_UNIT = NO_C004_EXECUTION_AUTHORIZED
```

## GV0R01-C004 closed outcome-blind — 2026-09-25

No market window consumed. No hypothesis executed. No price opened. Exact primary support is the 16-point label orbit, not the power-planning Monte Carlo.

```
C004_STATUS = CLOSED_OUTCOME_BLIND_INFERENCE_SUPPORT_INSUFFICIENT
C004_EXECUTED = false
C004_MARKET_OUTCOMES_OPENED = false
PRIMARY_LABEL_ORBIT_SIZE = 16
MIN_ATTAINABLE_EXACT_P = 0.0625
ALPHA = 0.05
ALPHA_ATTAINABLE = false
POWER_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK
STRESS_POWER_AT_0_20_SHARE_DECLINE = approximately 0.11
SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0
EVIDENCE_ON_POST_FOMC_RESIDUAL_SHARE = NONE
NEXT_CANDIDATE_FOR_DESIGN = GV0R01-C020
NEXT_UNIT = GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER
```

## GV0R01-C020 design blocked before a sample — 2026-09-25

Definition recovered. No holiday calendar pinned. No price or volume opened. No statistic, inference or power.

```
C020_DEFINITION_STATUS = UNAMBIGUOUS
OUTCOME_BLIND_GATE_RESULT = BLOCKED_BY_MISSING_INPUT
MISSING = NYSE_HOLIDAY_CALENDAR_ARCHIVE, CN_STATE_COUNCIL_HOLIDAY_NOTICES, US_OPM_FEDERAL_HOLIDAY_LIST
POWER_SIMULATION_PERFORMED = false
MARKET_DATA_OPENED_FOR_C020 = false
C020_PRIMARY_TEST_EXECUTED = false
NEXT_UNIT = GV0R01_C020_HOLIDAY_CALENDAR_PINNING
```

## GV0R03 generator feasibility contract — 2026-09-25

Contract only. No new hypotheses, no LLM call, no market outcomes. V02 card acceptance is unchanged.

```
GENERATOR_CONTRACT_VERSION = GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V0
COMPILER_SCHEMA_VERSION = GV0R02_SCHEMA_V0
COMPILER_MAPPING_STATUS = MECHANICAL_COPY
MISSING_FIELD_REJECTION_STATUS = EACH_REQUIRED_FIELD
SCIENTIFIC_DOF_PRESERVATION_STATUS = SEALED_FIELDS_REJECT_DOWNSTREAM_EDIT
NEW_HYPOTHESES_GENERATED = false
LLM_CALLS = 0
NEXT_UNIT = NONE_AUTHORIZED_AFTER_GV0R03_CONTRACT
```

## GV0R02 feasibility compiler positive control — 2026-09-25

Synthetic planning fixture only. Same `compile_proposal` entry point. No policy edit, no golden-case edit, no market outcomes.

```
POSITIVE_CONTROL_ID = GV0R02_POSITIVE_CONTROL_SYNTHETIC
POSITIVE_CONTROL_STATUS = FEASIBLE_FOR_PREREGISTRATION
NEGATIVE_MUTATION = NOMINAL_OBSERVATION_COUNT 10000 -> 36
NEGATIVE_MUTATION_STATUS = INFORMATIONALLY_WEAK
NEGATIVE_MUTATION_BLOCKER = MDE_TOO_LARGE
MARKET_OUTCOMES_OPENED = false
GENERATOR_MODIFIED = false
NEXT_UNIT = NONE_AUTHORIZED_AFTER_POSITIVE_CONTROL
```

## GV0R02 feasibility compiler implementation — 2026-09-25

Implementation of the frozen contract. No generator edit, no new data, no market outcomes, no positive control.

```
FEASIBILITY_COMPILER_IMPLEMENTED = true
FEATURE_REGISTRY_VERSION = GV0R02_FEATURE_REGISTRY_V0
GOLDEN_C012 = INFORMATIONALLY_WEAK
GOLDEN_C004 = INFERENCE_SUPPORT_INSUFFICIENT
GOLDEN_C020 = INFORMATIONALLY_WEAK
NEXT_UNIT = GV0R02_FEASIBILITY_COMPILER_POSITIVE_CONTROL
```

## GV0R02 feasibility compiler design — 2026-09-25

Design only. No compiler engine, no generator edit, no new hypotheses, no new data, no market outcomes.

```
COMPILER_SCHEMA_VERSION = GV0R02_SCHEMA_V0
COMPILER_POLICY_VERSION = GV0R02_POLICY_V0
FEASIBILITY_COMPILER_IMPLEMENTED = false
NEXT_UNIT = GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_IMPLEMENTATION
```

## GV0R01-C020 close routing — 2026-09-25

The classification below is unchanged. The next unit is not another Stream-B candidate.

```
NEXT_UNIT = GV0R02_OUTCOME_BLIND_FEASIBILITY_COMPILER_DESIGN
QUEUE_CONTINUED = false
COMPILER_IMPLEMENTED = false
C020_EXECUTION_AUTHORIZED = false
```

## GV0R01-C020 inference classification audit and close — 2026-09-25

Terminology audit only. The design, the power gate, and the execution decision are unchanged. No BTC value was opened.

```
C020_STATUS = CLOSED_OUTCOME_BLIND_INFORMATIONALLY_WEAK_REFERENCE_TEST
INFERENCE_CLASSIFICATION = PLACEBO_REFERENCE_DISTRIBUTION
EXACT_RANDOMIZATION_CLAIM_STATUS = NOT_JUSTIFIED
OBSERVED_ASSIGNMENT_IN_REFERENCE_SUPPORT = false
REFERENCE_SUPPORT_RESOLUTION = 1.6473952425747334e-59
MONTE_CARLO_P_FLOOR = 1/1001
STRESS_POWER_AT_FROZEN_BAR = 0.40
C020_EXECUTION_AUTHORIZED = false
NEXT_CANDIDATE = NONE_READY
NEXT_UNIT = STREAM_B_REMAINING_CANDIDATES_BLOCKED
```

C006 and C014 stay blocked on DVOL point-in-time evidence. C016 stays blocked on paid spread history. No new candidate was created.

## GV0R01-C020 outcome-blind design and power — 2026-09-25

Design only. No C020 execution. No BTC price or quote volume opened. Protected 2025/2026 unopened.

```
OUTCOME_BLIND_GATE_RESULT = EXECUTION_INFORMATIONALLY_WEAK
PRIMARY_EVENT_COUNT = 47
US_SESSION = 09:30-16:00 America/New_York
EXECUTION_MDE_THRESHOLD = log(0.90)
ALPHA = 0.05
ALPHA_ATTAINABLE = true
BASE_POWER_AT_BAR = 0.79
STRESS_POWER_AT_BAR = 0.40
MARKET_DATA_OPENED_FOR_C020 = false
C020_PRIMARY_TEST_EXECUTED = false
NEXT_UNIT = NO_C020_EXECUTION_AUTHORIZED
```

The frozen 10 percent relative-share bar is not reached at 80 percent power in the stress scenario. The design is not retuned. A material redesign would need a new research-object id.

## GV0R01-C020 holiday calendars pinned — 2026-09-25

Data provenance only. No price or volume opened. No C020 sample, inference, or power.

```
STATUS = HOLIDAY_CALENDARS_PINNED
NYSE_ROLE = PRIMARY_EVENT_DEFINITION
CN_STATE_COUNCIL_ROLE = CONTROL_CONTAMINATION_EXCLUSION_AND_NON_DECISIVE_EXTENSION
US_OPM_ROLE = OTHER_FALSIFIER_SPECIFICITY
NYSE_FULL_WEEKDAY_CLOSURE_COUNT = 47
NYSE_EARLY_CLOSE_COUNT = 9
NYSE_UNRESOLVED_COUNT = 1
OPM_UNRESOLVED_COUNT = 1
CN_NON_WORKING_ROW_COUNT = 144
CN_COMPENSATING_WORKING_ROW_COUNT = 36
CN_UNRESOLVED_COUNT = 0
MARKET_DATA_OPENED_FOR_C020 = false
POWER_SIMULATION_PERFORMED = false
NEXT_UNIT = GV0R01_C020_OUTCOME_BLIND_DESIGN_AND_POWER_CONTINUATION
```

## Beta V0 prospective Q1/Q2 superseded; historical follow-up foundation — 2026-09-28

No protected data opened. No Q1/Q2 statistic, matched-control comparison, sign test or bootstrap computed or inspected.

```
EVALUATION = BETA_V0_PROSPECTIVE_FORWARD_EVALUATION (Q1 primary, Q2 secondary)
STATUS = SUPERSEDED_BEFORE_INSPECTION (neither passed nor failed)
REASON = product will display historical follow-up / base-rate statistics before the preregistered stopping rule
LIVE_BETA_COLLECTION_STARTED_BEFORE_AMENDMENT = true
Q1_Q2_STATISTIC_INSPECTED = false
ANALYSIS_SCRIPT_FROZEN = false
DETECTOR_RULE_CHANGED_BECAUSE_OF_OUTCOMES = false
FUTURE_CONFIRMATION = requires a new prospective contract and a new future observation window
FOLLOW_UP_FOUNDATION = docs/BETA_HISTORICAL_FOLLOW_UP_V0.md (EVENT_COMPARABILITY_V0; not wired; no replay)
```

## Self-referential generic finite-sample screen — 2026-09-30

First official held-out generic validation of `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1` at implementation `ebb26aca6ed37c12bbf3b3f578973d3078407d99`. Synthetic global-null worlds only. No BitMEX path, no D7 geometry admission, no confirmatory beacon stream.

```
DECISION = FINITE_SAMPLE_STRESS_VALIDATED
GENERIC_OUTER_WORLD_N = 1600
R_VALIDATION = 999
TOTAL_REJECT_COUNT = 75
AGGREGATE_GATE = PASS
REGIONAL_REJECTS = 10, 4, 14, 13, 9, 6, 6, 13
PROFILE_VALIDATION_EXECUTED = true
PROFILE_VALIDATED = true
CLAIMS_TRUE_TYPE_I_AT_MOST_0_06 = false
D7_GEOMETRY_ADMISSION_EXECUTED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
STATISTICAL_RERUNS = 0
INFRASTRUCTURE_RETRIES = 1
PROFILE_NEXT_ACTION = READY_FOR_D7_EXACT_GEOMETRY_ADMISSION
```

The screen does not validate BitMEX mixing and does not confirm D7. Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_GENERIC_VALIDATION_V1.md`.

## D7 exact-geometry admission stop — 2026-09-30

First official `D7_EXACT_GEOMETRY_ADMISSION` attempt for `SELF_REFERENTIAL_TIME_SERIES_CONTRAST_V1`. Stopped before world 0. The published gap clock interval and the published year masses do not locate the eligible-index break inside the 4079 eligible 2016 rows. No admission world, admission seed, or confirmatory stream was generated. The generic screen was not rerun.

```
DECISION = D7_GEOMETRY_ADMISSION_EXECUTION_FAILED:ELIGIBLE_INDEX_GAP_BREAK_UNPUBLISHED
D7_EXACT_GEOMETRY_ADMISSION_STARTED = false
D7_GEOMETRY_ADMISSION_EXECUTED = false
WORLDS_COMPLETED = 0
D7_ADMISSION_REJECT_COUNT = UNSET
D7_PROFILE_ADMISSION = NOT_DECIDED
PROFILE_VALIDATED = true
GENERIC_DECISION = FINITE_SAMPLE_STRESS_VALIDATED
GENERIC_REJECT_COUNT = 75
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
STATISTICAL_RERUNS = 0
POWER_GATE_EXECUTED = false
NEXT_ACTION = D7_EXACT_GEOMETRY_ADMISSION_STOPPED_BEFORE_WORLD_0
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_GEOMETRY_ADMISSION_V1.md`.

## D7 eligible-index gap break — 2026-09-30

Geometry metadata only. The single missing scalar is the eligible-index position of the published structural gap. No admission world, admission seed, lag-1 state, or D7 effect was produced.

```
MINIMUM_REQUIRED_GEOMETRY = ELIGIBLE_INDEX_GAP_BREAK
ELIGIBLE_COUNT_BEFORE_GAP = 3503
ELIGIBLE_COUNT_AFTER_GAP = 576
ELIGIBLE_INDEX_GAP_BREAK = 3503
ELIGIBLE_2016_TOTAL = 4079
ELIGIBLE_2017_TOTAL = 8757
ELIGIBLE_2018_TOTAL = 8759
ELIGIBLE_2019_TOTAL = 8759
T = 30354
CONSISTENT = true
GEOMETRY_EXTRACTOR_TARGET_BLIND = true
D7_EXACT_GEOMETRY_ADMISSION_STARTED = false
D7_GEOMETRY_ADMISSION_EXECUTED = false
D7_PROFILE_ADMISSION = NOT_DECIDED
PROFILE_VALIDATED = true
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
NEXT_ACTION = READY_TO_RETRY_D7_EXACT_GEOMETRY_ADMISSION_PREFLIGHT
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_ELIGIBLE_INDEX_GAP_BREAK_V1.md`.

## D7 exact-geometry admission — 2026-09-30

First official D7 admission that ran worlds. Preflight used execution HEAD `e69fc5c56ba9d4c5d31915f44b30cebf66c5275b` and an empty statistical diff against `ebb26aca6ed37c12bbf3b3f578973d3078407d99`. Geometry break `3503` was taken from the published amendment. The extractor was not rerun.

```
D7_EXACT_GEOMETRY_ADMISSION_STARTED = true
D7_GEOMETRY_ADMISSION_EXECUTED = true
D7_ADMISSION_OUTER_WORLD_N = 1600
R_VALIDATION = 999
D7_ADMISSION_REJECT_COUNT = 73
DECISION = HYPOTHESIS_GEOMETRY_ADMISSION_PASS
D7_PROFILE_ADMISSION = PASS
PROFILE_VALIDATED = true
PRIMARY_COMPLETED = 1600
EXECUTION_FAILURES = 0
STATISTICAL_RERUNS = 0
INFRASTRUCTURE_RETRIES = 0
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
POWER_GATE_EXECUTED = false
NEXT_ACTION = READY_FOR_D7_POWER_GATE
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_EXACT_GEOMETRY_ADMISSION_V1.md`.

## D7 power gate — 2026-09-30

Outcome-blind power gate after the sealed generic screen and the sealed D7 admission. Population contrast `1/20`. Detection is the primary reject plus the 2-of-3 temporal gate on `{2017, 2018, 2019}`.

```
D7_POWER_GATE_STARTED = true
D7_PRACTICAL_EFFECT = 1/20
D7_REQUIRED_POWER_BASE = 0.80
D7_REQUIRED_POWER_STRESS = 0.50
N_POWER_PER_FAMILY = 2000
R_VALIDATION = 999
POWER_BASE = 2000/2000
POWER_YEAR_HETEROGENEOUS = 2000/2000
POWER_CELL_HETEROGENEOUS = 2000/2000
DECISION = D7_POWER_GATE_PASS
D7_HYPOTHESIS_FAILED = false
PROFILE_VALIDATED = true
D7_PROFILE_ADMISSION = PASS
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
STATISTICAL_RERUNS = 0
NEXT_ACTION = READY_FOR_FINAL_TARGET_OPENING_AUTHORIZATION_REVIEW
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_POWER_GATE_V1.md`.

## D7 target-opening authorization review — 2026-10-01

Outcome-blind review of whether one irreversible D7 opening is authorized. No target read, no effect, no confirmatory stream, no new simulation. The sealed power result is unchanged.

```
PROVENANCE_CHAIN_COMPLETE = true
STATISTICAL_IMPLEMENTATION_CHANGED = false
POWER_POPULATION_EFFECT_EXACT = true
POWER_TARGET_BLIND = true
STATISTICAL_DUPLICATE_WORLDS = 0
TEMPORAL_GATE_FULLY_SPECIFIED = true
CONFIRMATORY_RNG_READY_BUT_UNGENERATED = false
DECISION = D7_TARGET_OPENING_NOT_AUTHORIZED:FINAL_PASS_CONJUNCTION_NOT_UNIQUE
D7_HYPOTHESIS_FAILED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_TARGET_OPENING_AUTHORIZATION_REVIEW_V1.md`.

## D7 final contract integrity repair — 2026-10-01

Outcome-blind contract repair after the authorization review. No target read, no effect, no confirmatory stream, no beacon fetch, and no rerun of generic validation, D7 admission, or D7 power.

```
OFFICIAL_POWER_DETECTION_BOOLEAN = PRIMARY_COMPLETED AND statistical_reject AND temporal_gate
TEMPORAL_POWER_ALREADY_EXECUTED = true
TEMPORAL_GATE_POWER_VALIDATED_IN_OFFICIAL_D7_POWER_RUN = true
CLAIM_CHANGE: magnitude >= 0.05 is no longer a D7 confirmation PASS condition
D7_DIRECTIONAL_CONFIRMATION_PASS = PRIMARY_COMPLETED AND STATISTICAL_REJECT AND TEMPORAL_PASS AND INTEGRITY_PASS
ADAPTER_DIGEST_TARGET_BLIND = true
CONFIRMATORY_BIT_GENERATOR = NUMPY_PCG64
POST_OPEN_UNTHRESHOLDED_DIAGNOSTICS_CANNOT_CHANGE_PRIMARY_LABEL = true
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
TARGET_OPENING = FORBIDDEN
NEXT_ACTION = READY_TO_REPEAT_FINAL_TARGET_OPENING_AUTHORIZATION_REVIEW
```

Record: `docs/research/D7_FINAL_CONTRACT_INTEGRITY_REPAIR_V1.md`.

## D7 target-opening authorization review V2 — 2026-10-01

Outcome-blind repeat after the contract/integrity repair. No target read, no effect, no beacon fetch, no confirmatory stream, and no rerun of validation, admission, or power. The freeze contract is unchanged.

```
FREEZE_MANIFEST_INTACT = true
FINAL_PASS_CONJUNCTION_UNIQUE = true
MAGNITUDE_RULE_FULLY_SPECIFIED = true
TEMPORAL_POWER_ALREADY_EXECUTED = true
ADAPTER_DIGEST_TARGET_BLIND = true
INTEGRITY_PASS_NONADAPTIVE = true
SERVER_FREEZE_TIME_ACCEPTABLE = true
BEACON_RULE_EXECUTABLE = true
CONFIRMATORY_RNG_CONTRACT_EXECUTABLE = true
CONFIRMATORY_RNG_READY_BUT_UNGENERATED = true
SINGLE_RUN_SEMANTICS_FROZEN = true
DECISION = D7_TARGET_OPENING_AUTHORIZED
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CONFIRMATORY_RNG_GENERATED = false
BEACON_FETCHED = false
TARGET_OPENING = FORBIDDEN
```

Record: `docs/research/INFERENCE_PROFILE_SELF_REFERENTIAL_D7_TARGET_OPENING_AUTHORIZATION_REVIEW_V2.md`.

## D7 confirmatory target opening — 2026-10-01

Authorized confirmatory execution. Identity pins matched the freeze. The first NIST Beacon 2.0 pulse at or after `2026-10-01T07:09:59Z` is chain 2 pulse `1965184` at `2026-10-01T07:10:00.000Z`. Its `outputValue` matches the uint32 serialization and its `certificateId` matches the certificate DER. PKCS#1 v1.5 SHA-512 verification fails: the certificate key is 2048 bits and `signatureValue` is 512 bytes. The run stopped there.

```
EXECUTION_STATUS = D7_CONFIRMATORY_EXECUTION_FAILED:BEACON_SIGNATURE_INVALID
BEACON_FETCHED = true
BEACON_SIGNATURE_VALID = false
RAW_BEACON_RECORD_SHA256 = 276779a2d1f7a627acd4e891ddf5233feca22b5db7e194a9f3b1606894720c9a
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
PRIMARY_RESULT_SEALED = false
D7_DIRECTIONAL_CONFIRMATION_PASS = unevaluated
```

Record: `docs/research/D7_CONFIRMATORY_TARGET_OPENING_V1.md`.

## D7 beacon verifier repair — 2026-10-01

Pre-seed repair. Pulse `1965184` was classified from its preserved bytes: RSA modulus 2048 bits / 256 bytes, signature 512 bytes, `s < n` false. Classification `PULSE_1965184_OBJECTIVELY_INVALID`. The verifier no longer requires a 512-byte signature; PKCS#1 v1.5 length is `ceil(modulus_bits / 8)` of the certificate named by that pulse. Offline regressions: 4096-bit pulse `1923756` (`2026-09-02T12:00:00.000Z`) verifies; pulse `1965184` is rejected; a TEST-ONLY RSA-2048 pulse with a 256-byte signature verifies. No pulse after `1965184` was fetched. No seed, no RNG, no target parse, no D7 estimand.

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
CANDIDATES_AFTER_1965184_FETCHED = false
NEXT_ACTION = READY_FOR_SEQUENTIAL_NIST_BEACON_SCAN_FROM_AFTER_1965184
```

Record: `docs/research/D7_BEACON_VERIFIER_REPAIR_V1.md`.

## D7 confirmatory beacon scan — 2026-10-01

Outcome-blind sequential scan after pulse `1965184`. Verifier bytes unchanged (`d7f7687`, blob `bed8a2aa33599b7ce4c0915eb410ad7413747b1d`). Examined `2/1965185` at `2026-10-01T07:11:00.000Z` through `2/1965225` at `2026-10-01T07:51:00.000Z`: 41 pulses, all `INVALID` (`PULSE_{index}_OBJECTIVELY_INVALID`), modulus 256 bytes, signature 512 bytes, same named certificate as pulse `1965184`. All 41 continuity edges passed. `VALID` count is 0. The successor of `2/1965225` returned HTTP 404 and stopped the scan as incomplete. No seed, no RNG, no target parse, no D7 estimand.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965225
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965225
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

Record: `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.md`.

## D7 confirmatory beacon scan resume — 2026-10-01

Same scan identity. Invocation 2 retried the chronological successor of `2/1965225` and fetched `2/1965226` at `2026-10-01T07:52:00.000Z`. Eight pulses, `2/1965226` through `2/1965233` at `2026-10-01T07:59:00.000Z`, classified `INVALID`. Continuity on those edges passed. The successor of `2/1965233` returned HTTP 404. Prior 41 rows were not rewritten. Cumulative examined: 49. No seed, no RNG, no target parse, no D7 estimand.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965233
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965233
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

Record: `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.md`.

## D7 confirmatory beacon scan resume 3 — 2026-10-01

Same scan identity. Invocation 3 retried the chronological successor of `2/1965233` and fetched `2/1965234` at `2026-10-01T08:00:00.000Z`. Seventeen pulses, `2/1965234` through `2/1965250` at `2026-10-01T08:16:00.000Z`, classified `INVALID`. Continuity on those edges passed. The successor of `2/1965250` returned HTTP 404. Prior 49 rows were not rewritten. Cumulative examined: 66. No seed, no RNG, no target parse, no D7 estimand.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965250
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965250
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

Record: `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.md`.

## D7 confirmatory beacon scan resume 4 — 2026-10-01

Same scan identity. Invocation 4 retried the chronological successor of `2/1965250` and fetched `2/1965251` at `2026-10-01T08:17:00.000Z`. Six pulses, `2/1965251` through `2/1965256` at `2026-10-01T08:22:00.000Z`, classified `INVALID`. Continuity on those edges passed. The successor of `2/1965256` returned HTTP 404. Prior 66 rows were not rewritten. Cumulative examined: 72. No seed, no RNG, no target parse, no D7 estimand.

```
SELECTED_CONFIRMATORY_BEACON = NONE
LAST_COMPLETELY_CLASSIFIED_CANDIDATE = 2/1965256
NEXT_REQUIRED_CANDIDATE = chronological successor of 2/1965256
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
NEXT_ACTION = BEACON_CANDIDATE_FETCH_OR_VERIFICATION_INCOMPLETE
```

Record: `docs/research/D7_CONFIRMATORY_BEACON_SCAN_V1.md`.

## D7 confirmatory seed-source amendment — 2026-10-01

Pre-target amendment. `SEED_SOURCE_CHANGE = NIST_BEACON_2_0 -> DETERMINISTIC_FIXED_SEED_V1`. The NIST scan is `SUPERSEDED_BY_SEED_SOURCE_AMENDMENT` and its 72 `INVALID` rows, cursor, pulse `1965184` record, and verifier repair remain. The seed message is the exact UTF-8 literal with digest `5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e`. It does not use target bytes, the canonical source digest, or `FREEZE_MANIFEST_SHA256`. `EXTERNAL_UNPREDICTABILITY_GUARANTEE = REMOVED`. `PRE_TARGET_SEED_COMMITMENT = PRESERVED`. `STATISTICAL_PROCEDURE_CHANGED = false`. No confirmatory PCG64 stream, no target parse, no theta.

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
SELECTED_CONFIRMATORY_BEACON = NONE
```

Record: `docs/research/D7_CONFIRMATORY_SEED_SOURCE_AMENDMENT_V1.md`.

## D7 deterministic-seed opening authorization — 2026-10-01

Mechanical review after amendment commit `b603f55d7b12492bf813abac1537aa21f85932e4` was served by the GitHub API at `2026-10-01T08:46:42Z`. `SEED_SOURCE_AMENDMENT_COMMITTED = true`. `TARGET_WAS_UNOPENED_AT_AMENDMENT_COMMIT = true`. Digest matches `5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e`. `STATISTICAL_PROCEDURE_CHANGED = false`. Focused seed and verifier tests passed. Decision `D7_DETERMINISTIC_SEED_OPENING_AUTHORIZED`. Target remains unopened. No confirmatory bootstrap stream.

```
CONFIRMATORY_RNG_GENERATED = false
D7_BITMEX_PRIMARY_TARGET_OPENED = false
D7_PRIMARY_EFFECT_COMPUTED = false
```

Record: `docs/research/D7_DETERMINISTIC_SEED_OPENING_AUTHORIZATION_V1.md`.

## D7 confirmatory primary result — 2026-10-01

One authorized opening under `DETERMINISTIC_FIXED_SEED_V1`, amendment commit `b603f55d7b12492bf813abac1537aa21f85932e4`. Seed digest `5d81a9be7f96abab8a92539e2527006cf97340a8f5ca7fe966b8d6293f4ba63e`. Geometry `T=30354`, year masses `4079/8757/8759/8759`, gap break `3503`, segments `[3503, 26851]`, `B=L=721`. `theta_hat=0.12932529232325488`, `V_obs=2.458771532240802`, `SE=0.009000178507085975`, `T_obs=14.369191924519624`. `R=9999`, exceedance `0`, `p=0.0001`, `STATISTICAL_REJECT=true`. Year theta `2016=0.1357945428437761` (diagnostic), `2017=0.1556649226614804`, `2018=0.1268447223183365`, `2019=0.09454730105201403`. `TEMPORAL_PASS=true`. `L=0.1138795303766755`, `MAGNITUDE_AT_0_05_SUPPORTED=true`. `INTEGRITY_PASS=true`. `D7_DIRECTIONAL_CONFIRMATION_PASS=true`. Label `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`. Sealed artifact SHA-256 `b4efa972cec9acfacb2987be7aef3ad1ed239c8279977374a18265dfe60df503`. No rerun.

```
CONFIRMATORY_RNG_GENERATED = true
D7_BITMEX_PRIMARY_TARGET_OPENED = true
D7_PRIMARY_EFFECT_COMPUTED = true
PRIMARY_RESULT_SEALED = true
```

Record: `docs/research/D7_CONFIRMATORY_PRIMARY_RESULT_V1.md`.

## Decision-layer research program V0 — owner decision — 2026-10-01

Program routing only. No new scientific outcome. No window consumed. The beta is frozen as it is. The research goal is evidence for a future decision layer. The first mechanism is a TWAP execution footprint on Binance spot `aggTrades`, which must be incremental over matched net taker flow. The Delta-direction arm is not run: H05 already rejected it.

```
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
H05_REOPENED = false
MARKET_07_CREATED = false
NEXT_UNIT = TWAP_FOOTPRINT_OUTCOME_BLIND_FEASIBILITY
```

Record: `docs/research/DECISION_LAYER_RESEARCH_PROGRAM_V0.md`.

## D7 campaign close — 2026-10-01

Closeout record only. No new scientific outcome. The D7 campaign is closed:
- discovery `D7_PROMISING_PROTOTYPE`;
- BitMEX confirmation `CONFIRMED_UNDER_MAINTAINED_ASSUMPTIONS`, sealed `b4efa972…`;
- one beta claim through `BETA_D7_REGIME_CONTEXT_GATE_V1`.

Claim scope: the baseline matched year × four RV quartiles. Persistence beyond within-bucket volatility and relative volume was not tested.

```
D7_CAMPAIGN_CLOSED = true
D7_RERUN_AUTHORIZED = false
D7_SECOND_SEED_AUTHORIZED = false
D7_CHILD_CARDS_AUTHORIZED = false
D7_LIVE_HIT_RATE_MONITORING = NOT_AUTHORIZED
PROTECTED_2025_OPENED = false
PROTECTED_2026_OPENED = false
```

Record: `docs/research/D7_CAMPAIGN_CLOSE_V1.md`.

## Hypothesis evaluation contract V1 review — 2026-10-01

Desk review only. No market file was opened and no historical verdict changed. 19 recorded objects were replayed under V1 using recorded numbers, including the recorded D12 per-transition values and the C013 weekly series:
- 0 failures turned into support;
- C013 would be `HETEROGENEOUS_UNEXPLAINED` (heterogeneity `p < 0.0001`; 2023 and 2024 significantly opposite);
- D12 is not downgraded (heterogeneity `p = 0.087`);
- D7 needs a claim-scope note, and D11 needs a prior-volatility check before any confirmation.

Three over-strict draft rules were fixed:
- the hard share rule, which rejects 33–84% of constant effects at these sizes;
- the claim types, which now include `CONTEXT_DESCRIPTIVE`;
- replication, which now allows a prospective surface.

The red team found ten paths, each closed by a contract rule. Only `SUPPORTED_UNCONDITIONAL` and `SUPPORTED_CONDITIONAL` are promotable, and only after time-disjoint replication, the frequency gate and a claim-specific gate.

```
V1_RED_TEAM = PASS_WITH_CLOSING_RULES
V1_STATUS = READY_FOR_OWNER_ADOPTION
NEXT_UNIT = OWNER_ADOPTION_OF_HYPOTHESIS_EVALUATION_CONTRACT_V1
```

Records: `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1_REVIEW.{md,json}`, `docs/research/HYPOTHESIS_EVALUATION_CONTRACT_V1.md`.

## Hypothesis evaluation contract V1 adopted — 2026-10-01

Owner adoption. No scientific outcome. The adopted text is `HYPOTHESIS_EVALUATION_CONTRACT_V1.md` at merge commit `0db19833adcfa97feac754c3a2108b86122469c5`. It includes the pre-adoption amendments A1 (fixed stopping rule for prospective replication) and A2 (no stability claim from heterogeneity tests). It is not retroactive. It supersedes the decision-layer scoped profile.

```
HYPOTHESIS_EVALUATION_CONTRACT_V1 = ADOPTED
RETROACTIVE = false
NEXT_UNIT = GV0R02_COMPILER_AND_GENERATOR_CONTRACT_V1_MAPPING
```

## GV0R02 compiler V1 mapping — 2026-10-01

Tooling only. No scientific outcome, no market data. The compiler V1 layer is implemented over the unchanged V0 compiler. The golden cases C012, C004 and C020 keep their statuses, and the positive control stays feasible. The stale layout assertion in `test_gv0r02_feasibility_compiler_design.py` had failed since GV0R03; it is narrowed to its intent.

```
GV0R02_SCHEMA_V1 = IMPLEMENTED
OLD_RESULTS_RESCORED = false
NEXT_UNIT = GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING
```

Record: `docs/research/GV0R02_FEASIBILITY_COMPILER_V1_MAPPING.md`.

## Seed recorded — absorption plus indicator divergence after a decline — 2026-10-01

Provenance record only. This is the owner's prior discretionary rule: after a pronounced decline, an observable buyback plus bullish divergence in at least 2 of 3 indicator families (RSI 14 and 21, MACD 12/26/9, CVD). The timeframe is a separate axis.
- It is not a card, nothing is frozen, and no market data was opened.
- It is close to H02, H03 and H05, which stay closed. This seed is not a rescue of any of them.
- Records: `docs/research/SEED_ABSORPTION_DIVERGENCE_V0.md` (regular divergence, reversal) and `docs/research/SEED_HIDDEN_DIVERGENCE_CONTINUATION_V0.md` (hidden divergence, continuation). These are two separate seeds.

## TWAP execution footprint — sealed end-to-end run V1 — 2026-10-02

One-shot execution of `DECISION_LAYER_RESEARCH_PROGRAM_V0.md` §8, run with no human approval between phases. The spec `TWAP_SEALED_SPEC_V1.json` (SHA-256 `961c7578…`) was frozen and pushed at `5a0cd66` before the first scientific outcome.

**Data and detector.** Binance spot BTCUSDT `aggTrades`, checksum-verified: discovery 2020-01..2024-12, replication 2017-08..2019-12. The detector was selected outcome-blind on 2024-06: 250 ms tolerance, K = 20, 15 min.

**Consumed windows.** Discovery 2020–2024 is now consumed for this footprint. Replication 2017-08..2019-12 is consumed for counts only; no outcome was computed on it.

**Results:**
- **Support.** 1,207 persistence-eligible episodes on 702 days.
- **H1 (post-detection same-side flow).** Ratio 1.264, one-sided p < 0.0001: pass, on discovery only. It is partly mechanical, because it includes the detected algorithm's own remaining slices. Independent replication is insufficient.
- **Price cells.** No cell is supported. Day-block bootstrap with Holm m = 3 and a 10 bps floor:
  - H2_1h: +5.0 bps, Holm p 0.17;
  - H2_6h: −0.4 bps;
  - H3 post-end: +0.5 bps.
- **Replication.** Support 19 < 100, so `INFERENCE_INSUFFICIENT`.
- **Timing (descriptive).** The median remaining execution at detection is 11 min.

```
TWAP_SEALED_RUN_V1 = MECHANISM_SUPPORTED_PRICE_EFFECT_NOT_SUPPORTED
RERUN_AUTHORIZED = false
NEARBY_VARIANTS_AUTHORIZED = false
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = OWNER_DECISION_AFTER_TWAP_SEALED_RUN_V1
```

Record: `docs/research/TWAP_SEALED_RUN_V1_RESULT.md`, artifacts `docs/research/twap_sealed_run_v1/`. The record carries a post-run erratum: the §8 wording "real counts are never a selection criterion" conflicts with the zero-denominator admissibility rule. The selection outcome is unchanged.

## TWAP V1 closed — owner decision — 2026-10-02

Owner decision after the sealed run (#287, merged at `becb6cd`). No new outcome was opened. The TWAP branch is closed: no rerun, no nearby detector, horizon or floor variant, and no product directional claim. The closure is limited to the tested region and does not close the algorithmic-execution family.

```
TWAP_V1 = CLOSED
NEXT_UNIT = GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING
```

## Generator feasibility contract V1 mapping — 2026-10-02

Tooling only. No LLM call, no market data and no scientific outcome. `GV0R03_GENERATOR_FEASIBILITY_CONTRACT_V1` maps a shortlisted card's planning object to `GV0R02_SCHEMA_V1`.
- The V1 design fields live on the planning object, not on the frozen V02 card.
- The contract checks shape only; the compiler adjudicates the V1 rules.
- Owner decision, same day: the complexity ladder `ATOMIC` / `CONDITIONAL` / `INTERACTION` / `COMPOSITE`. It applies on the planning object.
  - For interaction and composite claims, each component's main effect is controlled in the baseline and the joint term is tested for its increment. No component needs prior support.
  - The shortlist quota is 2/2/1. An unfilled seat passes down the ladder, never up.

```
GENERATOR_FEASIBILITY_CONTRACT_V1 = IMPLEMENTED
COMPLEXITY_LADDER = PLANNING_CONTRACT_AND_SHORTLIST_QUOTA_IMPLEMENTED
GENERATOR_CARD_SCHEMA_CHANGED = false
NEXT_UNIT = GENERATOR_V0_COMPLEXITY_LADDER_AMENDMENT
```

Record: `docs/research/GENERATOR_FEASIBILITY_CONTRACT_V1_MAPPING.md`.

## Generator complexity ladder amendment (V03) — 2026-10-02

Owner-authorized generator design amendment. Offline only: no LLM call, no market data and no scientific outcome. `GENERATOR_CONTRACT_V03` adds rung-assigned slots (16/14/7/3, assigned before the LLM call), `COMPLEXITY_CLASS` and `COMPONENTS` on the card, two intake rules, two critic-enforced rules and the 2/2/1 shortlist quota. V02 is byte-identical. Generator cards are not counted as hypotheses.

```
GENERATOR_CONTRACT_V03 = IMPLEMENTED
LLM_CALLS = 0
NEXT_UNIT = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN
```

Record: `docs/research/GENERATOR_V0_COMPLEXITY_LADDER_AMENDMENT.{md,json}`.

## Generator V0 pre-campaign hardening — 2026-10-02

Offline only: no LLM call, no market data and no scientific outcome.
- **Finalizer.** The memory finalizer accepts V03 campaigns: it validates the ladder fields and critic outputs and copies them verbatim. A failed `RUNG_CONSISTENT` maps to `METHOD_RUNG_INCONSISTENT`. V02 deltas and the rules digest are unchanged.
- **Budget stop.** V03 budget-stop semantics are frozen: `INCOMPLETE_BUDGET_STOP`, no shortlist, resume of the same run only, and the shortlist is built once after a full resume.

```
MEMORY_FINALIZER_V03 = IMPLEMENTED
V03_BUDGET_STOP = INCOMPLETE_BUDGET_STOP
NEXT_UNIT = GENERATOR_V0_FRESH_SHADOW_CAMPAIGN
```

Record: `docs/research/GENERATOR_V0_PRE_CAMPAIGN_HARDENING.{md,json}`.

## Generator V0 ladder-40 V03 r01 paused — 2026-10-02

Owner-authorized fresh `GENERATOR_CONTRACT_V03` shadow campaign, absolute cap USD 12, OpenAI network mode `DIRECT`. It stopped before any card existed.

The first generator call (`generation:0`, Anthropic `claude-opus-5-5`) was dispatched and the client timed out. State `UNCERTAIN`. Error `TimeoutError`. No message id. Reserved USD 2.210772. Recorded cost none. Call key `ae215fdf93381475470783cc79bb51e96f3902bc1b126abea12aedb42ca32304`.

No OpenAI call was sent. No candidate, no critic judgment, and no shortlist exist. Memory was not finalized. Protected 2025/2026 was not opened. No market outcome was tested.

```
LADDER40_V03_R01 = PAUSED_UNCERTAIN_CALL
RERUN_AUTHORIZED = false
NEW_CAMPAIGN_AUTHORIZED = false
REPLAY_UNCERTAIN_CREATE = false
MEMORY_FINALIZER = NOT_RUN
PROTECTED_2025_2026_OPENED = false
MARKET_OUTCOMES_TESTED = false
NEXT_UNIT = OWNER_RECONCILE_OF_LADDER40_V03_R01_UNCERTAIN_GENERATOR_CALL
```

Record: `docs/research/GENERATOR_V0_LADDER40_V03_R01_PAUSE.{md,json}`. Journal snapshot: `docs/research/generator_v0_ladder40_v03_r01/run.sqlite`.

## Generator V0 r01 frozen; resumable Anthropic generator transport — 2026-10-02

**Owner decision on r01.** `ladder-40-card` r01 is a technically failed run.
- It is frozen: no `UNKNOWN` reconcile, no replay and no resume.
- Its single uncertain generator call is recorded later as an offline `BILLED` reconcile, when the Anthropic console shows the exact cost.
- Nothing scientific was consumed: no card, no critic judgment, no shortlist, no market data.

**`ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1`** is an infrastructure amendment, implemented offline.
- **Message Batches.** The V03 ladder GENERATOR goes through one-request Message Batches:
  - the `custom_id` is journaled before the create POST;
  - the batch id is journaled at acceptance, and the call is then only polled;
  - a lost create acknowledgement is found by listing;
  - an absent create is closed NOT_BILLED;
  - poll failures leave the call PENDING.
- **External journal checkpoints** run at acceptance, rounds, review blocks, the result and stops.
- **Pricing.** Batch pricing is half of standard.
- **Unchanged.** The V02 routes and the V03 scientific design.

```
LADDER40_V03_R01 = INFRASTRUCTURE_FAILED_FROZEN
R01_RECONCILE = BILLED_LATER_WITH_CONSOLE_COST (not UNKNOWN; no replay; no resume)
ANTHROPIC_GENERATOR_RESUMABLE_TRANSPORT_V1 = IMPLEMENTED_OFFLINE
LLM_CALLS = 0
SCIENTIFIC_DESIGN_CHANGED = false
PROTECTED_2025_2026_OPENED = false
MARKET_OUTCOMES_TESTED = false
NEXT_UNIT = LADDER40_V03_R02 (identical V03 design; fresh owner live authorization required)
```

Records:
- `docs/research/GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.{md,json}`;
- `docs/research/GENERATOR_V0_LADDER40_V03_R01_PAUSE.{md,json}` (owner decision section).

## Generator V0 r01 + r02 budget lineage — 2026-10-02

The owner set one combined exposure ceiling for `ladder-40-card-v03-r01` and `ladder-40-card-v03-r02`.
- **r01 charge.** Until exact provider billing evidence exists, r01 is charged its full reservation.
- **r02 is not a fresh USD 12 allocation.**
- **A lower r01 cost is not reclaimed automatically.** Any increase of the r02 total needs a new, recorded owner decision and must keep `R01_ACTUAL_BILLED_USD + R02_AUTHORIZED_TOTAL_USD <= 12.000000`.
- **Nothing was run or consumed.**

```
LINEAGE_CAP_USD = 12.000000
R01_CONSERVATIVE_CHARGE_USD = 2.210772
R02_INITIAL_CAP_USD = 9.789228
LADDER40_V03_R01 = INFRASTRUCTURE_FAILED_FROZEN
R01_RECONCILE = BILLED_WITH_EXACT_PROVIDER_EVIDENCE (only)
R02_LIVE_EXECUTION_AUTHORIZED = false
LLM_CALLS = 0
```

Record: `docs/research/GENERATOR_V0_ANTHROPIC_RESUMABLE_TRANSPORT.{md,json}` (section "r02 budget lineage", key `R02_BUDGET_LINEAGE`).

## Generator V0 r02 paused; resumable OpenAI critics; derived continuation — 2026-10-02

`ladder-40-card-v03-r02` is an infrastructure pause, not a scientific result. All four generator rounds completed on Anthropic Message Batches (USD 2.192768; 40 slots, 30 valid, 10 hard fail). The synchronous feasibility call for C024 timed out after dispatch with no response id. It stays `UNCERTAIN` at its reserved USD 0.005302. The source charged total is USD 3.659239. The source journal was not modified and C024 was not reconciled. PR #299 (`bb13d8f26a93713fa6fb956703c5207486b6a570`) remains the durable checkpoint. A byte-identical copy is `docs/research/generator_v0_ladder40_v03_r02/run.sqlite` (SHA256 `ffa179220d12986520c214f7a1ad1cfecd084848f9de0158fcd43476d9447a37`).

`OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1` moves V03 feasibility and the selector from synchronous Chat Completions to background Responses. Every paid V03 role is now resumable. V02 routing is unchanged. No prompt, schema, model, effort or shortlist rule changed.

`ladder-40-card-v03-r02-derived-critics-v1` is a derived continuation, not a new campaign. It imports the four generator rounds and treats every source critic call as a prior attempt. The 30 valid cards are to be reviewed again under one routing identity. The destination starts at USD 3.659239 charged. The r02 cap stays USD 9.789228 (USD 6.129989 left). The offline remaining bound is base USD 14.518795 and stress USD 29.035834. Neither fits. The cap was not raised. No live call was made.

```
LADDER40_V03_R02 = PAUSED_UNCERTAIN_CALL / IMMUTABLE_SOURCE_FOR_DERIVED_CONTINUATION
OPENAI_V03_ALL_CRITICS_RESUMABLE_TRANSPORT_V1 = IMPLEMENTED_OFFLINE
DERIVED_RUN_ID = ladder-40-card-v03-r02-derived-critics-v1
DERIVED_INITIAL_CHARGED_USD = 3.659239
AVAILABLE_R02_USD = 6.129989
BASE_REMAINING_BOUND_USD = 14.518795
STRESS_REMAINING_BOUND_USD = 29.035834
FITS_BASE = false
FITS_STRESS = false
DERIVED_CONTINUATION_LIVE_AUTHORIZED = false
LLM_CALLS = 0
SCIENTIFIC_DESIGN_CHANGED = false
PROTECTED_2025_2026_OPENED = false
MARKET_OUTCOMES_TESTED = false
```

Record: `docs/research/GENERATOR_V0_V03_RESUMABLE_CRITICS_AND_DERIVED_CONTINUATION.{md,json}`.

## GV0V03L40 C033 outcome-blind count — 2026-10-02

Pinned `CORE_BTC_BINANCE_V0` and `CORE_ETH_BINANCE_V0` monthly archives for `2020-01..2024-12` were read to count the frozen C033 primary state. The read stops at 2024-12. No `RV_DECAY`, post-T return, or target value was computed. The window is not a consumed confirmatory result.

```
TOTAL_ELIGIBLE_SHOCKS = 2926
KEPT_AFTER_6H = 1383
TOTAL_ALL4_EVENTS = 0
FEASIBILITY_STATUS = FEASIBLE_FOR_PREREGISTRATION
C033_NEXT = PREREGISTRATION_DESIGN
EXECUTION_AUTHORIZED = false
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
```

Record: `docs/research/GV0V03L40_C033_V1_FEASIBILITY.md`.

## GV0V03L40 C033 V2 compiler repair — 2026-10-02

The sealed C033 planning object was recompiled under `GV0R02_SCHEMA_V2` / `GV0R02_POLICY_V2`. V1 semantics were not changed, and the V1 `FEASIBLE_FOR_PREREGISTRATION` artifact remains the V1 output. The repair is outcome-blind. The 2020–2024 count window is not a consumed confirmatory result.

```
MECHANISM_ACTIVE_N = 0
MECHANISM_INACTIVE_N = 1383
FEASIBILITY_STATUS = DEFINITION_INCOMPLETE
BLOCKERS = PRIMARY_MECHANISM_SUPPORT_ZERO, ALPHA_UNATTAINABLE, PROSPECTIVE_MECHANISM_SUPPORT_UNGUARANTEED
C033_NEXT = STOP / NOT_PREREGISTRABLE_UNDER_FROZEN_DESIGN
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
SCIENTIFIC_DESIGN_CHANGED = false
```

Record: `docs/research/GV0V03L40_C033_V2_FEASIBILITY.md`.

## SEED-0001 regular divergence card registered — 2026-10-02

The owner's SEED-0001 decisions (2026-10-02) are frozen into a twin preregistration: `docs/research/SEED0001_REGULAR_DIVERGENCE_PREREG.{md,json}`.
- **Retrospective card.** BTCUSDT perp 1h, decisions 2023-01-01..2024-12-28, labelled `RETROSPECTIVE_EVIDENCE` (never a holdout or final confirmation).
- **Prospective confirmation.** Decisions from 2026-10-05; stop at 30 Arm-A episodes or 2028-10-05, minimum 20.
  - The protected 2026 segment may be pinned only by metadata; running the detector on it needs an owner decision.
  - The single analysis needs a separate owner decision.
- **Primary family.** P1 = A vs B and P2 = A vs C on +1R before −1R within 48h, Holm, both required. +2R and 96h are secondary.
- **ETH.** Robustness only, identical definitions, never pooled.
- **Adjustment set.** Prior RV, time of day, decline magnitude and pre-decision net flow, plus the bracket width (design addition, strikable before outcomes).
- **H05.** The distance is stated; H05 stays closed.
- **Not consumed.** No window is consumed and no outcome is computed. Only a format probe of one 2023 bookDepth file preceded the freeze.

```
TF-SEED0001-RD-RETRO1 = REGISTERED_NOT_EXECUTED
TF-SEED0001-RD-PROSP1 = REGISTERED_NOT_STARTED
SEARCH_FAMILY_ID = SF-OWNER-SEEDS
MARKET_OUTCOMES_COMPUTED = false
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = SEED0001_OUTCOME_BLIND_FEASIBILITY_COUNT_PASS
```

## SEED-0001 outcome-blind feasibility — 2026-10-02

The count pass ran after the freeze commit. It used Binance UM klines (2022-11..2024-12, pinned to the CORE inventories) and bookDepth for 2023–2024; 3 BTC and 2 ETH days are missing in the archive.
- **Not computed:** no outcome, R-multiple, MFE/MAE or post-decision price.
- **Point-in-time audit:** 30/30 identical per symbol.
- **BTC eligible:** 743 episodes, A/B/C/D = 36/259/63/385.
  - A falls on 33 dates and in 24 weekly clusters, with 10/6/9/11 by half-year.
  - Divergence is the rare part (13% of eligible episodes); support holds in 40%.
- **Dependence:** every A episode shares a 48h overlap chain with another episode, and 22% of windows cross a week boundary.
- **Power.** The Holm conjunction of P1 and P2 has STRESS power 0.10 at the 10 pp bar, and the MDE is about 30 pp. Covariate support passes (max |SMD| 0.61). Heterogeneity is `NOT_ASSESSABLE`.
- **Prospective.** The stop at 30 A episodes is about 15% powered at 10 pp.
- **ETH (robustness):** A = 32 episodes on 27 dates.
- **Verdict (frozen rule):** `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`. It would also be `INFORMATIONALLY_WEAK` above the floor.

**Nothing changed or opened.** Definitions were not changed after the counts. The 2023–2024 outcome surface for this card is unopened, not consumed. Outcomes need a separate owner authorization, and the report does not recommend opening them at this power.

```
SEED0001_FEASIBILITY = INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR
MARKET_OUTCOMES_COMPUTED = false
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = OWNER_DECISION on SEED-0001
```

Record: `docs/research/SEED0001_FEASIBILITY_REPORT.{md,json}`.

## SEED-0001 owner decision — retrospective leg closed outcome-blind — 2026-10-02

The owner accepted the SEED-0001 feasibility stop. The retrospective leg (`TF-SEED0001-RD-RETRO1`) is closed outcome-blind with the frozen verdict `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`.
- **Outcomes.** Forward outcomes remain unopened and must not be computed. The 2023–2024 outcome surface of this card is not consumed.
- **No rescue.** No threshold modification, parameter tuning or reinterpretation of SEED-0001 is authorized. Preregistration, detector, feasibility rule, report, episode sets and manifest are unchanged.
- **Prospective leg.** The preregistration (`TF-SEED0001-RD-PROSP1`) stays frozen and is not activated. Any detector run on the protected 2026 segment, or on the prospective cohort, needs a separate explicit owner decision.
- **Track B.** Longer-history proxy research for the book observable, if pursued, is a separate card or seed. It is not a continuation or rescue of SEED-0001.
- **Routing.** It returns to the research queue in `CURRENT_RESEARCH_STATE.md`. This entry supersedes the `NEXT_UNIT = OWNER_DECISION on SEED-0001` line of the feasibility entry above.

```
SEED0001_RETROSPECTIVE_LEG = CLOSED_OUTCOME_BLIND
SEED0001_FEASIBILITY = INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR
TF-SEED0001-RD-RETRO1 = REGISTERED_NOT_EXECUTED
TF-SEED0001-RD-PROSP1 = REGISTERED_NOT_STARTED
MARKET_OUTCOMES_COMPUTED = false
PROTECTED_2025_2026_OPENED = false
SCIENTIFIC_DEGREES_OF_FREEDOM_REMAINING = 0
NEW_DESIGN_REQUIRES_NEW_RESEARCH_OBJECT_ID = true
NEXT_UNIT = NONE_AUTHORIZED_AFTER_SEED0001_FEASIBILITY_STOP
```

## SEED-0001 owner decision — exploratory outcome analysis authorized — 2026-10-02

This supersedes the routing of the feasibility-stop entry above. That entry stays as the historically correct record.
- **Owner decision.** SEED-0001 continues despite `INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR`, which is unchanged. The owner accepts that the retrospective sample is underpowered and authorizes an exploratory outcome-analysis phase.
- **Status of the test.** It is not a conversion of the preregistered retrospective test into a confirmatory success. The classification is fixed before outcomes as `INCONCLUSIVE_DISCOVERY`.
- **Frozen inputs.** The preregistration, detector, thresholds, covariates, contrasts, hard floor, episode sets and feasibility report stay frozen. Their SHA256s are re-verified and recorded in `docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json`.
- **Allowed scope.** Outcomes are opened only for the frozen episodes and the frozen outcome definitions. The forward return, MFE and MAE definitions are fixed in the permit before opening. All statistics are exploratory / underpowered.
- **Changes need a new SEED.** Any later parameter change, alternative threshold, stop, entry, exit, subgroup selection or rescue analysis needs a new research object / SEED.
- **Prospective leg.** It stays separate and frozen.
- **Consumption.** Opening outcomes consumes the 2023–2024 Binance UM 1h outcome surface for this card and for nearby questions. A later variant cannot use it as untouched evidence.

```
SEED0001_FEASIBILITY = INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR
SEED0001_EXPLORATORY_OUTCOME_PERMIT = docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json
EVIDENCE_LABEL = EXPLORATORY / UNDERPOWERED
CLASSIFICATION_FIXED_BEFORE_OUTCOMES = INCONCLUSIVE_DISCOVERY
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = SEED0001_EXPLORATORY_OUTCOME_ANALYSIS
```

## SEED-0001 exploratory outcome analysis — result — 2026-10-02

This ran under `docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json`, authorized in `df9e351`. The evaluator was committed in `1e4f848` before the one run.
- **Checked before the run:** the frozen artifacts were re-verified and the frozen episode sets were used as they are.
- **No unavailable windows.** No byte from 2025 or 2026 was read.
- **Label.** `EXPLORATORY / UNDERPOWERED`. The classification is `INCONCLUSIVE_DISCOVERY`, as fixed before outcomes.

**BTC, Y1_48H (+1R before −1R).** Raw WIN/LOSS/NEUTRAL counts by arm:

| Arm | WIN | LOSS | NEUTRAL |
|---|---:|---:|---:|
| A | 20 | 15 | 1 |
| B | 130 | 121 | 8 |
| C | 26 | 29 | 8 |
| D | 201 | 159 | 25 |

Adjusted contrasts, with CR1 weekly-cluster 95% CIs, the week-bootstrap CIs (4999 resamples) and Holm p-values:

| Contrast | Estimate | CR1 95% CI | Bootstrap 95% CI | Holm p |
|---|---:|---|---|---:|
| P1, A − B | +0.042 | [−0.099, +0.184] | [−0.111, +0.180] | 0.554 |
| P2, A − C | +0.148 | [−0.037, +0.332] | [−0.044, +0.331] | 0.233 |

- **Gates.** The statistical gate fails and the practical gate fails.
- **Secondaries.** Y2_48H, the 96h endpoints and chain clustering: none rejects.
- **Half-years.** 3 of 4 epochs share the pooled sign for each contrast. The heterogeneity permutation p is 0.55 for P1 and 0.35 for P2, and the gate was `NOT_ASSESSABLE` before opening.
- **ETH (robustness only).** P1 is −0.089 and P2 is −0.138, so `ETH_NOT_SAME_DIRECTION`.

**Consumed.** The 2023–2024 Binance UM 1h outcome surface is consumed for this card and for nearby questions. No threshold, horizon, stop, entry, exit or subgroup was searched after outcomes. The prospective preregistration is unchanged and not activated.

```
TF-SEED0001-RD-RETRO1 = EXECUTED / INCONCLUSIVE_DISCOVERY
EVIDENCE_LABEL = EXPLORATORY / UNDERPOWERED
RESULT = docs/research/SEED0001_EXPLORATORY_OUTCOME_RESULT.{md,json}
PROTECTED_2025_2026_OPENED = false
RERUN_AUTHORIZED = false
NEXT_UNIT = NONE_AUTHORIZED_AFTER_SEED0001_EXPLORATORY_OUTCOME_ANALYSIS
```

## Divergence research program — map V0 — 2026-10-02

The owner directed that SEED-0001 become a research program on divergences, with the program mapped before any new outcome test. Record: `docs/research/DIVERGENCE_RESEARCH_MAP_V0.{md,json}`.
- **First hypothesis.** H-DIV-1, the interaction of divergence with a confirmed support state.
- **Origin.** It is motivated by mechanism. SEED-0001's exploratory numbers are its origin, not evidence.
- **Spend of 2025–2026.** The owner proposes spending 2025–2026 before the prospective stream on one frozen divergence card. This is not decided.
- **Conditions in the map:**
  - the card is frozen first;
  - its feasibility comes from 2023–2024 layouts;
  - no access to the E1-RUN-001 holdout `[2026-08-16, 2026-08-25 17:20)`;
  - an explicit owner decision on D2's 2025/2026 reservation;
  - policy documents and a new compiler policy version are updated with the decision.
- **Nothing consumed.** No data was opened and no window was consumed. The only access was HTTP checks of pre-2025 `.CHECKSUM` objects, to establish availability.

```
DIVERGENCE_RESEARCH_MAP_V0 = PROGRAM_MAP / NO_DATA_OPENED
PROTECTED_2025_2026_OPENED = false
PROTECTED_SPEND_DECIDED = false
NEXT_UNIT = DIVERGENCE_PANEL_FEASIBILITY_V0
```

## Divergence program owner decisions V1; D2 reservation released — 2026-10-02

Record: `docs/research/DIVERGENCE_PROGRAM_OWNER_DECISIONS_V1.md`. The feasibility design was frozen before any download or count in `docs/research/DIVERGENCE_PANEL_FEASIBILITY_V0_DESIGN.json`.
- **Authorized now.** `DIVERGENCE_PANEL_FEASIBILITY_V0`, on 2023–2024 only, outcome-blind, for the panel BTC, ETH, SOL, XRP, BNB and DOGE.
- **Conditional spend window.** Decisions 2025-01-01..2026-08-11, only if the panel reaches power 0.80 at 15 pp under the dependence-aware STRESS profile.
  - 10 pp is diagnostic.
  - 20 pp alone never authorizes opening.
- **E1 untouched.** The E1-RUN-001 holdout stays strictly protected.
- **D2 (superseding; history unchanged).** The reservation on 2025 (primary confirmation surface) and on pre-E1 2026 (second reserved surface) is released.
  - **Why:** the frozen D2 confirmation has negligible yield on a one-year surface (power 0.011).
  - **What remains:** D2 stays a valid historical research object. A future D2 confirmation needs a new independent dataset or a prospective surface.
- **Estimands.** The primary is `(A − B) − (C − D)`; `A − B` is the key secondary. Both are frozen before any protected opening.
- **What SEED-0003 must freeze** before any opening: the list of 17 items in the decision record.
- **Nothing opened.** No protected byte was read.

```
DIVERGENCE_PANEL_FEASIBILITY_V0 = AUTHORIZED
HOLDOUT_SPEND_WINDOW = 2025-01-01..2026-08-11 (CONDITIONAL)
D2_RESERVATION_ON_SPEND_SURFACE = RELEASED
PROTECTED_2025_2026_OPENED = false
```

## Divergence panel feasibility V0 — INFORMATIONALLY_WEAK — 2026-10-02

The pass ran under the design frozen in `1404346`.
- **Detector and data.** The SEED-0001 detector, unchanged, on six UM perps for 2023–2024. The BTC and ETH digests reproduce. The PIT audit is 30/30 on each symbol. bookDepth days missing in the archive are listed in the report.
- **Not computed.** No outcome on any symbol, and no byte from 2025 or 2026.
- **Panel counts.** A/B/C/D are 156 / 1434 / 330 / 2518. The A episodes fall on 110 distinct dates and in 67 week clusters.
- **Concentration.** The largest symbol share of A is 23%.
- **Interaction power at 15 pp on the projected 85-week spend layouts:**

| Profile | Power |
|---|---|
| STRESS (the gate) | 0.655 / 0.609 |
| INDEPENDENT | 0.78 / 0.76 |
| COLLAPSED | 0.61 / 0.58 |

- **MDE80 under STRESS.** 20 pp.
- **Verdict.** `INFORMATIONALLY_WEAK`.
- **Required history.** About 2.5–3 years of panel history at the 2023–2024 density.
- **Consequence.** The conditional holdout spend is not authorized and 2025–2026 stays sealed. No SEED-0003 prereg was written. Nothing is consumed: 2023–2024 counts carry no outcome information.

```
DIVERGENCE_PANEL_FEASIBILITY_V0 = INFORMATIONALLY_WEAK
HOLDOUT_SPEND = NOT AUTHORIZED
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = OWNER_DECISION_AFTER_DIVERGENCE_PANEL_FEASIBILITY_V0
```

## Divergence program owner decisions V2 — conditional-support feasibility V1 authorized — 2026-10-02

After V0, the owner authorized a new outcome-blind unit: `DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1`. The V0 verdict `INFORMATIONALLY_WEAK` stands; it is not reinterpreted or rescued.
- **New question.** Does regular bullish divergence add practically meaningful value conditional on support?
  - The primary estimand is `A − B`, which is not an interaction.
  - The secondary is `(A − B) − (C − D)`.
- **Bar.** The minimum effect stays 15 pp.
- **Allowed scope.** The historical window and a pre-specified combined design with a prospective panel stream from 2026-10-05.
- **Excluded.**
  - Continuous models are secondary concepts only.
  - There is no panel expansion.
- **Unchanged constraints.** E1 stays absolute and D2 stays released. SEED-0003 is not created. Nothing protected was opened.

Records: `docs/research/DIVERGENCE_PROGRAM_OWNER_DECISIONS_V2.md` and `docs/research/DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_DESIGN.json`.

## Divergence conditional-support feasibility V1 — result — 2026-10-02

This was an outcome-blind run of the design frozen in `323451e`. The six-symbol panel and the V0 digests reproduce. The primary estimand is `A − B`, at 15 pp.

**Window proxies:**

| Measure | Proxy 1 | Proxy 2 |
|---|---:|---:|
| A episodes | 134 | 125 |
| A dates | 98 | 88 |
| A week clusters | 57 | 55 |
| STRESS power at 15 pp (10k replicates) | 0.813 | 0.789 |

Other numbers:
- **Design effect on A − B (STRESS):** about 1.45.
- **Historical window alone:** `INFORMATIONALLY_WEAK`.
- **Combined design.** The window plus a prospective panel stream from 2026-10-05 reaches 0.80 after about 4 weeks: 0.812 on proxy 2, 0.825 on proxy 1 at 0 weeks. It is the same with BTC excluded from the prospective part.
  - **Frozen-form stop:** cumulative A ≥ 135 and A week clusters ≥ 59.
  - **Deadline:** 2026-11-30.
  - **Verdict:** `FEASIBLE_FOR_PREREGISTRATION`, with a thin margin.
- **Secondary interaction:** 0.61–0.64.
- **Nothing consumed:** no outcome was computed and no protected byte was read. SEED-0003 was not created.

```
HISTORICAL_ONLY_VERDICT = INFORMATIONALLY_WEAK
COMBINED_DESIGN_VERDICT = FEASIBLE_FOR_PREREGISTRATION
PROTECTED_2025_2026_OPENED = false
NEXT_UNIT = OWNER_DECISION_AFTER_DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1
```

## Divergence full-history research V0 — design frozen — 2026-10-02

The owner accepted the V1 results unchanged and authorized `DIVERGENCE_FULL_HISTORY_RESEARCH_V0`, a pre-specified research program rather than a confirmatory test.

**Slices.**
- **Discovery** is 2023–2024, previously observed.
- **Validation** is 2025-01-01..2026-08-11, previously unseen. The previously protected surface is opened for this program only after the freeze, and it is evaluated once.
- **Pooled** results are never presented as replication.

**Boundaries.** The E1-safe cutoffs are derived mechanically: last decision 2026-08-11 and read horizon 2026-08-15. The E1 holdout is untouched.

**What is frozen.** The six-symbol panel, the unchanged detector and arms, the primary A − B, the secondary interaction, the SEED-0001 outcomes plus net R and timing, costs, a 22-feature PIT mechanism registry, weekly clustering, the labels, the analyses and the prohibited actions. All are frozen with code and frozen-artifact hashes in `docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_DESIGN.{md,json}`.

**Not activated.** The prospective stream is not activated, and no SEED-0003 is created.

```
DIVERGENCE_FULL_HISTORY_RESEARCH_V0 = DESIGN FROZEN
PROTECTED_2025_PLUS_READ_AT_FREEZE = false
E1_INTERVAL_TOUCHED = false
```

## Divergence full-history research V0 — stage 1 validation and stage 2 pooled/mechanism — 2026-10-02

**Commits.** Freeze `c12204079462c0c173eebdc8b81308174d21f457`, before any 2025+ byte. Stage-1 validation result `fca3ab54633d7c47e651ffb9d773a779473ae614`, persisted before any pooled or mechanism step. Stage 2 is the commit that adds this entry.

**Consumed.**
- The VALIDATION slice (decisions 2025-01-01..2026-08-11) of the six-symbol UM panel. It was evaluated once, and a second evaluation is refused by the runner.
- Reads end at the 2026-08-15 read horizon. The E1 holdout [2026-08-16, 2026-08-25 17:20) was never requested.

**Stage 1 (VALIDATION / PREVIOUSLY UNSEEN).**
- **Counts:** A 160, B 1251, C 342, D 2010. A falls on 112 dates and in 62 of 85 weekly clusters.
- **Primary A − B, Y1_48H:** +0.011 [−0.087, +0.109], p = 0.83; week bootstrap [−0.083, +0.105].
- **Interaction:** +0.018 [−0.094, +0.129].
- **Tags:** `SAME_DIRECTION`, `COMPATIBLE_WITH_ZERO`, `BELOW_MEOI`, `ECONOMICALLY_SMALL`, `NO_DETECTED_SYMBOL_HETEROGENEITY`.
- **Discovery** under the same frozen model: A − B +0.026 [−0.058, +0.110].

**Stage 2 (POOLED FULL HISTORY + EXPLORATORY MECHANISM; never replication or confirmation).**
- **Pooled A − B:** +0.019 [−0.047, +0.084], with N = 8201 and 186 weekly clusters.
- **Net R.** After costs, mean net R of the 1R bracket is negative in every arm and slice.
- **Heterogeneity.** Years and symbols show none detected (Q p = 0.94 and 0.40).
- **Divergence inside support:** about +2 pp. The MACD family carries nothing.
- **Exploratory.** A flow/OI selling-exhaustion state gives +0.038 [−0.000, +0.075], and a graded RSI change inside support-only episodes gives about +3.8 pp per SD (Holm p ≈ 0.03 among 22 features). Both were seen on data that includes validation and are not evidence.
- **Failure states within A.** None survive Holm.

**Report:** `docs/research/DIVERGENCE_FULL_HISTORY_RESEARCH_V0_REPORT.md`.

```
DIVERGENCE_FULL_HISTORY_RESEARCH_V0 = COMPLETE
VALIDATION_A_MINUS_B_15PP = EXCLUDED (upper 95% bound +0.109)
PROTECTED_2025_PLUS_OPENED_FOR_DIVERGENCE = true (2025-01-01..2026-08-15 read horizon)
E1_INTERVAL_TOUCHED = false
PROSPECTIVE_ACTIVATED = false
SEED0003_CREATED = false
NEXT_UNIT = OWNER_DECISION_AFTER_DIVERGENCE_FULL_HISTORY_RESEARCH_V0
```

## Selling-exhaustion support feasibility V0 — design frozen — 2026-10-02

The owner accepted `DIVERGENCE_FULL_HISTORY_RESEARCH_V0` (`DIVERGENCE_PROGRAM_OWNER_DECISIONS_V3.md`) and authorized a feasibility-only new research object: `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0`.

**Population.** Support episodes of the unchanged SEED-0001 detector on the exposed six-symbol surface: decisions 2023-01-01..2026-08-11, read horizon 2026-08-15.

**Candidate states.** No oscillator input; thresholds are no-change points or medians; windows reuse frozen constants.
- `SE_LEG`: weaker net taker selling over the second leg than the first, AND OI not up over the leg.
- `SE_BASELINE`: 24-bar approach flow above its local 720-bar median, AND OI not up over 24h.

**Primary:** `E − S`. Power is reported at 3 / 5 / 7.5 / 10 pp; the decision line is 5 pp within 104 prospective weeks under STRESS.

**Dependence calibration.** It is state-blind, using already-opened outcomes only.

**Not done.** No E − S outcome contrast is computed, and no SEED is created.

```
SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 = DESIGN FROZEN
NEW_PROTECTED_OUTCOMES_OPENED = false
E1_INTERVAL_TOUCHED = false
```

## Selling-exhaustion support feasibility V0 — result — 2026-10-02

**Run.** One run of the design frozen in `a4b76fd`, on the exposed six-symbol surface. It used no new protected outcome, computed no E − S outcome contrast, and touched no E1 byte.

**Integrity.** The PIT truncation audit was 30/30 on every symbol. The discovery digests and the validation ids reproduced.

**Counts.** There are 3,005 support episodes over 186 weeks.
- **`SE_LEG`:** 667 E (22%) and 2,335 S.
- **`SE_BASELINE`:** 349 E (12%) and 2,649 S.
- **Concentration:** the maximum symbol share of E is 0.18–0.19, and the maximum half-year share is 0.16–0.17.

**State-blind outcome dependence.** Same-date cross-symbol φ = 0.227; same-week other-date φ = 0.026; same-symbol chain φ ≈ 0.

**Power.**
- **Exposed-sized sample, MDE80:** 6.5–8.0 pp (`SE_LEG`) and 8.0–9.5 pp (`SE_BASELINE`).
- **Prospective weeks for 80% at 5 pp:** 270–430 (`SE_LEG`) and 472–604 (`SE_BASELINE`).
- **At 4 pp:** 453–665 (`SE_LEG`).

**Continuous score.** It is 3–4× more efficient only under a graded effect, and about 3× worse under a step.

**Report:** `docs/research/SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.md`.

```
SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 = INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON
NEW_PROTECTED_OUTCOMES_OPENED = false
E_MINUS_S_OUTCOME_CONTRAST_COMPUTED = false
E1_INTERVAL_TOUCHED = false
SEED_CREATED = false
NEXT_UNIT = OWNER_DECISION_AFTER_SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0
```

## Divergence / selling-exhaustion line — final owner routing decision — 2026-10-03

The owner accepted `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 = INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON` and closed the divergence / selling-exhaustion line as an active research route.
- **Status of the observations.** They are not declared false. They stay available as descriptive context.
- **Routing** returns to `PRODUCT_FIRST_DECISION_V1`.
- **Consumed by this record:** nothing. No research unit ran and no market outcome was computed.
- **Unchanged:** every result file, frozen design and earlier ledger entry.

**Chronology (UTC).**
- The six-symbol surface was opened by the full-history validation run at 20:06 on 2026-10-02 (`fca3ab5`).
- `PRODUCT_FIRST_DECISION_V1` reached `main` at 21:22 (`8973d1d`).
- `SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0` was authorized at 22:22 (`b701864`) and completed by 22:39 (`62653a3`), on the research branch before it contained the product-first records. The lines met in the merge `c896fa2`.

```
REGULAR_BULLISH_DIVERGENCE_PROGRAM = COMPLETED
SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 = INFORMATIONALLY_WEAK / NOT_TESTABLE_WITHIN_REALISTIC_HORIZON
NEW_DIVERGENCE_RESEARCH_UNIT_AUTHORIZED = false
NEW_SELLING_EXHAUSTION_RESEARCH_UNIT_AUTHORIZED = false
RSI_GRADIENT_SUPPORT_CANDIDATE = ARCHIVED_CANDIDATE / NOT_AUTHORIZED (exploratory; found on exposed data; not independently validated)
PROSPECTIVE_DIVERGENCE_STREAM_ACTIVE = false
SEED_CREATED = false
DIVERGENCE_SUPPORT_2025_2026_SURFACE_OPENED = true (BTC/ETH/SOL/BNB/DOGE/XRP USD-M; 2025-01-01..2026-08-15 exclusive)
E1_RUN_001_OPENED = false (holdout [2026-08-16T00:00Z, 2026-08-25T17:20Z) never requested)
NEXT_UNIT = none (research); product build-to-test per PRODUCT_FIRST_DECISION_V1.md §3
NEW_RESEARCH_PROGRAMS_AUTHORIZED = false
```


## GV0V03L40 C025-R1 outcome-blind stop — 2026-10-02

Owner-authorized manual escalation of C025. The original card was not edited. Critic verdicts remain novelty REJECT, feasibility REJECT, red team REJECT. The executed design is C025-R1: a past-only 60-minute refractory replaces the original rule that dropped a burst because another burst fell inside the outcome window. That future-burst rule was not run.

The count uses pinned Binance BTCUSDT perpetual 1m bars for 2020-01..2024-12 only. No post-T impact ratio was computed. The window is not a consumed confirmatory result.

```
PRIMARY_VARIANT = theta 0.70 / quantile 0.999 / W 30m
RAW_BURSTS = 2895
ONE_SIDED_N = 1
TWO_SIDED_N = 879
MATCHABLE_ONE_SIDED_N = 1
MATCHABLE_TWO_SIDED_N = 169
FEASIBILITY_STATUS = INFORMATIONALLY_WEAK
BLOCKER = MDE_TOO_LARGE
EFFECTIVE_N = 0.994
MDE_STRESS = 5.620
POWER_STRESS = 0.035
EXECUTION_PERFORMED = false
PREREGISTRATION_CREATED = false
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
OTHER_VARIANTS_ESTIMATED = false
RESCUE_ATTEMPTED = false
```

Record: `docs/research/GV0V03L40_C025_R1_CLOSE.md`.

## 2026-10-03 — Owner cards R03 executed once and closed

Owner-authorized program `SF-OWNER-CARDS-R03` (override of the product-first "no new research programs" rule for this program only; `docs/research/OWNER_CARDS_R03_DECISION.md`). Three cards of four `CONTEXT_DESCRIPTIVE` hypotheses on window range versus an ordinary-conditions comparator: scheduled derivatives-expiry clock (G), panel breadth/dispersion states (H), session/participant-clock structure (J).

- **Consumed by this record:** the discovery surface Binance BTCUSDT 2020–2024 for the twelve frozen definitions (six executed, six closed outcome-blind). No rescue of any of the twelve.
- **Not consumed:** BitMEX 2017–2019 (declared replication; no outcome opened), the 2025/2026 surfaces, the B2_06 OI/funding snapshot (not used).
- **Result:** all six executed hypotheses `NO_INCREMENTAL_STRUCTURE`; zero prototypes; nothing promoted. Weekend hours (C1) show a clear negative effect (≈ −0.4 SD, Holm p 0.0001, growing by year) that is below the frozen 0.5 SD bar.

```
EXECUTED = R03-A1, R03-A4, R03-B2, R03-C1, R03-C2, R03-C4
CLOSED_AT_FEASIBILITY = R03-A2, R03-A3, R03-C3, R03-B1, R03-B3, R03-B4
PROMISING_PROTOTYPES = 0
REPLICATION_EXECUTED = false
RERUN_AUTHORIZED = false
PROTECTED_2025_2026_OPENED = false
```

Records: `docs/research/OWNER_CARDS_R03_RESULT.md`, `SCIENTIFIC_TEST_LEDGER.json` (`TF-R03-A-EXPIRY-CLOCK`, `TF-R03-B-PANEL-STATES`, `TF-R03-C-SESSION-CLOCK`).

## Protected Binance 2025/2026 opened for product statistics — 2026-10-03

Owner decision (`docs/PRODUCT_DECISION_V2_DECISION_SUPPORT.md` §4). The decision-support statistics of the product read Binance USD-M BTCUSDT 5m klines (2020-01 → yesterday) and Vision OI metrics (2020-09 → yesterday), 2025/2026 included.

```
PROTECTED_2025_2026_PRODUCT_USE = OPENED
PRODUCT_FEATURES = range/volatility (1h/4h/24h corridor model), level first-touch reactions
                   (PDH/PDL/PWH/PWL/PMH/PML, round numbers, previous-day POC), 1h/4h price/OI/taker
                   state labels and their forward 1h/4h/24h outcomes, CPI/FOMC/expiry hour and day sizes
EXCLUDED = E1-RUN-001 final holdout [2026-08-16T00:00Z, 2026-08-25T17:20Z) — never stored
RESEARCH_STATUS_OF_2025_2026 = CONSUMED for any hypothesis over the product features
SEALED_VERDICTS_REOPENED = false
RESCUE_ATTEMPTED = false
```

**Correction (2026-10-03, red-team of the V2 branch, before any deploy).** The first implementation dropped holdout rows only after parsing: it planned the August 2026 monthly klines archive and the 2026-08-25 metrics file, both of which overlap the holdout, so a sync would have downloaded holdout bytes. It never ran against the network (no deploy; this environment cannot reach Binance), so no holdout byte was fetched. The planner now rejects every overlapping object before any request (21 objects: the August monthly klines, daily klines and metrics of 2026-08-16 … 2026-08-25), and a request gate refuses any overlapping URL. `PROTECTED_BYTES_FETCHED = NO`.

These statistics are product evidence (descriptive, with N, a comparable baseline and a verdict), not research claims. Development numbers seen while building them (2022–2024 repository archives, synthetic OI only for the analogue mechanics) are recorded in the implementation review, not as results.

---

## 2026-10-03 — Event corridor temporal repair: 2024 release windows become repair data

Design record: `docs/BETA_EVENT_CORRIDOR_TEMPORAL_REPAIR_DESIGN_V1.md` (design only; no code change, no retrain). The product corridor's CPI/FOMC term (`event_in_window`, release in `[t, t + H)`) widens the corridor before a release and drops it from the first 5-minute live anchor after it; the hourly calibration never sees that moment. The owner-relayed red-team table (2024 FOMC, −60…+60 min around the release) showed it and shaped the redesign.

```
SURFACE                        = Binance USD-M BTCUSDT 2024 scheduled releases (12 CPI, 8 FOMC)
STATUS                         = EXPOSED / DIAGNOSTIC / REPAIR DATA (event semantics)
ALLOWED                        = reproduce the failure; outcome-blind implementation checks
FORBIDDEN                      = confirmatory holdout for any new event semantics; choosing candidates by 2024 coverage
GENERIC_2024_HOLDOUT           = exposed (examined at build, by the red team and by the design record); diagnostic only
PREFERRED_CANDIDATE            = K1 (PRE in [t, t+H) and POST in [t-60m, t)), fixed before any fit
CONFIRMATION                   = prospective releases after the freeze (primary); BitMEX 2017-2019 = unaudited secondary, not opened
FEASIBILITY                    = FALSIFICATION_FEASIBLE / CALIBRATION_CONFIRMATION_NOT_FEASIBLE_SHORT_TERM (units = releases, ~20/year)
FALLBACK                       = no numerical corridor around releases until a prospective check passes
EVENT_CODE_CHANGED             = NO
EVENT_MODEL_RETRAINED          = NO
```

**Follow-up (2026-10-03, owner scope "product safety fallback + feasibility clarification").**
- **Feasibility.** Recomputed with methods fixed before computing: exact one-sided binomial for detection, Wilson for precision. 12 / 38 / 127 releases to detect a true coverage of 40% / 60% / 70% against 80% (α = 0.05, power 0.80); 81 / 289 releases for ±10 / ±5 pp. The earlier 8 / 29 / 109 / 62 / 246 came from two undeclared normal approximations and are superseded.
- **BitMEX XBTUSD 2017–2019.** Provenance audit, no outcome computed: read in bulk by D2 and D7; only aggregates published; no CPI/FOMC calendar ever joined. Every hour, event hours included, entered D7 states and D2 volatility, and the C012 triage already named the surface for scheduled events. Verdict: `NOT_PROVABLY_INDEPENDENT`.
- **Product fallback.** Implemented in the V2 branch: no numerical corridor, touch chance or `/risk` figure inside `[release − H, release + 60 min)`; no multiplier; no forecast tracked there.
- **Unchanged.** `EVENT_CODE_CHANGED_FOR_K1 = NO`, `EVENT_MODEL_RETRAINED = NO`, `PROTECTED_BYTES_FETCHED = NO`.

**Follow-up (2026-10-03, owner scope "EVENT SAFETY cleanup").** No surface opened, no outcome read.

```
EVENT_FEASIBILITY_TABLE        = LOCKED: 12 / 38 / 127 / 81 / 289 (exact one-sided binomial, H0 p = 0.80, alpha 0.05,
                                 power 0.80, stable for every m in [n, n+100]; Wilson 95% for precision);
                                 no change after prospective outcomes without a dated amendment
PRIMARY_CONFIRMATION_SURFACE   = PROSPECTIVE RELEASES AFTER K1 FREEZE
BITMEX_CONFIRMATION_STATUS     = NOT_PROVABLY_INDEPENDENT
SURFACE_2024                   = EXPOSED / DIAGNOSTIC / REPAIR
SURFACE_2025_2026              = EXPOSED_FOR_OTHER_PURPOSES / NOT CONFIRMATORY
EVENT_MULTIPLIER_USER_FACING   = NO
RAPID_MOVE_EVENT_RISK_CLASS    = C / EVENT_FLAG_DECISION_RELEVANT_UNCALIBRATED (design record §10); detector unchanged
```

**Follow-up (2026-10-03, owner authorisation "sharp-move event fallback, Option 1").** A product safety fallback. It is not research and not a confirmation of any event semantics.

```
SHARP_MOVE_EVENT_CONDITIONING  = DISABLED_PENDING_VALIDATION
STATISTIC                      = MOVE15_OVER_1H_SCALE_EVENT_NEUTRAL_V1 (1h rangecast scale, CPI/FOMC columns at 0),
                                 one function for live detection and nightly calibration
CALIBRATION_PROCEDURE_CHANGED  = NO
THRESHOLD_DIAGNOSTIC           = OLD 2.0618 -> NEW 2.0963 (repo archives 2022-2024, pooled, same procedure; not used
                                 to change anything)
CORRIDOR_MODEL_CHANGED         = NO (K0 event term, coefficients, fit, forecast)
```

## 2026-10-03 — Autonomous research generation G01: no survivor, nothing executed

**Program.** `SF-AUTOGEN-G01` is an owner override of `NEW_RESEARCH_PROGRAMS_AUTHORIZED = false` for this program only (`AUTOGEN_G01_DECISION.md`). The research map was rebuilt from `main` at `a7d738f`.

**Candidates.** Fourteen were generated (`AUTOGEN_G01_CANDIDATES.md`).
- **Closed at red team (8):**
  - HK ETF 08:00 UTC fixing: confounded with funding and expiry;
  - weekend BTC share of the spot panel: fee-promotion and FDUSD-migration artifacts;
  - session taker-sign profile: directional, clock not identified;
  - taker-sign persistence: outcome not in doubt;
  - equity OPEX hour: rare N;
  - Asia lunch participation: clock not identified;
  - ETF-era weekend gap: leakage from R03-C1's exposed epoch trend;
  - bank-holiday fiat rails: rare N.
- **Closed at dedupe (2):**
  - signed-shock range asymmetry: repeats GV0V03L40-C027/C003 and sits in the D2/D8 neighbourhood;
  - unusual-hour persistence: D2 RV neighbourhood, outcome not in doubt.

**Compiled under `GV0R02_SCHEMA_V2` plus unit screens (`AUTOGEN_G01_FEASIBILITY.md`):** all four are `INFORMATIONALLY_WEAK`.

| Hypothesis | Discovery | Replication | Blocker |
|---|---|---|---|
| G01-A1 turn-of-month participation | 59 months, unit MDE 0.486 | 36 BitMEX months, MDE 0.63 | replication MDE too large |
| G01-A2 turn-of-month range | same | same | same |
| G01-A3 month-end mark hour | MDE 0.78 | — | MDE too large |
| G01-B1 ETF NAV fixing-hour participation, DiD at the 2024-01-11 launch | 210 pre / 51 post weeks, unit MDE 0.5005 | prospective, underpowered | above the bar |

A definitional error in B1's prospective stopping rule (`MIN_N` above `MAX_EPISODES`) was corrected before freeze and recorded.

**Not consumed.** Nothing was consumed: no market value was read, and no hypothesis was frozen, registered or executed.

```
AUTOGEN_G01 = CLOSED_AT_FEASIBILITY / NOTHING_EXECUTED
FROZEN = 0; EXECUTED = 0; PROMISING_PROTOTYPES = 0
MARKET_VALUES_READ = false; OBJECTS_2025_2026_USED = none; E1_RUN_001_OPENED = false; B2_06_OPENED = false
NEXT_UNIT = none (research); routing returns to PRODUCT_FIRST_DECISION_V1
```

## 2026-10-03 — AUTOGEN_G01 closure accepted: CLOSED_NO_SURVIVORS

The owner accepted the G01 result. The cleanup is documentation only: no compiler, R03, frozen contract, product code or production change.

**What we learned.** The AUTOGEN_G01 search over the authorized research map and the current candidate sources found no new high-frequency hypothesis that was at once incremental to prior work, identifiable, research-authorized and sufficiently powered at the frozen 0.5 SD bar. This is a statement about this search, not a claim that the high-frequency mechanism space is exhausted. The four hypotheses that reached the compiler were low-frequency calendar or natural-experiment cells, whose independent units per era are too few for discovery plus time-disjoint replication at that bar.

**G01-B1.** Initial `MIN_N = 252` wrongly added the fixed historical (pre-launch) arm to the prospective arm. Corrected `MIN_N = 52` reflects the intended prospective requirement. The correction was made before freeze and before any outcome access. It did not rescue the hypothesis: final feasibility is still `INFORMATIONALLY_WEAK` (unit-level MDE 0.5005 > 0.5; prospective replication underpowered). It stays only as `FUTURE_CANDIDATE / NATURAL_DATA_ACCUMULATION`: no lowered bar, no 2025–2026 surface, no prospective automation within G01.

```
G01_STATUS = CLOSED_NO_SURVIVORS
CANDIDATES_FROZEN = 0; CANDIDATES_EXECUTED = 0; MARKET_OUTCOMES_OPENED = NO
```

## 2026-10-03 — Research Atlas V1: past research transferred onto one permanent map

**Decision (owner proposal of 2026-10-03).** Numbered generation campaigns are replaced by `SIGNALBOT_RESEARCH_ATLAS_V1`: Mechanism (66 rows in 13 regions) × Data surface (10 columns) × Research state (11 states). This is documentation and tooling only:
- no market value was read;
- no test was registered or run;
- no window was consumed;
- no sealed record or memory-chain file was edited.

**Recorded on the map.** Each of the 145 units carries:
- what was tested;
- data and period;
- the practical bar;
- the verdict;
- why it closed;
- what would reopen it;
- forbidden rescues;
- records.

Every surface carries an exposure ledger.

**Facts made explicit by the transfer:**
- **Order book.** Binance USD-M bookDepth for BTC/ETH in 2023–2024 and for six symbols in 2025–2026 is exposed for book-imbalance and depth-asymmetry mechanisms, because the SEED-0001 and divergence "book support" state was a ±5% depth imbalance computed with outcomes.
- **D7.** Recorded as CONFIRMED (the BitMEX confirmation).
- **GV0V03L40-C033.** Recorded as BLOCKED_METHOD (V2 recompile: the joint state never occurs).
- **PRICE_OI pilot.** Its frozen grid starts inside the calendar span of the E1-RUN-001 holdout. This is flagged for the owner; nothing was run.

```
ATLAS = SIGNALBOT_RESEARCH_ATLAS_V1
WINDOWS_CONSUMED = none; MARKET_VALUES_READ = none; NEW_TESTS = none
```

## 2026-10-03 — Atlas governance cleanup before merge: PRICE_OI/E1 erratum, SEED-0001 prospective closure, memory reconciliation, reserve, event log

No market value was read and no test was registered or run. Every change is append-only or a new record:
- the frozen PRICE_OI preregistration and its twin are unchanged;
- the SEED-0001 preregistration and the `SCIENTIFIC_TEST_LEDGER.json` entry are unchanged;
- the generator memory chain is unchanged.

**PRICE_OI pilot vs E1-RUN-001 (`PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md`).**
- **Overlap.** The frozen 12434-bucket grid starts at 2026-08-16T19:30Z; 2566 buckets lie inside the protected interval `[2026-08-16T00:00Z, 2026-08-25T17:20Z)`.
- **Not run, and not runnable as frozen.** The runner was never executed. Execution on the segment is invalid, and the frozen data gate cannot be met without it, so a future execution is a new pilot identity with a new explicit permit.
- **Boundaries.** The earliest eligible grid timestamp is 2026-08-25T17:20:00Z; the input-clean decision bucket is from 2026-09-24T17:20:00Z (30-day percentile lookback).
- **Atlas.** `BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP`.
- **E1.** The pilot never read E1-RUN-001; E1's evaluator and sealed artifacts were not touched.
- **P4.** The owner-run P4 descriptive follow-up (2026-09-29) used the same grid and reported 1h/4h realized ranges. The owner adjudicated this the same day (next entry).

**SEED-0001 prospective (`SEED0001_PROSPECTIVE_CLOSURE_V1.md`).**
- `TF-SEED0001-RD-PROSP1 = CLOSED_BEFORE_START`, superseded by the divergence program closure.
- Never started, no prospective outcome opened, no confirmation surface consumed.

**Atlas.**
- **Memory reconciliation layer.** D7 is CONFIRMED and GV0V03L40-C033 is BLOCKED_METHOD by atlas authority; the memory statuses are preserved.
- **Reservations.** The E1 holdout is the only reserved surface; it is invisible to generation and needs a permit.
- **Event log.** Append-only and hash-chained; event 1 reproduces the transfer digest.
- **Designs only.** Generator contract V04 and the confirmation budget.
- **Bot bridge.** Atlas → proposed registry diff → review → bot; no automatic coupling.

**Product.** V2 is recorded as deployed to production from `main` `a16b876` (owner-reported).

```
WINDOWS_CONSUMED = none; MARKET_VALUES_READ = none; NEW_TESTS = none; PROTECTED_SURFACES_CONSUMED = none
PRICE_OI_PILOT_V0 = BLOCKED_GOVERNANCE / HOLDOUT_OVERLAP
TF-SEED0001-RD-PROSP1 = CLOSED_BEFORE_START
```

## 2026-10-03 — Owner decision: P4 opened the E1-RUN-001 protected outcome surface

The owner ruled that the P4 owner-run descriptive follow-up contaminated the E1 protected outcome surface for every timestamp it read inside the protected interval. It is recorded as Amendment 1 of `docs/research/PRICE_OI_INCREMENTAL_INFORMATION_PILOT_V0_E1_OVERLAP_ERRATUM.md`; the historical E1 records are not rewritten.

```
E1_EVALUATOR_TOUCHED = NO
E1_SEALED_ARTIFACTS_OPENED = NO
E1_OUTCOME_SURFACE_OPENED_BY_P4 = YES
E1_PRISTINE_HOLDOUT_STATUS = INVALIDATED_FOR_P4_OVERLAP
```

**Exposed interval, derived from P4's records.** P4 has no row-level log in the repository. The interval comes from its manifest (`authorized_buckets = 12434`, `as_of = 2026-09-29T15:03Z`) and the frozen code it names:
- **Replay (`364db27`).** It read `klines_1m` and `open_interest`, BTCUSDT, live, over `[2026-07-17T19:30:00Z, 2026-09-29T00:00:00Z)`, with no exclusion inside.
- **Follow-up (`beta/followup.py` at `9e1ba036`).** Its 1h/4h outcome windows can extend to at most `2026-09-29T04:00:00Z`. Whether it actually read past 00:00Z is not recorded.

**Consequences:**
- **E1.** Inside the E1 interval, the exposure is the whole interval `[2026-08-16T00:00:00Z, 2026-08-25T17:20:00Z)`.
- **Treated as P4-exposed:** `[2026-07-17T19:30:00Z, 2026-09-29T04:00:00Z)`.
- **Future PRICE_OI or related pilots** must:
  - exclude those timestamps;
  - exclude every anchor whose feature, lookback or control window touches them (under the V0 lookbacks, anchors from `2026-10-29T04:00:00Z`);
  - have a new explicit permit;
  - not reuse the old frozen data gate.
- **Atlas.** The E1 reservation stays `RESERVED`, with `pristine_status = INVALIDATED_FOR_P4_OVERLAP`. The live-archive surfaces carry the P4 window as exposure for all rows.

```
WINDOWS_CONSUMED = none by this record (it records a past exposure); MARKET_VALUES_READ = none; NEW_TESTS = none
```

## 2026-10-04 — DH1: directional hypotheses for the bot, frozen before any outcome

**Owner decision.** `docs/research/DIRECTIONAL_HYPOTHESES_DECISION_V1.md`: research may target the directional probabilities the bot states.
- **Endpoints:** level hold 4h after a first touch; barrier first-passage ±X in 4h.
- **Bar:** 3 pp plus a positive Brier skill score.
- **Statuses:** «Проверено» or «Гипотеза».
- **Data:** discovery on Binance 2020–2024; confirmation on 2017–2019 and live tracking.

**Funnel** (`DH1_CANDIDATES.md`): 15 candidates; 9 closed at red team (approach speed, OI, sessions, D9/H03/basis neighbours, perp taker imbalance, DVOL); 1 deferred (OKX L2 book recovery).

**Outcome-blind feasibility** (`DH1_FEASIBILITY.{md,json}`). The frozen rule runs a cell only if its discovery MDE is at most 6 pp.
- **Executes:** DH1-L2, confluent level vs isolated level (N 4622, MDE 5.8 pp).
- **Closed `INFORMATIONALLY_WEAK`:**
  - DH1-L1 (spot-confirmed approach, MDE 8.5 pp);
  - DH1-L3 (stale level, MDE 7.4 pp);
  - DH1-B2 (spot share in a sharp move, MDE 11 pp; smaller arm 289);
  - DH1-B1 (spot-confirmed sharp move): degenerate, since spot taker flow agrees with the move's direction in 97.6 % of moves.
- **Replication surface:** underpowered for every cell (MDE ≥ 10.6 pp), so confirmation in practice comes from live tracking.

**Data pinned (free).**
- Binance spot BTCUSDT 5m klines 2017-08..2024-12: 89 months, archive checksums verified.
- BitMEX XBTUSD public trades 2017-08-01..2019-12-31: 883 daily files pinned by SHA256, aggregated to 5m with the taker side.
- Discovery perp: `CORE_BTC_BINANCE_V0`.

```
SEARCH_FAMILY = SF-DH1; TEST_FAMILY = TF-DH1-L-LEVEL-HOLD (1 primary cell: DH1-L2); TF-DH1-B-BARRIER not registered (no executable cell)
PREREG = docs/research/DH1_PREREG.json; MARKET_OUTCOMES_OPENED = NO at freeze; OBJECTS_2025_2026_USED = none; E1 / B2-06 untouched
```

## 2026-10-04 — DH1 executed once: DH1-L2 inconclusive by a hair, practically null; nothing replicated

**Discovery** (Binance 2020–2024, one shot; `DH1_RESULT_DISCOVERY.json`). DH1-L2, confluent vs lone key level at its first touch, measured by 4h hold:
- 4622 touches (2049 / 2573); hold 46.5 % vs 46.3 %;
- nuisance-adjusted +0.05 pp, 95 % CI −3.03 … +3.06 pp, Holm p 0.95, Brier skill −0.0008;
- years −6.9 / +5.3 / −0.3 / −4.2 / +1.2 pp, heterogeneity p 0.13 (not assessable at this power).

**Class.** Frozen class `INCONCLUSIVE`, because the interval reaches the ±3 pp bar by 0.03–0.06 pp. In practice it is null, recorded in the atlas as `NO_STRUCTURE`.

**Replication.** There was no `PROMISING_PROTOTYPE`, so the 2017–2019 surface was not opened (`DH1_RESULT_REPLICATION.json`: no outcome read).

**Bot.** No probability line. `/research` gets one `NOT_CONFIRMED` line (DH1-L2); the level-alert line stays H02.

```
WINDOWS_CONSUMED = Binance BTCUSDT 2020-2024 for PRICE_STRUCTURE.levels (DH1-L2 state); 2017-2019 not consumed (states counted only)
TESTS_EXECUTED = 1 (TF-DH1-L-LEVEL-HOLD); PROMISING_PROTOTYPES = 0; RERUN_AUTHORIZED = false
OBJECTS_2025_2026_USED = none; E1 / B2-06 untouched
```

## 2026-10-04 — DH2: DH1-L1, L3, B2 pooled over six coins, frozen before any outcome

**Owner decision** (`DH2_POOLED_DESIGN.md`):
- pool BTC, ETH, BNB, XRP, DOGE and SOL (Binance USD-M 2020–2024);
- this overrides, for DH2 only, the atlas rule against pooling to manufacture N;
- coin fixed effects, a coin-heterogeneity gate and the BTC-only estimate are always reported.

**Data pinned (free, checksums verified):** USD-M alts 5m (281 months) and spot alts 5m (354 months, including ETH/BNB/XRP 2017–2019).

**Outcome-blind feasibility** (`DH2_FEASIBILITY.{md,json}`). All three cells are executable:

| Cell | N | MDE | Power at 3 pp |
|---|---|---|---|
| DH2-L1 | 16362 | 3.9 pp | 0.56 |
| DH2-L3 | 16373 | 4.2 pp | 0.49 |
| DH2-B2 | 9630 | 3.6 pp | 0.65 |

- **Heterogeneity gates:** both the epoch and the coin gate are `NOT_ASSESSABLE` (power 0.11–0.19).
- **Replication:** underpowered; DH2-L3 on spot 4 coins has an MDE of 8.0 pp, and DH2-L1 / B2 on BitMEX BTC have MDEs of 13–16 pp.

```
SEARCH_FAMILY = SF-DH2; TEST_FAMILIES = TF-DH2-L-LEVEL-HOLD (DH2-L1, DH2-L3), TF-DH2-B-BARRIER (DH2-B2)
PREREG = docs/research/DH2_PREREG.json (sha256 cb8bef28…53b6); MARKET_OUTCOMES_OPENED = NO at freeze; OBJECTS_2025_2026_USED = none
```

## 2026-10-04 — DH2 executed once: no pooled cell moves a directional probability; nothing replicated

**Discovery** (six coins, Binance 2020–2024, one shot; `DH2_RESULT_DISCOVERY.json`):

| Cell | Shift | 95 % CI | Holm p | Class |
|---|---|---|---|---|
| DH2-L1 | −1.75 pp | −3.78 … +0.36 | 0.21 | `INCONCLUSIVE` |
| DH2-L3 | −0.61 pp | −3.49 … +2.27 | 0.67 | `INCONCLUSIVE` |
| DH2-B2 | +0.55 pp | −1.78 … +2.84 | 0.64 | `NO_INCREMENTAL_STRUCTURE` |

- **Brier skill:** at or below about zero for all three.
- **Coin gate:** passed (p 0.51–0.70), but not assessable at this power.
- **BTC alone:** −5.1, +3.9 and −3.3 pp, all with wide intervals.

**Replication.** There was no `PROMISING_PROTOTYPE`, so no replication outcome was read.

**Bot.** Three `NOT_CONFIRMED` `/research` lines; the alert texts are unchanged.

```
WINDOWS_CONSUMED = six-coin Binance 2020-2024 for PRICE_STRUCTURE.levels, SPOT_PERP.spot_confirmation, SPOT_PERP.volume_share (DH2 states)
TESTS_EXECUTED = 2 families (TF-DH2-L-LEVEL-HOLD, TF-DH2-B-BARRIER); PROMISING_PROTOTYPES = 0; RERUN_AUTHORIZED = false
OBJECTS_2025_2026_USED = none; E1 / B2-06 untouched
```

## 2026-10-04 — DH3: five cards of three (direction and range), frozen before any outcome

**Owner decision** (`DH3_DESIGN.md`):
- 15 hypotheses in 5 cards: positioning (OI metrics), liquidity (bookDepth), options (DVOL), levels extended, and spot↔perp at one second (aggTrades);
- 9 range endpoints (bar log 1.15) and 6 directional endpoints (bar 3 pp);
- OI history and heavy free data allowed; funding and the premium index stay out (MARKET-04H, B2-06).

**Data pinned** (free):
- BTC metrics: 1583 days;
- bookDepth, six coins 2023–2024: 4386 objects, 18 missing days;
- Deribit DVOL hourly for BTC/ETH: 66144 rows, committed CSV;
- aggTrades USD-M and spot BTC 2020–2024: 120 monthly zips verified, streamed into 4368 stress-hour features.

**Outcome-blind feasibility** (`DH3_FEASIBILITY.{md,json}`): 14 cells executable; DH3-S2 `INFORMATIONALLY_WEAK` (MDE 6.7 pp).

**PRE_FREEZE_DEFINITIONAL_CORRECTION:**
- **Error:** card L's two-year surface could never meet the 3-calendar-year rule.
- **Fix:** half-year epochs were declared before any outcome.
- **Unchanged:** no state, bar or endpoint.

```
SEARCH_FAMILY = SF-DH3; TEST_FAMILIES = TF-DH3-P, TF-DH3-L, TF-DH3-O, TF-DH3-V, TF-DH3-S (14 primary cells)
PREREG = docs/research/DH3_PREREG.json; MARKET_OUTCOMES_OPENED = NO at freeze; OBJECTS_2025_2026_USED = none
```

## 2026-10-04 — DH3 executed once: two promising cells (P3 crowd positioning, V3 retests), range states below the bar

**Discovery** (`DH3_RESULT_DISCOVERY.json`), 14 cells:
- **DH3-P3** `PROMISING_PROTOTYPE`: −5.92 pp, CI −8.32 … −3.52, Brier +0.0024, negative in every year.
- **DH3-V3** `PROMISING_PROTOTYPE`: +3.87 pp, CI +1.58 … +6.15.
- **Significant but below the 15 % range bar:**
  - P1 +13.4 %;
  - O2 +9.6 %;
  - L3 +6.5 %;
  - S1 −5.9 %;
  - V2 +2.3 %.
- **Null or heterogeneous:** P2, L1, L2, O1, O3, V1, S3.

**Replication** (`DH3_RESULT_REPLICATION.json`, card V only). DH3-V3 on spot BTC/ETH/BNB/XRP 2017–2019 gave −0.71 pp (CI −4.75 … +3.06). That is `REPLICATION_INCONCLUSIVE` (the surface was underpowered), and the effect did not show.

**Bot.** `/research` gains 14 lines; there is no alert change and no deploy.

```
WINDOWS_CONSUMED = BTC 2020-2024 OI metrics + long/short ratio; six-coin bookDepth 2023-2024; BTC/ETH DVOL 2021-2024; BTC aggTrades stress features 2020-2024; six-coin levels 2020-2024 (session, key-level controls, retests); spot 2017-2019 for DH3-V3
TESTS_EXECUTED = 5 families; PROMISING_PROTOTYPES = 2; SUPPORTED = 0; RERUN_AUTHORIZED = false; OBJECTS_2025_2026_USED = none
```

## 2026-10-04 — Owner decision: DH3 closed

The owner merged DH3 and declared it `CLOSED`. P3 live tracking is not started. The merge triggers no deploy. DH3-P3 and DH3-V3 stay `PROMISING_PROTOTYPE`; the bot shows them only as «Гипотеза» lines in `/research`. Any later live test is a new unit with its own owner go.

```
DH3_STATUS = CLOSED; LIVE_TRACKING_P3 = NOT_STARTED; DEPLOY = none; WINDOWS_CONSUMED = none by this record
```

## 2026-10-05 — Compiler V3 variance line closed; evidence-and-claims model adopted

**Owner decision.** The compiler V3 variance research line is closed (`docs/research/COMPILER_V3_VARIANCE_LINE_CLOSURE_V1.md`). The line covered the variance-floor validation (Official Run 1 → `VARIANCE_MODEL_REDESIGN_REQUIRED`), the redesign (`NEXT_VALIDATION_POSSIBLE = NO`) and the exposed-variance estimator calibration (Official Run 1 → `ESTIMATOR_CALIBRATION_FAIL_INFORMATION_INSUFFICIENT`).
- Both official results stand as recorded. There is no Official Run 2, no repair and no recomputation.
- **Reason:** at the project's N, guaranteeing in advance both near-absolute coverage safety and practical utility is a dead end. This is a negative methodological result, not evidence about market structure.
- **Audit trail:** the full record was merged unchanged from `research/hypothesis-evaluation-contract-v2-draft` at `8909f50`.

**New research model.** `docs/research/EVIDENCE_AND_CLAIMS_DECISION_V1.md` applies to new units and is not retroactive.
- **Before the outcome:** a design note (estimand, method chosen by design, comparison, what changes our mind, variants tried).
- **Result:** reported as evidence (estimate, uncertainty, information, stability, falsification, limitations, search exposure).
- **Claims:** a separate claim decision on the L0–L4 ladder. L2 directional historical wording is quantitative. L3 needs live calibration.
- **Journal:** a prospective claim journal (`docs/BETA_CLAIM_JOURNAL_DESIGN_V1.md`, design only).
- **Contracts:** contract V2 draft is not adopted and is superseded as the plan. Contract V1 keeps its force for units registered under it.

**Shadow formatting exercise.** Not a test.
- Expectations were committed first (`6b0b542`). Then DH1-L2, R03-C1 and D12 were written in the new result record from their own records only (`docs/research/EVIDENCE_FORMAT_SHADOW_REPORT_V1.md`).
- Outcome: `FORMAT_DISTINGUISHES_THE_THREE_TYPES`. No status, verdict, ledger row, atlas unit or findings entry changed.

**Next unit recorded, not executed.** `WEEKDAY_WEEKEND_BASELINE_UNIT_V2` (`docs/WEEKDAY_WEEKEND_BASELINE_UNIT_V2.md`), a `PRODUCT_EVIDENCE` unit. It supersedes revision 5 of the weekday/weekend design as the plan; that revision was merged unchanged from `product/weekday-weekend-baseline-calibration-design-v2`.

```
COMPILER_V3_VARIANCE_LINE = CLOSED; OFFICIAL_RUN_2 = never; RESULTS_CHANGED = none
CONTRACT_V2_DRAFT = NOT_ADOPTED / SUPERSEDED_AS_PLAN; CONTRACT_V1 = in force for its units
WINDOWS_CONSUMED = none by this record; MARKET_DATA_READ = none; OBJECTS_2025_2026_USED = none
```

## 2026-10-05 — Closed-line tombstone; weekday/weekend baseline unit V2 executed once

**Preflight repairs before the run (owner).**
1. **Window.** The window was restored to 2020–2024 (amendment A1, `2c1aed2`, committed before any rate was computed). The only 2020 constraint is objective point-in-time: no pinned data before 2020-01-01, so each candidate's reference matures on its own calendar; warm-up hours are counted, not removed.
2. **Tombstone.** The compiler V3 official entry points are hard-refused by an operational tombstone (`docs/research/CLOSED_RESEARCH_LINES_V1.json`, `scripts/research/closed_lines.py`, installed from the packages' `__init__.py`). Frozen code and artifacts are unchanged; override only by a new owner reopen authorization.

**Unit.** `WEEKDAY_WEEKEND_BASELINE_UNIT_V2`, track `PRODUCT_EVIDENCE`.
- **Run:** once. Evaluator committed first (`86b2c09`).
- **Data:** `CORE_BTC_BINANCE_V0` 2020–2024 through the pinned R03 loader (digest `93659495…`), single-venue proxy.
- **Result:** `CHANGE_BASELINE (C1)`.
  - C0 weekend gate qualification is 2.4 % vs weekday 7.1 %, `P_S` 20.9 pp.
  - C1 (same day type within the 30-day window): `P_S` 2.0 pp, all gaps within about ±2 pp.
  - C2 is not robust (overdispersion); C3 is eligible at 2.9 pp.
- **No product change made**; no directional or edge claim.
- **Exposure:** the surface 2020–2024 was already exposed by R03 and is used as product evidence.

```
WINDOWS_CONSUMED = none new (2020-2024 already exposed); LIVE_TAPE_READ = no; OBJECTS_2025_2026_USED = none
PRODUCT_CHANGE = none (C1 needs a separate owner go); CLAIM_JOURNAL = not started; PR_328 = not merged
```

## 2026-10-05 — Research history audit V1 (forensic census; no verdict changed)

**Record.** `docs/research/RESEARCH_HISTORY_AUDIT_V1.md`, with the JSON, the per-unit table, the assessments file and the builder `scripts/research/history_audit.py`.

**Census.** 188 units: the 187 atlas units plus `WEEKDAY_WEEKEND_BASELINE_UNIT_V2`. Listed separately: 6 child executions, 6 methodology units, and the non-units (16 linked generator attempts, 10 never-produced ladder slots, H-001..H-016). The completeness proof reconciles the memory chain, the test ledger, the findings registry, this ledger's headings and the research file names, with zero unplaced ids.

**Reading.**
- 57 research units have a computed outcome. Of these, 34 are genuine nulls or negatives.
- 27 units died from lack of information; 20 of these are honest limits.
- 7 closures were driven by a framework rule against measured or available information (R03-C1, D3, DH3-P1, DH3-O2, DH3-L3, G01-A1, G01-A2), and 11 partly so.
- The main methodology problems:
  - fixed magnitude bars used as verdict switches;
  - stacked feasibility screens before any estimate;
  - gate conjunctions without conjunction power;
  - a verdict vocabulary that mixes precise nulls with uninformative results.

**Holes recorded:**
- B2-02: durable result copy unavailable.
- B2-05: bytes not provable, so not recoverable.
- E1: holdout opened by P4, so no clean confirmation remains.
- `WEEKDAY_WEEKEND_BASELINE_UNIT_V2` is not yet an atlas unit.

```
VERDICTS_CHANGED = none; RESULTS_CHANGED = none; MARKET_DATA_READ = none; RERUNS = none
WINDOWS_CONSUMED = none; OBJECTS_2025_2026_USED = none; E1 / V3 / B2-06 untouched
PROPOSED (owner go needed, design note before outcome) = turn-of-month baseline (G01-A1/A2); D8-successor shock-recovery object
```

## 2026-10-06 — Turn-of-month baseline unit V1 executed once; NO_CHANGE

**Unit.** `TURN_OF_MONTH_BASELINE_UNIT_V1` (atlas `TOM-BASELINE-V1`), tracks `PRODUCT_EVIDENCE` (Part B, decides) and `STRUCTURE` (Part A, L1 at most). It succeeds G01-A1/A2, which stay closed as recorded.
- **Owner go:** 2026-10-06. One official run strictly per the design note, `CORE_BTC_BINANCE_V0` 2020–2024, no 2025/2026 slice, no plan change after outcomes.
- **Before the outcome:** design note `54421a0`; evaluator and tests committed and pushed before the run (`1067bcb`); raw output `c6d60d8`.
- **Data:** the pinned R03 loader (digest `93659495…`, 60 zips SHA-verified); trade count from column 8 of the same zips, aligned on `open_ms`; single-venue proxy. Calendar: G01 day sets on [2020-01-31, 2025-01-01): 202 TOM / 826 MID days, 58 months with both sets.
- **Part B (C1, deployed):** `NO_CHANGE`.
  - 0 labels `BEYOND_TOLERANCE`.
  - 1 `WITHIN_TOLERANCE`: the 1h band move ≤ 0.20.
  - 12 `NOT_RESOLVED`.
  - The activity labels fire less on TOM days: 1h flags D −1.5 to −1.8 pp (TOM within ±0.4 pp of nominal, MID +1.1 to +1.5 pp above); TOD −5.1 / −5.3 pp; 24h range −9.4 pp. No interval lies wholly past τ.
  - C0 gives the same statuses.
- **Part A:** TOM days were quieter than days 8–21 of the same month.
  - Volume −0.24 SD (95 % −0.44 … −0.03).
  - Trade count −0.32 SD (−0.52 … −0.12).
  - Range −0.24 SD (−0.46 … −0.01).
  - 58 months; the sign agrees in 4/5, 5/5 and 5/5 years.
  - The note's rule permits an L1 line. It is not shown: a findings entry needs its own product go (registry `no_bot_context`).
  - The sign is opposite to G01's declared expectation. No G01 verdict changes.
- **Records:** `docs/TURN_OF_MONTH_BASELINE_UNIT_V1_RESULT.md` (+ `.json`); atlas event seq 7 (`UNIT_ADDED`).

```
WINDOWS_CONSUMED = none new (2020-2024 already exposed; first turn-of-month contrast on it, recorded as exposure CALENDAR.month_boundary)
OBJECTS_2025_2026_USED = none; BITMEX_READ = no; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched
PRODUCT_CHANGE = none; CORRECTION_UNIT = not proposed (Part B NO_CHANGE); BOT_LINE = none (needs a product go)
```

## 2026-10-07 — LEVEL_TOUCH_DEGRADATION_V1 executed once; L2; not integrated

**Unit.** `LEVEL_TOUCH_DEGRADATION_V1` (atlas `LEVEL-TOUCH-DEGRADATION-V1`), family `LEVEL_BEHAVIOR_V1`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim ceiling L2. It does not rescore DH1-L2 or DH3-V3.
- **Owner go:** the task of 2026-10-07. One official run. Design note `65015c2` before any break rate. Evaluator guard `d79801f1` before the run. No threshold, horizon, definition, baseline or grouping was added after the rates were read.
- **Data:** `CORE_BTC_BINANCE_V0` 5m bars, 2020-01-01 through 2024-12-31, events from 2020-02-01. Price only. No 2025/2026 slice, no live tape, no funding, no liquidations, no OI, no order book. The E1 holdout was not read. The 2020–2024 level row was already consumed by DH1-L2; this run is additional exposure, not a confirmation.
- **Estimand:** difference in historical 4h `BREAK_FIRST` between independent touch 2 and touch 3+ and touch 1, standardized on level family, approach side and pre-touch volatility tercile. Baseline is touch 1 in the same structural population. Falsification is a deterministic half-rotation pseudo-level.
- **Primary:** crude `BREAK_FIRST` 40.1% / 37.6% / 33.6% (N 1905 / 1101 / 1185). Standardized Δ2 −2.3 pp (95% −6.0..+1.5). Standardized Δ3 −6.6 pp (95% −10.7..−2.2). `REJECT_FIRST` stays near 50%. `NEITHER` rises from 9.6% to 17.1%. Analysis N 4191, 258 week clusters.
- **Stability:** crude Δ3 is negative in 2020, 2021, 2022 and 2024 (−7.3, −10.8, −7.7, −6.5 pp) and about zero in 2023 (+0.1 pp). Busiest year 21.4%. Busiest touch-3+ family (week) 42.2%. Support-side crude Δ3 −1.9 pp; resistance-side −10.9 pp.
- **Falsification:** pseudo-level standardized Δ2 +7.3 pp (95% +3.8..+10.7), Δ3 +4.7 pp (95% −0.1..+9.8). Opposite sign. The control interval for Δ3 includes 0.
- **Claim:** L2. The allowed sentences are the quantitative cohort frequencies in the result record. Not a current probability. Not “the level weakens”.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = YES` under the predeclared conjunction. No `/btc`, `/levels`, scoring, findings-registry or deploy change. Successors named and not run: `LEVEL_REJECTION_MEMORY_V1`, `LEVEL_APPROACH_STATE_V1`, `LEVEL_CONFLUENCE_V1`.

```
WINDOWS_CONSUMED = none new (2020-2024 PRICE_STRUCTURE.levels already consumed by DH1-L2; this touch-ordinal contrast is recorded as further exposure)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
```

## 2026-10-07 — LEVEL_REJECTION_MEMORY_V1 executed once; L2; near zero; not integrated

**Unit.** `LEVEL_REJECTION_MEMORY_V1` (atlas `LEVEL-REJECTION-MEMORY-V1`), family `LEVEL_BEHAVIOR_V1`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim ceiling L2. Successor of `LEVEL_TOUCH_DEGRADATION_V1` / PR #352 / `dfc9e0f04358de15606382472badeb5aee787039`. It does not rescore that unit, DH1-L2 or DH3-V3.
- **Owner go:** the task of 2026-10-07. One official run. Design note `c8a1d4d2` before any next-touch rate. No threshold, horizon, feature, baseline or grouping was added after the rates were read.
- **Data:** `CORE_BTC_BINANCE_V0` 5m bars, 2020-01-01 through 2024-12-31, events from 2020-02-01. Price only. No 2025/2026 slice, no live tape, no funding, no liquidations, no OI, no order book. The E1 holdout was not read. The 2020–2024 level row was already consumed; this run is additional exposure, not a confirmation.
- **Cohort:** consecutive independent touches of the same structural zone where the previous touch was `REJECT_FIRST` and a later independent touch exists. Predictors are known before the next touch.
- **Estimand:** change in historical 4h `BREAK_FIRST` per +1 SD faster prior rejection. Speed is the frozen z-score of −log(bars to the reject barrier). The linear probability model adjusts for next-touch ordinal, family, side, volatility tercile, year and log wait after the rejection bar. Baseline is the same structural next-touch population. Falsification is a deterministic half-rotation pseudo-level scored on the real scales.
- **Primary:** −0.1 pp (95% −2.9..+2.6), N=1151, 283 clusters. The interval includes 0 and the absolute coefficient is below the 3 pp reading scale. `REJECT_FIRST` +1.0 pp (95% −1.9..+3.9). `NEITHER` −0.8 pp (95% −2.7..+1.0). Crude tertile `BREAK_FIRST` shares 39.2% / 39.7% / 39.4% (N 385 / 408 / 358).
- **Adjustment checks:** without the touch-ordinal control −0.2 pp (95% −2.9..+2.5). Without the log-wait control +0.2 pp (95% −2.4..+3.0). Neither reveals a hidden association.
- **Stability:** year coefficients −3.4 / −3.2 / +5.5 / +1.3 / +0.4 pp (2020–2024); signs flip; every year interval includes 0. Family DAY +0.6, WEEK −1.1, MONTH −1.3 pp. Resistance −2.5 pp, support +2.0 pp. Busiest year 22.1%. Busiest family 60.5%.
- **Falsification:** pseudo-level primary +1.2 pp (95% −1.9..+4.3), N=1055, 245 clusters. Two control-year intervals exclude 0 (2023 +15.5 pp, 2024 −9.0 pp); those cells stay in the predeclared table and are not a new claim.
- **Claim:** L2. The allowed sentence is the quantitative cohort frequency in the result record. Not a current probability. Not “a strong rejection makes a strong level”. The cohort is levels that rejected and were later retested.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = NO` under the predeclared conjunction. No `/btc`, `/levels`, scoring, findings-registry or deploy change. Successors named and not run: `LEVEL_APPROACH_STATE_V1`, `LEVEL_CONFLUENCE_V1`.

```
WINDOWS_CONSUMED = none new (2020-2024 PRICE_STRUCTURE.levels already consumed; this rejection-memory contrast is recorded as further exposure)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
```

## 2026-10-07 — LEVEL_APPROACH_STATE_DISCOVERY_V1 executed once; discovery; no successor; not integrated

**Unit.** `LEVEL_APPROACH_STATE_DISCOVERY_V1` (atlas `LEVEL-APPROACH-STATE-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Family-statement claim L2. A cell selected by the successor rule would be `DISCOVERY_ONLY`; none was selected. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039`, #353 `c3d39bffda861b535605a98205d7578c0c84c782`, #354 methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`. It does not rescore those units, DH1-L2 or DH3-V3.
- **Owner go:** the task of 2026-10-07. One official run. Design note `778e23dd` before any approach-conditioned outcome rate. Result commit `3cd68af0`. No feature, window, horizon, interaction or threshold was added after the rates were read.
- **Data:** `CORE_BTC_BINANCE_V0` 5m bars, 2020-01-01 through 2024-12-31, events from 2020-02-01. OHLC and quote volume. No taker-buy quote, no OI, no funding, no liquidations, no order book, no 2025/2026 slice, no live tape. The E1 holdout was not read. The 2020–2024 level row was already consumed; this run is additional exposure, not a confirmation.
- **Cohort:** independent touches of ex-ante structural zones with an observed entry into the outer band `1.0 ×` primary X and at least four in-band bars ending at the bar before the touch. Features use only bars before the touch.
- **Family:** velocity, efficiency, persistence, acceleration, range state, relative quote volume, dwell. Pullback was dropped before outcomes because it is exactly `(1 − efficiency) / 2` (ρ = −1). Search exposure 441 cells. Benjamini–Hochberg at q = 0.10 on the 21 primary slopes only.
- **Primary:** N=1973, 1210 episode clusters, 3 ambiguous touches dropped. Four slopes have absolute value at least 3 pp and an interval that excludes 0. Velocity → BREAK_FIRST −3.9 pp (95% −7.3..−0.5, q=0.122). Efficiency → NEITHER +4.4 pp (95% +2.2..+6.8, q=0.002). Dwell → REJECT_FIRST −3.0 pp (95% −5.3..−0.7, q=0.059). Dwell → NEITHER +4.7 pp (95% +2.6..+6.7, q=0.000). Acceleration stays within about 1 pp on every outcome.
- **Why none is a successor:** DAY is 72.9% of the analysis sample, above the frozen 70% cap. On the pseudo-level, those four coefficients are +4.0, +3.9, −4.2 and +4.1 pp; none satisfies the control clause. Year signs of the four structural slopes agree, and leave-one-year-out keeps the sign. Dropping log approach length flips velocity → BREAK_FIRST to +1.2 pp and efficiency → NEITHER to −1.8 pp. Touch ordinal does not account for the slopes.
- **Routing:** `STRUCTURE_PRESENT_BUT_UNSTABLE`. Atlas `CLOSED_ON_SURFACE`. `SUCCESSOR_CANDIDATE = NONE`. Interactions estimated: 0.
- **Claim:** L2. The allowed sentence is the quantitative cohort contrast in the result record. Not a current probability. Not “a fast approach breaks the level”. The cohort is structural touches that showed a full approach episode.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change. Confirmation was not started. `LEVEL_APPROACH_FLOW_INCREMENTAL_V1` was not started.

```
WINDOWS_CONSUMED = none new (2020-2024 PRICE_STRUCTURE.levels already consumed; this approach-state matrix is recorded as further exposure)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no
```

## 2026-10-07 — LEVEL_STRUCTURE_DISCOVERY_V1 executed once; discovery; no successor; not integrated

**Unit.** `LEVEL_STRUCTURE_DISCOVERY_V1` (atlas `LEVEL-STRUCTURE-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Family-statement claim L2. A cell selected by the successor rule would be `DISCOVERY_ONLY`; none was selected. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039`, #353 `c3d39bffda861b535605a98205d7578c0c84c782`, #354 methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`, #355 `aa85e5b43c405ee225336ff385e3a3383fa59d09`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. One official run. Design note `1ac77d2d` before any feature-conditioned outcome rate. No feature, tolerance, horizon, interaction, pseudo construction or threshold was added after the rates were read.
- **Data:** `CORE_BTC_BINANCE_V0` 5m bars, 2020-01-01 through 2024-12-31, events from 2020-02-01. OHLC and the anchor source period's quote volume. No taker-buy quote, no OI, no funding, no liquidations, no order book, no 2025/2026 slice, no live tape. The E1 holdout was not read. The 2020–2024 level row was already consumed; this run is additional exposure, not a confirmation.
- **Cohort:** the #352 feature-eligible structural touches, restricted before outcomes to source episodes that also have a feature-complete half-rotation pseudo touch. Not the #355 approach-eligible subset. Analysis sample after the ambiguous drop: N real = 2640, N pseudo = 2634, 1227 clusters. Ambiguous bars dropped: 9 real, 12 pseudo.
- **Family:** age, binary confluence, zone span, formation range, formation volume, close-off-extreme, extreme timing, extreme density. Diversity was dropped before outcomes (binary coding, ρ = 1 with confluence). Search exposure 576 cells. Benjamini–Hochberg at q = 0.10 on the 24 primary real-minus-pseudo increments only. The #355 70% DAY cap is not a clause.
- **Primary differential:** age → NEITHER +4.2 pp (95% +2.4..+6.1, q=0.000). The real slope is −1.3 pp (95% −2.6..+0.1). The rotated-price slope is −5.5 pp (95% −6.9..−4.1). The real slope is negative in 3 of 5 years. The other 23 primary increments have q above 0.10. Confluence increments are about 0 pp with intervals of about ±8 pp (284 multi-member real touches).
- **Why none is a successor:** the frozen rule requires the real-effect sign in at least 4 eligible years. Leave-one-year-out and leave-one-family-out keep the age → NEITHER increment positive; that is not sufficient. The approach-path sensitivity was not run, because it cannot name a candidate.
- **Routing:** `STRUCTURE_PRESENT_BUT_UNSTABLE`. Atlas `CLOSED_ON_SURFACE`. `SUCCESSOR_CANDIDATE = NONE`. Interactions estimated: 0.
- **Claim:** L2. The allowed sentence is the quantitative cohort increment in the result record. Not a current probability. Not “an old level is weaker” and not “confluence is stronger”.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change. Confirmation was not started.

```
WINDOWS_CONSUMED = none new (2020-2024 PRICE_STRUCTURE.levels already consumed; this structure matrix is recorded as further exposure)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no
```

## 2026-10-07 — LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1 executed once; L2; replicated historical resolution gap; not integrated

**Unit.** `LEVEL_FIRST_TOUCH_RESOLUTION_CONFIRMATION_V1` (atlas `LEVEL-FIRST-TOUCH-RESOLUTION-CONFIRMATION-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = CONFIRMATION`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2, a replicated historical mechanism. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039`, #353 `c3d39bffda861b535605a98205d7578c0c84c782`, #354 methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`, #355 `aa85e5b43c405ee225336ff385e3a3383fa59d09`, #356 `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. One official run. Design note `a4f3a0d6` before any BitMEX barrier rate. No horizon, barrier, zone, rotation, level type or threshold was added after the rates were read.
- **Question.** The post-hoc #352 description, which was not that unit's primary hypothesis, was that a real structural first touch resolves into BREAK or REJECT within 4h more often than the matched pseudo first touch (about +12 pp on Binance 2020–2024). That surface cannot confirm it. This unit asks the same contrast on time-disjoint BitMEX XBTUSD.
- **Data:** `DH1_BITMEX_XBTUSD_TRADES_5M_V0`, canonical SHA256 `df3c32922e95bdca80fcf0fa695ec2c8f29455cf8c1ab930277e92c994b4995f`, grid 2017-08-01 through 2019-12-31, events from 2017-09-01. Before this run the atlas status was feasibility-exposed and the DH1 replication outcomes had not been read. This run consumes the surface for this resolution contrast. No 2025/2026 object, no live tape, no E1 holdout.
- **Cohort:** touch number 1 of PDH, PDL, PWH, PWL, PMH and PML, paired with the unchanged #352 half-rotation control. Availability-matched pairs 558. Analysis pairs 548 after excluding 10 pairs with an ambiguous label (4 real, 7 pseudo). 119 product weeks. Epoch counts 100 / 250 / 198.
- **Primary:** Δ_resolution = +8.0 pp (95% +4.4..+11.8). Real resolution rate 91.1%. Pseudo resolution rate 83.0%. Discordant pairs: real resolved and pseudo unresolved 80; the reverse 36; both resolved 419; both unresolved 13. The adjusted coefficient on the real-touch indicator is +7.9 pp (95% +4.0..+11.7).
- **Stability:** epoch points +5.0, +5.2 and +13.1 pp, all positive. Leave-one-epoch-out points +8.7, +10.4 and +5.1 pp, all positive. The 2017H2 and 2018 intervals include 0. The predeclared sign rule uses the point estimates and holds. Family points: DAY +8.5 pp (N=480), WEEK +5.1 pp (N=59), MONTH 0.0 pp (N=9, both sides resolved on every pair). Side points: resistance +7.2 pp, support +8.8 pp.
- **Decomposition:** BREAK +10.0 pp (95% +4.6..+15.4), REJECT −2.0 pp (95% −7.1..+3.0), NEITHER −8.0 pp (95% −12.0..−4.1). The resolution gap sits in BREAK versus NEITHER. REJECT does not decide the confirmation.
- **Evidence label:** `REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE`. All five predeclared clauses hold. This is a description of the frozen rule, not the word PASS.
- **Claim:** L2. The allowed sentence is that the first touch of a pre-known structural level historically resolved into one of the two barrier outcomes within 4 hours more often than the matched pseudo-price touch. Not a current probability. Not a direction. Not L3.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = YES` by the rule frozen before the outcome. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change. Integration was not performed.

```
WINDOWS_CONSUMED = DH1_BITMEX_XBTUSD_TRADES_5M_V0 PRICE_STRUCTURE.levels 2017-09-01..2019-12-31, for RESOLVED_WITHIN_4H real versus matched pseudo first touch (previously EXPOSED by DH1 feasibility counts only)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 / B2-06 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
PRODUCT_INTEGRATION_CANDIDATE = YES; INTEGRATION_PERFORMED = no; SUCCESSOR_STARTED = no
```

## 2026-10-07 — LEVEL_POSITIONING_FLOW_DISCOVERY_V1 executed once; discovery; no incremental position/flow structure; not integrated

**Unit.** `LEVEL_POSITIONING_FLOW_DISCOVERY_V1` (atlas `LEVEL-POSITIONING-FLOW-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2, a family statement. A selected cell would have been discovery-only; none was selected. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039`, #353 `c3d39bffda861b535605a98205d7578c0c84c782`, #354 methodology `8effe9acc3b88b925a79b33f04ac0ee9e6f93e26`, #355 `aa85e5b43c405ee225336ff385e3a3383fa59d09`, #356 `f8623d3281424c165ebd7ee7fbcb0af994cc1e8d`, #357 `c1cd4e0102e700f7860d21a9af0d243c3bc367be`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. One official run. Design note `2491bbe9277faa24f0e5e3a295bbe6a01672ddf9` before any feature-conditioned outcome rate. No window, formula, FDR threshold, practical scale, outcome or interaction was added after the rates were read.
- **Question.** #357 established that a first touch of a pre-known structural level resolves within 4h more often than a matched pseudo-price. This unit asks which point-in-time open-interest and aggressive-flow states, if any, distinguish “resolves or stalls” and “if resolved, BREAK or REJECT”, beyond the frozen price and context baseline, and whether that association is specific to the structural price.
- **OI authority:** the seven outcome-blind conditions passed. Git snapshot `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`. `oi.jsonl` SHA256 `c4744a9369844f453476589111c2436372e729e7afdbe5fb34b6e9938a905b94`, 455273 native 5m rows, `available_at = period_start + 5m`. Only `sum_open_interest`. Funding was not opened. The B2-06 contract was not edited. `research_authorized` stays false. This is not B2-06 crowding science and not a rescue of H05, MARKET-01/02 or DH1-X2.
- **Data:** `CORE_BTC_BINANCE_V0`, zip-list SHA256 `936594956e8bfea33eec09a7e61dbbc8051bb4c0d4d083abdbcb6091c62aa90b`. Events `[2020-09-01T01:05:00Z, 2025-01-01T00:00:00Z)`. Observed first touch 2020-09-01T05:55:00Z, last 2024-12-31T12:30:00Z. No 2025/2026 object, no E1 holdout.
- **Cohort:** touch number 1 of PDH, PDL, PWH, PWL, PMH and PML. Geometry-legitimate first touches 1708. Ambiguous labels 10, excluded from rates. On 1698 labeled touches: BREAK 688 (40.5%), REJECT 843 (49.6%), NEITHER 167 (9.8%), resolve rate 90.2%. 227 product weeks. Redundancy before outcomes: maximum absolute correlation 0.267; all four features retained.
- **Primary:** eight adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. None passes the conjunction. Nearest cell: OI recent acceleration → BREAK given resolved, +2.90 pp (95% +0.43..+5.50), p=0.027, q=0.201, N=1513. Epoch points +0.34 / +2.66 / +4.48 / +4.97 / +2.85 pp, all positive. Leave-one-year-out points +3.43 / +3.48 / +2.66 / +2.17 / +2.95 pp, all positive. It fails q=0.10 and the 3 pp scale. The other seven primary intervals include 0 or the absolute estimate is below 3 pp, and their q-values are above 0.10.
- **Specificity:** three stacked real-minus-pseudo intervals exclude 0 (oriented taker → resolve −4.35 pp; acceleration → break +4.21 pp; oriented taker → break +5.32 pp). They are not candidates. The real-cohort conjunction failed, so neither `LEVEL_INTERACTION_CANDIDATE` nor `GENERIC_STATE_CANDIDATE` is assigned.
- **Shape:** five frozen tertile tables are U-shaped. Recorded as exploratory successor ideas. No threshold or interaction was fit.
- **Routing:** `NO_INCREMENTAL_POSITION_FLOW_STRUCTURE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim:** L2. A historical association in this first-touch cohort. Not a current probability. An OI increase is more outstanding open interest. Oriented flow is aggressive executed volume toward the level. Not L3.
- **Product:** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-09-01..2024-12-31, pre-touch taker quote imbalance into first-touch resolution type (further exposure, not a confirmation)
WINDOWS_CONSUMED = B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0 OI leg only, sum_open_interest, same window, covariate of first-touch resolution; funding.jsonl not opened; B2-06 crowding still unauthorized
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-07 — LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1 executed once; discovery; no incremental joint-state structure; not integrated

**Unit.** `LEVEL_FLOW_RESPONSE_STATE_DISCOVERY_V1` (atlas `LEVEL-FLOW-RESPONSE-STATE-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. A selected state would have been discovery-only; none was selected. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #358 `e6e5f307cfa098db607544a556bae01a2310eb6a`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. Design note `59361e92bf2e2e49507ae59e4d34b41801ff6739` before any state-conditioned resolution rate. K, the scaler, the centroids, the window, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is a joint predictor configuration at a structural first touch. It is not H05 (taker imbalance to subsequent return) and not B2-05 (`ABS_IMB * FLOW_RET` on a generic 15m grid to a subsequent return). Open interest is required. Price progress is oriented by the approach side and is not multiplied by flow. Atlas row `PRICE_STRUCTURE.levels`.
- **Partition, before outcomes.** Robust-z KMeans on 1688 predictor-complete first touches. K=3 selected (silhouette 0.270, median ARI 0.892). K=4 failed the ARI gate. K=6 failed the minimum size. K=5 was eligible and lost on silhouette. Training counts 190 / 1178 / 320. Pseudo rows were assigned to the frozen centroids (1074) and did not enter the fit.
- **Primary.** Six state-versus-rest contrasts, q=0.10, scale 3 pp. None passes. STATE_1 → RESOLVE_4H is +3.33 pp (95% −1.18..+7.53, q=0.354, n_state=186): the point clears 3 pp and the epoch and leave-one-year-out signs agree, and the interval includes 0. STATE_3 → BREAK given resolved is +5.37 pp (95% −1.08..+11.93, q=0.354, n_state=292); the 2020Q4 point has the opposite sign. The bars were not loosened.
- **Specificity.** Three stacked intervals exclude 0, including STATE_1 → BREAK −17.6 pp, where the pseudo-only coefficient is +14.8 pp. They are not candidates. The real-cohort conjunction failed.
- **Routing.** `NO_INCREMENTAL_JOINT_STATE_STRUCTURE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. A historical frequency in this cohort. Not a current probability. Not an absorption story.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No product change.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-09-01..2024-12-31, joint pre-touch OI/taker/price-progress state into first-touch resolution (further exposure, not a confirmation)
WINDOWS_CONSUMED = B2_06 OI leg only, sum_open_interest, same window, one coordinate of that state; funding.jsonl not opened; B2-06 crowding still unauthorized
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-07 — LEVEL_LIQUIDITY_STATE_DISCOVERY_V1 executed once; discovery; no incremental level-liquidity structure; not integrated

**Unit.** `LEVEL_LIQUIDITY_STATE_DISCOVERY_V1` (atlas `LEVEL-LIQUIDITY-STATE-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Any selected cell would have been discovery-only on an already exposed book surface; none was selected. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #359 `bcc0a9e8a5c2af221b23b72768d7b7ba1d6a4aa2`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. Design note `f7430ca27c664e3669d7adb633561ba381a598e3` before any feature-conditioned resolution rate. The band, the 90-second staleness, the 60-minute lag, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is the local book state around a structural first touch: approach-oriented ±1% notional, measured strictly before the touch, with a pseudo-price control, and with resolution rather than range or up-first as the endpoint. It is not DH3-L1 (all-hours thin-book quintile → range), not DH3-L2 (all-hours bid-heavy quintile → up first), not DH3-L3 (book recovery 30 minutes after a sharp move → range), and not the SEED-0001 ±5% binary support state. Reopen key `NEW_MECHANISM`. The surface stays discovery-only.
- **Book.** `DH3_BINANCE_UM_BOOKDEPTH_V0`, object-list SHA256 `c53fc179d922f83b572703d52e80f847fb54531961ac776929f2e3e95feeddce`. BTCUSDT, 728 verified days, missing 2023-02-08, 2023-02-09 and 2024-04-18. 2,068,585 snapshots. Native bands −5..−1 and +1..+5. No band inside ±1%. No price ladder. Term: `LOCAL_BOOK_STATE_AROUND_LEVEL_TOUCH`. Staleness 90 seconds, from a ~30-second cadence. 767 of 790 geometry-legitimate first touches had both legal snapshots.
- **Cohort.** Touch number 1 of PDH, PDL, PWH, PWL, PMH and PML, window `[2023-01-01T02:00:00Z, 2025-01-01)`. Geometry-legitimate 790. Ambiguous 5, excluded from rates. On 785 labeled touches: BREAK 290 (36.9%), REJECT 425 (54.1%), NEITHER 70 (8.9%), resolve rate 91.1%. Book-legal primary N: RESOLVE 762, BREAK given resolved 695. 106 weeks. All five features retained. Maximum absolute correlation before outcomes 0.780.
- **Primary.** Ten adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. None passes. Nearest: total local depth → RESOLVE −2.61 pp (95% −4.93..−0.50, q=0.203), below 3 pp; total local depth → BREAK +4.03 pp (95% −0.30..+8.05, q=0.203), interval includes 0; oriented imbalance → BREAK +3.93 pp (95% −0.42..+7.83, q=0.203), interval includes 0 and 2024H1 flips sign. The bars were not loosened.
- **Specificity.** No stacked real-minus-pseudo interval excludes 0. A pseudo-only oriented-imbalance → RESOLVE slope of +5.09 pp (95% +1.64..+8.65) is descriptive. The real slope is −0.06 pp, so it is not a generic candidate.
- **Shape.** Three frozen tertile tables are U-shaped. Recorded as exploratory ideas. No threshold was fit.
- **Routing.** `NO_INCREMENTAL_LEVEL_LIQUIDITY_STRUCTURE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. A historical association in this first-touch cohort. Not a current probability. Not a statement that a thick book holds or a thin book breaks.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2023-01-01..2024-12-31, local book state at structural first touches into resolution type (further exposure, not a confirmation)
WINDOWS_CONSUMED = DH3_BINANCE_UM_BOOKDEPTH_V0 BTCUSDT 2023-01-01..2024-12-31, ±1% notional at those touches; surface already consumed by DH3-L; not a reopen of DH3-L1/L2/L3 or SEED-0001
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-07 — LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1 executed once; discovery; structure present but unstable; not integrated

**Unit.** `LEVEL_POST_TOUCH_REACTION_DISCOVERY_V1` (atlas `LEVEL-POST-TOUCH-REACTION-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only on an already consumed level surface. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #360 `181debc4aa626637f2cd560103447d2d4adc96b1`. It does not rescore those units.
- **Owner go:** the task of 2026-10-07. Design note `f3101015f33b19d38b38c226891422c5863cc723` before any late resolution rate. The 15-minute window, the early exclusion, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is a state update 15 minutes after a #352 structural first touch, on events that have not yet reached either barrier, with the outcome equal to the remainder of the original 4h. It is not H02 (rolling-range wick → signed return), not B2-02, and not V2 `CONFIRMED_BREAKOUT`. No acceptance, reclaim, or failed-break flag was fit. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels`.
- **Clock.** T is the open of touch bar j. D = T+15m. Reaction features use bars j, j+1 and j+2. Early passage uses j+1 and j+2 and does not treat the touch bar as a resolution. Late passage uses j+3 through j+48.
- **Cohort.** Window `[2020-09-01T00:05:00Z, 2025-01-01)`. Geometry-legitimate first touches 1709. Early BREAK 260, early REJECT 238, early ambiguous 9, unresolved 1202, unavailable 0. On unresolved events: late BREAK 428, REJECT 606, NEITHER 167, ambiguous 1. Primary N: late resolve 1201, late break given resolved 1034. 227 weeks. All five features retained. Maximum absolute correlation before outcomes 0.828.
- **Primary.** Ten adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. `END_POSITION_X` → late BREAK +20.31 pp (95% +17.20..+23.46, q=0.0000, N=1034). All five years and all five leave-one-year-out fits stay positive. Resistance +20.02 pp and support +21.06 pp. The conjunction fails only because leave-one-family-out omitting DAY returned no coefficient (complement N=122). DAY itself is +20.20 pp and WEEK is +19.45 pp. The other nine cells fail q, the 3 pp scale, or the interval. The bars were not loosened.
- **Specificity.** Not promoted. Pseudo and stacked intervals were withheld: valid week-cluster draws were below the frozen 90 percent line. The pseudo end-position → late BREAK point is +30.13 pp (N=413) and is descriptive only.
- **Shape.** Relative activity versus late resolve, and OI change versus late break, are U-shaped on frozen tertiles. Recorded as exploratory ideas. No threshold was fit.
- **Routing.** `STRUCTURE_PRESENT_BUT_UNSTABLE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. A historical association in this unresolved first-touch cohort. Not a current probability. Not an acceptance rule and not a failed break.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-09-01..2024-12-31, 15m post-touch reaction into the remainder of the original 4h (further exposure, not a confirmation)
WINDOWS_CONSUMED = B2_06_BINANCE_UM_BTCUSDT_OI_FUNDING_V0 sum_open_interest only, prints at T and at T+15m; funding.jsonl not opened; B2-06 crowding remains unauthorized
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1 executed once; discovery; no incremental path memory; not integrated

**Unit.** `LEVEL_ACCEPTANCE_PATH_DISCOVERY_V1` (atlas `LEVEL-ACCEPTANCE-PATH-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only on an already consumed level surface. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #361 `44726ded55c75fefecc6848ab8b76971ead83721`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `bae1060c390e049f652c57792b8c18fc1c41058e` before any late BREAK rate. The states, the overlap rule, the arm minimum, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is path memory within the first 15 minutes after a structural first touch, inside one endpoint side, with `END_POSITION_X` held as a nuisance. It is not H02, not B2-02, not V2 `CONFIRMED_BREAKOUT`, and not a rescore of the #361 endpoint slope. `REENTERED` is not labelled a false break. `PERSISTENT_OUTSIDE` is not labelled acceptance. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels`.
- **Clock.** T is the open of touch bar j. D = T+15m. Bits use the closes of j, j+1 and j+2 against the break-side zone edge. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.
- **Cohort.** Window `[2020-02-01T00:00:00Z, 2025-01-01)`. Price OHLC only. Geometry-legitimate first touches 1919. Early BREAK 296, early REJECT 278, early ambiguous 13, unresolved 1332. States: never outside 983, reentered 115, late or recross 80, persistent 154. 258 weeks.
- **Gate.** C1 overlap passed (standardized endpoint difference +1.27; 62.6% and 53.8% of each arm inside the other central band). C2 was not estimated: the late-or-recross arm has 80 unresolved events. Its overlap would have passed. The taxonomy was not changed.
- **Primary.** One adjusted contrast, Benjamini–Hochberg q=0.10, practical scale 3 pp. `REENTRY_MEMORY` +6.74 pp (95% −4.22..+17.62, q=0.2218, N=952, arms 101 and 851, 2000 valid draws). The interval includes 0. Eligible years do not share one sign. Leave-one-year-out omitting 2022 changes sign. DAY is +8.99 pp and WEEK is −12.72 pp, both estimable and opposite. Resistance is −3.46 pp and support is +18.59 pp, both estimable and opposite. No candidate.
- **Specificity.** Not applied. The pseudo reentry slope is +9.52 pp (95% −9.68..+28.77, N=300, treated arm 26). The interval includes 0. It does not rescue the real null.
- **Routing.** `NO_INCREMENTAL_PATH_MEMORY_BEYOND_ENDPOINT`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. A historical adjusted difference in this unresolved first-touch cohort. Not a current probability. Not a false break and not acceptance.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-02-01..2024-12-31, 15m close-path memory conditional on END_POSITION_X into the remainder of the original 4h (further exposure, not a confirmation)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; OI / funding / book / taker not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1 executed once; discovery; one level-interaction candidate; not integrated

**Unit.** `LEVEL_CROSS_VENUE_REACTION_DISCOVERY_V1` (atlas `LEVEL-CROSS-VENUE-REACTION-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #362 `b005eaac895d3a4c644d16101d2e5eb7d2ff8d5f`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `f21be5a6cd022e3c8aacceccf8d13c61106e3b83` before any late BREAK rate. The venue set, the −3h Bybit label offset, the 15-minute window, the four features, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is the 15-minute price reaction of other linear perpetuals around a Binance structural first touch, with `END_POSITION_X` held in every model. It is not MARKET-06 (Binance USD-M versus OKX BTC-USDT spot, daily absolute dislocation, 24h adverse-path MAE, `MARKET_06_NO_EVIDENCE`). It is not `CROSS_VENUE_REGION.venue_disagreement`, not DH3-X6, and not the V2 `price_direction_agreement` gate. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `CROSS_VENUE`.
- **Data.** Tier A, frozen before outcomes. Binance USD-M BTCUSDT perpetual is the only structural venue. Bybit BTCUSDT linear perpetual public MT4 5m closes, canonical SHA256 `f7ef739f7d359056cbbf78a77993995f54e3303e50775b5aadf36b4ba68f507c`, label clock UTC+3. OKX BTC-USDT-SWAP `history-candles` confirm=1, canonical SHA256 `b435fdec219df96e88e2ae4b65c04e16217af16f327aae36dca148d9203172a8`. OKX spot was not used. No 2025/2026 object was requested.
- **Clock.** T is the open of Binance touch bar j. D = T+15m. Each venue return is the log close at D over the close of the bar opening at T−5m. Alignment tolerance is 0. A missing bar drops the event. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.
- **Cohort.** Window `[2020-04-01T00:05:00Z, 2025-01-01)`. Geometry-legitimate first touches 1856. Early BREAK 286, early REJECT 265, early ambiguous 13, unresolved 1292. Feature-complete unresolved 1235; the only missingness is Bybit, 57 events. Late labels: BREAK 439, REJECT 621, NEITHER 174, ambiguous 1. Primary N=1060. Pseudo primary N=612. 238 weeks. All four features retained. Maximum absolute correlation before outcomes 0.630.
- **Baseline.** `END_POSITION_X` +20.30 pp per +1 SD (95% +17.41..+23.17, N=1060, 2000 valid draws).
- **Primary.** Four adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. `OTHER_VENUE_MEDIAN_MOVE` +8.87 pp (95% +5.02..+12.67, q=1.70e-5, N=1060). Same-model end position +13.43 pp. Five eligible years; four match the full-sample sign, including a negative 2020 point whose interval includes 0. Leave-one-year-out stays positive. DAY +8.63 pp and WEEK +5.60 pp. Resistance +5.10 pp; support point +13.63 pp with the interval withheld. The confirmation gap, dispersion and direction agreement fail the statistical gate. Direction-agreement tertiles collapse because the mass sits at 1. No two-thirds threshold was fit.
- **Specificity.** Applied to CV1 because the real conjunction passed and the matched pseudo N is 612. Pseudo-only slope −1.61 pp (95% −6.17..+2.85). Stacked delta −4.24 pp (95% −7.96..−0.05, N=1223). The frozen rule names `LEVEL_CROSS_VENUE_INTERACTION_CANDIDATE`. The stacked real slope on that matched sample is about zero and does not reproduce the primary +8.87 pp. The classification was not refit.
- **Routing.** `LEVEL_CROSS_VENUE_STRUCTURE_PRESENT`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. A historical adjusted association in this unresolved first-touch cohort. Not a current probability. Not a statement that another venue led or caused the barrier.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change. Direction #4 was not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-04-01..2024-12-31, Binance structural reference for the 15m cross-venue reaction (further exposure, not a confirmation)
WINDOWS_CONSUMED = BYBIT_BTCUSDT_PUBLIC_HISTORY BTCUSDT linear perpetual 5m closes 2020-03-31T21:00Z..2024-12-31T20:55Z, four public-file holes left missing
WINDOWS_CONSUMED = OKX_OFFICIAL_ARCHIVES BTC-USDT-SWAP 5m history-candles 2020-04-01..2024-12-31, confirm=1; MARKET-06 OKX spot dataset not read
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; OI / funding / book / taker not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1 executed once; discovery; no incremental spot reaction; not integrated

**Unit.** `LEVEL_SPOT_PERP_REACTION_DISCOVERY_V1` (atlas `LEVEL-SPOT-PERP-REACTION-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #363 `f22100177e2f89a43c6271929aba0d63f7b4552f`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `98c750a4cf8df7d2b7b1262506129372bb2dc785` before any late BREAK rate. The spot source, the window, the three features, the relative formulas, the baseline, q and the 3 pp scale were not changed after the rates were read.
- **Novelty.** The object is the 15-minute Binance spot reaction after a structural first touch, with `END_POSITION_X` and `OTHER_VENUE_MEDIAN_MOVE` held in every model. It is not DH1-L1 / DH2-L1 pre-touch hour flow, not DH1-B1 sign confirmation, not DH1-B2 / DH2-B2 spot share, not D9 or DH3 lead/lag, and not MARKET-06. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `SPOT`. The cross-perp coefficient is a control, not a confirmation of #363.
- **Data.** Binance USD-M BTCUSDT perpetual is the structural venue. Spot is `DH1_BINANCE_SPOT_BTCUSDT_5M_V0`, months 2020-04..2024-12, taker-buy quote present, 355 of 499968 bars missing and left missing. Bybit and OKX are the pinned #363 perpetuals, not reminted. No 2025/2026 object was requested. No OKX spot.
- **Clock.** T is the open of Binance touch bar j. D = T+15m. Returns use the close at D over the close of the bar opening at T−5m. Alignment tolerance is 0. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.
- **Cohort.** Window `[2020-04-01T00:05:00Z, 2025-01-01)`. Geometry-legitimate first touches 1856. Early BREAK 286, early REJECT 265, early ambiguous 13, unresolved 1292. Feature-complete unresolved 1234. SP3 legal rate 1.0. All three features retained. Maximum absolute correlation among them 0.082. SP1 correlation with the cross-perp control 0.998, recorded before outcomes and not used as a drop. Late labels: BREAK 439, REJECT 620, NEITHER 174, ambiguous 1. Primary N=1059. 238 weeks.
- **Baseline.** `END_POSITION_X` +13.36 pp per +1 SD (95% +9.38..+17.51, N=1059, 2000 valid draws). `OTHER_VENUE_MEDIAN_MOVE` +9.08 pp (95% +5.17..+12.84). The control is not in the FDR family.
- **Primary.** Three adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. SP1 +32.97 pp (95% −12.36..+76.94, q=0.228). SP2 +2.29 pp (95% −0.30..+5.12, q=0.228). SP3 −1.29 pp (95% −4.04..+1.57, q=0.385). No interval excludes 0. No feature clears the statistical gate. SP1 year signs are three of five. SP1 DAY and WEEK have opposite signs. SP3 resistance and support points have opposite signs. None of those slices is a candidate. Raw SP1 tertiles repeat the cross-perp gradient and are not an incremental spot effect.
- **Specificity.** Not applied. No full-sample candidate. No matched delta was estimated.
- **Routing.** `NO_INCREMENTAL_SPOT_PERP_REACTION`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. No incremental historical association for the spot layer in this unresolved first-touch cohort, beyond Binance end position and the other perpetual venues' 15-minute move. Not a current probability. Not a statement that spot led or that the move is only a leveraged-complex fact in a causal sense.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry or deploy change. Lead/lag, time-to-resolution, a volatility transition, confirmation, a 30-minute window, a liquidation map and prospective tracking were not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-04-01..2024-12-31, Binance structural reference and reaction-bar taker quote for the spot-versus-perp question (further exposure, not a confirmation)
WINDOWS_CONSUMED = DH1_BINANCE_SPOT_BTCUSDT_5M_V0 Binance spot BTCUSDT 5m 2020-04..2024-12, taker-buy quote included, 355 missing bars left missing; 2017-2019 not read
WINDOWS_CONSUMED = BYBIT_BTCUSDT_PUBLIC_HISTORY BTCUSDT linear perpetual 5m closes reused as the cross-perp control; not reminted
WINDOWS_CONSUMED = OKX_OFFICIAL_ARCHIVES BTC-USDT-SWAP 5m history-candles reused as the cross-perp control; MARKET-06 OKX spot dataset not read
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; funding / book / liquidation / OI not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1 executed once; discovery; resolution clock faster than pseudo; not integrated

**Unit.** `LEVEL_TIME_TO_RESOLUTION_DISCOVERY_V1` (atlas `LEVEL-TIME-TO-RESOLUTION-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #364 `7c297997da263e286524fd939e4a536dfa42002c`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `56b162f07e69f3e8a4b6784e18dc497ea5a7d042` before any barrier time. The horizon, the time origin, the ambiguity rule, the RMUT restriction, the checkpoint grid, and the 15-minute scale were not changed after the times were read.
- **Novelty.** The object is the time from a structural first touch until the frozen BREAK or REJECT barrier, compared with the matched pseudo-price touch. It is not the #352 touch-ordinal rate, not the #357 4h resolution probability, and not `GV0R01-C024` (round numbers, order-book depth, ±0.2% exit, 6h cap). Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `CANDLES`.
- **Data.** Price only. Binance USD-M BTCUSDT perpetual, `CORE_BTC_BINANCE_V0`. Window `[2020-02-01, 2025-01-01)`. No 2025/2026 object was requested. No spot, other venue, book, taker, or open interest.
- **Clock.** T is the open of touch bar j. Bar j is not a resolution. A hit on bar j+k has time `5 * k` minutes. AMBIGUOUS counts for any-resolution. No hit by j+48 is right-censored at 240 minutes and is not stored as an observed event time.
- **Cohort.** Real legitimate first touches 1919. Pseudo legitimate 1962. Matched pairs 1231. Unusable clocks 0. Real censored 107. Pseudo censored 207. 254 weeks.
- **Primary.** Real RMUT_240 64.24 minutes. Pseudo 89.39 minutes. Delta −25.15 minutes (95% −31.42..−19.07, 2000 valid draws). The interval excludes 0 and the absolute difference clears 15 minutes.
- **Stability.** Years −40.39 / −29.84 / −7.75 / −22.65 / −23.70. Five of five share the negative sign. The 2022 point is under 15 minutes; the frozen rule is a sign rule and was not rewritten. Leave-one-year-out stays negative. DAY −24.91 and WEEK −28.91. Resistance −22.88 and support −28.05. MONTH N=22 is descriptive.
- **Descriptive curve.** Real resolved-by rates at 15/30/60/120/240 minutes: 0.401 / 0.529 / 0.673 / 0.807 / 0.913. Pseudo: 0.299 / 0.410 / 0.548 / 0.696 / 0.832. The conditional hazard is higher for real in every predeclared interval. No cutoff was selected. BREAK and REJECT quartiles are conditional on kind and are not a directional candidate.
- **Routing.** `LEVEL_RESOLUTION_CLOCK_STRUCTURE_PRESENT`. Class `LEVEL_RESOLUTION_CLOCK_CANDIDATE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. First touches of these structural levels historically spent less time unresolved, inside the same 4h horizon, than the deterministic pseudo-price touches. Not a current expected number of minutes. Not a statement that the level expires after N minutes.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No ACTIVE, STALE, countdown, or push change. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry, or deploy change. False-break semantics, acceptance, a 30-minute threshold, current hazard calibration, and a product timer were not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-02-01..2024-12-31, price OHLC only, structural first-touch resolution clock versus half-rotation pseudo (further exposure, not a confirmation)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; spot / other venue / book / taker / OI / funding / liquidation not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1 executed once; discovery; no incremental sequence structure; not integrated

**Unit.** `LEVEL_BREAK_REJECT_SEQUENCE_DISCOVERY_V1` (atlas `LEVEL-BREAK-REJECT-SEQUENCE-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #365 `3ad8431ee62cc48c86eeaeface9b50884babfbbe`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `fcfc3e438e4cbea4213e8284a4cb851234e030f0` before any post-first opposite-barrier scan. The six classes, the 4h horizon, the parent first-event rule, the 5 pp scale, and the FDR were not changed after the sequences were read.
- **Exposure.** `FIRST_EVENT_TYPE_ALREADY_EXPOSED = true`. Parent BREAK / REJECT / NEITHER / AMBIGUOUS counts were already known. `POST_FIRST_OPPOSITE_BARRIER_SEQUENCE_NOT_YET_READ = true` at the design commit. The sequence was then read once.
- **Novelty.** The object is whether the opposite frozen barrier is reached after the first one-sided hit, inside the original 4h event, relative to the matched pseudo touch. It is not H02, not the V2 false-break lifecycle, not the #362 path predictor, and not the #365 resolution clock. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `CANDLES`.
- **Data.** Price OHLC only. Binance USD-M BTCUSDT perpetual, `CORE_BTC_BINANCE_V0`. Window `[2020-02-01, 2025-01-01)`. No 2025/2026 object was requested. No volume, taker, open interest, spot, other venue, or book.
- **Cohort.** Real legitimate first touches 1919. Pseudo legitimate 1962. Matched pairs 1231. Unusable windows 0. Real first events: BREAK 579, REJECT 539, AMBIGUOUS 6, NEITHER 107. Pseudo: BREAK 467, REJECT 549, AMBIGUOUS 8, NEITHER 207. 254 weeks. Both denominator gates pass.
- **P1.** Later REJECT given FIRST_BREAK: real 18.13% (105/579), pseudo 14.99% (70/467), delta +3.15 pp (95% −1.23..+7.56, p=0.160, q=0.320, 2000/2000). Under 5 pp. Interval includes 0. Class `NONE`. Years +2.04 / +4.81 / +8.26 / +7.39 / −7.64. Four of five share the sign. 2024 is opposite and above 5 pp; the frozen rule was not rewritten. Leave-one-year-out stays positive.
- **P2.** Later BREAK given FIRST_REJECT: real 20.22% (109/539), pseudo 18.94% (104/549), delta +1.28 pp (95% −3.27..+5.95, p=0.578, q=0.578). Under 5 pp. Interval includes 0. Class `NONE`. Years +9.27 / +2.69 / −4.40 / −0.45 / −2.25. The year rule fails, and omitting 2020 flips the leave-one-year-out sign. The contrast is not statistical, so this is not an unstable structure.
- **Descriptive.** Two-sided traversal 17.87% real versus 14.78% pseudo (+3.09 pp). One-sided resolution 73.44% versus 68.40% (+5.04 pp of all pairs). That unconditional share is not a primary. Conditional on the first event, the one-sided gaps are the negatives of P1 and P2. Reversal-delay medians: real break-then-reject 70 min (N=105), real reject-then-break 90 min (N=109). No delay cutoff was tested.
- **Routing.** `NO_INCREMENTAL_SEQUENTIAL_OUTCOME_STRUCTURE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. The historical conditional reversal rates do not differ from the matched pseudo touch by the frozen 5 pp bar. Not a current false-break probability. Not an acceptance probability.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No `FALSE_BREAK`, `ACCEPTED_BREAK`, `CONFIRMED_REJECT`, or whipsaw alert. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry, or deploy change. Volume-at-level, acceptance thresholds, a close-based false-break rule, cross-venue composition, and prospective confirmation were not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-02-01..2024-12-31, price OHLC only, post-first opposite-barrier sequence versus half-rotation pseudo (further exposure, not a confirmation)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; volume / taker / OI / spot / other venue / book / funding / liquidation not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1 executed once; discovery; no incremental zone-traded activity; not integrated

**Unit.** `LEVEL_ZONE_TRADED_ACTIVITY_DISCOVERY_V1` (atlas `LEVEL-ZONE-TRADED-ACTIVITY-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #366 `b411cff97309fbb12450b0f095f96fea6e84c3d3`. It does not rescore those units.
- **Owner go:** the task of 2026-10-08. Design note `ee2abb0dd3c4c6b0b9d2e2e1a0b48ba1ebfa6e19` before any late BREAK label. The zone, the 15-minute window, the 60-minute normalizer, ZA1–ZA3, the redundancy rule, the baseline, q and the 3 pp scale were not changed after the labels were read.
- **Novelty.** The object is unsigned Binance USD-M quote notional inside the exact structural zone during `[T, D)`, incremental to `END_POSITION_X` and `OTHER_VENUE_MEDIAN_MOVE`, with touch offset as a nuisance. It is not H05 signed imbalance, not B2-05 absorption, not DH3-S large prints, not #360 displayed depth, not the #361 taker coordinate, not the #362 close path, and not the #366 barrier sequence. Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `PERP_FLOW`. The cross-perp coefficient is a control, not a confirmation of #363.
- **Data.** Official USD-M BTCUSDT aggTrades, 58 months `2020-03` through `2024-12`, each checksum-verified. March 2020 is lookback only. Aggregate digest `af1eb088ac0fc7e860cbd211f654d3fd7cf8332588fa03c91b22131f37e34970`. Raw zips deleted. Quantity is base BTC; quote notional is price times quantity. Aggressor side was not used. Bybit and OKX are the pinned #363 perpetuals, not reminted. No 2025/2026 object was requested. No spot trades.
- **Clock.** T is the open of touch bar j. D = T+15m. `TAU_TOUCH` is diagnostic only. Real touch match 1832/1856 = 0.987. Pseudo 1163/1183 = 0.983. Early passage uses j+1 and j+2. Late passage uses j+3 through j+48.
- **Cohort.** Window `[2020-04-01T00:05:00Z, 2025-01-01)`. Geometry-legitimate first touches 1856. Unresolved with nuisance 1235. Common retained support 1215. ZA3 dropped before outcomes (Spearman 0.925 with ZA2). Late labels on that support: BREAK 432, REJECT 612, NEITHER 170, ambiguous 1. Primary N=1044. 238 weeks.
- **Baseline.** `END_POSITION_X` +13.13 pp per +1 SD (95% +8.70..+17.39, N=1044, 2000 valid draws). `OTHER_VENUE_MEDIAN_MOVE` +9.33 pp (95% +5.35..+13.35). Touch offset −0.09 pp (95% −3.34..+2.97). The controls are not in the FDR family.
- **Primary.** Two adjusted slopes, Benjamini–Hochberg q=0.10, practical scale 3 pp per +1 SD. ZA1 −0.95 pp (95% −4.25..+2.27, q=0.557). ZA2 −1.76 pp (95% −5.19..+1.48, q=0.557). Neither clears 3 pp or excludes 0. Years are four of five on the pooled negative sign; 2023 is opposite (ZA1 +3.19 pp, ZA2 +4.84 pp). The frozen five-year rule still passes and was not rewritten. Leave-one-year-out stays negative. DAY and WEEK are both negative. Resistance and support are both negative. Raw ZA1 tertile late-BREAK rates are 31.67% / 42.24% / 50.89%. That unadjusted gradient is not the estimand and was not promoted.
- **Specificity.** Not applied. No full-sample candidate. No matched delta was estimated.
- **Routing.** `NO_INCREMENTAL_ZONE_TRADED_ACTIVITY`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. No incremental historical association for unsigned executed activity inside the structural zone, beyond Binance end position, the other perpetual venues' 15-minute move, and the touch offset. Not a current probability. Not absorption, defense, or a statement that volume confirms a break.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No volume-confirmation badge, absorption state, acceptance state, or level-strength score. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry, or deploy change. A taker split, another zone width, a 30-minute or 60-minute window, a large-trade threshold, BitMEX replication, and prospective confirmation were not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-04-01T00:05Z..2024-12-31, structural reference for unsigned zone executions after a first touch (further exposure, not a confirmation)
WINDOWS_CONSUMED = BINANCE_UM_TRADES_AGGTRADES_ARCHIVE USD-M BTCUSDT aggTrades 2020-03..2024-12, event-level unsigned quote notional only; aggressor side unused; raw zips not retained
WINDOWS_CONSUMED = BYBIT_BTCUSDT_PUBLIC_HISTORY BTCUSDT linear perpetual 5m closes reused as the cross-perp control; not reminted
WINDOWS_CONSUMED = OKX_OFFICIAL_ARCHIVES BTC-USDT-SWAP 5m history-candles reused as the cross-perp control; MARKET-06 OKX spot dataset not read
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; spot aggTrades / book / funding / liquidation / OI not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1 executed once; discovery; volatility-transition candidate; sequence 8/8 complete; not integrated

**Unit.** `LEVEL_VOLATILITY_TRANSITION_DISCOVERY_V1` (atlas `LEVEL-VOLATILITY-TRANSITION-DISCOVERY-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = DISCOVERY`, tracks `STRUCTURE` and `PRODUCT_EVIDENCE`. Claim L2. Discovery only. Dependencies: #352 `dfc9e0f04358de15606382472badeb5aee787039` through #367 `fcdf650ccf58a96c54f4931c0cb5d16e7d143473`. It does not rescore those units. This is direction 8 of 8. `LEVEL_ENGINE_DISCOVERY_8_OF_8_COMPLETE = YES`.
- **Owner go:** the task of 2026-10-08. Design note `54338b7faab9598152e2fa1270d2fb51a4beed18` before any post-touch RV. The windows, the touch-bar exclusion, the RV formula, the 10% scale, and the stability rules were not changed after the transitions were read.
- **Novelty.** The object is the paired difference in `log(RV_POST60 / RV_PRE60)` between a structural first touch and its exact #352 pseudo touch. It is not H01 (no compression screen), not B2-01 (no forecast target), and not DH3-V2 (not a 4h high-low range and not a random level). Reopen key `NEW_MECHANISM` on `PRICE_STRUCTURE.levels` × `CANDLES`. Not placed on `VOLATILITY_STATE.compression`, `VOLATILITY_STATE.regime_transition`, or `VOLATILITY_STATE.range_forecast`.
- **Data.** Price closes only. Binance USD-M BTCUSDT perpetual, `CORE_BTC_BINANCE_V0`. Window `[2020-02-01, 2025-01-01)`. No 2025/2026 object was requested. No volume, taker, open interest, spot, other venue, or book.
- **Clock.** T is the open of touch bar j. Pre returns are assigned to j−12..j−1. Post returns are assigned to j+1..j+12. The touch-bar return is in neither window. `RV = sqrt(mean(r^2))`. No demean and no annualization.
- **Cohort.** Real legitimate first touches 1919. Pseudo legitimate 1962. Matched path-complete pairs 1231. Usable pairs 1231. Non-positive RV drops 0. 254 weeks. Years 242/334/258/181/216.
- **Pre-RV balance.** Paired mean of log(real pre / pseudo pre) is +0.56%. Below 10%. Not used as an adjustment. No rematch.
- **Primary.** `DELTA_TRANSITION` +0.106803 log units, about +11.27% on the post/pre RV multiplier (95% +0.066548..+0.146661, about +6.88%..+15.80%, p=1.048e-7, N=1231, 2000/2000, seed 20261024). The point clears `log(1.10)`. The interval excludes 0 and includes multipliers below 10%. That inclusion was not a reason to change the frozen rule. Real mean transition +0.298, pseudo +0.192. Expansion fraction, descriptive only: real 0.695, pseudo 0.611, difference +0.084.
- **Stability.** Years +16.93% / +12.05% / +0.10% / +17.52% / +12.87%. Five of five share the positive sign. 2022 is practically null; the frozen rule is a sign rule and was not rewritten. Leave-one-year-out stays positive, including omit-2020 at about +9.93%. DAY +10.06% (N=1071) and WEEK +25.63% (N=138). MONTH is −11.47% on N=22 and is diagnostic only. Resistance +14.34% (N=690). Support +7.48% (N=541), same sign and under 10%, so not a material contradiction.
- **Routing.** `LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT`. Class `LEVEL_VOLATILITY_TRANSITION_CANDIDATE`. `SUCCESSOR_CANDIDATE = NONE`.
- **Claim.** L2. Historically, realized volatility changed more across a structural first touch than across its matched pseudo-price touch, with the post/pre RV multiplier differing by about 11%. Not a current expected volatility. Not a breakout recommendation. Not a statement that the level causes volatility.
- **Product.** `PRODUCT_INTEGRATION_CANDIDATE = NO`. No volatility-expansion badge, no confirmation state, no alert. No `/btc`, `/levels`, `/check`, `/risk`, scoring, findings-registry, or deploy change. Discovery synthesis, candidate selection, and confirmation design were not started.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 PRICE_STRUCTURE.levels 2020-02-01..2024-12-31, 5m closes only, paired 60m pre/post realized-volatility transition versus half-rotation pseudo (further exposure, not a confirmation)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; volume / taker / OI / spot / other venue / book / funding / liquidation not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
SUCCESSOR_CANDIDATE = NONE; CONFIRMATION_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO; LEVEL_ENGINE_DISCOVERY_8_OF_8_COMPLETE = YES
```

## 2026-10-08 — LEVEL_ENGINE_DISCOVERY_SYNTHESIS_V1 recorded; no new market window; confirmation not started

**Record.** `LEVEL_ENGINE_DISCOVERY_SYNTHESIS_V1`. Mode `SYNTHESIS / NO_NEW_MARKET_OUTCOMES`. Not an outcome unit and not an atlas cell. Parent HEAD `fb6598aa62fc9b47cec2e9095959aa98182f0407`. Source main `1a2e425303fb29e1044ca57452b8ad9b6f0a831b`.
- **Scope.** Evidence map of #352, #353, #355, #356, #357, #358, #359, #360, #361, #362, #363, #364, #365, #366, #367, and #368. #354 is the governing discovery-first decision and is not market evidence. Frozen routes and result files were not edited. L0–L4 was not redefined.
- **Foundation.** #357 stays `FOUNDATION_CONFIRMED` (`REPLICATED_POSITIVE_RESOLUTION_DIFFERENCE`). It was not rerun.
- **Selection.** No P1 historical confirmation. Prospective sketches only: #368 paired RV transition, then #363 primary cross-venue coefficient. #365 is `DO_NOT_CONFIRM`. #361 is `DO_NOT_CONFIRM_AS_LEVEL_SPECIFIC`. Null neighborhoods are closed and not authorized.
- **Data.** No new window. No 2025/2026 object. No BitMEX outcome column. No live tape. No product change. Findings registry unchanged.

```
WINDOWS_CONSUMED = none
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
CONFIRMATION_STARTED = no; ATLAS_UPDATED = no; LEVEL_ENGINE_DISCOVERY_SYNTHESIS_RECORDED = YES
```

## 2026-10-08 — LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1 executed once; exposed-surface replication supports the frozen claim; not pristine; not integrated

**Unit.** `LEVEL_VOLATILITY_TRANSITION_BITMEX_REPLICATION_V1` (atlas `LEVEL-VOLATILITY-TRANSITION-BITMEX-REPLICATION-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = CONFIRMATION`, surface class `TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION`. Claim ceiling L2. It does not rescore #368 or #357.
- **Owner go.** The task of 2026-10-08, after `EXPOSURE_WEIGHTING_DECISION_V1` (`OWNER_DECISION_RECORDED`). Prior use of a surface is not by itself a ban. Exposure sets wording. Outcome-driven redesign is forbidden. The decision does not rewrite past results and does not change L0–L4.
- **Design.** `6d97157be44f02ad09344a00df58b715e5c8aa13`, committed before any post-touch RV. The #368 formula, the touch-bar exclusion, the 12-return windows, the 10% bar `log(1.10) = 0.09531017980432493`, the positive sign, the week-block bootstrap (B=2000, seed 20261025), the epoch sign rule, and the leave-one-epoch-out sign rule were not changed after the transitions were read. Discovery design remains `54338b7faab9598152e2fa1270d2fb51a4beed18`.
- **Why this surface.** Discovery was Binance USD-M BTCUSDT 2020–2024. This run is BitMEX XBTUSD inverse perpetual 2017–2019. Venue, contract, era, and microstructure differ. The exact 60m close RV transition had not been computed here. #357 had read `RESOLVED_WITHIN_4H` and scanned high/low on `j+1..j+48`. `EXACT_CLAIM_PREVIOUSLY_READ = false`. `NEIGHBORING_POST_TOUCH_PATH_PREVIOUSLY_READ = true`. `SURFACE_PRISTINE = false`.
- **Data.** `DH1_BITMEX_XBTUSD_TRADES_5M_V0`, canonical SHA256 `df3c32922e95bdca80fcf0fa695ec2c8f29455cf8c1ab930277e92c994b4995f`. Event window `[2017-09-01T00:00:00Z, 2020-01-01T00:00:00Z)`. August 2017 is warm-up only. No new BitMEX download. No 2020–2024 Binance reread. No 2025/2026 object. No E1 holdout. RV uses log closes only. No inverse-contract adjustment, volume, funding, taker side, trade count, or spread.
- **Events.** Exact #357 structural first-touch constructor, first touch only, half-rotation pseudo, matched pairing. Inclusion is not conditioned on BREAK, REJECT, or NEITHER. The #357 outcome label does not enter the primary frame. No first-hit time, RMUT, or hazard.
- **Information gate.** Before outcomes: 1981 structural episodes, 890 real legitimate first touches, 891 pseudo legitimate, 558 matched, 554 path-complete, 120 ISO weeks, epochs 100 / 250 / 204. Planning SE scaled from the published #368 bootstrap SE, 95% half-width about 0.057, below `log(1.10)`. Gate `REPLICATION_INFORMATION_ADEQUATE`. The Binance N=800 rule was not copied.
- **Primary.** Usable pairs 554. Non-positive RV drops 0. `DELTA_TRANSITION` +0.09654494866839887 log units, about +10.136% (95% +0.02178047720554232..+0.1681728175697164, about +2.202%..+18.314%, Wald p=0.011207, SE 0.038067, 2000/2000). The point clears `log(1.10)`. The interval excludes 0. It contains the bar and the discovery point +0.106803. That inclusion was not a reason to tighten the frozen rule.
- **Balance and expansion.** Paired mean log(real pre / pseudo pre) is about −2.05%. Not used as an adjustment. Descriptive expansion fraction: real 0.702, pseudo 0.632, difference +0.070. Descriptive only.
- **Stability.** Epochs +15.31% / +0.28% / +20.79%. All three eligible epochs are positive. 2018 is practically null; the sign rule was not rewritten. Leave-one-epoch-out stays positive: omit 2017H2 about +9.03%, omit 2018 about +18.96%, omit 2019 about +4.36%. DAY +11.16% (N=483). WEEK +4.86% (N=62), same sign and below the bar. MONTH −5.84% on N=9, diagnostic only. Resistance +13.14% (N=269). Support +7.37% (N=285), same sign and below the bar. No family winner and no side winner.
- **Comparison.** Binance discovery point about +11.272% and BitMEX about +10.136% are reported side by side. They were not pooled.
- **Routing.** `REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION`. Evidence label `REPLICATED_ON_TIME_DISJOINT_EXPOSED_SURFACE`. Post-synthesis status of the #368 object: `TIME_DISJOINT_REPLICATED_EXPOSED_SURFACE`. The #368 frozen route `LEVEL_VOLATILITY_TRANSITION_STRUCTURE_PRESENT` is unchanged.
- **Claim.** L2. The frozen structural first-touch volatility-transition relation discovered on Binance 2020–2024 also appeared on time-disjoint BitMEX 2017–2019 under the unchanged 60m definition. The BitMEX surface had previously been used for a neighboring 4h barrier-path outcome, so this is an exposed-surface historical replication rather than a pristine confirmation. Not L3. Not a current probability. Not an expected current RV. Not a trading edge. `INDEPENDENCE_FROM_RESOLUTION_CLOCK = UNRESOLVED`.
- **Product.** No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings-registry, or deploy change. No volatility badge. Prospective #368, #363, #365, a new RV window, a combined model, and a meta-analysis were not started. Prospective collection remains the next stronger layer and is not redundant with this pass.

```
WINDOWS_CONSUMED = DH1_BITMEX_XBTUSD_TRADES_5M_V0 PRICE_STRUCTURE.levels 2017-09-01..2019-12-31, 5m closes only, paired 60m pre/post realized-volatility transition versus half-rotation pseudo (further exposure; exact estimand unread before this run; neighboring 4h high/low path already consumed by #357; not pristine; not a reopen of RESOLVED_WITHIN_4H)
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run; volume / taker / OI / spot / other venue / book / funding / liquidation not opened
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
CONFIRMATION of this exact claim EXECUTED ONCE; PROSPECTIVE_STARTED = no; CROSS_VENUE_STARTED = no; PRODUCT_INTEGRATION_CANDIDATE = NO
```

## 2026-10-08 — LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1 design frozen; accrual started; no outcome

**Unit.** `LEVEL_VOLATILITY_TRANSITION_PROSPECTIVE_CONFIRMATION_V1` (atlas `LEVEL-VOLATILITY-TRANSITION-PROSPECTIVE-CONFIRMATION-V1`), family `LEVEL_BEHAVIOR_V1`, `MODE = CONFIRMATION`, `ACCRUAL = PROSPECTIVE_ONLY`. Surface class for the exact claim after the frozen start: `PRISTINE_CONFIRMATION`. Claim ceiling L2. It does not rescore #368 or the BitMEX replication.
- **Design.** `d30622de19f90efe3ee12b56fc5e2d017ef38c57`, committer time `2026-10-08T11:30:26Z`, before any prospective transition. The formula, the touch-bar exclusion, the 12-return windows, the bar `log(1.10)`, the positive sign, and the week-block bootstrap (`B=2000`, seed `20261026`) are the #368 objects.
- **Start.** `PROSPECTIVE_START_UTC = 2026-10-09T00:00:00Z`, the first UTC midnight strictly after the design commit. Resolved from git metadata. Manifest digest `0f1b26921ff73bf68403af34bef2467b4ea77cac509420ac434a543b2dc47e2c`. No market bar was used to choose it.
- **Eligibility.** An episode is prospective only when its active period opens at or after the start. Pre-start bars are warm-up for prior levels and the 24h sigma. They are not events. The pseudo map is written only after the cohort closes.
- **Stop.** Both 600 matched path-complete pairs and 104 completed weeks, checked only at 104, 130, and 156 weeks (`2028-10-06`, `2029-04-06`, `2029-10-05`). A shortfall at 156 weeks closes as information-limited and does not read the transition.
- **Status.** `PROSPECTIVE_CONFIRMATION_STARTED`. Accrual clock `AWAITING_START`. Completed weeks 0. `exact_outcome_read = false`. Evaluator: `REFUSING_PREMATURE_PROSPECTIVE_EVALUATION`. Cohort close: `REFUSING_PREMATURE_COHORT_CLOSE`.
- **Data.** Forward Binance USD-M BTCUSDT 5m closes from complete 1m bins after the start. `CORE_BTC_BINANCE_V0` is not the sample. No new database table. The product claim journal is not reused. No recovery interval has been logged.
- **Product.** No `/btc`, `/levels`, `/check`, `/risk`, Telegram, scoring, findings-registry, or deploy change. `#363`, `#365`, a joint model, and a meta-analysis were not started. There is no prospective effect to report.

```
WINDOWS_CONSUMED = none
OBJECTS_2025_2026_USED = none; LIVE_TAPE_READ = no; E1 / V3 untouched; COMPILER_V3 = not run
PROSPECTIVE_CONFIRMATION_STARTED = yes; ACCRUAL = AWAITING_START; EXACT_OUTCOME_READ = no
PRODUCT_CHANGE = none; BOT_LINE = none; FINDINGS_REGISTRY = unchanged
CROSS_VENUE_STARTED = no; COHORT_CLOSED = no; PAIR_MAP_FROZEN = no
```

## 2026-10-08 — LEVEL_RACE_FORECAST_V1 design frozen; HIST table V1 computed once on 2020–2024; model not started

**Unit.** `LEVEL_RACE_FORECAST_V1` (atlas `LEVEL-RACE-FORECAST-V1`), family `LEVEL_BEHAVIOR_V1`, program `FORECAST_LAYER_DECISION_V1`, `MODE = DISCOVERY` then one held-out read. ОПГ-2 track F1.
- **Design.** `997ba98615135b263684ad10f9c044335910a346` (`docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md` + `.json`), frozen before any race outcome; chain `bd4d257 → c0fe8ba → d7e9783 → 0ba50cd → 80fbed4 → 997ba98`.
- **Read.** `CORE_BTC_BINANCE_V0` events 2020-02-01..2024-12-31, #352 constructor unchanged: 1919 eligible first touches (T0 rows); j+1/j+2 census NEITHER 1332, BREAK 296, REJECT 278, AMBIGUOUS 13; T15 rows 1332. 121 T0 closes outside the barrier pair (B0 floor rule).
- **Table.** `docs/research/LEVEL_RACE_HIST_TABLE_V1.json`, sha256 `4f57c80065ba17482ea7cae8aa8ac732a9f3897fa58a93bb86d26ddb9224805b`, code `748dae25`. 6 T0 cells + 18 T15 cells; ladder: T0 4 CELL / 2 LOW_N (MONTH); T15 9 CELL / 3 POOLED_SIDE / 6 LOW_N. L2 descriptive; no selection, no level-effect claim.
- **Not done.** No model fit, no CV, no B1/M1/C1, no generic stream, no 2025/2026 object, no held-out read. No product file changed.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 2020-02..2024-12 PRICE_STRUCTURE.levels (further exposure, 4h race shares)
OBJECTS_2025_2026_USED = none; E1 / V3 untouched; COMPILER_V3 = not run
HIST_TABLE_V1 = computed once; MODEL = not started; HELD_OUT_READ = no
PRODUCT_CHANGE = none (table artifact only); FINDINGS_REGISTRY = unchanged
```

## 2026-10-08 — LEVEL_RACE_FORECAST_V1 development (CV 2020–2024) run once; champion M1 by the frozen rule; not frozen

**Unit.** `LEVEL_RACE_FORECAST_V1` (atlas `LEVEL-RACE-FORECAST-V1`). Design `997ba986`; code `d7012001` committed before the run. Record `docs/research/LEVEL_RACE_FORECAST_V1_DEVELOPMENT.md` / `.json`.
- **Read.** `CORE_BTC_BINANCE_V0` 2020-02..2024-12 race outcomes again (same rows as HIST V1) for rolling-origin CV; `LEVEL_CROSS_VENUE_PERP_5M_V0` 2020-04..2024-12 Bybit/OKX closes for C1; hourly generic 4h races on the same CORE bars.
- **Evidence.** Pooled out-of-fold log-loss: B0 0.8987, B1 0.9650, M1 0.8705 (gain +0.028, 95 % +0.014..+0.042), M1A 0.8883, M1B 0.8902. Champion M1 (DISCOVERY_ONLY). C1 vs base −0.006 (−0.012..+0.000). Generic G1 vs GB0 +0.036 (+0.031..+0.041).
- **Not done.** No freeze, no held-out read, no 2025/2026 object, no product display.

```
WINDOWS_CONSUMED = CORE_BTC_BINANCE_V0 2020-02..2024-12 PRICE_STRUCTURE.levels (model development, further exposure); LEVEL_CROSS_VENUE_PERP_5M_V0 2020-04..2024-12 (C1 fit); CORE 2020-02..2024-12 generic hourly 4h races
OBJECTS_2025_2026_USED = none; E1 / V3 untouched
MODEL_FROZEN = no; HELD_OUT_READ = no; PRODUCT_CHANGE = none
```

## 2026-10-09 — LEVEL_RACE_FORECAST_V1 held-out read (one-shot): case B at T0 and T15; state HIST; level offset not claimed

**Unit.** `LEVEL_RACE_FORECAST_V1` (atlas `LEVEL-RACE-FORECAST-V1`). Model frozen `50eeb39b` (model sha256 `454109c8…0d3a`, FREEZE_DATE 2026-10-09). Architect go 2026-10-09T09:02:49Z; run once from main `bd35820b` (clean), exit 0. Record `docs/research/LEVEL_RACE_FORECAST_V1_HELDOUT.md` / `.json` (sha256 `6c6c5739…be34`).
- **Read.** Binance USD-M BTCUSDT 5m klines 2024-12 (warm-up) and 2025-01-01 → 2026-10-08 via the product planner (50 objects, checksum-verified); 11 objects overlapping the E1-RUN-001 holdout refused before any request; event spans touching [2026-08-16, 2026-08-26) excluded. Surface class TIME_DISJOINT_EXPOSED_SURFACE_REPLICATION-like.
- **Evidence.** Scored T0 698 / T15 564, 92 weeks. Raw M1 vs B0: T0 +0.010 (−0.018..+0.038), T15 −0.000 (−0.027..+0.027) nats. Raw M1 vs G1@event: T0 +0.052 (+0.013..+0.090), T15 +0.024 (−0.014..+0.062). Case B at both. Fallback G2 fails (NEITHER CITL −18.8 / −15.7 pp); G1 gate fails; state at switch HIST at both.
- **Not done.** No user-facing change, no journal write, no flag change; C1 not evaluated.

```
WINDOWS_CONSUMED = BINANCE_UM_KLINES_5M_PRODUCT 2025-01-01..2026-10-08 (minus E1 objects) PRICE_STRUCTURE.levels held-out read (one-shot)
OBJECTS_2025_2026_USED = 49 kline objects (+ 2024-12 warm-up); E1 objects refused; E1 / V3 untouched
MODEL_FROZEN = 50eeb39b; HELD_OUT_READ = yes (once); CASE = B/B; STATE = HIST/HIST; PRODUCT_CHANGE = none
```

## 2026-10-12 — RANGECAST_V2 development (folds 2021–2024) and one time-disjoint exposed read of 2025–2026; W_L1 selected; not wired

**Unit.** `RANGECAST_V2` (owner go 2026-10-12: the forecast track). Design `1774cfb` before any outcome; development `2d5be72`; read `078fa27`. Records `docs/research/RANGECAST_V2_RESULT.md`, `RANGECAST_V2_DEVELOPMENT.json`, `RANGECAST_V2_READ_2025_2026.json`.
- **Read.** Binance USD-M BTCUSDT 5m klines 2020-01-01 → 2026-10-11 via the product planner (112 objects, checksum-verified, list digest `17eac792…0e45`); 11 objects overlapping the E1-RUN-001 holdout refused before any request. Touch outcomes of hourly anchors on a 16-point log grid per horizon, both sides; folds 2021–2024 for the whole 8-model menu; 2025-01-01 → 2026-10-11 once, for the selected model and V1 only.
- **Evidence.** 4h log loss per anchor, V1 0.41402; W_L1 0.41000, −0.0040 (95 % −0.0047..−0.0034), negative in each fold year; L2 and L3 rejected against L1; LightGBM diagnostic +0.0172 against W_L1. Read 2025–2026: −0.0057 (−0.0067..−0.0047) at 4h, −0.0037 at 1h, −0.0072 at 24h.
- **Not done.** No production change, no journal write, no user-facing probability changed; atlas registration pending (`build_atlas --check` fails on main for an unrelated registry id).

```
WINDOWS_CONSUMED = BINANCE_UM_KLINES_5M_PRODUCT 2020-01..2024-12 (touch outcomes, model development, further exposure); 2025-01-01..2026-10-11 minus E1 objects (one read, selected model vs V1)
OBJECTS_2025_2026_USED = kline objects of the product planner; E1 objects refused; E1 / V3 untouched
MODEL_SELECTED = W_L1 (L1 scale set, recency half-life 365 d); PRODUCT_CHANGE = none
```

## 2026-10-12 — RANGECAST_V2 shadow readiness: W_L1 frozen, paired adapter, audit on the development folds; promotion rule frozen; shadow not started

**Unit.** `RANGECAST_V2` follow-up (owner go 2026-10-12: prepare the paired shadow). Records `docs/research/RANGECAST_V2_SHADOW_AUDIT.md` / `.json`, `RANGECAST_V2_SHADOW_PARITY.json`, `RANGECAST_V2_W_L1_MODEL_V1.json`; `docs/RANGECAST_V2_SHADOW_CONTRACT_V1.md`, `docs/RANGECAST_V2_SHADOW_PLAN_V1.md`.
- **Read.** The development folds 2021–2024 again (anchor offsets, tails, «ни один», planning numbers); no new window. One W_L1 fit on the product surface 2020-01-01 → 2026-10-11 for the frozen artifact, no outcome scored. The 2025–2026 read was not repeated; E1 objects never requested.
- **Not done.** No production change, no journal write, no user-facing probability changed; the shadow needs the journal track's writer and an owner go.

```
WINDOWS_CONSUMED = none new (development folds 2021-2024 re-read for engineering checks)
OBJECTS_2025_2026_USED = product-planner kline objects for the artifact fit only (no outcome); E1 objects refused; E1 / V3 untouched
PROMOTION_RULE = RANGECAST_V2_PROMOTION_RULE_V1 frozen before any shadow outcome; PRODUCT_CHANGE = none
```

## 2026-10-12 — RANGECAST_V2 shadow integrated with the paired shadow store; identity covers the procedure; promotion rule V2; shadow not started

**Unit.** `RANGECAST_V2` follow-up. Owner decision of 2026-10-12: use the journal track's store (`BETA_PAIRED_SHADOW_CONTRACT_V1.md`) and no second shadow-claims system; W_L1 refitted nightly is the evaluated procedure; the promotion rule blocks an observed 4h result against W_L1 and only recommends. Records:
- `docs/RANGECAST_V2_SHADOW_CONTRACT_V2.md`;
- `docs/RANGECAST_V2_SHADOW_PLAN_V2.md`;
- `docs/research/RANGECAST_V2_PROMOTION_RULE_V2_HISTORY.json` (`scripts/research/rangecast_v2/audit.py --rule-v2`);
- the addendum §5 of `RANGECAST_V2_SHADOW_AUDIT.md`.

Contract V1 and plan V1 are superseded and kept.
- **Read.** The development folds 2021–2024 again, for the weekly log-loss and Brier series of the rule's history. No new window. No 2025–2026 outcome was read and E1 objects were not requested.
- **Evidence (rule history, 100 windows of 12 weeks).**

  | Scenario | Primary and 4h gate pass | With superiority |
  |---|---|---|
  | Gain as observed | 84 % | 42 % |
  | No gain | 25 % | 2 % |
  | V2 worse by the margin | 5 % | 0 % |
- **Not done.**
  - No production change, no table, no claim and no user-facing probability changed.
  - Recording is off. It waits for the owner's go on the store's schema and writer, and on the nightly W_L1 fit.
  - The journal track has to take Amendment 1, `procedure_digest`, into #459.

```
WINDOWS_CONSUMED = none new (development folds 2021-2024 re-read for the rule's operating characteristics)
OBJECTS_2025_2026_USED = none; E1 / V3 untouched
PROMOTION_RULE = RANGECAST_V2_PROMOTION_RULE_V2 fixed before any shadow outcome (V1 superseded unused); PRODUCT_CHANGE = none
```

## 2026-10-12 — RANGECAST_V2 shadow: identity converged with the updated paired shadow store (#459)

**Unit.** `RANGECAST_V2` follow-up, engineering only. The journal track's update of #459 pinned W_L1 to the digest of `rangecast_v2.spec()`, `00539f2d…`, and added the store's hour path (`plan_shadow_record`, `execute_hour`). This branch now follows it.
- **Withdrawn.** The forecast track's `procedure_digest` amendment (entry above). Nothing was stored under it.
- **Kept on this side.** V1 is guarded by a pinned digest of its math constants, `eff8e649…`, proposed to the store as V1's spec digest.
- **Removed.** `rangecast_shadow.plan_paired_issues`, a second planning path. `paired_forecast` is the record the store's hour path stores.
- **Unchanged.** The model math, the frozen artifact, the parity record, promotion rule V2 and its history.
- **Read.** Nothing new: no market window, no 2025–2026 outcome, E1 untouched.

```
WINDOWS_CONSUMED = none
OBJECTS_2025_2026_USED = none; E1 / V3 untouched
PRODUCT_CHANGE = none
```
