# Signalbot — Current Project Status

**Status date:** 2026-09-17
**Operating mode:** `RESEARCH_FIRST / PRODUCT_DEVELOPMENT_FROZEN`
**Active research phase:** `MARKET`

This file is the canonical answer to: **what is Signalbot doing now?**

## 1. Current decision

Further product/forecasting architecture development is frozen until the project demonstrates at least one independently validated market edge or produces sufficiently strong evidence that the investigated hypothesis classes do not contain one.

The goal is **not** to force the discovery of an edge. `NO EDGE`, `INSUFFICIENT DATA`, and `REJECTED` are valid outcomes.

Signalbot is operating as a market-research platform rather than as a product-development program.

The synthetic Microscope calibration is closed. Canonical V3 is immutable historical evidence, not a live research program. The active next phase is **MARKET**: take real crypto-market hypotheses through the existing research process. Do not repair, rerun, or reinterpret V3. Do not create V4. V3 `DETECTED`/`PASS` is not by itself sufficient evidence of a robust market edge.

## 2. Why the direction changed

Three facts drive the change:

1. engineering correctness and architecture progressed faster than empirical evidence;
2. the currently available rich historical overlap is roughly one month, which is useful for falsification but far too short to support a durable-edge claim across regimes;
3. development evidence from `E1-RUN-001` did not justify automatically continuing into additional lifecycle/product complexity.

Building Stage 6+, richer UI/notifications, ML, or more features before proving the underlying predictive structure would increase sunk cost without increasing confidence that a tradable edge exists.

## 3. What is frozen

Until the research restart gate in §8 is satisfied, do **not** develop:

- Stage 6 lifecycle / episode machinery beyond correctness fixes required to preserve existing evidence;
- Stage 7+ product progression;
- new production signal families;
- new production scoring/confidence systems;
- ML/adaptive thresholds/automatic tuning;
- Telegram/UI/product features unrelated to research;
- production enable/deploy of V2;
- speculative platform abstractions;
- business-model/monetization expansion beyond recording hypotheses.

Existing V1/V2 code is retained as research material and infrastructure. Freeze does not mean delete.

## 4. What remains active

Active work is limited to work that increases the quality of empirical inference:

- preserve the frozen `E1-RUN-001` record and its unopened holdout; the current TP/CB/FB formulations are retired at development and the holdout is not to be spent on rescue;
- expand historical data coverage;
- build reproducible research datasets/manifests;
- formulate and test market hypotheses;
- build simple baselines and negative controls;
- perform threshold/parameter research on development data only;
- run chronological validation/OOS/walk-forward studies;
- measure regime dependence, concentration, delay/cost sensitivity and effective sample size;
- validate incremental value of richer features only after a simpler core hypothesis shows evidence.

## 5. Current empirical state

### V1

Frozen research baseline. Autopsy found that it behaved primarily as a reactive 5m momentum/continuation state classifier, with high signal churn and notification latency that consumed much of any very-short continuation. Confidence did not demonstrate useful future-outcome ordering.

V1 is not an active product-development target.

### CORE_BTC_BINANCE_V0

Accepted for discovery on 2026-08-26. Snapshot `717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415`. Frozen interval `[2020-01-01T00:00:00Z, 2026-08-26T00:00:00Z)`. `3,497,760` complete 1m rows; 0 gaps; 0 duplicates; 104/104 checksums. Manifest: `docs/manifests/CORE_BTC_BINANCE_V0.yaml`. Evidence: `docs/research_data/CORE_BTC_BINANCE_V0/`. This is not confirmatory authorization and not an edge claim.

First mechanism experiment `H01_COMPRESSION_EXPANSION` finished development-only on this snapshot. Verdict: **`H01_KILL` / `REJECTED`**. Unusually low recent realized vol predicted **lower**, not higher, subsequent vol. That reverse persistence pattern is not validated evidence.

