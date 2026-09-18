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

## 2026-09-18 — MARKET-03 source capture + outcome-blind feasibility

External public strategy family `EmaCross` vs `EmaCrossFunding` from
`https://github.com/wiktorj137/btc-strategy-lab` pinned at
`b68a5518b4a3eba2fde1733160d7d7de356023b5` /
tree `f7717e681c911ea3ccce15492246053cf15883cb`. Capture
`2026-09-18T16:46:53Z`. No Signalbot strategy run. No prereg, ARM, or
RESULT. Protected OOS not opened. B2-06 remains blocked.

Author trades Binance **spot** `BTC/USDT` 1h and uses perpetual REST
funding only as an entry filter (`funding_max_pct=55` on a 180d
percentile of 3-day mean funding). Signalbot has no spot BTCUSDT
dataset. CORE is USD-M perpetual and excludes spot. Funding publication
latency remains unproven.

Verdict: **`DATA_ACQUISITION_REQUIRED`**. Faithful reproduction with
current snapshots is `NOT_FEASIBLE`. Do not substitute perpetual price
for spot. Do not describe EMA=600 / funding 55 / BTC as independently
preregistered by the author.

Evidence:
`docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.md`.

- market_03_prereg: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- feasibility_verdict: **DATA_ACQUISITION_REQUIRED**

- next required step: `MARKET_03_DATA_ACQUISITION_OR_NAMED_ASSUMPTION_IF_AUTHORIZED` (not prereg, not execution)

## 2026-09-18 — MARKET-03 source capture + outcome-blind feasibility

External public strategy family `EmaCross` vs `EmaCrossFunding` from
`https://github.com/wiktorj137/btc-strategy-lab` pinned at
`b68a5518b4a3eba2fde1733160d7d7de356023b5` /
tree `f7717e681c911ea3ccce15492246053cf15883cb`. Capture
`2026-09-18T16:46:53Z`. No Signalbot strategy run. No prereg, ARM, or
RESULT. Protected OOS not opened. B2-06 remains blocked.

Author trades Binance **spot** `BTC/USDT` 1h and uses perpetual REST
funding only as an entry filter (`funding_max_pct=55` on a 180d
percentile of 3-day mean funding). Signalbot has no spot BTCUSDT
dataset. CORE is USD-M perpetual and excludes spot. Funding publication
latency remains unproven.

Verdict: **`DATA_ACQUISITION_REQUIRED`**. Faithful reproduction with
current snapshots is `NOT_FEASIBLE`. Do not substitute perpetual price
for spot. Do not describe EMA=600 / funding 55 / BTC as independently
preregistered by the author.

Evidence:
`docs/research/MARKET_03_PUBLIC_STRATEGY_SOURCE_FEASIBILITY.md`.

- market_03_prereg: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- feasibility_verdict: **DATA_ACQUISITION_REQUIRED**

- next required step: `MARKET_03_DATA_ACQUISITION_OR_NAMED_ASSUMPTION_IF_AUTHORIZED` (not prereg, not execution)


## 2026-09-18 — MARKET-03 data acquisition + provenance

Closed the source-feasibility gaps without running the strategy. Built
immutable SPOT dataset `MARKET_03_BINANCE_SPOT_BTCUSDT_1H_V0` snapshot
`2ce1f504709dc40c37a70dddcf73acb444e715820e9c855f6817c48f10d2b345`
covering `[2019-08-01, 2025-01-01)` native Binance 1h klines (47477 rows,
43 enumerated gaps, 0 duplicates). Vision USD-M `fundingRate` ZIP bytes
are 52/52 identical to B2-06 on 2020-09..2024-12. REST
`/fapi/v1/fundingRate` vs Vision `last_funding_rate`/`calc_time` matched
5481/5481 records on the authorized overlap. Publication latency remains
**UNPROVEN**. Named `fundingTime`-as-available assumption is
**ACCEPTABLE** for LEVEL_2 only and does not unblock B2-06.

Verdict: **`READY_FOR_MARKET_03_PREREG_DESIGN`**. Ceiling
`LEVEL_2_FAITHFUL_REIMPLEMENTATION`. Not LEVEL_1. Not a prereg, ARM, or
RESULT. Protected OOS not used for science.

Evidence: `docs/research/MARKET_03_DATA_ACQUISITION.md`.

- market_03_prereg: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- protected_oos_used_for_science: **false**
- b2_06_execution_authorized: **false**
- feasibility_verdict: **READY_FOR_MARKET_03_PREREG_DESIGN**
- replication_level: **LEVEL_2_FAITHFUL_REIMPLEMENTATION**
- STRICT_HISTORICAL_PUBLICATION_LATENCY: **UNPROVEN**
- REPRODUCTION_FUNDINGTIME_ASSUMPTION: **ACCEPTABLE**

