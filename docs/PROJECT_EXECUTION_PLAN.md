# Signalbot Project Execution Plan

> Tactical execution plan for the current project state. This document coordinates **implementation**, **empirical evidence**, and **engineering/debt** work. It does not override product or correctness semantics.

## 0. Document authority

Use this hierarchy when documents overlap:

1. `docs/V2_PRODUCT_CONTRACT.md` — what V2 product behavior means.
2. `docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md` — exact deterministic correctness, acceptance populations, and promotion semantics.
3. `docs/FORECASTING_ROADMAP.md` — canonical high-level product direction and stage sequence.
4. `docs/PROJECT_EXECUTION_PLAN.md` — current tactical ordering, parallel tracks, and gates.
5. `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md` — empirical falsification/evidence methodology.
6. `docs/PROJECT_RISK_AND_DEBT_REGISTER.md` — exhaustive known risk/debt inventory and closure requirements.
7. historical Stage 1/2 specs, clarifications, audits, and acceptance records — historical records unless explicitly carried forward by a higher-authority document.

A future documentation-hygiene PR must link this hierarchy from README/roadmap so a new reader is not forced to infer it.

---

## 1. Project posture

The project now has three different kinds of progress. They must be tracked separately:

- **Track A — Core implementation/correctness:** can the system compute, persist, replay, and operate exactly as specified?
- **Track B — Evidence/research validity:** do the hypotheses contain incremental predictive/economic information beyond simple controls?
- **Track C — Engineering/product debt:** documentation, config hygiene, CI/supply-chain, reproducibility, maintainability, and public-repo presentation.

A green Track A does not imply a green Track B.

---

## 2. Track A — Core V2 implementation and correctness

### A0. Pre-Stage-6 hardening — current gate

Complete and merge the remaining V2-H2/H3 work before Stage 6 begins:

- **H2b — DRAIN-BEFORE-ACTIVATE** version-switch state machine. MERGED (PR #58, merge commit `19f3b1d5075df642a3f1e8decb0f53ea0b3d8b48`; see C-001 / `PROJECT_RISK_AND_DEBT_REGISTER.md`).
- **H2c — historical/as-of instrument metadata** including tick-size replay semantics. MERGED (PR #59, merge commit `1eef3dc7d19ccb7dd9c9410f8c3b7da2b84f3572`; see D-007, CLOSED).
- **H2e — Stage-2 correction publication completeness + deterministic replay/coherent historical view.** Implemented on `hardening/v2-h2e-correction-publication-coherent-replay`, PR open, NOT YET MERGED (see D-008, IN_PROGRESS).
- **H3 — persistence/idempotency hardening**: deterministic semantic IDs, same-T singular event semantics, atomic event batches, stable LIVE run identity. Not started.

Then perform the existing **H2 + H3 convergence gate**.

No Stage-6 lifecycle implementation begins before this gate passes.

### A1. Stage 6 — Episode State Machine

Proceed with the planned reviewable units after convergence:

1. identity + persisted-history read foundation;
2. candidate classification/arbitration/EARLY_SIGNAL creation/cooldown eligibility;
3. confirmation/false-break/candidate-expiry transitions;
4. CONFIRMED/WEAKENING/invalidation/horizon terminal resolution + shared excursion primitive;
5. same-boundary orchestration + reversal cardinality + Stage-6 completion.

Do not expand setup families or add new signal intelligence during this stage.

### A2. Stage 7 — Entry Feasibility

Implement the frozen feasibility/lateness semantics. Preserve late/non-actionable decisions for research; do not optimize thresholds from early results.

### A3. Stage 8 — V2 Outcome Evaluator

Implement the canonical episode populations, MFE/MAE/R-normalized metrics, costs/delay semantics, path-completeness handling, and reproducible reporting foundation.

### A4. Mandatory empirical GO / SIMPLIFY / KILL gate

**Stage 8 completion no longer means “continue automatically to Telegram”.**

Before user-facing Stage 9 promotion work, execute the required program in `docs/V2_EMPIRICAL_RED_TEAM_PLAN.md` and record a formal decision:

- `GO` — sufficient evidence to continue;
- `SIMPLIFY` — remove/demote unsupported complexity/families and version appropriately;
- `KILL/RETHINK` — V2-v0 did not demonstrate the core hypothesis; preserve the platform and reformulate the model.

Stage 9 may still have non-user-facing scaffolding work if needed, but no claim/promotion bypasses this gate.

### A5. Stage 9 / Stage 10

- Stage 9: Telegram V2 only for semantics that survived the evidence gate.
- Stage 10: Parallel Shadow Deployment remains mandatory before user-facing eligibility under the correctness contract.
- Live-shadow evidence remains distinct from replay evidence.

---

## 3. Track B — Evidence and research validity

This track begins **now**, not after Stage 8.

### B0. Formal V1 diagnostic report — start now

Use persisted V1 predictions/outcomes to establish what V1 actually gets wrong:

- direction vs lateness;
- MFE/MAE and remaining movement after notification delay;
- confidence ordering;
- signal/reason/component diagnostics where reproducible;
- clustering of repeated 5m signals into latent events;
- missing-data behavior;
- comparison with simple momentum/breakout and time-matched random controls.

Outcome: a version-pinned diagnostic report stating whether V1's main failure is direction, lateness, unnecessary complexity, one harmful component, or insufficient evidence.

This work does **not** authorize tuning V1.

### B1. Research ledger + preregistration discipline — start now

Create/maintain `docs/RESEARCH_LEDGER.md`.

Before confirmatory research, record:

- hypothesis;
- expected effect;
- primary metric;
- baselines/controls;
- dataset window;
- whether OOS has been viewed;
- result and keep/reject decision.

A consumed holdout cannot be reused as untouched evidence for a modified model.

### B2. Data-semantics/live-equivalence audit — start now

Document and later implement evidence-tier classification for historical samples:

- live-equivalent;
- partial historical;
- non-comparable feed semantics;
- not evaluable.

Specific required audits:

- venue-by-feature historical availability;
- liquidation feed semantics/completeness per venue and period;
- OI source granularity/ffill behavior;
- provider/API semantic changes over time;
- missingness correlation with volatility/outages.

### B3. Provider-granularity correctness audit — start now

Prove that coarse historical sources cannot create fake fine-grained information after upsampling. OI 5m -> 1m forward-fill is the first explicit target.

If downstream features infer minute-level timing from a 5m provider observation, treat it as a blocker for historical evidence using that feature.

### B4. Baselines and negative controls — define before Stage-5 event study

Pre-register:

- V1 where comparable;
- simple 4h trend + 5m breakout;
- simple 15m price-structure breakout/pullback;
- time-matched random controls;
- null/drift control;
- time-shift, direction-inversion, feature-permutation, and venue-permutation controls where valid.

### B5. Stage-5 detector event study — after H2e/coherent replay

As soon as H2e provides trustworthy coherent historical decision views, evaluate detector qualification points without pretending full Stage-6 semantics exist.

For each family/direction compare future return/MFE/MAE/time-to-MFE with matched controls.

Purpose: cheaply test whether detectors separate interesting future behavior at all.

This is an `E1_DETECTOR_SEPARATION` study, **not** a final V2 backtest.

### B6. Full episode evaluation — after Stage 8

Execute:

- chronological OOS/walk-forward;
- parameter-neighborhood sensitivity;
- ablations;
- cross-exchange contribution;
- setup-family overlap/distinctness;
- confidence-ordering curves;
- regime/concentration analysis;
- delay/cost stress;
- effective-sample/uncertainty analysis;
- negative controls;
- multiple-testing/research-ledger review.

Then hold the A4 GO/SIMPLIFY/KILL gate.

### B7. Live-shadow forward holdout — Stage 10

Treat live shadow as a new forward evidence source. Do not relabel replay as live evidence. Monitor:

- feature availability vs historical assumptions;
- operational latency and notification/action delay distribution;
- fail-closed/data-gap rates;
- per-family acceptance metrics;
- replay/live divergence.

---

## 4. Track C — Engineering, documentation, reproducibility, and product debt

These items are real obligations but do not all block the current H2/H3 path. They are tracked exhaustively in `docs/PROJECT_RISK_AND_DEBT_REGISTER.md`.

### C0. Research-validity technical blockers

Highest-priority non-stage work:

- provider-granularity/ffill audit;
- live-equivalent evidence classification design;
- historical feed-semantics versioning/audit trail;
- denominator/missingness transparency;
- data-revision/environment identity for reproducible reports.

### C1. Documentation topology / README

Required cleanup:

- README must reflect the actual current V2 implementation state;
- README must point to the document-authority hierarchy;
- roadmap historical/stale status wording must be reconciled with current Stage 3–5 implementation and H2 split;
- public project description/topics/license decision should be made separately.

### C2. Config hygiene

Audit and either remove, rename, or document/consume legacy-looking keys such as:

- `coverage_2of4_blocks_new_triggered`;
- `coverage_1of4_pauses_signal_engine`;
- legacy `calibration.min_sample_*` values that must not be mistaken for V2 proof thresholds.

Unused config is treated as debt because it creates an illusion of active safety controls.

### C3. CI / supply-chain / static quality

Plan dedicated hardening for:

- explicit minimal GitHub Actions permissions;
- pinning Actions to immutable commit SHAs;
- dependency review/vulnerability gating;
- secret scanning/SAST where appropriate;
- lint/static typing policy;
- coverage reporting/threshold decision;
- property-based tests for high-value invariants where useful.

These are maintenance/security improvements, not substitutes for empirical validation.

### C4. Reproducible dependency/runtime environment

Direct dependency pins are not a full reproducible environment. Decide and implement an appropriate lock/hash strategy for transitive dependencies and record execution-environment identity in research artifacts.

A model-code identity should not imply identical execution if dependency resolution can silently differ.

### C5. Maintainability / complexity debt

The size of contracts and detector modules is now itself a risk. Plan periodic architecture review for:

- excessively large modules/functions;
- duplicated validation logic;
- test-suite runtime/maintenance burden;
- contract navigation/indexing;
- API boundaries that are becoming defensive layers around other defensive layers.

Do not refactor merely for aesthetics during correctness-critical work; refactor when behavior is protected by tests/contracts and the change reduces real maintenance risk.

---

## 5. Gate matrix

| Gate | Mandatory before | Required work |
|---|---|---|
| `G0 H2/H3 CONVERGENCE` | Stage 6 | H2b + H2c + H2e + H3 accepted/merged |
| `G1 REPLAY TRUST` | relying on detector historical study | coherent replay + data/provenance correctness + provider-granularity audit for used features |
| `G2 DETECTOR SEPARATION` | interpreting detector logic as promising | Stage-5 event study + simple/matched controls; diagnostic only |
| `G3 EPISODE EVALUATION READY` | full V2 empirical judgment | Stage 6 + Stage 7 + Stage 8 |
| `G4 EMPIRICAL GO/SIMPLIFY/KILL` | user-facing V2 product progression | red-team/OOS/baseline/ablation/delay/cost evidence review |
| `G5 LIVE SHADOW` | user-facing eligibility | correctness-contract live-shadow requirements per family |
| `G6 PRODUCT MATURITY DEBT` | calling repository/product mature | README/docs/config/reproducibility/CI/debt closure at agreed thresholds |

---

## 6. Freeze on hypothesis-surface expansion

Until G4 has meaningful evidence, no new signal intelligence is the default:

- no extra setup families;
- no order book/spot/CoinGlass/macro merely to rescue metrics;
- no ML/adaptive thresholds/auto-tuning;
- no arbitrary new indicators/scoring dimensions;
- no multi-symbol expansion used as a way to manufacture sample size for the same unvalidated hypothesis.

New research ideas may be recorded in the ledger/backlog, but they do not enter V2-v0 silently.

---

## 7. Definition of progress

From now on report progress in at least two separate dimensions:

- **Implementation/correctness readiness**;
- **Empirical evidence readiness**.

Optional third dimension:

- **engineering/product maturity/debt**.

Do not summarize all three into one percentage that can make thousands of new tests look like evidence of market predictability.