Second mechanism experiment `H02_FAILED_BREAKOUT_MEAN_REVERSION` finished development-only. Verdict: **`H02_KILL`**. Closing back inside a local range did not beat successful-breakout or show a strength-monotonic reversion surface. 2025 validation and 2026 OOS were not opened. See `docs/research/H02_DEV_SUMMARY.md`.

### R2 Batch01

Batch01 is closed: **0 of 5 primary mechanism families promoted**.

- H01: `REJECTED / H01_KILL`
- H02: `REJECTED / H02_KILL`
- H03: `H03_REJECTED_SPECIFIC_CLAIM`
- H04: `H04_REJECTED_SPECIFIC_CLAIM`
- H05: `H05_REJECTED_SPECIFIC_CLAIM / CLOSED_DEVELOPMENT_REJECTED`

2025 validation and 2026 OOS remain untouched for H01-H05. Several families
showed raw conditional structure, but none earned promotion under the required
robustness/incremental-information controls. See
`docs/research/BATCH01_SYNTHESIS.md`.

### R2 Batch02

Batch02 inventory remains frozen/immutable and is **not** the active
research program after the V3 Microscope closeout. Post-outcome status
lives in `docs/research/BATCH02_STATUS_LEDGER.md`. B2-06 remains
blocked; `MARKET-01` does not have to be B2-06.

- B2-01 `VOLATILITY_TRANSITION`: `CLOSED_NO_PROMOTION`
- B2-02 `BOUNDARY_INTERACTION_PATH`: `CLOSED_NO_PROMOTION`
- B2-03 `IMPULSE_MORPHOLOGY`: `CLOSED_NO_PROMOTION`
- B2-04 `MODERATE_PULLBACK_STRUCTURE`: `CLOSED_NO_PROMOTION`
- B2-05 `FLOW_ABSORPTION`: development consumed; durable evidence
  `B2_05_RECOVERY_ARCHIVED_OPERATOR_ADJUDICATED` at archive
  `e31e5666fe845116197b6f2531289bf17d848027` (historical bytes
  operator-adjudicated, not proven)
- B2-06 `LEVERAGE_CROWDING`: `BLOCKED_MISSING_OBSERVABLE`. An outcome-blind
  first-party OI/funding snapshot is Git-bound as
  `5a9d036b23721d75b519b8478b81e333791227376d25cbeea5f0666c90730a33`
  (`docs/research/B2_06_LEVERAGE_CROWDING_DATA_EXPANSION.md`); funding
  publication latency is unproven; B2-06 outcomes remain unauthorized.
  The mandatory pre-B2-06 methodology unit
  `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V1` was executed from exact ARM
  commit `9ab32fc14c50df0c6f1c7ddfe2a8990d2d49c339` / tree
  `8aca4445f4638f678810d64a17de2a253a22763d` (`workers=4`). All 3200
  planned worlds completed structurally. Mint refused:
  `INCOMPLETE_EXECUTION_NO_METHODOLOGY_CLAIM` (113 worlds `valid=false`
  under the V1 any-candidate rank rule). RESULT and WORLD_RECORDS were
  not minted. V1 ARM authority was not consumed. The V1 attempt and the
  3087-world subset are permanently non-claimable. Do not resume V1 mint.
  Successor methodology unit
  `HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY` now
  has a reviewed fixture-only implementation frozen at HEAD `a310837`
  (`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_RANK_DEGENERACY_POLICY_IMPLEMENTATION_FREEZE.json`)
  plus a pre-outcome production lifecycle and the independently reviewed
  33/33 inherited-ladder implementation frozen at HEAD `614295d` / tree
  `e754b12`
  (`docs/research/HARNESS_SYNTHETIC_EDGE_CALIBRATION_V2_33_33_IMPLEMENTATION_FREEZE.json`).
  Governing methodology is Amendment_003 + Amendment_004; Amendment_002 is
  rejected historical authority and cannot govern executable science. The
  visibility statistic gap remains unresolved and fail-closed. This freeze
  does not create an ARM, authorize execution, or run the 3200-world grid.
  No V2 ARM artifact exists anywhere in the repository; V2 production
  remains unarmed and does not authorize B2-06. Next required step for
  that unit: `INDEPENDENT_V2_33_33_IMPLEMENTATION_FREEZE_REVIEW`.
  Historical ARM `120ac45` and unused driver ARM `0abc5fe` do
  not authorize V1 or V2 runtime. This does not authorize B2-06 science.