- next required step: `MARKET_03_PREREG_DESIGN_IF_AUTHORIZED` (not this unit)

## 2026-09-18 — MARKET-03 preregistration design

Froze MARKET-03 scientific identity before execution. Object:
**EXTERNAL HISTORICAL CLAIM REPRODUCTION** of the pinned
`EmaCross` vs `EmaCrossFunding` drawdown-reduction claim at
`LEVEL_2_FAITHFUL_REIMPLEMENTATION`. Author open-ended `20191001-`
overlaps protected 2025/2026 OOS; evaluation truncated to
`[2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)` without opening OOS.
Primary classification is directional (`REPRODUCED_DIRECTION` /
`NOT_REPRODUCED_DIRECTION`); magnitude fidelity is descriptive (no
invented ±pp gate). B2-06 is not funding authority; ARM requires a
dedicated REST funding snapshot from already-acquired JSONL
`e7885cd5…`. No p-value. Not the live prereg.

Verdict: **`READY_FOR_MARKET_03_PREREG`**.

Evidence: `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_DESIGN.md`.

- market_03_prereg: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- design_verdict: **READY_FOR_MARKET_03_PREREG**
- replication_level: **LEVEL_2_FAITHFUL_REIMPLEMENTATION**
- STRICT_HISTORICAL_PUBLICATION_LATENCY: **UNPROVEN**

- next required step: `MARKET_03_PREREG_IF_AUTHORIZED` (not this unit)

## 2026-09-18 — MARKET-03 preregistration + freeze

Materialized and froze the MARKET-03 preregistration from the approved
design without executing the strategy. Object remains **EXTERNAL
HISTORICAL CLAIM REPRODUCTION** at
`LEVEL_2_FAITHFUL_REIMPLEMENTATION`. Evaluation truncated to
`[2019-10-01T00:00:00Z, 2025-01-01T00:00:00Z)`. Primary classification
is signed `MDD_filtered > MDD_baseline`. Funding named snapshot is a
pre-ARM required artifact. Canonical executions authorized/consumed = 0.

```text
PRE_PREREG_HEAD = 9454af65398df1d3f5e0cb3af5e48c0986049d2d
PREREG_HEAD     = 06d6ec0121a9a35f8ee947fbe89e37e97388b6e2
PREREG_MD_SHA256   = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
```

Evidence: `docs/research/MARKET_03_PUBLIC_STRATEGY_PREREG_FREEZE.md`.

- market_03_prereg: **true**
- market_03_prereg_frozen: **true**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- canonical_executions_authorized: **0**
- canonical_executions_consumed: **0**
- funding_snapshot_ready: **false**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**

- next required step: `MARKET_03_IMPLEMENTATION_IF_AUTHORIZED` (not ARM, not execution)

## 2026-09-18 — MARKET-03 dedicated funding snapshot

Wrapped the already-acquired Binance USD-M BTCUSDT REST
`/fapi/v1/fundingRate` JSONL into a dedicated immutable dataset without
running the strategy or modifying the frozen prereg.

```text
SOURCE_SHA256         = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
SOURCE_SIZE           = 442988
FUNDING_DATASET_ID    = MARKET_03_BINANCE_UM_BTCUSDT_FUNDINGRATE_REST_V0
FUNDING_SNAPSHOT_ID   = d47b7b78b6e7dbb842c7d9eb122c81063e0b804e179a53dd87723f9a8a8adc68
FUNDING_DATA_SHA256   = e7885cd53407d70b4627d58b9abf2cdf5b26cdc7097a139eac2e454ad75944cb
FUNDING_ROWS          = 5819
FUNDING_TIME_BOUNDS   = 2019-09-10T08:00:00Z .. 2024-12-31T16:00:00Z
```

Identity copy of source bytes. 0 duplicate `fundingTime`. 0 missing 8h
hour-floor events. 2438 millisecond residuals preserved, not rounded.
`STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN`.
`REPRODUCTION_FUNDINGTIME_ASSUMPTION = ACCEPTABLE`. B2-06 is not
authority. Spot snapshot `2ce1f504…` and prereg SHA256 `044bb2a6…` /
`3f35f9a1…` unchanged.

Evidence: `docs/research/MARKET_03_FUNDING_SNAPSHOT.md`.

- funding_snapshot_ready: **true**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- canonical_executions_authorized: **0**
- canonical_executions_consumed: **0**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- unit_verdict: **A. FUNDING_SNAPSHOT_READY**

- next required step: `MARKET_03_IMPLEMENTATION_IF_AUTHORIZED` (not ARM, not execution)

## 2026-09-18 — MARKET-03 implementation (not freeze, not ARM, not execution)

Implemented LEVEL_2 EmaCross baseline and EmaCrossFunding filtered
reproduction semantics from the pinned external source without running
the strategy on bound real MARKET-03 snapshots.

