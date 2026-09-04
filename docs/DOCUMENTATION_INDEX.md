# Signalbot Documentation Index

**Status:** ACTIVE / CANONICAL INDEX

This index exists to stop historical implementation documents from being mistaken for the current project plan **without erasing the history that explains how Signalbot evolved**.

The repository intentionally has two visible layers:

1. **current truth** — what the project is doing now;
2. **historical trail** — what it previously believed/built, what evidence changed that belief, and why the direction changed.

For the narrative evolution, read `PROJECT_HISTORY.md`. For complete original documents from earlier phases, use `history/README.md`.

---

## 1. Current sources of truth

Read these first:

| Document | Status | Purpose |
|---|---|---|
| `PROJECT_STATUS.md` | **ACTIVE / CANONICAL** | Current project posture, freeze, empirical state and restart gate |
| `RESEARCH_ROADMAP.md` | **ACTIVE / CANONICAL** | Active execution order |
| `EDGE_RESEARCH_PROTOCOL.md` | **ACTIVE / CANONICAL** | Discovery/validation rules and anti-overfit discipline |
| `HISTORICAL_DATA_STRATEGY.md` | **ACTIVE / CANONICAL** | Multi-year CORE vs shorter RICH evidence strategy |
| `DATA_CAPABILITY_MATRIX.md` | **ACTIVE / RESEARCH DATA DESIGN** | Verified source/venue/date/granularity map and acquisition order for the 2020/2021–2026 research program |
| `CORE_BTC_BINANCE_V0_PROBE_RUNBOOK.md` | **ACTIVE / RESEARCH INFRASTRUCTURE** | How to run the small deterministic `CORE_BTC_BINANCE_V0` source-capability probe; why `SOURCE_PROBE_PASSED` != `DATASET_ACCEPTED` |
| `CORE_BTC_BINANCE_V0_MATERIALIZATION_RUNBOOK.md` | **ACTIVE / RESEARCH INFRASTRUCTURE** | How the CORE BTC Binance materializer pipeline is staged; CLI finalize is not dataset acceptance |
| `manifests/CORE_BTC_BINANCE_V0.yaml` | **ACCEPTED_FOR_DISCOVERY** | Canonical CORE BTC Binance V0 dataset manifest |
| `research_data/CORE_BTC_BINANCE_V0/` | **FROZEN_EVIDENCE** | Accepted snapshot `717d37a4` identity, source inventory, and quality report |
| `research/H01_COMPRESSION_EXPANSION_PREREG.md` | **FROZEN_EVIDENCE** | H01 preregistration (before development outcomes) |
| `research/H01_DEV_SUMMARY.md` | **FROZEN_EVIDENCE** | H01 development-only result; verdict `H01_KILL` |
| `research/H02_FAILED_BREAKOUT_MEAN_REVERSION_PREREG.md` | **FROZEN_EVIDENCE** | H02 preregistration (before development outcomes) |
| `research/H02_DEV_SUMMARY.md` | **FROZEN_EVIDENCE** | H02 development-only result; verdict `H02_KILL` |
| `research/BATCH02_STATUS_LEDGER.md` | **ACTIVE RECORD** | Post-outcome Batch02 formulation/family status; does not mutate the frozen inventory |
| `research/B2_01_VOLATILITY_TRANSITION_RESULT.md` | **FROZEN_EVIDENCE** | B2-01 development-only result; verdict `B2_01_CLOSED_NO_PROMOTION` |
| `research/B2_02_BOUNDARY_INTERACTION_PATH_RESULT.md` | **FROZEN_EVIDENCE** | B2-02 development-only result; verdict `B2_02_CLOSED_NO_PROMOTION` |
| `research/B2_03_IMPULSE_MORPHOLOGY_PREREG.md` | **FROZEN_EVIDENCE** | B2-03 preregistration (before development outcomes) |
| `research/B2_03_IMPULSE_MORPHOLOGY_RESULT.md` | **FROZEN_EVIDENCE** | B2-03 development-only result; verdict `B2_03_CLOSED_NO_PROMOTION` |
| `research/B2_04_MODERATE_PULLBACK_STRUCTURE_PREREG.md` | **FROZEN_EVIDENCE** | B2-04 preregistration (before implementation or development outcomes) |
| `PROJECT_STRATEGY_AND_ARCHITECTURE_PRINCIPLES.md` | **ACTIVE / CANONICAL** | Evidence-first architecture philosophy and current non-goals |
| `ACTIVE_RESEARCH_RISKS.md` | **ACTIVE RECORD** | Risks that can invalidate the current research-first program |
| `RESEARCH_LEDGER.md` | **ACTIVE RECORD** | Experiment/hypothesis history and consumed windows |
| `CODEBASE_STATUS.md` | **ACTIVE / CANONICAL MAP** | Which code surfaces are active, frozen, deferred or operational |
| `PROJECT_HISTORY.md` | **ACTIVE HISTORY** | Narrative evolution of Signalbot's ideas, architecture and philosophy |
| `history/README.md` | **ACTIVE HISTORY INDEX** | Direct links to immutable full historical roadmaps/contracts/specifications |
| `DATA_DURABILITY_RUNBOOK.md` | **OPERATIONS** | Data durability/recovery reference |
| `research/BATCH02_DURABLE_EVIDENCE_RETENTION_V1.md` | **IMPLEMENTED_PENDING_INDEPENDENT_REVIEW** | Outcome-blind B2-03+ durable evidence reservation/archival contract; no market outcomes |