V3 confirmatory calibration is **closed**. Canonical RESULT authority is
commit `99b409cae279513eaf489194e7fa206082c60aef`, WORLD_RECORDS SHA256
`5d09631db5180f562076b2191fe002aa21318a3925d3cd1c4014d83e4b41eb4f`,
RESULT SHA256
`f72eedcdcb511e2c7f22369cbdef164688317dfc99f9ab3e533df14cb2a27866`.
Mechanical cell verdicts: EASY `PASS` (400/400), MODERATE `PASS`
(313/400), NULL `INDETERMINATE` (21/400), NONSTATIONARY_TRAP `FAIL`
(188/400). `methodology_claimable = false`. `incomplete_execution = false`.

Narrow closeout interpretation (do not reinterpret the mechanical RESULT):

1. V3 repaired the measured V2 confirmatory sensitivity problem (`EASY`
   `PASS`, `MODERATE` `PASS`).
2. V3 did not establish a generally claimable methodology (`NULL`
   `INDETERMINATE`, `NONSTATIONARY_TRAP` `FAIL`,
   `methodology_claimable = false`).
3. Known limitation: the current V3 confirmatory decision is
   insufficiently protected against the frozen nonstationary trap. Do
   **not** translate 188/400 into a general real-market false-positive
   rate; it applies only to the frozen synthetic trap DGP.
4. V3 `DETECTED`/`PASS` is research evidence but must not by itself be
   treated as sufficient evidence of a robust market edge. Any promising
   MARKET result must retain explicit regime / nonstationarity scrutiny
   before stronger promotion claims.
5. This limitation is **not** authorization for immediate V4.

Microscope closeout flags:

- `V3_CALIBRATION_CLOSED = YES`
- `V3_RERUN_AUTHORIZED = NO`
- `V3_METHODOLOGY_CLAIMABLE = NO`
- `CONFIRMATORY_SENSITIVITY = DEMONSTRATED_ON_FROZEN_SYNTHETIC_EASY_MODERATE`
- `NONSTATIONARY_TRAP_PROTECTION = INADEQUATE_ON_FROZEN_TRAP_DGP`
- `DEFAULT_V4 = NO`

The Microscope remains available as scientific instrumentation. It is
not deleted. It is no longer the active research program. B2-06 remains
`BLOCKED_MISSING_OBSERVABLE`; MARKET-01 does not unblock it.

Family F1 is `CLOSED_NO_PROMOTION`. 2025 validation and 2026 OOS remain
untouched. No Batch02 formulation has a promoted candidate, so there is no
Batch02 validation path to open.

### V2 / E1-RUN-001

The frozen Stage-5 detector families were:

- `TREND_PULLBACK` (TP)
- `COMPRESSION_BREAKOUT` (CB)
- `CONFIRMED_BREAKOUT` (FB)

Their development evidence was consumed and did not justify promotion. The
chronological E1 holdout remains **unopened**.

Following Batch01 synthesis, the three E1 detector formulations are now
`RETIRED_CURRENT_FORMULATION`. This does not claim that Batch01 reran the
exact E1 code or disproved every future trend/compression/breakout mechanism.
It records a project decision that the existing formulations have not earned
the right to consume their frozen holdout.

The frozen evaluator, preregistration and holdout artifacts remain historical
evidence and must not be rewritten. Any materially new child formulation must
receive a new hypothesis identity and clean evaluation path.

## 6. Evidence posture

No current Signalbot configuration is claimed to possess a durable trading edge.