```text
PREREG_MD_SHA256   = 044bb2a6bbd51c49c856b02eb7866b43171664a05d947dce995489389eeb0b57
PREREG_JSON_SHA256 = 3f35f9a1d0575eaff3a1993a4779642259c0891dbdda1d49f22b958eba714f89
LIB_SHA256         = 3e69943368b72d37067a55ce93c0999e4688887a8b89d07ab2008ea0901d3b79
AUTHORITY_SHA256   = d828af5cbbf9810ccf79a16d0582ec450c8db88a958cfc5d7282cc685e43023d
EXECUTE_SHA256     = 4e54b5d6759e5d2d8f53de1401de9bdc8c59da0bd557cab226ca9ab7af382a1b
EXACT_DIFFERENTIAL_TESTS = YES
SEMANTIC_FIXTURE_TESTS   = YES
```

Fail-closed bound execution. Synthetic/fixture/handcrafted tests only.
`STRICT_HISTORICAL_PUBLICATION_LATENCY = UNPROVEN`. B2-06 is not
authority. Protected 2025/2026 OOS untouched.

Evidence: `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION.md`.

- implementation_complete: **true**
- implementation_frozen: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- canonical_executions_authorized: **0**
- canonical_executions_consumed: **0**
- protected_oos_touched: **false**
- b2_06_execution_authorized: **false**
- prereg_changed: **false**
- spot_snapshot_changed: **false**
- funding_snapshot_changed: **false**

- next required step: `MARKET_03_IMPLEMENTATION_FREEZE_IF_AUTHORIZED` (not ARM, not execution)

## 2026-09-18 — MARKET-03 implementation repair (not freeze, not ARM, not execution)

Outcome-blind repair of red-team `B. REPAIR_REQUIRED` on HEAD
`cada1bef…` / tree `95a6f7de…`.

```text
F1_CLOSED = YES  force-exit no longer appends a second same-timestamp capture
F2_CLOSED = YES  EMA/signals restricted to warmup 2019-08-07T20:00:00Z
F3_CLOSED = YES  USDT.total = start + closed profit_abs - open stake (spot)
F5_CLOSED = YES  canonical path requires full identity then refuses unarmed
EXACT_DIFFERENTIAL_TESTS = PARTIAL
LIB_SHA256       = 46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5
AUTHORITY_SHA256 = 97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4
EXECUTE_SHA256   = 90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf
```

Prereg, spot snapshot, and funding snapshot unchanged. Bound real
OHLCV/funding not loaded into strategy logic.

Evidence: `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_REPAIR.md`.

- implementation_complete: **true**
- implementation_frozen: **false**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- canonical_executions_authorized: **0**
- canonical_executions_consumed: **0**
- protected_oos_touched: **false**
- prereg_changed: **false**
- spot_snapshot_changed: **false**
- funding_snapshot_changed: **false**

- next required step: `MARKET_03_IMPLEMENTATION_RE_REVIEW_THEN_FREEZE_IF_AUTHORIZED` (not ARM, not execution)

## 2026-09-18 — MARKET-03 implementation freeze (not ARM, not execution)

Docs-only freeze of the targeted re-review identity
`03411aaa…` / tree `87a1da25…` (`READY_FOR_IMPLEMENTATION_FREEZE`).
Scientific implementation bytes were not modified.

```text
FROZEN_IMPLEMENTATION_HEAD = 03411aaa1a2f938169f07f8f3576f17227a2b14b
FROZEN_IMPLEMENTATION_TREE = 87a1da250a56343c44625e3f5187a6877035d1da
LIB_SHA256       = 46ec2449e967172b61eec32f5ab6caf897ff9db04249395ac55a2368840289a5
AUTHORITY_SHA256 = 97f000c6afc2427db9fe3f90548f77c7e7ab4da0e43ba3283159101565a305e4
EXECUTE_SHA256   = 90fd315d926b2b957391ed31c71bff6a33b0f22257960d0779e27e277cb40bcf
EXACT_DIFFERENTIAL_TESTS = PARTIAL
FULL_PYTEST_AT_REVIEW    = NOT_COMPLETED
```

Evidence: `docs/research/MARKET_03_PUBLIC_STRATEGY_IMPLEMENTATION_FREEZE.md`.

- implementation_frozen: **true**
- market_03_armed: **false**
- market_03_executed: **false**
- market_03_outcome_inspected: **false**
- market_03_parameter_search: **false**
- canonical_executions_authorized: **0**
- canonical_executions_consumed: **0**
- protected_oos_touched: **false**
- prereg_changed: **false**
- spot_snapshot_changed: **false**
- funding_snapshot_changed: **false**

- next required step: `MARKET_03_ARM_IF_AUTHORIZED` (not execution)