If a historical document conflicts with the active canonical set about **what the project should do next**, the current documents win.

---

## 2. Project history — preserved intentionally

`PROJECT_HISTORY.md` is the human-readable map of the project's evolution:

- original market-information/decision-support idea;
- Stage 1 data foundation;
- V1 shadow forecasting;
- V1 empirical autopsy;
- V2 multi-timeframe architecture thesis;
- shift from correctness to falsification;
- E1 detector-separation experiment;
- discovery that one month of rich overlap is inadequate for durable-edge claims;
- 2026-08-26 research-first pivot.

`history/README.md` complements that narrative with direct links to the full immutable source documents exactly as they existed before the pivot and records retired branch/PR history needed for safe branch cleanup.

The point of retaining history is not nostalgia. It prevents the project from repeatedly rediscovering rejected ideas and makes the reasoning behind architectural changes auditable.

Failed/null hypotheses remain part of the history.

---

## 3. Frozen experiment records — do not rewrite to match current philosophy

These are evidence/provenance artifacts for `E1-RUN-001` and must remain historically faithful:

- `E1_DETECTOR_SEPARATION_PREREG.md`
- `E1_DATA_INVENTORY_2026-08-25.md`
- `E1_VPS_RUNBOOK.md`
- `e1/E1_RUN_001_ABLATION_OUTCOME_REPORTING_FREEZE.md`
- `e1/E1_RUN_001_ABLATION_PROTOCOL_FREEZE.md`
- `e1/E1_RUN_001_CONTROL_PROTOCOL_FREEZE.md`
- `e1/E1_RUN_001_COVERAGE_PREFLIGHT_CLARIFICATION.md`
- `e1/E1_RUN_001_DEVELOPMENT_ABLATIONS.md`
- `e1/E1_RUN_001_DEVELOPMENT_CONTROLS.md`
- `e1/E1_RUN_001_DEVELOPMENT_OUTCOMES.md`
- `e1/E1_RUN_001_FINAL_HOLDOUT_EVALUATOR_FREEZE.md`
- `e1/E1_RUN_001_HOLDOUT_COVERAGE_READINESS_CLARIFICATION.md`
- `e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md`

Do not rewrite old preregistration text to match later knowledge. Add a new dated clarification/ledger entry instead.

---

## 4. Historical implementation contracts / audits

The following describe earlier Stage1/Stage2/V2 implementation states or audits. They remain useful for code archaeology/reproducibility but are **not active product-development authorization**:

- `STAGE1_ACCEPTANCE.md`
- `STAGE2_SPEC.md`
- `STAGE2_CLARIFICATIONS.md`
- `STAGE2_DATA_AUDIT.md`
- `STAGE2_IMPLEMENTATION_PLAN.md`
- `V2_CONSENSUS_ROBUSTNESS_HISTORICAL_AUDIT.md`
- `V2_PERCENTILE_MATURITY_AUDIT.md`
- `history/V2_MATHEMATICAL_HYPOTHESIS_REGISTER.md` — exact historical governance content archived from the standalone `research/v2-mathematical-hypothesis-register` branch before branch cleanup.