One month of rich overlap may:

- expose obvious failures;
- reveal candidate mechanisms;
- support engineering/correctness checks;

but it may **not** by itself establish stability across market regimes.

The next research program therefore separates:

- **multi-year CORE evidence** for simple market mechanisms; and
- **shorter RICH overlap evidence** for incremental value of OI/funding/liquidations/cross-venue features.

See `docs/HISTORICAL_DATA_STRATEGY.md`.

## 7. Active objective

The active research phase is **MARKET**. `MARKET-01`
(`OI_EXPANSION_WEAK_CONTINUATION`) is **`RESULT`** and closed under its
frozen design. Mechanical classification: **`NO_EVIDENCE`**. Canonical
RESULT SHA256
`5310946b44dd3ebc609d05a13f92f6cb414e3a0727141d0ee324bce0aa626c5e`.
`CANONICAL_EXECUTIONS_CONSUMED = 1`. No rerun is authorized. Do not
change thresholds or windows. The confirmatory test remains a new
stratified two-group OLS identity, not V3, and remains uncalibrated
(`MARKET_01_TEST_CALIBRATED = NO`). This is not validated alpha, not a
production signal, and not OOS validation.
RESULT authority:
`docs/research/MARKET_01_OI_EXPANSION_WEAK_CONTINUATION_RESULT.json`.

Post-calibration operating priority:

- approximately 70–80% actual market research;
- approximately 20–30% infrastructure only when concrete research
  blockers require it.

Primary progress metric: MARKET hypotheses honestly closed per week.

Initial evidence milestone: 25–50 real market hypotheses through the
stable research process. That milestone is observational/research-oriented;
it is not a promise that 25–50 studies establish alpha.

B2-06 remains `BLOCKED_MISSING_OBSERVABLE` / funding publication-latency
unproven. `MARKET-01` does not have to be B2-06 and does not silently
unblock it. Do not rerun B2-05 or rescue closed B2-01 through B2-04
results. Do not repair, rerun, or reinterpret V3. Do not create V4.

The research objective remains:

> Discover and independently validate one or two market mechanisms with stable incremental information — or falsify the investigated mechanisms without rescuing them through post-hoc complexity.

A valid edge must survive more than a favorable backtest window. Exact requirements are defined in `docs/EDGE_RESEARCH_PROTOCOL.md`. Any promising MARKET result must retain explicit regime / nonstationarity scrutiny before stronger promotion claims.

## 8. Restart gate for product architecture

Product/forecasting architecture development may resume only after at least one candidate edge has:

1. a clearly defined mechanism and deterministic rule;
2. multi-year or otherwise regime-diverse evidence appropriate to the claim;
3. chronological validation separate from discovery;
4. an untouched OOS or equivalent forward test;
5. separation from simple/matched controls;
6. parameter/threshold robustness rather than one magic point;
7. acceptable delay/cost sensitivity for the intended use;
8. transparent sample concentration and missingness.

Only then should lifecycle, risk orchestration, product UX, explanations and richer architecture be designed around the observed behavior of the validated edge.

## 9. Canonical documents

Read in this order:

1. `docs/PROJECT_STATUS.md` — current posture and freeze;
2. `docs/RESEARCH_ROADMAP.md` — active execution order;
3. `docs/EDGE_RESEARCH_PROTOCOL.md` — rules for discovery/validation;
4. `docs/HISTORICAL_DATA_STRATEGY.md` — data expansion strategy;
5. `docs/ACTIVE_RESEARCH_RISKS.md` — current inference risks;
6. `docs/RESEARCH_LEDGER.md` — consumed hypotheses/windows and experiment history;
7. `docs/PROJECT_HISTORY.md` — why the project evolved into the current posture;
8. `docs/DOCUMENTATION_INDEX.md` — current vs historical documents.

When a legacy V2/Stage document conflicts with this file about **current project direction**, this file wins. Historical contracts still govern interpretation/reproduction of experiments that were frozen under them.