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

## Next research program — hypothesis discovery after E1

Status: `AUTHORIZED_FOR_DISCOVERY / NOT YET CONFIRMATORY`.

`CORE_BTC_BINANCE_V0` is `ACCEPTED_FOR_DISCOVERY` (snapshot `717d37a4`).

Recorded discovery runs:

- `H01_COMPRESSION_EXPANSION` = `REJECTED / H01_KILL`
- `H02_FAILED_BREAKOUT_MEAN_REVERSION` = `H02_KILL`
- `H03_EXTREME_IMPULSE_CONTINUATION_EXHAUSTION` = `H03_REJECTED_SPECIFIC_CLAIM`
- `H04_TREND_PULLBACK_CONTINUATION` = `H04_REJECTED_SPECIFIC_CLAIM`

Remaining mechanism classes still untested:

- price/OI divergence;
- crowded positioning -> reversal risk.

H05 (`Taker Imbalance -> Subsequent Return Distribution`) is named in
`docs/R2_SCREENING_PROTOCOL_V1.md`'s R2 Batch 01 list but not yet started.

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