The old `PROJECT_RISK_AND_DEBT_REGISTER.md` is also retained as a **historical V2-era debt register**. Its Stage-6/7/8 implementation items are not automatically current work. Use `ACTIVE_RESEARCH_RISKS.md` for the current program.

---

## 5. Superseded roadmap/product documents

These paths are intentionally retained as compatibility/history pointers so old links do not silently lead readers into an obsolete active plan:

- `FORECASTING_ROADMAP.md`
- `PROJECT_EXECUTION_PLAN.md`
- `V2_PRODUCT_CONTRACT.md`
- `V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md`
- `V2_EMPIRICAL_RED_TEAM_PLAN.md`
- `PRODUCT_SPEC_V0.md`

Their former full contents are preserved in git history at the pre-pivot repository state, indexed for normal browsing in `history/README.md`, and their role in project evolution is summarized in `PROJECT_HISTORY.md`.

They must not contain a second active roadmap.

---

## 6. Deferred product hypotheses

`PRODUCT_HYPOTHESES.md` is a parking lot / historical product-thinking record only. Product/business work is frozen while the project is in research-first mode.

Do not delete rejected/deferred ideas merely to make the repository look cleaner; label them honestly and keep them outside current execution authority.

---

## 7. Operational/deployment references

These documents may still be useful operationally, but following them is not authorization to deploy or restart product development:

- `VPS_DEPLOY.md`
- `SHADOW_TIMER_DEPLOY.md`
- `TELEGRAM_NOTIFIER_DEPLOY.md`
- `E1_VPS_RUNBOOK.md`

Before using an operational runbook, compare it with current code/config and runtime state. Some commands/names reflect earlier deployment stages.

---

## 8. Code status

Use `CODEBASE_STATUS.md` before assuming that an implemented module is active roadmap scope.

Key examples:

- `analytics/forecasting/` — `FROZEN_BASELINE` (V1);
- `analytics/forecasting_v2/` — `FROZEN_RESEARCH_ENGINE` (V2-v0);
- E1-specific holdout scripts — `FROZEN_EXPERIMENT_TOOLING` once frozen;
- `storage/`, `data_ingestion/`, `backfill/` — active research infrastructure where justified by evidence/data needs;
- notification/product surfaces — retained but deferred.

Code may remain because it is useful history or a frozen comparator. Presence does not imply active development.

---

## 9. Repository instruction file

`../AGENTS.md` points coding/review agents to current sources of truth plus frozen research artifacts relevant to the task. It must not restore old V2 roadmap authority.

---

## 10. Status vocabulary for future docs

Every new planning/research document should declare one status near the top:

- `ACTIVE / CANONICAL` — current decision authority;
- `ACTIVE RECORD` — mutable ledger/register, not roadmap authority;
- `ACTIVE HISTORY` — maintained narrative/history index;
- `FROZEN_EVIDENCE` — immutable preregistration/result artifact;
- `FROZEN_ENGINE_REFERENCE` — semantics of a specific historical engine/version;
- `HISTORICAL` — preserved project history, no current execution authority;
- `DEFERRED` — intentionally parked, not active scope;
- `SUPERSEDED` — old active authority replaced by a newer source;
- `OPERATIONS` — runtime/runbook reference, not research/product authority.

Do not create an unlabelled roadmap/contract that can later be mistaken for current truth.

---

## 11. Cleanup policy

The target is **one current truth + a readable historical trail**.

Delete a file only when it is:

- an exact/near duplicate with no independent historical value;
- generated/transient material accidentally committed;
- an obsolete instruction whose presence creates operational risk and whose historical role is already preserved;
- dead scaffold/placeholder with no evidence, provenance or explanatory value.

Do **not** delete merely because:

- a hypothesis failed;
- a roadmap was superseded;
- the project changed philosophy;
- an implementation was abandoned.

When historically meaningful content is shortened or removed from the active tree, preserve at least one of:

- a clear entry in `PROJECT_HISTORY.md`;
- a frozen experiment record;
- an immutable git commit/reference containing the full original document.

When adding documentation:

1. declare its status;
2. update an existing canonical document instead of creating a competing roadmap;
3. do not duplicate large formulas/contracts across current files;
4. preserve failed experiments/preregistrations exactly;
5. remove contradictory instructions from current docs;
6. keep historical links discoverable from `PROJECT_HISTORY.md` / `history/README.md` / this index;
7. update this index whenever authority changes.
